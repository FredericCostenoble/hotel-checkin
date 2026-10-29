"""Workflow per hotel uit de configuratie."""

from datetime import date, datetime

import pytest

from hotel_checkin.core import workflow
from hotel_checkin.core.models import Guest, Reservation, ReservationStatus


def _r(**kw):
    return Reservation("lucca", "x", Guest("A", "B", "a@b.c"), date(2099, 1, 10), date(2099, 1, 12), **kw)


def test_lucca_workflow():
    steps = {s.step: s for s in workflow.steps("lucca")}
    assert set(steps) == {"confirmation", "reminder", "access_code"}
    assert steps["reminder"].due_date(_r()) == date(2099, 1, 3)
    assert workflow.detail_window_days("lucca") == 8
    assert workflow.needs_details_after_booking("lucca")


def test_conditions():
    reminder = next(s for s in workflow.steps("lucca") if s.step == "reminder")
    assert reminder.conditions_met(_r())
    assert not reminder.conditions_met(_r(status=ReservationStatus.CANCELLED))
    assert not reminder.conditions_met(_r(checkin_completed_at=datetime(2099, 1, 1)))
    code = next(s for s in workflow.steps("lucca") if s.step == "access_code")
    assert not code.conditions_met(_r()) and code.conditions_met(_r(paid=True))


def test_invalid_workflow(monkeypatch):
    monkeypatch.setattr(workflow, "load_hotel", lambda h: {"workflow": [{"step": "x", "when": "sometime"}]})
    with pytest.raises(ValueError, match="when"):
        workflow.steps("lucca")
    monkeypatch.setattr(workflow, "load_hotel", lambda h: {"workflow": [{"step": "x", "when": "at_start", "only_if": ["vip"]}]})
    with pytest.raises(ValueError, match="vip"):
        workflow.steps("lucca")
