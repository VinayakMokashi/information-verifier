# The cheap app: installable PWA and the Play Store route

Researched 2026-10-15 by a research agent (web sources dated in each finding). **Verification: independently verified (verdicts inline).** This file is the durable copy of the agent's result (the raw journals are session-internal and not kept).

## Summary

I picked up the source trail from the killed run (72 leads) and went straight to the primary pages it pointed at, using about 17 web calls. No paid scripts were run.

For Android and iOS, making static/index.html an installable app needs no new money. The pieces are: a manifest (name/short_name, start_url, display: standalone, icons 192 and 512 px including a maskable one, prefer_related_applications absent), an apple-touch-icon and theme-color, all served over HTTPS from one stable origin. app/main.py already mounts static/ at "/", so these files can simply be dropped into static/.

A service worker is NOT needed to be installable. MDN (updated 2026-10-06) says so. Chromium's current InstallableStatusCode enum has commented out every service-worker code (NO_MATCHING_SERVICE_WORKER, NOT_OFFLINE_CAPABLE, SERVICE_WORKER_NOT_REQUIRED) and the engagement code. Chrome also shows its own default offline page for installed apps that have no service worker.

On iOS/iPadOS 26, any site added to the Home Screen opens as a web app by default, even without a manifest (WebKit, 2025-06-09). iOS has no install prompt and no share_target, ignores maskable icons, and keeps an installed app's storage separate from Safari's (firt.dev, updated 2026-10-13).

Share Target works only on Android: Chrome Android and Samsung Internet 12+, after install. Links and text arrive through a simple GET. Files (images, audio) arrive as a multipart POST, which is most cleanly caught by a small service worker that holds the file until the user taps Check. Whether WhatsApp offers installed PWAs in its share sheet for text messages could not be confirmed. For photos, videos and voice notes the "Share" menu probably reaches the Android share sheet, but this is unverified. A WhatsApp feature for sharing messages to other apps was reported in beta in Dec 2024, and its stable status was not found. Instagram and YouTube "Share" to the system share sheet is the high-value, low-risk case.

Play Store via a Trusted Web Activity is doable without Node or a JDK by using PWABuilder in the browser. It costs a one-time US$25 and needs a government ID plus a card in the owner's legal name (prepaid cards refused). Personal accounts created after 2023-11-13 must run a closed test with at least 12 testers opted in for 14 consecutive days before production. Other requirements: Android device verification through the Play Console app, a hosted /.well-known/assetlinks.json carrying the Play App Signing SHA-256, and an in-app way to report offensive AI output.

Android developer verification starts enforcement on 2026-09-30 only in Brazil, Indonesia, Singapore and Thailand, with the global rollout "2027 and beyond". Apps on Play that use Play App Signing are registered automatically. Nothing found says PWAs or WebAPKs are in scope.

The biggest hosting constraint this research turned up: Cloudflare Quick Tunnels (trycloudflare) change hostname on every start and do NOT support Server-Sent Events (Cloudflare docs, updated 2026-09-30). They cannot carry an installed app.

## Findings

### F1. Chrome no longer needs a service worker or fetch handler for installability, including the install prompt; the requirements are HTTPS plus a manifest with name/short_name, icons at 192 and 512 px, start_url, a standalone-type display, and prefer_related_applications absent or false.
*Confidence: high*

