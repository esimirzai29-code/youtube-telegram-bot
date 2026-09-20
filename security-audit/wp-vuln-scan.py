#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
WP Vuln Scan — اسکنر امنیتی وردپرس (نسخه‌محور، غیرتهاجمی)
----------------------------------------------------------
فقط با کتابخانه استاندارد پایتون کار می‌کند (نیازی به pip نیست).
فقط درخواست خواندنی (GET) می‌زند — نسخه افزونه‌ها را از readme پیدا
کرده و با دیتابیس آسیب‌پذیری‌های شناخته‌شده (CVE) مقایسه می‌کند.

استفاده:
    python3 wp-vuln-scan.py https://your-site.com
    python3 wp-vuln-scan.py https://your-site.com --json
    python3 wp-vuln-scan.py --selftest   (تست داخلی منطق اسکنر)

کد خروج: 0=تمیز  1=هشدار  2=یافته بحرانی/بالا
"""
import json
import re
import socket
import ssl
import sys
import urllib.request
from datetime import datetime

TIMEOUT = 12
UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) WP-Vuln-Scan/1.0"}

# ---------------------------------------------------------------- دیتابیس CVE
# قالب: slug -> لیست (عنوان، نسخه اصلاح‌شده، شدت، توضیح)
CVE_DB = {
    "elementor": [
        ("Stored XSS از طریق Text Path Widget", "3.30.3", "medium", "نیاز به حساب Contributor+"),
        ("Arbitrary File Read از طریق Image Import", "3.30.3", "medium", "CVSS 4.9 — نیاز به حساب Admin"),
        ("Missing Authorization", "3.33.1", "medium", "CVSS 4.3"),
        ("Stored DOM-XSS از طریق Text Path", "3.33.4", "medium", "CVSS 5.9"),
        ("Stored XSS (شامل CVE-2026-32352)", "3.35.6", "medium", "نیاز به حساب Contributor+"),
        ("Stored XSS از طریق REST API (‏CVE-2026-6127‏)", "4.0.5", "medium", "CVSS 6.8"),
    ],
    "elementor-pro": [
        ("نقص آپلود فایل (‏CVE-2026-32475‏)", "4.2.2", "critical", "CVSS 9.8! — نسخه پرو از بیرون قابل تشخیص دقیق نیست؛ در پیشخوان چک شود"),
    ],
    "woocommerce": [
        ("Stored XSS ‏(CVE-2025-26762‏)", "9.7.1", "medium", "نسخه‌های تا 9.7.0"),
        ("اصلاحات امنیتی API/احراز هویت/سشن (منتشرشده در 11.1.1)", "11.1.1", "high", "جزئیات علنی نشده — عقب‌ماندگی امنیتی محسوب می‌شود"),
    ],
    "contact-form-7": [
        ("Reflected XSS", "5.9.2", "medium", "CVSS 6.1"),
        ("Unauthenticated Open Redirect", "5.9.5", "medium", "CVSS 4.3 — بدون نیاز به لاگین"),
        ("Order Replay", "6.0.6", "medium", "CVSS 5.3"),
    ],
    "seo-by-rank-math": [
        ("Broken Access Control ‏(CVE-2026-34892‏)", "1.0.271.1", "high", "کاربر Subscriber می‌تواند از آن سوءاستفاده کند"),
        ("تغییر تنظیمات هسته توسط Editor ‏(CVE-2026-77786‏)", "1.0.277", "medium", "CVSS 4.9"),
    ],
}
PLUGIN_SLUGS = list(CVE_DB.keys()) + ["yith-woocommerce-wishlist", "jetpack"]

SEV_FA = {"critical": "🔴 بحرانی", "high": "🟠 بالا", "medium": "🟡 متوسط", "low": "🟢 کم", "info": "ℹ️ اطلاع"}

# ---------------------------------------------------------------- ابزارها
def parse_ver(v):
    """تبدیل نسخه به تاپل قابل مقایسه: '1.0.271.1' -> (1,0,271,1)"""
    parts = []
    for chunk in re.split(r"[.\-+_]", str(v).strip()):
        if not chunk:
            continue
        m = re.match(r"(\d+)(.*)$", chunk)
        if m:
            parts.append(int(m.group(1)))
            if m.group(2):
                parts.append(-1)  # پسوند مثل beta پایین‌تر حساب می‌شود
        else:
            parts.append(-1)
    return tuple(parts) or (0,)


def ver_lt(a, b):
    try:
        return parse_ver(a) < parse_ver(b)
    except Exception:
        return False


def http_get(url):
    """GET ساده، خروجی: (status_code, text). خطای اتصال -> (0, '')"""
    try:
        req = urllib.request.Request(url, headers=UA)
        with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
            raw = r.read(200_000)
            try:
                return r.status, raw.decode("utf-8", "ignore")
            except Exception:
                return r.status, ""
    except urllib.error.HTTPError as e:
        return e.code, ""
    except Exception:
        return 0, ""


def stable_tag(readme_text):
    m = re.search(r"^Stable tag:\s*([^\s]+)", readme_text, re.M | re.I)
    return m.group(1).strip() if m else None


# ---------------------------------------------------------------- اسکن
class Report:
    def __init__(self):
        self.findings = []  # (severity, title, detail)

    def add(self, sev, title, detail=""):
        self.findings.append({"severity": sev, "title": title, "detail": detail})


def scan(target):
    rep = Report()
    site = target.rstrip("/")
    print(f"\n🔍 شروع اسکن: {site}\n" + "=" * 55)

    # ---- ۱. نسخه هسته وردپرس از فید ----
    print("\n--- ۱. نسخه هسته وردپرس ---")
    code, feed = http_get(site + "/feed/")
    m = re.search(r"wordpress\.org/\?v=([\d.]+)", feed)
    if m:
        print(f"  ℹ️ نسخه وردپرس لو رفته در فید: {m.group(1)}")
        rep.add("low", f"نشت نسخه وردپرس ({m.group(1)}) در /feed/",
                "پنهان‌سازی با افزونه یا کد امنیتی توصیه می‌شود (کم‌خطر).")
    elif code == 0:
        print("  ⚠️ عدم اتصال به /feed/ (احتمالاً WAF/جیوبلاک — از داخل ایران اجرا کن)")
        rep.add("info", "اتصال به سایت برقرار نشد", "اگر WAF جیوبلاک دارد، اسکنر را از داخل ایران یا روی هاست اجرا کن.")
    else:
        print("  ✅ نسخه وردپرس در فید دیده نشد")

    # ---- ۲. نسخه افزونه‌ها + تطبیق CVE ----
    print("\n--- ۲. نسخه افزونه‌ها و آسیب‌پذیری‌های شناخته‌شده ---")
    for slug in PLUGIN_SLUGS:
        code, txt = http_get(f"{site}/wp-content/plugins/{slug}/readme.txt")
        ver = stable_tag(txt) if code == 200 else None
        if code != 200:
            print(f"  ℹ️ {slug}: readme در دسترس نیست (HTTP {code}) — نسخه نامشخص")
            if slug in CVE_DB:
                rep.add("info", f"نسخه {slug} مشخص نشد",
                        "به‌صورت دستی در پیشخوان → افزونه‌ها نسخه را با آخرین نسخه مقایسه کن.")
            continue
        if not ver:
            print(f"  ℹ️ {slug}: نصب است ولی نسخه در readme نیست")
            if slug == "elementor-pro":
                era = re.search(r"Requires Elementor:\s*([^\s]+)", txt)
                era_txt = f" (Requires Elementor: {era.group(1)})" if era else ""
                print(f"     ⚠️ سرنخ قدمت:{era_txt} — اگر پرو زیر 4.2.2 باشد، CVE-2026-32475 (‏CVSS 9.8‏) شاملش می‌شود!")
                rep.add("high", "نسخه المنتور پرو از بیرون مشخص نیست ولی قدیمی به نظر می‌رسد" + era_txt,
                        "فوراً در پیشخوان → المنتور → اطلاعات سیستم نسخه را ببین؛ اگر زیر 4.2.2 است، CVE-2026-32475 (‏CVSS 9.8‏) شاملش می‌شود.")
            continue
        print(f"  📦 {slug}: نسخه {ver}")
        for title, fixed_in, sev, note in CVE_DB.get(slug, []):
            if ver_lt(ver, fixed_in):
                print(f"     {SEV_FA[sev]} {title} — اصلاح در {fixed_in}")
                rep.add(sev, f"{slug} {ver}: {title}", f"آپدیت به {fixed_in} یا بالاتر. {note}")
        if slug not in CVE_DB:
            rep.add("info", f"{slug} نسخه {ver} — در دیتابیس این اسکنر CVE ثبت نشده",
                    "به‌معنی امن بودن نیست؛ در پیشخوان آپدیت بودن را چک کن.")

    # ---- ۳. نقاط رایج نشت ----
    print("\n--- ۳. نقاط رایج نشت اطلاعات ---")
    checks = [
        ("xmlrpc.php", "blocked"), ("wp-json/wp/v2/users", "blocked"),
        ("?author=1", "blocked"), ("readme.html", "gone"),
        ("license.txt", "gone"), ("wp-content/debug.log", "gone"),
        ("wp-config.php.bak", "gone"),
    ]
    for path, expect in checks:
        code, _ = http_get(site + "/" + path)
        if expect == "blocked":
            if code in (401, 403, 404):
                print(f"  ✅ /{path} بلاک است (HTTP {code})")
            elif code == 0:
                print(f"  ⚠️ /{path} عدم اتصال (WAF؟)")
            else:
                print(f"  🟡 /{path} پاسخ می‌دهد (HTTP {code}) — بهتر است بلاک شود")
                rep.add("low", f"/{path} باز است (HTTP {code})", "بلاک کردن آن در WAF یا htaccess توصیه می‌شود.")
        else:
            if code == 200:
                print(f"  🟡 /{path} در دسترس است! — حذف/بلاک شود")
                rep.add("low", f"/{path} در دسترس است", "حذف فایل یا بلاک در htaccess.")
            elif code == 0:
                print(f"  ⚠️ /{path} عدم اتصال (WAF؟)")
            else:
                print(f"  ✅ /{path} در دسترس نیست (HTTP {code})")

    # ---- ۴. هدرهای امنیتی ----
    print("\n--- ۴. هدرهای امنیتی ---")
    try:
        req = urllib.request.Request(site + "/", headers=UA)
        with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
            headers = {k.lower(): v for k, v in r.headers.items()}
    except Exception:
        headers = {}
    if not headers:
        print("  ⚠️ دریافت هدر ممکن نشد (WAF؟)")
    else:
        for h in ["strict-transport-security", "x-frame-options",
                  "x-content-type-options", "referrer-policy",
                  "content-security-policy", "permissions-policy"]:
            if h in headers:
                print(f"  ✅ {h}")
            else:
                print(f"  🟡 {h} یافت نشد")
                rep.add("low", f"هدر امنیتی {h} فعال نیست", "در WAF یا htaccess فعال شود.")
        if "x-powered-by" in headers:
            print(f"  🟡 X-Powered-By لو رفته: {headers['x-powered-by']}")
            rep.add("low", "هدر X-Powered-By لو رفته", "مخفی‌سازی در تنظیمات PHP/سرور.")
        if "server" in headers:
            print(f"  ℹ️ Server: {headers['server']}")

    # ---- ۵. گواهی SSL ----
    print("\n--- ۵. گواهی SSL ---")
    host = re.sub(r"^https?://", "", site).split("/")[0]
    try:
        ctx = ssl.create_default_context()
        with socket.create_connection((host, 443), timeout=TIMEOUT) as sock:
            with ctx.wrap_socket(sock, server_hostname=host) as ssock:
                cert = ssock.getpeercert()
        exp = datetime.strptime(cert["notAfter"], "%b %d %H:%M:%S %Y %Z")
        days = (exp - datetime.utcnow()).days
        print(f"  ℹ️ انقضا: {exp.date()} (‏{days}‏ روز مانده)")
        if days < 30:
            rep.add("high", f"گواهی SSL کمتر از ۳۰ روز اعتبار دارد ({days} روز)", "تمدید فوری.")
            print("  🟠 کمتر از ۳۰ روز مانده!")
        else:
            print("  ✅ اعتبار کافی است")
    except Exception as e:
        print(f"  ⚠️ بررسی گواهی ممکن نشد ({type(e).__name__} — احتمالاً WAF/جیوبلاک)")

    return rep


def print_report(rep, as_json=False):
    if as_json:
        print(json.dumps(rep.findings, ensure_ascii=False, indent=2))
        return 0
    print("\n" + "=" * 55)
    print("📊 جمع‌بندی یافته‌ها")
    print("=" * 55)
    order = {"critical": 0, "high": 1, "medium": 2, "low": 3, "info": 4}
    items = sorted(rep.findings, key=lambda f: order.get(f["severity"], 9))
    if not items:
        print("🟢 عالی! یافته‌ای ثبت نشد.")
        return 0
    for f in items:
        print(f"\n{SEV_FA.get(f['severity'], f['severity'])}  {f['title']}")
        if f["detail"]:
            print(f"      └─ {f['detail']}")
    n_crit = sum(1 for f in items if f["severity"] == "critical")
    n_high = sum(1 for f in items if f["severity"] == "high")
    n_med = sum(1 for f in items if f["severity"] == "medium")
    n_low = sum(1 for f in items if f["severity"] == "low")
    print(f"\n🔴 {n_crit} بحرانی | 🟠 {n_high} بالا | 🟡 {n_med} متوسط | 🟢 {n_low} کم")
    if n_crit or n_high:
        return 2
    if n_med or n_low:
        return 1
    return 0


def selftest():
    """تست داخلی منطق مقایسه نسخه و پارس readme"""
    assert ver_lt("3.30.0", "3.30.3")
    assert not ver_lt("3.30.3", "3.30.3")
    assert not ver_lt("9.9.6", "9.7.1")
    assert ver_lt("9.9.6", "11.1.1")
    assert ver_lt("1.0.270", "1.0.271.1")
    assert ver_lt("1.0.271", "1.0.277")
    assert not ver_lt("4.2.4", "4.0.5")
    assert stable_tag("x\nStable tag: 3.30.0\n") == "3.30.0"
    assert stable_tag("no tag here") is None
    print("✅ selftest passed: version compare + readme parsing OK")


if __name__ == "__main__":
    args = sys.argv[1:]
    if "--selftest" in args:
        selftest()
        sys.exit(0)
    if not args or args[0].startswith("-"):
        print(__doc__)
        sys.exit(1)
    target = args[0]
    if not target.startswith("http"):
        target = "https://" + target
    report = scan(target)
    sys.exit(print_report(report, as_json="--json" in args))
