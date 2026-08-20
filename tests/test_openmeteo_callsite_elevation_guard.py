"""Issue #1991 (AC-4) — Wächter: jede Open-Meteo-Anfrage baut ihre Koordinaten
über den gemeinsamen Params-Erbauer, statt selbst ein `latitude`-tragendes
Dict-Literal oder einen `latitude=`-f-String zu bauen.

Spec: docs/specs/modules/wegpunkt_hoehe_provider.md AC-4.
Context: docs/context/fix-1991-wegpunkt-hoehe.md (E1).

Warum es diesen Wächter gibt: `_request()` (openmeteo.py:598) ist bewusst
NICHT der Durchreiche-Ort für die Wegpunkt-Höhe — es kennt die `Location` gar
nicht und deckt nur vier von sechs Baustellen ab. Der zukünftige gemeinsame
Erbauer `_punkt_params()` (Spec, S1) muss deshalb an JEDER Stelle verwendet
werden, die Open-Meteo mit Koordinaten anspricht — sonst leckt eine neue
Stelle die Höhe unbemerkt weiter. Dieser Wächter erzwingt das statisch, über
`src/` und `api/`.

Zwei Baumuster werden erkannt (beide bereits im Produktivcode vorhanden):

1. Ein `ast.Dict`-Literal mit dem Schlüssel `"latitude"` (die vier
   openmeteo.py-Baustellen: `probe_model_availability`, `_fetch_uv_data`,
   `fetch_forecast`, `_fetch_ensemble_spread`).
2. Ein f-String (`ast.JoinedStr`), dessen literaler Textanteil `"latitude="`
   enthält (`geosphere.py::_fetch_openmeteo_clouds`,
   `radar_service.py::_fetch_openmeteo_15` — beide hartkodierte URLs).

Statische AST-Analyse: kein Netz, kein Mock, keine Marker — Kern-Schicht.

Erwartete Rotfärbung heute: der Erbauer existiert noch nicht, also läuft
JEDE der o.g. Stellen (ausser den zwei bewusst dokumentierten Ausnahmen)
noch direkt über ein Dict-Literal bzw. einen f-String — der Wächter meldet
sie alle als Verstoß. Das ist erwartet (fehlender Erbauer-Eintrag, kein
Import-/Tippfehler) und wird erst nach S1 grün.
"""
from __future__ import annotations

import ast
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SRC = REPO_ROOT / "src"
API = REPO_ROOT / "api"

_MODULE_SCOPE = "<module>"

# Benannte, BEWUSSTE Ausnahmen. Schluessel: "<pfad>::<funktion>". Beide aus
# der Spec (Implementation Details, S1): weder Stelle hat einen Ortsbezug,
# der eine Wegpunkt-Hoehe tragen koennte bzw. annehmen wuerde.
BEWUSSTE_AUSNAHMEN: dict[str, str] = {
    "src/providers/openmeteo.py::probe_model_availability": (
        "Faehigkeits-Probe mit festen Sondier-Koordinaten (Modell-Bounding-"
        "Box-Mittelpunkt aus _PROBE_COORDS) ohne Ortsbezug -- es gibt keinen "
        "Wegpunkt, dessen Hoehe hier mitgeschickt werden koennte (Spec S1)."
    ),
    "src/providers/openmeteo.py::_fetch_uv_data": (
        "Luftqualitaets-/CAMS-Endpunkt (Air-Quality-API) kennt keinen "
        "elevation-Parameter -- Issue #1991 AC-13, Spec Known Limitations."
    ),
}


def _scan_files() -> list[Path]:
    return sorted(p for p in [*SRC.rglob("*.py"), *API.rglob("*.py")] if p.exists())