web.dev install-criteria (last updated 2024-09-19) lists: not already installed; user clicked the page at least once and spent 30 s on it; HTTPS; manifest with short_name or name, icons including 192px and 512px, start_url, display = fullscreen | standalone | minimal-ui | window-controls-overlay, prefer_related_applications absent or false. It does not mention a service worker. MDN 'Making PWAs installable' (modified 2026-10-06) says a service worker is 'not a requirement for a PWA to be installable'. Chromium main's installable_logging.h has these codes commented out as DEPRECATED: NO_MATCHING_SERVICE_WORKER=12, NOT_OFFLINE_CAPABLE=29, NO_URL_FOR_SERVICE_WORKER=35, WARN_NOT_OFFLINE_CAPABLE=40, SERVICE_WORKER_NOT_REQUIRED=45, and also INSUFFICIENT_ENGAGEMENT=20. That means the install pipeline no longer has a service-worker failure state. The older Chrome blog 'Revisiting installability criteria' (updated 2023-12-05) said the menu install stopped needing a fetch handler from Chrome 108 (mobile) and 112 (desktop) but the prompt 'still requires' one. That statement is superseded by the deprecations in the source. Caveat: whether Chrome 2026 shows the automatic mini-infobar or ambient badge is decided by engagement heuristics I did not trace in source. A custom button driven by beforeinstallprompt, or the 'Install app' menu item, works either way. Note: NO_ID_SPECIFIED still exists, so set manifest 'id' explicitly.

Sources: https://web.dev/articles/install-criteria · https://developer.mozilla.org/en-US/docs/Web/Progressive_web_apps/Guides/Making_PWAs_installable · https://raw.githubusercontent.com/chromium/chromium/main/components/webapps/browser/installable/installable_logging.h · https://developer.chrome.com/blog/update-install-criteria

### F2. The installed app is tied to one origin, so it needs a stable public HTTPS hostname. Cloudflare Quick Tunnels (trycloudflare.com) change hostname on every start, are 'for testing and development', have no uptime guarantee, and 'do not support Server-Sent Events (SSE)'.
*Confidence: high — **decision-critical***

Cloudflare's trycloudflare page (last updated 2026-09-30) says: 'The hostname changes each time you create a Quick Tunnel'; 'Quick Tunnels are for testing and development'; 'up to 200 in-flight requests'; 'Quick Tunnels do not support Server-Sent Events (SSE)'; 'no uptime guarantee'. Each change of origin orphans the installed WebAPK or home-screen icon and its storage. The SSE gap breaks this app's live stream (polling /reports would still work). Installing the app therefore depends on the hosting decision: a named Cloudflare Tunnel on an owned domain, or a cloud host with a fixed HTTPS domain. A stable HTTPS URL is also what the planned WhatsApp webhook needs.

Sources: https://developers.cloudflare.com/cloudflare-one/networks/connectors/cloudflare-tunnel/do-more-with-tunnels/trycloudflare/

**Verifier: confirmed.** Corrected: As stated. Cloudflare's Quick Tunnels page, last updated 2026-09-30, says word for word: 'The hostname changes each time you create a Quick Tunnel'; 'Quick Tunnels are for testing and development'; 'Each Quick Tunnel supports up to 200 in-flight requests' (more get HTTP 429); 'Quick Tunnels do not support Server-Sent Events (SSE)'; 'Quick Tunnels have no uptime guarantee'. An installed PWA belongs to one web address (its origin), so it needs a stable HTTPS hostname.
> I fetched the trycloudflare page directly and it shows 'Last updated Sep 30, 2026'. All five quoted statements are there. The point that a changed origin orphans the installed app follows from how web-app manifests and storage are tied to one origin. That is an inference, not something this page says, but it is standard platform behaviour.

### F3. iOS/iPadOS 26: any website added to the Home Screen opens as a web app by default, even without a manifest. iOS has no install prompt (no beforeinstallprompt or appinstalled), does not support manifest share_target, ignores maskable icons, and keeps the installed app's storage separate from Safari's.
*Confidence: high*

WebKit's WWDC25 post (2025-06-09) says: 'By default, every website added to the Home Screen opens as a web app', with an 'Open as Web App' toggle the user can switch off, and 'nothing is required beyond the basics of an HTML file and a URL'; manifest icons are used if present. firt.dev iOS PWA notes (updated 2026-10-13) add: Add to Home Screen also works from Chrome, Edge and Firefox on iOS since 16.4; supported manifest fields are name, short_name, scope, start_url, display (browser/standalone), icons (15.4), id (16.4) and theme_color; maskable and monochrome icons are ignored; an apple-touch-icon link overrides manifest icons. NOT supported: share_target, background_color, orientation, Background Sync, link capturing. Web Push and Badging (16.4+) work only for installed apps. getUserMedia and MediaRecorder (14.5+) and file input are available. iOS users therefore cannot share from WhatsApp into the app. They paste instead, or use a future WhatsApp/Telegram bot.

