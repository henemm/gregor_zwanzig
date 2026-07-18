"""TDD RED — Issue #576: Token-Werte computed style auf Staging.

Spec: docs/specs/modules/issue_576_tokens_sync_v2.md
Test-Manifest: docs/specs/tests/issue_576_token_values_tests.md
"""
import os
from pathlib import Path

import pytest

# Dialt real gegen Staging/Prod (#1211 Scheibe 2a) -- nur via -m staging ausfuehren.
pytestmark = pytest.mark.staging

VALIDATOR_ENV = Path(__file__).resolve().parents[2] / ".claude" / "validator.env"
if VALIDATOR_ENV.exists():
    for line in VALIDATOR_ENV.read_text().splitlines():
        if line and "=" in line and not line.startswith("#"):
            k, v = line.split("=", 1)
            os.environ.setdefault(k.strip(), v.strip())

STAGING = os.environ.get("GZ_VALIDATION_URL", "https://staging.gregor20.henemm.com")
USER = os.environ.get("GZ_VALIDATOR_USER", "")
PASS = os.environ.get("GZ_VALIDATOR_PASS", "")


@pytest.fixture(scope="module")
def page():
    pytest.importorskip("playwright.sync_api")
    from playwright.sync_api import sync_playwright

    if not USER or not PASS:
        pytest.skip("GZ_VALIDATOR_USER/PASS nicht gesetzt")

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        ctx = browser.new_context(viewport={"width": 1024, "height": 680})
        page = ctx.new_page()
        page.goto(f"{STAGING}/login", timeout=20000)
        page.fill("input[name='username']", USER)
        page.fill("input[name='password']", PASS)
        page.click("button[type='submit']")
        page.wait_for_url(lambda u: "/login" not in u, timeout=15000)
        page.goto(f"{STAGING}/archiv", timeout=20000)
        page.wait_for_load_state("networkidle", timeout=15000)
        yield page
        browser.close()


def _computed(page, var_name: str, css_property: str) -> str:
    return page.evaluate(
        """([varName, prop]) => {
            const d = document.createElement('div');
            d.style.width = '100px';
            d.style.height = '100px';
            d.style[prop.replace(/-([a-z])/g, (_, c) => c.toUpperCase())] = `var(${varName})`;
            d.style.position = 'absolute';
            d.style.top = '-9999px';
            document.body.appendChild(d);
            const style = getComputedStyle(d);
            const val = style.getPropertyValue(prop);
            d.remove();
            return val;
        }""",
        [var_name, css_property],
    )


def test_issue_576_g_r_3_is_6px(page):
    """AC-1: --g-r-3 muss 6px ergeben (JSX-Wert)."""
    val = _computed(page, "--g-r-3", "border-radius")
    assert val == "6px", f"--g-r-3 ist {val!r}, erwartet '6px'"


def test_issue_576_g_r_4_is_10px(page):
    """AC-2: --g-r-4 muss 10px ergeben (JSX-Wert)."""
    val = _computed(page, "--g-r-4", "border-radius")
    assert val == "10px", f"--g-r-4 ist {val!r}, erwartet '10px'"


def test_issue_576_g_info_is_2c5a8c(page):
    """AC-3: --g-info muss rgb(44, 90, 140) = #2c5a8c ergeben."""
    val = _computed(page, "--g-info", "background-color")
    assert val in ("rgb(44, 90, 140)", "#2c5a8c"), (
        f"--g-info ist {val!r}, erwartet 'rgb(44, 90, 140)'"
    )
