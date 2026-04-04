"""Парсинг телефона, даты и времени."""
from __future__ import annotations

import re
from datetime import date, datetime, timedelta
from typing import Optional, Tuple


def normalize_phone(text: str) -> Tuple[bool, str]:
    digits = re.sub(r"\D", "", text)
    if not digits:
        return False, ""
    if digits.startswith("8") and len(digits) == 11:
        digits = "7" + digits[1:]
    if digits.startswith("9") and len(digits) == 10:
        digits = "7" + digits
    if len(digits) == 11 and digits.startswith("7"):
        return True, f"+{digits}"
    if len(digits) == 10:
        return True, f"+7{digits}"
    return False, digits


def parse_date_text(text: str, now: Optional[datetime] = None) -> Optional[date]:
    now = now or datetime.now()
    t = text.strip().lower()
    if t in ("сегодня", "today"):
        return now.date()
    if t in ("завтра", "tomorrow"):
        return (now + timedelta(days=1)).date()
    if t in ("послезавтра"):
        return (now + timedelta(days=2)).date()
    for fmt in ("%d.%m.%Y", "%d.%m.%y", "%Y-%m-%d"):
        try:
            return datetime.strptime(text.strip(), fmt).date()
        except ValueError:
            continue
    return None


def parse_time_text(text: str) -> Optional[Tuple[int, int]]:
    m = re.match(r"^(\d{1,2})[:.](\d{2})$", text.strip())
    if not m:
        return None
    h, mi = int(m.group(1)), int(m.group(2))
    if 0 <= h <= 23 and 0 <= mi <= 59:
        return h, mi
    return None


def combine_local_datetime(d: date, hour: int, minute: int) -> datetime:
    return datetime(d.year, d.month, d.day, hour, minute)


def week_bounds(now: Optional[datetime] = None) -> Tuple[datetime, datetime]:
    now = now or datetime.now()
    # Понедельник — начало недели
    d = now.date()
    weekday = d.weekday()  # Mon=0
    start_d = d - timedelta(days=weekday)
    start = datetime.combine(start_d, datetime.min.time())
    end = start + timedelta(days=7)
    return start, end


def month_bounds(ref: Optional[datetime] = None) -> Tuple[datetime, datetime]:
    ref = ref or datetime.now()
    start = ref.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    if start.month == 12:
        end = start.replace(year=start.year + 1, month=1)
    else:
        end = start.replace(month=start.month + 1)
    return start, end


def today_bounds(now: Optional[datetime] = None) -> Tuple[datetime, datetime]:
    now = now or datetime.now()
    d = now.date()
    start = datetime.combine(d, datetime.min.time())
    end = start + timedelta(days=1)
    return start, end


def tomorrow_bounds(now: Optional[datetime] = None) -> Tuple[datetime, datetime]:
    s, e = today_bounds(now)
    return s + timedelta(days=1), e + timedelta(days=1)
