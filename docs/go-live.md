# Going live — step 4: this PC, 24/7, at its own address

**For:** Vinayak, doing the owner's half of step 4 (decided 2026-10-15:
this PC behind a Cloudflare named tunnel, a .com, a cloud VM later).
Everything here is free except the domain (~$10.46 the first year).
The research behind each step is in
[docs/research/2026-10-15/home-tunnel.md](research/2026-10-15/home-tunnel.md)
and its verification; HANDOFF §0 lists the other go-live settings.

Each step says how to check it worked. Do them in order; stop at any
check that fails.

---

## 1. Before the domain (today, free)

1. **Sarvam:** Settings → Workspace → Data retention → Model APIs → **0
   days**. It only covers audio sent from then on. THEN put
   `SARVAM_ZERO_RETENTION=true` in `.env`. Only then does the privacy
   notice say Sarvam keeps none of it; until then it says Sarvam may keep
   it.
   - **Seen 2026-10-23 on the owner's account:** the workspace page is
     called **Data policy** (`/settings/workspace/data-policy`) and lists
     only **Voice Agents**. That covers call recordings, at 24 months.
     There is no Model APIs row, although Sarvam's docs describe one.
     So there is no switch for this app's speech-to-text.
   - Leave `SARVAM_ZERO_RETENTION` **unset**, so the notice keeps saying
     Sarvam may keep voice notes, which is true. Ask Sarvam support how
     to set Model APIs to "No retention".
   - This does not block the rest of go-live. The startup warning about
     it stays until it is settled.
2. **Anthropic:** a separate workspace for the public key, with a monthly
   spend limit; put that workspace's key in `.env` as `ANTHROPIC_API_KEY`.
   Checked against Anthropic's docs on 2026-10-23:
   - **Create the workspace:** platform.claude.com/settings/workspaces →
     **Create workspace**, then name it and pick a colour. Only an
     organisation admin can do it. The Default Workspace cannot take a
     spend limit, which is why this one is new.
   - **Spend limit:** on the same page, select the workspace → **Spend
     limits**. Use about **$35 a month** with an alert at about $25.
     The app's own $1 a day comes to $31 at most. A refusal at this
     limit pauses checking at no cost ("workspace API usage limits",
     app/providers/llm.py).
   - **The key:** platform.claude.com/settings/keys → **Create key**.
     Set Linked account to yourself, Expiration to **Never**, and
     **scope it to the new workspace**. The app sends no
     `anthropic-workspace-id` header, so an unscoped key fails every
     check with a 400. The secret is shown once.
   - Replace the value after `ANTHROPIC_API_KEY=` in `.env`. Disable the
     old key only after the first real check works on the new one.
3. **Telegram:** send `/id` to the bot; put the number in `.env` as
   `OWNER_CHAT_ID=` (restarts, budget and failures then reach your phone).
4. **Backups:** `BACKUP_DIR=` a OneDrive (or USB) folder in `.env`.
5. **What the privacy notice publishes:** `CONTACT_EMAIL=` (a role
   address, such as a new Gmail for the service, avoids publishing your
   own) and, if you want a name shown, `OPERATOR_NAME=`.
6. **This PC:**
   - Settings → Privacy & security → **Device encryption** on (Telegram's
     bot terms want stored data encrypted). Not every PC offers it on
     Windows Home. If yours doesn't, say so: PROJECT_PLAN §11 29 has the
     other way (encrypting the stored answers in the app).
   - Power: sleep **Never** when plugged in; lid close **Do nothing**.
   - Windows Update → Advanced → **Active hours 07:00–01:00**. Today's
     18:00–11:00 puts update restarts in the middle of the Indian day.

**Check:** start the app (`start.cmd`), open http://127.0.0.1:8000/ready —
`"status": "ready"`.

## 2. The domain

Buy a **.com** at Cloudflare Registrar (dash.cloudflare.com → Domain
Registration). Use a Visa, Mastercard or Amex enabled for international
online payments. Cloudflare requires 3-D Secure on Indian cards and lists
no RuPay or UPI. If the card is declined, buy it at any registrar and set
its nameservers to the two Cloudflare gives you when you add the site.

