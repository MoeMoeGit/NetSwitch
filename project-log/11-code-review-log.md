# 代码评审记录

> **最后更新**：2026-05-25
> **验证方式**：全量阅读代码、project-log、README；运行 `python -m py_compile main.py main_window.py edit_dialog.py settings_dialog.py tray.py profile_manager.py network_controller.py scripts\build.py scripts\generate_icon.py`。  
> **限制**：未执行真实网络切换，避免改动当前机器网络配置；涉及 `netsh` 行为的问题基于代码路径和 Windows 命令语义确认。

## 评审流程

```text
A 评审（发现） → B 验证 + 修复确认项 + 评审（发现）
→ C 验证 + 修复确认项 + 评审（发现）
→ D ... → 直到无新问题
```

每一步的验证必须独立，不能直接采信上一棒结论。

---

## 评审概览

| 棒次 | 评审人 | 日期 | 发现问题数 | 其中被下一棒确认 |
|------|--------|------|-----------|-----------------|
| 1 | A: Codex | 2026-05-22 | 12 | — |
| 2 | B: Codex（实机反馈修复） | 2026-05-22 | 3 | 3 |
| 3 | E: Codex（更新完整性校验） | 2026-05-25 | 1 | 1 |

---

## 历史已修复问题

### H-01：PyQt6 托盘启动崩溃

- **类型**：Bug / 打包运行
- **严重程度**：高
- **状态**：已修复
- **位置**：`tray.py:77`
- **描述**：旧版本使用 `QMenu(self)` 创建托盘菜单，但 `QSystemTrayIcon` 不是 `QWidget`，在 PyQt6 下会崩溃。PyInstaller 使用 `--windowed` 打包后错误窗口不可见，表现为双击 exe 没反应。
- **修复方式**：改为 `QMenu()`，再通过 `self.setContextMenu(self.menu)` 挂到托盘图标。
- **回归注意**：不要把 `QMenu()` 改回 `QMenu(self)`。

### H-02：Release 只上传便携版 exe，缺少安装包

- **类型**：CI / 发布
- **严重程度**：中
- **状态**：已修复
- **位置**：`.github/workflows/release.yml`
- **描述**：旧版本 GitHub Actions 只上传 `dist/NetSwitch.exe`，没有安装 Inno Setup 并编译安装包。
- **修复方式**：Release workflow 增加 `choco install innosetup -y`、`iscc scripts/installer_output.iss`，并上传 `installer_output/NetSwitch-Setup-${VERSION}.exe`。
- **回归注意**：修改发布流程时必须同时验证便携版 exe 和安装包两个产物。

---

## A — 第一轮评审

**评审人**：Codex  
**日期**：2026-05-22  
**范围**：全量代码、README、project-log  

### 发现的问题

#### 问题 A-01：网络切换失败路径不完整回滚，DNS 写入失败可能被当作成功

- **类型**：Bug / 安全
- **严重程度**：高
- **状态**：已确认，待修复
- **位置**：`network_controller.py:176`、`network_controller.py:189`、`network_controller.py:196`
- **描述**：`apply_profile()` 只在抛出异常时调用 `_rollback()`。但 `_run_netsh()` 返回 `False` 的失败路径多处直接 `return FAILED`，不会回滚。DNS 自动 / 手动设置命令的返回值没有检查，`set dns` 或 `add dns` 失败后仍可能继续返回成功。
- **复现步骤**：
  1. 构造一个 DNS 命令失败的环境或传入无效备用 DNS。
  2. 调用 `apply_profile()`。
  3. 观察 `_run_netsh(["interface", "ip", "set/add", "dns", ...])` 返回值被忽略。
- **建议修复**：
  - `_run_netsh()` 返回详细结果：`success`、`stdout`、`stderr`、`returncode`。
  - 所有 IP / DNS 写入失败都进入统一失败处理，并尝试 `_rollback(adapter_name, old_config)`。
  - 回滚失败也应返回明确错误，提示用户当前网络可能处于半应用状态。

#### 问题 A-02：单实例唤起在窗口隐藏到托盘时失效

