"""全域設定：路徑、Shioaji 限流防禦參數、Treemap 顯示參數。"""
from __future__ import annotations

from pathlib import Path

PROJECT_ROOT: Path = Path(__file__).resolve().parent
STOCK_INDEX_DIR: Path = PROJECT_ROOT / "stock_index"
STOCK_DATA_DIR: Path = PROJECT_ROOT / "stock_data"

LISTED_FILE: Path = STOCK_INDEX_DIR / "Listed_Company_list.txt"
OTC_FILE: Path = STOCK_INDEX_DIR / "OTC_Company_list.txt"
ETF_FILE: Path = STOCK_INDEX_DIR / "ETF_list.txt"

FILE_ENCODINGS: tuple[str, ...] = ("utf-8-sig", "utf-8", "cp950", "big5")

# Shioaji 防禦性參數
SNAPSHOT_BATCH_SIZE: int = 450
RATE_WINDOW_SEC: float = 5.0
RATE_MAX_CALLS: int = 40
INTER_BATCH_SLEEP_SEC: float = 0.1
CONTRACTS_TIMEOUT_MS: int = 15000
USAGE_WARN_REMAINING_BYTES: int = 50 * 1024 * 1024
MIN_AUTO_REFRESH_SEC: int = 15

# Treemap 配色（台股慣例：紅漲綠跌）
TREEMAP_COLORSCALE: list[list] = [
    [0.0, "#1ca85c"],
    [0.5, "#3a3f4b"],
    [1.0, "#e8473f"],
]
DEFAULT_COLOR_RANGE_PCT: float = 5.0

# 匯出檔案分類前綴
EXPORT_CATEGORIES: tuple[str, ...] = ("listed", "otc", "etf")
