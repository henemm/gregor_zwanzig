"""TDD RED — Issue #1916, AC-Gruppe B ("Rollierende Basis"), AC-6.

SPEC: docs/specs/modules/trip_alert.md v3.0, ADR-0056;
docs/specs/modules/fix_1987_kanal_anker.md (S1).

Dritter, rollierender Anker-Typ. Kern-Schicht, deterministisch:
``cached_weather``/``fresh_weather`` werden DIREKT an
``check_and_send_alerts()`` uebergeben (Vorbild
``test_alert_channel_threshold.py:409-412``) -- der Schreibpfad ist Teil
dieser Methode selbst, unabhaengig davon, wie ``cached`` zustande kam.

**Issue #1987 (S1) hat den Hybrid-Trigger halbiert.** ADR-0056 kannte zwei
Schreibtrigger: (a) tatsaechlicher Alarmversand, (b) opportunistische
Auffrischung beim Ueberschreiten der 4h-Ceiling, auch ohne Alarm. Trigger
(b) ist mit der Zustellungsbindung von #1987 begrifflich unmoeglich geworden
-- er lief im Zweig "kein Alarm gefeuert", also ohne jede
``delivered_channels``-Information, und schrieb damit einen Stand fort, den
kein Empfaenger je bekommen hat (Spec #1987, "Bewusste Abkehr von
Alt-Verhalten", zweite Abkehr). Die frueheren AC-7/AC-8-Tests dieser Datei
haben genau diesen Trigger geprueft und sind deshalb ERSETZT durch
``test_ohne_alarm_wird_kein_rollierender_anker_mehr_geschrieben`` unten --
die Umkehrung derselben Naht. Dasselbe gilt fuer den frueheren
``_effective_anchor_age()``-Regressionstest: die Methode existiert nicht
mehr, sie hatte nur den entfallenen Schreibtrigger zu bedienen.

Die Schutzwirkung gegen eine veraltete Vergleichsbasis ist NICHT entfallen,
sie wandert in den Lesepfad: ein gealterter Kanal-Merker wird dort nicht
mehr als Kandidat herangezogen, die Kette faellt fuer diesen Kanal auf den
Tier-1-Briefing-Anker zurueck. Bewacht in
``test_alert_channel_anchor_ceiling_fallback.py`` (#1987 AC-4).

API seit #1987: ``save_alarm_anchor()``/``load_alarm_anchor()`` tragen
``channel`` als PFLICHT-Parameter, je Kanal eine eigene Datei
``{trip_id}_alarm_anchor_{channel}.json``.
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


def _dienst(user_id: str):
    """Alarm-Dienst mit gesetzter Transportnaht.

    Issue #1987 (S1): der rollierende Anker rueckt seither NUR fuer
    tatsaechlich ZUGESTELLTE Kanaele vor. Ohne die ``mail_sink``-Naht
    scheitert der E-Mail-Versand am Egress-Waechter, ``delivered_channels``
    bliebe leer und es entstuende gar kein Anker -- kein Mock, dieselbe
    Naht wie in ``test_alert_anchor_day_guard``.
    """
    from services.trip_alert import TripAlertService

    return TripAlertService(
        settings=settings_email_only(), user_id=user_id,
        mail_sink=lambda subject, body: None,
    )


def test_ac6_erfolgreicher_alarmversand_schreibt_rollierenden_anker():
    """AC-6: Trigger (a) -- ein tatsaechlich versendeter Alarm schreibt einen
    frischen rollierenden Anker, unabhaengig von einem vorherigen Briefing.

    Seit #1987 kanalscharf: geschrieben wird der Merker des Kanals, der den
    Alarm zugestellt bekommen hat (hier E-Mail).
    """
    from services.weather_snapshot import WeatherSnapshotService

    user_id, trip_id = f"tdd-1916-ac6-{uuid.uuid4().hex[:8]}", "trip-ac6"
    trip = gust_alert_trip(trip_id)
    svc = _dienst(user_id)
    vor_lauf = datetime.now(timezone.utc)

    ausgeloest = svc.check_and_send_alerts(
        trip, [_wetter(10.0, vor_lauf - timedelta(hours=1))],
        fresh_weather=[_wetter(150.0, vor_lauf)],
    )

    assert ausgeloest, "Fixtur-Schutz: das massive Delta muss ausloesen."
    anker = WeatherSnapshotService(user_id=user_id).load_alarm_anchor(trip_id, "email")
    assert anker, (
        "AC-6: nach einem tatsaechlich versendeten Alarm MUSS ein "
        "rollierender Anker existieren -- unabhaengig von einem Briefing."
    )
    assert _aware(anker[0].fetched_at) >= vor_lauf, (
        f"AC-6: der geschriebene Anker muss den AKTUELLEN Wetterstand "
        f"tragen (fetched_at={anker[0].fetched_at}, Lauf-Start={vor_lauf})."
    )


def test_ohne_alarm_wird_kein_rollierender_anker_mehr_geschrieben():
    """Nachfolger der frueheren AC-7/AC-8 (#1916 Trigger b), Issue #1987 S1.

    GIVEN einen 5 h alten rollierenden Merker (weit ausserhalb der
          4h-Ceiling) und ein unterschwelliges Delta.
    WHEN  der Check-Lauf ohne ausgeloesten Alarm endet.
    THEN  bleibt der Merker UNVERAENDERT -- der opportunistische
          Ceiling-Schreibtrigger ist ersatzlos entfallen. In diesem Zweig
          wurde nichts versendet, es gibt also keine ``delivered_channels``;
          ein hier geschriebener Merker waere ein Stand, den kein Empfaenger
          je zugestellt bekam (#1987, E1/AC-2).

    Diese Zusicherung ist die Umkehrung der frueheren AC-7/AC-8 an derselben
    Naht: eine Mutation, die den Ceiling-Schreibtrigger wieder einbaut, wird
    hier rot. Dass die Alterung dadurch nicht wirkungslos wird, sondern beim
    LESEN greift, bewacht ``test_alert_channel_anchor_ceiling_fallback.py``
    (#1987 AC-4).

    Die Rueckdatierung von ``snapshot_at`` ist reine Testdaten-Manipulation
    der Persistenz (``save_alarm_anchor()`` schreibt immer die Schreibzeit),
    kein Mock/Patch des Prueflings.
    """
    import json

    from app.loader import get_snapshots_dir
    from services.weather_snapshot import WeatherSnapshotService

    user_id, trip_id = f"tdd-1987-kein-b-{uuid.uuid4().hex[:8]}", "trip-kein-b"
    trip = gust_alert_trip(trip_id)
    snap_svc = WeatherSnapshotService(user_id=user_id)
    alt = datetime.now(timezone.utc) - timedelta(hours=5)
    snap_svc.save_alarm_anchor(trip_id, date.today(), [_wetter(10.0, alt)], "email")
    pfad = get_snapshots_dir(user_id) / f"{trip_id}_alarm_anchor_email.json"
    daten = json.loads(pfad.read_text())
    daten["snapshot_at"] = alt.isoformat()
    pfad.write_text(json.dumps(daten, indent=2))
    vorher = snap_svc.load_alarm_anchor(trip_id, "email")[0].fetched_at
    assert vorher == alt, "Fixtur-Schutz: die Rueckdatierung muss greifen."

    ausgeloest = _dienst(user_id).check_and_send_alerts(
        trip, [_wetter(10.0, datetime.now(timezone.utc) - timedelta(minutes=30))],
        fresh_weather=[_wetter(12.0, datetime.now(timezone.utc))],
    )

    assert not ausgeloest, "Fixtur-Schutz: das Delta (2 km/h) darf NICHT ausloesen."
    nachher = snap_svc.load_alarm_anchor(trip_id, "email")[0].fetched_at
    assert nachher == vorher, (
        "Ohne Alarmversand darf KEIN rollierender Anker fortgeschrieben "
        "werden -- auch nicht, wenn der bestehende Merker die 4h-Ceiling "
        f"ueberschreitet (#1987: Trigger (b) entfaellt ersatzlos). Vorher: "
        f"{vorher}, nachher: {nachher}."
    )
