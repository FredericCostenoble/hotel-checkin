"""WhatsApp-sjablonen beheren in de monitor (processes/whatsapp_templates.py), zonder echte Twilio-aanroep."""

import json
from datetime import timedelta

import httpx
import pytest

from hotel_checkin.guests import repository as repo
from hotel_checkin.messaging import content_templates
from hotel_checkin.processes import send_messages
from hotel_checkin.processes import whatsapp_templates as wa


@pytest.fixture(autouse=True)
def _setup(monkeypatch):
    repo.use_memory_store()
    monkeypatch.setenv("TWILIO_ACCOUNT_SID", "ACtest")
    monkeypatch.setenv("TWILIO_AUTH_TOKEN", "token")
    monkeypatch.setenv("WEBSITE_HOSTNAME", "func.example.net")
    monkeypatch.delenv("CHECKIN_FORM_URL", raising=False)


class FakeTwilio:
    """Content API van Twilio: aanmaken, indienen, status, verwijderen."""

    def __init__(self):
        self.created: list[dict] = []
        self.submitted: list[dict] = []
        self.deleted: list[str] = []
        self.status: dict[str, str] = {}
        self.status_calls = 0

    def client(self) -> httpx.Client:
        def handler(req: httpx.Request) -> httpx.Response:
            path = req.url.path
            if req.method == "POST" and path == "/v1/Content":
                body = json.loads(req.content)
                sid = f"HX{len(self.created) + 1:032d}"
                self.created.append(body | {"sid": sid})
                self.status[sid] = "received"
                return httpx.Response(201, json={"sid": sid})
            if req.method == "POST" and path.endswith("/ApprovalRequests/whatsapp"):
                self.submitted.append(json.loads(req.content) | {"sid": path.split("/")[3]})
                return httpx.Response(201, json={"status": "received", "rejection_reason": ""})
            if req.method == "GET" and path.endswith("/ApprovalRequests"):
                self.status_calls += 1
                sid = path.split("/")[3]
                return httpx.Response(200, json={"whatsapp": {"status": self.status[sid],
                                                              "rejection_reason": "te vaag" if self.status[sid] == "rejected" else ""}})
            if req.method == "DELETE":
                self.deleted.append(path.split("/")[3])
                return httpx.Response(204)
            return httpx.Response(404, json={"code": 20404, "message": "not found"})

        return httpx.Client(transport=httpx.MockTransport(handler))


def _lang(view, step, lang):
    t = next(x for x in view["templates"] if x["step"] == step)
    return next(x for x in t["langs"] if x["lang"] == lang)


def test_default_texts_are_valid():
    """Alle standaardteksten voldoen aan de regels van Meta (ook de knoptekst van hoogstens 20 tekens)."""
    v = wa.view("lucca", refresh=False)
    for t in v["templates"]:
        for lg in t["langs"]:
            assert lg["text"]["body"], (t["step"], lg["lang"])
            assert lg["errors"] == [], (t["step"], lg["lang"], lg["errors"])
            assert lg["state"] == "new"


def test_variables_match_send_messages():
    """De oude sjablonen (instellingen) hebben de eerste plaatsen van nu, met de knop als laatste plaats."""
    for step, names in send_messages.WHATSAPP_VARIABLES.items():
        assert wa.var_names(step, count=len(names)) == names


def test_var_names_of_older_versions():
    assert wa.var_names("access_code") == ("kamer_kort", "pincode", "checkin_suffix")
    assert wa.var_names("access_code", count=2) == ("kamer_kort", "checkin_suffix")
    assert wa.var_names("access_code", body="Uw kamer {{1}} is klaar.") == ("kamer_kort", "checkin_suffix")
    assert wa.var_names("breakfast_list", count=3) == ("dag", "samenvatting", "pdf_pad")


