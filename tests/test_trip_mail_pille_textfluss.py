"""Issue #1670 (TDD RED) AC-1/AC-2: Pillen der Trip-Mail fliessen als Text.

Spec: docs/specs/modules/fix_1670_mail_formatdetails.md
Heute: pill_html() liefert display:inline-flex -> mobil kollabiert das
Leerzeichen vor der Uhrzeit ("Max16:00"). Keine Mocks, echter Renderer.
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest

from src.output.renderers.email.helpers import pill_html

LABELS = ["Max 16:00", "ab 15:00 · Regen", "stärkste 14:00"]
HTML_PY = Path(__file__).resolve().parent.parent / "src/output/renderers/email/html.py"


@pytest.mark.parametrize("label", LABELS)
@pytest.mark.parametrize("tone", ["ampel_green", "ampel_red", "neutral"])
def test_pille_ist_kein_flex_container(label, tone):
    html = pill_html(label, tone)
    assert "inline-flex" not in html
    assert "display:flex" not in html
    assert "display:inline-block" in html
    assert "vertical-align:middle" in html


@pytest.mark.parametrize("label", LABELS)
def test_pillentext_bleibt_zeichengleich_mit_leerzeichen_vor_uhrzeit(label):
    html = pill_html(label, "ampel_green")
    text = re.sub(r"<[^>]+>", "", html)
    assert text == label
    assert re.search(r" \d{2}:00", text)


def test_pillen_container_behaelt_abstand_und_umbruch():
    src = HTML_PY.read_text(encoding="utf-8")  # doc-compliance-test
    assert "display:flex;gap:6px;flex-wrap:wrap" in src
