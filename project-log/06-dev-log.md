# 开发日志

---

## 2026-05-23（确认问题修复）

**触发原因**：用户要求先复核已发现问题，再修复确认成立的问题。本轮修复网络切换可靠性、单实例唤起、自启反馈、配置数据一致性和 README 构建命令等问题。

**修改内容**：
1. `network_controller.py` — 增加网络写入全局互斥锁，避免多个入口并发执行 `netsh`；无网关时返回 warning；回滚命令逐条检查，回滚失败信息传回 UI。
2. `main.py`、`main_window.py` — 主窗口设置固定标题，第二实例枚举隐藏窗口也可恢复已有主窗口；托盘和主窗口入口增加切换防重复。
3. `main.py`、`settings_dialog.py` — 开机自启 Run 路径加引号；注册表写入失败时不更新配置，恢复 UI 勾选状态并提示用户。
4. `edit_dialog.py` — 备用 DNS 非空时校验 IPv4，并在保存前二次校验。
5. `profile_manager.py` — 方案读取和保存时清理与当前 IP / DNS 模式不匹配的旧字段；配置文件损坏时先备份为 `profiles.invalid.<timestamp>.json` 再重建默认配置。
6. `tray.py` — warning 状态 tooltip 改为“网关异常”，覆盖网关不通和无网关两种情况。
7. `README.md` — 安装包构建命令改为 `iscc scripts/installer_output.iss`。
8. `VERSION`、`pyproject.toml`、`uv.lock` — 版本号推进到 `1.3.1`。
9. `project-log/05-current-status.md`、`project-log/10-planning-log.md` — 更新当前状态和本轮修复方案。

**遇到的问题**：
- 网络切换行为无法在本轮直接实测，因为会修改当前机器 IP / DNS。
- 单实例完整验证需要运行打包或真实应用进程，本轮只能通过代码路径和静态编译确认。

**解决方式**：
- 将网络写入互斥放在 `network_controller.apply_profile()` 底层作为兜底，同时在 UI 入口减少重复 worker。
- 对会产生“假成功”的路径改为显式反馈：回滚失败、无网关、自启写入失败都不再静默。
- 对配置数据做读取时清理，确保旧配置文件中的残留字段也能被修正。

**验证方式**：
- 运行 `python -m py_compile main.py main_window.py edit_dialog.py settings_dialog.py tray.py profile_manager.py network_controller.py scripts\build.py scripts\generate_icon.py`。
- 运行只读 / 不改网络的小脚本，验证 `apply_profile()` 忙碌锁返回和 `profile_manager._normalize_profile()` 行为。
- 运行只读 / 不改网络的小脚本，验证合法 JSON 但结构异常的配置会恢复为默认结构。
- 运行 `uv run python scripts\build.py` 本地打包便携版 exe。

**验证结果**：
- 静态编译通过。
- 便携版 exe 本地打包通过：`dist/NetSwitch.exe`。
- 未执行真实 DHCP / 静态 IP 切换，原因是会修改本机网络配置。

**本地产物清理**：
- 本轮静态编译产生的 `__pycache__/` 和 `scripts/__pycache__/` 已删除。
- 保留 `dist/NetSwitch.exe`、`build/`、`NetSwitch.spec`、`scripts/installer_output.iss`，用于本地构建验证；这些路径已被 `.gitignore` 忽略。

---

## 2026-05-22（修复实机构建反馈问题）

**触发原因**：用户反馈最新安装包安装后桌面周期性闪过窗口；当前机器为自定义 IP，但主窗口显示“未检测到网络”，托盘为黄色，点击 DHCP 切换失败；安装时勾选开机自启但托盘右键未勾选。

