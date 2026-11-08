#!/usr/bin/env python3
"""
🚀 deploy.py — دیپلوی سریع سایت استاتیک روی اینترنت
استفاده:
    python3 deploy.py netlify -d ~/mysite      # Netlify Drop (سریع‌ترین)
    python3 deploy.py cloudflare -d ~/mysite   # Cloudflare Pages
    python3 deploy.py vercel -d ~/mysite       # Vercel
    python3 deploy.py github -d ~/mysite       # GitHub Pages
    python3 deploy.py --list                   # نمایش همه سرویس‌ها
"""

import argparse
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
import zipfile
from pathlib import Path
from urllib import request, error

# ---------- رنگ‌ها ----------
class C:
    RESET = "\033[0m"; BOLD = "\033[1m"; GREEN = "\033[92m"; CYAN = "\033[96m"
    YELLOW = "\033[93m"; RED = "\033[91m"; MAGENTA = "\033[95m"; DIM = "\033[2m"

def log(msg, color=C.RESET, icon="•"):
    print(f"{color}{icon} {msg}{C.RESET}", flush=True)

def banner():
    print(f"""
{C.CYAN}{C.BOLD}╔══════════════════════════════════════════════╗
║   🌍  DEPLOY SITE TO THE CLOUD               ║
║   دیپلوی سریع سایت روی اینترنت              ║
╚══════════════════════════════════════════════╝{C.RESET}
""")

# ---------- چک کردن دستورها ----------
def has(cmd):
    return shutil.which(cmd) is not None

def check_or_install(cmd, install_hint):
    if not has(cmd):
        log(f"'{cmd}' نصب نیست. نصب کن:", C.RED, "✗")
        log(f"   {install_hint}", C.DIM)
        return False
    return True

# ---------- چک کردن پوشه سایت ----------
def validate_site(directory):
    d = Path(directory).expanduser().resolve()
    if not d.is_dir():
        log(f"پوشه پیدا نشد: {d}", C.RED, "✗"); return None
    if not (d / "index.html").exists():
        log("index.html نیست! مطمئنی این پوشه سایتته؟", C.YELLOW, "⚠")
    return d

# ---------- استخراج URL از خروجی ----------
URL_RE = re.compile(r"https?://[a-zA-Z0-9\-._~:/?#\[\]@!$&'()*+,;=%]+")

def extract_urls(text):
    return URL_RE.findall(text)

# ============================================================
#                   دیپلوی روی Netlify Drop
# ============================================================
def deploy_netlify(directory):
    """
    Netlify Drag & Drop رو شبیه‌سازی می‌کنه.
    روش: فایل zip ساخته می‌شه، بعد به Netlify API آپلود می‌شه.
    """
    log("شروع دیپلوی Netlify...", C.CYAN, "🥇")

    # ساختن zip
    log("ساختن بسته‌ی سایت...", C.DIM, "📦")
    tmp_zip = Path(tempfile.gettempdir()) / f"deploy-{int(time.time())}.zip"
    try:
        with zipfile.ZipFile(tmp_zip, "w", zipfile.ZIP_DEFLATED) as z:
            for f in Path(directory).rglob("*"):
                if f.is_file():
                    z.write(f, f.relative_to(directory))
        size_kb = tmp_zip.stat().st_size / 1024
        log(f"بسته ساخته شد ({size_kb:.1f} KB)", C.GREEN, "✓")
    except Exception as e:
        log(f"خطا در ساخت zip: {e}", C.RED, "✗"); return

    # آپلود به Netlify (endpoint عمومی)
    log("آپلود به Netlify (ممکنه ۵-۱۵ ثانیه طول بکشه)...", C.DIM, "☁️")
    try:
        with open(tmp_zip, "rb") as f:
            data = f.read()
        req = request.Request(
            "https://api.netlify.com/api/v1/sites",
            data=data,
            method="POST",
            headers={"Content-Type": "application/zip"},
        )
        with request.urlopen(req, timeout=120) as resp:
            body = resp.read().decode("utf-8", errors="ignore")
        # پیدا کردن URL
        urls = [u for u in extract_urls(body) if "netlify" in u]
        if urls:
            public = sorted(set(urls))[0]
            print()
            log("═" * 60, C.GREEN)
            log(f"🌍 سایت منتشر شد: {C.BOLD}{C.CYAN}{public}{C.RESET}")
            log("═" * 60, C.GREEN)
            print()
        else:
            log("آپلود موفق، ولی نتونستم URL رو استخراج کنم.", C.YELLOW, "⚠")
            log("پاسخ سرور:", C.DIM)
            print(body[:500])
    except error.HTTPError as e:
        log(f"HTTP error: {e.code} {e.reason}", C.RED, "✗")
        log("راه جایگزین: Netlify Drop دستی →", C.DIM)
        log("  https://app.netlify.com/drop", C.CYAN)
    except Exception as e:
        log(f"خطا: {e}", C.RED, "✗")
        log("راه جایگزین: Netlify Drop دستی → https://app.netlify.com/drop", C.CYAN)
    finally:
        tmp_zip.unlink(missing_ok=True)

