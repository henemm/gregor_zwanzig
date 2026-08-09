"""TDD RED — Issue #1614 Teil 2: GELB-Kontrast (`G_ALERT_L2`) auf WCAG-AA.

SPEC: docs/specs/modules/fix_1614_briefing_warnfenster.md (AC-8, AC-9)

RED-Ursache (heute): `G_ALERT_L2` steht noch auf dem alten Wert `#9a6f00`
(4,11:1 gegen `G_PAPER`, unter der von CLAUDE.md geforderten WCAG-AA-
Mindestgrenze 4,5:1). Der neue Wert `#8a6300` erreicht laut Spec-Rechnung
4,94:1 (G_PAPER) bzw. 5,43:1 (weisser Kartenhintergrund).

Testpolitik (CLAUDE.md "Test-Politik: Zwei Schichten"): reine Mathematik
gegen die Hex-Konstanten -- WCAG-2.1-relative-Luminanz-Formel aus dem
bestehenden Mess-Werkzeug `scripts/contrast_audit.py` (keine zweite Formel-
Implementierung). Kein Mock-Theater. Test 9 prueft die tatsaechlich
gerenderte HTML-Ausgabe (Wirkung, nicht nur die Konstante).

Pfadregel #1409: `_REPO_ROOT` wird relativ zu DIESER Datei aufgeloest.
"""
from __future__ import annotations

import importlib.util
from datetime import datetime, timedelta, timezone
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[2]

_NEW_G_ALERT_L2 = "#8a6300"
_OLD_G_ALERT_L2 = "#9a6f00"
_G_PAPER = "#f6f4ee"
# design_tokens.py definiert keine eigene "G_CARD"-Konstante -- der
# Warn-Block sitzt teils direkt auf weissem Kartenhintergrund (Spec-Rechnung
# "gegen G_CARD (#ffffff)").
_G_CARD = "#ffffff"


def _load_contrast_audit():
    """Laedt das bestehende Mess-Werkzeug als Modul (kein Formel-Duplikat)."""
    spec = importlib.util.spec_from_file_location(
        "contrast_audit_1614", _REPO_ROOT / "scripts" / "contrast_audit.py",
    )
    if spec is None or spec.loader is None:
        raise FileNotFoundError("scripts/contrast_audit.py nicht ladbar")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_g_alert_l2_neuer_wert_erreicht_wcag_aa_gegen_paper_und_card():
    """Test 8 / AC-8.

    GIVEN der neue `G_ALERT_L2`-Wert `#8a6300`
    WHEN  der Kontrast gegen `G_PAPER` (`#f6f4ee`) und den weissen
          Kartenhintergrund (`#ffffff`) nach WCAG-2.1 berechnet wird
    THEN  liegt beides bei mindestens 4,5:1 (WCAG-AA).
    """
    from output.renderers.email.design_tokens import G_ALERT_L2

    assert G_ALERT_L2 == _NEW_G_ALERT_L2, (
        f"G_ALERT_L2 muss auf den kontrastreicheren Wert {_NEW_G_ALERT_L2!r} "
        f"angehoben werden, aktuell: {G_ALERT_L2!r}"
    )
    cab = _load_contrast_audit()
    ratio_paper = cab.contrast_ratio(G_ALERT_L2, _G_PAPER)
    ratio_card = cab.contrast_ratio(G_ALERT_L2, _G_CARD)
    assert ratio_paper >= 4.5, (
        f"G_ALERT_L2 ({G_ALERT_L2!r}) gegen G_PAPER unter WCAG-AA: {ratio_paper:.2f}:1"
    )
    assert ratio_card >= 4.5, (
        f"G_ALERT_L2 ({G_ALERT_L2!r}) gegen G_CARD unter WCAG-AA: {ratio_card:.2f}:1"
    )


def test_renderer_gibt_den_neuen_farbwert_fuer_eine_gelbe_warnung_aus():
    """Test 9 / AC-9 (Renderer-Durchgriff).

    GIVEN eine amtliche Warnung der Stufe 2 (GELB)
    WHEN  sie als E-Mail-HTML gerendert wird (`render_official_alerts_html`)
    THEN  enthaelt die erzeugte Ausgabe den neuen Hex-Wert `#8a6300`, nicht
          mehr den alten `#9a6f00` -- belegt, dass der Token-Wechsel bis zur
          tatsaechlichen Ausgabe durchschlaegt.
    """
    from output.renderers.alert.official_alerts import render_official_alerts_html
    from services.official_alerts import OfficialAlert

    now = datetime.now(timezone.utc)
    alert = OfficialAlert(
        source="tdd-1614-t9", hazard="thunderstorm", level=2,
        label="Gewitterwarnung Stufe 2 (#1614 Test 9)", region_label="Gailtal",
        valid_from=now - timedelta(hours=1), valid_to=now + timedelta(hours=8),
    )
    html = render_official_alerts_html([("Gailtal", [alert])])

    assert _NEW_G_ALERT_L2 in html, (
        f"Der neue Farbwert {_NEW_G_ALERT_L2!r} muss im gerenderten HTML einer "
        f"Stufe-2-Warnung erscheinen: {html!r}"
    )
    assert _OLD_G_ALERT_L2 not in html, (
        f"Der alte Farbwert darf nach dem Token-Wechsel nicht mehr erscheinen: {html!r}"
    )
