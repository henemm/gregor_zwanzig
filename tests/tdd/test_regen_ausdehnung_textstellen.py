"""TDD RED — Issue #2051 Scheibe S2a: EINE Textstelle (E-Mail-Trip-Langform)
zeigt die raeumliche Ausdehnung, plus die Modell-/Verdrahtungs-Zusicherungen
drumherum.

SPEC: docs/specs/modules/feat_2051_s2a_raeumliche_ausdehnung.md — AC-7, AC-8,
AC-9, AC-10, AC-15, AC-16.

RED-Ursache: `OnsetEvent.rain_zones` (additives Feld, `model.py`) existiert
noch nicht -> `TypeError` bei der Konstruktion; der Renderer-Helfer
`_onset_extent_suffix` existiert noch nicht.

Mock-frei: echte `OnsetEvent`/`AlertMessage`-Objekte durch die echten
Renderer (Muster `test_onset_ende_textstellen.py`), echter
`TripAlertService.check_radar_alerts()`-Lauf fuer den Draht-Test (AC-9,
Muster `test_issue_822_radar_nowcast_segment.py`).
"""
from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from app.config import Settings
from app.models import TripReportConfig
from app.trip import Stage, Trip, Waypoint
from output.renderers.alert.model import AlertMessage, OnsetEvent
from output.renderers.alert.render import render_email
from services.radar_service import NowcastResult, RadarNowcastService
from utils.geo import haversine_km

from tests.helpers.arrival_window_fixtures import active_window_offsets, stage_date

_TZ = ZoneInfo("Europe/Vienna")

_MINIMAL_FIELDS = dict(
    onset_minutes=30, onset_time="18:00", km_from=8.0, km_to=8.0,
    is_convective=False, intensity_label="Mäßiger Regen",
    source_label="Radar (DWD)", segment_id="Ziel",
)


def _onset_event(**overrides) -> OnsetEvent:
    fields = dict(_MINIMAL_FIELDS)
    fields.update(overrides)
    return OnsetEvent(**fields)


def _onset_msg(*events: OnsetEvent) -> AlertMessage:
    return AlertMessage(
        trip_short="KHW 403", stand_at="17:30", events=tuple(events),
        source="Radar (DWD)",
    )


# --------------------------------------------------------------------------
# AC-7: km_from/km_to bleiben die Segment-Grenzen, rain_zones ein EIGENES
#       Feld — kein Test darf beide Bedeutungen ueber denselben Namen lesen.
# --------------------------------------------------------------------------

def test_ac7_km_von_bis_und_rain_zones_sind_getrennte_bedeutungen():
    from services.rain_extent import RainZone

    zone = RainZone(km_from=2.0, km_to=4.0, onset_minutes=15, event_end_minutes=25)
    event = _onset_event(km_from=0.0, km_to=13.0, rain_zones=(zone,))

    assert event.km_from == 0.0 and event.km_to == 13.0, (
        f"AC-7: km_from/km_to muessen die Segment-Grenzen bleiben, waren "
        f"{event.km_from}/{event.km_to}"
    )
    assert event.rain_zones[0].km_from == 2.0 and event.rain_zones[0].km_to == 4.0, (
        f"AC-7: rain_zones[0] muss die Zonen-Grenzen tragen, waren "
        f"{event.rain_zones[0].km_from}/{event.rain_zones[0].km_to}"
    )
    # Gegenprobe: die beiden Wertepaare duerfen nicht zusammenfallen — sonst
    # koennte ein Pruefling still beide ueber denselben Namen lesen, ohne
    # dass der Test es merkt.
    assert (event.km_from, event.km_to) != (
        event.rain_zones[0].km_from, event.rain_zones[0].km_to,
    ), "AC-7: Testvoraussetzung verletzt — die beiden Wertepaare muessen sich unterscheiden"


# --------------------------------------------------------------------------
# AC-8: unvermessene Etappe (km_measured=False) -> KEINE Zusatzzeile, Text
#       bleibt byte-identisch zum Stand vor dieser Spec.
# --------------------------------------------------------------------------

