# Ontwerpbriefing: gast-app Hotel Lucca

Briefing voor het visuele ontwerp van de gast-app (Claude Design). De gast-app vervangt het huidige
check-in-formulier: één pagina per reservatie waar de gast alles over zijn verblijf ziet en doet.

Huidig formulier (voorbeeldreservatie, niets wordt bewaard): https://checkin.hotellucca.be/?r=voorbeeld-lucca
In TST: https://checkin-tst.hotellucca.be/?r=voorbeeld-lucca

## Doel

- De gast heeft minder nood aan de receptie (die is alleen open van 14:00 tot 18:30).
- Eén link per reservatie, in elke mail en WhatsApp dezelfde knop "Bekijk je verblijf".
- In één oogopslag: wat moet ik nog doen (gegevens, betalen), wanneer krijg ik mijn code, hoe kom ik binnen.

## Gebruikers en context

- Hotelgasten, meestal op hun gsm, vaak onderweg of aan de deur, soms 's nachts en met weinig bereik.
- Vier talen: Nederlands, Frans, Engels, Duits. Taalkeuze bovenaan, zoals nu.
- Alle leeftijden: grote tekst, duidelijke knoppen, weinig tekst per scherm.
- Mobiel eerst (360 tot 430 px breed). Op een computer gewoon gecentreerd, maximaal ongeveer 600 px breed.

## Huisstijl

| Element | Waarde |
|---|---|
| Accent (grijsblauw van het logo) | `#B4BCCC` |
| Accent donker (knoppen, titels) | `#5C6478` |
| Tekst | `#2B2F38` |
| Achtergrond | `#F4F5F8` |
| Fout | `#A33A3A` |
| Logo | https://hotellucca.be/wp-content/uploads/2025/06/Logo-website-hotel-lucca.png |
| Lettertype nu | Helvetica Neue / Helvetica / Arial |

- Sfeer: rustig, klassiek, verzorgd (historisch boetiekhotel in het centrum van Brugge), geen schreeuwerige kleuren.
- De mails gebruiken dezelfde stijl: grijsblauwe band met logo bovenaan, witte kaart, kleine titels in hoofdletters.
- Kleuren komen per hotel uit de instellingen (de software is voor meerdere hotels). Het ontwerp moet dus werken
  met vier kleurvariabelen en een logo, niet met kleuren die alleen bij Lucca passen.
- Status mag met kleur, maar nooit alleen met kleur (ook een woord of icoon): groen voor klaar of open,
  donkergrijs voor nog niet beschikbaar, rood alleen voor fouten.

## Structuur van de pagina

Bovenaan altijd: logo, taalkeuze, naam van de gast, data van het verblijf en kamer(s).
Daaronder kaarten. Welke kaarten zichtbaar zijn en in welke staat, hangt af van de fase.

### Kaarten

1. **Jouw toegang**: tegels per deur (voordeur, kamer 16, of een kamer met eigen ingang). Per tegel de pincode
   met het pijltje (↵ na de code) en een ontgrendelknop.
2. **Te doen**: wat de gast nog moet doen, met een duidelijke status (gegevens invullen, betalen). Is alles gedaan:
   een korte bevestiging ("Alles in orde").
3. **Jouw gegevens**: het huidige formulier (e-mail, gsm met landkeuze, reserve-e-mail en reserve-gsm,
   vraag "moeilijk trappen lopen", geen reclame ontvangen). Ingevuld = dichtgeklapt met "Wijzigen".
4. **Betalen**: openstaand bedrag (bv. toeristenbelasting), knop "Betalen", en de staten
   "betaling wordt verwerkt" en "betaald".
5. **Je verblijf**: reservatiegegevens (alleen lezen), check-in vanaf, check-out tot, ontbijturen.
6. **Praktisch**: adres met kaartlink, wifi (per kamer via QR-code op de kamer, of één gedeelde code),
   receptie-uren, contact (WhatsApp en bellen).
7. **Na vertrek**: bedankt, reviewknop (Google), betaalknop als er nog iets openstaat.

### Fasen

