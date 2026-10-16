"""Randomized interleaving explorer for scripts/telegram_bot.py. Free: no
network, no app, no Telegram — fakes that suspend at every await.

    .venv\\Scripts\\python.exe scripts\\bot_explorer.py [seeds]     # 2000 by default

Run it after any change to the bot's concurrency: the per-chat lock, what
counts as work in flight, pending and prompted. It found what the tests
could not, twice. On 2026-09-22 it found two bugs in the FIXED bot. On
2026-10-16 it found a "hi" mid-check left unanswered, and chat locks kept
forever (review S5-2: 291 of 300 seeds before that fix, none after).

Written 2026-09-22 in a session scratch folder, where it survived by luck;
adapted 2026-10-16 to today's bot: subject-aware app calls, claim texts that
pass the small-talk triage, and the kinds step 5 changed — "/status" (an
unknown bare command, a poke for a waiting answer), "/privacy" (instant),
"hi" (small talk, not work in flight) and a sticker (unsupported).

Every fake await suspends a random number of loop turns, so interleavings
are real. Invariants per run:
  I1  a chat never submits while an earlier job of that chat is undelivered
      and not gone on the server (paying twice / overlapping checks)
  I2  every message gets at least one reply of its own
  I3  no report is delivered twice
  I4  after a final settle (all jobs done + pokes), every done job was
      delivered exactly once
  I5  after drain, nothing in flight, and `pending` holds nothing delivered
  I6  a report goes to the chat that asked for it
  I7  after drain, no chat's lock or live-handler count is left (S5-2)
  I8  `prompted` only names chats that still have a pending answer
"""
import asyncio
import os
import random
import sys
import threading
import traceback
from collections import Counter, defaultdict

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import scripts.telegram_bot as B  # noqa: E402
from scripts.render import force_utf8_stdout  # noqa: E402

CLAIM = "5G se corona phailta hai sach"


def report_for(job_id):
    return {"status": "COMPLETE", "tier": "trusted", "confidence": 90,
            "sections": [{"markdown": f"REPORT-{job_id}", "tier": "trusted"}],
            "sources": [], "cached": False}


class World:
    def __init__(self, rng, long_polls, p_reject, p_raise):
        self.rng = rng
        self.long_polls = long_polls
        self.p_reject = p_reject
        self.p_raise = p_raise
        self.jobs = {}
        self.n = 0
        self.violations = []
        self.sent = []
        self.task_msg = {}
        self.delivered = Counter()
        self.all_done_mode = False

    async def y(self, lo=1, hi=3):
        for _ in range(self.rng.randint(lo, hi)):
            await asyncio.sleep(0)


class FakeApp:
    def __init__(self, w: World):
        self.w = w

    async def _submit(self, chat, what):
        w = self.w
        await w.y()
        r = w.rng.random()
        if r < w.p_raise:
            raise RuntimeError("connection reset")
        if r < w.p_raise + w.p_reject:
            return None, "Today's checking budget has been used up."
        for j, info in w.jobs.items():
            if info["chat"] == chat and w.delivered[j] == 0 and info["state"] != "gone":
                w.violations.append(f"I1 chat {chat} submitted {what!r} while {j} "
                                    f"({info['state']}) was undelivered")
        w.n += 1
        job = f"j{w.n}"
        w.jobs[job] = {"chat": chat, "state": "done" if w.all_done_mode else "running"}
        await w.y()
        return job, ""

    async def submit_json(self, endpoint, payload, subject=None):
        text = payload.get("text") or payload.get("url")
        chat = int(text.split("-")[0][1:])
        return await self._submit(chat, text)

    async def submit_file(self, endpoint, filename, content, content_type, subject=None):
        raise AssertionError("files not used here")

    async def wait_for_report(self, job_id, attempts=None):
        w = self.w
        n = attempts if attempts is not None else w.long_polls
        for i in range(n):
            await w.y()
            state = w.jobs[job_id]["state"]
            if state == "gone":
                raise B.JobGone(job_id)
            if state == "done":
                return report_for(job_id)
            if i + 1 < n:
                await w.y(1, 4)
        return None


class FakeTG:
    def __init__(self, w: World):
        self.w = w

    async def send(self, chat_id, text):
        w = self.w
        await w.y()
        task = asyncio.current_task()
        w.sent.append((chat_id, text, task))
        for j in list(w.jobs):
            if f"REPORT-{j}<" in text or text.endswith(f"REPORT-{j}") or f"REPORT-{j}\n" in text:
                w.delivered[j] += 1
                if w.jobs[j]["chat"] != chat_id:
                    w.violations.append(f"I6 {j} sent to chat {chat_id}")
                if w.delivered[j] > 1:
                    w.violations.append(f"I3 {j} delivered {w.delivered[j]} times")
        return True

    async def file_bytes(self, file_id):
        return b"x", "voice/x.oga"


