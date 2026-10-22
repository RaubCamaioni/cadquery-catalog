"""Run uploaded tools in per-run rootless podman containers.

Design: docs/superpowers/specs/2026-10-19-podman-sandbox-runner-design.md
"""

import asyncio
import logging
import os
import secrets
import shutil
import stat
import string
import time
from contextlib import suppress
from dataclasses import dataclass
from enum import Enum, auto
from pathlib import Path
from typing import Any, Awaitable, Callable, Optional

from app.utility import serializer
from app.utility.sandbox_config import SandboxConfig
from app.utility.trace import read_trace

logger = logging.getLogger("uvicorn.error")

# (argv..., timeout=None) -> (returncode, stdout, stderr); the podman binary is argv[0]
Exec = Callable[..., Awaitable[tuple[int, str, str]]]

STDERR_TAIL_LINES = 20
# captured output is a ring buffer: a tool that floods stdout/stderr cannot grow the app's memory
OUTPUT_CAP_BYTES = 64 * 1024
# result.json is written by untrusted code: only a modest regular file is accepted
RESULT_MAX_BYTES = 16 * 1024 * 1024
# podman kills a timed-out container; a late exit within this margin still counts as the timeout
TIMEOUT_TOLERANCE = 0.5
# the app gives `podman run --timeout` this much extra before killing the container itself
SAFETY_NET_SECONDS = 2.0
# every other podman call gets a timeout so a stalled podman can never pin a sandbox slot
PODMAN_CALL_TIMEOUT = 15.0
PULL_TIMEOUT = 600.0
READINESS_SECONDS = 60
PULL_RETRY_SECONDS = 60
REFRESH_SECONDS = 600
# startup self-test: a run that must be OOM-killed and a run that must be killed by --timeout
SELFTEST_MEMORY = "64m"
SELFTEST_MEMORY_CODE = "bytearray(200*1024*1024)"
SELFTEST_TIMEOUT = 2
SELFTEST_TIMEOUT_CODE = "import time; time.sleep(30)"
KILLED_EXIT_CODES = (137, 143)
# how podman reports a container killed by its own --timeout: `podman run` exits 255, inspect shows -1
TIMEOUT_RUN_EXIT_CODE = 255
TIMEOUT_INSPECT_EXIT_CODE = -1
# uid of the `app` user created in containers/Containerfile.sandbox
SANDBOX_UID = 1001
# the FIFO in the run directory that carries the sandbox's executed line numbers
TRACE_NAME = "trace"
TRACE_ENV = "PYWEBTOOLS_TRACE"
TRACE_DRAIN_SECONDS = 1.0
STARTING = "starting"
# warm pool: containers started ahead of a job (see sandbox/runner.py `--wait`)
WARM_PREFIX = "warm-"
READY_FILE = "ready"  # the sandbox writes it once its preload is done
GO_FILE = "go"  # the app writes it (the tool file name) to hand the job over
PRELOAD_ENV = "SANDBOX_PRELOAD"
WARM_CHECK_SECONDS = 1.0
WARM_SWEEP_SECONDS = 60.0  # how often stray warm-* containers (unknown to the pool) are removed
RUN_DIR_NAME_LENGTH = 32
RUN_DIR_CHARS = string.ascii_letters + string.digits + "-_"


class SandboxBusy(Exception):
    """No sandbox slot became free within the queue wait."""


class SandboxUnavailable(Exception):
    """The sandbox failed its startup checks; tool runs are refused."""


async def _read_tail(stream: asyncio.StreamReader) -> bytes:
    tail = bytearray()
    while True:
        chunk = await stream.read(OUTPUT_CAP_BYTES)
        if not chunk:
            return bytes(tail)
        tail += chunk
        if len(tail) > OUTPUT_CAP_BYTES:
            del tail[: len(tail) - OUTPUT_CAP_BYTES]


