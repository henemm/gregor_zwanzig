# doc-compliance-test
"""TDD RED — die abgeloesten Entscheidungen sind in der Doku vermerkt
(Issue #2050 Scheibe S3b, AC-13 und AC-14).

SPEC: docs/specs/modules/feat_2050_s3b_budget_und_unterdrueckungsgrund.md

Werkzeug-Klasse (CLAUDE.md-Ausnahme ``# doc-compliance-test``, Vorbild
``tests/test_adr_index_drift.py``): hier ist der Dateiinhalt AUSDRUECKLICH der
Pruefgegenstand, nicht ein Ersatz fuer einen Verhaltensnachweis. Die Spec
fuehrt AC-13/AC-14 selbst als "nur Kern-Test, Dateiinhalt-Pruefung auf Doku
ist hier zulaessig" (Abschnitt "Messbarkeit auf Staging").

Fachlicher Grund: die Projektregel "eine dokumentierte Entscheidung wird nie
still rueckgaengig gemacht" (CLAUDE.md, ADR-Abschnitt). Szenario 10 dieser
Scheibe weicht von ADR-0021 ab (amtlicher Pfad protokolliert kuenftig), und
zwei bestehende Spec-ACs werden fuer den Eskalationsfall abgeloest. Ohne die
Vermerke faende ein spaeterer Leser zwei sich widersprechende Zusicherungen
und keinen Hinweis darauf, welche gilt.

RED heute: weder der Nachtrag noch die beiden Abloese-Vermerke existieren.

Pfadregel #1409: die Doku wird relativ zu DIESER Datei aufgeloest — ein
fester Hauptrepo-Pfad pruefte aus dem Worktree die unveraenderte Kopie und
meldete falsches Gruen.
"""
from __future__ import annotations

import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]

ADR_0021 = REPO_ROOT / "docs/adr/0021-shared-deviation-alert-engine.md"
SPEC_S3B = "feat_2050_s3b_budget_und_unterdrueckungsgrund.md"
SPEC_TAGESLIMIT = REPO_ROOT / "docs/specs/modules/alert_daily_limit.md"
SPEC_2065 = REPO_ROOT / "docs/specs/modules/fix_2065_verschaerfung_ueberholt_sperre.md"

# Kopfzeile eines datierten Nachtrags, z.B.
#   - **Nachtrag (Issue #2065, 2026-08-22):** …
_NACHTRAG_KOPF = re.compile(r"^\s*-\s*\*\*Nachtrag\s*\((?P<kopf>[^)]*)\)\s*:\*\*")
_ISO_DATUM = re.compile(r"\d{4}-\d{2}-\d{2}")

# AC-Kopfzeile in einer Spec — beide im Repo vorkommenden Formen
# (``- **AC-1:**`` in den aelteren Specs, ``**AC-1:**`` in den neueren).
_AC_KOPF = re.compile(r"^\s*(?:-\s*)?\*\*AC-(?P<nr>\d+)[:.]?\*\*")


def _nachtraege(text: str) -> list[tuple[int, str, str]]:
    """``(Reihenfolge, Kopf, Rumpf)`` je Nachtrag — der Rumpf reicht bis zum
    naechsten Nachtrag bzw. zur naechsten Ueberschrift."""
    zeilen = text.splitlines()
    starts: list[tuple[int, str]] = []
    for i, zeile in enumerate(zeilen):
        treffer = _NACHTRAG_KOPF.match(zeile)
        if treffer:
            starts.append((i, treffer.group("kopf")))

    ergebnis: list[tuple[int, str, str]] = []
    for rang, (start, kopf) in enumerate(starts):
        ende = starts[rang + 1][0] if rang + 1 < len(starts) else len(zeilen)
        for j in range(start + 1, ende):
            if zeilen[j].startswith("#"):
                ende = j
                break
        ergebnis.append((rang, kopf, "\n".join(zeilen[start:ende])))
    return ergebnis


def _ac_block(pfad: Path, nummer: int) -> str:
    """Text EINES Akzeptanzkriteriums — von seiner Kopfzeile bis zur naechsten
    AC-Kopfzeile oder zur naechsten Ueberschrift."""
    zeilen = pfad.read_text(encoding="utf-8").splitlines()
    start = None
    for i, zeile in enumerate(zeilen):
        treffer = _AC_KOPF.match(zeile)
        if treffer and int(treffer.group("nr")) == nummer:
            start = i
            break
    assert start is not None, (
        f"{pfad.name}: AC-{nummer} nicht gefunden — hat sich die Nummerierung "
        f"verschoben?"
    )
    ende = len(zeilen)
    for j in range(start + 1, len(zeilen)):
        if _AC_KOPF.match(zeilen[j]) or zeilen[j].startswith("#"):
            ende = j
            break
    return "\n".join(zeilen[start:ende])


# ═════════════════════════════════ AC-13 ════════════════════════════════════


