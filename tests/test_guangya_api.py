#!/usr/bin/env python3
"""
光鸭云盘 API 快速测试脚本

用法:
    # 设置环境变量 (推荐: 用 refresh_token, 可自动续期)
    export GUANGYA_DID="你的设备ID"
    export GUANGYA_REFRESH_TOKEN="gy.xxxxx"

    # 或者直接用 access_token (2h 过期, 临时测试用)
    export GUANGYA_DID="你的设备ID"
    export GUANGYA_TOKEN="eyJhbG..."

    # 运行全部测试
    python tests/test_guangya_api.py

    # 只测试某个功能
    python tests/test_guangya_api.py account
    python tests/test_guangya_api.py ls
    python tests/test_guangya_api.py mkdir
    python tests/test_guangya_api.py magnet
    python tests/test_guangya_api.py torrent
    python tests/test_guangya_api.py download
    python tests/test_guangya_api.py upload

获取凭证:
    1. 打开 https://www.guangyapan.com/ 并登录
    2. F12 → Console → 执行:
       console.log(localStorage.getItem('credentials_aMe-8VSlkrbQXpUR'))
    3. 输出 JSON 中:
       - refresh_token: "gy.xxx..." → 设为 GUANGYA_REFRESH_TOKEN (长期有效, 推荐)
       - access_token: "eyJ..." → 设为 GUANGYA_TOKEN (2h 过期, 临时用)
    4. F12 → Network → 任意请求 → Request Headers → did → 设为 GUANGYA_DID
"""

import os
import sys
import json
import tempfile

# 让 import 找到项目根目录
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from quark_cli.guangya_api import GuangyaAPI


# ── 颜色输出 ──────────────────────────────────────────────

GREEN = "\033[92m"
RED = "\033[91m"
YELLOW = "\033[93m"
CYAN = "\033[96m"
RESET = "\033[0m"
BOLD = "\033[1m"


def ok(msg):
    print(f"  {GREEN}✓{RESET} {msg}")


def fail(msg):
    print(f"  {RED}✗{RESET} {msg}")


def info(msg):
    print(f"  {CYAN}ℹ{RESET} {msg}")


def warn(msg):
    print(f"  {YELLOW}⚠{RESET} {msg}")


def section(title):
    print(f"\n{BOLD}{'─' * 50}")
    print(f"  {title}")
    print(f"{'─' * 50}{RESET}")


# ── 测试函数 ──────────────────────────────────────────────

def test_account(api: GuangyaAPI):
    """测试账号初始化 & 空间信息"""
    section("账号 / 空间信息")

    assets = api.init()
    if not assets:
        fail("init() 失败 — 凭证可能无效")
        return False

    ok("init() 成功")
    total = api.format_bytes(assets.get("totalSpaceSize", 0))
    used = api.format_bytes(assets.get("usedSpaceSize", 0))
    vip = "VIP" if assets.get("vipStatus") else "普通用户"
    info(f"空间: {used} / {total}  |  {vip}")

    if assets.get("vipExpireTime"):
        from datetime import datetime
        exp = datetime.fromtimestamp(assets["vipExpireTime"]).strftime("%Y-%m-%d")
        info(f"VIP 到期: {exp}")

    return True


def test_ls(api: GuangyaAPI):
    """测试列目录"""
    section("列目录 (根目录)")

    result = api.ls_dir(parent_id="", page_size=10)
    if result.get("msg") != "success":
        fail(f"ls_dir() 失败: {result}")
        return False

    items = result["data"]["list"]
    total = result["data"]["total"]
    ok(f"ls_dir() 成功, 共 {total} 项")

    for item in items[:10]:
        ftype = "📁" if item.get("resType") == 2 else "📄"
        size = api.format_bytes(item["fileSize"]) if item.get("fileSize") else "-"
        print(f"    {ftype} {item['fileName']}  ({size})  id={item['fileId']}")

    return True


