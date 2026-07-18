"""
TDD RED — Issue #496 Layout-Fix
Spec: docs/specs/modules/issue_496_channel_preview_layout_fix.md

AC-1: Email-Tabelle horizontal scrollbar mit 10+ Metriken (scrollWidth > clientWidth)
AC-2: ChannelPreviewBlock Breite > 900px auf 1440px-Desktop
AC-3: Email mit 5 Metriken: alle Spalten ohne Scrollen sichtbar (scrollWidth == clientWidth)
AC-4: data-testid="channel-preview-block" und "channel-fidelity-email" vorhanden
"""
import json
import os
import re
import time
import uuid

import pytest
from playwright.sync_api import sync_playwright

from tests.helpers.staging_auth import (  # Bündel H #987: Staging-Basic-Auth
    playwright_http_credentials,
)

# Dialt real gegen Staging/Prod (#1211 Scheibe 2a) -- nur via -m staging ausfuehren.
pytestmark = pytest.mark.staging

BASE = "https://staging.gregor20.henemm.com"
# App-Login-Konto (GZ_AUTH_*) — unabhaengig von den rotierenden nginx-Basic-Auth-
# Validator-Creds (GZ_VALIDATOR_*, siehe playwright_http_credentials()).
USER = os.environ.get("GZ_AUTH_USER", "default")
PASS = os.environ.get("GZ_AUTH_PASS", "")

MANY_METRICS = [
    "temperature", "wind_chill", "wind", "gust", "rain_probability",
    "precipitation", "thunder", "cloud_total", "uv_index", "humidity",
    "visibility", "freezing_level",
]
FEW_METRICS = ["temperature", "wind", "gust", "rain_probability", "precipitation"]


def _login(page):
    page.goto(f"{BASE}/login", wait_until="networkidle")
    time.sleep(2)
    inp = page.query_selector("input[name='identifier']") or page.query_selector("input[type='text']")
    inp.click()
    page.keyboard.type(USER)
    pw = page.query_selector("input[type='password']")
    pw.click()
    page.keyboard.type(PASS)
    page.click("button[type='submit']")
    page.wait_for_url(re.compile(r"^https://staging\.gregor20\.henemm\.com(?!/login)"), timeout=30000)


def _create_trip(page, primary_metrics):
    trip_id = uuid.uuid4().hex[:8]
    payload = {
        "id": trip_id,
        "name": f"TDD-496-{trip_id}",
        "stages": [],
        "display_config": {
            "buckets": {
                "primary": primary_metrics,
                "secondary": [],
                "off": [],
            }
        },
    }
    resp = page.request.post(
        f"{BASE}/api/trips",
        data=json.dumps(payload),
        headers={"Content-Type": "application/json"},
    )
    assert resp.ok, f"Trip-Anlage fehlgeschlagen: {resp.status} {resp.text()[:200]}"
    return trip_id


def _delete_trip(page, trip_id):
    page.request.delete(f"{BASE}/api/trips/{trip_id}")


def _open_email_preview(page, trip_id):
    page.goto(f"{BASE}/trips/{trip_id}#weather", wait_until="networkidle")
    time.sleep(2)
    for sel in ["button:has-text('Wetter-Briefing')", "[role='tab']:has-text('Wetter')"]:
        el = page.query_selector(sel)
        if el:
            el.click()
            time.sleep(1.5)
            break
    email_btn = page.query_selector('[data-testid="channel-consequence-email"]')
    assert email_btn, "channel-consequence-email Button nicht gefunden"
    email_btn.click()
    time.sleep(1)


@pytest.fixture(scope="module")
def browser_ctx():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        ctx = browser.new_context(
            viewport={"width": 1440, "height": 900},
            http_credentials=playwright_http_credentials(),
        )
        page = ctx.new_page()
        _login(page)
        yield page
        browser.close()


@pytest.fixture()
def trip_many(browser_ctx):
    trip_id = _create_trip(browser_ctx, MANY_METRICS)
    yield trip_id
    _delete_trip(browser_ctx, trip_id)


@pytest.fixture()
def trip_few(browser_ctx):
    trip_id = _create_trip(browser_ctx, FEW_METRICS)
    yield trip_id
    _delete_trip(browser_ctx, trip_id)


