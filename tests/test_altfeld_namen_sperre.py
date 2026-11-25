# doc-compliance-test
"""Feldnamen-Waechter: die zehn Altfelder kehren nicht in den Backend-Code zurueck (#3277).

SPEC: docs/specs/modules/feat_3277_altfelder_entfernen.md, AC-7 (Schritt 5),
AC-9 (Schritt 6), AC-10.

Werkzeug-Klasse (CLAUDE.md-Ausnahme ``# doc-compliance-test``): der Waechter
liest Quelltext als DATEN. Python (``src``, ``api``, ``.claude/hooks``,
``scripts``) per ``ast.walk``: ein Altfeld-Name als Schluessel-/String-Literal,
Attribut, Parameter, Schluesselwort-Argument oder annotiertes Feld (Modell)
ist ein Treffer. Go (``internal``, ``cmd``, ohne ``_test.go``) per Textsuche
nach dem Namen in Anfuehrungszeichen (Schluessel-Literal, JSON-Tag);
Kommentare zaehlen nicht.

Ausnahmen:
* Die EINE zentrale Entfernungsliste (Spec Schritt 1) heisst ``ALTFELDER``;
  String-Literale im Wert ihrer Zuweisung zaehlen nicht. Sie darf im
  Backend nur einmal definiert sein und nennt genau die zehn Namen.
* ``ERLAUBT``: (Datei, Name) -> (Grund >= 20 Zeichen, Ablaufdatum). Eine
  abgelaufene Ausnahme macht den Test rot.

Selbstnachweis: synthetischer Quelltext (Verstoss erkannt, erlaubter Eintrag
besteht, Ablauf schlaegt an, zu kurzer Grund wird abgelehnt).
"""
from __future__ import annotations

import ast
import re
from datetime import date
from pathlib import Path

import pytest

WURZEL = Path(__file__).resolve().parents[1]
PYTHON = (WURZEL / "src", WURZEL / "api", WURZEL / ".claude" / "hooks", WURZEL / "scripts")
GO = (WURZEL / "internal", WURZEL / "cmd")

#: Die zehn Altfelder (Spec #3122 Teil A Nr. 8, ADR-0124 Nr. 6).
ALTFELD_NAMEN = frozenset({
    "channel_layouts", "channel_layouts_per_report", "channel_active_metrics",
    "outlook_metrics", "outlook_metric_formats", "hourly_metrics",
    "hourly_metric_formats", "show_outlook", "multi_day_trend_reports",
    "outlook_enabled",
})

#: Name der zentralen Entfernungsliste (Spec Schritt 1).
LISTEN_NAME = "ALTFELDER"

_VALIDATOR_GRUND = ("Request-Parameter der Validator-Vorschau ohne Store-Bezug: liest nur den "
                    "Body, baut daraus placements, laedt/schreibt kein Abo (Spec Schritt 6)")
_ABLAUF = date(2027, 2, 23)

#: (Datei relativ zur Wurzel, Name) -> (Begruendung, Ablaufdatum).
ERLAUBT: dict[tuple[str, str], tuple[str, date]] = {
    ("api/routers/validator.py", "hourly_metrics"): (_VALIDATOR_GRUND, _ABLAUF),
    ("api/routers/validator.py", "hourly_metric_formats"): (_VALIDATOR_GRUND, _ABLAUF),
    ("src/services/validator_render_service.py", "hourly_metrics"): (_VALIDATOR_GRUND, _ABLAUF),
    ("src/services/validator_render_service.py", "hourly_metric_formats"):
        (_VALIDATOR_GRUND, _ABLAUF),
}


def _listen_literale(baum: ast.AST) -> set[int]:
    """``id()`` aller String-Literale im Wert einer ``ALTFELDER``-Zuweisung."""
    frei: set[int] = set()
    for knoten in ast.walk(baum):
        ziele = []
        if isinstance(knoten, ast.Assign):
            ziele = knoten.targets
        elif isinstance(knoten, ast.AnnAssign):
            ziele = [knoten.target]
        if any(isinstance(z, ast.Name) and z.id == LISTEN_NAME for z in ziele) and knoten.value:
            frei |= {id(k) for k in ast.walk(knoten.value) if isinstance(k, ast.Constant)}
    return frei


