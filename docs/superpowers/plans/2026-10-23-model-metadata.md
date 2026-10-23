# Model Metadata (Categories and Tags) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Catalog models get tags and categories as database metadata set in the upload form and edited on the model page, browsable through a curated two-level category tree, with a metadata layer that later kinds can join.

**Architecture:** `app/categories.py` loads the tree from `app/categories.yaml`. `app/metadata/` holds one module per metadata kind (tags, categories), each owning its table, form parsing, storage and templates, and a registry whose `apply` the upload, update and edit routes call. Search moves from the JSON `Tool.tags` column to the `ModelTag` table; category pages filter on `ModelCategory`.

**Tech Stack:** FastAPI, SQLModel on SQLite, Jinja2, htmx + hyperscript, PyYAML, pytest.

**Spec:** `docs/superpowers/specs/2026-10-23-model-metadata-design.md`

## Global Constraints

- Lines at most 120 characters (ruff `line-length = 120`); match the surrounding comment style (short `#` comments that say why).
- Category slugs match `^[a-z][a-z0-9-]*$`; a filed path is `<category>/<subcategory>` or `misc`.
- Tags: lowercased, trimmed, inner whitespace to `-`, must match `^[a-z0-9][a-z0-9.+-]{0,29}$`, duplicates dropped, at most 10 per model.
- Categories: at most 3 per model, first is primary, duplicates rejected, `misc` cannot be combined with other paths.
- Metadata is never read from the script; line 1 is no longer parsed.
- A model with no effective categories shows under Miscellaneous (`misc`).
- Only public models appear in listings, category pages, counts and tag suggestions.
- Owner-or-admin checks return 404 to anyone else, as code updates do.
- PyTools is not touched.
- Tests run on the server (the app's runner tests need FIFOs). Test command, run from the worktree root in Git Bash:
  `tar -C server -cf - src tests pyproject.toml MANIFEST.in | ssh root@192.155.89.63 'rm -rf /tmp/catdev && mkdir /tmp/catdev && tar -C /tmp/catdev -xf - && chown -R pytools: /tmp/catdev && su - pytools -c "cd /tmp/catdev && ~/catalog/dev/.venv/bin/pip install -q --no-deps -e . && ~/catalog/dev/.venv/bin/python -m pytest -m \"not integration\" -q -p no:cacheprovider $ARGS"'`
  (`ARGS` = test file or `-k` filter; empty runs everything). Install PyYAML into that venv once (Task 1).
- Commits end with `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`; work on branch `feat/model-metadata`, merged by squash PR.

## Review Focus

1. Search text containing `%` or `_` must match literally, not as SQL wildcards: test in Task 4 (`test_search_escapes_like_wildcards`).
2. A private model must never show on a category page, in a category count or in tag suggestions: tests in Tasks 2 and 7.
3. Emptying the categories editor and saving puts the model under Miscellaneous; it must not vanish from browsing: test in Task 5 (`test_cleared_categories_fall_back_to_misc_page`).
4. Tags typed with capitals, spaces or trailing commas (`"Kitchen Tools, "`) normalise instead of failing: test in Task 2.
5. `apply-manifest` meeting two owner models with the same name must stop rather than guess: test in Task 8.

---

### Task 1: Category tree

**Files:**
- Create: `server/src/app/categories.yaml`
- Create: `server/src/app/categories.py`
- Modify: `server/MANIFEST.in` (add `include src/app/categories.yaml`)
- Modify: `server/pyproject.toml` (dependency `"pyyaml>=6.0"`)
- Test: `server/tests/test_categories.py`

**Interfaces:**
- Produces:
  - `class Category` (dataclass, frozen): `slug: str`, `name: str`, `description: str`, `subcategories: tuple[Category, ...]`, `path: str`
  - `class CategoryError(ValueError)`
  - `load_tree(text: str) -> tuple[Category, ...]`: parses and validates YAML text, raises `CategoryError`
  - `TREE: tuple[Category, ...]`: loaded from the shipped file at import
  - `is_leaf(path: str) -> bool`, `label(path: str) -> str` (`"Home › Kitchen"`, `"Miscellaneous"`),
    `paths_under(slug: str) -> list[str]`, `leaves() -> list[tuple[str, str]]` (path, label) in file order,
    `find(path: str) -> Optional[Category]` (top-level or leaf), `MISC = "misc"`

- [ ] **Step 1: Write `categories.yaml`** with the spec's tree exactly (6 categories, 23 subcategories, then `misc`), slugs and names from the spec table, one-line descriptions (the spec's for `home`, `kitchen`, `misc`; write the rest in the same voice).

