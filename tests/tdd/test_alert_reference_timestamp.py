"""TDD RED — Issue #1916, AC-Gruppe A ("Sichtbarkeit").

SPEC: docs/specs/modules/trip_alert.md v3.0, AC-1..AC-5.

Der Referenz-Zeitpunkt der tatsaechlich verglichenen Vergleichsbasis muss in
der Alarmnachricht sichtbar werden, statt des generischen Texts "verglichen
mit dem letzten Briefing" (``render.py:517,562,807``). Kern-Schicht,
deterministisch (kein Netz): Slice 1 braucht KEINE Datei-Snapshots --
``SegmentWeatherData.fetched_at`` traegt den Referenz-Zeitstempel bereits
(Spec-Abschnitt "AC-Gruppe A"), deshalb wird ``cached``/``fresh_weather``
direkt an ``check_and_send_alerts()`` uebergeben (Vorbild:
``test_alert_channel_threshold.py:409-412``). Transport ueber ``mail_sink``.

AC-3 (SMS-Laengenbudget) ruft ``to_alert_message()``/``render_sms()`` DIREKT
auf und nimmt an, dass ``to_alert_message()`` (project.py MODIFY-Zeile der
Spec) einen neuen ``reference_at``-Keyword-Parameter bekommt -- begruendete
Annahme (Spec nennt project.py als Durchreiche-Stelle fuer den neuen
Referenz-Zeitpunkt), dokumentiert hier statt geraten und verschwiegen.
"""
from __future__ import annotations

import dataclasses
import uuid
from datetime import date, datetime, time as dtime, timedelta, timezone

from app.models import ChangeSeverity, WeatherChange
from utils.timezone import local_fmt, tz_for_coords

from tests.helpers.alert_log_fixtures import (
    LAT, LON, gust_alert_trip, settings_email_only, weather,
)

_GENERISCHER_TEXT = "verglichen mit dem letzten Briefing"


def _wetter(gust_kmh: float, fetched_at: datetime):
    return dataclasses.replace(weather(1, gust_max_kmh=gust_kmh), fetched_at=fetched_at)


def _lauf(user_id: str, trip_id: str, anker_zeit: datetime):
    from services.trip_alert import TripAlertService

    trip = gust_alert_trip(trip_id)
    mails: list[tuple[str, str]] = []
    svc = TripAlertService(
        settings=settings_email_only(), user_id=user_id,
        mail_sink=lambda subject, body: mails.append((subject, body)),
    )
    ausgeloest = svc.check_and_send_alerts(
        trip, [_wetter(10.0, anker_zeit)],
        fresh_weather=[_wetter(120.0, datetime.now(timezone.utc))],
    )
    return ausgeloest, mails


def test_ac1_email_footer_zeigt_referenz_zeitpunkt_statt_generischen_text():
    """AC-1: Footer zeigt HH:MM des tatsaechlich verglichenen Ankers.

    HEUTE ROT: ``notification_service.send_deviation_alert()`` speist
    ``stand_at`` aus ``datetime.now()`` (Zeile 652) statt aus dem Anker, und
    ``render.py`` haelt den generischen Text hart verdrahtet.
    """
    tz = tz_for_coords(LAT, LON)
    anker_zeit = datetime.now(timezone.utc) - timedelta(hours=3)
    erwartete_zeit = local_fmt(anker_zeit, tz)

    ausgeloest, mails = _lauf(
        f"tdd-1916-ac1-{uuid.uuid4().hex[:8]}", "trip-ac1", anker_zeit,
    )

    assert ausgeloest, "Fixtur-Schutz: das massive Delta muss ausloesen."
    assert mails, "Fixtur-Schutz: es muss eine Mail geben."
    _subject, body = mails[-1]
    assert _GENERISCHER_TEXT not in body, (
        f"AC-1: der generische Text '{_GENERISCHER_TEXT}' darf nicht mehr "
        f"erscheinen. Mail-Body:\n{body}"
    )
    assert erwartete_zeit in body, (
        f"AC-1: der Footer muss den Referenz-Zeitpunkt des Ankers "
        f"({erwartete_zeit}) zeigen. Mail-Body:\n{body}"
    )


