---
name: vps-configuration-analysis
description: Use when a VPS task needs a complete configuration audit, a node or panel specification, a comparison between nodes, or a proof-backed explanation of why panel, pg-node, Xray, firewall, and subscription state differ.
---

# Анализ конфигурации и составление спецификации VPS

Этот скилл превращает разрозненные чтения PG, нод и подписки в одну проверяемую спецификацию. Он нужен для аудита, сравнения, расследования падений и подготовки плана изменения. Он не даёт разрешения менять production и не заменяет согласование записи.

## Обязательный входной проход

1. Если в задаче есть `Fable`, `Фейбл` или просьба применить Fable 5, сначала активируй `$fable5-codex:fable5-codex` из текущего каталога Codex. Пройди Fable-baseline, затем `project-context-bootstrap`, `project-workflow-router` и один подходящий lifecycle Superpowers из `superpowers@gigma-skills`. Для read-only аудита оставь все внешние записи выключенными.
2. Прочитай `C:\Users\Art\.ssh\pg\PG-RUNBOOK.md` перед доступом к PG или нодам. Адреса в ранбуке — снимок, а не вечный канон: перед каждым SSH и API-сеансом сверяй актуальный адрес, порт, пользователя, ключ и fingerprint с панелью, ранбуком и подтверждённым владельцем.
3. Зафиксируй границы: какие ноды, core, host, группы, подписка, серверы-источники проверки и действия разрешены. Если пользователь просит только анализ или план, не меняй PG, firewall, fail2ban, systemd, Docker, ключи, сертификаты или подписки.
4. Сохрани `case_id`, `evidence_revision`, роль исполнителя, запреты и точку возврата в текущем контексте. Повторный вход в уже завершённую ветку по тем же фактам не запускай.

## Target Lock для ноды и панели

Перед любым планом записи создай одну карточку `Target Lock`: `target_id`/Node ID, Core ID, Host ID, Group ID, management/SSH/client/egress адреса и порты, environment, источник истины, fingerprint или версию и время live `read-back`. Имена, адрес из ранбука и старый transcript — только справка до сверки с актуальной панелью и нодой.

Сначала перечитай live inventory и сравни все поля карточки; затем повтори сверку перед каждой записью. Если ID, адрес, fingerprint, `sendThrough` или source-of-truth revision отсутствует либо расходится, выставь `context_stale`, покажи `old -> current` с источником и не выполняй запись или автоматический retry. Нельзя переносить IP или поля другой ноды. Намеренная смена адреса — отдельная `migration`-ветка с явно названной целью, подтверждением владельца и обязательным post-write read-back.

## Модель, которую нужно проверять целиком

Разделяй шесть уровней и не подменяй один другим:

| Уровень | Что проверять | Что доказывает |
|---|---|---|
| Панель | node, core, inbound/tag, host, группы, приоритеты, API-ключ, сертификат доверия | Что PG хранит и назначает |
| Управление | адрес node, `pg-node`, keep-alive, версия, connected, журналы | Может ли панель доставить конфигурацию |
| Нода | фактический процесс, Xray-бинарник, версия, применённый JSON, listeners | Что реально запущено |
| Сеть | bind/listen, firewall/nftables/iptables, fail2ban, маршруты, DNS, source IP | Какие соединения допускаются |
| Клиентский профиль | свежая подписка, адрес/порт, transport, SNI/Host/path, REALITY-поля | Что получает клиент |
| Внешняя проверка | отдельная разрешённая точка, каждый профиль, HTTPS и egress IP | Что работает снаружи |

`connected` означает только канал управления. Работу Xray не подтверждает ни статус узла, ни открытый локальный listener, ни успешный GET панели.

## Снимок конфигурации перед сравнением

Собери таблицу по всем узлам и всем core, включая неиспользуемые core:

| Поле | Значение | Источник | Ревизия/время | Доказательство |
|---|---|---|---|---|
| Node ID/имя/роль |  | PG `GET /api/node` + ранбук |  | адрес управления и SSH разделены |
| Управление | address, порт, keep-alive, connected | PG и `pg-node` |  | read-back + журнал |
| API-key управления | наличие и защищённое равенство `Node.api_key` ↔ `API_KEY` работающего pg-node | PG + окружение PID/контейнера |  | сравнение в памяти или HMAC с одноразовой солью; выводить только match/mismatch |
| Core | ID, tag, назначенная нода | PG |  | полный JSON |
| Inbound | protocol, listen, port, tag, network/security | core и нода |  | применённый JSON |
| REALITY | target/dest, serverNames, shortIds, fingerprint, key presence | core/host/subscription |  | защищённое сравнение |
| Transport | TCP/XHTTP/gRPC, mode/path/serviceName, Host, padding/fragment | core, host, subscription |  | профиль и JSON |
| Egress | `DIRECT.sendThrough`, domainStrategy, outbounds, routing | core и нода |  | полный раздел |
| DNS/policy | servers, queryStrategy, уровни и таймауты | core и нода |  | полный раздел |
| Firewall | клиентские и управляющие порты, source allowlist | нода |  | ruleset/read-only listing |
| Anti-abuse | fail2ban jail, active bans, Cara/VPN source | нода/Cara |  | jail status + ban list |
| Host | ID, remark, address, port, priority, inbound tag | PG |  | полный объект |
| Group | группы и назначение хостов | PG |  | member IDs |
| Subscription | число профилей и фактические поля | свежий ответ |  | замаскированный sample |

