#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Table Profile — 表档案（会话级缓存）

把 (project_id, table_name) 解析成 DQC 等 API 所需的 tableGuid，
同时通过 searchTables 校验表存在，避免「拼字符串 + 静默失败」。

模块级单例，自动连接 .dataworks/session.duckdb（与 node_profile 共享）：

    from table_profile import resolve
    profile = resolve(client, project_id=14255, table_name="my_table")
    # → {"projectId": 14255, "tableName": "my_table",
    #    "database": "autotest_dev", "dbType": "ODPS",
    #    "tableGuid": "odps.autotest_dev.my_table",
    #    "entityGuid": "...", "entityType": "maxcompute-table"}

支持 'database.table' 短名（同名跨库时用来消歧）。
"""

import json
import os
import sys


_DDL = """
CREATE TABLE IF NOT EXISTS table_profile (
    project_id   BIGINT NOT NULL,
    table_name   VARCHAR NOT NULL,
    db_name      VARCHAR,
    db_type      VARCHAR,
    table_guid   VARCHAR,
    entity_guid  VARCHAR,
    entity_type  VARCHAR,
    updated_at   TIMESTAMP DEFAULT current_timestamp,
    PRIMARY KEY (project_id, table_name)
);
"""

_instance = None
_DB_DIR = ".dataworks"
_DB_FILE = "session.duckdb"


def get_profile():
    """获取 TableProfile 单例。DuckDB 不可用时返回 None。"""
    global _instance
    if _instance is not None:
        return _instance
    try:
        import duckdb
        db_path = os.path.join(os.getcwd(), _DB_DIR, _DB_FILE)
        os.makedirs(os.path.dirname(db_path), exist_ok=True)
        db = duckdb.connect(db_path)
        _instance = TableProfile(db)
        return _instance
    except Exception:
        return None


def resolve(client, project_id, table_name):
    """解析表 → tableGuid + 元信息（含校验存在性）。

    Args:
        client: BFFClient 实例
        project_id: 工作空间 ID
        table_name: 表名（支持 'database.table' 短名指定库）

    Returns:
        dict: projectId, tableName, database, dbType, tableGuid, entityGuid, entityType

    Raises:
        ValueError: 项目下无此表 / 同名跨库未指定 database
    """
    project_id = int(project_id)

    # 'db.table' 短名拆分
    if "." in table_name:
        db_hint, simple_name = table_name.split(".", 1)
    else:
        db_hint, simple_name = None, table_name

    # ── 1. 查缓存 ──
    tp = get_profile()
    if tp:
        cached = tp.lookup(project_id, simple_name)
        if cached and cached.get("table_guid"):
            if not db_hint or (cached.get("db_name") or "").lower() == db_hint.lower():
                return _to_result(cached)

    # ── 2. searchTables 校验存在 + 取真实 database ──
    matches = _search(client, project_id, simple_name)
    if not matches:
        raise ValueError(
            f"未在项目 {project_id} 下找到表 '{simple_name}'\n"
            f"→ 用 search_table.py \"{simple_name}\" 检查表名是否正确"
        )

    if db_hint:
        filtered = [m for m in matches
                    if (m.get("databaseName") or "").lower() == db_hint.lower()]
        if not filtered:
            dbs = ", ".join(sorted({m.get("databaseName") or "?" for m in matches}))
            raise ValueError(
                f"表 '{simple_name}' 不在 database '{db_hint}' 下，"
                f"实际所在: {dbs}"
            )
        matches = filtered

    if len(matches) > 1:
        dbs = sorted({m.get("databaseName") or "?" for m in matches})
        raise ValueError(
            f"项目 {project_id} 下有 {len(matches)} 张同名表 '{simple_name}' "
            f"(databases: {', '.join(dbs)})\n"
            f"→ 用 'database.table' 形式指定，例如 '{dbs[0]}.{simple_name}'"
        )

    table = matches[0]
    db_name = table.get("databaseName") or ""
    entity_guid = table.get("entityGuid") or ""
    entity_type = table.get("entityType") or "maxcompute-table"

    # DQC 的 tableGuid 始终用 'odps' 前缀（涵盖 maxcompute）
    table_guid = f"odps.{db_name}.{simple_name}"
    db_type = "ODPS"

    # ── 3. 写缓存 ──
    if tp:
        tp.upsert(project_id, simple_name,
                  db_name=db_name, db_type=db_type,
                  table_guid=table_guid, entity_guid=entity_guid,
                  entity_type=entity_type)

    return {
        "projectId": project_id,
        "tableName": simple_name,
        "database": db_name,
        "dbType": db_type,
        "tableGuid": table_guid,
        "entityGuid": entity_guid,
        "entityType": entity_type,
    }


def _search(client, project_id, table_name):
    """精确匹配表名，返回所有命中（可能跨多个 database）。"""
    matches = []
    for entity_type in ("maxcompute-table", "dlf-table"):
        try:
            result = client.load(
                "searchTables",
                keyword=table_name,
                entityType=entity_type,
                projectIds=json.dumps([str(project_id)]),
                pageSize=20,
                max_pages=1,
            )
            if isinstance(result, list):
                exact = [t for t in result
                         if (t.get("name") or "").lower() == table_name.lower()]
                matches.extend(exact)
        except Exception as e:
            print(f"[table_profile] searchTables({entity_type}) 失败: {e}",
                  file=sys.stderr)
    return matches


def _to_result(row):
    return {
        "projectId": row.get("project_id"),
        "tableName": row.get("table_name"),
        "database": row.get("db_name"),
        "dbType": row.get("db_type"),
        "tableGuid": row.get("table_guid"),
        "entityGuid": row.get("entity_guid"),
        "entityType": row.get("entity_type"),
    }


# ── TableProfile 类（CRUD） ──────────────────────────────────

class TableProfile:
    """表档案：会话级 DuckDB 缓存，UPSERT 语义（新值非 None 才覆盖）。"""

    def __init__(self, db_conn):
        self._db = db_conn
        self._db.execute(_DDL)

    def lookup(self, project_id, table_name):
        rows = self._db.execute(
            "SELECT project_id, table_name, db_name, db_type, "
            "table_guid, entity_guid, entity_type "
            "FROM table_profile WHERE project_id = ? AND table_name = ?",
            [int(project_id), table_name]
        ).fetchall()
        if not rows:
            return None
        keys = ("project_id", "table_name", "db_name", "db_type",
                "table_guid", "entity_guid", "entity_type")
        return dict(zip(keys, rows[0]))

    def upsert(self, project_id, table_name, *, db_name=None, db_type=None,
               table_guid=None, entity_guid=None, entity_type=None):
        new_vals = {
            "db_name": db_name,
            "db_type": db_type,
            "table_guid": table_guid,
            "entity_guid": entity_guid,
            "entity_type": entity_type,
        }
        existing = self.lookup(project_id, table_name)
        if existing:
            updates = {k: v for k, v in new_vals.items()
                       if v is not None and v != existing.get(k)}
            if not updates:
                return
            set_parts = [f"{k} = ?" for k in updates]
            set_parts.append("updated_at = current_timestamp")
            sql = (f"UPDATE table_profile SET {', '.join(set_parts)} "
                   f"WHERE project_id = ? AND table_name = ?")
            self._db.execute(sql,
                             list(updates.values()) + [int(project_id), table_name])
        else:
            cols = {"project_id": int(project_id), "table_name": table_name}
            cols.update({k: v for k, v in new_vals.items() if v is not None})
            col_names = ", ".join(cols.keys())
            placeholders = ", ".join(["?"] * len(cols))
            self._db.execute(
                f"INSERT INTO table_profile ({col_names}) VALUES ({placeholders})",
                list(cols.values())
            )
