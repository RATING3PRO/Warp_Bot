# Warp Bot

一个 Telegram Bot，用于申请 Cloudflare WARP WireGuard / Xray 配置文件，并把配置文件发送给用户。

> 注意：这里使用的是 Cloudflare WARP 客户端注册接口。它不是面向第三方公开承诺稳定性的 API，Cloudflare 变更接口后可能需要更新代码。

## 功能

- `/warp` 自动生成同一套 WARP 配置对应的 WireGuard `.conf` 和 Xray `.json` 两个文件
- `/wg` 只生成 WireGuard `.conf` 配置文件
- `/xray` 只生成可粘贴到 Xray `outbounds` 数组中的 WireGuard outbound 对象
- 向 Cloudflare WARP 注册设备
- 渲染 WireGuard `.conf` 或 Xray outbound `.json` 配置文件
- 启动时向 Telegram 注册 `/warp`、`/wg`、`/xray`、`/help` 命令菜单
- 通过 Telegram Markdown 代码块和文档消息同时返回配置
- 可选 `ALLOWED_USER_IDS` 白名单限制使用者

## 准备

1. 在 Telegram 找 `@BotFather` 创建 Bot，并拿到 token。
2. 安装 Python 3.12+ 和 [uv](https://docs.astral.sh/uv/)。
3. 安装依赖：

```bash
uv sync
```

4. 创建 `.env`：

```bash
cp .env.example .env
```

然后编辑 `.env`：

```dotenv
TELEGRAM_BOT_TOKEN=你的BotToken
ALLOWED_USER_IDS=123456789
WARP_API_TIMEOUT=20
# 如果服务器访问 Telegram 或 Cloudflare 需要代理，可添加：
# HTTPS_PROXY=http://127.0.0.1:7890
# HTTP_PROXY=http://127.0.0.1:7890
```

`ALLOWED_USER_IDS` 留空表示任何能找到这个 Bot 的用户都能申请配置。

## 运行

### 本地运行

```bash
uv run python bot.py
```

Bot 启动后，在 Telegram 中发送：

```text
/warp
/wg
/xray
```

`/warp` 和 `/xray` 返回的 Xray JSON 不是完整 Xray 客户端配置，只是 `outbounds` 数组中的一个 outbound 对象。

### Docker 运行

Docker 镜像不需要 `.env` 文件，直接通过容器环境变量注入配置：

```bash
docker run -d \
  --name warp-bot \
  --restart unless-stopped \
  -e TELEGRAM_BOT_TOKEN=你的BotToken \
  -e ALLOWED_USER_IDS=123456789,987654321 \
  -e WARP_API_TIMEOUT=20 \
  ghcr.io/rating3pro/warp_bot:latest
```

如果服务器访问 Telegram 或 Cloudflare 需要代理：

```bash
docker run -d \
  --name warp-bot \
  --restart unless-stopped \
  -e TELEGRAM_BOT_TOKEN=你的BotToken \
  -e HTTPS_PROXY=http://127.0.0.1:7890 \
  -e HTTP_PROXY=http://127.0.0.1:7890 \
  ghcr.io/rating3pro/warp_bot:latest
```

本仓库提供的 GitHub Workflow 会发布镜像到：

```text
ghcr.io/rating3pro/warp_bot
```

触发条件：

- push 到 `main`
- push `v*.*.*` tag
- 手动运行 `workflow_dispatch`

发布前确认仓库的 Actions 权限允许写入 Packages。使用 workflow 默认的 `GITHUB_TOKEN`，不需要额外配置 GHCR token。

## 部署建议

- 不要提交 `.env`。
- 建议设置 `ALLOWED_USER_IDS`，避免 Bot 被公开滥用。
- WARP 配置文件包含 WireGuard 私钥，不要公开转发或存档到公共日志。

## 测试

```bash
uv run pytest
```