"""Controleert dat alle bouwblokken importeerbaar zijn."""

import importlib

import pytest

MODULES = [
    "hotel_checkin.core.models",
    "hotel_checkin.core.config",
    "hotel_checkin.messaging.email",
    "hotel_checkin.messaging.sms",
    "hotel_checkin.messaging.whatsapp",
    "hotel_checkin.pms.lighthouse",
    "hotel_checkin.guests.repository",
    "hotel_checkin.access.salto",
    "hotel_checkin.voice.ivr",
    "hotel_checkin.processes.new_reservation",
    "hotel_checkin.processes.send_access_code",
]


@pytest.mark.parametrize("name", MODULES)
def test_import(name):
    importlib.import_module(name)
