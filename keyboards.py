"""Клавиатуры Telegram."""
from __future__ import annotations

from datetime import date as Date, datetime

from telebot import types

from config import TIME_SLOTS


def main_menu() -> types.ReplyKeyboardMarkup:
    kb = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    kb.add(
        types.KeyboardButton("📝 Новая запись"),
        types.KeyboardButton("📊 Отчёты"),
    )
    kb.add(
        types.KeyboardButton("📋 Статус записи"),
        types.KeyboardButton("⚙️ Настройки"),
    )
    return kb


def cancel_reply() -> types.ReplyKeyboardMarkup:
    kb = types.ReplyKeyboardMarkup(resize_keyboard=True)
    kb.add(types.KeyboardButton("⏹️ Отмена"))
    return kb


def skip_or_cancel_reply() -> types.ReplyKeyboardMarkup:
    kb = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    kb.add(types.KeyboardButton("⏭️ Пропустить"), types.KeyboardButton("⏹️ Отмена"))
    return kb


def services_inline(
    service_catalog: list[tuple[str, list[str]]],
    *,
    prefix: str = "svc",
    selected: set[str] | None = None,
    active_section_idx: int | None = None,
) -> tuple[types.InlineKeyboardMarkup, list[str]]:
    kb = types.InlineKeyboardMarkup(row_width=2)
    selected = selected or set()
    options: list[str] = []
    option_idx = 0

    is_section_mode = active_section_idx is not None and 0 <= active_section_idx < len(service_catalog)
    if is_section_mode:
        section_name, services = service_catalog[active_section_idx]
        kb.row(types.InlineKeyboardButton(f"📂 {section_name}", callback_data=f"{prefix}:noop"))
        for service_name in services:
            marker = "🟩" if service_name in selected else "⬜"
            label = f"{marker} {service_name}"
            if len(label) > 64:
                label = (service_name if len(service_name) <= 64 else service_name[:61] + "…")
            kb.add(types.InlineKeyboardButton(label, callback_data=f"{prefix}:{option_idx}"))
            options.append(service_name)
            option_idx += 1
        nav: list[types.InlineKeyboardButton] = []
        if active_section_idx > 0:
            nav.append(
                types.InlineKeyboardButton("◀️ Назад", callback_data=f"{prefix}:nav:{active_section_idx - 1}")
            )
        if active_section_idx < len(service_catalog) - 1:
            nav.append(
                types.InlineKeyboardButton("Вперёд ▶️", callback_data=f"{prefix}:nav:{active_section_idx + 1}")
            )
        if nav:
            kb.row(*nav)
        kb.row(types.InlineKeyboardButton("🔙 К разделам", callback_data=f"{prefix}:all"))
    else:
        for sec_idx, (section_name, services) in enumerate(service_catalog):
            kb.row(types.InlineKeyboardButton(f"📂 {section_name}", callback_data=f"{prefix}:sec:{sec_idx}"))

    kb.row(types.InlineKeyboardButton(f"✅ Готово ({len(selected)})", callback_data=f"{prefix}:done"))
    kb.row(
        types.InlineKeyboardButton("➕ Добавить раздел", callback_data=f"{prefix}:addsec"),
        types.InlineKeyboardButton("➕ Добавить услугу", callback_data=f"{prefix}:addsvc"),
    )
    kb.row(types.InlineKeyboardButton("⏭️ Пропустить", callback_data="skp:sv"))
    return kb, options


def _parse_slot_hhmm(slot: str) -> tuple[int, int] | None:
    try:
        h_s, m_s = slot.split(":")
        return int(h_s), int(m_s)
    except Exception:
        return None