async def run_podman(*argv: str, timeout: Optional[float] = None, capture: bool = True) -> tuple[int, str, str]:
    """Run podman and return (rc, stdout, stderr). `capture=False` discards the output: a detached
    `podman run -d` hands its pipes to the container monitor, so reading them to EOF would wait
    for the container itself to exit.
    """
    if not capture:
        devnull = asyncio.subprocess.DEVNULL
        proc = await asyncio.create_subprocess_exec(*argv, stdin=devnull, stdout=devnull, stderr=devnull)
        try:
            await asyncio.wait_for(proc.wait(), timeout)
        except asyncio.TimeoutError:
            proc.kill()
            await proc.wait()
            raise
        return proc.returncode, "", ""
    proc = await asyncio.create_subprocess_exec(*argv, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)

    async def finish():
        out, err = await asyncio.gather(_read_tail(proc.stdout), _read_tail(proc.stderr))
        await proc.wait()
        return out, err

    try:
        out, err = await asyncio.wait_for(finish(), timeout)
    except asyncio.TimeoutError:
        proc.kill()
        await proc.wait()
        raise
    return proc.returncode, out.decode(errors="replace"), err.decode(errors="replace")


class Outcome(Enum):
    OK = auto()
    TIMEOUT = auto()
    OOM = auto()
    CRASHED = auto()


@dataclass
class RunResult:
    outcome: Outcome
    results: Any = None  # deserialized result.json when outcome is OK
    message: Optional[str] = None  # user-facing text for every other outcome
    stderr_tail: str = ""


_INVALID = object()  # result.json exists but cannot be trusted


