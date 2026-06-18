#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""我的数据资产 — 专辑 + 管理的表 + 生产的表

查看当前用户的数据资产全貌：推荐专辑、我管理的表、我名下生产的表。

用法:
    python my_data_assets.py                        # 查看我的数据资产概览
    python my_data_assets.py --album-id 382469      # 查看某个专辑内的表
    python my_data_assets.py --managed               # 只看我管理的表
    python my_data_assets.py --production            # 只看我生产的表
    python my_data_assets.py --official              # 查看官方专辑
    python my_data_assets.py --page-size 50          # 指定每页条数

涉及 API: listMyAlbums, listAlbumEntity, getTableAssetsManagedByMe, getTableAssetsUnderProduction
"""

import argparse

from bff_client import BFFClient


def main():
    parser = argparse.ArgumentParser(description="我的数据资产")
    parser.add_argument("--album-id", type=int, help="查看指定专辑内的表")
    parser.add_argument("--scene", choices=["owner", "manage", "official", "attention", "all"],
                        help="专辑场景: owner=我创建, manage=我管理, official=官方, attention=我关注, all=全部")
    parser.add_argument("--managed", action="store_true", help="只看我管理的表")
    parser.add_argument("--production", action="store_true", help="只看我生产的表")
    parser.add_argument("--page-size", type=int, default=20, help="每页条数（默认 20）")
    parser.add_argument("--page", type=int, default=1, help="页码（默认 1）")
    args = parser.parse_args()

    client = BFFClient()

    # 查看专辑内的表
    if args.album_id:
        entities = client.load("listAlbumEntity",
                               albumId=str(args.album_id),
                               pageSize=str(args.page_size),
                               pageNum=str(args.page))
        print(f"\n━━ 专辑 {args.album_id} 的表 ━━")
        if isinstance(entities, list):
            print(f"  共 {len(entities)} 条（第 {args.page} 页）\n")
            for i, e in enumerate(entities):
                entity = e.get("entity", {}) if isinstance(e, dict) else {}
                name = entity.get("name", entity.get("tableName", "?"))
                owner = entity.get("ownerName", entity.get("owner", "?"))
                db = entity.get("databaseName", "?")
                print(f"  {i+1}. {name}  项目={db}  负责人={owner}")
            if len(entities) >= args.page_size:
                print(f"\n  💡 下一页: python my_data_assets.py --album-id {args.album_id} --page {args.page + 1}")
        else:
            print(f"  {entities}")
        return

    # 按场景查专辑
    if args.scene:
        scene_label = {"owner": "我创建的", "manage": "我管理的", "official": "官方",
                       "attention": "我关注的", "all": "全部"}
        albums = client.load("listMyAlbums",
                             pageSize=str(args.page_size), pageNum=str(args.page),
                             scene=args.scene)
        print(f"\n━━ {scene_label.get(args.scene, args.scene)}专辑 ━━")
        if isinstance(albums, list):
            print(f"  共 {len(albums)} 个（第 {args.page} 页）\n")
            for a in albums:
                name = a.get("albumName", "?")
                aid = a.get("id", "?")
                count = a.get("tableCount", "?")
                owner = a.get("ownerNickName", "?")
                print(f"  [{aid}] {name}  ({count} 张表)  创建人={owner}")
            if len(albums) >= args.page_size:
                print(f"\n  💡 下一页: python my_data_assets.py --scene {args.scene} --page {args.page + 1}")
        else:
            print(f"  {albums}")
        return

    # 只看管理的表
    if args.managed:
        managed = client.load("getTableAssetsManagedByMe",
                              datasourceType="odps", type="imanage",
                              pageNum=str(args.page), pageSize=str(args.page_size))
        print(f"\n━━ 我管理的表 ━━")
        _print_tables(managed, args)
        return

    # 只看生产的表
    if args.production:
        production = client.load("getTableAssetsUnderProduction",
                                 datasourceType="odps", type="productacct",
                                 pageNum=str(args.page), pageSize=str(args.page_size))
        print(f"\n━━ 我生产的表 ━━")
        _print_tables(production, args)
        return

    # 默认：全貌概览
    print(f"\n━━ 我的数据资产 ━━")

    # 1. 我创建的专辑
    my_albums = client.load("listMyAlbums", pageSize="20", pageNum="1", scene="owner")
    if isinstance(my_albums, list) and my_albums:
        print(f"\n【我创建的专辑】（{len(my_albums)} 个）")
        for a in my_albums:
            name = a.get("albumName", "?")
            aid = a.get("id", "?")
            count = a.get("tableCount", "?")
            print(f"  [{aid}] {name}  ({count} 张表)")
    else:
        print(f"\n【我创建的专辑】无")

    # 2. 我管理的专辑
    managed_albums = client.load("listMyAlbums", pageSize="20", pageNum="1", scene="manage")
    if isinstance(managed_albums, list) and managed_albums:
        # 去掉和"我创建的"重复的
        my_ids = {a.get("id") for a in my_albums} if isinstance(my_albums, list) else set()
        extra = [a for a in managed_albums if a.get("id") not in my_ids]
        if extra:
            print(f"\n【我管理的专辑】（另有 {len(extra)} 个）")
            for a in extra:
                name = a.get("albumName", "?")
                aid = a.get("id", "?")
                count = a.get("tableCount", "?")
                owner = a.get("ownerNickName", "?")
                print(f"  [{aid}] {name}  ({count} 张表)  创建人={owner}")

    # 3. 我管理的表（摘要）
    managed = client.load("getTableAssetsManagedByMe",
                          datasourceType="odps", type="imanage",
                          pageNum="1", pageSize="5")
    managed_list = managed if isinstance(managed, list) else []
    print(f"\n【我管理的表】（前 5 条）")
    if managed_list:
        for t in managed_list[:5]:
            name = t.get("tableName", "?")
            project = t.get("appGuid", "?").replace("odps.", "")
            print(f"  {name}  项目={project}")
        print(f"  💡 查看全部: python my_data_assets.py --managed")
    else:
        print("  无")

    # 4. 我生产的表（摘要）
    production = client.load("getTableAssetsUnderProduction",
                             datasourceType="odps", type="productacct",
                             pageNum="1", pageSize="5")
    prod_list = production if isinstance(production, list) else []
    print(f"\n【我生产的表】（前 5 条）")
    if prod_list:
        for t in prod_list[:5]:
            name = t.get("tableName", "?")
            project = t.get("appGuid", "?").replace("odps.", "")
            print(f"  {name}  项目={project}")
        print(f"  💡 查看全部: python my_data_assets.py --production")
    else:
        print("  无")

    # chain hints
    if isinstance(my_albums, list) and my_albums:
        aid = my_albums[0].get("id", "?")
        print(f"\n  💡 查看专辑内的表: python my_data_assets.py --album-id {aid}")


def _print_tables(tables, args):
    """打印表列表"""
    table_list = tables if isinstance(tables, list) else []
    if not table_list:
        print("  无数据")
        return
    print(f"  共 {len(table_list)} 条（第 {args.page} 页）\n")
    for i, t in enumerate(table_list):
        name = t.get("tableName", "?")
        project = t.get("appGuid", "?").replace("odps.", "")
        size = t.get("dataSize", "")
        views = t.get("viewCountMonthly", "")
        comment = t.get("tableComment", "")
        extra = []
        if size:
            extra.append(f"大小={size}")
        if views:
            extra.append(f"月访问={views}")
        if comment:
            extra.append(comment[:30])
        extra_str = f"  {'  '.join(extra)}" if extra else ""
        print(f"  {i+1}. {name}  项目={project}{extra_str}")
    if len(table_list) >= args.page_size:
        flag = "--managed" if hasattr(args, 'managed') and args.managed else "--production"
        print(f"\n  💡 下一页: python my_data_assets.py {flag} --page {args.page + 1}")


if __name__ == "__main__":
    main()
