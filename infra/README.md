# Azure-omgevingen TST en PRD

Twee resource groups in de tenant van Hotel Lucca, met dezelfde opbouw (`main.bicep`):

| Resource | Naam | Kost |
|---|---|---|
| Static Web App (Free): pagina's van het formulier, geen gegevens | `swa-checkin-<env>` | gratis |
| Function App (Flex Consumption): processen en API van het formulier | `func-checkin-<env>-<suffix>` | gratis tegoed, daarna per gebruik |
| Storage (tabellen, deploymentpakketten) | `stcheckin<env><suffix>` | centen per maand |
| Key Vault (secrets per hotel) | `kv-checkin-<env>-<suffix>` | centen per maand |
| Log Analytics + Application Insights | `log-` / `appi-checkin-<env>` | limiet 0,1 GB per dag |
| Budgetmelding | `budget-checkin-<env>` | 10 (TST) / 20 (PRD) per maand |

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
| `FORM_ORIGINS` | leeg | Extra adressen die de API mogen aanroepen, bv. `https://checkin.hotellucca.be` (zet dit in de omgeving prd) |

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

## Eigen domein voor PRD

Na de eerste uitrol naar PRD: in DNS een CNAME `checkin` naar de standaardnaam van
`swa-checkin-prd` (staat in de samenvatting van de workflow), daarna in de portal bij de
Static Web App: Custom domains > Add. Zet daarna `FORM_ORIGINS=https://checkin.hotellucca.be`
in de GitHub-omgeving prd, zodat de API dat adres toelaat.

## Opmerkingen

- De API van het formulier draait in de Function App, in dezelfde regio als de gegevens, met
  managed identity. De opslag laat geen sleutels toe.
- De Lighthouse-robot (Container Apps Job) wordt toegevoegd zodra het bouwblok klaar is.
- Lukt het budget niet (sommige abonnementen via een partner laten dat niet toe), zet dan
  `deployBudget=false`.
