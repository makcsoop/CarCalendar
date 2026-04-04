#!/usr/bin/env python3
"""Telegram-бот записи детейлинга: SQLite + Яндекс.Календарь (CalDAV)."""
from __future__ import annotations

import logging
from datetime import date, datetime, timedelta
from typing import Any, Optional

import telebot
from telebot import custom_filters, types
from telebot.states import State, StatesGroup
from telebot.states.sync.context import StateContext
from telebot.states.sync.middleware import StateMiddleware
from telebot.storage import StateMemoryStorage

import car_catalog
import chat_ui
import database as db
import reports_engine
import yandex_calendar
from config import (
    ADMIN_TELEGRAM_IDS,
    BOT_TOKEN,
    BRAND_OTHER_LABEL,
    MASTERS,
    SERVICES,
    TIME_SLOTS,
)
from keyboards import (
    brands_inline,
    cancel_reply,
    confirm_inline,
    date_inline,
    edit_field_inline,
    main_menu,
    masters_inline,
    models_inline,
    recent_bookings_inline,
    report_menu_inline,
    services_inline,
    status_pick_booking,
    time_inline,
)
from reports_parser import ParsedReport, parse_report_message
from utils import combine_local_datetime, normalize_phone, parse_date_text, parse_time_text

logging.basicConfig(level=logging.INFO)
log = logging.getLogger(__name__)

if not BOT_TOKEN:
    raise SystemExit("Задайте BOT_TOKEN в .env")

state_storage = StateMemoryStorage()
bot = telebot.TeleBot(BOT_TOKEN, state_storage=state_storage, use_class_middlewares=True)


class BookingStates(StatesGroup):
    client_name = State()
    phone = State()
    car_brand = State()
    car_brand_text = State()
    car_model = State()
    car_model_custom = State()
    plate = State()
    service = State()
    date_pick = State()
    date_text = State()
    time_pick = State()
    time_text = State()
    master = State()
    review = State()
    pick_edit = State()
    report_query = State()


def is_admin(uid: int) -> bool:
    if not ADMIN_TELEGRAM_IDS:
        log.warning("ADMIN_TELEGRAM_IDS пуст — доступ разрешён всем (только для отладки).")
        return True
    return uid in ADMIN_TELEGRAM_IDS


def access_denied(chat_id: int) -> None:
    bot.send_message(chat_id, "Доступ запрещён. Обратитесь к руководителю.")


def booking_as_draft(b: db.BookingRow) -> dict[str, Any]:
    try:
        sa = datetime.fromisoformat(b.start_at)
        return {
            "client_name": b.client_name,
            "phone": b.phone,
            "make_model": b.make_model,
            "license_plate": b.license_plate,
            "service": b.service,
            "master_name": b.master_name,
            "booking_date": sa.date().isoformat(),
            "booking_time": (sa.hour, sa.minute),
        }
    except Exception:
        return {
            "client_name": b.client_name,
            "phone": b.phone,
            "make_model": b.make_model,
            "license_plate": b.license_plate,
            "service": b.service,
            "master_name": b.master_name,
            "booking_date": "",
            "booking_time": None,
        }


def draft_lines(data: dict[str, Any]) -> str:
    d = data.get("booking_date")
    t = data.get("booking_time")
    dt_s = "—"
    if d and t:
        try:
            dd = date.fromisoformat(d) if isinstance(d, str) else d
            h, m = t if isinstance(t, tuple) else (0, 0)
            dt_s = combine_local_datetime(dd, h, m).strftime("%d.%m.%Y %H:%M")
        except Exception:
            dt_s = f"{d} {t}"
    return (
        f"Клиент: {data.get('client_name', '—')}\n"
        f"Телефон: {data.get('phone', '—')}\n"
        f"Авто: {data.get('make_model', '—')}\n"
        f"Госномер: {data.get('license_plate', '—')}\n"
        f"Услуга: {data.get('service', '—')}\n"
        f"Дата и время: {dt_s}\n"
        f"Мастер: {data.get('master_name') or 'Не назначен'}"
    )


def goto_review(state: StateContext, chat_id: int) -> None:
    state.add_data(return_to_review=False)
    state.set(BookingStates.review)
    send_review(chat_id, state)


