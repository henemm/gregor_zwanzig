"""Wächter: CLAUDE.md bleibt klein, ihre Verweise tragen, nichts ging beim Auslagern verloren (#2640).

KEIN Verhaltensnachweis im Produktsinn (CLAUDE.md-Ausnahme ``# doc-compliance-test``):
geprüft wird eine Eigenschaft des Dokuments selbst. CLAUDE.md wird bei jeder
Modell-Anfrage jeder Sitzung mitgeladen, jede Zeile wird dort immer wieder bezahlt.
Die Ratsche verhindert, dass die Datei still wieder anwächst.

Regel-Budget: ersetzt die bisher ungeprüfte Prosa-Vorgabe „CLAUDE.md nur
Entscheidungen und Fakten“. Prüfdatum: 2027-01-28 — kein nachweisbarer Fang → Rückbau.

Die Dateien werden relativ zu dieser Testdatei aufgelöst (nicht über den festen
Hauptrepo-Pfad), damit der Test im Worktree nicht gegen fremden Stand prüft.
"""

import re
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
CLAUDE_MD = REPO / "CLAUDE.md"
REF = REPO / "docs" / "reference"

MAX_ZEILEN = 120
MAX_BYTES = 12 * 1024


def _text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


# --- AC-1: Größe --------------------------------------------------------------


def test_ac1_claude_md_hat_hoechstens_120_zeilen():  # doc-compliance-test
    zeilen = len(_text(CLAUDE_MD).splitlines())
    assert zeilen <= MAX_ZEILEN, (
        f"CLAUDE.md hat {zeilen} Zeilen (Obergrenze {MAX_ZEILEN}). "
        "Detailmechanik gehört nach docs/reference/, hier nur Entscheidung + Verweis."
    )


def test_ac1_claude_md_hat_hoechstens_12_kb():  # doc-compliance-test
    groesse = len(CLAUDE_MD.read_bytes())
    assert groesse <= MAX_BYTES, (
        f"CLAUDE.md hat {groesse} Byte (Obergrenze {MAX_BYTES}). "
        "Wird bei jeder Anfrage mitgeladen — kürzen oder auslagern."
    )


# --- AC-2: Verweise tragen ------------------------------------------------------


def _verwiesene_pfade() -> list:
    """Pfade in Backticks, die auf docs/ oder .claude/ zeigen (ohne Platzhalter)."""
    pfade = []
    for treffer in re.findall(r"`((?:docs|\.claude)/[^`\s]+)`", _text(CLAUDE_MD)):
        if any(zeichen in treffer for zeichen in "<>*{}[]$"):
            continue
        pfade.append(treffer.rstrip("/").split("::")[0])
    return sorted(set(pfade))


def test_ac2_jeder_verweis_in_claude_md_zeigt_auf_eine_vorhandene_datei():  # doc-compliance-test
    pfade = _verwiesene_pfade()
    assert pfade, "Vakuum-Schutz: CLAUDE.md verweist auf keine einzige Datei in docs/ oder .claude/"
    fehlend = [p for p in pfade if not (REPO / p).exists()]
    assert not fehlend, f"Verweise ohne Zieldatei: {fehlend}"


# --- AC-3: ausgelagerte Regeln stehen vollständig am Zielort ----------------------

# (Datei, Kernmerkmal, was es belegt)
AUSGELAGERT = [
    (REF / "workflow_und_agenten.md", "OPENSPEC_ACTIVE_WORKFLOW", "Workflow-State, korrigierter Variablenname"),
    (REF / "workflow_und_agenten.md", "loc_limit_override", "Workflow-State: LoC-Limit-Überschreitung"),
    (REF / "workflow_und_agenten.md", "#1199", "Nebenbefund-Triage: Sammel-Issue"),
    (REF / "workflow_und_agenten.md", "SendMessage", "Messaging: Sitzungen im selben Projekt"),
    (REF / "workflow_und_agenten.md", "Agenten-Modelle", "Agenten-Modelle"),
    (REF / "gates_und_ratschen.md", "Mock-Theater", "Test-Politik: Verbot"),
    (REF / "gates_und_ratschen.md", "Kern (deterministisch)", "Test-Politik: Zwei-Schichten-Tabelle"),
    (REF / "gates_und_ratschen.md", "Live-E2E", "Test-Politik: Zwei-Schichten-Tabelle"),
    (REF / "operations_playbook.md", "svelte-check", "CI-Ampel: alle sechs Checks benannt"),
    (REF / "operations_playbook.md", "Token-Budget", "Token-Budget-Regeln"),
    (REF / "design_system.md", "Hoher Kontrast", "Design-Leitprinzip Lesbarkeit"),
]


