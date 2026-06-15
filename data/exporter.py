"""資料匯出：依上市/上櫃/ETF 分類輸出 .txt 至 stock_data/。"""
from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any

import config
from data.universe import Category, StockMeta, category_of


def _format_lines(records: list[dict[str, Any]], meta_index: dict[str, StockMeta]) -> list[str]:
    header = (
        f"{'代號':<8} {'名稱':<12} {'市場':<8} {'產業':<14} "
        f"{'收盤':>10} {'漲跌':>8} {'漲跌幅%':>8} "
        f"{'成交額':>14} {'成交量':>10} {'昨量比':>8}"
    )
    lines = [header, "-" * 100]
    for rec in sorted(records, key=lambda r: r.get("code", "")):
        code = rec.get("code", "")
        meta = meta_index.get(code)
        name = meta.name if meta else ""
        market = meta.market if meta else ""
        industry = meta.industry if meta else ""
        lines.append(
            f"{code:<8} {name:<12} {market:<8} {industry:<14} "
            f"{rec.get('close', 0):>10.2f} "
            f"{rec.get('change_price', 0):>8.2f} "
            f"{rec.get('change_rate', 0):>8.2f} "
            f"{rec.get('total_amount', 0):>14,} "
            f"{rec.get('total_volume', 0):>10,} "
            f"{rec.get('volume_ratio', 0):>8.2f}"
        )
    return lines


def _group_by_category(
    records: list[dict[str, Any]],
    meta_index: dict[str, StockMeta],
) -> dict[Category, list[dict[str, Any]]]:
    groups: dict[Category, list[dict[str, Any]]] = {
        "listed": [],
        "otc": [],
        "etf": [],
    }
    for rec in records:
        code = rec.get("code", "")
        meta = meta_index.get(code)
        if meta is None:
            continue
        groups[category_of(meta)].append(rec)
    return groups


def export_snapshots(
    records: list[dict[str, Any]],
    meta_index: dict[str, StockMeta],
    timestamp: datetime | None = None,
) -> list[Path]:
    """依分類匯出至 stock_data/{category}_{YYYYMMDD_HHMMSS}.txt，回傳寫入路徑。"""
    config.STOCK_DATA_DIR.mkdir(parents=True, exist_ok=True)
    ts = (timestamp or datetime.now()).strftime("%Y%m%d_%H%M%S")
    groups = _group_by_category(records, meta_index)
    written: list[Path] = []

    for category in config.EXPORT_CATEGORIES:
        group_records = groups[category]
        if not group_records:
            continue
        path = config.STOCK_DATA_DIR / f"{category}_{ts}.txt"
        lines = [
            f"# 台股行情匯出 {datetime.now().isoformat(timespec='seconds')}",
            f"# 分類: {category} | 筆數: {len(group_records)}",
            *_format_lines(group_records, meta_index),
        ]
        path.write_text("\n".join(lines), encoding="utf-8")
        written.append(path)

    return written
