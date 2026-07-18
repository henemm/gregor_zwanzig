"""FixtureProvider: alpine Zusatzfelder werden aus fixtures/openmeteo/*.json gemappt.

Herkunft: diese vier Tests (ac2-ac5) stammen aus dem geloeschten
`tests/tdd/test_bug_497_preview_content.py` (Issue #497) und wurden im Zuge
von Fix-1306-Adversary-Finding F001 hierher ueberfuehrt (#1306-F001). Der
fuenfte Test aus der Ursprungsdatei (ac1, SMS-Praefix-Split) blieb bewusst
geloescht -- lt. ADR-Rationale Punkt 2 in
docs/specs/modules/fix_1306_mail_render_bundle.md ("Befund 4: SMS-Praefix ...")
prueft er ein durch #1260-v2.0-Design und Codepfad-Entfernung (#954) bereits
zweifach ueberholtes Verhalten, kein RED-Bug mehr.

Diese vier Tests waren VOR der Loeschung gruen (Codepfad lebt weiterhin:
src/providers/fixture.py:131-134 mappt cloud_low_pct/pop_pct/snowfall_limit_m/
wind_dir_deg aus den Fixture-JSONs). Sie pruefen daher kein RED-Verhalten mehr,
sondern sind Regressionsschutz fuer das Fixture->Model-Feld-Mapping.

Kein Mocking: echte FixtureProvider-Instanz gegen die versionierten
fixtures/openmeteo/*.json-Dateien (GZ_TEST_FIXTURE_DIR wird von
tests/conftest.py autouse gesetzt, hier zusaetzlich der reale Repo-Pfad
direkt uebergeben -- unabhaengig vom Env-Var, wie im Original).
"""
from __future__ import annotations

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
FIXTURE_DIR = str(REPO_ROOT / "fixtures" / "openmeteo")


def test_fixture_provider_maps_cloud_low_pct():
    """
    GIVEN FixtureProvider mit den fixtures/openmeteo/*.json Dateien
    WHEN fetch_forecast() fuer einen alpinen Standort aufgerufen wird
    THEN muss data[0].cloud_low_pct einen Integer-Wert (0-100) liefern, nicht None.
    """
    from app.config import Location
    from providers.fixture import FixtureProvider

    provider = FixtureProvider(FIXTURE_DIR)
    loc = Location(latitude=47.2692, longitude=11.4041, name="Innsbruck")
    ts = provider.fetch_forecast(loc)

    assert ts.data[0].cloud_low_pct is not None, (
        "cloud_low_pct ist None - FixtureProvider mappt dieses Feld nicht.\n"
        "Fix: cloud_low_pct in fixtures/*.json ergaenzen + Mapping in fixture.py."
    )
    assert 0 <= ts.data[0].cloud_low_pct <= 100, (
        f"cloud_low_pct ausserhalb 0-100: {ts.data[0].cloud_low_pct}"
    )


def test_fixture_provider_maps_pop_pct():
    """
    GIVEN FixtureProvider mit den fixtures/openmeteo/*.json Dateien
    WHEN fetch_forecast() fuer einen alpinen Standort aufgerufen wird
    THEN muss data[0].pop_pct (Regenwahrscheinlichkeit) einen Integer-Wert
         (0-100) liefern, nicht None.
    """
    from app.config import Location
    from providers.fixture import FixtureProvider

    provider = FixtureProvider(FIXTURE_DIR)
    loc = Location(latitude=47.2692, longitude=11.4041, name="Innsbruck")
    ts = provider.fetch_forecast(loc)

    assert ts.data[0].pop_pct is not None, (
        "pop_pct (Regenwahrscheinlichkeit) ist None - FixtureProvider mappt "
        "dieses Feld nicht.\n"
        "Fix: pop_pct in fixtures/*.json ergaenzen + Mapping in fixture.py."
    )
    assert 0 <= ts.data[0].pop_pct <= 100, (
        f"pop_pct ausserhalb 0-100: {ts.data[0].pop_pct}"
    )


def test_fixture_provider_maps_snowfall_limit_m():
    """
    GIVEN FixtureProvider mit den fixtures/openmeteo/*.json Dateien
    WHEN fetch_forecast() fuer einen alpinen Standort aufgerufen wird
    THEN muss data[0].snowfall_limit_m (Schneefallgrenze) einen Integer-Wert
         (>0) liefern, nicht None.
    """
    from app.config import Location
    from providers.fixture import FixtureProvider

    provider = FixtureProvider(FIXTURE_DIR)
    loc = Location(latitude=47.2692, longitude=11.4041, name="Innsbruck")
    ts = provider.fetch_forecast(loc)

    assert ts.data[0].snowfall_limit_m is not None, (
        "snowfall_limit_m (Schneefallgrenze) ist None - FixtureProvider mappt "
        "dieses Feld nicht.\n"
        "Fix: snowfall_limit_m in fixtures/*.json ergaenzen + Mapping in fixture.py."
    )
    assert ts.data[0].snowfall_limit_m > 0, (
        f"snowfall_limit_m soll > 0 sein (alpine Hoehe), war {ts.data[0].snowfall_limit_m}"
    )


def test_fixture_provider_maps_wind_direction_deg():
    """
    GIVEN FixtureProvider mit den fixtures/openmeteo/*.json Dateien
    WHEN fetch_forecast() fuer einen alpinen Standort aufgerufen wird
    THEN muss data[0].wind_direction_deg (Windrichtung) einen Integer-Wert
         (0-359) liefern, nicht None.
    """
    from app.config import Location
    from providers.fixture import FixtureProvider

    provider = FixtureProvider(FIXTURE_DIR)
    loc = Location(latitude=47.2692, longitude=11.4041, name="Innsbruck")
    ts = provider.fetch_forecast(loc)

    assert ts.data[0].wind_direction_deg is not None, (
        "wind_direction_deg (Windrichtung) ist None - FixtureProvider mappt "
        "dieses Feld nicht.\n"
        "Fix: wind_dir_deg in fixtures/*.json ergaenzen + Mapping in fixture.py."
    )
    assert 0 <= ts.data[0].wind_direction_deg <= 359, (
        f"wind_direction_deg ausserhalb 0-359: {ts.data[0].wind_direction_deg}"
    )