- **类型**：Bug / 交互
- **严重程度**：高
- **状态**：已确认，待修复
- **位置**：`main.py:41`
- **描述**：第二个实例检测到 mutex 已存在后调用 `_try_bring_existing_window()`，该函数只枚举 `IsWindowVisible(hwnd)` 的窗口。NetSwitch 主窗口关闭后会隐藏到托盘，此时没有可见窗口可枚举，第二次启动会直接退出且不会打开已有实例窗口。
- **复现步骤**：
  1. 启动应用。
  2. 关闭主窗口，使其隐藏到托盘。
  3. 再次启动 exe。
  4. 当前进程退出，但已有主窗口不会被唤起。
- **建议修复**：
  - 使用本地 IPC，如 Windows named pipe、localhost socket、Qt `QLocalServer/QLocalSocket`，向已有实例发送“show main window”消息。
  - 或创建隐藏消息窗口，第二实例通过 Windows message 通知已有实例显示窗口。

#### 问题 A-03：托盘连续点击方案可能并发执行多个网络切换

- **类型**：Bug / 并发
- **严重程度**：高
- **状态**：已确认，待修复
- **位置**：`main.py:177`
- **描述**：`_on_tray_profile_selected()` 每次点击都会创建新的 `_TrayApplyWorker` 并赋值给 `self._tray_worker`。如果用户快速点击多个方案，旧线程引用可能被覆盖，多个 `netsh` 写入并发执行，导致网络配置互相覆盖或 QThread 生命周期风险。
- **复现步骤**：
  1. 托盘右键连续点击两个不同方案。
  2. 两个后台线程都可能进入 `network_controller.apply_profile()`。
- **建议修复**：
  - 增加 `self._is_switching` 状态，切换期间禁用托盘方案菜单和主窗口激活按钮。
  - 新点击可选择忽略、排队或提示“正在切换中”。

#### 问题 A-04：默认路由识别没有按 metric 选择最小路由

- **类型**：Bug / 兼容性
- **严重程度**：高
- **状态**：已确认，待修复
- **位置**：`network_controller.py:48`
- **描述**：函数注释和设计要求是“找到 metric 最小的默认路由”，但当前实现解析 `route print` 后遇到第一条 `0.0.0.0 0.0.0.0` 就返回 `parts[3]`，没有解析和比较 metric。多网卡、VPN、虚拟网卡环境可能选错网卡。
- **复现步骤**：
  1. 准备两个默认路由，例如有线网卡和 VPN。
  2. 让输出中第一条默认路由并非 metric 最小。
  3. 当前实现会返回第一条，而非最小 metric。
- **建议修复**：
  - 解析所有默认路由并按 metric 最小选择。
  - 更稳妥的方式：用 PowerShell `Get-NetRoute -DestinationPrefix "0.0.0.0/0" | Sort-Object RouteMetric, InterfaceMetric`。

#### 问题 A-05：备用 DNS 未校验，保存后可能导致 DNS 写入失败

- **类型**：Bug
- **严重程度**：中
- **状态**：已确认，待修复
- **位置**：`edit_dialog.py:128`、`edit_dialog.py:229`、`edit_dialog.py:310`
- **描述**：备用 DNS 是选填，但如果填写了，就应校验 IPv4 格式。当前只校验首选 DNS，备用 DNS 输入框没有绑定 `textChanged` 校验，保存前也不检查。
- **复现步骤**：
  1. 新建方案，DNS 模式选“手动指定”。
  2. 首选 DNS 填合法地址，备用 DNS 填 `999.999.999.999` 或任意文本。
  3. 保存按钮仍可启用并保存。
- **建议修复**：
  - `edit_dns_secondary.textChanged.connect(self._validate)`。
  - 当备用 DNS 非空时执行 `validate_ipv4()`。
  - 保存前同样校验非空备用 DNS。

#### 问题 A-06：编辑模式切换后旧字段不清理，可能导致 DHCP 方案展示旧静态 IP

- **类型**：Bug / 数据一致性
- **严重程度**：中
- **状态**：已确认，待修复
- **位置**：`profile_manager.py:175`、`edit_dialog.py:317`、`main_window.py:201`
- **描述**：`get_data()` 在 DHCP 模式下不会返回 `ip_address/subnet_mask/gateway`，但 `update_profile()` 只覆盖传入字段，不删除旧字段。若用户把静态方案改为 DHCP，旧 IP 仍留在 JSON 中。卡片副文本对非激活方案优先读取 `ip_address`，会显示旧静态 IP。
- **复现步骤**：
  1. 创建静态 IP 方案。
  2. 编辑该方案，将 IP 模式改为 DHCP 后保存。
  3. 查看 `profiles.json` 仍保留旧静态字段；卡片可能继续显示旧 IP。
