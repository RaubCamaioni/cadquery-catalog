"""Build-time stub for VTK.

CadQuery imports VTK (through OCP.IVtkOCC and vtkmodules) to render shapes in Jupyter; the
catalogue never does, yet that import cost about a second of every build. Any
`vtkmodules.<name>` import succeeds and yields a module whose attributes raise if used.
Installed by containers/Containerfile.sandbox at /venvs/stubs, first on PYTHONPATH.
"""

import importlib.abc
import importlib.machinery
import sys
import types


class _Missing:
    def __init__(self, *args, **kwargs):
        raise RuntimeError("VTK is not available in this sandbox (build-time stub)")


def _module_getattr(name):
    if name.startswith("__"):
        raise AttributeError(name)
    return _Missing


class _Finder(importlib.abc.MetaPathFinder, importlib.abc.Loader):
    def find_spec(self, fullname, path=None, target=None):
        if fullname.startswith("vtkmodules."):
            return importlib.machinery.ModuleSpec(fullname, self)
        return None

    def create_module(self, spec):
        module = types.ModuleType(spec.name)
        module.__getattr__ = _module_getattr
        return module

    def exec_module(self, module):
        pass


sys.meta_path.insert(0, _Finder())
