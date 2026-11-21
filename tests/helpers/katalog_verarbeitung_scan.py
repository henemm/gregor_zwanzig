"""Erkennungs-Kern der Ratsche „Ein Katalog, eine Verarbeitung“ (Issue #3260, ADR-0127).

SPEC: docs/specs/modules/feat_3260_s1a_ratsche_ein_katalog.md

Sucht Metrik-Wissen und Metrik-Verarbeitung ausserhalb der erlaubten Orte
(Katalog ``src/app/metric_catalog.py``, Verarbeitung ``src/output/metric_format``,
Ampel-Vorlagen ``src/app/ampel_templates.py``/``src/app/ampel.py``). Arten:

* ``ID_SAMMLUNG``        Python-Sammlung mit >= 2 Kennungen (auch rechts von ``in``)
* ``ID_VERZWEIGUNG``     ``==``/``!=`` bzw. ``match``-``case`` auf eine Kennung
* ``SCHWELLE``           ``<``/``<=``/``>``/``>=`` eines Messwerts mit einer Zahl
* ``VERARBEITUNG_AUSSEN`` Definition/Aufruf/Verweis einer Verarbeitungsfunktion
* ``FRONTEND_LISTE``/``FRONTEND_VERZWEIGUNG``/``FRONTEND_SCHWELLE`` (TS/Svelte),
  ``GO_LISTE``/``GO_VERZWEIGUNG``/``GO_SCHWELLE``
* ``VALIDATOR_IMPORT``   Import von Metrik-Wissen in ``.claude/hooks/*.py``

Alle Scan-Funktionen nehmen Wurzeln (Verzeichnisse ODER Dateien) und eine
``basis`` fuer die relativen Pfade — so laufen die Gegenproben gegen ein
temporaeres Verzeichnis. Die Soll-Kennungen kommen aus dem Register
(``_METRICS``), nicht von Hand. Grenzfaelle werden durch Umbau aufgeloest,
nicht durch Sonderfaelle hier (ADR-0127, Konsequenzen).

Ausnahmeliste neu erzeugen (der Test schreibt nie)::

    uv run python -m tests.helpers.katalog_verarbeitung_scan --schreibe-ausnahmen

Regel-Budget: Pruefdatum 2027-02-19.
"""
from __future__ import annotations

import ast
import bisect
import json
import re
import subprocess
import sys
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Iterable, Iterator

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT / "src") not in sys.path:
    sys.path.insert(0, str(REPO_ROOT / "src"))

from app.metric_catalog import _METRICS  # noqa: E402

#: Metrik-Kennungen aus dem Register (alle 32 ``_METRICS``-Ids).
METRIK_IDS: frozenset[str] = frozenset(m.id for m in _METRICS)
#: Alarm-Identitaeten, ebenfalls aus dem Register (``alert_metrics`` und
#: ``change_alert_metric`` je Metrik): ``wind_gust``, ``temperature_min`` …
#: Ohne sie bliebe die Alarm-Vokabular-Kopie in Go (``AlertableMetrics``)
#: unsichtbar (Abweichung von der Spec, dort dokumentiert).
ALARM_IDS: frozenset[str] = frozenset(
    {a for m in _METRICS for a in m.alert_metrics.values()}
    | {m.change_alert_metric for m in _METRICS if m.change_alert_metric})
KENNUNGEN: frozenset[str] = METRIK_IDS | ALARM_IDS
AUSNAHMEN_PFAD = REPO_ROOT / "tests" / "unit" / "ein_katalog_ausnahmen.json"

ID_SAMMLUNG = "ID_SAMMLUNG"
ID_VERZWEIGUNG = "ID_VERZWEIGUNG"
SCHWELLE = "SCHWELLE"
VERARBEITUNG_AUSSEN = "VERARBEITUNG_AUSSEN"
FRONTEND_LISTE = "FRONTEND_LISTE"
FRONTEND_VERZWEIGUNG = "FRONTEND_VERZWEIGUNG"
GO_LISTE = "GO_LISTE"
GO_VERZWEIGUNG = "GO_VERZWEIGUNG"
FRONTEND_SCHWELLE = "FRONTEND_SCHWELLE"
GO_SCHWELLE = "GO_SCHWELLE"
VALIDATOR_IMPORT = "VALIDATOR_IMPORT"
ARTEN = (ID_SAMMLUNG, ID_VERZWEIGUNG, SCHWELLE, VERARBEITUNG_AUSSEN,
         FRONTEND_LISTE, FRONTEND_VERZWEIGUNG, FRONTEND_SCHWELLE,
         GO_LISTE, GO_VERZWEIGUNG, GO_SCHWELLE, VALIDATOR_IMPORT)

