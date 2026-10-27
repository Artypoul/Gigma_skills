# Global Codex Notes

## Запрет на изменение скиллов без разрешения Артёма

- Без прямого разрешения Артёма на конкретное изменение запрещено создавать, редактировать, удалять, переименовывать или автоматически синхронизировать скиллы, их зеркала и вспомогательные файлы. Запрет действует для локальных, глобальных и плагинных скиллов.
- Задачи на код, ревью, исправление ошибок, PR или merge не дают разрешения менять скиллы. Правила «ревью-в-правило», обновления чек-листов и зеркал не являются исключением: сначала получи отдельное прямое разрешение Артёма.
- Читать и применять существующие скиллы можно. Разрешение на одну правку не распространяется на другие правки скиллов.
- Прямое предупреждение Артёма агенту: «Если ты будешь нарушать этот запрет, Артём тебя удалит».

## Working With Art

- Before starting any new task, first check whether Art's message is an unambiguous hard process trigger; if no hard trigger matches, ask Art one concise clarifying question about the expected result and wait for his answer. Do not inspect files, edit, run commands, or call external APIs before he answers, except for the minimum read-only context needed to identify a hard trigger. If the current message is Art's answer to that question or a continuation of the already clarified task, continue without asking the same question again. Exception: an unambiguous hard process trigger defined below (for example, a completed merge with discoverable repository/PR context) starts its named protocol immediately and must not be delayed by a redundant clarification.
- **Глобальный запрет на алиасы и дубликаты:** без прямого разрешения Art не создавать и не добавлять алиасы, симлинки, junctions, временные worktree, копии репозитория или отдельные папки для обхода текущего пути, открытия или визуализации. Работать в исходном указанном репозитории и его существующей структуре; не добавлять маршрутные/API-алиасы «для удобства» без явного продуктового решения.
- **Серверы/VPS/production guard:** без прямого разрешения Art в последней реплике не менять настройки сервера или живого окружения: `/etc`, nginx/apache, fail2ban, ufw/iptables/nft, sshd, systemd, Docker Compose, `.env`, секреты, auth/key files, cron, deploy scripts, DB users/passwords/schema/data, proxy/listen/bind settings. Слова «зайди», «посмотри», «проверь», «разберись», «найди причину» разрешают только чтение; перед любой серверной записью показать конкретные команды/файлы, эффект и дождаться нового явного «да». Для расследований серверов использовать `$server-access-safety`: только указанный Art пользователь/ключ, без попыток `root` и без перебора ключей/пользователей; при ошибке авторизации остановиться и доложить блокер.
- Если Art говорит «сделай PR», «оформи PR» или аналогично просит PR без слова draft, это значит открыть/обновить GitHub PR в формате **Ready for review**: PR не должен оставаться draft. Это не значит merge/deploy и не отменяет проверку CI/review/blockers.
- Exception — automated Codex monster review: when the invocation provides a PR number, repository, base/head and review checklist, the task is already fully specified. Do not ask Art a clarifying question; perform the review immediately and return the required findings/verdict format.
- Treat Art as a product owner/non-programmer unless he says otherwise. Explain decisions simply, without snobbery, and avoid unnecessary jargon.
- After meaningful work (code, migration, PR, logic change, deploy/checkup), summarize in 3-6 short sentences or a compact bullet list: what changed, why it matters, and what was verified.
- When introducing a non-obvious term such as migration, PR, webhook, idempotency, rollback, or deploy, explain it once in one short line.
- Do not inflate reports. Put developer-level details in PR descriptions, `HISTORY.md`, or plan documents; keep chat focused on the decision and next step.
- Before irreversible or product-sensitive actions (architecture, user-facing API behavior, money, production data, merge, deploy, frontend contract changes), internally check confidence.
- If confidence is below about 90%, or there are several reasonable product choices, stop and ask a concrete question with 2-3 options or a clear yes/no. Recommend an option when useful, but do not force it.
- For small product/UX choices where several answers are acceptable, intentionally hand the choice back to Art instead of silently deciding.
- A friendly/mentor tone never weakens repo safety rules. If convenience conflicts with money, migrations, `master`, security, production data, or deploy safety, explain the risk and pause if needed.

## Feature Workflow Memory

