"""Wächter — kein Ausgabepfad formatiert Uhrzeiten je wieder ohne Zeitzone.

Issue #1402: Uhrzeiten erschienen beim Nutzer wiederholt in Weltzeit statt
Ortszeit (7 belegte Vorfälle in vier Wochen). Mechanisch zuverlässig
erkennbare Bugklassen tragen die meisten Fälle:

1. ``irgendwas.astimezone(...)`` DIREKT auf einem Zeitstempel, statt über den
   EINEN zentralen Naiv-Guard (``utils.timezone.local_dt``/``local_hour``/
   ``local_fmt``/``local_stamp``) zu gehen. Ein naiver Zeitstempel ist per
   Hausnorm (#1345) UTC — ``.astimezone()`` deutet ihn aber als Prozess-
   Lokalzeit. Auf dem UTC-Server zufällig richtig, überall sonst falsch
   (genau die Falle aus diesem Issue).
2. Ein Parameter/Klassenattribut namens ``tz``/``_tz``/``alert_tz``, dessen
   Default wortlos auf eine fest verdrahtete Zone zurückfällt
   (``= ZoneInfo("UTC")`` oder ``= None``) statt den Aufrufer zu zwingen,
   eine echte Zone zu liefern.
3. Dieselbe stille Rückfall-Semantik MITTEN im Funktionskörper statt am
   Parameter-Default — vier Ausdrucksformen: ``tz or ZoneInfo("UTC")``
   (``BoolOp``), ``getattr(self, "_tz", ZoneInfo("UTC"))`` (3-Arg-``getattr``),
   ``if tz is None: tz = ZoneInfo("UTC")`` (``If``-Wächter) und
   ``tz if tz is not None else ZoneInfo("UTC")`` (Ternary/``IfExp``). Erkennt
   auch einen hartkodierten Rückfall auf eine ANDERE feste Zone als UTC
   (z. B. ``ZoneInfo("Europe/Vienna")``) — dieselbe Bugklasse, nur mit
   geratener statt fehlender Zone.

Vorbild für Form + Ratsche: ``tests/test_egress_inventory_drift.py``
(Inventar-Drift Python↔Go), ``tests/unit/test_compare_catalog_derives_
from_central_catalog.py`` (``AGGREGATION_CHECK_EXEMPTIONS`` — Ausnahmeliste
darf nur schrumpfen).

KNOWN_VIOLATIONS unten ist die Restliste des Bestandsaufnahme-Katalogs aus
#1402. Die Verankerung dieser Bugklasse selbst kam mit Scheibe A (dieser
Test + `day_window.py`/`trip_report.py`/`trip_report_scheduler.py:1648` +
die zwei entdoppelten Auflöser). Scheibe C hat seither alle Signaturen mit
KLEINER, beherrschbarer Aufrufer-Fläche auf Pflichtparameter umgestellt
(inkl. `trip_report_scheduler.py`s Gewitter-Vorhersage-Kette; zwei dabei
gefundene Parameter erwiesen sich als vollständig ungenutzt und wurden
ersatzlos entfernt statt Pflicht), plus einen dritten und vierten doppelten
Auflöser entdoppelt (`send_multi_location_radar_alert`/`send_multi_location_
official_alert`/`compact_summary._location_tz` → `resolve_location_tz()`/
`location_tz()`). Scheibe D (restliche Einzel-Ausgabestellen ohne
Signatur-Bezug) ist vollständig abgearbeitet. Jeder NEUE, unlistete Fund
lässt den Test rot werden — jeder behobene Fund MUSS aus der Liste entfernt
werden (sonst meldet der Shrink-Test ihn als "veraltet"). Die Liste kann
dadurch nur kleiner werden, nie wachsen.

Zwei Arten der verbleibenden Einträge (s. Kommentar-Blöcke in
KNOWN_VIOLATIONS):
- **DAUERHAFT**: `tz=None` ist hier ein legitimer Domänen-Zustand (z. B.
  "Compare-Ort ohne Zeitzone"), kein vergessener Aufruf — bleibt bewusst
  Optional, keine Scheibe soll das je schließen.
- **Aufrufseite abgesichert (PO-Entscheidung #1402)**: für Funktionen mit
  GROSSER Test-Aufrufer-Fläche (>3 Dateien, teils >40) wird NICHT die
  Signatur umgebaut (Regressionsrisiko in der Golden-/Formatter-Suite ohne
  Sicherheitsgewinn — beide echten Produktiv-Aufrufer übergaben `tz` immer
  schon). Stattdessen erzwingt `test_production_callsites_pass_tz_
  explicitly()` unten, dass jeder Aufruf dieser Funktionen AUS PRODUKTIV-
  CODE (`src/`, `api/` — nicht `tests/`) `tz` explizit übergibt. Zählen NICHT
  mehr als offene Schuld — der Wächter sitzt nur an einer anderen Stelle
  (Aufrufer statt Signatur). Der Bau dieses Wächters deckte sofort 3 echte
  Produktionsbugs auf (comparison.py, compare_html.py, trip_command_
  processor.py "/jetzt") — alle gefixt.

Restliche bekannte Scanner-Lücke (Scope, keine Ausnahme): eine mehrstufige
Koordinaten-Herleitung mit hartkodiertem UTC-Letztfallback (z. B.
``tz_for_coords(...) if lat is not None else ZoneInfo("UTC")`` als
``IfExp`` mit einem ANDEREN Ausdruck als ``body``, nicht der ``tz``-Variable
selbst) ist mit dieser rein strukturellen Prüfung nicht von einer
legitimen, bewusst mehrstufigen Herleitung zu unterscheiden — wo das
tatsächlich der doppelte Auflöser war, wurde es von Hand gefunden und
entdoppelt (`resolve_location_tz`), nicht über den Scanner erzwungen.
"""
from __future__ import annotations

import ast
import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SRC = REPO_ROOT / "src"

# Scanflaeche, zwei Schichten (Issue #1723 hat die zweite ergaenzt):
#
# 1. AUSGABE — das komplette src/output/-Baumwerk (Renderer, Kanäle, Tokens)
#    + die "nachrichtenerzeugenden Services" aus der #1402-Bestandsaufnahme,
#    die selbst Uhrzeiten für Mail/SMS/Telegram/CLI formatieren, aber
#    außerhalb von src/output/ liegen.
# 2. ENTSCHEIDUNG — das komplette src/services/- und api/-Baumwerk: welcher
#    Kalendertag gemeint ist, ob ein Versand fällig ist, ob Ruhezeit gilt.
#    Dort greifen die beiden Fundarten der Entscheidungs-Schicht (Muster A/B,
#    s. _KIND_*-Konstanten unten).
#
# Sechs der sieben _MESSAGING_SERVICE_FILES liegen bereits unter
# src/services/ und sind damit doppelt erfasst — _scan_files() fuehrt die
# Kombination deshalb ueber eine MENGE. Der siebte Eintrag (src/app/cli.py)
# ist der einzige, den die neue Flaeche nicht mitbringt.
#
# NICHT gescannt wird der zentrale Aufloeser/Naiv-Guard selbst
# (``utils/timezone.py``) — der darf ``.astimezone()`` aufrufen, das ist
# seine Aufgabe.
_OUTPUT_DIR = SRC / "output"
_SERVICES_DIR = SRC / "services"
_API_DIR = REPO_ROOT / "api"
_MESSAGING_SERVICE_FILES = [
    # Issue #1465: stand hier als SRC/"app"/... — diesen Pfad gibt es nicht,
    # die Datei liegt unter services/. `_scan_files()` filtert mit
    # `if p.exists()` und liess ihn deshalb WORTLOS fallen: der Waechter hat
    # den Drilldown-Formatter nie gesehen, obwohl sein Detektor beide
    # `raw_astimezone`-Funde dort sofort findet. Neue Eintraege deshalb immer
    # gegen `test_scan_list_paths_all_exist()` unten pruefen.
    SRC / "services" / "trip_command_processor.py",
    SRC / "app" / "cli.py",
    SRC / "services" / "radar_service.py",
    SRC / "services" / "notification_service.py",
    SRC / "services" / "comparison_engine.py",
    SRC / "services" / "trip_report_scheduler.py",
    SRC / "services" / "weather_change_detection.py",
]

_ZONE_ABBR_RE = re.compile(r"\b(MESZ|MEZ|CEST|CET)\b")
_TZ_NAMES = {"tz", "_tz", "alert_tz"}

# Platzhalter für Funde außerhalb jeder Funktion (Modulebene, Klassenrumpf) —
# wörtlich derselbe wie in test_success_status_guard.py /
# test_resolution_loss_guard.py, damit ein Schlüssel aus allen drei Wächtern
# gleich zu lesen ist.
_MODULE_SCOPE = "<module>"

