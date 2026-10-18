#!/usr/bin/env python3
"""Lead intake and a small panel. Standard library only."""

import csv
import hmac
import io
import json
import os
import re
import secrets
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

MSK = timezone(timedelta(hours=3))
DATA = Path(os.environ.get("NAROD_DATA", "/var/lib/narod"))
LEADS = DATA / "leads.jsonl"
HOST = os.environ.get("BIND", "127.0.0.1")
PORT = int(os.environ.get("PORT", "8787"))
LOCK = threading.Lock()
SESSIONS = {}
ATTEMPTS = {}
HITS = {}

CITIZENSHIP = {
    "Гражданин РФ",
    "Узбекистан",
    "Таджикистан",
    "Кыргызстан",
    "Казахстан",
    "Армения",
    "Молдова",
    "Другая страна СНГ",
    "Индия",
    "Страна Африки",
    "Страна Ближнего Востока",
    "Другое",
}


def clean(value, limit):
    text = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f]", "", str(value or "")).strip()
    return text[:limit]


def client_ip(headers):
    forwarded = headers.get("X-Forwarded-For", "")
    if forwarded:
        return forwarded.split(",")[0].strip()[:64]
    return headers.get("X-Real-IP", "")[:64] or "unknown"


def limited(bucket, key, max_hits, window):
    now = time.time()
    with LOCK:
        hits = [item for item in bucket.get(key, []) if now - item < window]
        if len(hits) >= max_hits:
            bucket[key] = hits
            return True
        hits.append(now)
        bucket[key] = hits
        return False


def read_leads():
    if not LEADS.exists():
        return []
    rows = []
    for line in LEADS.read_text(encoding="utf-8").splitlines():
        if line.strip():
            rows.append(json.loads(line))
    return rows


def yougile_key():
    return os.environ.get("YOUGILE_KEY", "").strip()


def yougile_request(method, path, payload=None):
    data = None if payload is None else json.dumps(payload).encode()
    request = urllib.request.Request(
        "https://yougile.com/api-v2" + path,
        data=data,
        method=method,
        headers={
            "Authorization": "Bearer " + yougile_key(),
            "Content-Type": "application/json",
            "Accept": "application/json",
        },
    )
    with urllib.request.urlopen(request, timeout=12) as response:
        return json.loads(response.read().decode())


def find_column():
    configured = os.environ.get("YOUGILE_COLUMN_ID", "").strip()
    if configured:
        return configured
    offset = 0
    while offset < 500:
        found = yougile_request("GET", f"/columns?limit=50&offset={offset}")
        if isinstance(found, list):
            rows = found
        elif isinstance(found, dict):
            rows = found.get("content") or []
        else:
            rows = []
        for row in rows:
            title = str(row.get("title", "")).strip().lower()
            if title == "новые" or title.startswith("нов"):
                return row["id"]
        paging = found.get("paging", {}) if isinstance(found, dict) else {}
        if not paging.get("next"):
            break
        offset += 50
    return ""


def push_yougile(lead):
    if not yougile_key():
        return {"status": "not_configured"}
    column = find_column()
    if not column:
        return {"status": "error", "error": "Колонка «Новые» не найдена"}
    lines = [
        f"Имя: {lead['name']}",
        f"Телефон: {lead['phone']}",
        f"Город: {lead['city'] or '—'}",
        f"Гражданство: {lead['citizenship']}",
        f"Ситуация: {lead['status'] or '—'}",
        f"Комментарий: {lead['message'] or '—'}",
        f"Гео: {format_geo(lead.get('geo'))}",
        f"Страница: {lead['page']}",
        f"Метки: {json.dumps(lead.get('utm') or {}, ensure_ascii=False)}",
        f"IP: {lead['ip']}",
    ]
    created = yougile_request(
        "POST",
        "/tasks",
        {
            "title": f"Заявка: {lead['name']} · {lead['city'] or 'город не указан'}",
            "columnId": column,
            "description": "\n".join(lines),
        },
    )
    return {"status": "ok", "id": created.get("id", ""), "columnId": column}


def format_geo(geo):
    if not geo:
        return "—"
    parts = [geo.get("city", ""), geo.get("region", ""), geo.get("country", "")]
    return ", ".join(part for part in parts if part) or "—"