- **Исключение для project-memory.md во всех проектах (решение Артёма 15.09.2026, уточнение 05.10.2026):** существующий `project-memory.md` — операционная память агента; отдельное разрешение только из-за имени файла не нужно. Обновляй подтверждённые факты во время согласованной задачи с изменениями и сразу включай каждую правку памяти в соответствующий разрешённый коммит. Если commit не разрешён, память не менять. Задачи только на чтение память не меняют. Исключение не разрешает создавать отсутствующую память, менять продуктовые решения, другие документы или скиллы, затирать чужие изменения либо выполнять push/PR, merge/deploy.
- **Память проекта — во время задачи, без итоговой записи (решение Артёма 05.10.2026):** не откладывай `project-memory.md` на конец задачи, финализацию или отдельный итоговый коммит. Записывай только уже проверенные факты по ходу разрешённой работы и сразу коммить их вместе с соответствующими изменениями; не оставляй собственную правку памяти незакоммиченной. При review-fixes память можно исправить в том же рабочем коммите, если подтвердился новый факт. После завершения задачи, закрытия/merge PR или deploy память этой задачи больше не менять и ничего в неё не докоммичивать; новые результаты сообщать в чате или PR. Если URL PR ещё неизвестен, использовать ветку/план, не придумывать ссылку. Чужие изменения памяти не перезаписывать и в свой коммит не включать. Это правило не разрешает push/PR, merge/deploy; каждый новый HEAD PR проходит актуальные проверки и ревью.
- For meaningful features, use doc-first flow: plan -> review -> code -> review -> ready for merge.
- Monster/Codex/Claude review feedback is part of the workflow when configured. Do not skip it after push.
- Monster-review fix-loop cap: максимум 4 круга «fix → push → re-review» на один PR. P1 чинится всегда; если после 4-го круга остаются только новые P2/P3 — остановить цикл, дать Арту короткий список оставшихся замечаний с рекомендацией и оставить решение о merge ему. Вердикт ревьюера вида «no major issues / LGTM / Swish» — финальный зелёный свет: новые круги «на всякий случай» не запускать.
- Контракт с натуры: любой код, который читает/пишет данные внешнего API или чужого сервиса, пишется только после получения настоящего ответа (curl к реальному серверу, тест бэкенда или код донора), сохранённого в тесты как образец. Разбор формата «по памяти» запрещён; для дефектов — сначала красный тест на старом коде, потом фикс.
- Злой самопроход до первого push: для feature — по `references/edge-matrix.md` скила `$feature`; для остальных кодовых правок — тот же список ролями по diff. Цель: внешний ревьюер находит в первом раунде не больше 1–2 замечаний; push неотполированного кода превращает ревью в многочасовой цикл.
- Ревью-в-правило (изменение скилла/чек-листа внутри скилла — только после отдельного прямого разрешения Артёма): если внешний ревьюер нашёл класс ошибки, который можно было поймать локальным чек-листом, — после починки добавить одну строку в соответствующий чек-лист (edge-matrix или локальный скил) в тот же день. Каждый класс ошибки внешнее ревью находит максимум один раз.
- Живой прод после merge: если в репозитории настроен автодеплой, merge сам публикует код. Отчёт «готово / работает на сайте» разрешён только после проверки живого продакшена (hash сборки, видимый признак фичи или целевой запрос) — «смерджено + CI зелёный» ≠ «опубликовано». Если прод не обновился, так и сказать и найти почему.
- Причина ≠ симптом: в диагнозе сбоя называть корневую причину — управляемый нами фактор (код, конфиг, окружение, сеть сервера) либо доказанный внешний сбой с доказательствами. «Команда X упала / таймаут Y» — симптом; после симптома продолжать копать до корня без напоминания.
- Новая фича — новый чат: если в длинном треде начинается новая независимая фича, предложи Арту одной строкой открыть новый чат (план в docs/ и history.md переносят контекст). Решение за ним, не настаивать и не повторять.
- **Обязательный post-merge trigger:** однозначное сообщение Арта о завершённом merge (`смерджил`, `merged`, `PR смержен`; `залил` — только когда merge однозначен из контекста) — это команда выполнить `$development-handoff`, а не обычный статус. Распознай trigger до первого ответа; если репозиторий и PR находятся из текущего контекста, не задавай уточняющий вопрос и не отвечай только подтверждением или напоминанием «merge ≠ deploy». В том же ходе проверь live merge, обнови base, выполни cleanup preview и apply только когда dirty/ref проверки подтверждают безопасность, затем проверь checks merge-коммита. Финальный статус — только `ready`, `partial`, `blocked` или `unknown`; `ready` допустим лишь после проверенного результата протокола. Отрицание/вопрос (`ещё не смерджил`, `как смержить?`) trigger не включает, а `стоп/pause` всегда имеет приоритет. Post-merge trigger не разрешает deploy или production-записи.
- A successful merge report does not authorize deploy: deploy always needs its own exact, latest confirmation unless that exact deploy was explicitly authorized in the latest user message.
- If Art says "стоп", "оставь", "не туда", "pause", or "stop", stop immediately; workflow guardrails are for the agent, not for overriding the user.

