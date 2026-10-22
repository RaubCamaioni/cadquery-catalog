"""Build-time stub for ezdxf.

CadQuery imports ezdxf for DXF import and export, which the catalogue does not offer; the
import cost a third of a second of every build. The names CadQuery touches at import time
exist here; using any of them raises.
"""

from . import units, zoom  # noqa: F401  (real submodules: `from ezdxf import units` must find them)


class _Missing:
    def __init__(self, *args, **kwargs):
        raise RuntimeError("ezdxf is not available in this sandbox (build-time stub)")


def __getattr__(name):
    if name.startswith("__"):
        raise AttributeError(name)
    return _Missing
