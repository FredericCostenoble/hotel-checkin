#!/usr/bin/env bash
# Eigen adres voor de monitor koppelen (eenmalig per omgeving), na de DNS-records:
#   CNAME <naam>        -> <function app>.azurewebsites.net
#   TXT   asuid.<naam>  -> customDomainVerificationId van de function app
# Gebruik (in de codespace):
#   unset GITHUB_TOKEN; bash infra/add-monitor-domain.sh tst monitor-tst.hotellucca.be
#   unset GITHUB_TOKEN; bash infra/add-monitor-domain.sh prd monitor.hotellucca.be

set -euo pipefail
ENV="$1"; DOMAIN="$2"
REPO="FredericCostenoble/hotel-checkin"
RG="rg-checkin-$ENV"
FUNC=$(az resource list -g "$RG" --resource-type Microsoft.Web/sites \
  --query "[?starts_with(name, 'func-checkin-')].name | [0]" -o tsv)

echo "1. Adres koppelen aan $FUNC"
az functionapp config hostname add -g "$RG" --webapp-name "$FUNC" --hostname "$DOMAIN" -o none

echo "2. Gratis certificaat van Azure (kan enkele minuten duren)"
THUMB=$(az functionapp config ssl create -g "$RG" -n "$FUNC" --hostname "$DOMAIN" --query thumbprint -o tsv)

echo "3. Certificaat aan het adres binden"
az functionapp config ssl bind -g "$RG" -n "$FUNC" --certificate-thumbprint "$THUMB" --ssl-type SNI -o none

echo "4. Adres toevoegen aan de login"
gh variable set MONITOR_DOMAIN --env "$ENV" --repo "$REPO" --body "$DOMAIN"
bash "$(dirname "$0")/setup-admin.sh"

echo "Klaar: https://$DOMAIN/monitor/"