def reverse_geo(latitude, longitude):
    query = urllib.parse.urlencode(
        {
            "format": "jsonv2",
            "lat": f"{latitude:.4f}",
            "lon": f"{longitude:.4f}",
            "zoom": "10",
            "accept-language": "ru",
        }
    )
    request = urllib.request.Request(
        "https://nominatim.openstreetmap.org/reverse?" + query,
        headers={"User-Agent": "narod-pobediteley/1.0 (narodpobediteley@mail.ru)"},
    )
    with urllib.request.urlopen(request, timeout=8) as response:
        payload = json.loads(response.read().decode())
    address = payload.get("address", {})
    city = address.get("city") or address.get("town") or address.get("village") or address.get("hamlet") or ""
    return {
        "city": clean(city, 80),
        "region": clean(address.get("state", ""), 80),
        "country": clean(address.get("country", ""), 80),
        "source": "browser",
    }


def esc(value):
    return (
        str(value)
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )


def page(title, body):
    return f"""<!DOCTYPE html>
<html lang="ru">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <meta name="robots" content="noindex">
  <meta name="theme-color" content="#0e2744">
  <meta name="apple-mobile-web-app-capable" content="yes">
  <title>{title}</title>
  <link rel="icon" href="/img/logo.svg">
  <link rel="manifest" href="/panel/manifest.webmanifest">
  <link rel="stylesheet" href="/css/main.css">
</head>
<body class="panel-body">
  <div class="flag" aria-hidden="true"><span></span><span></span><span></span><span></span></div>
  <main class="section"><div class="wrap">{body}</div></main>
</body>
</html>"""