def test_ac8_unvermessene_etappe_zeigt_keine_ausdehnung_byte_identisch():
    from services.rain_extent import RainZone

    zone = RainZone(km_from=8.0, km_to=12.0, onset_minutes=20, event_end_minutes=40)

    baseline = _onset_msg(_onset_event(km_measured=False))
    mit_zonen_unvermessen = _onset_msg(
        _onset_event(km_measured=False, rain_zones=(zone,))
    )

    _html_base, plain_base = render_email(baseline)
    _html_zonen, plain_zonen = render_email(mit_zonen_unvermessen)

    assert plain_zonen == plain_base, (
        f"AC-8: unvermessene Etappe muss byte-identisch zum Stand ohne "
        f"Zonen-Feld bleiben.\nMit Zonen:\n{plain_zonen}\nBaseline:\n{plain_base}"
    )
    assert "Nass km" not in plain_zonen, (
        f"AC-8: keine Ausdehnungs-Zeile bei unvermessener Etappe erlaubt:\n{plain_zonen}"
    )


# --------------------------------------------------------------------------
# AC-9: vermessene Etappe (km_measured=True) + eine Zone -> Zusatzzeile mit
#       exakt "Nass km 8-12".
# --------------------------------------------------------------------------

def test_ac9_vermessene_etappe_zeigt_die_nasszone():
    """AC-9 (Renderer-Ebene). Positivkontrolle zu AC-8: ohne diesen Fall
    waere AC-8s Abwesenheits-Pruefung trivial wahr."""
    from services.rain_extent import RainZone

    zone = RainZone(km_from=8.0, km_to=12.0, onset_minutes=20, event_end_minutes=40)
    msg = _onset_msg(_onset_event(km_measured=True, rain_zones=(zone,)))

    _html, plain = render_email(msg)

    assert "Nass km 8-12" in plain, (
        f"AC-9: erwartet die Zusatzzeile 'Nass km 8-12' im Text:\n{plain}"
    )


