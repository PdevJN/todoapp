import json
from pathlib import Path

import pytest

from todoapp.repository.config_repository import (
    AppConfig,
    ConfigRepository,
    Theme,
    dark_mode_value_to_theme,
    theme_to_dark_mode_value,
)


def test_load_returns_auto_theme_by_default_when_file_missing(tmp_path: Path) -> None:
    repository = ConfigRepository(path=tmp_path / "config.json")
    config = repository.load()
    assert config == AppConfig(theme="auto")


def test_save_then_load_roundtrips_theme(tmp_path: Path) -> None:
    repository = ConfigRepository(path=tmp_path / "config.json")
    repository.save(AppConfig(theme="dark"))

    loaded = repository.load()

    assert loaded == AppConfig(theme="dark")


def test_load_falls_back_to_auto_for_unknown_theme_value(tmp_path: Path) -> None:
    # 同値分析: スキーマ外の不正な値(異常系)は「auto」に丸められる
    path = tmp_path / "config.json"
    path.write_text(json.dumps({"theme": "unknown"}), encoding="utf-8")
    repository = ConfigRepository(path=path)

    assert repository.load() == AppConfig(theme="auto")


def test_load_falls_back_to_auto_when_theme_key_is_missing(tmp_path: Path) -> None:
    path = tmp_path / "config.json"
    path.write_text(json.dumps({}), encoding="utf-8")
    repository = ConfigRepository(path=path)

    assert repository.load() == AppConfig(theme="auto")


def test_load_returns_sunday_week_start_by_default_when_file_missing(tmp_path: Path) -> None:
    repository = ConfigRepository(path=tmp_path / "config.json")
    assert repository.load().week_start == "sunday"


def test_save_then_load_roundtrips_week_start(tmp_path: Path) -> None:
    repository = ConfigRepository(path=tmp_path / "config.json")
    repository.save(AppConfig(theme="auto", week_start="monday"))

    loaded = repository.load()

    assert loaded == AppConfig(theme="auto", week_start="monday")


def test_load_falls_back_to_sunday_for_unknown_week_start_value(tmp_path: Path) -> None:
    path = tmp_path / "config.json"
    path.write_text(json.dumps({"week_start": "unknown"}), encoding="utf-8")
    repository = ConfigRepository(path=path)

    assert repository.load().week_start == "sunday"


def test_save_preserves_both_theme_and_week_start_together(tmp_path: Path) -> None:
    # テーマ・週の開始曜日いずれか一方だけを変更して保存しても、
    # もう一方の設定を消してしまわないことを確認する
    repository = ConfigRepository(path=tmp_path / "config.json")
    repository.save(AppConfig(theme="dark", week_start="monday"))

    loaded = repository.load()

    assert loaded == AppConfig(theme="dark", week_start="monday")


def test_load_returns_eight_hours_standard_work_hours_by_default(tmp_path: Path) -> None:
    repository = ConfigRepository(path=tmp_path / "config.json")
    assert repository.load().standard_work_hours == 8.0

    path = tmp_path / "legacy.json"
    path.write_text(json.dumps({"theme": "dark"}), encoding="utf-8")
    assert ConfigRepository(path=path).load().standard_work_hours == 8.0


def test_save_then_load_roundtrips_standard_work_hours(tmp_path: Path) -> None:
    repository = ConfigRepository(path=tmp_path / "config.json")
    repository.save(AppConfig(standard_work_hours=7.5))

    assert repository.load().standard_work_hours == 7.5


def test_load_falls_back_to_default_for_invalid_standard_work_hours(tmp_path: Path) -> None:
    # 同値分析: 数値以外・0以下・真偽値(異常系)は既定の8.0に丸められる
    for invalid in ("8", 0, -1, None, True):
        path = tmp_path / "config.json"
        path.write_text(json.dumps({"standard_work_hours": invalid}), encoding="utf-8")
        assert ConfigRepository(path=path).load().standard_work_hours == 8.0


@pytest.mark.parametrize(
    ("raw", "expected"),
    [("light", "light"), ("dark", "dark"), ("auto", "auto"), ("", "auto"), (None, "auto"), (1, "auto")],
)
def test_load_parses_theme_equivalence_classes(tmp_path: Path, raw: object, expected: str) -> None:
    path = tmp_path / "config.json"
    path.write_text(json.dumps({"theme": raw}), encoding="utf-8")

    assert ConfigRepository(path=path).load().theme == expected


@pytest.mark.parametrize(
    ("theme", "dark_mode"),
    [("light", False), ("dark", True), ("auto", None)],
)
def test_theme_and_dark_mode_value_convert_both_ways(theme: Theme, dark_mode: bool | None) -> None:
    assert theme_to_dark_mode_value(theme) is dark_mode
    assert dark_mode_value_to_theme(dark_mode) == theme


@pytest.mark.parametrize(
    ("raw", "expected"),
    [(0.1, 0.1), (24, 24.0), (8, 8.0), (0, 8.0), (-0.1, 8.0), ("8", 8.0), (None, 8.0), (True, 8.0), (False, 8.0)],
)
def test_load_standard_work_hours_boundaries(tmp_path: Path, raw: object, expected: float) -> None:
    # 0以下は既定値、0より大きい最小側の値と整数はそのまま採用する。真偽値は数値として扱わない
    path = tmp_path / "config.json"
    path.write_text(json.dumps({"standard_work_hours": raw}), encoding="utf-8")

    assert ConfigRepository(path=path).load().standard_work_hours == expected
