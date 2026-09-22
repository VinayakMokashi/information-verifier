"""Regressions worth keeping across the chat pivot. Free.

The language-tag and translation-cache regressions died with the
back-translation stage. These two did not: a silently doubled bill, and a
stored answer that keeps citing a domain after it leaves the whitelist.
"""
import asyncio
import types

from app.providers.usage import UsageMeter, instrument


def test_a_stored_answer_stops_citing_a_de_whitelisted_domain(monkeypatch):
    """The gap this closed: tiering ran when the answer was BUILT, so one
    stored last week carried last week's whitelist — and the page re-serves
    stored answers on every reload of a #job= link."""
    from datetime import datetime, timezone

    import app.trusted_sources as TS
    from app.api.routes import relabel_sources
    from app.models.answer import Answer, JobStatus, Source

    stored = Answer(
        job_id="j", status=JobStatus.COMPLETE,
        created_at=datetime.now(timezone.utc), tier="trusted",
        sources=[Source(url="https://www.altnews.in/x", tier="trusted")],
    )
    assert relabel_sources(stored) is stored          # trusted: untouched

    monkeypatch.setattr(TS, "TRUSTED_DOMAINS",
                        [d for d in TS.TRUSTED_DOMAINS if d != "altnews.in"])
    served = relabel_sources(stored)
    assert served.sources[0].tier == "web"
    assert served.tier == "web"
    # The stored object itself is untouched — relabelling is a serve-time view.
    assert stored.sources[0].tier == "trusted"


# -- the meter cannot double-count -------------------------------------------

def test_a_delegating_sdk_cannot_double_the_bill():
    """The installed SDK's parse() calls _post() directly, so this is
    insurance — but a doubled bill would look entirely plausible."""
    class Delegating:
        async def create(self, **kw):
            return types.SimpleNamespace(usage=types.SimpleNamespace(
                input_tokens=100, output_tokens=0,
                cache_creation_input_tokens=0, cache_read_input_tokens=0,
                server_tool_use=types.SimpleNamespace(web_search_requests=1)))

        async def parse(self, **kw):
            return await self.create(**kw)      # the hazard

    client = types.SimpleNamespace(messages=Delegating())
    instrument(client)
    meter = UsageMeter()

    async def main():
        with meter.activate():
            await client.messages.parse(model="claude-haiku-4-5")

    asyncio.run(main())
    snap = meter.snapshot()
    assert snap.models["claude-haiku-4-5"].calls == 1
    assert snap.models["claude-haiku-4-5"].input_tokens == 100
    assert snap.web_searches == 1


def test_sequential_calls_still_count_separately():
    """The re-entrancy guard must not swallow genuinely separate calls."""
    class Plain:
        async def create(self, **kw):
            return types.SimpleNamespace(usage=types.SimpleNamespace(
                input_tokens=10, output_tokens=0, cache_creation_input_tokens=0,
                cache_read_input_tokens=0, server_tool_use=None))
        parse = create

    client = types.SimpleNamespace(messages=Plain())
    instrument(client)
    meter = UsageMeter()

    async def main():
        with meter.activate():
            await client.messages.create(model="m")
            await client.messages.create(model="m")

    asyncio.run(main())
    assert meter.snapshot().models["m"].calls == 2


def test_whitelisting_a_domain_later_never_promotes_a_stored_answer(monkeypatch):
    """A stored "web" answer can be one whose model said no fact-checker
    addressed the claim — and its prose says so. Promoting the label after
    the fact would put "Fact-checkers and official sources" over words that
    contradict it. The chip is re-tiered (a fact about the domain); the
    answer's label is not raised."""
    from datetime import datetime, timezone

    import app.trusted_sources as TS
    from app.api.routes import relabel_sources
    from app.models.answer import Answer, JobStatus, Source

    stored = Answer(
        job_id="j", status=JobStatus.COMPLETE,
        created_at=datetime.now(timezone.utc), tier="web",
        sources=[Source(url="https://newly-vetted.example/x", tier="web")],
    )
    monkeypatch.setattr(TS, "TRUSTED_DOMAINS",
                        [*TS.TRUSTED_DOMAINS, "newly-vetted.example"])
    served = relabel_sources(stored)
    assert served.sources[0].tier == "trusted"      # the domain fact moves
    assert served.tier == "web"                     # the judgment does not
