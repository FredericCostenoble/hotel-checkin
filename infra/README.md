# Azure-omgevingen TST en PRD

Twee resource groups in de tenant van Hotel Lucca, met dezelfde opbouw (`main.bicep`):

| Resource | Naam | Kost |
|---|---|---|
| Static Web App (Free): formulier en API | `swa-checkin-<env>` | gratis |
| Function App (Flex Consumption): processen | `func-checkin-<env>-<suffix>` | gratis tegoed, daarna per gebruik |
| Storage (tabellen, deploymentpakketten) | `stcheckin<env><suffix>` | centen per maand |
| Key Vault (secrets per hotel) | `kv-checkin-<env>-<suffix>` | centen per maand |
| Log Analytics + Application Insights | `log-` / `appi-checkin-<env>` | limiet 0,1 GB per dag |
| Budgetmelding | `budget-checkin-<env>` | 10 (TST) / 20 (PRD) per maand |

Alles is gedeeld door de hotels. Per hotel: `config/hotels/<hotel_id>.toml` en secrets
`<hotel_id>-<naam>` in Key Vault. Verhuizen naar een andere tenant: `setup.sh` en de workflow
daar opnieuw draaien, daarna de tabellen overzetten.

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
Static Web App: Custom domains > Add.

## Opmerkingen

- De API van het formulier draait als beheerde Functions in de Static Web App. Op het gratis
  niveau kan die geen managed identity gebruiken; daarom krijgt ze de verbindingsreeks van de
  opslag als instelling (alleen in Azure, nooit in git).
- De Lighthouse-robot (Container Apps Job) wordt toegevoegd zodra het bouwblok klaar is.
- Lukt het budget niet (sommige abonnementen via een partner laten dat niet toe), zet dan
  `deployBudget=false`.
