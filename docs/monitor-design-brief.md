# Ontwerpbriefing: beheerapp (monitor) Hotel Lucca

Briefing om de beheerapp van de check-in-automatisatie volledig opnieuw te ontwerpen in Claude Design. Vandaag heet ze
"Check-in monitor": een technische pagina met tabbladen. Ze moet dezelfde look and feel krijgen als de gast-app
(zelfde canvas "Gast-app Hotel Lucca", zie docs/guest-app-design-brief.md) en veel gebruiksvriendelijker worden:
geen rij tabbladen meer, wel een duidelijke navigatie en een startscherm met wat vandaag aandacht vraagt.

Alle functies hieronder bestaan al en moeten in het nieuwe ontwerp een plaats krijgen. Niets mag wegvallen.

## Gebruikers

- **Uitbater en receptie** (dagelijks): wie komt vandaag en morgen, heeft iedereen zijn gegevens en code, wat staat er
  nog open, de ontbijt- en schoonmaaklijst. Meestal op een laptop aan de receptie, soms op een tablet of gsm.
- **Beheerder** (Frederic, af en toe): instellingen, workflow van de berichten, robot en fouten.
- Aanmelden gebeurt met een Microsoft-account (Entra ID); dat scherm hoort niet bij het ontwerp.
- Twee talen voor de schermen: Nederlands en Engels (keuze bovenaan, zoals nu).

## Huisstijl

Dezelfde als de gast-app: grijsblauwe band (`#B4BCCC`), donker grijsblauw voor knoppen en titels (`#5C6478`), tekst
`#2B2F38`, achtergrond `#F4F5F8`, witte kaarten met afgeronde hoeken, kleine titels in hoofdletters, badges voor
status (groen klaar, grijs nog niet, oranje let op, rood fout), lijniconen (geen emoji), Helvetica. Het logo van het
hotel linksboven. De software is voor meerdere hotels: kleuren en logo komen van het gekozen hotel.

Wel compacter dan de gast-app: dit is een werkinstrument met tabellen. Desktop eerst (1280 tot 1440 breed), maar elk
scherm moet ook op een tablet en gsm bruikbaar blijven (tabellen worden dan kaarten of scrollen in een kader).

## Altijd zichtbaar (kop of zijbalk)

- **Hotelkeuze** (meerdere hotels mogelijk).
- **Omgeving**: TST of PRD, heel duidelijk anders gekleurd. In TST een balk "Testomgeving: berichten gaan alleen naar
  de testadressen". Een knop om naar de andere omgeving te springen.
- **Hoofdschakelaars** van het hotel, als compacte statusbolletjes met naam; klik = naar de instellingen:
  - Reservaties lezen (robot), Overschrijvingen Booking.com, Ontbijt labels, Ontbijtlijst, Schoonmaaklijst,
    Deuren via de app: aan of uit.
  - Gastcommunicatie: **uit, aan of selectie** (selectie = alleen voor reservaties die je zelf aanzet, om te testen).
    Drie duidelijk verschillende toestanden.
- **Herstelbanner**: als de bewaking een probleem ziet (robot mist een run, Lighthouse veranderde), een opvallende
  balk met uitleg, de status van de automatische herstelling (zoekt, klaar om te testen, opgelost) en een knop.
- Versie (klein), taalkeuze NL/EN, afmelden.

## Voorstel voor de navigatie (vrij te herwerken)

1. **Vandaag** (nieuw startscherm)
2. **Reservaties**
3. **Gasten**
4. **Lijsten** (ontbijt en schoonmaak samen)
5. **Instellingen**: Hotel (dagelijks en technisch), Berichten (workflow), Robot

## 1. Vandaag (nieuw, uit bestaande gegevens)

Wat vandaag aandacht vraagt, zonder te zoeken:
- Aankomsten vandaag en morgen: per reservatie gast, kamer, formulier ingevuld ja/nee, betaald ja/nee, code gemaakt
  ja/nee, code-mail verstuurd, label ONTBIJT, moeilijk ter been. Wat ontbreekt in oranje.
