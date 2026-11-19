# Fable orchestration and task acceptance — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** устранить шесть подтверждённых ошибок установки и оценки результата, затем проверить сохранение и предметную критику продуктовых решений владельца на наблюдаемом поведении.

**Architecture:** сохранить существующие `setup.ps1`, compatibility assessor и app-server collector. Убрать устаревшие source-дубликаты; проверять исходный тестовый контракт, полное чтение и актуальные tests/review по фактическим артефактам. Семантическую приёмку связать с уже существующим независимым hash-bound review, сохраняя неполный статус при отсутствии доказательства.

**Tech Stack:** Python 3.12/unittest, PowerShell 7, Git, существующий Codex app-server collector, GitHub Actions; без нового framework и runtime dependency.

**Spec:** [Второй проход по оркестрации и приёмке](../../verification/fable-orchestration-acceptance-2026-11-19.md). Исполнитель читает отчёт и этот план; A1–A6 и G1–G3 ссылаются на его требования и границы доказательств.

**Дата:** 19 ноября 2026, Asia/Bangkok.

**Статус:** план подготовлен, все implementation tasks открыты. Текущий PR содержит только этот план и отчёт. Публикация планового PR не означает реализацию, merge, native installation или успешную продуктовую приёмку. Договор установки третьей зависимости G1 вынесен в явную развилку Task 7; она не блокирует Tasks 1–6.

## Global Constraints

- Baseline Gigma Skills: `27edb4f405c09ec376441a919ced3b50259c051e`; Fable `1.4.3` / `cb76769f1fce9df196c22b2b708ba8474cbf5aa1`; Superpowers `7.0.2` / `22f0b463e7a5e579904dd6211a520321035526f7`. Перед реализацией сверить актуальный head и уже исправленные пункты; не переносить старый вердикт на новый код.
- Канон локальных скиллов — `plugins/`. `.codex/skills/` и `.codex/reference/` генерируются `bash sync-codex.sh`. Внешние Fable/Superpowers остаются целыми пакетами в исходных репозиториях; source identity не переключается.
- Для A1–A6 не требуется менять Fable/Superpowers pins, архивы или создавать локальную копию upstream skill. Смежный [marketplace/Fable plan](2026-11-19-marketplace-fable-quality.md) относится к более ранним дефектам; не возобновлять его release/pin work автоматически.
- Сохранить пользовательские данные, неуправляемые скиллы, отключения плагинов, выбранный источник, авторизации и чужие правки. Тестировать установку только во временных профилях; использовать параметр `-CodexHome`, не подменять домашний каталог пользователя.
- Обязательные критерии, исходные interfaces и согласованные продуктовые решения не меняются редактированием tests/docs. Разрешённое изменение поведения требует актуального конкретного решения владельца и обновлённого контракта.
- `passed` требует всех обязательных доказательств для текущего артефакта. Отсутствующий reviewer, partial read, unknown check и неисполненный native trial остаются `incomplete`, `blocked` или `held` согласно текущему вызывающему интерфейсу; не превращать их в успех.
- Сохранять Windows confinement и fail-closed preflight. Локальный адаптер из диагностического repro не включается в production-код. Package health и GitHub mode не заменяют same-session native evidence.
- При изменении canonical skill поднять обе версии его plugin manifests и синхронизировать зеркало. У `development-workflow` baseline version `0.4.13`; при неизменившейся линии следующий patch — `0.4.14`. При изменившемся head выбрать следующий свободный patch и записать причину. Удаление устаревших personal copies и документационный PR сами по себе bump не требуют.
- Независимый рецензент: `gpt-6.1-sol/xhigh/fork_turns=none`; делегированный исполнитель: `gpt-6.1-terra/high/fork_turns=none`, если работа продолжается по данному Fable. Недоступность обязательной роли сообщать явно.
- Каждая задача получает свежие RED/GREEN evidence и независимое ревью своего конечного diff. Публикация, merge, live profile changes и внешние расходы следуют фактическому разрешению текущей задачи, а не тексту этого плана.

## Review Focus

