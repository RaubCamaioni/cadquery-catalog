"""The warm pool: containers started before a job, one job each (podman_runner warm section)."""

import asyncio
import json

from app.utility.podman_runner import GO_FILE, READY_FILE, Outcome, PodmanRunner

from tests.test_podman_run import FakePodman, cfg


def warm_runner(fake, tmp_path, **kw):
    runner = PodmanRunner(
        cfg(SANDBOX_RUN_DIR=tmp_path, SANDBOX_WARM_POOL=1, SANDBOX_PRELOAD="cadquery", **kw), exec=fake
    )
    runner.mark_available()
    return runner


async def test_tending_starts_one_warm_container_with_preload_and_long_timeout(tmp_path):
    fake = FakePodman()
    runner = warm_runner(fake, tmp_path, SANDBOX_TIMEOUT_SECONDS=30, SANDBOX_WARM_TTL_SECONDS=600)
    await runner._tend_warm()
    assert fake.subcommands() == ["run"]
    argv = fake.calls[0]
    assert argv[1:4] == ["run", "-d", "--name"] and argv[4].startswith("warm-")
    assert "--timeout=632" in argv and "-e" in argv and "SANDBOX_PRELOAD=cadquery" in argv
    assert argv[-4:-2] == ["--wait", "600.0"] and argv[-2] == "--workdir"
    run_dir = next(iter(runner._warm))
    assert run_dir.is_dir() and argv[-1] == str(run_dir)
    # a second tend does not start another one while the first is idle
    await runner._tend_warm()
    assert fake.subcommands() == ["run"]


async def test_new_run_dir_prefers_a_ready_warm_directory(tmp_path):
    fake = FakePodman()
    runner = warm_runner(fake, tmp_path)
    await runner._tend_warm()
    warm_dir = next(iter(runner._warm))
    # not ready yet (preload still running): the request gets a fresh directory
    fresh = runner.new_run_dir()
    assert fresh != warm_dir and fresh.is_dir()
    (warm_dir / READY_FILE).write_text("")
    assert runner.new_run_dir() == warm_dir
    # taken: handed out once only
    assert runner.new_run_dir() != warm_dir


async def test_warm_run_hands_the_job_over_and_waits_for_the_container(tmp_path):
    fake = FakePodman({"wait": (0, "0\n", ""), "inspect": (0, "0 false", "")})
    runner = warm_runner(fake, tmp_path)
    await runner._tend_warm()
    warm_dir = next(iter(runner._warm))
    (warm_dir / READY_FILE).write_text("")
    run_dir = runner.new_run_dir()
    assert run_dir == warm_dir
    (run_dir / "t.py").write_text("x")
    (run_dir / "result.json").write_text(json.dumps({"ok": True}))
    r = await runner.run(run_dir / "t.py", run_dir)
    assert r.outcome is Outcome.OK and r.results == {"ok": True}
    assert fake.subcommands() == ["run", "wait", "inspect", "logs", "rm", "unshare"]
    assert fake.calls[1][:3] == ["podman", "wait", warm_dir and fake.calls[0][4]]
    assert not (run_dir / GO_FILE).exists() and run_dir not in runner._warm


async def test_warm_job_over_the_limit_is_killed_and_a_timeout(tmp_path):
    class Hanging(FakePodman):
        async def __call__(self, *argv, timeout=None):
            if argv[1] == "wait":
                self.calls.append(list(argv))
                raise asyncio.TimeoutError
            return await super().__call__(*argv, timeout=timeout)

    fake = Hanging({"inspect": (0, "137 false", "")})
    runner = warm_runner(fake, tmp_path, SANDBOX_TIMEOUT_SECONDS=1)
    await runner._tend_warm()
    warm_dir = next(iter(runner._warm))
    (warm_dir / READY_FILE).write_text("")
    run_dir = runner.new_run_dir()
    (run_dir / "t.py").write_text("x")
    r = await runner.run(run_dir / "t.py", run_dir)
    assert r.outcome is Outcome.TIMEOUT
    assert fake.subcommands().count("kill") == 1 and fake.subcommands()[-1] == "unshare"


async def test_idle_warm_containers_are_retired_after_the_ttl_and_on_image_refresh(tmp_path, monkeypatch):
    fake = FakePodman()
    runner = warm_runner(fake, tmp_path, SANDBOX_WARM_TTL_SECONDS=10)
    await runner._tend_warm()
    first = next(iter(runner._warm.values()))
    first.created -= 11  # older than the ttl
    await runner._tend_warm()
    assert first.run_dir not in runner._warm and not first.run_dir.exists()
    assert ["rm", "-f", first.name] == fake.calls[-3][1:4] or any(
        c[1:4] == ["rm", "-f", first.name] for c in fake.calls
    )
    assert len(runner._warm) == 1  # replaced
    # a run directory already handed to a request is left alone
    second = next(iter(runner._warm.values()))
    second.created -= 11
    second.taken = True
    await runner._tend_warm()
    assert second.run_dir in runner._warm


async def test_cold_runs_still_work_beside_the_pool(tmp_path):
    fake = FakePodman({"inspect": (0, "0 false", "")})
    runner = warm_runner(fake, tmp_path)
    run_dir = runner.make_run_dir()
    (run_dir / "result.json").write_text(json.dumps([1]))
    r = await runner.run(run_dir / "t.py", run_dir)
    assert r.outcome is Outcome.OK and fake.subcommands() == ["run", "inspect", "logs", "rm", "unshare"]
    assert fake.calls[0][2] == "--name"  # not detached: the on-demand form
