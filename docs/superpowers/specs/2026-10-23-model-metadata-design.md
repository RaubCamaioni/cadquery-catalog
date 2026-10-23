# Model metadata: categories and tags

Date: 2026-10-23
Status: for review

## Goal

Visitors browse the catalog by a two-level category tree (Home › Kitchen, Workshop › Tool Storage, …)
as well as by search. A model's tags and categories are metadata the catalog keeps beside the script,
set in the upload form and edited on the model page; the script itself carries none. The metadata
layer is built so that later kinds (parameter variations, printer profiles, licences, …) can be added
without changing the existing ones or the model table.

## Decisions (agreed in conversation)

- The category tree is curated: one YAML file in the repo defines it, and uploaders pick from it.
- Two levels: category › subcategory. A model is filed under subcategories only, except
  **Miscellaneous**, a top-level category with no subcategories that is itself selectable.
- A model has 0 to 3 categories, the first being its primary. A model with none is shown under
  Miscellaneous, and so is a model whose categories all disappear from the YAML.
- Tags are free-form, but the form suggests existing tags with their counts so authors reuse them.
- Metadata is never read from the script. Line 1 of a file is no longer parsed for tags; old tag
  comments in stored scripts stay as harmless comments.
- Categories and tags are set in the upload form and edited from the model page (owner or admin).
  Replacing a model's code keeps its metadata unless the form changes it.
- PyTools is out of scope; it keeps its line-1 tags.

## The category tree

`server/src/app/categories.yaml`, shipped inside the app package. Changing the tree is a pull request
and a release. A slug is a permanent id (stored in the database); names and descriptions may change
freely.

```yaml
# Catalog categories, two levels. A slug is a permanent id stored with every model filed under it;
# names and descriptions can change freely. Removing a slug moves its models to Miscellaneous.
- slug: home
  name: Home
  description: Things for around the house.
  subcategories:
    - slug: kitchen
      name: Kitchen
      description: Cooking, baking, food storage and serving.
    # ...
- slug: misc
  name: Miscellaneous
  description: Models that do not fit another category yet.
```

The initial tree (6 categories, 23 subcategories, plus Miscellaneous):

| Category | Subcategories |
|---|---|
| Home `home` | Kitchen `kitchen`, Bathroom `bathroom`, Bedroom & Personal `bedroom`, Decor `decor`, Storage `storage`, Wall & Hanging `wall`, Fixtures `fixtures` |
| Office & Desk `office` | Desk Organizers `desk`, Stands & Risers `stands`, Cable Management `cables` |
| Workshop `workshop` | Tool Storage `tool-storage`, Shop Aids `shop-aids`, 3D Printing `printing` |
| Hardware & Electronics `hardware` | Fasteners & Spacers `fasteners`, Brackets & Mounts `mounts`, Mechanisms `mechanisms`, Electronics `electronics` |
| Outdoor & Garage `outdoor` | Garden `garden`, Garage & Vehicle `garage` |
| Hobbies `hobbies` | Games `games`, Crafts `crafts`, Science `science` |
| Miscellaneous `misc` | (none: selectable itself) |

A filed category is referenced by its path: `home/kitchen`, or `misc` for Miscellaneous.

`app/categories.py` loads the YAML once at import and checks it; a bad file stops the app from
starting instead of serving a broken tree:

- slugs match `^[a-z][a-z0-9-]*$`, unique among siblings, every path unique;
- every top-level entry has `name` and `description`; it either has at least one subcategory or is
  `misc`, which must exist and has none;
- subcategories have no subcategories of their own.

It exposes the tree for templates (ordered as in the file), `is_leaf(path)`, `label(path)`
("Home › Kitchen") and `paths_under(slug)` (all leaf paths under a top-level category).

## Metadata layer

### Shape

A package `app/metadata/` with one module per kind and a small registry:

