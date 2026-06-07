#!/usr/bin/env python3
"""Erfasst den LIVE Alarme-Tab (Trip-Detail → ?tab=alerts) von Staging als PNG.

Wegwerf-Skript (#586). Login via validator.env, oeffnet die erste Trip-Karte
(JS-klickbar, kein <a href>), wechselt auf den Alerts-Tab und screenshottet das
Element [data-testid="alerts-tab"] bei 1440px Breite (apples-to-apples zum JSX).
"""
import os
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
OUT = HERE / "live-alert-config.png"
BASE = os.environ.get("GZ_VALIDATION_URL", "https://staging.gregor20.henemm.com")


def load_validator_env() -> None:
    env = Path(".claude/validator.env")
    if not env.exists():
        return
    for line in env.read_text().splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, v = line.split("=", 1)
            os.environ.setdefault(k.strip(), v.strip())


def main() -> int:
    load_validator_env()
    from playwright.sync_api import sync_playwright

    u = os.environ.get("GZ_VALIDATOR_USER", "")
    pw = os.environ.get("GZ_VALIDATOR_PASS", "")
    if not (u and pw):
        print("Validator-Creds fehlen", file=sys.stderr)
        return 2

    state_file = HERE / "staging_state.json"
    with sync_playwright() as p:
        b = p.chromium.launch()
        ctx_kwargs = {"viewport": {"width": 1440, "height": 1600}}
        if state_file.exists():
            ctx_kwargs["storage_state"] = str(state_file)
        ctx = b.new_context(**ctx_kwargs)
        pg = ctx.new_page()

        if not state_file.exists():
            # Nur EIN Login — Session danach speichern, um den Auth-Rate-Limit (429)
            # bei Folge-Laeufen NICHT erneut zu triggern.
            pg.goto(BASE + "/login")
            pg.wait_for_load_state("networkidle")
            pg.fill("input[name='username']", u)
            pg.fill("input[name='password']", pw)
            pg.click("button[type='submit']")
            try:
                pg.wait_for_url(lambda url: "/login" not in url, timeout=15000)
            except Exception:
                print(f"Login fehlgeschlagen (URL={pg.url}) — Rate-Limit aktiv", file=sys.stderr)
                b.close()
                return 2
            ctx.storage_state(path=str(state_file))
            print(f"Session gespeichert: {state_file}")

        pg.goto(BASE + "/trips")
        pg.wait_for_load_state("networkidle")
        pg.wait_for_timeout(1800)

        # Trip oeffnen: content-btn (force, da im Table-Layout teils 0-size/ueberlagert),
        # Fallback auf die ganze Trip-Karte bzw. den Namen.
        opened = False
        for sel in ["div[role='button'][title*='öffnen']",
                    "[data-testid='trip-card-content-btn']",
                    "[data-testid='trip-card']"]:
            loc = pg.locator(sel).first
            if loc.count() == 0:
                continue
            try:
                loc.scroll_into_view_if_needed(timeout=5000)
                loc.click(force=True, timeout=8000)
                pg.wait_for_url("**/trips/*", timeout=12000)
                opened = True
                print(f"Trip geoeffnet via {sel}")
                break
            except Exception as e:
                print(f"Klick {sel} fehlgeschlagen: {str(e)[:80]}", file=sys.stderr)
        if not opened:
            tids = pg.eval_on_selector_all(
                "[data-testid]", "els=>[...new Set(els.map(e=>e.getAttribute('data-testid')))]"
            )
            print("URL:", pg.url, "TESTIDS:", tids, file=sys.stderr)
            b.close()
            return 1
        pg.wait_for_load_state("networkidle")
        trip_path = pg.url.split("?")[0].replace(BASE, "")
        print(f"Trip: {trip_path}")

        pg.goto(BASE + trip_path + "?tab=alerts")
        pg.wait_for_load_state("networkidle")
        pg.wait_for_selector("[data-testid='alerts-tab']", timeout=15000)
        pg.wait_for_timeout(1500)

        el = pg.query_selector("[data-testid='alerts-tab']")
        el.screenshot(path=str(OUT))
        txt = pg.inner_text("[data-testid='alerts-tab']")[:240]
        b.close()

    print(f"Live-PNG: {OUT} ({OUT.stat().st_size if OUT.exists() else 0} bytes)")
    print(f"Live-Text (Auszug): {txt!r}")
    return 0 if OUT.exists() else 1


if __name__ == "__main__":
    sys.exit(main())
