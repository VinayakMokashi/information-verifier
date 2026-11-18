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

from app.providers.links import allowed_link_host, find_links

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


# What people send WITH a link they want checked, and nothing else. With a
# link nobody can open, nothing is left to check. Only these, whole: any
# other words may carry the claim, and are checked.
_JUST_ASKING = frozenset("""
is this true|is it true|is this real|is it real|is this fake|is it fake
is this correct|is this right|true or false|real or fake|fake or real|true|fake
check|check this|check it|please check|pls check|plz check|check please
fact check|fact check this|verify|verify this|please verify|see this|look
kya ye sach hai|kya yeh sach hai|ye sach hai kya|yeh sach hai kya|sach hai kya
kya sach hai|sach hai|kya ye sahi hai|kya yeh sahi hai|ye sahi hai kya
sahi hai kya|kya ye fake hai|kya yeh fake hai|fake hai kya|sach ya jhooth
sach ya jhuth|check karo|check kariye|check kijiye|isko check karo|dekho
क्या यह सच है|क्या ये सच है|सच है क्या|ये सच है क्या|यह सच है क्या|क्या यह सही है
सही है क्या|चेक करो|चेक कीजिए
""".replace("\n", "|").strip("|").split("|"))


def only_unopenable_links(text: str) -> bool:
    """True when the message is links this service cannot open — a news site,
    X, a WhatsApp channel — and at most a greeting or "is this true?".

    The engine cannot open a link; such a check bought only an answer saying
    so (2026-11-18, "it says it can't read the link"). A link it CAN read
    (links.allowed_link_host) is never turned away here.
    """
    links = find_links(text)
    if not links or any(allowed_link_host(link) for _, _, link in links):
        return False
    rest, last = [], 0
    for start, end, _ in links:
        rest.append(text[last:start])
        last = end
    rest.append(text[last:])
    norm = _normalise(" ".join(rest))
    return not norm or norm in _SMALL_TALK or norm in _JUST_ASKING
