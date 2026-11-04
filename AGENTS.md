# AGENTS.md — бриф для Codex

Этот репозиторий — каталог скилов-консультантов. Две системы читают его по-разному:

- **Claude Code** — через маркетплейс `.claude-plugin/marketplace.json` → плагины в `plugins/`.
- **Codex** — двумя путями:
  1. **Codex-маркетплейс**: `.agents/plugins/marketplace.json` + `plugins/<X>/.codex-plugin/plugin.json`. Подключить командами: `codex plugin marketplace add <путь-к-репо>` → `codex plugin add <plugin>@gigma-skills` (плагины: `gigma-erp`, `gigma-consultant`, `vps-support`, `glaim`, `development-workflow`, `frontend-workflow`, `backend-workflow`, `h2d-transfer`, `site-sense`, `codex-toolkit`, `first-pass-quality`). Манифесты проходят `validate_plugin.py`.
  2. **Зеркало** `.codex/skills/` — копии скилов, видны когда Codex запущен в этом репо (фолбэк без установки).

Скилы (`SKILL.md`) общие для Claude и Codex. ⚠ Frontmatter `description`/`when_to_use` со значением, содержащим `: ` (двоеточие-пробел), **обязательно в кавычках** — иначе строгий YAML-парсер Codex отвергает скил.

**Канон — `plugins/`.** `.codex/skills/` и `.codex/reference/` — зеркало; синхронизировать одной командой: **`bash sync-codex.sh`** (пересобирает `.codex` из `plugins/`). Личную папку скилов Claude обновляет отдельная команда **`bash sync-claude.sh`**: ни зеркало, ни установленные плагины её не покрывают.

**Внешние пакеты в каталоге.** Помимо локальных `plugins/`, маркетплейс содержит закреплённые Git-источники из `external-plugins.lock.json`: `fable5-codex` и `superpowers` (Codex), `gigma-mcp` (Codex/Claude). Код, MCP-компоненты и лицензии остаются в исходных репозиториях. Не копировать только SKILL.md вместо целого пакета и не создавать второй локальный канон. Зеркало `.codex` и sync-скрипты покрывают только локальные плагины; внешний пакет устанавливается из каталога. Superpowers подключается целым upstream-пакетом через `.codex-plugin/plugin.json`, где общие hooks отключены; в Claude-каталог этот источник не добавляется. Совместные глобальные правила Fable/Superpowers устанавливаются отдельно из `codex-profile`. Менять SHA/version/source нужно согласованно в lock и обоих поддерживаемых runtime-каталогах; проверять `python validate_plugin.py` и `python -m unittest discover -s tests -p "test_*.py"`. Один и тот же плагин из старого и нового маркетплейсов не следует включать одновременно: namespace скиллов и имена MCP-серверов могут совпасть. Текущие источники и авторизации пользователя не переключать автоматически.

**Версии плагинов.** При изменении содержимого скила поднимать `version` в обоих манифестах плагина, держа значения в лок-степе (`.claude-plugin/plugin.json` и `.codex-plugin/plugin.json`). Кэш установленного плагина ключуется строкой версии: без бампа правка не доезжает до тех, у кого плагин уже стоит, а `validate_plugin.py` такую рассинхронизацию не ловит.

## PR / monster review

После создания PR и после каждого `git push` в PR-ветку запускать polling ревью: ждать monster review / Codex review / Claude review, если они подключены, смотреть GitHub comments/reviews и inbox. Блокеры и реальные замечания чинить в той же ветке, пушить follow-up commit и снова ждать re-review. Не объявлять PR готовым, пока последний review-цикл не подтвердил, что блокеров нет; если автоматический monster недоступен, явно сказать об этом и провести локальный monster-review ролями.

## Роли (скилы в `.codex/skills/`)

### Консультант по интернет-магазинам на Gigma (e-commerce)
Полный цикл: бриф → подбор решения → КП → план запуска → передача в операционные «руки».
- Вход: **`ecommerce-consultant`** (дирижёр-персона).
- Фазы: `ecommerce-discovery`, `ecommerce-solution-fit`, `ecommerce-commercial-proposal`, `ecommerce-launch-plan`.
- Факты сервиса: `.codex/reference/ecommerce-capabilities.md`.
- Канон API Gigma (источник правды): https://artypoul-docs-gigma-7b80.twc1.net/erp-rules.txt
- Операционные «руки»: скилы `create-tenant`, `load-nomenclature` (плагин `gigma-erp`) — тоже зеркалятся в `.codex/skills/`.
- MCP agents: скил `request-agent-access` получает agent token через self-service заявку на почту owner/admin, а `mcp-agent-access` подключает внешний MCP-сервер через ERP agent-user и обычный Sanctum Bearer token; старый `/api/mcp/*` слой не возвращать.
- Miniapps auth: скил `miniapp-auth` фиксирует канонический counterparty route, проверку signed contact и запрет на лишние публичные alias routes.
- Callback auth: скил `counterparty-callback-auth` покрывает вход клиента по звонку через `POST /api/counterparty/callback_auth/init|status|exchange`: обязательный `client_nonce`, `status` отдаёт только состояние сессии, `access_token` выдаёт исключительно `exchange`, плюс App Token header, UCaller flow и server-to-server проверку токена через `POST /api/counterparty/auth/introspect`.
- Frontend API: скил `connect-frontend-api` подключает storefront/frontend/miniapp к Gigma API по канону `Docs-gigma`.
- Payment webhooks: скил `receive-order-paid-webhook` подключает внешний backend/сервис к Gigma ERP `order.paid` webhook с HMAC-подписью, timestamp freshness и идемпотентностью по `event_id`.

