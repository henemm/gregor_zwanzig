"""Schrumpf-Test der Ausnahmeliste `BEKANNTE_PAARE` der Pendant-Sperre.

Spec: docs/specs/modules/feat_2346_cockpit_paritaet.md, Abschnitt „S1 — Pendant-Sperre
erweitern", AC-3.

`BEKANNTE_PAARE` nimmt die Bestandspaare von der Namens-Erkennung aus, die es beim Einfuehren
schon gab. Die Liste DARF NUR SCHRUMPFEN:

  (a) jede Datei jedes Eintrags existiert noch — ein veralteter Eintrag wird rot und zwingt
      zum Streichen (S2 streicht die HomeHero*- und Kachel-Paare mit dem Loeschen der Dateien);
  (b) die Liste ist Teilmenge der unten EINGEFRORENEN acht Paare — ein neuer Eintrag ist ein
      Befund, kein Schleichweg.

Vertrag zur Form: `BEKANNTE_PAARE` ist ein Iterable von Zweiergruppen (Tupel/Liste/frozenset)
aus Pfaden RELATIV zur Repo-Wurzel. Verglichen wird als Menge von frozensets, die Reihenfolge
innerhalb eines Paars ist gleichgueltig.

Beide Pruefungen sind bei leerer Liste gruen — das ist gewollt (vollstaendig geschrumpft).
Das Gegengewicht ist der Verhaltenstest
`tests/tdd/test_pendant_gate.py::test_bestandspaar_mitglied_mitfuehren_loest_keinen_fehlalarm_aus`.

Kern-Schicht: kein Netz, kein Mock. Pfadregel #1409: Prueflig und Repo werden relativ zu
DIESER Datei aufgeloest.
"""
from __future__ import annotations

import importlib.util
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
GATE = REPO / ".claude" / "hooks" / "pendant_gate.py"

FE = "frontend/src/lib/components"

# Eingefroren am 2026-10-23 (Aufmass Spec #2346), korrigiert 2026-10-24 (Adversary F003): die
# acht Bestandspaare ausserhalb der alten Reichweite. DARF NUR SCHRUMPFEN — nie hier etwas
# hinzufuegen (die Korrektur vom 24.10. ist ein Messfehler des Aufmasses, kein neues Paar).
EINGEFROREN: frozenset[frozenset[str]] = frozenset({
    frozenset({f"{FE}/organisms/HomeHeroCompare.svelte", f"{FE}/organisms/HomeHeroTrip.svelte"}),
    frozenset({"frontend/src/routes/_home/CompareKachel.svelte",
               "frontend/src/routes/_home/TripKachel.svelte"}),
    frozenset({"src/services/compare_alert.py", "src/services/trip_alert.py"}),
    frozenset({"src/services/compare_alert_channels.py", "src/services/alert_channels.py"}),
    frozenset({"src/services/compare_preview_service.py", "src/services/preview_service.py"}),
    frozenset({"src/services/compare_weather_snapshot.py", "src/services/weather_snapshot.py"}),
    frozenset({f"{FE}/shared/weather-metrics-tab/compareChannelMetricLayouts.ts",
               f"{FE}/shared/weather-metrics-tab/channelMetricLayouts.ts"}),
    # nachgemessen 2026-10-24 (Adversary F003, Sweep mit dem Hook-eigenen Matcher ueber alle
    # git ls-files): das achte Paar, beim Aufmass vom 2026-10-23 uebersehen.
    frozenset({"src/services/trip_forecast.py", "src/services/forecast.py"}),
})


def _bekannte_paare() -> frozenset[frozenset[str]]:
    """`BEKANNTE_PAARE` aus dem ECHTEN Waechter laden (im Test, nicht beim Sammeln)."""
    spec = importlib.util.spec_from_file_location("_pendant_gate_bekannte_paare", GATE)
    modul = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modul)
    roh = modul.BEKANNTE_PAARE
    paare = []
    for eintrag in roh:
        paar = frozenset(eintrag)
        assert len(paar) == 2 and all(isinstance(p, str) for p in paar), (
            f"Eintrag ist keine Zweiergruppe aus Pfaden: {eintrag!r}")
        paare.append(paar)
    assert len(paare) == len(set(paare)), f"Doppelter Eintrag in BEKANNTE_PAARE: {roh!r}"
    return frozenset(paare)


def test_jede_datei_der_ausnahmeliste_existiert_im_repo():
    """AC-3 (a): veralteter Eintrag (Datei geloescht/verschoben) -> rot, Eintrag streichen."""
    fehlend = sorted(p for paar in _bekannte_paare() for p in paar if not (REPO / p).is_file())
    assert not fehlend, (
        "Diese Eintraege in BEKANNTE_PAARE zeigen auf keine Datei mehr — aus der Liste "
        f"streichen (sie darf nur schrumpfen): {fehlend}")


def test_ausnahmeliste_ist_teilmenge_der_eingefrorenen_paare():
    """AC-3 (b): ein hinzugefuegter Eintrag -> rot. Streichen bleibt gruen."""
    neu = _bekannte_paare() - EINGEFROREN
    assert not neu, (
        "BEKANNTE_PAARE enthaelt Paare ausserhalb der eingefrorenen Menge — die Liste darf "
        f"nur schrumpfen: {sorted(sorted(p) for p in neu)}")

