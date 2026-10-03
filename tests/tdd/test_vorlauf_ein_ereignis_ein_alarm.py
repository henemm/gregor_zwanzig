"""TDD RED — Issue #2261 Teil A (A-1): ein Ereignis = ein Alarm ueber den
Segmentwechsel (AC-8, Anforderung C-2).

SPEC: docs/specs/modules/feat_2261_a1_radar_vorlauf.md (AC-8;
Implementation Details §5)

Bei Schwelle = Quell-Horizont sieht der Radar ein Ereignis schon in
Segment A, das der Nutzer laut Zeitplan erst in Segment B erlebt. Heute
registriert der Radar-Alarm nur `[aktives Segment]`; der naechste Lauf in
Segment B traegt `[B]` — disjunkt zu `[A]`, das Identitaets-Gate kennt das
Ereignis nicht wieder, und es gaebe einen zweiten Alarm fuer dasselbe
Ereignis. Kuenftig registriert der Alarm {aktives Segment} ∪ {Segment zur
Ereigniszeit}; die Semantik des Identitaets-Gates bleibt unveraendert.

Aufbau: echte Laeufe von `check_radar_alerts()` ueber die Alarm-Pruefstrecke,
Frames an ABSOLUTEN Zeitpunkten (das Ereignis beginnt fest um T0+170), Uhr im
Cron-Raster. Jedes Segment < 2 km (Einzelpunkt-Fall, Aufenthaltsfenster
offen) — der Messort zur Ereigniszeit (AC-3) spielt hier bewusst keine
Rolle. Zwei Nutzer mit derselben Trip-Kennung je Test, plus Aufbau-Kontrolle
(Onset 38 loest schon heute aus).

Kein Mock()/patch()/MagicMock, keine Dateiinhalt-Checks.
"""
from __future__ import annotations

from datetime import timedelta

from services import alert_log

from tests.helpers.alarm_pruefstrecke import AlarmPruefstrecke
from tests.tdd.test_952_onset_alert_fidelity import _clean_user
from tests.tdd.test_alarm_pruefstrecke_selbstschutz import _settings_all_channels
from tests.tdd.test_vorlauf_vergleichbare_menge import (
    ONSET_ERSTSICHT, T0, baue_trip, gruende_seit, lauf_zeit, messe, nutzer,
    radar, regen_ab,
)

EREIGNIS = T0 + timedelta(minutes=ONSET_ERSTSICHT)  # 13:42 UTC, fest
# Segment A: T0-30 .. T0+60 · Segment B: T0+60 .. T0+240. Das Ereignis
# (T0+170) liegt laut Zeitplan in B.
ZWEI_SEGMENTE = [-30, 60, 240]
# Kurze Sperrzeit: Lauf 9 (T0+135) liegt weit dahinter und erreicht das
# Identitaets-Gate — sonst schwiege er an der Sperrzeit, nicht als Duplikat.
SPERRZEIT_KURZ_MIN = 60
LAUF_IN_B = 9  # T0+135: aktives Segment ist B, Onset des Ereignisses 35


def _kontrolle(tag: str, trip_id: str, ankuenfte: list[int]) -> None:
    u = nutzer(f"{tag}-kontrolle")
    try:
        trip = baue_trip(u, trip_id, ankuenfte, cooldown_min=SPERRZEIT_KURZ_MIN)
        strecke = AlarmPruefstrecke(user_id=u, settings=_settings_all_channels())
        lauf = strecke.lauf(
            at=T0, zweig="radar", trip=trip,
            radar_service=radar(regen_ab(T0 + timedelta(minutes=38), 2.0)),
        )
        assert lauf.triggered_count == 1, (
            f"Aufbau defekt: Regen bei Onset 38 muss mit diesem Trip-Aufbau "
            f"schon heute alarmieren. triggered_count={lauf.triggered_count}, "
            f"Gruende={gruende_seit(u, trip, T0)!r}"
        )
    finally:
        _clean_user(u)


def _aktives_segment(trip, at):
    """Das Segment, das der Pruefling zur Uhrzeit `at` waehlt — ueber
    denselben produktiven Aufloeser."""
    from freezegun import freeze_time

    from services.trip_day import trip_local_today
    from services.trip_segments import resolve_current_segment

    with freeze_time(at):
        aufgeloest = resolve_current_segment(trip, at, trip_local_today(trip, at))
    assert aufgeloest is not None, f"Aufbau: kein aktives Segment um {at}"
    return aufgeloest[0]


