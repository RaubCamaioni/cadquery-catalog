from pathlib import Path
import pytest
import re

from app.utility import render


def test_list_items_loader_requests_a_full_next_page():
    tools = [(i, f"tool{i}") for i in range(50)]
    html = render.list_items("", tools, end=50, page=50)
    # the infinite-scroll loader must fetch the next 50, not one tool at a time
    assert re.search(r'hx-post="/models\?start=50&(amp;)?end=100"', html), html[-300:]


def test_list_items_without_more_pages_has_no_loader():
    html = render.list_items("", [(1, "a")], end=None)
    assert "hx-post" not in html


def test_render_dict_is_key_value_rows_with_copy_brackets():
    html = render.render({"scientific": "6.022e23", "exponent": 23, "nested": {"a": [1, 2]}})
    # the value and its bracket share one cell right after the key
    assert (
        '<span class="key">scientific:</span><span class="cell"><span class="val str">6.022e23</span>'
        '<button type="button" class="copy" data-copy="6.022e23">[copy]</button></span>'
    ) in html
    assert '<span class="val num">23</span>' in html and "'" not in html  # no python quotes anywhere
    # a nested container gets its own indented block under its key
    assert '<span class="key">nested:</span>' in html and '<div class="nest"><div class="kv-table">' in html
    assert '<span class="key">a:</span>' in html and '<span class="bullet">-</span><span class="val num">1</span>' in html


def test_render_copy_all_is_raw_text_for_a_string_and_json_otherwise():
    html = render.render("two\nlines")
    assert 'data-copy="two\nlines">[copy]' in html and "[copy all]" not in html  # one value, one bracket
    html = render.render({"a": [1, "b"], "p": Path("/r/x.txt")})
    assert 'data-copy="{\n  &quot;a&quot;: [\n    1,\n    &quot;b&quot;\n  ],\n  &quot;p&quot;: &quot;' in html


def test_render_list_is_bullet_rows_copied_whole():
    html = render.render([f"item-{i:02d}" for i in range(3)])
    assert html.count('<span class="bullet">-</span>') == 3 and "[copy]" not in html
    assert 'data-copy="item-00\nitem-01\nitem-02">[copy all]' in html  # one item per line, no quotes
    # a list under a key: the bracket sits by the key and copies that list
    html = render.render({"words": ["a", "b"], "n": 1})
    assert '<span class="key">words:</span><span class="cell"><button type="button" class="copy" data-copy="a\nb">' in html
    assert html.count("[copy]") == 2  # the list and the number; not the items


def test_render_strings_are_raw_and_escaped():
    html = render.render("0x68 0x69")
    assert '<span class="val str">0x68 0x69</span>' in html and "'0x68" not in html
    html = render.render("<b>not html</b> & co")
    assert "&lt;b&gt;not html&lt;/b&gt; &amp; co" in html and "<b>" not in html
    assert '<span class="val num">42</span>' in render.render(42)
    assert '<span class="val lit">True</span>' in render.render(True)
    assert '<span class="val lit">{}</span>' in render.render({}) and "[copy all]" not in render.render({})


def test_render_image_result_is_previewed_inline():
    html = render.render({"file": Path("/runs/abc/out.PNG")})
    assert '<a href="/download/runs/abc/out.PNG" download="out.PNG"' in html
    assert '<img class="preview" src="/download/runs/abc/out.PNG?preview=1" alt="out.PNG"' in html


def test_render_media_results_are_embedded():
    html = render.render([Path("/r/a.mp3"), Path("/r/b.webm"), Path("/r/c.pdf"), Path("/r/d.stl")])
    assert '<audio class="preview" controls="" preload="metadata" src="/download/r/a.mp3?preview=1">' in html
    assert '<video class="preview" controls="" preload="metadata" src="/download/r/b.webm?preview=1">' in html
    assert '<object class="preview document" data="/download/r/c.pdf?preview=1" type="application/pdf">' in html
    assert '<stl-viewer url="/download/r/d.stl">' in html


def test_render_other_files_are_links_only():
    html = render.render(Path("/runs/abc/out.csv"))
    assert "<a href=" in html and "<img" not in html and "<object" not in html


def test_preview_media_types():
    assert render.preview_media_type("a.webp") == "image/webp"
    assert render.preview_media_type("a.m4a") == "audio/mp4"
    assert render.preview_media_type("a.pdf") == "application/pdf"
    assert render.preview_media_type("a.png") == "image/png"


def test_number_arguments_are_typed_not_spun():
    html = render.args_to_form({"ratio": ("float", "0.3"), "count": ("int", "2")})
    assert 'type="number"' not in html and html.count('inputmode="decimal"') == 2


def test_argument_inputs_are_console_fields():
    html = render.args_to_form({"count": ("int", "1"), "mode": ("Literal['a', 'b']", "a")})
    assert html.count('<span class="field') == 1 and html.count('<span class="pick') == 1  # text: underscore caret; list: arrow


def test_user_tool_table_starts_with_a_header_row():
    from app.models.tools import Tool

    html = render.list_item_user("", [Tool(id=1, name="a", code="", public=True, annonymous=True, usage=3)])
    assert html.index("NAME") < html.index("MODE") < html.index("RUNS") < html.index("ACTIONS") < html.index("a.py")
    assert html.index("a.py") < html.index("[public]")  # the name, the row's identifier, comes first
    assert html.index("ACTIONS") < html.index("[upload]") < html.index("a.py")  # the upload row leads the table
    assert html.count('<li class="contents') == 3  # header + upload row + one tool row, all grid rows
    assert html.count(">---<") == 3  # name, mode and runs do not apply to the upload row; [upload] is its action


@pytest.mark.parametrize(
    "count, text",
    [(0, "0"), (9999, "9999"), (10000, "10K"), (12345, "12K"), (999999, "999K"), (1000000, "1.0M"),
     (1234567, "1.2M"), (9999999, "9.9M"), (10000000, "10M"), (999999999, "999M"), (1000000000, "1.0B")],
)
def test_format_runs_fits_four_characters(count, text):
    assert render.format_runs(count) == text and len(text) <= 4


def test_result_paths_render_as_download_links():
    html = render.render(Path("/tmp/pywebtools-runs/abc/qr_code.png"))
    assert 'href="/download/tmp/pywebtools-runs/abc/qr_code.png"' in html.replace("\\", "/")
    assert 'download="qr_code.png"' in html