def start_booking_flow(chat_id: int, user_id: int, state: StateContext) -> None:
    chat_ui.purge_tracked(bot, chat_id, state)
    state.delete()
    state.set(BookingStates.client_name)
    chat_ui.send_tracked(
        bot,
        chat_id,
        state,
        "Новая запись. Введите имя клиента:",
        reply_markup=cancel_reply(),
    )


@bot.message_handler(commands=["start", "help"])
def cmd_start(message: types.Message, state: StateContext):
    if not is_admin(message.from_user.id):
        return access_denied(message.chat.id)
    state.delete()
    bot.send_message(
        message.chat.id,
        "Бот записи детейлинга.\n"
        "• «Новая запись» — пошаговый ввод с кнопками.\n"
        "• «Отчёты» — меню или напишите запрос текстом.\n"
        "• «Статус записи» — выполнено / не пришёл / отмена.\n"
        "/cancel — сбросить текущий шаг.",
        reply_markup=main_menu(),
    )


@bot.message_handler(commands=["cancel"], state="*")
def cmd_cancel(message: types.Message, state: StateContext):
    if not is_admin(message.from_user.id):
        return access_denied(message.chat.id)
    chat_ui.purge_tracked(bot, message.chat.id, state)
    state.delete()
    bot.send_message(message.chat.id, "Шаг сброшен.", reply_markup=main_menu())


@bot.message_handler(func=lambda m: m.text == "Отмена", state="*")
def reply_cancel(message: types.Message, state: StateContext):
    if not is_admin(message.from_user.id):
        return access_denied(message.chat.id)
    chat_ui.purge_tracked(bot, message.chat.id, state)
    state.delete()
    bot.send_message(message.chat.id, "Ок, отменено.", reply_markup=main_menu())


@bot.message_handler(func=lambda m: m.text == "Помощь")
def help_btn(message: types.Message, state: StateContext):
    if not is_admin(message.from_user.id):
        return access_denied(message.chat.id)
    state.delete()
    bot.send_message(
        message.chat.id,
        "Бот записи детейлинга.\n"
        "• «Новая запись» — пошаговый ввод с кнопками.\n"
        "• «Отчёты» — меню или свой текстовый запрос.\n"
        "• «Статус записи» — выполнено / не пришёл / отмена.\n"
        "/cancel — сбросить текущий шаг.",
        reply_markup=main_menu(),
    )


@bot.message_handler(func=lambda m: m.text == "Новая запись")
def btn_new(message: types.Message, state: StateContext):
    if not is_admin(message.from_user.id):
        return access_denied(message.chat.id)
    start_booking_flow(message.chat.id, message.from_user.id, state)


@bot.message_handler(state=BookingStates.client_name)
def step_name(message: types.Message, state: StateContext):
    if not is_admin(message.from_user.id):
        return access_denied(message.chat.id)
    name = (message.text or "").strip()
    if len(name) < 2:
        return chat_ui.send_tracked(
            bot,
            message.chat.id,
            state,
            "Имя слишком короткое, введите ещё раз.",
            reply_markup=cancel_reply(),
        )
    with state.data() as data:
        ret = data.get("return_to_review")
    state.add_data(client_name=name)
    if ret:
        return goto_review(state, message.chat.id)
    state.set(BookingStates.phone)
    chat_ui.send_tracked(
        bot,
        message.chat.id,
        state,
        "Телефон клиента (можно с +7 или 8…):",
        reply_markup=cancel_reply(),
    )


@bot.message_handler(state=BookingStates.phone)
def step_phone(message: types.Message, state: StateContext):
    if not is_admin(message.from_user.id):
        return access_denied(message.chat.id)
    ok, phone = normalize_phone(message.text or "")
    if not ok:
        return chat_ui.send_tracked(
            bot,
            message.chat.id,
            state,
            "Не похоже на российский номер. Пример: +79161234567 или 89161234567.",
            reply_markup=cancel_reply(),
        )
    with state.data() as data:
        ret = data.get("return_to_review")
    state.add_data(phone=phone)
    if ret:
        return goto_review(state, message.chat.id)
    state.set(BookingStates.car_brand)
    brands = car_catalog.merged_brands_list()
    chat_ui.send_tracked(
        bot,
        message.chat.id,
        state,
        "Марка автомобиля. Свои марки сохраняются и попадают в быстрый выбор.",
        reply_markup=brands_inline(brands),
    )


