"""Every script must still be able to import what it says it imports.

This exists because of a measured gap, not a hypothetical one: after the old
engine was deleted, `scripts/render.py`, `demo_offline.py`, `smoke_test.py`
and `link_smoke.py` all still did `from app.models.report import TruthReport`
— a module that no longer existed. Every one of them would have died on the
first line. The suite stayed green the whole time, because no test imported a
script; the free-path table in CLAUDE.md promised four commands that would
have crashed on launch.

Static rather than subprocess-per-script on purpose: this runs in
milliseconds, has no side effects (several scripts patch globals and start
servers at import), and still catches both halves of the failure — a module
that is gone, and a name that is gone from a module that survived.
"""
import ast
import importlib
import importlib.util
from pathlib import Path

import pytest

SCRIPTS = sorted((Path(__file__).resolve().parent.parent / "scripts").glob("*.py"))
assert SCRIPTS, "no scripts found — has the directory moved?"

# Only our own packages. Third-party imports are pinned by requirements.txt,
# and stdlib is not going anywhere.
OURS = ("app", "scripts")


def _local_imports(path: Path):
    """-> [(module, [names]), …] for every `app.*` / `scripts.*` import."""
    out = []
    for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name.split(".")[0] in OURS:
                    out.append((alias.name, []))
        elif isinstance(node, ast.ImportFrom):
            if node.module and node.module.split(".")[0] in OURS:
                out.append((node.module, [a.name for a in node.names]))
    return out


@pytest.mark.parametrize("script", SCRIPTS, ids=lambda p: p.name)
def test_every_import_in_every_script_resolves(script):
    for module, names in _local_imports(script):
        assert importlib.util.find_spec(module) is not None, \
            f"{script.name} imports {module}, which does not exist"
        loaded = importlib.import_module(module)
        for name in names:
            if name == "*":
                continue
            assert hasattr(loaded, name) or \
                importlib.util.find_spec(f"{module}.{name}") is not None, \
                f"{script.name} imports {name} from {module}, which has no {name}"


@pytest.mark.parametrize("script", SCRIPTS, ids=lambda p: p.name)
def test_every_script_parses(script):
    ast.parse(script.read_text(encoding="utf-8"))


RUNNABLE = [p for p in SCRIPTS if '__name__ == "__main__"' in p.read_text(encoding="utf-8")]


@pytest.mark.parametrize("script", RUNNABLE, ids=lambda p: p.name)
def test_every_runnable_script_that_prints_forces_utf8(script):
    """Windows falls back to cp1252 whenever stdout is redirected or piped,
    and these scripts print transcripts, captions, titles and answers — in
    Hindi, Tamil, Bengali. MEASURED three times: demo_offline.py died on
    `> out.txt`; serve_demo.py's banner printed "simulated \ufffd $0"; and
    crawl_probe.py's FIRST run made its paid API call and then crashed on a
    '≈' before it could report what it had found."""
    src = script.read_text(encoding="utf-8")
    if "print(" not in src:
        return
    guards = ("force_utf8_stdout(", "_utf8_console(", "print_answer(")
    assert any(g in src for g in guards), \
        f"{script.name} prints but never forces UTF-8 on stdout"
