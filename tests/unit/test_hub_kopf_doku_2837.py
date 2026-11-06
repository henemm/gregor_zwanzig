# doc-compliance-test
"""Doku-Folgen von #2837 Scheibe S1 (Hub-Kopf als ein Baustein, Epic #2345), AC-12.

Spec: docs/specs/modules/rework_2837_s1_hub_kopf.md (Abschnitt „Ablösung", AC-12).

Konventions-Waechter ueber DOKU-Dateien, kein Verhaltensnachweis. Eine Entscheidung wird
nie still rueckgaengig gemacht (CLAUDE.md, ADR-Regel): der Umbau hebt zwei ausdrueckliche
Entscheidungen frueherer Specs auf und braucht dafuer

- ADR `docs/adr/0110-hub-kopf-und-anlege-rahmen-ein-baustein.md` mit Abschnitt „Löst ab"
  (#2284 S1 Entscheidung 6, #2284 S2 Entscheidungen 7 und 8) und Verweis auf ADR-0097,
- den Index-Eintrag in `docs/adr/README.md` (Konsistenz bewacht zusaetzlich
  tests/test_adr_index_drift.py),
- je einen „Abgelöst durch ADR-0110"-Hinweis in `feat_2284_s1_subscription_header.md` und
  `feat_2284_s2_trip_kopf.md` (bei eingefrorener Spec im Changelog/Known Limitations, nicht
  an der gesperrten Stelle — die alte Entscheidung bleibt als historischer Beleg stehen),
- den nachgezogenen Wortlaut in `docs/reference/design_system.md` (Accent = Weiter /
  Aktiv-Zustand, Hauptaktion = Ink / `Btn primary`).

Pfadregel #1409: Prueflinge relativ zu DIESER Datei aufgeloest.

    uv run pytest tests/unit/test_hub_kopf_doku_2837.py -v
"""
from __future__ import annotations

import re
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
ADR = REPO / "docs" / "adr" / "0110-hub-kopf-und-anlege-rahmen-ein-baustein.md"
ADR_INDEX = REPO / "docs" / "adr" / "README.md"
S1 = REPO / "docs" / "specs" / "modules" / "feat_2284_s1_subscription_header.md"
S2 = REPO / "docs" / "specs" / "modules" / "feat_2284_s2_trip_kopf.md"
DESIGN = REPO / "docs" / "reference" / "design_system.md"


def _lies(pfad: Path) -> str:
    assert pfad.is_file(), f"Doku fehlt: {pfad.relative_to(REPO)}"
    return pfad.read_text(encoding="utf-8")


def _abschnitt(text: str, ueberschrift: str, datei: Path) -> str:
    treffer = re.split(rf"^##\s+{re.escape(ueberschrift)}\s*$", text, flags=re.M)
    assert len(treffer) == 2, f"{datei.name}: Abschnitt '## {ueberschrift}' nicht genau einmal"
    return re.split(r"^##\s", treffer[1], maxsplit=1, flags=re.M)[0]


# ─── ADR-0110 ───────────────────────────────────────────────────────────────


def test_adr_0110_existiert_mit_titel_und_status():
    text = _lies(ADR)
    assert re.search(r"^#\s+ADR-0110\b", text, flags=re.M), "ADR-0110: Titelzeile '# ADR-0110 …' fehlt"
    assert "#2837" in text, "ADR-0110 nennt das Issue #2837 nicht"


def _loest_ab(text: str) -> str:
    """„Löst ab"-Block: Abschnitt `## Löst ab` ODER Label `**Löst ab:**` (Muster ADR-0011:165)
    bis zur naechsten Ueberschrift."""
    if re.search(r"^##\s+Löst ab\s*$", text, flags=re.M):
        return _abschnitt(text, "Löst ab", ADR)
    teile = text.split("**Löst ab:**")
    assert len(teile) == 2, f"{ADR.name}: weder Abschnitt '## Löst ab' noch genau ein Label '**Löst ab:**' ({len(teile) - 1}x)"
    return re.split(r"^#{1,6}\s", teile[1], maxsplit=1, flags=re.M)[0]