Sources: https://webkit.org/blog/16993/news-from-wwdc25-web-technology-coming-this-fall-in-safari-26-beta/ · https://firt.dev/notes/pwa-ios/

### F4. Web Share Target works only on Android (Chrome Android, Samsung Internet 12+) and only after the app is installed. Text and URLs can arrive by GET to a server URL. Files (images, audio) arrive as a POST multipart/form-data navigation, best caught by a service-worker fetch listener. Safari iOS and Firefox Android do not support it.
*Confidence: high*

caniuse for mdn-manifests_webapp_share_target: Chrome Android supported; Samsung Internet 12.0+; desktop Chrome 89+; Safari iOS not supported through 27.2; Firefox Android not supported. Chrome's Web Share Target doc (last updated 2019-11-08, old but still the canonical page) says: 'your web app has to be installed'; for text and links use action plus GET params title/text/url; for files use method POST, enctype multipart/form-data, and a files[] array of {name, accept}, listing both MIME types and extensions. 'The foreground page cannot process this data directly'; the documented pattern is a service worker that reads formData() and returns a 303 redirect. On Android the shared link often arrives in 'text' rather than 'url', so the handler must read every field. Inference, not verified: a POST navigation with no service worker would reach the FastAPI server directly, but then the server would have to hold an unconfirmed upload. A service worker that stashes the file and redirects to '/?shared=1', so the user confirms before any paid check, fits invariant 5 (bounded spend) better. A share must never auto-submit a paid check.

Sources: https://caniuse.com/mdn-manifests_webapp_share_target · https://developer.chrome.com/docs/capabilities/web-apis/web-share-target

### F5. No evidence was found that WhatsApp for Android can share a plain TEXT message into another app's share sheet. Media messages (photo, video, voice note, document) probably can (unverified). A 'share messages and media to other apps' feature was reported in beta development in Dec 2024, and its stable rollout was not confirmed.
*Confidence: low*

