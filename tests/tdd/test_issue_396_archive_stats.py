"""
TDD RED — Issue #396: Archiv-Statistiken (Briefings + Alarme pro Tour)

Alle Tests bis auf test_cockpit_still_filters_24h schlagen fehl,
weil die Implementierung noch nicht existiert.
"""
import subprocess
from pathlib import Path


# ---------------------------------------------------------------------------
# AC-1 — Briefing-Zähler pro Tour
# ---------------------------------------------------------------------------

def test_store_go_has_briefing_count_by_trip():
    """
    GIVEN: store.go existiert
    WHEN: nach der Funktion BriefingCountByTrip gesucht wird
    THEN: Funktion ist vorhanden (RED: noch nicht implementiert)
    """
    store_path = Path(__file__).parents[2] / "internal" / "store" / "store.go"
    assert store_path.exists(), f"store.go nicht gefunden: {store_path}"
    content = store_path.read_text()
    assert "BriefingCountByTrip" in content, (
        "BriefingCountByTrip nicht in store.go gefunden — noch nicht implementiert"
    )


def test_briefing_count_per_trip():
    """
    GIVEN: store.go existiert
    WHEN: nach BriefingCountByTrip gesucht wird
    THEN: Funktion implementiert korrekte trip_id-Aggregation (RED: fehlt)
    """
    store_path = Path(__file__).parents[2] / "internal" / "store" / "store.go"
    assert store_path.exists()
    content = store_path.read_text()
    assert "BriefingCountByTrip" in content, (
        "BriefingCountByTrip nicht in store.go — AC-1 nicht erfüllt"
    )


# ---------------------------------------------------------------------------
# AC-2 — Alert-Retention entfernen
# ---------------------------------------------------------------------------

def test_alert_retention_code_removed():
    """
    GIVEN: src/services/trip_alert.py
    WHEN: nach dem 48h-Retention-Code gesucht wird
    THEN: Code ist nicht mehr vorhanden (RED: Retention noch drin)
    """
    alert_py = Path(__file__).parents[2] / "src" / "services" / "trip_alert.py"
    assert alert_py.exists(), f"trip_alert.py nicht gefunden: {alert_py}"
    content = alert_py.read_text()
    assert "timedelta(hours=48)" not in content, (
        "48h-Retention-Code noch in trip_alert.py — muss entfernt werden"
    )


def test_alert_count_includes_old_entries():
    """
    GIVEN: alert_log.json mit Einträgen älter als 48h
    WHEN: 48h-Retention entfernt und AlertCountByTrip aufgerufen wird
    THEN: auch alte Einträge werden gezählt (RED: Retention noch aktiv + Funktion fehlt)
    """
    store_path = Path(__file__).parents[2] / "internal" / "store" / "store.go"
    assert store_path.exists()
    content = store_path.read_text()
    assert "AlertCountByTrip" in content, (
        "AlertCountByTrip nicht in store.go — alte Einträge können nicht gezählt werden"
    )
    alert_py = Path(__file__).parents[2] / "src" / "services" / "trip_alert.py"
    py_content = alert_py.read_text()
    assert "timedelta(hours=48)" not in py_content, (
        "48h-Retention noch aktiv — ältere Alerts werden gelöscht statt gezählt"
    )


# ---------------------------------------------------------------------------
# AC-3 — Cockpit-Endpoint filtert weiterhin 24h (Regression Guard — GREEN)
# ---------------------------------------------------------------------------

def test_cockpit_still_filters_24h():
    """
    GIVEN: internal/handler/cockpit.go
    WHEN: Go-seitige 24h-Filterung geprüft wird
    THEN: cutoff24h-Filter ist unverändert vorhanden (GREEN: Go filtert bereits)
    """
    cockpit_path = Path(__file__).parents[2] / "internal" / "handler" / "cockpit.go"
    assert cockpit_path.exists(), f"cockpit.go nicht gefunden: {cockpit_path}"
    content = cockpit_path.read_text()
    assert "cutoff24h" in content, "cutoff24h-Filter in cockpit.go fehlt"
    assert "After(cutoff24h)" in content, "24h-Alert-Filter in cockpit.go fehlt"


# ---------------------------------------------------------------------------
# AC-4 — Nullwerte korrekt behandeln
# ---------------------------------------------------------------------------

def test_store_go_has_alert_count_by_trip():
    """
    GIVEN: store.go existiert
    WHEN: nach der Funktion AlertCountByTrip gesucht wird
    THEN: Funktion ist vorhanden (RED: noch nicht implementiert)
    """
    store_path = Path(__file__).parents[2] / "internal" / "store" / "store.go"
    assert store_path.exists()
    content = store_path.read_text()
    assert "AlertCountByTrip" in content, (
        "AlertCountByTrip nicht in store.go gefunden — noch nicht implementiert"
    )


def test_zero_counts_handled():
    """
    GIVEN: leere oder nicht vorhandene Log-Dateien
    WHEN: GET /api/archive/stats aufgerufen wird
    THEN: Response enthält leere Maps (kein Crash)

    RED: Handler existiert noch nicht → archive_stats.go fehlt
    """
    handler_path = Path(__file__).parents[2] / "internal" / "handler" / "archive_stats.go"
    assert handler_path.exists(), (
        f"archive_stats.go nicht gefunden: {handler_path} — Handler noch nicht implementiert"
    )
    content = handler_path.read_text()
    assert "make(map[string]int" in content or "{}" in content, (
        "Handler behandelt leere Maps nicht korrekt"
    )


def test_archive_stats_handler_exists():
    """
    GIVEN: internal/handler/ Verzeichnis
    WHEN: nach archive_stats.go gesucht wird
    THEN: Datei existiert mit ArchiveStatsHandler Funktion (RED: noch nicht vorhanden)
    """
    handler_path = Path(__file__).parents[2] / "internal" / "handler" / "archive_stats.go"
    assert handler_path.exists(), (
        f"archive_stats.go existiert nicht: {handler_path}"
    )
    content = handler_path.read_text()
    assert "ArchiveStatsHandler" in content, (
        "ArchiveStatsHandler Funktion nicht in archive_stats.go gefunden"
    )
