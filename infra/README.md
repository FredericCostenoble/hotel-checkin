# Azure-omgevingen TST en PRD

Twee resource groups in de tenant van Hotel Lucca, met dezelfde opbouw (`main.bicep`):

| Resource | Naam | Kost |
|---|---|---|
| Static Web App (Free): pagina's van het formulier, geen gegevens | `swa-checkin-<env>` | gratis |
| Function App (Flex Consumption): processen en API van het formulier | `func-checkin-<env>-<suffix>` | gratis tegoed, daarna per gebruik |
| Storage (tabellen, deploymentpakketten) | `stcheckin<env><suffix>` | centen per maand |
| Key Vault (secrets per hotel) | `kv-checkin-<env>-<suffix>` | centen per maand |
| Log Analytics + Application Insights | `log-` / `appi-checkin-<env>` | limiet 0,1 GB per dag |
| Budgetmelding (optioneel) | `budget-checkin-<env>` | bedrag via `BUDGET_AMOUNT` |

Alles is gedeeld door de hotels. Per hotel: `config/hotels/<hotel_id>.toml` en secrets
`<hotel_id>-<naam>` in Key Vault. Verhuizen naar een andere tenant: `setup.sh` en de workflow
daar opnieuw draaien, daarna de tabellen overzetten.

## Regio's

Instelbaar met GitHub-variabelen (Settings > Secrets and variables > Actions > Variables),
zonder de code aan te passen. Een variabele in een GitHub-omgeving (tst, prd) gaat voor op
dezelfde variabele op repo-niveau.

| Variabele | Standaard | Waarvoor |
|---|---|---|
| `AZURE_LOCATION` | `belgiumcentral` | Alle gegevens en verwerking (opslag, Function App, Key Vault, logging) |
| `SWA_LOCATION` | `eastus2` | Static Web App. Alleen de pagina's, geen gegevens. Static Web Apps bestaat maar in enkele regio's (westeurope, eastus2, westus2, centralus, eastasia) |
| `BUDGET_AMOUNT` | leeg (geen melding) | Maandbudget; melding bij 80 procent verbruikt of 100 procent verwacht. Per omgeving in te stellen |
| `CUSTOM_DOMAIN` | leeg | Eigen adres van het formulier, per omgeving: `checkin-tst.hotellucca.be` (tst), `checkin.hotellucca.be` (prd). Wordt automatisch gekoppeld en toegelaten in de API |
| `FORM_ORIGINS` | leeg | Extra adressen die de API mogen aanroepen (normaal niet nodig) |

West Europe neemt sinds oktober 2026 geen nieuwe klanten meer aan; daarom Belgium Central.
Bestaande resources verhuizen niet vanzelf als de regio verandert: verwijder dan eerst de
resources in de resource group (de tabellen eerst overzetten).

## Verschil TST en PRD

- TST: `APP_ENV=tst`. Elke mail gaat naar `TEST_EMAIL`, elke SMS of WhatsApp naar `TEST_PHONE`.
  De links in de mails wijzen naar het testformulier (`CHECKIN_FORM_URL`).
  TST mag de productie van Lighthouse lezen, maar schrijft er nooit in.
- PRD: `APP_ENV=prd`, berichten naar de echte gasten, formulier op `checkin.hotellucca.be`.
- Het ophalen van reservaties staat in beide uit (`POLL_ENABLED=false`) tot de Lighthouse-robot klaar is.

## Eenmalige opzet

In de codespace:

```bash
az login
bash infra/setup.sh
```

Daarna rolt elke push op `main` uit naar TST. PRD: Actions > Deploy > Run workflow > `prd`.

## Eigen domein

DNS van hotellucca.be staat bij Combell. Per omgeving een CNAME naar de standaardnaam van de
Static Web App (staat in de samenvatting van de workflow):

| Naam | Wijst naar |
|---|---|
| `checkin` | Static Web App van PRD |
| `checkin-tst` | Static Web App van TST |

Daarna de GitHub-variabele `CUSTOM_DOMAIN` in de omgeving zetten en opnieuw uitrollen. Azure
koppelt het adres en maakt zelf een certificaat (kan enkele minuten duren).
Dev is de codespace en heeft geen eigen adres.

## Opmerkingen

- De API van het formulier draait in de Function App, in dezelfde regio als de gegevens, met
  managed identity. De opslag laat geen sleutels toe.
- De Lighthouse-robot (Container Apps Job) wordt toegevoegd zodra het bouwblok klaar is.
- De budgetmelding vraagt dat de kosten zichtbaar zijn voor de klant. Bij een abonnement via
  een partner (Cloudworx) zet de partner dat aan; anders faalt de uitrol met een 401.
  Laat `BUDGET_AMOUNT` leeg tot dat geregeld is.