class PodmanRunner:
    def __init__(
        self,
        config: SandboxConfig,
        exec: Optional[Exec] = None,
        sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
    ):
        self.config = config
        self._exec: Exec = exec or run_podman
        self._sleep = sleep
        self._slots = asyncio.Semaphore(config.max_concurrent)
        self._unavailable_reason: Optional[str] = STARTING
        self._tasks: list[asyncio.Task] = []
        self._warm: dict[Path, _Warm] = {}  # run directory -> its waiting container
        self._last_request = float("-inf")  # the pool is only kept while runs are being requested
        self._last_sweep = time.monotonic()  # first sweep after WARM_SWEEP_SECONDS

    @property
    def available(self) -> bool:
        return self._unavailable_reason is None

    @property
    def unavailable_reason(self) -> Optional[str]:
        return self._unavailable_reason

    def mark_unavailable(self, reason: str):
        logger.error(f"sandbox unavailable: {reason}")
        self._unavailable_reason = reason

    def mark_available(self):
        self._unavailable_reason = None

    # --- startup -----------------------------------------------------------------

    def start_in_background(self):
        """Serve pages right away; the sandbox reports 'starting' until start() finishes."""
        self._tasks.append(asyncio.create_task(self.start(), name="sandbox-start"))

    async def start(self):
        """Readiness, leftover cleanup, image pull and the fail-closed self-test. Never raises."""
        try:
            if not await self._wait_ready():
                self.mark_unavailable("inner podman not ready")
            else:
                await self._remove_leftovers()
                await self._prepare()
        except Exception as e:
            logger.exception("sandbox startup failed")
            self.mark_unavailable(f"startup failed: {e}")
        self._tasks.append(asyncio.create_task(self._refresh_loop()))
        if not self.available:
            self._tasks.append(asyncio.create_task(self._retry_loop()))
        if self.config.warm_pool > 0:
            self._tasks.append(asyncio.create_task(self._warm_loop(), name="sandbox-warm"))

    async def stop(self):
        for task in self._tasks:
            task.cancel()
        await asyncio.gather(*self._tasks, return_exceptions=True)
        self._tasks.clear()
        for warm in list(self._warm.values()):
            await self._recycle(warm)

    async def self_test(self) -> Optional[str]:
        """Return why limits are not enforced, or None when both checks pass."""
        rc = await self._selftest_run(
            {"--memory": SELFTEST_MEMORY, "--memory-swap": SELFTEST_MEMORY}, SELFTEST_MEMORY_CODE
        )
        if rc not in KILLED_EXIT_CODES:
            return "memory limit not enforced"
        rc = await self._selftest_run({"--timeout": str(SELFTEST_TIMEOUT)}, SELFTEST_TIMEOUT_CODE)
        if rc not in (*KILLED_EXIT_CODES, TIMEOUT_RUN_EXIT_CODE):
            return "timeout not enforced"
        return None

    async def _selftest_run(self, overrides: dict[str, str], code: str) -> int:
        flags = []
        for flag in self._limit_flags():
            key = flag.split("=")[0]
            flags.append(f"{key}={overrides[key]}" if key in overrides else flag)
        argv = ["podman", "run", "--rm", *flags, "--entrypoint", "python3", self.config.image, "-c", code]
        rc, _, _ = await self._exec(*argv, timeout=SELFTEST_TIMEOUT + 30)
        return rc

    async def _wait_ready(self) -> bool:
        for _ in range(READINESS_SECONDS):
            try:
                rc, _, _ = await self._exec("podman", "info", timeout=PODMAN_CALL_TIMEOUT)
            except FileNotFoundError:
                logger.error("podman binary not found; sandbox disabled")
                return False
            except (OSError, asyncio.TimeoutError) as e:
                logger.warning(f"podman info failed: {e}")
                rc = 1
            if rc == 0:
                return True
            await self._sleep(1)
        return False

    async def _remove_leftovers(self):
        rc, out, _ = await self._exec(
            "podman", "ps", "-a", "--filter", "name=^(run|warm)-", "--format", "{{.Names}}", timeout=PODMAN_CALL_TIMEOUT
        )
        if rc != 0:
            return
        for name in out.split():
            logger.warning(f"removing leftover sandbox container {name}")
            await self._exec("podman", "rm", "-f", name, timeout=PODMAN_CALL_TIMEOUT)

    async def _prepare(self):
        if not await self._ensure_image():
            return
        reason = await self.self_test()
        if reason:
            self.mark_unavailable(reason)
        else:
            self.mark_available()
            logger.info("sandbox self-test passed; sandbox ready")

    async def _ensure_image(self) -> bool:
        image = self.config.image
        rc, _, err = await self._exec("podman", "pull", image, timeout=PULL_TIMEOUT)
        if rc == 0:
            return True
        rc, _, _ = await self._exec("podman", "image", "exists", image, timeout=PODMAN_CALL_TIMEOUT)
        if rc == 0:
            logger.warning(f"pull of {image} failed ({err.strip()}); using the local copy")
            return True
        self.mark_unavailable(f"sandbox image unavailable: {err.strip()}")
        return False

    async def _retry_loop(self):
        while not self.available:
            await self._sleep(PULL_RETRY_SECONDS)
            try:
                await self._prepare()
            except Exception as e:
                logger.warning(f"sandbox retry failed: {e}")

    async def _refresh_loop(self):
        # sandbox-only releases are picked up without an app restart: new runs use the new local image
        while True:
            await self._sleep(REFRESH_SECONDS)
            try:
                rc, _, err = await self._exec("podman", "pull", self.config.image, timeout=PULL_TIMEOUT)
                if rc != 0:
                    logger.warning(f"sandbox image refresh failed: {err.strip()}")
                else:
                    # idle warm containers still run the old image: replace them
                    for warm in [w for w in self._warm.values() if not w.taken]:
                        await self._recycle(warm)
            except Exception as e:
                logger.warning(f"sandbox image refresh raised: {e}")

    # --- one run -----------------------------------------------------------------

    @staticmethod
    def container_name(run_dir: Path) -> str:
        # the fixed prefix keeps the name valid even when the directory name starts with - or _
        return f"run-{run_dir.name}"

    def _limit_flags(self) -> list[str]:
        cfg = self.config
        return [
            "--network=none",
            "--uts=host",
            # the image's unprivileged user; maps to a sub-UID of the inner podman user, never to the app user.
            # (--userns=auto would force a re-owned copy of the 2.6 GB image per mapping on fuse-overlayfs)
            f"--user={SANDBOX_UID}",
            f"--cpus={cfg.cpus}",
            f"--memory={cfg.memory}",
            f"--memory-swap={cfg.memory}",
            f"--pids-limit={cfg.pids}",
            "--read-only",
            "--tmpfs=/tmp:rw,size=64m",
            "--cap-drop=ALL",
            "--security-opt=no-new-privileges",
            # the container log lives in the inner image store; a chatty tool must not fill it
            "--log-opt=max-size=1mb",
            f"--timeout={int(cfg.timeout_seconds)}",
        ]

    def command(self, name: str, tool: Path, run_dir: Path, trace: Optional[Path] = None) -> list[str]:
        flags = self._limit_flags()
        # keep the "--tmpfs <spec>" form the tests and operators expect
        i = flags.index("--tmpfs=/tmp:rw,size=64m")
        flags[i : i + 1] = ["--tmpfs", "/tmp:rw,size=64m"]
        # the run directory keeps its own path inside the sandbox: args.json carries absolute upload
        # paths and result.json carries absolute output paths that the app serves afterwards
        return [
            "podman",
            "run",
            "--name",
            name,
            *flags,
            "-v",
            f"{run_dir}:{run_dir}:U",
            # the trace FIFO travels as an environment variable: a sandbox image that predates the
            # trace ignores it (no events, page falls back), where an unknown flag would fail the run
            *(["-e", f"{TRACE_ENV}={trace}"] if trace is not None else []),
            self.config.image,
            "--file",
            str(run_dir / tool.name),
            "--workdir",
            str(run_dir),
        ]

    async def run(self, tool: Path, run_dir: Path, on_line: Optional[Callable[[int], None]] = None) -> RunResult:
        """Run `tool`; with `on_line`, forward the sandbox's executed line numbers as they happen."""
        if not self.available:
            raise SandboxUnavailable(self._unavailable_reason)
        try:
            await asyncio.wait_for(self._slots.acquire(), self.config.queue_seconds)
        except asyncio.TimeoutError:
            raise SandboxBusy()
        try:
            if run_dir in self._warm:
                return await self._supervise_warm(tool, run_dir, on_line)
            return await self._supervise(tool, run_dir, on_line)
        finally:
            self._slots.release()

    async def _supervise(self, tool: Path, run_dir: Path, on_line: Optional[Callable[[int], None]]) -> RunResult:
        name = self.container_name(run_dir)
        timed_out = False
        stderr = ""
        exit_code: Optional[int] = None
        oom_killed = False
        trace = _open_trace(run_dir) if on_line is not None else None
        reader = None
        if trace is not None:
            reader = asyncio.create_task(read_trace(trace.rfd, _line_count(tool), on_line))
        started = time.monotonic()
        try:
            try:
                _, _, stderr = await self._exec(
                    *self.command(name, tool, run_dir, trace=trace.path if trace is not None else None),
                    timeout=self.config.timeout_seconds + SAFETY_NET_SECONDS,
                )
            except asyncio.TimeoutError:
                timed_out = True
                logger.warning(f"{name}: podman --timeout did not fire, killing container")
                await self._podman("kill", name)
            except Exception as e:
                logger.exception(f"{name}: podman run failed")
                stderr = f"{type(e).__name__}: {e}"
            exit_code, oom_killed = await self._inspect(name)
            if not stderr:
                rc, out, err = await self._podman("logs", "--tail", str(STDERR_TAIL_LINES), name)
                if rc == 0:
                    stderr = err or out  # output of a killed run only survives in the container log
        finally:
            elapsed = time.monotonic() - started
            # the sandbox owned its files; hand them back to the app user before anything reads or deletes them
            await self._podman("rm", "-f", name)
            await self._podman("unshare", "chown", "-R", "0:0", str(run_dir))
            if trace is not None:
                await trace.finish(reader)
        return self.classify(run_dir, exit_code, oom_killed, elapsed, stderr, timed_out)

    async def _podman(self, *args: str) -> tuple[int, str, str]:
        """A bounded, never-raising podman call for the post-run bookkeeping."""
        try:
            rc, out, err = await self._exec("podman", *args, timeout=PODMAN_CALL_TIMEOUT)
            if rc != 0:
                logger.warning(f"podman {' '.join(args)} failed: {err.strip()}")
            return rc, out, err
        except Exception as e:  # bookkeeping must never mask the run's result
            logger.warning(f"podman {' '.join(args)} raised: {e}")
            return 1, "", str(e)

    async def _inspect(self, name: str) -> tuple[Optional[int], bool]:
        rc, out, _ = await self._podman("inspect", "--format", "{{.State.ExitCode}} {{.State.OOMKilled}}", name)
        try:
            if rc != 0:
                raise ValueError(out)
            exit_code, oom = out.split()
            return int(exit_code), oom == "true"
        except ValueError:
            logger.warning(f"{name}: could not inspect container state")
            return None, False

    # --- warm pool -----------------------------------------------------------------
    # A warm container is `podman run -d ... <image> --wait <ttl>`: it preloads the slow imports,
    # writes READY_FILE into its run directory and waits for GO_FILE. new_run_dir() hands that
    # directory to the request, which writes the tool and args into it as usual; run() then drops
    # GO_FILE and waits for the container to exit. One job per container, so isolation is unchanged;
    # only the import time moves ahead of the request.

    def make_run_dir(self) -> Path:
        """A fresh, secret, world-writable run directory under the configured root."""
        root = self.config.run_dir
        root.mkdir(parents=True, exist_ok=True)
        run_dir = root / "".join(secrets.choice(RUN_DIR_CHARS) for _ in range(RUN_DIR_NAME_LENGTH))
        os.mkdir(run_dir)
        os.chmod(run_dir, stat.S_IRWXU | stat.S_IRWXG | stat.S_IRWXO)
        return run_dir

    def new_run_dir(self) -> Path:
        """The run directory for a request: a warm container's, else a fresh one. A container still
        preloading is handed out too: the sandbox looks for the job only once its imports are done,
        so the job starts the moment they are, always sooner than a cold start would.
        """
        self._last_request = time.monotonic()
        idle = [w for w in self._warm.values() if not w.taken]
        if idle:
            ready = [w for w in idle if (w.run_dir / READY_FILE).exists()]
            warm = min(ready or idle, key=lambda w: w.created)
            warm.taken = True
            return warm.run_dir
        return self.make_run_dir()

    def warm_command(self, name: str, run_dir: Path) -> list[str]:
        flags = self._limit_flags()
        # the container may idle for the whole ttl before its job starts
        i = flags.index(f"--timeout={int(self.config.timeout_seconds)}")
        flags[i] = f"--timeout={int(self.config.warm_ttl_seconds + self.config.timeout_seconds + SAFETY_NET_SECONDS)}"
        i = flags.index("--tmpfs=/tmp:rw,size=64m")
        flags[i : i + 1] = ["--tmpfs", "/tmp:rw,size=64m"]
        return [
            "podman",
            "run",
            "-d",
            "--name",
            name,
            *flags,
            "-v",
            f"{run_dir}:{run_dir}:U",
            "-e",
            f"{TRACE_ENV}={run_dir / TRACE_NAME}",
            "-e",
            f"{PRELOAD_ENV}={self.config.preload}",
            self.config.image,
            "--wait",
            str(self.config.warm_ttl_seconds),
            "--workdir",
            str(run_dir),
        ]

    async def _warm_loop(self):
        while True:
            try:
                await self._tend_warm()
            except Exception as e:
                logger.warning(f"warm pool: {e}")
            await self._sleep(WARM_CHECK_SECONDS)

    async def _tend_warm(self):
        """Retire idle containers past their ttl and, while the site is in use, keep `warm_pool` of them
        waiting. In use means a run was requested within the ttl: an idle site runs no containers at
        all, the first request after a quiet spell pays the cold start, the ones after it do not.
        """
        if not self.available:
            return
        now = time.monotonic()
        for warm in list(self._warm.values()):
            if not warm.taken and now - warm.created >= self.config.warm_ttl_seconds:
                await self._recycle(warm)
        idle = sum(1 for w in self._warm.values() if not w.taken)
        in_use = now - self._last_request < self.config.warm_ttl_seconds
        for _ in range(self.config.warm_pool - idle if in_use else 0):
            await self._start_warm()
        if now - self._last_sweep >= WARM_SWEEP_SECONDS:
            self._last_sweep = now
            await self._sweep_strays()

    async def _sweep_strays(self):
        """Remove warm-* containers the pool does not know (a start reported failed, an app restart)."""
        rc, out, _ = await self._podman("ps", "-a", "--filter", f"name=^{WARM_PREFIX}", "--format", "{{.Names}}")
        if rc != 0:
            return
        known = {w.name for w in self._warm.values()}
        for name in out.split():
            if name not in known:
                logger.warning(f"removing stray warm container {name}")
                await self._podman("rm", "-f", name)

    async def _start_warm(self):
        run_dir = self.make_run_dir()
        name = WARM_PREFIX + run_dir.name
        try:
            rc, _, err = await self._exec(*self.warm_command(name, run_dir), timeout=PODMAN_CALL_TIMEOUT, capture=False)
        except Exception as e:
            rc, err = 1, f"{type(e).__name__}: {e}"
        if rc != 0:
            logger.warning(f"warm container failed to start: {err.strip()}")
            await self._podman("rm", "-f", name)
            shutil.rmtree(run_dir, ignore_errors=True)
            return
        self._warm[run_dir] = _Warm(name=name, run_dir=run_dir, created=time.monotonic())

    async def _recycle(self, warm: "_Warm"):
        """Drop a warm container that was never used (ttl, image refresh, shutdown)."""
        self._warm.pop(warm.run_dir, None)
        await self._podman("rm", "-f", warm.name)
        await self._podman("unshare", "chown", "-R", "0:0", str(warm.run_dir))
        shutil.rmtree(warm.run_dir, ignore_errors=True)

    async def _supervise_warm(self, tool: Path, run_dir: Path, on_line: Optional[Callable[[int], None]]) -> RunResult:
        warm = self._warm.pop(run_dir)
        name = warm.name
        timed_out = False
        stderr = ""
        exit_code: Optional[int] = None
        oom_killed = False
        trace = _open_trace(run_dir) if on_line is not None else None
        reader = None
        if trace is not None:
            reader = asyncio.create_task(read_trace(trace.rfd, _line_count(tool), on_line))
        started = time.monotonic()
        try:
            # hand the job over: the sandbox polls for GO_FILE, written atomically
            go = run_dir / GO_FILE
            go.with_suffix(".tmp").write_text(tool.name, encoding="utf-8")
            os.replace(go.with_suffix(".tmp"), go)
            try:
                rc, out, err = await self._exec(
                    "podman", "wait", name, timeout=self.config.timeout_seconds + SAFETY_NET_SECONDS
                )
                if rc != 0:
                    stderr = err
            except asyncio.TimeoutError:
                timed_out = True
                logger.warning(f"{name}: job exceeded the limit, killing container")
                await self._podman("kill", name)
            except Exception as e:
                logger.exception(f"{name}: podman wait failed")
                stderr = f"{type(e).__name__}: {e}"
            exit_code, oom_killed = await self._inspect(name)
            if not stderr:
                rc, out, err = await self._podman("logs", "--tail", str(STDERR_TAIL_LINES), name)
                if rc == 0:
                    stderr = err or out
        finally:
            elapsed = time.monotonic() - started
            await self._podman("rm", "-f", name)
            await self._podman("unshare", "chown", "-R", "0:0", str(run_dir))
            if trace is not None:
                await trace.finish(reader)
            for leftover in (GO_FILE, READY_FILE):
                with suppress(OSError):
                    (run_dir / leftover).unlink()
        return self.classify(run_dir, exit_code, oom_killed, elapsed, stderr, timed_out)

    # --- outcome -----------------------------------------------------------------

    def classify(
        self,
        run_dir: Path,
        exit_code: Optional[int],
        oom_killed: bool,
        elapsed: float,
        stderr: str,
        timed_out: bool = False,
    ) -> RunResult:
        cfg = self.config
        tail = "\n".join(stderr.splitlines()[-STDERR_TAIL_LINES:])

        if _dir_size(run_dir) > cfg.max_output_mb * 1024 * 1024:
            _empty_dir(run_dir)
            return RunResult(
                Outcome.CRASHED, message=f"Tool output exceeded the {cfg.max_output_mb} MB limit", stderr_tail=tail
            )

        results = _read_results(run_dir / "result.json")
        if results is not _INVALID and results is not None:
            return RunResult(Outcome.OK, results=results[0], stderr_tail=tail)

        if oom_killed:
            return RunResult(
                Outcome.OOM, message=f"Tool exceeded the {cfg.memory_label} memory limit", stderr_tail=tail
            )
        if timed_out or exit_code == TIMEOUT_INSPECT_EXIT_CODE or elapsed >= cfg.timeout_seconds - TIMEOUT_TOLERANCE:
            return RunResult(
                Outcome.TIMEOUT, message=f"Tool exceeded the {cfg.timeout_seconds:g} second limit", stderr_tail=tail
            )
        return RunResult(Outcome.CRASHED, message="Tool failed to run", stderr_tail=tail)


