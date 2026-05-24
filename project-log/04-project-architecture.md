# 项目架构

> **最后更新**：2026-05-22

## 系统架构

```text
用户
  │
  ├─ 托盘菜单 tray.py
  │     └─ 选择方案 / 开机自启 / 设置 / 退出
  │
  ├─ 主窗口 main_window.py
  │     └─ 方案列表 / 新建编辑 / 删除 / 激活
  │
  └─ 编辑与设置弹窗 edit_dialog.py / settings_dialog.py

Qt 应用协调层 main.py
  ├─ 单实例 Mutex
  ├─ 托盘与主窗口信号连接
  ├─ 定时网络状态检测
  └─ 开机恢复上次方案

业务层
  ├─ profile_manager.py
  │     └─ %AppData%\NetSwitch\profiles.json
  └─ network_controller.py
        ├─ route print / PowerShell 读取网络状态
        ├─ netsh 写入网络配置
        └─ ping 验证网关
```

## 目录结构

```text
NetSwitch/
├── main.py                 # 入口、单实例、应用协调
├── tray.py                 # 托盘图标和菜单
├── main_window.py          # 主界面和方案卡片
├── edit_dialog.py          # 新建/编辑/查看方案弹窗
├── settings_dialog.py      # 设置弹窗
├── profile_manager.py      # 配置文件和方案管理
├── network_controller.py   # 网络读取、写入、验证和回滚
├── assets/                 # 图标、截图等资源
├── scripts/
│   ├── generate_icon.py    # 构建期图标生成
│   ├── build.py            # PyInstaller 打包
│   ├── app.manifest        # UAC requireAdministrator
│   └── installer.iss       # Inno Setup 模板
├── project-log/            # 本地开发知识库，当前被 .gitignore 忽略
├── pyproject.toml          # Python 版本和依赖
├── uv.lock                 # uv 锁文件
└── README.md               # 面向用户的说明文档
```

## 关键技术决策

### 决策 1：使用 PyQt6 构建桌面托盘应用

- **选择**：PyQt6。
- **备选方案**：Tkinter、Tauri、Electron、.NET WinForms/WPF。
- **原因**：Python 调用系统命令简单，PyQt6 能覆盖托盘、窗口、弹窗和线程需求。
- **参考**：详见 `12-design-decisions.md`。

### 决策 2：不保存网卡字段，实时识别当前优先网卡

- **选择**：通过 `route print 0.0.0.0` + PowerShell 读取当前优先网卡。
- **备选方案**：用户手动选择网卡并保存在方案中。
- **原因**：降低配置成本，避免换网卡名后方案失效。
- **已知不足**：多网卡、VPN、虚拟网卡场景可能误判。

### 决策 3：用 JSON 保存本地配置

- **选择**：`%AppData%\NetSwitch\profiles.json`。
- **备选方案**：SQLite、注册表。
- **原因**：数据结构小、迁移简单、易于手工备份。

## 依赖关系

| 依赖 | 版本 | 用途 |
|------|------|------|
| Python | `>=3.12,<3.13` | 运行环境 |
| PyQt6 | 锁定在 `uv.lock` | GUI、托盘、线程、绘制 |
| PyInstaller | dev 依赖 | 打包 exe |
| Pillow | dev 依赖 | 构建期生成 ico/png |
| Inno Setup | 6.x | 生成安装包 |
| Windows `netsh` | 系统内置 | 写入 IP/DNS 配置 |
| Windows PowerShell | 系统内置 | 读取网络状态 |

## 线程模型

- 主窗口激活方案使用 `_ApplyWorker(QThread)`，避免 UI 在网络写入时阻塞。
- 托盘激活方案使用 `_TrayApplyWorker(QThread)`。
- 删除当前激活方案时使用 `_DeleteWorker(QThread)` 先切回 DHCP。
- 状态栏刷新和主应用定时状态检测当前仍在 UI 线程执行，存在卡顿风险。

## 变更记录

| 日期 | 变更内容 | 原因 |
|------|----------|------|
| 2026-05-22 | 按当前代码补齐项目架构 | 恢复 project-log 并统一上下文 |
