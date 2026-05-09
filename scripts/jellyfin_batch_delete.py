#!/usr/bin/env python3
"""
Jellyfin 批量删除影片脚本 (用户名密码认证)

环境变量:
    JELLYFIN_URL       Jellyfin 服务器地址
    JELLYFIN_USERNAME  用户名
    JELLYFIN_PASSWORD  密码

用法:
    export JELLYFIN_URL=http://fn.jian.uno:8097
    export JELLYFIN_USERNAME=jian
    export JELLYFIN_PASSWORD=yourpass

    python3 jellyfin_batch_delete.py --min-rating 7.0 --dry-run
    python3 jellyfin_batch_delete.py --before-year 2000 --dry-run
    python3 jellyfin_batch_delete.py --before-year 2005 --min-rating 7.0 --debug
"""

import argparse
import os
import sys
import requests


DEBUG = False
EMBY_AUTH_HEADER = 'MediaBrowser Client="JellyBatchDelete", Device="CLI", DeviceId="batch-delete-script", Version="1.0"'


def debug(msg):
    if DEBUG:
        print(f"[DEBUG] {msg}")


def authenticate(base_url, username, password):
    """登录获取 AccessToken"""
    url = f"{base_url}/Users/AuthenticateByName"
    headers = {
        "Content-Type": "application/json",
        "X-Emby-Authorization": EMBY_AUTH_HEADER,
    }
    data = {"Username": username, "Pw": password}
    debug(f"POST {url}")
    debug(f"  body: Username={username}")
    resp = requests.post(url, json=data, headers=headers)
    debug(f"  response: {resp.status_code}")
    if resp.status_code != 200:
        print(f"[ERROR] 登录失败: {resp.status_code} {resp.text[:200]}")
        sys.exit(1)
    result = resp.json()
    token = result.get("AccessToken", "")
    user_id = result.get("User", {}).get("Id", "")
    user_name = result.get("User", {}).get("Name", "")
    print(f"[INFO] 登录成功: {user_name} (ID: {user_id})")
    return token


def make_headers(token):
    return {
        "X-Emby-Authorization": f'{EMBY_AUTH_HEADER}, Token="{token}"',
    }


def get_movies(base_url, token, library_id=None):
    headers = make_headers(token)
    params = {
        "IncludeItemTypes": "Movie",
        "Recursive": "true",
        "Fields": "Path,PremiereDate,CommunityRating,Size,DateCreated",
        "Limit": "10000",
        "SortBy": "ProductionYear",
        "SortOrder": "Ascending",
    }
    if library_id:
        params["ParentId"] = library_id
    url = f"{base_url}/Items"
    debug(f"GET {url}")
    debug(f"  params: {params}")
    resp = requests.get(url, headers=headers, params=params)
    debug(f"  response: {resp.status_code}")
    resp.raise_for_status()
    return resp.json().get("Items", [])


def get_libraries(base_url, token):
    headers = make_headers(token)
    url = f"{base_url}/Library/VirtualFolders"
    debug(f"GET {url}")
    resp = requests.get(url, headers=headers)
    debug(f"  response: {resp.status_code}")
    resp.raise_for_status()
    return resp.json()


def delete_item(base_url, token, item_id):
    headers = make_headers(token)
    url = f"{base_url}/Items/{item_id}"
    debug(f"DELETE {url}")
    debug(f"  headers: {headers}")
    resp = requests.delete(url, headers=headers)
    debug(f"  response: {resp.status_code} {resp.text[:200] if resp.text else ''}")
    resp.raise_for_status()


def format_size(size_bytes):
    if not size_bytes:
        return "N/A"
    gb = size_bytes / (1024 ** 3)
    if gb >= 1:
        return f"{gb:.1f} GB"
    return f"{size_bytes / (1024**2):.0f} MB"


