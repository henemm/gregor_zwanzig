# doc-compliance-test
"""Runbook-Pruefung: Stalwart-Eventname ist als VERIFIZIERT eingetragen (#2439, AC-17).

Spec: docs/specs/modules/feat_2439_befehle_antwortzeit.md (AC-17)

Dokumentationspruefung -- liest AUSSCHLIESSLICH ``docs/runbooks/inbound-webhooks.md``,
nie Produkt-Quelltext. Das Runbook ist hier der Pruefling, weil die Zusicherung
(AC-17) eine Aussage der Doku ist: ein Leser, der die Registrierung des
Stalwart-Hooks nachschlaegt, findet den verifizierten Eventnamen und keinen
Verifizierungs-Auftrag mehr.

Repo-Wurzel RELATIV zur Testdatei: die Datei liegt direkt unter ``tests/``,
also ``parents[0] == tests`` und ``parents[1] == <Repo-Wurzel>`` (Lehre aus
05c7cebd8: eine Ebene zu hoch loeste die Wurzel falsch auf).

RED heute: das Runbook nennt den Namen nur einmal und als Aufforderung
"vor Registrierung ... verifizieren"; Z. 102 ("noch offen") nennt ihn gar nicht;
``store.ingest`` ist nicht als nicht existierend vermerkt.
"""
from __future__ import annotations

import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
RUNBOOK = REPO_ROOT / "docs" / "runbooks" / "inbound-webhooks.md"
EVENTNAME = "message-ingest.ham"


def _text() -> str:
    assert (REPO_ROOT / "docs").is_dir(), (
        f"Repo-Wurzel falsch aufgeloest ({REPO_ROOT}) -- 'docs' fehlt dort"
    )
    assert RUNBOOK.is_file(), f"Runbook fehlt: {RUNBOOK}"
    return RUNBOOK.read_text(encoding="utf-8")


def _absaetze_mit(text: str, stichwort: str) -> list[str]:
    """Alle Absaetze (durch Leerzeile getrennt), die ``stichwort`` enthalten."""
    return [a for a in re.split(r"\n\s*\n", text) if stichwort in a]


def test_runbook_nennt_den_verifizierten_eventnamen_an_beiden_stellen():
    """AC-17: Registrierungsabschnitt UND Betriebs-Punkt 4 tragen den Eventnamen."""
    text = _text()
    assert text.count(EVENTNAME) >= 2, (
        f"`{EVENTNAME}` muss an beiden Stellen stehen (Abschnitt 'Stalwart "
        f"registrieren' und Betriebs-Punkt 4), gefunden: {text.count(EVENTNAME)}x"
    )
    absaetze = _absaetze_mit(text, "Eventname")
    assert len(absaetze) >= 2, (
        f"Erwartet >= 2 Absaetze, die den 'Eventname' behandeln, gefunden {len(absaetze)}"
    )
    fehlt = [a.strip().splitlines()[0][:80] for a in absaetze if EVENTNAME not in a]
    assert not fehlt, (
        f"Diese Eventname-Absaetze nennen `{EVENTNAME}` nicht: {fehlt}"
    )


def test_runbook_verlangt_keine_verifikation_vor_der_registrierung_mehr():
    """AC-17: der Satz 'vor Registrierung ... verifizieren' ist weg."""
    text = _text()
    flach = re.sub(r"\s+", " ", text)
    assert not re.search(r"vor\s+Registrierung[^.]{0,80}verifizieren", flach, re.I), (
        "Das Runbook enthaelt noch die Aufforderung 'vor Registrierung ... "
        "verifizieren' -- der Eventname ist verifiziert und gehoert als Fakt hinein"
    )
    assert "noch offen — Eintrag nach Verifikation" not in flach, (
        "Betriebs-Punkt 4 steht noch auf 'noch offen -- Eintrag nach Verifikation'"
    )


def test_runbook_vermerkt_store_ingest_als_nicht_existierend():
    """AC-17: `store.ingest` taucht nur noch als 'existiert nicht' auf."""
    flach = re.sub(r"\s+", " ", _text())
    treffer = [m.start() for m in re.finditer(re.escape("store.ingest"), flach)]
    assert treffer, "`store.ingest` muss als nicht existierend vermerkt bleiben"
    for pos in treffer:
        umfeld = flach[max(0, pos - 120): pos + 160].lower()
        assert re.search(r"nicht\s+exist|existiert\s+nicht|gibt\s+es\s+nicht", umfeld), (
            f"`store.ingest` ohne Vermerk 'nicht existierend' im Umfeld: ...{umfeld}..."
        )
