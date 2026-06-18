# 开发日志

---

## 2026-06-19（v1.5.0 后置自查 — `ui_style.py` 菜单规则去重）

**触发原因**：v1.5.0 发布后用户要求再做一次完整自查；自查中发现 `ui_style.py` 中 `MENU_QSS` 和 `COMMON_QSS` 各写了一份完全相同的 QMenu 规则（30 行重复），属于上一轮提取 `MENU_QSS` 时收尾不干净。功能正常但维护性差，用户确认顺手清理。

**修改内容**：
1. `ui_style.py` — 新增私有常量 `_MENU_RULES` 作为单一来源；`COMMON_QSS` 末尾改为 `+ _MENU_RULES`；`MENU_QSS` 改为 `QWidget` 字体规则 + `_MENU_RULES`。功能等价，消除重复。
2. `project-log/05-current-status.md`、`project-log/06-dev-log.md` — 记录本次小修。

**遇到的问题**：无。

**解决方式**：抽取共享字符串片段，两份 QSS 都引用。

**验证方式**：
- 运行 `uv run python -m py_compile main.py main_window.py edit_dialog.py settings_dialog.py tray.py profile_manager.py network_controller.py update_manager.py ui_style.py scripts/build.py scripts/generate_icon.py`。
- 实例化 `MainWindow` / `EditDialog` / `SettingsDialog` / `TrayIcon`，确认 stylesheet 都正常应用。
- 断言：`COMMON_QSS` 和 `MENU_QSS` 各只出现 1 次 `QMenu::item:selected`（不再重复）；`MENU_QSS` 不包含 `QPushButton / QLineEdit / QGroupBox / QRadioButton / QCheckBox / QComboBox / QFrame` 等表单控件规则。

**验证结果**：
- 静态编译通过。
- 实例化通过。
- 两份 QSS 都只含一份 QMenu 规则；`MENU_QSS` 不含表单控件样式。

**本地产物清理**：
- 已清理 `__pycache__/`。

---

## 2026-06-19（评审发现的 14 项 bug / 优化批量修复）

**触发原因**：用户要求对全项目（不仅是 6-18 UI 改造）做一次完整评审，并把所有"确定是 bug 或可优化项"一次修完。本轮共 14 项，覆盖窗口生命周期、单实例检测、网络切换 settle、配色统一、首次启动阻塞、PowerShell 调用次数等。

**修改内容**：
1. `ui_style.py` — 抽出独立 `MENU_QSS`（QMenu 专用），`COMMON_QSS` 仍包含菜单段；`WARNING` 由 `#C27A0A` 改为 `#D97706`，与状态栏 dot 现有色一致，便于统一引用。
2. `tray.py` — `_ICON_COLORS` 由硬编码改为引用 `ui_style.SUCCESS / WARNING / DANGER`，托盘图标和主窗口状态色完全一致；菜单仅挂 `MENU_QSS`，避免把表单/按钮样式带到托盘菜单。
3. `profile_manager.py` —
   - 删除从未被调用的 `delete_profile()`（dead code）。
   - `load_config()` 首次启动只创建默认配置并标 `first_run_pending=True`，不再同步调用 PowerShell；启动延迟由原来的 1-3 秒降为零。
   - 新增 `detect_and_import_current_static()`（仅只读检测和构造 profile，可在后台线程调用）、`add_imported_profile()`（追加到 config 并视情况设为激活）、`clear_first_run_pending()`。
   - 同时去掉了原 `_detect_and_save_current_config` 中对 `get_gateway()` 的冗余调用（`get_current_ip_config` 已经包含 gateway）。
4. `network_controller.py` —
   - `get_current_ip_config()` 由 4 次串行 `_run_ps()` 改为 1 次 PowerShell + `ConvertTo-Json`，apply 流程节省 ~600ms。
   - `_wait_for_profile_to_settle()` 接受 `old_config` 参数。DHCP 路径不再只看 "有 default adapter IP" 立刻 return，要么 IP 已变化、要么 `Get-NetIPInterface.Dhcp` 状态确认 Enabled，避免切 DHCP 时旧静态 IP 仍在线导致的过早 settle / ping 旧网关误报 success。
   - `apply_profile` 调用 settle 时传入 `old_config`。
