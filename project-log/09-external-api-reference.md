# 外部服务 / API 参考

> **最后更新**：2026-05-22

## 外部服务清单

当前不依赖外部服务、云 API、模型 API 或第三方账号体系。

## 本机系统能力参考

| 能力 | 用途 | 参考 |
|------|------|------|
| `netsh interface ip` | 写入 IP / DNS 配置 | Windows 内置命令 |
| PowerShell `NetTCPIP` 模块 | 读取 IP、路由、网卡接口 | `Get-NetIPAddress`、`Get-NetRoute`、`Get-NetIPInterface` |
| PowerShell `DnsClient` 模块 | 读取 DNS 服务器 | `Get-DnsClientServerAddress` |
| Windows 注册表 Run | 开机自启 | `HKCU\Software\Microsoft\Windows\CurrentVersion\Run` |
| Inno Setup 6 | 生成安装包 | 本地安装的 `iscc` |

## 已知问题 / 踩坑记录

| 日期 | 问题 | 解决方案 |
|------|------|----------|
| 2026-05-22 | `route print` 输出受系统语言和多网卡环境影响 | 当前代码仅做基础解析；后续应改为更稳健的 PowerShell 路由查询或显式按 metric 排序 |
| 2026-05-22 | `netsh` 失败信息当前没有暴露给用户 | 后续 `_run_netsh` 应返回 returncode、stdout、stderr，便于提示和回滚 |

## 变更记录

| 日期 | 变更内容 | 原因 |
|------|----------|------|
| 2026-05-22 | 标注无外部服务，并记录本机系统能力 | 恢复 project-log |
