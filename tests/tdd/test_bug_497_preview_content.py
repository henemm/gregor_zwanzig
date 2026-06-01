"""TDD RED — Issue #497: Trip/Preview ist inhaltlich falsch.

Spec: docs/specs/modules/bug_497_preview_content.md

Zwei Bugs:
  Bug 1: preview_service.py:151 — `.replace(":", "")` kürzt "KHW_10: von Egger..."
         auf "KHW_10 von" statt "KHW_10" (korrekt: `.split(":", 1)[0]`)
  Bug 2: FixtureProvider liefert None für cloud_low_pct, pop_pct, snowfall_limit_m,
         wind_direction_deg — diese Felder fehlen in den Fixture-JSONs + im Mapping.

Kein Mocking. GZ_TEST_FIXTURE_DIR wird von conftest.py autouse gesetzt.
"""
from __future__ import annotations

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
FIXTURE_DIR = str(REPO_ROOT / "fixtures" / "openmeteo")

_KHW_USER = "henning"
_KHW_TRIP = "5f534011"
_KHW_STAGE_DATE = "2026-05-31"  # KHW_10: von Egger Alm nach Dolinza Alm


# ---------------------------------------------------------------------------
# AC-1 — SMS-Präfix: Stage-Name mit "ID: Beschreibung"-Format
# ---------------------------------------------------------------------------


def test_ac1_sms_prefix_uses_id_before_colon():
    """
    GIVEN Trip KHW 403, Stage "KHW_10: von Egger Alm nach Dolinza Alm" (2026-05-31)
    WHEN render_sms_preview() aufgerufen wird (Demo-Modus via conftest GZ_TEST_FIXTURE_DIR)
    THEN muss die token_line mit "KHW_10:" beginnen — nicht mit "KHW_10 von:"

    RED-Ursache: preview_service.py:151 nutzt .replace(":", "").strip() →
    "KHW_10 von Egger Alm..." → _sanitize_stage_name → "KHW_10 von" (10 Zeichen)
    """
    from services.preview_service import PreviewService

    _, token_line = PreviewService().render_sms_preview(
        _KHW_TRIP,
        user_id=_KHW_USER,
        target_date=_KHW_STAGE_DATE,
    )

    # Format-basierte Prüfung (stage-agnostisch):
    # Mit Bug `.replace(":", "")` enthält der Präfix Leerzeichen ("KHW_10 von" / "KHW_00a Vo").
    # Mit Fix `.split(":", 1)[0]` ist der Präfix nur die Stage-ID ohne Leerzeichen.
    assert token_line.count(":") >= 1, (
        f"token_line muss mindestens ein ':' enthalten (Stage-Präfix-Separator).\n"
        f"  Bekommen: '{token_line[:40]}'"
    )
    prefix = token_line.split(":", 1)[0]
    assert " " not in prefix, (
        f"SMS-Präfix enthält Leerzeichen — Stage-Name wurde nicht korrekt bei ':' getrennt.\n"
        f"  Präfix: '{prefix}' (sollte nur Stage-ID ohne Leerzeichen sein, z.B. 'KHW_10')\n"
        f"  Bug: .replace(':', '') entfernt Trennzeichen vor dem 10-Zeichen-Schnitt.\n"
        f"  Fix: .split(':', 1)[0] extrahiert korrekt nur den Teil vor dem ersten Doppelpunkt."
    )


# ---------------------------------------------------------------------------
# AC-2 — FixtureProvider: cloud_low_pct nicht None
# ---------------------------------------------------------------------------


def test_ac2_fixture_provides_cloud_low_pct():
    """
    GIVEN FixtureProvider mit den fixtures/openmeteo/*.json Dateien
    WHEN fetch_forecast() für einen alpinen Standort aufgerufen wird
    THEN muss data[0].cloud_low_pct einen Integer-Wert (0–100) liefern, nicht None.

    RED-Ursache: Fixture-JSONs enthalten kein cloud_low_pct-Feld,
    fixture.py mappt es nicht → ForecastDataPoint.cloud_low_pct = None.
    """
    from app.config import Location
    from providers.fixture import FixtureProvider

    provider = FixtureProvider(FIXTURE_DIR)
    loc = Location(latitude=47.2692, longitude=11.4041, name="Innsbruck")
    ts = provider.fetch_forecast(loc)

    assert ts.data[0].cloud_low_pct is not None, (
        "cloud_low_pct ist None — FixtureProvider mappt dieses Feld nicht.\n"
        "Fix: cloud_low_pct in fixtures/*.json ergänzen + Mapping in fixture.py."
    )
    assert 0 <= ts.data[0].cloud_low_pct <= 100, (
        f"cloud_low_pct außerhalb 0–100: {ts.data[0].cloud_low_pct}"
    )


