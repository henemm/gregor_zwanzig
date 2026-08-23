"""TDD RED — Issue #2096 AC-15: das Fixture-Etappendatum stammt aus der
ORTSZEIT, nicht aus dem Systemdatum.

SPEC: docs/specs/modules/fix_2096_tagesbezug_testwaechter.md — AC-15.

Warum das zaehlt: `_active_window()`
(`tests/tdd/test_952_onset_alert_fidelity.py:125-148`) rechnet das
Etappenfenster in Ortszeit (Korsika, `Europe/Paris`, UTC+2),
`_trip_with_active_segment()` (`:150-177`) stempelt es aber mit
`date_type.today()` -- dem SYSTEMdatum (UTC). Ab 22:00 UTC weichen beide um
einen Tag ab, das Segment landet rund 24 Stunden in der Vergangenheit, die
Aktivitaetspruefung `seg.start_time <= now_utc <= seg.end_time` schlaegt fehl
und `check_radar_alerts()` liefert `0` statt `1` -- zwei rote CI-Tests jeden
Abend, ohne Produktivdefekt (echte Trips tragen echte `stage.date`-Werte;
`trip_alert.py:1246-1249` loest "heute" ueber `trip_local_today()` in
Ortszeit auf, ADR-0044).

Dieser Test haelt die Reparatur fest: bei gestellter Uhr NACH 22:00 UTC, wo
Systemdatum und Ortsdatum nachweislich auseinanderfallen, muss der 952-Aufbau
weiterhin einen Alarm liefern.

Mock-frei: echter `TripAlertService`, echter DI-Seam `_GuaranteedWetRadar`
(echte `RadarNowcastService`-Subklasse), echte Persistenz ueber
`app.loader.save_trip()`, echte `mail_sink`-Senke statt Versand. Aufbau und
Radar-Seam werden aus der Bestandsdatei IMPORTIERT statt kopiert -- eine
Kopie wuerde die Reparatur dort nicht mitbekommen.

RED heute: `_trip_with_active_segment()` verwendet `date_type.today()` --
`check_radar_alerts()` liefert `0`.
"""
from __future__ import annotations

import inspect
from datetime import datetime, timezone
from pathlib import Path

from freezegun import freeze_time

from app.config import Settings
from app.models import TripReportConfig
from utils.timezone import tz_for_coords

from tests.tdd.test_952_onset_alert_fidelity import (
    _GuaranteedWetRadar,
    _clean_user,
    _trip_with_active_segment,
)

# 23:30 UTC -- auf Korsika (UTC+2) ist es dann bereits 01:30 des Folgetages.
_GEFRORENE_UHR = "2026-08-22 23:30:00+00:00"


def test_prueling_stammt_aus_diesem_arbeitsbaum():
    """Vorbedingung (kein AC): der Alarm-Service wird RELATIV ZU DIESER
    Testdatei aufgeloest, nicht aus dem Hauptrepo-Pfad."""
    from services import trip_alert as trip_module

    arbeitsbaum = Path(__file__).resolve().parents[2]
    modul_pfad = Path(inspect.getfile(trip_module)).resolve()
    assert modul_pfad.is_relative_to(arbeitsbaum), (
        f"Prueling stammt nicht aus diesem Arbeitsbaum: {modul_pfad}"
    )


@freeze_time(_GEFRORENE_UHR)
def test_ac15_radar_alarm_feuert_wenn_ortsdatum_vom_systemdatum_abweicht():
    """AC-15 GIVEN eine gestellte Uhr nach 22:00 UTC, bei der das Systemdatum
    (UTC) und das Ortsdatum des Trips (Korsika, UTC+2) auseinanderfallen
    WHEN der 952-Aufbau `check_radar_alerts()` faehrt
    THEN liefert er 1 statt 0, und genau eine Alarm-Mail geht in die Senke.

    Die Abweichung der beiden Daten wird als Vorbedingung GEMESSEN, nicht
    behauptet: liefe die Suite in einer Zone, in der beide Daten
    zusammenfielen, pruefte der Test nichts und muss das sagen
    (`reference_positivkontrolle_prueft_ob_die_pruefung_misst`).

    RED heute: `_trip_with_active_segment()` stempelt das Etappendatum mit
    `date_type.today()`; das Segment liegt damit einen Tag zurueck und
    `check_radar_alerts()` liefert `0`."""
    uid = "tdd-2096-ac15"
    trip_id = "trip-2096-ac15"
    _clean_user(uid)
    try:
        config = TripReportConfig(
            trip_id=trip_id, send_email=True, send_telegram=False,
            send_sms=False, alert_on_changes=True,
        )
        trip = _trip_with_active_segment(trip_id, config)

        # Die Koordinaten kommen aus dem Aufbau selbst, nicht aus einer
        # zweiten Kopie im Test -- sonst maesse die Vorbedingung eine andere
        # Zone als die, in der das Segment liegt.
        wp = trip.stages[0].waypoints[0]
        jetzt_utc = datetime.now(timezone.utc)
        ortszeit = jetzt_utc.astimezone(tz_for_coords(wp.lat, wp.lon))
        assert ortszeit.date() != jetzt_utc.date(), (
            "Vorbedingung: bei dieser gestellten Uhr MUESSEN Ortsdatum "
            f"({ortszeit.date()}) und Systemdatum ({jetzt_utc.date()}) "
            "auseinanderfallen, sonst prueft der Fall den Fehler nicht"
        )

        from app.loader import save_trip
        save_trip(trip, user_id=uid)

        settings = Settings().model_copy(update={
            "smtp_host": "smtp.test.invalid", "smtp_user": "alert@test.invalid",
            "smtp_pass": "secret", "mail_to": "gregor-test@henemm.com",
            "smtp_port": 587, "is_test_mode": False,
            "telegram_bot_token": "", "telegram_chat_id": "",
            "sms_gateway_url": "", "seven_api_key": "", "sms_to": "",
        })
        mail_calls: list[tuple[str, str]] = []
        from services.trip_alert import TripAlertService
        svc = TripAlertService(
            settings=settings, throttle_hours=0, user_id=uid,
            radar_service=_GuaranteedWetRadar(
                onset_minutes=12, intensity_label="leichter Regen",
                is_convective=False,
            ),
            mail_sink=lambda subject, body: mail_calls.append((subject, body)),
        )

        result = svc.check_radar_alerts()

        assert result == 1, (
            "check_radar_alerts() sollte bei gestellter Uhr "
            f"{_GEFRORENE_UHR} genau 1 Alarm liefern, war {result} -- das "
            "Etappendatum stammt aus dem Systemdatum statt aus der Ortszeit "
            f"(Etappe: {trip.stages[0].date}, Ortsdatum: {ortszeit.date()})"
        )
        assert len(mail_calls) == 1, (
            f"Genau EINE Alarm-Mail erwartet, waren {len(mail_calls)}"
        )
    finally:
        _clean_user(uid)
