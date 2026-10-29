// Opvolgpagina: haalt gegevens op via /api/opvolging/... (lokaal de devserver, later de Function App).
const API = window.ADMIN_API || "";
const $ = s => document.querySelector(s);
const esc = s => String(s ?? "").replace(/[&<>"]/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));
const day = iso => iso ? new Date(iso + (iso.length === 10 ? "T00:00" : "")).toLocaleDateString("nl-BE", { day: "2-digit", month: "2-digit", year: "2-digit" }) : "";
const stamp = iso => iso ? new Date(iso).toLocaleString("nl-BE", { day: "2-digit", month: "2-digit", hour: "2-digit", minute: "2-digit" }) : "";
let rows = [], timer = null;

function store(k, v) { try { v === undefined ? null : localStorage.setItem(k, v); return localStorage.getItem(k); } catch { return null; } }
async function get(path, opts) {
  const r = await fetch(API + path, opts);
  if (r.status === 401) { location.href = "/.auth/login/aad?post_login_redirect_uri=/opvolging/"; throw new Error("login"); }
  if (!r.ok) throw new Error(r.status);
  return r.json();
}

// Filter "Verblijf van" staat standaard op vandaag, "tot" leeg
const todayIso = () => new Date().toISOString().slice(0, 10);
$("#from").value = todayIso();

async function init() {
  const hotels = await get("/api/opvolging/hotels");
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
  $("#from").onchange = render;
  $("#to").onchange = render;
  $("#today").onclick = () => { $("#from").value = todayIso(); $("#to").value = ""; render(); };
  $("#run").onclick = runRobot;
  load();
}

async function load() {
  const h = $("#hotel").value;
  rows = await get(`/api/opvolging/${h}/reservations`);
  render();
  loadRuns();
}

function render() {
  const q = $("#search").value.toLowerCase();
  // Verblijf dat (deels) in de gekozen periode valt; lege datum = geen grens
  const from = $("#from").value, to = $("#to").value;
  const list = rows.filter(r => (!from || r.departure >= from) && (!to || r.arrival <= to) &&
    (!q || [r.guest, r.booking_number, r.email, r.phone].join(" ").toLowerCase().includes(q)));
  $("#count").textContent = `${list.length} reservaties`;
  $("#res").innerHTML = list.map(r => `
    <tr class="${r.status === "cancelled" ? "cancelled" : ""}">
      <td>${day(r.arrival)}</td><td>${day(r.departure)}</td>
      <td>${esc(r.booking_number)}</td><td>${esc(r.guest)}</td><td>${esc(r.guests ?? "")}</td>
      <td>${esc(r.rooms.join(", ") || r.room_type)}</td><td>${esc(r.source)}</td><td>${esc(r.pms_status)}</td>
      <td>${stamp(r.booked_at)}</td>
      <td>${r.checkin_completed_at ? `<span class="ok">ja</span> ${stamp(r.checkin_completed_at)}` : `<span class="muted">nee</span>`}</td>
      <td class="wrap">${esc(r.email)}${r.email && r.phone ? "<br>" : ""}${esc(r.phone)}</td>
      <td class="wrap">${r.messages.map(m => `<span class="tag ${m.ok ? "" : "fail"}" title="${esc(stamp(m.at))}">${esc(m.type)} (${esc(m.channel)})</span>`).join("") || '<span class="muted">geen</span>'}</td>
    </tr>`).join("") || `<tr><td colspan="12" class="muted">Geen reservaties</td></tr>`;
}

async function loadRuns() {
  const h = $("#hotel").value;
  const d = await get(`/api/opvolging/${h}/runs`);
  $("#run").disabled = d.running || !d.can_run;
  $("#robot-state").textContent = d.running ? "De robot is bezig..." :
    (d.can_run ? "" : "De robot draait hier nog niet: de cloudversie (geplande taak) volgt.");
  $("#runs").innerHTML = d.runs.map(x => {
    const secs = (new Date(x.finished_at) - new Date(x.started_at)) / 1000;
    return `<tr><td>${stamp(x.started_at)}</td><td>${Math.round(secs)} s</td><td>${esc(x.task)}</td>
      <td class="${x.ok ? "ok" : "err"}">${x.ok ? "ok" : "fout"}</td><td>${x.found}</td><td>${x.new}</td>
      <td class="wrap err">${esc(x.error)}</td></tr>`;
  }).join("") || `<tr><td colspan="7" class="muted">De robot heeft nog niet gedraaid</td></tr>`;
  clearTimeout(timer);
  if (d.running) timer = setTimeout(async () => { await loadRuns(); }, 3000);
  else if ($("#run").dataset.waiting) { delete $("#run").dataset.waiting; load(); }
}

async function runRobot() {
  const h = $("#hotel").value;
  $("#run").disabled = true;
  $("#run").dataset.waiting = "1";
  await get(`/api/opvolging/${h}/run?hours=${encodeURIComponent($("#hours").value)}`, { method: "POST" });
  loadRuns();
}

init().catch(e => { document.body.insertAdjacentHTML("beforeend", `<p class="err">Fout bij laden: ${esc(e.message)}</p>`); });
