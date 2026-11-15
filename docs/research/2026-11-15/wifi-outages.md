# The Wi-Fi outages, 2026-11-10 to 2026-11-15: the PC's link sticks

status: complete

All free and read-only: the bot's logs (content-free), Windows' WLAN and
Kernel-Power event logs, `Get-NetAdapter`, `powercfg` and the adapter's
registry key. Follows L-2 in `docs/research/2026-11-10/live-logs.md`.

## Since 10 Nov: about 20 more hours down

The bot's ConnectError runs of 10 minutes or more:

| From | To | Hours |
|---|---|---|
| 11-10 13:01 | 11-10 16:05 | 3.1 |
| 11-11 00:39 | 11-11 01:51 | 1.2 |
| 11-11 01:58 | 11-11 04:26 | 2.5 |
| 11-11 16:05 | 11-12 01:03 | **9.0** |
| 11-12 01:41 | 11-12 04:36 | 2.9 |

There were also several shorter runs. 13, 14 and 15 Nov were nearly
clean (428, 5 and 21 failure lines).

## What the event logs show: Windows says "connected", nothing gets through

- The 9-hour outage: the Wi-Fi reconnected at **11-11 16:05:39**. There
  was no Wi-Fi event at all until **11-12 01:03:11**, when the **driver**
  dropped and remade the link. The bot's failures stopped at that same
  minute. For 9 hours, Windows reported the Wi-Fi as connected while no
  traffic passed.
- The same pattern on 11-10: failures 13:01–16:05, then "disconnected
  by the driver" at 16:03:55, reconnected at 16:05:14. The last failure
  was at 16:05:13.
- 11-12 01:40: the driver dropped the link and it stayed down until
  04:36:53. The failures ran 01:41–04:36.
- Most disconnects give the reason "The network is disconnected by the
  driver" or "a temporary-disconnect request". Every Kernel-Power 172
  "NIC compliance" event lasts about 2 seconds. Those are not the
  outages.

So each long outage ended when the link was remade, not when an outside
line came back. Most likely the PC's adapter or its driver. The router
cannot be ruled out: it may need the link remade too.

## The adapter

- **Realtek RTL8852AE WiFi 6 PCIe**, in an **HP ENVY x360 13-ay1xxx**.
- **Driver 6001.10.351.0, dated 2022-08-26**, more than four years old.
- **No wired Ethernet adapter on this laptop.** Every other adapter is a
  VPN, Bluetooth or virtual one.
- "Allow the computer to turn off this device to save power" is **on**
  (the default): the adapter's class key has no `PnPCapabilities`
  value.
- The power plan's wireless "Power Saving Mode" is Maximum Performance
  on AC (0), Medium Power Saving on battery (2).
- `Get-NetAdapterPowerManagement` fails here ("A device attached to the
  system is not functioning"), so the registry was read instead.

## Options

Owner's side, cheapest first:
1. Untick the power-saving box: Device Manager → the Realtek adapter →
   Power Management.
2. Update the Wi-Fi driver from HP (HP Support Assistant, or HP's
   support page for this model), or through Windows Update's optional
   driver updates.
3. A USB-to-Ethernet adapter and a cable to the router: the most
   reliable, and it bypasses the Wi-Fi entirely.
4. A free outside uptime monitor, which emails him when the site is
   down. The owner alerts cannot do this: they need the internet that
   is gone.

Code side (free to build, not started):
- A watchdog in the supervisor: after N minutes with no connection,
  remake the Wi-Fi link. Remaking the link is what ended every long
  outage above.
- The bot's retry backoff (L-2).
