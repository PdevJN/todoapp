# 稼働集計(月・期間の稼働日数/合計/残業時間と見積りGAP) 設計

## 目的

月ごと、または指定した期間ごとに、標準労働時間に対する稼働の過不足(`残業時間`)と、見積りに対する実績の差(`GAP`)を数字とグラフで確認できるようにする。

## 要件(ユーザー指示と確認結果)

- 集計画面に表示する(新しいタブ`稼働集計`)
- 数字: `稼働日数`、`合計`(= 稼働日数 × 標準労働時間)、実績の稼働時間、`残業時間`(実績と合計の差)、`見積り`と`見積りGAP`
- グラフ: 見積り・その差分のGAP・実際の稼働時間
- 表示単位は`月`と、`指定した期間`。期間では、その期間内の合計として扱い、`残業時間`の合計も表示する
- 設定で`残業時間の目標値`を設定でき(既定20時間)、`残業時間`の文字色を、目標を上回った場合とそうでない場合で変える
- 稼働日数は、既定が平日(土日・祝日を除く)。カレンダーで日ごとに選び直せ、選び直した内容は日ごとに保存する
- 見積りは日ごとの`本日の見積り`の合計とする。`本日の見積り`は最後に設定した1日分しか持たず、過去日の値は復元できないため、今後は日ごとの履歴を記録する(導入前の日は見積りなし)
- 目標との比較は、月表示でも期間指定でも、表示中の`残業時間`(期間指定では合計)をそのまま目標と比べる

## 前提(現状の仕組み)

- 集計画面は`ui/category_summary_dialog.py`(`カテゴリ別`・`アイテム別`の2タブ)。右上の円グラフボタンで、表示中のタブのグラフを切り替える。開くたびに全タブとも非表示から始まる
- `本日の見積り`は`TodoItem.today_estimate_hours`と`today_estimate_date`の1組だけを持つ(`edit_item`で設定・0で解除)。`today_estimate_seconds()`が有効な日かを判定する
- 標準労働時間・スリープ検知は`~/.todoapp/config.json`(`repository/config_repository.py`)、設定ダイアログは`ui/settings_dialog.py`
- 祝日は`HolidayRepository`が`~/.todoapp/holidays.json`から読み、`main.py`が`dict[date, str]`として保持する(無い場合は空)
- 保存データは`~/.todoapp/todos.json`。スキーマ`version`は現在2で、`repository/json_repository.py`の`MIGRATIONS`で移行する
- Undo/Redoのスナップショットは`items`・`categories`・`link_templates`(`domain/undo.py`)
- 実行記録は0:00で日ごとに分割されるため、記録の`start_time.date()`で日ごとに集計できる

## 判断した点(レビューで確認したい)

1. **`残業時間`は「今日までの稼働日」で計算する**。月の途中で全稼働日の合計と比べると常に大きなマイナスになり、目標との比較が意味を持たないため。`残業時間 = 実績(期間内)− 今日以前の稼働日数 × 標準労働時間`。期間が全て過去なら、全稼働日の合計と一致する。`稼働日数`・`合計`は、ユーザー指示どおり期間全体(未来日を含む)で表示する
2. **見積りGAPは「見積りが記録された日」だけが対象**。`見積りGAP = その日の実績の合計 − 見積りの合計`(見積りのある日のみ)。導入前の日や見積りを入れていない日の実績を、そのまま超過として数えないため。符号は既存のGAPと同じ(超過が`+`、余りが`-`)
3. **休日出勤の実績も実績に含める**(稼働日でない日の記録も、`残業時間`に加わる)
4. **スキップ中のアイテムの見積りも集計に含める**(「集計画面は従来どおり扱う」の既存方針に合わせる)
5. **グラフは円グラフボタンと同じ切り替えボタンで表示/非表示**にし、他のタブと同様、開くたびに非表示から始める
6. **稼働日の上書きはUndoの対象外**(カレンダーの切り替えは編集系の操作ではなく、頻繁に使うため)。見積り履歴はUndoの対象(アイテムの編集と食い違わないため)

## データ(`domain/models.py`・`repository/json_repository.py`)

### 日ごとの見積り履歴

- `DailyEstimate`(新規): `day: date`・`item_id: str`・`seconds: int`
- `AppData.estimate_history: list[DailyEstimate]`(既定は空)。JSONでは`"estimate_history": [{"date": "2026-10-22", "item_id": "...", "seconds": 5400}]`
- 同じ(`day`, `item_id`)は1件だけ持つ。`TodoService.edit_item`が`today_estimate_hours`を受けたとき、`today_estimate_hours > 0`なら当日の分を追加・更新し、0なら当日の分を削除する(履歴の記録はここだけに置く)。秒は`round(hours × 3600)`
- アイテムを削除しても履歴は残す(その日に見積もった事実は消さない)。Undoでは`items`と一緒に履歴も戻す(`Snapshot`に`estimate_history`を加える)

