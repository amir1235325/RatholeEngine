# پلن: افزودن Backhaul به‌عنوان core اضافه کنار rathole

> **وضعیت: پیاده‌سازی شد (۱۴۰۵/۰۵/۰۴ — 2026-07-26).** بخش‌های ۲ و ۳ زیر تصمیم‌های *اولیه* را نگه
> داشته‌اند؛ چند مورد حین پیاده‌سازی عوض شد. آنچه واقعاً در کد است:
>
> 1. **مسیر `/_bh/<hex>` حذف شد** — همان‌طور که بخش «نکته‌ی فنی حل‌شده» توضیح می‌دهد، backhaul
>    مسیرهای `/channel` و `/tunnel` را هاردکد می‌کند. پس `ensure_backhaul_path` و آرگومان
>    `<bh_path>` ساخته نشدند.
> 2. **backhaul یک مقدارِ `.transport` روی node است (مثل `noise`)، نه یک فیلد جدای `.backhaul`.**
>    transport هر node دقیقاً یکی است (`ws` / `noise` / `backhaul`) و `gen_server_toml` نودهای
>    backhaul را رد می‌کند — وگرنه rathole-server و backhaul-server هر دو `127.0.0.1:<port>` را
>    bind می‌کنند و دومی بالا نمی‌آید.
> 3. **transport دو طرف عمداً یکی نیست:** TLS فقط روی nginx terminate می‌شود، پس سرور همیشه
>    variant بدون TLS است (`ws`/`wsmux`) و کلاینت variant TLS‌دار (`wss`/`wssmux`) — همان
>    invariant رathole. `backhaul_client_transport` در `common.sh` این نگاشت را انجام می‌دهد.
> 4. **`ports` با فرمت `"127.0.0.1:<port_iran>=<inbound_port_node>"`** نوشته می‌شود (سرویس api هم
>    اضافه شد)، نه فقط `"127.0.0.1:<port>"`.
> 5. **روی نود، `rathole-client` هنگام روشن‌شدن backhaul متوقف و disable می‌شود** — سرویسش از
>    `server.toml` حذف شده و در غیر این صورت crash-loop می‌کند.
> 6. **probe adaptive به `/channel` با هدر `Authorization: Bearer <token>` می‌رود** — بدون توکن
>    backhaul با ۴۰۱ رد می‌کند و adaptive اشتباهاً failover می‌کند.

## Context (چرا)

رathole برای لینک‌های شلوغ/lossy ایران بهینه نیست — هر connection کاربر یک stream مجزا است و mux ندارد. **Backhaul** (هسته‌ی Go از `Musixal/Backhaul`) با SMUX روی `wsmux`/`tcpmux` چند connection را روی یک stream multiplex می‌کند که برای این لینک‌ها بهتر است.

تصمیم‌های نهایی کاربر:
- **Core جدای کنار rathole** (unit/کانفیگ جدا، الگوی noise). نه transport داخل rathole، نه مهاجرت کامل.
- **تک‌پورت 443 / تک‌دامنه حفظ شود** → Backhaul سرور روی `127.0.0.1` می‌شود و **از مسیر مخفی nginx روی همان 443 عبور می‌کند** (مثل control channel رathole و `/_rh/<hex>`).
- **Transport: wsmux پیش‌فرض، و «تا جایی که ممکنه همه»** (tcpmux، ws، wssmux). پلن: wsmux اول؛ بقیه از یک الگوی مشترک.
- **route کاربران همان rathole/nginx با path روی 443 است** — Backhaul یک **backbone mux** اضافه برای مسیر کنترل/دیتا است، نه جایگزین route کاربران.
- **hub + adaptive هم در همین پلن**.

### مدل Backhaul (برخلاف rathole)
- `server` = **ایران** (`bind_addr` + `ports` = کجا listen و به کجای نود فوروارد). 
- `client` = **نود** (`remote_addr`, `connection_pool`, mux params).
- Auth با `token` مشترک (نه cert). mux با SMUX (`mux_con`, `mux_version`, `mux_framesize`, ...).
- Hot-reload داخلی دارد ولی تغییر transport/ports با restart امن‌تر است (مثل noise).

