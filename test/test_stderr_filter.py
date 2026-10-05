from todoapp.stderr_filter import filter_lines


def test_filter_lines_drops_only_suppressed_message() -> None:
    lines = [
        b"2026 app[1:2] Text input context does not respond to _valueForTIProperty:\n",
        b"_TIPropertyValueIsValid called with 4 on nil context!\n",
        b"imkxpc_getApplicationProperty:reply: called with incorrect property value 4, bailing.\n",
        b"real error\n",
    ]
    assert list(filter_lines(lines)) == [b"real error\n"]