class Handler(BaseHTTPRequestHandler):
    server_version = "narod"

    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        route = parsed.path.rstrip("/") or "/"
        if route == "/api/health":
            self.send_json(200, {"ok": True, "yougile": bool(yougile_key())})
            return
        if route == "/panel/manifest.webmanifest":
            body = json.dumps(
                {
                    "name": "Заявки · Народ победителей",
                    "short_name": "Заявки",
                    "start_url": "/panel/",
                    "display": "standalone",
                    "background_color": "#f5f3ee",
                    "theme_color": "#0e2744",
                    "lang": "ru",
                },
                ensure_ascii=False,
            ).encode()
            self.send_bytes(200, "application/manifest+json", body)
            return
        if route == "/panel/login":
            self.send_html(page("Вход", login_form("")))
            return
        if route == "/panel/logout":
            self.logout()
            return
        if not self.authorized():
            self.redirect("/panel/login")
            return
        if route == "/panel/export.csv":
            self.export_csv()
            return
        if route == "/panel":
            self.send_html(page("Заявки", panel_html(parsed.query)))
            return
        self.send_json(404, {"error": "Не найдено"})

    def do_POST(self):
        parsed = urllib.parse.urlparse(self.path)
        route = parsed.path.rstrip("/") or "/"
        length = int(self.headers.get("Content-Length", "0") or "0")
        if length > 30000:
            self.send_json(413, {"error": "Слишком большое обращение"})
            return
        raw = self.rfile.read(length) if length else b""
        if route == "/api/lead":
            self.create_lead(raw)
            return
        if route == "/api/geo":
            self.geo(raw)
            return
        if route == "/panel/login":
            self.login(raw)
            return
        self.send_json(404, {"error": "Не найдено"})

    def create_lead(self, raw):
        ip = client_ip(self.headers)
        if limited(HITS, ip, 8, 600):
            self.send_json(429, {"error": "Слишком много заявок. Позвоните нам."})
            return
        try:
            payload = json.loads(raw.decode())
        except (UnicodeDecodeError, json.JSONDecodeError):
            self.send_json(400, {"error": "Некорректная заявка"})
            return
        if clean(payload.get("website"), 80):
            self.send_json(200, {"ok": True})
            return
        lead = {
            "name": clean(payload.get("name"), 80),
            "phone": clean(payload.get("phone"), 20),
            "city": clean(payload.get("city"), 80),
            "citizenship": clean(payload.get("citizenship"), 80),
            "status": clean(payload.get("status"), 120),
            "message": clean(payload.get("message"), 2000),
            "page": clean(payload.get("page"), 120),
        }
        digits = re.sub(r"\D", "", lead["phone"])
        if len(lead["name"]) < 2:
            self.send_json(400, {"error": "Укажите имя"})
            return
        if len(digits) < 10:
            self.send_json(400, {"error": "Укажите телефон"})
            return
        if lead["citizenship"] not in CITIZENSHIP:
            self.send_json(400, {"error": "Выберите гражданство"})
            return
        if payload.get("age") != "yes" or payload.get("consent") != "yes":
            self.send_json(400, {"error": "Нужны подтверждение 18+ и согласие"})
            return
        geo = payload.get("geo") if isinstance(payload.get("geo"), dict) else None
        if geo:
            geo = {
                "city": clean(geo.get("city"), 80),
                "region": clean(geo.get("region"), 80),
                "country": clean(geo.get("country"), 80),
                "source": "browser",
            }
        utm = payload.get("utm") if isinstance(payload.get("utm"), dict) else {}
        utm = {clean(key, 40): clean(value, 200) for key, value in list(utm.items())[:12]}
        record = {
            "id": secrets.token_hex(8),
            "created": datetime.now(MSK).isoformat(timespec="minutes"),
            **lead,
            "geo": geo,
            "utm": utm,
            "ip": ip,
            "user_agent": clean(self.headers.get("User-Agent"), 240),
        }
        try:
            record["yougile"] = push_yougile(record)
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, KeyError) as error:
            record["yougile"] = {"status": "error", "error": clean(error, 240)}
        DATA.mkdir(parents=True, exist_ok=True)
        with LOCK:
            with LEADS.open("a", encoding="utf-8") as handle:
                handle.write(json.dumps(record, ensure_ascii=False) + "\n")
        self.send_json(200, {"ok": True})

    def geo(self, raw):
        ip = client_ip(self.headers)
        if limited(HITS, "geo:" + ip, 20, 600):
            self.send_json(429, {"error": "Слишком часто"})
            return
        try:
            payload = json.loads(raw.decode())
            latitude = float(payload.get("latitude"))
            longitude = float(payload.get("longitude"))
        except (UnicodeDecodeError, json.JSONDecodeError, TypeError, ValueError):
            self.send_json(400, {"error": "Нет координат"})
            return
        if payload.get("consent") != "yes" or not (-90 <= latitude <= 90 and -180 <= longitude <= 180):
            self.send_json(400, {"error": "Нет разрешения"})
            return
        try:
            found = reverse_geo(latitude, longitude)
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError):
            self.send_json(200, {"city": ""})
            return
        self.send_json(200, found)

    def login(self, raw):
        ip = client_ip(self.headers)
        if limited(ATTEMPTS, ip, 8, 600):
            self.send_html(page("Вход", login_form("Слишком много попыток. Подождите.")), 429)
            return
        fields = urllib.parse.parse_qs(raw.decode(errors="ignore"))
        password = fields.get("password", [""])[0]
        expected = os.environ.get("PANEL_PASSWORD", "")
        if not expected or not hmac.compare_digest(password, expected):
            self.send_html(page("Вход", login_form("Неверный пароль")), 401)
            return
        token = secrets.token_urlsafe(32)
        with LOCK:
            SESSIONS[token] = time.time() + 14 * 24 * 3600
        self.send_response(303)
        secure = os.environ.get("COOKIE_SECURE", "1") == "1"
        cookie = f"np_panel={token}; Path=/panel; HttpOnly; SameSite=Strict; Max-Age=1209600"
        if secure:
            cookie += "; Secure"
        self.send_header("Set-Cookie", cookie)
        self.send_header("Location", "/panel/")
        self.end_headers()

    def logout(self):
        token = self.token()
        if token:
            with LOCK:
                SESSIONS.pop(token, None)
        self.send_response(303)
        self.send_header("Set-Cookie", "np_panel=; Path=/panel; Max-Age=0; HttpOnly; SameSite=Strict")
        self.send_header("Location", "/panel/login")
        self.end_headers()

    def token(self):
        header = self.headers.get("Cookie", "")
        for part in header.split(";"):
            name, _, value = part.strip().partition("=")
            if name == "np_panel":
                return value
        return ""

    def authorized(self):
        token = self.token()
        if not token:
            return False
        with LOCK:
            expires = SESSIONS.get(token, 0)
            if expires < time.time():
                SESSIONS.pop(token, None)
                return False
            return True

    def export_csv(self):
        buffer = io.StringIO()
        buffer.write("\ufeff")
        writer = csv.writer(buffer, delimiter=";")
        writer.writerow(["время", "имя", "телефон", "город", "гражданство", "ситуация", "комментарий", "гео", "метки", "yougile"])
        for lead in reversed(read_leads()):
            writer.writerow([
                lead.get("created", ""),
                lead.get("name", ""),
                lead.get("phone", ""),
                lead.get("city", ""),
                lead.get("citizenship", ""),
                lead.get("status", ""),
                lead.get("message", ""),
                format_geo(lead.get("geo")),
                json.dumps(lead.get("utm") or {}, ensure_ascii=False),
                json.dumps(lead.get("yougile") or {}, ensure_ascii=False),
            ])
        self.send_bytes(200, "text/csv; charset=utf-8", buffer.getvalue().encode())

    def send_json(self, status, payload):
        self.send_bytes(status, "application/json; charset=utf-8", json.dumps(payload, ensure_ascii=False).encode())

    def send_html(self, html, status=200):
        self.send_bytes(status, "text/html; charset=utf-8", html.encode())

    def send_bytes(self, status, content_type, body):
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def redirect(self, location):
        self.send_response(303)
        self.send_header("Location", location)
        self.end_headers()

    def log_message(self, fmt, *args):
        return


