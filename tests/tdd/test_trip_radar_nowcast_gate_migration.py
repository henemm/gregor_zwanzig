"""Invarianten-Waechter — Trip-Nowcast bleibt beim Umklemmen auf den
geteilten Freigabe-Baustein Bit fuer Bit gleich (Issue #1467 S3, AC-16).

SPEC: docs/specs/modules/rework_1467_s3_nowcast.md

Diese Datei ist KEIN RED-Test: sie ist HEUTE gruen und muss es nach dem Umbau
bleiben. Die vier Szenarien wurden am Stand VOR dem Umbau gemessen; genau
diese Tabelle gilt danach unveraendert weiter:

    | # | Ruhezeit | Sperrzeit | Tageslimit | Ergebnis (gemessen 2026-08-08) |
    |---|----------|-----------|------------|--------------------------------|
    | A | aus      | frei      | frei       | ZUGESTELLT ueber "email"       |
    | B | AN       | frei      | frei       | nicht zugestellt               |
    | C | aus      | AKTIV     | frei       | nicht zugestellt               |
    | D | aus      | frei      | ERREICHT   | nicht zugestellt               |

Zusaetzlich haelt Szenario A die Buchungsseite fest: nach erfolgreicher
Zustellung liegt der Sperrzeit-Eintrag im geteilten ``throttle_state.json``
unter Scope ``radar`` mit dem Trip-Schluessel, und der Tageszaehler steht auf
1. Wuerde der Umbau den Trip-Pfad auf einen anderen Scope umhaengen oder das
Buchen vor die Zustellung ziehen, faellt das hier auf.

Die einzige zugelassene NEUE Wirkung fuer den Trip ist die Unterdrueckungs-
Protokollierung (AC-10, ``test_nowcast_suppression_logging.py``) — die
Zustellentscheidung selbst aendert sich nicht.

Mock-frei: echter Trip auf Platte, echter ``TripAlertService``, echte
Zustandsdateien; Radar ueber den ``frame_source``-Seam, Versand ueber
``mail_sink``. Kein Netz.
"""
from __future__ import annotations

from datetime import datetime, timezone

from tests.helpers.nowcast_gate_fixtures import (
    SCOPE_TRIP_RADAR, CountingFrameSource, clean_uid, fresh_uid, make_trip,
    TRIP_ZONE, quiet_window_elsewhere, quiet_window_now, read_daily_counter,
    read_throttle_state, record_throttle, save_trip, seed_daily_counter,
    settings_email_only, trip_alert_service, write_user_tier,
)


def _run_trip_scenario(
    uid: str,
    trip_id: str,
    *,
    quiet: bool,
    throttled: bool,
    daily_limit_reached: bool,
) -> tuple[int, list]:
    """EIN Trip-Nowcast-Lauf mit auslloesendem Onset. Liefert
    ``(rueckgabewert, mail_aufrufe)``."""
    write_user_tier(uid, "free")  # Limit 2/Tag
    seed_daily_counter(uid, 2 if daily_limit_reached else 0, zone=TRIP_ZONE)

    # Issue #1726: Ortszone der TOUR (Island), nicht Wien.
    quiet_from, quiet_to = (
        quiet_window_now(zone=TRIP_ZONE) if quiet
        else quiet_window_elsewhere(zone=TRIP_ZONE)
    )
    trip = make_trip(trip_id, cooldown_minutes=120, quiet_from=quiet_from, quiet_to=quiet_to)
    save_trip(trip, uid)

    if throttled:
        record_throttle(uid, SCOPE_TRIP_RADAR, trip_id, datetime.now(timezone.utc))

    mail_calls: list = []
    svc = trip_alert_service(
        uid, settings_email_only(), CountingFrameSource(onset_minutes=8),
        lambda subject, body: mail_calls.append((subject, body)),
    )
    return svc.check_radar_alerts(), mail_calls