#: Erlaubte Orte (relativ zur Basis) — werden nicht gescannt.
ERLAUBT_DATEIEN = frozenset({
    "src/app/metric_catalog.py", "src/output/metric_format.py",
    "src/app/ampel_templates.py", "src/app/ampel.py",
})
ERLAUBT_PRAEFIXE = ("src/output/metric_format/", "src/analysis/")

#: Verarbeitungsfunktionen ausserhalb des Moduls (Ausgangsbestand P2, #3260).
VERARBEITUNGS_FUNKTIONEN = frozenset({
    # Zellformatierung und Einfach-Formen (Renderer)
    "fmt_val", "_friendly_outlook_text", "_friendly_hour_text",
    "format_outlook_value", "_hour_einfach_text", "_friendly_overview_html",
    "_plain_metric_cell",
    # src/services/weather_metrics.py: Wert -> Wort/Symbol/Kompass
    "get_weather_emoji", "_night_emoji", "_dni_emoji", "_cloud_pct_emoji",
    "format_wind_strength", "format_precip_intensity", "format_precip_daily_sum",
    "format_rain_probability_scale", "format_sunshine_scale",
    "degrees_to_compass", "get_weather_symbol",
    # src/output/renderers/compact_summary.py: Wort-/Schwellenfunktionen
    "_format_clouds", "_format_precipitation", "_precip_adjective",
    "_find_rain_pattern", "_format_wind", "_find_wind_peak", "_format_thunder",
    # src/output/renderers/narrow.py: Wort-/Schwellenfunktionen
    "_thunder_severity", "_day_window_thunder_severity", "_tg_day_footer", "_gelb",
    # src/services/risk_engine.py: Bewertungsfunktionen
    "_check_thunder", "_check_catalog_metric", "_check_confidence",
    "_check_wind_exposition",
})

MESSWERT_MUSTER = re.compile(
    r"wind(?!ow)|gust|boe|böe|precip|rain|regen|niederschlag|(?<!at)temp|chill|cloud|wolk|uv"
    r"|snow|schnee|cape|visib|sicht|sun|sonne|thunder|gewitter|humid|feucht"
    r"|pressure|druck|dewpoint|freezing|kmh|_mm\b|pct|\bval\b|value|wert"
    # Spec-Abweichung (dort dokumentiert): ``wind(?!ow)`` und ``(?<!at)temp``
    # halten ``window``/``day_window_*`` und ``attempt`` heraus; ergaenzt sind
    # ``speed``, ``mm``, ``dni`` — sonst blieben ``speed > 60`` (Windwort in
    # compact_summary) und ``mm > 10`` / ``dni_wm2 >= 600`` unsichtbar.
    r"|speed|\bmm\b|dni",
    re.IGNORECASE)

#: Module, deren Import in einem Validator verboten ist (dazu ``app.*metric*``/``app.*compare*``).
VERBOTENE_MODULE = ("app.metric_catalog", "app.ampel_templates", "app.ampel",
                    "output", "services")


@dataclass(frozen=True)
class Fund:
    """Eine Fundstelle: Datei (relativ zur Basis), Zeile, Art, Auszug."""

    datei: str
    zeile: int
    art: str
    auszug: str

    def __str__(self) -> str:
        return f"{self.datei}:{self.zeile} [{self.art}] {self.auszug}"


def _relativ(pfad: Path, basis: Path) -> str:
    try:
        return pfad.resolve().relative_to(basis.resolve()).as_posix()
    except ValueError:
        return pfad.as_posix()


def _auszug(zeilen: list[str], nr: int) -> str:
    text = zeilen[nr - 1].strip() if 0 < nr <= len(zeilen) else ""
    return text[:120]


def _dateien(wurzeln: Iterable[Path | str], endungen: tuple[str, ...]) -> Iterator[Path]:
    for wurzel in wurzeln:
        pfad = Path(wurzel)
        if pfad.is_dir():
            for datei in sorted(pfad.rglob("*")):
                if datei.is_file() and datei.name.endswith(endungen):
                    yield datei
        elif pfad.is_file() and pfad.name.endswith(endungen):
            yield pfad


