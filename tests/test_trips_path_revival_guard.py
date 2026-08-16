# doc-compliance-test
"""Waechter gegen die Wiederkehr der toten Trip-Ablage (#1708, Scheibe A).

Werkzeug-Klasse (CLAUDE.md-Ausnahme ``# doc-compliance-test``): dieser
Laeufer liest Go- und Python-Produktivquellen als DATEN (String-Literale),
nicht als Verhaltensnachweis auf Code-Strings im herkoemmlichen Sinn.

Spec: ``docs/specs/modules/fix_1708_a_trips_pfad_waechter.md``.

Seit dem Cutover (ADR-0023) leben Trips ausschliesslich in
``data/users/<uid>/briefings/<id>.json``. Der Pfad
``data/users/<uid>/trips/<id>.json`` ist tot -- aber er sieht vollstaendig
und plausibel aus und hat nachweislich vier Fehlaussagen und zwei
Datenaenderungen ins Leere verursacht (siehe Spec "Purpose"). Dieser
Waechter wird rot, sobald Produktivcode den toten Pfad wieder bildet.

## Erkennungsregel

Ein String-Literal ``L`` ist ein Fund, wenn:

    R1:  L == "trips"
    R2:  re.search(r"(?:^|/|\\*/)trips(?:/|$)", L)  UND  ("*" in L oder "users" in L)

Bewusst am LITERAL gebunden, nicht am Ausdruckskontext:
``internal/store/user.go:84`` baut den Pfad NICHT in einem
``filepath.Join`` -- das Literal steht in einem
``[]string{"locations", "trips", "gpx", "weather_snapshots"}``-Slice, der
Join passiert eine Zeile spaeter mit der Schleifenvariablen ``sub``. Eine
Regel "Literal in einem Join, der auch 'users' enthaelt" uebersaehe genau
diese Stelle -- deshalb feuert R1 auf das exakte Literal ``"trips"`` immer,
unabhaengig vom umgebenden Ausdruck.

## Bekannte Umgehungen des Waechters (gehoeren woertlich hierher)

1. **Konstante/Variable** in einer ausgeschlossenen Datei, importiert in
   Produktivcode.
2. **Konkatenation/Formatierung:** ``"tri" + "ps"``,
   ``fmt.Sprintf("tri%s", "ps")``.
3. **Konfiguration/Umgebung:** Verzeichnisname aus ``config.ini`` oder Env.
4. **Go-Rohstrings** (Backticks) werden vom ``"..."``-Regex nicht erfasst.
5. **Go-Blockkommentare** ``/* ... */`` werden nicht abgeschnitten --
   Falsch-Positiv-Richtung, harmlos.
6. **Schema-Umbenennung:** ein wiederbelebter Altpfad namens ``trip_files/``
   faellt per Bauart durch.
7. **Neuer Top-Level-Baum** ausserhalb ``internal/``, ``cmd/``, ``src/``,
   ``api/``.

Keine davon ist versehentlich erreichbar -- alle erfordern bewusste Arbeit.
Der reale Rueckfall (jemand fuegt ``"trips"`` wieder in die
``ProvisionUserDirs``-Liste ein) wird getroffen.

## Weitere Grenzen

Der Python-Prozess bemerkt NICHT, wenn eine Go-Datei syntaktisch kaputt
ist -- er sieht nur Text. Abgefangen wird das durch die
Scanflaechen-Untergrenze und den Traegernachweis (AC-6), nicht durch einen
Parser.

Test-Politik: Kernschicht, keine Mocks. Pfadregel #1409: Pruefling relativ
zu DIESER Testdatei aufgeloest, nie ueber einen festen Hauptrepo-Pfad --
sonst misst der Test aus einem Worktree den falschen Baum.
"""
from __future__ import annotations

import ast
import re
from pathlib import Path

import pytest

# Pfadregel #1409: Repo-Wurzel relativ zu DIESER Testdatei, nie fest verdrahtet.
REPO_ROOT = Path(__file__).resolve().parents[1]

GO_ROOTS = ["internal", "cmd"]
PY_ROOTS = ["src", "api"]

MIN_GO_FILES = 80
MIN_PY_FILES = 180

CARRIER_FILES = {
    "internal/store/user.go",
    "internal/store/trip.go",
    "src/app/loader.py",
}

