"""Issue #1991 (AC-4, AC-8, AC-9) — Wächter am Wirkort fuer die RESTLICHEN
zwei Hoehe-Durchreiche-Stellen, die `test_openmeteo_callsite_elevation_guard.py`
(bewusst) NICHT abdeckt: `RadarNowcastService.get_nowcast()`-Aufrufer und
`Location(...)`-Konstruktionen.

Warum ein zweiter Wächter statt Erweiterung des ersten: der erste Wächter
gruppiert seine Funde nach Funktions-Scope in EINER `BEWUSSTE_AUSNAHMEN`-
Liste fuer drei Dict/String-Baumuster. Wuerden `get_nowcast`- und
`Location`-Funde in denselben Namensraum gemischt, wuerde eine Ausnahme fuer
den EINEN Fund-Typ in einem Scope automatisch auch Funde des ANDEREN Typs im
selben Scope verdecken — ein Loch, das schwer aufzuloesen ist. Getrennte
Dateien = getrennte Ausnahme-Namensraeume = keine Querverdeckung.

Fuenf bis sechs punktuelle Einzeltests (je Aufrufer) waeren hier das falsche
Werkzeug gewesen: sie sagen nichts ueber einen SIEBTEN, morgen geschriebenen
Aufrufer. Dieser Wächter erzwingt die Regel STRUKTURELL, ueber `src/` und
`api/`, exakt wie `test_openmeteo_callsite_elevation_guard.py`.

Zwei unabhaengige Pruefungen:

1. **`get_nowcast`-Aufrufe**: jeder `.get_nowcast(...)`-Call MUSS ein
   `elevation_m=`-Schluesselwort tragen (nicht nur positional — die Spec
   verlangt woertlich das Schluesselwort, damit an der Aufrufstelle sichtbar
   bleibt, DASS ueber Hoehe nachgedacht wurde, auch wenn der Wert `None`
   ist). `RadarNowcastService.get_nowcast()` selbst (die Methoden-DEFINITION,
   kein Aufruf) ist naturgemaess kein Fund, da sie kein `ast.Call` ist.

2. **`Location(...)`-Konstruktionen**: JEDE Konstruktion der Klasse
   `app.config.Location` in `src/`/`api/` muss `elevation_m=` setzen. Diese
   Regel ist bewusst NICHT eingeschraenkt auf "Konstruktionen, die an einen
   Wetterabruf gehen" (was Datenfluss-Analyse braeuchte, die AST alleine
   nicht leistet) — sondern greift auf JEDE Konstruktion der Klasse, deren
   eigene Docstring lautet: "Geographic location for weather queries." Eine
   Ausnahme waere nur fuer eine `Location`, die nachweislich NICHT fuer einen
   Wetterabruf gebaut wird, gerechtfertigt; nach Durchsicht von `src/` und
   `api/` gibt es aktuell keine solche Stelle — die Ausnahmeliste ist daher
   leer, aber der Mechanismus bleibt (analog zum ersten Wächter) fuer
   kuenftige, tatsaechlich begruendete Faelle bestehen.

Was dieser Wächter NICHT faengt: eine Stelle, die `elevation_m=<falscher
Wert>` traegt (z. B. eine vertauschte Variable) — er prueft nur, DASS das
Schluesselwort da ist, nicht ob der Wert stimmt. Wert-Korrektheit ist Sache
der AC-1/AC-6/AC-8-Tests (echte HTTP-Request-Pruefung bzw. Cache-Verhalten),
nicht dieser statischen Struktur-Pruefung.

Spec: docs/specs/modules/wegpunkt_hoehe_provider.md AC-4, AC-8, AC-9.

Statische AST-Analyse: kein Netz, kein Mock, keine Marker — Kern-Schicht.
"""
from __future__ import annotations

import ast
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SRC = REPO_ROOT / "src"
API = REPO_ROOT / "api"

_MODULE_SCOPE = "<module>"

# Benannte, BEWUSSTE Ausnahmen fuer Pruefung 1 (get_nowcast-Aufrufe).
# Schluessel: "<pfad>::<funktion>". Aktuell leer -- alle bekannten Aufrufer
# (trip_alert.py, trip_report_scheduler.py, compare_radar_alert.py,
# trip_command_processor.py, thunder_enrichment.py) tragen das Schluesselwort
# bereits (Issue #1991, S1-S4). Der Mechanismus bleibt fuer kuenftige,
# tatsaechlich begruendete Faelle bestehen (z. B. ein interner Test-Helfer,
# der absichtlich ohne Hoehenbezug aufruft).
NOWCAST_AUSNAHMEN: dict[str, str] = {}