def _python_ausgenommen(rel: str) -> bool:
    teile = rel.split("/")
    name = teile[-1]
    return (rel in ERLAUBT_DATEIEN or rel.startswith(ERLAUBT_PRAEFIXE)
            or "tests" in teile[:-1] or "__pycache__" in teile
            or name.startswith("test_") or name.endswith("_test.py")
            or ".generated." in name or "_generated" in name)


# --------------------------------------------------------------------- Python

def _ist_kennung(knoten: ast.AST | None) -> bool:
    return (isinstance(knoten, ast.Constant) and isinstance(knoten.value, str)
            and knoten.value in KENNUNGEN)


def _ist_zahl(knoten: ast.AST) -> bool:
    if isinstance(knoten, ast.UnaryOp) and isinstance(knoten.op, (ast.USub, ast.UAdd)):
        knoten = knoten.operand
    return (isinstance(knoten, ast.Constant) and isinstance(knoten.value, (int, float))
            and not isinstance(knoten.value, bool))


def _ist_messwert(knoten: ast.AST) -> bool:
    text = ast.unparse(knoten)
    return "len(" not in text and MESSWERT_MUSTER.search(text) is not None


def _sammlung(knoten: ast.AST) -> bool:
    """>= 2 verschiedene konstante Strings, alle Kennungen (dict: je Seite)."""
    if isinstance(knoten, ast.Dict):
        seiten = [knoten.keys, knoten.values]
    elif isinstance(knoten, (ast.Set, ast.List, ast.Tuple)):
        seiten = [knoten.elts]
    else:
        return False
    for teile in seiten:
        strings = {t.value for t in teile
                   if isinstance(t, ast.Constant) and isinstance(t.value, str)}
        if len(strings) >= 2 and strings <= KENNUNGEN:
            return True
    return False


def _verzweigung(knoten: ast.AST) -> bool:
    if isinstance(knoten, ast.Compare):
        operanden = [knoten.left, *knoten.comparators]
        return any(isinstance(op, (ast.Eq, ast.NotEq))
                   and (_ist_kennung(operanden[i]) or _ist_kennung(operanden[i + 1]))
                   for i, op in enumerate(knoten.ops))
    return isinstance(knoten, ast.MatchValue) and _ist_kennung(knoten.value)


def _schwelle(knoten: ast.AST) -> bool:
    """Kette ``a < x < b`` zaehlt einmal (ein Knoten, ein Fund)."""
    if not isinstance(knoten, ast.Compare):
        return False
    operanden = [knoten.left, *knoten.comparators]
    for i, op in enumerate(knoten.ops):
        if not isinstance(op, (ast.Lt, ast.LtE, ast.Gt, ast.GtE)):
            continue
        links, rechts = operanden[i], operanden[i + 1]
        if (_ist_zahl(rechts) and _ist_messwert(links)) or (
                _ist_zahl(links) and _ist_messwert(rechts)):
            return True
    return False


def _verarbeitung(knoten: ast.AST) -> bool:
    if isinstance(knoten, (ast.FunctionDef, ast.AsyncFunctionDef)):
        return knoten.name in VERARBEITUNGS_FUNKTIONEN
    if isinstance(knoten, ast.Name) and isinstance(knoten.ctx, ast.Load):
        return knoten.id in VERARBEITUNGS_FUNKTIONEN
    if isinstance(knoten, ast.Attribute) and isinstance(knoten.ctx, ast.Load):
        return knoten.attr in VERARBEITUNGS_FUNKTIONEN
    return False


_PYTHON_PRUEFER = ((ID_SAMMLUNG, _sammlung), (ID_VERZWEIGUNG, _verzweigung),
                   (SCHWELLE, _schwelle), (VERARBEITUNG_AUSSEN, _verarbeitung))


def scanne_python_datei(pfad: Path, rel: str) -> list[Fund]:
    quelltext = pfad.read_text(encoding="utf-8")
    zeilen = quelltext.splitlines()
    baum = ast.parse(quelltext, filename=str(pfad))
    funde = []
    for knoten in ast.walk(baum):
        for art, pruefer in _PYTHON_PRUEFER:
            if pruefer(knoten):
                funde.append(Fund(rel, knoten.lineno, art, _auszug(zeilen, knoten.lineno)))
    return sorted(funde, key=lambda f: (f.zeile, f.art))


