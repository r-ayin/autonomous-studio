#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
分页与限频处理 Mixin

BFFClient 通过多继承混入此类，获得自动翻页和弹性并发能力。
"""

import sys


class PaginationMixin:
    """自动翻页 + 弹性并发 + 限频退避"""

    def _call_paged(self, api_name, **kwargs):
        """内部方法：调用列表 API 单页，返回 {"items": [...], "total_count": N}"""
        api_meta = self.api_index.get(api_name)
        if not api_meta:
            raise ValueError(f"未找到 API: {api_name}。可用 API: {list(self.api_index.keys())}")

        result = self._do_request(api_name, api_meta, **kwargs)

        if not self.is_success(result):
            raise RuntimeError(
                f"API 调用失败: {api_name} → code={result.get('code')}, "
                f"message={result.get('message')}, requestId={result.get('requestId')}"
            )

        data = result.get("data", {})
        # 不同 API 总数字段名不同：totalCount / totalNum / count / total（searchSchedulerNodes 用 count；listApply 用 total）
        total_count = (data.get("totalCount") or data.get("totalNum") or data.get("count") or data.get("total") or 0) if isinstance(data, dict) else 0

        return_structure = api_meta.get("return_structure")
        items = self._parse_return_structure(result, return_structure)
        if items is None:
            items = []

        return {"items": items, "total_count": total_count}

    def _call_all_pages(self, api_name, page_size=100, load_to_db=True, max_pages=3000, max_offset=None, **kwargs):
        """内部方法：自动翻页获取所有数据

        优化策略：第一页串行拿 totalCount，剩余页弹性并发拉取。
        遇到限频自动降低并发度（30→10→3→1），指数退避重试。

        Args:
            page_size: 默认 100（兼容旧行为）；callers 可传 pageSize=500/1000 加速大结果集
            max_pages: 默认 3000（配合 page_size=100 = 30w 行上限）。callers 可按需下调以节流。
            max_offset: 服务端 offset 上限（如 searchTables 的 5000）。非 None 时自动限制翻页数，
                        避免 (pageNum-1)*pageSize 超限触发服务端报错。
        """
        from concurrent.futures import ThreadPoolExecutor, as_completed
        import math
        import time as _time

        # 分页参数名：从元数据读取，默认 pageNumber
        api_meta = self.api_index.get(api_name, {})
        page_num_key = api_meta.get("page_num_key", "pageNumber")
        use_offset = (page_num_key == "pageStart")

        def _build_page_kwargs(page_num):
            pk = dict(kwargs)
            requested_page_size = kwargs.get("pageSize", page_size)
            pk["pageSize"] = str(requested_page_size)
            if use_offset:
                pk[page_num_key] = str((page_num - 1) * int(requested_page_size))
            else:
                pk[page_num_key] = str(page_num)
            return pk

        # ── 第一页：串行，拿 totalCount ──
        first_result = self._call_paged_with_retry(api_name, **_build_page_kwargs(1))
        all_items = list(first_result["items"])
        total_count = first_result["total_count"]
        effective_page_size = int(kwargs.get("pageSize", page_size))

        # 场景 A：API 返回 totalCount，用 totalCount 决定翻页数
        if total_count > 0:
            if len(all_items) >= total_count:
                if load_to_db:
                    self._auto_load_to_analyzer(api_name, all_items, call_params=kwargs)
                return all_items
            actual_pages = math.ceil(total_count / effective_page_size)
            # 服务端 offset 上限约束（如 searchTables (pageNum-1)*pageSize <= 5000）
            if max_offset is not None:
                max_pages_by_offset = max(1, max_offset // effective_page_size)
                total_pages = min(actual_pages, max_pages, max_pages_by_offset)
            else:
                total_pages = min(actual_pages, max_pages)
            if actual_pages > total_pages:
                truncated_count = total_pages * effective_page_size
                self._log_warn(
                    f"{api_name} 数据量 {total_count} 条超过翻页上限"
                    f"（{total_pages} 页 × {effective_page_size} = {truncated_count} 条），"
                    f"截断为前 {truncated_count} 条"
                )
                print(f"⚠️ {api_name} 共 {total_count} 条，已截断为前 {truncated_count} 条（翻页上限 {total_pages} 页）")
            pending_pages = list(range(2, total_pages + 1))
        else:
            # 场景 B：API 不返回 totalCount（如 searchSchedulerNodes）
            # 策略：首页 < pageSize 即完；否则**按批并发探测**直至某批有页返回 < pageSize。
            if len(all_items) < effective_page_size:
                if load_to_db:
                    self._auto_load_to_analyzer(api_name, all_items, call_params=kwargs)
                return all_items

            BATCH = 20  # 每批并发 20 页
            effective_max = max_pages
            if max_offset is not None:
                effective_max = min(max_pages, max(1, max_offset // effective_page_size))
            page_cursor = 2
            hit_end = False
            hit_cap = False
            while page_cursor <= effective_max:
                batch_end = min(page_cursor + BATCH, effective_max + 1)
                batch_pages = list(range(page_cursor, batch_end))
                page_results = {}
                rate_limited = []
                with ThreadPoolExecutor(max_workers=min(BATCH, len(batch_pages))) as pool:
                    future_map = {
                        pool.submit(self._call_paged_safe, api_name, **_build_page_kwargs(p)): p
                        for p in batch_pages
                    }
                    for f in as_completed(future_map):
                        pnum = future_map[f]
                        res = f.result()
                        if res is None:
                            rate_limited.append(pnum)
                        else:
                            page_results[pnum] = res["items"]

                # 限频页：重试一次（简单退避）
                if rate_limited:
                    _time.sleep(2)
                    for p in rate_limited:
                        res = self._call_paged_safe(api_name, **_build_page_kwargs(p))
                        if res is not None:
                            page_results[p] = res["items"]

                # 按页号顺序合并本批结果，检查是否碰到短页（= 接近尾部）
                for p in batch_pages:
                    items = page_results.get(p, [])
                    if items:
                        all_items.extend(items)
                    if len(items) < effective_page_size:
                        hit_end = True
                if hit_end:
                    break
                page_cursor = batch_end
                if page_cursor > effective_max:
                    hit_cap = True

            if hit_cap:
                truncated_count = effective_max * effective_page_size
                self._log_warn(f"{api_name} 无 totalCount，达翻页上限 {effective_max} 页（{truncated_count} 条），实际可能更多")
                print(f"⚠️ {api_name} 无 totalCount，达翻页上限 {effective_max} 页（{truncated_count} 条），实际可能更多")
            if load_to_db:
                self._auto_load_to_analyzer(api_name, all_items, call_params=kwargs)
            return all_items

        # 弹性并发度：从 30 开始，限频时逐级降到 10→3→1
        concurrency_levels = [30, 10, 3, 1]
        concurrency_idx = 0
        page_results = {}

        while pending_pages:
            max_workers = min(len(pending_pages), concurrency_levels[concurrency_idx])
            batch = pending_pages[:]  # 当前批次要拉的页

            rate_limited_pages = []
            with ThreadPoolExecutor(max_workers=max_workers) as pool:
                future_map = {
                    pool.submit(self._call_paged_safe, api_name, **_build_page_kwargs(p)): p
                    for p in batch
                }
                for f in as_completed(future_map):
                    page_num = future_map[f]
                    result = f.result()
                    if result is None:
                        # 限频，记录下来等重试
                        rate_limited_pages.append(page_num)
                    else:
                        page_results[page_num] = result["items"]

            # 从 pending 移除成功的
            pending_pages = rate_limited_pages

            if pending_pages:
                # 降低并发度
                if concurrency_idx < len(concurrency_levels) - 1:
                    concurrency_idx += 1
                # 退避等待：并发越低等越久
                wait = [1, 2, 5, 10][concurrency_idx]
                print(f"[BFFClient] 限频，降并发为 {concurrency_levels[concurrency_idx]}，等待 {wait}s（剩余 {len(pending_pages)} 页）",
                      file=sys.stderr)
                _time.sleep(wait)

        # 按页码顺序收集
        for p in range(2, total_pages + 1):
            items = page_results.get(p, [])
            if items:
                all_items.extend(items)

        # 自动灌入 DuckDB + 统计
        if load_to_db:
            self._auto_load_to_analyzer(api_name, all_items, call_params=kwargs)

        return all_items

    @staticmethod
    def _is_rate_limit_error(err_msg):
        """判断错误信息是否为限频/限流错误"""
        msg = err_msg.lower()
        return (
                "frequent" in msg
                or "throttl" in msg
                or "exceeded limit" in msg
                or "9990020002" in msg
                or "9990040001" in msg
        )

    def _call_paged_safe(self, api_name, **kwargs):
        """调用单页，限频时返回 None 而不是抛异常"""
        try:
            return self._call_paged(api_name, **kwargs)
        except RuntimeError as e:
            if self._is_rate_limit_error(str(e)):
                return None  # 限频信号
            raise  # 其他错误继续抛出

    def _call_paged_with_retry(self, api_name, max_retries=3, **kwargs):
        """调用单页，限频时指数退避重试"""
        import time as _time
        for attempt in range(max_retries + 1):
            try:
                return self._call_paged(api_name, **kwargs)
            except RuntimeError as e:
                if self._is_rate_limit_error(str(e)) and attempt < max_retries:
                    wait = 2 ** attempt  # 1, 2, 4 秒
                    print(f"[BFFClient] 限频，{wait}s 后重试（{attempt + 1}/{max_retries}）", file=sys.stderr)
                    _time.sleep(wait)
                    continue
                raise
