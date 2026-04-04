"""События в Яндекс.Календаре через CalDAV."""
from __future__ import annotations

import logging
import uuid
from datetime import datetime, timedelta
from typing import Optional, Tuple
from zoneinfo import ZoneInfo

import caldav
from icalendar import Calendar as ICal
from icalendar import Event as IEvent

from config import YANDEX_CALDAV_PASSWORD, YANDEX_CALDAV_USER, YANDEX_CALENDAR_NAME

log = logging.getLogger(__name__)

TZ = ZoneInfo("Europe/Moscow")


class YandexCalendarDisabled(Exception):
    pass


def is_configured() -> bool:
    return bool(YANDEX_CALDAV_USER and YANDEX_CALDAV_PASSWORD)


def _client() -> caldav.DAVClient:
    if not is_configured():
        raise YandexCalendarDisabled("Задайте YANDEX_CALDAV_USER и YANDEX_CALDAV_PASSWORD")
    return caldav.DAVClient(
        url="https://caldav.yandex.ru/",
        username=YANDEX_CALDAV_USER,
        password=YANDEX_CALDAV_PASSWORD,
    )


def _pick_calendar() -> caldav.Calendar:
    principal = _client().principal()
    calendars = principal.calendars()
    if not calendars:
        raise RuntimeError("CalDAV: список календарей пуст. Проверьте пароль приложения.")
    if YANDEX_CALENDAR_NAME:
        name_lower = YANDEX_CALENDAR_NAME.casefold()
        for c in calendars:
            cname = getattr(c, "name", None) or ""
            if cname.casefold() == name_lower:
                return c
        log.warning("Календарь «%s» не найден, берём первый: %s", YANDEX_CALENDAR_NAME, calendars[0].name)
    return calendars[0]


def _naive_to_tz(dt: datetime) -> datetime:
    if dt.tzinfo is None:
        return dt.replace(tzinfo=TZ)
    return dt.astimezone(TZ)


def create_calendar_event(
    *,
    summary: str,
    description: str,
    start_at: datetime,
    duration_minutes: int = 120,
) -> Tuple[Optional[str], Optional[str]]:
    """Создаёт событие. Возвращает (uid, href) или (None, None) если не настроено."""
    if not is_configured():
        return None, None
    uid = f"{uuid.uuid4()}@detailings-bot"
    start = _naive_to_tz(start_at)
    end = start + timedelta(minutes=duration_minutes)

    ev = IEvent()
    ev.add("uid", uid)
    ev.add("dtstamp", datetime.now(TZ))
    ev.add("dtstart", start)
    ev.add("dtend", end)
    ev.add("summary", summary)
    ev.add("description", description)

    cal = ICal()
    cal.add("prodid", "-//Detailing Bot//RU//")
    cal.add("version", "2.0")
    cal.add_component(ev)
    ics = cal.to_ical().decode("utf-8")

    calendar = _pick_calendar()
    saved = calendar.add_event(ics)
    href: Optional[str] = None
    if saved is not None and getattr(saved, "url", None):
        href = str(saved.url)
    return uid, href


def status_ru(status: str) -> str:
    return {
        "confirmed": "подтверждена",
        "rescheduled": "перенесена",
        "completed": "выполнена",
        "cancelled": "отменена",
        "no_show": "не пришёл",
    }.get(status, status)
