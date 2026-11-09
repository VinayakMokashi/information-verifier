"""A request for a name that cannot be a file is simply not found. Free.

SEEN LIVE on 2026-11-03 (docs/research/2026-11-10/live-logs.md, L-1): a
scanner asked the public site for /*, /*/[id] and /*update.cgi*. On
Windows `*` (and ? < > | " :) cannot be in a file name, Starlette's
StaticFiles lookup catches only "not found", and each probe became a 500
with a traceback in the app's log — sixteen in a minute.
"""
import pytest


@pytest.mark.parametrize("path", ["/*", "/*/[id]", "/*update.cgi*", "/a?b",
                                  "/x<y>.html", "/x|y", '/x"y', "/x:y"])
def test_a_name_that_cannot_be_a_file_is_not_found(client, path):
    assert client.get(path).status_code == 404


def test_real_pages_still_load(client):
    assert client.get("/").status_code == 200
    assert client.get("/manifest.webmanifest").status_code == 200
