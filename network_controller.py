"""网络控制模块 - 执行 netsh 命令、ping 验证、回滚逻辑、网卡自动检测"""

import subprocess
import re
import os
import tempfile

# 切换结果状态枚举
SUCCESS = "success"
GATEWAY_UNREACHABLE = "gateway_unreachable"
FAILED = "failed"


def _run_ps(command, timeout=10):
    """执行 PowerShell 命令，通过临时文件传递结果避免编码问题"""
    tmp = tempfile.NamedTemporaryFile(
        mode="w", suffix=".txt", delete=False, encoding="utf-8"
    )
    tmp_path = tmp.name
    tmp.close()
    try:
        ps_cmd = f'{command} | Out-File -FilePath "{tmp_path}" -Encoding utf8'
        subprocess.run(
            ["powershell", "-Command", ps_cmd],
            capture_output=True, timeout=timeout,
        )
        with open(tmp_path, "r", encoding="utf-8-sig") as f:
            return f.read().strip()
    finally:
        try:
            os.unlink(tmp_path)
        except OSError:
            pass


def _run_netsh(args, timeout=15):
    """执行 netsh 命令"""
    try:
        result = subprocess.run(
            ["netsh"] + args,
            capture_output=True, text=True, encoding="gbk", timeout=timeout,
        )
        return result.returncode == 0
    except Exception:
        return False


def get_default_adapter_ip():
    """获取系统当前优先网卡的 IP 地址（路由表 metric 最小的默认路由）"""
    try:
        result = subprocess.run(
            ["route", "print", "0.0.0.0"],
            capture_output=True, timeout=10,
        )
        output = result.stdout.decode("utf-8", errors="replace")
        lines = output.strip().split("\n")

        in_active = False
        for line in lines:
            stripped = line.strip()
            if "Active Routes" in stripped or "活动路由" in stripped:
                in_active = True
                continue
            if "==" in stripped:
                in_active = False
                continue
            if in_active and "0.0.0.0" in stripped:
                parts = stripped.split()
                if len(parts) >= 5 and parts[0] == "0.0.0.0" and parts[1] == "0.0.0.0":
                    return parts[3]
    except Exception:
        pass
    return None


def get_adapter_name_by_ip(ip):
    """根据 IP 地址获取网卡名称"""
    name = _run_ps(f"Get-NetIPAddress -IPAddress {ip} | Select-Object -ExpandProperty InterfaceAlias")
    return name if name else None


def get_current_ip_config(adapter_ip=None):
    """获取当前网卡的 IP 配置。不传 adapter_ip 则自动检测。"""
    config = {}
    if not adapter_ip:
        adapter_ip = get_default_adapter_ip()
    if not adapter_ip:
        return config

    adapter_name = get_adapter_name_by_ip(adapter_ip)
    if not adapter_name:
        return config

    # IP 和前缀长度
    content = _run_ps(
        f'Get-NetIPAddress -InterfaceAlias "{adapter_name}" -AddressFamily IPv4 '
        f"| Select-Object -Property IPAddress, PrefixLength"
    )
    match = re.search(r"(\d+\.\d+\.\d+\.\d+)\s+(\d+)", content)
    if match:
        config["ip"] = match.group(1)
        prefix_len = int(match.group(2))
        mask_bits = (0xFFFFFFFF >> (32 - prefix_len)) << (32 - prefix_len)
        config["mask"] = (
            f"{(mask_bits >> 24) & 0xFF}.{(mask_bits >> 16) & 0xFF}"
            f".{(mask_bits >> 8) & 0xFF}.{mask_bits & 0xFF}"
        )

    # 是否 DHCP
    dhcp_content = _run_ps(
        f'Get-NetIPInterface -InterfaceAlias "{adapter_name}" -AddressFamily IPv4 '
        f"| Select-Object -Property Dhcp"
    )
    config["dhcp"] = "True" in dhcp_content or "Enabled" in dhcp_content

    # 网关
    gw = get_gateway(adapter_ip)
    if gw:
        config["gateway"] = gw

    # DNS
    dns_content = _run_ps(
        f'Get-DnsClientServerAddress -InterfaceAlias "{adapter_name}" '
        f"| Select-Object -ExpandProperty ServerAddresses"
    )
    dns_matches = re.findall(r"(\d+\.\d+\.\d+\.\d+)", dns_content)
    if len(dns_matches) >= 1:
        config["dns"] = dns_matches[0]
    if len(dns_matches) >= 2:
        config["dns_secondary"] = dns_matches[1]

    return config


