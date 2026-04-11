"""SQLite: клиенты, записи, статусы."""
from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any, Generator, Iterable, Optional

from config import SQLITE_PATH


def _ensure_parent(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)


@contextmanager
def get_conn() -> Generator[sqlite3.Connection, None, None]:
    _ensure_parent(SQLITE_PATH)
    conn = sqlite3.connect(SQLITE_PATH)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def init_db() -> None:
    with get_conn() as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS clients (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                phone TEXT NOT NULL,
                created_at TEXT NOT NULL DEFAULT (datetime('now'))
            );
            CREATE TABLE IF NOT EXISTS vehicles (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                client_id INTEGER NOT NULL REFERENCES clients(id),
                make_model TEXT NOT NULL,
                license_plate TEXT NOT NULL,
                created_at TEXT NOT NULL DEFAULT (datetime('now'))
            );
            CREATE TABLE IF NOT EXISTS bookings (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                client_id INTEGER NOT NULL REFERENCES clients(id),
                vehicle_id INTEGER NOT NULL REFERENCES vehicles(id),
                service TEXT NOT NULL,
                master_name TEXT,
                start_at TEXT NOT NULL,
                end_at TEXT,
                status TEXT NOT NULL DEFAULT 'confirmed',
                admin_telegram_id INTEGER,
                confirm_key TEXT,
                google_event_id TEXT,
                sheet_row INTEGER,
                notes TEXT,
                created_at TEXT NOT NULL DEFAULT (datetime('now')),
                updated_at TEXT NOT NULL DEFAULT (datetime('now'))
            );
            CREATE TABLE IF NOT EXISTS saved_brands (
                name TEXT PRIMARY KEY
            );
            CREATE TABLE IF NOT EXISTS saved_models (
                brand_name TEXT NOT NULL,
                model_name TEXT NOT NULL,
                PRIMARY KEY (brand_name, model_name)
            );
            CREATE INDEX IF NOT EXISTS idx_bookings_start ON bookings(start_at);
            CREATE INDEX IF NOT EXISTS idx_bookings_status ON bookings(status);
            CREATE INDEX IF NOT EXISTS idx_bookings_master ON bookings(master_name);
            CREATE UNIQUE INDEX IF NOT EXISTS ux_bookings_confirm_key ON bookings(confirm_key);
            """
        )
        _migrate_bookings(conn)


def _migrate_bookings(conn: sqlite3.Connection) -> None:
    cols = {row[1] for row in conn.execute("PRAGMA table_info(bookings)").fetchall()}
    if "calendar_uid" not in cols:
        conn.execute("ALTER TABLE bookings ADD COLUMN calendar_uid TEXT")
    if "calendar_href" not in cols:
        conn.execute("ALTER TABLE bookings ADD COLUMN calendar_href TEXT")
    if "confirm_key" not in cols:
        conn.execute("ALTER TABLE bookings ADD COLUMN confirm_key TEXT")
    conn.execute("CREATE UNIQUE INDEX IF NOT EXISTS ux_bookings_confirm_key ON bookings(confirm_key)")


def list_saved_brands() -> list[str]:
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT name FROM saved_brands ORDER BY name COLLATE NOCASE"
        ).fetchall()
    return [r["name"] for r in rows]


def add_saved_brand(name: str) -> None:
    n = name.strip()
    if len(n) < 2:
        return
    with get_conn() as conn:
        conn.execute("INSERT OR IGNORE INTO saved_brands (name) VALUES (?)", (n,))


def list_saved_models(brand_name: str) -> list[str]:
    with get_conn() as conn:
        rows = conn.execute(
            """
            SELECT model_name FROM saved_models
            WHERE brand_name = ?
            ORDER BY model_name COLLATE NOCASE
            """,
            (brand_name,),
        ).fetchall()
    return [r["model_name"] for r in rows]


def add_saved_model(brand_name: str, model_name: str) -> None:
    b = brand_name.strip()
    m = model_name.strip()
    if len(b) < 1 or len(m) < 1:
        return
    with get_conn() as conn:
        conn.execute(
            "INSERT OR IGNORE INTO saved_models (brand_name, model_name) VALUES (?, ?)",
            (b, m),
        )


def delete_saved_brand(name: str) -> None:
    n = name.strip()
    if len(n) < 2:
        return
    with get_conn() as conn:
        conn.execute("DELETE FROM saved_models WHERE brand_name = ?", (n,))
        conn.execute("DELETE FROM saved_brands WHERE name = ?", (n,))


def delete_saved_model(brand_name: str, model_name: str) -> None:
    b = brand_name.strip()
    m = model_name.strip()
    if len(b) < 1 or len(m) < 1:
        return
    with get_conn() as conn:
        conn.execute(
            "DELETE FROM saved_models WHERE brand_name = ? AND model_name = ?",
            (b, m),
        )


def list_brands_with_saved_models() -> list[str]:
    with get_conn() as conn:
        rows = conn.execute(
            """
            SELECT DISTINCT brand_name FROM saved_models
            ORDER BY brand_name COLLATE NOCASE
            """
        ).fetchall()
    return [r["brand_name"] for r in rows]


@dataclass
class BookingRow:
    id: int
    client_name: str
    phone: str
    make_model: str
    license_plate: str
    service: str
    master_name: Optional[str]
    start_at: str
    status: str


def _row_to_booking(row: sqlite3.Row) -> BookingRow:
    return BookingRow(
        id=row["id"],
        client_name=row["client_name"],
        phone=row["phone"],
        make_model=row["make_model"],
        license_plate=row["license_plate"],
        service=row["service"],
        master_name=row["master_name"],
        start_at=row["start_at"],
        status=row["status"],
    )


def create_booking(
    *,
    client_name: str,
    phone: str,
    make_model: str,
    service: str,
    start_at: datetime,
    license_plate: str = "",
    master_name: Optional[str] = None,
    duration_minutes: int = 120,
    admin_telegram_id: Optional[int] = None,
    confirm_key: Optional[str] = None,
    calendar_uid: Optional[str] = None,
    calendar_href: Optional[str] = None,
    notes: Optional[str] = None,
) -> int:
    end_at = start_at + timedelta(minutes=duration_minutes)
    with get_conn() as conn:
        if confirm_key:
            existing = conn.execute(
                "SELECT id FROM bookings WHERE confirm_key = ?",
                (confirm_key,),
            ).fetchone()
            if existing:
                return int(existing["id"])

        cur = conn.execute(
            "INSERT INTO clients (name, phone) VALUES (?, ?)",
            (client_name.strip(), phone.strip()),
        )
        client_id = int(cur.lastrowid)
        cur = conn.execute(
            "INSERT INTO vehicles (client_id, make_model, license_plate) VALUES (?, ?, ?)",
            (client_id, make_model.strip(), (license_plate or "").strip().upper()),
        )
        vehicle_id = int(cur.lastrowid)
        cur = conn.execute(
            """
            INSERT INTO bookings (
                client_id, vehicle_id, service, master_name, start_at, end_at,
                status, admin_telegram_id, confirm_key, google_event_id, sheet_row, notes,
                calendar_uid, calendar_href
            ) VALUES (?, ?, ?, ?, ?, ?, 'confirmed', ?, ?, NULL, NULL, ?, ?, ?)
            """,
            (
                client_id,
                vehicle_id,
                service.strip(),
                master_name,
                start_at.isoformat(timespec="minutes"),
                end_at.isoformat(timespec="minutes"),
                admin_telegram_id,
                confirm_key,
                notes,
                calendar_uid,
                calendar_href,
            ),
        )
        return int(cur.lastrowid)


def update_booking_calendar(
    booking_id: int,
    *,
    calendar_uid: Optional[str] = None,
    calendar_href: Optional[str] = None,
) -> None:
    sets: list[str] = ["updated_at = datetime('now')"]
    args: list[Any] = []
    if calendar_uid is not None:
        sets.append("calendar_uid = ?")
        args.append(calendar_uid)
    if calendar_href is not None:
        sets.append("calendar_href = ?")
        args.append(calendar_href)
    args.append(booking_id)
    with get_conn() as conn:
        conn.execute(
            f"UPDATE bookings SET {', '.join(sets)} WHERE id = ?",
            args,
        )


def update_booking_status(booking_id: int, status: str) -> None:
    with get_conn() as conn:
        conn.execute(
            "UPDATE bookings SET status = ?, updated_at = datetime('now') WHERE id = ?",
            (status, booking_id),
        )


def update_booking_fields(
    booking_id: int,
    *,
    client_name: Optional[str] = None,
    phone: Optional[str] = None,
    make_model: Optional[str] = None,
    license_plate: Optional[str] = None,
    service: Optional[str] = None,
    master_name: Optional[str] = None,
    start_at: Optional[datetime] = None,
    duration_minutes: int = 120,
) -> None:
    with get_conn() as conn:
        row = conn.execute(
            """
            SELECT b.client_id, b.vehicle_id, b.start_at
            FROM bookings b WHERE b.id = ?
            """,
            (booking_id,),
        ).fetchone()
        if not row:
            return
        client_id, vehicle_id, old_start = row["client_id"], row["vehicle_id"], row["start_at"]
        if client_name is not None:
            conn.execute("UPDATE clients SET name = ? WHERE id = ?", (client_name.strip(), client_id))
        if phone is not None:
            conn.execute("UPDATE clients SET phone = ? WHERE id = ?", (phone.strip(), client_id))
        if make_model is not None:
            conn.execute(
                "UPDATE vehicles SET make_model = ? WHERE id = ?",
                (make_model.strip(), vehicle_id),
            )
        if license_plate is not None:
            conn.execute(
                "UPDATE vehicles SET license_plate = ? WHERE id = ?",
                (license_plate.strip().upper(), vehicle_id),
            )
        b_sets: list[str] = ["updated_at = datetime('now')"]
        b_args: list[Any] = []
        if service is not None:
            b_sets.append("service = ?")
            b_args.append(service.strip())
        if master_name is not None:
            b_sets.append("master_name = ?")
            b_args.append(master_name)
        if start_at is not None:
            end_at = start_at + timedelta(minutes=duration_minutes)
            b_sets.append("start_at = ?")
            b_sets.append("end_at = ?")
            b_args.extend([start_at.isoformat(timespec="minutes"), end_at.isoformat(timespec="minutes")])
        if len(b_sets) > 1:
            b_args.append(booking_id)
            conn.execute(
                f"UPDATE bookings SET {', '.join(b_sets)} WHERE id = ?",
                b_args,
            )


def list_active_bookings_overlapping(
    start_at: datetime,
    end_at: datetime,
    *,
    exclude_booking_id: Optional[int] = None,
    duration_fallback_minutes: int = 120,
) -> list[BookingRow]:
    """
    Записи со статусом confirmed/rescheduled, интервал [start_at, end_at) которых
    пересекается с переданным [start_at, end_at).
    """
    new_s = start_at.isoformat(timespec="minutes")
    new_e = end_at.isoformat(timespec="minutes")
    with get_conn() as conn:
        fb = int(duration_fallback_minutes)
        sql = f"""
            SELECT b.id, c.name AS client_name, c.phone, v.make_model, v.license_plate,
                   b.service, b.master_name, b.start_at, b.status
            FROM bookings b
            JOIN clients c ON c.id = b.client_id
            JOIN vehicles v ON v.id = b.vehicle_id
            WHERE b.status IN ('confirmed', 'rescheduled')
              AND datetime(b.start_at) < datetime(?)
              AND datetime(
                    COALESCE(
                        b.end_at,
                        datetime(b.start_at, '+{fb} minutes')
                    )
                  ) > datetime(?)
        """
        params: list[Any] = [new_e, new_s]
        if exclude_booking_id is not None:
            sql += " AND b.id != ?"
            params.append(exclude_booking_id)
        sql += " ORDER BY b.start_at"
        rows = conn.execute(sql, params).fetchall()
    return [_row_to_booking(r) for r in rows]


def get_booking(booking_id: int) -> Optional[BookingRow]:
    with get_conn() as conn:
        row = conn.execute(
            """
            SELECT b.id, c.name AS client_name, c.phone, v.make_model, v.license_plate,
                   b.service, b.master_name, b.start_at, b.status
            FROM bookings b
            JOIN clients c ON c.id = b.client_id
            JOIN vehicles v ON v.id = b.vehicle_id
            WHERE b.id = ?
            """,
            (booking_id,),
        ).fetchone()
    return _row_to_booking(row) if row else None


def get_booking_calendar_refs(booking_id: int) -> tuple[Optional[str], Optional[str]]:
    with get_conn() as conn:
        row = conn.execute(
            "SELECT calendar_uid, calendar_href FROM bookings WHERE id = ?",
            (booking_id,),
        ).fetchone()
    if not row:
        return None, None
    return row["calendar_uid"], row["calendar_href"]


def list_recent_bookings(limit: int = 15) -> list[BookingRow]:
    with get_conn() as conn:
        rows = conn.execute(
            """
            SELECT b.id, c.name AS client_name, c.phone, v.make_model, v.license_plate,
                   b.service, b.master_name, b.start_at, b.status
            FROM bookings b
            JOIN clients c ON c.id = b.client_id
            JOIN vehicles v ON v.id = b.vehicle_id
            ORDER BY datetime(b.start_at) DESC
            LIMIT ?
            """,
            (limit,),
        ).fetchall()
    return [_row_to_booking(r) for r in rows]


def count_upcoming_bookings(now: Optional[datetime] = None) -> int:
    """Подтверждённые/перенесённые с датой начала не раньше сейчас."""
    now = now or datetime.now()
    now_s = now.isoformat(timespec="minutes")
    with get_conn() as conn:
        row = conn.execute(
            """
            SELECT COUNT(*) AS c FROM bookings b
            WHERE datetime(b.start_at) >= datetime(?)
              AND b.status IN ('confirmed', 'rescheduled')
            """,
            (now_s,),
        ).fetchone()
    return int(row["c"]) if row else 0


def list_upcoming_bookings_page(
    offset: int,
    limit: int,
    now: Optional[datetime] = None,
) -> list[BookingRow]:
    now = now or datetime.now()
    now_s = now.isoformat(timespec="minutes")
    with get_conn() as conn:
        rows = conn.execute(
            """
            SELECT b.id, c.name AS client_name, c.phone, v.make_model, v.license_plate,
                   b.service, b.master_name, b.start_at, b.status
            FROM bookings b
            JOIN clients c ON c.id = b.client_id
            JOIN vehicles v ON v.id = b.vehicle_id
            WHERE datetime(b.start_at) >= datetime(?)
              AND b.status IN ('confirmed', 'rescheduled')
            ORDER BY datetime(b.start_at) ASC
            LIMIT ? OFFSET ?
            """,
            (now_s, limit, offset),
        ).fetchall()
    return [_row_to_booking(r) for r in rows]


def count_completed_bookings() -> int:
    with get_conn() as conn:
        row = conn.execute(
            "SELECT COUNT(*) AS c FROM bookings WHERE status = 'completed'",
        ).fetchone()
    return int(row["c"]) if row else 0


def list_completed_bookings_page(offset: int, limit: int) -> list[BookingRow]:
    with get_conn() as conn:
        rows = conn.execute(
            """
            SELECT b.id, c.name AS client_name, c.phone, v.make_model, v.license_plate,
                   b.service, b.master_name, b.start_at, b.status
            FROM bookings b
            JOIN clients c ON c.id = b.client_id
            JOIN vehicles v ON v.id = b.vehicle_id
            WHERE b.status = 'completed'
            ORDER BY datetime(b.updated_at) DESC, datetime(b.start_at) DESC
            LIMIT ? OFFSET ?
            """,
            (limit, offset),
        ).fetchall()
    return [_row_to_booking(r) for r in rows]


def bookings_between(start: datetime, end: datetime) -> list[BookingRow]:
    with get_conn() as conn:
        rows = conn.execute(
            """
            SELECT b.id, c.name AS client_name, c.phone, v.make_model, v.license_plate,
                   b.service, b.master_name, b.start_at, b.status
            FROM bookings b
            JOIN clients c ON c.id = b.client_id
            JOIN vehicles v ON v.id = b.vehicle_id
            WHERE datetime(b.start_at) >= datetime(?) AND datetime(b.start_at) < datetime(?)
            ORDER BY b.start_at
            """,
            (start.isoformat(timespec="minutes"), end.isoformat(timespec="minutes")),
        ).fetchall()
    return [_row_to_booking(r) for r in rows]


def bookings_on_date(d: date) -> list[BookingRow]:
    start = datetime.combine(d, datetime.min.time())
    end = start + timedelta(days=1)
    return bookings_between(start, end)


def count_bookings_between(start: datetime, end: datetime) -> int:
    with get_conn() as conn:
        row = conn.execute(
            """
            SELECT COUNT(*) AS c FROM bookings
            WHERE datetime(start_at) >= datetime(?) AND datetime(start_at) < datetime(?)
            """,
            (start.isoformat(timespec="minutes"), end.isoformat(timespec="minutes")),
        ).fetchone()
    return int(row["c"]) if row else 0


def count_by_service_between(start: datetime, end: datetime) -> list[tuple[str, int]]:
    with get_conn() as conn:
        rows = conn.execute(
            """
            SELECT service, COUNT(*) AS c FROM bookings
            WHERE datetime(start_at) >= datetime(?) AND datetime(start_at) < datetime(?)
            GROUP BY service ORDER BY c DESC
            """,
            (start.isoformat(timespec="minutes"), end.isoformat(timespec="minutes")),
        ).fetchall()
    return [(r["service"], int(r["c"])) for r in rows]


def count_by_master_between(start: datetime, end: datetime) -> list[tuple[Optional[str], int]]:
    with get_conn() as conn:
        rows = conn.execute(
            """
            SELECT IFNULL(master_name, '—') AS m, COUNT(*) AS c FROM bookings
            WHERE datetime(start_at) >= datetime(?) AND datetime(start_at) < datetime(?)
            GROUP BY master_name ORDER BY c DESC
            """,
            (start.isoformat(timespec="minutes"), end.isoformat(timespec="minutes")),
        ).fetchall()
    return [(r["m"] if r["m"] != "—" else None, int(r["c"])) for r in rows]


def completed_between(start: datetime, end: datetime) -> list[BookingRow]:
    with get_conn() as conn:
        rows = conn.execute(
            """
            SELECT b.id, c.name AS client_name, c.phone, v.make_model, v.license_plate,
                   b.service, b.master_name, b.start_at, b.status
            FROM bookings b
            JOIN clients c ON c.id = b.client_id
            JOIN vehicles v ON v.id = b.vehicle_id
            WHERE b.status = 'completed'
              AND datetime(b.updated_at) >= datetime(?) AND datetime(b.updated_at) < datetime(?)
            ORDER BY b.updated_at
            """,
            (start.isoformat(timespec="seconds"), end.isoformat(timespec="seconds")),
        ).fetchall()
    return [_row_to_booking(r) for r in rows]


def no_show_since(days: int = 14) -> list[BookingRow]:
    since = datetime.now() - timedelta(days=days)
    with get_conn() as conn:
        rows = conn.execute(
            """
            SELECT b.id, c.name AS client_name, c.phone, v.make_model, v.license_plate,
                   b.service, b.master_name, b.start_at, b.status
            FROM bookings b
            JOIN clients c ON c.id = b.client_id
            JOIN vehicles v ON v.id = b.vehicle_id
            WHERE b.status = 'no_show' AND datetime(b.start_at) >= datetime(?)
            ORDER BY b.start_at DESC
            """,
            (since.isoformat(timespec="minutes"),),
        ).fetchall()
    return [_row_to_booking(r) for r in rows]


def open_or_cancelled() -> list[BookingRow]:
    """Незакрытые (ожидают) и отменённые за последние 30 дней."""
    since = datetime.now() - timedelta(days=30)
    with get_conn() as conn:
        rows = conn.execute(
            """
            SELECT b.id, c.name AS client_name, c.phone, v.make_model, v.license_plate,
                   b.service, b.master_name, b.start_at, b.status
            FROM bookings b
            JOIN clients c ON c.id = b.client_id
            JOIN vehicles v ON v.id = b.vehicle_id
            WHERE (b.status IN ('confirmed', 'rescheduled') AND datetime(b.start_at) >= datetime(?))
               OR (b.status = 'cancelled' AND datetime(b.updated_at) >= datetime(?))
            ORDER BY b.start_at
            """,
            (since.isoformat(timespec="minutes"), since.isoformat(timespec="minutes")),
        ).fetchall()
    return [_row_to_booking(r) for r in rows]


def master_bookings_month(master_substr: str, ref: Optional[datetime] = None) -> tuple[int, list[BookingRow]]:
    ref = ref or datetime.now()
    start = ref.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    if start.month == 12:
        end = start.replace(year=start.year + 1, month=1)
    else:
        end = start.replace(month=start.month + 1)
    sub = f"%{master_substr.strip().lower()}%"
    with get_conn() as conn:
        rows = conn.execute(
            """
            SELECT b.id, c.name AS client_name, c.phone, v.make_model, v.license_plate,
                   b.service, b.master_name, b.start_at, b.status
            FROM bookings b
            JOIN clients c ON c.id = b.client_id
            JOIN vehicles v ON v.id = b.vehicle_id
            WHERE datetime(b.start_at) >= datetime(?) AND datetime(b.start_at) < datetime(?)
              AND lower(IFNULL(b.master_name, '')) LIKE ?
            ORDER BY b.start_at
            """,
            (start.isoformat(timespec="minutes"), end.isoformat(timespec="minutes"), sub),
        ).fetchall()
    lst = [_row_to_booking(r) for r in rows]
    return len(lst), lst


def client_stats_between(start: datetime, end: datetime) -> tuple[int, int]:
    """Новые клиенты (первый визит в периоде) и повторные (был раньше)."""
    with get_conn() as conn:
        new_rows = conn.execute(
            """
            SELECT COUNT(DISTINCT b.client_id) AS c FROM bookings b
            JOIN clients cl ON cl.id = b.client_id
            WHERE datetime(b.start_at) >= datetime(?) AND datetime(b.start_at) < datetime(?)
              AND NOT EXISTS (
                SELECT 1 FROM bookings b2
                WHERE b2.client_id = b.client_id
                  AND datetime(b2.start_at) < datetime(?)
              )
            """,
            (
                start.isoformat(timespec="minutes"),
                end.isoformat(timespec="minutes"),
                start.isoformat(timespec="minutes"),
            ),
        ).fetchone()
        total_clients = conn.execute(
            """
            SELECT COUNT(DISTINCT client_id) AS c FROM bookings
            WHERE datetime(start_at) >= datetime(?) AND datetime(start_at) < datetime(?)
            """,
            (start.isoformat(timespec="minutes"), end.isoformat(timespec="minutes")),
        ).fetchone()
    new_c = int(new_rows["c"]) if new_rows else 0
    total = int(total_clients["c"]) if total_clients else 0
    return new_c, max(0, total - new_c)


def popular_cars(limit: int = 10, *, only_processed: bool = False) -> list[tuple[str, int]]:
    """
    Топ авто по полю vehicles.make_model.
    only_processed=True -> только записи со статусом completed.
    """
    where = "WHERE b.status = 'completed'" if only_processed else ""
    with get_conn() as conn:
        rows = conn.execute(
            f"""
            SELECT v.make_model AS make_model, COUNT(*) AS c
            FROM bookings b
            JOIN vehicles v ON v.id = b.vehicle_id
            {where}
            GROUP BY v.make_model
            ORDER BY c DESC, v.make_model COLLATE NOCASE ASC
            LIMIT ?
            """,
            (max(1, int(limit)),),
        ).fetchall()
    return [(r["make_model"], int(r["c"])) for r in rows]