**Check:** the domain shows **Active** in the Cloudflare dashboard.

Then, in that dashboard:
- **Security → Bots: Bot Fight Mode OFF.** It cannot be scoped, and it
  would challenge the future WhatsApp webhook.
- **Turnstile → Add widget** for the domain (Managed). Put its two keys in
  `.env` as `TURNSTILE_SITE_KEY=` and `TURNSTILE_SECRET_KEY=`.

## 3. The tunnel (cloudflared is already installed)

In a PowerShell window (not as admin yet), with `<domain>` your .com:

```powershell
cloudflared tunnel login                 # a browser opens: pick <domain>
cloudflared tunnel create verifier       # prints the tunnel's id (a UUID)
cloudflared tunnel route dns verifier <domain>
```

Write `%USERPROFILE%\.cloudflared\config.yml`. Put the UUID in both
places, and keep the four ingress rules in this order:

```yaml
tunnel: <UUID>
credentials-file: C:\Users\<you>\.cloudflared\<UUID>.json
ingress:
  # The spending dashboard already 404s through any proxy; this fences it
  # at the edge too, with its JSON (verification of home-tunnel.md, F12).
  - hostname: <domain>
    path: ^/(dashboard|api/v1/admin/)
    service: http_status:404
  - hostname: <domain>
    service: http://127.0.0.1:8000
  - service: http_status:404
```

**Check:** `cloudflared tunnel ingress validate` says OK, and
`cloudflared tunnel ingress rule https://<domain>/dashboard` names the
404 rule.

## 4. The settings that open the door

In `.env`: `PUBLIC_HOSTS=<domain>`. Without it every visitor is refused,
and the server prints each name it refused.

Start the app with `start.cmd`. Its window must NOT show any "PUBLIC_HOSTS
is set but …" line: Turnstile, CONTACT_EMAIL and SARVAM_ZERO_RETENTION
are each warned about until they are set.

Then, in a second window: `cloudflared tunnel run verifier`.

**Check, from your phone on mobile data (not the home Wi-Fi):**
- `https://<domain>` loads, and the privacy and terms links work.
- `https://<domain>/dashboard` is a 404.
- One check goes through and its answer streams in word by word. That
  last part is the one thing no document settled: whether Cloudflare
  streams the answer or buffers it. If it arrives all at once at the end,
  tell Claude. The fallback to polling still works, just less nicely.
- "Install app" or Share → Add to Home Screen works.

In @BotFather, set the bot's privacy policy to `https://<domain>/privacy`.

## 5. Making it run by itself

**cloudflared as a service** (PowerShell **as administrator**):

```powershell
mkdir C:\Windows\System32\config\systemprofile\.cloudflared
copy $env:USERPROFILE\.cloudflared\config.yml C:\Windows\System32\config\systemprofile\.cloudflared\
copy $env:USERPROFILE\.cloudflared\<UUID>.json C:\Windows\System32\config\systemprofile\.cloudflared\
```

In the copied `config.yml`, change `credentials-file:` to the new folder.
Then install the service, and tell it what to run. Installed without a
token, the service starts cloudflared with no arguments, and that runs
**no tunnel**. Cloudflare's own Windows page makes this registry change
as its steps 13–14; it was missing here until the re-check (F-5).

```powershell
cloudflared service install
$exe = (Get-Command cloudflared).Source
Set-ItemProperty "HKLM:\SYSTEM\CurrentControlSet\Services\Cloudflared" ImagePath `
  ('"' + $exe + '" --config="C:\Windows\System32\config\systemprofile\.cloudflared\config.yml" tunnel run')
Restart-Service cloudflared
```

**Check:** `Get-Service cloudflared` shows Running, AND the site still
loads after closing the `tunnel run` window. The second half is the one
that catches a service running no tunnel.

**The app and the bot at boot.** `scripts\serve_forever.py` starts both
and restarts either if it stops. It writes `logs\app-*.log` and
`logs\bot-*.log` and tells your phone of each restart. Close `start.cmd`'s
two windows first, then register a task. As administrator, with the
project path and your Windows user name:

```powershell
$dir = "C:\Users\Vinayak Mokashi\Python Sab\Information_Verifier"
$action = New-ScheduledTaskAction -Execute "$dir\.venv\Scripts\python.exe" `
  -Argument "`"$dir\scripts\serve_forever.py`"" -WorkingDirectory $dir
