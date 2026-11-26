// Gast-app: één pagina per reservatie (link met een geheim token: ?r=<token>).
// Haalt alles op via GET /api/checkin/<token> en toont het volgens de fase van het verblijf:
//   nog niet ingecheckt: uitleg + formulier (eerst de gegevens, dan de rest);
//   before / code: te doen (betalen), toegang (code zodra die er is), gegevens, verblijf, praktisch;
//   stay: toegang met schuifknoppen bovenaan; after: bedankt, review, eventueel betalen.
// POST /api/checkin/<token> bewaart de gegevens, /unlock opent een deur, /pay meldt dat de gast op Betalen klikte.
// API: zelfde site (lokaal) of de Function App in Azure, ingesteld in config.js bij de uitrol.
const API = window.CHECKIN_API || "";
(function () {
  const params = new URLSearchParams(location.search);
  // Link uit een WhatsApp-bericht van TST: TST gebruikt de WhatsApp-sjablonen van PRD, waarvan de knop naar dit
  // (PRD-)formulier wijst. Door naar het formulier van TST: zelfde adres met "-tst" achter het eerste deel
  // (checkin.hotellucca.be -> checkin-tst.hotellucca.be). Nooit naar een ander domein.
  if (params.get("env") === "tst" && !location.hostname.split(".")[0].endsWith("-tst") && location.hostname.includes(".")) {
    const host = location.hostname.split(".");
    host[0] += "-tst";
    params.delete("env");
    location.replace("https://" + host.join(".") + "/?" + params.toString());
    return;
  }
  params.delete("env");
  // Vanaf het beginscherm (Android) opent de app zonder ?r=: dan de laatst geopende verblijfspagina
  const token = params.get("r") || (() => { try { return localStorage.getItem("gastapp:last") || ""; } catch (e) { return ""; } })();
  let lang = (params.get("lang") || (navigator.language || "en").slice(0, 2)).toLowerCase();
  if (!I18N[lang]) lang = "en";
  let langChosenByGuest = !!params.get("lang");
  let data = null;
  let offline = false;
  let editing = false;
  let formFilled = false;  // het formulier één keer vullen, niet overschrijven terwijl de gast typt
  const doorState = {};  // deur -> ready, busy, done, fail
  let doorStatus = {};  // deur -> {online, locked} volgens Salto (alleen tijdens het verblijf)
  const CACHE_KEY = "gastapp:" + token;
  const PAY_KEY = "gastapp-pay:" + token;
  const PAY_PENDING_MS = 30 * 60 * 1000;

  const $ = (id) => document.getElementById(id);
  const esc = (s) => String(s == null ? "" : s).replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
  function fill(s) {
    return s.replace("{voornaam}", data ? data.first_name : "").replace("{hotel}", data && data.hotel ? data.hotel.name : "");
  }
  function t(key, ...args) {
    const v = I18N[lang][key] !== undefined ? I18N[lang][key] : I18N.en[key];
    if (typeof v === "function") return v(...args);
    return fill(v || "");
  }
  function store(key, value) { try { value === null ? localStorage.removeItem(key) : localStorage.setItem(key, value); } catch (e) { /* privé-modus */ } }
  function stored(key) { try { return localStorage.getItem(key); } catch (e) { return null; } }

  // ------------------------------------------------------------ iconen (lijntekeningen)
  const svg = (d, size = 20, w = 2) => `<svg width="${size}" height="${size}" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="${w}" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">${d}</svg>`;
  const I = {
    cal: (s) => svg('<rect x="3.5" y="5" width="17" height="15" rx="2"></rect><path d="M3.5 10h17M8 3v4M16 3v4"></path>', s),
    bed: (s) => svg('<path d="M3 18V7"></path><path d="M21 18v-5a3 3 0 0 0-3-3h-8v6"></path><path d="M3 15h18"></path><circle cx="6.5" cy="11" r="1.5"></circle>', s),
    person: (s) => svg('<circle cx="12" cy="8" r="4"></circle><path d="M4 21a8 8 0 0 1 16 0"></path>', s),
    door: (s) => svg('<path d="M5 21V4a1 1 0 0 1 1-1h12a1 1 0 0 1 1 1v17"></path><path d="M3 21h18"></path><circle cx="15" cy="12" r="1"></circle>', s),
    key: (s) => svg('<circle cx="8" cy="15" r="4"></circle><path d="M11 12l9-9"></path><path d="M17 6l3 3"></path>', s),
    clock: (s) => svg('<circle cx="12" cy="12" r="9"></circle><path d="M12 7v5l3 2"></path>', s),
    check: (s) => svg('<path d="M5 12.5l4.5 4.5L19 7.5"></path>', s || 16, 2.4),
    chev: (s) => svg('<path d="M9 6l6 6-6 6"></path>', s || 16, 2.4),
    card: (s) => svg('<rect x="3" y="5.5" width="18" height="13" rx="2"></rect><path d="M3 10h18"></path><path d="M7 15h4"></path>', s || 22),
    pin: (s) => svg('<path d="M12 21s-7-6.2-7-11.5a7 7 0 0 1 14 0C19 14.8 12 21 12 21z"></path><circle cx="12" cy="9.5" r="2.5"></circle>', s),
    wifi: (s) => svg('<path d="M2 8.5a15 15 0 0 1 20 0"></path><path d="M5 12a10 10 0 0 1 14 0"></path><path d="M8.5 15.5a5 5 0 0 1 7 0"></path><circle cx="12" cy="19" r="1"></circle>', s),
    desk: (s) => svg('<path d="M3 10h18"></path><path d="M5 10v10M19 10v10"></path><path d="M8 10V6a4 4 0 0 1 8 0v4"></path>', s),
    phone: (s) => svg('<path d="M5 4h4l2 5-2.5 1.5a11 11 0 0 0 5 5L15 13l5 2v4a2 2 0 0 1-2 2A16 16 0 0 1 3 6a2 2 0 0 1 2-2z"></path>', s),
    chat: (s) => svg('<path d="M21 12a8 8 0 0 1-11.6 7.1L4 20.5l1.4-5A8 8 0 1 1 21 12z"></path>', s),
    mail: (s) => svg('<rect x="3" y="5" width="18" height="14" rx="2"></rect><path d="M3 7l9 6 9-6"></path>', s),
    share: (s) => svg('<path d="M12 3v12"></path><path d="M8 7l4-4 4 4"></path><path d="M6 11H5a1 1 0 0 0-1 1v8a1 1 0 0 0 1 1h14a1 1 0 0 0 1-1v-8a1 1 0 0 0-1-1h-1"></path>', s),
    plus: (s) => svg('<rect x="4" y="4" width="16" height="16" rx="3"></rect><path d="M12 8v8M8 12h8"></path>', s),
    dots: (s) => svg('<circle cx="12" cy="5" r="1.3"></circle><circle cx="12" cy="12" r="1.3"></circle><circle cx="12" cy="19" r="1.3"></circle>', s),
    lock: (s) => svg('<rect x="5" y="11" width="14" height="10" rx="2"></rect><path d="M8 11V7a4 4 0 0 1 8 0v4"></path>', s || 24),
    arrow: () => svg('<path d="M5 12h14"></path><path d="M13 6l6 6-6 6"></path>', 26, 2.6),
    cup: (s) => svg('<path d="M4 9h13v5a5 5 0 0 1-5 5H9a5 5 0 0 1-5-5z"></path><path d="M17 10h1.5a2.5 2.5 0 0 1 0 5H17"></path><path d="M8 3v3M12 3v3"></path>', s),
    star: () => svg('<path d="M12 3.5l2.6 5.4 5.9.8-4.3 4.1 1 5.8-5.2-2.8-5.2 2.8 1-5.8-4.3-4.1 5.9-.8z"></path>', 22),
    alert: () => svg('<circle cx="12" cy="12" r="9"></circle><path d="M12 7.5v5.5"></path><circle cx="12" cy="16.5" r="0.6"></circle>', 22),
    nonet: () => svg('<path d="M3 3l18 18"></path><path d="M8.5 15.5a5 5 0 0 1 7 0"></path><path d="M5 12a10 10 0 0 1 4.5-2.6"></path><path d="M14.5 9.4A10 10 0 0 1 19 12"></path><circle cx="12" cy="19" r="1"></circle>', 24),
    spin: () => '<svg class="spin" width="26" height="26" viewBox="0 0 24 24" fill="none" aria-hidden="true"><circle cx="12" cy="12" r="9" stroke="#D5D8E0" stroke-width="3"></circle><path d="M12 3a9 9 0 0 1 9 9" stroke="currentColor" stroke-width="3" stroke-linecap="round"></path></svg>',
  };

  // ------------------------------------------------------------ datums
  const locale = () => lang + "-BE";
  function day(iso) { const [y, m, d] = iso.slice(0, 10).split("-").map(Number); return new Date(y, m - 1, d); }
  const fmt = (date, opts) => new Intl.DateTimeFormat(locale(), opts).format(date);
  const fmtDay = (iso) => fmt(day(iso), { weekday: "short", day: "numeric", month: "short" });
  const fmtDayYear = (iso) => fmt(day(iso), { weekday: "short", day: "numeric", month: "short", year: "numeric" });
  const fmtMoment = (iso) => {
    const d = new Date(iso);
    return fmt(d, { weekday: "short", day: "numeric", month: "short" }) + " " + fmt(d, { hour: "2-digit", minute: "2-digit" });
  };
  const todayIso = () => { const d = new Date(); return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`; };

  // ------------------------------------------------------------ bouwstenen
  const badge = (cls, icon, text) => `<span class="badge ${cls}">${icon}${esc(text)}</span>`;
  const row = (icon, label, value, extra = "") => `<div class="row"><span class="ri">${icon}</span><div>${label ? `<div class="rl">${esc(label)}</div>` : ""}<div class="rv">${value}</div>${extra}</div></div>`;
  const note = (icon, html) => `<div class="note">${icon}<span>${html}</span></div>`;
  const codeHtml = (pin) => `<div class="code" aria-label="${esc(pin.split("").join(" "))} ↵">${esc(pin)}<span class="enter">↵</span></div>`;
  const rooms = () => (data.rooms || []);
  const roomCode = (room) => ((data.access && data.access.codes) || []).find((c) => c.room === room);
  function roomSub(r) {
    const name = r.name && (r.name[lang] || r.name.en);
    if (name) return name.charAt(0).toUpperCase() + name.slice(1);
    return r.floor ? t("floor_n", r.floor) : "";
  }
  function payPending() {
    const at = Number(stored(PAY_KEY) || 0);
    return at && Date.now() - at < PAY_PENDING_MS && data.pay && !data.pay.paid;
  }
  function payOpen() { return data.pay && !data.pay.paid && data.pay.open > 0.004; }

  // ------------------------------------------------------------ kaarten
  function guestHtml() {
    const rs = rooms();
    const roomLine = rs.length > 1
      ? rs.map((r) => t("room_n", r.room)).join(` ${t("and")} `).replace(/^(.)/, (c) => c.toUpperCase())
      : [rs.length ? t("room_n", rs[0].room) : "", data.room_type, rs.length ? roomSub(rs[0]) : ""].filter(Boolean).join(" · ");
    const people = [data.guest_count ? t("persons", data.guest_count) : "", rs.length > 1 ? t("n_rooms", rs.length) : "", t("nights", data.nights)].filter(Boolean).join(" · ");
    const dates = data.phase === "stay"
      ? t("checkout_until", data.times.checkout_until) + ", " + fmtDay(data.departure)
      : t("range", fmtDay(data.arrival), fmtDayYear(data.departure));
    return `<h1>${esc(data.first_name)} ${esc(data.last_name)}</h1>
      <div class="meta">${I.cal()}<span>${esc(dates)}</span></div>
      ${roomLine ? `<div class="meta">${I.bed()}<span>${esc(roomLine)}</span></div>` : ""}
      <div class="meta">${I.person()}<span>${esc(people)}</span></div>`;
  }

  function stepsHtml() {
    const a = data.access || {};
    const pay = data.pay;
    const steps = [];
    steps.push([t("step_checkin"), data.completed ? "done" : "now", data.completed ? t("st_done") : t("st_todo")]);
    if (pay && pay.paid) steps.push([t("step_pay"), "done", t("st_done")]);
    else if (payOpen()) steps.push([t("step_pay"), data.completed ? "now" : "", data.completed ? t("st_todo") : t("st_later")]);
    else steps.push([t("step_pay"), "", t("st_later")]);
    const codes = (a.codes || []).length;
    steps.push([t("step_code"), codes ? "done" : "", codes ? t("st_done") : a.code_date && a.code_date > todayIso() ? t("st_from", fmtDay(a.code_date)) : t("st_later")]);
    steps.push([t("step_doors"), "", t("st_from", fmtDay(data.arrival))]);
    return `<ol class="steps">${steps.map(([label, cls, status], i) =>
      `<li class="${cls}"><span class="num">${cls === "done" ? I.check(16) : i + 1}</span><span class="sl">${esc(label)}</span><span class="ss">${esc(status)}</span></li>`).join("")}</ol>`;
  }

  function warningHtml() {
    return `<div class="note warn">${I.alert()}<span>${esc(t("link_warning"))}</span></div>`;
  }

  function introHtml() {
    return `<h2 class="ct"><span>${esc(t("intro_title"))}</span></h2>
      <p>${esc(t(data.completed ? "intro_done" : "intro_new"))}</p>
      ${stepsHtml()}
      <p class="muted">${esc(t("intro_keep"))}</p>
      ${warningHtml()}`;
  }

  function payItemHtml() {
    const p = data.pay;
    if (!p) return "";
    if (p.paid) {
      if (!stored(PAY_KEY)) return "";
      return `<div class="todo"><div class="todo-h"><span>${esc(t("pay_paid"))}</span>${badge("b-ok", I.check(), t("pay_paid"))}</div><div class="muted">${esc(t("pay_paid_text"))}</div></div>`;
    }
    if (!payOpen()) return "";
    const label = p.kind === "city_tax" ? t("pay_city_tax") : t("pay_balance");
    let body = "";
    if (p.tax) body += `<div class="muted">${esc(t("pay_tax_line", p.tax.persons, p.tax.nights, p.tax.rate))}</div>`;
    if (data.access && !data.access.room_paid) body += `<div class="muted">${esc(t("pay_room_first"))}</div>`;
    if (payPending()) {
      body += note(I.clock(), esc(t("pay_pending")));
      return `<div class="todo"><div class="todo-h"><span>${esc(label)}</span>${badge("b-wait", I.spin().replace('width="26" height="26"', 'width="16" height="16"'), t("badge_busy"))}</div><div class="big-amount">${esc(p.amount)}</div>${body}</div>`;
    }
    body += p.url
      ? `<a class="btn" id="pay-btn" href="${esc(p.url)}" target="_blank" rel="noopener">${I.card()}${esc(t("pay_button"))} ${esc(p.amount)}</a>`
      : note(I.clock(), esc(t("pay_soon")));
    return `<div class="todo"><div class="todo-h"><span>${esc(label)}</span><span>${esc(p.amount)}</span></div>${body}</div>`;
  }

  function todoHtml() {
    const item = payItemHtml();
    const open = payOpen() ? 1 : 0;
    const a = data.access || {};
    let rest = "";
    if (!item) {
      const codes = (a.codes || []).length;
      rest = `<p>${esc(codes ? t("all_ok_ready") : a.code_date && a.code_date > todayIso() ? t("all_ok_code", fmtDay(a.code_date)) : t("all_ok_soon"))}</p>`;
    } else if (open && !(a.codes || []).length && a.room_paid && a.code_date && a.code_date > todayIso()) {
      rest = note(I.clock(), esc(t("code_on", fmtDay(a.code_date))));
    }
    const head = open ? badge("b-todo", I.chev(), t("n_open", open)) : badge("b-ok", I.check(), t("all_ok"));
    return `<h2 class="ct"><span>${esc(t("card_todo"))}</span>${head}</h2>${item}${rest}`;
  }

  function sliderHtml(door, label) {
    const a = data.access;
    const win = a.unlock && a.unlock[door];
    if (!win) return "";
    const now = new Date();
    if (now > new Date(win.until)) return "";
    if (now < new Date(win.from)) {
      return `<button type="button" class="slide s-off" disabled aria-label="${esc(t("slide_from", fmtMoment(win.from)))}"><span class="knob">${I.lock()}</span><span>${esc(t("slide_from", fmtMoment(win.from)))}</span></button>`;
    }
    if (offline || !navigator.onLine) {
      return `<button type="button" class="slide s-nonet" disabled><span class="knob">${I.nonet()}</span><span>${esc(t("slide_nonet"))}</span></button>`;
    }
    const st = doorState[door] || "ready";
    if (st === "busy") return `<button type="button" class="slide end" aria-live="polite" disabled><span>${esc(t("slide_busy"))}</span><span class="knob">${I.spin()}</span></button>`;
    if (st === "done") return `<button type="button" class="slide end s-open" aria-live="polite" disabled><span>${esc(t("slide_done"))}</span><span class="knob">${svg('<path d="M5 12.5l4.5 4.5L19 7.5"></path>', 28, 3)}</span></button>`;
    if (st === "fail") return "";
    const text = t("slide_open", label);
    return `<button type="button" class="slide" data-door="${esc(door)}" aria-label="${esc(text)}"><span class="knob">${I.arrow()}</span><span>${esc(text)}</span></button>`;
  }

  function codeBlockHtml(door, pin, label) {
    if (doorState[door] === "fail") {
      return `<div class="fail" role="alert"><div class="fail-t">${I.alert()}<span>${esc(t("fail_title"))}</span></div>${codeHtml(pin)}<div class="muted" style="color:var(--text)">${esc(t("fail_text", pin))}</div></div>`;
    }
    return `<div class="codebox">${codeHtml(pin)}<div class="codelbl">${esc(label)}</div></div>`;
  }

  function tileHtml(kind, r) {
    const a = data.access;
    const codes = a.codes || [];
    const isFront = kind === "front";
    const title = isFront ? t("front_door") : r ? t("room_n", r.room) : t("room");
    const icon = isFront ? I.door(24) : r && r.own_entrance ? I.key(24) : I.bed(24);
    const sub = isFront ? (data.hotel.address || "").split(",")[0] : r ? roomSub(r) : "";
    const accessText = !isFront && r && r.own_entrance ? (r.access[lang] || r.access.en || "") : "";
    const door = isFront ? "front" : r ? "room:" + r.room : "";
    let pin = null;
    let label = t("code_label");
    if (isFront) {
      const viaFront = codes.filter((c) => { const rr = rooms().find((x) => x.room === c.room); return !rr || !rr.own_entrance; });
      if (viaFront.length) pin = viaFront[0].pin;
      if (viaFront.length > 1) label = t("code_label_multi");
    } else if (r) {
      const c = roomCode(r.room);
      pin = c ? c.pin : null;
    }
    let state = "";
    let body = "";
    if (pin) {
      state = data.phase === "stay" ? badge("b-ok", I.check(), t("badge_open")) : badge("b-wait", I.clock(16), t("st_from", fmtDay(data.arrival)));
      body = sliderHtml(door, isFront ? t("door_front") : t("door_room", r ? r.room : "")) + codeBlockHtml(door, pin, label);
    } else if (!a.room_paid && data.pay && !data.pay.paid) {
      state = badge("b-wait", I.clock(16), t("badge_no_code"));
      body = `<div class="codebox lock">${I.lock(26)}<b>${esc(t("pay_for_code"))}</b></div>`;
    } else {
      state = badge("b-wait", I.clock(16), t("badge_not_yet"));
      body = note(I.clock(), a.code_date && a.code_date > todayIso() ? esc(t("code_on", fmtDay(a.code_date))).replace(esc(fmtDay(a.code_date)), `<b>${esc(fmtDay(a.code_date))}</b>`) : esc(t("code_soon")));
    }
    const ds = pin && data.phase === "stay" ? doorStatus[door] : null;
    if (ds && ds.online === false) {
      body = `<div class="lockstate off">${I.nonet()}<span>${esc(t("lock_offline"))}</span></div>` + codeBlockHtml(door, pin, label);
    } else if (ds && ds.locked !== null && ds.locked !== undefined) {
      body = `<div class="lockstate ${ds.locked ? "" : "open"}">${ds.locked ? I.lock(20) : svg('<rect x="5" y="11" width="14" height="10" rx="2"></rect><path d="M8 11V7a4 4 0 0 1 7.5-2"></path>', 20)}<span>${esc(t(ds.locked ? "lock_locked" : "lock_unlocked"))}</span></div>` + body;
    }
    const later = pin ? "" : " later";
    return `<div class="tile${later}"><div class="tile-h"><div class="tile-t">${icon}<span>${esc(title)}</span></div>${state}</div>
      ${sub ? `<div class="tile-s">${esc(sub)}</div>` : ""}
      ${accessText ? note(I.pin(), esc(accessText)) : ""}${body}</div>`;
  }

  function accessHtml() {
    const a = data.access;
    let tiles = "";
    if (a.front_door) tiles += tileHtml("front");
    const rs = rooms();
    tiles += rs.length ? rs.map((r) => tileHtml("room", r)).join("") : tileHtml("room", null);
    const howto = (a.codes || []).length
      ? `<div class="howto"><div class="keypad" aria-hidden="true">${[1, 2, 3, 4, 5, 6, 7, 8, 9, "", 0].map((k) => `<span>${k}</span>`).join("")}<span class="go">↵</span></div><div style="font-size:15px"><b>${esc(t("howto_title"))}</b><br>${esc(t("howto_text"))}</div></div>`
      : "";
    return `<h2 class="ct"><span>${esc(t("card_access"))}</span></h2>${tiles}${howto}${(a.codes || []).length ? warningHtml() : ""}`;
  }

  function contactButtons() {
    const h = data.hotel;
    return (h.whatsapp ? `<a class="btn2" href="${esc(h.whatsapp)}" target="_blank" rel="noopener">${I.chat(22)}${esc(t("whatsapp"))}</a>` : "")
      + `<a class="btn2" href="tel:${esc(h.phone.replace(/\s/g, ""))}">${I.phone(22)}${esc(t("call"))}</a>`;
  }

  function stayHtml() {
    const tm = data.times;
    const rs = rooms();
    const roomVal = rs.length
      ? rs.map((r) => esc([t("room_n", r.room), rs.length === 1 ? data.room_type : ""].filter(Boolean).join(", ")) + (roomSub(r) ? "<br>" + esc(roomSub(r)) : "")).join("<br>")
      : esc(data.room_type);
    return `<h2 class="ct"><span>${esc(t("card_stay"))}</span></h2><div class="rows">
      ${row(I.cal(), t("arrival"), esc(fmtDayYear(data.arrival) + (tm.checkin_from ? ", " + t("from_time", tm.checkin_from) : "")))}
      ${row(I.cal(), t("departure"), esc(fmtDayYear(data.departure) + (tm.checkout_until ? ", " + t("until_time", tm.checkout_until) : "")),
        `<div class="muted">${esc(t("luggage"))}${data.access && data.access.front_door && tm.front_door_until ? " " + esc(t("front_until", tm.front_door_until)) : ""}</div>`)}
      ${roomVal ? row(I.bed(), rs.length > 1 ? t("rooms") : t("room"), roomVal) : ""}
      ${data.guest_count ? row(I.person(), t("guests"), esc(t("persons", data.guest_count))) : ""}
      ${tm.breakfast_from ? row(I.cup(), t("breakfast"), esc(t("range", tm.breakfast_from, tm.breakfast_until))) : ""}
    </div>`;
  }

  function practicalHtml(withButtons) {
    const h = data.hotel;
    const tm = data.times;
    const w = data.wifi;
    return `<h2 class="ct"><span>${esc(t(withButtons === "contact" ? "contact" : "card_practical"))}</span></h2><div class="rows">
      ${row(I.pin(), t("address"), esc(h.address), h.map_url ? `<a class="lnk" href="${esc(h.map_url)}" target="_blank" rel="noopener">${esc(t("open_map"))}</a>` : "")}
      ${withButtons !== "contact" && w ? row(I.wifi(), t("wifi"), esc(w.per_room ? t("wifi_room") : t("wifi_shared", w.name, w.password))) : ""}
      ${withButtons !== "contact" && tm.reception_from ? row(I.desk(), t("reception"), esc(t("range", tm.reception_from, tm.reception_until))) : ""}
      ${row(I.phone(), t("contact"), `<a href="tel:${esc(h.phone.replace(/\s/g, ""))}">${esc(h.phone)}</a><br><a href="mailto:${esc(h.email)}">${esc(h.email)}</a>`)}
    </div><div class="btnrow">${contactButtons()}</div>`;
  }

  function afterHtml() {
    return `<p class="thanks">${esc(t("after_title"))}</p><div class="muted">${esc(t("after_text"))}</div>`;
  }
  function reviewHtml() {
    return `<h2 class="ct"><span>${esc(t("card_review"))}</span></h2><div>${esc(t("review_text"))}</div>
      <a class="btn" href="${esc(data.hotel.review_url)}" target="_blank" rel="noopener">${I.star()}${esc(t("review_button"))}</a>`;
  }

  function detailsSummary() {
    $("details-rows").innerHTML = row(I.mail(), t("email"), esc(data.email))
      + (data.phone ? row(I.phone(), t("phone"), esc(data.phone)) : "");
  }

  // ------------------------------------------------------------ opbouw volgens de fase
  const CARD_IDS = ["message-card", "intro-card", "after-card", "todo-card", "access-card", "home-card", "contact-row", "details-card", "stay-card", "practical-card"];

  // ------------------------------------------------------------ op het beginscherm zetten
  // Android (Chrome, Edge, Samsung): de knop vraagt het toestel om de app te installeren. iPhone en iPad: Apple laat
  // dat niet toe vanuit een pagina, dus tonen we de drie tikken in Safari. Al op het beginscherm: geen kaart.
  let installPrompt = null;
  let homeHelp = false;
  const ua = navigator.userAgent || "";
  const isIos = /iPhone|iPad|iPod/.test(ua) || (navigator.platform === "MacIntel" && navigator.maxTouchPoints > 1);
  const standalone = () => window.matchMedia("(display-mode: standalone)").matches || navigator.standalone === true;
  window.addEventListener("beforeinstallprompt", (e) => { e.preventDefault(); installPrompt = e; if (data) renderCards(); });
  window.addEventListener("appinstalled", () => { installPrompt = null; store("gastapp:home", "1"); if (data) renderCards(); });

  // Alleen op een gsm of tablet: op een laptop heeft een icoon op het beginscherm geen zin.
  const mobile = () => /Android|iPhone|iPad|iPod|Mobi/i.test(navigator.userAgent)
    || (navigator.platform === "MacIntel" && navigator.maxTouchPoints > 1);  // iPad die zich als Mac voordoet

  function homeWanted() {
    return data && mobile() && data.state === "open" && data.phase !== "after" && !standalone()
      && !stored("gastapp:home") && !stored("gastapp:home-no:" + token);
  }

  function homeHtml() {
    const h = data.hotel;
    const icon = h.app_icon ? `<img class="home-icon" src="${esc(h.app_icon)}" alt="" width="56" height="56">` : "";
    let help = "";
    if (homeHelp) {
      const steps = isIos
        ? [[I.share(20), t("home_ios_1")], [I.plus(20), t("home_ios_2")], [I.check(20), t("home_ios_3")]]
        : [[I.dots(20), t("home_other_1")], [I.plus(20), t("home_other_2")]];
      help = `<ol class="home-steps">${steps.map(([ic, s]) => `<li><span class="home-step-ic">${ic}</span><span>${esc(s)}</span></li>`).join("")}</ol>`;
    }
    return `<div class="home-head">${icon}<div><b>${esc(t("home_title"))}</b><div class="muted">${esc(t("home_text"))}</div></div></div>
      ${homeHelp ? help : `<button class="btn" type="button" id="home-btn">${I.plus(22)}${esc(t("home_button"))}</button>`}
      <button class="linkbtn" type="button" id="home-no">${esc(t(homeHelp ? "home_done" : "home_no"))}</button>`;
  }

  function wireHome() {
    const b = $("home-btn");
    if (b) b.addEventListener("click", async () => {
      if (installPrompt) {
        installPrompt.prompt();
        const choice = await installPrompt.userChoice.catch(() => null);
        installPrompt = null;
        if (choice && choice.outcome === "accepted") store("gastapp:home", "1");
      } else {
        homeHelp = true;
      }
      renderCards();
    });
    const n = $("home-no");
    if (n) n.addEventListener("click", () => { store("gastapp:home-no:" + token, "1"); renderCards(); });
  }

  function applyApp(h) {
    // Icoon en naam op het beginscherm. Het manifest alleen voor Android: zonder manifest bewaart een iPhone de
    // volledige link (met ?r=), en die is nodig omdat de app op een iPhone haar eigen opslag krijgt.
    if (h.app_icon) $("touch-icon").href = h.app_icon;
    $("app-title").content = h.name;
    if (h.app_manifest && !isIos && !document.querySelector('link[rel="manifest"]')) {
      const l = document.createElement("link");
      l.rel = "manifest";
      l.href = h.app_manifest;
      document.head.appendChild(l);
    }
  }

  function place(order) {
    const cards = $("cards");
    CARD_IDS.forEach((id) => { $(id).hidden = !order.includes(id); });
    order.forEach((id) => cards.appendChild($(id)));
  }

  function showMessage(kind) {
    $("loading").hidden = true;
    $("guest").hidden = true;
    $("message-title").textContent = t(kind + "_title");
    $("message-text").textContent = t(kind + "_text");
    place(["message-card"]);
  }

  function renderCards() {
    if (!data) return;
    if (data.state !== "open") return showMessage(data.state);
    $("loading").hidden = true;
    $("offline").hidden = !(offline || !navigator.onLine);
    $("guest").hidden = data.phase === "after";
    $("guest").innerHTML = guestHtml();
    const set = (id, html) => { $(id).innerHTML = html; };
    let order;
    if (data.phase === "after") {
      set("after-card", afterHtml());
      if (data.hotel.review_url) set("intro-card", reviewHtml());
      set("todo-card", todoHtml());
      set("practical-card", practicalHtml("contact"));
      order = ["after-card"].concat(data.hotel.review_url ? ["intro-card"] : [], payOpen() ? ["todo-card"] : [], ["practical-card"]);
    } else if (!data.completed) {
      set("intro-card", introHtml());
      set("stay-card", stayHtml());
      set("practical-card", practicalHtml());
      if (homeWanted()) set("home-card", homeHtml());
      order = ["intro-card", "details-card"].concat(homeWanted() ? ["home-card"] : [], ["stay-card", "practical-card"]);
    } else if (data.phase === "stay") {
      set("access-card", accessHtml());
      set("contact-row", contactButtons());
      set("todo-card", todoHtml());
      set("stay-card", stayHtml());
      set("practical-card", practicalHtml());
      if (homeWanted()) set("home-card", homeHtml());
      order = ["access-card"].concat(homeWanted() ? ["home-card"] : [], ["contact-row"], payOpen() || payPending() ? ["todo-card"] : [], ["practical-card", "stay-card", "details-card"]);
    } else {
      set("intro-card", introHtml());
      set("todo-card", todoHtml());
      set("access-card", accessHtml());
      set("stay-card", stayHtml());
      set("practical-card", practicalHtml());
      if (homeWanted()) set("home-card", homeHtml());
      order = ["intro-card", "todo-card", "access-card"].concat(homeWanted() ? ["home-card"] : [], ["details-card", "stay-card", "practical-card"]);
    }
    place(order);
    renderDetails();
    wireDynamic();
    wireHome();
  }

  function renderDetails() {
    if (!data || data.state !== "open") return;
    const open = !data.completed || editing;
    $("form").hidden = !open;
    $("details-summary").hidden = open;
    $("details-badge").innerHTML = data.completed ? badge("b-ok", I.check(), t("details_done")) : badge("b-todo", I.chev(), t("badge_todo"));
    $("form-intro").textContent = data.completed ? t("form_intro_again") : t("start_here");
    if (!open) detailsSummary();
    const st = data.stairs && (data.stairs[lang] || data.stairs.en);
    $("stairs-box").hidden = !st;
    if (st) { $("stairs-q").textContent = st.q; $("stairs-text").textContent = st.text; $("stairs-text").hidden = !st.text; }
    const h = data.hotel;
    $("privacy-link").href = (h.privacy_urls && h.privacy_urls[lang]) || h.privacy_url;
  }

  function render() {
    document.documentElement.lang = lang;
    document.querySelectorAll("[data-t]").forEach((el) => (el.textContent = t(el.dataset.t)));
    document.querySelectorAll(".lang button").forEach((b) => b.classList.toggle("on", b.dataset.lang === lang));
    ["phone_cc", "backup_phone_cc"].forEach((id) => { wireCountrySelect($(id)); fillCountrySelect($(id), lang, $(id).value || defaultCountry()); });
    if (data) document.title = data.hotel.name;
    renderCards();
  }

  // ------------------------------------------------------------ schuifknop en betaalknop
  function wireDynamic() {
    document.querySelectorAll(".slide[data-door]").forEach(wireSlider);
    const pay = $("pay-btn");
    if (pay) pay.addEventListener("click", () => {
      store(PAY_KEY, String(Date.now()));
      fetch(API + "/api/checkin/" + encodeURIComponent(token) + "/pay", { method: "POST", headers: { "Content-Type": "application/json" }, body: "{}" }).catch(() => {});
      setTimeout(renderCards, 500);  // na het openen van de betaalpagina: "wordt verwerkt"
    });
  }

  function wireSlider(btn) {
    const knob = btn.querySelector(".knob");
    let startX = null;
    let max = 0;
    let dx = 0;
    btn.addEventListener("pointerdown", (e) => {
      startX = e.clientX; dx = 0; max = btn.clientWidth - knob.offsetWidth - 12;
      btn.classList.add("dragging");
      btn.setPointerCapture(e.pointerId);
    });
    btn.addEventListener("pointermove", (e) => {
      if (startX === null) return;
      dx = Math.max(0, Math.min(max, e.clientX - startX));
      knob.style.transform = `translateX(${dx}px)`;
    });
    const end = () => {
      if (startX === null) return;
      startX = null;
      btn.classList.remove("dragging");
      if (dx >= max * 0.85) { knob.style.transform = `translateX(${max}px)`; unlock(btn.dataset.door); }
      else knob.style.transform = "";
    };
    btn.addEventListener("pointerup", end);
    btn.addEventListener("pointercancel", end);
    // Met het toetsenbord (Enter of spatie) is het een bewuste keuze: dan meteen openen
    btn.addEventListener("click", (e) => { if (e.detail === 0) unlock(btn.dataset.door); });
  }

  async function loadDoors() {
    if (!data || data.phase !== "stay" || !data.access || !data.access.unlock || offline || !navigator.onLine) return;
    try {
      const res = await fetch(API + "/api/checkin/" + encodeURIComponent(token) + "/doors", { cache: "no-store" });
      if (!res.ok) return;
      const body = await res.json();
      doorStatus = body.doors || {};
      renderCards();
    } catch (e) { /* toestand onbekend: niets tonen */ }
  }

  async function unlock(door) {
    doorState[door] = "busy";
    renderCards();
    let ok = false;
    try {
      const res = await fetch(API + "/api/checkin/" + encodeURIComponent(token) + "/unlock", {
        method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ door }),
      });
      const body = await res.json().catch(() => ({}));
      ok = res.ok && body.ok;
    } catch (e) { ok = false; }
    doorState[door] = ok ? "done" : "fail";
    renderCards();
    if (ok) [2500, 9000].forEach((ms) => setTimeout(loadDoors, ms));  // slot gaat open en weer dicht
    setTimeout(() => { doorState[door] = "ready"; renderCards(); }, ok ? 6000 : 30000);
  }

  // ------------------------------------------------------------ formulier
  const EMAIL_RE = /^[^@\s]+@[^@\s]+\.[^@\s]{2,}$/;
  function showFieldError(id, bad) { $("err-" + id).hidden = !bad; $(id).classList.toggle("invalid", bad); }
  ["email", "backup_email"].forEach((id) => {
    $(id).addEventListener("blur", () => { const v = $(id).value.trim(); showFieldError(id, id === "email" ? !EMAIL_RE.test(v) : !!v && !EMAIL_RE.test(v)); });
    $(id).addEventListener("input", () => showFieldError(id, false));
  });
  ["phone", "backup_phone"].forEach((id) => {
    const sel = $(id + "_cc");
    $(id).addEventListener("input", () => { cleanPhoneInput(sel, $(id)); showFieldError(id, false); });
    $(id).addEventListener("blur", () => showFieldError(id, !phoneLooksValid(sel, $(id))));
    sel.addEventListener("change", () => { if ($(id).value) showFieldError(id, !phoneLooksValid(sel, $(id))); });
  });
  function defaultCountry() { return (data && data.country && DIAL[data.country]) ? data.country : "BE"; }
  function setPhone(prefix, e164) {
    const parts = splitPhone(e164, defaultCountry());
    fillCountrySelect($(prefix + "_cc"), lang, parts.iso);
    $(prefix).value = parts.national;
  }
  function fillForm() {
    $("email").value = data.email;
    $("backup_email").value = data.backup_email;
    setPhone("phone", data.phone);
    setPhone("backup_phone", data.backup_phone);
    $("backup-box").open = !!(data.backup_email || data.backup_phone);
    $("language").value = langChosenByGuest || !I18N[data.language] ? lang : data.language;
    $("no_marketing").checked = data.no_marketing;
    $("stairs_yes").checked = !!data.stairs_help;
    $("stairs_no").checked = data.completed && !data.stairs_help;
  }
  $("details-edit").addEventListener("click", () => { editing = true; fillForm(); renderDetails(); $("email").focus(); });

  async function postWithRetry(url, opts, tries = 3) {
    for (let i = 1; ; i++) {
      try {
        const res = await fetch(url, opts);
        if (res.status < 500 || i >= tries) return res;
      } catch (e) { if (i >= tries) throw e; }
      await new Promise((r) => setTimeout(r, 1500 * i));
    }
  }

  $("form").addEventListener("submit", async (ev) => {
    ev.preventDefault();
    ["err-email", "err-phone", "err-backup_email", "err-backup_phone", "err-general"].forEach((id) => ($(id).hidden = true));
    const btn = $("submit");
    btn.disabled = true;
    btn.textContent = t("saving");
    const form = {
      email: $("email").value,
      phone: composePhone($("phone_cc").value, $("phone").value),
      backup_email: $("backup_email").value,
      backup_phone: composePhone($("backup_phone_cc").value, $("backup_phone").value),
      language: $("language").value,
      no_marketing: $("no_marketing").checked,
      stairs_help: !!data.stairs && $("stairs_yes").checked,
    };
    try {
      const res = await postWithRetry(API + "/api/checkin/" + encodeURIComponent(token), {
        method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(form),
      });
      const body = await res.json().catch(() => ({}));
      if (res.ok && body.ok) {
        lang = form.language; langChosenByGuest = true;
        editing = false;
        if (data.demo) Object.assign(data, { completed: true, email: form.email.trim().toLowerCase(), phone: form.phone || "", stairs_help: form.stairs_help });
        else { formFilled = false; await load(true); }
        render();
        $("saved").hidden = false;
        setTimeout(() => { $("saved").hidden = true; }, 6000);
        window.scrollTo({ top: 0, behavior: "smooth" });
        return;
      }
      const errors = body.errors || {};
      ["email", "phone", "backup_email", "backup_phone"].forEach((k) => { if (errors[k]) showFieldError(k, true); });
      if (errors.backup_email || errors.backup_phone) $("backup-box").open = true;
      if (errors.state) return showMessage(errors.state);
      if (errors.token) return showMessage("notfound");
      if (!["email", "phone", "backup_email", "backup_phone"].some((k) => errors[k])) {
        $("err-general").textContent = t("err_general");
        $("err-general").hidden = false;
      }
    } catch (e) {
      $("err-general").textContent = t("err_general");
      $("err-general").hidden = false;
    } finally {
      btn.disabled = false;
      btn.textContent = t("submit");
    }
  });

  // ------------------------------------------------------------ laden
  function applyHotel(h) {
    const root = document.documentElement.style;
    root.setProperty("--acc", h.colors.accent);
    root.setProperty("--accd", h.colors.accent_donker);
    root.setProperty("--text", h.colors.tekst);
    root.setProperty("--bg", h.colors.achtergrond);
    $("logo").src = h.logo_url;
    if (h.favicon_url) {  // icoon van het hotel, zoals op zijn website
      $("favicon").removeAttribute("type");
      $("favicon").href = h.favicon_url;
      $("touch-icon").href = h.favicon_url;
    }
    $("logo").alt = h.name;
    $("logo-link").href = h.website;
    $("f-name").textContent = h.name;
    $("f-address").textContent = h.address;
    $("f-phone").textContent = h.phone;
    $("f-phone").href = "tel:" + h.phone.replace(/\s/g, "");
    $("f-email").textContent = h.email;
    $("f-email").href = "mailto:" + h.email;
  }

  // visit: de gast opent de pagina (of keert terug naar de app); niet bij het automatisch verversen
  async function load(quiet, visit) {
    if (!token) return showMessage("notfound");
    let res = null;
    try {
      res = await fetch(API + "/api/checkin/" + encodeURIComponent(token) + (visit ? "?v=1" : ""), { cache: "no-store" });
    } catch (e) { res = null; }
    if (res && res.status === 404) { store(CACHE_KEY, null); data = null; return showMessage("notfound"); }
    if (res && res.ok) {
      data = await res.json();
      offline = false;
      if (!data.demo) { store(CACHE_KEY, JSON.stringify(data)); store("gastapp:last", token); }  // ook zonder netwerk
    } else {
      const cached = stored(CACHE_KEY);
      if (!cached) { if (!data && !quiet) showMessage("notfound"); return; }
      data = JSON.parse(cached);
      offline = true;
    }
    if (data.pay && data.pay.paid && stored(PAY_KEY) && Date.now() - Number(stored(PAY_KEY)) > PAY_PENDING_MS) store(PAY_KEY, null);
    applyHotel(data.hotel);
    applyApp(data.hotel);
    if (!langChosenByGuest && I18N[data.language]) lang = data.language;
    if (!formFilled) { fillForm(); formFilled = true; }
  }

  document.querySelectorAll(".lang button").forEach((b) => b.addEventListener("click", () => {
    lang = b.dataset.lang; langChosenByGuest = true;
    if (!$("form").hidden && !data?.completed) $("language").value = lang;  // nog niet ingecheckt: zelfde taal voor de berichten
    render();
  }));
  window.addEventListener("online", () => { offline = false; load(true).then(render); });
  window.addEventListener("offline", renderCards);
  // Nieuwe gegevens (fase, code, betaling) zonder herladen: elke 5 minuten, elke minuut als een betaling bezig is
  let ticks = 0;
  setInterval(() => {
    ticks += 1;
    if (document.hidden || editing || !data) return;
    if (payPending() || ticks % 5 === 0) load(true).then(renderCards).then(loadDoors);
    else { renderCards(); loadDoors(); }  // tijden van de schuifknoppen, toestand van de sloten
  }, 60 * 1000);
  document.addEventListener("visibilitychange", () => { if (!document.hidden && data && !editing) load(true, true).then(renderCards); });

  if ("serviceWorker" in navigator && (location.protocol === "https:" || location.hostname === "localhost")) {
    navigator.serviceWorker.register("sw.js").catch(() => {});
  }

  render();
  load(false, true).then(render).then(loadDoors);
})();
