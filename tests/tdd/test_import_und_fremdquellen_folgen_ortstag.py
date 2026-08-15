"""TDD RED — Issue #1727 S5d: Import und Fremdquellen folgen dem Ortstag.

SPEC: docs/specs/modules/fix_1727_s5d_import_fremdquellen_ortstag.md (AC-1 bis AC-8)

Vier Fundstellen bestimmen den Kalendertag noch ueber die Serveruhr, obwohl es
weder Trip noch Preset gibt, aus dem sich eine Zone ergaebe:
``gpx_to_stage_data`` (Rueckfalltag ohne ``stage_date``), die zwei
franzoesischen Behoerdenquellen ``massif_closure``/``meteo_forets`` (Tag/Monat
des Herausgebers) und der Staging-Debug-Ausloeser
``api/routers/debug.py::trigger_radar_alert`` (Henne-Ei ueber
``trip_local_today``). ``compute_default_start_date`` (AC-2) hat keinen
Produktiv-Aufrufer und wird separat auf Abwesenheit geprueft (s.
``tests/refactor/test_epic_129a_2_module_structure.py``).

RED-Gruende (gemessen, nicht vermutet): alle vier rechnen noch mit
``date.today()``/``datetime.now()`` OHNE Zone -- auf dem UTC-Server
(``timedatectl``: ``Etc/UTC``) identisch zum Weltzeit-Tag. Extremzonen
(Kiritimati UTC+14, Paris an der Mitternachtsgrenze) machen den Unterschied
sichtbar; Mitteleuropa-Fixturen (Offset 1-2h) waeren nicht diskriminierend.

Testpolitik (CLAUDE.md "Zwei Schichten"): Kern-Schicht, kein Netz.
``massif_closure`` laeuft gegen einen ECHTEN lokalen ``http.server`` auf
``127.0.0.1`` (kein Mock, Muster ``tests/tdd/test_warn_services_rest.py:65-93``,
um Pfad-Aufzeichnung erweitert -- der Bestand zaehlt dort nur Requests, nicht
den angefragten Pfad). Kein ``pytest.mark.live``.

Jeder Test mit Ortstag-Behauptung traegt den geteilten Vorbedingungs-Anker
``_anker()`` (``tests/tdd/conftest.py:88-109``) VOR der Hauptzusicherung.

Pfadregel #1409: diese Datei liest nichts von der Platte ausser den
synthetischen Fixtures, die sie selbst erzeugt.
"""
from __future__ import annotations

import http.server
import json
import threading
from contextlib import contextmanager
from datetime import date, datetime, timezone

from freezegun import freeze_time

from tests.tdd.conftest import _anker
from tests.tdd.test_befehlspfade_folgen_ortszone import KIRITIMATI, KIRITIMATI_ZONE

# Toulon (Mont Faron) -- reale Var-Koordinaten, ueber massif_at()/massifs_at()
# verifiziert (kein Raten): src='83', massif_id='831' ("MONTS TOULONNAIS").
# Vorbild: tests/tdd/test_issue_1037_massif_closure.py:57 (_VAR_REAL_POINTS).
# Liegt zugleich innerhalb der AROME-Frankreich-Box (radar_service.py:42-45)
# -- dieselben Koordinaten dienen AC-3/AC-4 (massif_closure) UND AC-5
# (meteo_forets).
TOULON = (43.1550, 5.9300)


# ---------------------------------------------------------------------------
# AC-1 — gpx_to_stage_data: Rueckfalltag aus der Zone des ERSTEN Wegpunkts
# ---------------------------------------------------------------------------

def _mini_gpx_bytes(lat0: float, lon0: float, n: int = 12) -> bytes:
    """Synthetische Mini-GPX-Datei mit ``n`` Trackpunkten ab ``(lat0, lon0)``
    -- core/gpx_parser.py verlangt mindestens 10 Punkte je Track."""
    pts = "\n".join(
        f'      <trkpt lat="{lat0 + i * 0.0003:.6f}" lon="{lon0 + i * 0.0003:.6f}">'
        f'<ele>{100 + i}</ele></trkpt>'
        for i in range(n)
    )
    xml = (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<gpx version="1.1" creator="test">\n'
        '  <trk>\n'
        '    <name>Synthetischer Track</name>\n'
        '    <trkseg>\n'
        f"{pts}\n"
        '    </trkseg>\n'
        '  </trk>\n'
        '</gpx>\n'
    )
    return xml.encode("utf-8")


