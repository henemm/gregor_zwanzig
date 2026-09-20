"""Struktur-Waechter: ``user_id`` als Pflichtparameter an FastAPI-Endpunkten
(#2156, Epic #2138, ADR-0003).

Spec: docs/specs/modules/store_scope_call_guard.md v2.0 (AC-6, AC-8 Doku-Teil)

Es gibt bislang keinen Test, der meldet, wenn ein Endpunkt in
``api/routers/`` einen ``user_id``-Parameter mit Default fuehrt --
``test_user_id_default_guard.py`` prueft nur, dass der Default nicht
konkret ``"default"`` lautet (Scheibe A/C), nicht die Existenz eines
Pflichtparameters ueberhaupt. Dieser Waechter prueft die WIRKUNG der
Signatur (Pflichtparameter ja/nein), nicht ihre Schreibweise -- eine reine
Textpruefung auf ``Query(...)`` erzeugte in der Analyse 5 Fehlalarme und
uebersah 2 wirkungsgleiche Faelle (``api/routers/scheduler.py:97/107``,
``user_id: str`` ohne ``Query(...)``).

Marker-Konvention (analog Go, ``# gz-<thema>: <Begruendung>``): ein
Endpunkt darf ``user_id`` ausnahmsweise optional fuehren, wenn er den
Kommentar ``# gz-user-id-optional: <Begruendung>`` (>= 15 Zeichen) direkt
(nur Dekorator-/Leerzeilen dazwischen) vor der Funktionsdefinition traegt.
Ein solcher Marker an einem Endpunkt, der die Regel ohnehin erfuellt, gilt
als verwaist und macht den Waechter rot -- Marker sollen sichtbare,
begruendete Ausnahmen bleiben, keine stille Dekoration.
"""
from __future__ import annotations

import ast
import re
from dataclasses import dataclass
from pathlib import Path

_REPO = Path(__file__).resolve().parents[1]

_MARKER_OPTIONAL = "gz-user-id-optional:"
_MIN_BEGRUENDUNG = 15
_MIN_ENDPUNKTE = 15  # heute 22 Pflicht-Endpunkte -- Selbstschutz gegen "Pfad verloren"

_ROUTER_METHODEN = {"get", "post", "put", "delete", "patch", "head", "options"}
_DEF_RE = re.compile(r"^\s*(?:async\s+)?def\s+\w+")
_DECORATOR_RE = re.compile(r"^\s*@")
_NICHT_WORT_RE = re.compile(r"[^\w]+", re.UNICODE)


def _begruendung_gueltig(text: str) -> bool:
    return len(_NICHT_WORT_RE.sub("", text)) >= _MIN_BEGRUENDUNG


def _marker_ziel_zeilen(quelltext: str) -> dict[int, str]:
    """1-indexierte Zeile der naechsten Funktionsdefinition -> Begruendung,
    fuer jeden ``# gz-user-id-optional:``-Kommentar, der (nur durch
    Dekorator-/Leerzeilen getrennt) direkt vor einer ``def``/``async def``
    steht. Kein AST-Weg moeglich -- Python-Kommentare sind nicht Teil des
    Syntaxbaums, daher Zeilenscan analog zum Go-Doc-Comment-Mechanismus."""
    zeilen = quelltext.splitlines()
    ziel: dict[int, str] = {}
    for i, zeile in enumerate(zeilen):
        stripped = zeile.lstrip()
        if not stripped.startswith("#") or _MARKER_OPTIONAL not in stripped:
            continue
        begruendung = stripped.split(_MARKER_OPTIONAL, 1)[1].strip()
        j = i + 1
        while j < len(zeilen) and (not zeilen[j].strip() or _DECORATOR_RE.match(zeilen[j])):
            j += 1
        if j < len(zeilen) and _DEF_RE.match(zeilen[j]):
            ziel[j + 1] = begruendung
    return ziel


def _ist_router_dekoriert(node: ast.FunctionDef | ast.AsyncFunctionDef) -> bool:
    for dec in node.decorator_list:
        ziel = dec.func if isinstance(dec, ast.Call) else dec
        if isinstance(ziel, ast.Attribute) and ziel.attr in _ROUTER_METHODEN:
            if getattr(ziel.value, "id", None) == "router":
                return True
    return False


def _user_id_parameter(node: ast.FunctionDef | ast.AsyncFunctionDef) -> ast.arg | None:
    for arg in node.args.args + node.args.kwonlyargs:
        if arg.arg == "user_id":
            return arg
    return None


def _default_fuer(node: ast.FunctionDef | ast.AsyncFunctionDef, ziel: ast.arg) -> ast.AST | None:
    a = node.args
    positional = a.posonlyargs + a.args
    paare = list(zip(positional[len(positional) - len(a.defaults):], a.defaults))
    paare += list(zip(a.kwonlyargs, a.kw_defaults))
    for arg, default in paare:
        if arg is ziel and default is not None:
            return default
    return None


