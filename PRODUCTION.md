# Развёртывание в production

Инструкция для Debian/Ubuntu: Nginx установлен на хосте, Django, Flask и Redis запускаются через Docker Compose **на той же машине**. Команды проекта выполняются из папки с `compose.yaml`.

## 1. Подготовка

Потребуются Docker Engine с плагином Compose, Python 3, Nginx и Certbot. Настройте DNS-запись домена на публичный IP сервера. Для HTTP-01 и работы сайта должны быть доступны TCP 80 и 443; за NAT пробросьте их на Nginx.

В примерах используется `wheel.example.com`. Замените его своим доменом во всех командах, `.env` и конфигурации Nginx. Если публикуете AAAA-запись, IPv6 тоже должен вести на работающий Nginx; IPv6-слушатели в примере можно раскомментировать.

Создайте конфигурацию приложения:

```bash
python3 setup_env.py
```

Скрипт генерирует секреты локально и добавляет недостающие параметры, сохраняя существующие. Настройте `.env`:

```dotenv
ALLOWED_HOSTS=wheel.example.com,localhost,127.0.0.1
CSRF_TRUSTED_ORIGINS=https://wheel.example.com
COOKIE_SECURE=true
TRUSTED_PROXY_CIDRS=
```

Сохраните `localhost` в ALLOWED_HOSTS: он нужен healthcheck. В ALLOWED_HOSTS пишутся имена без схемы и портов, в CSRF_TRUSTED_ORIGINS — origin со схемой.

| Секрет | Назначение |
| --- | --- |
| `WHEEL_ACCESS_TOKENS` | JSON-набор именованных токенов доступа |
| `WHEEL_ACCESS_TOKEN` | Токен, который вводят на странице входа |
| `API_TOKEN` | Внутренний доступ Django → Flask |
| `DJANGO_SECRET_KEY` | Секрет Django и ключ для служебных HMAC |
| `REDIS_PASSWORD` | Пароль Redis |


## 2. Запуск приложения

```bash
docker compose up -d --build
docker compose ps
curl http://127.0.0.1:8080/healthz
```

Ожидаемый ответ healthcheck — `{"status": "ok"}`. Он подтверждает работу Django, но не проверяет весь путь входа и розыгрыша.

Внешний порт приложения должен оставаться `127.0.0.1:8080:8000`. Flask и Redis наружу не публикуются. Для браузера в production используйте HTTPS-домен, а не этот HTTP-адрес: при COOKIE_SECURE=true cookie входа предназначены для HTTPS.

## 3. Первичное получение сертификата

Если подходящий сертификат уже существует, переходите к следующему разделу. Уточните фактические пути через `sudo certbot certificates`: имя каталога может отличаться, например иметь суффикс `-0001`.

Для нового сертификата сначала подключите **временный HTTP-конфиг** без SSL. Создайте каталог проверки:

```bash
sudo mkdir -p /var/www/letsencrypt
sudo nano /etc/nginx/sites-available/fortune.conf
```

Вставьте, заменив домен:

```nginx
server {
    listen 80;
    server_name wheel.example.com;

    location ^~ /.well-known/acme-challenge/ {
        root /var/www/letsencrypt;
        default_type text/plain;
        try_files $uri =404;
    }

    location / {
        return 404;
    }
}
```

Подключите файл, если ссылка ещё не создана:

```bash
sudo ln -s /etc/nginx/sites-available/fortune.conf /etc/nginx/sites-enabled/fortune.conf
sudo nginx -t
```

Если проверка успешна:

```bash
sudo systemctl reload nginx
sudo certbot certonly --webroot -w /var/www/letsencrypt -d wheel.example.com
```

Certbot запросит необходимые данные для выпуска. Не включайте итоговый SSL-конфиг, пока сертификат и ключ не появились: иначе `nginx -t` завершится ошибкой.

## 4. Постоянный конфиг Nginx

В [nginx.example.conf](nginx.example.conf) замените домен и пути сертификата, затем скопируйте файл вместо временного:

```bash
sudo cp nginx.example.conf /etc/nginx/sites-available/fortune.conf
sudo nginx -t
```

При успешной проверке:

```bash
sudo systemctl reload nginx
```

Файл должен подключаться внутри `http {}` в `/etc/nginx/nginx.conf`. В стандартной схеме Debian/Ubuntu это обеспечивает `include /etc/nginx/sites-enabled/*;`. Можно использовать и `conf.d/*.conf`, если этот include также находится внутри http, но не подключайте один конфиг обоими способами.

`limit_req_zone` объявляется вне server-блоков и только один раз для имени `fortune_edge`. Дополнительный блок `http {}` в файле сайта не нужен. Конфигурация включает редирект HTTP → HTTPS, исключение ACME для продления, лимит тела 256 KiB и внешний лимит 5 запросов/с на IP с burst=20.

Если этот домен уже обслуживается другим файлом Nginx, объедините настройки или отключите его дублирующий server-блок. Другие сайты сервера менять не требуется.

### Продление сертификата

Убедитесь, что установленный Certbot запускает автоматическое продление. Для пакета с systemd-таймером:

