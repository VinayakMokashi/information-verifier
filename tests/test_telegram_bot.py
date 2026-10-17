"""The Telegram bot, fully offline. Free — no Telegram, no app, no network.

The loop is a thin shell; everything decision-shaped is a pure function or
takes duck-typed clients. What these pin: message classification agrees with
the server's own link gate, an Answer becomes a message that Telegram will
actually accept, prose can never smuggle a link past the sources block, and
every failure becomes words in the chat.
"""
import asyncio
import json
import os

import pytest

from app.config import settings
from scripts import telegram_bot as B

# -- classification -----------------------------------------------------------

def test_commands_get_help():
    assert B.classify_message({"text": "/start"})[0] == "help"
    assert B.classify_message({"text": "/help extra"})[0] == "help"


def test_plain_text_is_text():
    kind, payload = B.classify_message({"text": "WHO ne kaha 5G se corona"})
    assert (kind, payload) == ("text", "WHO ne kaha 5G se corona")


def test_links_use_the_servers_own_gate():
    """One definition of 'a checkable link', not two that drift apart."""
    kind, _ = B.classify_message({"text": "https://www.instagram.com/reel/DbsVyqLpbRa/"})
    assert kind == "link"
    kind, _ = B.classify_message({"text": "https://youtu.be/x"})
    assert kind == "link"
    # A lookalike the server would refuse must not be classified as a link.
    kind, _ = B.classify_message({"text": "https://youtube.com.evil.com/watch"})
    assert kind == "text"


def test_a_forward_containing_a_link_is_still_text():
    kind, _ = B.classify_message({"text": "dekho https://youtu.be/x sach hai kya"})
    assert kind == "text"


def test_voice_video_photo_and_junk():
    assert B.classify_message({"voice": {"file_id": "v1"}}) == ("media", "v1")
    assert B.classify_message({"video_note": {"file_id": "n1"}}) == ("media", "n1")
    assert B.classify_message(
        {"photo": [{"file_id": "small"}, {"file_id": "big"}]}) == ("image", "big")
    assert B.classify_message({"sticker": {}})[0] == "unsupported"


# -- reply formatting ---------------------------------------------------------

def _answer(**kw):
    base = {
        "status": "COMPLETE",
        "source_text": None,
        "sections": [{
            "tier": "trusted",
            "markdown": (
                "**This is false.** 5G radio waves cannot spread a virus.\n\n"
                "Alt News and BOOM both checked this when it went viral, and "
                "the WHO has said plainly that COVID-19 spreads through "
                "respiratory droplets."),
        }],
        "sources": [{"url": "https://altnews.in/x", "title": "No link",
                     "publisher": "AltNews", "tier": "trusted"}],
        "confidence": 95,
        "tier": "trusted",
        "truncated": False,
        "cached": False,
    }
    base.update(kw)
    return base


def test_the_answer_prose_is_the_reply():
    reply = B.format_reply(_answer())
    assert "5G radio waves cannot spread a virus" in reply
    assert "respiratory droplets" in reply
    # Markdown is promoted, not shown raw.
    assert "<b>This is false.</b>" in reply
    assert "**" not in reply


def test_the_readers_language_survives():
    """Devanagari in the sections comes out unchanged — no transliteration,
    no escaping of Indic code points."""
    hindi = "**यह दावा झूठा है।** 5जी की तरंगें वायरस नहीं फैला सकतीं।"
    reply = B.format_reply(_answer(sections=[{"tier": "trusted", "markdown": hindi}]))
    assert "5जी की तरंगें वायरस नहीं फैला सकतीं।" in reply
    assert "<b>यह दावा झूठा है।</b>" in reply
    # Sources stay in their original language — they are receipts to click,
    # and a translated headline is unfindable on the source page.
    assert "AltNews" in reply and "https://altnews.in/x" in reply


def test_evidence_badge_and_confidence_are_both_shown():
    reply = B.format_reply(_answer())
    assert "Fact-checkers / official sources se check kiya" in reply
    assert "95% confident" in reply


def test_a_missing_confidence_says_so_rather_than_inventing_one():
    reply = B.format_reply(_answer(confidence=None))
    assert "Confidence stated nahi hui" in reply
    assert "% confident" not in reply


def test_the_web_tier_is_labelled_not_blended_in():
    """Merged into one blob, a random blog reads as if it carried a
    fact-checker's authority."""
    reply = B.format_reply(_answer(
        tier="web",
        sections=[{"tier": "web", "markdown": "Only a few blogs mention this."}],
        sources=[{"url": "https://example.com/post", "title": "A post",
                  "publisher": "example.com", "tier": "web"}],
    ))
    assert "Sirf aam web" in reply
    assert "Aam web (fact-checkers nahi)" in reply


def test_both_tiers_get_a_divider_between_them():
    reply = B.format_reply(_answer(sections=[
        {"tier": "trusted", "markdown": "Nobody vetted has covered this."},
        {"tier": "web", "markdown": "A few blogs say otherwise."},
    ]))
    assert "Neeche sirf aam web se" in reply
    assert reply.index("Nobody vetted") < reply.index("Neeche sirf aam web se")
    assert reply.index("Neeche sirf aam web se") < reply.index("A few blogs")


def test_the_heard_text_is_shown_back():
    reply = B.format_reply(_answer(source_text="WHO ne kaha 5G se corona"))
    assert "Humne yeh suna/padha" in reply
    assert "WHO ne kaha" in reply


def test_a_cached_answer_says_it_cost_nothing():
    assert "kharch $0" in B.format_reply(_answer(cached=True))


def test_a_truncated_answer_says_so():
    assert "beech mein kat gaya" in B.format_reply(_answer(truncated=True))


def test_failed_reports_become_words():
    reply = B.format_reply({"status": "FAILED", "error": "The transcription "
                            "service is unavailable right now."})
    assert "Check nahi ho paya" in reply
    assert "transcription service" in reply


def test_html_in_content_is_escaped():
    reply = B.format_reply(_answer(sections=[
        {"tier": "trusted", "markdown": "<script>alert(1)</script>"}]))
    assert "<script>" not in reply
    assert "&lt;script&gt;" in reply


def test_a_url_the_model_wrote_never_becomes_a_tappable_link():
    """Invariant 3: prose is never a receipt. Telegram auto-links bare URLs in
    message text, so a link the MODEL invented would arrive tappable and
    indistinguishable from the vetted ones — the one surface where 'render it
    as plain text' is not enough on its own."""
    reply = B.format_reply(_answer(sections=[{
        "tier": "trusted",
        "markdown": "See [the study](https://evil.example/steal?q=secret) and "
                    "also https://evil.example/raw for details.",
    }]))
    assert "evil.example" not in reply
    assert "the study" in reply                 # the words survive
    assert reply.count("<a href=") == 1         # only the real citation
    assert "https://altnews.in/x" in reply


def test_a_leaked_sentinel_never_reaches_the_reader():
    """Invariant 7. The engine strips its own sentinel; this also runs over
    rows written before a fix."""
    reply = B.format_reply(_answer(sections=[{
        "tier": "trusted",
        "markdown": 'It is false. <verdict confidence="82" trusted="yes"/>',
    }]))
    assert "verdict confidence" not in reply
    assert "It is false." in reply


# -- length: Telegram rejects the whole message, so this is a payment bug -----

def test_a_long_answer_drops_whole_paragraphs_never_mid_sentence():
    paras = "\n\n".join(f"Paragraph number {i} " + "x" * 400 for i in range(20))
    reply = B.format_reply(_answer(sections=[{"tier": "trusted",
                                              "markdown": paras}]))
    assert len(reply) <= B._TG_HARD_LIMIT
    assert "poora jawab web page par" in reply   # the drop is DISCLOSED
    assert not reply.rstrip().endswith("<")


def test_a_giant_answer_never_yields_broken_html():
    """A cut landing inside a tag or an &entity; makes Telegram reject the
    whole message — which, before send() started checking its response, meant
    total silence after a paid check. Conversion happens per paragraph, so a
    cut can only land between well-formed blocks."""
    reply = B.format_reply(_answer(
        sections=[{"tier": "trusted",
                   "markdown": "**bold & <angry>** para\n\n" * 400}],
        source_text="x " * 900,
    ))
    assert len(reply) <= B._TG_HARD_LIMIT
    assert reply.count("<b>") == reply.count("</b>")
    assert reply.count("<i>") == reply.count("</i>")
    assert not reply.rstrip().endswith("<")