def test_adr_0110_loest_die_beiden_2284_entscheidungen_ab():
    loest_ab = _loest_ab(_lies(ADR))
    assert "feat_2284_s1_subscription_header" in loest_ab, "„Löst ab“ nennt #2284 S1 nicht"
    assert re.search(r"Entscheidung\s+6\b", loest_ab), "„Löst ab“ nennt S1 Entscheidung 6 nicht"
    assert "feat_2284_s2_trip_kopf" in loest_ab, "„Löst ab“ nennt #2284 S2 nicht"
    assert re.search(r"Entscheidungen?\s+7\b", loest_ab) and re.search(r"\b8\b", loest_ab), (
        "„Löst ab“ nennt S2 Entscheidungen 7 und 8 nicht")


def test_adr_0110_schreibt_adr_0097_fort_und_begruendet_ink_mit_kontrast():
    text = _lies(ADR)
    assert "ADR-0097" in text or "0097-trip-ortsvergleich-code-teilung" in text, "ADR-0110 verweist nicht auf ADR-0097"
    assert "Ink" in text or "--g-ink" in text, "ADR-0110 nennt Hauptaktion = Ink nicht"
    assert "4,5" in text or "4.5" in text, "ADR-0110 begruendet nicht mit der Kontrast-Schwelle (WCAG-AA 4,5:1)"


def test_adr_index_fuehrt_0110():
    index = _lies(ADR_INDEX)
    zeilen = [z for z in index.splitlines() if "[0110](0110-hub-kopf-und-anlege-rahmen-ein-baustein.md)" in z]
    assert len(zeilen) == 1, f"docs/adr/README.md: Index-Zeile fuer 0110 nicht genau einmal ({len(zeilen)}x)"


# ─── „Abgelöst durch"-Hinweise in den alten Specs ───────────────────────────


def _hinweis_zeilen(text: str) -> list[str]:
    return [z for z in text.splitlines() if re.search(r"Abgelöst durch\s+(\[)?ADR-0110", z)]


def test_s1_spec_traegt_hinweis_abgeloest_durch_adr_0110_fuer_entscheidung_6():
    text = _lies(S1)
    zeilen = _hinweis_zeilen(text)
    assert zeilen, f"{S1.name}: kein „Abgelöst durch ADR-0110“-Hinweis"
    assert any("#2837" in z and re.search(r"Entscheidung\s+6\b", z) for z in zeilen), (
        f"{S1.name}: der Hinweis nennt nicht #2837 und Entscheidung 6")
    # historischer Beleg bleibt: die Entscheidung selbst wird nicht gelöscht
    assert "Seiten-Chrome bleibt in der Seite" in text or "Seiten-Chrome" in text, (
        f"{S1.name}: die abgelöste Entscheidung 6 ist verschwunden (nie löschen, nur ablösen)")


def test_s2_spec_traegt_hinweis_abgeloest_durch_adr_0110_fuer_entscheidungen_7_und_8():
    text = _lies(S2)
    zeilen = _hinweis_zeilen(text)
    assert zeilen, f"{S2.name}: kein „Abgelöst durch ADR-0110“-Hinweis"
    assert any("#2837" in z and re.search(r"\b7\b", z) and re.search(r"\b8\b", z) for z in zeilen), (
        f"{S2.name}: der Hinweis nennt nicht #2837 und die Entscheidungen 7 und 8")
    if re.search(r"^frozen_spec_sha256:", text, flags=re.M):
        # eingefroren: Vermerk in den beweglichen Abschnitten (Muster feat_2682 AC-19)
        beweglich = _abschnitt(text, "Changelog", S2) + _abschnitt(text, "Known Limitations", S2)
        assert _hinweis_zeilen(beweglich), f"{S2.name} ist eingefroren: Hinweis gehört in Changelog/Known Limitations"


# ─── design_system.md: Hauptaktion = Ink, Accent = Weiter/Aktiv ─────────────


def test_design_system_nennt_accent_weiter_aktiv_und_hauptaktion_ink():
    text = _lies(DESIGN)
    zeile = [z for z in text.splitlines() if z.startswith("| `--g-accent`")]
    assert len(zeile) == 1, "design_system.md: Token-Zeile `--g-accent` nicht genau einmal"
    assert "CTA" not in zeile[0], f"design_system.md: `--g-accent` heißt noch „CTA“: {zeile[0]}"
    assert "Weiter" in zeile[0] and "Aktiv" in zeile[0], f"design_system.md: `--g-accent` nicht als Weiter/Aktiv beschrieben: {zeile[0]}"
    assert re.search(r"Hauptaktion[^\n]*(Ink|--g-ink|Btn primary)", text), (
        "design_system.md: kein Satz „Hauptaktion = Ink (Btn primary)“")
