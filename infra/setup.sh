#!/usr/bin/env bash
# Eenmalige opzet van Azure en GitHub voor de uitrol (TST en PRD).
# Draai in de codespace na `az login` met een account dat eigenaar is van het abonnement:
#     bash infra/setup.sh
# Het script mag opnieuw gedraaid worden; wat al bestaat, wordt overgeslagen.
#
# Wat het doet:
# 1. Resource providers registreren.
# 2. Resource groups rg-checkin-tst en rg-checkin-prd aanmaken.
# 3. App registration github-hotel-checkin met federated credentials voor de GitHub-omgevingen
#    tst en prd (aanmelden zonder secret).
# 4. Die app rechten geven op enkel de twee resource groups.
# 5. De GitHub-variabelen zetten (of tonen als dat vanuit de codespace niet lukt).

set -euo pipefail

REPO="FredericCostenoble/hotel-checkin"
# Regio van de resource groups (alleen metadata). Instelbaar: AZURE_LOCATION=... bash infra/setup.sh
LOCATION="${AZURE_LOCATION:-belgiumcentral}"
APP_NAME="github-hotel-checkin"
ALERT_EMAIL="${ALERT_EMAIL:-management@hotellucca.be}"

OWNER="${REPO%%/*}"
REPO_NAME="${REPO#*/}"
OWNER_ID=$(gh api "repos/$REPO" --jq .owner.id)
REPO_ID=$(gh api "repos/$REPO" --jq .id)

SUB=$(az account show --query id -o tsv)
TENANT=$(az account show --query tenantId -o tsv)
echo "Abonnement: $(az account show --query name -o tsv) ($SUB)"

echo "1. Resource providers"
for p in Microsoft.Web Microsoft.Storage Microsoft.KeyVault Microsoft.OperationalInsights \
         Microsoft.Insights Microsoft.Consumption; do
  az provider register --namespace "$p" >/dev/null
done

echo "2. App registration $APP_NAME"
APP_ID=$(az ad app list --display-name "$APP_NAME" --query "[0].appId" -o tsv)
if [ -z "$APP_ID" ]; then
  APP_ID=$(az ad app create --display-name "$APP_NAME" --query appId -o tsv)
fi
SP_ID=$(az ad sp show --id "$APP_ID" --query id -o tsv 2>/dev/null || true)
if [ -z "$SP_ID" ]; then
  SP_ID=$(az ad sp create --id "$APP_ID" --query id -o tsv)
fi

for ENV in tst prd; do
  RG="rg-checkin-$ENV"
  echo "3. $RG"
  az group create --name "$RG" --location "$LOCATION" --tags app=hotel-checkin env="$ENV" >/dev/null
  RG_ID=$(az group show --name "$RG" --query id -o tsv)

  for ROLE in "Contributor" "Role Based Access Control Administrator"; do
    if [ -z "$(az role assignment list --assignee "$SP_ID" --role "$ROLE" --scope "$RG_ID" --query "[0].id" -o tsv)" ]; then
      az role assignment create --assignee-object-id "$SP_ID" --assignee-principal-type ServicePrincipal \
        --role "$ROLE" --scope "$RG_ID" >/dev/null
    fi
  done

  # GitHub gebruikt in het OIDC-token ofwel de namen, ofwel namen met vaste id's
  # (repo:eigenaar@id/repo@id:...). Beide vormen worden toegelaten.
  for CRED in "github-$ENV|repo:$REPO:environment:$ENV" \
              "github-$ENV-ids|repo:$OWNER@$OWNER_ID/$REPO_NAME@$REPO_ID:environment:$ENV"; do
    NAME="${CRED%%|*}"
    SUBJECT="${CRED#*|}"
    if [ -z "$(az ad app federated-credential list --id "$APP_ID" --query "[?name=='$NAME'].name" -o tsv)" ]; then
      az ad app federated-credential create --id "$APP_ID" --parameters "{
        \"name\": \"$NAME\",
        \"issuer\": \"https://token.actions.githubusercontent.com\",
        \"subject\": \"$SUBJECT\",
        \"audiences\": [\"api://AzureADTokenExchange\"]
      }" >/dev/null
    fi
  done
done

ME=$(az ad signed-in-user show --query id -o tsv)

echo "4. GitHub-variabelen"
declare -A VARS=(
  [AZURE_CLIENT_ID]="$APP_ID"
  [AZURE_TENANT_ID]="$TENANT"
  [AZURE_SUBSCRIPTION_ID]="$SUB"
  [ALERT_EMAIL]="$ALERT_EMAIL"
  [KV_ADMIN_OBJECT_ID]="$ME"
  [TEST_EMAIL]="${TEST_EMAIL:-}"
  [TEST_PHONE]="${TEST_PHONE:-}"
)
FAILED=0
for k in "${!VARS[@]}"; do
  if ! gh variable set "$k" --repo "$REPO" --body "${VARS[$k]}" >/dev/null 2>&1; then
    FAILED=1
  fi
done

if [ "$FAILED" = 1 ]; then
  echo
  echo "De variabelen konden niet automatisch gezet worden. Zet ze in GitHub:"
  echo "Settings > Secrets and variables > Actions > tabblad Variables > New repository variable"
  for k in "${!VARS[@]}"; do printf '  %-22s %s\n' "$k" "${VARS[$k]}"; done
else
  echo "Variabelen gezet in $REPO."
fi
echo
echo "Klaar. De volgende push op main rolt uit naar TST."
