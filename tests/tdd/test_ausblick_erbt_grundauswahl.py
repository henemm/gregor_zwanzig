"""TDD RED — #1848 A3: der Trip-Ausblick erbt die Grundauswahl (Block B/D).

SPEC: docs/specs/modules/feat_1848_a3_ausblick_erbt_grundauswahl.md
      AC-3, AC-4, AC-10, AC-11 (Trip-Seite; AC-6/Ortsvergleich siehe
      test_compare_ausblick_erbt_grundauswahl.py)
KONTEXT: docs/context/feat-1848-a3-outlook-kanal-modul.md M1/M3/M5

Prueforts-Regel (Spec, "Harte Regeln"): jeder Test rendert ueber
``render_trip_mail()`` -- den echten Aufrufpfad ueber
``TripReportFormatter.format_email()`` inkl. ``resolve_trip_outlook_metrics()``
und ``html.py``/``plain.py``. Ein Test auf den Rueckgabewert des Resolvers
allein faengt einen Rueckfall im Renderer nicht (CLAUDE.md-Regel
"Prueford == Wirkort").

Kein Mock-Framework, kein Netz -- echte ``UnifiedWeatherDisplayConfig``- und
``SegmentWeatherSummary``-Objekte ueber die Fixtur-Helfer aus
``tests/helpers/trip_outlook_selection.py`` (Vorbild:
``tests/tdd/test_trip_outlook_metric_selection.py``, #1720 S1).

🔴 Bekannter Konflikt mit Bestandsschutz (fuer den Adversary/GREEN-Phase
dokumentiert, s. Abschluss-Bericht des RED-Agenten): AC-3 aendert den
Rueckfall fuer ``outlook_metrics=None`` von "sieben feste Spalten" auf "volle
Grundauswahl". Das widerspricht direkt
``test_trip_outlook_metric_selection.py::test_ac1_bestandstrip_html_ausblick_bleibt_byte_identisch``
und ihren zwei Geschwistern (Legende/Klartext) -- Spec "Known Limitations"
nennt das ausdruecklich ("Die Ausblick-Tabelle wird fuer bestehende Trips
breiter"). Diese Datei fasst jene Tests NICHT an (RED-Phase-Auftrag: nur neue
Tests, keine Implementierung/Aufraeumung bestehender Tests ausserhalb des
explizit benannten AST-Waechters).
"""
from __future__ import annotations

import sys
from pathlib import Path

# Pfadregel #1409: Pruefling relativ zur eigenen Testdatei aufloesen.
REPO_ROOT = Path(__file__).resolve().parents[2]
for _pfad in (REPO_ROOT, REPO_ROOT / "src"):
    if str(_pfad) not in sys.path:
        sys.path.insert(0, str(_pfad))

from tests.helpers.outlook_columns import compare_outlook_soll_spalten  # noqa: E402
from tests.helpers.trip_outlook_selection import (  # noqa: E402
    display_config, html_outlook_headers, outlook_rows, plain_outlook_block,
    render_trip_mail,
)

# Die heutigen sieben festen Rueckfall-Spaltenkuerzel (email/outlook.py:157-170)
# -- AC-3 verlangt, dass sie fuer eine Grundauswahl-gebundene Vorschau NICHT
# mehr erscheinen.
_FIXED_SEVEN = {"N", "D", "R", "PR", "Wind", "Böen", "Gew"}
# #2098 AC-13: ACC ist seit der Behebung eine fest angehaengte Zusatzspalte
# HINTER der Auswahl -- sie stammt nicht aus der Grundauswahl und ist auch
# keine der abgeloesten sieben festen Spalten.
_ACC = "ACC"


def _soll_ueberschriften(metric_ids: set[str]) -> set[str]:
    """Erwartete Spaltenueberschriften fuer eine Grundauswahl, GERECHNET aus
    dem Compare-Katalog (nicht aus ``outlook_columns()`` uebernommen -- sonst
    waeren Massstab und Pruefling dieselbe Funktion, Vorbild
    ``test_trip_outlook_metric_selection.py::test_ac11...``)."""
    return {
        s["ueberschrift"] for s in compare_outlook_soll_spalten()
        if s["metric_id"] in metric_ids
    }


# ══════════════════════ AC-3 — Grundauswahl ist die Ausgangsmenge ═══════════

