"""Annotations are checked at upload and resolved at run time without ever being evaluated."""

import ast
from pathlib import Path
from typing import Literal, get_args, get_origin

import pytest
from fastapi import HTTPException

from app.models import tools as db
from app.utility.annotations import AnnotationError, check_annotation, resolve_annotation


def annotation(text: str) -> ast.expr:
    return ast.parse(f"def f(x: {text}): pass").body[0].args.args[0].annotation


@pytest.mark.parametrize("text,expected", [("str", str), ("int", int), ("float", float), ("Path", Path)])
def test_simple_types_are_accepted(text, expected):
    assert check_annotation(annotation(text)) == text and resolve_annotation(text) is expected


def test_literals_of_plain_values_are_accepted():
    text = check_annotation(annotation('Literal["png", "jpg", 3, 1.5]'))
    resolved = resolve_annotation(text)
    assert get_origin(resolved) is Literal and get_args(resolved) == ("png", "jpg", 3, 1.5)
    assert get_args(resolve_annotation("Literal['only']")) == ("only",)


HOSTILE = [
    "__import__('os').system('id')",
    "eval('1')",
    "os.system",
    "str.__class__",
    "type('x', (), {})",
    "(lambda: 1)()",
    "[str][0]",
    "str if True else int",
    "Literal[__import__('os').getcwd()]",
    "Literal['a' + 'b']",
    "Literal[f'{1}']",
    "Literal[True]",
    "Literal[None]",
    "Literal[b'x']",
    "Literal['has space']",
    "Literal['../x']",
    "Literal[()]",
    "typing.Literal['a']",
    "Optional[Path]",
    "list[str]",
    "bool",
    "Path | None",
]


@pytest.mark.parametrize("text", HOSTILE)
def test_anything_else_is_rejected_at_upload(text):
    with pytest.raises(AnnotationError):
        check_annotation(annotation(text))


@pytest.mark.parametrize("text", HOSTILE + ["not python (", "", "str; import os", "x" * 5000])
def test_stored_text_outside_the_allow_list_is_refused_at_run_time(text):
    with pytest.raises(AnnotationError):
        resolve_annotation(text)


def test_resolving_hostile_stored_text_runs_nothing(tmp_path):
    marker = tmp_path / "ran"
    with pytest.raises(AnnotationError):
        resolve_annotation(f"open({str(marker)!r}, 'w').write('x')")
    with pytest.raises(AnnotationError):
        resolve_annotation(f"Literal[open({str(marker)!r}, 'w').write('x')]")
    assert not marker.exists()


def test_upload_rejects_a_code_annotation_with_a_400(tmp_path):
    marker = tmp_path / "ran"
    code = f"# tag\n\n\ndef demo(value: open({str(marker)!r}, 'w').write('x') = 1) -> int:\n    return value\n"
    with pytest.raises(HTTPException) as info:
        db.create_tool(1, "demo", code)
    assert info.value.status_code == 400 and "Annotation Error" in info.value.detail and "value" in info.value.detail
    assert not marker.exists()


def test_upload_stores_the_canonical_annotation():
    code = '# tag\n\nfrom typing import Literal\n\n\ndef demo(kind: Literal["a", "b"] = "a") -> str:\n    return kind\n'
    assert db.create_tool(1, "demo", code).arguments == {"kind": ("Literal['a', 'b']", "a")}
