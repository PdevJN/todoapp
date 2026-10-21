from todoapp.domain.undo import MAX_HISTORY, Snapshot, UndoHistory


def _snapshot(tag: str) -> Snapshot:
    return Snapshot(items=[], categories=[], link_templates=[], record_names={"r": tag})


def test_undo_on_empty_history_returns_none() -> None:
    history = UndoHistory()
    assert history.undo(_snapshot("now")) is None
    assert history.redo(_snapshot("now")) is None


def test_undo_returns_pushed_snapshot_and_moves_current_to_redo() -> None:
    history = UndoHistory()
    history.push("削除", _snapshot("before"))

    assert history.undo(_snapshot("after")) == ("削除", _snapshot("before"))
    assert history.redo(_snapshot("before")) == ("削除", _snapshot("after"))


def test_push_clears_redo() -> None:
    history = UndoHistory()
    history.push("a", _snapshot("1"))
    history.undo(_snapshot("2"))

    history.push("b", _snapshot("3"))

    assert history.redo(_snapshot("4")) is None


def test_history_keeps_only_the_latest_limit_entries() -> None:
    history = UndoHistory()
    for i in range(MAX_HISTORY + 10):
        history.push(f"op{i}", _snapshot(str(i)))

    labels = []
    while (entry := history.undo(_snapshot("now"))) is not None:
        labels.append(entry[0])

    assert len(labels) == MAX_HISTORY
    assert labels[0] == f"op{MAX_HISTORY + 9}"
    assert labels[-1] == "op10"


def test_redo_stack_is_also_limited() -> None:
    history = UndoHistory(limit=2)
    for i in range(3):
        history.push(f"op{i}", _snapshot(str(i)))
    for _ in range(2):
        history.undo(_snapshot("now"))

    assert [history.redo(_snapshot("now")) is not None for _ in range(3)] == [True, True, False]