def test_a_huge_answer_cannot_push_out_the_receipts():
    """A verdict with no sources is the failure this project exists to avoid,
    so the receipts are reserved out of the budget before the prose gets it."""
    reply = B.format_reply(_answer(
        sections=[{"tier": "trusted", "markdown": "para " * 3000}]))
    assert len(reply) <= B._TG_HARD_LIMIT
    assert "https://altnews.in/x" in reply
    assert "95% confident" in reply


def test_one_enormous_paragraph_still_yields_an_answer():
    """MEASURED: 'para ' * 3000 is ONE 15,000-char block. It fit in no budget,
    so ALL of it was dropped and the reply was a 95%-confident badge with a
    source link and no answer — a confident-looking verdict explaining
    nothing, which is worse than saying nothing at all. Blocks must be
    droppable, therefore bounded."""
    reply = B.format_reply(_answer(
        sections=[{"tier": "trusted", "markdown": "para " * 3000}]))
    assert reply.count("para ") > 100, "the answer itself vanished"
    assert len(reply) <= B._TG_HARD_LIMIT
    assert "poora jawab web page par" in reply    # and the cut is disclosed


def test_escaping_expansion_cannot_blow_the_message_budget():
    """MEASURED: `source_text` is ASR / OCR / caption output — third-party
    text. 4,000 ampersands are 4,000 characters until `_e()` turns each into
    `&amp;`, and then they are 20,000. The budget measured the raw string, so
    the finished reply blew Telegram's hard limit and degraded to "Jawab bahut
    lamba hai" — throwing away an answer that had already been paid for.

    Cutting the ESCAPED string instead would be worse: a cut inside `&amp;` is
    exactly the broken entity Telegram rejects outright."""
    reply = B.format_reply(_answer(source_text="&" * 4000))
    assert len(reply) <= B._TG_HARD_LIMIT
    assert "5G radio waves cannot spread a virus" in reply, "the answer vanished"
    assert "&amp;" in reply                       # some of it still shown back
    assert "&am;" not in reply and "&a;" not in reply   # no split entity
    assert "aur characters" in reply              # and the cut is disclosed


def test_a_paragraph_with_no_spaces_can_still_be_softened():
    """_soften() broke on spaces, so a script that does not use them — or one
    enormous unbroken token — produced a single block that fit in no budget,
    and the whole answer was dropped again. Same failure as the 15,000-char
    paragraph, one layer down."""
    reply = B.format_reply(_answer(
        sections=[{"tier": "trusted", "markdown": "字" * 9000}]))
    assert len(reply) <= B._TG_HARD_LIMIT
    assert reply.count("字") > 500, "the answer vanished"


def test_a_source_heading_never_appears_with_nothing_under_it():
    """'🌐 Aam web' followed by no links tells the reader we found general-web
    sources and then shows none of them."""
    sources = [{"url": f"https://altnews.in/{i}", "publisher": "AltNews",
                "title": "x" * 78, "tier": "trusted"} for i in range(40)]
    sources.append({"url": "https://example.com/a", "publisher": "example.com",
                    "title": "A blog", "tier": "web"})
    reply = B.format_reply(_answer(sources=sources))
    for heading in ("📎 <b>Sources</b>", "🌐 <b>Aam web (fact-checkers nahi)</b>"):
        if heading in reply:
            after = reply[reply.index(heading) + len(heading):]
            assert "<a href=" in after.split("\n\n")[0], \
                f"{heading} has no sources under it"


def test_machine_read_text_is_not_silently_shortened():
    """Invariant 4: a mis-hear in a hidden tail would silently become a
    confident answer about words the sender never said."""
    long_heard = "क ख ग " * 900          # far past any inline budget
    reply = B.format_reply(_answer(source_text=long_heard))
    assert "Humne yeh suna/padha" in reply
    assert "aur characters" in reply     # the cut is DISCLOSED, not hidden

    short = "WHO ne kaha 5G se corona"
    assert "aur characters" not in B.format_reply(_answer(source_text=short))


def test_a_quote_in_a_source_url_cannot_break_the_html():
    """Source URLs come from search results; the trust filter checks the HOST,
    not the query. One unescaped double quote closed the href early, Telegram
    rejected the whole message, and the reader got silence after paying."""
    reply = B.format_reply(_answer(sources=[
        {"url": 'https://altnews.in/x?q="evil', "title": 'a "title"',
         "publisher": "AltNews", "tier": "trusted"}]))
    assert 'href="https://altnews.in/x?q=&quot;evil"' in reply
    # Exactly one opening and one closing anchor — the tag is not broken.
    assert reply.count("<a href=") == 1 and reply.count("</a>") == 1


def test_a_non_http_source_url_is_never_linked():
    reply = B.format_reply(_answer(sources=[
        {"url": "javascript:alert(1)", "title": "x", "publisher": "evil",
         "tier": "trusted"}]))
    assert "javascript:" not in reply
    assert "<a href=" not in reply


# -- one message end to end (stub clients) ------------------------------------

class StubApp:
    def __init__(self, report=None, reject=None):
        self.report = report or _answer()
        self.reject = reject
        self.submissions = []
        self.subjects = []          # whom each submission was made for

    async def submit_json(self, endpoint, payload, subject=None):
        self.submissions.append((endpoint, payload))
        self.subjects.append(subject)
        if self.reject:
            return None, self.reject
        return "job123", ""

    async def submit_file(self, endpoint, filename, content, content_type, subject=None):
        self.submissions.append((endpoint, filename, content_type))
        self.subjects.append(subject)
        return "job123", ""

    async def wait_for_report(self, job_id, attempts=None):
        return self.report


class StubTG:
    def __init__(self):
        self.sent = []

    async def send(self, chat_id, text):
        # A real send is a network call, and a network call SUSPENDS. Without
        # this the fake never yields, and the double-payment race in
        # handle_message (check pending -> send ack -> submit) could not
        # happen in a test — measured: a no-op lock still passed.
        await asyncio.sleep(0)
        self.sent.append((chat_id, text))
        return True

    async def file_bytes(self, file_id):
        return b"OggS-fake", "voice/file_77.oga"


def _handle(msg, app, tg, pending=None, prompted=None):
    asyncio.run(B.handle_message(msg, app, tg, pending, prompted=prompted))


def test_text_flow_submits_polls_and_replies():
    app, tg = StubApp(), StubTG()
    _handle({"chat": {"id": 7}, "text": "WHO ne kaha 5G se corona"}, app, tg)

    assert app.submissions == [("text", {"text": "WHO ne kaha 5G se corona"})]
    assert len(tg.sent) == 2                      # ack + reply
    assert "Checking" in tg.sent[0][1]
    assert "This is false." in tg.sent[1][1]


def test_link_flow_uses_the_link_endpoint():
    app, tg = StubApp(), StubTG()
    _handle({"chat": {"id": 7},
             "text": "https://www.youtube.com/shorts/QBHKZ36_dlo"}, app, tg)
    assert app.submissions[0][0] == "link"


def test_voice_flow_downloads_then_posts_multipart():
    app, tg = StubApp(), StubTG()
    _handle({"chat": {"id": 7}, "voice": {"file_id": "v9"}}, app, tg)
    endpoint, filename, ctype = app.submissions[0]
    assert endpoint == "media"
    assert filename == "file_77.oga"
    assert ctype == "audio/ogg"


def test_a_rejection_reaches_the_chat_in_words():
    app, tg = StubApp(reject="Only public Instagram and YouTube links can be "
                             "checked (https)."), StubTG()
    _handle({"chat": {"id": 7}, "text": "some text"}, app, tg)
    assert "😕" in tg.sent[-1][1]
    assert "Only public" in tg.sent[-1][1]


def test_a_crash_still_answers_the_chat():
    class ExplodingApp(StubApp):
        async def submit_json(self, endpoint, payload, subject=None):
            raise RuntimeError("app down")

    app, tg = ExplodingApp(), StubTG()
    # A real claim: "hello" is small talk now and never reaches a submit.
    _handle({"chat": {"id": 7}, "text": "WHO ne kaha 5G se corona"}, app, tg)
    assert "gadbad" in tg.sent[-1][1]


def test_help_costs_nothing():
    app, tg = StubApp(), StubTG()
    _handle({"chat": {"id": 7}, "text": "/start"}, app, tg)
    assert app.submissions == []
    assert "Information Verifier" in tg.sent[0][1]


