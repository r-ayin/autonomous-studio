#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
数据分析工具 —— 根据 API 结果特征自动统计重要维度

职责：只管分析，不管数据加载（加载由 duckdb_loader.py 负责）。
根据列的基数（cardinality）自动识别维度列和度量列，生成统计摘要。

核心逻辑：
  - 低基数列（distinct 值少，如 region/status）→ 维度列，自动 GROUP BY 计数
  - 数值列 → 度量列，算 min/max/avg/sum
  - 高基数列（distinct 值多，如 id/name）→ 明细列，只展示样本
  - 时间戳列 → 时间范围

用法:
    from data_analyzer import DataAnalyzer
    da = DataAnalyzer(loader)
    da.auto_summary("ListPartitions")   # 自动分析任意 API 结果
    da.sql("SELECT * FROM ListPartitions WHERE name LIKE '%group%'")  # 明细查询

依赖: duckdb_loader.py, duckdb
"""

import os
import sys

# 列分类阈值
MAX_DIMENSION_CARDINALITY = 50   # distinct <= 50 的列视为维度
MIN_DIMENSION_ROWS_RATIO = 0.3   # distinct/rows > 0.3 的不当维度（除非 distinct <= 10）


class DataAnalyzer:
    """根据数据特征自动统计重要维度（使用 Memory DB 做临时分析）"""

    def __init__(self, loader, skill_scripts_dir=None):
        """
        Args:
            loader: DuckDBLoader 实例（已灌入数据）
            skill_scripts_dir: skill 的 scripts 目录路径（用于生成可执行命令）
        """
        self.loader = loader
        self.db = loader._mem  # 分析用 Memory DB（临时表，不影响 File DB）
        self._skill_scripts_dir = skill_scripts_dir

    def sql(self, query):
        """执行 SQL 查询并打印结果（查 File DB，面向用户）"""
        return self.loader.sql(query)

    def fetch(self, query):
        """执行 SQL 查询，返回 list[dict]（查 File DB，面向用户）"""
        return self.loader.fetch(query)

    def _mem_fetch(self, query):
        """内部方法：在 Memory DB 上执行分析查询"""
        try:
            result = self.db.execute(query)
            columns = [desc[0] for desc in result.description]
            rows = result.fetchall()
            return [dict(zip(columns, row)) for row in rows]
        except Exception as e:
            print(f"[DataAnalyzer] Memory SQL 失败: {e}", file=sys.stderr)
            return []

    def auto_summary(self, table_name, quiet=False, sample_row=None):
        """
        根据数据特征自动生成统计摘要

        工作流程：
        1. 获取表的列信息和行数
        2. 对每列计算 distinct count 和数据类型
        3. 分类：维度列 / 度量列 / 明细列 / 时间列
        4. 维度列：GROUP BY 计数
        5. 度量列：min/max/avg/sum
        6. 时间列：时间范围
        7. 明细列：展示样本值

        Args:
            table_name: DuckDB 表名
            quiet: True 时跳过 stdout 输出（仍返回分析结果）
            sample_row: 原始数据的第一行 dict（用于展开 STRUCT[] 子字段名）

        Returns:
            dict: 统计结果，包含 dimensions, metrics, time_range, sample 等
        """
        info = self.loader.get_table_info(table_name)
        if not info:
            print(f"[DataAnalyzer] 表 {table_name} 不存在", file=sys.stderr)
            return None

        row_count = info["row_count"]
        # 兼容新旧格式：schema 是 [{name, type, sample}] 或 columns 是 [str]
        schema = info.get("schema", [])
        if schema:
            columns = [s["name"] for s in schema]
        else:
            columns = info.get("columns", [])

        if row_count == 0:
            print(f"[{table_name}] 空表，无数据")
            return None

        # 1. 分析每列的特征
        col_profiles = self._profile_columns(table_name, columns, row_count)

        # 2. 分类
        dimensions = []   # 低基数 → GROUP BY
        metrics = []      # 数值 → 聚合
        time_cols = []     # 时间戳 → 范围
        detail_cols = []   # 高基数 → 样本

        for cp in col_profiles:
            if cp["category"] == "dimension":
                dimensions.append(cp)
            elif cp["category"] == "metric":
                metrics.append(cp)
            elif cp["category"] == "time":
                time_cols.append(cp)
            else:
                detail_cols.append(cp)

        # 3. 检测停产维度（从明细列的 KV 展开中获取）
        stalled_dims = []
        expanded_views = []
        if detail_cols:
            stalled_dims, expanded_views = self._detect_stalled_dims(table_name, detail_cols, time_cols)

        # 4. stdout: 表名 + 行数 + 列名（紧凑格式，供 agent 直接写 SQL）
        col_names = [cp["name"] for cp in col_profiles if not cp["name"].startswith("_")]
        example_sql = self._generate_example_sql(table_name, col_profiles, expanded_views)

        if not quiet:
            # 构建 params 上下文（如 projectId=14255, direction=INPUT）
            params_str = ""
            call_params = info.get("call_params")
            if call_params:
                skip = {"pageSize", "pageNumber", "pageNum", "pageStart", "confirmed"}
                parts = [f"{k}={v}" for k, v in call_params.items() if k not in skip]
                if parts:
                    params_str = " | " + ", ".join(parts)

            # 紧凑列名：STRUCT/STRUCT[] 展开子字段名，让 agent 知道嵌套结构
            from bff_client import BFFClient
            cols_str = BFFClient._format_columns_with_structs(schema, sample_row or {})
            if not cols_str:
                cols_str = ", ".join(col_names)
            print(f'[{table_name}] {row_count} 条{params_str} | {cols_str}')
            if '.{' in cols_str:
                print(f'  💡 嵌套字段用 struct.field 访问，如: SELECT colName.subField FROM {table_name}')

            if expanded_views:
                for v in expanded_views:
                    print(f"  展开视图: {v['name']} → 新增列: {', '.join(v['cols'])}")

            # 停产告警：输出完整可执行命令
            trace_cmd = self._trace_upstream_cmd()
            for i, s in enumerate(stalled_dims):
                line = f"⚠️ 停产: {s['dimension']}={s['value']} 停在 {s['latest']}（正常应到 {s['max_latest']}）"
                if i == 0 and trace_cmd:
                    line += f' → {trace_cmd} "表名"'
                print(line)

        result = {
            "table_name": table_name,
            "row_count": row_count,
            "columns": col_names,
            "example_sql": example_sql,
        }
        if expanded_views:
            result["expanded_views"] = expanded_views  # [{"name": "...", "cols": [...]}]
        if stalled_dims:
            result["alerts"] = []
            trace_cmd = self._trace_upstream_cmd()
            for i, s in enumerate(stalled_dims):
                msg = f"{s['dimension']}={s['value']} 停在 {s['latest']}（正常应到 {s['max_latest']}）"
                if i == 0 and trace_cmd:
                    msg += f' → {trace_cmd} "表名"'
                result["alerts"].append(msg)
        return result

    def _trace_upstream_cmd(self):
        """生成 trace_upstream.py 的可执行命令前缀"""
        if self._skill_scripts_dir:
            # skill_scripts_dir 指向 core/，trace_upstream 在 modules/discovery/scripts/
            project_root = os.path.dirname(self._skill_scripts_dir)
            trace_path = os.path.join(project_root, "modules", "discovery", "scripts", "trace_upstream.py")
            if os.path.exists(trace_path):
                return f"PYTHONPATH={self._skill_scripts_dir} python {trace_path}"
        return ""

    def _profile_columns(self, table_name, columns, row_count):
        """分析每列的数据类型、基数、空值率，返回列画像列表"""
        # 过滤内部字段
        target_cols = [c for c in columns if not c.startswith("_")]
        if not target_cols:
            return []

        # 单次查询获取所有列的 distinct count 和 non_null count
        select_parts = []
        for col in target_cols:
            select_parts.append(f'COUNT(DISTINCT "{col}") as "d_{col}"')
            select_parts.append(f'COUNT("{col}") as "n_{col}"')
        try:
            stats = self._mem_fetch(f'SELECT {", ".join(select_parts)} FROM "{table_name}"')
        except Exception:
            return []

        if not stats:
            return []
        s = stats[0]

        # 从 information_schema 获取列类型（比 typeof() 更准确）
        col_types = {}
        try:
            type_rows = self._mem_fetch(
                f"SELECT column_name, data_type FROM information_schema.columns "
                f"WHERE table_name = '{table_name}' AND table_schema = 'main'"
            )
            col_types = {r["column_name"]: r["data_type"].upper() for r in type_rows}
        except Exception:
            pass

        profiles = []
        for col in target_cols:
            distinct = s.get(f"d_{col}", 0)
            non_null = s.get(f"n_{col}", 0)
            col_type = col_types.get(col, "VARCHAR")

            profile = {
                "name": col,
                "distinct": distinct,
                "non_null": non_null,
                "col_type": col_type,
                "category": self._classify_column(col, distinct, non_null, row_count, col_type),
            }
            profiles.append(profile)

        return profiles

    def _classify_column(self, col_name, distinct, non_null, row_count, col_type):
        """
        根据列特征分类：dimension / metric / time / detail

        分类规则：
        - 列名或类型像时间戳 → time
        - 数值类型 + 高基数 → metric（可聚合的度量）
        - 低基数（distinct 少）→ dimension（可 GROUP BY 的维度）
        - 其他 → detail（明细，展示样本）
        """
        name_lower = col_name.lower()

        # 时间列：列名含 time/date/timestamp，或类型是 TIMESTAMP
        if any(kw in name_lower for kw in ("time", "date", "timestamp", "created", "modified", "updated")):
            if "BIGINT" in col_type or "INTEGER" in col_type or "TIMESTAMP" in col_type:
                return "time"

        # 复合类型（数组、结构体等）→ 明细
        if any(t in col_type for t in ("[]", "STRUCT", "MAP", "LIST")):
            return "detail"

        # 数值列：类型是数字
        is_numeric = any(t in col_type for t in ("BIGINT", "INTEGER", "DOUBLE", "FLOAT", "DECIMAL", "NUMERIC"))

        if is_numeric:
            # 低基数数值（如 status=3 种）→ 维度
            if distinct <= 10:
                return "dimension"
            # 高基数数值（如 recordCount）→ 度量
            if distinct > MAX_DIMENSION_CARDINALITY:
                return "metric"
            # 中等基数数值 → 看比例
            ratio = distinct / max(row_count, 1)
            if ratio <= MIN_DIMENSION_ROWS_RATIO:
                return "dimension"
            return "metric"

        # 文本列
        if distinct <= MAX_DIMENSION_CARDINALITY:
            ratio = distinct / max(row_count, 1)
            # 低基数文本 → 维度（但不能太接近行数）
            if distinct <= 10 or ratio <= MIN_DIMENSION_ROWS_RATIO:
                return "dimension"

        # 布尔列
        if "BOOLEAN" in col_type:
            return "dimension"

        # 其他 → 明细
        return "detail"

    def _detect_stalled_dims(self, table_name, detail_cols, time_cols=None):
        """检测明细列中的 KV 展开停产维度，不输出任何内容

        Returns:
            tuple: (停产维度列表, 展开视图信息列表[{"name": view_name, "cols": [col1, ...]}])
        """
        import re

        all_stalled = []
        expanded_views = []

        for dc in detail_cols:
            col = dc["name"]
            try:
                samples = self._mem_fetch(f'SELECT DISTINCT "{col}" FROM "{table_name}" WHERE "{col}" IS NOT NULL LIMIT 3')
                vals = [str(s[col]) for s in samples if s[col] is not None]
            except Exception:
                continue

            # 检测 key=value/key=value 模式（如 ds=20250803/region=group）
            if vals and re.match(r'^[a-zA-Z_]+=.+', vals[0]):
                stalled, view_name, view_dims = self._expand_kv_column(table_name, col, time_cols)
                if view_name:
                    expanded_views.append({"name": view_name, "cols": view_dims})
                if isinstance(stalled, list):
                    all_stalled.extend(stalled)

        return all_stalled, expanded_views

    def _expand_kv_column(self, table_name, col, time_cols=None):
        """将 key=value/key=value 格式的列展开为子维度视图，检测停产

        Returns:
            tuple: (stalled_result, view_name)
                stalled_result: list(停产维度) / True(无停产) / False(未展开)
                view_name: 展开视图名（成功时）或 None（未展开时）
        """
        import re

        # 取样本解析维度名
        samples = self._mem_fetch(f'SELECT DISTINCT "{col}" FROM "{table_name}" WHERE "{col}" IS NOT NULL LIMIT 5')
        if not samples:
            return False, None, []

        sample_val = str(samples[0][col])
        parts = sample_val.split("/")
        dims = []
        for part in parts:
            if "=" in part:
                key = part.split("=", 1)[0].strip()
                if key:
                    dims.append(key)

        if not dims:
            return False, None, []

        # 用 SQL 提取子维度：在 Memory DB 创建临时视图
        view_name = f"_{table_name}_{col}_expanded"
        select_parts = [f'"{table_name}".*']
        for dim in dims:
            select_parts.append(
                f"regexp_extract(\"{col}\", '{re.escape(dim)}=([^/]*)', 1) AS \"{dim}\""
            )
        select_sql = ", ".join(select_parts)
        self.db.execute(f'DROP VIEW IF EXISTS "{view_name}"')
        self.db.execute(f'CREATE VIEW "{view_name}" AS SELECT {select_sql} FROM "{table_name}"')

        # 同时在 File DB 创建视图（供用户后续 SQL 查询）
        try:
            self.loader.db.execute(f'DROP VIEW IF EXISTS "{view_name}"')
            self.loader.db.execute(f'CREATE VIEW "{view_name}" AS SELECT {select_sql} FROM "{table_name}"')
        except Exception:
            pass

        # 区分时间子维度和值子维度
        time_dims = [d for d in dims if d in ("ds", "dt", "pt", "bizdate")]
        value_dims = [d for d in dims if d not in time_dims]

        # 收集停产维度
        stalled_dims = []

        for dim in value_dims:
            ref_time = time_dims[0] if time_dims else None
            if ref_time:
                rows = self._mem_fetch(f'''
                    SELECT "{dim}", COUNT(*) as cnt, MAX("{ref_time}") as latest
                    FROM "{view_name}"
                    WHERE "{dim}" IS NOT NULL AND "{dim}" != ''
                    GROUP BY "{dim}"
                    ORDER BY latest DESC
                ''')
                if rows:
                    valid_dates = [r["latest"] for r in rows if r.get("latest")]
                    if not valid_dates:
                        continue
                    max_latest = max(valid_dates)
                    for r in rows:
                        if r["latest"] != max_latest:
                            stalled_dims.append({
                                "dimension": dim,
                                "value": r[dim],
                                "latest": r["latest"],
                                "max_latest": max_latest,
                            })

        return (stalled_dims if stalled_dims else True), view_name, dims

    def _generate_example_sql(self, table_name, col_profiles, expanded_views):
        """根据数据特征生成最有用的一条示例 SQL"""
        # 优先用展开视图
        if expanded_views:
            v = expanded_views[0]
            time_dims = [c for c in v["cols"] if c in ("ds", "dt", "pt", "bizdate")]
            value_dims = [c for c in v["cols"] if c not in time_dims]
            if value_dims and time_dims:
                vd = value_dims[0]
                td = time_dims[0]
                return f'SELECT {vd}, MAX({td}) as latest FROM {v["name"]} GROUP BY {vd}'
            elif time_dims:
                td = time_dims[0]
                return f'SELECT {td}, COUNT(*) as cnt FROM {v["name"]} GROUP BY {td} ORDER BY {td} DESC LIMIT 10'

        # 用基表：找低基数列做 GROUP BY
        dims = [cp for cp in col_profiles if cp["category"] == "dimension"]
        if dims:
            dim = dims[0]["name"]
            return f'SELECT "{dim}", COUNT(*) as cnt FROM {table_name} GROUP BY "{dim}" ORDER BY cnt DESC'

        # 兜底：SELECT 前几列
        cols = [cp["name"] for cp in col_profiles[:3]]
        col_sql = ", ".join(f'"{c}"' for c in cols)
        return f"SELECT {col_sql} FROM {table_name} LIMIT 5"
