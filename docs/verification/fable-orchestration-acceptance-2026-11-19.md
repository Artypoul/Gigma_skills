# Fable 5: второй проход по оркестрации и приёмке

Дата: 19 ноября 2026, Asia/Bangkok. Статус: ревью завершено; перечисленные исправления ещё не реализованы. Этот документ и [план реализации](../superpowers/plans/2026-11-19-fable-orchestration-acceptance.md) составляют отдельный документационный PR.

## Вывод

**Request changes для рассмотренных механизмов приёмки и Standard-установки.** Текстовые инструкции сохраняют решения владельца и допускают предметную критику ошибочного решения. Исполняемые оценщики в нескольких местах принимают более слабое доказательство, чем требует этот контракт.

Второй проход подтвердил пять ранее найденных групп проблем и добавил A2: изменение исполнителем старых тестов может скрыть конкретную регрессию даже от `assess_case`, который запускает собственные direct assertions. Это дефект оценщика, воспроизведённый на локальном контролируемом примере; это не утверждение об уже принятой реальной задаче Артёма.

| ID | Приоритет | Подтверждённая проблема | Исправление в плане |
| --- | --- | --- | --- |
| A1 | P1, только Standard | Шесть дубликатов исходных скиллов останавливают default setup до копирования скиллов | Task 1 |
| A2 | P2, новый | Ослабленный авторский suite скрывает нарушение исходного тестового контракта | Task 2 |
| A3 | P2 | Старое, противоречивое или явно частичное ревью принимается за полное одобрение | Task 3 |
| A4 | P2 | Неполное/другое содержимое MCP выдаётся за полностью прочитанный скилл | Task 4 |
| A5 | P2 | Ошибочная исследовательская рекомендация проходит по наличию ключевых слов | Task 6 |
| A6 | P2 | Нерелевантный GREEN и нераспознанная поздняя запись не отменяют TDD-доказательство | Task 5 |

IDs A1–A6 принадлежат этому отчёту. Они не переоткрывают F1–F6 из [более раннего плана marketplace/Fable](../superpowers/plans/2026-11-19-marketplace-fable-quality.md), который относится к другому snapshot и другим дефектам.

## Источники и пределы проверки

