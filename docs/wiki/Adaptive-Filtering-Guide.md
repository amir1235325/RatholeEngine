# راهنمای جامع Adaptive Filtering (سوئیچ خودکار)

ویژگی **Adaptive Filtering** (از v1.5.0) به نودهای خارج اجازه می‌دهد بدون دخالت اپراتور، در صورت فیلتر یا اختلال در حامل فعلی تونل، به‌طور هوشمند به حامل‌های جایگزین سوئیچ کنند.

---

## منطق پروب‌های لایه‌ای

سرویس مانیتورینگ در بازه‌های زمانی مشخص یک WebSocket RFC 6455 به `WS_PATH` می‌فرستد و نتیجه را طبقه‌بندی می‌کند:

| طبقه‌بندی | علت | اکشن |
|-----------|-----|------|
| `healthy` | اتصال کامل و بدون مشکل | ماندن در حامل فعلی |
| `dns_failed` | خطای nameserver دامنه | پروب مجدد |
| `tcp_timeout` | مسدود شدن TCP/443 | آماده‌سازی سوئیچ به KCP |
| `tls_failed` | دستکاری TLS توسط DPI | سوئیچ به KCP |
| `ws_rejected` | رد شدن هدرهای WebSocket | سوئیچ به KCP |
| `ws_timeout` | اتصال برقرار شد ولی پاسخ WS نیامد | سوئیچ به KCP |

---

## پارامترها و hysteresis

```bash
ratholenode adaptive on [--interval N] [--failures N] [--recoveries N]
```

| پارامتر | پیش‌فرض | توضیح |
|---------|---------|-------|
| `--interval` | ۳۰ ثانیه | بازه‌ی بین هر پروب |
| `--failures` | ۳ | تعداد شکست متوالی برای سوئیچ |
| `--recoveries` | ۵ | تعداد موفقیت متوالی برای بازگشت به `ws` |

**Cooldown:** بعد از هر سوئیچ، حداقل ۳۰۰ ثانیه صبر می‌شود (`ADAPTIVE_COOLDOWN`) تا سوئیچ‌های پی‌درپی جلوگیری شود.

**اولویت حامل‌ها:** `ws` → `kcp`. حامل `plain` فقط با متغیر `ALLOW_INSECURE=1` در `node.env` در چرخش قرار می‌گیرد — هرگز بدون اجازه صریح انتخاب نمی‌شود.

**Rollback خودکار:** اگر probe بعد از سوئیچ هم fail باشد، config قبلی بازیابی می‌شود.

---

## دستورات مدیریت

```bash
# روشن کردن
sudo ratholenode adaptive on --interval 30 --failures 3 --recoveries 5

# وضعیت جاری (حامل فعال + نتیجه آخرین probe)
sudo ratholenode adaptive status

# اجرای یک پروب آنی
sudo ratholenode adaptive test
sudo ratholenode adaptive test --json

# خاموش کردن
sudo ratholenode adaptive off
```

---

## امنیت و حریم خصوصی

فایل state در `/etc/rathole/adaptive-state.json` (mode 0600) فقط این فیلدها را نگه می‌دارد:

```
time, current, classification, latency_ms, consecutive_failures
```

هیچ‌کدام از `token`، `WS_PATH` یا کلیدهای رمزنگاری در این فایل ثبت یا از طریق API هاب فاش نمی‌شوند.

---

## پیش‌نیاز

برای کارکرد adaptive، حداقل دو حامل باید آماده باشند:

```bash
# سمت ایران — KCP را فعال کن:
sudo ratholectl kcp on

# سمت نود — KCP را اضافه کن:
sudo ratholenode kcp on <ip:port> <key> [profile]

# سپس adaptive را روشن کن:
sudo ratholenode adaptive on
```

پروفایل KCP دو طرف باید یکی باشد (`balanced` / `lossy` / `aggressive`).
