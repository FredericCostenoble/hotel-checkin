// Monitor (opvolgpagina): haalt gegevens op via /api/monitor/... (lokaal de devserver, in Azure de Function App).
const API = window.ADMIN_API || "";

const T = {
  nl: {
    title: "Check-in monitor", hotel: "Hotel", tab_res: "Reservaties", tab_robot: "Robot", tab_guests: "Gasten",
    returning: n => `terugkerend (${n}×)`,
    g_update: "Synchroniseren", g_busy: "Bezig...", g_done: d => `${d.linked} gekoppeld, ${d.counted} verblijven meegeteld, ${d.reservations_deleted} oude reservaties en ${d.guests_deleted} gasten verwijderd`,
    g_search: "Zoek op naam, e-mail, telefoon", g_count: n => `${n} gasten`, g_country: "Land", g_stays: "Verblijven",
    g_avg_nights: "Gem. nachten", g_avg_persons: "Gem. pers.", g_first: "Eerste verblijf", g_last: "Laatste verblijf",
    g_channel: "Kanaal", g_rooms: "Kamers", g_relay: "doorstuuradres, niet voor marketing", g_form: "formulier",
    g_optout: "geen marketing", no_guests: "Nog geen gasten (klik op Synchroniseren)",
    m_title: n => `Mogelijke dubbels (${n})`, m_help: "Zelfde of bijna dezelfde naam in hetzelfde land. Nooit automatisch samengevoegd.",
    m_same_name: "zelfde naam", m_similar_name: "bijna zelfde naam", m_merge: "Samenvoegen", m_different: "Andere persoon",
    m_confirm: "Deze twee gasten samenvoegen tot één?", filter_guest: name => `Gast: ${name}`, show_all: "alles tonen",
    search: "Zoek op naam, nummer, e-mail", stay_from: "Verblijf van", stay_to: "tot", from_today: "Vanaf vandaag",
    c_arrival: "Aankomst", c_departure: "Vertrek", c_number: "Nummer", c_guest: "Gast", c_pers: "Pers.",
    c_room: "Kamer", c_via: "Via", c_booked: "Geboekt", c_added: "Toegevoegd", c_updated: "Bijgewerkt", c_form: "Formulier", c_contact: "Contact", c_messages: "Berichten",
    yes: "ja", no: "nee", none: "geen", count: n => `${n} reservaties`, no_res: "Geen reservaties",
    hours_a: "Nieuwe reservaties van de laatste", hours_b: "uur", run: "Robot nu draaien",
    r_start: "Start", r_duration: "Duur", r_task: "Taak", r_result: "Resultaat", r_found: "Gevonden", r_new: "Nieuw", r_error: "Opmerking",
    all_tasks: "Alle", sub_log: "Logboek robot", del: "Verwijderen", del_confirm: "Deze regel uit het logboek verwijderen?", del_all: "Alles verwijderen",
    del_all_confirm: (n, task) => `${n} regels${task ? ` van "${task}"` : ""} uit het logboek verwijderen?`, t_login: "aanmelden", t_list: "lijst", t_contact: (n, sec) => `${n} contact${n > 1 ? "en" : ""} à ${sec} s`, task_nieuwe_reservaties: "Nieuwe reservaties", task_contactgegevens_nalezen: "Reservaties bijwerken", task_meldingen: "Meldingen per mail", task_onderhoud: "Gasten synchroniseren",
    ok: "ok", fail: "fout", busy: "De robot is bezig...", scheduled: "Draait ook automatisch op schema.",
    not_installed: "De robot is in deze omgeving nog niet geïnstalleerd.", no_runs: "Nog geen afgeronde run",
    load_error: "Fout bij laden",
    exec_title: "Runs volgens Azure", exec_end: "Einde", exec_status: "Status", exec_name: "Naam",
  },
  en: {
    title: "Check-in monitor", hotel: "Hotel", tab_res: "Reservations", tab_robot: "Robot", tab_guests: "Guests",
    returning: n => `returning (${n}×)`,
    g_update: "Synchronize", g_busy: "Working...", g_done: d => `${d.linked} linked, ${d.counted} stays counted, ${d.reservations_deleted} old reservations and ${d.guests_deleted} guests deleted`,
    g_search: "Search name, e-mail, phone", g_count: n => `${n} guests`, g_country: "Country", g_stays: "Stays",
    g_avg_nights: "Avg nights", g_avg_persons: "Avg pers.", g_first: "First stay", g_last: "Last stay",
    g_channel: "Channel", g_rooms: "Rooms", g_relay: "relay address, not for marketing", g_form: "form",
    g_optout: "no marketing", no_guests: "No guests yet (click Synchronize)",
    m_title: n => `Possible duplicates (${n})`, m_help: "Same or almost the same name in the same country. Never merged automatically.",
    m_same_name: "same name", m_similar_name: "similar name", m_merge: "Merge", m_different: "Different person",
    m_confirm: "Merge these two guests into one?", filter_guest: name => `Guest: ${name}`, show_all: "show all",
    search: "Search name, number, e-mail", stay_from: "Stay from", stay_to: "to", from_today: "From today",
    c_arrival: "Arrival", c_departure: "Departure", c_number: "Number", c_guest: "Guest", c_pers: "Pers.",
    c_room: "Room", c_via: "Via", c_booked: "Booked", c_added: "Added", c_updated: "Updated", c_form: "Form", c_contact: "Contact", c_messages: "Messages",
    yes: "yes", no: "no", none: "none", count: n => `${n} reservations`, no_res: "No reservations",
    hours_a: "New reservations of the last", hours_b: "hours", run: "Run robot now",
    r_start: "Start", r_duration: "Duration", r_task: "Task", r_result: "Result", r_found: "Found", r_new: "New", r_error: "Note",
    all_tasks: "All", sub_log: "Robot log", del: "Delete", del_confirm: "Delete this line from the log?", del_all: "Delete all",
    del_all_confirm: (n, task) => `Delete ${n} lines${task ? ` of "${task}"` : ""} from the log?`, t_login: "login", t_list: "list", t_contact: (n, sec) => `${n} contact${n > 1 ? "s" : ""} × ${sec} s`, task_nieuwe_reservaties: "New reservations", task_contactgegevens_nalezen: "Update reservations", task_meldingen: "Mail notifications", task_onderhoud: "Synchronize guests",
    ok: "ok", fail: "failed", busy: "The robot is running...", scheduled: "Also runs automatically on a schedule.",
    not_installed: "The robot is not installed in this environment yet.", no_runs: "No finished run yet",
    load_error: "Loading failed",
    exec_title: "Runs according to Azure", exec_end: "End", exec_status: "Status", exec_name: "Name",
  },
};
let lang = "nl";
const t = (k, ...a) => { const v = T[lang][k]; return typeof v === "function" ? v(...a) : v; };
const locale = () => (lang === "en" ? "en-GB" : "nl-BE");
const $ = s => document.querySelector(s);
const esc = s => String(s ?? "").replace(/[&<>"]/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));
const day = iso => iso ? new Date(iso + (iso.length === 10 ? "T00:00" : "")).toLocaleDateString(locale(), { day: "2-digit", month: "2-digit", year: "2-digit" }) : "";
const stamp = iso => iso ? new Date(iso).toLocaleString(locale(), { day: "2-digit", month: "2-digit", hour: "2-digit", minute: "2-digit" }) : "";
let rows = [], runsData = null, timer = null, waitTries = 0;
const TASKS = ["nieuwe_reservaties", "contactgegevens_nalezen", "meldingen", "onderhoud"];
const taskName = k => T[lang]["task_" + k] || k;
let taskFilter = "";
try { taskFilter = localStorage.getItem("monitor-task") || ""; } catch (e) { /* geen opslag */ }

function store(k, v) { try { v === undefined ? null : localStorage.setItem(k, v); return localStorage.getItem(k); } catch { return null; } }
async function get(path, opts) {
  const r = await fetch(API + path, opts);
  if (r.status === 401) { location.href = "/.auth/login/aad?post_login_redirect_uri=/monitor/"; throw new Error("login"); }
  if (!r.ok) throw new Error(r.status);
  return r.json();
}

// Filter "Verblijf van" staat standaard op vandaag, "tot" leeg
const todayIso = () => new Date().toISOString().slice(0, 10);
$("#from").value = todayIso();

function setLang(l) {
  lang = T[l] ? l : "nl";
  store("lang", lang);
  document.documentElement.lang = lang;
  document.querySelectorAll("[data-t]").forEach(e => { e.textContent = t(e.dataset.t); });
  document.querySelectorAll("[data-tp]").forEach(e => { e.placeholder = t(e.dataset.tp); });
  document.querySelectorAll(".langs button").forEach(b => b.classList.toggle("active", b.dataset.lang === lang));
  render();
  renderGuests();
  if (runsData) renderRuns(runsData);
}

async function init() {
  document.querySelectorAll(".langs button").forEach(b => b.onclick = () => setLang(b.dataset.lang));
  setLang(store("lang") || (navigator.language || "nl").slice(0, 2));
  const hotels = await get("/api/monitor/hotels");
  $("#hotel").innerHTML = hotels.map(h => `<option value="${esc(h.id)}">${esc(h.name)}</option>`).join("");
  const saved = store("hotel");
  if (saved && hotels.some(h => h.id === saved)) $("#hotel").value = saved;
  $("#hotel").onchange = () => { store("hotel", $("#hotel").value); load(); };
  document.querySelectorAll(".subtabs button").forEach(b => b.onclick = () => showSub(b.dataset.sub));
  $("#bin-all").innerHTML = BIN;
  $("#bin-all").onclick = deleteAllRuns;
  document.querySelectorAll("nav button").forEach(b => b.onclick = () => showTab(b.dataset.tab));
  $("#g-search").oninput = renderGuests;
  $("#g-update").onclick = updateGuests;
  document.querySelectorAll("#g-head th[data-gsort]").forEach(th => th.onclick = () => gSortBy(th.dataset.gsort));
  $("#search").oninput = render;
  document.querySelectorAll("#res-head th[data-sort]").forEach(th => th.onclick = () => sortBy(th.dataset.sort));
  $("#task").onchange = () => {
    taskFilter = $("#task").value;
    try { localStorage.setItem("monitor-task", taskFilter); } catch (e) { /* geen opslag */ }
    if (runsData) renderRuns(runsData);
  };
  $("#from").onchange = render;
  $("#to").onchange = render;
  $("#today").onclick = () => { $("#from").value = todayIso(); $("#to").value = ""; render(); };
  $("#run").onclick = runRobot;
  load();
}

function showTab(name) {
  document.querySelectorAll("nav button").forEach(x => x.classList.toggle("active", x.dataset.tab === name));
  ["res", "guests", "robot"].forEach(n => { $(`#tab-${n}`).hidden = n !== name; });
}

async function load() {
  const h = $("#hotel").value;
  resIds = null; guestId = null;
  rows = await get(`/api/monitor/${h}/reservations`);
  render();
  loadGuests();
  loadRuns();
}

// ---------------------------------------------------------------- gasten
let guestData = { guests: [], matches: [] }, guestId = null, resIds = null;
let gSortKey = "last_stay", gSortDir = -1;
const gValue = (g, k) => k === "rooms" ? g.rooms.join(", ") : k === "reservations" ? g.reservations.length
  : k === "email" ? (g.email || g.phone) : (g[k] ?? "");
function gSortBy(k) { gSortDir = k === gSortKey ? -gSortDir : 1; gSortKey = k; renderGuests(); }

// Synchroniseren: koppelen, voorbije verblijven meetellen (nooit dubbel), opruimen
async function updateGuests() {
  $("#g-update").disabled = true;
  $("#g-state").textContent = t("g_busy");
  try {
    const d = await get(`/api/monitor/${$("#hotel").value}/maintenance`, { method: "POST" });
    $("#g-state").textContent = t("g_done", d);
    await loadGuests();
    loadRuns();
  } catch (e) {
    $("#g-state").textContent = `${t("load_error")}: ${e.message}`;
  } finally {
    $("#g-update").disabled = false;
  }
}

async function loadGuests() {
  guestData = await get(`/api/monitor/${$("#hotel").value}/guests`);
  renderGuests();
  render();
}

function guestById(id) { return guestData.guests.find(g => g.id === id); }

// Van een reservatie naar de gast
function openGuest(id) { guestId = id; showTab("guests"); renderGuests(); }
// Van een gast naar zijn reservaties
function openReservations(id) { resIds = guestById(id)?.reservations || []; guestId = id; $("#from").value = ""; showTab("res"); render(); }

function contactCell(g) {
  const tags = [];
  if (g.email && !g.email_own) tags.push(`<span class="tag" title="${esc(t("g_relay"))}">OTA</span>`);
  if (g.form) tags.push(`<span class="tag">${esc(t("g_form"))}</span>`);
  if (g.opt_out) tags.push(`<span class="tag fail">${esc(t("g_optout"))}</span>`);
  return `${esc(g.email)}${g.email && g.phone ? "<br>" : ""}${esc(g.phone)} ${tags.join("")}`;
}

function renderGuests() {
  const q = $("#g-search").value.toLowerCase();
  const chip = $("#g-filter"), focus = guestId && guestById(guestId);
  chip.hidden = !focus;
  if (focus) {
    chip.innerHTML = `${esc(t("filter_guest", focus.name))} <a href="#">${esc(t("show_all"))}</a>`;
    chip.querySelector("a").onclick = e => { e.preventDefault(); guestId = null; renderGuests(); };
  }
  const list = guestData.guests.filter(g => (!focus || g.id === guestId) &&
    (!q || [g.name, g.email, g.phone].join(" ").toLowerCase().includes(q)));
  list.sort((a, b) => {
    const x = gValue(a, gSortKey), y = gValue(b, gSortKey);
    if (x === "" || x === null || y === "" || y === null) return x === y ? 0 : (x === "" || x === null ? 1 : -1);
    return (typeof x === "number" ? x - y : String(x).localeCompare(String(y), locale(), { numeric: true })) * gSortDir;
  });
  document.querySelectorAll("#g-head th[data-gsort]").forEach(th => {
    th.classList.toggle("sorted", th.dataset.gsort === gSortKey);
    th.dataset.dir = th.dataset.gsort === gSortKey ? (gSortDir > 0 ? "asc" : "desc") : "";
  });
  $("#g-count").textContent = t("g_count", list.length);
  $("#guests").innerHTML = list.map(g => `
    <tr>
      <td>${esc(g.name)}</td><td class="wrap">${contactCell(g)}</td>
      <td>${esc(g.country)}${g.language ? ` <span class="muted">${esc(g.language)}</span>` : ""}</td>
      <td>${g.stays}</td><td>${g.avg_nights ?? ""}</td><td>${g.avg_persons ?? ""}</td>
      <td>${day(g.first_stay)}</td><td>${day(g.last_stay)}</td>
      <td title="${esc(g.channels.map(c => `${c.name} ${c.count}×`).join(", "))}">${esc(g.preferred_channel)}</td>
      <td>${esc(g.rooms.join(", "))}${g.room_type ? ` <span class="muted">${esc(g.room_type)}</span>` : ""}</td>
      <td>${g.reservations.length ? `<a href="#" data-res="${esc(g.id)}">${g.reservations.length}</a>` : "0"}</td>
    </tr>`).join("") || `<tr><td colspan="11" class="muted">${t("no_guests")}</td></tr>`;
  document.querySelectorAll("#guests a[data-res]").forEach(a => a.onclick = e => { e.preventDefault(); openReservations(a.dataset.res); });
  renderMatches();
}

function renderMatches() {
  const m = guestData.matches.filter(x => guestById(x.a) && guestById(x.b));
  $("#matches-wrap").hidden = !m.length;
  $("#matches-title").textContent = t("m_title", m.length);
  const who = g => `<strong>${esc(g.name)}</strong> <span class="muted">${esc([g.country, g.email || g.phone, g.stays + "×"].filter(Boolean).join(" · "))}</span>`;
  $("#matches").innerHTML = m.map(x => `
    <tr><td>${who(guestById(x.a))}</td><td>${who(guestById(x.b))}</td><td class="muted">${esc(t("m_" + x.reason))}</td>
      <td><button type="button" data-act="merge" data-a="${esc(x.a)}" data-b="${esc(x.b)}">${esc(t("m_merge"))}</button>
        <button type="button" data-act="different" data-a="${esc(x.a)}" data-b="${esc(x.b)}">${esc(t("m_different"))}</button></td></tr>`).join("");
  document.querySelectorAll("#matches button").forEach(b => b.onclick = async () => {
    if (b.dataset.act === "merge" && !confirm(t("m_confirm"))) return;
    await get(`/api/monitor/${$("#hotel").value}/guests?action=${b.dataset.act}&a=${encodeURIComponent(b.dataset.a)}&b=${encodeURIComponent(b.dataset.b)}`, { method: "POST" });
    loadGuests();
  });
}

// Sorteren: klik op een kolomtitel, nog eens klikken keert de volgorde om
let sortKey = "arrival", sortDir = 1;
try { [sortKey, sortDir] = JSON.parse(localStorage.getItem("monitor-sort")) || [sortKey, sortDir]; } catch (e) { /* geen opslag */ }
const sortValue = (r, k) => k === "room" ? (r.rooms.join(", ") || r.room_type)
  : k === "messages" ? r.messages.length : k === "guests" ? (r.guests ?? -1)
  : k === "email" ? (r.email || r.phone) : (r[k] ?? "");
function sortBy(k) {
  sortDir = k === sortKey ? -sortDir : 1;
  sortKey = k;
  try { localStorage.setItem("monitor-sort", JSON.stringify([sortKey, sortDir])); } catch (e) { /* geen opslag */ }
  render();
}

function render() {
  const q = $("#search").value.toLowerCase();
  // Verblijf dat (deels) in de gekozen periode valt; lege datum = geen grens
  const from = $("#from").value, to = $("#to").value;
  const chip = $("#res-filter"), focus = resIds && guestId && guestById(guestId);
  chip.hidden = !resIds;
  if (resIds) {
    chip.innerHTML = `${esc(t("filter_guest", focus ? focus.name : ""))} <a href="#">${esc(t("show_all"))}</a>`;
    chip.querySelector("a").onclick = e => { e.preventDefault(); resIds = null; $("#from").value = todayIso(); render(); };
  }
  const list = rows.filter(r => (!resIds || resIds.includes(r.id)) && (!from || r.departure >= from) && (!to || r.arrival <= to) &&
    (!q || [r.guest, r.booking_number, r.email, r.phone].join(" ").toLowerCase().includes(q)));
  list.sort((a, b) => {
    const x = sortValue(a, sortKey), y = sortValue(b, sortKey);
    // lege waarden altijd onderaan
    if (x === "" || y === "") return x === y ? 0 : (x === "" ? 1 : -1);
    return (typeof x === "number" ? x - y : String(x).localeCompare(String(y), locale(), { numeric: true })) * sortDir;
  });
  document.querySelectorAll("#res-head th[data-sort]").forEach(th => {
    th.classList.toggle("sorted", th.dataset.sort === sortKey);
    th.dataset.dir = th.dataset.sort === sortKey ? (sortDir > 0 ? "asc" : "desc") : "";
  });
  $("#count").textContent = t("count", list.length);
  $("#res").innerHTML = list.map(r => `
    <tr class="${r.status === "cancelled" ? "cancelled" : ""}">
      <td>${day(r.arrival)}</td><td>${day(r.departure)}</td>
      <td>${esc(r.booking_number)}</td><td>${r.guest_id && guestById(r.guest_id) ? `<a href="#" data-guest="${esc(r.guest_id)}">${esc(r.guest)}</a>` : esc(r.guest)}${r.guest_stays ? ` <span class="tag back">${esc(t("returning", r.guest_stays))}</span>` : ""}</td><td>${esc(r.guests ?? "")}</td>
      <td>${esc(r.rooms.join(", ") || r.room_type)}</td><td>${esc(r.source)}</td><td>${esc(r.pms_status)}</td>
      <td>${stamp(r.booked_at)}</td><td>${stamp(r.added_at)}</td><td>${stamp(r.updated_at)}</td>
      <td>${r.checkin_completed_at ? `<span class="ok">${t("yes")}</span> ${stamp(r.checkin_completed_at)}` : `<span class="muted">${t("no")}</span>`}</td>
      <td class="wrap">${esc(r.email)}${r.email && r.phone ? "<br>" : ""}${esc(r.phone)}</td>
      <td class="wrap">${r.messages.map(m => `<span class="tag ${m.ok ? "" : "fail"}" title="${esc(stamp(m.at))}">${esc(m.type)} (${esc(m.channel)})</span>`).join("") || `<span class="muted">${t("none")}</span>`}</td>
    </tr>`).join("") || `<tr><td colspan="14" class="muted">${t("no_res")}</td></tr>`;
  document.querySelectorAll("#res a[data-guest]").forEach(a => a.onclick = e => { e.preventDefault(); openGuest(a.dataset.guest); });
}

async function loadRuns() {
  const h = $("#hotel").value;
  runsData = await get(`/api/monitor/${h}/runs`);
  const since = $("#run").dataset.waiting;
  // Na "Robot nu draaien": verversen tot er een nieuwe run is (in de cloud start de job pas na enkele seconden)
  if (since && runsData.runs.length && runsData.runs[0].started_at > since && !runsData.running) {
    delete $("#run").dataset.waiting;
    renderRuns(runsData);
    return load();
  }
  if (since && waitTries++ > 60) delete $("#run").dataset.waiting;
  renderRuns(runsData);
  clearTimeout(timer);
  if (runsData.running || $("#run").dataset.waiting) timer = setTimeout(loadRuns, 5000);
}

// Gemeten duur per onderdeel onder de totale duur, bv. "aanmelden 25 s, lijst 6 s, 2 contacten à 9 s"
function timingText(tm) {
  if (!tm || !Object.keys(tm).length) return "";
  const p = [];
  if (tm.login != null) p.push(`${t("t_login")} ${Math.round(tm.login)} s`);
  if (tm.list != null) p.push(`${t("t_list")} ${Math.round(tm.list)} s`);
  if (tm.contact != null) p.push(t("t_contact", tm.contacts || 1, Math.round(tm.contact)));
  return `<div class="timing">${esc(p.join(", "))}</div>`;
}

const BIN = `<svg viewBox="0 0 16 16" width="14" height="14" aria-hidden="true"><path fill="currentColor" d="M6 1h4l.5 1H14v1.5H2V2h3.5L6 1zm-2.5 3.5h9l-.7 9.6a1 1 0 0 1-1 .9H5.2a1 1 0 0 1-1-.9L3.5 4.5zm3 1.5v7h1V6h-1zm2 0v7h1V6h-1z"/></svg>`;
let subTab = "log";
function showSub(name) {
  subTab = name;
  document.querySelectorAll(".subtabs button").forEach(b => b.classList.toggle("active", b.dataset.sub === name));
  $("#sub-log").hidden = name !== "log";
  $("#task").disabled = name !== "log";  // filter op taak geldt alleen voor het logboek (blijft staan, niets verspringt)
  $("#exec-wrap").hidden = name !== "azure";
}

// Vuilbakje in de kolomtitel: alles wat nu getoond wordt (alle taken, of de gekozen taak)
async function deleteAllRuns() {
  const task = $("#task").value, n = runsData.runs.filter(x => !task || x.task === task).length;
  if (!n || !confirm(t("del_all_confirm", n, task ? taskName(task) : ""))) return;
  const h = $("#hotel").value;
  await get(`/api/monitor/${h}/runs?all=1&task=${encodeURIComponent(task)}`, { method: "DELETE" });
  runsData.runs = runsData.runs.filter(x => task && x.task !== task);
  renderRuns(runsData);
}

async function deleteRun(id) {
  if (!confirm(t("del_confirm"))) return;
  const h = $("#hotel").value;
  await get(`/api/monitor/${h}/runs?id=${encodeURIComponent(id)}`, { method: "DELETE" });
  runsData.runs = runsData.runs.filter(x => x.id !== id);
  renderRuns(runsData);
}

function renderRuns(d) {
  $("#bin-all").title = $("#bin-all").ariaLabel = t("del_all");
  const busy = d.running || !!$("#run").dataset.waiting;
  $("#run").disabled = busy || !d.can_run;
  // In de cloud bepaalt de robot zelf vanaf wanneer (sinds de vorige geslaagde run)
  $("#hours-wrap").hidden = !!d.cloud;
  $("#robot-state").textContent = busy ? t("busy") : (d.can_run ? (d.cloud ? t("scheduled") : "") : t("not_installed"));
  // Filter op taak: vaste keuzes, plus eventuele andere taken uit het logboek
  const sel = $("#task"), chosen = sel.value || taskFilter;
  const tasks = [...new Set([...TASKS, ...d.runs.map(x => x.task)])];
  sel.innerHTML = `<option value="">${t("all_tasks")}</option>` +
    tasks.map(k => `<option value="${esc(k)}">${esc(taskName(k))}</option>`).join("");
  sel.value = tasks.includes(chosen) ? chosen : "";
  const shown = d.runs.filter(x => !sel.value || x.task === sel.value);
  $("#runs").innerHTML = shown.map(x => {
    const secs = (new Date(x.finished_at) - new Date(x.started_at)) / 1000;
    // Rood alleen bij een fout of overgeslagen rijen; anders is de opmerking gewoon informatie
    const problem = !x.ok || Number(x.skipped || 0) > 0;
    return `<tr><td>${stamp(x.started_at)}</td><td>${Math.round(secs)} s${timingText(x.timings)}</td>
      <td><span class="task task-${esc(x.task)}">${esc(taskName(x.task))}</span></td>
      <td class="${x.ok ? "ok" : "err"}">${x.ok ? t("ok") : t("fail")}</td><td>${x.found}</td><td>${x.new}</td>
      <td class="wrap ${problem ? "err" : ""}">${esc(x.error)}</td>
      <td>${x.id ? `<button type="button" class="bin" data-id="${esc(x.id)}" title="${esc(t("del"))}" aria-label="${esc(t("del"))}">${BIN}</button>` : ""}</td></tr>`;
  }).join("") || `<tr><td colspan="8" class="muted">${t("no_runs")}</td></tr>`;
  document.querySelectorAll("#runs .bin").forEach(b => b.onclick = () => deleteRun(b.dataset.id));
  // In de cloud: ook de runs volgens Azure (toont runs die mislukten voor ze iets konden noteren)
  // Runs volgens Azure: apart subtabblad, alleen in de cloud
  $("#sub-azure").hidden = !d.executions;
  if (!d.executions && subTab === "azure") showSub("log");
  $("#exec-wrap").hidden = !d.executions || subTab !== "azure";
  $("#execs").innerHTML = (d.executions || []).map(e =>
    `<tr><td>${stamp(e.start)}</td><td>${stamp(e.end)}</td>
      <td>${e.start && e.end ? Math.round((new Date(e.end) - new Date(e.start)) / 1000) + " s" : ""}</td>
      <td class="${e.status === "Succeeded" ? "ok" : (e.status === "Failed" ? "err" : "")}">${esc(e.status)}</td>
      <td class="muted">${esc(e.name)}</td></tr>`).join("");
}

async function runRobot() {
  const h = $("#hotel").value;
  $("#run").disabled = true;
  $("#run").dataset.waiting = new Date().toISOString();
  waitTries = 0;
  await get(`/api/monitor/${h}/run?hours=${encodeURIComponent($("#hours").value)}`, { method: "POST" });
  loadRuns();
}

init().catch(e => { document.body.insertAdjacentHTML("beforeend", `<p class="err">${t("load_error")}: ${esc(e.message)}</p>`); });
