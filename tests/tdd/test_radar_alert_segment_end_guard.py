"""TDD RED — Issue #2009: Segment-Ende-Guard fuer den Trip-Radar-Pfad (AC-6).

SPEC: docs/specs/modules/fix_2009_nowcast_vorlauf.md

Mit der auf 55 Min angehobenen Onset-Schwelle (#2009) kann der berechnete
Onset-Zeitpunkt weiter in der Zukunft liegen als das aktive Segment des
Trips (`active.end_time`, Issue #822/#1584) -- der Nutzer haette den
Abschnitt zu diesem Zeitpunkt laengst hinter sich. `check_radar_alerts()`
prueft das heute NICHT: `active.end_time` wird zwar fuer den
Briefing-Abgleich gelesen, aber nie gegen den berechneten Onset-Zeitpunkt
verglichen.

Der Ortsvergleich hat KEINEN Segment-Bezug (Compare-Presets adressieren
`location_ids`, keine Etappen -- dokumentiert `compare_radar_alert.py:13-16`)
und ist deshalb NICHT Teil dieses Tests (Spec, Abschnitt "Architektur-
Entscheidung").

Kein Mock des Gates: echter Trip mit realer Etappe (`TripSegment.end_time`
ueber `arrival_calculated`), echter `CountingFrameSource`-Frame ueber den
`frame_source`-DI-Seam, Zustellung ueber den `mail_sink`-Zaehler.

Zeitbezug: `check_radar_alerts()` bietet keinen `now`-Injektions-Seam (liest
`datetime.now(timezone.utc)` selbst, `trip_alert.py:1140`) -- die Uhr wird
deshalb GESTELLT (`freeze_time`, Muster `test_radar_alert_follows_
ortstag.py`) und die Segmentzeiten relativ zu diesem festen, mitternachts-
fernen Zeitpunkt gebaut. Koordinaten sind Reykjavik (`TRIP_LAT`/`TRIP_LON`,
ganzjaehrig UTC+0 -- `make_trip()`s Default), damit HH:MM Ortszeit ohne
Zonenumrechnung direkt aus der gestellten UTC-Zeit ablesbar ist.

🔴 Warum NICHT die echte Wanduhr (Messung 2026-08-20,
`tests/helpers/wanduhr_matrix.py`, 24 Datenpunkte): mit `now` aus
`datetime.now()` kippte der erste Fall bei genau einem Datenpunkt (00:00
UTC). Dort ergibt `now - 10 min`/`now + 15 min` die HH:MM-Angaben
23:50/00:15 -- eine Etappe, die vom Etappendatum aus erst am ABEND beginnt
und ueber Mitternacht laeuft. Der Kontrollfall traf damit kein aktives
Segment mehr, sondern den Horizont-Guard (#1697). Das ist eine Grenze der
FIXTURE (`arrival_calculated` traegt nur HH:MM, das Etappendatum kommt aus
`make_trip(stage_date=...)`), kein Produktfehler -- die Segmentbildung
fuehrt den Tagesuebertrag korrekt mit (`trip_segments.py:159-167` bildet
`wp_days`, `:191-198` kombiniert ihn mit `target_date` zu vollen
UTC-Zeitstempeln). Nachgemessen 2026-08-20: eine echte Etappe 23:50->00:15
am VORTAG wird um 00:00 UTC als aktives Segment gefunden
(`2026-08-11T23:50` -> `2026-08-12T00:15`), und der Guard entscheidet dort
richtig -- Onset 00:10 loest aus, Onset 00:53 wird unterdrueckt.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from freezegun import freeze_time

from tests.helpers.nowcast_gate_fixtures import (
    CountingFrameSource, clean_uid, fresh_uid, make_trip, reset_radar_cache,
    save_trip, settings_email_only, trip_alert_service, write_user_tier,
)


def _hhmm(dt_utc: datetime) -> str:
    return dt_utc.strftime("%H:%M")


# Gestellter Bezugszeitpunkt aller Faelle dieser Datei: mittags, weit von
# jeder Tagesgrenze entfernt (s. Modul-Docstring). Reykjavik = UTC+0, die
# HH:MM-Angaben der Etappe sind damit direkt hieraus ablesbar.
_MITTAGS = "2026-08-11T12:00:00+00:00"


def _guard_lauf(uid: str, trip_id: str, *, ende_in_minuten: int, onset_minutes: int) -> tuple[int, list]:
    """Ein echter `check_radar_alerts()`-Lauf unter gestellter Uhr: Etappe
    beginnt 10 Min vor dem Bezugszeitpunkt und endet `ende_in_minuten`
    danach. Liefert `(Anzahl Alarme, zugestellte Mails)`."""
    clean_uid(uid)
    with freeze_time(_MITTAGS):
        now = datetime.now(timezone.utc)
        write_user_tier(uid, "premium")
        trip = make_trip(
            trip_id,
            arrival_start=_hhmm(now - timedelta(minutes=10)),
            arrival_end=_hhmm(now + timedelta(minutes=ende_in_minuten)),
        )
        save_trip(trip, uid)
        reset_radar_cache()
        mails: list = []
        svc = trip_alert_service(
            uid, settings_email_only(),
            CountingFrameSource(onset_minutes=onset_minutes),
            lambda subject, body: mails.append((subject, body)),
        )
        return svc.check_radar_alerts(), mails


def test_ac6_segment_end_guard_suppresses_late_onset():
    """AC-6: Given ein Trip, dessen aktives Segment vor dem berechneten
    Onset-Zeitpunkt endet (Segment endet in 15 Min, Onset laege bei 53 Min)
    / When `check_radar_alerts()` laeuft / Then wird kein Alarm versendet;
    Kontrollfall im selben Testlauf: liegt der Onset VOR dem Segmentende
    (Segment endet erst in 90 Min), loest derselbe Onset weiterhin regulaer
    aus."""
    onset_minutes = 53  # erreichbarer Rasterwert, <= 55 (neue Schwelle) -> loest grundsaetzlich aus

    # ---- Fall 1: Segment endet VOR dem Onset (in 15 Min < 53 Min) -> Guard
    #      muss den Alarm unterdruecken.
    uid_suppressed = fresh_uid("ac6-suppressed")
    try:
        sent, mails = _guard_lauf(
            uid_suppressed, "trip-ac6-suppressed",
            ende_in_minuten=15, onset_minutes=onset_minutes,
        )
        assert sent == 0, (
            f"Segment endet in 15 Min, Onset laege erst in {onset_minutes} "
            f"Min (danach) -- der Alarm haette unterdrueckt werden muessen, "
            f"erhalten: {sent}"
        )
        assert mails == [], (
            f"Trotz Segment-Ende vor dem Onset wurde versendet: {mails!r}"
        )
    finally:
        clean_uid(uid_suppressed)

    # ---- Fall 2 (Kontrolle): Segment endet NACH dem Onset (in 90 Min >
    #      53 Min) -> regulaerer Alarm, unveraendertes Verhalten.
    uid_control = fresh_uid("ac6-control")
    try:
        sent, mails = _guard_lauf(
            uid_control, "trip-ac6-control",
            ende_in_minuten=90, onset_minutes=onset_minutes,
        )
        assert sent == 1, (
            f"Segment endet erst in 90 Min, Onset liegt bei {onset_minutes} "
            f"Min (davor) -- Kontrollfall muss weiterhin regulaer ausloesen, "
            f"erhalten: {sent}"
        )
        assert len(mails) == 1, (
            f"Kontrollfall: erwartet genau EINE Mail, erhalten {len(mails)}"
        )
    finally:
        clean_uid(uid_control)


# ═══════════ Fix-Loop F002 (Adversary, MEDIUM) — der RANDWERT ═════════════


def test_ac6_onset_exakt_am_segmentende_loest_noch_aus():
    """F002: der Gleichheitsfall ist eine ENTSCHEIDUNG, kein Zufall — ein
    Onset EXAKT zum Segmentende trifft einen Abschnitt, auf dem der Nutzer
    zu diesem Zeitpunkt noch steht, und loest deshalb aus
    (`trip_alert.py`: `_onset_dt > _segment_end`, bewusst nicht `>=`).

    Die beiden Faelle oben lassen die Richtung offen: 15 bzw. 90 Minuten
    Abstand entscheiden dieselbe Frage bei `>` wie bei `>=`. Erst dieser
    Fall nagelt sie fest — die Mutation `>` -> `>=` macht ihn rot.

    Gestellte Uhr (`freeze_time`) statt Wanduhr: die Segmentzeiten kommen
    aus `arrival_calculated` ("HH:MM", Sekunde 0), der Onset-Zeitpunkt aus
    `now + 53 Min`. Exakte Gleichheit gibt es nur, wenn "jetzt" selbst auf
    einer vollen Minute steht. Reykjavik-Koordinaten (`make_trip`-Default,
    ganzjaehrig UTC+0): Ortszeit == gestellte UTC-Zeit, keine Zonenrechnung.
    """
    onset_minutes = 53
    uid = fresh_uid("ac6-randwert")
    clean_uid(uid)
    try:
        with freeze_time(_MITTAGS):
            now = datetime.now(timezone.utc)
            segment_ende = now + timedelta(minutes=onset_minutes)

            write_user_tier(uid, "premium")
            trip = make_trip(
                "trip-ac6-randwert",
                arrival_start=_hhmm(now - timedelta(minutes=60)),
                arrival_end=_hhmm(segment_ende),
            )
            save_trip(trip, uid)

            # Testvoraussetzung: das aktive Segment muss GENAU zum
            # Onset-Zeitpunkt enden — sonst prueft der Fall den Randwert
            # nicht (die Segmentzeiten koennen durch Tagesfenster-Guards
            # verschoben werden, #1584).
            from services.trip_segments import resolve_current_segment
            from services.trip_day import trip_local_today

            aufgeloest = resolve_current_segment(
                trip, now, trip_local_today(trip, now),
            )
            assert aufgeloest is not None, (
                "Testvoraussetzung: es muss ein aktives Segment geben"
            )
            assert aufgeloest[0].end_time == segment_ende, (
                f"Testvoraussetzung: das aktive Segment muss exakt zum "
                f"Onset-Zeitpunkt {segment_ende.isoformat()} enden, endet "
                f"aber {aufgeloest[0].end_time.isoformat()}"
            )

            reset_radar_cache()
            mails: list = []
            svc = trip_alert_service(
                uid, settings_email_only(),
                CountingFrameSource(onset_minutes=onset_minutes),
                lambda subject, body: mails.append((subject, body)),
            )
            sent = svc.check_radar_alerts()

        assert sent == 1 and len(mails) == 1, (
            f"Onset exakt zum Segmentende ({segment_ende.isoformat()}): der "
            f"Nutzer ist dann noch im Segment, der Alarm MUSS ausloesen. "
            f"Erhalten: sent={sent}, mails={len(mails)}. Genau das waere das "
            f"Verhalten der Mutation `_onset_dt >= _segment_end`."
        )
    finally:
        clean_uid(uid)
