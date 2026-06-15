"""標的宇宙：解析 stock_index 清單，建立全市場標的清單。"""
from __future__ import annotations

import csv
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

import config

Category = Literal["listed", "otc", "etf"]


@dataclass(frozen=True)
class StockMeta:
    code: str
    name: str
    market: str
    industry: str
    kind: str


def category_of(meta: StockMeta) -> Category:
    """依 CLAUDE.md 職責 4 分類：上市 / 上櫃 / ETF。"""
    if meta.kind == "ETF":
        return "etf"
    if meta.market == "上櫃":
        return "otc"
    if meta.market.startswith("上市"):
        return "listed"
    return "listed"


def _read_rows(path: Path) -> list[dict[str, str]]:
    last_err: Exception | None = None
    for enc in config.FILE_ENCODINGS:
        try:
            with path.open("r", encoding=enc, newline="") as fh:
                reader = csv.DictReader(fh, delimiter="\t")
                return list(reader)
        except (UnicodeDecodeError, UnicodeError) as err:
            last_err = err
    raise RuntimeError(f"無法讀取清單檔 {path}") from last_err


def _first_value(row: dict[str, str], *keys: str) -> str:
    for key in keys:
        if key in row and row[key] is not None:
            value = row[key].strip()
            if value:
                return value
    return ""


def _parse_file(path: Path, kind: str, default_industry: str) -> list[StockMeta]:
    metas: list[StockMeta] = []
    for row in _read_rows(path):
        code = _first_value(row, "代號", "有價證券代號")
        name = _first_value(row, "名稱")
        if not code or not name:
            continue
        market = _first_value(row, "市場別") or ("上市" if kind == "ETF" else "")
        industry = _first_value(row, "產業別") or default_industry
        metas.append(
            StockMeta(code=code, name=name, market=market, industry=industry, kind=kind)
        )
    return metas


def load_universe(
    include_listed: bool = True,
    include_otc: bool = True,
    include_etf: bool = True,
) -> list[StockMeta]:
    metas: list[StockMeta] = []
    if include_listed:
        metas += _parse_file(config.LISTED_FILE, kind="STK", default_industry="其他")
    if include_otc:
        metas += _parse_file(config.OTC_FILE, kind="STK", default_industry="其他")
    if include_etf:
        metas += _parse_file(config.ETF_FILE, kind="ETF", default_industry="ETF")

    seen: set[str] = set()
    unique: list[StockMeta] = []
    for meta in metas:
        if meta.code in seen:
            continue
        seen.add(meta.code)
        unique.append(meta)
    return unique


def build_meta_index(metas: list[StockMeta]) -> dict[str, StockMeta]:
    return {meta.code: meta for meta in metas}


if __name__ == "__main__":
    universe = load_universe()
    print(f"標的總數：{len(universe)}")
    counts: dict[str, int] = {"listed": 0, "otc": 0, "etf": 0}
    for m in universe:
        counts[category_of(m)] += 1
    print("分類分布：", counts)
