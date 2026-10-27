---
name: counterparty-audit-investigation
description: "Расследовать конкретного контрагента Gigma ERP по телефону или counterparty_id: проверить diagnostics/history, авторизации через приложения, подписки, платежи и события. Используй сразу, когда Art просит проверить/расследовать конкретного контрагента, клиента, номер телефона или активную подписку, особенно по сервисам Твой VPS."
---

# Counterparty Audit Investigation

Цель: быстро и безопасно дать Art фактический разрез по контрагенту из Gigma ERP: найден ли контрагент, через какие приложения он авторизовался, есть ли подписки/платежи/события, и что видно в history.

## Hard Trigger

Если Art просит "расследование", "проверить контрагента", "есть ли подписка", "по номеру", "по телефону", "по counterparty_id", "Твой VPS" или похожую фактическую проверку конкретного клиента/контрагента, сразу применяй этот skill.

Не уходи в общий callback-auth flow и не объясняй контракт callback, если Art просит фактическое состояние конкретных контрагентов.

Не применяй этот skill для проектирования или ревью API/кода callback-auth, miniapp-auth, платежей, подписок или webhooks без конкретного телефона/counterparty_id. Такие задачи маршрутизируются в профильный auth/payment/subscription flow.

## Доступ

Работай API-first и read-only.

Сначала проверь существующий purpose-bound token:

- `%USERPROFILE%\.gigma\counterparty-investigation-agent.env`
- ожидаемый ключ: `GIGMA_COUNTERPARTY_INVESTIGATION_TOKEN`
- проверить через `GET https://api.gigma.ru/api/user`
- достаточно права `view-counterparties`

Если этот token существует, валиден и имеет `view-counterparties`, не спрашивай `owner_email` и не создавай новую agent-access заявку.

Если token отсутствует, невалиден, истек или не имеет `view-counterparties`, используй skill `gigma-erp:request-agent-access` и создай self-service заявку с минимальным правом:

- `permissions`: `["view-counterparties"]`
- `purpose`: read-only counterparty audit/investigation
- `agent_name`: `Codex Counterparty Investigation Agent`
- `agent_login`: по умолчанию не указывать для расследования контрагента; добавлять только если Art явно попросил стабильный login и `gigma-erp:request-agent-access` это допускает

Спрашивай у Art только `owner_email`, если его нельзя безопасно найти локально. Не проси owner/admin Bearer token, пароль, OTP, approval token, БД или SSH для обычного расследования.

Никогда не выводи в чат, PR, issue, shell history или файлы репозитория:

- `request_token`
- `approval_token`
- `agent_token`
- Bearer token

## Порядок расследования

Для каждого lookup делай отдельную проверку. Если Art дал два телефона, обработай их последовательно как два независимых lookup, а не объединяй в один запрос.

1. Нормализуй телефон к виду `7XXXXXXXXXX`, если это очевидно.
2. Выполни:

```http
GET /api/counterparties/diagnostics?phone=<phone>&limit=50&auth_window_hours=12
Authorization: Bearer <agent_token>
Accept: application/json
```

Или, если Art дал `counterparty_id`:

```http
GET /api/counterparties/diagnostics?counterparty_id=<id>&limit=50&auth_window_hours=12
Authorization: Bearer <agent_token>
Accept: application/json
```

3. Из diagnostics извлеки:

- `lookup.match_count`, `matched_counterparty_ids`
- `counterparty.id`, имя/тип/телефоны, если есть
- `service_registrations.applications`
- `service_registrations.callback_auth_sessions`
- `auth.counterparty_sessions`
- `subscriptions.items`
- `subscriptions.status_events`
- `subscriptions.autopay_consents`
- `subscriptions.saved_payment_methods`
- `payments.subscription_payments`
- `payments.orders`
- `payments.payment_records`
- `meta.warnings`
- `periods.business` и `periods.auth`

4. Если diagnostics вернул `counterparty.id`, выполни:

```http
GET /api/counterparties/<id>/history?per_page=50
Authorization: Bearer <agent_token>
Accept: application/json
```

5. Для запроса про "Твой VPS" ищи приложения и бизнес-записи по признакам:

- `Tvoi_vps.com`
- `Твой VPS`
- `Твой ВПС`
- `VPS`
- `ВПС`

Но вывод об активной подписке делай только по subscription/payment/status данным, а не по самому факту callback-auth входа.

## Как делать вывод

Разделяй три факта:

- "контрагент найден";
- "контрагент авторизовался через приложение";
- "у контрагента есть активная подписка/оплата".

Успешный callback `verified` означает только вход/авторизацию. Он не доказывает активную подписку.

Активная подписка подтверждается только явной записью в `subscriptions.items` или статусными событиями/платежами, из которых видно active/current/paid и сервис "Твой VPS". Если таких записей нет, формулируй: "по ERP diagnostics активной подписки не найдено", а не "точно никогда не было подписки".

Если API не содержит нужного источника, не лезь в БД/логи/SSH без отдельного последнего разрешения Art. Скажи, какого источника не хватает и какой следующий безопасный шаг нужен.

## Формат ответа Art

Пиши коротко и по делу:

- время проверки;
- источник: diagnostics/history live API;
- по каждому телефону или id: counterparty_id, приложение, последние релевантные события, количество подписок/платежей;
- итог: есть/нет активной подписки;
- ограничения, если БД/SSH не проверялись.

Не перегружай ответ сырыми JSON и не раскрывай секреты.
