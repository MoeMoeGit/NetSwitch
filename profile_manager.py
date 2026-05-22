"""方案管理模块 - 负责方案增删改查和配置文件读写"""

import json
import os
import uuid
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
        config = get_default_config()
        save_config(config)
        return config

    # 确保有默认方案
    if not any(p["id"] == "default" for p in config.get("profiles", [])):
        config["profiles"].insert(0, get_default_profile())

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

        config["profiles"].append(profile_data)
        config["active_profile_id"] = profile_data["id"]

    except Exception as e:
        print(f"检测网络配置失败: {e}")


def save_config(config):
    """保存配置文件"""
    ensure_config_dir()
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(config, f, ensure_ascii=False, indent=2)


def get_profiles(config):
    """获取所有方案"""
    return config.get("profiles", [])


def get_profile_by_id(config, profile_id):
    """根据 ID 获取方案"""
    for profile in config.get("profiles", []):
        if profile["id"] == profile_id:
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

    save_config(config)
    return profile


def delete_profile(config, profile_id):
    """删除方案"""
    profile = get_profile_by_id(config, profile_id)
    if not profile or profile.get("locked"):
        return False

    config["profiles"] = [p for p in config["profiles"] if p["id"] != profile_id]

    if config.get("active_profile_id") == profile_id:
        config["active_profile_id"] = "default"

    save_config(config)
    return True


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
