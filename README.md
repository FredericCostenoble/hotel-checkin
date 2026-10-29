# hotel-checkin
Hotel check in proces

Bibliotheek met kleine, losse bouwblokken om de check-in van het hotel te automatiseren
(Lighthouse PMS, Salto KS sloten, mail, SMS, WhatsApp, telefoon). Een procesmodule roept
de bouwblokken na elkaar op. Elk bouwblok doet één ding.

## Bouwblokken

| Module | Functie | Leverancier / techniek |
|---|---|---|
| `messaging/email.py` | Mail sturen | Microsoft Graph (eigen M365-mailbox) |
| `messaging/sms.py` | SMS sturen | Twilio |
| `messaging/whatsapp.py` | WhatsApp sturen | Twilio (WhatsApp Business) |
| `pms/lighthouse.py` | Nieuwe reservaties ophalen, code en status wegschrijven | Browserautomatisatie (Playwright), later API indien Lighthouse die aanbiedt |
| `access/salto.py` | Code reserveren voor gast, kamer en periode | Salto KS Connect API |
| `voice/ivr.py` | Nachtelijke oproepen automatisch afhandelen | Twilio Voice |
| `guests/repository.py` | Reservaties, berichtenlog, marketing-blokkeerlijst | Azure Table Storage |
| `checkin/service.py` + `web/checkin/` | Online check-in-formulier (checkin.hotellucca.be) | Pagina's: Azure Static Web Apps (gratis), API: Function App |
| `messaging/templates.py` | Berichten in NL/FR/EN/DE, mailopmaak | Teksten in `messaging/texts/`, instellingen per hotel in `config/hotels/<hotel_id>.toml` |
| `processes/` | Processen die de bouwblokken combineren | |

Gedeelde types staan in `core/models.py`, configuratie in `core/config.py`.

## Meerdere hotels

- Elk hotel heeft een `hotel_id` (bv. `lucca`) en een instellingenbestand `config/hotels/<hotel_id>.toml`.
- Eigen teksten per hotel (optioneel): `config/hotels/<hotel_id>/texts/<taal>.toml`.
- Alle gegevens in de opslag zitten per hotel in een eigen partitie; ook de marketing-blokkeerlijst.
- Instellingen per hotel (`core/config.py`, `hotel_setting`), in deze volgorde:
  1. eigen geheim van het hotel: Key Vault `<hotel_id>-<naam>` (codespace: `LUCCA_<NAAM>`), bv. `lucca-lighthouse-password`;
  2. het hotelbestand, voor wat niet geheim is (afzendnummers, Lighthouse-adres);
  3. gedeelde waarde voor alle hotels, bv. het Twilio-account (`TWILIO-AUTH-TOKEN`).
  Een hotel kan zo een eigen waarde krijgen zonder codewijziging. Het Lighthouse-wachtwoord is altijd van het hotel zelf.

## Omgevingen en bescherming van gasten

- `APP_ENV=prd` (productie), `tst` (test in Azure) of `dev` (codespace, standaard).
- Buiten `prd` gaat elk bericht naar `TEST_EMAIL` of `TEST_PHONE`; de echte ontvanger staat in het
  onderwerp of vooraan in de tekst. Zonder testadres wordt niets verstuurd (`core/safety.py`).

## Hosting (Azure)

- Twee omgevingen: `rg-checkin-tst` en `rg-checkin-prd`, opgebouwd met `infra/main.bicep`
  (details en eenmalige opzet in `infra/README.md`).
- Uitrol met GitHub Actions (`.github/workflows/deploy.yml`): push op main naar TST, PRD manueel.
- Bouwblokken en processen: Azure Functions (`function_app.py`).
- Lighthouse-robot (headless browser): Azure Container Apps Job op schema, los van een pc (volgt).
- Secrets: Azure Key Vault, toegang via Managed Identity.
- Logging: Application Insights.

## Ontwikkelen

Open de repo in GitHub Codespaces (Code > Codespaces > Create codespace on main).
De devcontainer installeert Python, Azure CLI, Azure Functions Core Tools en Playwright.

```bash
pytest            # tests
func start        # Azure Functions lokaal in de codespace
```

Configuratie gebeurt via omgevingsvariabelen (zie `.env.example`). Nooit secrets committen.

## Opvolgpagina

Lokaal: start de devserver (hieronder) en open `/opvolging/`. Met "Robot nu draaien" leest de robot
Lighthouse (alleen lezen) en verschijnen de reservaties. In Azure: zie `infra/README.md`.

## Check-in-formulier lokaal testen

```bash
python -m hotel_checkin.checkin.devserver
```

Open de link die verschijnt (`?r=demo`). Opslag in het geheugen met voorbeeldreservaties.
Met `--azure` gebruikt de server de echte opslag (`STORAGE_TABLE_ENDPOINT`).

In Azure staan de pagina's (`web/checkin`) in Static Web Apps en draait de API in de Function App
(`function_app.py`). Het adres van de API zet de workflow in `web/checkin/config.js`.