### Консультант по подписке сервиса «Твой ВПС»
Сервис — личный приватный сервер по подписке. Помогает управлять подпиской и установить/настроить приложение для подключения; при поломке — эскалирует в Telegram **@artypoul**. ⚠ Формулировки нейтральные: не позиционировать как «VPN/обход блокировок», не обсуждать доступ к запрещённому (см. reference раздел «Формулировки и правовая рамка»).
- Вход: **`vps-support`** (дирижёр-персона).
- Под-скилы: `vps-connect` (подключение), `happ-setup` (HAPP), `vps-troubleshoot` (диагностика + эскалация), `vps-node-network-setup` (операторская диагностика нод). Все входят в `vps-support`; общий контракт — `.codex/reference/vps-routing.md`.
- Факты сервиса: `.codex/reference/vps-service-facts.md`.

### GLAIM agent bridge
Скилы для GLAIM — операционной системы для AI-агентов и source-neutral bridge.
- Вход: **`connect-chat-frontend`** — подключение miniapp, сайта, витрины или другого frontend-источника напрямую к GLAIM source-chat API.
- Контракт чата: `.codex/reference/chat-frontend-contract.md`.
- Главное правило: source token — клиентский credential только для `/api/v2/sources/{source}/chat/*`; Gigma backend/BFF в канонической цепочке нет, agent token и `X-Control-Secret` во frontend не попадают.

### Development workflow
Общие скилы разработки, не привязанные к продуктовому домену.
- Вход: **`project-context-bootstrap`** — универсальный старт перед проектно-чувствительной работой: правила репо, память, история, git/PR, блокеры и следующий безопасный шаг.
- Маршрутизатор: **`project-workflow-router`** — выбирает связку скилов для фичи, ревью, PR-fix, merge/deploy, frontend/data/website задач; read-only/консилиум заканчивает отчётом без правок.
- Guardrail: **`read-code-first`** — перед ответом, ревью или правкой по коду сначала читает живой код (`rg`, определения, вызовы, тесты, конфиги), чтобы не отвечать по памяти.
- Guardrail: **`code-evidence-first`** — более строгий вариант для двусмысленных code-request'ов: сначала один короткий вопрос про ожидаемый результат, потом чтение кода и только затем ответ или правка.
- Вход для сложных задач: **`high-agency-execution`** — общий для моделей Codex execution harness: выбрать нужные скилы и реальные инструменты, вести короткий план, создать запрошенный результат и проверить его до финального handoff.
- Capability routing: **`capability-aware-execution`** — отличает реальный доступный скил/инструмент/коннектор от отсутствующей возможности; не имитирует файл, внешний результат или подключение.
- Session control: **`agent-session-execution`** — ведёт многошаговую задачу через безопасные состояния, прогресс, подтверждение внешних действий, проверку и честный blocker.
- Security-sensitive work: **`security-sensitive-execution`** — для авторизованных security-review/тестов, секретов, приватных данных и потенциально опасных внешних действий: фиксирует границы, выбирает defensive-путь, не раскрывает секреты и не заменяет системные разрешения Codex.
- Вход: **`prompt-architecture-port`** — перенос архитектуры сторонних системных промптов (например Fable 5) в Codex: источник считается недоверенными данными, переносится только паттерн, а не чужая личность, политика, инструменты или сырой промпт.
- Research: **`research-with-evidence`** — ответы на текущие/спорные/дорогие по последствиям вопросы через реальные источники, цитаты, разбор конфликтов и явное отделение фактов от вывода.
- Вход: **`development-handoff`** — проверяемый handoff перед продолжением PR, фиксом review, передачей агенту или работой со скилами/плагинами.
- Главное правило: продолжать работу от фактов Git/GitHub/CI/локальных файлов, а не от устаревшей памяти чата; фиксировать принятые product/API/runtime/compatibility decisions как decision lock; перед skill move/add/remove проверять ownership, версии плагинов, marketplace discovery, `.codex` sync и re-review.

