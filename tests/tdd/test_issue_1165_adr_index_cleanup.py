"""TDD RED -- Issue #1165: ADR-Index-Cleanup.

SPEC: docs/specs/modules/issue_1165_adr_index_cleanup.md (AC-1, AC-2, AC-3)

docs/adr/README.md ist aktuell inkonsistent mit dem tatsaechlichen Inhalt von
docs/adr/: ADR-0018 fehlt im Index, und die Nummern 0013 und 0014 sind je
doppelt vergeben. Diese Tests pruefen Markdown-Konsistenz (Dateinamen vs.
Index-Tabelle, Cross-Referenzen) -- kein Laufzeitverhalten, daher als
doc-compliance-test markiert (Ausnahme von der No-File-Content-Check-Regel).
"""
from __future__ import annotations

import re
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[2]
_ADR_DIR = _REPO_ROOT / "docs" / "adr"
_ADR_README = _ADR_DIR / "README.md"

_ADR_FILENAME_RE = re.compile(r"^(\d{4})-.*\.md$")
_INDEX_ROW_RE = re.compile(r"\[(\d{4})\]\(([^)]+\.md)\)")


def _adr_files() -> dict[str, str]:
    """Nummer -> Dateiname fuer alle echten ADR-Dateien (README/_template ausgeschlossen)."""
    files = {}
    for f in _ADR_DIR.iterdir():
        if f.name in ("README.md", "_template.md"):
            continue
        m = _ADR_FILENAME_RE.match(f.name)
        if m:
            files.setdefault(m.group(1), []).append(f.name)
    return files


def _index_rows() -> list[tuple[str, str]]:
    """[(Nummer, Dateiname), ...] aus der Index-Tabelle in README.md."""
    text = _ADR_README.read_text(encoding="utf-8")
    return _INDEX_ROW_RE.findall(text)


# AC-1: Bijektion zwischen docs/adr/*.md-Dateien und Index-Zeilen (# doc-compliance-test)
def test_adr_index_is_bijective_with_files():  # doc-compliance-test
    """
    GIVEN: der Zustand von docs/adr/ nach der geplanten Umnummerierung
    WHEN: man alle docs/adr/*.md-Dateien mit den Index-Zeilen in README.md abgleicht
    THEN: jede Datei ist genau einmal gelistet, keine Nummer doppelt, keine fehlt

    RED (heute): 0013 und 0014 sind je zwei Dateien zugeordnet (Kollision),
    0018 fehlt komplett im Index -> Bijektion verletzt.
    """
    by_number = _adr_files()
    rows = _index_rows()

    # Keine Nummer darf zu zwei verschiedenen Dateien gehoeren
    collisions = {num: names for num, names in by_number.items() if len(names) > 1}
    assert not collisions, f"Nummern-Kollision(en) in docs/adr/: {collisions}"

    row_numbers = [num for num, _ in rows]
    # Keine Nummer doppelt im Index
    duplicate_index_numbers = {n for n in row_numbers if row_numbers.count(n) > 1}
    assert not duplicate_index_numbers, (
        f"Nummer(n) mehrfach im Index gelistet: {duplicate_index_numbers}"
    )

    indexed_filenames = {fname for _, fname in rows}
    actual_filenames = {names[0] for names in by_number.values()}

    missing_from_index = actual_filenames - indexed_filenames
    assert not missing_from_index, f"Datei(en) fehlen im Index: {missing_from_index}"

    dangling_index_entries = indexed_filenames - actual_filenames
    assert not dangling_index_entries, (
        f"Index verweist auf nicht existierende Datei(en): {dangling_index_entries}"
    )


# Meta-Dokumente ueber DIESEN Fix selbst -- beschreiben bewusst die alten
# Nummern als Teil der Migrationsbeschreibung, sind keine echten Cross-Referenzen.
_SELF_REFERENTIAL_EXCLUDES = (
    _REPO_ROOT / "docs" / "context" / "fix-1165-adr-index-cleanup.md",
    _REPO_ROOT / "docs" / "specs" / "modules" / "issue_1165_adr_index_cleanup.md",
)
_SELF_REFERENTIAL_EXCLUDE_DIRS = (_REPO_ROOT / "docs" / "artifacts",)


