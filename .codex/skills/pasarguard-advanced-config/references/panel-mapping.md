# Слои PasarGuard и границы версии

Проверенный ориентир — [v5.5.1](https://github.com/PasarGuard/panel/releases/tag/v5.5.1), commit `eba70d68eaa5a89e34ffebb47c8fd5ce054d0e43`, проверка 2026-11-09. Для другой установленной версии заново проверь исходники и контракт, не обновляя этот скилл автоматически. [Документация Host](https://docs.pasarguard.org/en/panel/host/) и [Groups](https://docs.pasarguard.org/en/panel/groups/) текущая, не зафиксирована по версии.

- **Core inbound** задаёт серверную сторону: протокол, transport, security и параметры входа. Flow подписки берётся из `inbound.settings.flow`: [core/xray.py](https://github.com/PasarGuard/panel/blob/eba70d68eaa5a89e34ffebb47c8fd5ce054d0e43/app/core/xray.py#L629), [subscription/xray.py](https://github.com/PasarGuard/panel/blob/eba70d68eaa5a89e34ffebb47c8fd5ce054d0e43/app/subscription/xray.py#L463).
- **Host override** формирует параметры подписки клиента. Изменение SNI или path в Host само по себе не меняет серверный inbound. Сопоставь Host с inbound и нодой, доступностью слушателя и реальным импортом клиента.
- Groups связывает пользователя с активной группой, её `inbound_tag` и соответствующими Host; проверяй фактическую связку. `priority` сортируется по возрастанию, это порядок выдачи, а не доказанный автоматический failover: [hosts.py](https://github.com/PasarGuard/panel/blob/eba70d68eaa5a89e34ffebb47c8fd5ce054d0e43/app/core/hosts.py#L823).
- В v5.5.1 `transport_settings.xhttp_settings.download_settings` — целочисленный ID Host, не готовый объект streamSettings; выход в Xray JSON — `streamSettings.xhttpSettings.extra.downloadSettings`: [host.py](https://github.com/PasarGuard/panel/blob/eba70d68eaa5a89e34ffebb47c8fd5ce054d0e43/app/models/host.py#L688). Панель находит и разворачивает его при рендере: [hosts.py](https://github.com/PasarGuard/panel/blob/eba70d68eaa5a89e34ffebb47c8fd5ce054d0e43/app/core/hosts.py#L688), [xray.py](https://github.com/PasarGuard/panel/blob/eba70d68eaa5a89e34ffebb47c8fd5ce054d0e43/app/subscription/xray.py#L402). Disabled Host допустим с 5.5.1; отсутствующий либо не обслуживаемый inbound может исключить downloadSettings. Проверь именно сгенерированный клиентский профиль.
- Host `final_mask_settings` может переопределить FinalMask, иначе копируется inbound без серверного filter: [hosts.py#L60](https://github.com/PasarGuard/panel/blob/eba70d68eaa5a89e34ffebb47c8fd5ce054d0e43/app/core/hosts.py#L60), [hosts.py#L161](https://github.com/PasarGuard/panel/blob/eba70d68eaa5a89e34ffebb47c8fd5ce054d0e43/app/core/hosts.py#L161). `null` возвращает наследование, а не гарантированно отключает маскировку. Для отключения проверь итоговый профиль и способ переопределения в установленной версии. Наличие поля в панели не доказывает поддержку в core или клиенте.
- **Client template** управляет рендером клиентского конфига, а не серверным inbound. В 5.5.1 это `client_templates` с `content: Text`: [models.py](https://github.com/PasarGuard/panel/blob/eba70d68eaa5a89e34ffebb47c8fd5ce054d0e43/app/db/models.py#L952), [client_templates.py](https://github.com/PasarGuard/panel/blob/eba70d68eaa5a89e34ffebb47c8fd5ce054d0e43/app/subscription/client_templates.py#L10). Не путай с core templates и не предлагай старый `XRAY_SUBSCRIPTION_TEMPLATE` без проверки конкретной версии.

`XRAY_SUBSCRIPTION_TEMPLATE` остаётся внутренним ключом словаря шаблонов в [share.py](https://github.com/PasarGuard/panel/blob/eba70d68eaa5a89e34ffebb47c8fd5ce054d0e43/app/subscription/share.py#L82); это не доказательство управления через переменную окружения. `subscription_templates.xray` в Host выбирает ID клиентского шаблона для формата Xray. В `add_config` сгенерированные outbounds добавляются **перед** `template.outbounds`; словари `streamSettings` автоматически не сливаются. Сохраняй массив `outbounds` в шаблоне, проверяй ссылки routing на теги и дубли `proxy`/`dialer`; дополнительный статический outbound не переопределяет сгенерированный `proxy`. [Выбор шаблона](https://github.com/PasarGuard/panel/blob/eba70d68eaa5a89e34ffebb47c8fd5ce054d0e43/app/subscription/share.py#L465), [сборка](https://github.com/PasarGuard/panel/blob/eba70d68eaa5a89e34ffebb47c8fd5ce054d0e43/app/subscription/xray.py#L74).

Не выводи контракт записи из примеров другой версии. Получи реальный обезличенный export или подтверждённую схему; проверь generated client для каждого используемого формата подписки.
- Старые Host `fragment_settings`/`noise_settings` отличаются от `streamSettings.finalmask`: основной legacy-механизм создаёт freedom outbound с `tag=dialer`. В 5.5.1 `_download_config` назначает `dsdialer`, но штатный renderer соответствующий outbound не создаёт. По умолчанию не включай legacy fragment/noise для download Host, пока фактический клиентский JSON не содержит matching outbound и соединение не проверено. `_download_config` этой версии не передаёт downstream FinalMask, поэтому не обещай его заменой. URI/link-формат отличается от JSON и `dsdialer` не выдаёт; проверь фактический формат. Это вывод из кода, не воспроизведённый live bug. Источники: [рендер download](https://github.com/PasarGuard/panel/blob/eba70d68eaa5a89e34ffebb47c8fd5ce054d0e43/app/subscription/xray.py#L402-L440), [outbounds](https://github.com/PasarGuard/panel/blob/eba70d68eaa5a89e34ffebb47c8fd5ce054d0e43/app/subscription/xray.py#L725-L755), [ошибка отсутствующего dialer в Xray v26.3.27](https://github.com/XTLS/Xray-core/blob/v26.3.27/transport/internet/dialer.go#L270-L279). Не совмещай механизмы вслепую.

Для Host path и сгенерированного объекта см. [тесты 5.5.1](https://github.com/PasarGuard/panel/blob/eba70d68eaa5a89e34ffebb47c8fd5ce054d0e43/tests/api/test_host_download_host.py#L39-L47) и [renderer](https://github.com/PasarGuard/panel/blob/eba70d68eaa5a89e34ffebb47c8fd5ce054d0e43/app/subscription/xray.py#L146-L190).

## Практическая карта XHTTP 5.5.1

Это соответствия полей, не готовый запрос записи. Основа — [BaseHost и TransportSettings](https://github.com/PasarGuard/panel/blob/eba70d68eaa5a89e34ffebb47c8fd5ce054d0e43/app/models/host.py), [сборка Host](https://github.com/PasarGuard/panel/blob/eba70d68eaa5a89e34ffebb47c8fd5ce054d0e43/app/core/hosts.py#L129) и [рендер XHTTP](https://github.com/PasarGuard/panel/blob/eba70d68eaa5a89e34ffebb47c8fd5ce054d0e43/app/subscription/xray.py#L146-L190). Сверь фактический экспорт перед patch.

Ниже `H` = `transport_settings.xhttp_settings` в Host, `X` = `streamSettings.xhttpSettings` в выданном Xray outbound.

| Поле Host | Выданный клиентский параметр / назначение |
| --- | --- |
| `inbound_tag` | Выбирает inbound, откуда берётся транспорт; поля `Host.network` здесь нет. |
| `address`, `port` | Адрес подключения клиента; это не REALITY target и не TLS SNI. |
| `sni`, `security`, `fingerprint`, `alpn` | Настройки клиентского TLS/REALITY с учётом наследования; сервер не перенастраивают. |
| `host`, `path`, `http_headers` | `X.host`, `X.path`, `X.extra.headers`; HTTP host отличается от объекта Host панели. |
| `H.mode` | `X.mode` |
| `H.x_padding_bytes`, `H.x_padding_obfs_mode` | `X.extra.xPaddingBytes`, `X.extra.xPaddingObfsMode` |
| `H.x_padding_key`, `H.x_padding_header`, `H.x_padding_placement`, `H.x_padding_method` | `X.extra.xPaddingKey`, `xPaddingHeader`, `xPaddingPlacement`, `xPaddingMethod` |
| `H.session_placement`, `H.session_key` | `X.extra.sessionIDPlacement`, `X.extra.sessionIDKey` |
| `H.session_id_table`, `H.session_id_length` | `X.extra.sessionIDTable`, `X.extra.sessionIDLength` |
| `H.seq_placement`, `H.seq_key` | `X.extra.seqPlacement`, `X.extra.seqKey` |
| `H.uplink_http_method`, `H.uplink_data_placement`, `H.uplink_data_key` | `X.extra.uplinkHTTPMethod`, `uplinkDataPlacement`, `uplinkDataKey` |
| `H.uplink_chunk_size` | `X.extra.uplinkChunkSize` |
| `H.no_grpc_header` | `X.extra.noGRPCHeader` |
| `H.sc_max_each_post_bytes`, `H.sc_min_posts_interval_ms` | `X.extra.scMaxEachPostBytes`, `X.extra.scMinPostsIntervalMs` |
| `H.xmux` | `X.extra.xmux`; не путай с отдельным `mux_settings.xray`. |
| `H.download_settings` | ID другого Host → `X.extra.downloadSettings`, с ограничениями выше. |

`address`, `sni` и `host` в модели — наборы строк; не подменяй их скалярной строкой при подготовке API patch. Для списков вариантов проверь реально выбранное значение в каждой выданной подписке. Присутствие расширенного поля в модели PG не доказывает его поддержку клиентом: сверяй весь путь Host → профиль → импорт клиента. Параметры размещения данных, padding и HTTP-метода согласуй с серверной схемой; значения по умолчанию и диапазоны бери из установленной версии core.

Все шесть полей `H.xmux`: `max_concurrency` → `maxConcurrency`, `max_connections` → `maxConnections`, `c_max_reuse_times` → `cMaxReuseTimes`, `h_max_reusable_secs` → `hMaxReusableSecs`, `h_max_request_times` → `hMaxRequestTimes`, `h_keep_alive_period` → `hKeepAlivePeriod`. Справа — имена aliases в объекте `X.extra.xmux`; в API используй форму из реального экспорта. Первые пять принимают строку числа/диапазона, последнее — целое число. Источник: `XMuxSettings` в [модели Host](https://github.com/PasarGuard/panel/blob/eba70d68eaa5a89e34ffebb47c8fd5ce054d0e43/app/models/host.py#L641).

Если в Core `xhttpSettings.extra` уже является объектом, PG читает расширенные значения оттуда, без подстановки одноимённых полей верхнего уровня. Не смешивай две формы в надежде на слияние; даже пустой `extra: {}` меняет выбор источника. [Разбор Core](https://github.com/PasarGuard/panel/blob/eba70d68eaa5a89e34ffebb47c8fd5ce054d0e43/app/core/xray.py#L380).

## TLS, REALITY и преобразования выдачи

В Xray JSON PG 5.5.1 ветки различаются: [TLS renderer](https://github.com/PasarGuard/panel/blob/eba70d68eaa5a89e34ffebb47c8fd5ce054d0e43/app/subscription/xray.py#L350).

| Host / Core | Фактическое назначение |
| --- | --- |
| Host `sni`, `fingerprint` | Выдаются в `tlsSettings` или `realitySettings` по выбранной безопасности. `none` у fingerprint может означать наследование, а не отключение; для REALITY есть резервное значение `chrome`. |
| Host `alpn`, `allowinsecure`, `pinned_peer_cert_sha256`, `verify_peer_cert_by_name` | Выдаются в TLS-ветке как `alpn`, `allowInsecure`, `pinnedPeerCertSha256`, `verifyPeerCertByName`; не считай их действующими в REALITY-ветке этого renderer. |
| Host `ech.xray.config_list`, `ech.xray.query_strategy` | TLS `echConfigList`, `echForceQuery`. В сверенном Xray v26.11.9 поле `echForceQuery` отсутствует в `TLSConfig`; эффект нужно проверять на фактическом core. |
| Host `cipher_suites` | TLS `cipherSuites` выдаётся только при `fingerprint=unsafe`. Для REALITY такой fingerprint непригоден. |
| Core REALITY `privateKey`, `shortIds`, `spiderX`, `mldsa65Verify` | PG вычисляет клиентский publicKey, выбирает shortId и передаёт spiderX/проверочный ключ. Это не произвольные Host overrides. |

Схема актуального core для сравнения: [transport_security.go, v26.11.9](https://github.com/XTLS/Xray-core/blob/676eaf66f8f05d4d558ee7a74b4736623d3feeb9/infra/conf/transport_security.go). Она не заменяет проверку установленной версии.

`normalize_and_remove_none_values` в PG 5.5.1 удаляет `None`, пустые строки/списки, числовой `0` и `false` из словарей; строка `"0"` сохраняется. Поэтому введённый ноль или выключатель не всегда явно попадает в профиль: сравни отсутствие поля с default конкретного core. Не меняй тип значения ради обхода очистки без проверки схемы. [Реализация](https://github.com/PasarGuard/panel/blob/eba70d68eaa5a89e34ffebb47c8fd5ce054d0e43/app/subscription/base.py#L12).

Отдельно проверь legacy `fragment_settings.xray.max_split`: модель имеет alias `maxSplit`, но подготовка Host вызывает `model_dump()` без aliases, а Xray renderer передаёт fragment без переименования. Это риск выдачи `max_split` вместо ожидаемого Xray `maxSplit`, выявленный по коду; не объявляй настройку применённой без чтения клиентского JSON. Не смешивай его с FinalMask, где другой serializer. [Host dump](https://github.com/PasarGuard/panel/blob/eba70d68eaa5a89e34ffebb47c8fd5ce054d0e43/app/core/hosts.py#L536), [dialer](https://github.com/PasarGuard/panel/blob/eba70d68eaa5a89e34ffebb47c8fd5ce054d0e43/app/subscription/xray.py#L385), [Xray Fragment](https://github.com/XTLS/Xray-core/blob/676eaf66f8f05d4d558ee7a74b4736623d3feeb9/infra/conf/freedom.go).
