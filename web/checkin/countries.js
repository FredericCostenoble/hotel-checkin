// Landen met hun internationale kengetal. Namen komen uit de browser (Intl.DisplayNames) in de taal van de gast.
const COUNTRIES = [
  ["BE", "32"], ["NL", "31"], ["FR", "33"], ["DE", "49"], ["LU", "352"], ["GB", "44"], ["IE", "353"],
  ["ES", "34"], ["PT", "351"], ["IT", "39"], ["CH", "41"], ["AT", "43"], ["DK", "45"], ["SE", "46"],
  ["NO", "47"], ["FI", "358"], ["IS", "354"], ["PL", "48"], ["CZ", "420"], ["SK", "421"], ["HU", "36"],
  ["SI", "386"], ["HR", "385"], ["RO", "40"], ["BG", "359"], ["GR", "30"], ["CY", "357"], ["MT", "356"],
  ["EE", "372"], ["LV", "371"], ["LT", "370"], ["UA", "380"], ["TR", "90"], ["IL", "972"], ["AE", "971"],
  ["US", "1"], ["CA", "1"], ["MX", "52"], ["BR", "55"], ["AR", "54"], ["CL", "56"], ["CO", "57"],
  ["AU", "61"], ["NZ", "64"], ["JP", "81"], ["KR", "82"], ["CN", "86"], ["HK", "852"], ["TW", "886"],
  ["SG", "65"], ["IN", "91"], ["TH", "66"], ["ZA", "27"], ["MA", "212"], ["EG", "20"],
];
const DIAL = Object.fromEntries(COUNTRIES);

function countryName(iso, lang) {
  try { return new Intl.DisplayNames([lang], { type: "region" }).of(iso); } catch (e) { return iso; }
}

// Vul een keuzelijst: landnaam (+kengetal), alfabetisch in de taal van de gast.
function fillCountrySelect(select, lang, selected) {
  const sorted = COUNTRIES.slice().sort((a, b) => countryName(a[0], lang).localeCompare(countryName(b[0], lang), lang));
  select.innerHTML = "";
  for (const [iso, dial] of sorted) {
    const opt = document.createElement("option");
    opt.value = iso;
    opt.dataset.full = countryName(iso, lang) + " (+" + dial + ")";
    opt.dataset.short = iso + " +" + dial;
    opt.textContent = opt.dataset.full;
    select.appendChild(opt);
  }
  select.value = DIAL[selected] ? selected : "BE";
  compactCountrySelect(select);
}

// In het gesloten veld alleen de code tonen (bv. "BE +32"); in de open lijst de volledige namen.
function compactCountrySelect(select) {
  for (const opt of select.options) opt.textContent = opt.selected ? opt.dataset.short : opt.dataset.full;
}

function expandCountrySelect(select) {
  for (const opt of select.options) opt.textContent = opt.dataset.full;
}

function wireCountrySelect(select) {
  select.addEventListener("mousedown", () => expandCountrySelect(select));
  select.addEventListener("focus", () => expandCountrySelect(select));
  select.addEventListener("change", () => { compactCountrySelect(select); });
  select.addEventListener("blur", () => compactCountrySelect(select));
}

// Splits een +-nummer in land en nationaal nummer. Bij gedeelde kengetallen (+1) wint het voorkeursland.
function splitPhone(e164, preferIso) {
  if (!e164 || !e164.startsWith("+")) return { iso: preferIso, national: e164 || "" };
  const digits = e164.slice(1);
  let best = null;
  for (const [iso, dial] of COUNTRIES) {
    if (digits.startsWith(dial) && (!best || dial.length > best.dial.length || (dial.length === best.dial.length && iso === preferIso))) {
      best = { iso, dial };
    }
  }
  return best ? { iso: best.iso, national: digits.slice(best.dial.length) } : { iso: preferIso, national: e164 };
}

// Stel het volledige nummer samen. Begint de invoer met + of 00, dan wordt de landkeuze genegeerd.
function composePhone(iso, input) {
  const raw = (input || "").trim();
  if (!raw) return "";
  if (raw.startsWith("+")) return "+" + raw.replace(/\D/g, "");
  if (raw.startsWith("00")) return "+" + raw.replace(/\D/g, "").slice(2);
  let national = raw.replace(/\D/g, "");
  if (iso !== "IT") national = national.replace(/^0+/, ""); // in Italie hoort de 0 bij het nummer
  return "+" + DIAL[iso] + national;
}
