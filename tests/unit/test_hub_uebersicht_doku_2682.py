# doc-compliance-test
"""Doku-Folgen von #2682 (Hub-Uebersicht geteilt, Epic #2345), AC-19.

Spec: docs/specs/modules/feat_2682_hub_uebersicht_geteilt.md (AC-19).

Konventions-Waechter ueber DOKU-Dateien, kein Verhaltensnachweis: seit #2682 ist die
Hub-Uebersicht EIN geteilter Baustein (`shared/hub-uebersicht/`). Die Doku darf sie
deshalb nicht mehr als Vergleichs-Eigenheit ohne Trip-Gegenpart fuehren:

- `docs/reference/gates_und_ratschen.md`: der Absatz „Dokumentierte Vergleichs-Eigenheit
  ausserhalb des CLAUDE.md-Katalogs" (Uebersicht des Vergleichs-Hubs ohne Gegenpart im
  Trip-Hub, Kopf in compare-hub-fidelity-s8c) ist gestrichen.
- `docs/specs/modules/feat_2347_s4_paritaets_e2e.md`: Befund 6 („Die Hub-Uebersicht ist
  zweimal implementiert"), AC-20 und AC-22 fuehren die Abweichung als erledigt mit
  Verweis auf #2682; die Kopf-Tabelle nennt s8c nicht mehr als Spec ohne Trip-Gegenpart.

Die Kommentare in #2658/#2659 (zweiter Teil von AC-19) sind GitHub-Zustand und werden
in /60 geprueft, nicht hier.

Pfadregel #1409: Prueflinge relativ zu DIESER Datei aufgeloest.
"""
from __future__ import annotations

from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
GATES = REPO / "docs" / "reference" / "gates_und_ratschen.md"
S4 = REPO / "docs" / "specs" / "modules" / "feat_2347_s4_paritaets_e2e.md"

ABSATZ = "Dokumentierte Vergleichs-Eigenheit außerhalb des CLAUDE.md-Katalogs"


def _lies(pfad: Path) -> str:
    assert pfad.is_file(), f"Doku fehlt: {pfad}"
    return pfad.read_text(encoding="utf-8")


def _zeile(text: str, beginn: str) -> str:
    treffer = [z for z in text.splitlines() if z.lstrip().startswith(beginn)]
    assert len(treffer) == 1, f"Zeile mit Beginn {beginn!r} nicht genau einmal gefunden ({len(treffer)}x)"
    return treffer[0]


def test_gates_und_ratschen_fuehrt_die_hub_uebersicht_nicht_mehr_als_vergleichs_eigenheit():
    text = _lies(GATES)
    assert ABSATZ not in text, (
        f"{GATES.name} enthaelt noch den Absatz '{ABSATZ}' -- seit #2682 hat die Uebersicht "
        f"einen Trip-Gegenpart (shared/hub-uebersicht/), der Absatz ist zu streichen")


def test_gates_und_ratschen_behauptet_keinen_fehlenden_trip_gegenpart_der_uebersicht():
    text = _lies(GATES)
    for satz in ("hat keinen Gegenpart im Trip-Hub", "Ihre Fälle\n  bleiben mit Kopf in `compare-hub-fidelity-s8c`"):
        assert satz not in text, f"{GATES.name}: veraltete Aussage {satz!r} steht noch drin"


def test_s4_befund_6_ist_als_erledigt_durch_2682_gefuehrt():
    zeile = _zeile(_lies(S4), "6. **Die Hub-Übersicht ist zweimal implementiert")
    assert "#2682" in zeile and "erledigt" in zeile, (
        "feat_2347_s4 Befund 6 fuehrt die doppelte Hub-Uebersicht nicht als erledigt (#2682)")


def test_s4_ac20_und_ac22_verweisen_auf_die_erledigung_durch_2682():
    text = _lies(S4)
    for ac in ("- **AC-20:**", "- **AC-22:**"):
        zeile = _zeile(text, ac)
        assert "#2682" in zeile, f"feat_2347_s4 {ac} verweist nicht auf die Erledigung durch #2682"


def test_s4_kopftabelle_nennt_s8c_nicht_mehr_ohne_trip_gegenpart():
    zeilen = [z for z in _lies(S4).splitlines() if z.startswith("| `compare-hub-fidelity-s8c.spec.ts`")]
    for z in zeilen:
        assert "keinen Gegenpart im Trip-Hub" not in z, (
            "feat_2347_s4: Kopf-Tabelle fuehrt s8c noch als Uebersicht ohne Trip-Gegenpart")
