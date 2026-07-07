"""TDD RED — Issue #1034: Official Alerts Fundament (Modell, Registry, Compare-Mail).

SPEC: docs/specs/modules/issue_1034_official_alerts_foundation.md
AC-1, AC-2, AC-3

Diese Tests schlagen ABSICHTLICH fehl, weil `src/services/official_alerts/` noch
nicht existiert:
- `from services.official_alerts import ...` -> ModuleNotFoundError (Subklasse von
  ImportError)

Nach der Implementierung (/5-implement) muessen alle drei Tests gruen sein.

KEINE Mocks (Projektkonvention CLAUDE.md): Die Test-Fake-Quellen sind echte
Python-Objekte, die das `OfficialAlertSource`-Protocol strukturell erfuellen und
ueber `register_official_alert_source()` im echten Codepfad registriert werden --
kein `Mock()`/`patch()`/`MagicMock`.

Alle drei Tests fahren einen echten `ComparisonEngine.run()` gegen den
Offline-`FixtureProvider` (aktiviert automatisch via die autouse-Fixture in
`tests/conftest.py`, GZ_TEST_FIXTURE_DIR). Die Orte liegen bewusst ausserhalb der
GeoSphere-Bounding-Box (lat 45-50, lon 8-18) an der Côte d'Azur (Primär-Szenario
des Epics #1033), damit `_select_provider_for_location()` den `openmeteo`-Zweig
waehlt und der Fixture-Provider greift statt eines echten GeoSphere-Netzwerkrufs.
"""
from __future__ import annotations

import re
from datetime import date, timedelta

from app.profile import ActivityProfile
from app.user import SavedLocation
from output.renderers.email.compare_html import _render_official_alerts_block, render_compare_html
from services.comparison_engine import ComparisonEngine


def _riviera_locations() -> list[SavedLocation]:
    """Drei reale Côte-d'Azur-Orte, alle ausserhalb der GeoSphere-Bounding-Box
    (lat 45-50 / lon 8-18) -> ComparisonEngine waehlt den openmeteo-Zweig, der
    ueber die autouse-Fixture in tests/conftest.py auf den Offline-FixtureProvider
    umgeleitet wird (kein echter Netzwerkruf)."""
    return [
        SavedLocation(id="riviera-nice", name="Nizza", lat=43.7102, lon=7.2620, elevation_m=10),
        SavedLocation(id="riviera-cannes", name="Cannes", lat=43.5528, lon=7.0174, elevation_m=12),
        SavedLocation(id="riviera-marseille", name="Marseille", lat=43.2965, lon=5.3698, elevation_m=8),
    ]


class _ThrowingOfficialAlertSource:
    """Echte Quelle (kein Mock), die bei jedem fetch()-Aufruf wirft.

    Beweist AC-3: get_official_alerts_for_location() faengt Fehler pro Quelle ab,
    ComparisonEngine.run() bricht nicht ab.
    """

    @property
    def name(self) -> str:
        return "test-throwing-source"

    def covers(self, lat: float, lon: float) -> bool:
        return True

    def fetch(self, lat: float, lon: float):
        raise RuntimeError("simulierter Ausfall der amtlichen Quelle")


class _CompoundThrowingOfficialAlertSource:
    """Echte Quelle (kein Mock), die SOWOHL in fetch() ALS AUCH in der
    name-Property wirft.

    Beweist Adversary-Finding F004 (Fix-Loop 2): der except-Handler in
    get_official_alerts_for_location() darf nicht ungeschuetzt auf
    source.name zugreifen, sonst propagiert die zweite Exception nach aussen
    und verletzt die Garantie "wirft selbst nie" (AC-3).
    """

    @property
    def name(self) -> str:
        raise KeyError("name-Property wirft ebenfalls")

    def covers(self, lat: float, lon: float) -> bool:
        return True

    def fetch(self, lat: float, lon: float):
        raise RuntimeError("simulierter Ausfall der amtlichen Quelle")