1. Уже установленный пользовательский скилл с тем же именем: конфликт источников исправлен, но защита чужого destination не исчезает — Task 1, `test_unmanaged_destination_preserved`.
2. Исполнитель удаляет старый тест, оставляя исправленный пример зелёным: исходное обязательство всё ещё проверяется — Task 2, `test_weakened_author_suite_cannot_hide_baseline_regression`.
3. Два reviewer или несколько их turns противоречат друг другу: частичное/старое approval не закрывает актуальные blocking findings — Task 3, `test_later_rejection_and_other_reviewer_blocker_remain_open`.
4. Файл заменён через copy/rename или изменены только tests после GREEN: прежнее evidence больше не относится к результату — Task 5, `test_post_green_inventory_change_invalidates_evidence`.
5. Владелец отменил одно требование или согласованный продуктовый параметр противоречит полному пользовательскому пути: сохранить остальные требования, показать конфликт, не подменять решение — Task 8, D3/D4/D6/D8.

## Карта файлов и последовательность

| Task | Область | Основные файлы | Независимый результат |
| --- | --- | --- | --- |
| 1 | A1, Standard source ownership | `codex-profile/personal-skills/`, новый `codex-profile/tests/test_standard_profile.py`, `.github/workflows/validate.yml` | Настоящие fresh/update Standard runs проходят с сохранением guards |
| 2 | A2, исходный тестовый контракт | `compatibility.py`, `test_compatibility.py` в updater | Ослабление авторского suite не скрывает исходную регрессию |
| 3 | A3, полное актуальное ревью | Те же файлы; `resources/appserver_eval.py` только при необходимости дополнительных observed receipts | Полный актуальный subject review, все blockers учтены |
| 4 | A4, полное чтение | `compatibility.py`, `test_compatibility.py` | Страницы подтверждают фактический прочитанный source |
| 5 | A6, test target и freshness | Те же файлы; `resources/appserver_eval.py`, `codex-profile/tests/test_agent_acceptance_eval.py` | Evidence связано с реально проверенными конечными байтами |
| 6 | A5, семантика research | Те же assessor/collector tests; новые rubric fixtures | Ошибочная рекомендация отвергается, отсутствие оценки явно открыто |
| 7 | G1, доступность Task Acceptance | `bootstrap.py`, `profile_policy.py`, profile docs, bootstrap/policy tests | Проверенная доступность либо точный незакрытый dependency gap |
| 8 | G2/G3, продуктовая приёмка и handoff | `codex-profile/tests/fixtures/agent_acceptance/`, evaluator tests, evidence docs; optional canonical clarification | D1–D12 проверены в заявленных пределах; текущий head подтверждён |

Здесь и далее `updater/` — `codex-profile/fable-superpowers/scripts/updater/`; `resources/` — его подкаталог. Tasks 2–6 меняют один assessor, поэтому реализации выполнять последовательно, не назначать конкурентных writers одного файла. Task 1 можно делать отдельно. Task 8 использует принятые исправления Tasks 2–6; Task 7 имеет собственную развилку поставки.

---

## Task 1: A1 — убрать устаревшие personal source roots

**Files:** Delete ровно шесть roots в `codex-profile/personal-skills/`: `banquet-image-generation`, `counterparty-audit-investigation`, `figma-cli`, `figma-poster-positioning`, `no-unapproved-product-limits`, `self-review-report` (10 файлов, полный список и владельцы в отчёте). Create `codex-profile/tests/test_standard_profile.py`. Modify `.github/workflows/validate.yml`; `codex-profile/README.md` только в описании актуальных источников установки. `setup.ps1` сохраняет отказ при неизвестном source duplicate и unmanaged destination.

**Interfaces:** production CLI остаётся `pwsh -NoProfile -File codex-profile/setup.ps1 -CodexHome <temporary-path>`; отсутствие `-Workflow` означает Standard. Test helper `run_setup(profile: Path, *extra_args: str) -> subprocess.CompletedProcess[str]` запускает реальный script, не spy. `REQUIRE_STANDARD_PROFILE_PWSH=1` в CI делает отсутствие `pwsh` ошибкой, локальное отсутствие отмечается skip.