- **建议修复**：
  - 更新方案时根据 `ip_mode` 清理不适用字段。
  - 根据 `dns_mode` 清理不适用 DNS 字段。
  - 或让 `get_data()` 显式返回需要清空的字段并统一规范化 profile。

#### 问题 A-07：固定 `sleep(2)` 等待网络生效不稳定

- **类型**：Bug / 性能 / 体验
- **严重程度**：中
- **状态**：已确认，待优化
- **位置**：`network_controller.py:200`
- **描述**：写入网络配置后固定等待 2 秒。DHCP 获取网关可能超过 2 秒，导致误判网关不通；网络快速生效时又无谓等待。用户已确认目标应改为最多 5 秒轮询，每 500ms 检测一次是否生效。
- **复现步骤**：
  1. 在 DHCP 响应较慢的网络中切换 DHCP。
  2. 2 秒后可能还没有获取网关，状态进入 warning。
- **建议修复**：
  - 替换固定等待为轮询。
  - 静态模式检查目标 IP / 网关是否已出现在当前网卡。
  - DHCP 模式检查实际 IP / 网关是否获取成功。

#### 问题 A-08：状态检测在 UI 线程执行，可能周期性卡顿

- **类型**：性能 / 交互
- **严重程度**：中
- **状态**：已确认，待优化
- **位置**：`main.py:148`、`main_window.py:637`
- **描述**：主应用 30 秒一次 `_check_network_status()`，主窗口 15 秒一次 `_refresh_status_bar()`，均直接执行 `route`、PowerShell 和可能的 `ping`。PowerShell 冷启动或网络阻塞时会卡住 Qt UI 线程。
- **复现步骤**：
  1. 打开主窗口。
  2. 在 PowerShell 启动慢或网络命令阻塞时观察窗口响应。
- **建议修复**：
  - 状态刷新放入可复用后台 worker。
  - 设置超时和取消策略。
  - 避免主应用和主窗口重复执行相同检测。

#### 问题 A-09：开机自启注册表路径未显式加引号，失败也无反馈

- **类型**：Bug / 交互
- **严重程度**：中
- **状态**：已确认，待修复
- **位置**：`main.py:239`、`settings_dialog.py:54`
- **描述**：`winreg.SetValueEx()` 写入的是 `self._get_exe_path()` 原始路径。若路径包含空格，Windows Run 项可能解析失败。外层 `except Exception: pass` 会吞掉所有错误，设置弹窗和托盘菜单仍可能显示已开启。
- **复现步骤**：
  1. 将程序安装到带空格路径，如 `Program Files`。
  2. 开启开机自启。
  3. 检查 Run 值未显式加引号，异常也不会提示。
- **建议修复**：
  - Run 值写入 `"<exe_path>"`。
  - `_set_start_with_windows()` 返回成功/失败。
  - UI 根据实际结果更新勾选状态并提示错误。

#### 问题 A-10：README 构建安装包命令与实际构建脚本不一致

- **类型**：文档 Bug
- **严重程度**：低
- **状态**：已确认，待修复
- **位置**：`README.md:134`、`scripts/build.py:84`
- **描述**：`scripts/build.py` 会生成 `scripts/installer_output.iss` 并提示 `iscc {iss_path}`。README 写的是 `iscc scripts/installer.iss`，该文件是模板，包含 `{{VERSION}}`。
- **复现步骤**：
  1. 按 README 执行 `uv run python scripts/build.py`。
  2. 再执行 `iscc scripts/installer.iss`。
  3. 安装包版本占位符不会按预期替换。
- **建议修复**：
  - README 改为 `iscc scripts/installer_output.iss`。

#### 问题 A-11：首次导入 / 配置损坏恢复缺少备份和用户提示

