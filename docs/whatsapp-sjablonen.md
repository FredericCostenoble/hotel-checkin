# WhatsApp-sjablonen (Twilio Content Templates, goed te keuren door Meta)

Berichten die het hotel als eerste stuurt, moeten een goedgekeurd sjabloon gebruiken, categorie **Utility**.

## Beheer in de monitor (instellingen, WhatsApp)

De teksten worden gewijzigd en ingediend in de monitor, niet meer met de hand in de Content Template Builder
(`processes/whatsapp_templates.py`, bouwblok `messaging/content_templates.py`):

- Standaardteksten per hotel: `config/whatsapp/<hotel_id>.toml`. Wat in de monitor gewijzigd wordt, staat in de
  database (document `whatsapp_templates`), per omgeving apart.
- Indienen maakt een nieuw sjabloon bij Twilio (naam `<hotel>_<omgeving>_<bericht>_<taal>_v<n>`) en dient het in bij
  Meta. Een ingediend sjabloon kan niet meer gewijzigd worden: elke nieuwe tekst is een nieuwe versie.
- Tot Meta een nieuwe versie goedkeurt, blijft de vorige goedgekeurde versie verstuurd worden. Zonder goedgekeurde
  versie: de SID uit `[whatsapp] template_<bericht>_<taal>` in de instellingen, anders Engels, anders per sms.
- Wacht er al een versie op Meta, dan kan toch een nieuwe ingediend worden: die vervangt de wachtende (die wordt bij
  Twilio verwijderd).
- De status wordt alleen gevraagd voor versies die nog wachten: elke 15 minuten (timer oversight) en bij het openen
  van het tabblad (hoogstens een keer per minuut). Goedgekeurd of afgekeurd wordt niet meer opgevraagd.
- Het icoontje naast de naam opent de Content Template Builder in Twilio (zoeken op de naam).
- Knoptekst hoogstens 20 tekens (Twilio), voettekst hoogstens 60, titel hoogstens 60.
- Titel (vet bovenaan): Twilio-type whatsapp/card. Niet bij de lijsten: daar staat de pdf bovenaan en dat kan niet samen.

Welke gegevens in welke plaats staan: `WHATSAPP_VARIABLES` in `processes/send_messages.py` (gasten) en
`_send_phone` in `processes/daily_lists.py` (personeel).

Regels van Meta: een sjabloon begint en eindigt niet met een variabele, een variabele bevat geen nieuwe regel, en er
moet genoeg vaste tekst zijn voor het aantal variabelen. Knoptekst hoogstens 25 tekens.

## Toestemming

WhatsApp en sms gaan alleen naar gsm-nummers die de gast zelf in het check-in-formulier invulde (zin onder het
gsm-veld: met het nummer kan het hotel hem contacteren en ook via WhatsApp of sms berichten sturen). Een nummer dat
alleen van Booking.com of Expedia komt, krijgt nooit WhatsApp of sms (`Guest.phone_consent`,
`send_messages.recipients`). Daardoor gaan in de praktijk alleen de code-mail en de kamerwissel ook per WhatsApp:
de herinnering gaat alleen naar wie het formulier nog niet invulde.

## Knop naar het check-in-formulier

De knop heeft een vast begin en een variabel einde: `https://checkin.hotellucca.be/?r={{n}}`. De variabele is het
token met de taal (`abc123&lang=nl`, `templates.checkin_suffix`). Het formulier toont ook de betaalknop zodra
Lighthouse een betaallink maakte en er iets openstaat (`checkin/service.py`, `pay_info`).

TST heeft een ander formulieradres (`CHECKIN_FORM_URL`) en een andere Function App: in TST eigen sjablonen (alleen NL
volstaat), met het TST-adres als vast begin.

## Gasten

De teksten staan in `config/whatsapp/<hotel_id>.toml` en worden gewijzigd in de monitor. Plaatsen:
confirmation en reminder {{1}} voornaam, {{2}} formulierlink vanaf het token (knop); access_code {{1}} kamer,
{{2}} formulierlink vanaf het token (knop); room_change {{1}} kamer.

Geen pincode in WhatsApp, en niet de woorden pincode of code: Meta keurde zulke sjablonen op 21/11/2026 af
("categorie moet Verificatie zijn", of zonder reden). De pincode staat in de code-mail en in de app achter de knop.
De sms (terugval) bevat de pincode wel.

Niet als sjabloon: de bedankmail na vertrek (alleen per mail) en het automatische antwoord op een bericht van de gast
(vrije tekst mag binnen 24 uur na zijn bericht, texts/<taal>.toml `[incoming]`).

## Personeel (alleen en, zoals de lijsten zelf)

Type **Media**: de pdf als document bovenaan. Media-URL: `https://<function app>/api/lists/{{3}}` (de pdf, met
handtekening, 24 uur geldig; `processes/daily_lists.py`, `pdf_path`). Meta haalt bij het goedkeuren het voorbeeld op:
dat is een echte lege lijst (`sample_pdf_path`, zonder gastgegevens). In TST het adres van de TST-Function App.

| Sjabloon | Tekst |
|---|---|
| breakfast_list | Breakfast list for {{1}}: {{2}}. Open the PDF for the full list to print. |
| cleaning_list | Cleaning list for {{1}}: {{2}}. Open the PDF for the full list with the remarks. |

{{1}} de dag ("Friday 13/11/2026"), {{2}} kort wat erop staat ("12 persons in 6 rooms, 1 to check" of
"3 leave, 5 stay, 2 check in").

## Antwoorden op het nummer

In Twilio bij het nummer (sms) en de WhatsApp-afzender: "A message comes in" =
`https://<function app>/api/twilio/incoming?h=lucca` (POST). Het bericht gaat per mail naar `[twilio] doorsturen`,
de afzender krijgt één keer per 12 uur een automatisch antwoord met `[twilio] contact_whatsapp`
(`processes/incoming.py`). Het personeel krijgt geen automatisch antwoord.

## Oproepen op het nummer

"A call comes in" = `https://<function app>/api/twilio/voice?h=lucca` (POST): overdag naar `[hotel] telefoon`,
van `[doorschakelen] avond_van` tot `avond_tot` naar `[nood] nummer` (`processes/call_forward.py`).
"Primary handler fails" = de TwiML Bin "Forward to hotel" (vast naar de gsm van het hotel), als vangnet.