# Benannte, BEWUSSTE Ausnahmen fuer Pruefung 2 (Location-Konstruktionen).
# Schluessel: "<pfad>::<funktion>". Leer aus demselben Grund wie oben --
# Durchsicht von src/ und api/ fand keine Location-Konstruktion, die
# nachweislich nicht fuer einen Wetterabruf bestimmt ist.
LOCATION_AUSNAHMEN: dict[str, str] = {}


def _scan_files() -> list[Path]:
    return sorted(p for p in [*SRC.rglob("*.py"), *API.rglob("*.py")] if p.exists())


def _scopes(tree: ast.AST) -> dict[int, str]:
    """Knoten -> Name der umgebenden Funktion (sonst ``<module>``)."""
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


def _ist_get_nowcast_aufruf(knoten: ast.Call) -> bool:
    return isinstance(knoten.func, ast.Attribute) and knoten.func.attr == "get_nowcast"


def _ist_location_konstruktion(knoten: ast.Call) -> bool:
    func = knoten.func
    if isinstance(func, ast.Name):
        return func.id == "Location"
    if isinstance(func, ast.Attribute):
        return func.attr == "Location"
    return False


def _traegt_elevation_keyword(knoten: ast.Call) -> bool:
    return any(kw.arg == "elevation_m" for kw in knoten.keywords)


def _funde(pfad: Path) -> tuple[dict[str, str], dict[str, str]]:
    """Fundstellen in EINER Datei -> (nowcast_funde, location_funde), je
    ``{"<pfad>::<funktion>::<zeile>": "ohne_elevation_m"}``."""
    try:
        baum = ast.parse(pfad.read_text(encoding="utf-8"))
    except (SyntaxError, UnicodeDecodeError):
        return {}, {}
    raum = _scopes(baum)
    try:
        rel = pfad.relative_to(REPO_ROOT).as_posix()
    except ValueError:
        rel = pfad.as_posix()

    nowcast_treffer: dict[str, str] = {}
    location_treffer: dict[str, str] = {}
    for knoten in ast.walk(baum):
        if not isinstance(knoten, ast.Call):
            continue
        if _traegt_elevation_keyword(knoten):
            continue
        schluessel = f"{rel}::{raum.get(id(knoten), _MODULE_SCOPE)}::{knoten.lineno}"
        if _ist_get_nowcast_aufruf(knoten):
            nowcast_treffer[schluessel] = "ohne_elevation_m"
        elif _ist_location_konstruktion(knoten):
            location_treffer[schluessel] = "ohne_elevation_m"
    return nowcast_treffer, location_treffer


def _alle_funde() -> tuple[dict[str, str], dict[str, str]]:
    nowcast_gesamt: dict[str, str] = {}
    location_gesamt: dict[str, str] = {}
    for pfad in _scan_files():
        n, l = _funde(pfad)
        nowcast_gesamt.update(n)
        location_gesamt.update(l)
    return nowcast_gesamt, location_gesamt


def _ohne_ausnahmen(funde: dict[str, str], ausnahmen: dict[str, str]) -> dict[str, str]:
    return {
        k: v for k, v in funde.items()
        if k.rsplit("::", 1)[0] not in ausnahmen
    }


# ---------------------------------------------------------------------------


def test_jeder_get_nowcast_aufruf_traegt_elevation_keyword():
    """GIVEN den Produktivcode unter src/ und api/
    WHEN eine Stelle `RadarNowcastService.get_nowcast(...)` aufruft
    THEN traegt der Aufruf ein `elevation_m=`-Schluesselwort — oder steht
    namentlich mit Begruendung in NOWCAST_AUSNAHMEN.
    """
    nowcast_funde, _ = _alle_funde()
    verstoesse = _ohne_ausnahmen(nowcast_funde, NOWCAST_AUSNAHMEN)
    assert not verstoesse, (
        "get_nowcast()-Aufruf ohne elevation_m=-Schluesselwort (Issue "
        "#1991). Entweder Hoehe durchreichen oder mit Begruendung in "
        f"NOWCAST_AUSNAHMEN eintragen — Code reference: {sorted(verstoesse.items())}"
    )


def test_jede_location_konstruktion_traegt_elevation_keyword():
    """GIVEN den Produktivcode unter src/ und api/
    WHEN eine Stelle `Location(...)` konstruiert
    THEN traegt die Konstruktion ein `elevation_m=`-Schluesselwort — oder
    steht namentlich mit Begruendung in LOCATION_AUSNAHMEN.
    """
    _, location_funde = _alle_funde()
    verstoesse = _ohne_ausnahmen(location_funde, LOCATION_AUSNAHMEN)
    assert not verstoesse, (
        "Location(...)-Konstruktion ohne elevation_m=-Schluesselwort (Issue "
        "#1991). Entweder Hoehe durchreichen oder mit Begruendung in "
        f"LOCATION_AUSNAHMEN eintragen — Code reference: {sorted(verstoesse.items())}"
    )


