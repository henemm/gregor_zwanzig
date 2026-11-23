"""Echtbaum-Ratsche fuer parallele CI-Laeufe (Issue #3209, AC-5).

Unter ``pytest-xdist`` (CI: ``-n 4 --dist loadgroup``) laufen nur Tests mit
``@pytest.mark.real_data_root`` bzw. ``xdist_group("echtdaten")`` gemeinsam
und nacheinander in EINEM Worker (``tests/conftest.py`` haengt die Gruppe an
jeden ``real_data_root``-Test). Eine Testdatei, die den ECHTEN ``data/users``
-Baum des Repos beruehrt, ohne zu dieser Gruppe zu gehoeren, liefe parallel zu
Tests, die dort schreiben oder die materialisierten Referenz-Kopien kurzzeitig
entfernen -- und loeste die Echtbaum-Waechter anderer Worker aus.

``finde_echtbaum_verstoesse(wurzel)`` meldet solche Dateien statisch (AST, keine
Ausfuehrung; Kommentare, Docstrings und Code in String-Literalen zaehlen nicht).

Erkannte Zugriffe auf den echten Baum:

* ``Path("data/users...")`` / ``Path("data", "users", ...)``
* ``Path("data") / "users"``
* ``<Repo-Wurzel> / "data" / "users"`` bzw. ``<Repo-Wurzel> / "data/users"``,
  wobei die Repo-Wurzel ein Name mit ``root``/``repo`` (z. B. ``REPO_ROOT``)
  oder ein aus ``__file__`` abgeleiteter Ausdruck ist -- ``tmp_path / "data" /
  "users"`` ist KEIN Echtbaum-Zugriff.
* ``os.path.join("data", "users", ...)`` bzw. ``os.path.join(<Repo-Wurzel>,
  "data", "users", ...)``
* in allen Formen auch f-Strings, deren konstanter Anfang die Segmente
  liefert (``Path(f"data/users/{uid}")``, ``Path(f"data") / f"users/{uid}"``,
  ``os.path.join(f"data/users", uid)``) -- Fix-Loop 2.

Konform ist ein Zugriff, wenn er in einem Geltungsbereich mit
``real_data_root`` oder ``xdist_group("echtdaten")`` steht (``pytestmark`` des
Moduls oder der Klasse, Dekorator an Klasse oder Testfunktion), ODER wenn er in
einer Hilfsfunktion/Fixture/Modulkonstante steht, die ausschliesslich von
solchen konformen Tests (transitiv) verwendet wird.
"""
from __future__ import annotations

import ast
from pathlib import Path

GRUPPE = "echtdaten"
_WURZEL_HINWEISE = ("root", "repo")


# ---------------------------------------------------------------------------
# Erkennung eines Echtbaum-Zugriffs
# ---------------------------------------------------------------------------


def _str(node: ast.AST) -> str | None:
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    return None


class _Anfang(str):
    """Konstanter Anfang eines f-Strings, auf den ein Platzhalter folgt."""


def _seg(node: ast.AST) -> str | None:
    """Pfad-Segment als Text: String-Konstante, f-String ohne Platzhalter
    vollstaendig, f-String mit Platzhalter als ``_Anfang`` (konstanter Teil vor
    dem ersten Platzhalter, z. B. ``f"data/users/{uid}"`` -> ``"data/users/"``)."""
    s = _str(node)
    if s is not None:
        return s
    if isinstance(node, ast.JoinedStr):
        teile: list[str] = []
        for wert in node.values:
            t = _str(wert)
            if t is None:
                break
            teile.append(t)
        anfang = "".join(teile)
        if len(teile) == len(node.values):
            return anfang
        return _Anfang(anfang) if anfang else None
    return None


def _ist_path_aufruf(node: ast.AST) -> bool:
    if not isinstance(node, ast.Call):
        return False
    f = node.func
    name = f.id if isinstance(f, ast.Name) else f.attr if isinstance(f, ast.Attribute) else ""
    return name in ("Path", "PurePath", "PosixPath")


def _path_args(node: ast.Call) -> list[str | None]:
    return [_seg(a) for a in node.args]


def _ist_repo_wurzel(node: ast.AST) -> bool:
    """Ausdruck, der die Repo-Wurzel benennt (nicht tmp_path & Co.)."""
    for teil in ast.walk(node):
        if isinstance(teil, ast.Name):
            if teil.id == "__file__":
                return True
            low = teil.id.lower()
            if "tmp" in low or "temp" in low:
                return False
            if any(h in low for h in _WURZEL_HINWEISE):
                return True
        if isinstance(teil, ast.Attribute):
            low = teil.attr.lower()
            if any(h in low for h in _WURZEL_HINWEISE) and "tmp" not in low:
                return True
    return False