def test_ac1_email_scroll_with_many_metrics(browser_ctx, trip_many):
    """
    AC-1: Given Email aktiv und 10+ Metriken in primary
    When Nutzer zur Email-Fidelity scrollt
    Then alle Spalten erreichbar — Card.Root darf overflow NICHT mehr :hidden klemmen
    """
    _open_email_preview(browser_ctx, trip_many)

    # Direkt den Bug-1-Fix prüfen: Card.Root darf nicht mehr overflow:hidden sein
    card = browser_ctx.query_selector('[data-testid="channel-preview-block"]')
    assert card, "channel-preview-block nicht gefunden"
    card_overflow_x = browser_ctx.evaluate(
        "el => window.getComputedStyle(el).overflowX", card
    )
    assert card_overflow_x != "hidden", (
        f"AC-1 FAIL: Card.Root hat overflowX='{card_overflow_x}'. "
        f"overflow-visible-Fix ist nicht aktiv — Tabelle kann abgeschnitten sein."
    )

    # Wenn die Tabelle überläuft, muss der Scroll-Mechanismus funktionieren
    table_wrap = browser_ctx.query_selector(".table-wrap")
    assert table_wrap, ".table-wrap nicht gefunden"
    scroll_width = browser_ctx.evaluate("el => el.scrollWidth", table_wrap)
    client_width = browser_ctx.evaluate("el => el.clientWidth", table_wrap)
    if scroll_width > client_width:
        overflow_x = browser_ctx.evaluate(
            "el => window.getComputedStyle(el).overflowX", table_wrap
        )
        assert overflow_x in ("auto", "scroll"), (
            f"AC-1 FAIL: Tabelle überläuft (scrollWidth={scroll_width} > "
            f"clientWidth={client_width}) aber overflow-x='{overflow_x}'. Scroll blockiert."
        )


def test_ac2_block_uses_full_tab_width(browser_ctx, trip_many):
    """
    AC-2: Given Wetter-Briefing-Tab auf 1440px-Desktop
    When ChannelPreviewBlock gerendert
    Then Breite > 900px (volle Tab-Breite, nicht editor-col ~628px)
    """
    _open_email_preview(browser_ctx, trip_many)

    block = browser_ctx.query_selector('[data-testid="channel-preview-block"]')
    assert block, "channel-preview-block nicht gefunden"

    bb = block.bounding_box()
    assert bb, "Bounding Box nicht ermittelbar"

    assert bb["width"] > 900, (
        f"AC-2 FAIL: Block zu schmal. "
        f"Breite={bb['width']:.0f}px, erwartet >900px. "
        f"Block sitzt noch in editor-col statt auf voller Tab-Breite."
    )


def test_ac3_five_metrics_all_columns_visible(browser_ctx, trip_few):
    """
    AC-3: Given Email-Vorschau mit 5 primären Metriken
    When Desktop-Mail-Ansicht aktiv
    Then alle 5 Spalten ohne Scrollen sichtbar (scrollWidth == clientWidth)
    """
    _open_email_preview(browser_ctx, trip_few)

    table_wrap = browser_ctx.query_selector(".table-wrap")
    assert table_wrap, ".table-wrap nicht gefunden"

    scroll_width = browser_ctx.evaluate("el => el.scrollWidth", table_wrap)
    client_width = browser_ctx.evaluate("el => el.clientWidth", table_wrap)

    assert scroll_width <= client_width, (
        f"AC-3 FAIL: 5 Metriken sollten ohne Scrollen passen. "
        f"scrollWidth={scroll_width} > clientWidth={client_width}. "
        f"Block zu schmal oder overflow:hidden aktiv."
    )


def test_ac4_testids_present(browser_ctx, trip_few):
    """
    AC-4: data-testid='channel-preview-block' und 'channel-fidelity-email' vorhanden
    (Regressions-Check — muss auch nach Verschiebung des Blocks bestehen)
    """
    _open_email_preview(browser_ctx, trip_few)

    block = browser_ctx.query_selector('[data-testid="channel-preview-block"]')
    assert block, "data-testid='channel-preview-block' fehlt"

    fidelity = browser_ctx.query_selector('[data-testid="channel-fidelity-email"]')
    assert fidelity, "data-testid='channel-fidelity-email' fehlt"
