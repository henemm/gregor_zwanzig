"""TDD: Issue #346 — Python Fixture-Provider erzwingt Offline-Tests.

Spec: docs/specs/modules/issue_346_fixture_provider_e2e.md
Test-Manifest: docs/specs/tests/issue_346_fixture_provider_tests.md

KEINE Mocks. Echter FixtureProvider gegen die echten fixtures/openmeteo/*.json,
echter PreviewService gegen einen echten Trip aus data/users. monkeypatch wird
nur für ENV-Var-Isolation und Umleitung des Diagnose-Log-Pfads genutzt (etabliert
in test_bug_338) — kein Mock von Geschäftslogik oder HTTP.
"""
from __future__ import annotations

import json
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
FIXTURE_DIR = str(REPO_ROOT / "fixtures" / "openmeteo")


def _find_test_trip() -> tuple[str | None, str | None]:
    """Ersten vorhandenen echten Trip finden (Alpen bevorzugt für Plausibilität)."""
    from app.loader import get_trips_dir

    for uid, tid in (("henning", "5f534011"), ("default", "gr221-mallorca")):
        if (get_trips_dir(uid) / f"{tid}.json").exists():
            return uid, tid
    return None, None


# ---------- AC-1: Protocol-Erfüllung ----------

def test_ac1_fixture_provider_satisfies_protocol():
    """AC-1: FixtureProvider erfüllt das WeatherProvider-Protocol strukturell."""
    from providers.base import WeatherProvider
    from providers.fixture import FixtureProvider

    provider = FixtureProvider(FIXTURE_DIR)
    assert isinstance(provider, WeatherProvider), \
        "FixtureProvider muss das @runtime_checkable WeatherProvider-Protocol erfüllen"
    assert provider.name == "openmeteo", \
        "name soll 'openmeteo' sein (transparent für Aufrufer)"


# ---------- AC-2: Fixture-Aktivierung bei gesetzter ENV-Var ----------

def test_ac2_get_provider_returns_fixture_when_env_set(monkeypatch):
    """AC-2: Bei gesetztem GZ_TEST_FIXTURE_DIR liefert get_provider() FixtureProvider."""
    monkeypatch.setenv("GZ_TEST_FIXTURE_DIR", FIXTURE_DIR)
    from providers.base import get_provider
    from providers.fixture import FixtureProvider

    provider = get_provider("openmeteo")
    assert isinstance(provider, FixtureProvider), \
        f"Erwartete FixtureProvider bei gesetzter ENV-Var, sah {type(provider).__name__}"


# ---------- AC-3: Prod-Schutz ohne ENV-Var ----------

def test_ac3_get_provider_returns_real_when_env_unset(monkeypatch):
    """AC-3: Ohne GZ_TEST_FIXTURE_DIR liefert get_provider() den echten OpenMeteoProvider."""
    monkeypatch.delenv("GZ_TEST_FIXTURE_DIR", raising=False)
    from providers.base import get_provider
    from providers.openmeteo import OpenMeteoProvider

    provider = get_provider("openmeteo")
    assert isinstance(provider, OpenMeteoProvider), \
        f"Prod-Pfad: erwartete OpenMeteoProvider, sah {type(provider).__name__}"


# ---------- AC-4: Offline-Fetch mit 72 Punkten ----------

def test_ac4_fetch_forecast_offline_72_points():
    """AC-4: fetch_forecast liefert NormalizedTimeseries mit 72 Punkten, offline."""
    from app.config import Location
    from providers.fixture import FixtureProvider

    provider = FixtureProvider(FIXTURE_DIR)
    loc = Location(latitude=47.2692, longitude=11.4041, name="Innsbruck")
    ts = provider.fetch_forecast(loc)

    assert ts is not None, "fetch_forecast darf nicht None liefern"
    assert len(ts.data) == 72, f"Erwartete 72 Datenpunkte, sah {len(ts.data)}"
    assert ts.data[0].t2m_c is not None, "t2m_c muss aus der Fixture gemappt sein"


# ---------- AC-5: Timestamp-Verankerung am aktuellen UTC-Tag ----------

def test_ac5_timestamps_restamped_to_today():
    """AC-5: Timestamps werden auf den aktuellen UTC-Tag verankert (1h-Inkrement)."""
    from app.config import Location
    from providers.fixture import FixtureProvider

    provider = FixtureProvider(FIXTURE_DIR)
    loc = Location(latitude=47.2692, longitude=11.4041, name="Innsbruck")
    ts = provider.fetch_forecast(loc)

    today0 = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
    assert ts.data[0].ts == today0, \
        f"data[0].ts soll heute 00:00 UTC sein, sah {ts.data[0].ts}"
    assert ts.data[1].ts == today0 + timedelta(hours=1), \
        f"data[1].ts soll heute 01:00 UTC sein, sah {ts.data[1].ts}"