def test_help_promises_what_the_engine_actually_does():
    """The bot went general-purpose with the engine; a help text still
    promising only Indian political fact-checks would undersell it and
    mis-set expectations for a health or science question."""
    assert "health" in B.HELP and "science" in B.HELP
    assert "WHO" in B.HELP


class _PendingApp(StubApp):
    """Reports 'not ready' on the first wait, ready afterwards."""

    def __init__(self):
        super().__init__()
        self.waits = 0

    async def wait_for_report(self, job_id, attempts=None):
        self.waits += 1
        return None if self.waits == 1 else self.report


def test_a_slow_check_is_resumed_not_re_bought():
    """Telling a user to 'send it again' bought the whole check twice —
    exactly for the slow, expensive jobs."""
    app, tg, pending, prompted = _PendingApp(), StubTG(), {}, set()

    _handle({"chat": {"id": 7}, "text": "WHO ne kaha 5G"}, app, tg, pending, prompted)
    assert pending == {7: "job123"}              # remembered for next time
    assert "dobara paisa nahi lagega" in tg.sent[-1][1]

    _handle({"chat": {"id": 7}, "text": "kya hua?"}, app, tg, pending, prompted)
    assert len(app.submissions) == 1             # NOT resubmitted
    assert "pichla check pura hua" in tg.sent[-2][1]
    assert "This is false." in tg.sent[-1][1]
    assert pending == {}


def test_a_still_running_job_blocks_a_new_submission():
    class NeverReady(StubApp):
        async def wait_for_report(self, job_id, attempts=None):
            return None

    app, tg, pending = NeverReady(), StubTG(), {7: "old-job"}
    _handle({"chat": {"id": 7}, "text": "naya rumour"}, app, tg, pending)

    assert app.submissions == []                 # wallet protected
    assert "abhi bhi chal raha hai" in tg.sent[-1][1]


def test_help_still_works_while_a_job_is_pending():
    app, tg, pending = StubApp(), StubTG(), {7: "old-job"}
    _handle({"chat": {"id": 7}, "text": "/help"}, app, tg, pending)
    assert "Information Verifier" in tg.sent[0][1]
    assert app.submissions == []


def test_a_bare_http_error_never_reaches_the_chat():
    """ "HTTP 500" was sent straight into the chat when the API gave no detail."""
    import httpx

    class Bare500:
        async def post(self, *a, **kw):
            return httpx.Response(500, text="Internal Server Error")

    app = B.AppClient(Bare500(), base="http://x")
    job_id, err = asyncio.run(app.submit_json("text", {"text": "x"}))
    assert job_id is None
    assert "HTTP" not in err and "500" not in err
    assert "dobara" in err


# -- concurrency (to-do 8, 2026-09-22) ----------------------------------------

class _GatedApp(StubApp):
    """A check whose FINISHING and whose long-wait WAKING are separate.

    `done[job]`    — the server has finished it: a quick peek sees the answer.
    `release[job]` — the handler's long wait wakes up.
    Real life has a gap between the two (the wait polls every few seconds);
    the exactly-once test lives in that gap.
    """

    def __init__(self):
        super().__init__()
        self.done: dict[str, asyncio.Event] = {}
        self.release: dict[str, asyncio.Event] = {}
        self._n = 0
        self._all_finished = False

    async def submit_json(self, endpoint, payload, subject=None):
        await asyncio.sleep(0)                 # a real POST suspends too
        self.submissions.append((endpoint, payload))
        self._n += 1
        job = f"job{self._n}"
        self.done[job], self.release[job] = asyncio.Event(), asyncio.Event()
        if self._all_finished:                 # so drain() can never hang on a
            self.done[job].set()               # job submitted after finish_all —
            self.release[job].set()            # a broken bot must FAIL, not hang
        return job, ""

    async def wait_for_report(self, job_id, attempts=None):
        if attempts is not None:           # the short "is it done yet?" peek
            return self.report if self.done[job_id].is_set() else None
        await self.release[job_id].wait()
        return self.report

    def finish_all(self):
        self._all_finished = True
        for job in self.done:
            self.done[job].set()
            self.release[job].set()


def _msg(chat, text):
    return {"chat": {"id": chat}, "text": text}


async def _until(condition, turns=500):
    """Let the event loop run until `condition()` holds (or give up quietly
    and let the assertions that follow report what happened).

    NOT asyncio.sleep(0.01): asyncio's clock on Windows is time.monotonic,
    measured here stepping in 15-16 ms jumps, so a 10 ms sleep can return
    after a single loop turn — before a handler reaches its third await. The
    first version of these tests failed on exactly that, not on the bot.
    """
    for _ in range(turns):
        if condition():
            return
        await asyncio.sleep(0)


def test_one_chats_slow_check_does_not_block_another_chat():
    """The bot handled messages one at a time: one person's 4-minute reel
    check blocked every other chat, /help included."""
    async def scenario():
        app, tg = _GatedApp(), StubTG()
        bot = B.Dispatcher(app, tg)
        bot.dispatch(_msg(1, "a slow rumour"))
        await _until(lambda: "job1" in app.done)   # chat 1 is now waiting
        bot.dispatch(_msg(2, "/help"))
        bot.dispatch(_msg(3, "another rumour"))
        await _until(lambda: len(app.submissions) == 2
                     and any(c == 2 for c, _ in tg.sent))
        # Chat 2 got help and chat 3 got its own check started — while chat
        # 1's check is still running.
        assert any(c == 2 and "Information Verifier" in t for c, t in tg.sent)
        assert [p for _, p in app.submissions] == [{"text": "a slow rumour"},
                                                    {"text": "another rumour"}]
        app.finish_all()
        await bot.drain()
        return tg

    tg = asyncio.run(scenario())
    replies = [c for c, t in tg.sent if "This is false." in t]
    assert sorted(replies) == [1, 3]


def test_two_messages_from_one_chat_at_once_pay_for_one_check():
    """The money risk that concurrency opened: both handlers would see no
    pending job and BOTH submit. The per-chat lock makes the second one find
    the first job instead."""
    async def scenario():
        app, tg = _GatedApp(), StubTG()
        bot = B.Dispatcher(app, tg)
        bot.dispatch(_msg(7, "first message"))
        bot.dispatch(_msg(7, "second message, sent right after"))
        # Wait for the second message's outcome — "still running" if the
        # lock worked, a second submission if it did not.
        await _until(lambda: len(app.submissions) > 1
                     or any("abhi bhi chal raha hai" in t for _, t in tg.sent))
        assert len(app.submissions) == 1, "one chat paid twice"
        assert any("abhi bhi chal raha hai" in t for _, t in tg.sent)
        app.finish_all()
        await bot.drain()
        return app, tg

    app, tg = asyncio.run(scenario())
    assert len(app.submissions) == 1


def test_a_finished_check_is_delivered_exactly_once():
    """The job finishes on the server while the first handler's wait has not
    woken yet, and the user asks again in that gap. The second message's peek
    delivers it; the first handler must then stay silent — not send it twice."""
    async def scenario():
        app, tg = _GatedApp(), StubTG()
        bot = B.Dispatcher(app, tg)
        bot.dispatch(_msg(7, "a rumour"))
        await _until(lambda: "job1" in app.done)   # waiting on job1
        app.done["job1"].set()                     # finished server-side...
        bot.dispatch(_msg(7, "kya hua?"))          # ...and the user asks again
        await _until(lambda: any("This is false." in t for _, t in tg.sent))
        app.release["job1"].set()                  # now the first wait wakes
        await bot.drain()
        return app, tg

    app, tg = asyncio.run(scenario())
    assert sum("This is false." in t for _, t in tg.sent) == 1
    assert len(app.submissions) == 1               # "kya hua?" bought nothing


class _PeekGatedApp(_GatedApp):
    """_GatedApp whose short peek takes real time (2 polls, ~3 s in life):
    it starts, then waits on `peek_gate` before answering."""

    def __init__(self):
        super().__init__()
        self.peek_gate = asyncio.Event()
        self.peeking = 0

    async def wait_for_report(self, job_id, attempts=None):
        if attempts is not None:
            self.peeking += 1
            await self.peek_gate.wait()
        return await super().wait_for_report(job_id, attempts)