def test_ac9_draht_km_measured_erreicht_das_gerenderte_onset_event():
    """AC-9 (Draht-Test, Kartierungs-Befund): `check_radar_alerts()` muss
    `TripSegment.distance_measured` bis in das gerenderte `OnsetEvent`
    tragen — sonst waere AC-9 nur auf Renderer-Ebene erfuellt, waehrend die
    Ausdehnung in Produktion auf KEINER Etappe erschiene (auch nicht auf den
    vermessenen).

    RED heute: weder `RadarAlertRequest` noch `OnsetEvent`-Konstruktion in
    `notification_service.py::send_radar_alert` (die tatsaechliche
    Trip-Onset-Baustelle — nicht `radar_alert_service.py:60`, das ist toter
    Code, s. Ruecklauf an den Auftraggeber) reichen `km_measured`/
    `rain_zones` durch. Der Body enthaelt deshalb heute KEINE 'Nass km'-Zeile,
    obwohl die Etappe hier bewusst vermessen ist (`distance_from_start_km`
    auf beiden Wegpunkten monoton, >= Luftlinie).
    """
    from services.trip_alert import TripAlertService
    from services.radar_service import RadarNowcastService

    uid = f"tdd-2051-s2a-ac9-{uuid.uuid4().hex[:6]}"
    lat0, lon0 = 47.0, 11.0
    lat1, lon1 = 47.05, 11.05
    luftlinie = haversine_km(lat0, lon0, lat1, lon1)

    from app.loader import get_briefings_dir
    import shutil
    from pathlib import Path

    def _clean(u: str) -> None:
        d = Path(__file__).resolve().parents[2] / "data" / "users" / u
        if d.exists():
            shutil.rmtree(d, ignore_errors=True)

    _clean(uid)
    try:
        today = stage_date(lat0, lon0)
        arr0, arr1 = active_window_offsets(lat0, lon0, -60, 60)

        wp0 = Waypoint(
            id="WP0", name="WP0", lat=lat0, lon=lon0, elevation_m=1000.0,
            arrival_calculated=arr0, distance_from_start_km=0.0,
        )
        wp1 = Waypoint(
            id="WP1", name="WP1", lat=lat1, lon=lon1, elevation_m=1000.0,
            arrival_calculated=arr1, distance_from_start_km=round(luftlinie, 3),
        )
        stage = Stage(id="S1", name="Tag 1", date=today, waypoints=[wp0, wp1])
        trip_id = f"tdd-2051-s2a-ac9-trip-{uuid.uuid4().hex[:6]}"
        trip = Trip(id=trip_id, name="AC9 Draht Trip", stages=[stage])
        trip.report_config = TripReportConfig(
            trip_id=trip_id, send_email=True, send_telegram=False,
            alert_on_changes=False,
        )

        trips_dir = get_briefings_dir(uid)
        trips_dir.mkdir(parents=True, exist_ok=True)
        import json
        data = {
            "id": trip.id, "name": trip.name,
            "stages": [{
                "id": stage.id, "name": stage.name, "date": stage.date.isoformat(),
                "waypoints": [
                    {
                        "id": w.id, "name": w.name, "lat": w.lat, "lon": w.lon,
                        "elevation_m": w.elevation_m,
                        "arrival_calculated": w.arrival_calculated,
                        "distance_from_start_km": w.distance_from_start_km,
                    }
                    for w in stage.waypoints
                ],
            }],
            "report_config": {
                "trip_id": trip.report_config.trip_id,
                "send_email": True, "send_telegram": False,
            },
        }
        (trips_dir / f"{trip.id}.json").write_text(json.dumps(data))

        captured: list[dict] = []

        def _sink(subject: str, body: str) -> None:
            captured.append({"subject": subject, "body": body})

        def _wet_frames(la: float, lo: float) -> list:
            from providers.brightsky import RadarFrame
            now = datetime.now(timezone.utc)
            return [RadarFrame(timestamp=now + timedelta(minutes=5), precip_mm_h=4.0)]

        svc = TripAlertService(
            throttle_hours=2, user_id=uid,
            radar_service=RadarNowcastService(frame_source=_wet_frames),
            settings=Settings(
                smtp_host="test.invalid", smtp_user="u", smtp_pass="p",
                mail_to="x@example.com",
            ),
            mail_sink=_sink,
        )
        svc.clear_radar_throttle(trip_id)
        sent = svc.check_radar_alerts()

        assert sent >= 1 and captured, (
            f"Testvoraussetzung: der Alarm muss ausgeloest worden sein "
            f"(sent={sent}, captured={len(captured)}) — ohne Mail ist AC-9 "
            f"am Draht nicht pruefbar"
        )
        body = captured[0]["body"]
        assert "Nass km" in body, (
            "AC-9 (Draht): die vermessene Etappe (distance_measured=True) "
            f"muss eine 'Nass km'-Zeile tragen — km_measured erreicht das "
            f"gerenderte OnsetEvent nicht.\nBody:\n{body}"
        )
    finally:
        _clean(uid)


# --------------------------------------------------------------------------
# AC-10: zwei getrennte Zonen -> "Nass km 2-4, km 9-11", NIEMALS eine
#        zusammengefasste Huelle "km 2-11".
# --------------------------------------------------------------------------

def test_ac10_zwei_zonen_bleiben_getrennt_keine_huelle():
    from services.rain_extent import RainZone

    zone_a = RainZone(km_from=2.0, km_to=4.0, onset_minutes=10, event_end_minutes=20)
    zone_b = RainZone(km_from=9.0, km_to=11.0, onset_minutes=40, event_end_minutes=55)
    msg = _onset_msg(_onset_event(km_measured=True, rain_zones=(zone_a, zone_b)))

    _html, plain = render_email(msg)

    assert "Nass km 2-4, km 9-11" in plain, (
        f"AC-10: erwartet 'Nass km 2-4, km 9-11' im Text:\n{plain}"
    )
    assert "km 2-11" not in plain, (
        f"AC-10: KEINE zusammengefasste Huelle 'km 2-11' erlaubt:\n{plain}"
    )


# --------------------------------------------------------------------------
# AC-15: Ortsvergleich-Pfad (`to_multi_location_onset_alert_message`) setzt
#        `rain_zones` nie — S2a aendert `compare_radar_alert.py` nicht.
# --------------------------------------------------------------------------