### معماری پیشنهادی (single-port/443 سازگار)
```
[کاربر] --443--> nginx (دامنه, TLS) --path--> rathole-server --> [نود: Xray]   ← route کاربران (بدون تغییر)
[نود Backhaul client] --wss--> nginx 443 --> location /_bh/<hex> --> 127.0.0.1:BH_PORT (backhaul server)   ← backbone mux
```
Backhaul سرور روی `127.0.0.1:<bh_port>` با `transport=wsmux` و `token` مشترک listen می‌کند؛ nginx با یک `location` اختصاصی (`/_bh/<rand-hex>`، مثل `ensure_control_path`) به آن proxy می‌کند. این‌طوری همچنان یک دامنه/443 داریم. چون wsmux از مسیر WS استفاده می‌کند، از nginx عبور می‌کند؛ tcpmux (خام TCP) **نمی‌تواند** از nginx/443 عبور کند — پس tcpmux به یک listener جدا روی پورت خودش نیاز دارد (مثل noise) و با اصل تک‌پورت سازگار نیست → در پلن به‌صورت optional/جدا.

---

## فایل‌ها و تغییرات

### 1) `rathole-manager/common.sh` — نصب binary (الگوی `install_kcptun` common.sh:55)
- تابع جدید **`install_backhaul <role>`**: دانلود `backhaul_linux_<arch>.tar.gz` از `https://github.com/Musixal/Backhaul/releases/download/${BACKHAUL_VER:-vX}` (با همان **حلقه‌ی mirror** غیرفعال‌سازی فیلتر ایران — الگوی `install-panel.sh:163-176` و `install-node.sh:52-56`) → استخراج → `install -m 755 ... /usr/local/bin/backhaul-<role>` (role = server|client).
- تابع **`backhaul_mux_profile <profile>`** (مثل `kcp_profile` common.sh:45): `balanced|lossy|aggressive` → مقادیر `mux_con mux_version mux_framesize mux_recievebuffer mux_streambuffer connection_pool` تا دو طرف هم‌خوان باشند.

### 2) `rathole-manager/ratholectl` (پنل ایران) — الگوی دقیق noise
- **ثابت‌ها** (کنار `NOISE_TOML` ratholectl:31): `BH_TOML=/etc/rathole/backhaul-server.toml`, `BH_SVC=rathole-backhaul-server`, `BH_UNIT=/etc/systemd/system/${BH_SVC}.service`.
- **`ensure_backhaul_path()`** — کپیِ `ensure_control_path` (ratholectl:83): `/_bh/$(openssl rand -hex 16)` در state `.backhaul_path`، یک‌بار ساخته و ذخیره می‌شود. این مسیر مخفی nginx است.
- **`gen_backhaul_server_toml()`** — الگوی `gen_noise_server_toml` (ratholectl:398): اگر `.backhaul_port` نیست return. می‌نویسد `[server]` با `bind_addr="127.0.0.1:<bh_port>"`, `transport`, `token`, mux params، و `ports=[...]` (پورت‌مپینگ). commit با `rth_commit_config` (common.sh:21). 
- **`ensure_backhaul_unit()`** — کپیِ `ensure_noise_unit` (ratholectl:1943): unit systemd `ExecStart=/usr/local/bin/backhaul-server ${BH_TOML}`, `Restart=always`.
- **`gen_nginx_conf()`** (ratholectl:448): اگر `.backhaul_path` ست است، یک `location = <bh_path>` به‌جای/کنار `location = <ctrl_path>` (ratholectl:559) اضافه کن که به `http://127.0.0.1:<bh_port>` با WS-upgrade proxy کند (همان بلاک headers). **نکته‌ی فنی:** این location باید قبل از `location /` match شود (مسیر دقیق `=` این را تضمین می‌کند).
- **`cmd_backhaul()`** — الگوی `cmd_noise` (ratholectl:1965) با subcommandهای `on [port] [--transport wsmux|...] [--token T]`, `off`, `status`, `show`:
  - `on`: `install_backhaul server` → `ensure_backhaul_path` → `state_set .backhaul_port/.backhaul_transport/.backhaul_token` → `ensure_backhaul_unit` → `gen_backhaul_server_toml` → enable → `regenerate` → **restart** `rathole-backhaul-server` → `print_backhaul_connect` (چاپ `ratholenode backhaul on <domain> <bh_path> <token> [transport]`).
  - `off`: jq `del(.backhaul_*)` → disable+rm unit+toml → `regenerate`.
