from todoapp.ui.formatting import format_duration


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
