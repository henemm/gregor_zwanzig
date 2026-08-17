"""TDD RED — Issue #1916, AC-Gruppe B ("Rollierende Basis"), AC-6..AC-8.

SPEC: docs/specs/modules/trip_alert.md v3.0, ADR-0056.

Dritter, rollierender Anker-Typ mit Hybrid-Schreibtrigger: (a) bei jedem
tatsaechlich versendeten Alarm, (b) opportunistisch beim Ueberschreiten der
4h-Alterungs-Ceiling. Kern-Schicht, deterministisch: ``cached_weather``/
``fresh_weather`` werden DIREKT an ``check_and_send_alerts()`` uebergeben
(Vorbild ``test_alert_channel_threshold.py:409-412``) -- der Schreibpfad ist
Teil dieser Methode selbst (Spec-Tabelle: "trip_alert.py MODIFY ... neuer
Schreibpfad nach jedem Check-Lauf"), unabhaengig davon, wie ``cached``
zustande kam.

Angenommene API (Spec Zeile 69, "z.B."): ``WeatherSnapshotService.
save_alarm_anchor()``/``load_alarm_anchor()``, Rueckgabetyp wie die
Geschwistermethoden ``load()``/``load_dated()``
(``Optional[list[SegmentWeatherData]]``). Aendert die Implementierung die
Namen, betrifft das nur die Aufrufstellen hier, nicht die Zusicherungen
selbst.
"""
from __future__ import annotations

import dataclasses
import uuid
from datetime import date, datetime, timedelta, timezone

from tests.helpers.alert_log_fixtures import gust_alert_trip, settings_email_only, weather


def _wetter(gust_kmh: float, fetched_at: datetime):
    return dataclasses.replace(weather(1, gust_max_kmh=gust_kmh), fetched_at=fetched_at)


def _aware(dt: datetime) -> datetime:
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


def test_ac6_erfolgreicher_alarmversand_schreibt_rollierenden_anker():
    """AC-6: Trigger (a) -- ein tatsaechlich versendeter Alarm schreibt einen
    frischen rollierenden Anker, unabhaengig von einem vorherigen Briefing.

    HEUTE ROT: ``load_alarm_anchor()`` existiert nicht -> AttributeError.
    """
    from services.trip_alert import TripAlertService
    from services.weather_snapshot import WeatherSnapshotService

    user_id, trip_id = f"tdd-1916-ac6-{uuid.uuid4().hex[:8]}", "trip-ac6"
    trip = gust_alert_trip(trip_id)
    svc = TripAlertService(settings=settings_email_only(), user_id=user_id)
    vor_lauf = datetime.now(timezone.utc)

    ausgeloest = svc.check_and_send_alerts(
        trip, [_wetter(10.0, vor_lauf - timedelta(hours=1))],
        fresh_weather=[_wetter(150.0, vor_lauf)],
    )

    assert ausgeloest, "Fixtur-Schutz: das massive Delta muss ausloesen."
    anker = WeatherSnapshotService(user_id=user_id).load_alarm_anchor(trip_id)
    assert anker, (
        "AC-6: nach einem tatsaechlich versendeten Alarm MUSS ein "
        "rollierender Anker existieren -- unabhaengig von einem Briefing."
    )
    assert _aware(anker[0].fetched_at) >= vor_lauf, (
        f"AC-6: der geschriebene Anker muss den AKTUELLEN Wetterstand "
        f"tragen (fetched_at={anker[0].fetched_at}, Lauf-Start={vor_lauf})."
    )