def _ist_pflichtparameter(default: ast.AST | None) -> bool:
    """AC-6: ``user_id`` ist erfuellt ohne Default ODER mit ``Query(...)``,
    dessen ERSTES Positional-Argument ``Ellipsis`` ist (weitere kwargs wie
    ``description=`` sind unschaedlich)."""
    if default is None:
        return True
    if isinstance(default, ast.Call):
        name = getattr(default.func, "id", None) or getattr(default.func, "attr", None)
        if name == "Query" and default.args:
            erstes = default.args[0]
            return isinstance(erstes, ast.Constant) and erstes.value is Ellipsis
    return False


@dataclass
class Endpunktbefund:
    datei: str
    funktion: str
    zeile: int
    grund: str


def pruefe_endpunkte(wurzel: Path) -> tuple[list[Endpunktbefund], int]:
    """AST-Wächter ueber ``wurzel/api/routers/*.py``. Liefert (Funde, Anzahl
    gepruefter Endpunkte mit ``user_id``-Parameter)."""
    funde: list[Endpunktbefund] = []
    geprueft = 0
    router_dir = wurzel / "api" / "routers"
    if not router_dir.exists():
        return funde, geprueft
    for datei in sorted(router_dir.glob("*.py")):
        quelltext = datei.read_text(encoding="utf-8")
        baum = ast.parse(quelltext, filename=str(datei))
        marker_ziele = _marker_ziel_zeilen(quelltext)
        verwendet: set[int] = set()
        rel = datei.relative_to(wurzel).as_posix()
        for node in ast.walk(baum):
            if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            if not _ist_router_dekoriert(node):
                continue
            arg = _user_id_parameter(node)
            if arg is None:
                continue
            geprueft += 1
            pflicht = _ist_pflichtparameter(_default_fuer(node, arg))
            begruendung = marker_ziele.get(node.lineno)
            hat_marker = begruendung is not None
            if hat_marker:
                verwendet.add(node.lineno)

            if pflicht and hat_marker:
                funde.append(Endpunktbefund(rel, node.name, node.lineno,
                    "verwaister gz-user-id-optional Marker -- Endpunkt erfuellt die Regel ohnehin"))
            elif not pflicht and not hat_marker:
                funde.append(Endpunktbefund(rel, node.name, node.lineno,
                    "user_id hat einen Default und traegt keinen gz-user-id-optional Marker"))
            elif not pflicht and hat_marker and not _begruendung_gueltig(begruendung):
                funde.append(Endpunktbefund(rel, node.name, node.lineno,
                    f"gz-user-id-optional Begruendung zu kurz (< {_MIN_BEGRUENDUNG} Zeichen)"))

        for zeile in set(marker_ziele) - verwendet:
            funde.append(Endpunktbefund(rel, "?", zeile,
                "gz-user-id-optional Marker haengt an keiner Endpunkt-Funktion mit user_id"))
    return funde, geprueft


# ═══════════════════════════ AC-6 (Ist-Stand) ═════════════════════════════


def test_ac6_router_endpunkte_haben_user_id_als_pflichtparameter():
    """AC-6: jeder Endpunkt in api/routers/ mit user_id-Parameter erfuellt
    die Wirkungsregel (kein Default, Query(...) mit Ellipsis, oder gueltiger
    gz-user-id-optional Marker). Heute 0 Befunde bei 22 Pflicht-Endpunkten --
    inklusive api/routers/scheduler.py:97/107 (user_id: str ohne Query),
    die korrekt als erfuellt gelten."""
    funde, geprueft = pruefe_endpunkte(_REPO)
    assert geprueft >= _MIN_ENDPUNKTE, (
        f"nur {geprueft} Endpunkte mit user_id geprueft (erwartet >= {_MIN_ENDPUNKTE}) -- "
        "Pfad verloren?"
    )
    assert funde == [], f"AC-6: user_id-Pflicht verletzt: {funde}"


# ═════════════════════ AC-8 (Doku-Teil, doc-compliance) ═══════════════════


