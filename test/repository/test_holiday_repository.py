import json
from datetime import date
from pathlib import Path

from todoapp.repository.holiday_repository import HolidayRepository, parse_holiday_csv

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