def login_form(error):
    message = f'<p class="form-status bad">{esc(error)}</p>' if error else ""
    return f"""
    <form class="form login-box" method="post" action="/panel/login">
      <p class="eyebrow">Панель</p>
      <h1>Заявки</h1>
      <p class="muted">Та же страница открывается на iPhone и на Windows.</p>
      <label>Пароль<input type="password" name="password" autocomplete="current-password" required></label>
      {message}
      <button class="btn" type="submit">Войти</button>
    </form>"""


def panel_html(query):
    params = urllib.parse.parse_qs(query)
    needle = clean(params.get("q", [""])[0], 80).lower()
    rows = list(reversed(read_leads()))
    if needle:
        rows = [row for row in rows if needle in json.dumps(row, ensure_ascii=False).lower()]
    yougile = "подключён" if yougile_key() else "не подключён, заявки остаются здесь"
    cards = []
    for row in rows[:200]:
        cards.append(
            f"""<article class="lead-card">
              <header><strong>{esc(row.get("name"))}</strong><time>{esc(row.get("created"))}</time></header>
              <p><a href="tel:{esc(re.sub(r"[^0-9+]", "", row.get("phone", "")))}">{esc(row.get("phone"))}</a></p>
              <p>{esc(row.get("city") or "город не указан")} · {esc(row.get("citizenship"))}</p>
              <p>{esc(row.get("status") or "")}</p>
              <p>{esc(row.get("message") or "")}</p>
              <p class="muted">Гео: {esc(format_geo(row.get("geo")))}<br>Метки: {esc(json.dumps(row.get("utm") or {}, ensure_ascii=False))}<br>YouGile: {esc(json.dumps(row.get("yougile") or {}, ensure_ascii=False))}</p>
            </article>"""
        )
    listing = "".join(cards) or "<p>Заявок пока нет.</p>"
    return f"""
    <p class="eyebrow">Панель заявок</p>
    <h1>Новые обращения</h1>
    <p class="muted">Всего в базе: {len(read_leads())}. YouGile: {yougile}. На iPhone откройте эту страницу в Safari и выберите «На экран Домой».</p>
    <form class="filters" method="get" action="/panel/">
      <input name="q" value="{esc(needle)}" placeholder="Имя, телефон, город" aria-label="Поиск">
      <button class="btn navy" type="submit">Найти</button>
      <a class="btn line" href="/panel/export.csv">Скачать CSV</a>
      <a class="btn line" href="/panel/logout">Выйти</a>
    </form>
    <div class="lead-list">{listing}</div>"""


def main():
    DATA.mkdir(parents=True, exist_ok=True)
    ThreadingHTTPServer((HOST, PORT), Handler).serve_forever()


if __name__ == "__main__":
    main()