- [ ] **Step 2: Write the failing tests**

```python
def test_shipped_tree_loads():
    assert [c.slug for c in categories.TREE] == ["home", "office", "workshop", "hardware", "outdoor", "hobbies", "misc"]
    assert sum(len(c.subcategories) for c in categories.TREE) == 23
    assert categories.label("home/kitchen") == "Home › Kitchen" and categories.label("misc") == "Miscellaneous"
    assert categories.is_leaf("home/kitchen") and categories.is_leaf("misc") and not categories.is_leaf("home")
    assert "workshop/tool-storage" in categories.paths_under("workshop") and categories.paths_under("misc") == ["misc"]

@pytest.mark.parametrize("bad, message", [
    ("- {slug: Home, name: H, description: d, subcategories: [{slug: a, name: A, description: d}]}\n- {slug: misc, name: M, description: d}", "slug"),
    ("- {slug: home, name: H, description: d, subcategories: []}\n- {slug: misc, name: M, description: d}", "subcategor"),
    ("- {slug: home, name: H, description: d, subcategories: [{slug: a, name: A, description: d}, {slug: a, name: B, description: d}]}\n- {slug: misc, name: M, description: d}", "duplicate"),
    ("- {slug: home, name: H, description: d, subcategories: [{slug: a, name: A, description: d}]}", "misc"),
    ("- {slug: home, name: H, subcategories: [{slug: a, name: A, description: d}]}\n- {slug: misc, name: M, description: d}", "description"),
    ("- {slug: home, name: H, description: d, subcategories: [{slug: a, name: A, description: d, subcategories: [{slug: b, name: B, description: d}]}]}\n- {slug: misc, name: M, description: d}", "nest"),
])
def test_bad_trees_are_rejected(bad, message):
    with pytest.raises(categories.CategoryError, match=message):
        categories.load_tree(bad)
```

- [ ] **Step 3: Run tests to verify they fail.** First install PyYAML once: `ssh root@192.155.89.63 'su - pytools -c "~/catalog/dev/.venv/bin/pip install -q pyyaml"'`. Run with `ARGS=tests/test_categories.py`. Expected: FAIL (`ModuleNotFoundError: app.categories`).

- [ ] **Step 4: Implement `app/categories.py`.** `yaml.safe_load`; the error messages contain the words the tests match (`slug`, `subcategories`, `duplicate`, `misc`, `description`, `nest`). `TREE = load_tree((Path(__file__).parent / "categories.yaml").read_text(encoding="utf-8"))`.

- [ ] **Step 5: Run tests to verify they pass.** `ARGS=tests/test_categories.py`. Expected: all PASS.

- [ ] **Step 6: Commit** `git add server/src/app/categories.* server/MANIFEST.in server/pyproject.toml server/tests/test_categories.py && git commit -m "Category tree: categories.yaml and its loader"`

### Task 2: Metadata registry and the tags kind

**Files:**
- Create: `server/src/app/metadata/__init__.py`, `server/src/app/metadata/tags.py`
- Create: `server/src/app/webapp/templates/components/meta_tags_editor.html`, `meta_tags_display.html`
- Modify: `server/src/app/models/tools.py` (import `app.metadata` table modules before `create_all` in `create_db_and_tables`)
- Modify: `server/tests/conftest.py` (the `session_with_models` fixture)
- Test: `server/tests/test_metadata_tags.py`

**Interfaces:**
- Produces (in `app/metadata/__init__.py`):
  - `class MetadataError(ValueError)`
  - `class MetadataKind(Protocol)`: `key: str`, `editor_template: str`, `display_template: str`,
    `parse(form: Mapping[str, list[str]]) -> Optional[Any]`, `save(session, model_id: int, value) -> None`,
    `load(session, model_ids: list[int]) -> dict[int, Any]`
  - `KINDS: list[MetadataKind]` (Task 2 registers tags; Task 3 appends categories)
  - `parse_all(form: Mapping[str, list[str]]) -> dict[str, Any]` (only kinds that returned non-None; any `MetadataError` propagates before anything is saved)
  - `save_all(session, model_id: int, parsed: dict[str, Any]) -> None`
  - `apply(session, model_id: int, form) -> None` = `save_all(session, model_id, parse_all(form))`
  - `load_all(session, model_ids: list[int]) -> dict[int, dict[str, Any]]`
  - `form_lists(form: FormData) -> dict[str, list[str]]` (Starlette `FormData.getlist` per key)