**修改内容**：
1. `network_controller.py` — 为 PowerShell、`netsh`、`route`、`ping` 子进程增加 `CREATE_NO_WINDOW`，避免 GUI 程序周期性闪出控制台窗口；PowerShell 增加 `-NoProfile`。
2. `network_controller.py` — 重写默认网卡 IP 检测逻辑，优先使用 PowerShell `Get-NetRoute` 路由对象按 `RouteMetric + InterfaceMetric` 选择当前优先默认路由；`route print` 文本解析仅作兜底，且不再依赖 `Active Routes / 活动路由` 标题。
3. `main.py`、`tray.py` — 启动时先读取注册表开机自启状态再构建托盘菜单；`update_startup_state()` 更新状态后重建菜单，修复初始勾选状态不刷新。
4. `uv.lock` — `uv run` 同步本项目版本号到 1.2.2，与 `pyproject.toml` 保持一致。
5. `project-log/05-current-status.md` — 更新本轮修复状态和剩余待办。
6. `project-log/11-code-review-log.md` — 追加 B 轮实机反馈验证和修复记录。
7. `project-log/07-deployment.md`、`project-log/11-code-review-log.md` — 补充历史已修复问题：`QMenu(self)` 导致 PyQt6 托盘启动崩溃，以及 Release 缺少 Inno Setup 安装包产物。

**遇到的问题**：
- 用户环境中的网络检测失败会连锁导致托盘 warning、状态栏未检测到网络、DHCP 切换失败。
- 周期性闪窗来自后台状态检测频繁启动控制台子进程。

**解决方式**：
- 子进程统一隐藏控制台窗口。
- 默认路由解析避开本地化标题和编码依赖。
- 托盘开机自启状态更新后立即重建菜单。

**验证方式**：
- 运行 `python -m py_compile main.py main_window.py edit_dialog.py settings_dialog.py tray.py profile_manager.py network_controller.py scripts\build.py scripts\generate_icon.py`。
- 运行 `uv run python -m py_compile main.py main_window.py edit_dialog.py settings_dialog.py tray.py profile_manager.py network_controller.py scripts\build.py scripts\generate_icon.py`。
- 只读调用 `network_controller.get_default_adapter_ip()`。
- 只读调用 `network_controller.get_gateway(ip)` 和 `network_controller.get_current_ip_config(ip)`。
- 运行 `uv run python scripts\build.py` 重新打包便携版 exe。
- 尝试运行 `iscc scripts\installer_output.iss` 构建安装包。

**验证结果**：
- 静态编译通过。
- 当前开发机 PowerShell 主路径和 `route print` 兜底路径均检测到默认网卡 IP `10.1.1.8`；网关为 `10.1.1.2`，并能读取当前静态配置。
- 便携版 exe 已生成：`dist/NetSwitch.exe`。
- 安装包未生成：本机缺少 `iscc` 命令，需安装 Inno Setup 或由 GitHub Actions 构建。
- 未执行 DHCP 切换，原因是会修改本机网络配置。

**本地产物清理**：
- 本轮静态编译产生的 `__pycache__/` 和 `scripts/__pycache__/` 已删除。
- 保留 `dist/NetSwitch.exe`、`build/`、`NetSwitch.spec`、`scripts/installer_output.iss`，用于用户测试和后续安装包构建；这些路径已被 `.gitignore` 忽略。

---

## 2026-05-22（优化网络状态检测策略）

**触发原因**：用户确认网络状态对该工具不是秒级变化，后台周期性检测意义不大；更合理的策略是在启动、打开主窗口、切换网络等关键动作时检测。

**修改内容**：
1. `main.py` — 删除 30/60 秒周期检测 timer，新增 `_StatusCheckWorker` 后台线程；启动、右键托盘菜单、打开主窗口、切换完成、方案保存/删除等关键动作触发一次检测。
2. `main.py` — 网络状态检测结果统一保存为 `status/ip/gateway` 快照，托盘和主窗口共用同一份结果。
3. `main_window.py` — 删除主窗口 15 秒状态栏刷新 timer，主窗口不再直接调用网络命令，只接收主程序推送的网络状态快照。
4. `tray.py` — 托盘菜单 `aboutToShow` 时发出刷新请求，右键托盘也会触发一次后台状态检测。
5. `project-log/05-current-status.md`、`project-log/11-code-review-log.md` — 记录周期检测优化结论和验证结果。

