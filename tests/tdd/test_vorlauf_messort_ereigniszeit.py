"""TDD RED — Issue #2261 Teil A, A-1: Messort zur Ereigniszeit (AC-3, AC-4).

SPEC: docs/specs/modules/feat_2261_a1_radar_vorlauf.md (AC-3, AC-4;
Implementation Details 3)

Bei Schwelle 180 darf Regen an einem Messpunkt nur ausloesen, wenn der Nutzer
laut Zeitplan zur Ereigniszeit dort ist: Punkt k ist faellig, wenn
`jetzt + onset_k <= E_k` mit `E_k = p_{k+1} + 30` (letzter Punkt und
Einzelpunkt: Fenster offen); laufender Regen ist an jedem Punkt faellig.

Geometrie (`tests/helpers/radar_vorlauf_strecke.py`, analytisch):
`ETAPPE_MITTEL` 11:00-14:00, 24 km, Uhr 12:00 -> sechs Punkte, Durchgang
`jetzt + 27 + 15k`, Fenster-Enden 72/87/102/117/132/offen.

RED-Grund je Test:
* `test_regen_nach_dem_weitergehen_loest_nicht_aus` — RED ueber die
  Positivkontrolle (Onset 100 an Punkt 3 im Fenster loest heute nicht aus,
  Schwelle 55). Die Negativ-Haelfte (Onset 150 an Punkt 3, Fenster-Ende 117)
  faengt Spec-Mutation 3 (Faelligkeitsfenster entfernt).
* `test_regen_im_aufenthaltsfenster_loest_aus`, `test_letzter_punkt_fenster_offen`,
  `test_einzelpunkt_fall_fenster_offen` — RED: Onset > 55 loest heute nicht aus.
* `test_laufender_regen_ist_ueberall_faellig` — HEUTE GRUEN (Regressionswaechter):
  faengt eine Faelligkeitspruefung, die `onset_minutes` (bei laufendem Regen
  `None`) gegen das Fenster rechnet.
* `test_durchgangszeit_folgt_linearer_interpolation` — RED: die neue
  Durchgangszeit-Funktion `trip_segments.points_with_passage_times` fehlt.
* `test_jeder_alarm_von_heute_loest_weiter_aus` (AC-4) — HEUTE GRUEN
  (Regressionswaechter): faengt Spec-Mutation 4 (Toleranz 0 / Fenster zu eng).

Mock-frei: echte `check_radar_alerts()`-Laeufe ueber die `AlarmPruefstrecke`,
gestellt ist nur die Radar-Quelle (Ergebnis je Punktindex, Zuordnung ueber die
Koordinate). Je Test zwei verschiedene Nutzer.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
from freezegun import freeze_time

from tests.helpers import radar_vorlauf_strecke as strecke
from tests.helpers.nowcast_gate_fixtures import clean_uid

_NUTZER = ("a", "b")


def _alarme(tag: str, etappe, script) -> list[int]:
    """Ein Lauf je Nutzer; liefert die Ausloesezahlen."""
    return [
        strecke.szenario_lauf(f"{tag}-{n}", etappe, script)[0].triggered_count
        for n in _NUTZER
    ]


# ─────────────────────────────── AC-3 ────────────────────────────────────


def test_regen_nach_dem_weitergehen_loest_nicht_aus():
    """AC-3 GIVEN Regen beginnt an Punkt 3 erst, nachdem der Nutzer laut
    Zeitplan Punkt 3 laengst verlassen hat (`jetzt + 150 > p_4 + 30 = 117`)
    / WHEN der Prueflauf laeuft / THEN kein Alarm.

    Positivkontrolle im selben Test (Pflicht): derselbe Punkt mit Beginn
    INNERHALB des Fensters (100 <= 117) loest aus — sonst bewiese die Stille
    nur, dass die Schwelle noch bei 55 steht."""
    etappe = strecke.ETAPPE_MITTEL
    e3 = etappe.fenster_ende_min()[3]
    assert e3 is not None and 100 <= e3 - 10 and 150 >= e3 + 10, (
        f"Testvoraussetzung: Fenster-Ende an Punkt 3 muss klar zwischen 100 "
        f"und 150 liegen, ist {e3}"
    )

    kontrolle = _alarme("ac3-kontrolle", etappe, {3: strecke.nass(100)})
    assert kontrolle == [1, 1], (
        f"AC-3 Positivkontrolle: Beginn in 100 Min an Punkt 3 liegt im "
        f"Aufenthaltsfenster (bis {e3:.0f}) und muss ausloesen, erhalten "
        f"{kontrolle}"
    )
    spaet = _alarme("ac3-spaet", etappe, {3: strecke.nass(150)})
    assert spaet == [0, 0], (
        f"AC-3: Beginn in 150 Min an Punkt 3 — der Nutzer ist laut Zeitplan "
        f"seit {e3:.0f} Min weiter, kein Alarm erwartet, erhalten {spaet}"
    )


def test_regen_im_aufenthaltsfenster_loest_aus():
    """AC-3 GIVEN Regen beginnt an Punkt 3 innerhalb des Aufenthaltsfensters
    (`jetzt + 100 <= p_4 + 30 = 117`) / WHEN der Prueflauf laeuft / THEN wird
    alarmiert."""
    etappe = strecke.ETAPPE_MITTEL
    e3 = etappe.fenster_ende_min()[3]
    assert e3 is not None and 100 <= e3 - 10, f"Testvoraussetzung: E_3={e3}"
    erhalten = _alarme("ac3-fenster", etappe, {3: strecke.nass(100)})
    assert erhalten == [1, 1], (
        f"AC-3: Beginn in 100 Min an Punkt 3 liegt im Aufenthaltsfenster (bis "
        f"{e3:.0f} Min) und muss ausloesen, erhalten {erhalten}"
    )


def test_letzter_punkt_fenster_offen():
    """AC-3 GIVEN Regen beginnt erst in 170 Min am LETZTEN Messpunkt / WHEN
    der Prueflauf laeuft / THEN wird alarmiert (Fenster nach oben offen: der
    Nutzer erreicht das Ziel und bleibt dort). Gegenprobe: derselbe Beginn am
    vorletzten Punkt (Fenster-Ende 132) loest NICHT aus."""
    etappe = strecke.ETAPPE_MITTEL
    fenster = etappe.fenster_ende_min()
    letzter = len(fenster) - 1
    assert letzter == 5 and fenster[letzter] is None and fenster[4] < 160, (
        f"Testvoraussetzung: sechs Punkte, letzter offen, vorletzter endet vor "
        f"160: {fenster}"
    )
    erhalten = _alarme("ac3-letzter", etappe, {letzter: strecke.nass(170)})
    assert erhalten == [1, 1], (
        f"AC-3: Beginn in 170 Min am letzten Punkt muss ausloesen (Fenster "
        f"offen), erhalten {erhalten}"
    )
    vorletzter = _alarme("ac3-vorletzter", etappe, {4: strecke.nass(170)})
    assert vorletzter == [0, 0], (
        f"AC-3: derselbe Beginn am vorletzten Punkt (Fenster bis "
        f"{fenster[4]:.0f} Min) darf nicht ausloesen, erhalten {vorletzter}"
    )


def test_einzelpunkt_fall_fenster_offen():
    """AC-3 GIVEN Reststrecke unter dem Punktabstand (genau EIN Messpunkt)
    und Regenbeginn in 170 Min / WHEN der Prueflauf laeuft / THEN wird
    alarmiert (Einzelpunkt: Fenster offen)."""
    etappe = strecke.ETAPPE_KURZ
    assert len(etappe.punkte_km()) == 1, (
        f"Testvoraussetzung: Einzelpunkt-Fall, Punkte {etappe.punkte_km()}"
    )
    erhalten = _alarme("ac3-einzel", etappe, {0: strecke.nass(170)})
    assert erhalten == [1, 1], (
        f"AC-3: Einzelpunkt mit Beginn in 170 Min muss ausloesen, erhalten "
        f"{erhalten}"
    )


@pytest.mark.parametrize("onset", [82, 100, 150])
def test_regen_an_punkt_0_nach_dem_weitergehen_loest_nicht_aus(onset):
    """AC-3 (Adversary F001) GIVEN Regen nur am ERSTEN Messpunkt, Beginn erst
    nach dessen Aufenthaltsfenster (`E_0 = p_1 + 30 = 72` auf ETAPPE_MITTEL)
    / WHEN der Prueflauf laeuft / THEN kein Alarm — auch Punkt 0 unterliegt
    dem Fenster, nicht nur die Folgepunkte.

    Bewacht den Rueckfall-Pfad: filtert das Fenster ALLE Punkte heraus, darf
    das ungefilterte Ergebnis von Punkt 0 nicht trotzdem ausloesen."""
    etappe = strecke.ETAPPE_MITTEL
    e0 = etappe.fenster_ende_min()[0]
    assert e0 is not None and onset >= e0 + 10, (
        f"Testvoraussetzung: Beginn {onset} klar hinter E_0={e0}"
    )
    erhalten = _alarme(f"ac3-p0-spaet-{onset}", etappe, {0: strecke.nass(onset)})
    assert erhalten == [0, 0], (
        f"AC-3: Beginn in {onset} Min an Punkt 0 — der Nutzer ist laut Zeitplan "
        f"seit {e0:.0f} Min weiter, kein Alarm erwartet, erhalten {erhalten}"
    )


def test_toleranz_ist_30_minuten_nicht_mehr():
    """AC-3 (Adversary M17b): die Toleranz hinter dem naechsten Durchgang ist
    30 Min. Beginn in 130 Min an Punkt 3 liegt hinter `E_3 = p_4 + 30 = 117`
    — kein Alarm. Bei einer zu weiten Toleranz (60 -> 147) loeste er aus."""
    etappe = strecke.ETAPPE_MITTEL
    e3 = etappe.fenster_ende_min()[3]
    assert e3 is not None and e3 + 10 <= 130 <= e3 + 30 - 10, (
        f"Testvoraussetzung: 130 klar zwischen E_3={e3} und E_3+30"
    )
    erhalten = _alarme("ac3-toleranz", etappe, {3: strecke.nass(130)})
    assert erhalten == [0, 0], (
        f"AC-3: Beginn in 130 Min an Punkt 3 liegt hinter dem Fenster-Ende "
        f"{e3:.0f} (Toleranz 30) — kein Alarm erwartet, erhalten {erhalten}"
    )


@pytest.mark.parametrize("onset", [57, 62])
def test_regen_an_punkt_0_im_aufenthaltsfenster_loest_aus(onset):
    """AC-3 Positivgrenze zu F001: Beginn an Punkt 0 jenseits der alten
    Schwelle 55, aber innerhalb `E_0 = 72` -> Alarm. Ohne diese Haelfte
    bewiese die Stille oben nur eine zu enge Regel."""
    etappe = strecke.ETAPPE_MITTEL
    e0 = etappe.fenster_ende_min()[0]
    assert e0 is not None and onset <= e0 - 10, f"Testvoraussetzung: E_0={e0}"
    erhalten = _alarme(f"ac3-p0-fenster-{onset}", etappe, {0: strecke.nass(onset)})
    assert erhalten == [1, 1], (
        f"AC-3: Beginn in {onset} Min an Punkt 0 liegt im Aufenthaltsfenster "
        f"(bis {e0:.0f} Min) und muss ausloesen, erhalten {erhalten}"
    )


@pytest.mark.parametrize("idx", [0, 3])
def test_regenbeginn_genau_am_fensterende_loest_aus(idx):
    """AC-3 Fensterrand (Adversary F102) GIVEN Regen beginnt an Punkt `idx`
    EXAKT am Ende seines Aufenthaltsfensters (`jetzt + onset_k == E_k`;
    ETAPPE_MITTEL: E_0 = 72, E_3 = 117, ganzzahlig, weil der Durchgang im
    15-Min-Takt liegt) / WHEN der Prueflauf laeuft / THEN wird alarmiert —
    die Spec sagt `<=`, der Rand gehoert zum Fenster.

    Gegenprobe im selben Test: eine Minute spaeter (`E_k + 1`) kein Alarm —
    sonst bewiese das Ausloesen am Rand nichts ueber die Lage des Rands."""
    etappe = strecke.ETAPPE_MITTEL
    ende = etappe.fenster_ende_min()[idx]
    assert ende is not None and ende == int(ende) and ende > 60, (
        f"Testvoraussetzung: Fenster-Ende an Punkt {idx} ganzzahlig und jenseits "
        f"der Menge-Grenze 60, ist {ende}"
    )
    rand = int(ende)
    am_rand = _alarme(f"ac3-rand-{idx}", etappe, {idx: strecke.nass(rand)})
    assert am_rand == [1, 1], (
        f"AC-3: Beginn in {rand} Min an Punkt {idx} liegt GENAU am Fenster-Ende "
        f"E_{idx}={ende:.0f} (Spec: `<=`) und muss ausloesen, erhalten {am_rand}"
    )
    dahinter = _alarme(f"ac3-rand-plus1-{idx}", etappe, {idx: strecke.nass(rand + 1)})
    assert dahinter == [0, 0], (
        f"AC-3: Beginn in {rand + 1} Min an Punkt {idx} liegt eine Minute hinter "
        f"E_{idx}={ende:.0f} — kein Alarm erwartet, erhalten {dahinter}"
    )


@pytest.mark.parametrize("idx", [0, 3, 5])
def test_laufender_regen_ist_ueberall_faellig(idx):
    """AC-3 GIVEN Regen laeuft an Punkt `idx` bereits (Lage C: kein kuenftiger
    Beginn, `onset_minutes is None`) / WHEN der Prueflauf laeuft / THEN wird
    alarmiert — an jedem Punkt, auch dort, wo der Nutzer erst spaeter ist.

    Heute gruen (Regressionswaechter): rot wird er, wenn die neue
    Faelligkeitspruefung `jetzt + onset_k` auch fuer laufenden Regen rechnet."""
    etappe = strecke.ETAPPE_MITTEL
    erhalten = _alarme(
        f"ac3-laufend-{idx}", etappe, {idx: strecke.nass(None, laufend=True)},
    )
    assert erhalten == [1, 1], (
        f"AC-3: laufender Regen an Punkt {idx} ist faellig, erhalten {erhalten}"
    )


def _aktives_segment(trip, jetzt: datetime):
    from services.trip_day import trip_local_today
    from services.trip_segments import resolve_current_segment

    aufgeloest = resolve_current_segment(trip, jetzt, trip_local_today(trip, jetzt))
    assert aufgeloest is not None, "Testvoraussetzung: aktives Segment"
    return aufgeloest


@pytest.mark.parametrize(
    "etappe",
    [strecke.ETAPPE_MITTEL, strecke.Etappe("13:00", "16:00", 24.0), strecke.ETAPPE_KURZ],
    ids=["laufend", "vorschau-t0-ist-start", "einzelpunkt"],
)
def test_durchgangszeit_folgt_linearer_interpolation(etappe):
    """AC-3 (reiner Baustein) — die neue Durchgangszeit-Funktion.

    Erwarteter Name und Vertrag (Spec, Implementation Details 3):
    ``trip_segments.points_with_passage_times(trip, active, segment_date, at)
    -> list[tuple[GPXPoint, datetime]]`` — dieselben Punkte in derselben
    Reihenfolge wie ``points_along_remaining_route(trip, active, segment_date,
    at)`` (rueckwaertskompatibel), dazu je Punkt die Durchgangszeit
    ``p_k = t0 + Anteil_k * (active.end_time - t0)``, ``t0 = max(at,
    active.start_time)``, ``Anteil_k = k * Punktabstand / Reststrecke``.

    Soll-Zeiten analytisch aus der Etappe (nicht aus `_remaining_km`); die
    km-Rundung der Segmentlaenge (0,1 km) erlaubt 1 Min Toleranz."""
    import services.trip_segments as trip_segments_mod

    u = strecke.uid("ac3-durchgang")
    clean_uid(u)
    try:
        trip = strecke.baue_trip(u, etappe)
        with freeze_time(strecke.AT):
            jetzt = datetime.now(timezone.utc)
            active, segment_date = _aktives_segment(trip, jetzt)
            at = jetzt + timedelta(minutes=strecke.MESS_OFFSET_MIN)
            punkte = trip_segments_mod.points_along_remaining_route(
                trip, active, segment_date, at,
            )
            funktion = getattr(trip_segments_mod, "points_with_passage_times")
            mit_zeit = funktion(trip, active, segment_date, at)
    finally:
        clean_uid(u)

    assert [p for p, _t in mit_zeit] == punkte, (
        "AC-3: die Punkte muessen identisch zu points_along_remaining_route sein "
        "(Rueckwaertskompatibilitaet)"
    )
    soll = etappe.durchgang()
    assert len(mit_zeit) == len(soll), (
        f"AC-3: {len(mit_zeit)} Punkte, analytisch erwartet {len(soll)}"
    )
    for k, ((_p, ist), erwartet) in enumerate(zip(mit_zeit, soll)):
        abw = abs((ist - erwartet).total_seconds()) / 60
        assert abw <= 1.0, (
            f"AC-3: Durchgangszeit Punkt {k} ist {ist:%H:%M:%S}, erwartet "
            f"{erwartet:%H:%M:%S} (lineare Interpolation), Abweichung {abw:.2f} Min"
        )


# ─────────────────────────────── AC-4 ────────────────────────────────────


@pytest.mark.parametrize("idx", range(6))
@pytest.mark.parametrize("onset", [8, 23, 38, 53])
@pytest.mark.parametrize(
    "etappe", [strecke.ETAPPE_MITTEL, strecke.ETAPPE_SCHNELL],
    ids=["mittel", "schnell-kleines-p1-p0"],
)
def test_jeder_alarm_von_heute_loest_weiter_aus(etappe, onset, idx):
    """AC-4 GIVEN eine Konstellation, die mit Schwelle 55 ausgeloest haette
    (Beginn <= 55 an einem Punkt) / WHEN der Prueflauf mit der neuen Regel
    laeuft / THEN loest er ebenfalls aus (`E_k >= 27 + 30 = 57 > 55`).

    Ueber alle erreichbaren Onsets 8/23/38/53 und Punktindex 0..5, auch auf
    einer schnellen Etappe mit sehr kleinem `p_1 - p_0` (~1,7 Min).

    Heute gruen (Regressionswaechter): rot wird er bei Spec-Mutation 4
    (Toleranz 0 -> Fenster-Ende an Punkt 0 nur ~29 bzw. 42 Min)."""
    fenster = etappe.fenster_ende_min()
    assert idx < len(fenster), f"Testvoraussetzung: Punkt {idx} existiert ({fenster})"
    assert fenster[idx] is None or fenster[idx] >= 57, (
        f"Testvoraussetzung (Spec-Rueckwaerts-Eigenschaft): E_{idx}={fenster[idx]}"
    )
    erhalten = _alarme(f"ac4-{onset}-{idx}", etappe, {idx: strecke.nass(onset)})
    assert erhalten == [1, 1], (
        f"AC-4: Beginn in {onset} Min an Punkt {idx} loeste mit Schwelle 55 aus "
        f"und muss weiter ausloesen, erhalten {erhalten}"
    )
