"""Tests voor het bouwblok sjablonen en vertaling."""

import re
import tomllib

import pytest

from hotel_checkin.messaging.templates import (
    EMAIL_MESSAGES,
    LANGUAGES,
    TEXTS_DIR,
    render,
    sample_data,
)

ALL_MESSAGES = (*EMAIL_MESSAGES, "at_the_door")


def _structure(lang: str):
    with open(TEXTS_DIR / f"{lang}.toml", "rb") as f:
        texts = tomllib.load(f)
    return {k: [b["type"] for b in v.get("blokken", [])] for k, v in texts.items()}


@pytest.mark.parametrize("lang", LANGUAGES)
def test_all_languages_have_same_structure(lang):
    assert _structure(lang) == _structure("nl")


@pytest.mark.parametrize("lang", LANGUAGES)
@pytest.mark.parametrize("message", ALL_MESSAGES)
def test_no_missing_fields_with_full_data(lang, message):
    r = render("lucca", message, lang, sample_data(lang))
    for part in (r.subject, r.html, r.text, r.sms):
        if part is not None:
            assert not re.search(r"\{[a-z_]+\}", part), part


def test_missing_field_stays_visible():
    r = render("lucca", "access_code", "nl", {"voornaam": "Anna"})
    assert "{pincode}" in r.html


def test_unknown_language_falls_back_to_english():
    r = render("lucca", "confirmation", "es", sample_data("en"))
    assert r.subject.startswith("Your stay")


def test_html_escapes_guest_data():
    data = sample_data("nl") | {"voornaam": "<script>"}
    assert "<script>" not in render("lucca", "confirmation", "nl", data).html


def test_checkin_link_from_config():
    r = render("lucca", "confirmation", "nl", sample_data("nl") | {"token": "abc"})
    assert "?r=abc" in r.html


def test_checkin_link_override_for_tst(monkeypatch):
    monkeypatch.setenv("CHECKIN_FORM_URL", "https://test.example/?r={token}")
    r = render("lucca", "confirmation", "nl", sample_data("nl") | {"token": "abc"})
    assert "https://test.example/?r=abc" in r.html