**遇到的问题**：
- 如果完全依赖后台周期检测，会浪费资源并增加 PowerShell 子进程启动频率。
- 如果主窗口自己检测，会和托盘检测重复。

**解决方式**：
- 改成事件触发检测。
- 检测放入 QThread，避免打开窗口或切换后 UI 卡顿。
- 主窗口只消费快照，不再自行拉起系统命令。

**验证方式**：
- 运行 `uv run python -m py_compile main.py main_window.py edit_dialog.py settings_dialog.py tray.py profile_manager.py network_controller.py scripts\build.py scripts\generate_icon.py`。
- 运行只读网络检测，确认仍能读到默认网卡 IP 和网关。
- 运行 `uv run python scripts\build.py` 重新打包便携版 exe。
- 搜索确认不存在 `_status_timer`、`_refresh_status_bar`、15/30/60 秒状态检测 timer 残留。

**验证结果**：
- 静态编译通过。
- 只读检测返回默认网卡 IP `10.1.1.8`、网关 `10.1.1.2`。
- 便携版 exe 已重新生成：`dist/NetSwitch.exe`。
- 未执行真实 DHCP 切换，原因是会修改本机网络配置。

**本地产物清理**：
- 本轮静态编译产生的 `__pycache__/` 和 `scripts/__pycache__/` 已删除。
- 保留 `dist/NetSwitch.exe`、`build/`、`NetSwitch.spec`、`scripts/installer_output.iss`，用于用户测试和后续安装包构建；这些路径已被 `.gitignore` 忽略。

---

## 2026-05-22（增强 DHCP 切换诊断与 netsh 兼容性）

**触发原因**：用户反馈点击 `DHCP（默认）` 时会卡一会，然后提示切换失败，并回到之前设置；需要确认原因并提供可诊断日志。

**修改内容**：
1. `network_controller.py` — 增加滚动调试日志，路径为 `%AppData%\NetSwitch\netswitch.log`，记录默认网卡选择、应用方案、旧配置、`netsh` 命令、返回码和错误输出。
2. `network_controller.py` — `_run_netsh()` 改为返回 `(success, message)`，不再丢弃 Windows 的错误信息。
3. `network_controller.py` — `netsh` 参数改为标准 `name=... source=... address=... mask=... gateway=...` 形式，提高 DHCP / 静态 IP / DNS 设置兼容性。
4. `network_controller.py` — DNS 自动 / 手动设置失败现在会触发回滚，并把具体错误传回 UI。
5. `network_controller.py` — 写入后等待逻辑从固定 `sleep(2)` 改为最多 5 秒轮询，每 500ms 检查一次是否基本生效。
6. `network_controller.py` — `netsh` 输出改为字节捕获后多编码解码，修复中文错误信息乱码。
7. `main.py` — 启动时检查管理员权限；非管理员运行时通过 UAC 重新启动，用户拒绝时提示需要管理员权限并退出。

**遇到的问题**：
- 当前不能直接执行 DHCP 切换验证，因为会修改本机网络配置。
- 旧实现只返回“设置 DHCP 失败”，无法知道 `netsh` 实际报错。
- 日志确认当前失败根因是进程未以管理员权限运行：`netsh` 返回“请求的操作需要提升（作为管理员运行）”。

**解决方式**：
- 把可变更网络的真实命令留给用户测试。
- 通过日志和 UI 错误信息提供下一步诊断依据。
- 启动阶段主动确保管理员权限，避免进入主界面后切换才失败。

**验证方式**：
- 运行 `uv run python -m py_compile main.py main_window.py edit_dialog.py settings_dialog.py tray.py profile_manager.py network_controller.py scripts\build.py scripts\generate_icon.py`。
- 只读调用默认网卡和网关读取逻辑，确认仍能返回 `10.1.1.8` / `10.1.1.2`。
- 模拟 UTF-8 / GBK 中文 `netsh` 输出解码，确认可还原为正常中文。
- 运行 `uv run python scripts\build.py` 重新打包便携版 exe。

**验证结果**：
- 静态编译通过。
- 只读网络检测通过。
- 便携版 exe 已重新生成：`dist/NetSwitch.exe`。
- 未执行真实 DHCP 切换，原因是会修改本机网络配置。

