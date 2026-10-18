#!/usr/bin/env python3
"""Assemble static pages from src/pages into public/."""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PAGES = ROOT / "src" / "pages"
PUBLIC = ROOT / "public"
HOST = "https://народпобедителей.рф"

NAV = [
    ("index.html", "Главная", "index"),
    ("uslugi.html", "Услуги", "uslugi"),
    ("dokumenty.html", "Документы", "dokumenty"),
    ("vyplaty.html", "Выплаты", "vyplaty"),
    ("specialnosti.html", "Специальности", "specialnosti"),
    ("komu.html", "Кому помогаем", "komu"),
    ("kontakty.html", "Контакты", "kontakty"),
]

SOCIALS = [
    ("tg", "Telegram", "https://t.me/bpla18", "Telegram bpla18"),
    ("tg", "Канал", "https://t.me/vsrfbpla", "Telegram vsrfbpla"),
    ("max", "MAX группа", "https://max.ru/join/FkWU8D4RliZazVMtRS_w7mKd61wj3X384I2Ccv3FSYE", "MAX группа"),
    ("max", "MAX профиль", "https://max.ru/u/f9LHodD0cOLNfNulDMTQ8_wO_mdHdJJK4nOdIltbjQdNDetWWXIFxIFVhbg", "MAX профиль"),
    ("vk", "ВКонтакте", "https://vk.ru/bpla18", "ВКонтакте bpla18"),
    ("vk", "Группа", "https://vk.ru/club241184153", "ВКонтакте группа"),
    ("ok", "ОК", "https://ok.ru/profile/910612967253", "Одноклассники"),
    ("wa", "WhatsApp", "https://wa.me/qr/PZW3MWIV37OXL1", "WhatsApp"),
]

ICONS = {
    "tg": '<svg viewBox="0 0 24 24" aria-hidden="true"><circle cx="12" cy="12" r="12" fill="#1d4e89"/><path fill="#fff" d="M17.6 7.3 15.7 16c-.1.6-.5.8-1 .5l-2.8-2.1-1.3 1.3c-.2.1-.3.3-.3.5l.2-2.9 5.3-4.8c.2-.2 0-.3-.3-.1l-6.6 4.1-2.8-.9c-.6-.2-.6-.6.1-.9l11-4.2c.5-.2 1 .1.8.8Z"/></svg>',
    "vk": '<svg viewBox="0 0 24 24" aria-hidden="true"><circle cx="12" cy="12" r="12" fill="#1d4e89"/><path fill="#fff" d="M12.6 16.4h.8s.2 0 .4-.2c.1-.2.1-.4 0-.6 0-.1-.3-.8-.9-1.5-.5-.6-.4-.5.2-1.5.3-.5.7-1.1.9-1.4.1-.3 0-.5-.3-.5h-1.2c-.2 0-.4.1-.4.3 0 .3-.5 1.2-.9 1.9-.4.6-.6.6-.7.6-.2 0-.3-.1-.3-.5V9.8c0-.4-.1-.5-.4-.5H9.2c-.2 0-.4.2-.4.3 0 .4.5.5.6 1.5v1.8c0 .4 0 .5-.2.5-.6 0-1.9-2-2-2.1-.1-.2-.2-.3-.5-.3H5.6c-.3 0-.4.2-.4.3 0 .3.6 1.8 2.6 3.8 1.4 1.4 3.2 1.5 3.2 1.5Z"/></svg>',
    "ok": '<svg viewBox="0 0 24 24" aria-hidden="true"><circle cx="12" cy="12" r="12" fill="#1f6b45"/><circle cx="12" cy="9" r="2.2" fill="none" stroke="#fff" stroke-width="1.6"/><path fill="none" stroke="#fff" stroke-width="1.6" d="M8.2 13.2c1 .9 2.3 1.4 3.8 1.4s2.8-.5 3.8-1.4M12 14.6v2.2M9.4 18.4l2.6-1.6 2.6 1.6"/></svg>',
    "wa": '<svg viewBox="0 0 24 24" aria-hidden="true"><circle cx="12" cy="12" r="12" fill="#1f6b45"/><path fill="#fff" d="M12 6.2a5.7 5.7 0 0 0-4.9 8.6L6.6 17.4l2.7-.7A5.7 5.7 0 1 0 12 6.2Zm3.3 8.1c-.1.4-.8.7-1.1.7-.3.1-1.2.2-2.1-.4-.7-.5-1.4-1.2-1.9-2-.3-.5-.1-1 .2-1.2l.4-.4c.1-.1.1-.3 0-.4l-.6-1.4c-.1-.3-.3-.3-.5-.3h-.4c-.2 0-.5.1-.6.4-.3.6-.1 1.6.6 2.5.8 1.1 1.9 1.8 3.2 2.2.5.1 1 .1 1.3-.1.2-.2.4-.5.4-.7 0-.1 0-.3-.1-.3l-.8-.4Z"/></svg>',
    "max": '<svg viewBox="0 0 24 24" aria-hidden="true"><circle cx="12" cy="12" r="12" fill="#b4232c"/><path fill="#fff" d="M6.8 16.2 12 6.4h1.7l5.2 9.8h-1.8l-1.2-2.4H9.9l-1.2 2.4H6.8Zm3.6-3.8h3.9L12.4 8.8 10.4 12.4Z"/></svg>',
}


