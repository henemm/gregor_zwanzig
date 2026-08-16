"""RED-Nachweise fuer #1708 Scheibe B2 -- toten `trips/`-Pfad aus Testdateien
und Loader entfernen.

Spec: ``docs/specs/modules/fix_1708_b2_trips_pfad_rueckbau.md``.
Context: ``docs/context/fix-1708-b2-trips-pfad-rueckbau.md``.

Seit #1250 Scheibe 7a (ADR-0023) leben Trips ausschliesslich in
``data/users/<uid>/briefings/<id>.json``. ``get_trips_dir()``
(``src/app/loader.py:1155``) ist tot -- kein Produktivaufrufer, aber neun
Testdateien rufen sie noch real auf und wirken dadurch entweder wirkungslos
oder verlieren eine echte Zusicherung an eine Adresse, die nie beschrieben
wird (AC-6).

Fuenf Nachweise, in Wichtigkeitsreihenfolge:

- N1 (AC-3): ``get_trips_dir`` faellt aus ``src/app/loader.py``.
- N2 (AC-4): die eine Waechter-Ausnahme dafuer wird leer.
- N3 (AC-1): keine Testdatei ruft die Funktion mehr echt auf (AST, nicht
  Textvergleich -- eine Nennung in Kommentar/Docstring/String ist kein
  Aufruf).
- N4 (AC-5): der wichtigste und schwierigste Nachweis. Mit blindem Scanner
  (``_py_scan_files``/``_go_scan_files`` liefern ``[]``) UND leerer
  ``KNOWN_VIOLATIONS`` muss mindestens einer der inhaltlichen
  Waechter-Tests rot werden -- sonst misst kein Test mehr, ob der Scanner
  auf echten Dateien ueberhaupt etwas findet (R1 im Kontextdokument). Die
  drei AC-6/AC-8-Scanflaechen-Sanity-Tests sind ausdruecklich NICHT Teil
  dieses Nachweises -- sie schuetzen eine andere Eigenschaft (Dateizahl,
  Traeger-Mitgliedschaft), nicht die Fund-Erkennung selbst.
- N5 (AC-6): die Cross-User-Zusicherung in
  ``tests/tdd/test_issue_731_unified_commands.py::TestAC10UserIsolation
  .test_weiter_only_affects_own_trip`` zielt heute auf den toten
  ``trips/``-Pfad und kann dort nie fehlschlagen.

Test-Politik: Kernschicht, keine Mocks -- ``monkeypatch`` auf echte
Modul-Globals biegt echten Code um, ersetzt ihn nicht. Pfadregel #1409:
Pruefling relativ zu DIESER Testdatei aufgeloest, nie ueber einen festen
Hauptrepo-Pfad.
"""
from __future__ import annotations

import ast
import importlib.util
import inspect
import sys
from pathlib import Path

# Pfadregel #1409: Repo-Wurzel relativ zu DIESER Testdatei.
_TESTS_DIR = Path(__file__).resolve().parent
_REPO_ROOT = _TESTS_DIR.parent


def _load_guard():
    """Den Waechter als eigenstaendiges Modul laden -- ueber seinen
    Dateipfad (Hausnorm: tests/test_guard_findings_survive_line_shifts.py),
    damit ein Worktree-Lauf zwingend die Worktree-Fassung misst."""
    path = _TESTS_DIR / "test_trips_path_revival_guard.py"
    assert path.exists(), f"Waechter-Datei fehlt: {path}"
    spec = importlib.util.spec_from_file_location(
        "gz_guard_trips_path_revival_b2", path
    )
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


# ---------------------------------------------------------------------------
# N1 (AC-3): get_trips_dir() faellt aus src/app/loader.py
# ---------------------------------------------------------------------------


def test_get_trips_dir_removed_from_loader():
    from app import loader

    assert not hasattr(loader, "get_trips_dir"), (
        "src.app.loader.get_trips_dir existiert noch -- AC-3 verlangt die "
        "vollstaendige Entfernung. Code reference: src/app/loader.py:1155-1163"
    )


# ---------------------------------------------------------------------------
# N2 (AC-4): die eine Waechter-Ausnahme wird leer, im selben Commit
# ---------------------------------------------------------------------------


def test_known_violations_guard_exception_emptied():
    guard = _load_guard()
    assert guard.KNOWN_VIOLATIONS == {}, (
        f"KNOWN_VIOLATIONS ist nicht leer: {guard.KNOWN_VIOLATIONS} -- der "
        "Eintrag fuer get_trips_dir muss im selben Commit wie die Funktion "
        "selbst fallen (AC-4). Code reference: "
        "tests/test_trips_path_revival_guard.py:90-95"
    )


# ---------------------------------------------------------------------------
# N3 (AC-1): keine Testdatei ruft get_trips_dir() noch echt auf
# ---------------------------------------------------------------------------