**本地产物清理**：
- 本轮静态编译产生的 `__pycache__/` 和 `scripts/__pycache__/` 已删除。
- 保留 `dist/NetSwitch.exe`、`build/`、`NetSwitch.spec`、`scripts/installer_output.iss`，用于用户测试和后续安装包构建；这些路径已被 `.gitignore` 忽略。

---

## 2026-05-22（恢复 project-log 与全量评审）

**触发原因**：`project-log/` 曾被误删，用户移回标准文档模板，并提供原始设计文案；需要按当前代码实现补齐文档，同时把本轮发现的 bug 和优化点写入评审文档。

**修改内容**：
1. `project-log/00-project-overview.md` — 按当前实现补齐项目背景、目标、场景、技术栈、边界和约束。
2. `project-log/01-function-design.md` — 按模块补齐方案管理、网络切换、主界面、托盘设置、构建发布的功能设计。
3. `project-log/02-database-design.md` — 标注项目无数据库，改为记录 `%AppData%\NetSwitch\profiles.json` 配置结构。
4. `project-log/03-api-design.md` — 标注项目无服务端 API，记录本机系统命令接口。
5. `project-log/04-project-architecture.md` — 补齐桌面应用架构、目录结构、依赖和线程模型。
6. `project-log/05-current-status.md` — 更新当前版本、已完成能力、待处理问题、任务交接。
7. `project-log/07-deployment.md` — 补齐本地打包、CI/CD、安装包构建和回滚说明。
8. `project-log/08-env-config.md` — 补齐 Windows / Python / uv / PyQt6 等环境要求。
9. `project-log/09-external-api-reference.md` — 标注无外部服务，记录系统能力参考。
10. `project-log/10-planning-log.md` — 记录文档恢复口径和网络等待轮询的规划决策。
11. `project-log/11-code-review-log.md` — 按规范写入第一轮全量评审，确认 12 个问题。
12. `project-log/12-design-decisions.md` — 沉淀网卡识别、托盘图标、开机自启入口、等待轮询等设计决策。

**遇到的问题**：
- 原始设计文案与当前代码存在差异，包括 Python 版本、网卡检测方式、配置字段命名、首次导入名称、托盘菜单、动态图标方式、网络等待时间。
- 真实网络切换测试会修改当前机器网络配置，本轮未执行。

**解决方式**：
- 向用户确认不一致项，最终按当前代码实现写文档。
- 对当前实现中需要修复或优化的差异，写入 `05-current-status.md` 和 `11-code-review-log.md`。

**验证方式**：
- 全量阅读核心代码、README 和 project-log。
- 运行 `python -m py_compile main.py main_window.py edit_dialog.py settings_dialog.py tray.py profile_manager.py network_controller.py scripts\build.py scripts\generate_icon.py`。
- 使用 `rg --files` 和目录扫描确认文档位置与项目结构。

**验证结果**：
- Python 静态编译通过。
- 未运行真实网络切换测试，原因是会修改本机 IP / DNS。

**本地产物清理**：
- 本轮未生成构建产物。
- 运行 `py_compile` 可能更新了 `__pycache__/`；该目录已在 `.gitignore` 中忽略，未作为交付物保留。

---

## 2026-05-23（v1.3.0 实机验证）

**验证环境**：B 电脑，WLAN 连接，10.1.6.x 网段，IP 10.1.6.93，自定义网关 10.1.6.6。

**验证结果**：

1. **首次启动检测成功**：v1.3.0 正确识别了当前静态 IP 配置（`dhcp: False`，网关 10.1.6.6），自动创建了"自定义"方案。v1.2.2 在相同环境下检测失败的原因已无法追溯（无日志）。

2. **网络切换功能正常**：
   - DHCP → 静态 IP（10.1.6.93 / 10.1.6.6）切换成功
   - 静态 IP → DHCP 切换成功
   - 日志中 `old_config` 记录完整，回滚数据可靠

