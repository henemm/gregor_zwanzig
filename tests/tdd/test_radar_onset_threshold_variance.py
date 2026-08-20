"""TDD RED — Issue #2009: geteilte Onset-Schwelle 20 -> 55 Minuten.

SPEC: docs/specs/modules/fix_2009_nowcast_vorlauf.md (AC-1, AC-2, AC-3)

Heutiger Stand: `trip_alert.py:1270` ruft `radar_alert_due(result,
threshold_min=20)` mit einem hartkodierten Literal auf,
`compare_radar_alert.py:53` pflegt ein eigenes `_RADAR_ONSET_THRESHOLD_MIN =
20`. Es existiert **keine** geteilte Konstante `RADAR_ONSET_THRESHOLD_MIN` in
`services.radar_service` — dieses Modul importiert/referenziert sie deshalb
ueberall, wo sie gebraucht wird, und schlaegt heute mit AttributeError fehl.

Zusaetzlich prueft heute KEIN Test, dass `onset_minutes` ueberhaupt variieren
kann: `tests/helpers/nowcast_gate_fixtures.py::CountingFrameSource` hat den
Default `onset_minutes=8` und wird suiteweit genau damit aufgerufen — die
Blindstelle, die AC-2/AC-3 schliessen.

Mock-frei: echte `RadarFrame`-Objekte ueber den `frame_source`-DI-Seam
(`CountingFrameSource`), echte Trips/Presets auf der isolierten
Test-Datenwurzel (`_isolate_data_root`, autouse), Zustellung ueber den
`mail_sink`-Zaehler (kein Netz, kein echter Versand — Kern-Test im
Commit-Gate, #1477).

🔴 Warum die Uhr GESTELLT wird (nicht zurueckdrehen!): `make_trip()` baut
seine Etappe standardmaessig von 00:00 bis 23:59 des KALENDERTAGS, an dem
der Test laeuft. Der mit diesem Ticket eingefuehrte Segment-Ende-Guard
(AC-6, `trip_alert.py`) vergleicht den berechneten Onset-Zeitpunkt gegen
`active.end_time` — rutscht `jetzt + onset_minutes` ueber Mitternacht, liegt
er hinter dem Etappenende und der Guard unterdrueckt den Alarm voellig
korrekt. Gegen die echte Wanduhr wurden die Alarm-Faelle dieser Datei
deshalb taeglich zwischen ~23:10 und 23:59 UTC rot (Messung 2026-08-20,
`tests/helpers/wanduhr_matrix.py`, 10-Min-Raster: 23:10 ein Fall, ab 23:40
vier Faelle). Das ist ein Test-Robustheitsdefekt, kein Produktfehler.
Gestellt wird auf einen mittaeglichen, tagesgrenzen-fernen Zeitpunkt —
dasselbe Muster und derselbe Bezugszeitpunkt wie in der Schwesterdatei
`test_radar_alert_segment_end_guard.py`, die denselben Guard ueber denselben
`make_trip()`-Pfad durchlaeuft. Reykjavik (`make_trip()`-Default,
ganzjaehrig UTC+0) macht die Ortszeit direkt aus der gestellten UTC-Zeit
ablesbar.
"""
from __future__ import annotations

import pytest
from freezegun import freeze_time

from app.loader import save_location

from tests.helpers.nowcast_gate_fixtures import (
    CountingFrameSource, clean_uid, compare_radar_service, fresh_uid,
    location, make_trip, radar_preset, reset_radar_cache, save_trip,
    settings_email_only, trip_alert_service, write_presets, write_user_tier,
)


# Gestellter Bezugszeitpunkt ALLER Laeufe dieser Datei: mittags, weit von
# jeder Tagesgrenze entfernt (Begruendung im Modul-Docstring). Bewusst
# derselbe Wert wie `_MITTAGS` in `test_radar_alert_segment_end_guard.py` —
# beide Dateien fahren denselben Guard.
_MITTAGS = "2026-08-11T12:00:00+00:00"


# ═══════════════════════════════ AC-1 ═════════════════════════════════════


