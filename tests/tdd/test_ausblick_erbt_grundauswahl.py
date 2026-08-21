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
nennt das ausdruecklich ("Die Ausblick-Tabelle wird fuer bestehende Touren
breiter"). Diese Datei fasst jene Tests NICHT an (RED-Phase-Auftrag: nur neue
Tests, keine Implementierung/Aufraeumung bestehender Tests ausserhalb des
explizit benannten AST-Waechters).
"""
from __future__ import annotations

import logging
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
    assert set(kopf[1:]) == erwartet, (
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
    enabled = {"temperature", "wind", "precipitation"}  # kein "thunder"
    auswahl = ["temperature", "thunder"]
    dc = display_config(enabled_ids=enabled, outlook_metrics=auswahl)
    rows = outlook_rows(trip_display_config=dc, report_type="evening")
    html, plain = render_trip_mail(dc, rows)

    kopf = html_outlook_headers(html)
    assert "Gewitter" not in kopf, (
        f"Kopfzeile {kopf!r}: 'Gewitter' erscheint, obwohl die Groesse in der "
        "Grundauswahl nicht aktiv ist (AC-4)."
    )
    assert kopf[1:] == ["Temperatur"], (
        f"Erwartet nur die Grundauswahl-gedeckte Spalte 'Temperatur': {kopf!r}"
    )
    block = plain_outlook_block(plain)
    assert block is not None and "Gewitter" not in block, (
        f"Klartext-Ausblick nennt 'Gewitter' trotz Grundauswahl-Abwahl: {block!r}"
    )


# ═══════════════ AC-10 / AC-11 — stiller Totalausfall wird unmoeglich ═══════

def test_ac10_vs_ac11_vollstaendig_geschnittene_auswahl_faellt_auf_die_grundauswahl_zurueck_bewusst_geleert_bleibt_verschieden(
    caplog,
):
    """AC-10 + AC-11 im selben Test gegenuebergestellt (Spec-Vorgabe: "sonst
    beweist keiner die Unterscheidbarkeit").

    AC-10: eine NICHT-LEERE, aber nach dem Schnitt gegen die Grundauswahl
    VOLLSTAENDIG verworfene Auswahl (beide Eintraege liegen ausserhalb der
    Grundauswahl) darf NICHT denselben Zustand erzeugen wie eine bewusst
    geleerte Auswahl -- der Ausblick muss mit der vollen Grundauswahl
    erscheinen, plus einer Protokoll-Warnung.

    AC-11: eine ausdruecklich leere Auswahl (``outlook_metrics=[]``) laesst
    den Block dagegen vollstaendig entfallen.

    🔴 M3-Bug (Kontext-Dokument): ``resolve_trip_outlook_metrics()`` liefert
    heute fuer den AC-10-Fall ``[]`` statt ``None`` -- ``html.py:1356``
    (``_outlook_metrics != []``) schaltet den GESAMTEN Block ab. Der
    AC-10-Teil dieses Tests ist deshalb rot; der AC-11-Teil kann bereits
    heute gruen sein (Regressionsschutz fuer den "bewusst geleert"-Zweig, der
    unveraendert bleiben muss).
    """
    enabled = {"temperature", "wind", "precipitation"}

    # --- AC-10: "humidity"/"uv_index" liegen BEIDE ausserhalb der Grundauswahl.
    dc_ac10 = display_config(
        enabled_ids=enabled, outlook_metrics=["humidity", "uv_index"],
    )
    with caplog.at_level(logging.WARNING):
        rows_ac10 = outlook_rows(trip_display_config=dc_ac10, report_type="evening")
        html_ac10, plain_ac10 = render_trip_mail(dc_ac10, rows_ac10)
    kopf_ac10 = html_outlook_headers(html_ac10)

    assert kopf_ac10, (
        "AC-10 FAIL: der Ausblick-Block ist komplett verschwunden, obwohl "
        "die gespeicherte Auswahl nicht ausdruecklich leer war -- 'unaufloesbar "
        "nach dem Grundauswahl-Schnitt' und 'bewusst geleert' duerfen nie "
        "denselben Zustand erzeugen (M3-Bug, resolve_trip_outlook_metrics() "
        "liefert [] statt None)."
    )
    erwartet = _soll_ueberschriften(enabled)
    assert set(kopf_ac10[1:]) == erwartet, (
        f"AC-10: nach dem Totalschnitt zeigt der Ausblick {kopf_ac10[1:]!r} "
        f"statt der VOLLEN Grundauswahl {sorted(erwartet)!r}."
    )
    warnungen = "\n".join(
        r.getMessage() for r in caplog.records if r.levelno >= logging.WARNING
    )
    assert "humidity" in warnungen or "uv_index" in warnungen, (
        f"AC-10: der Rueckfall auf die Grundauswahl wurde nicht protokolliert "
        f"(logger.warning erwartet). Gesehene Warnungen:\n{warnungen}"
    )

    # --- AC-11: ausdruecklich LEERE Auswahl -- Gegenprobe, muss verschieden bleiben.
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

    # --- Unterscheidbarkeit: AC-10 (Totalschnitt) und AC-11 (bewusst leer)
    # duerfen NICHT dasselbe Ergebnis liefern.
    assert bool(html_outlook_headers(html_ac10)) != bool(html_outlook_headers(html_ac11)), (
        "AC-10 und AC-11 sind nicht unterscheidbar: 'unaufloesbar nach dem "
        "Grundauswahl-Schnitt' (AC-10) und 'bewusst geleert' (AC-11) erzeugen "
        "denselben Zustand -- genau der Fehler, den A2 an der Nachbarstelle "
        "bereits beseitigt hat (compare_outlook_metric_ids.py:91-97)."
    )
