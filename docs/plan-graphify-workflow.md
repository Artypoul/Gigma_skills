# План: исправить и опубликовать скил Graphify

## Цель

Сделать второй проход по текущему глобальному `graphify-workflow`, исправить подтверждённые неточности и добавить его в существующий `development-workflow` плагин Gigma Skills. После публикации пользователь сможет установить и обнаружить скил обычным способом; он будет направлять агента к реальным Graphify CLI/MCP и проектным launcher'ам, не выдавая статический граф за доказательство runtime-поведения.

## Подтверждённый контекст

- Глобальный скил уже существует и включает `SKILL.md`, `agents/openai.yaml`, а также ссылки на `operations.md`, `process-graph-contracts.md` и условную карту Gigma Work Desktop.
- В Gigma Skills каноническими являются `plugins/`; каталог `development-workflow` уже владеет общими рабочими скилами. Отдельный Graphify-плагин не нужен.
- В каноническом `development-workflow` Graphify-скила пока нет. Версии плагина: Claude `0.4.7`, Codex `0.4.7+codex.20260902130545`; обновить общий базовый уровень до `0.4.8`.
- Текущая формулировка смешивает `graphify install` с установкой CLI. По проверенному контракту Graphify эта команда устанавливает/копирует skill-инструкции, а не бинарник CLI. Универсальные примеры также не должны зависеть от абсолютных путей с локальными именами дисков.
- `sync-codex.sh` пересоздаёт всё зеркало `.codex/skills` и `.codex/reference`. Для этого узкого изменения разрешено обновить только Graphify-зеркало и сверить байтовое равенство с каноном; остальные зеркала не трогать.

## Область работ

- Выполнить и проверить второй проход глобального Graphify-скила: уточнить смысл `graphify install`, определить CLI и MCP из фактического окружения, использовать проектные launcher/критерии свежести, сохранять границу между статическим графом и подтверждённым поведением.
- Удалить машинно-зависимые абсолютные пути из всех распространяемых файлов, включая условную карту Gigma Work Desktop; заменить их поиском корня проекта/окружения через launcher и `<repo-root>`/`<tool-root>`. Сохранить контрольный commit Gigma Work Desktop только как условный исторический пример, применимый при совпадении файлов проекта.
- Перенести исправленный скил и нужные references в `plugins/development-workflow/skills/graphify-workflow/`, добавить метаданные `agents/openai.yaml`.
- Добавить точку обнаружения в оба описания marketplace, Codex manifest/default prompt и соответствующий раздел `AGENTS.md`.
- Обновить только `.codex/skills/graphify-workflow/` и вложенные references, сохранив их точное байтовое соответствие канону.
- Обновить Claude manifest до `0.4.8`, Codex manifest до `0.4.8+codex.<актуальная временная метка>`; базовая версия должна совпадать.
- После локального review плана координатор публикует planning-only PR; planning review-gate должен пройти до реализации. Затем изменения реализуются в той же ветке/PR, проходят свежие тесты и project review/CI; merge выполняется только после зелёных gates. Никаких deploy или production-записей.

## Вне scope

- Не создавать новый плагин и не менять владельца `development-workflow`.
- Не запускать `bash sync-codex.sh`: его широкая перезапись затронет зеркала посторонних скилов.
- Не менять другие глобальные скилы, локальные/установленные plugin caches, зеркала других скилов, каталоги Claude пользователя, hooks, MCP-конфиги или глобальные настройки.
- Не устанавливать/обновлять Graphify CLI, не запускать `graphify install`, не менять приложение Gigma Work Desktop и не обновлять его сгенерированный граф.
- Не добавлять backend/API/БД, сетевые вызовы, новые команды Graphify или неподтверждённые runtime-возможности.

## Переиспользование и размещение

| Существующая часть | Решение |
| --- | --- |
| `plugins/development-workflow` | Каноническое место: Graphify — общая инженерная возможность, не доменная фича Gigma. |
| `project-workflow-router` | Не менять: область записи ограничена Graphify skill и его упаковкой. Обнаружение покрывается plugin metadata/default prompt и каталогом. |
| Глобальные `operations.md` и `process-graph-contracts.md` | Перенести после второго прохода, сохраняя версионные оговорки и отделяя upstream-контракт от локальных расширений. |
| Условная `gigma-work-desktop.md` | Сохранить рядом с Graphify skill только как отдельную карту проекта с явным условием совпадения файлов; не делать её общим default для других репозиториев. |
| `validate_plugin.py` и существующие тесты | Переиспользовать для проверки discovery, метаданных и целостности зеркала. |
| `sync-codex.sh` | Не запускать из-за полного удаления/пересоздания зеркала; добавить только новое зеркало и проверить точные хэши. |

## Что делаем

