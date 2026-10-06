from __future__ import annotations

from collections.abc import Sequence
from datetime import date, datetime, time, timedelta
from typing import Literal

Interval = tuple[datetime, datetime]
Edge = Literal["start", "end"]

_MIN_DURATION = timedelta(minutes=1)


def truncate_to_minute(value: datetime) -> datetime:
    return value.replace(second=0, microsecond=0)


def _day_bounds(day: date) -> Interval:
    start = datetime.combine(day, time.min)
    return start, start + timedelta(days=1)


def _overlaps(start: datetime, end: datetime, others: Sequence[Interval]) -> list[Interval]:
    return [other for other in others if other[0] < end and other[1] > start]


def snap_move(start: datetime, end: datetime, others: Sequence[Interval], day: date) -> Interval | None:
    """バー全体を移動した結果を返す。所要時間は維持し、隣接記録と重なる場合はその境界(秒精度)へ密着させる。

    どちらにも配置できない場合(当日を出る、他の記録と重なる)は`None`を返す。
    """
    new_start = truncate_to_minute(start)
    duration = truncate_to_minute(end) - new_start
    if duration <= timedelta(0):
        # 1分未満の記録は、秒を切り捨てると所要時間が消えるため元の所要時間を使う
        duration = end - start
    new_end = new_start + duration
    day_start, day_end = _day_bounds(day)

    def fits(candidate: datetime) -> bool:
        candidate_end = candidate + duration
        return day_start <= candidate and candidate_end <= day_end and not _overlaps(candidate, candidate_end, others)

    if fits(new_start):
        return new_start, new_end
    overlapped = _overlaps(new_start, new_end, others)
    if not overlapped:
        return None

    before = min(other[0] for other in overlapped) - duration
    after = max(other[1] for other in overlapped)
    candidates = sorted((before, after), key=lambda candidate: abs(candidate - new_start))
    for candidate in candidates:
        if fits(candidate):
            return candidate, candidate + duration
    return None


def snap_resize(edge: Edge, new_time: datetime, fixed_time: datetime, others: Sequence[Interval], day: date) -> Interval | None:
    """片端をリサイズした結果を返す。動かした端のみ、隣接記録の境界または当日の範囲へ寄せる。

    所要時間が1分未満になる場合は`None`を返す。
    """
    day_start, day_end = _day_bounds(day)
    moved = truncate_to_minute(new_time)
    if edge == "start":
        moved = max(moved, day_start)
        for _, other_end in _overlaps(moved, fixed_time, others):
            moved = max(moved, other_end)
        result = (moved, fixed_time)
    else:
        moved = min(moved, day_end)
        for other_start, _ in _overlaps(fixed_time, moved, others):
            moved = min(moved, other_start)
        result = (fixed_time, moved)
    return result if result[1] - result[0] >= _MIN_DURATION else None
