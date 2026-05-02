from __future__ import annotations

import asyncio

from bot import TELEGRAM_MESSAGE_LIMIT, _markdown_config_messages, _reply_unauthorized
from warp import WarpConfigResult


class FakeMessage:
    def __init__(self) -> None:
        self.texts: list[str] = []

    async def reply_text(self, text: str) -> None:
        self.texts.append(text)


def test_markdown_config_messages_fit_telegram_limit() -> None:
    result = WarpConfigResult(
        config="a" * (TELEGRAM_MESSAGE_LIMIT + 500),
        filename="warp_test.conf",
        device_id="test",
    )

    messages = _markdown_config_messages(result)

    assert len(messages) > 1
    assert all(len(message) <= TELEGRAM_MESSAGE_LIMIT for message in messages)
    assert all("```" in message for message in messages)


def test_markdown_config_messages_include_filename_and_config() -> None:
    result = WarpConfigResult(
        config="[Interface]\nPrivateKey = test\n",
        filename="wg_test.conf",
        device_id="test",
    )

    messages = _markdown_config_messages(result)

    assert messages == ["`wg_test.conf`\n```\n[Interface]\nPrivateKey = test\n\n```"]


def test_reply_unauthorized_includes_user_id() -> None:
    message = FakeMessage()

    asyncio.run(_reply_unauthorized(message, 123456789))

    assert message.texts == ["你没有权限使用这个 Bot。\n用户ID：123456789"]
