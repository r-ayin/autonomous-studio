"""DI 配置校验器

基于 JSON Schema 对 DI 任务配置进行严格校验。
从 validate_di_config.py 迁入核心逻辑，不含 CLI。
"""

import json
from pathlib import Path
from typing import Any, Dict, List, Tuple

import warnings
warnings.filterwarnings("ignore", message=".*RefResolver.*deprecated.*")

try:
    from jsonschema import Draft7Validator, RefResolver
except ImportError:
    Draft7Validator = None
    RefResolver = None

_DEFAULT_SCHEMA_DIR = Path(__file__).parent.parent.parent / "reference" / "schemas"


class DIConfigValidator:
    """DI 离线同步任务配置校验器"""

    def __init__(self, schema_dir=None):
        if Draft7Validator is None:
            raise ImportError("需要安装 jsonschema: pip install jsonschema")
        self.schema_dir = Path(schema_dir).resolve() if schema_dir else _DEFAULT_SCHEMA_DIR.resolve()
        self.errors: List[str] = []
        self.warnings: List[str] = []
        self._load_schemas()
        self._build_step_type_map()

    def _load_schemas(self):
        self.schema_store: Dict[str, Any] = {}
        for sf in self.schema_dir.glob("*.schema.json"):
            with open(sf, "r", encoding="utf-8") as f:
                self.schema_store[sf.name] = json.load(f)
        self.main_schema = self.schema_store.get("DIJob.schema.json")
        if not self.main_schema:
            raise FileNotFoundError(f"未找到 DIJob.schema.json，目录: {self.schema_dir}")

    def _build_step_type_map(self):
        self.step_type_map: Dict[Tuple[str, str], str] = {}
        for name, schema in self.schema_store.items():
            if name in ("DIJob.schema.json", "DIReaderBase.schema.json", "DIWriterBase.schema.json"):
                continue
            st = schema.get("properties", {}).get("stepType", {}).get("const")
            if not st:
                continue
            all_of = schema.get("allOf", [])
            is_r = any("ReaderBase" in r.get("$ref", "") for r in all_of)
            is_w = any("WriterBase" in r.get("$ref", "") for r in all_of)
            if not is_r and not is_w:
                title = schema.get("title", "").lower()
                is_r = "reader" in title
                is_w = "writer" in title
            if is_r:
                self.step_type_map[(st.lower(), "reader")] = name
            if is_w:
                self.step_type_map[(st.lower(), "writer")] = name

    def _create_resolver(self, schema):
        base_uri = "file://" + str(self.schema_dir) + "/"
        store = {base_uri + n: s for n, s in self.schema_store.items()}
        return RefResolver(base_uri=base_uri, referrer=schema, store=store)

    def validate(self, config) -> Tuple[bool, List[str], List[str]]:
        """完整校验，返回 (is_valid, errors, warnings)"""
        self.errors = []
        self.warnings = []

        if isinstance(config, str):
            try:
                config = json.loads(config)
            except json.JSONDecodeError as e:
                self.errors.append(f"[JSON解析] {e}")
                return False, self.errors, self.warnings

        if not isinstance(config, dict):
            self.errors.append("[JSON解析] 配置必须是 JSON 对象")
            return False, self.errors, self.warnings

        self._validate_structure(config)
        self._validate_steps_schema(config)
        self._validate_business_rules(config)

        return len(self.errors) == 0, self.errors, self.warnings

    def _validate_structure(self, config):
        structural = {
            "$schema": "http://json-schema.org/draft-07/schema#",
            "type": "object",
            "properties": {
                "steps": {"type": "array"},
                "order": self.main_schema.get("properties", {}).get("order", {}),
                "setting": self.main_schema.get("properties", {}).get("setting", {}),
            },
        }
        for err in sorted(Draft7Validator(structural).iter_errors(config), key=lambda e: list(e.path)):
            path = " → ".join(str(p) for p in err.absolute_path) or "(根级)"
            self.errors.append(f"[结构校验] {path} | {err.message}")

    def _validate_steps_schema(self, config):
        steps = config.get("steps", [])
        if not isinstance(steps, list):
            return
        for i, step in enumerate(steps):
            st = step.get("stepType", "")
            cat = step.get("category", "")
            schema_name = self.step_type_map.get((st.lower(), cat))
            if not schema_name:
                if st:
                    self.warnings.append(f"[steps[{i}]] 未找到 {st}/{cat} 对应 Schema，跳过")
                continue
            schema = self.schema_store[schema_name]
            try:
                resolver = self._create_resolver(schema)
                for err in sorted(Draft7Validator(schema, resolver=resolver).iter_errors(step),
                                  key=lambda e: list(e.path)):
                    path = " → ".join(str(p) for p in err.absolute_path) or "(根级)"
                    self.errors.append(f"[steps[{i}] {st}/{cat}] {path} | {err.message}")
            except Exception as e:
                self.warnings.append(f"[steps[{i}]] Schema 校验异常: {e}")

    def _validate_business_rules(self, config):
        # 顶级必填
        for f in ("type", "version", "steps", "order", "setting", "extend"):
            if f not in config:
                self.errors.append(f"[必填字段] 缺少 '{f}'")

        t = config.get("type")
        if t is not None and t != "job":
            self.errors.append(f"[type] 应为 'job'，当前 '{t}'")

        v = config.get("version")
        if v is not None and v != "2.0":
            self.warnings.append(f"[version] 建议 '2.0'，当前 '{v}'")

        # steps
        steps = config.get("steps", [])
        if not isinstance(steps, list) or not steps:
            self.errors.append("[steps] 不能为空")
        else:
            cats = [s.get("category") for s in steps]
            if "reader" not in cats:
                self.errors.append("[steps] 缺少 reader")
            if "writer" not in cats:
                self.errors.append("[steps] 缺少 writer")
            for idx, s in enumerate(steps):
                if not s.get("name"):
                    self.errors.append(f"[steps[{idx}]] 缺少 name")
                if not s.get("stepType"):
                    self.errors.append(f"[steps[{idx}]] 缺少 stepType")

        # order.hops
        order = config.get("order")
        if isinstance(order, dict):
            hops = order.get("hops", [])
            if not hops:
                self.errors.append("[order.hops] 不能为空")
            else:
                names = {s.get("name") for s in steps if s.get("name")}
                for j, h in enumerate(hops):
                    for d in ("from", "to"):
                        val = h.get(d)
                        if not val:
                            self.errors.append(f"[order.hops[{j}]] 缺少 {d}")
                        elif val not in names:
                            self.errors.append(f"[order.hops[{j}].{d}] '{val}' 不在 steps 中")

        # setting.speed
        setting = config.get("setting")
        if isinstance(setting, dict) and "speed" not in setting:
            self.errors.append("[setting] 缺少 speed")

        # extend
        extend = config.get("extend")
        if isinstance(extend, dict):
            for field, desc in {"resourceGroup": "资源组", "mode": "模式", "__new__": "新建标识"}.items():
                if field not in extend:
                    self.errors.append(f"[extend] 缺少 '{field}'（{desc}）")
            mode = extend.get("mode")
            if mode and mode not in ("wizard", "code"):
                self.errors.append(f"[extend.mode] 无效 '{mode}'")
            rg = extend.get("resourceGroup", "")
            if isinstance(rg, str) and ("<" in rg or ">" in rg or not rg.strip()):
                self.warnings.append(f"[extend.resourceGroup] 需替换: '{rg}'")
