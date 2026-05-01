from __future__ import annotations

import logging
import os
from io import BytesIO
from typing import Iterable

from dotenv import load_dotenv
from telegram import Update
from telegram.constants import ParseMode
from telegram.ext import Application, CommandHandler, ContextTypes

from warp import WarpRegistrationError, generate_warp_config


logger = logging.getLogger(__name__)


def _parse_allowed_user_ids(raw: str | None) -> set[int]:
    if not raw:
        return set()

    allowed: set[int] = set()
    for item in raw.split(","):
        item = item.strip()
        if not item:
            continue
        try:
            allowed.add(int(item))
        except ValueError as exc:
            raise ValueError(f"Invalid Telegram user ID in ALLOWED_USER_IDS: {item}") from exc
    return allowed


def _is_allowed(user_id: int | None, allowed_user_ids: Iterable[int]) -> bool:
    allowed = set(allowed_user_ids)
    return not allowed or (user_id is not None and user_id in allowed)


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if update.effective_message is None:
        return

    await update.effective_message.reply_text(
        "发送 /warp 申请一个 Cloudflare WARP WireGuard 配置文件。\n"
        "配置会以 .conf 文件返回，请自行妥善保管。",
    )


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if update.effective_message is None:
        return

    await update.effective_message.reply_text(
        "/warp - 申请新的 WARP WireGuard 配置文件\n"
        "/start - 查看说明\n"
        "/help - 查看命令",
    )


async def warp_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    message = update.effective_message
    if message is None:
        return

    allowed_user_ids: set[int] = context.application.bot_data["allowed_user_ids"]
    if not _is_allowed(update.effective_user.id if update.effective_user else None, allowed_user_ids):
        await message.reply_text("你没有权限使用这个 Bot。")
        return

    waiting = await message.reply_text("正在向 Cloudflare WARP 申请配置，请稍候...")

    try:
        result = await generate_warp_config(timeout=context.application.bot_data["warp_api_timeout"])
    except WarpRegistrationError as exc:
        logger.warning("WARP registration failed: %s", exc)
        await waiting.edit_text(f"申请失败：{exc}")
        return
    except Exception:
        logger.exception("Unexpected error while generating WARP config")
        await waiting.edit_text("申请失败：内部错误，请稍后重试。")
        return

    config_bytes = BytesIO(result.config.encode("utf-8"))
    config_bytes.name = result.filename

    caption = (
        "WARP WireGuard 配置已生成。\n"
        f"`Device ID: {result.device_id}`\n"
        "不要把配置文件或 PrivateKey 发给他人。"
    )
    await message.reply_document(
        document=config_bytes,
        filename=result.filename,
        caption=caption,
        parse_mode=ParseMode.MARKDOWN,
    )
    await waiting.delete()


def build_application() -> Application:
    load_dotenv()

    token = os.getenv("TELEGRAM_BOT_TOKEN")
    if not token:
        raise RuntimeError("TELEGRAM_BOT_TOKEN is required")

    allowed_user_ids = _parse_allowed_user_ids(os.getenv("ALLOWED_USER_IDS"))
    warp_api_timeout = float(os.getenv("WARP_API_TIMEOUT", "20"))

    application = Application.builder().token(token).build()
    application.bot_data["allowed_user_ids"] = allowed_user_ids
    application.bot_data["warp_api_timeout"] = warp_api_timeout

    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("warp", warp_command))
    return application


def main() -> None:
    logging.basicConfig(
        level=os.getenv("LOG_LEVEL", "INFO"),
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    build_application().run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
