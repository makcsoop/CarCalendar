"""Удаление старых сообщений бота, чтобы чат не забивался."""
from __future__ import annotations

import logging
from typing import Any

from telebot import TeleBot
from telebot.states.sync.context import StateContext

log = logging.getLogger(__name__)

DEFAULT_MAX_KEEP = 7


def _get_ids(state: StateContext) -> list[int]:
    with state.data() as data:
        raw = data.get("bot_msg_ids")
        if not raw:
            return []
        return list(raw)


def _set_ids(state: StateContext, ids: list[int]) -> None:
    """Сохраняет id сообщений бота. Без активного FSM-ключа storage падает — игнорируем."""
    try:
        state.add_data(bot_msg_ids=ids)
    except RuntimeError as e:
        if "does not exist" not in str(e):
            raise


def purge_tracked(bot: TeleBot, chat_id: int, state: StateContext) -> None:
    for mid in _get_ids(state):
        try:
            bot.delete_message(chat_id, mid)
        except Exception as e:  # noqa: BLE001
            log.debug("delete_message %s: %s", mid, e)
    _set_ids(state, [])


def send_tracked(
    bot: TeleBot,
    chat_id: int,
    state: StateContext,
    text: str,
    *,
    max_keep: int = DEFAULT_MAX_KEEP,
    **kwargs: Any,
):
    ids = _get_ids(state)
    while len(ids) >= max_keep:
        old = ids.pop(0)
        try:
            bot.delete_message(chat_id, old)
        except Exception as e:  # noqa: BLE001
            log.debug("delete_message %s: %s", old, e)
    msg = bot.send_message(chat_id, text, **kwargs)
    ids.append(msg.message_id)
    _set_ids(state, ids)
    return msg


def delete_callback_message(bot: TeleBot, chat_id: int, message_id: int | None) -> None:
    if message_id is None:
        return
    try:
        bot.delete_message(chat_id, message_id)
    except Exception as e:  # noqa: BLE001
        log.debug("delete_callback_message: %s", e)
