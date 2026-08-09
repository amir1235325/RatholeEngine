# مرجع کامل دستورات CLI

## نمای سریع (Quick Reference)

| گروه | ratholectl | ratholenode |
|------|-----------|-------------|
| وضعیت | `status` · `ls` · `show` · `doctor` · `logs` · `version` | `status` · `show` · `ls` · `logs` · `check` · `version` |
| مدیریت | `add` · `rm` · `edit` · `rename` · `rotate` | `add-svc` · `rm-svc` · `set` · `set-main` · `apply` |
| پیکربندی | `set` · `init` · `regen` · `paths` · `info` | `backup` · `restore` · `migrate` |
| بک‌آپ | `backup` · `restore` · `recover` | `backup` · `restore` |
| حامل تونل | `kcp` · `plain` · `noise` · `backhaul` | `kcp` · `plain` · `noise` · `backhaul` |
| ورودی کاربر | `direct` · `proxy` · `game` | — |
| multi-Iran | — | `upstream` · `watchdog` · `adaptive` |
| دامنه/گواهی | `domain` · `cert` · `ip-cert` · `control-path` | — |
| Hub/System | `hub` · `tune` · `fakeweb` · `update` | `tune` · `fakeweb` · `update` |

---

## ratholectl — سرور ایران

### وضعیت و اطلاعات

```bash
ratholectl status            # وضعیت سرویس‌ها، پورت‌ها، transport فعال
ratholectl status --json     # همان، به‌صورت JSON
ratholectl version           # نسخه‌ی ratholectl و باینری rathole
ratholectl ls                # لیست نودها با پورت و transport
ratholectl show <name>       # جزئیات و دستور نصب یک نود
ratholectl token <name>      # نمایش دستور نصب (مترادف show)
ratholectl info              # خلاصه‌ی کامل پیکربندی (دامنه، گواهی، پورت‌ها)
ratholectl certs             # بررسی انقضای گواهی‌های فعال
ratholectl paths             # نمایش همه‌ی مسیرهای فایل (state، configs، units)
ratholectl doctor            # چک‌لیست سلامت سرویس‌ها، پورت‌ها و تست WS
ratholectl logs [n]          # آخرین n خط لاگ همه سرویس‌ها (پیش‌فرض ۵۰)
ratholectl logs --bundle     # همان، فشرده در یک .txt.gz برای اشتراک‌گذاری
```

### مدیریت نودها

```bash
ratholectl add <name> <inbound_port> [--api-port N]
# افزودن نود؛ دستور نصب کامل را چاپ می‌کند
# --api-port: پورت inbound کانال مدیریت (برای دسترسی hub به نود)

ratholectl rm <name>         # حذف نود و regenerate

ratholectl edit <name> [--inbound N] [--api-port N|off]
# ویرایش پورت inbound یا کانال مدیریت یک نود موجود

ratholectl rename <old> <new>
# تغییر نام نود (= تغییر path کاربری /$old → /$new)
# ⚠ روی نود هم باید service را rename کنید: rm-svc + add-svc

ratholectl rotate <name>
# چرخش توکن نود (و api_token اگر دارد)
# نود باید با توکن جدید دوباره نصب/آپدیت شود
```

### پیکربندی

```bash
ratholectl set domain        <value>   # دامنه اصلی
ratholectl set fullchain     <path>    # مسیر fullchain.pem
ratholectl set key           <path>    # مسیر privkey.pem
ratholectl set fake-port     <N>       # پورت سایت فیک (پیش‌فرض ۸۰۸۰)
ratholectl set sub-port      <N>       # پورت subscription (پیش‌فرض ۲۰۹۶)
ratholectl set control-port  <N>       # پورت کنترل rathole (پیش‌فرض ۲۳۳۳)
ratholectl set sub-path      <seg>     # بخش path برای sub (پیش‌فرض sub)
ratholectl set hub-path      <seg>     # بخش path برای hub (پیش‌فرض hub)
ratholectl regen             # بازتولید server.toml + nginx.conf و hot-reload

ratholectl init              # راه‌اندازی اولیه تعاملی (اگر از install.sh استفاده نشده)
ratholectl init --panel --domain <d> --fullchain <f> --key <k>
# نصب غیرتعاملی (همان flags که install.sh می‌گیرد)
```

