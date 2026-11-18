# Gigma Skills и Fable 5 — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** устранить шесть подтверждённых дефектов синхронизации, диагностики, установки и оценки активации, затем проверить согласованную связку Fable/Superpowers на закреплённой версии.

**Architecture:** сохранить существующие каталоги, интерфейсы и границы двух репозиториев. Исправления Fable выполнять в его upstream; в Gigma Skills менять собственные скрипты и профиль, а ссылку на исправленный Fable обновлять отдельным завершающим изменением. Для статусов `ready`, `passed` и `rolled_back` требовать доказательство фактического текущего состояния.

**Tech Stack:** Bash, Python 3.12 в CI, Node.js >=20, node:test, unittest, MCP SDK из существующего lock-файла, GitHub Actions.

**Spec:** [Review requirements](#review-requirements) в этом же документе: результаты ревью, наблюдаемые сценарии и инварианты. Исполнитель читает этот раздел до задач.

**Дата:** 19 ноября 2026, Asia/Bangkok.

**Статус:** план подготовлен по завершённому ревью; исправления ещё не реализованы. Текущий PR добавляет только этот документ. Его публикация не означает запуск реализации, merge, deploy, смену пользовательского профиля или создание расписаний.

## Global Constraints

- Источник локальных скиллов — `plugins/`; `.codex/skills/` и `.codex/reference/` остаются генерируемыми зеркалами.
- Внешний Fable остаётся полным upstream-пакетом. Не копировать его код или отдельный `SKILL.md` в новый локальный канон Gigma Skills.
- Сохранить пользовательские скиллы, отключения, настройки, чужие плагины, авторизации и конкурентные изменения. Не считать совпадение имени доказательством принадлежности.
- В нативном режиме обязательны согласованные discovery/read/status для одного проекта, выбранного источника и содержимого. Режим `chatgpt_github` не подменяет неудачную нативную активацию.
- Сохранить Superpowers `7.0.2` на SHA `22f0b463e7a5e579904dd6211a520321035526f7`; изменение этой зависимости не требуется для шести исправлений.
- Новые зависимости и общая переработка архитектуры не требуются. Не менять исходный архив Fable, защищённые файлы и их контрольные значения ради прохождения проверок.
- Изменение содержимого поставляемого плагина требует новой версии. Версия и SHA внешнего источника обновляются согласованно в lock и применимых runtime-каталогах. Не добавлять Fable или Superpowers в Claude-каталог ради симметрии.
- Тесты установки и обновления выполняются во временных каталогах и профилях. Живой пользовательский `CODEX_HOME` не является тестовым стендом.
- После каждой содержательной правки нужны свежие относящиеся к ней проверки. Пропуск, недоступный runtime и отсутствие результата не считаются успешной проверкой.
- Делегированный исполнитель: `gpt-6.1-terra/high`, независимый рецензент: `gpt-6.1-sol/xhigh`; для обоих `fork_turns=none`, если реализация ведётся по прочитанной Fable 1.4.0. Проверить доступность перед назначением; не подменять роль молча.
- Право на commit/push/PR, merge и deploy проверяется отдельно по актуальной задаче. Пункты ниже описывают будущую реализацию и не дают самостоятельного разрешения на внешние действия.

## Review Focus

1. Личный каталог с тем же именем и набором файлов, но другими байтами: остаётся неизменным без `--adopt`; Task 1.
2. Несколько правил включения/отключения одного скилла, разные селекторы и порядок: применяется итоговая разрешённая конфигурация; Task 2.
3. Нестандартный профиль при наличии похожей копии в профиле по умолчанию: проверяется именно установленный кандидат; Task 3.
4. Поздний `blocked`, partial/error или смена каталога после `ready`, включая повторное делегирование: прежнее доказательство больше не действует; Task 5.
5. Ошибка файловой системы при завершении установки, повторный запуск и конкурентная правка: результат соответствует фактическому состоянию, чужие данные сохранены; Task 6.

---

## Review requirements

### Проверенные источники

| Репозиторий | Версия / роль | Снимок ревью |
| --- | --- | --- |
| `Artypoul/Gigma_skills` | реестр, sync, профиль, оценщик | [`4db7fda7da1ba36c118c74ec983dcb42e2b7f2a0`](https://github.com/Artypoul/Gigma_skills/tree/4db7fda7da1ba36c118c74ec983dcb42e2b7f2a0) |
| `Artypoul/claude-fable-5-system-prompt` | Fable 5, пакет `1.4.0` | [`2cf4d13bea89a895d07f15036c5df9a92f950d71`](https://github.com/Artypoul/claude-fable-5-system-prompt/tree/2cf4d13bea89a895d07f15036c5df9a92f950d71) |
| `obra/superpowers` | `7.0.2`, обязательная зависимость | [`22f0b463e7a5e579904dd6211a520321035526f7`](https://github.com/obra/superpowers/tree/22f0b463e7a5e579904dd6211a520321035526f7) |

При подготовке плана Gigma `main` оставался на снимке ревью. Fable `main` — merge-коммит `f08b46081a5f415d1a03ecc1b69f915eb45a1373`; [сравнение с закреплённой ревизией](https://github.com/Artypoul/claude-fable-5-system-prompt/compare/2cf4d13bea89a895d07f15036c5df9a92f950d71...f08b46081a5f415d1a03ecc1b69f915eb45a1373) не содержит изменённых файлов. Перед реализацией заново сверить текущие ветки и затронутые функции; не переносить доказательства на изменённый код автоматически.

### Подтверждённые дефекты

| ID | Приоритет | Наблюдение | Требуемый результат |
| --- | --- | --- | --- |
| F1 | P1 | Неуправляемый личный `vps-connect/SKILL.md` с тем же `name:` и списком файлов заменён каноном без `--adopt`; выход `0`, предупреждения нет. | Отличающееся личное содержимое сохраняется; конфликт явно виден. |
| F2 | P2 | При `enabled=false` для `using-superpowers` каталог возвращает его включённым, чтение доступно, статус `ready`, `partial=false`, warnings `0`. | Отключение реально действует; обязательный отключённый скилл не позволяет получить `ready`. |
| F3 | P2 | Дочерний MCP-процесс, запущенный с окружением обновлятора, не получает `CODEX_HOME`. Реальный SDK/server находит уникальный скилл только при передаче переменной. | Проверка здоровья использует тот же профиль и тот же установленный пакет. |
| F4 | P2 | README устанавливает `fable5-codex@fable5`; `pipeline-status.mjs` требует `fable5-codex@gigma-skills` и отвергает документированный вариант. | Документированные поддерживаемые установки проходят согласованную проверку, неоднозначность блокируется. |
| F5 | P2 | Последовательность `search → read → ready → blocked → delegate` оценена как `activation_before_delegation=satisfied`, итог `passed`. | Новое отрицательное состояние отменяет прежнюю готовность. |
| F6 | P2 | Ошибка записи `automation-request.json` после `phase=complete` даёт `rolled_back`, но плагин остаётся включённым, удаление не вызывается. | `rolled_back` возвращается только после подтверждённого восстановления. |

Исходники: [F1](https://github.com/Artypoul/Gigma_skills/blob/4db7fda7da1ba36c118c74ec983dcb42e2b7f2a0/sync-claude.sh#L67-L102), [F2](https://github.com/Artypoul/claude-fable-5-system-prompt/blob/2cf4d13bea89a895d07f15036c5df9a92f950d71/mcp/src/catalog.mjs#L340-L463), [F3](https://github.com/Artypoul/claude-fable-5-system-prompt/blob/2cf4d13bea89a895d07f15036c5df9a92f950d71/mcp/src/update-native.mjs#L769-L855), [F4: установка](https://github.com/Artypoul/claude-fable-5-system-prompt/blob/2cf4d13bea89a895d07f15036c5df9a92f950d71/README.md#L56-L76), [F4: диагностика](https://github.com/Artypoul/claude-fable-5-system-prompt/blob/2cf4d13bea89a895d07f15036c5df9a92f950d71/mcp/src/pipeline-status.mjs#L3-L18), [F5](https://github.com/Artypoul/Gigma_skills/blob/4db7fda7da1ba36c118c74ec983dcb42e2b7f2a0/codex-profile/fable-superpowers/scripts/updater/resources/appserver_eval.py#L518-L577), [F6](https://github.com/Artypoul/Gigma_skills/blob/4db7fda7da1ba36c118c74ec983dcb42e2b7f2a0/codex-profile/fable-superpowers/scripts/bootstrap.py#L415-L429).

### Границы доказательств

- F1/F2 воспроизведены во временных каталогах с настоящими файлами инструкций. F3 проверен реальным SDK-транспортом и собранным сервером; полный native update пользовательского профиля не выполнялся.
- F4 проверен вызовом диагностики с документированной identity. F5 — воспроизведением потока событий в существующем оценщике. Для F6 использована настоящая ошибка файловой системы и тестовый backend установки.
- R1: правило профиля и native-инструкции Fable допускают только `superpowers@gigma-skills`, а compatibility runner включает `superpowers@fable-superpowers-compat-<hash>`. Противоречие в [инструкции профиля](https://github.com/Artypoul/Gigma_skills/blob/4db7fda7da1ba36c118c74ec983dcb42e2b7f2a0/codex-profile/fable-superpowers/assets/cooperation-AGENTS.md#L11-L16), [Fable SKILL.md](https://github.com/Artypoul/claude-fable-5-system-prompt/blob/2cf4d13bea89a895d07f15036c5df9a92f950d71/.agents/skills/fable5-codex/SKILL.md#L42-L73) и [конфигурации](https://github.com/Artypoul/Gigma_skills/blob/4db7fda7da1ba36c118c74ec983dcb42e2b7f2a0/codex-profile/fable-superpowers/scripts/updater/compatibility.py#L250-L260) подтверждено; отказ живой модели пока не наблюдался. Это отдельный риск, не седьмой подтверждённый дефект.
- Подозрение на отсутствие повышения версий H2D/first-pass-quality снято после сравнения опубликованных merge-снимков. Не включать его в исправления.
- В исходном ревью прошли 437 тестовых случаев, 12 были пропущены. Это базовая линия прежнего кода, а не доказательство исправлений. [CI Gigma](https://github.com/Artypoul/Gigma_skills/actions/runs/44356158993) и [CI Fable](https://github.com/Artypoul/claude-fable-5-system-prompt/actions/runs/44355317304) относятся к тем же исходным снимкам.
- Сохранённые оценки действий модели не заменяют живую установку, активацию в текущем чате, сохранение Project settings или проверку наследования новым чатом.

## Границы файлов и поставки

| Часть | Репозиторий | Основные файлы | Ответственность |
| --- | --- | --- | --- |
| A | Gigma Skills | `sync-claude.sh`, новый `tests/test_sync_claude.py` | сохранность личного содержимого |
| B | Fable | `mcp/src/catalog.mjs`, `mcp/src/update-native.mjs`, `mcp/src/pipeline-status.mjs`, связанные `mcp/test/*.test.mjs` | эффективный каталог, профиль health, поддерживаемые identities |
| C | Gigma Skills | `codex-profile/fable-superpowers/scripts/bootstrap.py`, `scripts/updater/resources/appserver_eval.py`, `scripts/updater/compatibility.py` внутри профиля, тесты и policy asset | правдивые результаты транзакции/оценки и изоляция compatibility |
| D | Fable, затем Gigma Skills | manifests/build artifacts Fable; `external-plugins.lock.json`, `.agents/plugins/marketplace.json`, evidence document Gigma | новая версия, закрепление принятого upstream, итоговая проверка |

Пути в задачах ниже относительны к указанному репозиторию. Каждый существующий тест расширяется по его текущему соглашению о fixtures; не создавать второй тестовый framework. Сначала поставляется независимое исправление F1, затем части B/C, затем D. Части B/C можно выполнять параллельно в разных ветках; D зависит от обеих.

## Task 1: F1 — сохранить неуправляемые личные скиллы

**Repository:** Gigma Skills.

**Files:** Modify `sync-claude.sh`; Create `tests/test_sync_claude.py`. Существующий CI уже запускает `tests/test_*.py`, отдельный job не нужен.

**Interfaces:** сохранить CLI `--dest`, `--plugin`, `--adopt` и формат управляемого списка. Изменить только распознавание неуправляемой копии и связанное сообщение о конфликте. Копия без ownership принимается автоматически лишь при одинаковом наборе допустимых файлов и побайтовом равенстве содержимого; generated `__pycache__` не участвует, как и сейчас.

- [ ] Добавить `test_unmanaged_same_name_changed_content_is_preserved`: временный `--dest`, один личный `vps-connect/SKILL.md`, managed-списка нет. После запуска байты исходного файла равны исходным, имя не присвоено синхронизатором, конфликт указан в выводе; exit code `3` по существующему контракту конфликтов.
- [ ] Добавить положительные случаи: идентичная неуправляемая копия принимается; ранее управляемая копия обновляется; явно указанный `--adopt` разрешает замену. Добавить личный дополнительный файл: он остаётся на месте без adoption. При `--plugin X --prune` managed-скиллы остальных канонических плагинов сохраняются.
- [ ] Запустить `python -B -m unittest discover -s tests -p 'test_sync_claude.py' -v`; основной отрицательный сценарий должен выявлять потерю исходных байтов на baseline.
- [ ] Заменить эвристику `looks_like_our_copy` доказательством равенства содержимого либо явного владения. Не менять unrelated reference sync и pruning.
- [ ] Повторить focused suite и `python -B -m unittest discover -s tests -p 'test_*.py'`; ожидание — все случаи проходят, личный каталог сохранён.
- [ ] Проверить diff, получить независимое ревью и оформить отдельный commit `fix: preserve unmanaged personal skills during Claude sync`, когда commit разрешён задачей реализации.

## Task 2: F2 — учитывать индивидуальное отключение скиллов

**Repository:** Fable.

**Files:** Modify `mcp/src/catalog.mjs`, `mcp/test/catalog.test.mjs`, `mcp/test/pipeline-status.test.mjs`; затронутые проверки `mcp/test/search.test.mjs` / `mcp/test/protocol.test.mjs` — только если нужна проверка публичного search/read контракта.

**Interfaces:** сохранить `fetchConfiguredCatalog(cwd, options)`, `parseCatalog` и форматы search/read/status. Учитывать `skills.config` после обнаружения кандидатов, перед публикацией итогового каталога. Сохранить provenance плагина при повторном добавлении того же пути. Индивидуальное включение не должно самостоятельно включать отключённый плагин.

- [ ] Добавить тесты `configured catalogue applies disabled skill path`, `configured catalogue applies disabled skill name` и `configured catalogue uses the last matching skill rule` для repo/user/plugin discovery и повторного обнаружения нормализованного пути. Сверить поддерживаемые селекторы и порядок с официальным контрактом текущего host и native fixture; неизвестную форму не интерпретировать как разрешение.
- [ ] Зафиксировать assertions: отключённая запись отсутствует среди доступных включённых скиллов; старый ID не позволяет читать отключённый файл после повторного discovery; позднее явное разрешение восстанавливает доступ, сохраняя `plugin_id` и нормализованный путь.
- [ ] Добавить интеграционный случай: enabled Fable/Superpowers, реальные три обязательных `SKILL.md`, индивидуально disabled `using-superpowers`; диагностика должна отклонить готовность, а не вернуть `ready`.
- [ ] Из каталога `mcp/` запустить `node --test test/catalog.test.mjs test/pipeline-status.test.mjs`; убедиться, что новые негативные случаи падают по ожидаемой причине.
- [ ] Реализовать итоговое состояние по правилам конфигурации; сравнивать канонические пути, не выбирать кэш как замену явно отключённому источнику. Не добавлять новый TOML-парсер или зависимость без необходимости.
- [ ] Повторить targeted tests и `npm test`; проверить, что неоднозначный/неполный каталог по-прежнему не становится готовым.
- [ ] Проверить diff и оформить отдельный проверенный commit `fix: honor effective skill enablement in MCP catalogue` при разрешённой реализации.

## Task 3: F3 — привязать health к выбранному профилю и установленным байтам

**Repository:** Fable.

**Files:** Modify `mcp/src/update-native.mjs`, `mcp/test/update-native.test.mjs`. Генерируемые `mcp/dist/*` обновляются штатным build, не вручную.

**Interfaces:** сохранить `NativeBackend.health(installed, project, files)`. Дочерний `StdioClientTransport` получает тот же абсолютный `CODEX_HOME`, что и native-проверки; при отсутствии override сохраняется стандартное поведение. Не передавать весь `process.env` без разбора. Сохранить `FABLE5_CODEX_BIN`.

- [ ] Добавить `health MCP uses the custom CODEX_HOME`: временные профиль/проект и реальный дочерний bundled MCP; уникальный скилл есть только в выбранном профиле. Проверять границу процесса, не только прямой вызов `fetchConfiguredCatalog`.
- [ ] Добавить `health rejects a matching identity from another installation`: в другом профиле лежит одноимённая копия, но `skill.path`/digest не соответствуют `installed.path` и `files`; ожидание — `HEALTH_FAILED`.
- [ ] Добавить позитивный вариант с корректными profile/path/digest и вариант без `CODEX_HOME`. В тестах восстанавливать environment и закрывать транспорт даже при исключении.
- [ ] Из `mcp/` выполнить `npm run build`, затем `node --test test/update-native.test.mjs`; на baseline профильный негативный сценарий должен обнаруживать неверный каталог.
- [ ] Исправить передачу профиля; сверять MCP discovery/read с конкретным установленным `SKILL.md`, фактическим digest кандидата и выбранной identity. Не менять native source/marketplace и авторизацию.
- [ ] Повторить build и targeted tests; затем `npm test`. Убедиться, что одинаковое имя/identity в постороннем каталоге не даёт успешного health.
- [ ] Оформить проверенный commit `fix: bind updater health to the active Codex profile` при разрешённой реализации.

## Task 4: F4 — согласовать две существующие identity Fable

**Repository:** Fable.

**Files:** Modify `mcp/src/pipeline-status.mjs`, `mcp/test/pipeline-status.test.mjs`, `README.md`, `PLUGIN.md`, `MCP.md`, `.agents/skills/fable5-codex/SKILL.md`, `.agents/skills/fable5-codex/references/tools-and-mcp.md`. Extend `tests/test_codex_port.py` / `tests/test_pipeline_control.py` только в части проверяемого контракта активации. `SAFE_UPDATE.md` менять лишь в описании применимости существующего standalone updater, если оно противоречит принятому маршруту.

**Interfaces:** сохранить форму ответа status и экспортируемые контракты. Поддержать ровно один активный проверенный Fable из закрытого множества `{fable5-codex@fable5, fable5-codex@gigma-skills}`; сохранить в ответе реально выбранную identity/path/digest. Superpowers остаётся только `superpowers@gigma-skills`. Две одновременно активные копии Fable, неизвестный marketplace или несовпадение доказательств блокируют готовность.

**Решение совместимости:** сохранить оба уже документированных/используемых источника. Не переименовывать установленный плагин, не мигрировать каталог автоматически и не ослаблять проверку до совпадения имени. Standalone updater сохраняет свою текущую identity `@fable5`; обновление закреплённого Fable в Gigma выполняется через Task 8, а не перенастройкой standalone updater на другой репозиторий.

- [ ] Добавить табличные status-тесты: только `@fable5` → ready; только `@gigma-skills` → ready; обе включены → not ready; неизвестный `@other` → not ready; правильное имя с чужим path/digest → not ready; disabled copy не заменяет активный источник.
- [ ] Для обоих позитивных случаев требовать полный matching search/read/status и неизменные identity/path/digest. Проверить, что отсутствие либо отключение обязательного Superpowers по-прежнему блокирует ready.
- [ ] Запустить `node --test test/pipeline-status.test.mjs` из `mcp/`; случай с документированным `@fable5` должен обнаруживать исходную несовместимость.
- [ ] Согласованно изменить диагностику и все перечисленные native-инструкции. Чтение через GitHub не должно становиться доказательством enabled-identity; условия `chatgpt_github` оставить прежними.
- [ ] Прогнать `rg -n 'fable5-codex@(gigma-skills|fable5)' README.md PLUGIN.md MCP.md SAFE_UPDATE.md .agents/skills/fable5-codex mcp/src/pipeline-status.mjs` и вручную проверить, что каждый жёсткий идентификатор имеет корректную область действия.
- [ ] Выполнить `python -B scripts/verify_codex_skill.py`, `python -B -m unittest discover -s tests`, затем build/`npm test` в `mcp/`. Обновлять только относящиеся к изменённому контракту ожидания; не подделывать сохранённые model observations под новый результат.
- [ ] Оформить проверенный commit `fix: align supported Fable installation identities` при разрешённой реализации.

## Task 5: F5 — отменять устаревшее доказательство активации

**Repository:** Gigma Skills.

**Files:** Modify `codex-profile/fable-superpowers/scripts/updater/resources/appserver_eval.py`, `codex-profile/tests/test_agent_acceptance_eval.py`.

**Interfaces:** сохранить `assess_observation(...)` и структуру `criteria.activation_before_delegation`. Использовать существующие `AcceptanceTests.activation_events()` и `observation()`. Оценивать доказательства по порядку событий в той же сессии и `cwd`, а не искать любое прежнее успешное состояние.

- [ ] Добавить `test_blocked_status_invalidates_prior_activation`: вставить завершённый `fable_status(status='blocked')` между valid ready и delegate; assert итог `failed` и критерий не `satisfied`.
- [ ] Добавить варианты позднего partial/warning/error, смены каталога или выбранной identity, а также двух делегирований с invalidation между ними; ни одно затронутое делегирование не принимается по старой цепочке.
- [ ] Добавить `test_fresh_complete_activation_after_blocked_is_accepted`: после invalidation есть новая полная согласованная цепочка до delegate; assert `passed`. События другого `cwd`/thread не подтверждают и не отменяют текущую активацию.
- [ ] Выполнить `python -B -m unittest discover -s codex-profile/tests -p 'test_agent_acceptance_eval.py' -v`; новый blocked-case должен падать на baseline.
- [ ] Изменить локальную логику оценки: каждое отменяющее событие инвалидирует прежнюю цепочку; проверять каждый относящийся к критерию момент делегирования. Сохранить строгую проверку полного чтения, digest и identity.
- [ ] Повторить suite; проверить существующие `test_complete_activation_order_requires_real_matching_receipts` и `test_early_delegation_cannot_be_fixed_by_later_activation`.
- [ ] Оформить проверенный commit `fix: invalidate stale activation receipts before delegation` при разрешённой реализации.

## Task 6: F6 — завершать транзакцию после подготовки результата установки

**Repository:** Gigma Skills.

**Files:** Modify `codex-profile/fable-superpowers/scripts/bootstrap.py`, `codex-profile/tests/test_fable_superpowers_bootstrap.py`.

**Interfaces:** сохранить `Setup.install()`, `automation(factory)` и существующие успешные поля ответа. Выбранный подход — подготовить локальный automation request и возвращаемый payload до последнего перехода `phase='complete'`. Создание реального расписания остаётся отдельной операцией. Не добавлять новый успешный статус, который прежние callers могут неверно интерпретировать.

- [ ] В `SetupTests` добавить `test_automation_request_write_failure_rolls_back_owned_install`: создать каталог на месте `automation-request.json`, вызвать fresh install. Assertions: при `rolled_back` новая owned-установка действительно удалена, исходные настройки восстановлены, Fable и чужие плагины не изменены.
- [ ] Добавить тест исключения factory до записи и тест ошибки финального journal write после подготовки request. Сохранить исходные байты прежнего request либо удалить только доказанно созданный этой транзакцией файл; конкурентно изменённый файл не перезаписывать.
- [ ] Добавить повторный запуск после ошибки: он не использует оставшееся доказательство успешной установки, если context уже не совпадает; успешная повторная установка по-прежнему возвращает ожидаемые `automation`/`automation_request_path`.
- [ ] Выполнить `python -B -m unittest discover -s codex-profile/tests -p 'test_fable_superpowers_bootstrap.py' -v`; baseline должен выявлять ложный `rolled_back`.
- [ ] Перенести подготовку request/payload до complete; учесть принадлежность и прежнее содержимое создаваемого локального request в существующем восстановлении. Финальная запись complete — последняя fallible операция перед возвратом подготовленного результата.
- [ ] Проверить fresh install, existing install, health failure, interruption и конфликт восстановления. Ошибка request в `validate_existing()` сохраняет уже установленный плагин и не называется rollback. Если восстановление новой установки не подтверждено, сохранить `recovery_required`/ошибку; не возвращать `rolled_back`.
- [ ] Повторить focused suite и все `codex-profile/tests`; оформить проверенный commit `fix: report bootstrap rollback only after actual recovery` при разрешённой реализации.

## Task 7: R1 — проверить и согласовать изолированный compatibility source

**Repositories:** Gigma Skills; Fable — только для согласования относящихся к испытанию инструкций после проверки. Это проверка подтверждённого противоречия, а не объявление наблюдавшегося отказа модели.

**Files, Gigma:** `codex-profile/fable-superpowers/scripts/updater/compatibility.py`, `codex-profile/fable-superpowers/scripts/updater/test_compatibility.py`, `codex-profile/fable-superpowers/assets/cooperation-AGENTS.md`, связанные policy tests `codex-profile/tests/test_fable_superpowers_policy.py`. **Files, Fable:** `.agents/skills/fable5-codex/SKILL.md`, `.agents/skills/fable5-codex/references/tools-and-mcp.md` и `MCP.md` только в части явно выбранного изолированного испытания. Не вводить глобальное разрешение других marketplace.

**Interfaces:** сохранить `staging_plugin_id(candidate)`, `_project_config(stage_id, active_plugin_ids)` и `prepare_fixtures(...)`. Разрешение временной identity действует только внутри проверяемого fixture, для конкретного кандидата и его fingerprint. В рабочем профиле правило `superpowers@gigma-skills` остаётся обязательным.

- [ ] До изменения инструкций выполнить ограниченный native trial существующего кандидата при доступном авторизованном runtime; записать, какие инструкции прочитаны и где возникает противоречие. Если runtime недоступен, зафиксировать незакрытый live gate и не выдавать прогноз поведения за наблюдение.
- [ ] Добавить `test_fixture_policy_authorizes_only_the_exact_staged_candidate`: generated instruction содержит точную временную identity, путь и digest кандидата; другой staged hash или чужой source не разрешён.
- [ ] Добавить негативные проверки отсутствующего/изменённого разрешения и изменения candidate после подготовки. Сохранить отключение пользовательских копий только в изолированном тестовом контексте.
- [ ] Запустить `python -B -m unittest -v test_compatibility` из `codex-profile/fable-superpowers/scripts/updater/` и policy suite из корня; подтвердить исходное противоречие проверкой сгенерированных инструкций.
- [ ] Сформировать узкое разрешение тестового источника и правило его области действия; согласовать его с Fable native-инструкциями, если они блокируют выбранное испытание. Проверить, что обычные пользовательские задачи не получают этот exception и production readiness не подтверждается тестовым alias. Если требуется изменение executable status-контракта Fable сверх Tasks 2–4, сначала оформить отдельное решение и тесты, не расширять закрытый список identities молча.
- [ ] При доступном авторизованном runtime выполнить все пять существующих compatibility tasks с реальным агентом и независимым ревью; сохранить candidate/config hashes и исходные observations. Подмена native/model результата fixture-ответом запрещена.
- [ ] Если runtime/нужная модель недоступны, указать точный незакрытый gate; deterministic tests не закрывают требование живого прогона.
- [ ] Оформить проверенный commit `fix: scope compatibility instructions to the staged candidate` при разрешённой реализации.

## Task 8: выпуск Fable и согласованное закрепление в реестре

**Repositories:** сначала Fable, затем Gigma Skills. Depends on Tasks 1–7 для полного результата связки; Fable release зависит непосредственно от Tasks 2–4 и относящейся к Fable части Task 7, если trial показал необходимость её изменения.

**Files, Fable:** `.codex-plugin/plugin.json`, `.agents/plugins/marketplace.json`, штатные `mcp/dist/server.mjs`, `mcp/dist/update.mjs`, `mcp/dist/build-info.json`, относящиеся к выпуску notes в существующих документах. Версию `mcp/package.json` не приравнивать механически к версии плагина: у этого внутреннего пакета отдельная нумерация.

**Files, Gigma:** `external-plugins.lock.json`, `.agents/plugins/marketplace.json`; Create `docs/verification/marketplace-fable-quality-2026-11-19.md` при реализации. Обновлять другие документы только при наличии реально изменившегося договора поставки.

**Interfaces:** результат upstream-этапа — пара `FABLE_RELEASE_VERSION` и полный 40-символьный `FABLE_RELEASE_SHA` принятого commit с проверенным содержимым. Это выход этапа, а не разрешение использовать плавающий `main`. При неизменившемся baseline целевая patch-версия — `1.4.1`; если к реализации она занята, выбрать следующую свободную patch-версию текущей совместимой линии и явно записать причину.

- [ ] В Fable поднять версию плагина согласованно в manifests, выполнить `npm ci`, `npm run build`, `npm test` из `mcp/`; запустить Python structural/package suites из корня. Собрать пакет штатным `scripts/package_plugin.py` согласно его актуальной CLI.
- [ ] Проверить diff поставляемых файлов, независимое ревью и CI точного upstream head. Зафиксировать release version/SHA; merge/publication выполнять только при отдельном разрешении соответствующей задачи.
- [ ] В Gigma заменить только Fable version/SHA в lock и Codex marketplace. Superpowers и gigma-mcp сохраняют свои значения; Claude marketplace не получает новый Fable entry.
- [ ] Выполнить `python -B validate_plugin.py`, `python -B -m unittest discover -s tests -p 'test_*.py'`, полный `codex-profile/tests` и updater suites. Проверить, что checkout/read всех обязательных файлов происходит по новому SHA и совпадает с manifest version.
- [ ] В изолированном профиле проверить установку и ordered native activation для каждой поддерживаемой Fable identity; отдельно индивидуальное отключение `using-superpowers` должно блокировать ready. Проверить обычный и custom `CODEX_HOME`, затем обновление/rollback по поддерживаемому маршруту.
- [ ] Отдельно повторить `chatgpt_github`: чтение реестра, manifests, полного основного skill и нужных dependencies по новому pin; отдельно сообщить готовность исходников, наличие task capabilities и непроверенные Project settings/new-chat inheritance.
- [ ] Записать evidence document: точные commits, команды, exit codes, OS/runtime, passed/skipped/blocked, ссылки на CI/review, наблюдения живых сценариев, оставшиеся ограничения. Не переносить прежние «437 passed» на новый release.
- [ ] После последнего push проверить фактический PR diff/head, CI и комментарии/reviews. Реальные блокеры исправить в той же ветке и повторить review cycle. При недоступном автоматическом reviewer провести разрешённое независимое локальное ревью и явно записать ограничение.

## Отдельная последующая работа: измерение пользы Fable

Эта работа не является седьмым дефектом и не блокирует поставку шести исправлений при выполненных gates выше.

Текущий [генератор оценочных заданий](https://github.com/Artypoul/claude-fable-5-system-prompt/blob/2cf4d13bea89a895d07f15036c5df9a92f950d71/scripts/evaluate_behavior.py#L215-L257) заранее сообщает значительную часть ожидаемого поведения. Сохранить эти полезные регрессионные проверки, но не использовать их как единственное доказательство прироста качества на новых задачах.

- [ ] В отдельной согласованной задаче подготовить нераскрытые задания на багфикс, конфигурацию, ревью и исследование; условия не содержат готового порядка действий и требуемых ответов.
- [ ] До запуска зафиксировать критерии корректности, соблюдения scope, полноты результата, времени и количества вызовов инструментов; сохранить модель, effort, доступные tools и лимиты одинаковыми между сравниваемыми режимами.
- [ ] Сравнить базовый режим и Fable на одинаковых заданиях с независимой оценкой артефактов; сохранить сырые разрешённые observations. Не объявлять улучшение на основании одного удачного примера.
- [ ] Описать ограничения выборки и затраты отдельно от качества. Живые model calls и внешние расходы выполнять только в пределах авторизованного запуска.

## Порядок будущих PR и критерии завершения

1. **Gigma A:** Task 1 — самостоятельное исправление риска потери данных.
2. **Fable B:** Tasks 2–4 и upstream-часть Task 8 — каталог, health, identities и новая версия.
3. **Gigma C:** Tasks 5–7 — оценщик, bootstrap, compatibility. Может идти параллельно B.
4. **Gigma D:** registry/evidence-часть Task 8 — pin проверенного Fable и интеграционная проверка связки.

При реализации отдельные commits/PR можно объединить, если сохраняются независимое ревью, доказательства и порядок зависимостей. Нельзя закрыть registry integration до проверки фактического upstream commit.

### Definition of Done для исправлений

- [ ] Все F1–F6 покрыты регрессиями, которые воспроизводили старое поведение и проходят на исправленном коде.
- [ ] Личное содержимое и настройки сохраняются; disabled skill, неверный профиль, неоднозначная identity и устаревший ready не принимаются как готовность.
- [ ] Каждый reported rollback подтверждается фактическим состоянием; ошибки восстановления остаются явно видимыми.
- [ ] R1 проверен в изолированном контексте; отсутствие живого подтверждения отражено как незакрытый gate, а не passed.
- [ ] Поставляемые bundles, manifests и registry pin согласованы; новая версия реально соответствует проверенному содержимому.
- [ ] CI и независимое ревью относятся к последнему изменённому head; открытых блокирующих замечаний нет.
- [ ] Итоговый handoff перечисляет PR/commit, проверки, пропуски, пределы живого покрытия и фактический статус merge/deploy.

### Проверка самого планового PR

Этот PR готов к передаче, когда содержит только данный план, все шесть findings связаны с конкретными задачами и источниками, риски отделены от подтверждённых ошибок, пути/команды сверены с репозиториями, независимое ревью плана учтено, а созданный PR и его checks/reviews прочитаны обратно через GitHub. Готовность плана не означает выполнение Definition of Done для будущих исправлений.
