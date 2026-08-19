"""Issue #1468 — Waechter: jede PRODUKTIVE Aufrufstelle von
`compute_basis_metrics()` uebergibt eine ECHTE Zeitzone.

Warum es diesen Waechter gibt (Adversary-Runde 1, F001-Nachspiel):

Der Fix zu F001 hat die eine Bugklasse beseitigt -- `tz` ist Pflicht, der
stille Rueckfall `zone = tz or timezone.utc` ist weg. An seine Stelle trat
ABSTAIN: `tz is None` heisst "kein Ortsbezug", die Beginn-Felder bleiben
leer. Das ist fuer die Zeitzonen-Frage richtig, tauscht aber ein Risiko
gegen ein anderes aus DERSELBEN Familie:

    Vorher haette ein vergessener Ortsbezug eine FALSCHE Uhrzeit ergeben.
    Jetzt ergibt er GAR KEINE -- und damit nie einen Beginn-Alarm.

Beides still. Und die Spec-Invariante aus `rework_1467_s2_aenderungsalarm.md`
nennt ausdruecklich den ausbleibenden Alarm als den gefaehrlicheren Fehler.
Der Zeitzonen-Waechter (`test_output_timezone_guard.py`) faengt das NICHT: er
prueft Signatur-Defaults und rohe `.astimezone()`-Aufrufe, nicht den WERT an
der Aufrufstelle.

Dieser Waechter schliesst genau diese Luecke: er liest den Produktivcode
(`src/`, `api/`) statisch und verlangt an jeder Aufrufstelle ein `tz=`, das
nicht die Konstante `None` ist. Tests sind ausgenommen -- sie sind kein
Produktionspfad (dieselbe Grenze wie in
`test_output_timezone_guard.test_production_callsites_pass_tz_explicitly`).

Statische AST-Analyse: kein Netz, kein Mock, keine Marker -- Kern-Schicht.
"""
from __future__ import annotations

import ast
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SRC = REPO_ROOT / "src"
API = REPO_ROOT / "api"

# Die beobachtete Funktion. Bewusst NUR diese: sie ist die einzige, deren
# `tz`-Wert ueber "Beginn-Alarm oder Stille" entscheidet.
GUARDED = "compute_basis_metrics"

_MODULE_SCOPE = "<module>"

# Benannte, BEWUSSTE Ausnahme. Schluessel: "<pfad>::<funktion>".
#
# `summarize_points()` ist der Compare-ANZEIGE-Helfer: er bekommt eine reine
# Stundenpunkt-Liste ohne Ort, also gibt es dort keine Ortszeit. `tz=None`
# ist die ehrliche Aussage "kein Ortsbezug" statt einer erfundenen Zone. Der
# Compare-ALARM-Pfad laeuft NICHT hier durch, sondern ueber
# `SegmentWeatherService._aggregate_for_segment()`, wo die Zone aus den
# Segment-Koordinaten kommt -- bewacht von
# `tests/tdd/test_onset_compare_day_window.py`.
BEWUSSTE_ABSTAIN_AUFRUFER: dict[str, str] = {
    "src/services/weather_metrics.py::summarize_points": (
        "Compare-Anzeige ohne Ortsbezug: reine Stundenpunkte, kein Ort -> "
        "keine Ortszeit und damit ausdruecklich keine Beginn-Aussage. Der "
        "Compare-ALARM-Pfad geht ueber _aggregate_for_segment() mit echter "
        "Zone."
    ),
}


def _scan_files() -> list[Path]:
    return sorted(
        p for p in [*SRC.rglob("*.py"), *API.rglob("*.py")] if p.exists()
    )


def _scopes(tree: ast.AST) -> dict[int, str]:
    """Knoten -> Name der umgebenden Funktion (sonst ``<module>``).

    Woertlich dasselbe Vorgehen wie in ``test_output_timezone_guard.py``:
    die Suche laeuft flach ueber ``ast.walk``, der Funktionsname wird
    nachtraeglich angehaengt -- so kann die Zuordnung keine Fundstelle
    verlieren.
    """
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


def _ist_none(knoten: ast.AST) -> bool:
    return isinstance(knoten, ast.Constant) and knoten.value is None


def _funde(pfad: Path) -> dict[str, str]:
    """Aufrufstellen von ``compute_basis_metrics`` mit fehlendem oder
    ``None``-wertigem ``tz`` -> {"<pfad>::<funktion>::<zeile>": Grund}."""
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
        if not isinstance(knoten, ast.Call):
            continue
        name = (
            knoten.func.attr if isinstance(knoten.func, ast.Attribute)
            else knoten.func.id if isinstance(knoten.func, ast.Name)
            else None
        )
        if name != GUARDED:
            continue
        tz_arg = next(
            (kw.value for kw in knoten.keywords if kw.arg == "tz"), None
        )
        if any(kw.arg is None for kw in knoten.keywords) and tz_arg is None:
            continue  # `**kwargs`-Weiterreichung: der Wert steht woanders
        if tz_arg is None:
            grund = "callsite_ohne_tz"
        elif _ist_none(tz_arg):
            grund = "callsite_tz_none"
        else:
            continue
        schluessel = f"{rel}::{raum.get(id(knoten), _MODULE_SCOPE)}"
        treffer[f"{schluessel}::{knoten.lineno}"] = grund
    return treffer


def _alle_funde() -> dict[str, str]:
    gesamt: dict[str, str] = {}
    for pfad in _scan_files():
        gesamt.update(_funde(pfad))
    return gesamt


