from __future__ import annotations

SCHEDULE_LABELS = {
    "daily": "毎日",
    "weekly": "週次",
    "monthly": "月次",
    "one_time": "当日",
}


# 完了したアイテムの表示(取り消し線とグレーのフォント)。画面をまたいで共通にする
DONE_TEXT_CLASSES = "line-through text-gray-400"
DONE_FILTER_LABELS = {"active": "未完了のみ", "all": "すべて", "done": "完了のみ"}


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


def format_estimate_cell(estimate_seconds: float | None, today_estimate_seconds: float | None) -> str:
    """集計画面の見積り欄。本日だけの限定見積りがあれば括弧書きで併記する。"""
    text = format_duration(estimate_seconds) if estimate_seconds is not None else "-"
    if today_estimate_seconds is None:
        return text
    return f"{text} ({format_duration(today_estimate_seconds)})"


def format_work_balance(standard_work_hours: float, planned_seconds: float) -> tuple[str, bool]:
    """標準労働時間から本日の見積り合計を引いた残りの表示と、超過したか(ちょうどは超過にしない)を返す。"""
    balance_seconds = round(standard_work_hours * 3600) - round(planned_seconds)
    text = format_estimate(abs(balance_seconds) / 3600)
    if balance_seconds < 0:
        return f"超過 {text}", True
    return f"残り {text}", False


def format_gap(gap_seconds: float | None) -> str:
    """見積りとのズレ(累積経過時間 - 見積り)を符号付きのHH:MM:SSにする。ズレが無ければ`-`。"""
    if gap_seconds is None:
        return "-"
    rounded = round(gap_seconds)
    if rounded == 0:
        return format_duration(0)
    return f"{'+' if rounded > 0 else '-'}{format_duration(abs(rounded))}"


_GAP_OVER_RGB = "229, 57, 53"
_GAP_UNDER_RGB = "30, 136, 229"
_GAP_MIN_ALPHA = 0.08
_GAP_ALPHA_RANGE = 0.52


def gap_background(gap_seconds: float | None, estimate_seconds: float | None) -> str | None:
    """GAPの背景色。超過は赤、余りは青で、見積りに対するズレの比率が大きいほど濃い(±100%で最大)。"""
    if gap_seconds is None or not estimate_seconds or round(gap_seconds) == 0:
        return None
    ratio = min(abs(gap_seconds) / estimate_seconds, 1.0)
    alpha = round(_GAP_MIN_ALPHA + _GAP_ALPHA_RANGE * ratio, 3)
    rgb = _GAP_OVER_RGB if gap_seconds > 0 else _GAP_UNDER_RGB
    return f"rgba({rgb}, {alpha})"