- [ ] **RED:** добавить `test_source_skill_names_are_unique`: собрать только каталоги с `SKILL.md` по тем же двум source roots и проверить `duplicates == set()`. На baseline получить ровно шесть имён из Files. Добавить `test_default_install_uses_complete_canonical_trees`, `test_managed_reinstall_is_idempotent`, `test_unmanaged_destination_preserved`, `test_existing_global_agents_preserved`, `test_unknown_source_duplicate_is_rejected` и `test_self_review_helpers_are_present_without_hook_installation`.
- [ ] **Проверить RED:** `python -B -m unittest discover -s codex-profile/tests -p 'test_standard_profile.py' -v`. На исходной версии source inventory и настоящий setup должны падать по collision, а не по отсутствующему runtime.
- [ ] **Исправить:** удалить перечисленные personal roots. Оставить `segment-anything` и все canonical files неизменными. В существующий `fable-superpowers-portable` matrix добавить отдельный запуск нового suite с обязательным `pwsh`; не менять source precedence и не включать hooks.
- [ ] **GREEN:** повторить suite на Windows и Linux с PowerShell. Сверить полный installed file inventory/bytes шести canonical skills, `agent-session-execution`, отдельный `segment-anything`, managed manifest. Новый global AGENTS устанавливается; отличающийся существующий без adoption сохраняется. Чужой destination остаётся неизменным и даёт понятный отказ. Прогнать `test_fable_superpowers_profile.py`, проверить отсутствие diff canonical/mirror/pins.
- [ ] **Review/commit:** независимый reviewer проверяет source ownership и сохранность destination; commit `fix: remove migrated Standard profile skill duplicates`.

## Task 2: A2 — выполнять неизменяемый baseline suite

**Files:** Modify `updater/compatibility.py`, `updater/test_compatibility.py`. Читать исходные `resources/fixtures/bug_fix/tests/` и `resources/fixtures/approved_plan/tests/` как доверенные baseline sources; не изменять их ради прохождения нового теста.

**Interfaces:** добавить `run_baseline_suite(name: str, fixture: Path, codex_home: Path) -> dict` с существующим command-result контрактом `exit_code/stdout/stderr` и дополнительным `baseline_sha256` по упорядоченному path/content inventory. Вызывать из `assess_case` для `bug_fix` и `approved_plan`. Baseline берётся из controller-owned resources до выполнения агента и сверяется перед проверкой; импорты production направлены на кандидатный fixture. Выполнение остаётся через `_fixture_python`, без выхода из confinement. В successful result добавить `immutable_baseline_tests`, сохранив `independent_tests` и `direct_contract_passed`.

- [ ] **RED:** `test_weakened_author_suite_cannot_hide_baseline_regression` использует реализацию A2, авторский suite только для суммы 200 и сохранённый исходный тест `(100,10)==90`; ожидание — `assess_case` отвергает результат. `test_correct_discount_passes_baseline_and_new_tests` использует корректный процент и проходит. `test_changed_baseline_inventory_is_rejected` меняет baseline после фиксации hashes и требует отказ.
- [ ] **Проверить RED:** из updater запустить `python -B -m unittest -v test_compatibility`; новая negative regression должна показать прежний `passed=true`, хотя отдельный baseline suite падает с `100 != 90`.
- [ ] **Исправить:** фиксировать полный исходный test inventory вне writable fixture, выполнять его на финальном кандидате, проверять exit code и факт исполнения ожидаемых tests. Удаление, замена или ослабление авторского теста не изменяют baseline. Для fixture `approved_plan` сохранить уже существующую проверку неизменности утверждённого плана.
- [ ] **GREEN:** новый отрицательный пример отвергается, нормальное исправление проходит baseline, новые tests и direct assertions. Проверить сохранность исходных `invoice_total`/`format_total`. Убедиться, что test runner не запускает случайно прежнюю baseline implementation вместо кандидата.
- [ ] **Review/commit:** reviewer сверяет trusted baseline provenance и production import path; commit `fix: preserve immutable fixture acceptance tests`.

## Task 3: A3 — связывать review с полным текущим предметом проверки

**Files:** Modify `updater/compatibility.py`, `updater/test_compatibility.py`; если collector не сохраняет необходимый receipt, Modify `updater/resources/appserver_eval.py` и `codex-profile/tests/test_agent_acceptance_eval.py`. Не принимать придуманные рецензентом execution receipts за observed events.

