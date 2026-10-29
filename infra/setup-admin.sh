#!/usr/bin/env bash
# Eenmalige opzet van de Microsoft-login voor de opvolgpagina (TST en PRD).
# Draai in de codespace na `az login` (beheerder van de tenant) en `gh auth login`:
#     unset GITHUB_TOKEN; bash infra/setup-admin.sh
# Mag opnieuw gedraaid worden. Extra gebruikers toegang geven:
#     bash infra/setup-admin.sh iemand@hotellucca.be
#
# Per omgeving:
# 1. App registration hotel-checkin-admin-<env> (alleen accounts van deze tenant)
# 2. Toewijzing verplicht: alleen wie toegewezen is, kan aanmelden
# 3. Jezelf (en eventueel de opgegeven gebruikers) toewijzen
# 4. GitHub-variabele ADMIN_CLIENT_ID in de omgeving zetten; de volgende uitrol zet de login aan

set -euo pipefail

REPO="FredericCostenoble/hotel-checkin"
EXTRA_USERS=("$@")
ME=$(az ad signed-in-user show --query id -o tsv)

for ENV in tst prd; do
  RG="rg-checkin-$ENV"
  HOST=$(az resource list -g "$RG" --resource-type Microsoft.Web/sites \
    --query "[?starts_with(name, 'func-checkin-')].name | [0]" -o tsv)
  HOST=$(az resource show -g "$RG" -n "$HOST" --resource-type Microsoft.Web/sites \
    --query properties.defaultHostName -o tsv)
  if [ -z "$HOST" ]; then echo "Geen Function App gevonden in $RG"; exit 1; fi
  NAME="hotel-checkin-admin-$ENV"
  echo "== $ENV: https://$HOST/opvolging/"

  APP_ID=$(az ad app list --display-name "$NAME" --query "[0].appId" -o tsv)
  if [ -z "$APP_ID" ]; then
    APP_ID=$(az ad app create --display-name "$NAME" --sign-in-audience AzureADMyOrg \
      --web-redirect-uris "https://$HOST/.auth/login/aad/callback" \
      --enable-id-token-issuance true --query appId -o tsv)
  fi
  SP_ID=$(az ad sp show --id "$APP_ID" --query id -o tsv 2>/dev/null || true)
  if [ -z "$SP_ID" ]; then
    SP_ID=$(az ad sp create --id "$APP_ID" --query id -o tsv)
  fi
  az ad sp update --id "$APP_ID" --set appRoleAssignmentRequired=true

  for USER in "$ME" "${EXTRA_USERS[@]}"; do
    UID_=$(az ad user show --id "$USER" --query id -o tsv)
    EXISTS=$(az rest --method get \
      --url "https://graph.microsoft.com/v1.0/servicePrincipals/$SP_ID/appRoleAssignedTo" \
      --query "value[?principalId=='$UID_'].id" -o tsv)
    if [ -z "$EXISTS" ]; then
      az rest --method post \
        --url "https://graph.microsoft.com/v1.0/servicePrincipals/$SP_ID/appRoleAssignedTo" \
        --body "{\"principalId\":\"$UID_\",\"resourceId\":\"$SP_ID\",\"appRoleId\":\"00000000-0000-0000-0000-000000000000\"}" \
        -o none
      echo "   toegang voor $USER"
    fi
  done

  if gh variable set ADMIN_CLIENT_ID --env "$ENV" --repo "$REPO" --body "$APP_ID" >/dev/null 2>&1; then
    echo "   ADMIN_CLIENT_ID gezet voor $ENV"
  else
    echo "   Zet zelf in GitHub (omgeving $ENV): ADMIN_CLIENT_ID = $APP_ID"
  fi
done
echo "Klaar. Rol daarna opnieuw uit (TST: push op main; PRD: Run workflow > prd)."