# Namen der beiden Fundarten der Entscheidungs-Schicht (Issue #1723, Epic
# #1722 S1). Sie stehen hier als VERTRAG: die roten Wirkungsnachweise unten
# prüfen den `kind`-Wert wörtlich gegen diese Konstanten, damit ein lautlos
# leerlaufender Detektor nicht in einer Summe über beide Muster verschwindet
# (AC-7).
#   Muster A — Umgebungsuhr: ``date.today()`` / ``datetime.now()`` ohne
#   ``tz``-Argument. ``.utcnow()`` gehoert NICHT dazu (E2).
#   Muster B — festes Nicht-UTC-Zonen-Literal: ``ZoneInfo("Europe/Vienna")``
#   und Verwandte. ``ZoneInfo("UTC")`` gehoert NICHT dazu (E1).
_KIND_AMBIENT_CLOCK = "ambient_clock"
_KIND_HARDCODED_NON_UTC_ZONE = "hardcoded_non_utc_zone"

# Attributnamen der Umgebungsuhr (Muster A). ``utcnow`` steht bewusst NICHT
# hier: es liefert AUSDRUECKLICH Weltzeit, waehrend ``now``/``today`` STILL
# Prozess-Lokalzeit liefern — andere Fehlerklasse (E1/E2 der Spec). Ein
# Ausschluss-Sonderfall waere nur eine zweite Stelle, die dasselbe sagt.
_AMBIENT_CLOCK_ATTRS = {"now", "today"}


def _scan_files() -> list[Path]:
    """Ausgabe- UND Entscheidungs-Schicht, ueber eine MENGE gefuehrt.

    Die Mengenbildung ist keine Kosmetik: sechs der sieben
    ``_MESSAGING_SERVICE_FILES`` liegen unter ``src/services/`` und kaemen mit
    ``+=`` zweimal in die Liste (Issue #1723).
    """
    return sorted(
        {
            *_OUTPUT_DIR.rglob("*.py"),
            *(p for p in _MESSAGING_SERVICE_FILES if p.exists()),
            *_SERVICES_DIR.rglob("*.py"),
            *_API_DIR.rglob("*.py"),
        }
    )


def _is_zoneinfo_utc_call(node: ast.AST) -> bool:
    """Erkennt ``ZoneInfo("UTC")`` als Default-Ausdruck."""
    return (
        isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id == "ZoneInfo"
        and len(node.args) == 1
        and isinstance(node.args[0], ast.Constant)
        and node.args[0].value == "UTC"
    )


def _is_hardcoded_zoneinfo_call(node: ast.AST) -> bool:
    """``ZoneInfo("<beliebige Zone>")`` -- nicht nur "UTC": ein Rückfall auf
    IRGENDEINE fest verdrahtete Zone (z. B. "Europe/Vienna") ist dieselbe
    Bugklasse — der Aufrufer wollte eine echte, aus Daten abgeleitete Zone
    liefern und bekommt stattdessen eine geraten-feste."""
    return (
        isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id == "ZoneInfo"
        and len(node.args) == 1
        and isinstance(node.args[0], ast.Constant)
        and isinstance(node.args[0].value, str)
    )


def _is_silent_default(node: ast.AST) -> bool:
    return _is_zoneinfo_utc_call(node) or (
        isinstance(node, ast.Constant) and node.value is None
    )


def _is_utc_ish(node: ast.AST) -> bool:
    """Rechte Seite eines stillen Rückfalls: ``ZoneInfo("...")`` oder die
    ``UTC``-Konstante aus ``utils.timezone`` als blanker Name."""
    return _is_hardcoded_zoneinfo_call(node) or (
        isinstance(node, ast.Name) and node.id == "UTC"
    )


def _is_tz_like(node: ast.AST) -> bool:
    """Linke Seite: eine Variable/ein Attribut namens tz/_tz/alert_tz."""
    if isinstance(node, ast.Name):
        return node.id in _TZ_NAMES
    if isinstance(node, ast.Attribute):
        return node.attr in _TZ_NAMES
    return False


def _bare_string_statement_ids(tree: ast.AST) -> set[int]:
    """Docstrings (Modul/Klasse/Funktion) UND als String geschriebene
    Zwischenkommentare -- ``ast.Expr(Constant(str))`` als eigene Anweisung.
    Diese sind kein Ausgabe-Text und duerfen Zonen-Kuerzel in der Prosa
    nennen (z. B. "CEST im Sommer, CET im Winter" in einer Docstring)."""
    ids: set[int] = set()
    for node in ast.walk(tree):
        if (
            isinstance(node, ast.Expr)
            and isinstance(node.value, ast.Constant)
            and isinstance(node.value.value, str)
        ):
            ids.add(id(node.value))
    return ids


def _scopes(tree: ast.AST) -> dict[int, str]:
    """``id(knoten)`` → Name des umschließenden Funktionsraums.

    Nachgerüstete Bereichsverfolgung (Issue #1466 AP2/AC-5). Semantik wörtlich
    wie die ``_scopes()``-Generatoren der beiden anderen Wächter: Modulraum
    (``_MODULE_SCOPE``) plus JEDER Funktionsraum, verschachtelte Funktionen als
    EIGENER Raum (ein Fund in ``inner`` gehört zu ``inner``, nicht zu
    ``outer``). Ein Klassenrumpf ist kein eigener Raum — er gehört zum
    Modulraum, genau wie dort.

    Bewusst eine Zuordnungstabelle statt eines Generators: die Fund-Logik
    unten läuft flach über ``ast.walk(tree)``, und daran wird NICHTS geändert
    (die sieben Fundarten bleiben Zeichen für Zeichen dieselben). Die Tabelle
    hängt den Funktionsnamen nachträglich an, statt die Suche umzubauen — so
    kann diese Umschlüsselung keine Fundstelle verlieren.

    Eine ``FunctionDef`` selbst trägt IHREN eigenen Namen, nicht den des
    umgebenden Raums: der Fund ``silent_tz_default`` hängt am
    Parameter-Default, und der gehört fachlich zu genau dieser Funktion
    (Bestandsbeleg: ``trip_report.py::format_email``).
    """
    scopes: dict[int, str] = {id(tree): _MODULE_SCOPE}
    stack: list[tuple[ast.AST, str]] = [(tree, _MODULE_SCOPE)]
    while stack:
        node, scope_name = stack.pop()
        for child in ast.iter_child_nodes(node):
            if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)):
                scopes[id(child)] = child.name
                stack.append((child, child.name))
            else:
                scopes[id(child)] = scope_name
                stack.append((child, scope_name))
    return scopes


def _number_findings(raw: dict[tuple[str, str], dict[int, str]]) -> dict[str, str]:
    """Rohfunde je Funktionsraum → Schlüssel ``"pfad::funktion::ordinal"``.

    Issue #1466 AP2: der frühere Schlüssel ``"pfad:zeile"`` wanderte bei JEDER
    eingefügten Zeile — dieselbe Stelle galt danach gleichzeitig als behoben
    (alter Schlüssel) und als neuer Verstoß (neuer Schlüssel). Das Ordinal ist
    die 0-basierte Position des Fundes INNERHALB seiner Funktion, nach
    Zeilennummer sortiert — dieselbe Zählweise wie in den beiden anderen
    Wächtern. Ohne es fielen die 22 Funde dieses Wächters auf 14 Einträge
    zusammen (AC-4).
    """
    numbered: dict[str, str] = {}
    for (rel, scope_name), by_line in raw.items():
        for ordinal, lineno in enumerate(sorted(by_line)):
            numbered[f"{rel}::{scope_name}::{ordinal}"] = by_line[lineno]
    return numbered


