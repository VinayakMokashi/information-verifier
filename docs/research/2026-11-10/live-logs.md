# What two weeks of live running showed (2026-10-28 to 2026-11-10)

status: complete

Read from the live logs (`logs\`, content-free by design), the dashboard's
spend API and Windows' own event logs. All free and read-only; the real
database was never opened.

## Up and running

- The PC restarted on **2026-10-31 at 01:36** (Windows Update after the
  owner's pause ended). The scheduled task started the app and the bot by
  itself 21 s later, with nobody needing to act. The supervisor's log
  shows starts at 01:33, 01:35 and 01:36: the update restarted the PC more
  than once. There has been no restart since. **This is go-live §5d,
  passed in practice.**
- Spend to date: **$3.2661 over 32 checks**. The last 7 days come to
  $0.1594; the most recent check was on 2026-11-04. The caps were still
  raised ($5 a day, 200 checks), overdue for the revert.

## L-1. Scanners crash the static-file server on Windows: a 500 and a traceback per probe

- On 2026-11-03 at 09:37–09:38, a scanner requested paths such as `/*`,
  `/*/[id]`, `/*update.cgi*` and `/*/[slug]`. That made 16 tracebacks in
  `logs\app-2026-11-03.log`.
- Each one: `OSError: [WinError 123] The filename, directory name, or
  volume label syntax is incorrect: '…\static\*'`, raised from Starlette's
  StaticFiles lookup. On Windows, `*` (and `? < > | " :`) cannot be in a
  file name, and the lookup catches only "not found" errors.
- So the visitor got **500** where it should be **404**, and the log
  filled with a long traceback.
- Nothing leaked, and the server stayed up. But every scanner on the
  internet can do this, and the noise can hide a real error.
- Fix: a request for a name that cannot be a file is simply not found
  (404). Test it first, with the `/*` path.

## L-2. The PC loses its internet for hours, and the site and the bot go down with it

- `logs\bot-*.log` has **19,867** "getUpdates failed" lines since
  2026-10-28. Almost all are **ConnectError** (no network at all), 5 s
  apart, which is the bot's retry pause.
  - 10-30: 4,398 (about 6.1 h)
  - 11-05: 4,456 (about 6.2 h)
  - 11-08: 7,303 (about 10.1 h, 11:00–22:24)
  - 11-09: 2,350 (about 3.3 h)
  - a few on other days.
  - That is **about 27 hours down since 30 Oct**, roughly 89% uptime.
- Windows confirms it.
  - The WLAN log (Microsoft-Windows-WLAN-AutoConfig/Operational, 8001
    and 8003) shows the Wi-Fi dropping and reconnecting repeatedly on
    11-08. It reconnected for good at **22:24:44**, and the bot's errors
    end at **22:24:40**.
  - Kernel-Power 172: "Connectivity state in standby: Disconnected,
    Reason: **NIC compliance**", meaning the Wi-Fi adapter does not hold
    the connection in Modern Standby.
  - Yet sleep is Never and the display never turns off, on AC and on
    battery, and there was no power-source change since 11-05. So it was
    plugged in.
- Not a code bug. The cause is this PC's Wi-Fi, or the home network.
  Owner options, cheapest first:
  - a **wired Ethernet** connection;
  - in Device Manager → the Wi-Fi adapter → Power Management, untick
    "Allow the computer to turn off this device to save power";
  - check the router or ISP on the outage days.
- **The owner alerts cannot report this**: they need the internet that
  is gone. A free outside uptime monitor would. It pings
  https://informationverifier.com every few minutes and emails or
  messages him; it sees only the public URL.
- Small code improvement: the bot retries every 5 s however long the
  outage lasts, which made 7,303 log lines on 11-08. A backoff that
  doubles to about 60 s keeps the log readable and reconnects within a
  minute of the network's return.

## L-3. The asyncio WinError 10054 traceback, again (harmless)

`logs\app-2026-11-04.log`: two "Exception in callback
_ProactorBasePipeTransport._call_connection_lost … ConnectionResetError",
the known Windows Proactor noise when a client drops its socket. Already
on the to-do list (silence it).