- **`regenerate()`** (ratholectl:786): بلاک backhaul (کنار بلاک noise 834-848) — اگر `.backhaul_port` ست است: `ensure_backhaul_unit` + `gen_backhaul_server_toml` + enable + **restart**.
- **`usage()`** و **`main()` case** (ratholectl:2277): `backhaul) cmd_backhaul "$@" ;;`.
- `.backhaul_port` را به `next_port()` (ratholectl:266) اضافه کن تا با سایر پورت‌ها تداخل نکند.

### 3) `rathole-manager/ratholenode` (نود) — الگوی `cmd_noise`/`cmd_plain`
- **ثابت‌ها** (کنار `KCP_CLI_BIN` ratholenode:263): `BH_CLI_BIN=/usr/local/bin/backhaul-client`, `BH_CLI_UNIT=/etc/systemd/system/rathole-backhaul-client.service`, `BH_TOML=/etc/rathole/backhaul-client.toml`.
- **`gen_backhaul_client_toml()`** — می‌نویسد `[client]` با `remote_addr="<domain>:443"`, `transport`, `token`, `edge_ip` (اختیاری برای CDN)، mux params، `connection_pool`. commit با `rth_commit_config`.
- **`gen_backhaul_client_unit()`** — unit systemd.
- **`cmd_backhaul()`** — الگوی `cmd_noise` (ratholenode:418) با `on <domain> <bh_path> <token> [transport]` / `off` / `status`:
  - `on`: validate `bh_path` (`^/[a-zA-Z0-9/_-]+$`) و `token` → `install_backhaul client` → `env_set`های `BH_REMOTE/BH_PATH/BH_TOKEN/BH_TRANSPORT` در node.env → `gen_backhaul_client_toml` → `gen_backhaul_client_unit` → enable + **restart** `rathole-backhaul-client`.
  - `off`: disable+rm unit → `env_set` پاک‌سازی BH_* .
- **`usage()`** و **`main()` case** (ratholenode:1303): `backhaul) shift; cmd_backhaul "$@" ;;`.
- چون نود **client** است و nginx ایران به `/_bh/<hex>` proxy می‌کند، client باید WS به آن path وصل شود — بررسی شود آیا Backhaul client پارامتر path را می‌پذیرد؛ اگر نه، باید `remote_addr` را مستقیم به IP:443 (بدون path) یا با `edge_ip` تنظیم کرد و در پنل `location /_bh/...` به‌جای path-match، با یک vhost/SNI جدا یا subdomain کار کند. **این تنها نکته‌ی باز فنی است** که هنگام پیاده‌سازی با binary واقعی Backhaul تست می‌شود (مشابه کاری که برای `path` رathole در v1.5.1 کردیم).

### 4) `rathole-manager/install-panel.sh` و `install-node.sh`
- حلقه‌ی mirror دانلود Backhaul (کپی الگوی rathole: install-panel.sh:163-176 / install-node.sh:52-56) — فقط وقتی کاربر backhaul را روشن می‌کند هم کافی است؛ نصب پیش‌فرض اجباری نیست (الگوی kcp که on-demand نصب می‌شود).

### 5) `rathole-manager/ratholehub/hub.py` (Python stdlib) — الگوی noise/plain
- **`build_iran_cmd`** (hub.py:247): `backhaul_on/off/status/show` → argv-list امن (مثل `noise_on` 347-354) با validate `RE_PORT` و `RE_NAME`.
- **`build_node_cmd`** (hub.py:437): `backhaul_on/off/status` → argv-list با validate domain/path/token (regex جدید `RE_BH_PATH=^/[a-zA-Z0-9/_-]+$`).
- **`WRITE_ACTIONS`** (hub.py:550): اضافه کردن `backhaul_on`, `backhaul_off`, ...
- **i18n dicts** (fa ~1700 / en ~1809) + **دکمه‌های UI** (الگوی noise_mode 1704) برای روشن/خاموش/وضعیت backhaul روی پنل و نود.