def _div_kette(node: ast.AST) -> list[ast.AST]:
    """``a / b / c`` -> [a, b, c]."""
    if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Div):
        return [*_div_kette(node.left), node.right]
    return [node]


def _segmente_beginnen_mit_data_users(segmente: list[str | None]) -> bool:
    teile: list[str] = []
    for s in segmente:
        if s is None:
            break
        teile.extend(p for p in s.split("/") if p)
        if len(teile) >= 2 or isinstance(s, _Anfang):
            break
    return teile[:2] == ["data", "users"]


def _ist_echtbaum_zugriff(node: ast.AST) -> bool:
    # Path("data/users...") / Path("data", "users", ...)
    if _ist_path_aufruf(node):
        return _segmente_beginnen_mit_data_users(_path_args(node))

    # os.path.join(...)
    if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and node.func.attr == "join":
        wert = node.func.value
        if isinstance(wert, ast.Attribute) and wert.attr == "path":
            args = list(node.args)
            if args and _seg(args[0]) is None and _ist_repo_wurzel(args[0]):
                args = args[1:]
            return _segmente_beginnen_mit_data_users([_seg(a) for a in args])
        return False

    # Div-Ketten: nur am obersten Knoten der Kette pruefen
    if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Div):
        kette = _div_kette(node)
        basis, rest = kette[0], kette[1:]
        if _ist_path_aufruf(basis):
            return _segmente_beginnen_mit_data_users(
                [*_path_args(basis), *[_seg(r) for r in rest]]
            )
        if _seg(basis) is None and _ist_repo_wurzel(basis):
            # Wurzel ueber mehrere Div-Glieder (Path(__file__).parent / ".." )
            # ueberspringen, bis die erste Konstante "data" folgt.
            segmente = [_seg(r) for r in rest]
            for i, s in enumerate(segmente):
                if s is not None and s.split("/")[0] == "data":
                    return _segmente_beginnen_mit_data_users(segmente[i:])
                if s is None:
                    return False
        return False
    return False


# ---------------------------------------------------------------------------
# Markierung (serielle Gruppe)
# ---------------------------------------------------------------------------


def _ausdruck_markiert(node: ast.AST | None) -> bool:
    """Enthaelt der Ausdruck ``real_data_root`` oder ``xdist_group('echtdaten')``?"""
    if node is None:
        return False
    for teil in ast.walk(node):
        if isinstance(teil, ast.Attribute) and teil.attr == "real_data_root":
            return True
        if isinstance(teil, ast.Call):
            f = teil.func
            name = f.attr if isinstance(f, ast.Attribute) else f.id if isinstance(f, ast.Name) else ""
            if name == "xdist_group":
                werte = [_str(a) for a in teil.args] + [
                    _str(k.value) for k in teil.keywords if k.arg == "name"
                ]
                if GRUPPE in werte:
                    return True
    return False


def _pytestmark_in(body: list[ast.stmt]) -> bool:
    for stmt in body:
        if isinstance(stmt, ast.Assign):
            if any(isinstance(t, ast.Name) and t.id == "pytestmark" for t in stmt.targets):
                if _ausdruck_markiert(stmt.value):
                    return True
        elif isinstance(stmt, ast.AnnAssign):
            if isinstance(stmt.target, ast.Name) and stmt.target.id == "pytestmark":
                if _ausdruck_markiert(stmt.value):
                    return True
    return False


def _dekoriert_markiert(node: ast.AST) -> bool:
    return any(_ausdruck_markiert(d) for d in getattr(node, "decorator_list", []))


def _ist_autouse(node: ast.AST) -> bool:
    for d in getattr(node, "decorator_list", []):
        for teil in ast.walk(d):
            if isinstance(teil, ast.keyword) and teil.arg == "autouse":
                if isinstance(teil.value, ast.Constant) and teil.value.value is True:
                    return True
    return False


# ---------------------------------------------------------------------------
# Einheiten der Datei: Funktionen und Modul-/Klassen-Anweisungen
# ---------------------------------------------------------------------------


class _Einheit:
    """Eine benannte Einheit (Funktion, Fixture oder Konstante) mit Geltungsbereich."""

    def __init__(self, namen: set[str], knoten: ast.AST, ist_test: bool,
                 markiert: bool, klasse: ast.ClassDef | None, autouse: bool):
        self.namen = namen
        self.knoten = knoten
        self.ist_test = ist_test
        self.markiert = markiert
        self.klasse = klasse
        self.autouse = autouse
        self.zugriff = any(_ist_echtbaum_zugriff(n) for n in ast.walk(knoten))


