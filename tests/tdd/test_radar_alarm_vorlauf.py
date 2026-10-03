"""TDD RED — Issue #2261 Teil A, A-1: Radar-Alarm meldet so frueh wie moeglich.

SPEC: docs/specs/modules/feat_2261_a1_radar_vorlauf.md (AC-1)

AC-1: Die Ausloeseschwelle ist die Reichweite der Quelle
(`RADAR_ONSET_THRESHOLD_MIN = NOWCAST_HORIZON_MIN`, 180), keine zweite Zahl.
Trip und Ortsvergleich lesen sie ueber die MODUL-Referenz; ein Drift zwischen
beiden faellt zur Laufzeit auf.

RED heute: die Schwelle steht auf 55 — Regenbeginn in 170 Minuten loest nicht
aus, und die Schwelle ist nicht gleich dem Horizont.

Mock-frei: echte `check_radar_alerts()`-Laeufe ueber die `AlarmPruefstrecke`
bzw. `check_all_compare_presets()`; gestellt ist nur die Radar-Quelle. Die
Drift-Probe setzt eine ECHTE Modulkonstante per `monkeypatch.setattr` um — das
ist kein Mock-Theater, sondern genau die Naht, an der eine beim Import
gebundene Kopie still vorbeilaufen wuerde.

Neue/geaenderte Symbole werden ueber die Modulreferenz zur Laufzeit gelesen,
nie per `from ... import` auf Modulebene (sonst Collection-Error statt
Test-fuer-Test-RED).
"""
from __future__ import annotations

from tests.helpers import radar_vorlauf_strecke as strecke
from tests.helpers.nowcast_gate_fixtures import clean_uid, fresh_uid


def test_beginn_in_170_min_loest_aus():
    """AC-1 GIVEN ein Trip, an dessen Messpunkten der Regen laut Radar-Quelle
    in 170 Minuten beginnt (der Nutzer ist dann noch dort: Ganztags-Etappe,
    Durchgang alle ~4 h) / WHEN der Radar-Prueflauf laeuft / THEN wird genau
    ein Radar-Alarm versendet — fuer zwei verschiedene Nutzer.

    RED heute: Schwelle 55 < 170 -> kein Alarm."""
    etappe = strecke.ETAPPE_GANZTAGS
    fenster = etappe.fenster_ende_min()
    assert fenster[0] is not None and fenster[0] > 170, (
        f"Testvoraussetzung: der Nutzer muss zur Ereigniszeit noch an Punkt 0 "
        f"sein (Fenster-Ende {fenster[0]} Min)"
    )
    script = {i: strecke.nass(170) for i in range(len(etappe.punkte_km()))}
    for nutzer in ("a", "b"):
        lauf, _radar, uid = strecke.szenario_lauf(f"ac1-170-{nutzer}", etappe, script)
        assert lauf.triggered_count == 1, (
            f"AC-1 ({uid}): Regenbeginn in 170 Min liegt in der Reichweite der "
            f"Quelle (180) und muss einen Alarm ausloesen, erhalten "
            f"{lauf.triggered_count}"
        )
        assert len(lauf.mail) == 1, (
            f"AC-1 ({uid}): der Alarm muss den Kanal wirklich erreichen, "
            f"zugestellt {len(lauf.mail)} Mail(s)"
        )


def test_schwelle_ist_abgeleitet_und_trip_und_vergleich_lesen_dieselbe(monkeypatch):
    """AC-1 GIVEN die geteilte Schwelle / WHEN sie gelesen bzw. zur Laufzeit
    umgesetzt wird / THEN ist sie gleich dem Quell-Horizont, und Trip- UND
    Ortsvergleichs-Pfad folgen einem Laufzeit-Fremdwert gemeinsam.

    Drift-Probe (Muster #2009 AC-1, `test_radar_onset_threshold_variance.py`):
    * Default: Onset 170 loest in BEIDEN Pfaden aus (RED heute, 55).
    * Fremdwert 150 per `monkeypatch.setattr` auf das Modul: Onset 170 loest
      in BEIDEN Pfaden NICHT mehr aus. Eine wieder eingeschlichene Literal-
      Schwelle in einem der Pfade (Spec-Mutation 11) bliebe beim Umsetzen
      unberuehrt und wuerde weiter bei 180 ausloesen.
    """
    import services.radar_service as radar_service_mod

    from tests.tdd.test_radar_onset_threshold_variance import _compare_run, _trip_run

    onset = 170
    angelegt: list[str] = []
    try:
        # ---- Default-Schwelle: beide Pfade loesen bei Onset 170 aus.
        u_trip, u_cmp = fresh_uid("2261-ac1-trip"), fresh_uid("2261-ac1-cmp")
        angelegt += [u_trip, u_cmp]
        clean_uid(u_trip)
        clean_uid(u_cmp)
        sent_trip, _ = _trip_run(u_trip, "trip-2261-ac1", onset)
        sent_cmp, _ = _compare_run(u_cmp, "cp-2261-ac1", onset)
        assert sent_trip == 1, (
            f"AC-1: Trip-Pfad muss bei Default-Schwelle Onset {onset} melden, "
            f"erhalten {sent_trip}"
        )
        assert sent_cmp == 1, (
            f"AC-1: Ortsvergleichs-Pfad muss bei Default-Schwelle Onset {onset} "
            f"melden, erhalten {sent_cmp}"
        )

        # ---- Laufzeit-Fremdwert 150: beide Pfade folgen gemeinsam.
        monkeypatch.setattr(radar_service_mod, "RADAR_ONSET_THRESHOLD_MIN", 150)
        u_trip2, u_cmp2 = fresh_uid("2261-ac1-trip-p"), fresh_uid("2261-ac1-cmp-p")
        angelegt += [u_trip2, u_cmp2]
        clean_uid(u_trip2)
        clean_uid(u_cmp2)
        sent_trip2, _ = _trip_run(u_trip2, "trip-2261-ac1-p", onset)
        sent_cmp2, _ = _compare_run(u_cmp2, "cp-2261-ac1-p", onset)
        assert sent_trip2 == 0, (
            f"AC-1 Drift: Schwelle zur Laufzeit 150 — der Trip-Pfad meldet "
            f"Onset {onset} trotzdem ({sent_trip2}); er liest eine eigene Kopie"
        )
        assert sent_cmp2 == 0, (
            f"AC-1 Drift: Schwelle zur Laufzeit 150 — der Ortsvergleichs-Pfad "
            f"meldet Onset {onset} trotzdem ({sent_cmp2}); er liest eine eigene "
            f"Kopie"
        )
    finally:
        for u in angelegt:
            clean_uid(u)
        monkeypatch.undo()

    # Abgeleitet, keine zweite Zahl: der Modulwert IST der Horizont.
    assert radar_service_mod.RADAR_ONSET_THRESHOLD_MIN == radar_service_mod.NOWCAST_HORIZON_MIN, (
        f"AC-1: die Ausloeseschwelle muss die Reichweite der Quelle sein "
        f"(NOWCAST_HORIZON_MIN = {radar_service_mod.NOWCAST_HORIZON_MIN}), ist "
        f"{radar_service_mod.RADAR_ONSET_THRESHOLD_MIN}"
    )
