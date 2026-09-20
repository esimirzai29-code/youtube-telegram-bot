#!/usr/bin/env bash
# ============================================================
# WP Security Check — اسکن امنیتی غیرتهاجمی وردپرس
# فقط درخواست‌های خواندنی (GET) می‌زند — امن برای اجرا روی سایت خودت
#
# استفاده:
#   chmod +x wp-security-check.sh
#   ./wp-security-check.sh https://example.com
# ============================================================
set -u

SITE="${1:-}"
if [[ -z "$SITE" ]]; then
  echo "Usage: $0 https://your-site.com"
  exit 1
fi
SITE="${SITE%/}"
CURL="curl -sk --max-time 15 -A Mozilla/5.0"

PASS=0; WARN=0; FAIL=0
ok()   { echo "  ✅ PASS  $1"; PASS=$((PASS+1)); }
warn() { echo "  ⚠️  WARN  $1"; WARN=$((WARN+1)); }
fail() { echo "  ❌ FAIL  $1"; FAIL=$((FAIL+1)); }
info() { echo "  ℹ️  $1"; }

echo "=================================================="
echo "🔍 بررسی امنیتی: $SITE"
echo "📅 $(date '+%Y-%m-%d %H:%M')"
echo "=================================================="

# ---------- ۱. نقاط رایج نشت اطلاعات ----------
echo ""
echo "--- ۱. نقاط رایج نشت اطلاعات ---"

# باید بسته باشند (403/404/301 به صفحه امن)
for path in "xmlrpc.php" "wp-json/wp/v2/users" "?author=1" "readme.html" "license.txt" "wp-config.php.bak" "wp-config.php~" ".git/HEAD" "wp-content/debug.log"; do
  code=$($CURL -o /dev/null -w "%{http_code}" "$SITE/$path" 2>/dev/null || echo "000")
  case "$path" in
    xmlrpc.php|wp-json/wp/v2/users|"?author=1")
      if [[ "$code" == "403" || "$code" == "404" ]]; then ok "/$path بلاک است (HTTP $code)"
      else warn "/$path پاسخ می‌دهد (HTTP $code) — بهتر است بلاک شود"; fi
      ;;
    *)
      if [[ "$code" == "200" ]]; then fail "/$path در دسترس است! (HTTP 200) — حذف/بلاک شود"
      elif [[ "$code" == "000" ]]; then warn "/$path — عدم اتصال (احتمالاً WAF/جیوبلاک)"
      else ok "/$path در دسترس نیست (HTTP $code)"; fi
      ;;
  esac
done

# ---------- ۲. هدرهای امنیتی ----------
echo ""
echo "--- ۲. هدرهای امنیتی ---"
HEADERS=$($CURL -sI "$SITE/" 2>/dev/null || true)
if [[ -z "$HEADERS" ]]; then
  warn "دریافت هدر ممکن نشد (احتمالاً WAF اتصال را قطع کرد)"
else
  for h in "strict-transport-security" "x-frame-options" "x-content-type-options" "referrer-policy" "content-security-policy" "permissions-policy"; do
    if echo "$HEADERS" | grep -qi "$h"; then ok "هدر $h فعال است"
    else warn "هدر $h یافت نشد"; fi
  done
  if echo "$HEADERS" | grep -qi "^server:"; then
    info "Server: $(echo "$HEADERS" | grep -i '^server:' | tr -d '\r')"
  fi
  if echo "$HEADERS" | grep -qi "x-powered-by:"; then
    warn "هدر X-Powered-By لو رفته: $(echo "$HEADERS" | grep -i 'x-powered-by:' | tr -d '\r')"
  else ok "هدر X-Powered-By مخفی است"; fi
fi

# ---------- ۳. گواهی SSL ----------
echo ""
echo "--- ۳. گواهی SSL ---"
HOST=$(echo "$SITE" | sed -E 's#https?://##' | cut -d/ -f1)
CERT_END=$(echo | openssl s_client -connect "$HOST:443" -servername "$HOST" 2>/dev/null | openssl x509 -noout -enddate 2>/dev/null | cut -d= -f2 || true)
if [[ -n "$CERT_END" ]]; then
  info "انقضای گواهی: $CERT_END"
  if openssl s_client -connect "$HOST:443" -servername "$HOST" 2>/dev/null | openssl x509 -noout -checkend 2592000 >/dev/null 2>&1; then
    ok "گواهی بیش از ۳۰ روز اعتبار دارد"
  else fail "گواهی کمتر از ۳۰ روز دیگر منقضی می‌شود!"; fi
else
  warn "بررسی گواهی ممکن نشد (اتصال TLS ناموفق — احتمالاً WAF/جیوبلاک)"
fi

# ---------- ۴. نسخه وردپرس از generator ----------
echo ""
echo "--- ۴. نشت نسخه ---"
GEN=$($CURL -s "$SITE/" 2>/dev/null | grep -oiE '<meta name="generator"[^>]*>' | head -n 3 || true)
if [[ -n "$GEN" ]]; then warn "تگ generator لو رفته: $GEN"
else ok "تگ generator در صفحه اصلی دیده نشد"; fi

# ---------- جمع‌بندی ----------
echo ""
echo "=================================================="
echo "📊 جمع‌بندی: ✅ $PASS موفق | ⚠️ $WARN هشدار | ❌ $FAIL خطر"
echo "=================================================="
if [[ "$FAIL" -gt 0 ]]; then
  echo "🔴 موارد FAIL را در اولویت برطرف کن (راهنما در فایل گزارش)."
  exit 2
elif [[ "$WARN" -gt 0 ]]; then
  echo "🟡 وضعیت کلی خوب است؛ هشدارها را در فرصت مناسب بررسی کن."
  exit 1
else
  echo "🟢 عالی! همه بررسی‌ها سبز است."
  exit 0
fi
