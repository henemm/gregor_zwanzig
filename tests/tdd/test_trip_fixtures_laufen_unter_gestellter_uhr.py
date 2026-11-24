"""Ratsche (#2242): ``make_trip()``+``save_trip()`` ohne gestellte Uhr in
derselben Funktion. Regel-Budget-Pruefdatum EXPIRY = 2026-12-08 (+90 Tage).

ROOT CAUSE (#2050): ``app.loader.save_trip()`` verwirft per Compute-on-Save
das Ganztags-Fenster aus ``make_trip()``; ausserdem rechnet ``make_trip()``
das Etappendatum ueber ``date.today()`` relativ zur Wanduhr — ein Aufruf
nahe Mitternacht UTC kann Bau und Pruefung auf verschiedene Kalendertage
legen (dreimal in drei Wochen ungeschuetzt gefunden, s.
``test_issue_1088_official_alert_triggers.py``, dort behoben).

BESTAND (beim Einfuehren gemessen): 12 vorbestehende Fundstellen ausserhalb
des #2242-Scopes stehen als ``KNOWN_VIOLATIONS`` (Nachtrag #1199); ab hier
blockt die Ratsche nur NEUE. GRENZEN: rein syntaktisch, funktionslokal,
Aufrufketten unverfolgt.
"""
from __future__ import annotations

import ast
import functools
from datetime import date
from pathlib import Path

import pytest

from tests.helpers.bezeichner_vorfilter import quelltext_mit_bezeichnern

# Der Ergebnis-Cache wirkt nur je Prozess, also ein Worker fuer die Datei (#3279).
pytestmark = pytest.mark.xdist_group("gestellte_uhr_ratsche")

REPO_ROOT = Path(__file__).resolve().parents[2]
TESTS_ROOT = REPO_ROOT / "tests"
EXPIRY = date(2026, 12, 8)

# Datei -> Funktionsnamen (spart Wiederholung des Pfads gegenueber Tupeln).
_KNOWN_BY_FILE = {
    "tests/tdd/test_alert_suppression_reason.py": ["test_ac4_doppel_alarm_guard_wird_protokolliert_und_deutsch_beschriftet"],
    "tests/tdd/test_nowcast_suppression_logging.py": ["_run_trip", "test_f004_gescheitertes_protokoll_stoppt_den_trip_lauf_nicht"],
    "tests/tdd/test_onset_ende_kanalparitaet.py": ["_text_vom_trip_pfad"],
    "tests/tdd/test_onset_reichweite_guete_kanalparitaet.py": ["_text_vom_trip_pfad"],
    "tests/tdd/test_ruhezeit_und_zaehler_folgen_der_ortszone.py": ["trip_mit_ruhezeit", "test_ac3_stelle5_nowcast_schranke", "trip_zwei_zonen", "lauf"],
    "tests/tdd/test_trip_radar_nowcast_gate_migration.py": ["_run_trip_scenario"],
}
KNOWN_VIOLATIONS = {(d, f) for d, fs in _KNOWN_BY_FILE.items() for f in fs}

def _ist_aufruf(knoten: ast.AST, name: str) -> bool:
    if not isinstance(knoten, ast.Call):
        return False
    ziel = knoten.func
    if isinstance(ziel, ast.Name):
        return ziel.id == name
    return isinstance(ziel, ast.Attribute) and ziel.attr == name

def _hat_freeze_dekorator(func: ast.AST) -> bool:
    return any(
        _ist_aufruf(dek, "freeze_time")
        or (isinstance(dek, ast.Attribute) and dek.attr == "freeze_time")
        or (isinstance(dek, ast.Name) and dek.id == "freeze_time")
        for dek in func.decorator_list
    )