5. `edit_dialog.py` — 新建 `_grow_to_fit()`：替换 `_on_ip_mode_changed` / `_on_dns_mode_changed` / `_on_mask_changed` 中的 `adjustSize()`，弹窗只增高、不再因来回切换字段而上下抖动。
6. `main_window.py` —
   - `ProfileCard` 新增 `delete_requested` 信号；右键菜单删除走信号，移除原来 `_on_delete()` 沿 `parent()` 链向上找 `MainWindow` 的脆弱实现，`_load_cards` 改为统一信号连接。
   - 标题栏关闭按钮 `btn_close` 移除冗余的内联 `setStyleSheet`，改为依赖父级 stylesheet 的 `#titleClose` 选择器；同时给父级 stylesheet 补充 `QPushButton#titleClose` 基础样式（`border: none; background: transparent; font-size: 14px;`）。
   - `set_network_status` 颜色映射改为引用 `ui_style.SUCCESS / WARNING / DANGER`，状态栏 dot 与托盘图标的 normal / warning / error 完全一致。
   - 新增 `apply_failed` 信号；`_on_apply_finished` 的 FAILED 分支会立即把状态栏 dot 置为 error，并通过信号通知主程序刷新托盘和重新检测网络（与托盘入口失败处理对齐）。
   - `_restore_position` 由"只校验左上角点在屏内"改为"标题栏整宽 × 36px 都在屏内"，避免上次保存位置贴右边时窗口大半飘出屏幕。
7. `main.py` —
   - `show_main_window` 用 `showNormal()` 取代 `show()`，修复"先最小化、再点 X 关到托盘后，下次点托盘图标主窗口仍以最小化状态出现"的卡死感。
   - `_try_bring_existing_window` 由 `if target_title in buf.value` 改为 `if buf.value == target_title`，避免 IDE 编辑源码、浏览器仓库页等含 `NetSwitch` 字样窗口被误识别为已有实例。
   - 新增 `_FirstDetectWorker` 后台线程；`__init__` 检测到 `first_run_pending` 时启动该 worker，完成后再走开机恢复 / 状态检测流程。托盘图标首次启动可立即出现。
   - 新增 `_on_main_window_apply_failed` 处理 `MainWindow.apply_failed` 信号：托盘 `update_status("error")` + 触发 `_check_network_status`。
8. `project-log/05-current-status.md`、`project-log/06-dev-log.md` — 同步更新本轮 14 项修复范围、验证方式和遗留事项。

**遇到的问题**：
- `MainWindow` 通过 `hide()` 关闭到托盘时，`Qt.WindowMinimized` 状态不会被清除；后续 `show()` 会以最小化状态出现。已在 offscreen Qt 测试中复现并验证 `showNormal()` 修复。
- `keyPressEvent` 的 monkey-patch 在 PyQt6 中是否生效曾被怀疑：实测 PyQt6 对实例属性赋值方式的事件覆盖支持良好，无须改造。
- `WA_TranslucentBackground=False` + `mainContainer` 8px 圆角实测下角落仅有 5-10 灰度差异，肉眼几乎看不出，本轮不动这块；未来如果改造液态玻璃质感再统一处理。
- `tray.py` 首次启动时托盘菜单挂全表单 QSS 在 QMenu 内不会渲染按钮/输入框等，副作用有限，但仍按用户要求抽出独立 `MENU_QSS` 以表达意图。

**解决方式**：
- 启动期网络检测改为后台线程，先把托盘画出来再异步补 profile；如果用户在检测期间已经手动切换过方案，新检测出的方案只追加不抢占激活。
- DHCP settle 通过 IP 变化和 `Get-NetIPInterface.Dhcp` 双重确认，避免被旧静态 IP 蒙蔽。
- 主窗口失败路径的状态同步通过新信号 `apply_failed` 暴露给主程序，沿用与托盘成功 / 失败一致的处理路径。
- 单实例标题严格相等比子串匹配更安全；如果未来出现多个标题恰好同名的窗口（极罕见），可以再升级到 PID + 进程名校验。

**验证方式**：
- 运行 `uv run python -m py_compile main.py main_window.py edit_dialog.py settings_dialog.py tray.py profile_manager.py network_controller.py update_manager.py ui_style.py scripts/build.py scripts/generate_icon.py`。
- 使用临时 `APPDATA` + `QT_QPA_PLATFORM=offscreen` 实例化 `MainWindow`、`ProfileCard`、`EditDialog`、`SettingsDialog`、`TrayIcon`，验证：
  - `profile_manager.delete_profile` 已删除，`detect_and_import_current_static` / `add_imported_profile` / `clear_first_run_pending` 已新增；
  - `MainWindow.apply_failed`、`ProfileCard.delete_requested`、`EditDialog._grow_to_fit` 都存在；
  - `ui_style.MENU_QSS` 存在、`ui_style.WARNING == #D97706`；
  - `_wait_for_profile_to_settle` 签名包含 `old_config` 参数；
  - `load_config()` 首次启动产出 `first_run_pending=True`，profiles 仅有默认 1 项。