def _find_violations(path: Path) -> dict[str, str]:
    """Verstöße in EINER Datei, als ``{"pfad::funktion::ordinal": "art"}``.

    ``relative_to`` scheitert für Pfade außerhalb des Repos (Wirkungsnachweis-
    Tests scannen synthetische Dateien in ``tmp_path``) — dann bleibt der
    absolute Pfad im Schlüssel, das Format ist nur für Menschenlesbarkeit
    relevant.
    """
    try:
        rel = path.relative_to(REPO_ROOT).as_posix()
    except ValueError:
        rel = str(path)
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    skip_ids = _bare_string_statement_ids(tree)
    scopes = _scopes(tree)
    raw: dict[tuple[str, str], dict[int, str]] = {}

    def record(node: ast.AST, lineno: int, kind: str) -> None:
        """Einen Fund unter seinem Funktionsraum ablegen.

        Zwei Funde auf DERSELBEN Zeile desselben Raums fallen weiterhin
        zusammen (letzter gewinnt) — genau wie beim alten ``"pfad:zeile"``-
        Schlüssel; die Umschlüsselung soll die Fundzahl nicht verändern.
        """
        raw.setdefault((rel, scopes.get(id(node), _MODULE_SCOPE)), {})[lineno] = kind

    for node in ast.walk(tree):
        if (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and node.func.attr == "astimezone"
        ):
            record(node, node.lineno, "raw_astimezone")
        elif (
            isinstance(node, ast.Constant)
            and isinstance(node.value, str)
            and id(node) not in skip_ids
            and _ZONE_ABBR_RE.search(node.value)
        ):
            record(node, node.lineno, "hardcoded_zone_abbrev")
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            a = node.args
            posargs = a.posonlyargs + a.args
            pad = [None] * (len(posargs) - len(a.defaults))
            for arg, default in zip(posargs, pad + list(a.defaults)):
                if arg.arg in _TZ_NAMES and default is not None and _is_silent_default(default):
                    record(node, arg.lineno, "silent_tz_default")
            for arg, default in zip(a.kwonlyargs, a.kw_defaults):
                if arg.arg in _TZ_NAMES and default is not None and _is_silent_default(default):
                    record(node, arg.lineno, "silent_tz_default")
        elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
            if node.target.id in _TZ_NAMES and node.value is not None and _is_zoneinfo_utc_call(node.value):
                record(node, node.lineno, "silent_tz_default")
        elif (
            isinstance(node, ast.BoolOp)
            and isinstance(node.op, ast.Or)
            and len(node.values) == 2
            and _is_tz_like(node.values[0])
            and _is_utc_ish(node.values[1])
        ):
            # z.B. ``effective_tz = tz or ZoneInfo("UTC")``
            record(node, node.lineno, "silent_tz_or_fallback")
        elif (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id == "getattr"
            and len(node.args) == 3
            and isinstance(node.args[1], ast.Constant)
            and node.args[1].value in _TZ_NAMES
            and _is_utc_ish(node.args[2])
        ):
            # z.B. ``getattr(self, "_tz", ZoneInfo("UTC"))``
            record(node, node.lineno, "silent_tz_getattr_fallback")
        elif (
            isinstance(node, ast.If)
            and isinstance(node.test, ast.Compare)
            and _is_tz_like(node.test.left)
            and len(node.test.ops) == 1
            and isinstance(node.test.ops[0], ast.Is)
            and len(node.test.comparators) == 1
            and isinstance(node.test.comparators[0], ast.Constant)
            and node.test.comparators[0].value is None
        ):
            # z.B. ``if tz is None: tz = ZoneInfo("UTC")``
            for stmt in node.body:
                if (
                    isinstance(stmt, ast.Assign)
                    and len(stmt.targets) == 1
                    and _is_tz_like(stmt.targets[0])
                    and _is_utc_ish(stmt.value)
                ):
                    record(node, node.lineno, "silent_tz_none_guard")
        elif isinstance(node, ast.IfExp):
            # z.B. ``tz if tz is not None else ZoneInfo("UTC")`` (und die
            # gespiegelte Reihenfolge).
            if _is_tz_like(node.body) and _is_utc_ish(node.orelse):
                record(node, node.lineno, "silent_tz_ternary")
            elif _is_tz_like(node.orelse) and _is_utc_ish(node.body):
                record(node, node.lineno, "silent_tz_ternary")
        elif (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and node.func.attr in _AMBIENT_CLOCK_ATTRS
        ):
            # Muster A (#1723) — Umgebungsuhr. ``date.today()`` kennt keine
            # Zone und ist deshalb IMMER ein Fund; ``datetime.now()`` nur
            # ohne Zonenargument (``now(zone)`` positional wie ``now(tz=zone)``
            # als Keyword sind die richtige Schreibweise).
            has_tz_arg = bool(node.args) or any(kw.arg == "tz" for kw in node.keywords)
            if node.func.attr == "today" or not has_tz_arg:
                record(node, node.lineno, _KIND_AMBIENT_CLOCK)
        elif _is_hardcoded_zoneinfo_call(node) and not _is_zoneinfo_utc_call(node):
            # Muster B (#1723) — festes Nicht-UTC-Zonen-Literal, in JEDER
            # Ausdrucksform (Modulebene-Zuweisung, Funktionsargument,
            # Rueckfallausdruck), nicht nur in den Mid-Body-Rueckfallformen
            # oberhalb. ``ZoneInfo("UTC")`` ist nach Hausnorm #1345 die
            # richtige Schreibweise und faellt hier bewusst heraus (E1).
            record(node, node.lineno, _KIND_HARDCODED_NON_UTC_ZONE)

    return _number_findings(raw)


def _all_violations() -> dict[str, str]:
    violations: dict[str, str] = {}
    for path in _scan_files():
        violations.update(_find_violations(path))
    return violations


# ---------------------------------------------------------------------------
# Aufrufseiten-Wächter (PO-Entscheidung #1402): diese Funktionen behalten
# einen stillen `tz=None`/`ZoneInfo("UTC")`-Default (Signatur-Umbau würde
# 250+ Aufrufstellen über 65+ Testdateien anfassen, ohne ein echtes
# Produktionsrisiko zu schliessen -- beide echten Aufrufer lieferten `tz`
# immer schon). Stattdessen erzwingt der Scanner unten, dass jeder Aufruf
# aus PRODUKTIVCODE (src/, api/) `tz` explizit als Keyword uebergibt. Tests
# duerfen den Default weiterhin nutzen (legitime Bequemlichkeit).
#
# Enthaelt neben den 6 von der PO benannten Funktionen auch die daran
# gekettelten official_alerts.py-Helfer (`_typ_tag`/`_format_validity`/
# `render_official_alert_telegram`/`_tag_time`/`render_official_alert_sms`)
# -- dieselbe Fehlerklasse, gleiches Prinzip, aber jeweils EIGENE Aufrufer
# ausserhalb von render_official_alert_subject()/render_warn_block().
# ---------------------------------------------------------------------------
_CALLSITE_GUARDED_FUNCTIONS = {
    "format_email",
    "format_sms",
    "render_official_alert_subject",
    "render_warn_block",
    "format_now_text",
    "_build_stage_trend",
    "_typ_tag",
    "_format_validity",
    "render_official_alert_telegram",
    "_tag_time",
    "render_official_alert_sms",
}

# Datei, die jede der obigen Funktionen definiert -- Aufrufe INNERHALB dieser
# Datei sind eng gekoppelte interne Weiterreichung (haeufig positional statt
# `tz=`, z.B. `_typ_tag(n, tz)`) und bereits von Hand verifiziert; sie werden
# hier NICHT erneut verlangt, `tz=` als Keyword zu schreiben. Aufrufe von
# AUSSERHALB dieser Datei (das eigentliche Risiko: ein neuer Aufrufer, der
# `tz` vergisst) werden weiterhin verlangt.
_CALLSITE_GUARDED_DEFINING_FILE = {
    "format_email": "src/output/renderers/trip_report.py",
    "format_sms": "src/output/renderers/sms_trip.py",
    "render_official_alert_subject": "src/output/renderers/alert/official_alerts.py",
    "render_warn_block": "src/output/renderers/alert/official_alerts.py",
    "format_now_text": "src/services/radar_service.py",
    "_build_stage_trend": "src/services/trip_report_scheduler.py",
    "_typ_tag": "src/output/renderers/alert/official_alerts.py",
    "_format_validity": "src/output/renderers/alert/official_alerts.py",
    "render_official_alert_telegram": "src/output/renderers/alert/official_alerts.py",
    "_tag_time": "src/output/renderers/alert/official_alerts.py",
    "render_official_alert_sms": "src/output/renderers/alert/official_alerts.py",
}


def _production_files() -> list[Path]:
    """`src/` + `api/` (rekursiv) — bewusst NICHT `tests/`: dort ist ein
    weggelassenes `tz` legitime Bequemlichkeit, kein Produktionsrisiko."""
    files = sorted((SRC).rglob("*.py"))
    api_dir = REPO_ROOT / "api"
    if api_dir.exists():
        files += sorted(api_dir.rglob("*.py"))
    return files


