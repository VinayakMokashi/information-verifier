"""No credential reaches anything that gets printed. Free.

MEASURED 2026-09-29: the first, deliberately failing, run of
tests/test_isolation.py displayed a Settings object, and pytest's assertion
display carried the start of the real Anthropic API key. Whatever prints the
object — a failing assert, a traceback with locals, a debug line, a future
/health that dumps the config — printed every key in full (PROJECT_PLAN §11 17).

The rule is tested, not just today's five fields: the WhatsApp bot and a bot
shield will each add credentials, and a new key field must not quietly be
the one that prints.
"""
import re

from app.config import Settings, settings

# Every credential the app reads today. The name rule below must find each
# of them — a pattern that matched nothing would make every test here vacuous.
_KNOWN = {"anthropic_api_key", "google_factcheck_api_key", "sarvam_api_key",
          "hf_token", "telegram_bot_token"}
# "chat_max_tokens" is a size, not a credential: `token$` stops at the name's end.
_CREDENTIAL_NAME = re.compile(r"(?:^|_)(?:key|token|credentials?)$|secret|password")


def _credential_fields() -> list[str]:
    return sorted(n for n in Settings.model_fields if _CREDENTIAL_NAME.search(n))


def test_the_name_rule_finds_every_known_credential():
    missing = sorted(_KNOWN - set(_credential_fields()))
    assert missing == []


def test_the_name_rule_does_not_sweep_in_ordinary_settings():
    assert "chat_max_tokens" not in _credential_fields()


def test_no_credential_field_is_displayed_or_serialized():
    shown = [n for n in _credential_fields() if Settings.model_fields[n].repr]
    dumped = [n for n in _credential_fields() if not Settings.model_fields[n].exclude]
    assert shown == []
    assert dumped == []


def test_the_live_settings_object_never_shows_a_credential(monkeypatch):
    """The object that leaked: the module-level instance, loaded from .env."""
    planted = {}
    for i, name in enumerate(_credential_fields()):
        planted[name] = f"PLANTED-{i}-must-never-print"
        monkeypatch.setattr(settings, name, planted[name])

    # Compared as names, outside the assert: on failure, pytest's display of
    # the strings themselves would be the leak this file exists to stop.
    surfaces = {
        "repr": repr(settings),
        "str": str(settings),
        "format": f"{settings}",
        "model_dump": str(settings.model_dump()),
        "model_dump_json": settings.model_dump_json(),
    }
    leaks = sorted(f"{surface}:{name}" for surface, text in surfaces.items()
                   for name, value in planted.items() if value in text)
    assert leaks == []


def test_the_credentials_still_work_as_plain_strings(monkeypatch):
    """Hiding them must not change how they are read: the providers, the
    demo's key-blanking (scripts/fake_stages.py) and dozens of tests assign
    and compare plain strings."""
    monkeypatch.setattr(settings, "sarvam_api_key", "abc")
    assert settings.sarvam_api_key == "abc"
    assert isinstance(Settings(_env_file=None, anthropic_api_key="k").anthropic_api_key, str)