### 稼働日の上書き

- `AppData.workday_overrides: dict[date, bool]`(既定は空)。JSONでは`"workday_overrides": {"2026-10-12": true}`
- `domain/work_summary.py`の`is_workday(day, overrides, holidays)`に判定を集約する: 上書きがあればその値、無ければ「平日(月〜金)かつ祝日でない」
- カレンダーで切り替えた結果が既定と同じになる場合は、上書きを削除する(保存データを最小に保つ)

### スキーマ移行(`version` 2 → 3)

- `SCHEMA_VERSION`を3に上げ、`MIGRATIONS[2]`を追加する(適用前の内容は既存の仕組みで`todos.json.v2.bak`へ残る)
- 移行関数は、`estimate_history`と`workday_overrides`を空で追加する。ただし、移行時点で`today_estimate_date`が設定済みで`today_estimate_hours > 0`のアイテムは、その日の分を履歴へ入れる(導入日当日の見積りを失わないため)

## ドメイン(`domain/work_summary.py`、新規)

画面に計算を持たせず、純粋関数に集める。

```python
@dataclass(frozen=True)
class WorkDayRow:
    day: date
    is_workday: bool
    estimate_seconds: int | None   # 履歴に1件も無い日は None
    actual_seconds: float

@dataclass(frozen=True)
class WorkSummary:
    start: date
    end: date
    rows: list[WorkDayRow]
    workday_count: int             # 期間全体の稼働日数
    total_seconds: float           # workday_count × 標準労働時間
    actual_seconds: float          # 期間内の実績の合計
    overtime_seconds: float        # 実績 − (今日以前の稼働日数 × 標準労働時間)。マイナスあり
    estimate_seconds: int          # 期間内の見積りの合計
    estimate_day_count: int        # 見積りが記録された日の数(0なら見積り・GAPは`-`表示)
    gap_seconds: float             # 見積りのある日の (実績 − 見積り) の合計
```

- `build_work_summary(start, end, today, standard_seconds, overrides, holidays, estimates, actuals)`: 日ごとの行と合計を作る。`estimates`は日ごとの見積り秒の辞書、`actuals`は日ごとの実績秒の辞書
- `TodoService.work_summary(start, end, holidays, standard_hours)`: 履歴・実行記録(実行中は現在時刻まで)から`estimates`・`actuals`を作って呼ぶ
- 期間は`start <= end`、最大366日。画面側で検証し、範囲外はサービスに渡さない
- `TodoService.set_workday(day, workday, holidays)`: 上書きを設定する(既定と同じなら削除)。Undoは対象外のため`@undoable`は付けず、`_save()`する

## 設定(`repository/config_repository.py`・`ui/settings_dialog.py`・`main.py`)

- `AppConfig.overtime_target_hours: float`(既定20.0)を追加し、`config.json`の`overtime_target_hours`へ保存する。読み込み時の不正値(数値でない・負数・上限超過)は既定値に戻す(`standard_work_hours`と同じ扱い)
- 設定ダイアログに`残業時間の目標(時間)`の入力欄を追加する。範囲は0以上744以下(0は「残業なし」を目標とする意味で許す)。範囲外は保存せず警告を表示する
- `SettingsDialog`の`on_save`は`(標準労働時間, 残業時間の目標, スリープ検知)`を受ける

## 画面(`ui/work_summary_panel.py`新規・`ui/category_summary_dialog.py`)

`CategorySummaryDialog`に3つ目のタブ`稼働集計`を加える。タブの中身は`WorkSummaryPanel`に切り出し、ダイアログ本体を大きくしない。`WorkSummaryPanel`は、サービス・標準労働時間・残業目標・祝日を取る関数を受け取る。

### 期間の指定

- 上部のトグルで`月`・`期間`を切り替える。開くたびに`月`(今月)から始め、保存しない
- `月`: `◀`・`2026年10月`・`▶`で月を移動する
- `期間`: `開始日`・`終了日`の日付入力。開始が終了より後、または366日を超える場合は警告を表示して更新しない

### 数字

| 項目 | 内容 |
|---|---|
| 稼働日数 | 期間内の稼働日の数(`N日`) |
| 合計 | 稼働日数 × 標準労働時間(`HH:MM`) |
| 実績 | 期間内の実行時間の合計(`HH:MM`) |
| 残業時間 | `overtime_seconds`(符号付き、`+HH:MM`/`-HH:MM`)。期間指定では合計であることを示す |
| 見積り | 見積りの合計(`HH:MM`)。履歴が無い期間は`-` |
| 見積りGAP | 符号付き(`+HH:MM`/`-HH:MM`)。対象の日が無い場合は`-` |

