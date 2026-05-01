# Warp Bot

一个 Telegram Bot，用于申请 Cloudflare WARP WireGuard 配置文件，并把 `.conf` 文件发送给用户。

> 注意：这里使用的是 Cloudflare WARP 客户端注册接口。它不是面向第三方公开承诺稳定性的 API，Cloudflare 变更接口后可能需要更新代码。

## 功能

- `/warp` 自动生成 WireGuard X25519 密钥对
- 向 Cloudflare WARP 注册设备
- 渲染 WireGuard `.conf` 配置文件
- 通过 Telegram 文档消息返回配置
- 可选 `ALLOWED_USER_IDS` 白名单限制使用者

## 准备

1. 在 Telegram 找 `@BotFather` 创建 Bot，并拿到 token。
2. 安装 Python 3.9+（推荐 Python 3.11+）。
3. 安装依赖：

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

4. 创建 `.env`：

```powershell
Copy-Item .env.example .env
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

```powershell
python bot.py
```

Bot 启动后，在 Telegram 中发送：

```text
/warp
```

## 部署建议

- 不要提交 `.env`。
- 建议设置 `ALLOWED_USER_IDS`，避免 Bot 被公开滥用。
- WARP 配置文件包含 WireGuard 私钥，不要公开转发或存档到公共日志。

## 测试

```powershell
pytest
```
