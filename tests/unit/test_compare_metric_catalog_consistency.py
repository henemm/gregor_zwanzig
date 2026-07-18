"""
Struktureller Guard gegen wiederholtes stilles Verwerfen waehlbarer
Compare-Metriken (#1296, AC-6; gehaertet #1298, B3).

Ohne sichtbares Signal wiederholt sich der Bug-Typ von #1285/#1296 bei der
naechsten neu eingefuehrten Frontend-Metrik ein drittes Mal. Dieser Test haelt
zwei Dinge fest: (a) eine nicht mappbare ID erzeugt ein Log-Warning statt
stiller Verwerfung, (b) der Editor-Katalog (``compareMetricDefs.ts::
ALL_METRICS``, 15 IDs) ist 1:1 auf ``FRONTEND_TO_RENDERER_METRIC_ID``
abgebildet.

Issue #1298 (B3): die urspruengliche Fassung hielt die 15 IDs als von Hand
gepflegte Kopie -- bei einer 16. Metrik ohne Nachpflege blieb der Test
faelschlich gruen. Seit der Haertung liest ``_ts_metric_parser.
parse_all_metrics_ids()`` die IDs direkt aus der echten
``compareMetricDefs.ts`` (Vakuum-Schutz: der Parser muss auf der realen
Datei nachweislich alle 15 IDs finden, nicht 0).

Kern-Schicht, deterministisch: kein Mock, kein Netz, kein patch(). Reiner
Konsistenz-Check gegen die Konstanten des Moduls + echtes Logger-Verhalten
(``caplog``, kein gemocktes Logging-Objekt).

SPEC: docs/specs/modules/issue_1296_compare_metrics_dropped.md
SPEC: docs/specs/modules/issue_1298_compare_metric_guard_cape_label.md
"""
from __future__ import annotations

import logging

import pytest

from output.renderers.compare_metric_ids import (
    FRONTEND_TO_RENDERER_METRIC_ID,
    resolve_enabled_metrics,
)

from _ts_metric_parser import COMPARE_METRIC_DEFS_TS, parse_all_metrics_ids

# Issue #1298 (B3): ersetzt die vormalige Hand-Kopie der 15 IDs -- die Menge
# wird jetzt live aus der echten compareMetricDefs.ts gelesen (siehe
# _ts_metric_parser), kann also nicht mehr veralten.
ALL_METRICS_FRONTEND_IDS: set[str] = set(parse_all_metrics_ids())


def test_unmapped_metric_logs_warning_instead_of_silent_drop(caplog):
    """AC-6 (rot vor Fix): ``resolve_enabled_metrics()`` verwirft eine nicht
    mappbare ID heute kommentarlos -- kein Log-Warning wird erzeugt.
    """
    with caplog.at_level(logging.WARNING):
        resolve_enabled_metrics(["nicht_gemappte_id_xyz"])

    warnings = [r for r in caplog.records if r.levelno >= logging.WARNING]
    assert warnings, (
        "resolve_enabled_metrics() verwirft eine nicht mappbare ID heute "
        "kommentarlos -- kein Log-Warning erzeugt (AC-6 struktureller Guard "
        "fehlt)."
    )
    assert any("nicht_gemappte_id_xyz" in r.getMessage() for r in warnings), (
        f"Kein Warning nennt die verworfene ID 'nicht_gemappte_id_xyz': "
        f"{[r.getMessage() for r in warnings]}"
    )


def test_all_frontend_metric_ids_have_renderer_mapping():
    """AC-6: JEDE im Editor waehlbare Metrik-ID braucht ein
    Renderer-Mapping. Schlaegt fehl, sobald eine neu eingefuehrte waehlbare
    Metrik ohne Mapping hinzukommt (struktureller Guard) -- die Menge kommt
    seit #1298 (B3) live aus der echten ``compareMetricDefs.ts``, nicht mehr
    aus einer Hand-Kopie.
    """
    mapped = set(FRONTEND_TO_RENDERER_METRIC_ID.keys())
    missing = ALL_METRICS_FRONTEND_IDS - mapped
    assert not missing, (
        f"Editor-waehlbare Metrik-IDs ohne Renderer-Mapping (werden still "
        f"verworfen statt angezeigt): {sorted(missing)}"
    )
    orphaned = mapped - ALL_METRICS_FRONTEND_IDS
    assert not orphaned, (
        f"FRONTEND_TO_RENDERER_METRIC_ID enthaelt Eintraege, die nicht in "
        f"ALL_METRICS stehen (verwaistes Mapping, hart hinterlegte Kopie "
        f"veraltet?): {sorted(orphaned)}"
    )


def test_ts_parser_finds_all_15_ids_on_real_file():
    """AC-2 Vakuum-Schutz (rot vor Fix: ``_ts_metric_parser`` existiert noch
    nicht -- ImportError). Der Parser muss auf der ECHTEN
    ``compareMetricDefs.ts`` nachweislich alle 15 IDs finden -- ein
    kaputter/leerer Parser (0 IDs) duerfte den Waechter oben sonst
    faelschlich immer gruen erscheinen lassen, weil eine leere Menge nie
    eine fehlende ID entdeckt.
    """
    assert COMPARE_METRIC_DEFS_TS.exists(), (
        f"Erwarteter Pfad zu compareMetricDefs.ts existiert nicht: "
        f"{COMPARE_METRIC_DEFS_TS}"
    )
    ids = parse_all_metrics_ids()
    assert len(ids) == 15, (
        f"Parser fand {len(ids)} IDs statt 15 auf der echten Datei -- "
        f"Vakuum-Schutz-Verdacht (kaputtes Format oder falscher Pfad): {ids}"
    )
    assert len(ids) == len(set(ids)), f"Parser liefert Duplikate: {ids}"


def test_guard_actually_fails_when_a_16th_metric_has_no_mapping():
    """AC-2 Wirkungsnachweis (rot vor Fix: ``_ts_metric_parser`` existiert
    noch nicht -- ImportError). Haelt den Kern-Vergleich aus
    ``test_all_frontend_metric_ids_have_renderer_mapping`` gegen eine
    KUENSTLICH um ein Mapping reduzierte Kopie von
    ``FRONTEND_TO_RENDERER_METRIC_ID`` -- simuliert eine 16. waehlbare
    Metrik, die (wie bei #1285/#1296) kein Renderer-Mapping bekommen hat.
    Der Guard muss dafuer tatsaechlich rot werden, nicht nur zufaellig gruen
    bleiben.
    """
    real_ids = parse_all_metrics_ids()
    assert real_ids, "Vorbedingung: Parser liefert IDs (s. Vakuum-Schutz-Test)."

    incomplete_mapping = dict(FRONTEND_TO_RENDERER_METRIC_ID)
    del incomplete_mapping[real_ids[0]]

    missing = set(real_ids) - set(incomplete_mapping.keys())
    assert missing == {real_ids[0]}, (
        f"Guard-Vergleich erkennt die kuenstlich entfernte ID "
        f"'{real_ids[0]}' nicht als fehlend -- Wirkungsnachweis "
        f"fehlgeschlagen: missing={missing}"
    )

    # Wirkungsnachweis: derselbe Assert-Ausdruck wie im echten Guard-Test
    # (test_all_frontend_metric_ids_have_renderer_mapping) muss gegen das
    # kuenstlich reduzierte Mapping tatsaechlich einen AssertionError werfen.
    with pytest.raises(AssertionError):
        assert not missing, (
            f"Editor-waehlbare Metrik-IDs ohne Renderer-Mapping (werden still "
            f"verworfen statt angezeigt): {sorted(missing)}"
        )
