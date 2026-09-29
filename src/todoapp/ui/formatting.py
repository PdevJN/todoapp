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


def estimate_to_hours_minutes(estimate_hours: float) -> tuple[int, int]:
    """見積り(時間の小数)を、分単位に丸めた(時間, 分)に分ける。"""
    total_minutes = max(round(estimate_hours * 60), 0)
    hours, minutes = divmod(total_minutes, 60)
    return hours, minutes


def hours_minutes_to_estimate(hours: float, minutes: float) -> float:
    """時間(小数可)と分を、分単位に丸めた見積り(時間の小数)に変換する。"""
    total_minutes = max(round(hours * 60 + minutes), 0)
    return total_minutes / 60


def format_estimate(estimate_hours: float) -> str:
    hours, minutes = estimate_to_hours_minutes(estimate_hours)
    if hours and minutes:
        return f"{hours}時間{minutes}分"
    if hours:
        return f"{hours}時間"
    return f"{minutes}分"