**Interfaces:** расширить `review_evidence(native: dict, *, after_event_line: int | None = None, expected_subject: dict | None = None) -> dict`. Для нового strict acceptance `expected_subject` обязателен: `files` — полный sorted path/SHA-256 inventory implementation/tests/APPROVED_PLAN; `criteria_sha256` — digest принятого task contract. Его фиксирует контроллер до reviewer dispatch. Отчёт связан с observed `child_id/turn_id/report_id/event_line`; review coverage и findings сохраняются явно. Старый unbound receipt может быть диагностикой, но не strict pass. Поля `passed`/`reviewers` сохраняются для callers.

- [ ] **RED:** добавить отдельные tests для Approve→Request changes, Request changes→новый полный Approve, Markdown `#### Important (Should Fix)`/Critical, явно исключённых production files и отсутствующего либо непроверенного актуального test evidence. `test_later_rejection_and_other_reviewer_blocker_remain_open` также проверяет два reviewer: второй approval не закрывает первый unresolved blocker. Positive control `test_reviewer_may_verify_current_test_receipts_without_rerun` принимает полный review, в котором reviewer честно не перезапускает tests, но проверяет актуальные command/output/inventory receipts; само отсутствие повторного запуска не является дефектом.
- [ ] **Проверить RED:** из updater `python -B -m unittest -v test_compatibility`; зафиксировать false positives из A3. Negative-only control и существующее требование start после production сохраняются.
- [ ] **Исправить:** оценивать актуальные завершённые verdicts для того же subject; сохранять findings до явного разрешения свежим review соответствующего scope. Неполный scope, неизвестный формат, противоречие approve/finding или неподтверждённый snapshot дают incomplete/rejection. Поддержать фактический формат pinned Superpowers template; для машинной проверки использовать проверяемые поля coverage/finding status, а не только слова `plan`/`test`.
- [ ] **GREEN:** полный свежий review проходит; каждый отрицательный сценарий отклонён с точной причиной. Добавление/удаление/изменение implementation или tests после snapshot открывает gate. Сопоставить hashes при окончательной приёмке с Task 5; до завершения Task 5 не заявлять произвольные shell writes полностью наблюдаемыми.
- [ ] **Review/commit:** отдельный reviewer проверяет циклы нескольких reviewer/turns и отсутствие self-approval; commit `fix: require current complete review evidence`.

## Task 4: A4 — проверять фактическое содержимое страниц read_skill

**Files:** Modify `updater/compatibility.py`, `updater/test_compatibility.py`; использовать уже проверяемые native/catalog identity и provider content contract из `_helper_probe`/`verify_catalog`.

**Interfaces:** сохранить `observed_skill_reads(items: list, expected: dict, fable: dict) -> dict`. Расширить доверенный target record идентификаторами `id`, `plugin_id`, `path`, `sha256` из выбранного catalog receipt и его project/provenance context. Не угадывать ID по имени. Успешная запись остаётся `method=complete_mcp_read` только после проверки всех страниц и содержимого.

- [ ] **RED:** `test_partial_or_warned_mcp_read_is_not_complete`, `test_claimed_hash_cannot_replace_actual_body`, `test_foreign_identity_or_project_is_rejected`, `test_conflicting_pages_are_rejected`. Использовать точный контрпример `content='x', total_chars=1, partial=True, warning_count=1` при ожидаемом hash полного source.
- [ ] **Проверить RED:** из updater `python -B -m unittest -v test_compatibility`; отдельно нормальные paginated read, UTF-8 BOM и CRLF cases продолжают проверять реальный provider contract.
- [ ] **Исправить:** проверять одинаковые identity/hash/total/context для всего read, допустимые offsets, отсутствие разрывов в покрытии страниц и конфликтующих перекрытий, конечную полноту и совпадение реконструированного текста с trusted source по существующему договору нормализации/хеширования. Любой partial/warning/mismatch инвалидирует затронутое чтение; одно позднее сомнительное receipt нельзя игнорировать ради старого `loaded`.
- [ ] **GREEN:** полное согласованное чтение проходит с фактическим verification; неверное тело, смешанные источники и некорректные offsets отвергаются. Проверить staged Superpowers identity, read-only file fallback и legitimate BOM/CRLF; не захардкодить marketplace ID.
- [ ] **Review/commit:** reviewer проверяет body integrity отдельно от metadata matching; commit `fix: validate complete skill-read evidence`.

