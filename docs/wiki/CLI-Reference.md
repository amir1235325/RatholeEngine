# مرجع کامل دستورات CLI (ratholectl & ratholenode)

این سند تمامی دستورات خط فرمان موجود در ابزارهای مدیریت پنل ایران (`ratholectl`) و نود خارج (`ratholenode`) را پوشش می‌دهد.

---

## 🇮🇷 ابزار مدیریت سرور ایران (`ratholectl`)

### دستورات عمومی و وضعیت:
- `ratholectl status`: نمایش وضعیت سرویس rathole و nginx و پورت‌ها.
- `ratholectl status --json`: خروجی وضعیت به فرمت JSON برای استفاده در اتوماسیون.
- `ratholectl ls`: لیست نودهای تعریف‌شده به همراه پورت‌های ورودی و وضعیت.
- `ratholectl show <node_name>`: مشاهده مشخصات و توکن اختصاصی یک نود.
- `ratholectl version`: نمایش نسخه جاری ratholectl و باینری rathole.

### مدیریت نودها:
- `ratholectl add <name> <inbound_port>`: افزودن نود جدید و تولید دستور نصب خودکار.
- `ratholectl rm <name>`: حذف نود.
- `ratholectl token <name>`: بازتولید یا مشاهده توکن نود.

### مدیریت مسیر مخفی کنترلی (Secret Control Path):
- `ratholectl control-path show`: مشاهده مسیر مخفی جریانی WebSocket (مثلاً `/_rh/a1b2c3...`).
- `ratholectl control-path rotate`: ساخت مسیر مخفی جدید و چرخش آن با حفظ سازگاری نودهای قبلی.

### حامل‌های تونل (Transport):
هر نود دقیقاً **یک** حامل دارد. سوییچ بین حامل‌ها مسیر (path) کاربران را عوض نمی‌کند.

- `ratholectl kcp on [port] [profile]` / `off` / `status` / `show`: مسیر موازی UDP+FEC.
- `ratholectl plain on [port]` / `off`: وب‌سوکت بدون TLS روی یک پورت HTTP جدا.
- `ratholectl noise on [port]` سپس `ratholectl noise node <name> on`: تونل رمزنگاری‌شده بدون گواهی.
- `ratholectl backhaul on [port] [transport] [profile]`: فعال‌سازی هسته‌ی **backhaul** (SMUX).
- `ratholectl backhaul node <name> on|off`: انتقال یک نود به backhaul یا برگرداندنش.
- `ratholectl backhaul status` / `show` / `off`.

### هسته‌ی backhaul (مالتی‌پلکس SMUX):
یک باینری Go جدا کنار rathole که چند connection کاربر را روی یک stream مالتی‌پلکس می‌کند — مناسب لینک‌های شلوغ یا پرافت که rathole در آن‌ها mux ندارد.

```bash
# سمت ایران — پورت داخلی است و از nginx/443 عبور می‌کند (تک‌دامنه حفظ می‌شود)
ratholectl backhaul on 3080 wsmux balanced
ratholectl backhaul node <node_name> on
ratholectl backhaul show     # خط آماده‌ی نود را چاپ می‌کند
```

```bash
# سمت نود — دقیقاً همان خطی که «show» بالا داد
ratholenode backhaul on <domain> <token> wssmux balanced
```

نکات مهم:
- **transport دو طرف عمداً یکی نیست.** TLS فقط روی nginx خاتمه می‌یابد، پس سرور همیشه `ws`/`wsmux` (بدون TLS) و نود همیشه `wss`/`wssmux` می‌گیرد. هر دو سمت ورودی اشتباه را با پیام راهنما رد می‌کنند.
- **`tcpmux` پشتیبانی نمی‌شود** — TCP خام است و از nginx لایه ۷ عبور نمی‌کند.
- **profile باید دو طرف یکی باشد** (`balanced` / `lossy` / `aggressive`)، وگرنه پارامترهای SMUX نمی‌خوانند.
- وقتی نودی روی backhaul می‌رود، سرویسش از `server.toml` خارج می‌شود و روی نود `rathole-client` متوقف می‌شود — این عمدی است و از تداخل bind جلوگیری می‌کند.
- توکن مشترک secret است؛ فقط به نودهای backhaul بدهید.

---

## 🌐 ابزار مدیریت نود خارج (`ratholenode`)

### دستورات سرویس و حامل:
- `ratholenode status`: وضعیت اتصال نود به سرور ایران.
- `ratholenode set SERVER <domain_or_ip:port>`: تغییر سرور ایران مقصد.
- `ratholenode add-svc <name> <token> <inbound_port>`: افزودن یک سرویس جدید داخل تونل.
- `ratholenode rm-svc <name>`: حذف سرویس.

### حامل‌های تونل سمت نود:
- `ratholenode kcp on <ip:port> <key> [profile]` / `off` / `status`
- `ratholenode plain on <ip:port>` / `off` / `status`
- `ratholenode noise on <ip:port> <pubkey> [pattern]` / `off` / `status`
- `ratholenode backhaul on <domain> <token> [transport] [profile]` / `off` / `status`

### مدیریت Adaptive Failover:
- `ratholenode adaptive on`: فعال‌سازی سوئیچ خودکار حامل‌ها.
- `ratholenode adaptive off`: غیرفعال‌سازی سوئیچ خودکار.
- `ratholenode adaptive status`: مشاهده وضعیت حامل فعلی و قطعی‌ها.
- `ratholenode adaptive test`: اجرای تست شبکه و نمایش طبقه‌بندی خطاها.

---

## 🔄 آپدیت و کانال بتا

هر دو ابزار از گیت‌هاب آپدیت می‌گیرند و پیش از هر تغییر یک اسنپ‌شات کامل می‌سازند (با رول‌بک خودکار در صورت خطا).

```bash
ratholectl update           # کانال پایدار (stable)
ratholectl update beta      # آخرین نسخه‌ی آزمایشی (pre-release)
```

```bash
ratholenode update
ratholenode update beta
```

نکته: مسیر `releases/latest/download` در گیت‌هاب نسخه‌های pre-release را **نادیده می‌گیرد**، بنابراین `update beta` ابتدا آخرین تگ بتا را از فید `releases.atom` (از طریق میرورهای ghproxy، بدون نیاز به `jq`) پیدا می‌کند و سپس همان تگ را نصب می‌کند. برای برگشت به پایدار کافی است `update` بدون آرگومان بزنید.

⚠️ نسخه‌های بتا آزمایشی‌اند؛ روی سرور production فقط وقتی استفاده کنید که بخواهید قابلیت جدیدی را تست کنید.