```python
class MetadataKind(Protocol):
    key: str                      # "tags", "categories"; also the form field prefix
    def parse(self, form: FormData) -> Optional[Value]: ...   # None: the form did not touch this kind
    def save(self, session: Session, model_id: int, value: Value) -> None: ...
    def load(self, session: Session, model_ids: list[int]) -> dict[int, Value]: ...
    editor_template: str          # partial for the upload form and the edit dialog
    display_template: str         # partial for the model page

KINDS: list[MetadataKind] = [Tags(), Categories()]
```

- `metadata.apply(session, model_id, form)` runs every kind's `parse` and `save`. The upload, update
  and edit routes call only this, so adding a kind does not touch them.
- `parse` raises `MetadataError(message)`, which the routes turn into a 400 with that message. Every
  kind is parsed before any is saved, so a bad field stores nothing.
- A kind whose fields are absent from the form returns `None` and keeps the stored value, which is how
  a code update keeps its metadata. Each editor partial includes a hidden `<key>.present` field, so an
  editor that was shown and emptied is told apart from one that was not shown.
- `load` is batched by model id so list pages make one query per kind, not one per model.
- Each kind owns its own table(s). The model (`Tool`) table gains no columns for metadata, so a later
  kind (a `ModelVariation` table with a name and a parameter JSON per row, a printer-profile table, …)
  is a new module, a new table created by `create_all`, and a line in `KINDS`.

### Tags

- Table `ModelTag(model_id, tag)`, primary key on both, index on `tag`.
- Form fields: repeated `tags` values. Normalised: lowercased, trimmed, inner whitespace to `-`; must
  match `^[a-z0-9][a-z0-9.+-]{0,29}$`; duplicates dropped; at most 10. The profanity filter checks
  them, as it does code.
- Suggestions: `GET /tags/suggest?q=kit` returns up to 10 existing tags on public models that start
  with `q`, most used first, with counts. An empty `q` returns the most used tags.
- The model name is searched directly (`Tool.name`), so it is no longer appended to the tags.

### Categories

- Table `ModelCategory(model_id, path, position)`, primary key `(model_id, path)`, index on `path`.
  `position` 0 is the primary.
- Form fields: repeated `categories` values in order, each a leaf path from the YAML. At most 3,
  duplicates rejected, unknown paths rejected with the list of valid ones.
- `misc` stands alone: a list containing `misc` and another path is rejected (filing a model somewhere
  real takes it out of Miscellaneous).
- Effective categories: the stored paths still present in the YAML, in order; if none remain, `misc`.
  Only the effective list is shown or browsed, so a slug removed from the YAML never hides a model.

### Retiring `Tool.tags`

On first start of the new version, a one-time step copies each model's JSON `tags` (minus the model
name, which was appended automatically) into `ModelTag`, if `ModelTag` is empty. The JSON column is
then unused; it is left in place (SQLite cannot drop a column cheaply on older versions) and the
`Tool.tags` field is removed from the model class. Search moves from `Tool.tags.ilike` to a join on
`ModelTag`.

## Routes and pages

### Upload and update

The `[upload]` row on the profile becomes a short form: the file, the tags editor and the categories
editor, and an `[upload]` button, posting to `POST /manage/model/upload`. The update row keeps its
one-click file picker (`POST /manage/model/update/{id}`), which sends no metadata fields and therefore
keeps the model's tags and categories.

The upload route order: check login and ban, read the file, parse metadata (400 on a bad field),
build the model in the sandbox (400 on failure), then store the model and its metadata in one
transaction.

### Editing metadata

- `POST /manage/model/{id}/metadata`: owner or admin only (404 otherwise, as with updates); body is
  the editors' fields; runs `metadata.apply`.
- On the model page the owner (or an admin) sees `[edit]` beside the tags and categories. It opens the
  same editors in place (htmx swap) with `[save]` and `[cancel]`.

### Editors

Plain HTML plus a little hyperscript, matching the site:

