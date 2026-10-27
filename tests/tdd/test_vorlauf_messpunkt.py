"""TDD RED — Issue #2261 Teil A, A-1: Messpunkt-Offset entkoppelt (AC-2).

SPEC: docs/specs/modules/feat_2261_a1_radar_vorlauf.md (AC-2)

Heute wird der erste Messpunkt aus der Schwelle berechnet
(`RADAR_ONSET_THRESHOLD_MIN // 2`, `trip_alert.py`). Steht die Schwelle auf
180, wanderte er auf `jetzt + 90` und fiele mit dem Briefing-Offset
(`NOWCAST_HORIZON_MIN // 2`) zusammen. Ziel: eigene Konstante
`RADAR_MEASURE_OFFSET_MIN = 27`, der erste Messpunkt bleibt bit-identisch.

RED heute: mit Schwelle 180 misst der Lauf bei +90 (Zuschreibung am Ort des
Abrufs), und `RADAR_MEASURE_OFFSET_MIN` existiert nicht.

Mock-frei: echter `check_radar_alerts()`-Lauf ueber die `AlarmPruefstrecke`;
die Radar-Quelle schreibt nur mit, WO abgefragt wird. Die Soll-Position ist
analytisch aus der Etappen-Geometrie gerechnet (Nord-Strecke, lineare
Zeitinterpolation), nicht aus dem Pruefling.
"""
from __future__ import annotations

from tests.helpers import radar_vorlauf_strecke as strecke
from tests.helpers.nowcast_gate_fixtures import clean_uid


def test_erster_messpunkt_bleibt_27_min(monkeypatch):
    """AC-2 GIVEN die Schwelle steht auf 180 / WHEN die Messpunkte eines
    Laufs bestimmt werden / THEN liegt der erste Messpunkt bei `jetzt + 27`
    (nicht bei +90), der Briefing-Offset (+90) bleibt davon verschieden, und
    die Konstante wird nicht aus der Schwelle berechnet.

    Die Schwelle wird zur Laufzeit auf 180 gesetzt (echte Modulkonstante) —
    damit ist der Test schon heute trennscharf: ein Messpunkt, der aus der
    Schwelle folgt, wandert dabei mit (Spec-Mutation 2)."""
    import services.radar_service as radar_service_mod

    monkeypatch.setattr(radar_service_mod, "RADAR_ONSET_THRESHOLD_MIN", 180)

    etappe = strecke.ETAPPE_MITTEL  # 11:00-14:00, 24 km, Uhr 12:00
    # Analytisch: +27 -> Zeitanteil 87/180 -> km 11,6; +90 -> 150/180 -> km 20,0
    soll_km = etappe.punkte_km()[0]
    assert abs(soll_km - 11.6) < 1e-9, f"Testvoraussetzung: Soll-km {soll_km}"

    for nutzer in ("a", "b"):
        uid = strecke.uid(f"ac2-{nutzer}")
        clean_uid(uid)
        try:
            trip = strecke.baue_trip(uid, etappe)
            radar = strecke.PunktRadar(None)  # nur mitschreiben
            strecke.lauf(uid, trip, radar)
            assert radar.aufrufe, f"Testvoraussetzung ({uid}): kein Abruf"
            erster_km = min(a["km"] for a in radar.aufrufe)
            assert abs(erster_km - soll_km) < 0.3, (
                f"AC-2 ({uid}): erster Messpunkt bei km {erster_km:.2f}, erwartet "
                f"km {soll_km:.2f} (= jetzt + 27 Min). km ~20 hiesse: der Offset "
                f"folgt noch der Schwelle (180 // 2 = +90)."
            )
        finally:
            clean_uid(uid)

    offset = getattr(radar_service_mod, "RADAR_MEASURE_OFFSET_MIN")
    assert offset == 27, f"AC-2: RADAR_MEASURE_OFFSET_MIN muss 27 sein, ist {offset}"
    assert offset != radar_service_mod.NOWCAST_HORIZON_MIN // 2, (
        "AC-2: Messpunkt-Offset und Briefing-Offset (NOWCAST_HORIZON_MIN // 2) "
        "muessen verschieden bleiben"
    )
