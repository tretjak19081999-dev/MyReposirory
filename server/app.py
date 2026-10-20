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
EVENTS = DATA / "events.jsonl"
HITS_LOG = DATA / "hits.jsonl"
REPORTS = DATA / "reports.jsonl"
SNAPSHOT = DATA / "yougile-snapshot.json"
VK_CACHE = DATA / "vk-cache.json"
METRIKA_CACHE = DATA / "metrika-cache.json"
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


def read_jsonl(path):
    if not path.exists():
        return []
    rows = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            rows.append(json.loads(line))
    return rows


def read_leads():
    return read_jsonl(LEADS)


def read_events():
    return read_jsonl(EVENTS)


def append_jsonl(path, record):
    DATA.mkdir(parents=True, exist_ok=True)
    with LOCK:
        with path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(record, ensure_ascii=False) + "\n")


def append_event(event):
    event.setdefault("at", datetime.now(MSK).isoformat(timespec="minutes"))
    append_jsonl(EVENTS, event)


def parse_time(value):
    try:
        return datetime.fromisoformat(value)
    except (TypeError, ValueError):
        return None


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
        f"Регион: {lead.get('region') or '—'}",
        f"Возраст: {lead.get('age_years') or '—'}",
        f"Гражданство: {lead['citizenship']}",
        f"Профессия: {lead.get('profession') or '—'}",
        f"Куда хочет: {lead.get('direction') or '—'}",
        f"Ситуация: {lead['status'] or '—'}",
        f"Дополнительно: {lead['message'] or '—'}",
        f"Сообщения об услугах: {'да' if lead.get('ads') == 'yes' else 'нет'}",
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


FUNNEL = ["Новые", "Связались", "Документы", "Оформление", "Завершено", "Не наш случай"]
SYNC_LOCK = threading.Lock()


def list_rows(payload):
    if isinstance(payload, list):
        return payload
    if isinstance(payload, dict):
        return payload.get("content") or []
    return []


def sync_yougile():
    if not yougile_key():
        return
    if not SYNC_LOCK.acquire(blocking=False):
        return
    try:
        board = os.environ.get("YOUGILE_BOARD_ID", "").strip()
        query = f"/columns?limit=50" + (f"&boardId={board}" if board else "")
        columns = [row for row in list_rows(yougile_request("GET", query)) if not row.get("deleted")]
        if board:
            columns = [row for row in columns if row.get("boardId") == board]
        current = {}
        for column in columns:
            tasks = list_rows(yougile_request("GET", f"/task-list?columnId={column['id']}&limit=100"))
            for task in tasks:
                current[task["id"]] = {
                    "title": task.get("title", ""),
                    "columnId": column["id"],
                    "column": column.get("title", ""),
                }
        previous = {}
        if SNAPSHOT.exists():
            previous = json.loads(SNAPSHOT.read_text(encoding="utf-8"))
        for task_id, item in current.items():
            old = previous.get(task_id)
            if old and old.get("columnId") != item["columnId"]:
                append_event({
                    "type": "move",
                    "taskId": task_id,
                    "title": item["title"],
                    "from": old.get("column", ""),
                    "to": item["column"],
                })
        DATA.mkdir(parents=True, exist_ok=True)
        SNAPSHOT.write_text(json.dumps(current, ensure_ascii=False), encoding="utf-8")
    finally:
        SYNC_LOCK.release()


def sync_loop():
    while True:
        try:
            sync_yougile()
        except Exception:
            pass
        time.sleep(180)


def bar_rows(pairs):
    peak = max((count for _, count in pairs), default=0) or 1
    html = []
    for label, count in pairs:
        width = max(4, round(count / peak * 100)) if count else 0
        html.append(
            f'<div class="bar"><span>{esc(label)}</span><i style="width:{width}%"></i><b>{count}</b></div>'
        )
    return "".join(html) or "<p class=\"muted\">Пока пусто.</p>"


