# Колесо фортуны

Веб-приложение для выбора победителей по никам. Поддерживает три режима: отдельный шанс на каждую запись, вес по количеству повторов и обратный вес. Длительность вращения — от 3 до 20 секунд.

Победителя выбирает **Flask**, страницу и API для браузера обслуживает **Django**, интерфейс написан на **HTML/CSS/JavaScript**. **Redis** хранит сессии входа и общие счётчики ограничения запросов. Список участников и последние 50 результатов сохраняются в браузере.

## Запуск

Нужны Docker с плагином Compose и Python 3. Склонируйте репозиторий и выполните из его корня:

```bash
python3 setup_env.py
```

Скрипт создаст `.env` с секретами или добавит недостающие параметры в существующий файл.

Для локального запуска по HTTP укажите в `.env`:

```dotenv
COOKIE_SECURE=false
```

Запустите приложение:

```bash
docker compose up -d --build
```

Откройте **http://localhost:8080** на машине с Docker. Для входа используйте свой токен доступа. При первоначальной одиночной конфигурации это `WHEEL_ACCESS_TOKEN` из `.env`.

Для production настройте домен, HTTPS, `COOKIE_SECURE=true` и доверенный адрес Nginx. Подробности — в [PRODUCTION.md](PRODUCTION.md), пример прокси — в [nginx.example.conf](nginx.example.conf).

Логи и остановка:

```bash
docker compose logs -f
docker compose down
```

## Управление токенами

Все команды выполняются на Docker-хосте из корня проекта.

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

После первого обновления Python-кода нужна пересборка `docker compose up -d --build frontend`. Для последующих изменений только токенов достаточно `docker compose up -d frontend` — перезапуск без пересоздания не подхватит новые переменные окружения.

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

После правок пересоберите нужный сервис:

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