"""TDD RED — Issue #2009: Datumsbezug am Onset-Zeitpunkt (AC-4, AC-5).

SPEC: docs/specs/modules/fix_2009_nowcast_vorlauf.md

Mit der auf 55 Min angehobenen Onset-Schwelle (#2009) kann der berechnete
Onset-Zeitpunkt ueber Mitternacht rutschen (23:30 + 53 Min = 00:23
Folgetag). `render.py` formatiert `onset_time` heute als reines `%H:%M`
(`utils/timezone.py::local_fmt`) -- ohne Tagesbezug ist "00:23" mehrdeutig
(heute Nacht oder in ueber 23 Stunden?).

`OnsetEvent` (`output/renderers/alert/model.py`) hat noch KEIN
`onset_day_offset`-Feld -- die Konstruktion mit diesem Keyword-Argument
schlaegt heute mit `TypeError: unexpected keyword argument` fehl.

Kein Mock: echte `OnsetEvent`/`AlertMessage`-Objekte durch die echten
Renderer (`render_email`/`render_telegram`/`render_sms`), FESTE
`onset_time`-Werte (keine Wanduhr noetig -- die Renderer lesen `onset_time`
nur aus dem uebergebenen Objekt, s. `test_alert_sms_onset_zeitpunkt.py`
fuer dasselbe Muster).
"""
from __future__ import annotations

import re
from datetime import date as date_type
from zoneinfo import ZoneInfo

from freezegun import freeze_time

from app.loader import save_location
from output.renderers.alert.model import AlertMessage, OnsetEvent
from output.renderers.alert.project import to_multi_location_onset_alert_message
from output.renderers.alert.render import render_email, render_sms, render_telegram
from services.radar_service import NowcastResult

from tests.helpers.nowcast_gate_fixtures import (
    TRIP_LAT, TRIP_LON, CountingFrameSource, clean_uid, compare_radar_service,
    fresh_uid, location, make_trip, radar_preset, reset_radar_cache, save_trip,
    settings_email_only, trip_alert_service, write_presets, write_user_tier,
)


def _onset_event(**kw) -> OnsetEvent:
    """Ein Trip-Radar-Onset-Ereignis mit festen Feldern (keine Wanduhr)."""
    fields = dict(
        onset_minutes=53, onset_time="00:23", km_from=8.0, km_to=8.0,
        is_convective=True, intensity_label="Starker Regen",
        source_label="INCA",
    )
    fields.update(kw)
    return OnsetEvent(**fields)


def _onset_msg(event: OnsetEvent, *, trip_short: str = "KHW 403", source: str = "radar") -> AlertMessage:
    """`source is not None` routet die Renderer in den Onset-Zweig."""
    return AlertMessage(trip_short=trip_short, stand_at="23:30", events=(event,), source=source)


# ═══════════════════════════════ AC-4 ═════════════════════════════════════


def test_ac4_email_and_telegram_show_day_on_rollover():
    """AC-4: Given ein Onset-Zeitpunkt, der ueber Mitternacht rutscht
    (now=23:30 lokal, onset_minutes=53 -> 00:23 Folgetag) / When E-Mail-
    oder Telegram-Text gerendert wird / Then enthaelt der Text einen
    eindeutigen Tagesbezug ("ab morgen 00:23") statt der nackten,
    mehrdeutigen Uhrzeit; Kontrollfall im selben Test: ein Onset ohne
    Tageswechsel bleibt exakt wie bisher (kein "morgen"-Zusatz)."""
    rollover_event = _onset_event(onset_time="00:23", onset_day_offset=1)
    rollover_msg = _onset_msg(rollover_event)

    _, plain = render_email(rollover_msg)
    telegram = render_telegram(rollover_msg)

    assert "ab morgen 00:23" in plain, (
        f"E-Mail-Text traegt keinen eindeutigen Tagesbezug fuer den "
        f"Mitternachts-Ueberlauf (erwartet 'ab morgen 00:23'): {plain!r}"
    )
    assert "ab 00:23" not in plain, (
        f"Die nackte, mehrdeutige Uhrzeit '00:23' ohne Tagesbezug darf nach "
        f"dem Ueberlauf nicht mehr vorkommen: {plain!r}"
    )
    assert "morgen 00:23" in telegram, (
        f"Telegram-Text traegt keinen eindeutigen Tagesbezug fuer den "
        f"Mitternachts-Ueberlauf: {telegram!r}"
    )

    # Kontrollfall: kein Tageswechsel -> Text bleibt EXAKT wie bisher
    # (byte-identisch, kein "morgen"-Zusatz, Regressionsschutz).
    control_event = _onset_event(onset_time="14:05", onset_day_offset=0)
    control_msg = _onset_msg(control_event)
    _, control_plain = render_email(control_msg)
    control_telegram = render_telegram(control_msg)

    assert "ab 14:05" in control_plain, (
        f"Ohne Tageswechsel muss die Uhrzeit unveraendert erscheinen: "
        f"{control_plain!r}"
    )
    assert "morgen" not in control_plain, (
        f"Ohne Tageswechsel darf kein 'morgen'-Zusatz erscheinen (byte-"
        f"identisch zum Bestandsverhalten): {control_plain!r}"
    )
    assert "14:05" in control_telegram and "morgen" not in control_telegram, (
        f"Telegram-Kontrollfall (kein Tageswechsel) muss unveraendert "
        f"bleiben: {control_telegram!r}"
    )


