"""更新检查模块 - 读取 GitHub Release 并下载安装包"""

import json
import re
import urllib.error
import urllib.request
from pathlib import Path


GITHUB_REPO = "MoeMoeGit/NetSwitch"
LATEST_RELEASE_URL = f"https://api.github.com/repos/{GITHUB_REPO}/releases/latest"
USER_AGENT = "NetSwitch-Updater"


class UpdateError(RuntimeError):
    """更新检查 / 下载失败。"""


def normalize_version(version):
    """把 v1.2.3 / 1.2.3 统一成纯版本号。"""
    if not version:
        return ""
    version = str(version).strip()
    if version.lower().startswith("v"):
        version = version[1:]
    return version


def version_key(version):
    """把版本号转成可比较的整数元组。"""
    parts = re.findall(r"\d+", normalize_version(version))
    numbers = [int(part) for part in parts[:4]]
    while len(numbers) < 4:
        numbers.append(0)
    return tuple(numbers)


def compare_versions(left, right):
    """比较两个版本号。返回 -1 / 0 / 1。"""
    left_key = version_key(left)
    right_key = version_key(right)
    if left_key < right_key:
        return -1
    if left_key > right_key:
        return 1
    return 0


def _request_json(url, timeout=10):
    request = urllib.request.Request(
        url,
        headers={
            "Accept": "application/vnd.github+json",
            "User-Agent": USER_AGENT,
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return json.load(response)
    except urllib.error.HTTPError as e:
        detail = ""
        try:
            detail = e.read().decode("utf-8", errors="ignore").strip()
        except Exception:
            pass
        message = f"HTTP {e.code}"
        if detail:
            message = f"{message}: {detail}"
        raise UpdateError(message) from e
    except urllib.error.URLError as e:
        raise UpdateError(str(e.reason or e)) from e
    except Exception as e:
        raise UpdateError(str(e)) from e


def _select_asset(assets, version):
    preferred_names = [
        f"NetSwitch-Setup-{version}.exe",
        "NetSwitch-Setup.exe",
    ]
    asset_map = {asset.get("name", ""): asset for asset in assets or []}
    for name in preferred_names:
        if name in asset_map:
            return asset_map[name]

    for asset in assets or []:
        name = asset.get("name", "")
        if name.lower().endswith(".exe") and "setup" in name.lower():
            return asset
    return None


def get_latest_release(current_version):
    """读取 GitHub 最新 Release；若没有新版本则返回 None。"""
    release = _request_json(LATEST_RELEASE_URL)
    if not isinstance(release, dict):
        raise UpdateError("GitHub Release 响应无效")

    latest_version = normalize_version(release.get("tag_name") or release.get("name"))
    if not latest_version:
        raise UpdateError("Release 未提供版本号")

    if compare_versions(latest_version, current_version) <= 0:
        return None

    asset = _select_asset(release.get("assets", []), latest_version)
    if not asset:
        raise UpdateError("未找到可下载的更新安装包")

    return {
        "version": latest_version,
        "tag_name": release.get("tag_name") or f"v{latest_version}",
        "name": release.get("name") or f"NetSwitch v{latest_version}",
        "body": release.get("body") or "",
        "html_url": release.get("html_url") or f"https://github.com/{GITHUB_REPO}/releases/latest",
        "asset_name": asset.get("name") or f"NetSwitch-Setup-{latest_version}.exe",
        "asset_url": asset.get("browser_download_url") or "",
    }


def download_file(url, destination, timeout=30, progress_callback=None, cancel_check=None):
    """下载文件到本地。"""
    request = urllib.request.Request(
        url,
        headers={"User-Agent": USER_AGENT},
    )
    destination = Path(destination)
    tmp_destination = destination.with_name(destination.name + ".download")
    if tmp_destination.exists():
        tmp_destination.unlink()
    downloaded = 0
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            total = response.headers.get("Content-Length")
            total = int(total) if total and total.isdigit() else None
            with open(tmp_destination, "wb") as file:
                while True:
                    if cancel_check and cancel_check():
                        raise UpdateError("已取消下载")
                    chunk = response.read(1024 * 1024)
                    if not chunk:
                        break
                    file.write(chunk)
                    downloaded += len(chunk)
                    if progress_callback and total:
                        progress_callback(downloaded, total)
        if downloaded <= 0:
            raise UpdateError("下载文件为空")
        tmp_destination.replace(destination)
        return str(destination)
    except Exception:
        tmp_destination.unlink(missing_ok=True)
        raise