def test_mkdir(api: GuangyaAPI):
    """测试创建 & 删除目录"""
    section("创建目录 → 重命名 → 删除")

    dir_name = "_quark_cli_test_dir"
    new_name = "_quark_cli_test_dir_renamed"

    # 创建
    result = api.mkdir(dir_name)
    if not result:
        fail(f"mkdir('{dir_name}') 失败")
        return False
    file_id = result["fileId"]
    ok(f"mkdir() 成功: {file_id}")

    # 重命名
    if api.rename(file_id, new_name):
        ok(f"rename() 成功: {dir_name} → {new_name}")
    else:
        warn("rename() 失败")

    # 删除
    resp = api.delete([file_id])
    if resp.get("msg") == "success" or resp.get("data", {}).get("taskId"):
        ok("delete() 成功")
    else:
        fail(f"delete() 失败: {resp}")
        return False

    return True


def test_magnet(api: GuangyaAPI):
    """测试磁力解析 (不实际下载)"""
    section("磁力链接解析")

    magnet = "magnet:?xt=urn:btih:3b245504cf5f11bbdbe1201cea6a6bf45aee1bc0"
    info(f"解析: {magnet[:60]}...")

    result = api.resolve_magnet(magnet)
    if not result:
        warn("resolve_magnet() 返回空 — 可能是磁力链接无法解析或需要 VIP")
        return True

    bt = result.get("btResInfo", {})
    ok(f"解析成功: {bt.get('fileName', '?')}")
    info(f"大小: {api.format_bytes(bt.get('fileSize', 0))}")
    info(f"子文件数: {bt.get('subfilesNum', 0)}")

    if bt.get("subfiles"):
        for sf in bt["subfiles"][:5]:
            print(f"    📄 {sf['fileName']}  ({api.format_bytes(sf.get('fileSize', 0))})")

    return True


def test_torrent(api: GuangyaAPI):
    """测试种子解析"""
    section("种子文件解析")

    torrent_files = []
    for root, dirs, files in os.walk("."):
        for f in files:
            if f.endswith(".torrent"):
                torrent_files.append(os.path.join(root, f))
        if torrent_files:
            break

    if not torrent_files:
        warn("当前目录下未找到 .torrent 文件, 跳过")
        return True

    path = torrent_files[0]
    info(f"使用: {path}")

    result = api.resolve_torrent(path)
    if not result:
        fail("resolve_torrent() 失败")
        return False

    bt = result.get("btResInfo", {})
    ok(f"解析成功: {bt.get('fileName', '?')}")
    info(f"大小: {api.format_bytes(bt.get('fileSize', 0))}")
    return True


def test_download(api: GuangyaAPI):
    """测试获取下载链接"""
    section("获取下载链接")

    result = api.ls_dir(parent_id="")
    items = result.get("data", {}).get("list", [])

    file_item = None
    for item in items:
        if item.get("resType") == 1:
            file_item = item
            break

    if not file_item:
        warn("根目录下没有文件, 跳过下载测试")
        return True

    info(f"获取下载链接: {file_item['fileName']} ({file_item['fileId']})")
    dl = api.download(file_item["fileId"])
    if not dl:
        fail("download() 失败")
        return False

    url = dl.get("signedURL", "")
    duration = dl.get("urlDuration", 0)
    ok(f"下载链接获取成功, 有效期 {duration}s")
    info(f"URL: {url[:100]}...")
    return True


def test_upload(api: GuangyaAPI):
    """测试上传小文件 → 删除"""
    section("上传 → 删除")

    content = b"quark-cli guangya api test file\n" * 10
    tmp = tempfile.NamedTemporaryFile(suffix=".txt", prefix="guangya_test_", delete=False)
    tmp.write(content)
    tmp.close()

    try:
        info(f"上传: {os.path.basename(tmp.name)} ({len(content)} bytes)")
        result = api.upload_file(tmp.name, parent_id="")

        if not result:
            warn("upload_file() 返回空 — 可能缺少 boto3 或 OSS 凭证已过期")
            info("提示: pip install boto3  可启用 S3 上传")
            return True

        ok(f"上传成功: fileId={result.get('fileId')}")

        file_id = result.get("fileId")
        if file_id:
            api.delete([file_id])
            ok("已删除测试文件")

    finally:
        os.unlink(tmp.name)

    return True