# ═══════════════════════════════ AC-5 ═════════════════════════════════════


def test_ac5_sms_token_carries_day_suffix():
    """AC-5: Given denselben Mitternachts-Ueberlauf-Fall / When die
    Kurznachricht (SMS und Premium-SMS teilen `_render_sms_onset`) gerendert
    wird / Then traegt der Token ein zeichensparendes Tages-Suffix
    ("TH@0:23+1"), bleibt GSM-7-vertraeglich und unter der 160-Zeichen-
    Grenze; ohne Tageswechsel bleibt der Token exakt wie bisher."""
    rollover_event = _onset_event(onset_time="00:23", onset_day_offset=1)
    sms = render_sms(_onset_msg(rollover_event))

    assert "TH@0:23+1" in sms, (
        f"Erwartetes Tages-Suffix-Token 'TH@0:23+1' fehlt in der SMS: {sms!r}"
    )
    assert len(sms) <= 160, f"SMS ueberschreitet die 160-Zeichen-Grenze: {len(sms)} — {sms!r}"

    token_match = re.search(r"(TH|R)@\d{1,2}:\d{2}(?:\+\d+)?", sms)
    assert token_match, f"Kein Onset-Zeitpunkt-Token in der SMS gefunden: {sms!r}"
    token = token_match.group(0)
    assert re.fullmatch(r"[A-Za-z0-9@:+\-]+", token), (
        f"Token enthaelt Zeichen ausserhalb des GSM-7-vertraeglichen Satzes "
        f"(Ziffern/@/:/+/-): {token!r}"
    )

    # Kontrollfall: kein Tageswechsel -> Token bleibt EXAKT wie bisher.
    control_event = _onset_event(onset_time="15:40", onset_day_offset=0)
    control_sms = render_sms(_onset_msg(control_event))
    assert "TH@15:40" in control_sms, (
        f"Ohne Tageswechsel muss der Token unveraendert erscheinen: {control_sms!r}"
    )
    assert "+1" not in control_sms, (
        f"Ohne Tageswechsel darf kein Tages-Suffix erscheinen: {control_sms!r}"
    )


# ═══════════ Fix-Loop F001 (Adversary, CRITICAL) — der WIRKORT ════════════
#
# Die beiden ACs oben pruefen die Renderer mit handgebauten `OnsetEvent`s.
# Damit blieb offen, ob `onset_day_offset` an den ECHTEN Versandpfaden
# ueberhaupt berechnet wird: die Mutation `utils.timezone.day_offset() ->
# return 0` liess die gesamte Zielsuite gruen. Berechnet wurde der Offset
# bis zu diesem Fix nur in `services/radar_alert_service.py`, das
# ausschliesslich der Debug-Endpunkt `api/routers/debug.py` aufruft — kein
# produktiver Alarm kam dort je vorbei.
#
# Die beiden Tests unten fahren deshalb die echten Versandpfade:
#   * Trip:         `TripAlertService.check_radar_alerts()`
#   * Ortsvergleich: `CompareRadarAlertService.check_all_compare_presets()`
# Zustellung ueber den `mail_sink`-Zaehler (kein Netz, kein echter Versand,
# #1477), Uhr ueber `freeze_time` (Muster `test_radar_alert_follows_
# ortstag.py`), Frames ueber die echte `frame_source`-DI-Naht.


def _trip_radar_klartext(zeitpunkt: str, *, ankunft_start: str, ankunft_ende: str) -> str:
    """Ein echter `check_radar_alerts()`-Lauf unter gestellter Uhr; liefert
    den KLARTEXT der zugestellten Mail (`mail_sink` bekommt `plain`,
    notification_service.py:1439).

    Reykjavik-Koordinaten (`make_trip`-Default, ganzjaehrig UTC+0): die
    Ortszeit ist damit direkt aus der gestellten UTC-Zeit ablesbar, ohne
    Zonenrechnung im Test.
    """
    uid = fresh_uid("f001-trip")
    clean_uid(uid)
    try:
        with freeze_time(zeitpunkt):
            write_user_tier(uid, "premium")
            trip = make_trip(
                "trip-f001-rollover", stage_date=date_type.today(),
                arrival_start=ankunft_start, arrival_end=ankunft_ende,
            )
            save_trip(trip, uid)
            reset_radar_cache()
            mails: list = []
            svc = trip_alert_service(
                uid, settings_email_only(), CountingFrameSource(onset_minutes=53),
                lambda subject, body: mails.append((subject, body)),
            )
            sent = svc.check_radar_alerts()
        assert sent == 1 and len(mails) == 1, (
            f"Testvoraussetzung bei {zeitpunkt}: genau EIN Alarm haette "
            f"zugestellt werden muessen, war sent={sent}, mails={len(mails)}"
        )
        return mails[0][1]
    finally:
        clean_uid(uid)


