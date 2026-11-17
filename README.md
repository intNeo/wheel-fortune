# Колесо фортуны

Веб-приложение для выбора победителей по никам. Поддерживает три режима: отдельный шанс на каждую запись, вес по количеству повторов и обратный вес. Длительность вращения — от 3 до 20 секунд.

Победителя выбирает **Flask**, страницу и API для браузера обслуживает **Django**, интерфейс написан на **HTML/CSS/JavaScript**. **Redis** хранит сессии входа и общие счётчики ограничения запросов. Список участников и последние 50 результатов сохраняются в браузере.

## Содержание

- [Запуск](#запуск)
- [Настройка Nginx и HTTPS](#настройка-nginx-и-https)
- [Вход, сессии и лимиты](#вход-сессии-и-лимиты)
- [Управление токенами](#управление-токенами)
- [Обновление и обслуживание](#обновление-и-обслуживание)
- [Проверка перед публикацией](#проверка-перед-публикацией)
- [Редактирование и вклад](#редактирование-и-вклад)

## Запуск

Нужны Docker с плагином Compose, Python 3 и curl. Клонировать репозиторий и собирать образы не требуется.

### 1. Скачивание файлов

```bash
mkdir -p wheel-fortune
cd wheel-fortune

BASE_URL="https://raw.githubusercontent.com/intNeo/wheel-fortune/main"

curl -fL "$BASE_URL/compose.prod.yaml" -o compose.yaml
curl -fL "$BASE_URL/setup_env.py" -o setup_env.py
curl -fL "$BASE_URL/generate_access_tokens.py" -o generate_access_tokens.py
curl -fL "$BASE_URL/rotate_access_token.py" -o rotate_access_token.py
curl -fL "$BASE_URL/nginx.example.conf" -o nginx.example.conf
```

В скачанном `compose.yaml` используются готовые образы:

- `docker.int-neo.com/intneo/wheel-fortune/frontend:latest`
- `docker.int-neo.com/intneo/wheel-fortune/backend:latest`
- `redis:7.4-alpine` из Docker Hub.

Если Registry требует авторизацию, выполните `docker login docker.int-neo.com` перед скачиванием образов. Для доступа необходима учётная запись с правом pull.

Для установки конкретной версии добавьте в `.env` параметр `VERSION=1.0.0` (или другую опубликованную версию). Без него используется `latest`.

### 2. Настройка окружения

Создайте локальную конфигурацию:

```bash
python3 setup_env.py
```

Скрипт создаст `.env` с секретами или добавит недостающие параметры в существующий файл.

Ограничьте доступ к файлу с секретами: `chmod 600 .env`.

Для локального запуска по HTTP укажите в `.env`:

```dotenv
COOKIE_SECURE=false
```

| Секрет | Назначение |
| --- | --- |
| `WHEEL_ACCESS_TOKENS` | JSON-набор именованных токенов доступа |
| `WHEEL_ACCESS_TOKEN` | Токен, который вводят на странице входа |
| `API_TOKEN` | Внутренний доступ Django → Flask |
| `DJANGO_SECRET_KEY` | Секрет Django и ключ для служебных HMAC |
| `REDIS_PASSWORD` | Пароль Redis |

### 3. Скачивание образов и запуск

Запустите приложение:

```bash
docker compose pull
docker compose up -d --no-build
docker compose ps
curl http://127.0.0.1:8080/healthz
```

Ожидаемый ответ healthcheck — `{"status": "ok"}`. Он подтверждает работу Django, но не проверяет весь путь входа и розыгрыша.

Откройте **http://localhost:8080** на машине с Docker. Для входа используйте свой токен доступа. При первоначальной одиночной конфигурации это `WHEEL_ACCESS_TOKEN` из `.env`.

Для публичного доступа следуйте разделу [Настройка Nginx и HTTPS](#настройка-nginx-и-https). Порт приложения привязан к `127.0.0.1:8080`, Flask и Redis наружу не публикуются.

## Настройка Nginx и HTTPS

Инструкция для Debian/Ubuntu: Nginx установлен на хосте, Django, Flask и Redis запускаются через Docker Compose **на той же машине**. Команды проекта выполняются из папки с `compose.yaml`.

Дополнительно потребуются Nginx и Certbot. Настройте DNS-запись домена на публичный IP сервера. Для HTTP-01 и работы сайта должны быть доступны TCP 80 и 443; за NAT пробросьте их на Nginx.

В примерах используется `wheel.example.com`. Замените его своим доменом во всех командах, `.env` и конфигурации Nginx. Если публикуете AAAA-запись, IPv6 тоже должен вести на работающий Nginx; IPv6-слушатели в примере можно раскомментировать.

После установки по разделу [Запуск](#запуск) настройте `.env`:

```dotenv
ALLOWED_HOSTS=wheel.example.com,localhost,127.0.0.1
CSRF_TRUSTED_ORIGINS=https://wheel.example.com
COOKIE_SECURE=true
TRUSTED_PROXY_CIDRS=
```

Сохраните `localhost` в ALLOWED_HOSTS: он нужен healthcheck. В ALLOWED_HOSTS пишутся имена без схемы и портов, в CSRF_TRUSTED_ORIGINS — origin со схемой.

Примените настройки: `docker compose up -d --no-build`. Для входа используйте HTTPS-домен, поскольку `COOKIE_SECURE=true`.

### Первичное получение сертификата

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

### Постоянный конфиг Nginx

В [nginx.example.conf](nginx.example.conf) замените домен и пути сертификата, затем скопируйте файл вместо временного:

```bash
sudo cp nginx.example.conf /etc/nginx/sites-available/fortune.conf
# Если ссылка ещё не создана:
sudo ln -s /etc/nginx/sites-available/fortune.conf /etc/nginx/sites-enabled/fortune.conf
sudo nginx -t
```

При успешной проверке:

```bash
sudo systemctl reload nginx
```

Файл должен подключаться внутри `http {}` в `/etc/nginx/nginx.conf`. В стандартной схеме Debian/Ubuntu это обеспечивает `include /etc/nginx/sites-enabled/*;`. Можно использовать и `conf.d/*.conf`, если этот include также находится внутри http, но не подключайте один конфиг обоими способами.

`limit_req_zone` объявляется вне server-блоков и только один раз для имени `fortune_edge`. Дополнительный блок `http {}` в файле сайта не нужен. Конфигурация включает редирект HTTP → HTTPS, исключение ACME для продления, лимит тела 256 KiB и внешний лимит 5 запросов/с на IP с burst=20.

Если этот домен уже обслуживается другим файлом Nginx, объедините настройки или отключите его дублирующий server-блок. Другие сайты сервера менять не требуется.

#### Продление сертификата

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

### Реальный IP посетителя за прокси

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

## Вход, сессии и лимиты

Откройте приложение (в production — `https://wheel.example.com`) и введите действующий токен из локального `.env`: при одиночной конфигурации — `WHEEL_ACCESS_TOKEN`, при использовании именованных токенов — значение из `WHEEL_ACCESS_TOKENS`. Персональных аккаунтов нет. Сессия хранится в Redis; браузер получает HttpOnly-cookie. По умолчанию она действует 8 часов. Выход отзывает её на сервере.

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

## Управление токенами

Все команды выполняются на Docker-хосте из папки с `compose.yaml`.

### Добавить пользователя

```bash
python3 generate_access_tokens.py friend
docker compose up -d frontend
```

Добавляется **один** токен прямо в `.env`, остальные сохраняются. Новый токен выводится в терминал — передайте его пользователю приватно. Повторное имя отклоняется без изменения существующего токена.

### Сменить токен

```bash
python3 rotate_access_token.py --name friend
docker compose up -d frontend
```

Создаётся новое значение для `friend`; оно сохраняется в `.env`. Прежний токен и его сессии перестают давать доступ после применения настройки.

### Удалить токен и отозвать доступ

```bash
python3 rotate_access_token.py --name friend --delete
docker compose up -d frontend
```

Запись удаляется из `.env`. При следующем запросе сессии этого токена будут отклонены, остальные сохранятся. Последний действующий токен удалить нельзя — сначала добавьте другой.

При переходе с одного токена генератор сохраняет старый под именем `default`. Непустой `WHEEL_ACCESS_TOKENS` имеет приоритет над одиночным `WHEEL_ACCESS_TOKEN`. Не возвращайте отозванное значение: для повторной выдачи всегда создавайте новый токен. Все токены имеют одинаковые права; лимиты по IP и на весь сайт остаются общими.

Для изменения токенов пересборка образов не требуется. Команда `docker compose up -d frontend` применяет изменённые переменные окружения; обычный перезапуск контейнера их не обновляет.

## Обновление и обслуживание

Для обновления готовых образов:

```bash
docker compose pull
docker compose up -d --no-build
```

При использовании фиксированной версии сначала измените `VERSION` в `.env`. Обновляйте frontend и backend совместно до одной версии. При необходимости отдельно обновите Compose и вспомогательные скрипты из репозитория, сохранив локальные настройки. Повторно генерировать секреты для обычного обновления не нужно.

Для диагностики и остановки:

```bash
docker compose ps
docker compose logs --tail=100 frontend backend redis
sudo nginx -t # если используется Nginx
# Остановка приложения:
docker compose down
```

Redis хранит сессии и лимиты в томе `redis-data`. Обычный `docker compose down` сохраняет его; `down -v` удаляет. Результаты розыгрышей по-прежнему хранятся в браузере, а не в Redis. Сохраняйте `.env` отдельно от Git; резервная копия Redis может содержать действующие сессии.

Если используется Watchtower, добавьте в frontend, backend и redis на одном уровне с `image:`:

```yaml
labels:
  - "com.centurylinklabs.watchtower.enable=false"
```

Затем примените `docker compose up -d`.

## Проверка перед публикацией

- Без входа сайт переводит на страницу ввода токена.
- Верный токен позволяет провести розыгрыш, неверный — нет.
- У cookie wheel_session установлены HttpOnly, Secure и SameSite=Strict.
- После выхода доступ снова требует входа.
- Лимиты учитывают реальные IP; блокировка возвращает 429.
- Успешны `nginx -t`, healthcheck контейнеров и проверка продления сертификата.

## Редактирование и вклад

Для предложения изменений сделайте fork, склонируйте его и создайте ветку:

```bash
git switch -c feature/my-change
```

Редактируйте исходники проекта:

| Что изменить | Где искать |
| --- | --- |
| Разметка колеса и страницы входа | `frontend/wheel/templates/wheel/` |
| Дизайн и поведение интерфейса | `frontend/wheel/static/wheel/` |
| Django API | `frontend/wheel/views.py` |
| Авторизация и лимиты | `frontend/wheel/auth_views.py`, `frontend/wheel/security.py` |
| Алгоритм выбора победителя | `backend/app.py` |

При изменении режимов согласуйте веса и порядок секторов во Flask и `buildSectors()` в JavaScript.

Следующие команды предназначены только для разработки в клонированном репозитории с исходным `compose.yaml`, содержащим `build:`. После правок пересоберите нужный сервис:

```bash
docker compose up -d --build frontend
# Если изменён Flask:
docker compose up -d --build backend
```

Для запуска тестов в Linux/WSL:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r backend/requirements.txt -r frontend/requirements.txt -r tests/requirements.txt
python -m unittest discover -s tests -v
```

Сохраните изменения в коммит, отправьте ветку в свой fork и откройте Pull Request. Кратко опишите, что изменено и как проверено. Для ошибок приложите шаги воспроизведения и логи без секретов.
