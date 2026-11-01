"""Sessiecookies van Lighthouse tussen robotruns: in de aparte sessiekluis, alleen de cookies."""

import json

import pytest

from hotel_checkin import robot
from hotel_checkin.core import session_vault
from hotel_checkin.guests import repository as repo


@pytest.fixture
def vault(monkeypatch, tmp_path):
    repo.use_memory_store()
    store: dict[str, str] = {}
    monkeypatch.setenv("LIGHTHOUSE_STATE_DIR", str(tmp_path))
    monkeypatch.setattr(session_vault, "available", lambda: True)
    monkeypatch.setattr(session_vault, "get", lambda name: store.get(name))
    monkeypatch.setattr(session_vault, "put", lambda name, value: store.__setitem__(name, value) or True)
    return store


def test_session_saved_and_restored(vault, tmp_path):
    repo.set_state("lucca", robot.SESSION_KEY, "oud")  # vroegere kopie in de tabel
    state = tmp_path / "lighthouse-lucca.json"
    state.write_text(json.dumps({"cookies": [{"name": "s", "value": "1"}], "origins": [{"origin": "x"}]}))
    robot._store_session("lucca")
    assert json.loads(vault["lucca-lighthouse-session"]) == {"cookies": [{"name": "s", "value": "1"}], "origins": []}
    assert repo.get_state("lucca", robot.SESSION_KEY) is None  # niet meer in de tabel
    state.unlink()
    robot._restore_session("lucca")  # nieuwe container: terug uit de kluis
    assert json.loads(state.read_text())["cookies"][0]["value"] == "1"


def test_without_vault_nothing_happens(monkeypatch, tmp_path):
    monkeypatch.setenv("LIGHTHOUSE_STATE_DIR", str(tmp_path))
    monkeypatch.delenv("SESSION_VAULT_URL", raising=False)
    robot._restore_session("lucca")
    robot._store_session("lucca")
    assert not (tmp_path / "lighthouse-lucca.json").exists()
