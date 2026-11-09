# Azure-omgevingen TST en PRD

Twee resource groups in de tenant van Hotel Lucca, met dezelfde opbouw (`main.bicep`):

| Resource | Naam | Kost |
|---|---|---|
| Static Web App (Free): pagina's van het formulier, geen gegevens | `swa-checkin-<env>` | gratis |
| Function App (Flex Consumption): processen en API van het formulier | `func-checkin-<env>-<suffix>` | gratis tegoed, daarna per gebruik |
| Storage (tabellen, deploymentpakketten) | `stcheckin<env><suffix>` | centen per maand |
| Key Vault (secrets per hotel) | `kv-checkin-<env>-<suffix>` | centen per maand |
| Log Analytics + Application Insights | `log-` / `appi-checkin-<env>` | limiet 0,1 GB per dag |
| Robot: Container Apps Job met Chromium | `job-checkin-robot-<env>`, `cae-checkin-<env>` | binnen het gratis tegoed, hooguit enkele euro's |
| Containerregister (gedeeld TST/PRD, in rg-checkin-prd) | `acrcheckin<suffix>` | ongeveer 5 euro per maand |
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

- TST: `APP_ENV=tst`. Elke mail en SMS of WhatsApp gaat naar het testadres of testnummer van het hotel
  (instellingen in de monitor, sectie `[test]`). Leeg = niets versturen.
  De links in de mails wijzen naar het testformulier (`CHECKIN_FORM_URL`).
  TST mag de productie van Lighthouse lezen, maar schrijft er nooit in.
- PRD: `APP_ENV=prd`, berichten naar de echte gasten, formulier op `checkin.hotellucca.be`.
- De Lighthouse-robot (Container Apps Job, `job-checkin-robot-<env>`) leest Lighthouse alleen.
  De job heeft geen eigen schema (triggerType Manual): de Function App start hem. Normaal start de meldingsmail
  van Lighthouse de robot meteen (processes/mail_trigger.py); als vangnet start de Function App hem om de
  [robot] check_minutes (instelling in de monitor, Lucca: 60; processes/robot_schedule.py). Met alle hoofdschakelaars
  uit start hij niet (bevroren omgeving, geen kost). Daarnaast de knop "Robot nu draaien" op de monitor.
  De GitHub-variabele ROBOT_SCHEDULE wordt niet meer gebruikt.
  Hij leest alles sinds de nieuwste opgeslagen boeking.

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

## Opvolgpagina

Per omgeving op `https://<function app>/monitor/` (staat in de samenvatting van de workflow).
Toont per hotel de reservaties, verstuurde berichten en de runs van de robot. Bevat
gastgegevens en is daarom alleen bereikbaar na aanmelden met een Microsoft-account van de
tenant, en alleen voor wie toegewezen is.

Eenmalig in de codespace (na `az login` en `gh auth login`):

```bash
unset GITHUB_TOKEN; bash infra/setup-admin.sh
```

Eigen adres (monitor.hotellucca.be, monitor-tst.hotellucca.be): DNS-records zetten (CNAME en TXT
`asuid.<naam>`), daarna `bash infra/add-monitor-domain.sh <env> <adres>`.

Iemand anders toegang geven: `bash infra/setup-admin.sh iemand@hotellucca.be`.
Zolang `ADMIN_CLIENT_ID` niet gezet is, blijft de opvolgpagina dicht.

## Herstelrobot (Lighthouse veranderd)

De robot doet elke dag een zelftest (processes/pms_health.py). Vindt hij niet meer alles in Lighthouse, dan schrijft
hij niets meer in Lighthouse, bewaart hij de pagina's als bewijs en vraagt hij de herstelrobot een oplossing
(.github/workflows/repair.yml). Die zet een geteste oplossing alleen op TST. Op TST zetten Frederic of Seppe
ze na het testen met een knop naar PRD ([beheer] prd_vrijgeven). Eenmalig nodig:

1. GitHub-secret `ANTHROPIC_API_KEY` (Settings > Secrets and variables > Actions).
2. Een fine-grained GitHub-token, alleen deze repo, rechten Actions lezen en schrijven en Contents lezen, als
   secret `github-deploy-token` in de Key Vault van TST en van PRD (kv-checkin-tst-... en kv-checkin-prd-...).
3. De deploy-identiteit (GitHub-variabele AZURE_CLIENT_ID) de rol Storage Table Data Reader op de opslag van
   TST en PRD (om het bewijs te lezen):
   `az role assignment create --assignee <AZURE_CLIENT_ID> --role "Storage Table Data Reader" --scope $(az storage account list -g rg-checkin-prd --query "[0].id" -o tsv)` (en hetzelfde met rg-checkin-tst).
4. Settings > Actions > General: "Allow GitHub Actions to create and approve pull requests" aan.
5. Geen verplichte goedkeurders op de GitHub-omgeving prd (anders wacht de herstelrobot op goedkeuring).

Proef: Actions > Repair > Run workflow (prd). Zonder probleem vindt hij niets en verandert hij niets.

## Opmerkingen

- De API van het formulier draait in de Function App, in dezelfde regio als de gegevens, met
  managed identity. De opslag laat geen sleutels toe.
- De budgetmelding vraagt dat de kosten zichtbaar zijn voor de klant. Bij een abonnement via
  een partner (Cloudworx) zet de partner dat aan; anders faalt de uitrol met een 401.
  Laat `BUDGET_AMOUNT` leeg tot dat geregeld is.