```bash
systemctl list-timers --all 'certbot*'
sudo certbot renew --dry-run
```

Чтобы Nginx подхватывал успешно обновлённые сертификаты, добавьте deploy-hook, если аналогичного ещё нет:

```bash
sudo mkdir -p /etc/letsencrypt/renewal-hooks/deploy
sudo tee /etc/letsencrypt/renewal-hooks/deploy/reload-nginx.sh >/dev/null <<'SH'
#!/bin/sh
nginx -t && systemctl reload nginx
SH
sudo chmod 755 /etc/letsencrypt/renewal-hooks/deploy/reload-nginx.sh
```

Webroot-проверка требует доступного HTTP-пути `/.well-known/acme-challenge/`. Этот путь уже предусмотрен итоговым конфигом.

## 5. Реальный IP посетителя за прокси

Django принимает X-Real-IP только от адресов в `TRUSTED_PROXY_CIDRS`. Без настройки лимиты сохраняются, но все посетители могут считаться одним адресом Docker-шлюза.

Откройте сайт через Nginx и посмотрите адрес непосредственного отправителя в access-логе Gunicorn:

```bash
docker compose logs --tail=30 frontend
```

Допустим, подтверждённый адрес — `172.20.0.1`. Укажите в `.env`:

```dotenv
TRUSTED_PROXY_CIDRS=172.20.0.1/32
```

Это пример: используйте фактический адрес. Не задавайте `0.0.0.0/0` и не доверяйте всей локальной сети. Примените:

```bash
docker compose up -d frontend
```

При пересоздании Docker-сети адрес шлюза может измениться. Nginx должен перезаписывать X-Real-IP, а порт 8080 не должен быть доступен посетителям напрямую.

Если Nginx находится на другой машине, замените upstream 127.0.0.1 на доступный ему LAN-адрес приложения, измените привязку порта Compose и разрешите доступ к нему только от прокси. При наличии CDN перед Nginx сначала настройте real_ip в Nginx только для доверенных адресов CDN; данный пример рассчитан на прямое подключение посетителей к Nginx.

## 6. Вход, сессии и лимиты

Откройте `https://wheel.example.com` и введите WHEEL_ACCESS_TOKEN из локального `.env`. Это общий токен доступа, персональных аккаунтов нет. Сессия хранится в Redis; браузер получает HttpOnly-cookie. По умолчанию она действует 8 часов. Выход отзывает её на сервере.

Параметры можно добавить в `.env`:

| Параметр | По умолчанию |
| --- | --- |
| `AUTH_SESSION_SECONDS` | 28800 |
| `LOGIN_ATTEMPTS` / `LOGIN_WINDOW_SECONDS` | 5 попыток с IP за 300 секунд |
| `LOGIN_GLOBAL_PER_MINUTE` | 60 попыток входа на весь сайт |
| `SPINS_PER_MINUTE` | 10 запросов розыгрыша с IP в минуту |
| `SPIN_BURST_PER_SECOND` | 2 запроса розыгрыша с IP в секунду |
| `SPINS_GLOBAL_PER_MINUTE` | 60 розыгрышей на весь сайт в минуту |
| `REQUESTS_PER_MINUTE` | 120 динамических запросов с IP в минуту |

Лимит попыток входа учитывает и успешные попытки. Люди за одним NAT делят IP-лимит. Приложение использует общие Redis-счётчики с фиксированными окнами, возвращает HTTP 429 и Retry-After. Лимит Nginx работает независимо и тоже может вернуть 429. При недоступности Redis доступ закрывается с ошибкой, а защита не отключается.

После изменения настроек:

```bash
docker compose up -d frontend
```

### Смена токена

```bash
python3 rotate_access_token.py
docker compose up -d frontend
```

Новый токен записывается в `.env`. После применения настройки старый токен и прежние сессии больше не дают доступ.

## 7. Обновление и обслуживание

Для изменения исходников:

```bash
docker compose up -d --build
```

Только интерфейс/Django — `docker compose up -d --build frontend`, только Flask — `docker compose up -d --build backend`. Перезапуск без сборки не копирует новые исходники в образ.

Для диагностики:

```bash
docker compose ps
docker compose logs --tail=100 frontend backend redis
sudo nginx -t
```

Redis хранит сессии и лимиты в томе `redis-data`. Обычный `docker compose down` сохраняет его; `down -v` удаляет. Результаты розыгрышей по-прежнему хранятся в браузере, а не в Redis. Сохраняйте `.env` отдельно от Git; резервная копия Redis может содержать действующие сессии.

Если используется Watchtower, добавьте в frontend, backend и redis на одном уровне с build/image:

```yaml
labels:
  - "com.centurylinklabs.watchtower.enable=false"
```

Затем примените `docker compose up -d`.

## 8. Проверка перед публикацией

- Без входа сайт переводит на страницу ввода токена.
- Верный токен позволяет провести розыгрыш, неверный — нет.
- У cookie wheel_session установлены HttpOnly, Secure и SameSite=Strict.
- После выхода доступ снова требует входа.
- Лимиты учитывают реальные IP; блокировка возвращает 429.
- Успешны `nginx -t`, healthcheck контейнеров и проверка продления сертификата.