# ---------- AC-6: PreviewService rendert ohne echten Open-Meteo-Call ----------

def test_ac6_preview_renders_without_real_api_call(monkeypatch, tmp_path):
    """AC-6: render_email_preview läuft mit gesetzter ENV-Var offline (kein open-meteo-Call)."""
    uid, tid = _find_test_trip()
    if not uid:
        pytest.skip("Kein echter Test-Trip in data/users vorhanden")

    monkeypatch.setenv("GZ_TEST_FIXTURE_DIR", FIXTURE_DIR)

    # Diagnose-Log auf tmp_path umleiten. Maßgeblich ist providers.openmeteo.
    # DIAGNOSTICS_PATH — _log_api_call spiegelt diesen Pfad vor dem Delegieren an
    # call_log (openmeteo.py:415-422). call_log zusätzlich patchen (defensive).
    import providers.openmeteo as om
    import providers.call_log as cl
    log_path = tmp_path / "openmeteo_calls.jsonl"
    monkeypatch.setattr(om, "DIAGNOSTICS_PATH", log_path, raising=False)
    monkeypatch.setattr(cl, "DIAGNOSTICS_PATH", log_path, raising=False)

    from services.preview_service import PreviewService

    html = PreviewService().render_email_preview(tid, user_id=uid, report_type="morning")
    assert html and "<" in html, "Vorschau muss nicht-leeres HTML liefern"

    # Beweis: kein einziger Abruf gegen die echte Open-Meteo-API
    if log_path.exists():
        entries = [json.loads(l) for l in log_path.read_text().splitlines() if l.strip()]
        om_calls = [e for e in entries if "open-meteo" in (e.get("endpoint") or "").lower()]
        assert not om_calls, \
            f"Vorschau darf KEINE echten Open-Meteo-Calls auslösen, sah {len(om_calls)}: {om_calls[:3]}"


# ---------- conftest-Mechanismus: Default-Test bekommt Fixture-Modus ----------

def test_conftest_sets_fixture_dir_for_normal_tests():
    """AC-6 (conftest): Ein normaler Test läuft automatisch im Fixture-Modus.

    KEIN eigenes setenv — prüft, dass die autouse-Fixture in tests/conftest.py
    GZ_TEST_FIXTURE_DIR setzt.
    """
    assert os.environ.get("GZ_TEST_FIXTURE_DIR"), \
        "conftest soll GZ_TEST_FIXTURE_DIR für normale Tests automatisch setzen"


# ---------- AC-7: live-Marker deaktiviert den Fixture-Modus ----------

@pytest.mark.live
def test_ac7_live_marker_disables_fixture_mode():
    """AC-7: Ein @pytest.mark.live-Test läuft OHNE Fixture-Modus (echte API erlaubt).

    KEIN eigenes setenv — prüft, dass die conftest-autouse-Fixture die ENV-Var
    für live-markierte Tests entfernt.
    """
    assert not os.environ.get("GZ_TEST_FIXTURE_DIR"), \
        "Bei @pytest.mark.live darf GZ_TEST_FIXTURE_DIR NICHT gesetzt sein"


# ---------- F001: Whitespace-ENV-Var aktiviert den Fixture-Modus NICHT ----------

def test_f001_whitespace_env_does_not_activate_fixture(monkeypatch):
    """F001: Whitespace-only GZ_TEST_FIXTURE_DIR fällt auf Prod-Verhalten zurück."""
    monkeypatch.setenv("GZ_TEST_FIXTURE_DIR", "   ")
    from providers.base import get_provider
    from providers.openmeteo import OpenMeteoProvider

    provider = get_provider("openmeteo")
    assert isinstance(provider, OpenMeteoProvider), \
        f"Whitespace-ENV darf Fixture nicht aktivieren, sah {type(provider).__name__}"


# ---------- F002: Fehlende "data" in Fixture-JSON wirft ProviderError ----------

def test_f002_malformed_fixture_missing_data_raises(tmp_path):
    """F002: Fixture-JSON ohne "data"-Key liefert keine 0-Punkte-Timeseries, sondern ProviderError."""
    from app.config import Location
    from providers.base import ProviderError
    from providers.fixture import FixtureProvider

    (tmp_path / "innsbruck.json").write_text(
        json.dumps({"timezone": "UTC", "meta": {}})
    )
    provider = FixtureProvider(str(tmp_path))
    loc = Location(latitude=47.2692, longitude=11.4041, name="Innsbruck")
    with pytest.raises(ProviderError):
        provider.fetch_forecast(loc)
