#!/bin/sh
set -eu

HOST="${DEPLOY_HOST:-root@194.87.140.49}"
KEY="${DEPLOY_KEY:-$HOME/.ssh/timeweb_narod}"
ROOT="$(CDPATH= cd -- "$(dirname "$0")/.." && pwd)"
SSH="ssh -i $KEY -o IdentitiesOnly=yes"

python3 "$ROOT/src/build.py"

tar -C "$ROOT/public" -czf - . | $SSH "$HOST" 'mkdir -p /var/www/narod && tar -C /var/www/narod -xzf - && rm -f /var/www/narod/styles.css'

$SSH "$HOST" 'mkdir -p /opt/narod /etc/narod /var/lib/narod /etc/letsencrypt/renewal-hooks/deploy'
scp -i "$KEY" -o IdentitiesOnly=yes "$ROOT/server/app.py" "$HOST:/opt/narod/app.py"
scp -i "$KEY" -o IdentitiesOnly=yes "$ROOT/deploy/narod-leads.service" "$HOST:/etc/systemd/system/narod-leads.service"
scp -i "$KEY" -o IdentitiesOnly=yes "$ROOT/deploy/nginx/narod.conf" "$HOST:/etc/nginx/sites-available/narod"
scp -i "$KEY" -o IdentitiesOnly=yes "$ROOT/deploy/nginx/reload-nginx.sh" "$HOST:/etc/letsencrypt/renewal-hooks/deploy/reload-nginx.sh"

$SSH "$HOST" 'bash -s' << 'EOF'
set -eu
if [ ! -f /etc/narod/config.env ]; then
  token=$(python3 -c 'import secrets; print(secrets.token_urlsafe(18))')
  cat > /etc/narod/config.env << ENV
PANEL_PASSWORD=${token}
COOKIE_SECURE=1
BIND=127.0.0.1
PORT=8787
NAROD_DATA=/var/lib/narod
YOUGILE_COMPANY_ID=438914b0-2d5a-4ca3-acd9-d008bd69c55e
YOUGILE_KEY=
YOUGILE_COLUMN_ID=
ENV
  echo "PANEL_PASSWORD_CREATED=${token}"
fi
chown root:www-data /etc/narod/config.env
chmod 640 /etc/narod/config.env
chown -R www-data:www-data /var/lib/narod
chmod 755 /etc/letsencrypt/renewal-hooks/deploy/reload-nginx.sh /opt/narod/app.py
ln -sfn /etc/nginx/sites-available/narod /etc/nginx/sites-enabled/narod
rm -f /etc/nginx/sites-enabled/default
nginx -t
systemctl daemon-reload
systemctl enable --now narod-leads
systemctl restart narod-leads
systemctl reload nginx
systemctl is-active narod-leads nginx
EOF
