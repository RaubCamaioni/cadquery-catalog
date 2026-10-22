"""CadQuery reads `units.MM` as a class default at import time; any unit name is a plain value."""


def __getattr__(name):
    if name.startswith("__"):
        raise AttributeError(name)
    return 4  # ezdxf's code for millimetres
