/* NestDash receiver — protocol v1 (docs/plans/2026-10-23-receiver-design.md)
   Modes: demo (?demo=1, canned state, taps log to #age), live (CAF SDK +
   sender), waiting (no state for 30 s). No build step, no framework. */
"use strict";
const NS = "urn:x-cast:com.hotep.nestdash";
const PAGES = ["home", "status", "actions"];
const STALE_AFTER_S = 30;

let state = null, lastState = 0, page = "home", demo = false;
const $ = (id) => document.getElementById(id);

function show(p) {
  page = PAGES.includes(p) ? p : "home";
  PAGES.forEach((x) => $("p-" + x).classList.toggle("active", x === page));
  document.querySelectorAll(".dot").forEach((d) => d.classList.toggle("active", d.dataset.p === page));
}

function render() {
  if (!state) return;
  show(state.page || page);
  const h = state.pages.home || {};
  $("clock").textContent = h.clock || "--:--";
  $("date").textContent = h.date || "";
  $("wx").textContent = h.weather || "";
  $("hilo").textContent = h.hilo || "";
  $("stats").innerHTML = Object.entries(state.pages.status || {})
    .map(([k, v]) => `<div class="stat"><span>${k}</span><b>${v}</b></div>`).join("");
  const tiles = $("tiles");
  tiles.innerHTML = "";
  ((state.pages.actions || {}).tiles || []).forEach((t) => {
    const el = document.createElement("div");
    el.className = "tile"; el.textContent = t.label; el.dataset.id = t.id;
    if (t.result) { el.textContent += " — " + t.result;
      el.classList.add(t.result === "ok" ? "flash-ok" : "flash-err"); }
    el.onclick = () => tap(el, t.id);
    tiles.appendChild(el);
  });
}

function tap(el, id) {
  if (demo) { $("age").textContent = "demo tap: " + id; return; }
  if (el.dataset.confirm) { el.dataset.confirm = ""; el.classList.remove("confirm"); }
  else if ((el.dataset.confirmNeeded === "1")) {
    el.dataset.confirm = "1"; el.classList.add("confirm");
    setTimeout(() => { el.classList.remove("confirm"); el.dataset.confirm = ""; }, 5000);
  }
  send({ type: "event", v: 1, id, action: "tap", page });
}

function send(msg) {
  if (demo) return;
  // sendCustomMessage verified in live caf_receiver_framework.js bundle.
  try {
    const ctx = window.cast && cast.framework && cast.framework.CastReceiverContext.getInstance();
    ctx && ctx.sendCustomMessage(NS, undefined, msg);
  } catch (e) { console.warn("send failed", e); }
}

function onState(s) { state = s; lastState = Date.now(); render(); }

function tick() {
  const age = state ? Math.round((Date.now() - lastState) / 1000) : -1;
  $("wait").style.display = age < 0 || age > STALE_AFTER_S ? "flex" : "none";
  if (age >= 0) $("age").textContent = "updated " + age + "s ago";
  $("waitage").textContent = state ? "last state " + age + "s ago" : "no state received";
}

function start() {
  demo = new URLSearchParams(location.search).has("demo");
  $("net").textContent = demo ? "demo" : "live";
  setInterval(tick, 1000); tick();

  // gesture: swipe horizontally between pages (touch + mouse drag)
  let x0 = null;
  const down = (e) => { x0 = (e.touches ? e.touches[0].clientX : e.clientX); };
  const up = (e) => {
    if (x0 === null) return;
    const x1 = (e.changedTouches ? e.changedTouches[0].clientX : e.clientX);
    const dx = x1 - x0; x0 = null;
    if (Math.abs(dx) < 60) return;
    const i = PAGES.indexOf(page);
    show(PAGES[Math.min(PAGES.length - 1, Math.max(0, i + (dx < 0 ? 1 : -1)))]);
  };
  addEventListener("touchstart", down, { passive: true });
  addEventListener("touchend", up, { passive: true });
  addEventListener("mousedown", down); addEventListener("mouseup", up);

  if (demo) {
    onState(demoState()); setInterval(() => onState(demoState()), 5000);
    return;
  }
  // Bootstrap verified against googlecast/CastReceiver sample + live bundle.
  try {
    const ctx = cast.framework.CastReceiverContext.getInstance();
    const opts = new cast.framework.CastReceiverOptions();
    opts.maxInactivity = 3600;          // stay up; sender daemon manages lifecycle
    ctx.addCustomMessageListener(NS, (ev) => ev.data && ev.data.type === "state" && onState(ev.data));
    ctx.start(opts);
  } catch (e) { console.warn("CAF SDK unavailable; staying in waiting mode", e); }
}

function demoState() {
  const now = new Date();
  return { type: "state", v: 1, page: page, ts: Math.floor(now.getTime() / 1000),
    pages: {
      home: { clock: now.toTimeString().slice(0, 5), date: now.toDateString(),
              weather: "72\u00b0F clear (demo)", hilo: "Hi 85\u00b0  Lo 60\u00b0" },
      status: { cpu: "12%", ram: "48%", disk: "61%", uptime: "3d 4h" },
      actions: { tiles: [
        { id: "btn-ping", label: "Ping PC" }, { id: "btn-refresh", label: "Refresh" },
        { id: "btn-ip", label: "Show IP" }, { id: "btn-demo4", label: "Demo 4" }] } } };
}

addEventListener("DOMContentLoaded", start);
