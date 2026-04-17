"""
Quark Drive API Client - 夸克网盘 API 封装
"""

import os
import re
import json
import time
import random
import urllib.parse
import requests
from datetime import datetime
from typing import Optional, Tuple, List, Dict, Any

from quark_cli import debug as dbg


class QuarkAPI:
    """夸克网盘 API 客户端"""

    BASE_URL = "https://drive-pc.quark.cn"
    BASE_URL_APP = "https://drive-m.quark.cn"
    USER_AGENT = (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) quark-cloud-drive/3.14.2 Chrome/112.0.5615.165 "
        "Electron/24.1.3.8 Safari/537.36 Channel/pckk_other_ch"
    )

    def __init__(self, cookie: str = ""):
        self.cookie = cookie.strip()
        self.is_active = False
        self.nickname = ""
        self.mparam = self._match_mparam(cookie)
        self.savepath_fid: Dict[str, str] = {"/": "0"}

    def _match_mparam(self, cookie: str) -> dict:
        """从 cookie 提取移动端参数"""
        mparam = {}
        kps = re.search(r"(?<!\w)kps=([a-zA-Z0-9%+/=]+)[;&]?", cookie)
        sign = re.search(r"(?<!\w)sign=([a-zA-Z0-9%+/=]+)[;&]?", cookie)
        vcode = re.search(r"(?<!\w)vcode=([a-zA-Z0-9%+/=]+)[;&]?", cookie)
        if kps and sign and vcode:
            mparam = {
                "kps": kps.group(1).replace("%25", "%"),
                "sign": sign.group(1).replace("%25", "%"),
                "vcode": vcode.group(1).replace("%25", "%"),
            }
        return mparam

    def _request(self, method: str, url: str, **kwargs) -> requests.Response:
        """发送请求"""
        headers = {
            "cookie": self.cookie,
            "content-type": "application/json",
            "user-agent": self.USER_AGENT,
        }
        if "headers" in kwargs:
            headers = kwargs.pop("headers")

        # 分享链接使用移动端参数
        if self.mparam and "share" in url and self.BASE_URL in url:
            url = url.replace(self.BASE_URL, self.BASE_URL_APP)
            kwargs.setdefault("params", {}).update(
                {
                    "device_model": "M2011K2C",
                    "entry": "default_clouddrive",
                    "dmn": "Mi%2B11",
                    "fr": "android",
                    "pf": "3300",
                    "bi": "35937",
                    "ve": "7.4.5.680",
                    "ss": "411x875",
                    "mi": "M2011K2C",
                    "nt": "5",
                    "nw": "0",
                    "kt": "4",
                    "pr": "ucpro",
                    "sv": "release",
                    "dt": "phone",
                    "data_from": "ucapi",
                    "kps": self.mparam.get("kps"),
                    "sign": self.mparam.get("sign"),
                    "vcode": self.mparam.get("vcode"),
                    "app": "clouddrive",
                    "kkkk": "1",
                }
            )
            del headers["cookie"]

        # Debug: 打印请求
        dbg.log_request(method, url, params=kwargs.get("params"), body=kwargs.get("json"))

        try:
            t0 = time.time()
            response = requests.request(method, url, headers=headers, timeout=30, **kwargs)
            elapsed_ms = (time.time() - t0) * 1000

            # Debug: 打印响应
            try:
                resp_body = response.json()
            except Exception:
                resp_body = response.text[:500] if response.text else None
            dbg.log_response(response.status_code, url, body=resp_body, elapsed_ms=elapsed_ms)

            return response
        except Exception as e:
            dbg.log("API", f"请求异常: {e}")
            fake = requests.Response()
            fake.status_code = 500
            fake._content = json.dumps(
                {"status": 500, "code": 1, "message": str(e)}
            ).encode()
            return fake

    # ========== 账号相关 ==========

    def get_account_info(self) -> Optional[dict]:
        """获取账号信息"""
        url = "https://pan.quark.cn/account/info"
        resp = self._request("GET", url, params={"fr": "pc", "platform": "pc"}).json()
        return resp.get("data") if resp.get("data") else None

    def init(self) -> Optional[dict]:
        """初始化账号，验证 cookie 有效性"""
        info = self.get_account_info()
        if info:
            self.is_active = True
            self.nickname = info.get("nickname", "")
            return info
        return None

    def get_growth_info(self) -> Optional[dict]:
        """获取成长信息（空间/签到）"""
        url = f"{self.BASE_URL_APP}/1/clouddrive/capacity/growth/info"
        params = {
            "pr": "ucpro",
            "fr": "android",
            "kps": self.mparam.get("kps"),
            "sign": self.mparam.get("sign"),
            "vcode": self.mparam.get("vcode"),
        }
        headers = {"content-type": "application/json"}
        resp = self._request("GET", url, headers=headers, params=params).json()
        return resp.get("data")

    def sign_in(self) -> Tuple[bool, Any]:
        """每日签到"""
        url = f"{self.BASE_URL_APP}/1/clouddrive/capacity/growth/sign"
        params = {
            "pr": "ucpro",
            "fr": "android",
            "kps": self.mparam.get("kps"),
            "sign": self.mparam.get("sign"),
            "vcode": self.mparam.get("vcode"),
        }
        payload = {"sign_cyclic": True}
        headers = {"content-type": "application/json"}
        resp = self._request(
            "POST", url, json=payload, headers=headers, params=params
        ).json()
        if resp.get("data"):
            return True, resp["data"]["sign_daily_reward"]
        return False, resp.get("message", "未知错误")

    # ========== 分享链接相关 ==========

    def get_stoken(self, pwd_id: str, passcode: str = "") -> dict:
        """获取分享 token（同时验证分享链接是否有效）"""
        url = f"{self.BASE_URL}/1/clouddrive/share/sharepage/token"
        params = {"pr": "ucpro", "fr": "pc"}
        payload = {"pwd_id": pwd_id, "passcode": passcode}
        return self._request("POST", url, json=payload, params=params).json()

    def get_share_detail(
        self,
        pwd_id: str,
        stoken: str,
        pdir_fid: str,
        _fetch_share: int = 0,
        fetch_share_full_path: int = 0,
    ) -> dict:
        """获取分享详情（文件列表）

        自动处理:
        - 去掉 ver=2 参数 (部分分享链接在 ver=2 下返回 41004)
        - 若 pdir_fid=0 返回空列表，自动用 share.first_fid 重试
        """
        all_items = []
        page = 1
        first_resp = None

        while True:
            url = f"{self.BASE_URL}/1/clouddrive/share/sharepage/detail"
            params = {
                "pr": "ucpro",
                "fr": "pc",
                "pwd_id": pwd_id,
                "stoken": stoken,
                "pdir_fid": pdir_fid,
                "force": "0",
                "_page": page,
                "_size": "50",
                "_fetch_banner": "0",
                "_fetch_share": _fetch_share,
                "_fetch_total": "1",
                "_sort": "file_type:asc,updated_at:desc",
                "fetch_share_full_path": fetch_share_full_path,
            }
            resp = self._request("GET", url, params=params).json()

            if resp.get("code") != 0:
                # ver=2 导致 41004 时不再 fallback，因为已经去掉了 ver 参数
                return resp

            if first_resp is None:
                first_resp = resp

            items = resp["data"]["list"]
            if items:
                all_items.extend(items)
                page += 1
            else:
                break
            if len(all_items) >= resp["metadata"]["_total"]:
                break

        first_resp["data"]["list"] = all_items

        # 自动重试: pdir_fid=0 且列表为空时，尝试用 share.first_fid
        if not all_items and pdir_fid == "0":
            share_info = first_resp.get("data", {}).get("share", {})
            first_fid = share_info.get("first_fid", "")
            if first_fid:
                dbg.log("API", f"pdir_fid=0 返回空列表, 用 first_fid={first_fid} 重试")
                retry_resp = self.get_share_detail(
                    pwd_id, stoken, first_fid,
                    _fetch_share=_fetch_share,
                    fetch_share_full_path=fetch_share_full_path,
                )
                if retry_resp.get("code") == 0:
                    retry_items = retry_resp["data"]["list"]
                    if retry_items:
                        first_resp["data"]["list"] = retry_items
                        # 保留 share 信息
                        if "share" not in first_resp["data"] and "share" in retry_resp.get("data", {}):
                            first_resp["data"]["share"] = retry_resp["data"]["share"]
                        return first_resp
                    # first_fid 也是空, 可能是单文件分享, 构造一个虚拟列表
                    if share_info.get("file_num", 0) > 0:
                        dbg.log("API", "first_fid 也为空, 构造单文件条目")
                        first_resp["data"]["list"] = [{
                            "fid": first_fid,
                            "file_name": share_info.get("title", "未知文件"),
                            "dir": share_info.get("first_layer_file_categories", [None])[0] == 0,
                            "share_fid_token": first_fid,
                            "size": share_info.get("size", 0),
                        }]

        return first_resp

    # ========== 文件操作 ==========

    def get_fids(self, file_paths: List[str]) -> List[dict]:
        """根据文件路径获取 fid"""
        fids = []
        remaining = list(file_paths)
        while remaining:
            url = f"{self.BASE_URL}/1/clouddrive/file/info/path_list"
            params = {"pr": "ucpro", "fr": "pc"}
            payload = {"file_path": remaining[:50], "namespace": "0"}
            resp = self._request("POST", url, json=payload, params=params).json()
            if resp["code"] == 0:
                fids.extend(resp["data"])
                remaining = remaining[50:]
            else:
                break
        return fids

    def ls_dir(self, pdir_fid: str, **kwargs) -> dict:
        """列出目录文件"""
        all_items = []
        page = 1
        while True:
            url = f"{self.BASE_URL}/1/clouddrive/file/sort"
            params = {
                "pr": "ucpro",
                "fr": "pc",
                "uc_param_str": "",
                "pdir_fid": pdir_fid,
                "_page": page,
                "_size": "50",
                "_fetch_total": "1",
                "_fetch_sub_dirs": "0",
                "_sort": "file_type:asc,updated_at:desc",
                "_fetch_full_path": kwargs.get("fetch_full_path", 0),
                "fetch_all_file": 1,
                "fetch_risk_file_name": 1,
            }
            resp = self._request("GET", url, params=params).json()
            if resp.get("code") != 0:
                return resp
            items = resp["data"]["list"]
            if items:
                all_items.extend(items)
                page += 1
            else:
                break
            if len(all_items) >= resp["metadata"]["_total"]:
                break
        resp["data"]["list"] = all_items
        return resp

    def save_file(
        self,
        fid_list: List[str],
        fid_token_list: List[str],
        to_pdir_fid: str,
        pwd_id: str,
        stoken: str,
    ) -> dict:
        """转存文件"""
        url = f"{self.BASE_URL}/1/clouddrive/share/sharepage/save"
        params = {
            "pr": "ucpro",
            "fr": "pc",
            "uc_param_str": "",
            "app": "clouddrive",
            "__dt": int(random.uniform(1, 5) * 60 * 1000),
            "__t": datetime.now().timestamp(),
        }
        payload = {
            "fid_list": fid_list,
            "fid_token_list": fid_token_list,
            "to_pdir_fid": to_pdir_fid,
            "pwd_id": pwd_id,
            "stoken": stoken,
            "pdir_fid": "0",
            "scene": "link",
        }
        return self._request("POST", url, json=payload, params=params).json()

    def query_task(self, task_id: str) -> dict:
        """查询任务状态"""
        retry = 0
        while True:
            url = f"{self.BASE_URL}/1/clouddrive/task"
            params = {
                "pr": "ucpro",
                "fr": "pc",
                "uc_param_str": "",
                "task_id": task_id,
                "retry_index": retry,
                "__dt": int(random.uniform(1, 5) * 60 * 1000),
                "__t": datetime.now().timestamp(),
            }
            resp = self._request("GET", url, params=params).json()
            if resp.get("status") != 200:
                return resp
            if resp["data"]["status"] == 2:
                break
            retry += 1
            time.sleep(0.5)
            if retry > 60:
                break
        return resp

    def mkdir(self, dir_path: str) -> dict:
        """创建目录"""
        url = f"{self.BASE_URL}/1/clouddrive/file"
        params = {"pr": "ucpro", "fr": "pc", "uc_param_str": ""}
        payload = {
            "pdir_fid": "0",
            "file_name": "",
            "dir_path": dir_path,
            "dir_init_lock": False,
        }
        return self._request("POST", url, json=payload, params=params).json()

    def rename(self, fid: str, file_name: str) -> dict:
        """重命名文件"""
        url = f"{self.BASE_URL}/1/clouddrive/file/rename"
        params = {"pr": "ucpro", "fr": "pc", "uc_param_str": ""}
        payload = {"fid": fid, "file_name": file_name}
        return self._request("POST", url, json=payload, params=params).json()

    def delete(self, filelist: List[str]) -> dict:
        """删除文件"""
        url = f"{self.BASE_URL}/1/clouddrive/file/delete"
        params = {"pr": "ucpro", "fr": "pc", "uc_param_str": ""}
        payload = {"action_type": 2, "filelist": filelist, "exclude_fids": []}
        return self._request("POST", url, json=payload, params=params).json()

    def download(self, fids: List[str]) -> Tuple[dict, str]:
        """获取下载链接"""
        url = f"{self.BASE_URL}/1/clouddrive/file/download"
        params = {"pr": "ucpro", "fr": "pc", "uc_param_str": ""}
        payload = {"fids": fids}
        resp = self._request("POST", url, json=payload, params=params)
        cookies = resp.cookies.get_dict()
        cookie_str = "; ".join(f"{k}={v}" for k, v in cookies.items())
        return resp.json(), cookie_str

    def recycle_list(self, page: int = 1, size: int = 30) -> list:
        """回收站列表"""
        url = f"{self.BASE_URL}/1/clouddrive/file/recycle/list"
        params = {
            "_page": page,
            "_size": size,
            "pr": "ucpro",
            "fr": "pc",
            "uc_param_str": "",
        }
        resp = self._request("GET", url, params=params).json()
        return resp.get("data", {}).get("list", [])

    def recycle_remove(self, record_list: list) -> dict:
        """彻底删除回收站文件"""
        url = f"{self.BASE_URL}/1/clouddrive/file/recycle/remove"
        params = {"uc_param_str": "", "fr": "pc", "pr": "ucpro"}
        payload = {"select_mode": 2, "record_list": record_list}
        return self._request("POST", url, json=payload, params=params).json()

    # ========== 工具方法 ==========

    @staticmethod
    def extract_share_url(url: str) -> Tuple[Optional[str], str, str, list]:
        """解析分享链接，返回 (pwd_id, passcode, pdir_fid, paths)"""
        match_id = re.search(r"/s/(\w+)", url)
        pwd_id = match_id.group(1) if match_id else None
        match_pwd = re.search(r"pwd=(\w+)", url)
        passcode = match_pwd.group(1) if match_pwd else ""
        paths = []
        matches = re.findall(r"/(\w{32})-?([^/]+)?", url)
        for m in matches:
            fid = m[0]
            name = urllib.parse.unquote(m[1]).replace("*101", "-")
            paths.append({"fid": fid, "name": name})
        pdir_fid = paths[-1]["fid"] if matches else "0"
        return pwd_id, passcode, pdir_fid, paths

    @staticmethod
    def format_bytes(size_bytes: int) -> str:
        """格式化字节大小"""
        units = ("B", "KB", "MB", "GB", "TB", "PB")
        i = 0
        size = float(size_bytes)
        while size >= 1024 and i < len(units) - 1:
            size /= 1024
            i += 1
        return f"{size:.2f} {units[i]}"