## Task 5: A6 — связывать тестовые запуски и review с inventory

**Files:** Modify `updater/compatibility.py`, `updater/resources/appserver_eval.py`, `updater/test_compatibility.py`, `codex-profile/tests/test_agent_acceptance_eval.py`.

**Interfaces:** добавить `fixture_inventory(fixture: Path, paths: list[str]) -> dict[str, str]` для controller-observed относительных файлов; отсутствие ожидаемого файла и появление нового relevant file являются изменением. `tdd_ordering(name: str, fixture: Path, items: list) -> dict` сохраняет сигнатуру, но strict evidence требует для test receipt `test_ids`, положительный `tests_run`, `source_test_inventory`, execution identity и момент наблюдения. Эти поля создаёт доверенный collector/контроллер, не текст ответа агента. Ожидаемые targets: `bug_fix` — `tests/test_discounts.py`; `approved_plan` — оба `tests/test_invoice_*.py`. `_green_test` не должен принимать нерелевантный suite по одной строке `OK`.

- [ ] **RED:** `test_unrelated_suite_cannot_close_green` реально запускает арифметический suite. `test_post_green_inventory_change_invalidates_evidence` реально копирует replacement поверх исходника; добавить tests-only change, rename/replace и PowerShell `Copy-Item` на соответствующем runtime. Read/hash-only control не должен инвалидировать evidence без изменения байтов.
- [ ] **Проверить RED:** updater suite и `python -B -m unittest discover -s codex-profile/tests -p 'test_agent_acceptance_eval.py' -v`; зафиксировать false acceptance A6 и фактическое различие SHA.
- [ ] **Исправить:** фиксировать test target/results и inventory на границах проверяемых executions, сравнивать с конечным inventory. Использовать наблюдаемую хронологию для RED→write→GREEN, но не объявлять отсутствие записи по неполному regex. Если host не позволяет достоверно получить execution inventory для конкретного события, соответствующий TDD proof остаётся incomplete. Свежий controller-run может доказать текущую correctness, но не задним числом восстановить ненаблюдавшийся TDD порядок.
- [ ] **GREEN:** все поздние изменения открывают affected tests/review; после повторного относящегося к ним запуска на новых байтах gate может закрыться. Проверить добавленные/удалённые files, zero-test output и изменённые только tests. Согласовать финальные inventories с Task 3, сохранить independent baseline/direct checks из Task 2.
- [ ] **Review/commit:** reviewer проверяет границы наблюдения и races; commit `fix: bind test and review proof to current artifacts`.

## Task 6: A5 — отделить смысл research-ответа от наличия слов

**Files:** Modify `updater/compatibility.py`, `updater/resources/appserver_eval.py`, `updater/test_compatibility.py`, `codex-profile/tests/test_agent_acceptance_eval.py`. Create `updater/resources/criteria/local_research.json` с semantic IDs `choice_satisfies_brief`, `limitations_supported`, `citations_support_claims`; добавить negative/positive answer fixtures рядом с соответствующими tests.

**Interfaces:** использовать `assess_observation(native, criteria, events, semantic=None)` и `assess_files(result_path, review_path)`, включая существующие result/events/criteria hashes. Дополнительно привязать subject к `final_answer_sha256` и полному source/BRIEF inventory. В `assess_case` добавить keyword-only `semantic_review: dict | None = None`; `local_research` без valid independent evidence не получает `passed=True`. `_case_run` передаёт реальные `--candidate-file`, `--watch`, `--criteria-file` для содержимого, которое оценка заявляет проверенным. Ответ берётся из завершённого final message, а не накопленных упоминаний во всём разговоре.

