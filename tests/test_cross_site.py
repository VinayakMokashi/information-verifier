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

import scripts.fake_stages as F

_IMAGE = {"file": ("shot.png", b"\x89PNG" + b"0" * 64, "image/png")}


def _post(client, route, headers):
    if route == "image":
        return client.post("/api/v1/verify/image", files=_IMAGE, headers=headers)
    if route == "media":
        return client.post("/api/v1/verify/media",
                           files={"file": ("v.ogg", b"OggS" + b"0" * 64, "audio/ogg")},
                           headers=headers)
    return client.post("/api/v1/verify/text", json={"text": "5G spreads corona"},
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