def test_szenario_a_ohne_sperre_wird_zugestellt_und_gebucht():
    """AC-16 Szenario A: keine Ruhezeit, keine Sperrzeit, Tagesbudget frei —
    der Trip-Nowcast geht raus (Kanal E-Mail). Danach steht die Buchung im
    geteilten Speicher: Scope ``radar``, Schluessel = Trip-Kennung, und der
    Tageszaehler ist um genau 1 gestiegen."""
    uid, trip_id = fresh_uid("ac16-a"), "trip-ac16-a"
    clean_uid(uid)
    try:
        sent, mails = _run_trip_scenario(
            uid, trip_id, quiet=False, throttled=False, daily_limit_reached=False,
        )

        assert sent == 1, (
            f"Szenario A muss GENAU EINEN Trip-Nowcast zustellen, erhalten: {sent}"
        )
        assert len(mails) == 1, (
            f"Szenario A: erwartet genau EINE Mail ueber den mail_sink, "
            f"erhalten {len(mails)}"
        )

        state = read_throttle_state(uid)
        assert trip_id in state.get(SCOPE_TRIP_RADAR, {}), (
            f"Sperrzeit des Trip-Nowcast fehlt unter Scope {SCOPE_TRIP_RADAR!r} "
            f"mit Schluessel {trip_id!r}: {state!r}"
        )
        assert read_daily_counter(uid, zone=TRIP_ZONE) == 1, (
            f"Tageszaehler muss nach genau einer Zustellung auf 1 stehen, "
            f"steht auf {read_daily_counter(uid, zone=TRIP_ZONE)}"
        )
    finally:
        clean_uid(uid)


def test_szenario_b_ruhezeit_unterdrueckt():
    """AC-16 Szenario B: Ruhezeit aktiv, sonst alles frei — keine Zustellung,
    keine Buchung."""
    uid, trip_id = fresh_uid("ac16-b"), "trip-ac16-b"
    clean_uid(uid)
    try:
        sent, mails = _run_trip_scenario(
            uid, trip_id, quiet=True, throttled=False, daily_limit_reached=False,
        )

        assert sent == 0, f"Ruhezeit muss den Trip-Nowcast unterdruecken, erhalten: {sent}"
        assert mails == [], "Waehrend der Ruhezeit darf keine Mail rausgehen"
        assert read_daily_counter(uid, zone=TRIP_ZONE) == 0, "Unterdrueckter Alarm darf nicht zaehlen"
        assert trip_id not in read_throttle_state(uid).get(SCOPE_TRIP_RADAR, {}), (
            "Unterdrueckter Alarm darf keine Sperrzeit buchen"
        )
    finally:
        clean_uid(uid)


def test_szenario_c_sperrzeit_unterdrueckt():
    """AC-16 Szenario C: Sperrzeit aktiv (frischer Eintrag im geteilten
    Speicher), sonst alles frei — keine Zustellung."""
    uid, trip_id = fresh_uid("ac16-c"), "trip-ac16-c"
    clean_uid(uid)
    try:
        sent, mails = _run_trip_scenario(
            uid, trip_id, quiet=False, throttled=True, daily_limit_reached=False,
        )

        assert sent == 0, f"Sperrzeit muss den Trip-Nowcast unterdruecken, erhalten: {sent}"
        assert mails == [], "Innerhalb der Sperrzeit darf keine Mail rausgehen"
        assert read_daily_counter(uid, zone=TRIP_ZONE) == 0, "Unterdrueckter Alarm darf nicht zaehlen"
    finally:
        clean_uid(uid)


def test_szenario_d_tageslimit_unterdrueckt():
    """AC-16 Szenario D: Tages-Obergrenze erreicht (free = 2/Tag), sonst alles
    frei — keine Zustellung, Zaehler bleibt stehen."""
    uid, trip_id = fresh_uid("ac16-d"), "trip-ac16-d"
    clean_uid(uid)
    try:
        sent, mails = _run_trip_scenario(
            uid, trip_id, quiet=False, throttled=False, daily_limit_reached=True,
        )

        assert sent == 0, f"Tageslimit muss den Trip-Nowcast unterdruecken, erhalten: {sent}"
        assert mails == [], "Bei erreichtem Tageslimit darf keine Mail rausgehen"
        assert read_daily_counter(uid, zone=TRIP_ZONE) == 2, (
            f"Der Zaehler darf beim unterdrueckten Alarm nicht wachsen, steht auf "
            f"{read_daily_counter(uid, zone=TRIP_ZONE)}"
        )
        assert trip_id not in read_throttle_state(uid).get(SCOPE_TRIP_RADAR, {}), (
            "Unterdrueckter Alarm darf keine Sperrzeit buchen"
        )
    finally:
        clean_uid(uid)
