#!/usr/bin/env python3
"""DuckDB SQL 查询工具 — 直接在命令行执行 SQL

用法:
    python duckdb_query.py "SELECT name, type FROM ListDataSources_r1_c1"
    python duckdb_query.py "DESCRIBE ListDataSources_r1_c1"   # 查看表结构
    python duckdb_query.py --tables                            # 列出所有可用表和视图
    python duckdb_query.py --merge "ListProjectMembers_r*" --as all_members
"""
import os
import sys
import fnmatch
import duckdb

DB_FILE = os.path.join(".dataworks", "session.duckdb")


def do_merge(db, pattern, view_name):
    """将匹配 glob 模式的所有表 UNION ALL BY NAME 合并为一个视图。"""
    tables = db.sql(
        "SELECT table_name FROM duckdb_tables() WHERE table_name NOT LIKE '_dw_%' ORDER BY table_name"
    ).fetchall()
    matched = [t[0] for t in tables if fnmatch.fnmatch(t[0], pattern)]

    if not matched:
        print(f"❌ 没有匹配 '{pattern}' 的表", file=sys.stderr)
        sys.exit(1)

    # 用 read_only 打开的连接不能建视图，重新以读写模式打开
    db.close()
    db = duckdb.connect(DB_FILE)

    union_sql = " UNION ALL BY NAME ".join(
        f'SELECT * FROM "{t}"' for t in matched
    )
    db.sql(f'CREATE OR REPLACE VIEW "{view_name}" AS {union_sql}')
    print(f"✅ 合并 {len(matched)} 张表 → 视图 {view_name}")
    print(f"   匹配: {', '.join(matched)}")

    row_count = db.sql(f'SELECT COUNT(*) FROM "{view_name}"').fetchone()[0]
    cols = db.sql(
        f"SELECT column_name FROM information_schema.columns WHERE table_name = '{view_name}' ORDER BY ordinal_position"
    ).fetchall()
    col_names = [c[0] for c in cols]
    print(f"   行数: {row_count}, 列: {', '.join(col_names)}")
    print(f"\n后续查询示例:")
    print(f'  python duckdb_query.py "SELECT * FROM {view_name} LIMIT 10"')


def main():
    db = duckdb.connect(DB_FILE, read_only=True)

    if "--merge" in sys.argv:
        idx = sys.argv.index("--merge")
        if idx + 1 >= len(sys.argv):
            print("用法: python duckdb_query.py --merge \"pattern\" --as view_name", file=sys.stderr)
            sys.exit(1)
        pattern = sys.argv[idx + 1]
        view_name = pattern.replace("*", "all").replace("_r_", "_")
        if "--as" in sys.argv:
            as_idx = sys.argv.index("--as")
            if as_idx + 1 < len(sys.argv):
                view_name = sys.argv[as_idx + 1]
        do_merge(db, pattern, view_name)
        return

    if "--tables" in sys.argv:
        # 列出所有用户表和视图（含展开视图），附带列名摘要
        db.sql("""
            WITH all_objects AS (
                SELECT table_name, 'TABLE' AS type, estimated_size AS rows
                FROM duckdb_tables()
                WHERE table_name NOT LIKE '_dw_%'
                UNION ALL
                SELECT view_name AS table_name, 'VIEW' AS type, NULL AS rows
                FROM duckdb_views()
                WHERE view_name NOT LIKE '_dw_%'
                  AND schema_name = 'main' AND internal = false
            ),
            cols AS (
                SELECT table_name,
                       string_agg(column_name, ', ' ORDER BY ordinal_position) AS columns
                FROM information_schema.columns
                WHERE table_schema = 'main'
                GROUP BY table_name
            )
            SELECT a.table_name, a.type, a.rows, c.columns
            FROM all_objects a
            LEFT JOIN cols c ON a.table_name = c.table_name
            ORDER BY a.table_name
        """).show(max_width=200)
        return

    if len(sys.argv) < 2:
        print("用法: python duckdb_query.py \"SQL语句\"", file=sys.stderr)
        print("      python duckdb_query.py --tables", file=sys.stderr)
        sys.exit(1)

    full_mode = "--full" in sys.argv
    args = [a for a in sys.argv[1:] if a != "--full"]
    query = args[0]

    result = db.sql(query)
    cols = [desc[0] for desc in result.description]

    if full_mode:
        # --full: 逐行逐字段输出，不截断
        rows = result.fetchall()
        if not rows:
            print("(0 rows)")
        elif len(cols) == 1:
            # 单列：直接输出值
            for row in rows:
                print(row[0])
        else:
            for i, row in enumerate(rows):
                if len(rows) > 1:
                    print(f"── 第 {i + 1}/{len(rows)} 行 ──")
                for col, val in zip(cols, row):
                    print(f"{col}: {val}")
                if i < len(rows) - 1:
                    print()
    else:
        # 默认表格输出
        result.show(max_width=200)
        # 截断检测：重新 fetch 检查是否有长文本被截断
        rows = result.fetchall()
        if rows:
            display_width = max(30, 200 // max(len(cols), 1))
            truncated_cols = []
            for ci, col in enumerate(cols):
                for row in rows:
                    val = row[ci]
                    if isinstance(val, str) and len(val) > display_width:
                        truncated_cols.append(col)
                        break
            if truncated_cols:
                cols_str = ", ".join(truncated_cols)
                print(f"💡 列 {cols_str} 有长文本被截断，查看完整内容: python duckdb_query.py \"SELECT {cols_str} FROM ...\" --full")

if __name__ == "__main__":
    main()