| Что делаем | Было | Стало | Как делаем | БД | Endpoint / команда |
| --- | --- | --- | --- | --- | --- |
| Исправляем второй проход Graphify-инструкций | `graphify install` описан как CLI-интеграция; переносимый текст содержит машинные пути и отдельные факты версии | Инструкция различает установку skill и CLI, определяет реальную среду/launcher, маркирует version-specific сведения и границы доказательств | Перепроверка установленной документации Graphify и согласованная правка `SKILL.md`/references | БД не меняется | Без endpoint; команды только по фактической операции и версии |
| Добавляем Graphify skill в существующий плагин | В `development-workflow` нет Graphify entry point | Skill, метаданные и ссылки доступны из канонического плагина; проектная карта остаётся условной | Новый `skills/graphify-workflow/` с `SKILL.md`, `agents/openai.yaml`, нужными references | БД не меняется | Без endpoint |
| Делаем skill обнаруживаемым | Plugin manifests, marketplace descriptions и каталог не указывают на Graphify skill | Graphify trigger обнаруживается через описание/metadata плагина и каталог; другие скилы и маршрутизация не меняются | Codex default prompt/interface + оба marketplace description + раздел `AGENTS.md`; общий base version `0.4.8` | БД не меняется | Skill trigger `$graphify-workflow`; без endpoint |
| Синхронизируем ограниченное зеркало | `.codex` строится общей командой, которая переписывает все зеркала | Только новое Graphify-зеркало добавлено и совпадает с каноном | Точечное копирование новых файлов; сравнение списка файлов и SHA-256, без запуска full sync | БД не меняется | `python validate_plugin.py`; без endpoint |
| Публикуем через проверяемый PR | Глобальная инструкция не является частью Gigma Skills; отдельного Graphify PR нет | Исправление проходит planning review, реализационный review и CI до merge | Planning-only Ready-for-review PR, затем изменения на той же ветке и актуальные проверки/re-review | БД не меняется | GitHub PR и CI; merge после зелёных gates |

## Файлы реализации

- `plugins/development-workflow/skills/graphify-workflow/SKILL.md`
- `plugins/development-workflow/skills/graphify-workflow/agents/openai.yaml`
- `plugins/development-workflow/skills/graphify-workflow/references/` — переносимые операции и контракты; проектная карта отдельна и явно условна
- Исправленные исходные файлы глобального `graphify-workflow`: `SKILL.md` и используемые references, включая условную карту Gigma Work Desktop
- `plugins/development-workflow/.codex-plugin/plugin.json`
- `plugins/development-workflow/.claude-plugin/plugin.json`
- `.agents/plugins/marketplace.json`, `.claude-plugin/marketplace.json`
- `AGENTS.md`
- `.codex/skills/graphify-workflow/` — только новый skill bundle, точная копия канона

На плановой фазе изменяется только этот документ; после локального review координатор публикует planning-only PR. Реализация начинается после прохождения planning review-gate.

## Ошибки и совместимость

- CLI, MCP и Graphify `install` — разные возможности; перед использованием проверять реально доступные инструменты и побочные эффекты.
- При существующем Graphify launcher, venv или pinned requirements следовать проектной документации; не менять глобальное окружение.
- Не переносить версия-зависимые Graphify поля, confidence thresholds, schema/API, порты и локальные пути как универсальные defaults.
- Устаревший/неуспешно обновлённый граф не считается свежим; важные связи подтверждать исходным кодом или реальным ответом инструмента.
- Точечное зеркало должно включать все ссылки `SKILL.md`, но не затрагивать остальные файлы `.codex`.

## Проверки реализации

После последней правки выполнить:

```text
python <skill-creator>/scripts/quick_validate.py plugins/development-workflow/skills/graphify-workflow
python validate_plugin.py
python -m unittest discover -s tests -p "test_*.py"
python -m unittest discover -s plugins/development-workflow/tests -p "test_*.py"
git diff --check
```

Дополнительно проверить:

- оба manifest имеют базовую версию `0.4.8`, marketplace-описания содержат trigger;
- новый skill и нужные references перечислены одинаково в каноне и только в целевом `.codex`-зеркале, а их хэши совпадают;
- все распространяемые Graphify-файлы, включая условную карту Desktop, не содержат машинных абсолютных путей и не выдают Gigma-specific конфигурацию за default;
- PR открылся как Ready for review, planning review пройден до кода, а после последнего commit требуемые CI/review checks относятся к актуальному head; merge выполняется только после их успеха.

## DoneWhen

Названная глобальная `graphify-workflow` прошла второй проход; исправленный Graphify skill находится в каноническом `development-workflow`, обнаруживается через plugin metadata/default prompt и каталог, а новое зеркало byte-identical; validators, общий и `development-workflow` unit suites, и `git diff --check` зелёные на последнем diff; planning и code review/CI закрыты для актуального PR head; PR смержен в `main`. Другие глобальные скилы, plugin caches, установки и зеркала остаются нетронутыми.

## Planning review

| Роль | Что проверить |
| --- | --- |
| Корректность Graphify skill | Второй проход устраняет смешение `install`/CLI, ограничивает version-specific утверждения и не выдаёт граф за runtime-доказательство. |
| Упаковка и discovery | Размещение в `development-workflow`, версии, marketplace/default-prompt, references и безопасный точечный mirror. |
| Поддержка и совместимость | Запрет full sync соблюдён; CI и валидатор проверяют только допустимую область без переписывания чужих зеркал. |

Открытых продуктовых решений для планирования не выявлено; переход к реализации — после согласования плана review-ролевыми проверками.