def test_f001_trip_versandpfad_traegt_den_tagesbezug():
    """F001: der Tagesbezug entsteht im ECHTEN Trip-Versandpfad, nicht nur im
    Renderer.

    Hauptfall: 23:30 Ortszeit (Reykjavik = UTC), Onset 53 Min -> 00:23 des
    Folgetags. Die Etappe laeuft 22:00->02:00, das aktive Segment endet also
    erst NACH dem Onset (sonst unterdrueckte der Segment-Ende-Guard aus AC-6
    den Alarm, und der Test maesse diesen statt des Tagesbezugs).

    Gegenprobe im selben Test: derselbe Onset mittags (12:00 -> 12:53) bleibt
    ohne Zusatz. Ohne sie wuerde ein Renderer, der IMMER "morgen" schreibt,
    unbemerkt durchgehen.

    ROT bei der Mutation `utils.timezone.day_offset() -> return 0` (und
    ebenso, wenn `check_radar_alerts()` das Feld gar nicht erst befuellt).
    """
    rollover = _trip_radar_klartext(
        "2026-08-11T23:30:00+00:00", ankunft_start="22:00", ankunft_ende="02:00",
    )
    assert "ab morgen 00:23" in rollover, (
        f"Der Trip-Versandpfad haette den Onset als 'ab morgen 00:23' "
        f"ausweisen muessen (23:30 Ortszeit + 53 Min). Mail:\n{rollover}"
    )

    kontrolle = _trip_radar_klartext(
        "2026-08-11T12:00:00+00:00", ankunft_start="11:00", ankunft_ende="14:00",
    )
    assert "ab 12:53" in kontrolle and "morgen" not in kontrolle, (
        f"Ohne Tageswechsel (12:00 + 53 Min = 12:53) muss der Text "
        f"unveraendert bleiben. Mail:\n{kontrolle}"
    )


def test_f001_compare_versandpfad_traegt_den_tagesbezug_je_ort():
    """F001: derselbe Nachweis fuer den Ortsvergleichs-Versandpfad — und
    zusaetzlich, dass JEDER Ort seine EIGENE Zone benutzt.

    Ein Buendel kann Orte in verschiedenen Zonen tragen. Gestellte Zeit
    21:30 UTC: Wien (UTC+2 im August) steht auf 23:30, der Onset (+53 Min)
    rutscht dort auf 00:23 des Folgetags; Reykjavik (UTC+0) steht auf 21:30,
    der Onset bleibt mit 22:23 am selben Tag. In EINER Mail muessen deshalb
    beide Formen nebeneinander stehen — eine gemeinsame Buendel-Zone waere
    fuer einen der beiden Orte still falsch.

    ROT bei `day_offset() -> return 0` (Wien verliert "morgen") und ebenso
    bei einer Zone, die nicht je Ort aufgeloest wird (dann traegt entweder
    kein Ort oder trage BEIDE den Zusatz).
    """
    uid = fresh_uid("f001-compare")
    clean_uid(uid)
    try:
        with freeze_time("2026-08-11T21:30:00+00:00"):
            write_user_tier(uid, "premium")
            save_location(location("loc-wien", "Wien"), user_id=uid)
            save_location(
                location("loc-rvk", "Reykjavik", lat=TRIP_LAT, lon=TRIP_LON),
                user_id=uid,
            )
            write_presets(uid, [radar_preset(
                "cp-f001", ["loc-wien", "loc-rvk"], user_id=uid,
            )])
            reset_radar_cache()
            mails: list = []
            svc = compare_radar_service(
                uid, settings_email_only(), CountingFrameSource(onset_minutes=53),
                lambda subject, body: mails.append((subject, body)),
            )
            sent = svc.check_all_compare_presets()
        assert sent == 1 and len(mails) == 1, (
            f"Testvoraussetzung: genau EIN Buendel-Alarm haette zugestellt "
            f"werden muessen, war sent={sent}, mails={len(mails)}"
        )
        klartext = mails[0][1]
    finally:
        clean_uid(uid)

    assert "ab morgen 00:23" in klartext, (
        f"Wien (23:30 Ortszeit + 53 Min) haette den Tagesbezug tragen "
        f"muessen. Mail:\n{klartext}"
    )
    assert "ab 22:23" in klartext and "morgen 22:23" not in klartext, (
        f"Reykjavik (21:30 Ortszeit + 53 Min = 22:23) bleibt am selben Tag "
        f"und darf KEINEN Tagesbezug tragen — sonst rechnet das Buendel alle "
        f"Orte in einer gemeinsamen Zone. Mail:\n{klartext}"
    )


