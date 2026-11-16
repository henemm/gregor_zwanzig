"""Waechter der Fallliste "Einstellung = Mail" (Issue #3047, Arbeitspaket E, AC-1).

SPEC: docs/specs/modules/feat_3047_einstellung_gleich_mail_pruefkatalog.md (§2, §3, §4, AC-1)

Liest die vier Teildateien ``tests/fixtures/einstellung_gleich_mail/fallliste_*.json``
und prueft ohne Testausfuehrung:

(a) Abdeckungsmatrix Liste x Format je Pruefung ``auswahl`` und ``reihenfolge``;
(b) jeder Fall -- auch ``ausnahme`` und ``offen_feature`` (#3047 J2) -- nennt
    eine auffindbare Testfunktion (Python per ``ast``, Vitest per Titelsuche,
    Go per ``func <Name>(`` in ``internal/**/*_test.go`` bei ``seite: "go"``);
(c) paarweise Ueberdeckung der ``dimensionen`` je Liste;
(d) "fertig": kein Fall ``rot_erwartet``; ``ausnahme``/``offen_feature`` tragen Verweis;
(e) Schema: Pflichtfelder, erlaubte Status/Formate, ``id`` global eindeutig.

Die Pruefungen sind reine Funktionen mit Pfadparametern; die Selbsttests am Dateiende
fuettern sie mit synthetischen Falllisten in ``tmp_path`` (positiv und negativ).
Kein Mock.
"""
from __future__ import annotations

import ast
import itertools
import json
import re
from collections import Counter
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
FALLLISTEN_DIR = REPO_ROOT / "tests" / "fixtures" / "einstellung_gleich_mail"
TEILDATEIEN = ("trip", "orte", "validatoren", "editor")

PFLICHTFELDER = ("id", "liste", "kontext", "format", "pruefung", "test", "ac", "befund", "status")
ERLAUBTE_STATUS = frozenset({"gruen", "rot_erwartet", "ausnahme", "offen_feature"})
ERLAUBTE_FORMATE = frozenset({"html", "klartext", "kompakt", "editor"})
#: #3047 J2: jeder Status nennt einen auffindbaren Test -- ein ``offen_feature``
#: belegt sich mit ``xfail(strict=True)`` rot, eine ``ausnahme`` mit dem Test,
#: der die gewollte Abweichung zeigt.
STATUS_MIT_TEST = ERLAUBTE_STATUS
STATUS_MIT_VERWEIS = frozenset({"ausnahme", "offen_feature"})
META_SCHLUESSEL = frozenset({"ausgeschlossen", "hinweis"})
VERWEIS_MUSTER = re.compile(r"#\d+|ADR-\d+|\bWV?\d+\b")

# Abdeckungsmatrix (Spec §2): Liste -> Formate; je Kombination auswahl UND reihenfolge.
ABDECKUNG_SOLL: dict[str, tuple[str, ...]] = {
    "trip_stundentabelle": ("html", "klartext", "kompakt"),
    "trip_nachttabelle": ("html", "klartext", "kompakt"),
    "trip_ausblick": ("html", "klartext", "kompakt"),
    "orte_vergleichstabelle": ("html", "klartext"),
    "orte_stundenverlauf": ("html", "klartext"),
    "orte_ausblick": ("html", "klartext"),
}
ABDECKUNG_PRUEFUNGEN = ("auswahl", "reihenfolge")

PY_TEST_GLOB = "tests/tdd/test_einstellung_gleich_mail_*.py"
VITEST_GLOB = "frontend/src/**/__tests__/*.test.ts"
GO_TEST_GLOB = "internal/**/*_test.go"


# ---------------------------------------------------------------------------
# Laden
# ---------------------------------------------------------------------------


class FalllisteFehler(Exception):
    """Teildatei fehlt oder ist kein gueltiges JSON-Objekt."""


