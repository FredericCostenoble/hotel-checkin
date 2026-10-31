// Monitor (opvolgpagina): haalt gegevens op via /api/monitor/... (lokaal de devserver, in Azure de Function App).
const API = window.ADMIN_API || "";

const T = {
  nl: {
    title: "Check-in monitor", hotel: "Hotel", tab_res: "Reservaties", tab_robot: "Robot", tab_guests: "Gasten", tab_workflow: "Workflow",
    wf_save: "Bewaren", wf_reset: "Terug naar standaard", wf_saved: "Bewaard.", wf_dirty: "Niet bewaarde wijzigingen.",
    wf_reset_confirm: "De workflow terugzetten naar de standaard uit het hotelbestand? Alle wijzigingen gaan verloren.",
    wf_from_file: "Standaard uit het hotelbestand", wf_changed: (who, when) => `Gewijzigd door ${who} op ${when}`,
    wf_leave: "Er zijn niet bewaarde wijzigingen. Toch verder?",
    flow_booking: "Booking.com", flow_expedia: "Expedia", flow_website_paid: "Website, betaald", flow_website_unpaid: "Website, niet betaald",
    wf_start: "Boeking komt binnen", wf_arrival: "Aankomst", wf_departure: "Vertrek", wf_days_after: n => `${n} dag${n === 1 ? "" : "en"} na vertrek`,
    step_thank_you: "Bedankmail na het verblijf", step_payment_request: "Betaalverzoek (nog iets open na vertrek)",
    short_thank_you: "Bedankt", short_payment_request: "Betaalverzoek", when_days_after_departure: "dagen na vertrek", c_not_paid: "niet (volledig) betaald",
    wf_not_ready_access_code: "wacht op Salto", wf_not_ready_payment_request: "wacht op Saferpay", wf_days_before: n => `${n} dag${n === 1 ? "" : "en"} voor aankomst`,
    wf_right_after: "Meteen na de boeking", step_confirmation: "Bevestiging met link naar het check-in-formulier",
    step_reminder: "Herinnering (formulier niet ingevuld)", step_access_code: "Code en praktische info",
    f_enabled: "Actief", f_when: "Wanneer", f_days: "Dagen voor aankomst", f_channels: "Kanalen", f_only_if: "Alleen als",
    f_replaced_by: "Overslaan als al aan de beurt", f_late: "Alleen als de boeking vóór die dag binnenkwam (anders kreeg de gast net de bevestiging)",
    wf_later_rule: "Deze mail gaat niet weg als op dat moment al een latere mail aan de beurt is (bv. bij een late boeking krijgt de gast meteen alleen de code-mail).", f_pay: "Betaalknop", f_content: "In de mail", g_when: "Wanneer versturen", wf_example: "Voorbeeldmail", pv_subject: "Onderwerp",
    m_reservation: "reservatiegegevens", m_checkin_form: "link check-in-formulier", m_code: "pincode", m_practical_info: "praktische info", m_pay: "betaalknop",
    wf_pay_note: "Knop om het openstaande bedrag online te betalen: alleen de toeristenbelasting of alles, wat in Lighthouse nog openstaat.",
    wf_form_note: "De link naar het formulier valt vanzelf weg als de gast het al invulde.",
    when_after_booking: "na de boeking", when_days_before_arrival: "dagen voor aankomst",
    ch_email: "e-mail", ch_sms: "sms", ch_whatsapp: "WhatsApp",
    pay_none: "geen", pay_open_amount: "openstaand bedrag", pay_city_tax: "toeristenbelasting",
    c_not_cancelled: "niet geannuleerd", c_form_completed: "formulier ingevuld", c_form_not_completed: "formulier niet ingevuld",
    c_paid: "betaald", c_checked_in: "ingecheckt", c_has_email: "e-mailadres gekend", c_has_phone: "telefoon gekend",
    wf_rules: "Herkennen", wf_sources: "Kanaal bevat (komma's tussen)", wf_other: "Alle andere kanalen",
    wf_paid_yes: "en volledig betaald", wf_paid_no: "en nog niet (volledig) betaald",
    wf_params: "Parameters (alle flows)", p_city_tax: "Toeristenbelasting", p_unit: "Per", unit_person_night: "persoon per nacht",
    unit_person_stay: "persoon per verblijf", p_currency: "Munt", wf_not_ready: "nog niet gebouwd (Salto)", wf_off: "uit",
    returning: n => `terugkerend (${n}×)`, mg_message: "Bericht", mg_time: "Tijdstip", short_confirmation: "Bevestiging", short_reminder: "Herinnering", short_access_code: "Code-mail", mg_channel: "Kanaal", mg_to: "Naar",
    mg_title: (num, guest) => `Berichten voor ${guest} (${num})`, mg_click: "Klik voor alle details",
    mg_plan: "Tijdlijn", mg_attempts: "Alle pogingen", mg_next: "volgt",
    pl_sent: "verstuurd", pl_failed: "mislukt", pl_planned: "gepland", pl_due: "volgende run", pl_skipped: "valt weg", pl_off: "niet actief", tab_hotel: "Hotel",
    hs_intro: "Gegevens en instellingen van het hotel. Standaard uit het hotelbestand; wat u hier wijzigt, gaat voor (alleen in deze omgeving).",
    hs_default: "standaard", hs_env: "In deze omgeving vastgelegd in Key Vault of de Function App: die waarde gaat voor.",
    hs_add: "Toevoegen", hs_key: "naam", hs_value: "waarde", hs_reset_confirm: "Alle instellingen terug naar het hotelbestand? Alle wijzigingen gaan verloren.",
    hs_list: "komma's ertussen",
    sec_hotel: "Hotel", sec_verzending: "Afzender van de mails", sec_receptie: "Receptie", sec_checkout: "Check-out", sec_ontbijt: "Ontbijt",
    sec_wifi: "Wifi", sec_parking: "Parking", sec_nood: "Noodnummer", sec_twilio: "Twilio (sms en WhatsApp)", sec_robot: "Robot",
    sec_messaging: "Berichten", sec_whatsapp: "WhatsApp-sjablonen", sec_retention: "Bewaartermijnen", sec_salto: "Salto",
    sec_salto_rooms: "Salto: kamers en deuren", sec_lighthouse: "Lighthouse", sec_checkin: "Check-in-formulier",
    sec_privacy: "Privacyverklaring", sec_kleuren: "Kleuren", settings: "Instellingen", back: "Monitor", open_lh: "Openen in Lighthouse", pl_not_tried: "niet geprobeerd", backup: "extra adres uit het check-in-formulier",
    rs_now: "Nu versturen", rs_again: "Opnieuw versturen", rs_confirm: (step, ch, to) => `${step} nu versturen per ${ch} naar ${to}?`,
    chr_muted: "uitgezet voor deze gast", chr_phone_off: "nog niet actief (Twilio)", chr_fallback: "alleen als WhatsApp niet lukt",
    rs_disabled: "stap staat uit", rs_messaging_off: "berichten staan uit in deze omgeving", rs_before_start: "reservatie van voor de start",
    rs_booked_late: "boeking kwam te laat", rs_later_due: "een latere mail is al aan de beurt", rs_not_ready: "nog niet gebouwd",
    rs_no_contact: "geen e-mail of telefoon", rs_window_passed: "moment voorbij", rs_condition: "voorwaarde niet voldaan",
    g_msgs: "Berichten", g_mute_hint: "Vinkje weg: dit kanaal nooit gebruiken voor deze gast",
    st_sent: "verstuurd", st_failed: "mislukt", st_delivered: "afgeleverd", st_read: "gelezen", st_undelivered: "niet afgeleverd", show_guest: "Gastgegevens tonen", show_res: "Reservaties van deze gast tonen",
    g_update: "Synchroniseren", g_busy: "Bezig...", g_done: d => `${d.linked} gekoppeld, ${d.counted} verblijven en ${d.cancellations} annuleringen meegeteld, ${d.reservations_deleted} oude reservaties en ${d.guests_deleted} gasten verwijderd`,
    g_search: "Zoek op naam, e-mail, telefoon", g_count: n => `${n} gasten`, g_country: "Land", g_stays: "Verblijven", g_cancelled: "Geannuleerd",
    g_avg_nights: "Gem. nachten", g_avg_persons: "Gem. pers.", g_first: "Eerste verblijf", g_last: "Laatste verblijf",
    g_channel: "Kanaal", g_rooms: "Kamers", g_relay: "doorstuuradres, niet voor marketing", g_form: "formulier",
    g_optout: "geen marketing", no_guests: "Nog geen gasten (klik op Synchroniseren)",
    m_title: n => `Mogelijke dubbels (${n})`, m_help: "Zelfde of bijna dezelfde naam in hetzelfde land. Nooit automatisch samengevoegd.",
    m_same_name: "zelfde naam", m_extra_contact: "extra adres of nummer van de ene is dat van de andere (zelfde persoon of partner?)", m_similar_name: "bijna zelfde naam", m_merge: "Samenvoegen", m_different: "Andere persoon",
    m_confirm: "Deze twee gasten samenvoegen tot één?", reset: "Filter wissen",
    search: "Zoek op naam, nummer, e-mail", stay_from: "Verblijf van", stay_to: "tot", from_today: "Vanaf vandaag",
    c_arrival: "Aankomst", c_departure: "Vertrek", c_number: "Nummer", c_guest: "Gast", c_pers: "Pers.",
    c_room: "Kamer", c_via: "Via", c_booked: "Geboekt", c_added: "Toegevoegd", c_updated: "Bijgewerkt", c_form: "Formulier", c_contact: "Contact", c_messages: "Berichten",
    yes: "ja", no: "nee", none: "geen", count: n => `${n} reservaties`, no_res: "Geen reservaties",
    hours_a: "Nieuwe reservaties van de laatste", hours_b: "uur", run: "Robot nu draaien",
    r_start: "Start", r_duration: "Duur", r_task: "Taak", r_result: "Resultaat", r_found: "Gevonden", r_new: "Nieuw", r_error: "Opmerking",
    all_tasks: "Alle", sub_log: "Logboek robot", del: "Verwijderen", del_confirm: "Deze regel uit het logboek verwijderen?", del_all: "Alles verwijderen",
    del_all_confirm: (n, task) => `${n} regels${task ? ` van "${task}"` : ""} uit het logboek verwijderen?`, t_login: "aanmelden", t_list: "lijst", t_contact: (n, sec) => `${n} contact${n > 1 ? "en" : ""} à ${sec} s`, task_nieuwe_reservaties: "Nieuwe reservaties", task_contactgegevens_nalezen: "Reservaties bijwerken", task_meldingen: "Meldingen per mail", task_onderhoud: "Gasten synchroniseren", task_berichten: "Berichten",
    ok: "ok", fail: "fout", busy: "De robot is bezig...", scheduled: "Draait ook automatisch op schema.",
    not_installed: "De robot is in deze omgeving nog niet geïnstalleerd.", no_runs: "Nog geen afgeronde run",
    load_error: "Fout bij laden",
    exec_title: "Runs volgens Azure", exec_end: "Einde", exec_status: "Status", exec_name: "Naam",
  },
  en: {
    title: "Check-in monitor", hotel: "Hotel", tab_res: "Reservations", tab_robot: "Robot", tab_guests: "Guests", tab_workflow: "Workflow",
    wf_save: "Save", wf_reset: "Back to default", wf_saved: "Saved.", wf_dirty: "Unsaved changes.",
    wf_reset_confirm: "Reset the workflow to the default from the hotel file? All changes will be lost.",
    wf_from_file: "Default from the hotel file", wf_changed: (who, when) => `Changed by ${who} on ${when}`,
    wf_leave: "There are unsaved changes. Continue anyway?",
    flow_booking: "Booking.com", flow_expedia: "Expedia", flow_website_paid: "Website, paid", flow_website_unpaid: "Website, not paid",
    wf_start: "Booking comes in", wf_arrival: "Arrival", wf_departure: "Departure", wf_days_after: n => `${n} day${n === 1 ? "" : "s"} after departure`,
    step_thank_you: "Thank-you mail after the stay", step_payment_request: "Payment request (amount still open after departure)",
    short_thank_you: "Thank you", short_payment_request: "Payment request", when_days_after_departure: "days after departure", c_not_paid: "not (fully) paid",
    wf_not_ready_access_code: "waiting for Salto", wf_not_ready_payment_request: "waiting for Saferpay", wf_days_before: n => `${n} day${n === 1 ? "" : "s"} before arrival`,
    wf_right_after: "Right after booking", step_confirmation: "Confirmation with link to the check-in form",
    step_reminder: "Reminder (form not filled in)", step_access_code: "Code and practical info",
    f_enabled: "Active", f_when: "When", f_days: "Days before arrival", f_channels: "Channels", f_only_if: "Only if",
    f_replaced_by: "Skip if already due", f_late: "Only if the booking came in before that day (otherwise the guest just got the confirmation)",
    wf_later_rule: "This mail is not sent if a later mail is already due at that moment (e.g. with a late booking the guest only gets the code mail).", f_pay: "Pay button", f_content: "In the mail", g_when: "When to send", wf_example: "Example mail", pv_subject: "Subject",
    m_reservation: "reservation details", m_checkin_form: "check-in form link", m_code: "PIN code", m_practical_info: "practical info", m_pay: "pay button",
    wf_pay_note: "Button to pay the open amount online: just the city tax or everything, whatever is still open in Lighthouse.",
    wf_form_note: "The form link is left out automatically when the guest already filled it in.",
    when_after_booking: "after booking", when_days_before_arrival: "days before arrival",
    ch_email: "e-mail", ch_sms: "SMS", ch_whatsapp: "WhatsApp",
    pay_none: "none", pay_open_amount: "open amount", pay_city_tax: "city tax",
    c_not_cancelled: "not cancelled", c_form_completed: "form filled in", c_form_not_completed: "form not filled in",
    c_paid: "paid", c_checked_in: "checked in", c_has_email: "e-mail known", c_has_phone: "phone known",
    wf_rules: "Recognised by", wf_sources: "Channel contains (comma separated)", wf_other: "All other channels",
    wf_paid_yes: "and fully paid", wf_paid_no: "and not (fully) paid",
    wf_params: "Parameters (all flows)", p_city_tax: "City tax", p_unit: "Per", unit_person_night: "person per night",
    unit_person_stay: "person per stay", p_currency: "Currency", wf_not_ready: "not built yet (Salto)", wf_off: "off",
    returning: n => `returning (${n}×)`, mg_message: "Message", mg_time: "Time", short_confirmation: "Confirmation", short_reminder: "Reminder", short_access_code: "Code mail", mg_channel: "Channel", mg_to: "To",
    mg_title: (num, guest) => `Messages for ${guest} (${num})`, mg_click: "Click for all details",
    mg_plan: "Timeline", mg_attempts: "All attempts", mg_next: "next",
    pl_sent: "sent", pl_failed: "failed", pl_planned: "planned", pl_due: "next run", pl_skipped: "skipped", pl_off: "not active", tab_hotel: "Hotel",
    hs_intro: "Hotel details and settings. Default from the hotel file; what you change here takes precedence (in this environment only).",
    hs_default: "default", hs_env: "Set for this environment in Key Vault or the Function App: that value takes precedence.",
    hs_add: "Add", hs_key: "name", hs_value: "value", hs_reset_confirm: "Reset all settings to the hotel file? All changes will be lost.",
    hs_list: "comma separated",
    sec_hotel: "Hotel", sec_verzending: "Mail sender", sec_receptie: "Reception", sec_checkout: "Check-out", sec_ontbijt: "Breakfast",
    sec_wifi: "Wi-Fi", sec_parking: "Parking", sec_nood: "Emergency number", sec_twilio: "Twilio (SMS and WhatsApp)", sec_robot: "Robot",
    sec_messaging: "Messages", sec_whatsapp: "WhatsApp templates", sec_retention: "Retention", sec_salto: "Salto",
    sec_salto_rooms: "Salto: rooms and doors", sec_lighthouse: "Lighthouse", sec_checkin: "Check-in form",
    sec_privacy: "Privacy statement", sec_kleuren: "Colours", settings: "Settings", back: "Monitor", open_lh: "Open in Lighthouse", pl_not_tried: "not tried", backup: "extra address from the check-in form",
    rs_now: "Send now", rs_again: "Send again", rs_confirm: (step, ch, to) => `Send ${step} now by ${ch} to ${to}?`,
    chr_muted: "switched off for this guest", chr_phone_off: "not active yet (Twilio)", chr_fallback: "only if WhatsApp fails",
    rs_disabled: "step is off", rs_messaging_off: "messages are off in this environment", rs_before_start: "reservation from before the start",
    rs_booked_late: "booked too late", rs_later_due: "a later mail is already due", rs_not_ready: "not built yet",
    rs_no_contact: "no e-mail or phone", rs_window_passed: "moment passed", rs_condition: "condition not met",
    g_msgs: "Messages", g_mute_hint: "Unchecked: never use this channel for this guest",
    st_sent: "sent", st_failed: "failed", st_delivered: "delivered", st_read: "read", st_undelivered: "not delivered", show_guest: "Show guest data", show_res: "Show this guest's reservations",
    g_update: "Synchronize", g_busy: "Working...", g_done: d => `${d.linked} linked, ${d.counted} stays and ${d.cancellations} cancellations counted, ${d.reservations_deleted} old reservations and ${d.guests_deleted} guests deleted`,
    g_search: "Search name, e-mail, phone", g_count: n => `${n} guests`, g_country: "Country", g_stays: "Stays", g_cancelled: "Cancelled",
    g_avg_nights: "Avg nights", g_avg_persons: "Avg pers.", g_first: "First stay", g_last: "Last stay",
    g_channel: "Channel", g_rooms: "Rooms", g_relay: "relay address, not for marketing", g_form: "form",
    g_optout: "no marketing", no_guests: "No guests yet (click Synchronize)",
    m_title: n => `Possible duplicates (${n})`, m_help: "Same or almost the same name in the same country. Never merged automatically.",
    m_same_name: "same name", m_extra_contact: "extra address or number of one is that of the other (same person or partner?)", m_similar_name: "similar name", m_merge: "Merge", m_different: "Different person",
    m_confirm: "Merge these two guests into one?", reset: "Clear filter",
    search: "Search name, number, e-mail", stay_from: "Stay from", stay_to: "to", from_today: "From today",
    c_arrival: "Arrival", c_departure: "Departure", c_number: "Number", c_guest: "Guest", c_pers: "Pers.",
    c_room: "Room", c_via: "Via", c_booked: "Booked", c_added: "Added", c_updated: "Updated", c_form: "Form", c_contact: "Contact", c_messages: "Messages",
    yes: "yes", no: "no", none: "none", count: n => `${n} reservations`, no_res: "No reservations",
    hours_a: "New reservations of the last", hours_b: "hours", run: "Run robot now",
    r_start: "Start", r_duration: "Duration", r_task: "Task", r_result: "Result", r_found: "Found", r_new: "New", r_error: "Note",
    all_tasks: "All", sub_log: "Robot log", del: "Delete", del_confirm: "Delete this line from the log?", del_all: "Delete all",
    del_all_confirm: (n, task) => `Delete ${n} lines${task ? ` of "${task}"` : ""} from the log?`, t_login: "login", t_list: "list", t_contact: (n, sec) => `${n} contact${n > 1 ? "s" : ""} × ${sec} s`, task_nieuwe_reservaties: "New reservations", task_contactgegevens_nalezen: "Update reservations", task_meldingen: "Mail notifications", task_onderhoud: "Synchronize guests", task_berichten: "Messages",
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
const TASKS = ["nieuwe_reservaties", "contactgegevens_nalezen", "meldingen", "onderhoud", "berichten"];
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
if ($("#from")) $("#from").value = todayIso();

function setLang(l) {
  lang = T[l] ? l : "nl";
  store("lang", lang);
  document.documentElement.lang = lang;
  document.querySelectorAll("[data-t]").forEach(e => { e.textContent = t(e.dataset.t); });
  document.querySelectorAll("[data-tp]").forEach(e => { e.placeholder = t(e.dataset.tp); });
  document.querySelectorAll("[data-tt]").forEach(e => { e.title = t(e.dataset.tt); });
  document.querySelectorAll(".langs button").forEach(b => b.classList.toggle("active", b.dataset.lang === lang));
  if (PAGE === "main") { render(); renderGuests(); } else { renderWorkflow(); renderSettings(); if (runsData) renderRuns(runsData); }
}

async function init() {
  document.querySelectorAll(".langs button").forEach(b => b.onclick = () => setLang(b.dataset.lang));
  setLang(store("lang") || (navigator.language || "nl").slice(0, 2));
  const hotels = await get("/api/monitor/hotels");
  $("#hotel").innerHTML = hotels.map(h => `<option value="${esc(h.id)}">${esc(h.name)}</option>`).join("");
  const saved = store("hotel");
  if (saved && hotels.some(h => h.id === saved)) $("#hotel").value = saved;
  $("#hotel").onchange = () => { store("hotel", $("#hotel").value); load(); };
  if ($("#version").textContent.includes("__")) $("#version").textContent = "dev";  // lokaal, niet uitgerold
  // Twee aparte pagina's: de monitor (index.html: reservaties, gasten) en de instellingen
  // (settings.html: workflow, robot). Elk met eigen tabbladen en eigen adres per tabblad (#...).
  document.querySelectorAll("nav button[data-tab]").forEach(b => b.onclick = () => showTab(b.dataset.tab));
  window.addEventListener("hashchange", () => { const n = location.hash.slice(1); if (TABS.includes(n) && n !== current) showTab(n); });
  showTab(TABS.includes(location.hash.slice(1)) ? location.hash.slice(1) : TABS[0], true);
  if (PAGE === "main") {
    $("#g-search").oninput = renderGuests;
    // Filter wissen: zoekvak leeg (reservaties: ook terug "vanaf vandaag")
    $("#search-reset").onclick = () => { $("#search").value = ""; $("#from").value = todayIso(); $("#to").value = ""; render(); };
    $("#g-search-reset").onclick = () => { $("#g-search").value = ""; renderGuests(); };
    $("#g-update").onclick = updateGuests;
    $("#msgs-close").onclick = () => { $("#msgs").hidden = true; };
    $("#msgs").onclick = e => { if (e.target.id === "msgs") $("#msgs").hidden = true; };
    document.querySelectorAll("#g-head th[data-gsort]").forEach(th => th.onclick = () => gSortBy(th.dataset.gsort));
    $("#search").oninput = render;
    document.querySelectorAll("#res-head th[data-sort]").forEach(th => th.onclick = () => sortBy(th.dataset.sort));
    $("#from").onchange = render;
    $("#to").onchange = render;
    $("#today").onclick = () => { $("#from").value = todayIso(); $("#to").value = ""; render(); };
  } else {
    document.querySelectorAll("#tab-robot .subtabs button").forEach(b => b.onclick = () => showSub(b.dataset.sub));
    $("#bin-all").innerHTML = BIN;
    $("#bin-all").onclick = deleteAllRuns;
    $("#wf-save").onclick = saveWorkflow;
    $("#hs-save").onclick = saveSettings;
    $("#hs-reset").onclick = resetSettings;
    $("#wf-reset").onclick = resetWorkflow;
    $("#pv-close").onclick = () => { $("#preview").hidden = true; };
    $("#preview").onclick = e => { if (e.target.id === "preview") $("#preview").hidden = true; };
    $("#task").onchange = () => {
      taskFilter = $("#task").value;
      try { localStorage.setItem("monitor-task", taskFilter); } catch (e) { /* geen opslag */ }
      if (runsData) renderRuns(runsData);
    };
    $("#run").onclick = runRobot;
    // Niet bewaarde wijzigingen in de workflow: waarschuwen bij het verlaten van de pagina
    window.addEventListener("beforeunload", e => { if (wfDirty || hsDirty) { e.preventDefault(); e.returnValue = ""; } });
  }
  load();
}

const PAGE = document.body.dataset.page || "main";
const TABS = PAGE === "settings" ? ["workflow", "hotel", "robot"] : ["res", "guests"];
let current = TABS[0];
function showTab(name, initial = false) {
  if (((wfDirty && current === "workflow") || (hsDirty && current === "hotel")) && name !== current && !confirm(t("wf_leave"))) {
    if (location.hash.slice(1) !== current) history.replaceState(null, "", "#" + current);
    return;
  }
  current = name;
  document.querySelectorAll("nav button[data-tab]").forEach(x => x.classList.toggle("active", x.dataset.tab === name));
  TABS.forEach(n => { $(`#tab-${n}`).hidden = n !== name; });
  if (location.hash.slice(1) !== name) history[initial ? "replaceState" : "pushState"](null, "", "#" + name);
}

async function load() {
  if (PAGE === "settings") {
    loadWorkflow();
    loadSettings();
    loadRuns();
    return;
  }
  rows = await get(`/api/monitor/${$("#hotel").value}/reservations`);
  render();
  loadGuests();
  loadWorkflow();  // stappen die al verstuurd kunnen worden (tijdlijn per reservatie)
}

// ---------------------------------------------------------------- berichten per reservatie
// In de lijst kort: per bericht één label (groen als het per alle kanalen lukte, rood als iets
// mislukte). Klik: alle pogingen met kanaal, ontvanger, status en fout.
const CH = { email: "ch_email", whatsapp: "ch_whatsapp", sms: "ch_sms" };
function msgSummary(r) {
  if (!r.messages.length) {
    const next = (r.plan || []).find(p => p.state === "planned" || p.state === "due");
    const label = next ? `${t("mg_next")}: ${stepShort(next.step)} ${day(next.due)}` : t("none");
    return `<a href="#" class="msgs muted" data-msgs="${esc(r.id)}" title="${esc(t("mg_click"))}">${esc(label)}</a>`;
  }
  const byType = {};
  r.messages.forEach(m => { (byType[m.type] = byType[m.type] || []).push(m); });
  const tags = Object.entries(byType).map(([type, ms]) => {
    const channels = [...new Set(ms.filter(m => m.ok).map(m => t(CH[m.channel] || m.channel)))];
    const bad = ms.some(m => !m.ok) && !channels.length;
    const partly = ms.some(m => !m.ok) && channels.length;
    return `<span class="tag ${bad ? "fail" : partly ? "warn" : ""}">${esc(stepShort(type))}${channels.length ? ": " + esc(channels.join(", ")) : ""}</span>`;
  });
  return `<a href="#" class="msgs" data-msgs="${esc(r.id)}" title="${esc(t("mg_click"))}">${tags.join("")}</a>`;
}
const stepShort = type => T[lang]["short_" + type] || type;

function showMessages(id) {
  const r = rows.find(x => x.id === id);
  if (!r) return;
  $("#msgs-title").textContent = t("mg_title", r.booking_number, r.guest);
  $("#msgs-plan").innerHTML = (r.plan || []).map(p => {
    const mine = r.messages.filter(m => m.type === p.step);
    const sent = mine.filter(m => m.ok);
    const when = p.state === "sent" && sent.length ? stamp(sent[0].at) : day(p.due);
    // per kanaal: laatste poging uit het log, anders wat er gaat gebeuren
    // per kanaal en adres: laatste poging uit het log, anders wat er gaat gebeuren
    const key = (ch, to) => ch + "|" + (to || "").toLowerCase();
    const targets = new Map();
    (p.channels || []).forEach(c => targets.set(key(c.channel, c.to), c));
    mine.forEach(m => { if (!targets.has(key(m.channel, m.to))) targets.set(key(m.channel, m.to), { channel: m.channel, to: m.to, reason: "" }); });
    const firstOf = {};
    const chips = [...targets.values()].map(c => {
      const ch = c.channel;
      const tries = mine.filter(m => key(m.channel, m.to) === key(ch, c.to));
      const last = tries[tries.length - 1];
      const nr = (firstOf[ch] = (firstOf[ch] || 0) + 1);
      let cls = "", txt;
      if (last) {
        cls = last.ok ? "ok" : "fail";
        txt = (t("st_" + last.status) || last.status) + (tries.length > 1 ? ` (${tries.length}×)` : "");
      } else if (["sent", "failed", "planned", "due"].includes(p.state)) {
        txt = c.reason ? t("chr_" + c.reason) : t("pl_" + (p.state === "sent" || p.state === "failed" ? "not_tried" : p.state));
        cls = c.reason ? "off" : "todo";
      } else return "";
      const title = [c.to, last && stamp(last.at), last && last.error, last && last.note].filter(Boolean).join(" · ");
      const canSend = READY.includes(p.step) && c.reason !== "phone_off" && c.to;
      const btn = canSend ? `<button type="button" class="resend" title="${esc(last ? t("rs_again") : t("rs_now"))}" data-step="${esc(p.step)}" data-ch="${esc(ch)}" data-to="${esc(c.to)}">&#8635;</button>` : "";
      return `<span class="tag ch ${cls}" title="${esc(title)}">${esc(t(CH[ch] || ch))}${nr > 1 ? " 2" : ""}: ${esc(txt)}${btn}</span>`;
    }).join("");
    return `<li class="pl-${p.state}"><span class="dot"></span><strong>${esc(stepShort(p.step))}</strong>
      <span class="muted">${esc(when)}</span> <span class="tag pl">${esc(t("pl_" + p.state))}</span>
      ${p.reason ? `<span class="muted">${esc(reasonText(p.reason))}</span>` : ""}
      ${chips ? `<div class="chs">${chips}</div>` : ""}</li>`;
  }).join("");
  $("#msgs-attempts").hidden = !r.messages.length;
  document.querySelectorAll("#msgs-plan button.resend").forEach(b => b.onclick = async () => {
    if (!confirm(t("rs_confirm", stepShort(b.dataset.step), t(CH[b.dataset.ch]), b.dataset.to))) return;
    b.disabled = true;
    const q = new URLSearchParams({ id: r.id, step: b.dataset.step, channel: b.dataset.ch, to: b.dataset.to });
    const d = await get(`/api/monitor/${$("#hotel").value}/resend?${q}`, { method: "POST" }).catch(e => ({ ok: false, error: String(e) }));
    if (!d.ok) alert(d.error || t("load_error"));
    await load();
    showMessages(r.id);
  });
  $("#msgs-rows").innerHTML = [...r.messages].reverse().map(m => `<tr>
    <td>${stamp(m.at)}</td><td>${esc(stepShort(m.type))}</td><td>${esc(t(CH[m.channel] || m.channel))}</td>
    <td>${esc(m.to)}</td><td class="${m.ok ? "ok" : "err"}">${esc(t("st_" + m.status) || m.status)}${m.status_at ? ` <span class="muted">${esc(stamp(m.status_at))}</span>` : ""}</td>
    <td class="wrap">${esc([m.error, m.note].filter(Boolean).join(". "))}</td></tr>`).join("");
  $("#msgs").hidden = false;
}

function reasonText(reason) {
  if (reason.startsWith("condition:")) return `${t("rs_condition")}: ${reason.slice(10).split(",").map(c => t("c_" + c) || c).join(", ")}`;
  return t("rs_" + reason) || reason;
}

// ---------------------------------------------------------------- gasten
let guestData = { guests: [], matches: [] };
const ICON_GUEST = `<svg viewBox="0 0 16 16" width="12" height="12" aria-hidden="true"><path fill="currentColor" d="M8 8a3 3 0 1 0 0-6 3 3 0 0 0 0 6zm-5 6c0-2.8 2.2-4.5 5-4.5s5 1.7 5 4.5v.5H3v-.5z"/></svg>`;
const ICON_LH = `<svg viewBox="0 0 16 16" width="14" height="14" aria-hidden="true" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"><path d="M9 2h5v5M14 2 7.5 8.5M12 9.5V13a1 1 0 0 1-1 1H3a1 1 0 0 1-1-1V5a1 1 0 0 1 1-1h3.5"/></svg>`;
const ICON_RES = `<svg viewBox="0 0 16 16" width="12" height="12" aria-hidden="true"><path fill="currentColor" d="M4 1h1v1.5h6V1h1v1.5h2V15H2V2.5h2V1zm-1 5v8h10V6H3zm2 2h2v2H5V8z"/></svg>`;
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

// Van een reservatie naar de gast, en van een gast naar zijn reservaties: gewoon het zoekvak invullen
function openGuest(id) { $("#g-search").value = guestById(id)?.name || ""; showTab("guests"); renderGuests(); }
function openReservations(id) {
  $("#search").value = guestById(id)?.name || "";
  $("#from").value = ""; $("#to").value = "";  // ook voorbije verblijven
  showTab("res"); render();
}

function contactCell(g) {
  const tags = [];
  if (g.email && !g.email_own) tags.push(`<span class="tag" title="${esc(t("g_relay"))}">OTA</span>`);
  if (g.form) tags.push(`<span class="tag">${esc(t("g_form"))}</span>`);
  if (g.opt_out) tags.push(`<span class="tag fail">${esc(t("g_optout"))}</span>`);
  return `${contactLines(g)} ${tags.join("")}`;
}

// Hoofdadres en nummer, plus het extra adres en nummer uit het check-in-formulier
function contactLines(x) {
  const extra = v => `<span class="muted" title="${esc(t("backup"))}">${esc(v)} (2)</span>`;
  return [x.email && esc(x.email), x.backup_email && extra(x.backup_email), x.phone && esc(x.phone), x.backup_phone && extra(x.backup_phone)]
    .filter(Boolean).join("<br>");
}

function renderGuests() {
  const q = $("#g-search").value.toLowerCase();
  const list = guestData.guests.filter(g => (!q || [g.name, g.email, g.phone, g.backup_email, g.backup_phone].join(" ").toLowerCase().includes(q)));
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
      <td>${g.reservations.length ? `<a href="#" class="jump" data-res="${esc(g.id)}" title="${esc(t("show_res"))}">${esc(g.name)}</a>` : esc(g.name)}</td><td class="wrap">${contactCell(g)}</td>
      <td>${esc(g.country)}${g.language ? ` <span class="muted">${esc(g.language)}</span>` : ""}</td>
      <td>${g.stays}</td><td>${g.cancellations ? `<span title="${esc(day(g.last_cancelled))}">${g.cancellations}</span>` : ""}</td><td>${g.avg_nights ?? ""}</td><td>${g.avg_persons ?? ""}</td>
      <td>${day(g.first_stay)}</td><td>${day(g.last_stay)}</td>
      <td title="${esc(g.channels.map(c => `${c.name} ${c.count}×`).join(", "))}">${esc(g.preferred_channel)}</td>
      <td>${esc(g.rooms.join(", "))}${g.room_type ? ` <span class="muted">${esc(g.room_type)}</span>` : ""}</td>
      <td>${g.reservations.length ? `<a href="#" class="jump" data-res="${esc(g.id)}" title="${esc(t("show_res"))}">${ICON_RES} ${g.reservations.length}</a>` : "0"}</td>
      <td class="mute" title="${esc(t("g_mute_hint"))}">${["email", "whatsapp", "sms"].map(c => `<label class="chk"><input type="checkbox" data-mute="${esc(g.id)}" value="${c}" ${(g.muted || []).includes(c) ? "" : "checked"}> ${esc(t(CH[c]))}</label>`).join("")}</td>
    </tr>`).join("") || `<tr><td colspan="13" class="muted">${t("no_guests")}</td></tr>`;
  document.querySelectorAll("#guests a[data-res]").forEach(a => a.onclick = e => { e.preventDefault(); openReservations(a.dataset.res); });
  document.querySelectorAll("#guests input[data-mute]").forEach(el => el.onchange = async () => {
    const id = el.dataset.mute;
    const muted = [...document.querySelectorAll(`#guests input[data-mute="${id}"]`)].filter(x => !x.checked).map(x => x.value);
    const g = guestById(id);
    if (g) g.muted = muted;
    await get(`/api/monitor/${$("#hotel").value}/guests?action=channels&a=${encodeURIComponent(id)}&muted=${muted.join(",")}`, { method: "POST" });
  });
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
  const list = rows.filter(r => (!from || r.departure >= from) && (!to || r.arrival <= to) &&
    (!q || [r.guest, r.booking_number, r.email, r.phone, r.backup_email, r.backup_phone].join(" ").toLowerCase().includes(q)));
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
      <td class="nowrap">${esc(r.booking_number)}${r.lighthouse_url ? ` <a class="lh" href="${esc(r.lighthouse_url)}" target="_blank" rel="noopener" title="${esc(t("open_lh"))}">${ICON_LH}</a>` : ""}</td><td>${r.guest_id && guestById(r.guest_id) ? `<a href="#" class="jump" data-guest="${esc(r.guest_id)}" title="${esc(t("show_guest"))}">${ICON_GUEST} ${esc(r.guest)}</a>` : esc(r.guest)}${r.guest_stays ? ` <span class="tag back">${esc(t("returning", r.guest_stays))}</span>` : ""}</td><td>${esc(r.guests ?? "")}</td>
      <td>${esc(r.rooms.join(", ") || r.room_type)}</td><td>${esc(r.source)}</td><td>${esc(r.pms_status)}</td>
      <td>${stamp(r.booked_at)}</td><td>${stamp(r.added_at)}</td><td>${stamp(r.updated_at)}</td>
      <td>${r.checkin_completed_at ? `<span class="ok">${t("yes")}</span> ${stamp(r.checkin_completed_at)}` : `<span class="muted">${t("no")}</span>`}</td>
      <td class="wrap">${contactLines(r)}</td>
      <td class="wrap">${msgSummary(r)}</td>
    </tr>`).join("") || `<tr><td colspan="14" class="muted">${t("no_res")}</td></tr>`;
  document.querySelectorAll("#res a[data-guest]").forEach(a => a.onclick = e => { e.preventDefault(); openGuest(a.dataset.guest); });
  document.querySelectorAll("#res a[data-msgs]").forEach(a => a.onclick = e => { e.preventDefault(); showMessages(a.dataset.msgs); });
}

async function loadRuns() {
  if (PAGE !== "settings") return;
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
  document.querySelectorAll("#tab-robot .subtabs button").forEach(b => b.classList.toggle("active", b.dataset.sub === name));
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



// ---------------------------------------------------------------- workflow (tabblad Workflow)
// Per flow een tijdlijn van boven (boeking) naar onder (aankomst). Alles wat hier verandert,
// bewaart de server in de database; de processen lezen het meteen.
let wf = null, wfFlow = "booking", wfDirty = false;
let READY = ["confirmation", "reminder", "thank_you"];  // stappen die al echt verstuurd worden (komt van de server)

async function loadWorkflow() {
  try { wf = await get(`/api/monitor/${$("#hotel").value}/workflow`); } catch (e) { return; }
  if (wf.ready) READY = wf.ready;
  wfDirty = false;
  renderWorkflow();
}

function setDirty() { wfDirty = true; $("#wf-save").disabled = false; $("#wf-state").textContent = t("wf_dirty"); }

function wfMeta() {
  if (!wf) return "";
  return wf.meta.source === "monitor" ? t("wf_changed", wf.meta.updated_by || "?", stamp(wf.meta.updated_at)) : t("wf_from_file");
}

function renderWorkflow() {
  if (!wf || !$("#wf-flows")) return;
  const c = wf.choices;
  $("#wf-flows").innerHTML = c.flows.map(f => `<button type="button" data-flow="${f}" class="${f === wfFlow ? "active" : ""}">${esc(t("flow_" + f))}</button>`).join("");
  document.querySelectorAll("#wf-flows button").forEach(b => b.onclick = () => { wfFlow = b.dataset.flow; renderWorkflow(); });
  $("#wf-meta").textContent = wfMeta();
  $("#wf-save").disabled = !wfDirty;
  const flow = wf.flows[wfFlow];
  // volgorde op de tijdlijn: na de boeking eerst, dan van ver naar dicht bij de aankomst
  if (wf.ready) READY = wf.ready;
  // volgorde: na de boeking, dan van ver naar dicht bij de aankomst, dan na het vertrek
  const pos = s => s.when === "after_booking" ? -1e6 : s.when === "days_after_departure" ? 1e6 + s.days : -s.days;
  const order = flow.steps.map((s, i) => ({ s, i })).sort((a, b) => pos(a.s) - pos(b.s));
  const node = (cls, label) => `<div class="tl-node ${cls}"><span class="dot"></span><strong>${esc(label)}</strong></div>`;
  const cards = phase => order.filter(({ s }) => (s.when === "days_after_departure") === (phase === "after"))
    .map(({ s, i }) => stepCard(s, i, flow, c)).join("");
  $("#wf-timeline").innerHTML = `<div class="tl-phase before">${node("start", t("wf_start"))}${cards("before")}</div>` +
    `<div class="tl-phase stay">${node("arrival", t("wf_arrival"))}${node("departure", t("wf_departure"))}</div>` +
    `<div class="tl-phase after">${cards("after")}</div>`;
  bindSteps(flow);
  renderSide(flow, c);
}

function checks(name, idx, options, chosen, label) {
  return options.map(o => `<label class="chk"><input type="checkbox" data-i="${idx}" data-f="${name}" value="${esc(o)}" ${chosen.includes(o) ? "checked" : ""}> ${esc(label(o))}</label>`).join("");
}

// Ligt stap b later (dichter bij de aankomst) dan stap a?
const isLater = (b, a) => b && b.enabled && b.when === "days_before_arrival" && (a.when === "after_booking" || b.days < a.days);

function stepCard(s, i, flow, c) {
  const others = flow.steps.map(x => x.step).filter(x => x !== s.step);
  const when = s.when === "after_booking" ? t("wf_right_after")
    : s.when === "days_after_departure" ? t("wf_days_after", s.days) : t("wf_days_before", s.days);
  const notReady = READY.includes(s.step) ? "" : ` <span class="tag">${esc(t("wf_not_ready_" + s.step) || t("wf_not_ready"))}</span>`;
  return `<div class="tl-step ${s.enabled ? "" : "off"}">
    <div class="tl-when"><span class="dot"></span>${esc(when)}</div>
    <div class="card">
      <div class="card-head"><label class="chk title" title="${esc(t("f_enabled"))}"><input type="checkbox" data-i="${i}" data-f="enabled" ${s.enabled ? "checked" : ""}> <strong>${esc(t("step_" + s.step))}</strong></label>${notReady}
        <button type="button" class="link right" data-preview="${i}">${esc(t("wf_example"))}</button></div>
      ${others.some(o => isLater(flow.steps.find(x => x.step === o), s)) ? `<p class="info top">${esc(t("wf_later_rule"))}</p>` : ""}
      <div class="group">
        <div class="group-title">${esc(t("g_when"))}</div>
        <div class="fields">
          <label><span class="lbl">${esc(t("f_when"))}</span>
            ${s.when !== "after_booking" ? `<input type="number" class="days" min="0" max="365" data-i="${i}" data-f="days" value="${s.days}">` : ""}
            <select data-i="${i}" data-f="when">${c.when.map(w => `<option value="${w}" ${w === s.when ? "selected" : ""}>${esc(t("when_" + w))}</option>`).join("")}</select></label>
          <div><span class="lbl">${esc(t("f_only_if"))}</span>${checks("only_if", i, c.conditions, s.only_if, x => t("c_" + x))}</div>
          ${s.when === "days_before_arrival" ? `<label class="chk"><input type="checkbox" data-i="${i}" data-f="skip_if_booked_late" ${s.skip_if_booked_late ? "checked" : ""}> ${esc(t("f_late"))}</label>` : ""}
        </div>
      </div>
      <div class="group">
        <div class="group-title">${esc(t("f_content"))}</div>
        <div class="fields"><div>${CONTENT.map(m => `<label class="chk" title="${m === "checkin_form" ? esc(t("wf_form_note")) : ""}"><input type="checkbox" data-i="${i}" data-f="content" value="${m}" ${contentOf(s)[m] ? "checked" : ""}> ${esc(t("m_" + m))}</label>`).join("")}<label class="chk" title="${esc(t("wf_pay_note"))}"><input type="checkbox" data-i="${i}" data-f="pay" ${s.pay !== "none" ? "checked" : ""}> ${esc(t("m_pay"))}</label></div></div>
      </div>
    </div></div>`;
}

const CONTENT = ["reservation", "checkin_form", "code", "practical_info"];
const DEFAULT_CONTENT = {
  confirmation: { reservation: true, checkin_form: true, code: false, practical_info: false },
  reminder: { reservation: true, checkin_form: true, code: false, practical_info: false },
  access_code: { reservation: false, checkin_form: false, code: true, practical_info: true },
  thank_you: { reservation: false, checkin_form: false, code: false, practical_info: false },
  payment_request: { reservation: true, checkin_form: false, code: false, practical_info: false },
};
const contentOf = s => ({ ...(DEFAULT_CONTENT[s.step] || {}), ...(s.content || {}) });

// Voorbeeldmail: de stap zoals ze nu op het scherm staat (ook als ze nog niet bewaard is)
let pvStep = null, pvLang = "nl";
async function showPreview(step) {
  pvStep = step;
  $("#preview").hidden = false;
  $("#pv-title").textContent = `${t("wf_example")}: ${t("step_" + step.step)} (${t("flow_" + wfFlow)})`;
  $("#pv-langs").innerHTML = ["nl", "fr", "en", "de"].map(l => `<button type="button" data-l="${l}" class="${l === pvLang ? "active" : ""}">${l.toUpperCase()}</button>`).join("");
  document.querySelectorAll("#pv-langs button").forEach(b => b.onclick = () => { pvLang = b.dataset.l; showPreview(pvStep); });
  const r = await fetch(API + `/api/monitor/${$("#hotel").value}/preview`, {
    method: "POST", headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ step, flow: wfFlow, language: pvLang, parameters: wf.parameters }),
  });
  const d = await r.json().catch(() => ({}));
  $("#pv-subject").textContent = d.error ? d.error : `${t("pv_subject")}: ${d.subject}`;
  // Links in de voorbeeldmail (check-in-formulier, website, ...) openen in een nieuw tabblad
  const html = d.html || "";
  $("#pv-frame").srcdoc = /<head[\s>]/i.test(html) ? html.replace(/<head([^>]*)>/i, '<head$1><base target="_blank">') : '<base target="_blank">' + html;
}

function bindSteps(flow) {
  document.querySelectorAll("#wf-timeline [data-preview]").forEach(b => b.onclick = () => showPreview(flow.steps[+b.dataset.preview]));
  document.querySelectorAll("#wf-timeline [data-f]").forEach(el => el.onchange = () => {
    const s = flow.steps[+el.dataset.i], f = el.dataset.f;
    if (f === "content") {
      s.content = { ...contentOf(s), [el.value]: el.checked };
    } else if (["channels", "only_if", "replaced_by"].includes(f)) {
      s[f] = [...document.querySelectorAll(`#wf-timeline [data-i="${el.dataset.i}"][data-f="${f}"]:checked`)].map(x => x.value);
    } else if (f === "pay") {
      s.pay = el.checked ? "open_amount" : "none";
    } else if (f === "enabled" || f === "skip_if_booked_late") {
      s[f] = el.checked;
    } else if (f === "days") {
      s.days = Math.max(0, Math.min(365, parseInt(el.value || "0", 10)));
    } else {
      s[f] = el.value;
      if (f === "when" && el.value === "after_booking") s.days = 0;
    }
    setDirty();
    renderWorkflow();
  });
}