def test_ac2_anker_von_anderem_kalendertag_traegt_expliziten_tagesbezug():
    """AC-2: Anker von GESTERN (anderer Ortstag) -> der Footer nennt den Tag
    explizit (Spec-Beispiel: "gestern HH:MM Uhr"), nicht nur eine nackte Zeit.

    Angenommene Wortwahl ("gestern"): das Spec-Beispiel, keine Pflichtformel
    -- waehlt die Implementierung eine andere Formulierung, muss NUR diese
    eine Zusicherung angepasst werden.
    """
    tz = tz_for_coords(LAT, LON)
    heute = date.today()
    gestern = heute - timedelta(days=1)
    anker_lokal = datetime.combine(gestern, dtime(18, 3), tzinfo=tz)
    anker_zeit = anker_lokal.astimezone(timezone.utc)
    assert anker_lokal.date() != heute, "Fixtur-Schutz: Anker muss von gestern sein."

    ausgeloest, mails = _lauf(
        f"tdd-1916-ac2-{uuid.uuid4().hex[:8]}", "trip-ac2", anker_zeit,
    )

    assert ausgeloest and mails, "Fixtur-Schutz"
    _subject, body = mails[-1]
    erwartete_zeit = local_fmt(anker_zeit, tz)
    assert "gestern" in body.lower(), (
        f"AC-2: ein Anker von einem anderen Kalendertag braucht einen "
        f"expliziten Tagesbezug ('gestern'). Mail-Body:\n{body}"
    )
    assert erwartete_zeit in body, (
        f"AC-2: die Uhrzeit des Ankers ({erwartete_zeit}) muss trotzdem "
        f"erscheinen. Mail-Body:\n{body}"
    )


def test_ac3_sms_referenz_zeitpunkt_haelt_160_zeichen_budget_ein():
    """AC-3: SMS/Premium-SMS teilen sich denselben ``render_sms()``-Aufruf
    (``notification_service.py:1359/1543``) -- ein Test deckt beide Kanaele.

    Maximale Event-Anzahl (6 unzweideutige Metriken) UND Referenz-Zeitpunkt
    im Text: Gesamtlaenge bleibt <=160 (tatsaechliches Budget: 140, s.
    ``render_sms(limit=140)``), der Referenz-Text muss TROTZDEM im Ergebnis
    auftauchen (kein "Feld existiert, wird aber nie gerendert").

    HEUTE ROT: ``to_alert_message()`` kennt kein ``reference_at`` -> TypeError.
    """
    from output.renderers.alert.project import to_alert_message
    from output.renderers.alert.render import render_sms

    tz = tz_for_coords(LAT, LON)
    now = datetime.now(timezone.utc)
    segment = weather(1, gust_max_kmh=1.0).segment
    weather_data = [dataclasses.replace(weather(1, gust_max_kmh=1.0), fetched_at=now)]
    felder = [
        ("wind_max_kmh", 25.0, 55.0),
        ("gust_max_kmh", 30.0, 70.0),
        ("precip_sum_mm", 1.0, 8.5),
        ("pop_max_pct", 20.0, 80.0),
        ("cape_max_jkg", 200.0, 1500.0),
        ("uv_index_max", 3.0, 9.0),
    ]
    changes = [
        WeatherChange(
            metric=feld, old_value=alt, new_value=neu, delta=neu - alt,
            threshold=(neu - alt) / 2, severity=ChangeSeverity.MAJOR,
            direction="increase", segment_id="1", occurred_at=None,
        )
        for feld, alt, neu in felder
    ]

    msg = to_alert_message(
        changes, weather_data, "Sehr Langer Absurder Tournamensname",
        tz=tz, stand_at="10:00", reference_at="18:03",
    )
    sms = render_sms(msg)

    assert len(sms) <= 160, (
        f"AC-3: SMS/Premium-SMS duerfen 160 Zeichen nie ueberschreiten "
        f"(gemessen: {len(sms)}). Text: {sms!r}"
    )
    assert "18:03" in sms, (
        f"AC-3: der Referenz-Zeitpunkt muss trotz Kuerzungsdruck im Text "
        f"erscheinen. Text: {sms!r}"
    )


