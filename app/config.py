"""Central settings, loaded once from environment / .env.

Model IDs live here so the whole engine swaps models in one place: the chat
check and vision OCR both run on Sonnet 5 since the 2026-09 pivot.
"""
from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


def _credential():
    """A key field that no repr, str or dump of Settings ever shows.

    MEASURED 2026-09-29: a failing assert displayed this object with the
    start of the real Anthropic key (PROJECT_PLAN §11 17). Plain `str`, not
    SecretStr, on purpose: providers, the demo's key-blanking and the tests
    all assign and read plain strings. tests/test_secrets.py fails any field
    named like a credential that is declared without this.
    """
    return Field(default="", repr=False, exclude=True)


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # Credentials
    anthropic_api_key: str = _credential()
    google_factcheck_api_key: str = _credential()
    sarvam_api_key: str = _credential()
    hf_token: str = _credential()  # unused since the pivot removed the local embedding model
    telegram_bot_token: str = _credential()  # from @BotFather; used only by scripts/telegram_bot.py
    # Cloudflare Turnstile (decided 2026-10-15): with both set, a paid check
    # from a web visitor needs a pass (app/providers/turnstile.py). Unset =
    # no challenge — this machine and development. The site key is public
    # (the page shows it); it is hidden here only because its name is a key's.
    turnstile_site_key: str = _credential()
    turnstile_secret_key: str = _credential()

    # Vision OCR still needs a model of its own (it is not the chat call).
    vision_model: str = "claude-sonnet-5"

    # Storage
    db_path: str = "./data/verifier.db"
    # Where the daily content-free copies of the spend record go (app/store/
    # backup.py); empty = a "backups" folder beside the database. A synced
    # folder here (OneDrive, a USB drive) takes them off this machine.
    backup_dir: str = ""

    # Chat engine (the pivot, 2026-09-10) — one Claude call per check,
    # whitelist-first then open web. Sonnet 5 chosen over Opus 5 on cost:
    # this workload is mostly "read these search results and explain them",
    # not the hard adjudication the old pipeline needed Opus for.
    chat_model: str = "claude-sonnet-5"
    chat_effort: str = "medium"      # low | medium | high | xhigh | max
    chat_max_tokens: int = 12000     # caps thinking + prose; a pre-call bound
    chat_max_searches_trusted: int = 3
    chat_max_searches_web: int = 2
    web_tier_enabled: bool = True    # False = whitelist only, never escalate
    # When Google's free Fact Check API found vetted fact-checks, answer from
    # them with no search tool first (2026-10-10, PROJECT_PLAN §7). False =
    # always search; the kill switch if its answers ever disappoint.
    factcheck_shortcut_enabled: bool = True
    # An answer resting only on general web sources can never show a
    # fact-checker-grade number. None = no cap (a trust decision; see §11).
    web_tier_confidence_cap: int | None = 75
    # Exact-match answer cache. TTL by tier because "no fact-checker has
    # covered this" is wrong the day one does.
    answer_cache_ttl_trusted_h: int = 168   # 7 days
    answer_cache_ttl_web_h: int = 24
    # What a pasted link said, by its platform video id. A post's audio does
    # not change; its caption can, so this still expires.
    transcript_cache_ttl_days: int = 30
    # Every stranger's message used to be kept forever. Answers (which hold
    # the message, what a machine read from it, and the reply) are deleted
    # after this many days; the spend ledger keeps the costs, with no content.
    answer_retention_days: int = 30

    # Media — audio/video via ffmpeg + Sarvam Saaras
    max_media_bytes: int = 25 * 1024 * 1024  # 25 MB upload cap — upload routes ONLY
    # Every other request body. REPRODUCED 2026-10-15: the 25 MB upload cap
    # was the only cap, so a 25 MB JSON "message" was parsed whole and the
    # small-talk triage froze the whole server for 10-19 s before any limit.
    # Fits a max_input_chars message even fully \uXXXX-escaped (a test pins it).
    max_json_bytes: int = 64 * 1024
    # The names a PAID check may be addressed to, beyond this machine's own
    # (127.0.0.1, localhost, [::1]): the public domain the tunnel serves,
    # comma-separated; ".example.com" allows any subdomain (share_demo.ps1
    # sets ".trycloudflare.com" for its quick tunnel). Anything else is
    # refused: a DNS-rebinding page sends its own name (review R5). Going
    # live, put the domain here — the server prints any name it refused.
    public_hosts: str = ""
    # The OWNER's Telegram chat id: trouble (paused for money, the budget
    # running low, failures in a row, a restart mid-check) is sent there
    # (app/providers/alerts.py). Empty = off. The bot's /id command says it.
    owner_chat_id: str = ""
    # Who runs the public service and where to write — printed by the privacy
    # notice and the terms (app/api/legal.py) for questions, deletion,
    # corrections and complaints. Publishing a person's name and address is
    # the owner's decision, so neither lives in the repo. Empty = the pages
    # say a contact is published before launch, and a public deployment is
    # warned at startup.
    operator_name: str = ""
    contact_email: str = ""
    # Set to true ONLY after Sarvam's dashboard has Model APIs data retention
    # at 0 days (Settings → Workspace → Data retention). Sarvam keeps
    # everything until an owner sets a period, so the privacy notice says
    # "keeps none of it" only when this says so (review S5-4).
    sarvam_zero_retention: bool = False
    # True only in the FREE demo server (scripts/fake_stages.apply_fake_stages):
    # /ready says "demo", and the bot refuses to wire people to it.
    demo_mode: bool = False
    max_media_seconds: int = 300             # 5 min cap — protects ASR credits
    asr_chunk_seconds: int = 29              # Sarvam sync API takes <=30 s per request

    # Spending guard — every check costs money and the share link is public.
    # One submission is one answer since the pivot (it used to fan out to a
    # paid check per claim), so a count of submissions now bounds spend.
    rate_limit_enabled: bool = True
    max_checks_per_hour: int = 10   # per PERSON (limits.subject_of) — abuse, not spend
    # One check at a time per person, from its claim until it ends, however
    # it ends (Vinayak's decision, 2026-10-15). REPRODUCED: five concurrent
    # slow link resolves from one visitor held all five daily slots, then
    # were refunded — a free lockout of everyone. The TTL frees a person
    # whose check hung without ever ending (the longest measured: 295 s).
    max_in_flight_per_person: int = 1
    # ...except where one "person" is really many: an IPv4 address is shared
    # by everyone behind carrier NAT or office Wi-Fi (review R9, reproduced:
    # strangers were told "you already have a check running").
    in_flight_by_kind: dict[str, int] = {"ip": 3}
    in_flight_ttl_s: int = 900
    # Paid checks a day per person, by who is asking (limits.subject_of) —
    # Vinayak's numbers, 2026-10-15: 5 per Telegram user and WhatsApp number,
    # 3 per web device (the signed cookie app/api/device.py issues after a
    # Turnstile pass, since 2026-10-16). A web visitor without one counts by
    # address: an IPv6 /64 is one phone; an IPv4 address is shared by many
    # under carrier NAT, so it is only a loose brake. Kept in memory: who
    # someone is never goes to disk.
    person_daily_limits: dict[str, int] = {"tg": 5, "tgchat": 5, "wa": 5,
                                           "dev": 3, "ip6": 5, "ip": 20}
    # DECIDED 2026-09-22 by Vinayak, before the first live use: "lower it for
    # now and do only 2 checks per day, just to be safe. We can increase it
    # later." Across the whole deployment — web page and Telegram bot share
    # it. Persisted in SQLite so a restart cannot quietly hand out two more.
    # Raise it here (or MAX_CHECKS_PER_DAY in .env); PROJECT_PLAN §7 has why.
    # RAISED to 5 on 2026-09-29 for the answer-quality checks ("use 5 or even
    # more if you want"). Measured checks run $0.05–0.26, so a full day is at
    # most ~$1.30. Five, not more: quality testing needs a handful a day, and
    # the cap's job is still to bound a bad day.
    # 2026-10-15: the MONEY is now bounded by daily_budget_usd below; this
    # count stays only as a backstop above it (~15 checks fill $1 at the
    # measured mix, ~119 if every one were a $0.0084 shortcut).
    max_checks_per_day: int = 40
    # DECIDED 2026-10-15 by Vinayak: strangers share "$1 a day". Each check
    # reserves its kind's worst case before any spend and settles at its real
    # cost when it ends; the database refuses a reservation past the budget
    # (limits.reserve). The reservations sit above the MEASURED maxima: text
    # $0.17 (two passes, 295 s), a reel $0.26, OCR a few cents.
    daily_budget_usd: float = 1.0
    budget_reserve_usd: dict[str, float] = {"text": 0.20, "image": 0.25,
                                            "media": 0.30, "link": 0.30}
    # "Gets cheaper as it runs low" (the same decision): with less than this
    # share of the day's budget left, no open-web pass (reserving half)...
    budget_vetted_below: float = 0.40
    # ...and below this, only answers from Google's published fact-checks
    # (~$0.008, reserving this much) and only for text; never a search.
    budget_shortcut_below: float = 0.15
    budget_shortcut_reserve_usd: float = 0.02
    # When Anthropic refuses for MONEY (a spend limit, the tier cap, billing,
    # an empty balance — app/providers/llm.paused_reason), new paid checks
    # are refused up front for this long, then one is let through to see if
    # it has cleared: one free failed attempt per window, not one per visitor.
    paused_retry_s: int = 600
    # When "a day" rolls over. IST (UTC+5:30), because the person watching the
    # bill is in India and "2 a day" means his day. A fixed offset rather than
    # a zone name: India has no DST, and zoneinfo needs the tzdata package on
    # Windows.
    day_boundary_utc_offset_min: int = 330
    max_input_chars: int = 5000     # a forwarded message, not a book


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