### بک‌آپ و بازیابی

```bash
ratholectl backup [file]     # snapshot از state.json + configs (پیش‌فرض /root/rathole-panel-backup-<ts>.tar.gz)
ratholectl restore [file]    # بازگردانی state + configs از backup

ratholectl recover
# حذف همه دامنه‌های اضافی و بازتولید تک‌دامنه — برای رفع خرابی nginx
```

### حامل‌های تونل (Transport)

هر حامل یک listener/core مستقل است؛ روشن/خاموش‌شان سرویس‌ها و مسیر کاربران را عوض نمی‌کند.

```bash
# KCP — مسیر موازی UDP+FEC
ratholectl kcp on [port] [profile]   # profile: balanced | lossy | aggressive (پیش‌فرض balanced)
ratholectl kcp off
ratholectl kcp status
ratholectl kcp show   # کلید و دستور آماده برای نود

# Plain — WebSocket بدون TLS روی پورت HTTP جدا
ratholectl plain on [port]           # پیش‌فرض ۸۸۸۰
ratholectl plain off
ratholectl plain status

# Noise — رمزنگاری X25519 بدون گواهی (اینستنس دوم rathole)
ratholectl noise on [port]           # پیش‌فرض ۲۳۳۴
ratholectl noise off
ratholectl noise status
ratholectl noise node <name> on      # انتقال این نود به transport=noise
ratholectl noise node <name> off     # برگرداندن نود به transport پیش‌فرض

# Backhaul — مالتی‌پلکس SMUX (هسته‌ی Go جدا، پشت همان nginx/443)
ratholectl backhaul on [port] [transport] [profile]
# transport: wsmux (پیش‌فرض) | wssmux (برای backhaul-e direct-IP)
# profile: balanced | lossy | aggressive
ratholectl backhaul off
ratholectl backhaul status
ratholectl backhaul show             # خط آماده‌ی ratholenode backhaul on را چاپ می‌کند
ratholectl backhaul node <name> on   # انتقال نود به transport=backhaul
ratholectl backhaul node <name> off  # برگرداندن نود
```

### ورودی‌های کاربری (Ingress)

> این‌ها **حامل تونل** نیستند — راه ورود جایگزین برای کاربر هستند؛ مسیر تونل بین نود↔ایران دست‌نخورده می‌ماند.

```bash
# Direct-IP — ورود مستقیم به IP سرور با header استتارشده (بدون دامنه/TLS)
ratholectl direct on [--port P] [--header H]
# پیش‌فرض: port=8081، header=X-Cdn-Id؛ مقدار header = نام نود
# ⚠ پورت جدید را در فایروال باز کنید (کد خودش ufw را امتحان می‌کند)
ratholectl direct off
ratholectl direct status
ratholectl direct show [name]    # URL و header آماده برای کاربر

# Proxy — مسیر /<name>/ روی همان 443 به یک upstream دلخواه (بدون عبور از rathole)
ratholectl proxy add <name> <http(s)://host:port>
ratholectl proxy rm <name>
ratholectl proxy ls
```

### Game / SNI (L4 Passthrough)

وقتی یک نود `sni` داشته باشد، پورت ۴۴۳ به حالت stream/SNI nginx (passthrough لایه ۴) می‌رود و vhost لایه ۷ به `internal_port` (پیش‌فرض ۸۴۴۳) منتقل می‌شود.

```bash
ratholectl game add <name> <node_tls_port> <sni>
# name = نام نود روی نود + SNI که کاربر می‌بیند
# node_tls_port = پورتی که Xray/VLESS+TLS روی نود گوش می‌دهد
ratholectl game rm <name>
ratholectl game ls
ratholectl game cert <name>      # نمایش public cert گواهی نود (برای pin کردن)
```

### مسیر کنترلی مخفی

```bash
ratholectl control-path show     # مسیر /_rh/<hex> جاری (masked در لاگ)
ratholectl control-path rotate   # مسیر جدید تولید می‌کند؛ نودها باید آپدیت شوند
```

