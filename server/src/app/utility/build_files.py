"""A build's files, read from the run directory without trusting the run.

Model code runs in the same sandbox process as the runner, so it can write its own result.json
naming any host path (`/proc/self/environ`, the database) as its STL or preview. sandboxcore turns
every returned path into an OutputFile only if it is a regular file inside the run directory reached
without symlinks; on top of that the catalog takes each export only under its fixed name, caps its
size, and accepts only the numeric shape of the measurements.
"""

import math
from sandboxcore.host import OutputFile, RunFileError

FILES = {"stl": "model.stl", "step": "model.step", "preview": "preview.svg"}
MAX_BYTES = {"stl": 64 * 1024 * 1024, "step": 64 * 1024 * 1024, "preview": 4 * 1024 * 1024}
META_NUMBERS = ("volume_mm3", "area_mm2")


class BuildFileError(ValueError):
    pass


def read_build_file(out, limit: int) -> bytes:
    """The bytes of a vetted export file holding at most `limit` bytes."""
    if not isinstance(out, OutputFile):
        raise BuildFileError("the build is missing a file")
    try:
        return out.read(limit)
    except RunFileError as e:
        raise BuildFileError(str(e)) from None


def checked_build(results) -> dict:
    """The export dict of a run: each file the vetted OutputFile under its fixed name (and readable within
    its size cap), and the measurements checked against their schema. BuildFileError when anything is
    out of shape."""
    if not isinstance(results, dict):
        raise BuildFileError("the build returned no model")
    files = {}
    for key, name in FILES.items():
        out = results.get(key)
        if not isinstance(out, OutputFile) or out.name != name:
            raise BuildFileError(f"{name} is missing or not a plain file")
        read_build_file(out, MAX_BYTES[key])
        files[key] = out
    return {**files, "meta": checked_meta(results.get("meta"))}


def checked_meta(meta) -> dict:
    """The measurements (size_mm, volume_mm3, area_mm2, solids) as plain numbers, nothing else."""
    if not isinstance(meta, dict) or set(meta) != {"size_mm", *META_NUMBERS, "solids"}:
        raise BuildFileError("the build's measurements are malformed")
    size = meta["size_mm"]
    if not isinstance(size, list) or len(size) != 3 or not all(_finite(v) for v in size):
        raise BuildFileError("the build's measurements are malformed")
    if not all(_finite(meta[k]) for k in META_NUMBERS):
        raise BuildFileError("the build's measurements are malformed")
    solids = meta["solids"]
    if type(solids) is not int or solids < 0:
        raise BuildFileError("the build's measurements are malformed")
    return {"size_mm": list(size), **{k: meta[k] for k in META_NUMBERS}, "solids": solids}


def _finite(value) -> bool:
    # bool is an int subclass: exclude it
    return type(value) in (int, float) and math.isfinite(value)