def time_inline(*, booking_date: str | Date | None = None, now: datetime | None = None) -> types.InlineKeyboardMarkup:
    kb = types.InlineKeyboardMarkup(row_width=3)
    now = now or datetime.now()

    target: Date | None = None
    if isinstance(booking_date, Date):
        target = booking_date
    elif isinstance(booking_date, str) and booking_date:
        try:
            target = Date.fromisoformat(booking_date)
        except ValueError:
            target = None

    slots: list[str] = list(TIME_SLOTS)
    if target is not None and target == now.date():
        filtered: list[str] = []
        for s in slots:
            if s == "Другое":
                continue
            hm = _parse_slot_hhmm(s)
            if hm is None:
                continue
            h, m = hm
            if (h, m) > (now.hour, now.minute):
                filtered.append(s)
        if "Другое" in slots:
            filtered.append("Другое")
        slots = filtered

    row: list[types.InlineKeyboardButton] = []
    for t in slots:
        if t == "Другое":
            label = "✏️ Другое"
            cb = "tmv:other"
        else:
            label = f"🕐 {t}"
            cb = f"tmv:{t}"
        row.append(types.InlineKeyboardButton(label, callback_data=cb))
        if len(row) == 3:
            kb.row(*row)
            row = []
    if row:
        kb.row(*row)
    kb.row(types.InlineKeyboardButton("⏭️ Пропустить", callback_data="skp:tm"))
    return kb


def date_inline(prefix: str = "dt") -> types.InlineKeyboardMarkup:
    kb = types.InlineKeyboardMarkup(row_width=2)
    kb.add(
        types.InlineKeyboardButton("📅 Сегодня", callback_data=f"{prefix}:0"),
        types.InlineKeyboardButton("📆 Завтра", callback_data=f"{prefix}:1"),
    )
    kb.add(types.InlineKeyboardButton("🗓 Послезавтра", callback_data=f"{prefix}:2"))
    kb.add(types.InlineKeyboardButton("✍️ Ввести дату текстом", callback_data=f"{prefix}:9"))
    kb.row(types.InlineKeyboardButton("⏭️ Пропустить", callback_data="skp:dt"))
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
    kb.add(types.InlineKeyboardButton("✏️ Своя модель", callback_data=f"{prefix}:c"))
    kb.add(types.InlineKeyboardButton("⏭️ Пропустить", callback_data="skp:md"))
    return kb


def confirm_inline() -> types.InlineKeyboardMarkup:
    kb = types.InlineKeyboardMarkup(row_width=2)
    kb.add(
        types.InlineKeyboardButton("✅ Подтвердить", callback_data="cf:ok"),
        types.InlineKeyboardButton("✏️ Изменить", callback_data="cf:ed"),
    )
    kb.add(types.InlineKeyboardButton("🗑 Отменить черновик", callback_data="cf:xx"))
    return kb


def edit_field_inline() -> types.InlineKeyboardMarkup:
    kb = types.InlineKeyboardMarkup(row_width=2)
    fields = [
        ("👤 Имя", "nm"),
        ("📞 Телефон", "ph"),
        ("🚗 Авто", "cr"),
        ("🧰 Услуга", "sv"),
        ("📅 Дата/время", "dt"),
    ]
    for label, code in fields:
        kb.add(types.InlineKeyboardButton(label, callback_data=f"ed:{code}"))
    kb.add(types.InlineKeyboardButton("🔙 Назад к проверке", callback_data="ed:back"))
    return kb


def report_menu_inline() -> types.InlineKeyboardMarkup:
    kb = types.InlineKeyboardMarkup(row_width=1)
    opts = [
        ("📈 Записей на этой неделе", "rp:w"),
        ("🌅 Все записи на завтра", "rp:tm"),
        ("✅ Выполнено сегодня", "rp:cd"),
        ("📊 За текущий месяц (сводка)", "rp:mo"),
        ("🚗 Частые авто (приходят и обрабатываются)", "rp:ca"),
        ("🚶 Не пришли за 2 недели", "rp:ns"),
        ("📂 Незакрытые и отменённые", "rp:op"),
        ("👥 Новые / повторные клиенты (месяц)", "rp:st"),
        ("💬 Свой запрос текстом", "rp:tx"),
    ]
    for label, data in opts:
        kb.add(types.InlineKeyboardButton(text=label, callback_data=data))
    return kb


def status_pick_booking(booking_id: int) -> types.InlineKeyboardMarkup:
    kb = types.InlineKeyboardMarkup(row_width=2)
    kb.add(
        types.InlineKeyboardButton("✅ Выполнена", callback_data=f"st:{booking_id}:done"),
        types.InlineKeyboardButton("📆 Перенесена", callback_data=f"st:{booking_id}:resched"),
    )
    kb.add(
        types.InlineKeyboardButton("🚫 Не пришёл", callback_data=f"st:{booking_id}:noshow"),
        types.InlineKeyboardButton("❌ Отменить запись", callback_data=f"st:{booking_id}:cancel"),
    )
    return kb


