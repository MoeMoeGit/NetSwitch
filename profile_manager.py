"""方案管理模块 - 负责方案增删改查和配置文件读写"""

import json
import os
import uuid
import shutil
import tempfile
from datetime import datetime
from pathlib import Path


APP_DIR = Path(os.environ.get("APPDATA", "")) / "NetSwitch"
CONFIG_FILE = APP_DIR / "profiles.json"


def get_default_profile():
    """获取默认方案"""
    return {
        "id": "default",
        "name": "DHCP（默认）",
        "locked": True,
        "ip_mode": "dhcp",
        "dns_mode": "auto",
    }


def get_default_config():
    """获取默认配置"""
    return {
        "profiles": [get_default_profile()],
        "active_profile_id": "default",
        "start_with_windows": True,
        "restore_last_on_boot": False,
        "window_x": None,
        "window_y": None,
    }


def ensure_config_dir():
    """确保配置目录存在"""
    APP_DIR.mkdir(parents=True, exist_ok=True)


def load_config():
    """加载配置文件。首次启动时检测当前网络状态。"""
    ensure_config_dir()

    if not CONFIG_FILE.exists():
        config = get_default_config()
        _detect_and_save_current_config(config)
        save_config(config)
        return config

    try:
        with open(CONFIG_FILE, "r", encoding="utf-8") as f:
            config = json.load(f)
    except (json.JSONDecodeError, KeyError):
        _backup_invalid_config()
        config = get_default_config()
        save_config(config)
        return config

    if not isinstance(config, dict):
        _backup_invalid_config()
        config = get_default_config()
        save_config(config)
        return config

    changed = _normalize_config(config)
    if changed:
        save_config(config)

    return config


def _detect_and_save_current_config(config):
    """首次启动时检测当前网络配置。DHCP → 激活默认方案；手动 → 创建"自定义"并激活。"""
    try:
        import network_controller

        ip_config = network_controller.get_current_ip_config()

        if not ip_config.get("ip"):
            return

        # DHCP 模式，默认方案已创建，直接激活
        if ip_config.get("dhcp", True):
            return

        # 手动静态 IP，创建导入方案
        ip = ip_config.get("ip")
        mask = ip_config.get("mask", "255.255.255.0")
        gateway = network_controller.get_gateway()
        dns = ip_config.get("dns")

        profile_data = {
            "id": str(uuid.uuid4()),
            "name": "自定义",
            "locked": False,
            "ip_mode": "static",
            "ip_address": ip,
            "subnet_mask": mask,
            "gateway": gateway or "",
            "dns_mode": "manual" if dns else "auto",
            "last_used": datetime.now().isoformat(),
        }

        if dns:
            profile_data["dns_primary"] = dns
            dns_secondary = ip_config.get("dns_secondary")
            if dns_secondary:
                profile_data["dns_secondary"] = dns_secondary

        config["profiles"].append(profile_data)
        config["active_profile_id"] = profile_data["id"]

    except Exception as e:
        print(f"检测网络配置失败: {e}")


def save_config(config):
    """保存配置文件"""
    ensure_config_dir()
    tmp_path = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            delete=False,
            dir=APP_DIR,
            prefix="profiles.",
            suffix=".tmp",
        ) as f:
            tmp_path = Path(f.name)
            json.dump(config, f, ensure_ascii=False, indent=2)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp_path, CONFIG_FILE)
    finally:
        if tmp_path and tmp_path.exists():
            try:
                tmp_path.unlink()
            except Exception:
                pass


def get_profiles(config):
    """获取所有方案"""
    return config.get("profiles", [])


def get_profile_by_id(config, profile_id):
    """根据 ID 获取方案"""
    for profile in config.get("profiles", []):
        if profile.get("id") == profile_id:
            return profile
    return None


def get_active_profile(config):
    """获取当前激活的方案"""
    active_id = config.get("active_profile_id", "default")
    return get_profile_by_id(config, active_id)


def set_active_profile(config, profile_id):
    """设置激活方案"""
    config["active_profile_id"] = profile_id
    save_config(config)


def create_profile(config, name, ip_mode, ip_address=None,
                   subnet_mask=None, gateway=None, dns_mode="auto",
                   dns_primary=None, dns_secondary=None, remark=None):
    """创建新方案"""
    profile = {
        "id": str(uuid.uuid4()),
        "name": name,
        "locked": False,
        "ip_mode": ip_mode,
        "dns_mode": dns_mode,
        "last_used": None,
    }

    if remark:
        profile["remark"] = remark

    if ip_mode == "static":
        profile["ip_address"] = ip_address
        profile["subnet_mask"] = subnet_mask
        profile["gateway"] = gateway

    if dns_mode == "manual":
        profile["dns_primary"] = dns_primary
        if dns_secondary:
            profile["dns_secondary"] = dns_secondary

    _normalize_profile(profile)
    config["profiles"].append(profile)
    save_config(config)
    return profile


