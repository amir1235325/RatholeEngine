# عیب‌یابی، بک‌آپ و رول‌بک

---

## ابزار تشخیص خودکار

```bash
sudo ratholectl doctor
# چک‌لیست سرویس‌ها، پورت‌های لوکال، تست WS به control-path
# خروجی OK/FAIL برای هر بررسی + خلاصه‌ی نهایی
```

---

## بررسی لاگ‌ها

```bash
# ایران — همه سرویس‌ها یکجا (توکن/کلید redact می‌شوند)
sudo ratholectl logs [n]
sudo ratholectl logs --bundle   # فشرده برای اشتراک‌گذاری

# نود خارج
sudo ratholenode logs [n]
sudo ratholenode logs all       # main + upstreamها

# مستقیم از journalctl
sudo journalctl -u rathole-server -n 50 --no-pager
sudo journalctl -u rathole-client -n 50 --no-pager
sudo journalctl -u rathole-backhaul-server -n 50 --no-pager
sudo journalctl -u rathole-backhaul-client -n 50 --no-pager
```

---

## مشکلات رایج

### tunnel وصل نمی‌شود

| نشانه | علت | راه‌حل |
|-------|-----|---------|
| نود log `retrying` دائمی دارد | آدرس/پورت اشتباه، یا control-path ناهماهنگ | `ratholenode show` → `SERVER` را بررسی کن؛ `ratholectl control-path show` با مقدار `WS_PATH` در نود تطبیق بده |
| `nginx -t` خطا می‌دهد | config دستی ویرایش شده یا regenerate ناقص | `sudo ratholectl regen` → اگر باز هم خطا: `ratholectl recover` |
| نود وصل است ولی ترافیک نمی‌رسد | `map $uri` یا `inbound_port` اشتباه | `ratholectl ls` → port نود با config Xray/VLESS تطبیق بده |

### Backhaul

| نشانه | علت | راه‌حل |
|-------|-----|---------|
| `control channel` مدام قطع/وصل | دو نود با یک token، یا profile ناهماهنگ | فقط یک نود به ازای هر توکن؛ profile دو طرف را یکی کن |
| کلاینت backhaul وصل نمی‌شود | transport اشتباه | سرور `ws`/`wsmux` و نود `wss`/`wssmux` — عمداً متفاوتند |
| `rathole-client` روی نود backhaul خطا | طبیعی است | سرویس عمداً متوقف است؛ backhaul جایگزین است |
| port bind نمی‌شود | نود هنوز در `server.toml` مانده | `ratholectl backhaul node <name> on` → `regen` |
| سرویس بالا نمی‌آید، لاگ `Usage: ... -c` | نسخه‌ی قدیمی یونیت | آپدیت به ≥ v1.6.0 |
| دو نود backhaul با همان inbound_port | backhaul 1:1 است — دو ماشین جداگانه نمی‌توانند | هر سرور ایران فقط یک ماشین خارجی می‌تواند backhaul داشته باشد |

### Direct-IP

| نشانه | علت | راه‌حل |
|-------|-----|---------|
| کاربر به سایت فیک می‌رود | header وجود ندارد یا نام نود اشتباه | مقدار header باید دقیقاً نام نود باشد (`ratholectl direct show <name>`) |
| پورت direct-IP باز نیست | فایروال | `ufw allow <port>/tcp` (کد خودش تلاش می‌کند) |
| SNI node از direct-IP استفاده نمی‌کند | SNI nodeها L4 passthrough هستند و پورت direct-IP ندارند | این محدودیت ذاتی است |

### Noise

| نشانه | علت | راه‌حل |
|-------|-----|---------|
| اتصال noise قطع می‌شود | pubkey ناهماهنگ | `ratholectl noise status` → pubkey را کپی و روی نود `ratholenode noise on <ip:port> <pubkey>` بزن |
| noise service بالا نمی‌آید | پورت در استفاده است | `ratholectl noise on <port>` با پورت دیگری |

### Adaptive Failover

| نشانه | علت | راه‌حل |
|-------|-----|---------|
| adaptive سوئیچ نمی‌کند | `kcp` روی سرور ایران فعال نیست | `ratholectl kcp on` روی ایران + `ratholenode kcp on` روی نود |
| adaptive مدام سوئیچ می‌کند | threshold خیلی پایین یا cooldown کم | `ratholenode adaptive on --failures 5 --recoveries 8 --interval 45` |
| وضعیت `ws_rejected` | control-path ناهماهنگ | `ratholectl control-path show` و مقایسه با `node.env/WS_PATH` |

### چند دامنه (domain)

| نشانه | علت | راه‌حل |
|-------|-----|---------|
| `nginx -t` بعد از `domain add` خطا | گواهی پیدا نشد | مسیر `--fullchain` و `--key` را بررسی کن یا از `--certbot` استفاده کن |
| دامنه اضافی کار نمی‌کند | DNS به این سرور اشاره نمی‌کند | DNS را بررسی کن؛ بعد `ratholectl regen` |
| nginx crash loop بعد از `domain add` | `default_server` conflict | `ratholectl recover` → nginx را به‌حالت تک‌دامنه برگرداند |

### گواهی IP (ip-cert)

| نشانه | علت | راه‌حل |
|-------|-----|---------|
| نود با `set-main` به IP وصل نمی‌شود | گواهی self-signed trusted نیست | `ratholectl ip-cert-show <ip>` → cert را در `/etc/rathole/trusted-<ip>.pem` ذخیره کن → `ratholenode set-main <ip>:443 <ip> /etc/rathole/trusted-<ip>.pem` |
| `ip-cert-off` خطا می‌دهد | backhaul direct_ip با wss/wssmux از همین گواهی استفاده می‌کند | اول backhaul را به `wsmux` تغییر بده |

---

## بک‌آپ و رول‌بک

### آپدیت با بک‌آپ خودکار

```bash
ratholectl update      # snapshot کامل → آپدیت → health-check → رول‌بک خودکار در صورت شکست
ratholenode update
```

### مدیریت دستی بک‌آپ‌ها

```bash
# ایران
sudo ratholectl backup [file]       # snapshot از state + configs
sudo ratholectl restore [file]

# نود
sudo ratholenode backup [file]      # node.env + services + upstreamها
sudo ratholenode restore <file>

# رول‌بک از snapshot آپدیت
sudo update.sh --list-backups
sudo update.sh --rollback                         # آخرین snapshot سالم
sudo update.sh --rollback 20260725-094447         # یک snapshot خاص
```

### بک‌آپ nginx (داخل regenerate)

هر بار که `regenerate` موفق می‌شود، یک `.rathole-good.bak` از config nginx ذخیره می‌شود. اگر `nginx -t` شکست بخورد، همان فایل خودکار بازگردانده می‌شود.

```bash
sudo ratholectl recover    # حذف همه دامنه‌های اضافی + بازتولید تک‌دامنه

---

## همچنین ببینید

- **[مرجع کامل CLI](CLI-Reference)** — syntax دقیق همه دستورات
- **[راهنماهای عملی](Workflow-Guides)** — گام‌به‌گام: direct-IP، backhaul، چند دامنه، multi-upstream
```