- 渲染测试确认 hide() 后再 show()/raise/activateWindow() 仍保留 `WindowMinimized`，验证修复必要性；改成 `showNormal()` 后清除最小化状态。

**验证结果**：
- 静态编译通过。
- 实例化 / 信号 / API 检查通过。
- 未执行真实 DHCP / 静态 IP 切换，原因：会修改本机网络配置，且测试机为 macOS 无 PowerShell。
- 未执行完整 PyInstaller / Inno Setup 构建。
- 未在真实 Windows 桌面验证液态玻璃观感、DHCP settle 修复在慢速 DHCP 服务器上的实际行为、首次启动后台导入的端到端体验——这些需要在真实 Windows 管理员环境下实机回归。

**本地产物清理**：
- 已清理 `__pycache__/`、`scripts/__pycache__/` 和临时 UI 截图、临时 `APPDATA`。

---

## 2026-06-18（统一液态玻璃风格界面）

**触发原因**：用户反馈前端界面太丑，特别是新建方案页面，希望改成简洁优雅、苹果风格、克制的液态玻璃界面，并统一所有页面风格。

**修改内容**：
1. `ui_style.py` — 新增共享视觉样式模块，统一字体、浅色背景、半透明白色表面、细边框、主按钮 / 危险按钮 / 文本按钮、输入框、下拉框、菜单和分组样式。
2. `edit_dialog.py` — 重做新建 / 编辑 / 查看方案弹窗，改为顶部标题、基础信息、IP 配置、DNS 配置、底部操作区的清晰分区；保留原有字段校验和保存数据结构。
3. `main_window.py` — 主窗口接入共享样式，统一卡片、标题栏、状态栏和底部按钮的浅色玻璃质感；保留原窗口尺寸、快捷键、激活和删除逻辑。
4. `settings_dialog.py` — 设置页接入共享样式，统一常规、更新、帮助与反馈区块的间距、按钮和文字层级。
5. `tray.py` — 托盘右键菜单接入共享菜单样式，使桌面入口和主窗口风格一致。
6. `project-log/05-current-status.md`、`project-log/06-dev-log.md` — 记录本轮 UI 改造范围、验证方式和剩余确认项。

**遇到的问题**：
- 第一次组件实例化验证时使用了真实 `%AppData%`，关闭测试主窗口触发了原有窗口位置保存逻辑，导致真实 `profiles.json` 被示例配置覆盖。
- 当前 `QT_QPA_PLATFORM=offscreen` 验证环境中 Qt 字体库为空，自动截图中文字渲染为方块，不能作为最终字体观感依据。

**解决方式**：
- 立即用只读网络检测重建真实配置为“默认 DHCP + 当前系统静态配置”，去掉测试示例方案；后续 UI 实例化验证统一改用临时 `APPDATA`。
- 截图只用于检查布局、间距和色块，不作为文字渲染验收；最终字体效果需要在真实 Windows 桌面环境查看。

**验证方式**：
- 运行 `python -m py_compile main.py main_window.py edit_dialog.py settings_dialog.py tray.py profile_manager.py network_controller.py update_manager.py scripts\build.py scripts\generate_icon.py ui_style.py`。
- 使用临时 `APPDATA` 和 `QT_QPA_PLATFORM=offscreen` 实例化 `MainWindow`、`EditDialog`、`SettingsDialog`，确认组件可创建且不触发网络写入。
- 运行 `git diff --check` 检查行尾空格等格式问题。

**验证结果**：
- 静态编译通过。
- 组件实例化通过。
- 未执行真实 DHCP / 静态 IP 切换，原因是会修改本机网络配置。
- 未执行完整 PyInstaller / Inno Setup 构建。

**本地产物清理**：
- 已清理本轮产生的 `__pycache__/`、`scripts/__pycache__/` 和临时 UI 截图 / 临时 `APPDATA` 目录。

## 2026-05-25（更新安装包完整性校验）

**触发原因**：用户确认优化更新流程，希望保留软件内更新入口，但把“直接下载并运行外部安装器”的安全风险补上。