def scanne_python(wurzeln: Iterable[Path | str], basis: Path = REPO_ROOT) -> list[Fund]:
    """Python-Produktcode: ID_SAMMLUNG, ID_VERZWEIGUNG, SCHWELLE, VERARBEITUNG_AUSSEN."""
    funde: list[Fund] = []
    for pfad in _dateien(wurzeln, (".py",)):
        rel = _relativ(pfad, basis)
        if not _python_ausgenommen(rel):
            funde.extend(scanne_python_datei(pfad, rel))
    return funde


# ------------------------------------------------------- TS/Svelte und Go

_TOKEN_TS = re.compile(
    r"(?P<k>//[^\n]*|/\*.*?\*/|<!--.*?-->)"
    r"|(?P<s>'(?:[^'\\\n]|\\.)*'|\"(?:[^\"\\\n]|\\.)*\"|`(?:[^`\\]|\\.)*`)"
    r"|(?P<i>[A-Za-z_$][\w$]*)"
    r"|(?P<n>\d+(?:\.\d+)?)"
    r"|(?P<o>===|!==|==|!=|=>|<=|>=|[{}\[\]():,;?=.<>\-])"
    r"|(?P<x>\S)", re.DOTALL)
_TOKEN_GO = re.compile(
    r"(?P<k>//[^\n]*|/\*.*?\*/)"
    r"|(?P<s>\"(?:[^\"\\\n]|\\.)*\"|`[^`]*`|'(?:[^'\\\n]|\\.)*')"
    r"|(?P<i>[A-Za-z_][\w]*)"
    r"|(?P<n>\d+(?:\.\d+)?)"
    r"|(?P<o>==|!=|:=|<-|<=|>=|[{}\[\]():,;?=.<>\-])"
    r"|(?P<x>\S)", re.DOTALL)
_OEFFNEN = {"(": ")", "[": "]", "{": "}"}
_VERGLEICH = frozenset({"===", "!==", "==", "!="})
_ORDNUNG = frozenset({"<", "<=", ">", ">="})


@dataclass
class _Token:
    art: str      # "s" (String), "i" (Bezeichner), "n" (Zahl), "o" (Satzzeichen)
    text: str     # String: Inhalt ohne Anfuehrungszeichen
    zeile: int


def _tokens(quelltext: str, muster: re.Pattern[str]) -> list[_Token]:
    umbrueche = [t.start() for t in re.finditer("\n", quelltext)]
    tokens = []
    for treffer in muster.finditer(quelltext):
        art = treffer.lastgroup
        if art in ("k", "x"):
            continue
        text = treffer.group()
        if art == "s":
            text = "" if "${" in text else text[1:-1]
        zeile = bisect.bisect_right(umbrueche, treffer.start() - 1) + 1
        tokens.append(_Token(art, text, zeile))
    return tokens


def _konstanten(tokens: list[_Token], *, go: bool) -> dict[str, str]:
    """Bezeichner, die als Konstante an eine Kennung gebunden sind.

    TS: ``const NAME = 'wind'`` / ``const NAME: Typ = 'wind'``. Go: ``const NAME
    [Typ] = "wind"`` einzeln oder im ``const ( … )``-Block. So wird eine Liste
    aus Konstanten (``AlertableMetrics``) genauso sichtbar wie eine aus Literalen."""
    gebunden: dict[str, str] = {}
    tiefe, im_block = 0, False
    for i, tok in enumerate(tokens):
        if go and tok.text == "const" and i + 1 < len(tokens) and tokens[i + 1].text == "(":
            im_block, tiefe = True, 0
        if im_block and tok.text in ("(", ")"):
            tiefe += 1 if tok.text == "(" else -1
            im_block = tiefe > 0
        if tok.art != "s" or tok.text not in KENNUNGEN or i < 2 or tokens[i - 1].text != "=":
            continue
        namen = [t.text for t in tokens[max(0, i - 5):i - 1]
                 if t.art == "i" and t.zeile == tokens[i - 1].zeile]
        if "const" in namen[:-1]:
            gebunden[namen[namen.index("const") + 1]] = tok.text
        elif go and im_block and namen:
            gebunden[namen[0]] = tok.text
    return gebunden


