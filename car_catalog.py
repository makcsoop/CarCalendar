"""Сборка списков марок и моделей: конфиг + SQLite."""
from __future__ import annotations

import database as db
from config import BRAND_OTHER_LABEL, CAR_BRANDS, MODELS_BY_BRAND


def merged_brands_list() -> list[str]:
    """Базовые марки + сохранённые пользователем + кнопка «Другое»."""
    defaults = list(CAR_BRANDS)
    saved = db.list_saved_brands()
    merged: list[str] = []
    seen: set[str] = set()
    for b in defaults:
        k = b.casefold()
        if k not in seen:
            seen.add(k)
            merged.append(b)
    for b in saved:
        k = b.casefold()
        if k not in seen:
            seen.add(k)
            merged.append(b)
    merged.append(BRAND_OTHER_LABEL)
    return merged


def models_for_brand(brand: str) -> list[str]:
    presets = MODELS_BY_BRAND.get(brand) or MODELS_BY_BRAND.get("_default", [])
    saved = db.list_saved_models(brand)
    out: list[str] = []
    seen: set[str] = set()
    for m in presets:
        k = m.casefold()
        if k not in seen:
            seen.add(k)
            out.append(m)
    for m in saved:
        k = m.casefold()
        if k not in seen:
            seen.add(k)
            out.append(m)
    return out
