"""A check killed mid-flight still lands in the ledger, the spend truth. Free.

docs/research/2026-10-15/audit-ops.md OPS-04, reproduced there
(orphan_ledger.py): pass 1 was billed (8,000 tokens in, 2,500 out, 3
searches), then a hard kill — on this PC a closed window, a crash or a reboot;
on a host a redeploy. On restart the job was FAILED with usage=None and the
dashboard's ledger read "checks=0 usd=0": the money was spent and recorded
nowhere. A running check now keeps its bill so far on its row (routes
._checkpointing), and the sweeps that fail an abandoned row write its ledger
row from it.
"""
import asyncio
import types
import uuid
from datetime import datetime, timedelta, timezone

import pytest

import app.api.routes as R
from app.config import settings
from app.engine import job as J
from app.models.answer import Answer, AnswerSection, JobStatus, ReportUsage
from app.providers.usage import UsageMeter, note_asr, note_llm
from app.store.db import get_conn, init_db
from app.store.repository import AnswerRepository

PASS_ONE = types.SimpleNamespace(
    input_tokens=8000, output_tokens=2500, cache_creation_input_tokens=0,
    cache_read_input_tokens=0, server_tool_use=types.SimpleNamespace(web_search_requests=3))


@pytest.fixture()
def repo(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "db_path", str(tmp_path / "k.db"))
    monkeypatch.setattr(R, "_CHECKPOINT_EVERY_S", 0.01)
    init_db()
    return AnswerRepository()


def _new(repo, age_s=0.0):
    answer = Answer(job_id=uuid.uuid4().hex, status=JobStatus.QUEUED,
                    created_at=datetime.now(timezone.utc) - timedelta(seconds=age_s),
                    input_text="5G spreads corona")
    repo.save(answer)
    return answer


def _ledger():
    with get_conn() as conn:
        return {r["job_id"]: (r["status"], r["usd"])
                for r in conn.execute("SELECT job_id, status, usd FROM spend_ledger")}


async def _until(condition, seconds=5.0):
    for _ in range(int(seconds / 0.01)):
        if condition():
            return True
        await asyncio.sleep(0.01)
    return False


def test_a_check_killed_after_its_first_pass_still_lands_in_the_ledger(repo, monkeypatch):
    async def scenario():
        async def engine(text, *, heard=None, emit=None, language=None, mode="full"):
            note_llm(settings.chat_model, PASS_ONE)          # pass 1, billed
            await asyncio.Event().wait()                     # ...and the process dies here

        monkeypatch.setattr(J.chat, "answer", engine)
        answer = _new(repo)
        job = asyncio.create_task(R._run_check_job(answer.job_id, answer.input_text, repo))
        landed = await _until(lambda: (repo.get(answer.job_id).usage or
                                       ReportUsage()).estimated_usd > 0)
        # The process is gone: nothing in its `finally` ever runs. The next
        # one starts, and fails what it finds mid-flight:
        healed = repo.sweep_orphans()
        result = (landed, healed, repo.get(answer.job_id), _ledger().get(answer.job_id))
        job.cancel()                                         # this test's cleanup only
        await asyncio.gather(job, return_exceptions=True)
        return result

    landed, healed, row, ledger = asyncio.run(scenario())
    assert landed, "the bill so far never reached the row"
    assert healed == 1 and row.status is JobStatus.FAILED
    assert ledger is not None, "the spend of a killed check is recorded nowhere"
    assert ledger[0] == "FAILED" and ledger[1] == pytest.approx(row.usage.estimated_usd)
    assert ledger[1] > 0.05                                  # ~ the audit's $0.07


def test_a_late_checkpoint_never_overwrites_a_finished_answer(repo):
    answer = _new(repo)
    answer.status = JobStatus.COMPLETE
    answer.sections = [AnswerSection(tier="trusted", markdown="It is false.")]
    repo.save(answer)
    assert repo.record_progress(answer.job_id, ReportUsage(estimated_usd=9.0)) is False
    stored = repo.get(answer.job_id)
    assert stored.status is JobStatus.COMPLETE and stored.usage is None


def test_the_stale_sweep_writes_a_stuck_checks_spend_too(repo):
    stuck = _new(repo, age_s=3600)
    assert repo.record_progress(stuck.job_id, ReportUsage(estimated_usd=0.07))
    assert repo.sweep_stale(1800, running=lambda job_id: False) == 1
    assert _ledger()[stuck.job_id] == ("FAILED", pytest.approx(0.07))


def test_a_link_checkpoints_the_transcription_it_paid_for(repo, monkeypatch):
    """A link's transcription is paid BEFORE its check starts: killed then,
    it was lost the same way."""
    async def scenario():
        async def gather(info):
            note_asr(70.0)                                   # 70 s of Sarvam
            await asyncio.Event().wait()

        monkeypatch.setattr(R, "gather_link_text", gather)
        answer = _new(repo)
        info = R.LinkInfo(url="https://www.youtube.com/watch?v=iiiiiiiiiii",
                          platform="youtube", video_id="iiiiiiiiiii", title="t",
                          uploader="u", duration=70.0, caption="", has_media=True,
                          subtitle=None)
        job = asyncio.create_task(R._run_link_job(answer.job_id, info, repo))
        landed = await _until(lambda: (repo.get(answer.job_id).usage or
                                       ReportUsage()).asr_seconds == 70.0)
        job.cancel()
        await asyncio.gather(job, return_exceptions=True)
        return landed

    assert asyncio.run(scenario()), "a link's paid transcription never reached its row"


def test_a_voice_note_checkpoints_what_its_upload_already_paid(repo, monkeypatch):
    async def scenario():
        async def transcribe(wav, duration):
            await asyncio.Event().wait()

        monkeypatch.setattr(R, "transcribe_wav", transcribe)
        answer = _new(repo)
        meter = UsageMeter()
        meter.note_asr(30.0)                                 # the route's decode noted it
        job = asyncio.create_task(R._run_media_job(answer.job_id, b"RIFF", 30.0, repo, meter))
        landed = await _until(lambda: (repo.get(answer.job_id).usage or
                                       ReportUsage()).asr_seconds == 30.0)
        job.cancel()
        await asyncio.gather(job, return_exceptions=True)
        return landed

    assert asyncio.run(scenario()), "a voice note's paid seconds never reached its row"