def test_ac1_gpx_rueckfalltag_folgt_der_zone_des_ersten_wegpunkts(tmp_path):
    """AC-1.

    GIVEN eine GPX-Datei, deren ERSTER Wegpunkt auf Kiritimati liegt (UTC+14),
          OHNE ``stage_date`` aufgerufen,
    WHEN  ``gpx_to_stage_data()`` den Rueckfalltag bestimmt,
    THEN  ergibt sich das Etappendatum aus dem ORTSTAG von Kiritimati
          (``tz_for_coords`` auf dessen Koordinaten), NICHT aus dem Servertag.

    RED-Grund: ``gpx_to_stage_data`` rechnet noch mit
    ``d = stage_date or date.today()`` -- auf dem UTC-Server identisch zum
    Weltzeit-Tag.

    Zum Fail-soft-Zweig (leere Punktliste, AC-1 zweiter Halbsatz): dieser
    Zweig ist ueber den oeffentlichen Aufrufweg strukturell NICHT auf
    Laufzeitebene diskriminierend testbar. ``process_gpx_upload()`` ruft
    intern ``parse_gpx()`` (core/gpx_parser.py::_validate_points), das JEDE
    Datei mit weniger als 10 Trackpunkten bereits mit ``GPXParseError``
    ablehnt -- ``track.points == []`` erreicht die Fallback-Zeile in
    ``gpx_to_stage_data`` deshalb nie. Zusaetzlich waere selbst ein
    erzwungener Aufruf dieses Zweigs auf dem UTC-Server LAUFZEIT-IDENTISCH
    zum heutigen Verhalten (``date.today() == datetime.now(timezone.utc)
    .date()`` dort) -- ein Testfall koennte also nicht rot werden, ohne
    wertlos zu sein. Die Muster-A-Konformität dieses (in der Praxis toten)
    Zweigs wird ausschliesslich vom AST-Waechter AC-7
    (``tests/test_output_timezone_guard.py``) durchgesetzt, der Quelltext
    statisch scannt, unabhaengig von Laufzeit-Erreichbarkeit.
    """
    from services.gpx_processing import gpx_to_stage_data

    now_utc = datetime(2026, 8, 19, 20, 0, 0, tzinfo=timezone.utc)
    erwarteter_ortstag = date(2026, 8, 20)
    _anker(now_utc, KIRITIMATI_ZONE, erwarteter_ortstag)

    content = _mini_gpx_bytes(*KIRITIMATI)

    with freeze_time(now_utc):
        result = gpx_to_stage_data(content, "kiritimati.gpx", upload_dir=tmp_path)

    assert result["date"] == erwarteter_ortstag.isoformat(), (
        f"gpx_to_stage_data() lieferte date={result['date']!r} -- erwartet "
        f"den ORTSTAG von Kiritimati ({erwarteter_ortstag.isoformat()}), "
        f"nicht den Servertag ({now_utc.date().isoformat()})"
    )


# ---------------------------------------------------------------------------
# AC-3/AC-4 — massif_closure: Herausgebertag + explizites UTC fuer last_run
# ---------------------------------------------------------------------------

@contextmanager
def _lokaler_massif_server():
    """Echter lokaler HTTP-Server (kein Mock, kein externes Netz) --
    erweitert das Sentinel-Muster aus test_warn_services_rest.py:65-93 um
    Aufzeichnung des ANGEFRAGTEN PFADS (der Bestand zaehlt dort nur die
    Anzahl der Requests, s. Spec 'Nachweisfuehrung')."""
    requested_paths: list[str] = []

    class _Handler(http.server.BaseHTTPRequestHandler):
        def do_GET(self):  # noqa: N802 - stdlib-Signatur
            requested_paths.append(self.path)
            body = json.dumps({"massifs": {"831": [1]}}).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, *_args):  # Testlauf-Output nicht zumuellen
            pass

    srv = http.server.HTTPServer(("127.0.0.1", 0), _Handler)
    thread = threading.Thread(target=srv.serve_forever, daemon=True)
    thread.start()
    try:
        yield srv, requested_paths
    finally:
        srv.shutdown()
        thread.join(timeout=2)