def svg_columns(pairs):
    if not pairs:
        return "<p class=\"muted\">За период пусто.</p>"
    width, height = 720, 190
    peak = max((count for _, count in pairs), default=0) or 1
    gap = 8
    bar_w = max(6, (width - gap * (len(pairs) + 1)) / max(len(pairs), 1))
    parts = [f'<svg class="chart" viewBox="0 0 {width} {height}" role="img">']
    for index, (label, count) in enumerate(pairs):
        bar_h = 0 if not count else max(4, (height - 36) * count / peak)
        x = gap + index * (bar_w + gap)
        y = height - 24 - bar_h
        parts.append(f'<rect x="{x:.1f}" y="{y:.1f}" width="{bar_w:.1f}" height="{bar_h:.1f}" rx="3" fill="#1d4e89"/>')
        if count:
            parts.append(f'<text x="{x + bar_w / 2:.1f}" y="{y - 4:.1f}" text-anchor="middle" font-size="11">{count}</text>')
        if len(pairs) <= 16 or index % 2 == 0:
            parts.append(f'<text x="{x + bar_w / 2:.1f}" y="{height - 6}" text-anchor="middle" font-size="10">{esc(label)}</text>')
    parts.append("</svg>")
    return "".join(parts)


def period_bounds(query):
    params = urllib.parse.parse_qs(query or "")
    now = datetime.now(MSK)
    preset = clean(params.get("preset", ["month"])[0], 20) or "month"
    start_text = clean(params.get("from", [""])[0], 10)
    end_text = clean(params.get("to", [""])[0], 10)
    if start_text and end_text:
        try:
            start = datetime.fromisoformat(start_text).replace(tzinfo=MSK)
            end = datetime.fromisoformat(end_text).replace(hour=23, minute=59, tzinfo=MSK)
            return start, end, "custom", start_text, end_text
        except ValueError:
            pass
    if preset == "day":
        start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    elif preset == "week":
        start = (now - timedelta(days=6)).replace(hour=0, minute=0, second=0, microsecond=0)
    elif preset == "all":
        start = datetime(2026, 1, 1, tzinfo=MSK)
    else:
        preset = "month"
        start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    return start, now, preset, start.date().isoformat(), now.date().isoformat()


def in_period(moment, start, end):
    return bool(moment and start <= moment <= end)


def tally(rows, key_of):
    counts = {}
    for row in rows:
        key = key_of(row) or "не указан"
        counts[key] = counts.get(key, 0) + 1
    return sorted(counts.items(), key=lambda item: item[1], reverse=True)


def period_switch(base, preset, start_text, end_text):
    links = []
    for key, label in (("day", "День"), ("week", "Неделя"), ("month", "Месяц"), ("all", "Всё время")):
        cls = "btn" if preset == key else "btn line"
        links.append(f'<a class="{cls}" href="{base}?preset={key}">{label}</a>')
    return f"""
    <form class="filters" method="get" action="{base}">
      {"".join(links)}
      <input type="date" name="from" value="{esc(start_text)}" aria-label="С">
      <input type="date" name="to" value="{esc(end_text)}" aria-label="По">
      <button class="btn navy" type="submit">Период</button>
    </form>"""


def external_json(method, url, payload=None, headers=None):
    data = None if payload is None else payload if isinstance(payload, bytes) else json.dumps(payload).encode()
    request = urllib.request.Request(url, data=data, method=method, headers=headers or {})
    with urllib.request.urlopen(request, timeout=20) as response:
        return json.loads(response.read().decode())


def vk_access_token():
    cached = os.environ.get("VK_ADS_TOKEN", "").strip()
    expires = float(os.environ.get("VK_ADS_TOKEN_UNTIL", "0") or "0")
    if cached and expires > time.time() + 120:
        return cached
    client_id = os.environ.get("VK_ADS_CLIENT_ID", "").strip()
    client_secret = os.environ.get("VK_ADS_CLIENT_SECRET", "").strip()
    if not client_id or not client_secret:
        return cached
    body = urllib.parse.urlencode({
        "grant_type": "client_credentials",
        "client_id": client_id,
        "client_secret": client_secret,
    }).encode()
    found = external_json(
        "POST",
        "https://ads.vk.com/api/v2/oauth2/token.json",
        body,
        {"Content-Type": "application/x-www-form-urlencoded", "Accept": "application/json"},
    )
    token = found.get("access_token", "")
    if token:
        os.environ["VK_ADS_TOKEN"] = token
        os.environ["VK_ADS_TOKEN_UNTIL"] = str(time.time() + int(found.get("expires_in") or 3600))
    return token


