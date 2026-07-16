"""TDD RED — Issue #1270 / Spec docs/specs/modules/compare_channel_preview_dispatch.md

Test 7 (AC-6, ADR-0003): Der neue Compare-Preview-Pfad ist nutzerbezogen. Ein
Preset von Nutzer A darf unter der `user_id` von Nutzer B NICHT aufloesbar
sein — kein Cross-User-Datenleck, kein `"default"`-Fallback.

RED-Grund: `src/services/compare_preview_service.py` existiert nicht →
ModuleNotFoundError.

KEINE Mocks: zwei echte, verschiedene Nutzer-Kontexte mit echten Dateien im
isolierten Daten-Root. Die `ComparisonEngine` wird durch eine echte Subklasse
ersetzt, die JEDEN Lauf als Fehler meldet — im Isolations-Fall darf sie gar
nicht erst erreicht werden, und im Positiv-Fall (Nutzer A, eigenes Preset)
beweist der Zaehler, dass die Aufloesung ueberhaupt bis zur Engine kommt.
"""
from __future__ import annotations

import uuid
from datetime import date, datetime

import pytest

from app.loader import get_data_dir, save_location
from app.models import ForecastDataPoint, ThunderLevel
from app.user import SavedLocation

from tests.helpers.compare_briefings import write_compare_briefings

TARGET_DATE = date(2026, 7, 8)


@pytest.fixture
def two_users(tmp_path, monkeypatch):
    """Zwei echte, verschiedene user_ids im isolierten Daten-Root — niemals
    'default'."""
    from app import loader as app_loader

    data_root = tmp_path / "data"
    data_root.mkdir(parents=True, exist_ok=True)
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(app_loader, "_DATA_ROOT", str(data_root))
    try:
        from src.app import loader as src_loader

        monkeypatch.setattr(src_loader, "_DATA_ROOT", str(data_root))
    except ImportError:  # pragma: no cover
        pass

    suffix = uuid.uuid4().hex[:8]
    return f"tdd-1270-userA-{suffix}", f"tdd-1270-userB-{suffix}"


def _dp(hour: int) -> ForecastDataPoint:
    return ForecastDataPoint(
        ts=datetime(TARGET_DATE.year, TARGET_DATE.month, TARGET_DATE.day, hour, 0),
        t2m_c=22.0, wind_chill_c=21.0, wind10m_kmh=11.0, gust_kmh=19.0,
        precip_1h_mm=0.0, cloud_total_pct=35, uv_index=5.0,
        thunder_level=ThunderLevel.NONE, pop_pct=10, visibility_m=9000,
    )


class _EngineCalls:
    def __init__(self) -> None:
        self.count = 0


def _install_recording_engine(monkeypatch, calls: _EngineCalls) -> None:
    import services.comparison_engine as ce_mod
    from app.user import ComparisonResult, LocationResult

    original = ce_mod.ComparisonEngine

    class RecordingEngine(original):  # echte Subklasse, kein Mock
        @staticmethod
        def run(*args, **kwargs):
            locations = kwargs.get("locations")
            if locations is None and args:
                locations = args[0]
            calls.count += 1
            return ComparisonResult(
                locations=[
                    LocationResult(
                        location=loc, score=90, temp_max=22.0, temp_min=12.0,
                        wind_max=11.0, gust_max=19.0, cloud_avg=35, sunny_hours=6,
                        official_alerts=[], hourly_data=[_dp(9), _dp(12)],
                    )
                    for loc in list(locations or [])
                ],
                time_window=(9, 16),
                target_date=TARGET_DATE,
                created_at=datetime(2026, 7, 8, 4, 0),
            )

    monkeypatch.setattr(ce_mod, "ComparisonEngine", RecordingEngine)
    try:
        import services.compare_preview_service as svc_mod
    except ImportError:
        return  # RED: der Service existiert noch nicht
    if hasattr(svc_mod, "ComparisonEngine"):
        monkeypatch.setattr(svc_mod, "ComparisonEngine", RecordingEngine)


def _seed_user_a(user_a: str) -> str:
    preset_id = "cp-1270-private"
    save_location(
        SavedLocation(id="loc-a", name="Innsbruck", lat=47.27, lon=11.39, elevation_m=574),
        user_id=user_a,
    )
    write_compare_briefings(
        get_data_dir(user_a),
        [{
            "id": preset_id,
            "name": "Privater Vergleich A",
            "user_id": user_a,
            "location_ids": ["loc-a"],
            "schedule": "daily",
            "profil": "ALLGEMEIN",
            "hour_from": 9,
            "hour_to": 16,
            "forecast_hours": 48,
            "empfaenger": ["a@example.invalid"],
            "created_at": "2026-07-01T00:00:00Z",
        }],
    )
    return preset_id


def test_preset_of_user_a_is_not_resolvable_under_user_b(two_users, monkeypatch):
    """GIVEN ein Preset gehoert Nutzer A
    WHEN die Vorschau mit der user_id von Nutzer B angefordert wird
    THEN wird das Preset nicht aufgeloest (Ablehnung/Fehler), und Nutzer B
    bekommt KEINEN Inhalt von Nutzer A zu sehen.

    RED: services.compare_preview_service existiert nicht (ModuleNotFoundError)."""
    user_a, user_b = two_users
    preset_id = _seed_user_a(user_a)
    calls = _EngineCalls()
    _install_recording_engine(monkeypatch, calls)
    from services.compare_preview_service import ComparePreviewService

    with pytest.raises(Exception) as exc:
        result = ComparePreviewService().render_email_preview(
            preset_id, user_id=user_b, target_date=TARGET_DATE.isoformat()
        )
        pytest.fail(
            "AC-6/ADR-0003: Nutzer B konnte die Vorschau des Presets von Nutzer A "
            f"abrufen (Cross-User-Datenleck). Rueckgabe: {str(result)[:300]!r}"
        )

    # pytest.fail() wirft Failed (BaseException) — es wird von
    # pytest.raises(Exception) NICHT gefangen und schlaegt korrekt durch.
    assert "Innsbruck" not in str(exc.value), (
        "Die Ablehnung darf keine Inhalte des fremden Presets durchreichen"
    )
    assert calls.count == 0, (
        "AC-6: Fuer ein fremdes Preset darf gar keine Wetter-Berechnung starten "
        f"— ComparisonEngine.run lief {calls.count}x."
    )


def test_owner_can_preview_own_preset(two_users, monkeypatch):
    """Gegenprobe zur Isolation: unter der ECHTEN user_id des Eigentuemers
    liefert derselbe Aufruf eine normale Vorschau — die Ablehnung oben ist
    also Isolation und nicht generelle Unerreichbarkeit.

    RED: services.compare_preview_service existiert nicht (ModuleNotFoundError)."""
    user_a, _user_b = two_users
    preset_id = _seed_user_a(user_a)
    calls = _EngineCalls()
    _install_recording_engine(monkeypatch, calls)
    from services.compare_preview_service import ComparePreviewService

    html = ComparePreviewService().render_email_preview(
        preset_id, user_id=user_a, target_date=TARGET_DATE.isoformat()
    )

    assert isinstance(html, str) and "Innsbruck" in html, (
        "Der Eigentuemer muss seine eigene Vorschau bekommen, war aber: "
        f"{str(html)[:300]!r}"
    )
    assert calls.count == 1, f"Genau ein Engine-Lauf erwartet, waren {calls.count}"