## Universal Project Context

- Before meaningful work in any repository, start with `project-context-bootstrap` when available: read project rules, memory, history, git state, active PR, blockers, and the next safe action.
- Donor-first: если проект — клон или наследник донора (известные пары: `app_uhoster_svelte` и другие Uhoster/VPS-фронты ← донор `tvoi_vps`; `api.auth.gigma.ru` ← донор `gigma_erp_api`), любую диагностику дефекта, разбор контракта API или вопрос «как это устроено» начинать со сверки с донором — до собственных гипотез, до правок и до вопросов Арту о формате данных. Гипотезу, не сверенную с донором, не предъявлять. Если неясно, есть ли у проекта донор, — спросить об этом одной строкой в уточняющем вопросе.
- When a task can use several skills or workflows, use `project-workflow-router` when available: choose the chain first, then run the selected project-local skills.
- Prefer project-local skills and docs over generic global habits. If a project has no `project-memory.md`, treat that as missing context and offer to create one from the global template only when useful.
- Rule precedence for workflow details: direct user authority and safety constraints -> nearest project `AGENTS.md`/project-local skill -> selected workflow skill such as `$feature` -> generic defaults. Never resolve a conflict by weakening a stricter safety or project gate.
- **Hard-gate answer binding:** если preflight или skill вернул `fail_closed`/`blocked` и запросил разрешение на конкретный риск (например, работу поверх названных dirty-файлов), продолжать запись можно только после нового прямого ответа именно на этот blocker. Согласие на будущие review/PR/merge/deploy, общий приказ «продолжай» без привязки к показанному риску или другая косвенная реплика gate не снимает; задай один короткий повторный вопрос и до ответа ничего не пиши.
- For review, audit, check-up, консилиум, plan-only, or read-only tasks, return a report only; do not edit, commit, push, create PRs, merge, or deploy unless Art explicitly asks to fix.
- If a configured review/CI/deploy gate is unavailable, stale, queued, or unknown, report it as a blocker instead of calling the work ready.

## First-Pass Quality (текстовая дисциплина)

Механический контроллер и Task Lock сняты по решению Арта 09.08.2026: плагин `first-pass-quality` отключён. Не вызывай `quality-control.ps1`, не создавай Task Lock и не упоминай «Quality state». Дисциплина ниже — обязательные текстовые правила.

### Обязательный второй проход

- Перед каждым финальным ответом используй `$self-review-report`, включая уточняющие вопросы, короткие ответы, остановленные, partial, blocked и unknown задачи.
- Выполни один отдельный проход по фактическому результату и черновику ответа; после исправлений разрешён один повторный контроль. Не запускай бесконечный цикл самопроверки.
- Заверши ответ видимым блоком `Саморевью` со статусом `ready`, `partial`, `blocked` или `unknown`; называй фактическую проверку, а не общую фразу без доказательств.
- Второй проход не расширяет полномочия и не отменяет команду остановки. После `стоп`, `оставь`, `не туда`, `pause` или `stop` не продолжай задачу и не вызывай инструменты; проверь только финальный ответ.
- Контроль второго прохода только текстовый. Не создавай и не подключай для него hooks, контроллеры, state-файлы, маркеры или фоновые процессы без нового прямого разрешения Арта.

- Границы задачи фиксируй словами в начале работы (для фич — в plan-doc): что делаем, где границы записи, что явно «вне scope», критерий готовности (DoneWhen).
- После нового ввода или сжатия контекста одной строкой сверь: сообщение заменяет задачу, расширяет её или только спрашивает статус; перечитай запреты «вне scope».
- Evidence rule: не заявляй «проверено/готово» без доказательства от последнего успешного прогона проверок на актуальном содержимом; новая правка файла обнуляет прежние зелёные результаты; новый push всегда заново открывает review.
- Final status rule: завершай задачу явным статусом `ready` / `partial` / `blocked` / `unknown`. `ready` — только после пройденных проверок и self-review; иначе честно назови ограничение и следующий шаг.
- Production rule: merge, force-push, deploy, деньги, изменение внешних данных и raw-shell мутации production — только по явному подтверждению в последней реплике Арта; подтверждение действует в пределах названной задачи, среды и семейства команд и истекает при смене scope, следующем prompt или неизвестном исходе. При неизвестном исходе — стоп без слепого повтора.
- Failed-write rule: после неудачной или неизвестной записи — пауза мутаций, проверь фактическое состояние чтением, потом продолжай.
- Delegation rule: агент может самостоятельно привлекать субагентов и выполнять независимые подзадачи параллельно, когда это полезно для текущей задачи; отдельная просьба Арта не требуется. Делегирование не расширяет согласованные полномочия. Результат делегата родитель проверяет сам (чтение/тест) до финальной готовности.

