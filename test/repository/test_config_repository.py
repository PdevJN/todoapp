import json
from pathlib import Path

from todoapp.repository.config_repository import AppConfig, ConfigRepository


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
