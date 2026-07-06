"""TDD RED — Issue #1046: Compare-Mail-Validator, veralteter 2-Tabellen-Vertrag.

Beweist Verhalten (kein Mock, keine Dateiinhalt-Checks) direkt gegen die
reinen Parsing-/Prüf-Funktionen aus `.claude/hooks/email_spec_validator.py`,
mit synthetischen HTML-Fixtures, die exakt die reale Struktur seit #460
nachbilden (2 Header-Stats-Tabellen + 1 Vergleichsmatrix + N Stunden-
Tabellen).

AC-6 (Gate-Nachweis gegen eine echte, frisch zugestellte Staging-Mail) ist
hier bewusst NICHT als pytest-Test enthalten — analog zum #997-Präzedenz
(`docs/specs/modules/fix_997_validator_bundle.md`, dortiges AC-5) wird der
End-to-End-Nachweis erst nach Deploy im Post-Push-Workflow gegen die echte
IMAP-Mail erbracht (siehe Spec `docs/specs/modules/
issue_1046_email_validator_table_contract.md`).
"""
from __future__ import annotations

import importlib.util
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
VALIDATOR_PATH = REPO_ROOT / ".claude" / "hooks" / "email_spec_validator.py"


def _load_validator():
    """Lade den Validator als isoliertes Modul (vermeidet sys.modules-Kontamination)."""
    spec = importlib.util.spec_from_file_location("esv1046", str(VALIDATOR_PATH))
    if spec is None or spec.loader is None:
        raise ImportError(f"Validator nicht ladbar: {VALIDATOR_PATH}")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


# --------------------------------------------------------------------------- #
# HTML-Fixture-Builder (echte Struktur wie render_compare_html(), kein Mock)
# --------------------------------------------------------------------------- #

_HEADER_GRID_ROW = "<tr><th>Profil</th><th>Orte</th><th>Horizont</th><th>Erstellt</th></tr>"

# Header-Zeile + 7 Metrik-Zeilen = 8 Zeilen, wie von validate_structure()
# erwartet (expected_labels). Locations mit #N-Praefix, wie extract_locations()
# ihn abstreift.
_MATRIX_ROWS = (
    "<tr><th>Metric</th><th>#1 LocationA</th><th>#2 LocationB</th><th>#3 LocationC</th></tr>"
    "<tr><td>Score</td><td>71</td><td>68</td><td>75</td></tr>"
    "<tr><td>Snow Depth</td><td>-</td><td>-</td><td>-</td></tr>"
    "<tr><td>New Snow</td><td>-</td><td>-</td><td>-</td></tr>"
    "<tr><td>Wind/Gusts</td><td>10/25 SW</td><td>12/30 NW</td><td>8/20 N</td></tr>"
    "<tr><td>Temperature (felt)</td><td>18</td><td>16</td><td>20</td></tr>"
    "<tr><td>Sunny Hours</td><td>~5h</td><td>0h</td><td>~3h</td></tr>"
    "<tr><td>Cloud Cover</td><td>42%</td><td>60%*</td><td>30%</td></tr>"
)

_REQUIRED_SECTION_MARKERS = "<div>Time Window</div><div>Hourly Overview</div><div>Recommendation</div>"


def _table(class_attr: "str | None", inner_html: str) -> str:
    cls = f' class="{class_attr}"' if class_attr else ""
    return f'<table{cls} cellspacing="0" cellpadding="0">{inner_html}</table>'


def _hourly_table(i: int) -> str:
    return _table(None, f"<tr><td>{i:02d}:00</td><td>12°</td><td>10</td><td>20%</td></tr>")


def _build_body(
    *,
    header_desktop: bool = True,
    header_mobile: bool = True,
    matrix: bool = True,
    hourly_count: int = 3,
    extra_unknown_table: bool = False,
) -> str:
    """Reale Compare-Mail-Struktur seit #460 nachgebildet (Klassen, keine
    Positions-Annahme): 2 Header-Stats-Varianten + 1 Matrix + N Stunden-
    Tabellen."""
    parts: list[str] = []
    if header_desktop:
        parts.append(_table("header-stats-desktop", _HEADER_GRID_ROW))
    if header_mobile:
        parts.append(_table("header-stats-mobile", _HEADER_GRID_ROW))
    if matrix:
        parts.append(_table("matrix-table", _MATRIX_ROWS))
    for i in range(hourly_count):
        parts.append(_hourly_table(i + 9))
    if extra_unknown_table:
        parts.append(_table("foo-table", "<tr><td>x</td></tr>"))
    parts.append(_REQUIRED_SECTION_MARKERS)
    return "".join(parts)


