# Afspraken voor deze repo

- Kleine, losse bouwblokken: elk blok doet één ding en praat met één systeem.
  Processen (`src/hotel_checkin/processes/`) combineren de blokken en bevatten geen
  technische details van Lighthouse, Salto of Twilio.
- Trigger is altijd Lighthouse (nieuwe of gewijzigde reservatie).
- Lighthouse: voorlopig browserautomatisatie (Playwright) met een aparte robotgebruiker
  en TOTP. Pagina's altijd volledig laten laden (folio/transacties laden asynchroon).
- Salto: rechtstreeks via KS Connect API. De code wordt daarna door het Lighthouse-blok
  in Lighthouse weggeschreven.
- Hosting op Azure, zo goedkoop mogelijk (klein hotel). Secrets alleen in Key Vault.
- Code wordt nooit naar het bellende nummer gestuurd, alleen naar het nummer uit de reservatie.
- Werk via een branch en pull request, niet rechtstreeks op `main`.
- Documentatie en commentaar in het Nederlands, code-identifiers in het Engels.
  Geen lange liggende streepjes in teksten.