- Tags: a text input with a `<datalist>` filled from `/tags/suggest` as the user types; Enter or
  comma turns the text into a chip; `×` removes a chip. Each chip is a hidden `tags` input.
- Categories: a text input with a `<datalist>` of every leaf label ("Home › Kitchen"), filtered by
  the browser as the user types; choosing one adds a chip (hidden `categories` input holding the path).
  Chips can be removed and moved left or right; the first is marked primary. Adding a fourth is
  refused in the page; the server enforces the limit as well.

### Browsing

- The front page gets a category bar under the search box: the top-level names, each opening its
  subcategories. Counts are shown beside names.
- `GET /c/{category}` lists public models filed under any of its subcategories (or under `misc`);
  `GET /c/{category}/{subcategory}` lists that leaf. Unknown slugs return 404. Each page has a
  breadcrumb, the YAML description, and the existing infinite-scroll model list; the search box on a
  category page searches within it.
- A model appears on every category page it is filed under. Its model page shows the primary as a
  breadcrumb and the others as links, and its tags as links to a search for that tag.

### Search

Each typed word must match the model name (substring, case-insensitive) or one of its tags
(exact, or prefix for the last word as the user is still typing). Words are combined with AND, as
today. On a category page the category filter is applied as well.

## Existing models and bulk uploads

- `models/catalog.yaml` in the repo maps every model file to its tags and categories:

  ```yaml
  measuring_scoop:
    tags: [scoop, measuring, kitchen, spoon, volume, ml, oz]
    categories: [home/kitchen]
  ```

  The first version is generated from the files' current line-1 tags plus the agreed tree; the
  category assignments are reviewed in the pull request that adds it. The same PR removes the line-1
  tag comments from the files in `models/`.
- A test checks the manifest: every file in `models/` has an entry and every entry has a file, tags
  pass the tag rules, categories are leaf paths in `categories.yaml`.
- An admin command in the app image, `catalog-admin apply-manifest <file> [--apply]`, sets tags and
  categories on the stored models owned by the owner account, matching by model name. Without
  `--apply` it prints what would change. It writes a JSON backup of the previous metadata first. It
  is run inside the app container after the release, the same way the measuring-scoop update was run.
- For future bulk uploads, the existing GitHub-raw upload script sends the manifest's tags and
  categories as form fields with each file.

## Errors

- Bad metadata field: 400 with the field's message; nothing is stored, including the model.
- Unknown category or subcategory page: 404.
- Metadata edit by anyone but the owner or an admin: 404, as for code updates.
- Invalid `categories.yaml`: the app does not start (logged); CI catches it first through the tests.

## Testing

Unit (server venv, `-m "not integration"`):

- `categories.py`: the shipped YAML loads; each rule rejects a crafted bad tree; `label`, `is_leaf`,
  `paths_under`.
- Tags: normalisation, limits, character rules, profanity; suggestions order and prefix match on
  public models only.
- Categories: valid lists, more than 3, duplicates, unknown path, a top-level path that is not `misc`;
  effective categories falling back to `misc`.
- `metadata.apply`: absent fields keep stored values; an emptied editor clears them; one bad kind
  stores nothing.
- Routes: upload with metadata; update without metadata keeps it; metadata edit by owner, by admin,
  by another user (404); category pages list the right models including extras; unknown slugs 404;
  search by name, by tag, within a category.
- Migration: JSON tags copied into `ModelTag` once, name removed, idempotent on a second start.
- Manifest: matches `models/` and the YAML.

Live, after the release and `apply-manifest --apply`: every category page shows the expected count,
no public model sits in Miscellaneous unless the manifest put it there, and an upload through the
form stores its tags and categories.

## Out of scope

- PyTools metadata.
- Uploader-created categories and an admin UI for the tree (the YAML is the editor).
- Any specific later metadata kind (variations, printer profiles); the layer only leaves room for them.
