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


def test_full_text_flow_and_cache(client):
    report = _submit_and_fetch(client, {"text": "WHO ne kaha 5G se corona hota hai"})
    assert report["status"] == "COMPLETE"
    assert report["overall_rating"] == "FALSE"
    assert len(report["claim_verdicts"]) == 2  # non-checkworthy claim dropped
    assert report["claim_verdicts"][0]["verdict"]["citations"]
    assert F.CALLS["adjudicate"] == 2

    # Same claims again -> served from cache, no new simulated LLM calls.
    second = _submit_and_fetch(client, {"text": "WHO ne kaha 5G se corona hota hai"})
    assert second["status"] == "COMPLETE"
    assert all(cv["cache_hit"] for cv in second["claim_verdicts"])
    assert F.CALLS["adjudicate"] == 2


def test_image_flow_with_simulated_ocr(client):
    resp = client.post(
        "/api/v1/verify/image",
        files={"file": ("meme.png", b"\x89PNG fake bytes", "image/png")},
    )
    assert resp.status_code == 202
    report = client.get(f"/api/v1/reports/{resp.json()['job_id']}").json()
    assert report["status"] == "COMPLETE"
    assert report["overall_rating"] == "FALSE"
    # OCR text is machine-derived, so it is shown back for the same reason
    # a transcript is.
    assert "simulated OCR" in report["source_text"]


def test_image_flow_rejects_unsupported_type(client):
    resp = client.post(
        "/api/v1/verify/image",
        files={"file": ("notes.txt", b"hello", "text/plain")},
    )
    assert resp.status_code == 415