### چند دامنه

```bash
ratholectl domain add <domain> [--certbot] [--email E] [--fullchain F] [--key K]
# دامنه اضافی روی همان سرور؛ اگر گواهی ندارد از گواهی دامنه اصلی استفاده می‌کند
ratholectl domain rm <domain>
ratholectl domain ls
ratholectl domain primary <domain> [--certbot] [--email E] [--fullchain F] [--key K]
# تغییر دامنه اصلی + گواهی آن

# گواهی Let's Encrypt با certbot (تعاملی‌تر از --certbot در domain add)
ratholectl cert <domain> [email]

# گواهی self-signed برای ورود مستقیم به IP (بدون دامنه)
ratholectl ip-cert <IPv4> [days]       # ساخت/بارگذاری گواهی (پیش‌فرض ۸۲۵ روز)
ratholectl ip-cert-show [IP]           # نمایش public cert
ratholectl ip-cert-off                 # حذف vhost IP TLS
```

### Hub

```bash
ratholectl hub on [port]   # نصب خودکار hub اگر نصب نشده + فعال‌سازی پشت nginx/443/hub/
# پورت پیش‌فرض ۸۰۸۸؛ nginx مسیر /hub/ را به 127.0.0.1:port proxy می‌کند
ratholectl hub off         # location /hub/ را از nginx حذف می‌کند (service می‌ماند)
ratholectl hub status      # وضعیت service و port، هشدار اگر port ناهماهنگ باشد
```

### سیستم

```bash
ratholectl fakeweb on [port]   # سایت فیک روی پورت HTTP داخلی (پیش‌فرض ۸۰۸۰)
ratholectl fakeweb off

ratholectl tune                # اعمال تنظیمات sysctl برای عملکرد بهتر (BBR، buffer، ...)

ratholectl restart             # ری‌استارت rathole-server (همه تانل‌ها لحظه‌ای قطع می‌شوند)

ratholectl update              # آپدیت به آخرین نسخه‌ی پایدار
ratholectl update beta         # آخرین نسخه‌ی pre-release
ratholectl update v1.7.0       # آپدیت به یک نسخه‌ی خاص
```

---

## ratholenode — نود خارج

### وضعیت و اطلاعات

```bash
ratholenode status           # transport فعال، endpoint، وضعیت service
ratholenode status --json    # همان، JSON
ratholenode version          # نسخه‌ی ratholenode
ratholenode show             # محتوای node.env + لیست سرویس‌ها
ratholenode ls               # لیست سرویس‌های ثبت‌شده
ratholenode check            # تست سریع اتصال (بررسی DNS + TCP + TLS)
```

### مدیریت سرویس

```bash
ratholenode add-svc <name> <token> <inbound_port>
# افزودن سرویس به tunnel؛ از دستور خروجی ratholectl show بگیرید

ratholenode rm-svc <name>    # حذف سرویس

ratholenode set SERVER <host:port>
# تغییر آدرس سرور ایران (tunnel اصلی)

ratholenode set-main <host:port> [tls_hostname] [trusted_root]
# تنظیم اتمیک سرور + TLS SNI + CA سفارشی (برای direct-IP با ip-cert)
# tls_hostname: نام دامنه برای SNI (اگر با IP وصل می‌شوید)
# trusted_root: مسیر fullchain.pem گواهی self-signed سرور ایران

ratholenode apply            # بازتولید client.toml و hot-reload (بدون restart)
ratholenode logs [n]         # آخرین n خط لاگ tunnel اصلی (پیش‌فرض ۵۰)
ratholenode logs all         # لاگ همه سرویس‌ها + upstreamها
```

### حامل‌های تونل

```bash
ratholenode kcp on <ip:port> <key> [profile]   # profile: balanced|lossy|aggressive
ratholenode kcp off
ratholenode kcp status

ratholenode plain on <ip:port>   # WebSocket بدون TLS
ratholenode plain off
ratholenode plain status

ratholenode noise on <ip:port> <pubkey> [pattern]
ratholenode noise off
ratholenode noise status

ratholenode backhaul on <domain> <token> [transport] [profile]
# transport: wssmux (پیش‌فرض، TLS) | wss | wsmux | ws
# دستور آماده را از ratholectl backhaul show بگیرید
ratholenode backhaul off
ratholenode backhaul status
```

