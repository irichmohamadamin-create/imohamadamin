#!/usr/bin/env python3
"""
🚀 serve.py — راه‌اندازی سریع سرور محلی + تونل عمومی Cloudflare
استفاده:
    python3 serve.py                    # پوشه فعلی، پورت 3000
    python3 serve.py -p 8080            # پورت دلخواه
    python3 serve.py -d ~/mysite        # پوشه دلخواه
    python3 serve.py -d ~/mysite -p 5000
    python3 serve.py --no-tunnel        # فقط سرور، بدون تونل
    python3 serve.py --no-browser       # بدون باز کردن مرورگر
"""

import argparse
import http.server
import os
import re
import shutil
import socket
import socketserver
import subprocess
import sys
import threading
import time
import webbrowser
from pathlib import Path

# ---------- رنگ‌ها برای ترمینال ----------
class C:
    RESET = "\033[0m"
    BOLD = "\033[1m"
    GREEN = "\033[92m"
    CYAN = "\033[96m"
    YELLOW = "\033[93m"
    RED = "\033[91m"
    MAGENTA = "\033[95m"
    DIM = "\033[2m"


def log(msg, color=C.RESET, icon="•"):
    print(f"{color}{icon} {msg}{C.RESET}", flush=True)


def banner():
    print(f"""
{C.CYAN}{C.BOLD}╔══════════════════════════════════════════════╗
║   🚀  LOCAL SERVER + PUBLIC TUNNEL          ║
║   سرویس‌دهنده محلی + تونل عمومی              ║
╚══════════════════════════════════════════════╝{C.RESET}
""")


# ---------- چک کردن پورت ----------
def is_port_free(port):
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(1)
        return s.connect_ex(("127.0.0.1", port)) != 0


def find_free_port(start=3000, max_tries=50):
    for p in range(start, start + max_tries):
        if is_port_free(p):
            return p
    raise RuntimeError("هیچ پورت آزادی پیدا نشد!")


# ---------- سرور HTTP با لاگ ----------
class QuietHandler(http.server.SimpleHTTPRequestHandler):
    """هندلر HTTP که فقط درخواست‌های مهم رو نشون میده"""

    def log_message(self, fmt, *args):
        # درخواست‌های ۲۰۰ رو با رنگ سبز، بقیه رو زرد نشون بده
        msg = fmt % args
        if " 200 " in msg or " 304 " in msg:
            color = C.DIM
        elif " 404 " in msg:
            color = C.RED
        else:
            color = C.YELLOW
        print(f"{color}  → {msg}{C.RESET}", flush=True)

    def end_headers(self):
        # جلوگیری از کش شدن برای دیباگ راحت‌تر
        self.send_header("Cache-Control", "no-store, no-cache, must-revalidate")
        super().end_headers()


def run_server(port, directory):
    os.chdir(directory)
    handler = QuietHandler
    socketserver.TCPServer.allow_reuse_address = True
    httpd = socketserver.TCPServer(("0.0.0.0", port), handler)
    return httpd


# ---------- استخراج لینک از خروجی cloudflared ----------
TUNNEL_URL_RE = re.compile(r"https://[a-zA-Z0-9-]+\.trycloudflare\.com")


def run_tunnel(port, stop_event, url_holder):
    """اجرای cloudflared و استخراج لینک عمومی"""
    cloudflared = shutil.which("cloudflared")
    if not cloudflared:
        log("cloudflared پیدا نشد! نصبش کن:", C.RED, "✗")
        log("   macOS:   brew install cloudflared", C.DIM)
        log("   Linux:   https://developers.cloudflare.com/cloudflare-one/connections/connect-networks/downloads/", C.DIM)
        log("   Windows: winget install --id Cloudflare.cloudflared", C.DIM)
        return

    try:
        proc = subprocess.Popen(
            [cloudflared, "tunnel", "--url", f"http://localhost:{port}",
             "--no-autoupdate"],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
        )
    except Exception as e:
        log(f"خطا در اجرای cloudflared: {e}", C.RED, "✗")
        return

    # خواندن خروجی خط به خط
    for line in proc.stdout:
        if stop_event.is_set():
            break

        # پیدا کردن لینک عمومی
        m = TUNNEL_URL_RE.search(line)
        if m and not url_holder["url"]:
            url_holder["url"] = m.group(0)
            print()
            log("═" * 50, C.GREEN)
            log(f"🌐 لینک عمومی: {C.BOLD}{C.CYAN}{m.group(0)}{C.RESET}")
            log("═" * 50, C.GREEN)
            print()

        # چاپ خطوط مهم cloudflared (خطاها)
        if any(k in line.lower() for k in ["error", "failed", "unable"]):
            print(f"{C.RED}  [cloudflared] {line.strip()}{C.RESET}", flush=True)

    proc.terminate()
    try:
        proc.wait(timeout=3)
    except subprocess.TimeoutExpired:
        proc.kill()


