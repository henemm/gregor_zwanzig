# doc-compliance-test
"""TDD RED — Issue #2913 (Epic #2791): ADR-0112, Prüf-Agent und Doku zum Bausteine-Wächter.

Spec: docs/specs/modules/einstellungen_neu_neustart_adr_waechter_elementliste.md — AC-8, AC-16, AC-17.

Reine Dokumentationsmerkmale (Ausnahme der Test-Politik, daher ``# doc-compliance-test``).
Das Verhalten des Wächters prüft frontend/src/lib/__tests__/bausteine_waechter.test.ts.

    uv run pytest tests/test_adr_0112_bausteine_regel_doku.py tests/test_adr_index_drift.py \
        tests/test_claude_md_budget.py
"""
from __future__ import annotations

import re
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
ADR_DIR = REPO / "docs" / "adr"
ADR_0112 = ADR_DIR / "0112-oberflaechen-nur-aus-design-system-bausteinen.md"
ADR_0111 = ADR_DIR / "0111-design-vorgaben-bereinigt-audit-2026-11.md"
AGENT = REPO / ".claude" / "agents" / "mockup-bildpruefer.md"
REF = REPO / "docs" / "reference"


def _text(p: Path) -> str:
    assert p.exists(), f"{p.relative_to(REPO)} fehlt"
    return p.read_text(encoding="utf-8")


# ---------------------------------------------------------------- AC-8
def test_adr_0112_liegt_vor_und_ist_akzeptiert():
    t = _text(ADR_0112)
    assert re.search(r"^#\s*ADR-0112", t, re.M), "Titelzeile ADR-0112 fehlt"
    assert re.search(r"\*\*Status:\*\*\s*Akzeptiert", t), "Status Akzeptiert fehlt"


def test_adr_0112_nennt_die_vier_regeln():
    t = _text(ADR_0112).lower()
    for teil in ("atoms", "molecules", "organisms"):
        assert teil in t, f"Regel 1: Baustein-Ordner {teil} fehlt"
    assert re.search(r"fehlt ein baustein|fehlende[rn]? baustein", t), "Regel 2: fehlende Bausteine zuerst ins System"
    assert "token" in t and "var(--g-" in t, "Regel 3: Styling nur über Tokens"
    assert "wächter" in t and "merge" in t, "Regel 4: Wächter blockt beim Merge"
    assert "bausteine_waechter" in t, "Wächter-Datei muss benannt sein"


def test_adr_0112_hat_pruefdatum_und_loeschbedingung():
    t = _text(ADR_0112)
    assert "2027-02-08" in t, "Prüfdatum 2027-02-08 fehlt"
    assert re.search(r"Löschbedingung|Rückbau", t), "Löschbedingung fehlt"
    assert re.search(r"kein(?:en)? nachweisbare[nr]? Fang", t), "Löschbedingung „kein nachweisbarer Fang“ fehlt"


def test_adr_index_enthaelt_0112_und_0111_verweist():
    readme = _text(ADR_DIR / "README.md")
    assert "](0112-oberflaechen-nur-aus-design-system-bausteinen.md)" in readme, "Index-Zeile 0112 fehlt"
    assert "Ergänzt durch: ADR-0112" in _text(ADR_0111), "ADR-0111 muss „Ergänzt durch: ADR-0112“ tragen"


def test_anti_patterns_006_bis_008_sind_pflicht_mit_waechter():
    t = _text(REPO / "docs" / "design-system" / "ANTI-PATTERNS.md")
    for ap in ("AP-006", "AP-007", "AP-008"):
        start = t.index(f"## {ap}")
        nxt = t.find("\n## ", start + 5)
        abschnitt = t[start : nxt if nxt > 0 else len(t)]
        assert "Pflicht mit Wächter, ADR-0112" in abschnitt, f"{ap}: Vermerk „Pflicht mit Wächter, ADR-0112“ fehlt"


# ---------------------------------------------------------------- AC-16
def _frontmatter(t: str) -> str:
    m = re.match(r"^---\n(.*?)\n---\n", t, re.S)
    assert m, "Agent-Definition ohne Frontmatter"
    return m.group(1)


def test_pruef_agent_hat_nur_bildlesen_kein_quellcode():
    t = _text(AGENT)
    fm = _frontmatter(t)
    assert re.search(r"^name:\s*mockup-bildpruefer\s*$", fm, re.M)
    tools = re.search(r"^tools:\s*(.+)$", fm, re.M)
    assert tools, "tools: muss ausdrücklich gesetzt sein (sonst erbt der Agent alle Werkzeuge)"
    erlaubt = {w.strip() for w in tools.group(1).split(",")}
    assert erlaubt == {"Read"}, f"nur Bildlesen (Read) erlaubt, gefunden: {erlaubt}"
    for verboten in ("Grep", "Glob", "Bash", "Edit", "Write"):
        assert verboten not in erlaubt


def test_pruef_agent_eingaben_runden_und_rolle():
    t = _text(AGENT)
    for eingabe in ("Mockup-Bild", "Staging-Bild", "Elementlisten-Auszug"):
        assert eingabe in t, f"feste Eingabe {eingabe} fehlt"
    assert re.search(r"gleiche[nmr]? Viewport", t), "gleicher Viewport muss verlangt sein"
    assert re.search(r"höchstens zwei Runden", t), "Begrenzung auf höchstens zwei Runden fehlt"
    assert re.search(r"ergänzt die Elementliste", t) and re.search(r"ersetzt sie nicht", t)
    assert re.search(r"kein(?:en)? Quellcode", t), "Verbot des Quellcode-Zugriffs fehlt"


def test_pruef_agent_probelauf_dokumentiert():
    belege = list((REPO / "docs" / "artifacts" / "einstellungen-neu-neustart").glob("*bildpruefer*probelauf*"))
    assert belege, "Probelauf des Prüf-Agenten ist nicht dokumentiert (docs/artifacts/einstellungen-neu-neustart/)"


# ---------------------------------------------------------------- AC-17
def test_gates_und_ratschen_beschreibt_waechter_und_budget():
    t = _text(REF / "gates_und_ratschen.md")
    assert "bausteine_waechter" in t
    assert "SEITEN_SCOPE" in t and "AUSNAHMEN" in t
    assert re.search(r"Neue-Datei-Regel", t)
    zeilen = [z for z in t.splitlines() if "bausteine_waechter" in z and z.lstrip().startswith("|")]
    assert any("2027-02-08" in z for z in zeilen), "Regel-Budget-Tabelle: Zeile mit Prüfdatum 2027-02-08 fehlt"


def test_design_system_verweist_auf_adr_0112():
    t = _text(REF / "design_system.md")
    assert "ADR-0112" in t and "bausteine_waechter" in t


def test_workflow_doku_beschreibt_scheiben_ablauf():
    t = _text(REF / "workflow_und_agenten.md")
    assert "mockup-bildpruefer" in t
    assert re.search(r"Scheibe\s*→\s*Staging-Abgleich\s*→\s*Prüf-Agent", t), "Ablauf Scheibe → Staging-Abgleich → Prüf-Agent fehlt"
    assert re.search(r"höchstens zwei Runden", t)
