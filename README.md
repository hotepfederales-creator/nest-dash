# NestDash — Nest Hub (2nd Gen) dashboard & interactive receiver

Turn a Google Nest Hub 2nd Gen (MPN GUIK2, LAN name "Master bedroom", IP 192.168.3.102)
into a PC-driven dashboard, then into a fully interactive touchscreen app.

## Status

| Piece | State |
|---|---|
| `dashboard.py` — PNG clock+weather loop, cast via Default Media Receiver | ✅ **running in production** on the LAN |
| `receiver/` — custom Cast receiver web app (touch, 3 pages) | 🚧 scaffold, demo mode works |
| `sender/` — daemon: state push + tap/command execution | 🚧 scaffold, `--selftest` works |
| Google Cast app registration (APP_ID) | ⏳ human step, see design doc §4 |

## Quick start

```bash
# 1. Legacy PNG dashboard (works now, no registration needed)
python dashboard.py            # loops forever; env: NEST_IP LAT LON PORT REFRESH_S

# 2. Receiver app — local test, no hub needed
#    open receiver/index.html?demo=1 in Chrome; taps log to on-screen console

# 3. Sender daemon
python sender/sender.py --selftest   # prints the state JSON it would push
```

## Layout

- `dashboard.py` — v1: renders PNG, serves over HTTP, re-casts to hub every 60 s
- `receiver/` — Cast receiver web app (host on GitHub Pages; HTTPS required)
- `sender/` — Python daemon; owns data, pushes state, runs tile commands
- `docs/plans/2026-10-23-receiver-design.md` — validated design; read before changing architecture

See `AGENTS.md` for working rules and the verified-vs-TODO list.