- Produces (in `app/metadata/tags.py`):
  - `class ModelTag(SQLModel, table=True)`: `model_id: int` (FK `tool.id`, PK), `tag: str` (PK, indexed)
  - `normalise(raw: str) -> str` (raises `MetadataError` on an invalid result)
  - `class Tags`: `key = "tags"`; `parse` reads `form["tags"]` (each value may hold several comma-separated tags), returns `None` unless `"tags.present"` is in the form; `save` replaces the model's rows; `load` returns `{id: [tags in insertion order]}`
  - `suggest(session, prefix: str, limit: int = 10) -> list[tuple[str, int]]` (public models only, count desc then tag asc)

- [ ] **Step 1: Write the failing tests**

```python
def test_normalise():
    assert tags.normalise("  Kitchen Tools ") == "kitchen-tools"
    assert tags.normalise("M3") == "m3"
    for bad in ["", "-x", "a" * 31, "café", "a/b"]:
        with pytest.raises(MetadataError):
            tags.normalise(bad)

def test_parse_splits_commas_drops_duplicates_and_limits():
    form = {"tags.present": ["1"], "tags": ["Kitchen Tools, ", "kitchen-tools", "M3"]}
    assert tags.Tags().parse(form) == ["kitchen-tools", "m3"]
    assert tags.Tags().parse({}) is None
    assert tags.Tags().parse({"tags.present": ["1"]}) == []
    with pytest.raises(MetadataError, match="10"):
        tags.Tags().parse({"tags.present": ["1"], "tags": [f"t{i}" for i in range(11)]})

def test_profane_tag_is_rejected(): ...  # uses get_filter(); a word the filter flags -> MetadataError

def test_save_replaces_and_load_batches(session_with_models): ...  # save [a,b] then [b,c]; load([id1,id2]) -> {id1:[b,c], id2:[]}

def test_suggest_counts_public_models_only(session_with_models):
    # public models tagged kitchen x2, kettle x1; a private model tagged kitchen
    assert tags.suggest(session, "k") == [("kitchen", 2), ("kettle", 1)]
    assert tags.suggest(session, "") [0] == ("kitchen", 2)

def test_apply_parses_everything_before_saving(session_with_models):
    # a form whose tags are valid and a fake second kind whose parse raises: nothing stored
```

Put a `session_with_models` fixture in `server/tests/conftest.py`: an in-memory engine (`sqlite://`, `check_same_thread=False`) with `create_all`, yielding `(session, make)` where `make(name, public=True)` adds a `Tool` and returns its id.

- [ ] **Step 2: Run tests to verify they fail.** `ARGS=tests/test_metadata_tags.py`. Expected: FAIL on import.

- [ ] **Step 3: Implement `app/metadata/__init__.py` and `app/metadata/tags.py`.** Profanity: `get_filter()` from `app.models.tools`, `is_clean(tag)`. `suggest` is one `GROUP BY tag` query joined to `Tool` with `Tool.public == True` and `tag LIKE prefix || '%'` (prefix escaped as in Task 4).

- [ ] **Step 4: Editor and display partials.** `meta_tags_editor.html`: hidden `tags.present`, existing tags as chips each with a hidden `tags` input and `[x]`, a text input with `list="tag-suggestions"` whose `input` fetches `{{ root_path }}/tags/suggest?q=` (Task 5 adds the route) into a `<datalist id="tag-suggestions">`; Enter or `,` turns the text into a chip. `meta_tags_display.html`: tags as links to `{{ root_path }}/?search=<tag>`.

- [ ] **Step 5: Run tests to verify they pass.** Expected: PASS.

- [ ] **Step 6: Commit** "Metadata registry and the tags kind"

### Task 3: The categories kind

**Files:**
- Create: `server/src/app/metadata/categories.py`
- Create: `server/src/app/webapp/templates/components/meta_categories_editor.html`, `meta_categories_display.html`
- Modify: `server/src/app/metadata/__init__.py` (register `Categories()` after `Tags()`)
- Test: `server/tests/test_metadata_categories.py`

