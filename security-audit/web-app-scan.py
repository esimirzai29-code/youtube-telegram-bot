#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Web App Scan — اسکنر غیرتهاجمی وب‌اپلیکیشن (عمومی، نه مخصوص وردپرس)
--------------------------------------------------------------------
فقط کتابخانه استاندارد پایتون. فقط درخواست خواندنی (GET/OPTIONS/TRACE)
و خواندن هدر Location (بدون دنبال کردن ریدایرکت). هیچ فرمی ثبت نمی‌کند.

چک‌ها: گواهی TLS، هدرهای امنیتی، فلگ‌های کوکی، متدهای HTTP،
فایل‌های حساس رایج، robots/sitemap، تست Open Redirect (فقط خواندن هدر).

استفاده:
    python3 web-app-scan.py https://example.com
    python3 web-app-scan.py https://example.com --json
    python3 web-app-scan.py --selftest
"""
import http.client
import json
import re
import socket
import ssl
import sys
import urllib.parse
import urllib.request
from datetime import datetime

TIMEOUT = 12
UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Web-App-Scan/1.0"}
SEV_FA = {"critical": "🔴 بحرانی", "high": "🟠 بالا", "medium": "🟡 متوسط",
          "low": "🟢 کم", "info": "ℹ️ اطلاع", "good": "✅ خوب"}


def http_get(url, method="GET"):
    """خروجی: (status, text, headers_lower_dict, set_cookie_list)"""
    try:
        req = urllib.request.Request(url, headers=UA, method=method)
        with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
            raw = r.read(300_000)
            hdrs = {k.lower(): v for k, v in r.headers.items()}
            cookies = r.headers.get_all("Set-Cookie") or []
            try:
                return r.status, raw.decode("utf-8", "ignore"), hdrs, cookies
            except Exception:
                return r.status, "", hdrs, cookies
    except urllib.error.HTTPError as e:
        try:
            hdrs = {k.lower(): v for k, v in e.headers.items()}
            cookies = e.headers.get_all("Set-Cookie") or []
        except Exception:
            hdrs, cookies = {}, []
        return e.code, "", hdrs, cookies
    except Exception:
        return 0, "", {}, []


def raw_request(host, port, use_https, method, path):
    """درخواست خام با http.client (برای TRACE و Location بدون ریدایرکت)"""
    try:
        conn = http.client.HTTPSConnection(host, port or 443, timeout=TIMEOUT) \
            if use_https else http.client.HTTPConnection(host, port or 80, timeout=TIMEOUT)
        conn.request(method, path, headers={"User-Agent": UA["User-Agent"], "Host": host})
        resp = conn.getresponse()
        data = (resp.status, resp.getheader("Location", "") or "",
                resp.getheader("Allow", "") or "")
        conn.close()
        return data
    except Exception:
        return 0, "", ""


def parse_cookie_flags(set_cookie):
    """'sid=abc; Secure; HttpOnly; SameSite=Lax' -> ('sid', {...})"""
    parts = [p.strip() for p in set_cookie.split(";")]
    name = parts[0].split("=")[0] if parts else "?"
    low = set_cookie.lower()
    m = re.search(r"samesite=([a-z]+)", low)
    return name, {"secure": "secure" in low,
                  "httponly": "httponly" in low,
                  "samesite": m.group(1) if m else None}


def is_external_redirect(location, site_host):
    """آیا Location به هاست دیگری می‌رود؟"""
    if not location:
        return False
    if location.startswith(("http://", "https://", "//")):
        host = urllib.parse.urlsplit(location if "://" in location else "https:" + location).hostname
        return host and host.lower() != site_host.lower()
    return False


def sitemap_locs(xml):
    return re.findall(r"<loc>([^<]+)</loc>", xml)


class Report:
    def __init__(self):
        self.findings = []

    def add(self, sev, title, detail=""):
        self.findings.append({"severity": sev, "title": title, "detail": detail})


def scan(target):
    rep = Report()
    site = target.rstrip("/")
    u0 = urllib.parse.urlsplit(site)
    host, use_https = u0.hostname, u0.scheme != "http"
    port = u0.port or (443 if use_https else 80)
    print(f"\n🔍 اسکن وب‌اپلیکیشن: {site}\n" + "=" * 55)

    # ---- ۱. TLS ----
    print("\n--- ۱. گواهی TLS ---")
    if use_https:
        try:
            ctx = ssl.create_default_context()
            with socket.create_connection((host, 443), timeout=TIMEOUT) as sock:
                with ctx.wrap_socket(sock, server_hostname=host) as ssock:
                    cert = ssock.getpeercert()
                    ver = ssock.version()
            exp = datetime.strptime(cert["notAfter"], "%b %d %H:%M:%S %Y %Z")
            days = (exp - datetime.utcnow()).days
            print(f"  ℹ️ پروتکل: {ver} | انقضا: {exp.date()} ({days} روز)")
            rep.add("info", f"TLS {ver} — انقضای گواهی {days} روز دیگر", "")
            if days < 30:
                rep.add("high", "گواهی کمتر از ۳۰ روز اعتبار دارد", "تمدید فوری.")
            if ver in ("TLSv1", "TLSv1.1"):
                rep.add("high", f"پروتکل ناامن {ver} فعال است", "فقط TLS 1.2+ مجاز باشد.")
        except Exception as e:
            print(f"  ⚠️ بررسی TLS ممکن نشد ({type(e).__name__})")
    else:
        print("  🔴 سایت با HTTP است!")
        rep.add("critical", "اتصال بدون HTTPS", "فوراً HTTPS با ریدایرکت اجباری فعال شود.")

    # ---- ۲. هدرها ----
    print("\n--- ۲. هدرهای امنیتی ---")
    code, _, headers, _ = http_get(site + "/")
    if code == 0:
        print("  ⚠️ عدم اتصال (WAF/جیوبلاک؟) — از داخل ایران اجرا کن")
        rep.add("info", "اتصال برقرار نشد", "اسکنر را از داخل ایران یا روی هاست اجرا کن.")
    else:
        for h in ["strict-transport-security", "x-frame-options",
                  "x-content-type-options", "referrer-policy",
                  "content-security-policy", "permissions-policy"]:
            if h in headers:
                print(f"  ✅ {h}")
            else:
                print(f"  🟡 {h} یافت نشد")
                rep.add("low", f"هدر {h} فعال نیست", "در وب‌سرور یا کد فعال شود.")
        for leak in ["x-powered-by", "x-aspnet-version", "x-generator"]:
            if leak in headers:
                print(f"  🟡 {leak} لو رفته: {headers[leak]}")
                rep.add("low", f"هدر {leak} تکنولوژی را لو می‌دهد", "مخفی شود.")
        if "server" in headers:
            print(f"  ℹ️ Server: {headers['server']}")
            rep.add("info", f"هدر Server: {headers['server']}", "اگر نسخه دقیق دارد، مخفی شود.")

    # ---- ۳. کوکی‌ها ----
    print("\n--- ۳. فلگ‌های امنیتی کوکی ---")
    seen = set()
    for p in ["/", "/login"]:
        _, _, _, cookies = http_get(site + p)
        for c in cookies:
            name, flags = parse_cookie_flags(c)
            if name in seen:
                continue
            seen.add(name)
            problems = []
            if use_https and not flags["secure"]:
                problems.append("Secure ندارد")
            if not flags["httponly"]:
                problems.append("HttpOnly ندارد")
            if not flags["samesite"]:
                problems.append("SameSite ندارد")
            if problems:
                print(f"  🟡 کوکی {name}: {', '.join(problems)}")
                rep.add("low", f"کوکی {name}: {', '.join(problems)}",
                        "کوکی نشست باید Secure + HttpOnly + SameSite=Lax/Strict داشته باشد.")
            else:
                print(f"  ✅ کوکی {name}: فلگ‌ها کامل است")
    if not seen:
        print("  ℹ️ کوکی‌ای در پاسخ GET دیده نشد (طبیعی است؛ با لاگین واقعی بررسی شود)")

    # ---- ۴. متدها ----
    print("\n--- ۴. متدهای HTTP ---")
    for method in ["OPTIONS", "TRACE"]:
        st, _, allow = raw_request(host, port, use_https, method, "/")
        if method == "TRACE" and st == 200:
            print("  🔴 متد TRACE فعال است (ریسک XST)!")
            rep.add("medium", "متد TRACE فعال است", "در وب‌سرور غیرفعال شود (TraceEnable Off).")
        else:
            print(f"  ℹ️ {method}: HTTP {st}" + (f" | Allow: {allow}" if allow else ""))

    # ---- ۵. فایل‌های حساس ----
    print("\n--- ۵. فایل‌ها و مسیرهای حساس ---")
    paths = [".git/HEAD", ".env", ".env.bak", "server-status", "phpinfo.php",
             ".DS_Store", "backup.sql", "db.sql", "debug", "actuator/health",
             "api/docs", "swagger.json", "uploads/", ".well-known/security.txt"]
    for p in paths:
        code, _, _, _ = http_get(site + "/" + p)
        if p == ".well-known/security.txt":
            if code == 200:
                print("  ✅ security.txt وجود دارد")
                rep.add("good", "فایل security.txt منتشر شده", "")
            else:
                print(f"  🟡 security.txt نیست (HTTP {code}) — پیشنهاد می‌شود اضافه شود")
                rep.add("low", "فایل security.txt وجود ندارد",
                        "طبق RFC 9116 برای گزارش آسیب‌پذیری اضافه شود.")
        elif code == 200:
            print(f"  🔴 /{p} در دسترس است (HTTP 200)!")
            rep.add("high", f"/{p} در دسترس است!", "فوراً بررسی و بلاک شود.")
        elif code == 0:
            print(f"  ⚠️ /{p} عدم اتصال")
        else:
            print(f"  ✅ /{p} بسته است (HTTP {code})")

    # ---- ۶. robots و sitemap ----
    print("\n--- ۶. robots.txt و sitemap ---")
    code, robots, _, _ = http_get(site + "/robots.txt")
    if code == 200:
        dis = re.findall(r"(?i)^disallow:\s*(\S+)", robots, re.M)
        sm = re.findall(r"(?i)^sitemap:\s*(\S+)", robots, re.M)
        print(f"  ℹ️ {len(dis)} مسیر Disallow | sitemap: {', '.join(sm) if sm else 'ندارد'}")
        interesting = [d for d in dis if re.search(r"admin|config|backup|debug|test|dev|api|private", d, re.I)]
        if interesting:
            print(f"  🟡 مسیرهای حساس در robots: {', '.join(interesting[:8])}")
            rep.add("low", "robots.txt مسیرهای داخلی را لو می‌دهد",
                    "robots برای امنیت نیست؛ دسترسی واقعی در کد کنترل شود. مسیرها: " + ", ".join(interesting[:8]))
        for s in sm[:2]:
            if urllib.parse.urlsplit(s).hostname != host:
                continue
            _, xml, _, _ = http_get(s)
            locs = sitemap_locs(xml)
            print(f"  ℹ️ sitemap: {len(locs)} آدرس")
            rep.add("info", f"sitemap شامل {len(locs)} آدرس است",
                    "اگر کل کاربران/داده‌ها در آن است، آگاهانه باشد (SEO در برابر شمارش).")
    elif code == 0:
        print("  ⚠️ عدم اتصال")
    else:
        print(f"  ℹ️ robots.txt نیست (HTTP {code})")

    # ---- ۷. Open Redirect ----
    print("\n--- ۷. تست Open Redirect (فقط خواندن هدر) ---")
    evil = "https://evil.example.com/"
    probes = ["login?next=", "login?redirect=", "login?returnUrl=", "login?continue=",
              "logout?next=", "register?next="]
    found = False
    for pb in probes:
        st, loc, _ = raw_request(host, port, use_https, "GET", "/" + pb + urllib.parse.quote(evil, safe=""))
        if st in (301, 302, 303, 307, 308) and is_external_redirect(loc, host):
            print(f"  🔴 Open Redirect در /{pb}... → {loc[:60]}")
            rep.add("medium", f"احتمال Open Redirect در /{pb.split('?')[0]}",
                    "پارامتر مقصد باید اعتبارسنجی شود (فقط مسیر داخلی).")
            found = True
    if not found:
        print("  ✅ در پروب‌های استاندارد ریدایرکت خارجی دیده نشد")
    return rep


def print_report(rep, as_json=False):
    if as_json:
        print(json.dumps(rep.findings, ensure_ascii=False, indent=2))
        return 0
    print("\n" + "=" * 55 + "\n📊 جمع‌بندی یافته‌ها\n" + "=" * 55)
    order = {"critical": 0, "high": 1, "medium": 2, "low": 3, "info": 4, "good": 5}
    items = sorted(rep.findings, key=lambda f: order.get(f["severity"], 9))
    real = [f for f in items if f["severity"] not in ("info", "good")]
    if not real:
        print("🟢 عالی! یافته امنیتی ثبت نشد.")
    for f in items:
        print(f"\n{SEV_FA.get(f['severity'], f['severity'])}  {f['title']}")
        if f["detail"]:
            print(f"      └─ {f['detail']}")
    n = lambda s: sum(1 for f in items if f["severity"] == s)
    print(f"\n🔴 {n('critical')} بحرانی | 🟠 {n('high')} بالا | 🟡 {n('medium')} متوسط | 🟢 {n('low')} کم")
    if n("critical") or n("high"):
        return 2
    if n("medium") or n("low"):
        return 1
    return 0


def selftest():
    assert parse_cookie_flags("sid=abc; Secure; HttpOnly; SameSite=Lax") == \
        ("sid", {"secure": True, "httponly": True, "samesite": "lax"})
    assert parse_cookie_flags("x=1")[1] == {"secure": False, "httponly": False, "samesite": None}
    assert is_external_redirect("https://evil.example.com/a", "nlink.info")
    assert not is_external_redirect("/dashboard", "nlink.info")
    assert not is_external_redirect("https://nlink.info/x", "nlink.info")
    assert not is_external_redirect("", "nlink.info")
    assert sitemap_locs("<loc>https://a/b</loc><loc>https://a/c</loc>") == ["https://a/b", "https://a/c"]
    print("✅ selftest passed")


if __name__ == "__main__":
    args = sys.argv[1:]
    if "--selftest" in args:
        selftest()
        sys.exit(0)
    if not args:
        print(__doc__)
        sys.exit(1)
    target = args[0] if args[0].startswith("http") else "https://" + args[0]
    sys.exit(print_report(scan(target), as_json="--json" in args))