function renderSide(flow, c) {
  const p = wf.parameters;
  const rule = flow.sources.length
    ? `<label>${esc(t("wf_sources"))}<input id="wf-sources" type="text" value="${esc(flow.sources.join(", "))}"></label>`
    : `<p>${esc(t("wf_other"))} ${esc(t(flow.paid ? "wf_paid_yes" : "wf_paid_no"))}</p>`;
  $("#wf-side").innerHTML = `
    <h3>${esc(t("wf_rules"))}</h3>${rule}
    <h3>${esc(t("wf_params"))}</h3>
    <label>${esc(t("p_city_tax"))} <input id="wf-tax" type="number" min="0" step="0.01" value="${p.city_tax_amount}"></label>
    <label>${esc(t("p_unit"))} <select id="wf-unit">${c.city_tax_units.map(u => `<option value="${u}" ${u === p.city_tax_unit ? "selected" : ""}>${esc(t("unit_" + u))}</option>`).join("")}</select></label>
    <label>${esc(t("p_currency"))} <input id="wf-cur" type="text" maxlength="3" value="${esc(p.currency)}"></label>`;
  const src = $("#wf-sources");
  if (src) src.onchange = () => { flow.sources = src.value.split(",").map(x => x.trim()).filter(Boolean); setDirty(); };
  $("#wf-tax").onchange = () => { p.city_tax_amount = parseFloat($("#wf-tax").value || "0"); setDirty(); };
  $("#wf-unit").onchange = () => { p.city_tax_unit = $("#wf-unit").value; setDirty(); };
  $("#wf-cur").onchange = () => { p.currency = $("#wf-cur").value.toUpperCase(); setDirty(); };
}