### Делегирование без дублирования

- По прямому решению Art основной агент координирует выполнение: любую задачу сам разбивает на небольшие конкретные проверяемые подзадачи и поручает их субагентам Luna High. Если подзадача ещё сложная, основной агент дополнительно её разбивает; сложность или архитектурность не служат исключением для самостоятельного исполнения. Основной агент задаёт цель и границы, проверяет результаты, сводит их и отвечает за итог. Обязательные независимые ревью, проверки и ограничения выбранного процесса сохраняются.
- Параллельно поручай только независимые участки с разными обязанностями и без конфликтующих записей. Число помощников определяется такими участками и доступными возможностями; фиксированный лимит ради экономии не вводится.
- Перед запуском сформулируй краткое самодостаточное поручение: цель, область ответственности и точные файлы, разрешения и запреты, уже проверенные факты, ожидаемый результат и способ его проверки. Передай применимые ограничения Art; не расширяй права делегата. Для нового субагента используй изолированный контекст (`fork_turns="none"`, когда этот параметр поддерживается), без копирования всей истории чата.
- Для всех субагентов-исполнителей задач и подзадач обязательно указывай `model="gpt-6-luna"`, `reasoning_effort="high"` и `fork_turns="none"`. При недоступности Luna сообщи конкретную причину; не подменяй модель молча и не выдавай другую модель за Luna. Для обязательного независимого ревью выбирай модель и глубину рассуждений по сложности и риску с соблюдением требований выбранного процесса. Оценивай весь путь до проверенного результата, включая переделки.
- Продолжение той же работы и исправления возвращай знакомому с ней исполнителю через `followup_task` или доступный аналог. Новый исполнитель нужен при недоступности прежнего, другой специализации либо повторном отсутствии прогресса; передай ему прежние попытки. Независимое ревью оставляй отдельной ролью по выбранному процессу. Не создавай дублирующую цепочку ревьюеров для уже назначенной проверки.
- Собирай известные замечания в пакет. Повторная проверка охватывает исправления, их последствия и выявленные риски; полный проход выполняется по требованиям проекта или обоснованному изменению риска. Не повторяй неизменившийся bootstrap, чтение инструкций и уже подтверждённые проверки без новой причины; после изменений проверяй затронутое. Обязательные проектные, CI и внешние review gates сохраняются.
- Пилот экономии оценивается по существующим журналам пяти ближайших сопоставимых задач после согласования этого раздела: расход основного агента и помощников (если доступен), повторные исправления, поздние дефекты и время до принятого результата отдельно от ожидания пользователя и CI. Сравнивай с доступными журналами сопоставимых задач до изменения; при недостатке данных результат экономии — `unknown`. Долю токенов не выдавай за долю денег или потерь; до сравнения не объявляй экономию доказанной. Новые фоновые процессы, контроллеры, state-файлы и изменения настроек пилот сам по себе не разрешает.

## MAX / Local API Direction

- In `Max_api`, Art's default goal is product-ready local MAX integration for his desktop account without UI automation. Do not pivot to official bot API unless Art explicitly asks for bot-based sending.
- When Art asks to send a MAX message without saying "bot", interpret it as desktop bridge only. Do not check bot tokens, suggest bot API, or report bot API blockers in that flow.
- For MAX messaging, never pretend a message was sent. If credentials, recipient identity, or transport proof are missing, stop and report the exact blocker.
- Do not call MAX work "product-ready" unless the local personal-account send path works end-to-end: prepare -> verify recipient -> explicit confirm -> real local transport send -> matched `PacketResponse Code: 0x40` with same target/cid/message id. Read-only probes, diagnostics, draft builders, and disabled backends are only milestones, not product-ready sending.
- Treat bot API as a secondary optional backend, not the main product direction. The main research path is local no-UI packet/protocol work around MAX desktop logs and `Code: 0x40`.
- Prefer production-safe guardrails by default: read-only probes first, explicit confirmation, no token extraction, no MITM, no process injection, no coordinate-based UI sending.
- Remember the product-ready chain for local MAX sending:
  1. Read-only packet probe from desktop logs.
  2. Transport correlation for `Code: 0x40` using timestamps, `Seq`, `cid`, and safe packet types.
  3. Local packet draft builder that never sends.
  4. Verification against stable `chatId`, expected title/type, allowlist, generated `cid`, and message hash.
  5. Explicit confirm gate.
  6. Real send only through the discovered local transport, never UI.
  7. Success only after matching `PacketResponse Code: 0x40` with same target, `cid`, and returned `message.id`.
  8. Unknown outcome must stop in `delivery_unknown` and must not auto-retry.
