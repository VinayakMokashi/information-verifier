"""The bot explorer, with restarts and the clock: what scripts/bot_explorer.py
never exercises. Free: the same fakes, no network, no app, no Telegram.

    .venv\\Scripts\\python.exe scripts\\bot_explorer_restarts.py [seeds] [first seed]

Each run starts like a restart: a PERSISTED pending file (on a fake clock),
sometimes holding an entry a previous run left, which resume() hands over;
then the usual message mix, with tidy() at random points (as the poll loop
calls it) and a day passing mid-run. Written by the re-check of the step-5
fixes (2026-10-17), where it found two defects the shipped explorer could
not: a message arriving during a restart's hand-over was checked and paid
for (F-6), and a chat dropped by another chat's write kept its "prompted"
mark for the life of the process (F-2).

Invariants: bot_explorer's I1-I8, allowing what expires by design ("at most
a day") to stay undelivered and be followed by a new submission; plus
  I9  a day after the last message, once tidy() runs, nothing of any chat
      is left: pending, prompted, locks, active, in_flight
  I10 the file on disk never holds an entry older than a day after a write
"""
import asyncio
import json
import os
import random
import shutil
import sys
import tempfile
import threading
import traceback
from collections import Counter, defaultdict

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import scripts.bot_explorer as E  # noqa: E402
import scripts.telegram_bot as B  # noqa: E402
from scripts.render import force_utf8_stdout  # noqa: E402

TTL = B.PendingStore._TTL_S
NOW = [1_800_000_000.0]
CURRENT = [None]                      # the World of the running scenario


def install_fakes() -> None:
    """Put the pending store on the fake clock and watch what it drops and
    writes. Called by main() only — never on import, so importing this file
    (the suite's import check does) changes nothing."""
    original_drop = B.PendingStore._drop_expired
    original_write = B.PendingStore._write

    def drop(self):
        before = dict(self)
        old = original_drop(self)
        if CURRENT[0] is not None:
            for chat in old:
                CURRENT[0].expired.add(before[chat])
        return old

    def write(self):
        original_write(self)
        if CURRENT[0] is None:
            return
        try:
            with open(self._path, encoding="utf-8") as f:
                saved = json.load(f)
        except (OSError, ValueError):
            return
        for chat, entry in saved.items():
            if NOW[0] - float(entry["at"]) >= TTL:
                CURRENT[0].violations.append(
                    f"I10 chat {chat}'s entry is a day old and still on disk")

    B.PendingStore._clock = staticmethod(lambda: NOW[0])
    B.PendingStore._drop_expired = drop
    B.PendingStore._write = write


class World(E.World):
    def __init__(self, *a, **k):
        super().__init__(*a, **k)
        self.expired = set()


class FakeApp(E.FakeApp):
    async def _submit(self, chat, what):
        w = self.w
        await w.y()
        r = w.rng.random()
        if r < w.p_raise:
            raise RuntimeError("connection reset")
        if r < w.p_raise + w.p_reject:
            return None, "Today's checking budget has been used up."
        for j, info in w.jobs.items():
            if (info["chat"] == chat and w.delivered[j] == 0
                    and info["state"] != "gone" and j not in w.expired):
                w.violations.append(f"I1 chat {chat} submitted {what!r} while {j} "
                                    f"({info['state']}) was undelivered")
        w.n += 1
        job = f"j{w.n}"
        w.jobs[job] = {"chat": chat, "state": "done" if w.all_done_mode else "running"}
        await w.y()
        return job, ""


