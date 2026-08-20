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
`datetime.now(timezone.utc)` selbst, `trip_alert.py:1140`) -- die
Segment-Zeiten werden deshalb relativ zur echten Uhr gebaut (Muster
`nowcast_gate_fixtures.py::quiet_window_now`), in der UTC-Ortszeit von
Reykjavik (`TRIP_LAT`/`TRIP_LON`, ganzjaehrig UTC+0 -- `make_trip()`s
Default-Koordinaten), damit HH:MM Ortszeit ohne Zonenumrechnung direkt aus
UTC "jetzt" ablesbar ist.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from tests.helpers.nowcast_gate_fixtures import (
    CountingFrameSource, clean_uid, fresh_uid, make_trip, reset_radar_cache,
    save_trip, settings_email_only, trip_alert_service, write_user_tier,
)


def _hhmm(dt_utc: datetime) -> str:
    return dt_utc.strftime("%H:%M")


def test_ac6_segment_end_guard_suppresses_late_onset():
    """AC-6: Given ein Trip, dessen aktives Segment vor dem berechneten
    Onset-Zeitpunkt endet (Segment endet in 15 Min, Onset laege bei 53 Min)
    / When `check_radar_alerts()` laeuft / Then wird kein Alarm versendet;
    Kontrollfall im selben Testlauf: liegt der Onset VOR dem Segmentende
    (Segment endet erst in 90 Min), loest derselbe Onset weiterhin regulaer
    aus."""
    now = datetime.now(timezone.utc)
    onset_minutes = 53  # erreichbarer Rasterwert, <= 55 (neue Schwelle) -> loest grundsaetzlich aus

    # ---- Fall 1: Segment endet VOR dem Onset (in 15 Min < 53 Min) -> Guard
    #      muss den Alarm unterdruecken.
    uid_suppressed = fresh_uid("ac6-suppressed")
    trip_id_suppressed = "trip-ac6-suppressed"
    clean_uid(uid_suppressed)
    try:
        write_user_tier(uid_suppressed, "premium")
        trip = make_trip(
            trip_id_suppressed,
            arrival_start=_hhmm(now - timedelta(minutes=10)),
            arrival_end=_hhmm(now + timedelta(minutes=15)),
        )
        save_trip(trip, uid_suppressed)
        reset_radar_cache()
        mails: list = []
        svc = trip_alert_service(
            uid_suppressed, settings_email_only(),
            CountingFrameSource(onset_minutes=onset_minutes),
            lambda subject, body: mails.append((subject, body)),
        )
        sent = svc.check_radar_alerts()
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
    trip_id_control = "trip-ac6-control"
    clean_uid(uid_control)
    try:
        write_user_tier(uid_control, "premium")
        trip = make_trip(
            trip_id_control,
            arrival_start=_hhmm(now - timedelta(minutes=10)),
            arrival_end=_hhmm(now + timedelta(minutes=90)),
        )
        save_trip(trip, uid_control)
        reset_radar_cache()
        mails: list = []
        svc = trip_alert_service(
            uid_control, settings_email_only(),
            CountingFrameSource(onset_minutes=onset_minutes),
            lambda subject, body: mails.append((subject, body)),
        )
        sent = svc.check_radar_alerts()
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
