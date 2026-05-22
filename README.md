# NetSwitch

> Windows 系统托盘网络配置切换工具 — 右键托盘，一键切网。

![NetSwitch 主界面](assets/screenshot.png)

## 这是什么

NetSwitch 是一个轻量级的 Windows 系统托盘工具，让你在多个网络配置方案之间一键切换，无需进入系统设置手动修改 IP、网关和 DNS。

**典型场景：**

- 每天带着笔记本往返家庭和公司，需要切换 DHCP / 静态 IP
- 调试软路由、自建 DNS 时频繁更换网关和 DNS 配置
- 客户现场网络与办公网络不同，需要快速切换

## 功能

- **托盘常驻** — 最小化到系统托盘，不占任务栏空间，随时调用
- **多方案管理** — 新建、编辑、删除多套网络配置方案（DHCP 或静态 IP + 自定义 DNS）
- **右键秒切** — 托盘右键菜单直接选择方案，一键应用
- **切换安全** — 切换前自动备份当前配置，失败自动回滚，保证网络不中断
- **网卡自动识别** — 每次切换自动检测系统当前优先网卡，无需手动选择
- **状态可视化** — 托盘 tooltip 实时显示当前方案名称和网络连通状态
- **开机自启** — 可选开机启动，托盘菜单一键开关
- **首次友好** — 首次运行自动检测当前网络配置，如果是静态 IP 则自动导入为方案

## 安装

### 方式一：安装包（推荐）

从 [Releases](https://github.com/your-repo/netswitch/releases) 下载 `NetSwitch-Setup-x.x.x.exe`，双击安装。

安装包功能：
- 自定义安装路径
- 可选桌面快捷方式
- 可选开机自启动

### 方式二：便携版

从 [Releases](https://github.com/your-repo/netswitch/releases) 下载 `NetSwitch.exe`，直接运行，无需安装。

> **注意**：修改网络配置需要管理员权限，启动时会弹出 UAC 提示。

## 使用

### 基本操作

| 操作 | 方式 |
|------|------|
| 切换方案 | 右键托盘图标 → 点击方案名称 |
| 打开主界面 | 右键托盘图标 → 打开主界面，或左键单击托盘图标 |
| 新建方案 | 主界面 → 新建按钮 → 填写配置 → 保存 |
| 编辑方案 | 主界面 → 双击卡片，或右键卡片 → 查看详情 |
| 重命名方案 | 主界面 → 右键卡片 → 重命名 |
| 删除方案 | 主界面 → 选中卡片 → 删除按钮 |
| 退出程序 | 右键托盘图标 → 退出 |

### 方案配置说明

| 字段 | 说明 |
|------|------|
| 方案名称 | 任意名称，如"公司网络"、"家庭软路由" |
| IP 模式 | DHCP（自动获取）或手动指定 IP、掩码、网关 |
| 子网掩码 | 预设 /24、/16、/8，或自定义输入 |
| DNS 模式 | 自动获取，或手动指定首选/备用 DNS |

内置的「DHCP（默认）」方案不可删除、不可重命名，作为兜底方案始终可用。

### 网络状态

鼠标悬停在托盘图标上可查看当前状态：

| Tooltip 状态 | 含义 |
|-------------|------|
| 正常 | 配置已应用，网关可达 |
| 网关不通 | 配置已应用，但 ping 网关失败 |
| 切换失败 | 方案切换执行失败 |
| 切换中… | 正在应用配置 |

## 配置存储

所有方案数据保存在 `%AppData%\NetSwitch\profiles.json`。如需迁移到新电脑，直接复制该文件即可。

## 从源码构建

### 环境要求

- [Python](https://www.python.org/) 3.12
- [uv](https://docs.astral.sh/uv/) 包管理器

### 构建步骤

```bash
# 1. 克隆项目
git clone https://github.com/your-repo/netswitch.git
cd NetSwitch

# 2. 安装依赖
uv sync

# 3. 运行
uv run python main.py

# 4. 打包为 exe
uv run python scripts/generate_icon.py
uv run python scripts/build.py

# 5. 构建安装包（需要 Inno Setup 6）
iscc installer_output.iss
```

## 技术栈

| 层级 | 技术 |
|------|------|
| 语言 | Python 3.12 |
| GUI | PyQt6 |
| 网络操作 | netsh（写入）+ PowerShell（读取） |
| 配置存储 | JSON 文件 |
| 打包分发 | PyInstaller + Inno Setup |

## 项目结构

```
NetSwitch/
├── main.py                 # 程序入口，单实例检测
├── tray.py                 # 系统托盘图标和菜单
├── main_window.py          # 主界面（卡片列表）
├── edit_dialog.py          # 方案编辑弹窗
├── profile_manager.py      # 方案增删改查
├── network_controller.py   # 网络配置读写、回滚
├── assets/                 # 图标资源
└── scripts/                # 构建脚本
```

## 许可

MIT License