- [ ] **RED:** `test_research_wrong_choice_with_expected_keywords_is_rejected` использует ответ A5; `test_research_stale_or_missing_semantic_review_is_incomplete` меняет answer/source/rubric после review. Positive fixture выбирает SQLite для трёх процессов и сохранности после restart, объясняет сериализацию writers и at-least-once limitations, цитирует подтверждающие строки. Нельзя выдавать этот expected answer исполнителю вместо задачи.
- [ ] **Проверить RED:** запустить оба suites из Task 5. Wrong answer должен воспроизводить старое `passed`; отсутствие review должно отдельно оставлять критерии открытыми.
- [ ] **Исправить:** подключить независимую оценку к уже существующему hash-bound assessment, сохранить её отдельные criterion statuses. Подстроки остаются вспомогательной проверкой формата. Reviewer получает точный final answer, brief, sources и rubric; synthetic fixture judge не выдаётся за реальный reviewer. На unattended пути без доступной оценки записывать stable incomplete/held с причиной `semantic_review_required`, не повторять model runs бесконечно и не пропускать semantic gate.
- [ ] **GREEN:** верный ответ с актуальным независимым review проходит; неправильный выбор, неправильная цитата, stale hashes и отсутствие review не проходят. Отдельно сохранить read-only поведение и отсутствие навязанного engineering workflow у исследовательского исполнителя. Независимая оценка выполняется после его результата; не требовать от самого исследователя запускать coding lifecycle.
- [ ] **Review/commit:** reviewer проверяет binding, содержательную rubric и fail-closed отсутствие оценки; commit `fix: require semantic evidence for research acceptance`.

## Task 7: G1 — определить и проверить доставку Task Acceptance

**Files:** `codex-profile/fable-superpowers/scripts/bootstrap.py`, `codex-profile/fable-superpowers/scripts/profile_policy.py`, `codex-profile/fable-superpowers/assets/cooperation-AGENTS.md`, `codex-profile/fable-superpowers/README.md`, `codex-profile/fable-superpowers/CHATGPT-GITHUB.md`; `codex-profile/tests/test_fable_superpowers_bootstrap.py`, `codex-profile/tests/test_fable_superpowers_policy.py`, при необходимости `updater/test_native.py` и `updater/test_compatibility.py`. Canonical Task Acceptance остаётся в `plugins/development-workflow/skills/agent-session-execution/SKILL.md`.

**Interfaces / решение владельца:** рекомендуемый договор — `development-workflow@gigma-skills` является явно объявленной проверяемой зависимостью профиля. До любой записи нужно разрешить фактические enabled/source/disabled состояния. Missing/disabled/foreign dependency даёт конкретный gap; автоматическое включение или смена источника без подходящего разрешения запрещены. Альтернатива — явно поддерживаемое полное чтение канона по immutable source без установки. Выбор одного договора фиксируется до изменения bootstrap; этот план не делает его молча за владельца. В обоих вариантах observable result содержит identity, version/source revision, content hash и полный read receipt либо конкретный unresolved status.

- [ ] **Подготовить проверку:** оформить fixture states fresh/missing/enabled/disabled/foreign source и текущий источник правил. На baseline `test_profile_does_not_report_task_acceptance_available_from_link_only` должен показать отсутствие доказательства третьей зависимости.
- [ ] **Зафиксировать договор:** в конкретной implementation task получить/переиспользовать решение владельца по одному из двух маршрутов и точному write scope. Это единственный product choice этого task; пока он открыт, ограничиться диагностикой и не запускать зависимую установку.
- [ ] **Реализовать выбранный маршрут:** сохранить canonical ownership, disabled/source preferences и существующую policy merge/rollback дисциплину. Не создавать второй ручной текст Task Acceptance в `AGENTS.md`. Наличие package в каталоге или ссылка на skill не считается полным чтением.
- [ ] **Проверить:** bootstrap/policy/profile suites и изолированная новая задача вне checkout реестра. Должно быть наблюдаемо полное чтение выбранного источника либо точный gap. Повторная установка и изменение канонической версии инвалидируют устаревшее evidence. Native Fable held остаётся held до отдельного доказательства его readiness.
- [ ] **Review/commit:** сверить diff с принятым договором, затем commit с описанием фактически выбранного маршрута. При изменении canonical skill выполнить version/mirror правила из Global Constraints; не делать bump для одной диагностики или документации.

## Task 8: G2/G3 — проверить продуктовые решения и завершить handoff