async def scenario(seed, folder):
    rng = random.Random(seed)
    NOW[0] = 1_800_000_000.0
    w = World(rng, long_polls=rng.randint(1, 6), p_reject=0.1, p_raise=0.05)
    CURRENT[0] = w
    app, tg = FakeApp(w), E.FakeTG(w)
    path = os.path.join(folder, f"pending-{seed}.json")
    chats = [1, 2, 3][: rng.randint(1, 3)]
    if rng.random() < 0.5:                    # a previous run's entry (OPS-07)
        c = rng.choice(chats)
        w.jobs["j0"] = {"chat": c, "state": rng.choice(["running", "done"])}
        with open(path, "w", encoding="utf-8") as f:
            json.dump({str(c): {"job": "j0", "at": NOW[0] - rng.uniform(0, TTL * 0.99)}}, f)
    bot = B.Dispatcher(app, tg, max_in_flight=rng.randint(1, 3), pending_path=path)
    counter = defaultdict(int)
    orig_dispatch = bot.dispatch

    def dispatch(msg, kind):
        before = set(bot._tasks)
        orig_dispatch(msg)
        (task,) = set(bot._tasks) - before
        w.task_msg[task] = (msg["chat"]["id"], msg.get("text"), kind)

    await bot.resume()
    for _ in range(rng.randint(3, 25)):
        action = rng.random()
        if action < 0.42:
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
                dispatch({"chat": {"id": c}, "text": f"c{c}-m{counter[c]} {E.CLAIM}"}, "text")
        elif action < 0.68:
            running = [j for j, i in w.jobs.items() if i["state"] == "running"]
            if running:
                w.jobs[rng.choice(running)]["state"] = "done"
        elif action < 0.71:
            alive = [j for j, i in w.jobs.items() if i["state"] != "gone"]
            if alive:
                w.jobs[rng.choice(alive)]["state"] = "gone"
        elif action < 0.74:
            NOW[0] += TTL + 1                 # a day passes, mid-run
        else:
            bot.tidy()                        # the poll loop's tidy-up
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
            dispatch({"chat": {"id": c}, "text": f"c{c}-poke{counter[c]} {E.CLAIM}"}, "poke")
        await asyncio.wait_for(bot.drain(), 20)

    per_task = Counter(t for _, _, t in w.sent)
    for task, (c, text, kind) in w.task_msg.items():
        if per_task[task] == 0:
            w.violations.append(f"I2 chat {c} message {text!r} ({kind}) got no reply")
    for j, i in w.jobs.items():
        if i["state"] == "done" and w.delivered[j] != 1 and not (
                j in w.expired and w.delivered[j] == 0):
            w.violations.append(f"I4 {j} (chat {i['chat']}) delivered {w.delivered[j]} times")
    if bot.in_flight:
        w.violations.append(f"I5 in_flight not empty: {bot.in_flight}")
    for c, j in bot.pending.items():
        if w.delivered[j]:
            w.violations.append(f"I5 pending[{c}]={j} already delivered")
    if bot.locks or bot.active:
        w.violations.append(f"I7 left after drain: locks={list(bot.locks)} active={bot.active}")
    if not set(bot.prompted) <= set(bot.pending):
        w.violations.append(f"I8 prompted {set(bot.prompted)} beyond pending {set(bot.pending)}")
    NOW[0] += TTL + 1                         # a day later the poll loop tidies up
    bot.tidy()
    await asyncio.wait_for(bot.drain(), 20)
    for name in ("pending", "prompted", "locks", "active", "in_flight"):
        left = getattr(bot, name)
        if left:
            shown = dict(left) if isinstance(left, dict) else set(left)
            w.violations.append(f"I9-{name} kept past its day: {shown}")
    CURRENT[0] = None
    return w


def run(seed, folder):
    out = {}

    def target():
        try:
            out["w"] = asyncio.run(scenario(seed, folder))
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


def main(argv: list[str] | None = None) -> int:
    force_utf8_stdout()
    args = list(sys.argv[1:] if argv is None else argv)
    n = int(args[0]) if args else 2000
    first = int(args[1]) if len(args) > 1 else 0
    install_fakes()
    folder = tempfile.mkdtemp(prefix="bot-explorer-")
    kinds, examples = Counter(), {}
    try:
        for seed in range(first, first + n):
            w, err = run(seed, folder)
            if err:
                kinds["ERROR"] += 1
                examples.setdefault("ERROR", (seed, err[-800:]))
                continue
            for v in w.violations:
                k = v.split()[0]
                kinds[k] += 1
                examples.setdefault(k, (seed, v))
    finally:
        shutil.rmtree(folder, ignore_errors=True)
    print(f"seeds run: {n}")
    print("violations by invariant:", dict(kinds) or "none")
    for k, (seed, v) in sorted(examples.items()):
        print(f"  first {k}: seed={seed}: {v}")
    return 1 if kinds else 0


if __name__ == "__main__":
    sys.exit(main())
