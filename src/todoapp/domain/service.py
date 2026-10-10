from __future__ import annotations

from collections.abc import Callable, Iterable
from datetime import date, datetime, time, timedelta
from typing import NamedTuple, Protocol

from todoapp.domain.models import (
    AppData,
    Category,
    DoneFilter,
    ExecutionRecord,
    ScheduleType,
    TodoItem,
    is_done,
    is_due_today,
    matches_done_filter,
    today_estimate_seconds,
)


class TodoRepository(Protocol):
    def load(self) -> AppData: ...
    def save(self, data: AppData) -> None: ...


class AliveStore(Protocol):
    """実行中の「最後に動作していた時刻」の保存先。アプリの終了後に、実行を止める時刻として使う。"""

    def load(self) -> datetime | None: ...
    def save(self, value: datetime) -> None: ...


# 実行中は、この間隔で生存時刻を保存する(強制終了しても、記録のずれがこの秒数程度に収まる)
ALIVE_SAVE_INTERVAL_SECONDS = 2
# 1秒タイマーの呼び出しがこの秒数より空いたら、スリープ等で処理が止まっていたとみなす
SUSPEND_GAP_SECONDS = 60


class ItemGapRow(NamedTuple):
    """アイテムごとの集計1行分。累積・見積り・GAPは、削除済みアイテムや見積り未設定の場合`None`。"""

    name: str
    today_seconds: float
    cumulative_seconds: float | None
    estimate_seconds: int | None
    gap_seconds: float | None  # 累積経過時間 - 見積り(超過が正)
    done: bool = False
    today_estimate_seconds: int | None = None  # 本日だけの限定見積り(未設定は`None`)


