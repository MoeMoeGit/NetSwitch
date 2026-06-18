"""网络控制模块 - 执行 netsh 命令、ping 验证、回滚逻辑、网卡自动检测"""

import subprocess
import json
import re
import os
import tempfile
import logging
import time
import threading
from logging.handlers import RotatingFileHandler
from pathlib import Path

_CREATE_NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)
_LOG_PATH = Path(os.environ.get("APPDATA", "")) / "NetSwitch" / "netswitch.log"
_LOGGER = logging.getLogger("NetSwitch.network")
_APPLY_LOCK = threading.Lock()


def _setup_logger():
    if _LOGGER.handlers:
        return
    try:
        _LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
        handler = RotatingFileHandler(
            _LOG_PATH, maxBytes=256 * 1024, backupCount=3, encoding="utf-8"
        )
        handler.setFormatter(logging.Formatter(
            "%(asctime)s %(levelname)s %(message)s"
        ))
        _LOGGER.addHandler(handler)
        _LOGGER.setLevel(logging.DEBUG)
        _LOGGER.propagate = False
    except Exception:
        _LOGGER.addHandler(logging.NullHandler())


def _log_debug(message):
    _setup_logger()
    _LOGGER.debug(message)


def _log_error(message):
    _setup_logger()
    _LOGGER.error(message)

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
        result = subprocess.run(
            ["powershell", "-NoProfile", "-Command", ps_cmd],
            capture_output=True, timeout=timeout,
            creationflags=_CREATE_NO_WINDOW,
        )
        if result.returncode != 0:
            err = _decode_command_output(result.stderr or b"").strip()
            _log_error(f"PowerShell failed rc={result.returncode}: {err}")
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
        _log_debug(f"netsh start: {' '.join(args)}")
        result = subprocess.run(
            ["netsh"] + args,
            capture_output=True, timeout=timeout,
            creationflags=_CREATE_NO_WINDOW,
        )
        stdout = _decode_command_output(result.stdout or b"")
        stderr = _decode_command_output(result.stderr or b"")
        output = "\n".join(
            part.strip() for part in (stdout, stderr) if part and part.strip()
        )
        if result.returncode == 0:
            _log_debug(f"netsh ok: {' '.join(args)}")
            return True, output

        message = output or f"exit code {result.returncode}"
        _log_error(f"netsh failed rc={result.returncode}: {' '.join(args)} | {message}")
        return False, message
    except Exception as e:
        _log_error(f"netsh exception: {' '.join(args)} | {e}")
        return False, str(e)


def _ps_quote(value):
    """PowerShell 单引号字符串转义。"""
    return "'" + str(value).replace("'", "''") + "'"


def get_default_adapter_ip():
    """获取系统当前优先网卡的 IP 地址（路由表 metric 最小的默认路由）"""
    adapter_ip = _get_default_adapter_ip_from_route()
    if adapter_ip:
        _log_debug(f"default adapter from route: {adapter_ip}")
        return adapter_ip
    adapter_ip = _get_default_adapter_ip_from_powershell()
    if adapter_ip:
        _log_debug(f"default adapter from powershell: {adapter_ip}")
    else:
        _log_error("default adapter not found")
    return adapter_ip


def _get_default_adapter_ip_from_powershell():
    """通过 PowerShell 路由对象获取当前优先网卡 IP。"""
    route_index = _run_ps(
        "Get-NetRoute -DestinationPrefix '0.0.0.0/0' "
        "-ErrorAction SilentlyContinue | "
        "Where-Object { $_.NextHop -and $_.NextHop -ne '0.0.0.0' } | "
        "Sort-Object @{Expression={$_.RouteMetric + $_.InterfaceMetric}} | "
        "Select-Object -First 1 -ExpandProperty InterfaceIndex"
    )
    if not route_index.isdigit():
        return None

    content = _run_ps(
        f"Get-NetIPAddress -InterfaceIndex {route_index} -AddressFamily IPv4 "
        "-ErrorAction SilentlyContinue | "
        "Where-Object { $_.IPAddress -notlike '169.254.*' } | "
        "Select-Object -First 1 -ExpandProperty IPAddress "
    )
    match = re.search(r"\b(\d{1,3}(?:\.\d{1,3}){3})\b", content)
    if match and validate_ipv4(match.group(1)):
        return match.group(1)
    return None


def _get_default_adapter_ip_from_route():
    """通过 route print 文本兜底获取当前优先网卡 IP。"""
    try:
        result = subprocess.run(
            ["route", "print", "0.0.0.0"],
            capture_output=True, timeout=10,
            creationflags=_CREATE_NO_WINDOW,
        )
        output = _decode_command_output(result.stdout)

        candidates = []
        for line in output.strip().splitlines():
            stripped = line.strip()
            parts = stripped.split()
            if len(parts) >= 5 and parts[0] == "0.0.0.0" and parts[1] == "0.0.0.0":
                try:
                    candidates.append((int(parts[4]), parts[3]))
                except ValueError:
                    continue
        if candidates:
            candidates.sort(key=lambda item: item[0])
            return candidates[0][1]
    except Exception:
        pass
    return None