### Adaptive Failover (سوئیچ خودکار)

```bash
ratholenode adaptive on [--interval N] [--failures N] [--recoveries N]
# interval: بازه‌ی probe به ثانیه (پیش‌فرض ۳۰)
# failures: تعداد شکست متوالی برای سوئیچ (پیش‌فرض ۳)
# recoveries: تعداد موفقیت متوالی برای بازگشت (پیش‌فرض ۵)
ratholenode adaptive off
ratholenode adaptive status  # transport فعال، نتیجه‌ی آخرین probe
ratholenode adaptive test [--json]  # یک probe اجرا و نتیجه را فوری نشان می‌دهد
```

### Upstream — چند سرور ایران

نود می‌تواند هم‌زمان به چند سرور ایران وصل باشد. هر upstream یک `rathole-client@<id>` مستقل است.

```bash
ratholenode upstream add <id> <server:port> [hostname]
ratholenode upstream add-svc <id> <name> <token> <inbound>
ratholenode upstream rm-svc <id> <name>
ratholenode upstream rm <id>
ratholenode upstream apply <id>        # بازتولید client.toml این upstream
ratholenode upstream restart <id>
ratholenode upstream ls                # لیست همه upstreamها
ratholenode upstream status <id>
ratholenode upstream logs <id> [n]
ratholenode upstream kcp   <id> on <ip:port> <key> [profile] | off | status
ratholenode upstream plain <id> on <host:port> | off | status
ratholenode upstream noise <id> on <host:port> <pubkey> [pattern] | off | status
ratholenode upstream ws    <id>        # برگشت به transport=ws
```

### Watchdog — راه‌اندازی مجدد خودکار

```bash
ratholenode watchdog on [interval_sec]   # پیش‌فرض ۶۰ ثانیه
# یک systemd timer می‌سازد که tunnel گیر‌کرده/قطع را restart می‌کند
ratholenode watchdog off
ratholenode watchdog status
```

### بک‌آپ

```bash
ratholenode backup [file]    # node.env + services.conf + upstreams (پیش‌فرض /root/rathole-node-backup-<ts>.tar.gz)
ratholenode restore <file>   # بازگردانی + بازتولید client.toml + restart
```

### ابزارهای تشخیص

```bash
ratholenode migrate
# نقشه‌ی مهاجرت همه tunnelها (main + upstreamها) به KCP را چاپ می‌کند
# دستورات دو طرف را آماده نشان می‌دهد؛ هیچ تغییری اعمال نمی‌کند

ratholenode check
# تست سریع DNS + TCP + TLS اتصال به سرور ایران
```

### سیستم

```bash
ratholenode tune             # اعمال sysctl برای بهینه‌سازی (BBR، buffer، ...)
ratholenode fakeweb on [port]
ratholenode fakeweb off
ratholenode restart          # ری‌استارت rathole-client (همه tunnelها لحظه‌ای قطع می‌شوند)
ratholenode update           # آپدیت به آخرین نسخه‌ی پایدار
ratholenode update beta      # آخرین pre-release
ratholenode update v1.7.0    # آپدیت به نسخه‌ی خاص
```

---

## نکات مشترک

**توکن backhaul از توکن‌های سرویس جداست** — با `openssl rand -hex 20` تولید کنید و فقط به نودهای backhaul بدهید.

**transport دو طرف backhaul عمداً متفاوت است:** سرور ایران `ws`/`wsmux` (بدون TLS) و نود `wss`/`wssmux` (با TLS) می‌گیرد. `tcpmux` از nginx لایه ۷ عبور نمی‌کند.

**هر نود دقیقاً یک transport دارد.** آخرین دستور برنده است — قبل از سوئیچ، transport قبلی را `off` کنید.

**آپدیت همیشه قبل از تغییر یک snapshot کامل می‌گیرد.** در صورت خرابی: `ratholectl update --rollback` یا `update.sh --rollback`.

