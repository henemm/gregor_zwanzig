"""RED — Issue #1314: Ortsvergleich-Matrix-Chip kollabiert visuell identische

amtliche Warnungen ("Hitze" + "Hitze"), ohne die Datenebene zu veraendern.

SPEC: docs/specs/modules/issue_1314_compare_warn_chip_dedup.md (AC-1..AC-5)

Kern-Schicht (deterministisch, netzfrei, keine Mocks): echte
``OfficialAlert``-Objekte, direkter Aufruf der Render-Funktionen. Testdatei
nach Verhalten benannt (nicht nach Issue-Nummer, s. test_naming_gate).

Test 1 (AC-1) ist der eigentliche Bug-Repro und muss vor dem Fix ROT sein:
zwei extreme_heat-Alerts gleicher Stufe mit unterschiedlichem Zeitfenster
ueberleben die Datenebene-Dedup (``_dedup_alerts``) als zwei getrennte
Objekte (das ist beabsichtigtes Verhalten, #1245/#1134), rendern in
``_render_warn_cell`` aber aktuell als zwei sichtbar identische "Hitze"-
Chips. Tests 2-5 sind Nicht-Regressions-/Konsistenz-Checks (AC-2..AC-5) und
duerfen bereits vor dem Fix gruen sein.
"""
from __future__ import annotations

from datetime import datetime

from output.renderers.alert.official_alerts import (
    render_official_alerts_html,
    render_official_alerts_plain,
)
from output.renderers.email.compare_html import (
    _ALERT_LEVEL_CELL,
    _dedup_alerts,
    _render_warn_cell,
)
from services.official_alerts.models import OfficialAlert


def _heat_alert(region: str, level: int, day: int, label: str) -> OfficialAlert:
    return OfficialAlert(
        source="meteofrance",
        hazard="extreme_heat",
        level=level,
        label=label,
        valid_from=datetime(2026, 7, day, 12, 0),
        valid_to=datetime(2026, 7, day, 18, 0),
        region_label=region,
    )


def test_ac1_two_extreme_heat_same_level_different_window_collapse_to_one_chip():
    """AC-1: zwei extreme_heat-Alerts gleicher Stufe, unterschiedliches
    Zeitfenster/Ort-Label -- _render_warn_cell darf nur EINEN 'Hitze'-Chip
    rendern (aktuell: zwei, weil _warn_short kein unterscheidendes Detail
    traegt)."""
    alert1 = _heat_alert("Nord", level=3, day=20, label="Hitzewarnung Nord")
    alert2 = _heat_alert("Sued", level=3, day=21, label="Hitzewarnung Sued")

    # Sanity: die Datenebene-Dedup (#1245/#1134) darf die beiden Alerts NICHT
    # zusammenfassen -- sonst waere dies kein echter Bug-Repro auf Render-Ebene.
    deduped = _dedup_alerts([alert1, alert2])
    assert len(deduped) == 2, (
        "Test-Fixture ungültig: _dedup_alerts hat die zwei Alerts bereits auf "
        "Datenebene kollabiert -- AC-1 würde dann keinen echten Render-Bug "
        "belegen."
    )

    result = _render_warn_cell(deduped)

    assert result.count(">Hitze<") == 1, (
        f"Erwartet genau EIN 'Hitze'-Chip (visuelle Kollaps-Ebene fehlt "
        f"noch), gefunden: {result.count('>Hitze<')} in {result!r}"
    )


def test_ac2_two_extreme_heat_different_level_keep_both_chips():
    """AC-2 (Nicht-Regression): unterschiedliche Stufe -> unterschiedliche
    Chip-Farbe -> beide Chips bleiben sichtbar."""
    alert_l2 = _heat_alert("Nord", level=2, day=20, label="Hitzewarnung Nord")
    alert_l3 = _heat_alert("Sued", level=3, day=21, label="Hitzewarnung Sued")

    deduped = _dedup_alerts([alert_l2, alert_l3])
    assert len(deduped) == 2

    result = _render_warn_cell(deduped)

    assert result.count(">Hitze<") == 2

    bg_l2, _fg_l2 = _ALERT_LEVEL_CELL[2]
    bg_l3, _fg_l3 = _ALERT_LEVEL_CELL[3]
    assert bg_l2 != bg_l3, "Testvoraussetzung: Level 2/3 muessen unterschiedliche Farben haben"
    assert f"background:{bg_l2};" in result
    assert f"background:{bg_l3};" in result


def test_ac3_different_hazards_keep_both_chips():
    """AC-3 (Nicht-Regression): unterschiedliche hazard-Kuerzel ('Hitze' vs.
    'Zugang') kollabieren nicht miteinander."""
    heat = _heat_alert("Nord", level=3, day=20, label="Hitzewarnung Nord")
    access = OfficialAlert(
        source="prefecture",
        hazard="access_ban",
        level=2,
        label="Zugang eingeschraenkt",
        valid_from=datetime(2026, 7, 20, 0, 0),
        valid_to=datetime(2026, 7, 20, 23, 59),
        region_label="Massiv X",
    )

    deduped = _dedup_alerts([heat, access])
    assert len(deduped) == 2

    result = _render_warn_cell(deduped)

    assert result.count(">Hitze<") == 1
    assert result.count(">Zugang<") == 1


def test_ac4_per_location_strip_keeps_both_alerts_with_detail():
    """AC-4 (Nicht-Regression): der Pro-Ort-Streifen (render_official_alerts_html)
    zeigt weiterhin beide Warnungen mit ihrem jeweiligen Detail (Label +
    Zeitfenster) -- die Chip-Kollaps-Logik aus _render_warn_cell wirkt hier
    NICHT."""
    alert1 = _heat_alert("Nord", level=3, day=20, label="Hitzewarnung Nord")
    alert2 = _heat_alert("Sued", level=3, day=21, label="Hitzewarnung Sued")

    deduped = _dedup_alerts([alert1, alert2])
    assert len(deduped) == 2

    html = render_official_alerts_html([("Testort", deduped)])

    assert "Hitzewarnung Nord" in html
    assert "Hitzewarnung Sued" in html
    # Unterscheidende Zeitfenster (unterschiedlicher Kalendertag) muessen
    # beide im Streifen auftauchen -- kein Kollaps auf ein gemeinsames Detail.
    assert "20.07." in html
    assert "21.07." in html


def test_ac5_plain_text_keeps_both_lines_with_detail():
    """AC-5 (Konsistenz-Check): der Klartext-Pfad (render_official_alerts_plain)
    kennt strukturell keine Kuerzel-Kompression -- beide Zeilen mit Detail
    bleiben unveraendert erhalten."""
    alert1 = _heat_alert("Nord", level=3, day=20, label="Hitzewarnung Nord")
    alert2 = _heat_alert("Sued", level=3, day=21, label="Hitzewarnung Sued")

    deduped = _dedup_alerts([alert1, alert2])
    assert len(deduped) == 2

    lines = render_official_alerts_plain([("Testort", deduped)])

    assert len(lines) == 2
    assert any("Hitzewarnung Nord" in line and "20.07." in line for line in lines)
    assert any("Hitzewarnung Sued" in line and "21.07." in line for line in lines)
