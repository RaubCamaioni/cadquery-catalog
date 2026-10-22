import pytest
from fastapi import HTTPException

from app.models import tools as db


def source(line: str) -> str:
    return "# tag\n\n" + line + "\n\n\ndef demo(value: int = 1) -> int:\n    return value\n"


def test_line_at_the_limit_is_accepted():
    tool = db.create_tool(1, "demo", source("x = 1  " + "#" * (db.MAX_LINE_LENGTH - 7)))
    assert tool.name == "demo" and tool.arguments == {"value": ("int", "1")}


def test_line_over_the_limit_is_rejected_with_its_number():
    line = "x = '" + "a" * db.MAX_LINE_LENGTH + "'"
    with pytest.raises(HTTPException) as info:
        db.create_tool(1, "demo", source(line))
    assert info.value.status_code == 400
    assert info.value.detail.startswith(f"Line Too Long: line 3 has {len(line)} characters")


def test_invalid_python_is_rejected_before_the_length_check():
    # the formatter runs first and cannot parse this, so the syntax problem is the one reported
    with pytest.raises(HTTPException) as info:
        db.create_tool(1, "demo", source("def (" + "a" * 130))
    assert info.value.status_code == 400 and "Syntax Error" in info.value.detail


def test_long_code_line_is_wrapped_by_the_formatter():
    call = "x = max(" + ", ".join(f"value_{n}" for n in range(30)) + ")"
    assert len(call) > db.MAX_LINE_LENGTH
    tool = db.create_tool(1, "demo", source(call))
    assert all(len(line) <= db.MAX_LINE_LENGTH for line in tool.code.splitlines())
    assert "value_29,\n)" in tool.code


def test_uploads_are_black_formatted():
    tool = db.create_tool(1, "demo", "# tag\nimport os\ndef demo(value:int=1)->int:\n  return  value")
    assert tool.code == "# tag\nimport os\n\n\ndef demo(value: int = 1) -> int:\n    return value\n"
    assert tool.arguments == {"value": ("int", "1")}


def test_upload_ends_with_exactly_one_newline():
    for ending in ("", "\n", "\n\n\n"):
        tool = db.create_tool(1, "demo", source("x = 1").rstrip("\n") + ending)
        assert tool.code.endswith("value\n") and not tool.code.endswith("\n\n")


def test_windows_line_endings_are_normalised():
    tool = db.create_tool(1, "demo", source("x = 1").replace("\n", "\r\n"))
    assert "\r" not in tool.code and tool.tags == ["tag", "demo"]


@pytest.mark.parametrize("name", ["storage_box", "spacer"])
def test_shipped_models_pass(name):
    from pathlib import Path

    code = (Path(__file__).resolve().parents[2] / "models" / f"{name}.py").read_text(encoding="utf-8")
    tool = db.create_tool(1, name, code)
    assert tool.name == name and all(t in ("int", "float", "str") or t.startswith("Literal") for t, _ in tool.arguments.values())


def test_path_parameters_are_rejected():
    code = "# tag\n\nfrom pathlib import Path\n\n\ndef demo(value: int = 1, shape: Path = None) -> int:\n    return value\n"
    with pytest.raises(HTTPException) as info:
        db.create_tool(1, "demo", code)
    assert info.value.status_code == 400 and "'shape' is a Path" in info.value.detail


def test_hardware_words_pass_the_profanity_filter():
    pf = next(db.get_filter())
    assert pf.is_clean("a knob with a screw hole") and not pf.is_clean("fuck")