class _SingleLocationOfficialAlertSource:
    """Echte Quelle (kein Mock), die nur fuer einen konkreten Ort (bbox-Toleranz
    0.05 Grad) zustaendig ist und dort genau einen OfficialAlert liefert."""

    def __init__(self, lat: float, lon: float, alert) -> None:
        self._lat = lat
        self._lon = lon
        self._alert = alert

    @property
    def name(self) -> str:
        return "test-single-location-source"

    def covers(self, lat: float, lon: float) -> bool:
        return abs(lat - self._lat) < 0.05 and abs(lon - self._lon) < 0.05

    def fetch(self, lat: float, lon: float):
        return [self._alert]


class TestIssue1034OfficialAlertsFoundation:
    """TDD-Reihenfolge laut Spec: AC-1 -> AC-3 -> AC-2."""

    def test_ac1_leere_registry_kein_spuren_und_keine_zusaetzliche_leerzeile(self):
        """AC-1: Given eine Compare-Mail mit >=3 Orten und leerer Official-Alert-
        Registry, When die Mail gerendert wird, Then (a) liefert
        `_render_official_alerts_block()` fuer Locations ohne Alerts nachweislich
        den leeren String (Unit-Vertrag, nicht aus einem HTML-Diff erschlossen),
        und (b) enthaelt das volle HTML an der Einfuegestelle (hinter dem
        Warnungs-Banner, vor der Vergleichsmatrix) exakt EIN Newline-Zeichen --
        keine zusaetzliche Leerzeile und keine Spur des Features.

        Bewusst NICHT als A==A-Vergleich zweier identischer Renderer-Laeufe
        formuliert (das haette nur bewiesen, dass der Code deterministisch ist,
        nicht dass er byte-identisch zum Pre-Slice-Stand ist). Der einmalige
        Byte-fuer-Byte-Beweis gegen den echten Pre-Slice-Codestand
        (`git show $(git merge-base HEAD origin/main):...compare_html.py`) liegt
        dauerhaft im Adversary-Fix-Artefakt:
        docs/artifacts/issue-1034-official-alerts-foundation/ac1-byte-identity-proof.txt
        """
        import services.official_alerts.base as oa_base

        # Registry isolieren (analog AC-3/F004/AC-2): seit Issue #1035 registriert
        # `services.official_alerts` beim Import eine echte Default-Quelle
        # (VigilanceSource). Der "leere Registry"-Vertrag dieses Tests muss die
        # globale Registry daher explizit leeren, sonst laufen mit gesetztem
        # GZ_METEOFRANCE_APIKEY echte Vigilance-Alerts in das Ergebnis ein.
        backup = list(oa_base._REGISTERED_SOURCES)
        oa_base._REGISTERED_SOURCES.clear()
        try:
            locations = _riviera_locations()
            target = date.today() + timedelta(days=1)

            result = ComparisonEngine.run(
                locations,
                time_window=(9, 16),
                target_date=target,
                profile=ActivityProfile.ALLGEMEIN,
            )

            # (a) Unit-Vertrag: leere Registry -> leerer Block, unabhaengig vom HTML.
            assert _render_official_alerts_block([]) == "", (
                "_render_official_alerts_block([]) muss exakt '' liefern"
            )
            assert _render_official_alerts_block(result.locations) == "", (
                "Ohne registrierte Quellen darf keine Location einen Alert haben -> "
                "_render_official_alerts_block() muss exakt '' liefern"
            )

            # (b) Einfuegestelle im vollen HTML: Warnungs-Banner direkt gefolgt von
            # genau einem Newline vor der Vergleichsmatrix -- kein Doppel-Newline,
            # keine Badge-Spur dazwischen.
            html = render_compare_html(
                result, profile=ActivityProfile.ALLGEMEIN, warnings=["Sturmwarnung Test"]
            )
            banner_end = html.index("Sturmwarnung Test</div>") + len("Sturmwarnung Test</div>")
            matrix_start = html.index('<table class="matrix-table"', banner_end)
            between = html[banner_end:matrix_start]

            assert between.count("\n") == 1, (
                f"Zwischen Warnungs-Banner und Vergleichsmatrix darf bei leerer "
                f"Official-Alert-Registry nur genau EIN Newline stehen (keine "
                f"zusaetzliche Leerzeile durch den Platzhalter), gefunden: {between!r}"
            )
            assert "\n\n" not in between, (
                f"Kein Doppel-Newline an der Einfuegestelle erlaubt, gefunden: {between!r}"
            )
        finally:
            oa_base._REGISTERED_SOURCES.clear()
            oa_base._REGISTERED_SOURCES.extend(backup)

    def test_ac3_werfende_quelle_fail_soft(self):
        """AC-3: Given eine registrierte Test-Fake-Quelle wirft in fetch() eine
        Exception, When ComparisonEngine.run() laeuft, Then wird die Compare-Mail
        trotzdem vollstaendig generiert (alle Orte im Ergebnis, keine Exception
        dringt nach aussen) und die betroffene Location hat official_alerts == [].

        TDD RED: `services.official_alerts` existiert noch nicht -> ImportError.
        """
        import services.official_alerts.base as oa_base
        from services.official_alerts import register_official_alert_source

        backup = list(oa_base._REGISTERED_SOURCES)
        oa_base._REGISTERED_SOURCES.clear()
        try:
            register_official_alert_source(_ThrowingOfficialAlertSource())

            locations = _riviera_locations()[:2]
            target = date.today() + timedelta(days=1)

            result = ComparisonEngine.run(
                locations,
                time_window=(9, 16),
                target_date=target,
                profile=ActivityProfile.ALLGEMEIN,
            )

            assert len(result.locations) == 2, (
                f"Alle {len(locations)} Orte muessen im Ergebnis vorhanden sein, "
                f"gefunden {len(result.locations)}"
            )
            for loc_result in result.locations:
                assert loc_result.error is None, (
                    f"Werfende Official-Alert-Quelle darf den Wetter-Fetch nicht "
                    f"stoeren: {loc_result.location.name} hat error={loc_result.error!r}"
                )
                assert loc_result.official_alerts == [], (
                    f"Bei werfender Quelle muss official_alerts leer bleiben "
                    f"(fail-soft), war {loc_result.official_alerts!r} fuer "
                    f"{loc_result.location.name}"
                )
        finally:
            oa_base._REGISTERED_SOURCES.clear()
            oa_base._REGISTERED_SOURCES.extend(backup)

    def test_f004_werfende_name_property_bleibt_fail_soft(self):
        """Adversary-Finding F004 (Fix-Loop 2): Given eine registrierte
        Test-Fake-Quelle wirft SOWOHL in fetch() ALS AUCH in ihrer
        name-Property, When ComparisonEngine.run() laeuft, Then propagiert
        keine der beiden Exceptions nach aussen, die Location hat
        error is None, die Wetterdaten sind intakt und official_alerts
        bleibt [].
        """
        import services.official_alerts.base as oa_base
        from services.official_alerts import register_official_alert_source

        backup = list(oa_base._REGISTERED_SOURCES)
        oa_base._REGISTERED_SOURCES.clear()
        try:
            register_official_alert_source(_CompoundThrowingOfficialAlertSource())

            locations = _riviera_locations()[:2]
            target = date.today() + timedelta(days=1)

            result = ComparisonEngine.run(
                locations,
                time_window=(9, 16),
                target_date=target,
                profile=ActivityProfile.ALLGEMEIN,
            )

            assert len(result.locations) == 2, (
                f"Alle {len(locations)} Orte muessen im Ergebnis vorhanden sein, "
                f"gefunden {len(result.locations)}"
            )
            for loc_result in result.locations:
                assert loc_result.error is None, (
                    f"Werfende name-Property darf den Wetter-Fetch nicht "
                    f"stoeren: {loc_result.location.name} hat error={loc_result.error!r}"
                )
                assert loc_result.hourly_data is not None and len(loc_result.hourly_data) > 0, (
                    f"Wetterdaten muessen trotz doppelt werfender Quelle intakt "
                    f"bleiben fuer {loc_result.location.name}"
                )
                assert loc_result.official_alerts == [], (
                    f"Bei doppelt werfender Quelle muss official_alerts leer bleiben "
                    f"(fail-soft), war {loc_result.official_alerts!r} fuer "
                    f"{loc_result.location.name}"
                )
        finally:
            oa_base._REGISTERED_SOURCES.clear()
            oa_base._REGISTERED_SOURCES.extend(backup)

    def test_ac2_badge_fuer_betroffenen_ort(self):
        """AC-2: Given eine Test-Fake-Quelle liefert fuer genau einen der
        verglichenen Orte einen OfficialAlert(level=3, hazard="thunderstorm", ...),
        When die Compare-Mail gerendert wird, Then erscheint der Badge/Label fuer
        diesen Ort und NICHT fuer die anderen, die <table>-Anzahl bleibt identisch
        zur Baseline ohne registrierte Quellen (der Badge fuegt keine Tabelle
        hinzu), Badge-Block liegt vor der Vergleichsmatrix (`matrix-table`).

        TDD RED: `services.official_alerts` existiert noch nicht -> ImportError.
        """
        import services.official_alerts.base as oa_base
        from services.official_alerts import OfficialAlert, register_official_alert_source

        backup = list(oa_base._REGISTERED_SOURCES)
        oa_base._REGISTERED_SOURCES.clear()
        try:
            locations = _riviera_locations()
            nice = locations[0]
            target = date.today() + timedelta(days=1)

            baseline_result = ComparisonEngine.run(
                locations,
                time_window=(9, 16),
                target_date=target,
                profile=ActivityProfile.ALLGEMEIN,
            )
            baseline_html = render_compare_html(baseline_result, profile=ActivityProfile.ALLGEMEIN)
            tables_baseline = [m.start() for m in re.finditer(r"<table", baseline_html)]

            alert = OfficialAlert(
                source="test-vigilance",
                hazard="thunderstorm",
                level=3,
                label="Gewitterwarnung Stufe Orange",
            )
            register_official_alert_source(
                _SingleLocationOfficialAlertSource(nice.lat, nice.lon, alert)
            )

            result = ComparisonEngine.run(
                locations,
                time_window=(9, 16),
                target_date=target,
                profile=ActivityProfile.ALLGEMEIN,
            )
            html = render_compare_html(result, profile=ActivityProfile.ALLGEMEIN)

            tables_mit_badge = [m.start() for m in re.finditer(r"<table", html)]
            assert len(tables_mit_badge) == len(tables_baseline), (
                f"Die <table>-Anzahl mit Badge muss identisch zur Baseline ohne "
                f"registrierte Quellen sein (der Badge fuegt keine Tabelle hinzu), "
                f"Baseline={len(tables_baseline)}, mit Badge={len(tables_mit_badge)}"
            )

            matrix_pos = html.find('<table class="matrix-table"')
            assert matrix_pos != -1, "Vergleichsmatrix (matrix-table) muss im HTML vorhanden sein"

            label_positions = [m.start() for m in re.finditer(re.escape(alert.label), html)]
            assert len(label_positions) == 1, (
                f"Badge-Label '{alert.label}' muss genau einmal im HTML erscheinen "
                f"(nur beim betroffenen Ort Nizza, nicht bei Cannes/Marseille), "
                f"gefunden {len(label_positions)}x"
            )
            assert label_positions[0] < matrix_pos, (
                "Der Official-Alert-Badge muss im Dokumentfluss VOR der "
                "Vergleichsmatrix (matrix-table) stehen (Slot hinter warnings_html, "
                "vor matrix_html)"
            )
        finally:
            oa_base._REGISTERED_SOURCES.clear()
            oa_base._REGISTERED_SOURCES.extend(backup)
