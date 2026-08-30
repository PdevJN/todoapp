from __future__ import annotations

import calendar
import random
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


CATEGORY_COLORS = [
    "red",
    "orange",
    "amber",
    "green",
    "teal",
    "blue",
    "indigo",
    "purple",
    "pink",
    "brown",
]


@dataclass
class Category:
    name: str
    kind: str = ""
    expiry_date: date | None = None
    color: str = field(default_factory=lambda: random.choice(CATEGORY_COLORS))
    prj_code: str = ""
    id: str = field(default_factory=lambda: uuid.uuid4().hex)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "kind": self.kind,
            "expiry_date": self.expiry_date.isoformat() if self.expiry_date else None,
            "color": self.color,
            "prj_code": self.prj_code,
        }

    @staticmethod
    def from_dict(data: dict[str, Any]) -> Category:
        expiry_date = data.get("expiry_date")
        return Category(
            id=data.get("id") or uuid.uuid4().hex,
            name=data["name"],
            kind=data.get("kind", ""),
            expiry_date=date.fromisoformat(expiry_date) if expiry_date else None,
            color=data.get("color") or random.choice(CATEGORY_COLORS),
            prj_code=data.get("prj_code", ""),
        )


def is_category_expired(category: Category, today: date) -> bool:
    return category.expiry_date is not None and category.expiry_date < today


@dataclass
class TodoItem:
    name: str
    schedule_type: ScheduleType
    anchor_date: date
    estimate_hours: float = 0.0
    category_id: str | None = None
    id: str = field(default_factory=lambda: uuid.uuid4().hex)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "schedule_type": self.schedule_type.value,
            "anchor_date": self.anchor_date.isoformat(),
            "estimate_hours": self.estimate_hours,
            "category_id": self.category_id,
        }

    @staticmethod
    def from_dict(data: dict[str, Any]) -> TodoItem:
        return TodoItem(
            id=data["id"],
            name=data["name"],
            schedule_type=ScheduleType(data["schedule_type"]),
            anchor_date=date.fromisoformat(data["anchor_date"]),
            estimate_hours=data["estimate_hours"],
            category_id=data.get("category_id"),
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
    categories: list[Category] = field(default_factory=list)


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
