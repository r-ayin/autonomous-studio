#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Node Profile — 节点档案（会话级缓存）

将开发态 entityId、运行态 taskId、产出表名等散落在不同 API 的信息
统一存入 DuckDB 表，各脚本写入已知字段、读取缺失字段。

模块级单例，自动连接 .dataworks/session.duckdb：

    from node_profile import get_profile
    np = get_profile()          # 返回 NodeProfile 或 None（DuckDB 不可用时）
    if np:
        np.upsert(14255, task_id=308437862, node_name="sync_xxx", owner="张三")
        np.upsert(14255, task_id=308437862, entity_id="abc-def-123")  # 合并，不覆盖已有
        profile = np.lookup(14255, task_id=308437862)
"""

import os

_COLUMNS = (
    "project_id", "node_name", "entity_id", "task_id",
    "output_table", "owner", "node_type", "deploy_status", "updated_at",
)

_UPDATABLE = (
    "node_name", "entity_id", "task_id",
    "output_table", "owner", "node_type", "deploy_status",
)

_DDL = """
CREATE TABLE IF NOT EXISTS node_profile (
    project_id    BIGINT NOT NULL,
    node_name     VARCHAR,
    entity_id     VARCHAR,
    task_id       BIGINT,
    output_table  VARCHAR,
    owner         VARCHAR,
    node_type     VARCHAR,
    deploy_status INT,
    updated_at    TIMESTAMP DEFAULT current_timestamp
);
"""

_IDX_TASK = """
CREATE UNIQUE INDEX IF NOT EXISTS idx_np_task
    ON node_profile (project_id, task_id) WHERE task_id IS NOT NULL;
"""

_IDX_ENTITY = """
CREATE UNIQUE INDEX IF NOT EXISTS idx_np_entity
    ON node_profile (project_id, entity_id) WHERE entity_id IS NOT NULL;