def _verzweigungs_indizes(tokens: list[_Token]) -> set[int]:
    """Kennungs-Strings direkt neben ``==``/``===``/``!=``/``!==`` oder in einer
    ``case``-Liste (``case "a", "b":``)."""
    treffer: set[int] = set()
    for i, tok in enumerate(tokens):
        if tok.art != "s" or tok.text not in KENNUNGEN:
            continue
        vor = tokens[i - 1] if i > 0 else None
        nach = tokens[i + 1] if i + 1 < len(tokens) else None
        if (vor and vor.art == "o" and vor.text in _VERGLEICH) or (
                nach and nach.art == "o" and nach.text in _VERGLEICH):
            treffer.add(i)
            continue
        j = i - 1
        while j >= 0 and (tokens[j].art == "s" or tokens[j].text == ","):
            j -= 1
        if j >= 0 and tokens[j].art == "i" and tokens[j].text == "case":
            treffer.add(i)
    return treffer


def _schluessel(tokens: list[_Token], i: int) -> bool:
    """Bezeichner als Objektschluessel: ``{ wind: …`` / ``, gust?: …``."""
    tok = tokens[i]
    if tok.art != "i" or tok.text not in KENNUNGEN:
        return False
    j = i + 1
    if j < len(tokens) and tokens[j].text == "?":
        j += 1
    if j >= len(tokens) or tokens[j].text != ":":
        return False
    vor = tokens[i - 1] if i > 0 else None
    return vor is None or vor.text in ("{", ",", ";") or vor.zeile < tok.zeile


def _kennung_an(tokens: list[_Token], i: int, konstanten: dict[str, str]) -> str | None:
    tok = tokens[i]
    if tok.art == "s":
        return tok.text if tok.text in KENNUNGEN else None
    if tok.art == "i" and tok.text in konstanten:
        return konstanten[tok.text]
    return tok.text if _schluessel(tokens, i) else None


def _listen(tokens: list[_Token], verzweigungen: set[int],
            konstanten: dict[str, str]) -> list[int]:
    """Zeilen der innersten Klammer-Spannen mit >= 2 verschiedenen Kennungen.

    Kennungen in einer bereits gemeldeten Unter-Spanne zaehlen fuer die
    aeussere nicht mehr; Verzweigungs-Literale zaehlen nur als Verzweigung."""
    stapel: list[tuple[str, int, set[str]]] = []
    zeilen: list[int] = []
    for i, tok in enumerate(tokens):
        if tok.art == "o" and tok.text in _OEFFNEN:
            stapel.append((_OEFFNEN[tok.text], tok.zeile, set()))
        elif tok.art == "o" and tok.text in (")", "]", "}"):
            if not any(e[0] == tok.text for e in stapel):
                continue
            while stapel[-1][0] != tok.text:
                stapel.pop()
            _, zeile, gefunden = stapel.pop()
            if len(gefunden) >= 2:
                zeilen.append(zeile)
            elif stapel:
                stapel[-1][2].update(gefunden)
        elif stapel and i not in verzweigungen:
            kennung = _kennung_an(tokens, i, konstanten)
            if kennung is not None:
                stapel[-1][2].add(kennung)
    return zeilen


def _operand_rueckwaerts(tokens: list[_Token], ende: int) -> str | None:
    """Bezeichner/Member-Ausdruck, der bei ``ende`` endet (``a.b?.wind_kmh``)."""
    if ende < 0 or tokens[ende].art != "i":
        return None
    teile, j = [tokens[ende].text], ende
    while True:
        if j >= 2 and tokens[j - 1].text == "." and tokens[j - 2].art == "i":
            j -= 2
        elif (j >= 3 and tokens[j - 1].text == "." and tokens[j - 2].text == "?"
              and tokens[j - 3].art == "i"):
            j -= 3
        else:
            return ".".join(reversed(teile))
        teile.append(tokens[j].text)


def _operand_vorwaerts(tokens: list[_Token], start: int) -> str | None:
    teile: list[str] = []
    j = start
    while j < len(tokens) and tokens[j].art == "i":
        teile.append(tokens[j].text)
        if j + 2 < len(tokens) and tokens[j + 1].text == "." and tokens[j + 2].art == "i":
            j += 2
        elif (j + 3 < len(tokens) and tokens[j + 1].text == "?"
              and tokens[j + 2].text == "." and tokens[j + 3].art == "i"):
            j += 3
        else:
            break
    if not teile or (j + 1 < len(tokens) and tokens[j + 1].text in ("(", "[")):
        return None
    return ".".join(teile)


