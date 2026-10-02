# doc-compliance-test
"""Ratsche ADR-0049: keine unbegruendete Dreier-Kanalliste ohne Premium-SMS.

Spec: docs/specs/bugfix/fix_2229_premium_sms_kanallisten.md (AC-4, AC-5).

Premium-SMS ist laut ADR-0049 der vierte, gleichrangige Kanal. Listen der
VERSAND-Kanaele muessen ihn fuehren. Listen fuer METRIKEN/LAYOUT bleiben zu
Recht dreistellig (Premium-SMS hat keine eigene Auswahl, sie sendet den
fertigen SMS-Text) — diese Stellen tragen die Marke ``ADR-0049`` in der
Fundzeile oder der Zeile davor. Ausnahmen werden NICHT hier gelistet, sondern
an der Stelle markiert.

Gesucht wird ein Literal der Form ``['email', 'telegram', 'sms']`` bzw.
``("email", "telegram", "sms")`` — beliebige Anfuehrungszeichen/Leerzeichen,
die Liste schliesst direkt nach ``sms``. Eine Vierer-Liste mit
``premium_sms`` ist damit strukturell kein Fund.

Bekannte Grenze: Listen in Objekt-Form, in anderer Reihenfolge, ueber mehrere
Zeilen verteilt oder aus Variablen zusammengesetzt erkennt die Ratsche nicht.

Pruefdatum (Regel-Budget): 2026-12-30 — kein nachweisbarer Fang bis dahin
=> Rueckbau (docs/reference/gates_und_ratschen.md).
"""

from __future__ import annotations

import re
from pathlib import Path

# Pfadregel: relativ zur Testdatei, nie ueber den festen Hauptrepo-Pfad —
# sonst prueft der Worktree das Hauptrepo (falsches Gruen).
REPO = Path(__file__).resolve().parent.parent

SCAN_ROOTS = ("frontend/src", "src", "api")
SUFFIXES = {".ts", ".js", ".svelte", ".py"}
MARKE = "ADR-0049"

_Q = r"""['"]"""
DREIER_LISTE = re.compile(
    rf"[\[\(]\s*{_Q}email{_Q}\s*,\s*{_Q}telegram{_Q}\s*,\s*{_Q}sms{_Q}\s*,?\s*[\]\)]"
)


def _ist_testdatei(pfad: Path) -> bool:
    name = pfad.name
    return (
        "__tests__" in pfad.parts
        or "node_modules" in pfad.parts
        or name.endswith(".test.ts")
        or name.startswith("test_")
    )


def finde_unmarkierte(text: str) -> list[int]:
    """Zeilennummern (1-basiert) unmarkierter Dreier-Kanallisten in ``text``."""
    zeilen = text.splitlines()
    funde: list[int] = []
    for i, zeile in enumerate(zeilen):
        if not DREIER_LISTE.search(zeile):
            continue
        davor = zeilen[i - 1] if i > 0 else ""
        if MARKE in zeile or MARKE in davor:
            continue
        funde.append(i + 1)
    return funde


def _scan_repo() -> list[str]:
    funde: list[str] = []
    for wurzel in SCAN_ROOTS:
        basis = REPO / wurzel
        if not basis.is_dir():
            continue
        for pfad in sorted(basis.rglob("*")):
            if pfad.suffix not in SUFFIXES or not pfad.is_file():
                continue
            if _ist_testdatei(pfad.relative_to(REPO)):
                continue
            text = pfad.read_text(encoding="utf-8", errors="replace")
            for nr in finde_unmarkierte(text):
                funde.append(f"{pfad.relative_to(REPO)}:{nr}")
    return funde


def test_keine_unmarkierte_dreier_kanalliste_im_quelltext():
    """AC-5: Fundmenge unmarkierter Dreier-Kanallisten ist leer."""
    # Plausibilitaet: der Scan sieht ueberhaupt Quelltext (sonst vakuum-gruen).
    assert (REPO / "frontend/src/lib/components/shared/layout-tab/ltChannels.ts").is_file()

    funde = _scan_repo()
    assert funde == [], (
        "Dreier-Kanalliste ohne premium_sms und ohne Marke 'ADR-0049' gefunden. "
        "Versand-Kanal-Liste => premium_sms ergaenzen; Metrik-/Layout-Liste => "
        "Marke 'ADR-0049' mit Begruendung in die Zeile oder die Zeile davor.\n  "
        + "\n  ".join(funde)
    )


def test_selbsttest_unmarkierte_liste_ergibt_fund():
    """AC-5 Selbsttest: die Ratsche erkennt eine unmarkierte Liste."""
    text = "const x = 1;\nconst CH = ['email', 'telegram', 'sms'];\n"
    assert finde_unmarkierte(text) == [2]
    py = 'for ch in ("email", "telegram", "sms"):\n    pass\n'
    assert finde_unmarkierte(py) == [1]


def test_selbsttest_marke_in_zeile_davor_oder_derselben_zeile_ergibt_keinen_fund():
    davor = "// ADR-0049: nur Metrik-/Layout-Kanaele\nconst CH = ['email', 'telegram', 'sms'];\n"
    gleiche = "const CH = ['email', 'telegram', 'sms']; // ADR-0049: Metrik-Kanaele\n"
    assert finde_unmarkierte(davor) == []
    assert finde_unmarkierte(gleiche) == []


def test_selbsttest_marke_zwei_zeilen_davor_genuegt_nicht():
    text = "// ADR-0049\n\nconst CH = ['email', 'telegram', 'sms'];\n"
    assert finde_unmarkierte(text) == [3]


def test_selbsttest_vierer_liste_mit_premium_sms_ergibt_keinen_fund():
    text = '_ALL = ("email", "telegram", "sms", "premium_sms")\n'
    assert finde_unmarkierte(text) == []