**Interfaces:**
- Consumes: Task 1 `categories.is_leaf`, `label`, `leaves`, `MISC`; Task 2 `MetadataKind`, `MetadataError`.
- Produces:
  - `class ModelCategory(SQLModel, table=True)`: `model_id: int` (FK, PK), `path: str` (PK, indexed), `position: int`
  - `class Categories`: `key = "categories"`; `parse` returns `None` unless `"categories.present"`; returns the ordered list; `save` replaces rows with positions 0..n; `load` returns `{id: effective list}`
  - `effective(paths: list[str]) -> list[str]`: stored paths still leaves in the tree, in order; `["misc"]` if none remain
  - `model_ids_in(session, paths: list[str]) -> Select` subquery of model ids filed under any of `paths` (by effective category, so models with no rows or only dead paths count as `misc`)

- [ ] **Step 1: Write the failing tests**

```python
def parse(*paths):
    return categories_kind.Categories().parse({"categories.present": ["1"], "categories": list(paths)})

def test_parse_valid_and_ordered():
    assert parse("workshop/tool-storage", "home/storage") == ["workshop/tool-storage", "home/storage"]
    assert parse() == [] and parse("misc") == ["misc"]

@pytest.mark.parametrize("paths, message", [
    (("home/kitchen",) * 2, "duplicate"),
    (("home/kitchen", "home/bathroom", "home/decor", "home/storage"), "3"),
    (("home/cooking",), "unknown"),
    (("home",), "unknown"),
    (("misc", "home/kitchen"), "misc"),
])
def test_parse_rejects(paths, message): ...

def test_effective_falls_back_to_misc():
    assert categories_kind.effective([]) == ["misc"]
    assert categories_kind.effective(["gone/away"]) == ["misc"]
    assert categories_kind.effective(["gone/away", "home/kitchen"]) == ["home/kitchen"]

def test_model_ids_in_counts_unfiled_models_as_misc(session_with_models): ...
    # a: home/kitchen; b: no rows; c: gone/away -> ids in ["misc"] == {b, c}; ids in ["home/kitchen"] == {a}
```

The "unknown" message lists the valid paths (assert `"home/kitchen" in str(err)`).

- [ ] **Step 2: Run tests to verify they fail.** `ARGS=tests/test_metadata_categories.py`. Expected: FAIL on import.

- [ ] **Step 3: Implement `app/metadata/categories.py`.** For `model_ids_in` with `"misc"` in `paths`, also include `Tool.id` values having no `ModelCategory` row whose `path` is a live leaf: `~exists(select ModelCategory where model_id == Tool.id and path in live_leaves)`.

- [ ] **Step 4: Editor and display partials.** Editor: hidden `categories.present`; chips (hidden `categories` input with the path, label text, `[<]` `[>]` `[x]`, first chip prefixed `primary:`); a text input with `list="category-options"` and a `<datalist>` rendered from `categories.leaves()` (option value = label, `data-path` = path); choosing an option adds a chip, and a fourth is refused with a note. Display: primary as a breadcrumb linking to `/c/<category>` and `/c/<category>/<sub>` (or `/c/misc`), extras as links.

- [ ] **Step 5: Run tests to verify they pass.** Expected: PASS.

- [ ] **Step 6: Commit** "Metadata: the categories kind"

### Task 4: Retire Tool.tags and move search to ModelTag

**Files:**
- Modify: `server/src/app/models/tools.py` (remove `Tool.tags` field and `get_tags`; `create_tool` stops parsing line 1; replace `get_tools_by_tags`; one-time copy at startup)
- Modify: `server/src/app/routes/tools.py:165-190` (`get_tools` calls `search_models`)
- Modify: `server/tests/test_tags.py` (rewrite for the new search), any test constructing `Tool(tags=...)`
- Test: `server/tests/test_tags.py`, `server/tests/test_tag_migration.py`

**Interfaces:**
- Consumes: Task 2 `ModelTag`; Task 3 `model_ids_in`.
- Produces:
  - `search_models(session, words: list[str], start: int, end: int, category: Optional[str] = None) -> list[tuple[int, str]]`: public models; each word matches `Tool.name` (case-insensitive substring) or a tag (exact; the last word also by prefix); `category` is a top-level slug or a leaf path, filtered through `model_ids_in(paths_under(slug) or [path])`; ordered by `Tool.id`
  - `copy_json_tags(engine) -> int`: if `modeltag` is empty, inserts each model's JSON `tags` minus its own name (read with raw SQL from the still-present `tool.tags` column, normalised, invalid ones skipped); returns rows inserted
  - `create_db_and_tables()` calls `copy_json_tags(engine)` after `migrate`

