// Monitor (opvolgpagina): haalt gegevens op via /api/monitor/... (lokaal de devserver, in Azure de Function App).
const API = window.ADMIN_API || "";

const T = {
  nl: {
    title: "Check-in monitor", hotel: "Hotel", tab_res: "Reservaties", tab_robot: "Robot", tab_guests: "Gasten", tab_workflow: "Workflow",
    tab_breakfast: "Ontbijt", tab_cleaning: "Schoonmaak", dl_day: "Lijst voor", dl_make: "Lijst maken", dl_send: "Maken en versturen",
    dl_c_day: "Dag", dl_c_made: "Gemaakt", dl_c_by: "Door", dl_c_content: "Inhoud", dl_c_sent: "Verstuurd", dl_view: "Bekijken", dl_hide: "Verbergen",
    dl_auto: "automatisch", dl_busy: "Bezig...", dl_made: day => `Lijst voor ${day} gemaakt.`, dl_sent_ok: day => `Lijst voor ${day} gemaakt en verstuurd.`,
    dl_sent_fail: n => `Gemaakt, maar ${n} verzending(en) niet gelukt (zie Verstuurd).`, dl_none: "Nog geen lijsten.", dl_del_confirm: d => `De lijst van ${d} verwijderen?`,
    dl_not_sent: "niet verstuurd", dl_no_to: "geen ontvangers", dl_confirm: (day, to) => `Lijst voor ${day} opnieuw maken en versturen naar ${to}?`,
    dl_info: (on, time, days, to, keep) => `Automatisch: ${on ? `elke dag om ${time} voor ${days === 0 ? "dezelfde dag" : days === 1 ? "de dag erna" : `${days} dagen later`}` : "uit (hoofdschakelaar)"}. Naar: ${to || "niemand (instellingen)"}. De laatste ${keep} lijsten blijven bewaard.`,
    dl_waiting: (day, at) => `Gevraagd om ${at}: de robot leest de reservaties van ${day} in Lighthouse en maakt de lijst (enkele minuten). Zie ook het robotlog.`, dl_sending: (day, at) => `Lijst voor ${day} gemaakt door de robot, wordt verstuurd...`, dl_no_robot: (day, at) => `Lijst voor ${day} gevraagd om ${at}, maar er draait geen robot (niet gestart, zie robotlog). Klik opnieuw om het nog eens te proberen.`, dl_ready: day => `Lijst voor ${day} gemaakt.`,
    dl_name_breakfast: "Ontbijtlijst", dl_name_cleaning: "Schoonmaaklijst", dl_wa: "WhatsApp/sms",
    sw_blist: "Ontbijtlijst", sw_clist: "Schoonmaaklijst", sw_read: "Reservaties lezen", task_ontbijtlijst: "Ontbijtlijst", task_kuislijst: "Schoonmaaklijst",
    sec_ontbijtlijst: "Ontbijtlijst", sec_kuislijst: "Schoonmaaklijst", sec_kamers: "Kamers",
    wf_save: "Bewaren", wf_reset: "Terug naar standaard", wf_saved: "Bewaard.", wf_dirty: "Niet bewaarde wijzigingen.",
    wf_reset_confirm: "De workflow terugzetten naar de standaard uit het hotelbestand? Alle wijzigingen gaan verloren.",
    wf_from_file: "Standaard uit het hotelbestand", wf_changed: (who, when) => `Gewijzigd door ${who} op ${when}`,
    wf_leave: "Er zijn niet bewaarde wijzigingen. Toch verder?",
    flow_booking: "Booking.com", flow_expedia: "Expedia", flow_website: "Website en andere",
    wf_start: "Boeking komt binnen", wf_arrival: "Aankomst", wf_departure: "Vertrek", wf_days_after: n => `${n} dag${n === 1 ? "" : "en"} na vertrek`,
    step_thank_you: "Bedankmail na het verblijf", step_payment_request: "Betaalverzoek (nog iets open na vertrek)",
    short_thank_you: "Bedankt", short_payment_request: "Betaalverzoek", when_days_after_departure: "dagen na vertrek", c_not_paid: "niet (volledig) betaald",
    wf_not_ready_access_code: "wacht op Salto", wf_not_ready_payment_request: "wacht op Saferpay", wf_days_before: n => `${n} dag${n === 1 ? "" : "en"} voor aankomst`,
    wf_right_after: "Meteen na de boeking", step_confirmation: "Bevestiging met link naar het check-in-formulier",
    step_reminder: "Herinnering (formulier niet ingevuld)", step_access_code: "Code en praktische info",
    f_enabled: "Actief", f_when: "Wanneer", f_days: "Dagen voor aankomst", f_channels: "Kanalen", f_only_if: "Alleen als",
    f_replaced_by: "Overslaan als al aan de beurt", f_late: "Alleen als de boeking vóór die dag binnenkwam (anders kreeg de gast net de bevestiging)",
    wf_later_rule: "Deze mail gaat niet weg als op dat moment al een latere mail aan de beurt is (bv. bij een late boeking krijgt de gast meteen alleen de code-mail).", f_pay: "Betaalknop", f_content: "In de gast-app", g_when: "Wanneer versturen", wf_example: "Voorbeeldmail", pv_subject: "Onderwerp",
    m_reservation: "reservatiegegevens", m_checkin_form: "link check-in-formulier", m_code: "pincode", m_practical_info: "praktische info", m_pay: "betaalknop",
    wf_pay_note: "Knop om het openstaande bedrag online te betalen: alleen de toeristenbelasting of alles, wat in Lighthouse nog openstaat.",
    wf_form_note: "De link naar het formulier valt vanzelf weg als de gast het al invulde.",
    f_rates: "Inhoud in de gast-app", m_message: "tekst van het bericht", rate_nfr: "NFR (niet annuleerbaar)", rate_standard: "Standaard (annuleerbaar of onbekend)",
    rate_row_off: "niets aangevinkt: gaat niet weg", rate_example: "voorbeeld",
    wf_rule_code: "Pincode: alleen als de kamer betaald is in Lighthouse (toeristenbelasting mag openstaan).",
    wf_rule_pay: "Betaalknop: alleen als er nog iets openstaat en Lighthouse een betaallink gaf.",
    wf_rule_form: "Check-in-formulier: al ingevuld, dan een knop om de gegevens aan te passen.",
    when_after_booking: "na de boeking", when_days_before_arrival: "dagen voor aankomst",
    ch_email: "e-mail", ch_sms: "sms", ch_whatsapp: "WhatsApp",
    pay_none: "geen", pay_open_amount: "openstaand bedrag", pay_city_tax: "toeristenbelasting",
    c_not_cancelled: "niet geannuleerd", c_form_completed: "formulier ingevuld", c_form_not_completed: "formulier niet ingevuld",
    c_paid: "betaald", c_room_paid: "kamer betaald (toeristenbelasting mag openstaan)", c_checked_in: "ingecheckt", c_has_email: "e-mailadres gekend", c_has_phone: "telefoon gekend",
    wf_rules: "Herkennen", wf_sources: "Via (Lighthouse) bevat (komma's tussen)", wf_other: "Alle andere waarden van Via",
    wf_paid_yes: "en volledig betaald", wf_paid_no: "en nog niet (volledig) betaald",
    wf_params: "Parameters (alle flows)", wf_params_moved: "Toeristenbelasting en munt staan bij Instellingen > Hotel.",
    wf_seen: "Waarden van Via (Lighthouse) die nu bij deze flow horen:", wf_seen_none: "Nog geen reservaties in deze flow.", p_city_tax: "Toeristenbelasting", p_unit: "Per", unit_person_night: "persoon per nacht",
    unit_person_stay: "persoon per verblijf", p_currency: "Munt", wf_not_ready: "nog niet gebouwd (Salto)", wf_off: "uit",
    returning: n => `terugkerend (${n}×)`, mg_message: "Bericht", mg_time: "Tijdstip", short_confirmation: "Bevestiging", short_checkin_form: "Formulier ingevuld", ch_lighthouse: "Lighthouse", short_booking_payout: "Overschrijving Booking.com", short_pay_request: "Betaalverzoek in Lighthouse", short_pms_sync: "Code en status in Lighthouse", short_room_change: "Kamerwissel", short_stay_link: "Link verblijfspagina (op vraag van de gast)", short_incoming: "Antwoord van de gast", ch_form: "formulier", ch_app: "gast-app", short_app_unlock: "Deur geopend (gast-app)", short_app_pay: "Betaalknop (gast-app)", short_reminder: "Herinnering", short_access_code: "Code-mail", mg_channel: "Kanaal", mg_to: "Naar",
    mg_title: (num, guest) => `Berichten voor ${guest} (${num})`, mg_click: "Klik voor alle details",
    mg_plan: "Tijdlijn", mg_attempts: "Alle pogingen", mg_next: "volgt",
    pl_sent: "verstuurd op", pl_failed: "mislukt op", pl_planned: "gepland", pl_due: "wordt nu verstuurd", pl_will: "wordt verstuurd op", pl_wont: "wordt niet verstuurd", pl_was: "gepland", pl_skipped: "valt weg", pl_off: "niet actief", pl_missed: "niet verstuurd, te laat", lg_sent: "verstuurd", lg_failed: "mislukt", lg_planned: "komt nog", lg_missed: "te laat, niet verstuurd", lg_cond: "voorwaarde niet voldaan", lg_off: "niet actief", pl_cond: "niet verstuurd, voorwaarde", stairs_tag: "trappen", stairs_tip: "Formulier: een van de gasten kan moeilijk trappen lopen (lagere verdieping indien vrij).", stairs_in_lh: w => `In de interne memo in Lighthouse sinds ${w}.`, form_yes: "✓ formulier ingevuld", form_no: "formulier niet ingevuld", sb_open: "Versturen", sb_again: "Opnieuw versturen",
    rss_before_start: "voor de startdatum", rss_booked_late: "te laat geboekt", rss_stored_late: "boeking al lang achter de rug", rss_later_due: "zit in de latere mail",
    rss_window_passed: "moment voorbij", rss_messaging_off: "berichten uit", rss_not_selected: "niet voor deze reservatie", rs_not_selected: "automatische berichten staan uit voor deze reservatie (vinkje bovenaan)", mo_label: "Automatische berichten voor deze reservatie", mo_hint_aan: "De schakelaar Gastcommunicatie staat aan: alle reservaties krijgen berichten, behalve als je dit vinkje weghaalt.", mo_hint_selectie: "De schakelaar Gastcommunicatie staat op selectie: alleen reservaties met dit vinkje krijgen berichten.", mo_hint_uit: "De schakelaar Gastcommunicatie staat uit: er gaat niets naar gasten, ook niet met dit vinkje.", tag_msgs_on: "berichten aan", tag_msgs_off: "berichten uit", sw_selection: "selectie", rss_disabled: "stap uit", rss_not_ready: "nog niet gebouwd", sb_other: "Ander adres...", sb_bad_email: "Ongeldig e-mailadres", sb_bad_phone: "Ongeldig nummer (met landcode, bv. +32...)", src_test: "testadres", src_form: "check-in-formulier",
    src_form_extra: "extra, check-in-formulier", src_relay: "doorstuuradres", src_profile: "gastprofiel", src_used: "eerder gebruikt", src_earlier: "vroeger", sb_to: "naar", sb_go: "Versturen", sb_off: "(nog niet actief)", send_to: "Versturen naar...", send_to_ask: "Naar welk e-mailadres (of gsm-nummer met +32...) versturen? Het wordt bij de reservatie bewaard.", ct_add: "E-mailadres of gsm-nummer toevoegen", ct_email: "e-mailadres", ct_phone: "gsm-nummer met landcode (+32...)", env_to_prd: "Naar PRD", env_bar_tst: "TESTOMGEVING (TST): berichten gaan alleen naar het testadres, nooit naar gasten",
    env_bar_prd: "PRODUCTIE (PRD): berichten gaan naar echte gasten", env_to_tst: "Naar TST", sw_title: "Hoofdschakelaars (instellingen, tabblad Hotel)", sw_payout: "Overschrijvingen", sw_messages: "Gastcommunicatie", sw_breakfast: "Ontbijt labels", sw_unlock: "Deuren via app", sw_on: "AAN", sw_off: "UIT",
    env_confirm_prd: "Overschakelen naar PRODUCTIE? Daar gaan berichten naar echte gasten.", env_confirm_tst: "Overschakelen naar de testomgeving (TST)?", pl_not_sent: "niet verstuurd", relay_hint: "Doorstuuradres van het boekingsplatform, geen eigen adres van de gast.", relay_kept: "Doorstuuradres van het boekingsplatform. Bewaard, maar het eigen adres uit het check-in-formulier gaat voor.", mg_test_addr: "testadres", mg_for: "bedoeld voor", tab_hotel: "Hotel",
    hs_func: "Dagelijks", hs_tech: "Technisch",
    sec_secrets: "Geheimen (Key Vault)", ks_help: "Sleutels en wachtwoorden van deze omgeving. Alleen zichtbaar met een rol op de Key Vault; wijzigen met Key Vault Secrets Officer. Een nieuwe waarde werkt binnen enkele minuten.",
    ks_show: "Tonen", ks_hide: "Verbergen", ks_save: "Bewaren", ks_saved: "Bewaard", ks_failed: "Niet bewaard", ks_readonly: "Alleen bekijken (geen rol om te wijzigen)", ks_new: "nieuwe waarde", ks_hotel: "dit hotel", ks_shared: "alle hotels", ks_portal: "Openen in de Azure Portal",
    hs_intro: "Gegevens en instellingen van het hotel. Standaard uit het hotelbestand; wat u hier wijzigt, gaat voor (alleen in deze omgeving).",
    hs_default: "standaard", hs_env: "In deze omgeving vastgelegd in Key Vault of de Function App: die waarde gaat voor.",
    hs_add: "Toevoegen", hs_key: "naam", hs_value: "waarde", hs_reset_confirm: "Alle instellingen terug naar het hotelbestand? Alle wijzigingen gaan verloren.",
    hs_list: "komma's ertussen",
    sec_schakelaars: "Hoofdschakelaars", sec_hotel: "Hotel", sec_test: "Testomgeving", sec_workflow_parameters: "Toeristenbelasting en munt", sec_reviews: "Reviews", sec_verzending: "Afzender van de mails", sec_receptie: "Receptie", sec_checkout: "Check-out", sec_ontbijt: "Ontbijt", sec_betaalverzoek: "Betaalverzoeken",
    sec_wifi: "Wifi", sec_parking: "Parking", sec_nood: "Noodnummer", sec_doorschakelen: "Oproepen doorschakelen", sec_twilio: "Twilio (sms en WhatsApp)", sec_robot: "Robot",
    sec_messaging: "Berichten", sec_whatsapp: "WhatsApp-sjablonen", sec_retention: "Bewaartermijnen", sec_salto: "Salto",
    sec_salto_rooms: "Salto: kamers en deuren", sec_lighthouse: "Lighthouse", sec_checkin: "Check-in-formulier", sec_kuislijst_label_tekst: "Schoonmaaklijst: tekst van de labels", sec_kuislijst_wensen: "Schoonmaaklijst: wensen in de teksten", unit_eerste_cijfer: "eerste cijfer van het kamernummer", unit_geen: "geen verdieping tonen", sec_bewaking: "Bewaking", sec_beheer: "Beheer",
    sec_privacy: "Privacyverklaring", sec_kleuren: "Kleuren", settings: "Instellingen", back: "Monitor", open_lh: "Openen in Lighthouse", pl_not_tried: "niet geprobeerd", backup: "extra adres uit het check-in-formulier",
    rs_now: "Nu versturen", rs_again: "Opnieuw versturen", rs_confirm: (step, ch, to) => `${step} nu versturen per ${ch} naar ${to}?`,
    rs_confirm_test: (step, ch, test, to) => `${step} nu versturen per ${ch} naar het testadres ${test}? (bedoeld voor ${to}; in de testomgeving gaat niets naar de gast)`,
    rs_no_test: "Er is geen testadres ingesteld voor deze omgeving, dus er wordt niets verstuurd. Vul het in op Instellingen > Hotel > Testomgeving.",
    chr_muted: "uitgezet voor deze gast", chr_phone_off: "nog niet actief (Twilio)", chr_fallback: "alleen als WhatsApp niet lukt", chr_step_off: "niet aangevinkt bij deze stap (workflow)", wfch_email: "Mail", wfch_whatsapp: "WhatsApp (sms als terugval, alleen met gsm-nummer)",
    rs_disabled: "stap staat uit", rs_rate_off_nfr: "uit voor NFR (niets aangevinkt bij dit tarief)", rs_rate_off_standard: "uit voor Standaard (niets aangevinkt bij dit tarief)", rs_messaging_off: "berichten staan uit in deze omgeving", rs_before_start: "niet automatisch: reservatie kwam binnen vóór de startdatum van de berichten (Instellingen > Hotel > Berichten > Vanaf)",
    rs_booked_late: "boeking kwam te laat", rs_stored_late: "oudere boeking, later binnengehaald: het moment van de boeking is voorbij (de herinnering en de code-mail komen wel)", rs_later_due: "een latere mail is al aan de beurt, de inhoud zit daarin", rs_not_ready: "nog niet gebouwd",
    rs_no_contact: "Geen e-mailadres of gsm-nummer in Lighthouse. Versturen kan wel: klik bij een bericht op Versturen en kies of typ een adres.", rs_window_passed: "moment voorbij", rs_condition: "voorwaarde niet voldaan",
    g_msgs: "Berichten", g_mute_hint: "Vinkje weg: dit kanaal nooit gebruiken voor deze gast",
    st_sent: "verstuurd", st_failed: "mislukt", st_delivered: "afgeleverd", st_read: "gelezen", st_undelivered: "niet afgeleverd", show_guest: "Gastgegevens tonen", show_res: "Reservaties van deze gast tonen",
    g_update: "Synchroniseren", g_busy: "Bezig...", g_done: d => `${d.linked} gekoppeld, ${d.counted} verblijven en ${d.cancellations} annuleringen meegeteld, ${d.reservations_deleted} oude reservaties en ${d.guests_deleted} gasten verwijderd`,
    g_search: "Zoek op naam, e-mail, telefoon", g_count: n => `${n} gasten`, g_country: "Land", g_res: "Reservaties", g_stays: "Verblijven", g_cancelled: "Geannuleerd",
    g_avg_nights: "Gem. nachten", g_avg_persons: "Gem. pers.", g_first: "Eerste verblijf", g_last: "Laatste verblijf",
    g_channel: "Kanaal", g_rooms: "Kamers", g_relay: "doorstuuradres, niet voor marketing", g_form: "formulier",
    g_optout: "geen marketing", no_guests: "Nog geen gasten (klik op Synchroniseren)",
    m_title: n => `Mogelijke dubbels (${n})`, m_help: "Zelfde of bijna dezelfde naam in hetzelfde land. Nooit automatisch samengevoegd.",
    m_same_name: "zelfde naam", m_same_contact: "zelfde e-mailadres of gsm-nummer, andere naam (partner of familie?)", m_extra_contact: "extra adres of nummer van de ene is dat van de andere (zelfde persoon of partner?)", m_similar_name: "bijna zelfde naam", m_merge: "Samenvoegen", m_shared_hint: (v, n, ch) => `${v} staat bij ${n} gasten met een andere naam${ch ? " (" + ch + ")" : ""}: misschien van de boekingssite of een bureau.`, m_shared_btn: "Nummer van boekingssite of bureau", m_shared_q: v => `${v} is van een boekingssite of bureau, niet van een gast? Het is dan nooit meer een reden om gasten samen te voegen.`, m_open_profile: "profiel openen", m_f_email: "E-mail", m_f_relay: "Doorstuuradres", m_f_phone: "Gsm", m_f_country: "Land, taal", m_f_channel: "Kanaal", m_f_stays: "Reservaties", m_f_res: "reservaties", m_f_st: "verblijven", m_f_rooms: "Kamers", m_different: "Andere persoon",
    m_confirm: "Deze twee gasten samenvoegen tot één?", reset: "Filter wissen",
    search: "Zoek op naam, nummer, e-mail", stay_from: "Verblijf van", stay_to: "tot", from_today: "Vanaf vandaag",
    c_arrival: "Aankomst", c_departure: "Vertrek", c_number: "Nummer", c_guest: "Gast", c_pers: "Pers.",
    c_room: "Kamer", c_rate: "Tarief", rate_nrf: "niet annuleerbaar", rate_flex: "annuleerbaar", c_via: "Via", c_flow: "Workflow", c_booked: "Geboekt", c_added: "Toegevoegd", c_updated: "Bijgewerkt", c_form: "Formulier", c_contact: "Contact", c_messages: "Berichten",
    yes: "ja", no: "nee", none: "geen", count: n => `${n} reservaties`, no_res: "Geen reservaties",
    hours_a: "Nieuwe reservaties van de laatste", hours_b: "uur", run: "Robot nu draaien",
    r_start: "Start", r_duration: "Duur", r_task: "Taak", r_result: "Resultaat", r_found: "Te doen", r_new: "Gedaan", r_error: "Opmerking",
    all_tasks: "Alle", sub_log: "Logboek robot", del: "Verwijderen", del_confirm: "Deze regel uit het logboek verwijderen?", del_all: "Alles verwijderen",
    del_all_confirm: (n, task) => `${n} regels${task ? ` van "${task}"` : ""} uit het logboek verwijderen?`, t_azure: "Azure start", t_container: "container", t_ready: s => `klaar om te lezen na ${s} s`, t_login: "aanmelden", t_browser: "browser starten", t_reused: "sessie hergebruikt", t_new: "opnieuw aangemeld", t_list: "lijst", t_contact: (n, sec) => `${n} contact${n > 1 ? "en" : ""} à ${sec} s`, task_nieuwe_reservaties: "Nieuwe reservaties", task_contactgegevens_nalezen: "Reservaties bijwerken", task_overschrijving_booking: "Overschrijvingen", task_lighthouse_bijwerken: "Pincode en status in Lighthouse", task_meldingen: "Mailbox nakijken", task_onderhoud: "Gasten synchroniseren", task_berichten: "Berichten versturen", task_bewaking: "Bewaking", task_robot: "Run", task_ontbijt_labels: "Ontbijt labels", task_oude_boekingen: "Oudere boekingen", task_betaalverzoeken: "Betaalverzoeken", sw_not_built: "nog niet gebouwd",
    ok: "ok", fail: "fout", partial: "deels", busy: "De robot is bezig...", live_now: "nu bezig", not_robot: "geen robotrun", not_robot_tip: "Losse taak in Azure, buiten de robot: mailbox elke minuut, berichten elke 2 minuten, bewaking elke 15 minuten", run_open: "klik om de taken te tonen", run_close: "klik om te verbergen", run_label: "Robotrun", run_tasks: n => `${n} ${n === 1 ? "taak" : "taken"}`, run_failed: n => `fout in ${n} ${n === 1 ? "taak" : "taken"}`, live_done: "afsluiten", live_since: s => `sinds ${s} s`, live_quiet: s => `geen teken van leven sinds ${s} s`, live_run: "run gestart om", scheduled: "Start ook vanzelf: bij een meldingsmail, een gevraagde lijst en als vangnet (instelling Robot: om de hoeveel minuten).",
    not_installed: "De robot is in deze omgeving nog niet geïnstalleerd.", no_runs: "Nog geen afgeronde run",
    load_error: "Fout bij laden",
    exec_title: "Runs volgens Azure", exec_end: "Einde", exec_status: "Status", exec_name: "Naam",
  },
  en: {
    title: "Check-in monitor", hotel: "Hotel", tab_res: "Reservations", tab_robot: "Robot", tab_guests: "Guests", tab_workflow: "Workflow",
    tab_breakfast: "Breakfast", tab_cleaning: "Cleaning", dl_day: "List for", dl_make: "Make list", dl_send: "Make and send",
    dl_c_day: "Day", dl_c_made: "Made", dl_c_by: "By", dl_c_content: "Content", dl_c_sent: "Sent", dl_view: "View", dl_hide: "Hide",
    dl_auto: "automatic", dl_busy: "Working...", dl_made: day => `List for ${day} made.`, dl_sent_ok: day => `List for ${day} made and sent.`,
    dl_sent_fail: n => `Made, but ${n} sending(s) failed (see Sent).`, dl_none: "No lists yet.", dl_del_confirm: d => `Delete the list of ${d}?`,
    dl_not_sent: "not sent", dl_no_to: "no recipients", dl_confirm: (day, to) => `Make the list for ${day} again and send it to ${to}?`,
    dl_info: (on, time, days, to, keep) => `Automatic: ${on ? `every day at ${time} for ${days === 0 ? "the same day" : days === 1 ? "the next day" : `${days} days later`}` : "off (main switch)"}. To: ${to || "nobody (settings)"}. The last ${keep} lists are kept.`,
    dl_waiting: (day, at) => `Requested at ${at}: the robot reads the reservations of ${day} in Lighthouse and makes the list (a few minutes). See also the robot log.`, dl_sending: (day, at) => `List for ${day} made by the robot, being sent...`, dl_no_robot: (day, at) => `List for ${day} requested at ${at}, but no robot is running (not started, see robot log). Click again to retry.`, dl_ready: day => `List for ${day} made.`,
    dl_name_breakfast: "Breakfast list", dl_name_cleaning: "Cleaning list", dl_wa: "WhatsApp/SMS",
    sw_blist: "Breakfast list", sw_clist: "Cleaning list", sw_read: "Read reservations", task_ontbijtlijst: "Breakfast list", task_kuislijst: "Cleaning list",
    sec_ontbijtlijst: "Breakfast list", sec_kuislijst: "Cleaning list", sec_kamers: "Rooms",
    wf_save: "Save", wf_reset: "Back to default", wf_saved: "Saved.", wf_dirty: "Unsaved changes.",
    wf_reset_confirm: "Reset the workflow to the default from the hotel file? All changes will be lost.",
    wf_from_file: "Default from the hotel file", wf_changed: (who, when) => `Changed by ${who} on ${when}`,
    wf_leave: "There are unsaved changes. Continue anyway?",
    flow_booking: "Booking.com", flow_expedia: "Expedia", flow_website: "Website and other",
    wf_start: "Booking comes in", wf_arrival: "Arrival", wf_departure: "Departure", wf_days_after: n => `${n} day${n === 1 ? "" : "s"} after departure`,
    step_thank_you: "Thank-you mail after the stay", step_payment_request: "Payment request (amount still open after departure)",
    short_thank_you: "Thank you", short_payment_request: "Payment request", when_days_after_departure: "days after departure", c_not_paid: "not (fully) paid",
    wf_not_ready_access_code: "waiting for Salto", wf_not_ready_payment_request: "waiting for Saferpay", wf_days_before: n => `${n} day${n === 1 ? "" : "s"} before arrival`,
    wf_right_after: "Right after booking", step_confirmation: "Confirmation with link to the check-in form",
    step_reminder: "Reminder (form not filled in)", step_access_code: "Code and practical info",
    f_enabled: "Active", f_when: "When", f_days: "Days before arrival", f_channels: "Channels", f_only_if: "Only if",
    f_replaced_by: "Skip if already due", f_late: "Only if the booking came in before that day (otherwise the guest just got the confirmation)",
    wf_later_rule: "This mail is not sent if a later mail is already due at that moment (e.g. with a late booking the guest only gets the code mail).", f_pay: "Pay button", f_content: "In the guest app", g_when: "When to send", wf_example: "Example mail", pv_subject: "Subject",
    m_reservation: "reservation details", m_checkin_form: "check-in form link", m_code: "PIN code", m_practical_info: "practical info", m_pay: "pay button",
    wf_pay_note: "Button to pay the open amount online: just the city tax or everything, whatever is still open in Lighthouse.",
    wf_form_note: "The form link is left out automatically when the guest already filled it in.",
    f_rates: "Guest app content", m_message: "message text", rate_nfr: "NFR (non-refundable)", rate_standard: "Standard (refundable or unknown)",
    rate_row_off: "nothing ticked: not sent", rate_example: "example",
    wf_rule_code: "PIN code: only when the room is paid in Lighthouse (city tax may be open).",
    wf_rule_pay: "Pay button: only when something is still open and Lighthouse gave a payment link.",
    wf_rule_form: "Check-in form: already filled in, then a button to edit the details.",
    when_after_booking: "after booking", when_days_before_arrival: "days before arrival",
    ch_email: "e-mail", ch_sms: "SMS", ch_whatsapp: "WhatsApp",
    pay_none: "none", pay_open_amount: "open amount", pay_city_tax: "city tax",
    c_not_cancelled: "not cancelled", c_form_completed: "form filled in", c_form_not_completed: "form not filled in",
    c_paid: "paid", c_room_paid: "room paid (city tax may be open)", c_checked_in: "checked in", c_has_email: "e-mail known", c_has_phone: "phone known",
    wf_rules: "Recognised by", wf_sources: "Via (Lighthouse) contains (comma separated)", wf_other: "All other values of Via",
    wf_paid_yes: "and fully paid", wf_paid_no: "and not (fully) paid",
    wf_params: "Parameters (all flows)", wf_params_moved: "City tax and currency are under Settings > Hotel.",
    wf_seen: "Values of Via (Lighthouse) that now fall in this flow:", wf_seen_none: "No reservations in this flow yet.", p_city_tax: "City tax", p_unit: "Per", unit_person_night: "person per night",
    unit_person_stay: "person per stay", p_currency: "Currency", wf_not_ready: "not built yet (Salto)", wf_off: "off",
    returning: n => `returning (${n}×)`, mg_message: "Message", mg_time: "Time", short_confirmation: "Confirmation", short_checkin_form: "Form filled in", ch_lighthouse: "Lighthouse", short_booking_payout: "Booking.com bank transfer", short_pay_request: "Payment request in Lighthouse", short_pms_sync: "Code and status in Lighthouse", short_room_change: "Room change", short_stay_link: "Stay page link (asked by the guest)", short_incoming: "Reply from the guest", ch_form: "form", ch_app: "guest app", short_app_unlock: "Door opened (guest app)", short_app_pay: "Pay button (guest app)", short_reminder: "Reminder", short_access_code: "Code mail", mg_channel: "Channel", mg_to: "To",
    mg_title: (num, guest) => `Messages for ${guest} (${num})`, mg_click: "Click for all details",
    mg_plan: "Timeline", mg_attempts: "All attempts", mg_next: "next",
    pl_sent: "sent on", pl_failed: "failed on", pl_planned: "planned", pl_due: "being sent now", pl_will: "will be sent on", pl_wont: "will not be sent", pl_was: "planned", pl_skipped: "skipped", pl_off: "not active", pl_missed: "not sent, too late", lg_sent: "sent", lg_failed: "failed", lg_planned: "still to come", lg_missed: "too late, not sent", lg_cond: "condition not met", lg_off: "not active", pl_cond: "not sent, condition", stairs_tag: "stairs", stairs_tip: "Form: one of the guests has difficulty climbing stairs (lower floor if available).", stairs_in_lh: w => `In the internal memo in Lighthouse since ${w}.`, form_yes: "✓ form filled in", form_no: "form not filled in", sb_open: "Send", sb_again: "Send again",
    rss_before_start: "before start date", rss_booked_late: "booked too late", rss_stored_late: "booking long past", rss_later_due: "included in the later mail",
    rss_window_passed: "moment passed", rss_messaging_off: "messages off", rss_not_selected: "not for this reservation", rs_not_selected: "automatic messages are off for this reservation (tick box at the top)", mo_label: "Automatic messages for this reservation", mo_hint_aan: "Guest communication is on: all reservations get messages, unless you untick this box.", mo_hint_selectie: "Guest communication is on selection: only reservations with this box ticked get messages.", mo_hint_uit: "Guest communication is off: nothing goes to guests, not even with this box ticked.", tag_msgs_on: "messages on", tag_msgs_off: "messages off", sw_selection: "selection", rss_disabled: "step off", rss_not_ready: "not built yet", sb_other: "Other address...", sb_bad_email: "Invalid e-mail address", sb_bad_phone: "Invalid number (with country code, e.g. +32...)", src_test: "test address", src_form: "check-in form",
    src_form_extra: "extra, check-in form", src_relay: "relay address", src_profile: "guest profile", src_used: "used before", src_earlier: "earlier", sb_to: "to", sb_go: "Send", sb_off: "(not active yet)", send_to: "Send to...", send_to_ask: "Send to which e-mail address (or mobile number with +32...)? It is saved with the reservation.", ct_add: "Add e-mail address or mobile number", ct_email: "e-mail address", ct_phone: "mobile number with country code (+32...)", env_to_prd: "To PRD", env_bar_tst: "TEST ENVIRONMENT (TST): messages only go to the test address, never to guests",
    env_bar_prd: "PRODUCTION (PRD): messages go to real guests", env_to_tst: "To TST", sw_title: "Main switches (settings, Hotel tab)", sw_payout: "Bank transfers", sw_messages: "Guest communication", sw_breakfast: "Breakfast labels", sw_unlock: "Doors via app", sw_on: "ON", sw_off: "OFF",
    env_confirm_prd: "Switch to PRODUCTION? Messages there go to real guests.", env_confirm_tst: "Switch to the test environment (TST)?", pl_not_sent: "not sent", relay_hint: "Relay address of the booking platform, not the guest's own address.", relay_kept: "Relay address of the booking platform. Kept, but the guest's own address from the check-in form takes precedence.", mg_test_addr: "test address", mg_for: "meant for", tab_hotel: "Hotel",
    hs_func: "Everyday", hs_tech: "Technical",
    sec_secrets: "Secrets (Key Vault)", ks_help: "Keys and passwords of this environment. Only visible with a role on the Key Vault; changing needs Key Vault Secrets Officer. A new value takes effect within a few minutes.",
    ks_show: "Show", ks_hide: "Hide", ks_save: "Save", ks_saved: "Saved", ks_failed: "Not saved", ks_readonly: "View only (no role to change)", ks_new: "new value", ks_hotel: "this hotel", ks_shared: "all hotels", ks_portal: "Open in the Azure Portal",
    hs_intro: "Hotel details and settings. Default from the hotel file; what you change here takes precedence (in this environment only).",
    hs_default: "default", hs_env: "Set for this environment in Key Vault or the Function App: that value takes precedence.",
    hs_add: "Add", hs_key: "name", hs_value: "value", hs_reset_confirm: "Reset all settings to the hotel file? All changes will be lost.",
    hs_list: "comma separated",
    sec_schakelaars: "Main switches", sec_hotel: "Hotel", sec_test: "Test environment", sec_workflow_parameters: "City tax and currency", sec_reviews: "Reviews", sec_verzending: "Mail sender", sec_receptie: "Reception", sec_checkout: "Check-out", sec_ontbijt: "Breakfast", sec_betaalverzoek: "Payment requests",
    sec_wifi: "Wi-Fi", sec_parking: "Parking", sec_nood: "Emergency number", sec_doorschakelen: "Call forwarding", sec_twilio: "Twilio (SMS and WhatsApp)", sec_robot: "Robot",
    sec_messaging: "Messages", sec_whatsapp: "WhatsApp templates", sec_retention: "Retention", sec_salto: "Salto",
    sec_salto_rooms: "Salto: rooms and doors", sec_lighthouse: "Lighthouse", sec_checkin: "Check-in form", sec_kuislijst_label_tekst: "Cleaning list: label text", sec_kuislijst_wensen: "Cleaning list: wishes in the texts", unit_eerste_cijfer: "first digit of the room number", unit_geen: "do not show a floor", sec_bewaking: "Monitoring", sec_beheer: "Administration",
    sec_privacy: "Privacy statement", sec_kleuren: "Colours", settings: "Settings", back: "Monitor", open_lh: "Open in Lighthouse", pl_not_tried: "not tried", backup: "extra address from the check-in form",
    rs_now: "Send now", rs_again: "Send again", rs_confirm: (step, ch, to) => `Send ${step} now by ${ch} to ${to}?`,
    rs_confirm_test: (step, ch, test, to) => `Send ${step} now by ${ch} to the test address ${test}? (meant for ${to}; in the test environment nothing goes to the guest)`,
    rs_no_test: "No test address is set for this environment, so nothing will be sent. Fill it in under Settings > Hotel > Test environment.",
    chr_muted: "switched off for this guest", chr_phone_off: "not active yet (Twilio)", chr_fallback: "only if WhatsApp fails", chr_step_off: "not ticked for this step (workflow)", wfch_email: "Email", wfch_whatsapp: "WhatsApp (SMS as fallback, only with a mobile number)",
    rs_disabled: "step is off", rs_rate_off_nfr: "off for NFR (nothing ticked for this rate)", rs_rate_off_standard: "off for Standard (nothing ticked for this rate)", rs_messaging_off: "messages are off in this environment", rs_before_start: "not automatic: reservation came in before the messages start date (Settings > Hotel > Messages > From)",
    rs_booked_late: "booked too late", rs_stored_late: "older booking, imported later: the booking moment has passed (reminder and code mail still follow)", rs_later_due: "a later mail is already due, the content is included there", rs_not_ready: "not built yet",
    rs_no_contact: "No e-mail address or mobile number in Lighthouse. You can still send: click Send at a message and pick or type an address.", rs_window_passed: "moment passed", rs_condition: "condition not met",
    g_msgs: "Messages", g_mute_hint: "Unchecked: never use this channel for this guest",
    st_sent: "sent", st_failed: "failed", st_delivered: "delivered", st_read: "read", st_undelivered: "not delivered", show_guest: "Show guest data", show_res: "Show this guest's reservations",
    g_update: "Synchronize", g_busy: "Working...", g_done: d => `${d.linked} linked, ${d.counted} stays and ${d.cancellations} cancellations counted, ${d.reservations_deleted} old reservations and ${d.guests_deleted} guests deleted`,
    g_search: "Search name, e-mail, phone", g_count: n => `${n} guests`, g_country: "Country", g_res: "Reservations", g_stays: "Stays", g_cancelled: "Cancelled",
    g_avg_nights: "Avg nights", g_avg_persons: "Avg pers.", g_first: "First stay", g_last: "Last stay",
    g_channel: "Channel", g_rooms: "Rooms", g_relay: "relay address, not for marketing", g_form: "form",
    g_optout: "no marketing", no_guests: "No guests yet (click Synchronize)",
    m_title: n => `Possible duplicates (${n})`, m_help: "Same or almost the same name in the same country. Never merged automatically.",
    m_same_name: "same name", m_same_contact: "same e-mail or mobile number, different name (partner or family?)", m_extra_contact: "extra address or number of one is that of the other (same person or partner?)", m_similar_name: "similar name", m_merge: "Merge", m_shared_hint: (v, n, ch) => `${v} appears with ${n} guests with a different name${ch ? " (" + ch + ")" : ""}: maybe from the booking site or an agency.`, m_shared_btn: "Number of booking site or agency", m_shared_q: v => `${v} belongs to a booking site or agency, not to a guest? It will then never again be a reason to merge guests.`, m_open_profile: "open profile", m_f_email: "E-mail", m_f_relay: "Relay address", m_f_phone: "Mobile", m_f_country: "Country, language", m_f_channel: "Channel", m_f_stays: "Reservations", m_f_res: "reservations", m_f_st: "stays", m_f_rooms: "Rooms", m_different: "Different person",
    m_confirm: "Merge these two guests into one?", reset: "Clear filter",
    search: "Search name, number, e-mail", stay_from: "Stay from", stay_to: "to", from_today: "From today",
    c_arrival: "Arrival", c_departure: "Departure", c_number: "Number", c_guest: "Guest", c_pers: "Pers.",
    c_room: "Room", c_rate: "Rate", rate_nrf: "non-refundable", rate_flex: "refundable", c_via: "Via", c_flow: "Workflow", c_booked: "Booked", c_added: "Added", c_updated: "Updated", c_form: "Form", c_contact: "Contact", c_messages: "Messages",
    yes: "yes", no: "no", none: "none", count: n => `${n} reservations`, no_res: "No reservations",
    hours_a: "New reservations of the last", hours_b: "hours", run: "Run robot now",
    r_start: "Start", r_duration: "Duration", r_task: "Task", r_result: "Result", r_found: "To do", r_new: "Done", r_error: "Note",
    all_tasks: "All", sub_log: "Robot log", del: "Delete", del_confirm: "Delete this line from the log?", del_all: "Delete all",
    del_all_confirm: (n, task) => `Delete ${n} lines${task ? ` of "${task}"` : ""} from the log?`, t_azure: "Azure start", t_container: "container", t_ready: s => `ready to read after ${s} s`, t_login: "login", t_browser: "start browser", t_reused: "session reused", t_new: "logged in again", t_list: "list", t_contact: (n, sec) => `${n} contact${n > 1 ? "s" : ""} × ${sec} s`, task_nieuwe_reservaties: "New reservations", task_contactgegevens_nalezen: "Update reservations", task_overschrijving_booking: "Bank transfers", task_lighthouse_bijwerken: "PIN and status in Lighthouse", task_meldingen: "Mailbox check", task_onderhoud: "Synchronize guests", task_berichten: "Send messages", task_bewaking: "Monitoring", task_robot: "Run", task_ontbijt_labels: "Breakfast labels", task_oude_boekingen: "Older bookings", task_betaalverzoeken: "Payment requests", sw_not_built: "not built yet",
    ok: "ok", fail: "failed", partial: "partly", busy: "The robot is running...", live_now: "running now", not_robot: "not a robot run", not_robot_tip: "Separate task in Azure, outside the robot: mailbox every minute, messages every 2 minutes, monitoring every 15 minutes", run_open: "click to show the tasks", run_close: "click to hide", run_label: "Robot run", run_tasks: n => `${n} ${n === 1 ? "task" : "tasks"}`, run_failed: n => `error in ${n} ${n === 1 ? "task" : "tasks"}`, live_done: "closing", live_since: s => `for ${s} s`, live_quiet: s => `no sign of life for ${s} s`, live_run: "run started at", scheduled: "Also starts by itself: on a notification mail, a requested list and as a safety net (setting Robot: every how many minutes).",
    not_installed: "The robot is not installed in this environment yet.", no_runs: "No finished run yet",
    load_error: "Loading failed",
    exec_title: "Runs according to Azure", exec_end: "End", exec_status: "Status", exec_name: "Name",
  },
};
// Teksten van het ontwerp (Claude Design, canvas Beheerapp Hotel Lucca)
Object.assign(T.nl, {
  m_arrives: d => `aankomst ${d}`, list_more: (n, tot) => `${n} van ${tot} getoond, scroll voor meer`, dlg_send: "Versturen",
  ls_send: "Versturen", ls_more: "Kies hoe je verstuurt", ls_ch_all: "Mail en WhatsApp", ls_ch_wa: "Alleen WhatsApp", ls_ch_mail: "Alleen mail", ls_ch_sms: "Alleen sms", ls_by_sms: "Per sms", ls_title: "Lijst manueel versturen", ls_q: l => `Ben je zeker dat je de ${l} manueel wil versturen?`, ls_to: "Wordt verstuurd naar",
  ls_by_mail: "Mail", ls_by_wa: "WhatsApp (sms als WhatsApp niet lukt)", ls_wa_off: "WhatsApp en sms staan uit, wordt niet verstuurd", ls_no_to: "Er zijn geen ontvangers ingesteld voor deze lijst (instellingen, Hotel).",
  ls_past: d => `Let op: dit is geen lijst voor vandaag! Het is de lijst van ${d}.`, ls_already: (w, to) => `Deze lijst is al verstuurd op ${w} naar ${to}.`,
  ls_note: "Bericht (niet verplicht)", ls_note_ph: "Komt bovenaan de mail en in de WhatsApp of sms", ls_done: x => `Verstuurd: ${x}.`, ls_fail: x => `Niet (helemaal) gelukt: ${x}`,
  rx_title: "Uitzonderingen per kamer", rx_help: "Kamers die afwijken van de rest: eigen naam, eigen ingang, geen verdieping, twin. Alle andere kamers volgen de regels hierboven.",
  rx_add: "Uitzondering toevoegen", rx_edit: "Aanpassen", rx_close: "Klaar", rx_del: "Verwijderen", rx_room: "Kamernummer", rx_none: "Nog geen uitzonderingen.",
  rx_new: "nieuwe uitzondering", rx_del_confirm: r => `De uitzondering voor kamer ${r} verwijderen? Ze verdwijnt pas als je bewaart.`,
  rx_no_room: "Vul bij elke uitzondering een kamernummer in.", rx_dup: r => `Kamer ${r} staat er twee keer.`, rx_empty: "geen waarden",
  rx_f_verdieping: ["Verdieping", "Leeg = geen verdieping tonen in de mail en de sms (bv. een eigen ingang). Of een getal, bv. 0 voor de benedenverdieping."],
  rx_f_lijst: ["Naam op de lijsten", "Eigen naam in plaats van het nummer op de ontbijt- en schoonmaaklijst (bv. App). Leeg = het nummer."],
  rx_f_twin: ["Twin kamer", "Standaard opgemaakt met 2 aparte bedden. Het label DOUBLE OPMAKEN komt dan bij de opmerkingen op de schoonmaaklijst."],
  rx_f_naam: ["Naam", "In de code-mail, na het kamernummer (bv. Kamer 2, historische suite)."],
  rx_f_kort: ["Kort", "In de sms, na het kamernummer."],
  rx_f_toegang: ["Toegang", "Uitleg onder de code in de mail, bv. hoe de gast bij de eigen ingang komt."],
  rx_lang: { nl: "Nederlands", fr: "Frans", en: "Engels", de: "Duits" }, dlg_delete: "Verwijderen", dlg_reset: "Terugzetten", dlg_leave: "Niet bewaren en verder",
  nav_lists: "Lijsten", nav_messages: "Berichten", logout: "Afmelden", search_lbl: "Zoeken",
  tst_bar: "Testomgeving: berichten gaan alleen naar de testadressen", env_name_prd: "Productie", env_name_tst: "Testomgeving",
  c_stay: "Verblijf", c_res: "Reservatie", c_room_rate: "Kamer en tarief", c_channel: "Kanaal",
  r_until: (d, n) => `tot ${d}, ${n} n.`, r_booked: d => `geboekt ${d}`, r_updated: d => `bijgewerkt ${d}`,
  r_returning: n => `terugkerend (${n}x)`, r_form: "Formulier", r_noform: "Geen formulier", r_stairs: "Trappen",
  r_msgs_on: "Berichten aan", r_msgs_off: "Berichten uit", r_cancelled: "Geannuleerd", r_rooms: n => `${n} kamers`,
  r_roomtype: "kamertype", r_room: n => `Kamer ${n}`, r_p: n => `${n} p.`, r_flow: f => `flow ${f}`, r_rate_nrf: "NFR", r_rate_flex: "Annuleerbaar",
  r_next: x => `Volgende: ${x}`, r_next_m: x => `volgende: ${x}`, r_none: "geen", r_none_off: "geen (uit)", r_failed: x => `${x} mislukt`,
  r_emails: "E-mailadressen", r_phones: "Gsm-nummers", r_details: n => `Details ${n}`,
  res_count: n => `<b style="color:#2B2F38">${n} reservaties</b>`, res_sel: 'Gastcommunicatie staat op <b>selectie</b>: alleen reservaties met het label "Berichten aan" krijgen berichten.',
  sw_robot: "Robot", sw_go: "Naar de instellingen", sw_st_on: "aan", sw_st_off: "uit", sw_st_sel: "selectie",
  g_sub: "Gastprofielen los van de reservaties, ook na het verblijf bewaard.", g_name: "Naam", g_profiles: n => `${n} gastprofielen`,
  m_card: "Te beslissen: mogelijk dezelfde gast", m_open: n => `${n} open`, m_and: "en", m_keep: "Samenvoegen", m_apart: "Apart houden",
  gp_since: d => `gastprofiel sinds ${d}`, gp_nomkt: "Geen marketing", gp_back: "Terugkerend", gp_resn: "reservaties", gp_stays: "verblijven", gp_canc: "geannuleerd", pick_filter: "Filter",
  gp_nights: "nachten gem.", gp_pers: "personen gem.", gp_first: "Eerste verblijf", gp_last: "Laatste verblijf", gp_chan: "Voorkeurskanaal", gp_rooms: "Kamers",
  gp_contact: "Contact", gp_help: "Verblijf: berichten over het verblijf (bevestiging, code, ...) naar dit adres. De robot volgt deze vinkjes; je kan ze omwisselen. Marketing: nieuwsbrieven en aanbiedingen naar dit adres.", gp_use: "gebruiken", gp_relay: "doorstuuradres van de boekingssite (nooit marketing)", gp_old: "niet gebruikt: vroeger adres", gp_fake: "nepnummer van de boekingssite: nooit gebruikt",
  gp_stayinfo: "Verblijf", gp_mkt: "Marketing", gp_not_used: "niet gebruikt: er is een eigen e-mailadres", gp_no_consent: "geen toestemming in het check-in-formulier", gp_mkt_noform: "marketing volgt de keuze in het check-in-formulier (nog niet ingevuld met dit adres)", gp_mkt_guest: "de gast vroeg zelf geen marketing", gp_mkt_relay: "doorstuuradres: nooit marketing",
  gp_detach: "Ontkoppelen", gp_detach_q: n => `Reservatie #${n} hoort niet bij deze gast? Ze krijgt een eigen gastprofiel, of komt bij de gast waar ze zeker bij hoort. Ze komt nooit meer terug bij deze gast.`, gp_detached: "Ontkoppeld.",
  gp_form: "formulier", gp_booking: "reservatie", gp_res: "Reservaties", gp_all: n => `Alle ${n} reservaties`, gp_now: "Nu", gp_left: "Vertrokken", gp_coming: "Komt",
  d_back: "Reservaties", d_nights: n => `${n} nachten`, d_persons: n => `${n} personen`, d_rooms: x => `kamer ${x}`, d_and: "en",
  d_open_lh: "Open in Lighthouse", d_app: "Gast-app bekijken", d_profile: "Gastprofiel", d_auto: "Automatische berichten voor deze reservatie",
  d_auto_off: " Zet je het uit, dan gaat er niets meer automatisch naar deze gast.", d_timeline: "Tijdlijn van de berichten",
  d_sent: "Verstuurd", d_failed: "Mislukt", d_planned: "Komt nog", d_missed: "Te laat", d_cond: "Voorwaarde niet voldaan", d_off: "Niet actief",
  d_again: "Opnieuw versturen", d_now: "Nu versturen", d_send: "Versturen", d_cancel: "Annuleren", d_attempts: "Alle pogingen en gebeurtenissen",
  d_time: "Tijdstip", d_msg: "Bericht of gebeurtenis", d_chan: "Kanaal of detail", d_to: "Naar", d_status: "Status", d_err: "Fout",
  d_pins: "Pincodes", d_made: "Gemaakt", d_valid: (a, b) => `geldig ${a} tot ${b}`, d_pins_pms: "Gemaakt bij Salto en in Lighthouse gezet.", d_pins_salto: "Gemaakt bij Salto, nog niet in Lighthouse gezet.",
  d_pay: "Betaling", d_open: "Open", d_paid: "Betaald", d_rooms_lbl: "Kamers", d_paid_payout: d => `Betaald (overschrijving Booking.com ${d})`, d_unpaid: "Niet betaald", d_unknown: "Nog niet gecontroleerd",
  d_open_lbl: "Openstaand", d_total: "Totaal", d_payreq: "Betaalverzoek bekijken", d_payreq_at: d => `Betaalverzoek gemaakt op ${d}.`,
  d_contact: "Contact", d_src: x => `bron: ${x}`, d_add: "Adres toevoegen", d_add_ph: "E-mailadres of gsm-nummer (+32...)", d_data: "Gegevens",
  d_k_chan: "Kanaal", d_k_flow: "Flow", d_k_rate: "Tarief", d_k_booked: "Geboekt op", d_k_added: "Toegevoegd", d_k_updated: "Bijgewerkt", d_nrf: "niet annuleerbaar", d_flex: "annuleerbaar",
  d_door: "Voordeur", d_moves: "Kamerwissel", d_pins_when: d => `Gemaakt bij Salto op ${d}.`, d_pins_when_pms: (a, b) => `Gemaakt bij Salto op ${a} en in Lighthouse gezet op ${b}.`, d_pins_in_pms: "In Lighthouse gezet.",
  l_sub: "Ontbijt en schoonmaak", l_make_title: "Lijst maken", l_last: n => "Laatste lijsten", l_make_k: { breakfast: "Ontbijtlijst maken", cleaning: "Schoonmaaklijst maken" }, l_last_k: { breakfast: "Laatste ontbijtlijsten", cleaning: "Laatste schoonmaaklijsten" }, l_all: "Alle lijsten", l_c_list: "Lijst", l_c_made: "Gemaakt op", l_c_sent: "Verstuurd naar",
  l_preview: "Voorbeeld zoals geprint", l_title_breakfast: d => `Ontbijtlijst ${d}`, l_title_cleaning: d => `Schoonmaaklijst ${d}`, l_made_by: (w, b) => `gemaakt ${w} door ${b}`,
  l_sent: x => `Verstuurd: ${x}`, l_not_sent: "Niet verstuurd", l_none_sel: "Kies een lijst om te bekijken.", l_mail: n => `mail ${n}`, l_wa: n => `WhatsApp ${n}`, l_sms: n => `sms ${n}`, l_failed: "Mislukt",
  gc_uit: "Uit", gc_selectie: "Selectie", gc_aan: "Aan", gc_uit_help: "Er gaat niets naar gasten.", gc_selectie_help: "Alleen reservaties die je zelf aanzet. Om te testen.", gc_aan_help: "Alle reservaties, behalve wie je uitvinkt.",
  hs_env_badge: "Vast per omgeving (Key Vault)", hs_env_note: "Deze waarden liggen vast per omgeving en zijn hier niet te wijzigen. Aanpassen gebeurt in Azure Key Vault.",
  rb_busy: "Bezig", rb_idle: "Klaar", rb_sub: "Leest Lighthouse volgens het schema van het hotel", rb_state: "Toestand", rb_hours: "Uren terug", rb_help: "De knop is uit zolang de robot bezig is.", rb_log: "Logboek per run",
  wfx_sub: "Welke berichten wanneer vertrekken, per flow", wfx_unsaved: "Niet bewaarde wijzigingen", wfx_in_flow: f => `in de flow ${f}`, wfx_line: "Tijdlijn van boeking tot na vertrek",
  wfx_click: "Klik een stap om ze te wijzigen", wfx_step: s => `Stap: ${s}`, wfx_recog: "Herkennen van deze flow", wfx_booking: "Boeking",
  nav_today: "Vandaag", td_update: (d, u) => `${d}, laatste update ${u}`, td_arr: "aankomsten vandaag", td_arr_tom: "aankomsten morgen", td_dep: "vertrekken vandaag",
  td_inhouse: (r) => `gasten in huis (${r} kamers)`, td_failed: "bericht mislukt", td_attn: "Vraagt aandacht", td_points: n => `${n} punten`,
  td_a_failed: (s, g, x) => `<b>${s} mislukt</b> voor ${g}${x ? ` (${x})` : ""}.`, td_a_resend: "Opnieuw versturen",
  td_a_failed2: (s, ch, g, to, why) => `<b>${s} per ${ch} niet verstuurd</b> voor ${g}${to ? ` (${to})` : ""}. ${why}`,
  td_a_tech: "Technische fout", td_a_dismiss: "Negeren",
  pb_mail_rights: "De app mag geen mails versturen: de rechten in Microsoft 365 ontbreken.",
  pb_provider_rights: "Twilio weigerde de aanmelding: het account of de sleutel klopt niet.",
  pb_bad_address: "Het adres of nummer is ongeldig.", pb_not_delivered: "Verstuurd, maar niet afgeleverd bij de gast.",
  pb_template: "WhatsApp weigerde het bericht (sjabloon niet goedgekeurd of buiten het venster van 24 uur).",
  pb_unavailable: "De dienst was even niet bereikbaar.", pb_other: "Onbekende fout.",
  td_a_unpaid: (g, a) => `<b>${g} komt vandaag</b> en heeft nog niet betaald${a ? ` (${a})` : ""}. Zonder betaling geen pincode.`, td_a_open: "Reservatie openen",
  td_a_form: x => `<b>Formulier niet ingevuld:</b> ${x}.`, td_a_view: "Bekijken", td_today_s: "vandaag", td_tomorrow_s: "morgen",
  td_a_blist: t => `<b>Ontbijtlijst voor morgen</b> nog niet gemaakt (automatisch om ${t}).`, td_a_make: "Nu maken",
  td_arr_today: d => `Aankomsten vandaag, ${d}`, td_arr_tomorrow: d => `Aankomsten morgen, ${d}`, td_all_res: "Alle reservaties",
  td_c_guest: "Gast", td_c_room: "Kamer", td_c_form: "Formulier", td_c_paid: "Betaald", td_c_code: "Code", td_c_mail: "Code-mail", td_c_labels: "Labels",
  td_filled: "Ingevuld", td_notfilled: "Niet ingevuld", td_paid: "Betaald", td_open: "Open", td_made: "Gemaakt", td_waitpay: "Wacht op betaling", td_sent: "Verstuurd",
  td_notsent: "Niet verstuurd", td_wait: "wacht", td_coming: "komt nog", td_none: "geen", td_deps: "Vertrekken vandaag", td_checkout: t => `Check-out tot ${t}`,
  td_left: "Vertrokken", td_openst: "Openstaand", td_openst_x: a => `Openstaand ${a}`, td_now: "Nu in huis", td_nowcount: (r, g) => `${r} kamers, ${g} gasten`, td_until: d => `tot ${d}`,
  st_lbl: "Status", st_all: "Alle", st_active: "Niet geannuleerd", st_cancelled: "Geannuleerd", pick_clear: "Toon alle",
  td_more: n => `en nog ${n}`, td_robot: "Robot", td_last: "Laatste run", td_result: "Resultaat", td_next: "Volgende", td_res_x: (n, u) => `${n} nieuwe, ${u} bijgewerkt`,
  td_run: "Robot nu draaien", td_log: "Logboek", td_msgs: "Berichten", td_msgs_failed: (n, x) => `<b>${n} mislukt</b>: ${x}`, td_msgs_today: n => `Vertrekt vandaag nog (${n})`,
  td_lists: "Lijsten", td_cl_today: "Schoonmaaklijst", td_bl: "Ontbijtlijst", td_l_today: "vandaag", td_l_tomorrow: "morgen", td_l_made: (w, x) => `Gemaakt ${w}${x}`,
  td_l_auto: t => `Automatisch om ${t}`, td_l_notyet: "Nog niet", td_l_sent: "Verstuurd", td_l_made_b: "Gemaakt", td_open_soon: "Openstaand, komt binnenkort",
  td_room: n => `kamer ${n}`, td_tax: "toeristenbelasting", td_none_attn: "Niets dat aandacht vraagt.", td_no_arr: "Geen aankomsten.", td_ok: "In orde",
  td_miss_form: "Mist formulier", td_miss_pay: "Mist betaling", td_miss_code: "Mist code-mail", td_tomorrow_n: n => `${n} aankomsten`, td_tomorrow_open: (f, p) => `${f} formulier en ${p} betaling open`,
  td_arrivals_m: "aankomsten", td_deps_m: "vertrekken", td_inhouse_m: "in huis", td_robot_ok: "Gelukt", td_robot_err: "Fout", td_robot_last_m: (w, n, u) => `Laatste run ${w}, ${n} nieuw, ${u} bijgewerkt`,
  ev_event: "Gebeurtenis", ev_reply: "Antwoord", ev_all: "Alles", ev_msgs: "Alleen berichten", ev_events: "Alleen gebeurtenissen", ev_ok: "Gelukt", ev_lh: "Lighthouse", ev_recv: "Ontvangen",
  ev_booked: "Reservatie gemaakt in Lighthouse", ev_added: "Reservatie gelezen door de robot", ev_payout: "Overschrijving Booking.com geregistreerd", ev_payreq: "Betaalverzoek gemaakt in Lighthouse",
  ev_bf: "Label ONTBIJT gezet in Lighthouse", ev_stairs: "Regel in de interne memo: moeilijk ter been", ev_stairs_lbl: "Label NIET VERPLAATSEN gezet in Lighthouse",
  ev_visit_first: "Gast opende zijn verblijfspagina voor het eerst", ev_visit_last: n => `Gast opende zijn verblijfspagina (laatste keer, ${n}× in totaal)`,
  ev_codes_seen: "Gast zag zijn pincode voor het eerst op de verblijfspagina", d_seen: (a, b) => `Gezien door de gast: ${a}${b ? `, laatst ${b}` : ""}`,
  d_not_seen: "Nog niet gezien door de gast op de verblijfspagina.",
  ev_move: (a, b) => `Kamerwissel in Lighthouse: ${a} (was ${b})`, ev_form: "Formulier ingevuld in de gast-app", ev_contact: "Contactgegevens gelezen in Lighthouse",
  ev_codes: "Pincodes gemaakt bij Salto", ev_codes_lh: "Code en status KLAAR OM IN TE CHECKEN gezet in Lighthouse",
  g_synced: d => `laatst gesynchroniseerd ${d}`, g_back: "Gasten", s_back: "Instellingen", hs_sec_reset_confirm: s => `De sectie "${s}" terugzetten naar de standaardwaarden uit het hotelbestand?`,
  hs_group_lbl: "Groep", hs_sec_lbl: "Sectie", wf_flow_m: f => `Flow: ${f}`, wf_line_m: "Van boeking tot na vertrek", wf_preview_m: "Voorbeeldmail", rb_now_m: "Nu draaien",
  rb_done_m: (a, b) => `${a} van ${b} gedaan`, rb_del_sel: "Selectie verwijderen", rp_search: "Zoekt oorzaak", rp_test: "Klaar om te testen", rp_solved: "Opgelost",
  gp_nowsuffix: "(nu)", gp_wa: "WhatsApp", gp_sms: "Sms", gp_none: "Kies een gast in de lijst.", gp_stays_m: n => `${n} verblijven`,
});
Object.assign(T.en, {
  m_arrives: d => `arriving ${d}`, list_more: (n, tot) => `${n} of ${tot} shown, scroll for more`, dlg_send: "Send",
  ls_send: "Send", ls_more: "Choose how to send", ls_ch_all: "Mail and WhatsApp", ls_ch_wa: "Only WhatsApp", ls_ch_mail: "Only mail", ls_ch_sms: "Only SMS", ls_by_sms: "By SMS", ls_title: "Send list manually", ls_q: l => `Are you sure you want to send the ${l} manually?`, ls_to: "Will be sent to",
  ls_by_mail: "Mail", ls_by_wa: "WhatsApp (SMS if WhatsApp fails)", ls_wa_off: "WhatsApp and SMS are off, will not be sent", ls_no_to: "No recipients are set for this list (settings, Hotel).",
  ls_past: d => `Watch out: this is not a list for today! It is the list of ${d}.`, ls_already: (w, to) => `This list was already sent on ${w} to ${to}.`,
  ls_note: "Message (optional)", ls_note_ph: "Goes at the top of the mail and in the WhatsApp or SMS", ls_done: x => `Sent: ${x}.`, ls_fail: x => `Not (fully) sent: ${x}`,
  rx_title: "Room exceptions", rx_help: "Rooms that differ from the rest: own name, own entrance, no floor, twin. All other rooms follow the rules above.",
  rx_add: "Add exception", rx_edit: "Edit", rx_close: "Done", rx_del: "Delete", rx_room: "Room number", rx_none: "No exceptions yet.",
  rx_new: "new exception", rx_del_confirm: r => `Delete the exception for room ${r}? It is only gone after you save.`,
  rx_no_room: "Fill in a room number for every exception.", rx_dup: r => `Room ${r} is listed twice.`, rx_empty: "no values",
  rx_f_verdieping: ["Floor", "Empty = no floor in the mail and the SMS (e.g. own entrance). Or a number, e.g. 0 for the ground floor."],
  rx_f_lijst: ["Name on the lists", "Own name instead of the number on the breakfast and cleaning list (e.g. App). Empty = the number."],
  rx_f_twin: ["Twin room", "Made up with 2 separate beds by default. The label DOUBLE OPMAKEN then goes to the remarks on the cleaning list."],
  rx_f_naam: ["Name", "In the code mail, after the room number (e.g. Room 2, historic suite)."],
  rx_f_kort: ["Short", "In the SMS, after the room number."],
  rx_f_toegang: ["Access", "Explanation under the code in the mail, e.g. how the guest gets to the own entrance."],
  rx_lang: { nl: "Dutch", fr: "French", en: "English", de: "German" }, dlg_delete: "Delete", dlg_reset: "Reset", dlg_leave: "Leave without saving",
  nav_lists: "Lists", nav_messages: "Messages", logout: "Sign out", search_lbl: "Search",
  tst_bar: "Test environment: messages only go to the test addresses", env_name_prd: "Production", env_name_tst: "Test environment",
  c_stay: "Stay", c_res: "Reservation", c_room_rate: "Room and rate", c_channel: "Channel",
  r_until: (d, n) => `until ${d}, ${n} n.`, r_booked: d => `booked ${d}`, r_updated: d => `updated ${d}`,
  r_returning: n => `returning (${n}x)`, r_form: "Form", r_noform: "No form", r_stairs: "Stairs",
  r_msgs_on: "Messages on", r_msgs_off: "Messages off", r_cancelled: "Cancelled", r_rooms: n => `${n} rooms`,
  r_roomtype: "room type", r_room: n => `Room ${n}`, r_p: n => `${n} p.`, r_flow: f => `flow ${f}`, r_rate_nrf: "NRF", r_rate_flex: "Refundable",
  r_next: x => `Next: ${x}`, r_next_m: x => `next: ${x}`, r_none: "none", r_none_off: "none (off)", r_failed: x => `${x} failed`,
  r_emails: "E-mail addresses", r_phones: "Mobile numbers", r_details: n => `Details ${n}`,
  res_count: n => `<b style="color:#2B2F38">${n} reservations</b>`, res_sel: 'Guest communication is set to <b>selection</b>: only reservations with the label "Messages on" get messages.',
  sw_robot: "Robot", sw_go: "To the settings", sw_st_on: "on", sw_st_off: "off", sw_st_sel: "selection",
  g_sub: "Guest profiles separate from the reservations, kept after the stay.", g_name: "Name", g_profiles: n => `${n} guest profiles`,
  m_card: "To decide: possibly the same guest", m_open: n => `${n} open`, m_and: "and", m_keep: "Merge", m_apart: "Keep apart",
  gp_since: d => `guest profile since ${d}`, gp_nomkt: "No marketing", gp_back: "Returning", gp_resn: "reservations", gp_stays: "stays", gp_canc: "cancelled", pick_filter: "Filter",
  gp_nights: "nights avg.", gp_pers: "persons avg.", gp_first: "First stay", gp_last: "Last stay", gp_chan: "Preferred channel", gp_rooms: "Rooms",
  gp_contact: "Contact", gp_help: "Stay info: messages about the stay (confirmation, code, ...) to this address. The robot follows these ticks; you can swap them. Marketing: newsletters and offers to this address.", gp_use: "use", gp_relay: "relay address of the booking site (never marketing)", gp_old: "not used: earlier address", gp_fake: "fake number of the booking site: never used",
  gp_stayinfo: "Stay info", gp_mkt: "Marketing", gp_not_used: "not used: there is an own e-mail address", gp_no_consent: "no permission in the check-in form", gp_mkt_noform: "marketing follows the choice in the check-in form (not filled in with this address yet)", gp_mkt_guest: "the guest asked for no marketing", gp_mkt_relay: "relay address: never marketing",
  gp_detach: "Detach", gp_detach_q: n => `Reservation #${n} does not belong to this guest? It gets its own guest profile, or joins the guest it surely belongs to. It never comes back to this guest.`, gp_detached: "Detached.",
  gp_form: "form", gp_booking: "reservation", gp_res: "Reservations", gp_all: n => `All ${n} reservations`, gp_now: "Now", gp_left: "Departed", gp_coming: "Coming",
  d_back: "Reservations", d_nights: n => `${n} nights`, d_persons: n => `${n} persons`, d_rooms: x => `room ${x}`, d_and: "and",
  d_open_lh: "Open in Lighthouse", d_app: "View guest app", d_profile: "Guest profile", d_auto: "Automatic messages for this reservation",
  d_auto_off: " If you switch it off, nothing more goes to this guest automatically.", d_timeline: "Timeline of the messages",
  d_sent: "Sent", d_failed: "Failed", d_planned: "Still to come", d_missed: "Too late", d_cond: "Condition not met", d_off: "Not active",
  d_again: "Send again", d_now: "Send now", d_send: "Send", d_cancel: "Cancel", d_attempts: "All attempts and events",
  d_time: "Time", d_msg: "Message or event", d_chan: "Channel or detail", d_to: "To", d_status: "Status", d_err: "Error",
  d_pins: "PIN codes", d_made: "Created", d_valid: (a, b) => `valid ${a} until ${b}`, d_pins_pms: "Created at Salto and set in Lighthouse.", d_pins_salto: "Created at Salto, not yet set in Lighthouse.",
  d_pay: "Payment", d_open: "Open", d_paid: "Paid", d_rooms_lbl: "Rooms", d_paid_payout: d => `Paid (Booking.com payout ${d})`, d_unpaid: "Not paid", d_unknown: "Not checked yet",
  d_open_lbl: "Outstanding", d_total: "Total", d_payreq: "View payment request", d_payreq_at: d => `Payment request created on ${d}.`,
  d_contact: "Contact", d_src: x => `source: ${x}`, d_add: "Add address", d_add_ph: "E-mail address or mobile number (+32...)", d_data: "Details",
  d_k_chan: "Channel", d_k_flow: "Flow", d_k_rate: "Rate", d_k_booked: "Booked on", d_k_added: "Added", d_k_updated: "Updated", d_nrf: "non-refundable", d_flex: "refundable",
  d_door: "Front door", d_moves: "Room change", d_pins_when: d => `Created at Salto on ${d}.`, d_pins_when_pms: (a, b) => `Created at Salto on ${a} and set in Lighthouse on ${b}.`, d_pins_in_pms: "Set in Lighthouse.",
  l_sub: "Breakfast and cleaning", l_make_title: "Make a list", l_last: n => "Latest lists", l_make_k: { breakfast: "Make a breakfast list", cleaning: "Make a cleaning list" }, l_last_k: { breakfast: "Latest breakfast lists", cleaning: "Latest cleaning lists" }, l_all: "All lists", l_c_list: "List", l_c_made: "Made on", l_c_sent: "Sent to",
  l_preview: "Preview as printed", l_title_breakfast: d => `Breakfast list ${d}`, l_title_cleaning: d => `Cleaning list ${d}`, l_made_by: (w, b) => `made ${w} by ${b}`,
  l_sent: x => `Sent: ${x}`, l_not_sent: "Not sent", l_none_sel: "Choose a list to view.", l_mail: n => `mail ${n}`, l_wa: n => `WhatsApp ${n}`, l_sms: n => `SMS ${n}`, l_failed: "Failed",
  gc_uit: "Off", gc_selectie: "Selection", gc_aan: "On", gc_uit_help: "Nothing goes to guests.", gc_selectie_help: "Only reservations you switch on yourself. For testing.", gc_aan_help: "All reservations, except the ones you untick.",
  hs_env_badge: "Fixed per environment (Key Vault)", hs_env_note: "These values are fixed per environment and cannot be changed here. They are changed in Azure Key Vault.",
  rb_busy: "Running", rb_idle: "Ready", rb_sub: "Reads Lighthouse on the hotel's schedule", rb_state: "State", rb_hours: "Hours back", rb_help: "The button is off while the robot is running.", rb_log: "Log per run",
  wfx_sub: "Which messages go out when, per flow", wfx_unsaved: "Unsaved changes", wfx_in_flow: f => `in the flow ${f}`, wfx_line: "Timeline from booking to after departure",
  wfx_click: "Click a step to change it", wfx_step: s => `Step: ${s}`, wfx_recog: "Recognising this flow", wfx_booking: "Booking",
  nav_today: "Today", td_update: (d, u) => `${d}, last update ${u}`, td_arr: "arrivals today", td_arr_tom: "arrivals tomorrow", td_dep: "departures today",
  td_inhouse: (r) => `guests in house (${r} rooms)`, td_failed: "message failed", td_attn: "Needs attention", td_points: n => `${n} items`,
  td_a_failed: (s, g, x) => `<b>${s} failed</b> for ${g}${x ? ` (${x})` : ""}.`, td_a_resend: "Send again",
  td_a_failed2: (s, ch, g, to, why) => `<b>${s} by ${ch} not sent</b> for ${g}${to ? ` (${to})` : ""}. ${why}`,
  td_a_tech: "Technical error", td_a_dismiss: "Dismiss",
  pb_mail_rights: "The app may not send mail: the Microsoft 365 permissions are missing.",
  pb_provider_rights: "Twilio refused the sign-in: the account or key is wrong.",
  pb_bad_address: "The address or number is invalid.", pb_not_delivered: "Sent, but not delivered to the guest.",
  pb_template: "WhatsApp refused the message (template not approved or outside the 24 hour window).",
  pb_unavailable: "The service was briefly unavailable.", pb_other: "Unknown error.",
  td_a_unpaid: (g, a) => `<b>${g} arrives today</b> and has not paid yet${a ? ` (${a})` : ""}. No PIN code without payment.`, td_a_open: "Open reservation",
  td_a_form: x => `<b>Form not filled in:</b> ${x}.`, td_a_view: "View", td_today_s: "today", td_tomorrow_s: "tomorrow",
  td_a_blist: t => `<b>Breakfast list for tomorrow</b> not made yet (automatically at ${t}).`, td_a_make: "Make now",
  td_arr_today: d => `Arrivals today, ${d}`, td_arr_tomorrow: d => `Arrivals tomorrow, ${d}`, td_all_res: "All reservations",
  td_c_guest: "Guest", td_c_room: "Room", td_c_form: "Form", td_c_paid: "Paid", td_c_code: "Code", td_c_mail: "Code mail", td_c_labels: "Labels",
  td_filled: "Filled in", td_notfilled: "Not filled in", td_paid: "Paid", td_open: "Open", td_made: "Created", td_waitpay: "Waiting for payment", td_sent: "Sent",
  td_notsent: "Not sent", td_wait: "waiting", td_coming: "still to come", td_none: "none", td_deps: "Departures today", td_checkout: t => `Check-out until ${t}`,
  td_left: "Departed", td_openst: "Outstanding", td_openst_x: a => `Outstanding ${a}`, td_now: "In house now", td_nowcount: (r, g) => `${r} rooms, ${g} guests`, td_until: d => `until ${d}`,
  st_lbl: "Status", st_all: "All", st_active: "Not cancelled", st_cancelled: "Cancelled", pick_clear: "Show all",
  td_more: n => `and ${n} more`, td_robot: "Robot", td_last: "Last run", td_result: "Result", td_next: "Next", td_res_x: (n, u) => `${n} new, ${u} updated`,
  td_run: "Run robot now", td_log: "Log", td_msgs: "Messages", td_msgs_failed: (n, x) => `<b>${n} failed</b>: ${x}`, td_msgs_today: n => `Still going out today (${n})`,
  td_lists: "Lists", td_cl_today: "Cleaning list", td_bl: "Breakfast list", td_l_today: "today", td_l_tomorrow: "tomorrow", td_l_made: (w, x) => `Made ${w}${x}`,
  td_l_auto: t => `Automatically at ${t}`, td_l_notyet: "Not yet", td_l_sent: "Sent", td_l_made_b: "Made", td_open_soon: "Outstanding, arriving soon",
  td_room: n => `room ${n}`, td_tax: "tourist tax", td_none_attn: "Nothing needs attention.", td_no_arr: "No arrivals.", td_ok: "OK",
  td_miss_form: "Missing form", td_miss_pay: "Missing payment", td_miss_code: "Missing code mail", td_tomorrow_n: n => `${n} arrivals`, td_tomorrow_open: (f, p) => `${f} form and ${p} payment open`,
  td_arrivals_m: "arrivals", td_deps_m: "departures", td_inhouse_m: "in house", td_robot_ok: "Succeeded", td_robot_err: "Error", td_robot_last_m: (w, n, u) => `Last run ${w}, ${n} new, ${u} updated`,
  ev_event: "Event", ev_reply: "Reply", ev_all: "All", ev_msgs: "Messages only", ev_events: "Events only", ev_ok: "Succeeded", ev_lh: "Lighthouse", ev_recv: "Received",
  ev_booked: "Reservation made in Lighthouse", ev_added: "Reservation read by the robot", ev_payout: "Booking.com payout registered", ev_payreq: "Payment request created in Lighthouse",
  ev_bf: "Label ONTBIJT set in Lighthouse", ev_stairs: "Line in the internal memo: difficulty with stairs", ev_stairs_lbl: "Label NIET VERPLAATSEN set in Lighthouse",
  ev_visit_first: "Guest opened the stay page for the first time", ev_visit_last: n => `Guest opened the stay page (last time, ${n}× in total)`,
  ev_codes_seen: "Guest first saw the PIN code on the stay page", d_seen: (a, b) => `Seen by the guest: ${a}${b ? `, last ${b}` : ""}`,
  d_not_seen: "Not seen by the guest on the stay page yet.",
  ev_move: (a, b) => `Room change in Lighthouse: ${a} (was ${b})`, ev_form: "Form filled in in the guest app", ev_contact: "Contact details read in Lighthouse",
  ev_codes: "PIN codes created at Salto", ev_codes_lh: "Code and status READY TO CHECK IN set in Lighthouse",
  g_synced: d => `last synchronized ${d}`, g_back: "Guests", s_back: "Settings", hs_sec_reset_confirm: s => `Reset the section "${s}" to the defaults from the hotel file?`,
  hs_group_lbl: "Group", hs_sec_lbl: "Section", wf_flow_m: f => `Flow: ${f}`, wf_line_m: "From booking to after departure", wf_preview_m: "Preview mail", rb_now_m: "Run now",
  rb_done_m: (a, b) => `${a} of ${b} done`, rb_del_sel: "Delete selection", rp_search: "Looking for the cause", rp_test: "Ready to test", rp_solved: "Solved",
  gp_nowsuffix: "(now)", gp_wa: "WhatsApp", gp_sms: "SMS", gp_none: "Choose a guest in the list.", gp_stays_m: n => `${n} stays`,
});
// WhatsApp-sjablonen (instellingen, WhatsApp)
Object.assign(T.nl, {
  tab_wa: "WhatsApp", wa_sub: "Teksten van de WhatsApp-berichten. Elke nieuwe tekst moet eerst door Meta goedgekeurd worden.",
  wa_how: "Zo werkt het", wa_how_text: "Wijzig de tekst, bewaar en dien in bij Meta. Tot Meta de nieuwe versie goedkeurt, blijft de vorige goedgekeurde versie verstuurd worden. Zonder goedgekeurde versie in die taal gaat de Engelse, en anders een sms. De status wordt gevraagd zolang Meta nog beslist; afgewezen versies nog elk uur, want na een bezwaar kan Meta ze alsnog goedkeuren.",
  wa_overview: "Overzicht", wa_check: "Status vernieuwen", wa_all: n => `Alles indienen (${n})`, wa_all_none: "Alles ingediend",
  wa_all_q: n => `${n} nieuwe of gewijzigde teksten bij Meta indienen?`, wa_submit: "Indienen bij Meta", wa_submit_q: "Deze tekst bij Meta indienen? De goedgekeurde versie blijft in gebruik tot Meta de nieuwe goedkeurt.",
  wa_save: "Bewaren", wa_reset: "Herstellen", wa_reset_q: "Terug naar de actieve tekst (of de standaardtekst als er nog geen goedgekeurde versie is)? Daarna kan je indienen.",
  wa_header: "Titel (vet bovenaan, niet verplicht)", wa_body: "Tekst", wa_button: "Knoptekst", wa_footer: "Voettekst (niet verplicht)", wa_preview: "Voorbeeld",
  wa_button_help: p => `De knop opent ${p}... (de link van de gast komt er automatisch achter).`, wa_media_help: p => `De pdf komt bovenaan het bericht (${p || "adres van de Function App"}...).`,
  wa_vars: "Plaatsen", wa_unsaved: "Niet bewaard.", wa_saved: "Bewaard.", wa_dlg_submit: "Indienen", wa_dlg_reset: "Herstellen",
  wa_st_approved: "Goedgekeurd", wa_st_waiting: "Wacht op Meta", wa_st_changed: "Gewijzigd, niet ingediend", wa_st_new: "Nog niet ingediend", wa_st_rejected: "Afgekeurd", wa_st_error: "Fout",
  wa_active: (v, d) => `In gebruik: versie ${v}, goedgekeurd ${d}.`, wa_none_active: "Nog geen goedgekeurde versie: dit bericht gaat per sms.",
  wa_manual: sid => `In gebruik: sjabloon ${sid} uit de instellingen.`,
  wa_pending: (v, d, who) => `Versie ${v} ingediend ${d}${who ? " door " + who : ""}.`, wa_checked: d => `Laatst nagekeken ${d}.`, wa_reason: r => `Reden van Meta: ${r}`,
  wa_twilio: n => `Openen in Twilio (zoek op ${n})`, wa_replace: "Meta beslist nog over de ingediende versie. Een nieuwe versie indienen vervangt die; de goedgekeurde versie blijft in gebruik tot Meta de nieuwe goedkeurt.",
  wa_defaults: n => `Nieuwe standaardteksten overnemen (${n})`, wa_defaults_q: n => `${n} teksten vervangen door de nieuwe standaardtekst? Daarna indienen; tot Meta ze goedkeurt blijven de huidige goedgekeurde versies verstuurd.`, wa_defaults_done: n => `${n} standaardteksten overgenomen. Klik nu op Alles indienen.`,
  wa_shared: (env, d) => `Deze omgeving gebruikt de goedgekeurde sjablonen van ${env.toUpperCase()}: wijzigen en indienen gebeurt daar. De knop opent het ${env.toUpperCase()}-formulier, dat de gast doorstuurt naar het formulier van deze omgeving.${d ? " Laatst opgevraagd " + d + "." : ""}`,
  wa_changes: x => `Nieuw: ${x}.`, wa_no_changes: "Geen nieuwe beslissing van Meta.", wa_done: n => `${n} ingediend.`,
  wa_t_confirmation: ["Bevestiging", "Meteen na de boeking, met knop naar het check-in-formulier."],
  wa_t_reminder: ["Herinnering", "Een week voor aankomst, als het formulier nog niet ingevuld is."],
  wa_t_access_code: ["Pincode", "Per kamer, met een knop naar de reservatie (pincode, deuren openen, betalen). Het getal zelf nooit in WhatsApp: Meta keurt dat af. Het woord pincode mag wel."],
  wa_t_room_change: ["Kamerwissel", "Als de kamer wijzigt nadat de pincode verstuurd is (de pincode blijft dezelfde), met een knop naar de reservatie."],
  wa_t_breakfast_list: ["Ontbijtlijst (personeel)", "Met de lijst als pdf bovenaan."],
  wa_t_cleaning_list: ["Schoonmaaklijst (personeel)", "Met de lijst als pdf bovenaan."],
  wa_v: { voornaam: "voornaam", kamer_kort: "kamer", pincode: "pincode", dag: "dag", samenvatting: "samenvatting" },
});
Object.assign(T.en, {
  tab_wa: "WhatsApp", wa_sub: "Texts of the WhatsApp messages. Every new text must first be approved by Meta.",
  wa_how: "How it works", wa_how_text: "Change the text, save and submit to Meta. Until Meta approves the new version, the previous approved version keeps being sent. Without an approved version in that language the English one is sent, otherwise an SMS. The status is asked while Meta has not decided yet; rejected versions still every hour, since Meta can approve them after an appeal.",
  wa_overview: "Overview", wa_check: "Refresh status", wa_all: n => `Submit all (${n})`, wa_all_none: "All submitted",
  wa_all_q: n => `Submit ${n} new or changed texts to Meta?`, wa_submit: "Submit to Meta", wa_submit_q: "Submit this text to Meta? The approved version stays in use until Meta approves the new one.",
  wa_save: "Save", wa_reset: "Restore", wa_reset_q: "Back to the active text (or the default text if there is no approved version yet)? Then you can submit.",
  wa_header: "Title (bold on top, optional)", wa_body: "Text", wa_button: "Button text", wa_footer: "Footer (optional)", wa_preview: "Preview",
  wa_button_help: p => `The button opens ${p}... (the guest's link is added automatically).`, wa_media_help: p => `The PDF goes on top of the message (${p || "address of the Function App"}...).`,
  wa_vars: "Placeholders", wa_unsaved: "Not saved.", wa_saved: "Saved.", wa_dlg_submit: "Submit", wa_dlg_reset: "Restore",
  wa_st_approved: "Approved", wa_st_waiting: "Waiting for Meta", wa_st_changed: "Changed, not submitted", wa_st_new: "Not submitted yet", wa_st_rejected: "Rejected", wa_st_error: "Error",
  wa_active: (v, d) => `In use: version ${v}, approved ${d}.`, wa_none_active: "No approved version yet: this message goes by SMS.",
  wa_manual: sid => `In use: template ${sid} from the settings.`,
  wa_pending: (v, d, who) => `Version ${v} submitted ${d}${who ? " by " + who : ""}.`, wa_checked: d => `Last checked ${d}.`, wa_reason: r => `Reason from Meta: ${r}`,
  wa_twilio: n => `Open in Twilio (search for ${n})`, wa_replace: "Meta has not decided on the submitted version yet. Submitting a new version replaces it; the approved version stays in use until Meta approves the new one.",
  wa_defaults: n => `Take over new default texts (${n})`, wa_defaults_q: n => `Replace ${n} texts with the new default text? Then submit; until Meta approves them the current approved versions keep being sent.`, wa_defaults_done: n => `${n} default texts taken over. Now click Submit all.`,
  wa_shared: (env, d) => `This environment uses the approved templates of ${env.toUpperCase()}: changing and submitting happens there. The button opens the ${env.toUpperCase()} form, which forwards the guest to the form of this environment.${d ? " Last checked " + d + "." : ""}`,
  wa_changes: x => `New: ${x}.`, wa_no_changes: "No new decision from Meta.", wa_done: n => `${n} submitted.`,
  wa_t_confirmation: ["Confirmation", "Right after the booking, with a button to the check-in form."],
  wa_t_reminder: ["Reminder", "One week before arrival, if the form is not filled in yet."],
  wa_t_access_code: ["PIN code", "Per room, with a button to the reservation (PIN code, opening doors, paying). Never the number itself in WhatsApp: Meta rejects that. The word PIN code is fine."],
  wa_t_room_change: ["Room change", "When the room changes after the PIN code was sent (the PIN code stays the same), with a button to the reservation."],
  wa_t_breakfast_list: ["Breakfast list (staff)", "With the list as a PDF on top."],
  wa_t_cleaning_list: ["Cleaning list (staff)", "With the list as a PDF on top."],
  wa_v: { voornaam: "first name", kamer_kort: "room", pincode: "PIN code", dag: "day", samenvatting: "summary" },
});
let lang = "nl";
const t = (k, ...a) => { const v = T[lang][k]; return typeof v === "function" ? v(...a) : v; };
const locale = () => (lang === "en" ? "en-GB" : "nl-BE");
const $ = s => document.querySelector(s);
const esc = s => String(s ?? "").replace(/[&<>"]/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));

// Eigen popup in plaats van confirm() en alert() van de browser.
// ask(tekst, { ok: "Samenvoegen", danger: true }) geeft een Promise<boolean>; notice(tekst) alleen een knop om te sluiten.
// html: eigen inhoud (al veilig gemaakt) onder de tekst; input: { label, placeholder } = vrij tekstveld, dan geeft
// de popup de tekst terug (of null bij annuleren) in plaats van true/false.
function dialog(text, { ok, cancel = true, danger = false, title = "", html = "", input = null } = {}) {
  return new Promise(resolve => {
    const en = lang === "en" ? 1 : 0;
    const back = document.createElement("div");
    back.className = "v2 dlg-back";
    back.innerHTML = `<div class="card dlg" role="dialog" aria-modal="true" aria-labelledby="dlg-t">
      <div class="dlg-b">${title ? `<h2 class="ct" id="dlg-t">${esc(title)}</h2>` : ""}<p ${title ? "" : 'id="dlg-t"'}>${esc(text)}</p>${html}
        ${input ? `<div class="field"><label for="dlg-in">${esc(input.label || "")}</label><textarea class="input" id="dlg-in" rows="3" maxlength="500" placeholder="${esc(input.placeholder || "")}"></textarea></div>` : ""}</div>
      <div class="dlg-f">${cancel ? `<button type="button" class="btn2" data-v="0">${esc(["Annuleren", "Cancel"][en])}</button>` : ""}
      <button type="button" class="btn${danger ? " danger" : ""}" data-v="1">${esc(ok || (cancel ? ["Bevestigen", "Confirm"][en] : "OK"))}</button></div></div>`;
    const prev = document.activeElement;
    const done = v => {
      const val = input ? (v ? back.querySelector("#dlg-in").value.trim() : null) : v;
      document.removeEventListener("keydown", key, true); back.remove(); if (prev && prev.focus) prev.focus(); resolve(val);
    };
    const key = e => {
      if (e.key === "Escape") { e.preventDefault(); done(!cancel); }
      else if (e.key === "Tab") {  // focus binnen de popup houden
        const b = [...back.querySelectorAll("button, textarea")], i = b.indexOf(document.activeElement);
        e.preventDefault(); b[(i + (e.shiftKey ? b.length - 1 : 1)) % b.length].focus();
      }
    };
    // Klikken naast de popup sluit ze niet: alleen de knoppen in de popup (of Escape)
    back.querySelectorAll("button").forEach(b => b.onclick = () => done(b.dataset.v === "1"));
    document.addEventListener("keydown", key, true);
    document.body.appendChild(back);
    back.querySelector(input ? "#dlg-in" : danger && cancel ? 'button[data-v="0"]' : 'button[data-v="1"]').focus();
  });
}
const ask = (text, opts = {}) => dialog(text, opts);
const notice = (text, opts = {}) => dialog(text, { ...opts, cancel: false });
const day = iso => iso ? new Date(iso + (iso.length === 10 ? "T00:00" : "")).toLocaleDateString(locale(), { day: "2-digit", month: "2-digit", year: "2-digit" }) : "";
const stamp = iso => iso ? new Date(iso).toLocaleString(locale(), { day: "2-digit", month: "2-digit", hour: "2-digit", minute: "2-digit" }) : "";
let rows = [], runsData = null, timer = null, waitTries = 0;
const resAsked = new Set();  // reservaties die al eens opgevraagd werden (niet blijven vragen als ze er niet meer zijn)

// ---- Lijsten per 50 van de server (index op de server), doorlopend scrollen
// rows = alle reservaties die de app al kent (cache, per id). De lijst Reservaties toont resIds (volgorde van de
// server), Vandaag toont todayIds (aankomsten en vertrekken rond vandaag en mislukte berichten).
const RES_PAGE = 50;
let resIds = [], resTotal = 0, resNext = null, resLoading = false, resSeq = 0, todayIds = null;
function mergeRows(items) {
  const m = new Map(rows.map(r => [r.id, r]));
  items.forEach(r => m.set(r.id, r));
  rows = [...m.values()];
}
const resById = id => rows.find(r => r.id === id);
const allRows = () => rows;
function resParams(offset, limit) {
  const p = new URLSearchParams({ page: "1", offset: String(offset), limit: String(limit) });
  if (resPick) p.set("ids", [...resPick.ids].join(","));
  else {
    if ($("#search").value.trim()) p.set("q", $("#search").value.trim());
    if ($("#from").value) p.set("from", $("#from").value);
    if ($("#to").value) p.set("to", $("#to").value);
    if ($("#status") && $("#status").value) p.set("status", $("#status").value);
  }
  p.set("sort", sortKey === "messages" ? "arrival" : sortKey);
  p.set("dir", sortDir > 0 ? "asc" : "desc");
  return p;
}
// reset: opnieuw van boven (filter of sortering veranderd); keep: zoveel rijen meteen laden (verversen zonder
// dat de lijst korter wordt en de scrollpositie verspringt)
async function loadResPage(reset = true, keep = 0) {
  if (!$("#res")) return;
  const seq = ++resSeq;
  resLoading = true;
  const offset = reset ? 0 : resIds.length, limit = reset ? Math.max(RES_PAGE, keep) : RES_PAGE;
  try {
    const d = await get(`/api/monitor/${$("#hotel").value}/reservations?${resParams(offset, limit)}`);
    if (seq !== resSeq) return;  // er kwam intussen een nieuwere vraag
    mergeRows(d.items);
    const ids = d.items.map(r => r.id);
    resIds = reset ? ids : resIds.concat(ids.filter(id => !resIds.includes(id)));
    resTotal = d.total; resNext = d.next;
  } finally {
    if (seq === resSeq) resLoading = false;
  }
  render();
}
async function loadToday() {
  const today = todayIso();
  const d = await get(`/api/monitor/${$("#hotel").value}/reservations?page=1&window=${addDays(today, -2)},${addDays(today, 14)}`);
  mergeRows(d.items);
  todayIds = new Set(d.items.map(r => r.id));
}
// Alles verversen; de lijst houdt zoveel rijen als er nu geladen zijn
async function loadReservations() {
  await Promise.all([loadToday(), loadResPage(true, resIds.length)]);
}
// Precies deze reservaties ophalen als de app ze nog niet kent (detail, gastprofiel)
async function ensureRes(ids, fresh = false) {
  const miss = fresh ? ids : ids.filter(id => !resById(id));
  if (!miss.length) return;
  const d = await get(`/api/monitor/${$("#hotel").value}/reservations?page=1&ids=${encodeURIComponent(miss.join(","))}`);
  mergeRows(d.items);
}
let resFilterTimer = null;
function resFilterChanged(delay = 0) {
  clearTimeout(resFilterTimer);
  resFilterTimer = setTimeout(() => { loadResPage(true); }, delay);
}
// Doorlopend scrollen: een lege rij onder de lijst; komt die in beeld, dan de volgende 50
function watchMore(sentinelId, more) {
  const el = $(sentinelId);
  if (!el || !("IntersectionObserver" in window)) return;
  new IntersectionObserver(es => { if (es.some(e => e.isIntersecting)) more(); }, { rootMargin: "600px 0px" }).observe(el);
}
const runOpen = {};  // robotlog: welke runs zelf open- of dichtgeklapt werden (blijft zo bij het verversen)
const TASKS = ["nieuwe_reservaties", "contactgegevens_nalezen", "overschrijving_booking", "lighthouse_bijwerken", "betaalverzoeken", "ontbijt_labels", "meldingen", "onderhoud", "berichten", "ontbijtlijst", "kuislijst"];
// Taken zonder Te doen/Gedaan (alleen een notitie, bv. de bewaking: welke mail verstuurd werd)
const NO_COUNTS = ["bewaking", "onderhoud", "robot"];  // onderhoud: de aantallen staan in de notitie
const taskName = k => T[lang]["task_" + k] || k;
let taskFilter = "";
try { taskFilter = localStorage.getItem("monitor-task") || ""; } catch (e) { /* geen opslag */ }

function store(k, v) { try { v === undefined ? null : localStorage.setItem(k, v); return localStorage.getItem(k); } catch { return null; } }
// Elke aanroep van de monitor-API draagt deze kop. Een andere website kan die niet meesturen zonder
// toestemming (CORS), dus een wijziging (versturen, samenvoegen, robot starten) kan niet van elders komen.
function apiFetch(url, opts = {}) {
  return fetch(url, { ...opts, headers: { ...(opts.headers || {}), "X-Monitor": "1" } });
}
async function get(path, opts) {
  const r = await apiFetch(API + path, opts);
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
  const mkMore = document.getElementById("list-send-ch"); if (mkMore) mkMore.setAttribute("aria-label", t("ls_more"));
  document.querySelectorAll("[data-tp]").forEach(e => { e.placeholder = t(e.dataset.tp); });
  document.querySelectorAll("[data-tt]").forEach(e => { e.title = t(e.dataset.tt); });
  document.querySelectorAll("[data-lang]").forEach(b => { b.classList.toggle("active", b.dataset.lang === lang); b.classList.toggle("on", b.dataset.lang === lang); });
  const envNow = ($("#env")?.textContent || "").trim().toLowerCase();
  if ($("#envname")) $("#envname").textContent = t("env_name_" + envNow) || "";
  if ($("#env-switch") && !$("#env-switch").hidden) $("#env-switch").textContent = t("env_to_" + (envNow === "tst" ? "prd" : "tst"));
  renderSwitches();
  if (PAGE === "main") { render(); renderGuests(); LIST_KINDS.forEach(k => renderList(k)); } else { renderWorkflow(); renderSettings(); renderWhatsapp(); if (runsData) renderRuns(runsData); }
}

// Hoofdschakelaars van het gekozen hotel, altijd zichtbaar bovenaan (groen = aan, grijs = uit)
// Schakelaars waarvan de taak nog niet bestaat: aan zetten doet nog niets, en dat staat erbij
const NOT_BUILT = [];

function renderSwitches() {
  const el = $("#switches"), mel = $("#mswitches");
  if (!el) return;
  const sw = hotelNow().switches;
  el.hidden = !sw;
  if (mel) mel.hidden = !sw;
  if (!sw) return;
  const items = [["reservaties", "sw_robot"], ["overschrijvingen", "sw_payout"], ["ontbijt_labels", "sw_breakfast"], ["ontbijtlijst", "sw_blist"], ["kuislijst", "sw_clist"], ["berichten", "sw_messages"]];  // ontgrendelen (deuren via app): pas na Salto
  const html = items.map(([k, label]) => {
    const st = k === "berichten" && sw[k] === "selectie" ? "sel" : sw[k] && sw[k] !== "uit" ? "on" : "off";
    return `<a class="sw ${st}" href="settings.html#hotel" title="${esc(t("sw_go"))}"><span class="d d-${st}"></span>${esc(t(label))} <span class="st">${esc(t("sw_st_" + st))}</span></a>`;
  }).join("");
  el.innerHTML = html;
  if (mel) mel.innerHTML = html;
  // Uitleg bij selectie (zoals in het ontwerp, onder de titel Reservaties)
  if ($("#res-sub")) { $("#res-sub").hidden = sw.berichten !== "selectie"; $("#res-sub").innerHTML = t("res_sel"); }
}

async function refreshSwitches() {
  try { hotelList = await get("/api/monitor/hotels"); } catch (e) { return; }
  renderSwitches();
}

// Lighthouse veranderd: balk bovenaan met wat er aan de hand is en wat te doen; op TST de knop naar PRD
async function loadRepair() {
  const box = $("#repair-banner");
  if (!box) return;
  let s;
  const h = encodeURIComponent($("#hotel").value);
  try { s = await get(`/api/monitor/${h}/repair`); } catch (e) { box.hidden = true; return; }
  const b = s.banner;
  if (!b) { box.hidden = true; return; }
  // Ontwerp (Kop-varianten): rode kader met de oorzaak, de stappen van de herstelling en de knop
  box.className = "repair v2";
  const link = t => esc(t).replace(/(https?:\/\/\S+?)([).,]?)(\s|$)/g, '<a href="$1">$1</a>$2$3');
  const testing = b.level === "blue";
  const stepsHtml = `<div class="steps" aria-label="Status"><span class="${testing ? "done" : "cur"}">${testing ? IC(P.check, 12, 2.6) : ""}${esc(t("rp_search"))}</span><span class="${testing ? "cur" : ""}">${esc(t("rp_test"))}</span><span>${esc(t("rp_solved"))}</span></div>`;
  box.innerHTML = `<span class="ri">${IC(P.warn, 22)}</span><div class="rb"><div class="rt">${link(b.lines[0] || "")}</div>${b.lines.slice(1).map(l => `<div class="small" style="color:#5A2620">${link(l)}</div>`).join("")}${stepsHtml}
    ${b.promote && s.may_promote && !s.can_promote ? `<span class="small" id="promote-msg" style="color:#5A2620">${esc("Kan nu niet: " + (s.why_not || ""))}</span>` : `<span class="small" id="promote-msg"></span>`}</div>
    ${b.promote && s.may_promote ? `<button type="button" class="btn" id="promote" style="background:#7E241D" ${s.can_promote ? "" : "disabled"} title="${esc(s.why_not || "")}">${IC('<path d="M14.5 6.5a4 4 0 0 0 5 5l-9 9a2.1 2.1 0 0 1-3-3l9-9a4 4 0 0 0-2-2z"/><path d="M14.5 6.5L17 4l3 3-2.5 2.5"/>', 16)}Deze versie naar PRD zetten</button>` : ""}`;
  box.hidden = false;
  const btn = $("#promote");
  if (btn) btn.onclick = async () => {
    if (!await ask(`Versie v${s.version} naar PRD zetten? Doe dit alleen als alles op TST klopt.`, { ok: "Naar PRD zetten", danger: true })) return;
    btn.disabled = true;
    let r;
    try { r = await (await apiFetch(`${API}/api/monitor/${h}/repair`, { method: "POST" })).json(); }
    catch (e) { r = { message: String(e.message || e) }; }
    $("#promote-msg").textContent = r.message || "";
  };
}

async function init() {
  document.querySelectorAll("[data-lang]").forEach(b => b.onclick = () => setLang(b.dataset.lang));
  setLang(store("lang") || (navigator.language || "nl").slice(0, 2));
  const hotels = await get("/api/monitor/hotels");
  hotelList = hotels;
  $("#hotel").innerHTML = hotels.map(h => `<option value="${esc(h.id)}">${esc(h.name)}</option>`).join("");
  const saved = store("hotel");
  if (saved && hotels.some(h => h.id === saved)) $("#hotel").value = saved;
  const setLogo = () => { const h = hotelNow(); ["#logo", "#mlogo"].forEach(s => { if ($(s) && h.logo_url) { $(s).src = h.logo_url; $(s).alt = h.name; } }); };
  setLogo();
  $("#hotel").onchange = () => { store("hotel", $("#hotel").value); setLogo(); renderSwitches(); loadRepair(); load(); };
  fetch("/.auth/me").then(r => r.ok ? r.json() : null).then(d => { const u = d && (d.clientPrincipal || (d[0] || {})); if (u && $("#me")) $("#me").textContent = u.userDetails || u.user_id || ""; }).catch(() => {});
  if ($("#m-menu")) $("#m-menu").onclick = () => document.body.classList.toggle("menu-open");
  if ($("#m-hotel")) $("#m-hotel").onclick = () => { document.body.classList.add("menu-open"); $("#hotel").focus(); };
  document.addEventListener("click", e => { if (document.body.classList.contains("menu-open") && !e.target.closest(".side, #m-menu, #m-hotel")) document.body.classList.remove("menu-open"); });
  renderSwitches();
  loadRepair();
  if ($("#version").textContent.includes("__")) $("#version").textContent = "dev";  // lokaal, niet uitgerold
  envSwitch();
  // Twee aparte pagina's: de monitor (index.html: reservaties, gasten) en de instellingen
  // (settings.html: workflow, robot). Elk met eigen tabbladen en eigen adres per tabblad (#...).
  document.querySelectorAll("nav button[data-tab]").forEach(b => b.onclick = () => showTab(b.dataset.tab));
  window.addEventListener("hashchange", () => { const n = location.hash.slice(1); if (TABS.includes(n) && n !== current) showTab(n); });
  showTab(TABS.includes(location.hash.slice(1)) ? location.hash.slice(1) : TABS[0], true);
  if (PAGE === "main") {
    $("#g-search").oninput = () => gFilterChanged(250);
    watchMore("#g-more", () => { if (gNext != null && !gLoading) loadGuestPage(false); });
    // Filter wissen: zoekvak leeg (reservaties: ook terug "vanaf vandaag")
    $("#search-reset").onclick = () => { $("#search").value = ""; $("#from").value = todayIso(); $("#to").value = ""; resFilterChanged(); };
    $("#g-search-reset").onclick = () => { $("#g-search").value = ""; gFilterChanged(); };
    $("#g-update").onclick = updateGuests;
    $("#msgs-close").onclick = () => { $("#msgs").hidden = true; };
    document.querySelectorAll("#g-head th[data-gsort]").forEach(th => th.onclick = () => gSortBy(th.dataset.gsort));
    $("#search").oninput = () => resFilterChanged(250);
    document.querySelectorAll("#res-head th[data-sort]").forEach(th => th.onclick = () => sortBy(th.dataset.sort));
    $("#from").onchange = () => { resPick = null; resFilterChanged(); };
    if ($("#status")) $("#status").onchange = () => resFilterChanged();
    $("#to").onchange = () => { resPick = null; resFilterChanged(); };
    $("#today").onclick = () => { $("#from").value = todayIso(); $("#to").value = ""; resPick = null; resFilterChanged(); };
    watchMore("#res-more", () => { if (resNext != null && !resLoading) loadResPage(false); });
    $("#list-make").onclick = () => makeList(listKind, false);
    $("#list-send").onclick = () => makeList(listKind, true);
    // Menu naast Maken en versturen: alles, alleen WhatsApp, alleen mail of alleen sms (zoals de knop Versturen)
    const mkMenu = $("#list-make-menu"), mkMore = $("#list-send-ch");
    mkMore.onclick = e => { e.stopPropagation(); mkMenu.hidden = !mkMenu.hidden; mkMore.setAttribute("aria-expanded", String(!mkMenu.hidden)); };
    mkMenu.querySelectorAll("[data-make-ch]").forEach(b => b.onclick = () => { mkMenu.hidden = true; makeList(listKind, true, b.dataset.makeCh); });
    document.addEventListener("click", e => { if (!e.target.closest("#list-make-menu, #list-send-ch")) { mkMenu.hidden = true; mkMore.setAttribute("aria-expanded", "false"); } });
    document.querySelectorAll("#list-kind label").forEach(l => l.onclick = e => { e.preventDefault(); showTab(l.dataset.kind); });
  } else {
    document.querySelectorAll("#tab-robot .subtabs button").forEach(b => b.onclick = () => showSub(b.dataset.sub));
    $("#bin-all").innerHTML = BIN;
    $("#bin-all").onclick = deleteAllRuns;
    $("#wf-save").onclick = saveWorkflow;
    $("#hs-save").onclick = saveSettings;
    $("#hs-reset").onclick = resetSettings;
    $("#wf-reset").onclick = resetWorkflow;
    $("#wf-cancel").onclick = () => location.reload();
    $("#pv-close").onclick = () => { $("#preview").hidden = true; };
    $("#task").onchange = () => {
      taskFilter = $("#task").value;
      try { localStorage.setItem("monitor-task", taskFilter); } catch (e) { /* geen opslag */ }
      if (runsData) renderRuns(runsData);
    };
    $("#run").onclick = runRobot;
    // Niet bewaarde wijzigingen in de workflow: waarschuwen bij het verlaten van de pagina
    $("#wa-check").onclick = waCheck;
    $("#wa-defaults").onclick = waUseDefaults;
    $("#wa-all").onclick = waSubmitAll;
    window.addEventListener("beforeunload", e => { if (wfDirty || hsDirty || waDirty()) { e.preventDefault(); e.returnValue = ""; } });
  }
  load();
}

const PAGE = document.body.dataset.page || "main";
// De browser zet de scrollpositie niet terug bij wisselen van tabblad (vorige/volgende): dat doet showTab zelf
if ("scrollRestoration" in history) history.scrollRestoration = "manual";
const TABS = PAGE === "settings" ? ["hotel", "tech", "workflow", "whatsapp", "robot"] : ["today", "res", "guests", "breakfast", "cleaning"];
let current = TABS[0];
function showTab(name, initial = false, leave = false) {
  if (!leave && ((wfDirty && current === "workflow") || (hsDirty && HS_TABS.includes(current)) || (waDirty() && current === "whatsapp")) && name !== current) {
    if (location.hash.slice(1) !== current) history.replaceState(null, "", "#" + current);
    ask(t("wf_leave"), { ok: t("dlg_leave"), danger: true }).then(ok => {
      if (ok) { history.replaceState(null, "", "#" + name); showTab(name, initial, true); }
    });
    return;
  }
  // Ander tabblad: altijd bovenaan beginnen. De scrollpositie onthouden gebeurt alleen bij lijst > detail > terug
  // (detailBack, zet de positie daarna zelf terug).
  if (name !== current && !initial) window.scrollTo(0, 0);
  current = name;
  document.querySelectorAll("nav button[data-tab]").forEach(x => { x.classList.toggle("active", x.dataset.tab === name); x.classList.toggle("on", x.classList.contains("lbtn-lists") ? LIST_KINDS.includes(name) : x.dataset.tab === name); });
  const mt = PAGE === "settings" ? "settings" : LIST_KINDS.includes(name) ? "lists" : name;
  document.querySelectorAll("[data-mtab]").forEach(x => x.classList.toggle("on", x.dataset.mtab === mt));
  document.body.classList.remove("menu-open");
  TABS.forEach(n => { if ($(`#tab-${n}`)) $(`#tab-${n}`).hidden = n !== name; });
  if (HS_TABS.includes(name) && $("#tab-hotel")) {  // Hotel en Technisch: zelfde pagina, elk hun eigen secties
    $("#tab-hotel").hidden = false;
    hsGroup = name === "tech" ? "tech" : "func";
    hsMSec = 0;
    renderSettings();
  }
  if ($("#tab-lists")) { $("#tab-lists").hidden = !LIST_KINDS.includes(name); if (LIST_KINDS.includes(name)) { listKind = name; renderList(name); } }
  if ($("#tab-detail")) $("#tab-detail").hidden = true;
  if (LIST_KINDS.includes(name) && !initial) loadList(name);
  if (name === "today") loadTodayRuns();
  if (name === "whatsapp" && !initial) loadWhatsapp();
  if (name === "guests") { if ($("#tab-guests")) $("#tab-guests").classList.remove("gdet"); loadGuestSync(); }
  if (location.hash.slice(1) !== name) history[initial ? "replaceState" : "pushState"](null, "", "#" + name);
}

// Monitor actueel houden zonder de pagina te herladen: bij terugkeren naar het venster en elke minuut
// (niet terwijl de berichtenpopup open is, zodat een geopende verzendrij niet verdwijnt)
let lastLoad = 0;
async function refreshNow() {
  lastLoad = Date.now();
  await loadReservations();
  await loadGuests(true);
}
function refreshSoon() {
  if (PAGE !== "main" || document.hidden || !$("#msgs").hidden || Date.now() - lastLoad < 15000) return;
  refreshNow().catch(() => {});
}
window.addEventListener("focus", refreshSoon);
document.addEventListener("visibilitychange", refreshSoon);
setInterval(refreshSoon, 60000);

async function load() {
  lastLoad = Date.now();
  if (PAGE === "settings") {
    loadWorkflow();
    loadSettings();
    loadRuns();
    loadWhatsapp();
    return;
  }
  await loadReservations();
  loadGuests();
  loadWorkflow();
  LIST_KINDS.forEach(k => { listData[k] = null; listDay[k] = ""; loadList(k); });  // stappen die al verstuurd kunnen worden (tijdlijn per reservatie)
}

// ---------------------------------------------------------------- berichten per reservatie
// In de lijst kort: per bericht één label (groen als het per alle kanalen lukte, rood als iets
// mislukte). Klik: alle pogingen met kanaal, ontvanger, status en fout.
const CH = { email: "ch_email", whatsapp: "ch_whatsapp", sms: "ch_sms", form: "ch_form", lighthouse: "ch_lighthouse", app: "ch_app" };
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
  const mode = (hotelNow().switches || {}).berichten || "uit";
  $("#msgs-on").checked = !!r.messages_on || (mode === "uit" && r.messages_pick === "on");
  $("#msgs-on-hint").textContent = t("mo_hint_" + mode);
  $("#msgs-on").onchange = async () => {
    const on = $("#msgs-on").checked;
    const d = await get(`/api/monitor/${$("#hotel").value}/select?id=${encodeURIComponent(r.id)}&on=${on ? 1 : 0}`, { method: "POST" }).catch(e => ({ ok: false, error: String(e) }));
    if (!d.ok) { $("#msgs-on").checked = !on; notice(d.error || "?"); return; }
    await ensureRes([id], true);
    render();
    showMessages(id);
  };
  document.getElementById("msgs-nocontact")?.remove();
  $("#msgs-legend").innerHTML = ["sent", "failed", "planned", "missed", "cond", "off"]
    .map(k => `<span class="k-${k}"><span class="dot"></span>${esc(t("lg_" + k))}</span>`).join("");
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

    const chips = [...targets.values()].map(c => {
      const ch = c.channel;
      const tries = mine.filter(m => key(m.channel, m.to) === key(ch, c.to));
      const last = tries[tries.length - 1];
      let cls = "", txt;
      if (last) {
        cls = last.ok ? "ok" : "fail";
        txt = (t("st_" + last.status) || last.status) + (tries.length > 1 ? ` (${tries.length}×)` : "");
      } else if (["sent", "failed", "planned", "due"].includes(p.state)) {
        txt = c.reason ? t("chr_" + c.reason) : t("pl_" + (p.state === "sent" || p.state === "failed" ? "not_tried" : p.state));
        cls = c.reason ? "off" : "todo";
      } else {
        // Niet automatisch (bv. reservatie van voor de start, voorwaarde niet voldaan): wel met de hand te versturen
        txt = c.reason && c.reason !== "fallback" ? t("chr_" + c.reason) : "";
        cls = "off";
      }
      const title = [c.to, last && stamp(last.at), last && last.error, last && last.note].filter(Boolean).join(" · ");
      // Alleen de toestand; (opnieuw) versturen gebeurt met de knop rechts van de stap
      // Kanaal en adres (het adres kort; volledig bij aanwijzen)
      return `<span class="tag ch ${cls}" title="${esc(title)}">${esc(t(CH[ch] || ch))} <span class="addr">${esc(c.to || "")}</span>${txt ? `: ${esc(txt)}` : ""}</span>`;
    }).join("");
    // Kop van de stap op één lijn: naam, datum, toestand, korte reden (volledig bij aanwijzen), rechts de knop Versturen
    const sendable = READY.includes(p.step);
    const k = planKind(p);
    const showReason = p.reason && !["sent", "failed"].includes(k);
    return `<li class="pl-${p.state} k-${k}"><span class="dot"></span>
      <div class="pl-head"><strong>${esc(stepShort(p.step))}</strong>
        <span class="tag pl">${esc(planText(p, when))}</span>
        ${showReason ? `<span class="reason" title="${esc(reasonText(p.reason))}">${esc(reasonShort(p.reason))}</span>` : ""}
        ${["missed", "cond"].includes(k) && when ? `<span class="muted was">(${esc(t("pl_was"))} ${esc(when)})</span>` : ""}
        <span class="sp"></span>
        ${sendable ? `<button type="button" class="secondary small send-open" data-step="${esc(p.step)}">${esc(t(sent.length ? "sb_again" : "sb_open"))}</button>` : ""}</div>
      ${chips ? `<div class="chs">${chips}</div>` : ""}
      ${sendable ? `<div class="send-bar" data-bar="${esc(p.step)}" hidden></div>` : ""}</li>`;
  }).join("");
  $("#msgs-attempts").hidden = !r.messages.length;
  // Geen adres: één keer melden (niet bij elke stap); versturen kan wel via de balk hieronder
  if (!(r.email || r.phone)) $("#msgs-plan").insertAdjacentHTML("beforebegin", `<p class="info" id="msgs-nocontact">${esc(t("rs_no_contact"))}</p>`);
  document.querySelectorAll("#msgs-plan .send-open").forEach(b => b.onclick = () => {
    const bar = document.querySelector(`#msgs-plan [data-bar="${b.dataset.step}"]`);
    bar.hidden = !bar.hidden;
    if (!bar.hidden) sendBar(r, b.dataset.step, bar);
  });
  document.querySelectorAll("#msgs-plan button.resend").forEach(b => b.onclick = async () => {
    const ch = b.dataset.ch, step = stepShort(b.dataset.step), guestTo = b.dataset.to;
    const question = isPrd() ? t("rs_confirm", step, t(CH[ch]), guestTo)
      : testTo(ch) ? t("rs_confirm_test", step, t(CH[ch]), testTo(ch), guestTo) : t("rs_no_test");
    if (!isPrd() && !testTo(ch)) { notice(question); return; }
    if (!await ask(question, { ok: t("dlg_send") })) return;
    b.disabled = true;
    const q = new URLSearchParams({ id: r.id, step: b.dataset.step, channel: b.dataset.ch, to: b.dataset.to });
    const d = await get(`/api/monitor/${$("#hotel").value}/resend?${q}`, { method: "POST" }).catch(e => ({ ok: false, error: String(e) }));
    if (!d.ok) notice(d.error || t("load_error"));
    await load();
    showMessages(r.id);
  });
  $("#msgs-rows").innerHTML = [...r.messages].reverse().map(m => `<tr>
    <td>${stamp(m.at)}</td><td>${esc(stepShort(m.type))}</td><td>${esc(t(CH[m.channel] || m.channel))}</td>
    <td>${toCell(m)}</td><td class="${m.ok ? "ok" : "err"}">${esc(t("st_" + m.status) || m.status)}${m.status_at ? ` <span class="muted">${esc(stamp(m.status_at))}</span>` : ""}</td>
    <td class="wrap">${esc([m.error, m.note].filter(Boolean).join(". "))}</td></tr>`).join("");
  $("#msgs").hidden = false;
}


// ---------------------------------------------------------------- Vandaag (ontwerp: Vandaag, desktop en gsm)
let todayRuns = null;
async function loadTodayRuns() {
  try { todayRuns = await get(`/api/monitor/${$("#hotel").value}/runs`); } catch (e) { todayRuns = null; }
  renderToday();
}
const addDays = (iso, n) => { const [y, m, d] = iso.split("-").map(Number); return new Date(Date.UTC(y, m - 1, d + n)).toISOString().slice(0, 10); };
const yn = (cls, ic, txt) => `<span class="yn ${cls}">${IC(ic, 14, cls === "na" ? 2 : 2.4)}${esc(txt)}</span>`;

function renderToday() {
  const el = $("#tab-today");
  if (!el || !todayIds) return;
  const rows = allRows().filter(r => todayIds.has(r.id));
  const today = todayIso(), tomorrow = addDays(today, 1);
  const live = rows.filter(r => r.status !== "cancelled");
  const arrT = live.filter(r => r.arrival === today), arrM = live.filter(r => r.arrival === tomorrow);
  todayPicks.tomorrow = { label: t("td_arr_tomorrow", dday(tomorrow)), ids: arrM.map(r => r.id) };
  const deps = live.filter(r => r.departure === today), inHouse = live.filter(r => r.arrival <= today && r.departure > today);
  const codeSent = r => r.messages.some(m => m.type === "access_code" && m.ok);
  const codeFailed = r => r.messages.some(m => m.type === "access_code" && !m.ok) && !codeSent(r);
  const unpaid = r => r.paid === false;
  // Mislukt bericht: tot het opnieuw gelukt is, iemand op Negeren klikte of de gast vertrokken is
  const lastFail = r => [...r.messages].filter(m => !m.ok).pop();
  const failedRows = live.filter(r => { const l = msgLast(r), f = lastFail(r); return l && l.failed && f && !f.dismissed_at && r.departure >= today; });
  const labels = r => [(r.pms_labels || []).some(l => /ontbijt|breakfast/i.test(l)) ? `<span class="tag t-bf">Ontbijt</span>` : "", r.stairs ? `<span class="tag t-st">${esc(t("r_stairs"))}</span>` : ""].filter(Boolean).join(" ") || `<span class="muted small">${esc(t("td_none"))}</span>`;
  const gLink = r => `<a class="nm" href="#" data-open="${esc(r.id)}">${esc(r.guest)}</a>${r.guest_stays ? ` <span class="small muted">(${esc(t("r_returning", r.guest_stays))})</span>` : ""}<div class="small muted">#${esc(r.booking_number)}</div>`;
  const room = r => esc(r.rooms.join(" + ") || r.room_type);
  // Vraagt aandacht
  const att = [];
  failedRows.forEach(r => {
    const last = lastFail(r), ch = last.channel === "email" ? "mail" : last.channel === "sms" ? "sms" : "WhatsApp";
    const tech = last.error ? `<details class="tech"><summary>${esc(t("td_a_tech"))}</summary><code>${esc(last.error)}</code></details>` : "";
    att.push(["err", P.warn, t("td_a_failed2", esc(stepShort(last.type)), esc(ch), esc(r.guest), esc(last.to || ""),
      esc(t("pb_" + (last.problem || "other")) || t("pb_other"))) + tech,
      `<span class="row" style="gap:6px;flex:none"><a class="btn sm" href="#" data-open="${esc(r.id)}">${esc(t("td_a_resend"))}</a><button type="button" class="btn2 sm" data-dismiss="${esc(r.id)}">${esc(t("td_a_dismiss"))}</button></span>`]);
  });
  arrT.filter(unpaid).forEach(r => att.push(["warn", P.euro, t("td_a_unpaid", esc(r.guest), r.open_amount ? esc(eur(r.open_amount)) : ""), `<a class="btn2 sm" href="#" data-open="${esc(r.id)}">${esc(t("td_a_open"))}</a>`]));
  const noForm = [...arrT.map(r => [r, "td_today_s"]), ...arrM.map(r => [r, "td_tomorrow_s"])].filter(([r]) => !r.checkin_completed_at);
  todayPicks.noform = { label: t("td_a_form", "").replace(/<[^>]+>/g, "").replace(/[\s:.]+$/, ""), ids: noForm.map(([r]) => r.id) };
  if (noForm.length) att.push(["warn", P.mail, t("td_a_form", noForm.map(([r, w]) => `${esc(r.guest)} (${esc(t(w))})`).join(", ")), `<a class="btn2 sm" href="#res" data-go="res" data-pick="noform">${esc(t("td_a_view"))}</a>`]);
  const bl = listData.breakfast;
  if (bl && bl.switch && !(bl.records || []).some(x => x.day === tomorrow)) att.push(["warn", P.coffee || P.clock, t("td_a_blist", esc(bl.time || "")), `<a class="btn2 sm" href="#breakfast" data-go="breakfast">${esc(t("td_a_make"))}</a>`]);
  if ($("#today-cnt")) { $("#today-cnt").hidden = !failedRows.length; $("#today-cnt").textContent = failedRows.length; }
  const attHtml = att.map(([k, ic, txt, btn]) => `<div class="att ${k}">${IC(ic, 18)}<div class="lt">${txt}</div>${btn}</div>`).join("");
  // Tabellen met aankomsten
  const arrTable = (title, list, isToday) => `<section class="card"><div class="ch"><h2 class="ct">${IC(P.bed)} ${esc(title)}</h2>${isToday ? `<a class="btn3" href="#res" data-go="res">${esc(t("td_all_res"))}</a>` : ""}</div><div class="tbox"><table>
    <thead><tr><th>${esc(t("td_c_guest"))}</th><th>${esc(t("td_c_room"))}</th><th>${esc(t("td_c_form"))}</th><th>${esc(t("td_c_paid"))}</th><th>${esc(t("td_c_code"))}</th><th>${esc(t("td_c_mail"))}</th><th>${esc(t("td_c_labels"))}</th></tr></thead><tbody>
    ${list.map(r => {
      const form = r.checkin_completed_at ? yn("y", P.check, t("td_filled")) : yn("n", P.warn, t("td_notfilled"));
      const paid = r.paid === false ? yn("n", P.warn, t("td_open")) : r.paid ? yn("y", P.check, t("td_paid")) : yn("na", P.clock, "?");
      const code = (r.access_codes || []).length ? yn("y", P.check, t("td_made")) : r.paid === false ? yn("n", P.warn, t("td_waitpay")) : yn("na", P.clock, r.access_valid_from ? dday(r.access_valid_from) : t("td_coming"));
      const mail = codeSent(r) ? yn("y", P.check, t("td_sent")) : codeFailed(r) ? yn("n", P.warn, t("td_notsent")) : r.paid === false ? `<span class="yn na">${esc(t("td_wait"))}</span>` : `<span class="yn na">${esc(t("td_coming"))}</span>`;
      const warn = !r.checkin_completed_at || r.paid === false || codeFailed(r);
      return `<tr data-row-open="${esc(r.id)}" class="${warn ? "warnrow" : ""}${r.id === lastOpened ? " sel" : ""}"><td>${gLink(r)}</td><td>${room(r)}</td><td>${form}</td><td>${paid}</td><td>${code}</td><td>${mail}</td><td>${labels(r)}</td></tr>`;
    }).join("") || `<tr><td colspan="7" class="muted">${esc(t("td_no_arr"))}</td></tr>`}</tbody></table></div></section>`;
  const depCard = `<section class="card"><div class="ch"><h2 class="ct">${IC('<path d="M5 21V4a1 1 0 0 1 1-1h12a1 1 0 0 1 1 1v17"/><path d="M3 21h18"/><circle cx="15" cy="12" r="1"/>')} ${esc(t("td_deps"))}</h2></div><div class="cb">
    ${deps.map(r => `<div class="li"><div class="lt"><a class="nm" href="#" data-open="${esc(r.id)}">${esc(r.guest)}</a> <span class="muted">${esc(t("td_room", r.rooms.join(", ")))}</span>${r.open_amount > 0 ? `<div class="small muted">${esc(t("td_openst_x", eur(r.open_amount)))}</div>` : ""}</div>
      ${r.open_amount > 0 ? `<span class="badge b-warn">${IC(P.warn, 14, 2.4)}${esc(t("td_openst"))}</span>` : (r.room_statuses || []).includes("checkout") ? `<span class="badge b-ok">${IC(P.check, 14, 2.4)}${esc(t("td_left"))}</span>` : ""}</div>`).join("") || `<span class="muted small">${esc(t("td_none"))}</span>`}</div></section>`;
  const guestsIn = inHouse.reduce((n, r) => n + (r.guests || 0), 0), roomsIn = inHouse.reduce((n, r) => n + Math.max(1, r.rooms.length), 0);
  todayPicks.inhouse = { label: t("td_now"), ids: inHouse.map(r => r.id) };
  const nowCard = `<section class="card"><div class="ch"><h2 class="ct">${IC(P.users)} ${esc(t("td_now"))}</h2><span class="small muted">${esc(t("td_nowcount", roomsIn, guestsIn))}</span></div><div class="cb">
    ${inHouse.slice(0, 3).map(r => `<div class="li"><div class="lt"><a class="nm" href="#" data-open="${esc(r.id)}">${esc(r.guest)}</a> <span class="muted">${esc(t("td_room", r.rooms.join(", ")))}${r.guests != null ? ", " + esc(t("r_p", r.guests)) : ""}</span></div><span class="small muted">${esc(t("td_until", dday(r.departure)))}</span></div>`).join("")}
    ${inHouse.length > 3 ? `<a class="btn3" href="#res" data-go="res" data-pick="inhouse" style="padding:0">${esc(t("td_more", inHouse.length - 3))}</a>` : ""}</div></section>`;
  // Rechts: robot, berichten, lijsten, openstaand
  const runs = (todayRuns && todayRuns.runs) || [], lastRun = runs.find(x => x.task === "nieuwe_reservaties") || runs[0];
  const runOk = lastRun ? lastRun.ok !== false : true;  // error bevat ook gewone opmerkingen van een gelukte run
  const robot = `<section class="card"><div class="ch"><h2 class="ct">${IC('<rect x="4" y="8" width="16" height="12" rx="2"/><path d="M12 4v4M9 13v1M15 13v1M9.5 17h5"/><circle cx="12" cy="3.5" r="1"/>')} ${esc(t("td_robot"))}</h2>${lastRun ? `<span class="badge ${runOk ? "b-ok" : "b-err"}">${IC(runOk ? P.check : P.warn, 14, 2.4)}${esc(t(runOk ? "td_robot_ok" : "td_robot_err"))}</span>` : ""}</div><div class="cb">
    ${lastRun ? `<dl class="kv"><dt>${esc(t("td_last"))}</dt><dd>${esc(dtime(lastRun.started_at))}${lastRun.finished_at ? `, ${Math.round((new Date(lastRun.finished_at) - new Date(lastRun.started_at)) / 1000)} s` : ""}</dd><dt>${esc(t("td_result"))}</dt><dd>${esc(lastRun.error || t("td_res_x", lastRun.new || 0, Math.max(0, (lastRun.found || 0) - (lastRun.new || 0))))}</dd></dl>` : ""}
    <div class="row"><button class="btn" type="button" id="td-run" ${todayRuns && todayRuns.can_run && !todayRuns.running ? "" : "disabled"}>${IC('<path d="M7 4.5v15l12-7.5z"/>', 14)}${esc(t("td_run"))}</button><a class="btn3" href="settings.html#robot">${esc(t("td_log"))}</a></div></div></section>`;
  const dueToday = live.flatMap(r => (r.plan || []).filter(p => (p.state === "planned" || p.state === "due") && p.due && p.due.slice(0, 10) === today).map(p => ({ r, p }))).sort((a, b) => a.p.due.localeCompare(b.p.due));
  todayPicks.msgs = { label: t("td_msgs_today", dueToday.length), ids: [...new Set(dueToday.map(({ r }) => r.id))] };
  const msgs = `<section class="card"><div class="ch"><h2 class="ct">${IC(P.mail)} ${esc(t("td_msgs"))}</h2></div><div class="cb">
    ${failedRows.length ? `<div class="att err" style="padding:8px 10px">${IC(P.warn, 16)}<div class="lt">${t("td_msgs_failed", failedRows.length, failedRows.slice(0, 2).map(r => esc(stepShort(msgLast(r) && [...r.messages].filter(m => !m.ok).pop().type) + " " + r.guest)).join(", "))}</div></div>` : ""}
    <div class="lbl" style="margin-top:4px">${esc(t("td_msgs_today", dueToday.length))}</div>
    ${dueToday.slice(0, 4).map(({ r, p }) => `<div class="li"><div class="lt small"><b>${esc(stepShort(p.step))}</b> ${esc(r.guest)}</div><span class="small muted mono">${esc(p.due.length > 10 ? new Date(p.due).toLocaleTimeString(locale(), { hour: "2-digit", minute: "2-digit" }) : "")}</span></div>`).join("")}
    ${dueToday.length > 4 ? `<a class="btn3" href="#res" data-go="res" data-pick="msgs" style="padding:0">${esc(t("td_more", dueToday.length - 4))}</a>` : ""}</div></section>`;
  const lrow = (kind, day, when) => {
    const d = listData[kind], x = d && (d.records || []).find(r => r.day === day);
    const name = t(kind === "breakfast" ? "td_bl" : "td_cl_today");
    if (x) return `<div class="li"><div class="lt"><b>${esc(name)}</b> ${esc(t(when))}<div class="small muted">${esc(t("td_l_made", dtime(x.generated_at), x.sent && x.sent.length ? ", " + t("td_l_sent").toLowerCase() : ""))}</div></div>${x.sent && x.sent.length ? `<span class="badge b-ok">${IC(P.check, 14, 2.4)}${esc(t("td_l_sent"))}</span>` : `<span class="badge b-info">${esc(t("td_l_made_b"))}</span>`}</div>`;
    return `<div class="li"><div class="lt"><b>${esc(name)}</b> ${esc(t(when))}<div class="small muted">${esc(d ? t("td_l_auto", d.time) : "")}</div></div><span class="badge b-wait">${IC(P.clock, 14, 2.4)}${esc(t("td_l_notyet"))}</span></div>`;
  };
  const lists = `<section class="card"><div class="ch"><h2 class="ct">${IC('<rect x="5" y="4" width="14" height="17" rx="2"/><path d="M9 4V3h6v1M8.5 10h7M8.5 14h7M8.5 18h4"/>')} ${esc(t("td_lists"))}</h2></div><div class="cb">
    ${lrow("cleaning", today, "td_l_today")}${lrow("breakfast", today, "td_l_today")}${lrow("breakfast", tomorrow, "td_l_tomorrow")}
    <div class="row"><a class="btn2 sm" href="#breakfast" data-go="breakfast">${IC(P.eye, 15)}${esc(t("td_a_view"))}</a></div></div></section>`;
  const soon = live.filter(r => r.open_amount > 0 && r.arrival >= today && r.arrival <= addDays(today, 7)).sort((a, b) => a.arrival.localeCompare(b.arrival));
  const openCard = `<section class="card"><div class="ch"><h2 class="ct">${IC(P.euro)} ${esc(t("td_open_soon"))}</h2></div><div class="cb">
    ${soon.slice(0, 5).map(r => `<div class="li"><div class="lt"><a class="nm" href="#" data-open="${esc(r.id)}">${esc(r.guest)}</a><div class="small muted">${esc(r.arrival === today ? t("td_today_s") : r.arrival === tomorrow ? t("td_tomorrow_s") : dday(r.arrival))}, ${esc(r.paid === false ? t("td_room", r.rooms.join(", ")) : t("td_tax"))}</div></div><b class="mono">${esc(eur(r.open_amount))}</b></div>`).join("") || `<span class="muted small">${esc(t("td_none"))}</span>`}</div></section>`;
  const now = new Date();
  const dateLong = now.toLocaleDateString(locale(), { weekday: "long", day: "numeric", month: "long", year: "numeric" });
  const upd = lastLoad ? new Date(lastLoad).toLocaleTimeString(locale(), { hour: "2-digit", minute: "2-digit" }) : "";
  const kpi = (n, l, cls = "") => `<div class="stat ${cls}"><span class="n"${cls === "err" ? ' style="color:#8B2E2E"' : ""}>${n}</span><span class="l">${esc(l)}</span></div>`;
  const mStatus = r => !r.checkin_completed_at ? `<span class="badge b-warn">${IC(P.warn, 14, 2.4)}${esc(t("td_miss_form"))}</span>` : r.paid === false ? `<span class="badge b-warn">${IC(P.warn, 14, 2.4)}${esc(t("td_miss_pay"))}</span>` : codeFailed(r) ? `<span class="badge b-warn">${IC(P.warn, 14, 2.4)}${esc(t("td_miss_code"))}</span>` : `<span class="badge b-ok">${IC(P.check, 14, 2.4)}${esc(t("td_ok"))}</span>`;
  el.innerHTML = `
    <div class="d-only" style="display:contents">
    <div class="ph"><div><h1>${esc(t("nav_today"))}</h1><div class="sub">${esc(t("td_update", dateLong, upd))}</div></div></div>
    <div class="statgrid">${kpi(arrT.length, t("td_arr"))}${kpi(arrM.length, t("td_arr_tom"))}${kpi(deps.length, t("td_dep"))}${kpi(guestsIn, t("td_inhouse", roomsIn))}${kpi(failedRows.length, t("td_failed"), failedRows.length ? "err" : "")}</div>
    <section class="card"><div class="ch"><h2 class="ct">${IC('<path d="M5 21V4M5 4h11l-2 4 2 4H5"/>')} ${esc(t("td_attn"))}</h2><span class="small muted">${esc(t("td_points", att.length))}</span></div><div class="cb" style="gap:8px">${attHtml || `<span class="muted small">${esc(t("td_none_attn"))}</span>`}</div></section>
    <div class="cols"><div class="col-main">${arrTable(t("td_arr_today", dday(today)), arrT, true)}${arrTable(t("td_arr_tomorrow", dday(tomorrow)), arrM, false)}<div class="grid2">${depCard}${nowCard}</div></div>
      <div class="col-side">${robot}${msgs}${lists}${openCard}</div></div>
    </div>
    <div class="m-only" style="display:flex;flex-direction:column;gap:14px">
      <div><div class="mh1">${esc(t("nav_today"))}</div><div class="small muted">${esc(dday(today))} ${today.slice(0, 4)}, update ${esc(upd)}</div></div>
      ${att.slice(0, 2).map(([k, ic, txt, btn]) => `<div class="att ${k}" style="flex-wrap:wrap">${IC(ic, 18)}<div class="lt">${txt}</div>${btn.replace('class="btn sm"', 'class="btn sm" style="width:100%"')}</div>`).join("")}
      <div class="statgrid" style="grid-template-columns:repeat(3,minmax(0,1fr));gap:8px">${kpi(arrT.length, t("td_arrivals_m"))}${kpi(deps.length, t("td_deps_m"))}${kpi(guestsIn, t("td_inhouse_m"))}</div>
      <section class="mcard"><div class="ct">${esc(t("td_arr_today", "").replace(/,\s*$/, ""))}</div>${arrT.map(r => `<a href="#" class="li" data-open="${esc(r.id)}" style="text-decoration:none;color:#2B2F38"><div class="lt"><b>${esc(r.guest)}</b> <span class="muted">${esc(t("td_room", r.rooms.join(" + ")))}</span><div class="row" style="gap:4px;margin-top:4px">${mStatus(r)} ${labels(r)}</div></div>${ICO.chev}</a>`).join("") || `<span class="muted small">${esc(t("td_no_arr"))}</span>`}</section>
      <section class="mcard"><div class="ct">${esc(t("td_arr_tomorrow", dday(tomorrow)))}</div><a href="#res" data-go="res" data-pick="tomorrow" class="li" style="text-decoration:none;color:#2B2F38"><div class="lt"><b>${esc(t("td_tomorrow_n", arrM.length))}</b><div class="small muted">${esc(t("td_tomorrow_open", arrM.filter(r => !r.checkin_completed_at).length, arrM.filter(unpaid).length))}</div></div>${ICO.chev}</a></section>
      ${robot.replace('class="card"', 'class="mcard"')}
      ${lists.replace('class="card"', 'class="mcard"')}
    </div>`;
  el.querySelectorAll("[data-open]").forEach(a => a.onclick = e => { e.preventDefault(); openDetail(a.dataset.open); });
  el.querySelectorAll("[data-go]").forEach(a => a.onclick = e => {
    e.preventDefault();
    // "en nog 7", "Bekijken": precies de reservaties waarover het gaat, niet de hele lijst
    resPick = a.dataset.pick && todayPicks[a.dataset.pick] ? { ...todayPicks[a.dataset.pick], ids: new Set(todayPicks[a.dataset.pick].ids) } : null;
    if (resPick) clearResFilters();
    showTab(a.dataset.go);
    if (a.dataset.go === "res") loadResPage(true);
  });
  el.querySelectorAll("#td-run").forEach(b => b.onclick = async () => {
    b.disabled = true;
    await apiFetch(`${API}/api/monitor/${$("#hotel").value}/run`, { method: "POST" }).catch(() => null);
    setTimeout(loadTodayRuns, 5000);
  });
}

// ---------------------------------------------------------------- detail van een reservatie (ontwerp: Reservatie detail)
const IC = (d, n = 15, w = 2) => `<svg width="${n}" height="${n}" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="${w}" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">${d}</svg>`;
const P = {
  back: '<path d="M15 6l-6 6 6 6"/>', ext: '<path d="M14 4h6v6M20 4l-9 9"/><path d="M18 14v5a1 1 0 0 1-1 1H5a1 1 0 0 1-1-1V7a1 1 0 0 1 1-1h5"/>',
  eye: '<path d="M2 12s3.5-7 10-7 10 7 10 7-3.5 7-10 7S2 12 2 12z"/><circle cx="12" cy="12" r="3"/>',
  users: '<circle cx="9" cy="8" r="3.5"/><path d="M2.5 20a6.5 6.5 0 0 1 13 0"/><path d="M16 4.5a3.5 3.5 0 0 1 0 7M18 14.5a6.5 6.5 0 0 1 3.5 5.5"/>',
  mail: '<rect x="3" y="5" width="18" height="14" rx="2"/><path d="M3.5 6.5l8.5 6.5 8.5-6.5"/>', check: '<path d="M5 12.5l4.5 4.5L19 7.5"/>',
  warn: '<path d="M12 3.5l9.5 16.5h-19z"/><path d="M12 10v4.5M12 17.5v.5"/>', clock: '<circle cx="12" cy="12" r="9"/><path d="M12 7v5l3 2"/>',
  x: '<path d="M6 6l12 12M18 6L6 18"/>', dots: '<circle cx="5" cy="12" r="1.2"/><circle cx="12" cy="12" r="1.2"/><circle cx="19" cy="12" r="1.2"/>',
  send: '<path d="M21 3L10 14"/><path d="M21 3l-7 18-4-7-7-4z"/>', wa: '<path d="M21 12a8 8 0 0 1-11.6 7.1L4 20.5l1.4-5A8 8 0 1 1 21 12z"/>',
  phone: '<path d="M5 4h4l2 5-2.5 1.5a11 11 0 0 0 5 5L15 13l5 2v4a2 2 0 0 1-2 2A16 16 0 0 1 3 6a2 2 0 0 1 2-2z"/>',
  key: '<circle cx="8" cy="15" r="4"/><path d="M11 12l9-9M17 6l3 3M14 9l2 2"/>', euro: '<path d="M17 6.5A7 7 0 1 0 17 17.5"/><path d="M4 10h9M4 14h9"/>',
  card: '<rect x="3" y="6" width="18" height="13" rx="2"/><path d="M3 10h18M7 15h4"/>', plus: '<path d="M12 5v14M5 12h14"/>',
  bed: '<path d="M3 18V7"/><path d="M21 18v-5a3 3 0 0 0-3-3h-8v6"/><path d="M3 15h18"/><circle cx="6.5" cy="11" r="1.5"/>',
  coffee: '<path d="M4 9h13v5a5 5 0 0 1-5 5H9a5 5 0 0 1-5-5z"/><path d="M17 10h1.5a2.5 2.5 0 0 1 0 5H17"/><path d="M8 3v3M12 3v3"/>',
};
const chIcon = ch => IC(ch === "email" ? P.mail : ch === "whatsapp" ? P.wa : P.phone, 13);
const eur = x => x == null ? "" : "EUR " + Number(x).toLocaleString("nl-BE", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
let detailId = "", detailFilter = "";
// Onder de pincodes: wanneer gemaakt bij Salto en wanneer in Lighthouse gezet (als dat bewaard is)
function pinsNote(r) {
  const made = (r.access_codes || []).map(c => c.created_at).filter(Boolean).sort()[0];
  if (made) return r.pms_codes_at ? t("d_pins_when_pms", dtime(made), dtime(r.pms_codes_at)) : r.codes_in_pms ? t("d_pins_when", dtime(made)) + " " + t("d_pins_in_pms") : t("d_pins_when", dtime(made));
  return t(r.codes_in_pms ? "d_pins_pms" : "d_pins_salto");
}

// Terug naar waar je vandaan kwam (lijst, Vandaag, Gasten): zelfde scrollpositie, de reservatie gemarkeerd
let detailBack = null;  // { tab, scroll, id }
let lastOpened = "";    // laatst geopende reservatie: rij blijft gemarkeerd in de lijsten
function goBackFromDetail() {
  const b = detailBack || { tab: "res", scroll: 0 };
  $("#tab-detail").hidden = true;
  showTab(b.tab);
  markOpened();
  requestAnimationFrame(() => requestAnimationFrame(() => window.scrollTo(0, b.scroll || 0)));
}
// Rij van de laatst geopende reservatie markeren (lijst Reservaties en de tabellen op Vandaag)
function markOpened() {
  document.querySelectorAll("tr[data-row-open]").forEach(tr => tr.classList.toggle("sel", tr.dataset.rowOpen === lastOpened));
}
// Negeren (Vandaag): mislukte berichten van die reservatie niet meer als aandachtspunt tonen
document.addEventListener("click", async e => {
  const b = e.target.closest("[data-dismiss]");
  if (!b) return;
  e.preventDefault();
  b.disabled = true;
  try {
    await get(`/api/monitor/${encodeURIComponent($("#hotel").value)}/dismiss?id=${encodeURIComponent(b.dataset.dismiss)}`, { method: "POST" });
    await ensureRes([b.dataset.dismiss], true);
    renderToday();
  } catch (err) { b.disabled = false; notice(String(err.message || err)); }
});
// Hele rij klikbaar: overal waar een rij data-row-open heeft (behalve op een link, knop of veld in de rij)
document.addEventListener("click", e => {
  const tr = e.target.closest("tr[data-row-open]");
  if (!tr || e.target.closest("a, button, input, select, textarea, label")) return;
  openDetail(tr.dataset.rowOpen);
});

function openDetail(id) {
  const visibleTab = !$("#tab-detail").hidden ? (detailBack && detailBack.tab) : current;
  if ($("#tab-detail").hidden) detailBack = { tab: visibleTab || "res", scroll: window.scrollY, id };
  lastOpened = id;
  detailId = id;
  TABS.forEach(n => { if ($(`#tab-${n}`)) $(`#tab-${n}`).hidden = true; });
  if ($("#tab-lists")) $("#tab-lists").hidden = true;
  $("#tab-detail").hidden = false;
  document.querySelectorAll("nav button[data-tab]").forEach(x => x.classList.toggle("on", x.dataset.tab === "res"));
  document.querySelectorAll("[data-mtab]").forEach(x => x.classList.toggle("on", x.dataset.mtab === "res"));
  renderDetail();
  if (!resById(id)) ensureRes([id]).then(renderDetail).catch(() => {});
  window.scrollTo(0, 0);
}

function renderDetail() {
  const r = rows.find(x => x.id === detailId), el = $("#tab-detail");
  if (!r || el.hidden) return;
  const mode = (hotelNow().switches || {}).berichten || "uit";
  const n = nights(r);
  const sub = [`${dday(r.arrival)} ${t("stay_to")} ${dday(r.departure)} ${r.departure.slice(0, 4)} (${t("d_nights", n)})`,
    r.rooms.length ? t("d_rooms", r.rooms.join(` ${t("d_and")} `)) : r.room_type, r.guests != null ? t("d_persons", r.guests) : "",
    [r.source, t("r_flow", t("flow_" + r.flow) || r.flow)].filter(Boolean).join(", "), r.rate_plan].filter(Boolean).join(" · ");
  const acts = [r.lighthouse_url && `<a class="btn2" href="${esc(r.lighthouse_url)}" target="_blank" rel="noopener">${IC(P.ext)}${esc(t("d_open_lh"))}</a>`,
    r.app_link && `<a class="btn2" href="${esc(r.app_link)}" target="_blank" rel="noopener">${IC(P.eye)}${esc(t("d_app"))}</a>`,
    r.guest_id && guestById(r.guest_id) && `<a class="btn2" href="#" id="d-guest">${IC(P.users)}${esc(t("d_profile"))}</a>`].filter(Boolean).join("");
  // Tijdlijn: elke stap uit de planning met de kanalen en de laatste poging per kanaal
  const KIND = { sent: ["c-ok", "b-ok", P.check, "d_sent"], failed: ["c-err", "b-err", P.x, "d_failed"], due: ["c-wait", "b-wait", P.clock, "d_planned"],
    planned: ["c-wait", "b-wait", P.clock, "d_planned"], missed: ["c-cond", "b-warn", P.dots, "d_missed"], cond: ["c-cond", "b-warn", P.dots, "d_cond"], off: ["c-off", "b-no", P.dots, "d_off"] };
  const steps = (r.plan || []).map((p, i, all) => {
    const k = planKind(p), [cc, bc, ic, label] = KIND[k] || KIND.off;
    const mine = r.messages.filter(m => m.type === p.step), sent = mine.filter(m => m.ok);
    const when = p.state === "sent" && sent.length ? dtime(sent[0].at) : p.due ? (p.due.length > 10 ? dtime(p.due) : dshort(p.due)) : "";
    const key = (ch, to) => ch + "|" + (to || "").toLowerCase(), targets = new Map();
    (p.channels || []).forEach(c => targets.set(key(c.channel, c.to), c));
    mine.forEach(m => { if (!targets.has(key(m.channel, m.to))) targets.set(key(m.channel, m.to), { channel: m.channel, to: m.to, reason: "" }); });
    const chips = [...targets.values()].map(c => {
      const tries = mine.filter(m => key(m.channel, m.to) === key(c.channel, c.to)), last = tries[tries.length - 1];
      let cls = "wait", txt;
      if (last) { cls = last.ok ? "ok" : "err"; txt = t("st_" + last.status) || last.status; }
      else if (["sent", "failed", "planned", "due"].includes(p.state)) txt = c.reason ? t("chr_" + c.reason) : t("pl_" + (p.state === "sent" || p.state === "failed" ? "not_tried" : "planned"));
      else txt = c.reason && c.reason !== "fallback" ? t("chr_" + c.reason) : "";
      return `<span class="chip ${cls}" title="${esc([last && stamp(last.at), last && last.error].filter(Boolean).join(" · "))}">${chIcon(c.channel)}${esc(t(CH[c.channel] || c.channel))}${c.to ? " · " + esc(c.to) : ""}${txt ? ` · <b>${esc(txt)}</b>` : ""}</span>`;
    }).join("");
    const err = mine.filter(m => !m.ok && (m.error || m.note)).pop();
    const sendable = READY.includes(p.step);
    const why = p.reason && !["sent", "failed"].includes(k) ? reasonText(p.reason) : "";
    return `<div class="tls"><div class="tm"><span class="c ${cc}">${IC(ic, 15, 2.6)}</span>${i < all.length - 1 ? '<span class="ln"></span>' : ""}</div>
      <div class="tb${k === "failed" ? " err" : ""}"><div class="th"><span class="tn">${esc(stepShort(p.step))}</span><span class="badge ${bc}">${esc(t(label))}</span><span class="small muted">${esc(when)}</span>
        ${sendable ? `<button class="btn2 sm d-send" type="button" data-step="${esc(p.step)}" style="margin-left:auto">${IC(P.send, 14)}${esc(t(sent.length ? "d_again" : "d_now"))}</button>` : ""}</div>
        ${why ? `<div class="small muted">${esc(why)}</div>` : ""}
        ${chips ? `<div class="row" style="gap:6px">${chips}</div>` : ""}
        ${err ? `<div class="small" style="color:#7E241D">${esc([err.error, err.note].filter(Boolean).join(". "))}</div>` : ""}
        ${sendable ? `<div class="pop" data-pop="${esc(p.step)}" hidden><div class="lbl">${esc(t(sent.length ? "d_again" : "d_now"))}</div><div class="send-bar" data-bar="${esc(p.step)}"></div><div class="row"><button class="btn3 d-cancel" type="button">${esc(t("d_cancel"))}</button></div></div>` : ""}
      </div></div>`;
  }).join("");
  const legend = ["sent", "failed", "planned", "missed", "cond", "off"].map(k => { const [, bc, ic, label] = KIND[k]; return `<span class="badge ${bc}">${k === "cond" || k === "off" ? "" : IC(ic, 14, 2.4)}${esc(t(label))}</span>`; }).join("");
  // Alle pogingen en gebeurtenissen: berichten uit het log, plus wat er met de reservatie gebeurde (tijdstippen die bewaard worden)
  const EVTYPES = ["checkin_form", "incoming", "app_unlock", "app_pay", "booking_payout", "pay_request", "pms_sync", "room_change"];
  const items = r.messages.map(m => {
    const ev = EVTYPES.includes(m.type);
    return { at: m.at, kind: ev ? "event" : "msg", what: m.type === "incoming" ? t("ev_reply") : ev ? t("ev_event") : stepShort(m.type),
      detail: ev ? [stepShort(m.type), m.note].filter(Boolean).join(": ") : t(CH[m.channel] || m.channel), to: ev && m.type !== "incoming" ? "" : toCell(m),
      badge: m.type === "incoming" ? ["b-info", t("ev_recv")] : [m.ok ? "b-ok" : "b-err", t("st_" + m.status) || m.status], err: [m.error, ev ? "" : m.note].filter(Boolean).join(". ") };
  });
  const ev = (at, text, lh = true) => { if (at) items.push({ at, kind: "event", what: t("ev_event"), detail: text, to: "", badge: lh ? ["b-info", t("ev_lh")] : ["b-ok", t("ev_ok")], err: "" }); };
  ev(r.booked_at, t("ev_booked"));
  ev(r.added_at, t("ev_added"), false);
  ev(r.contact_checked_at, t("ev_contact"));
  if (!r.messages.some(m => m.type === "checkin_form")) ev(r.checkin_completed_at, t("ev_form"), false);
  ev(r.payout_registered_at, `${t("ev_payout")}${r.folio_total != null ? ` (${eur(r.folio_total)})` : ""}`, false);
  ev(r.pay_requested_at, t("ev_payreq"), false);
  ev(r.breakfast_labeled_at, t("ev_bf"), false);
  ev(r.stairs_memo_at, t("ev_stairs"), false);
  ev(r.stairs_label_at, t("ev_stairs_lbl"), false);
  const vis = r.visit;
  if (vis) {
    ev(vis.first_at, t("ev_visit_first"), false);
    if (vis.last_at && vis.last_at !== vis.first_at) ev(vis.last_at, t("ev_visit_last", vis.count), false);
    ev(vis.codes_first_at, t("ev_codes_seen"), false);
  }
  (r.room_moves || []).forEach(m => ev(m.at, t("ev_move", [].concat(m.to || []).join(" + "), [].concat(m.from || []).join(" + "))));
  // Pincodes: per tijdstip (minuut) samen, met de kamers erbij
  const byMin = {};
  (r.access_codes || []).filter(c => c.created_at).forEach(c => { (byMin[c.created_at.slice(0, 16)] = byMin[c.created_at.slice(0, 16)] || { at: c.created_at, rooms: [] }).rooms.push(c.room); });
  Object.values(byMin).forEach(x => ev(x.at, `${t("ev_codes")} (${x.rooms.join(", ")})`, false));
  ev(r.pms_codes_at, t("ev_codes_lh"), false);
  items.sort((a, b) => String(b.at).localeCompare(String(a.at)));
  const shownItems = items.filter(x => !detailFilter || x.kind === detailFilter);
  const attempts = shownItems.map(x => `<tr><td class="mono small">${esc(dtime(x.at))}</td><td><b>${esc(x.what)}</b></td><td>${esc(x.detail)}</td>
    <td class="small">${x.to}</td><td><span class="badge ${x.badge[0]}">${esc(x.badge[1])}</span></td><td class="small" style="color:#8B2E2E">${esc(x.err)}</td></tr>`).join("");
  // Rechts: pincodes, betaling, contact, gegevens
  const codes = r.access_codes || [];
  const pins = codes.length ? `<section class="card"><div class="ch"><h2 class="ct">${IC(P.key)} ${esc(t("d_pins"))}</h2><span class="badge b-ok">${IC(P.check, 14, 2.4)}${esc(t("d_made"))}</span></div><div class="cb">
    ${codes.map((c, i) => `<div class="li"><div class="lt"><b>${esc(/^\d+$/.test(c.room) ? t("r_room", c.room) : !c.room || /voordeur|front|door/i.test(c.room) ? t("d_door") : c.room)}</b>${i === 0 && r.access_valid_from ? `<div class="small muted">${esc(t("d_valid", dtime(r.access_valid_from), dtime(r.access_valid_until)))}</div>` : ""}</div><span class="code">${esc(c.pin)}<span class="enter">&#8629;</span></span></div>`).join("")}
    <div class="small" style="margin-top:6px">${r.visit && r.visit.codes_first_at
      ? `<span class="badge b-ok">${IC(P.eye, 14, 2.4)}${esc(t("d_seen", dtime(r.visit.codes_first_at), r.visit.codes_last_at !== r.visit.codes_first_at ? dtime(r.visit.codes_last_at) : ""))}</span>`
      : `<span class="badge b-no">${esc(t("d_not_seen"))}</span>`}</div>
    <div class="small muted">${esc(pinsNote(r))}</div></div></section>` : "";
  const open = r.open_amount != null && r.open_amount > 0;
  const roomPay = r.payout_registered_at ? t("d_paid_payout", dshort(r.payout_registered_at)) : r.paid === true ? t("d_paid") : r.paid === false ? t("d_unpaid") : t("d_unknown");
  const pay = `<section class="card"><div class="ch"><h2 class="ct">${IC(P.euro)} ${esc(t("d_pay"))}</h2>${open ? `<span class="badge b-warn">${IC(P.warn, 14, 2.4)}${esc(t("d_open"))}</span>` : r.paid ? `<span class="badge b-ok">${IC(P.check, 14, 2.4)}${esc(t("d_paid"))}</span>` : ""}</div><div class="cb">
    <dl class="kv"><dt>${esc(t("d_rooms_lbl"))}</dt><dd>${esc(roomPay)}</dd>${(r.folio || []).filter(l => /toerist|city|tax/i.test(l.label || "")).map(l => `<dt>${esc(l.label)}</dt><dd>${esc(eur(l.amount))}</dd>`).join("")}
    ${r.folio_total != null ? `<dt>${esc(t("d_total"))}</dt><dd>${esc(eur(r.folio_total))}</dd>` : ""}<dt>${esc(t("d_open_lbl"))}</dt><dd>${esc(r.open_amount != null ? eur(r.open_amount) : "-")}</dd></dl>
    ${r.pay_link ? `<div class="row"><a class="btn2 sm" href="${esc(r.pay_link)}" target="_blank" rel="noopener">${IC(P.card, 14)}${esc(t("d_payreq"))}</a></div>` : ""}
    ${r.pay_requested_at ? `<div class="small muted">${esc(t("d_payreq_at", dtime(r.pay_requested_at)))}</div>` : ""}</div></section>`;
  const cl = [];
  const addC = (v, ic, src) => { if (v && !cl.some(x => x.v.toLowerCase() === v.toLowerCase())) cl.push({ v, ic, src }); };
  addC(r.email, P.mail, r.email_platform || (r.checkin_completed_at ? t("src_form") : "Lighthouse"));
  addC(r.backup_email, P.mail, t("src_form_extra"));
  addC(r.relay_email, P.mail, `${t("src_relay")}${r.relay_platform ? " " + r.relay_platform : ""}`);
  addC(r.phone, P.phone, r.checkin_completed_at ? t("src_form") : "Lighthouse");
  addC(r.backup_phone, P.phone, t("src_form_extra"));
  const contact = `<section class="card"><div class="ch"><h2 class="ct">${IC(P.phone)} ${esc(t("d_contact"))}</h2></div><div class="cb">
    ${cl.map(c => `<div class="li">${IC(c.ic, 16)}<div class="lt"><b>${esc(c.v)}</b><div class="small muted">${esc(t("d_src", c.src))}</div></div></div>`).join("")}
    <button class="btn2 sm" type="button" id="d-add" style="align-self:flex-start">${IC(P.plus, 14)}${esc(t("d_add"))}</button>
    <div id="d-add-form" class="pop" hidden><div class="field"><input id="d-add-v" class="input" placeholder="${esc(t("d_add_ph"))}"></div><div class="row"><button class="btn sm" type="button" id="d-add-go">${esc(t("d_add"))}</button><button class="btn3" type="button" id="d-add-x">${esc(t("d_cancel"))}</button><span id="d-add-err" class="small" style="color:#8B2E2E"></span></div></div></div></section>`;
  const data = `<section class="card"><div class="ch"><h2 class="ct">${IC(P.bed)} ${esc(t("d_data"))}</h2></div><div class="cb"><dl class="kv">
    <dt>${esc(t("d_k_chan"))}</dt><dd>${esc(r.source)}</dd><dt>${esc(t("d_k_flow"))}</dt><dd>${esc(t("flow_" + r.flow) || r.flow)}</dd>
    <dt>${esc(t("d_k_rate"))}</dt><dd>${esc(r.rate_plan)}${r.non_refundable != null ? ` (${esc(t(r.non_refundable ? "d_nrf" : "d_flex"))})` : ""}</dd>
    <dt>Lighthouse</dt><dd>${esc(r.pms_status)}</dd><dt>${esc(t("d_k_booked"))}</dt><dd>${esc(r.booked_at ? dlong(r.booked_at.slice(0, 10)) + " " + r.booked_at.slice(11, 16) : "")}</dd>
    <dt>${esc(t("d_k_added"))}</dt><dd>${esc(r.added_at ? dlong(r.added_at.slice(0, 10)) + " " + new Date(r.added_at).toLocaleTimeString(locale(), { hour: "2-digit", minute: "2-digit" }) : "")}</dd>
    <dt>${esc(t("d_k_updated"))}</dt><dd>${esc(r.updated_at ? dlong(r.updated_at.slice(0, 10)) + " " + new Date(r.updated_at).toLocaleTimeString(locale(), { hour: "2-digit", minute: "2-digit" }) : "")}</dd></dl></div></section>`;
  const tagsBf = (r.pms_labels || []).some(l => /ontbijt|breakfast/i.test(l)) ? ` <span class="tag t-bf">Ontbijt</span>` : "";
  const checked = !!r.messages_on || (mode === "uit" && r.messages_pick === "on");
  const backTab = (detailBack && detailBack.tab) || "res";
  el.innerHTML = `<a class="btn3" href="#${esc(backTab)}" id="d-back" style="padding:0;align-self:flex-start">${IC(P.back, 16)}${esc(backTab === "res" ? t("d_back") : t("nav_" + backTab) || t("d_back"))}</a>
    <div class="ph"><div><h1>${esc(r.guest)}${r.booking_number ? ` <span class="muted" style="font-weight:400;font-size:20px">#${esc(r.booking_number)}</span>` : ""}</h1><div class="sub">${esc(sub)}</div>
      <div class="row" style="margin-top:8px;gap:6px">${resTags(r)}${tagsBf}</div></div><div class="acts">${acts}</div></div>
    <div class="cols"><div class="col-main">
      <section class="card"><div class="cb" style="padding-top:16px"><div class="toggle" style="padding:0"><div class="tx"><label class="tn" for="d-auto">${esc(t("d_auto"))}</label><div class="help">${esc(t("mo_hint_" + mode))}${mode !== "uit" ? esc(t("d_auto_off")) : ""}</div></div><input id="d-auto" class="switch" type="checkbox" ${checked ? "checked" : ""}></div></div></section>
      <section class="card"><div class="ch"><h2 class="ct">${IC(P.mail)} ${esc(t("d_timeline"))}</h2><div class="legend">${legend}</div></div><div class="cb"><div class="tl">${steps}</div></div></section>
      ${items.length ? `<section class="card"><div class="ch"><h2 class="ct">${IC(P.clock)} ${esc(t("d_attempts"))}</h2><select id="d-filter" class="select" style="width:auto" aria-label="Filter"><option value="">${esc(t("ev_all"))}</option><option value="msg" ${detailFilter === "msg" ? "selected" : ""}>${esc(t("ev_msgs"))}</option><option value="event" ${detailFilter === "event" ? "selected" : ""}>${esc(t("ev_events"))}</option></select></div><div class="tbox"><table><thead><tr><th>${esc(t("d_time"))}</th><th>${esc(t("d_msg"))}</th><th>${esc(t("d_chan"))}</th><th>${esc(t("d_to"))}</th><th>${esc(t("d_status"))}</th><th>${esc(t("d_err"))}</th></tr></thead><tbody>${attempts}</tbody></table></div></section>` : ""}
    </div><div class="col-side">${pins}${pay}${contact}${data}</div></div>`;
  if ($("#d-filter")) $("#d-filter").onchange = () => { detailFilter = $("#d-filter").value; renderDetail(); };
  $("#d-back").onclick = e => { e.preventDefault(); goBackFromDetail(); };
  if ($("#d-guest")) $("#d-guest").onclick = e => { e.preventDefault(); $("#tab-detail").hidden = true; openGuest(r.guest_id); };
  $("#d-auto").onchange = async () => {
    const on = $("#d-auto").checked;
    const d = await get(`/api/monitor/${$("#hotel").value}/select?id=${encodeURIComponent(r.id)}&on=${on ? 1 : 0}`, { method: "POST" }).catch(e => ({ ok: false, error: String(e) }));
    if (!d.ok) { $("#d-auto").checked = !on; notice(d.error || "?"); return; }
    await ensureRes([r.id], true);
    render(); renderDetail();
  };
  el.querySelectorAll(".d-send").forEach(b => b.onclick = () => {
    const pop = el.querySelector(`[data-pop="${b.dataset.step}"]`);
    pop.hidden = !pop.hidden;
    if (!pop.hidden) sendBar(r, b.dataset.step, pop.querySelector(".send-bar"));
  });
  el.querySelectorAll(".d-cancel").forEach(b => b.onclick = () => { b.closest(".pop").hidden = true; });
  $("#d-add").onclick = () => { $("#d-add-form").hidden = !$("#d-add-form").hidden; };
  $("#d-add-x").onclick = () => { $("#d-add-form").hidden = true; };
  $("#d-add-go").onclick = async () => {
    const v = $("#d-add-v").value.trim(), isMail = v.includes("@");
    const q = new URLSearchParams({ id: r.id, email: isMail ? v : "", phone: isMail ? "" : v });
    const d = await get(`/api/monitor/${$("#hotel").value}/contact?${q}`, { method: "POST" }).catch(e => ({ ok: false, error: String(e) }));
    if (!d.ok) { $("#d-add-err").textContent = d.error || t("load_error"); return; }
    await ensureRes([r.id], true);
    render(); renderDetail();
  };
}

// Ontvanger: buiten PRD ging het bericht naar het testadres, niet naar de gast
let hotelList = [];
const hotelNow = () => hotelList.find(h => h.id === $("#hotel").value) || {};
const isPrd = () => hotelNow().production === true;
// Testadres of -nummer van deze omgeving voor een kanaal (leeg = niets versturen)
const testTo = ch => ch === "email" ? hotelNow().test_email : hotelNow().test_phone;
function toCell(m) {
  if (m.channel === "form" || m.channel === "app") return esc(m.to);  // ingevuld door de gast, niets verstuurd
  if (isPrd() && (!m.delivered_to || m.delivered_to === m.to)) return esc(m.to);
  const test = m.delivered_to && m.delivered_to !== m.to ? m.delivered_to : (testTo(m.channel) || t("mg_test_addr"));
  return `<span class="tag warn">TEST</span> ${esc(test)}<div class="muted small">${esc(t("mg_for"))} ${esc(m.to)}</div>`;
}

// Versturen met de hand: bericht, kanaal en adres kiezen. Het adres komt uit een lijst (hoofdadres,
// extra adres, doorstuuradres, adressen van vroegere berichten) of wordt vrij getypt; het wordt niet bewaard.
// Keuzelijst van adressen (of nummers) voor versturen, met de bron erbij. Standaard: in de testomgeving
// het testadres, anders het adres uit het check-in-formulier (of het hoofdadres). Laatste keuze: ander adres.
function addressOptions(r, ch) {
  const out = [], seen = new Set();
  const add = (v, src) => {
    const k = (v || "").trim().toLowerCase();
    if (k && !seen.has(k)) { seen.add(k); out.push({ value: v.trim(), src }); }
  };
  const form = !!r.checkin_completed_at;
  if (ch === "email") {
    if (!isPrd() && testTo("email")) add(testTo("email"), t("src_test"));
    add(r.email, r.email_platform || (form ? t("src_form") : "Lighthouse"));
    add(r.backup_email, t("src_form_extra"));
    add(r.relay_email, r.relay_platform || t("src_relay"));
    (r.profile_emails || []).forEach(v => add(v, t("src_profile")));
    r.messages.filter(m => m.channel === "email").forEach(m => add(m.to, t("src_used")));
  } else {
    if (!isPrd() && testTo("phone")) add(testTo("phone"), t("src_test"));
    add(r.phone, form ? t("src_form") : "Lighthouse");
    add(r.backup_phone, t("src_form_extra"));
    (r.profile_phones || []).forEach(v => add(v, t("src_profile")));
    r.messages.filter(m => ["whatsapp", "sms"].includes(m.channel)).forEach(m => add(m.to, t("src_used")));
  }
  return out;
}

function sendBar(r, step, bar) {
  const phoneOn = !!hotelNow().phone_enabled;
  bar.innerHTML = `<select class="sb-ch"><option value="email">${esc(t("ch_email"))}</option>
      <option value="whatsapp" ${phoneOn ? "" : "disabled"}>${esc(t("ch_whatsapp"))}${phoneOn ? "" : " " + esc(t("sb_off"))}</option>
      <option value="sms" ${phoneOn ? "" : "disabled"}>${esc(t("ch_sms"))}${phoneOn ? "" : " " + esc(t("sb_off"))}</option></select>
    <span class="lbl">${esc(t("sb_to"))}</span><select class="sb-pick"></select>
    <input class="sb-to" autocomplete="off" hidden>
    <button type="button" class="primary sb-go">${esc(t("sb_go"))}</button><span class="sb-err" hidden></span>`;
  const ch = bar.querySelector(".sb-ch"), pick = bar.querySelector(".sb-pick"), to = bar.querySelector(".sb-to"), go = bar.querySelector(".sb-go");
  const fill = () => {
    const list = addressOptions(r, ch.value);
    pick.innerHTML = list.map(o => `<option value="${esc(o.value)}">${esc(o.value)} (${esc(o.src)})</option>`).join("")
      + `<option value="">${esc(t("sb_other"))}</option>`;
    to.placeholder = ch.value === "email" ? t("ct_email") : t("ct_phone");
    to.value = "";
    to.hidden = !!list.length;
    if (!list.length) pick.value = "";
  };
  fill();
  ch.onchange = fill;
  pick.onchange = () => { to.hidden = pick.value !== ""; if (!to.hidden) to.focus(); };
  to.oninput = () => { bar.querySelector(".sb-err").hidden = true; to.classList.remove("invalid"); };
  go.onclick = async () => {
    const address = (pick.value || to.value).trim();
    if (!address) { to.hidden = false; to.focus(); return; }
    // Getypt adres eerst nakijken (de server controleert ook): e-mail met @ en domein, nummer met landcode
    const err = bar.querySelector(".sb-err");
    const valid = ch.value === "email" ? /^[^@\s]+@[^@\s]+\.[^@\s]{2,}$/.test(address) : /^\+?[0-9 ./()-]{8,}$/.test(address);
    err.hidden = valid;
    err.textContent = valid ? "" : t(ch.value === "email" ? "sb_bad_email" : "sb_bad_phone");
    to.classList.toggle("invalid", !valid);
    if (!valid) { to.focus(); return; }
    const question = isPrd() ? t("rs_confirm", stepShort(step), t(CH[ch.value]), address)
      : testTo(ch.value) ? t("rs_confirm_test", stepShort(step), t(CH[ch.value]), testTo(ch.value), address) : t("rs_no_test");
    if (!isPrd() && !testTo(ch.value)) { notice(question); return; }
    if (!await ask(question, { ok: t("dlg_send") })) return;
    go.disabled = true;
    const q = new URLSearchParams({ id: r.id, step, channel: ch.value, to: address });
    const d = await get(`/api/monitor/${$("#hotel").value}/resend?${q}`, { method: "POST" }).catch(e => ({ ok: false, error: String(e) }));
    if (!d.ok) notice(d.error || t("load_error"));
    await load();
    if ($("#tab-detail") && !$("#tab-detail").hidden) renderDetail(); else showMessages(r.id);
  };
}

// Eerste kolommen vast bij horizontaal scrollen (aankomst, vertrek, nummer, gast)
function stickColumns(table, n) {
  if (!table) return;
  const heads = [...table.querySelectorAll("thead th")].slice(0, n);
  let left = 0;
  heads.forEach((th, i) => {
    const x = left;
    table.querySelectorAll(`tr > :nth-child(${i + 1})`).forEach(c => { c.classList.add("stick"); c.style.left = x + "px"; c.classList.toggle("stick-last", i === n - 1); });
    left += th.getBoundingClientRect().width;
  });
}


// Soort toestand in de tijdlijn, elk met een eigen kleur:
// sent (verstuurd), failed (mislukt), due (nu), planned (komt nog), missed (moment voorbij),
// cond (voorwaarde niet voldaan of geen adres), off (stap of berichten niet actief)
function planKind(p) {
  if (["sent", "failed", "due", "planned"].includes(p.state)) return p.state;
  if (p.state === "off") return "off";
  if (["window_passed", "booked_late", "later_due"].includes(p.reason)) return "missed";
  return "cond";
}

// Wordt het bericht verstuurd en wanneer
function planText(p, when) {
  const k = planKind(p);
  if (k === "sent") return `${t("pl_sent")} ${when}`;
  if (k === "failed") return `${t("pl_failed")} ${when}`;
  if (k === "planned") return `${t("pl_will")} ${when}`;
  if (k === "due") return t("pl_due");
  return t("pl_" + k);
}

// Korte reden in de tijdlijn (de volledige uitleg staat bij aanwijzen)
function reasonShort(reason) {
  if (reason.startsWith("condition:")) return t("rs_condition");
  return t("rss_" + reason) || reasonText(reason);
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
function gSortBy(k) { gSortDir = k === gSortKey ? -gSortDir : 1; gSortKey = k; loadGuestPage(true); }

// Gasten per 50 van de server (zelfde werking als de reservaties): guestData.guests = alle gekende profielen (cache),
// gIds = de lijst in de volgorde van de server
let gIds = [], gTotal = 0, gNext = null, gLoading = false, gSeq = 0, gFilterTimer = null;
function mergeGuests(items) {
  const m = new Map(guestData.guests.map(g => [g.id, g]));
  items.forEach(g => m.set(g.id, g));
  guestData.guests = [...m.values()];
}
async function loadGuestPage(reset = true, keep = 0) {
  if (!$("#guests")) return;
  const seq = ++gSeq;
  gLoading = true;
  const offset = reset ? 0 : gIds.length;
  const p = new URLSearchParams({ page: "1", offset: String(offset), limit: String(reset ? Math.max(RES_PAGE, keep) : RES_PAGE),
    sort: gSortKey, dir: gSortDir > 0 ? "asc" : "desc" });
  if ($("#g-search").value.trim()) p.set("q", $("#g-search").value.trim());
  try {
    const d = await get(`/api/monitor/${$("#hotel").value}/guests?${p}`);
    if (seq !== gSeq) return;
    mergeGuests([...d.guests, ...(d.match_guests || [])]);
    if (d.matches) guestData.matches = d.matches;
    const ids = d.guests.map(g => g.id);
    gIds = reset ? ids : gIds.concat(ids.filter(id => !gIds.includes(id)));
    gTotal = d.total; gNext = d.next;
  } finally {
    if (seq === gSeq) gLoading = false;
  }
  renderGuests();
  render();
}
async function ensureGuests(ids) {
  const miss = ids.filter(id => id && !guestById(id));
  if (!miss.length) return;
  const d = await get(`/api/monitor/${$("#hotel").value}/guests?page=1&ids=${encodeURIComponent(miss.join(","))}`);
  mergeGuests(d.guests);
}
function gFilterChanged(delay = 0) {
  clearTimeout(gFilterTimer);
  gFilterTimer = setTimeout(() => loadGuestPage(true), delay);
}

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

// keep: verversen zonder dat de lijst korter wordt (zelfde aantal rijen opnieuw laden)
async function loadGuests(keep = false) {
  await loadGuestPage(true, keep ? gIds.length : 0);
}

function guestById(id) { return guestData.guests.find(g => g.id === id); }

// Van een reservatie naar de gast (zoekvak), en van een gast naar precies zijn reservaties (ook onder een andere
// naam, bv. na samenvoegen; ook voorbije verblijven)
async function openGuest(id) {
  gSel = id;
  await ensureGuests([id]).catch(() => {});
  $("#g-search").value = guestById(id)?.name || "";
  showTab("guests");
  loadGuestPage(true);
}
function openReservations(id) {
  const g = guestById(id);
  $("#search").value = "";
  resPick = g ? { label: g.name, ids: new Set(g.reservations) } : null;
  clearResFilters();
  showTab("res"); loadResPage(true);
}

// Gastprofiel: alle contactgegevens met de bron. Hoofdadres en -nummer (bevestigd in het formulier of
// uit Lighthouse), extra adres en nummer uit het formulier, vroeger gebruikte en doorstuuradressen.
function contactCell(g) {
  const row = (v, label, cls = "") => `<div class="ct-line ${cls}">${esc(v)} <span class="tag src">${esc(label)}</span></div>`;
  const main = g.form ? t("src_form") : "Lighthouse";
  const lines = [];
  const seen = new Set();
  const add = (v, label, cls) => { const k = (v || "").toLowerCase(); if (k && !seen.has(k)) { seen.add(k); lines.push(row(v, label, cls)); } };
  add(g.email, g.email_own ? main : "OTA");
  add(g.phone, main);
  add(g.backup_email, t("src_form_extra"));
  add(g.backup_phone, t("src_form_extra"));
  (g.known_emails || []).forEach(v => add(v, t("src_earlier"), "muted"));
  (g.known_phones || []).forEach(v => add(v, t("src_earlier"), "muted"));
  (g.relay_emails || []).forEach(v => add(v, t("src_relay"), "muted"));
  if (g.opt_out) lines.push(`<span class="tag fail">${esc(t("g_optout"))}</span>`);
  return lines.join("");
}

// Hoofdadres en nummer, plus het extra adres en nummer uit het check-in-formulier
function contactLines(x) {
  const extra = v => `<span class="muted" title="${esc(t("backup"))}">${esc(v)} (2)</span>`;
  // Doorstuuradres van Booking.com, Expedia, ...: label met het platform; bewaard maar niet gebruikt
  // zodra de gast een eigen adres gaf (dat gaat voor)
  const platform = p => p ? ` <span class="tag" title="${esc(t("relay_hint"))}">${esc(p)}</span>` : "";
  const relay = x.relay_email ? `<span class="muted" title="${esc(t("relay_kept"))}"><s>${esc(x.relay_email)}</s></span>${platform(x.relay_platform)}` : "";
  return [x.email && esc(x.email) + platform(x.email_platform), x.backup_email && extra(x.backup_email), relay,
    x.phone && esc(x.phone), x.backup_phone && extra(x.backup_phone)].filter(Boolean).join("<br>");
}

let gSel = "", guestSync = "";  // gekozen gast (profiel rechts), laatste synchronisatie (robotlog, taak onderhoud)
async function loadGuestSync() {
  try {
    const d = await get(`/api/monitor/${$("#hotel").value}/runs`);
    const last = (d.runs || []).find(x => x.task === "onderhoud" && x.ok !== false);
    guestSync = last ? (last.finished_at || last.started_at) : "";
    renderGuests();
  } catch (e) { /* niet erg: dan zonder tijdstip */ }
}
const ICG = {
  mail: '<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><rect x="3" y="5" width="18" height="14" rx="2"/><path d="M3.5 6.5l8.5 6.5 8.5-6.5"/></svg>',
  wa: '<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M21 12a8 8 0 0 1-11.6 7.1L4 20.5l1.4-5A8 8 0 1 1 21 12z"/></svg>',
  phone: '<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M5 4h4l2 5-2.5 1.5a11 11 0 0 0 5 5L15 13l5 2v4a2 2 0 0 1-2 2A16 16 0 0 1 3 6a2 2 0 0 1 2-2z"/></svg>',
};
const dlong = iso => iso ? new Date(iso + (iso.length === 10 ? "T00:00" : "")).toLocaleDateString(locale(), { day: "numeric", month: "short", year: "numeric" }).replace(/\./g, "") : "";
const dmonth = iso => iso ? new Date(iso + (iso.length === 10 ? "T00:00" : "")).toLocaleDateString(locale(), { month: "short", year: "numeric" }).replace(/\./g, "") : "";
const countryName = c => { try { return c ? new Intl.DisplayNames([locale()], { type: "region" }).of(c.toUpperCase()) : ""; } catch { return c; } };
const num1 = x => x == null ? "" : Number(x).toLocaleString(locale(), { minimumFractionDigits: 1, maximumFractionDigits: 1 });

function renderGuests() {
  // Zoeken en sorteren doet de server (per 50, loadGuestPage)
  const list = gIds.map(guestById).filter(Boolean);
  document.querySelectorAll("#g-head th[data-gsort]").forEach(th => {
    th.classList.toggle("sorted", th.dataset.gsort === gSortKey);
    th.dataset.dir = th.dataset.gsort === gSortKey ? (gSortDir > 0 ? "asc" : "desc") : "";
  });
  if (!gSel || !guestById(gSel)) gSel = list[0]?.id || "";
  if ($("#g-more")) $("#g-more").textContent = gNext != null ? t("list_more", list.length, gTotal) : "";
  $("#g-count").textContent = t("g_profiles", gTotal) + (guestSync ? " · " + t("g_synced", dtime(guestSync)) : "");
  const nomkt = g => g.opt_out ? ` <span class="tag t-off">${esc(t("gp_nomkt"))}</span>` : "";
  $("#guests").innerHTML = list.map(g => `
    <tr data-g="${esc(g.id)}" style="cursor:pointer${g.id === gSel ? ";background:#EEF0F5" : ""}">
      <td><a class="nm" href="#" data-g="${esc(g.id)}">${esc(g.name)}</a>${nomkt(g)}</td><td>${esc(g.country)}</td>
      <td class="mono">${g.reservations.length}</td><td class="mono">${g.stays}</td><td class="small">${esc(dlong(g.last_stay))}</td><td class="small">${esc(g.preferred_channel)}</td>
    </tr>`).join("") || `<tr><td colspan="6" class="muted">${t("no_guests")}</td></tr>`;
  $("#mguests").innerHTML = list.map(g => `<a href="#" class="mcard" data-g="${esc(g.id)}" style="text-decoration:none;color:#2B2F38">
      <div class="mrow"><b style="font-size:16px">${esc(g.name)}</b>${ICO.chev}</div>
      <div class="small muted">${esc([g.country, `${g.reservations.length} ${t("gp_resn")}`, t("gp_stays_m", g.stays), g.last_stay ? dlong(g.last_stay) : "", g.preferred_channel].filter(Boolean).join(" · "))}</div>
      ${g.opt_out ? `<div class="row" style="gap:4px"><span class="tag t-off">${esc(t("gp_nomkt"))}</span></div>` : ""}</a>`).join("") || `<div class="muted">${t("no_guests")}</div>`;
  document.querySelectorAll("#guests [data-g], #mguests [data-g]").forEach(el => el.onclick = e => {
    e.preventDefault();
    gSel = el.dataset.g;
    $("#tab-guests").classList.add("gdet");  // gsm: het profiel als eigen scherm
    renderGuests();
    if (matchMedia("(max-width:760px)").matches) window.scrollTo(0, 0);  // alleen gsm: profiel is daar een eigen scherm
  });
  renderProfile();
  renderMatches();
}

// Nepnummer van een boekingssite (zelfde regel als checkin/service.py placeholder_phone)
const fakePhone = p => { const d = String(p || "").replace(/\D/g, ""); return d.length >= 8 && (new Set(d).size === 1 || new Set(d.slice(3)).size === 1); };
// Profiel van de gekozen gast, zoals in het ontwerp (rechts)
function renderProfile() {
  const g = guestById(gSel), el = $("#g-profile");
  if (!g) { el.innerHTML = `<section class="card"><div class="cb" style="padding-top:16px"><span class="muted">${esc(t("gp_none"))}</span></div></section>`; return; }
  const muted = g.muted || [];
  const own = [...new Set([g.email, g.backup_email, ...(g.known_emails || [])].filter(Boolean))].filter(x => !(g.relay_emails || []).includes(x));
  const phones = [...new Set([g.phone, g.backup_phone, ...(g.known_phones || [])].filter(Boolean))];
  const src = x => x === g.email && g.form ? t("gp_form") : t("gp_booking");
  const box = (label, attrs, on, title) => `<label class="row small" style="gap:6px;font-weight:600;white-space:nowrap"${title ? ` title="${esc(title)}"` : ""}><input type="checkbox" ${attrs} ${on ? "checked" : ""}>${esc(label)}</label>`;
  // mail: marketing = "own" (eigen adres), "relay" (nooit) of leeg (gsm: geen marketing-vinkje)
  // Zoals de robot verstuurt (send_messages.recipients): eigen adressen; het doorstuuradres alleen zolang er geen eigen
  // adres is; gsm alleen met toestemming in het formulier. Marketing volgt de keuze in het formulier.
  const formMails = (g.form_emails || []), consent = (g.consent_phones || []);
  const line = (icon, value, sub, ch, disabled, mail) => {
    const lc = value.toLowerCase(), why = [];
    // Standaard (zoals de robot zonder vinkje beslist); een vinkje van het hotel gaat voor en mag dat omwisselen
    let def = !muted.includes(ch);
    if (def && mail === "relay" && own.length) { def = false; why.push(t("gp_not_used")); }
    if (def && mail === "own" && ![g.email, g.backup_email].filter(Boolean).map(x => x.toLowerCase()).includes(lc)) { def = false; why.push(t("gp_old")); }
    if (def && !mail && ch && !consent.includes(value)) { def = false; why.push(t("gp_no_consent")); }
    const set = (g.prefs || {})[`${ch}:${lc}`];
    if (set !== undefined) why.length = 0;
    const stay = box(t("gp_stayinfo"), disabled ? "disabled" : `data-pref="${esc(ch)}" data-addr="${esc(value)}"`, !disabled && (set !== undefined ? set : def));
    const off = (g.marketing_off || []).includes(lc), byGuest = (g.marketing_by_guest || []).includes(lc), fromForm = formMails.includes(lc);
    const mkt = mail === "relay" ? box(t("gp_mkt"), "disabled", false, t("gp_mkt_relay"))
      : mail === "own" ? (byGuest || !fromForm ? box(t("gp_mkt"), "disabled", false, byGuest ? t("gp_mkt_guest") : t("gp_mkt_noform"))
        : box(t("gp_mkt"), `data-mkt="${esc(value)}"`, !off)) : "";
    if (mail === "own" && byGuest) why.push(t("gp_mkt_guest"));
    else if (mail === "own" && !fromForm) why.push(t("gp_mkt_noform"));
    return `<div class="li">${icon}<div class="lt"><b>${esc(value)}</b><div class="small muted">${esc([sub, ...why].join(" · "))}</div></div>
      <div style="display:flex;flex-direction:column;gap:6px;align-items:flex-start;flex:0 0 112px">${stay}${mkt}</div></div>`;
  };
  const contacts = [
    ...own.map(x => line(ICG.mail, x, src(x), "email", false, "own")),
    // Doorstuuradres van Booking.com/Expedia: berichten over het verblijf gaan er wel naartoe, nooit marketing
    ...(g.relay_emails || []).map(x => line(ICG.mail, x, t("gp_relay"), "email", false, "relay")),
    // Nepnummer van de boekingssite (+11111111111): nooit gebruikt, dus geen vinkje
    ...phones.flatMap(x => fakePhone(x) ? [line(ICG.phone, x, t("gp_fake"), "", true)]
      : [line(ICG.wa, x, `${t("gp_wa")}, ${src(x)}`, "whatsapp"), line(ICG.phone, x, `${t("gp_sms")}, ${src(x)}`, "sms")]),
  ].join("");
  const today = todayIso();
  const missing = g.reservations.filter(id => !resById(id) && !resAsked.has(id));
  if (missing.length) { missing.forEach(id => resAsked.add(id)); ensureRes(missing).then(renderProfile).catch(() => {}); }
  const res = g.reservations.map(resById).filter(Boolean).sort((a, b) => b.arrival.localeCompare(a.arrival));
  const badge = r => r.status === "cancelled" ? `<span class="badge b-err">${esc(t("r_cancelled"))}</span>`
    : r.departure < today ? `<span class="badge b-ok">${esc(t("gp_left"))}</span>`
    : r.arrival <= today ? `<span class="badge b-info">${esc(t("gp_now"))}</span>` : `<span class="badge b-wait">${esc(t("gp_coming"))}</span>`;
  const resLines = res.slice(0, 3).map(r => `<div class="li"><div class="lt"><a href="#" class="nm" data-open-res="${esc(g.id)}">#${esc(r.booking_number)}</a> ${esc(`${dshort(r.arrival)} ${t("stay_to")} ${dlong(r.departure)}${r.rooms.length ? ", " + t("r_room", r.rooms.join(", ")).toLowerCase() : ""}`)}${res.length > 1 ? `<div><a href="#" class="small" data-detach="${esc(r.id)}" data-bn="${esc(r.booking_number)}">${esc(t("gp_detach"))}</a></div>` : ""}</div>${badge(r)}</div>`).join("");
  const inHouse = res.some(r => r.status !== "cancelled" && r.arrival <= today && r.departure > today);
  el.innerHTML = `<a class="btn3 m-only" href="#guests" id="gp-back" style="padding:0;align-self:flex-start">${IC(P.back, 16)}${esc(t("g_back"))}</a><section class="card"><div class="ch"><div><h2 style="font-size:20px">${esc(g.name)}</h2><div class="small muted">${esc([countryName(g.country), g.first_stay ? t("gp_since", dmonth(g.first_stay)) : ""].filter(Boolean).join(" · "))}</div></div>
    <div class="row">${g.opt_out ? `<span class="tag t-off">${esc(t("gp_nomkt"))}</span>` : ""}${g.stays > 1 ? `<span class="tag t-on">${esc(t("gp_back"))}</span>` : ""}</div></div>
    <div class="cb"><div class="statgrid" style="grid-template-columns:repeat(3,minmax(0,1fr))">
      <div class="stat"><span class="n">${g.reservations.length}</span><span class="l">${esc(t("gp_resn"))}</span></div>
      <div class="stat"><span class="n">${g.stays}</span><span class="l">${esc(t("gp_stays"))}</span></div>
      <div class="stat"><span class="n">${g.cancellations || 0}</span><span class="l">${esc(t("gp_canc"))}</span></div>
      <div class="stat"><span class="n">${esc(num1(g.avg_nights))}</span><span class="l">${esc(t("gp_nights"))}</span></div>
      <div class="stat"><span class="n">${esc(num1(g.avg_persons))}</span><span class="l">${esc(t("gp_pers"))}</span></div></div>
    <dl class="kv"><dt>${esc(t("gp_first"))}</dt><dd>${esc(dmonth(g.first_stay))}</dd><dt>${esc(t("gp_last"))}</dt><dd>${esc(dlong(g.last_stay))}${inHouse ? " " + esc(t("gp_nowsuffix")) : ""}</dd>
      <dt>${esc(t("gp_chan"))}</dt><dd>${esc(g.preferred_channel)}</dd><dt>${esc(t("gp_rooms"))}</dt><dd>${esc(g.rooms.join(", "))}</dd></dl>
    <div class="lbl" style="margin-top:6px">${esc(t("gp_contact"))}</div><div class="help">${esc(t("gp_help"))}</div>${contacts}
    <div class="lbl" style="margin-top:6px">${esc(t("gp_res"))}</div>${resLines}
    ${g.reservations.length ? `<a class="btn3" href="#" data-open-res="${esc(g.id)}" style="padding:0">${esc(t("gp_all", g.reservations.length))}</a>` : ""}</div></section>`;
  el.querySelectorAll("[data-open-res]").forEach(a => a.onclick = e => { e.preventDefault(); openReservations(a.dataset.openRes); });
  el.querySelectorAll("[data-detach]").forEach(a => a.onclick = async e => {
    e.preventDefault();
    if (!await ask(t("gp_detach_q", a.dataset.bn), { ok: t("gp_detach"), danger: true })) return;
    const d = await get(`/api/monitor/${encodeURIComponent($("#hotel").value)}/guests?action=detach&reservation=${encodeURIComponent(a.dataset.detach)}`, { method: "POST" });
    await refreshNow();
    if (d.guest) { gSel = d.guest; renderGuests(); }  // meteen de gast waar ze nu bij hoort
  });
  if ($("#gp-back")) $("#gp-back").onclick = e => { e.preventDefault(); $("#tab-guests").classList.remove("gdet"); window.scrollTo(0, 0); };
  el.querySelectorAll("input[data-mkt]").forEach(b => b.onchange = async () => {
    const r = await get(`/api/monitor/${encodeURIComponent($("#hotel").value)}/guests?action=marketing&email=${encodeURIComponent(b.dataset.mkt)}&on=${b.checked ? 1 : 0}`, { method: "POST" });
    if (!r.ok) { b.checked = !b.checked; if (r.error) await ask(r.error, { ok: "OK" }); return; }
    const k = b.dataset.mkt.toLowerCase();
    g.marketing_off = b.checked ? (g.marketing_off || []).filter(x => x !== k) : [...(g.marketing_off || []), k];
  });
  el.querySelectorAll("input[data-pref]").forEach(b => b.onchange = async () => {
    const r = await get(`/api/monitor/${encodeURIComponent($("#hotel").value)}/guests?action=pref&a=${encodeURIComponent(g.id)}&channel=${b.dataset.pref}&address=${encodeURIComponent(b.dataset.addr)}&on=${b.checked ? 1 : 0}`, { method: "POST" });
    if (!r.ok) { b.checked = !b.checked; return; }
    g.prefs = { ...(g.prefs || {}), [`${b.dataset.pref}:${b.dataset.addr.toLowerCase()}`]: b.checked };
    g.muted = (g.muted || []).filter(c => c !== b.dataset.pref);
    renderProfile();
  });
  el.querySelectorAll("input[data-mute]").forEach(box => box.onchange = async () => {
    const id = box.dataset.mute;
    // Per kanaal: alle regels van hetzelfde kanaal mee aan- of uitvinken
    el.querySelectorAll(`input[data-mute][value="${box.value}"]`).forEach(x => { x.checked = box.checked; });
    const m = ["email", "whatsapp", "sms"].filter(c => { const x = el.querySelector(`input[data-mute][value="${c}"]`); return x && !x.checked; });
    g.muted = m;
    await get(`/api/monitor/${$("#hotel").value}/guests?action=channels&a=${encodeURIComponent(id)}&muted=${m.join(",")}`, { method: "POST" });
  });
}

function renderMatches() {
  const m = guestData.matches.filter(x => guestById(x.a) && guestById(x.b));
  $("#matches-card").hidden = !m.length;
  $("#m-open").textContent = t("m_open", m.length);
  const who = g => {
    const info = (g.preferred_channel || g.last_stay ? [g.preferred_channel, g.last_stay ? g.last_stay.slice(0, 4) : ""]
      : [g.booked_source, g.booked_arrival ? t("m_arrives", dshort(g.booked_arrival) + " " + g.booked_arrival.slice(0, 4)) : ""]).filter(Boolean).join(", ");
    return `<b>${esc(g.name)}</b>${info ? ` (${esc(info)})` : ""}`;
  };
  // Openklappen: per gast de adressen, nummers en gegevens, zodat je kan beslissen voor je samenvoegt
  const uniq = xs => [...new Set(xs.filter(Boolean).map(v => String(v)))];
  const facts = (g, hit) => {
    const mark = v => v.toLowerCase() === String(hit || "").toLowerCase() ? `<mark>${esc(v)}</mark>` : esc(v);
    const line = (lbl, vals) => vals.length ? `<div><span class="muted">${esc(lbl)}:</span> ${vals.map(mark).join(", ")}</div>` : "";
    const res = (g.reservations || []).length;
    return `<div style="flex:1 1 240px;min-width:0"><div><b>${esc(g.name)}</b> <a href="#" data-open-guest="${esc(g.id)}">${esc(t("m_open_profile"))}</a></div>
      ${line(t("m_f_email"), uniq([g.email, ...(g.known_emails || []), g.backup_email]))}
      ${line(t("m_f_relay"), uniq(g.relay_emails || []))}
      ${line(t("m_f_phone"), uniq([g.phone, ...(g.known_phones || []), g.backup_phone]))}
      ${line(t("m_f_country"), uniq([g.country, g.language && g.language.toUpperCase()]))}
      ${line(t("m_f_channel"), uniq((g.channels || []).map(c => `${c.name} (${c.count})`).concat(g.channels && g.channels.length ? [] : [g.booked_source])))}
      ${line(t("m_f_stays"), uniq([`${res} ${t("m_f_res")}`, `${g.stays || 0} ${t("m_f_st")}`, g.first_stay && `${dshort(g.first_stay)} ${g.first_stay.slice(0, 4)}`, g.last_stay && `${dshort(g.last_stay)} ${g.last_stay.slice(0, 4)}`, g.booked_arrival && t("m_arrives", dshort(g.booked_arrival) + " " + g.booked_arrival.slice(0, 4))]))}
      ${line(t("m_f_rooms"), uniq(g.rooms || []))}</div>`;
  };
  $("#matches").innerHTML = m.map(x => `<div class="note warn" style="flex-wrap:wrap"><details style="flex:1 1 280px"><summary style="cursor:pointer">${who(guestById(x.a))} ${esc(t("m_and"))} ${who(guestById(x.b))}: ${esc(t("m_" + x.reason))}${x.contact ? ` (${esc(x.contact)})` : ""}</summary>
    <div class="row small" style="align-items:flex-start;gap:16px;margin-top:8px">${facts(guestById(x.a), x.contact)}${facts(guestById(x.b), x.contact)}</div>
    ${x.contact ? `<div class="row small" style="margin-top:8px;gap:8px">${x.shared_names ? `<span><b>${esc(t("m_shared_hint", x.contact, x.shared_names, (x.shared_channels || []).join(", ")))}</b></span>` : ""}<button class="btn2 sm" type="button" data-shared="${esc(x.contact)}">${esc(t("m_shared_btn"))}</button></div>` : ""}</details>
    <div class="row"><button class="btn sm" type="button" data-act="merge" data-a="${esc(x.a)}" data-b="${esc(x.b)}">${esc(t("m_keep"))}</button><button class="btn2 sm" type="button" data-act="different" data-a="${esc(x.a)}" data-b="${esc(x.b)}" data-value="${esc(x.contact || "")}">${esc(t("m_apart"))}</button></div></div>`).join("");
  document.querySelectorAll("#matches [data-shared]").forEach(b => b.onclick = async () => {
    if (!await ask(t("m_shared_q", b.dataset.shared), { ok: t("m_shared_btn") })) return;
    await get(`/api/monitor/${$("#hotel").value}/guests?action=shared&value=${encodeURIComponent(b.dataset.shared)}`, { method: "POST" });
    loadGuests();
  });
  document.querySelectorAll("#matches [data-open-guest]").forEach(a => a.onclick = e => { e.preventDefault(); openGuest(a.dataset.openGuest); });
  document.querySelectorAll("#matches button").forEach(b => b.onclick = async () => {
    if (b.dataset.act === "merge" && !await ask(t("m_confirm"), { ok: t("m_keep") })) return;
    await get(`/api/monitor/${$("#hotel").value}/guests?action=${b.dataset.act}&a=${encodeURIComponent(b.dataset.a)}&b=${encodeURIComponent(b.dataset.b)}${b.dataset.value ? "&value=" + encodeURIComponent(b.dataset.value) : ""}`, { method: "POST" });
    loadGuests();
  });
}

// Sorteren: klik op een kolomtitel, nog eens klikken keert de volgorde om
let sortKey = "arrival", sortDir = 1;
try { [sortKey, sortDir] = JSON.parse(localStorage.getItem("monitor-sort")) || [sortKey, sortDir]; } catch (e) { /* geen opslag */ }
const sortValue = (r, k) => k === "room" ? (r.rooms.join(", ") || r.room_type)
  : k === "messages" ? r.messages.length : k === "guests" ? (r.guests ?? -1)
  : k === "email" ? (r.email || r.phone)
  : k === "rate" ? (r.non_refundable === true ? "0" : r.non_refundable === false ? "1" : "") + (r.rate_plan || "")
  : (r[k] ?? "");
function sortBy(k) {
  sortDir = k === sortKey ? -sortDir : 1;
  sortKey = k;
  try { localStorage.setItem("monitor-sort", JSON.stringify([sortKey, sortDir])); } catch (e) { /* geen opslag */ }
  loadResPage(true);
}

const ICO = {
  ext: '<svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M14 4h6v6M20 4l-9 9"/><path d="M18 14v5a1 1 0 0 1-1 1H5a1 1 0 0 1-1-1V7a1 1 0 0 1 1-1h5"/></svg>',
  mail: n => `<svg width="${n}" height="${n}" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><rect x="3" y="5" width="18" height="14" rx="2"/><path d="M3.5 6.5l8.5 6.5 8.5-6.5"/></svg>`,
  phone: '<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M5 4h4l2 5-2.5 1.5a11 11 0 0 0 5 5L15 13l5 2v4a2 2 0 0 1-2 2A16 16 0 0 1 3 6a2 2 0 0 1 2-2z"/></svg>',
  chev: '<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M9 6l6 6-6 6"/></svg>',
};
// Datums zoals in het ontwerp: "wo 18 nov", "18 nov 07:12"
const dday = iso => iso ? new Date(iso + (iso.length === 10 ? "T00:00" : "")).toLocaleDateString(locale(), { weekday: "short", day: "numeric", month: "short" }).replace(/\./g, "") : "";
const dshort = iso => iso ? new Date(iso + (iso.length === 10 ? "T00:00" : "")).toLocaleDateString(locale(), { day: "numeric", month: "short" }).replace(/\./g, "") : "";
const dtime = iso => iso ? `${dshort(iso)} ${new Date(iso).toLocaleTimeString(locale(), { hour: "2-digit", minute: "2-digit" })}` : "";
const nights = r => Math.round((new Date(r.departure) - new Date(r.arrival)) / 86400000);

// Labels bij de gast: formulier, trappen, berichten aan/uit, geannuleerd
function resTags(r) {
  const tg = [];
  if (r.status === "cancelled") tg.push(`<span class="tag t-off">${esc(t("r_cancelled"))}</span>`);
  else tg.push(r.checkin_completed_at ? `<span class="tag t-on" title="${esc(stamp(r.checkin_completed_at))}">${esc(t("r_form"))}</span>` : `<span class="tag t-off">${esc(t("r_noform"))}</span>`);
  if (r.stairs) tg.push(`<span class="tag t-st" title="${esc(t("stairs_tip"))}">${esc(t("r_stairs"))}</span>`);
  if (r.messages_pick) tg.push(`<span class="tag ${r.messages_pick === "on" ? "t-on" : "t-off"}">${esc(t(r.messages_pick === "on" ? "r_msgs_on" : "r_msgs_off"))}</span>`);
  return tg.join(" ");
}
const roomLabel = r => r.rooms.length ? t("r_room", r.rooms.join(", ")) : (r.room_type || "");
const rateTag = r => r.non_refundable === true ? t("r_rate_nrf") : r.non_refundable === false ? t("r_rate_flex") : "";
// Laatste bericht en het volgende uit de planning
function msgLast(r) {
  const ms = [...r.messages].sort((a, b) => String(a.at).localeCompare(String(b.at)));
  const last = ms[ms.length - 1];
  if (!last) return null;
  const failed = !ms.filter(m => m.type === last.type).some(m => m.ok);
  return { failed, text: failed ? t("r_failed", stepShort(last.type)) : `${stepShort(last.type)} ${dshort(last.at)}` };
}
function msgNext(r) {
  const next = (r.plan || []).find(p => p.state === "planned" || p.state === "due");
  if (next) return `${stepShort(next.step)} ${next.due ? (next.due.length > 10 ? dtime(next.due) : dshort(next.due)) : ""}`.trim();
  return r.messages_on === false ? t("r_none_off") : t("r_none");
}

// Bij een link naar precies bepaalde reservaties: de andere filters leeg, zodat wat op het scherm staat ook is wat
// gebruikt wordt (de reservaties zelf staan als filter boven de lijst, met Toon alle)
function clearResFilters() {
  $("#search").value = ""; $("#from").value = ""; $("#to").value = "";
  if ($("#status")) $("#status").value = "";
}
let resPick = null;  // {label, ids}: alleen deze reservaties (link vanuit Vandaag), tot "Toon alle"
const todayPicks = {};
function render() {
  // Zoeken, filteren en sorteren doet de server (per 50, zie loadResPage); hier alleen tonen
  const list = resIds.map(resById).filter(Boolean);
  document.querySelectorAll("#res-head th[data-sort]").forEach(th => {
    th.classList.toggle("sorted", th.dataset.sort === sortKey);
    th.dataset.dir = th.dataset.sort === sortKey ? (sortDir > 0 ? "asc" : "desc") : "";
  });
  if ($("#res-more")) $("#res-more").textContent = resNext != null ? t("list_more", list.length, resTotal) : "";
  $("#count").innerHTML = t("res_count", resTotal) + (resPick ? ` <span class="badge b-info" style="margin-left:8px">${esc(t("pick_filter"))}: ${esc(resPick.label)} (${resPick.ids.size})</span> <a href="#" class="btn3" id="pick-clear" style="padding:0">${esc(t("pick_clear"))}</a>` : "");
  if ($("#pick-clear")) $("#pick-clear").onclick = e => { e.preventDefault(); resPick = null; loadResPage(true); };
  const contactCount = r => [[r.email, r.backup_email], [r.phone, r.backup_phone]].map(x => x.filter(Boolean).length);
  $("#res").innerHTML = list.map(r => {
    const last = msgLast(r), [ne, np] = contactCount(r), cancelled = r.status === "cancelled";
    const pms = cancelled ? `<span class="badge b-err">${esc(t("r_cancelled"))}</span>` : r.pms_status ? `<span class="badge ${/klaar|ready/i.test(r.pms_status) ? "b-ok" : "b-info"}">${esc(r.pms_status)}</span>` : "";
    const guest = `<a class="nm" href="#" data-msgs="${esc(r.id)}">${esc(r.guest)}</a>${r.guest_stays ? ` <span class="small muted">(${esc(t("r_returning", r.guest_stays))})</span>` : ""}`;
    return `<tr data-row-open="${esc(r.id)}" class="${cancelled ? "cancel" : last && last.failed ? "warnrow" : ""}${r.id === lastOpened ? " sel" : ""}">
      <td class="mono"><b>${esc(dday(r.arrival))}</b><div class="small muted">${esc(t("r_until", dday(r.departure), nights(r)))}</div></td>
      <td>${r.lighthouse_url ? `<a href="${esc(r.lighthouse_url)}" target="_blank" rel="noopener" class="row" style="gap:4px;font-weight:700" title="${esc(t("open_lh"))}">#${esc(r.booking_number)} ${ICO.ext}</a>` : `<b>#${esc(r.booking_number)}</b>`}${r.booked_at ? `<div class="small muted">${esc(t("r_booked", dshort(r.booked_at)))}</div>` : ""}${r.updated_at ? `<div class="small muted">${esc(t("r_updated", dtime(r.updated_at)))}</div>` : ""}</td>
      <td>${guest}<div class="row" style="gap:4px;margin-top:4px">${resTags(r)}</div></td>
      <td><b>${esc(roomLabel(r))}</b>${r.guests != null ? ` <span class="small muted">${esc(t("r_p", r.guests))}</span>` : ""}<div class="small muted">${esc(r.rooms.length > 1 ? t("r_rooms", r.rooms.length) : r.rooms.length ? r.room_type : t("r_roomtype"))}</div><div style="margin-top:3px">${rateTag(r) ? `<span class="tag">${esc(rateTag(r))}</span>` : ""} <span class="small muted">${esc(r.rate_plan)}</span></div></td>
      <td>${esc(r.source)}<div class="small muted">${esc(t("r_flow", t("flow_" + r.flow) || r.flow))}</div></td>
      <td>${pms}</td>
      <td><div class="row small" style="gap:10px"><span class="row" style="gap:3px" title="${esc(t("r_emails"))}">${ICO.mail(14)}${ne}</span><span class="row" style="gap:3px" title="${esc(t("r_phones"))}">${ICO.phone}${np}</span></div></td>
      <td><a href="#" class="msgs" data-msgs="${esc(r.id)}" title="${esc(t("mg_click"))}">${last ? `<div class="small"${last.failed ? ' style="color:#8B2E2E"' : ""}><b>${esc(last.text)}</b></div>` : ""}<div class="small muted">${esc(t("r_next", msgNext(r)))}</div></a></td>
      <td><a class="btn3" href="#" data-msgs="${esc(r.id)}" aria-label="${esc(t("r_details", r.guest))}">${ICO.chev}</a></td>
    </tr>`;
  }).join("") || `<tr><td colspan="9" class="muted">${t("no_res")}</td></tr>`;
  $("#mres").innerHTML = list.map(r => {
    const last = msgLast(r);
    return `<a href="#" class="mcard" data-msgs="${esc(r.id)}" style="text-decoration:none;color:#2B2F38;${last && last.failed ? "box-shadow:0 0 0 2px #E6BDBD" : ""}">
      <div class="mrow"><b style="font-size:16px${r.status === "cancelled" ? ";text-decoration:line-through" : ""}">${esc(r.guest)}</b>${ICO.chev}</div>
      <div class="small muted">${esc(`${dday(r.arrival)} ${t("stay_to")} ${dday(r.departure)} · ${roomLabel(r)}${r.guests != null ? " · " + t("r_p", r.guests) : ""}`)}</div>
      <div class="small muted">${esc(["#" + r.booking_number, r.source, rateTag(r)].filter(Boolean).join(" · "))}</div>
      <div class="row" style="gap:4px">${resTags(r)}</div>
      <div class="small"${last && last.failed ? ' style="color:#8B2E2E"' : ""}>${ICO.mail(13)} ${esc([last ? last.text : "", t("r_next_m", msgNext(r))].filter(Boolean).join(" · "))}</div>
    </a>`;
  }).join("") || `<div class="muted">${t("no_res")}</div>`;
  // Popup altijd met verse gegevens (bv. net ingevuld formulier, nieuw bericht)
  document.querySelectorAll("#res [data-msgs], #mres [data-msgs]").forEach(a => a.onclick = e => { e.preventDefault(); openDetail(a.dataset.msgs); });
  renderDetail();
  renderToday();
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
  // Tijdens een run elke 3 seconden verversen, zodat je de voortgang ziet
  if (runsData.running || runsData.progress || $("#run").dataset.waiting) timer = setTimeout(loadRuns, 3000);
}

// Gemeten duur per onderdeel onder de totale duur, bv. "aanmelden 25 s, lijst 6 s, 2 contacten à 9 s"
// Opstart van een robotrun: Azure start de run, de container start, klaar om te lezen (aangemeld)
const hms = iso => iso ? new Date(iso).toLocaleTimeString(locale(), { hour: "2-digit", minute: "2-digit", second: "2-digit" }) : "";
function startText(x, execs) {
  if (!x.process_started_at) return "";
  const azure = (execs || {})[x.execution];
  const p = [];
  if (azure) p.push(`${t("t_azure")} ${hms(azure)}`);
  const wait = azure ? Math.round((new Date(x.process_started_at) - new Date(azure)) / 1000) : null;
  p.push(`${t("t_container")} ${hms(x.process_started_at)}${wait != null ? ` (+${wait} s)` : ""}`);
  const tm = x.timings || {};
  if (tm.ready != null) p.push(t("t_ready", Math.round(tm.ready + (wait || 0))));
  return `<div class="timing">${esc(p.join(" · "))}</div>`;
}

function timingText(tm) {
  if (!tm || !Object.keys(tm).length) return "";
  const p = [];
  if (tm.lh_browser != null) p.push(`${t("t_browser")} ${Math.round(tm.lh_browser)} s`);
  if (tm.login != null) {
    const how = tm.lh_session === 1 ? t("t_reused") : tm.lh_session === 0 ? t("t_new") : "";
    p.push(`${t("t_login")} ${Math.round(tm.lh_login ?? tm.login)} s${how ? ` (${how})` : ""}`);
  }
  if (tm.list != null) p.push(`${t("t_list")} ${Math.round(tm.list)} s`);
  if (tm.contact != null) p.push(t("t_contact", tm.contacts || 1, Math.round(tm.contact)));
  return `<div class="timing">${esc(p.join(", "))}</div>`;
}

const BIN = `<svg viewBox="0 0 16 16" width="14" height="14" aria-hidden="true"><path fill="currentColor" d="M6 1h4l.5 1H14v1.5H2V2h3.5L6 1zm-2.5 3.5h9l-.7 9.6a1 1 0 0 1-1 .9H5.2a1 1 0 0 1-1-.9L3.5 4.5zm3 1.5v7h1V6h-1zm2 0v7h1V6h-1z"/></svg>`;
let subTab = "log";
function showSub(name) {
  subTab = name;
  document.querySelectorAll("#tab-robot .subtabs button").forEach(b => b.classList.toggle("active", b.dataset.sub === name));
  // Ontwerp: logboek en runs volgens Azure altijd naast elkaar
}

// Vuilbakje in de kolomtitel: alles wat nu getoond wordt (alle taken, of de gekozen taak)
async function deleteAllRuns() {
  const task = $("#task").value, n = runsData.runs.filter(x => !task || x.task === task).length;
  if (!n || !await ask(t("del_all_confirm", n, task ? taskName(task) : ""), { ok: t("dlg_delete"), danger: true })) return;
  const h = $("#hotel").value;
  await get(`/api/monitor/${h}/runs?all=1&task=${encodeURIComponent(task)}`, { method: "DELETE" });
  runsData.runs = runsData.runs.filter(x => task && x.task !== task);
  renderRuns(runsData);
}

async function deleteRun(id) {
  if (!await ask(t("del_confirm"), { ok: t("dlg_delete"), danger: true })) return;
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
  // Toestand kort in een label (ontwerp); de uitleg over het zelf starten staat eronder
  $("#robot-state").innerHTML = busy ? `<span class="badge b-info">${IC(P.clock, 14, 2.4)}${esc(t("rb_busy"))}</span>`
    : d.can_run ? `<span class="badge b-ok">${IC(P.check, 14, 2.4)}${esc(t("rb_idle"))}</span>` : `<span class="badge b-wait">${esc(t("not_installed"))}</span>`;
  if ($("#robot-help")) $("#robot-help").textContent = [t("rb_help"), d.can_run && d.cloud ? t("scheduled") : ""].filter(Boolean).join(" ");
  // Filter op taak: vaste keuzes, plus eventuele andere taken uit het logboek
  const sel = $("#task"), chosen = sel.value || taskFilter;
  const tasks = [...new Set([...TASKS, ...d.runs.map(x => x.task)])];
  sel.innerHTML = `<option value="">${t("all_tasks")}</option>` +
    tasks.map(k => `<option value="${esc(k)}">${esc(taskName(k))}</option>`).join("");
  sel.value = tasks.includes(chosen) ? chosen : "";
  const shown = d.runs.filter(x => !sel.value || x.task === sel.value);
  const execStart = Object.fromEntries((d.executions || []).map(e => [e.name, e.start]));
  // Per robotrun gegroepeerd: een kopregel met start, duur en resultaat van de hele run, daaronder de taken van
  // die run in volgorde (boven = eerst). Regels zonder run (bewaking, meldingen per mail, berichten) apart.
  const p = d.progress, now = Date.now();
  const age = p ? Math.round((now - new Date(p.updated)) / 1000) : null;
  // Live (core/progress.py). Klaar (done): alleen zolang Azure de run nog als bezig ziet (afsluiten duurt even)
  const showLive = p && (p.done ? busy : (busy || age < 180));
  const groups = new Map();
  for (const x of shown) {
    const key = x.execution ? "run:" + x.execution : "one:" + (x.id || x.started_at);
    if (!groups.has(key)) groups.set(key, { key, exec: x.execution || "", rows: [] });
    groups.get(key).rows.push(x);
  }
  let liveGroup = null;
  if (showLive) {
    liveGroup = p.run && groups.get("run:" + p.run);
    if (!liveGroup) {  // run nog zonder afgewerkte taak (net gestart): eigen groep bovenaan
      liveGroup = { key: "live", exec: p.run || "", rows: [] };
      groups.set("live", liveGroup);
    }
    liveGroup.live = p;
  }
  const first = g => g.live ? now : Math.max(...g.rows.map(x => +new Date(x.started_at)));
  const ordered = [...groups.values()].sort((a, b) => first(b) - first(a));
  const rel = (iso, t0) => { const s = Math.max(0, Math.round((new Date(iso) - t0) / 1000)); return `+${Math.floor(s / 60)}:${String(s % 60).padStart(2, "0")}`; };
  const counts = x => NO_COUNTS.includes(x.task) ? "<td></td><td></td>" : `<td>${x.found}</td><td>${x.new}</td>`;
  const bin = x => x.id ? `<button type="button" class="bin" data-id="${esc(x.id)}" title="${esc(t("del"))}" aria-label="${esc(t("del"))}">${BIN}</button>` : "";
  const rowHtml = (x, t0, inRun) => {
    const secs = (new Date(x.finished_at) - new Date(x.started_at)) / 1000;
    // Groen ok; oranje deels (enkele reservaties met een fout, de rest gelukt); rood alleen als de taak mislukte
    const partial = x.ok && Number(x.skipped || 0) > 0;
    const problem = !x.ok;
    return `<tr class="${inRun ? "run-step" : ""}"><td>${inRun ? `<span class="rel">${rel(x.started_at, t0)}</span> <span class="muted">${hms(x.started_at)}</span>` : stamp(x.started_at)}</td>
      <td>${Math.round(secs)} s${inRun ? "" : startText(x, execStart)}${timingText(x.timings)}</td>
      <td><span class="task task-${esc(x.task)}">${esc(taskName(x.task))}</span>${inRun ? "" : ` <span class="not-robot" title="${esc(t("not_robot_tip"))}">${t("not_robot")}</span>`}</td>
      <td><span class="badge ${problem ? "b-err" : partial ? "b-warn" : "b-ok"}">${problem ? t("fail") : (partial ? t("partial") : t("ok"))}</span></td>${counts(x)}
      <td class="wrap ${problem ? "err" : (partial ? "warn" : "")}">${esc(x.error)}</td><td>${bin(x)}</td></tr>`;
  };
  const liveHtml = (q, t0) => `<tr class="run-step live"><td><span class="rel">${rel(q.task_started, t0)}</span> <span class="muted">${hms(q.task_started)}</span></td>
      <td>${Math.round((now - new Date(q.task_started)) / 1000)} s</td>
      <td><span class="task task-${esc(q.task)}">${esc(taskName(q.task))}</span></td>
      <td class="${!q.done && age > 120 ? "err" : "running"}">${q.done ? "" : '<span class="spin"></span>'}${t(q.done ? "live_done" : "live_now")}</td><td></td><td></td>
      <td class="wrap">${esc(q.text)} ${q.done ? "" : `<span class="${age > 120 ? "err" : "muted"}">(${age > 120 ? t("live_quiet", age) : t("live_since", age)})</span>`}</td><td></td></tr>`;
  // Inklapbaar per run: standaard alleen de lopende of de laatste run open; wat je zelf open- of dichtklapt, blijft zo
  const firstRun = ordered.find(g => g.exec || g.live);
  const html = ordered.map(g => {
    const single = !g.exec && !g.live;
    if (single) return g.rows.map(x => rowHtml(x, 0, false)).join("");
    const rows = [...g.rows].sort((a, b) => new Date(a.started_at) - new Date(b.started_at));
    const starts = [execStart[g.exec], g.live && g.live.run_started, ...rows.map(x => x.process_started_at), ...rows.map(x => x.started_at)]
      .filter(Boolean).map(v => +new Date(v));
    const t0 = Math.min(...starts);
    const t1 = g.live ? now : Math.max(...rows.map(x => +new Date(x.finished_at)));
    const failed = rows.filter(x => !x.ok).length;
    const partials = rows.filter(x => x.ok && Number(x.skipped || 0) > 0).length;
    const running = g.live && !g.live.done;
    const state = running ? `<span class="spin"></span>${t("live_now")}` : (failed ? t("run_failed", failed) : (partials ? t("partial") : t("ok")));
    const tasks = rows.filter(x => x.task !== "robot").map(x => taskName(x.task));
    const rk = g.exec || "live";
    const open = rk in runOpen ? runOpen[rk] : g === firstRun;
    const head = `<tr class="run-head" data-toggle="${esc(rk)}" title="${esc(t(open ? "run_close" : "run_open"))}"><td><span class="caret-run">${open ? "\u25BE" : "\u25B8"}</span> ${stamp(new Date(t0).toISOString())}</td><td>${Math.round((t1 - t0) / 1000)} s${rows[0] ? startText(rows[0], execStart) : ""}</td>
      <td><span class="task task-robot">${t("run_label")}</span></td>
      <td><span class="badge ${running ? "b-info" : failed ? "b-err" : partials ? "b-warn" : "b-ok"}">${state}</span></td><td></td><td></td>
      <td class="wrap muted">${esc(tasks.length ? t("run_tasks", tasks.length) + ": " + tasks.join(", ") : (rows[0] && rows[0].error) || "")}</td><td></td></tr>`;
    const body = rows.filter(x => !(rows.length === 1 && x.task === "robot")).map(x => rowHtml(x, t0, true)).join("");
    const inner = (body + (g.live ? liveHtml(g.live, t0) : ""))
      .replaceAll('<tr class="run-step', `<tr data-run="${esc(rk)}"${open ? "" : " hidden"} class="run-step`);
    return head + inner;
  }).join("");
  $("#runs").innerHTML = html || `<tr><td colspan="8" class="muted">${t("no_runs")}</td></tr>`;
  if ($("#mruns")) {
    $("#mruns").innerHTML = ordered.filter(g => g.rows.length).slice(0, 20).map(g => {
      const rs = [...g.rows].sort((a, b) => new Date(a.started_at) - new Date(b.started_at));
      const t0 = Math.min(...rs.map(x => +new Date(x.started_at))), t1 = Math.max(...rs.map(x => +new Date(x.finished_at || x.started_at)));
      const failed = rs.filter(x => !x.ok).length, partials = rs.filter(x => x.ok && Number(x.skipped || 0) > 0).length;
      const badge = `<span class="badge ${failed ? "b-err" : partials ? "b-warn" : "b-ok"}">${esc(failed ? t("fail") : partials ? t("partial") : t("ok"))}</span>`;
      const rk = g.exec || g.key, open = rk in runOpen ? runOpen[rk] : g === firstRun;
      const secs = Math.round((t1 - t0) / 1000), dur = secs >= 60 ? `${Math.floor(secs / 60)} min ${secs % 60} s` : `${secs} s`;
      const todo = rs.reduce((n, x) => n + (Number(x.found) || 0), 0), done = rs.reduce((n, x) => n + (Number(x.new) || 0), 0);
      const steps = open ? rs.filter(x => x.task !== "robot").map(x => `<div class="li"><div class="lt small"><b>${esc(taskName(x.task))}</b><div class="muted">${esc([hms(x.started_at), Math.round((new Date(x.finished_at || x.started_at) - new Date(x.started_at)) / 1000) + " s", NO_COUNTS.includes(x.task) ? "" : `${x.new}/${x.found}`, x.error].filter(Boolean).join(" · "))}</div></div><span class="badge ${!x.ok ? "b-err" : Number(x.skipped || 0) > 0 ? "b-warn" : "b-ok"}">${esc(!x.ok ? t("fail") : Number(x.skipped || 0) > 0 ? t("partial") : t("ok"))}</span></div>`).join("") : "";
      const err = failed ? rs.find(x => x.error) : null;
      return `<section class="mcard"${failed ? ' style="box-shadow:0 0 0 2px #E6BDBD"' : ""}><button class="mrow btn3" type="button" data-mrun="${esc(rk)}" style="padding:0;text-decoration:none;color:#2B2F38;width:100%"><span><b>${esc(dday(new Date(t0).toISOString().slice(0, 10)))} ${esc(hms(new Date(t0).toISOString()).slice(0, 5))}</b> · ${esc(dur)}</span>${open ? IC('<path d="M6 9l6 6 6-6"/>', 18) : badge}</button>
        ${open ? `<div class="row">${badge}<span class="small">${esc(t("rb_done_m", done, todo))}</span></div>${steps}` : ""}${err && !open ? `<div class="small">${esc(err.error)}</div>` : ""}</section>`;
    }).join("") || `<div class="muted">${t("no_runs")}</div>`;
    document.querySelectorAll("#mruns [data-mrun]").forEach(b => b.onclick = () => { const k = b.dataset.mrun; runOpen[k] = !(k in runOpen ? runOpen[k] : false) || !b.parentElement.querySelector(".li"); renderRuns(runsData); });
  }
  document.querySelectorAll("#runs .bin").forEach(b => b.onclick = () => deleteRun(b.dataset.id));
  document.querySelectorAll("#runs tr[data-toggle]").forEach(tr => tr.onclick = () => {
    const k = tr.dataset.toggle, nowOpen = !tr.nextElementSibling || tr.nextElementSibling.hidden;
    runOpen[k] = nowOpen;
    document.querySelectorAll(`#runs tr[data-run="${CSS.escape(k)}"]`).forEach(r => { r.hidden = !nowOpen; });
    tr.querySelector(".caret-run").textContent = nowOpen ? "\u25BE" : "\u25B8";
  });
  // In de cloud: ook de runs volgens Azure (toont runs die mislukten voor ze iets konden noteren)
  // Runs volgens Azure: apart subtabblad, alleen in de cloud
  $("#sub-azure").hidden = !d.executions;
  if (!d.executions && subTab === "azure") showSub("log");
  $("#exec-wrap").hidden = false;
  $("#execs").innerHTML = (d.executions || []).slice(0, 10).map(e =>
    `<tr><td>${stamp(e.start)}</td><td>${stamp(e.end)}</td>
      <td>${e.start && e.end ? Math.round((new Date(e.end) - new Date(e.start)) / 1000) + " s" : ""}</td>
      <td><span class="badge ${e.status === "Succeeded" ? "b-ok" : e.status === "Failed" ? "b-err" : "b-info"}" title="${esc(e.name)}">${esc(e.status)}</span></td></tr>`).join("");
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

let wfStep = "";  // gekozen stap in de tijdlijn (Instellingen, Berichten)
function setDirty() { wfDirty = true; $("#wf-save").disabled = false; $("#wf-state").textContent = t("wfx_in_flow", t("flow_" + wfFlow)); $("#wf-savebar").hidden = false; }

function wfMeta() {
  if (!wf) return "";
  return wf.meta.source === "monitor" ? t("wf_changed", wf.meta.updated_by || "?", stamp(wf.meta.updated_at)) : t("wf_from_file");
}

function renderWorkflow() {
  if (!wf || !$("#wf-flows")) return;
  const c = wf.choices;
  $("#wf-flows").innerHTML = c.flows.map(f => `<label data-flow="${f}" class="${f === wfFlow ? "on" : ""}"><input type="radio" name="fl" ${f === wfFlow ? "checked" : ""}>${esc(t("flow_" + f))}</label>`).join("");
  document.querySelectorAll("#wf-flows label").forEach(b => b.onclick = e => { e.preventDefault(); wfFlow = b.dataset.flow; renderWorkflow(); });
  $("#wf-savebar").hidden = !wfDirty;
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
  // Ontwerp: tijdlijn van boeking tot na vertrek bovenaan, daaronder de gekozen stap
  if (!order.some(({ s }) => s.step === wfStep)) wfStep = (order.find(({ s }) => s.enabled) || order[0])?.s.step || "";
  const whenText = s => s.when === "after_booking" ? t("wf_right_after") : s.when === "days_after_departure" ? t("wf_days_after", s.days) : t("wf_days_before", s.days);
  const chans = s => (s.channels || []).map(x => t(CH[x] || x) || x).join(" + ");
  let markedArr = false, markedDep = false;
  $("#wf-flowline").innerHTML = order.map(({ s }, n) => {
    let mark = n === 0 ? t("wfx_booking") : "";
    if (!markedArr && s.when === "days_before_arrival" && s.days <= 2) { mark = t("wf_arrival"); markedArr = true; }
    if (!markedDep && s.when === "days_after_departure") { mark = t("wf_departure"); markedDep = true; }
    const icon = s.enabled ? '<path d="M3 5h18v14H3z"/><path d="M3.5 6.5l8.5 6.5 8.5-6.5"/>' : '<path d="M6 6l12 12M18 6L6 18"/>';
    return `<div class="fstep"><span class="fmark">${mark ? esc(mark) : "&nbsp;"}</span><span class="dot ${s.enabled ? "c-ok" : "c-off"}"><svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">${icon}</svg></span>${n < order.length - 1 ? '<span class="bar" style="top:32px"></span>' : ""}
      <a href="#" class="card2 ${s.step === wfStep ? "sel" : ""} ${s.enabled ? "" : "off"}" data-step="${esc(s.step)}"><b>${esc(stepShort(s.step))}</b><span class="small muted">${esc(s.enabled ? whenText(s) : t("pl_off"))}</span><span class="small">${esc(s.enabled ? chans(s) : t("sw_st_off"))}</span></a></div>`;
  }).join("");
  document.querySelectorAll("#wf-flowline [data-step]").forEach(a => a.onclick = e => { e.preventDefault(); wfStep = a.dataset.step; renderWorkflow(); });
  if ($("#wf-mflow")) {
    $("#wf-mflow").innerHTML = c.flows.map(f => `<option value="${f}" ${f === wfFlow ? "selected" : ""}>${esc(t("wf_flow_m", t("flow_" + f)))}</option>`).join("");
    $("#wf-mflow").onchange = () => { wfFlow = $("#wf-mflow").value; renderWorkflow(); };
    $("#wf-msteps").innerHTML = order.map(({ s }) => `<a href="#" class="li" data-mstep="${esc(s.step)}" style="text-decoration:none;color:#2B2F38;${s.step === wfStep ? "background:#EEF0F5;margin:0 -14px;padding:9px 14px" : ""}">
      <span class="c ${s.enabled ? "c-ok" : "c-off"}" style="width:26px;height:26px;border-radius:50%;display:flex;align-items:center;justify-content:center;flex:none">${IC(s.enabled ? P.mail : P.x, 13)}</span>
      <div class="lt"><b>${esc(stepShort(s.step))}</b><div class="small muted">${esc(s.enabled ? whenText(s) : t("pl_off"))}</div></div>${IC(s.step === wfStep ? '<path d="M6 9l6 6 6-6"/>' : '<path d="M9 6l6 6-6 6"/>', 18)}</a>`).join("");
    document.querySelectorAll("#wf-msteps [data-mstep]").forEach(a => a.onclick = e => { e.preventDefault(); wfStep = a.dataset.mstep; renderWorkflow(); });
  }
  const cur = order.find(({ s }) => s.step === wfStep);
  $("#wf-step-title").textContent = cur ? t("wfx_step", stepShort(cur.s.step)) : "";
  $("#wf-timeline").innerHTML = cur ? stepCard(cur.s, cur.i, flow, c) : "";
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
          <div><span class="lbl">${esc(t("f_channels"))}</span>${checks("channels", i, c.channels, s.channels || ["email"], x => t("wfch_" + x))}</div>
          <div><span class="lbl">${esc(t("f_only_if"))}</span>${checks("only_if", i, c.conditions, s.only_if, x => t("c_" + x))}</div>
          ${s.when === "days_before_arrival" ? `<label class="chk"><input type="checkbox" data-i="${i}" data-f="skip_if_booked_late" ${s.skip_if_booked_late ? "checked" : ""}> ${esc(t("f_late"))}</label>` : ""}
        </div>
      </div>
      <div class="group">
        <div class="group-title">${esc(t("f_rates"))}</div>
        <div class="table-wrap"><table class="rates">
          <tr><th></th>${SECTIONS.map(m => `<th>${esc(t("m_" + m))}</th>`).join("")}</tr>
          ${RATES.map(rate => {
            const sec = sectionsOf(s, rate), off = !SECTIONS.some(m => sec[m]);
            return `<tr class="${off ? "off" : ""}"><th>${esc(t("rate_" + rate))}<br>${off ? `<span class="muted small">${esc(t("rate_row_off"))}</span>`
                : `<button type="button" class="link small" data-preview="${i}" data-rate="${rate}">${esc(t("rate_example"))}</button>`}</th>
              ${SECTIONS.map(m => `<td><input type="checkbox" aria-label="${esc(t("rate_" + rate) + ": " + t("m_" + m))}" data-i="${i}" data-f="rate" data-rate="${rate}" value="${m}" ${sec[m] ? "checked" : ""}></td>`).join("")}</tr>`;
          }).join("")}
        </table></div>
        <p class="muted small">${esc(t("wf_rule_code"))}<br>${esc(t("wf_rule_pay"))}<br>${esc(t("wf_rule_form"))}</p>
      </div>
    </div></div>`;
}

const CONTENT = ["reservation", "checkin_form", "code", "practical_info"];
const DEFAULT_CONTENT = {
  confirmation: { reservation: true, checkin_form: true, code: false, practical_info: false },
  reminder: { reservation: true, checkin_form: true, code: false, practical_info: false },
  access_code: { reservation: false, checkin_form: false, code: true, practical_info: true },
  thank_you: { reservation: false, checkin_form: false, code: false, practical_info: false },
};
const contentOf = s => ({ ...(DEFAULT_CONTENT[s.step] || {}), ...(s.content || {}) });
const RATES = ["nfr", "standard"];
const SECTIONS = ["message", ...CONTENT, "pay"];
// Onderdelen per tarief; zonder keuze per tarief wat de stap had (content en pay)
const sectionsOf = (s, rate) => {
  const base = { message: true, ...contentOf(s), pay: s.pay !== "none" };
  return Object.fromEntries(SECTIONS.map(m => [m, !!({ ...base, ...((s.rates || {})[rate] || {}) })[m]]));
};

// Voorbeeldmail: de stap zoals ze nu op het scherm staat (ook als ze nog niet bewaard is)
let pvStep = null, pvLang = "nl", pvRate = "standard";
async function showPreview(step, rate) {
  pvStep = step; pvRate = rate || pvRate;
  $("#preview").hidden = false;
  $("#pv-title").textContent = `${t("wf_example")}: ${t("step_" + step.step)} (${t("flow_" + wfFlow)}, ${t("rate_" + pvRate)})`;
  $("#pv-langs").innerHTML = ["nl", "fr", "en", "de", "es"].map(l => `<button type="button" data-l="${l}" class="${l === pvLang ? "active" : ""}">${l.toUpperCase()}</button>`).join("");
  document.querySelectorAll("#pv-langs button").forEach(b => b.onclick = () => { pvLang = b.dataset.l; showPreview(pvStep); });
  const r = await apiFetch(API + `/api/monitor/${$("#hotel").value}/preview`, {
    method: "POST", headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ step, flow: wfFlow, rate: pvRate, language: pvLang, parameters: wf.parameters }),
  });
  const d = await r.json().catch(() => ({}));
  $("#pv-subject").textContent = d.error ? d.error : `${t("pv_subject")}: ${d.subject}`;
  // Links in de voorbeeldmail (check-in-formulier, website, ...) openen in een nieuw tabblad
  const html = d.html || "";
  $("#pv-frame").srcdoc = /<head[\s>]/i.test(html) ? html.replace(/<head([^>]*)>/i, '<head$1><base target="_blank">') : '<base target="_blank">' + html;
}

function bindSteps(flow) {
  document.querySelectorAll("#wf-timeline [data-preview]").forEach(b => b.onclick = () => showPreview(flow.steps[+b.dataset.preview], b.dataset.rate));
  document.querySelectorAll("#wf-timeline [data-f]").forEach(el => el.onchange = () => {
    const s = flow.steps[+el.dataset.i], f = el.dataset.f;
    if (f === "rate") {
      s.rates = Object.fromEntries(RATES.map(r => [r, sectionsOf(s, r)]));
      s.rates[el.dataset.rate][el.value] = el.checked;
    } else if (f === "content") {
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
  const rule = flow.sources.length
    ? `<label>${esc(t("wf_sources"))}<input id="wf-sources" type="text" value="${esc(flow.sources.join(", "))}"></label>`
    : `<p>${esc(t("wf_other"))} ${esc(t(flow.paid ? "wf_paid_yes" : "wf_paid_no"))}</p>`;
  $("#wf-side").innerHTML = `
    <h3>${esc(t("wf_rules"))}</h3>${rule}
    ${(wf.seen_sources?.[wfFlow] || []).length ? `<p class="small"><span class="lbl">${esc(t("wf_seen"))}</span><br>${wf.seen_sources[wfFlow].map(([v, n]) => `<span class="tag">${esc(v)} (${n})</span>`).join(" ")}</p>` : `<p class="muted small">${esc(t("wf_seen_none"))}</p>`}
    <p class="muted small">${esc(t("wf_params_moved"))}</p>`;
  const src = $("#wf-sources");
  if (src) src.onchange = () => { flow.sources = src.value.split(",").map(x => x.trim()).filter(Boolean); setDirty(); };
}

async function saveWorkflow() {
  const r = await apiFetch(API + `/api/monitor/${$("#hotel").value}/workflow`, {
    method: "POST", headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ parameters: wf.parameters, flows: wf.flows }),
  });
  const d = await r.json().catch(() => ({}));
  if (!r.ok) { $("#wf-state").textContent = d.error || `${t("load_error")} ${r.status}`; $("#wf-state").className = "err"; return; }
  wf = d; wfDirty = false;
  $("#wf-state").className = "muted";
  $("#wf-state").textContent = t("wf_saved");
  const y = window.scrollY;  // na bewaren blijven waar je was
  renderWorkflow();
  window.scrollTo(0, y);
}

async function resetWorkflow() {
  if (!await ask(t("wf_reset_confirm"), { ok: t("dlg_reset"), danger: true })) return;
  wf = await get(`/api/monitor/${$("#hotel").value}/workflow?action=reset`, { method: "POST" });
  wfDirty = false;
  $("#wf-state").textContent = "";
  renderWorkflow();
}


// Labels en uitleg van de instellingen (tabblad Hotel), per taal: sectie.sleutel -> [label, uitleg]
const HS_TEXT = {
 "nl": {
  "fields": {
   "reviews.google_url": ["Google", "Link om een review te schrijven op Google, als knop in de bedankmail. Leeg = geen knop."],
   "reviews.other_url": ["Andere site", "Bv. Tripadvisor. Leeg = geen knop."],
   "workflow_parameters.city_tax_amount": ["Toeristenbelasting", "Bedrag per persoon (per nacht of per verblijf, zie hieronder). Komt in de mails met een betaalknop."],
   "workflow_parameters.city_tax_unit": ["Per", ""],
   "workflow_parameters.currency": ["Munt", "Bv. EUR."],
   "test.email": [
  "Testadres e-mail",
  "In TST en de codespace gaat elke mail hierheen, nooit naar de gast. Leeg = geen mails."
 ],
 "test.phone": [
  "Testnummer sms en WhatsApp",
  "In TST en de codespace gaat elke sms en WhatsApp hierheen. Leeg = niets versturen."
 ],
 "hotel.naam": [
    "Naam",
    ""
   ],
   "hotel.adres": [
    "Adres",
    "Staat in de mails en onderaan het formulier."
   ],
   "hotel.telefoon": [
    "Telefoon",
    "Contactnummer voor gasten."
   ],
   "hotel.email": [
    "E-mail",
    "Contactadres voor gasten. Antwoorden op de mails komen hier aan."
   ],
   "hotel.website": [
    "Website",
    "Algemeen adres, gebruikt als er geen adres voor de taal is."
   ],
   "hotel.website_nl": [
    "Website (Nederlands)",
    "Logo en link onderaan de Nederlandstalige mails."
   ],
   "hotel.website_fr": [
    "Website (Frans)",
    "Logo en link onderaan de Franstalige mails."
   ],
   "hotel.website_en": [
    "Website (Engels)",
    "Logo en link onderaan de Engelstalige mails."
   ],
   "hotel.website_de": [
    "Website (Duits)",
    "Logo en link onderaan de Duitstalige mails."
   ],
   "hotel.logo_url": [
    "Logo",
    "Adres van de afbeelding bovenaan de mails en het formulier."
   ],
   "hotel.favicon_url": [
    "Icoon van de gast-app",
    "Vierkante afbeelding (bv. 192 x 192) voor het tabblad en het beginscherm van de gsm, liefst dezelfde als op de website. Leeg = standaardicoon."
   ],
   "verzending.mail_afzender": [
    "Afzender",
    "Mailbox waarmee de mails technisch verstuurd worden. Gasten antwoorden naar het contactadres van het hotel."
   ],
   "receptie.van": [
    "Open vanaf",
    "Ook het uur vanaf wanneer de pincode werkt."
   ],
   "receptie.tot": [
    "Open tot",
    ""
   ],
   "checkout.tot": [
    "Uitchecken tot",
    "Ook het uur tot wanneer de pincode werkt op de dag van vertrek."
   ],
   "ontbijt.van": [
    "Van",
    ""
   ],
   "ontbijt.tot": [
    "Tot",
    ""
   ],
   "betaalverzoek.template": [
    "Template in Lighthouse",
    "Naam van de e-mail template voor betaalverzoeken in Lighthouse."
   ],
   "betaalverzoek.dagen_vooraf": [
    "Dagen vooraf",
    "Zoveel dagen voor een mail met betaalknop maakt de robot het betaalverzoek (mail naar de eigen mailbox)."
   ],
   "ontbijt.label": [
    "Label op het planbord",
    "Naam van het label in Lighthouse dat de robot zet bij wie ontbijt heeft (hoofdschakelaar Ontbijt labels)."
   ],
   "ontbijt.label_dagen": [
    "Label voor aankomsten binnen",
    "Aantal dagen vooruit dat de robot het ontbijtlabel zet. 0 = alle toekomstige reservaties."
   ],
   "wifi.per_kamer": ["Eigen netwerk per kamer", "Aan: elke kamer heeft een eigen, privé wifinetwerk; de mail zegt de QR-code op de kamer te scannen. Uit: één netwerk voor iedereen, met de naam en het wachtwoord hieronder."],
   "wifi.naam": [
    "Netwerk",
    "Alleen als het netwerk niet per kamer is: naam van het wifinetwerk voor gasten. Leeg = geen wifiregel in de mail."
   ],
   "wifi.wachtwoord": [
    "Wachtwoord",
    "Alleen als het netwerk niet per kamer is. Staat in de mail met de praktische info."
   ],
   "parking.naam": [
    "Parking",
    "Aanbevolen parking."
   ],
   "parking.minuten": [
    "Minuten te voet",
    ""
   ],
   "nood.nummer": [
    "Noodnummer",
    "Voor 's avonds en 's nachts, als de receptie dicht is."
   ],
   "twilio.sms_from": [
    "Afzender sms",
    "Nummer waarmee de sms'en verstuurd worden."
   ],
   "twilio.whatsapp_from": [
    "Afzender WhatsApp",
    "WhatsApp Business-nummer van het hotel."
   ],
   "robot.check_minutes": [
    "Vangnet: om de hoeveel minuten",
    "Normaal start de meldingsmail van Lighthouse de robot. Daarnaast start hij als vangnet op vaste uren vanaf middernacht: 60 = elk heel uur, 240 = 00:00, 04:00, 08:00, ... Uit die uren kies je ook het uur van de ontbijt- en schoonmaaklijst. 0 = nooit op schema. Met alle hoofdschakelaars uit start hij nooit."
   ],
   "doorschakelen.receptie_van": [
    "Receptie bereikbaar: vanaf",
    "Vanaf dit uur gaan oproepen naar het Twilio-nummer naar de vaste lijn van de receptie."
   ],
   "doorschakelen.receptie_tot": [
    "Receptie bereikbaar: tot",
    ""
   ],
   "doorschakelen.receptie_nummer": [
    "Vaste lijn receptie",
    "Leeg = tijdens de receptie-uren naar de telefoon van het hotel."
   ],
   "doorschakelen.avond_van": [
    "Oproepen 's avonds: vanaf",
    "Vanaf dit uur gaan oproepen naar het Twilio-nummer naar het noodnummer. Buiten de receptie-uren en de avond gaan ze naar de telefoon van het hotel. Leeg = geen avondperiode."
   ],
   "doorschakelen.avond_tot": [
    "Oproepen 's avonds: tot",
    "Tot dit uur 's morgens gaan oproepen naar het noodnummer."
   ],
   "robot.nacht_van": [
    "Nacht: van",
    "Vanaf dit uur start de robot alleen op de nachtelijke uren hieronder, niet elk uur en niet door een meldingsmail. Leeg = geen nacht."
   ],
   "robot.nacht_tot": [
    "Nacht: tot",
    "Tot dit uur. Meldingsmails van 's nachts starten de robot dan."
   ],
   "robot.nacht_uren": [
    "Nacht: robot om",
    "Uren waarop de robot 's nachts toch draait, bv. 01:00, 04:00. Hoogstens 3."
   ],
   "robot.contact_refresh_hours": [
    "Reservaties bijwerken: om de hoeveel uur",
    "Contactgegevens, kamer, data en betaling opnieuw lezen voor reservaties die binnenkort aankomen."
   ],
   "robot.mail_trigger": [
    "Starten bij meldingsmail",
    "De robot start meteen als Lighthouse een mail stuurt over een nieuwe of gewijzigde boeking."
   ],
   "schakelaars.overschrijvingen": [
    "Overschrijvingen Booking.com",
    "De robot registreert in Lighthouse de betaling door Booking.com (overschrijving of virtuele kaart) als Overschrijving. Alleen niet-annuleerbaar (meteen) of vanaf 2 dagen voor aankomst. Geldt alleen voor deze omgeving."
   ],
   "schakelaars.ontbijt_labels": [
    "Ontbijt labels plaatsen",
    "De robot zet het label ONTBIJT op het planbord bij wie ontbijt heeft (tarief met ontbijt, of ontbijt voor alle personen en nachten in de folio). Geldt alleen voor deze omgeving."
   ],
   "schakelaars.ontgrendelen": ["Deuren openen met de gast-app", "Gasten kunnen tijdens hun verblijf de voordeur en hun kamer openen met een schuifknop in de gast-app (Salto, op afstand openen). Alleen met een code, binnen de periode van de code. De pincode blijft altijd werken. Geldt alleen voor deze omgeving; buiten PRD alleen voor testgasten."],
   "schakelaars.reservaties": ["Reservaties lezen (robot)", "De robot leest nieuwe en gewijzigde reservaties in Lighthouse. Staan alle hoofdschakelaars uit, dan is deze omgeving bevroren: de robot start niet meer en opent Lighthouse niet. Geldt alleen voor deze omgeving."],
   "schakelaars.ontbijtlijst": ["Ontbijtlijst maken en versturen", "Elke dag de ontbijtlijst maken en versturen (instellingen Ontbijtlijst). In de monitor (tabblad Ontbijt) kan een lijst ook met de schakelaar uit gemaakt worden. Geldt alleen voor deze omgeving."],
   "schakelaars.kuislijst": ["Schoonmaaklijst maken en versturen", "Elke dag de schoonmaaklijst maken en versturen (instellingen Schoonmaaklijst). In de monitor (tabblad Schoonmaak) kan een lijst ook met de schakelaar uit gemaakt worden. Geldt alleen voor deze omgeving."],
   "ontbijtlijst.uur": ["Uur", "Elke dag om dit uur maken en versturen. Je kiest uit de vaste uren van de robot (instelling Robot: om de hoeveel minuten): de lijst gebruikt de robotrun van dat uur, dus geen extra run. Klaar na enkele minuten."],
   "ontbijtlijst.dag": ["Voor welke dag", "1 = morgen, 0 = vandaag."],
   "ontbijtlijst.email": ["Per mail naar", "Mail met de lijst en de Excel als bijlage. Meer adressen met een komma. Leeg = geen mail."],
   "ontbijtlijst.whatsapp": ["Per WhatsApp naar", "Gsm-nummers (+32...), met een komma. WhatsApp met de lijst als pdf (sjabloon: tabblad WhatsApp), anders per sms. Pas als WhatsApp en sms aan staan."],
   "ontbijtlijst.samen_tekst": ["Tekst bij meerdere kamers", "Eén reservatie met meer kamers: bij elke kamer de andere, {rooms} = de kamers. Leeg = niet vermelden."],
   "ontbijtlijst.woorden": ["Woorden voor opmerkingen", "Zinnen uit de opmerking of de folio van de reservatie met een van deze woorden komen bij de opmerkingen (bv. glutenvrij)."],
   "kuislijst.uur": ["Uur", "Elke dag om dit uur maken en versturen. Je kiest uit de vaste uren van de robot (instelling Robot: om de hoeveel minuten): de lijst gebruikt de robotrun van dat uur, dus geen extra run. Klaar na enkele minuten."],
   "kuislijst.dag": ["Voor welke dag", "1 = morgen, 0 = vandaag."],
   "kuislijst.email": ["Per mail naar", "Mail met de lijst en de Excel als bijlage. Meer adressen met een komma. Leeg = geen mail."],
   "kuislijst.whatsapp": ["Per WhatsApp naar", "Gsm-nummers (+32...), met een komma. WhatsApp met de lijst als pdf (sjabloon: tabblad WhatsApp), anders per sms. Pas als WhatsApp en sms aan staan."],
   "kuislijst.controle": ["Controle", "Functie bovenaan de lijst (Controle: ...), geen naam. Leeg = geen regel."],
   "kuislijst.extra_rijen": ["Vaste rijen onderaan", "Bv. TOILETTEN. Meer rijen met een komma."],
   "kuislijst.labels": ["Labels als opmerking", "Labels op het planbord in Lighthouse die bij de opmerkingen komen, bv. BABY BED. Meer labels met een komma."],
   "hotel.tijdzone": ["Tijdzone", "Voor de kalender van de workflow (herinnering, code-mail, opruimen), bv. Europe/Brussels."],
   "test.guest_names": ["Testgasten (achternaam)", "Reservaties van deze gasten zijn testreservaties: de robot mag er ook in TST in Lighthouse schrijven. Echte reservaties leest TST alleen. Meer namen met een komma."],
   "checkout.kamer_tot": ["Kamerdeur open tot", "Op de dag van vertrek werkt de code aan de kamerdeur nog tot dit uur (marge na de check-out, niet in de mails)."],
   "checkout.voordeur_tot": ["Voordeur open tot", "Op de dag van vertrek werkt de code aan de voordeur (en andere gemeenschappelijke deuren) nog tot dit uur, bv. om de bagage op te halen."],
   "twilio.contact_whatsapp": ["WhatsApp-nummer van het hotel", "Antwoordt een gast op het nummer van de automatische berichten, dan krijgt hij dit nummer (WhatsApp Business-app van het hotel) in een automatisch antwoord."],
   "twilio.doorsturen": ["Antwoorden doorsturen naar", "Antwoorden van gasten op de automatische berichten gaan per mail naar deze adressen. Meer adressen met een komma."],
   "salto.pin_lengte": ["Lengte van de pincode", "Eigen gekozen pincodes van dit aantal cijfers (vraagt Custom Pin, Salto KS Pro). Leeg = Salto kiest de code."],
   "salto.max_gebruikers": ["Maximum gebruikers", "Maximum aantal gebruikers van het abonnement bij Salto (personeel inbegrepen). Leeg = niet nakijken."],
   "kamers.verdieping_regel": ["Verdieping uit het kamernummer", "eerste_cijfer: het eerste cijfer van het kamernummer is de verdieping (12 = 1e verdieping). geen: nooit een verdieping tonen. Kamers die afwijken staan bij de uitzonderingen."],
   "beheer.prd_vrijgeven": ["Mag naar PRD zetten", "Wie op TST een geteste herstelling voor Lighthouse naar PRD mag zetten: het e-mailadres waarmee je je aanmeldt. Meer adressen met een komma."],
   "bewaking.email": ["Mail naar", "Wie het dagelijkse overzicht en de waarschuwingen krijgt. Meer adressen met een komma."],
   "bewaking.overzicht_uur": ["Dagelijks overzicht om", "Uur van de mail met de aankomsten van vandaag en morgen."],
   "bewaking.controle_uren": ["Extra controles om", "Uren waarop de aankomsten nog eens nagekeken worden (mail alleen bij een probleem). Leeg = geen."],
   "bewaking.monitoring": ["Monitoring", "Meteen een mail als de robot een gepland uur mist, als Lighthouse veranderd is, als er een oplossing klaarstaat om te testen en als het opgelost is. De herstelrobot zoekt dan zelf een oplossing. Uit: alleen het dagelijkse overzicht."],
   "bewaking.robot_max_uren": ["Robot: alarm na (uren)", "Alleen als er geen vast schema voor de robot is. Anders telt het geplande uur."],
   "kuislijst.personen": ["Aantal personen tonen", "Bij check in het aantal personen bij de opmerkingen."],
   "kuislijst.opmerkingen": ["Vrije opmerkingen tonen", "Opmerkingen uit de reservatie (bv. van Booking.com). Uit = alleen labels zoals BABY BED en DOUBLE OPMAKEN en de memo bij SPECIAAL VERZOEK."],
   "kuislijst.labels_twin": ["Labels alleen op een twin kamer", "Bv. DOUBLE OPMAKEN: komt alleen bij de opmerkingen van een twin kamer (in het hotelbestand: [kamers.<nummer>] twin)."],
   "kuislijst.labels_memo": ["Labels met interne memo", "Bv. SPECIAAL VERZOEK: de interne memo van de reservatie komt bij de opmerkingen."],
   "kuislijst.woorden": ["Woorden voor opmerkingen", "Zinnen uit de opmerking of de folio van de reservatie met een van deze woorden komen bij de opmerkingen (bv. babybed, romantisch)."],
   "kamers.lijst_volgorde": ["Kamers op de ontbijt- en schoonmaaklijst", "In deze volgorde, met een komma; - = lege rij (nieuwe verdieping). Naast het nummer komt de omschrijving uit Lighthouse. Een kamer die hier niet in staat (bv. nog buiten dienst), komt alleen achteraan op een dag met een reservatie."],
   "kamers.20.lijst": ["Naam op de lijsten", "Eigen naam in plaats van het nummer op de ontbijt- en schoonmaaklijst (bv. App). Leeg = het nummer."],
   "schakelaars.berichten": [
    "Gastcommunicatie",
    "Mails, sms en WhatsApp aan gasten, en de pincodes bij Salto. Uit = niets naar gasten en geen codes. Aan = voor alle reservaties, behalve die waarvoor je de berichten uitzet (berichtenvenster van de reservatie). Selectie = alleen voor de reservaties waarvoor je ze aanzet, om te testen. Geldt alleen voor deze omgeving; buiten PRD gaat alles naar de testadressen."
   ],
   "messaging.start": [
    "Vanaf",
    "Alleen reservaties die vanaf dit moment binnenkomen krijgen berichten."
   ],
   "messaging.phone": [
    "WhatsApp en sms",
    "Naast de mail ook WhatsApp (met sms als terugval). Aan zodra Twilio betaald is."
   ],
   "retention.reservation_days": [
    "Reservaties bewaren (dagen na vertrek)",
    "Daarna worden de reservatie en haar berichten gewist. Gastprofielen blijven."
   ],
   "retention.guest_days": [
    "Gasten bewaren (dagen na laatste verblijf)",
    "Daarna wordt het gastprofiel gewist. 0 = altijd bewaren."
   ],
   "salto.identity_url": [
    "Aanmeldserver",
    "Test of productie van Salto."
   ],
   "salto.api_url": [
    "API-adres",
    ""
   ],
   "salto.site_id": [
    "Site",
    "Id van het hotel bij Salto. Leeg = Salto staat uit."
   ],
   "salto.guest_role_id": [
    "Gastenrol",
    "Leeg = de rol met 'guest' of 'gast' in de naam."
   ],
   "salto.common_lock_ids": [
    "Gemeenschappelijke deuren",
    "Ids van de voordeur en andere deuren voor alle gasten, met komma's ertussen."
   ],
   "lighthouse.base_url": [
    "Adres",
    "Adres van Reservation Manager."
   ],
   "checkin.trappen_vraag_nl": ["Trappen: vraag (NL)", "Aanvinkvakje op het formulier: een van de gasten kan moeilijk trappen lopen. Leeg = de vraag staat er niet."],
   "checkin.trappen_uitleg_nl": ["Trappen: uitleg (NL)", "Tekst onder de vraag."],
   "checkin.trappen_vraag_fr": ["Trappen: vraag (FR)", "Aanvinkvakje op het formulier: een van de gasten kan moeilijk trappen lopen. Leeg = de vraag staat er niet."],
   "checkin.trappen_uitleg_fr": ["Trappen: uitleg (FR)", "Tekst onder de vraag."],
   "checkin.trappen_vraag_en": ["Trappen: vraag (EN)", "Aanvinkvakje op het formulier: een van de gasten kan moeilijk trappen lopen. Leeg = de vraag staat er niet."],
   "checkin.trappen_uitleg_en": ["Trappen: uitleg (EN)", "Tekst onder de vraag."],
   "checkin.trappen_vraag_de": ["Trappen: vraag (DE)", "Aanvinkvakje op het formulier: een van de gasten kan moeilijk trappen lopen. Leeg = de vraag staat er niet."],
   "checkin.trappen_uitleg_de": ["Trappen: uitleg (DE)", "Tekst onder de vraag."],
   "checkin.trappen_niet_bij": ["Trappen: niet bij kamertype", "De vraag staat niet op het formulier als het kamertype een van deze woorden bevat (bv. appartement, suite): daar kan het hotel niet van kamer wisselen."],
   "checkin.trappen_memo": ["Trappen: regel in de interne memo", "De robot zet deze regel achteraan de interne memo in Lighthouse (alleen aanvullen, alleen PRD)."],
   "checkin.trappen_label": ["Trappen: label op het planbord", "Bv. NIET VERPLAATSEN. Alleen als de gast al op een lage verdieping ligt (zie hieronder); later naar beneden verplaatst: alsnog. Leeg = geen label."],
   "checkin.trappen_label_verdieping": ["Trappen: lage verdieping tot", "Het label komt er alleen als alle kamers op deze verdieping of lager liggen (1 = gelijkvloers en 1e verdieping)."],
   "checkin.formulier_url": [
    "Adres van het formulier",
    "{token} wordt per gast ingevuld. In TST gaat de link naar het testformulier."
   ],
   "privacy.url_nl": [
    "Nederlands",
    ""
   ],
   "privacy.url_fr": [
    "Frans",
    ""
   ],
   "privacy.url_en": [
    "Engels",
    ""
   ],
   "privacy.url_de": [
    "Duits",
    ""
   ],
   "kleuren.accent": [
    "Accent",
    "Kader rond de pincode en lijnen."
   ],
   "kleuren.accent_donker": [
    "Accent donker",
    "Knoppen en titels."
   ],
   "kleuren.tekst": [
    "Tekst",
    ""
   ],
   "kleuren.achtergrond": [
    "Achtergrond",
    ""
   ]
  },
  "sections": {
   "hotel": "Gegevens die gasten zien in de mails en op het formulier.",
   "doorschakelen": "Wie het nummer van de automatische berichten belt, wordt doorgeschakeld: tijdens de receptie-uren naar de vaste lijn, 's avonds naar het noodnummer, anders naar de telefoon van het hotel.",
   "twilio": "Het Twilio-account zelf staat in Key Vault.",
   "robot": "De robot leest Lighthouse (alleen lezen).",
   "schakelaars": "Hoofdschakelaars: wat het systeem echt mag doen. Standaard uit, per omgeving apart.",
   "ontbijtlijst": "Dagelijkse ontbijtlijst: per kamer het aantal personen met ontbijt. Aan of uit met de hoofdschakelaar Ontbijtlijst.",
   "kuislijst": "Dagelijkse schoonmaaklijst: per kamer vertrek, blijft of check in, met opmerkingen. Aan of uit met de hoofdschakelaar Schoonmaaklijst.",
   "kuislijst.wensen": "De robot leest de opmerking van de gast, de folio en de interne memo. Staat er een van de woorden in (in welke taal ook), dan komt links de korte opmerking op de schoonmaaklijst, nooit de tekst zelf. Woorden met een komma; met kort ervoor geen, no, pas de of kein telt het niet.",
   "messaging": "Berichten uit de workflow.",
   "whatsapp": "Door Meta goedgekeurde sjablonen per bericht en taal, bv. template_confirmation_nl = HX... Zonder sjabloon gaat het bericht per sms.",
   "retention": "Opruimen gebeurt bij Synchroniseren op het tabblad Gasten.",
   "salto": "Aanmeldgegevens staan in Key Vault.",
   "salto.rooms": "Per kamer de deur bij Salto: kamernummer = id van de deur.",
   "lighthouse": "De robotgebruiker staat in Key Vault.",
   "privacy": "Link naar de privacyverklaring per taal.",
   "kleuren": "Kleuren van de mails en het formulier."
  }
 },
 "en": {
  "fields": {
   "reviews.google_url": ["Google", "Link to write a review on Google, as a button in the thank-you mail. Empty = no button."],
   "reviews.other_url": ["Other site", "E.g. Tripadvisor. Empty = no button."],
   "workflow_parameters.city_tax_amount": ["City tax", "Amount per person (per night or per stay, see below). Used in mails with a pay button."],
   "workflow_parameters.city_tax_unit": ["Per", ""],
   "workflow_parameters.currency": ["Currency", "E.g. EUR."],
   "test.email": [
  "Test e-mail address",
  "In TST and the codespace every mail goes here, never to the guest. Empty = no mails."
 ],
 "test.phone": [
  "Test number SMS and WhatsApp",
  "In TST and the codespace every SMS and WhatsApp goes here. Empty = nothing sent."
 ],
 "hotel.naam": [
    "Name",
    ""
   ],
   "hotel.adres": [
    "Address",
    "Shown in the mails and at the bottom of the form."
   ],
   "hotel.telefoon": [
    "Phone",
    "Contact number for guests."
   ],
   "hotel.email": [
    "E-mail",
    "Contact address for guests. Replies to the mails arrive here."
   ],
   "hotel.website": [
    "Website",
    "General address, used when there is no address for the language."
   ],
   "hotel.website_nl": [
    "Website (Dutch)",
    "Logo and link at the bottom of Dutch mails."
   ],
   "hotel.website_fr": [
    "Website (French)",
    "Logo and link at the bottom of French mails."
   ],
   "hotel.website_en": [
    "Website (English)",
    "Logo and link at the bottom of English mails."
   ],
   "hotel.website_de": [
    "Website (German)",
    "Logo and link at the bottom of German mails."
   ],
   "hotel.logo_url": [
    "Logo",
    "Address of the image at the top of the mails and the form."
   ],
   "hotel.favicon_url": [
    "Guest app icon",
    "Square image (e.g. 192 x 192) for the browser tab and the phone home screen, preferably the same as on the website. Empty = default icon."
   ],
   "verzending.mail_afzender": [
    "Sender",
    "Mailbox used to send the mails. Guests reply to the hotel's contact address."
   ],
   "receptie.van": [
    "Open from",
    "Also the time from which the PIN code works."
   ],
   "receptie.tot": [
    "Open until",
    ""
   ],
   "checkout.tot": [
    "Check out until",
    "Also the time until which the PIN code works on the day of departure."
   ],
   "ontbijt.van": [
    "From",
    ""
   ],
   "ontbijt.tot": [
    "Until",
    ""
   ],
   "betaalverzoek.template": [
    "Template in Lighthouse",
    "Name of the e-mail template for payment requests in Lighthouse."
   ],
   "betaalverzoek.dagen_vooraf": [
    "Days ahead",
    "This many days before a mail with a pay button the robot creates the payment request (mail to our own mailbox)."
   ],
   "ontbijt.label": [
    "Label on the planboard",
    "Name of the Lighthouse label the robot sets for guests with breakfast (main switch Breakfast labels)."
   ],
   "ontbijt.label_dagen": [
    "Label for arrivals within",
    "Number of days ahead for which the robot sets the breakfast label. 0 = all future reservations."
   ],
   "wifi.per_kamer": ["Own network per room", "On: every room has its own private Wi-Fi network; the mail tells guests to scan the QR code in the room. Off: one network for everyone, with the name and password below."],
   "wifi.naam": [
    "Network",
    "Only when the network is not per room: name of the guest Wi-Fi network. Empty = no Wi-Fi line in the mail."
   ],
   "wifi.wachtwoord": [
    "Password",
    "Only when the network is not per room. Shown in the mail with practical info."
   ],
   "parking.naam": [
    "Car park",
    "Recommended car park."
   ],
   "parking.minuten": [
    "Minutes on foot",
    ""
   ],
   "nood.nummer": [
    "Emergency number",
    "For evenings and nights, when reception is closed."
   ],
   "twilio.sms_from": [
    "SMS sender",
    "Number used to send text messages."
   ],
   "twilio.whatsapp_from": [
    "WhatsApp sender",
    "The hotel's WhatsApp Business number."
   ],
   "robot.check_minutes": [
    "Safety net: every how many minutes",
    "Normally the Lighthouse notification mail starts the robot. It also starts as a safety net at fixed times from midnight: 60 = every full hour, 240 = 00:00, 04:00, 08:00, ... The time of the breakfast and cleaning list is chosen from these times. 0 = never on schedule. With all main switches off it never starts."
   ],
   "doorschakelen.receptie_van": [
    "Reception reachable: from",
    "From this time, calls to the Twilio number go to the reception landline."
   ],
   "doorschakelen.receptie_tot": [
    "Reception reachable: until",
    ""
   ],
   "doorschakelen.receptie_nummer": [
    "Reception landline",
    "Empty = during reception hours to the hotel phone."
   ],
   "doorschakelen.avond_van": [
    "Evening calls: from",
    "From this time, calls to the Twilio number go to the emergency number. Outside reception hours and the evening they go to the hotel phone. Empty = no evening period."
   ],
   "doorschakelen.avond_tot": [
    "Evening calls: until",
    "Until this time in the morning, calls go to the emergency number."
   ],
   "robot.nacht_van": [
    "Night: from",
    "From this time the robot only starts at the night times below, not every hour and not from a notification mail. Empty = no night."
   ],
   "robot.nacht_tot": [
    "Night: until",
    "Until this time. Notification mails from the night start the robot then."
   ],
   "robot.nacht_uren": [
    "Night: robot at",
    "Times at which the robot still runs at night, e.g. 01:00, 04:00. At most 3."
   ],
   "robot.contact_refresh_hours": [
    "Update reservations: every how many hours",
    "Re-read contact details, room, dates and payment for upcoming reservations."
   ],
   "robot.mail_trigger": [
    "Start on notification mail",
    "The robot starts as soon as Lighthouse sends a mail about a new or changed booking."
   ],
   "schakelaars.overschrijvingen": [
    "Booking.com bank transfers",
    "The robot registers the Booking.com payment (bank transfer or virtual card) as Overschrijving in Lighthouse. Only non-refundable (right away) or from 2 days before arrival. Applies to this environment only."
   ],
   "schakelaars.ontbijt_labels": [
    "Place breakfast labels",
    "The robot puts the ONTBIJT label on the planboard for guests with breakfast (rate with breakfast, or breakfast for all persons and nights in the folio). Applies to this environment only."
   ],
   "schakelaars.reservaties": ["Read reservations (robot)", "The robot reads new and changed reservations in Lighthouse. With all main switches off, this environment is frozen: the robot no longer starts and does not open Lighthouse. Applies to this environment only."],
   "schakelaars.ontbijtlijst": ["Make and send the breakfast list", "Make and send the breakfast list every day (settings Breakfast list). In the monitor (Breakfast tab) a list can also be made with the switch off. Applies to this environment only."],
   "schakelaars.ontgrendelen": ["Open doors with the guest app", "During their stay, guests can open the front door and their room with a slider in the guest app (Salto remote opening). Only with a code, within the period of the code. The PIN code always keeps working. Applies to this environment only; outside PRD only for test guests."],
   "schakelaars.kuislijst": ["Make and send the cleaning list", "Make and send the cleaning list every day (settings Cleaning list). In the monitor (Cleaning tab) a list can also be made with the switch off. Applies to this environment only."],
   "ontbijtlijst.uur": ["Time", "Make and send every day at this time. You choose from the fixed times of the robot (setting Robot: every how many minutes): the list uses the robot run of that time, so no extra run. Ready after a few minutes."],
   "ontbijtlijst.dag": ["For which day", "1 = tomorrow, 0 = today."],
   "ontbijtlijst.email": ["By mail to", "Mail with the list and the Excel attached. More addresses separated by commas. Empty = no mail."],
   "ontbijtlijst.whatsapp": ["By WhatsApp to", "Mobile numbers (+32...), separated by commas. WhatsApp with the list as a PDF (template: WhatsApp tab), otherwise by SMS. Only when WhatsApp and SMS are on."],
   "ontbijtlijst.samen_tekst": ["Text for several rooms", "One reservation with several rooms: with each room the others, {rooms} = the rooms. Empty = not shown."],
   "ontbijtlijst.woorden": ["Words for remarks", "Sentences from the reservation remark or folio containing one of these words are added to the remarks (e.g. gluten free)."],
   "kuislijst.uur": ["Time", "Make and send every day at this time. You choose from the fixed times of the robot (setting Robot: every how many minutes): the list uses the robot run of that time, so no extra run. Ready after a few minutes."],
   "kuislijst.dag": ["For which day", "1 = tomorrow, 0 = today."],
   "kuislijst.email": ["By mail to", "Mail with the list and the Excel attached. More addresses separated by commas. Empty = no mail."],
   "kuislijst.whatsapp": ["By WhatsApp to", "Mobile numbers (+32...), separated by commas. WhatsApp with the list as a PDF (template: WhatsApp tab), otherwise by SMS. Only when WhatsApp and SMS are on."],
   "kuislijst.controle": ["Check", "Role at the top of the list (Controle: ...), not a name. Empty = no line."],
   "kuislijst.extra_rijen": ["Fixed rows at the bottom", "E.g. TOILETTEN. More rows separated by commas."],
   "kuislijst.labels": ["Labels as remarks", "Labels on the Lighthouse planboard that are added to the remarks, e.g. BABY BED. More labels separated by commas."],
   "hotel.tijdzone": ["Time zone", "For the calendar of the workflow (reminder, code mail, clean-up), e.g. Europe/Brussels."],
   "test.guest_names": ["Test guests (last name)", "Reservations of these guests are test reservations: the robot may also write to Lighthouse for them in TST. TST only reads real reservations. More names separated by commas."],
   "checkout.kamer_tot": ["Room door open until", "On the day of departure the code for the room door still works until this time (margin after check-out, not in the mails)."],
   "checkout.voordeur_tot": ["Front door open until", "On the day of departure the code for the front door (and other shared doors) still works until this time, e.g. to pick up luggage."],
   "twilio.contact_whatsapp": ["Hotel WhatsApp number", "When a guest replies to the number of the automatic messages, an automatic answer gives them this number (the hotel's WhatsApp Business app)."],
   "twilio.doorsturen": ["Forward replies to", "Guest replies to the automatic messages are mailed to these addresses. More addresses separated by commas."],
   "salto.pin_lengte": ["PIN code length", "Own chosen PIN codes with this many digits (needs Custom Pin, Salto KS Pro). Empty = Salto chooses the code."],
   "salto.max_gebruikers": ["Maximum users", "Maximum number of users of the Salto subscription (staff included). Empty = do not check."],
   "kamers.verdieping_regel": ["Floor from the room number", "eerste_cijfer: the first digit of the room number is the floor (12 = 1st floor). geen: never show a floor. Rooms that differ are listed under the exceptions."],
   "beheer.prd_vrijgeven": ["May release to PRD", "Who may move a tested Lighthouse fix from TST to PRD: the e-mail address used to sign in. More addresses separated by commas."],
   "bewaking.email": ["Mail to", "Who receives the daily overview and the warnings. More addresses separated by commas."],
   "bewaking.overzicht_uur": ["Daily overview at", "Time of the mail with today's and tomorrow's arrivals."],
   "bewaking.controle_uren": ["Extra checks at", "Times at which arrivals are checked again (mail only if there is a problem). Empty = none."],
   "bewaking.monitoring": ["Monitoring", "Immediate mail when the robot misses a planned run, when Lighthouse has changed, when a fix is ready to test and when it is solved. The repair robot then looks for a fix itself. Off: only the daily overview."],
   "bewaking.robot_max_uren": ["Robot: alert after (hours)", "Only when the robot has no fixed schedule. Otherwise the planned time counts."],
   "kuislijst.personen": ["Show number of persons", "On check in, the number of persons in the remarks."],
   "kuislijst.opmerkingen": ["Show free remarks", "Remarks from the reservation (e.g. from Booking.com). Off = only labels such as BABY BED and DOUBLE OPMAKEN and the memo for SPECIAAL VERZOEK."],
   "kuislijst.labels_twin": ["Labels only on a twin room", "E.g. DOUBLE OPMAKEN: only added to the remarks of a twin room (hotel file: [kamers.<number>] twin)."],
   "kuislijst.labels_memo": ["Labels with internal memo", "E.g. SPECIAAL VERZOEK: the internal memo of the reservation is added to the remarks."],
   "kuislijst.woorden": ["Words for remarks", "Sentences from the reservation remark or folio containing one of these words are added to the remarks (e.g. baby cot, romantic)."],
   "kamers.lijst_volgorde": ["Rooms on the breakfast and cleaning list", "In this order, separated by commas; - = empty row (new floor). The description from Lighthouse is shown next to the number. A room not in here (e.g. still out of service) only appears at the end on a day with a reservation."],
   "kamers.20.lijst": ["Name on the lists", "Own name instead of the number on the breakfast and cleaning list (e.g. App). Empty = the number."],
   "schakelaars.berichten": [
    "Guest communication",
    "Mails, SMS and WhatsApp to guests, and the Salto PIN codes. Off = nothing to guests and no codes. On = for all reservations, except those you switch off (messages window of the reservation). Selection = only for the reservations you switch on, for testing. Applies to this environment only; outside PRD everything goes to the test addresses."
   ],
   "messaging.start": [
    "From",
    "Only reservations that come in from this moment on get messages."
   ],
   "messaging.phone": [
    "WhatsApp and SMS",
    "WhatsApp (with SMS as fallback) next to the mail. On once Twilio is paid."
   ],
   "retention.reservation_days": [
    "Keep reservations (days after departure)",
    "After that the reservation and its messages are deleted. Guest profiles stay."
   ],
   "retention.guest_days": [
    "Keep guests (days after last stay)",
    "After that the guest profile is deleted. 0 = keep forever."
   ],
   "salto.identity_url": [
    "Login server",
    "Salto test or production."
   ],
   "salto.api_url": [
    "API address",
    ""
   ],
   "salto.site_id": [
    "Site",
    "The hotel's id at Salto. Empty = Salto is off."
   ],
   "salto.guest_role_id": [
    "Guest role",
    "Empty = the role with 'guest' in its name."
   ],
   "salto.common_lock_ids": [
    "Shared doors",
    "Ids of the front door and other doors for all guests, comma separated."
   ],
   "lighthouse.base_url": [
    "Address",
    "Reservation Manager address."
   ],
   "checkin.trappen_vraag_nl": ["Stairs: question (NL)", "Checkbox on the form: one of the guests has difficulty climbing stairs. Empty = the question is not shown."],
   "checkin.trappen_uitleg_nl": ["Stairs: explanation (NL)", "Text under the question."],
   "checkin.trappen_vraag_fr": ["Stairs: question (FR)", "Checkbox on the form: one of the guests has difficulty climbing stairs. Empty = the question is not shown."],
   "checkin.trappen_uitleg_fr": ["Stairs: explanation (FR)", "Text under the question."],
   "checkin.trappen_vraag_en": ["Stairs: question (EN)", "Checkbox on the form: one of the guests has difficulty climbing stairs. Empty = the question is not shown."],
   "checkin.trappen_uitleg_en": ["Stairs: explanation (EN)", "Text under the question."],
   "checkin.trappen_vraag_de": ["Stairs: question (DE)", "Checkbox on the form: one of the guests has difficulty climbing stairs. Empty = the question is not shown."],
   "checkin.trappen_uitleg_de": ["Stairs: explanation (DE)", "Text under the question."],
   "checkin.trappen_niet_bij": ["Stairs: not for room type", "The question is not shown when the room type contains one of these words (e.g. apartment, suite): there the hotel cannot change rooms."],
   "checkin.trappen_memo": ["Stairs: line in the internal memo", "The robot adds this line at the end of the internal memo in Lighthouse (append only, PRD only)."],
   "checkin.trappen_label": ["Stairs: label on the planboard", "E.g. NIET VERPLAATSEN. Only when the guest is already on a low floor (see below); moved down later: then too. Empty = no label."],
   "checkin.trappen_label_verdieping": ["Stairs: low floor up to", "The label is only set when all rooms are on this floor or lower (1 = ground and first floor)."],
   "checkin.formulier_url": [
    "Form address",
    "{token} is filled in per guest. In TST the link goes to the test form."
   ],
   "privacy.url_nl": [
    "Dutch",
    ""
   ],
   "privacy.url_fr": [
    "French",
    ""
   ],
   "privacy.url_en": [
    "English",
    ""
   ],
   "privacy.url_de": [
    "German",
    ""
   ],
   "kleuren.accent": [
    "Accent",
    "Frame around the PIN code and lines."
   ],
   "kleuren.accent_donker": [
    "Dark accent",
    "Buttons and titles."
   ],
   "kleuren.tekst": [
    "Text",
    ""
   ],
   "kleuren.achtergrond": [
    "Background",
    ""
   ]
  },
  "sections": {
   "hotel": "Details guests see in the mails and on the form.",
   "doorschakelen": "Calls to the number of the automatic messages are forwarded: during reception hours to the landline, in the evening to the emergency number, otherwise to the hotel phone.",
   "twilio": "The Twilio account itself is in Key Vault.",
   "robot": "The robot reads Lighthouse (read only).",
   "schakelaars": "Main switches: what the system is really allowed to do. Off by default, per environment.",
   "ontbijtlijst": "Daily breakfast list: per room the number of persons with breakfast. On or off with the main switch Breakfast list.",
   "kuislijst": "Daily cleaning list: per room departure, stay or check-in, with remarks. On or off with the main switch Cleaning list.",
   "kuislijst.wensen": "The robot reads the guest remark, the folio and the internal memo. If one of the words appears (in any language), the short remark on the left goes on the cleaning list, never the text itself. Words separated by commas; preceded by geen, no, pas de or kein it does not count.",
   "messaging": "Messages from the workflow.",
   "whatsapp": "Templates approved by Meta per message and language, e.g. template_confirmation_nl = HX... Without a template the message goes by SMS.",
   "retention": "Clean-up happens with Synchronize on the Guests tab.",
   "salto": "Login details are in Key Vault.",
   "salto.rooms": "Per room the door at Salto: room number = door id.",
   "lighthouse": "The robot user is in Key Vault.",
   "privacy": "Link to the privacy statement per language.",
   "kleuren": "Colours of the mails and the form."
  }
 }
};

// ---------------------------------------------------------------- instellingen van het hotel (tabblad Hotel)
// Alle instellingen uit het hotelbestand, per sectie. Wat hier gewijzigd wordt, gaat voor op het bestand
// (database, per omgeving). Vrije secties (kamers en deuren, WhatsApp-sjablonen): naam = waarde.
let hs = null, hsEdit = {}, hsDirty = false;

// Pagina Technisch: geheimen in Key Vault, alleen met een rol op de Key Vault (server: admin/secrets.py).
// Waarden verborgen tot op het oogje geklikt wordt; nooit bewaard in het scherm na Verbergen.
let ks = null, ksHotel = "";
const EYE = '<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M2 12s3.5-7 10-7 10 7 10 7-3.5 7-10 7S2 12 2 12z"/><circle cx="12" cy="12" r="3"/></svg>';
const EXT = '<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M14 4h6v6M20 4l-9 9M18 14v5a1 1 0 0 1-1 1H5a1 1 0 0 1-1-1V7a1 1 0 0 1 1-1h5"/></svg>';
async function loadSecrets() {
  ksHotel = $("#hotel").value;
  const r = await apiFetch(`${API}/api/monitor/${ksHotel}/secrets`);
  ks = r.ok ? await r.json() : false;
}
function renderSecrets() {
  const box = $("#hs-sections");
  if (!box) return;
  if (ks === null || ksHotel !== $("#hotel").value) { loadSecrets().then(() => { if (hsGroup === "tech") renderSettings(); }).catch(() => {}); return; }
  if (!ks) return;
  const write = ks.access === "write";
  const rows = ks.secrets.map((x, n) => `<div class="field" style="border-top:1px solid #EEF0F3;padding-top:10px">
      <label for="ks-${n}">${esc(x.name)} <span class="help" style="display:inline">· ${esc(t(x.hotel ? "ks_hotel" : "ks_shared"))}${x.updated ? " · " + esc(stamp(x.updated)) : ""}${x.updated_by ? " · " + esc(x.updated_by) : ""}</span></label>
      <div class="row" style="flex-wrap:nowrap;gap:6px"><input id="ks-${n}" class="input" type="password" autocomplete="off" data-ks="${esc(x.name)}" placeholder="••••••••" ${write ? "" : "readonly"} style="flex:1">
      ${x.portal ? `<a class="ibtn" href="${esc(x.portal)}" target="_blank" rel="noopener" title="${esc(t("ks_portal"))}" aria-label="${esc(t("ks_portal"))}">${EXT}</a>` : ""}
      <button type="button" class="ibtn" data-ks-eye="${n}" title="${esc(t("ks_show"))}" aria-label="${esc(t("ks_show"))}">${EYE}</button>
      ${write ? `<button type="button" class="btn" data-ks-save="${n}" disabled>${esc(t("ks_save"))}</button>` : ""}</div></div>`).join("");
  box.insertAdjacentHTML("beforeend", `<section class="card" id="hs-secrets"><div class="ch"><h2 class="ct">${LOCK} ${esc(t("sec_secrets"))}</h2></div>
    <div class="cb"><div class="help">${esc(t("ks_help"))}${write ? "" : " " + esc(t("ks_readonly"))}</div>${rows}</div></section>`);
  const input = n => $(`#ks-${n}`);
  document.querySelectorAll("[data-ks-eye]").forEach(b => b.onclick = async () => {
    const el = input(b.dataset.ksEye);
    if (el.type === "text") { el.type = "password"; if (!el.dataset.dirty) el.value = ""; b.title = t("ks_show"); return; }
    if (!el.dataset.dirty) {
      const r = await apiFetch(`${API}/api/monitor/${ksHotel}/secrets?name=${encodeURIComponent(el.dataset.ks)}`);
      if (!r.ok) { notice(t("ks_failed")); return; }
      el.value = (await r.json()).value || "";
    }
    el.type = "text"; b.title = t("ks_hide");
  });
  document.querySelectorAll("[data-ks]").forEach(el => el.oninput = () => {
    el.dataset.dirty = "1";
    const b = document.querySelector(`[data-ks-save="${el.id.slice(3)}"]`); if (b) b.disabled = !el.value.trim();
  });
  document.querySelectorAll("[data-ks-save]").forEach(b => b.onclick = async () => {
    const el = input(b.dataset.ksSave);
    const r = await apiFetch(`${API}/api/monitor/${ksHotel}/secrets`, { method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ name: el.dataset.ks, value: el.value }) });
    notice(t(r.ok ? "ks_saved" : "ks_failed"));
    if (r.ok) { ks = null; renderSettings(); }
  });
}

async function loadSettings() {
  try { hs = await get(`/api/monitor/${$("#hotel").value}/settings`); } catch (e) { return; }
  hsEdit = {}; hsDirty = false;
  renderSettings();
}

// Label en uitleg in de taal van het scherm; onbekende instelling: de technische naam, geen uitleg
function hsText(section, key) {
  const x = ((HS_TEXT[lang] || HS_TEXT.en).fields)[`${section}.${key}`];
  return x || [key, ""];
}

function hsValue(sec, f) {
  const e = hsEdit[sec.section];
  return e && f.key in e ? e[f.key] : f.value;
}

function hsInput(sec, f, i) {
  const v = hsValue(sec, f), id = `hs-${i}`, attrs = `id="${id}" data-sec="${esc(sec.section)}" data-key="${esc(f.key)}"`;
  if (f.type === "bool") return `<input type="checkbox" ${attrs} ${v ? "checked" : ""}>`;
  if (f.type === "choice") return `<select ${attrs}>${f.choices.map(c => `<option value="${esc(c)}" ${c === v ? "selected" : ""}>${esc(t("unit_" + c) || c)}</option>`).join("")}</select>`;
  if (f.type === "int" || f.type === "float") return `<input type="number" ${attrs} step="${f.type === "int" ? 1 : "any"}" value="${esc(v)}">`;
  if (f.type === "color") return `<input type="color" ${attrs} value="${esc(v)}"> <code>${esc(v)}</code>`;
  if (f.type === "list") return `<input type="text" ${attrs} value="${esc((v || []).join(", "))}" placeholder="${esc(t("hs_list"))}">`;
  return `<input type="text" ${attrs} value="${esc(v ?? "")}">`;
}

// Instellingen op twee pagina's (menu Instellingen): Hotel (wat het hotel geregeld aanpast, in deze volgorde) en
// Technisch (de rest)
const HS_FUNCTIONAL = ["schakelaars", "hotel", "receptie", "checkout", "doorschakelen", "nood", "ontbijtlijst", "kuislijst",
  "kamers", "ontbijt", "wifi", "parking", "reviews", "workflow_parameters"];
const HS_TABS = ["hotel", "tech"];
let hsGroup = "func";  // pagina Hotel (func) of Technisch (tech)

function hsShown() {
  // Een deelsectie (bv. kuislijst.label_tekst) hoort bij haar hoofdsectie
  const root = s => s.section.split(".")[0];
  const order = s => { const i = HS_FUNCTIONAL.indexOf(root(s)); return i < 0 ? 999 : i; };  // Technisch achteraan
  return hs.sections
    .map((s, n) => [s, n])
    .filter(([s]) => !s.rooms && !(root(s) === "test" && isPrd()) && (hsGroup === "func") === HS_FUNCTIONAL.includes(root(s)))
    .sort(([a, i], [b, j]) => order(a) - order(b) || i - j)
    .map(([s]) => s);
}

let hsMSec = 0;  // gsm: gekozen sectie
const LOCK = '<svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><rect x="5" y="11" width="14" height="10" rx="2"/><path d="M8 11V8a4 4 0 0 1 8 0v3"/></svg>';
// Invoerveld in de stijl van het ontwerp (klasse input/select/switch), zelfde data-attributen als vroeger
function hsField(sec, f, i) {
  const v = hsValue(sec, f), id = `hs-${i}`, attrs = `id="${id}" data-sec="${esc(sec.section)}" data-key="${esc(f.key)}"${f.env ? " disabled" : ""}`;
  if (f.type === "choice") return `<select class="select" ${attrs}>${f.choices.map(c => `<option value="${esc(c)}" ${c === v ? "selected" : ""}>${esc(t("unit_" + c) || c)}</option>`).join("")}</select>`;
  if (f.type === "int" || f.type === "float") return `<input class="input" type="number" ${attrs} step="${f.type === "int" ? 1 : "any"}" value="${esc(v)}">`;
  if (f.type === "color") return `<div class="row"><input type="color" ${attrs} value="${esc(v)}" style="width:48px;height:38px;border:0;padding:0;background:none"><code>${esc(v)}</code></div>`;
  if (f.type === "list") return `<input class="input" type="text" ${attrs} value="${esc((v || []).join(", "))}" placeholder="${esc(t("hs_list"))}">`;
  return `<input class="input" type="text" ${attrs} value="${esc(v ?? "")}">`;
}

// ---- Uitzonderingen per kamer: in de sectie Kamers, een lijst met per kamer zijn waarden
const RX = "kamers.uitzonderingen";
let rxOpen = -1;  // welke uitzondering open staat om aan te passen
const rxSec = () => hs && hs.sections.find(x => x.rooms);
const rxItems = () => hsEdit[RX] || rxSec().items;
const rxEdit = () => (hsEdit[RX] = hsEdit[RX] || rxSec().items.map(x => ({ room: x.room, values: { ...x.values } })));
function rxLabel(key) {
  const m = key.match(/^(naam|kort|toegang)_(\w+)$/);
  if (m) return [`${t("rx_f_" + m[1])[0]} (${m[2].toUpperCase()})`, t("rx_f_" + m[1])[1]];
  return t("rx_f_" + key) || [key, ""];
}
function rxSummary(x) {
  const v = x.values, l = lang === "en" ? "en" : "nl", bits = [];
  const nm = v["naam_" + l] || v.naam_nl || v.naam_en;
  if (nm) bits.push(`<b>${esc(nm)}</b>`);
  if (v["kort_" + l] || v.kort_nl) bits.push(esc(v["kort_" + l] || v.kort_nl));
  if (v.lijst) bits.push(`${esc(t("rx_f_lijst")[0])}: ${esc(v.lijst)}`);
  if ("verdieping" in v) bits.push(`${esc(t("rx_f_verdieping")[0])}: ${esc(v.verdieping === "" ? "-" : v.verdieping)}`);
  if (v.twin) bits.push(esc(t("rx_f_twin")[0]));
  return bits.join(" · ") || `<span class="muted">${esc(t("rx_empty"))}</span>`;
}
function rxBlock() {
  const sec = rxSec();
  if (!sec) return "";
  const items = rxItems(), tpl = sec.template;
  const field = (n, f) => {
    const v = items[n].values[f.key], [lbl, hlp] = rxLabel(f.key), id = `rx-${n}-${f.key}`, long = /^toegang_/.test(f.key);
    const attrs = `id="${id}" data-rx="${n}" data-rk="${esc(f.key)}"`;
    if (f.type === "bool") return `<div class="toggle"><div class="tx"><label class="tn" for="${id}">${esc(lbl)}</label>${hlp ? `<div class="help">${esc(hlp)}</div>` : ""}</div><input class="switch" type="checkbox" ${attrs} ${v ? "checked" : ""}></div>`;
    const input = long ? `<textarea class="input" rows="3" ${attrs}>${esc(v ?? "")}</textarea>` : `<input class="input" type="text" ${attrs} value="${esc(v ?? "")}">`;
    return `<div class="field"${long ? ' style="grid-column:1/-1"' : ""}><label for="${id}">${esc(lbl)}</label>${input}${hlp ? `<span class="help">${esc(hlp)}</span>` : ""}</div>`;
  };
  const editor = n => {
    const base = tpl.filter(f => ["verdieping", "lijst"].includes(f.key)), bools = tpl.filter(f => f.type === "bool");
    const langs = [...new Set(tpl.map(f => (f.key.match(/^(?:naam|kort|toegang)_(\w+)$/) || [])[1]).filter(Boolean))];
    const extra = tpl.filter(f => f.type !== "bool" && !["verdieping", "lijst"].includes(f.key) && !/^(naam|kort|toegang)_/.test(f.key));
    return `<div class="rx-ed">
      <div class="fgrid"><div class="field"><label for="rx-${n}-room">${esc(t("rx_room"))}</label><input class="input" id="rx-${n}-room" data-rx="${n}" data-rk="" value="${esc(items[n].room)}"></div>${base.map(f => field(n, f)).join("")}</div>
      ${bools.map(f => field(n, f)).join("")}
      ${langs.map(lg => `<div class="rx-lang">${esc((t("rx_lang") || {})[lg] || lg.toUpperCase())}</div><div class="fgrid">${["naam", "kort", "toegang"].map(k => tpl.find(f => f.key === `${k}_${lg}`)).filter(Boolean).map(f => field(n, f)).join("")}</div>`).join("")}
      ${extra.length ? `<div class="fgrid">${extra.map(f => field(n, f)).join("")}</div>` : ""}
      <div class="row" style="justify-content:flex-end"><button type="button" class="btn2 sm" data-rx-close>${esc(t("rx_close"))}</button></div></div>`;
  };
  return `<div class="rx"><h3 class="rx-t">${esc(t("rx_title"))}</h3><div class="help">${esc(t("rx_help"))}</div>
    <div class="rx-list">${items.length ? items.map((x, n) => `<div class="rx-item${n === rxOpen ? " open" : ""}">
      <div class="rx-row"><span class="rx-room">${esc(x.room ? t("r_room", x.room) : t("rx_new"))}</span><span class="rx-sum">${rxSummary(x)}</span>
        <span class="row" style="gap:6px;flex:none"><button type="button" class="btn2 sm" data-rx-open="${n}">${esc(n === rxOpen ? t("rx_close") : t("rx_edit"))}</button><button type="button" class="btn3" data-rx-del="${n}">${esc(t("rx_del"))}</button></span></div>
      ${n === rxOpen ? editor(n) : ""}</div>`).join("") : `<div class="muted">${esc(t("rx_none"))}</div>`}</div>
    <button type="button" class="btn2" data-rx-add style="align-self:flex-start">+ ${esc(t("rx_add"))}</button></div>`;
}
function rxWire() {
  document.querySelectorAll("#hs-sections [data-rx]").forEach(el => el.onchange = () => {
    const x = rxEdit()[+el.dataset.rx];
    if (!el.dataset.rk) x.room = el.value.trim();
    else x.values[el.dataset.rk] = el.type === "checkbox" ? el.checked : el.value;
    hsTouched();
  });
  document.querySelectorAll("#hs-sections [data-rx-open]").forEach(b => b.onclick = () => { rxOpen = rxOpen === +b.dataset.rxOpen ? -1 : +b.dataset.rxOpen; renderSettings(); });
  document.querySelectorAll("#hs-sections [data-rx-close]").forEach(b => b.onclick = () => { rxOpen = -1; renderSettings(); });
  document.querySelectorAll("#hs-sections [data-rx-del]").forEach(b => b.onclick = async () => {
    const n = +b.dataset.rxDel, x = rxItems()[n];
    if (x.room && !await ask(t("rx_del_confirm", x.room), { ok: t("dlg_delete"), danger: true })) return;
    rxEdit().splice(n, 1); rxOpen = -1; hsTouched();
  });
  const add = $("#hs-sections [data-rx-add]");
  if (add) add.onclick = () => {
    rxEdit().push({ room: "", values: {} }); rxOpen = rxItems().length - 1; hsTouched();
    setTimeout(() => { const el = $(`#rx-${rxOpen}-room`); if (el) { el.focus(); el.scrollIntoView({ block: "center" }); } });
  };
}

function renderSettings() {
  if (!hs || !$("#hs-sections")) return;
  $("#hs-sub").textContent = `${hotelNow().name || ""} · ${($("#env")?.textContent || "").toUpperCase()}`;
  const who = hs.meta.source === "monitor" ? t("wf_changed", hs.meta.updated_by || "?", stamp(hs.meta.updated_at)) : t("wf_from_file");
  let i = 0;
  const shown = hsShown();
  const secName = sec => t("sec_" + sec.section.replace(".", "_")) || sec.section;
  $("#hs-title").textContent = t(hsGroup === "tech" ? "hs_tech" : "tab_hotel");
  document.querySelectorAll("[data-ms]").forEach(x => x.classList.toggle("on", x.dataset.ms === (hsGroup === "tech" ? "tech" : "hotel")));
  $("#hs-nav").innerHTML = shown.map((sec, n) => `<a href="#hs-s${n}" data-jump="hs-s${n}" style="display:block;padding:6px 10px;border-radius:6px;text-decoration:none;font-weight:${n === 0 ? 700 : 500};${n === 0 ? "background:#E6E9EF;" : ""}color:#2B2F38">${esc(t("sec_" + sec.section.replace(".", "_")) || sec.section)}</a>`).join("");
  // Per sectie: wie wijzigde ze laatst, en Bewaren alleen actief als er in deze sectie iets veranderde
  const foot = sec => { const rx = sec.section === "kamers" && rxSec() ? rxSec() : null;
    const m = rx && (rx.meta || {}).updated_at > ((sec.meta || {}).updated_at || "") ? rx.meta : sec.meta || {}; const w = m.updated_at ? t("wf_changed", m.updated_by || "?", stamp(m.updated_at)) : t("wf_from_file");
    return `<div class="row" style="justify-content:space-between;border-top:1px solid #EEF0F3;padding-top:12px"><span class="who">${esc(w)}</span><div class="row"><button class="btn3 hs-reset-btn" type="button">${esc(t("wf_reset"))}</button><button class="btn hs-save-btn" type="button" ${hsEdit[sec.section] || (rx && hsEdit[RX]) ? "" : "disabled"}>${esc(t("wf_save"))}</button></div></div>`; };
  $("#hs-sections").innerHTML = shown.map((sec, n) => {
    const title = t("sec_" + sec.section.replace(".", "_")) || sec.section;
    const help = (HS_TEXT[lang] || HS_TEXT.en).sections[sec.section] || "";
    const env = sec.fields.some(f => f.env);
    let body;
    if (sec.free) {
      const pairs = hsEdit[sec.section] ? Object.entries(hsEdit[sec.section]) : sec.fields.map(f => [f.key, f.value]);
      body = `<div class="fgrid">${pairs.map(([k, v]) => `<div class="field"><input type="text" class="input hs-k" data-free="${esc(sec.section)}" value="${esc(k)}" placeholder="${esc(t("hs_key"))}"></div>
        <div class="field"><input type="text" class="input hs-v" data-free="${esc(sec.section)}" value="${esc(v)}" placeholder="${esc(t("hs_value"))}"></div>`).join("")}</div>
        <button type="button" class="btn3" data-add="${esc(sec.section)}" style="padding:0;align-self:flex-start">+ ${esc(t("hs_add"))}</button>`;
    } else if (sec.section === "schakelaars") {
      // Gastcommunicatie als drie keuzes (uit, selectie, aan), de andere schakelaars als knop
      const gc = sec.fields.find(f => f.key === "berichten");
      const cards = gc ? (() => {
        const v = hsValue(sec, gc), id = i++;
        const opt = (val, d, col, txt) => `<label style="flex:1 1 150px;display:flex;gap:10px;align-items:flex-start;padding:12px;border-radius:10px;border:${v === val ? `2.5px solid ${col}` : "1.5px solid #D5D9E0"};background:${v === val ? (val === "selectie" ? "#FDF3E7" : val === "aan" ? "#F1F8F3" : "#F6F7F9") : "#fff"};cursor:pointer">
          <input type="radio" name="hs-gc" value="${val}" data-sec="schakelaars" data-key="berichten" ${v === val ? "checked" : ""} style="width:18px;height:18px;margin:2px 0 0;accent-color:${col}"><span><span class="row" style="gap:6px;font-weight:700"><span class="d d-${d}"></span>${esc(t("gc_" + val))}</span><span class="help" style="display:block">${esc(t("gc_" + val + "_help"))}</span></span></label>`;
        return `<fieldset style="border:0;margin:0;padding:12px 0;border-top:1px solid #EEF0F3"><legend class="tn" style="font-weight:700;padding:0;margin-bottom:4px">${esc(hsText(sec.section, "berichten")[0])}</legend><div class="help" style="margin-bottom:8px">${esc(hsText(sec.section, "berichten")[1] || "")}</div>
          <div class="row" style="gap:8px;align-items:stretch">${opt("uit", "off", "#8A8F99")}${opt("selectie", "sel", "#C0640F")}${opt("aan", "on", "#2E7D4F")}</div></fieldset>`;
      })() : "";
      // ontgrendelen (deuren via de gast-app) pas tonen als Salto klaar is; de waarde blijft bewaard
      body = cards + sec.fields.filter(f => f.key !== "berichten" && f.key !== "ontgrendelen").map(f => {
        const id = i++, v = hsValue(sec, f), [lbl, hlp] = hsText(sec.section, f.key);
        const on = f.type === "bool" ? !!v : v && v !== "uit";
        return `<div class="toggle"><div class="tx"><label class="tn" for="hs-${id}">${esc(lbl)}</label>${hlp ? `<div class="help">${esc(hlp)}</div>` : ""}</div>
          <input id="hs-${id}" class="switch" type="checkbox" data-sec="schakelaars" data-key="${esc(f.key)}" data-sw="${f.type === "bool" ? "bool" : "aanuit"}" ${on ? "checked" : ""}></div>`;
      }).join("");
    } else {
      const bools = sec.fields.filter(f => f.type === "bool"), others = sec.fields.filter(f => f.type !== "bool");
      body = (others.length ? `<div class="fgrid">${others.map(f => {
        const id = i++, [lbl, hlp] = hsText(sec.section, f.key);
        const changed = JSON.stringify(hsValue(sec, f)) !== JSON.stringify(f.default);
        return `<div class="field"><label for="hs-${id}">${esc(lbl)}</label>${hsField(sec, f, id)}${hlp ? `<span class="help">${esc(hlp)}</span>` : ""}${changed && !f.env ? `<span class="help">${esc(t("hs_default"))}: ${esc(Array.isArray(f.default) ? f.default.join(", ") : String(f.default ?? ""))}</span>` : ""}</div>`;
      }).join("")}</div>` : "") + bools.map(f => {
        const id = i++, [lbl, hlp] = hsText(sec.section, f.key);
        return `<div class="toggle"><div class="tx"><label class="tn" for="hs-${id}">${esc(lbl)}</label>${hlp ? `<div class="help">${esc(hlp)}</div>` : ""}</div><input id="hs-${id}" class="switch" type="checkbox" data-sec="${esc(sec.section)}" data-key="${esc(f.key)}" ${hsValue(sec, f) ? "checked" : ""}${f.env ? " disabled" : ""}></div>`;
      }).join("");
      if (env) body += `<div class="note">${LOCK.replace('width="13" height="13"', 'width="16" height="16"')}<span>${esc(t("hs_env_note"))}</span></div>`;
      if (sec.section === "kamers") body += rxBlock();
    }
    return `<section class="card" id="hs-s${n}" data-sec="${esc(sec.section)}"><div class="ch"><h2 class="ct">${esc(title)}</h2>${env ? `<span class="locked">${LOCK}${esc(t("hs_env_badge"))}</span>` : ""}</div>
      <div class="cb"${sec.section === "schakelaars" ? ' style="gap:0"' : ""}>${help ? `<div class="help">${esc(help)}</div>` : ""}${body}${env && !sec.fields.some(f => !f.env) ? "" : foot(sec)}</div></section>`;
  }).join("");
  if (hsGroup === "tech") renderSecrets();
  document.querySelectorAll("#hs-sections .hs-save-btn").forEach(b => b.onclick = () => {
    const s = b.closest("section").dataset.sec;
    saveSettings(s === "kamers" && rxSec() ? `kamers,${RX}` : s);
  });
  rxWire();
  document.querySelectorAll("#hs-sections .hs-reset-btn").forEach(b => b.onclick = async () => {
    const sec = hs.sections.find(x => x.section === b.closest("section").dataset.sec);
    if (!sec || !await ask(t("hs_sec_reset_confirm", t("sec_" + sec.section.replace(".", "_")) || sec.section), { ok: t("dlg_reset"), danger: true })) return;
    hsEdit[sec.section] = sec.free ? Object.fromEntries(sec.fields.map(f => [f.key, f.default]).filter(([, v]) => v != null))
      : Object.fromEntries(sec.fields.filter(f => !f.env).map(f => [f.key, f.default]));
    if (sec.section === "kamers" && rxSec()) { hsEdit[RX] = rxSec().default_items.map(x => ({ room: x.room, values: { ...x.values } })); rxOpen = -1; }
    saveSettings(sec.section === "kamers" && rxSec() ? `kamers,${RX}` : sec.section);
  });
  // Gsm (ontwerp m-Instellingen-hotel): groep en sectie kiezen, één sectie tegelijk
  if ($("#hs-msec")) {
    $("#hs-msec").innerHTML = shown.map((sec, n) => `<option value="${n}" ${n === hsMSec ? "selected" : ""}>${esc(secName(sec))}</option>`).join("");
    $("#hs-msec").onchange = () => { hsMSec = +$("#hs-msec").value; renderSettings(); };
    document.querySelectorAll("#hs-sections > section").forEach((el, n) => el.classList.toggle("msel", n === hsMSec));
  }
  document.querySelectorAll("#hs-nav [data-jump]").forEach(a => a.onclick = e => { e.preventDefault(); $("#" + a.dataset.jump).scrollIntoView({ behavior: "smooth", block: "start" }); });
  document.querySelectorAll("#hs-sections [data-key]").forEach(el => el.onchange = () => {
    const sec = hs.sections.find(x => x.section === el.dataset.sec), f = sec.fields.find(x => x.key === el.dataset.key);
    let v = el.type === "checkbox" ? el.checked : el.value;
    if (el.dataset.sw === "aanuit") v = el.checked ? "aan" : "uit";
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

async function saveSettings(only) {
  // Alles wat op het scherm staat (ook ongewijzigd): de server bewaart alleen wat verschilt van het bestand
  const body = {};
  const rooms = rxSec() ? rxItems() : [];
  if (rooms.some(x => !x.room)) { notice(t("rx_no_room")); return; }
  const dup = rooms.map(x => x.room).find((r, n, a) => a.indexOf(r) !== n);
  if (dup) { notice(t("rx_dup", dup)); return; }
  hs.sections.forEach(sec => {
    if (sec.rooms) { body[sec.section] = Object.fromEntries(rooms.map(x => [x.room, x.values])); return; }
    if (sec.free) body[sec.section] = hsEdit[sec.section] || Object.fromEntries(sec.fields.map(f => [f.key, f.value]));
    else body[sec.section] = Object.fromEntries(sec.fields.map(f => [f.key, hsValue(sec, f)]));
  });
  const sections = typeof only === "string" ? only : "";
  const r = await apiFetch(API + `/api/monitor/${$("#hotel").value}/settings${sections ? "?only=" + encodeURIComponent(sections) : ""}`, {
    method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body),
  });
  const d = await r.json().catch(() => ({}));
  if (!r.ok) { $("#hs-state").textContent = d.error || `${t("load_error")} ${r.status}`; $("#hs-state").className = "err"; return; }
  hs = d;
  if (sections) { sections.split(",").forEach(k => delete hsEdit[k]); hsDirty = Object.keys(hsEdit).length > 0; if (sections.includes(RX)) rxOpen = -1; }
  else { hsEdit = {}; hsDirty = false; }
  $("#hs-state").className = "muted";
  $("#hs-state").textContent = t("wf_saved");
  const y = window.scrollY;  // na bewaren blijven waar je was (de pagina wordt opnieuw opgebouwd)
  renderSettings();
  window.scrollTo(0, y);
  refreshSwitches();
}

async function resetSettings() {
  if (!await ask(t("hs_reset_confirm"), { ok: t("dlg_reset"), danger: true })) return;
  hs = await get(`/api/monitor/${$("#hotel").value}/settings?action=reset`, { method: "POST" });
  hsEdit = {}; hsDirty = false;
  $("#hs-state").textContent = "";
  const y = window.scrollY;
  renderSettings();
  window.scrollTo(0, y);
  refreshSwitches();
}


// ---------------------------------------------------------------- ontbijtlijst en kuislijst (tabbladen Ontbijt en Schoonmaak)
// Per dag één lijst (de laatste 15). Opnieuw maken (en versturen) voor een gekozen dag; bekijken en de Excel downloaden.
const LIST_KINDS = ["breakfast", "cleaning"];
const listData = {}, listDay = {}, listOpen = {}, listPoll = {};
// Voorbeeld van een lijst: eigen taal (NL/EN), los van de taal van het scherm. Standaard EN: zo wordt ze verstuurd.
const PAPER = {
  en: { breakfast: "Breakfast list", cleaning: "Cleaning list", made: (w, b) => `made ${w} by ${b}`, auto: "automatic", loc: "en-GB" },
  nl: { breakfast: "Ontbijtlijst", cleaning: "Schoonmaaklijst", made: (w, b) => `gemaakt ${w} door ${b}`, auto: "automatisch", loc: "nl-BE" },
};
let paperLang = (() => { try { return localStorage.getItem("paperLang") === "nl" ? "nl" : "en"; } catch (e) { return "en"; } })();
const dayLong = iso => new Date(iso + "T00:00").toLocaleDateString(locale(), { weekday: "long", day: "2-digit", month: "2-digit", year: "numeric" });

async function loadList(kind) {
  try { listData[kind] = await get(`/api/monitor/${$("#hotel").value}/lists?kind=${kind}`); } catch (e) { return; }
  if (!listDay[kind]) listDay[kind] = listData[kind].next_day;
  renderList(listKind);
}

// channel: leeg = alles, of alleen email, whatsapp of sms (sms gaat naar de WhatsApp-nummers)
function recipients(d, channel = "") {
  const mail = channel === "whatsapp" || channel === "sms" ? [] : d.email;
  const phone = channel === "email" ? [] : d.whatsapp.map(x => `${x} (${channel === "sms" ? "sms" : t("dl_wa")})`);
  return [...mail, ...phone].join(", ");
}

function sentCell(x) {
  if (!x.sent || !x.sent.length) return `<span class="muted">${esc(t("dl_not_sent"))}</span>`;
  return `<span class="muted small">${esc(stamp(x.sent_at))}</span><br>` + x.sent.map(s =>
    `<span class="tag ${s.ok ? "" : "fail"}" title="${esc(s.error || "")}">${esc(s.channel === "email" ? t("ch_email") : s.channel === "sms" ? t("ch_sms") : t("ch_whatsapp"))}: ${esc(s.to)}</span>`).join(" ");
}

let listKind = "breakfast", listSel = "";  // gekozen soort en de lijst in het voorbeeld ("kind:dag")
const LICON = { breakfast: '<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M4 9h13v5a5 5 0 0 1-5 5H9a5 5 0 0 1-5-5z"/><path d="M17 10h1.5a2.5 2.5 0 0 1 0 5H17"/><path d="M8 3v3M12 3v3"/></svg>',
  cleaning: '<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M14 4l-4 8"/><path d="M6 12h8l2 8H4z"/><path d="M8 16v4M12 16v4"/></svg>' };
const DL = '<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M12 4v11M7 10l5 5 5-5M4 20h16"/></svg>';
function sentBadge(x) {
  if (!x.sent || !x.sent.length) return `<span class="badge b-wait">${esc(t("l_not_sent"))}</span>`;
  const ok = x.sent.filter(s => s.ok), bad = x.sent.filter(s => !s.ok);
  const cnt = ch => ok.filter(s => s.channel === ch).length;
  const parts = [cnt("email") && t("l_mail", cnt("email")), cnt("whatsapp") && t("l_wa", cnt("whatsapp")), cnt("sms") && t("l_sms", cnt("sms"))].filter(Boolean).join(", ");
  return `<span class="badge ${bad.length ? (ok.length ? "b-warn" : "b-err") : "b-ok"}" title="${esc(x.sent.map(s => `${s.channel}: ${s.to}${s.error ? " (" + s.error + ")" : ""}`).join("\n"))}">${esc(ok.length ? t("l_sent", parts) : t("l_failed"))}</span>`;
}

function renderList(kind) {
  const d = listData[kind];
  if (!$("#list-rows") || kind !== listKind) return;
  document.querySelectorAll("#list-kind label").forEach(l => l.classList.toggle("on", l.dataset.kind === kind));
  // Titels zeggen welke soort lijst gekozen is (keuze bovenaan)
  const mk = document.querySelector('#tab-lists [data-t="l_make_title"]'), la = document.querySelector('#tab-lists [data-t="l_last"]');
  if (mk) mk.textContent = (T[lang] || T.en).l_make_k[kind]; if (la) la.textContent = (T[lang] || T.en).l_last_k[kind];
  if (listSel && !listSel.startsWith(kind + ":")) listSel = "";  // de keuze bovenaan geldt voor alles: maken, lijsten en voorbeeld
  const dayInput = $("#list-day");
  if (d && (dayInput.dataset.kind !== kind + $("#hotel").value)) { dayInput.value = listDay[kind] || d.manual_day || d.next_day; dayInput.dataset.kind = kind + $("#hotel").value; }
  dayInput.onchange = () => { listDay[listKind] = dayInput.value; };
  $("#list-info").textContent = d ? t("dl_info", d.switch, d.time, d.days, recipients(d), d.keep) : "";
  const state = $("#list-state");
  if (d) {
    const busy = (d.pending || []).length > 0;
    [$("#list-make"), $("#list-send")].forEach(b => { b.disabled = !!d.robot_busy; });
    if (busy) {
      state.style.color = d.robot_busy ? "" : "#8B2E2E";
      state.textContent = d.pending.map(p => t(p.made ? "dl_sending" : d.robot_busy ? "dl_waiting" : "dl_no_robot", dayLong(p.day), stamp(p.at))).join(" ");
      clearTimeout(listPoll[kind]);
      listPoll[kind] = setTimeout(() => loadList(kind), 15000);
    } else if (listPoll[kind]) {
      listPoll[kind] = null;
      const last = d.records[0];
      state.style.color = "#245A3A";
      state.textContent = last ? t("dl_ready", dayLong(last.day)) : "";
      if (last) listSel = kind + ":" + last.day;
    }
  }
  // Laatste lijsten van de soort die bovenaan gekozen is, nieuwste eerst
  const all = (listData[kind]?.records || []).map(x => ({ ...x, kind }))
    .sort((a, b) => String(b.generated_at).localeCompare(String(a.generated_at))).slice(0, 15);
  if (!listSel && all.length) listSel = all[0].kind + ":" + all[0].day;
  $("#list-rows").innerHTML = all.map(x => {
    const key = x.kind + ":" + x.day, on = key === listSel;
    return `<tr data-row="${esc(key)}" style="cursor:pointer${on ? ";background:#EEF0F5" : ""}"><td><b>${esc(dday(x.day))}</b></td><td class="small mono">${esc(dtime(x.generated_at))}</td>
      <td class="small">${esc(x.generated_by === "automatisch" ? t("dl_auto") : x.generated_by)}</td><td>${sentBadge(x)}</td>
      <td><div class="row" style="gap:6px;flex-wrap:nowrap"><button class="btn3" type="button" data-view="${esc(key)}">${esc(t(on ? "dl_hide" : "dl_view"))}</button>${x.generated_by !== "automatisch"  // zelf gemaakt: mag weg; lijsten van de robot niet
        ? `<button class="btn3" type="button" data-del="${esc(key)}" title="${esc(t("del"))}" aria-label="${esc(t("del"))}">${BIN}</button>` : ""}</div></td></tr>`;
  }).join("") || `<tr><td colspan="5" class="muted">${esc(t("dl_none"))}</td></tr>`;
  document.querySelectorAll("#list-rows button[data-view]").forEach(b => b.onclick = () => { listSel = listSel === b.dataset.view ? "" : b.dataset.view; renderList(listKind); });
  // Klik ergens op de rij: die lijst meteen tonen (nog eens klikken: verbergen)
  document.querySelectorAll("#list-rows tr[data-row]").forEach(tr => tr.onclick = e => {
    if (e.target.closest("button, a")) return;
    listSel = listSel === tr.dataset.row ? "" : tr.dataset.row; renderList(listKind);
  });
  document.querySelectorAll("#list-rows button[data-del]").forEach(b => b.onclick = async () => {
    const [k, d] = b.dataset.del.split(":");
    if (!await ask(t("dl_del_confirm", dayLong(d)), { ok: t("dlg_delete"), danger: true })) return;
    await get(`/api/monitor/${encodeURIComponent($("#hotel").value)}/lists?kind=${k}&day=${encodeURIComponent(d)}&action=delete`, { method: "POST" });
    if (listSel === b.dataset.del) listSel = "";
    loadList(k);
  });
  // Voorbeeld zoals geprint
  const [sk, sd] = listSel.split(":"), x = (listData[sk]?.records || []).find(r => r.day === sd);
  const hotel = encodeURIComponent($("#hotel").value);
  $("#list-preview").innerHTML = x ? `<div class="row" style="justify-content:space-between"><div class="lbl">${esc(t("l_preview"))}</div><div class="row">
      <div class="seg v2" role="radiogroup" aria-label="Taal van de lijst" style="height:32px;box-sizing:border-box">${["nl", "en"].map(l =>
        `<label class="${l === paperLang ? "on" : ""}" data-plang="${l}" style="min-height:0;height:100%;padding:0 10px;font-size:13px"><input type="radio" name="plang" ${l === paperLang ? "checked" : ""}>${l.toUpperCase()}</label>`).join("")}</div>
      <a class="btn2 sm" href="${API}/api/monitor/${hotel}/list-xlsx?kind=${sk}&day=${esc(sd)}">${DL}Excel</a>
      <a class="btn2 sm" href="${API}/api/monitor/${hotel}/list-pdf?kind=${sk}&day=${esc(sd)}">${DL}PDF</a>
      <span style="position:relative;display:inline-flex"><button class="btn sm" type="button" id="list-send-saved" style="border-top-right-radius:0;border-bottom-right-radius:0">${IC('<path d="M22 2L11 13"/><path d="M22 2l-7 20-4-9-9-4z"/>', 14)}${esc(t("ls_send"))}</button><button class="btn sm" type="button" id="list-send-more" aria-haspopup="true" aria-expanded="false" aria-label="${esc(t("ls_more"))}" style="border-top-left-radius:0;border-bottom-left-radius:0;border-left:1px solid rgba(255,255,255,.35);padding-left:8px;padding-right:8px">${IC('<path d="M6 9l6 6 6-6"/>', 14)}</button>
        <div class="pop v2" id="list-send-menu" hidden style="position:absolute;right:0;top:calc(100% + 6px);z-index:20;min-width:190px;padding:6px;gap:2px">
          <button class="btn3" type="button" data-send-ch="" style="justify-content:flex-start;text-align:left;width:100%;padding:8px 10px;text-decoration:none">${esc(t("ls_ch_all"))}</button>
          <button class="btn3" type="button" data-send-ch="whatsapp" style="justify-content:flex-start;text-align:left;width:100%;padding:8px 10px;text-decoration:none">${esc(t("ls_ch_wa"))}</button>
          <button class="btn3" type="button" data-send-ch="email" style="justify-content:flex-start;text-align:left;width:100%;padding:8px 10px;text-decoration:none">${esc(t("ls_ch_mail"))}</button>
          <button class="btn3" type="button" data-send-ch="sms" style="justify-content:flex-start;text-align:left;width:100%;padding:8px 10px;text-decoration:none">${esc(t("ls_ch_sms"))}</button>
        </div></span>
      <button class="btn3" type="button" id="list-del" title="${esc(t("del"))}">${BIN}</button></div></div>
    <div class="paper" id="list-paper"><div class="row" style="justify-content:space-between;align-items:flex-start"><div><div class="lbl">${esc(hotelNow().name || "")}</div>
      <h2 style="font-size:20px;margin-top:2px">${esc(PAPER[paperLang][sk] + " " + new Date(sd + "T00:00").toLocaleDateString(PAPER[paperLang].loc, { weekday: "long", day: "2-digit", month: "2-digit", year: "numeric" }))}</h2><div class="small muted">${esc(PAPER[paperLang].made(dtime(x.generated_at), x.generated_by === "automatisch" ? PAPER[paperLang].auto : x.generated_by))}</div></div>
      <div style="text-align:right" class="small muted">${esc((paperLang === "nl" ? x.summary_nl : x.summary) || x.summary || "")}</div></div><div class="tbox" style="margin-top:14px">${(paperLang === "nl" ? x.html_nl : x.html) || x.html}</div></div>`
    : `<div class="card"><div class="cb" style="padding-top:16px"><span class="muted">${esc(t("l_none_sel"))}</span></div></div>`;
  if (x) {
    document.querySelectorAll("#list-preview [data-plang]").forEach(b => b.onclick = e => {
      e.preventDefault(); paperLang = b.dataset.plang;
      try { localStorage.setItem("paperLang", paperLang); } catch (err) { /* alleen een voorkeur */ }
      renderList(listKind);
    });
    $("#list-send-saved").onclick = () => sendSavedList(sk, sd, x, "");
    const menu = $("#list-send-menu"), more = $("#list-send-more");
    more.onclick = e => { e.stopPropagation(); menu.hidden = !menu.hidden; more.setAttribute("aria-expanded", String(!menu.hidden)); };
    menu.querySelectorAll("[data-send-ch]").forEach(b => b.onclick = () => { menu.hidden = true; sendSavedList(sk, sd, x, b.dataset.sendCh); });
    if (!window.lsMenuBound) {  // één keer: klik ernaast sluit het menu
      window.lsMenuBound = true;
      document.addEventListener("click", e => {
        const m = $("#list-send-menu"), b = $("#list-send-more");
        if (m && !e.target.closest("#list-send-menu, #list-send-more")) { m.hidden = true; if (b) b.setAttribute("aria-expanded", "false"); }
      });
    }
    $("#list-del").onclick = async () => {
      if (!await ask(t("dl_del_confirm", dayLong(sd)), { ok: t("dlg_delete"), danger: true })) return;
      await get(`/api/monitor/${hotel}/lists?kind=${sk}&day=${encodeURIComponent(sd)}&action=delete`, { method: "POST" });
      listSel = ""; loadList(sk);
    };
  }
}

// Knop Versturen: de bewaarde lijst manueel versturen. Popup met ontvangers, al verstuurd, voorbije dag en een bericht.
async function sendSavedList(kind, day, x, channel = "") {
  const all = listData[kind] || { email: [], whatsapp: [] };
  // Keuze in het menu van de knop Versturen: alles, alleen WhatsApp, alleen mail of alleen sms (naar de WhatsApp-nummers)
  const d = { ...all, email: channel === "whatsapp" || channel === "sms" ? [] : all.email, whatsapp: channel === "email" ? [] : all.whatsapp };
  const byPhone = t(channel === "sms" ? "ls_by_sms" : "ls_by_wa");
  const now = new Date(), today = `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, "0")}-${String(now.getDate()).padStart(2, "0")}`;
  const to = [...d.email.map(a => `<li>${esc(t("ls_by_mail"))}: <b>${esc(a)}</b></li>`), ...d.whatsapp.map(a => `<li>${esc(byPhone)}: <b>${esc(a)}</b>${d.phone_on === false ? ` <span class="muted">(${esc(t("ls_wa_off"))})</span>` : ""}</li>`)];
  if (!to.length) { notice(t("ls_no_to")); return; }
  const warn = [];
  if (day < today) warn.push(`<div class="note err"><b>${esc(t("ls_past", dayLong(day)))}</b></div>`);
  const okSent = (x.sent || []).filter(s => s.ok);
  if (okSent.length) warn.push(`<div class="note warn">${esc(t("ls_already", stamp(x.sent_at), okSent.map(s => s.to).join(", ")))}</div>`);
  const what = t("l_title_" + kind, dayLong(day));
  const note = await dialog(t("ls_q", what[0].toLowerCase() + what.slice(1)), {
    title: t("ls_title"), ok: t("ls_send"),
    html: `${warn.join("")}<div class="lbl" style="margin-top:4px">${esc(t("ls_to"))}</div><ul class="dlg-to">${to.join("")}</ul>`,
    input: { label: t("ls_note"), placeholder: t("ls_note_ph") },
  });
  if (note === null) return;
  const state = $("#list-state");
  state.style.color = ""; state.textContent = t("dl_busy");
  const r = await apiFetch(`${API}/api/monitor/${encodeURIComponent($("#hotel").value)}/lists?kind=${kind}&day=${encodeURIComponent(day)}&action=send${channel ? "&channel=" + channel : ""}`, {
    method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ note }),
  }).then(x => x.json()).catch(e => ({ ok: false, error: String(e) }));
  state.textContent = "";
  await loadList(kind);
  if (r.ok) notice(t("ls_done", r.text || ""));
  else notice(t("ls_fail", r.error || r.text || "?"));
}

async function makeList(kind, send, channel = "") {
  const day = $("#list-day").value;
  if (!day) return;
  const d = listData[kind];
  if (send && !await ask(t("dl_confirm", dayLong(day), (d && recipients(d, channel)) || t("dl_no_to")), { ok: t("dlg_send") })) return;
  const state = $("#list-state"), buttons = [$("#list-make"), $("#list-send")];
  buttons.forEach(b => { b.disabled = true; });
  state.style.color = "";
  state.textContent = t("dl_busy");
  try {
    const r = await get(`/api/monitor/${$("#hotel").value}/lists?kind=${kind}&day=${day}${send ? "&send=1" : ""}${send && channel ? "&channel=" + channel : ""}`, { method: "POST" });
    if (r.requested) {  // de robot leest eerst Lighthouse; de lijst volgt
      await loadList(kind);
      if ((r.robot || "").startsWith("robot niet gestart")) { state.style.color = "#8B2E2E"; state.textContent = r.robot; }
      return;
    }
    const failed = (r.sent || []).filter(s => !s.ok).length;
    state.style.color = failed ? "#8B2E2E" : "#245A3A";
    state.textContent = failed ? t("dl_sent_fail", failed) : t(send ? "dl_sent_ok" : "dl_made", dayLong(day));
    listSel = kind + ":" + day;
    await loadList(kind);
  } catch (e) {
    state.style.color = "#8B2E2E";
    state.textContent = `${t("load_error")}: ${e.message}`;
  } finally {
    buttons.forEach(b => { b.disabled = !!listData[kind]?.robot_busy; });
  }
}

// ---------------------------------------------------------------- wisselen tussen TST en PRD
// Link naar de andere omgeving (monitor-tst.hotellucca.be <-> monitor.hotellucca.be), zelfde pagina
// en tabblad. Altijd eerst bevestigen; naar PRD met een duidelijke waarschuwing (echte gasten).
function envSwitch() {
  const env = ($("#env")?.textContent || "").trim().toLowerCase();
  document.body.classList.add("env-" + (env === "prd" || env === "tst" ? env : "dev"));
  if (env === "prd" || env === "tst") document.title = `[${env.toUpperCase()}] ${document.title}`;
  else document.querySelectorAll("#env, [data-env]").forEach(e => { e.hidden = true; });  // lokaal: geen badge
  if ($("#envname")) $("#envname").textContent = t("env_name_" + env) || "";
  if ($("#tstbar")) $("#tstbar").hidden = env !== "tst";
  const host = location.hostname;
  const other = env === "tst" && host.startsWith("monitor-tst.") ? host.replace("monitor-tst.", "monitor.")
    : env === "prd" && host.startsWith("monitor.") ? host.replace("monitor.", "monitor-tst.") : null;
  if (!other) return;
  const target = env === "tst" ? "prd" : "tst";
  [$("#env-switch"), $("#tst-switch")].filter(Boolean).forEach(link => {
    link.hidden = false;
    if (link.id === "env-switch") link.textContent = t("env_to_" + target);
    link.href = `${location.protocol}//${other}${location.pathname}${location.hash}`;
    link.onclick = async e => {
      e.preventDefault();
      link.href = `${location.protocol}//${other}${location.pathname}${location.hash}`;  // zelfde tabblad als nu
      if (await ask(t("env_confirm_" + target), { ok: t("env_to_" + target) })) location.href = link.href;
    };
  });
}

// Smartphone: tabellen tonen als kaartjes (CSS, admin.css "Smartphone"). Elke cel krijgt de kolomnaam als label,
// zodat elke regel "kolom: waarde" leest. Werkt vanzelf voor elke tabel met kolomtitels, ook na opnieuw tekenen.
function labelCells(table) {
  const heads = [...table.querySelectorAll("thead th")].map(th => th.textContent.replace(/[\u2191\u2193]/g, "").trim());
  if (!heads.length) return;
  table.classList.add("cards");
  table.querySelectorAll("tbody tr").forEach(tr => {
    let i = 0;
    [...tr.children].forEach(td => {
      const span = Number(td.getAttribute("colspan") || 1);
      if (span > 1) td.classList.add("full"); else if (heads[i]) td.dataset.label = heads[i];
      i += span;
    });
  });
}
let labelTimer = null;
new MutationObserver(() => {
  clearTimeout(labelTimer);
  labelTimer = setTimeout(() => document.querySelectorAll("table").forEach(tb => { if (!tb.closest(".v2")) labelCells(tb); }), 50);
}).observe(document.body, { childList: true, subtree: true, characterData: true });

// ---------------------------------------------------------------- WhatsApp-sjablonen (instellingen, tabblad WhatsApp)
// Per sjabloon en taal: tekst wijzigen, bewaren, indienen bij Meta; de status van wat nog wacht vraagt de server
// (hoogstens een keer per minuut bij het openen, en elke 15 minuten in de achtergrond).
let wa = null, waHotel = "", waEdit = {}, waNote = {};
const waLang = {};
const waDirty = () => Object.keys(waEdit).length > 0;
const WA_BADGE = { approved: "b-ok", waiting: "b-info", changed: "b-warn", new: "b-no", rejected: "b-err", error: "b-err" };
const waKey = (step, lg) => `${step}:${lg}`;
async function loadWhatsapp(view) {
  if (!$("#wa-list")) return;
  const hotel = $("#hotel").value;
  if (hotel !== waHotel) { waEdit = {}; waNote = {}; waHotel = hotel; }
  if (view) wa = view;
  else {
    try { wa = await get(`/api/monitor/${hotel}/whatsapp`); }
    catch (e) { $("#wa-state").className = "err"; $("#wa-state").textContent = `${t("load_error")} ${e.message}`; return; }
  }
  $("#wa-state").textContent = "";
  renderWhatsapp();
}
function waText(tp, lg) { return waEdit[waKey(tp.step, lg.lang)] || lg.text; }
function waFill(body, samples) { return String(body || "").replace(/\{\{\s*(\d+)\s*\}\}/g, (m, n) => samples[n - 1] ?? m); }
function waBadge(st) { return `<span class="badge ${WA_BADGE[st] || "b-no"}">${esc(t("wa_st_" + st))}</span>`; }
function waPreview(tp, x) {
  const btn = tp.button && x.button ? `<div style="border-top:1px solid #E3E6EB;margin-top:8px;padding-top:7px;text-align:center;font-weight:700;color:#3E4558">${IC('<path d="M9 6H6a2 2 0 0 0-2 2v10a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2v-3M14 4h6v6M20 4l-9 9"/>', 13)} ${esc(x.button)}</div>` : "";
  const pdf = tp.media ? `<div class="row" style="gap:6px;padding:8px;margin-bottom:8px;border-radius:6px;background:#E9EAED;font-size:12.5px">${IC('<path d="M14 3H7a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2V8z"/><path d="M14 3v5h5"/>', 14)} ${esc(tp.media_sample)}</div>` : "";
  const head = x.header && !tp.media ? `<div style="font-weight:700;margin-bottom:4px">${esc(x.header)}</div>` : "";
  return `<div style="max-width:420px;background:#F4F5F8;border-radius:10px;padding:10px 12px">${pdf}${head}<div style="white-space:pre-wrap;overflow-wrap:anywhere">${esc(waFill(x.body, tp.samples))}</div>${x.footer ? `<div class="small muted" style="margin-top:6px">${esc(x.footer)}</div>` : ""}${btn}</div>`;
}
function waLink(v) {
  // Icoon naar de Content Template Builder in Twilio, om na te kijken wat daar echt staat
  return v && v.name ? ` <a href="${esc(wa.console_url)}" target="_blank" rel="noopener" title="${esc(t("wa_twilio", v.name))}" aria-label="${esc(t("wa_twilio", v.name))}" style="display:inline-flex;vertical-align:-2px;color:#4E5669">${IC('<path d="M14 4h6v6M20 4l-9 9"/><path d="M18 14v4a2 2 0 0 1-2 2H6a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h4"/>', 14)}</a> <code class="small">${esc(v.name)}</code>` : "";
}
function waMeta(lg) {
  const bits = [];
  if (lg.active) bits.push(esc(t("wa_active", lg.active.version, stamp(lg.active.approved_at))) + waLink(lg.active));
  else if (lg.manual_sid) bits.push(esc(t("wa_manual", lg.manual_sid)) + waLink({ name: lg.manual_sid }));
  else bits.push(esc(t("wa_none_active")));
  if (lg.pending) {
    bits.push(esc(t("wa_pending", lg.pending.version, stamp(lg.pending.submitted_at), lg.pending.submitted_by || "")) + waLink(lg.pending)
      + (lg.pending.status !== "error" && lg.pending.checked_at && lg.state === "waiting" ? " " + esc(t("wa_checked", stamp(lg.pending.checked_at))) : ""));
  }
  return bits.join("<br>");
}
function waCard(tp) {
  const [title, help] = t("wa_t_" + tp.step);
  const cur = waLang[tp.step] && tp.langs.some(l => l.lang === waLang[tp.step]) ? waLang[tp.step] : tp.langs[0].lang;
  waLang[tp.step] = cur;
  const lg = tp.langs.find(l => l.lang === cur), k = waKey(tp.step, cur), x = waText(tp, lg), dirty = !!waEdit[k];
  const L = wa.limits, bodyMax = tp.button ? L.body_button : L.body, id = `wa-${tp.step}`;
  const vars = tp.vars.map((v, n) => `<code>{{${n + 1}}}</code> ${esc((t("wa_v") || {})[v] || v)}`).join(" · ");
  const seg = tp.langs.length > 1 ? `<div class="seg" role="radiogroup">${tp.langs.map(l => `<label class="${l.lang === cur ? "on" : ""}" data-wa-lang="${tp.step}:${l.lang}"><input type="radio" name="wal-${tp.step}" ${l.lang === cur ? "checked" : ""}>${l.lang.toUpperCase()} <span class="badge ${WA_BADGE[waEdit[waKey(tp.step, l.lang)] ? "changed" : l.state]}" style="padding:0 6px;min-width:0">&nbsp;</span></label>`).join("")}</div>` : "";
  const st = dirty ? "changed" : lg.state;
  const reason = lg.state === "rejected" && lg.pending && lg.pending.reason ? `<div class="note warn">${esc(t("wa_reason", lg.pending.reason))}</div>` : "";
  const err = lg.state === "error" && lg.pending && lg.pending.error ? `<div class="note warn">${esc(lg.pending.error)}</div>` : "";
  const errors = !dirty && lg.errors.length ? `<div class="note warn"><span>${lg.errors.map(esc).join("<br>")}</span></div>` : "";
  const note = waNote[k] ? `<span class="small ${waNote[k].ok ? "muted" : "err"}">${esc(waNote[k].text)}</span>` : "";
  const ro = !!wa.shared_from;
  const canSubmit = dirty || ["new", "changed", "error"].includes(lg.state);
  const same = (a, b) => ["header", "body", "button", "footer"].every(f => (a[f] || "") === (b[f] || ""));
  const canReset = dirty || lg.edited || ["rejected", "error"].includes(lg.state) || (lg.state === "waiting" && !lg.active && !same(lg.text, lg.default));
  return `<section class="card" id="wa-c-${tp.step}" data-wa="${tp.step}"><div class="ch"><h2 class="ct">${IC('<path d="M4 20l1.4-4.2A8 8 0 1 1 8.6 19z"/>')} ${esc(title)}</h2><span class="row" style="gap:6px"><span class="small muted">${esc(cur.toUpperCase())}</span>${waBadge(st)}</span></div>
    <div class="cb"><div class="help">${esc(help)} ${esc(t("wa_vars"))}: ${vars}</div>${seg}
      <div class="help">${waMeta(lg)}</div>${reason}${err}<div class="note" id="${id}-replace" ${dirty && lg.state === "waiting" ? "" : "hidden"}><span>${esc(t("wa_replace"))}</span></div>
      ${tp.media ? "" : `<div class="field"><label for="${id}-header">${esc(t("wa_header"))} <span class="muted small" id="${id}-n-header">${(x.header || "").length}/${L.header}</span></label><input class="input" id="${id}-header" data-wa-f="header" ${wa.shared_from ? "disabled" : ""} maxlength="${L.header}" value="${esc(x.header || "")}"></div>`}
      <div class="field"><label for="${id}-body">${esc(t("wa_body"))} <span class="muted small" id="${id}-n-body">${(x.body || "").length}/${bodyMax}</span></label><textarea class="input" id="${id}-body" data-wa-f="body" ${ro ? "disabled" : ""} rows="5" style="padding:8px 10px;min-height:110px;font:inherit;line-height:1.45;resize:vertical">${esc(x.body || "")}</textarea></div>
      ${tp.button ? `<div class="field"><label for="${id}-button">${esc(t("wa_button"))} <span class="muted small" id="${id}-n-button">${(x.button || "").length}/${L.button}</span></label><input class="input" id="${id}-button" data-wa-f="button" ${ro ? "disabled" : ""} maxlength="${L.button}" value="${esc(x.button || "")}"><span class="help">${esc(t("wa_button_help", wa.button_prefix))}</span></div>` : ""}
      ${tp.media ? `<div class="help">${esc(t("wa_media_help", wa.media_prefix))}</div>` : `<div class="field"><label for="${id}-footer">${esc(t("wa_footer"))} <span class="muted small" id="${id}-n-footer">${(x.footer || "").length}/${L.footer}</span></label><input class="input" id="${id}-footer" data-wa-f="footer" ${ro ? "disabled" : ""} maxlength="${L.footer}" value="${esc(x.footer || "")}"></div>`}
      <div class="field"><span class="lbl">${esc(t("wa_preview"))}</span><div id="${id}-pv">${waPreview(tp, x)}</div></div>${errors}
      <div class="row" style="justify-content:space-between;border-top:1px solid #EEF0F3;padding-top:12px" ${ro ? "hidden" : ""}><span class="who" id="${id}-state">${dirty ? esc(t("wa_unsaved")) : ""}${note}</span>
        <div class="row"><button class="btn3" type="button" data-wa-act="reset" ${canReset ? "" : "hidden"}>${esc(t("wa_reset"))}</button><button class="btn2" type="button" data-wa-act="save" ${dirty ? "" : "disabled"}>${esc(t("wa_save"))}</button><button class="btn" type="button" data-wa-act="submit" ${canSubmit ? "" : "disabled"}>${esc(t("wa_submit"))}</button></div></div>
    </div></section>`;
}
function renderWhatsapp() {
  if (!wa || !$("#wa-list")) return;
  $("#wa-sub2").textContent = `${hotelNow().name || ""} · ${(wa.env || "").toUpperCase()}`;
  const all = wa.templates.flatMap(tp => tp.langs.map(l => ({ tp, l })));
  const todo = all.filter(({ tp, l }) => ["new", "changed", "error"].includes(l.state) && !waEdit[waKey(tp.step, l.lang)]).length;
  $("#wa-all").disabled = todo === 0;
  $("#wa-all").lastElementChild.textContent = todo ? t("wa_all", todo) : t("wa_all_none");
  const ro = !!wa.shared_from;
  $("#wa-all").hidden = ro;
  if (ro) { $("#wa-state").className = "note"; $("#wa-state").textContent = t("wa_shared", wa.shared_from, wa.checked_at ? stamp(wa.checked_at) : ""); }
  $("#wa-check").hidden = false;  // altijd: ook na een bezwaar kan Meta een versie alsnog goedkeuren
  $("#wa-defaults").hidden = ro || !wa.newer_defaults;
  if (wa.newer_defaults) $("#wa-defaults").lastElementChild.textContent = t("wa_defaults", wa.newer_defaults);
  $("#wa-overview").innerHTML = `<table><tbody>${wa.templates.map(tp => `<tr><td style="font-weight:600">${esc(t("wa_t_" + tp.step)[0])}</td><td><div class="row" style="gap:4px;flex-wrap:nowrap">${tp.langs.map(l => `<a href="#" class="badge ${WA_BADGE[waEdit[waKey(tp.step, l.lang)] ? "changed" : l.state]}" style="text-decoration:none" title="${esc(t("wa_st_" + (waEdit[waKey(tp.step, l.lang)] ? "changed" : l.state)))}" data-wa-go="${tp.step}:${l.lang}">${l.lang.toUpperCase()}</a>`).join("")}</div></td></tr>`).join("")}</tbody></table>
    <div class="row" style="gap:6px;flex-wrap:wrap;margin-top:10px">${["approved", "waiting", "changed", "new", "rejected"].map(waBadge).join("")}</div>`;
  $("#wa-list").innerHTML = wa.templates.map(waCard).join("");
  waWire();
}
function waRefresh(step) {
  // Na typen: alleen tellers, voorbeeld en knoppen bijwerken (de focus blijft in het veld)
  const tp = wa.templates.find(x => x.step === step), lg = tp.langs.find(l => l.lang === waLang[step]), x = waText(tp, lg), id = `wa-${step}`;
  ["header", "body", "button", "footer"].forEach(f => { const n = $(`#${id}-n-${f}`); if (n) n.textContent = n.textContent.replace(/^\d+/, String((x[f] || "").length)); });
  $(`#${id}-pv`).innerHTML = waPreview(tp, x);
  const card = $(`#wa-c-${step}`);
  card.querySelector('[data-wa-act="save"]').disabled = false;
  card.querySelector('[data-wa-act="submit"]').disabled = false;
  card.querySelector('[data-wa-act="reset"]').hidden = false;
  card.querySelector(".ch .badge").outerHTML = waBadge("changed");
  $(`#${id}-state`).textContent = t("wa_unsaved");
  if (lg.state === "waiting") $(`#${id}-replace`).hidden = false;
}
function waWire() {
  document.querySelectorAll("#wa-list [data-wa-lang]").forEach(l => l.onclick = e => {
    e.preventDefault(); const [step, lg] = l.dataset.waLang.split(":"); waLang[step] = lg; renderWhatsapp();
  });
  document.querySelectorAll("#wa-overview [data-wa-go]").forEach(a => a.onclick = e => {
    e.preventDefault(); const [step, lg] = a.dataset.waGo.split(":"); waLang[step] = lg; renderWhatsapp();
    $(`#wa-c-${step}`).scrollIntoView({ behavior: "smooth", block: "start" });
  });
  document.querySelectorAll("#wa-list [data-wa-f]").forEach(el => el.oninput = () => {
    const card = el.closest("[data-wa]"), step = card.dataset.wa, tp = wa.templates.find(x => x.step === step);
    const lg = tp.langs.find(l => l.lang === waLang[step]), k = waKey(step, lg.lang);
    waEdit[k] = { ...waText(tp, lg), [el.dataset.waF]: el.value };
    delete waNote[k];
    waRefresh(step);
  });
  document.querySelectorAll("#wa-list [data-wa-act]").forEach(b => b.onclick = () => waAction(b.closest("[data-wa]").dataset.wa, b.dataset.waAct, b));
}
async function waPost(params, body) {
  const r = await apiFetch(API + `/api/monitor/${$("#hotel").value}/whatsapp?` + new URLSearchParams(params), {
    method: "POST", headers: { "Content-Type": "application/json" }, body: body ? JSON.stringify(body) : "",
  });
  const d = await r.json().catch(() => ({}));
  if (!r.ok) throw new Error(d.error || r.status);
  return d;
}
async function waAction(step, act, btn) {
  const tp = wa.templates.find(x => x.step === step), lg = tp.langs.find(l => l.lang === waLang[step]), k = waKey(step, lg.lang);
  if (act === "submit" && !await ask(t("wa_submit_q"), { ok: t("wa_dlg_submit") })) return;
  if (act === "reset" && !await ask(t("wa_reset_q"), { ok: t("wa_dlg_reset"), danger: true })) return;
  btn.disabled = true;
  try {
    const d = await waPost({ action: act, step, lang: lg.lang }, act === "reset" ? null : waEdit[k] || null);
    delete waEdit[k];
    waNote[k] = act === "save" ? { ok: true, text: t("wa_saved") } : d.message ? { ok: d.ok, text: d.message } : null;
    if (!waNote[k]) delete waNote[k];
    await loadWhatsapp(d.view);
  } catch (e) {
    waNote[k] = { ok: false, text: `${t("load_error")} ${e.message}` };
    renderWhatsapp();
  }
}
async function waSubmitAll() {
  const n = wa.templates.flatMap(tp => tp.langs).filter(l => ["new", "changed", "error"].includes(l.state)).length;
  if (!n || !await ask(t("wa_all_q", n), { ok: t("wa_dlg_submit") })) return;
  $("#wa-all").disabled = true;
  try {
    const d = await waPost({ action: "submit_all" });
    const bad = d.results.filter(r => !r.ok);
    await loadWhatsapp(d.view);
    notice([t("wa_done", d.results.length - bad.length), ...bad.map(r => `${t("wa_t_" + r.step)[0]} ${r.lang.toUpperCase()}: ${r.message}`)].join("\n"));
  } catch (e) { notice(`${t("load_error")} ${e.message}`); renderWhatsapp(); }
}
async function waUseDefaults() {
  if (!await ask(t("wa_defaults_q", wa.newer_defaults), { ok: t("wa_dlg_reset") })) return;
  try {
    const d = await waPost({ action: "use_defaults" });
    await loadWhatsapp(d.view);
    $("#wa-state").className = "small muted";
    $("#wa-state").textContent = t("wa_defaults_done", d.count);
  } catch (e) { $("#wa-state").className = "err"; $("#wa-state").textContent = `${t("load_error")} ${e.message}`; }
}
async function waCheck() {
  $("#wa-check").disabled = true;
  try {
    const d = await waPost({ action: "check" });
    await loadWhatsapp(d.view);
    $("#wa-state").className = "small muted";
    $("#wa-state").textContent = d.changes.length ? t("wa_changes", d.changes.join(", ")) : t("wa_no_changes");
  } catch (e) { $("#wa-state").className = "err"; $("#wa-state").textContent = `${t("load_error")} ${e.message}`; }
  $("#wa-check").disabled = false;
}
// Zolang iets wacht op Meta en het tabblad open staat: elke minuut opnieuw (niet tijdens het typen)
setInterval(() => {
  if (PAGE !== "settings" || current !== "whatsapp" || document.hidden || !wa) return;
  if (!wa.templates.some(tp => tp.langs.some(l => l.state === "waiting"))) return;
  if (document.activeElement && document.activeElement.closest && document.activeElement.closest("#wa-list")) return;
  loadWhatsapp().catch(() => {});
}, 60000);

// Als laatste: alle functies en variabelen hierboven bestaan dan
init().catch(e => { document.body.insertAdjacentHTML("beforeend", `<p class="err">${t("load_error")}: ${esc(e.message)}</p>`); });
