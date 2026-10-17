"""Swapping a finished file into place, on Windows.

MEASURED 2026-10-18 (review G-8): `os.replace` onto a file written a moment
ago was refused with "access denied" (winerror 5) in 12 of 60 writes half a
second apart, in this project's own folder, and in 1 of 20 even two seconds
apart — most likely the antivirus still reading the file it had just been
handed. Retried after 10, 20, 50, 100 and 200 ms, all 860 writes landed:
median wait 2 ms, worst 451 ms.
"""
import os
import time

_PAUSES_S = (0.01, 0.02, 0.05, 0.1, 0.2)


def replace(source, target) -> None:
    """`os.replace`, tried again over ~0.4 s while Windows refuses it.
    Blocks for that long at worst, so it suits a rare small write, even on
    an event loop. Raises the last refusal when it never lands."""
    for pause in _PAUSES_S:
        try:
            os.replace(source, target)
            return
        except PermissionError:
            time.sleep(pause)
    os.replace(source, target)