async function saveWorkflow() {
  const r = await fetch(API + `/api/monitor/${$("#hotel").value}/workflow`, {
    method: "POST", headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ parameters: wf.parameters, flows: wf.flows }),
  });
  const d = await r.json().catch(() => ({}));
  if (!r.ok) { $("#wf-state").textContent = d.error || `${t("load_error")} ${r.status}`; $("#wf-state").className = "err"; return; }
  wf = d; wfDirty = false;
  $("#wf-state").className = "muted";
  $("#wf-state").textContent = t("wf_saved");
  renderWorkflow();
}

async function resetWorkflow() {
  if (!confirm(t("wf_reset_confirm"))) return;
  wf = await get(`/api/monitor/${$("#hotel").value}/workflow?action=reset`, { method: "POST" });
  wfDirty = false;
  $("#wf-state").textContent = "";
  renderWorkflow();
}


// ---------------------------------------------------------------- instellingen van het hotel (tabblad Hotel)
// Alle instellingen uit het hotelbestand, per sectie. Wat hier gewijzigd wordt, gaat voor op het bestand
// (database, per omgeving). Vrije secties (kamers en deuren, WhatsApp-sjablonen): naam = waarde.
let hs = null, hsEdit = {}, hsDirty = false;

async function loadSettings() {
  try { hs = await get(`/api/monitor/${$("#hotel").value}/settings`); } catch (e) { return; }
  hsEdit = {}; hsDirty = false;
  renderSettings();
}

