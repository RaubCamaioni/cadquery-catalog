"""Warm mode of the sandbox runtime: preload, announce readiness, wait for one job."""

import json
import os
import subprocess
import sys
import threading
import time

import pytest

if sys.version_info < (3, 12):  # the line tracer needs sys.monitoring, as the sandbox image's Python has
    pytest.skip("sandbox runtime needs Python 3.12", allow_module_level=True)

from sandbox import runner as sandbox_runner  # noqa: E402


def test_wait_for_job_returns_the_named_file_when_go_appears(tmp_path):
    def hand_over():
        time.sleep(0.2)
        (tmp_path / "go").write_text("tool.py")

    threading.Thread(target=hand_over).start()
    assert sandbox_runner.wait_for_job(tmp_path, ttl_seconds=5) == tmp_path / "tool.py"


def test_wait_for_job_gives_up_after_the_ttl(tmp_path):
    assert sandbox_runner.wait_for_job(tmp_path, ttl_seconds=0.2) is None


def test_preload_imports_named_modules_and_survives_bad_ones(monkeypatch, capsys):
    monkeypatch.setenv(sandbox_runner.PRELOAD_ENV, "json, no_such_module_xyz")
    sandbox_runner.preload()
    assert "preload of no_such_module_xyz failed" in capsys.readouterr().err


def test_wait_mode_end_to_end_runs_one_job_then_exits(tmp_path):
    (tmp_path / "args.json").write_text(json.dumps({"n": 2}))
    proc = subprocess.Popen(
        [sys.executable, "-m", "sandbox.runner", "--wait", "10", "--workdir", str(tmp_path)],
        env={**os.environ, sandbox_runner.PRELOAD_ENV: "json"},
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    try:
        for _ in range(100):
            if (tmp_path / "ready").exists():
                break
            time.sleep(0.05)
        assert (tmp_path / "ready").exists(), proc.stderr.read().decode()
        (tmp_path / "double.py").write_text("def double(n: int = 1):\n    return 'not a model'\n")
        (tmp_path / "go").write_text("double.py")
        proc.wait(timeout=30)
        assert proc.returncode == 0, proc.stderr.read().decode()
        # a string result is the runtime's own report (here: the entrypoint returned no model)
        result = json.loads((tmp_path / "result.json").read_text())
        assert isinstance(result, str) and result.startswith("Export Error")
    finally:
        if proc.poll() is None:
            proc.kill()
