"""Katalog-Oberflaeche rund um ``aggregations`` nach #1728 Scheibe 3 (AC-7).

Spec: ``docs/specs/modules/feat_1728_s3_aggregations_cleanup.md`` — AC-7
(DEC-3, korrigiert).

Zwei Zusicherungen mit gegenlaeufiger Richtung, absichtlich in EINER Datei:

1. ``pill_default_aggregations()`` ist die einzige echte Leiche im
   API-Cluster (verifiziert 0 Aufrufer) und wird entfernt — der Import muss
   danach scheitern. **Heute rot**, die Funktion existiert noch.
2. ``available_aggregations()`` BLEIBT — sie versorgt ueber den
   ``aggregations``-Array von ``GET /api/metrics`` den Alarme-Reiter
   (``tripAlertMetricsFromCatalog.ts`` liest ``alert_metric`` je Auswertung).
   Das Kontext-Dokument wollte sie mitentfernen; das waere ein echter
   Regress gewesen. Diese Haelfte ist heute gruen und muss es bleiben.

Kern-Schicht, deterministisch: reine Katalog-Auswertung auf der echten
Registry, kein ``Mock()``, kein ``patch()``, kein Netz.
"""
from __future__ import annotations

import importlib

import pytest


def test_pill_default_aggregations_ist_entfernt():
    """AC-7 GIVEN ``src/app/metric_catalog.py`` nach Scheibe 3
    WHEN ``from app.metric_catalog import pill_default_aggregations``
    THEN schlaegt der Import mit ``ImportError`` fehl — die Funktion hat
    repo-weit keinen Aufrufer mehr und ist mit DEC-3 geloescht."""
    with pytest.raises(ImportError):
        from app.metric_catalog import pill_default_aggregations  # noqa: F401

    modul = importlib.import_module("app.metric_catalog")
    assert not hasattr(modul, "pill_default_aggregations"), (
        "``pill_default_aggregations`` existiert noch als Modul-Attribut — "
        "DEC-3 verlangt die vollstaendige Entfernung der Funktion "
        "(0 Aufrufer in src/, api/, frontend/src, tests/)."
    )


def test_available_aggregations_bleibt_erhalten():
    """AC-7 Gegenrichtung GIVEN dieselbe Datei
    WHEN ``available_aggregations("temperature")`` aufgerufen wird
    THEN liefert sie weiterhin die berechenbaren Auswertungen — sie traegt
    seit S1/S2 ausschliesslich die Alarm-Identitaets-Aufloesung des
    Alarme-Reiters und darf NICHT mitentfernt werden (DEC-3-Korrektur)."""
    from app.metric_catalog import available_aggregations

    ist = available_aggregations("temperature")
    assert "min" in ist and "max" in ist, (
        f"``available_aggregations('temperature')`` liefert {ist!r} — der "
        f"Alarme-Reiter leitet daraus ueber GET /api/metrics die "
        f"Alarm-Identitaeten (temperature_min/_max) ab."
    )