def vk_report(start, end):
    token = ""
    try:
        token = vk_access_token()
    except Exception as error:
        return {"ok": False, "error": clean(error, 180)}
    if not token:
        return {"ok": False, "error": "нет ключа кабинета"}
    cache_key = f"{start.date().isoformat()}:{end.date().isoformat()}"
    if VK_CACHE.exists() and time.time() - VK_CACHE.stat().st_mtime < 900:
        cached = json.loads(VK_CACHE.read_text(encoding="utf-8"))
        if cached.get("key") == cache_key and cached.get("ok"):
            return cached
    headers = {"Authorization": "Bearer " + token, "Accept": "application/json"}
    plans = external_json("GET", "https://ads.vk.com/api/v2/ad_plans.json?limit=100", headers=headers)
    items = plans.get("items") if isinstance(plans, dict) else plans
    ids = [str(item.get("id")) for item in (items or []) if item.get("id")][:50]
    names = {str(item.get("id")): item.get("name") or str(item.get("id")) for item in (items or [])}
    if not ids:
        report = {"ok": True, "key": cache_key, "shows": 0, "clicks": 0, "spent": 0, "campaigns": [], "days": []}
        VK_CACHE.write_text(json.dumps(report, ensure_ascii=False), encoding="utf-8")
        return report
    query = urllib.parse.urlencode({
        "id": ",".join(ids),
        "date_from": start.date().isoformat(),
        "date_to": end.date().isoformat(),
        "metrics": "base",
    })
    try:
        stats = external_json("GET", "https://ads.vk.com/api/v2/statistics/ad_plans/day.json?" + query, headers=headers)
    except urllib.error.HTTPError:
        stats = external_json("GET", "https://ads.vk.com/api/v2/statistics/campaigns/day.json?" + query, headers=headers)
    shows = clicks = 0
    spent = 0.0
    days = {}
    campaigns = []
    for item in stats.get("items") or []:
        total = ((item.get("total") or {}).get("base") or {})
        item_shows = int(total.get("shows") or 0)
        item_clicks = int(total.get("clicks") or 0)
        item_spent = float(total.get("spent") or 0)
        shows += item_shows
        clicks += item_clicks
        spent += item_spent
        campaigns.append((names.get(str(item.get("id")), str(item.get("id"))), item_clicks, round(item_spent, 2)))
        for row in item.get("rows") or []:
            base = row.get("base") or {}
            day = row.get("date", "")[5:]
            bucket = days.setdefault(day, {"shows": 0, "clicks": 0})
            bucket["shows"] += int(base.get("shows") or 0)
            bucket["clicks"] += int(base.get("clicks") or 0)
    day_pairs = sorted(days.items())
    report = {
        "ok": True,
        "key": cache_key,
        "shows": shows,
        "clicks": clicks,
        "spent": round(spent, 2),
        "ctr": round(clicks / shows * 100, 2) if shows else 0,
        "campaigns": sorted(campaigns, key=lambda item: item[1], reverse=True)[:8],
        "days": [[day, bucket["clicks"]] for day, bucket in day_pairs],
    }
    DATA.mkdir(parents=True, exist_ok=True)
    VK_CACHE.write_text(json.dumps(report, ensure_ascii=False), encoding="utf-8")
    return report


def metrika_report(start, end):
    token = os.environ.get("YANDEX_METRIKA_TOKEN", "").strip()
    counter = os.environ.get("YANDEX_METRIKA_COUNTER", "").strip()
    if not token or not counter:
        return {"ok": False, "error": "нужны номер счётчика и токен Метрики"}
    query = urllib.parse.urlencode({
        "ids": counter,
        "metrics": "ym:s:visits,ym:s:users,ym:s:pageviews",
        "dimensions": "ym:s:date",
        "date1": start.date().isoformat(),
        "date2": end.date().isoformat(),
        "limit": 100,
    })
    try:
        found = external_json(
            "GET",
            "https://api-metrika.yandex.net/stat/v1/data?" + query,
            headers={"Authorization": "OAuth " + token, "Accept": "application/json"},
        )
    except Exception as error:
        return {"ok": False, "error": clean(error, 180)}
    totals = found.get("totals") or [0, 0, 0]
    days = []
    for row in found.get("data") or []:
        dims = row.get("dimensions") or [{}]
        metrics = row.get("metrics") or [0]
        name = (dims[0] or {}).get("name") or ""
        days.append((name[8:10] + "." + name[5:7] if len(name) >= 10 else name, int(metrics[0] or 0)))
    return {
        "ok": True,
        "visits": int(totals[0] or 0),
        "users": int(totals[1] or 0),
        "pageviews": int(totals[2] or 0),
        "days": days,
    }


