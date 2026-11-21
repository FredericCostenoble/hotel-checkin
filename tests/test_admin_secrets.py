from types import SimpleNamespace

from hotel_checkin.admin import secrets


class FakeVault:
    def __init__(self):
        self.values = {"twilio-auth-token": "a", "lucca-lighthouse-password": "b", "other-salto-key": "c"}
        self.saved = {}

    def list_properties_of_secrets(self):
        return [SimpleNamespace(name=n, enabled=True, updated_on=None, tags={}) for n in self.values]

    def get_secret(self, name):
        return SimpleNamespace(value=self.values[name])

    def set_secret(self, name, value, tags=None):
        self.saved[name] = value


def test_only_shared_and_own_hotel(monkeypatch):
    vault = FakeVault()
    monkeypatch.setattr(secrets, "_vault", lambda: vault)
    monkeypatch.setattr(secrets, "list_hotels", lambda: ["lucca", "other"])
    names = [s["name"] for s in secrets.list_secrets("lucca")]
    assert names == ["lucca-lighthouse-password", "twilio-auth-token"]
    assert secrets.reveal("lucca", "other-salto-key") is None
    assert secrets.reveal("lucca", "twilio-auth-token") == "a"


def test_save_only_existing_and_not_empty(monkeypatch):
    vault = FakeVault()
    monkeypatch.setattr(secrets, "_vault", lambda: vault)
    monkeypatch.setattr(secrets, "list_hotels", lambda: ["lucca", "other"])
    assert secrets.save("lucca", "twilio-auth-token", " new ", "f@x") and vault.saved["twilio-auth-token"] == "new"
    assert not secrets.save("lucca", "twilio-auth-token", "  ", "f@x")
    assert not secrets.save("lucca", "brand-new", "x", "f@x")
    assert not secrets.save("lucca", "other-salto-key", "x", "f@x")


def test_no_access_without_user_or_vault(monkeypatch):
    monkeypatch.delenv("KEY_VAULT_ID", raising=False)
    assert secrets.access("") == ""
    assert secrets.access("oid") == ""
