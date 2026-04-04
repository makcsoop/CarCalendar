"""Клавиатуры Telegram."""
from __future__ import annotations

from telebot import types

from config import MASTERS, SERVICES, TIME_SLOTS


def main_menu() -> types.ReplyKeyboardMarkup:
    kb = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    kb.add(
        types.KeyboardButton("Новая запись"),
        types.KeyboardButton("Отчёты"),
    )
    kb.add(
        types.KeyboardButton("Статус записи"),
        types.KeyboardButton("Помощь"),
    )
    return kb


def cancel_reply() -> types.ReplyKeyboardMarkup:
    kb = types.ReplyKeyboardMarkup(resize_keyboard=True)
    kb.add(types.KeyboardButton("Отмена"))
    return kb


def services_inline(prefix: str = "svc") -> types.InlineKeyboardMarkup:
    kb = types.InlineKeyboardMarkup(row_width=2)
    for i, s in enumerate(SERVICES):
        kb.add(types.InlineKeyboardButton(s, callback_data=f"{prefix}:{i}"))
    return kb


def masters_inline(prefix: str = "mst") -> types.InlineKeyboardMarkup:
    kb = types.InlineKeyboardMarkup(row_width=2)
    for i, m in enumerate(MASTERS):
        kb.add(types.InlineKeyboardButton(m, callback_data=f"{prefix}:{i}"))
    return kb


def time_inline(prefix: str = "tm") -> types.InlineKeyboardMarkup:
    kb = types.InlineKeyboardMarkup(row_width=3)
    row: list[types.InlineKeyboardButton] = []
    for i, t in enumerate(TIME_SLOTS):
        row.append(types.InlineKeyboardButton(t, callback_data=f"{prefix}:{i}"))
        if len(row) == 3:
            kb.row(*row)
            row = []
    if row:
        kb.row(*row)
    return kb


def date_inline(prefix: str = "dt") -> types.InlineKeyboardMarkup:
    kb = types.InlineKeyboardMarkup(row_width=2)
    kb.add(
        types.InlineKeyboardButton("Сегодня", callback_data=f"{prefix}:0"),
        types.InlineKeyboardButton("Завтра", callback_data=f"{prefix}:1"),
    )
    kb.add(types.InlineKeyboardButton("Послезавтра", callback_data=f"{prefix}:2"))
    kb.add(types.InlineKeyboardButton("Ввести дату текстом", callback_data=f"{prefix}:9"))
    return kb


def brands_inline(brands: list[str], prefix: str = "br") -> types.InlineKeyboardMarkup:
    kb = types.InlineKeyboardMarkup(row_width=3)
    for i, b in enumerate(brands):
        label = b if len(b) <= 36 else b[:33] + "…"
        kb.add(types.InlineKeyboardButton(label, callback_data=f"{prefix}:{i}"))
    return kb


def models_inline(models: list[str], prefix: str = "md") -> types.InlineKeyboardMarkup:
    """Индексы md:0 … md:N-1, md:c — своя модель."""
    kb = types.InlineKeyboardMarkup(row_width=2)
    shown = models[:20]
    for i, m in enumerate(shown):
        label = m if len(m) <= 40 else m[:37] + "…"
        kb.add(types.InlineKeyboardButton(label, callback_data=f"{prefix}:{i}"))
    kb.add(types.InlineKeyboardButton("Своя модель", callback_data=f"{prefix}:c"))
    return kb


def confirm_inline() -> types.InlineKeyboardMarkup:
    kb = types.InlineKeyboardMarkup(row_width=2)
    kb.add(
        types.InlineKeyboardButton("Подтвердить", callback_data="cf:ok"),
        types.InlineKeyboardButton("Изменить", callback_data="cf:ed"),
    )
    kb.add(types.InlineKeyboardButton("Отменить запись", callback_data="cf:xx"))
    return kb


def edit_field_inline() -> types.InlineKeyboardMarkup:
    kb = types.InlineKeyboardMarkup(row_width=2)
    fields = [
        ("Имя", "nm"),
        ("Телефон", "ph"),
        ("Авто", "cr"),
        ("Госномер", "gp"),
        ("Услуга", "sv"),
        ("Дата/время", "dt"),
        ("Мастер", "ms"),
    ]
    for label, code in fields:
        kb.add(types.InlineKeyboardButton(label, callback_data=f"ed:{code}"))
    kb.add(types.InlineKeyboardButton("Назад к проверке", callback_data="ed:back"))
    return kb


def report_menu_inline() -> types.InlineKeyboardMarkup:
    kb = types.InlineKeyboardMarkup(row_width=1)
    opts = [
        ("Записей на этой неделе", "rp:w"),
        ("Все записи на завтра", "rp:tm"),
        ("Выполнено сегодня", "rp:cd"),
        ("За текущий месяц (сводка)", "rp:mo"),
        ("По мастеру (введите имя после кнопки)", "rp:ma"),
        ("Не пришли за 2 недели", "rp:ns"),
        ("Незакрытые и отменённые", "rp:op"),
        ("Новые / повторные клиенты (месяц)", "rp:st"),
        ("Свой запрос текстом", "rp:tx"),
    ]
    for label, data in opts:
        kb.add(types.InlineKeyboardButton(text=label, callback_data=data))
    return kb


def status_pick_booking(booking_id: int) -> types.InlineKeyboardMarkup:
    kb = types.InlineKeyboardMarkup(row_width=2)
    kb.add(
        types.InlineKeyboardButton("Выполнена", callback_data=f"st:{booking_id}:done"),
        types.InlineKeyboardButton("Перенесена", callback_data=f"st:{booking_id}:resched"),
    )
    kb.add(
        types.InlineKeyboardButton("Не пришёл", callback_data=f"st:{booking_id}:noshow"),
        types.InlineKeyboardButton("Отмена", callback_data=f"st:{booking_id}:cancel"),
    )
    return kb


def recent_bookings_inline(rows: list[tuple[int, str]]) -> types.InlineKeyboardMarkup:
    kb = types.InlineKeyboardMarkup(row_width=1)
    for bid, title in rows[:12]:
        kb.add(types.InlineKeyboardButton(text=title[:64], callback_data=f"bk:{bid}"))
    return kb