def test_ac4_compare_pfad_zeigt_referenz_zeitpunkt_ueber_denselben_renderer():
    """AC-4: der Ortsvergleich-Δ-Alarm teilt sich E-Mail- UND SMS-Renderer
    mit dem Trip-Pfad (``to_multi_point_alert_message`` -> ``render_email``/
    ``render_sms``) -- Slice 1 muss dort automatisch mitwirken.

    HEUTE ROT: ``to_multi_point_alert_message()`` kennt kein
    ``reference_at`` -> TypeError.
    """
    from output.renderers.alert.project import to_multi_point_alert_message
    from output.renderers.alert.render import render_email, render_sms

    tz = tz_for_coords(LAT, LON)
    punkt = weather(1, gust_max_kmh=1.0).segment.start_point
    change = WeatherChange(
        metric="gust_max_kmh", old_value=10.0, new_value=100.0, delta=90.0,
        threshold=20.0, severity=ChangeSeverity.MAJOR, direction="increase",
        segment_id="1", occurred_at=None,
    )
    msg = to_multi_point_alert_message(
        [("Testort", [change], punkt)], tz=tz, stand_at="14:00",
        reference_at="13:10",
    )

    _html, plain = render_email(msg)
    sms = render_sms(msg)

    assert _GENERISCHER_TEXT not in plain, (
        f"AC-4: der generische Text darf auch im Compare-Pfad nicht mehr "
        f"erscheinen. Mail-Body:\n{plain}"
    )
    assert "13:10" in plain, (
        f"AC-4: der Referenz-Zeitpunkt der Compare-Snapshot-Quelle muss im "
        f"E-Mail-Footer erscheinen. Mail-Body:\n{plain}"
    )
    assert "13:10" in sms, (
        f"AC-4: derselbe Referenz-Zeitpunkt muss auch im SMS-Text erscheinen. "
        f"Text: {sms!r}"
    )


