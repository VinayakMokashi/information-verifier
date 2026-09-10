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
