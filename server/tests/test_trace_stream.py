"""The browser trace stream: one channel per run token, bounded, superseded by a newer stream."""

from app.utility.trace_stream import TraceChannel, TraceRegistry


def test_channel_queue_is_bounded():
    ch = TraceChannel()
    for n in range(1, 1500):
        ch.put(n)
    assert ch.queue.qsize() == 1000 and ch.queue.get_nowait() == 500


def test_channel_close_marks_end():
    ch = TraceChannel()
    ch.put(3)
    ch.close()
    assert ch.closed and ch.queue.get_nowait() == 3 and ch.queue.get_nowait() is None
    ch.put(4)  # ignored after close
    assert ch.queue.empty()


def test_registry_replaces_and_expires():
    reg = TraceRegistry()
    a = reg.register("tok")
    b = reg.register("tok")
    assert a.closed and reg.get("tok") is b
    reg.expire(now=b.created + 61)
    assert reg.get("tok") is None


def test_registry_close_and_expire_closed():
    reg = TraceRegistry()
    ch = reg.register("tok")
    reg.close("tok")
    assert ch.closed and reg.get("tok") is ch  # still readable by a late client for a while
    reg.expire(now=ch.created + 11)
    assert reg.get("tok") is None


def test_channel_attach_supersedes_earlier_stream():
    ch = TraceChannel()
    first = ch.attach()
    second = ch.attach()
    assert first != second and ch.ticket == second
