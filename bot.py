from __future__ import annotations

import logging
import os
from io import BytesIO
from typing import Iterable

from dotenv import load_dotenv
from telegram import BotCommand, Update
from telegram.constants import ParseMode
from telegram.ext import Application, CommandHandler, ContextTypes

from warp import (
    WarpConfigResult,
    WarpRegistrationError,
    generate_warp_config_bundle,
    generate_wireguard_config,
    generate_xray_config,
)


logger = logging.getLogger(__name__)
TELEGRAM_MESSAGE_LIMIT = 4096


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


async def _reply_unauthorized(message, user_id: int | None) -> None:
    user_id_text = str(user_id) if user_id is not None else "unknown"
    await message.reply_text(f"你没有权限使用这个 Bot。\n用户ID：{user_id_text}")


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if update.effective_message is None:
        return

    await update.effective_message.reply_text(
        "/warp - WireGuard + Xray\n"
        "/wg - WireGuard\n"
        "/xray - Xray outbound\n"
        "/help - commands",
    )


def _markdown_config_messages(result: WarpConfigResult) -> list[str]:
    header = f"`{result.filename}`"
    prefix = "```\n"
    suffix = "\n```"
    available = TELEGRAM_MESSAGE_LIMIT - len(header) - len(prefix) - len(suffix) - 32
    if available <= 0:
        raise RuntimeError("Telegram message chunk size is too small")

    chunks = [result.config[index : index + available] for index in range(0, len(result.config), available)] or [""]
    if len(chunks) == 1:
        return [f"{header}\n{prefix}{chunks[0]}{suffix}"]

    return [
        f"{header} ({index}/{len(chunks)})\n{prefix}{chunk}{suffix}"
        for index, chunk in enumerate(chunks, start=1)
    ]


async def _reply_config(message, result: WarpConfigResult) -> None:
    for markdown in _markdown_config_messages(result):
        await message.reply_text(markdown, parse_mode=ParseMode.MARKDOWN)

    config_bytes = BytesIO(result.config.encode("utf-8"))
    config_bytes.name = result.filename

    await message.reply_document(
        document=config_bytes,
        filename=result.filename,
        caption=result.filename,
    )


async def warp_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    message = update.effective_message
    if message is None:
        return

    allowed_user_ids: set[int] = context.application.bot_data["allowed_user_ids"]
    user_id = update.effective_user.id if update.effective_user else None
    if not _is_allowed(user_id, allowed_user_ids):
        await _reply_unauthorized(message, user_id)
        return

    waiting = await message.reply_text("正在向 Cloudflare WARP 申请同配置文件，请稍候...")

    try:
        result = await generate_warp_config_bundle(timeout=context.application.bot_data["warp_api_timeout"])
    except WarpRegistrationError as exc:
        logger.warning("WARP registration failed: %s", exc)
        await waiting.edit_text(f"申请失败：{exc}")
        return
    except Exception:
        logger.exception("Unexpected error while generating WARP config")
        await waiting.edit_text("申请失败：内部错误，请稍后重试。")
        return

    await _reply_config(message, result.wireguard)
    await _reply_config(message, result.xray)
    await waiting.delete()


async def wg_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    message = update.effective_message
    if message is None:
        return

    allowed_user_ids: set[int] = context.application.bot_data["allowed_user_ids"]
    user_id = update.effective_user.id if update.effective_user else None
    if not _is_allowed(user_id, allowed_user_ids):
        await _reply_unauthorized(message, user_id)
        return

    waiting = await message.reply_text("正在向 Cloudflare WARP 申请 WireGuard 配置，请稍候...")

    try:
        result = await generate_wireguard_config(timeout=context.application.bot_data["warp_api_timeout"])
    except WarpRegistrationError as exc:
        logger.warning("WireGuard WARP registration failed: %s", exc)
        await waiting.edit_text(f"申请失败：{exc}")
        return
    except Exception:
        logger.exception("Unexpected error while generating WireGuard config")
        await waiting.edit_text("申请失败：内部错误，请稍后重试。")
        return

    await _reply_config(message, result)
    await waiting.delete()


async def xray_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    message = update.effective_message
    if message is None:
        return

    allowed_user_ids: set[int] = context.application.bot_data["allowed_user_ids"]
    user_id = update.effective_user.id if update.effective_user else None
    if not _is_allowed(user_id, allowed_user_ids):
        await _reply_unauthorized(message, user_id)
        return

    waiting = await message.reply_text("正在向 Cloudflare WARP 申请 Xray outbound，请稍候...")

    try:
        result = await generate_xray_config(timeout=context.application.bot_data["warp_api_timeout"])
    except WarpRegistrationError as exc:
        logger.warning("Xray WARP registration failed: %s", exc)
        await waiting.edit_text(f"申请失败：{exc}")
        return
    except Exception:
        logger.exception("Unexpected error while generating Xray config")
        await waiting.edit_text("申请失败：内部错误，请稍后重试。")
        return

    await _reply_config(message, result)
    await waiting.delete()


async def register_bot_commands(application: Application) -> None:
    await application.bot.set_my_commands(
        [
            BotCommand("warp", "生成 WireGuard + Xray 配置"),
            BotCommand("wg", "生成 WireGuard 配置"),
            BotCommand("xray", "生成 Xray outbound 配置"),
            BotCommand("help", "查看命令"),
        ]
    )


def build_application() -> Application:
    load_dotenv()

    token = os.getenv("TELEGRAM_BOT_TOKEN")
    if not token:
        raise RuntimeError("TELEGRAM_BOT_TOKEN is required")

    allowed_user_ids = _parse_allowed_user_ids(os.getenv("ALLOWED_USER_IDS"))
    warp_api_timeout = float(os.getenv("WARP_API_TIMEOUT", "20"))

    application = Application.builder().token(token).post_init(register_bot_commands).build()
    application.bot_data["allowed_user_ids"] = allowed_user_ids
    application.bot_data["warp_api_timeout"] = warp_api_timeout

    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("warp", warp_command))
    application.add_handler(CommandHandler("wg", wg_command))
    application.add_handler(CommandHandler("xray", xray_command))
    return application


def main() -> None:
    logging.basicConfig(
        level=os.getenv("LOG_LEVEL", "INFO"),
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    build_application().run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
