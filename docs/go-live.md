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
2. **Anthropic:** a separate workspace for the public key, with a monthly
   spend limit; put that workspace's key in `.env` as `ANTHROPIC_API_KEY`.
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
Then:

```powershell
cloudflared service install
```

**Check:** `Get-Service cloudflared` shows Running, and the site still
loads after closing the `tunnel run` window.

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

A password is needed to run with nobody signed in. If your account signs
in with a PIN or a Microsoft account and this fails, the research's advice
is a separate **local** standard account for the service. That account
needs read and write access to the project folder.

**Check:** restart the PC and don't sign in. From your phone, the site
answers and the bot replies. `logs\supervisor-<today>.log` shows both
started.

## If something goes wrong

- **Everything stops:** sign in, run `start.cmd`, and read its windows.
- **One part keeps restarting:** your phone gets an alert. Read
  `logs\app-<today>.log` or `logs\bot-<today>.log`.
- **Taking it offline:** Task Scheduler → "Information Verifier" → End,
  then `Stop-Service cloudflared`. Its children stop with it.
