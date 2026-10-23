"""A build's files, read from the run directory without trusting the run.

Model code runs in the same sandbox process as the runner, so it can write its own result.json
naming any host path (`/proc/self/environ`, the database) as its STL or preview, and the host
would then copy that file into the catalog. The host therefore ignores every path in result.json:
it opens the three fixed names in the run directory, refuses symlinks and anything that is not a
regular file, caps the size, and accepts only the numeric shape of the measurements.
"""

import math
import os
import stat
from pathlib import Path

FILES = {"stl": "model.stl", "step": "model.step", "preview": "preview.svg"}
MAX_BYTES = {"stl": 64 * 1024 * 1024, "step": 64 * 1024 * 1024, "preview": 4 * 1024 * 1024}
META_NUMBERS = ("volume_mm3", "area_mm2")


class BuildFileError(ValueError):
    pass


def read_build_file(path: Path, limit: int) -> bytes:
    """The bytes of a regular file that is not a symlink and holds at most `limit` bytes."""
    try:
        # O_NONBLOCK: a FIFO the model left behind must not block the event loop on open
        fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    except OSError:
        raise BuildFileError(f"{path.name} is missing or not a plain file") from None
    try:
        info = os.fstat(fd)
        if not stat.S_ISREG(info.st_mode):
            raise BuildFileError(f"{path.name} is not a plain file")
        if info.st_size > limit:
            raise BuildFileError(f"{path.name} is larger than {limit // (1024 * 1024)} MB")
        with os.fdopen(fd, "rb", closefd=False) as f:
            data = f.read(limit + 1)
        if len(data) > limit:
            raise BuildFileError(f"{path.name} is larger than {limit // (1024 * 1024)} MB")
        return data
    finally:
        os.close(fd)


def checked_build(run_dir: Path, results) -> dict:
    """The export dict for a run: the fixed file names in `run_dir` (each checked) and the measurements
    checked against their schema. BuildFileError when anything is out of shape."""
    if not isinstance(results, dict):
        raise BuildFileError("the build returned no model")
    files = {}
    for key, name in FILES.items():
        path = run_dir / name
        read_build_file(path, MAX_BYTES[key])
        files[key] = path
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
