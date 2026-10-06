import json
from datetime import date
from pathlib import Path
from typing import Any

import httpx
import pytest

from todoapp.repository.holiday_repository import HolidayRepository, fetch_holiday_csv, parse_holiday_csv

_SAMPLE_CSV = (
    "国民の祝日・休日月日,国民の祝日・休日名称\r\n"
    "1955/1/1,元日\r\n"
    "1955/1/15,成人の日\r\n"
    "2024/2/23,天皇誕生日\r\n"
)


def _sample_bytes() -> bytes:
    return _SAMPLE_CSV.encode("cp932")


def test_parse_holiday_csv_skips_header_and_parses_rows() -> None:
    holidays = parse_holiday_csv(_sample_bytes())

    assert holidays == {
        date(1955, 1, 1): "元日",
        date(1955, 1, 15): "成人の日",
        date(2024, 2, 23): "天皇誕生日",
    }


def test_parse_holiday_csv_ignores_blank_lines() -> None:
    raw = ("国民の祝日・休日月日,国民の祝日・休日名称\r\n" "2024/1/1,元日\r\n" "\r\n").encode("cp932")

    assert parse_holiday_csv(raw) == {date(2024, 1, 1): "元日"}


def test_parse_holiday_csv_returns_empty_dict_for_header_only() -> None:
    raw = "国民の祝日・休日月日,国民の祝日・休日名称\r\n".encode("cp932")

    assert parse_holiday_csv(raw) == {}


def test_repository_load_returns_empty_dict_when_file_missing(tmp_path: Path) -> None:
    repository = HolidayRepository(path=tmp_path / "holidays.json")
    assert repository.load() == {}


def test_repository_save_then_load_roundtrips(tmp_path: Path) -> None:
    repository = HolidayRepository(path=tmp_path / "holidays.json")
    holidays = {date(2024, 1, 1): "元日", date(2024, 2, 23): "天皇誕生日"}

    repository.save(holidays)

    assert repository.load() == holidays


def test_repository_load_ignores_unparsable_date_keys(tmp_path: Path) -> None:
    # 同値分析: 手動で壊れたファイルを置かれた場合(異常系)でもクラッシュせず無視する
    path = tmp_path / "holidays.json"
    path.write_text(json.dumps({"not-a-date": "元日"}), encoding="utf-8")
    repository = HolidayRepository(path=path)

    assert repository.load() == {}


def test_parse_holiday_csv_skips_rows_with_missing_date_or_name() -> None:
    raw = (
        "国民の祝日・休日月日,国民の祝日・休日名称\r\n"
        "2024/1/1,元日\r\n"
        "2024/1/2,\r\n"  # 名称なし
        ",成人の日\r\n"  # 日付なし
        "2024/1/3\r\n"  # 列が足りない
    ).encode("cp932")

    assert parse_holiday_csv(raw) == {date(2024, 1, 1): "元日"}


def test_fetch_holiday_csv_returns_response_body_and_sends_user_agent(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: dict[str, Any] = {}

    def fake_get(url: str, *, headers: dict[str, str], timeout: float) -> httpx.Response:
        calls.update(url=url, headers=headers, timeout=timeout)
        return httpx.Response(200, content=b"body", request=httpx.Request("GET", url))

    monkeypatch.setattr(httpx, "get", fake_get)

    assert fetch_holiday_csv("https://example.test/h.csv", timeout=3.0) == b"body"
    assert calls == {"url": "https://example.test/h.csv", "headers": {"User-Agent": "todoapp/1.0"}, "timeout": 3.0}


def test_fetch_holiday_csv_raises_on_http_error(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_get(url: str, *, headers: dict[str, str], timeout: float) -> httpx.Response:
        return httpx.Response(500, request=httpx.Request("GET", url))

    monkeypatch.setattr(httpx, "get", fake_get)

    with pytest.raises(httpx.HTTPStatusError):
        fetch_holiday_csv("https://example.test/h.csv")
