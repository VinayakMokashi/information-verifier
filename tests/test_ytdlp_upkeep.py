"""yt-dlp has to keep up with the platforms, and say so when it is falling behind. Free.

docs/research/2026-10-15/audit-ops.md OPS-25: yt-dlp's warnings were thrown
away twice over — `no_warnings: True` stopped them before the logger, whose
warning() did nothing anyway — so the day YouTube stops working without a
JavaScript runtime ("YouTube extraction without a JS runtime has been
deprecated, and some formats may be missing"), nothing would have said why;
and a 24/7 server had no reminder that its yt-dlp was going stale.
"""
from datetime import date

import app.main as M
from app.providers import links


def test_a_ytdlp_warning_is_logged_once_and_without_the_post(monkeypatch, capsys):
    monkeypatch.setattr(links, "_WARNED", set())
    warning = ("[youtube] dQw4w9WgXcQ: YouTube extraction without a JS runtime has "
               "been deprecated, and some formats may be missing")
    for _ in range(3):
        links._Silent().warning(warning)
    out = capsys.readouterr().out
    assert out.count("yt-dlp warning") == 1
    assert "JS runtime" in out and "dQw4w9WgXcQ" not in out


def test_the_resolver_lets_ytdlp_warn():
    opts = links._base_opts()
    assert opts["no_warnings"] is False and isinstance(opts["logger"], links._Silent)


def test_a_stale_ytdlp_is_said_at_startup(monkeypatch):
    monkeypatch.setattr(M, "_ytdlp_released", lambda: date(2026, 8, 19))
    note = M._ytdlp_staleness(today=date(2026, 10, 16))
    assert note and "58 days" in note and "pip install -U yt-dlp" in note
    assert M._ytdlp_staleness(today=date(2026, 9, 1)) is None


def test_an_unreadable_version_never_stops_the_start(monkeypatch):
    monkeypatch.setattr(M, "_ytdlp_released", lambda: None)
    assert M._ytdlp_staleness(today=date(2026, 10, 16)) is None