def _ist_messwert_text(text: str | None) -> bool:
    return (text is not None and not text.endswith((".length", ".size"))
            and MESSWERT_MUSTER.search(text) is not None)


def _schwellen_indizes(tokens: list[_Token]) -> list[int]:
    """``<``/``<=``/``>``/``>=`` zwischen Messwert-Bezeichner und Zahl (beide Seiten).
    Aufrufe/Indizes (``max(x) > 3``, ``d["wind"] > 3``) zaehlen nicht."""
    treffer = []
    for i, tok in enumerate(tokens):
        if tok.art != "o" or tok.text not in _ORDNUNG or i == 0:
            continue
        rechts = i + 2 if i + 2 < len(tokens) and tokens[i + 1].text == "-" else i + 1
        if rechts < len(tokens) and tokens[rechts].art == "n" and _ist_messwert_text(
                _operand_rueckwaerts(tokens, i - 1)):
            treffer.append(i)
        elif tokens[i - 1].art == "n" and i + 1 < len(tokens) and _ist_messwert_text(
                _operand_vorwaerts(tokens, i + 1)):
            treffer.append(i)
    return treffer


def _klammer_scan(dateien: list[tuple[Path, str]], *, go: bool) -> list[Fund]:
    """Zwei Durchgaenge: erst Konstanten aller Dateien, dann die Funde."""
    muster = _TOKEN_GO if go else _TOKEN_TS
    liste, zweig, schwelle = ((GO_LISTE, GO_VERZWEIGUNG, GO_SCHWELLE) if go
                              else (FRONTEND_LISTE, FRONTEND_VERZWEIGUNG, FRONTEND_SCHWELLE))
    gelesen = []
    konstanten: dict[str, str] = {}
    for pfad, rel in dateien:
        quelltext = pfad.read_text(encoding="utf-8", errors="replace")
        tokens = _tokens(quelltext, muster)
        konstanten.update(_konstanten(tokens, go=go))
        gelesen.append((rel, quelltext.splitlines(), tokens))
    funde: list[Fund] = []
    for rel, zeilen, tokens in gelesen:
        verzweigungen = _verzweigungs_indizes(tokens)
        funde += [Fund(rel, z, liste, _auszug(zeilen, z))
                  for z in _listen(tokens, verzweigungen, konstanten)]
        funde += [Fund(rel, tokens[i].zeile, zweig, _auszug(zeilen, tokens[i].zeile))
                  for i in sorted(verzweigungen)]
        funde += [Fund(rel, tokens[i].zeile, schwelle, _auszug(zeilen, tokens[i].zeile))
                  for i in _schwellen_indizes(tokens)]
    return funde


def _frontend_ausgenommen(rel: str) -> bool:
    teile = rel.split("/")
    name = teile[-1]
    return (name.endswith((".test.ts", ".spec.ts", ".d.ts")) or ".generated." in name
            or any(t in ("e2e", "__tests__", "node_modules", "generated", ".svelte-kit")
                   for t in teile[:-1]))


def scanne_frontend(wurzeln: Iterable[Path | str], basis: Path = REPO_ROOT) -> list[Fund]:
    """TS/Svelte: FRONTEND_LISTE, FRONTEND_VERZWEIGUNG."""
    dateien = [(p, _relativ(p, basis)) for p in _dateien(wurzeln, (".ts", ".svelte"))]
    return _klammer_scan([(p, r) for p, r in dateien if not _frontend_ausgenommen(r)],
                         go=False)


def scanne_go(wurzeln: Iterable[Path | str], basis: Path = REPO_ROOT) -> list[Fund]:
    """Go: GO_LISTE, GO_VERZWEIGUNG (ohne ``_test.go`` und generierte Dateien)."""
    dateien = [(p, _relativ(p, basis)) for p in _dateien(wurzeln, (".go",))
               if not p.name.endswith("_test.go") and ".generated." not in p.name]
    return _klammer_scan(dateien, go=True)


# ------------------------------------------------------------- Validatoren