# Restliste, Schluesselform "pfad::symbol::ordinal" (Hausnorm,
# tests/test_guard_findings_survive_line_shifts.py:52). Genau EIN Eintrag --
# kein Inline-Ausnahmeventil, jede Ausnahme muss hier stehen, sonst waere sie
# in der Taeterdatei fuer einen Reviewer unsichtbar mitzuschmuggeln.
KNOWN_VIOLATIONS: dict[str, str] = {
    "src/app/loader.py::get_trips_dir::0": (
        "UEBERGANG #1708 Scheibe B -- 12 Testdateien rufen sie; entfaellt mit "
        "deren Umstellung auf get_briefings_dir(). KEINE Dauerausnahme."
    ),
}

_TRIPS_SEGMENT_RE = re.compile(r"(?:^|/|\*/)trips(?:/|$)")
_GO_STRING_LITERAL_RE = re.compile(r'"([^"]*)"')
_GO_FUNC_DECL_RE = re.compile(r"^func\s+(?:\([^)]*\)\s+)?(\w+)\s*\(")


def _is_finding(literal: str) -> bool:
    """R1/R2 aus der Spec. Bindet am Literal, nicht am Ausdruckskontext."""
    if literal == "trips":
        return True
    if _TRIPS_SEGMENT_RE.search(literal) and ("*" in literal or "users" in literal):
        return True
    return False


def _scan_go_text(text: str) -> list[tuple[str, str, int]]:
    """Liest Go-Quelltext zeilenweise. Gibt (symbol, literal, zeile) je Fund.

    Zeile wird am ERSTEN ``//`` abgeschnitten (Vorbild:
    tests/test_egress_inventory_drift.py:_parse_go_inventory) -- eine voll
    auskommentierte Zeile zaehlt damit nicht, ein Inline-Kommentar hinter
    echtem Code schon (AC-5).
    """
    results: list[tuple[str, str, int]] = []
    current_symbol = "<module>"
    for line_no, raw_line in enumerate(text.splitlines(), start=1):
        code = raw_line.split("//", 1)[0]
        m = _GO_FUNC_DECL_RE.match(code.strip())
        if m:
            current_symbol = m.group(1)
        for literal in _GO_STRING_LITERAL_RE.findall(code):
            if _is_finding(literal):
                results.append((current_symbol, literal, line_no))
    return results


class _PySymbolScanner(ast.NodeVisitor):
    """Traegt den umschliessenden Funktions-/Methodennamen waehrend des
    Walks mit -- ``ast.walk`` allein kennt keine Elternbeziehung."""

    def __init__(self) -> None:
        self.stack: list[str] = ["<module>"]
        self.results: list[tuple[str, str, int]] = []

    def _visit_scope(self, node: ast.AST, name: str) -> None:
        self.stack.append(name)
        self.generic_visit(node)
        self.stack.pop()

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        self._visit_scope(node, node.name)

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
        self._visit_scope(node, node.name)

    def visit_ClassDef(self, node: ast.ClassDef) -> None:
        self._visit_scope(node, node.name)

    def _check(self, literal: str, lineno: int) -> None:
        if _is_finding(literal):
            self.results.append((self.stack[-1], literal, lineno))

    def visit_Constant(self, node: ast.Constant) -> None:
        if isinstance(node.value, str):
            self._check(node.value, node.lineno)
        self.generic_visit(node)

    def visit_JoinedStr(self, node: ast.JoinedStr) -> None:
        for part in node.values:
            if isinstance(part, ast.Constant) and isinstance(part.value, str):
                self._check(part.value, node.lineno)
        self.generic_visit(node)


def _scan_python_text(text: str) -> list[tuple[str, str, int]]:
    tree = ast.parse(text)
    scanner = _PySymbolScanner()
    scanner.visit(tree)
    return scanner.results


def _go_scan_files() -> list[Path]:
    """Scanflaeche PER RGLOB BERECHNET, nie als abgeschriebene Dateiliste."""
    files: list[Path] = []
    for root_name in GO_ROOTS:
        root = REPO_ROOT / root_name
        if not root.exists():
            continue
        for p in root.rglob("*.go"):
            if p.name.endswith("_test.go"):
                continue
            files.append(p)
    return sorted(files)


