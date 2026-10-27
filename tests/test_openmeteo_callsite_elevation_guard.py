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

Drei Baumuster werden erkannt:

1. Ein `ast.Dict`-Literal mit dem Schlüssel `"latitude"` (die vier
   openmeteo.py-Baustellen: `probe_model_availability`, `_fetch_uv_data`,
   `fetch_forecast`, `_fetch_ensemble_spread`, sowie der EINZIGE freigegebene
   Erbauer `_koordinaten_params`).
2. Ein f-String (`ast.JoinedStr`), dessen literaler Textanteil `"latitude="`
   enthält (hartkodierte URLs, z. B. per f-String zusammengesetzt).
3. Eine Schlüssel-ZUWEISUNG (`ast.Assign` mit einem `ast.Subscript`-Ziel und
   konstantem Schlüssel `"latitude"`, also `irgendwas["latitude"] = …`).
   Issue #1991 (Nachbesserung N1): dieses Muster war urspruenglich das Loch,
   ueber das `_punkt_params()` UND die primitiven Aufrufer in geosphere.py /
   radar_service.py den Waechter umgangen haben ("der AST-Waechter prueft
   nur Dict-LITERALE"). Alle drei Stellen bauen ihre Koordinaten inzwischen
   ueber den EINEN freigegebenen Erbauer `_koordinaten_params()`
   (openmeteo.py) -- die Zuweisungsform kommt im Produktivcode nicht mehr
   vor, wird aber weiterhin erkannt, damit ein KUENFTIGER Aufrufer, der
   dasselbe Loch erneut ausnutzt, gefangen wird.

Statische AST-Analyse: kein Netz, kein Mock, keine Marker — Kern-Schicht.
"""
from __future__ import annotations

import ast
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SRC = REPO_ROOT / "src"
API = REPO_ROOT / "api"

_MODULE_SCOPE = "<module>"

# Benannte, BEWUSSTE Ausnahmen. Schluessel: "<pfad>::<funktion>".
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
    "src/providers/openmeteo.py::_koordinaten_params": (
        "Der EINE freigegebene Erbauer (Issue #1991, Nachbesserung N1): "
        "_punkt_params() UND die primitiven lat/lon-Aufrufer in "
        "geosphere.py/radar_service.py bauen ihre Koordinaten ausschliesslich "
        "hierueber -- kein zweiter, unregistrierter Aufbau-Ort im Code."
    ),
    "src/app/cli.py::main": (
        "`overrides['latitude'] = args.lat` fuellt das CLI-Override-Dict fuer "
        "`Settings(**overrides)` -- kein Open-Meteo-Request-Params-Dict. Die "
        "eigentliche Anfrage baut spaeter, ueber die aufgeloeste Location, "
        "ausschliesslich `_koordinaten_params()`; hier wird nichts an die "
        "Wire-Anfrage durchgereicht (Legacy-CLI, Debug-Werkzeug)."
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


def _assign_traegt_latitude(knoten: ast.Assign) -> bool:
    """N1-Nachbesserung: `irgendwas["latitude"] = …` -- die Zuweisungsform,
    ueber die `_punkt_params()` und geosphere.py/radar_service.py den
    Waechter urspruenglich umgangen haben."""
    for ziel in knoten.targets:
        if (
            isinstance(ziel, ast.Subscript)
            and isinstance(ziel.slice, ast.Constant)
            and ziel.slice.value == "latitude"
        ):
            return True
    return False


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
        elif isinstance(knoten, ast.Assign) and _assign_traegt_latitude(knoten):
            art = "subscript_assign"
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


# Issue #1991 (N4-Nachbesserung): Die fruehere Positivkontrolle
# `test_bekannte_verstoesse_werden_am_richtigen_ort_gefunden` pruefte, dass
# vier konkrete Produktivstellen weiterhin Verstoesse SIND -- nach der
# Implementierung (alle vier laufen ueber `_koordinaten_params()`) ist das
# per Konstruktion falsch und der Test wuerde konsequent rot bleiben. Die
# Funktionsfaehigkeit des Scanners selbst ist unabhaengig davon durch die
# `test_scanner_erkennt_*`-Tests unten belegt (SYNTHETISCHE Dateien je
# Baumuster, nicht auf den aktuellen Produktivstand angewiesen) -- deshalb
# bewusst ersatzlos entfernt statt zu einem wirkungslosen Test umgebaut.


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


def test_scanner_erkennt_zuweisung_in_synthetischer_datei(tmp_path):
    """N1-Nachbesserung: das urspruengliche Loch -- `params["latitude"] = …`
    statt eines Dict-Literals -- muss ebenfalls erkannt werden."""
    datei = tmp_path / "synthetischer_aufrufer_zuweisung.py"
    datei.write_text(
        "def hole(lat, lon):\n"
        "    params = {}\n"
        "    params['latitude'] = lat\n"
        "    params['longitude'] = lon\n"
        "    return client.get(url, params=params)\n",
        encoding="utf-8",
    )
    funde = _funde(datei)
    assert any(v == "subscript_assign" for v in funde.values()), (
        f"Scanner hat die Schluessel-Zuweisung nicht erkannt: {funde}"
    )


def test_scanner_erkennt_zuweisung_vor_urlencode_in_synthetischer_datei(tmp_path):
    """N1-Nachbesserung: dieselbe Zuweisungsform, hier fuer ein Dict, das
    anschliessend per `urlencode()` in eine URL uebersetzt wird (Vorbild
    radar_service.py::_fetch_openmeteo_15 vor der Umstellung auf den
    gemeinsamen Erbauer)."""
    datei = tmp_path / "synthetischer_aufrufer_urlencode_zuweisung.py"
    datei.write_text(
        "from urllib.parse import urlencode\n"
        "def hole(lat, lon):\n"
        "    query = {}\n"
        "    query['latitude'] = lat\n"
        "    query['longitude'] = lon\n"
        "    url = 'https://api.open-meteo.com/v1/forecast?' + urlencode(query)\n"
        "    return client.get(url)\n",
        encoding="utf-8",
    )
    funde = _funde(datei)
    assert any(v == "subscript_assign" for v in funde.values()), (
        f"Scanner hat die Zuweisung vor urlencode() nicht erkannt: {funde}"
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
