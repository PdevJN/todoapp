from __future__ import annotations

import calendar
import random
import re
import unicodedata
import uuid
from collections.abc import Iterable
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from enum import Enum
from typing import Any
from urllib.parse import quote


class ScheduleType(str, Enum):
    DAILY = "daily"
    WEEKLY = "weekly"
    MONTHLY = "monthly"
    ONE_TIME = "one_time"
    UNDECIDED = "undecided"  # 実行日が決まっていない。どの日にも表示せず、編集一覧でだけ見える


# カテゴリの入力文字数の上限と、予約名(カテゴリ未設定の表示名)
ITEM_NAME_MAX_LENGTH = 50
CATEGORY_NAME_MAX_LENGTH = 30
CATEGORY_KIND_MAX_LENGTH = 20
CATEGORY_PRJ_CODE_MAX_LENGTH = 20
UNCATEGORIZED_NAME = "未定"
_PRJ_CODE_PATTERN = re.compile(r"[A-Za-z0-9_.\-]*")
LINK_TEMPLATE_NAME_MAX_LENGTH = 30
LINK_NAME_MAX_LENGTH = 30
LINK_URL_MAX_LENGTH = 500
LINK_VALUE_MAX_LENGTH = 200
LINK_RESOLVED_URL_MAX_LENGTH = 2000
LINK_MAX_PLACEHOLDERS = 5
_PLACEHOLDER_PATTERN = re.compile(r"\{([A-Za-z0-9_]+)\}")
_URL_SCHEMES = ("http://", "https://")

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


@dataclass
class LinkTemplate:
    name: str
    url_template: str  # 例: https://example.com/{project}/issues/{id}
    id: str = field(default_factory=lambda: uuid.uuid4().hex)

    def to_dict(self) -> dict[str, Any]:
        return {"id": self.id, "name": self.name, "url_template": self.url_template}

    @staticmethod
    def from_dict(data: dict[str, Any]) -> LinkTemplate:
        return LinkTemplate(
            id=data.get("id") or uuid.uuid4().hex, name=data["name"], url_template=data["url_template"]
        )


@dataclass
class ItemLink:
    name: str
    template_id: str | None = None  # Noneはテンプレートを使わず、`url`を直接開く
    url: str = ""
    values: dict[str, str] = field(default_factory=dict)  # テンプレート使用時の{置換項目名: 値}
    id: str = field(default_factory=lambda: uuid.uuid4().hex)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "template_id": self.template_id,
            "url": self.url,
            "values": dict(self.values),
        }

    @staticmethod
    def from_dict(data: dict[str, Any]) -> ItemLink:
        return ItemLink(
            id=data.get("id") or uuid.uuid4().hex,
            name=data["name"],
            template_id=data.get("template_id"),
            url=data.get("url", ""),
            values=dict(data.get("values", {})),
        )


def has_control_chars(text: str) -> bool:
    # 制御文字(Cc)・書式制御文字(Cf: ゼロ幅文字など)・行/段落区切り(Zl・Zp)を禁止する
    return any(unicodedata.category(ch) in ("Cc", "Cf", "Zl", "Zp") for ch in text)


def validate_item_name(name: str) -> str | None:
    """アイテム名を検証する。問題があればその内容(表示用メッセージ)を、無ければNoneを返す。"""
    if has_control_chars(name):
        return "アイテム名に制御文字は使えません"
    if len(name) > ITEM_NAME_MAX_LENGTH:
        return f"アイテム名は{ITEM_NAME_MAX_LENGTH}文字以内で入力してください"
    return None


def validate_category_fields(name: str | None = None, kind: str | None = None, prj_code: str | None = None) -> str | None:
    """カテゴリの入力値を検証する。問題があればその内容(表示用メッセージ)を、無ければNoneを返す。
    検証するのは渡された項目だけ。呼び出し側で前後の空白を除いた値を渡す。"""
    for label, value, limit in (
        ("カテゴリ名", name, CATEGORY_NAME_MAX_LENGTH),
        ("種別", kind, CATEGORY_KIND_MAX_LENGTH),
        ("PRJコード", prj_code, CATEGORY_PRJ_CODE_MAX_LENGTH),
    ):
        if value is None:
            continue
        if has_control_chars(value):
            return f"{label}に制御文字は使えません"
        if len(value) > limit:
            return f"{label}は{limit}文字以内で入力してください"
    if prj_code is not None and not _PRJ_CODE_PATTERN.fullmatch(prj_code):
        return "PRJコードは半角英数字と - _ . のみ使えます"
    return None


def is_category_expired(category: Category, today: date) -> bool:
    return category.expiry_date is not None and category.expiry_date < today


def template_placeholders(url_template: str) -> list[str]:
    """URL雛形の置換項目名を、最初に現れた順に重複なく返す。"""
    return list(dict.fromkeys(_PLACEHOLDER_PATTERN.findall(url_template)))


