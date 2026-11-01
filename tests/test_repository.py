"""Tests voor bouwblok 5 (opslag) met een eenvoudige tabel in het geheugen, zonder Azure."""

from datetime import UTC, date

import pytest

from hotel_checkin.core.models import Channel, Guest, Reservation, SendResult
from hotel_checkin.guests import repository as repo

FakeTable = repo.MemoryTable


@pytest.fixture(autouse=True)
def fake_tables(monkeypatch):
    tables: dict[str, FakeTable] = {}
    monkeypatch.setattr(repo, "_client_factory", lambda name: tables.setdefault(name, FakeTable()))
    return tables


def _reservation(rid="abc-123"):
    return Reservation(
        hotel_id="lucca",
        reservation_id=rid,
        guest=Guest("Anna", "Peeters", "Anna@Example.com", "+32470000000", "nl"),
        arrival=date(2026, 11, 14),
        departure=date(2026, 11, 16),
        rooms=["14"],
        source="Booking.com",
        room_type="Superior Double",
    )


def test_save_and_get_keeps_token():
    saved = repo.save_reservation(_reservation())
    assert saved.token
    again = repo.save_reservation(_reservation())  # opnieuw binnengekomen, zonder token
    assert again.token == saved.token
    r = repo.get_reservation("lucca", "abc-123")
    assert r.guest.email == "anna@example.com" and r.rooms == ["14"] and r.paid is None


def test_get_by_token_and_phone():
    saved = repo.save_reservation(_reservation())
    assert repo.get_by_token(saved.token).reservation_id == "abc-123"
    assert repo.get_by_token("onbestaand") is None
    assert [r.reservation_id for r in repo.find_by_phone("lucca", "+32470000000")] == ["abc-123"]


def test_mark_checkin_completed():
    repo.save_reservation(_reservation())
    r = repo.mark_checkin_completed("lucca", "abc-123", "nieuw@example.com", None, "fr")
    assert r.checkin_completed_at is not None
    assert repo.get_reservation("lucca", "abc-123").guest.language == "fr"


def test_message_log_and_duplicates():
    repo.log_message("lucca", "abc-123", "confirmation", SendResult(Channel.EMAIL, "a@b.c", ok=False, error="x"))
    assert not repo.was_sent("lucca", "abc-123", "confirmation")
    repo.log_message("lucca", "abc-123", "confirmation", SendResult(Channel.EMAIL, "a@b.c", ok=True))
    assert repo.was_sent("lucca", "abc-123", "confirmation")
    assert repo.was_sent("lucca", "abc-123", "confirmation", "email")
    assert not repo.was_sent("lucca", "abc-123", "confirmation", "sms")
    assert len(repo.messages_for("lucca", "abc-123")) == 2


def test_opt_out_is_case_insensitive():
    repo.add_opt_out("lucca", " Anna@Example.com ", "checkin_form")
    assert repo.is_opted_out("lucca", "anna@example.com")
    assert not repo.is_opted_out("lucca", "ander@example.com")


@pytest.mark.parametrize(
    "given,stored",
    [
        ("nl", "nl"), ("NL-nl", "nl"), ("nl_BE", "nl"),
        ("FR", "fr"), ("fr-CA", "fr"), ("FR-ch", "fr"), ("Fr", "fr"), ("fr-BE", "fr"),
        ("de-DE", "de"), ("de-AT", "de"), ("DE-ch", "de"),
        ("en", "en"), ("EN-us", "en"), ("it", "en"), ("es-ES", "en"), ("", "en"), (None, "en"),
    ],
)
def test_language_rule(given, stored):
    r = _reservation()
    r.guest.language = given
    repo.save_reservation(r)
    assert repo.get_reservation("lucca", "abc-123").guest.language == stored


def test_ids_with_special_characters():
    repo.save_reservation(_reservation("a/b#c?d"))
    assert repo.get_reservation("lucca", "a/b#c?d") is not None