**修改内容**：
1. `update_manager.py` — 解析 GitHub Release 时同时读取安装包与 SHA-256 校验文件；下载后先做哈希比对，再替换到目标路径。
2. `main.py` — 设置页的更新说明显示校验状态；若 Release 没提供校验文件，则不在软件内自动安装，直接引导用户去发布页手动下载。
3. `.github/workflows/release.yml` — Release 构建流程新增安装器 SHA-256 文件生成与上传，保证软件内自动安装有可验证来源。
4. `README.md`、`project-log/03-api-design.md`、`project-log/05-current-status.md`、`project-log/10-planning-log.md`、`project-log/12-design-decisions.md` — 同步记录更新校验策略与发布链路变化。

**遇到的问题**：
- 更新功能如果只是把远端二进制拉到本地再执行，安全边界太弱。
- 需要兼顾用户体验和安全：不能因为 Release 没有校验文件就把手动下载入口也一并堵死。

**解决方式**：
- 把自动安装更新和手动打开发布页分开。
- Release 缺少校验文件时，软件内自动安装直接退回到发布页，避免运行未验证的安装器。
- 更新校验文件放在发布流程里生成，减少人为遗漏。

**验证方式**：
- 运行 `python -m py_compile main.py main_window.py edit_dialog.py settings_dialog.py tray.py profile_manager.py network_controller.py update_manager.py scripts\build.py scripts\generate_icon.py`。

**验证结果**：
- 静态编译通过。
- 未执行真实 GitHub 下载与安装，原因是需要在线 Release 资源和会启动外部安装器。

**本地产物清理**：
- 本轮未生成构建产物。

## 2026-05-24（设置页增加检查更新与帮助反馈）

**触发原因**：用户反馈软件更新流程太麻烦，希望把检查更新放进软件内，并在设置页增加作者信息、GitHub 主页和 Issue 入口。

**修改内容**：
1. `update_manager.py` — 新增 GitHub Release 更新检查与安装包下载模块，支持版本比较、最新 Release 解析和文件下载。
2. `settings_dialog.py` — 将设置页拆成“常规 / 更新 / 帮助与反馈”三块，加入“检查更新”、作者姓名、邮箱、GitHub 主页和 Issue 反馈入口。
3. `main.py` — 接入设置页更新信号；后台检查最新 Release；发现新版本后可直接下载并运行安装包；同时补充 GitHub 页面打开逻辑。
4. `main.py` — 更新安装器启动失败时不退出当前程序；更新提示增加 Release 说明详情。
5. `scripts/installer.iss` — 安装器启用关闭 / 重启应用支持，并将安装完成后启动 NetSwitch 改为默认勾选，便于软件内更新后直接回到新版本。
6. `main.py`、`update_manager.py` — 更新检查 / 安装前避开网络切换进行中状态；下载先写 `.download` 临时文件，完整后再替换；只接受安装包资产，避免把便携版 exe 当安装器运行。
7. `main.py` — 自动安装更新仅对已安装版本开放；便携版用户会被引导到发布页手动下载新包，避免错误覆盖。
8. `main.py` — 便携版提示直接跳转 GitHub Releases 页面，减少用户寻找下载入口的步骤。

**遇到的问题**：
- 设置页原本只适合放两个开关，若直接塞入更新和反馈入口会显得拥挤。
- 软件内更新和自启动同属设置，但交互性质不同，需要拆分成独立区块，避免按钮混杂。

**解决方式**：
- 用 `QGroupBox` 组织为三个区块：常规、更新、帮助与反馈。
- 更新逻辑保持为手动触发，避免常驻后台打扰用户；支持下载后直接退出并启动安装程序。
- Windows 上不直接覆盖运行中的 exe；采用下载安装包、退出当前进程、运行安装器、安装完成后启动新版的流程。
- 更新与网络切换互斥，避免升级退出时打断正在执行的 `netsh` 写入。
- 便携版与安装版的更新策略分离，避免把“运行中的便携 exe”误当作可就地升级对象。

**验证方式**：
- 运行 `PYTHONDONTWRITEBYTECODE=1 python -B -m py_compile main.py main_window.py edit_dialog.py settings_dialog.py tray.py profile_manager.py network_controller.py scripts/build.py scripts/generate_icon.py update_manager.py`。

**验证结果**：
- 静态编译通过。
- 未执行真实网络切换，原因是会修改本机网络配置。