def test_a_new_message_is_never_silently_dropped():
    """Found by review, reproduced: chat 7's second message peeked at the
    first job; the first handler finished and delivered it meanwhile; the
    peek then saw nothing left to deliver and returned — the second message
    got no reply at all. It is not checked automatically (at 2 a day, "kya
    hua?" would spend half the day), but the chat is told, in words."""
    async def scenario():
        app, tg = _PeekGatedApp(), StubTG()
        bot = B.Dispatcher(app, tg)
        bot.dispatch(_msg(7, "first rumour"))
        await _until(lambda: "job1" in app.done)
        bot.dispatch(_msg(7, "a DIFFERENT rumour"))
        await _until(lambda: app.peeking == 1)       # second handler is peeking
        app.done["job1"].set()
        app.release["job1"].set()                    # first handler delivers job1
        await _until(lambda: any("This is false." in t for _, t in tg.sent))
        app.peek_gate.set()                          # the peek comes back
        await _until(lambda: any(t == B._NOT_CHECKED for _, t in tg.sent))
        app.finish_all()
        await bot.drain()
        return app, tg

    app, tg = asyncio.run(scenario())
    assert len(app.submissions) == 1                             # nothing spent
    assert sum("This is false." in t for _, t in tg.sent) == 1   # job1, once
    assert tg.sent[-1] == (7, B._NOT_CHECKED)


def test_a_message_sent_mid_check_hands_over_the_answer_and_says_so():
    """The first handler is still waiting when the second message's peek
    finds the job done: the peek delivers it, exactly once, and says that
    the new message itself was not checked — nobody had asked for a poke."""
    async def scenario():
        app, tg = _GatedApp(), StubTG()
        bot = B.Dispatcher(app, tg)
        bot.dispatch(_msg(7, "first rumour"))
        await _until(lambda: "job1" in app.done)
        app.done["job1"].set()                       # done; first wait not awake
        bot.dispatch(_msg(7, "a DIFFERENT rumour"))
        await _until(lambda: any(t == B._NOT_CHECKED for _, t in tg.sent))
        app.release["job1"].set()                    # the first wait wakes: silent
        await bot.drain()
        return app, tg

    app, tg = asyncio.run(scenario())
    assert len(app.submissions) == 1
    assert sum("This is false." in t for _, t in tg.sent) == 1
    assert [t for _, t in tg.sent][-3:-1] == ["Aapka pichla check pura hua:",
                                              tg.sent[-2][1]]
    assert tg.sent[-1] == (7, B._NOT_CHECKED)


def test_a_greeting_is_answered_without_a_check():
    """MEASURED 2026-10-10: "hi" bought a full check and a daily slot."""
    app, tg = StubApp(), StubTG()
    assert B.classify_message(_msg(7, "hi"))[0] == "smalltalk"
    _handle(_msg(7, "hi"), app, tg)
    assert app.submissions == []
    assert tg.sent == [(7, B._SMALLTALK_REPLY)]


def test_ok_still_collects_the_report_the_bot_asked_a_poke_for():
    """When a check outlives the wait, the bot asks for "any message" — and
    "ok" is what people send. Small talk must still deliver that report,
    which is why it is not filed under "help" (help answers before the
    pending-report logic runs)."""
    app, tg, pending, prompted = _PendingApp(), StubTG(), {}, set()
    _handle(_msg(7, "WHO ne kaha 5G"), app, tg, pending, prompted)
    assert prompted == {7}
    _handle(_msg(7, "ok"), app, tg, pending, prompted)
    assert len(app.submissions) == 1                 # nothing new was bought
    assert "This is false." in tg.sent[-1][1]
    assert pending == {}
    assert not any(t == B._NOT_CHECKED for _, t in tg.sent)


def test_the_poke_a_timed_out_wait_asked_for_gets_no_extra_note():
    """When the wait gave up it asked for "any message"; that message IS the
    request, and telling the person it "was not checked" would only confuse."""
    app, tg, pending, prompted = _PendingApp(), StubTG(), {}, set()
    _handle(_msg(7, "WHO ne kaha 5G"), app, tg, pending, prompted)
    assert prompted == {7}, "the wait did not record that it asked for a poke"
    _handle(_msg(7, "kya hua?"), app, tg, pending, prompted)
    assert "This is false." in tg.sent[-1][1]
    assert not any(t == B._NOT_CHECKED for _, t in tg.sent)
    assert prompted == set(), "the poke was not consumed"


class _GoneApp(StubApp):
    """The chat's remembered job no longer exists on the server."""

    async def wait_for_report(self, job_id, attempts=None):
        if job_id == "pruned-job":
            raise B.JobGone(job_id)
        return self.report


def test_a_job_the_server_deleted_does_not_lock_the_chat():
    """Found by review, reproduced: answers are deleted after 30 days now, so
    a 404 is a normal outcome. It read as "still running", and the chat was
    told so on every message until the bot restarted."""
    app, tg, pending = _GoneApp(), StubTG(), {7: "pruned-job"}
    _handle(_msg(7, "naya rumour"), app, tg, pending)
    assert app.submissions == [("text", {"text": "naya rumour"})]
    assert "This is false." in tg.sent[-1][1]
    assert not any("abhi bhi chal raha hai" in t for _, t in tg.sent)
    assert pending == {}


def test_a_404_is_gone_not_still_running():
    import httpx

    class Http404:
        async def get(self, *a, **kw):
            return httpx.Response(404, json={"detail": "Report not found."})

    app = B.AppClient(Http404(), base="http://x")
    with pytest.raises(B.JobGone):
        asyncio.run(app.wait_for_report("pruned-job", attempts=2))


def test_one_chat_cannot_hold_every_slot():
    """Found by review, reproduced: each queued message took a global slot
    BEFORE waiting on its chat's lock, so one impatient chat re-sending could
    hold all of them and starve every other chat. Queued messages now wait
    on their own chat's lock without a slot, and the minutes-long wait for a
    report holds none either."""
    async def scenario():
        app, tg = _PeekGatedApp(), StubTG()
        bot = B.Dispatcher(app, tg, max_in_flight=2)
        bot.dispatch(_msg(7, "chat 7 rumour"))
        await _until(lambda: "job1" in app.done)     # chat 7 waiting on its check
        for i in range(5):
            bot.dispatch(_msg(7, f"chat 7 again {i}"))
        await _until(lambda: app.peeking == 1)
        bot.dispatch(_msg(8, "chat 8 rumour"))
        await _until(lambda: len(app.submissions) == 2)
        submitted = [p["text"] for _, p in app.submissions]
        app.peek_gate.set()
        app.finish_all()
        await bot.drain()
        return submitted

    assert asyncio.run(scenario()) == ["chat 7 rumour", "chat 8 rumour"]


def test_a_poke_queued_behind_its_own_chat_is_not_paid_for():
    """Found by the review of the concurrency fix, reproduced: the rule was
    enforced when the lock was ACQUIRED, not when the message arrived. Two
    quick pokes — the first holds the chat lock for its ~3 s peek, the check
    finishes and is delivered in that window, and the second then finds an
    empty `pending` and is submitted as a new check. Paid, at 2 a day."""
    async def scenario():
        app, tg = _PeekGatedApp(), StubTG()
        bot = B.Dispatcher(app, tg)
        bot.dispatch(_msg(7, "Kya 5G se corona failta hai?"))
        await _until(lambda: "job1" in app.done)
        # Pokes that are NOT small talk: "?" would now never be submitted at
        # all (triage, 2026-10-10), and the test would pass with the guard
        # it exists for removed.
        bot.dispatch(_msg(7, "kab tak?"))             # poke 1: takes the lock
        await _until(lambda: app.peeking == 1)
        bot.dispatch(_msg(7, "kab tak??"))            # poke 2: queues on it
        await _until(lambda: len(bot._tasks) == 2)
        app.done["job1"].set()
        app.release["job1"].set()                     # delivered in that window
        await _until(lambda: any("This is false." in t for _, t in tg.sent))
        app.peek_gate.set()
        await _until(lambda: sum(t == B._NOT_CHECKED for _, t in tg.sent) == 2)
        app.finish_all()
        await bot.drain()
        return app, tg

    app, tg = asyncio.run(scenario())
    assert [p["text"] for _, p in app.submissions] == ["Kya 5G se corona failta hai?"]
    assert sum(t == B._NOT_CHECKED for _, t in tg.sent) == 2   # both were answered