def filtered_leads(start, end):
    rows = []
    for lead in read_leads():
        moment = parse_time(lead.get("created"))
        if in_period(moment, start, end):
            rows.append((moment, lead))
    return rows


def day_counts(rows, start, end):
    days = []
    cursor = start.date()
    last = end.date()
    while cursor <= last and len(days) < 62:
        label = cursor.strftime("%d.%m")
        days.append((label, sum(1 for moment, _ in rows if moment.date() == cursor)))
        cursor += timedelta(days=1)
    return days


def analytics_html(query=""):
    try:
        if not SNAPSHOT.exists() or time.time() - SNAPSHOT.stat().st_mtime > 90:
            sync_yougile()
    except Exception:
        pass
    start, end, preset, start_text, end_text = period_bounds(query)
    moments = filtered_leads(start, end)
    leads = [lead for _, lead in moments]
    days = day_counts(moments, start, end)
    sources = tally(leads, lambda lead: (lead.get("utm") or {}).get("utm_source") or "сайт")
    campaigns = tally(leads, lambda lead: (lead.get("utm") or {}).get("utm_campaign") or "")
    campaigns = [item for item in campaigns if item[0] != "не указан"][:8]
    cities = tally(leads, lambda lead: lead.get("city") or (lead.get("geo") or {}).get("city"))
    regions = tally(leads, lambda lead: lead.get("region"))
    vk_leads = sum(1 for lead in leads if "vk" in ((lead.get("utm") or {}).get("utm_source") or "").lower())
    snapshot = json.loads(SNAPSHOT.read_text(encoding="utf-8")) if SNAPSHOT.exists() else {}
    funnel_counts = {name: 0 for name in FUNNEL}
    for item in snapshot.values():
        title = item.get("column") or "Другое"
        funnel_counts[title] = funnel_counts.get(title, 0) + 1
    funnel_pairs = [(name, funnel_counts.get(name, 0)) for name in FUNNEL]
    moves = [event for event in read_events() if event.get("type") == "move"]
    period_moves = []
    for event in moves:
        moment = parse_time(event.get("at"))
        if in_period(moment, start, end):
            period_moves.append(event)
    move_html = "".join(
        f'<article class="move"><strong>{esc(event.get("title") or "Заявка")}</strong><p class="muted">{esc(event.get("at"))}: {esc(event.get("from") or "—")} → {esc(event.get("to") or "—")}</p></article>'
        for event in reversed(period_moves[-12:])
    ) or "<p class=\"muted\">Перемещений за период не было.</p>"
    try:
        ads = vk_report(start, end)
    except Exception as error:
        ads = {"ok": False, "error": clean(error, 180)}
    if ads.get("ok"):
        cpl = round(ads["spent"] / len(leads), 2) if leads and ads.get("spent") else 0
        vk_block = f"""
        <div class="stat-grid">
          <article class="stat"><span>Показы</span><b>{ads['shows']}</b></article>
          <article class="stat"><span>Клики</span><b>{ads['clicks']}</b></article>
          <article class="stat"><span>CTR</span><b>{ads['ctr']}%</b></article>
          <article class="stat"><span>Расход, ₽</span><b>{ads['spent']}</b></article>
        </div>
        <p>Заявок с меткой vk за период: <strong>{vk_leads}</strong>. Цена заявки по расходу кабинета: <strong>{cpl} ₽</strong>.</p>
        <div class="chart-card">{svg_columns([(label, count) for label, count in ads.get('days') or []])}</div>
        <div class="bars">{bar_rows([(name, clicks) for name, clicks, _spent in ads.get('campaigns') or []])}</div>"""
    else:
        vk_block = f"<p>Кабинет ВКонтакте: {esc(ads.get('error') or 'нет данных')}. Заявок с меткой vk за период: <strong>{vk_leads}</strong>.</p>"
    try:
        metrika = metrika_report(start, end)
    except Exception as error:
        metrika = {"ok": False, "error": clean(error, 180)}
    if metrika.get("ok"):
        metrika_block = f"<p>Визиты {metrika['visits']}, посетители {metrika['users']}, просмотры {metrika['pageviews']}.</p><div class=\"chart-card\">{svg_columns(metrika['days'])}</div>"
    else:
        metrika_block = f"<p>Яндекс Метрика пока не подключена: {esc(metrika.get('error') or 'нет токена')}. Посещения сайта ниже считаются самим сайтом.</p>"
    return f"""
    {panel_nav("analytics")}
    <p class="eyebrow">Сквозная аналитика</p>
    <h1>Заявки, реклама и воронка</h1>
    {period_switch("/panel/analytics", preset, start_text, end_text)}
    <div class="stat-grid">
      <article class="stat"><span>Заявки</span><b>{len(leads)}</b></article>
      <article class="stat"><span>Городов</span><b>{len([item for item in cities if item[0] != 'не указан'])}</b></article>
      <article class="stat"><span>Источников</span><b>{len(sources)}</b></article>
      <article class="stat"><span>Переходы воронки</span><b>{len(period_moves)}</b></article>
    </div>
    <section class="card chart-card"><h2>Заявки по дням</h2>{svg_columns(days)}</section>
    <div class="grid-2" style="margin-top:16px">
      <section class="card"><h2>Источники</h2><div class="bars">{bar_rows(sources[:8])}</div></section>
      <section class="card"><h2>Города</h2><div class="bars">{bar_rows(cities[:8])}</div></section>
    </div>
    <div class="grid-2" style="margin-top:16px">
      <section class="card"><h2>Регионы</h2><div class="bars">{bar_rows(regions[:8])}</div></section>
      <section class="card"><h2>Кампании из ссылок</h2><div class="bars">{bar_rows(campaigns)}</div></section>
    </div>
    <section class="card" style="margin-top:16px">
      <h2>Воронка YouGile</h2>
      <p class="muted">Доска «сайт народпобедителей». Счётчик колонок — текущее положение карточек. Переходы ниже — за выбранный период.</p>
      <div class="funnel">{bar_rows(funnel_pairs)}</div>
      <h3>Переходы</h3>
      <div class="moves">{move_html}</div>
    </section>
    <section class="card" style="margin-top:16px"><h2>Реклама ВКонтакте</h2>{vk_block}</section>
    <section class="card" style="margin-top:16px"><h2>Яндекс Метрика</h2>{metrika_block}</section>
    <form method="post" action="/panel/report?from={esc(start_text)}&to={esc(end_text)}"><button class="btn navy" type="submit">Сохранить отчёт за период</button></form>
    """