- **类型**：数据安全 / 交互
- **严重程度**：低
- **状态**：已确认，待优化
- **位置**：`profile_manager.py:52`
- **描述**：`profiles.json` JSON 解析失败时，当前直接创建默认配置并保存，原文件内容被覆盖。用户已有方案可能因为临时损坏或手工编辑错误而丢失。
- **复现步骤**：
  1. 将 `profiles.json` 改成非法 JSON。
  2. 启动应用。
  3. 程序重建默认配置，未备份旧文件。
- **建议修复**：
  - 解析失败时把原文件复制为 `profiles.invalid.<timestamp>.json`。
  - 提示用户配置已重置，并给出备份路径。

#### 问题 A-12：窗口位置超出屏幕时没有按规格居中

- **类型**：交互
- **严重程度**：低
- **状态**：已确认，待优化
- **位置**：`main_window.py:696`
- **描述**：原 UI 规格要求窗口位置超出屏幕范围时居中显示。当前 `_restore_position()` 校验失败后直接 return，依赖 Qt 默认位置；这通常可用，但不符合规格。
- **复现步骤**：
  1. 在 `profiles.json` 写入已断开显示器上的坐标。
  2. 打开主窗口。
  3. 当前实现不会显式居中。
- **建议修复**：
  - 如果保存坐标不在任意 `availableGeometry()` 内，移动到主屏幕可用区域中心。

---

## 待下一棒验证

下一轮评审需要逐条独立验证 A-01 到 A-12，修复后把状态改为「已修复」或「不成立」，并在 `06-dev-log.md` 记录修复内容和验证方式。

---

## B — 实机反馈验证 + 修复记录

**评审人**：Codex  
**日期**：2026-05-22

### 对 A 的发现逐条验证

| A 的问题 | 确认 | 说明 |
|----------|------|------|
| A-04 | ✅ 已确认并修复 | 用户实机反馈显示托盘 warning、主窗口“未检测到网络”、DHCP 切换失败。根因与默认网卡检测失败一致；已改为 PowerShell 路由对象主路径，并保留 `route print` 文本解析兜底，不再依赖“Active Routes / 活动路由”标题。 |
| A-09 | ✅ 部分确认并部分修复 | 用户实机反馈安装时勾选开机自启，但托盘菜单未勾选。根因是菜单先构建、后更新 `_startup_enabled`，已在 `TrayIcon.update_startup_state()` 中重建菜单。Run 路径加引号和失败反馈仍待修。 |

### B 的独立评审发现

#### 问题 B-01：后台系统命令导致 GUI 程序周期性闪出控制台窗口

- **类型**：Bug / 交互
- **严重程度**：高
- **状态**：已修复
- **位置**：`network_controller.py:14`、`network_controller.py:23`、`network_controller.py:42`、`network_controller.py:55`、`network_controller.py:168`
- **描述**：打包为 `--windowed` GUI 程序后，周期性状态检测仍会启动 `route`、PowerShell、`ping` 等控制台子进程。未指定 `CREATE_NO_WINDOW` 时，用户桌面会每隔几秒闪过一个窗口。
- **复现步骤**：
  1. 安装并启动打包后的 NetSwitch。
  2. 等待状态栏或托盘定时检测触发。
  3. 桌面周期性闪出控制台窗口。
- **修复方式**：
  - 为 PowerShell、`netsh`、`route`、`ping` 子进程统一增加 `creationflags=subprocess.CREATE_NO_WINDOW`。
  - PowerShell 增加 `-NoProfile`，减少启动开销和用户环境干扰。

#### 问题 B-02：默认网卡检测依赖语言标题，中文系统可能返回 None

- **类型**：Bug
- **严重程度**：高
- **状态**：已修复
- **位置**：`network_controller.py:48`
- **描述**：旧实现需要先识别 `Active Routes` 或 `活动路由` 才解析默认路由。命令输出编码不稳定时，中文标题可能无法匹配，导致返回 `None`，进一步造成主窗口显示“未检测到网络”、DHCP 切换提示“未检测到网络连接”。
- **复现步骤**：
  1. 在中文 Windows 或命令输出编码不匹配环境运行。
  2. `route print` 实际有默认路由，但标题识别失败。
  3. `get_default_adapter_ip()` 返回 `None`。
