# حالت‌های Transport — یک تونل، چند حامل

همان تونل معکوس می‌تواند ترافیک را از **پنج مسیر** حمل کند (به‌علاوه‌ی حالت ویژه‌ی game/SNI). سوییچ بین حالت‌ها **هیچ‌وقت** سرویس‌ها، توکن‌ها یا مسیر (path) کاربران را عوض نمی‌کند — فقط *حاملِ* تونل تغییر می‌کند.

> **حامل هر نود انحصاری است.** پنج دستورِ transport روی نود همگی **یک** متغیر واحد (`TUNNEL` در `node.env`) را می‌نویسند و آخرین دستور برنده است — ترکیب‌شدنی نیستند. به همین دلیل هاب (v1.6) حامل هر نود را با **یک select انحصاری** نشان می‌دهد که تعویضش هر دو سمت را هماهنگ می‌کند؛ سمت ایران سوییچ‌ها فقط می‌گویند کدام حامل‌ها *در دسترس*‌اند.

![حالت‌های transport](assets/transport-modes.svg)

> **اصل ثابت (invariant):** TLS فقط توسط nginx خاتمه می‌یابد؛ transport سمت rathole-server همیشه `tls = false` است. کلاینت پیش‌فرض با `tls = true` روی websocket به nginx/۴۴۳ وصل می‌شود.

