// Online check-in: haalt de reservatie op via /api/checkin/<token> en bewaart de contactgegevens.
(function () {
  const params = new URLSearchParams(location.search);
  const token = params.get("r") || "";
  let lang = (params.get("lang") || (navigator.language || "en").slice(0, 2)).toLowerCase();
  if (!I18N[lang]) lang = "en";
  let data = null;
  let langChosenByGuest = !!params.get("lang");

  const $ = (id) => document.getElementById(id);
  const t = (key) => (I18N[lang][key] || I18N.en[key] || "").replace("{voornaam}", data ? data.first_name : "");

  function fmtDate(iso) {
    const [y, m, d] = iso.split("-").map(Number);
    return new Intl.DateTimeFormat(lang + "-BE", { weekday: "long", day: "numeric", month: "long", year: "numeric" })
      .format(new Date(y, m - 1, d));
  }

  function render() {
    document.documentElement.lang = lang;
    document.querySelectorAll("[data-t]").forEach((el) => (el.textContent = t(el.dataset.t)));
    ["phone_cc", "backup_phone_cc"].forEach((id) => wireCountrySelect($(id)));

  // Controle per veld zodra de gast het veld verlaat; de fout verdwijnt tijdens het verbeteren.
  const EMAIL_RE = /^[^@\s]+@[^@\s]+\.[^@\s]{2,}$/;
  function showFieldError(id, bad) {
    $("err-" + id).hidden = !bad;
    $(id).classList.toggle("invalid", bad);
  }
  ["email", "backup_email"].forEach((id) => {
    $(id).addEventListener("blur", () => {
      const v = $(id).value.trim();
      showFieldError(id, id === "email" ? !EMAIL_RE.test(v) : !!v && !EMAIL_RE.test(v));
    });
    $(id).addEventListener("input", () => showFieldError(id, false));
  });
  ["phone", "backup_phone"].forEach((id) => {
    const sel = $(id + "_cc");
    $(id).addEventListener("input", () => { cleanPhoneInput(sel, $(id)); showFieldError(id, false); });
    $(id).addEventListener("blur", () => showFieldError(id, !phoneLooksValid(sel, $(id))));
    sel.addEventListener("change", () => { if ($(id).value) showFieldError(id, !phoneLooksValid(sel, $(id))); });
  });

  document.querySelectorAll(".langs button").forEach((b) => b.classList.toggle("active", b.dataset.lang === lang));
    ["phone_cc", "backup_phone_cc"].forEach((id) => fillCountrySelect($(id), lang, $(id).value || defaultCountry()));
    if (!data) return;
    $("intro").textContent = t(data.email || data.phone ? "intro_confirm" : "intro");
    $("r-name").textContent = data.first_name + " " + data.last_name;
    $("r-arrival").textContent = fmtDate(data.arrival);
    $("r-departure").textContent = fmtDate(data.departure);
    $("r-room").textContent = data.room_type;
    document.querySelectorAll(".room-row").forEach((el) => (el.hidden = !data.room_type));
    const h = data.hotel;
    $("privacy-link").href = (h.privacy_urls && h.privacy_urls[lang]) || h.privacy_url;
  }

  function defaultCountry() {
    return (data && data.country && DIAL[data.country]) ? data.country : "BE";
  }

  function setPhone(prefix, e164) {
    const parts = splitPhone(e164, defaultCountry());
    fillCountrySelect($(prefix + "_cc"), lang, parts.iso);
    $(prefix).value = parts.national;
  }

  function showMessage(kind) {
    $("loading").hidden = true;
    $("form-section").hidden = true;
    $("message").hidden = false;
    $("message-title").textContent = t(kind + "_title");
    $("message-text").textContent = t(kind + "_text");
  }

  function applyHotel(h) {
    const root = document.documentElement.style;
    root.setProperty("--accent", h.colors.accent);
    root.setProperty("--accent-dark", h.colors.accent_donker);
    root.setProperty("--text", h.colors.tekst);
    root.setProperty("--bg", h.colors.achtergrond);
    $("logo").src = h.logo_url;
    $("logo").alt = h.name;
    $("logo-link").href = h.website;
    $("f-name").textContent = h.name;
    $("f-address").textContent = h.address;
    $("f-phone").textContent = h.phone;
    $("f-phone").href = "tel:" + h.phone.replace(/\s/g, "");
    $("f-email").textContent = h.email;
    $("f-email").href = "mailto:" + h.email;
    $("f-website").href = h.website;
  }

  async function load() {
    render();
    if (!token) return showMessage("notfound");
    let res;
    try {
      res = await fetch("/api/checkin/" + encodeURIComponent(token));
    } catch (e) {
      return showMessage("notfound");
    }
    if (!res.ok) return showMessage("notfound");
    data = await res.json();
    applyHotel(data.hotel);
    if (!langChosenByGuest && I18N[data.language]) lang = data.language;
    render();
    if (data.state !== "open") return showMessage(data.state);
    $("email").value = data.email;
    $("backup_email").value = data.backup_email;
    setPhone("phone", data.phone);
    setPhone("backup_phone", data.backup_phone);
    $("backup-box").open = !!(data.backup_email || data.backup_phone);
    $("language").value = lang;
    $("no_marketing").checked = data.no_marketing;
    $("already").hidden = !data.completed;
    $("loading").hidden = true;
    $("form-section").hidden = false;
  }

  document.querySelectorAll(".langs button").forEach((b) =>
    b.addEventListener("click", () => {
      lang = b.dataset.lang;
      langChosenByGuest = true;
      if (!$("form-section").hidden) $("language").value = lang;
      render();
    })
  );

  $("form").addEventListener("submit", async (ev) => {
    ev.preventDefault();
    ["err-email", "err-phone", "err-backup_email", "err-backup_phone", "err-general"].forEach((id) => ($(id).hidden = true));
    const btn = $("submit");
    btn.disabled = true;
    btn.textContent = t("saving");
    try {
      const res = await fetch("/api/checkin/" + encodeURIComponent(token), {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          email: $("email").value,
          phone: composePhone($("phone_cc").value, $("phone").value),
          backup_email: $("backup_email").value,
          backup_phone: composePhone($("backup_phone_cc").value, $("backup_phone").value),
          language: $("language").value,
          no_marketing: $("no_marketing").checked,
        }),
      });
      const body = await res.json().catch(() => ({}));
      if (res.ok && body.ok) {
        lang = $("language").value;
        render();
        return showMessage("thanks");
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

  load();
})();