def _find_adr_mentions(pattern: str) -> list[tuple[Path, str]]:
    hits = []
    for f in _REPO_ROOT.glob("docs/**/*.md"):
        if f in _SELF_REFERENTIAL_EXCLUDES:
            continue
        if any(d in f.parents for d in _SELF_REFERENTIAL_EXCLUDE_DIRS):
            continue
        text = f.read_text(encoding="utf-8", errors="ignore")
        for line in text.splitlines():
            if pattern in line:
                hits.append((f, line))
    return hits


# AC-2: keine verbleibende "ADR-0014"-Referenz im Nullgradgrenze-Kontext (# doc-compliance-test)
def test_no_adr_0014_reference_in_nullgradgrenze_context():  # doc-compliance-test
    """
    GIVEN: der Nullgradgrenze-Kontext (ehemals ADR-0014, jetzt ADR-0019)
    WHEN: man docs/**/*.md nach "ADR-0014" durchsucht
    THEN: jede verbleibende Fundstelle bezieht sich eindeutig auf Telegram/Multi-Bubble,
          keine mehr auf Nullgradgrenze/freezing_level/snow_line

    RED (heute): docs/reference/api_contract.md referenziert "ADR-0014" noch im
    SNOW_LINE-/Nullgradgrenze-Kontext (Zeile ~2371).
    """
    hits = _find_adr_mentions("ADR-0014")
    assert hits, "Erwartet mindestens die bekannten Telegram-Referenzen auf ADR-0014"

    nullgradgrenze_markers = ("snow_line", "SNOW_LINE", "freezing_level", "Nullgradgrenze")
    telegram_markers = ("Telegram", "Bubble", "telegram")

    offending = [
        (f, line)
        for f, line in hits
        if any(m in line for m in nullgradgrenze_markers)
        and not any(m in line for m in telegram_markers)
    ]
    assert not offending, (
        "ADR-0014 wird noch im Nullgradgrenze-Kontext referenziert (sollte ADR-0019 sein): "
        f"{offending}"
    )


# AC-3: keine verbleibende "ADR-0013"-Referenz im node:test-Kontext (# doc-compliance-test)
def test_no_adr_0013_reference_in_node_test_context():  # doc-compliance-test
    """
    GIVEN: der node:test-Kontext (ehemals ADR-0013, jetzt ADR-0020)
    WHEN: man docs/**/*.md nach "ADR-0013" bzw. dem alten Dateinamen durchsucht
    THEN: der alte Dateiname existiert nicht mehr; verbleibende "ADR-0013"-Treffer
          beziehen sich ausschliesslich auf Alert-Threshold/Delta-Sensitivitaet

    RED (heute): docs/adr/README.md und docs/specs/modules/fix_972_974_975_tooling.md
    referenzieren noch "0013-node-test-frontend-unit-runner.md".
    """
    old_filename_hits = _find_adr_mentions("0013-node-test-frontend-unit-runner.md")
    assert not old_filename_hits, (
        f"Alter Dateiname 0013-node-test-frontend-unit-runner.md noch referenziert: "
        f"{old_filename_hits}"
    )

    hits = _find_adr_mentions("ADR-0013")
    assert hits, "Erwartet mindestens die bekannten Alert-Threshold-Referenzen auf ADR-0013"

    node_test_markers = ("node:test", "vitest", "node-test")
    threshold_markers = ("threshold", "Threshold", "Sensitivit", "Δ", "delta")

    offending = [
        (f, line)
        for f, line in hits
        if any(m in line for m in node_test_markers)
        and not any(m in line for m in threshold_markers)
    ]
    assert not offending, (
        "ADR-0013 wird noch im node:test-Kontext referenziert (sollte ADR-0020 sein): "
        f"{offending}"
    )