def test_validate_rules():
    v = wa.validate
    assert v("breakfast_list", {"body": "{{1}} list, {{2}} ok"}) == ["De tekst mag niet beginnen met een plaats ({{...}})."]
    assert any("eindigen" in e for e in v("breakfast_list", {"body": "List {{1}}: {{2}}"}))
    assert any("na elkaar" in e for e in v("breakfast_list", {"body": "List {{1}} {{2}} ok"}))
    assert any("ontbreekt" in e for e in v("breakfast_list", {"body": "List {{1}} ok"}))
    assert any("Onbekende" in e for e in v("room_change", {"body": "Kamer {{1}} en {{2}} ok"}))
    assert any("knoptekst is te lang" in e for e in v("confirmation", {"body": "Dag {{1}}, welkom.", "button": "x" * 21}))
    assert any("knoptekst ontbreekt" in e for e in v("confirmation", {"body": "Dag {{1}}, welkom."}))
    assert any("geen knop" in e for e in v("breakfast_list", {"body": "List {{1}}: {{2}} ok", "button": "Ga"}))


def test_submit_creates_content_with_button_and_footer():
    fake = FakeTwilio()
    res = wa.submit("lucca", "confirmation", "nl", "fred", client=fake.client())
    assert res["ok"], res
    c = fake.created[0]
    assert c["language"] == "nl" and c["friendly_name"] == "lucca_prd_confirmation_nl_v1"
    card = c["types"]["whatsapp/card"]
    assert card["header_text"] == "Uw reservatie in Hotel Lucca"
    assert card["footer"] == "Hotel Lucca, Naaldenstraat 30, Brugge"
    assert card["actions"] == [{"type": "URL", "title": "Check-in invullen", "url": "https://checkin.hotellucca.be/?r={{2}}"}]
    assert c["variables"] == {"1": "Jan", "2": "a1b2c3d4&lang=nl"}
    assert fake.submitted[0]["name"] == "lucca_prd_confirmation_nl_v1" and fake.submitted[0]["category"] == "UTILITY"
    assert _lang(wa.view("lucca", refresh=False), "confirmation", "nl")["state"] == "waiting"


def test_submit_cta_text_and_media_types():
    fake = FakeTwilio()
    wa.submit("lucca", "access_code", "en", "fred", client=fake.client())
    wa.submit("lucca", "room_change", "fr", "fred", client=fake.client())
    wa.submit("lucca", "breakfast_list", "en", "fred", client=fake.client())
    cta, text, media = (c["types"] for c in fake.created)
    assert cta["whatsapp/card"]["actions"][0]["url"] == "https://checkin.hotellucca.be/?r={{3}}"
    assert cta["whatsapp/card"]["footer"] == "Hotel Lucca, Naaldenstraat 30, Brugge"
    assert fake.created[0]["variables"] == {"1": "16 verdiep 1", "2": "3453", "3": "a1b2c3d4&lang=nl"}
    assert text["whatsapp/card"]["header_text"] == "Changement de chambre"
    assert text["whatsapp/card"]["actions"][0]["title"] == "Votre réservation"
    assert media["twilio/media"]["media"] == ["https://func.example.net/api/lists/{{3}}"]
    assert fake.created[2]["variables"] == {"1": "Friday 13/11/2026", "2": "12 persons in 6 rooms",
                                            "3": "lucca/breakfast/2026-11-13/0/sample/breakfast-list-2026-11-13.pdf"}
    assert fake.created[2]["language"] == "en"


def test_status_only_asked_while_waiting_and_approved_becomes_active():
    fake = FakeTwilio()
    wa.submit("lucca", "reminder", "de", "fred", client=fake.client())
    assert send_messages.whatsapp_template("lucca", "reminder", "de") is None  # nog niet goedgekeurd
    assert wa.check("lucca", client=fake.client()) == []  # net ingediend: nog niet opnieuw vragen
    assert fake.status_calls == 0
    fake.status[fake.created[0]["sid"]] = "approved"
    assert wa.check("lucca", client=fake.client(), min_age=timedelta(0)) == ["lucca_prd_reminder_de_v1 goedgekeurd"]
    assert send_messages.whatsapp_template("lucca", "reminder", "de") == fake.created[0]["sid"]
    assert _lang(wa.view("lucca", refresh=False), "reminder", "de")["state"] == "approved"
    calls = fake.status_calls
    wa.check("lucca", client=fake.client(), min_age=timedelta(0))
    assert fake.status_calls == calls  # goedgekeurd: nooit meer gevraagd


