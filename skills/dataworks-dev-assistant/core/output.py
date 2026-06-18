#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
输出格式化 + DuckDB 灌入 + 会话状态 Mixin

BFFClient 通过多继承混入此类，获得自动数据分析和会话持久化能力。
"""

import json
import os
import sys
from datetime import datetime

from runtime import _TOOL_SCRIPTS, _SESSION_STATE_FILE, get_runtime_dir


class OutputMixin:
    """输出格式化、DuckDB 自动灌入、会话状态管理"""

    def _print_follow_up(self, follow_up, write_params, write_result=None):
        """输出异步操作的 follow-up 查询命令到 stdout"""
        api = follow_up["api"]
        param_mapping = follow_up.get("param_mapping", {})
        mode = follow_up.get("mode", "async")
        terminal = follow_up.get("terminal", {})
        pending_status = follow_up.get("pending", {})

        # 从 write_params 解析 follow-up 参数值
        # 支持 "$result" / "$result.field" / "[0]" / "=literal" 引用
        follow_params = {}
        for target_key, source_expr in param_mapping.items():
            if source_expr == "$result":
                if write_result is not None:
                    follow_params[target_key] = write_result
            elif isinstance(source_expr, str) and source_expr.startswith("$result."):
                if isinstance(write_result, dict):
                    value = write_result
                    for key in source_expr[len("$result."):].split("."):
                        if isinstance(value, dict):
                            value = value.get(key)
                        else:
                            value = None
                            break
                    if value is not None:
                        follow_params[target_key] = value
            elif isinstance(source_expr, str) and source_expr.startswith("="):
                literal = source_expr[1:]
                if literal == "null":
                    follow_params[target_key] = None
                elif literal == "true":
                    follow_params[target_key] = True
                elif literal == "false":
                    follow_params[target_key] = False
                else:
                    try:
                        follow_params[target_key] = int(literal)
                    except ValueError:
                        follow_params[target_key] = literal
            elif "[0]" in source_expr:
                field = source_expr.replace("[0]", "")
                val = write_params.get(field)
                if isinstance(val, list) and val:
                    val = val[0]
                if val is not None:
                    follow_params[target_key] = val
            else:
                val = write_params.get(source_expr)
                if val is not None:
                    follow_params[target_key] = val

        # 构建 load() 命令（指令语气，引导 agent 直接执行而非询问用户）
        params_str = ", ".join(f"{k}={v!r}" for k, v in follow_params.items())
        if mode == "verify":
            print(f"🔎 执行下一步验证结果: client.load('{api}', {params_str})")
        else:
            print(f"⏳ 异步操作已提交，执行下一步确认结果: client.load('{api}', {params_str})")

        # 状态码含义
        t_str = ", ".join(f"{k}={v}" for k, v in terminal.items())
        p_str = ", ".join(f"{k}={v}" for k, v in pending_status.items())
        parts = []
        if t_str:
            parts.append(f"终态: {t_str}")
        if p_str:
            parts.append(f"中间态: {p_str}")
        if parts:
            print(f"  {' | '.join(parts)}")

    @staticmethod
    def _format_columns_with_structs(schema, parsed):
        """格式化列名，STRUCT/STRUCT[] 列展开显示子字段名

        普通列直接输出名称：
        - STRUCT 列输出 "colName.{subField1, subField2, ...}"
        - STRUCT[] 列输出 "colName[].{subField1, subField2, ...}"
        让 agent 看到可用字段名，写代码时不用猜。

        Args:
            schema: [{name, type, ...}] 列信息
            parsed: API 返回的原始数据（用于提取 struct 子字段）

        Returns:
            str: 格式化后的列名字符串
        """
        # 从 parsed 数据中获取实际值（用于提取 struct keys）
        row = parsed
        if isinstance(row, list):
            row = row[0] if row else {}
        if not isinstance(row, dict):
            row = {}

        parts = []
        for s in schema:
            name = s["name"]
            if name.startswith("_"):
                continue
            col_type = s.get("type", "")
            val = row.get(name)
            # STRUCT 列：从实际数据提取子字段名
            if "STRUCT" in col_type and val is not None:
                if isinstance(val, dict):
                    sub_keys = list(val.keys())
                    if sub_keys:
                        parts.append(f"{name}.{{{', '.join(sub_keys)}}}")
                        continue
                elif isinstance(val, list) and val and isinstance(val[0], dict):
                    sub_keys = list(val[0].keys())
                    if sub_keys:
                        parts.append(f"{name}[].{{{', '.join(sub_keys)}}}")
                        continue
            parts.append(name)
        return ", ".join(parts)

    def _translate_status(self, api_name, parsed):
        """查找引用此 API 的 follow_up 配置，翻译状态码

        Returns:
            str: 状态翻译行（如 "→ status=6（成功）— 终态"），无匹配时返回 None
        """
        # 遍历所有 API 的 follow_up，找到 target == api_name 的配置
        follow_up = None
        for meta in self.api_index.values():
            if not isinstance(meta, dict):
                continue
            fu = meta.get("follow_up")
            if fu and fu.get("api") == api_name:
                follow_up = fu
                break

        if not follow_up:
            return None

        status_field = follow_up.get("status_field", "")
        terminal = follow_up.get("terminal", {})
        pending = follow_up.get("pending", {})
        all_status = {**terminal, **pending}

        if not status_field or not all_status:
            return None

        # 从 parsed 数据中提取状态值（支持 "taskCurrentRun.status" 点路径）
        value = parsed
        if isinstance(value, list):
            value = value[0] if value else None
        for key in status_field.split("."):
            if isinstance(value, dict):
                value = value.get(key)
            else:
                value = None
                break

        if value is None:
            return None

        value_str = str(value)
        label = all_status.get(value_str)
        if not label:
            return None

        is_terminal = value_str in terminal
        suffix = "终态，无需继续查询" if is_terminal else "等待后重新查询"
        return f"→ {status_field}={value_str}（{label}）— {suffix}"

    def _auto_load_to_analyzer(self, api_name, parsed, call_params=None):
        """将 API 返回数据灌入 DuckDB + 自动分析，将分析结果存入 _tables 供状态文件使用"""
        if not self.loader or parsed is None:
            return

        with self._loader_lock:
            self._auto_load_to_analyzer_locked(api_name, parsed, call_params)

    def _auto_load_to_analyzer_locked(self, api_name, parsed, call_params=None):
        """_auto_load_to_analyzer 的加锁实现"""
        # 空结果明确告知 agent（避免 agent 猜测"未找到"并误判为错误）
        if isinstance(parsed, list) and len(parsed) == 0:
            if not self._quiet:
                params_str = ""
                if call_params:
                    params_str = " | " + ", ".join(f"{k}={v}" for k, v in call_params.items()
                                                   if k not in ("pageSize", "pageNumber", "pageNum", "pageStart", "confirmed"))
                print(f"[{api_name}] 0 条{params_str}（查询正常，无匹配数据）")
            return

        try:
            table_name = self.loader.load(
                api_name, parsed,
                call_params=call_params,
            )
            self.last_table = table_name  # 暴露给脚本使用
            # 列表数据（>=2 行）自动统计
            if table_name and self._analyzer and isinstance(parsed, list) and len(parsed) >= 2:
                summary = self._analyzer.auto_summary(table_name, quiet=self._quiet, sample_row=parsed[0] if parsed else None)
                if summary:
                    # 将分析结果存入 _tables，供 _save_session_state 使用
                    self.loader._tables[table_name].update({
                        "example_sql": summary.get("example_sql"),
                        "expanded_views": summary.get("expanded_views"),
                        "alerts": summary.get("alerts"),
                    })
            elif table_name and not self._quiet:
                # dict 或少量数据：auto_summary 不触发，但仍需告知 agent 表名和列名
                info = self.loader.get_table_info(table_name)
                if info:
                    row_count = info.get("row_count", 0)
                    cols_str = self._format_columns_with_structs(info.get("schema", []), parsed)
                    # 标量字符串（如代码内容）：直接输出完整内容，避免 DuckDB 显示截断
                    if isinstance(parsed, str):
                        print(f'[{table_name}] {api_name} 返回文本（{len(parsed)} 字符）:')
                        print(parsed)
                    else:
                        print(f'[{table_name}] {row_count} 条 | {cols_str}')
                        if '.{' in cols_str:
                            # STRUCT 列存在时提示 DuckDB 访问语法
                            print(f'  💡 嵌套字段用 struct.field 访问，如: SELECT taskCurrentRun.status FROM {table_name}')
                    # 状态码翻译：查找引用此 API 的 follow_up 配置
                    status_line = self._translate_status(api_name, parsed)
                    if status_line:
                        print(status_line)
            # 搜索类 API 返回多条结果时，提示用户选择（元数据驱动）
            if not self._quiet and isinstance(parsed, list) and len(parsed) > 1:
                api_meta_tmp = self.api_index.get(api_name, {})
                if api_meta_tmp.get("multi_result_confirm"):
                    pk = api_meta_tmp.get("primary_key", "id")
                    print(f"⚠️ 返回 {len(parsed)} 条结果，请让用户确认要操作哪一个（用 {pk} 区分）")

            # 链式引导（元数据驱动，支持单个 chain_hint 或数组 chain_hints）
            api_meta = self.api_index.get(api_name, {})
            hints = api_meta.get("chain_hints") or []
            single = api_meta.get("chain_hint")
            if single:
                hints = [single] + hints  # 兼容旧格式
            if hints and not self._quiet and parsed:
                for hint in hints:
                    hint_api = hint["api"]
                    label = hint.get("label", hint_api)
                    params = ", ".join(f'{k}=<该结果的 {v}>' for k, v in hint.get("param_map", {}).items())
                    print(f'→ {label}: client.load("{hint_api}", {params})')
            # 同一 API 多次调用时，stdout 提示合并
            if table_name and not self._quiet:
                same_api_tables = self.loader.get_tables_for_api(api_name)
                if len(same_api_tables) >= 2:
                    view_name = f"all_{api_name}"
                    tables_str = ", ".join(same_api_tables[:3])
                    if len(same_api_tables) > 3:
                        tables_str += f" 等 {len(same_api_tables)} 张"
                    print(f'💡 {api_name} 已调用 {len(same_api_tables)} 次（{tables_str}）')
                    print(f'   合并查询: python duckdb_query.py --merge "{api_name}_r*" --as {view_name}')

        except Exception as e:
            print(f"[BFFClient] 自动加载到 DuckDB 失败（{api_name}）: {e}", file=sys.stderr)

    def _ensure_user_context(self):
        """懒加载当前用户信息（仅调一次 currentUser API）"""
        if "user" in self._context:
            return
        try:
            api_meta = self.api_index.get("currentUser")
            if not api_meta:
                return
            result = self._do_request("currentUser", api_meta)
            if self.is_success(result):
                data = result.get("data", {})
                self._context["user"] = {
                    "baseId": data.get("baseId", ""),
                    "displayName": data.get("displayName", ""),
                }
        except Exception:
            pass

    def _save_session_state(self):
        """将当前会话状态写入文件（供 agent 跨轮次读取）

        合并语义：先读旧 state（保留所有未知顶层字段如 confirmed_params），
        再覆盖本类负责的已知字段（context / round / tables / available_tools / last_updated）。
        其他模块写入的顶层字段不会被本方法误清。
        """
        if not self.loader or not hasattr(self.loader, '_tables') or not self.loader._tables:
            return

        # 懒加载用户信息
        self._ensure_user_context()

        state_path = os.path.join(get_runtime_dir(self._work_dir), _SESSION_STATE_FILE)

        # 先读旧 state，未知顶层字段（如 confirmed_params）原样保留
        state = {}
        if os.path.exists(state_path):
            try:
                with open(state_path, "r", encoding="utf-8") as f:
                    state = json.load(f)
                if not isinstance(state, dict):
                    state = {}
            except Exception as e:
                print(f"⚠️ session_state 读取失败: {e}", file=sys.stderr)
                state = {}

        # 合并历史 context（当前值优先）
        old_ctx = state.get("context", {}) if isinstance(state.get("context"), dict) else {}
        old_ctx.update(self._context)
        self._context = old_ctx

        # 覆盖本类负责的已知字段
        state["context"] = self._context
        state["round"] = self.loader._round
        state["available_tools"] = []
        state["last_updated"] = datetime.now().isoformat()
        if "tables" not in state or not isinstance(state["tables"], dict):
            state["tables"] = {}

        # 合并当前表信息（含 api_name、params、schema、example_sql 等）
        for name, info in self.loader._tables.items():
            state["tables"][name] = {
                "api_name": info.get("api_name", name),
                "params": info.get("call_params"),
                "row_count": info["row_count"],
                "schema": info.get("schema", []),
                "called_at": info.get("called_at"),
                "example_sql": info.get("example_sql"),
                "expanded_views": info.get("expanded_views"),
                "alerts": info.get("alerts"),
            }

        # 移除已被 drop 的表（不在 loader._tables 中的旧条目清除）
        current_tables = set(self.loader._tables.keys())
        state["tables"] = {k: v for k, v in state["tables"].items() if k in current_tables}

        # 扫描可用工具脚本
        for script, desc in _TOOL_SCRIPTS.items():
            if os.path.exists(os.path.join(self._work_dir, script)):
                state["available_tools"].append(f"{script} — {desc}")

        try:
            with open(state_path, "w", encoding="utf-8") as f:
                json.dump(state, f, ensure_ascii=False, indent=2, default=str)
        except Exception as e:
            print(f"⚠️ session_state 写入失败: {e}", file=sys.stderr)