def _py_scan_files() -> list[Path]:
    files: list[Path] = []
    for root_name in PY_ROOTS:
        root = REPO_ROOT / root_name
        if not root.exists():
            continue
        files.extend(sorted(root.rglob("*.py")))
    return sorted(files)


def _numbered_findings(
    raw: list[tuple[str, str, int]], rel_path: str
) -> dict[str, tuple[str, int]]:
    """Gruppiert nach Symbol, ordnet nach Zeile, vergibt Ordinal 0..n-1
    (Hausnorm: tests/test_output_timezone_guard.py Muster
    ``for ordinal, lineno in enumerate(sorted(by_line))``)."""
    by_symbol: dict[str, list[tuple[int, str]]] = {}
    for symbol, literal, line in raw:
        by_symbol.setdefault(symbol, []).append((line, literal))
    numbered: dict[str, tuple[str, int]] = {}
    for symbol, entries in by_symbol.items():
        for ordinal, (line, literal) in enumerate(sorted(entries, key=lambda e: e[0])):
            key = f"{rel_path}::{symbol}::{ordinal}"
            numbered[key] = (literal, line)
    return numbered


def _all_go_findings() -> dict[str, tuple[str, int]]:
    findings: dict[str, tuple[str, int]] = {}
    for path in _go_scan_files():
        rel = str(path.relative_to(REPO_ROOT))
        raw = _scan_go_text(path.read_text(encoding="utf-8"))
        findings.update(_numbered_findings(raw, rel))
    return findings


def _all_python_findings() -> dict[str, tuple[str, int]]:
    findings: dict[str, tuple[str, int]] = {}
    for path in _py_scan_files():
        rel = str(path.relative_to(REPO_ROOT))
        raw = _scan_python_text(path.read_text(encoding="utf-8"))
        findings.update(_numbered_findings(raw, rel))
    return findings


def _all_violations() -> dict[str, tuple[str, int]]:
    findings = _all_go_findings()
    findings.update(_all_python_findings())
    return findings


# ---------------------------------------------------------------------------
# AC-1/AC-2: Go-Erkenner gegen synthetische Quellen (nicht gegen echte
# Dateien -- sonst meldet der Waechter sich selbst).
# ---------------------------------------------------------------------------


def test_ac1_slice_literal_form_detected():
    """AC-1: Slice-Form ``[]string{"locations", "trips", "gpx"}`` -> genau
    ein Fund mit dem umschliessenden Symbol. Dies ist die Form, die die
    Falle real neu herstellt (internal/store/user.go:84) -- bliebe sie
    unerkannt, waere der ganze Waechter wirkungslos."""
    src = (
        "package store\n\n"
        'func (s *Store) ProvisionUserDirs(id string) error {\n'
        "\tbase := s.UserDir(id)\n"
        '\tfor _, sub := range []string{"locations", "trips", "gpx", "weather_snapshots"} {\n'
        "\t\tif err := os.MkdirAll(filepath.Join(base, sub), 0755); err != nil {\n"
        "\t\t\treturn err\n"
        "\t\t}\n"
        "\t}\n"
        "\treturn nil\n"
        "}\n"
    )
    raw = _scan_go_text(src)
    assert len(raw) == 1, f"Erwartet genau 1 Fund, bekommen: {raw}"
    symbol, literal, _line = raw[0]
    assert symbol == "ProvisionUserDirs"
    assert literal == "trips"


def test_ac2_filepath_join_form_detected():
    """AC-2: ``filepath.Join(s.DataDir, "users", s.UserID, "trips")`` ->
    genau ein Fund (das Literal "users" allein loest R2 NICHT aus)."""
    src = (
        "package store\n\n"
        "func (s *Store) TripsDir() string {\n"
        '\treturn filepath.Join(s.DataDir, "users", s.UserID, "trips")\n'
        "}\n"
    )
    raw = _scan_go_text(src)
    assert len(raw) == 1, f"Erwartet genau 1 Fund, bekommen: {raw}"
    symbol, literal, _line = raw[0]
    assert symbol == "TripsDir"
    assert literal == "trips"


# ---------------------------------------------------------------------------
# AC-3: Python-Erkenner per AST gegen synthetische Quellen.
# ---------------------------------------------------------------------------