def _real_calls_to(tree: ast.AST, target_name: str) -> list[ast.Call]:
    """Echte ``ast.Call``-Aufrufe einer Funktion mit gegebenem Namen --
    unterscheidet einen Aufruf von einer blossen Namensnennung in
    Kommentar/Docstring/String (dort erscheint der Name gar nicht im Baum
    als Call, sondern hoechstens als ``ast.Constant``)."""
    calls: list[ast.Call] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        name = None
        if isinstance(func, ast.Name):
            name = func.id
        elif isinstance(func, ast.Attribute):
            name = func.attr
        if name == target_name:
            calls.append(node)
    return calls


def test_no_test_file_still_calls_get_trips_dir():
    """N3/AC-1: ueber alle .py-Dateien unter tests/ -- eine echte AST-Pruefung,
    kein Textvergleich (verboten waere z.B. ``assert 'get_trips_dir' not in
    text``, das traefe auch Kommentare/Docstrings, die AC-7 bewusst als
    Altbestands-Hinweis stehen laesst)."""
    offenders: dict[str, int] = {}
    for path in sorted(_TESTS_DIR.rglob("*.py")):
        text = path.read_text(encoding="utf-8")
        tree = ast.parse(text, filename=str(path))
        calls = _real_calls_to(tree, "get_trips_dir")
        if calls:
            offenders[str(path.relative_to(_REPO_ROOT))] = len(calls)

    assert not offenders, (
        "Echte Aufrufe von get_trips_dir() in "
        f"{len(offenders)} Testdatei(en) (AC-1 verlangt: keine mehr nach der "
        f"Umstellung auf get_briefings_dir()): {sorted(offenders.items())}"
    )


# ---------------------------------------------------------------------------
# N4 (AC-5): blinder Scanner MUSS die Waechter-Suite roet machen
# ---------------------------------------------------------------------------

# Diese Waechter-Tests pruefen den Scanner ausschliesslich gegen
# SYNTHETISCHE Quellstrings (AC-1..AC-5 des Waechters) oder gegen die
# Scanflaeche selbst (Dateizahl/Traeger-Mitgliedschaft, AC-6/AC-8) -- sie
# haengen nicht an KNOWN_VIOLATIONS/_all_violations() und wuerden mit
# blindem Scanner aus einem ANDEREN Grund rot (AC-6 zaehlt z.B. direkt
# len(_go_scan_files())) bzw. gar nicht betroffen sein. Sie gehoeren nicht
# zum Trefferkraft-Nachweis dieses Tickets und werden bewusst ausgeschlossen,
# damit die Ausschlussliste selbst kein Verhalten faelscht.
_GUARD_TESTS_UNRELATED_TO_TREFFERKRAFT = frozenset(
    {
        "test_ac1_slice_literal_form_detected",
        "test_ac2_filepath_join_form_detected",
        "test_ac3_python_division_form_detected",
        "test_ac3_python_glob_form_detected",
        "test_ac4_real_bestand_forms_are_not_findings",
        "test_ac5_full_comment_line_is_not_a_finding",
        "test_ac5_code_with_trailing_comment_is_a_finding",
        "test_ac6_go_scan_area_minimum_file_count",
        "test_ac6_python_scan_area_minimum_file_count",
        "test_ac6_carrier_files_are_within_scan_area",
        "test_ac8_scan_area_excludes_tests_and_scripts",
    }
)


def _call_with_supported_fixtures(func, *, tmp_path, monkeypatch) -> None:
    """Ruft eine Waechter-Testfunktion mit genau den Fixtures auf, die sie
    per Signatur verlangt -- unterstuetzt werden nur ``tmp_path`` und
    ``monkeypatch`` (die einzigen, die der kuenftige Trefferkraft-Test laut
    Kontextdokument braucht)."""
    sig = inspect.signature(func)
    kwargs = {}
    for name in sig.parameters:
        if name == "tmp_path":
            kwargs["tmp_path"] = tmp_path
        elif name == "monkeypatch":
            kwargs["monkeypatch"] = monkeypatch
        else:
            raise TypeError(
                f"{func.__name__} braucht die nicht unterstuetzte Fixture "
                f"{name!r} -- Nachweis kann diese Funktion nicht generisch "
                "aufrufen."
            )
    func(**kwargs)