**本地产物清理**：
- 本轮未生成构建产物。

## 2026-05-24（按钮可读性与闪退异常落盘）

**触发原因**：Windows 台式机实机测试反馈主窗口底部按钮在白底上不可读，且点击自定义方案后应用看似成功但窗口直接退出，需要把真正的异常写入日志。

**修改内容**：
1. `main_window.py` — 为“新建”和“删除”按钮补充明确背景色、文字色和悬停态，确保在白底窗口中可读。
2. `main_window.py` — 方案应用成功后的回写链路增加异常捕获；若 `set_active_profile()`、`update_last_used()`、`profile_applied.emit()` 或随后的 UI 刷新失败，会把 traceback 写入 `%AppData%\NetSwitch\netswitch.log` 并弹出错误提示。
3. `main.py` — 增加全局 `sys.excepthook`，将未捕获异常写入日志，便于定位打包后的“直接退出”问题。

**遇到的问题**：
- 当前日志只能看到 `netsh ok` 和 `apply success`，无法直接定位后续 Python 层异常。
- 按钮样式如果只依赖默认系统主题，在白底布局上容易失去可读性。

**解决方式**：
- 通过显式样式统一按钮外观。
- 通过 `network_controller._log_error()` 输出 traceback，避免 windowed 程序吞掉异常信息。

**验证方式**：
- 运行 `PYTHONDONTWRITEBYTECODE=1 python -B -m py_compile main.py main_window.py edit_dialog.py settings_dialog.py tray.py profile_manager.py network_controller.py scripts/build.py scripts/generate_icon.py`。

**验证结果**：
- 静态编译通过。
- 未执行真实网络切换，原因是会修改本机网络配置。

**本地产物清理**：
- 本轮未生成构建产物。

## 2026-05-24（二次复核确认问题修复）

**触发原因**：用户确认继续执行本轮复核后的修复，要求先记录，再修改代码。本轮重点补齐单实例隐藏窗口引用保留、自启状态同步、合法子网掩码校验、配置原子写和 release 版本一致性检查。

**修改内容**：
1. `main.py` — 启动时以注册表真实状态为准，同步回 `profiles.json`，避免托盘与设置弹窗显示不一致；窗口关闭到托盘后保留主窗口引用，不再主动清空。
2. `edit_dialog.py`、`network_controller.py` — 子网掩码改为连续 1 的合法掩码校验，阻止 `1.2.3.4` 这类非法值保存。
3. `profile_manager.py` — `profiles.json` 采用临时文件写入后 `os.replace()` 原子替换，降低损坏风险。
4. `scripts/build.py` — 在打包前校验 `VERSION` 与 Git tag 版本一致，避免 Release 产物文件名和上传路径不匹配。
5. `project-log/05-current-status.md`、`project-log/01-function-design.md`、`project-log/03-api-design.md`、`project-log/10-planning-log.md`、`project-log/11-code-review-log.md` — 同步更新本轮复核结果和旧文档内容。

**遇到的问题**：
- 需要区分“窗口隐藏后保留引用”和“窗口真的关闭销毁”两种生命周期语义，避免单实例唤起再次失效。
- 版本一致性检查需要兼容本地开发运行和 GitHub Actions tag 发布两种场景。

**解决方式**：
- 主窗口关闭到托盘时只隐藏不销毁实例引用，由应用层统一管理生命周期。
- 版本校验只在 tag 发布上下文启用，普通本地构建不受影响。

**验证方式**：
- 运行 `PYTHONDONTWRITEBYTECODE=1 python -B -m py_compile main.py main_window.py edit_dialog.py settings_dialog.py tray.py profile_manager.py network_controller.py scripts/build.py scripts/generate_icon.py`。

**验证结果**：
- 静态编译通过。
- 未执行真实网络切换，原因是会修改本机网络配置。

**本地产物清理**：
- 本轮未生成构建产物。

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
8. `VERSION`、`pyproject.toml`、`uv.lock` — 版本号推进到 `1.4.0`。
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

## 2026-06-05（复核分类与确认项优化）

**触发原因**：用户要求对上一轮分析的每一条重新判断是 bug 还是优化点，确认成立后直接优化掉。