def status_booking_mode_inline() -> types.InlineKeyboardMarkup:
    """Выбор раздела: предстоящие / завершённые."""
    kb = types.InlineKeyboardMarkup(row_width=1)
    kb.add(
        types.InlineKeyboardButton("📅 Предстоящие записи", callback_data="slm:u"),
        types.InlineKeyboardButton("✅ Завершённые записи", callback_data="slm:c"),
    )
    return kb


def bookings_carousel_inline(
    mode: str,
    page: int,
    per_page: int,
    total_count: int,
    items: list[tuple[int, str]],
) -> types.InlineKeyboardMarkup:
    """mode: 'u' — предстоящие, 'c' — завершённые. Карусель по страницам."""
    kb = types.InlineKeyboardMarkup(row_width=1)
    for bid, title in items:
        kb.add(types.InlineKeyboardButton(text=title[:64], callback_data=f"bk:{bid}"))
    total_pages = max(1, (total_count + per_page - 1) // per_page) if total_count else 1
    page = max(0, min(page, total_pages - 1))
    if total_pages > 1:
        nav: list[types.InlineKeyboardButton] = []
        if page > 0:
            nav.append(
                types.InlineKeyboardButton("◀️ Назад", callback_data=f"bpg:{mode}:{page - 1}")
            )
        nav.append(
            types.InlineKeyboardButton(
                f"📄 {page + 1}/{total_pages}",
                callback_data=f"bpi:{mode}:{page}",
            )
        )
        if page < total_pages - 1:
            nav.append(
                types.InlineKeyboardButton("Вперёд ▶️", callback_data=f"bpg:{mode}:{page + 1}")
            )
        kb.row(*nav)
    kb.row(types.InlineKeyboardButton("🔙 К разделам", callback_data="slm:menu"))
    return kb


def catalog_settings_root_inline() -> types.InlineKeyboardMarkup:
    kb = types.InlineKeyboardMarkup(row_width=1)
    kb.add(
        types.InlineKeyboardButton("🗑 Удалить сохранённую марку", callback_data="cd:delbr"),
        types.InlineKeyboardButton("🗑 Удалить сохранённую модель", callback_data="cd:delmd"),
        types.InlineKeyboardButton("✖️ Закрыть", callback_data="cd:close"),
    )
    return kb


def catalog_saved_brands_delete_inline(brands: list[str]) -> types.InlineKeyboardMarkup:
    kb = types.InlineKeyboardMarkup(row_width=1)
    for i, b in enumerate(brands):
        short = b if len(b) <= 40 else b[:37] + "…"
        kb.add(types.InlineKeyboardButton(f"🗑 {short}", callback_data=f"cd:db:{i}"))
    kb.add(types.InlineKeyboardButton("🔙 Назад", callback_data="cd:home"))
    return kb


def catalog_brands_for_models_delete_inline(brands: list[str]) -> types.InlineKeyboardMarkup:
    kb = types.InlineKeyboardMarkup(row_width=1)
    for i, b in enumerate(brands):
        short = b if len(b) <= 40 else b[:37] + "…"
        kb.add(types.InlineKeyboardButton(short, callback_data=f"cd:mb:{i}"))
    kb.add(types.InlineKeyboardButton("🔙 Назад", callback_data="cd:home"))
    return kb


def catalog_models_delete_inline(brand_idx: int, models: list[str]) -> types.InlineKeyboardMarkup:
    kb = types.InlineKeyboardMarkup(row_width=1)
    for mi, m in enumerate(models):
        short = m if len(m) <= 36 else m[:33] + "…"
        kb.add(
            types.InlineKeyboardButton(
                f"🗑 {short}", callback_data=f"cd:dm:{brand_idx}:{mi}"
            )
        )
    kb.add(types.InlineKeyboardButton("🔙 К маркам", callback_data="cd:delmd"))
    return kb