def test_new_version_keeps_old_active_until_approved():
    fake = FakeTwilio()
    wa.submit("lucca", "room_change", "nl", "fred", client=fake.client())
    first = fake.created[0]["sid"]
    fake.status[first] = "approved"
    wa.check("lucca", client=fake.client(), min_age=timedelta(0))
    wa.save_text("lucca", "room_change", "nl", {"body": "Nieuwe kamer {{1}}, meer info via de knop.", "button": "Uw reservatie"}, "fred")
    assert _lang(wa.view("lucca", refresh=False), "room_change", "nl")["state"] == "changed"
    wa.submit("lucca", "room_change", "nl", "fred", client=fake.client())
    assert fake.created[1]["friendly_name"] == "lucca_prd_room_change_nl_v2"
    assert send_messages.whatsapp_template("lucca", "room_change", "nl") == first  # oude versie blijft in gebruik
    fake.status[fake.created[1]["sid"]] = "approved"
    wa.check("lucca", client=fake.client(), min_age=timedelta(0))
    assert send_messages.whatsapp_template("lucca", "room_change", "nl") == fake.created[1]["sid"]


def test_rejected_shows_reason_and_resubmit_replaces_it():
    fake = FakeTwilio()
    wa.submit("lucca", "confirmation", "fr", "fred", client=fake.client())
    sid = fake.created[0]["sid"]
    fake.status[sid] = "rejected"
    wa.check("lucca", client=fake.client(), min_age=timedelta(0))
    lg = _lang(wa.view("lucca", refresh=False), "confirmation", "fr")
    assert lg["state"] == "rejected" and lg["pending"]["reason"] == "te vaag"
    res = wa.submit_all("lucca", "fred", client=fake.client())  # de andere nieuwe sjablonen wel
    assert ("confirmation", "fr") not in [(r["step"], r["lang"]) for r in res["results"]]  # afgekeurd, ongewijzigd
    assert len(res["results"]) == 21 and res["ok"]  # 4 x 5 voor gasten + 2 voor het personeel, min 1
    wa.save_text("lucca", "confirmation", "fr", {"body": "Bonjour {{1}}, merci pour votre réservation.",
                                                  "button": "Mon check-in"}, "fred")
    wa.submit("lucca", "confirmation", "fr", "fred", client=fake.client())
    assert sid in fake.deleted  # afgekeurde versie opgeruimd bij Twilio
    assert _lang(wa.view("lucca", refresh=False), "confirmation", "fr")["state"] == "waiting"


def test_save_and_reset_text():
    wa.save_text("lucca", "room_change", "en", {"body": "Room {{1}} is yours.", "button": "Go"}, "fred")
    lg = _lang(wa.view("lucca", refresh=False), "room_change", "en")
    assert lg["edited"] and lg["text"]["body"] == "Room {{1}} is yours."
    wa.reset_text("lucca", "room_change", "en", "fred")
    lg = _lang(wa.view("lucca", refresh=False), "room_change", "en")
    assert not lg["edited"] and lg["text"] == lg["default"]


def test_twilio_error_is_shown_not_raised():
    def handler(req):
        return httpx.Response(400, json={"code": 21656, "message": "Invalid content"})

    res = wa.submit("lucca", "room_change", "de", "fred", client=httpx.Client(transport=httpx.MockTransport(handler)))
    assert not res["ok"] and "21656" in res["message"]
    assert _lang(wa.view("lucca", refresh=False), "room_change", "de")["state"] == "error"


def test_settings_sid_still_used_as_fallback(monkeypatch):
    monkeypatch.setenv("LUCCA_WHATSAPP_TEMPLATE_ROOM_CHANGE_EN", "HXmanual")
    assert send_messages.whatsapp_template("lucca", "room_change", "nl") == "HXmanual"


def test_build_types_card_without_button():
    assert content_templates.build_types("Hallo {{1}} ok", footer="Voet") == {
        "twilio/card": {"title": "Hallo {{1}} ok", "subtitle": "Voet"}}


def test_tst_names_differ(monkeypatch):
    monkeypatch.setenv("APP_ENV", "tst")
    assert wa.template_name("lucca", "confirmation", "nl", 3) == "lucca_tst_confirmation_nl_v3"