def test_a_burst_from_one_chat_pays_for_one_check():
    """Found by a 2,000-interleaving search of the FIXED bot (seed 120): a
    burst of three arrives before the first handler has submitted anything,
    so `pending` was empty when each was dispatched — and the third, landing
    while the first answer was being delivered, looked like a fresh start
    and was paid for. "Busy" has to include "an earlier message of this chat
    is still being handled"."""
    async def scenario():
        app, tg = _GatedApp(), StubTG()
        bot = B.Dispatcher(app, tg)
        for i in range(3):
            bot.dispatch(_msg(7, f"rumour {i}"))
        await _until(lambda: "job1" in app.done)
        app.done["job1"].set()
        app.release["job1"].set()
        await _until(lambda: len(bot._tasks) <= 1)
        app.finish_all()
        await bot.drain()
        return app, tg

    app, tg = asyncio.run(scenario())
    assert [p["text"] for _, p in app.submissions] == ["rumour 0"]
    assert sum("This is false." in t for _, t in tg.sent) == 1
    for chat, text in tg.sent:                 # and every message was answered
        assert text
    assert len([1 for _, t in tg.sent if t == B._NOT_CHECKED
                or "abhi bhi chal raha hai" in t]) == 2


def test_the_timeout_message_says_the_next_message_is_not_checked():
    """It asks for "any message" to re-deliver the report — so it has to say
    that the message itself will not be checked, or a new claim sent in
    answer to it is consumed as the poke in silence (found by review)."""
    app, tg, pending = _PendingApp(), StubTG(), {}
    _handle(_msg(7, "WHO ne kaha 5G"), app, tg, pending)
    prompt = tg.sent[-1][1]
    assert "koi bhi message bhejiye" in prompt
    assert "khud check nahi hoga" in prompt


def test_drain_returns_when_the_last_task_has_only_just_finished():
    """drain() spun forever — synchronously, so no timeout could fire — when
    called in the one loop turn between a task finishing and its
    done-callback removing it. A thread, so that a spin FAILS this test
    instead of hanging the suite."""
    import threading

    async def scenario():
        bot = B.Dispatcher(StubApp(), StubTG())
        bot.dispatch(_msg(7, "/help"))
        await _until(lambda: all(t.done() for t in bot._tasks))
        await bot.drain()

    runner = threading.Thread(target=asyncio.run, args=(scenario(),), daemon=True)
    runner.start()
    runner.join(10)
    assert not runner.is_alive(), "drain() never returned"


def test_the_bot_waits_longer_for_a_202_than_the_server_may_take():
    """Traced by review: the bot's HTTP timeout was 30 s, and /verify/link
    resolves the link INLINE (yt-dlp; a Facebook reel measured 14 s). A
    slower resolve timed the bot out and it said "try again" — while the
    server went on to create and bill the job, whose answer nobody would
    ever deliver, and the retry paid again."""
    import httpx

    from app.api import routes

    seen = {}

    class Recorder:
        async def post(self, *a, **kw):
            seen.update(kw)
            return httpx.Response(202, json={"job_id": "j", "status": "QUEUED"})

    asyncio.run(B.AppClient(Recorder(), base="http://x").submit_json("link", {"url": "u"}))
    assert seen["timeout"].read >= 2 * routes._RESOLVE_WALL_S
    seen.clear()
    asyncio.run(B.AppClient(Recorder(), base="http://x").submit_file(
        "image", "a.png", b"x", "image/png"))
    assert seen["timeout"].read >= 2 * routes._RESOLVE_WALL_S


def test_one_failing_message_does_not_stop_the_others():
    class Exploding(StubApp):
        async def submit_json(self, endpoint, payload, subject=None):
            if payload["text"] == "boom":
                raise RuntimeError("app down")
            return await super().submit_json(endpoint, payload, subject)

    async def scenario():
        app, tg = Exploding(), StubTG()
        bot = B.Dispatcher(app, tg)
        bot.dispatch(_msg(1, "boom"))
        bot.dispatch(_msg(2, "fine"))
        await bot.drain()
        return tg

    tg = asyncio.run(scenario())
    assert any(c == 1 and "gadbad" in t for c, t in tg.sent)
    assert any(c == 2 and "This is false." in t for c, t in tg.sent)


def test_the_summary_is_reserved_so_a_long_answer_cannot_drop_it():
    """It is the part a reader who reads nothing else reads (Vinayak,
    2026-09-23), so the length budget takes it out FIRST — like the
    receipts — instead of letting the prose eat it."""
    paras = "\n\n".join(f"Paragraph {i} " + "x" * 400 for i in range(20))
    reply = B.format_reply(_answer(
        sections=[{"tier": "trusted", "markdown": paras}],
        summary="5G does not spread covid. Alt News and the WHO checked it."))
    assert "In short" in reply
    assert "5G does not spread covid." in reply
    assert len(reply) <= B._TG_HARD_LIMIT
    assert "aur" in reply and "paragraph" in reply      # the prose was cut, not it


def test_an_answer_with_no_summary_reads_as_before():
    reply = B.format_reply(_answer())
    assert "In short" not in reply
    assert "blockquote" not in reply


def _probe(base: str, status: int, body: dict | None = None):
    import httpx

    seen = []

    def handler(request):
        seen.append(request.url.path)
        return httpx.Response(status, json=body or {})

    async def run():
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as http:
            return await B.app_is_up(http, base)

    return asyncio.run(run()), seen


_READY = {"status": "ready", "mode": "real",
          "checks": {"database": True, "keys": True, "ffmpeg": True}}


def test_the_startup_probe_asks_the_apps_real_ready_route():
    """MEASURED 2026-09-29, going live: the probe asked APP_BASE/../health,
    which resolves to /api/health — a 404 — and passed anyway, because any
    HTTP response counted as "up". Something else on port 8000 would have
    passed too. Since OPS-18 it asks /ready, which knows the mode."""
    up, seen = _probe("http://127.0.0.1:8000/api/v1", 200, _READY)
    assert seen == ["/ready"]
    assert up is True
    # APP_BASE can point at an app mounted under a prefix (a proxy path).
    up, seen = _probe("http://host/verifier/api/v1/", 200, _READY)
    assert seen == ["/verifier/ready"]
    assert up is True


def test_the_bot_refuses_the_free_demo_server():
    """PROJECT_PLAN §11 19 / audit-ops OPS-18: the demo server answered the
    constant /health too, and a bot started beside it would have sent people
    its simulated verdicts as real."""
    import httpx

    def handler(request):
        return httpx.Response(200, json={**_READY, "mode": "demo"})

    async def run():
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as http:
            return (await B.app_status(http, "http://127.0.0.1:8000/api/v1"),
                    await B.app_is_up(http, "http://127.0.0.1:8000/api/v1"))

    assert asyncio.run(run()) == ("demo", False)


def test_an_app_that_is_not_ready_is_told_apart_from_an_absent_one():
    import httpx

    def handler(request):
        return httpx.Response(503, json={**_READY, "status": "not ready"})

    async def run():
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as http:
            return await B.app_status(http, "http://127.0.0.1:8000/api/v1")

    assert asyncio.run(run()) == "not ready"


def test_a_404_from_the_probe_is_not_an_app_that_is_up():
    up, _ = _probe("http://127.0.0.1:8000/api/v1", 404, {"detail": "Not Found"})
    assert up is False


def test_some_other_server_answering_200_is_not_our_app():
    import httpx

    def handler(request):
        return httpx.Response(200, text="<html>someone else's page</html>")

    async def run():
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as http:
            return await B.app_is_up(http, "http://127.0.0.1:8000/api/v1")

    assert asyncio.run(run()) is False


def test_a_summary_is_escaped_like_everything_else_a_model_wrote():
    reply = B.format_reply(_answer(summary='<script>alert(1)</script> & "quoted"'))
    assert "<script>" not in reply
    assert "&lt;script&gt;" in reply


# -- the bot token never reaches a printed line --------------------------------

# Every Bot API URL carries the token, and an httpx error's text IS its URL.
_TOKEN = "123456:PLANTED-token-must-never-print"


def _real_tg_run(handler, body):
    """Drive the REAL TelegramClient against a fake Telegram."""
    import httpx

    async def run():
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as http:
            return await body(B.TelegramClient(http, _TOKEN))

    return asyncio.run(run())


