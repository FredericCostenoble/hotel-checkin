"""Workflow per hotel: flows, stappen, voorwaarden, wijzigen en terugzetten."""

from datetime import date, datetime

import pytest

from hotel_checkin.core import workflow
from hotel_checkin.core.models import Guest, Reservation, ReservationStatus
from hotel_checkin.guests import repository as repo


@pytest.fixture(autouse=True)
def memory():
    repo.use_memory_store()


def _r(**kw):
    return Reservation("lucca", "x", Guest("A", "B", "a@b.c"), date(2099, 1, 10), date(2099, 1, 12), **kw)


def test_lucca_workflow():
    steps = {s.step: s for s in workflow.steps("lucca", "booking")}
    assert set(steps) == {"confirmation", "reminder", "access_code", "thank_you", "payment_request"}
    assert steps["payment_request"].only_if == ["not_cancelled", "not_paid"]
    assert steps["reminder"].due_date(_r()) == date(2099, 1, 3)
    assert steps["access_code"].days == 2 and steps["access_code"].pay == "city_tax"
    assert workflow.detail_window_days("lucca") == 8
    assert workflow.needs_details_after_booking("lucca")


def test_conditions():
    reminder = next(s for s in workflow.steps("lucca", "website_paid") if s.step == "reminder")
    assert reminder.conditions_met(_r())
    assert not reminder.conditions_met(_r(status=ReservationStatus.CANCELLED))
    assert not reminder.conditions_met(_r(checkin_completed_at=datetime(2099, 1, 1)))
    code = next(s for s in workflow.steps("lucca", "website_paid") if s.step == "access_code")
    assert not code.conditions_met(_r()) and code.conditions_met(_r(paid=True))


def test_flow_for():
    assert workflow.flow_for("lucca", _r(source="Booking.com")) == "booking"
    assert workflow.flow_for("lucca", _r(source="Expedia")) == "expedia"
    assert workflow.flow_for("lucca", _r(source="Booking Engine", paid=True)) == "website_paid"
    assert workflow.flow_for("lucca", _r(source="Booking Engine")) == "website_unpaid"


def test_city_tax_per_person_per_night():
    assert workflow.city_tax("lucca", _r(guest_count=2)) == 20.0  # 5 x 2 personen x 2 nachten


def test_save_and_reset():
    cfg = workflow.config("lucca")
    assert cfg["meta"]["source"] == "file"
    cfg["flows"]["booking"]["steps"][2]["days"] = 3
    cfg["parameters"]["city_tax_amount"] = 4.2
    saved = workflow.save_config("lucca", cfg, "frederic@hotellucca.be")
    assert saved["meta"]["source"] == "monitor" and saved["meta"]["updated_by"] == "frederic@hotellucca.be"
    assert next(s for s in workflow.steps("lucca", "booking") if s.step == "access_code").days == 3
    assert workflow.reset_config("lucca")["parameters"]["city_tax_amount"] == 5.0


def test_invalid_config_explained():
    cfg = workflow.config("lucca")
    cfg["flows"]["expedia"]["steps"][0]["when"] = "sometime"
    cfg["flows"]["expedia"]["steps"][1]["only_if"] = ["vip"]
    cfg["parameters"]["city_tax_amount"] = "veel"
    with pytest.raises(ValueError) as e:
        workflow.save_config("lucca", cfg, "x")
    assert "sometime" in str(e.value) and "vip" in str(e.value) and "bedrag" in str(e.value)


def test_disabled_step_not_used():
    cfg = workflow.config("lucca")
    cfg["flows"]["booking"]["steps"][1]["enabled"] = False
    workflow.save_config("lucca", cfg, "x")
    assert "reminder" not in {s.step for s in workflow.steps("lucca", "booking")}


def test_monitor_save_error_and_user():
    from hotel_checkin.admin import service

    view = service.workflow_view("lucca")
    assert view["choices"]["flows"] == list(workflow.FLOWS)
    bad = {"parameters": view["parameters"], "flows": {**view["flows"], "expedia": None}}
    ok, data = service.workflow_save("lucca", bad, "x")
    assert not ok and "expedia" in data["error"]
    ok, data = service.workflow_save("lucca", {"parameters": view["parameters"], "flows": view["flows"]}, "frederic")
    assert ok and data["meta"]["updated_by"] == "frederic"
