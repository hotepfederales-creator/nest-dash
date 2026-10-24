"""Nest Hub dashboard: render clock+weather PNG, serve it, cast it to the hub.

Usage:
  python dashboard.py --once   # render + cast once, report status, exit
  python dashboard.py          # loop: refresh cast every REFRESH_S
Env overrides: NEST_IP, LAT, LON, PORT
"""
import os
import sys
import time
import threading
import urllib.request
from datetime import datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from io import BytesIO

import pychromecast
from PIL import Image, ImageDraw, ImageFont

NEST_IP = os.environ.get("NEST_IP", "192.168.3.102")
LAT = os.environ.get("LAT", "33.4484")   # Phoenix (device timezone)
LON = os.environ.get("LON", "-112.0740")
PORT = int(os.environ.get("PORT", "8765"))
REFRESH_S = int(os.environ.get("REFRESH_S", "60"))
W, H = 1024, 600  # Nest Hub 2nd gen screen

WMO = {0: "clear", 1: "mostly clear", 2: "partly cloudy", 3: "overcast",
       45: "fog", 48: "rime fog", 51: "light drizzle", 53: "drizzle", 55: "heavy drizzle",
       61: "light rain", 63: "rain", 65: "heavy rain", 71: "light snow", 73: "snow",
       75: "heavy snow", 80: "rain showers", 95: "thunderstorm", 96: "t-storm w/ hail"}


def font(size, bold=True):
    for name in ("segoeuib.ttf", "segoeui.ttf", "arialbd.ttf", "arial.ttf"):
        try:
            return ImageFont.truetype(f"C:\\Windows\\Fonts\\{name}", size)
        except OSError:
            continue
    return ImageFont.load_default()


def local_ip():
    s = __import__("socket").socket(__import__("socket").AF_INET, __import__("socket").SOCK_DGRAM)
    try:
        s.connect((NEST_IP, 8009))
        return s.getsockname()[0]
    finally:
        s.close()


def fetch_weather():
    url = (f"https://api.open-meteo.com/v1/forecast?latitude={LAT}&longitude={LON}"
           "&current=temperature_2m,weather_code&daily=temperature_2m_max,temperature_2m_min"
           "&temperature_unit=fahrenheit&timezone=auto")
    with urllib.request.urlopen(url, timeout=10) as r:
        d = __import__("json").load(r)
    c, dy = d["current"], d["daily"]
    return {"temp": round(c["temperature_2m"]), "cond": WMO.get(c["weather_code"], "?"),
            "hi": round(dy["temperature_2m_max"][0]), "lo": round(dy["temperature_2m_min"][0])}


_png = b""
_hits = [0]


def render():
    global _png
    try:
        wx = fetch_weather()
    except Exception as e:
        wx = {"temp": "--", "cond": f"weather unavailable", "hi": "--", "lo": "--"}
        print("weather fetch failed:", e)
    img = Image.new("RGB", (W, H), (12, 14, 20))
    d = ImageDraw.Draw(img)
    now = datetime.now()
    d.text((60, 60), now.strftime("%I:%M %p").lstrip("0"), font=font(170), fill=(235, 238, 245))
    d.text((66, 290), now.strftime("%A, %B ") + str(now.day), font=font(64), fill=(150, 158, 175))
    # weather block, bottom
    d.text((66, 420), f"{wx['temp']}\u00b0F  {wx['cond']}", font=font(84), fill=(120, 200, 255))
    d.text((66, 515), f"Hi {wx['hi']}\u00b0  Lo {wx['lo']}\u00b0", font=font(48), fill=(150, 158, 175))
    buf = BytesIO()
    img.save(buf, "PNG")
    _png = buf.getvalue()
    print(f"rendered {len(_png)} bytes at {now:%H:%M:%S}")


class DashHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-Type", "image/png")
        self.send_header("Content-Length", str(len(_png)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(_png)
        _hits[0] += 1

    def log_message(self, *a):
        pass


def main():
    once = "--once" in sys.argv
    render()
    httpd = ThreadingHTTPServer(("0.0.0.0", PORT), DashHandler)
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    print(f"serving on http://{local_ip()}:{PORT}/dashboard.png")

    casts, browser = pychromecast.get_chromecasts(known_hosts=[NEST_IP])
    c = next(x for x in casts if x.cast_info.host == NEST_IP)
    c.wait(10)
    url = f"http://{local_ip()}:{PORT}/dashboard.png"

    def cast_once():
        c.play_media(url + f"?t={int(time.time())}", "image/png", title="Dashboard")
        time.sleep(8)
        st = c.media_controller.status
        print(f"app={c.status.display_name!r} player={st.player_state} "
              f"content={st.status_text if hasattr(st, 'status_text') else ''} http_hits={_hits[0]}")

    cast_once()
    if once:
        c.disconnect()
        httpd.shutdown()
        return
    while True:
        time.sleep(REFRESH_S)
        render()
        cast_once()


if __name__ == "__main__":
    main()