@pytest.mark.parametrize("datei,merkmal,belegt", AUSGELAGERT)
def test_ac3_ausgelagerte_regel_steht_am_zielort(datei, merkmal, belegt):  # doc-compliance-test
    assert datei.exists(), f"{datei.relative_to(REPO)} fehlt ({belegt})"
    assert merkmal in _text(datei), (
        f"{datei.relative_to(REPO)} enthält „{merkmal}“ nicht — {belegt} wäre beim Kürzen verloren"
    )


# --- AC-4: Abschnittsnamen, auf die Hooks und Tests verweisen ---------------------


@pytest.mark.parametrize(
    "ueberschrift",
    [
        "Test-Politik",
        "Trip/Ortsvergleich-Code-Teilung",
        "Parallele Sessions",
        "Mail-Validatoren & Renderer-Gate",
    ],
)
def test_ac4_abschnitt_bleibt_als_ueberschrift_erhalten(ueberschrift):  # doc-compliance-test
    ueberschriften = re.findall(r"^#{2,3}\s+(.+)$", _text(CLAUDE_MD), flags=re.MULTILINE)
    assert any(ueberschrift in u for u in ueberschriften), (
        f"Überschrift „{ueberschrift}“ fehlt in CLAUDE.md — Hook-Meldungen und Tests verweisen darauf"
    )


# --- AC-5: PO-Vorgaben stehen in CLAUDE.md selbst, nicht nur als Verweis ------------

PO_VORGABEN = [
    ("gleichrangig", "alle vier Kanäle gleichrangig"),
    ("Premium-SMS-Reichweite", "Premium-SMS in Trip UND Ortsvergleich"),
    ("user_id", "Multi-User-Isolation aus dem Auth-Kontext"),
    ('context="route"', "Trip/Ortsvergleich-Teilung: geteilter Baustein mit Kontext-Parameter"),
    ("confidence_pct", "Confidence nicht wählbar"),
    ("Read-Modify-Write", "Datenerhalt bei Schema-Änderungen"),
]


@pytest.mark.parametrize("merkmal,vorgabe", PO_VORGABEN)
def test_ac5_po_vorgabe_steht_in_claude_md_selbst(merkmal, vorgabe):  # doc-compliance-test
    assert merkmal in _text(CLAUDE_MD), f"CLAUDE.md nennt „{merkmal}“ nicht mehr — {vorgabe}"


# --- AC-6: Liefer-Workflow, Rollen und Ampel --------------------------------------


def test_ac6_playbook_benennt_sechs_checks_und_rolle_bei_claude():  # doc-compliance-test
    playbook = _text(REF / "operations_playbook.md")
    assert "alle 5 Checks" not in playbook, "Playbook nennt noch 5 statt der 6 Checks der CI-Ampel"
    assert "6 Checks" in playbook or "sechs Checks" in playbook
    assert "bleiben beim PO" in playbook, (
        "Playbook muss die überstimmte Vorlage von /60-validate ausdrücklich benennen"
    )


def test_ac6_claude_md_nennt_pr_merge_und_deploy_bei_claude():  # doc-compliance-test
    text = _text(CLAUDE_MD)
    assert "Pull Request" in text or " PR " in text
    assert re.search(r"(Merge|Deploy)[^\n]*Claude|Claude[^\n]*(Merge|Deploy)", text), (
        "CLAUDE.md muss sagen, dass PR, Merge und Deploy bei Claude liegen"
    )
