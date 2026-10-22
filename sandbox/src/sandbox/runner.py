from sandbox import serializer
from sandbox.export import export_model
from sandbox.trace import LineTracer, open_trace

from typing import Any, Callable
from functools import partial
from pathlib import Path
import importlib
import importlib.util
import traceback
import time
import sys
import os

# warm mode: the container starts before any job exists, imports what SANDBOX_PRELOAD names (the
# slow part, e.g. cadquery), writes READY_FILE, then waits for the host to drop the job into the
# work directory and write GO_FILE (containing the tool file name). One job, then exit.
PRELOAD_ENV = "SANDBOX_PRELOAD"
READY_FILE = "ready"
GO_FILE = "go"
WAIT_POLL_SECONDS = 0.05


def runner(file: Path, workdir: Path, trace: str | None = None) -> Any:
    os.chdir(workdir)

    # optional line trace: 4-byte line numbers of the tool file to a FIFO the host reads
    tracer = None
    if trace is not None:
        fd = open_trace(trace)
        if fd is not None:
            tracer = LineTracer(file, fd)
            tracer.start()
    try:
        _run(file)
    finally:
        if tracer is not None:
            tracer.stop()
            os.close(tracer.fd)


def preload() -> None:
    """Import the modules named in SANDBOX_PRELOAD (comma separated) so a job does not pay for them."""
    for name in filter(None, (n.strip() for n in os.environ.get(PRELOAD_ENV, "").split(","))):
        try:
            importlib.import_module(name)
        except Exception as e:  # a bad preload must not take the sandbox down; the job imports itself
            print(f"preload of {name} failed: {type(e).__name__}: {e}", file=sys.stderr)


def wait_for_job(workdir: Path, ttl_seconds: float) -> Path | None:
    """Block until the host writes GO_FILE into the work directory; None when the ttl passes first."""
    go = workdir / GO_FILE
    deadline = time.monotonic() + ttl_seconds
    while time.monotonic() < deadline:
        if go.exists():
            name = go.read_text(encoding="utf-8").strip()
            return workdir / name
        time.sleep(WAIT_POLL_SECONDS)
    return None


def _run(file: Path) -> None:

    with open("args.json", "r") as f:
        args = serializer.load(f)

    module_name = file.stem
    spec = importlib.util.spec_from_file_location(module_name, file)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    if not hasattr(module, module_name):
        raise ValueError(f"no function named: {module_name}")

    func: Callable[[Any], Any] = getattr(module, module_name, None)

    failed = False
    try:
        results = partial(func, **args)()
    except Exception as e:
        failed = True
        _, _, exc_traceback = sys.exc_info()
        frames = traceback.extract_tb(exc_traceback)

        trace = []
        for frame in frames:
            trace.append(f"  {frame.name}: {frame.lineno}")
        trace = "\n".join(trace)
        results = f"Runtime Error: {file.stem} {type(e).__name__}\n{trace}"

        print(results)

    # a model returns a CadQuery object; the files the site serves are made from it here. Anything
    # else it returns (a string included) is reported by the export step, not passed off as a result
    if not failed:
        try:
            results = export_model(results)
        except Exception as e:
            results = f"Export Error: {type(e).__name__}: {e}"
            print(results)

    with open("result.json", "w") as f:
        serializer.dump(results, f)


def main():
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("--file", "-f", type=str, help="the tool file (not needed with --wait)")
    parser.add_argument("--workdir", "-w", type=str, required=True)
    # the host passes the trace FIFO in the environment; the flag exists for local use
    parser.add_argument("--trace", "-t", type=str, default=os.environ.get("PYWEBTOOLS_TRACE"))
    parser.add_argument(
        "--wait", type=float, default=None, help="warm mode: preload, then wait this many seconds for a job"
    )
    args = parser.parse_args()

    workdir = Path(args.workdir)
    if args.wait is not None:
        preload()
        (workdir / READY_FILE).write_text("", encoding="utf-8")
        file = wait_for_job(workdir, args.wait)
        if file is None:
            return  # idle for the whole ttl: exit quietly, the host starts a fresh one
    else:
        if not args.file:
            parser.error("--file is required without --wait")
        file = Path(args.file)

    # the trace FIFO may not exist until the job does; only use it if the host created one
    trace = args.trace if args.trace and os.path.exists(args.trace) else None
    runner(file, workdir, trace)


if __name__ == "__main__":
    main()