def test_hotels_are_separated():
    a = _reservation("R-1")
    b = _reservation("R-1")
    b.hotel_id = "ander-hotel"
    b.guest.first_name = "Bert"
    repo.save_reservation(a)
    repo.save_reservation(b)
    assert repo.get_reservation("lucca", "R-1").guest.first_name == "Anna"
    assert repo.get_reservation("ander-hotel", "R-1").guest.first_name == "Bert"
    assert [r.hotel_id for r in repo.find_by_phone("lucca", "+32470000000")] == ["lucca"]
    repo.add_opt_out("lucca", "anna@example.com", "checkin_form")
    assert repo.is_opted_out("lucca", "anna@example.com")
    assert not repo.is_opted_out("ander-hotel", "anna@example.com")
    repo.log_message("lucca", "R-1", "confirmation", SendResult(Channel.EMAIL, "a@b.c", ok=True))
    assert repo.was_sent("lucca", "R-1", "confirmation")
    assert not repo.was_sent("ander-hotel", "R-1", "confirmation")


def test_prune_robot_runs():
    from datetime import datetime, timedelta

    now = datetime.now(UTC)
    repo.log_robot_run("lucca", "t", now - timedelta(days=40), True)
    repo.log_robot_run("lucca", "t", now - timedelta(days=1), True)
    assert repo.prune_robot_runs("lucca", 30) == 1
    assert len(repo.robot_runs("lucca")) == 1


def test_updated_at_only_when_something_changed(monkeypatch):
    from datetime import date, datetime

    from hotel_checkin.core.models import Guest, Reservation
    from hotel_checkin.guests import repository as repo

    repo.use_memory_store()
    times = iter([datetime(2026, 10, 30, 9, m, tzinfo=UTC) for m in range(60)])
    monkeypatch.setattr(repo, "_now", lambda: next(times))
    r = Reservation("lucca", "u9", Guest("Jan", "Voorbeeld"), date(2099, 1, 1), date(2099, 1, 2))
    first = repo.save_reservation(r)
    added, updated = first.created_at, first.updated_at
    repo.save_reservation(repo.get_reservation("lucca", "u9"))  # niets veranderd
    same = repo.get_reservation("lucca", "u9")
    assert (same.created_at, same.updated_at) == (added, updated)
    same.guest.email = "jan@example.com"
    repo.save_reservation(same)
    changed = repo.get_reservation("lucca", "u9")
    assert changed.created_at == added and changed.updated_at > updated


def test_delete_robot_run():
    from datetime import datetime

    from hotel_checkin.guests import repository as repo

    repo.use_memory_store()
    repo.log_robot_run("lucca", "nieuwe_reservaties", datetime.now(UTC), True)
    run_id = repo.robot_runs("lucca")[0]["RowKey"]
    assert not repo.delete_robot_run("lucca", "x' or 1 eq 1")
    assert repo.delete_robot_run("lucca", run_id) and repo.robot_runs("lucca") == []


def test_delete_robot_runs_all_or_per_task():
    from datetime import datetime

    from hotel_checkin.guests import repository as repo

    repo.use_memory_store()
    now = datetime.now(UTC)
    for task in ("nieuwe_reservaties", "nieuwe_reservaties", "meldingen"):
        repo.log_robot_run("lucca", task, now, True)
    assert repo.delete_robot_runs("lucca", "meldingen") == 1
    assert repo.delete_robot_runs("lucca") == 2 and repo.robot_runs("lucca") == []


