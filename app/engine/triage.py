"""Is there anything here to check at all? Free, before any money is spent.

MEASURED 2026-10-10: every text reaching the engine bought a full check —
about 8,000 tokens of fixed setup per pass, roughly $0.03-0.05 — and one of
the day's capped slots, even "hi". The model already answers a greeting
with "nothing to check here"; it was just paid to say so.

Deliberately narrow: only a WHOLE message that is a greeting, a thanks, an
acknowledgement, or has no letters or digits at all. A short real claim
("5G causes covid") must never be turned away, so there is no length rule —
in scripts without spaces between words a whole claim can be one "word".
Shared by the API route and the Telegram bot, so every surface agrees.
"""
import re
import unicodedata

# Whole-message small talk, after normalising (lowercase, punctuation and
# emoji removed, runs of 3+ identical letters squeezed: "hiii" -> "hi").
# English, Hinglish and Hindi, because that is who sends forwards here.
_SMALL_TALK = frozenset("""
hi|hii|hello|helo|hlo|hey|heya|yo|hm|hmm|ok|okay|okk|oky|k|kk|ok ji
thanks|thank you|thanku|thankyou|thx|ty|tq|thanks a lot|thank you so much
welcome|you re welcome|good morning|good night|good evening|good afternoon
gm|gn|bye|bye bye|see you|yes|no|yeah|yup|nope|sure|cool|nice|great|wow
lol|haha|hahaha|done|test|testing|start|help
namaste|namaskar|ram ram|haan|ha|han|nahi|nahin|accha|achha|acha|theek hai
thik hai|thik h|ji|shukriya|dhanyavad|dhanyawad|kya hua|kaise ho
kya haal hai|sat sri akal|salaam|salam|assalamualaikum|vanakkam
नमस्ते|नमस्कार|धन्यवाद|शुक्रिया|ठीक है|हाँ|हां|नहीं|अच्छा|हेलो|हाय|राम राम|जी
""".replace("\n", "|").strip("|").split("|"))

_SQUEEZE = re.compile(r"(.)\1{2,}")


def _normalise(text: str) -> str:
    # Keep letters, digits and combining marks (Devanagari vowel signs are
    # marks: dropping them would turn "नहीं" into something else).
    kept = "".join(ch if unicodedata.category(ch)[0] in "LNM" else " "
                   for ch in text.lower())
    return _SQUEEZE.sub(r"\1", " ".join(kept.split()))


def nothing_to_check(text: str) -> bool:
    """True when the whole message is small talk or has no words at all."""
    norm = _normalise(text or "")
    return not norm or norm in _SMALL_TALK
