from __future__ import annotations

import csv
import io
import json
from datetime import date
from pathlib import Path

import httpx

from todoapp.repository.safe_io import atomic_write_text

CAO_HOLIDAY_CSV_URL = "https://www8.cao.go.jp/chosei/shukujitsu/syukujitsu.csv"

DEFAULT_HOLIDAY_PATH = Path.home() / ".todoapp" / "holidays.json"


def parse_holiday_csv(raw: bytes) -> dict[date, str]:
    """内閣府配布の祝日CSV(Shift_JIS)を`日付 -> 祝日名`の辞書に変換する。"""
    text = raw.decode("cp932")
    rows = csv.reader(io.StringIO(text))
    next(rows, None)  # ヘッダー行をスキップ

    holidays: dict[date, str] = {}
    for row in rows:
        if len(row) < 2:
            continue
        raw_date, name = row[0].strip(), row[1].strip()
        if not raw_date or not name:
            continue
        year, month, day = (int(part) for part in raw_date.split("/"))
        holidays[date(year, month, day)] = name
    return holidays


def fetch_holiday_csv(url: str = CAO_HOLIDAY_CSV_URL, timeout: float = 10.0) -> bytes:
    # httpxはCA証明書にcertifiを既定で使うため、urllib+sslのように一部のPython実行環境
    # (uv管理のCPython等、OSのCA証明書ストアを参照できない環境)でのSSL検証エラーを
    # 意識する必要が無い
    response = httpx.get(url, headers={"User-Agent": "todoapp/1.0"}, timeout=timeout)
    response.raise_for_status()
    return response.content


class HolidayRepository:
    def __init__(self, path: Path = DEFAULT_HOLIDAY_PATH) -> None:
        self._path = path

    def load(self) -> dict[date, str]:
        if not self._path.exists():
            return {}
        raw: dict[str, str] = json.loads(self._path.read_text(encoding="utf-8"))
        holidays: dict[date, str] = {}
        for key, name in raw.items():
            try:
                holidays[date.fromisoformat(key)] = name
            except ValueError:
                continue
        return holidays

    def save(self, holidays: dict[date, str]) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        payload = {d.isoformat(): name for d, name in holidays.items()}
        atomic_write_text(self._path, json.dumps(payload, ensure_ascii=False, indent=2))