# ---------- کلاس سرور در ترد جداگانه ----------
class ServerThread(threading.Thread):
    def __init__(self, httpd):
        super().__init__(daemon=True)
        self.httpd = httpd

    def run(self):
        self.httpd.serve_forever()

    def stop(self):
        self.httpd.shutdown()
        self.httpd.server_close()


# ---------- main ----------
def main():
    parser = argparse.ArgumentParser(
        description="🚀 راه‌اندازی سریع سرور محلی + تونل عمومی",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("-p", "--port", type=int, default=3000, help="پورت سرور (پیش‌فرض: 3000)")
    parser.add_argument("-d", "--dir", type=str, default=".", help="پوشه سایت (پیش‌فرض: پوشه فعلی)")
    parser.add_argument("--no-tunnel", action="store_true", help="بدون اجرای تونل")
    parser.add_argument("--no-browser", action="store_true", help="بدون باز کردن مرورگر")
    parser.add_argument("--auto-port", action="store_true", help="اگه پورت اشغال بود، پورت آزاد پیدا کن")
    args = parser.parse_args()

    banner()

    # بررسی پوشه
    directory = Path(args.dir).expanduser().resolve()
    if not directory.is_dir():
        log(f"پوشه پیدا نشد: {directory}", C.RED, "✗")
        sys.exit(1)

    # بررسی index.html
    if not (directory / "index.html").exists():
        log("هشدار: فایل index.html پیدا نشد! (بقیه فایل‌ها هم سرو می‌شن)", C.YELLOW, "⚠")

    # بررسی پورت
    port = args.port
    if not is_port_free(port):
        if args.auto_port:
            new_port = find_free_port(port)
            log(f"پورت {port} اشغاله، استفاده از پورت {new_port}", C.YELLOW, "⚠")
            port = new_port
        else:
            log(f"پورت {port} اشغاله! از -p برای انتخاب پورت دیگه استفاده کن یا --auto-port بذار", C.RED, "✗")
            sys.exit(1)

    # شروع سرور
    log(f"پوشه: {C.CYAN}{directory}{C.RESET}", C.GREEN, "📁")
    log(f"پورت: {C.CYAN}{port}{C.RESET}", C.GREEN, "🔌")

    try:
        httpd = run_server(port, str(directory))
    except Exception as e:
        log(f"خطا در راه‌اندازی سرور: {e}", C.RED, "✗")
        sys.exit(1)

    server_thread = ServerThread(httpd)
    server_thread.start()
    log(f"سرور محلی بالا اومد → {C.BOLD}http://localhost:{port}{C.RESET}", C.GREEN, "✓")

    # باز کردن مرورگر
    if not args.no_browser:
        threading.Timer(1.0, lambda: webbrowser.open(f"http://localhost:{port}")).start()

    # شروع تونل
    tunnel_proc = None
    url_holder = {"url": None}
    stop_event = threading.Event()

    if not args.no_tunnel:
        log("در حال راه‌اندازی تونل Cloudflare...", C.CYAN, "🌐")
        tunnel_thread = threading.Thread(
            target=run_tunnel,
            args=(port, stop_event, url_holder),
            daemon=True,
        )
        tunnel_thread.start()

    print()
    log("═" * 50, C.MAGENTA)
    log(f"  {C.BOLD}Ctrl+C{C.RESET} برای توقف", C.DIM)
    log("═" * 50, C.MAGENTA)
    print()

    # حلقه اصلی
    try:
        while True:
            time.sleep(0.5)
    except KeyboardInterrupt:
        print()
        log("در حال خاموش کردن...", C.YELLOW, "⏹")
        stop_event.set()
        server_thread.stop()
        log("خداحافظ! 👋", C.GREEN, "✓")
        sys.exit(0)


if __name__ == "__main__":
    main()