function hsValue(sec, f) {
  const e = hsEdit[sec.section];
  return e && f.key in e ? e[f.key] : f.value;
}

function hsInput(sec, f, i) {
  const v = hsValue(sec, f), id = `hs-${i}`, attrs = `id="${id}" data-sec="${esc(sec.section)}" data-key="${esc(f.key)}"`;
  if (f.type === "bool") return `<input type="checkbox" ${attrs} ${v ? "checked" : ""}>`;
  if (f.type === "int" || f.type === "float") return `<input type="number" ${attrs} step="${f.type === "int" ? 1 : "any"}" value="${esc(v)}">`;
  if (f.type === "color") return `<input type="color" ${attrs} value="${esc(v)}"> <code>${esc(v)}</code>`;
  if (f.type === "list") return `<input type="text" ${attrs} value="${esc((v || []).join(", "))}" placeholder="${esc(t("hs_list"))}">`;
  return `<input type="text" ${attrs} value="${esc(v ?? "")}">`;
}

function renderSettings() {
  if (!hs || !$("#hs-sections")) return;
  $("#hs-meta").textContent = hs.meta.source === "monitor" ? t("wf_changed", hs.meta.updated_by || "?", stamp(hs.meta.updated_at)) : t("wf_from_file");
  $("#hs-save").disabled = !hsDirty;
  let i = 0;
  $("#hs-sections").innerHTML = hs.sections.map(sec => {
    const title = t("sec_" + sec.section.replace(".", "_")) || sec.section;
    let rows;
    if (sec.free) {
      const pairs = hsEdit[sec.section] ? Object.entries(hsEdit[sec.section]) : sec.fields.map(f => [f.key, f.value]);
      rows = pairs.map(([k, v]) => `<div class="hs-row free"><input type="text" class="hs-k" data-free="${esc(sec.section)}" value="${esc(k)}" placeholder="${esc(t("hs_key"))}">
          <input type="text" class="hs-v" data-free="${esc(sec.section)}" value="${esc(v)}" placeholder="${esc(t("hs_value"))}"></div>`).join("")
        + `<button type="button" class="link" data-add="${esc(sec.section)}">+ ${esc(t("hs_add"))}</button>`;
    } else {
      rows = sec.fields.map(f => {
        const id = i++;
        const changed = JSON.stringify(hsValue(sec, f)) !== JSON.stringify(f.default);
        return `<div class="hs-row ${changed ? "changed" : ""}">
          <label for="hs-${id}">${esc(f.key)}</label>
          <div>${hsInput(sec, f, id)}${f.env ? ` <span class="tag warn" title="${esc(t("hs_env"))}">Key Vault</span>` : ""}
            ${changed ? `<span class="muted small">${esc(t("hs_default"))}: ${esc(Array.isArray(f.default) ? f.default.join(", ") : String(f.default ?? ""))}</span>` : ""}
            ${f.help ? `<div class="muted small">${esc(f.help)}</div>` : ""}</div></div>`;
      }).join("");
    }
    return `<div class="hs-card"><h3>${esc(title)}</h3>${sec.help ? `<p class="muted small">${esc(sec.help)}</p>` : ""}${rows}</div>`;
  }).join("");
  document.querySelectorAll("#hs-sections [data-key]").forEach(el => el.onchange = () => {
    const sec = hs.sections.find(x => x.section === el.dataset.sec), f = sec.fields.find(x => x.key === el.dataset.key);
    let v = el.type === "checkbox" ? el.checked : el.value;
    if (f.type === "int" || f.type === "float") v = v === "" ? f.default : Number(v);
    if (f.type === "list") v = v.split(",").map(x => x.trim()).filter(Boolean);
    (hsEdit[sec.section] = hsEdit[sec.section] || {})[f.key] = v;
    hsTouched();
  });
  const readFree = section => {
    const ks = [...document.querySelectorAll(`#hs-sections .hs-k[data-free="${section}"]`)];
    const vs = [...document.querySelectorAll(`#hs-sections .hs-v[data-free="${section}"]`)];
    hsEdit[section] = Object.fromEntries(ks.map((k, j) => [k.value.trim(), vs[j].value.trim()]).filter(([k]) => k));
  };
  document.querySelectorAll("#hs-sections [data-free]").forEach(el => el.onchange = () => { readFree(el.dataset.free); hsTouched(); });
  document.querySelectorAll("#hs-sections [data-add]").forEach(b => b.onclick = () => {
    readFree(b.dataset.add);
    hsEdit[b.dataset.add][""] = "";
    renderSettings();
  });
}

