"""TDD RED — Issue #1085: GeoSphereWarnSource (amtliche Warnungen Oesterreich).

SPEC: docs/specs/modules/issue_1085_geosphere_warn_source.md
Kontext: docs/context/feat-1085-geosphere-warn.md
AC-1 bis AC-4

Diese Tests schlagen ABSICHTLICH fehl, weil
``services.official_alerts.geosphere_warn`` noch nicht existiert ->
ModuleNotFoundError (Subklasse von ImportError) beim jeweils ersten Import
innerhalb der Testfunktion.

KEINE Mocks (CLAUDE.md-Projektkonvention "KEINE MOCKED TESTS!"):
- AC-1/AC-4-Live-Tests rufen die echte GeoSphere-Warn-API
  (``https://warnungen.zamg.at/wsapp/api/getWarningsForCoords``) auf, kein
  Mock, kein Patch.
- AC-3 nutzt eine echte Koordinate am Schweizer Grenzgebiet innerhalb der
  INCA-Bbox, die real ein HTTP 404 der API ausloest ("Could not find
  municipal for coords."), um das fail-soft-Verhalten zu beweisen.
- AC-4-Mapping-Unit-Test ruft die reine Parse-Funktion direkt mit einer
  synthetischen, aber strukturell echten JSON-Antwort auf (kein
  Netzwerk-Mock der Bibliothek, nur Testdaten).
- Kein Test haengt an der tatsaechlichen Warnlage zum Testzeitpunkt: ein
  warnungsfreier Ort liefert korrekt eine leere Liste.
"""
from __future__ import annotations

from datetime import datetime, timezone

import pytest

# Reale Koordinaten aus Spec/Kontext-Dokument.
INNSBRUCK = (47.2692, 11.4041)  # Oesterreich, INCA-Bbox, Live-Warnungen moeglich
PARIS = (48.8566, 2.3522)  # ausserhalb der INCA-Bbox (lon < 9.5)
HAMBURG = (53.55, 9.99)  # ausserhalb der INCA-Bbox (lat > 49.1)
GRAUBUENDEN_GRENZGEBIET = (46.85, 9.53)  # innerhalb INCA-Bbox, keine AT-Gemeinde -> 404

_EXPECTED_HAZARD_TABLE = {
    1: ("wind_gust", "Sturm"),
    2: ("rain", "Starkregen"),
    3: ("snow", "Schneefall"),
    4: ("black_ice", "Glatteis"),
    5: ("thunderstorm", "Gewitter"),
    6: ("extreme_heat", "Hitze"),
    7: ("extreme_cold", "Kälte"),
}


def _synthetic_warning(warntypid: int, warnstufeid: int, start_epoch: str, end_epoch: str) -> dict:
    """Baut eine einzelne Warnungs-``properties``-Struktur wie in der echten
    GeoSphere-Antwort dokumentiert (Kontext-Dokument, verifiziert 2026-07-08)."""
    return {
        "type": "Feature",
        "properties": {
            "warntypid": warntypid,
            "warnstufeid": warnstufeid,
            "begin": "10.07.2026 00:00",
            "end": "11.07.2026 00:00",
            "text": f"Testwarnung Typ {warntypid}",
            "rawinfo": {"start": start_epoch, "end": end_epoch},
        },
    }


def _synthetic_response(location_name: str, warnings: list[dict]) -> dict:
    """Baut die volle GeoJSON-Feature-Struktur wie vom echten Endpunkt
    geliefert: ``properties.location.properties.name`` +
    ``properties.warnings[]``."""
    return {
        "type": "Feature",
        "properties": {
            "location": {
                "type": "Feature",
                "properties": {"name": location_name},
            },
            "warnings": warnings,
        },
    }


