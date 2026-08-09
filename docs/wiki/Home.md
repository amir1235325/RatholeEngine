# RatholeEngine Wiki

خوش آمدید به مستندات جامع و ویکی پروژه **RatholeEngine**.

این سیستم یک راهکار **معکوس‌تونل (Reverse Tunnel)** پیشرفته و چندموقعیتی بر پایه‌ی **rathole + Nginx** برای عبور از فیلترینگ شدید است.

---

## 📚 فهرست صفحات ویکی (Wiki Index)

1. 🚀 **[راهنمای شروع سریع (Getting Started)](Getting-Started)**
   - نصب خودکار یک‌خطی
   - گزینه‌های نصب (Panel / Node / Hub)
   - پیش‌نیازها و معماری عمومی

2. ⚡ **[راهنمای Adaptive Filtering (سوئیچ خودکار)](Adaptive-Filtering-Guide)**
   - منطق سوئیچینگ هوشمند بین WebSocket و KCP
   - آزمایش و عیب‌یابی لایه‌ای (Layered Probes)
   - تنظیم فواصل، حد آستانه (Threshold) و Cooldown
   - الزامات امنیتی و Sanitization

3. 📖 **[مرجع کامل دستورات CLI (CLI Reference)](CLI-Reference)**
   - دستورات سرور ایران (`ratholectl`)
   - دستورات نود خارج (`ratholenode`)
   - مدیریت مسیر مخفی کنترلی (`control-path`)
   - حامل‌ها: KCP، Plain، Noise، **Backhaul (SMUX)**، Direct-IP و Game/SNI
   - آپدیت و کانال بتا (`update beta`)

4. 🖥️ **[مدیریت مرکزی با Hub (Hub Management)](Hub-Management)**
   - نصب و کانفیگ پنل وب Hub (`hub.py`)
   - راهنمای REST API و امنیت اتصال SSH
   - آپدیت گروهی و مانیتورینگ لایو سرورها

5. 🛠️ **[عیب‌یابی، بک‌آپ و رول‌بک (Troubleshooting)](Troubleshooting)**
   - عیب‌یابی اتصالات و لاگ‌ها
   - سیستم بک‌آپ خودکار قبل از آپدیت
   - دستورات رول‌بک دکمه‌ای و دستی

6. 📋 **[راهنماهای عملی (Workflow Guides)](Workflow-Guides)**
   - راه‌اندازی دسترسی direct-IP
   - مهاجرت از WebSocket به Backhaul (SMUX)
   - اضافه کردن دامنه دوم
   - اتصال نود به چند سرور ایران (multi-upstream)

---

## 📜 لایسنس (License)

پروژه تحت لایسنس **[AGPL-3.0-or-later](https://github.com/loopy-iri/RatholeEngine/blob/main/LICENSE)** به‌صورت متن‌باز منتشر شده است.

نسخه‌های تا v1.7.0 تحت MIT منتشر شده بودند و همچنان تحت MIT در دسترس‌اند؛ از آن پس پروژه AGPL-3.0 است.
نکته‌ی عملی (بند ۱۳ AGPL): اگر RatholeEngine را تغییر دهید و دیگران از طریق شبکه با نسخه‌ی تغییریافته‌ی شما
کار کنند (مثلاً پنل وب `ratholehub` را برایشان اجرا کنید)، باید سورس نسخه‌ی خود را به آن‌ها ارائه دهید.
جزئیات در [NOTICE](https://github.com/loopy-iri/RatholeEngine/blob/main/NOTICE).