def _find_missing_tz_callsites(path: Path) -> dict[str, str]:
    """Aufrufe der `_CALLSITE_GUARDED_FUNCTIONS` in EINER Datei ohne
    explizites `tz=`-Keyword. Trifft sowohl Methodenaufrufe (`self.format_
    email(...)`/`x.format_sms(...)`) als auch Modulfunktionen (`render_
    official_alert_subject(...)`)."""
    try:
        rel = path.relative_to(REPO_ROOT).as_posix()
    except ValueError:
        rel = str(path)
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    found: dict[str, str] = {}

    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        name = None
        if isinstance(node.func, ast.Attribute) and node.func.attr in _CALLSITE_GUARDED_FUNCTIONS:
            name = node.func.attr
        elif isinstance(node.func, ast.Name) and node.func.id in _CALLSITE_GUARDED_FUNCTIONS:
            name = node.func.id
        if name is None:
            continue
        if rel == _CALLSITE_GUARDED_DEFINING_FILE.get(name):
            continue  # interne Weiterreichung, s. Kommentar oben
        has_tz_kwarg = any(kw.arg == "tz" for kw in node.keywords)
        if not has_tz_kwarg:
            found[f"{rel}:{node.lineno}"] = f"callsite_missing_tz:{name}"

    return found


def _all_missing_tz_callsites() -> dict[str, str]:
    violations: dict[str, str] = {}
    for path in _production_files():
        violations.update(_find_missing_tz_callsites(path))
    return violations