def test_erstsicht_170_dann_segmentwechsel_ein_alarm():
    """AC-8: Erstsicht bei Onset 170 in Segment A; der Nutzer ist zur
    Ereigniszeit laut Zeitplan in Segment B. Der Lauf in Segment B sieht
    dasselbe Ereignis erneut (Onset 35, gleiche Dringlichkeit) — er wird als
    `event_duplicate` unterdrueckt. Genau EIN Alarm."""
    trip_id = "trip-2261-ac8-wechsel"
    _kontrolle("ac8w", trip_id, ZWEI_SEGMENTE)
    quelle = regen_ab(EREIGNIS, 2.0)
    assert messe(quelle, lauf_zeit(LAUF_IN_B)).onset_minutes == 35, (
        "Konstruktion: Lauf in B muss dasselbe Ereignis bei Onset 35 sehen."
    )

    for tag in ("a", "b"):
        u = nutzer(f"ac8w-{tag}")
        try:
            trip = baue_trip(u, trip_id, ZWEI_SEGMENTE, cooldown_min=SPERRZEIT_KURZ_MIN)
            seg_a = _aktives_segment(trip, lauf_zeit(0))
            seg_b = _aktives_segment(trip, lauf_zeit(LAUF_IN_B))
            assert seg_a.segment_id != seg_b.segment_id and seg_b.start_time <= EREIGNIS <= seg_b.end_time, (
                f"Konstruktion: Lauf 0 in A, Lauf {LAUF_IN_B} in B, Ereignis in B "
                f"(A={seg_a.segment_id}, B={seg_b.segment_id} "
                f"{seg_b.start_time}..{seg_b.end_time})"
            )
            strecke = AlarmPruefstrecke(user_id=u, settings=_settings_all_channels())

            lauf0 = strecke.lauf(at=lauf_zeit(0), zweig="radar", trip=trip,
                                 radar_service=radar(quelle))
            assert lauf0.triggered_count == 1, (
                f"[{tag}] Erstsicht bei Onset 170 in Segment A muss alarmieren "
                f"(Schwelle = Quell-Horizont, AC-1). triggered_count="
                f"{lauf0.triggered_count}"
            )

            lauf_b = strecke.lauf(at=lauf_zeit(LAUF_IN_B), zweig="radar", trip=trip,
                                  radar_service=radar(quelle))
            gruende = gruende_seit(u, trip, lauf_zeit(LAUF_IN_B))
            assert lauf0.triggered_count + lauf_b.triggered_count == 1, (
                f"[{tag}] AC-8: ein Ereignis = ein Alarm — der Lauf in Segment B "
                f"sieht dasselbe Ereignis und darf keinen zweiten Alarm senden. "
                f"Alarme: Lauf 0={lauf0.triggered_count}, Lauf B="
                f"{lauf_b.triggered_count}, Gruende={gruende!r}"
            )
            assert alert_log.REASON_EVENT_DUPLICATE in gruende, (
                f"[{tag}] AC-8: der zweite Alarm muss als "
                f"{alert_log.REASON_EVENT_DUPLICATE!r} unterdrueckt sein (nicht "
                f"Sperrzeit o. a.). Gefunden: {gruende!r}"
            )
        finally:
            _clean_user(u)


