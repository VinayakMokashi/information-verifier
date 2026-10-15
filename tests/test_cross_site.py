"""Other websites cannot submit checks through their visitors' browsers. Free.

REPRODUCED 2026-10-15 in real headless Chrome (docs/research/2026-10-15/
audit-security.md, "missed" finding 1): a page on ANOTHER origin made the
browser POST /verify/image — multipart/form-data is a CORS-"simple" request,
so no preflight ever asked this app. The server ran the paid vision call and
the chat check and took a daily slot, from the visitor's real IP, defeating
every per-visitor limit. Removing the CORS wildcard (main.py) only ever
stopped the JSON routes.

A browser says where a request came from (Sec-Fetch-Site; Origin on every
cross-origin POST). Requests carrying neither are not from a page — the
Telegram bot, curl — and CSRF needs a page.
"""
import pytest
from fastapi.testclient import TestClient

import scripts.fake_stages as F

_IMAGE = {"file": ("shot.png", b"\x89PNG" + b"0" * 64, "image/png")}


def _post(client, route, headers, prefix=""):
    if route == "image":
        return client.post(f"{prefix}/api/v1/verify/image", files=_IMAGE, headers=headers)
    if route == "media":
        return client.post(f"{prefix}/api/v1/verify/media",
                           files={"file": ("v.ogg", b"OggS" + b"0" * 64, "audio/ogg")},
                           headers=headers)
    return client.post(f"{prefix}/api/v1/verify/text", json={"text": "5G spreads corona"},
                       headers=headers)


@pytest.mark.parametrize("route", ["image", "media", "text"])
@pytest.mark.parametrize("headers", [
    {"origin": "https://evil.example"},
    {"origin": "null"},                                  # sandboxed frame, data: URL
    {"sec-fetch-site": "cross-site"},
    {"sec-fetch-site": "same-site"},                     # a sibling subdomain
    {"sec-fetch-site": "cross-site", "origin": "http://testserver"},  # FS wins
])
def test_a_request_another_site_made_is_refused_before_it_costs(client, route, headers):
    resp = _post(client, route, headers)
    assert resp.status_code == 403
    assert F.CALLS["answer"] == 0


@pytest.mark.parametrize("headers", [
    {},                                                  # the bot, curl: no page
    {"sec-fetch-site": "same-origin"},
    {"origin": "http://testserver"},                     # our own page, older browser
    {"sec-fetch-site": "same-origin", "origin": "http://testserver"},
])
def test_our_own_page_and_the_bot_still_get_through(client, headers):
    assert _post(client, "image", headers).status_code == 202


def test_reading_an_answer_is_never_blocked(client):
    """Only submissions are guarded: a GET cannot spend, and the page's own
    reads must not depend on headers a privacy extension might strip."""
    job = _post(client, "text", {}).json()["job_id"]
    resp = client.get(f"/api/v1/reports/{job}",
                      headers={"sec-fetch-site": "cross-site", "origin": "https://evil.example"})
    assert resp.status_code == 200


# -- a root path (review R4) ---------------------------------------------------
# REPRODUCED on real uvicorn with root_path="/v": uvicorn puts the prefix IN
# scope["path"]; Starlette routes on the path without it (get_route_path), but
# both middlewares compared the raw path — so another site's page could submit
# paid checks again, and every real screenshot over 64 KiB was "too long".
# Any sub-path deployment (a reverse proxy at /verifier) would hit it on day one.

@pytest.mark.parametrize("route", ["image", "text"])
def test_a_root_path_does_not_blind_the_cross_site_check(client, route):
    from app.main import app

    with TestClient(app, root_path="/v") as sub:
        resp = _post(sub, route, {"sec-fetch-site": "cross-site"}, prefix="/v")
    assert resp.status_code == 403
    assert F.CALLS["answer"] == 0


def test_a_root_path_keeps_the_upload_allowance(client):
    from app.main import app

    shot = {"file": ("shot.png", b"\x89PNG" + b"0" * 300_000, "image/png")}
    with TestClient(app, root_path="/v") as sub:
        resp = sub.post("/v/api/v1/verify/image", files=shot)
    assert resp.status_code == 202, resp.text