- Vertrekken vandaag, en wie nu in huis is.
- Mislukte berichten (rood) en berichten die vandaag nog vertrekken.
- Laatste run van de robot (wanneer, gelukt of niet) en een knop "Robot nu draaien".
- Ontbijtlijst en schoonmaaklijst van vandaag/morgen: gemaakt, verstuurd, knop om te bekijken.
- Openstaande bedragen van gasten die binnenkort aankomen.

## 2. Reservaties

Lijst met zoekveld (naam, nummer, e-mail) en periode (verblijf van, tot, knop "Vanaf vandaag"), aantal resultaten.
Per reservatie (nu kolommen, mag anders):
- aankomst, vertrek, reservatienummer met link naar Lighthouse, gast (link naar het gastprofiel), "terugkerend (n×)"
- labels: formulier ingevuld of niet, moeilijk ter been (trappen), berichten aan/uit als die voor deze reservatie
  afwijkt van de schakelaar, geannuleerd (doorgestreept)
- aantal personen, kamer(s) of kamertype, tarief (NFR niet annuleerbaar / annuleerbaar en de naam van het tarief)
- kanaal (Via: Booking.com, Expedia, website), workflow (flow) waarin ze valt, status in Lighthouse
- geboekt op, toegevoegd, bijgewerkt
- contact: e-mailadressen en gsm-nummers met hun bron (formulier, boekingssite doorstuuradres, gastprofiel,
  testadres), knop om een adres toe te voegen
- berichten: korte samenvatting (laatste, volgende) en klik voor het detail

**Detail van een reservatie (nu een venster "Berichten")**, liefst een zijpaneel of eigen pagina:
- vinkje **Automatische berichten voor deze reservatie** met uitleg volgens de stand van de schakelaar (aan: iedereen
  behalve uitgevinkt; selectie: alleen aangevinkt; uit: niemand)
- **tijdlijn** van de stappen (bevestiging, herinnering, code-mail, bedankt, betaalverzoek), per stap: datum, toestand
  (verstuurd, mislukt, komt nog, te laat, voorwaarde niet voldaan, niet actief), reden, per kanaal en adres een chip
  met de toestand, en een knop **Versturen / Opnieuw versturen** met keuze van kanaal en adres (of een ander adres)
- legende van de toestanden
- **alle pogingen**: tijdstip, bericht, kanaal, naar, status (afgeleverd, gelezen, mislukt via Twilio), fout
- ook in het log: formulier ingevuld, pincode gemaakt bij Salto, code en status in Lighthouse gezet, overschrijving
  Booking.com, betaalverzoek in Lighthouse, kamerwissel, antwoord van de gast, deur geopend via de gast-app, Betalen
  geklikt in de gast-app
- nieuw in het detail (gegevens zijn er al): pincodes per kamer, betaalstatus en openstaand bedrag, link naar de
  gast-app van deze reservatie (voorbeeld zoals de gast ze ziet)

## 3. Gasten

Gastprofielen los van de reservaties (blijven bewaard voor later commercieel gebruik).
- zoeken op naam, e-mail, telefoon; knop **Synchroniseren** (profielen opnieuw opbouwen)
- per gast: naam, contact (e-mail, telefoon, doorstuuradres niet voor marketing, uit het formulier), land, aantal
  verblijven, geannuleerd, gemiddeld aantal nachten en personen, eerste en laatste verblijf, voorkeurskanaal, kamers,
  "geen marketing" (afgemeld), link naar zijn reservaties
- per gast kanalen uitzetten (vinkje weg = dit kanaal nooit gebruiken voor deze gast)
- twijfelachtige koppelingen (zelfde gast via verschillende boekingen) laten beslissen

## 4. Lijsten (ontbijt en schoonmaak)

Nu twee tabbladen met dezelfde opbouw; samen voorstellen kan:
- keuze van de dag ("lijst voor"), knoppen **Lijst maken** (niets versturen) en **Maken en versturen**
- overzicht van de laatste 15 lijsten: dag, gemaakt op, door (automatisch of iemand), inhoud (bekijken/verbergen),
  verstuurd naar (mail, WhatsApp/sms) of "niet verstuurd", "geen ontvangers", "uit (hoofdschakelaar)"