@dataclass
class _Warm:
    name: str
    run_dir: Path
    created: float
    taken: bool = False  # handed to a request by new_run_dir(); run() consumes it


@dataclass
class _Trace:
    path: Path
    rfd: int
    wfd: int  # the app's own write end: without one the read end reports EOF before the sandbox connects

    async def finish(self, reader: Optional["asyncio.Task"]) -> None:
        os.close(self.wfd)  # the container is gone, so this close delivers EOF to the reader
        if reader is not None:
            try:
                await asyncio.wait_for(reader, TRACE_DRAIN_SECONDS)
            except (asyncio.TimeoutError, Exception):
                reader.cancel()
                with suppress(BaseException):
                    await reader
        os.close(self.rfd)


def _open_trace(run_dir: Path) -> Optional[_Trace]:
    """Create the trace FIFO and hold both ends open; None (run without a trace) on any failure."""
    path = run_dir / TRACE_NAME
    rfd = None
    try:
        os.mkfifo(path, 0o666)
        os.chmod(path, 0o666)  # the sandbox user must be able to open it for writing
        rfd = os.open(path, os.O_RDONLY | os.O_NONBLOCK)
        wfd = os.open(path, os.O_WRONLY | os.O_NONBLOCK)
        return _Trace(path, rfd, wfd)
    except OSError as e:
        logger.warning(f"trace FIFO unavailable for {run_dir.name}: {e}")
        if rfd is not None:
            os.close(rfd)
        return None


