# 数据 / 配置设计

> 本项目无数据库。此文件记录本地 JSON 配置结构。  
> **最后更新**：2026-05-22

## 数据存储选型

| 项目 | 选择 | 说明 |
|------|------|------|
| 数据库类型 | 不适用 | 桌面工具，无服务端数据库 |
| 配置存储 | JSON 文件 | `%AppData%\NetSwitch\profiles.json` |
| ORM / 驱动 | 不适用 | 使用 Python 标准库 `json` 读写 |

## 配置文件路径

```text
%AppData%\NetSwitch\profiles.json
```

首次启动时，如果文件不存在，程序自动创建。

## 顶层结构

```json
{
  "profiles": [],
  "active_profile_id": "default",
  "start_with_windows": true,
  "restore_last_on_boot": false,
  "window_x": null,
  "window_y": null
}
```

| 字段 | 类型 | 说明 |
|------|------|------|
| `profiles` | array | 网络配置方案列表 |
| `active_profile_id` | string | 上次成功激活的方案 ID |
| `start_with_windows` | boolean | 开机自启偏好，同时会尝试写入注册表 |
| `restore_last_on_boot` | boolean | 启动时是否恢复上次激活方案 |
| `window_x` | number/null | 主窗口左上角 X 坐标 |
| `window_y` | number/null | 主窗口左上角 Y 坐标 |

## 默认方案结构

```json
{
  "id": "default",
  "name": "DHCP（默认）",
  "locked": true,
  "ip_mode": "dhcp",
  "dns_mode": "auto"
}
```

默认方案不可删除、不可重命名，作为回到 DHCP 的兜底入口。

## 用户方案结构

```json
{
  "id": "uuid",
  "name": "Home 软路由",
  "locked": false,
  "remark": "备注信息，选填",
  "ip_mode": "static",
  "ip_address": "10.1.1.100",
  "subnet_mask": "255.255.255.0",
  "gateway": "10.1.1.2",
  "dns_mode": "manual",
  "dns_primary": "10.1.1.2",
  "dns_secondary": "8.8.8.8",
  "last_used": "2026-05-22T20:00:00"
}
```

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `id` | string | 是 | UUID；默认方案固定为 `default` |
| `name` | string | 是 | 方案名称 |
| `locked` | boolean | 是 | 是否锁定；默认方案为 `true` |
| `remark` | string | 否 | 备注 |
| `ip_mode` | string | 是 | `dhcp` 或 `static` |
| `ip_address` | string | 静态 IP 时 | IPv4 地址 |
| `subnet_mask` | string | 静态 IP 时 | 子网掩码 |
| `gateway` | string | 静态 IP 时 | 默认网关；当前实现强制填写 |
| `dns_mode` | string | 是 | `auto` 或 `manual` |
| `dns_primary` | string | 手动 DNS 时 | 首选 DNS |
| `dns_secondary` | string | 否 | 备用 DNS |
| `last_used` | string/null | 否 | ISO 时间字符串 |

## 设计决策

- 不保存网卡字段。程序每次切换时实时读取当前优先网卡，避免用户换网卡、改网卡名后配置失效。
- 使用 JSON 而不是 SQLite。当前数据量很小，单用户本地读写足够简单。
- 字段命名按当前代码保持一致：`remark` / `ip_address` / `subnet_mask`。

## 已知问题

- 编辑方案从静态 IP 切到 DHCP 后，旧静态字段不会被清理，可能影响展示；详见 `11-code-review-log.md`。
- JSON 损坏时当前直接重建默认配置，没有自动备份损坏文件。

## 变更记录

| 日期 | 变更内容 | 原因 |
|------|----------|------|
| 2026-05-22 | 将数据库模板改为本地 JSON 配置设计 | 项目无数据库，需记录实际配置结构 |