def lade_falllisten(verzeichnis: Path, teile: tuple[str, ...] = TEILDATEIEN) -> dict[str, dict]:
    """Liest alle Teildateien; fehlende/kaputte Dateien -> FalllisteFehler (kein Skip)."""
    fehler: list[str] = []
    daten: dict[str, dict] = {}
    for teil in teile:
        pfad = verzeichnis / f"fallliste_{teil}.json"
        if not pfad.is_file():
            fehler.append(f"Teildatei fehlt: {pfad}")
            continue
        try:
            inhalt = json.loads(pfad.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            fehler.append(f"{pfad.name}: kein gueltiges JSON ({exc})")
            continue
        if not isinstance(inhalt, dict) or not isinstance(inhalt.get("faelle"), list):
            fehler.append(f"{pfad.name}: erwartet Objekt mit Liste 'faelle'")
            continue
        daten[pfad.name] = inhalt
    if fehler:
        raise FalllisteFehler("Fallliste unvollstaendig:\n  " + "\n  ".join(fehler))
    return daten


def _alle_faelle(dateien: dict[str, dict]):
    for name, inhalt in dateien.items():
        for fall in inhalt.get("faelle", []):
            if isinstance(fall, dict):
                yield name, fall


# ---------------------------------------------------------------------------
# (a) Abdeckungsmatrix
# ---------------------------------------------------------------------------


def pruefe_abdeckung(dateien: dict[str, dict]) -> list[str]:
    vorhanden = {
        (f.get("liste"), f.get("format"), f.get("pruefung")) for _, f in _alle_faelle(dateien)
    }
    fehlend = []
    for liste, formate in ABDECKUNG_SOLL.items():
        for fmt in formate:
            for pruefung in ABDECKUNG_PRUEFUNGEN:
                if (liste, fmt, pruefung) not in vorhanden:
                    fehlend.append(f"kein Fall fuer liste={liste}, format={fmt}, pruefung={pruefung}")
    return fehlend


# ---------------------------------------------------------------------------
# (b) Testverweise
# ---------------------------------------------------------------------------


def _python_testnamen(datei: Path) -> set[str]:
    """Funktionsnamen und Klasse::methode (plus bare Methodennamen) einer Datei."""
    baum = ast.parse(datei.read_text(encoding="utf-8"), filename=str(datei))
    namen: set[str] = set()
    for knoten in baum.body:
        if isinstance(knoten, (ast.FunctionDef, ast.AsyncFunctionDef)):
            namen.add(knoten.name)
        elif isinstance(knoten, ast.ClassDef):
            for kind in knoten.body:
                if isinstance(kind, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    namen.add(kind.name)
                    namen.add(f"{knoten.name}::{kind.name}")
    return namen


#: Testaufrufe im Frontend: Vitest (``it``/``test``/``it.fails``) und
#: ``node --test`` mit dem Helfer ``rotErwartet`` (#3047 Paket D).
_VITEST_AUFRUF = r"\b(?:it|test|it\.fails|rotErwartet)\s*\(\s*"
#: Template-Literal-Titel: der feste Text vor dem ersten ``${`` (z. B.
#: ``test(`Grundname ${z.id}`)`` -> ``Grundname``).
_VITEST_TEMPLATE_PRAEFIX = re.compile(_VITEST_AUFRUF + r"`([^`$]*)\$\{")


def _vitest_titel_gefunden(titel: str, dateien: list[Path]) -> bool:
    muster = re.compile(_VITEST_AUFRUF + r"(['\"`])" + re.escape(titel) + r"\1")
    for d in dateien:
        quelle = d.read_text(encoding="utf-8")
        if muster.search(quelle):
            return True
        praefixe = {p.strip() for p in _VITEST_TEMPLATE_PRAEFIX.findall(quelle)}
        if titel.strip() and titel.strip() in praefixe:
            return True
    return False


def _ist_vitest_fall(fall: dict) -> bool:
    return fall.get("seite") == "frontend" or ".test.ts::" in str(fall.get("test", ""))


def _pruefe_vitest_verweis(test: str, vitest_dateien: list[Path]) -> bool:
    if ".test.ts::" in test:
        datei_teil, titel = test.split(".test.ts::", 1)
        datei_name = Path(datei_teil + ".test.ts").name
        kandidaten = [d for d in vitest_dateien if d.name == datei_name]
    else:
        titel, kandidaten = test, vitest_dateien
    return bool(titel) and _vitest_titel_gefunden(titel, kandidaten)


def _pruefe_go_verweis(test: str, go_dateien: list[Path]) -> bool:
    """Go-Testfunktion ``func <Name>(`` (``seite: "go"``) in ``internal/**/*_test.go``."""
    if not re.fullmatch(r"Test\w+", test):
        return False
    muster = re.compile(r"^func\s+" + re.escape(test) + r"\s*\(", re.MULTILINE)
    return any(muster.search(d.read_text(encoding="utf-8")) for d in go_dateien)


def _pruefe_python_verweis(test: str, py_namen: dict[str, set[str]]) -> bool:
    if ".py::" in test:
        datei_teil, name = test.split(".py::", 1)
        datei_name = Path(datei_teil + ".py").name
        return name in py_namen.get(datei_name, set())
    return any(test in namen for namen in py_namen.values())


def pruefe_testverweise(dateien: dict[str, dict], wurzel: Path) -> list[str]:
    py_namen = {p.name: _python_testnamen(p) for p in sorted(wurzel.glob(PY_TEST_GLOB))}
    vitest_dateien = sorted(wurzel.glob(VITEST_GLOB))
    go_dateien = sorted(wurzel.glob(GO_TEST_GLOB))
    fehler = []
    for name, fall in _alle_faelle(dateien):
        if fall.get("status") not in STATUS_MIT_TEST:
            continue
        test = str(fall.get("test") or "").strip()
        if fall.get("seite") == "go":
            ok = _pruefe_go_verweis(test, go_dateien)
            ort = GO_TEST_GLOB
        elif _ist_vitest_fall(fall):
            ok = _pruefe_vitest_verweis(test, vitest_dateien)
            ort = VITEST_GLOB
        else:
            ok = bool(test) and _pruefe_python_verweis(test, py_namen)
            ort = PY_TEST_GLOB
        if not ok:
            fehler.append(f"{name}: Fall {fall.get('id')!r} nennt Test {test!r}, nicht gefunden in {ort}")
    return fehler


# ---------------------------------------------------------------------------
# (c) Paarweise Ueberdeckung
# ---------------------------------------------------------------------------


def _ist_ausgeschlossen(ausgeschlossen: list, liste: str, a: str, wa, b: str, wb) -> bool:
    for eintrag in ausgeschlossen:
        if not isinstance(eintrag, list):
            continue
        if len(eintrag) == 5:
            if eintrag[0] != liste:
                continue
            eintrag = eintrag[1:]
        if len(eintrag) != 4:
            continue
        if eintrag == [a, wa, b, wb] or eintrag == [b, wb, a, wa]:
            return True
    return False


def _wert(fall: dict, dim: str):
    werte = fall.get("werte") or {}
    return werte[dim] if dim in werte else fall.get(dim)


def pruefe_paarweise(dateien: dict[str, dict]) -> list[str]:
    fehler = []
    for name, inhalt in dateien.items():
        dims_obj = inhalt.get("dimensionen") or {}
        dims = {k: v for k, v in dims_obj.items() if k not in META_SCHLUESSEL and isinstance(v, list)}
        if len(dims) < 2:
            continue
        ausgeschlossen = dims_obj.get("ausgeschlossen") or []
        nach_liste: dict[str, list[dict]] = {}
        for fall in inhalt.get("faelle", []):
            if isinstance(fall, dict) and fall.get("werte"):
                nach_liste.setdefault(fall.get("liste"), []).append(fall)
        for liste, faelle in sorted(nach_liste.items(), key=lambda kv: str(kv[0])):
            for a, b in itertools.combinations(dims, 2):
                gesehen = {(_wert(f, a), _wert(f, b)) for f in faelle}
                for wa, wb in itertools.product(dims[a], dims[b]):
                    if (wa, wb) in gesehen or _ist_ausgeschlossen(ausgeschlossen, liste, a, wa, b, wb):
                        continue
                    fehler.append(f"{name}: liste={liste}: Paar {a}={wa!r} x {b}={wb!r} nicht abgedeckt")
    return fehler


# ---------------------------------------------------------------------------
# (d) Fertig
# ---------------------------------------------------------------------------


def finde_rot_erwartet(dateien: dict[str, dict]) -> list[str]:
    return [
        f"{name}: Fall {f.get('id')!r} ({f.get('liste')}, {f.get('format')}, {f.get('pruefung')}) ist rot_erwartet"
        for name, f in _alle_faelle(dateien)
        if f.get("status") == "rot_erwartet"
    ]


def pruefe_verweise(dateien: dict[str, dict]) -> list[str]:
    fehler = []
    for name, fall in _alle_faelle(dateien):
        if fall.get("status") not in STATUS_MIT_VERWEIS:
            continue
        verweis = str(fall.get("verweis") or "").strip()
        if not verweis or not VERWEIS_MUSTER.search(verweis):
            fehler.append(
                f"{name}: Fall {fall.get('id')!r} ({fall.get('status')}) ohne Verweis "
                f"(#Issue, ADR-NNNN oder Wnn), verweis={verweis!r}"
            )
    return fehler


# ---------------------------------------------------------------------------
# (e) Schema
# ---------------------------------------------------------------------------


def _pruefe_fall_schema(name: str, index: int, fall) -> list[str]:
    if not isinstance(fall, dict):
        return [f"{name}: faelle[{index}] ist kein Objekt"]
    kennung = f"{name}: Fall {fall.get('id', f'faelle[{index}]')!r}"
    fehler = [f"{kennung}: Pflichtfeld {feld!r} fehlt" for feld in PFLICHTFELDER if feld not in fall]
    if "status" in fall and fall["status"] not in ERLAUBTE_STATUS:
        fehler.append(f"{kennung}: status {fall['status']!r} nicht erlaubt ({sorted(ERLAUBTE_STATUS)})")
    if "format" in fall and fall["format"] not in ERLAUBTE_FORMATE:
        fehler.append(f"{kennung}: format {fall['format']!r} nicht erlaubt ({sorted(ERLAUBTE_FORMATE)})")
    if "werte" in fall and not isinstance(fall["werte"], dict):
        fehler.append(f"{kennung}: 'werte' muss ein Objekt sein")
    return fehler


def pruefe_schema(dateien: dict[str, dict]) -> list[str]:
    fehler: list[str] = []
    ids: Counter = Counter()
    for name, inhalt in dateien.items():
        if "dimensionen" in inhalt and not isinstance(inhalt["dimensionen"], dict):
            fehler.append(f"{name}: 'dimensionen' muss ein Objekt sein")
        for index, fall in enumerate(inhalt.get("faelle", [])):
            fehler.extend(_pruefe_fall_schema(name, index, fall))
            if isinstance(fall, dict) and "id" in fall:
                ids[fall["id"]] += 1
    fehler.extend(f"id {i!r} kommt {n}-mal vor (muss global eindeutig sein)" for i, n in ids.items() if n > 1)
    return fehler


def zaehle_status(dateien: dict[str, dict]) -> dict[str, int]:
    zaehler = Counter(f.get("status") for _, f in _alle_faelle(dateien))
    return {s: zaehler.get(s, 0) for s in ("gruen", "ausnahme", "offen_feature", "rot_erwartet")}


def _melde(fehler: list[str], titel: str) -> None:
    if fehler:
        pytest.fail(f"{titel} ({len(fehler)}):\n  " + "\n  ".join(fehler), pytrace=False)


# ---------------------------------------------------------------------------
# Waechter gegen die echten Teildateien
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def _echte_falllisten_roh() -> dict[str, dict] | FalllisteFehler:
    try:
        return lade_falllisten(FALLLISTEN_DIR)
    except FalllisteFehler as exc:
        return exc


@pytest.fixture
def echte_falllisten(_echte_falllisten_roh) -> dict[str, dict]:
    """Echte Teildateien; fehlt eine, scheitert der Test selbst (kein Skip, kein Setup-Error)."""
    return _echte_falllisten_roh


def _geladen(daten) -> dict[str, dict]:
    if isinstance(daten, FalllisteFehler):
        pytest.fail(str(daten), pytrace=False)
    return daten


def test_abdeckungsmatrix_auswahl_und_reihenfolge(echte_falllisten):
    """(a) jede Liste x Format hat einen Fall auswahl und einen Fall reihenfolge."""
    _melde(pruefe_abdeckung(_geladen(echte_falllisten)), "Abdeckungsmatrix unvollstaendig")


def test_testverweise_auffindbar(echte_falllisten):
    """(b) jeder Fall (auch ausnahme/offen_feature) nennt eine existierende Testfunktion."""
    _melde(pruefe_testverweise(_geladen(echte_falllisten), REPO_ROOT), "Testverweise nicht auffindbar")


def test_paarweise_ueberdeckung(echte_falllisten):
    """(c) jedes Wertepaar zweier Dimensionen kommt je Liste vor (ausser ausgeschlossen)."""
    _melde(pruefe_paarweise(_geladen(echte_falllisten)), "Paarweise Ueberdeckung lueckenhaft")


def test_fertig_kein_rot_erwartet(echte_falllisten):
    """(d) fertig heisst: kein Fall steht noch auf rot_erwartet."""
    _melde(finde_rot_erwartet(_geladen(echte_falllisten)), "Faelle noch rot_erwartet")


def test_template_literal_titel_alle_gefunden():
    """(b) Jeder Frontend-Fall, dessen Titel nur als Template-Literal im Test
    steht (``test(`<Titel> ${z.id}`)``), wird ueber den festen Praefix gefunden
    -- und jeder solche Praefix der Editor-Testdateien hat mindestens einen
    Fall (sonst liefe ein Testblock ohne Eintrag in der Fallliste)."""
    vitest_dateien = sorted(REPO_ROOT.glob(VITEST_GLOB))
    praefixe = {p.strip() for d in vitest_dateien
                if "gleich_mail" in d.name or "in_allen_listen" in d.name
                for p in _VITEST_TEMPLATE_PRAEFIX.findall(d.read_text(encoding="utf-8"))}
    # Ganz dynamischer Titel (``test(`${name} ...`)``) gehoert zum Helfer
    # ``rotErwartet``; dessen Aufrufe werden als eigene Titel gefunden.
    praefixe.discard("")
    assert praefixe, "keine Template-Literal-Titel gefunden -- Muster pruefen"
    faelle = [f for _, f in _alle_faelle(lade_falllisten(FALLLISTEN_DIR)) if _ist_vitest_fall(f)]
    titel = {str(f["test"]).split(".test.ts::")[-1].strip() for f in faelle}
    fehlend = [f["id"] for f in faelle if f["status"] in STATUS_MIT_TEST
               and not _pruefe_vitest_verweis(str(f["test"]), vitest_dateien)]
    assert fehlend == [], f"Template-/Titel nicht gefunden: {fehlend}"
    assert praefixe <= titel, f"Template-Titel ohne Fall: {sorted(praefixe - titel)}"


def test_ausnahmen_und_offene_features_tragen_verweis(echte_falllisten):
    """(d) jede ausnahme / jedes offen_feature traegt einen Issue-/ADR-/Konzept-Verweis."""
    _melde(pruefe_verweise(_geladen(echte_falllisten)), "Verweis fehlt")


def test_schema_der_fallliste(echte_falllisten):
    """(e) Pflichtfelder, erlaubte Werte, id global eindeutig."""
    _melde(pruefe_schema(_geladen(echte_falllisten)), "Schema verletzt")


def test_zaehlung_ausgeben(echte_falllisten):
    """Zaehlung als eine Zeile (sichtbar mit -s); besteht, sofern Dateien lesbar."""
    z = zaehle_status(_geladen(echte_falllisten))
    print(
        f"Fallliste #3047: gruen={z['gruen']} ausnahme={z['ausnahme']} "
        f"offen_feature={z['offen_feature']} rot_erwartet={z['rot_erwartet']}"
    )


# ---------------------------------------------------------------------------
# Selbsttests der Prueflogik mit synthetischen Falllisten (tmp_path)
# ---------------------------------------------------------------------------

_SYN_PY_TESTS = '''
def test_trip_fall():
    pass

class TestOrte:
    def test_orte_methode(self):
        pass
'''

_SYN_VITEST = """
import { it, test } from 'vitest';
it('editor behaelt reihenfolge', () => {});
it.fails("editor kennt noch nicht", () => {});
rotErwartet('editor rot bis zur behebung', () => {});
for (const z of zustaende) {
  test(`editor standard je zustand ${z.id}`, () => {});
}
"""

_SYN_GO = """package handler

func TestSynVorlageFolge(t *testing.T) {}

// func TestNurImKommentar(t *testing.T) {}
func helperTestKeinTest() {}
"""


def _syn_fall(fid: str, liste: str, fmt: str, pruefung: str, **extra) -> dict:
    fall = {
        "id": fid, "liste": liste, "kontext": liste.split("_")[0], "format": fmt,
        "pruefung": pruefung, "test": "test_trip_fall", "ac": "AC-2", "befund": "", "status": "gruen",
    }
    fall.update(extra)
    return fall


def _syn_daten() -> dict[str, dict]:
    trip, orte = [], []
    for liste, formate in ABDECKUNG_SOLL.items():
        ziel = trip if liste.startswith("trip") else orte
        for fmt in formate:
            for pruefung in ABDECKUNG_PRUEFUNGEN:
                ziel.append(_syn_fall(f"{liste}-{fmt}-{pruefung}", liste, fmt, pruefung))
    orte[0]["test"] = "test_einstellung_gleich_mail_syn.py::TestOrte::test_orte_methode"
    orte[1]["test"] = "test_orte_methode"
    paarweise = [
        _syn_fall(f"pw-{i}", "trip_ausblick", "html", "darstellung", werte={"auswahl": a, "darstellung": d})
        for i, (a, d) in enumerate(itertools.product(["teilmenge", "alles"], ["roh", "einfach"]))
    ]
    editor = [
        _syn_fall("ed-1", "trip_vorlage", "editor", "standard", seite="frontend",
                  test="editor behaelt reihenfolge"),
        _syn_fall("ed-2", "trip_vorlage", "editor", "standard",
                  test="editor_standard_gleich_mail.test.ts::editor kennt noch nicht"),
        _syn_fall("ed-3", "trip_vorlage", "editor", "standard", status="offen_feature",
                  verweis="Konzept W19, Issue #3050"),
    ]
    return {
        "fallliste_trip.json": {
            "dimensionen": {"auswahl": ["teilmenge", "alles"], "darstellung": ["roh", "einfach"],
                            "hinweis": "synthetisch"},
            "faelle": trip + paarweise,
        },
        "fallliste_orte.json": {"dimensionen": {}, "faelle": orte},
        "fallliste_validatoren.json": {"faelle": []},
        "fallliste_editor.json": {"faelle": editor},
    }


def _schreibe(wurzel: Path, daten: dict[str, dict]) -> Path:
    verzeichnis = wurzel / "tests" / "fixtures" / "einstellung_gleich_mail"
    verzeichnis.mkdir(parents=True, exist_ok=True)
    for name, inhalt in daten.items():
        (verzeichnis / name).write_text(json.dumps(inhalt, ensure_ascii=False), encoding="utf-8")
    tdd = wurzel / "tests" / "tdd"
    tdd.mkdir(parents=True, exist_ok=True)
    (tdd / "test_einstellung_gleich_mail_syn.py").write_text(_SYN_PY_TESTS, encoding="utf-8")
    vt = wurzel / "frontend" / "src" / "lib" / "x" / "__tests__"
    vt.mkdir(parents=True, exist_ok=True)
    (vt / "editor_standard_gleich_mail.test.ts").write_text(_SYN_VITEST, encoding="utf-8")
    gt = wurzel / "internal" / "handler"
    gt.mkdir(parents=True, exist_ok=True)
    (gt / "syn_test.go").write_text(_SYN_GO, encoding="utf-8")
    return verzeichnis


def _alle_pruefungen(wurzel: Path, verzeichnis: Path) -> list[str]:
    d = lade_falllisten(verzeichnis)
    return (pruefe_abdeckung(d) + pruefe_testverweise(d, wurzel) + pruefe_paarweise(d)
            + finde_rot_erwartet(d) + pruefe_verweise(d) + pruefe_schema(d))


def test_selbsttest_vollstaendige_liste_ist_gruen(tmp_path):
    verzeichnis = _schreibe(tmp_path, _syn_daten())
    assert _alle_pruefungen(tmp_path, verzeichnis) == []
    assert zaehle_status(lade_falllisten(verzeichnis)) == {
        "gruen": 36, "ausnahme": 0, "offen_feature": 1, "rot_erwartet": 0,
    }


def test_selbsttest_fehlende_teildatei_scheitert_klar(tmp_path):
    daten = _syn_daten()
    del daten["fallliste_editor.json"]
    verzeichnis = _schreibe(tmp_path, daten)
    with pytest.raises(FalllisteFehler, match=r"Teildatei fehlt: .*fallliste_editor\.json"):
        lade_falllisten(verzeichnis)


def test_selbsttest_geloeschter_fall_wird_benannt(tmp_path):
    daten = _syn_daten()
    orte = daten["fallliste_orte.json"]["faelle"]
    daten["fallliste_orte.json"]["faelle"] = [
        f for f in orte if f["id"] != "orte_stundenverlauf-klartext-reihenfolge"
    ]
    verzeichnis = _schreibe(tmp_path, daten)
    assert pruefe_abdeckung(lade_falllisten(verzeichnis)) == [
        "kein Fall fuer liste=orte_stundenverlauf, format=klartext, pruefung=reihenfolge"
    ]


def test_selbsttest_ausnahme_zaehlt_als_abgedeckt(tmp_path):
    daten = _syn_daten()
    fall = daten["fallliste_trip.json"]["faelle"][0]
    fall.update(status="ausnahme", verweis="#814 AC-5")
    verzeichnis = _schreibe(tmp_path, daten)
    assert _alle_pruefungen(tmp_path, verzeichnis) == []


def test_selbsttest_unbekannte_testfunktion_wird_gemeldet(tmp_path):
    daten = _syn_daten()
    daten["fallliste_trip.json"]["faelle"][0]["test"] = "test_gibt_es_nicht"
    daten["fallliste_orte.json"]["faelle"][0]["test"] = "test_einstellung_gleich_mail_syn.py::test_nicht_da"
    daten["fallliste_editor.json"]["faelle"][0]["test"] = "editor tippfehler"
    verzeichnis = _schreibe(tmp_path, daten)
    fehler = pruefe_testverweise(lade_falllisten(verzeichnis), tmp_path)
    assert len(fehler) == 3
    assert any("test_gibt_es_nicht" in f for f in fehler)
    assert any("test_nicht_da" in f for f in fehler)
    assert any("editor tippfehler" in f for f in fehler)


def test_selbsttest_testverweis_auch_bei_ausnahme_und_offen_feature(tmp_path):
    """#3047 J2: auch ``ausnahme`` und ``offen_feature`` nennen eine
    auffindbare Testfunktion (Python per AST, Frontend-Titel, Go) -- ein
    offenes Feature ohne roten Test liefe sonst unbemerkt; ein leerer Verweis
    zaehlt nicht."""
    daten = _syn_daten()
    faelle = daten["fallliste_trip.json"]["faelle"]
    faelle[0].update(status="ausnahme", verweis="#814", test="test_gibt_es_nicht")
    faelle[1].update(status="offen_feature", verweis="#3065", test="test_fehlt_auch")
    faelle[2].update(status="offen_feature", verweis="#3065", test="")
    daten["fallliste_editor.json"]["faelle"].append(_syn_fall(
        "ed-go-offen", "trip_vorlage", "editor", "standard", seite="go", status="offen_feature",
        verweis="#3065", test="TestNurImKommentar"))
    daten["fallliste_editor.json"]["faelle"].append(_syn_fall(
        "ed-fe-ausnahme", "trip_vorlage", "editor", "standard", seite="frontend",
        status="ausnahme", verweis="#814", test="editor tippfehler"))
    verzeichnis = _schreibe(tmp_path, daten)
    fehler = pruefe_testverweise(lade_falllisten(verzeichnis), tmp_path)
    assert len(fehler) == 5, fehler
    for kennung in (faelle[0]["id"], faelle[1]["id"], faelle[2]["id"], "ed-go-offen", "ed-fe-ausnahme"):
        assert any(repr(kennung) in f for f in fehler), (kennung, fehler)
    faelle[0]["test"] = faelle[1]["test"] = faelle[2]["test"] = "test_trip_fall"
    daten["fallliste_editor.json"]["faelle"][-2]["test"] = "TestSynVorlageFolge"
    daten["fallliste_editor.json"]["faelle"][-1]["test"] = "editor behaelt reihenfolge"
    verzeichnis = _schreibe(tmp_path, daten)
    assert pruefe_testverweise(lade_falllisten(verzeichnis), tmp_path) == []


def test_selbsttest_frontend_rot_erwartet_und_template_titel(tmp_path):
    """``rotErwartet(`` zaehlt als Testaufruf (node --test-Helfer), ein
    Template-Literal-Titel wird ueber seinen festen Text vor ``${`` gefunden;
    ein Teil dieses Textes oder ein Nicht-Testaufruf zaehlt nicht."""
    daten = _syn_daten()
    editor = daten["fallliste_editor.json"]["faelle"]
    editor[0]["test"] = "editor rot bis zur behebung"
    editor[1]["test"] = "editor_standard_gleich_mail.test.ts::editor standard je zustand"
    verzeichnis = _schreibe(tmp_path, daten)
    assert pruefe_testverweise(lade_falllisten(verzeichnis), tmp_path) == []

    editor[0]["test"] = "editor standard je"            # nur ein Teil des Praefixes
    editor[1]["test"] = "editor_standard_gleich_mail.test.ts::nur beschreibung"
    vt = tmp_path / "frontend" / "src" / "lib" / "x" / "__tests__"
    verzeichnis = _schreibe(tmp_path, daten)
    datei = vt / "editor_standard_gleich_mail.test.ts"
    datei.write_text(_SYN_VITEST + "describe(`nur beschreibung ${x}`, () => {});\n",
                     encoding="utf-8")
    fehler = pruefe_testverweise(lade_falllisten(verzeichnis), tmp_path)
    assert len(fehler) == 2, fehler


def test_selbsttest_paarluecke_und_ausschluss(tmp_path):
    daten = _syn_daten()
    trip = daten["fallliste_trip.json"]
    trip["faelle"] = [f for f in trip["faelle"] if f["id"] != "pw-3"]  # alles x einfach
    verzeichnis = _schreibe(tmp_path, daten)
    fehler = pruefe_paarweise(lade_falllisten(verzeichnis))
    assert fehler == [
        "fallliste_trip.json: liste=trip_ausblick: Paar auswahl='alles' x darstellung='einfach' nicht abgedeckt"
    ]
    for ausschluss in (["darstellung", "einfach", "auswahl", "alles"],
                       ["trip_ausblick", "auswahl", "alles", "darstellung", "einfach"]):
        trip["dimensionen"]["ausgeschlossen"] = [ausschluss]
        verzeichnis = _schreibe(tmp_path, daten)
        assert pruefe_paarweise(lade_falllisten(verzeichnis)) == []
    trip["dimensionen"]["ausgeschlossen"] = [["trip_stundentabelle", "auswahl", "alles", "darstellung", "einfach"]]
    verzeichnis = _schreibe(tmp_path, daten)
    assert len(pruefe_paarweise(lade_falllisten(verzeichnis))) == 1


def test_selbsttest_rot_erwartet_und_fehlender_verweis(tmp_path):
    daten = _syn_daten()
    faelle = daten["fallliste_trip.json"]["faelle"]
    faelle[0]["status"] = "rot_erwartet"
    faelle[1].update(status="ausnahme", verweis="gewollt")
    faelle[2].update(status="offen_feature")
    verzeichnis = _schreibe(tmp_path, daten)
    d = lade_falllisten(verzeichnis)
    rot = finde_rot_erwartet(d)
    assert len(rot) == 1 and faelle[0]["id"] in rot[0]
    verweise = pruefe_verweise(d)
    assert len(verweise) == 2
    assert faelle[1]["id"] in verweise[0] and faelle[2]["id"] in verweise[1]


def test_selbsttest_go_testfunktion(tmp_path):
    """``seite: "go"``: gefunden wird ``func <Name>(`` am Zeilenanfang in
    ``internal/**/*_test.go``; ein Name nur im Kommentar, ein Teilname oder
    ein Python-Testname mit ``seite: "go"`` zaehlt nicht."""
    daten = _syn_daten()
    editor = daten["fallliste_editor.json"]["faelle"]
    editor.append(_syn_fall("ed-go", "trip_vorlage", "editor", "reihenfolge", seite="go",
                            test="TestSynVorlageFolge"))
    verzeichnis = _schreibe(tmp_path, daten)
    assert pruefe_testverweise(lade_falllisten(verzeichnis), tmp_path) == []
    for falsch in ("TestNurImKommentar", "TestSyn", "test_trip_fall", "helperTestKeinTest"):
        editor[-1]["test"] = falsch
        verzeichnis = _schreibe(tmp_path, daten)
        fehler = pruefe_testverweise(lade_falllisten(verzeichnis), tmp_path)
        assert len(fehler) == 1 and falsch in fehler[0] and GO_TEST_GLOB in fehler[0], (falsch, fehler)


def test_selbsttest_schema_verstoesse(tmp_path):
    daten = _syn_daten()
    faelle = daten["fallliste_trip.json"]["faelle"]
    del faelle[0]["ac"]
    faelle[1]["status"] = "gelb"
    faelle[2]["format"] = "pdf"
    daten["fallliste_editor.json"]["faelle"][0]["id"] = faelle[3]["id"]
    verzeichnis = _schreibe(tmp_path, daten)
    fehler = pruefe_schema(lade_falllisten(verzeichnis))
    assert len(fehler) == 4
    assert any("'ac' fehlt" in f for f in fehler)
    assert any("'gelb'" in f for f in fehler)
    assert any("'pdf'" in f for f in fehler)
    assert any("global eindeutig" in f and faelle[3]["id"] in f for f in fehler)
