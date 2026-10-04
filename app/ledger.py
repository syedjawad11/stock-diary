"""SQLite stock ledger. Balances are derived from immutable movement rows."""

import json
import re
import sqlite3
import threading
from datetime import date, datetime, timedelta, timezone
from typing import Callable, Dict, List, Optional, Tuple

from app.models import Direction, Movement, NewProduct, PostLine, Product, StockRow, UNITS


MAX_CUSTOM_PRODUCTS = 30


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class LedgerError(Exception):
    code = "ledger_error"


class UnknownProduct(LedgerError):
    code = "unknown_product"


class DuplicateProduct(LedgerError):
    code = "duplicate_product"


class TooManyProducts(LedgerError):
    code = "too_many_products"


class InsufficientStock(LedgerError):
    code = "insufficient_stock"

    def __init__(self, product_id: str, available: int, requested: int) -> None:
        self.product_id = product_id
        self.available = available
        self.requested = requested
        super().__init__(
            "{} has {} available; {} requested".format(product_id, available, requested)
        )


class AlreadyReversed(LedgerError):
    code = "already_reversed"


class NotFound(LedgerError):
    code = "not_found"


class Ledger:
    def __init__(
        self,
        db_path: str,
        catalogue: List[Product],
        now: Callable[[], datetime] = utcnow,
    ) -> None:
        self.catalogue = list(catalogue)
        self._products = {product.id: product for product in catalogue}
        if len(self._products) != len(catalogue):
            raise ValueError("duplicate product id")
        self._now = now
        self._lock = threading.Lock()
        self._db = sqlite3.connect(db_path, check_same_thread=False, isolation_level=None)
        self._db.row_factory = sqlite3.Row
        self._db.execute("PRAGMA foreign_keys = ON")
        self._db.executescript(
            """
            CREATE TABLE IF NOT EXISTS visitors (
                id TEXT PRIMARY KEY,
                last_seen TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS visitor_products (
                visitor_id TEXT NOT NULL REFERENCES visitors(id) ON DELETE CASCADE,
                id TEXT NOT NULL,
                name_en TEXT NOT NULL,
                name_ur TEXT NOT NULL,
                aliases TEXT NOT NULL,
                unit TEXT NOT NULL,
                low_threshold INTEGER NOT NULL,
                created_key TEXT NOT NULL,
                created_at TEXT NOT NULL,
                PRIMARY KEY(visitor_id, id),
                UNIQUE(visitor_id, created_key)
            );
            CREATE TABLE IF NOT EXISTS posts (
                id INTEGER PRIMARY KEY,
                visitor_id TEXT NOT NULL REFERENCES visitors(id) ON DELETE CASCADE,
                key TEXT NOT NULL,
                UNIQUE(visitor_id, key)
            );
            CREATE TABLE IF NOT EXISTS movements (
                id INTEGER PRIMARY KEY,
                visitor_id TEXT NOT NULL REFERENCES visitors(id) ON DELETE CASCADE,
                product_id TEXT NOT NULL,
                qty INTEGER NOT NULL CHECK(qty > 0),
                direction TEXT NOT NULL CHECK(direction IN ('in', 'out')),
                note TEXT NOT NULL,
                created_at TEXT NOT NULL,
                reverses INTEGER UNIQUE,
                post_id INTEGER REFERENCES posts(id) ON DELETE CASCADE,
                line_index INTEGER,
                is_opening INTEGER NOT NULL DEFAULT 0
            );
            CREATE INDEX IF NOT EXISTS movements_balance
                ON movements(visitor_id, product_id);
            CREATE INDEX IF NOT EXISTS movements_recent
                ON movements(visitor_id, id DESC);
            """
        )

    def _timestamp(self) -> str:
        return self._as_utc(self._now()).isoformat()

    @staticmethod
    def _as_utc(value: datetime) -> datetime:
        if value.tzinfo is None:
            value = value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc)

    def _begin(self) -> None:
        self._db.execute("BEGIN IMMEDIATE")

    def _seed(self, visitor_id: str, timestamp: str) -> None:
        for product in self.catalogue:
            if product.opening_qty:
                self._db.execute(
                    """INSERT INTO movements
                       (visitor_id, product_id, qty, direction, note, created_at, is_opening)
                       VALUES (?, ?, ?, 'in', 'opening stock', ?, 1)""",
                    (visitor_id, product.id, product.opening_qty, timestamp),
                )

    def _ensure_locked(self, visitor_id: str, timestamp: str) -> bool:
        cursor = self._db.execute(
            "INSERT OR IGNORE INTO visitors(id, last_seen) VALUES (?, ?)",
            (visitor_id, timestamp),
        )
        created = cursor.rowcount == 1
        if created:
            self._seed(visitor_id, timestamp)
        else:
            self._db.execute(
                "UPDATE visitors SET last_seen = ? WHERE id = ?", (timestamp, visitor_id)
            )
        return created

    def ensure_visitor(self, visitor_id: str) -> bool:
        with self._lock:
            self._begin()
            try:
                created = self._ensure_locked(visitor_id, self._timestamp())
                self._db.commit()
                return created
            except Exception:
                self._db.rollback()
                raise

    def reset(self, visitor_id: str) -> None:
        with self._lock:
            self._begin()
            try:
                timestamp = self._timestamp()
                self._db.execute(
                    "INSERT OR IGNORE INTO visitors(id, last_seen) VALUES (?, ?)",
                    (visitor_id, timestamp),
                )
                self._db.execute("DELETE FROM movements WHERE visitor_id = ?", (visitor_id,))
                self._db.execute("DELETE FROM posts WHERE visitor_id = ?", (visitor_id,))
                self._db.execute("DELETE FROM visitor_products WHERE visitor_id = ?", (visitor_id,))
                self._db.execute(
                    "UPDATE visitors SET last_seen = ? WHERE id = ?", (timestamp, visitor_id)
                )
                self._seed(visitor_id, timestamp)
                self._db.commit()
            except Exception:
                self._db.rollback()
                raise

    @staticmethod
    def _custom_product(row: sqlite3.Row) -> Product:
        return Product(
            id=row["id"],
            name_en=row["name_en"],
            name_ur=row["name_ur"],
            aliases=json.loads(row["aliases"]),
            unit=row["unit"],
            low_threshold=row["low_threshold"],
            opening_qty=0,
        )

    def _catalogue_locked(self, visitor_id: str) -> List[Product]:
        rows = self._db.execute(
            "SELECT * FROM visitor_products WHERE visitor_id = ? ORDER BY created_at, rowid",
            (visitor_id,),
        ).fetchall()
        return list(self.catalogue) + [self._custom_product(row) for row in rows]

    def catalogue_for(self, visitor_id: str) -> List[Product]:
        with self._lock:
            return self._catalogue_locked(visitor_id)

    def add_product(self, visitor_id: str, new: NewProduct, key: str) -> Product:
        with self._lock:
            self._begin()
            try:
                timestamp = self._timestamp()
                self._ensure_locked(visitor_id, timestamp)
                prior = self._db.execute(
                    "SELECT * FROM visitor_products WHERE visitor_id = ? AND created_key = ?",
                    (visitor_id, key),
                ).fetchone()
                if prior is not None:
                    self._db.commit()
                    return self._custom_product(prior)

                name_en = " ".join(new.name_en.split())
                if not name_en:
                    raise ValueError("name_en must not be empty")
                name_ur = new.name_ur.strip() or name_en
                if new.unit not in UNITS:
                    raise ValueError("invalid product unit")
                aliases = []
                for value in new.aliases:
                    alias = " ".join(value.lower().split())
                    if alias and len(alias) <= 40 and alias not in aliases:
                        aliases.append(alias)
                name_aliases = [name_en.lower()]
                if name_ur.casefold() != name_en.casefold():
                    name_aliases.append(name_ur)
                for alias in name_aliases:
                    if alias and alias not in aliases:
                        aliases.append(alias)

                custom_names = self._db.execute(
                    "SELECT name_en FROM visitor_products WHERE visitor_id = ?", (visitor_id,)
                ).fetchall()
                if any(product.name_en.casefold() == name_en.casefold()
                       for product in self.catalogue) or any(
                    row["name_en"].casefold() == name_en.casefold() for row in custom_names
                ):
                    raise DuplicateProduct(name_en)
                count = self._db.execute(
                    "SELECT COUNT(*) FROM visitor_products WHERE visitor_id = ?", (visitor_id,)
                ).fetchone()[0]
                if count >= MAX_CUSTOM_PRODUCTS:
                    raise TooManyProducts(visitor_id)

                slug = "-".join(re.findall(r"[a-z0-9]+", name_en.lower()))[:30].rstrip("-") or "item"
                base_id = "custom-" + slug
                product_id = base_id
                suffix = 2
                while product_id in self._products or self._db.execute(
                    "SELECT 1 FROM visitor_products WHERE visitor_id = ? AND id = ?",
                    (visitor_id, product_id),
                ).fetchone() is not None:
                    product_id = "{}-{}".format(base_id, suffix)
                    suffix += 1
                self._db.execute(
                    """INSERT INTO visitor_products
                       (visitor_id, id, name_en, name_ur, aliases, unit,
                        low_threshold, created_key, created_at)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (visitor_id, product_id, name_en, name_ur, json.dumps(aliases),
                     new.unit, new.low_threshold, key, timestamp),
                )
                self._db.commit()
                return Product(
                    id=product_id, name_en=name_en, name_ur=name_ur,
                    aliases=aliases, unit=new.unit,
                    low_threshold=new.low_threshold, opening_qty=0,
                )
            except Exception:
                self._db.rollback()
                raise

    def _check_product(self, visitor_id: str, product_id: str) -> None:
        if product_id in self._products:
            return
        if self._db.execute(
            "SELECT 1 FROM visitor_products WHERE visitor_id = ? AND id = ?",
            (visitor_id, product_id),
        ).fetchone() is None:
            raise UnknownProduct(product_id)

    def _balance(self, visitor_id: str, product_id: str) -> int:
        row = self._db.execute(
            """SELECT COALESCE(SUM(CASE direction WHEN 'in' THEN qty ELSE -qty END), 0)
               FROM movements WHERE visitor_id = ? AND product_id = ?""",
            (visitor_id, product_id),
        ).fetchone()
        return int(row[0])

    def balance(self, visitor_id: str, product_id: str) -> int:
        with self._lock:
            self._check_product(visitor_id, product_id)
            return self._balance(visitor_id, product_id)

    def stock(self, visitor_id: str) -> List[StockRow]:
        with self._lock:
            catalogue = self._catalogue_locked(visitor_id)
            rows = self._db.execute(
                """SELECT product_id,
                          SUM(CASE direction WHEN 'in' THEN qty ELSE -qty END) AS qty
                   FROM movements WHERE visitor_id = ? GROUP BY product_id""",
                (visitor_id,),
            ).fetchall()
            quantities = {row["product_id"]: int(row["qty"]) for row in rows}
            return [
                StockRow(
                    product=product,
                    qty=quantities.get(product.id, 0),
                    is_low=quantities.get(product.id, 0) <= product.low_threshold,
                )
                for product in catalogue
            ]

    def preview(self, visitor_id: str, lines: List[PostLine]) -> List[Tuple[int, int]]:
        with self._lock:
            for line in lines:
                self._check_product(visitor_id, line.product_id)
            running: Dict[str, int] = {}
            result = []
            for line in lines:
                before = running.setdefault(
                    line.product_id, self._balance(visitor_id, line.product_id)
                )
                after = before + (line.qty if line.direction == Direction.IN else -line.qty)
                result.append((before, after))
                running[line.product_id] = after
            return result

    @staticmethod
    def _movement(row: sqlite3.Row) -> Movement:
        return Movement(
            id=row["id"],
            product_id=row["product_id"],
            qty=row["qty"],
            direction=row["direction"],
            note=row["note"],
            created_at=row["created_at"],
            reverses=row["reverses"],
            reversed_by=row["reversed_by"],
        )

    _SELECT = """SELECT m.id, m.product_id, m.qty, m.direction, m.note,
                       m.created_at, m.reverses, r.id AS reversed_by
                FROM movements AS m LEFT JOIN movements AS r ON r.reverses = m.id"""

    def post(
        self, visitor_id: str, lines: List[PostLine], note: str, key: str
    ) -> List[Movement]:
        with self._lock:
            self._begin()
            try:
                prior = self._db.execute(
                    "SELECT id FROM posts WHERE visitor_id = ? AND key = ?",
                    (visitor_id, key),
                ).fetchone()
                if prior is not None:
                    rows = self._db.execute(
                        self._SELECT + " WHERE m.post_id = ? ORDER BY m.line_index",
                        (prior["id"],),
                    ).fetchall()
                    self._db.commit()
                    return [self._movement(row) for row in rows]
                for line in lines:
                    self._check_product(visitor_id, line.product_id)
                timestamp = self._timestamp()
                self._ensure_locked(visitor_id, timestamp)
                post_id = self._db.execute(
                    "INSERT INTO posts(visitor_id, key) VALUES (?, ?)",
                    (visitor_id, key),
                ).lastrowid
                running: Dict[str, int] = {}
                for index, line in enumerate(lines):
                    available = running.setdefault(
                        line.product_id, self._balance(visitor_id, line.product_id)
                    )
                    after = available + (
                        line.qty if line.direction == Direction.IN else -line.qty
                    )
                    if after < 0:
                        raise InsufficientStock(line.product_id, available, line.qty)
                    running[line.product_id] = after
                    self._db.execute(
                        """INSERT INTO movements
                           (visitor_id, product_id, qty, direction, note,
                            created_at, post_id, line_index)
                           VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                        (
                            visitor_id, line.product_id, line.qty,
                            line.direction.value, note, timestamp, post_id, index,
                        ),
                    )
                rows = self._db.execute(
                    self._SELECT + " WHERE m.post_id = ? ORDER BY m.line_index",
                    (post_id,),
                ).fetchall()
                self._db.commit()
                return [self._movement(row) for row in rows]
            except Exception:
                self._db.rollback()
                raise

    def undo(self, visitor_id: str, movement_id: int) -> Movement:
        with self._lock:
            self._begin()
            try:
                row = self._db.execute(
                    "SELECT * FROM movements WHERE id = ? AND visitor_id = ?",
                    (movement_id, visitor_id),
                ).fetchone()
                if row is None:
                    raise NotFound(movement_id)
                if row["reverses"] is not None or self._db.execute(
                    "SELECT 1 FROM movements WHERE reverses = ?", (movement_id,)
                ).fetchone() is not None:
                    raise AlreadyReversed(movement_id)
                if row["direction"] == Direction.IN.value:
                    available = self._balance(visitor_id, row["product_id"])
                    if available < row["qty"]:
                        raise InsufficientStock(row["product_id"], available, row["qty"])
                    direction = Direction.OUT.value
                else:
                    direction = Direction.IN.value
                new_id = self._db.execute(
                    """INSERT INTO movements
                       (visitor_id, product_id, qty, direction, note, created_at, reverses)
                       VALUES (?, ?, ?, ?, ?, ?, ?)""",
                    (
                        visitor_id, row["product_id"], row["qty"], direction,
                        "reversal of #{}".format(movement_id), self._timestamp(),
                        movement_id,
                    ),
                ).lastrowid
                result = self._db.execute(
                    self._SELECT + " WHERE m.id = ?", (new_id,)
                ).fetchone()
                self._db.commit()
                return self._movement(result)
            except Exception:
                self._db.rollback()
                raise

    def recent(self, visitor_id: str, limit: int = 10) -> List[Movement]:
        with self._lock:
            rows = self._db.execute(
                self._SELECT +
                " WHERE m.visitor_id = ? AND m.is_opening = 0 ORDER BY m.id DESC LIMIT ?",
                (visitor_id, max(0, limit)),
            ).fetchall()
            return [self._movement(row) for row in rows]

    def today(self, visitor_id: str, day: date) -> List[Movement]:
        start = datetime(day.year, day.month, day.day, tzinfo=timezone.utc)
        end = start + timedelta(days=1)
        with self._lock:
            rows = self._db.execute(
                self._SELECT +
                " WHERE m.visitor_id = ? AND m.is_opening = 0 "
                "AND m.created_at >= ? AND m.created_at < ? ORDER BY m.id DESC",
                (visitor_id, start.isoformat(), end.isoformat()),
            ).fetchall()
            return [self._movement(row) for row in rows]

    def purge_inactive(
        self, older_than_hours: int = 24, now: Optional[datetime] = None
    ) -> int:
        current = self._as_utc(now if now is not None else self._now())
        cutoff = (current - timedelta(hours=older_than_hours)).isoformat()
        with self._lock:
            self._begin()
            try:
                count = self._db.execute(
                    "SELECT COUNT(*) FROM visitors WHERE last_seen < ?", (cutoff,)
                ).fetchone()[0]
                self._db.execute("DELETE FROM visitors WHERE last_seen < ?", (cutoff,))
                self._db.commit()
                return count
            except Exception:
                self._db.rollback()
                raise