# ============================================================
#                  دیپلوی روی Cloudflare Pages
# ============================================================
def deploy_cloudflare(directory):
    log("شروع دیپلوی Cloudflare Pages...", C.CYAN, "🥈")

    # npx wrangler نصب شده؟
    if not check_or_install("npx", "pkg install nodejs-lts (Termux) / brew install node (macOS)"):
        return

    # اسم پروژه
    proj = Path(directory).resolve().name.lower().replace(" ", "-")
    proj = re.sub(r"[^a-z0-9-]", "", proj) or "mysite"
    log(f"نام پروژه: {C.BOLD}{proj}{C.RESET}", C.DIM, "📝")

    # اجرای wrangler
    log("اجرای wrangler (بار اول می‌پرسه login کن)...", C.DIM, "☁️")
    log("اگه پرسید: 'A browser window will open' → Yes رو بزن", C.DIM, "💡")
    cmd = ["npx", "-y", "wrangler", "pages", "deploy", str(directory),
           "--project-name", proj, "--commit-dirty=true"]
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
        out = proc.stdout + proc.stderr
        urls = [u for u in extract_urls(out) if "pages.dev" in u]
        if urls:
            print()
            log("═" * 60, C.GREEN)
            log(f"🌍 سایت منتشر شد: {C.BOLD}{C.CYAN}{urls[0]}{C.RESET}")
            log("═" * 60, C.GREEN)
            print()
        else:
            log("خروجی wrangler:", C.DIM)
            print(out[-800:])
    except subprocess.TimeoutExpired:
        log("وای! ۵ دقیقه شد و تموم نشد. احتمالاً منتظر login هستی.", C.YELLOW, "⏱")
        log("دستی اجرا کن: npx wrangler pages deploy . --project-name=mysite", C.CYAN)
    except Exception as e:
        log(f"خطا: {e}", C.RED, "✗")

# ============================================================
#                        دیپلوی Vercel
# ============================================================
def deploy_vercel(directory):
    log("شروع دیپلوی Vercel...", C.CYAN, "🥉")

    if not check_or_install("npx", "pkg install nodejs-lts (Termux) / brew install node (macOS)"):
        return

    log("اجرای vercel (بار اول login می‌خواد)...", C.DIM, "☁️")
    cmd = ["npx", "-y", "vercel", "--yes", "--cwd", str(directory), "--prod"]
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
        out = proc.stdout + proc.stderr
        urls = [u for u in extract_urls(out) if "vercel.app" in u]
        if urls:
            public = sorted(set(urls), key=len)[0]
            print()
            log("═" * 60, C.GREEN)
            log(f"🌍 سایت منتشر شد: {C.BOLD}{C.CYAN}{public}{C.RESET}")
            log("═" * 60, C.GREEN)
            print()
        else:
            log("خروجی vercel:", C.DIM)
            print(out[-800:])
            log("اگه login خواست، دستی اجرا کن: npx vercel --prod", C.CYAN)
    except subprocess.TimeoutExpired:
        log("وای! ۵ دقیقه شد. احتمالاً منتظر login هستی.", C.YELLOW, "⏱")
    except Exception as e:
        log(f"خطا: {e}", C.RED, "✗")

