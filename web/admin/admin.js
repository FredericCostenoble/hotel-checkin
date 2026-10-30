// Monitor (opvolgpagina): haalt gegevens op via /api/monitor/... (lokaal de devserver, in Azure de Function App).
const API = window.ADMIN_API || "";

const T = {
  nl: {
    title: "Check-in monitor", hotel: "Hotel", tab_res: "Reservaties", tab_robot: "Robot",
    search: "Zoek op naam, nummer, e-mail", stay_from: "Verblijf van", stay_to: "tot", from_today: "Vanaf vandaag",
    c_arrival: "Aankomst", c_departure: "Vertrek", c_number: "Nummer", c_guest: "Gast", c_pers: "Pers.",
    c_room: "Kamer", c_via: "Via", c_booked: "Geboekt", c_form: "Formulier", c_contact: "Contact", c_messages: "Berichten",
    yes: "ja", no: "nee", none: "geen", count: n => `${n} reservaties`, no_res: "Geen reservaties",
    hours_a: "Nieuwe reservaties van de laatste", hours_b: "uur", run: "Robot nu draaien",
    r_start: "Start", r_duration: "Duur", r_task: "Taak", r_result: "Resultaat", r_found: "Gevonden", r_new: "Nieuw", r_error: "Opmerking",
    all_tasks: "Alle", t_login: "aanmelden", t_list: "lijst", t_contact: (n, sec) => `${n} contact${n > 1 ? "en" : ""} à ${sec} s`, task_nieuwe_reservaties: "Nieuwe reservaties", task_contactgegevens_nalezen: "Reservaties bijwerken",
    ok: "ok", fail: "fout", busy: "De robot is bezig...", scheduled: "Draait ook automatisch op schema.",
    not_installed: "De robot is in deze omgeving nog niet geïnstalleerd.", no_runs: "Nog geen afgeronde run",
    load_error: "Fout bij laden",
    exec_title: "Runs volgens Azure", exec_end: "Einde", exec_status: "Status", exec_name: "Naam",
  },
  en: {
    title: "Check-in monitor", hotel: "Hotel", tab_res: "Reservations", tab_robot: "Robot",
    search: "Search name, number, e-mail", stay_from: "Stay from", stay_to: "to", from_today: "From today",
    c_arrival: "Arrival", c_departure: "Departure", c_number: "Number", c_guest: "Guest", c_pers: "Pers.",
    c_room: "Room", c_via: "Via", c_booked: "Booked", c_form: "Form", c_contact: "Contact", c_messages: "Messages",
    yes: "yes", no: "no", none: "none", count: n => `${n} reservations`, no_res: "No reservations",
    hours_a: "New reservations of the last", hours_b: "hours", run: "Run robot now",
    r_start: "Start", r_duration: "Duration", r_task: "Task", r_result: "Result", r_found: "Found", r_new: "New", r_error: "Note",
    all_tasks: "All", t_login: "login", t_list: "list", t_contact: (n, sec) => `${n} contact${n > 1 ? "s" : ""} × ${sec} s`, task_nieuwe_reservaties: "New reservations", task_contactgegevens_nalezen: "Update reservations",
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
const TASKS = ["nieuwe_reservaties", "contactgegevens_nalezen"];
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
  document.querySelectorAll("nav button").forEach(b => b.onclick = () => {
    document.querySelectorAll("nav button").forEach(x => x.classList.toggle("active", x === b));
    $("#tab-res").hidden = b.dataset.tab !== "res";
    $("#tab-robot").hidden = b.dataset.tab !== "robot";
  });
  $("#search").oninput = render;
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

async function load() {
  const h = $("#hotel").value;
  rows = await get(`/api/monitor/${h}/reservations`);
  render();
  loadRuns();
}

function render() {
  const q = $("#search").value.toLowerCase();
  // Verblijf dat (deels) in de gekozen periode valt; lege datum = geen grens
  const from = $("#from").value, to = $("#to").value;
  const list = rows.filter(r => (!from || r.departure >= from) && (!to || r.arrival <= to) &&
    (!q || [r.guest, r.booking_number, r.email, r.phone].join(" ").toLowerCase().includes(q)));
  $("#count").textContent = t("count", list.length);
  $("#res").innerHTML = list.map(r => `
    <tr class="${r.status === "cancelled" ? "cancelled" : ""}">
      <td>${day(r.arrival)}</td><td>${day(r.departure)}</td>
      <td>${esc(r.booking_number)}</td><td>${esc(r.guest)}</td><td>${esc(r.guests ?? "")}</td>
      <td>${esc(r.rooms.join(", ") || r.room_type)}</td><td>${esc(r.source)}</td><td>${esc(r.pms_status)}</td>
      <td>${stamp(r.booked_at)}</td>
      <td>${r.checkin_completed_at ? `<span class="ok">${t("yes")}</span> ${stamp(r.checkin_completed_at)}` : `<span class="muted">${t("no")}</span>`}</td>
      <td class="wrap">${esc(r.email)}${r.email && r.phone ? "<br>" : ""}${esc(r.phone)}</td>
      <td class="wrap">${r.messages.map(m => `<span class="tag ${m.ok ? "" : "fail"}" title="${esc(stamp(m.at))}">${esc(m.type)} (${esc(m.channel)})</span>`).join("") || `<span class="muted">${t("none")}</span>`}</td>
    </tr>`).join("") || `<tr><td colspan="12" class="muted">${t("no_res")}</td></tr>`;
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

function renderRuns(d) {
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
      <td class="wrap ${problem ? "err" : ""}">${esc(x.error)}</td></tr>`;
  }).join("") || `<tr><td colspan="7" class="muted">${t("no_runs")}</td></tr>`;
  // In de cloud: ook de runs volgens Azure (toont runs die mislukten voor ze iets konden noteren)
  $("#exec-wrap").hidden = !d.executions;
  $("#execs").innerHTML = (d.executions || []).map(e =>
    `<tr><td>${stamp(e.start)}</td><td>${stamp(e.end)}</td>
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