def test_pin_code_only_in_access_code():
    """De pincode alleen in het bericht met de toegang (goedgekeurd na bezwaar), nergens anders."""
    for t in wa.view("lucca", refresh=False)["templates"]:
        assert ("pincode" in t["vars"]) == (t["step"] == "access_code"), t["step"]


def test_old_active_version_keeps_its_own_variables():
    """Tot de versie met pincode goedgekeurd is, gaat de vorige (zonder pincode) uit, met haar eigen plaatsen."""
    data = {"access_code": {"nl": {"version": 1, "active": {"sid": "HXold", "name": "lucca_prd_access_code_nl_v1",
                                                            "text": {"body": "Uw kamer {{1}} is klaar."}}}}}
    wa._save("lucca", data, "test")
    assert send_messages.whatsapp_choice("lucca", "access_code", "nl") == ("HXold", ("kamer_kort", "checkin_suffix"))
    v = wa.view("lucca", refresh=False)
    assert _lang(v, "access_code", "nl")["errors"]  # de oude tekst mist de pincode: eerst de nieuwe overnemen
    assert v["newer_defaults"] >= 1
    wa.use_defaults("lucca", "fred")
    fake = FakeTwilio()
    assert wa.submit("lucca", "access_code", "nl", "fred", client=fake.client())["ok"]
    assert send_messages.whatsapp_choice("lucca", "access_code", "nl")[0] == "HXold"
    fake.status[fake.created[0]["sid"]] = "approved"
    wa.check("lucca", client=fake.client(), min_age=timedelta(0))
    assert send_messages.whatsapp_choice("lucca", "access_code", "nl") == (
        fake.created[0]["sid"], ("kamer_kort", "pincode", "checkin_suffix"))


def test_sample_pdf_exists_for_meta():
    """Meta haalt de voorbeeld-pdf op: die link moet een echte pdf geven, zonder gastgegevens."""
    from hotel_checkin.processes import daily_lists

    path = daily_lists.sample_pdf_path("lucca", "cleaning")
    hotel, kind, day, expires, sig, _ = path.split("/")
    name, pdf = daily_lists.pdf_for_link(hotel, kind, day, expires, sig)
    assert pdf.startswith(b"%PDF") and name == "cleaning-list-2026-11-13.pdf"
    assert daily_lists.pdf_for_link(hotel, kind, day, "0", "fake") is None


def test_old_rejected_versions_dropped_once():
    repo.set_config_doc("lucca", wa.DOC, {"access_code": {"nl": {"version": 1, "pending": {
        "status": "rejected", "text": {"body": "Kamer {{1}}, code {{2}} ok", "button": "X"}}}}}, "x")
    lg = _lang(wa.view("lucca", refresh=False), "access_code", "nl")
    assert lg["pending"] is None and lg["text"] == lg["default"] and lg["errors"] == []


def test_header_rules_and_types():
    assert any("titel is te lang" in e for e in wa.validate("room_change", {"body": "Kamer {{1}} ok", "header": "x" * 61}))
    assert any("geen titel" in e for e in wa.validate("breakfast_list", {"body": "List {{1}}: {{2}} ok", "header": "T"}))
    assert content_templates.build_types("Hallo {{1}} ok", footer="Voet") == {
        "twilio/card": {"title": "Hallo {{1}} ok", "subtitle": "Voet"}}
    assert "twilio/call-to-action" in content_templates.build_types("Hallo {{1}} ok", "Ga", "https://x/{{2}}")


def test_reset_waiting_old_text_goes_to_default():
    fake = FakeTwilio()
    wa.save_text("lucca", "reminder", "nl", {"body": "Beste {{1}}, uw pincode volgt.", "button": "Ga"}, "fred")
    wa.submit("lucca", "reminder", "nl", "fred", client=fake.client())
    assert _lang(wa.view("lucca", refresh=False), "reminder", "nl")["state"] == "waiting"
    wa.reset_text("lucca", "reminder", "nl", "fred")
    lg = _lang(wa.view("lucca", refresh=False), "reminder", "nl")
    assert lg["text"] == lg["default"] and lg["state"] == "new"
    wa.submit("lucca", "reminder", "nl", "fred", client=fake.client())
    assert fake.created[1]["friendly_name"] == "lucca_prd_reminder_nl_v2" and fake.deleted == [fake.created[0]["sid"]]