def update_profile(config, profile_id, **kwargs):
    """更新方案"""
    profile = get_profile_by_id(config, profile_id)
    if not profile or profile.get("locked"):
        return None

    for key, value in kwargs.items():
        if key in ("name", "ip_mode", "ip_address", "subnet_mask",
                   "gateway", "dns_mode", "dns_primary", "dns_secondary", "remark"):
            profile[key] = value

    _normalize_profile(profile)

    save_config(config)
    return profile


def delete_profile(config, profile_id):
    """删除方案。返回 (success, message)。若方案处于激活状态，先切回 DHCP 再删除。"""
    profile = get_profile_by_id(config, profile_id)
    if not profile or profile.get("locked"):
        return False, "无法删除此方案"

    # 如果要删除的是当前激活方案，先切回 DHCP
    if config.get("active_profile_id") == profile_id and profile_id != "default":
        import network_controller
        default_profile = get_profile_by_id(config, "default")
        status, msg = network_controller.apply_profile(default_profile)
        if status == network_controller.FAILED:
            return False, "当前方案激活中，切换回默认失败，无法删除"

    config["profiles"] = [p for p in config["profiles"] if p.get("id") != profile_id]

    if config.get("active_profile_id") == profile_id:
        config["active_profile_id"] = "default"

    save_config(config)
    return True, None


def update_last_used(config, profile_id):
    """更新方案最后使用时间"""
    profile = get_profile_by_id(config, profile_id)
    if profile:
        profile["last_used"] = datetime.now().isoformat()
        save_config(config)


def get_start_with_windows(config):
    """获取开机自启设置"""
    return config.get("start_with_windows", True)


def set_start_with_windows(config, enabled):
    """设置开机自启"""
    config["start_with_windows"] = enabled
    save_config(config)


def get_restore_last_on_boot(config):
    """获取开机恢复方案设置"""
    return config.get("restore_last_on_boot", False)


def set_restore_last_on_boot(config, enabled):
    """设置开机恢复方案"""
    config["restore_last_on_boot"] = enabled
    save_config(config)


def save_window_position(config, x, y):
    """保存主窗口位置"""
    config["window_x"] = x
    config["window_y"] = y
    save_config(config)


def get_window_position(config):
    """获取保存的主窗口位置，返回 (x, y) 或 (None, None)"""
    return config.get("window_x"), config.get("window_y")


def _backup_invalid_config():
    """保留损坏配置的备份，避免直接覆盖丢失。"""
    if not CONFIG_FILE.exists():
        return

    backup_path = CONFIG_FILE.with_name(
        f"profiles.invalid.{datetime.now().strftime('%Y%m%d%H%M%S')}.json"
    )
    try:
        shutil.copy2(CONFIG_FILE, backup_path)
    except Exception:
        pass


def _normalize_config(config):
    """补齐配置结构并清理无法使用的 profile。返回是否发生变更。"""
    changed = False

    if not isinstance(config, dict):
        return False

    if not isinstance(config.get("profiles"), list):
        config["profiles"] = []
        changed = True

    valid_profiles = []
    for profile in config["profiles"]:
        if not isinstance(profile, dict) or not profile.get("id") or not profile.get("name"):
            changed = True
            continue
        changed = _normalize_profile(profile) or changed
        valid_profiles.append(profile)

    config["profiles"] = valid_profiles

    if not any(p.get("id") == "default" for p in config["profiles"]):
        config["profiles"].insert(0, get_default_profile())
        changed = True

    if not get_profile_by_id(config, config.get("active_profile_id", "default")):
        config["active_profile_id"] = "default"
        changed = True

    return changed


def _normalize_profile(profile):
    """清理与当前模式不匹配的旧字段。返回是否发生变更。"""
    changed = False

    if profile.get("ip_mode") != "static":
        for key in ("ip_address", "subnet_mask", "gateway"):
            if key in profile:
                profile.pop(key, None)
                changed = True

    if profile.get("dns_mode") != "manual":
        for key in ("dns_primary", "dns_secondary"):
            if key in profile:
                profile.pop(key, None)
                changed = True

    return changed