# ---------------------------------------------------------------------------
# Restliste aus der #1402-Bestandsaufnahme (Scheiben B/C/D) — DARF NUR
# SCHRUMPFEN. Schlüssel = "pfad::funktion::ordinal" (wie vom Scanner geliefert,
# s. _number_findings), Wert = kurze Einordnung. Ein NEUER, hier nicht
# gelisteter Fund ist ein echter Rückfall (Test 1 schlägt fehl). Ein hier
# gelisteter Fund, den der Scanner nicht mehr findet, MUSS entfernt werden
# (Test 2 schlägt sonst fehl, "veraltet") -- das ist der Schrumpf-Nachweis.
#
# UMSCHLÜSSELUNG (#1466 AP2, 2026-08-02): früher "pfad:zeile". Dieser
# Schlüssel wanderte bei jeder eingefügten Zeile; zuletzt galten 16 der 22
# Einträge gleichzeitig als "behoben" und als "neuer Verstoß", ohne dass sich
# eine einzige Codestelle geändert hätte. Die Einträge selbst sind
# UNVERÄNDERT: dieselben Codestellen, dieselben Begründungen, nichts
# gestrichen. Die alte Zeilennummer steht jeweils in der Begründung.
# ---------------------------------------------------------------------------
KNOWN_VIOLATIONS: dict[str, str] = {
    # --- Bewusste, dauerhafte Ausnahmen (keine Scheibe schliesst diese) ---
    # `tz=None` ist hier ein legitimer DOMAENEN-Zustand ("dieser Compare-Ort
    # hat keine aufloesbare Zeitzone"), keine vergessene Aufloesung durch den
    # Aufrufer -- der Stunden-/Zeit-Anteil entfaellt dann bewusst ERSATZLOS
    # (dokumentiert im jeweiligen Docstring), statt eine falsche Ortszeit
    # vorzutaeuschen. Analog `resolve_location_tz()`s eigenem `Optional`-
    # Rueckgabetyp.
    "src/output/renderers/alert/official_alerts.py::official_alerts_to_sms_entries::0": (
        "DAUERHAFT (vormals :363) — official_alerts_to_sms_entries: tz=None "
        "heisst 'Compare-Ort ohne SavedLocation.timezone', Stunde entfaellt "
        "ersatzlos (dokumentiert im Docstring), kein Bug."
    ),
    "src/services/notification_service.py::send_multi_location_radar_alert::0": (
        "DAUERHAFT (vormals :546) — send_multi_location_radar_alert: tz bleibt "
        "bewusster Override-Parameter; die Herleitung selbst wurde entdoppelt "
        "(resolve_location_tz() statt eigener tz_for_coords()-Kopie, #1402 "
        "Auflage 2/Task 8)."
    ),
    # --- Aufrufseite abgesichert (PO-Entscheidung #1402): Signatur bleibt
    # bewusst optional -- 250+ Aufrufstellen ueber 65+ Testdateien fuer diese
    # 6 Funktionen (+ der daran gekettelten official_alerts.py-Helfer)
    # umzubauen wuerde kein Produktionsrisiko schliessen (beide echten
    # Aufrufer lieferten tz immer schon), aber ein erhebliches
    # Regressionsrisiko in der Golden-/Formatter-Suite erzeugen. Stattdessen
    # erzwingt `test_production_callsites_pass_tz_explicitly()` unten, dass
    # JEDER Aufruf aus src/+api/ (nicht tests/) `tz=` explizit uebergibt --
    # zaehlen NICHT mehr als offene Schuld. Beim Bau dieses Wächters selbst
    # deckte er bereits 3 echte fehlende Aufrufe auf (comparison.py:501,
    # compare_html.py Warn-Banner, trip_command_processor.py "/jetzt") —
    # sofort gefixt, s. Commit-Historie.
    "src/output/renderers/sms_trip.py::format_sms::0": "Aufrufseite abgesichert (vormals :258) — format_sms (Wächter: test_production_callsites_pass_tz_explicitly).",
    "src/output/renderers/trip_report.py::<module>::0": "Aufrufseite abgesichert (vormals :55) — TripReportFormatter._tz Klassenattribut (Klassenrumpf = Modulraum), an format_email gekoppelt.",
    "src/output/renderers/trip_report.py::format_email::0": "Aufrufseite abgesichert (vormals :70) — format_email (Wächter: test_production_callsites_pass_tz_explicitly).",
    "src/output/renderers/trip_report.py::format_email::1": "Aufrufseite abgesichert (vormals :120) — Mid-Body-Rückfall zum Default von format_email, daran gekoppelt.",
    "src/output/renderers/alert/official_alerts.py::_format_validity::0": "Aufrufseite abgesichert (vormals :636) — _format_validity (Wächter: test_production_callsites_pass_tz_explicitly).",
    "src/output/renderers/alert/official_alerts.py::_format_validity::1": "Aufrufseite abgesichert (vormals :642) — '… if tz else roh'-Zweig zum Default von _format_validity.",
    "src/output/renderers/alert/official_alerts.py::_format_validity::2": "Aufrufseite abgesichert (vormals :643) — '… if tz else roh'-Zweig zum Default von _format_validity.",
    "src/output/renderers/alert/official_alerts.py::_typ_tag::0": "Aufrufseite abgesichert (vormals :666) — _typ_tag (Wächter: test_production_callsites_pass_tz_explicitly).",
    "src/output/renderers/alert/official_alerts.py::_typ_tag::1": "Aufrufseite abgesichert (vormals :676) — '… if tz else roh'-Zweig zum Default von _typ_tag.",
    "src/output/renderers/alert/official_alerts.py::render_official_alert_subject::0": "Aufrufseite abgesichert (vormals :713) — render_official_alert_subject (Wächter: test_production_callsites_pass_tz_explicitly).",
    "src/output/renderers/alert/official_alerts.py::render_official_alert_subject::1": "Aufrufseite abgesichert (vormals :749) — if-None-Guard zum Default von render_official_alert_subject. Fällt jetzt ehrlich auf UTC zurück (war Europe/Vienna geraten, PO-Fund).",
    "src/output/renderers/alert/official_alerts.py::render_warn_block::0": "Aufrufseite abgesichert (vormals :1473) — render_warn_block (Wächter: test_production_callsites_pass_tz_explicitly).",
    "src/output/renderers/alert/official_alerts.py::render_official_alert_telegram::0": "Aufrufseite abgesichert (vormals :1505) — render_official_alert_telegram (Wächter: test_production_callsites_pass_tz_explicitly).",
    "src/output/renderers/alert/official_alerts.py::_tag_time::0": "Aufrufseite abgesichert (vormals :1565) — _tag_time (Wächter: test_production_callsites_pass_tz_explicitly).",
    # Die zwei rohen .astimezone() standen bis #1466 als ':1580'/':1581' mit
    # dem Vermerk 'in render_warn_block' in der Liste — der Vermerk war durch
    # die Zeilendrift falsch geworden: beide stehen im Rumpf von _tag_time
    # (heute :1586/:1587). Der funktionsbezogene Schlüssel korrigiert die
    # Zuordnung; es sind unverändert dieselben zwei Codestellen.
    "src/output/renderers/alert/official_alerts.py::_tag_time::1": "Aufrufseite abgesichert (vormals :1580) — roher .astimezone() im Rumpf von _tag_time, an dessen Default gekoppelt.",
    "src/output/renderers/alert/official_alerts.py::_tag_time::2": "Aufrufseite abgesichert (vormals :1581) — roher .astimezone() im Rumpf von _tag_time, an dessen Default gekoppelt.",
    "src/output/renderers/alert/official_alerts.py::render_official_alert_sms::0": "Aufrufseite abgesichert (vormals :1690) — render_official_alert_sms (Wächter: test_production_callsites_pass_tz_explicitly).",
    "src/services/radar_service.py::format_now_text::0": "Aufrufseite abgesichert (vormals :219) — format_now_text (Wächter: test_production_callsites_pass_tz_explicitly).",
    "src/services/trip_report_scheduler.py::_build_stage_trend::0": "Aufrufseite abgesichert (vormals :1365) — _build_stage_trend (Wächter: test_production_callsites_pass_tz_explicitly).",
    # ORDINAL-VERSCHIEBUNG (#1723): Muster A findet in _build_stage_trend ein
    # `date.today()` (:1812) VOR dem Ternary (:1869) — der Ternary rutscht
    # dadurch von ::1 auf ::2. Dieselben zwei Codestellen wie bisher, plus der
    # neue Fund dazwischen; nichts gestrichen.
    "src/services/trip_report_scheduler.py::_build_stage_trend::1": "Muster A (:1812) — `today = date.today()` datiert den Etappen-Trend auf die Serveruhr statt auf die Ortszeit der Etappe (#1726).",
    "src/services/trip_report_scheduler.py::_build_stage_trend::2": "Aufrufseite abgesichert (vormals :1427, jetzt :1869) — Ternary-Rückfall zum Default von _build_stage_trend, daran gekoppelt.",
    # -----------------------------------------------------------------------
    # ENTSCHEIDUNGS-SCHICHT (Issue #1723, Epic #1722 S1) — Bestandsaufnahme
    # von `src/services/**` + `api/**`, gemessen am 2026-08-11 gegen
    # origin/main `0db5eec6` (nach #1724, das zwei Europe/Vienna-Stellen
    # entfernt hat). 53 Einträge, ausschliesslich per AST-Scan erhoben, nicht
    # per grep gezaehlt. Sie sind AUFGENOMMEN, nicht entschuldigt: diese
    # Lieferung blockt nur Neuzugaenge, die Behebung traegt #1726 (S4).
    # -----------------------------------------------------------------------
    # --- Muster A: Umgebungsuhr (`date.today()` / `datetime.now()` ohne tz) ---
    "api/routers/compare.py::run_comparison::0": "Muster A (:53) — Sofort-Vergleich nimmt die Serveruhr als 'jetzt' (#1726).",
    "api/routers/compare.py::run_comparison::1": "Muster A (:55) — Zieltag 'heute' vom Server, nicht vom Ort (#1726).",
    "api/routers/compare.py::run_comparison::2": "Muster A (:58) — Zieltag 'morgen' vom Server, nicht vom Ort (#1726).",
    "api/routers/debug.py::trigger_radar_alert::0": "Muster A (:61) — Debug-Ausloeser datiert auf die Serveruhr (#1726).",
    "src/output/renderers/email/compare_html.py::_compute_next_send::0": "Muster A (:1377) — naechste Sendezeit gegen den Servertag geprueft (#1726).",
    "src/services/alert_briefing_anchor.py::briefing_target_day_is_current::0": "Muster A (:169) — Briefing-Anker faellt auf den Servertag zurueck (#1726).",
    "src/services/compare_preview_service.py::_resolve_target_date::0": "Muster A (:250) — Vorschau-Zieltag vom Server (#1726).",
    "src/services/comparison_engine.py::dict_to_comparison_result::0": "Muster A (:407) — Zieltag beim Einlesen vom Server (#1726).",
    "src/services/gpx_processing.py::compute_default_start_date::0": "Muster A (:189) — GPX-Vorgabestart vom Servertag (#1726).",
    "src/services/gpx_processing.py::compute_default_start_date::1": "Muster A (:193) — zweiter Rueckfall auf den Servertag (#1726).",
    "src/services/gpx_processing.py::gpx_to_stage_data::0": "Muster A (:223) — Etappendatum faellt auf den Servertag zurueck (#1726).",
    "src/services/inbound_telegram_reader.py::_find_active_trip::0": "Muster A (:358) — 'aktive Tour heute' gegen den Servertag (#1726).",
    "src/services/notification_service.py::_target_date_from_report::0": "Muster A (:1676) — Zieltag des Berichts vom Server (#1726).",
    "src/services/official_alerts/massif_closure.py::_do_request::0": "Muster A (:102) — Abfrage-Datum der franzoesischen Quelle vom Server (#1726).",
    "src/services/official_alerts/massif_closure.py::fetch::0": "Muster A (:127) — Zeitstempel fuer `last_run` ohne Zone (#1726).",
    "src/services/official_alerts/meteo_forets.py::covers::0": "Muster A (:130) — Saison-Fenster gegen den Servermonat (#1726).",
    "src/services/preview_service.py::_resolve_target_date::0": "Muster A (:94) — Vorschau-Zieltag vom Server (#1726).",
    "src/services/scheduler_dispatch_service.py::_auto_pause_expired_presets::0": "Muster A (:79) — Ablauf eines Presets gegen den Servertag (#1726).",
    "src/services/scheduler_dispatch_service.py::send_one_compare_preset::0": "Muster A (:368) — Zieltag des Vergleichs-Versands vom Server (#1726).",
    "src/services/trip_command_processor.py::_show_now::0": "Muster A (:1227) — '/jetzt' datiert auf den Servertag (#1726).",
    "src/services/trip_command_processor.py::_show_status::0": "Muster A (:1076) — '/status' datiert auf den Servertag (#1726).",
    "src/services/trip_report_scheduler.py::_clamp_segments_to_today::0": "Muster A (:1497) — Segment-Beschnitt gegen den Servertag (#1726).",
    "src/services/trip_report_scheduler.py::_collect_future_stage_weather::0": "Muster A (:2205) — 'zukuenftige Etappen' ab Servertag (#1726).",
    "src/services/trip_report_scheduler.py::_send_trip_report_outcome::0": "Muster A (:932) — Test-Rueckfall vergleicht Zieltag mit Servertag (#1726).",
    "src/services/trip_report_scheduler.py::select_test_stage::0": "Muster A (:765) — Test-Etappenwahl ab Servertag (#1726).",
    # --- Muster B: festes Nicht-UTC-Zonen-Literal (namentlich #1726/S4) ---
    "src/services/alert_daily_limit.py::<module>::0": "Muster B (:23) — `VIENNA = ZoneInfo('Europe/Vienna')` als Tagesgrenze des Alarm-Kontingents; ADR-0051, Behebung #1726.",
    "src/services/deviation_alert_engine.py::<module>::0": "Muster B (:31) — `VIENNA = ZoneInfo('Europe/Vienna')` als Ruhezeit-Zone; ADR-0051, Behebung #1726.",
    # --- Bestehende Fundart `raw_astimezone` auf der NEU hinzugekommenen
    # Flaeche: kein neuer Detektor, nur groesserer Geltungsbereich. Viele davon
    # sind Umrechnungen NACH UTC (nach Hausnorm #1345 unauffaellig) — der
    # Scanner unterscheidet das strukturell nicht, deshalb gelistet statt
    # ausgenommen.
    "src/services/alert_briefing_anchor.py::record_briefing_sent::0": "raw_astimezone (:195) — Normalisierung des Sendezeitpunkts nach UTC.",
    "src/services/alert_daily_limit.py::_vienna_date_str::0": "raw_astimezone (:32) — Tagesgrenze ueber die feste VIENNA-Zone, an Muster B oben gekoppelt (#1726).",
    "src/services/compare_location_weather_source.py::_window_bound::0": "raw_astimezone (:39) — Fenstergrenze aus lokalem Tag + Stunde.",
    "src/services/compare_location_weather_source.py::fetch::0": "raw_astimezone (:116) — lokaler Tag des Vergleichsorts.",
    "src/services/compare_official_alert.py::_day_window_end::0": "raw_astimezone (:271) — lokales 'jetzt' des Vergleichsorts.",
    "src/services/compare_official_alert.py::_day_window_end::1": "raw_astimezone (:275) — Fensterende zurueck nach UTC.",
    "src/services/deviation_alert_engine.py::is_quiet_hours::0": "raw_astimezone (:112) — Ruhezeit gegen die feste VIENNA-Zone, an Muster B oben gekoppelt (#1726).",
    "src/services/forecast_budget.py::_today_utc::0": "raw_astimezone (:130) — Kontingent-Tag bewusst in UTC (Zaehlwerk, kein Nutzerdatum).",
    "src/services/official_alerts/meteoalarm_budget.py::_now_ts::0": "raw_astimezone (:167) — Kontingent-Zeitstempel bewusst in UTC.",
    "src/services/official_alerts/meteoalarm_budget.py::_today_utc::0": "raw_astimezone (:176) — Kontingent-Tag bewusst in UTC.",
    "src/services/scheduler_dispatch_service.py::run_compare_presets_daily::0": "raw_astimezone (:179) — Faelligkeit in der Ortszone des Presets (#1724).",
    "src/services/segment_weather.py::_aggregate_for_segment::0": "raw_astimezone (:254) — Segmentbeginn auf volle UTC-Stunde.",
    "src/services/segment_weather.py::_aggregate_for_segment::1": "raw_astimezone (:257) — Segmentende auf volle UTC-Stunde.",
    "src/services/stage_weather.py::_to_utc_date::0": "raw_astimezone (:62) — Etappendatum in UTC.",
    "src/services/trip_alert.py::_briefing_precip_for_onset::0": "raw_astimezone (:872) — Einsetzstunde auf volle UTC-Stunde.",
    "src/services/trip_alert.py::check_radar_alerts::0": "raw_astimezone (:1092) — Einsetzzeit in der Ortszone ausgegeben.",
    "src/services/trip_segments.py::convert_trip_to_segments::0": "raw_astimezone (:184) — Segmentstart aus Etappentag + Startstunde.",
    "src/services/trip_segments.py::convert_trip_to_segments::1": "raw_astimezone (:189) — Segmentende aus Folgetag + Startstunde.",
    "src/services/trip_segments.py::convert_trip_to_segments::2": "raw_astimezone (:275) — Ankunftstag in der Zielortzone.",
    "src/services/trip_segments.py::convert_trip_to_segments::3": "raw_astimezone (:277) — Tagesende aus Ankunftstag + Endstunde.",
    "src/services/weather_cache.py::get::0": "raw_astimezone (:126) — Cache-Schluessel Fensterbeginn in UTC.",
    "src/services/weather_cache.py::get::1": "raw_astimezone (:127) — Cache-Schluessel Fensterende in UTC.",
    "src/services/weather_cache.py::put::0": "raw_astimezone (:177) — Cache-Ablage Fensterbeginn in UTC.",
    "src/services/weather_cache.py::put::1": "raw_astimezone (:178) — Cache-Ablage Fensterende in UTC.",
    "src/services/weather_extractor.py::_to_naive_utc::0": "raw_astimezone (:32) — Naiv-Guard nach Hausnorm #1345 (naiv == UTC).",
}