Для сравнения API-key сначала убирай только транспортные `CR/LF` и пробелы вокруг значения, затем сравнивай исходные строки в памяти или их HMAC с одной одноразовой солью. Хэширование вывода команды вместе с завершающим переводом строки запрещено: оно создаёт ложное расхождение.

Для каждого значения указывай источник. Если панель, нода и подписка не совпали, это `drift`, а не «почти совпало».

## Алгоритм сравнения узлов

1. Сначала выровняй идентичность: имя машины, роль, текущий IP, SSH-IP, адрес управления, клиентский адрес, служебные порты и исходящий IP. Не копируй IP одной ноды в другую.
2. Сопоставь Node → Core → inbound `tag` → Host → Group → Subscription. Один Host может иметь отдельный адрес и не обязан повторять `Node.address`.
3. Найди дубли тегов во всех core, в том числе не назначенных. Генератор подписки может выбрать старый тег из неиспользуемого core, поэтому «core не назначен» не делает дубликат безопасным.
4. Сравни transport и фактическую выдачу: `tcp`/`xhttp`/`grpc`, порт, SNI, Host, path, serviceName, режим XHTTP, padding/fragment. Слово в alias не является доказательством транспорта; устаревший alias помечай отдельно.
5. Сверь REALITY без вывода секретов: наличие private key, защищённое равенство public key/pbk, принадлежность sid к shortIds, SNI к serverNames, fingerprint к фактическому клиенту.
6. Сравни DNS, policy, routing и outbounds полностью, а не по нескольким знакомым полям. Отдельно отметь `sendThrough`; без него входной адрес не доказывает исходящий IP.
7. Сверь listeners с firewall: клиентские 443/8443/9443/9444 и управляющие 62050/62051 — разные классы. Для management allowlist перечисляй Cara и подтверждённые VPN-egress адреса; неизвестный VPN-адрес нельзя угадывать.
8. Проверь fail2ban и блокировки на ноде и Cara. Наличие таймаута — симптом; бан устанавливай только по журналу/jail/правилу и временной отметке.
9. Запроси свежую подписку тестовой записи, замаскируй токены и персональные ссылки, распарсь каждый профиль и сравни с core/host. Для каждого профиля запиши отдельный результат.
10. Выполни внешнюю проверку с разрешённой точки. Проверка с самой ноды подтверждает только локальную часть. Не объявляй сервис рабочим по одному профилю или по `connected`.

## Как составлять полную спецификацию

Выдавай документ в следующем порядке:

1. **Идентичность и границы** — нода, панель, ревизия, разрешения, что не проверялось.
2. **Ресурс и runtime** — ОС, kernel, CPU/RAM/disk, Docker/compose, `pg-node`, Xray fork/version, binary hash.
3. **Панель PG** — Node, API-key ID и состояние без секрета, trusted certificate presence, Core, inbounds, Hosts, Groups, priorities.
4. **Применённая нода** — процесс, config path, listeners, JSON sections `dns`, `policy`, `routing`, `outbounds`, `stats`, `metrics`.
5. **Транспортная матрица** — отдельная строка на каждый inbound/host/profile.
6. **Сетевой слой** — bind, firewall, fail2ban, routes, DNS resolution, source allowlists, Cara/Mildred/VPN path. Прокси или цепочку указывай только если она реально обнаружена и явно разрешена; не предлагай обход по умолчанию.
7. **Subscription output** — свежий замаскированный sample, число профилей, фактический transport/SNI/Host/path/port.
8. **Расхождения** — `panel→node`, `node→subscription`, `subscription→external`, severity, evidence, root cause или гипотеза.
9. **План исправления** — точный объект и поля, ожидаемый эффект, возможный перезапуск, откат, проверка после записи. План не является выполнением.
10. **DoneWhen** — все уровни либо имеют доказательство, либо явно помечены `unknown/blocked/partial`.

## Паттерны, вынесенные из прошлых расследований