def test_a_voice_note_telegram_will_not_hand_over_never_prints_the_token(capsys):
    """Telegram refuses getFile over 20 MB ("file is too big"), so anyone can
    cause this by sending a big video. The refusal surfaced as an httpx
    error whose text is the request URL, and the submit catch-all printed
    it — the token, in the log (and in a host's log store, once public)."""
    import json

    import httpx

    sent = []

    def handler(request):
        if request.url.path.endswith("/getFile"):
            return httpx.Response(400, json={"ok": False, "error_code": 400,
                                             "description": "Bad Request: file is too big"})
        if request.url.path.endswith("/sendMessage"):
            sent.append(json.loads(request.content))
            return httpx.Response(200, json={"ok": True, "result": {}})
        return httpx.Response(404, json={"ok": False})

    _real_tg_run(handler, lambda tg: B.handle_message(
        {"chat": {"id": 7}, "voice": {"file_id": "v9"}}, StubApp(), tg))

    out = capsys.readouterr()
    assert _TOKEN not in out.out + out.err
    assert "getFile" in out.out             # the failure is still logged...
    assert "gadbad" in sent[-1]["text"]     # ...and the chat still hears back


@pytest.mark.parametrize("call, failing, status", [
    ("get_updates", "/getUpdates", 409),    # another poller holds the token
    ("file_bytes", "/getFile", 400),        # over Telegram's 20 MB limit
    ("file_bytes", "/file/", 404),          # the download itself (its own URL)
])
def test_no_error_leaving_the_telegram_client_carries_the_token(call, failing, status):
    """The rule at the seam, for every call that can raise: whatever prints
    the error — a catch-all, a traceback — prints no token. It must stay an
    httpx.HTTPError: the poll loop's retry catches exactly that."""
    import traceback

    import httpx

    def handler(request):
        if failing in request.url.path:
            return httpx.Response(status, json={"ok": False, "error_code": status,
                                                "description": "refused"})
        if request.url.path.endswith("/getFile"):
            return httpx.Response(200, json={"ok": True,
                                             "result": {"file_path": "voice/file_1.oga"}})
        return httpx.Response(200, json={"ok": True, "result": []})

    async def body(tg):
        if call == "get_updates":
            return await tg.get_updates(0)
        return await tg.file_bytes("f1")

    with pytest.raises(httpx.HTTPError) as info:
        _real_tg_run(handler, body)
    shown = (str(info.value) + repr(info.value)
             + "".join(traceback.format_exception(info.value)))
    assert _TOKEN not in shown
    assert str(status) in str(info.value)   # still says what went wrong


# -- a file Telegram will not hand a bot is refused up front -------------------

_OVER_TG_LIMIT = 21 * 1024 * 1024


@pytest.mark.parametrize("key", ["voice", "audio", "video", "video_note"])
def test_media_over_telegrams_bot_download_limit_is_classified_up_front(key):
    msg = {"chat": {"id": 7}, key: {"file_id": "big", "file_size": _OVER_TG_LIMIT}}
    assert B.classify_message(msg)[0] == "too_big"


def test_media_at_or_under_the_limit_or_of_unknown_size_is_still_media():
    at = {"voice": {"file_id": "a", "file_size": 20 * 1024 * 1024}}
    unknown = {"voice": {"file_id": "b"}}           # file_size is optional
    assert B.classify_message(at) == ("media", "a")
    assert B.classify_message(unknown) == ("media", "b")


def test_a_too_big_file_gets_the_real_reason_not_try_again_later():
    """Telegram refuses getFile over 20 MB, every time. The bot used to say
    "Checking…", fail the download, and then "try again later" — advice
    that can never work, so a person retries and waits for nothing."""
    app, tg = StubApp(), StubTG()
    _handle({"chat": {"id": 7},
             "video": {"file_id": "big", "file_size": _OVER_TG_LIMIT}}, app, tg)
    assert app.submissions == []                    # nothing downloaded or sent
    assert len(tg.sent) == 1
    assert "20 MB" in tg.sent[0][1]
    assert "Checking" not in tg.sent[0][1]


# -- each Telegram user is their own person to the API (2026-10-15) ------------

def test_each_telegram_user_is_their_own_subject():
    """REPRODUCED 2026-10-15: every Telegram user reached the API as ONE
    client — the bot on 127.0.0.1 — so the per-person limits were one bucket
    for all of them. The bot names the person on every submission."""
    app, tg = StubApp(), StubTG()
    _handle({"chat": {"id": 7}, "from": {"id": 4242}, "text": "5G spreads corona"}, app, tg)
    assert app.subjects == ["tg:4242"]

    channel = StubApp()           # a channel post has no sender: the chat is the person
    _handle({"chat": {"id": -100123}, "text": "5G spreads corona"}, channel, StubTG())
    assert channel.subjects == ["tgchat:-100123"]

    voice = StubApp()
    _handle({"chat": {"id": 7}, "from": {"id": 4242}, "voice": {"file_id": "v9"}},
            voice, StubTG())
    assert voice.subjects == ["tg:4242"]


def test_the_real_app_client_sends_the_person_on_every_submission():
    import httpx

    seen = []

    def handler(request):
        seen.append(request.headers.get("x-verifier-subject"))
        return httpx.Response(202, json={"job_id": "j1", "status": "QUEUED"})

    async def run():
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as http:
            app = B.AppClient(http, "http://127.0.0.1:8000/api/v1")
            await app.submit_json("text", {"text": "x"}, subject="tg:42")
            await app.submit_file("image", "a.png", b"x", "image/png", subject="tg:42")
            await app.submit_json("text", {"text": "x"})            # nobody named

    asyncio.run(run())
    assert seen == ["tg:42", "tg:42", None]


def test_the_bot_and_the_api_agree_on_the_header_and_its_shape():
    """One name for the header, imported, not copied; and every subject the
    bot can produce is one the API will honour."""
    from app.api import limits

    assert B.SUBJECT_HEADER is limits.SUBJECT_HEADER
    for msg in ({"chat": {"id": 7}, "from": {"id": 4242}},
                {"chat": {"id": -1001234567890}},
                {"chat": {"id": 7}, "from": {"id": 9_999_999_999}}):
        assert limits._SUBJECT.fullmatch(B.subject_of_message(msg))


def test_a_link_with_a_line_break_and_a_question_is_text_not_a_crash():
    """REPRODUCED (review R3): "link\nKya yeh sach hai?" was filed as a link
    with the question inside it, crashed the server's URL handling (a 500),
    and the bot said "try again later" — which could never work. A link
    with other words around it is text (the existing rule above)."""
    msg = {"text": "https://www.facebook.com/share/r/17RQxbYP2j/\nKya yeh sach hai?"}
    assert B.classify_message(msg)[0] == "text"        # the rule of the test above


def test_anonymous_admins_and_channel_posts_are_their_chat_not_a_shared_account():
    """REPRODUCED (review R13): Telegram fills `from` with ONE placeholder for
    every anonymous group admin (1087968824) and every "post as a channel"
    sender (136817688), and names the real sender in `sender_chat` — so
    they all shared one allowance, and one could use it up for the rest."""
    anon = {"chat": {"id": -100111}, "from": {"id": 1087968824},
            "sender_chat": {"id": -100111}}
    as_channel = {"chat": {"id": -100222}, "from": {"id": 136817688},
                  "sender_chat": {"id": -100999}}
    assert B.subject_of_message(anon) == "tgchat:-100111"
    assert B.subject_of_message(as_channel) == "tgchat:-100999"
    person = {"chat": {"id": 7}, "from": {"id": 4242}}
    assert B.subject_of_message(person) == "tg:4242"


# -- step 5 of the launch: AI on every answer, /privacy, /delete (2026-10-16) --
# policy-legal.md as its verification corrected it: Anthropic's Usage Policy
# wants the AI disclosed at the start of each chat SESSION, and a Telegram
# chat never starts a new one; Telegram's bot terms want an easily reached
# privacy policy and deletion on request.

def test_help_says_an_ai_answers_who_it_is_for_and_where_data_goes():
    assert "AI" in B.HELP and "Claude" in B.HELP
    assert "18" in B.HELP
    assert "/privacy" in B.HELP


def test_every_answer_says_an_ai_wrote_it():
    assert B.AI_TAG in B.format_reply(_answer())


def test_the_ai_line_survives_an_answer_too_long_for_one_message():
    paragraphs = ["Ek lamba paragraph. " * 30] * 40
    reply = B.format_reply(_answer(sections=[{"tier": "trusted",
                                              "markdown": "\n\n".join(paragraphs)}]))
    assert "paragraph — poora jawab web page par" in reply    # some were dropped
    assert B.AI_TAG in reply and len(reply) <= B._TG_HARD_LIMIT


@pytest.mark.parametrize("text,kind", [("/privacy", "privacy"),
                                       ("/privacy@SomeVerifierBot", "privacy"),
                                       ("/delete", "delete"), ("/DELETE", "delete")])
