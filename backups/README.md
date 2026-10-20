# Копия сайта для переноса

Каталог `backups/ГГГГ-ММ-ДД/` собирает скрипт `deploy/backup.sh`. В git попадает только эта инструкция: в архиве есть заявки и файл с паролями, их нельзя выкладывать в репозиторий.

Что лежит в копии на этом компьютере и на сервере в `/var/backups/narod/`:

- собранный сайт `public.tar.gz`
- программа панели `app.py`
- nginx и служба systemd
- `config.env` с ключами кабинетов
- `var-lib-narod.tar.gz` — заявки, просмотры, отчёты и снимок воронки

Новый сервер:

1. Поставить Ubuntu, nginx, certbot и каталоги `/opt/narod`, `/etc/narod`, `/var/lib/narod`, `/var/www/narod`.
2. Распаковать сайт в `/var/www/narod`, положить `app.py` в `/opt/narod/app.py`, вернуть `config.env`, nginx и systemd.
3. Запустить `deploy/deploy.sh` с новым адресом или распаковать архив вручную и выполнить `systemctl enable --now narod-leads`.
4. Выпустить сертификат на домен и проверить `https://народпобедителей.рф/api/health`.

Логотип отдельно: `brand/logo.png`, фавикон по звезде и крыльям `brand/favicon.png`. Прежние SVG оставлены в `brand/`.
