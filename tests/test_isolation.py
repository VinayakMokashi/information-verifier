"""The test suite never touches the real database. Free.

MEASURED 2026-09-29: two real checks were paid for in the morning, and by
noon the persisted daily counter read 0 — every run of this free suite had
handed one slot back on the REAL database. The burst test cancels 25 claims
while a write lock is held; each one finishes later on the limiter's own
pool and refunds its slot, after the test's patches were undone, so the
refund read the real `db_path` and a limiter switched back on. Reproduced
with the suite pointed at a canary database: 2 -> 1 per run.

The rule is wider than that one test: anything that runs after a test's
patches are undone falls back to whatever `settings.db_path` held before
them. So what it held must never be the real database.
"""
import os
import subprocess
import sys
from pathlib import Path

from app.config import Settings, settings

ROOT = Path(__file__).resolve().parent.parent


# Compared as plain strings, outside the assert: pytest's failure display
# introspects the objects in an assert, and a Settings repr carries the API
# keys (it printed one on this test's first, deliberately failing, run).
def _paths() -> tuple[str, str]:
    in_use = os.path.abspath(str(settings.db_path))
    # The real one is what the owner's .env names, read on purpose: the
    # suite itself reads no .env (the test below).
    real = os.path.abspath(str(Settings(_env_file=".env").db_path))
    return in_use, real


def test_the_suite_reads_nothing_from_the_owners_env_file(tmp_path):
    """FOUND 2026-10-27, before raising the caps through .env: conftest
    overrode the keys and six settings, and every other line of the owner's
    .env reached the suite. BACKUP_DIR would have put the backup tests'
    copies in his OneDrive folder, and a raised DAILY_BUDGET_USD would fail
    every test that pins the defaults. A planted .env, read the way the
    suite's own environment reads one — in a child, from that folder."""
    (tmp_path / ".env").write_text("DAILY_BUDGET_USD=9\nBACKUP_DIR=planted-backups\n",
                                   encoding="utf-8")
    code = "from app.config import settings as s; print(s.daily_budget_usd, repr(s.backup_dir))"
    out = subprocess.run([sys.executable, "-c", code], cwd=tmp_path, capture_output=True,
                         text=True, timeout=60, env=dict(os.environ, PYTHONPATH=str(ROOT)))
    assert out.stdout.split() == ["1.0", "''"], out.stdout + out.stderr[-500:]


def test_a_test_that_patches_nothing_is_not_on_the_real_database():
    in_use, real = _paths()
    assert in_use != real


_DUMMY_KEY = "test-not-a-real-key"
_KEY_FIELDS = ("anthropic_api_key", "google_factcheck_api_key", "sarvam_api_key",
               "hf_token", "telegram_bot_token")


def test_the_suite_never_holds_a_real_key():
    """MEASURED 2026-10-16: the suite ran with the real keys from .env
    loaded. Eight link and voice tests passed only because a real Sarvam key
    was there (on a copy without .env they failed), and a seam some test
    forgot to fake would have reached a provider with a key it bills.
    tests/conftest.py sets a dummy before the app is imported. Only field
    NAMES are compared in the assert, never a value."""
    real = [name for name in _KEY_FIELDS if getattr(settings, name) != _DUMMY_KEY]
    assert real == []
    # Turnstile stays OFF (empty): configured, it would demand a token for
    # every paid check and ask Cloudflare. Names only, never a value.
    loaded = [name for name in ("turnstile_site_key", "turnstile_secret_key")
              if getattr(settings, name)]
    assert loaded == []


def test_undoing_a_patch_does_not_restore_the_real_database(monkeypatch):
    """Exactly the leak's path: a fixture patches db_path, the test ends,
    the patch is undone, and late work reads what is left."""
    monkeypatch.setattr(settings, "db_path", "somewhere/else.db")
    monkeypatch.undo()
    in_use, real = _paths()
    assert in_use != real