**修改内容**：
1. `main.py` — 新增 `_RestoreProfileWorker`，把开机恢复上次方案改为后台执行，避免启动阶段同步执行网络切换阻塞 UI。
2. `network_controller.py` — 默认网卡识别改为优先使用 `route print` 的接口 IP；读取当前 IP / 掩码 / DHCP / DNS / 网关时按 adapter IP 精确查询，降低同一网卡多 IPv4 取错配置的风险。
3. `main_window.py` — 删除当前激活方案前切回 DHCP 若返回 warning，会提示用户当前网络异常；保存窗口坐标越界时显式居中到主屏幕。
4. `project-log/11-code-review-log.md` — 追加 F 轮评审，区分已确认问题和待确认问题。
5. `project-log/05-current-status.md` — 更新当前状态、待处理项、未解决问题和任务交接。
6. `project-log/01-function-design.md`、`project-log/04-project-architecture.md` — 同步状态检测、默认路由识别和单实例唤起等已变化描述。
7. `main.py` — 复查时补充退出保护，网络切换 / 开机恢复未完成时提示等待，避免 QThread 运行中退出应用。

**遇到的问题**：
- 真实 DHCP / 静态 IP 切换、多 IPv4 网卡和内置更新安装流程都需要 Windows 实机环境，本轮只能做静态验证。
- 无默认网关静态 IP 是否正式支持属于产品决策，未擅自改变输入规则。

**解决方式**：
- 只修复确认成立且范围可控的问题；需要实机或产品判断的项目保留为待确认。

**验证方式**：
- 运行 `PYTHONDONTWRITEBYTECODE=1 python -B -m py_compile main.py main_window.py edit_dialog.py settings_dialog.py tray.py profile_manager.py network_controller.py update_manager.py scripts/build.py scripts/generate_icon.py`。
- 运行不触网的 monkeypatch 脚本验证 `network_controller.get_default_adapter_ip()` 按默认路由 metric 选择接口 IP，并验证 `get_current_ip_config(adapter_ip)` 按指定 IP 精确读取配置。
- 运行 `git diff --check` 检查行尾空格等提交前格式问题。

**验证结果**：
- 静态编译通过。
- 不触网函数级检查通过。
- `git diff --check` 通过。
- 未执行真实 DHCP / 静态 IP 切换，原因是会修改本机网络配置。

**本地产物清理**：
- 已删除本轮静态编译产生的 `__pycache__/` 和 `scripts/__pycache__/`。

---

## 2026-06-05（发布 v1.4.2）

**触发原因**：用户要求在确认 bug 修复后推进一个新版本，并上传到 GitHub 触发新版本构建。

**修改内容**：
1. `VERSION` — 版本号从 `1.4.1` 推进到 `1.4.2`。
2. `pyproject.toml` — 项目版本同步为 `1.4.2`。
3. `project-log/05-current-status.md` — 当前版本更新为 V1.4.2，并记录本版包含开机恢复后台化、多 IPv4 精确读取、删除 warning 提示、窗口越界居中和退出保护。
4. `project-log/07-deployment.md` — 同步 Release 流程中的 SHA-256 校验文件上传，移除 README 构建命令的过期已知问题。

**遇到的问题**：
- 当前本地没有 `v1.4.1` tag，但代码版本已是 `1.4.1`；本轮按补丁版本推进到 `1.4.2` 并计划创建 `v1.4.2` tag。

**解决方式**：
- 提交版本号和文档更新后，推送 `main` 和 `v1.4.2` tag；`.github/workflows/release.yml` 会在 tag push 时触发构建和 Release 创建。

**验证方式**：
- 运行 `PYTHONDONTWRITEBYTECODE=1 python -B -m py_compile main.py main_window.py edit_dialog.py settings_dialog.py tray.py profile_manager.py network_controller.py update_manager.py scripts/build.py scripts/generate_icon.py`。
- 运行不触网的 monkeypatch 脚本验证 `network_controller.get_default_adapter_ip()` 和 `get_current_ip_config(adapter_ip)` 的关键读取行为。
- 运行 `git diff --check`。

**验证结果**：
- 静态编译通过。
- 不触网函数级检查通过。
- 版本一致性检查通过：`VERSION`、`pyproject.toml` 和 `project-log/05-current-status.md` 均为 `1.4.2` / V1.4.2。
- `git diff --check` 通过。
- 未执行真实 DHCP / 静态 IP 切换，原因是会修改本机网络配置。

**本地产物清理**：
- 已删除本轮静态编译产生的 `__pycache__/` 和 `scripts/__pycache__/`。

---

<!-- 新记录追加在上方分隔线之后、旧记录之前 -->