def test_scan_list_paths_all_exist():
    """GIVEN die feste Dateiliste des Wächters
    WHEN ein Eintrag auf einen Pfad zeigt, den es nicht (mehr) gibt
    THEN ist das ein blinder Fleck, KEIN grüner Wächter.

    Issue #1465: ``SRC/"app"/"trip_command_processor.py"`` existierte nie (die
    Datei liegt unter ``services/``). ``_scan_files()`` filtert mit
    ``if p.exists()`` und liess den Eintrag wortlos fallen — die Datei wurde
    nie gescannt, der Wächter blieb grün, und zwei ``raw_astimezone``-Stellen
    im Telegram-Drilldown schliefen dort monatelang. Ein Wächter, der nichts
    findet, weil er nichts ansieht, ist immer grün.
    """
    missing = [str(p.relative_to(REPO_ROOT)) for p in _MESSAGING_SERVICE_FILES
               if not p.exists()]
    assert not missing, (
        "Diese Einträge in _MESSAGING_SERVICE_FILES zeigen ins Leere und "
        f"werden still uebersprungen: {missing} — Pfad korrigieren oder "
        "Eintrag entfernen (verschoben/geloescht), nie einfach stehenlassen."
    )


def test_no_unlisted_output_timezone_violations():
    """GIVEN der Scan über src/output/** + die nachrichtenerzeugenden Services
    WHEN ein Fund NICHT in KNOWN_VIOLATIONS steht
    THEN ist das ein neuer, bislang unbemerkter Rückfall in Weltzeit-statt-
    Ortszeit — der Test benennt Datei:Zeile und Art des Fundes.
    """
    found = _all_violations()
    unlisted = {k: v for k, v in found.items() if k not in KNOWN_VIOLATIONS}
    assert not unlisted, (
        "Neue Uhrzeiten-ohne-Zeitzone-Verstöße im Ausgabepfad entdeckt "
        "(Issue #1402) — entweder über utils.timezone.local_dt/local_hour/"
        "local_fmt/local_stamp beheben, oder falls bewusst hingenommen: in "
        f"KNOWN_VIOLATIONS eintragen. Code reference: {sorted(unlisted.items())}"
    )


def test_known_violations_only_shrink():
    """Die Restliste ist Übergangs-Buchhaltung für #1402 Scheiben C/D und darf
    nur kleiner werden. Sobald eine gelistete Stelle behoben ist (der Scanner
    sie nicht mehr findet), MUSS der Eintrag entfernt werden — sonst bliebe
    die Liste eine Dauereinrichtung statt eines Fortschrittsnachweises."""
    found = _all_violations()
    stale = sorted(k for k in KNOWN_VIOLATIONS if k not in found)
    assert not stale, (
        "Diese Stellen sind inzwischen behoben (Scanner findet sie nicht "
        f"mehr): {stale} — aus KNOWN_VIOLATIONS entfernen (die Liste darf "
        "nur schrumpfen)."
    )


def test_production_callsites_pass_tz_explicitly():
    """PO-Entscheidung #1402: statt die Signatur der 6 grossflaechigen
    Funktionen (+ ihrer official_alerts.py-Kettenhelfer) umzubauen (250+
    Aufrufstellen, 65+ Testdateien, kein Produktionsrisiko-Gewinn), sitzt der
    Wächter an der Aufrufseite. JEDER Aufruf aus PRODUKTIVCODE (src/, api/)
    muss `tz=` explizit übergeben — Tests dürfen den stillen Default weiter
    nutzen (legitime Bequemlichkeit, kein Produktionspfad).
    """
    missing = _all_missing_tz_callsites()
    assert not missing, (
        "Produktivcode ruft eine der grossflaechigen Funktionen "
        f"({sorted(_CALLSITE_GUARDED_FUNCTIONS)}) ohne explizites `tz=` auf "
        f"(Issue #1402) — Code reference: {sorted(missing.items())}"
    )


def test_scanner_detects_missing_tz_callsite_in_synthetic_production_file(tmp_path):
    """Wirkungsnachweis: ein synthetischer Aufruf von `format_email(...)`
    OHNE `tz=` in einer Datei unter einem `src/`-artigen Pfad wird erkannt."""
    src_like = tmp_path / "src" / "services"
    src_like.mkdir(parents=True)
    bad_file = src_like / "synthetic_caller.py"
    bad_file.write_text(
        "def send():\n"
        "    formatter.format_email(segments, trip_name, report_type)\n",
        encoding="utf-8",
    )
    found = _find_missing_tz_callsites(bad_file)
    assert any(v == "callsite_missing_tz:format_email" for v in found.values()), (
        f"Scanner hat den fehlenden tz=-Aufruf nicht erkannt: {found}"
    )


def test_scanner_ignores_callsite_with_explicit_tz_kwarg(tmp_path):
    """Gegenprobe: derselbe Aufruf MIT `tz=` wird nicht gemeldet — sonst
    wäre der Wächter selbst nach korrekter Übergabe nie grün zu bekommen."""
    src_like = tmp_path / "src" / "services"
    src_like.mkdir(parents=True)
    good_file = src_like / "synthetic_caller_ok.py"
    good_file.write_text(
        "def send():\n"
        "    formatter.format_email(segments, trip_name, report_type, tz=alert_tz)\n",
        encoding="utf-8",
    )
    found = _find_missing_tz_callsites(good_file)
    assert not found, f"Aufruf MIT tz= faelschlich als Verstoß gezaehlt: {found}"


def test_scanner_detects_raw_astimezone_in_synthetic_output_file(tmp_path):
    """Wirkungsnachweis: eine SYNTHETISCHE Datei mit genau dem Bug-Muster
    (rohes .astimezone() auf einem Zeitstempel) wird erkannt — beweist, dass
    der Scanner nicht durch einen Parser-/Pfad-Fehler leer läuft und der
    Wächter kein zahnloses Bestandsprotokoll ist."""
    bad_file = tmp_path / "synthetic_bad_renderer.py"
    bad_file.write_text(
        "def render(dp, tz):\n"
        "    return dp.ts.astimezone(tz).strftime('%H:%M')\n",
        encoding="utf-8",
    )
    found = _find_violations(bad_file)
    assert any(v == "raw_astimezone" for v in found.values()), (
        f"Scanner hat den synthetischen .astimezone()-Verstoß nicht erkannt: {found}"
    )


