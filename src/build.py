#!/usr/bin/env python3
"""Assemble static pages from src/pages into public/."""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PAGES = ROOT / "src" / "pages"
PUBLIC = ROOT / "public"
HOST = "https://народпобедителей.рф"

NAV = [
    ("index.html", "Главная", "index"),
    ("trebovaniya.html", "Требования", "trebovaniya"),
    ("vakansii.html", "Вакансии", "vakansii"),
    ("vyplaty.html", "Выплаты", "vyplaty"),
    ("semya.html", "Семья", "semya"),
    ("put.html", "Путь", "put"),
    ("voprosy.html", "Вопросы", "voprosy"),
    ("stati.html", "Статьи", "stati"),
    ("dokumenty.html", "Документы", "dokumenty"),
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
    "tg": "/img/icons/telegram.svg",
    "vk": "/img/icons/vk.svg",
    "ok": "/img/icons/odnoklassniki.svg",
    "wa": "/img/icons/whatsapp.svg",
    "max": "/img/icons/max.svg",
}


def socials(compact=False):
    items = SOCIALS[:4] if compact else SOCIALS
    links = []
    for key, label, href, title in items:
        links.append(
            f'<a href="{href}" target="_blank" rel="noopener noreferrer" title="{title}"><img src="{ICONS[key]}" width="22" height="22" alt=""><span>{label}</span></a>'
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
  <label>Город<input name="city" autocomplete="address-level2" maxlength="80" required></label>
  <label>Регион<input name="region" autocomplete="address-level1" maxlength="80" required placeholder="Область, край или республика"></label>
  <label>Возраст, полных лет<input name="age_years" type="number" inputmode="numeric" min="18" max="80" required></label>
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
  <label class="citizenship-other" hidden>Своё гражданство<input name="citizenship_other" maxlength="80" placeholder="Напишите страну или гражданство"></label>
  <label>Профессия и опыт<input name="profession" maxlength="160" required placeholder="Кем работали, какое образование"></label>
  <label>Куда хотели бы пойти
    <select name="direction" required>
      <option value="">Выберите</option>
      <option>Пока не знаю, нужна консультация</option>
      <option>Вождение и техника</option>
      <option>Связь</option>
      <option>Беспилотные системы</option>
      <option>Медицина</option>
      <option>Охрана и режим</option>
      <option>Штаб и обеспечение</option>
      <option>Другое направление</option>
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
  <label>Дополнительная информация<textarea name="message" maxlength="2000" placeholder="Что ещё важно: семья, сроки, удобное время для связи"></textarea></label>
  <label class="check"><input type="checkbox" name="age" value="yes" required><span>Мне есть 18 лет. Сайт не для несовершеннолетних.</span></label>
  <label class="check"><input type="checkbox" name="consent" value="yes" required><span>Даю <a href="/soglasie.html">согласие</a> на обработку персональных данных и принимаю <a href="/politika.html">политику</a> и <a href="/soglashenie.html">пользовательское соглашение</a>.</span></label>
  <label class="check"><input type="checkbox" name="ads" value="yes"><span>Согласен получать сообщения об услугах центра. Галочка не обязательна и не проставлена заранее.</span></label>
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
  <link rel="icon" href="/favicon.ico" sizes="any">
  <link rel="icon" href="/favicon.png" type="image/png" sizes="32x32">
  <link rel="apple-touch-icon" href="/apple-touch-icon.png">
  <meta property="og:image" content="{HOST}/img/logo.png">
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
        <img src="/img/logo.png" width="68" height="68" alt="">
        <span><span class="logo-name">Народ победителей</span><small>Добровольческий центр</small></span>
      </a>
      <nav class="nav" id="nav" aria-label="Разделы">
        {"".join(nav_links)}
        {socials()}
      </nav>
      <div class="head-actions">
        <span class="phones">
          <a class="phone-link" href="tel:+79163574362">+7 916 357-43-62</a>
          <a class="phone-link" href="tel:+79264262737">+7 926 426-27-37</a>
        </span>
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
        <a class="logo" href="/"><img src="/img/logo.png" width="68" height="68" alt=""><span><span class="logo-name">Народ победителей</span><small>Добровольческий центр</small></span></a>
        <p>Добровольческий центр «Народ победителей». Частный оператор: не военкомат, не пункт отбора и не подразделение Министерства обороны.</p>
        {socials()}
      </div>
      <div>
        <h2>Разделы</h2>
        <p><a href="/vakansii.html">Вакансии</a><br><a href="/otnoshenie.html">Отношение</a><br><a href="/stati.html">Статьи</a><br><a href="/voprosy.html">Вопросы</a><br><a href="/dokumenty.html">Документы</a><br><a href="/zakony.html">Законы</a><br><a href="/uslugi.html">Услуги</a></p>
      </div>
      <div>
        <h2>Документы сайта</h2>
        <p><a href="/politika.html">Политика конфиденциальности</a><br><a href="/soglasie.html">Согласие на обработку данных</a><br><a href="/soglashenie.html">Пользовательское соглашение</a><br><a href="/cookies.html">Файлы cookie</a><br><a href="/oferta.html">Публичная оферта</a><br><a href="/rekvizity.html">Реквизиты</a></p>
      </div>
    </div>
    <div class="wrap legal-note">
      <p>ИП Шувалов Роман Альбертович · ИНН 503408651872 · ОГРНИП 326508100529586 от 08.09.2026<br>
      Юридический адрес: 142632, Московская область, г. Орехово-Зуево, д. Демихово, ул. Заводская, 27, 37<br>
      Офис для встреч: Москва, Фрунзенская наб., 22, стр. 4 · narodpobediteley@mail.ru · +7 916 357-43-62 · +7 926 426-27-37</p>
      <p>Реклама услуг частного агентства. Идентификатор рекламы (ERID) указывается в объявлениях рекламных систем. Цифра «от 2 300 000 ₽» на главной — ориентир по открытым региональным программам, не оферта агентства и не гарантия выплаты.</p>
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