async def scenario(seed):
    rng = random.Random(seed)
    w = World(rng, long_polls=rng.randint(1, 6), p_reject=0.1, p_raise=0.05)
    app, tg = FakeApp(w), FakeTG(w)
    bot = B.Dispatcher(app, tg, max_in_flight=rng.randint(1, 3))
    chats = [1, 2, 3][: rng.randint(1, 3)]
    counter = defaultdict(int)
    orig_dispatch = bot.dispatch

    def dispatch(msg, kind):
        before = set(bot._tasks)
        orig_dispatch(msg)
        (task,) = set(bot._tasks) - before
        w.task_msg[task] = (msg["chat"]["id"], msg.get("text"), kind)

    for _ in range(rng.randint(3, 25)):
        action = rng.random()
        if action < 0.45:
            c = rng.choice(chats)
            counter[c] += 1
            pick = rng.random()
            if pick < 0.08:
                dispatch({"chat": {"id": c}, "text": "/help"}, "help")
            elif pick < 0.16:
                dispatch({"chat": {"id": c}, "text": "/status"}, "unknown-command")
            elif pick < 0.22:
                dispatch({"chat": {"id": c}, "text": "/privacy"}, "privacy")
            elif pick < 0.32:
                dispatch({"chat": {"id": c}, "text": "hi"}, "smalltalk")
            elif pick < 0.36:
                dispatch({"chat": {"id": c}, "sticker": {"file_id": "s"}}, "sticker")
            else:
                dispatch({"chat": {"id": c}, "text": f"c{c}-m{counter[c]} {CLAIM}"}, "text")
        elif action < 0.75:
            running = [j for j, i in w.jobs.items() if i["state"] == "running"]
            if running:
                w.jobs[rng.choice(running)]["state"] = "done"
        elif action < 0.78:
            alive = [j for j, i in w.jobs.items() if i["state"] != "gone"]
            if alive:
                w.jobs[rng.choice(alive)]["state"] = "gone"
        await w.y(0, 6)

    w.all_done_mode = True
    w.p_reject = w.p_raise = 0.0
    for j, i in w.jobs.items():
        if i["state"] == "running":
            i["state"] = "done"
    await asyncio.wait_for(bot.drain(), 20)
    for _ in range(10):
        if not bot.pending:
            break
        for c in list(bot.pending):
            counter[c] += 1
            dispatch({"chat": {"id": c}, "text": f"c{c}-poke{counter[c]} {CLAIM}"}, "poke")
        await asyncio.wait_for(bot.drain(), 20)

    per_task = Counter(t for _, _, t in w.sent)
    for task, (c, text, kind) in w.task_msg.items():
        if per_task[task] == 0:
            w.violations.append(f"I2 chat {c} message {text!r} ({kind}) got no reply")
    for j, i in w.jobs.items():
        if i["state"] == "done" and w.delivered[j] != 1:
            w.violations.append(f"I4 {j} (chat {i['chat']}) delivered {w.delivered[j]} times")
    if bot.in_flight:
        w.violations.append(f"I5 in_flight not empty: {bot.in_flight}")
    for c, j in bot.pending.items():
        if w.delivered[j]:
            w.violations.append(f"I5 pending[{c}]={j} already delivered")
    if bot.locks or getattr(bot, "active", {}):
        w.violations.append(f"I7 left after drain: locks={list(bot.locks)} "
                            f"active={getattr(bot, 'active', {})}")
    if not set(bot.prompted) <= set(bot.pending):
        w.violations.append(f"I8 prompted {set(bot.prompted)} beyond pending "
                            f"{set(bot.pending)}")
    return w


def run(seed):
    out = {}

    def target():
        try:
            out["w"] = asyncio.run(scenario(seed))
        except Exception:  # noqa: BLE001
            out["err"] = traceback.format_exc()

    t = threading.Thread(target=target, daemon=True)
    t.start()
    t.join(30)
    if t.is_alive():
        return None, "HUNG (thread still alive after 30 s)"
    if "err" in out:
        return None, out["err"]
    return out["w"], None


if __name__ == "__main__":
    force_utf8_stdout()
    n = int(sys.argv[1]) if len(sys.argv) > 1 else 2000
    kinds = Counter()
    examples = {}
    for seed in range(n):
        w, err = run(seed)
        if err:
            kinds["ERROR"] += 1
            examples.setdefault("ERROR", (seed, err[-800:]))
            continue
        for v in w.violations:
            k = v.split()[0]
            kinds[k] += 1
            examples.setdefault(k, (seed, v))
    print(f"seeds run: {n}")
    print("violations by invariant:", dict(kinds) or "none")
    for k, (seed, v) in examples.items():
        print(f"  first {k}: seed={seed}: {v}")
