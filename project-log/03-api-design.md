# API / 系统接口设计

> 本项目不提供 HTTP API、RPC、WebSocket 或服务端接口。  
> 本文件记录桌面应用调用的本机系统命令接口。  
> **最后更新**：2026-05-22

## API 概览

| 类型 | 接口 | 说明 | 权限 |
|------|------|------|------|
| 系统命令 | `route print 0.0.0.0` | 读取默认路由，用于定位当前优先网卡 IP | 普通读取 |
| PowerShell | `Get-NetIPAddress` | 根据 IP 查询网卡别名、当前 IP / 前缀长度 | 普通读取 |
| PowerShell | `Get-NetIPInterface` | 查询 DHCP 状态 | 普通读取 |
| PowerShell | `Get-NetRoute` | 查询默认网关 | 普通读取 |
| PowerShell | `Get-DnsClientServerAddress` | 查询 DNS 服务器 | 普通读取 |
| 系统命令 | `netsh interface ip set address` | 设置 DHCP 或静态 IP | 管理员 |
| 系统命令 | `netsh interface ip set/add dns` | 设置 DNS | 管理员 |
| 系统命令 | `ping` | 验证网关可达性 | 普通读取 |
| 注册表 | `HKCU\Software\Microsoft\Windows\CurrentVersion\Run` | 设置当前用户开机自启 | 当前用户写入 |

## 认证方式

不适用。桌面应用通过 Windows UAC 管理员权限执行网络写入。`scripts/app.manifest` 声明 `requireAdministrator`，不使用 `ctypes` 动态提权。

## 关键命令

### 设置手动 IP

```bash
netsh interface ip set address "以太网" static 10.1.1.100 255.255.255.0 10.1.1.2
```

### 设置手动 DNS

```bash
netsh interface ip set dns "以太网" static 10.1.1.2
netsh interface ip add dns "以太网" 8.8.8.8 index=2
```

### 切回 DHCP

```bash
netsh interface ip set address "以太网" dhcp
netsh interface ip set dns "以太网" dhcp
```

### 读取当前优先网卡

```bash
route print 0.0.0.0
```

当前实现解析输出中的默认路由，取接口 IP，再用 PowerShell 查询 `InterfaceAlias`。

## 错误处理约定

`network_controller.apply_profile()` 返回：

| 状态 | 说明 |
|------|------|
| `success` | 应用成功，网关可达或无需进一步警告 |
| `gateway_unreachable` | 配置已应用，但网关 ping 不通 |
| `failed` | 应用失败 |

当前实现需要改进：部分 `netsh` 失败没有触发回滚，DNS 命令失败也可能被忽略。详见 `11-code-review-log.md`。

## 变更记录

| 日期 | 变更内容 | 原因 |
|------|----------|------|
| 2026-05-22 | 标注无服务端 API，并记录系统命令接口 | 桌面应用需要记录本地系统接口边界 |