- [ ] **Step 1: Write the failing tests**

```python
def test_search_by_name_tag_and_prefix(session_with_models):
    # pdf_merge [pdf, merge]; pdf_split [pdf, split]; image_crop [image, crop]; private_pdf [pdf] (private)
    assert names(search_models(s, ["pdf"], 0, 50)) == ["pdf_merge", "pdf_split"]
    assert names(search_models(s, ["crop"], 0, 50)) == ["image_crop"]
    assert names(search_models(s, ["pdf", "spl"], 0, 50)) == ["pdf_split"]   # last word by prefix
    assert names(search_models(s, ["mer", "pdf"], 0, 50)) == ["pdf_merge"]   # name substring

def test_search_escapes_like_wildcards(session_with_models):
    assert search_models(s, ["%"], 0, 50) == [] and search_models(s, ["_"], 0, 50) == []

def test_search_within_category(session_with_models): ...  # filter by "home" and by "home/kitchen"

def test_upload_ignores_line_one(): # create_tool on code whose line 1 is "# a, b" stores no tags anywhere
def test_copy_json_tags_runs_once(tmp_path): ...  # file db with a tool row whose tags JSON is ["box","lid","demo"] and name "demo"
    # -> modeltag has box, lid; a second call inserts 0
```

- [ ] **Step 2: Run tests to verify they fail.** `ARGS="tests/test_tags.py tests/test_tag_migration.py"`. Expected: FAIL.

- [ ] **Step 3: Implement.** Escape `\`, `%`, `_` with `\` and use `ilike(..., escape="\\")`. `copy_json_tags` must run while the `tool.tags` column still exists in old databases and do nothing in fresh ones (column absent: return 0).

- [ ] **Step 4: Run the whole suite** (`ARGS=` empty). Expected: all PASS; fix tests that built `Tool(tags=...)`.

- [ ] **Step 5: Commit** "Search on ModelTag; tags are no longer read from line 1"

### Task 5: Upload, update, edit and suggestion routes

**Files:**
- Modify: `server/src/app/routes/upload.py` (upload parses metadata first, stores model + metadata in one commit; update leaves metadata alone unless fields are present)
- Create: `server/src/app/routes/metadata.py` (`POST /manage/model/{id}/metadata`, `GET /manage/model/{id}/metadata/edit`, `GET /tags/suggest`)
- Modify: `server/src/app/app.py` (include the router)
- Modify: `server/src/app/webapp/templates/components/upload_tool_item.html` (a form: file, both editors, `[upload]` button)
- Test: `server/tests/test_metadata_routes.py`

**Interfaces:**
- Consumes: Task 2 `parse_all`, `save_all`, `form_lists`, `MetadataError`, `suggest`; Task 3 `Categories`.
- Produces:
  - `POST /manage/model/upload`: multipart `file` + metadata fields; 400 with the `MetadataError` text on bad metadata before any build
  - `POST /manage/model/{id}/metadata`: owner or admin; form of editor fields; returns the rendered display partials (htmx swap target `#model-meta`)
  - `GET /manage/model/{id}/metadata/edit`: owner or admin; returns both editors with `[save]` `[cancel]`
  - `GET /tags/suggest?q=`: `<option value="tag">tag · n</option>` lines

- [ ] **Step 1: Write the failing tests** (reuse `logged_in`, `BuildingRunner`, `built` from `tests/test_upload_models.py`)

```python
def test_upload_stores_metadata(monkeypatch, logged_in):
    r = upload(..., data={"tags.present": "1", "tags": ["Box", "lid"], "categories.present": "1", "categories": ["home/storage"]})
    assert r.status_code == 200
    # load_all(...)[id] == {"tags": ["box", "lid"], "categories": ["home/storage"]}

def test_bad_metadata_rejects_upload_before_building(monkeypatch, logged_in):
    # categories=["home/cooking"] -> 400 mentioning "unknown"; runner.run never called; no Tool row

def test_update_without_metadata_keeps_it(monkeypatch, logged_in): ...
def test_edit_metadata_owner_admin_other(monkeypatch, logged_in, ...): ...  # 200, 200, 404
def test_cleared_categories_fall_back_to_misc_page(monkeypatch, logged_in):
    # set categories [] via edit -> GET /c/misc lists the model (needs Task 7; mark xfail until then, remove the mark in Task 7)
def test_suggest_route(logged_in): ...
```