def test_verschaerfung_nach_segmentwechsel_kommt_durch():
    """AC-8: Wie oben, aber der Lauf in Segment B sieht das Ereignis als
    GEWITTER (Dringlichkeit MODERATE -> HIGH). Die Verschaerfung kommt durch
    das Identitaets-Gate (`severity_override`)."""
    trip_id = "trip-2261-ac8-verschaerfung"
    _kontrolle("ac8v", trip_id, ZWEI_SEGMENTE)
    gewitter = regen_ab(EREIGNIS, 2.0, gewitter=True)
    assert messe(gewitter, lauf_zeit(LAUF_IN_B)).is_convective, (
        "Konstruktion: Lauf in B muss ein Gewitter sehen."
    )

    for tag in ("a", "b"):
        u = nutzer(f"ac8v-{tag}")
        try:
            trip = baue_trip(u, trip_id, ZWEI_SEGMENTE, cooldown_min=SPERRZEIT_KURZ_MIN)
            strecke = AlarmPruefstrecke(user_id=u, settings=_settings_all_channels())
            lauf0 = strecke.lauf(at=lauf_zeit(0), zweig="radar", trip=trip,
                                 radar_service=radar(regen_ab(EREIGNIS, 2.0)))
            assert lauf0.triggered_count == 1, (
                f"[{tag}] Erstsicht bei Onset 170 in Segment A muss alarmieren "
                f"(Schwelle = Quell-Horizont, AC-1). triggered_count="
                f"{lauf0.triggered_count}"
            )
            lauf_b = strecke.lauf(at=lauf_zeit(LAUF_IN_B), zweig="radar", trip=trip,
                                  radar_service=radar(gewitter))
            assert lauf_b.triggered_count == 1, (
                f"[{tag}] AC-8: eine echte Verschaerfung (Gewitter) nach dem "
                f"Segmentwechsel muss durchkommen. triggered_count="
                f"{lauf_b.triggered_count}, Gruende="
                f"{gruende_seit(u, trip, lauf_zeit(LAUF_IN_B))!r}"
            )
        finally:
            _clean_user(u)


def test_ereignis_nach_letzter_etappe_bleibt_aktives_segment():
    """AC-8: Die einzige Etappe endet um T0+60; das Ereignis (T0+170) liegt
    danach — es gibt kein Segment zur Ereigniszeit. Registriert wird dann das
    aktive Segment: der Alarm geht raus (kein Absturz, keine leere
    Segmentmenge), und ein Folgelauf im selben Segment, der dasselbe
    Ereignis sieht, ist `event_duplicate`.

    Faengt die Verfaelschung „nur das Segment zur Ereigniszeit registrieren"
    (leere Menge ⇒ das Gate findet nie einen Treffer ⇒ zweiter Alarm)."""
    trip_id = "trip-2261-ac8-letzte"
    ankuenfte = [-30, 60]
    _kontrolle("ac8l", trip_id, ankuenfte)
    quelle = regen_ab(EREIGNIS, 2.0)

    for tag in ("a", "b"):
        u = nutzer(f"ac8l-{tag}")
        try:
            # Sperrzeit 15 Min: Lauf 2 (T0+30) liegt dahinter, steht noch im
            # selben (letzten) Segment und erreicht das Identitaets-Gate.
            trip = baue_trip(u, trip_id, ankuenfte, cooldown_min=15)
            seg = _aktives_segment(trip, lauf_zeit(2))
            assert seg.end_time < EREIGNIS, (
                f"Konstruktion: die letzte Etappe muss vor dem Ereignis enden "
                f"({seg.end_time} vs. {EREIGNIS})"
            )
            strecke = AlarmPruefstrecke(user_id=u, settings=_settings_all_channels())
            lauf0 = strecke.lauf(at=lauf_zeit(0), zweig="radar", trip=trip,
                                 radar_service=radar(quelle))
            assert lauf0.triggered_count == 1, (
                f"[{tag}] Erstsicht bei Onset 170 nach der letzten Etappe muss "
                f"alarmieren (Schwelle = Quell-Horizont, AC-1; Segment zur "
                f"Ereigniszeit fehlt ⇒ aktives Segment). triggered_count="
                f"{lauf0.triggered_count}"
            )
            lauf2 = strecke.lauf(at=lauf_zeit(2), zweig="radar", trip=trip,
                                 radar_service=radar(quelle))
            gruende = gruende_seit(u, trip, lauf_zeit(2))
            assert lauf2.triggered_count == 0 and alert_log.REASON_EVENT_DUPLICATE in gruende, (
                f"[{tag}] AC-8: der Folgelauf im selben Segment muss dasselbe "
                f"Ereignis als {alert_log.REASON_EVENT_DUPLICATE!r} erkennen — die "
                f"Registrierung traegt das aktive Segment. triggered_count="
                f"{lauf2.triggered_count}, Gruende={gruende!r}"
            )
        finally:
            _clean_user(u)