def _ohne_ausnahmen(funde: dict[str, str]) -> dict[str, str]:
    return {
        k: v for k, v in funde.items()
        if k.rsplit("::", 1)[0] not in BEWUSSTE_ABSTAIN_AUFRUFER
    }


# ---------------------------------------------------------------------------


def test_produktive_aufrufer_uebergeben_eine_echte_zeitzone():
    """GIVEN den Produktivcode unter src/ und api/
    WHEN eine Stelle `compute_basis_metrics()` ruft
    THEN uebergibt sie ein `tz=`, das nicht `None` ist -- ausser sie steht
    namentlich in BEWUSSTE_ABSTAIN_AUFRUFER.

    Ein `tz=None` ausserhalb dieser Liste heisst: dieser Pfad berechnet
    dauerhaft keinen Ereignis-Beginn und kann deshalb NIE einen
    Beginn-Alarm ausloesen -- ein stiller Alarmausfall, kein sichtbarer
    Fehler.
    """
    verstoesse = _ohne_ausnahmen(_alle_funde())
    assert not verstoesse, (
        "Produktivcode ruft compute_basis_metrics() ohne echte Zeitzone auf "
        "(Issue #1468). Diese Pfade berechnen dauerhaft keinen Beginn und "
        "loesen nie einen Beginn-Alarm aus. Entweder eine echte Zone "
        "uebergeben oder die Stelle mit Begruendung in "
        f"BEWUSSTE_ABSTAIN_AUFRUFER eintragen — Code reference: "
        f"{sorted(verstoesse.items())}"
    )


def test_jede_eingetragene_ausnahme_existiert_noch():
    """Shrink-Schutz: eine Ausnahme, die im Code nicht mehr vorkommt, ist
    veraltet und muss raus -- sonst waechst die Liste zu einem Friedhof, in
    dem eine echte neue Ausnahme nicht mehr auffaellt."""
    vorhanden = {k.rsplit("::", 1)[0] for k in _alle_funde()}
    veraltet = sorted(set(BEWUSSTE_ABSTAIN_AUFRUFER) - vorhanden)
    assert not veraltet, (
        f"Veraltete Eintraege in BEWUSSTE_ABSTAIN_AUFRUFER: {veraltet} — "
        "die Aufrufstelle gibt es nicht mehr oder sie uebergibt inzwischen "
        "eine echte Zone. Eintrag entfernen."
    )


def test_jede_ausnahme_traegt_eine_begruendung():
    """Eine Ausnahme ohne Begruendung ist eine Ausrede."""
    ohne = sorted(
        k for k, v in BEWUSSTE_ABSTAIN_AUFRUFER.items() if len(v.strip()) < 40
    )
    assert not ohne, f"Ausnahmen ohne tragfaehige Begruendung: {ohne}"


# --- Wirkungsnachweise: faengt der Scanner ueberhaupt etwas? ---------------

def test_scanner_erkennt_tz_none_in_synthetischer_produktivdatei(tmp_path):
    """Ohne diesen Nachweis koennte der Waechter aus einem Pfad-, Parser-
    oder Namensfehler leer laufen und waere ein zahnloses Protokoll."""
    datei = tmp_path / "synthetischer_aufrufer.py"
    datei.write_text(
        "def hole():\n"
        "    return dienst.compute_basis_metrics(reihe, tz=None)\n",
        encoding="utf-8",
    )
    funde = _funde(datei)
    assert any(v == "callsite_tz_none" for v in funde.values()), (
        f"Scanner hat den tz=None-Aufruf nicht erkannt: {funde}"
    )


def test_scanner_erkennt_fehlendes_tz_in_synthetischer_produktivdatei(tmp_path):
    datei = tmp_path / "synthetischer_aufrufer_ohne.py"
    datei.write_text(
        "def hole():\n"
        "    return dienst.compute_basis_metrics(reihe)\n",
        encoding="utf-8",
    )
    funde = _funde(datei)
    assert any(v == "callsite_ohne_tz" for v in funde.values()), (
        f"Scanner hat den Aufruf ohne tz= nicht erkannt: {funde}"
    )


def test_scanner_meldet_einen_aufruf_mit_echter_zone_nicht(tmp_path):
    """Gegenprobe: sonst waere der Waechter auch nach korrekter Uebergabe
    nie gruen zu bekommen und wuerde zwangslaeufig entschaerft."""
    datei = tmp_path / "synthetischer_aufrufer_ok.py"
    datei.write_text(
        "def hole():\n"
        "    return dienst.compute_basis_metrics(reihe, tz=orts_zone)\n",
        encoding="utf-8",
    )
    assert not _funde(datei), (
        f"Aufruf MIT echter Zone faelschlich als Verstoss gezaehlt: {_funde(datei)}"
    )


def test_scanner_findet_die_echte_aufrufstelle_im_alarmpfad():
    """Positivkontrolle am ECHTEN Code: der Alarm-/Briefing-Pfad
    (`segment_weather._aggregate_for_segment`) ruft mit echter Zone und darf
    deshalb NICHT als Verstoss auftauchen -- er muss aber ueberhaupt
    gefunden werden, sonst prueft dieser Waechter eine leere Menge.
    """
    quelle = (SRC / "services" / "segment_weather.py").read_text(encoding="utf-8")
    assert f"{GUARDED}(" in quelle, (
        "segment_weather.py ruft compute_basis_metrics() nicht mehr — dieser "
        "Waechter beobachtet dann womoeglich eine leere Menge."
    )
    assert not _funde(SRC / "services" / "segment_weather.py"), (
        "Der Alarm-/Briefing-Pfad uebergibt keine echte Zone: "
        f"{_funde(SRC / 'services' / 'segment_weather.py')}"
    )