def _einheiten(baum: ast.Module) -> list[_Einheit]:
    modul_markiert = _pytestmark_in(baum.body)
    einheiten: list[_Einheit] = []

    def _sammle(body: list[ast.stmt], klasse: ast.ClassDef | None, scope_markiert: bool) -> None:
        for stmt in body:
            if isinstance(stmt, (ast.FunctionDef, ast.AsyncFunctionDef)):
                ist_test = stmt.name.startswith("test")
                einheiten.append(_Einheit(
                    {stmt.name}, stmt, ist_test,
                    scope_markiert or _dekoriert_markiert(stmt), klasse, _ist_autouse(stmt),
                ))
            elif isinstance(stmt, ast.ClassDef):
                k_markiert = (
                    scope_markiert or _dekoriert_markiert(stmt) or _pytestmark_in(stmt.body)
                )
                _sammle(stmt.body, stmt, k_markiert)
                # Klassen-Name als Einheit (Hilfsklassen ausserhalb von Tests)
                einheiten.append(_Einheit(
                    {stmt.name}, ast.Module(body=[], type_ignores=[]), False,
                    k_markiert, klasse, False,
                ))
            else:
                namen: set[str] = set()
                for teil in ast.walk(stmt):
                    if isinstance(teil, ast.Name) and isinstance(teil.ctx, ast.Store):
                        namen.add(teil.id)
                einheiten.append(_Einheit(namen, stmt, False, scope_markiert, klasse, False))

    _sammle(baum.body, None, modul_markiert)
    return einheiten


def _verweist_auf(einheit: _Einheit, name: str) -> bool:
    for teil in ast.walk(einheit.knoten):
        if isinstance(teil, ast.Name) and teil.id == name:
            if not (isinstance(teil.ctx, ast.Store) and name in einheit.namen):
                return True
        elif isinstance(teil, ast.Attribute) and teil.attr == name:
            return True
        elif isinstance(teil, ast.arg) and teil.arg == name:
            return True
        elif isinstance(teil, ast.Constant) and teil.value == name:
            return True  # usefixtures("name")
    return False


def _konform(einheit: _Einheit, alle: list[_Einheit]) -> bool:
    """Ist der Zugriff in ``einheit`` nur aus der seriellen Gruppe erreichbar?"""
    if einheit.markiert:
        return True
    if einheit.ist_test:
        return False

    gesehen: set[int] = {id(einheit)}
    offen = [einheit]
    tests: list[_Einheit] = []
    markierte_nutzer = 0
    while offen:
        aktuell = offen.pop()
        if aktuell.autouse:
            # autouse-Fixture: trifft jeden Test ihres Geltungsbereichs.
            for e in alle:
                if e.ist_test and (aktuell.klasse is None or e.klasse is aktuell.klasse):
                    tests.append(e)
        for name in aktuell.namen:
            for e in alle:
                if id(e) in gesehen or not _verweist_auf(e, name):
                    continue
                gesehen.add(id(e))
                if e.ist_test:
                    tests.append(e)
                elif e.markiert:
                    # markierte Hilfsfunktion/Fixture: laeuft nur in der Gruppe
                    markierte_nutzer += 1
                else:
                    offen.append(e)
    if not tests and not markierte_nutzer:
        return False  # niemand nutzt den Zugriff erkennbar -> nicht belegbar konform
    return all(t.markiert for t in tests)


def _datei_verstoesst(pfad: Path) -> bool:
    try:
        baum = ast.parse(pfad.read_text(encoding="utf-8"), filename=str(pfad))
    except (SyntaxError, UnicodeDecodeError):
        return False
    alle = _einheiten(baum)
    return any(e.zugriff and not _konform(e, alle) for e in alle)


def finde_echtbaum_verstoesse(wurzel: Path) -> list[str]:
    """Relative POSIX-Pfade aller ``test_*.py`` unter ``wurzel``, die den echten
    ``data/users``-Baum ausserhalb der seriellen Gruppe beruehren, sortiert."""
    wurzel = Path(wurzel)
    befunde = []
    for pfad in sorted(wurzel.rglob("test_*.py")):
        if any(teil in ("__pycache__", ".venv", "node_modules") for teil in pfad.parts):
            continue
        if _datei_verstoesst(pfad):
            befunde.append(pfad.relative_to(wurzel).as_posix())
    return sorted(befunde)
