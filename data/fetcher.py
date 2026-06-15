"""資料抓取：串接 Shioaji API 取得即時行情（含限流防禦）。"""
from __future__ import annotations

import os
import time
from collections import deque
from dataclasses import dataclass
from threading import Lock
from typing import Any

import shioaji as sj
from dotenv import load_dotenv

import config


@dataclass(frozen=True)
class UsageInfo:
    connections: int
    bytes_used: int
    limit_bytes: int
    remaining_bytes: int

    @property
    def used_mb(self) -> float:
        return self.bytes_used / 1024 / 1024

    @property
    def limit_mb(self) -> float:
        return self.limit_bytes / 1024 / 1024

    @property
    def remaining_mb(self) -> float:
        return self.remaining_bytes / 1024 / 1024

    @property
    def usage_ratio(self) -> float:
        if self.limit_bytes <= 0:
            return 0.0
        return self.bytes_used / self.limit_bytes


class RateLimiter:
    """滑動視窗速率限制器。"""

    def __init__(
        self,
        window_sec: float = config.RATE_WINDOW_SEC,
        max_calls: int = config.RATE_MAX_CALLS,
    ) -> None:
        self.window_sec = window_sec
        self.max_calls = max_calls
        self._timestamps: deque[float] = deque()
        self._lock = Lock()

    def acquire(self) -> None:
        with self._lock:
            now = time.monotonic()
            self._purge(now)
            if len(self._timestamps) >= self.max_calls:
                sleep_sec = self.window_sec - (now - self._timestamps[0])
                if sleep_sec > 0:
                    time.sleep(sleep_sec)
                now = time.monotonic()
                self._purge(now)
            self._timestamps.append(now)

    def _purge(self, now: float) -> None:
        while self._timestamps and now - self._timestamps[0] >= self.window_sec:
            self._timestamps.popleft()


class ShioajiFetcher:
    def __init__(self) -> None:
        self.api: sj.Shioaji | None = None
        self.rate_limiter = RateLimiter()
        self._logged_in = False

    def login(self) -> None:
        if self._logged_in and self.api is not None:
            return

        load_dotenv(config.PROJECT_ROOT / ".env")
        api_key = os.getenv("SJ_API_KEY", "").strip()
        secret_key = os.getenv("SJ_SEC_KEY", "").strip()
        if not api_key or not secret_key:
            raise RuntimeError("缺少 SJ_API_KEY 或 SJ_SEC_KEY，請在 .env 設定")

        production = os.getenv("SJ_PRODUCTION", "false").lower() in ("true", "1", "yes")
        self.api = sj.Shioaji(simulation=not production)
        self.api.login(
            api_key=api_key,
            secret_key=secret_key,
            fetch_contract=True,
            contracts_timeout=config.CONTRACTS_TIMEOUT_MS,
            subscribe_trade=False,
        )
        self._logged_in = True

    def logout(self) -> None:
        if self.api is not None and self._logged_in:
            self.api.logout()
        self.api = None
        self._logged_in = False

    def usage(self) -> UsageInfo:
        self._ensure_logged_in()
        assert self.api is not None
        raw = self.api.usage()
        return UsageInfo(
            connections=int(raw.connections),
            bytes_used=int(raw.bytes),
            limit_bytes=int(raw.limit_bytes),
            remaining_bytes=int(raw.remaining_bytes),
        )

    def resolve_contracts(self, codes: list[str]) -> tuple[list[Any], list[str]]:
        self._ensure_logged_in()
        assert self.api is not None

        contracts: list[Any] = []
        missing: list[str] = []
        for code in codes:
            try:
                contract = self.api.Contracts.Stocks[code]
            except (KeyError, AttributeError, TypeError):
                missing.append(code)
                continue
            if contract is None:
                missing.append(code)
                continue
            contracts.append(contract)
        return contracts, missing

    def fetch_snapshots(self, codes: list[str]) -> tuple[list[dict[str, Any]], list[str]]:
        self._ensure_logged_in()
        assert self.api is not None

        contracts, missing = self.resolve_contracts(codes)
        if not contracts:
            return [], missing

        records: list[dict[str, Any]] = []
        batch_size = config.SNAPSHOT_BATCH_SIZE
        for start in range(0, len(contracts), batch_size):
            batch = [c for c in contracts[start : start + batch_size] if c is not None]
            if not batch:
                continue
            self.rate_limiter.acquire()
            snapshots = self.api.snapshots(batch)
            for snap in snapshots or []:
                if snap is None or not getattr(snap, "code", None):
                    continue
                record = _snapshot_to_dict(snap)
                if record["close"] > 0 or record["total_amount"] > 0:
                    records.append(record)
            if start + batch_size < len(contracts):
                time.sleep(config.INTER_BATCH_SLEEP_SEC)

        return records, missing

    def _ensure_logged_in(self) -> None:
        if not self._logged_in or self.api is None:
            raise RuntimeError("尚未登入 Shioaji，請先呼叫 login()")


def _snapshot_to_dict(snap: Any) -> dict[str, Any]:
    def _float(value: Any) -> float:
        try:
            return float(value) if value is not None else 0.0
        except (TypeError, ValueError):
            return 0.0

    def _int(value: Any) -> int:
        try:
            return int(value) if value is not None else 0
        except (TypeError, ValueError):
            return 0

    return {
        "code": str(snap.code),
        "close": _float(snap.close),
        "change_price": _float(snap.change_price),
        "change_rate": _float(snap.change_rate),
        "total_amount": _int(snap.total_amount),
        "total_volume": _int(snap.total_volume),
        "open": _float(snap.open),
        "high": _float(snap.high),
        "low": _float(snap.low),
        "volume_ratio": _float(snap.volume_ratio),
    }


def _run_smoke_test() -> None:
    test_codes = ["2330", "2317", "0050"]
    fetcher = ShioajiFetcher()
    print("登入 Shioaji...")
    fetcher.login()

    usage_before = fetcher.usage()
    print(
        f"流量（抓取前）: {usage_before.used_mb:.2f} MB / "
        f"{usage_before.limit_mb:.0f} MB，剩餘 {usage_before.remaining_mb:.2f} MB"
    )

    print(f"抓取 snapshots: {test_codes}")
    records, missing = fetcher.fetch_snapshots(test_codes)
    if missing:
        print(f"找不到商品檔: {missing}")

    for rec in records:
        print(
            f"  {rec['code']}: close={rec['close']}, "
            f"change_rate={rec['change_rate']}%, total_amount={rec['total_amount']}"
        )

    usage_after = fetcher.usage()
    print(
        f"流量（抓取後）: {usage_after.used_mb:.2f} MB / "
        f"{usage_after.limit_mb:.0f} MB，剩餘 {usage_after.remaining_mb:.2f} MB"
    )

    fetcher.logout()
    print("Smoke test 完成。")


if __name__ == "__main__":
    _run_smoke_test()
