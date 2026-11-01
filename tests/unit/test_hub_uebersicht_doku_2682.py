# doc-compliance-test
"""Doku-Folgen von #2682 (Hub-Uebersicht geteilt, Epic #2345), AC-19.

Spec: docs/specs/modules/feat_2682_hub_uebersicht_geteilt.md (AC-19).

Konventions-Waechter ueber DOKU-Dateien, kein Verhaltensnachweis: seit #2682 ist die
Hub-Uebersicht EIN geteilter Baustein (`shared/hub-uebersicht/`). Die Doku darf sie
deshalb nicht mehr als Vergleichs-Eigenheit ohne Trip-Gegenpart fuehren:

- `docs/reference/gates_und_ratschen.md`: der Absatz „Dokumentierte Vergleichs-Eigenheit
  ausserhalb des CLAUDE.md-Katalogs" (Uebersicht des Vergleichs-Hubs ohne Gegenpart im
  Trip-Hub, Kopf in compare-hub-fidelity-s8c) ist gestrichen.
- `docs/specs/modules/feat_2347_s4_paritaets_e2e.md` (abgeschlossen, eingefroren): ein Vermerk
  „Abgelöst durch #2682" in Known Limitations und Changelog nennt je Stelle (Befund 6,
  Ausnahme in AC-20, AC-22, s8c-Zeile der Kopftabelle) die Erledigung und den neuen Ort.

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


# ─── feat_2347_s4: Vermerk „Abgelöst durch #2682" ────────────────────────────────
# S4 ist eine abgeschlossene, freigegebene Spec: Befunde, Kopftabelle und AC-Zeilen sind
# eingefroren (edit_gate / frozen_spec_sha256, je Stelle gemessen). Die Erledigung steht
# deshalb — ADR-Muster „Abgelöst durch" — als Vermerk in den beweglichen Abschnitten
# Known Limitations UND Changelog (Eintrag 2026-11-01). Jeder Fall prueft im GEZIELT
# herausgeschnittenen Abschnitt eine eigene Vermerk-Zeile je Stelle, die die Stelle,
# „#2682", „erledigt"/„abgelöst" und den neuen Pfad nennt; die eingefrorene Stelle selbst
# muss als historischer Beleg weiter existieren.

NEUER_PFAD = "shared/hub-uebersicht/HubUebersicht.svelte"


def _abschnitt(text: str, ueberschrift: str) -> str:
    kopf = f"\n## {ueberschrift}\n"
    assert text.count(kopf) == 1, f"Abschnitt '## {ueberschrift}' nicht genau einmal in {S4.name}"
    rest = text.split(kopf, 1)[1]
    return rest.split("\n## ", 1)[0]


def _changelog_eintrag_2682(text: str) -> str:
    zeilen = _abschnitt(text, "Changelog").splitlines()
    start = [i for i, z in enumerate(zeilen) if z.startswith("- 2026-11-01") and "#2682" in z]
    assert len(start) == 1, f"{S4.name}: Changelog-Eintrag 2026-11-01 zu #2682 nicht genau einmal ({len(start)}x)"
    eintrag = [zeilen[start[0]]]
    for z in zeilen[start[0] + 1:]:
        if z.startswith("- "):
            break
        eintrag.append(z)
    return "\n".join(eintrag)


def _vermerk(block: str, stelle: str, wo: str) -> str:
    treffer = [z for z in block.splitlines() if z.lstrip().startswith(f"- {stelle}")]
    assert len(treffer) == 1, f"{S4.name} ({wo}): Vermerk-Zeile fuer '{stelle}' nicht genau einmal ({len(treffer)}x)"
    zeile = treffer[0]
    assert "#2682" in zeile, f"{S4.name} ({wo}): Vermerk zu '{stelle}' nennt #2682 nicht"
    assert "erledigt" in zeile or "abgelöst" in zeile, f"{S4.name} ({wo}): Vermerk zu '{stelle}' sagt nicht erledigt/abgelöst"
    assert NEUER_PFAD in zeile, f"{S4.name} ({wo}): Vermerk zu '{stelle}' nennt den neuen Ort {NEUER_PFAD} nicht"
    return zeile


def _vermerk_in_beiden(text: str, stelle: str) -> None:
    _vermerk(_abschnitt(text, "Known Limitations"), stelle, "Known Limitations")
    _vermerk(_changelog_eintrag_2682(text), stelle, "Changelog 2026-11-01")


def test_s4_befund_6_ist_als_erledigt_durch_2682_gefuehrt():
    text = _lies(S4)
    _zeile(text, "6. **Die Hub-Übersicht ist zweimal implementiert")  # historischer Beleg bleibt
    _vermerk_in_beiden(text, "Befund 6")


def test_s4_ac20_und_ac22_verweisen_auf_die_erledigung_durch_2682():
    text = _lies(S4)
    for ac, stelle in (("- **AC-20:**", "Ausnahme in AC-20"), ("- **AC-22:**", "AC-22")):
        _zeile(text, ac)  # historischer Beleg bleibt
        _vermerk_in_beiden(text, stelle)


def test_s4_kopftabelle_nennt_s8c_nicht_mehr_ohne_trip_gegenpart():
    text = _lies(S4)
    zeilen = [z for z in text.splitlines() if z.startswith("| `compare-hub-fidelity-s8c.spec.ts`")]
    assert len(zeilen) == 1, "feat_2347_s4: Kopftabellen-Zeile zu s8c nicht genau einmal (historischer Beleg)"
    _vermerk_in_beiden(text, "Kopftabelle, Zeile `compare-hub-fidelity-s8c.spec.ts`")