- [ ] **Step 2: Run tests to verify they fail.** `ARGS=tests/test_metadata_routes.py`. Expected: FAIL (404s, missing fields).

- [ ] **Step 3: Implement the routes and the upload form.** Ownership check copies the update route's (`db_tool.user_id != user.id` and not admin -> 404). The upload form posts with `hx-post`, `hx-encoding="multipart/form-data"`, and on success sends `refresh` to `#tool-rows` as today.

- [ ] **Step 4: Run tests to verify they pass** (the misc page test stays xfail). Then the whole suite.

- [ ] **Step 5: Commit** "Upload and edit model metadata; tag suggestions"

### Task 6: Model page shows and edits metadata

**Files:**
- Modify: `server/src/app/routes/tools.py:237-288` (`entrypoint_page` loads `load_all` for the model; passes `can_edit`)
- Modify: `server/src/app/webapp/templates/pages/tool.html` (a `#model-meta` block: display partials, `[edit]` for owner/admin fetching the edit route)
- Test: `server/tests/test_metadata_routes.py`

**Interfaces:**
- Consumes: Task 5 edit routes; Task 2/3 display partials.

- [ ] **Step 1: Write the failing tests:** the model page shows `Home › Kitchen` linking to `/c/home/kitchen` and tag links; owner sees `[edit]`, a visitor does not; a model with no categories shows `Miscellaneous`; links carry `root_path` (assert with the `/catalog` prefix as `test_root_path.py` does).
- [ ] **Step 2: Run to verify fail.** Expected: FAIL.
- [ ] **Step 3: Implement.**
- [ ] **Step 4: Run the suite.** Expected: PASS.
- [ ] **Step 5: Commit** "Model page: categories, tags and the owner's editor"

### Task 7: Browsing by category

**Files:**
- Create: `server/src/app/routes/browse.py` (`GET /c/{category}`, `GET /c/{category}/{sub}`)
- Create: `server/src/app/webapp/templates/pages/category.html`, `components/category_bar.html`
- Modify: `server/src/app/routes/tools.py` (`read_root` passes the bar data; `get_tools` reads an optional `category` form field and passes it to `search_models`)
- Modify: `server/src/app/webapp/templates/pages/index.html` (include the bar), `components/tool_scroll_loader.html` (carry `category` in `hx-vals`), `server/src/app/utility/render.py` (`list_items` gains `category: Optional[str] = None`)
- Modify: `server/src/app/app.py` (include the router)
- Test: `server/tests/test_browse.py`

**Interfaces:**
- Consumes: Task 1 tree, `find`, `paths_under`; Task 3 `model_ids_in`; Task 4 `search_models(..., category=)`.
- Produces: `category_counts(session) -> dict[str, int]` in `routes/browse.py` (public models per leaf path and per top-level slug, a model counted once per category it is filed under, unfiled ones under `misc`).

- [ ] **Step 1: Write the failing tests**

```python
def test_category_pages(client_with_models):
    # a: home/kitchen + workshop/storage-extra; b: home/bathroom; c: private, home/kitchen; d: none
    assert listed("/c/home") == {"a", "b"} and listed("/c/home/kitchen") == {"a"}
    assert listed("/c/workshop/tool-storage") == {"a"} and listed("/c/misc") == {"d"}
    assert client.get("/c/nope").status_code == 404 and client.get("/c/home/nope").status_code == 404
    assert client.get("/c/misc/x").status_code == 404

def test_category_page_has_breadcrumb_and_description(): ...
def test_counts_ignore_private_models(): ...   # category_counts()["home/kitchen"] == 1
def test_index_shows_the_bar_in_yaml_order(): ...
def test_search_inside_category(): ...  # POST /models with search + category
```

Remove the xfail mark from `test_cleared_categories_fall_back_to_misc_page`.

