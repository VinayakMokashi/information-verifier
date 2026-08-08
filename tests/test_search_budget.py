"""The per-claim search budget survives pause_turn continuations. Free.

`max_uses` is a per-REQUEST tool cap and a paused turn is resumed with a
fresh request — review disputed whether that could lawfully bill
max_search_uses on every continuation (4 becoming 24). Rather than settle
the API-semantics argument, retrieve.py enforces the budget itself from
each response's measured usage. These tests drive that loop with a stub.
"""
import asyncio
import types

import pytest

from app.config import settings
from app.engine import retrieve as R
from app.models.claim import Claim

CLAIM = Claim(text="5G spreads coronavirus.", subject="5G",
              claim_type="causal", checkworthy=True)


def _resp(stop_reason="end_turn", searches=0, text="found nothing"):
    return types.SimpleNamespace(
        stop_reason=stop_reason,
        content=[types.SimpleNamespace(type="text", text=text)],
        usage=types.SimpleNamespace(
            server_tool_use=types.SimpleNamespace(web_search_requests=searches)),
    )


class StubClient:
    """Records each request's offered max_uses and plays scripted responses."""

    def __init__(self, responses):
        self._responses = list(responses)
        self.offered_max_uses = []
        outer = self

        class Messages:
            async def create(self, **kw):
                outer.offered_max_uses.append(kw["tools"][0]["max_uses"])
                return outer._responses.pop(0)

        self.messages = Messages()


def _run(stub, monkeypatch):
    monkeypatch.setattr(R, "async_client", stub)
    return asyncio.run(R._web_search(CLAIM))


def test_the_budget_is_spent_across_continuations_not_per_request(monkeypatch):
    """Three paused turns of 2 searches each must stop at the 4-search budget
    — and the third request must never be made."""
    monkeypatch.setattr(settings, "max_search_uses", 4)
    stub = StubClient([
        _resp("pause_turn", searches=2),
        _resp("pause_turn", searches=2),   # budget now 0 -> no resume
        _resp("end_turn", searches=99),    # would be request 3; must not happen
    ])

    _run(stub, monkeypatch)

    assert stub.offered_max_uses == [4, 2]   # remainder offered, then stop


def test_an_unpaused_turn_ends_the_loop_normally(monkeypatch):
    monkeypatch.setattr(settings, "max_search_uses", 4)
    stub = StubClient([_resp("end_turn", searches=3)])
    summary, sources = _run(stub, monkeypatch)
    assert stub.offered_max_uses == [4]
    assert summary == "found nothing"


def test_a_response_with_no_usage_field_does_not_crash_the_budget(monkeypatch):
    monkeypatch.setattr(settings, "max_search_uses", 4)
    bare = types.SimpleNamespace(stop_reason="end_turn",
                                 content=[], usage=None)
    stub = StubClient([bare])
    _run(stub, monkeypatch)
    assert stub.offered_max_uses == [4]


def test_continuations_are_still_bounded_by_the_backstop(monkeypatch):
    """Zero-search pause loops (no budget spent) must still terminate."""
    monkeypatch.setattr(settings, "max_search_uses", 4)
    stub = StubClient([_resp("pause_turn", searches=0)] * 10)
    _run(stub, monkeypatch)
    assert len(stub.offered_max_uses) == R._MAX_CONTINUATIONS