def _trip_run(uid: str, trip_id: str, onset_minutes: int) -> tuple[int, list]:
    """Ein echter `check_radar_alerts()`-Lauf unter gestellter Uhr. Liefert
    `(Anzahl Alarme, zugestellte Mails)`."""
    with freeze_time(_MITTAGS):
        write_user_tier(uid, "premium")  # kein Tageslimit — nur die Schwelle wird gemessen
        trip = make_trip(trip_id)
        save_trip(trip, uid)
        reset_radar_cache()
        mails: list = []
        svc = trip_alert_service(
            uid, settings_email_only(), CountingFrameSource(onset_minutes=onset_minutes),
            lambda subject, body: mails.append((subject, body)),
        )
        return svc.check_radar_alerts(), mails


def _compare_run(uid: str, preset_id: str, onset_minutes: int) -> tuple[int, list]:
    """Gegenstueck fuer den Ortsvergleichs-Pfad — dieselbe gestellte Uhr.

    Der Ortsvergleich hat KEINEN Segment-Bezug und war in der Messung auch
    nicht betroffen; er wird trotzdem gestellt, damit beide Haelften
    desselben Tests denselben Zeitbezug haben und die Datei als Ganzes
    wanduhr-frei ist."""
    with freeze_time(_MITTAGS):
        write_user_tier(uid, "premium")
        save_location(location("loc-onset", "Onset-Ort"), user_id=uid)
        write_presets(uid, [radar_preset(preset_id, ["loc-onset"], user_id=uid)])
        reset_radar_cache()
        mails: list = []
        svc = compare_radar_service(
            uid, settings_email_only(), CountingFrameSource(onset_minutes=onset_minutes),
            lambda subject, body: mails.append((subject, body)),
        )
        return svc.check_all_compare_presets(), mails


def test_ac1_shared_threshold_drives_both_paths(monkeypatch):
    """AC-1: Drift-Waechter statt Identitaetspruefung.

    Ein `is`-Vergleich auf den Zahlwert 55 taugt nicht — ein unabhaengig
    hingeschriebenes Literal `55` an einer der beiden Aufrufstellen wuerde
    ihn ebenso bestehen. Stattdessen wird die geteilte Konstante
    `services.radar_service.RADAR_ONSET_THRESHOLD_MIN` zur Laufzeit auf
    einen Fremdwert (30) gesetzt: nur wenn BEIDE Pfade (Trip UND
    Ortsvergleich) diesen Wert tatsaechlich referenzieren — statt eine
    eigene, beim Import gebundene Kopie zu pflegen — aendert sich ihr
    Ausloeseverhalten fuer denselben Onset (38 Min, ein erreichbarer
    Rasterwert). Eine wieder eingeschlichene lokale Kopie faellt durch:
    sie bliebe beim Monkeypatch der geteilten Konstante unberuehrt und
    wuerde weiterhin bei der Default-Schwelle 55 pruefen.
    """
    from services import radar_service

    onset = 38  # < 55 (Default) und >= 30 (Fremdwert) -- trennscharf fuer beide Schwellen

    # ---- Baseline: unveraenderte Default-Schwelle (55) -> Onset 38 loest in
    #      BEIDEN Pfaden aus.
    uid_trip_base, uid_cmp_base = fresh_uid("ac1-trip-base"), fresh_uid("ac1-cmp-base")
    clean_uid(uid_trip_base)
    clean_uid(uid_cmp_base)
    try:
        sent_trip_base, _ = _trip_run(uid_trip_base, "trip-ac1-base", onset)
        sent_cmp_base, _ = _compare_run(uid_cmp_base, "cp-ac1-base", onset)
        assert sent_trip_base == 1, (
            f"Voraussetzung: bei Default-Schwelle 55 muss Onset {onset} im "
            f"Trip-Pfad ausloesen, erhalten {sent_trip_base}"
        )
        assert sent_cmp_base == 1, (
            f"Voraussetzung: bei Default-Schwelle 55 muss Onset {onset} im "
            f"Ortsvergleichs-Pfad ausloesen, erhalten {sent_cmp_base}"
        )
    finally:
        clean_uid(uid_trip_base)
        clean_uid(uid_cmp_base)

    # ---- Fremdwert 30 (Laufzeit-Monkeypatch der geteilten Konstante):
    #      BEIDE Pfade duerfen Onset 38 danach NICHT mehr ausloesen.
    uid_trip_patched = fresh_uid("ac1-trip-patched")
    uid_cmp_patched = fresh_uid("ac1-cmp-patched")
    clean_uid(uid_trip_patched)
    clean_uid(uid_cmp_patched)
    monkeypatch.setattr(radar_service, "RADAR_ONSET_THRESHOLD_MIN", 30)
    try:
        sent_trip_patched, _ = _trip_run(uid_trip_patched, "trip-ac1-patched", onset)
        sent_cmp_patched, _ = _compare_run(uid_cmp_patched, "cp-ac1-patched", onset)
        assert sent_trip_patched == 0, (
            f"Fremdwert 30 statt 55 haette Onset {onset} im Trip-Pfad "
            f"unterdruecken muessen -- eine unabhaengige lokale Kopie der "
            f"Schwelle waere hier durchgefallen: {sent_trip_patched}"
        )
        assert sent_cmp_patched == 0, (
            f"Fremdwert 30 statt 55 haette Onset {onset} im "
            f"Ortsvergleichs-Pfad unterdruecken muessen -- eine unabhaengige "
            f"lokale Kopie der Schwelle waere hier durchgefallen: "
            f"{sent_cmp_patched}"
        )
    finally:
        clean_uid(uid_trip_patched)
        clean_uid(uid_cmp_patched)


