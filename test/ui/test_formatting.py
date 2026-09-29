from todoapp.ui.formatting import (
    estimate_to_hours_minutes,
    format_duration,
    format_estimate,
    format_gap,
    gap_background,
    hours_minutes_to_estimate,
)


def test_format_duration_at_zero_boundary() -> None:
    # 境界値分析: 経過時間の下限0秒
    assert format_duration(0) == "00:00:00"


def test_format_duration_clamps_negative_values_to_zero() -> None:
    # 同値分析: 負数(異常値)は0秒と同じ表示に丸められる
    assert format_duration(-1) == "00:00:00"


def test_format_duration_seconds_only() -> None:
    # 同値クラス: 60秒未満(秒のみ)
    assert format_duration(45) == "00:00:45"


def test_format_duration_at_one_minute_boundary() -> None:
    # 境界値分析: 59秒(分未満の上限)と60秒(1分ちょうど)の境目
    assert format_duration(59) == "00:00:59"
    assert format_duration(60) == "00:01:00"


def test_format_duration_minutes_and_seconds() -> None:
    # 同値クラス: 1分以上60分未満
    assert format_duration(125) == "00:02:05"


def test_format_duration_at_one_hour_boundary() -> None:
    # 境界値分析: 3599秒(1時間未満の上限)と3600秒(1時間ちょうど)の境目
    assert format_duration(3599) == "00:59:59"
    assert format_duration(3600) == "01:00:00"


def test_format_duration_hours_minutes_seconds() -> None:
    # 同値クラス: 1時間以上
    assert format_duration(3661) == "01:01:01"


def test_format_duration_does_not_wrap_hours_beyond_two_digits() -> None:
    # 境界値分析: 2桁の範囲を超える時間数(実行時間が長時間に及ぶケース)でも
    # ゼロ埋めが壊れず、そのままの桁数で表示されることを確認する
    assert format_duration(100 * 3600) == "100:00:00"


def test_format_duration_truncates_fractional_seconds() -> None:
    # 境界値分析: 60秒未満の小数(59.9)はintで切り捨てられ、1分に繰り上がらない
    assert format_duration(59.9) == "00:00:59"


def test_estimate_to_hours_minutes_splits_fractional_hours() -> None:
    assert estimate_to_hours_minutes(1.5) == (1, 30)


def test_estimate_to_hours_minutes_rounds_to_nearest_minute() -> None:
    # 10分(0.1666…時間)のように割り切れない値も分単位に戻る
    assert estimate_to_hours_minutes(10 / 60) == (0, 10)


def test_hours_minutes_to_estimate_accepts_fractional_hours() -> None:
    assert hours_minutes_to_estimate(1.5, 15) == 1.75


def test_hours_minutes_round_trip_keeps_minutes() -> None:
    for hours, minutes in [(0, 0), (0, 10), (1, 59), (12, 1)]:
        assert estimate_to_hours_minutes(hours_minutes_to_estimate(hours, minutes)) == (hours, minutes)


def test_format_estimate_shapes() -> None:
    assert format_estimate(1.5) == "1時間30分"
    assert format_estimate(0.75) == "45分"
    assert format_estimate(2.0) == "2時間"


def test_format_gap_shows_sign_for_overrun_and_surplus() -> None:
    assert format_gap(1800) == "+00:30:00"
    assert format_gap(-1200) == "-00:20:00"


def test_format_gap_is_unsigned_at_zero() -> None:
    assert format_gap(0) == "00:00:00"
    assert format_gap(0.4) == "00:00:00"


def test_format_gap_is_dash_without_gap() -> None:
    assert format_gap(None) == "-"


def test_gap_background_is_none_without_estimate_or_gap() -> None:
    assert gap_background(None, None) is None
    assert gap_background(600, None) is None
    assert gap_background(None, 3600) is None


def test_gap_background_is_none_at_zero_gap() -> None:
    assert gap_background(0, 3600) is None
    assert gap_background(0.4, 3600) is None


def test_gap_background_is_red_for_overrun_and_blue_for_surplus() -> None:
    assert gap_background(1800, 3600) == "rgba(229, 57, 53, 0.34)"
    assert gap_background(-1800, 3600) == "rgba(30, 136, 229, 0.34)"


def test_gap_background_gets_darker_as_ratio_grows_and_caps_at_full_ratio() -> None:
    assert gap_background(360, 3600) == "rgba(229, 57, 53, 0.132)"
    assert gap_background(3600, 3600) == "rgba(229, 57, 53, 0.6)"
    assert gap_background(7200, 3600) == "rgba(229, 57, 53, 0.6)"
    assert gap_background(-7200, 3600) == "rgba(30, 136, 229, 0.6)"
