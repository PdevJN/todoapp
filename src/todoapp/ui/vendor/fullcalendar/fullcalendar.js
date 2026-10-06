import { loadResource } from "../../static/utils/resources.js";

export default {
  template: "<div></div>",
  props: {
    options: Array,
    resourcePath: String,
  },
  async mounted() {
    await this.$nextTick(); // wait for window.path_prefix to be set
    // upstream(zauberzeug/nicegui examples/fullcalendar)ではここでカレンダーを
    // 即座に構築していたが、実際の構築はダイアログが開かれた時(on_open)に
    // 一本化する(詳細はon_openのコメントを参照)。ここではライブラリの
    // ロードだけ済ませておく
    // 日本語localeはindex.global.min.jsが定義するFullCalendarグローバルに登録されるため、
    // 本体の読み込み完了後に読み込む(optionsのlocale: "ja"で有効になる)
    this._loaded = loadResource(window.path_prefix + `${this.resourcePath}/index.global.min.js`).then(() =>
      loadResource(window.path_prefix + `${this.resourcePath}/ja.global.min.js`),
    );
    this.options.eventClick = (info) => this.$emit("click", { info });
    // upstream(zauberzeug/nicegui examples/fullcalendar)には無い処理。祝日の日付に
    // マウスオーバーすると、ブラウザ既定のツールチップ(title属性)で祝日名を表示する。
    // 常時表示する小さな文字での追記は視認性が悪かったため、ホバー時のみの表示にしている。
    // this.options.holidays は {"YYYY-MM-DD": "祝日名"} 形式(set_holidaysで更新される)。
    // FullCalendarは日付を表すあらゆる要素(日表示・週表示の列ヘッダーとその日全体の列、
    // 月表示の日付セル)にdata-date属性を付与するため、それを目印に一括で反映することで、
    // 表示形式によらずその日の色付き領域全体でホバーできるようにする(日付テキスト部分に
    // 限定すると、週表示・日表示では列の大部分でツールチップが出ず一貫しなかったため)
    this.options.datesSet = () => this._applyHolidayTitles();
    // upstream(zauberzeug/nicegui examples/fullcalendar)には無い処理。ブロック内には
    // タスク名のみ表示し(displayEventTime: false)、マウスオーバー時のツールチップで
    // 開始・終了・経過時間(Python側extendedProps.tooltipで組み立て済み)を確認できるように
    // する。tooltipが無いイベント(祝日の背景イベント等)はタイトルのみをフォールバック表示
    // upstream(zauberzeug/nicegui examples/fullcalendar)には無い処理。ドラッグ&ドロップ
    // (eventDrop)・端のリサイズ(eventResize)で確定した開始・終了時刻をPython側へ通知する。
    // 表示位置の更新はPython側が隣接記録への吸着を計算した上でeventsを再設定して行うため、
    // FullCalendarが動かした位置は必ずrevertしてから通知する。日時はタイムゾーン無しの
    // ローカル時刻文字列にする(startStrはオフセット付きになり、Python側で扱いづらいため)
    const localIso = (date) => {
      const p = (n) => String(n).padStart(2, "0");
      return `${date.getFullYear()}-${p(date.getMonth() + 1)}-${p(date.getDate())}` +
        `T${p(date.getHours())}:${p(date.getMinutes())}:${p(date.getSeconds())}`;
    };
    const emitChange = (info, kind) => {
      const { id, start, end } = info.event;
      const edge = kind === "resize" ? (info.startDelta.milliseconds || info.startDelta.days ? "start" : "end") : null;
      const detail = { id, kind, edge, start: localIso(start), end: localIso(end) };
      info.revert();
      this.$emit("event_change", detail);
    };
    // upstream(zauberzeug/nicegui examples/fullcalendar)には無い処理。ドラッグ・リサイズ中、
    // 動かしているバー(FullCalendarが描画するミラー)が他のバーと重なったら、密着する境界
    // (ミラーの中心が他のバーの上半分なら上端、下半分なら下端)に濃い赤の線を表示する。
    // Python側の吸着計算(record_layout)とは独立した、画面上の位置からの目安表示であり、
    // 「収まらないため元に戻す」ケースまでは反映しない
    const start = () => this._startSnapGuide();
    const stop = () => this._stopSnapGuide();
    this.options.eventDragStart = start;
    this.options.eventResizeStart = start;
    this.options.eventDragStop = stop;
    this.options.eventResizeStop = stop;
    this.options.eventDrop = (info) => emitChange(info, "move");
    this.options.eventResize = (info) => emitChange(info, "resize");
    this.options.eventDidMount = (info) => {
      const tooltip = info.event.extendedProps && info.event.extendedProps.tooltip;
      info.el.title = tooltip || info.event.title || "";
    };
  },
  methods: {
    _startSnapGuide() {
      this._stopSnapGuide();
      const guide = document.createElement("div");
      guide.style.cssText =
        "position:absolute;height:3px;background:#b71c1c;pointer-events:none;z-index:20;display:none;";
      this.$el.style.position = "relative";
      this.$el.appendChild(guide);
      this._snapGuide = guide;
      this._onSnapMove = () => this._updateSnapGuide();
      document.addEventListener("mousemove", this._onSnapMove);
    },
    _stopSnapGuide() {
      if (this._onSnapMove) {
        document.removeEventListener("mousemove", this._onSnapMove);
        this._onSnapMove = null;
      }
      if (this._snapGuide) {
        this._snapGuide.remove();
        this._snapGuide = null;
      }
    },
    _updateSnapGuide() {
      const guide = this._snapGuide;
      const mirror = this.$el.querySelector(".fc-event-mirror");
      if (!guide || !mirror) {
        if (guide) guide.style.display = "none";
        return;
      }
      const m = mirror.getBoundingClientRect();
      const base = this.$el.getBoundingClientRect();
      const others = this.$el.querySelectorAll(
        ".fc-event:not(.fc-event-mirror):not(.fc-event-dragging):not(.fc-event-resizing)"
      );
      for (const el of others) {
        const o = el.getBoundingClientRect();
        if (m.top < o.bottom && m.bottom > o.top && m.left < o.right && m.right > o.left) {
          const above = m.top + m.height / 2 < o.top + o.height / 2;
          guide.style.left = `${o.left - base.left}px`;
          guide.style.width = `${o.width}px`;
          guide.style.top = `${(above ? o.top : o.bottom) - base.top - 1}px`;
          guide.style.display = "block";
          return;
        }
      }
      guide.style.display = "none";
    },
    _applyHolidayTitles() {
      const holidays = this.options.holidays || {};
      this.$el.querySelectorAll("[data-date]").forEach((el) => {
        const name = holidays[el.dataset.date];
        if (name) {
          el.title = name;
        } else {
          el.removeAttribute("title");
        }
      });
    },
    update_calendar() {
      if (this.calendar) {
        this.calendar.setOption("events", this.options.events);
        this.calendar.render();
      }
    },
    // upstream(zauberzeug/nicegui examples/fullcalendar)には無いメソッド。
    // events以外の任意のFullCalendarオプション(firstDay等)を切り替える
    set_option(name, value) {
      this.options[name] = value;
      if (this.calendar) {
        this.calendar.setOption(name, value);
      }
    },
    // upstream(zauberzeug/nicegui examples/fullcalendar)には無いメソッド。holidaysは
    // FullCalendar本体が認識する正規のオプションではないため、setOptionではなく直接
    // 差し替える。render()だけでは表示中の日付範囲が変わらない限りdatesSetが
    // 再発火せずツールチップが古いままになるため、明示的に反映し直す
    set_holidays(map) {
      this.options.holidays = map;
      if (this.calendar) {
        this.calendar.render();
        this._applyHolidayTitles();
      }
    },
    // upstream(zauberzeug/nicegui examples/fullcalendar)には無いメソッド。ダイアログを
    // 開いた直後に呼び出す。このコンポーネントはQuasarのQDialog(NiceGUIのui.dialog)の
    // 中に配置されており、ダイアログの開くアニメーション中は祖先要素に
    // `q-dialog__inner--minimized`というtransform: scale(0)状態のクラスが付与される。
    // transformはCSS上のレイアウト幅には影響しないが、実際に描画される幅
    // (getBoundingClientRect)は0になるため、アニメーションが終わる前にカレンダーを
    // 構築すると列幅が0で計算されてしまう。そのため、ライブラリのロード完了と、
    // ダイアログの開くトランジション完了(transitionendイベント)の両方を待ってから
    // 構築する。前回表示していた週ではなく常に今週から表示される
    async on_open() {
      await this._loaded;
      await this._waitForDialogTransition();
      if (this.calendar) {
        this.calendar.destroy();
      }
      this.calendar = new FullCalendar.Calendar(this.$el, this.options);
      this.calendar.render();
    },
    _waitForDialogTransition() {
      const inner = this.$el.closest(".q-dialog__inner");
      if (!inner || !inner.classList.contains("q-dialog__inner--minimized")) {
        return Promise.resolve();
      }
      return new Promise((resolve) => {
        const onDone = () => {
          inner.removeEventListener("transitionend", onDone);
          resolve();
        };
        inner.addEventListener("transitionend", onDone);
        // transitionendが発火しないケース(reduced motion設定等)に備えた保険
        setTimeout(onDone, 500);
      });
    },
  },
};