- Полный PUT узла с секретными или нормализованными полями может завершиться TLS EOF после фактической записи. После неизвестного ответа сначала делай GET/read-back; повторяй только после подтверждения состояния. Для небольшого изменения используй минимальный partial update, если API это поддерживает.
- Смена IP требует проверки в четырёх местах: SSH/ОС, `Node.address`, Host address/порт и `DIRECT.sendThrough`. Изменение Host не меняет исходящий IP.
- Смена транспорта без смены alias создаёт ложный отчёт. После TCP↔XHTTP↔gRPC проверяй и фактический профиль, и отображаемое имя.
- `GPRS` в имени машины или ноды — организационное обозначение, а не transport. Транспорт устанавливай только по inbound/core и свежему профилю.
- Дополнительные входы 9443/9444 проверяй как отдельные профили: не смешивай их с рабочими 443/8443, не меняй группы молча и подтверждай, что новые Host реально попали в разрешённую подписку.
- Статус ноды, открытый порт и локальный curl не равны внешней работоспособности. Проверяй каждый профиль с разрешённой внешней машины и отдельно фиксируй незатронутые сети.
- Таймаут между Cara и нодой локализуй по этапам: DNS/маршрут, TCP SYN/SYN-ACK, firewall source set, fail2ban, listener, TLS/pg-node. Не называй конкретный шлюз причиной без захвата или журнала на обеих сторонах.
- Локальный proxy/sing-box, Mildred, Cara и VPN — разные участки пути. Не включай цепочку, туннель или обход без прямого разрешения владельца. Сначала докажи, что путь действительно используется процессом.
- Для 62050/62051 проверяй именно управление `pg-node`, а 443/8443/9443/9444 — клиентские входы. Не смешивай их правила firewall.
- При новом IP проверяй fingerprint и known_hosts; при смене ключа/сертификата сравнивай наличие, fingerprint, SAN и фактическое чтение сервисом. Секреты в отчёт не выводи.
- `keep_alive` — часть управления, а не исправление transport. После изменения проверяй read-back, connected и поведение после интервала, но не приписывай keep-alive причину сетевого падения без журнала.
- «Работает у меня» и клиентское наблюдение — доказательства разных уровней. Клиентский факт записывай отдельно; серверную причину подтверждай серверными данными.

## Jolymmiles и авторские примеры

При работающем Jolymmiles сначала зафиксируй фактическую версию и hash, затем сравнивай с:

- [Jolymmiles/Xray-core](https://github.com/Jolymmiles/Xray-core) и его `AGENTS.md`: server-focused fork, сохранение совместимости, оценка TLS fingerprint, packet size/timing, lifecycle и interop.
- [релизом Jolymmiles v26.11.1-1424](https://github.com/Jolymmiles/Xray-core/releases/tag/v26.11.1-1424): учитывай XHTTP/h2Params, listener-leak fixes и version-skew checks, но не приписывай release note конкретному сбою без логов.
- [XTLS TCP/REALITY example](https://github.com/XTLS/Xray-examples/blob/main/VLESS-TCP-REALITY%20(without%20being%20stolen)/config_server.jsonc), [XHTTP/REALITY server](https://github.com/XTLS/Xray-examples/blob/main/VLESS-XHTTP-Reality/minimal-steal_others/server.jsonc), [XHTTP client](https://github.com/XTLS/Xray-examples/blob/main/VLESS-XHTTP-Reality/minimal-steal_others/client.jsonc) и [gRPC/REALITY example](https://github.com/XTLS/Xray-examples/blob/main/VLESS-gRPC-REALITY/config_server.jsonc).

Ссылки — образцы для проверки структуры и совместимости, а не приказ копировать SNI, target, padding или routing в production. Любое авторское наблюдение отделяй от факта конкретной ноды и от собственной гипотезы.

## Правила изменения и приёмки

Перед записью подготовь таблицу `объект → поля → старое → новое → эффект → откат`. Новая запись требует отдельного подтверждения владельца для названной среды. После записи перечитай тот же объект, проверь применённый процесс, свежую подписку и каждый затронутый профиль. При неизвестном результате записи останови мутации, сделай read-back и только затем решай, можно ли продолжать.

Готовность (`ready`) допустима только когда выполнены все заявленные проверки. Если отсутствует внешняя точка, VPN-egress, SSH-доступ, подписка или свежий read-back, используй `partial`, `blocked` или `unknown` с точным ограничением. Секреты, полные API-ключи, private keys и персональные ссылки никогда не включай в спецификацию.


## Контрольные матрицы Node/Panel

Используй [канонические операторские guardrails](C:/Users/Art/.codex/reference/operator-guardrails.md) для scope, идентичности, сетевой матрицы, geodata, подписки и приёмки. Этот скилл добавляет только специализированный алгоритм сравнения ниже и не копирует общий чек-лист.