# ═══════════════════════════ AC-2 / AC-3 ══════════════════════════════════

# Am Cron-Takt `7,22,37,52` + 15-Min-Datenraster erreichbare Onset-Werte
# (docs/context/fix-2009-nowcast-vorlauf.md, Root-Cause-Tabelle). Bei
# Schwelle 55 loesen 8/23/38/53 aus, 68/83 nicht mehr.
_GRID = [
    (8, True), (23, True), (38, True), (53, True),
    (68, False), (83, False),
]


@pytest.mark.parametrize(
    "onset_minutes,expect_alert", _GRID,
    ids=[f"{m}min-{'alarm' if e else 'still'}" for m, e in _GRID],
)
def test_ac2_trip_variance_over_grid_values(onset_minutes, expect_alert):
    """AC-2: Trip-Pfad ueber die sechs erreichbaren Rasterwerte -- 8/23/38/53
    loesen bei Schwelle 55 genau EINEN Alarm aus, 68/83 keinen. Schliesst
    die Blindstelle: heute prueft kein Test, dass `onset_minutes`
    ueberhaupt variieren kann (`CountingFrameSource`-Default ist 8)."""
    uid = fresh_uid(f"ac2-{onset_minutes}")
    trip_id = f"trip-ac2-{onset_minutes}"
    clean_uid(uid)
    try:
        sent, mails = _trip_run(uid, trip_id, onset_minutes)
        expected = 1 if expect_alert else 0
        assert sent == expected, (
            f"Onset {onset_minutes} Min bei Schwelle 55: erwartet {expected} "
            f"Alarm(e), erhalten {sent}"
        )
        assert len(mails) == expected, (
            f"mail_sink-Aufrufe stimmen nicht mit dem Rueckgabewert ueberein: "
            f"{len(mails)} Aufrufe, sent={sent}"
        )
    finally:
        clean_uid(uid)


@pytest.mark.parametrize(
    "onset_minutes,expect_alert", _GRID,
    ids=[f"{m}min-{'alarm' if e else 'still'}" for m, e in _GRID],
)
def test_ac3_compare_variance_over_grid_values(onset_minutes, expect_alert):
    """AC-3: Ortsvergleich-Pfad, dieselbe Parametrisierung wie AC-2 --
    Paritaet zwischen Trip und Ortsvergleich (ADR-0021)."""
    uid = fresh_uid(f"ac3-{onset_minutes}")
    preset_id = f"cp-ac3-{onset_minutes}"
    clean_uid(uid)
    try:
        sent, mails = _compare_run(uid, preset_id, onset_minutes)
        expected = 1 if expect_alert else 0
        assert sent == expected, (
            f"Onset {onset_minutes} Min bei Schwelle 55: erwartet {expected} "
            f"Alarm(e), erhalten {sent}"
        )
        assert len(mails) == expected, (
            f"mail_sink-Aufrufe stimmen nicht mit dem Rueckgabewert ueberein: "
            f"{len(mails)} Aufrufe, sent={sent}"
        )
    finally:
        clean_uid(uid)
