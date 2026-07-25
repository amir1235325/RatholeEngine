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

---

## 🌐 ابزار مدیریت نود خارج (`ratholenode`)

### دستورات سرویس و حامل:
- `ratholenode status`: وضعیت اتصال نود به سرور ایران.
- `ratholenode set SERVER <domain_or_ip:port>`: تغییر سرور ایران مقصد.
- `ratholenode add-svc <name> <token> <inbound_port>`: افزودن یک سرویس جدید داخل تونل.
- `ratholenode rm-svc <name>`: حذف سرویس.

### مدیریت Adaptive Failover:
- `ratholenode adaptive on`: فعال‌سازی سوئیچ خودکار حامل‌ها.
- `ratholenode adaptive off`: غیرفعال‌سازی سوئیچ خودکار.
- `ratholenode adaptive status`: مشاهده وضعیت حامل فعلی و قطعی‌ها.
- `ratholenode adaptive test`: اجرای تست شبکه و نمایش طبقه‌بندی خطاها.
