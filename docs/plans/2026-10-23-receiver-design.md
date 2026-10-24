# Design: NestDash custom Cast receiver app — 2026-10-23

Status: validated with owner. Architecture changes need re-validation (see AGENTS.md).

## 1. Architecture

```
┌── LAN PC ───────────────┐        CASTV2 / TLS :8009         ┌── Nest Hub ─────────┐
│ sender/sender.py daemon │ ── LAUNCH (APP_ID) ─────────────► │ receiver/ web app   │
│  data + decisions       │ ── {type:"state"} JSON ─────────► │  (GitHub Pages,     │
│  runs tile commands     │ ◄─ {type:"event"} touch events ── │   HTTPS required)   │
└─────────────────────────┘                                   └─────────────────────┘
```

Fixed by platform constraints:
- Receiver page must be HTTPS with a valid cert → hosted free on GitHub Pages.
- All real data flows over the Cast custom-message channel (namespace
  `urn:x-cast:com.hotep.nestdash`), so the receiver page is static and dumb —
  no mixed-content issues, no CORS.
- Custom (unpublished) app IDs only launch on devices whitelisted in the
  Cast SDK Console. Hub UUID: `3c5a917f-b352-b2c5-5f25-b25f1206abdf`.
- `dashboard.py` (PNG → Default Media Receiver loop) remains the fallback
  until the receiver app is proven end-to-end.

## 2. App: "Kiosk Dashboard v2" — 3 pages, dark theme, 1024×600

- **home** — big clock, date, weather + hi/lo (open-meteo, no API key)
- **status** — PC stats pushed by sender (psutil when available: CPU/RAM/disk, uptime)
- **actions** — ≤6 tappable tiles from `sender/actions.json`;
  `{id, label, command, confirm}`; `confirm:true` requires a second tap
  within 5 s

Pages are entries in the state JSON; adding a page is a config change, not a
redeploy. Swipe horizontally to change pages; taps send
`{type:"event", id:"<tile-id>", action:"tap"}`.

## 3. Protocol (v1)

```
PC → hub : {type:"state", v:1, page:"home", pages:{home:{...}, status:{...},
            actions:{tiles:[...]}}, ts:<unix>}
hub → PC : {type:"event", v:1, id:"btn-ping", action:"tap"}
```

Receiver behavior: renders latest state; if no state for N=30 s shows
"waiting for PC…" plus last-update age. Demo mode (`?demo=1`) renders canned
state and logs taps on-screen — used for browser testing without a hub.

## 4. Failure modes

| Failure | Behavior |
|---|---|
| sender dies | receiver shows waiting screen + staleness age |
| hub reboot / app killed | sender relaunches when running app_id changes |
| Wi-Fi blip | sender reconnect loop w/ backoff; state carries ts |
| tile command fails | tile flashes red; error text in next state push |
| destructive tile | confirm:true → "tap again within 5 s" |
| APP_ID not found | whitelist propagation delay (min–hours); retry |

Known limit: no auth on the command channel. Home LAN threat model only.

## 5. Testing

1. Receiver in desktop Chrome `?demo=1` — layout, swipe, tap echo
2. `sender/sender.py --selftest` — prints state JSON, exit 0
3. Real hub: launch APP_ID, verify state render + tap round-trip
4. Soak: overnight; reboot hub once; confirm auto-recovery

## 6. Human-only setup steps (~15 min + propagation wait)

1. Cast SDK Console (console.developers.google.com → Cast) → register Custom
   Receiver "NestDash", URL = GitHub Pages URL → note APP_ID (possible
   one-time $5 fee)
2. Register test device with hub UUID above (hub must be online)
3. Put APP_ID in `.env` as `NESTDASH_APP_ID`; never commit it

## 7. Out of scope (v1)

- Auth/encryption on the command channel
- More than 3 pages / 6 tiles
- Camera feeds, calendars, third-party integrations
- chipicopwn / custom-OS work (firmware too new; see AGENTS.md history)