$trigger = New-ScheduledTaskTrigger -AtStartup
$settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries `
  -DontStopIfGoingOnBatteries -StartWhenAvailable `
  -ExecutionTimeLimit ([TimeSpan]::Zero) -RestartCount 999 `
  -RestartInterval (New-TimeSpan -Minutes 1)
Register-ScheduledTask -TaskName "Information Verifier" -Action $action `
  -Trigger $trigger -Settings $settings -User "$env:USERNAME" -Password (Read-Host "Windows password")
```

A password is needed to run with nobody signed in. With a Microsoft
account, give that account's password, not the PIN. `Read-Host` shows
it as you type, so make sure nobody is watching the screen.

If that is refused, the fallback is a separate **local** standard account
for the service. It needs more than the project folder (re-check F-10):
Python, ffmpeg and your BACKUP_DIR live in YOUR profile, which only you
can read. Without Python and ffmpeg the task fails before anything
starts. Without BACKUP_DIR every backup fails (review G-2). Run this in
the SAME administrator window as the block above, because it uses its
`$dir`. Put in the account's name and your BACKUP_DIR exactly as it is
in `.env`:

```powershell
$account = "<the service account>"
$backup = "<your BACKUP_DIR>"
$python = ((Get-Content "$dir\.venv\pyvenv.cfg") -match '^home') -replace '^home\s*=\s*', ''
$ffmpeg = Split-Path (Get-Command ffmpeg).Source
icacls $dir /grant "${account}:(OI)(CI)M"
icacls $python /grant "${account}:(OI)(CI)RX"
icacls $ffmpeg /grant "${account}:(OI)(CI)RX"
icacls $backup /grant "${account}:(OI)(CI)M"
[Environment]::SetEnvironmentVariable("Path",
  [Environment]::GetEnvironmentVariable("Path", "Machine") + ";$ffmpeg", "Machine")
```

Then register the task with `-User $account` and that account's password.

**Check, before any restart:** `Start-ScheduledTask "Information Verifier"`.
Within a minute:
- `logs\supervisor-<today>.log` shows both started;
- http://127.0.0.1:8000/ready says `"ready"`, which covers ffmpeg too,
  as whatever account the task runs as;
- today's `ledger-<date>.db` is in BACKUP_DIR, and `logs\app-<today>.log`
  has no "housekeeping … failed" line. A failing step also alerts your
  phone.

Then restart the PC and don't sign in: from your phone, the site answers
and the bot replies.

## If something goes wrong

- **Everything stops:** first read `logs\supervisor-<today>.log`. If it
  shows the app and the bot running, they are fine: check the tunnel
  (`Get-Service cloudflared`) and the internet instead. Only if the
  supervisor is not running: sign in, run `start.cmd`, and read its
  windows. A second bot refuses to start anyway; only one may run.
- **One part keeps restarting:** your phone gets an alert. Read
  `logs\app-<today>.log` or `logs\bot-<today>.log`.
- **Taking it offline:** in the project folder,
  `New-Item data\serve_forever.stop`. The supervisor stops the bot, lets
  checks already running finish (up to 5 minutes), stops the app, and its
  task ends. `logs\supervisor-<today>.log` then says "stopped". Then
  `Stop-Service cloudflared`. Task Scheduler's **End** is a hard kill:
  checks in flight are lost but still paid for, so use it only if the stop
  file is ignored.
- **Bringing it back:** `Start-Service cloudflared`, then
  `Start-ScheduledTask "Information Verifier"` (or restart the PC). The
  supervisor removes any stop file left behind.
- **Changing the tunnel's config.yml later:** the service reads its own
  copy in `C:\Windows\System32\config\systemprofile\.cloudflared\`. Edit
  that copy, then `Restart-Service cloudflared`.