def _erste_ungeschuetzte_save_trip_zeile(func: ast.AST) -> int | None:
    treffer: list[int] = []

    def besuche(knoten: ast.AST, geschuetzt: bool) -> None:
        wird = geschuetzt or (isinstance(knoten, ast.With) and any(
            _ist_aufruf(i.context_expr, "frozen_active_window")
            or _ist_aufruf(i.context_expr, "freeze_time")
            for i in knoten.items
        ))
        if _ist_aufruf(knoten, "save_trip") and not wird:
            treffer.append(knoten.lineno)
        for kind in ast.iter_child_nodes(knoten):
            besuche(kind, wird)

    besuche(func, False)
    return treffer[0] if treffer else None

def scan_ungestellte_uhr(tests_root: Path) -> list[tuple[Path, str, int]]:
    """Jede Funktion, die ``make_trip()`` UND einen ungeschuetzten
    ``save_trip()`` kombiniert."""
    funde: list[tuple[Path, str, int]] = []
    for datei in sorted(tests_root.rglob("*.py")):
        try:
            quelltext = quelltext_mit_bezeichnern(datei, alle=("make_trip", "save_trip"))
            if quelltext is None:
                continue
            baum = ast.parse(quelltext)
        except (SyntaxError, UnicodeDecodeError):
            continue
        for func in ast.walk(baum):
            if not isinstance(func, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            if _hat_freeze_dekorator(func):
                continue
            if not any(_ist_aufruf(n, "make_trip") for n in ast.walk(func)):
                continue
            zeile = _erste_ungeschuetzte_save_trip_zeile(func)
            if zeile is not None:
                funde.append((datei, func.name, zeile))
    return funde

@functools.cache
def _echtbaum() -> tuple[tuple[Path, str, int], ...]:
    """Ein Scan des echten Baums je Prozess (#3279); Tupel, damit kein
    Aufrufer den Cache veraendert. ``tmp_path``-Laeufe scannen direkt."""
    return tuple(scan_ungestellte_uhr(TESTS_ROOT))

def funde_echtbaum() -> list[tuple[Path, str, int]]:
    return list(_echtbaum())

def _relativ(pfad: Path) -> str:
    return str(pfad.relative_to(REPO_ROOT))

def test_bestand_liefert_keine_neuen_funde():
    funde = funde_echtbaum()
    neu = [(p, f, z) for p, f, z in funde if (_relativ(p), f) not in KNOWN_VIOLATIONS]
    zeilen = "\n".join(f"  - {_relativ(p)}:{z} in {f}()" for p, f, z in neu)
    assert not neu, (
        f"{len(neu)} NEUE Fundstelle(n) kombinieren make_trip()+save_trip() "
        f"ohne gestellte Uhr (#2242/#2050):\n{zeilen}\n\n"
        f"Abhilfe: with frozen_active_window(): um Bau, Speichern UND Pruefung."
    )

def test_known_violations_enthaelt_keine_veralteten_eintraege():
    aktuell = {(_relativ(p), f) for p, f, _ in funde_echtbaum()}
    veraltet = sorted(KNOWN_VIOLATIONS - aktuell)
    assert not veraltet, f"Veraltete Ausnahmen entfernen: {veraltet}"

_BAU = "trip = make_trip('t'); save_trip(trip, 'uid')"
_ROH = f"def test_x():\n    {_BAU}\n"
_MIT_HELFER = f"def test_x():\n    with frozen_active_window(): {_BAU}\n"
_MIT_FREEZE = f"def test_x():\n    with freeze_time('2026-01-01'): {_BAU}\n"
_MIT_DEKORATOR = f"@freeze_time('2026-01-01')\ndef test_x():\n    {_BAU}\n"

def test_scanner_meldet_das_antimuster(tmp_path):
    (tmp_path / "test_attrappe.py").write_text(_ROH, encoding="utf-8")
    assert [f for _, f, _ in scan_ungestellte_uhr(tmp_path)] == ["test_x"]

@pytest.mark.parametrize("code", [_MIT_HELFER, _MIT_FREEZE, _MIT_DEKORATOR])
def test_scanner_schweigt_wenn_geschuetzt(tmp_path, code):
    (tmp_path / "test_attrappe.py").write_text(code, encoding="utf-8")
    assert scan_ungestellte_uhr(tmp_path) == []

def test_regel_budget_pruefdatum_steht_als_text_in_der_datei():
    assert EXPIRY == date(2026, 12, 8)
    assert EXPIRY.isoformat() in Path(__file__).read_text(encoding="utf-8")

@pytest.mark.parametrize("alt, neu", [
    ("make_trip", "ｍａｋｅ_trip"), ("save_trip", "ｓａｖｅ_trip")])
def test_vorfilter_des_scanner_findet_nfkc_und_parst_nur_kandidaten(
    tmp_path, monkeypatch, alt, neu,
):
    """#3279 AC-3: Fullwidth-Bezeichner sind fuer Python derselbe Name."""
    text = _ROH.replace(alt, neu)
    (tmp_path / "test_attrappe.py").write_text(text, encoding="utf-8")
    (tmp_path / "test_unbeteiligt.py").write_text("make_trip('t')\n", encoding="utf-8")
    geparst: list[str] = []
    parse = ast.parse
    monkeypatch.setattr(ast, "parse", lambda q, *a, **k: (geparst.append(q), parse(q, *a, **k))[1])
    assert [f for _, f, _ in scan_ungestellte_uhr(tmp_path)] == ["test_x"]
    assert geparst == [text]

def test_vorfilter_des_scanner_braucht_auch_make_trip(tmp_path, monkeypatch):
    (tmp_path / "test_nur_save.py").write_text("save_trip('t')\n", encoding="utf-8")
    monkeypatch.setattr(ast, "parse", lambda *a, **k: pytest.fail("unbeteiligte Datei geparst"))
    assert scan_ungestellte_uhr(tmp_path) == []

@pytest.mark.parametrize("inhalt", [
    b"make_trip = save_trip(\n", b"# make_trip save_trip \xff\n"], ids=["syntax", "utf8"])
def test_scanner_ueberspringt_kaputte_kandidaten(tmp_path, inhalt):
    (tmp_path / "test_kaputt.py").write_bytes(inhalt)
    assert scan_ungestellte_uhr(tmp_path) == []

def test_echtbaum_cache_scannt_nur_einmal(tmp_path, monkeypatch):
    """#3279 AC-5: ein Scan, frische Liste je Aufruf, ``tmp_path`` ungecacht."""
    datei, scan = tmp_path / "test_attrappe.py", scan_ungestellte_uhr
    datei.write_text(_ROH, encoding="utf-8")
    erwartet = scan(tmp_path)
    assert erwartet
    aufrufe: list[Path] = []
    with monkeypatch.context() as m:
        m.setitem(globals(), "TESTS_ROOT", tmp_path)
        m.setitem(globals(), "_echtbaum", functools.cache(_echtbaum.__wrapped__))
        m.setitem(globals(), "scan_ungestellte_uhr", lambda w: (aufrufe.append(w), scan(w))[1])
        erste = funde_echtbaum()
        erste.append("fremd")
        assert funde_echtbaum() == erwartet
        assert aufrufe == [tmp_path]
    datei.write_text(_MIT_HELFER, encoding="utf-8")
    assert scan(tmp_path) == []

def test_echtbaum_pruefungen_nutzen_den_cache(monkeypatch):
    """#3279 AC-5: ist der Baum einmal gescannt, scannt keine Pruefung neu."""
    funde_echtbaum()

    def kein_neuer_scan(wurzel):
        raise AssertionError(f"neuer Baumlauf ueber {wurzel} statt Cache")

    monkeypatch.setitem(globals(), "scan_ungestellte_uhr", kein_neuer_scan)
    test_bestand_liefert_keine_neuen_funde()
    test_known_violations_enthaelt_keine_veralteten_eintraege()