def test_f001_compare_kurznachricht_traegt_das_tages_suffix():
    """F001, SMS-Halfte: die Kurznachricht des Ortsvergleichs-Onset-Alarms
    traegt das `+1`-Suffix, wenn der fuehrende Ort ueber Mitternacht rutscht
    — und NICHT, wenn er es nicht tut.

    Wirkort ist `to_multi_location_onset_alert_message()` selbst: dort
    entsteht der Offset des Ortsvergleichs-Pfades (`check_all_compare_
    presets()` -> `send_multi_location_radar_alert()` -> genau diese
    Funktion). Der Kurznachrichten-Renderer zeigt den FUEHRENDEN Ort
    (`render._render_sms_onset`, `msg.events[0]`), deshalb wird die
    Reihenfolge zwischen den beiden Haelften getauscht — das prueft in einem
    Zug, dass die Zone je Ort aufgeloest wird.
    """
    wien = location("loc-wien", "Wien")
    rvk = location("loc-rvk", "Reykjavik", lat=TRIP_LAT, lon=TRIP_LON)
    nc = NowcastResult(
        onset_minutes=53, intensity_label="Starker Regen", source="INCA",
    )

    with freeze_time("2026-08-11T21:30:00+00:00"):
        wien_fuehrt = render_sms(to_multi_location_onset_alert_message(
            [("Wien", wien, nc), ("Reykjavik", rvk, nc)],
            tz=ZoneInfo("Europe/Vienna"), stand_at="23:30",
        ))
        rvk_fuehrt = render_sms(to_multi_location_onset_alert_message(
            [("Reykjavik", rvk, nc), ("Wien", wien, nc)],
            tz=ZoneInfo("Europe/Vienna"), stand_at="23:30",
        ))

    assert "R@0:23+1" in wien_fuehrt, (
        f"Wien rutscht auf 00:23 des Folgetags — die Kurznachricht haette "
        f"'R@0:23+1' tragen muessen: {wien_fuehrt!r}"
    )
    assert len(wien_fuehrt) <= 160, (
        f"Kurznachricht ueberschreitet die 160-Zeichen-Grenze: "
        f"{len(wien_fuehrt)} — {wien_fuehrt!r}"
    )
    assert "R@22:23" in rvk_fuehrt and "+1" not in rvk_fuehrt, (
        f"Reykjavik bleibt am selben Tag (22:23) — kein Tages-Suffix "
        f"erlaubt, und die Zone muss je Ort aufgeloest werden: {rvk_fuehrt!r}"
    )


# ══════════════════════ Zusatzfall: Sommerzeit-Umstellung ═════════════════


def test_day_offset_survives_dst_transition():
    """Zusatz (Team-Lead-Wunsch zu AC-4/AC-5): `utils.timezone.day_offset()`
    vergleicht KALENDERTAGE in der Ortszone, nicht eine feste 24h-Distanz --
    bleibt deshalb auch ueber die Sommerzeit-Umstellung hinweg korrekt (ein
    "Tag" mit 23 Stunden aendert die Kalenderdatums-Differenz nicht).

    Fall: Sommerzeit-Beginn Europe/Berlin 2026-03-29, 02:00 CET -> 03:00 CEST
    (Umstellung bei 01:00 UTC). `now`=00:50 UTC (01:50 CET, VOR dem Sprung),
    Onset +53 Min = 01:43 UTC (03:43 CEST, NACH dem Sprung) -- beide liegen
    auf demselben Kalendertag (29.), day_offset muss 0 liefern, nicht
    faelschlich 1 wegen des uebersprungenen 02:00-03:00-Fensters."""
    from datetime import datetime, timedelta, timezone
    from zoneinfo import ZoneInfo

    from utils.timezone import day_offset

    tz = ZoneInfo("Europe/Berlin")
    now_utc = datetime(2026, 3, 29, 0, 50, tzinfo=timezone.utc)
    onset_utc = now_utc + timedelta(minutes=53)

    assert day_offset(now_utc, onset_utc, tz) == 0, (
        "Sommerzeit-Sprung (23h-Tag) darf einen Onset am selben Kalendertag "
        "nicht faelschlich als Tageswechsel zaehlen"
    )