class TestIssue1085GeosphereWarnSource:
    """TDD-Reihenfolge laut Spec: AC-2 (Registrierung/covers) -> AC-1/AC-4
    (Live-Struktur) -> AC-3 (fail-soft) -> AC-4 (Mapping-Unit)."""

    def test_ac2_klasse_existiert_name_und_registrierung(self):
        """AC-2: GIVEN das Modul geosphere_warn, WHEN GeoSphereWarnSource
        instanziiert und services.official_alerts importiert wird, THEN hat
        die Instanz name=='geosphere_warn' und ist nach dem Paket-Import in
        der zentralen Registry (base._REGISTERED_SOURCES) vertreten."""
        from services.official_alerts.geosphere_warn import GeoSphereWarnSource

        source = GeoSphereWarnSource()
        assert source.name == "geosphere_warn"

        import services.official_alerts  # noqa: F401 - triggert Lazy-Registration
        import services.official_alerts.base as oa_base

        registered_names = [s.name for s in oa_base._REGISTERED_SOURCES]
        assert "geosphere_warn" in registered_names, (
            f"GeoSphereWarnSource muss beim Paket-Import registriert werden, "
            f"registrierte Quellen: {registered_names}"
        )

    def test_ac2_covers_oesterreich_true_ausland_false_ohne_netzwerk(self):
        """AC-2: GIVEN Koordinaten in und ausserhalb Oesterreichs, WHEN
        covers() aufgerufen wird, THEN liefert covers() fuer Innsbruck True
        und fuer Paris/Hamburg False -- rein anhand der INCA-Bbox, ohne
        Netzwerk-Call (kein API-Key/Netzwerk-Setup in diesem Test)."""
        from services.official_alerts.geosphere_warn import GeoSphereWarnSource

        source = GeoSphereWarnSource()
        assert source.covers(*INNSBRUCK) is True
        assert source.covers(*PARIS) is False
        assert source.covers(*HAMBURG) is False

    # Echter GeoSphere-Call (warnungen.zamg.at) -- seit #1348 Scheibe 2b im Kern
    # via Egress-Guard blockiert. Struktureller Live-Vertrag gehoert in die
    # Live-Schicht (Guard aus), sonst vakuoes gruen ueber leere Liste.
    @pytest.mark.live
    def test_ac1_ac4_live_innsbruck_struktureller_vertrag(self):
        """AC-1/AC-4: GIVEN Innsbruck (echte AT-Koordinate), WHEN fetch()
        einen echten Live-Call gegen die GeoSphere-API macht, THEN ist das
        Ergebnis eine Liste und JEDES gelieferte Element erfuellt den
        strukturellen OfficialAlert-Vertrag (source/hazard/level/label/
        region_label) -- unabhaengig von der tatsaechlichen Warnlage zum
        Testzeitpunkt (leere Liste ist ebenfalls ein gueltiges Ergebnis)."""
        from services.official_alerts.geosphere_warn import GeoSphereWarnSource

        source = GeoSphereWarnSource()
        alerts = source.fetch(*INNSBRUCK)

        assert isinstance(alerts, list)
        allowed_hazards = {h for h, _ in _EXPECTED_HAZARD_TABLE.values()}
        for alert in alerts:
            assert alert.source == "geosphere_warn"
            assert alert.level in (2, 3, 4)
            assert alert.hazard in allowed_hazards
            assert alert.label and isinstance(alert.label, str)
            assert alert.region_label == "Innsbruck", (
                f"region_label muss der von der API gelieferte Gemeindename "
                f"sein, war {alert.region_label!r}"
            )

    # Beweist Fail-soft AUF EINEN ECHTEN 404 der GeoSphere-API
    # (warnungen.zamg.at) -- seit #1348 Scheibe 2b im Kern via Egress-Guard
    # blockiert; ohne den echten 404-Call ist die Assertion vakuoes. Gehoert in
    # die Live-Schicht (Guard aus).
    @pytest.mark.live
    def test_ac3_fail_soft_404_grenzgebiet_ohne_at_gemeinde(self):
        """AC-3: GIVEN eine Koordinate innerhalb der INCA-Bbox, aber real
        ausserhalb einer oesterreichischen Gemeinde (Schweizer Grenzgebiet
        Graubuenden), WHEN fetch() aufgerufen wird, THEN liefert die echte
        API einen HTTP 404 und fetch() faengt diesen fail-soft ab: liefert
        [] statt eine Exception zu werfen."""
        from services.official_alerts.geosphere_warn import GeoSphereWarnSource

        source = GeoSphereWarnSource()
        # Vorbedingung: liegt tatsaechlich in der INCA-Bbox, damit covers()
        # True liefert und fetch() ueberhaupt den echten Call macht.
        assert source.covers(*GRAUBUENDEN_GRENZGEBIET) is True

        alerts = source.fetch(*GRAUBUENDEN_GRENZGEBIET)
        assert alerts == [], (
            "fetch() muss bei einem 404 der GeoSphere-API [] liefern, "
            "keine Exception werfen"
        )

    def test_ac3_registry_get_official_alerts_for_location_wirft_nie(self):
        """AC-3: GIVEN die volle Official-Alerts-Registry inkl.
        GeoSphereWarnSource, WHEN get_official_alerts_for_location() fuer
        einen AT-Ort aufgerufen wird, THEN liefert die Funktion eine Liste
        und wirft keine Exception (fail-soft-Vertrag der Registry, #1034,
        bleibt mit der neuen Quelle intakt)."""
        from services.official_alerts.geosphere_warn import GeoSphereWarnSource  # noqa: F401
        from services.official_alerts import get_official_alerts_for_location

        alerts = get_official_alerts_for_location(*INNSBRUCK)
        assert isinstance(alerts, list)

    def test_ac4_mapping_alle_warntypid_und_unbekannter_typ_wird_uebersprungen(self):
        """AC-4: GIVEN eine synthetische, aber strukturell echte
        GeoSphere-Antwort mit allen sieben dokumentierten warntypid-Werten,
        drei warnstufeid-Stufen (1/2/3) sowie einem unbekannten warntypid
        (99), WHEN die interne Mapping-Funktion die Antwort parst, THEN wird
        jedes bekannte warntypid korrekt auf (hazard, label) abgebildet,
        jedes warnstufeid korrekt auf level=warnstufeid+1, die Epochen aus
        rawinfo.start/end korrekt auf valid_from/valid_to (datetime, UTC),
        region_label auf den Gemeindenamen -- und die unbekannte warntypid=99
        Warnung wird uebersprungen statt die gesamte Antwort zum Absturz zu
        bringen."""
        from services.official_alerts.geosphere_warn import _extract_alerts

        start_epoch, end_epoch = "1783720800", "1783807200"
        warnings = [
            _synthetic_warning(warntypid=w, warnstufeid=((idx % 3) + 1), start_epoch=start_epoch, end_epoch=end_epoch)
            for idx, w in enumerate(_EXPECTED_HAZARD_TABLE.keys())
        ]
        # Unbekanntes warntypid muss uebersprungen werden, nicht crashen.
        warnings.append(
            _synthetic_warning(warntypid=99, warnstufeid=1, start_epoch=start_epoch, end_epoch=end_epoch)
        )

        data = _synthetic_response("Innsbruck", warnings)
        alerts = _extract_alerts(data)

        assert len(alerts) == 7, (
            f"warntypid=99 muss uebersprungen werden, erwartet 7 Alerts aus "
            f"7 bekannten warntypid-Werten, erhalten {len(alerts)}"
        )

        by_hazard = {alert.hazard: alert for alert in alerts}
        expected_start = datetime.fromtimestamp(int(start_epoch), tz=timezone.utc)
        expected_end = datetime.fromtimestamp(int(end_epoch), tz=timezone.utc)

        for idx, (warntypid, (expected_hazard, expected_label)) in enumerate(_EXPECTED_HAZARD_TABLE.items()):
            expected_level = ((idx % 3) + 1) + 1  # warnstufeid + 1
            assert expected_hazard in by_hazard, (
                f"warntypid={warntypid} muss auf hazard={expected_hazard!r} "
                f"abgebildet werden, gefundene hazards: {list(by_hazard.keys())}"
            )
            alert = by_hazard[expected_hazard]
            assert alert.source == "geosphere_warn"
            assert alert.label == expected_label
            assert alert.level == expected_level
            assert alert.region_label == "Innsbruck"
            assert alert.valid_from == expected_start
            assert alert.valid_to == expected_end
