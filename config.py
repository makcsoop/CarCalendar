"""Загрузка настроек из окружения."""
from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent


def _parse_admin_ids(raw: str | None) -> set[int]:
    if not raw:
        return set()
    out: set[int] = set()
    for part in raw.replace(" ", "").split(","):
        if not part:
            continue
        try:
            out.add(int(part))
        except ValueError:
            continue
    print(out)
    return out


BOT_TOKEN = os.getenv("BOT_TOKEN", "").strip()
ADMIN_TELEGRAM_IDS = _parse_admin_ids(os.getenv("ADMIN_TELEGRAM_IDS", ""))

# Яндекс.Календарь через CalDAV (пароль приложения в настройках Яндекс ID)
YANDEX_CALDAV_USER = os.getenv("YANDEX_CALDAV_USER", "").strip()
YANDEX_CALDAV_PASSWORD = os.getenv("YANDEX_CALDAV_PASSWORD", "").strip()
# Имя календаря в интерфейсе (если пусто — первый доступный)
YANDEX_CALENDAR_NAME = os.getenv("YANDEX_CALENDAR_NAME", "").strip()

SQLITE_PATH = Path(os.getenv("SQLITE_PATH", str(BASE_DIR / "data" / "bookings.db")))

# Предустановки интерфейса
SERVICES = [
    "Полная защитная оклейка (глянец)",
    "Полная защитная оклейка (мат)",
    "Цветная защитная пленка",
    "Оклейка зоны риска (глянец)",
    "Бронь лобового стекла",
    "Ремонт скола стекла",
    "Тонировка задней полусферы",
    "Атермальная тонировка (перед)",
    "Шумоизоляция дверей",
    "Шумоизоляция арок",
    "Доводчики дверей",
    "Бронировка фар",
]

# Базовый список марок (плюс сохранённые пользователем в SQLite)
CAR_BRANDS = [
    "Toyota",
    "BMW",
    "Mercedes",
    "Audi",
    "Volkswagen",
    "Hyundai",
    "Kia",
]

BRAND_OTHER_LABEL = "Другое (ввести марку)"

# Подсказки моделей по марке; для неизвестной марки — ключ "_default"
MODELS_BY_BRAND: dict[str, list[str]] = {
    "Toyota": ["Camry", "Corolla", "RAV4", "Land Cruiser", "Highlander", "C-HR", "Yaris"],
    "BMW": ["3 серия", "5 серия", "X3", "X5", "X1", "1 серия"],
    "Mercedes": ["C-класс", "E-класс", "GLC", "GLE", "A-класс"],
    "Audi": ["A4", "A6", "Q5", "Q7", "A3", "Q3"],
    "Volkswagen": ["Polo", "Jetta", "Tiguan", "Passat", "Touareg", "Golf"],
    "Hyundai": ["Solaris", "Creta", "Tucson", "Santa Fe", "Elantra"],
    "Kia": ["Rio", "Sportage", "Sorento", "Cerato", "Optima"],
    "_default": ["Седан", "Хэтчбек", "Универсал", "Кроссовер", "Минивэн", "Пикап"],
}

TIME_SLOTS = [
    "09:00",
    "10:00",
    "11:00",
    "12:00",
    "13:00",
    "14:00",
    "15:00",
    "16:00",
    "17:00",
    "18:00",
    "Другое",
]

PHONE_TEMPLATES = [
    "+7 ___ ___-__-__",
    "Указать вручную",
]