## ۱) websocket + TLS (پیش‌فرض)
- کلاینت به `wss://domain:443` وصل می‌شود.
- nginx ریشه‌ی `/` را با `$http_upgrade` بین **سایت فیک** و **کانال کنترلی rathole** تقسیم می‌کند (rathole همیشه از `/` برای کنترل استفاده می‌کند؛ path در rathole قابل‌تنظیم نیست).
- TLS روی nginx خاتمه می‌یابد (گواهی Let's Encrypt).

## ۲) kcp (UDP+FEC)
- مسیر **موازی** UDP+FEC از طریق kcptun برای لینک‌های پرافت (mitigation برای TCP-over-TCP).
- **افزودنی است** — به server/nginx/۴۴۳ دست نمی‌زند؛ یک مسیر ورودی دوم اضافه می‌کند.
- پروفایل‌ها (`balanced`/`lossy`/`aggressive`) باید دو طرف یکی باشند (در `common.sh:kcp_profile`).
- چند-ایران: هر upstream kcp مستقل دارد (`rathole-kcp-up-<id>`، پورت لوکال از ۲۹۹۰۱).
- استتار: UDP/۴۴۳ برای DPI شبیه QUIC/HTTP3 دیده می‌شود و با nginx روی TCP/۴۴۳ تداخل ندارد.
- روشن‌کردن: `ratholectl kcp on [port] [profile]` (ایران) و `ratholenode kcp on <ip:port> <key> [profile]` (نود).

## ۳) plain (بدون TLS)
- websocket بدون TLS به یک listener جداگانه‌ی HTTP (پیش‌فرض ۸۸۸۰).
- سبک‌تر، ولی مسیر تونل بدون رمز nginx است.
- روشن‌کردن: `ratholectl plain on [port]` و `ratholenode plain on <ip:port>`.

## ۴) noise (رمزنگاری‌شده، بدون TLS/گواهی)
- یک **اینستنس دوم rathole** (`rathole-noise`) روی یک پورت TCP عمومی (پیش‌فرض ۲۳۳۴).
- transport از نوع Noise (X25519)؛ کلید خصوصی روی ایران می‌ماند، کلید عمومی منتشر می‌شود.
- سرویس نودهای noise از `server.toml` به `noise-server.toml` جابه‌جا می‌شود.
- روشن‌کردن: `ratholectl noise on [port]` سپس `ratholectl noise node <name> on`؛ نود: `ratholenode noise on <ip:port> <pubkey> [pattern]`.

## ۵) backhaul (هسته‌ی SMUX، پشت همان nginx/۴۴۳)

> یک **هسته‌ی جدا (باینری Go از `Musixal/Backhaul`)** کنار rathole — نه یک transport داخل rathole. برای لینک‌های شلوغ/پرافت که rathole در آن‌ها mux ندارد و هر connection کاربر یک stream مجزاست.

- **چرا:** backhaul با **SMUX** چند connection را روی یک stream مالتی‌پلکس می‌کند؛ روی لینک‌های پرافت بهتر از یک-stream-به-ازای-هر-connection عمل می‌کند.
- **تک‌پورت/تک‌دامنه حفظ می‌شود:** `backhaul-server` روی `127.0.0.1:<backhaul_port>` (پیش‌فرض ۳۰۸۰) گوش می‌دهد و nginx مسیرهای `/channel` (کانال کنترلی) و `/tunnel` (دیتا) را روی همان ۴۴۳ به آن proxy می‌کند. این دو مسیر **در خود backhaul هاردکد شده‌اند** و قابل تنظیم نیستند؛ چون کاربران به `/` (فیک) و `/<node>` (دیتا) می‌روند، تداخلی ندارند.
- **transport دو طرف عمداً یکی نیست:** TLS فقط روی nginx خاتمه می‌یابد، پس سرور همیشه variant **بدون TLS** است (`ws`/`wsmux`) و کلاینت variant **TLS‌دار** (`wss`/`wssmux`) — دقیقاً همان invariant بند بالا. `common.sh:backhaul_client_transport` این نگاشت را انجام می‌دهد و هر دو سمت ورودی اشتباه را رد می‌کنند.
- **`tcpmux` پشتیبانی نمی‌شود:** TCP خام است و از nginx لایه ۷ عبور نمی‌کند.
- **transport هر نود یکی است:** `backhaul` یک مقدارِ `.transport` روی نود است (مثل `noise`). نودِ backhaul از `server.toml` حذف می‌شود و به `ports` در `backhaul-server.toml` می‌رود — وگرنه rathole-server و backhaul-server هر دو `127.0.0.1:<port>` را bind می‌کنند و دومی بالا نمی‌آید. سمت نود هم `rathole-client` متوقف و disable می‌شود.
- **نگاشت پورت:** `"127.0.0.1:<port_ایران>=<inbound_port_نود>"` — یعنی همان پورتی که `map $uri` در nginx به آن اشاره می‌کند دست‌نخورده می‌ماند، پس **مسیر کاربران عوض نمی‌شود**. سرویس `<name>_api` هم اگر باشد اضافه می‌شود.
- **پروفایل mux** (`balanced`/`lossy`/`aggressive` در `common.sh:backhaul_mux_profile`) باید **دو طرف یکی** باشد. `mux_con` فقط سمت سرور و `connection_pool` فقط سمت کلاینت معنا دارد.
- **توکن مشترک** (`openssl rand -hex 20`) جای گواهی را می‌گیرد؛ secret است و فقط به نودهای backhaul داده می‌شود.
- روشن‌کردن: `ratholectl backhaul on [port] [transport] [profile]` سپس `ratholectl backhaul node <name> on`؛ نود: `ratholenode backhaul on <domain> <token> [transport] [profile]` (خروجی `ratholectl backhaul show` خط آماده می‌دهد و hub آن را autofill می‌کند).

## ۶) game / SNI (لایه ۴ passthrough)
- وقتی هر نودی `sni` داشته باشد، پورت ۴۴۳ به حالت **stream/SNI** در nginx (passthrough لایه ۴) می‌رود و vhost لایه ۷ (path/WS) به یک پورت داخلی (`internal_port`، پیش‌فرض ۸۴۴۳) منتقل می‌شود.
- TLSِ ترافیک game روی **نود** خاتمه می‌یابد (گواهی واقعی، VLESS+TLS+Vision) — ایران فقط بایت‌ها را رد می‌کند.
- روشن‌کردن: `ratholectl game add <name> <node_tls_inbound_port> <sni>`.

---

## ۷) direct-IP (masiryabi ba header — ورودیِ کاربری، نه حاملِ تونل)

> این یک **حالتِ ورودی (ingress)** است، نه یک حاملِ transport مثل پنج‌تای بالا. مسیر تونل عوض نمی‌شود؛ فقط یک **درگاهِ ورودیِ دیگر** برای کاربر باز می‌شود که به‌جای path، از یک **هدرِ استتارشده** برای انتخاب نود استفاده می‌کند.

- یک **پورت HTTP سادهٔ جداگانه** (پیش‌فرض ۸۰۸۱) که کاربر **مستقیم به IP سرور ایران** وصل می‌شود — نه دامنه، نه TLSِ nginx.
- تصمیمِ مسیریابی از یک **هدرِ استتارشده** (پیش‌فرض `X-Cdn-Id`) می‌آید که مقدارش = **نام نود** است. `Host` فقط یک **decoy** (مثلاً `myket.ir`) است و در مسیریابی نقشی ندارد.
- nginx با دو `map` (هدر → پورتِ لوکالِ rathole، سپس پورت-یا-fallback → backend) و یک `proxy_pass` مقصد را تعیین می‌کند. درخواست **بدون** هدرِ شناخته‌شده به **سایتِ فیک** می‌افتد (روی این پورت هیچ path-routing نیست).
- **تفاوت با حالت plain (بند ۳):** `plain` یک تعویضِ *حاملِ تونل* بین نود↔ایران است؛ ولی direct-IP یک *ورودیِ کاربری* است که انتخابِ نود را در یک هدر پنهان می‌کند تا دسترسی از راهِ IP خام (سبکِ domain-fronting) بهتر استتار شود. با path-routing معمولِ ۴۴۳ به‌صورت موازی هم‌زیستی دارد.
- **اشتراکِ پورت با plain:** اگر `direct_port == plain_port` باشد، فقط **یک** server block روی آن پورت ساخته می‌شود؛ هدرِ شناخته‌شده برنده است و هدرِ خالی/ناشناس به path-routing (`$backend_port`) می‌افتد.
- **نودهای SNI مستثنا هستند** (روی ۴۴۳ passthroughِ لایه ۴ هستند و پورتِ لایه ۷ لوکال برای HTTP ساده ندارند).
- روشن‌کردن: `ratholectl direct on [--port P] [--header H]`، و `off` / `status` / `show [name]`.

**⚠ امنیت (باید به اپراتور گفته شود):** این listener **بدون TLS، بدون احراز هویت و عمومی** است. محرمانگی و احراز هویت **در لایهٔ پروکسیِ داخلِ تونل** (VLESS/VMess UUID و…) انجام می‌شود، نه این لایه. هدر یک **راهنمای مسیریابی + استتار** است، **نه یک اعتبارنامهٔ محرمانه** — هرکس نامِ یک نود را بداند به inboundِ آن نود می‌رسد (که خودش احراز هویت خودش را اعمال می‌کند). نامِ هدر و نامِ نودها پیش از رسیدن به `map` به‌شدت اعتبارسنجی می‌شوند، پس هیچ ورودیِ اپراتور بدون escape داخل کانفیگ درج نمی‌شود. باز کردن `direct_port` روی اینترفیسِ عمومی یک تغییرِ فایروال است که صریحاً به اپراتور اطلاع داده می‌شود (`warn` + تلاشِ best-effort برای `ufw allow`).

---

## ۸) proxy (ریورس‌پروکسی غیرتونلی — مسیر به upstream دلخواه)

> این هم **حاملِ تونل نیست**؛ یک مسیر `/<name>/` روی همان ۴۴۳ است که **بدون عبور از rathole** به یک upstream دلخواه proxy می‌شود — برای تونل‌ها یا سرویس‌های مستقلی که rathole مدیریتشان نمی‌کند.

- state در `.proxies[]` با `{name, upstream}` نگه داشته می‌شود و در `gen_nginx_conf` یک `location /<name>/` با `proxy_pass` ساخته می‌شود.
- **upstream فقط `http(s)://host:port`** — بدون مسیر/query/متاکاراکتر، با regex سخت؛ چون مستقیم به کانفیگ nginx می‌رود.
- **فضای‌نام مشترک با نودها:** هر دو در `map $uri` می‌نشینند؛ `proxy add` با نامِ یک نودِ موجود رد می‌شود و برعکس. نام‌های `sub`/`hub`/`channel`/`tunnel` رزرواند.
- **امنیت:** upstream **اعتمادشده** فرض می‌شود — اپراتور می‌تواند nginx را به میزبان دلخواه اشاره دهد.
- دستورها: `ratholectl proxy add <name> <http(s)://host:port>` / `proxy rm <name>` / `proxy ls`؛ از هاب هم با اکشن‌های `proxy_add`/`proxy_rm`/`proxy_ls`.

---

**نکته‌ی کلیدی:** در حالت‌های ۱ تا ۵، سرویس‌ها/توکن‌ها/مسیر کاربران دست‌نخورده می‌مانند؛ فقط حاملِ تونل عوض می‌شود. برای جزئیات مسیر بسته لایه‌به‌لایه: [`traffic-flow.md`](traffic-flow.md).

---

## همچنین ببینید

- [مرجع کامل دستورات CLI (ویکی)](https://github.com/loopy-iri/RatholeEngine/wiki/CLI-Reference) — syntax کامل همه دستورات
- [راهنماهای عملی (ویکی)](https://github.com/loopy-iri/RatholeEngine/wiki/Workflow-Guides) — راه‌اندازی direct-IP، مهاجرت به backhaul، چند دامنه، multi-upstream
- [`transport-modes.en.md`](transport-modes.en.md) — نسخه انگلیسی همین سند
- [`architecture.md`](architecture.md) — معماری کلی سیستم

> یک لایه‌ی **خودکار** بالای حالت‌های ۱–۵. حاملِ فعال را بدون دخالت اپراتور عوض می‌کند.

- **probe‌های bounded:** هر بازه (پیش‌فرض ۳۰ ثانیه) یک WebSocket RFC 6455 به `WS_PATH` می‌فرستد؛ طبقه‌بندی مستقیم:
  `dns_failed` → `tcp_timeout` → `tls_failed` → `ws_rejected` → `ws_timeout` → `healthy`
- **threshold/hysteresis:** پس از `ADAPTIVE_FAILURES` (پیش‌فرض ۳) شکست متوالی سوییچ؛ پس از `ADAPTIVE_RECOVERIES` (پیش‌فرض ۵) بازگشت سالم + اتمام cooldown.
- **cooldown:** `ADAPTIVE_COOLDOWN` (پیش‌فرض ۳۰۰ ثانیه) بین سوییچ‌های متوالی.
- **حامل‌های اولویت‌دار:** `ws` → `kcp` (و در صورت `ALLOW_INSECURE=1`: `plain`). plain هرگز بدون اجازه‌ی صریح انتخاب نمی‌شود.
- **rollback خودکار:** اگر probe پس از سوییچ هم fail باشد، config قبلی بازیابی می‌شود.
- **state sanitize:** `/etc/rathole/adaptive-state.json` (mode 0600) فقط فیلدهای `time`, `current`, `classification`, `latency_ms`, `consecutive_failures` دارد — هیچ token/key/WS_PATH در JSON نیست.
- روشن‌کردن: `ratholenode adaptive on [--interval N] [--failures N] [--recoveries N]`، خاموش: `off`، وضعیت: `status`، تست: `test [--json]`.

## ۹) secret WebSocket control path (v1.5.0+)

> مسیر WebSocket کنترلی rathole از `/` به `/_rh/<32 hex>` منتقل شد تا DPI نتواند آن را از سایت فیک تشخیص دهد.

- **nginx:** فقط `location = /_rh/<secret>` از `$http_upgrade` به control port می‌رود؛ همه‌ی مسیرهای دیگر رفتار fake/data خود را حفظ می‌کنند.
- **مدیریت:** `ratholectl control-path show` نشان‌دهنده، `rotate` مسیر جدید می‌سازد و grace period برای به‌روزرسانی نودها فراهم می‌کند.
- **نود:** `WS_PATH` در `node.env` ذخیره می‌شود و در `client.toml` به‌عنوان `path = "/_rh/..."` درج می‌شود (patch‌ی از core روی `WebsocketConfig.path`).
- **نمایش:** `cmd_show` مقدار `WS_PATH=<masked>` چاپ می‌کند — هیچ secret کامل در لاگ پدیدار نمی‌شود.

---

**نکته‌ی کلیدی:** در حالت‌های ۱ تا ۵، سرویس‌ها/توکن‌ها/مسیر کاربران دست‌نخورده می‌مانند؛ فقط حاملِ تونل عوض می‌شود. برای جزئیات مسیر بسته لایه‌به‌لایه: [`traffic-flow.md`](traffic-flow.md).
