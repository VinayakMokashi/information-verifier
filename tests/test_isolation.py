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

from app.config import Settings, settings


# Compared as plain strings, outside the assert: pytest's failure display
# introspects the objects in an assert, and a Settings repr carries the API
# keys (it printed one on this test's first, deliberately failing, run).
def _paths() -> tuple[str, str]:
    in_use = os.path.abspath(str(settings.db_path))
    real = os.path.abspath(str(Settings().db_path))
    return in_use, real


def test_a_test_that_patches_nothing_is_not_on_the_real_database():
    in_use, real = _paths()
    assert in_use != real


def test_undoing_a_patch_does_not_restore_the_real_database(monkeypatch):
    """Exactly the leak's path: a fixture patches db_path, the test ends,
    the patch is undone, and late work reads what is left."""
    monkeypatch.setattr(settings, "db_path", "somewhere/else.db")
    monkeypatch.undo()
    in_use, real = _paths()
    assert in_use != real