def test_ac13_adr_0021_traegt_datierten_nachtrag_zu_2050_s3b():
    """AC-13.

    GIVEN diese Aenderung ist umgesetzt.
    WHEN  ``docs/adr/0021-shared-deviation-alert-engine.md`` gelesen wird.
    THEN  traegt es einen DATIERTEN Nachtrag mit Bezug auf ``#2050 S3b``, der
          beschreibt, dass der amtliche Pfad kuenftig Ruhezeit- und
          Tageslimit-Unterdrueckungen protokolliert — einsortiert NACH dem
          bestehenden #2065-Nachtrag (2026-08-22).

    Die Reihenfolge ist keine Kosmetik: die Nachtraege des ADR sind
    chronologisch zu lesen, ein spaeter eingeschobener Eintrag laese die
    Abloese-Kette in der falschen Richtung erscheinen.

    ROT heute: es gibt keinen #2050-S3b-Nachtrag.
    """
    text = ADR_0021.read_text(encoding="utf-8")
    nachtraege = _nachtraege(text)
    assert nachtraege, f"{ADR_0021.name}: keine Nachtraege gefunden"

    s3b = [n for n in nachtraege if "2050" in n[1] and "S3b" in n[1]]
    assert len(s3b) == 1, (
        f"Erwartet GENAU EINEN Nachtrag mit Bezug auf '#2050 S3b', gefunden "
        f"{len(s3b)}: {[n[1] for n in nachtraege]!r}"
    )
    rang_s3b, kopf_s3b, rumpf_s3b = s3b[0]

    assert _ISO_DATUM.search(kopf_s3b), (
        f"Der Nachtrag muss datiert sein (Format JJJJ-MM-TT), Kopf lautet "
        f"{kopf_s3b!r}"
    )

    zweitausendfuenfundsechzig = [n for n in nachtraege if "2065" in n[1]]
    assert len(zweitausendfuenfundsechzig) == 1, (
        f"Vorbedingung: der #2065-Nachtrag (2026-08-22) muss vorhanden sein, "
        f"gefunden {len(zweitausendfuenfundsechzig)}"
    )
    assert rang_s3b > zweitausendfuenfundsechzig[0][0], (
        f"Der #2050-S3b-Nachtrag muss NACH dem #2065-Nachtrag stehen — "
        f"gefunden auf Position {rang_s3b} gegenueber "
        f"{zweitausendfuenfundsechzig[0][0]}"
    )

    unten = rumpf_s3b.lower()
    for begriff, bedeutung in (
        ("amtlich", "welcher Pfad seine Zusicherung wechselt"),
        ("protokoll", "dass dort kuenftig protokolliert wird"),
        ("ruhezeit", "welche der beiden Stufen betroffen ist"),
        ("tages", "die zweite betroffene Stufe (Tages-Obergrenze)"),
    ):
        assert begriff in unten, (
            f"Der Nachtrag nennt {begriff!r} nicht — ohne diese Angabe fehlt "
            f"{bedeutung}:\n{rumpf_s3b}"
        )


# ═════════════════════════════════ AC-14 ════════════════════════════════════


def _abloese_vermerk_pruefen(pfad: Path, nummer: int) -> None:
    block = _ac_block(pfad, nummer)
    assert SPEC_S3B in block, (
        f"{pfad.name}: AC-{nummer} muss auf {SPEC_S3B} verweisen — sonst "
        f"findet ein Leser die geltende Zusicherung nicht:\n{block}"
    )
    unten = block.lower()
    assert any(wort in unten for wort in ("abgelöst", "abgeloest", "ablöse", "abloese")), (
        f"{pfad.name}: AC-{nummer} nennt den Verweis, sagt aber nicht, dass es "
        f"ABGELOEST ist — ein blosser Querverweis liest sich wie eine "
        f"Ergaenzung, nicht wie eine Ablösung:\n{block}"
    )


def test_ac14_tageslimit_spec_ac1_und_ac2_tragen_den_abloese_vermerk():
    """AC-14 (erste Haelfte): ``alert_daily_limit.md`` AC-1 und AC-2 tragen
    einen Vermerk, dass sie fuer den Eskalationsfall durch diese Spec
    abgeloest sind.

    BEIDE brauchen ihn: AC-1 (Free) und AC-2 (Standard) beschreiben dieselbe
    harte Unterdrueckung fuer zwei Nutzerlevel; ein Vermerk nur an einem
    hinterliesse den anderen als scheinbar weiter geltende Gegenaussage.

    ROT heute: keiner der beiden traegt einen Verweis."""
    _abloese_vermerk_pruefen(SPEC_TAGESLIMIT, 1)
    _abloese_vermerk_pruefen(SPEC_TAGESLIMIT, 2)


def test_ac14_fix_2065_spec_ac7_traegt_den_abloese_vermerk():
    """AC-14 (zweite Haelfte): ``fix_2065_verschaerfung_ueberholt_sperre.md``
    AC-7 traegt denselben Vermerk.

    ROT heute: der Verweis fehlt."""
    _abloese_vermerk_pruefen(SPEC_2065, 7)
