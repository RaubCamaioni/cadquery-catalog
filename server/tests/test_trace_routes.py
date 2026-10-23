from app.routes import tools as tools_routes
from app.utility.podman_runner import Outcome, RunResult, SandboxBusy

from tests.test_tool_routes import BUILD, StubRunner, client, public_tool  # noqa: F401  (fixture)

TOKEN = "a" * 32


def events(body: str) -> list[str]:
    return [block for block in body.strip().split("\n\n") if block]


def test_trace_stream_emits_lines_then_end(monkeypatch, public_tool):
    class Runner(StubRunner):
        async def run(self, tool, run_dir, on_line=None):
            on_line(1)
            on_line(2)
            return await super().run(tool, run_dir)

    c = client(monkeypatch, Runner())
    assert c.post("/model/8", headers={"X-Trace-Token": TOKEN}).status_code == 200
    # the channel outlives the run briefly, so a stream attached afterwards still gets every event
    assert events(c.get("/trace/" + TOKEN).text) == ["event: line\ndata: 1", "event: line\ndata: 2", "event: end\ndata:"]


def test_channel_closed_on_busy(monkeypatch, public_tool):
    c = client(monkeypatch, StubRunner(raise_=SandboxBusy()))
    assert c.post("/model/8", headers={"X-Trace-Token": "b" * 32}).status_code == 503
    assert events(c.get("/trace/" + "b" * 32).text) == ["event: end\ndata:"]


def test_channel_closed_when_tool_missing(monkeypatch, public_tool):
    monkeypatch.setattr(tools_routes.db_tools, "get_tool_by_id", lambda session, id: None)
    c = client(monkeypatch, StubRunner())
    assert c.post("/model/8", headers={"X-Trace-Token": "e" * 32}).status_code == 404
    assert events(c.get("/trace/" + "e" * 32).text) == ["event: end\ndata:"]


def test_unknown_token_ends_after_wait(monkeypatch):
    monkeypatch.setattr(tools_routes, "TRACE_WAIT_SECONDS", 0.05)
    r = client(monkeypatch, StubRunner()).get("/trace/" + "c" * 32)
    assert r.headers["content-type"].startswith("text/event-stream")
    assert events(r.text) == ["event: end\ndata:"]


def test_malformed_token_is_404(monkeypatch):
    assert client(monkeypatch, StubRunner()).get("/trace/short").status_code == 404
    assert client(monkeypatch, StubRunner()).get("/trace/" + "." * 32).status_code == 404


def test_token_reuse_replaces_channel():
    reg = tools_routes.TRACES
    a = reg.register("d" * 32)
    b = reg.register("d" * 32)
    assert a.closed and not b.closed


def test_bad_token_is_ignored(monkeypatch, public_tool):
    stub = StubRunner(RunResult(Outcome.OK, results=BUILD))
    assert client(monkeypatch, stub).post("/model/8", data={"trace": "../x"}).status_code == 200
    assert stub.on_line is None  # no channel, no trace


def test_good_token_gives_runner_a_callback(monkeypatch, public_tool):
    stub = StubRunner(RunResult(Outcome.OK, results=BUILD))
    client(monkeypatch, stub).post("/model/8", headers={"X-Trace-Token": "f" * 32})
    assert stub.on_line is not None


def test_second_stream_after_end_finishes_promptly(monkeypatch, public_tool):
    import threading

    monkeypatch.setattr(tools_routes, "TRACE_IDLE_SECONDS", 0.05)
    c = client(monkeypatch, StubRunner(RunResult(Outcome.OK, results=BUILD)))
    assert c.post("/model/8", headers={"X-Trace-Token": "g" * 32}).status_code == 200
    assert events(c.get("/trace/" + "g" * 32).text)[-1] == "event: end\ndata:"
    out = {}
    t = threading.Thread(target=lambda: out.setdefault("body", c.get("/trace/" + "g" * 32).text), daemon=True)
    t.start()
    t.join(2)
    assert not t.is_alive() and events(out["body"]) == ["event: end\ndata:"]  # a finished channel ends every later stream


def test_token_travels_in_a_header_not_the_form(monkeypatch, public_tool):
    stub = StubRunner(RunResult(Outcome.OK, results=BUILD))
    c = client(monkeypatch, stub)
    assert c.post("/model/8", headers={"X-Trace-Token": "h" * 32}).status_code == 200 and stub.on_line is not None
    stub.on_line = None
    assert c.post("/model/8", data={"trace": "h" * 32}).status_code == 200 and stub.on_line is None


def test_tool_argument_named_trace_keeps_the_users_value(monkeypatch, tmp_path):
    import dataclasses
    import json

    monkeypatch.setattr(
        tools_routes.db_tools,
        "get_tool_by_id",
        lambda session, id: tools_routes.db_tools.Tool(
            id=9, name="t", code="def t(trace: str): return trace", arguments={"trace": ("str", "")}, public=True, tags=[]
        ),
    )
    env = tools_routes.ENVIRONMENT
    monkeypatch.setattr(tools_routes, "ENVIRONMENT", dataclasses.replace(env, sandbox=dataclasses.replace(env.sandbox, run_dir=tmp_path)))
    class ArgsRunner(StubRunner):  # the run directory is removed once the request ends: read args during the run
        async def run(self, tool, run_dir, on_line=None):
            self.args = json.loads((run_dir / "args.json").read_text())
            return await super().run(tool, run_dir, on_line)

    stub = ArgsRunner(RunResult(Outcome.OK, results=BUILD))
    c = client(monkeypatch, stub)
    assert c.post("/model/9", data={"trace": "yes please"}, headers={"X-Trace-Token": "i" * 32}).status_code == 200
    assert stub.args["trace"] == "yes please" and stub.on_line is not None


def test_unknown_form_fields_are_ignored(monkeypatch, public_tool):
    stub = StubRunner(RunResult(Outcome.OK, results=BUILD))
    assert client(monkeypatch, stub).post("/model/8", data={"bogus": "1"}).status_code == 200
