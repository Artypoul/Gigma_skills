# Покрытие настройки и исходные репозитории

Проверка источников: 2026-11-09. Основа панели — PG 5.5.1, commit `eba70d68eaa5a89e34ffebb47c8fd5ce054d0e43`. Сверенный Xray — исходники v26.11.9, commit `676eaf66f8f05d4d558ee7a74b4736623d3feeb9`; это не установленная версия пользователя и не требование обновиться.

## Как использовать перечень

Для полного аудита каждой применимой строке назначь статус «проверено», «не применяется» или «неизвестно», укажи фактическое значение, источник, влияние на обе стороны и способ проверки. Не включай опциональные функции только ради полноты. Если нет клиентского/сетевого теста, неизвестность остаётся видимой.

## Все поля BaseHost PG 5.5.1

Перечень покрывает 30 объявленных полей [BaseHost](https://github.com/PasarGuard/panel/blob/eba70d68eaa5a89e34ffebb47c8fd5ce054d0e43/app/models/host.py#L900). Названия API не обязательно совпадают с подписями UI.

| Поля | Что проверить |
| --- | --- |
| `id`, `remark` | Точный объект для patch, подпись и подстановка переменных; не создавать дубликат вместо изменения выбранного Host. |
| `inbound_tag`, `is_disabled`, `status` | Связь с доступным inbound и группой; отключение и фильтр по статусу пользователя влияют на выдачу. |
| `address`, `port` | Реально выбранная точка подключения, доступность всех объявленных вариантов; адрес не равен SNI/REALITY target. |
| `sni`, `host`, `path`, `use_sni_as_host` | TLS SNI, HTTP host/authority и transport path; при use_sni_as_host HTTP host заменяется выбранным SNI. |
| `security`, `alpn`, `fingerprint`, `allowinsecure` | Наследование и применимость выбранной TLS/REALITY-ветки; не отключать проверку сертификата ради исправления ошибки. |
| `pinned_peer_cert_sha256`, `verify_peer_cert_by_name`, `cipher_suites`, `ech` | Ограничения проверки сертификата, ротация сертификата и поддержка клиентом; различия веток — в panel-mapping. ECH имеет отдельные настройки xray/mihomo/sing_box. |
| `http_headers`, `random_user_agent` | Поддержка транспортом и исходный список User-Agent в client template; random_user_agent не равен TLS fingerprint. Для XHTTP не помещать Host внутрь headers. |
| `transport_settings` | Выбранная ветка транспорта и весь её набор параметров, не произвольная смесь нескольких веток. |
| `mux_settings` | Ветка клиента, enabled/concurrency и XUDP; отдельно от XMux XHTTP. |
| `fragment_settings`, `noise_settings`, `final_mask_settings` | Legacy dialer против FinalMask; внешний транспорт, наследование, порядок слоёв, сериализация и версия core. |
| `vless_route` | Меняет часть выдаваемого UUID, а не обычные routing rules; сохраняй без изменения, если именно эта возможность не запрошена и не проверена. |
| `priority` | Порядок Host; randomize_order при выдаче может его перемешать. Это не проверка доступности и не failover. |
| `subscription_templates` | `xray` — ID client template, действующий в формате Xray; проверить существование и итоговый JSON. |
| `wireguard_overrides` | Только если используется WireGuard: allowed_ips, mtu, reserved, keepalive_seconds, dns; иначе «не применяется». Не переносить в VLESS. |

Источники поведения: [подготовка Host](https://github.com/PasarGuard/panel/blob/eba70d68eaa5a89e34ffebb47c8fd5ce054d0e43/app/core/hosts.py), [выбор значений и фильтры](https://github.com/PasarGuard/panel/blob/eba70d68eaa5a89e34ffebb47c8fd5ce054d0e43/app/subscription/share.py), [VLESS route](https://github.com/PasarGuard/panel/blob/eba70d68eaa5a89e34ffebb47c8fd5ce054d0e43/app/subscription/base.py).

## Вложенные настройки и совместимость

- **XHTTP:** все 22 поля `XHttpSettings` и 6 полей `XMuxSettings` сопоставлены в [panel-mapping](panel-mapping.md#практическая-карта-xhttp-551). Проверь ограничения сочетаний из [transport-recipes](transport-recipes.md), а не только существование полей.
- **Другие транспорты:** `TransportSettings` содержит `tcp_settings`, `grpc_settings`, `websocket_settings`, `kcp_settings`, `masque_settings` помимо XHTTP. Если ветка используется, прочитай её полную модель и обработчик из закреплённых исходников. Network выбирается inbound. Для gRPC проверь serviceName/authority, multi_mode и таймауты; для WS/HTTPUpgrade — path/host/headers; для RAW — header type; для KCP/MASQUE — их собственную схему, без переноса настроек XHTTP.
- **Mux Xray:** `mux_settings.xray.enabled`, `concurrency`, `xudp_concurrency`, `xudp_proxy_udp_443` → outbound `mux`, `xudpConcurrency`, `xudpProxyUDP443`. Проверяй совместимость с flow и QUIC; для sing-box/Mihomo другие ветки. В этой модели `xudp_proxy_udp_443` принимает reject/allow/skip. Выбор зависит от клиента и приложения.
- **Legacy fragment/noise:** модели `fragment_settings.xray` и `fragment_settings.sing_box` различаются. Для Xray проверь packets/length/interval/max_split; для `noise_settings.xray[]` — type/packet/delay/apply_to/rand. Это не схема FinalMask. Риск `max_split` и потеря `dsdialer` описаны в panel-mapping; не обещай эффект по одному заполненному полю.
- **FinalMask:** проверь `tcp[]`, `udp[]`, `quicParams`, точную модель каждого слоя и сериализацию aliases. PG 5.5.1 перечисляет TCP-типы header-custom/fragment/sudoku/xmc; UDP-типы header-custom/mkcp-legacy/noise/salamander/sudoku/xdns/xicmp/realm/udphop и legacy aliases. Не выбирай слой по названию: поддержка core, требования обеих сторон и нужная инфраструктура проверяются отдельно. Наличие xdns/xicmp в модели не разрешает менять DNS, порт 53 или сетевые службы. Server-only filter не добавлять в Host для клиента.
- **QUIC-параметры:** при используемом UDP/QUIC транспорте проверь congestion, bbrProfile/brutalUp/brutalDown, udpHop, окна stream/connection, maxIdleTimeout/keepAlivePeriod, disablePathMTUDiscovery и maxIncomingStreams. Это условная область, не ускоритель для любого RAW/XHTTP-профиля.
- **Смена версий:** поддержка panel renderer и Xray может различаться. В сверенном Xray v26.11.9 старые network h2/h3/http/quic отвергаются, тогда как PG сохраняет обработчики h2 и quic. Не выдавай наличие обработчика панели за поддержку core; не обновляй и не переводь рабочий профиль без отдельного решения. [Проверка transport](https://github.com/XTLS/Xray-core/blob/676eaf66f8f05d4d558ee7a74b4736623d3feeb9/infra/conf/transport_internet.go).

## Core, ноды и клиентский профиль

| Область | Минимальный предмет проверки |
| --- | --- |
| Публикация inbound | Уникальный tag, назначение на фактическую ноду, активная группа пользователя и Host; состояние ноды и реальная версия Xray. Изменение Host не создаёт слушатель. |
| Протокол | UUID и управление пользователями панелью, flow, VLESS encryption/decryption; не заменять динамических пользователей статическим clients из примера. |
| TLS/REALITY | Совместимость имён/ключей/сертификатов, ALPN и fingerprint, target и ограничения REALITY, опциональная ML-DSA-65; см. transport-recipes. |
| Transport | Парность network/path/HTTP host, режим XHTTP, split и конечные адреса обеих частей, FinalMask и ограничения версии. |
| DNS и routing | Где разрешается имя и каким outbound идёт DNS; IPv4/IPv6, порядок правил, доменные/IP-наборы и их наличие, существующие теги, маршрут без совпадений. Серверные правила не меняют автоматически клиентские. |
| Sniffing | Где включён, какие протоколы распознаются, нужны ли destOverride/routeOnly; не заменять адрес назначения без оценки последствий. |
| Mux, sockopt, таймауты | Разделять серверный и клиентский слой. В BaseHost нет общего sockopt; MPTCP, TFO, TCP congestion и dialerProxy нельзя обещать клиенту через выдуманное поле. Проверь поддержку OS/core и фактическую выдачу; sysctl остаётся вне этой задачи. |
| Client template | DNS/routing/inbounds и дополнительные outbounds, ссылки на proxy/direct/block, формат подписки и сохранность при импорте. Шаблон не является универсальным patch сгенерированного outbound. |
| Проверка результата | Синтаксис, соответствие схемам, разбор фактического профиля, подключение и A/B измерения в нужных сетях; каждый уровень подтверждается отдельно. |

Сверенные контракты: [PG Core](https://github.com/PasarGuard/panel/blob/eba70d68eaa5a89e34ffebb47c8fd5ce054d0e43/app/core/xray.py), [PG Xray renderer](https://github.com/PasarGuard/panel/blob/eba70d68eaa5a89e34ffebb47c8fd5ce054d0e43/app/subscription/xray.py), [Xray VLESS](https://github.com/XTLS/Xray-core/blob/676eaf66f8f05d4d558ee7a74b4736623d3feeb9/infra/conf/vless.go), [Xray transport/modes](https://github.com/XTLS/Xray-core/blob/676eaf66f8f05d4d558ee7a74b4736623d3feeb9/infra/conf/transport_method.go), [Xray TLS/REALITY](https://github.com/XTLS/Xray-core/blob/676eaf66f8f05d4d558ee7a74b4736623d3feeb9/infra/conf/transport_security.go), [Xray sockopt](https://github.com/XTLS/Xray-core/blob/676eaf66f8f05d4d558ee7a74b4736623d3feeb9/infra/conf/transport_sockopt.go).

## Исходные репозитории и примеры

Снимки примеров: XTLS/Xray-examples — `167cded1a33ac7b0ce76fcf00ea2d8fb0604e927` (2026-09-16); chika0801/Xray-examples — `383483096aad1e2979d46af17210fe4637438cf5` (2025-12-01); lxhao61/integrated-examples — `e108caafad63726aecfed7eaaeb1538f864b8def` (2026-10-24). Даты относятся к выбранным коммитам репозиториев, не доказывают свежесть каждого файла. Это проверенные источники примеров, не рейтинг по звёздам и не гарантия работоспособности.

| Сценарий и прочитанные файлы | Что учитывать при переносе в PG |
| --- | --- |
| Официальный Vision/REALITY: [client](https://github.com/XTLS/Xray-examples/blob/167cded1a33ac7b0ce76fcf00ea2d8fb0604e927/VLESS-TCP-XTLS-Vision-REALITY/config_client.jsonc), [server](https://github.com/XTLS/Xray-examples/blob/167cded1a33ac7b0ce76fcf00ea2d8fb0604e927/VLESS-TCP-XTLS-Vision-REALITY/config_server.jsonc) | Парность ключей/SNI/shortId и flow; server clients[].flow нужно согласовать с источником flow у PG. Не копировать debug logging как постоянную настройку. |
| Официальный простой XHTTP/REALITY: [client](https://github.com/XTLS/Xray-examples/blob/167cded1a33ac7b0ce76fcf00ea2d8fb0604e927/VLESS-XHTTP-Reality/minimal-steal_others/client.jsonc), [server](https://github.com/XTLS/Xray-examples/blob/167cded1a33ac7b0ce76fcf00ea2d8fb0604e927/VLESS-XHTTP-Reality/minimal-steal_others/server.jsonc) | Совпадение path и REALITY; это заготовки с незаполненными реквизитами. Не подменять выданную PG вложенную форму VLESS плоской формой из примера без проверки core. |
| Официальный XHTTP3: [client](https://github.com/XTLS/Xray-examples/blob/167cded1a33ac7b0ce76fcf00ea2d8fb0604e927/VLESS-XHTTP3-Nginx/client.jsonc), [server](https://github.com/XTLS/Xray-examples/blob/167cded1a33ac7b0ce76fcf00ea2d8fb0604e927/VLESS-XHTTP3-Nginx/server.jsonc) | По умолчанию stream-one, а #downloadSettings/#xmux выключены. Для split комментарий требует stream-up на обеих сторонах. Nginx/UDS и H3 — предпосылки примера, не разрешение их разворачивать. |
| chika0801 Vision/REALITY: [client](https://github.com/chika0801/Xray-examples/blob/383483096aad1e2979d46af17210fe4637438cf5/VLESS-Vision-REALITY/config_client.json), [server](https://github.com/chika0801/Xray-examples/blob/383483096aad1e2979d46af17210fe4637438cf5/VLESS-Vision-REALITY/config_server.json) | Полезен как парный пример; содержит публичные демонстрационные ID/ключи/target. Их не использовать как свои. Снимок старше остальных, не называть его свежей рекомендацией для любого core. |
| lxhao61 XHTTP/REALITY: [client](https://github.com/lxhao61/integrated-examples/blob/e108caafad63726aecfed7eaaeb1538f864b8def/Client%20Configuration/xray_vless_xhttp_reality_config.jsonc), [server](https://github.com/lxhao61/integrated-examples/blob/e108caafad63726aecfed7eaaeb1538f864b8def/Xray%28VLESS%2BXHTTP%2BREALITY%29/xray.jsonc) | Client-файл содержит два альтернативных JSON-объекта, второй использует IPv4/IPv6 split. Выбери один. Правила geosite:cn/geoip:cn, блокировка BitTorrent и дополнительный listener 80 в server — решения автора, не требования маскировки и не настройки для переноса целиком. |

Примеры проверены чтением исходников; это не стендовый тест пары server/client. Перед применением используй реальный экспорт пользователя, его версии и [план проверки](verification.md). При обновлении источника фиксируй новый ref в отчёте задачи; изменение самого скилла требует разрешения пользователя.
