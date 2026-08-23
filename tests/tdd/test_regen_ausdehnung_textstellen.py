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
from services.radar_service import NowcastResult
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