def test_use_new_defaults_after_approval(monkeypatch):
    fake = FakeTwilio()
    wa.save_text("lucca", "room_change", "nl", {"body": "Oud {{1}} tekst.", "button": "Ga"}, "fred")
    wa.submit("lucca", "room_change", "nl", "fred", client=fake.client())
    fake.status[fake.created[0]["sid"]] = "approved"
    wa.check("lucca", client=fake.client(), min_age=timedelta(0))
    v = wa.view("lucca", refresh=False)
    assert _lang(v, "room_change", "nl")["state"] == "approved" and v["newer_defaults"] == 1
    assert wa.use_defaults("lucca", "fred") == 1
    lg = _lang(wa.view("lucca", refresh=False), "room_change", "nl")
    assert lg["state"] == "changed" and lg["text"] == lg["default"]
    assert wa.view("lucca", refresh=False)["newer_defaults"] == 0


def test_tst_uses_prd_templates(monkeypatch):
    """TST dient niets in: het neemt de nieuwste goedgekeurde PRD-versie over (zelfde Twilio-account)."""
    monkeypatch.setenv("APP_ENV", "tst")

    def handler(req):
        return httpx.Response(200, json={"contents": [
            {"sid": "HXa", "friendly_name": "lucca_prd_access_code_nl_v1", "approval_requests": {"status": "approved"}},
            {"sid": "HXb", "friendly_name": "lucca_prd_access_code_nl_v3", "approval_requests": {"status": "approved"},
             "variables": {"1": "16", "2": "a1b2"}},
            {"sid": "HXc", "friendly_name": "lucca_prd_access_code_nl_v4", "approval_requests": {"status": "pending"}},
            {"sid": "HXd", "friendly_name": "lucca_tst_room_change_nl_v1", "approval_requests": {"status": "approved"}},
            {"sid": "HXe", "friendly_name": "other_prd_access_code_nl_v9", "approval_requests": {"status": "approved"}},
        ], "meta": {"next_page_url": None}})

    client = httpx.Client(transport=httpx.MockTransport(handler))
    assert wa.sync_shared("lucca", client=client, min_age=timedelta(0)) == ["lucca_prd_access_code_nl_v3 in gebruik"]
    assert send_messages.whatsapp_choice("lucca", "access_code", "nl") == ("HXb", ("kamer_kort", "checkin_suffix"))
    assert send_messages.whatsapp_template("lucca", "room_change", "nl") is None
    v = wa.view("lucca", refresh=False)
    assert v["shared_from"] == "prd" and _lang(v, "access_code", "nl")["active"]["name"] == "lucca_prd_access_code_nl_v3"
    with pytest.raises(ValueError):
        wa.submit("lucca", "access_code", "nl", "fred")


def test_tst_button_link_goes_via_prd_form(monkeypatch):
    from hotel_checkin.messaging import templates

    monkeypatch.setenv("APP_ENV", "tst")
    monkeypatch.setenv("CHECKIN_FORM_URL", "https://checkin-tst.hotellucca.be/?r={token}")
    assert templates.checkin_suffix("lucca", "tok", "fr") == "tok&lang=fr&env=tst"
    monkeypatch.setenv("APP_ENV", "prd")
    monkeypatch.delenv("CHECKIN_FORM_URL")
    assert templates.checkin_suffix("lucca", "tok", "fr") == "tok&lang=fr"


