# راهنمای شروع سریع (Getting Started)

این راهنما روش‌های نصب و راه‌اندازی **RatholeEngine** را به همراه معماری لایه‌ای توضیح می‌دهد.

---

## 🚀 نصب یک‌خطی از گیت‌هاب (پیشنهادی)

شما می‌توانید کل پروژه (شامل سرور ایران، نود خارج، یا پنل هاب) را با یک دستور ساده نصب یا آپدیت کنید:

```bash
curl -fsSL https://raw.githubusercontent.com/loopy-iri/RatholeEngine/main/install.sh | sudo bash
```

این دستور آخرین نسخه انتشاریافته (`v1.5.0`) را به همراه فایل‌های باینری بهینه‌شده برای معماری سرور شما (x86_64 یا aarch64) دانلود و اجرا می‌کند.

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
