"""Uploads check entrypoint annotations through sandboxcore's allow-list and store the canonical text.

The allow-list itself is tested in sandboxcore (tests/python/test_annotations.py).
"""

import pytest
from fastapi import HTTPException

from app.models import tools as db
from tests.test_tool_routes import create_tool


def test_upload_rejects_a_code_annotation_with_a_400(tmp_path):
    marker = tmp_path / "ran"
    code = f"# tag\n\n\ndef demo(value: open({str(marker)!r}, 'w').write('x') = 1) -> int:\n    return value\n"
    with pytest.raises(HTTPException) as info:
        create_tool(1, "demo", code)
    assert info.value.status_code == 400 and "Annotation Error" in info.value.detail and "value" in info.value.detail
    assert not marker.exists()


def test_upload_stores_the_canonical_annotation():
    code = '# tag\n\nfrom typing import Literal\n\n\ndef demo(kind: Literal["a", "b"] = "a") -> str:\n    return kind\n'
    assert create_tool(1, "demo", code).arguments == {"kind": ("Literal['a', 'b']", "a")}