class TodoService:
    def __init__(
        self,
        repository: TodoRepository,
        clock: Callable[[], datetime] = datetime.now,
        alive_store: AliveStore | None = None,
    ) -> None:
        self._repository = repository
        self._clock = clock
        self._alive_store = alive_store
        self._last_tick: datetime | None = None
        self._alive_saved_at: datetime | None = None
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
        today_estimate_hours: float | None = None,
    ) -> None:
        item = self._find_item(item_id)
        if name is not None:
            item.name = name
            # 実行記録は開始時点のアイテム名を保持しているため、リネーム後も同じタスクとして
            # 見えるよう、このアイテムの既存の記録の名前も揃える
            for record in self._data.records:
                if record.item_id == item_id:
                    record.item_name = name
        if schedule_type is not None:
            item.schedule_type = schedule_type
        if anchor_date is not None:
            item.anchor_date = anchor_date
        if estimate_hours is not None:
            item.estimate_hours = estimate_hours
        if today_estimate_hours is not None:
            # 限定見積りは設定した日だけ有効。0で解除する
            item.today_estimate_hours = today_estimate_hours
            item.today_estimate_date = self._clock().date() if today_estimate_hours > 0 else None
        self._save()

    def running_record(self) -> ExecutionRecord | None:
        for record in self._data.records:
            if record.is_running:
                return record
        return None

    def start(self, item_id: str) -> None:
        item = self._find_item(item_id)
        self.stop_running()
        now = self._clock()
        self._data.records.append(ExecutionRecord(item_id=item.id, item_name=item.name, start_time=now))
        self._save()
        # 停止中の空白(スリープ等)を中断と取り違えないよう、開始時点から数え直す
        self._touch_alive(now, force=True)

    def recover_interrupted(self) -> None:
        """前回の終了時に実行中のまま残った記録を、最後に動作していた時刻で停止する(起動時に1回呼ぶ)。"""
        running = self.running_record()
        if running is None:
            return
        alive = self._alive_store.load() if self._alive_store is not None else None
        # 生存時刻が無い・開始より前の場合は開始時刻で、未来の場合は現在で閉じる
        end = running.start_time if alive is None else max(min(alive, self._clock()), running.start_time)
        self._close_at(running, end)
        self._save()

    def keep_alive(self) -> bool:
        """実行中の見守り(1秒タイマーから呼ぶ)。0:00を跨いだ記録を分割して継続し、生存時刻を保存する。

        スリープ等で呼び出しが長く空いていた場合は、最後に動作していた時刻で停止して`True`を返す。
        """
        now = self._clock()
        running = self.running_record()
        if running is None:
            self._last_tick = now
            return False
        last = self._last_tick
        if last is not None and (now - last).total_seconds() > SUSPEND_GAP_SECONDS:
            self._close_at(running, last)
            self._save()
            return True
        if self._split_at_midnights(running, now) is not running:
            self._save()
        self._touch_alive(now)
        return False

    def _touch_alive(self, now: datetime, *, force: bool = False) -> None:
        self._last_tick = now
        if self._alive_store is None:
            return
        saved_at = self._alive_saved_at
        if force or saved_at is None or (now - saved_at).total_seconds() >= ALIVE_SAVE_INTERVAL_SECONDS:
            self._alive_store.save(now)
            self._alive_saved_at = now

    def _close_at(self, record: ExecutionRecord, end: datetime) -> None:
        """記録を`end`で閉じる。0:00を跨ぐ場合は日ごとに分割する。"""
        end = max(end, record.start_time)
        self._split_at_midnights(record, end).end_time = end

    def _split_at_midnights(self, record: ExecutionRecord, until: datetime) -> ExecutionRecord:
        """`until`より前の0:00で記録を日ごとに分割し、`until`と同じ日の最後の記録を返す(終了時刻は未設定)。"""
        while True:
            boundary = datetime.combine(record.start_time.date() + timedelta(days=1), time.min)
            if boundary >= until:
                return record
            rest = ExecutionRecord(item_id=record.item_id, item_name=record.item_name, start_time=boundary)
            record.end_time = boundary
            self._data.records.insert(self._data.records.index(record) + 1, rest)
            record = rest

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

    def move_item_to(self, item_id: str, target_id: str) -> None:
        """アイテムを、対象アイテムのいま居る位置へ移動する(表示を絞っていても全体の並びを正しく更新するため)。"""
        item = self._find_item(item_id)
        target_index = next(i for i, other in enumerate(self._data.items) if other.id == target_id)
        self._data.items.remove(item)
        self._data.items.insert(target_index, item)
        self._save()

    def items_due_today(self, today: date, done_filter: DoneFilter = DoneFilter.ALL) -> list[TodoItem]:
        return [
            item
            for item in self._data.items
            if is_due_today(item, today) and matches_done_filter(item, today, done_filter)
        ]

    def item_name_candidates(self) -> list[str]:
        """新規アイテム名の入力補完の候補。既存アイテム(新しい登録順)、実行記録(新しい順)の名前を重複なしで返す。"""
        names = [item.name for item in reversed(self._data.items)]
        names += [record.item_name for record in sorted(self._data.records, key=lambda r: r.start_time, reverse=True)]
        # dict.fromkeysは最初に現れた順を保って重複を除く。空の名前は候補にしない
        return [name for name in dict.fromkeys(names) if name]

    def set_done(self, item_ids: Iterable[str], done: bool, today: date) -> None:
        ids = set(item_ids)
        for item in self._data.items:
            if item.id in ids:
                item.done_date = today if done else None
        running = self.running_record()
        if done and running is not None and running.item_id in ids:
            self.stop_running()
            return
        self._save()

    def toggle_done(self, item_ids: Iterable[str], today: date) -> None:
        """1件でも未完了があれば全て完了に、全て完了済みなら全て未完了に戻す。"""
        ids = set(item_ids)
        items = [item for item in self._data.items if item.id in ids]
        all_done = bool(items) and all(is_done(item, today) for item in items)
        self.set_done(ids, not all_done, today)

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

    def today_remaining_seconds(self, item_id: str, today: date) -> float | None:
        """限定見積りから本日の実行時間を引いた残り。限定見積りが無効なら`None`。"""
        estimate = today_estimate_seconds(self._find_item(item_id), today)
        if estimate is None:
            return None
        return max(estimate - self.today_total_seconds(item_id, today), 0.0)

    def today_estimate_total_seconds(self, today: date, exclude_item_id: str | None = None) -> int:
        """本日の実行対象アイテムの、有効な限定見積り(完了済みも含む)の合計。編集中のアイテムは除外できる。"""
        total = 0
        for item in self.items_due_today(today):
            if item.id == exclude_item_id:
                continue
            total += today_estimate_seconds(item, today) or 0
        return total

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

    def _today_item_order(self, today: date) -> tuple[list[str], dict[str, float], dict[str, str]]:
        # 本日の実行対象アイテム(一覧順)の後ろに、対象外だが本日実行したアイテムを初回実行順に並べる
        now = self._clock()
        seconds_by_item: dict[str, float] = {}
        names: dict[str, str] = {}
        for record in self.today_records(today):
            elapsed = record.elapsed_seconds(now)
            seconds_by_item[record.item_id] = seconds_by_item.get(record.item_id, 0.0) + elapsed
            names.setdefault(record.item_id, record.item_name)

        order = [item.id for item in self.items_due_today(today)]
        order += [item_id for item_id in seconds_by_item if item_id not in order]
        return order, seconds_by_item, names

    def category_today_item_totals(self, today: date) -> dict[str | None, list[tuple[str, float, bool]]]:
        known_ids = {category.id for category in self._data.categories}
        items_by_id = {item.id: item for item in self._data.items}
        order, seconds_by_item, names = self._today_item_order(today)

        result: dict[str | None, list[tuple[str, float, bool]]] = {}
        for item_id in order:
            item = items_by_id.get(item_id)
            category_id = item.category_id if item is not None else None
            key = category_id if category_id in known_ids else None
            name = item.name if item is not None else names[item_id]
            done = item is not None and is_done(item, today)
            result.setdefault(key, []).append((name, seconds_by_item.get(item_id, 0.0), done))
        return result

    def item_gap_rows(self, today: date) -> list[ItemGapRow]:
        """本日の対象または本日実行したアイテムごとに、実行時間と見積りとのズレ(GAP)を返す。"""
        items_by_id = {item.id: item for item in self._data.items}
        order, seconds_by_item, names = self._today_item_order(today)

        rows: list[ItemGapRow] = []
        for item_id in order:
            item = items_by_id.get(item_id)
            today_seconds = seconds_by_item.get(item_id, 0.0)
            if item is None:
                rows.append(ItemGapRow(names[item_id], today_seconds, None, None, None))
                continue
            cumulative = self.cumulative_seconds(item_id)
            done = is_done(item, today)
            # 見積りは10分=0.1666…時間のような小数で保存されるため、秒に丸める
            estimate = round(item.estimate_hours * 3600)
            today_estimate = today_estimate_seconds(item, today)
            if estimate > 0:
                rows.append(
                    ItemGapRow(
                        item.name, today_seconds, cumulative, estimate, cumulative - estimate, done, today_estimate
                    )
                )
            else:
                rows.append(ItemGapRow(item.name, today_seconds, cumulative, None, None, done, today_estimate))
        return rows

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