- `残業時間`の文字色: 目標を**上回った**とき(`残業 > 目標`)は赤、そうでなければ緑。ちょうどは上回りではない。丸めは秒で比べる。表示にマウスオーバーすると、`目標 20時間`のツールチップを出す
- 時間の書式は既存の`format_duration`・`format_gap`に合わせる(新しい書式を作らない)

### 稼働日の選択

- 折りたたみ`稼働日を選ぶ`の中に、期間内の月ごとのカレンダー(7列のボタン格子)を置く
- 日のボタンはクリックで稼働/非稼働を切り替える。稼働日は青、非稼働は灰色、祝日の非稼働は薄い緑。上書きされた日は枠線で区別する。祝日名はツールチップで表示する
- 切り替えると保存し、数字とグラフを更新する

### グラフ

- ECharts(既存の`ui.echart`)で日別の棒グラフ: `見積り`・`実績`を並べて表示し、`GAP`(見積りのある日のみ)を折れ線で重ねる。非稼働日も実績があれば表示する
- ツールチップは日付と、見積り・実績・GAPを`HH:MM:SS`で出す
- 右上の円グラフボタンで表示/非表示を切り替える(ボタンの色で表示中が分かる)。他のタブと同様、開くたびに非表示から始め、タブごとに独立して持つ
- 見積りが1件も無い期間では`見積り`・`GAP`の系列を出さない。実績が全て0の場合は、`この期間の記録はありません`を表示する

## エラー処理・境界

- 標準労働時間は設定ダイアログの検証済みの値を使う
- 祝日データが無い場合は、祝日を空として扱う(土日のみ除外)。`holidays.json`は`main.py`の読み込み後に更新されるため、ダイアログを開くたびに最新の辞書を参照する
- 実行中の記録は現在時刻までを実績に含める。集計画面は毎秒更新しないため、開いた時点・期間を変えた時点の値
- 日跨ぎで分割済みの記録は、各日に正しく振り分けられる

## テスト

- `domain/work_summary.py`: `is_workday`(平日・土日・祝日・上書き)、`build_work_summary`(稼働日数、合計、残業時間が今日以前の稼働日で計算されること、見積りのある日だけがGAPの対象、未来日、休日出勤、366日)
- `TodoService`: 見積り履歴の記録(設定・更新・0で解除・アイテム削除後も残る)、`work_summary`(実行中の記録、日跨ぎ)、`set_workday`(既定と同じなら上書きを削除)、Undoで履歴が戻ること
- `json_repository`: 移行(v2→v3、導入日の見積りを履歴へ、`.v2.bak`の作成)、保存と読み込みの往復
- `config_repository`: `overtime_target_hours`の既定値・不正値・往復
- 画面: タブ追加、月/期間の切り替えと検証、数字の表示、`残業時間`の色(上回り・ちょうど・下回り)、稼働日の切り替えが保存されること、グラフの表示切り替え、設定ダイアログの新しい項目と範囲検証
- 既存テストの更新: `SettingsDialog`の`on_save`の引数が変わる、集計画面のタブが増える

## ドキュメント

- `CLAUDE.md`: 「集計画面」に`稼働集計`の節を追加し、「設定」を3項目に、「データの保存先」にスキーマ`version`3・`estimate_history`・`workday_overrides`・`overtime_target_hours`を追記する
- `README.md`: 主な機能に追記する(キー操作は追加しないため、`SHORTCUT_KEYS`・ヘルプは変更なし)
- `docs/development.md`: 新しいモジュール(`domain/work_summary.py`・`ui/work_summary_panel.py`)を構成図へ追記する

## 追補(実装後の変更)

- **過不足時間**: 表示中の期間の終了日が今日より後のとき、`残業時間`は`過不足時間`と表示する(今日までの稼働日との差であり、残業ではないため)。終了日が今日以前なら`残業時間`。計算と色は変えない。`WorkSummary.in_progress`で判定する
- **月別の内訳**: `期間`指定のときだけ、期間を月で分けた表(`月`・`稼働日数`・`合計`・`実績`・`残業時間`)と`通算`の行を表示する(`monthly_breakdown()`)。期間の端の月は期間に含まれる日だけで集計する。月の行は目標と比べて色を付け、`通算`の行は色を付けない。月ごとの残業時間の和は、期間全体の残業時間と一致する
- **グラフの空表示**: 実績も見積りも無い期間だけ`この期間の記録はありません`を表示する(見積りだけがある期間はグラフを出す)
- **見積り履歴の更新**: 既存の1件は同じ位置で置き換える(付け直すと順序が変わり、変更の無い保存がUndoの履歴に積まれるため)
- **集計画面のレイアウト**: タブの領域は縮めず(`flex-none`)、ダイアログ側をスクロールさせる(縮めると稼働日の格子の下の方がクリップされて押せなくなるため)

## スコープ外

- 稼働日の上書きのUndo/Redo
- 導入前の過去日の見積りの復元
- 残業時間の目標の期間按分
- 稼働集計のCSV出力・コピー