@bot.callback_query_handler(func=lambda c: c.data.startswith("br:"), state=BookingStates.car_brand)
def cb_brand(call: types.CallbackQuery, state: StateContext):
    if not is_admin(call.from_user.id):
        return bot.answer_callback_query(call.id)
    brands = car_catalog.merged_brands_list()
    idx = int(call.data.split(":")[1])
    if idx < 0 or idx >= len(brands):
        return bot.answer_callback_query(call.id)
    brand = brands[idx]
    chat_ui.delete_callback_message(bot, call.message.chat.id, call.message.message_id)
    if brand == BRAND_OTHER_LABEL:
        state.set(BookingStates.car_brand_text)
        bot.answer_callback_query(call.id)
        return chat_ui.send_tracked(
            bot,
            call.message.chat.id,
            state,
            "Введите марку автомобиля (будет в быстром выборе в следующий раз):",
            reply_markup=cancel_reply(),
        )
    state.add_data(car_brand=brand)
    state.set(BookingStates.car_model)
    models = car_catalog.models_for_brand(brand)
    state.add_data(models_order=models)
    bot.answer_callback_query(call.id)
    return chat_ui.send_tracked(
        bot,
        call.message.chat.id,
        state,
        f"Марка: {brand}. Выберите модель или «Своя модель»:",
        reply_markup=models_inline(models),
    )


@bot.message_handler(state=BookingStates.car_brand_text)
def step_brand_text(message: types.Message, state: StateContext):
    if not is_admin(message.from_user.id):
        return access_denied(message.chat.id)
    brand = (message.text or "").strip()
    if len(brand) < 2:
        return chat_ui.send_tracked(
            bot,
            message.chat.id,
            state,
            "Слишком коротко. Введите марку ещё раз.",
            reply_markup=cancel_reply(),
        )
    db.add_saved_brand(brand)
    state.add_data(car_brand=brand)
    state.set(BookingStates.car_model)
    models = car_catalog.models_for_brand(brand)
    state.add_data(models_order=models)
    chat_ui.send_tracked(
        bot,
        message.chat.id,
        state,
        f"Марка: {brand}. Выберите модель или «Своя модель»:",
        reply_markup=models_inline(models),
    )


@bot.callback_query_handler(func=lambda c: c.data.startswith("md:"), state=BookingStates.car_model)
def cb_model(call: types.CallbackQuery, state: StateContext):
    if not is_admin(call.from_user.id):
        return bot.answer_callback_query(call.id)
    chat_ui.delete_callback_message(bot, call.message.chat.id, call.message.message_id)
    part = call.data.split(":")[1]
    with state.data() as data:
        brand = data.get("car_brand") or ""
        models_order: list[str] = list(data.get("models_order") or [])
        ret = data.get("return_to_review")
    if part == "c":
        state.set(BookingStates.car_model_custom)
        bot.answer_callback_query(call.id)
        return chat_ui.send_tracked(
            bot,
            call.message.chat.id,
            state,
            f"Марка: {brand}. Введите модель (сохраним для этой марки):",
            reply_markup=cancel_reply(),
        )
    idx = int(part)
    if idx < 0 or idx >= len(models_order):
        return bot.answer_callback_query(call.id, "Неверный выбор", show_alert=True)
    model = models_order[idx]
    db.add_saved_model(brand, model)
    make_model = f"{brand} {model}".strip()
    state.add_data(make_model=make_model)
    bot.answer_callback_query(call.id)
    if ret:
        return goto_review(state, call.message.chat.id)
    state.set(BookingStates.plate)
    return chat_ui.send_tracked(
        bot,
        call.message.chat.id,
        state,
        "Госномер (как на машине):",
        reply_markup=cancel_reply(),
    )


@bot.message_handler(state=BookingStates.car_model_custom)
def step_car_model_custom(message: types.Message, state: StateContext):
    if not is_admin(message.from_user.id):
        return access_denied(message.chat.id)
    model = (message.text or "").strip()
    if len(model) < 1:
        return chat_ui.send_tracked(
            bot,
            message.chat.id,
            state,
            "Введите модель.",
            reply_markup=cancel_reply(),
        )
    with state.data() as data:
        brand = data.get("car_brand") or ""
        ret = data.get("return_to_review")
    db.add_saved_model(brand, model)
    make_model = f"{brand} {model}".strip()
    state.add_data(make_model=make_model)
    if ret:
        return goto_review(state, message.chat.id)
    state.set(BookingStates.plate)
    chat_ui.send_tracked(
        bot,
        message.chat.id,
        state,
        "Госномер (как на машине):",
        reply_markup=cancel_reply(),
    )