# --------------------------------------------------------------------------- #
# AC-1 — reale 6-Tabellen-Struktur (top_n_details=3) -> 0 Strukturfehler
# --------------------------------------------------------------------------- #

def test_ac1_real_six_table_structure_yields_no_structure_errors():
    mod = _load_validator()
    body = _build_body(hourly_count=3)

    errors = mod.validate_structure(body)

    assert errors == [], f"Erwartet: keine Strukturfehler, bekommen: {errors}"


# --------------------------------------------------------------------------- #
# AC-2 — top_n_details=0 (keine Stunden-Tabellen) -> weiterhin 0 Fehler
# --------------------------------------------------------------------------- #

def test_ac2_zero_hourly_tables_still_yields_no_structure_errors():
    mod = _load_validator()
    body = _build_body(hourly_count=0)

    errors = mod.validate_structure(body)

    assert errors == [], (
        f"Erwartet: keine Strukturfehler auch ohne Stunden-Tabellen "
        f"(top_n_details=0), bekommen: {errors}"
    )


# --------------------------------------------------------------------------- #
# AC-3 — fehlende matrix-table-Klasse MUSS erkannt werden (Nicht-Aufweichung)
# --------------------------------------------------------------------------- #

def test_ac3_missing_matrix_table_is_reported_as_error():
    mod = _load_validator()
    body = _build_body(matrix=False, hourly_count=3)

    errors = mod.validate_structure(body)

    assert errors, "Erwartet: Strukturfehler bei fehlender matrix-table-Klasse"
    assert any("matrix-table" in e for e in errors), (
        f"Erwartet: Fehlermeldung referenziert 'matrix-table', bekommen: {errors}"
    )


# --------------------------------------------------------------------------- #
# AC-4 — unbekannte zusaetzliche klassifizierte Tabelle -> Fehler (Anti-Erosion)
# --------------------------------------------------------------------------- #

def test_ac4_unknown_classified_table_is_reported_as_error():
    mod = _load_validator()
    body = _build_body(hourly_count=3, extra_unknown_table=True)

    errors = mod.validate_structure(body)

    assert errors, "Erwartet: Strukturfehler bei unbekannter zusaetzlicher Tabellen-Klasse"
    assert any("foo-table" in e for e in errors), (
        f"Erwartet: Fehlermeldung nennt die unbekannte Klasse 'foo-table', bekommen: {errors}"
    )


# --------------------------------------------------------------------------- #
# AC-5 — Kronbeweis: Zeilen/Locations stammen aus der Matrix, nicht dem Grid
# --------------------------------------------------------------------------- #

def test_ac5_extracted_locations_come_from_matrix_not_header_grid():
    mod = _load_validator()
    body = _build_body(hourly_count=3)

    locations = mod.extract_locations(body)

    assert locations == ["LocationA", "LocationB", "LocationC"], (
        f"Erwartet: Locations aus der matrix-table-Tabelle, bekommen: {locations}"
    )
    # Kein Bestandteil darf aus dem Header-Grid stammen.
    header_grid_cells = {"Orte", "Horizont", "Erstellt"}
    assert not header_grid_cells.intersection(locations), (
        f"Locations enthalten Header-Grid-Zellen statt Matrix-Inhalt: {locations}"
    )


def test_ac5_extracted_rows_come_from_matrix_not_header_grid():
    mod = _load_validator()
    body = _build_body(hourly_count=3)

    rows = mod.extract_table_rows(body)

    assert rows, "Erwartet: nicht-leere Zeilenliste aus der Matrix-Tabelle"
    assert rows[0][0] == "Metric", (
        f"Erwartet: erste Zeile/Spalte 'Metric' (Matrix-Header), bekommen: {rows[0]}"
    )
    assert len(rows) == 8, f"Erwartet: 8 Zeilen (Matrix), bekommen: {len(rows)}"
