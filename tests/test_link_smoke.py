"""scripts/link_smoke.py with the app already running (2026-11-19). Free:
nothing leaves the machine — the running app is a fake transport.

MEASURED: since go-live the app always runs, and the script's own copy of
the app could not start (the database lock refuses a second one, as it
should). The one approved paid check had to be sent by hand.
"""
import httpx

import scripts.link_smoke as S


def _live(statuses, seen):
    def handler(request):
        seen.append((request.method, request.url.path, request.content))
        if request.method == "POST":
            return httpx.Response(202, json={"job_id": "j1", "status": "QUEUED"})
        return httpx.Response(200, json={"job_id": "j1", "status": statuses.pop(0)})

    return httpx.Client(base_url="http://127.0.0.1:8000",
                        transport=httpx.MockTransport(handler))


def test_with_the_app_running_the_link_goes_to_it_and_waits_for_the_answer(monkeypatch):
    monkeypatch.setattr(S.time, "sleep", lambda seconds: None)
    seen = []
    payload = S.through_live_app("https://www.instagram.com/p/X/",
                                 client=_live(["PROCESSING", "COMPLETE"], seen))
    assert payload["status"] == "COMPLETE"
    assert seen[0][:2] == ("POST", "/api/v1/verify/link")
    assert b"https://www.instagram.com/p/X/" in seen[0][2]
    assert [s[:2] for s in seen[1:]] == [("GET", "/api/v1/reports/j1")] * 2


def test_a_refusal_from_the_running_app_is_printed_not_waited_on(capsys):
    def handler(request):
        return httpx.Response(422, json={"detail": "Only public links can be checked."})

    client = httpx.Client(base_url="http://127.0.0.1:8000",
                          transport=httpx.MockTransport(handler))
    assert S.through_live_app("https://example.com/", client=client) is None
    assert "REJECTED (422)" in capsys.readouterr().out


def test_main_sends_it_to_the_running_app_when_the_lock_is_held(monkeypatch):
    """The failure measured: AlreadyRunning from the app's own start-up."""
    import fastapi.testclient

    from app.store.instance import AlreadyRunning

    class Locked:
        def __init__(self, app):
            pass

        def __enter__(self):
            raise AlreadyRunning("data/verifier.db.lock")

        def __exit__(self, *exc):
            return False

    monkeypatch.setattr(fastapi.testclient, "TestClient", Locked)
    asked = []
    monkeypatch.setattr(S, "through_live_app", lambda url: asked.append(url))
    monkeypatch.setattr(S.sys, "argv", ["link_smoke.py", "https://youtu.be/x"])
    S.main()
    assert asked == ["https://youtu.be/x"]
