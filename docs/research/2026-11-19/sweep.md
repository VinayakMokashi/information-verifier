# The restart, one paid carousel check, and a sweep for what else breaks (2026-11-19)

status: complete. Built and pushed, NOT LIVE until the next restart
(Vinayak's OK).

Vinayak (2026-11-19): "Yeah do both of it" (the restart and one paid check
of an Instagram picture post), "Also think of such exceptions or places
where our app is not working currently and fix it."

## Restart (done)

- 06:39:38: stop file written. The supervisor logged "stopping", but
  "stopped" only came at **06:44:39**, five minutes later. The app logged
  "Shutting down" at 06:39:39 and nothing after that (see S-6).
- 06:44:57: Start-ScheduledTask; app pid 6928, bot pid 5528 (06:45:16).
- /ready reports `ready`, mode real, database, keys and ffmpeg all true.
  The served page is the new one (`multiple` on the picker, the new lead).
- Live from now on: L-1 (b9e44b6), item 30 (c061d61) and all of the
  2026-11-18 fixes.
- The raised caps are still in force: the dashboard reads a $5.00 limit
  and 200 checks. Vinayak did not ask for the revert.

## The paid check (approved; through the LIVE app)

`scripts/link_smoke.py` could not run. Its TestClient starts a second
app on the real database, and the instance lock refused it, as designed
(S-4). Nothing was spent. The check was instead submitted to the running
app from this machine, as the page would submit it (scratch script; no
Turnstile, since the request is local). So it went through the real
budget and the real ledger.

- Post: `instagram.com/p/DdngmoOjB1Q/`, cited in an Alt News article. It
  is a 9-picture carousel of white-on-black text slides: an English essay
  that cites two news incidents (Jamui, Bihar; Kalkaji/LSR, Delhi).
- **The link path works end to end.**
  - It resolved, 5 of the 9 pictures were fetched, and one vision call
    transcribed all 5 correctly.
  - The note "[This post has 9 pictures; only the first 5 were read.]"
    was shown.
  - Pass 1 found no vetted source. Pass 2 confirmed both incidents from
    news reports (The Statesman, Brut and others): 75%, general web.
- **Cost: $0.2051** (the ledger agrees: link, COMPLETE, web, 5 searches).
  - 3 calls: the vision call, pass 1 and pass 2.
  - In 12,615, out 5,140, cache write 23,333, cache read 100,644.
  - I had told Vinayak "about $0.10". The open-web pass is what doubled
    it.

## Defects found

- **S-1 (seen in the paid run): what the model writes between searches
  is kept as part of the answer.**
  - The second pass's prose began: "Jamui incident confirmed. Now let's
    check the second claim.Both core incidents check out. Let me verify a
    couple more peripheral factual elements … Let's do a quick check on
    the mosque water supply claim since it's a specific factual
    claim.दोनों मुख्य घटनाएं …"
  - Cause: `_run_pass` appends every text delta to the canonical
    markdown, including text written before a tool call, and the blocks
    run together with no break.
  - PROJECT_PLAN §4 knew of one "Let me check…" sentence before the
    first search. A pass that searches several times writes several.
- **S-2 (seen in the paid run): an English post was answered in Hindi.**
  - `language_hint()` says "English" only when not one Hinglish marker
    appears. Measured on this post's text: 546 words, 121 English
    markers and a single Hinglish one, "ki" from "Mann Ki Baat".
  - So there was no language line at all, and with the search tool
    attached the reply drifted, as measured on 2026-09-22.
  - Indian English often contains such a word ("Modi ji", "Mann Ki
    Baat").
- **S-3 (seen in the paid run): the picture reading adds filler.**
  - After every slide it wrote "No photo, chart, or visual is present in
    this image; it is plain white text on a black background."
  - That is shown to the reader as "what the machine read", and its
    English words count toward the language guess.
- **S-4 (operator tool): `link_smoke.py` cannot run while the app runs**,
  which is now always.
- **S-5 (operator tool): `link_probe.py`** says "1 pictures". Its own
  yt-dlp section diagnoses a photo post as "NOT A MEDIA URL — no
  extractor matched", although the app reads it.
- **S-6 (restart): the app took 5 minutes to stop with no check running**,
  so every restart is about 5 minutes of downtime. Not yet explained.

### Found by free probes and reading

- **S-7: Instagram share links failed.**
  - `instagram.com/share/reel/BBFJ7jx5Ys`, a real link from a public bug
    report, got "That link could not be read." yt-dlp's Instagram
    extractor refuses `/share/` on purpose.
  - Instagram answered a plain client with one 302 to
    `/reel/DDHhYR9S1LN/`. A browser User-Agent got the 200 app page, as
    Facebook's share links did.
  - The logs (14 days) show no one hit it.
- **S-8: a video's captions were read in the wrong language.** For
  `dQw4w9WgXcQ`, with uploader tracks de-DE, en, es-419, ja and pt-BR,
  the app would have read **de-DE** (the alphabetical first).
- **YouTube without deno (HANDOFF §0 to-do 6): it works.** Watch, Shorts
  and youtu.be links resolve, with the duration, captions and 5
  audio-only formats; yt-dlp only warns. `BaW_jenozKc` (yt-dlp's old
  test video) is "unavailable": gone, not blocked.
- **Facebook:**
  - Reels resolve.
  - Photo links (`/photo/?fbid=`, `/<page>/photos/a…`) are "Unsupported
    URL", and the app says "That link could not be read. Send a
    screenshot…", which is free and the right advice.
  - `/posts/pfbid…` and `permalink.php` links get 404 from Facebook
    without a login, which the app reports as "needs a login" or "not
    found".
  - Not fixable from here without logging in.
- **Instagram `/<user>/reel/<code>/`** (a newer link form) resolves.
- **S-9 (Telegram): a photo sent as a FILE is refused.** That happens
  with desktop Telegram, "send without compression", or a forwarded
  document. `classify_message` has no "document" branch, so the reply is
  "Yeh message type abhi check nahi kar sakta — text, link, voice note ya
  photo bhejiye." Videos and audio sent as files are refused the same
  way.
- **S-10 (Telegram): a video's or voice note's caption is ignored.**
  Only photos send theirs (`note`). A forwarded video often carries its
  claim in the caption.
- **S-11 (images): the declared type is trusted.**
  - `verify_image` hands `upload.content_type` to the vision call as the
    media type. A file whose bytes are not what its name says (a WebP
    saved as .jpg) is refused by the API after the slot is taken.
  - HEIC (iPhone) gets the generic "not an image".
  - Sides over 8000 px (a long scrolling screenshot) are refused by the
    API (its documented limit).
- The logs never record a post's id: `log_safe` writes `<post>`.

- **S-12: a video over 5 minutes was refused even with captions.**
  - The 5-minute cap protects transcription money, and a caption track
    needs no transcription.
  - The engine already bounds any message at 8,000 characters and says
    where it cut.
  - So a 7-minute captioned news clip was refused for no saving.
- **S-13: the privacy notice was behind the code.** Since 2026-11-18 a
  linked post's pictures are fetched, read by Claude and kept in the
  transcript cache. The notice said only "caption and sound".
- **S-14: the web page dropped words typed before picking a picture**
  (listed as not built on 2026-11-18).

## Commits (each failing-first; the bot's after both explorers)

| Commit | Fix |
|---|---|
| 1d8d474 | S-1: the stored answer is what is written after the pass's last search |
| 65a0374 | S-2: one Hindi name no longer vetoes the English hint |
| a2c201a | S-8: captions in the spoken language |
| 1f8b5c5 | S-7: Instagram share links followed; `/accounts/login` is a wall |
| b00f3f3 | S-10 (server): /verify/media takes a caption; with no speech, the caption is checked |
| 174d967 | S-9, S-10 (bot): photos, videos and audio sent as files; a video's caption is sent |
| 622bf3a | S-11: an image's type is read from its bytes; HEIC and sides over 8,000 px are refused for free |
| fa775ad | S-3: no "no visual" sentence for text-only pictures (several-pictures prompt) |
| b7ee6c9 | S-5: the probe's own run reads a post of pictures; "1 picture" |
| 9fa2b3b | S-4: link_smoke sends to the running app when the lock is held |
| d685876 | S-12: a captioned video may run to 20 minutes; a failed caption fetch says so |
| 9f416d4 | S-13: the notice names the pictures |
| 64baecd | S-14: the page sends typed words as the pictures' or clip's note |

Measured free after the fixes:
- link_probe on the real share link says "THE APP: YES - Instagram video
  DDHhYR9S1LN".
- The English video now reads its 'en' captions.
- The real picture post now says "RESOLVES: YES".
- Headless Chrome loaded the page with no script error. A control page
  with a deliberate syntax error showed that such an error would be
  seen.

## Not measured (each would need a paid run; ask first)

- S-1 and S-2 on the real model, though S-2's hint was checked on the
  paid run's own text: it now reads "written in English, so write your
  whole reply in English".
- S-3: a prompt change.

## Not done

- **S-6, the 5-minute stop.** uvicorn logged "Shutting down" and nothing
  more:
  - there was no "Waiting for connections" or "background tasks" line,
    so it hung after those, in `server.wait_closed()` (uvicorn 0.51,
    Python 3.12.3);
  - that matches a transport the Proactor loop never detached; the known
    WinError 10054 resets are the likely source;
  - the supervisor gave up at its 300 s orderly limit.
  A fix needs a free reproduction (a scratch app on another port, a
  reset connection, then CTRL_BREAK) and then a decision. It costs about
  5 minutes of downtime per restart, nothing else.
- **Long screenshots** are refused at 8,000 px, for free, with "send it in
  parts". Tiling them with ffmpeg (already installed) would read them
  whole.
- **Facebook photo and text posts** cannot be read without logging in. The
  free reply asks for a screenshot.
- **Cost, not breakage.** In 30 days, 5 of 27 checks were "tier none, 0
  searches" at about $0.044. Those were messages past the triage that
  pass 1 said needed nothing, and they still bought pass 2. Skipping pass
  2 when pass 1 searched nothing would save about $0.02 each. Not
  changed: it is a quality trade and would need measuring.