def test_ac15_ortsvergleich_pfad_setzt_rain_zones_nie():
    from output.renderers.alert.project import to_multi_location_onset_alert_message

    nc = NowcastResult(
        onset_minutes=15, intensity_label="Mäßiger Regen", source="radar",
    )
    msg = to_multi_location_onset_alert_message(
        [("Sillian", nc)], tz=_TZ, stand_at="17:55",
    )

    assert len(msg.events) == 1, f"Testvoraussetzung: genau 1 Event, war {msg.events!r}"
    assert msg.events[0].rain_zones == (), (
        f"AC-15: der Ortsvergleich-Pfad darf rain_zones NIE setzen, erhalten "
        f"{msg.events[0].rain_zones!r}"
    )


# --------------------------------------------------------------------------
# AC-16: keine Ankunftszeit-Rechnung/Handlungsempfehlung in der gerenderten
#        Ausdehnungs-Zeile.
# --------------------------------------------------------------------------

# Muster wie S3-AC-15 (test_onset_reichweite_guete_keine_bevormundung.py)
# plus arrival-time-calculation-spezifische Ergaenzungen fuer S2a.
_VERBOTENE_MUSTER = [
    "verlass dich nicht",
    "solltest du",
    "bis dahin solltest",
    "rechne damit, dass du",
    "sei vorsichtig",
    "achte darauf, dass du",
    "plane damit",
    "du erreichst",
    "wirst du dort",
    "wirst du diese zone",
    "bist du dort",
    "kommst du dort an",
    "wenn du ankommst",
]


def _pruefe(kandidaten: dict[str, str]) -> dict[str, list[str]]:
    gefunden: dict[str, list[str]] = {}
    for name, text in kandidaten.items():
        text_klein = text.lower()
        treffer = [m for m in _VERBOTENE_MUSTER if m in text_klein]
        if treffer:
            gefunden[name] = treffer
    return gefunden


def test_ac16_keine_ankunftszeit_rechnung_oder_handlungsempfehlung():
    """AC-16 GIVEN einen gerenderten Text mit gesetzten Zonen / WHEN er auf
    verbotene Formulierungen geprueft wird / THEN enthaelt er keine.

    Positivkontrolle des DETEKTORS selbst (Lehre aus #2054): ein
    synthetischer, ABSICHTLICH verbotener Satz muss von DERSELBEN
    Pruefschleife erkannt werden — sonst waere die Negativpruefung unten
    trivial wahr."""
    from services.rain_extent import RainZone

    zone = RainZone(km_from=8.0, km_to=12.0, onset_minutes=20, event_end_minutes=40)
    msg = _onset_msg(_onset_event(km_measured=True, rain_zones=(zone,)))
    _html, plain = render_email(msg)

    assert "Nass km 8-12" in plain, (
        f"Testvoraussetzung: die Ausdehnungs-Zeile muss ueberhaupt im Text "
        f"stehen, sonst prueft dieser Test nichts:\n{plain}"
    )

    synthetischer_verstoss = _pruefe({
        "synthetisch": "Nass km 8-12. Du erreichst diese Zone in 45 Minuten.",
    })
    assert synthetischer_verstoss, (
        "Vorbedingung: der Detektor muss einen ABSICHTLICH eingebauten "
        "Verstoss erkennen — sonst waere die Negativpruefung unten trivial "
        "wahr."
    )

    treffer = _pruefe({"email_trip_plain": plain})
    assert not treffer, (
        f"AC-16: verbotene Formulierung gefunden: {treffer}\nText:\n{plain}"
    )


# --------------------------------------------------------------------------
# E4 am WIRKORT (Adversary-Finding F001) und der Ausnahme-Zweig des
# Folgepunkt-Abrufs (F002). Beide nur am Draht pruefbar: die Zusicherung
# entsteht in `check_radar_alerts()`, nicht im Renderer.
# --------------------------------------------------------------------------

# Europe/Vienna (UTC+2 im August) -> 12:00 Ortszeit. Feste Uhr wie
# `test_issue_822_radar_nowcast_segment.UHR_TIROL`: die Punktzahl der
# Mehrpunkt-Abfrage haengt am Zeitanteil des Segments, ohne gestellte Uhr
# waere sie wanduhrabhaengig.
_UHR_TIROL = "2026-08-18T10:00:00+00:00"

# Etappe rein in Nord-Richtung, ~24 km — bei Zeitanteil 87/360 bleiben
# ~18,2 km Reststrecke und damit die vollen sechs Messpunkte (Deckel).
_ZONEN_LAT0, _ZONEN_LON0 = 47.0, 11.0
_ZONEN_LAT1, _ZONEN_LON1 = 47.2158, 11.0