def _line_count(tool: Path) -> int:
    try:
        return tool.read_text(encoding="utf-8", errors="replace").count("\n") + 1
    except OSError:
        return 0


def _read_results(path: Path):
    """None when absent, _INVALID when present but untrusted, else a 1-tuple with the value."""
    try:
        fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
    except FileNotFoundError:
        return None
    except OSError as e:  # symlink (ELOOP), permissions, ...
        logger.warning(f"result.json rejected: {e}")
        return _INVALID
    try:
        st = os.fstat(fd)
        if not stat.S_ISREG(st.st_mode) or st.st_size > RESULT_MAX_BYTES:
            logger.warning("result.json rejected: not a regular file or too large")
            os.close(fd)
            return _INVALID
        with os.fdopen(fd, "r") as f:
            return (serializer.load(f),)
    except (OSError, ValueError) as e:
        logger.warning(f"result.json rejected: {e}")
        return _INVALID


def _dir_size(run_dir: Path) -> int:
    total = 0
    for root, _, files in os.walk(run_dir):
        for name in files:
            try:
                total += os.lstat(os.path.join(root, name)).st_size
            except OSError:
                pass
    return total


def _empty_dir(run_dir: Path):
    for child in run_dir.iterdir():
        try:
            if child.is_dir() and not child.is_symlink():
                shutil.rmtree(child)
            else:
                child.unlink()
        except OSError as e:
            logger.warning(f"could not remove {child}: {e}")