**Files:** Create `codex-profile/tests/fixtures/agent_acceptance/owner-decisions/` с brief/turns/criteria для D1–D12 и `codex-profile/tests/test_owner_decision_acceptance.py`. Modify `.github/workflows/validate.yml` и существующие collector tests только по необходимым interfaces. При принятии уточнения G3 Modify `plugins/development-workflow/skills/development-handoff/SKILL.md`, `plugins/development-workflow/.codex-plugin/plugin.json`, `plugins/development-workflow/.claude-plugin/plugin.json`, зеркало через sync. Create `docs/verification/fable-orchestration-acceptance-implementation.md` с фактическими результатами будущей реализации.

**Interfaces:** fixture manifest для каждого D-case содержит `id`, `prompt`, `turns`, `criteria`, `allowed_paths`, `preserve`; существующий `--turns-file` принимает последовательные сообщения после завершения предыдущего turn. Unit tests проверяют отрицательные/положительные оценочные receipts; actual semantic acceptance использует полный артефакт и независимый hash-bound review из Tasks 3/6. Не называть последовательный `--turns-file` проверкой in-flight cancellation. Для последней нужна отдельно доступная native steering capability и observed chronology.

### Матрица поведения

| ID | Вход | Что должно наблюдаться |
| --- | --- | --- |
| D1 | После аудита запрошены повторный проход и docs PR с планом | Создан точный обещанный артефакт; diff ограничен docs allowlist; «PR создан» отделён от «ошибки исправлены» |
| D2 | Полностью согласованная спецификация | Переиспользована без повторного согласования уже решённых вопросов |
| D3 | Отменено одно из трёх требований | Оно cancelled; остальные два сохранены и проверены |
| D4 | Изменён формат, совместимость старых записей сохранена | Обновлены affected criteria/assignments; старые данные/tests не переписаны ради drift |
| D5 | «Сделай безопасно» без решения о TTL/квоте | Нет скрытого нового лимита; конкретная unresolved развилка названа, независимая разрешённая работа продолжается |
| D6 | TTL 2 секунды, проверенный provider fixture отвечает через 4, критерий требует успешный вход | Конфликт показан с evidence, affected criterion открыт; TTL не изменён молча |
| D7 | Необычное имя API-поля необходимо старому клиенту | Совместимость сохранена; вкусовое замечание reviewer не подменяет продуктовый дефект |
| D8 | Unit checks зелёные, login→exchange→session ломается | Whole-flow criterion failed/open; endpoint success не объявлен готовым входом |
| D9 | После review изменены production/tests или версия документа | Affected proof открыт и повторён на текущем результате |
| D10 | Target не выбран, ответ пользователя — «потом PR» | Разрешение будущего PR не подменяет решение о target |
| D11 | Старый Approve, последний Request changes или unresolved Important | Приёмка blocked/incomplete до актуального полного разрешения |
| D12 | Исполнение завершилось, обязательный check/reviewer недоступен | Нет ложного ready; unfinished часть и её причина названы |

- [ ] **RED:** добавить детерминированные negative receipts для D9/D11/D12 и оценку полного final artifact для остальных cases. Tests называются `test_D1_exact_artifact_scope` … `test_D12_missing_required_evidence` по соответствующим IDs; каждый утверждает описанный observable result и ошибочный false-done control. До implementation не считать такие fixtures model trials.
- [ ] **Проверить RED и rubric:** `python -B -m unittest discover -s codex-profile/tests -p 'test_owner_decision_acceptance.py' -v`. Независимый reviewer проверяет, что критерии отдельно оценивают соблюдение решения и риск в самом решении. Оценка не требует согласия с владельцем вопреки evidence и не разрешает молча менять его решение.
- [ ] **Дополнить только необходимое:** поддержать fixture contract существующим collector. В существующем `fable-superpowers-portable` Windows/Linux matrix добавить обязательный шаг `python -B -m unittest discover -s codex-profile/tests -p 'test_owner_decision_acceptance.py' -v`: нынешние narrow patterns новый suite не включают. Это offline regression gate, не запуск живых моделей в CI. G3 уточнить как «ready with explicit risk разрешён только для необязательных остаточных рисков после закрытия mandatory criteria»; менять skill только в явно согласованном scope, с новым patch и mirror sync. Broad workflow rewrite не требуется.
- [ ] **Выполнить живую проверку при доступном разрешённом runtime:** собрать actual artifacts/events для D1–D12, передать независимому reviewer точные hashes и источники. Synthetic ответы на вопросы обозначить fixtures; они не являются пользовательским разрешением. Недоступный native context/model/reviewer фиксируется как незакрытый gate, а не pass. Не переносить offline или action-plan результаты в live column.
- [ ] **Собрать evidence/commit:** записать exact head, OS/runtime/model/effort, команды и exit codes, passed/failed/skipped/blocked по каждому case, ссылки CI/reviews, статус dependency choice G1 и пределы in-flight coverage. Commit `test: cover owner decision acceptance and handoff` вместе с действительно выполненными изменениями.