def get_gateway(adapter_ip=None):
    """获取网卡的网关地址。不传 adapter_ip 则自动检测。"""
    if not adapter_ip:
        adapter_ip = get_default_adapter_ip()
    if not adapter_ip:
        return None

    gateway = _run_ps(
        f'Get-NetRoute -DestinationPrefix "0.0.0.0/0" '
        f"-InterfaceAlias (Get-NetIPAddress -IPAddress {adapter_ip}).InterfaceAlias "
        f"| Select-Object -ExpandProperty NextHop"
    )
    if gateway and re.match(r"\d+\.\d+\.\d+\.\d+", gateway):
        return gateway
    return None


def ping(host, timeout=3):
    """Ping 指定主机"""
    try:
        result = subprocess.run(
            ["ping", "-n", "1", "-w", str(timeout * 1000), host],
            capture_output=True, timeout=timeout + 2,
        )
        return result.returncode == 0
    except Exception:
        return False


def apply_profile(profile):
    """应用网络方案。返回 (status, message)，status 为 SUCCESS / GATEWAY_UNREACHABLE / FAILED"""
    adapter_ip = get_default_adapter_ip()
    if not adapter_ip:
        return FAILED, "未检测到网络连接"

    adapter_name = get_adapter_name_by_ip(adapter_ip)
    if not adapter_name:
        return FAILED, "未检测到网卡"

    old_config = get_current_ip_config(adapter_ip)

    try:
        if profile.get("ip_mode") == "dhcp":
            if not _run_netsh(["interface", "ip", "set", "address", adapter_name, "dhcp"]):
                return FAILED, "设置 DHCP 失败"
        else:
            ip = profile.get("ip_address")
            mask = profile.get("subnet_mask")
            gateway = profile.get("gateway")
            if not all([ip, mask, gateway]):
                return FAILED, "IP 配置不完整"
            if not _run_netsh(["interface", "ip", "set", "address", adapter_name, "static", ip, mask, gateway]):
                return FAILED, "设置静态 IP 失败"

        if profile.get("dns_mode") == "auto":
            _run_netsh(["interface", "ip", "set", "dns", adapter_name, "dhcp"])
        else:
            primary = profile.get("dns_primary")
            secondary = profile.get("dns_secondary")
            if not primary:
                return FAILED, "DNS 配置不完整"
            _run_netsh(["interface", "ip", "set", "dns", adapter_name, "static", primary])
            if secondary:
                _run_netsh(["interface", "ip", "add", "dns", adapter_name, secondary, "index=2"])

        import time
        time.sleep(2)

        if profile.get("ip_mode") == "dhcp":
            gw = get_gateway()
            if gw and not ping(gw):
                return GATEWAY_UNREACHABLE, "网关不通"
        else:
            gw = profile.get("gateway")
            if gw and not ping(gw):
                return GATEWAY_UNREACHABLE, "网关不通"

        return SUCCESS, None

    except Exception as e:
        _rollback(adapter_name, old_config)
        return FAILED, str(e)


def _rollback(adapter_name, old_config):
    """回滚到之前的配置（IP + DNS）"""
    try:
        if old_config.get("dhcp"):
            _run_netsh(["interface", "ip", "set", "address", adapter_name, "dhcp"])
            _run_netsh(["interface", "ip", "set", "dns", adapter_name, "dhcp"])
        else:
            ip = old_config.get("ip")
            mask = old_config.get("mask")
            gateway = old_config.get("gateway")
            if ip and mask and gateway:
                _run_netsh(["interface", "ip", "set", "address", adapter_name, "static", ip, mask, gateway])
            dns = old_config.get("dns")
            if dns:
                _run_netsh(["interface", "ip", "set", "dns", adapter_name, "static", dns])
                dns2 = old_config.get("dns_secondary")
                if dns2:
                    _run_netsh(["interface", "ip", "add", "dns", adapter_name, dns2, "index=2"])
            else:
                _run_netsh(["interface", "ip", "set", "dns", adapter_name, "dhcp"])
    except Exception:
        pass


def validate_ipv4(ip):
    """验证 IPv4 地址格式"""
    if not ip:
        return False
    match = re.match(r"^(\d{1,3})\.(\d{1,3})\.(\d{1,3})\.(\d{1,3})$", ip)
    if not match:
        return False
    return all(0 <= int(match.group(i)) <= 255 for i in range(1, 5))
