"""The Telegram bot, fully offline. Free — no Telegram, no app, no network.

The loop is a thin shell; everything decision-shaped is a pure function or
takes duck-typed clients. What these pin: message classification agrees with
the server's own link gate, an Answer becomes a message that Telegram will
actually accept, prose can never smuggle a link past the sources block, and
every failure becomes words in the chat.
"""
import asyncio

import pytest

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

    async def submit_json(self, endpoint, payload):
        self.submissions.append((endpoint, payload))
        if self.reject:
            return None, self.reject
        return "job123", ""

    async def submit_file(self, endpoint, filename, content, content_type):
        self.submissions.append((endpoint, filename, content_type))
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


def _handle(msg, app, tg, pending=None):
    asyncio.run(B.handle_message(msg, app, tg, pending))


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
        async def submit_json(self, endpoint, payload):
            raise RuntimeError("app down")

    app, tg = ExplodingApp(), StubTG()
    _handle({"chat": {"id": 7}, "text": "hello"}, app, tg)
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
    app, tg, pending = _PendingApp(), StubTG(), {}

    _handle({"chat": {"id": 7}, "text": "WHO ne kaha 5G"}, app, tg, pending)
    assert pending == {7: "job123"}              # remembered for next time
    assert "dobara paisa nahi lagega" in tg.sent[-1][1]

    _handle({"chat": {"id": 7}, "text": "kya hua?"}, app, tg, pending)
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

    async def submit_json(self, endpoint, payload):
        await asyncio.sleep(0)                 # a real POST suspends too
        self.submissions.append((endpoint, payload))
        self._n += 1
        job = f"job{self._n}"
        self.done[job], self.release[job] = asyncio.Event(), asyncio.Event()
        return job, ""

    async def wait_for_report(self, job_id, attempts=None):
        if attempts is not None:           # the short "is it done yet?" peek
            return self.report if self.done[job_id].is_set() else None
        await self.release[job_id].wait()
        return self.report

    def finish_all(self):
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


def test_one_failing_message_does_not_stop_the_others():
    class Exploding(StubApp):
        async def submit_json(self, endpoint, payload):
            if payload["text"] == "boom":
                raise RuntimeError("app down")
            return await super().submit_json(endpoint, payload)

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
