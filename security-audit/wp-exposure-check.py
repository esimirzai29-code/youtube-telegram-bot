#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
WP Exposure Check — بررسی «پیش‌نیازهای نفوذ» وردپرس (غیرتهاجمی)
----------------------------------------------------------------
این اسکریپت اکسپلویت اجرا نمی‌کند و چیزی را تغییر نمی‌دهد.
فقط با درخواست‌های خواندنی (GET) بررسی می‌کند که آیا پیش‌نیازهای
سوءاستفاده از باگ‌های شناخته‌شده روی سایت وجود دارد یا نه:
  ۱. ثبت‌نام کاربر باز است؟ (پیش‌نیاز باگ‌های نیازمند حساب کاربری)
  ۲. فرم با فیلد آپلود فایل منتشر شده؟ (همه صفحات سایت‌مپ! پیش‌نیاز CVE-2026-32475 پرو)
  ۳. نام کاربری از ?author=1 لو می‌رود؟ (با دنبال‌نکردن ریدایرکت)
  ۴. لیست فایل‌های uploads دیده می‌شود؟
  ۵. نسخه‌های کلیدی + حکم نهایی هر CVE

استفاده:
    python3 wp-exposure-check.py https://your-site.com
    python3 wp-exposure-check.py --selftest
"""
import http.client
import re
import sys
import urllib.parse
import urllib.request

TIMEOUT = 12
UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) WP-Exposure-Check/1.1"}
PAGE_CAP = 30


def http_get(url):
    try:
        req = urllib.request.Request(url, headers=UA)
        with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
            return r.status, r.read(300_000).decode("utf-8", "ignore"), dict(r.headers.items())
    except urllib.error.HTTPError as e:
        return e.code, "", {}
    except Exception:
        return 0, "", {}


def get_no_redirect(url):
    """یک GET بدون دنبال کردن ریدایرکت؛ خروجی: (status, location_header)"""
    u = urllib.parse.urlsplit(url if "://" in url else "https://" + url)
    host = u.hostname
    path = u.path or "/"
    if u.query:
        path += "?" + u.query
    try:
        conn = http.client.HTTPSConnection(host, u.port or 443, timeout=TIMEOUT) \
            if u.scheme != "http" else http.client.HTTPConnection(host, u.port or 80, timeout=TIMEOUT)
        conn.request("GET", path, headers={"User-Agent": UA["User-Agent"], "Host": host})
        resp = conn.getresponse()
        loc = resp.getheader("Location", "")
        status = resp.status
        conn.close()
        return status, loc
    except Exception:
        return 0, ""


def has_register_form(html):
    """آیا صفحه فرم ثبت‌نام دارد؟"""
    low = html.lower()
    return ('name="user_login"' in low or 'id="user_login"' in low) and \
           ("register" in low or "ثبت" in html or "عضویت" in html)


def has_file_upload(html):
    """آیا صفحه فرم با فیلد آپلود فایل دارد؟"""
    return bool(re.search(r'<input[^>]*type=["\']file["\']', html, re.I))


def stable_tag(readme_text):
    m = re.search(r"^Stable tag:\s*([^\s]+)", readme_text, re.M | re.I)
    return m.group(1).strip() if m else None


def ver_tuple(ver, n=4):
    nums = re.findall(r"\d+", ver or "")
    return tuple(map(int, nums[:n])) if nums else None


def sitemap_urls(site, cap=PAGE_CAP):
    """استخراج آدرس صفحات از سایت‌مپ (فقط همین هاست، حداکثر cap آدرس)"""
    urls = []
    host = urllib.parse.urlsplit(site).hostname
    _, idx, _ = http_get(site + "/sitemap_index.xml")
    smaps = re.findall(r"<loc>([^<]+)</loc>", idx)
    if not smaps:
        smaps = [site + "/page-sitemap.xml", site + "/post-sitemap.xml",
                 site + "/product-sitemap.xml"]
    for sm in smaps:
        if urllib.parse.urlsplit(sm).hostname != host:
            continue
        _, xml, _ = http_get(sm)
        for u in re.findall(r"<loc>([^<]+)</loc>", xml):
            if urllib.parse.urlsplit(u).hostname == host and u not in urls:
                urls.append(u)
            if len(urls) >= cap:
                return urls
    return urls


def check(target):
    site = target.rstrip("/")
    print(f"\n🎯 بررسی سطح حمله: {site}\n" + "=" * 55)
    results = {}

    # ---- ۱. ثبت‌نام ----
    print("\n--- ۱. آیا ثبت‌نام کاربر باز است؟ ---")
    reg_open, reg_where = False, []
    code, html, _ = http_get(site + "/wp-login.php?action=register")
    if code == 200 and has_register_form(html):
        reg_open, reg_where = True, ["/wp-login.php?action=register"]
        print("  🔴 ثبت‌نام وردپرس باز است!")
    elif code == 0:
        print("  ⚠️ عدم اتصال (WAF؟)")
    else:
        print(f"  ✅ ثبت‌نام وردپرس بسته است (HTTP {code})")
    code2, html2, _ = http_get(site + "/my-account/")
    if code2 == 200 and ("woocommerce-form-register" in html2 or 'name="register"' in html2.lower()):
        reg_open = True
        reg_where.append("/my-account/ (ثبت‌نام مشتری ووکامرس)")
        print("  🟡 ثبت‌نام مشتری ووکامرس باز است (نقش customer)")
    results["registration_open"] = reg_open
    results["registration_where"] = reg_where

    # ---- ۲. فرم آپلود (همه صفحات سایت‌مپ) ----
    print("\n--- ۲. آیا فرم با فیلد آپلود فایل منتشر شده؟ ---")
    pages = [site + p for p in ["/", "/shop/", "/contact-us/", "/contact/", "/about-us/"]]
    sm_urls = sitemap_urls(site)
    print(f"  ℹ️ {len(sm_urls)} آدرس از سایت‌مپ پیدا شد؛ در حال بررسی...")
    for u in sm_urls:
        if u not in pages:
            pages.append(u)
    upload_pages = []
    for page in pages[:PAGE_CAP + 5]:
        code, html, _ = http_get(page)
        if code == 200 and has_file_upload(html):
            short = page.replace(site, "") or "/"
            upload_pages.append(short)
            print(f"  🔴 فیلد آپلود فایل در: {short}")
    if not upload_pages:
        print(f"  ✅ در {min(len(pages), PAGE_CAP + 5)} صفحه بررسی‌شده فیلد آپلود فایل پیدا نشد")
    results["upload_forms"] = upload_pages

    # ---- ۳. نشت نام کاربری ----
    print("\n--- ۳. آیا ?author=1 نام کاربری لو می‌دهد؟ ---")
    status, loc = get_no_redirect(site + "/?author=1")
    leaked = ""
    if status in (301, 302, 307, 308) and "/author/" in loc:
        leaked = urllib.parse.unquote(loc.split("/author/")[-1].split("/")[0].split("?")[0])
        print(f"  🔴 نام کاربری لو رفت: {leaked}")
    elif status == 200:
        print("  🟡 پاسخ 200 بدون ریدایرکت (احتمالاً صفحه نویسنده مستقیم باز است)")
        leaked = "؟ (صفحه 200 می‌دهد)"
    elif status in (401, 403, 404):
        print(f"  ✅ بلاک است (HTTP {status})")
    else:
        print(f"  ⚠️ پاسخ غیرمنتظره (HTTP {status})")
    results["author_leak"] = leaked

    # ---- ۴. لیستینگ uploads ----
    print("\n--- ۴. لیست فایل‌های uploads دیده می‌شود؟ ---")
    code, html, _ = http_get(site + "/wp-content/uploads/")
    if code == 200 and ("Index of" in html or "Directory listing for" in html):
        print("  🟡 لیست فایل‌ها قابل مشاهده است!")
        results["uploads_listing"] = True
    elif code == 0:
        print("  ⚠️ عدم اتصال (WAF؟)")
        results["uploads_listing"] = None
    else:
        print(f"  ✅ لیستینگ بسته است (HTTP {code})")
        results["uploads_listing"] = False

    # ---- ۵. نسخه‌های کلیدی ----
    print("\n--- ۵. نسخه‌های کلیدی ---")
    versions = {}
    for slug in ["elementor", "elementor-pro", "seo-by-rank-math", "woocommerce"]:
        code, txt, _ = http_get(f"{site}/wp-content/plugins/{slug}/readme.txt")
        ver = stable_tag(txt) if code == 200 else None
        versions[slug] = ver
        print(f"  📦 {slug}: {ver if ver else 'نامشخص (HTTP ' + str(code) + ')'}")

    # ---- حکم نهایی ----
    print("\n" + "=" * 55)
    print("⚖️ حکم نهایی: آیا نفوذ از بیرون ممکن است؟")
    print("=" * 55)
    verdicts = []

    # المنتور رایگان
    evt = ver_tuple(versions.get("elementor"), 3)
    if evt and evt >= (4, 0, 5):
        verdicts.append(("🟢", "باگ‌های المنتور رایگان: نسخه امن است."))
    elif reg_open:
        verdicts.append(("🟠", "باگ‌های المنتور: ثبت‌نام باز است! اگر نقش پیش‌فرض ویرایشگر (یا بالاتر) باشد، مهاجم می‌تواند حساب بگیرد و از XSSها استفاده کند → در تنظیمات → عمومی، نقش پیش‌فرض را چک کن (باید مشترک/customer باشد)."))
    else:
        verdicts.append(("🟢", "باگ‌های المنتور رایگان: نیاز به حساب ویرایشگر دارند و ثبت‌نام بسته است → از بیرون قابل نفوذ نیست."))

    # المنتور پرو
    if upload_pages:
        verdicts.append(("🔴", f"نقص آپلود پرو (‏CVSS 9.8‏): فیلد آپلود در {len(upload_pages)} صفحه منتشر شده ({', '.join(upload_pages)}). اگر نسخه پرو زیر 4.2.2 است → ریسک نفوذ واقعی! نسخه پرو را در پیشخوان چک و آپدیت کن."))
    else:
        verdicts.append(("🟡", "نقص آپلود پرو (‏CVSS 9.8‏): در صفحات بررسی‌شده فیلد آپلود پیدا نشد → سطح حمله بسته به نظر می‌رسد، ولی چون نسخه پرو قدیمی است، همچنان آپدیت کن."))

    # رنک‌مث (دو سطحی و دقیق)
    rvt = ver_tuple(versions.get("seo-by-rank-math"))
    if rvt and rvt >= (1, 0, 277):
        verdicts.append(("🟢", "باگ‌های رنک‌مث: نسخه امن است (1.0.277+)."))
    elif rvt and rvt >= (1, 0, 271, 1):
        verdicts.append(("🟡", "رنک‌مث: از باگ سطح مشترک (‏CVE-2026-34892‏، تا 1.0.271) در امانی ✅ ولی CVE-2026-77786 (نیازمند نقش Editor) شاملت می‌شود → کاربر Editor ناآشنا نداشته باش و به 1.0.277 آپدیت کن."))
    elif rvt:
        if reg_open:
            verdicts.append(("🔴", "رنک‌مث زیر 1.0.271.1 + ثبت‌نام باز = باگ سطح مشترک (‏CVE-2026-34892‏، ‏CVSS 6.5‏) از بیرون قابل سوءاستفاده است! فوراً به 1.0.277+ آپدیت کن."))
        else:
            verdicts.append(("🟠", "رنک‌مث زیر 1.0.271.1 است ولی ثبت‌نام بسته است → ریسک کمتر، ولی فوراً به 1.0.277+ آپدیت کن."))
    else:
        verdicts.append(("🟡", "نسخه رنک‌مث مشخص نشد — دستی در پیشخوان چک کن (باید 1.0.277+ باشد)."))

    # نشت نام کاربری
    if leaked:
        verdicts.append(("🟠", f"نشت نام کاربری ({leaked}): ترکیب «نام کاربری ادمین لو رفته + صفحه ورود باز از ایران» = هدف Brute-force! → نام admin را عوض کن + 2FA + محدودسازی ورود + بستن ?author (یافته ۷ گزارش)."))
    else:
        verdicts.append(("🟢", "نشت نام کاربری: بسته است."))

    for icon, text in verdicts:
        print(f"\n{icon} {text}")

    print("\n" + "=" * 55)
    if any(v[0] == "🔴" for v in verdicts):
        print("🔴 نتیجه: حداقل یک مسیر نفوذ بالقوه باز است — اقدام فوری!")
        return 2
    if any(v[0] == "🟠" for v in verdicts):
        print("🟠 نتیجه: ریسک متوسط — موارد بالا را این هفته ببند.")
        return 1
    print("🟢 نتیجه: مسیر نفوذ مستقیمی از بیرون دیده نشد. آپدیت‌ها را برای اطمینان انجام بده.")
    return 0


def selftest():
    assert has_register_form('<form><input name="user_login">ثبت نام</form>')
    assert not has_register_form('<form><input name="log">ورود</form>')
    assert has_file_upload('<form><input type="file" name="f"></form>')
    assert has_file_upload("<INPUT TYPE='FILE'>")
    assert not has_file_upload('<form><input type="text"></form>')
    assert stable_tag("Stable tag: 1.0.272") == "1.0.272"
    assert ver_tuple("1.0.272") == (1, 0, 272)
    assert ver_tuple("1.0.272") >= (1, 0, 271, 1)
    assert ver_tuple("1.0.272") < (1, 0, 277)
    assert ver_tuple("3.30.0", 3) < (4, 0, 5)
    assert ver_tuple(None) is None
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
    sys.exit(check(target))
