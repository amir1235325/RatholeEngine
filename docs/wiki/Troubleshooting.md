# عیب‌یابی، بک‌آپ و رول‌بک (Troubleshooting & Rollback)

این راهنما روش‌های حل مشکلات متداول اتصالات و استفاده از سیستم بک‌آپ خودکار را تشریح می‌کند.

---

## 🔍 بررسی لاگ‌ها و وضعیت سرویس‌ها

### ۱. بررسی لاگ‌های سرور ایران:
```bash
sudo journalctl -u rathole-server -n 50 --no-pager
sudo nginx -t
```

### ۲. بررسی لاگ‌های نود خارج:
```bash
sudo journalctl -u rathole-client -n 50 --no-pager
sudo ratholenode status
```

### ۳. عیب‌یابی هسته‌ی backhaul:
```bash
# سمت ایران
sudo ratholectl backhaul status
sudo journalctl -u rathole-backhaul-server -n 50 --no-pager
```

```bash
# سمت نود
sudo ratholenode backhaul status
sudo journalctl -u rathole-backhaul-client -n 50 --no-pager
```

خطاهای رایج:

| نشانه | علت | راه‌حل |
|---|---|---|
| سرویس بالا نمی‌آید، لاگ `Usage: ... -c` | نسخه‌ی قدیمی‌تر یونیت (بدون `-c`) | آپدیت به ≥ v1.6.0 |
| `control channel` مدام قطع/وصل می‌شود | دو کلاینت با یک توکن، یا profile ناهماهنگ | فقط یک نود به ازای هر توکن؛ profile دو طرف را یکی کنید |
| کلاینت وصل نمی‌شود | transport اشتباه | سرور `ws`/`wsmux` و نود `wss`/`wssmux` — عمداً متفاوت‌اند |
| نود روی backhaul است ولی `rathole-client` خطا می‌دهد | طبیعی است | سرویس عمداً متوقف می‌شود؛ backhaul جایگزین تونل است |
| پورت نود bind نمی‌شود | نود هنوز در `server.toml` مانده | `ratholectl backhaul node <name> on` را بزنید و `regen` کنید |

---

## 📦 سیستم بک‌آپ و رول‌بک خودکار (Automatic Rollback)

هر زمان که دستور آپدیت (`install.sh --update` یا `ratholectl update`) اجرا می‌شود:
1. یک اسنپ‌شات کامل از فایلهای اجرایی CLI، کانفیگ‌ها و سرویس‌های systemd در مسیر `/var/backups/rathole-manager/pre-update-<timestamp>/` ذخیره می‌شود.
2. آپدیت اعمال شده و هلت‌چک سرویس‌ها بررسی می‌شود.
3. در صورت شکست هلت‌چک یا عدم تایید `nginx -t`، کدهای قبلی به‌صورت خودکار رول‌بک می‌شوند.

### مدیریت دستی بک‌آپ‌ها:

```bash
# مشاهده لیست بک‌آپ‌های موجود
sudo update.sh --list-backups

# بازگردانی (Rollback) به آخرین اسنپ‌شات سالم
sudo update.sh --rollback

# بازگردانی به یک اسنپ‌شات مشخص
sudo update.sh --rollback 20260725-094447
```