def _namen(baum: ast.AST) -> list[tuple[int, str]]:
    """(Zeile, Name) jeder Stelle, an der ein Altfeld-Name als Literal,
    Attribut, Parameter, Schluesselwort oder annotiertes Feld steht."""
    frei = _listen_literale(baum)
    treffer: list[tuple[int, str]] = []
    for k in ast.walk(baum):
        name = None
        if isinstance(k, ast.Constant) and isinstance(k.value, str) and id(k) not in frei:
            name = k.value
        elif isinstance(k, ast.Attribute):
            name = k.attr
        elif isinstance(k, ast.arg):
            name = k.arg
        elif isinstance(k, ast.keyword):
            name = k.arg
        elif isinstance(k, ast.AnnAssign) and isinstance(k.target, ast.Name):
            name = k.target.id
        if name in ALTFELD_NAMEN:
            treffer.append((getattr(k, "lineno", 0), name))
    return treffer


def _gefiltert(treffer, datei: str, erlaubt, heute: date) -> list[str]:
    out = []
    for zeile, name in treffer:
        ausnahme = erlaubt.get((datei, name))
        if ausnahme is not None and ausnahme[1] >= heute and len(ausnahme[0]) >= 20:
            continue
        out.append(f"{datei}:{zeile}: {name}")
    return out


def verstoesse(quelltext: str, datei: str, erlaubt=None, heute: date | None = None) -> list[str]:
    """Treffer in Python-Quelltext, die keine gueltige Ausnahme decken."""
    erlaubt = ERLAUBT if erlaubt is None else erlaubt
    return _gefiltert(_namen(ast.parse(quelltext)), datei, erlaubt, heute or date.today())


_GO_KOMMENTAR = re.compile(r"//[^\n]*")
_GO_NAME = re.compile(r'"(' + "|".join(sorted(ALTFELD_NAMEN)) + r')[",]')


def go_verstoesse(quelltext: str, datei: str, erlaubt=None, heute: date | None = None) -> list[str]:
    """Treffer in Go-Quelltext: Name in Anfuehrungszeichen (Literal, JSON-Tag)."""
    erlaubt = ERLAUBT if erlaubt is None else erlaubt
    treffer = []
    for nr, zeile in enumerate(quelltext.splitlines(), start=1):
        treffer += [(nr, m.group(1)) for m in _GO_NAME.finditer(_GO_KOMMENTAR.sub("", zeile))]
    return _gefiltert(treffer, datei, erlaubt, heute or date.today())


def _python_dateien():
    for ordner in PYTHON:
        yield from sorted(ordner.rglob("*.py"))


def _go_dateien():
    for ordner in GO:
        yield from sorted(p for p in ordner.rglob("*.go") if not p.name.endswith("_test.go"))


def _rel(pfad: Path) -> str:
    return str(pfad.relative_to(WURZEL))


# ---------------------------------------------------------------------------
# Repo-Pruefung
# ---------------------------------------------------------------------------

def test_ac7_kein_python_backend_code_nennt_ein_altfeld():
    funde = []
    for pfad in _python_dateien():
        funde += verstoesse(pfad.read_text(encoding="utf-8"), _rel(pfad))
    assert not funde, f"{len(funde)} Altfeld-Namen im Backend:\n" + "\n".join(funde)


def test_ac7_kein_go_code_nennt_ein_altfeld():
    funde = []
    for pfad in _go_dateien():
        funde += go_verstoesse(pfad.read_text(encoding="utf-8"), _rel(pfad))
    assert not funde, "Altfeld-Namen im Go-Code:\n" + "\n".join(funde)


