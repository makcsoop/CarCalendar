"""Разбор произвольных текстовых запросов отчётов (рус.)."""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Optional


@dataclass
class ParsedReport:
    kind: str
    master_hint: Optional[str] = None


def parse_report_message(text: str) -> Optional[ParsedReport]:
    t = text.strip().lower()
    if len(t) < 4:
        return None

    if re.search(r"недел", t) and re.search(r"сколько|запис|машин|авто", t):
        return ParsedReport("week_count")
    if "завтра" in t and re.search(r"запис|покаж|все", t):
        return ParsedReport("tomorrow_list")
    if "сегодня" in t and re.search(r"выполнен|услуг", t):
        return ParsedReport("completed_today")
    if re.search(r"месяц", t) and re.search(r"сколько|запис|свод", t):
        return ParsedReport("month_summary")
    if re.search(r"не\s*приш", t) or "no_show" in t:
        return ParsedReport("no_show_2w")
    if re.search(r"незакрыт|отмен", t):
        return ParsedReport("open_cancelled")
    if re.search(r"нов(ый|ые|ых)?\s+клиент|повторн", t):
        return ParsedReport("client_stats_month")
    return None