- [ ] **Step 2: Run to verify fail.** `ARGS=tests/test_browse.py`. Expected: FAIL.
- [ ] **Step 3: Implement.** Category pages reuse the index's search box and infinite list with `category` set; the breadcrumb is `Home › Kitchen` with links; description from the YAML.
- [ ] **Step 4: Run the suite.** Expected: PASS, including the formerly xfail test.
- [ ] **Step 5: Commit** "Browse by category"

### Task 8: Manifest for the repo's models and the admin command

**Files:**
- Create: `models/catalog.yaml` (127 entries: tags from each file's current line 1, categories per the spec tree)
- Modify: every `models/*.py` (delete line 1 and the blank line after it when line 1 is a `#` tag comment)
- Create: `server/src/app/admin_cli.py`; Modify: `server/pyproject.toml` (`catalog-admin = "app.admin_cli:main"`)
- Test: `server/tests/test_manifest.py`, `server/tests/test_admin_cli.py`

**Interfaces:**
- Consumes: Task 2 `Tags().parse`, Task 3 `Categories().parse` (validation reuses the kinds' parsers), `save_all`.
- Produces: `catalog-admin apply-manifest <file> [--apply] [--owner <user_id>]` (default owner 49600918). Dry run prints one line per model whose tags or categories would change; `--apply` first writes `<MODELS_DIR>/../backups/metadata-<UTC timestamp>.json` with the previous values, then saves.

- [ ] **Step 1: Generate `models/catalog.yaml`** with a scratch script (not committed): tags = line-1 words, lowercased, through `tags.normalise`; categories from the spec's tree table (models listed per subcategory in the brainstorm: every one of the 127 gets exactly one primary; add extras only where the brainstorm named two homes, e.g. `pegboard_bin: [workshop/tool-storage, home/storage]`). Strip the line-1 comments in the same script, LF endings.

- [ ] **Step 2: Write the failing tests**

```python
def test_manifest_matches_models_and_tree():
    manifest = yaml.safe_load((REPO / "models/catalog.yaml").read_text())
    files = {p.stem for p in (REPO / "models").glob("*.py")}
    assert set(manifest) == files
    for name, entry in manifest.items():
        Tags().parse({"tags.present": ["1"], "tags": entry["tags"]})
        Categories().parse({"categories.present": ["1"], "categories": entry["categories"]})
        assert not (REPO / "models" / f"{name}.py").read_text().startswith("# ")

def test_apply_manifest_dry_run_then_apply(tmp_path, session_with_models): ...  # prints changes, saves nothing; then saves + backup file
def test_apply_manifest_refuses_duplicate_names(...): ...  # two owner models named "box" -> exit code 1, nothing saved
def test_apply_manifest_reports_missing_models(...): ...  # manifest entry with no stored model is listed, not an error
```

`REPO` = `Path(__file__).parents[2]`; the test is skipped when `models/` is absent (the server-only test tarball): add `models/` to the tar in the test command for this task.

- [ ] **Step 3: Run to verify fail.** Expected: FAIL.
- [ ] **Step 4: Implement `admin_cli.py`** (argparse; uses `Session(engine)`; matches by `Tool.name` and `Tool.user_id == owner`).
- [ ] **Step 5: Run the suite.** Expected: PASS.
- [ ] **Step 6: Commit** "Manifest of the repo models' metadata; catalog-admin apply-manifest"

### Task 9: Release and backfill

- [ ] **Step 1:** Bump `server/pyproject.toml` to `0.5.0`; open the PR `feat/model-metadata` -> `main`; wait for CI (`gh pr checks --watch`); squash-merge after the user approves.
- [ ] **Step 2:** Tag `v0.5.0` on main and push the tag; wait for the publish run; `catalog-update.timer` restarts the app within ~5 minutes (check `/catalog/healthz` returns ready).
- [ ] **Step 3:** In the app container (as the scoop update was run: `podman exec --user podman ... catalog sh -c 'set -a; . /run/secrets/catalog.env; set +a; /venvs/server/bin/catalog-admin apply-manifest /tmp/catalog.yaml'`) run the dry run and show the user the summary; then `--apply`.
- [ ] **Step 4: Live checks:** every `/catalog/c/<category>` and leaf page lists the manifest's count of public models; `/catalog/c/misc` lists none of the 127; `/catalog/model/45` shows `Home › Kitchen`; an upload through the form with tags and a category stores both (upload a throwaway private model, check, delete it after verifying its id by title).
