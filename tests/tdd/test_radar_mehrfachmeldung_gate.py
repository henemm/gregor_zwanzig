"""WAECHTER (gruen erwartet) — Epic #2261, Scheibe A-2 S2, AC-11: bei dreifach
dichterem Takt (alle 5 statt 15 Minuten) wird dasselbe Ereignis nicht dreifach
gemeldet.

SPEC: docs/specs/modules/feat_2261_a2s2_radar_takt.md AC-11, Abschnitt 9

STATUS: Dieser Test ist mit dem HEUTIGEN Code bereits GRUEN und das ist so
gewollt — er sichert die bestehende Gate-Kette (Sperrzeit / Tageslimit /
Ereignis-Identitaet, #2065) ab, die den 3x-Takt tragen muss. Er wird NICHT
kuenstlich rot gemacht. Rot wird er erst, wenn die Umsetzung von S2 die Kette
aushoehlt (z.B. Radar-Zeitgrenze/Abbruch-Pfad bucht nicht mehr).

Aufbau ohne Netz und ohne lokale TCP-Server: echte ``RadarNowcastService``
mit dem ``frame_source``-Seam (identische nasse Daten), echte Gate-Kette
(``check_nowcast_gate`` ⇒ ThrottleStore/Tageslimit/Ereignis-Register im
isolierten Datenverzeichnis), ``mail_sink`` als Abgriff. Die Uhr wird mit
freezegun in 5-Minuten-Schritten gestellt (Takt), die Quelle liefert in jedem
Lauf dasselbe Ereignis.

Trip-Radar und Ortsvergleich-Radar werden getrennt geprueft. Jede Seite hat
eine Gegenprobe: ein frischer Nutzer OHNE vorherige Laeufe meldet beim selben
Zeitpunkt (Stille kommt vom gebuchten Zustand, nicht von den Daten). Ein
Durchbruch der Sperrzeit (#2065) ist nur mit Zusatzbedingung erlaubt
(Dringlichkeits-Eskalation) — die Daten bleiben hier bewusst identisch.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

from freezegun import freeze_time

from app.loader import save_location, save_trip
from app.models import TripReportConfig
from app.user import SavedLocation
from services.radar_cache import RadarNowcastCacheService
from services.radar_service import RadarNowcastService
from services.trip_alert import TripAlertService

from tests.helpers.compare_briefings import write_compare_briefings
from tests.tdd.test_952_onset_alert_fidelity import _trip_with_active_segment
from tests.tdd.test_compare_radar_alert import (
    _CoordFrameSource,
    _data_root_users,
    _radar_preset,
    _settings_email_capable_dummy,
    _wet_frame,
)
from tests.tdd.test_issue_827_radar_throttle_recording import (
    _make_settings_with_email,
    _wet_frames,
)

_AT = datetime(2026, 4, 5, 10, 0, tzinfo=timezone.utc)
TAKT = timedelta(minutes=5)
ZERMATT = (46.0207, 7.7491)


def _uid(tag: str) -> str:
    return f"tdd-2261s2-gate-{tag}-{uuid.uuid4().hex[:6]}"


def _trip_lauf(uid: str, trip_id: str, at: datetime, mails: list) -> int:
    """Ein Trip-Radar-Lauf zur gestellten Uhrzeit ``at`` (frische Instanz,
    Kontinuitaet nur ueber den Datentraeger — wie ein Cron-Tick)."""
    with freeze_time(at):
        svc = TripAlertService(
            settings=_make_settings_with_email(), user_id=uid,
            radar_service=RadarNowcastService(
                frame_source=_wet_frames, cache=RadarNowcastCacheService(),
            ),
            mail_sink=lambda subject, body: mails.append((subject, body)),
        )
        return svc.check_radar_alerts()


def _trip_aufbau(uid: str, trip_id: str) -> None:
    with freeze_time(_AT):
        trip = _trip_with_active_segment(
            trip_id, TripReportConfig(trip_id=trip_id, send_email=True, alert_on_changes=True),
        )
    save_trip(trip, user_id=uid)


def _compare_aufbau(uid: str, preset_id: str) -> None:
    save_location(
        SavedLocation(id="loc-z", name="Zermatt-Gate", lat=ZERMATT[0], lon=ZERMATT[1], elevation_m=1000),
        user_id=uid,
    )
    write_compare_briefings(
        _data_root_users() / uid, [_radar_preset(preset_id, ["loc-z"], ["gregor-test@henemm.com"])],
    )


def _compare_lauf(uid: str, at: datetime, mails: list) -> int:
    from services.compare_radar_alert import CompareRadarAlertService

    with freeze_time(at):
        radar = RadarNowcastService(
            frame_source=_CoordFrameSource({(round(ZERMATT[0], 4), round(ZERMATT[1], 4)): _wet_frame(8)}),
            cache=RadarNowcastCacheService(),
        )
        svc = CompareRadarAlertService(
            settings=_settings_email_capable_dummy(), user_id=uid, radar_service=radar,
            mail_sink=lambda subject, body: mails.append((subject, body)),
        )
        return svc.check_all_compare_presets()


def test_drei_radar_laeufe_gleiche_daten_hoechstens_eine_meldung():
    """AC-11: Given identische Wetterdaten mit ausloesendem Regenbeginn fuer
    einen Trip bzw. einen Ortsvergleich / When drei Radar-Laeufe im 5-Minuten-
    Takt hintereinander laufen (echte Gate-Kette, echtes ``tmp_path``-
    Datenverzeichnis) / Then wird insgesamt hoechstens EINE Meldung
    versendet — Trip-Radar und Ortsvergleich-Radar getrennt geprueft.

    Waechter, GRUEN erwartet (s. Moduldoku)."""
    # --- Trip-Radar --------------------------------------------------------
    uid = _uid("trip")
    _trip_aufbau(uid, "trip-gate")
    mails: list = []
    sent = [_trip_lauf(uid, "trip-gate", _AT + i * TAKT, mails) for i in range(3)]
    assert sent[0] == 1, f"Voraussetzung: Lauf 1 muss melden, war {sent!r}"
    assert sum(sent) <= 1 and len(mails) <= 1, (
        f"Trip-Radar: dasselbe Ereignis in drei Laeufen darf hoechstens einmal "
        f"gemeldet werden, war {sent!r} / {len(mails)} Mails"
    )
    # Gegenprobe: frischer Nutzer OHNE Vorlaeufe meldet zum Zeitpunkt von Lauf 3.
    ctrl = _uid("tripctrl")
    _trip_aufbau(ctrl, "trip-gate")
    ctrl_mails: list = []
    assert _trip_lauf(ctrl, "trip-gate", _AT + 2 * TAKT, ctrl_mails) == 1, (
        "Gegenprobe: ohne vorherige Laeufe muss derselbe Zeitpunkt melden — "
        "die Stille oben kommt vom gebuchten Zustand"
    )

    # --- Ortsvergleich-Radar ----------------------------------------------
    cuid = _uid("cmp")
    _compare_aufbau(cuid, "cp-gate")
    c_mails: list = []
    c_sent = [_compare_lauf(cuid, _AT + i * TAKT, c_mails) for i in range(3)]
    assert c_sent[0] == 1, f"Voraussetzung: Lauf 1 muss melden, war {c_sent!r}"
    assert sum(c_sent) <= 1 and len(c_mails) <= 1, (
        f"Ortsvergleich-Radar: hoechstens eine Meldung, war {c_sent!r} / {len(c_mails)} Mails"
    )
    cctrl = _uid("cmpctrl")
    _compare_aufbau(cctrl, "cp-gate")
    cc_mails: list = []
    assert _compare_lauf(cctrl, _AT + 2 * TAKT, cc_mails) == 1, (
        "Gegenprobe: ohne vorherige Laeufe muss derselbe Zeitpunkt melden"
    )
