"""
Tests für Dead-Code-Abbau Scheibe 1 (Issue #1215).
Spec: docs/specs/modules/rework_1215_dead_code_scheibe1.md

Beweisen über echte Imports/Attribut-Zugriffe, dass der Legacy-Block in
weather_metrics.py und das coordinates-Modul entfernt sind — und dass die
aktiven Nachbarn (aggregate_stage, WeatherMetricsService-Kern) unberührt
bleiben. Dateisystem-Prüfungen folgen dem etablierten Muster von
test_web_utils_file_removed (reine Existenz-Prüfung, kein Quelltext-Grep).

TDD RED: Vor der Implementierung schlagen die *_removed/*_archived-Tests
fehl, weil der tote Code noch existiert.
"""
import importlib
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]

LEGACY_MODULE_SYMBOLS = ["HourlyCell", "CloudStatus"]
LEGACY_SERVICE_METHODS = [
    "format_hourly_cell",
    "hourly_cell_to_compact",
    "calculate_cloud_status",
    "format_cloud_status",
    "get_cloud_status_emoji",
]


def test_weather_metrics_legacy_classes_removed():
    """AC-1: HourlyCell und CloudStatus existieren nicht mehr auf Modulebene."""
    mod = importlib.import_module("services.weather_metrics")
    leftover = [s for s in LEGACY_MODULE_SYMBOLS if hasattr(mod, s)]
    assert leftover == [], (
        f"Legacy-Klassen noch in services.weather_metrics vorhanden: {leftover} "
        f"— sollten mit Scheibe 1 (#1215) gelöscht sein (null externe Aufrufer)"
    )


def test_weather_metrics_legacy_methods_removed():
    """AC-1: Die fünf Legacy-Methoden sind aus WeatherMetricsService entfernt."""
    from services.weather_metrics import WeatherMetricsService

    leftover = [m for m in LEGACY_SERVICE_METHODS if hasattr(WeatherMetricsService, m)]
    assert leftover == [], (
        f"Legacy-Methoden noch in WeatherMetricsService vorhanden: {leftover} "
        f"— sollten mit Scheibe 1 (#1215) gelöscht sein (null externe Aufrufer)"
    )


def test_weather_metrics_active_api_intact():
    """AC-1/AC-3 (Schutz gegen Über-Löschung): aggregate_stage und der aktive
    Service-Kern bleiben erhalten — aggregate_stage hat einen echten Nutzer
    (tests/tdd/test_issue_721_email_outlook.py, Confidence-Propagation)."""
    mod = importlib.import_module("services.weather_metrics")
    for name in ["aggregate_stage", "WeatherMetricsService", "get_weather_emoji"]:
        assert hasattr(mod, name), (
            f"services.weather_metrics.{name} fehlt — Über-Löschung! "
            f"Nur der Legacy-Block darf entfernt werden."
        )
    svc = mod.WeatherMetricsService
    for name in ["compute_basis_metrics", "compute_extended_metrics", "calculate_effective_cloud"]:
        assert hasattr(svc, name), (
            f"WeatherMetricsService.{name} fehlt — Über-Löschung des aktiven Kerns!"
        )


def test_coordinates_module_removed():
    """AC-2: services.coordinates existiert nicht mehr (weder Import noch Datei)."""
    with pytest.raises(ModuleNotFoundError):
        importlib.import_module("services.coordinates")

    coords_path = REPO / "src" / "services" / "coordinates.py"
    assert not coords_path.exists(), (
        f"{coords_path} existiert noch — einziger Importer war der Struktur-Test "
        f"test_coordinates_module (mit Scheibe 1 entfernt)"
    )


def test_red_artifact_file_removed():
    """AC-4: RED-Protokoll red_839_fmt_val_thresholds.txt liegt nicht mehr im Repo-Root."""
    assert not (REPO / "red_839_fmt_val_thresholds.txt").exists(), (
        "red_839_fmt_val_thresholds.txt liegt noch im Repo-Root — "
        "Altlast eines abgeschlossenen Workflows, gehört gelöscht (#1215)"
    )


def test_design_mockups_archived():
    """AC-5: atoms.jsx/brand-kit.jsx sind aus dem Repo-Root ins Design-Archiv
    umgezogen und dort per README als eingefroren gekennzeichnet."""
    archive = REPO / "docs" / "design-requests" / "archive"
    for name in ["atoms.jsx", "brand-kit.jsx"]:
        assert not (REPO / name).exists(), (
            f"{name} liegt noch im Repo-Root — sollte nach {archive} verschoben sein"
        )
        assert (archive / name).exists(), (
            f"{archive / name} fehlt — Verschiebe-Ziel aus AC-5"
        )

    readme = archive / "README.md"
    assert readme.exists(), f"{readme} fehlt — AC-5 verlangt Einfroren-Notiz"
    content = readme.read_text(encoding="utf-8")  # doc-compliance-test
    for name in ["atoms.jsx", "brand-kit.jsx"]:
        assert name in content, (
            f"README im Design-Archiv erwähnt {name} nicht als eingefroren"
        )