@bot.message_handler(state=BookingStates.plate)
def step_plate(message: types.Message, state: StateContext):
    if not is_admin(message.from_user.id):
        return access_denied(message.chat.id)
    plate = (message.text or "").strip().upper()
    if len(plate) < 3:
        return chat_ui.send_tracked(
            bot,
            message.chat.id,
            state,
            "Госномер слишком короткий.",
            reply_markup=cancel_reply(),
        )
    with state.data() as data:
        ret = data.get("return_to_review")
    state.add_data(license_plate=plate)
    if ret:
        return goto_review(state, message.chat.id)
    state.set(BookingStates.service)
    chat_ui.send_tracked(
        bot,
        message.chat.id,
        state,
        "Выберите услугу:",
        reply_markup=services_inline(),
    )


@bot.callback_query_handler(func=lambda c: c.data.startswith("svc:"), state=BookingStates.service)
def cb_service(call: types.CallbackQuery, state: StateContext):
    if not is_admin(call.from_user.id):
        return bot.answer_callback_query(call.id)
    idx = int(call.data.split(":")[1])
    svc = SERVICES[idx]
    with state.data() as data:
        ret = data.get("return_to_review")
    state.add_data(service=svc)
    chat_ui.delete_callback_message(bot, call.message.chat.id, call.message.message_id)
    bot.answer_callback_query(call.id)
    if ret:
        return goto_review(state, call.message.chat.id)
    state.set(BookingStates.date_pick)
    chat_ui.send_tracked(bot, call.message.chat.id, state, "Дата записи:", reply_markup=date_inline())


@bot.callback_query_handler(func=lambda c: c.data.startswith("dt:"), state=BookingStates.date_pick)
def cb_date(call: types.CallbackQuery, state: StateContext):
    if not is_admin(call.from_user.id):
        return bot.answer_callback_query(call.id)
    code = int(call.data.split(":")[1])
    now = datetime.now()
    chat_ui.delete_callback_message(bot, call.message.chat.id, call.message.message_id)
    if code == 9:
        state.set(BookingStates.date_text)
        bot.answer_callback_query(call.id)
        return chat_ui.send_tracked(
            bot,
            call.message.chat.id,
            state,
            "Дата в формате ДД.ММ.ГГГГ или ГГГГ-ММ-ДД:",
            reply_markup=cancel_reply(),
        )
    d = now.date()
    if code == 1:
        d = d + timedelta(days=1)
    elif code == 2:
        d = d + timedelta(days=2)
    state.add_data(booking_date=d.isoformat())
    bot.answer_callback_query(call.id)
    state.set(BookingStates.time_pick)
    chat_ui.send_tracked(bot, call.message.chat.id, state, "Время:", reply_markup=time_inline())


@bot.message_handler(state=BookingStates.date_text)
def step_date_text(message: types.Message, state: StateContext):
    if not is_admin(message.from_user.id):
        return access_denied(message.chat.id)
    d = parse_date_text(message.text or "")
    if not d:
        return chat_ui.send_tracked(
            bot,
            message.chat.id,
            state,
            "Не удалось разобрать дату. Пример: 15.04.2026",
            reply_markup=cancel_reply(),
        )
    with state.data() as data:
        ret = data.get("return_to_review")
    state.add_data(booking_date=d.isoformat())
    if ret:
        state.set(BookingStates.time_pick)
        return chat_ui.send_tracked(
            bot,
            message.chat.id,
            state,
            "Выберите новое время:",
            reply_markup=time_inline(),
        )
    state.set(BookingStates.time_pick)
    chat_ui.send_tracked(bot, message.chat.id, state, "Время:", reply_markup=time_inline())


@bot.callback_query_handler(func=lambda c: c.data.startswith("tm:"), state=BookingStates.time_pick)
def cb_time(call: types.CallbackQuery, state: StateContext):
    if not is_admin(call.from_user.id):
        return bot.answer_callback_query(call.id)
    idx = int(call.data.split(":")[1])
    slot = TIME_SLOTS[idx]
    chat_ui.delete_callback_message(bot, call.message.chat.id, call.message.message_id)
    if slot == "Другое":
        state.set(BookingStates.time_text)
        bot.answer_callback_query(call.id)
        return chat_ui.send_tracked(
            bot,
            call.message.chat.id,
            state,
            "Время в формате ЧЧ:ММ (например 14:30):",
            reply_markup=cancel_reply(),
        )
    h, m = map(int, slot.split(":"))
    bot.answer_callback_query(call.id)
    _finish_time_pick(call.message.chat.id, state, h, m)


