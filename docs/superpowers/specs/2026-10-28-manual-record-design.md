# 実行記録の手動追加 設計

## 目的

実際には計測しなかった作業を、実行履歴(カレンダー)から後から記録として追加できるようにする。追加した記録は通常の記録と見分けられ、作業ログ・集計画面にも反映される。

## 要件

- 追加する項目は、`日付`・`カテゴリ`・`タスク名`(任意)・`開始時刻`・`終了時刻`。見積りは不要。
- アイテムは作らず、記録だけを追加する。メインパネル・編集一覧には出ない。
- 追加した記録は、カレンダーで薄い赤(背景 `#ef9a9a`、濃い赤の枠線)で表示し、ツールチップに`手動追加`を表示する。
- 手動記録は、作業ログ(`実行順`・`カテゴリ別`)、集計画面(`カテゴリ別`・`アイテム別`・`稼働集計`の実績)に通常の記録と同じく反映する。
- 手動記録のカテゴリは、カレンダー上の右クリックメニューから変更できる。名前の変更はできない。時刻の編集・削除は左クリックの`RecordEditDialog`で行う。

## 前提となる現状

- `ExecutionRecord`は`item_id`・`item_name`を持ち、カテゴリは`item_id`からアイテムを引いて求める(`TodoService.category_for_item()`)。
- 集計(`category_today_totals`・`category_today_item_totals`・`item_gap_rows`・`_today_item_order`)は`item_id`をキーにしている。
- 稼働集計の実績は記録の`start_time`の日付で合計しており、`item_id`を見ない。
- 記録の編集・削除は Undo の対象外。

## 設計

### データモデル(`domain/models.py`)

- `ExecutionRecord`に任意項目を追加する: `manual: bool = False`、`category_id: str | None = None`。`to_dict`/`from_dict`に含め、無い場合は既定値で読む。任意項目のためスキーマ`version`は上げない(`carried_from`と同じ扱い)。
- 手動記録の`item_id`は`manual:<記録ID>`の合成キーとする。既存の`item_id`キーの集計と衝突せず、アイテムへの参照は「該当なし」になる(累積は0)。
- `validate_manual_record()`を追加する。検証内容:
  - 開始 < 終了。
  - 開始と終了が同じ日(0:00をまたがない)。
  - 同日の既存記録(実行中を含む。実行中は現在時刻まで)と時間が重ならない。境界で接するのは可。
  - タスク名は`validate_item_name()`を通す(任意・50文字・制御文字禁止。空は可)。
  - 日付・時刻の形式が不正な場合は警告する。

### サービス(`domain/service.py`)

- `category_for_record(record)`を追加する。手動記録は`record.category_id`、通常記録は従来どおりアイテム経由でカテゴリを返す。存在しない`category_id`は`None`(`未定`)。
- `add_manual_record(category_id, name, start, end)`: `item_name`は、名前が空ならカテゴリの表示名(未設定は`未定`)にする。`@undoable`は付けない。
- `set_record_category(record_id, category_id)`: 手動記録のみ対象(通常記録は`ValueError`)。存在しないカテゴリは拒否する。`item_name`が変更前のカテゴリの表示名と同じ場合に限り、新しいカテゴリの表示名へ揃える。`@undoable`は付けない。
- 集計の`category_today_totals`・`category_today_item_totals`・`_today_item_order`・`item_gap_rows`は`category_for_record`を使う。`アイテム別`では手動記録を1件1行で表示し、`累積`・`見積り`・`GAP`は`-`とする。
- 稼働集計の実績は変更不要。

### UI

- `ui/calendar_view.py`: ヘッダーに`追加`ボタンを置く。押すと追加フォーム(新規ダイアログ)を開く。
- 追加フォーム(`ui/manual_record_dialog.py`、`DialogMixin`): `日付`(初期値は表示中の日、無ければ当日)・`カテゴリ`(`未定`を含む、`PRJコード`併記、有効期限切れは`❗️`)・`タスク名`(任意、`maxlength=50`)・`開始時刻`・`終了時刻`(`ui.time_input`、秒まで)。検証は保存時に行い、問題があれば警告を表示してダイアログを開いたままにする。
- カレンダーの描画: 手動記録は薄い赤の背景・濃い赤の枠線とし、色はカテゴリ色ではなく手動記録専用とする。ツールチップに`手動追加`と、カテゴリ名を併記する。
- 作業ログの`実行順`: 手動記録は、カテゴリバッジの隣に`手動`の小さな印を付ける。
- 右クリックメニュー(`ui/calendar_view.py`):
  - 手動記録のバーでの右クリックで、その位置に`ui.menu`を開く。通常記録では出さず、ブラウザ標準のままにする。
  - 内容は`カテゴリを変更`の見出しの下に、`未定`と登録済みカテゴリを登録順に並べる。カテゴリ色の丸・`PRJコード`・`❗️`を併記する。現在のカテゴリは選択済みの印を付けて無効にする。
  - 選択で`set_record_category`を呼び、カレンダーを再描画する。

### FullCalendarラッパー(`ui/vendor/fullcalendar/`)

- `fullcalendar.js`の`eventDidMount`に`contextmenu`リスナーを追加し、`preventDefault`の上で`event_contextmenu`として`{id, x, y}`(クリック位置)を通知する。
- `fullcalendar.py`に`on_contextmenu`引数を追加する。
- メニューの表示位置の指定(Quasarの`target`/位置指定)が WKWebView で動くかを、実装の最初に小さく確認する。動かない場合は代替手段(位置固定の要素へ`ui.menu`を結び付ける)に切り替える。

## 範囲外

- 手動記録の名前の変更、複数日にまたがる記録、実行中の記録との併用。
- 手動記録の追加・カテゴリ変更の Undo。
- 作業ログ画面からの追加。

## テスト

- `add_manual_record`: 名前あり・なし、`item_id`の合成キー、保存と読み込みの往復、旧データ(`manual`なし)の読み込み。
- `validate_manual_record`: 逆転・同時刻・日またぎ・重なり(実行中を含む)・境界の接触・名前の検証。
- `set_record_category`: 手動記録の変更、通常記録の拒否、存在しないカテゴリの拒否、名前の追従と非追従。
- 集計: `category_today_totals`・`kind_today_totals`・`category_today_item_totals`・`item_gap_rows`・稼働集計の実績への反映。削除済みカテゴリの手動記録は`未定`に集計される。
- UI(手動確認): 追加フォーム、薄い赤の表示、右クリックメニュー(位置・変更・通常記録では出ないこと)、作業ログの`手動`印。
- `CLAUDE.md`の仕様、ヘルプ(`ui/help_dialog.py`)、`README.md`を更新する。キー操作の追加は無いため`SHORTCUT_KEYS`は変更しない。
