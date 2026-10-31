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