def _is_http_url(url: str) -> bool:
    return url.lower().startswith(_URL_SCHEMES)


def resolve_link_url(link: ItemLink, templates: Iterable[LinkTemplate]) -> str | None:
    """リンクを開くURLを返す。置換項目が未入力・テンプレートが無い・http(s)以外の場合は`None`。"""
    if link.template_id is None:
        url = link.url
    else:
        template = next((t for t in templates if t.id == link.template_id), None)
        if template is None:
            return None
        names = template_placeholders(template.url_template)
        if any(not link.values.get(name, "").strip() for name in names):
            return None
        url = _PLACEHOLDER_PATTERN.sub(lambda m: quote(link.values[m.group(1)], safe=""), template.url_template)
    return url if _is_http_url(url) else None


def _validate_url_text(label: str, url: str) -> str | None:
    if not url:
        return f"{label}を入力してください"
    if has_control_chars(url):
        return f"{label}に制御文字は使えません"
    if "｛" in url or "｝" in url:
        return f"{label}に全角の｛ ｝は使えません。半角の {{ }} を使ってください"
    if not url.isascii():
        return f"{label}に全角などASCII以外の文字は使えません(日本語はエンコード済みの形で入力してください)"
    if any(ch.isspace() for ch in url):
        return f"{label}に空白は使えません"
    if len(url) > LINK_URL_MAX_LENGTH:
        return f"{label}は{LINK_URL_MAX_LENGTH}文字以内で入力してください"
    if not _is_http_url(url):
        return f"{label}は http:// または https:// で始めてください"
    return None


def _validate_label_text(label: str, text: str, limit: int) -> str | None:
    if not text:
        return f"{label}を入力してください"
    if has_control_chars(text):
        return f"{label}に制御文字は使えません"
    if len(text) > limit:
        return f"{label}は{limit}文字以内で入力してください"
    return None


def validate_link_template_fields(name: str, url_template: str) -> str | None:
    """リンクテンプレートの入力値を検証する。問題があればその内容(表示用メッセージ)を、無ければNoneを返す。"""
    error = _validate_label_text("テンプレート名", name, LINK_TEMPLATE_NAME_MAX_LENGTH)
    if error is not None:
        return error
    error = _validate_url_text("URL雛形", url_template)
    if error is not None:
        return error
    leftover = _PLACEHOLDER_PATTERN.sub("", url_template)
    if "{" in leftover or "}" in leftover:
        return "置換項目は {名前}(名前は半角英数字と _ のみ)の形で書いてください"
    count = len(template_placeholders(url_template))
    if count == 0:
        return "置換項目 {名前} を1つ以上入れてください"
    if count > LINK_MAX_PLACEHOLDERS:
        return f"置換項目は{LINK_MAX_PLACEHOLDERS}個までです"
    return None


def validate_item_link_fields(
    name: str, template: LinkTemplate | None, url: str, values: dict[str, str]
) -> str | None:
    """アイテムのリンクの入力値を検証する。呼び出し側で前後の空白を除いた値を渡す。"""
    # 表示名は省略できる(省略時は一覧にURLを表示する)
    error = _validate_label_text("リンクの表示名", name, LINK_NAME_MAX_LENGTH) if name else None
    if error is not None:
        return error
    if template is None:
        return _validate_url_text("URL", url)
    for placeholder in template_placeholders(template.url_template):
        error = _validate_label_text(placeholder, values.get(placeholder, ""), LINK_VALUE_MAX_LENGTH)
        if error is not None:
            return error
    resolved = resolve_link_url(ItemLink(name=name, template_id=template.id, values=values), [template])
    if resolved is None:
        return "URLを組み立てられません。テンプレートのURL雛形を確認してください"
    if len(resolved) > LINK_RESOLVED_URL_MAX_LENGTH:
        return f"組み立てたURLは{LINK_RESOLVED_URL_MAX_LENGTH}文字以内にしてください"
    return None