def test_ac3_python_division_form_detected():
    """AC-3a: ``get_data_dir(uid) / "trips"`` -> genau ein Fund."""
    src = (
        "def get_trips_dir(user_id='default'):\n"
        '    return get_data_dir(user_id) / "trips"\n'
    )
    raw = _scan_python_text(src)
    assert len(raw) == 1, f"Erwartet genau 1 Fund, bekommen: {raw}"
    symbol, literal, _line = raw[0]
    assert symbol == "get_trips_dir"
    assert literal == "trips"


def test_ac3_python_glob_form_detected():
    """AC-3b: ``root.glob("*/trips/*.json")`` -> genau ein Fund (das
    Literal traegt kein exaktes "trips", sondern greift ueber R2 + "*")."""
    src = (
        "def cleanup(root):\n"
        '    for f in root.glob("*/trips/*.json"):\n'
        "        pass\n"
    )
    raw = _scan_python_text(src)
    assert len(raw) == 1, f"Erwartet genau 1 Fund, bekommen: {raw}"
    symbol, literal, _line = raw[0]
    assert symbol == "cleanup"
    assert literal == "*/trips/*.json"


# ---------------------------------------------------------------------------
# AC-4: reale Bestandsformen duerfen NICHT als Fund erkannt werden.
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "literal",
    [
        "/api/trips/{id}",
        "https://gregor20.henemm.com/trips/",
        "corrupt_trips.json",
        "briefings",
    ],
)
def test_ac4_real_bestand_forms_are_not_findings(literal):
    """AC-4: reale Bestandsformen (Routen-String, absolute URL,
    ``corrupt_trips.json``, ``briefings``) -> null Funde je Form. Verhindert,
    dass der Waechter beim ersten Falsch-Positiv per Ausnahme entschaerft
    wird."""
    assert not _is_finding(literal), (
        f"{literal!r} wurde faelschlich als Fund erkannt -- Erkenner zu weit gefasst."
    )


# ---------------------------------------------------------------------------
# AC-5: Kommentar-Abschnitt wirkt, ohne echten Code zu verschlucken.
# ---------------------------------------------------------------------------


def test_ac5_full_comment_line_is_not_a_finding():
    """AC-5a: eine Zeile, die vollstaendig aus dem Kommentar
    ``// filepath.Join(dir, "trips")`` besteht -> null Funde."""
    src = '\t// filepath.Join(dir, "trips")\n'
    raw = _scan_go_text(src)
    assert raw == [], f"Auskommentierte Zeile faelschlich als Fund gemeldet: {raw}"


def test_ac5_code_with_trailing_comment_is_a_finding():
    """AC-5b: dieselbe Zeilenform, aber mit echtem Code VOR dem Kommentar
    -> genau ein Fund. Belegt, dass der Kommentar-Abschnitt nur den
    Kommentaranteil abschneidet, nicht die ganze Zeile verschluckt."""
    src = 'x := filepath.Join(dir, "trips") // legacy path, siehe #1708\n'
    raw = _scan_go_text(src)
    assert len(raw) == 1, f"Erwartet 1 Fund trotz Trailing-Kommentar, bekommen: {raw}"


# ---------------------------------------------------------------------------
# AC-6: Scanflaechen-Untergrenzen und Traegernachweis.
# ---------------------------------------------------------------------------


def test_ac6_go_scan_area_minimum_file_count():
    files = _go_scan_files()
    assert len(files) >= MIN_GO_FILES, (
        f"Nur {len(files)} Go-Produktivdateien unter {GO_ROOTS} gefunden "
        f"(< {MIN_GO_FILES}) -- die Scanflaeche ist vermutlich falsch "
        "berechnet (z.B. falscher Wurzelpfad)."
    )


def test_ac6_python_scan_area_minimum_file_count():
    files = _py_scan_files()
    assert len(files) >= MIN_PY_FILES, (
        f"Nur {len(files)} Python-Produktivdateien unter {PY_ROOTS} gefunden "
        f"(< {MIN_PY_FILES}) -- die Scanflaeche ist vermutlich falsch "
        "berechnet (z.B. falscher Wurzelpfad)."
    )