def _nass_spannen(plain: str) -> list[str]:
    """Die einzelnen `km A-B`-Spannen der Ausdehnungs-Angabe (leer: keine)."""
    import re

    treffer = re.search(r"· Nass (km .*)$", plain, re.MULTILINE)
    if not treffer:
        return []
    return [s.strip() for s in treffer.group(1).split(",")]


class _ZonenRadar(RadarNowcastService):
    """Echte `RadarNowcastService`-Unterklasse am DI-Seam von
    `TripAlertService` (Muster `_FixedRadar`,
    `test_alert_log_ereignisgroessen.py`) — liefert je Abruf ein ECHTES
    `NowcastResult`, gesteuert ueber die Reihenfolge der Abrufe.

    Kein Mock: die zurueckgegebenen Objekte sind die Produktiv-Dataclass mit
    ihren echten Feldern; gesteuert wird ausschliesslich, WELCHES Ergebnis ein
    Punkt bekommt.
    """

    def __init__(
        self,
        *,
        trocken_index: int | None = None,
        trocken_felder: dict | None = None,
        ausnahme_index: int | None = None,
        weitere_trockene: tuple[int, ...] = (),
    ) -> None:
        super().__init__()
        self.aufrufe: list[tuple[float, float]] = []
        self._trocken_index = trocken_index
        self._trocken_felder = dict(trocken_felder or {})
        self._ausnahme_index = ausnahme_index
        self._weitere_trockene = set(weitere_trockene)

    def get_nowcast(self, lat, lon, elevation_m=None, priority="user_briefing"):
        i = len(self.aufrufe)
        self.aufrufe.append((lat, lon))
        if i == self._ausnahme_index:
            raise RuntimeError(
                f"Nowcast-Abruf fuer Zonenpunkt {i} absichtlich fehlgeschlagen"
            )
        if i == self._trocken_index:
            return NowcastResult(
                onset_minutes=None, intensity_label="Kein Regen", source="radar",
                **self._trocken_felder,
            )
        if i in self._weitere_trockene:
            return NowcastResult(
                onset_minutes=None, intensity_label="Kein Regen", source="radar",
            )
        return NowcastResult(
            onset_minutes=10, intensity_label="Mäßiger Regen", source="radar",
            window_precip_mm=3.0, event_end_minutes=40,
        )


def _zonen_lauf(radar: _ZonenRadar) -> tuple[int, list[str], str]:
    """Ein echter `check_radar_alerts()`-Lauf auf der Etappe oben.

    Liefert `(sent, nass_spannen, body)`. Der Trip wird als Datei geschrieben
    und vom Pruefling selbst geladen — dieselbe Strecke wie in Produktion.
    """
    import json
    import shutil
    from pathlib import Path

    from freezegun import freeze_time

    from app.loader import get_briefings_dir
    from services.trip_alert import TripAlertService

    uid = f"tdd-2051-s2a-zonen-{uuid.uuid4().hex[:8]}"
    verzeichnis = (
        Path(__file__).resolve().parents[2] / "data" / "users" / uid
    )
    try:
        with freeze_time(_UHR_TIROL):
            luftlinie = haversine_km(
                _ZONEN_LAT0, _ZONEN_LON0, _ZONEN_LAT1, _ZONEN_LON1,
            )
            trip_id = f"tdd-2051-s2a-zonen-trip-{uuid.uuid4().hex[:6]}"
            trips_dir = get_briefings_dir(uid)
            trips_dir.mkdir(parents=True, exist_ok=True)
            data = {
                "id": trip_id, "name": "Zonen Draht Trip",
                "stages": [{
                    "id": "S1", "name": "Tag 1",
                    "date": stage_date(_ZONEN_LAT0, _ZONEN_LON0).isoformat(),
                    "waypoints": [
                        {
                            "id": "WP0", "name": "WP0",
                            "lat": _ZONEN_LAT0, "lon": _ZONEN_LON0,
                            "elevation_m": 1000.0, "arrival_calculated": "11:00",
                            "distance_from_start_km": 0.0,
                        },
                        {
                            "id": "WP1", "name": "WP1",
                            "lat": _ZONEN_LAT1, "lon": _ZONEN_LON1,
                            "elevation_m": 1000.0, "arrival_calculated": "17:00",
                            "distance_from_start_km": round(luftlinie, 3),
                        },
                    ],
                }],
                "report_config": {
                    "trip_id": trip_id, "send_email": True, "send_telegram": False,
                },
            }
            (trips_dir / f"{trip_id}.json").write_text(json.dumps(data))

            captured: list[dict] = []
            svc = TripAlertService(
                throttle_hours=2, user_id=uid, radar_service=radar,
                settings=Settings(
                    smtp_host="test.invalid", smtp_user="u", smtp_pass="p",
                    mail_to="x@example.com",
                ),
                mail_sink=lambda subject, body: captured.append(
                    {"subject": subject, "body": body}
                ),
            )
            svc.clear_radar_throttle(trip_id)
            sent = svc.check_radar_alerts()
            body = captured[0]["body"] if captured else ""
            return sent, _nass_spannen(body), body
    finally:
        shutil.rmtree(verzeichnis, ignore_errors=True)


