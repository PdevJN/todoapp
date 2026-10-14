// ui.table(QTable)の行を、SortableJSでドラッグ&ドロップできるようにする。
// 行はVueが管理しているため、ドロップした行はいったん元の位置へ戻し、並び替えはサーバー側で行って再描画させる。
export default {
  template: "<div></div>",
  props: {
    tableId: Number,
    fixedRows: Number,
    delay: Number,
  },
  async mounted() {
    const { Sortable } = await import("nicegui-sortable");
    this.Sortable = Sortable;
    this.attach();
    // 表の再描画でtbodyが作り直された場合に、付け直す
    this.observer = new MutationObserver(() => this.attach());
    this.retryTimer = setInterval(() => {
      if (this.sortable) return clearInterval(this.retryTimer);
      this.attach();
    }, 100);
    const table = document.getElementById("c" + this.tableId);
    if (table) this.observer.observe(table, { childList: true, subtree: true });
  },
  unmounted() {
    clearInterval(this.retryTimer);
    this.observer?.disconnect();
    this.sortable?.destroy();
  },
  methods: {
    attach() {
      const body = document.getElementById("c" + this.tableId)?.querySelector("tbody");
      if (!body || body === this.body) return;
      this.sortable?.destroy();
      this.body = body;
      const rows = () => [...body.children];
      this.sortable = this.Sortable.create(body, {
        animation: 150,
        delay: this.delay,
        draggable: "tr",
        ghostClass: "opacity-50",
        preventOnFilter: false,
        // 先頭の固定行と、選択用のチェックボックスからはドラッグを始めない
        filter: (_event, target) => {
          const row = target.closest("tr");
          return !row || rows().indexOf(row) < this.fixedRows || !!target.closest(".q-checkbox");
        },
        onMove: (event) => rows().indexOf(event.related) >= this.fixedRows,
        onStart: (event) => {
          this.nextSibling = event.item.nextSibling;
        },
        onEnd: (event) => {
          body.insertBefore(event.item, this.nextSibling);
          if (event.oldIndex !== event.newIndex) {
            this.$emit("reorder", { old_index: event.oldIndex, new_index: event.newIndex });
          }
        },
      });
    },
  },
};
