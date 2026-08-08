"""The Telegram bot, fully offline. Free — no Telegram, no app, no network.

The loop is a thin shell; everything decision-shaped is a pure function or
takes duck-typed clients. What these pin: message classification agrees with
the server's own link gate, replies prefer the reader's language and never
blow Telegram's length cap, and every failure becomes words in the chat.
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

def _report(**kw):
    base = {
        "status": "COMPLETE",
        "overall_rating": "FALSE",
        "summary": "1 claim(s) checked. Overall rating: FALSE.",
        "source_text": None,
        "claim_verdicts": [{
            "claim": {"text": "5G spreads coronavirus."},
            "verdict": {"rating": "FALSE", "confidence": 97,
                        "reasoning": "Trusted sources say it is false.",
                        "correction": "Corona spreads by droplets.",
                        "citations": [{"url": "https://altnews.in/x",
                                       "title": "No link", "publisher": "AltNews"}]},
        }],
        "localized": None,
    }
    base.update(kw)
    return base


def test_reply_prefers_the_readers_language():
    report = _report(localized={
        "language": "hi",
        "summary": "1 दावे की जांच की गई। नतीजा: गलत।",
        "claims": [{"claim": "5जी से कोरोना फैलता है।",
                    "reasoning": "भरोसेमंद स्रोत कहते हैं कि यह गलत है।",
                    "correction": "कोरोना बूंदों से फैलता है।"}],
    })
    reply = B.format_reply(report)
    assert "दावे की जांच" in reply
    assert "5जी से कोरोना" in reply
    assert "भरोसेमंद स्रोत" in reply
    # Citations remain English receipts either way.
    assert "AltNews" in reply and "https://altnews.in/x" in reply


def test_reply_falls_back_to_english_per_claim():
    report = _report(localized={"language": "hi", "summary": "सारांश",
                                "claims": [None]})
    reply = B.format_reply(report)
    assert "5G spreads coronavirus." in reply
    assert "Trusted sources say" in reply


def test_the_badge_and_heard_text_are_present():
    reply = B.format_reply(_report(source_text="WHO ne kaha 5G se corona"))
    assert "❌ FALSE" in reply
    assert "Humne yeh suna/padha" in reply
    assert "WHO ne kaha" in reply


def test_failed_reports_become_words():
    reply = B.format_reply({"status": "FAILED", "error": "The transcription "
                            "service is unavailable right now."})
    assert "Check nahi ho paya" in reply
    assert "transcription service" in reply


def test_html_in_content_is_escaped():
    report = _report()
    report["claim_verdicts"][0]["claim"]["text"] = "<script>alert(1)</script>"
    reply = B.format_reply(report)
    assert "<script>" not in reply
    assert "&lt;script&gt;" in reply


def test_a_long_report_drops_whole_claims_never_mid_sentence():
    many = [{
        "claim": {"text": f"Claim number {i} " + "x" * 400},
        "verdict": {"rating": "UNVERIFIED", "confidence": 0,
                    "reasoning": "y" * 400, "correction": "", "citations": []},
    } for i in range(12)]
    reply = B.format_reply(_report(claim_verdicts=many))
    assert len(reply) <= B._TG_HARD_LIMIT
    assert "aur" in reply and "claim(s)" in reply     # the drop is disclosed


# -- one message end to end (stub clients) ------------------------------------

class StubApp:
    def __init__(self, report=None, reject=None):
        self.report = report or _report()
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

    async def wait_for_report(self, job_id):
        return self.report


class StubTG:
    def __init__(self):
        self.sent = []

    async def send(self, chat_id, text):
        self.sent.append((chat_id, text))

    async def file_bytes(self, file_id):
        return b"OggS-fake", "voice/file_77.oga"


def _handle(msg, app, tg):
    asyncio.run(B.handle_message(msg, app, tg))


def test_text_flow_submits_polls_and_replies():
    app, tg = StubApp(), StubTG()
    _handle({"chat": {"id": 7}, "text": "WHO ne kaha 5G se corona"}, app, tg)

    assert app.submissions == [("text", {"text": "WHO ne kaha 5G se corona"})]
    assert len(tg.sent) == 2                      # ack + reply
    assert "Checking" in tg.sent[0][1]
    assert "❌ FALSE" in tg.sent[1][1]


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