def test_e4_punkt_ohne_frames_trennt_die_nasszone_nicht():
    """E4 am Wirkort (Adversary-Finding F001): ein Folgepunkt, dessen Ergebnis
    `throttled` bzw. `data_unavailable` traegt, ist eine LUECKE — er darf die
    umgebende Nass-Zone nicht trennen.

    `radar_service.py:987-1001` belegt, dass beide Merkmale immer mit
    `onset_minutes=None` einhergehen. Ohne den Filter in `_zonen_messwert()`
    faellt so ein Punkt in den "trocken"-Zweig von `derive_rain_zones()` und
    erfindet eine trockene Strecke, die niemand gemessen hat.

    Positivkontrolle im dritten Lauf: ein ECHT trockener Punkt an derselben
    Stelle MUSS die Zone trennen — sonst waere die Nicht-Trennungs-Pruefung
    oben trivial wahr, weil dieser Aufbau ueberhaupt nie zwei Zonen erzeugt.
    """
    for merkmal in ("throttled", "data_unavailable"):
        radar = _ZonenRadar(trocken_index=2, trocken_felder={merkmal: True})
        sent, spannen, body = _zonen_lauf(radar)
        assert len(radar.aufrufe) == 6, (
            f"Testvoraussetzung ({merkmal}): sechs Messpunkte erwartet, "
            f"gesehen {len(radar.aufrufe)}: {radar.aufrufe}"
        )
        assert sent >= 1 and spannen, (
            f"Testvoraussetzung ({merkmal}): der Alarm muss ausgeloest und "
            f"eine Ausdehnung gerendert worden sein (sent={sent}, "
            f"spannen={spannen})\nBody:\n{body}"
        )
        assert len(spannen) == 1, (
            f"E4/{merkmal}: der Punkt ohne verwertbare Frames darf die "
            f"Nass-Zone NICHT trennen — erhalten {len(spannen)} Zonen "
            f"{spannen}, erwartet genau eine.\nBody:\n{body}"
        )

    sent_dry, spannen_dry, body_dry = _zonen_lauf(_ZonenRadar(trocken_index=2))
    assert sent_dry >= 1, (
        f"Positivkontrolle: der Alarm muss auch hier ausgeloest haben "
        f"(sent={sent_dry})\nBody:\n{body_dry}"
    )
    assert len(spannen_dry) == 2, (
        f"Positivkontrolle: ein ECHT trockener Punkt an derselben Stelle muss "
        f"die Zone trennen — sonst misst die Pruefung oben nichts. Erhalten "
        f"{len(spannen_dry)} Zonen {spannen_dry}, erwartet zwei.\n"
        f"Body:\n{body_dry}"
    )


