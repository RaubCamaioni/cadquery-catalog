# CadQuery Catalog

A catalogue of parametric 3D models written as [CadQuery](https://cadquery.readthedocs.io)
scripts. Open a model, change its parameters, watch it regenerate in the 3D view, and download
the result as STL or STEP. Anyone with a GitHub login can publish a model.

The public instance runs at **https://raubcamaioni.com/catalog/**.

The site is built on the same foundation as [PyTools](https://github.com/RaubCamaioni/PyTools):
a FastAPI and htmx application in a monochrome terminal theme, GitHub login, votes and
reports, and a podman-in-podman sandbox that runs each build in a fresh container with no
network, half a CPU, 1 GB of memory and a hard time limit. The design, and what differs from
PyTools, is in `docs/superpowers/specs/2026-10-22-cadquery-catalog-design.md`.

## Writing a model

A model is one Python file whose entrypoint function has the file's name, takes numbers and
choices, and returns a CadQuery object.

```python
# spacer, standoff, hardware

from typing import Literal
import cadquery as cq


def spacer(
    outer_diameter: float = 12,
    hole_diameter: float = 6.4,
    height: float = 10,
    profile: Literal["round", "hex"] = "round",
) -> cq.Workplane:
    """A round or hexagonal spacer with a through hole."""
    if profile == "hex":
        body = cq.Workplane("XY").polygon(6, outer_diameter).extrude(height)
    else:
        body = cq.Workplane("XY").circle(outer_diameter / 2).extrude(height)
    return body.faces(">Z").workplane().hole(hole_diameter)
```

Rules the upload enforces:

- Line 1 is a comment of comma-separated tags, used by search.
- Parameters are `int`, `float`, `str` or `Literal[...]`, every one with a default, or `Path`
  with a default of `None`: a file the visitor may upload (an image, an STL). When no file is
  given, and during the validation build at upload, the model receives `None` and must build a
  demo instead. Pillow is available for images.
- The entrypoint returns a `cq.Workplane`, `cq.Shape` or `cq.Assembly`. It does not export
  anything itself; the runtime writes the STL, the STEP, the thumbnail and the measurements.
- The file is reformatted with `black -l 120` and stored with a single trailing newline.
- The upload is built once with its defaults in the sandbox before it is stored. A model that
  fails to build, or returns something that is not a CadQuery object, is rejected with the
  reason. That build's thumbnail (an SVG line drawing), measurements, STL and STEP are what
  the gallery and the model page show until a visitor regenerates with other parameters.

Sample models are in `models/`.

## Repository layout

The sandbox core (podman runner, limits, outcomes, trace channel, run-directory helpers, the annotation
allow-list and the in-sandbox runner) is the shared package
[sandboxcore](https://github.com/RaubCamaioni/sandboxcore), also used by PyTools.
Both `server/pyproject.toml` and `sandbox/pyproject.toml` pin the same release tag; bump them together.

| Path | Contents |
|---|---|
| `server/` | The FastAPI application: routes, SQLModel database, templates, static assets, tests. |
| `sandbox/` | The runtime that builds one model inside its container: the sandboxcore runner (argument loading, line tracing) with the export of STL, STEP, SVG preview and measurements as its finish step. |
| `containers/` | `Containerfile.prod` (the app image) and `Containerfile.sandbox` (the runtime image with CadQuery). |
| `models/` | Sample models. |
| `docs/` | The design spec and the sandbox runner's design documents inherited from PyTools. |

## Running, developing, releasing

Identical to PyTools: see its README for the container run command, the environment variables
and the release flow. The differences are the names:

| | PyTools | CadQuery Catalog |
|---|---|---|
| Images | `pywebtools`, `pywebtools-sandbox` | `cadquery-catalog`, `cadquery-catalog-sandbox` |
| Secrets file in the container | `/run/secrets/pywebtools.env` | `/run/secrets/catalog.env` |
| Extra variable | | `MODELS_DIR`: where default STL/STEP builds are kept (default: beside the database) |
| Commit file | `/etc/pytools-commit` | `/etc/catalog-commit` |
| Import trim | | The sandbox image stubs VTK and ezdxf (`sandbox/stubs`, first on `PYTHONPATH`) and pins CadQuery's version lookup at build time: CadQuery only needs them for Jupyter display and DXF, and they cost about 1.5 s of every build. Nothing is kept running between builds. |

```bash
cd server && python -m venv .venv && .venv/bin/pip install -e ".[dev]"
.venv/bin/pytest -m "not integration"
cd ../sandbox && pip install -e . && pytest        # needs cadquery installed
```

A push or pull request builds both images; a `vX.Y.Z` tag matching `server/pyproject.toml`
publishes them and the server deploys. The "Run workflow" button publishes any branch on
demand.