def _scopes(tree: ast.AST) -> dict[int, str]:
    """Knoten -> Name der umgebenden Funktion (sonst ``<module>``). Woertlich
    dasselbe Vorgehen wie in ``test_onset_callsite_timezone_guard.py``."""
    zuordnung: dict[int, str] = {id(tree): _MODULE_SCOPE}
    stapel: list[tuple[ast.AST, str]] = [(tree, _MODULE_SCOPE)]
    while stapel:
        knoten, name = stapel.pop()
        for kind in ast.iter_child_nodes(knoten):
            if isinstance(kind, (ast.FunctionDef, ast.AsyncFunctionDef)):
                zuordnung[id(kind)] = kind.name
                stapel.append((kind, kind.name))
            else:
                zuordnung[id(kind)] = name
                stapel.append((kind, name))
    return zuordnung


def _dict_traegt_latitude(knoten: ast.Dict) -> bool:
    return any(
        isinstance(k, ast.Constant) and k.value == "latitude" for k in knoten.keys
    )


def _joinedstr_traegt_latitude(knoten: ast.JoinedStr) -> bool:
    return any(
        isinstance(teil, ast.Constant)
        and isinstance(teil.value, str)
        and "latitude=" in teil.value
        for teil in knoten.values
    )


def _funde(pfad: Path) -> dict[str, str]:
    """Fundstellen in EINER Datei -> {"<pfad>::<funktion>::<zeile>": Art}."""
    try:
        baum = ast.parse(pfad.read_text(encoding="utf-8"))
    except (SyntaxError, UnicodeDecodeError):
        return {}
    raum = _scopes(baum)
    try:
        rel = pfad.relative_to(REPO_ROOT).as_posix()
    except ValueError:
        rel = pfad.as_posix()

    treffer: dict[str, str] = {}
    for knoten in ast.walk(baum):
        art = None
        if isinstance(knoten, ast.Dict) and _dict_traegt_latitude(knoten):
            art = "dict_literal"
        elif isinstance(knoten, ast.JoinedStr) and _joinedstr_traegt_latitude(knoten):
            art = "f_string"
        if art is None:
            continue
        schluessel = f"{rel}::{raum.get(id(knoten), _MODULE_SCOPE)}"
        treffer[f"{schluessel}::{knoten.lineno}"] = art
    return treffer


def _alle_funde() -> dict[str, str]:
    gesamt: dict[str, str] = {}
    for pfad in _scan_files():
        gesamt.update(_funde(pfad))
    return gesamt


def _ohne_ausnahmen(funde: dict[str, str]) -> dict[str, str]:
    return {
        k: v for k, v in funde.items()
        if k.rsplit("::", 1)[0] not in BEWUSSTE_AUSNAHMEN
    }


# ---------------------------------------------------------------------------


def test_produktive_aufrufer_verwenden_den_gemeinsamen_hoehe_erbauer():
    """GIVEN den Produktivcode unter src/ und api/
    WHEN eine Stelle Open-Meteo mit einem `latitude`-tragenden Dict-Literal
    oder `latitude=`-f-String direkt anspricht
    THEN steht sie entweder nicht mehr da (laeuft ueber den gemeinsamen
    Erbauer) oder namentlich mit Begruendung in BEWUSSTE_AUSNAHMEN.

    ROT heute: der Erbauer existiert noch nicht -- ALLE bekannten Baustellen
    ausser den zwei dokumentierten Ausnahmen bauen ihre Koordinaten noch
    direkt.
    """
    verstoesse = _ohne_ausnahmen(_alle_funde())
    assert not verstoesse, (
        "Produktivcode spricht Open-Meteo mit Koordinaten an, ohne ueber den "
        "gemeinsamen Params-Erbauer zu laufen (Issue #1991). Entweder ueber "
        "den Erbauer umstellen oder mit Begruendung in BEWUSSTE_AUSNAHMEN "
        f"eintragen — Code reference: {sorted(verstoesse.items())}"
    )


