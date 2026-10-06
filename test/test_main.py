from todoapp import main


def test_main_module_importable() -> None:
    assert hasattr(main, "main")
