"""The privacy notice and the terms: served, linked, and true to the code. Free.

Step 5 of the launch (docs/research/2026-10-15/decision-brief.md §6; the
drafting rules are policy-legal.md's recommendation as its verification
corrected it). Needed before any public URL: a privacy notice (Google's API
terms and Telegram's bot terms want one today, India's DPDP Rules from 13 May
2027), terms that say an answer is AI-written and must be checked against its
sources (Anthropic's Commercial Terms D.3), an AI line on every surface
(Anthropic's Usage Policy) and an 18+ line beside the button.

What a notice SAYS must stay true of what the code DOES, so the periods in it
come from the settings the deleting code reads — and these tests move those
settings to prove the page follows.
"""
import re
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

import app.main as M
from app.config import settings

PAGE = (Path(__file__).resolve().parent.parent / "static" / "index.html"
        ).read_text(encoding="utf-8")


@pytest.fixture()
def contact(monkeypatch):
    monkeypatch.setattr(settings, "contact_email", "owner@example.com")
    monkeypatch.setattr(settings, "operator_name", "A. Owner")


def _read(client, path: str) -> str:
    """The page as a reader meets it: the HTML wraps sentences across lines."""
    resp = client.get(path)
    assert resp.status_code == 200
    return " ".join(resp.text.split())


@pytest.mark.parametrize("path", ["/privacy", "/terms"])
def test_both_pages_are_served_as_html(client, path):
    resp = client.get(path)
    assert resp.status_code == 200
    assert resp.headers["content-type"].startswith("text/html")
    # A marker the renderer does not know would reach the reader verbatim.
    assert "{{" not in resp.text and "}}" not in resp.text


@pytest.mark.parametrize("path", ["/privacy", "/terms"])
def test_each_page_links_home_and_to_the_other(client, path):
    text = _read(client, path)
    assert 'href="./"' in text
    other = "terms" if path == "/privacy" else "privacy"
    assert f'href="{other}"' in text


def test_the_notice_names_everyone_who_receives_what_people_send(client):
    """Google's API terms §3(d): the policy must say what is shared with whom;
    the verification of policy-legal.md adds that naming every recipient is
    also the answer to IT Act s.72A, which stays in force."""
    text = _read(client, "/privacy")
    for recipient in ("Anthropic", "Google", "Sarvam", "Cloudflare", "Telegram",
                      "Instagram", "YouTube", "Facebook"):
        assert recipient in text, recipient


def test_the_notice_says_a_linked_posts_pictures_are_fetched_read_and_kept(client):
    """Since 2026-11-18 a linked post's pictures are fetched from the
    platform, read by Claude, and their text is kept with the post's caption
    and words (the transcript cache). The notice said only "caption and
    sound" (found 2026-11-19)."""
    text = _read(client, "/privacy")
    assert "to read its caption, pictures and sound" in text        # the fetch
    assert "and in a linked post's pictures" in text                # what Claude reads
    assert "its caption, words and the text in its pictures" in text  # what is kept


def test_the_notice_states_the_retention_the_code_applies(client, monkeypatch):
    monkeypatch.setattr(settings, "answer_retention_days", 45)
    monkeypatch.setattr(settings, "answer_cache_ttl_trusted_h", 96)
    monkeypatch.setattr(settings, "answer_cache_ttl_web_h", 24)
    monkeypatch.setattr(settings, "transcript_cache_ttl_days", 12)
    text = _read(client, "/privacy")
    assert re.search(r"\b45 days\b", text)
    # The answer cache is pruned at its LONGER lifetime (AnswerCache.prune).
    assert re.search(r"\b4 days\b", text)
    assert re.search(r"\b12 days\b", text)
    # Anthropic's own deletion period is the one fixed period the notice may
    # state; any other "30 days" left here is a hard-coded copy of ours.
    assert "30 days" not in text.replace("within 30 days", "")


def test_a_lifetime_in_hours_is_not_rounded_into_days(client, monkeypatch):
    monkeypatch.setattr(settings, "answer_cache_ttl_trusted_h", 36)
    monkeypatch.setattr(settings, "answer_cache_ttl_web_h", 24)
    assert re.search(r"\b36 hours\b", _read(client, "/privacy"))