def test_bekannte_verstoesse_werden_am_richtigen_ort_gefunden():
    """Positivkontrolle (Scan=Verdacht, Entwarnung nur mit Positivkontrolle):
    ohne diesen Nachweis koennte der Scanner aus einem Pfad-, Parser- oder
    Namensfehler leer laufen und die vorherige Zusicherung waere trivial
    gruen, weil sie eine leere Menge prueft."""
    gefundene_orte = {k.rsplit("::", 1)[0] for k in _alle_funde()}
    erwartet = {
        "src/providers/openmeteo.py::fetch_forecast",
        "src/providers/openmeteo.py::_fetch_ensemble_spread",
        "src/providers/geosphere.py::_fetch_openmeteo_clouds",
        "src/services/radar_service.py::_fetch_openmeteo_15",
    }
    fehlend = erwartet - gefundene_orte
    assert not fehlend, f"Scanner findet bekannte Verstoesse nicht: {fehlend}"


def test_jede_eingetragene_ausnahme_existiert_noch():
    """Shrink-Schutz: eine Ausnahme, die im Code nicht mehr vorkommt, ist
    veraltet und muss raus -- sonst waechst die Liste zu einem Friedhof, in
    dem eine echte neue Ausnahme nicht mehr auffaellt."""
    vorhanden = {k.rsplit("::", 1)[0] for k in _alle_funde()}
    veraltet = sorted(set(BEWUSSTE_AUSNAHMEN) - vorhanden)
    assert not veraltet, (
        f"Veraltete Eintraege in BEWUSSTE_AUSNAHMEN: {veraltet} — die "
        "Aufrufstelle gibt es nicht mehr oder sie baut ihre Koordinaten "
        "bereits ueber den Erbauer. Eintrag entfernen."
    )


def test_jede_ausnahme_traegt_eine_begruendung():
    """Eine Ausnahme ohne Begruendung ist eine Ausrede."""
    ohne = sorted(k for k, v in BEWUSSTE_AUSNAHMEN.items() if len(v.strip()) < 40)
    assert not ohne, f"Ausnahmen ohne tragfaehige Begruendung: {ohne}"


# --- Wirkungsnachweise: faengt der Scanner ueberhaupt etwas? ---------------


def test_scanner_erkennt_dict_literal_in_synthetischer_datei(tmp_path):
    datei = tmp_path / "synthetischer_aufrufer_dict.py"
    datei.write_text(
        "def hole():\n"
        "    params = {'latitude': 47.0, 'longitude': 11.0}\n"
        "    return client.get(url, params=params)\n",
        encoding="utf-8",
    )
    funde = _funde(datei)
    assert any(v == "dict_literal" for v in funde.values()), (
        f"Scanner hat das Dict-Literal nicht erkannt: {funde}"
    )


def test_scanner_erkennt_fstring_in_synthetischer_datei(tmp_path):
    datei = tmp_path / "synthetischer_aufrufer_fstring.py"
    datei.write_text(
        "def hole(lat, lon):\n"
        "    url = f'https://api.open-meteo.com/v1/forecast?latitude={lat}&longitude={lon}'\n"
        "    return client.get(url)\n",
        encoding="utf-8",
    )
    funde = _funde(datei)
    assert any(v == "f_string" for v in funde.values()), (
        f"Scanner hat den f-String nicht erkannt: {funde}"
    )


def test_scanner_meldet_aufruf_ueber_kuenftigen_erbauer_nicht(tmp_path):
    """Gegenprobe: eine Stelle, die den (kuenftigen) gemeinsamen Erbauer
    aufruft statt selbst ein Dict/f-String mit 'latitude' zu bauen, darf
    NICHT als Verstoss auftauchen -- sonst waere der Waechter nach der
    Implementierung nie gruen zu bekommen."""
    datei = tmp_path / "synthetischer_aufrufer_ok.py"
    datei.write_text(
        "def hole(location):\n"
        "    params = _punkt_params(location, hourly='temperature_2m')\n"
        "    return client.get(url, params=params)\n",
        encoding="utf-8",
    )
    assert not _funde(datei), (
        f"Aufruf UEBER den Erbauer faelschlich als Verstoss gezaehlt: {_funde(datei)}"
    )