def test_ac4_compare_wiring_ueber_echten_aufrufpfad_liefert_referenz_zeitpunkt():
    """AC-4 (Wiring, Fix-Loop F001): der ECHTE Aufrufpfad
    ``compare_alert.py::CompareAlertService.check_all_compare_presets()`` ->
    ``NotificationService.send_multi_location_deviation_alert()`` ->
    ``to_multi_point_alert_message()`` -> ``render_email()`` reicht den
    Referenz-Zeitpunkt der Compare-eigenen Snapshot-Quelle
    (``CompareWeatherSnapshotService``) durch — nicht nur der isolierte
    Renderer-Aufruf oben (``test_ac4_compare_pfad_...``).

    HEUTE ROT ohne den Fix-Loop-Fix: ``compare_alert.py`` extrahierte
    ``fetched_at`` nie aus dem geladenen Anker, der Footer zeigte weiterhin
    den generischen Text "verglichen mit dem letzten Briefing".
    """
    from app.loader import get_data_dir, save_location
    from app.models import SegmentWeatherSummary
    from app.user import SavedLocation
    from services.compare_alert import CompareAlertService
    from services.compare_weather_snapshot import CompareWeatherSnapshotService
    from services.point_weather import PointWeatherData
    from tests.helpers.compare_briefings import write_compare_briefings

    class _FixedWeatherSource:
        """Deterministischer `LocationWeatherSource`-Impl (kein Mock) —
        liefert einen festen Frischwert, Vorbild `_ScriptedWeatherSource`
        aus `test_issue_1169_compare_alert_consumer.py`."""

        def __init__(self, precip_sum_mm: float) -> None:
            self._val = precip_sum_mm

        def fetch(self, point_id, lat, lon, start_hour=None, end_hour=None):
            return PointWeatherData(
                id=point_id, name=point_id, lat=lat, lon=lon, timeseries=None,
                aggregated=SegmentWeatherSummary(precip_sum_mm=self._val),
                fetched_at=datetime.now(timezone.utc), provider="test",
            )

    uid = f"tdd-1916-ac4wire-{uuid.uuid4().hex[:8]}"
    preset_id = "cp-1916-ac4wire"
    location_id = "loc-x"
    loc = SavedLocation(id=location_id, name="Vergleichsort", lat=LAT, lon=LON, elevation_m=1000)
    save_location(loc, user_id=uid)
    preset = {
        "id": preset_id, "name": preset_id, "user_id": "default",
        "location_ids": [location_id], "schedule": "daily", "weekday": 4,
        "profil": "ALLGEMEIN", "hour_from": 9, "hour_to": 16,
        "empfaenger": ["dummy@example.com"], "letzter_versand": None,
        "top_ort_letzter_versand": None, "created_at": "2026-07-09T00:00:00Z",
        "cooldown_minutes": 0,
    }
    write_compare_briefings(get_data_dir(uid), [preset])

    anker_zeit = datetime.now(timezone.utc) - timedelta(hours=2)
    CompareWeatherSnapshotService(user_id=uid).save(
        preset_id, location_id,
        PointWeatherData(
            id=location_id, name=loc.name, lat=loc.lat, lon=loc.lon, timeseries=None,
            aggregated=SegmentWeatherSummary(precip_sum_mm=2.0),
            fetched_at=anker_zeit, provider="test",
        ),
    )

    mails: list[tuple[str, str]] = []
    service = CompareAlertService(
        settings=settings_email_only(), user_id=uid,
        weather_source=_FixedWeatherSource(20.0),  # Δ=18 >= Standard-Schwelle 10
        mail_sink=lambda subject, body: mails.append((subject, body)),
    )
    sent = service.check_all_compare_presets()

    assert sent == 1, "Fixtur-Schutz: das Delta (18 mm) muss ausloesen."
    assert mails, "Fixtur-Schutz: es muss eine Mail geben."
    _subject, body = mails[-1]
    tz = tz_for_coords(loc.lat, loc.lon)
    erwartete_zeit = local_fmt(anker_zeit, tz)
    assert _GENERISCHER_TEXT not in body, (
        f"AC-4 (Wiring): der generische Text darf ueber den ECHTEN "
        f"compare_alert.py-Aufrufpfad nicht mehr erscheinen. Mail-Body:\n{body}"
    )
    assert erwartete_zeit in body, (
        f"AC-4 (Wiring): der Referenz-Zeitpunkt des Compare-Ankers "
        f"({erwartete_zeit}) muss im Mail-Body erscheinen. Mail-Body:\n{body}"
    )


def test_ac5_regression_korridor_only_footer_bleibt_unveraendert():
    """AC-5 (REGRESSIONSSCHUTZ, erwartet GRUEN): reine Schwellen-/Radar-
    Alarme (kein Δ-Vergleich) behalten "Stand: heute HH:MM" unveraendert --
    Slice 1 betrifft ausschliesslich Δ-Vergleichs-Alarme.
    """
    from output.renderers.alert.model import AlertMessage, CorridorEvent
    from output.renderers.alert.render import render_email

    ce = CorridorEvent(
        metric_id="gust", value=55.0, bound=50.0, direction="above",
        occurred_at="14:00", km_from=0.0, km_to=5.0,
    )
    msg = AlertMessage(
        trip_short="Testtour", stand_at="14:00", events=(), source=None,
        corridor_events=(ce,),
    )
    _html, plain = render_email(msg)

    assert "Stand: heute 14:00" in plain, (
        f"AC-5: der Korridor-Footer muss weiterhin 'Stand: heute HH:MM' "
        f"zeigen (Regressions-Invariante). Body:\n{plain}"
    )
    assert _GENERISCHER_TEXT not in plain and "reference_at" not in plain.lower(), (
        f"AC-5: reine Schwellen-Alarme duerfen KEINEN Referenz-Zeitpunkt- "
        f"Zusatz bekommen -- das ist ausschliesslich Δ-Vergleichs-Alarmen "
        f"vorbehalten. Body:\n{plain}"
    )
