# 环境配置

> **最后更新**：2026-05-22

## 环境要求

| 项目 | 版本 | 说明 |
|------|------|------|
| Windows | 10/11 | 目标运行系统，主要面向 Windows 11 |
| Python | 3.12 | `pyproject.toml` 要求 `>=3.12,<3.13` |
| uv | 最新稳定版 | 依赖安装和运行 |
| PyQt6 | 锁定在 `uv.lock` | GUI 运行依赖 |
| PyInstaller | dev 依赖 | 打包 exe |
| Pillow | dev 依赖 | 构建期生成图标 |
| Inno Setup | 6.x | 生成安装包 |

## 环境变量

不适用。当前项目没有 `.env`、第三方密钥或服务连接串。

## 敏感信息规则

- 不要把真实 token、password、private key、cookie 或连接串密码写入 `project-log/`。
- 本项目当前无第三方密钥；如后续引入自动更新、错误上报等服务，需要新增 `.env.example` 或安全配置说明。
- `profiles.json` 可能包含用户真实内网 IP、网关和 DNS，提交 issue 或日志时应注意脱敏。

## 第三方服务

当前不依赖外部服务。

## 本地开发配置

```bash
git clone https://github.com/MoeMoeGit/NetSwitch.git
cd NetSwitch
uv sync
uv run python main.py
```

注意：

- 运行修改网络配置的功能需要管理员权限。
- 开发时直接运行 `python main.py` 不会自动提权；打包后的 exe 通过 manifest 请求 UAC。
- `project-log/` 当前被 `.gitignore` 忽略，是本地开发知识库。

## 变更记录

| 日期 | 变更内容 | 原因 |
|------|----------|------|
| 2026-05-22 | 补齐桌面应用环境配置 | 恢复 project-log |