# ---------------------------------------------------------------------------
# AC-3 — FixtureProvider: pop_pct (Regenwahrscheinlichkeit) nicht None
# ---------------------------------------------------------------------------


def test_ac3_fixture_provides_pop_pct():
    """
    GIVEN FixtureProvider mit den fixtures/openmeteo/*.json Dateien
    WHEN fetch_forecast() für einen alpinen Standort aufgerufen wird
    THEN muss data[0].pop_pct einen Integer-Wert (0–100) liefern, nicht None.

    RED-Ursache: Fixture-JSONs enthalten kein pop_pct-Feld,
    fixture.py mappt es nicht → ForecastDataPoint.pop_pct = None.
    """
    from app.config import Location
    from providers.fixture import FixtureProvider

    provider = FixtureProvider(FIXTURE_DIR)
    loc = Location(latitude=47.2692, longitude=11.4041, name="Innsbruck")
    ts = provider.fetch_forecast(loc)

    assert ts.data[0].pop_pct is not None, (
        "pop_pct (Regenwahrscheinlichkeit) ist None — FixtureProvider mappt dieses Feld nicht.\n"
        "Fix: pop_pct in fixtures/*.json ergänzen + Mapping in fixture.py."
    )
    assert 0 <= ts.data[0].pop_pct <= 100, (
        f"pop_pct außerhalb 0–100: {ts.data[0].pop_pct}"
    )


# ---------------------------------------------------------------------------
# AC-4 — FixtureProvider: snowfall_limit_m (Schneefallgrenze) nicht None
# ---------------------------------------------------------------------------


def test_ac4_fixture_provides_snowfall_limit_m():
    """
    GIVEN FixtureProvider mit den fixtures/openmeteo/*.json Dateien
    WHEN fetch_forecast() für einen alpinen Standort aufgerufen wird
    THEN muss data[0].snowfall_limit_m einen Integer-Wert (>0) liefern, nicht None.

    RED-Ursache: Fixture-JSONs enthalten kein snowfall_limit_m-Feld,
    fixture.py mappt es nicht → ForecastDataPoint.snowfall_limit_m = None.
    """
    from app.config import Location
    from providers.fixture import FixtureProvider

    provider = FixtureProvider(FIXTURE_DIR)
    loc = Location(latitude=47.2692, longitude=11.4041, name="Innsbruck")
    ts = provider.fetch_forecast(loc)

    assert ts.data[0].snowfall_limit_m is not None, (
        "snowfall_limit_m (Schneefallgrenze) ist None — FixtureProvider mappt dieses Feld nicht.\n"
        "Fix: snowfall_limit_m in fixtures/*.json ergänzen + Mapping in fixture.py."
    )
    assert ts.data[0].snowfall_limit_m > 0, (
        f"snowfall_limit_m soll > 0 sein (alpine Höhe), war {ts.data[0].snowfall_limit_m}"
    )


# ---------------------------------------------------------------------------
# AC-5 — FixtureProvider: wind_direction_deg (Windrichtung) nicht None
# ---------------------------------------------------------------------------


def test_ac5_fixture_provides_wind_direction_deg():
    """
    GIVEN FixtureProvider mit den fixtures/openmeteo/*.json Dateien
    WHEN fetch_forecast() für einen alpinen Standort aufgerufen wird
    THEN muss data[0].wind_direction_deg einen Integer-Wert (0–359) liefern, nicht None.

    RED-Ursache: Fixture-JSONs enthalten kein wind_dir_deg-Feld,
    fixture.py mappt es nicht → ForecastDataPoint.wind_direction_deg = None.
    """
    from app.config import Location
    from providers.fixture import FixtureProvider

    provider = FixtureProvider(FIXTURE_DIR)
    loc = Location(latitude=47.2692, longitude=11.4041, name="Innsbruck")
    ts = provider.fetch_forecast(loc)

    assert ts.data[0].wind_direction_deg is not None, (
        "wind_direction_deg (Windrichtung) ist None — FixtureProvider mappt dieses Feld nicht.\n"
        "Fix: wind_dir_deg in fixtures/*.json ergänzen + Mapping in fixture.py."
    )
    assert 0 <= ts.data[0].wind_direction_deg <= 359, (
        f"wind_direction_deg außerhalb 0–359: {ts.data[0].wind_direction_deg}"
    )
