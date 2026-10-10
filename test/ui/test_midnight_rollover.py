"""実行中に0:00を跨いだ場合の画面の追従(記録の分割と、表示日の追従)。"""

import asyncio
from datetime import date, datetime, time, timedelta
from typing import Any

from nicegui.testing import User

from test.ui.harness import AppEnv, make_item, make_record
from todoapp.domain.models import ScheduleType

TODAY = date.today()
YESTERDAY = TODAY - timedelta(days=1)


async def _wait_for(condition: Any, message: str, timeout: float = 5.0) -> None:
    deadline = asyncio.get_running_loop().time() + timeout
    while not condition():
        if asyncio.get_running_loop().time() > deadline:
            raise AssertionError(message)
        await asyncio.sleep(0.05)


def _seed_running_since_yesterday_evening(env: AppEnv) -> None:
    item = make_item("夜の作業", ScheduleType.DAILY, anchor_date=YESTERDAY)
    start = datetime.combine(YESTERDAY, time(23, 0))
    env.seed(items=[item], records=[make_record(item, start, None)])


async def test_running_record_started_yesterday_is_split_at_midnight_and_continues(
    app_user: User, app_env: AppEnv
) -> None:
    _seed_running_since_yesterday_evening(app_env)

    await app_user.open("/")
    midnight = datetime.combine(TODAY, time.min)
    await _wait_for(lambda: len(app_env.todos().records) == 2, "記録が0:00で分割されていません")

    first, second = sorted(app_env.todos().records, key=lambda r: r.start_time)
    assert (first.start_time, first.end_time) == (datetime.combine(YESTERDAY, time(23, 0)), midnight)
    assert (second.start_time, second.end_time) == (midnight, None)
    assert first.item_id == second.item_id