def _fetch_gegen_lokalen_server(monkeypatch, now_utc: datetime) -> list[str]:
    """``MassifClosureSource().fetch(*TOULON)`` gegen den lokalen Sentinel --
    geteilter Ablauf fuer AC-3 (Pfad) und AC-4 (last_run). Cache wird VOR
    jedem Aufruf geleert, damit kein Test vom anderen einen Cache-Treffer
    erbt (``cached_fetch`` nutzt ``time.monotonic``, NICHT ``freeze_time``)."""
    from services.official_alerts import massif_closure
    from services.official_alerts.massif_closure import MassifClosureSource

    massif_closure._cache.clear()
    with freeze_time(now_utc):
        with _lokaler_massif_server() as (srv, requested_paths):
            monkeypatch.setattr(
                massif_closure, "_ENDPOINT",
                f"http://127.0.0.1:{srv.server_port}/static/{{src}}/import_data/{{ymd}}.json",
            )
            MassifClosureSource().fetch(*TOULON)
    return requested_paths


def test_ac3_massif_closure_ymd_folgt_dem_pariser_tag(monkeypatch):
    """AC-3.

    GIVEN ``MassifClosureSource.fetch(lat, lon)`` baut die Tages-Abfrage-URL
          ``…/import_data/{ymd}.json`` fuer die franzoesische Praefektur-
          Quelle,
    WHEN  ``fetch()`` kurz nach Pariser Mitternacht laeuft (22:30 UTC =
          00:30 CEST -- UTC-Tag und Paris-Tag fallen auseinander),
    THEN  folgt ``{ymd}`` dem Tag des HERAUSGEBERS (Paris ueber
          ``tz_for_coords(lat, lon)``), NICHT dem Servertag.

    RED-Grund: ``_do_request()`` rechnet noch mit
    ``datetime.now().strftime("%Y%m%d")`` -- auf dem UTC-Server identisch
    zum Weltzeit-Tag.
    """
    now_utc = datetime(2026, 6, 1, 22, 30, 0, tzinfo=timezone.utc)
    erwarteter_ortstag = date(2026, 6, 2)
    _anker(now_utc, "Europe/Paris", erwarteter_ortstag)

    requested_paths = _fetch_gegen_lokalen_server(monkeypatch, now_utc)

    assert requested_paths, "kein Request beim lokalen Sentinel angekommen"
    erwarteter_pfad = f"/static/83/import_data/{erwarteter_ortstag:%Y%m%d}.json"
    assert requested_paths[0] == erwarteter_pfad, (
        f"massif_closure fragte {requested_paths[0]!r} ab -- erwartet den "
        f"PARISER Tag ({erwarteter_pfad}), nicht den Servertag "
        f"(/static/83/import_data/{now_utc:%Y%m%d}.json)"
    )


def test_ac4_massif_closure_last_run_ist_tz_aware_utc(monkeypatch):
    """AC-4.

    GIVEN ``MassifClosureSource.fetch`` schreibt ``_STATUS["last_run"]`` fuer
          das interne Monitoring,
    WHEN  der Zeitstempel gebildet wird,
    THEN  geschieht das EXPLIZIT in UTC (``datetime.now(timezone.utc)``),
          erkennbar an einem tz-aware ISO-Zeitstempel.

    RED-Grund: ``fetch()`` rechnet noch mit ``datetime.now().isoformat()``
    -- ein naiver Zeitstempel ohne Offset-Suffix.
    """
    from services.official_alerts import massif_closure

    now_utc = datetime(2026, 6, 1, 22, 30, 0, tzinfo=timezone.utc)
    massif_closure._STATUS["last_run"] = None

    _fetch_gegen_lokalen_server(monkeypatch, now_utc)

    last_run = massif_closure._STATUS["last_run"]
    assert last_run is not None, "fetch() hat _STATUS['last_run'] nicht gesetzt"
    assert last_run.endswith("+00:00"), (
        f"_STATUS['last_run']={last_run!r} traegt keine UTC-Offset-Markierung "
        f"-- RED-Grund: naives datetime.now().isoformat() ohne "
        f"timezone.utc liefert keinen Offset-Suffix"
    )