def _decode_command_output(data):
    """尽量按 Windows 常见控制台编码解码命令输出。"""
    for encoding in ("utf-8", "gbk", "mbcs", "cp936", "cp437"):
        try:
            return data.decode(encoding)
        except (LookupError, UnicodeDecodeError):
            continue
    return data.decode("utf-8", errors="replace")


def get_adapter_name_by_ip(ip):
    """根据 IP 地址获取网卡名称"""
    name = _run_ps(
        f"Get-NetIPAddress -IPAddress {_ps_quote(ip)} | "
        "Select-Object -First 1 -ExpandProperty InterfaceAlias"
    )
    return name if name else None


def get_current_ip_config(adapter_ip=None):
    """获取当前网卡的 IP 配置。不传 adapter_ip 则自动检测。

    通过单次 PowerShell 调用 ConvertTo-Json 返回所有字段，避免多次 PS 进程启动。
    """
    config = {}
    if not adapter_ip:
        adapter_ip = get_default_adapter_ip()
    if not adapter_ip:
        return config

    # adapter_ip 已通过 validate_ipv4 校验，仅含数字和点，安全可拼接进 PS 字符串
    ps = (
        f"$ip = '{adapter_ip}'; "
        "$ipObj = Get-NetIPAddress -IPAddress $ip -AddressFamily IPv4 "
        "-ErrorAction SilentlyContinue | Select-Object -First 1; "
        "if (-not $ipObj) { return }; "
        "$iface = Get-NetIPInterface -InterfaceIndex $ipObj.InterfaceIndex "
        "-AddressFamily IPv4 -ErrorAction SilentlyContinue | Select-Object -First 1; "
        "$gw = (Get-NetRoute -DestinationPrefix '0.0.0.0/0' "
        "-InterfaceIndex $ipObj.InterfaceIndex -ErrorAction SilentlyContinue | "
        "Where-Object { $_.NextHop -and $_.NextHop -ne '0.0.0.0' } | "
        "Sort-Object RouteMetric | Select-Object -First 1).NextHop; "
        "$dns = @((Get-DnsClientServerAddress -InterfaceIndex $ipObj.InterfaceIndex "
        "-AddressFamily IPv4 -ErrorAction SilentlyContinue).ServerAddresses); "
        "[PSCustomObject]@{"
        "IPAddress=$ipObj.IPAddress; "
        "PrefixLength=$ipObj.PrefixLength; "
        "InterfaceAlias=$ipObj.InterfaceAlias; "
        "Dhcp=if ($iface) { [string]$iface.Dhcp } else { '' }; "
        "Gateway=$gw; "
        "Dns=$dns"
        "} | ConvertTo-Json -Compress"
    )
    raw = _run_ps(ps)
    if not raw:
        return config
    try:
        data = json.loads(raw)
    except (ValueError, json.JSONDecodeError):
        _log_error(f"get_current_ip_config: failed to parse json: {raw[:200]}")
        return config

    if not isinstance(data, dict):
        return config

    ip_addr = data.get("IPAddress")
    if isinstance(ip_addr, str) and validate_ipv4(ip_addr):
        config["ip"] = ip_addr

    prefix_len = data.get("PrefixLength")
    if isinstance(prefix_len, int) and 0 <= prefix_len <= 32:
        if prefix_len == 0:
            config["mask"] = "0.0.0.0"
        else:
            mask_bits = (0xFFFFFFFF >> (32 - prefix_len)) << (32 - prefix_len)
            config["mask"] = (
                f"{(mask_bits >> 24) & 0xFF}.{(mask_bits >> 16) & 0xFF}"
                f".{(mask_bits >> 8) & 0xFF}.{mask_bits & 0xFF}"
            )

    dhcp_raw = str(data.get("Dhcp", ""))
    config["dhcp"] = "Enabled" in dhcp_raw or "True" in dhcp_raw

    gw = data.get("Gateway")
    if isinstance(gw, str):
        m = re.search(r"\b(\d{1,3}(?:\.\d{1,3}){3})\b", gw)
        if m and validate_ipv4(m.group(1)):
            config["gateway"] = m.group(1)

    dns = data.get("Dns")
    if isinstance(dns, str):
        dns = [dns]
    elif not isinstance(dns, list):
        dns = []
    valid_dns = [d for d in dns if isinstance(d, str) and validate_ipv4(d)]
    if valid_dns:
        config["dns"] = valid_dns[0]
        if len(valid_dns) >= 2:
            config["dns_secondary"] = valid_dns[1]

    return config