def test_the_notice_is_for_adults_and_says_where_to_complain(client):
    text = _read(client, "/privacy")
    assert "18" in text
    # The Board exists, but complaints open only on 13 May 2027 (DPDP ss.13
    # and 27): the verification corrected an unqualified "right to complain".
    assert "Data Protection Board" in text and "13 May 2027" in text


def test_the_notice_claims_no_more_than_the_code_does(client):
    """Review S5-14: the "In short" box — what most readers read — promised
    deletion after 30 days everywhere, while Anthropic, Sarvam and Telegram
    keep their own copies on their own terms; and "the counts behind the
    daily limits ... only in memory" while the deployment's day count and
    budget are on disk (holding no one's data). Say exactly what is ours."""
    text = _read(client, "/privacy")
    assert "We delete our copy after" in text and "keep theirs" in text
    assert "The per-person counts behind the daily limits" in text


def test_the_notice_says_who_can_open_an_answer(client):
    """GET /reports/{job_id} is open to whoever has the id, and the page puts
    it in the address bar — so a shared address shares the message."""
    assert "#job=" in _read(client, "/privacy")


def test_the_terms_say_ai_wrote_it_and_to_check_the_sources(client):
    text = _read(client, "/terms")
    # "written by an AI", unnamed (Vinayak, 2026-10-24); who receives the
    # message, Anthropic among them, is the privacy notice's to say.
    assert "Every answer is written by an AI" in text
    # D.3 is about relying on FACTUAL assertions without checking them —
    # for a fact-checker "can be wrong" alone is the weaker half.
    assert "checking the linked sources yourself" in text
    assert "not medical, legal or financial advice" in text
    assert "18" in text
    assert "laws of India" in text


@pytest.mark.parametrize("path", ["/privacy", "/terms"])
def test_the_contact_comes_from_settings_as_a_mail_link(client, contact, path):
    assert 'href="mailto:owner@example.com"' in _read(client, path)


@pytest.mark.parametrize("path", ["/privacy", "/terms"])
def test_the_operator_is_named_from_settings(client, contact, path):
    assert "A. Owner" in _read(client, path)


def test_what_settings_say_is_escaped_never_markup(client, monkeypatch):
    monkeypatch.setattr(settings, "operator_name", "<script>alert(1)</script>")
    monkeypatch.setattr(settings, "contact_email", 'x"><img src=y>@example.com')
    text = _read(client, "/privacy")
    assert "<script>alert(1)" not in text
    assert "<img src=y>" not in text
    assert "&lt;script&gt;" in text


def test_a_setting_is_filled_in_once_never_filled_in_again(client, monkeypatch):
    """One pass over the page: a value that happens to contain a marker is
    text, not a second template."""
    monkeypatch.setattr(settings, "operator_name", "{{contact}}")
    monkeypatch.setattr(settings, "contact_email", "owner@example.com")
    text = client.get("/privacy").text
    assert "run by {{contact}} in India" in " ".join(text.split())


@pytest.mark.parametrize("path", ["/privacy", "/terms"])
def test_without_a_contact_the_page_says_one_is_coming(client, path):
    """Unset is the state of every machine until the owner decides what to
    publish (conftest pins it empty)."""
    text = _read(client, path)
    assert "mailto:" not in text
    assert "before the service opens to the public" in text


def test_going_public_without_a_contact_is_warned(monkeypatch):
    monkeypatch.setattr(settings, "public_hosts", "verifier.example.com")
    monkeypatch.setattr(settings, "contact_email", "")
    assert any("CONTACT_EMAIL" in w for w in M._going_live_warnings())
    monkeypatch.setattr(settings, "contact_email", "owner@example.com")
    assert not any("CONTACT_EMAIL" in w for w in M._going_live_warnings())