# ---------------------------------------------------------------------------
# AC-5 — meteo_forets.covers: Saison-Monat der Ortszone
# ---------------------------------------------------------------------------

def test_ac5_meteo_forets_saison_gate_folgt_der_ortszone():
    """AC-5.

    GIVEN das Saison-Gate (Juni-September) von ``MeteoForetsSource.covers()``,
    WHEN  der Monat an der Saisongrenze bestimmt wird (31.05. 22:30 UTC =
          01.06. 00:30 CEST in Paris),
    THEN  gilt der PARISER Monat (Juni, Saison), nicht der Servermonat (Mai,
          ausserhalb der Saison).

    RED-Grund: ``covers()`` rechnet noch mit
    ``_is_season(datetime.now().month)`` -- auf dem UTC-Server identisch zum
    Weltzeit-Monat.
    """
    from services.official_alerts.meteo_forets import MeteoForetsSource

    now_utc = datetime(2026, 5, 31, 22, 30, 0, tzinfo=timezone.utc)
    erwarteter_ortstag = date(2026, 6, 1)
    _anker(now_utc, "Europe/Paris", erwarteter_ortstag)

    with freeze_time(now_utc):
        result = MeteoForetsSource().covers(*TOULON)

    assert result is True, (
        f"MeteoForetsSource.covers{TOULON} lieferte {result!r} -- erwartet "
        f"True: am 31.05. 22:30 UTC ist es in Paris bereits der 01.06. "
        f"(Saison Juni-September), waehrend der Servertag (31.05.) noch "
        f"ausserhalb der Saison liegt"
    )


# ---------------------------------------------------------------------------
# AC-6 — debug.py::trigger_radar_alert: trip_local_today() vor der Segmentwahl
# ---------------------------------------------------------------------------

def test_ac6_debug_trigger_radar_alert_today_folgt_trip_local_today(monkeypatch):
    """AC-6.

    GIVEN ein Trip mit einer Etappe auf Kiritimati (UTC+14), Staging-Debug-
          Ausloeser ``trigger_radar_alert`` (braucht ``today`` VOR der
          Segmentwahl -- Henne-Ei, weil die Zone eigentlich aus dem noch
          unbekannten aktiven Segment kaeme),
    WHEN  ``today`` bestimmt wird,
    THEN  ist das der ORTSTAG der Tour (``trip_local_today(trip, now_utc)``),
          nicht der Servertag (``date_type.today()``).

    DI-Spion direkt auf ``convert_trip_to_segments`` (Lehre #1727 S5c: die
    Zusicherung sitzt an der AUFLÖSUNG selbst, kein Ergebnis-Umweg) --
    ``now_utc`` wird NICHT zusaetzlich gemockt (Befund F001 aus S5a), nur
    ``freeze_time`` steuert die Systemuhr, ``datetime.now(timezone.utc)``
    liest sie echt. ``send_radar_alert_email`` wird durch einen
    No-Op-Ersatz ausgetauscht: dieser Kern-Schicht-Test darf keinen echten
    Mailversand ausloesen (Test-Politik "kein Netz") -- ``mail.henemm.com``
    waere vom Egress-Waechter sonst technisch erlaubt (TEST_ACCESS) und
    wuerde real senden.

    RED-Grund: ``trigger_radar_alert`` rechnet noch mit
    ``today = date_type.today()`` -- auf dem UTC-Server identisch zum
    Weltzeit-Tag.
    """
    import services.trip_segments as trip_segments_mod
    from api.routers.debug import trigger_radar_alert
    from app.loader import save_trip
    from app.trip import Stage, Trip, Waypoint

    now_utc = datetime(2026, 8, 19, 20, 0, 0, tzinfo=timezone.utc)
    erwarteter_ortstag = date(2026, 8, 20)
    _anker(now_utc, KIRITIMATI_ZONE, erwarteter_ortstag)

    user_id = "tdd-1727-s5d-debug"
    trip = Trip(
        id="kiritimati-debug",
        name="Kiritimati Debug",
        stages=[
            Stage(
                id="S0", name="Etappe 0", date=erwarteter_ortstag,
                waypoints=[
                    Waypoint(id="W0", name="Start", lat=KIRITIMATI[0],
                              lon=KIRITIMATI[1], elevation_m=10),
                    Waypoint(id="W1", name="Ziel", lat=KIRITIMATI[0] + 0.05,
                              lon=KIRITIMATI[1] + 0.05, elevation_m=20),
                ],
            ),
        ],
    )
    save_trip(trip, user_id=user_id)

    real_convert = trip_segments_mod.convert_trip_to_segments
    calls: list[date] = []

    def _spy_convert(trip_arg, day_arg):
        calls.append(day_arg)
        return real_convert(trip_arg, day_arg)

    monkeypatch.setattr(trip_segments_mod, "convert_trip_to_segments", _spy_convert)
    monkeypatch.setattr(
        "services.radar_alert_service.send_radar_alert_email",
        lambda *a, **kw: None,
    )
    monkeypatch.setenv("GZ_ENV", "staging")

    with freeze_time(now_utc):
        trigger_radar_alert(user_id=user_id)

    assert calls, "convert_trip_to_segments() wurde nicht aufgerufen"
    assert calls[0] == erwarteter_ortstag, (
        f"trigger_radar_alert() rief convert_trip_to_segments() ZUERST mit "
        f"today={calls[0]!r} auf -- erwartet den ORTSTAG der Tour "
        f"({erwarteter_ortstag.isoformat()}), nicht den Servertag "
        f"({now_utc.date().isoformat()})"
    )


