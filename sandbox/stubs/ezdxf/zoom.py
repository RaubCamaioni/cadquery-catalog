def __getattr__(name):
    if name.startswith("__"):
        raise AttributeError(name)
    raise RuntimeError("ezdxf is not available in this sandbox (build-time stub)")