- **修复方式**：
  - 优先使用 PowerShell `Get-NetRoute` 路由对象，按 `RouteMetric + InterfaceMetric` 选择当前优先默认路由，再用 `InterfaceIndex` 读取 IPv4 地址。
  - 保留 `route print` 文本解析作为兜底。
  - `route print` 兜底不再依赖语言标题，直接扫描所有 `0.0.0.0 0.0.0.0 ...` 默认路由行，并按 metric 最小返回接口 IP。
  - 增加多编码解码兜底。

#### 问题 B-03：托盘开机自启状态初始化后没有刷新菜单

- **类型**：Bug / 交互
- **严重程度**：中
- **状态**：已修复
- **位置**：`tray.py:99`、`main.py:127`
- **描述**：应用启动时先 `_update_tray()` 构建托盘菜单，再 `update_startup_state()` 设置 `_startup_enabled`。但 `update_startup_state()` 只更新变量，不重建菜单，因此安装器写入 Run 后，托盘右键仍显示未勾选。
- **复现步骤**：
  1. 安装时勾选开机自启。
  2. 安装后启动应用。
  3. 托盘右键菜单“开机自启”未勾选。
- **修复方式**：
  - `TrayIcon.update_startup_state()` 设置状态后调用 `_rebuild_menu()`。

#### 问题 B-04：周期性网络状态检测对子进程和资源不友好

- **类型**：性能 / 架构
- **严重程度**：中
- **状态**：已优化
- **位置**：`main.py:107`、`main.py:163`、`main_window.py:635`
- **描述**：旧实现主应用 30 秒检测一次，主窗口打开时 15 秒刷新一次。即使隐藏控制台窗口后，仍会周期性拉起 PowerShell、`route`、`ping` 等子进程。对“主要由用户主动切换网络”的托盘工具来说，持续轮询收益低。
- **复现步骤**：
  1. 启动应用常驻托盘。
  2. 不进行网络切换。
  3. 旧实现仍会定期执行网络状态检测。
- **修复方式**：
  - 删除主应用周期 timer 和主窗口状态栏 timer。
  - 新增 `_StatusCheckWorker` 后台线程，避免关键动作检测时阻塞 UI。
  - 检测触发点改为启动、右键托盘菜单、打开主窗口、切换完成、方案保存/删除等关键动作。
  - 主窗口复用主应用维护的 `status/ip/gateway` 快照，不再直接调用网络命令。

#### 问题 B-05：DHCP 切换失败时缺少 netsh 细节，且命令参数兼容性不足

- **类型**：Bug / 可诊断性
- **严重程度**：高
- **状态**：已修复，待实机 DHCP 切换验证
- **位置**：`network_controller.py:39`、`network_controller.py:211`
- **描述**：用户反馈点击 `DHCP（默认）` 会等待后失败并回到旧配置。旧实现使用较宽松的 `netsh interface ip set address <网卡名> dhcp` 形式，且 `_run_netsh()` 只返回布尔值，丢掉 stdout/stderr，无法定位失败原因。DNS 写入失败也会被忽略。
- **复现步骤**：
  1. 当前电脑为静态 IP。
  2. 点击 `DHCP（默认）`。
  3. UI 提示切换失败，但没有具体 Windows 错误。
- **修复方式**：
  - `_run_netsh()` 返回 `(success, message)`，记录返回码和输出。
  - 所有 `netsh` 写入改为标准 `name=... source=...` 参数形式。
  - DHCP、静态 IP、DNS 自动、DNS 手动、备用 DNS 的失败都会触发回滚并把错误传回 UI。
  - 增加 `%AppData%\NetSwitch\netswitch.log` 滚动日志，记录网卡选择、旧配置、命令和错误输出。
  - 固定 `sleep(2)` 改为最多 5 秒轮询等待。

#### 问题 B-06：非管理员运行时仍进入主界面，直到切换 DHCP 才失败

- **类型**：Bug / 权限
- **严重程度**：高
- **状态**：已修复
- **位置**：`main.py:92`、`main.py:348`
- **描述**：日志确认 DHCP 切换失败的实际 `netsh` 错误为“请求的操作需要提升（作为管理员运行）”。说明当前进程未以管理员权限运行，但应用仍允许用户进入主界面并尝试切换，导致切换时失败。
- **复现步骤**：
  1. 非管理员方式运行应用。
  2. 点击 `DHCP（默认）`。
  3. `netsh` 返回需要提升权限，应用回滚并提示失败。