def site_html(query=""):
    start, end, preset, start_text, end_text = period_bounds(query)
    hits = []
    for hit in read_jsonl(HITS_LOG):
        moment = parse_time(hit.get("at"))
        if in_period(moment, start, end):
            hits.append((moment, hit))
    pages = tally([hit for _, hit in hits], lambda hit: hit.get("path") or "/")
    refs = tally([hit for _, hit in hits], lambda hit: hit.get("ref") or "прямой заход")
    sources = tally([hit for _, hit in hits], lambda hit: hit.get("source") or "без метки")
    devices = tally([hit for _, hit in hits], lambda hit: hit.get("device") or "неизвестно")
    return f"""
    {panel_nav("site")}
    <p class="eyebrow">Сайт</p>
    <h1>Кто открывает страницы</h1>
    <p class="muted">Считаем свой журнал визитов: страница, сайт-источник, метка и телефон или компьютер. IP и имя сюда не пишем. Яндекс Метрика добавится в сквозную аналитику, когда будут номер счётчика и токен.</p>
    {period_switch("/panel/site", preset, start_text, end_text)}
    <div class="stat-grid">
      <article class="stat"><span>Просмотры</span><b>{len(hits)}</b></article>
      <article class="stat"><span>Страниц</span><b>{len(pages)}</b></article>
      <article class="stat"><span>Источников</span><b>{len(refs)}</b></article>
      <article class="stat"><span>С меткой</span><b>{sum(count for name, count in sources if name != 'без метки')}</b></article>
    </div>
    <section class="card chart-card"><h2>Просмотры по дням</h2>{svg_columns(day_counts(hits, start, end))}</section>
    <div class="grid-2" style="margin-top:16px">
      <section class="card"><h2>Страницы</h2><div class="bars">{bar_rows(pages[:10])}</div></section>
      <section class="card"><h2>Откуда пришли</h2><div class="bars">{bar_rows(refs[:8])}</div></section>
    </div>
    <div class="grid-2" style="margin-top:16px">
      <section class="card"><h2>Метки</h2><div class="bars">{bar_rows(sources[:8])}</div></section>
      <section class="card"><h2>Устройства</h2><div class="bars">{bar_rows(devices)}</div></section>
    </div>"""


