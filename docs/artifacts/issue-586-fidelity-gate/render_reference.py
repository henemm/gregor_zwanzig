#!/usr/bin/env python3
"""Rendert ScreenAlertConfig (bindende JSX, #586) zu einer Referenz-PNG.

Wegwerf-Skript (Memory feedback_shared_fidelity_tool): das geteilte
design_fidelity_diff.py bleibt unangetastet. Lokaler HTTP-Server, Babel
transpiliert die text/babel-Scripts, Playwright screenshottet den Container.
"""
import http.server
import socketserver
import sys
import threading
from functools import partial
from pathlib import Path

HERE = Path(__file__).resolve().parent
RENDER_DIR = HERE / "render"
OUT = HERE / "reference-alert-config.png"
PORT = 8097


def serve():
    handler = partial(http.server.SimpleHTTPRequestHandler, directory=str(RENDER_DIR))
    httpd = socketserver.TCPServer(("127.0.0.1", PORT), handler)
    httpd.serve_forever()


def main() -> int:
    t = threading.Thread(target=serve, daemon=True)
    t.start()
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        print("playwright fehlt", file=sys.stderr)
        return 2

    errors = []
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page(viewport={"width": 1440, "height": 1600}, device_scale_factor=2)
        page.on("console", lambda m: errors.append(m.text) if m.type == "error" else None)
        page.on("pageerror", lambda e: errors.append(str(e)))
        page.goto(f"http://127.0.0.1:{PORT}/render-alert.html")
        page.wait_for_function("window.__SOLL_READY__ === true", timeout=30000)
        page.wait_for_timeout(800)
        tab = page.query_selector("#soll-tab")
        if tab is None:
            print("kein #soll-tab", file=sys.stderr)
            return 1
        tab.screenshot(path=str(OUT))
        text = page.inner_text("#soll-tab")[:240]
        browser.close()

    if errors:
        print("CONSOLE/PAGE-ERRORS:", file=sys.stderr)
        for e in errors[:15]:
            print("  -", e, file=sys.stderr)
    print(f"Referenz-PNG: {OUT} ({OUT.stat().st_size if OUT.exists() else 0} bytes)")
    print(f"Render-Text (Auszug): {text!r}")
    return 0 if (OUT.exists() and not errors) else (1 if OUT.exists() else 2)


if __name__ == "__main__":
    sys.exit(main())
