from __future__ import annotations

SCHEDULE_LABELS = {
    "daily": "毎日",
    "weekly": "週次",
    "monthly": "月次",
    "one_time": "当日",
}


def format_duration(seconds: float) -> str:
    total_seconds = max(int(seconds), 0)
    hours, remainder = divmod(total_seconds, 3600)
    minutes, secs = divmod(remainder, 60)
    return f"{hours:02d}:{minutes:02d}:{secs:02d}"