def reports_html():
    rows = read_jsonl(REPORTS)
    cards = []
    for report in reversed(rows[-30:]):
        cards.append(
            f"""<article class="card"><h3>{esc(report.get('title') or 'Отчёт')}</h3>
            <p class="muted">{esc(report.get('saved'))} · {esc(report.get('start'))} — {esc(report.get('end'))}</p>
            <p>Заявки: <strong>{esc(report.get('leads'))}</strong> · Просмотры: <strong>{esc(report.get('hits'))}</strong> · Клики VK: <strong>{esc(report.get('vk_clicks') or 0)}</strong> · Расход: <strong>{esc(report.get('vk_spent') or 0)} ₽</strong></p></article>"""
        )
    listing = "".join(cards) or "<p class=\"muted\">Сохранённых отчётов ещё нет. На сквозной аналитике нажмите «Сохранить отчёт за период».</p>"
    return f"""
    {panel_nav("reports")}
    <p class="eyebrow">Отчёты</p>
    <h1>История периодов</h1>
    <p class="muted">Каждое сохранение фиксирует цифры на этот момент. Сырые заявки и просмотры остаются в базе и после этого.</p>
    <div class="lead-list">{listing}</div>"""


def panel_nav(active):
    items = [
        ("leads", "/panel/", "Заявки"),
        ("analytics", "/panel/analytics", "Сквозная"),
        ("reports", "/panel/reports", "Отчёты"),
        ("site", "/panel/site", "Сайт"),
    ]
    links = []
    for key, href, label in items:
        cls = "btn" if key == active else "btn line"
        links.append(f'<a class="{cls}" href="{href}">{label}</a>')
    links.append('<a class="btn line" href="/panel/logout">Выйти</a>')
    return '<nav class="panel-nav">' + "".join(links) + "</nav>"


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
  <link rel="icon" href="/favicon.png" type="image/png">
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
        if route == "/panel/analytics":
            self.send_html(page("Сквозная аналитика", analytics_html(parsed.query)))
            return
        if route == "/panel/reports":
            self.send_html(page("Отчёты", reports_html()))
            return
        if route == "/panel/site":
            self.send_html(page("Сайт", site_html(parsed.query)))
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
        if route == "/api/hit":
            self.create_hit(raw)
            return
        if route == "/panel/report":
            if not self.authorized():
                self.send_json(401, {"error": "Нет доступа"})
                return
            self.save_report()
            return
        if route == "/api/yougile":
            self.yougile_hook(parsed.query)
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
        citizenship = clean(payload.get("citizenship"), 80)
        if citizenship == "Другое":
            other = clean(payload.get("citizenship_other"), 80)
            if len(other) < 2:
                self.send_json(400, {"error": "Напишите своё гражданство"})
                return
            citizenship = "Другое: " + other
        try:
            age_years = int(clean(payload.get("age_years"), 3))
        except ValueError:
            age_years = 0
        lead = {
            "name": clean(payload.get("name"), 80),
            "phone": clean(payload.get("phone"), 20),
            "city": clean(payload.get("city"), 80),
            "region": clean(payload.get("region"), 80),
            "age_years": str(age_years) if age_years else "",
            "citizenship": citizenship,
            "profession": clean(payload.get("profession"), 160),
            "direction": clean(payload.get("direction"), 80),
            "status": clean(payload.get("status"), 120),
            "message": clean(payload.get("message"), 2000),
            "ads": "yes" if payload.get("ads") == "yes" else "no",
            "page": clean(payload.get("page"), 120),
            "referrer": clean(payload.get("referrer"), 240),
        }
        digits = re.sub(r"\D", "", lead["phone"])
        if len(lead["name"]) < 2:
            self.send_json(400, {"error": "Укажите имя"})
            return
        if len(digits) < 10:
            self.send_json(400, {"error": "Укажите телефон"})
            return
        if len(lead["city"]) < 2 or len(lead["region"]) < 2:
            self.send_json(400, {"error": "Укажите город и регион"})
            return
        if age_years < 18 or age_years > 80:
            self.send_json(400, {"error": "Заявку принимаем с 18 лет"})
            return
        base_citizenship = citizenship.split(":", 1)[0]
        if base_citizenship not in CITIZENSHIP:
            self.send_json(400, {"error": "Выберите гражданство"})
            return
        if len(lead["profession"]) < 2 or not lead["direction"]:
            self.send_json(400, {"error": "Укажите профессию и направление"})
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
        source = (record.get("utm") or {}).get("utm_source") or "сайт"
        append_event({
            "type": "lead",
            "name": record["name"],
            "city": record["city"],
            "source": source,
            "campaign": (record.get("utm") or {}).get("utm_campaign", ""),
        })
        self.send_json(200, {"ok": True})

    def create_hit(self, raw):
        ip = client_ip(self.headers)
        if limited(HITS, "hit:" + ip, 80, 60):
            self.send_json(429, {"error": "Слишком часто"})
            return
        try:
            payload = json.loads(raw.decode())
        except (UnicodeDecodeError, json.JSONDecodeError):
            self.send_json(400, {"error": "Некорректный просмотр"})
            return
        utm = payload.get("utm") if isinstance(payload.get("utm"), dict) else {}
        record = {
            "at": datetime.now(MSK).isoformat(timespec="minutes"),
            "path": clean(payload.get("path"), 120) or "/",
            "ref": clean(payload.get("ref"), 120),
            "source": clean(utm.get("utm_source"), 80),
            "campaign": clean(utm.get("utm_campaign"), 120),
            "device": clean(payload.get("device"), 20),
        }
        append_jsonl(HITS_LOG, record)
        self.send_json(200, {"ok": True})

    def save_report(self):
        parsed = urllib.parse.urlparse(self.path)
        start, end, _preset, start_text, end_text = period_bounds(parsed.query)
        hits = [hit for hit in read_jsonl(HITS_LOG) if in_period(parse_time(hit.get("at")), start, end)]
        try:
            ads = vk_report(start, end)
        except Exception:
            ads = {}
        append_jsonl(REPORTS, {
            "saved": datetime.now(MSK).isoformat(timespec="minutes"),
            "title": f"Отчёт {start_text} — {end_text}",
            "start": start_text,
            "end": end_text,
            "leads": len(filtered_leads(start, end)),
            "hits": len(hits),
            "vk_clicks": ads.get("clicks") or 0,
            "vk_shows": ads.get("shows") or 0,
            "vk_spent": ads.get("spent") or 0,
        })
        self.redirect("/panel/reports")

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

    def yougile_hook(self, query):
        token = urllib.parse.parse_qs(query).get("token", [""])[0]
        expected = os.environ.get("YOUGILE_WEBHOOK_TOKEN", "")
        if not expected or not hmac.compare_digest(token, expected):
            self.send_json(403, {"error": "Нет доступа"})
            return
        threading.Thread(target=self._sync_safe, daemon=True).start()
        self.send_json(200, {"ok": True})

    @staticmethod
    def _sync_safe():
        try:
            sync_yougile()
        except Exception:
            pass

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
        writer.writerow(["время", "имя", "телефон", "город", "регион", "возраст", "гражданство", "профессия", "направление", "ситуация", "комментарий", "рассылка", "гео", "метки", "yougile"])
        for lead in reversed(read_leads()):
            writer.writerow([
                lead.get("created", ""),
                lead.get("name", ""),
                lead.get("phone", ""),
                lead.get("city", ""),
                lead.get("region", ""),
                lead.get("age_years", ""),
                lead.get("citizenship", ""),
                lead.get("profession", ""),
                lead.get("direction", ""),
                lead.get("status", ""),
                lead.get("message", ""),
                lead.get("ads", ""),
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
              <p>{esc(row.get("city") or "город не указан")} · {esc(row.get("region") or "регион не указан")} · {esc(row.get("age_years") or "возраст не указан")}</p>
              <p>{esc(row.get("citizenship"))}</p>
              <p>{esc(row.get("profession") or "")} · {esc(row.get("direction") or "")}</p>
              <p>{esc(row.get("status") or "")}</p>
              <p>{esc(row.get("message") or "")}</p>
              <p class="muted">Гео: {esc(format_geo(row.get("geo")))}<br>Метки: {esc(json.dumps(row.get("utm") or {}, ensure_ascii=False))}<br>YouGile: {esc(json.dumps(row.get("yougile") or {}, ensure_ascii=False))}</p>
            </article>"""
        )
    listing = "".join(cards) or "<p>Заявок пока нет.</p>"
    return f"""
    {panel_nav("leads")}
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
    threading.Thread(target=sync_loop, daemon=True).start()
    ThreadingHTTPServer((HOST, PORT), Handler).serve_forever()


if __name__ == "__main__":
    main()