def test_storage_split_per_message_and_reads_old_format():
    """Alles samen werd te groot voor één veld in Azure (64 KB): per bericht een rij. Oude opslag wordt nog gelezen."""
    import json

    repo.set_config_doc("lucca", wa.DOC, {"_rev": 2, "room_change": {"nl": {"text": {"body": "Kamer {{1}} oud.", "button": "Ga"}}}}, "x")
    assert _lang(wa.view("lucca", refresh=False), "room_change", "nl")["text"]["body"] == "Kamer {{1}} oud."
    wa.reset_text("lucca", "room_change", "nl", "fred")
    assert repo.get_config_doc("lucca", wa.DOC)["value"] == {"_rev": 2, "_split": True}
    assert "nl" in repo.get_config_doc("lucca", wa.DOC + "_room_change")["value"]
    # Realistische toestand (actief + ingediend + tekst, alle talen): elke rij ruim onder 64 KB
    fake = FakeTwilio()
    wa.submit_all("lucca", "fred", client=fake.client())
    for c in fake.created:
        fake.status[c["sid"]] = "approved"
    wa.check("lucca", client=fake.client(), min_age=timedelta(0))
    for st in wa.TEMPLATES:
        for lg in wa.TEMPLATES[st]["langs"]:
            wa.save_text("lucca", st, lg, {**wa.current_text("lucca", st, lg), "footer": "x"}, "fred")
    wa.submit_all("lucca", "fred", client=fake.client())
    for st in wa.TEMPLATES:
        size = len(json.dumps(repo.get_config_doc("lucca", f"{wa.DOC}_{st}")["value"]).encode("utf-16-le"))
        assert size < 32_000, (st, size)


def test_saved_text_equal_to_approved_version_still_gets_new_default():
    """Een in de monitor bewaarde tekst die niet verschilt van de goedgekeurde versie, krijgt de nieuwe standaardtekst."""
    old = {"header": "Uw verblijf in Hotel Lucca", "body": "Uw kamer {{1}} is klaar.", "button": "Uw reservatie"}
    data = {"access_code": {"nl": {"version": 1, "text": dict(old),
                                   "active": {"sid": "HXold", "name": "lucca_prd_access_code_nl_v1", "text": dict(old)}},
                            "fr": {"version": 1, "text": {"body": "Eigen tekst {{1}} {{2}}.", "button": "X"},
                                   "active": {"sid": "HXfr", "name": "lucca_prd_access_code_fr_v1", "text": dict(old)}}}}
    wa._save("lucca", data, "test")
    assert wa.use_defaults("lucca", "fred") >= 1
    after = wa._load("lucca")["access_code"]
    assert "{{2}}" in after["nl"]["text"]["body"] and after["fr"]["text"]["body"] == "Eigen tekst {{1}} {{2}}."


def test_rejected_version_rechecked_hourly_for_appeal():
    """Na een bezwaar kan Meta een afgekeurde versie alsnog goedkeuren: die wordt elk uur opnieuw opgevraagd."""
    fake = FakeTwilio()
    wa.submit("lucca", "room_change", "de", "fred", client=fake.client())
    sid = fake.created[0]["sid"]
    fake.status[sid] = "rejected"
    assert wa.check("lucca", client=fake.client(), min_age=timedelta(0))  # afgekeurd: gemeld
    n = fake.status_calls
    assert wa.check("lucca", client=fake.client(), min_age=wa.CHECK_EVERY) == []
    assert fake.status_calls == n  # de timer: niet meteen opnieuw, pas na een uur
    data = wa._load("lucca")
    data["room_change"]["de"]["pending"]["checked_at"] = (wa._now() - timedelta(hours=2)).isoformat()
    wa._save("lucca", data, "test")
    fake.status[sid] = "approved"
    assert wa.check("lucca", client=fake.client(), min_age=wa.CHECK_EVERY) == [data["room_change"]["de"]["pending"]["name"] + " goedgekeurd"]
    assert send_messages.whatsapp_template("lucca", "room_change", "de") == sid


def test_refresh_button_also_rechecks_rejected_right_away():
    fake = FakeTwilio()
    wa.submit("lucca", "room_change", "fr", "fred", client=fake.client())
    sid = fake.created[0]["sid"]
    fake.status[sid] = "rejected"
    wa.check("lucca", client=fake.client(), min_age=timedelta(0))
    fake.status[sid] = "approved"
    assert wa.check("lucca", client=fake.client(), min_age=timedelta(0))  # knop: niet een uur wachten
    assert send_messages.whatsapp_template("lucca", "room_change", "fr") == sid
