"""TDD RED — Issue #577: Atom-Werte computed style auf Staging.

Spec: docs/specs/modules/issue_577_atoms_sync_v2.md
Test-Manifest: docs/specs/tests/issue_577_atoms_values_tests.md
"""
import os
from pathlib import Path

import pytest

from tests.helpers.staging_auth import (  # Bündel H #987: Staging-Basic-Auth
    playwright_http_credentials,
)

VALIDATOR_ENV = Path(__file__).resolve().parents[2] / ".claude" / "validator.env"
if VALIDATOR_ENV.exists():
    for line in VALIDATOR_ENV.read_text().splitlines():
        if line and "=" in line and not line.startswith("#"):
            k, v = line.split("=", 1)
            os.environ.setdefault(k.strip(), v.strip())

STAGING = os.environ.get("GZ_VALIDATION_URL", "https://staging.gregor20.henemm.com")
# App-Login-Konto (GZ_AUTH_*) — unabhaengig von den rotierenden nginx-Basic-Auth-
# Validator-Creds (GZ_VALIDATOR_*, siehe playwright_http_credentials()).
USER = os.environ.get("GZ_AUTH_USER", "default")
PASS = os.environ.get("GZ_AUTH_PASS", "")


@pytest.fixture(scope="module")
def page():
    pytest.importorskip("playwright.sync_api")
    from playwright.sync_api import sync_playwright

    if not USER or not PASS:
        pytest.skip("GZ_AUTH_USER/PASS nicht gesetzt")

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        ctx = browser.new_context(
            viewport={"width": 1024, "height": 680},
            http_credentials=playwright_http_credentials(),
        )
        pg = ctx.new_page()
        pg.goto(f"{STAGING}/login", timeout=20000)
        pg.fill("input[name='username']", USER)
        pg.fill("input[name='password']", PASS)
        pg.click("button[type='submit']")
        pg.wait_for_url(lambda u: "/login" not in u, timeout=15000)
        pg.goto(f"{STAGING}/archiv", timeout=20000)
        pg.wait_for_load_state("networkidle", timeout=15000)
        yield pg
        browser.close()


def _inject_and_read(page, html: str, props):
    return page.evaluate(
        """([html, props]) => {
            const wrap = document.createElement('div');
            wrap.style.position = 'absolute';
            wrap.style.top = '-9999px';
            wrap.innerHTML = html;
            document.body.appendChild(wrap);
            const el = wrap.firstElementChild;
            const cs = getComputedStyle(el);
            const out = {};
            for (const p of props) out[p] = cs.getPropertyValue(p);
            wrap.remove();
            return out;
        }""",
        [html, props],
    )


def _resolve_var(page, var_name: str, prop: str = "color") -> str:
    return page.evaluate(
        """([varName, prop]) => {
            const d = document.createElement('div');
            d.style[prop.replace(/-([a-z])/g, (_, c) => c.toUpperCase())] = `var(${varName})`;
            d.style.position = 'absolute';
            d.style.top = '-9999px';
            document.body.appendChild(d);
            const v = getComputedStyle(d).getPropertyValue(prop);
            d.remove();
            return v;
        }""",
        [var_name, prop],
    )


def test_issue_577_btn_border_radius_4px(page):
    """AC-1: Btn border-radius = 4px (JSX --g-r-2)."""
    out = _inject_and_read(page, '<button data-slot="btn" data-variant="primary" data-size="md">x</button>', ["border-radius"])
    assert out["border-radius"].strip() == "4px", f"border-radius = {out['border-radius']!r}, erwartet '4px'"


def test_issue_577_btn_md_padding_9_14(page):
    """AC-2: Btn md padding = 9px 14px."""
    out = _inject_and_read(page, '<button data-slot="btn" data-variant="primary" data-size="md">x</button>',
                           ["padding-top", "padding-bottom", "padding-left", "padding-right"])
    assert out["padding-top"].strip() == "9px", f"padding-top = {out['padding-top']!r}"
    assert out["padding-bottom"].strip() == "9px", f"padding-bottom = {out['padding-bottom']!r}"
    assert out["padding-left"].strip() == "14px", f"padding-left = {out['padding-left']!r}"
    assert out["padding-right"].strip() == "14px", f"padding-right = {out['padding-right']!r}"


