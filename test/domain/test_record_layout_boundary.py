"""`domain/record_layout.py`の吸着ロジックを、当日の端・1分・密着の境界値で網羅する。"""

from datetime import date, datetime, timedelta

import pytest

from todoapp.domain.record_layout import snap_move, snap_resize

DAY = date(2026, 9, 30)
MIDNIGHT = datetime(2026, 9, 30, 0, 0)
NEXT_MIDNIGHT = MIDNIGHT + timedelta(days=1)


def at(hour: int, minute: int = 0, second: int = 0) -> datetime:
    return datetime(2026, 9, 30, hour, minute, second)


# --- snap_move: 当日の端 ------------------------------------------------------------------


@pytest.mark.parametrize(
    ("start", "end", "expected"),
    [
        (MIDNIGHT, at(1), (MIDNIGHT, at(1))),  # 当日の先頭ちょうど
        (MIDNIGHT - timedelta(minutes=1), at(0, 59), None),  # 先頭の1分前(当日を出る)
        (at(23), NEXT_MIDNIGHT, (at(23), NEXT_MIDNIGHT)),  # 当日の末尾ちょうど
        (at(23, 1), NEXT_MIDNIGHT + timedelta(minutes=1), None),  # 末尾を1分超える
    ],
)
def test_snap_move_day_edges(start: datetime, end: datetime, expected: tuple[datetime, datetime] | None) -> None:
    assert snap_move(start, end, [], DAY) == expected


def test_snap_move_full_day_duration_fits_only_at_midnight() -> None:
    assert snap_move(MIDNIGHT, NEXT_MIDNIGHT, [], DAY) == (MIDNIGHT, NEXT_MIDNIGHT)
    assert snap_move(at(0, 1), NEXT_MIDNIGHT + timedelta(minutes=1), [], DAY) is None


# --- snap_move: 隣接記録との境界 ----------------------------------------------------------


@pytest.mark.parametrize(
    ("start", "end", "expected"),
    [
        (at(9), at(10), (at(9), at(10))),  # 前の記録の終了にちょうど接する(重なりなし)
        (at(11), at(12), (at(11), at(12))),  # 次の記録の開始にちょうど接する(重なりなし)
        (at(9, 59), at(10, 59), (at(9), at(10))),  # 後ろの記録に1分重なる -> 距離の近い前側(9:00-10:00)へ
        (at(10, 1), at(11, 1), (at(11), at(12))),  # 後ろの記録に1分重なる -> 距離の近い後ろ側へ
    ],
)
def test_snap_move_adjacent_boundaries(start: datetime, end: datetime, expected: tuple[datetime, datetime]) -> None:
    others = [(at(8), at(9)), (at(10), at(11))]
    assert snap_move(start, end, others, DAY) == expected


# --- snap_resize --------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("new_end", "expected"),
    [
        (at(10, 1), (at(10), at(10, 1))),  # ちょうど1分(最小の所要時間)
        (at(10, 0, 59), None),  # 秒を切り捨てると0分 -> 1分未満
        (at(10), None),  # 開始と同じ(0分)
        (at(9, 59), None),  # 開始より前(負の所要時間)
    ],
)
def test_snap_resize_end_minimum_duration_boundary(new_end: datetime, expected: tuple[datetime, datetime] | None) -> None:
    assert snap_resize("end", new_end, at(10), [], DAY) == expected


@pytest.mark.parametrize(
    ("new_start", "expected"),
    [
        (at(9, 59), (at(9, 59), at(10))),  # ちょうど1分
        (at(9, 59, 59), (at(9, 59), at(10))),  # 秒は切り捨てられ1分になる
        (at(10), None),  # 0分
        (at(10, 1), None),  # 終了より後
    ],
)
def test_snap_resize_start_minimum_duration_boundary(
    new_start: datetime, expected: tuple[datetime, datetime] | None
) -> None:
    assert snap_resize("start", new_start, at(10), [], DAY) == expected


def test_snap_resize_end_clamps_to_day_end_exactly() -> None:
    assert snap_resize("end", NEXT_MIDNIGHT + timedelta(hours=3), at(23), [], DAY) == (at(23), NEXT_MIDNIGHT)


def test_snap_resize_start_clamps_to_day_start_exactly() -> None:
    assert snap_resize("start", MIDNIGHT - timedelta(hours=3), at(1), [], DAY) == (MIDNIGHT, at(1))


def test_snap_resize_end_touching_next_record_is_not_clamped() -> None:
    # 次の記録の開始にちょうど接する位置(重なり0)は、そのまま採用する
    assert snap_resize("end", at(11), at(10), [(at(11), at(12))], DAY) == (at(10), at(11))


def test_snap_resize_end_sticks_to_second_precision_start_of_next_record() -> None:
    assert snap_resize("end", at(11, 30), at(10), [(at(11, 0, 20), at(12))], DAY) == (at(10), at(11, 0, 20))


def test_snap_resize_clamped_to_less_than_one_minute_returns_none() -> None:
    # 密着の結果、所要時間が1分未満になる場合は配置できない
    assert snap_resize("end", at(11), at(10), [(at(10, 0, 30), at(12))], DAY) is None
