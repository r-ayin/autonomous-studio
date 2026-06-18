"""数据源注册表

从 datasource_meta.yaml + JSON schema 文件构建统一注册表。
提供 step_type 查找、别名解析、参数模式查询。
"""

import json
from pathlib import Path
from typing import Any, Dict, List, Optional

import yaml

_DIR = Path(__file__).parent
_META_PATH = _DIR / "datasource_meta.yaml"
_ALIASES_PATH = _DIR / "type_aliases.yaml"
_DEFAULT_SCHEMA_DIR = _DIR.parent.parent / "reference" / "schemas"


class DatasourceInfo:
    """单个数据源的元数据 + schema 信息"""

    __slots__ = (
        "step_type", "roles", "entity_label", "sub_type",
        "reader_param_mode", "reader_prefer", "reader_defaults",
        "reader_auto_fields", "reader_table_field", "reader_required",
        "reader_extra_probe_params",
        "writer_param_mode", "writer_defaults", "writer_table_field",
        "writer_required", "writer_enums",
    )

    def __init__(self, step_type: str, meta: Dict[str, Any],
                 reader_schema: Optional[Dict] = None,
                 writer_schema: Optional[Dict] = None):
        self.step_type = step_type
        self.roles: List[str] = meta.get("roles", [])
        self.entity_label: str = meta.get("entity_label", "表")  # "表" / "Collection" / "Topic" / "文件路径"
        self.sub_type: str = meta.get("sub_type", "public")

        # Reader
        rm = meta.get("reader", {})
        self.reader_param_mode = rm.get("param_mode", "toplevel")
        self.reader_prefer = rm.get("prefer", self.reader_param_mode)
        self.reader_defaults = rm.get("defaults", {})
        self.reader_auto_fields = rm.get("auto_fields", {})
        self.reader_table_field = rm.get("table_field", "table")
        self.reader_extra_probe_params: List[str] = rm.get("extra_probe_params", [])
        self.reader_required = _schema_required(reader_schema) if reader_schema else []

        # Writer
        wm = meta.get("writer", {})
        self.writer_param_mode = wm.get("param_mode", "toplevel")
        self.writer_defaults = wm.get("defaults", {})
        self.writer_table_field = wm.get("table_field", "table")
        wr = _schema_required(writer_schema) if writer_schema else []
        self.writer_required = wr
        self.writer_enums = _schema_enums(writer_schema) if writer_schema else {}

    @property
    def can_read(self) -> bool:
        return "reader" in self.roles

    @property
    def can_write(self) -> bool:
        return "writer" in self.roles


def _schema_required(schema: Dict) -> List[str]:
    return schema.get("properties", {}).get("parameter", {}).get("required", [])


def _schema_enums(schema: Dict) -> Dict[str, List]:
    props = schema.get("properties", {}).get("parameter", {}).get("properties", {})
    return {k: v["enum"] for k, v in props.items() if "enum" in v}


class DatasourceRegistry:
    """数据源注册表：step_type → DatasourceInfo，支持别名解析"""

    def __init__(self, schema_dir: Optional[Path] = None):
        self._schema_dir = Path(schema_dir) if schema_dir else _DEFAULT_SCHEMA_DIR
        self._entries: Dict[str, DatasourceInfo] = {}
        self._aliases: Dict[str, str] = {}
        self._build()

    def _build(self):
        # 1. 加载元数据
        meta_all: Dict[str, Any] = {}
        if _META_PATH.is_file():
            with open(_META_PATH, "r", encoding="utf-8") as f:
                meta_all = yaml.safe_load(f) or {}

        # 2. 加载别名
        if _ALIASES_PATH.is_file():
            with open(_ALIASES_PATH, "r", encoding="utf-8") as f:
                self._aliases = yaml.safe_load(f) or {}

        # 3. 加载 schema 文件，按 stepType 分组
        reader_schemas: Dict[str, Dict] = {}
        writer_schemas: Dict[str, Dict] = {}
        if self._schema_dir.is_dir():
            for sf in self._schema_dir.glob("*.schema.json"):
                if sf.name in ("DIJob.schema.json", "DIReaderBase.schema.json", "DIWriterBase.schema.json"):
                    continue
                with open(sf, "r", encoding="utf-8") as f:
                    schema = json.load(f)
                st = schema.get("properties", {}).get("stepType", {}).get("const", "").lower()
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
                    reader_schemas[st] = schema
                if is_w:
                    writer_schemas[st] = schema

        # 4. 构建 entries
        # 先从 meta 构建
        for key, meta in meta_all.items():
            st = meta.get("step_type", key).lower()
            info = DatasourceInfo(
                st, meta,
                reader_schema=reader_schemas.get(st),
                writer_schema=writer_schemas.get(st),
            )
            self._entries[st] = info

        # 对 schema 中存在但 meta 中没有的 stepType，自动注册（保证不遗漏）
        for st in set(reader_schemas.keys()) | set(writer_schemas.keys()):
            if st not in self._entries:
                roles = []
                if st in reader_schemas:
                    roles.append("reader")
                if st in writer_schemas:
                    roles.append("writer")
                self._entries[st] = DatasourceInfo(
                    st, {"roles": roles},
                    reader_schema=reader_schemas.get(st),
                    writer_schema=writer_schemas.get(st),
                )

    def resolve(self, name: str) -> Optional[DatasourceInfo]:
        """解析数据源名称（含别名）→ DatasourceInfo"""
        key = name.strip().lower()
        # 直接匹配
        if key in self._entries:
            return self._entries[key]
        # 别名
        resolved = self._aliases.get(key)
        if resolved and resolved in self._entries:
            return self._entries[resolved]
        return None

    def supported_readers(self) -> List[str]:
        return sorted(k for k, v in self._entries.items() if v.can_read)

    def supported_writers(self) -> List[str]:
        return sorted(k for k, v in self._entries.items() if v.can_write)

    def all_step_types(self) -> List[str]:
        return sorted(self._entries.keys())