def test_ac3_ohne_gesetzte_ausblick_auswahl_zeigt_die_ausblick_tabelle_die_grundauswahl():
    """AC-3: Given ein Trip mit einer Grundauswahl aus drei darstellbaren
    Groessen und ``outlook_metrics`` noch nie eingestellt (``None``) / When
    das Briefing gerendert wird / Then zeigt die Ausblick-Tabelle GENAU diese
    drei Groessen -- nicht die frueheren sieben festen Spalten.
    """
    enabled = {"temperature", "wind", "precipitation"}
    dc = display_config(enabled_ids=enabled)  # outlook_metrics bleibt UNGESETZT
    rows = outlook_rows(trip_display_config=dc, report_type="evening")
    html, plain = render_trip_mail(dc, rows)

    kopf = html_outlook_headers(html)
    assert kopf, "Keine Ausblick-Tabelle gerendert -- Vorbedingung von AC-3 verletzt."
    assert kopf[0] == "Tag", kopf
    erwartet = _soll_ueberschriften(enabled)
    assert set(kopf[1:]) == erwartet | {_ACC}, (
        f"Ausblick-Kopfzeile {kopf[1:]!r} entspricht nicht der Grundauswahl "
        f"{sorted(erwartet)!r} (AC-3). Ohne gesetzte Auswahl faellt der "
        "Renderer vermutlich noch auf die alten sieben festen Spalten zurueck."
    )
    assert not (set(kopf[1:]) & _FIXED_SEVEN - erwartet), (
        f"Kopfzeile {kopf[1:]!r} enthaelt Kuerzel der alten sieben festen "
        f"Ausblick-Spalten ({_FIXED_SEVEN}) -- genau das schliesst AC-3 aus."
    )

    block = plain_outlook_block(plain)
    assert block is not None, "Klartext-Ausblick fehlt (AC-3)."
    for label in erwartet:
        assert label in block, (
            f"Klartext-Ausblick nennt {label!r} nicht: {block!r} (AC-3)"
        )


# ══════════════ AC-4 — Grundauswahl-Abwahl gewinnt gegen outlook_metrics ════

def test_ac4_in_der_grundauswahl_abgewaehlte_groesse_erscheint_nie_im_ausblick():
    """AC-4: Given "Gewitter" ist in der Grundauswahl NICHT aktiv, steht aber
    in ``outlook_metrics`` / When der Ausblick gerendert wird / Then
    erscheint dafuer KEINE Spalte -- unabhaengig davon, was gespeichert ist.
    """
    from app.metric_catalog import get_metric

    enabled = {"temperature", "wind", "precipitation"}  # kein "thunder"
    auswahl = ["temperature", "thunder"]
    dc = display_config(enabled_ids=enabled, outlook_metrics=auswahl)
    rows = outlook_rows(trip_display_config=dc, report_type="evening")
    html, plain = render_trip_mail(dc, rows)

    # #2136/ADR-0068: die Spaltenkoepfe tragen `col_label` ("Thdr"/"Temp"),
    # nicht mehr den deutschen Katalog-Langnamen ("Gewitter"/"Temperatur").
    thunder_label = get_metric("thunder").col_label
    temp_label = get_metric("temperature").col_label

    kopf = html_outlook_headers(html)
    assert thunder_label not in kopf, (
        f"Kopfzeile {kopf!r}: {thunder_label!r} erscheint, obwohl die Groesse "
        "in der Grundauswahl nicht aktiv ist (AC-4)."
    )
    assert kopf[1:] == [temp_label, _ACC], (
        f"Erwartet nur die Grundauswahl-gedeckte Spalte {temp_label!r}: {kopf!r}"
    )
    block = plain_outlook_block(plain)
    assert block is not None and thunder_label not in block, (
        f"Klartext-Ausblick nennt {thunder_label!r} trotz "
        f"Grundauswahl-Abwahl: {block!r}"
    )


# ═══════════════ AC-11 — bewusst geleert laesst den Block entfallen ═════════
#
# #3237: der AC-10-Teil (eine nach dem Grundauswahl-Schnitt vollstaendig
# verworfene Auswahl faellt mit Warnung auf die volle Grundauswahl zurueck)
# ist entfallen -- das war ein Schnitt-Rueckfall des Altpfads. Die Tabelle
# "Was steht wo" kennt keinen Rueckfall (ADR-0124, "Leer bleibt leer"); eine
# Metrik ausserhalb der Grundauswahl hat dort keine Zeile.

def test_ac11_bewusst_geleerte_auswahl_laesst_den_block_entfallen():
    """AC-11: eine ausdruecklich leere Auswahl (``outlook_metrics=[]``, in der
    Tabelle: an keiner Ausblick-Stelle ein Haken) laesst den Block vollstaendig
    entfallen; Gegenprobe: ohne Einstellung erscheint er."""
    enabled = {"temperature", "wind", "precipitation"}
    dc_ac11 = display_config(enabled_ids=enabled, outlook_metrics=[])
    rows_ac11 = outlook_rows(trip_display_config=dc_ac11, report_type="evening")
    html_ac11, plain_ac11 = render_trip_mail(dc_ac11, rows_ac11)

    assert html_outlook_headers(html_ac11) == [], (
        "AC-11 FAIL: eine ausdruecklich leere Ausblick-Auswahl zeigt weiterhin "
        f"eine Tabelle: {html_outlook_headers(html_ac11)!r} -- 'bewusst geleert' "
        "muss den Block vollstaendig entfallen lassen."
    )
    assert plain_outlook_block(plain_ac11) is None, (
        "AC-11 FAIL: der Klartext zeigt trotz bewusst leerer Auswahl weiterhin "
        f"einen Ausblick-Block:\n{plain_ac11}"
    )
    dc_an = display_config(enabled_ids=enabled)
    html_an, _plain_an = render_trip_mail(
        dc_an, outlook_rows(trip_display_config=dc_an, report_type="evening"))
    assert html_outlook_headers(html_an), "Gegenprobe: ohne Einstellung fehlt der Ausblick"