def test_privacy_and_delete_are_commands(text, kind):
    assert B.classify_message({"text": text})[0] == kind


@pytest.mark.parametrize("text", ["/privacyx", "/deleted it", "/delete_all"])
def test_lookalikes_are_not_those_commands(text):
    assert B.classify_message({"text": text})[0] not in ("privacy", "delete")


def test_privacy_answers_at_once_with_the_notice_and_costs_nothing(monkeypatch):
    monkeypatch.setattr(settings, "public_hosts", ".trycloudflare.com,verifier.example.com")
    monkeypatch.setattr(settings, "answer_retention_days", 45)
    app, tg, pending = StubApp(), StubTG(), {7: "old-job"}      # even mid-check
    _handle(_msg(7, "/privacy"), app, tg, pending)
    [(chat, text)] = tg.sent
    assert chat == 7 and app.submissions == [] and pending == {7: "old-job"}
    # The first name that IS a host: ".trycloudflare.com" names none.
    assert "https://verifier.example.com/privacy" in text
    for who in ("Anthropic", "Google", "Sarvam", "Claude"):
        assert who in text
    assert "45 din" in text and "18" in text and "/delete" in text


def test_the_bot_promises_only_what_is_ours_and_what_sarvam_confirmed(monkeypatch):
    """REPRODUCED by re-check F-12: S5-4 and S5-14 corrected the web notice
    only. The bot is public already, its text is the whole notice until a
    public address exists, and it still said the message "is deleted after
    30 days" — while Sarvam keeps voice notes on its own terms until the
    owner's dashboard change, and Anthropic may keep flagged content."""
    monkeypatch.setattr(settings, "sarvam_zero_retention", False)
    for text in (B.privacy_text(), B.delete_text()):
        assert "apni copy" in text, "says the deletion covers everyone's copy"
    assert "apne niyamon" in B.privacy_text() and "kuch bhi na rakhne" not in B.privacy_text()
    monkeypatch.setattr(settings, "sarvam_zero_retention", True)
    assert "kuch bhi na rakhne" in B.privacy_text()


def test_privacy_without_a_public_name_still_explains(monkeypatch):
    monkeypatch.setattr(settings, "public_hosts", "")
    app, tg = StubApp(), StubTG()
    _handle(_msg(7, "/privacy"), app, tg)
    assert "Anthropic" in tg.sent[0][1] and "https://" not in tg.sent[0][1]


def test_delete_says_how_and_gives_the_contact(monkeypatch):
    monkeypatch.setattr(settings, "contact_email", "owner@example.com")
    monkeypatch.setattr(settings, "answer_retention_days", 45)
    app, tg, pending = StubApp(), StubTG(), {7: "old-job"}
    _handle(_msg(7, "/delete"), app, tg, pending)
    [(chat, text)] = tg.sent
    assert "owner@example.com" in text and "45 din" in text
    assert app.submissions == [] and pending == {7: "old-job"}


def test_delete_without_a_contact_says_there_is_none_yet():
    """Not "one comes before the service goes public": the bot is public
    already (review S5-9)."""
    app, tg = StubApp(), StubTG()
    _handle(_msg(7, "/delete"), app, tg)
    assert "@" not in tg.sent[0][1] and "diya nahi gaya" in tg.sent[0][1]


def test_what_settings_say_is_escaped_in_the_chat(monkeypatch):
    """The bot sends HTML: markup in a setting would break the message."""
    monkeypatch.setattr(settings, "contact_email", "a<b>@example.com")
    app, tg = StubApp(), StubTG()
    _handle(_msg(7, "/delete"), app, tg)
    assert "a&lt;b&gt;@example.com" in tg.sent[0][1]


@pytest.mark.parametrize("first", [
    _msg(7, "/help"), _msg(7, "/id"), _msg(7, "/privacy"), _msg(7, "/delete"),
    _msg(7, "Hi"),                                              # small talk
    {"chat": {"id": 7}, "sticker": {"file_id": "s1"}},          # unsupported
    {"chat": {"id": 7}, "voice": {"file_id": "v1", "file_size": 21 * 1024 * 1024}},
], ids=["help", "id", "privacy", "delete", "smalltalk", "sticker", "too_big"])
def test_a_message_never_submitted_never_makes_the_next_look_mid_check(first):
    """FOUND 2026-10-16: the dispatcher counted every message but /help as
    work in flight, so "/id" and a claim arriving together made the claim
    look sent mid-check — never checked, and the person told so. bb623ae
    fixed the commands; REPRODUCED by review S5-5, the rule still failed for
    "Hi", a sticker or a too-big file: "Hi" then a forward is the most
    ordinary first exchange there is."""
    async def scenario():
        app, tg = StubApp(), StubTG()
        bot = B.Dispatcher(app, tg)
        bot.dispatch(first)
        bot.dispatch(_msg(7, "WHO ne kaha 5G se corona"))
        await bot.drain()
        return app

    app = asyncio.run(scenario())
    assert app.submissions == [("text", {"text": "WHO ne kaha 5G se corona"})]


@pytest.mark.parametrize("text,kind", [
    ("/privacy?", "privacy"), ("/privacy.", "privacy"), ("/delete?", "delete"),
    ("/help me", "help"), ("/start", "help"),
    ("/stop.", "help"), ("/stop!", "help"), ("/settings?", "help"),
    ("/cancel please", "help"), ("/stop it", "help"),
    ("/startup India scheme har yuva ko Rs 10 lakh", "text"),
    ("/helpline 1930 ab band ho gayi hai", "text"),
])
def test_commands_are_read_by_the_token_never_by_a_prefix(text, kind):
    """REPRODUCED by review S5-13: "/privacy?" and "/stop." were PAID checks
    (the unknown-command rule wanted an exact bare token), and the old
    prefix test turned claims beginning "/startup…" or "/helpline…" into
    the help text, unchecked. A command with at most two words after it is
    a command; more words make it a claim."""
    assert B.classify_message({"text": text})[0] == kind


def test_a_command_from_a_chat_with_a_waiting_answer_hands_it_over():
    """REPRODUCED by review S5-6: told "send me any message and I'll show
    that report", a person sending "/status" got the help text, and the
    answer stayed undelivered — before bb623ae it was the poke."""
    app, tg, pending, prompted = StubApp(), StubTG(), {7: "job1"}, {7}
    _handle(_msg(7, "/status"), app, tg, pending, prompted)
    assert pending == {} and app.submissions == []
    assert any("This is false." in text for _, text in tg.sent)


def test_small_talk_mid_check_always_gets_its_own_reply():
    """FOUND by the interleaving explorer (2026-10-16; in 13 of 300 seeds
    before step 5 too): "hi" sent mid-check, whose answer another of the
    chat's handlers delivered while "hi" looked, got no reply at all."""
    pending = {7: "job1"}

    class DeliveredMeanwhile(StubApp):
        async def wait_for_report(self, job_id, attempts=None):
            pending.pop(7, None)              # the first handler handed it over
            return self.report

    app, tg = DeliveredMeanwhile(), StubTG()
    _handle(_msg(7, "hi"), app, tg, pending)
    assert tg.sent and tg.sent[-1][1] == B._SMALLTALK_REPLY


def test_a_chat_is_forgotten_by_the_bot_once_nothing_is_running():
    """REPRODUCED by review S5-2: the per-chat lock table kept every chat id
    the bot ever handled, for the life of the process — the rule 60beff7
    applied to the limiter, missed here."""
    async def scenario():
        app, tg = StubApp(), StubTG()
        bot = B.Dispatcher(app, tg)
        bot.dispatch(_msg(4242, "WHO ne kaha 5G se corona"))
        await bot.drain()
        return bot

    bot = asyncio.run(scenario())
    assert (bot.locks, bot.in_flight, bot.pending, bot.prompted) == ({}, {}, {}, set())


def test_a_pending_check_is_forgotten_after_a_day_while_the_bot_runs(tmp_path, monkeypatch):
    """REPRODUCED by review S5-1: the day's limit was applied only when the
    file was LOADED, so in a bot that stays up, an undelivered entry — a
    chat id, and a job id that opens its message — stayed on disk for
    weeks; the privacy notice says at most a day."""
    clock = [1_000_000.0]
    monkeypatch.setattr(B.PendingStore, "_clock", staticmethod(lambda: clock[0]))
    path = tmp_path / "pending.json"
    store = B.PendingStore(str(path))
    store[777] = "job1"                       # its wait gave up; nobody pokes
    clock[0] += B.PendingStore._TTL_S + 1
    store[888] = "job2"                       # the next write of anyone's
    assert 777 not in store and "777" not in json.loads(path.read_text())
    clock[0] += B.PendingStore._TTL_S + 1
    # And with no write at all — reporting 777 too, which 888's write
    # dropped: the caller lets go of every one (re-check F-2).
    assert store.expire() == [777, 888]
    assert json.loads(path.read_text()) == {}


