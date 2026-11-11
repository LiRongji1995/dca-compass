"""SQLite 存储：日线行情 + 每日估值快照。"""

import sqlite3
from datetime import date
from pathlib import Path

import pandas as pd

from .providers.base import PRICE_COLUMNS

SCHEMA = """
CREATE TABLE IF NOT EXISTS prices (
    symbol TEXT NOT NULL,
    date TEXT NOT NULL,
    open REAL, high REAL, low REAL, close REAL, adj_close REAL, volume REAL,
    PRIMARY KEY (symbol, date)
);
CREATE TABLE IF NOT EXISTS valuations (
    symbol TEXT NOT NULL,
    date TEXT NOT NULL,
    pe REAL,
    forward_pe REAL,
    PRIMARY KEY (symbol, date)
);
"""


class Storage:
    def __init__(self, path: Path | str):
        if str(path) != ":memory:":
            Path(path).parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(path)
        self.conn.executescript(SCHEMA)

    def last_date(self, symbol: str) -> date | None:
        row = self.conn.execute("SELECT MAX(date) FROM prices WHERE symbol = ?", (symbol,)).fetchone()
        return date.fromisoformat(row[0]) if row[0] else None

    def upsert_prices(self, symbol: str, df: pd.DataFrame, replace_all: bool = False) -> int:
        rows = [
            (symbol, d.isoformat(), *(None if pd.isna(v) else float(v) for v in r))
            for d, r in zip(df.index, df[PRICE_COLUMNS].itertuples(index=False))
        ]
        with self.conn:
            if replace_all:
                self.conn.execute("DELETE FROM prices WHERE symbol = ?", (symbol,))
            self.conn.executemany(
                "INSERT OR REPLACE INTO prices VALUES (?, ?, ?, ?, ?, ?, ?, ?)", rows
            )
        return len(rows)

    def load_prices(self, symbol: str) -> pd.DataFrame:
        df = pd.read_sql(
            "SELECT * FROM prices WHERE symbol = ? ORDER BY date",
            self.conn, params=(symbol,), parse_dates=["date"],
        )
        return df.drop(columns="symbol").set_index("date")

    def save_valuation(self, symbol: str, day: date, pe: float | None, forward_pe: float | None):
        with self.conn:
            self.conn.execute(
                "INSERT OR REPLACE INTO valuations VALUES (?, ?, ?, ?)",
                (symbol, day.isoformat(), pe, forward_pe),
            )

    def load_valuations(self, symbol: str) -> pd.DataFrame:
        df = pd.read_sql(
            "SELECT date, pe, forward_pe FROM valuations WHERE symbol = ? ORDER BY date",
            self.conn, params=(symbol,), parse_dates=["date"],
        )
        return df.set_index("date")