def get_gateway(adapter_ip=None):
    """获取网卡的网关地址。不传 adapter_ip 则自动检测。"""
    if not adapter_ip:
        adapter_ip = get_default_adapter_ip()
    if not adapter_ip:
        return None

    gateway = _run_ps(
        f"Get-NetIPAddress -IPAddress {_ps_quote(adapter_ip)} | "
        "ForEach-Object { "
        "Get-NetRoute -DestinationPrefix '0.0.0.0/0' -InterfaceIndex $_.InterfaceIndex "
        "-ErrorAction SilentlyContinue "
        "} | Where-Object { $_.NextHop -and $_.NextHop -ne '0.0.0.0' } | "
        "Sort-Object RouteMetric | Select-Object -First 1 -ExpandProperty NextHop"
    )
    match = re.search(r"\b(\d{1,3}(?:\.\d{1,3}){3})\b", gateway)
    if match and validate_ipv4(match.group(1)):
        return match.group(1)
    return None


def ping(host, timeout=3):
    """Ping 指定主机"""
    try:
        result = subprocess.run(
            ["ping", "-n", "1", "-w", str(timeout * 1000), host],
            capture_output=True, timeout=timeout + 2,
            creationflags=_CREATE_NO_WINDOW,
        )
        return result.returncode == 0
    except Exception:
        return False


def apply_profile(profile):
    """应用网络方案。返回 (status, message)，status 为 SUCCESS / GATEWAY_UNREACHABLE / FAILED"""
    if not _APPLY_LOCK.acquire(blocking=False):
        return FAILED, "正在切换中，请稍候"

    _log_debug(f"apply start: id={profile.get('id')} name={profile.get('name')} mode={profile.get('ip_mode')}")
    adapter_name = None
    old_config = {}
    try:
        adapter_ip = get_default_adapter_ip()
        if not adapter_ip:
            _log_error("apply failed: no default adapter ip")
            return FAILED, "未检测到网络连接"

        adapter_name = get_adapter_name_by_ip(adapter_ip)
        if not adapter_name:
            _log_error(f"apply failed: no adapter name for ip={adapter_ip}")
            return FAILED, "未检测到网卡"

        _log_debug(f"apply adapter: name={adapter_name} ip={adapter_ip}")
        old_config = get_current_ip_config(adapter_ip)
        _log_debug(f"apply old_config: {old_config}")

        if profile.get("ip_mode") == "dhcp":
            ok, msg = _run_netsh([
                "interface", "ip", "set", "address",
                f"name={adapter_name}", "source=dhcp",
            ])
            if not ok:
                return _fail_with_rollback(adapter_name, old_config, f"设置 DHCP 失败：{msg}")
        else:
            ip = profile.get("ip_address")
            mask = profile.get("subnet_mask")
            gateway = profile.get("gateway")
            if not all([ip, mask, gateway]):
                return FAILED, "IP 配置不完整"
            ok, msg = _run_netsh([
                "interface", "ip", "set", "address",
                f"name={adapter_name}", "source=static",
                f"address={ip}", f"mask={mask}", f"gateway={gateway}",
            ])
            if not ok:
                return _fail_with_rollback(adapter_name, old_config, f"设置静态 IP 失败：{msg}")

        if profile.get("dns_mode") == "auto":
            ok, msg = _run_netsh([
                "interface", "ip", "set", "dnsservers",
                f"name={adapter_name}", "source=dhcp",
            ])
            if not ok:
                return _fail_with_rollback(adapter_name, old_config, f"设置 DNS 自动获取失败：{msg}")
        else:
            primary = profile.get("dns_primary")
            secondary = profile.get("dns_secondary")
            if not primary:
                return FAILED, "DNS 配置不完整"
            ok, msg = _run_netsh([
                "interface", "ip", "set", "dnsservers",
                f"name={adapter_name}", "source=static", f"address={primary}",
            ])
            if not ok:
                return _fail_with_rollback(adapter_name, old_config, f"设置首选 DNS 失败：{msg}")
            if secondary:
                ok, msg = _run_netsh([
                    "interface", "ip", "add", "dnsservers",
                    f"name={adapter_name}", f"address={secondary}", "index=2",
                ])
                if not ok:
                    return _fail_with_rollback(adapter_name, old_config, f"设置备用 DNS 失败：{msg}")

        _wait_for_profile_to_settle(profile, old_config=old_config)

        current_ip = get_default_adapter_ip() or adapter_ip
        gw = get_gateway(current_ip)
        if not gw:
            return GATEWAY_UNREACHABLE, "未检测到网关"
        if not ping(gw):
            return GATEWAY_UNREACHABLE, "网关不通"

        _log_debug(f"apply success: id={profile.get('id')} name={profile.get('name')}")
        return SUCCESS, None

    except Exception as e:
        try:
            if adapter_name:
                _rollback(adapter_name, old_config)
        except Exception:
            pass
        _log_error(f"apply exception: {e}")
        return FAILED, str(e)
    finally:
        _APPLY_LOCK.release()