WABetaInfo (2024-12-04, beta 2.24.25.20) described a planned bottom bar for sharing 'messages and media directly to other apps' (Instagram/Facebook stories, X, Snapchat, and a 'More' option). It was 'under development', not available even to beta testers, and its examples were photos, videos and GIFs; voice notes were not mentioned. Phonandroid (2024-12-04) said the same. WABetaInfo (2026-06-11) reported a redesigned message menu in beta 2.26.23.8 with no mention of share-to-other-apps. I found no source confirming the media 'Share' path, so treat it as unverified. Practical reading: for WhatsApp-forwarded TEXT on Android, expect users to long-press, Copy, and paste into the app; the share target will not catch it. Images, voice notes (an .opus/ogg audio file, so accept audio/* plus .opus and .ogg) and videos may reach the PWA only if WhatsApp's Share hands them to the Android share sheet. The higher-value, lower-risk case is Instagram, YouTube and Facebook 'Share' sending a reel URL to the system share sheet, where an installed WebAPK appears as a GET text/url target. Verifying on a real Android phone after install is free and settles all of this.

Sources: https://wabetainfo.com/whatsapp-beta-for-android-2-24-25-20-whats-new/ · https://www.phonandroid.com/whatsapp-va-enfin-corriger-ce-vilain-defaut-qui-nous-fait-perdre-tant-de-temps.html · https://wabetainfo.com/whatsapp-launches-a-redesigned-message-menu-on-android/

### F6. Google Play: one-time US$25 registration fee, paid by card (Visa/Mastercard/Amex; prepaid cards not accepted). A government ID and card in the developer's legal name may be required. Personal accounts created after 2023-11-13 must run a closed test with at least 12 testers opted in continuously for the preceding 14 days before applying for production. New personal accounts must also verify an Android device through the Play Console mobile app.
*Confidence: high — **decision-critical***

Play Console Help 14151465: 'At least 12 testers must be opted in to your closed test when you apply for production access … opted in continuously for the preceding 14 days'; it applies to 'personal developer accounts created after November 13, 2023'. Help 6112435: 'US$25 one-time registration fee', no refund if identity info is found invalid; 'Prepaid cards are not accepted'; you may be asked for 'a valid government ID and a credit card, both under your legal name'; must be 18+; from early 2024 new personal accounts verify Android device access via the Play Console app. Neither page shows a visible date. For an Indian card, international/online transactions must be enabled for a US$ charge (general knowledge, not re-verified here). Practical cost: about ₹2,100–2,300 one-time, plus recruiting 12 real testers for 2 weeks.

Sources: https://support.google.com/googleplay/android-developer/answer/14151465?hl=en · https://support.google.com/googleplay/android-developer/answer/6112435?hl=en

**Verifier: confirmed.** Corrected: Small refinements to an otherwise correct claim:
- The fee is a US$25 one-time registration fee.
- Accepted cards are MasterCard, Visa, American Express, Discover (US only) and Visa Electron (outside the US only). Accepted types may vary by location, and prepaid cards are not accepted.
- Google may ask for a valid government ID and a credit card, both in your legal name. You must be 18 or older.
- Since early 2024, new personal accounts must prove they have access to an Android device through the Play Console mobile app.
- Personal accounts created after 2023-11-13 must run a closed test with at least 12 testers, each opted in continuously for at least 14 days, before applying for production access. A tester who opts out and back in restarts the 14-day run.
> I fetched both Help pages directly today (2026-10-15). Neither shows a revision date, so the evidence is current but undated. Help 14151465 says 'a minimum of 12 testers who have been opted in continuously for at least 14 days' and applies to 'personal developer accounts created after November 13, 2023'. Help 6112435 confirms: US$25 one-time; 'Prepaid cards are not accepted'; ID and card may be requested in your legal name; 18+; Android device verification for new personal accounts. Two parts were not checked against a primary source: that an Indian card needs international transactions enabled, and the rupee conversion.

### F7. A Play listing can be built without local Node or JDK. PWABuilder (web) wraps the site as a Trusted Web Activity via Bubblewrap and outputs a signed .aab plus a generated signing.keystore. The site must then serve /.well-known/assetlinks.json containing the SHA-256 from Play Console > App integrity > App signing (Play re-signs the app). Until that is in place the TWA shows a browser address bar.
*Confidence: high*

PWABuilder docs (docs/builder/android.md on GitHub main): the download zip contains an .aab for Play; the 'New' key option generates signing.keystore and signing-key-info.txt, which the owner must keep for every future update; deploy assetlinks.json to <host>/.well-known/assetlinks.json; after upload 'Google Play re-signs your app', so add the Play App Signing SHA-256 to sha256_cert_fingerprints and redeploy; requires a manifest and HTTPS, Android 7.0+ (API 24), and a device or emulator for testing. No service worker is mentioned. In this repo app/main.py mounts StaticFiles(directory=static, html=True) at '/', so static/.well-known/assetlinks.json would be served at the right path (check its Content-Type is application/json). The TWA is bound to the domain, which is another reason a stable hostname (F2) comes first.

Sources: https://raw.githubusercontent.com/pwa-builder/PWABuilder/main/docs/builder/android.md · https://docs.pwabuilder.com/#/builder/android

### F8. Android developer verification starts enforcement on 2026-09-30 only in Brazil, Indonesia, Singapore and Thailand, with the global rollout listed as '2027 and beyond'. Apps on Google Play using Play App Signing are auto-registered. Off-Play distribution needs an Android Developer Console Full Distribution account (US$25; waived for Limited Distribution, up to 20 devices). No page reviewed mentions PWAs or WebAPKs.
*Confidence: medium — **decision-critical***

developer.android.com/developer-verification/guides: June 2026 early access; July/Aug 2026 Console API and limited distribution; '2026-09-30 enforcement begins in Brazil, Indonesia, Singapore, and Thailand'; '2027 and beyond: global rollout'. India is not named for 2026. Limited distribution: no ID, up to 20 devices. Full distribution: identity verification required. FAQ (updated 2026-03-25): 'The $25 fee for the Full Distribution account in the ADC … We are waiving the fee for developers who qualify for a Limited Distribution account'. FAQ (2025-09-03): with Play App Signing, 'Your eligible apps will be part of the automatic registration process'. Inference: Chrome-installed WebAPKs are minted and signed by Google's WebAPK server, not the developer, so the PWA route needs no verification from the owner. The docs do not say this explicitly. A Play TWA is covered by the Play account's verification. Only a sideloaded APK (e.g. PWABuilder's unsigned or self-signed output, outside Play) would face ADC registration once India is reached in 2027+.

Sources: https://developer.android.com/developer-verification/guides · https://developer.android.com/developer-verification/guides/faq

**Verifier: confirmed.** Corrected: Confirmed, with the WebAPK inference flagged as unverified.
- Enforcement starts 2026-09-30 for users in Brazil, Indonesia, Singapore and Thailand. The global rollout is '2027 and beyond'. India is not named anywhere.
- Apps distributed through Google Play are registered automatically. The FAQ (2025-09-03) says apps that use Play App Signing join automatic registration.
- Full Distribution in the Android Developer Console (ADC) costs US$25 and requires identity verification.
- Limited Distribution needs no identity verification, allows up to 20 devices, and its fee is waived (FAQ, 2026-03-25).
- A FAQ entry from 2026-07-15 says that for sideloading and other stores, 'these new verification requirements won't apply to your app yet'.
- No official page mentions PWAs or WebAPKs. That Chrome-minted WebAPKs are exempt is still only an inference.
> The guides page (last updated 2026-08-18) gives the timeline word for word: 'Starting September 30, 2026 ... Brazil, Indonesia, Singapore, and Thailand', and '2027 and beyond global rollout'. It also has the Full vs Limited table (ID yes/no; 'up to 20 devices') and says 'You will automatically be registered if you distribute your app through Google Play.'

The FAQ (page last updated 2026-09-30) has: the $25 Full Distribution fee and Limited Distribution waiver (entry dated 2026-03-25); Play App Signing apps 'part of the automatic registration process' (2025-09-03); 'plan to complete your verification before the global rollout begins in 2027' (2026-07-15). PWA, WebAPK and Chrome do not appear in either page.

I also ran one web search on WebAPKs. It found no official statement exempting WebAPKs, but none including them either.

### F9. Play's AI-generated content policy requires apps that generate AI content to include in-app reporting or flagging of offensive content without leaving the app. Its examples are text-to-text chatbots where chatting is 'a central feature of the app', so a claim-verifier answer app very likely qualifies.
*Confidence: medium*

Play Console Help 13985936 (no visible date; footer ©2026): apps generating AI content 'must contain in-app user reporting or flagging features' that let users report offensive content to developers without exiting the app, and must prevent Restricted Content (child exploitation, Deceptive Behavior). Whether a single-shot verifier counts as a 'chatbot' is not spelled out. Assume yes: a 'Report this answer' control that records the job_id (never the user's message, per invariant 10) is needed before submitting to Play, and is cheap to add to the web page too.

Sources: https://support.google.com/googleplay/android-developer/answer/13985936?hl=en

### F10. An optional service worker must never cache API or SSE responses or serve a stale index.html after a deploy. The safe minimum is either no service worker at all (Chrome supplies a default offline page for installed apps) or one that handles only navigations, network-first, falling back to a precached offline.html. All other requests are left to the network (no respondWith).
*Confidence: medium*

Chrome's installability blog says Chrome 'launched a default custom page' offline for installed sites with no service worker. Stale-index risk: a cache-first handler for '/' serves the old page until the service worker updates. The browser re-checks sw.js on navigations, and serving sw.js with Cache-Control: no-cache plus calling skipWaiting/clients.claim keeps updates prompt. Not caching '/' at all (network-first, cache only offline.html) removes the risk. Do not intercept /api/*, /reports/*, /stream/* (SSE) or uploads: return without calling respondWith so the browser handles them natively. Repo-specific risk to check for free: StaticFiles takes MIME types from Python's mimetypes, which on Windows can be overridden by the registry. A service-worker script served as text/plain fails to register, and .webmanifest may be unknown, so name the file manifest.json or set the type explicitly. Confirm with curl -I locally before deploying. A service worker becomes REQUIRED only for the file/POST share target (F4).

Sources: https://developer.chrome.com/blog/update-install-criteria · https://developer.chrome.com/docs/capabilities/web-apis/web-share-target

### F11. Samsung Internet installs PWAs as WebAPKs on Samsung devices (a launcher entry, the app switcher, system settings), uses the same Chromium manifest criteria, and supports share_target from version 12.0.
*Confidence: medium*

MDN (2026-10-06): on Samsung devices Samsung Internet installs WebAPKs and is listed among the Chromium browsers using the name/icons/start_url/display criteria. caniuse: share_target supported in Samsung Internet 12.0–30. I did not verify whether Samsung's ambient 'install' badge still needs a service worker. Check on a Samsung phone.

Sources: https://developer.mozilla.org/en-US/docs/Web/Progressive_web_apps/Guides/Making_PWAs_installable · https://caniuse.com/mdn-manifests_webapp_share_target

## Options

| Option | Monthly cost | Fits | For | Against |
|---|---|---|---|---|
| Android PWA (Chrome / Samsung Internet WebAPK) with Web Share Target | $0 extra (needs the stable HTTPS host that the hosting decision provides anyway) | Best fit for Indian Android users: installs from the site in one tap, appears in the launcher and the Android share sheet, and updates whenever the site deploys. No store, no fee, no review, no developer verification. | Zero cost; only static files: manifest.json, icons (192, 512, 512 maskable), apple-touch-icon 180, plus a <link rel=manifest> and theme-color in index.html; No service worker needed to install; Chrome gives a default offline page; share_target GET (title/text/url) lets reel links from Instagram, YouTube or Facebook 'Share' land straight in the app; Optional tiny service worker adds file sharing (images, voice notes) via POST share_target, kept client-side until the user taps Check, so no paid check runs unconfirmed; Every deploy is live immediately if index.html is never cached by a service worker | Needs a stable HTTPS origin; trycloudflare Quick Tunnels change hostname and do not support SSE; Sharing a WhatsApp TEXT message is very likely impossible (no Share-to-apps for text); users copy and paste. Media sharing from WhatsApp is unverified; Phones without Google Play services get a plain shortcut rather than a WebAPK, and some OEM ROMs need a 'home screen shortcuts' permission; The install prompt is controlled by Chrome's heuristics; offer an in-page button via beforeinstallprompt |
| iOS / iPadOS 26 home-screen web app (Safari 'Open as Web App') | $0 | Comes almost free with the Android work: the same manifest and apple-touch-icon give iPhone users a standalone app icon. The user installs manually via Share > Add to Home Screen. | Every site added to the Home Screen opens as a web app by default on iOS 26, even without a manifest; Uses manifest name, icons, start_url, display:standalone, theme_color and id; apple-touch-icon (180 px) overrides; Install also works from Chrome, Edge and Firefox on iOS (16.4+); File input, camera and microphone (MediaRecorder 14.5+) are available, so image and voice upload work | No install prompt or beforeinstallprompt; users need a one-line 'Share, then Add to Home Screen' hint; No share_target, so nothing can be shared INTO the app from WhatsApp; paste only; Maskable icons are ignored; storage is separate from Safari's; Same stable-origin requirement as Android |
| Google Play listing via Trusted Web Activity (PWABuilder) | $0 monthly; US$25 one-time Play registration (about ₹2,100–2,300 on an international-enabled Indian card) | Optional later step for discoverability and trust ('it's on the Play Store'). Not needed to put an installable app in users' hands, and it brings process overhead out of proportion to tens of checks a day. | PWABuilder runs in the browser: no local Node or JDK; it outputs a signed .aab and a keystore; The TWA is the same site full-screen; web deploys update the app content without a new release; Play App Signing apps are auto-registered for Android developer verification | New personal account: a closed test with at least 12 testers opted in for 14 consecutive days before production, plus Android device verification and a government ID; Must host /.well-known/assetlinks.json with the Play App Signing SHA-256, or the URL bar shows; Play's AI-content policy needs an in-app 'report offensive answer' feature; also a privacy policy, Data safety form and content rating; The keystore must be kept safe forever; losing it blocks updates; Play's review and policy exposure (e.g. deceptive-behaviour rules on a fact-checking app) is a new compliance surface |

## Recommendation (the researcher's)

The minimum to ship costs $0 and needs no app store. Once the app is on a stable HTTPS domain (not a trycloudflare Quick Tunnel: its hostname changes and it does not carry SSE):

(1) Add these files to static/, which app/main.py already serves at '/':
- manifest.json with name, short_name, id '/', start_url '/', scope '/', display 'standalone', background_color, theme_color
- icons: 192 px and 512 px PNG with purpose 'any', and a separate 512 px PNG with purpose 'maskable' that keeps the logo inside the central 80% safe zone
- apple-touch-icon.png at 180 px

(2) In index.html, add <link rel=manifest>, <link rel=apple-touch-icon>, <meta name=theme-color>, plus a small 'Install app' button wired to beforeinstallprompt (Android) and a one-line 'Share, then Add to Home Screen' hint on iOS.

(3) Add share_target with method GET (params title, text and url, all mapped into the composer) so reel links shared from Instagram, YouTube or Facebook prefill the text box. Never auto-submit: the user taps Check, so the daily cap and triage still gate all spend.

Ship with NO service worker at first. Chrome no longer needs one to install and shows its own offline page, and having none removes the stale-index.html risk entirely. Add one only for phase 2, file and voice-note sharing via a POST multipart share_target. That service worker should intercept only the share POST, stash the file and 303-redirect, and on other navigations go network-first with an offline.html fallback. It must never touch /api, /reports, /stream or uploads, and sw.js must be served as JavaScript with Cache-Control: no-cache.

Before building the WhatsApp-share story, verify on a real Android phone (free) what WhatsApp's share sheet offers. Text very likely cannot be shared; media is unverified. For WhatsApp text, the planned WhatsApp or Telegram bot is the real answer.

Defer Play/TWA. It costs only US$25 one-time, but it requires 12 testers for 14 consecutive days, an ID-verified account, assetlinks.json, an in-app 'report this answer' control under the AI-content policy, and a privacy policy and data-safety form, which is not worth it at tens of checks a day.

## Unknowns

- Whether WhatsApp for Android (stable, Oct 2026) offers the system share sheet for text messages, and whether it does for images, voice notes and videos. No source confirmed either; test on a real phone after installing.
- Whether Chrome Android in 2026 still uses engagement heuristics (the old 30 s plus one click) before showing the automatic install mini-infobar or ambient badge. The service-worker checks are confirmed removed in Chromium source; the heuristic timing was not traced.
- Whether Samsung Internet's install badge still needs a service worker (not verified).
- Whether India is in the 2027 Android developer verification rollout and on what date, and an explicit statement that Chrome WebAPKs are out of scope (inferred, because Google signs WebAPKs).
- Whether a single-shot claim verifier counts as a 'chatbot' under Play's AI-content policy; assumed yes.
- Play's current target-API-level deadline for new apps (PWABuilder normally handles it; not checked).
- What MIME types the FastAPI StaticFiles mount sends for .js and .webmanifest on the deployment host (Windows registry mimetypes can break service-worker registration); check with a free curl -I.
- Exact share_target accept values WhatsApp uses for voice notes (likely audio/ogg; codecs=opus or audio/opus, .opus); list both MIME types and extensions.

## Verifier on the recommendation

The general direction follows from the evidence: a $0 PWA on a stable HTTPS domain, with Play/TWA deferred. But three parts do not hold as written.

1. **The install button conflicts with having no service worker.** The plan says ship with no service worker AND add an 'Install app' button wired to beforeinstallprompt. Chrome's own post (developer.chrome.com/blog/update-install-criteria, last updated 2023-12-05) says the service-worker fetch() requirement was dropped only for installing from the browser menu (Chrome 108 on mobile, 112 on desktop). It says 'the algorithm that displays the install prompt still requires the presence of a fetch() handler'. The newer web.dev install-criteria page (2024-09-19) no longer lists a service worker, so the primary sources disagree.
   - Fix: on a real Android phone, test whether beforeinstallprompt fires with no service worker.
   - Either way, show a fallback hint ('⋮ menu → Install app'), so the button is not the only way to install.
   - Also confirm on the same phone that share_target works in an app installed from the menu without a service worker.

2. **The WhatsApp bot may not be allowed.** The plan says 'for WhatsApp text, the planned WhatsApp or Telegram bot is the real answer'. Meta's Terms for the WhatsApp Business Platform (§4.7, last modified 2026-09-23) say AI/ML providers are 'strictly prohibited' from using the platform 'when such technologies are the primary (rather than incidental or ancillary) functionality'. Meta alone decides what counts as primary. A claim verifier whose answer is produced by Claude is plausibly 'primary' AI functionality.
   - The AI-providers exception and pricing page lists only Brazil, Italy and the EU/EEA countries. India (+91) is not on it.
   - So for an Indian audience, the Telegram bot is the safe answer. A WhatsApp bot needs the owner to decide on this risk first.

3. **'$0' assumes a hosting choice.** A named Cloudflare Tunnel needs a domain whose DNS is on Cloudflare, which is a small yearly domain cost. A cloud host with its own fixed HTTPS subdomain would keep it at $0.

The rest holds. Polling /reports works without SSE. The Play cost and the 12-tester/14-day burden are confirmed. Android developer verification does not touch India before 2027, and does not clearly touch WebAPKs at all.

## Verifier: missed

- Meta's WhatsApp Business Platform terms, §4.7 (last modified 2026-09-23), ban AI providers whose AI is the 'primary functionality', in effect since 2026-01-15. India is not among the exception markets on Meta's AI-providers pricing page (that page lists Brazil, Italy and the EU/EEA). This directly decides whether the planned WhatsApp bot is allowed, and the research does not mention it.
- On Chrome, a beforeinstallprompt-driven install prompt may still need a service worker with a fetch handler (Chrome blog, 2023-12-05). Installing from the browser menu does not need one since Chrome 108 on mobile. The 'no service worker' and 'Install app button' plans need to be tested together on a real phone.
- A named Cloudflare Tunnel needs a domain on Cloudflare DNS, which costs a small yearly fee. The alternative is a free host subdomain. The recommendation's '$0' depends on this choice.
- On sideloaded or off-Play APKs, the Android developer verification FAQ (2026-07-15) says the requirements 'won't apply to your app yet', and recommends verifying before the 2027 global rollout. There is no official word either way on WebAPKs, so 'the PWA needs no verification' is still an inference.
- The beforeinstallprompt event and share_target are Chromium-only, and installed-app sharing works only on Android. On iOS the app can be added to the home screen but cannot be a share target. So the 'share a reel into the app' flow will not work for iPhone users.

