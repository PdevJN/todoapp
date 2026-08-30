from __future__ import annotations

import calendar
import uuid
from dataclasses import dataclass, field
from datetime import date, datetime
from enum import Enum
from typing import Any


class ScheduleType(str, Enum):
    DAILY = "daily"
    WEEKLY = "weekly"
    MONTHLY = "monthly"
    ONE_TIME = "one_time"


@dataclass
class TodoItem:
    name: str
    schedule_type: ScheduleType
    anchor_date: date
    estimate_hours: float = 0.0
    id: str = field(default_factory=lambda: uuid.uuid4().hex)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "schedule_type": self.schedule_type.value,
            "anchor_date": self.anchor_date.isoformat(),
            "estimate_hours": self.estimate_hours,
        }

    @staticmethod
    def from_dict(data: dict[str, Any]) -> TodoItem:
        return TodoItem(
            id=data["id"],
            name=data["name"],
            schedule_type=ScheduleType(data["schedule_type"]),
            anchor_date=date.fromisoformat(data["anchor_date"]),
            estimate_hours=data["estimate_hours"],
        )


@dataclass
class ExecutionRecord:
    item_id: str
    item_name: str
    start_time: datetime
    end_time: datetime | None = None
    id: str = field(default_factory=lambda: uuid.uuid4().hex)

    @property
    def is_running(self) -> bool:
        return self.end_time is None

    def elapsed_seconds(self, now: datetime) -> float:
        end = self.end_time or now
        return (end - self.start_time).total_seconds()

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "item_id": self.item_id,
            "item_name": self.item_name,
            "start_time": self.start_time.isoformat(),
            "end_time": self.end_time.isoformat() if self.end_time else None,
        }

    @staticmethod
    def from_dict(data: dict[str, Any]) -> ExecutionRecord:
        end_time = data["end_time"]
        return ExecutionRecord(
            id=data.get("id") or uuid.uuid4().hex,
            item_id=data["item_id"],
            item_name=data["item_name"],
            start_time=datetime.fromisoformat(data["start_time"]),
            end_time=datetime.fromisoformat(end_time) if end_time else None,
        )


@dataclass
class AppData:
    items: list[TodoItem]
    records: list[ExecutionRecord]


def _clamped_day(anchor_day: int, target: date) -> int:
    last_day_of_target_month = calendar.monthrange(target.year, target.month)[1]
    return min(anchor_day, last_day_of_target_month)


def is_due_today(item: TodoItem, today: date) -> bool:
    if item.schedule_type is ScheduleType.DAILY:
        return True
    if item.schedule_type is ScheduleType.WEEKLY:
        return today.weekday() == item.anchor_date.weekday()
    if item.schedule_type is ScheduleType.MONTHLY:
        return today.day == _clamped_day(item.anchor_date.day, today)
    return today == item.anchor_date