- **修复方式**：
  - 启动时调用 `IsUserAnAdmin()` 检查权限。
  - 如果不是管理员，使用 `ShellExecuteW(..., "runas", ...)` 触发 UAC 重新启动。
  - 用户拒绝 UAC 时显示“NetSwitch 需要管理员权限才能修改网络配置”并退出。
  - 保留 manifest `requireAdministrator`，运行时自检作为兜底。

#### 问题 B-07：netsh 中文错误信息乱码

- **类型**：Bug / 可诊断性
- **严重程度**：中
- **状态**：已修复
- **位置**：`network_controller.py:76`
- **描述**：截图和日志中的错误信息显示为乱码，例如“璇锋眰...”。原因是 `netsh` 输出实际可能是 UTF-8，但旧实现固定按 GBK 解码。
- **修复方式**：
  - `_run_netsh()` 改为捕获 bytes。
  - 统一走 `_decode_command_output()`，依次尝试 UTF-8、GBK、系统编码等。
  - UI 和日志都使用解码后的正常中文错误信息。

### B 验证方式

- 运行 `uv run python -m py_compile main.py main_window.py edit_dialog.py settings_dialog.py tray.py profile_manager.py network_controller.py scripts\build.py scripts\generate_icon.py`。
- 只读调用 `network_controller.get_default_adapter_ip()`，确认返回当前默认网卡 IP。
- 分别只读调用 `network_controller._get_default_adapter_ip_from_powershell()` 和 `network_controller._get_default_adapter_ip_from_route()`，确认主路径和兜底路径都能返回当前默认网卡 IP。
- 只读调用 `network_controller.get_gateway(ip)` 和 `network_controller.get_current_ip_config(ip)`，确认可读取网关和当前静态配置。
- 搜索确认 `_status_timer`、`_refresh_status_bar`、15/30/60 秒状态检测 timer 已移除。
- 运行 `uv run python scripts\build.py` 重新打包便携版 exe。

### B 验证结果

- 静态编译通过。
- 当前开发机只读检测结果：PowerShell 主路径、route 兜底路径均返回默认网卡 IP `10.1.1.8`；可读取网关 `10.1.1.2` 和当前静态配置。
- 状态检测已改为事件触发，主窗口不再自行启动网络命令。
- 便携版 exe 已重新生成：`dist/NetSwitch.exe`。
- 未执行 DHCP 切换，避免修改当前机器网络配置。

---

## C — 确认问题修复记录

**评审人**：Codex  
**日期**：2026-05-23  
**范围**：对本轮用户要求修复的确认问题做代码修复和静态验证。

### 本轮修复项

| 问题 | 状态 | 说明 |
|------|------|------|
| A-01 失败回滚反馈不足 | 已修复，待实机回归 | `_rollback()` 逐条检查命令结果，回滚失败会拼入 UI 错误消息。 |
| A-02 单实例隐藏窗口无法唤起 | 已修复，待实机回归 | 主窗口设置固定标题；第二实例枚举隐藏窗口并 `ShowWindow/SetForegroundWindow`。 |
| A-03 托盘切换可并发 | 已修复，待实机回归 | `apply_profile()` 增加全局互斥锁，托盘和主界面入口增加防重复。 |
| A-05 备用 DNS 未校验 | 已修复 | 备用 DNS 非空时在实时校验和保存校验中检查 IPv4。 |
| A-06 模式切换旧字段残留 | 已修复 | 读取和更新方案时清理 DHCP / 自动 DNS 下不适用的旧字段。 |
| A-09 开机自启写入失败无反馈 | 已修复，待实机回归 | Run 路径加引号；写入失败不更新配置，并提示用户和回滚 UI 勾选。 |
| A-10 README 构建命令不一致 | 已修复 | 改为 `iscc scripts/installer_output.iss`。 |
| A-11 配置损坏恢复无备份 | 已修复 | 重建默认配置前备份为 `profiles.invalid.<timestamp>.json`。 |

### C 验证方式