@bot.message_handler(state=BookingStates.time_text)
def step_time_text(message: types.Message, state: StateContext):
    if not is_admin(message.from_user.id):
        return access_denied(message.chat.id)
    parsed = parse_time_text(message.text or "")
    if not parsed:
        return chat_ui.send_tracked(
            bot,
            message.chat.id,
            state,
            "Формат ЧЧ:ММ, например 09:30",
            reply_markup=cancel_reply(),
        )
    h, m = parsed
    _finish_time_pick(message.chat.id, state, h, m)


def _finish_time_pick(chat_id: int, state: StateContext, h: int, m: int) -> None:
    with state.data() as data:
        ret = data.get("return_to_review")
        d_iso = data.get("booking_date")
    if not d_iso:
        chat_ui.send_tracked(bot, chat_id, state, "Сначала выберите дату.", reply_markup=cancel_reply())
        return
    d = date.fromisoformat(d_iso)
    state.add_data(booking_time=(h, m))
    if ret:
        return goto_review(state, chat_id)
    state.set(BookingStates.master)
    chat_ui.send_tracked(bot, chat_id, state, "Мастер:", reply_markup=masters_inline())


@bot.callback_query_handler(func=lambda c: c.data.startswith("mst:"), state=BookingStates.master)
def cb_master(call: types.CallbackQuery, state: StateContext):
    if not is_admin(call.from_user.id):
        return bot.answer_callback_query(call.id)
    idx = int(call.data.split(":")[1])
    name = MASTERS[idx]
    master_name: Optional[str] = None if name == "Не назначен" else name
    with state.data() as data:
        ret = data.get("return_to_review")
    state.add_data(master_name=master_name)
    chat_ui.delete_callback_message(bot, call.message.chat.id, call.message.message_id)
    bot.answer_callback_query(call.id)
    if ret:
        return goto_review(state, call.message.chat.id)
    state.set(BookingStates.review)
    send_review(call.message.chat.id, state)


def send_review(chat_id: int, state: StateContext) -> None:
    with state.data() as data:
        text = "Проверьте данные:\n\n" + draft_lines(data)
    chat_ui.send_tracked(bot, chat_id, state, text, reply_markup=confirm_inline())


@bot.callback_query_handler(func=lambda c: c.data.startswith("cf:"), state=BookingStates.review)
def cb_confirm(call: types.CallbackQuery, state: StateContext):
    if not is_admin(call.from_user.id):
        return bot.answer_callback_query(call.id)
    action = call.data.split(":")[1]
    bot.answer_callback_query(call.id)
    if action == "xx":
        chat_ui.purge_tracked(bot, call.message.chat.id, state)
        state.delete()
        return bot.send_message(call.message.chat.id, "Черновик отменён.", reply_markup=main_menu())
    if action == "ed":
        state.set(BookingStates.pick_edit)
        return chat_ui.send_tracked(
            bot, call.message.chat.id, state, "Что изменить?", reply_markup=edit_field_inline()
        )
    if action != "ok":
        return
    with state.data() as data:
        try:
            d_iso = data["booking_date"]
            h, m = data["booking_time"]
            start_at = combine_local_datetime(date.fromisoformat(d_iso), h, m)
        except Exception:
            state.delete()
            return bot.send_message(
                call.message.chat.id,
                "Не хватает даты/времени. Начните заново: «Новая запись».",
                reply_markup=main_menu(),
            )
        payload = {
            "client_name": data["client_name"],
            "phone": data["phone"],
            "make_model": data["make_model"],
            "license_plate": data["license_plate"],
            "service": data["service"],
            "master_name": data.get("master_name"),
            "start_at": start_at,
        }
    bid = db.create_booking(
        client_name=payload["client_name"],
        phone=payload["phone"],
        make_model=payload["make_model"],
        license_plate=payload["license_plate"],
        service=payload["service"],
        master_name=payload["master_name"],
        start_at=payload["start_at"],
        admin_telegram_id=call.from_user.id,
    )
    cal_err: Optional[str] = None
    if yandex_calendar.is_configured():
        try:
            desc = (
                f"Тел: {payload['phone']}\n"
                f"Авто: {payload['make_model']} {payload['license_plate']}\n"
                f"Услуга: {payload['service']}\n"
                f"ID в боте: {bid}"
            )
            uid, href = yandex_calendar.create_calendar_event(
                summary=f"{payload['service']} — {payload['client_name']}",
                description=desc,
                start_at=payload["start_at"],
            )
            db.update_booking_calendar(bid, calendar_uid=uid, calendar_href=href)
        except yandex_calendar.YandexCalendarDisabled:
            cal_err = "Яндекс.Календарь не настроен."
        except Exception as e:  # noqa: BLE001
            log.exception("yandex calendar")
            cal_err = str(e)
    else:
        cal_err = "Яндекс.Календарь не настроен — только SQLite."

    chat_ui.purge_tracked(bot, call.message.chat.id, state)
    state.delete()
    lines = [
        "Запись сохранена.",
        f"ID: {bid}",
        draft_lines(
            {
                **payload,
                "booking_date": payload["start_at"].date().isoformat(),
                "booking_time": (payload["start_at"].hour, payload["start_at"].minute),
            }
        ),
    ]
    if cal_err:
        lines.append(f"Календарь: {cal_err}")
    else:
        lines.append("Событие добавлено в Яндекс.Календарь.")
    bot.send_message(call.message.chat.id, "\n".join(lines), reply_markup=main_menu())