def test_the_dispatcher_lets_go_of_a_chat_whose_entry_expired(tmp_path, monkeypatch):
    clock = [1_000_000.0]
    monkeypatch.setattr(B.PendingStore, "_clock", staticmethod(lambda: clock[0]))
    bot = B.Dispatcher(StubApp(), StubTG(), pending_path=str(tmp_path / "p.json"))
    bot.pending[777] = "job1"
    bot.prompted.add(777)
    clock[0] += B.PendingStore._TTL_S + 1
    bot.tidy()
    assert 777 not in bot.pending and 777 not in bot.prompted


def test_a_chat_dropped_during_another_chats_write_is_still_let_go(tmp_path, monkeypatch):
    """REPRODUCED by re-check F-2: an entry past its day was dropped by the
    NEXT write of any chat, which threw the list away — so tidy() found
    nothing to report, and the chat's "prompted" mark (its Telegram id)
    stayed in memory for the life of the process."""
    clock = [1_000_000.0]
    monkeypatch.setattr(B.PendingStore, "_clock", staticmethod(lambda: clock[0]))
    bot = B.Dispatcher(StubApp(), StubTG(), pending_path=str(tmp_path / "p.json"))
    bot.pending[777] = "job1"
    bot.prompted.add(777)
    clock[0] += B.PendingStore._TTL_S + 1
    bot.pending[888] = "job2"                 # another chat writes first
    bot.tidy()
    assert 777 not in bot.prompted


def test_a_chat_dropped_by_any_write_is_let_go_at_once(tmp_path, monkeypatch):
    """Found by the restarts explorer once F-2's fix was in (10 of 2,000
    seeds): between another chat's write dropping an entry and the next
    tidy() — one long poll, up to ~50 s — the chat's mark outlived its day.
    The store now says so the moment it drops one."""
    clock = [1_000_000.0]
    monkeypatch.setattr(B.PendingStore, "_clock", staticmethod(lambda: clock[0]))
    bot = B.Dispatcher(StubApp(), StubTG(), pending_path=str(tmp_path / "p.json"))
    bot.pending[777] = "job1"
    bot.prompted.add(777)
    clock[0] += B.PendingStore._TTL_S + 1
    bot.pending[888] = "job2"                 # no tidy() at all
    assert 777 not in bot.prompted


def _refusing_replace(monkeypatch, times):
    """os.replace refused `times` times, as Windows did (review G-8: "access
    denied" swapping onto a file written a moment ago — 12 of 60 writes half
    a second apart, in this project's folder); then the real one. times=None
    refuses until `state["refuse"]` is set False."""
    real, state = os.replace, {"left": times, "refuse": True}

    def replace(src, dst):
        if state["left"] is None:
            refuse = state["refuse"]
        else:
            refuse = state["left"] > 0
            if refuse:
                state["left"] -= 1
        if refuse:
            raise PermissionError(13, "Access is denied")
        return real(src, dst)

    monkeypatch.setattr(os, "replace", replace)
    return state


def test_a_pending_save_windows_refuses_for_a_moment_still_lands(tmp_path, monkeypatch):
    """REPRODUCED by review G-8 (the restarts explorer's I10 on HEAD): the
    one refused swap was printed and dropped, so the file kept the previous
    state — a restart then re-delivered an answer already sent, or lost a
    check just submitted."""
    path = tmp_path / "pending.json"
    store = B.PendingStore(str(path))
    _refusing_replace(monkeypatch, 2)
    store[7] = "job1"
    assert json.loads(path.read_text())["7"]["job"] == "job1"


def test_a_pending_save_that_never_landed_is_written_at_the_next_tidy(tmp_path, monkeypatch):
    """G-8's rule: the file must come back to what memory says, not wait for
    some chat's next write — a quiet bot may not write again for hours."""
    path = tmp_path / "p.json"
    bot = B.Dispatcher(StubApp(), StubTG(), pending_path=str(path))
    state = _refusing_replace(monkeypatch, None)
    bot.pending[7] = "job1"
    assert "7" not in json.loads(path.read_text())    # refused throughout
    state["refuse"] = False
    bot.tidy()                                        # each long poll
    assert json.loads(path.read_text())["7"]["job"] == "job1"


def test_a_message_during_a_restarts_hand_over_is_not_checked(tmp_path):
    """REPRODUCED by re-check F-6 (its extended explorer: 10 of 6,000 seeds):
    after a restart the bot handed the previous answer over outside the
    chat's lock and its in-flight count, so a message arriving during the
    hand-over looked like a fresh start, and was checked and paid for."""
    async def scenario():
        app = StubApp()
        gate, sending = asyncio.Event(), asyncio.Event()

        class GatedTG(StubTG):
            async def send(self, chat_id, text):
                if text == B._DONE_EARLIER:
                    sending.set()
                    await gate.wait()         # the hand-over, mid-send
                return await super().send(chat_id, text)

        bot = B.Dispatcher(app, GatedTG(), pending_path=str(tmp_path / "p.json"))
        bot.pending[7] = "job1"               # what the previous run waited for
        await bot.resume()
        await asyncio.wait_for(sending.wait(), 5)
        bot.dispatch(_msg(7, "WHO ne kaha 5G se corona"))
        gate.set()
        await asyncio.wait_for(bot.drain(), 10)
        return app

    app = asyncio.run(scenario())
    assert app.submissions == [], "a message during the hand-over was paid for"


def test_a_second_bot_refuses_to_start(tmp_path, monkeypatch):
    """Re-check F-9: Telegram allows one poller, and two bots split every
    chat's burst between them and rewrite one pending file from two
    memories. start.cmd found the unattended runner's bot by its command
    line, which Windows hides when another account runs it."""
    import subprocess
    import sys

    monkeypatch.setattr(settings, "db_path", str(tmp_path / "data" / "verifier.db"))
    (tmp_path / "data").mkdir()
    holder = subprocess.Popen(
        [sys.executable, "-c",
         "import sys, time; sys.path.insert(0, sys.argv[1]);"
         "from app.store import instance; instance.acquire(sys.argv[2]);"
         "print('held', flush=True); time.sleep(60)",
         str(B.ROOT) if hasattr(B, "ROOT") else ".", B.bot_lock_path()],
        stdout=subprocess.PIPE, text=True, cwd=os.path.dirname(os.path.dirname(
            os.path.abspath(B.__file__))))
    try:
        assert holder.stdout.readline().strip() == "held"
        assert B.take_the_bot_lock() is False
    finally:
        holder.kill()
        holder.wait(10)


def test_a_public_bot_without_a_contact_says_so(monkeypatch):
    """REPRODUCED by review S5-9: the bot answers anyone already, but the
    missing-contact warning was keyed to the web's PUBLIC_HOSTS, and
    /delete promised a contact "before the service goes public"."""
    monkeypatch.setattr(settings, "contact_email", "")
    assert any("CONTACT_EMAIL" in w for w in B.startup_warnings())
    text = B.delete_text()
    assert "public hone se pehle" not in text and "diya nahi gaya" in text
    monkeypatch.setattr(settings, "contact_email", "owner@example.com")
    monkeypatch.setattr(settings, "sarvam_zero_retention", True)
    assert B.startup_warnings() == []


@pytest.mark.parametrize("text", ["/stop", "/settings", "/cancel@SomeVerifierBot", "/privacyx"])
def test_a_bare_unknown_command_gets_help_never_a_paid_check(text):
    """MEASURED 2026-10-16: "/privacy" reached the API as a paid text check
    before the bot knew the command — and so does any command it does not
    know, since one word passes the small-talk triage as a "claim"."""
    app, tg = StubApp(), StubTG()
    _handle(_msg(7, text), app, tg)
    assert app.submissions == []
    assert "Information Verifier" in tg.sent[0][1]


def test_a_claim_that_starts_with_a_slash_is_still_checked():
    assert B.classify_message({"text": "/5G se corona phailta hai, sach?"})[0] == "text"