- 运行 `python -m py_compile main.py main_window.py edit_dialog.py settings_dialog.py tray.py profile_manager.py network_controller.py scripts\build.py scripts\generate_icon.py`。
- 运行不改网络的小脚本验证切换锁忙碌返回和 profile 字段清理。

### C 验证结果

- 静态编译通过。
- 未执行真实 DHCP / 静态 IP 切换，原因是会修改当前机器网络配置。

---

## D — 全量复核与二次确认

**评审人**：Codex  
**日期**：2026-05-24  
**范围**：按用户要求先阅读 `project-log/README.md`，再复核 project-log、README、核心代码、构建脚本和 release workflow。

### 已确认问题

| 问题 | 严重程度 | 状态 | 说明 |
|------|----------|------|------|
| D-01 单实例隐藏窗口唤起仍可能失效 | 高 | 已修复，待验证 | 主窗口隐藏后保留引用，不再主动清空 `main_window`；第二实例仍通过窗口枚举尝试唤起。 |
| D-02 开机自启配置与注册表真实状态可能不同步 | 中 | 已修复 | 启动时以注册表为准，并同步回 `profiles.json`。 |
| D-03 自定义子网掩码校验过宽 | 中 | 已修复 | 新增连续 1 的合法掩码校验。 |
| D-04 配置保存不是原子写 | 中 | 已修复 | `profiles.json` 现在先写临时文件，再 `os.replace()` 原子替换。 |
| D-05 Release tag 版本与 `VERSION` 不一致时发布失败 | 低 | 已修复 | 构建脚本在打包前校验 `VERSION` 与 Git tag 是否一致。 |
| D-06 project-log 部分描述落后于代码 | 低 | 已修复 | 已同步更新 `01-function-design.md`、`03-api-design.md`、`05-current-status.md` 等文档。 |

### 待确认问题

| 问题 | 影响 | 验证需求 |
|------|------|----------|
| 多 IPv4 地址同网卡场景可能读错当前配置 | 默认路由网卡有多个 IPv4 时，正则取第一个地址不一定等于默认路由地址 | 需要 Windows 多 IP 网卡实机验证。 |
| 无默认网关 / 隔离网段是否正式支持 | 当前默认路由识别模型对无网关场景天然不友好 | 需要产品决策确认是否支持。 |

### 用户侧优化建议

- 增加“导入当前配置为方案”入口，减少用户手工录入现场网络参数。
- 为切换失败增加更显眼的通知或最近切换日志入口，避免错误只藏在 tooltip / 日志文件中。
- 区分“上次由 NetSwitch 应用的方案”和“当前系统实际匹配的方案”，避免用户手工改 Windows 网络后仍看到旧方案激活。
- 降低 DHCP 切换中间态的 `default adapter not found` 日志噪声。

### 本轮验证结果

- 静态编译通过。
- 未执行真实 DHCP / 静态 IP 切换，原因是会修改当前机器网络配置。

### D 验证方式

- 运行 `PYTHONDONTWRITEBYTECODE=1 python -B -m py_compile main.py main_window.py edit_dialog.py settings_dialog.py tray.py profile_manager.py network_controller.py scripts/build.py scripts/generate_icon.py`。
- 本轮评审未执行真实 DHCP / 静态 IP 切换，原因是会修改本机网络配置。

---

## E — 更新完整性校验修复

**评审人**：Codex
**日期**：2026-05-25
**范围**：更新检查、下载与安装链路、Release 发布流程。

### 已确认问题

| 问题 | 严重程度 | 状态 | 说明 |
|------|----------|------|------|
| E-01 软件内自动安装更新缺少完整性校验 | 高 | 已修复 | Release 现在会发布安装包对应的 SHA-256 文件；应用下载后先校验哈希，再运行安装器。若 Release 没有校验文件，软件内自动安装会退回到发布页手动下载。 |

### 本轮验证结果

- 静态编译通过。
- 未执行真实 GitHub 下载与外部安装器启动，原因是需要在线 Release 资源且会启动外部进程。

### E 验证方式

- 运行 `python -m py_compile main.py main_window.py edit_dialog.py settings_dialog.py tray.py profile_manager.py network_controller.py update_manager.py scripts\build.py scripts\generate_icon.py`。