def ist_metrik_import(modul: str) -> bool:
    """Metrik-Wissen im Validator (Tech-Lead-Entscheid #3260): Katalog,
    Ampel-Vorlagen, jedes ``app.*``-Modul mit ``metric``/``compare`` im Namen,
    ``output.*`` und ``services.*``. ``app.config``, ``i18n``, ``app.models``,
    ``app.user`` usw. zaehlen nicht. Ein vorangestelltes ``src.`` wird ignoriert."""
    if modul.startswith("src."):
        modul = modul[4:]
    if any(modul == m or modul.startswith(m + ".") for m in VERBOTENE_MODULE):
        return True
    teile = modul.split(".")
    return (len(teile) > 1 and teile[0] == "app"
            and any(w in teile[1] for w in ("metric", "compare")))


def _validator_importe(baum: ast.AST) -> Iterator[int]:
    """Je importiertem Namen eine Zeile — auch verzoegert in Funktionen."""
    for knoten in ast.walk(baum):
        if isinstance(knoten, ast.ImportFrom) and knoten.level == 0 and knoten.module:
            if ist_metrik_import(knoten.module):
                yield from (knoten.lineno for _ in knoten.names)
        elif isinstance(knoten, ast.Import):
            yield from (knoten.lineno for a in knoten.names if ist_metrik_import(a.name))
        elif (isinstance(knoten, ast.Call) and knoten.args
              and isinstance(knoten.args[0], ast.Constant)
              and isinstance(knoten.args[0].value, str)
              and ast.unparse(knoten.func) in ("importlib.import_module", "import_module",
                                               "__import__")
              and ist_metrik_import(knoten.args[0].value)):
            yield knoten.lineno


def scanne_validatoren(wurzeln: Iterable[Path | str], basis: Path = REPO_ROOT) -> list[Fund]:
    """``.claude/hooks/*.py``: VALIDATOR_IMPORT. Verzeichnisse nur flach (``*.py``)."""
    funde: list[Fund] = []
    for wurzel in wurzeln:
        pfad = Path(wurzel)
        dateien = sorted(pfad.glob("*.py")) if pfad.is_dir() else [pfad]
        for datei in dateien:
            quelltext = datei.read_text(encoding="utf-8")
            zeilen = quelltext.splitlines()
            rel = _relativ(datei, basis)
            baum = ast.parse(quelltext, filename=str(datei))
            funde += [Fund(rel, z, VALIDATOR_IMPORT, _auszug(zeilen, z))
                      for z in _validator_importe(baum)]
    return funde


# ------------------------------------------------------------ Gesamtlauf

def scanne_alles(basis: Path = REPO_ROOT) -> list[Fund]:
    """Der Bestand: Python (``src``, ``api``), Frontend, Go, Validatoren."""
    return (scanne_python([basis / "src", basis / "api"], basis)
            + scanne_frontend([basis / "frontend" / "src"], basis)
            + scanne_go([basis / "internal", basis / "cmd"], basis)
            + scanne_validatoren([basis / ".claude" / "hooks"], basis))


def zaehle(funde: Iterable[Fund]) -> dict[str, dict[str, int]]:
    zaehler = Counter((f.datei, f.art) for f in funde)
    tabelle: dict[str, dict[str, int]] = {}
    for (datei, art), anzahl in sorted(zaehler.items()):
        tabelle.setdefault(datei, {})[art] = anzahl
    return tabelle