def test_ac6_carrier_files_are_within_scan_area():
    """Eine reine Zaehlung faengt keinen Pfad-Tippfehler, der nur einen
    Teilbaum verliert -- deshalb zusaetzlich der namentliche Traegernachweis."""
    scanned = {str(p.relative_to(REPO_ROOT)) for p in _go_scan_files()} | {
        str(p.relative_to(REPO_ROOT)) for p in _py_scan_files()
    }
    missing = sorted(c for c in CARRIER_FILES if c not in scanned)
    assert not missing, (
        f"Traeger-Dateien fehlen in der berechneten Scanflaeche: {missing} "
        "-- ein Pfad-Tippfehler haette diese Dateien lautlos aus dem Scan "
        "genommen."
    )


# ---------------------------------------------------------------------------
# AC-7: Restliste darf nur schrumpfen, harte Obergrenze verhindert Wachstum.
# ---------------------------------------------------------------------------


def test_ac7_known_violations_only_shrink():
    """Ein Eintrag, dessen Fundstelle der Scanner nicht mehr findet
    (behoben oder verschoben), muss aus KNOWN_VIOLATIONS entfernt werden --
    sonst bliebe die Liste eine Dauereinrichtung statt Fortschrittsnachweis."""
    found = _all_violations()
    stale = sorted(k for k in KNOWN_VIOLATIONS if k not in found)
    assert not stale, (
        "Diese Ausnahmen sind veraltet (der Scanner meldet die Stelle nicht "
        f"mehr): {stale} -- aus KNOWN_VIOLATIONS entfernen (die Liste darf "
        "nur schrumpfen)."
    )


def test_ac7_known_violations_hard_upper_bound():
    """Ohne diese Obergrenze koennte jeder kuenftige Fund mit zwei Zeilen
    stillgelegt werden -- der Weg, auf dem Waechter im Feld sterben."""
    assert len(KNOWN_VIOLATIONS) <= 1, (
        f"KNOWN_VIOLATIONS hat {len(KNOWN_VIOLATIONS)} Eintraege (> 1) -- "
        "eine wachsende Ausnahmeliste ist die Hintertuer des Waechters."
    )


# ---------------------------------------------------------------------------
# AC-8: tests/ und scripts/ liegen ausserhalb der Scanflaeche.
# ---------------------------------------------------------------------------


def test_ac8_scan_area_excludes_tests_and_scripts():
    """Schuetzt tests/test_briefing_route_cutover.py (Lockvogel-Datei fuer
    den Cutover-Beweis) und die Migrations-Skripte, deren Aufgabe der
    Altpfad ist -- deren legitime 'trips'-Vorkommen duerfen nicht gemeldet
    werden."""
    all_files = _go_scan_files() + _py_scan_files()
    offenders = [p for p in all_files if "tests" in p.parts or "scripts" in p.parts]
    assert not offenders, (
        f"Scanflaeche enthaelt ausgeschlossene Verzeichnisse: {offenders}"
    )


# ---------------------------------------------------------------------------
# Der Hauptwaechter.
# ---------------------------------------------------------------------------


def test_keine_unlisted_trips_pfad_funde():
    """GIVEN der Quelltextbestand unter internal/, cmd/, src/, api/
    WHEN ein String-Literal-Fund NICHT in KNOWN_VIOLATIONS steht
    THEN ist das ein neuer/bestehender toter 'trips'-Pfad in Produktivcode
    (#1708) -- der Test benennt Datei, Symbol und Fundtext.

    Erwartung in der TDD-RED-Phase: ROT, benennt
    internal/store/trip.go:15 (TripsDir) und internal/store/user.go:84
    (ProvisionUserDirs). src/app/loader.py:1163 (get_trips_dir) ist ueber
    KNOWN_VIOLATIONS gedeckt und erscheint NICHT in der Fehlermeldung.
    """
    found = _all_violations()
    unlisted = {k: v for k, v in found.items() if k not in KNOWN_VIOLATIONS}
    assert not unlisted, (
        "Toter 'trips'-Pfad in Produktivcode gefunden (#1708) -- ADR-0023 "
        "legt briefings/<id>.json als einzige Persistenz-Wahrheit fest. "
        "Fundstellen (pfad::symbol::ordinal -> (literal, zeile)): "
        f"{sorted(unlisted.items())}"
    )
