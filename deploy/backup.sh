#!/bin/sh
set -eu

HOST="${DEPLOY_HOST:-root@194.87.140.49}"
KEY="${DEPLOY_KEY:-$HOME/.ssh/timeweb_narod}"
ROOT="$(CDPATH= cd -- "$(dirname "$0")/.." && pwd)"
STAMP="$(date +%F)"
SSH="ssh -i $KEY -o IdentitiesOnly=yes"
DEST="$ROOT/backups/$STAMP"

mkdir -p "$DEST/brand" "$ROOT/brand"
cp "$ROOT/public/img/logo.svg" "$ROOT/brand/logo.svg"
cp "$ROOT/public/favicon.svg" "$ROOT/brand/favicon.svg"
cp "$ROOT/public/favicon-panel.svg" "$ROOT/brand/favicon-panel.svg"
cp "$ROOT/brand/"*.svg "$DEST/brand/"
tar -C "$ROOT/public" -czf "$DEST/public.tar.gz" .
cp "$ROOT/server/app.py" "$DEST/app.py"
cp "$ROOT/deploy/nginx/narod.conf" "$DEST/narod.conf"
cp "$ROOT/deploy/narod-leads.service" "$DEST/narod-leads.service"

$SSH "$HOST" "mkdir -p /var/backups/narod/$STAMP && tar -C /var/www/narod -czf /var/backups/narod/$STAMP/public.tar.gz . && tar -C /var/lib/narod -czf /var/backups/narod/$STAMP/var-lib-narod.tar.gz . && cp /opt/narod/app.py /etc/narod/config.env /etc/nginx/sites-available/narod /etc/systemd/system/narod-leads.service /var/backups/narod/$STAMP/ && chmod 700 /var/backups/narod/$STAMP"
scp -i "$KEY" -o IdentitiesOnly=yes \
  "$HOST:/var/backups/narod/$STAMP/config.env" \
  "$HOST:/var/backups/narod/$STAMP/var-lib-narod.tar.gz" \
  "$HOST:/var/backups/narod/$STAMP/public.tar.gz" \
  "$DEST/"
chmod 700 "$DEST"
echo "backup $DEST"