@bot.callback_query_handler(func=lambda c: c.data.startswith("ed:"), state=BookingStates.pick_edit)
def cb_edit_menu(call: types.CallbackQuery, state: StateContext):
    if not is_admin(call.from_user.id):
        return bot.answer_callback_query(call.id)
    code = call.data.split(":")[1]
    bot.answer_callback_query(call.id)
    if code == "back":
        state.set(BookingStates.review)
        return send_review(call.message.chat.id, state)
    state.add_data(return_to_review=True)
    mapping = {
        "nm": BookingStates.client_name,
        "ph": BookingStates.phone,
        "cr": BookingStates.car_brand,
        "gp": BookingStates.plate,
        "sv": BookingStates.service,
        "dt": BookingStates.date_pick,
        "ms": BookingStates.master,
    }
    prompts = {
        "nm": "Новое имя клиента:",
        "ph": "Новый телефон:",
        "cr": "Выберите марку и модель:",
        "gp": "Новый госномер:",
        "sv": "Выберите услугу:",
    }
    if code not in mapping:
        return
    state.set(mapping[code])
    if code == "sv":
        return chat_ui.send_tracked(
            bot, call.message.chat.id, state, prompts[code], reply_markup=services_inline()
        )
    if code == "dt":
        return chat_ui.send_tracked(
            bot, call.message.chat.id, state, "Новая дата:", reply_markup=date_inline()
        )
    if code == "ms":
        state.set(BookingStates.master)
        return chat_ui.send_tracked(
            bot, call.message.chat.id, state, "Мастер:", reply_markup=masters_inline()
        )
    if code == "cr":
        brands = car_catalog.merged_brands_list()
        return chat_ui.send_tracked(
            bot,
            call.message.chat.id,
            state,
            prompts["cr"],
            reply_markup=brands_inline(brands),
        )
    return chat_ui.send_tracked(
        bot,
        call.message.chat.id,
        state,
        prompts.get(code, "Введите значение:"),
        reply_markup=cancel_reply(),
    )


@bot.message_handler(func=lambda m: m.text == "Отчёты")
def btn_reports(message: types.Message, state: StateContext):
    if not is_admin(message.from_user.id):
        return access_denied(message.chat.id)
    state.delete()
    bot.send_message(
        message.chat.id,
        "Выберите отчёт или нажмите «Свой запрос»:",
        reply_markup=report_menu_inline(),
    )