def socials(compact=False):
    items = SOCIALS[:4] if compact else SOCIALS
    links = []
    for key, label, href, title in items:
        links.append(
            f'<a href="{href}" target="_blank" rel="noopener noreferrer" title="{title}">{ICONS[key]}<span>{label}</span></a>'
        )
    return '<div class="socials">' + "".join(links) + "</div>"


FORM = """
<form class="lead-form form" method="post" action="/api/lead">
  <div>
    <p class="eyebrow">Заявка</p>
    <h2>Оставить обращение</h2>
    <p class="muted">Принимаем круглосуточно. Обработка идёт по мере работы, без обещания перезвонить в ту же минуту.</p>
  </div>
  <label>Имя<input name="name" autocomplete="name" required maxlength="80"></label>
  <label>Телефон<input name="phone" autocomplete="tel" inputmode="tel" required maxlength="20" placeholder="+7"></label>
  <label>Город<input name="city" autocomplete="address-level2" maxlength="80"></label>
  <label>Гражданство
    <select name="citizenship" required>
      <option value="">Выберите</option>
      <option>Гражданин РФ</option>
      <option>Узбекистан</option>
      <option>Таджикистан</option>
      <option>Кыргызстан</option>
      <option>Казахстан</option>
      <option>Армения</option>
      <option>Молдова</option>
      <option>Другая страна СНГ</option>
      <option>Индия</option>
      <option>Страна Африки</option>
      <option>Страна Ближнего Востока</option>
      <option>Другое</option>
    </select>
  </label>
  <label>Ваша ситуация
    <select name="status">
      <option value="">Необязательно</option>
      <option>Рассматриваю службу по контракту</option>
      <option>Уже служу и нужен совет</option>
      <option>Офицер запаса или комиссован</option>
      <option>Есть опыт службы в частной военной компании</option>
      <option>Обращаюсь как член семьи</option>
    </select>
  </label>
  <label>Комментарий<textarea name="message" maxlength="2000" placeholder="Город, вопрос и удобное время для связи"></textarea></label>
  <label class="check"><input type="checkbox" name="age" value="yes" required><span>Мне есть 18 лет. Сайт не для несовершеннолетних.</span></label>
  <label class="check"><input type="checkbox" name="consent" value="yes" required><span>Даю <a href="/soglasie.html">согласие</a> на обработку персональных данных и принимаю <a href="/politika.html">политику конфиденциальности</a>.</span></label>
  <div class="hp" aria-hidden="true"><label>Сайт<input name="website" tabindex="-1" autocomplete="off"></label></div>
  <button class="btn" type="submit">Отправить заявку</button>
  <p class="form-status" role="status"></p>
</form>
"""


