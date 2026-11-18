# "Can't read the link", "can't send several images" (2026-11-18)

status: in progress

Reported by Vinayak on 2026-11-18, from a friend's WhatsApp at 17:34:
"I cant post multiple images? Or say a link to Instagram post. Its not
able to identify link." Others had said the answer "says can't read link".

All free and read-only: the content-free logs, the local dashboard's spend
API (kind, status and cost; never content), yt-dlp's own source, and a
free probe that touches only Instagram.

## What happened

- `logs\app-2026-11-17.log`, 03:56, 03:56 and 04:02, and
  `logs\app-2026-11-18.log`, **17:32:10**:
  `[links] resolve/fetch failed: ERROR: [Instagram] <post>: No video
  formats found!`. None of these became a job. Each person saw the
  catch-all **"That link could not be read."**
- The ledger, 2026-11-18, India time:
  - 17:32:55, a **text** check, $0.0436, 0 searches, tier none. Most
    likely the same link sent again with some words: the text route
    cannot open links, so the answer said so.
  - 17:35:35, one **image** check (a screenshot), $0.1408, which worked.
- The bot log has nothing but the network errors (`getUpdates failed`).

## Causes, from the code

1. **Instagram photo posts are not read at all.** The link path reads
   only videos (`app/providers/links.py`). yt-dlp's Instagram extractor
   (2026.10.21) behaves like this:
   - A single-photo post raises "There is no video in this post"
     (`raise_no_formats`, instagram.py:530).
   - A **carousel** (several pictures in one post) is a playlist. Its
     picture items have no formats, so YoutubeDL raises "No video
     formats found!". That is what the logs show, so these were
     carousels.
   - A carousel of only videos is refused by our own playlist check:
     "That looks like a channel or playlist".
   - `_classified()` does not recognise the first two errors, so they
     fall through to "That link could not be read."
   - The route was already meant to check a post's caption when there
     is no video ("That post has no video and no caption"), but yt-dlp
     stops before the app sees the caption.
2. **A link with words around it goes to the text check.** The page sends
   only a bare link to `/verify/link` (`LINK_RE` is anchored). The bot
   does the same (`allowed_link_host(text)` on the whole text). "Is this
   true? https://instagram.com/p/…" is therefore a paid text check, whose
   model cannot open the link and says so (about $0.04).
3. **A link to any other site** (a news article, X, WhatsApp) is a paid
   text check whose answer is "I can't open links".
4. **One image at a time.**
   - The page's picker takes one file (`files[0]`, no `multiple`).
   - `/verify/image` takes one `file`.
   - The bot treats each photo of an album as its own message. The first
     starts a check; the others get "Yeh naya message check nahi hua …".
   - A photo's caption is ignored.

## Measured (free probe, `ig_probe.py` in the session scratchpad; only Instagram contacted)

The probe used `_base_opts()` plus `ignore_no_formats_error`.

- `instagram.com/p/BQ0eAlwhDrw/` (yt-dlp's own test, a carousel of 3
  videos): `_type=playlist`, 3 entries, 4 formats each, cover images on
  `instagram.fbom3-*.fna.fbcdn.net`, 720×720, caption 1,012 characters.
- `instagram.com/p/BsOGulcndj-/` (a single public photo): no `_type`, 0
  formats, caption 192 characters, 11 image versions on
  `instagram.fbom3-2.fna.fbcdn.net`.
  - The versions have no width or height. The size is in the URL's
    `stp` parameter (`dst-jpg_e35_s150x150_tt6` … `s480x480`), and the
    full-size version has no size token (`dst-jpg_e35_tt6`).
  - yt-dlp's "best" pick is last only because the URLs sort that way,
    so the app must choose by those size tokens itself.
- With `ignore_no_formats_error`, yt-dlp only warns ("There is no video
  in this post", "No video formats found!", "Requested format is not
  available") and returns the caption and the image URLs.

## Plan (each failing-first, one concern per commit)

1. **Read Instagram photo posts and carousels:**
   - `ignore_no_formats_error`, for Instagram hosts only, so YouTube and
     Facebook behave exactly as before;
   - the largest picture of each item, chosen by declared size, else by
     the `_s<W>x<H>` token;
   - fetched only from `*.cdninstagram.com` and `*.fbcdn.net`, over
     https on port 443, with no redirects, a byte cap and a deadline;
   - at most 5 pictures, read in ONE vision call with bounded output;
   - the caption, plus what was read, plus a note of what was not read
     (more than 5 pictures, or video items);
   - a carousel of only videos is refused for free and the person is
     told what works instead;
   - the classifier names the two "no video" errors.
   - Worst case: OCR ≤ 8,000 tokens in plus 4,000 out at Sonnet 5's
     $2/$10 ≈ $0.056, plus the check (≤ $0.17), inside the link
     reservation ($0.30).
2. **A supported link with a few words around it is checked as the
   link:**
   - The server's text route decides this, so the page and the bot need
     no rule of their own.
   - The words go with the post's text into the check.
   - "A few" means up to 300 characters; a longer forward is still a text
     check.
3. **A link nobody can open, sent alone** (or with only "is this true?"):
   a free reply saying which links work, and to paste the text or send a
   screenshot.
4. **Several images in one check:**
   - `/verify/image` takes up to 5 files, read in one vision call;
   - the page picks several;
   - the bot gathers an album (same `media_group_id`) into one check
     and passes a photo's caption with it.
   - Run both bot explorers after this.