def test_blinded_scanner_must_fail_the_guard_suite(monkeypatch, tmp_path):
    """N4/AC-5: GIVEN der Scanner ist blind gemacht (_py_scan_files/
    _go_scan_files liefern []) UND KNOWN_VIOLATIONS ist leer (der Zielzustand
    von N2) / WHEN die inhaltlichen Waechter-Tests (test_keine_unlisted_
    trips_pfad_funde, test_ac7_known_violations_*) laufen / THEN muss
    mindestens einer davon rot werden -- ein Scanner, der auf echten Dateien
    lautlos nichts mehr liefert, darf nicht unbemerkt bleiben (R1).

    HEUTE ist dieser Nachweis rot aus dem richtigen Grund: keiner der drei
    heutigen Kandidaten haengt an den Datei-Sammelfunktionen in einer Weise,
    die bei leerer KNOWN_VIOLATIONS auffiele -- ``found = {}``,
    ``KNOWN_VIOLATIONS = {}``, beide Pruefungen sind dann trivial erfuellt.
    Erst der kuenftige Trefferkraft-Test (legt echte Verstoss-Dateien in
    tmp_path an, biegt REPO_ROOT per monkeypatch um) haengt zusaetzlich an
    _all_violations() -> _py_scan_files()/_go_scan_files() und wird bei
    Blindheit rot, weil er echte Funde erwartet, aber keine bekommt. Die
    Kandidatenliste wird dynamisch aus dem Waechter-Modul gelesen (nicht
    hier abgeschrieben), damit dieser Nachweis den kuenftigen Test
    automatisch mit erfasst.
    """
    guard = _load_guard()
    monkeypatch.setattr(guard, "KNOWN_VIOLATIONS", {})
    monkeypatch.setattr(guard, "_py_scan_files", lambda: [])
    monkeypatch.setattr(guard, "_go_scan_files", lambda: [])

    candidates = [
        (name, obj)
        for name, obj in sorted(vars(guard).items())
        if name.startswith("test_")
        and name not in _GUARD_TESTS_UNRELATED_TO_TREFFERKRAFT
        and callable(obj)
        and getattr(obj, "pytestmark", None) is None
    ]
    assert candidates, (
        "Kein einziger Waechter-Test wurde als Trefferkraft-Kandidat erkannt "
        "-- Namensmuster oder Ausschlussliste in diesem Nachweis pruefen."
    )

    failures = []
    for name, func in candidates:
        try:
            _call_with_supported_fixtures(
                func, tmp_path=tmp_path, monkeypatch=monkeypatch
            )
        except AssertionError:
            failures.append(name)

    assert failures, (
        "Mit blindem Scanner (_py_scan_files/_go_scan_files liefern []) UND "
        f"leerer KNOWN_VIOLATIONS bleiben ALLE Kandidaten gruen: "
        f"{[n for n, _ in candidates]} -- kein Test misst mehr, ob der "
        "Scanner auf echten Dateien ueberhaupt etwas findet (Kontextdokument "
        "R1). Nach B2 muss der neue Trefferkraft-Nachweis (AC-5) hier "
        "auffallen und diese Assertion gruen machen."
    )


# ---------------------------------------------------------------------------
# N5 (AC-6): Cross-User-Zusicherung zielt heute auf den toten Pfad
# ---------------------------------------------------------------------------


def _function_calls(tree: ast.AST, class_name: str, func_name: str) -> set[str]:
    """Namen aller ``ast.Call``-Aufrufe INNERHALB einer bestimmten Methode
    einer Klasse -- Aufrufe in anderen Funktionen (auch Helfern, die diese
    Methode selbst aufruft) zaehlen nicht mit, nur der direkte Methodenkoerper."""
    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef) and node.name == class_name:
            for item in node.body:
                if isinstance(item, ast.FunctionDef) and item.name == func_name:
                    return {
                        c.func.id if isinstance(c.func, ast.Name) else c.func.attr
                        for c in ast.walk(item)
                        if isinstance(c, ast.Call)
                        and isinstance(c.func, (ast.Name, ast.Attribute))
                    }
    raise AssertionError(f"{class_name}.{func_name} nicht gefunden in {tree!r}")


def test_cross_user_assertion_targets_live_briefings_path():
    """N5/AC-6: GIVEN TestAC10UserIsolation.test_weiter_only_affects_own_trip
    prueft, dass ein WEITER von Nutzer A nichts unter users/default/
    hinterlaesst / WHEN die Pruefstelle inspiziert wird / THEN muss sie den
    LEBENDEN Pfad (get_briefings_dir) ansprechen -- am toten get_trips_dir
    kann diese Zusicherung nie fehlschlagen (ein echtes Leck nach
    users/default/briefings/ bliebe ungefangen, Kontextdokument R4/AC-6)."""
    path = _TESTS_DIR / "tdd" / "test_issue_731_unified_commands.py"
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    calls = _function_calls(
        tree, "TestAC10UserIsolation", "test_weiter_only_affects_own_trip"
    )

    assert "get_briefings_dir" in calls, (
        "TestAC10UserIsolation.test_weiter_only_affects_own_trip prueft die "
        "Cross-User-Zusicherung nicht gegen get_briefings_dir() (lebender "
        f"Pfad) -- gefundene Aufrufe im Methodenkoerper: {sorted(calls)}. "
        "Solange nur get_trips_dir() (toter Pfad seit #1250 Scheibe 7a) "
        "geprueft wird, kann diese Zusicherung nie fehlschlagen (AC-6). "
        "Code reference: tests/tdd/test_issue_731_unified_commands.py:403"
    )