def main():
    global DEBUG

    parser = argparse.ArgumentParser(
        description="Jellyfin 批量删除影片",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
环境变量:
  JELLYFIN_URL        服务器地址 (替代 --url)
  JELLYFIN_USERNAME   用户名     (替代 --username)
  JELLYFIN_PASSWORD   密码       (替代 --password)

示例:
  %(prog)s --min-rating 7.0 --dry-run
  %(prog)s --before-year 2000 --dry-run
  %(prog)s --before-year 2005 --min-rating 7.0
        """,
    )
    parser.add_argument("--url", default=os.environ.get("JELLYFIN_URL", ""),
                        help="Jellyfin 地址 (或设 JELLYFIN_URL)")
    parser.add_argument("--username", default=os.environ.get("JELLYFIN_USERNAME", ""),
                        help="用户名 (或设 JELLYFIN_USERNAME)")
    parser.add_argument("--password", default=os.environ.get("JELLYFIN_PASSWORD", ""),
                        help="密码 (或设 JELLYFIN_PASSWORD)")
    parser.add_argument("--before-year", type=int, default=None,
                        help="删除此年份之前(不含)的影片")
    parser.add_argument("--after-year", type=int, default=None,
                        help="删除此年份之后(不含)的影片")
    parser.add_argument("--dry-run", action="store_true", help="仅列出,不删除")
    parser.add_argument("--yes", "-y", action="store_true", help="跳过确认")
    parser.add_argument("--library", type=str, default="", help="只处理指定库名")
    parser.add_argument("--min-rating", type=float, default=None,
                        help="保留评分>=此值的影片(只删低于此分的)")
    parser.add_argument("--max-rating", type=float, default=None,
                        help="只删评分<=此值的影片")
    parser.add_argument("--sort", choices=["year", "rating", "size", "name"],
                        default="year", help="排序(默认year)")
    parser.add_argument("--debug", action="store_true", help="显示请求详情")
    args = parser.parse_args()

    DEBUG = args.debug

    base_url = (args.url or "").rstrip("/")
    username = args.username
    password = args.password

    if not base_url:
        print("[ERROR] 未指定服务器, 用 --url 或 export JELLYFIN_URL=...")
        sys.exit(1)
    if not username:
        print("[ERROR] 未指定用户名, 用 --username 或 export JELLYFIN_USERNAME=...")
        sys.exit(1)
    if not password:
        print("[ERROR] 未指定密码, 用 --password 或 export JELLYFIN_PASSWORD=...")
        sys.exit(1)
    if all(x is None for x in [args.before_year, args.after_year, args.min_rating, args.max_rating]):
        print("[ERROR] 至少需要一个筛选条件: --before-year/--after-year/--min-rating/--max-rating")
        sys.exit(1)

    # 登录
    token = authenticate(base_url, username, password)

    library_id = None
    if args.library:
        libs = get_libraries(base_url, token)
        for lib in libs:
            if lib.get("Name", "").lower() == args.library.lower():
                library_id = lib.get("ItemId")
                break
        if not library_id:
            print(f"[ERROR] 未找到库: {args.library}")
            print("可用:", ", ".join(l.get("Name", "") for l in libs))
            sys.exit(1)

    print("[INFO] 获取影片列表...")
    movies = get_movies(base_url, token, library_id)
    print(f"[INFO] 共 {len(movies)} 部电影")

    to_delete = []
    for m in movies:
        year = m.get("ProductionYear")
        rating = m.get("CommunityRating")
        if args.before_year is not None and (year is None or year >= args.before_year):
            continue
        if args.after_year is not None and (year is None or year <= args.after_year):
            continue
        if args.min_rating is not None:
            if rating is None:
                continue
            if rating >= args.min_rating:
                continue
        if args.max_rating is not None and (rating is None or rating > args.max_rating):
            continue
        to_delete.append(m)

    if not to_delete:
        print("[INFO] 无匹配影片")
        sys.exit(0)

    sort_keys = {
        "year": lambda m: (m.get("ProductionYear") or 9999),
        "rating": lambda m: (m.get("CommunityRating") or 0),
        "size": lambda m: (m.get("Size") or 0),
        "name": lambda m: (m.get("Name") or ""),
    }
    to_delete.sort(key=sort_keys[args.sort], reverse=args.sort in ("size", "rating"))

    total_size = sum(m.get("Size", 0) or 0 for m in to_delete)
    conds = []
    if args.before_year: conds.append(f"年份<{args.before_year}")
    if args.after_year: conds.append(f"年份>{args.after_year}")
    if args.min_rating: conds.append(f"评分<{args.min_rating}")
    if args.max_rating: conds.append(f"评分<={args.max_rating}")

    print(f"\n{'='*70}")
    print(f"  待删除: {len(to_delete)} 部 | 释放: {format_size(total_size)} | 条件: {' & '.join(conds)}")
    print(f"{'='*70}\n")
    print(f"{'#':<4} {'年份':<6} {'评分':<6} {'大小':<10} {'片名'}")
    print(f"{'-'*4} {'-'*6} {'-'*6} {'-'*10} {'-'*40}")

    for i, m in enumerate(to_delete, 1):
        year = m.get("ProductionYear", "?") or "?"
        r = m.get("CommunityRating")
        rs = f"{r:.1f}" if r else "-"
        print(f"{i:<4} {year:<6} {rs:<6} {format_size(m.get('Size', 0)):<10} {m.get('Name', '?')}")
        path = m.get("Path", "")
        if path:
            print(f"{'':4} {'':6} {'':6} {'':10} └─ {path}")

    print(f"\n{'='*70}")
    print(f"  合计: {len(to_delete)} 部 | {format_size(total_size)}")
    print(f"{'='*70}")

    if args.dry_run:
        print("\n[DRY-RUN] 仅预览")
        sys.exit(0)

    if not args.yes:
        print(f"\n⚠️  即将永久删除以上 {len(to_delete)} 部影片!")
        if input("输入 'DELETE' 确认: ").strip() != "DELETE":
            print("[ABORT] 已取消")
            sys.exit(0)

    print("\n[INFO] 删除中...")
    ok = fail = 0
    for i, m in enumerate(to_delete, 1):
        try:
            delete_item(base_url, token, m["Id"])
            ok += 1
            print(f"  [{i}/{len(to_delete)}] ✓ {m.get('Name')}")
        except Exception as e:
            fail += 1
            print(f"  [{i}/{len(to_delete)}] ✗ {m.get('Name')} - {e}")

    print(f"\n[DONE] 成功:{ok} 失败:{fail} 释放:{format_size(total_size)}")


if __name__ == "__main__":
    main()