def meta_of(text):
    meta = {"title": "Народ победителей", "description": "", "nav": ""}
    body = []
    for line in text.splitlines():
        if line.startswith("<!--TITLE:"):
            meta["title"] = line.removeprefix("<!--TITLE:").removesuffix("-->").strip()
        elif line.startswith("<!--DESC:"):
            meta["description"] = line.removeprefix("<!--DESC:").removesuffix("-->").strip()
        elif line.startswith("<!--NAV:"):
            meta["nav"] = line.removeprefix("<!--NAV:").removesuffix("-->").strip()
        else:
            body.append(line)
    return meta, "\n".join(body).strip().replace("{{FORM}}", FORM).replace("{{SOCIALS}}", socials())


def chrome(meta, body, path):
    nav_links = []
    for href, label, key in NAV:
        current = ' aria-current="page"' if key == meta["nav"] else ""
        nav_links.append(f'<a href="/{href}"{current}>{label}</a>')
    canonical = HOST + "/" if path == "index.html" else f"{HOST}/{path}"
    return f"""<!DOCTYPE html>
<html lang="ru">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{meta["title"]}</title>
  <meta name="description" content="{meta["description"]}">
  <meta name="rating" content="adult">
  <link rel="canonical" href="{canonical}">
  <link rel="icon" href="/img/logo.svg" type="image/svg+xml">
  <meta property="og:title" content="{meta["title"]}">
  <meta property="og:description" content="{meta["description"]}">
  <meta property="og:type" content="website">
  <meta property="og:url" content="{canonical}">
  <meta property="og:locale" content="ru_RU">
  <link rel="stylesheet" href="/css/main.css">
</head>
<body>
  <div class="flag" aria-hidden="true"><span></span><span></span><span></span><span></span></div>
  <div class="topbar">
    <div class="wrap">
      <span><b class="age">18+</b> Реклама. Рекламодатель: ИП Шувалов Роман Альбертович, ИНН 503408651872</span>
      <a href="/rekvizity.html">Реквизиты</a>
    </div>
  </div>
  <header class="header">
    <div class="wrap head">
      <a class="logo" href="/">
        <img src="/img/logo.svg" width="46" height="52" alt="">
        <span><span class="logo-name">Народ победителей</span><small>военно-кадровое агентство</small></span>
      </a>
      <nav class="nav" id="nav" aria-label="Разделы">
        {"".join(nav_links)}
        {socials()}
      </nav>
      <div class="head-actions">
        <a class="phone-link" href="tel:+79163574362">+7 916 357-43-62</a>
        <a class="btn" href="/kontakty.html">Заявка</a>
        <button class="burger" id="burger" type="button" aria-expanded="false" aria-controls="nav" aria-label="Меню"><span></span><span></span><span></span></button>
      </div>
    </div>
    <div class="wrap social-strip">{socials(compact=True)}</div>
  </header>
  {body}
  <footer class="footer">
    <div class="wrap footer-grid">
      <div>
        <a class="logo" href="/"><img src="/img/logo.svg" width="46" height="52" alt=""><span><span class="logo-name">Народ победителей</span><small>ВКА</small></span></a>
        <p>Частное военно-кадровое агентство. Не являемся военкоматом, пунктом отбора или Министерством обороны.</p>
        {socials()}
      </div>
      <div>
        <h2>Разделы</h2>
        <p><a href="/uslugi.html">Услуги</a><br><a href="/dokumenty.html">Документы</a><br><a href="/vyplaty.html">Выплаты</a><br><a href="/specialnosti.html">Специальности</a><br><a href="/komu.html">Кому помогаем</a></p>
      </div>
      <div>
        <h2>Документы сайта</h2>
        <p><a href="/politika.html">Политика конфиденциальности</a><br><a href="/soglasie.html">Согласие на обработку данных</a><br><a href="/cookies.html">Файлы cookie и геолокация</a><br><a href="/oferta.html">Публичная оферта</a><br><a href="/rekvizity.html">Реквизиты</a></p>
      </div>
    </div>
    <div class="wrap legal-note">
      <p>ИП Шувалов Роман Альбертович · ИНН 503408651872 · ОГРНИП 326508100529586 от 08.09.2026<br>
      Юридический адрес: 142632, Московская область, г. Орехово-Зуево, д. Демихово, ул. Заводская, 27, 37<br>
      Офис для встреч: Москва, Фрунзенская наб., 22, стр. 4 · narodpobediteley@mail.ru · +7 916 357-43-62</p>
      <p>Реклама услуг частного агентства. Идентификатор рекламы (ERID) указывается в объявлениях рекламных систем, когда кабинет передаёт креатив в оператора рекламных данных. На сайте суммы выплат не публикуются: их назначают не мы.</p>
    </div>
  </footer>
  <div class="tabbar" aria-label="Быстрые действия">
    <a class="btn line" href="tel:+79163574362">Позвонить</a>
    <a class="btn line" href="https://t.me/bpla18">Telegram</a>
    <a class="btn" href="/kontakty.html">Заявка</a>
  </div>
  <aside class="cookie" id="cookie" aria-label="Файлы cookie">
    <p><strong>Cookie и город</strong></p>
    <p class="muted">Нужные данные храним, чтобы сайт открывался и заявка дошла. Город и регион определяем только с вашего разрешения: для подбора региональной информации и квалификации обращения. Точные координаты не сохраняем.</p>
    <div class="cookie-settings" id="cookie-settings">
      <label class="check"><input type="checkbox" checked disabled><span>Необходимые: заявка и запоминание этого выбора</span></label>
      <label class="check"><input id="opt-geo" type="checkbox"><span>Город и регион устройства</span></label>
      <label class="check"><input id="opt-ads" type="checkbox"><span>Рекламный пиксель ВКонтакте, когда он будет подключён</span></label>
    </div>
    <div class="row">
      <button class="btn line" type="button" data-consent="necessary">Только необходимые</button>
      <button class="btn green" type="button" data-consent="geo">Разрешить город</button>
      <button class="btn navy" type="button" data-consent="settings">Настроить</button>
      <button class="btn cookie-save" type="button" data-consent="custom">Сохранить выбор</button>
    </div>
    <p class="muted"><a href="/cookies.html">Подробнее о cookie</a></p>
  </aside>
  <script src="/js/main.js"></script>
</body>
</html>
"""


def main():
    written = []
    for src in sorted(PAGES.glob("*.html")):
        meta, body = meta_of(src.read_text(encoding="utf-8"))
        target = "index.html" if meta["nav"] == "index" else src.name
        (PUBLIC / target).write_text(chrome(meta, body, target), encoding="utf-8")
        written.append((target, meta))
    urls = [HOST + "/"] + [
        f"{HOST}/{name}" for name, meta in written if name not in {"index.html", "404.html"}
    ]
    sitemap = ['<?xml version="1.0" encoding="UTF-8"?>', '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">']
    for url in urls:
        sitemap.append(f"<url><loc>{url}</loc></url>")
    sitemap.append("</urlset>")
    (PUBLIC / "sitemap.xml").write_text("\n".join(sitemap) + "\n", encoding="utf-8")
    (PUBLIC / "robots.txt").write_text(
        "User-agent: *\nAllow: /\nDisallow: /panel/\nDisallow: /api/\nSitemap: https://народпобедителей.рф/sitemap.xml\n",
        encoding="utf-8",
    )
    stale = PUBLIC / "styles.css"
    if stale.exists():
        stale.unlink()
    print(f"built {len(written)} pages")


if __name__ == "__main__":
    main()