3. **发现的次要问题**：切换到 DHCP 模式后，`_wait_for_profile_to_settle` 轮询期间短暂出现 `default adapter not found`。原因是切 DHCP 瞬间网卡丢失 IP，`Get-NetRoute` 返回空，PowerShell 退出码 1。约 4 秒后恢复，不影响最终结果，但说明轮询逻辑在网络配置切换的中间态下存在误报。

**日志摘录**：
```
02:34:10,327 DEBUG netsh ok: interface ip set address name=WLAN source=dhcp
02:34:12,581 ERROR PowerShell failed rc=1: 
02:34:12,638 ERROR default adapter not found
02:34:16,768 DEBUG default adapter from powershell: 10.1.6.93  ← 恢复
```

**相关文件**：`network_controller.py:402-413`（`_wait_for_profile_to_settle`）

---

## 2026-05-23（首次启动网络配置检测问题排查）

**触发原因**：用户反馈在 B 电脑上安装后首次启动，无法正确读取当前手动配置的网络。A 电脑（10.1.1.x 网段，手动 IP）检测正常，B 电脑（10.1.6.x 网段，自定义网关 10.1.6.6）检测失败，`profiles.json` 中只有默认 DHCP 方案。

**排查过程**：

1. **确认 `profiles.json` 内容**：B 电脑的配置文件中仅有默认方案，无"自定义"方案，确认首次检测确实失败。

2. **分析代码逻辑**：追踪 `_detect_and_save_current_config()`（`profile_manager.py:67`）→ `get_current_ip_config()`（`network_controller.py:183`）。发现关键判断链：
   - `network_controller.py:211-215`：通过 `Get-NetIPInterface` 检测 DHCP 状态，输出中匹配 `"True"` 或 `"Enabled"`
   - `profile_manager.py:78`：`ip_config.get("dhcp", True)`，默认值为 `True`
   - 若 PowerShell 命令返回空或异常 → `config` 中无 `dhcp` 键 → 默认 `True` → 判定为 DHCP → 跳过手动配置导入

3. **获取 B 电脑 PowerShell 输出**：
   - `Get-NetIPInterface` 显示以太网 `Dhcp: Enabled`，WLAN `Dhcp: Disabled`
   - 但以太网实际为 `Disconnected`，真正连接的是 WLAN（WiFi），IP 为 `10.1.6.93`

4. **确认设计决策**：按决策 1（`12-design-decisions.md`），不保存网卡字段，实时识别当前优先网卡。代码通过 `Get-NetRoute` 默认路由选择当前网卡，应自动选中 WLAN。

5. **矛盾点**：用户声称在 Windows 中手动设置了 IP 和网关，但 WLAN 的 `Dhcp` 显示 `Disabled`。如果手动配置已生效，DHCP 检测应返回 `False`，进入手动配置导入分支，不应失败。可能原因：
   - 用户手动配置的是其他适配器而非 WLAN
   - Windows 配置未真正保存生效
   - 用户表述中"手动"的实际含义与预期不同（如仅修改了高级设置中的网关）

6. **构建 v1.3.0 测试版**：因 v1.2.2 无日志功能，从当前代码打包 `dist/NetSwitch.exe`（v1.3.0），包含 `%AppData%\NetSwitch\netswitch.log` 滚动日志，用于后续定位。

**当前状态**：排查中断，待用户安装 v1.3.0 后在问题环境下复现，通过日志精确定位失败环节。

**待确认项**：
- B 电脑当前网络环境（是否仍在 10.1.6.x 网段）
- 用户手动配置的具体操作步骤（哪个适配器、是否真正保存）
- v1.3.0 日志中 `get_current_ip_config` 各步骤的输出

**相关文件**：
- `profile_manager.py:67-109` — `_detect_and_save_current_config()`
- `network_controller.py:183-233` — `get_current_ip_config()`
- `network_controller.py:211-215` — DHCP 检测逻辑
- `network_controller.py:236-251` — `get_gateway()`
- `12-design-decisions.md` — 决策 1：不保存网卡字段

---

<!-- 新记录追加在上方分隔线之后、旧记录之前 -->
