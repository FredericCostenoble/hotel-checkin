"""Bouwblok 7: telefooncentrale voor nachtelijke oproepen (Twilio Voice).

Het hotelnummer wordt 's nachts doorgeschakeld naar het Twilio-nummer. Keuzemenu:
  1 = check-in info, gestuurd per WhatsApp of SMS naar het nummer dat belt
  2 = code opnieuw sturen, ALLEEN naar het gsm-nummer uit de reservatie
      (nummerweergave kan vervalst worden, dus nooit naar het bellende nummer)
  9 = noodgeval, doorschakelen naar de nachtverantwoordelijke

De functies geven TwiML (XML) terug die Twilio uitvoert.
"""

from __future__ import annotations


def handle_incoming_call(caller: str, language: str = "nl") -> str:
    """Begroeting en keuzemenu."""
    raise NotImplementedError("Bouwblok telefoon (menu): nog te implementeren")


def handle_menu_choice(caller: str, digits: str, language: str = "nl") -> str:
    """Verwerk de gekozen toets."""
    raise NotImplementedError("Bouwblok telefoon (keuze): nog te implementeren")
