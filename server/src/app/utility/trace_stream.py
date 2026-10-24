"""The execution trace's way to the browser: line numbers of a run, held for its server-sent-events stream.

sandboxcore reads and checks the line numbers (`Sandbox.run(..., on_line=channel.put)`); this module
hands them to the page that started the run, under the random token the page sent with it.
Design: docs/superpowers/specs/2026-10-19-execution-trace-design.md
"""

import asyncio
import time
from typing import Optional

QUEUE_SIZE = 1000
# an unstarted channel is forgotten after this long; a finished one shortly after its end marker
UNSTARTED_TTL = 60.0
CLOSED_TTL = 10.0


class TraceChannel:
    """Line numbers of one run, consumed by one server-sent-events stream. `None` marks the end."""

    def __init__(self):
        self.queue: asyncio.Queue = asyncio.Queue(maxsize=QUEUE_SIZE)
        self.closed = False
        self.created = time.monotonic()
        self.closed_at: Optional[float] = None
        self.ticket = 0  # the stream holding the latest ticket is the only one served

    def attach(self) -> int:
        self.ticket += 1
        return self.ticket

    def _put(self, item):
        if self.queue.full():
            self.queue.get_nowait()  # drop the oldest: a late browser only needs recent lines
        self.queue.put_nowait(item)

    def put(self, line: int) -> None:
        if not self.closed:
            self._put(line)

    def close(self) -> None:
        if not self.closed:
            self.closed = True
            self.closed_at = time.monotonic()
            self._put(None)


class TraceRegistry:
    """Channels by run token. A token is single use: registering it again supersedes the old channel."""

    def __init__(self):
        self.channels: dict[str, TraceChannel] = {}

    def register(self, token: str) -> TraceChannel:
        old = self.channels.get(token)
        if old is not None:
            old.close()
        channel = TraceChannel()
        self.channels[token] = channel
        return channel

    def get(self, token: str) -> Optional[TraceChannel]:
        return self.channels.get(token)

    def close(self, token: str) -> None:
        channel = self.channels.get(token)
        if channel is not None:
            channel.close()

    def expire(self, now: Optional[float] = None) -> None:
        now = time.monotonic() if now is None else now
        for token, channel in list(self.channels.items()):
            if channel.closed:
                stale = now - channel.closed_at > CLOSED_TTL
            else:
                stale = now - channel.created > UNSTARTED_TTL
            if stale:
                del self.channels[token]
