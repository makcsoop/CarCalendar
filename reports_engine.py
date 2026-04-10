"""Формирование текстов отчётов."""
from __future__ import annotations

from datetime import datetime

import database as db
from utils import month_bounds, tomorrow_bounds, today_bounds, week_bounds


def _fmt_row(b: db.BookingRow) -> str:
    try:
        dt = datetime.fromisoformat(b.start_at)
        ds = dt.strftime("%d.%m.%Y %H:%M")
    except Exception:
        ds = b.start_at
    return (
        f"#{b.id} {ds} | {b.client_name} | {b.phone}\n"
        f"   {b.make_model} | {b.service} | {b.status}"
    )


def report_week_count() -> str:
    start, end = week_bounds()
    n = db.count_bookings_between(start, end)
    return f"Записей на текущей календарной неделе (пн–вс): {n}."


def report_tomorrow_list() -> str:
    start, end = tomorrow_bounds()
    rows = db.bookings_between(start, end)
    if not rows:
        return "На завтра записей нет."
    lines = [_fmt_row(r) for r in rows]
    return "Записи на завтра:\n\n" + "\n\n".join(lines)


def report_completed_today() -> str:
    start, end = today_bounds()
    rows = db.completed_between(start, end)
    if not rows:
        return "Сегодня нет отметок «выполнено» (статус меняется кнопкой «Статус записи»)."
    by_svc: dict[str, int] = {}
    for r in rows:
        by_svc[r.service] = by_svc.get(r.service, 0) + 1
    parts = [f"• {k}: {v}" for k, v in sorted(by_svc.items(), key=lambda x: -x[1])]
    return (
        f"Выполнено сегодня: всего {len(rows)}.\n"
        + "\n".join(parts)
        + "\n\n"
        + "\n\n".join(_fmt_row(r) for r in rows)
    )


def report_month_summary() -> str:
    start, end = month_bounds()
    n = db.count_bookings_between(start, end)
    svc = db.count_by_service_between(start, end)
    svc_lines = "\n".join(f"• {s}: {c}" for s, c in svc) or "—"
    return (
        f"Текущий месяц: всего записей {n}.\n\n"
        f"По услугам:\n{svc_lines}"
    )


def report_no_show() -> str:
    rows = db.no_show_since(14)
    if not rows:
        return "За последние 2 недели нет записей со статусом «не пришёл»."
    return "Не пришли (2 недели):\n\n" + "\n\n".join(_fmt_row(r) for r in rows)


def report_open_cancelled() -> str:
    rows = db.open_or_cancelled()
    if not rows:
        return "Незакрытых предстоящих и недавних отменённых не найдено."
    return "Незакрытые / отменённые:\n\n" + "\n\n".join(_fmt_row(r) for r in rows)


def report_client_stats_month() -> str:
    start, end = month_bounds()
    new_c, rep = db.client_stats_between(start, end)
    return (
        f"Клиенты за текущий месяц (по первой записи в базе):\n"
        f"• Новые: {new_c}\n"
        f"• Повторные (уже были раньше): {rep}"
    )


def report_popular_cars() -> str:
    top_all = db.popular_cars(limit=10, only_processed=False)
    top_done = db.popular_cars(limit=10, only_processed=True)
    if not top_all and not top_done:
        return "Данных по авто пока нет."
    all_lines = "\n".join(f"• {car}: {cnt}" for car, cnt in top_all) or "—"
    done_lines = "\n".join(f"• {car}: {cnt}" for car, cnt in top_done) or "—"
    return (
        "Наиболее частые авто:\n\n"
        "Приходят (все записи):\n"
        f"{all_lines}\n\n"
        "Обрабатываются (статус «выполнена»):\n"
        f"{done_lines}"
    )


def run_parsed(kind: str) -> str:
    if kind == "week_count":
        return report_week_count()
    if kind == "tomorrow_list":
        return report_tomorrow_list()
    if kind == "completed_today":
        return report_completed_today()
    if kind == "month_summary":
        return report_month_summary()
    if kind == "no_show_2w":
        return report_no_show()
    if kind == "open_cancelled":
        return report_open_cancelled()
    if kind == "client_stats_month":
        return report_client_stats_month()
    if kind == "cars_popular":
        return report_popular_cars()
    return "Неизвестный тип отчёта."
