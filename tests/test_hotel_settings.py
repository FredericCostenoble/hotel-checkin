"""Instellingen van een hotel wijzigen in de monitor (core/hotel_settings.py)."""

import pytest

from hotel_checkin.core import hotel_settings, hotels
from hotel_checkin.core.config import hotel_setting
from hotel_checkin.guests import repository as repo


@pytest.fixture(autouse=True)
def store():
    repo.use_memory_store()
    hotels.forget_overrides()
    yield
    hotels.forget_overrides()


def test_view_lists_sections_with_types_and_help():
    v = hotel_settings.view("lucca")
    names = [s["section"] for s in v["sections"]]
    assert "hotel" in names and "kleuren" in names and "flows" not in names
    robot = next(s for s in v["sections"] if s["section"] == "robot")
    assert {f["key"]: f["type"] for f in robot["fields"]}["mail_trigger"] == "bool"
    assert v["meta"]["source"] == "file"


def test_save_overrides_file_and_reset():
    hotel_settings.save("lucca", {"receptie": {"tot": "19:00"}, "robot": {"check_minutes": "30"}}, "fred")
    assert hotels.load_hotel("lucca")["receptie"]["tot"] == "19:00"
    assert hotel_setting("lucca", "ROBOT_CHECK_MINUTES") == "30"
    assert hotels.load_hotel_file("lucca")["receptie"]["tot"] == "18:30"  # bestand onaangeroerd
    assert hotel_settings.view("lucca")["meta"]["updated_by"] == "fred"
    hotel_settings.reset("lucca")
    assert hotels.load_hotel("lucca")["receptie"]["tot"] == "18:30"


def test_save_one_section_keeps_others_and_tracks_who():
    """Knop Bewaren per sectie: alleen die sectie verandert; wie en wanneer per sectie."""
    hotel_settings.save("lucca", {"receptie": {"tot": "19:00"}}, "fred")
    hotel_settings.save("lucca", {"robot": {"check_minutes": "30"}, "receptie": {"tot": "20:00"}}, "anna", only=["robot"])
    assert hotels.load_hotel("lucca")["receptie"]["tot"] == "19:00"  # niet in only: blijft zoals bewaard
    assert hotel_setting("lucca", "ROBOT_CHECK_MINUTES") == "30"
    meta = {s["section"]: s["meta"] for s in hotel_settings.view("lucca")["sections"]}
    assert meta["receptie"]["updated_by"] == "fred" and meta["robot"]["updated_by"] == "anna"
    assert meta["hotel"] == {}  # nooit gewijzigd: standaard uit het bestand
    # Terug naar standaard voor één sectie: de waarde uit het bestand, de andere sectie blijft
    hotel_settings.save("lucca", {"receptie": {"tot": "18:30"}}, "anna", only=["receptie"])
    assert hotels.load_hotel("lucca")["receptie"]["tot"] == "18:30"
    assert hotel_setting("lucca", "ROBOT_CHECK_MINUTES") == "30"
    assert {s["section"]: s["meta"] for s in hotel_settings.view("lucca")["sections"]}["receptie"] == {}


def test_free_sections_and_validation():
    hotel_settings.save("lucca", {"salto.rooms": {"12": "lock-a", "14": ""}}, "x")
    assert hotels.load_hotel("lucca")["salto"]["rooms"] == {"12": "lock-a"}
    with pytest.raises(ValueError):
        hotel_settings.save("lucca", {"robot": {"check_minutes": "veel"}}, "x")
    with pytest.raises(ValueError):
        hotel_settings.save("lucca", {"kleuren": {"accent": "blauw"}}, "x")
    with pytest.raises(ValueError):
        hotel_settings.save("lucca", {"onbekend": {"a": 1}}, "x")


def test_city_tax_from_hotel_settings():
    from hotel_checkin.core import workflow

    hotel_settings.save("lucca", {"workflow_parameters": {"city_tax_amount": "4.5", "city_tax_unit": "person_stay"}}, "x")
    assert workflow.config("lucca")["parameters"]["city_tax_amount"] == 4.5
    with pytest.raises(ValueError):
        hotel_settings.save("lucca", {"workflow_parameters": {"city_tax_unit": "per_kamer"}}, "x")


def test_list_time_is_a_robot_time():
    """Het uur van de lijsten: keuze uit de vaste uren van de robot ([robot] check_minutes)."""
    import pytest

    from hotel_checkin.core import hotel_settings as hs
    from hotel_checkin.guests import repository as repo

    repo.use_memory_store()
    with pytest.raises(ValueError):
        hs.validate("lucca", {"ontbijtlijst": {"uur": "17:45"}})
    assert hs.validate("lucca", {"ontbijtlijst": {"uur": "18:00"}}) == {"ontbijtlijst": {"uur": "18:00"}}


def test_room_exceptions_one_section_same_fields_add_and_remove():
    """Uitzonderingen per kamer: één lijst, dezelfde velden voor elke kamer, zelf kamers toevoegen en weghalen."""
    v = hotel_settings.view("lucca")
    names = [s["section"] for s in v["sections"]]
    assert not any(n.startswith("kamers.") and n != hotels.ROOM_EXCEPTIONS for n in names)
    rooms = next(s for s in v["sections"] if s["section"] == hotels.ROOM_EXCEPTIONS)
    keys = [f["key"] for f in rooms["template"]]
    assert {"verdieping", "lijst", "twin", "naam_nl", "kort_de", "toegang_fr"} <= set(keys)
    assert [x["room"] for x in rooms["items"]] == ["2", "20", "16"]
    # Kamer 16 krijgt een eigen naam, kamer 20 valt weg
    items = {x["room"]: dict(x["values"]) for x in rooms["items"] if x["room"] != "20"}
    items["16"] |= {"naam_nl": "twin kamer", "lijst": "", "verdieping": ""}
    hotel_settings.save("lucca", {hotels.ROOM_EXCEPTIONS: items}, "fred", only=[hotels.ROOM_EXCEPTIONS])
    cfg = hotels.load_hotel("lucca")["kamers"]
    assert "20" not in cfg and cfg["16"] == {"twin": True, "naam_nl": "twin kamer"} and cfg["2"]["naam_nl"] == "historische suite"
    assert cfg["lijst_volgorde"][0] == "20"  # gewone instellingen van [kamers] blijven
    with pytest.raises(ValueError):
        hotel_settings.save("lucca", {hotels.ROOM_EXCEPTIONS: {"1 2": {}}}, "fred", only=[hotels.ROOM_EXCEPTIONS])
    # Terug naar het bestand
    file_items = {x["room"]: x["values"] for x in rooms["default_items"]}
    hotel_settings.save("lucca", {hotels.ROOM_EXCEPTIONS: file_items}, "fred", only=[hotels.ROOM_EXCEPTIONS])
    assert "20" in hotels.load_hotel("lucca")["kamers"]
    assert hotels.ROOM_EXCEPTIONS not in ((repo.get_config_doc("lucca", hotels.SETTINGS_DOC) or {}).get("value") or {})