@bot.callback_query_handler(func=lambda c: c.data.startswith("rp:"))
def cb_report(call: types.CallbackQuery, state: StateContext):
    if not is_admin(call.from_user.id):
        return bot.answer_callback_query(call.id)
    code = call.data[3:]
    bot.answer_callback_query(call.id)
    if code == "tx":
        state.set(BookingStates.report_query)
        state.add_data(report_focus="free")
        return bot.send_message(
            call.message.chat.id,
            "Напишите запрос, например:\n"
            "«Сколько машин записано на этой неделе?»\n"
            "«Покажи все записи на завтра»",
            reply_markup=cancel_reply(),
        )
    kinds = {
        "w": "week_count",
        "tm": "tomorrow_list",
        "cd": "completed_today",
        "mo": "month_summary",
        "ma": "master_month",
        "ns": "no_show_2w",
        "op": "open_cancelled",
        "st": "client_stats_month",
    }
    kind = kinds.get(code)
    if not kind:
        return
    if kind == "master_month":
        state.set(BookingStates.report_query)
        state.add_data(report_focus="master")
        return bot.send_message(
            call.message.chat.id,
            "Напишите имя мастера или фразу целиком, например: «сколько записей у мастера Алексей за месяц».",
            reply_markup=cancel_reply(),
        )
    text = reports_engine.run_parsed(kind)
    bot.send_message(call.message.chat.id, text[:4000], reply_markup=main_menu())


@bot.message_handler(state=BookingStates.report_query)
def step_report_query(message: types.Message, state: StateContext):
    if not is_admin(message.from_user.id):
        return access_denied(message.chat.id)
    raw = message.text or ""
    with state.data() as data:
        focus = data.get("report_focus", "free")
    parsed = parse_report_message(raw)
    if not parsed and raw:
        parsed = parse_report_message("мастер " + raw)
    if not parsed and focus == "master" and len(raw.strip()) >= 1:
        parsed = ParsedReport("master_month", master_hint=raw.strip())
    if not parsed:
        state.delete()
        return bot.send_message(
            message.chat.id,
            "Не удалось разобрать запрос. Используйте кнопки в «Отчёты».",
            reply_markup=main_menu(),
        )
    state.delete()
    out = reports_engine.run_parsed(parsed.kind, parsed.master_hint)
    bot.send_message(message.chat.id, out[:4000], reply_markup=main_menu())


@bot.message_handler(func=lambda m: m.text == "Статус записи")
def btn_status(message: types.Message, state: StateContext):
    if not is_admin(message.from_user.id):
        return access_denied(message.chat.id)
    state.delete()
    rows = db.list_recent_bookings(15)
    if not rows:
        return bot.send_message(message.chat.id, "Записей пока нет.", reply_markup=main_menu())
    titles: list[tuple[int, str]] = []
    for r in rows:
        try:
            ds = datetime.fromisoformat(r.start_at).strftime("%d.%m %H:%M")
        except ValueError:
            ds = r.start_at
        titles.append((r.id, f"#{r.id} {ds} {r.client_name} {r.license_plate}"))
    bot.send_message(
        message.chat.id,
        "Выберите запись:",
        reply_markup=recent_bookings_inline(titles),
    )


@bot.callback_query_handler(func=lambda c: c.data.startswith("bk:"))
def cb_pick_booking(call: types.CallbackQuery, state: StateContext):
    if not is_admin(call.from_user.id):
        return bot.answer_callback_query(call.id)
    bid = int(call.data.split(":")[1])
    row = db.get_booking(bid)
    bot.answer_callback_query(call.id)
    if not row:
        return bot.send_message(call.message.chat.id, "Запись не найдена.")
    bot.send_message(
        call.message.chat.id,
        f"Запись #{bid}\n{draft_lines(booking_as_draft(row))}\n\nВыберите новый статус:",
        reply_markup=status_pick_booking(bid),
    )


@bot.callback_query_handler(func=lambda c: c.data.startswith("st:"))
def cb_set_status(call: types.CallbackQuery, state: StateContext):
    if not is_admin(call.from_user.id):
        return bot.answer_callback_query(call.id)
    parts = call.data.split(":")
    bid = int(parts[1])
    act = parts[2]
    mapping = {"done": "completed", "resched": "rescheduled", "noshow": "no_show", "cancel": "cancelled"}
    st = mapping.get(act)
    bot.answer_callback_query(call.id)
    if not st:
        return
    db.update_booking_status(bid, st)
    bot.send_message(
        call.message.chat.id,
        f"Статус записи #{bid} → {yandex_calendar.status_ru(st)}",
        reply_markup=main_menu(),
    )


bot.add_custom_filter(custom_filters.StateFilter(bot))
bot.setup_middleware(StateMiddleware(bot))


def main() -> None:
    db.init_db()
    log.info("Бот запущен.")
    bot.infinity_polling(
        skip_pending=True,
        allowed_updates=["message", "callback_query", "edited_message"],
    )


if __name__ == "__main__":
    main()
