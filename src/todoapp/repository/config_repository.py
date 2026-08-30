from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

Theme = Literal["auto", "light", "dark"]

DEFAULT_CONFIG_PATH = Path.home() / ".todoapp" / "config.json"

def _parse_theme(value: Any) -> Theme:
    if value == "light":
        return "light"
    if value == "dark":
        return "dark"
    return "auto"


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


class ConfigRepository:
    def __init__(self, path: Path = DEFAULT_CONFIG_PATH) -> None:
        self._path = path

    def load(self) -> AppConfig:
        if not self._path.exists():
            return AppConfig()
        raw: dict[str, Any] = json.loads(self._path.read_text(encoding="utf-8"))
        return AppConfig(theme=_parse_theme(raw.get("theme")))

    def save(self, config: AppConfig) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        payload = {"theme": config.theme}
        self._path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
