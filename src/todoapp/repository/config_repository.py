from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

Theme = Literal["auto", "light", "dark"]
WeekStart = Literal["sunday", "monday"]

DEFAULT_CONFIG_PATH = Path.home() / ".todoapp" / "config.json"
DEFAULT_STANDARD_WORK_HOURS = 8.0

def _parse_theme(value: Any) -> Theme:
    if value == "light":
        return "light"
    if value == "dark":
        return "dark"
    return "auto"


def _parse_week_start(value: Any) -> WeekStart:
    if value == "monday":
        return "monday"
    return "sunday"


def _parse_standard_work_hours(value: Any) -> float:
    # boolはintのサブクラスのため、数値として扱わないよう先に除外する
    if isinstance(value, bool) or not isinstance(value, int | float) or value <= 0:
        return DEFAULT_STANDARD_WORK_HOURS
    return float(value)


def theme_to_dark_mode_value(theme: Theme) -> bool | None:
    if theme == "light":
        return False
    if theme == "dark":
        return True
    return None


def dark_mode_value_to_theme(value: bool | None) -> Theme:
    if value is False:
        return "light"
    if value is True:
        return "dark"
    return "auto"


@dataclass
class AppConfig:
    theme: Theme = "auto"
    week_start: WeekStart = "sunday"
    standard_work_hours: float = DEFAULT_STANDARD_WORK_HOURS  # 1日の標準労働時間(時間)


class ConfigRepository:
    def __init__(self, path: Path = DEFAULT_CONFIG_PATH) -> None:
        self._path = path

    def load(self) -> AppConfig:
        if not self._path.exists():
            return AppConfig()
        raw: dict[str, Any] = json.loads(self._path.read_text(encoding="utf-8"))
        return AppConfig(
            theme=_parse_theme(raw.get("theme")),
            week_start=_parse_week_start(raw.get("week_start")),
            standard_work_hours=_parse_standard_work_hours(raw.get("standard_work_hours")),
        )

    def save(self, config: AppConfig) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "theme": config.theme,
            "week_start": config.week_start,
            "standard_work_hours": config.standard_work_hours,
        }
        self._path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