- de lijst zelf bekijken zoals ze geprint wordt (per kamer, personen met ontbijt, opmerkingen, in het geel wat
  nagekeken moet worden); downloaden als Excel/PDF

## 5. Instellingen

### Hotel (twee groepen: Dagelijks en Technisch)
Formulier per sectie, met uitleg per veld, bewaren en "terug naar standaard", wie het laatst wijzigde, en een
aanduiding als een waarde per omgeving vastligt (Key Vault). Secties:
- **Dagelijks**: hoofdschakelaars, hotel (naam, adres, telefoon, e-mail, website per taal, logo), receptie-uren,
  check-out (uur, kamerdeur tot, voordeur tot), ontbijt (uren, label), ontbijtlijst en schoonmaaklijst (uur, dag,
  ontvangers mail en WhatsApp), kamers (volgorde op de lijsten, naam, uitleg eigen ingang per taal), wifi, parking,
  noodnummer, oproepen doorschakelen (receptie-uren, vaste lijn, nachtnummer), reviews, toeristenbelasting en munt,
  testomgeving (testadressen e-mail, meerdere mogelijk, testnummer, testgasten), berichten (vanaf welke datum)
- **Technisch**: robot (interval, nachturen, bijwerken om de hoeveel uur, starten bij meldingsmail), Lighthouse,
  Salto (deuren per kamer, voordeur, pincode-lengte, maximum gebruikers), Twilio, afzender van de mails,
  betaalverzoeken, bewaking, check-in-formulier (vraag over trappen per taal)

### Berichten (nu "Workflow")
- per flow (Booking.com, Expedia, Website en andere) een **tijdlijn** van boeking tot na vertrek met de stappen
- per stap: actief, wanneer (na de boeking, x dagen voor aankomst, x dagen na vertrek), kanalen (e-mail, WhatsApp met
  sms als terugval), alleen als (voorwaarden), overslaan als al aan de beurt, betaalknop (geen, openstaand bedrag,
  toeristenbelasting), inhoud van de mail per tarief (NFR, Standaard: reservatiegegevens, link naar de verblijfspagina,
  pincode, praktische info), **voorbeeldmail** bekijken
- regels die altijd gelden (pincode alleen als de kamer betaald is, betaalknop alleen met een betaallink)
- herkennen van de flow: waarden van "Via" en betaalstatus, met de waarden die nu in die flow vallen
- bewaren, terug naar standaard, niet bewaarde wijzigingen

### Robot
- knop **Robot nu draaien** (met hoeveel uur terug), toestand (bezig, sinds, laatste teken van leven)
- logboek per run, uitklapbaar per taak: start, duur, taak, resultaat (ok, deels, fout), te doen, gedaan, opmerking;
  filter per taak; regels verwijderen
- runs volgens Azure (start, einde, duur, status)

## Gevraagd ontwerp

Desktop (1440) en gsm (390) voor:
1. Vandaag
2. Reservaties: lijst
3. Reservatie: detail met tijdlijn, berichten aan/uit, versturen
4. Gasten: lijst en profiel
5. Lijsten: overzicht en een geopende ontbijtlijst
6. Instellingen Hotel (dagelijks), met de hoofdschakelaars en de driestand Gastcommunicatie
7. Instellingen Berichten (workflow van één flow)
8. Robot: logboek met een uitgeklapte run
9. De kop in TST en in PRD, met en zonder herstelbanner

## Randvoorwaarden

- Eén pagina in gewone HTML, CSS en JavaScript zonder framework (zoals nu); het ontwerp moet daarin te bouwen zijn.
- Toegankelijk: echte knoppen, labels bij velden, contrast, bedienbaar met het toetsenbord.
- Gegevens zijn persoonsgegevens: geen gastgegevens in voorbeelden die echt lijken (gebruik verzonnen namen).
