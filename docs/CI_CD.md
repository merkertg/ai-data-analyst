# CI/CD: проверки проекта и публикация образа

[← README](../README.md) · [Все материалы](../README.md#documentation)

Эта инструкция объясняет, что запускает GitHub после обновления проекта,
как устроены проверки и как получить готовый Docker-образ. Краткая
английская версия — [CI and delivery](instructions/ci-and-delivery.md).

**Текущая цель:** после каждого push и pull request в `main` повторить на
чистой Linux-машине те же проверки, что выполняются локально, проверить
известные уязвимости зависимостей, собрать Docker-образ, поднять из него
весь стенд и проверить его сквозной smoke-проверкой. После push в `main` или
релизного тега `vX.Y.Z` **именно этот** образ публикуется в GitHub Container
Registry (GHCR): `ghcr.io/merkertg/ai-data-analyst`. Версию выбирает
человек; CI не создаёт теги автоматически.
[Подробная процедура выпуска и запуска опубликованного образа](RELEASES.md).

CD в этом проекте означает **Continuous Delivery — доставку готового образа
в реестр**. Развёртывание на сервере, покупка хостинга и запуск приложения
в интернете в текущую настройку не входят. Устройство самого стенда — в
[руководстве этапа 10](STAGE_10.md).

## Подтверждённый запуск

Результат GitHub Actions подтверждает пользователь; логи Actions напрямую
не читались.

| Коммит | Задание | Результат | Кто подтвердил |
| --- | --- | --- | --- |
| `63f3550` (этап 06) | Lint, types and tests | Успешно | Пользователь, 21 октября 2026 года |
| `31f31bd` (этап 09) | Lint, types and tests | Успешно | Пользователь, 22 октября 2026 года |

Оба подтверждения относятся к workflow с одним заданием. Четыре задания
этапа 10 (`checks`, `audit`, `container`, `publish`) и публикация в GHCR
успешным запуском пока не подтверждены: 23 октября CI сообщил об ошибке
аудита зависимостей, после чего зависимости были обновлены (подробности —
в [DEPENDENCY_UPDATES.md](DEPENDENCY_UPDATES.md)).

Локальные проверки и actionlint не подтверждают удалённый запуск: это разные
машины, и только GitHub показывает фактический результат. Сверяй результат
во вкладке Actions с конкретным коммитом; фактическое состояние фиксируется
в [VERIFICATION.md](VERIFICATION.md).

## 1. Какие слова нужно понимать

| Слово | Значение в этом проекте |
| --- | --- |
| Репозиторий | Папка проекта с историей Git; её копия хранится на GitHub. |
| Commit | Сохранённая версия изменений в локальной истории Git. |
| Push | Отправка локальных коммитов в репозиторий GitHub. |
| Pull request, PR | Предложение включить изменения из другой ветки в `main`. |
| Merge | Объединение изменений; после merge PR ветка `main` обновляется. |
| CI | Автоматическая проверка изменений: зависимости, стиль, типы, тесты, аудит, стенд. |
| CD | Доставка проверенного результата — Docker-образа — в реестр GHCR. |
| Workflow | Сценарий GitHub Actions из файла `.github/workflows/ci.yml`. |
| Job | Отдельное задание внутри workflow; выполняется на отдельной машине. |
| Step | Шаг внутри задания: например, установить uv или запустить тесты. |
| Runner | Машина GitHub, на которой выполняется задание; здесь `ubuntu-24.04`. |
| Action | Готовый переиспользуемый шаг, например `actions/checkout`. |
| Artifact | Файл, который задание сохраняет в запуске: отчёт покрытия, аудит или образ. |
| Образ | Упакованное приложение со всеми зависимостями; из него запускаются контейнеры. |
| GHCR | GitHub Container Registry — хранилище образов рядом с репозиторием. |
| Digest | Хэш содержимого образа `sha256:…`; в отличие от тега, его нельзя перенести. |
| Smoke-проверка | Короткая сквозная проверка запущенного стенда глазами пользователя. |

**Локальный `git commit` сам по себе не запускает GitHub Actions.**
GitHub увидит изменения только после `git push`. Поэтому «проверять при
коммите в main» означает: **проверять каждый push, который обновляет `main`
на GitHub**.

## 2. Когда запускается pipeline

| Событие | Запускает проверки | Публикует образ |
| --- | --- | --- |
| `push` в `main` | Да | `:main` и `:sha-<коммит>` |
| `push` тега `v1.2.3` | Да | `:v1.2.3` и `:sha-<коммит>` |
| Создание или обновление PR в `main` | Да | Нет |
| Ручной запуск **Run workflow** во вкладке Actions | Да | Нет |
| `push` в другую ветку без PR в `main` | Нет | Нет |
| Локальный `git commit` без `push` | Нет | Нет |

В событии `pull_request` фильтр `branches: [main]` относится к **целевой**
ветке PR: PR из `feature/database` в `main` запускает проверки. Изменения
только в документации тоже запускают pipeline: исключений по путям нет —
Ruff проверяет и Python-блоки в Markdown.

Кнопка ручного запуска появляется, когда workflow с `workflow_dispatch`
уже лежит в ветке по умолчанию.

## 3. В каком порядке всё выполняется

```text
push в main / push v1.2.3 / PR в main / ручной запуск
        │
        ▼
checks: lock → Ruff → mypy → миграции вверх, check, откат → pytest + покрытие ≥ 90 %
audit:  uv export без dev → pip-audit → сверка с audit-exceptions.json
        │ только при успехе обоих заданий
        ▼
container: docker build → контракт образа → docker compose up → smoke
           → down + up → bootstrap «already present / kept» → smoke ещё раз
        │ только при успехе и только для push
        ▼
publish: проверка тега → docker load проверенного образа → теги → GHCR
```

На PR и при ручном запуске цепочка заканчивается после проверки стенда.
На push в `main` или тега `vX.Y.Z` успешный pipeline заканчивается
публикацией образа в GHCR. Если задание завершилось ошибкой, зависящие
от него задания не запускаются, а запуск становится красным.

### Задание `checks`: проверить Python-проект

Имя в интерфейсе — **Lint, types and tests**; `ubuntu-24.04`, не дольше
15 минут.

```text
сервис: PostgreSQL 17 (тот же digest, что в compose.yaml), база industrialflow_test
 1. Checkout repository            — код ровно того коммита, который проверяется
 2. Install uv                     — uv 0.12.23 и Python 3.12, кеш по uv.lock
 3. Install locked dependencies    — uv sync --locked
 4. Ruff lint                      — uv run --locked ruff check .
 5. Ruff format                    — uv run --locked ruff format --check .
 6. Mypy                           — uv run --locked mypy app ui tests migrations
 7. Apply migrations               — alembic upgrade head
 8. Check models match migrations  — alembic check
 9. Check downgrade and upgrade    — alembic downgrade base, затем upgrade head
10. Pytest with coverage           — pytest --cov: unit и интеграционные тесты, порог 90 %
11. Upload coverage report         — артефакт coverage-report с coverage.xml
```

**Шаг 3** — главный для воспроизводимости. `--locked` требует, чтобы
`uv.lock` точно соответствовал `pyproject.toml`. Если кто-то изменил
зависимости, но забыл закоммитить обновлённый lock, CI упадёт здесь,
а не позже с непонятной ошибкой.

**Шаги 4–6 и 10** — те же команды, что в [инструкции тестирования](instructions/testing.md).
Флаг `--locked` у `uv run` ещё раз гарантирует, что окружение не будет
незаметно пересобрано с другими версиями.

**Шаги 7–9** проверяют миграции на пустой базе: схема создаётся только
Alembic, модели совпадают с миграциями (`alembic check` упадёт, если модель
изменили без новой миграции), а откат до пустой базы и повторное применение
работают. Подробно о миграциях — в [руководстве этапа 02](STAGE_02.md).

**Шаг 10** измеряет покрытие строк **и ветвей** `app/` и `ui/`: непроверенная
ветка `if` тоже видна. Порог задан в `[tool.coverage.report] fail_under = 90`
файла `pyproject.toml`; ниже порога шаг падает, даже если все тесты зелёные.
Фактическое значение каждого прогона — в [VERIFICATION.md](VERIFICATION.md).
Тесты безопасности и evals агента запускает тот же pytest: evals загружают
полный набор seed 42 (20 000 заказов) в откатываемую транзакцию. Ключ
OpenAI и сеть не нужны — агент работает с mock-провайдером и поддельным SDK.

#### Сервис PostgreSQL

```yaml
services:
  postgres:
    image: postgres:17@sha256:2d2b8998d31037bf721cfdf764d76ba74171b4fab3431b7f72c27c56ddbdf9e3
    env:
      POSTGRES_DB: industrialflow_test
    ports:
      - 5432:5432
    options: >-
      --health-cmd "pg_isready -h 127.0.0.1 -U analyst -d industrialflow_test"
```

GitHub запускает рядом с заданием отдельный контейнер PostgreSQL и ждёт,
пока healthcheck сообщит о готовности, — только потом начинаются шаги.
Контейнер существует только на время запуска. Переменные задания
`DATABASE_URL` (для Alembic) и `TEST_DATABASE_URL` (для тестов) указывают
на эту базу. Пароль `analyst_ci` относится к одноразовому контейнеру
и ничего не защищает.

GitHub сам задаёт `CI=true`. В этом режиме интеграционные тесты без
`TEST_DATABASE_URL` **падают**, а не пропускаются: забытая настройка не даст
зелёный результат без проверки базы. Любой тест, которому нужна тестовая
база, получает маркер `integration` автоматически из `tests/conftest.py`.

### Задание `audit`: проверить известные уязвимости зависимостей

Имя в интерфейсе — **Audit runtime dependencies**; не дольше 10 минут.
Выполняется параллельно с `checks`.

```text
1. Checkout repository
2. Install uv and Python 3.12
3. Audit locked runtime dependencies — python scripts/audit_dependencies.py
4. Upload audit report               — артефакт dependency-audit, даже при ошибке
```

`scripts/audit_dependencies.py` делает три вещи:

1. `uv export --locked --no-dev` записывает точные версии runtime-зависимостей
   с хэшами — без pytest, Ruff и mypy, которых нет в образе.
2. pip-audit 2.10.1 проверяет их по базе уязвимостей PyPI (`--strict`,
   `--require-hashes`).
3. Каждая находка сверяется с `scripts/audit-exceptions.json`. Находка вне
   списка, исключение без причины, со сроком дальше 30 дней, просроченное
   или уже лишнее — ошибка. Принятый риск остаётся видимым и временным.

Аудит прекращает проверку с ошибкой, если результату нельзя доверять. Перед
запуском pip-audit скрипт удаляет предыдущий `reports/pip-audit.json`, затем
требует новый JSON с корректной структурой зависимостей и находок. Код
завершения должен соответствовать отчёту: код «найдены уязвимости» с пустым
списком находок тоже считается ошибкой. Отсутствующий или повреждённый JSON,
операционная ошибка pip-audit и несогласованный код блокируют сборку. Эту
защиту проверяет `tests/test_audit_dependencies.py`: внешние команды
подменяются, поэтому сеть и настоящий pip-audit для проверки сбоев не нужны.

Сейчас список исключений пуст. История: первый аудит 22 октября нашёл
24 уязвимости `pillow 12.3.0` и одну `certifi 2026.7.22`; их временно
приняли до 6 ноября. 23 октября CI сообщил ещё о 12 находках, и вместо
расширения списка зависимости были обновлены: certifi 2026.10.19,
opentelemetry-api 1.45.1, Pillow 13.0.0 и Streamlit 1.66.1.

Обычные обновления ограничены общей датой `exclude-newer = 2026-10-09`
(14 дней до обновления). Для исправлений безопасности даты в
`[tool.uv.exclude-newer-package]` отдельно допускают Streamlit, Pillow и
certifi, а `constraint-dependencies` не даёт следующему разрешению
зависимостей вернуть уязвимые версии. Это исключения из правила возраста,
а не из аудита. Точные даты, ограничения и команды — в
[DEPENDENCY_UPDATES.md](DEPENDENCY_UPDATES.md).

### Задание `container`: проверить собранный стенд

Имя в интерфейсе — **Build and smoke test Docker**; `needs: [checks, audit]`,
не дольше 20 минут. Задание выполняет те же команды, что и пользователь:
сборка образа, `docker compose up`, проверка, пересоздание.

```text
 1. Checkout repository
 2. Build image                    — docker build --pull с метками OCI source и revision
 3. Check runtime user ...         — UID/GID 10001; нет pytest, Ruff, mypy и uv
 4. Start the stand                — docker compose up --no-build --detach --wait
 5. Smoke test API, agent and UI   — python3 scripts/smoke_stack.py
 6. Re-create containers ...       — down + up; bootstrap: already present, kept; smoke ещё раз
 7. Export tested image            — docker save | gzip (только push)
 8. Upload tested image            — артефакт tested-image на сутки (только push)
 9. Show Compose logs on failure   — последние 200 строк каждого сервиса
10. Remove the test stand          — docker compose down --volumes (всегда)
```

**Шаг 3** нужен потому, что здоровый стенд не покажет ни запуск от root,
ни оставшиеся в образе инструменты разработки.

**Шаг 4** использует `--no-build`: стенд запускается ровно из образа шага 2.
Compose получает явные значения через переменные задания — `.env` в CI нет:
`APP_IMAGE=ai-data-analyst:ci`, одноразовый пароль `container_ci`,
`LLM_PROVIDER=mock` и пустой `OPENAI_API_KEY`.

**Шаг 5.** `scripts/smoke_stack.py` использует только стандартную библиотеку
и проверяет: `/health`; `/ready` с ревизией `0004`; 401 без токена;
выручку сентября по seed 42 (`466678757.35`, изменение `-165497371.86`,
`-26.18` %); ответ агента, в доказательствах которого есть это значение;
этот запуск в истории; здоровье Streamlit. Токен интерфейса читается из
тома bootstrap, маскируется в журнале (`::add-mask::`) и передаётся через
переменную окружения, а не аргументом команды.

**Шаг 6** проверяет, что данные и токен переживают пересоздание
контейнеров: bootstrap второй раз сообщает `"demo_data": "already present"`
и `"ui_token": "kept"`, а smoke проходит снова.

### Задание `publish`: отправить проверенный образ в GHCR

Имя в интерфейсе — **Publish tested image to GHCR**; `needs: container`,
только для `push`, не дольше 10 минут.

```text
1. Checkout complete history  — полная история нужна для проверки тега
2. Validate version tag       — тег вида vX.Y.Z и коммит из истории main
3. Download tested image      — артефакт tested-image из задания container
4. Load tested image          — gunzip | docker load
5. Log in to GHCR             — встроенный GITHUB_TOKEN этого запуска
6. Push tags                  — :sha-<7 символов> и :main либо :vX.Y.Z; digest в сводке
```

Повторной сборки нет: в GHCR попадают те же слои, что прошли smoke. Только
у этого задания есть `packages: write`. Метка
`org.opencontainers.image.source` связывает пакет с репозиторием, поэтому
права пакета наследуются от репозитория: приватный репозиторий —
приватный пакет. Сводка задания (Summary) перечисляет теги и digest.

## 4. Зачем нужны `permissions`, `needs`, `if` и `concurrency`

```yaml
permissions:
  contents: read
```

Каждое задание получает временный токен GitHub. По умолчанию его права
могут быть шире, чем нужно. Здесь заданиям разрешено **только читать код**:
даже если в зависимость попадёт вредоносный код, он не сможет изменить
репозиторий этим токеном. Только `publish` дополнительно получает
`packages: write`.

```yaml
container:
  needs: [checks, audit]
publish:
  needs: container
  if: ${{ github.event_name == 'push' }}
```

`needs` задаёт порядок: стенд не собирается, пока не прошли тесты и аудит,
а публикация — пока не прошёл стенд. `if` пропускает публикацию для PR и
ручного запуска: в интерфейсе она получает статус **Skipped**, и это
ожидаемо.

```yaml
concurrency:
  group: ${{ github.workflow }}-${{ github.ref }}
  cancel-in-progress: ${{ github.event_name == 'pull_request' }}
```

Если в один PR быстро отправить два коммита, проверка первого уже не нужна —
она отменяется. Запуски для `main` не отменяются: каждый коммит в основной
ветке должен получить свой результат.

`timeout-minutes` ограничивает время каждого задания: 15 минут у `checks`,
20 у `container`, 10 у `audit` и `publish`. Если шаг завис, GitHub
остановит его по тайм-ауту.

### Почему действия и образы закреплены

```yaml
uses: actions/checkout@3d3c42e5aac5ba805825da76410c181273ba90b1 # v7.0.1
```

Тег `v7` автор действия может перенести на другой код, в том числе случайно
сломанный или вредоносный. Полный SHA коммита изменить нельзя. Комментарий
`# v7.0.1` нужен людям, чтобы понимать, какая это версия. Те же SHA
используются в первом проекте. Базовые образы PostgreSQL, Python и uv
закреплены по digest; `tests/test_delivery.py` проверяет, что каждое
`uses:` закреплено SHA, а образы — digest.

`persist-credentials: false` не оставляет токен GitHub в рабочей папке
после checkout: последующим шагам он не нужен.

## 5. Какие файлы за что отвечают

| Файл | Роль в CI/CD |
| --- | --- |
| `.github/workflows/ci.yml` | Сам сценарий: события, четыре задания, шаги и права |
| `pyproject.toml` | Зависимости, политика возраста пакетов, настройки pytest, покрытия, Ruff и mypy |
| `uv.lock` | Точные версии и хэши всех пакетов; `uv sync --locked` ставит именно их |
| `.python-version` | Версия Python для uv: 3.12 |
| `app/`, `ui/`, `tests/`, `migrations/` | Что проверяют mypy и pytest |
| `alembic.ini`, `migrations/versions/` | Миграции, которые применяют шаги 7–9 `checks` и сервис `migrate` |
| `sql/` | Запросы, которые выполняют интеграционные тесты |
| `evals/cases.json` | 42 вопроса evals агента; попадают и в образ |
| `scripts/audit_dependencies.py`, `scripts/audit-exceptions.json` | Аудит runtime-зависимостей и временно принятые находки со сроком |
| `Dockerfile`, `.dockerignore` | Сборка образа и список файлов, которые в него не попадают |
| `compose.yaml` | Стенд: `db`, `migrate`, `bootstrap`, `api`, `ui`; профиль `test` — `db-test` |
| `app/bootstrap.py` | Демо-данные в пустую базу и токен интерфейса; безопасен при повторе |
| `scripts/smoke_stack.py` | Сквозная проверка запущенного стенда |
| `tests/test_delivery.py` | Закрепление действий и образов, порты только на `127.0.0.1`, non-root, состав `.dockerignore` |
| `docs/**/*.md`, `README.md` | Python-блоки внутри проверяет `ruff format` |

### Как устроен `Dockerfile`

```text
python-base  python:3.12-slim@sha256:a6e3…   общий слой для обеих стадий
builder      + uv 0.12.23@sha256:61d3…       uv sync --locked --no-dev → /app/.venv
runtime      + /app/.venv и код              USER app (UID 10001), HEALTHCHECK /ready
```

Две стадии: uv и кеш сборки остаются в `builder`, в финальный образ идут
только `.venv`, `app/`, `ui/`, `migrations/`, `alembic.ini`, `.streamlit/` и
`evals/cases.json`. Сначала копируются `pyproject.toml` и `uv.lock`: изменение
кода не переустанавливает библиотеки. Один образ обслуживает все сервисы
стенда — Compose выбирает команду: миграции, bootstrap, Uvicorn или
Streamlit. `.dockerignore` не пропускает в образ `.env`, `.git`, тесты,
документацию, данные и отчёты. Подробный разбор — в
[руководстве этапа 10](STAGE_10.md).

## 6. Что проверить в GitHub перед первым запуском

1. Открой репозиторий [merkertg/ai-data-analyst](https://github.com/merkertg/ai-data-analyst).
2. В **Settings → Actions → General** убедись, что GitHub Actions разрешены.
   Если включён список разрешённых actions, он должен допускать
   `actions/checkout`, `astral-sh/setup-uv`, `actions/upload-artifact`,
   `actions/download-artifact` и `docker/login-action`.
3. Там же, в **Workflow permissions**, публикации нужен `GITHUB_TOKEN`,
   которому разрешено запрашивать запись пакетов (задание запрашивает
   `packages: write` само).
4. Для workflow не нужны секреты, ключи OpenAI, пароли или Docker Hub:
   пароли в workflow относятся к одноразовым контейнерам.

## 7. Как отправить изменения и запустить проверку

Перед коммитом проверь, что именно изменилось:

```bash
git status
git diff
```

Затем выполни проверки локально (раздел 9), создай коммит и отправь его:

```bash
git add <нужные файлы>
git commit -m "Describe the change in English"
git push origin main
```

Если работа идёт в отдельной ветке, отправь эту ветку и создай PR в `main`:
проверки запустятся для PR, а после merge — ещё раз для `main` вместе с
публикацией. Как выпустить версию тегом — в [RELEASES.md](RELEASES.md).

## 8. Где смотреть результат

1. Вкладка **Actions** → workflow **CI** → запуск с нужным коммитом.
2. На схеме запуска четыре задания: **Lint, types and tests**, **Audit
   runtime dependencies**, **Build and smoke test Docker** и **Publish tested
   image to GHCR**. На PR публикация имеет статус **Skipped**.
3. Зелёная галочка — задание прошло. Красный крестик — открой задание и
   раскрой красный шаг: там полный вывод команды.
4. Внизу страницы запуска — артефакты:

| Артефакт | Содержимое | Хранится |
| --- | --- | --- |
| `coverage-report` | `coverage.xml` | 7 дней |
| `dependency-audit` | Экспортированные зависимости и `pip-audit.json` | 7 дней |
| `tested-image` | Проверенный образ в формате `docker save` (только push) | 1 день |

5. Опубликованный образ — в разделе **Packages** владельца репозитория;
   сводка задания `publish` перечисляет теги и digest.

Значок результата также виден рядом с коммитом на главной странице
репозитория и в списке коммитов.

## 9. Как выполнить проверки локально

### Проверить Python-код и настоящую PostgreSQL

Те же команды, что в `checks`, из корня проекта:

```bash
uv sync --locked
uv run --locked ruff check .
uv run --locked ruff format --check .
uv run --locked mypy app ui tests migrations
docker compose --profile test up --detach --wait db-test
export TEST_DATABASE_URL='postgresql+psycopg://analyst:analyst_test@127.0.0.1:5437/industrialflow_test'
export DATABASE_URL="$TEST_DATABASE_URL"
uv run --locked alembic upgrade head
uv run --locked alembic check
uv run --locked alembic downgrade base
uv run --locked alembic upgrade head
CI=true uv run --locked pytest --cov
```

`DATABASE_URL` переопределён на тестовую базу так же, как в CI: миграции
не трогают базу разработки. `CI=true` включает строгий режим: интеграционные
тесты не будут пропущены.

### Проверить зависимости

```bash
uv run python scripts/audit_dependencies.py
```

Скрипту нужна сеть: pip-audit загружает базу уязвимостей. Отчёт —
`reports/pip-audit.json`.

### Собрать и запустить полный стенд

```bash
docker compose up --build --detach --wait --wait-timeout 300
SMOKE_TOKEN="$(docker compose exec -T ui cat /run/ai-data-analyst/ui_token)" python3 scripts/smoke_stack.py
docker compose down
```

`docker compose down` без `--volumes` сохраняет данные и токен: повторный
`up` должен сообщить `already present` и `kept`. Порты по умолчанию —
API `8001`, интерфейс `8502`, только на `127.0.0.1`; если они заняты,
задай `API_PORT` и `UI_PORT`.

Проверить сам workflow без отправки на GitHub:

```bash
uvx --from actionlint-py actionlint .github/workflows/ci.yml
```

Чтобы проверить проект «как на новой машине», склонируй его во временную
папку и выполни команды там — так ловятся файлы, которые забыли закоммитить.

## 10. Как скачать опубликованный образ

После успешного `publish`:

```bash
docker login ghcr.io --username <пользователь GitHub>
APP_IMAGE=ghcr.io/merkertg/ai-data-analyst:main docker compose up --no-build --detach --wait
```

Пакет приватный, как и репозиторий, поэтому сначала нужен вход в GHCR.
Для локального входа используется **personal access token (classic)** с
правом `read:packages`: вставь его в скрытый запрос пароля. Не добавляй
токен в команду, сохраняемую в истории терминала, и не помещай его в
`.github/workflows/ci.yml`, `.env`, Dockerfile или Git. CI использует
автоматически созданный `GITHUB_TOKEN`.

Чтобы запустить конкретный коммит или версию, замени тег: `:sha-<7 символов
коммита>` или `:v1.0.0`. `--no-build` запускает стенд из опубликованного
образа без локальной сборки. Публикуется образ `linux/amd64`; на Mac с
Apple Silicon он работает через эмуляцию, а `docker compose up --build`
собирает родной arm64. Для возврата к локальному образу выполни
`unset APP_IMAGE` и `docker compose up --build`.

## 11. Что делать, если pipeline красный

| Упавший шаг или симптом | Частая причина | Что сделать |
| --- | --- | --- |
| Actions не появился после commit | Не было `git push` или PR в `main` | Выполни `git push`; проверь, что workflow лежит в `.github/workflows/` |
| Install locked dependencies | `pyproject.toml` изменён, `uv.lock` — нет | `uv lock`, проверить diff и закоммитить `uv.lock` |
| Ruff lint | Стиль, порядок импортов, неиспользуемый импорт | `uv run ruff check --fix .`, остальное исправить вручную |
| Ruff format | Файл или Python-блок в Markdown не отформатирован | `uv run ruff format .` |
| Mypy | Ошибка типов или функция без аннотаций | Исправить по сообщению mypy |
| Apply migrations | Ошибка в файле миграции | Повторить `alembic upgrade head` на `db-test` и прочитать сообщение |
| Check models match migrations | Модель изменена без новой миграции | `alembic revision --autogenerate`, проверить и закоммитить файл |
| Check downgrade and upgrade | `downgrade()` не отменяет `upgrade()` | Исправить `downgrade()` в новой миграции |
| Pytest | Тест упал | Запустить `uv run pytest -x -v` локально и разобраться |
| `Coverage failure: total of … is less than fail-under=90` | Новый код без тестов | Посмотреть столбец `Missing` в выводе и добавить тесты на непокрытые строки и ветви |
| Audit runtime dependencies | Новая уязвимость, истёкшее или лишнее исключение | Обновить пакет по [DEPENDENCY_UPDATES.md](DEPENDENCY_UPDATES.md); исключение — только с причиной и сроком |
| Build image | Не найден копируемый файл или базовый образ | Открыть первый неуспешный шаг `docker build`; проверить `.dockerignore` |
| Check runtime user ... | В образ попал инструмент разработки или пользователь root | Проверить `--no-dev` и `USER app` в `Dockerfile` |
| Start the stand | Сервис не стал healthy | Раскрыть шаг **Show Compose logs on failure**: `migrate`, `bootstrap`, `api` |
| Smoke test | Изменились числа, ответ API или агента | Сравнить с [VERIFICATION.md](VERIFICATION.md), повторить стенд локально (раздел 9) |
| Re-create containers ... | Данные или токен не пережили пересоздание | Проверить тома `postgres_data` и `ui_token` в `compose.yaml` |
| Validate version tag | Тег не вида `vX.Y.Z` или не на `main` | Создать правильный тег на коммите из `main` ([RELEASES.md](RELEASES.md)) |
| `denied`, `permission_denied` в `publish` | Нет права на запись пакетов | Проверить Workflow permissions и доступ репозитория к пакету |
| `publish` имеет статус Skipped | PR или ручной запуск | Ожидаемо; для push в `main` проверить предыдущие задания |
| Любой, но локально всё зелёное | Файл не закоммичен или зависит от локального `.env` | Проверка в чистом клоне (раздел 9) |

Если не прошёл `checks` или `audit`, стенд и публикация не запускаются.
Если не прошёл `container`, публикация не запускается. Если публикация
завершилась ошибкой, предыдущий опубликованный образ остаётся в реестре.
После исправления сделай новый коммит и push: GitHub запустит проверку
заново. Не переписывай историю `main` ради «чистого» результата.

## 12. Как запретить merge с ошибками: необязательная настройка GitHub

Workflow проверяет изменения и сообщает результат. Сам по себе файл
workflow не включает правила защиты ветки на GitHub.

После первого успешного запуска владелец репозитория может настроить
`Settings → Rules → Rulesets` либо правила защиты ветки, доступные для его
тарифа и типа репозитория:

1. Выбрать ветку `main`.
2. Включить требование успешных status checks перед merge.
3. Добавить проверки `Lint, types and tests`, `Audit runtime dependencies`
   и `Build and smoke test Docker` с именами, показанными в интерфейсе
   завершившегося PR-запуска.
4. При необходимости требовать PR перед обновлением `main`.

Публикацию `publish` не нужно делать обязательной PR-проверкой: на PR она
намеренно пропускается. Эта инструкция описывает ручную настройку
владельца; она не утверждает, что защита ветки уже включена.

## 13. Как pipeline проверяет этапы проекта

Реализованы все десять этапов. Каждый этап добавлял проверки вместе с
реализацией:

| Этап | Что добавилось в CI |
| --- | --- |
| 01 | Задание `checks`: lock, Ruff, mypy, pytest |
| 02 | PostgreSQL в задании, миграции `upgrade`, `alembic check`, откат и интеграционные тесты |
| 03 | В наборе проверок: воспроизводимость генерации, файловый набор, загрузка и откат, отказ от существующих данных, межтабличные правила качества |
| 04 | В наборе проверок: SQL-показатели сверяются с ручными ответами; проверяются округление, границы Москвы, пустые месяцы, сравнения, вклады и JSON CLI |
| 05 | В наборе проверок: статистические примеры, короткая история, MAD = 0, IQR, складские разрывы, воспроизводимость Isolation Forest и отдельное покрытие внедрённых сценариев |
| 06 | В наборе проверок: параметры API без базы, ответы API на настоящей PostgreSQL против ручных расчётов, снимки отчётов, `READ ONLY` сессии, откат миграции `0002` |
| 07 | В наборе проверок: строгие схемы инструментов и отчёта, цикл агента со сценарным провайдером, OpenAI на поддельном SDK, полный запуск mock на PostgreSQL, откат миграции `0003`; сеть и ключ OpenAI не используются |
| 08 | Строгий mypy для `ui/`, настройки и HTTP-клиент интерфейса, точность подписей графиков, Streamlit AppTest с поддельным API |
| 09 | В наборе проверок: тесты безопасности (токены, роли, лимиты, SQL-инъекции, `READ ONLY`, `statement_timeout`, враждебная модель, утечка ключа) и evals; эталонный прогон обязан пройти все 42 вопроса, mock — ровно записанные 17 |
| 10 | Порог покрытия 90 %, задание `audit`, задание `container` со стендом и smoke до и после пересоздания, задание `publish` — это и есть CD |

Когда появится новая возможность, добавляй проверку вместе с её реализацией:

| Будущая возможность | Что добавить в CI |
| --- | --- |
| Настоящая модель OpenAI | Отдельный ручной запуск с секретом и лимитом расходов; тот же набор `evals/cases.json` |
| Подпись образа и SBOM | cosign keyless и CycloneDX в `publish`, как в первом проекте |
| Сборка arm64 | `docker buildx` для `linux/amd64` и `linux/arm64` под одним тегом |
| Развёртывание | Отдельное задание после `publish` и проверка работающего сервиса |

После изменения контракта API синхронно обновляй `app/`, `tests/` и
`scripts/smoke_stack.py`. Например, изменение выручки демо-набора без
обновления smoke-проверки остановит публикацию — это ожидаемое поведение.

## 14. Как понять, что настройка полностью заработала

Есть три отдельных подтверждения:

1. **Локальная проверка:** команды раздела 9 проходят; стенд поднимается и
   проходит smoke-проверку до и после пересоздания.
2. **GitHub CI:** после push или PR во вкладке Actions успешно закончились
   `checks`, `audit` и `container`.
3. **Доставка образа:** после push в `main` успешно закончился `publish`,
   в Packages появились теги `:main` и `:sha-<коммит>`, а образ скачивается
   и запускается (раздел 10).

Наличие файлов в репозитории подтверждает настройку pipeline, но не заменяет
настоящий прогон на GitHub. Оценивай результат по логам конкретного запуска
и наличию пакета в GHCR. Подтверждённые запуски записываются в начале этой
инструкции и в [VERIFICATION.md](VERIFICATION.md).

## 15. Официальные источники

Синтаксис событий, заданий и прав:
[GitHub Actions workflow syntax](https://docs.github.com/en/actions/reference/workflows-and-actions/workflow-syntax).

Установка `uv` и запуск команд в Actions:
[Using uv in GitHub Actions](https://docs.astral.sh/uv/guides/integration/github/).

Lock-файл и синхронизация окружения:
[Locking and syncing](https://docs.astral.sh/uv/concepts/projects/sync/).

Отмена устаревших запусков:
[Control workflow concurrency](https://docs.github.com/en/actions/how-tos/write-workflows/choose-when-workflows-run/control-workflow-concurrency).

Публикация образа из Actions:
[Publishing and installing a package with GitHub Actions](https://docs.github.com/en/packages/managing-github-packages-using-github-actions-workflows/publishing-and-installing-a-package-with-github-actions).

Реестр контейнеров GitHub:
[Working with the Container registry](https://docs.github.com/en/packages/working-with-a-github-packages-registry/working-with-the-container-registry).

Аудит зависимостей:
[pip-audit: usage and security model](https://github.com/pypa/pip-audit#usage).

Проверка workflow:
[actionlint v1.7.12](https://github.com/rhysd/actionlint/releases/tag/v1.7.12).
