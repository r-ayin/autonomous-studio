#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
DuckDB 数据加载器 —— 快照缓存层

核心设计：
  - 每次 read() 生成独立快照表，表名 {api_name}_r{轮次}_c{调用序号}
  - 不做 UPSERT，同一 API 不同参数的调用各自独立
  - 查询参数注入：call_params 合并到每行数据，形成完整实体记录
  - File DB 跨脚本持久化，Memory DB 临时分析用完即弃

被 bff_client.py 自动调用，也可独立使用：

    from duckdb_loader import DuckDBLoader
    loader = DuckDBLoader()
    table_name = loader.load("ListDataSources", data, call_params={"projectId": "14255"})
    loader.sql(f"SELECT name, type FROM {table_name}")
"""

import json
import os
import re
import sys
from datetime import datetime

try:
    import duckdb
except ImportError:
    raise ImportError("缺少 duckdb 库，请先安装: pip install duckdb")


_DB_FILE = "session.duckdb"
_RUNTIME_DIR = ".dataworks"


class DuckDBLoader:
    """两层 DuckDB：Memory DB（临时分析） + File DB（session 级持久化）"""

    def __init__(self):
        runtime_dir = os.path.join(os.getcwd(), _RUNTIME_DIR)
        os.makedirs(runtime_dir, exist_ok=True)
        db_path = os.path.join(runtime_dir, _DB_FILE)
        self.db = duckdb.connect(db_path)       # File DB: session 级持久化
        self._mem = duckdb.connect()              # Memory DB: 临时分析
        self._tables = {}  # table_name → {"api_name", "call_params", "row_count", "schema", "called_at"}
        self._round = self._next_round()
        self._call_seq = 0
        self._log_file = os.path.join(os.getcwd(), "logs", "dw_bff_calls.log")
        self._restore_tables()

    def _log(self, message):
        """写入日志文件（供运维排查，不输出到 stdout/stderr）"""
        try:
            os.makedirs(os.path.dirname(self._log_file), exist_ok=True)
            with open(self._log_file, "a", encoding="utf-8") as f:
                f.write(json.dumps({"ts": datetime.now().isoformat(), "source": "DuckDBLoader", "msg": message}, ensure_ascii=False) + "\n")
        except Exception:
            pass

    def _next_round(self):
        """从元数据表读取上次轮次号 +1；首次使用返回 1"""
        try:
            rows = self.db.execute(
                "SELECT max_round FROM _dw_metadata LIMIT 1"
            ).fetchall()
            return rows[0][0] + 1 if rows else 1
        except Exception:
            return 1

    def _save_round(self):
        """持久化当前轮次号到元数据表"""
        self.db.execute("CREATE TABLE IF NOT EXISTS _dw_metadata (max_round INTEGER)")
        self.db.execute("DELETE FROM _dw_metadata")
        self.db.execute(f"INSERT INTO _dw_metadata VALUES ({self._round})")

    def close(self):
        """关闭 DuckDB 连接"""
        if self._mem:
            self._mem.close()
            self._mem = None
        if self.db:
            self.db.close()
            self.db = None

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()

    # 表名格式：{api_name}_r{N}_c{N}
    _TABLE_NAME_RE = re.compile(r'^(.+)_r(\d+)_c(\d+)$')

    def _restore_tables(self):
        """从已有数据库文件恢复 _tables 元信息"""
        try:
            rows = self.db.execute(
                "SELECT table_name FROM information_schema.tables "
                "WHERE table_schema = 'main' AND table_type = 'BASE TABLE'"
            ).fetchall()
        except Exception:
            return

        for (tbl,) in rows:
            if tbl == '_dw_metadata':
                continue
            try:
                row_count = self.db.execute(f'SELECT COUNT(*) FROM "{tbl}"').fetchone()[0]
                schema = self._extract_schema(tbl)

                m = self._TABLE_NAME_RE.match(tbl)
                if m:
                    api_name = m.group(1)
                    r = int(m.group(2))
                    c = int(m.group(3))
                else:
                    api_name = tbl
                    r = 0
                    c = 0

                self._tables[tbl] = {
                    "api_name": api_name,
                    "row_count": row_count,
                    "schema": schema,
                    "called_at": None,
                }

                # 从已有表推断 _call_seq 上限，避免序号冲突
                if r == self._round and c >= self._call_seq:
                    self._call_seq = c
            except Exception:
                continue

    def _extract_schema(self, table_name):
        """从 File DB 提取表 schema：列名 + 类型 + 样本值"""
        schema = []
        try:
            type_rows = self.db.execute(
                f"SELECT column_name, data_type FROM information_schema.columns "
                f"WHERE table_name = '{table_name}' AND table_schema = 'main' "
                f"ORDER BY ordinal_position"
            ).fetchall()
        except Exception:
            return schema

        for col_name, data_type in type_rows:
            entry = {"name": col_name, "type": data_type}
            try:
                samples = self.db.execute(
                    f'SELECT DISTINCT "{col_name}" FROM "{table_name}" '
                    f'WHERE "{col_name}" IS NOT NULL LIMIT 3'
                ).fetchall()
                sample_vals = [r[0] for r in samples]
                cleaned = []
                for v in sample_vals:
                    if isinstance(v, str) and len(v) > 60:
                        cleaned.append(v[:57] + "...")
                    else:
                        cleaned.append(v)
                if cleaned:
                    entry["sample"] = cleaned
            except Exception:
                pass
            schema.append(entry)

        return schema

    def load(self, api_name, data, call_params=None, primary_key=None):
        """
        将 API 返回数据灌入 DuckDB（独立快照表）

        每次调用生成新的快照表，表名 {api_name}_r{轮次}_c{序号}。

        Args:
            api_name: API 名称
            data: API 返回的解析后数据（list/dict/str/bool/number）
            call_params: 调用参数 dict，如 {"projectId": "14255"}
            primary_key: 保留参数（不再用于 UPSERT，仅为接口兼容）

        Returns:
            str: 快照表名（如 "ListDataSources_r1_c1"）
        """
        if data is None:
            return None

        # 标准化为 list[dict]
        if not isinstance(data, (list, dict)):
            data = {"value": data}
        if isinstance(data, dict):
            data = [data]
        if not data:
            self._log(f"{api_name} 数据为空, params={call_params}")
            return None

        # 注入 call_params（row 已有同名字段不覆盖）
        if call_params:
            skip_params = {"pageSize", "pageNumber", "pageNum", "pageStart", "confirmed"}
            inject = {k: str(v) for k, v in call_params.items() if k not in skip_params}
            if inject:
                enriched = []
                for row in data:
                    if isinstance(row, dict):
                        merged = dict(inject)
                        merged.update(row)
                        enriched.append(merged)
                    else:
                        enriched.append(row)
                data = enriched

        # 生成快照表名
        self._call_seq += 1
        table_name = f"{api_name}_r{self._round}_c{self._call_seq}"

        # 写入临时 JSON
        tmp_path = f"/tmp/_duckdb_loader_{table_name}_{os.getpid()}.json"
        try:
            with open(tmp_path, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False)

            # File DB: 直接 CREATE（不做 UPSERT）
            self.db.execute(f'DROP TABLE IF EXISTS "{table_name}"')
            self.db.execute(
                f"CREATE TABLE \"{table_name}\" AS SELECT * FROM read_json_auto('{tmp_path}')"
            )

            # Memory DB: 同样创建（供 auto_summary 分析）
            self._mem.execute(f'DROP TABLE IF EXISTS "{table_name}"')
            self._mem.execute(
                f"CREATE TABLE \"{table_name}\" AS SELECT * FROM read_json_auto('{tmp_path}')"
            )

        finally:
            if os.path.exists(tmp_path):
                os.remove(tmp_path)

        # 更新元信息
        row_count = self.db.execute(f'SELECT COUNT(*) FROM "{table_name}"').fetchone()[0]
        schema = self._extract_schema(table_name)
        self._tables[table_name] = {
            "api_name": api_name,
            "call_params": call_params,
            "row_count": row_count,
            "schema": schema,
            "called_at": datetime.now().isoformat(),
        }
        self._save_round()
        return table_name

    def get_tables_for_api(self, api_name):
        """返回某个 API 的所有快照表名，按时间倒序"""
        return [name for name in sorted(self._tables.keys(), reverse=True)
                if self._tables[name].get("api_name") == api_name]

    def drop_api_tables(self, api_name):
        """删除某个 API 的所有快照（写操作缓存失效用）"""
        for name in self.get_tables_for_api(api_name):
            try:
                self.db.execute(f'DROP TABLE IF EXISTS "{name}"')
            except Exception:
                pass
            try:
                self._mem.execute(f'DROP TABLE IF EXISTS "{name}"')
            except Exception:
                pass
            self._tables.pop(name, None)

    def drop_table(self, table_name):
        """删除指定表（File DB + Memory DB + 元信息），保留向后兼容"""
        try:
            self.db.execute(f'DROP TABLE IF EXISTS "{table_name}"')
        except Exception:
            pass
        try:
            self._mem.execute(f'DROP TABLE IF EXISTS "{table_name}"')
        except Exception:
            pass
        self._tables.pop(table_name, None)

    def sql(self, query):
        """执行 SQL 查询，打印格式化表格并返回 list[dict]（查 File DB）

        同时做两件事：
        1. stdout 打印格式化表格（供 agent / 人类阅读）
        2. 返回 list[dict]（供脚本程序化处理）

        Example:
            rows = client.loader.sql(f"SELECT name, type FROM {client.last_table}")
            for r in rows:
                print(r["name"])  # 直接用字段名访问
        """
        try:
            self.db.sql(query).show()
            return self.fetch(query)
        except Exception as e:
            print(f"[DuckDBLoader] SQL 执行失败: {e}", file=sys.stderr)
            return []

    def fetch(self, query):
        """执行 SQL 查询，仅返回 list[dict]，不打印（查 File DB）

        适合工具脚本等不需要 stdout 输出的场景。
        需要同时打印和返回数据时用 sql()。
        """
        try:
            result = self.db.execute(query)
            columns = [desc[0] for desc in result.description]
            rows = result.fetchall()
            return [dict(zip(columns, row)) for row in rows]
        except Exception as e:
            print(f"[DuckDBLoader] SQL 执行失败: {e}", file=sys.stderr)
            return []

    def tables(self):
        """打印所有已加载的表"""
        if not self._tables:
            print("[DuckDBLoader] 未加载任何数据")
            return
        print("已加载的表:")
        for name, info in self._tables.items():
            cols = [s["name"] for s in info.get("schema", [])]
            api = info.get("api_name", name)
            params = info.get("call_params")
            params_str = ""
            if params:
                params_str = " | " + ", ".join(f"{k}={v}" for k, v in params.items()
                                                if k not in {"pageSize", "pageNumber", "pageNum", "pageStart", "confirmed"})
            print(f"  {name} ({api}): {info['row_count']} 行{params_str}, 列: {cols}")

    def get_table_names(self):
        """返回所有已加载的表名列表"""
        return list(self._tables.keys())

    def get_table_info(self, table_name):
        """返回指定表的元信息"""
        return self._tables.get(table_name)

    def get_schema(self, table_name):
        """返回指定表的完整 schema（列名+类型+样本值）"""
        info = self._tables.get(table_name)
        if info:
            return info.get("schema", [])
        return []