def test_the_notice_never_claims_a_sarvam_setting_nobody_confirmed(client, monkeypatch):
    """REPRODUCED by review S5-4: the notice said "Our Sarvam account is set
    to keep none of it" while HANDOFF still listed setting it as an owner
    action — and Sarvam keeps everything until an owner sets a period. The
    sentence now follows a switch the owner throws after doing it."""
    monkeypatch.setattr(settings, "sarvam_zero_retention", False)
    text = _read(client, "/privacy")
    assert "keep none of it" not in text and "under its own terms" in text
    monkeypatch.setattr(settings, "sarvam_zero_retention", True)
    text = _read(client, "/privacy")
    assert "Our Sarvam account is set to keep none of it" in text
    assert "under its own terms" not in text


def test_going_public_before_sarvam_keeps_nothing_is_warned(monkeypatch):
    monkeypatch.setattr(settings, "public_hosts", "verifier.example.com")
    monkeypatch.setattr(settings, "contact_email", "owner@example.com")
    monkeypatch.setattr(settings, "sarvam_zero_retention", False)
    assert any("SARVAM_ZERO_RETENTION" in w for w in M._going_live_warnings())
    monkeypatch.setattr(settings, "sarvam_zero_retention", True)
    assert not any("SARVAM_ZERO_RETENTION" in w for w in M._going_live_warnings())


def test_going_public_without_turnstile_is_warned(monkeypatch):
    monkeypatch.setattr(settings, "public_hosts", "verifier.example.com")
    monkeypatch.setattr(settings, "turnstile_site_key", "")
    monkeypatch.setattr(settings, "turnstile_secret_key", "")
    assert any("Turnstile" in w for w in M._going_live_warnings())


def test_this_machine_alone_is_not_warned(monkeypatch):
    monkeypatch.setattr(settings, "public_hosts", "")
    monkeypatch.setattr(settings, "contact_email", "")
    assert M._going_live_warnings() == []


def test_startup_prints_the_going_live_warnings(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(settings, "db_path", str(tmp_path / "startup.db"))
    monkeypatch.setattr(M, "_going_live_warnings", lambda: ["[startup] NOTICE-SENTINEL"])
    with TestClient(M.app):
        pass
    assert "NOTICE-SENTINEL" in capsys.readouterr().out


# -- the chat page ------------------------------------------------------------

def _hint() -> str:
    start = PAGE.index('<p class="hint">')
    return PAGE[start:PAGE.index("</p>", start)]


def test_the_page_links_both_pages_beside_the_button():
    assert 'href="privacy"' in _hint() and 'href="terms"' in _hint()


def test_the_page_says_an_ai_answers_and_who_it_is_for():
    """Anthropic's Usage Policy: a consumer-facing chatbot discloses it is AI,
    at the latest at the start of each session — the line is always on
    screen. 18+: DPDP s.9 and Anthropic's minors rule (policy-legal.md)."""
    assert "AI" in _hint()
    assert "18" in _hint()


def test_every_disclaimer_says_ai_and_none_names_the_model(client):
    """Vinayak, 2026-10-24: "written by AI", not "written by AI (Claude)".
    The policy asks only that people know they are "interacting with AI
    rather than a human" (policy-legal.verification.md); the privacy
    notice still names Anthropic, because that is where messages go."""
    from scripts import telegram_bot as B

    terms = _read(client, "/terms")
    terms = terms[terms.index("Answers are written by AI"):][:400]
    for where, text in (("the page", _hint()), ("the bot's /start", B.HELP),
                        ("the bot's answer tag", B.AI_TAG), ("the terms", terms)):
        assert "AI" in text, where
        assert "Claude" not in text, where


def test_every_answer_is_tagged_as_ai_written():
    """A screenshot of one answer travels without the page around it."""
    foot = PAGE[PAGE.index("function drawFooter("):PAGE.index("// -- transport")]
    assert "AI-written" in foot


def test_the_public_address_is_the_first_name_that_is_a_host(monkeypatch):
    """What the bot's /privacy links to. A ".example.com" entry allows a
    family of names (main._our_host) but names no one host to link."""
    from app.api.legal import public_url

    monkeypatch.setattr(settings, "public_hosts", " .trycloudflare.com , Verifier.Example.com. ")
    assert public_url("privacy") == "https://verifier.example.com/privacy"
    monkeypatch.setattr(settings, "public_hosts", ".trycloudflare.com")
    assert public_url("privacy") is None