def test_ausnahme_beim_folgepunkt_ist_eine_luecke_und_kostet_den_alarm_nicht():
    """Adversary-Finding F002: wirft der Nowcast-Abruf eines FOLGEPUNKTES,
    laeuft der Alarm weiter und der Punkt wird zur Luecke — er wird weder als
    trocken gewertet noch mit dem Ergebnis eines anderen Punktes aufgefuellt.

    Aufbau (sechs Messpunkte): Punkt 0 nass, Punkt 1 wirft, Punkt 2 trocken,
    Punkte 3+4 nass, Punkt 5 trocken. Korrekt ergibt das zwei Zonen, deren
    ERSTE aus dem einzelnen Punkt 0 besteht und deshalb identische Grenzen
    traegt (`km N-N`). Wuerde der Ausnahme-Zweig statt einer Luecke ein
    fremdes (nasses) Ergebnis anhaengen, waere Punkt 1 Teil der ersten Zone
    und ihre Grenzen liefen auseinander — genau daran haengt die Pruefung.

    Pendant zu AC-14 (werfendes `position_at_time`); der Fall fuer
    `get_nowcast` auf Folgepunkten fehlte.
    """
    radar = _ZonenRadar(ausnahme_index=1, weitere_trockene=(2, 5))
    sent, spannen, body = _zonen_lauf(radar)

    assert sent >= 1, (
        f"Der Fehler EINES Folgepunktes darf den Alarm nicht kosten — "
        f"sent={sent}\nBody:\n{body}"
    )
    assert len(radar.aufrufe) == 6, (
        f"Testvoraussetzung: sechs Messpunkte erwartet (der Aufbau haengt "
        f"daran), gesehen {len(radar.aufrufe)}: {radar.aufrufe}"
    )
    assert len(spannen) == 2, (
        f"Erwartet zwei getrennte Zonen (Punkt 0 / Punkte 3+4), erhalten "
        f"{len(spannen)}: {spannen}\nBody:\n{body}"
    )
    von, bis = spannen[0].removeprefix("km ").split("-")
    assert von == bis, (
        f"Der werfende Punkt 1 muss eine LUECKE sein: die erste Zone besteht "
        f"dann allein aus Punkt 0 und traegt identische Grenzen. Erhalten "
        f"'{spannen[0]}' — der Punkt wurde offenbar mit einem fremden "
        f"Ergebnis aufgefuellt.\nBody:\n{body}"
    )
    zweite_von, zweite_bis = spannen[1].removeprefix("km ").split("-")
    assert zweite_von != zweite_bis, (
        f"Positivkontrolle: die zweite Zone (Punkte 3+4) muss auseinander"
        f"laufende Grenzen tragen — sonst koennte die Pruefung oben schon an "
        f"der Rundung haengen. Erhalten '{spannen[1]}'.\nBody:\n{body}"
    )


# --------------------------------------------------------------------------
# Die km-Grenzen an ihrer BILDUNGSSTELLE (Mutations-Befund): alle Tests oben
# setzen ihre Zonen als Literal und bewachen damit nur den Renderer. Eine
# Verschiebung jeder Zonengrenze um 1 km in `rain_extent.derive_rain_zones()`
# bleibt dort unbemerkt.
# --------------------------------------------------------------------------


def _zonen_km_aus_geometrie(radar: _ZonenRadar) -> list[float]:
    """Kilometrierung der TATSAECHLICH abgefragten Punkte, unabhaengig vom
    Pruefling gerechnet.

    Der Produktivweg bildet die km-Lage eines Punktes durch Interpolation von
    `distance_from_start_km` (`trip_segments._lerp_point`). Hier laeuft sie
    ueber die GEOMETRIE: `radar.aufrufe` haelt die Koordinaten, mit denen der
    Nowcast wirklich abgerufen wurde, und die Etappe oben ist eine gerade
    Nord-Strecke mit `distance_from_start_km` 0 am Startwegpunkt. Die
    Kilometrierung eines Punktes ist damit schlicht seine Entfernung von WP0.

    Bewusst NICHT ueber `derive_rain_zones()` oder
    `points_along_remaining_route()` — ein Sollwert, den der Pruefling selbst
    liefert, prueft nichts.
    """
    return [
        haversine_km(_ZONEN_LAT0, _ZONEN_LON0, lat, lon)
        for lat, lon in radar.aufrufe
    ]