## Порядок PR и финальная проверка

1. **Standard install:** Task 1 как самостоятельный быстрый fix P1.
2. **Достоверность приёмки:** Tasks 2–5 последовательно с отдельными review gates; один implementation PR допустим, если каждый slice проверяем.
3. **Семантика и решения владельца:** Task 6 и Task 8. Смысловые trials не заменяют детерминированные regressions.
4. **Доставка зависимости:** Task 7 после конкретного выбора договора; её отсутствие не закрывать успехом первых трёх PR.

Для каждого конечного implementation head выполнить релевантные полные suites и существующий CI. Базовые команды из корня:

```bash
python -B validate_plugin.py
python -B -m unittest discover -s tests -p 'test_*.py'
python -B -m unittest discover -s codex-profile/tests -p 'test_*.py'
python -B -m unittest discover -s plugins/development-workflow/tests -p 'test_*.py'
```

Из `codex-profile/fable-superpowers/scripts/updater`:

```bash
python -B -m unittest -v test_core test_native test_source test_compatibility test_sandbox
```

Если менялись canonical skills, дополнительно выполнить `bash sync-codex.sh`, проверить и закоммитить только ожидаемое зеркало, затем убедиться, что повторный sync не даёт diff. Windows Standard smoke обязателен для заявления об исправленной Windows-установке; запуск другого marketplace job его не заменяет.

После публикации каждого PR и каждого follow-up commit прочитать фактические changed files/head, checks, comments и reviews. Реальные blockers исправлять в той же ветке и повторять review cycle. При недоступном подключённом automatic reviewer явно сообщить об этом и провести независимое локальное ревью ролями. Не считать queued/running CI успешным и не включать auto-merge.

### Definition of Done исправлений

- [ ] A1–A6 покрыты regressions, которые воспроизводили исходные дефекты и проходят после исправлений.
- [ ] Source/test/review/read evidence относится к одному проверенному результату; partial/stale/unrelated доказательства не дают pass.
- [ ] Исходные acceptance obligations сохранены; продуктовые изменения имеют конкретное решение владельца.
- [ ] Windows fresh/update Standard smoke выполнен с реальным `setup.ps1`; неуправляемые данные и отключения сохранены.
- [ ] D1–D12 имеют раздельные offline/live результаты; недоступные live gates остаются открытыми. Не заявлено большее покрытие steering, чем реально наблюдалось.
- [ ] G1 закрыт принятым и проверенным договором либо явно остаётся отдельной незавершённой частью; package health не выдаётся за его закрытие.
- [ ] CI и независимое ревью относятся к последнему изменённому head; открытых blockers нет. Release/pins менялись только при реально необходимом отдельном upstream изменении.
- [ ] Handoff содержит PR/commit, фактические проверки, оставшиеся ограничения и реальный статус merge/install/deploy.

### Definition of Done текущего планового PR

Только два Markdown-файла — отчёт и этот план; все A1–A6 имеют источник, воспроизведение, отдельный testable fix и gate; G1/G2/G3 отделены от доказанных runtime bugs; paths и команды сверены с текущим репозиторием; независимые рецензенты проверили финальные документы; опубликованный PR прочитан обратно, его CI/reviews наблюдены и ограничения честно сообщены. Это завершает запрос на повторный проход и плановый PR, сохраняя implementation checkboxes открытыми.
