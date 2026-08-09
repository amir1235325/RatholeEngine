# راهنمای شروع سریع (Getting Started)

این راهنما روش‌های نصب و راه‌اندازی **RatholeEngine** را به همراه معماری لایه‌ای توضیح می‌دهد.

---

## 🚀 نصب یک‌خطی از گیت‌هاب (پیشنهادی)

شما می‌توانید کل پروژه (شامل سرور ایران، نود خارج، یا پنل هاب) را با یک دستور ساده نصب یا آپدیت کنید:

```bash
curl -fsSL https://raw.githubusercontent.com/loopy-iri/RatholeEngine/main/install.sh | sudo bash
```

این دستور آخرین نسخه‌ی انتشاریافته را به همراه فایل‌های باینری بهینه‌شده برای معماری سرور شما (x86_64 یا aarch64) دانلود و اجرا می‌کند.

---

## ⚙️ گزینه‌های نصب خودکار (Non-interactive Flags)

### ۱. نصب سرور ایران (Iran Panel):
```bash
curl -fsSL https://raw.githubusercontent.com/loopy-iri/RatholeEngine/main/install.sh | sudo bash -s -- \
  --panel \
  --domain mydomain.com \
  --fullchain /etc/letsencrypt/live/mydomain.com/fullchain.pem \
  --key /etc/letsencrypt/live/mydomain.com/privkey.pem
```

### ۲. نصب نود خارج (Foreign Node):
```bash
curl -fsSL https://raw.githubusercontent.com/loopy-iri/RatholeEngine/main/install.sh | sudo bash -s -- \
  --node \
  --server mydomain.com:443 \
  --name node-germany \
  --token <YOUR_32_HEX_TOKEN> \
  --inbound-port 10080
```

### ۳. نصب پنل وب مدیریت مرکزی (RatholeHub):
```bash
curl -fsSL https://raw.githubusercontent.com/loopy-iri/RatholeEngine/main/install.sh | sudo bash -s -- \
  --hub \
  --port 8088 \
  --user admin \
  --pass secret123
```

---

## 🔄 آپدیت یک‌خطی (Update)

برای ارتقا به آخرین نسخه (همراه با بک‌آپ خودکار و رول‌بک در صورت خطا):
```bash
curl -fsSL https://raw.githubusercontent.com/loopy-iri/RatholeEngine/main/install.sh | sudo bash -s -- --update
```

اگر از قبل نصب دارید، ساده‌تر است مستقیم از خود سرور بزنید:
```bash
ratholectl update
```

### 🧪 کانال بتا (نسخه‌های آزمایشی)

برای تست قابلیت‌های جدید پیش از انتشار پایدار:
```bash
ratholectl update beta
```

روی نود خارج:
```bash
ratholenode update beta
```

یا با نصب یک‌خطی:
```bash
curl -fsSL https://raw.githubusercontent.com/loopy-iri/RatholeEngine/main/install.sh | sudo RATHOLE_RELEASE=beta bash -s -- --update
```

برگشت به کانال پایدار فقط با زدن `ratholectl update` (بدون آرگومان) انجام می‌شود.

⚠️ نسخه‌ی بتا آزمایشی است. چون آپدیت پیش از هر تغییر اسنپ‌شات کامل می‌گیرد، در صورت مشکل با `ratholectl update` یا `update.sh --rollback` برمی‌گردید.

---

## 🔧 قدم‌های بعدی (Optional)

پس از نصب پایه، ویژگی‌های زیر را می‌توانید اضافه کنید:

### ۱. فعال‌سازی هاب مدیریتی
```bash
sudo ratholectl hub on 8088   # → https://<domain>/hub/
```
برای مدیریت چند سرور ایران و نود از یک پنل وب. جزئیات: **[Hub Management](Hub-Management)**.

### ۲. دسترسی مستقیم از طریق IP (بدون دامنه)
```bash
sudo ratholectl direct on --port 8081
```
برای کاربرانی که دامنه برایشان کار نمی‌کند — از طریق IP سرور با هدر استتارشده.

### ۳. Watchdog (راه‌اندازی مجدد خودکار)
```bash
sudo ratholenode watchdog on   # روی نود خارج
```
یک timer که تانل‌های گیرکرده را خودکار restart می‌کند.

### ۴. سوئیچ هوشمند حامل (Adaptive Failover)
```bash
sudo ratholenode adaptive on
```
نود خارج را روشن می‌کند تا در صورت فیلتر شدن WebSocket، خودکار به KCP سوئیچ کند. جزئیات: **[Adaptive Filtering](Adaptive-Filtering-Guide)**.

### ۵. اتصال به چند سرور ایران (چند-موقعیتی)
```bash
sudo ratholenode upstream add iran2 <server2:443>
sudo ratholenode upstream add-svc iran2 <name> <token> <inbound>
```

### ۶. مرجع کامل دستورات
برای همه دستورات از جمله domain management، ip-cert، noise، backhaul و بیشتر: **[CLI Reference](CLI-Reference)**.

برای عیب‌یابی: **[Troubleshooting](Troubleshooting)**.
