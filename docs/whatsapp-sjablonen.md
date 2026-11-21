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
- Knoptekst hoogstens 20 tekens (Twilio), voettekst hoogstens 60.

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

### confirmation (meteen na de boeking)
Variabelen: {{1}} voornaam, {{2}} formulierlink vanaf het token (knop).

| Taal | Tekst | Knop |
|---|---|---|
| nl | Beste {{1}}, bedankt voor uw reservatie in Hotel Lucca. Vul voor uw aankomst uw check-in-gegevens in via de knop hieronder. Zo ontvangt u alle praktische info en uw persoonlijke pincode voor de ingang en uw kamer. | Check-in invullen |
| fr | Bonjour {{1}}, merci pour votre réservation à l'Hotel Lucca. Avant votre arrivée, complétez vos données d'enregistrement via le bouton ci-dessous. Vous recevrez ainsi toutes les informations pratiques et votre code PIN personnel pour l'entrée et votre chambre. | Compléter le check-in |
| en | Dear {{1}}, thank you for your reservation at Hotel Lucca. Before you arrive, please complete your check-in details using the button below. You will then receive all practical information and your personal PIN code for the entrance and your room. | Complete check-in |
| de | Guten Tag {{1}}, vielen Dank für Ihre Reservierung im Hotel Lucca. Bitte ergänzen Sie vor Ihrer Anreise Ihre Check-in-Daten über die Schaltfläche unten. So erhalten Sie alle praktischen Informationen und Ihren persönlichen PIN-Code für den Eingang und Ihr Zimmer. | Check-in ergänzen |

Voettekst (alle talen): `Hotel Lucca, Naaldenstraat 30, Brugge`

### reminder (een week voor aankomst, als het formulier niet ingevuld is)
Neutraal geformuleerd: de gegevens van de boekingssite staan al in het formulier, de gast kijkt ze na of vult aan.
Variabelen: {{1}} voornaam, {{2}} formulierlink vanaf het token (knop).

| Taal | Tekst | Knop |
|---|---|---|
| nl | Beste {{1}}, over een week bent u onze gast in Hotel Lucca. Kijk uw check-in-gegevens na of vul ze aan via de knop hieronder. Zo ontvangt u voor uw aankomst alle praktische info en uw persoonlijke pincode. | Gegevens nakijken |
| fr | Bonjour {{1}}, dans une semaine vous serez notre hôte à l'Hotel Lucca. Vérifiez ou complétez vos données d'enregistrement via le bouton ci-dessous. Vous recevrez ainsi avant votre arrivée toutes les informations pratiques et votre code PIN personnel. | Vérifier mes données |
| en | Dear {{1}}, in one week you will be our guest at Hotel Lucca. Please check or complete your check-in details using the button below. You will then receive all practical information and your personal PIN code before you arrive. | Check my details |
| de | Guten Tag {{1}}, in einer Woche sind Sie unser Gast im Hotel Lucca. Bitte prüfen oder ergänzen Sie Ihre Check-in-Daten über die Schaltfläche unten. So erhalten Sie vor Ihrer Anreise alle praktischen Informationen und Ihren persönlichen PIN-Code. | Daten prüfen |

### access_code (één bericht per kamer)
Variabelen: {{1}} kamer (kort, bv. "16 verdiep 1" of "2 (eigen ingang Kuipersstraat)"), {{2}} pincode,
{{3}} formulierlink vanaf het token (knop: daar staat ook de betaalknop als er nog iets openstaat).

| Taal | Tekst | Knop |
|---|---|---|
| nl | Uw verblijf @ Hotel Lucca, kamer {{1}}, code: {{2}} ↵<br>Toets de code en daarna de pijltoets ↵ op elk klavier. Alle info staat in uw mail. | Uw reservatie |
| fr | Votre séjour @ Hotel Lucca, chambre {{1}}, code : {{2}} ↵<br>Saisissez le code puis la touche flèche ↵ sur chaque clavier. Toutes les informations se trouvent dans votre e-mail. | Votre réservation |
| en | Your stay @ Hotel Lucca, room {{1}}, code: {{2}} ↵<br>Enter the code followed by the arrow key ↵ on each keypad. All information is in your email. | Your reservation |
| de | Ihr Aufenthalt @ Hotel Lucca, Zimmer {{1}}, Code: {{2}} ↵<br>Geben Sie den Code und danach die Pfeiltaste ↵ an jedem Tastenfeld ein. Alle Informationen finden Sie in Ihrer E-Mail. | Ihre Reservierung |

(`<br>` = nieuwe regel in het sjabloon.)

### room_change (kamerwissel na de code-mail)
Variabelen: {{1}} nieuwe kamer (kort), {{2}} pincode.

| Taal | Tekst |
|---|---|
| nl | Uw kamer in Hotel Lucca is gewijzigd: u verblijft nu in kamer {{1}}. Uw code blijft {{2}} ↵ Meer info in uw mail. |
| fr | Votre chambre à l'Hotel Lucca a changé : vous séjournez maintenant dans la chambre {{1}}. Votre code reste {{2}} ↵ Plus d'informations dans votre e-mail. |
| en | Your room at Hotel Lucca has changed: you are now staying in room {{1}}. Your code remains {{2}} ↵ More information in your email. |
| de | Ihr Zimmer im Hotel Lucca hat sich geändert: Sie wohnen jetzt in Zimmer {{1}}. Ihr Code bleibt {{2}} ↵ Weitere Informationen in Ihrer E-Mail. |

Niet als sjabloon: de bedankmail na vertrek (alleen per mail) en het automatische antwoord op een bericht van de gast
(vrije tekst mag binnen 24 uur na zijn bericht, texts/<taal>.toml `[incoming]`).

## Personeel (alleen en, zoals de lijsten zelf)

Type **Media**: de pdf als document bovenaan. Media-URL: `https://<function app>/api/lists/{{3}}` (de pdf, met
handtekening, 24 uur geldig; `processes/daily_lists.py`, `pdf_path`). In TST het adres van de TST-Function App.

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
