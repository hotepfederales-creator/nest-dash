"""NestDash sender daemon — protocol v1 (docs/plans/2026-10-23-receiver-design.md).

Pushes state JSON to the NestDash receiver app on the Nest Hub and executes
tile commands from actions.json. Uses only pychromecast.

Usage:
  python sender.py --selftest        # print state JSON, exit 0 (no hub needed)
  python sender.py                   # daemon loop (requires NESTDASH_APP_ID)
Env: NEST_IP (default 192.168.3.102), NESTDASH_APP_ID (or .env in repo root)
"""
import json
import os
import subprocess
import sys
import time
import urllib.request
from datetime import datetime

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
NEST_IP = os.environ.get("NEST_IP", "192.168.3.102")
LAT = os.environ.get("LAT", "33.4484")     # Phoenix (device timezone)
LON = os.environ.get("LON", "-112.0740")
PUSH_INTERVAL_S = 10


def env_file():
    """Tiny .env loader — no python-dotenv dependency."""
    p = os.path.join(ROOT, ".env")
    if os.path.exists(p):
        for line in open(p, encoding="utf-8"):
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                os.environ.setdefault(k.strip(), v.strip())


def load_actions():
    with open(os.path.join(HERE, "actions.json"), encoding="utf-8") as f:
        return [t for t in json.load(f)["tiles"] if not t.get("disabled")]


def build_state(tile_results):
    """Assemble the v1 state payload. Mirrors receiver/app.js render()."""
    now = datetime.now()
    pages = {
        "home": {
            "clock": now.strftime("%I:%M %p").lstrip("0"),
            "date": now.strftime("%A, %B ") + str(now.day),
            "weather": "", "hilo": "",
        },
        "status": pc_stats(),
        "actions": {"tiles": [
            {k: t.get(k) for k in ("id", "label", "confirm")} |
            ({"result": tile_results[t["id"]]} if t["id"] in tile_results else {})
            for t in load_actions()]},
    }
    try:
        url = (f"https://api.open-meteo.com/v1/forecast?latitude={LAT}&longitude={LON}"
               "&current=temperature_2m,weather_code&daily=temperature_2m_max,temperature_2m_min"
               "&temperature_unit=fahrenheit&timezone=auto")
        with urllib.request.urlopen(url, timeout=10) as r:
            d = json.load(r)
        pages["home"]["weather"] = f"{round(d['current']['temperature_2m'])}\u00b0F"
        pages["home"]["hilo"] = (f"Hi {round(d['daily']['temperature_2m_max'][0])}\u00b0  "
                                 f"Lo {round(d['daily']['temperature_2m_min'][0])}\u00b0")
    except Exception as e:  # weather is non-critical; receiver shows blanks
        print("weather unavailable:", e)
    return {"type": "state", "v": 1, "page": "home", "pages": pages,
            "ts": int(time.time())}


def pc_stats():
    stats = {}
    try:
        import psutil
        stats["cpu"] = f"{psutil.cpu_percent(interval=0.3):.0f}%"
        stats["ram"] = f"{psutil.virtual_memory().percent:.0f}%"
        stats["disk"] = f"{psutil.disk_usage('/').percent:.0f}%" if os.name != "nt" \
            else f"{psutil.disk_usage('C:').percent:.0f}%"
        up = time.time() - psutil.boot_time()
        stats["uptime"] = f"{up // 86400:.0f}d {up % 86400 // 3600:.0f}h"
    except ImportError:
        stats["hint"] = "pip install --user psutil"
    return stats


def run_tile(tile_id, actions, results):
    """Execute a tile command; record 'ok' or the error tail for the next push."""
    tile = next((t for t in actions if t["id"] == tile_id), None)
    if not tile or not tile.get("command"):
        results[tile_id] = "ok"
        return
    try:
        out = subprocess.run(tile["command"], shell=True, capture_output=True,
                             text=True, timeout=30, cwd=ROOT)
        tail = (out.stdout or out.stderr).strip().splitlines()
        results[tile_id] = "ok" if out.returncode == 0 else (tail[-1] if tail else f"exit {out.returncode}")
        if tail and out.returncode == 0:
            results[tile_id] = tail[-1][:40]
    except Exception as e:
        results[tile_id] = str(e)[:40]


def main():
    env_file()
    if "--selftest" in sys.argv:
        print(json.dumps(build_state({}), indent=2))
        return

    app_id = os.environ.get("NESTDASH_APP_ID")
    if not app_id:
        sys.exit("set NESTDASH_APP_ID (see design doc §6 — human-only registration step)")

    import pychromecast
    from pychromecast.controllers import BaseController

    class NestDash(BaseController):
        def __init__(self):
            super().__init__(namespace="urn:x-cast:com.hotep.nestdash")

        def receive_message(self, _msg, data):
            if data.get("type") == "event" and data.get("action") == "tap":
                print("EVENT", data, flush=True)
                run_tile(data["id"], load_actions(), results)
                push(cast, self)   # immediate refresh after a tap
            return True

    results: dict = {}
    cast = None

    def connect():
        cs, _b = pychromecast.get_chromecasts(known_hosts=[NEST_IP])
        c = next(x for x in cs if x.cast_info.host == NEST_IP)
        c.wait(10)
        controller = NestDash()
        # register_handler lives on socket_client (verified in installed source)
        c.socket_client.register_handler(controller)
        return c, controller

    def launch(c):
        # start_app(app_id) verified against installed pychromecast source.
        try:
            c.start_app(app_id)
        except AttributeError:
            c.socket_client.send_message(
                {"type": "LAUNCH", "appId": app_id}, inc_by=1)
        time.sleep(10)  # receiver page load + CAF handshake

    def push(c, controller):
        try:
            # send_message(data, *, inc_session_id, callback_function,
            # no_add_request_id) - verified in installed pychromecast source.
            controller.send_message(build_state(results))
        except Exception as e:
            print("push failed:", e)

    while True:  # outer reconnect loop (design §4: Wi-Fi blips, hub reboots)
        try:
            if cast is None:
                cast, controller = connect()
                launch(cast)
            elif getattr(cast.status, "app_id", None) != app_id:
                launch(cast)
            push(cast, controller)
            time.sleep(PUSH_INTERVAL_S)
        except KeyboardInterrupt:
            break
        except Exception as e:
            print("reconnecting after:", e)
            cast = None
            time.sleep(10)


if __name__ == "__main__":
    main()