def _fail_with_rollback(adapter_name, old_config, message):
    rollback_ok, rollback_message = _rollback(adapter_name, old_config)
    if rollback_ok:
        return FAILED, message
    return FAILED, f"{message}；回滚失败：{rollback_message}"


def _rollback(adapter_name, old_config):
    """回滚到之前的配置（IP + DNS）"""
    _log_debug(f"rollback start: adapter={adapter_name} old_config={old_config}")
    errors = []
    try:
        if old_config.get("dhcp"):
            ok, msg = _run_netsh([
                "interface", "ip", "set", "address",
                f"name={adapter_name}", "source=dhcp",
            ])
            if not ok:
                errors.append(f"回滚 DHCP 地址失败：{msg}")
            ok, msg = _run_netsh([
                "interface", "ip", "set", "dnsservers",
                f"name={adapter_name}", "source=dhcp",
            ])
            if not ok:
                errors.append(f"回滚 DHCP DNS 失败：{msg}")
        else:
            ip = old_config.get("ip")
            mask = old_config.get("mask")
            gateway = old_config.get("gateway")
            if ip and mask and gateway:
                ok, msg = _run_netsh([
                    "interface", "ip", "set", "address",
                    f"name={adapter_name}", "source=static",
                    f"address={ip}", f"mask={mask}", f"gateway={gateway}",
                ])
                if not ok:
                    errors.append(f"回滚静态地址失败：{msg}")
            dns = old_config.get("dns")
            if dns:
                ok, msg = _run_netsh([
                    "interface", "ip", "set", "dnsservers",
                    f"name={adapter_name}", "source=static", f"address={dns}",
                ])
                if not ok:
                    errors.append(f"回滚首选 DNS 失败：{msg}")
                dns2 = old_config.get("dns_secondary")
                if dns2:
                    ok, msg = _run_netsh([
                        "interface", "ip", "add", "dnsservers",
                        f"name={adapter_name}", f"address={dns2}", "index=2",
                    ])
                    if not ok:
                        errors.append(f"回滚备用 DNS 失败：{msg}")
            else:
                ok, msg = _run_netsh([
                    "interface", "ip", "set", "dnsservers",
                    f"name={adapter_name}", "source=dhcp",
                ])
                if not ok:
                    errors.append(f"回滚 DNS 自动获取失败：{msg}")
        _log_debug("rollback finished")
        return (len(errors) == 0, "; ".join(errors))
    except Exception as e:
        _log_error(f"rollback exception: {e}")
        return False, str(e)


def _wait_for_profile_to_settle(profile, old_config=None, timeout=5):
    """等待网络配置短暂生效；最多等待 timeout 秒，避免固定卡住。

    DHCP 切换：旧静态 IP 在 DHCP 重新协商完成前可能仍然在线，因此不能仅看
    `get_default_adapter_ip()` 是否非空——需要确认 IP 已变化（DHCP 给了新 IP）
    或 DHCP 标志已启用（已切换 DHCP 模式但 IP 恰好相同）。
    """
    old_ip = (old_config or {}).get("ip")
    deadline = time.time() + timeout
    while time.time() < deadline:
        if profile.get("ip_mode") == "dhcp":
            current_ip = get_default_adapter_ip()
            if current_ip and not current_ip.startswith("169.254."):
                if current_ip != old_ip:
                    return
                # IP 没变（DHCP 可能给了同一个 IP）；查 Dhcp 标志确认
                cfg = get_current_ip_config(current_ip)
                if cfg.get("dhcp"):
                    return
        else:
            current = get_current_ip_config()
            if current.get("ip") == profile.get("ip_address"):
                return
        time.sleep(0.5)


def validate_ipv4(ip):
    """验证 IPv4 地址格式"""
    if not ip:
        return False
    match = re.match(r"^(\d{1,3})\.(\d{1,3})\.(\d{1,3})\.(\d{1,3})$", ip)
    if not match:
        return False
    return all(0 <= int(match.group(i)) <= 255 for i in range(1, 5))


def validate_subnet_mask(mask):
    """验证子网掩码是否为连续 1 的合法掩码。"""
    if not validate_ipv4(mask):
        return False
    parts = [int(part) for part in mask.split(".")]
    value = 0
    for part in parts:
        value = (value << 8) | part

    if value == 0:
        return False

    inverted = (~value) & 0xFFFFFFFF
    return (inverted & (inverted + 1)) == 0
