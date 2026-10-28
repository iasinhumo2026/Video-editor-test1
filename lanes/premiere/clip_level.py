"""clip_level.py: the clip Volume > Level encoding for the Premiere lane, in ONE place.

    from clip_level import lvl_v, v_lvl

The rule's prose home is `lanes/premiere/lab-notes.md` (the Volume > Level bullet); this is its code
home, and every lane script — a hand or job-local ExtendScript placement included — imports it rather
than re-deriving the formula. It lives in its own module for the same reason `pes.py` and
`job_guard.py` do: the placers are hyphenated files (`place-sfx.py`, `place-music.py`) and a
hyphenated name cannot be imported, so the shared half has to sit beside them under an importable one.

Why (2026-09-19): `place-music.py` carried a byte-identical copy of both functions plus the formula in
its docstring, which is the exact drift the rule names. The drift it is guarding against already cost
a job once — encoding a clip level with the AMPLIFY effect's `(dB + 96) / 144` range instead put a
−29 dB riser on the timeline at +8.4 dB, and the readback agreed with it because it used the same
wrong formula.
"""
import math


def lvl_v(db):
    """dB -> a clip's Volume > Level value. NOT the Amplify effect's (dB + 96) / 144 range."""
    return 10 ** ((db - 15) / 20)


def v_lvl(v):
    """A clip's Volume > Level value -> dB, the inverse of lvl_v. A readback through it cannot PROVE a
    level (the same formula runs both ways): prove one with a solo bounce."""
    return 20 * math.log10(max(v, 1e-9)) + 15