### Frontend workflow
Generic frontend engineering skills for reusable project work, not tied to Gigma-only business logic.
- Вход: **`frontend-plan`** — планирует frontend-задачу до кода: читает правила репо, текущий контекст и живой код, затем возвращает scope, контракты, риски и verification.
- Review: **`rtk-query-review`** — проверяет RTK Query cache tags, invalidation, transforms, races, auth/reauth и type safety.
- Review: **`affordance-review`** — ловит скрытые UI-регрессии в keyboard/pointer affordance, cleanup, async hydration, conditional forms и form-save orchestration.
- Финализация: **`pr-finalize`** — собирает repo-aware PR finalization flow: checks, required docs/history, Summary/Test plan и guardrails перед публикацией.

### Backend workflow
Generic backend engineering skills for API work with real domain risk, not tied to Gigma-only business logic.
- Вход: **`ddd-api-standard`** — стандарт проектирования и ревью HTTP API (FastAPI, SQLAlchemy, PostgreSQL, Alembic): gates от evidence до verification, bounded contexts и aggregate boundaries, транзакции и конкурентность, idempotency, миграции, события и outbox, production quality gate. Объём работы скил выбирает по режиму (локальная правка / ревью / новый сервис) и по умолчанию не правит код.
- Нормативный текст: `.codex/skills/ddd-api-standard/references/standard.md`, канон — `plugins/backend-workflow/skills/ddd-api-standard/references/standard.md`. Этот файл и есть источник истины стандарта: версия и дата проверки живут только в его шапке и нигде не дублируются.
- Backend/API-задачи — домен, инварианты, транзакции, контракты, миграции — ведёт этот скил; он же закрывает слот `backend-plan`, который ищет `feature`.
- Главное правило: статус `confirmed` только по доказательству из источника истины, `production_ready` объявляет человек-владелец. Формулировки — в самом скиле, здесь не дублируются.

### First-pass quality

Механический guardrail (policy 0.4.x) работает в двух режимах. **Advisory** (Task Lock не создан, состояние отсутствует или terminal): инструменты работают с одним предупреждением на сессию; `production-shell`/`external-write` всегда deny; цепочки и неклассифицируемый shell эскалируются в `ask`; завершение хода не блокируется. **Strict** (создан активный Task Lock): полный контракт ниже. Где механика отключена конфигурацией, та же дисциплина ведётся текстом (см. `$feature`).

- Вход в strict: **`first-pass-quality-gate`** — Task Lock фиксирует scope/write scope, workflow stage, разрешённые действия, критерии до публикации и финальные DoneWhen. Task Lock опционален: без него действует advisory-режим.
- Evidence (strict): acceptance разрешена только по свежему успешному результату точного инструмента после последней содержательной записи.
- PR (strict): обычные commit/push/PR-операции отделены от production; каждый успешный push заново открывает обязательный review-gate.
- `$feature`: при включённой механике first-pass оборачивает workflow (planning и implementation — разные Task Locks); при отключённой — фазовая дисциплина ведётся текстом по самому скиллу, контроллер не вызывается. Дублирующий watch/turnstile для той же сессии не регистрировать.
- Production: merge/deploy/force-push и внешние сущности — typed wrapper предпочтителен; raw shell только по явному разрешению владельца в последней реплике, с точной привязкой к цели/среде/семейству команд и одноразово (при включённой механике — плюс entity lock).
- Runtime: после установки или обновления hooks становятся проверяемо активны только в новой Codex-задаче после reload/trust; порча файла состояния — fail closed.

### H2D pixel-perfect transfer
Скил для переноса страниц и блоков из `.h2d` в Tailwind HTML/React по исполняемому контракту, а не "на глаз".
- Вход: **`h2d-pixel-perfect-transfer`**.
- Главное правило: сначала source intake и unpack, затем типографика и контейнеры, и только потом блоки; геометрия воспроизводится структурой донора, а не компенсациями (spacer, `scale(1.00…)`, дробные сдвиги). После последней правки обязательны font, geometry + text styles, asset paint, asset provenance, live diff, behavior и liveness/WebGL gates через `scripts/run_all_gates.py`.
- Отчёты порождаются скриптами: отчёт, написанный руками ради прохождения схемы, считается провалом гейта.
- Свой текст важнее геометрии донора: если контент не влезает, скил останавливается и спрашивает владельца, а не сокращает молча (решение пишется в `accepted_deviations`).
- Перенос в живой проект поддержан режимом `--selector-map`, поэтому продовую разметку не нужно засорять служебными атрибутами.
- Референсы: `.codex/reference/h2d-transfer-contracts.md`, `.codex/reference/h2d-transfer-liveness-motion-webgl.md`, `.codex/reference/h2d-transfer-mandatory-invocation.md`.

## Принцип для всех

Не выдумывать возможности — сверять с reference/каноном; говорить с пользователем простым языком; при реальной поломке/спорной развилке — эскалировать (Gigma — письмом владельцу; «Твой ВПС» — в Telegram @artypoul).