def test_ac8_gates_und_ratschen_hat_abschnitt_und_pruefdatum():
    """AC-8 (Doku-Teil) — # doc-compliance-test

    docs/reference/gates_und_ratschen.md hat einen
    Abschnitt zur neuen Ratsche (Marker-Syntax-Tabelle) und eine Zeile mit
    dem Pruefdatum 2026-12-20 in der Tabelle 'Regel-Budget: Pruefdaten im
    Ueberblick'. Reine Metadaten-Praesenz, kein Verhaltensnachweis moeglich
    -- Ausnahme von der Dateiinhalt-Check-Regel.

    RED heute: weder der Abschnitt noch die Pruefdatum-Zeile existieren
    (0 Treffer nachgemessen); Phase 6 traegt beides ein.
    """
    text = (_REPO / "docs" / "reference" / "gates_und_ratschen.md").read_text(encoding="utf-8")
    assert "2026-12-20" in text, (
        "AC-8: Pruefdatum-Zeile fuer den store-scope-call-guard fehlt in "
        "docs/reference/gates_und_ratschen.md"
    )
    assert "gz-store-scope-exempt" in text or "gz-store-scope-required" in text, (
        "AC-8: Marker-Syntax-Tabelle fuer den store-scope-call-guard fehlt in "
        "docs/reference/gates_und_ratschen.md"
    )


# ═══════════════════════ AC-4 / AC-7 (Mutations-Gegenproben) ══════════════


def test_ac4_und_ac7_waechter_erkennt_default_und_query_verstoss(tmp_path):
    """AC-6 Test-Bullet + AC-7 Mutations-Gegenprobe: je eine Fixture fuer
    'ohne Default', 'Query(...)', 'user_id: str ohne Query' (alle drei
    gruen) sowie 'Default-String' und 'Query(\"x\")' (beide rot)."""
    router = tmp_path / "api" / "routers"
    router.mkdir(parents=True)
    (router / "fixture.py").write_text(
        "from fastapi import APIRouter, Query\n"
        "router = APIRouter()\n"
        "@router.get('/a')\n"
        "def ohne_default(user_id: str):\n    pass\n\n"
        "@router.get('/b')\n"
        "def mit_query(user_id: str = Query(...)):\n    pass\n\n"
        "@router.get('/c')\n"
        "def kein_query_pflicht(user_id: str):\n    pass\n\n"
        "@router.get('/d')\n"
        "def default_string(user_id: str = 'default'):\n    pass\n\n"
        "@router.get('/e')\n"
        "def query_mit_wert(user_id: str = Query('x')):\n    pass\n",
        encoding="utf-8",
    )
    funde, geprueft = pruefe_endpunkte(tmp_path)
    assert geprueft == 5
    verletzer = {f.funktion for f in funde}
    assert verletzer == {"default_string", "query_mit_wert"}, funde


def test_ac4_und_ac6_verwaister_marker_an_regelkonformem_endpunkt(tmp_path):
    """AC-4/AC-6: ein gz-user-id-optional Marker an einem Endpunkt, der die
    Regel ohnehin erfuellt (Query(...) mit Ellipsis), gilt als verwaist."""
    router = tmp_path / "api" / "routers"
    router.mkdir(parents=True)
    (router / "fixture.py").write_text(
        "from fastapi import APIRouter, Query\n"
        "router = APIRouter()\n"
        "# gz-user-id-optional: unnoetig, Endpunkt ist ohnehin pflichtig hier\n"
        "@router.get('/a')\n"
        "def regelkonform(user_id: str = Query(...)):\n    pass\n",
        encoding="utf-8",
    )
    funde, _ = pruefe_endpunkte(tmp_path)
    assert len(funde) == 1
    assert "verwaist" in funde[0].grund


def test_ac4_zu_kurze_marker_begruendung_wird_gemeldet(tmp_path):
    """AC-4: eine Begruendung unter 15 Zeichen macht den Waechter rot, auch
    wenn der Marker an einem tatsaechlich optionalen Endpunkt haengt."""
    router = tmp_path / "api" / "routers"
    router.mkdir(parents=True)
    (router / "fixture.py").write_text(
        "from fastapi import APIRouter\n"
        "router = APIRouter()\n"
        "# gz-user-id-optional: passt\n"
        "@router.get('/a')\n"
        "def alt_modus(user_id: str = 'legacy'):\n    pass\n",
        encoding="utf-8",
    )
    funde, _ = pruefe_endpunkte(tmp_path)
    assert len(funde) == 1
    assert "zu kurz" in funde[0].grund


def test_ac6_gueltiger_marker_unterdrueckt_befund(tmp_path):
    """AC-6: ein gueltiger gz-user-id-optional Marker (>= 15 Zeichen
    Begruendung) an einem Endpunkt mit Default unterdrueckt den Fund."""
    router = tmp_path / "api" / "routers"
    router.mkdir(parents=True)
    (router / "fixture.py").write_text(
        "from fastapi import APIRouter\n"
        "router = APIRouter()\n"
        "# gz-user-id-optional: Rueckwaertskompatibler Alt-Client-Modus, siehe #XYZ\n"
        "@router.get('/a')\n"
        "def alt_modus(user_id: str = 'legacy'):\n    pass\n",
        encoding="utf-8",
    )
    funde, _ = pruefe_endpunkte(tmp_path)
    assert funde == []