| Fase | Wanneer | Wat de gast ziet |
|---|---|---|
| A. Na boeking | tot het code-moment | Te doen bovenaan. Jouw toegang als grijze tegels met "Je code verschijnt hier op wo 19 nov". |
| B. Code klaar | ongeveer 2 dagen voor aankomst, als de kamer betaald is | Pincodes zichtbaar. Ontgrendelknoppen grijs: "Werkt vanaf vr 21 nov 14:00". |
| B'. Niet betaald | code-moment, kamer nog niet betaald | Op de plaats van de code: "Betaal om je code te ontvangen", met de betaalknop. |
| C. Tijdens verblijf | van aankomst (14:00) tot vertrek | Jouw toegang bovenaan, grote ontgrendelknoppen, code eronder. Praktisch en contact vlot bereikbaar. |
| D. Na vertrek | na de check-out | Bedankt, review, eventueel betalen. Geen code en geen ontgrendelknop meer. |
| E. Geannuleerd of verlopen | | Korte melding met de contactgegevens van het hotel. |

## Ontgrendelen (belangrijkste onderdeel)

- Per deur een eigen knop: eerst de voordeur, dan de kamer.
- Schuiven om te openen (slide to unlock), niet tikken: zo gaat er niets per ongeluk open.
- Staten die ontworpen moeten worden:
  1. nog niet beschikbaar (voor aankomst): grijs, met datum en uur vanaf wanneer het werkt
  2. klaar: uitnodigend, duidelijk welke deur
  3. bezig: na het schuiven, een paar seconden wachten
  4. open: groen, "Deur is open", na enkele seconden terug naar klaar
  5. mislukt: "Lukt niet, gebruik je code 2242 ↵", de code groot
  6. geen netwerk: de code blijft zichtbaar, de knop zegt dat er geen verbinding is
- De pincode staat altijd in de buurt van de knop: die werkt altijd, ook als de app of het netwerk faalt.
- Na de code moet de gast op de pijltoets van het slot drukken. Dat moet visueel duidelijk zijn (↵ na de code,
  eventueel een kleine tekening van het klavier).
- Kamers met een eigen ingang (Lucca: kamer 2, historische suite, ingang in de Kuipersstraat; kamer 20,
  appartement rechts naast het hotel) krijgen een korte uitleg onder de tegel en geen voordeur.

## Voorbeeldinhoud

- Gast: Anna Peeters, 2 personen
- Aankomst vr 21 nov 2026 (vanaf 14:00), vertrek zo 23 nov 2026 (tot 11:00)
- Kamer 16, Superior Double Room, 1e verdieping
- Pincode 2242 ↵ (voordeur en kamer, één code per kamer)
- Open bedrag: € 16,80 toeristenbelasting (2 personen, 2 nachten, € 4,20 per persoon per nacht)
- Ontbijt 8:30 tot 10:30, receptie 14:00 tot 18:30
- Hotel Lucca, Naaldenstraat 30, 8000 Brugge, +32 478 08 30 49, info@hotellucca.be
- Variant met twee kamers (kamer 16 en kamer 21, elk een eigen code)

## Teksten

- Kort en duidelijk, zonder marketingtaal.
- Geen namen van personeel, wel algemene termen (de receptie, het hotel).
- Datums voluit en in de taal van de gast (vr 21 nov, ven. 21 nov., Fri 21 Nov, Fr. 21. Nov.).

## Gevraagd ontwerp

Mobiele schermen voor:
1. Fase A, gegevens nog niet ingevuld en een bedrag open
2. Fase A, alles in orde
3. Fase B, code zichtbaar, ontgrendelen nog niet actief
4. Fase B', niet betaald
5. Fase C, tijdens het verblijf (de belangrijkste)
6. De zes staten van de ontgrendelknop
7. Jouw gegevens, open (formulier) en dichtgeklapt
8. Fase D, na vertrek
9. Variant met twee kamers

Daarnaast een voorbeeld van een vereenvoudigde mail: logo, één korte alinea, één knop "Bekijk je verblijf".
Alleen in de code-mail staat de pincode ook in de mail zelf (vangnet als de app niet bereikbaar is).

## Technische randvoorwaarden

- Eén statische pagina (HTML, CSS, JavaScript zonder framework), gegevens via een API. Het ontwerp moet in gewone
  HTML en CSS te bouwen zijn.
- Werkt ook zonder netwerk voor wat al geladen is (de code moet aan de deur zichtbaar blijven).
- Toegankelijk: voldoende contrast, knoppen minstens 44 px hoog, werkt met grote systeemletters.
