# AGENTS.md — working rules for NestDash

Small repo. Keep it small. YAGNI ruthlessly: no framework, no build step, no
dependency beyond `pychromecast`, `Pillow`, and optionally `psutil`.

## Ground truth

- Device: Nest Hub 2nd Gen "Master bedroom" @ 192.168.3.102 (UUID
  `3c5a917f-b352-b2c5-5f25-b25f1206abdf`), firmware 3.80.555360.
- `dashboard.py` is the live fallback — do not break it while receiver work is
  in progress. It runs as a background process on the LAN PC.
- The full design (validated with the owner) is
  `docs/plans/2026-10-23-receiver-design.md`. Architecture changes require
  re-validation, not silent edits.

## Commands

```bash
python sender/sender.py --selftest      # state builder + JSON out; must exit 0
python -c "import ast; ast.parse(open('dashboard.py').read()); ast.parse(open('sender/sender.py').read())"  # syntax check
# receiver: open receiver/index.html?demo=1 in a browser; no headless test yet
```

No test framework yet. If you add one, keep it stdlib (`unittest`), and wire
the two checks above into it.

## Verified vs TODO (as of 2026-10-23)

Verified on real hardware:
- CASTV2 control from LAN PC (pychromecast), volume/app control
- Unauthenticated Eureka API read (`:8008/setup/eureka_info`)
- PNG cast to Default Media Receiver; hub fetches from local HTTP server
- hub firmware too new for the chipicopwn bootloader exploit (do not retry)

TODO / unverified — verify against current docs before relying on them:
- Raw LAUNCH fallback in sender.py (start_app is verified; fallback is not)
- Whether the console still charges $5 for receiver registration
- Live hub launch of the registered APP_ID (blocked on human registration)

## Conventions

- Secrets and identifiers that may rotate (APP_ID) go in `.env` (gitignored)
  or environment variables — never in commits.
- `actions.json` tile commands run as shell on the LAN PC. `confirm: true`
  is mandatory for anything mutating.
- Message protocol is versioned (`v:1`). Bump and document breaking changes
  in the design doc.
- No auth on the command channel — home-LAN threat model only. Do not expose
  ports beyond the LAN.

## Agent workflow

1. Read the design doc before touching architecture.
2. Small, single-purpose commits; say what you verified in the commit body.
3. Anything you could not verify gets a `TODO-verify` comment, not silence.
