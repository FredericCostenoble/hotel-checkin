# Afspraken voor deze repo

- Kleine, losse bouwblokken: elk blok doet één ding en praat met één systeem.
  Processen (`src/hotel_checkin/processes/`) combineren de blokken en bevatten geen
  technische details van Lighthouse, Salto of Twilio.
- Multi-hotel: elke reservatie, elk bericht en elke instelling hoort bij een `hotel_id`.
  Nooit iets hotel-specifieks hardcoderen; het hoort in `config/hotels/<hotel_id>.toml`.
- Omgevingen TST en PRD. Buiten PRD mag geen bericht naar een echte gast (zie `core/safety.py`).
- Trigger is altijd Lighthouse (nieuwe of gewijzigde reservatie).
- Lighthouse: voorlopig browserautomatisatie (Playwright) met een aparte robotgebruiker
  en TOTP. Pagina's altijd volledig laten laden (folio/transacties laden asynchroon).
- Salto: rechtstreeks via KS Connect API. De code wordt daarna door het Lighthouse-blok
  in Lighthouse weggeschreven.
- Hosting op Azure, zo goedkoop mogelijk (klein hotel). Secrets alleen in Key Vault.
- Code wordt nooit naar het bellende nummer gestuurd, alleen naar het nummer uit de reservatie.
- Altijd eerst vragen of er gecommit en gepusht mag worden. Na akkoord doet Claude de
  commit en push zelf.
- Documentatie en commentaar in het Nederlands, code-identifiers in het Engels.
  Geen lange liggende streepjes in teksten.
