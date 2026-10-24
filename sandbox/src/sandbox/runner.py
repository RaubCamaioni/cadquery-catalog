"""The sandbox entrypoint: sandboxcore's Python runner with the catalogue's export step.

A model returns a CadQuery object; `export_model` turns it into the files the site serves. Anything
else it returns (a string included) is reported by the export step, not passed off as a result.
"""

from sandboxcore.python.runner import main as run_tool

from sandbox.export import export_model


def main():
    run_tool(finish=export_model, finish_label="Export Error")


if __name__ == "__main__":
    main()