| Компонент | Прочитанная версия | Точный commit |
| --- | --- | --- |
| Gigma Skills | `main`, повторно проверен перед проходом | [`27edb4f405c09ec376441a919ced3b50259c051e`](https://github.com/Artypoul/Gigma_skills/tree/27edb4f405c09ec376441a919ced3b50259c051e) |
| Fable | `1.4.3` | [`cb76769f1fce9df196c22b2b708ba8474cbf5aa1`](https://github.com/Artypoul/claude-fable-5-system-prompt/tree/cb76769f1fce9df196c22b2b708ba8474cbf5aa1) |
| Superpowers, собственный fork | `7.0.2` | [`22f0b463e7a5e579904dd6211a520321035526f7`](https://github.com/Artypoul/superpowers/tree/22f0b463e7a5e579904dd6211a520321035526f7) |

Режим работы — `chatgpt_github`: полные применимые инструкции и зависимости прочитаны по закреплённым SHA через подключённую интеграцию. Чтение не устанавливает native-плагин. `FABLE_GATE=ready` и `TASK_GATE=ready` здесь относятся к доступности инструкций и средств для ревью/планового PR; `MCP_GATE=not_run`. Project settings и наследование инструкций новым чатом не проверялись.

Источник всех A2–A6 — неизменённый [`compatibility.py`](https://github.com/Artypoul/Gigma_skills/blob/27edb4f405c09ec376441a919ced3b50259c051e/codex-profile/fable-superpowers/scripts/updater/compatibility.py), Git blob `22961c040e3b30852cb6fbc0190d33275a3f20fd`. Локальные байты проверены по Git blob SHA; это не SHA-256 содержимого. Для второго прохода runtime-рецензент также перепроверил 52/52 файла своей выборки, без расхождений.

Три независимых рецензента повторно проверили runtime evidence, source/install integration и продуктовую приёмку. Роли использовали `gpt-6.1-sol`, `xhigh`, изолированные контексты. Основной агент повторил все девять диагностических наблюдений ниже на точном исходном модуле.

Доказательства A2–A6 используют синтетические native event receipts. Локальные Git-команды, Python suites, исходный baseline suite и копирование файла для A6 выполнялись реально. В полноценных вызовах `assess_case` заменён только Windows confinement transport на локальный адаптер для известного кода fixture. Это не live model run, не Windows/MXC-проверка и не доказательство обхода полного updater pipeline. A1 установлен по полному дереву источников и ветвлению установщика; PowerShell в этой среде не запускался.

## A1. Standard setup блокируется собственными дубликатами

[`setup.ps1:35–56`](https://github.com/Artypoul/Gigma_skills/blob/27edb4f405c09ec376441a919ced3b50259c051e/codex-profile/setup.ps1#L35-L56) объединяет `plugins/*/skills` и `codex-profile/personal-skills` по имени каталога. При любом повторе выполняется `throw`. `Standard` — default; путь `FableSuperpowers` выходит раньше, поэтому приоритет P1 относится только к Standard.

| Дублирующий personal root | Канонический владелец | Результат сравнения всего дерева |
| --- | --- | --- |
| `banquet-image-generation` | `plugins/codex-toolkit/skills/banquet-image-generation` | Канон убирает жёсткие машинные пути, сохраняет геометрические требования |
| `counterparty-audit-investigation` | `plugins/gigma-erp/skills/counterparty-audit-investigation` | Канон исправляет различие исторической оплаты и текущей активности подписки, добавляет полноту истории/пагинацию |
| `figma-cli` | `plugins/codex-toolkit/skills/figma-cli` | Канон сохраняет выбранный режим и требует разрешения для patch/install |
| `figma-poster-positioning` | `plugins/codex-toolkit/skills/figma-poster-positioning` | Полностью одинаковые байты |
| `no-unapproved-product-limits` | `plugins/development-workflow/skills/no-unapproved-product-limits` | Полностью одинаковые байты |
| `self-review-report` | `plugins/development-workflow/skills/self-review-report` | Канон дополняет evidence states, route и сценарий незарегистрированного helper; Stop script одинаков |

Всего в шести personal roots 10 файлов; отсутствующих в каноне вспомогательных файлов нет. Отдельный `segment-anything` не дублируется. Согласно [`AGENTS.md`](https://github.com/Artypoul/Gigma_skills/blob/27edb4f405c09ec376441a919ced3b50259c051e/AGENTS.md), источник истины — `plugins/`.

Узкое исправление: удалить шесть устаревших personal source roots, сохранить весь канон, `segment-anything` и отказ при новом неожиданном дубликате. Нельзя выбирать personal precedence: это вернёт старые инструкции в четырёх расходящихся парах. Проверка должна запускать настоящий default setup и повторную установку во временный профиль, проверяя полные деревья и сохранность чужого содержимого.

## A2. Исходная проверка совместимости теряется при изменении тестов

[`assess_case:1114–1127`](https://github.com/Artypoul/Gigma_skills/blob/27edb4f405c09ec376441a919ced3b50259c051e/codex-profile/fable-superpowers/scripts/updater/compatibility.py#L1114-L1127) запускает тесты из изменённого fixture. Собственные direct assertions проверяют сумму `200`, но не исходный пример `apply_discount(100, 10) == 90`, который уже есть в [неизменённом baseline suite](https://github.com/Artypoul/Gigma_skills/blob/27edb4f405c09ec376441a919ced3b50259c051e/codex-profile/fable-superpowers/scripts/updater/resources/fixtures/bug_fix/tests/test_discounts.py#L6-L8).

В контролируемом примере реализация возвращает правильные значения для суммы 200 и проверяемых границ, но возвращает 100 для `(100, 10)`. Авторский suite заменён четырьмя тестами только проверяемых оценщиком значений. Эта намеренно неверная реализация воспроизводит потерю уже существовавшего обязательства:

```python
def apply_discount(amount, percent):
    if percent < 0 or percent > 100:
        raise ValueError("percent must be between 0 and 100")
    if percent == 100:
        return 0.0
    return amount - percent * 2 if amount == 200 else amount
```

Наблюдение: `assessor_passed=true`, `author_suite_exit=0`, `direct_contract_passed=true`. Отдельный запуск сохранённого первоначального suite на той же реализации даёт exit 1: `AssertionError: 100 != 90`.

Исправление должно запускать неизменяемые исходные проверки вместе с новыми тестами и direct contract. Само редактирование suite не разрешает менять критерии. Согласованное изменение старого поведения требует явного нового контракта; это не повод запрещать все законные изменения тестов.

## A3. Ревью не подтверждает актуальный полный результат

[`review_evidence:951–981`](https://github.com/Artypoul/Gigma_skills/blob/27edb4f405c09ec376441a919ced3b50259c051e/codex-profile/fable-superpowers/scripts/updater/compatibility.py#L951-L981) накапливает любое подходящее approval. Проверки scope/validation сводятся к наличию слов; parser findings не понимает стандартный Markdown-заголовок Important.

Три независимых контрпримера проходят:

1. У одного reviewer есть start 30, Approve 40, complete 45, затем новый start 50, Request changes 55, complete 60. После production event 25 оценщик принимает старый event 40. Контроль с одним отрицательным вердиктом корректно отвергается.
2. `Verdict: Approve` сопровождается незакрытой проблемой под `#### Important (Should Fix)`. Этот формат предусмотрен [pinned reviewer template](https://github.com/Artypoul/superpowers/blob/22f0b463e7a5e579904dd6211a520321035526f7/skills/requesting-code-review/code-reviewer.md), но не блокирует оценщик.
3. Reviewer прямо пишет: проверял только формулировки `APPROVED_PLAN.md`, исключил `invoice_helpers.py`/`invoice_cli.py`, тесты не запускал и поведение реализации не исследовал. Наличие `Scope`, `plan` и `Tests` всё равно даёт `passed=true`.

Необходимы ожидаемый scope до dispatch, привязка к текущим production/test байтам, актуальный завершённый verdict для того же предмета проверки и явные незакрытые findings. Частичное или противоречивое ревью не закрывает общий gate. При нескольких reviewers отдельное approval не погашает чужое незакрытое blocking finding.

## A4. Metadata MCP подменяет доказательство полного чтения

[`observed_skill_reads:929–947`](https://github.com/Artypoul/Gigma_skills/blob/27edb4f405c09ec376441a919ced3b50259c051e/codex-profile/fable-superpowers/scripts/updater/compatibility.py#L929-L947) доверяет заявленному `sha256` и сумме длин страниц; фактическое содержимое не сверяется с выбранным source.

Контрпример: source — непустой полный `SKILL.md`; MCP возвращает ожидаемые name/path/claimed hash, но `content="x"`, `offset=0`, `total_chars=1`, `partial=true`, `warning_count=1`. Результат — `complete_mcp_read`, хотя actual hash строки `x` отличается. Pinned Fable требует [проверять identity, partial/warnings и согласованность страниц](https://github.com/Artypoul/claude-fable-5-system-prompt/blob/cb76769f1fce9df196c22b2b708ba8474cbf5aa1/.agents/skills/fable5-codex/SKILL.md).

Нужно восстановить полное содержимое из согласованных страниц, проверить ожидаемую identity и фактическое содержимое по договору provider, отбросить partial/warning/conflicting/foreign receipts. Updater использует staged identity: нельзя исправлять это жёсткой подстановкой `superpowers@gigma-skills`. Контрпример не утверждает, что текущий MCP сам выдавал такие данные.

## A5. Неверная исследовательская рекомендация принята по словам

[`local_research:1103–1108`](https://github.com/Artypoul/Gigma_skills/blob/27edb4f405c09ec376441a919ced3b50259c051e/codex-profile/fable-superpowers/scripts/updater/compatibility.py#L1103-L1108) требует три подстроки: `SQLite`, `memory-queue.md:`, `sqlite-queue.md:`. [BRIEF](https://github.com/Artypoul/Gigma_skills/blob/27edb4f405c09ec376441a919ced3b50259c051e/codex-profile/fable-superpowers/scripts/updater/resources/fixtures/local_research/BRIEF.md) требует три producer processes и сохранность заданий после перезапуска; предоставленные источники исключают in-memory queue для этих условий.

Ответ «Choose the in-memory queue for durable multi-process jobs. Do not use SQLite», дополненный двумя именами файлов со строками, получает `passed=true` в полном `assess_case('local_research', ...)`. Fixture остаётся неизменным. Проверка ссылок полезна, но не подтверждает выбор и объяснение ограничений.

Нужна независимая семантическая оценка конечного ответа по исходному brief и проверенным источникам, связанная с их точными версиями. Уже существующий [hash-bound semantic assessment](https://github.com/Artypoul/Gigma_skills/blob/27edb4f405c09ec376441a919ced3b50259c051e/codex-profile/fable-superpowers/scripts/updater/resources/appserver_eval.py#L656-L749) следует использовать как основу, сохраняя `incomplete`, если семантическое доказательство отсутствует.

## A6. GREEN не связан с нужным тестом и конечными байтами

[`_green_test` и `tdd_ordering:1022–1067`](https://github.com/Artypoul/Gigma_skills/blob/27edb4f405c09ec376441a919ced3b50259c051e/codex-profile/fable-superpowers/scripts/updater/compatibility.py#L1022-L1067) принимают exit 0, слово `unittest`, `Ran N tests` и `OK`. Реально выполненный тест `1 + 1 == 2` из другого каталога закрывает GREEN для исправления `discounts.py`.

Второй проход дополнительно проверил позднюю запись: после условного GREEN реально выполнен `shutil.copyfile('replacement.py', 'discounts.py')`. SHA исходника изменился, но [`_writes_path:984–1018`](https://github.com/Artypoul/Gigma_skills/blob/27edb4f405c09ec376441a919ced3b50259c051e/codex-profile/fable-superpowers/scripts/updater/compatibility.py#L984-L1018) не распознал эту команду как запись. Proof остался `passed=true` с последним production event 3 вместо фактического copy event 5. Эта хронология также используется для freshness review.

Исправление: связывать RED/GREEN с ожидаемым test target, ненулевым набором реально исполненных тестов и inventory исходников/тестов на момент проверки. Конечные байты должны соответствовать проверенным. Дополнение regex очередной командой не решает общий пробел наблюдения.

Сам по себе A6 не доказывает, что весь багфикс с неверным результатом будет принят: ниже выполняются независимые tests/direct assertions. Их отдельная конкретная слабость показана в A2. Настоящий запуск нулевого suite в этой среде не дал ложный успех и не используется как runtime-доказательство.

## Решения Артёма: что защищено и чего ещё не проверили

Контракт [Task Acceptance](https://github.com/Artypoul/Gigma_skills/blob/27edb4f405c09ec376441a919ced3b50259c051e/plugins/development-workflow/skills/agent-session-execution/SKILL.md#L29-L43) фиксирует точный артефакт, сохраняет неотменённые требования при steering, связывает каждый ответ с конкретной развилкой, передаёт актуальные критерии исполнителю/рецензенту и проверяет текущую версию результата. [Decision lock](https://github.com/Artypoul/Gigma_skills/blob/27edb4f405c09ec376441a919ced3b50259c051e/plugins/development-workflow/skills/development-handoff/SKILL.md#L131-L157) запрещает легализовать отклонение переписыванием тестов или документации.

Приёмка должна отвечать на два отдельных вопроса: «исполнено ли согласованное решение?» и «обнаружен ли подтверждённый риск в самом решении?». [Superpowers reviewer](https://github.com/Artypoul/superpowers/blob/22f0b463e7a5e579904dd6211a520321035526f7/skills/requesting-code-review/code-reviewer.md#L101-L104) требует сообщать о дефектах плана. Решение об изменении продуктового поведения остаётся у владельца.

Новых instruction-level P1/P2, разрешающих молча заменить решение владельца, второй проход не подтвердил. При этом существуют три отдельные недоработки:

- **G1 — доставка зависимости.** [cooperation-AGENTS.md:20](https://github.com/Artypoul/Gigma_skills/blob/27edb4f405c09ec376441a919ced3b50259c051e/codex-profile/fable-superpowers/assets/cooperation-AGENTS.md#L20) требует Task Acceptance из `development-workflow`, а [bootstrap](https://github.com/Artypoul/Gigma_skills/blob/27edb4f405c09ec376441a919ced3b50259c051e/codex-profile/fable-superpowers/scripts/bootstrap.py#L458-L511) устанавливает Fable и Superpowers без гарантии доступности третьей зависимости. Наличие `AVAILABLE` не равно enabled/read. Это структурный gap, не наблюдавшаяся ошибочная задача модели. Выбор способа доставки требует отдельного явно согласованного договора; отключения и выбранный источник нельзя менять молча.
- **G2 — покрытие поведения.** Пять updater cases и 37 pinned Fable behavior cases не проверяют напрямую отмену/замену решения владельца, критику ошибочного согласованного решения и точную смену требуемого артефакта. Mocked multi-turn test и арифметический smoke проверяют транспорт, а не эту семантику. Матрица D1–D12 включена в план.
- **G3 — ясность формулировки.** `ready with this explicit risk` в [handoff:161–171](https://github.com/Artypoul/Gigma_skills/blob/27edb4f405c09ec376441a919ced3b50259c051e/plugins/development-workflow/skills/development-handoff/SKILL.md#L161-L171) желательно сузить до необязательных остаточных рисков после обязательных gates. Более строгие правила того же skill/router/cooperation уже запрещают ready при недостающих обязательных доказательствах. Это уточнение текста, не подтверждённый bypass; прежнее замечание уточнено по результату второго прохода.

## Повторная проверка и условия закрытия

Во втором проходе повторно выполнены:

| Проверка | Результат | Что доказывает |
| --- | --- | --- |
| `python -B -m unittest discover -s codex-profile/tests -p 'test_agent_acceptance_eval.py'` | 48 passed, exit 0 | Существующие collector/acceptance regressions |
| Из `codex-profile/fable-superpowers/scripts/updater`: `python -B -m unittest -v test_compatibility` | 53 passed, exit 0 | Существующие compatibility regressions |
| Шесть диагностических наблюдений первого прохода | Повторены | Старое approval, negative-only control, Markdown finding, unrelated GREEN, partial read, wrong research |
| Три наблюдения второго прохода | Повторены | Явно частичный review, нарушение baseline suite, реальная поздняя копия |
| Полный source inventory Standard и шесть сравнений деревьев | Коллизии подтверждены | Причина гарантированного `throw`; не Windows smoke |

Суммарно повторены **101 существующий тест**. Их зелёный результат не закрывает контрпримеры. CI исходного snapshot также был зелёным: [Gigma run 44490361564](https://github.com/Artypoul/Gigma_skills/actions/runs/44490361564), [Fable run 44486596778](https://github.com/Artypoul/claude-fable-5-system-prompt/actions/runs/44486596778). Эти исторические результаты не являются CI нового PR или будущих исправлений.

Текущий [native-context gate Fable 1.4.3](https://github.com/Artypoul/claude-fable-5-system-prompt/blob/cb76769f1fce9df196c22b2b708ba8474cbf5aa1/MCP.md) остаётся отдельным fail-closed ограничением. Package health, чтение GitHub и offline fixtures не разрешают объявлять native activation успешной. Изменение metadata generator/judge само по себе не включено в findings: CLI намеренно параметризует evaluator и не даёт достаточного основания считать это дефектом.

Закрытие A1–A6 требует regressions, сначала падающих на указанном baseline, затем проходящих на исправленном коде; проверки фактического конечного diff, связанного с ним независимого ревью и CI. Для заявлений о Windows/native/живой продуктовой приёмке нужны отдельные реальные прогоны. Настоящий PR добавляет только результаты ревью и план; его merge сам по себе ни одну из этих ошибок не исправляет.