def test_scanner_detects_mid_body_silent_fallbacks_in_synthetic_output_file(tmp_path):
    """Wirkungsnachweis für die drei Mid-Body-Rückfallformen (PO-Auflage zu
    Scheibe C): ``tz or ZoneInfo("UTC")``, ``getattr(self, "_tz", ...)``,
    ``if tz is None: tz = ZoneInfo(...)`` und die Ternary-Variante werden
    ALLE erkannt — nicht nur der Parameter-Default."""
    bad_file = tmp_path / "synthetic_mid_body_fallbacks.py"
    bad_file.write_text(
        "from zoneinfo import ZoneInfo\n"
        "\n"
        "def a(tz=None):\n"
        "    effective_tz = tz or ZoneInfo('UTC')\n"
        "    return effective_tz\n"
        "\n"
        "class C:\n"
        "    def b(self):\n"
        "        tz = getattr(self, '_tz', ZoneInfo('UTC'))\n"
        "        return tz\n"
        "\n"
        "def c(tz=None):\n"
        "    if tz is None:\n"
        "        tz = ZoneInfo('Europe/Vienna')\n"
        "    return tz\n"
        "\n"
        "def d(tz=None):\n"
        "    return tz if tz is not None else ZoneInfo('UTC')\n",
        encoding="utf-8",
    )
    found = _find_violations(bad_file)
    kinds = set(found.values())
    assert "silent_tz_or_fallback" in kinds, f"'or ZoneInfo(...)' nicht erkannt: {found}"
    assert "silent_tz_getattr_fallback" in kinds, f"getattr-Rückfall nicht erkannt: {found}"
    assert "silent_tz_none_guard" in kinds, f"'if tz is None'-Guard nicht erkannt: {found}"
    assert "silent_tz_ternary" in kinds, f"Ternary-Rückfall nicht erkannt: {found}"
    # Zusätzlich: die Funktionssignaturen a()/c() selbst tragen ebenfalls
    # einen stillen `tz=None`-Default -- auch das muss weiterhin anschlagen.
    assert "silent_tz_default" in kinds, f"Parameter-Default nicht (mehr) erkannt: {found}"


def test_scanner_ignores_astimezone_inside_resolver_pattern_when_file_excluded():
    """utils/timezone.py selbst (der EINE Aufloeser/Naiv-Guard) wird nicht
    gescannt — sonst würde der Wächter seine eigene Referenz-Implementierung
    als Verstoß melden."""
    resolver = SRC / "utils" / "timezone.py"
    assert resolver not in _scan_files(), (
        "utils/timezone.py darf nicht im Scan-Set liegen — es IST der "
        "zentrale Aufloeser und ruft .astimezone() legitim auf."
    )


def test_scanner_ignores_zone_abbreviation_mentioned_only_in_docstring(tmp_path):
    """Eine Docstring, die 'CEST'/'CET' beschreibend erwähnt (z. B. 'CEST im
    Sommer, CET im Winter'), ist kein Ausgabe-Literal und darf nicht als
    Verstoß zählen — sonst müsste man ehrliche Doku umschreiben, um den
    Wächter grün zu bekommen (F002-Analogie zu test_egress_inventory_drift).
    """
    docstring_file = tmp_path / "synthetic_docstring_only.py"
    docstring_file.write_text(
        'def f():\n'
        '    """Das Kuerzel ist zeitpunktabhaengig (CEST im Sommer, CET im '
        'Winter)."""\n'
        '    return 1\n',
        encoding="utf-8",
    )
    found = _find_violations(docstring_file)
    assert not found, f"Docstring-Erwähnung faelschlich als Verstoß gezaehlt: {found}"


# ---------------------------------------------------------------------------
# Entscheidungs-Schicht (Issue #1723, Epic #1722 S1)
#
# Der Wächter oben bewacht die DARSTELLUNG einer Uhrzeit. Die wiederkehrenden
# Zeitzonen-Bugs sitzen aber in der ENTSCHEIDUNG — welcher Kalendertag gemeint
# ist, ob ein Versand fällig ist, ob Ruhezeit gilt. Die Tests unten dehnen den
# Nachweis auf `src/services/**` + `api/**` aus (Scanfläche, AC-1) und auf die
# beiden dort greifenden Fundarten (Muster A/B, AC-2/AC-3/AC-9) inklusive der
# beiden bewussten Nicht-Fänge (E1/E2, AC-4/AC-5).
#
# Die synthetischen Dateien liegen bewusst unter `src/services/`- bzw.
# `api/`-artigen Pfaden in `tmp_path` — genau die Bäume, die `src/output/**`
# NICHT enthält.
# ---------------------------------------------------------------------------


def _scope_of(key: str) -> str:
    """Funktionsanteil aus einem Fundschlüssel ``"pfad::funktion::ordinal"``."""
    return key.split("::")[-2]


def test_scan_scope_includes_services_and_api_and_is_not_empty():
    """GIVEN die Entscheidungs-Schicht `src/services/**` + `api/**`
    WHEN `_scan_files()` die Scanfläche aufzählt
    THEN liegt JEDE `.py`-Datei beider Bäume darin, die Fläche ist nicht leer,
    kein Eintrag doppelt und keiner ausserhalb der (alten + neuen) Fläche.

    Bauform von `test_scan_scope_excludes_go_internal_tree` in
    `tests/test_success_status_guard.py`: eine Scanfläche, die nichts ansieht,
    ist immer grün (#1465). Die Doppelt-Prüfung sichert zusätzlich, dass die
    Kombination über eine MENGE geführt wird — sechs der sieben
    `_MESSAGING_SERVICE_FILES` liegen bereits unter `src/services/` und würden
    sonst zweimal gescannt.
    """
    services_dir = SRC / "services"
    api_dir = REPO_ROOT / "api"
    services_files = set(services_dir.rglob("*.py"))
    api_files = set(api_dir.rglob("*.py"))
    assert services_files and api_files, (
        "Vorbedingung verletzt: src/services/ oder api/ enthaelt keine .py-"
        "Datei — dann prueft dieser Test nichts."
    )

    scanned = _scan_files()
    assert scanned, "_scan_files() liefert eine LEERE Scanflaeche."
    assert len(scanned) == len(set(scanned)), (
        "Scanflaeche enthaelt Dateien doppelt — die Kombination aus "
        "src/output/**, _MESSAGING_SERVICE_FILES, src/services/** und api/** "
        "muss ueber eine Menge gefuehrt werden (sorted({*...}), nicht +=): "
        f"{sorted(str(p) for p in scanned if scanned.count(p) > 1)}"
    )

    scanned_set = set(scanned)
    missing_services = sorted(
        p.relative_to(REPO_ROOT).as_posix() for p in services_files - scanned_set
    )
    assert not missing_services, (
        "Diese Dateien aus src/services/ liegen NICHT in der Scanflaeche — die "
        "Entscheidungs-Schicht ist damit unbewacht (Issue #1723): "
        f"{missing_services}"
    )
    missing_api = sorted(
        p.relative_to(REPO_ROOT).as_posix() for p in api_files - scanned_set
    )
    assert not missing_api, (
        "Diese Dateien aus api/ liegen NICHT in der Scanflaeche — die "
        "Entscheidungs-Schicht ist damit unbewacht (Issue #1723): "
        f"{missing_api}"
    )

    allowed = (
        set(_OUTPUT_DIR.rglob("*.py"))
        | set(_MESSAGING_SERVICE_FILES)
        | services_files
        | api_files
    )
    outside = sorted(str(p) for p in scanned_set - allowed)
    assert not outside, (
        "Scanflaeche greift ueber die vereinbarte Flaeche hinaus "
        f"(src/output/**, _MESSAGING_SERVICE_FILES, src/services/**, api/**): {outside}"
    )


