#!/bin/sh
set -eu

HOST="${DEPLOY_HOST:-root@194.87.140.49}"
KEY="${DEPLOY_KEY:-$HOME/.ssh/timeweb_narod}"
ROOT="$(CDPATH= cd -- "$(dirname "$0")/.." && pwd)"

scp -i "$KEY" -o IdentitiesOnly=yes \
  "$ROOT/public/index.html" \
  "$ROOT/public/styles.css" \
  "$HOST:/var/www/narod/"

scp -i "$KEY" -o IdentitiesOnly=yes \
  "$ROOT/deploy/nginx/narod.conf" \
  "$HOST:/etc/nginx/sites-available/narod"

scp -i "$KEY" -o IdentitiesOnly=yes \
  "$ROOT/deploy/nginx/reload-nginx.sh" \
  "$HOST:/etc/letsencrypt/renewal-hooks/deploy/reload-nginx.sh"

ssh -i "$KEY" -o IdentitiesOnly=yes "$HOST" \
  'chmod 755 /etc/letsencrypt/renewal-hooks/deploy/reload-nginx.sh && ln -sfn /etc/nginx/sites-available/narod /etc/nginx/sites-enabled/narod && rm -f /etc/nginx/sites-enabled/default && nginx -t && systemctl reload nginx'
