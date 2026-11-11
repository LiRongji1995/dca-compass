"""读取 config/ 下的 YAML 配置。"""

from dataclasses import dataclass
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]
CONFIG_DIR = ROOT / "config"


@dataclass(frozen=True)
class Symbol:
    symbol: str
    kind: str  # index / sector / stock
    sector: str | None = None
    name: str | None = None


def _read_yaml(name: str) -> dict:
    with open(CONFIG_DIR / name, encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def load_settings() -> dict:
    return _read_yaml("settings.yaml")


def load_watchlist() -> list[Symbol]:
    raw = _read_yaml("watchlist.yaml")
    out = [Symbol(s, "index", name=n) for s, n in (raw.get("index_etfs") or {}).items()]
    out += [Symbol(s, "sector", sector=sec) for s, sec in (raw.get("sector_etfs") or {}).items()]
    for sec, syms in (raw.get("stocks") or {}).items():
        out += [Symbol(s, "stock", sector=sec) for s in syms]
    return out


def db_path() -> Path:
    return ROOT / load_settings()["data"]["db_path"]


def transactions_path() -> Path:
    """优先用个人的 transactions.csv，不存在时退回示例文件。"""
    real = CONFIG_DIR / "transactions.csv"
    return real if real.exists() else CONFIG_DIR / "transactions.example.csv"