def test_ac7_ueberschrittene_ceiling_schreibt_opportunistisch_ohne_alarm():
    """AC-7: Trigger (b) -- 5h alter Anker + unterschwelliges Δ: trotz
    ausbleibendem Alarm wird opportunistisch ein frischer Anker geschrieben.

    HEUTE ROT: ``load_alarm_anchor()`` existiert nicht -> AttributeError.
    """
    from services.trip_alert import TripAlertService
    from services.weather_snapshot import WeatherSnapshotService

    user_id, trip_id = f"tdd-1916-ac7-{uuid.uuid4().hex[:8]}", "trip-ac7"
    trip = gust_alert_trip(trip_id)
    svc = TripAlertService(settings=settings_email_only(), user_id=user_id)
    vor_lauf = datetime.now(timezone.utc)
    alter_anker = vor_lauf - timedelta(hours=5)

    ausgeloest = svc.check_and_send_alerts(
        trip, [_wetter(10.0, alter_anker)],
        fresh_weather=[_wetter(12.0, vor_lauf)],
    )

    assert not ausgeloest, "Fixtur-Schutz: das Delta (2 km/h) darf NICHT ausloesen."
    anker = WeatherSnapshotService(user_id=user_id).load_alarm_anchor(trip_id)
    assert anker, (
        "AC-7: trotz fehlendem Alarm muss die Ueberschreitung der 4h-Ceiling "
        "opportunistisch einen frischen rollierenden Anker schreiben."
    )
    assert _aware(anker[0].fetched_at) >= vor_lauf, (
        "AC-7: der opportunistisch geschriebene Anker muss den AKTUELLEN "
        f"Wetterstand tragen (fetched_at={anker[0].fetched_at})."
    )


def test_ac8_lange_ausfallserie_wird_automatisch_binnen_ceiling_aufgefrischt():
    """AC-8 (End-to-End-Symptomnachweis): mehrere Check-Laeufe in Folge, JEDER
    MIT DEMSELBEN ~28h alten (nie erneuerten) Briefing-Anker als ``cached`` --
    simuliert einen ueber Stunden ausgefallenen Briefing-Versand (#1897).
    Nach spaetestens einem Lauf liegt das rollierende Anker-Alter innerhalb
    der 4h-Ceiling -- das urspruengliche #1916-Symptom (~24h alte Basis)
    tritt nicht mehr auf.

    HEUTE ROT: ``load_alarm_anchor()`` existiert nicht -> AttributeError.
    """
    from services.trip_alert import TripAlertService
    from services.weather_snapshot import WeatherSnapshotService

    user_id, trip_id = f"tdd-1916-ac8-{uuid.uuid4().hex[:8]}", "trip-ac8"
    trip = gust_alert_trip(trip_id)
    svc = TripAlertService(settings=settings_email_only(), user_id=user_id)
    snap_svc = WeatherSnapshotService(user_id=user_id)
    uralter_anker = datetime.now(timezone.utc) - timedelta(hours=28)

    for _ in range(3):
        svc.check_and_send_alerts(
            trip, [_wetter(10.0, uralter_anker)],
            fresh_weather=[_wetter(12.0, datetime.now(timezone.utc))],
        )

    anker = snap_svc.load_alarm_anchor(trip_id)
    assert anker, "AC-8: nach mehreren Laeufen MUSS ein rollierender Anker existieren."
    alter = datetime.now(timezone.utc) - _aware(anker[0].fetched_at)
    assert alter <= timedelta(hours=4, minutes=5), (
        f"AC-8: die 4h-Ceiling muss eingehalten sein (gemessen: "
        f"{alter.total_seconds() / 3600:.2f} h) -- sonst besteht das "
        f"urspruengliche #1916-Symptom (~24h alte Basis) weiter."
    )


