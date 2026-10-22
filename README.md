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
| `checkin/service.py` + `web/checkin/` + `api/` | Online check-in-formulier (checkin.hotellucca.be) | Azure Static Web Apps (gratis niveau) |
| `messaging/templates.py` | Berichten in NL/FR/EN/DE, mailopmaak | Teksten in `messaging/texts/`, instellingen in `config/hotel.toml` |
| `processes/` | Processen die de bouwblokken combineren | |

Gedeelde types staan in `core/models.py`, configuratie in `core/config.py`.

## Hosting (Azure)

- Bouwblokken en processen: Azure Functions (`function_app.py`).
- Lighthouse-robot (headless browser): Azure Container Apps Job op schema, los van een pc.
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

## Check-in-formulier lokaal testen

```bash
python -m hotel_checkin.checkin.devserver
```

Open de link die verschijnt (`?r=demo`). Opslag in het geheugen met voorbeeldreservaties.
Met `--azure` gebruikt de server de echte opslag (`STORAGE_TABLE_ENDPOINT`).

Deployment naar Azure Static Web Apps: `web/checkin` is de app, `api` de API. Voor de deployment
worden `src/hotel_checkin` en `config` naar `api/` gekopieerd (workflow volgt).