function hsTouched() {
  hsDirty = true;
  $("#hs-save").disabled = false;
  $("#hs-state").className = "muted";
  $("#hs-state").textContent = t("wf_dirty");
  renderSettings();
}

async function saveSettings() {
  // Alles wat op het scherm staat (ook ongewijzigd): de server bewaart alleen wat verschilt van het bestand
  const body = {};
  hs.sections.forEach(sec => {
    if (sec.free) body[sec.section] = hsEdit[sec.section] || Object.fromEntries(sec.fields.map(f => [f.key, f.value]));
    else body[sec.section] = Object.fromEntries(sec.fields.map(f => [f.key, hsValue(sec, f)]));
  });
  const r = await fetch(API + `/api/monitor/${$("#hotel").value}/settings`, {
    method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body),
  });
  const d = await r.json().catch(() => ({}));
  if (!r.ok) { $("#hs-state").textContent = d.error || `${t("load_error")} ${r.status}`; $("#hs-state").className = "err"; return; }
  hs = d; hsEdit = {}; hsDirty = false;
  $("#hs-state").className = "muted";
  $("#hs-state").textContent = t("wf_saved");
  renderSettings();
}

async function resetSettings() {
  if (!confirm(t("hs_reset_confirm"))) return;
  hs = await get(`/api/monitor/${$("#hotel").value}/settings?action=reset`, { method: "POST" });
  hsEdit = {}; hsDirty = false;
  $("#hs-state").textContent = "";
  renderSettings();
}

// Als laatste: alle functies en variabelen hierboven bestaan dan
init().catch(e => { document.body.insertAdjacentHTML("beforeend", `<p class="err">${t("load_error")}: ${esc(e.message)}</p>`); });