def test_effective_anchor_age_waehlt_den_juengeren_anker_nicht_den_aelteren():
    """Regressionstest (Fix-Loop F002 zu #1916): `_effective_anchor_age()`
    MUSS den JUENGEREN der beiden Anker (Briefing- ODER rollierender Anker)
    waehlen -- nicht den aelteren. Sonst wuerde eine frische Vergleichsbasis
    faelschlich als "veraltet" behandelt und der rollierende Anker
    unnoetig ueberschrieben.

    Mutations-Gegenprobe (Fix-Loop-Befund): `max(candidates)` -> `min(candidates)`
    in `_effective_anchor_age()` wurde von KEINEM der bestehenden AC-6..AC-9-
    Tests gefangen, weil kein Test beide Anker gleichzeitig mit
    unterschiedlichem Alter am Aufrufpunkt konstruiert. Dieser Test tut genau
    das: ein ALTER rollierender Anker (5h, ausserhalb der Ceiling) UND eine
    FRISCHE `cached_weather`-Vergleichsbasis (30 Min, innerhalb der Ceiling)
    gleichzeitig -- der juengere (30 Min) muss den Ausschlag geben.

    `save_alarm_anchor()` schreibt bewusst IMMER die Schreibzeit als
    `snapshot_at` (nicht das uebergebene `fetched_at` der Segmente, s.
    AC-6/AC-7: "der Anker muss den AKTUELLEN Wetterstand tragen"). Um einen
    5h ALTEN rollierenden Anker zu simulieren, wird `snapshot_at` deshalb NACH
    dem Schreiben direkt in der Datei zurueckdatiert -- reine Testdaten-
    Manipulation der Persistenz (Vorbild: `test_alert_anchor_radar_isolation.py`
    liest/prueft dieselbe Art von Datei direkt), kein Mock/Patch des Prueflings.
    """
    import json

    from app.loader import get_snapshots_dir
    from services.trip_alert import TripAlertService
    from services.weather_snapshot import WeatherSnapshotService

    user_id, trip_id = f"tdd-1916-f002-{uuid.uuid4().hex[:8]}", "trip-f002"
    trip = gust_alert_trip(trip_id)
    svc = TripAlertService(settings=settings_email_only(), user_id=user_id)
    snap_svc = WeatherSnapshotService(user_id=user_id)

    # ALTER rollierender Anker (5h) -- ausserhalb der 4h-Ceiling fuer sich allein.
    alter_rollierender_anker_zeit = datetime.now(timezone.utc) - timedelta(hours=5)
    snap_svc.save_alarm_anchor(trip_id, date.today(), [_wetter(10.0, alter_rollierender_anker_zeit)])
    anchor_path = get_snapshots_dir(user_id) / f"{trip_id}_alarm_anchor.json"
    anchor_data = json.loads(anchor_path.read_text())
    anchor_data["snapshot_at"] = alter_rollierender_anker_zeit.isoformat()
    anchor_path.write_text(json.dumps(anchor_data))
    vor_lauf = snap_svc.load_alarm_anchor(trip_id)[0].fetched_at
    assert vor_lauf == alter_rollierender_anker_zeit, "Fixtur-Schutz: Rueckdatierung muss greifen."

    # FRISCHE Vergleichsbasis (30 Min) als `cached_weather` -- der juengere
    # der beiden Anker, MUSS die Ceiling-Entscheidung tragen.
    frischer_anker_zeit = datetime.now(timezone.utc) - timedelta(minutes=30)
    ausgeloest = svc.check_and_send_alerts(
        trip, [_wetter(10.0, frischer_anker_zeit)],
        fresh_weather=[_wetter(12.0, datetime.now(timezone.utc))],  # 2 km/h, unterschwellig
    )

    assert not ausgeloest, "Fixtur-Schutz: das Delta (2 km/h) darf NICHT ausloesen."
    nach_lauf = snap_svc.load_alarm_anchor(trip_id)[0].fetched_at
    assert nach_lauf == vor_lauf, (
        "F002: der rollierende Anker darf NICHT ueberschrieben werden, wenn "
        "der JUENGERE der beiden Anker (hier: der 30 Min alte "
        "cached_weather-Anker) noch innerhalb der 4h-Ceiling liegt -- "
        "unabhaengig vom Alter des ALTEN rollierenden Ankers. Ein `min()` "
        "statt `max()` in `_effective_anchor_age()` waehlt faelschlich den "
        f"AELTEREN Anker und macht diesen Test rot (vorher: {vor_lauf}, "
        f"nachher: {nach_lauf})."
    )
