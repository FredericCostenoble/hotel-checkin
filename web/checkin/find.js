// Pagina na de QR-code ter plaatse: de gast vraagt de link naar zijn verblijfspagina opnieuw.
// Er wordt nooit iets van een reservatie getoond. Alleen bij familienaam en vertrekdatum samen tonen we gemaskeerd
// waar de link naartoe ging (j•••@gmail.com), zodat de gast weet waar hij moet kijken.
(function () {
  "use strict";
  const T = {
    nl: {
      loading: "Even geduld...", title: "Uw verblijfspagina",
      intro: "Hier ontvangt u opnieuw de link naar uw verblijfspagina, met uw pincode en alle info. We sturen hem alleen naar een e-mailadres of gsm-nummer dat in uw reservatie staat.",
      wa_title: "Via WhatsApp", wa_text: "Het snelst: stuur het voorbereide bericht. U krijgt meteen uw link terug, als uw nummer in uw reservatie staat.", wa_btn: "Open WhatsApp",
      contact_title: "Via e-mail of gsm", contact_label: "Uw e-mailadres of gsm-nummer",
      contact_hint: "Gsm-nummer met landcode, bv. +44 7700 900123.", send: "Stuur mijn link",
      name_title: "Ik weet niet welk adres in mijn reservatie staat",
      name_intro: "Bv. omdat u via Booking.com of Expedia boekte. Vul uw familienaam en uw vertrekdatum in.",
      last_name: "Familienaam", departure: "Vertrekdatum",
      ok: "Hoort dit adres of nummer bij een reservatie van vandaag of morgen, dan ontvangt u binnen enkele minuten de link. Kijk ook in uw spam.",
      sent: "We stuurden de link naar:", to_email: s => `e-mail naar ${s}`, to_sms: s => `sms naar ${s}`,
      to_platform: p => `een bericht via ${p}: kijk in de app van ${p} of in de mailbox waarmee u boekte`,
      sent_none: "We vonden uw reservatie, maar er staat geen adres of nummer in. Bel de receptie.",
      not_found: "We vinden geen reservatie van vandaag of morgen met deze naam en vertrekdatum. Controleer de spelling, of bel de receptie.",
      limit: "Te veel pogingen. Probeer het over een uur opnieuw, of bel de receptie.",
      invalid: "Controleer wat u invulde.", error: "Er ging iets mis. Probeer het opnieuw, of bel de receptie.",
      help: "Lukt het niet? Bel de receptie.", call: n => `Bel ${n}`, unknown: "Deze pagina bestaat niet.",
    },
    fr: {
      loading: "Un instant...", title: "Votre page de séjour",
      intro: "Recevez à nouveau le lien vers votre page de séjour, avec votre code PIN et toutes les infos. Nous l'envoyons uniquement à une adresse e-mail ou un numéro de portable de votre réservation.",
      wa_title: "Par WhatsApp", wa_text: "Le plus rapide : envoyez le message préparé. Vous recevez aussitôt votre lien, si votre numéro figure dans votre réservation.", wa_btn: "Ouvrir WhatsApp",
      contact_title: "Par e-mail ou portable", contact_label: "Votre adresse e-mail ou numéro de portable",
      contact_hint: "Numéro avec indicatif du pays, p. ex. +33 6 12 34 56 78.", send: "Envoyer mon lien",
      name_title: "Je ne sais pas quelle adresse figure dans ma réservation",
      name_intro: "Par exemple parce que vous avez réservé via Booking.com ou Expedia. Indiquez votre nom de famille et votre date de départ.",
      last_name: "Nom de famille", departure: "Date de départ",
      ok: "Si cette adresse ou ce numéro correspond à une réservation d'aujourd'hui ou de demain, vous recevez le lien dans quelques minutes. Vérifiez aussi vos spams.",
      sent: "Nous avons envoyé le lien à :", to_email: s => `e-mail à ${s}`, to_sms: s => `SMS au ${s}`,
      to_platform: p => `un message via ${p} : regardez dans l'app ${p} ou dans la boîte mail utilisée pour réserver`,
      sent_none: "Nous avons trouvé votre réservation, mais elle ne contient ni adresse ni numéro. Appelez la réception.",
      not_found: "Nous ne trouvons pas de réservation d'aujourd'hui ou de demain avec ce nom et cette date de départ. Vérifiez l'orthographe, ou appelez la réception.",
      limit: "Trop d'essais. Réessayez dans une heure, ou appelez la réception.",
      invalid: "Vérifiez ce que vous avez saisi.", error: "Une erreur s'est produite. Réessayez, ou appelez la réception.",
      help: "Un souci ? Appelez la réception.", call: n => `Appeler le ${n}`, unknown: "Cette page n'existe pas.",
    },
    en: {
      loading: "One moment...", title: "Your stay page",
      intro: "Get the link to your stay page again, with your PIN code and all info. We only send it to an email address or mobile number from your booking.",
      wa_title: "Via WhatsApp", wa_text: "Fastest: send the prepared message. You get your link back right away, if your number is in your booking.", wa_btn: "Open WhatsApp",
      contact_title: "Via email or mobile", contact_label: "Your email address or mobile number",
      contact_hint: "Mobile number with country code, e.g. +44 7700 900123.", send: "Send my link",
      name_title: "I don't know which address is in my booking",
      name_intro: "For example because you booked via Booking.com or Expedia. Enter your last name and your departure date.",
      last_name: "Last name", departure: "Departure date",
      ok: "If this address or number belongs to a booking for today or tomorrow, you will receive the link within a few minutes. Also check your spam.",
      sent: "We sent the link to:", to_email: s => `email to ${s}`, to_sms: s => `text message to ${s}`,
      to_platform: p => `a message via ${p}: check the ${p} app or the mailbox you booked with`,
      sent_none: "We found your booking, but it has no address or number. Please call reception.",
      not_found: "We cannot find a booking for today or tomorrow with this name and departure date. Check the spelling, or call reception.",
      limit: "Too many attempts. Try again in an hour, or call reception.",
      invalid: "Please check what you entered.", error: "Something went wrong. Try again, or call reception.",
      help: "No luck? Call reception.", call: n => `Call ${n}`, unknown: "This page does not exist.",
    },
    de: {
      loading: "Einen Moment...", title: "Ihre Aufenthaltsseite",
      intro: "Erhalten Sie den Link zu Ihrer Aufenthaltsseite erneut, mit PIN-Code und allen Infos. Wir senden ihn nur an eine E-Mail-Adresse oder Handynummer aus Ihrer Buchung.",
      wa_title: "Per WhatsApp", wa_text: "Am schnellsten: Senden Sie die vorbereitete Nachricht. Sie erhalten sofort Ihren Link, wenn Ihre Nummer in Ihrer Buchung steht.", wa_btn: "WhatsApp öffnen",
      contact_title: "Per E-Mail oder Handy", contact_label: "Ihre E-Mail-Adresse oder Handynummer",
      contact_hint: "Handynummer mit Ländervorwahl, z. B. +49 151 23456789.", send: "Meinen Link senden",
      name_title: "Ich weiß nicht, welche Adresse in meiner Buchung steht",
      name_intro: "Zum Beispiel, weil Sie über Booking.com oder Expedia gebucht haben. Geben Sie Ihren Nachnamen und Ihr Abreisedatum ein.",
      last_name: "Nachname", departure: "Abreisedatum",
      ok: "Gehört diese Adresse oder Nummer zu einer Buchung von heute oder morgen, erhalten Sie den Link in wenigen Minuten. Prüfen Sie auch Ihren Spam-Ordner.",
      sent: "Wir haben den Link gesendet an:", to_email: s => `E-Mail an ${s}`, to_sms: s => `SMS an ${s}`,
      to_platform: p => `eine Nachricht über ${p}: Schauen Sie in die App von ${p} oder in das Postfach, mit dem Sie gebucht haben`,
      sent_none: "Wir haben Ihre Buchung gefunden, aber sie enthält keine Adresse oder Nummer. Bitte rufen Sie die Rezeption an.",
      not_found: "Wir finden keine Buchung von heute oder morgen mit diesem Namen und Abreisedatum. Prüfen Sie die Schreibweise, oder rufen Sie die Rezeption an.",
      limit: "Zu viele Versuche. Versuchen Sie es in einer Stunde erneut, oder rufen Sie die Rezeption an.",
      invalid: "Bitte prüfen Sie Ihre Eingabe.", error: "Etwas ist schiefgelaufen. Versuchen Sie es erneut, oder rufen Sie die Rezeption an.",
      help: "Klappt es nicht? Rufen Sie die Rezeption an.", call: n => `${n} anrufen`, unknown: "Diese Seite gibt es nicht.",
    },
  };
  const API = window.CHECKIN_API || "";
  const params = new URLSearchParams(location.search);
  const hotel = params.get("h") || "";
  let lang = (params.get("lang") || (navigator.language || "en").slice(0, 2)).toLowerCase();
  if (!T[lang]) lang = "en";
  let info = null;
  const $ = (id) => document.getElementById(id);
  const esc = (s) => String(s == null ? "" : s).replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
  const t = (k, ...a) => { const v = T[lang][k]; return typeof v === "function" ? v(...a) : v; };

  function render() {
    document.documentElement.lang = lang;
    document.querySelectorAll("[data-t]").forEach((el) => (el.textContent = t(el.dataset.t)));
    document.querySelectorAll(".lang button").forEach((b) => b.classList.toggle("on", b.dataset.lang === lang));
    if (!info) return;
    const h = info.hotel;
    document.title = h.name;
    $("wa-btn").textContent = t("wa_btn");
    $("call-btn").textContent = t("call", h.phone);
  }

  async function load() {
    let res = null;
    try { res = await fetch(API + "/api/find/" + encodeURIComponent(hotel) + "?lang=" + lang, { cache: "no-store" }); } catch (e) { res = null; }
    $("loading").hidden = true;
    if (!res || !res.ok) { $("loading").hidden = false; $("loading").textContent = t(res && res.status === 404 ? "unknown" : "error"); return; }
    info = await res.json();
    const h = info.hotel, root = document.documentElement.style;
    root.setProperty("--acc", h.colors.accent);
    root.setProperty("--accd", h.colors.accent_donker);
    root.setProperty("--text", h.colors.tekst);
    root.setProperty("--bg", h.colors.achtergrond);
    $("logo").src = h.logo_url; $("logo").alt = h.name; $("logo-link").href = h.website;
    if (h.favicon_url) { $("favicon").removeAttribute("type"); $("favicon").href = h.favicon_url; }
    $("call-btn").href = "tel:" + h.phone.replace(/\s/g, "");
    $("wa-btn").href = info.whatsapp || "#";
    ["intro", "contact-card", "name-card", "help-card"].forEach((id) => ($(id).hidden = false));
    $("wa-card").hidden = !info.whatsapp;
    render();
  }

  async function ask(body, out, btn) {
    btn.disabled = true;
    let res = null, data = null;
    try {
      res = await fetch(API + "/api/find/" + encodeURIComponent(hotel), { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) });
      data = await res.json();
    } catch (e) { data = null; }
    btn.disabled = false;
    out.hidden = false;
    out.classList.toggle("warn", !data || data.status !== "ok" && data.status !== "sent" || data.status === "sent" && !data.to.length);
    if (!data) { out.textContent = t("error"); return; }
    if (data.status === "sent") {
      if (!data.to.length) { out.textContent = t("sent_none"); return; }
      out.innerHTML = `<div><b>${esc(t("sent"))}</b><ul style="margin:6px 0 0;padding-left:20px">${data.to.map((x) =>
        `<li>${esc(x.platform ? t("to_platform", x.platform) : t(x.channel === "email" ? "to_email" : "to_sms", x.shown))}</li>`).join("")}</ul></div>`;
      return;
    }
    out.textContent = t(["ok", "not_found", "limit", "invalid"].includes(data.status) ? data.status : "error");
  }

  $("contact-form").addEventListener("submit", (e) => {
    e.preventDefault();
    const v = $("contact").value.trim();
    if (!v) { $("contact").focus(); return; }
    ask({ method: v.includes("@") ? "email" : "phone", value: v }, $("contact-result"), $("contact-btn"));
  });
  $("name-form").addEventListener("submit", (e) => {
    e.preventDefault();
    const n = $("last-name").value.trim(), d = $("departure").value;
    if (!n) { $("last-name").focus(); return; }
    if (!d) { $("departure").focus(); return; }
    ask({ method: "name", value: n, departure: d }, $("name-result"), $("name-btn"));
  });
  document.querySelectorAll(".lang button").forEach((b) => b.addEventListener("click", () => { lang = b.dataset.lang; render(); load(); }));
  render();
  load();
})();
