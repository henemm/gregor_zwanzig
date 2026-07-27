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

import http.server
import threading
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


class _Always404Handler(http.server.BaseHTTPRequestHandler):
    """Echter lokaler HTTP-Server, der JEDE Anfrage mit 404 beantwortet --
    analog dem echten ZAMG-Verhalten ausserhalb Oesterreichs. Kein Mock der
    HTTP-Bibliothek, sondern ein echter Socket-Roundtrip (Muster aus
    ``test_meteoalarm_source.py``s ``_BrokenJSONHandler``)."""

    def do_GET(self) -> None:  # noqa: N802 - von BaseHTTPRequestHandler vorgegeben
        self.send_response(404)
        self.send_header("Content-Type", "text/plain")
        self.end_headers()
        self.wfile.write(b"Could not find municipal for coords.")

    def log_message(self, format: str, *args) -> None:  # noqa: A002 - Signatur vorgegeben
        pass  # Testlauf-Ausgabe nicht mit Server-Zugriffslogs zumuellen


class TestIssue1397S2aZamg404IstNichtZustaendig:
    """Issue #1397 Scheibe S2a: ein ZAMG-404 heisst "nicht zustaendig", nicht
    "ausgefallen" -- kein lauter "amtliche Warnungen nicht abrufbar"-Hinweis
    fuer jede Suedtirol-Etappe. Gegenprobe: HTTP 500 und Timeout bleiben
    echte Ausfaelle (unveraendert)."""

    def test_404_liefert_leere_liste_ohne_ausfall_markierung(self, monkeypatch):
        """GIVEN ein lokaler Server antwortet mit 404 (wie ZAMG ausserhalb
        Oesterreichs), WHEN ``fetch()`` innerhalb einer
        ``observe_fetch_failure()``-Beobachtung aufgerufen wird, THEN liefert
        ``fetch()`` `[]` UND der Fehlschlag-Marker bleibt False (kein
        Ausfall) -- anders als vor der S2a-Nachbesserung."""
        from services.official_alerts import geosphere_warn, warn_egress
        from services.official_alerts.geosphere_warn import GeoSphereWarnSource

        server = http.server.HTTPServer(("127.0.0.1", 0), _Always404Handler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        geosphere_warn._cache.clear()
        try:
            monkeypatch.setattr(
                geosphere_warn, "GEOSPHERE_WARN_URL",
                f"http://127.0.0.1:{server.server_port}",
            )
            source = GeoSphereWarnSource()
            with warn_egress.observe_fetch_failure() as status:
                alerts = source.fetch(46.4983, 11.3548)  # Bozen/Suedtirol
            assert alerts == [], (
                f"404 muss fail-soft [] liefern, erhalten: {alerts}"
            )
            assert status["failed"] is False, (
                "Ein ZAMG-404 darf NICHT als Ausfall zaehlen (Issue #1397 S2a)"
            )
        finally:
            server.shutdown()
            thread.join(timeout=2)
            geosphere_warn._cache.clear()

    def test_404_wird_lang_gecacht_kein_wiederholter_call(self, monkeypatch):
        """GIVEN der erste Abruf liefert 404, WHEN ``fetch()`` fuer denselben
        (gerundeten) Punkt erneut aufgerufen wird, THEN wird der lokale
        Server NICHT ein zweites Mal kontaktiert (24h-Cache statt der
        kurzen 60s-Failure-TTL) -- ein Zaehler im Handler beweist das."""
        from services.official_alerts import geosphere_warn
        from services.official_alerts.geosphere_warn import GeoSphereWarnSource

        call_count = {"n": 0}

        class _CountingHandler(_Always404Handler):
            def do_GET(self) -> None:  # noqa: N802
                call_count["n"] += 1
                super().do_GET()

        server = http.server.HTTPServer(("127.0.0.1", 0), _CountingHandler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        geosphere_warn._cache.clear()
        try:
            monkeypatch.setattr(
                geosphere_warn, "GEOSPHERE_WARN_URL",
                f"http://127.0.0.1:{server.server_port}",
            )
            source = GeoSphereWarnSource()
            assert source.fetch(46.4983, 11.3548) == []
            assert source.fetch(46.4983, 11.3548) == []
            assert call_count["n"] == 1, (
                f"zweiter Abruf muss aus dem 24h-Cache kommen, kein echter "
                f"Call, erhalten {call_count['n']} echte Calls"
            )
        finally:
            server.shutdown()
            thread.join(timeout=2)
            geosphere_warn._cache.clear()

    def test_500_bleibt_echter_ausfall(self, monkeypatch):
        """Gegenprobe: GIVEN ein lokaler Server antwortet mit HTTP 500
        (echter Dienstfehler, kein Zustaendigkeits-404), WHEN ``fetch()``
        aufgerufen wird, THEN bleibt es beim bestehenden Ausfall-Verhalten
        -- Fehlschlag-Marker True."""
        from services.official_alerts import geosphere_warn, warn_egress
        from services.official_alerts.geosphere_warn import GeoSphereWarnSource

        class _Always500Handler(http.server.BaseHTTPRequestHandler):
            def do_GET(self) -> None:  # noqa: N802
                self.send_response(500)
                self.end_headers()

            def log_message(self, format: str, *args) -> None:  # noqa: A002
                pass

        server = http.server.HTTPServer(("127.0.0.1", 0), _Always500Handler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        geosphere_warn._cache.clear()
        try:
            monkeypatch.setattr(
                geosphere_warn, "GEOSPHERE_WARN_URL",
                f"http://127.0.0.1:{server.server_port}",
            )
            source = GeoSphereWarnSource()
            with warn_egress.observe_fetch_failure() as status:
                alerts = source.fetch(46.4983, 11.3548)
            assert alerts == []
            assert status["failed"] is True, (
                "Ein echter Dienstfehler (HTTP 500) MUSS weiterhin als "
                "Ausfall zaehlen -- die S2a-Nachbesserung gilt NUR fuer 404"
            )
        finally:
            server.shutdown()
            thread.join(timeout=2)
            geosphere_warn._cache.clear()

    def test_timeout_bleibt_echter_ausfall(self, monkeypatch):
        """Gegenprobe: GIVEN ``request_fn`` wirft (Timeout/Netzwerkfehler),
        WHEN ``fetch()`` aufgerufen wird, THEN bleibt es beim bestehenden
        Ausfall-Verhalten -- unveraendert durch die S2a-Nachbesserung."""
        from services.official_alerts import geosphere_warn, warn_egress
        from services.official_alerts.geosphere_warn import GeoSphereWarnSource

        geosphere_warn._cache.clear()

        def _raise_timeout(*_args, **_kwargs):
            raise TimeoutError("simulierter Netzwerk-Timeout")

        try:
            monkeypatch.setattr(geosphere_warn.httpx, "get", _raise_timeout)
            source = GeoSphereWarnSource()
            with warn_egress.observe_fetch_failure() as status:
                alerts = source.fetch(46.4983, 11.3548)
            assert alerts == []
            assert status["failed"] is True, (
                "Ein Timeout MUSS weiterhin als Ausfall zaehlen"
            )
        finally:
            geosphere_warn._cache.clear()

    def test_ende_zu_ende_suedtirol_zamg_404_und_funktionierendes_meteoalarm_kein_unavailable(
        self, monkeypatch
    ):
        """END-ZU-ENDE (Issue #1397 S2a): GIVEN ein Suedtirol-Punkt, bei dem
        ZAMG (via lokalem 404-Server) nicht zustaendig ist UND eine zweite,
        funktionierende Quelle (synthetisch, steht stellvertretend fuer eine
        echte MeteoAlarmSource ohne Netzwerkabhaengigkeit) erfolgreich
        antwortet, WHEN ``get_official_alerts_with_status()`` aufgerufen
        wird, THEN ist ``unavailable`` False -- kein "amtliche Warnungen
        nicht abrufbar"-Hinweis mehr fuer diese Etappe."""
        import services.official_alerts.base as oa_base
        from services.official_alerts import geosphere_warn
        from services.official_alerts.base import get_official_alerts_with_status
        from services.official_alerts.geosphere_warn import GeoSphereWarnSource

        class _WorkingItalySource:
            """Reale Objektimplementierung (kein Mock) -- steht fuer eine
            funktionierende MeteoAlarmSource an diesem Punkt."""

            @property
            def name(self) -> str:
                return "test-working-italy-source"

            def covers(self, lat: float, lon: float) -> bool:
                return True

            def fetch(self, lat: float, lon: float):
                return []

        server = http.server.HTTPServer(("127.0.0.1", 0), _Always404Handler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        geosphere_warn._cache.clear()
        backup = list(oa_base._REGISTERED_SOURCES)
        oa_base._REGISTERED_SOURCES.clear()
        try:
            monkeypatch.setattr(
                geosphere_warn, "GEOSPHERE_WARN_URL",
                f"http://127.0.0.1:{server.server_port}",
            )
            oa_base._REGISTERED_SOURCES.append(GeoSphereWarnSource())
            oa_base._REGISTERED_SOURCES.append(_WorkingItalySource())

            bozen = (46.4983, 11.3548)
            alerts, unavailable = get_official_alerts_with_status(*bozen)

            assert alerts == []
            assert unavailable is False, (
                "Ein ZAMG-404 (nicht zustaendig) DARF NICHT mehr als Ausfall "
                "in die unavailable-Berechnung eingehen, solange eine andere "
                "abdeckende Quelle erfolgreich antwortet (Issue #1397 S2a)"
            )
        finally:
            server.shutdown()
            thread.join(timeout=2)
            geosphere_warn._cache.clear()
            oa_base._REGISTERED_SOURCES.clear()
            oa_base._REGISTERED_SOURCES.extend(backup)