def test_scanner_detects_ambient_clock_in_synthetic_services_file(tmp_path):
    """GIVEN eine synthetische Datei unter einem `src/services/`-artigen Pfad
    mit `date.today()` und `datetime.now()` OHNE `tz`-Argument
    WHEN der Scanner laeuft
    THEN meldet er genau diese zwei Stellen als `ambient_clock` — und die
    beiden `datetime.now(...)`-Aufrufe MIT Zone nicht.

    Wirkungsnachweis fuer Muster A, ausserhalb von `src/output/`. Der
    `kind`-Wert wird woertlich geprueft (AC-7): eine blosse `assert found`-
    Summe wuerde einen lautlos leerlaufenden Muster-A-Detektor verdecken,
    solange Muster B noch Funde liefert.
    """
    services_like = tmp_path / "src" / "services"
    services_like.mkdir(parents=True)
    bad_file = services_like / "synthetic_decision_clock.py"
    bad_file.write_text(
        "from datetime import date, datetime\n"
        "\n"
        "def faellig_heute():\n"
        "    return date.today()\n"
        "\n"
        "def naechster_lauf():\n"
        "    return datetime.now()\n"
        "\n"
        "def mit_zone_keyword(zone):\n"
        "    return datetime.now(tz=zone)\n"
        "\n"
        "def mit_zone_positional(zone):\n"
        "    return datetime.now(zone)\n",
        encoding="utf-8",
    )
    found = _find_violations(bad_file)
    assert len(found) == 2, (
        f"erwartete 2 Funde (date.today() + datetime.now() ohne tz), gefunden "
        f"{len(found)}: {found}"
    )
    assert set(found.values()) == {_KIND_AMBIENT_CLOCK}, (
        f"erwartete ausschliesslich Fundart {_KIND_AMBIENT_CLOCK!r}, "
        f"gefunden: {sorted(set(found.values()))}"
    )
    assert {_scope_of(k) for k in found} == {"faellig_heute", "naechster_lauf"}, (
        "Muster A haengt an den falschen Funktionen — erwartet "
        f"faellig_heute + naechster_lauf, gefunden: {sorted(found)}"
    )


def test_scanner_detects_hardcoded_non_utc_zone_in_synthetic_api_file(tmp_path):
    """GIVEN eine synthetische Datei unter einem `api/`-artigen Pfad mit
    `ZoneInfo("Europe/Vienna")`
    WHEN der Scanner laeuft
    THEN meldet er die Stelle als `hardcoded_non_utc_zone`.

    Wirkungsnachweis fuer Muster B, ausserhalb von `src/output/` und
    ausserhalb der bisherigen Mid-Body-Rueckfallformen (BoolOp/getattr/If/
    IfExp): eine schlichte Zuweisung im Funktionsrumpf ist bislang unsichtbar.
    Auch hier wird der `kind`-Wert woertlich geprueft (AC-7).
    """
    api_like = tmp_path / "api" / "routers"
    api_like.mkdir(parents=True)
    bad_file = api_like / "synthetic_decision_zone.py"
    bad_file.write_text(
        "from zoneinfo import ZoneInfo\n"
        "\n"
        "def fensterbeginn():\n"
        "    zone = ZoneInfo('Europe/Vienna')\n"
        "    return zone\n",
        encoding="utf-8",
    )
    found = _find_violations(bad_file)
    assert len(found) == 1, (
        f"erwartete 1 Fund (ZoneInfo('Europe/Vienna')), gefunden {len(found)}: {found}"
    )
    assert set(found.values()) == {_KIND_HARDCODED_NON_UTC_ZONE}, (
        f"erwartete Fundart {_KIND_HARDCODED_NON_UTC_ZONE!r}, "
        f"gefunden: {sorted(set(found.values()))}"
    )
    assert {_scope_of(k) for k in found} == {"fensterbeginn"}, (
        f"Muster B haengt an der falschen Funktion: {sorted(found)}"
    )


def test_scanner_ignores_utc_zone_literal_but_still_flags_the_guessed_zone(tmp_path):
    """GIVEN eine synthetische Datei, die BEIDES enthaelt — ein geratenes
    Nicht-UTC-Zonen-Literal und ein `ZoneInfo("UTC")`
    WHEN der Scanner laeuft
    THEN meldet er genau EINEN Fund, und zwar das geratene Literal.

    Gegenprobe zu E1 als DIFFERENZ, nicht als blosses "UTC wird nicht
    gefangen": letzteres waere heute schon gruen, weil ueberhaupt nichts
    gefangen wird — ein unfehlbarer Test. Nach Hausnorm #1345 ist ein naiver
    Zeitstempel UTC; bekaempft wird die GERATENE Ortszone, nicht UTC.
    """
    api_like = tmp_path / "api" / "routers"
    api_like.mkdir(parents=True)
    mixed_file = api_like / "synthetic_utc_vs_guessed.py"
    mixed_file.write_text(
        "from zoneinfo import ZoneInfo\n"
        "\n"
        "def geratene_zone():\n"
        "    return ZoneInfo('Europe/Rome')\n"
        "\n"
        "def ehrliche_weltzeit():\n"
        "    return ZoneInfo('UTC')\n",
        encoding="utf-8",
    )
    found = _find_violations(mixed_file)
    assert len(found) == 1, (
        "erwartete genau 1 Fund (nur das geratene Nicht-UTC-Literal), gefunden "
        f"{len(found)}: {found}"
    )
    assert {_scope_of(k) for k in found} == {"geratene_zone"}, (
        "der einzige Fund muss das GERATENE Literal sein, nicht ZoneInfo('UTC'): "
        f"{sorted(found)}"
    )
    assert set(found.values()) == {_KIND_HARDCODED_NON_UTC_ZONE}, (
        f"erwartete Fundart {_KIND_HARDCODED_NON_UTC_ZONE!r}, "
        f"gefunden: {sorted(set(found.values()))}"
    )


def test_scanner_ignores_utcnow_but_still_flags_the_naive_now(tmp_path):
    """GIVEN eine synthetische Datei, die BEIDES enthaelt — `datetime.now()`
    ohne Zone und `datetime.utcnow()`
    WHEN der Scanner laeuft
    THEN meldet er genau EINEN Fund, und zwar `datetime.now()`.

    Gegenprobe zu E2 als DIFFERENZ (s. Test darueber). `.utcnow()` liefert
    AUSDRUECKLICH Weltzeit, `.now()`/`.today()` liefern STILL Prozess-
    Lokalzeit — eine andere Fehlerklasse. Dass `.utcnow()` seit Python 3.12
    veraltet ist, ist Modernisierungsarbeit, kein Zeitzonen-Bug.
    """
    services_like = tmp_path / "src" / "services"
    services_like.mkdir(parents=True)
    mixed_file = services_like / "synthetic_now_vs_utcnow.py"
    mixed_file.write_text(
        "from datetime import datetime\n"
        "\n"
        "def prozess_lokalzeit():\n"
        "    return datetime.now()\n"
        "\n"
        "def ausdrueckliche_weltzeit():\n"
        "    return datetime.utcnow()\n",
        encoding="utf-8",
    )
    found = _find_violations(mixed_file)
    assert len(found) == 1, (
        "erwartete genau 1 Fund (nur datetime.now() ohne tz), gefunden "
        f"{len(found)}: {found}"
    )
    assert {_scope_of(k) for k in found} == {"prozess_lokalzeit"}, (
        "der einzige Fund muss datetime.now() sein, nicht datetime.utcnow(): "
        f"{sorted(found)}"
    )
    assert set(found.values()) == {_KIND_AMBIENT_CLOCK}, (
        f"erwartete Fundart {_KIND_AMBIENT_CLOCK!r}, "
        f"gefunden: {sorted(set(found.values()))}"
    )


def test_module_level_zone_literal_finding_names_the_module_scope(tmp_path):
    """GIVEN ein `VIENNA = ZoneInfo("Europe/Vienna")` auf MODULEBENE, ausserhalb
    jeder Funktion, unter einem `src/services/`-artigen Pfad
    WHEN der Scanner laeuft
    THEN traegt der Fundschlüssel `_MODULE_SCOPE` als Funktionsanteil, im
    selben Format `"pfad::funktion::ordinal"` wie jeder andere Fund.

    Analog `test_timezone_guard_finding_names_the_enclosing_function` im
    Meta-Waechter: ein Fund, der seinen Ort nicht benennen kann, ist beim
    Eintragen in KNOWN_VIOLATIONS nicht wiederzufinden (#1466 AP2).
    """
    services_like = tmp_path / "src" / "services"
    services_like.mkdir(parents=True)
    module_level_file = services_like / "synthetic_module_level_zone.py"
    module_level_file.write_text(
        "from zoneinfo import ZoneInfo\n"
        "\n"
        "VIENNA = ZoneInfo('Europe/Vienna')\n"
        "\n"
        "def fenster():\n"
        "    return VIENNA\n",
        encoding="utf-8",
    )
    found = _find_violations(module_level_file)
    assert len(found) == 1, (
        f"erwartete 1 Modulebene-Fund, gefunden {len(found)}: {found}"
    )
    key = next(iter(found))
    assert key.endswith(f"::{_MODULE_SCOPE}::0"), (
        f"Modulebene-Fund traegt den falschen Funktionsanteil: {key!r} — "
        f"erwartet wurde '…::{_MODULE_SCOPE}::0'"
    )
    assert found[key] == _KIND_HARDCODED_NON_UTC_ZONE, (
        f"erwartete Fundart {_KIND_HARDCODED_NON_UTC_ZONE!r}, gefunden: {found[key]!r}"
    )
