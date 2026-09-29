from __future__ import annotations

from collections.abc import Callable, Iterable
from datetime import date, datetime
from typing import Protocol

from todoapp.domain.models import (
    AppData,
    Category,
    ExecutionRecord,
    ScheduleType,
    TodoItem,
    is_due_today,
)


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

    @property
    def categories(self) -> list[Category]:
        return self._data.categories

    def _save(self) -> None:
        self._repository.save(self._data)

    def _find_item(self, item_id: str) -> TodoItem:
        for item in self._data.items:
            if item.id == item_id:
                return item
        raise KeyError(item_id)

    def _find_record(self, record_id: str) -> ExecutionRecord:
        for record in self._data.records:
            if record.id == record_id:
                return record
        raise KeyError(record_id)

    def _find_category(self, category_id: str) -> Category:
        for category in self._data.categories:
            if category.id == category_id:
                return category
        raise KeyError(category_id)

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

    def delete_items(self, item_ids: Iterable[str]) -> None:
        ids = set(item_ids)
        running = self.running_record()
        if running is not None and running.item_id in ids:
            running.end_time = self._clock()
        self._data.items = [item for item in self._data.items if item.id not in ids]
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

    def is_over_estimate(self, item_id: str) -> bool:
        item = self._find_item(item_id)
        # 見積りは10分=0.1666…時間のような小数で保存されるため、秒に丸めてから比べる
        estimate_seconds = round(item.estimate_hours * 3600)
        return estimate_seconds > 0 and self.cumulative_seconds(item_id) > estimate_seconds

    def remaining_hours(self, item_id: str) -> float:
        return self.remaining_seconds(item_id) / 3600

    def today_records(self, today: date) -> list[ExecutionRecord]:
        todays = [r for r in self._data.records if r.start_time.date() == today]
        return sorted(todays, key=lambda r: r.start_time)

    def edit_record(self, record_id: str, *, start_time: datetime, end_time: datetime | None) -> None:
        record = self._find_record(record_id)
        record.start_time = start_time
        record.end_time = end_time
        self._save()

    def delete_record(self, record_id: str) -> None:
        self._data.records = [r for r in self._data.records if r.id != record_id]
        self._save()

    def delete_records(self, record_ids: Iterable[str]) -> None:
        ids = set(record_ids)
        self._data.records = [r for r in self._data.records if r.id not in ids]
        self._save()

    def add_category(self, name: str, kind: str = "", expiry_date: date | None = None) -> Category:
        category = Category(name=name, kind=kind, expiry_date=expiry_date)
        self._data.categories.append(category)
        self._save()
        return category

    def edit_category(
        self, category_id: str, *, name: str, kind: str, expiry_date: date | None, color: str, prj_code: str
    ) -> None:
        category = self._find_category(category_id)
        category.name = name
        category.kind = kind
        category.expiry_date = expiry_date
        category.color = color
        category.prj_code = prj_code
        self._save()

    def delete_category(self, category_id: str) -> None:
        self.delete_categories([category_id])

    def linked_item_count(self, category_ids: Iterable[str]) -> int:
        ids = set(category_ids)
        return sum(1 for item in self._data.items if item.category_id in ids)

    def delete_categories(self, category_ids: Iterable[str]) -> None:
        ids = set(category_ids)
        self._data.categories = [c for c in self._data.categories if c.id not in ids]
        for item in self._data.items:
            if item.category_id in ids:
                item.category_id = None
        self._save()

    def set_item_category(self, item_id: str, category_id: str | None) -> None:
        item = self._find_item(item_id)
        item.category_id = category_id
        self._save()

    def category_for_item(self, item_id: str) -> Category | None:
        item = next((i for i in self._data.items if i.id == item_id), None)
        if item is None or item.category_id is None:
            return None
        for category in self._data.categories:
            if category.id == item.category_id:
                return category
        return None

    def category_today_totals(self, today: date) -> dict[str | None, float]:
        now = self._clock()
        totals: dict[str | None, float] = {}
        items_by_id = {item.id: item for item in self._data.items}
        for record in self._data.records:
            if record.start_time.date() != today:
                continue
            item = items_by_id.get(record.item_id)
            category_id = item.category_id if item is not None else None
            totals[category_id] = totals.get(category_id, 0.0) + record.elapsed_seconds(now)
        return totals

    def category_today_all_totals(self, today: date) -> list[tuple[Category | None, float]]:
        # 登録済みの全カテゴリを登録順に並べ、最後に「未定」(None)を置く
        totals = self.category_today_totals(today)
        result: list[tuple[Category | None, float]] = []
        uncategorized = 0.0
        known_ids = {category.id for category in self._data.categories}
        for category in self._data.categories:
            result.append((category, totals.get(category.id, 0.0)))
        for category_id, seconds in totals.items():
            if category_id not in known_ids:
                uncategorized += seconds
        result.append((None, uncategorized))
        return result

    def category_today_item_totals(self, today: date) -> dict[str | None, list[tuple[str, float]]]:
        # 本日の実行対象アイテム(一覧順)の後ろに、対象外だが本日実行したアイテムを初回実行順に並べる
        now = self._clock()
        known_ids = {category.id for category in self._data.categories}
        items_by_id = {item.id: item for item in self._data.items}
        seconds_by_item: dict[str, float] = {}
        names: dict[str, str] = {}
        for record in self.today_records(today):
            elapsed = record.elapsed_seconds(now)
            seconds_by_item[record.item_id] = seconds_by_item.get(record.item_id, 0.0) + elapsed
            names.setdefault(record.item_id, record.item_name)

        order = [item.id for item in self.items_due_today(today)]
        order += [item_id for item_id in seconds_by_item if item_id not in order]

        result: dict[str | None, list[tuple[str, float]]] = {}
        for item_id in order:
            item = items_by_id.get(item_id)
            category_id = item.category_id if item is not None else None
            key = category_id if category_id in known_ids else None
            name = item.name if item is not None else names[item_id]
            result.setdefault(key, []).append((name, seconds_by_item.get(item_id, 0.0)))
        return result

    def kind_today_totals(self, today: date) -> dict[str, float]:
        categories_by_id = {category.id: category for category in self._data.categories}
        totals: dict[str, float] = {}
        for category_id, seconds in self.category_today_totals(today).items():
            if category_id is None:
                kind = "未定"
            else:
                category = categories_by_id.get(category_id)
                kind = (category.kind if category and category.kind else "未設定")
            totals[kind] = totals.get(kind, 0.0) + seconds
        return totals
