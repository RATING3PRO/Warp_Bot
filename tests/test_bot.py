from __future__ import annotations

from bot import TELEGRAM_MESSAGE_LIMIT, _markdown_config_messages
from warp import WarpConfigResult


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
