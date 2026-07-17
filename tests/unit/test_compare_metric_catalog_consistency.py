"""
Struktureller Guard gegen wiederholtes stilles Verwerfen waehlbarer
Compare-Metriken (#1296, AC-6).

Ohne sichtbares Signal wiederholt sich der Bug-Typ von #1285/#1296 bei der
naechsten neu eingefuehrten Frontend-Metrik ein drittes Mal. Dieser Test haelt
zwei Dinge fest: (a) eine nicht mappbare ID erzeugt ein Log-Warning statt
stiller Verwerfung, (b) der Editor-Katalog (``compareMetricDefs.ts::
ALL_METRICS``, 15 IDs) ist 1:1 auf ``FRONTEND_TO_RENDERER_METRIC_ID``
abgebildet.

Kern-Schicht, deterministisch: kein Mock, kein Netz, kein patch(). Reiner
Konsistenz-Check gegen die Konstanten des Moduls + echtes Logger-Verhalten
(``caplog``, kein gemocktes Logging-Objekt).

SPEC: docs/specs/modules/issue_1296_compare_metrics_dropped.md
"""
from __future__ import annotations

import logging

from output.renderers.compare_metric_ids import (
    FRONTEND_TO_RENDERER_METRIC_ID,
    resolve_enabled_metrics,
)

# Hart hinterlegte Kopie der 15 ``ALL_METRICS``-Keys aus
# frontend/src/lib/components/compare/compareMetricDefs.ts (Zeile 30-58,
# Stand 2026-07-17). Python kann kein TypeScript parsen (CLAUDE.md
# Test-Politik: deterministisch, kein Cross-Language-Tooling) -- bei
# kuenftigen Aenderungen an ALL_METRICS muss diese Kopie von Hand nachgezogen
# werden (dokumentierter Kompromiss, s. Spec Known Limitations).
ALL_METRICS_FRONTEND_IDS: set[str] = {
    "snow_depth_cm",
    "snow_new_sum_cm",
    "sunny_hours_h",
    "wind_max_kmh",
    "cloud_avg_pct",
    "visibility_min_m",
    "precip_sum_mm",
    "uv_index_max",
    "temp_max_c",
    "thunder_level_max",
    "temp_min_c",
    "gust_max_kmh",
    "cape_max_jkg",
    "freezing_level_m",
    "pop_max_pct",
}


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
    """AC-6 (rot vor Fix): JEDE im Editor waehlbare Metrik-ID braucht ein
    Renderer-Mapping -- heute fehlen vier (temp_min_c, gust_max_kmh,
    cape_max_jkg, freezing_level_m). Schlaegt kuenftig auch fehl, sobald eine
    neu eingefuehrte waehlbare Metrik ohne Mapping hinzukommt (struktureller
    Guard).
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