def test_ac7_zentrale_entfernungsliste_genau_einmal_mit_den_zehn_namen():
    definitionen = []
    for pfad in _python_dateien():
        baum = ast.parse(pfad.read_text(encoding="utf-8"))
        for knoten in ast.walk(baum):
            ziele = knoten.targets if isinstance(knoten, ast.Assign) else (
                [knoten.target] if isinstance(knoten, ast.AnnAssign) else [])
            if any(isinstance(z, ast.Name) and z.id == LISTEN_NAME for z in ziele):
                namen = {k.value for k in ast.walk(knoten.value)
                         if isinstance(k, ast.Constant) and isinstance(k.value, str)}
                definitionen.append((_rel(pfad), namen))
    assert len(definitionen) == 1, definitionen
    assert definitionen[0][1] == ALTFELD_NAMEN, definitionen


def test_ac7_erlaubnisliste_traegt_begruendung_und_ist_nicht_abgelaufen():
    for (datei, name), (grund, ablauf) in ERLAUBT.items():
        assert name in ALTFELD_NAMEN, (datei, name)
        assert (WURZEL / datei).exists(), datei
        assert len(grund) >= 20, (datei, name, grund)
        assert ablauf >= date.today(), f"Ausnahme abgelaufen: {datei} {name} ({ablauf})"


# ---------------------------------------------------------------------------
# Selbstnachweis
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("quelle", [
    "dc.get('show_outlook', True)\n",
    "data = {'multi_day_trend_reports': []}\n",
    "x = rc.outlook_enabled\n",
    "def f(*, hourly_metrics=None):\n    pass\n",
    "render(outlook_metrics=[])\n",
    "class C:\n    channel_layouts_per_report: dict = None\n",
])
def test_selbstnachweis_verstoss_wird_erkannt(quelle):
    assert verstoesse(quelle, "src/beispiel.py", erlaubt={}), quelle


def test_selbstnachweis_go_json_tag_wird_erkannt_kommentar_nicht():
    quelle = ('type P struct {\n'
              '\t// outlook_enabled war frueher hier ("outlook_enabled")\n'
              '\tX *bool `json:"outlook_enabled,omitempty"`\n'
              '}\n')
    funde = go_verstoesse(quelle, "internal/model/p.go", erlaubt={})
    assert funde == ["internal/model/p.go:3: outlook_enabled"], funde


def test_selbstnachweis_zentrale_liste_ist_frei():
    quelle = "ALTFELDER = frozenset({'show_outlook', 'outlook_enabled'})\n"
    assert verstoesse(quelle, "src/app/loader.py", erlaubt={}) == []
    assert verstoesse(quelle + "y = d['show_outlook']\n", "src/app/loader.py", erlaubt={})


def test_selbstnachweis_erlaubter_eintrag_besteht():
    erlaubt = {("src/beispiel.py", "hourly_metrics"):
               ("Selbstnachweis: befristete Ausnahme", date(2099, 1, 1))}
    assert verstoesse("f(hourly_metrics=[])\n", "src/beispiel.py", erlaubt=erlaubt) == []


def test_selbstnachweis_abgelaufener_eintrag_faellt():
    erlaubt = {("src/beispiel.py", "hourly_metrics"):
               ("Selbstnachweis: abgelaufene Ausnahme", date(2000, 1, 1))}
    assert verstoesse("f(hourly_metrics=[])\n", "src/beispiel.py", erlaubt=erlaubt)


def test_selbstnachweis_zu_kurzer_grund_wird_abgelehnt():
    erlaubt = {("src/beispiel.py", "hourly_metrics"): ("zu kurz", date(2099, 1, 1))}
    assert verstoesse("f(hourly_metrics=[])\n", "src/beispiel.py", erlaubt=erlaubt)


def test_selbstnachweis_andere_namen_und_texte_sind_frei():
    quelle = ("v = rc.outlook_reports\n"
              "'''Doku: show_outlook ist entfallen.'''\n"
              "d.get('placements')\n")
    assert verstoesse(quelle, "src/beispiel.py", erlaubt={}) == []
