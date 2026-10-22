# CadQuery Catalog: design

Date: 2026-10-22
Status: for review

## Goal

A catalogue of parametric 3D models written as CadQuery scripts, in the spirit of Thingiverse or
TurboSquid but where every model is code: a visitor opens a model, changes its parameters, sees
the result regenerate in a 3D view, and downloads it as STL or STEP. Anyone with a GitHub login
can publish a model, exactly as on PyTools.

Served at `https://raubcamaioni.com/catalog/`. Repository `RaubCamaioni/cadquery-catalog`,
site name "CadQuery Catalog".

## Starting point

A copy of PyTools at v0.3.2: FastAPI + SQLModel, htmx + hyperscript, the monochrome terminal
theme, GitHub login, votes, reports, admin and bans, the black-formatted upload path, the
podman-in-podman sandbox runner with the execution trace, root-path support, and the release
flow (tags publish, pushes only build). The generic converter tools and their docs are removed.
The package stays `app`; images become `cadquery-catalog` (the app) and
`cadquery-catalog-sandbox` (the runtime).

## Model contract

A model is one Python file. It follows the PyTools upload rules (tags on line 1, entrypoint
named after the file, typed parameters `int`, `float`, `str`, `Literal`, black at 120 columns),
with two differences:

- `Path` parameters are not allowed: a model is generated from numbers and choices only.
- The entrypoint returns a CadQuery object (`cq.Workplane`, `cq.Shape` or `cq.Assembly`)
  instead of a path. It does not export anything itself.

```python
# box, container, lid

import cadquery as cq


def storage_box(width: float = 80, depth: float = 60, height: float = 40, wall: float = 2.4) -> cq.Workplane:
    """An open box with rounded vertical edges."""
    return cq.Workplane("XY").box(width, depth, height).edges("|Z").fillet(wall).faces(">Z").shell(-wall)
```

Every numeric parameter must carry a default, so the model can be built unattended.

## Runtime (the sandbox side)

The sandbox runner for the catalogue imports the file, calls the entrypoint with the submitted
parameters, and from the returned object writes into the run directory:

- `model.stl` (for the viewer and download) and `model.step` (download)
- `preview.svg`: CadQuery's SVG projection, a monochrome line drawing that fits the site's look
  and needs no GPU or display
- `meta.json`: bounding box (x, y, z in mm), volume, surface area, solid count

An entrypoint that returns anything else, or raises, fails the run with the reason shown on
the page. Limits are the PyTools ones (no network, 0.5 CPU, 1 GB, 30 s) with one run at a time.

## Validation at upload

Uploading runs the model once with its defaults, in the sandbox, before it is stored. The
upload is rejected if that run fails. Its `preview.svg` and `meta.json` are kept as the
model's thumbnail and card data, so the gallery never has to run anything. Re-uploading a model
re-validates and replaces the thumbnail.

## Pages

- **Gallery (`/`)**: a grid of thumbnails with name, author alias and tags; search filters as
  you type by name and tags, as on PyTools. Sorted by votes, then recency.
- **Model page (`/model/{id}`)**: the 3D viewer large, with the parameter tree beside it
  (the PyTools argument form minus file inputs), `[regenerate]` under the parameters,
  dimensions and volume from `meta.json`, `[stl]` `[step]` download links for the current
  parameters, votes and report, and the source in the vim-style code view below. A share link
  carries the parameters in the query string.
- **Regeneration**: `[regenerate]` posts the parameters; the response replaces the viewer, the
  downloads and the dimensions in place (htmx). The execution trace drives the progress bar
  and cursor as on PyTools.
- **Profile, admin, policies**: unchanged from PyTools apart from wording.

## Data

The PyTools schema with `Tool` renamed `Model`, plus `preview_svg` (text) and `meta` (JSON) on
the model, written by the validation run. Run outputs live in the run directory for ten minutes
as on PyTools.

## Deployment

A second app container on the same server, `cadquery-catalog`, from its own image, listening
on `172.18.0.1:8081`, with its own data directory, secrets file, inner image store and GitHub
OAuth app (callback `https://raubcamaioni.com/catalog/auth/github`). nginx gets a
`location /catalog/` block like the `/tools/` one and the landing page a line.

Resource budget on the current 2 vCPU / 3.9 GB server: the catalogue container is capped at
1.5 GB with `SANDBOX_MAX_CONCURRENT=1`, and the PyTools cap is lowered from 3 GB to 2 GB. The
inner image store of PyTools has grown to 25 GB because old sandbox images are never pruned;
pruning after each refresh goes into PyTools first and is inherited by the catalogue.

## Out of scope for the first version

3MF, DXF and GLTF exports; parameter ranges and units beyond type and default; assemblies
with colours in the viewer (an assembly exports as one STL/STEP); print-bed checks; comments.

## Risks

- Memory: two nested-podman app containers plus a 1 GB sandbox on a 3.9 GB host. The caps
  above fit, with little headroom; a larger Linode plan is the fallback.
- CadQuery import time (~2 s) is paid on every run; acceptable at 30 s limits.
- STEP export of a complex model can take several seconds; it runs in the same sandbox call.