def test_jede_eingetragene_ausnahme_existiert_noch():
    """Shrink-Schutz: eine Ausnahme, die im Code nicht mehr vorkommt, ist
    veraltet und muss raus — sonst waechst die Liste zu einem Friedhof, in
    dem eine echte neue Ausnahme nicht mehr auffaellt."""
    nowcast_funde, location_funde = _alle_funde()
    nowcast_vorhanden = {k.rsplit("::", 1)[0] for k in nowcast_funde}
    location_vorhanden = {k.rsplit("::", 1)[0] for k in location_funde}
    veraltet = sorted(
        (set(NOWCAST_AUSNAHMEN) - nowcast_vorhanden)
        | (set(LOCATION_AUSNAHMEN) - location_vorhanden)
    )
    assert not veraltet, (
        f"Veraltete Eintraege in NOWCAST_AUSNAHMEN/LOCATION_AUSNAHMEN: "
        f"{veraltet} — die Aufrufstelle gibt es nicht mehr oder sie traegt "
        "das Schluesselwort bereits. Eintrag entfernen."
    )


def test_jede_ausnahme_traegt_eine_begruendung():
    """Eine Ausnahme ohne Begruendung ist eine Ausrede."""
    ohne = sorted(
        k for k, v in {**NOWCAST_AUSNAHMEN, **LOCATION_AUSNAHMEN}.items()
        if len(v.strip()) < 40
    )
    assert not ohne, f"Ausnahmen ohne tragfaehige Begruendung: {ohne}"


# --- Wirkungsnachweise: faengt der Scanner ueberhaupt etwas? ---------------


def test_scanner_erkennt_get_nowcast_ohne_elevation_in_synthetischer_datei(tmp_path):
    datei = tmp_path / "synthetischer_aufrufer_nowcast_ohne_hoehe.py"
    datei.write_text(
        "def hole(svc, lat, lon):\n"
        "    return svc.get_nowcast(lat, lon, priority='polling')\n",
        encoding="utf-8",
    )
    nowcast_funde, location_funde = _funde(datei)
    assert nowcast_funde, f"Scanner hat den Aufruf ohne elevation_m nicht erkannt: {nowcast_funde}"
    assert not location_funde


def test_scanner_erkennt_get_nowcast_mit_elevation_nicht_als_verstoss(tmp_path):
    datei = tmp_path / "synthetischer_aufrufer_nowcast_mit_hoehe.py"
    datei.write_text(
        "def hole(svc, lat, lon, elevation_m):\n"
        "    return svc.get_nowcast(lat, lon, elevation_m=elevation_m, priority='polling')\n",
        encoding="utf-8",
    )
    nowcast_funde, _ = _funde(datei)
    assert not nowcast_funde, (
        f"Aufruf MIT elevation_m faelschlich als Verstoss gezaehlt: {nowcast_funde}"
    )


def test_scanner_erkennt_location_ohne_elevation_in_synthetischer_datei(tmp_path):
    datei = tmp_path / "synthetischer_aufrufer_location_ohne_hoehe.py"
    datei.write_text(
        "from app.config import Location\n"
        "def hole(lat, lon):\n"
        "    return Location(latitude=lat, longitude=lon)\n",
        encoding="utf-8",
    )
    _, location_funde = _funde(datei)
    assert location_funde, (
        f"Scanner hat die Location-Konstruktion ohne elevation_m nicht erkannt: {location_funde}"
    )


def test_scanner_erkennt_location_mit_elevation_nicht_als_verstoss(tmp_path):
    datei = tmp_path / "synthetischer_aufrufer_location_mit_hoehe.py"
    datei.write_text(
        "from app.config import Location\n"
        "def hole(lat, lon, elevation_m):\n"
        "    return Location(latitude=lat, longitude=lon, elevation_m=elevation_m)\n",
        encoding="utf-8",
    )
    _, location_funde = _funde(datei)
    assert not location_funde, (
        f"Location-Konstruktion MIT elevation_m faelschlich als Verstoss gezaehlt: {location_funde}"
    )


def test_scanner_verwechselt_andere_location_klassen_nicht(tmp_path):
    """`_FixtureLocation(...)` (und andere *Location-Klassen mit anderem
    Namen) sind NICHT die geprueften `app.config.Location` -- der Scanner
    darf sie nicht als Verstoss zaehlen."""
    datei = tmp_path / "synthetischer_aufrufer_andere_klasse.py"
    datei.write_text(
        "def hole(lat, lon):\n"
        "    return _FixtureLocation('Test', lat, lon, 'test.json')\n",
        encoding="utf-8",
    )
    _, location_funde = _funde(datei)
    assert not location_funde, (
        f"_FixtureLocation faelschlich als Location-Verstoss gezaehlt: {location_funde}"
    )