@dataclass
class TodoItem:
    name: str
    schedule_type: ScheduleType
    anchor_date: date
    estimate_hours: float = 0.0
    today_estimate_hours: float = 0.0  # 本日だけの限定見積り。有効かどうかはtoday_estimate_seconds()で判定する
    today_estimate_date: date | None = None  # 限定見積りを設定した日
    category_id: str | None = None
    done_date: date | None = None  # 完了した日(最後に完了にした日)。判定はis_done()を使う
    skip_date: date | None = None  # スキップした日(繰り返しのアイテムのみ有効)。判定はis_skipped()を使う
    carried_from: date | None = None  # 初めて繰り越したときの元の基準日(当日のアイテムのみ有効)
    links: list[ItemLink] = field(default_factory=list)
    id: str = field(default_factory=lambda: uuid.uuid4().hex)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "schedule_type": self.schedule_type.value,
            "anchor_date": self.anchor_date.isoformat(),
            "estimate_hours": self.estimate_hours,
            "today_estimate_hours": self.today_estimate_hours,
            "today_estimate_date": self.today_estimate_date.isoformat() if self.today_estimate_date else None,
            "category_id": self.category_id,
            "done_date": self.done_date.isoformat() if self.done_date else None,
            "skip_date": self.skip_date.isoformat() if self.skip_date else None,
            "carried_from": self.carried_from.isoformat() if self.carried_from else None,
            "links": [link.to_dict() for link in self.links],
        }

    @staticmethod
    def from_dict(data: dict[str, Any]) -> TodoItem:
        done_date = data.get("done_date")
        today_estimate_date = data.get("today_estimate_date")
        skip_date = data.get("skip_date")
        carried_from = data.get("carried_from")
        return TodoItem(
            id=data["id"],
            name=data["name"],
            schedule_type=ScheduleType(data["schedule_type"]),
            anchor_date=date.fromisoformat(data["anchor_date"]),
            estimate_hours=data["estimate_hours"],
            today_estimate_hours=data.get("today_estimate_hours", 0.0),
            today_estimate_date=date.fromisoformat(today_estimate_date) if today_estimate_date else None,
            category_id=data.get("category_id"),
            done_date=date.fromisoformat(done_date) if done_date else None,
            skip_date=date.fromisoformat(skip_date) if skip_date else None,
            carried_from=date.fromisoformat(carried_from) if carried_from else None,
            links=[ItemLink.from_dict(link) for link in data.get("links", [])],
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
    link_templates: list[LinkTemplate] = field(default_factory=list)


def _clamped_day(anchor_day: int, target: date) -> int:
    last_day_of_target_month = calendar.monthrange(target.year, target.month)[1]
    return min(anchor_day, last_day_of_target_month)


class DoneFilter(str, Enum):
    ACTIVE = "active"
    ALL = "all"
    DONE = "done"
    SKIPPED = "skipped"


def is_done(item: TodoItem, today: date) -> bool:
    """完了済みか。繰り返し(毎日・週次・月次)は完了した日だけ、当日(one_time)・未定は永続的に完了とする。"""
    if item.done_date is None:
        return False
    if item.schedule_type in (ScheduleType.ONE_TIME, ScheduleType.UNDECIDED):
        return True
    return item.done_date == today


REPEATING_SCHEDULES = (ScheduleType.DAILY, ScheduleType.WEEKLY, ScheduleType.MONTHLY)


def is_skipped(item: TodoItem, today: date) -> bool:
    """その日だけスキップ中か。繰り返し(毎日・週次・月次)のみ対象で、スキップした日の翌日には自動で解除される。"""
    return item.schedule_type in REPEATING_SCHEDULES and item.skip_date == today


def today_estimate_seconds(item: TodoItem, today: date) -> int | None:
    """本日だけの限定見積り(秒)。設定した日以外、または未設定の場合は`None`。"""
    # 見積りは10分=0.1666…時間のような小数で保存されるため、秒に丸める
    seconds = round(item.today_estimate_hours * 3600)
    if item.today_estimate_date != today or seconds <= 0:
        return None
    return seconds


def can_carry_over(item: TodoItem, today: date, remaining_seconds: float) -> bool:
    """未完了で見積りが残っている当日のアイテムを、次の日へ繰り越せるか。見積りちょうど使い切った場合は対象外。"""
    return (
        item.schedule_type is ScheduleType.ONE_TIME
        and not is_done(item, today)
        and item.estimate_hours > 0
        and remaining_seconds > 0
        and item.anchor_date <= today
    )


def carry_over_target(item: TodoItem, today: date) -> date:
    """繰越先の日。基準日が過去なら今日、今日なら翌日。"""
    return today if item.anchor_date < today else today + timedelta(days=1)


def matches_done_filter(item: TodoItem, today: date, done_filter: DoneFilter) -> bool:
    if done_filter is DoneFilter.ALL:
        return True
    if done_filter is DoneFilter.SKIPPED:
        return is_skipped(item, today)
    if done_filter is DoneFilter.DONE:
        return is_done(item, today)
    return not is_done(item, today) and not is_skipped(item, today)


def is_due_today(item: TodoItem, today: date) -> bool:
    if item.schedule_type is ScheduleType.UNDECIDED:
        return False
    if item.schedule_type is ScheduleType.DAILY:
        return True
    # 週次・月次は基準日から繰り返す。基準日より前の日は対象外とする
    if item.schedule_type is ScheduleType.WEEKLY:
        return today >= item.anchor_date and today.weekday() == item.anchor_date.weekday()
    if item.schedule_type is ScheduleType.MONTHLY:
        return today >= item.anchor_date and today.day == _clamped_day(item.anchor_date.day, today)
    return today == item.anchor_date
