"""FREE end-to-end test of the web surface: static page + REST API + pipeline.

Uses the same simulated LLM stages as scripts/serve_demo.py, so the whole
submit -> background pipeline -> poll -> report flow runs with zero cost.
TestClient executes BackgroundTasks before returning, so the report is
COMPLETE by the time we poll it.
"""
import scripts.fake_stages as F


def _submit_and_fetch(client, payload):
    accepted = client.post("/api/v1/verify/text", json=payload)
    assert accepted.status_code == 202
    job_id = accepted.json()["job_id"]
    report = client.get(f"/api/v1/reports/{job_id}")
    assert report.status_code == 200
    return report.json()


def test_root_serves_the_demo_page(client):
    resp = client.get("/")
    assert resp.status_code == 200
    assert "text/html" in resp.headers["content-type"]
    assert "Information Verifier" in resp.text


def test_api_routes_win_over_the_static_mount(client):
    assert client.get("/health").json() == {"status": "ok"}
    assert client.get("/api/v1/reports/nonexistent").status_code == 404


def test_no_cors_grants_are_issued(client):
    """Every check spends money; a wildcard ACAO let any website drive checks
    from its visitors' browsers. The page itself is same-origin."""
    resp = client.post(
        "/api/v1/verify/text",
        # A real claim: "hello" is refused by triage now, and the point is a
        # request that WOULD spend money.
        json={"text": "5G causes covid"},
        headers={"Origin": "https://evil.example"},
    )
    assert resp.status_code == 202
    assert "access-control-allow-origin" not in resp.headers

    preflight = client.options(
        "/api/v1/verify/text",
        headers={"Origin": "https://evil.example",
                 "Access-Control-Request-Method": "POST"},
    )
    assert "access-control-allow-origin" not in preflight.headers


def test_full_text_flow_and_cache(client):
    report = _submit_and_fetch(client, {"text": "WHO ne kaha 5G se corona hota hai"})
    assert report["status"] == "COMPLETE"
    assert report["sections"][0]["markdown"].startswith("**This is false.**")
    assert report["confidence"] == 95
    assert report["tier"] == "trusted"
    assert report["sources"], "an answer must carry its receipts"
    assert F.CALLS["answer"] == 1

    # The same forward again -> served from cache, engine never runs.
    second = _submit_and_fetch(client, {"text": "WHO ne kaha 5G se corona hota hai"})
    assert second["status"] == "COMPLETE"
    assert second["cached"] is True
    assert second["markdown" if "markdown" in second else "sections"]
    assert F.CALLS["answer"] == 1
    assert second["usage"]["estimated_usd"] == 0.0


def test_an_answer_is_prose_not_a_form(client):
    """The point of the pivot: no rating enum, no per-claim verdict list."""
    report = _submit_and_fetch(client, {"text": "WHO ne kaha 5G se corona hota hai"})
    for gone in ("overall_rating", "claim_verdicts", "localized"):
        assert gone not in report, f"{gone} is a Truth Report leftover"
    # `summary` is back since 2026-09-23 with a different meaning: two lines
    # of PROSE for the reader's box. The old one was a structure (rating,
    # per-claim verdicts), and that is what must never return.
    assert isinstance(report.get("summary"), (str, type(None)))
    body = report["sections"][0]["markdown"]
    assert len(body.split()) > 30          # a paragraph, not a label
    assert body.count("\n\n") >= 1         # more than one paragraph


def test_the_answer_comes_back_in_the_senders_language(client):
    """Devanagari in -> Devanagari out, over the real HTTP contract."""
    report = _submit_and_fetch(
        client, {"text": "डब्ल्यूएचओ ने कहा कि 5जी से कोरोना फैलता है"})
    assert report["sections"][0]["markdown"].startswith("**यह दावा झूठा है।**")
    # Sources stay in their original language — they are receipts to click,
    # and a translated headline is unfindable on the source page.
    assert any("boomlive" in s["url"] for s in report["sources"])


def test_every_source_carries_a_tier_and_a_name(client):
    report = _submit_and_fetch(client, {"text": "WHO ne kaha 5G se corona hota hai"})
    for source in report["sources"]:
        assert source["tier"] in ("trusted", "web")
        assert source["url"].startswith("https://")
        assert source["publisher"] or source["title"]


def test_the_stream_endpoint_replays_a_finished_job(client):
    accepted = client.post("/api/v1/verify/text",
                           json={"text": "WHO ne kaha 5G se corona hota hai"})
    job_id = accepted.json()["job_id"]

    with client.stream("GET", f"/api/v1/stream/{job_id}") as resp:
        assert resp.status_code == 200
        assert "text/event-stream" in resp.headers["content-type"]
        body = "".join(resp.iter_text())

    assert "event: text" in body
    assert "event: done" in body

    # Text arrives word-by-word across many frames — reassemble the way the
    # page does, rather than expecting a phrase to sit in one frame.
    import json

    streamed = "".join(
        json.loads(line[len("data: "):]).get("text", "")
        for block in body.split("\n\n")
        for line in block.splitlines()
        if line.startswith("data: ") and "event: text" in block
    )
    assert streamed.startswith("**This is false.**")
    assert "5G radio waves cannot carry or spread a virus" in streamed


def test_streaming_an_unknown_job_is_404(client):
    assert client.get("/api/v1/stream/nope").status_code == 404


def test_image_flow_with_simulated_ocr(client):
    resp = client.post(
        "/api/v1/verify/image",
        files={"file": ("meme.png", b"\x89PNG fake bytes", "image/png")},
    )
    assert resp.status_code == 202
    report = client.get(f"/api/v1/reports/{resp.json()['job_id']}").json()
    assert report["status"] == "COMPLETE"
    assert report["sections"]
    # OCR text is machine-derived, so it is shown back for the same reason
    # a transcript is.
    assert "simulated OCR" in report["source_text"]


def test_image_flow_rejects_unsupported_type(client):
    resp = client.post(
        "/api/v1/verify/image",
        files={"file": ("notes.txt", b"hello", "text/plain")},
    )
    assert resp.status_code == 415


# -- the reader picks the reply language (2026-09-23) -------------------------

def test_the_reader_can_choose_the_reply_language(client):
    """The demo engine cannot translate, so it ECHOES the pick — which is
    exactly what this proves: the choice reaches the engine from both
    surfaces, JSON and multipart."""
    report = _submit_and_fetch(client, {"text": "Drinking hot water kills the coronavirus",
                                        "language": "Tamil"})
    assert "Tamil" in report["sections"][0]["markdown"]

    accepted = client.post("/api/v1/verify/image",
                           files={"file": ("shot.png", b"\x89PNG", "image/png")},
                           data={"language": "Marathi"})
    assert accepted.status_code == 202
    shot = client.get(f"/api/v1/reports/{accepted.json()['job_id']}").json()
    assert "Marathi" in shot["sections"][0]["markdown"]


def test_no_choice_means_the_language_it_came_in(client):
    report = _submit_and_fetch(client, {"text": "Drinking hot water kills the coronavirus"})
    assert "Simulated" not in report["sections"][0]["markdown"]


def test_an_absurd_language_string_is_refused_before_any_spending(client):
    resp = client.post("/api/v1/verify/text",
                       json={"text": "a claim", "language": "x" * 500})
    assert resp.status_code == 422