# ---------------------------------------------------------------------------
# AC-8 — Invarianten-Wächter: Fremdquellen-Signaturen bleiben zwei
# Positionsargumente. MUSS bereits jetzt gruen sein und gruen BLEIBEN -- kein
# RED-Ziel dieser Scheibe.
# ---------------------------------------------------------------------------

def test_ac8_massif_closure_und_meteo_forets_signaturen_bleiben_zwei_positionsargumente():
    """AC-8 — INVARIANTEN-WAECHTER (muss VOR UND NACH der Implementierung
    gruen bleiben, zaehlt NICHT als erfuelltes RED dieser Scheibe).

    ``covers(lat, lon)``/``fetch(lat, lon)`` sind ein
    ``OfficialAlertSource``-Protocol mit exakt zwei Positionsargumenten
    (``official_alerts/base.py:29-35``); die Registry ruft beide generisch
    fuer sechs Quellen IN ``try/except Exception`` (``base.py:137-141``,
    ``:148``) -- ein ``TypeError`` aus einer Signaturerweiterung wuerde dort
    geschluckt, geloggt und die Quelle STILL deaktivieren, statt laut zu
    brechen. Der Registry-Aufruf selbst taugt deshalb NICHT als Nachweis
    (Prüfort != Wirkort) -- dieser Test prueft direkt per
    ``inspect.signature()``, an der Stelle, wo die Zusicherung tatsaechlich
    wirkt.
    """
    import inspect

    from services.official_alerts.massif_closure import MassifClosureSource
    from services.official_alerts.meteo_forets import MeteoForetsSource

    fetch_params = list(inspect.signature(MassifClosureSource.fetch).parameters.keys())
    assert fetch_params == ["self", "lat", "lon"], (
        f"MassifClosureSource.fetch traegt {fetch_params} -- das "
        f"OfficialAlertSource-Protocol verlangt exakt self, lat, lon"
    )

    covers_params = list(inspect.signature(MeteoForetsSource.covers).parameters.keys())
    assert covers_params == ["self", "lat", "lon"], (
        f"MeteoForetsSource.covers traegt {covers_params} -- das "
        f"OfficialAlertSource-Protocol verlangt exakt self, lat, lon"
    )