def test_zonengrenzen_werden_aus_der_kilometrierung_der_nassen_punkte_gebildet():
    """Die im Text stehenden km-Grenzen muessen den nassen Punkten der
    jeweiligen Zone entsprechen — kleinster km-Wert vorn, groesster hinten.

    Aufbau: sechs Messpunkte, Punkt 2 echt trocken. Er trennt (E2), also zwei
    Zonen aus den Punkten 0+1 bzw. 3+4+5. Der Sollwert wird aus den
    Koordinaten der tatsaechlichen Abrufe abgeleitet, nicht hingeschrieben:
    ein Literal wuerde genau die Stelle ungeprueft lassen, um die es hier
    geht.
    """
    radar = _ZonenRadar(trocken_index=2)
    sent, spannen, body = _zonen_lauf(radar)

    assert sent >= 1 and len(radar.aufrufe) == 6, (
        f"Testvoraussetzung: Alarm ausgeloest und sechs Messpunkte erwartet — "
        f"sent={sent}, Abrufe={radar.aufrufe}\nBody:\n{body}"
    )

    km = _zonen_km_aus_geometrie(radar)
    assert all(a < b for a, b in zip(km, km[1:])), (
        f"Testvoraussetzung: die Messpunkte muessen streckenweise vorwaerts "
        f"laufen, sonst taugt die abgeleitete Kilometrierung nicht: {km}"
    )

    # Gruppierung wie E2: der trockene Punkt trennt, alle uebrigen sind nass.
    nass = [i for i in range(len(km)) if i != 2]
    gruppen: list[list[int]] = []
    for i in nass:
        if gruppen and gruppen[-1][-1] == i - 1:
            gruppen[-1].append(i)
        else:
            gruppen.append([i])

    erwartet = []
    for gruppe in gruppen:
        von_km = min(km[i] for i in gruppe)
        bis_km = max(km[i] for i in gruppe)
        for wert in (von_km, bis_km):
            assert abs(wert - round(wert)) < 0.35, (
                f"Testvoraussetzung: {wert:.3f} km liegt zu dicht an der "
                f"Rundungsgrenze — der Sollwert waere nicht eindeutig."
            )
        erwartet.append(f"km {int(round(von_km))}-{int(round(bis_km))}")

    assert spannen == erwartet, (
        f"Die km-Grenzen der Nass-Zonen muessen aus der Kilometrierung der "
        f"nassen Punkte entstehen.\nErwartet {erwartet} (abgeleitet aus den "
        f"Abruf-Koordinaten: {[round(k, 3) for k in km]}, trocken ist Punkt "
        f"2)\nErhalten {spannen}\nBody:\n{body}"
    )

    # Von/Bis-Zuordnung eigens: eine Vertauschung der beiden Grenzen ergaebe
    # eine rueckwaerts laufende Spanne. Der Vergleich oben faengt das mit,
    # diese Pruefung benennt es.
    for spanne in spannen:
        von, bis = (int(t) for t in spanne.removeprefix("km ").split("-"))
        assert von < bis, (
            f"Die kleinere km-Grenze gehoert nach vorn — '{spanne}' laeuft "
            f"rueckwaerts (km_from/km_to vertauscht).\nBody:\n{body}"
        )


# --------------------------------------------------------------------------
# Rundung der Zonengrenzen (Adversary-Finding F003): in Produktion sind die
# km-Werte Interpolations-Ergebnisse und damit grundsaetzlich fraktional.
# --------------------------------------------------------------------------

def test_fraktionale_zonengrenzen_werden_gerundet_nicht_abgeschnitten():
    """`8.6/11.4` muss als `km 9-11` erscheinen. Die Werte sind so gewaehlt,
    dass Runden und Abschneiden AUSEINANDERLAUFEN (abschneiden ergaebe
    `km 8-11`) — sonst pruefte der Test die Form statt des Werts."""
    from services.rain_extent import RainZone

    zone = RainZone(km_from=8.6, km_to=11.4, onset_minutes=20, event_end_minutes=40)
    msg = _onset_msg(_onset_event(km_measured=True, rain_zones=(zone,)))

    _html, plain = render_email(msg)

    assert "Nass km 9-11" in plain, (
        f"Fraktionale Zonengrenzen 8.6/11.4 muessen gerundet als 'Nass km 9-11' "
        f"erscheinen:\n{plain}"
    )
    assert "km 8-11" not in plain, (
        f"Abgeschnitten statt gerundet ('km 8-11') ist falsch:\n{plain}"
    )