def test_cloud_tasks(api: GuangyaAPI):
    """测试查询云添加任务列表"""
    section("云添加任务列表")

    data = api.list_cloud_tasks(page_size=10, status=[0, 1])
    if data is not None:
        tasks = data.get("list", [])
        ok(f"进行中的任务: {len(tasks)} 个")
        for t in tasks[:5]:
            progress = t.get("progress", 0)
            print(f"    ⏳ [{progress}%] {t['fileName']}  ({api.format_bytes(t.get('totalSize', 0))})")
    else:
        warn("list_cloud_tasks() 返回空")

    data = api.list_cloud_tasks(page_size=10, status=[2])
    if data is not None:
        tasks = data.get("list", [])
        ok(f"已完成的任务: {len(tasks)} 个")
        for t in tasks[:5]:
            print(f"    ✅ {t['fileName']}  ({api.format_bytes(t.get('totalSize', 0))})")

    return True


# ── 主入口 ────────────────────────────────────────────────

TEST_MAP = {
    "account": test_account,
    "ls": test_ls,
    "mkdir": test_mkdir,
    "magnet": test_magnet,
    "torrent": test_torrent,
    "download": test_download,
    "upload": test_upload,
    "tasks": test_cloud_tasks,
}

DEFAULT_TESTS = ["account", "ls", "mkdir", "download", "tasks", "magnet"]


def main():
    did = os.environ.get("GUANGYA_DID", "")
    refresh_token = os.environ.get("GUANGYA_REFRESH_TOKEN", "")
    access_token = os.environ.get("GUANGYA_TOKEN", "")

    if not did or (not refresh_token and not access_token):
        print(f"{RED}错误: 未设置环境变量{RESET}")
        print()
        print("推荐方式 (refresh_token 自动续期, 长期有效):")
        print(f'  export GUANGYA_DID="你的设备ID"')
        print(f'  export GUANGYA_REFRESH_TOKEN="gy.xxxxx"')
        print()
        print("临时方式 (access_token, 2h 过期):")
        print(f'  export GUANGYA_DID="你的设备ID"')
        print(f'  export GUANGYA_TOKEN="eyJhbG..."')
        print()
        print("获取凭证:")
        print("  1. 打开 https://www.guangyapan.com/ 并登录")
        print("  2. F12 → Console 执行:")
        print("     console.log(localStorage.getItem('credentials_aMe-8VSlkrbQXpUR'))")
        print("  3. 输出 JSON 中 refresh_token 和 access_token 即所需值")
        print("  4. F12 → Network → 任意请求 → Headers → did 即设备 ID")
        sys.exit(1)

    api = GuangyaAPI(did=did, refresh_token=refresh_token, token=access_token)
    auth_mode = "refresh_token (自动续期)" if refresh_token else "access_token (2h 过期)"

    print(f"{BOLD}光鸭云盘 API 测试{RESET}")
    print(f"did:  {did[:8]}...{did[-4:]}")
    print(f"认证: {auth_mode}")

    if len(sys.argv) > 1:
        names = sys.argv[1:]
    else:
        names = DEFAULT_TESTS

    passed = 0
    failed = 0
    skipped = 0

    for name in names:
        fn = TEST_MAP.get(name)
        if not fn:
            warn(f"未知测试: {name}  (可选: {', '.join(TEST_MAP.keys())})")
            skipped += 1
            continue
        try:
            if fn(api):
                passed += 1
            else:
                failed += 1
        except Exception as e:
            fail(f"{name} 异常: {e}")
            import traceback
            traceback.print_exc()
            failed += 1

    section("测试结果")
    total = passed + failed
    color = GREEN if failed == 0 else RED
    print(f"  {color}{passed}/{total} 通过{RESET}", end="")
    if skipped:
        print(f"  {YELLOW}({skipped} 跳过){RESET}", end="")
    print()


if __name__ == "__main__":
    main()