### 6) `rathole-manager/ratholenode` — adaptive
- `adaptive_run_probe()` (ratholenode:1119): case جدید برای backhaul — probe WS-TLS به مسیر `bh_path` (بازاستفاده از `adaptive_probe_ws_tls` ratholenode:1076) تا در failover شرکت کند. `adaptive.env`/state الگوی موجود را دنبال می‌کند.

---

## اصول معماری که رعایت می‌شود
- **state → regenerate → hot-reload**: هر mutation state را عوض می‌کند بعد `gen_*` + restart؛ config دستی هرگز.
- **Finglish comments/logs** مثل بقیه‌ی کد.
- **in-place write** با `rth_commit_config` (حفظ inode برای config_watcher).
- **restart نه reload** برای تغییر transport/instance (الگوی noise/kcp).
- **hub امن**: هیچ raw-shell — فقط argv-list + regex-validated args.
- **LF endings**، `set -uo pipefail` (نه `-e`)، `rth_mktemp` برای temp.
- **اسم/سرویس/unit conventions**: `rathole-backhaul-server`, `rathole-backhaul-client`، ثابت‌های `BH_*`.

## نکته‌ی فنی حل‌شده (با خواندن سورس Backhaul)
با خواندن سورس (`internal/client/transport/wsmux.go`, `internal/utils/network/ws_dialer.go`, `internal/server/transport/wsmux.go`) معلوم شد:
- **client مسیر WS را هاردکد می‌کند**: `/channel` (control) و `/tunnel/<randomUserID>` (data). قابل‌تغییر در کانفیگ **نیست** (پس طرح اولیه‌ی `/_bh/<hex>` ممکن نیست).
- **server** با `r.URL.Path == "/channel"` و `strings.HasPrefix(r.URL.Path, "/tunnel")` route می‌کند.
- auth با header `Authorization: Bearer <token>` + `X-User-Id`. handshake یک WS-upgrade است (Upgrade: websocket).

**معماری نهایی nginx:** به‌جای `/_bh/<hex>`، دو مسیر `/channel` و `/tunnel` را به backhaul proxy می‌کنیم:
```nginx
location = /channel { proxy_pass http://127.0.0.1:<bh_port>; ...WS upgrade headers... }
location /tunnel    { proxy_pass http://127.0.0.1:<bh_port>; ...WS upgrade headers... }
```
این مسیرها فقط وقتی backhaul روشن است اضافه می‌شوند. چون کاربران به `/` (fake) و `/<node>` (data) می‌روند، `/channel` و `/tunnel` برای کاربران عادی استفاده نمی‌شود و تداخلی نیست. Backhaul client با `remote_addr="<domain>:443"` و `transport=wsmux` به nginx وصل می‌شود؛ nginx TLS را terminate و WS را به backhaul server (127.0.0.1) پاس می‌دهد → **تک‌پورت 443/تک‌دامنه حفظ می‌شود**. mux params باید دو طرف یکی باشند (`backhaul_mux_profile`).

## Verification (تست end-to-end)
1. **syntax**: `bash -n ratholenode ratholectl common.sh install-*.sh` + `python3 -m py_compile hub.py` + `shellcheck`.
2. **harness رathole**: `bash rathole-manager/test-harness.sh` (sandboxed) — چک کند `gen_backhaul_server_toml` و nginx conf بدون خطا تولید می‌شوند و `nginx -t` (stub) پاس می‌شود.
3. **hub mock**: `RATHOLEHUB_MOCK=1 ... python3 hub.py` → باز کردن `http://127.0.0.1:8088` → دکمه‌های backhaul اکشن‌های درست را می‌سازند (در خروجی mock دیده می‌شود).
4. **واحد کانفیگ**: اجرای دستی `gen_backhaul_server_toml`/`gen_backhaul_client_toml` و چک TOML معتبر (`python3 -c "import tomllib; tomllib.load(...)"`).
5. **واقعی (اختیاری)**: روی دو VM تست — `ratholectl backhaul on` → چک `systemctl status rathole-backhaul-server` و `curl` مسیر `/_bh/<hex>` روی 443 → `ratholenode backhaul on <domain> <path> <token>` → چک tunnel بالا می‌آید و mux کار می‌کند.