"""

# ── 模块级单例 ──────────────────────────────────────────────

_instance = None
_DB_DIR = ".dataworks"
_DB_FILE = "session.duckdb"


def get_profile():
    """获取 NodeProfile 单例。DuckDB 不可用时返回 None。

    自动连接当前工作目录下的 .dataworks/session.duckdb，
    与 DuckDBLoader 共享同一个数据库文件。
    """
    global _instance
    if _instance is not None:
        return _instance
    try:
        import duckdb
        db_path = os.path.join(os.getcwd(), _DB_DIR, _DB_FILE)
        os.makedirs(os.path.dirname(db_path), exist_ok=True)
        db = duckdb.connect(db_path)
        _instance = NodeProfile(db)
        return _instance
    except Exception:
        return None


# ── resolve：给任意线索，补全整条链 ───────────────────────

def resolve(project_id, client, *, task_id=None, entity_id=None):
    """给一个线索（task_id 或 entity_id），补全完整节点档案。

    解析链：
      1. 查缓存，有什么先用什么
      2. 有 task_id 缺 entity_id → getVertexByDeployBaseline
      3. 有 entity_id 缺 task_id → GetNode
      4. 有 task_id 缺 output_table → getNodeDetail
      5. 写回缓存，返回完整 dict

    Args:
        project_id: 工作空间 ID
        client: BFFClient 实例（鸭子类型，需要 _do_request / load 方法）
        task_id: 运行态节点 ID（nodeId）
        entity_id: 开发态节点 UUID

    Returns:
        dict（包含 task_id, entity_id, node_name, output_table, owner, node_type 等）
        或 None（完全无法解析时）
    """
    if task_id is None and entity_id is None:
        return None

    np = get_profile()
    if not np:
        return None

    # ── 1. 查缓存 ──
    profile = np.lookup(project_id, task_id=task_id, entity_id=entity_id) or {}

    # 用缓存补全已知 ID
    task_id = task_id or profile.get("task_id")
    entity_id = entity_id or profile.get("entity_id")

    # ── 2. 缺 entity_id → getVertexByDeployBaseline ──
    if task_id and not entity_id:
        entity_id = _api_resolve_entity_id(client, project_id, task_id)

    # ── 3. 缺 task_id → GetNode ──
    if entity_id and not task_id:
        task_id, extra = _api_get_node(client, entity_id)
        if extra:
            profile.update(extra)

    # ── 4. 缺 output_table → getNodeDetail ──
    extras = {}  # 非持久化字段（如 DI 分区模式）
    if task_id and not profile.get("output_table"):
        detail = _api_get_node_detail(client, project_id, task_id)
        if detail:
            for k, v in detail.items():
                if k in _UPDATABLE:
                    profile[k] = v
                else:
                    extras[k] = v

    # ── 5. 写回缓存 ──
    if task_id or entity_id:
        np.upsert(
            project_id,
            task_id=task_id,
            entity_id=entity_id,
            node_name=profile.get("node_name"),
            output_table=profile.get("output_table"),
            owner=profile.get("owner"),
            node_type=profile.get("node_type"),
            deploy_status=profile.get("deploy_status"),
        )

    # 组装返回值（持久化字段 + 非持久化字段）
    result = np.lookup(project_id, task_id=task_id, entity_id=entity_id)
    if result and extras:
        result.update(extras)
    return result


# ── resolve 内部 API 调用（不 import bff_client，靠鸭子类型） ──

def _api_resolve_entity_id(client, project_id, task_id):
    """task_id → entity_id via getVertexByDeployBaseline"""
    try:
        api_meta = client.api_index.get("getVertexByDeployBaseline")
        if not api_meta:
            api_meta = {
                "path": "/ide/getVertexByDeployBaseline",
                "method": "GET",
                "params_type": "params",
                "return_structure": "data{}",
            }
        result = client._do_request("getVertexByDeployBaseline", api_meta,
                                    projectId=int(project_id),
                                    externalBizKey=str(task_id))
        # API 可能返回 code!=0 但不抛异常
        code = result.get("code")
        if code not in (None, 0, "0", 200, "200"):
            import sys
            print(f"[node_profile] getVertexByDeployBaseline 失败: "
                  f"code={code}, msg={result.get('message', '')}", file=sys.stderr)
            return None
        data = result.get("data")
        if not data or not isinstance(data, dict):
            return None
        entity_id = data.get("identifier") or data.get("uuid")
        if entity_id:
            return str(entity_id)
        # data 存在但没有 identifier/uuid，可能结构不同
        import sys
        print(f"[node_profile] getVertexByDeployBaseline 返回数据无 identifier: "
              f"keys={list(data.keys())[:5]}", file=sys.stderr)
        return None
    except Exception as e:
        import sys
        print(f"[node_profile] getVertexByDeployBaseline 异常: {e}", file=sys.stderr)
        return None


def _api_get_node(client, entity_id):
    """entity_id → task_id + 元数据 via GetNode"""
    try:
        detail = client.load("GetNode", uuid=entity_id)
        if not isinstance(detail, dict):
            return None, {}
        task_id = detail.get("taskId")
        extra = {}
        if detail.get("name"):
            extra["node_name"] = detail["name"]
        if detail.get("ownerName"):
            extra["owner"] = detail["ownerName"]
        project = detail.get("project") or {}
        if detail.get("deployStatus"):
            ds = detail["deployStatus"]
            extra["deploy_status"] = 2 if ds == "DeployedProd" else 0
        return int(task_id) if task_id else None, extra
    except Exception:
        return None, {}


def _extract_di_output(client, project_id, task_id):
    """DI 同步节点：从 getNodeCode 提取 writer（产出）和 reader（输入源）信息"""
    try:
        import json as _json
        api_meta = client.api_index.get("getNodeCode")
        if not api_meta:
            return None
        result = client._do_request("getNodeCode", api_meta,
                                    projectId=int(project_id),
                                    env="prod", nodeId=str(task_id))
        raw = result.get("data", {})
        code_str = raw.get("code") if isinstance(raw, dict) else None
        if not code_str:
            return None
        spec = _json.loads(code_str) if isinstance(code_str, str) else code_str
        if not isinstance(spec, dict):
            return None

        info = {}
        for step in spec.get("steps", []):
            category = step.get("category") or step.get("name", "").lower()
            param = step.get("parameter", {})

            if category in ("writer", "Writer"):
                if param.get("table"):
                    info["output_table"] = param["table"]
                if param.get("partition"):
                    info["output_partition"] = param["partition"]

            elif category in ("reader", "Reader"):
                if param.get("table"):
                    info["input_table"] = param["table"]
                # 数据源名从 connection 里提取
                conns = param.get("connection", [])
                if conns and isinstance(conns[0], dict):
                    ds = conns[0].get("datasource")
                    if ds:
                        info["input_datasource"] = ds

        return info if info else None
    except Exception:
        return None


def _api_get_node_detail(client, project_id, task_id):
    """task_id → output_table + node_type + owner via getNodeDetail"""
    try:
        api_meta = client.api_index.get("getNodeDetail")
        if not api_meta:
            api_meta = {
                "path": "/workbench/getNodeDetail",
                "method": "GET",
                "params_type": "params",
                "return_structure": "data{}",
            }
        result = client._do_request("getNodeDetail", api_meta,
                                    projectId=int(project_id), env="prod",
                                    tenantId=1, nodeId=str(task_id))
        code = result.get("code")
        if code not in (None, 0, "0", 200, "200"):
            return None
        data = result.get("data", {})
        if not isinstance(data, dict):
            return None

        info = {}
        # 提取产出表
        outputs = data.get("outputs") or []
        ref_tables = [o.get("refTableName") for o in outputs
                      if isinstance(o, dict) and o.get("refTableName")]
        if ref_tables:
            info["output_table"] = min(set(ref_tables), key=len)
        # 其他字段
        if data.get("nodeName"):
            info["node_name"] = data["nodeName"]
        if data.get("ownerName"):
            info["owner"] = data["ownerName"]
        if data.get("prgTypeName"):
            info["node_type"] = str(data["prgTypeName"])

        # DI 同步节点：writer step 是物理写入目标（优先级高于 outputs 的依赖追踪表名）
        if info.get("node_type") and "同步" in info["node_type"]:
            di_info = _extract_di_output(client, project_id, task_id)
            if di_info:
                if di_info.get("output_table"):
                    info["output_table"] = di_info["output_table"]
                if di_info.get("output_partition"):
                    info["output_partition"] = di_info["output_partition"]
                # DI 输入源
                if di_info.get("input_table"):
                    info["input_table"] = di_info["input_table"]
                if di_info.get("input_datasource"):
                    info["input_datasource"] = di_info["input_datasource"]
        elif not info.get("output_table"):
            di_info = _extract_di_output(client, project_id, task_id)
            if di_info:
                info.update(di_info)

        # 调度配置（非持久化，透传到 extras）
        if data.get("cronExpress"):
            info["cron_express"] = data["cronExpress"]
        if data.get("cycTypeName"):
            info["schedule_type"] = data["cycTypeName"]
        if data.get("baseLineName"):
            info["baseline_name"] = data["baseLineName"]
        if data.get("resGroupName"):
            info["res_group"] = data["resGroupName"]
        if data.get("priority") is not None:
            info["priority"] = int(data["priority"])

        return info if info else None
    except Exception:
        return None


# ── NodeProfile 类 ──────────────────────────────────────────

class NodeProfile:
    """节点档案：会话级 DuckDB 缓存，UPSERT 语义（COALESCE 合并）。"""

    def __init__(self, db_conn):
        self._db = db_conn
        self._ensure_table()

    def _ensure_table(self):
        self._db.execute(_DDL)
        try:
            self._db.execute(_IDX_TASK)
        except Exception:
            pass  # 索引已存在或部分索引不支持
        try:
            self._db.execute(_IDX_ENTITY)
        except Exception:
            pass

    # ── 查找 ────────────────────────────────────────────────

    def _find(self, project_id, *, task_id=None, entity_id=None):
        """按 task_id 或 entity_id 查找，返回 dict（含 rowid）或 None。"""
        if task_id is not None:
            rows = self._db.execute(
                "SELECT rowid, * FROM node_profile WHERE project_id = ? AND task_id = ?",
                [project_id, int(task_id)]
            ).fetchall()
            if rows:
                return self._row_to_dict(rows[0])
        if entity_id is not None:
            rows = self._db.execute(
                "SELECT rowid, * FROM node_profile WHERE project_id = ? AND entity_id = ?",
                [project_id, str(entity_id)]
            ).fetchall()
            if rows:
                return self._row_to_dict(rows[0])
        return None

    def _row_to_dict(self, row):
        # rowid + _COLUMNS
        keys = ("rowid",) + _COLUMNS
        return dict(zip(keys, row))

    # ── 公共 API ────────────────────────────────────────────

    def upsert(self, project_id, *, task_id=None, entity_id=None,
               node_name=None, output_table=None, owner=None,
               node_type=None, deploy_status=None):
        """写入已知字段。COALESCE 语义：新值非 None 才覆盖旧值。"""
        if task_id is None and entity_id is None:
            return

        new_vals = {
            "node_name": node_name,
            "entity_id": str(entity_id) if entity_id is not None else None,
            "task_id": int(task_id) if task_id is not None else None,
            "output_table": output_table,
            "owner": owner,
            "node_type": node_type,
            "deploy_status": int(deploy_status) if deploy_status is not None else None,
        }

        existing = self._find(project_id, task_id=task_id, entity_id=entity_id)

        if existing:
            # COALESCE 合并：只更新非 None 的新值
            updates = {}
            for col in _UPDATABLE:
                nv = new_vals.get(col)
                if nv is not None and nv != existing.get(col):
                    updates[col] = nv
            if not updates:
                return  # 无变化
            set_parts = [f"{k} = ?" for k in updates]
            set_parts.append("updated_at = current_timestamp")
            sql = f"UPDATE node_profile SET {', '.join(set_parts)} WHERE rowid = ?"
            self._db.execute(sql, list(updates.values()) + [existing["rowid"]])

            # 合并后清理孤儿行
            merged_entity = updates.get("entity_id") or existing.get("entity_id")
            merged_task = updates.get("task_id") or existing.get("task_id")
            if merged_entity and merged_task:
                self._cleanup_orphan(project_id, existing["rowid"],
                                     task_id=merged_task, entity_id=merged_entity)
        else:
            # 新建
            cols = {"project_id": project_id}
            cols.update({k: v for k, v in new_vals.items() if v is not None})
            col_names = ", ".join(cols.keys())
            placeholders = ", ".join(["?"] * len(cols))
            self._db.execute(
                f"INSERT INTO node_profile ({col_names}) VALUES ({placeholders})",
                list(cols.values())
            )

    def lookup(self, project_id, *, task_id=None, entity_id=None):
        """查找节点档案，返回 dict（不含 rowid）或 None。"""
        row = self._find(project_id, task_id=task_id, entity_id=entity_id)
        if row:
            row.pop("rowid", None)
            return row
        return None

    def bulk_upsert(self, project_id, rows):
        """批量写入。rows: list[dict]，每个 dict 的 key 同 upsert 的关键字参数。"""
        for row in rows:
            try:
                self.upsert(project_id, **row)
            except Exception:
                pass  # 单行失败不影响整批

    # ── 内部工具 ────────────────────────────────────────────

    def _cleanup_orphan(self, project_id, keep_rowid, *, task_id, entity_id):
        """删除同一节点因分批写入产生的重复行（保留 keep_rowid）。"""
        try:
            self._db.execute(
                "DELETE FROM node_profile WHERE project_id = ? AND entity_id = ? "
                "AND rowid != ? AND (task_id IS NULL OR task_id = ?)",
                [project_id, str(entity_id), keep_rowid, int(task_id)]
            )
            self._db.execute(
                "DELETE FROM node_profile WHERE project_id = ? AND task_id = ? "
                "AND rowid != ? AND (entity_id IS NULL OR entity_id = ?)",
                [project_id, int(task_id), keep_rowid, str(entity_id)]
            )
        except Exception:
            pass