# ============================================================
#                    دیپلوی GitHub Pages
# ============================================================
def deploy_github(directory):
    log("شروع دیپلوی GitHub Pages...", C.CYAN, "🏅")

    if not check_or_install("git", "pkg install git (Termux) / brew install git (macOS)"):
        return
    if not check_or_install("gh", "pkg install gh (Termux) / brew install gh (macOS)"):
        log("   یا: https://cli.github.com/", C.DIM)
        return

    proj = Path(directory).resolve().name.lower().replace(" ", "-")
    proj = re.sub(r"[^a-z0-9-]", "", proj) or "mysite"

    # چک login
    auth = subprocess.run(["gh", "auth", "status"], capture_output=True, text=True)
    if auth.returncode != 0:
        log("اول login کن به GitHub:", C.YELLOW, "🔑")
        log("   gh auth login", C.CYAN)
        return

    # ساخت ریپو
    log(f"ساخت ریپو با اسم {proj}...", C.DIM, "📝")
    r = subprocess.run(
        ["gh", "repo", "create", proj, "--public", "--source", str(directory),
         "--remote", "origin", "--push"],
        capture_output=True, text=True, timeout=180,
    )
    if r.returncode != 0 and "already exists" not in (r.stderr or ""):
        log(f"خطا در ساخت ریپو: {r.stderr[:300]}", C.RED, "✗")
        return

    # فعال‌سازی Pages
    log("فعال‌سازی GitHub Pages...", C.DIM, "🌐")
    subprocess.run(
        ["gh", "api", f"repos/{{owner}}/{proj}/pages", "-X", "POST",
         "-f", "source[branch]=main", "-f", "source[path]=/"],
        capture_output=True, text=True,
    )

    # گرفتن owner
    owner_r = subprocess.run(["gh", "api", "user", "--jq", ".login"],
                             capture_output=True, text=True)
    owner = (owner_r.stdout or "").strip()
    if owner:
        print()
        log("═" * 60, C.GREEN)
        log(f"🌍 سایت منتشر شد: {C.BOLD}{C.CYAN}https://{owner}.github.io/{proj}/{C.RESET}")
        log("(اولین بار ۱-۲ دقیقه طول می‌کشه تا فعال بشه)", C.DIM)
        log("═" * 60, C.GREEN)
        print()

# ============================================================
#                          main
# ============================================================
SERVICES = {
    "netlify":    ("Netlify Drop (سریع‌ترین، بدون login)", deploy_netlify),
    "cloudflare": ("Cloudflare Pages (login لازم)", deploy_cloudflare),
    "vercel":     ("Vercel (login لازم)", deploy_vercel),
    "github":     ("GitHub Pages (login لازم + دامنه رایگان)", deploy_github),
}

def main():
    ap = argparse.ArgumentParser(description="🌍 دیپلوی سریع سایت روی اینترنت")
    ap.add_argument("service", nargs="?", choices=list(SERVICES.keys()),
                    help="سرویس دیپلوی (netlify / cloudflare / vercel / github)")
    ap.add_argument("-d", "--dir", default=".", help="پوشه سایت (پیش‌فرض: پوشه فعلی)")
    ap.add_argument("--list", action="store_true", help="نمایش همه سرویس‌ها")
    args = ap.parse_args()

    banner()

    if args.list or not args.service:
        log("سرویس‌های موجود:", C.BOLD)
        for name, (desc, _) in SERVICES.items():
            print(f"  {C.GREEN}{name:<12}{C.RESET} {desc}")
        print()
        log("مثال:", C.DIM)
        print(f"  {C.CYAN}python3 deploy.py netlify -d ~/mysite{C.RESET}")
        print(f"  {C.CYAN}python3 deploy.py vercel -d ~/mysite{C.RESET}")
        print()
        return

    directory = validate_site(args.dir)
    if not directory:
        sys.exit(1)

    log(f"پوشه: {C.BOLD}{directory}{C.RESET}", C.GREEN, "📁")
    t0 = time.time()
    SERVICES[args.service][1](str(directory))
    elapsed = time.time() - t0
    log(f"⏱ زمان: {elapsed:.1f} ثانیه", C.DIM)

if __name__ == "__main__":
    main()