def test_form_data_not_overwritten_by_stale_copy():
    from datetime import date, timedelta

    from hotel_checkin.core.models import Guest, Reservation
    from hotel_checkin.guests import repository as repo

    repo.use_memory_store()
    arr = date.today() + timedelta(days=8)
    repo.save_reservation(Reservation("lucca", "race1", Guest("Caner", "Adnan", email="ac.1@guest.booking.com"), arr,
                                      arr + timedelta(days=3)))
    stale = repo.get_reservation("lucca", "race1")  # de robot leest...
    repo.mark_checkin_completed("lucca", "race1", "caner@elbonet.be", None, "en")  # ...de gast vult in...
    stale.rooms = ["12"]
    repo.save_reservation(stale)  # ...de robot bewaart zijn oude kopie
    r = repo.get_reservation("lucca", "race1")
    assert r.guest.email == "caner@elbonet.be" and r.checkin_completed_at and r.rooms == ["12"]
    assert r.guest.relay_email == "ac.1@guest.booking.com"


def test_partial_save_keeps_fields_of_other_writers():
    """Een oude kopie (bv. robot) bewaart alleen zijn eigen velden: de pincode van Salto blijft."""
    repo.save_reservation(_reservation("p1"))
    stale = repo.get_reservation("lucca", "p1")
    fresh = repo.get_reservation("lucca", "p1")
    fresh.access_pin, fresh.salto_user_id = "654321", "user-1"
    repo.save_reservation(fresh, fields=repo.SALTO_FIELDS)
    stale.rooms = ["21"]
    repo.save_reservation(stale, fields=repo.DETAIL_FIELDS)
    r = repo.get_reservation("lucca", "p1")
    assert r.rooms == ["21"] and r.access_pin == "654321" and r.salto_user_id == "user-1"


def test_save_retries_on_etag_conflict(monkeypatch):
    """Verandert de rij tussen lezen en schrijven, dan opnieuw lezen en samenvoegen."""
    repo.save_reservation(_reservation("e1"))
    table = repo._table(repo.T_RESERVATIONS)
    real_update, calls = table.update_entity, []

    def racing_update(entity, **kw):
        if not calls:  # iemand anders schrijft net de pincode
            calls.append(1)
            other = dict(table.get_entity(entity["PartitionKey"], entity["RowKey"]))
            other["access_pin"] = "111111"
            table.upsert_entity(other)
        return real_update(entity, **kw)

    monkeypatch.setattr(table, "update_entity", racing_update)
    r = repo.get_reservation("lucca", "e1")
    r.rooms = ["3"]
    repo.save_reservation(r, fields=repo.DETAIL_FIELDS)
    after = repo.get_reservation("lucca", "e1")
    assert after.rooms == ["3"] and after.access_pin == "111111"


def test_token_index_and_cleanup():
    r = repo.save_reservation(_reservation("t1"))
    assert repo.get_by_token(r.token).reservation_id == "t1"
    assert repo.get_by_token("bestaat-niet") is None
    repo.save_form_submission("lucca", "t1", {"email": "a@example.com"})
    repo.log_message("lucca", "t1", "confirmation", SendResult(Channel.EMAIL, "a@example.com", True))
    repo.delete_reservation("lucca", "t1")
    assert repo.get_by_token(r.token) is None
    assert repo.form_submissions("lucca", "t1") == [] and repo.messages_for("lucca", "t1") == []


def test_messages_for_hotel_does_not_mix_hotels():
    repo.log_message("lucca", "a", "confirmation", SendResult(Channel.EMAIL, "x@example.com", True))
    repo.log_message("lucca2", "b", "confirmation", SendResult(Channel.EMAIL, "y@example.com", True))
    assert list(repo.messages_for_hotel("lucca")) == ["a"]


def test_robot_runs_newest_first_with_task_filter():
    from datetime import datetime, timedelta

    now = datetime.now(UTC)
    for i, task in enumerate(["a", "b", "a"]):
        repo.log_robot_run("lucca", task, now - timedelta(minutes=10 - i), True)
    runs = repo.robot_runs("lucca", task="a")
    assert [r["task"] for r in runs] == ["a", "a"] and runs[0]["started_at"] > runs[1]["started_at"]
    assert len(repo.robot_runs("lucca", limit=1)) == 1