def test_issue_577_btn_lg_padding_and_fs(page):
    """AC-3: Btn lg padding = 12px 20px, font-size = 14px."""
    out = _inject_and_read(page, '<button data-slot="btn" data-variant="primary" data-size="lg">x</button>',
                           ["padding-top", "padding-bottom", "padding-left", "padding-right", "font-size"])
    assert out["padding-top"].strip() == "12px", f"padding-top = {out['padding-top']!r}"
    assert out["padding-bottom"].strip() == "12px", f"padding-bottom = {out['padding-bottom']!r}"
    assert out["padding-left"].strip() == "20px", f"padding-left = {out['padding-left']!r}"
    assert out["padding-right"].strip() == "20px", f"padding-right = {out['padding-right']!r}"
    assert out["font-size"].strip() == "14px", f"font-size = {out['font-size']!r}"


def test_issue_577_btn_sm_fs_12px(page):
    """AC-4: Btn sm font-size = 12px."""
    out = _inject_and_read(page, '<button data-slot="btn" data-variant="primary" data-size="sm">x</button>', ["font-size"])
    assert out["font-size"].strip() == "12px", f"font-size = {out['font-size']!r}"


def test_issue_577_btn_accent_color_white(page):
    """AC-5: Btn accent color = rgb(255, 255, 255) (#fff)."""
    out = _inject_and_read(page, '<button data-slot="btn" data-variant="accent" data-size="md">x</button>', ["color"])
    assert out["color"].strip() == "rgb(255, 255, 255)", f"color = {out['color']!r}, erwartet 'rgb(255, 255, 255)'"


def test_issue_577_pill_padding_3_9(page):
    """AC-6: Pill padding = 3px 9px."""
    out = _inject_and_read(page, '<span data-slot="pill" data-tone="neutral">x</span>',
                           ["padding-top", "padding-bottom", "padding-left", "padding-right"])
    assert out["padding-top"].strip() == "3px", f"padding-top = {out['padding-top']!r}"
    assert out["padding-bottom"].strip() == "3px", f"padding-bottom = {out['padding-bottom']!r}"
    assert out["padding-left"].strip() == "9px", f"padding-left = {out['padding-left']!r}"
    assert out["padding-right"].strip() == "9px", f"padding-right = {out['padding-right']!r}"


def test_issue_577_gcard_border_radius_6px(page):
    """AC-7: g-card border-radius = 6px (JSX --g-r-3)."""
    out = _inject_and_read(page, '<div data-slot="g-card">x</div>', ["border-radius"])
    assert out["border-radius"].strip() == "6px", f"border-radius = {out['border-radius']!r}"


def test_issue_577_gcard_padding_20px(page):
    """AC-8: g-card padding = 20px."""
    out = _inject_and_read(page, '<div data-slot="g-card">x</div>',
                           ["padding-top", "padding-bottom", "padding-left", "padding-right"])
    for p in ["padding-top", "padding-bottom", "padding-left", "padding-right"]:
        assert out[p].strip() == "20px", f"{p} = {out[p]!r}"


def test_issue_577_gcard_border_1px(page):
    """AC-9: g-card border-width = 1px, border-style = solid."""
    out = _inject_and_read(page, '<div data-slot="g-card">x</div>', ["border-top-width", "border-top-style"])
    assert out["border-top-width"].strip() == "1px", f"border-top-width = {out['border-top-width']!r}"
    assert out["border-top-style"].strip() == "solid", f"border-top-style = {out['border-top-style']!r}"


def test_issue_577_eyebrow_color_same_as_ink_3(page):
    """AC-10: Eyebrow color = rgb(107, 103, 92) (= JSX --g-ink-3 = #6b675c)."""
    out = _inject_and_read(page, '<div data-slot="eyebrow">x</div>', ["color"])
    assert out["color"].strip() == "rgb(107, 103, 92)", f"color = {out['color']!r}, erwartet 'rgb(107, 103, 92)'"