def vergleiche(funde: list[Fund], ausnahmen: dict, hoechststand_konstante: int) -> list[str]:
    """Verstoesse gegen die Ausnahmeliste (Regeln a–d der Spec); leer = gruen."""
    ist = zaehle(funde)
    soll: dict[str, dict[str, int]] = ausnahmen.get("eintraege", {})
    befunde: list[str] = []
    for datei, arten in sorted(ist.items()):
        for art, anzahl in sorted(arten.items()):
            erlaubt = soll.get(datei, {}).get(art, 0)
            if anzahl > erlaubt:
                stellen = "\n".join(f"    {f}" for f in funde
                                    if f.datei == datei and f.art == art)
                befunde.append(
                    f"(a) NEU: {datei} [{art}] hat {anzahl} Funde, gelistet {erlaubt}. "
                    f"Metrik-Wissen gehoert in den Katalog, Verarbeitung in "
                    f"metric_format (ADR-0127). Fundstellen:\n{stellen}")
    for datei, arten in sorted(soll.items()):
        for art, erlaubt in sorted(arten.items()):
            anzahl = ist.get(datei, {}).get(art, 0)
            if anzahl < erlaubt:
                befunde.append(
                    f"(b) RUECKGANG: {datei} [{art}] hat {anzahl} Funde, gelistet "
                    f"{erlaubt}. Ausnahmeliste verkleinern (python -m "
                    f"tests.helpers.katalog_verarbeitung_scan --schreibe-ausnahmen), "
                    f"damit der Rueckgang festgeschrieben ist.")
    summe = sum(n for arten in soll.values() for n in arten.values())
    hoechst = ausnahmen.get("hoechststand", 0)
    if summe > hoechst:
        befunde.append(f"(c) Summe der Ausnahmeliste {summe} > hoechststand {hoechst}: "
                       "die Liste darf nicht wachsen.")
    if hoechst > hoechststand_konstante:
        befunde.append(f"(d) hoechststand {hoechst} > festgeschriebener Hoechststand "
                       f"{hoechststand_konstante}: beide werden nur gesenkt.")
    return befunde


def lade_ausnahmen(pfad: Path = AUSNAHMEN_PFAD) -> dict:
    return json.loads(pfad.read_text(encoding="utf-8"))


MAIN_REF = "origin/main:tests/unit/ein_katalog_ausnahmen.json"


def _git_show(ref: str) -> str:
    return subprocess.run(["git", "-C", str(REPO_ROOT), "show", ref], check=True,
                          capture_output=True, text=True, timeout=30).stdout


def lade_main_ausnahmen(git_show: Callable[[str], str] = _git_show) -> tuple[dict | None, str]:
    """Die Ausnahmeliste auf ``origin/main`` — oder ``(None, Grund)``, wenn sie
    nicht lesbar ist (kein git, flacher Klon ohne ``origin/main``, Datei dort
    noch nicht vorhanden, kaputtes JSON)."""
    try:
        return json.loads(git_show(MAIN_REF)), ""
    except (OSError, subprocess.SubprocessError, ValueError) as fehler:
        text = getattr(fehler, "stderr", "") or str(fehler)
        return None, f"{MAIN_REF} nicht lesbar: {text.strip()[:200]}"


def vergleiche_mit_main(ausnahmen: dict, main: dict) -> list[str]:
    """Regel e: gegenueber ``origin/main`` darf weder ``hoechststand`` noch die
    Anzahl eines dort bereits gelisteten Eintrags steigen (Liste und Konstante
    zusammen anheben ist kein Ausweg)."""
    befunde = []
    if ausnahmen.get("hoechststand", 0) > main.get("hoechststand", 0):
        befunde.append(f"(e) hoechststand {ausnahmen.get('hoechststand')} > origin/main "
                       f"{main.get('hoechststand')}: die Liste schrumpft nur.")
    for datei, arten in sorted(main.get("eintraege", {}).items()):
        for art, erlaubt in sorted(arten.items()):
            jetzt = ausnahmen.get("eintraege", {}).get(datei, {}).get(art, 0)
            if jetzt > erlaubt:
                befunde.append(f"(e) {datei} [{art}] gelistet {jetzt} > origin/main "
                               f"{erlaubt}: die Liste schrumpft nur.")
    return befunde


def ausnahmen_aus(funde: Iterable[Fund]) -> dict:
    eintraege = zaehle(funde)
    gesamt = sum(n for arten in eintraege.values() for n in arten.values())
    return {"hoechststand": gesamt, "eintraege": eintraege}


def main(argv: list[str]) -> int:
    if argv != ["--schreibe-ausnahmen"]:
        print("Aufruf: python -m tests.helpers.katalog_verarbeitung_scan "
              "--schreibe-ausnahmen", file=sys.stderr)
        return 2
    daten = ausnahmen_aus(scanne_alles())
    AUSNAHMEN_PFAD.write_text(json.dumps(daten, indent=2, ensure_ascii=False,
                                         sort_keys=True) + "\n", encoding="utf-8")
    je_art = Counter()
    for arten in daten["eintraege"].values():
        je_art.update(arten)
    print(f"{AUSNAHMEN_PFAD.relative_to(REPO_ROOT)}: hoechststand {daten['hoechststand']}")
    for art in ARTEN:
        print(f"  {art}: {je_art.get(art, 0)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
