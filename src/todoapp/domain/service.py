from __future__ import annotations

from collections.abc import Callable
from datetime import date, datetime
from typing import Protocol

from todoapp.domain.models import AppData, ExecutionRecord, ScheduleType, TodoItem, is_due_today


class TodoRepository(Protocol):
    def load(self) -> AppData: ...
    def save(self, data: AppData) -> None: ...


class TodoService:
    def __init__(
        self,
        repository: TodoRepository,
        clock: Callable[[], datetime] = datetime.now,
    ) -> None:
        self._repository = repository
        self._clock = clock
        self._data = repository.load()

    @property
    def items(self) -> list[TodoItem]:
        return self._data.items

    @property
    def records(self) -> list[ExecutionRecord]:
        return self._data.records

    def _save(self) -> None:
        self._repository.save(self._data)

    def _find_item(self, item_id: str) -> TodoItem:
        for item in self._data.items:
            if item.id == item_id:
                return item
        raise KeyError(item_id)

    def add_item(
        self,
        name: str,
        schedule_type: ScheduleType,
        anchor_date: date,
        estimate_hours: float = 0.0,
    ) -> TodoItem:
        item = TodoItem(
            name=name,
            schedule_type=schedule_type,
            anchor_date=anchor_date,
            estimate_hours=estimate_hours,
        )
        self._data.items.append(item)
        self._save()
        return item

    def edit_item(
        self,
        item_id: str,
        *,
        name: str | None = None,
        schedule_type: ScheduleType | None = None,
        anchor_date: date | None = None,
        estimate_hours: float | None = None,
    ) -> None:
        item = self._find_item(item_id)
        if name is not None:
            item.name = name
        if schedule_type is not None:
            item.schedule_type = schedule_type
        if anchor_date is not None:
            item.anchor_date = anchor_date
        if estimate_hours is not None:
            item.estimate_hours = estimate_hours
        self._save()

    def running_record(self) -> ExecutionRecord | None:
        for record in self._data.records:
            if record.is_running:
                return record
        return None

    def start(self, item_id: str) -> None:
        item = self._find_item(item_id)
        self.stop_running()
        self._data.records.append(
            ExecutionRecord(item_id=item.id, item_name=item.name, start_time=self._clock())
        )
        self._save()

    def stop_running(self) -> None:
        record = self.running_record()
        if record is not None:
            record.end_time = self._clock()
            self._save()

    def toggle_execution(self, item_id: str) -> None:
        running = self.running_record()
        if running is not None and running.item_id == item_id:
            self.stop_running()
        else:
            self.start(item_id)

    def cancel_running(self, item_id: str) -> None:
        record = self.running_record()
        if record is not None and record.item_id == item_id:
            self._data.records.remove(record)
            self._save()

    def delete_item(self, item_id: str) -> None:
        running = self.running_record()
        if running is not None and running.item_id == item_id:
            self.stop_running()
        self._data.items = [item for item in self._data.items if item.id != item_id]
        self._save()

    def reorder(self, old_index: int, new_index: int) -> None:
        item = self._data.items.pop(old_index)
        self._data.items.insert(new_index, item)
        self._save()

    def items_due_today(self, today: date) -> list[TodoItem]:
        return [item for item in self._data.items if is_due_today(item, today)]

    def cumulative_seconds(self, item_id: str) -> float:
        now = self._clock()
        return sum(r.elapsed_seconds(now) for r in self._data.records if r.item_id == item_id)

    def today_total_seconds(self, item_id: str, today: date) -> float:
        now = self._clock()
        return sum(
            r.elapsed_seconds(now)
            for r in self._data.records
            if r.item_id == item_id and r.start_time.date() == today
        )

    def remaining_seconds(self, item_id: str) -> float:
        item = self._find_item(item_id)
        estimate_seconds = item.estimate_hours * 3600
        return max(estimate_seconds - self.cumulative_seconds(item_id), 0.0)

    def remaining_hours(self, item_id: str) -> float:
        return self.remaining_seconds(item_id) / 3600

    def today_records(self, today: date) -> list[ExecutionRecord]:
        todays = [r for r in self._data.records if r.start_time.date() == today]
        return sorted(todays, key=lambda r: r.start_time)
