from datetime import date, datetime

from todoapp.domain.record_layout import snap_move, snap_resize, truncate_to_minute

DAY = date(2026, 9, 30)


def at(hour: int, minute: int = 0, second: int = 0) -> datetime:
    return datetime(2026, 9, 30, hour, minute, second)


def test_truncate_to_minute_drops_seconds_and_microseconds() -> None:
    assert truncate_to_minute(datetime(2026, 9, 30, 10, 5, 59, 999)) == at(10, 5)


def test_snap_move_without_overlap_keeps_position_and_truncates_seconds() -> None:
    result = snap_move(at(10, 0, 40), at(11, 0, 40), [(at(8), at(9))], DAY)

    assert result == (at(10, 0), at(11, 0))


def test_snap_move_truncates_both_ends_to_minute() -> None:
    result = snap_move(at(10, 0, 40), at(10, 30, 50), [], DAY)

    assert result == (at(10, 0), at(10, 30))


def test_snap_move_keeps_duration_of_record_shorter_than_one_minute() -> None:
    result = snap_move(at(10, 0, 10), at(10, 0, 50), [], DAY)

    assert result == (at(10, 0), at(10, 0, 40))


def test_snap_move_keeps_duration() -> None:
    result = snap_move(at(10, 0), at(10, 45), [], DAY)

    assert result is not None
    assert result[1] - result[0] == at(10, 45) - at(10, 0)


def test_snap_move_overlapping_previous_sticks_to_its_end_with_second_precision() -> None:
    previous = (at(9), at(9, 30, 17))

    result = snap_move(at(9, 20), at(10, 20), [previous], DAY)

    assert result == (at(9, 30, 17), at(10, 30, 17))


def test_snap_move_overlapping_next_sticks_to_its_start_with_second_precision() -> None:
    following = (at(11, 0, 5), at(12))

    result = snap_move(at(10, 20), at(11, 20), [following], DAY)

    assert result == (at(10, 0, 5), at(11, 0, 5))


def test_snap_move_picks_nearer_side_when_both_sides_fit() -> None:
    previous = (at(9), at(10))
    following = (at(11, 30), at(12, 30))

    # 1時間20分のバーを10:20に置くと直後と重なる。前に寄せた位置(10:10-11:30)の方が近い
    result = snap_move(at(10, 20), at(11, 40), [previous, following], DAY)

    assert result == (at(10, 10), at(11, 30))


def test_snap_move_falls_back_to_other_side_when_nearest_does_not_fit() -> None:
    previous = (at(9), at(10))
    following = (at(10, 30), at(12))

    # 前(10:00)と後(10:30)の間は30分しか無く、1時間のバーは収まらないため後ろへ
    result = snap_move(at(10, 10), at(11, 10), [previous, following], DAY)

    assert result == (at(12), at(13))


def test_snap_move_returns_none_when_no_room_on_either_side() -> None:
    blocker = (at(0), at(23, 59))

    assert snap_move(at(10), at(11), [blocker], DAY) is None


def test_snap_move_outside_of_day_returns_none() -> None:
    assert snap_move(at(23, 30), datetime(2026, 10, 1, 0, 30), [], DAY) is None
    assert snap_move(datetime(2026, 9, 29, 23, 30), at(0, 30), [], DAY) is None


def test_snap_resize_end_without_overlap_truncates_seconds() -> None:
    result = snap_resize("end", at(11, 0, 30), at(10), [], DAY)

    assert result == (at(10), at(11))


def test_snap_resize_start_without_overlap_truncates_seconds() -> None:
    result = snap_resize("start", at(9, 0, 30), at(10), [], DAY)

    assert result == (at(9), at(10))


def test_snap_resize_end_clamps_to_next_start() -> None:
    following = (at(11, 0, 20), at(12))

    result = snap_resize("end", at(11, 30), at(10), [following], DAY)

    assert result == (at(10), at(11, 0, 20))


def test_snap_resize_start_clamps_to_previous_end() -> None:
    previous = (at(8), at(9, 0, 20))

    result = snap_resize("start", at(8, 30), at(10), [previous], DAY)

    assert result == (at(9, 0, 20), at(10))


def test_snap_resize_ignores_records_on_the_other_side() -> None:
    previous = (at(8), at(9))

    result = snap_resize("end", at(11), at(10), [previous], DAY)

    assert result == (at(10), at(11))


def test_snap_resize_shorter_than_one_minute_returns_none() -> None:
    assert snap_resize("end", at(10, 0, 30), at(10), [], DAY) is None
    assert snap_resize("start", at(9, 59, 59), at(10), [], DAY) is not None
    assert snap_resize("start", at(10), at(10), [], DAY) is None


def test_snap_resize_clamps_to_day_bounds() -> None:
    assert snap_resize("end", datetime(2026, 10, 1, 1), at(23), [], DAY) == (at(23), datetime(2026, 10, 1))
    assert snap_resize("start", datetime(2026, 9, 29, 22), at(1), [], DAY) == (at(0), at(1))
