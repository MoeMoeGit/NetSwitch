# 部署 / 打包

> **最后更新**：2026-05-22

## 部署环境

| 环境 | 用途 | 地址 |
|------|------|------|
| 本地开发 | 运行和调试 PyQt6 应用 | 开发者 Windows 机器 |
| GitHub Actions | tag 发布时构建 exe 和安装包 | `.github/workflows/` |
| 生产分发 | GitHub Releases 下载 exe / 安装包 | GitHub Release 页面 |

## 前置条件

- Windows 10/11。
- Python 3.12。
- `uv` 包管理器。
- Inno Setup 6，用于构建安装包。
- 修改网络配置需要管理员权限；打包 exe 通过 manifest 请求 UAC。

## 本地构建流程

```bash
uv sync
uv run python scripts/generate_icon.py
uv run python scripts/build.py
iscc scripts/installer_output.iss
```

产物：

- `dist/NetSwitch.exe`
- `installer_output/NetSwitch-Setup-<version>.exe`

注意：`scripts/build.py` 会从 `scripts/installer.iss` 模板生成 `scripts/installer_output.iss`，因此构建安装包应使用生成后的文件。

## CI/CD

GitHub Actions 触发条件：

```yaml
on:
  push:
    tags:
      - "v*"
```

流程：

1. Checkout。
2. 安装 uv 和 Python 3.12。
3. `uv sync`。
4. 生成图标。
5. 运行 PyInstaller 打包 exe。
6. 安装 Inno Setup。
7. 构建安装包。
8. 创建 GitHub Release 并上传 exe / setup。

## 历史发布问题

- 旧版本 Release 曾只上传便携版 `NetSwitch.exe`，没有生成安装包。当前 `.github/workflows/release.yml` 已包含安装 Inno Setup、编译 `scripts/installer_output.iss`、上传 `installer_output/NetSwitch-Setup-<version>.exe` 的步骤。
- 修改 CI 时必须确认 Release 同时包含便携版 exe 和安装包。

## 回滚方案

- Release 分发异常时，删除或标记对应 GitHub Release。
- 用户侧可卸载安装包版本，改用上一个 Release 的安装包或便携版 exe。
- 配置文件位于 `%AppData%\NetSwitch\profiles.json`，卸载应用不应默认删除用户配置。

## 已知问题

- README 当前构建安装包命令需要同步修正为 `iscc scripts/installer_output.iss`。
- 安装包可选开机自启写入 HKCU Run；应用内也可通过托盘或设置弹窗切换开机自启。

## 变更记录

| 日期 | 变更内容 | 原因 |
|------|----------|------|
| 2026-05-22 | 补齐桌面应用打包和发布流程 | 恢复 project-log |
