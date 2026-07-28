"""Wächter — kein Auflösungspfad verschluckt je wieder still einen Eintrag.

Issue #1405 (Hälfte A, „Was hineingeht, kommt heraus"): die häufigste
Fehlerart im Projekt ist das *stille Verschlucken* — eine Eingabemenge wird
auf eine kleinere Ausgabemenge abgebildet, ohne dass der Verlust irgendwo
protokolliert wird (18 von 79 belegten Fehlern in vier Wochen). Der Nutzer
sieht eine Spalte, einen Ort oder eine Warnung schlicht nicht mehr; im
Betrieb bleibt es unbemerkt, weil nichts es meldet.

Die Norm dagegen existiert bereits im eigenen Code — sie ist nur nicht
überall angewandt: die drei Compare-Metrik-Auflöser (``resolve_enabled_
metrics``/``resolve_hourly_metrics``/``resolve_outlook_metrics``) sammeln
Verworfenes in einer lokalen Liste (``unmapped``/``dropped``) und melden es
am Ende per ``logger.warning`` mit Issue-Bezug. Dieser Wächter rollt dieses
vorhandene Muster („Sammeln-und-melden") auf die restlichen Auflösungspfade
aus, statt eine neue Regel zu erfinden.

Signatur „stiller Auflösungsverlust" — BEIDE Bedingungen müssen zutreffen:

1. **Mengenbezug:** eine ``for``-Schleife oder Comprehension über eine
   Eingabesammlung, deren Iterationsergebnis in eine Ausgabesammlung fließt
   (``.append(...)``, Comprehension-Ziel, ``dict[k] = ...``, ``set.add(...)``,
   ``set.update(...)``) oder direkt in einen Renderer-/Versandaufruf geht.
2. **Stiller Abbruchpfad:** ``continue`` / Comprehension-Filter /
   ``except: ...`` (ohne ``raise``) OHNE begleitende ``logger.*``-Meldung,
   wobei die Abbruchbedingung ein **Lookup-Fehltreffer** ist
   (``x not in MAP``, ``MAP.get(x) is None``, ``except KeyError``) — kein
   Schwellenwertvergleich und keine Mitgliedschaftsprüfung gegen eine bereits
   gefüllte Ausgabemenge.

Fünf strukturelle Ausschlüsse (harmlos, dürfen NICHT als Fund zählen):

1. Dokumentierter Policy-Filter — der Verlust wird per ``logger.*`` gemeldet
   (deckt die drei Compare-Auflöser ab; fällt bereits durch Bedingung 2).
2. Sichtbarer Platzhalter — Funktionsnamensmuster ``_col_key``/``_cell``/
   ``fmt_*``: liefert per Hauskonvention einen Anzeige-Platzhalter ("–")
   statt eines echten Werts (Vorbild ``helpers.fmt_val``).
3. Fallback-Wert im selben Atemzug — VOR dem Abbruch wird ein Wert in
   dieselbe Ausgabesammlung geschrieben (``row[key] = None; continue``): es
   verschwindet nichts, es wird markiert. Klassen 2 und 3 sind derselbe
   Mechanismus („markiert statt verschwunden"), s. Spec „Geklärte Punkte" 1.
4. Aggregationsschleife ohne Mengenbezug — Ergebnis ist ein Skalar (Zähler,
   Min/Max, Schwellenwertvergleich); fällt bereits durch Bedingung 1.
5. Dedup-/Idempotenz-Guard — Abbruch wegen Duplikat gegen eine ``seen``-Menge,
   kein Katalog-Fehltreffer; fällt bereits durch Bedingung 2.

Bauform + Ratsche 1:1 nach ``tests/test_output_timezone_guard.py`` (#1402):
Scanfläche als Glob, ``ast.parse`` je Datei, Verstöße als
``{"pfad:zeile": "art::funktion"}``, zwei gekoppelte Ratschen-Tests (neuer
Fund → rot; erledigter Eintrag noch gelistet → rot), synthetische
Wirkungsnachweise je Bugmuster UND je Ausnahmeklasse.

Bekannte Grenzen (Scope, keine Ausnahme):
- **Nur Protokoll, nicht Sichtbarkeit:** der Wächter kann erzwingen, dass
  Verworfenes in ein ``logger.warning`` fließt — nicht, dass es in der
  gerenderten Mail/SMS für den Nutzer erkennbar wird. Das ist S3
  (Mengenerhalt-Nachweise), nicht diese Scheibe.
- **Go-Code bleibt ungeprüft:** ``internal/`` ist für einen Python-``ast``-
  Scan strukturell unerreichbar — bewusste, dokumentierte Lücke (AC-9).
- **Keine Mehrfunktions-Datenflüsse:** ein Wert, der verschwindet, weil eine
  vorgelagerte Funktion schon gefiltert hat, ist mit einer
  Ein-Funktion-Strukturprüfung nicht erkennbar (analog der
  Koordinaten-Herleitungs-Lücke im Zeitzonen-Wächter).

Regel-Budget (CLAUDE.md): neuer Pflicht-Test ohne Ersatz einer bestehenden
Regel → **Prüfdatum 2026-10-26** (+90 Tage). Kein nachweisbarer Fang bis
dahin → Rückbau erwägen.

Spec: ``docs/specs/modules/waechter_1405_stille_aufloesung.md``.
"""
from __future__ import annotations

import ast
from collections import Counter
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SRC = REPO_ROOT / "src"

# Scanfläche: der komplette Ausgabebaum (Renderer, Kanäle) + der komplette
# Service-Baum (inkl. official_alerts/). Deckt alle 13 bekannten Fundstellen
# ab und macht die Trip/Compare-Asymmetrie (A1–A9) im selben Lauf sichtbar.
# NICHT gescannt: `tests/` (kein Produktionspfad) und `internal/` (Go — für
# einen Python-AST-Scan strukturell unerreichbar, s. AC-9).
_OUTPUT_DIR = SRC / "output"
_SERVICES_DIR = SRC / "services"

# Art-Kennung im Verstoß-Wert. Der Wert hat die Form "<art>::<funktionsname>"
# — der Funktionsname trägt AC-1 (Erwartungsmenge ohne Zeilennummern) und
# überlebt Codeverschiebungen, anders als der "pfad:zeile"-Schlüssel.
KIND_SILENT_LOOKUP_MISS = "silent_lookup_miss"

# --- Bedingung 1: was zählt als Schreibzugriff auf eine Ausgabesammlung ------
_COLLECTION_WRITE_METHODS = {"append", "add", "update", "extend", "insert", "setdefault"}

# --- Bedingung 2: Ausnahmetypen, die einen Auflösungs-Fehltreffer schlucken --
# ``KeyError`` ist der Katalog-Fehltreffer im Wortsinn; ``Exception``/bare
# ``except`` schlucken ihn mit (so liegt A12 im Bestand: ``except Exception:
# continue`` um einen ganzen CAP-Sprachblock herum).
_SWALLOWING_EXCEPTIONS = {"KeyError", "Exception", "BaseException"}

# --- Ausschluss 2: Hauskonvention "sichtbarer Anzeige-Platzhalter" ----------
# Funktionen dieser Namensform liefern per Konvention ein "–" statt eines
# Werts — es verschwindet nichts, es wird markiert (Vorbild ``helpers.fmt_val``,
# ``compare_html._cell``).
_PLACEHOLDER_FUNCTION_NAMES = {"_cell", "_col_key"}
_PLACEHOLDER_FUNCTION_PREFIXES = ("fmt_",)

# Empfänger-Namen, die einen ``logger.*``-Aufruf ausmachen. Bewusst eine feste
# Liste statt einer "enthält log"-Heuristik: ``catalog.get(...)`` enthält
# ebenfalls "log" und würde jede Katalogabfrage als Meldung durchgehen lassen.
_LOGGER_RECEIVERS = {"logger", "_logger", "LOGGER", "log", "_log", "logging"}

_MODULE_SCOPE = "<module>"


def _scan_files() -> list[Path]:
    """Alle zu scannenden Python-Dateien: ``src/output/**`` + ``src/services/**``.

    Sortierte Liste aller ``*.py`` unter beiden Bäumen (rekursiv), ohne
    ``tests/`` und ohne ``internal/`` (Go). Die Liste ist die Scanfläche für
    ``_all_violations()`` und zugleich der Prüfgegenstand von
    ``test_scan_scope_excludes_go_internal_tree()``.
    """
    return sorted({*_OUTPUT_DIR.rglob("*.py"), *_SERVICES_DIR.rglob("*.py")})


# ---------------------------------------------------------------------------
# Strukturelle Bausteine des Scanners
# ---------------------------------------------------------------------------


def _walk_local(*nodes: ast.AST):
    """Wie ``ast.walk``, steigt aber NICHT in verschachtelte Funktionen ab.

    Der ganze Wächter ist eine Ein-Funktion-Prüfung: eine Schleife in einer
    inneren Hilfsfunktion gehört zu DEREN Funktionsraum, nicht zum äußeren —
    sonst würden Ausgabesammlungen und Logger-Aufrufe über Funktionsgrenzen
    hinweg vermischt und der Datenfluss-Nachweis wäre wertlos.

    Die Grenze gilt auch für die ÜBERGEBENEN Knoten selbst: eine Funktion, die
    direkt im Modul- oder Klassenrumpf steht, ist ihr eigener Raum und wird von
    ``_scopes()`` gesondert besucht — sonst zählte der Modulraum jede Schleife
    jeder Funktion ein zweites Mal mit.
    """
    boundaries = (ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda)
    stack = [node for node in nodes if not isinstance(node, boundaries)]
    while stack:
        node = stack.pop()
        yield node
        for child in ast.iter_child_nodes(node):
            if isinstance(child, boundaries):
                continue
            stack.append(child)


def _scopes(tree: ast.Module):
    """Modulraum + jeder Funktionsraum (auch verschachtelte) mit seinem Namen."""
    yield tree, _MODULE_SCOPE
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            yield node, node.name


def _is_placeholder_scope(name: str) -> bool:
    """Ausschluss 2 — Namensmuster ``_col_key``/``_cell``/``fmt_*``."""
    return name in _PLACEHOLDER_FUNCTION_NAMES or name.startswith(
        _PLACEHOLDER_FUNCTION_PREFIXES
    )


def _collection_writes(*nodes: ast.AST) -> set[str]:
    """Namen der Sammlungen, in die in ``nodes`` geschrieben wird.

    Trägt Bedingung 1 (Mengenbezug): ``out.append(x)``/``out.add(x)``/
    ``out.update(x)``/``out[k] = x``. Ein Zähler (``hits += 1``) oder ein
    Extremwert (``worst = max(...)``) taucht hier bewusst NICHT auf — das ist
    Ausschluss 4 (Aggregation ohne Mengenbezug).
    """
    names: set[str] = set()
    for node in _walk_local(*nodes):
        if (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and node.func.attr in _COLLECTION_WRITE_METHODS
            and isinstance(node.func.value, ast.Name)
        ):
            names.add(node.func.value.id)
        elif isinstance(node, (ast.Assign, ast.AugAssign, ast.AnnAssign)):
            targets = node.targets if isinstance(node, ast.Assign) else [node.target]
            for target in targets:
                if isinstance(target, ast.Subscript) and isinstance(target.value, ast.Name):
                    names.add(target.value.id)
    return names


def _is_logger_call(node: ast.AST) -> bool:
    if not (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)):
        return False
    receiver = node.func.value
    if isinstance(receiver, ast.Name):
        return receiver.id in _LOGGER_RECEIVERS
    if isinstance(receiver, ast.Attribute):
        return receiver.attr in _LOGGER_RECEIVERS
    return False


def _has_logger_call(*nodes: ast.AST) -> bool:
    return any(_is_logger_call(node) for node in _walk_local(*nodes))


def _logger_argument_names(*nodes: ast.AST) -> set[str]:
    """Alle Namen, die als Argument eines ``logger.*``-Aufrufs auftauchen.

    Das ist die eine Hälfte des Datenfluss-Nachweises für Absicherungsvariante
    (b): ``unmapped`` steht in ``logger.warning(..., unmapped)``, also ist ein
    ``unmapped.append(item)`` im Abbruchzweig eine echte Meldung. Ein
    ``logger.*``-Aufruf OHNE diesen Bezug zählt ausdrücklich nicht — sonst
    rutschte A12 durch (``meteoalarm`` bricht an einer Stelle stumm ab und
    protokolliert an einer völlig anderen).
    """
    names: set[str] = set()
    for node in _walk_local(*nodes):
        if not _is_logger_call(node):
            continue
        arguments = list(node.args) + [kw.value for kw in node.keywords]
        for argument in arguments:
            for inner in ast.walk(argument):
                if isinstance(inner, ast.Name):
                    names.add(inner.id)
                elif isinstance(inner, ast.Attribute):
                    names.add(inner.attr)
    return names


def _branch_is_safeguarded(branch: list[ast.stmt], logger_names: set[str]) -> bool:
    """Absicherung nach Spec-Korrektur (RED-Befund 2): (a) ``logger.*`` im
    Abbruchzweig selbst ODER (b) der verworfene Eintrag wird im Abbruchzweig in
    eine Sammlung geschrieben, die in derselben Funktion als Logger-Argument
    erscheint."""
    if _has_logger_call(*branch):
        return True
    return bool(_collection_writes(*branch) & logger_names)


def _branch_marks_instead_of_dropping(
    branch: list[ast.stmt], outputs: set[str]
) -> bool:
    """Ausschlüsse 2+3 („markiert statt verschwunden"): der Abbruchzweig
    schreibt VOR dem Abbruch selbst in eine der Ausgabesammlungen
    (``row[key] = None; continue``)."""
    return bool(_collection_writes(*branch) & outputs)


def _handler_swallows_lookup_miss(handler: ast.ExceptHandler) -> bool:
    if handler.type is None:
        return True
    candidates = handler.type.elts if isinstance(handler.type, ast.Tuple) else [handler.type]
    for candidate in candidates:
        if isinstance(candidate, ast.Name) and candidate.id in _SWALLOWING_EXCEPTIONS:
            return True
        if isinstance(candidate, ast.Attribute) and candidate.attr in _SWALLOWING_EXCEPTIONS:
            return True
    return False


def _branch_drops_entry(branch: list[ast.stmt]) -> bool:
    """Der Zweig verwirft genau diesen Eintrag und läuft weiter: er enthält
    ``continue`` oder besteht nur aus ``pass`` (so sehen A7/A9 aus). Ein
    ``raise``/``return`` ist etwas anderes — dort bricht der ganze Vorgang ab,
    das ist keine stille Mengen-Verkleinerung."""
    for node in _walk_local(*branch):
        if isinstance(node, (ast.Raise, ast.Return)):
            return False
    if any(isinstance(stmt, ast.Continue) for stmt in branch):
        return True
    return bool(branch) and all(isinstance(stmt, ast.Pass) for stmt in branch)


def _is_mapping_get_call(node: ast.AST) -> bool:
    return (
        isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr == "get"
    )


def _container_name(node: ast.AST) -> str | None:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        return node.attr
    return None


def _walk_loop_local(loop: ast.AST):
    """Der Rumpf EINER Schleife, ohne verschachtelte Schleifen.

    Ein ``continue`` gehört immer zur INNERSTEN Schleife — der Abbruchzweig
    muss also gegen deren Ausgabesammlung geprüft werden, nicht gegen die der
    umgebenden. Ohne diese Grenze erbt ein harmloser innerer Zweig den
    Mengenbezug der äußeren Schleife (falscher Alarm).
    """
    boundaries = (
        ast.FunctionDef,
        ast.AsyncFunctionDef,
        ast.Lambda,
        ast.For,
        ast.AsyncFor,
        ast.While,
        ast.ListComp,
        ast.SetComp,
        ast.DictComp,
        ast.GeneratorExp,
    )
    stack = [stmt for stmt in loop.body if not isinstance(stmt, boundaries)]
    while stack:
        node = stack.pop()
        yield node
        for child in ast.iter_child_nodes(node):
            if isinstance(child, boundaries):
                continue
            stack.append(child)


def _locally_bound_names(*nodes: ast.AST) -> set[str]:
    """Namen, die die Funktion sich SELBST zusammenbaut.

    Trennt den Katalog vom Arbeitsblatt: ``by_id = {row[0]: row for row in
    rows}`` ist eine im selben Atemzug abgeleitete Hilfsmenge — ein
    ``if m in by_id``-Filter dagegen ordnet/schneidet nur, er verliert nichts,
    was nicht ohnehin schon fehlte. Ein echter Auflösungsverlust schlägt gegen
    etwas fehl, das die Funktion NICHT selbst gebaut hat: einen Parameter
    (``all_locations``, A11) oder eine Modul-/Katalogkonstante
    (``_TYPE_HAZARD_MAP``, A13).
    """
    names: set[str] = set()
    for node in _walk_local(*nodes):
        targets: list[ast.AST] = []
        if isinstance(node, ast.Assign):
            targets = list(node.targets)
        elif isinstance(node, (ast.AugAssign, ast.AnnAssign, ast.NamedExpr)):
            targets = [node.target]
        elif isinstance(node, (ast.For, ast.AsyncFor, ast.comprehension)):
            targets = [node.target]
        elif isinstance(node, ast.withitem) and node.optional_vars is not None:
            targets = [node.optional_vars]
        for target in targets:
            for inner in ast.walk(target):
                if isinstance(inner, ast.Name):
                    names.add(inner.id)
    return names


def _looked_up_names(*nodes: ast.AST) -> set[str]:
    """Sammlungen, in denen hier tatsächlich NACHGESCHLAGEN wird (``MAP[x]``
    bzw. ``MAP.get(x)``).

    Das macht aus einer bloßen Mitgliedschaftsprüfung einen *Lookup*-
    Fehltreffer: ``if lid in all_locations`` bewacht ein ``all_locations[lid]``
    (A11). Eine Prüfung gegen eine Sammlung, in der nirgends nachgeschlagen
    wird (``if key in _AMPEL_CAPABLE_METRIC_IDS``), ist ein Policy-Filter —
    dort ist nichts aufzulösen, also kann auch nichts still verlorengehen.
    """
    names: set[str] = set()
    for node in _walk_local(*nodes):
        if isinstance(node, ast.Subscript):
            name = _container_name(node.value)
            if name is not None:
                names.add(name)
        elif _is_mapping_get_call(node):
            name = _container_name(node.func.value)
            if name is not None:
                names.add(name)
    return names


def _get_result_sources(*nodes: ast.AST) -> dict[str, str]:
    """``var -> MAP`` für ``var = MAP.get(...)`` — die Vorstufe zu
    ``if var is None: continue`` (so liegt A13 im Bestand).

    Nur der ÄUSSERSTE Aufruf zählt: in ``cap = _fetch_cap(props.get("id"))``
    stammt ``cap`` aus dem Abruf, nicht aus einem Lookup.
    """
    sources: dict[str, str] = {}
    for node in _walk_local(*nodes):
        if not isinstance(node, ast.Assign) or len(node.targets) != 1:
            continue
        target = node.targets[0]
        if not (isinstance(target, ast.Name) and _is_mapping_get_call(node.value)):
            continue
        source = _container_name(node.value.func.value)
        if source is not None:
            sources[target.id] = source
    return sources


def _is_external_container(name: str | None, local_names: set[str]) -> bool:
    return name is not None and name not in local_names


def _is_lookup_miss_test(
    test: ast.AST,
    get_sources: dict[str, str],
    looked_up: set[str],
    local_names: set[str],
) -> bool:
    """Bedingung 2 für ``if ...: continue`` — der verworfene Eintrag ist der,
    den der Katalog NICHT kennt.

    Zwei Formen: ``x not in MAP`` (und ``MAP`` wird auch wirklich als Lookup
    benutzt) sowie ``var is None`` nach ``var = MAP.get(x)`` bzw. direkt
    ``MAP.get(x) is None``. In beiden Fällen muss ``MAP`` von außen kommen.
    Eine Mitgliedschaftsprüfung gegen eine im selben Lauf gefüllte Sammlung
    (``seen``) ist ein Dedup-Guard (Ausschluss 5), ein Zahlenvergleich ein
    Schwellenwert (Ausschluss 4) — beide fallen hier heraus.
    """
    if not (
        isinstance(test, ast.Compare)
        and len(test.ops) == 1
        and len(test.comparators) == 1
    ):
        return False
    operator, right = test.ops[0], test.comparators[0]
    if isinstance(operator, ast.NotIn):
        name = _container_name(right)
        return _is_external_container(name, local_names) and name in looked_up
    if (
        isinstance(operator, ast.Is)
        and isinstance(right, ast.Constant)
        and right.value is None
    ):
        if _is_mapping_get_call(test.left):
            return _is_external_container(
                _container_name(test.left.func.value), local_names
            )
        if isinstance(test.left, ast.Name) and test.left.id in get_sources:
            return _is_external_container(get_sources[test.left.id], local_names)
    return False


def _is_comprehension_lookup_filter(
    condition: ast.AST, looked_up: set[str], local_names: set[str]
) -> bool:
    """Bedingung 2 für einen Comprehension-Filter. Achtung, umgekehrte
    Richtung: ein Filter BEHÄLT bei ``True``, verwirft also bei ``False``.
    ``[MAP[x] for x in xs if x in MAP]`` lässt genau die Einträge
    verschwinden, die der Katalog nicht kennt (so liegt A11 im Bestand)."""
    if not (isinstance(condition, ast.Compare) and len(condition.ops) == 1):
        return False
    if not isinstance(condition.ops[0], ast.In):
        return False
    name = _container_name(condition.comparators[0])
    return _is_external_container(name, local_names) and name in looked_up


def _loop_finding_lines(
    loop: ast.AST, logger_names: set[str], local_names: set[str]
) -> list[int]:
    """Zeilen stiller Auflösungsverluste in EINER ``for``-Schleife."""
    outputs = _collection_writes(*loop.body)
    if not outputs:
        return []  # Ausschluss 4: kein Mengenbezug, nur Aggregation.
    get_sources = _get_result_sources(*loop.body)
    looked_up = _looked_up_names(*loop.body)
    lines: list[int] = []
    for node in _walk_loop_local(loop):
        if isinstance(node, ast.Try):
            for handler in node.handlers:
                if not _handler_swallows_lookup_miss(handler):
                    continue
                if not _branch_drops_entry(handler.body):
                    continue
                if _branch_is_safeguarded(handler.body, logger_names):
                    continue
                if _branch_marks_instead_of_dropping(handler.body, outputs):
                    continue
                lines.append(node.lineno)
        elif isinstance(node, ast.If):
            if not any(isinstance(stmt, ast.Continue) for stmt in node.body):
                continue
            if not _is_lookup_miss_test(node.test, get_sources, looked_up, local_names):
                continue
            if _branch_is_safeguarded(node.body, logger_names):
                continue
            if _branch_marks_instead_of_dropping(node.body, outputs):
                continue
            lines.append(node.lineno)
    return lines


def _find_violations(path: Path) -> dict[str, str]:
    """Stille Auflösungsverluste in EINER Datei als ``{"pfad:zeile": "art::funktion"}``.

    GREEN muss liefern — je ``ast``-Knoten einer ``for``-Schleife oder
    Comprehension in der Scandatei:

    * **Mengenbezug feststellen** (Bedingung 1): fließt das Iterationsergebnis
      in eine Ausgabesammlung (``.append``/``.add``/``.update``/``dict[k] =``/
      Comprehension-Ziel) oder direkt in einen Aufruf? Wenn nein → kein Fund
      (schließt Aggregations-/Schwellenwertschleifen aus, Ausschluss 4).
    * **Stillen Lookup-Fehltreffer feststellen** (Bedingung 2): ein
      ``continue``/``except``-Zweig oder ein Comprehension-Filter, dessen
      Bedingung ein Katalog-Fehltreffer ist (``except KeyError``,
      ``x not in MAP``, ``MAP.get(x) is None``) — NICHT eine Prüfung gegen
      eine bereits gefüllte ``seen``-/Ausgabemenge (Ausschluss 5) und NICHT
      ein Schwellenwertvergleich.
    * **Meldung feststellen** (Ausschluss 1): enthält die umgebende Funktion
      einen ``logger.*``-Aufruf, der den Verlust meldet, ist es kein Fund.
      Maßgeblich ist die Funktion, nicht allein der Abbruchkörper — das
      Referenzmuster der drei Compare-Auflöser sammelt in ``unmapped``/
      ``dropped`` und meldet ERST NACH der Schleife (s. AC-5).
    * **Markierung statt Verschwinden feststellen** (Ausschlüsse 2+3): ein
      Schreibzugriff auf dieselbe Ausgabesammlung VOR dem Abbruch
      (``row[key] = None; continue``) ODER ein Funktionsname nach dem Muster
      ``_col_key``/``_cell``/``fmt_*`` → kein Fund.

    Schlüssel ist ``"<pfad relativ zum Repo>:<zeile>"``; ``relative_to``
    scheitert für Pfade außerhalb des Repos (die Wirkungsnachweise scannen
    synthetische Dateien in ``tmp_path``) — dann bleibt der absolute Pfad
    stehen, das Format ist nur für Menschenlesbarkeit relevant. Wert ist
    ``f"{KIND_SILENT_LOOKUP_MISS}::{name der umschließenden Funktion}"``.
    """
    try:
        rel = path.relative_to(REPO_ROOT).as_posix()
    except ValueError:
        rel = str(path)
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    found: dict[str, str] = {}

    for scope, scope_name in _scopes(tree):
        if _is_placeholder_scope(scope_name):
            continue  # Ausschluss 2: sichtbarer Platzhalter statt Verschwinden.
        logger_names = _logger_argument_names(*scope.body)
        local_names = _locally_bound_names(*scope.body)
        for node in _walk_local(*scope.body):
            if isinstance(node, (ast.For, ast.AsyncFor)):
                for lineno in _loop_finding_lines(node, logger_names, local_names):
                    found[f"{rel}:{lineno}"] = f"{KIND_SILENT_LOOKUP_MISS}::{scope_name}"
            elif isinstance(node, (ast.ListComp, ast.SetComp, ast.DictComp)):
                # Der Comprehension-Wert IST die Ausgabesammlung — Bedingung 1
                # ist damit erfüllt. Ein ``GeneratorExp`` bleibt bewusst außen
                # vor: er landet meist in ``any()``/``sum()``, also in einem
                # Skalar (Ausschluss 4).
                looked_up = _looked_up_names(node)
                for generator in node.generators:
                    for condition in generator.ifs:
                        if _is_comprehension_lookup_filter(
                            condition, looked_up, local_names
                        ):
                            found[f"{rel}:{node.lineno}"] = (
                                f"{KIND_SILENT_LOOKUP_MISS}::{scope_name}"
                            )
    return found


def _all_violations() -> dict[str, str]:
    """``_find_violations()`` über die gesamte Scanfläche, zu EINEM Dict vereint."""
    violations: dict[str, str] = {}
    for path in _scan_files():
        violations.update(_find_violations(path))
    return violations


def _finding_locations(found: dict[str, str]) -> set[str]:
    """Scan-Ergebnis → Menge aus ``"pfad::funktion"`` (ohne Zeilennummern).

    Reine Umformung des Scanner-Ergebnisses, damit AC-1 gegen eine
    zeilenstabile Erwartungsmenge prüfen kann.
    """
    locations: set[str] = set()
    for location, kind in found.items():
        path = location.rsplit(":", 1)[0]
        function = kind.split("::", 1)[1] if "::" in kind else ""
        locations.add(f"{path}::{function}")
    return locations


def _finding_location_counts(found: dict[str, str]) -> dict[str, int]:
    """Scan-Ergebnis → ``"pfad::funktion"`` mit der ZAHL der Treffer darin.

    Gezählt wird über das ROHE Scan-Ergebnis, in dem der Zeilenbezug noch
    steckt — nur so bleiben zwei Abbruchpfade derselben Funktion zwei Treffer.
    ``_finding_locations()`` wirft die Zeile weg und lässt sie zu einem Eintrag
    zusammenfallen; AC-1 wäre damit blind dafür, ob der Scanner beide oder nur
    einen der beiden Pfade sieht (A12/A13 in ``_extract_alerts_from_cap``).
    """
    counts: Counter[str] = Counter()
    for location, kind in found.items():
        path = location.rsplit(":", 1)[0]
        function = kind.split("::", 1)[1] if "::" in kind else ""
        counts[f"{path}::{function}"] += 1
    return dict(counts)


# ---------------------------------------------------------------------------
# Restliste aus der #1405-Bestandsaufnahme (A1–A13) — DARF NUR SCHRUMPFEN.
# Schlüssel = "pfad:zeile" (wie vom Scanner geliefert), Wert = Begründung +
# Issue-Bezug. Ein NEUER, hier nicht gelisteter Fund ist ein echter Rückfall
# (test_no_unlisted_resolution_drops schlägt fehl). Ein hier gelisteter Fund,
# den der Scanner nicht mehr findet, MUSS entfernt werden
# (test_known_violations_only_shrink schlägt sonst fehl, "veraltet").
#
# Alle Zeilennummern hier stammen aus dem ECHTEN Scan-Lauf, nicht aus der
# Spec — sonst prüfte die Ratsche eine Abschrift statt den Code. Die
# Spec-Tabelle A1–A13 ist die unabhängige Gegenprobe dazu
# (SPEC_LISTED_FINDINGS unten, AC-1).
#
# 22 Einträge: die 13 aus der Spec-Bestandsaufnahme (A1–A13) + 9 beim Bau des
# Wächters NEU entdeckte Stellen. Die neun sind von Hand nachgelesen und
# tragen jeweils dieselbe Mechanik wie eine bereits belegte Fundstelle — die
# Bestandsaufnahme war schlicht unvollständig. Sie sind KEINE Verbreiterung
# der Signatur: der Scanner meldet nach der Schärfung nichts, was nicht ein
# Auflösungs-Fehltreffer gegen einen von außen kommenden Katalog wäre.
# ---------------------------------------------------------------------------
KNOWN_VIOLATIONS: dict[str, str] = {
    # --- A1–A9: derselbe Mechanismus (get_metric() → except KeyError →
    # weiter ohne Spalte) neunfach. Die Compare-Seite ist gehärtet, die
    # Trip-/HTML-Seite nicht — dieselbe Asymmetrie, die #1262 auslöste.
    "src/output/renderers/trip_report.py:400": (
        "A1 (#1405) — _aggregate_night_block: Nacht-Block-Spalte einer "
        "aktivierten Metrik verschwindet bei unbekannter metric_id."
    ),
    "src/output/renderers/trip_report.py:482": (
        "A2 (#1405) — _dp_to_row: Stunden-Zeile-Spalte verschwindet."
    ),
    "src/output/renderers/email/html.py:721": (
        "A3 (#1405) — _allowed_col_keys_for_horizon: Spalte fällt aus dem "
        "Horizont-Filter."
    ),
    "src/output/renderers/email/html.py:785": (
        "A4 (#1405) — render_html (_col_order): Spaltenreihenfolge und "
        "-sichtbarkeit der ganzen Mail."
    ),
    "src/output/renderers/email/helpers.py:100": (
        "A5 (#1405) — dp_to_row: Stunden-Zeile-Spalte verschwindet."
    ),
    "src/output/renderers/email/helpers.py:152": (
        "A6 (#1405) — aggregate_night_block: Nacht-Block-Spalte verschwindet."
    ),
    "src/output/renderers/email/helpers.py:975": (
        "A7 (#1405) — build_friendly_keys: Ampel-/Friendly-Format entfällt "
        "(except KeyError: pass)."
    ),
    "src/output/renderers/email/helpers.py:992": (
        "A8 (#1405) — build_format_modes: Format-Mode-Eintrag entfällt."
    ),
    "src/output/renderers/email/helpers.py:1017": (
        "A9 (#1405) — build_html_indicator_keys: Ampel-Aktivierung entfällt."
    ),
    # --- A10–A13: Alarm- und Amtliche-Warnungen-Pfad ---
    "src/services/alert_preset.py:198": (
        "A10 (#1405) — expand_per_metric_levels (Spec-Tabelle: "
        "'resolve_alert_rules'): Direction-Feld-Optout verschwindet."
    ),
    "src/services/compare_official_alert.py:115": (
        "A11 (#1405) — _check_one_preset: ein Ort fällt per "
        "Comprehension-Filter aus der Alarm-Prüfung. Die zwei Geschwister "
        "(compare_alert.py, compare_radar_alert.py) melden bereits korrekt."
    ),
    "src/services/official_alerts/meteoalarm.py:334": (
        "A12 (#1405) — _extract_alerts_from_cap (Spec-Tabelle: '_parse_cap'): "
        "ganze CAP-Warnung fällt weg, except ohne Log. Der logger.warning in "
        "derselben Funktion (:378) hat mit diesem Zweig nichts zu tun."
    ),
    "src/services/official_alerts/meteoalarm.py:362": (
        "A13 (#1405) — _extract_alerts_from_cap: ganze Warnung fällt weg bei "
        "unbekanntem awareness_type (_TYPE_HAZARD_MAP-Fehltreffer)."
    ),
    # --- Beim Bau des Wächters NEU gefunden (nicht in der Bestandsaufnahme).
    # Jede Zeile von Hand nachgelesen; jede ist die exakte Mechanik einer
    # bereits belegten Fundstelle an einer weiteren Stelle. Reparatur gehört
    # zur Reparatur-Scheibe S4, nicht hierher (Wächter vor Reparatur).
    "src/output/renderers/email/helpers.py:468": (
        "NEU (#1405) — build_units_legend: get_metric_by_col_key() → "
        "except KeyError: continue. Dieselbe Mechanik wie A1–A9: eine Spalte "
        "verliert wortlos ihre Einheit in der Legende."
    ),
    "src/output/renderers/trip_report.py:521": (
        "NEU (#1405) — _build_units_legend: Trip-Zwilling von helpers.py:468, "
        "identische Mechanik."
    ),
    "src/output/renderers/email/compare_html.py:1040": (
        "NEU (#1405) — _units_legend_text: _METRICS_BY_ID.get() → is None → "
        "continue. Katalog-Fehltreffer wie A13; die Metrik verschwindet aus "
        "der Einheiten-Legende der Vergleichs-Mail."
    ),
    "src/services/day_comparison.py:271": (
        "NEU (#1405) — _summarize_metric_driven: "
        "_METRIC_ID_TO_ENTRY_ATTR.get() → is None → continue. Eine vom Nutzer "
        "gewählte Metrik fällt wortlos aus dem Tagesvergleich."
    ),
    "src/services/weather_change_detection.py:429": (
        "NEU (#1405) — from_display_config: get_metric() → except KeyError → "
        "continue. A1–A9-Mechanik im ALARM-Pfad: eine veraltete metric_id im "
        "display_config entschärft die Regel still (genau der #1262-Fall)."
    ),
    "src/services/official_alerts/geosphere_warn.py:122": (
        "NEU (#1405) — _extract_alerts: except (KeyError, TypeError, "
        "ValueError): continue ohne Log. Zwilling von A12 beim "
        "österreichischen Anbieter."
    ),
    "src/services/official_alerts/geosphere_warn.py:130": (
        "NEU (#1405) — _extract_alerts: _HAZARD_MAP-Fehltreffer → continue. "
        "Zwilling von A13; unbekannter Warntyp fällt wortlos weg."
    ),
    "src/services/official_alerts/vigilance.py:118": (
        "NEU (#1405) — _extract_alerts: _PHENOMENON_MAP-Fehltreffer → "
        "continue. Zwilling von A13 beim französischen Anbieter."
    ),
    "src/services/gpx_processing.py:297": (
        "NEU (#1405) — process_bulk_gpx_uploads: except Exception: continue "
        "ohne Log. Wer fünf GPX-Dateien hochlädt, bekommt bei einer kaputten "
        "vier Etappen und keinerlei Hinweis darauf."
    ),
}


# ---------------------------------------------------------------------------
# AC-1: die 13 in der Spec namentlich gelisteten Fundstellen A1–A13, als
# "pfad::funktion" → MINDEST-TREFFERZAHL — bewusst OHNE Zeilennummern, damit
# spätere Codeverschiebungen sie nicht brechen.
#
# Gezählt wird, nicht bloß auf Anwesenheit geprüft (Spec AC-1, „Trefferzahl
# statt bloßer Anwesenheit"): A12 und A13 liegen beide in
# ``meteoalarm.py::_extract_alerts_from_cap``. Ohne Zeilennummern fallen sie zu
# EINEM Eintrag zusammen — ein Scanner, der nur einen der beiden Abbruchpfade
# fände, bliebe bei einer reinen Mengenprüfung grün. Daher: 12 Einträge mit
# Erwartung 1, ``_extract_alerts_from_cap`` mit 2. Summe = 13.
#
# ACHTUNG: Diese Liste stammt aus der Spec
# (docs/specs/modules/waechter_1405_stille_aufloesung.md, Tabelle A1–A13) und
# ist die UNABHÄNGIGE Erwartung an die Trefferkraft des Scanners. Sie darf
# NICHT aus KNOWN_VIOLATIONS abgeleitet werden — sonst prüfte der Wächter
# sich selbst. Schlägt AC-1 fehl, ist der Scanner zu eng gebaut: die Liste
# wird zur Behebung NIEMALS gekürzt (Test-Politik: Schwellen nie anpassen,
# damit etwas grün wird). Nur eine reparierte Fundstelle darf hier
# verschwinden — dann zusammen mit ihrem KNOWN_VIOLATIONS-Eintrag.
#
# ZWEI FUNKTIONSNAMEN AUS DER SPEC-TABELLE KORRIGIERT (GREEN, 2026-07-28):
# Die Spec nennt für A10 ``resolve_alert_rules`` und für A12/A13 ``_parse_cap``
# — BEIDE Namen existieren nirgends in ``src/`` (nachgeprüft per grep). Die
# Datei:Zeile-Anker der Spec stimmen dagegen exakt; die dort tatsächlich
# stehenden Funktionen heißen ``expand_per_metric_levels`` bzw.
# ``_extract_alerts_from_cap``. Korrigiert ist nur der Name — die Erwartung
# selbst ist UNVERÄNDERT: weiterhin 13 Fundstellen, weiterhin dieselben
# Codestellen, nichts gekürzt und nichts abgeschwächt.
# ---------------------------------------------------------------------------
SPEC_LISTED_FINDINGS: dict[str, int] = {
    # A1 — Nacht-Block-Spalte einer aktivierten Metrik
    "src/output/renderers/trip_report.py::_aggregate_night_block": 1,
    # A2 — Stunden-Zeile-Spalte
    "src/output/renderers/trip_report.py::_dp_to_row": 1,
    # A3 — Spalte aus Horizont-Filter
    "src/output/renderers/email/html.py::_allowed_col_keys_for_horizon": 1,
    # A4 — Spaltenreihenfolge/-sichtbarkeit der ganzen Mail (_col_order)
    "src/output/renderers/email/html.py::render_html": 1,
    # A5 — Stunden-Zeile-Spalte
    "src/output/renderers/email/helpers.py::dp_to_row": 1,
    # A6 — Nacht-Block-Spalte
    "src/output/renderers/email/helpers.py::aggregate_night_block": 1,
    # A7 — Ampel/Friendly-Format
    "src/output/renderers/email/helpers.py::build_friendly_keys": 1,
    # A8 — Format-Mode-Eintrag
    "src/output/renderers/email/helpers.py::build_format_modes": 1,
    # A9 — Ampel-Aktivierung
    "src/output/renderers/email/helpers.py::build_html_indicator_keys": 1,
    # A10 — Direction-Feld-Optout (Spec-Tabelle nennt "resolve_alert_rules" —
    # existiert nicht; die Funktion an alert_preset.py:198 heißt
    # "expand_per_metric_levels")
    "src/services/alert_preset.py::expand_per_metric_levels": 1,
    # A11 — Ort aus der Alarm-Prüfung (Comprehension-Filter)
    "src/services/compare_official_alert.py::_check_one_preset": 1,
    # A12 + A13 — ZWEI Abbruchpfade in DERSELBEN Funktion, daher Erwartung 2:
    # ganze CAP-Warnung (except ohne Log) UND unbekannter awareness_type.
    # (Spec-Tabelle nennt "_parse_cap" — existiert nicht, die Funktion heißt
    # "_extract_alerts_from_cap".)
    "src/services/official_alerts/meteoalarm.py::_extract_alerts_from_cap": 2,
}


def test_scanner_finds_every_spec_listed_finding():
    """AC-1: GIVEN die 13 in der Spec gelisteten Fundstellen A1–A13
    WHEN der Wächter über die Scanfläche läuft
    THEN schlägt er in JEDER dieser Funktionen so oft an wie gelistet.

    Gemessen an SPEC_LISTED_FINDINGS — einer fest verdrahteten Erwartung aus
    der Spec (``pfad::funktion`` → Mindest-Trefferzahl), NICHT aus
    KNOWN_VIOLATIONS abgeleitet (AC-1/AC-3 dürfen nicht dieselbe Quelle
    benutzen, sonst prüft der Wächter sich selbst). Gezählt wird im ROHEN
    Scan-Ergebnis, wo der Zeilenbezug noch vorhanden ist: A12 und A13 liegen
    beide in ``_extract_alerts_from_cap``, und eine reine Mengenprüfung bliebe
    grün, wenn der Scanner einen der beiden Abbruchpfade verlöre.

    Fehlt ein Treffer, ist der Scanner zu eng gebaut — die Erwartung wird zur
    Behebung NICHT gekürzt.
    """
    found = _all_violations()
    hit_counts = _finding_location_counts(found)
    missing = sorted(
        f"{location} (erwartet >={expected}, gefunden {hit_counts.get(location, 0)})"
        for location, expected in SPEC_LISTED_FINDINGS.items()
        if hit_counts.get(location, 0) < expected
    )
    assert not missing, (
        "Der Wächter erkennt diese in der Spec belegten Fundstellen NICHT "
        "(oder nicht oft genug) — die Signatur ist zu eng gebaut (Issue "
        "#1405, Tabelle A1–A13). Die Erwartung NICHT kürzen, sondern den "
        f"Scanner erweitern. Code reference: {missing}"
    )


def test_no_unlisted_resolution_drops():
    """AC-2: GIVEN ein neuer Fund mit der Signatur (Mengenschleife + stiller
    Lookup-Fehltreffer ohne Meldung) irgendwo in der Scanfläche
    WHEN der Wächter läuft
    THEN schlägt er fehl und benennt Datei:Zeile — die Restliste kann nicht
    stillschweigend wachsen.

    Der Nachweis, dass der Scanner das Muster wirklich strukturell erkennt
    (statt zufällig zur Restliste zu passen), ist der synthetische
    Wirkungsnachweis in AC-4.
    """
    found = _all_violations()
    unlisted = {k: v for k, v in found.items() if k not in KNOWN_VIOLATIONS}
    assert not unlisted, (
        "Neue stille Auflösungsverluste entdeckt (Issue #1405): eine "
        "Eingabemenge wird auf eine kleinere Ausgabemenge abgebildet, ohne "
        "dass der Verlust gemeldet wird. Beheben nach dem Referenzmuster der "
        "Compare-Auflöser (Verworfenes sammeln + logger.warning mit "
        "Issue-Bezug) — oder, falls bewusst hingenommen, mit Begründung in "
        f"KNOWN_VIOLATIONS eintragen. Code reference: {sorted(unlisted.items())}"
    )


def test_known_violations_only_shrink():
    """AC-3: Die Restliste ist Übergangs-Buchhaltung für die Reparatur-Scheibe
    S4 und darf nur kleiner werden. Sobald eine gelistete Stelle behoben ist
    (der Scanner sie nicht mehr findet), MUSS der Eintrag entfernt werden —
    sonst bliebe die Liste eine Dauereinrichtung statt eines
    Fortschrittsnachweises."""
    found = _all_violations()
    stale = sorted(k for k in KNOWN_VIOLATIONS if k not in found)
    assert not stale, (
        "Diese Stellen sind inzwischen behoben (Scanner findet sie nicht "
        "mehr) — aus KNOWN_VIOLATIONS entfernen, die Liste darf nur "
        f"schrumpfen. Code reference: {stale}"
    )


def test_scanner_detects_silent_lookup_miss_in_synthetic_file(tmp_path):
    """AC-4: Wirkungsnachweis für das Bugmuster selbst — Schleife über eine
    Eingabemenge, ``except KeyError: continue`` beim Katalog-Lookup, kein
    ``logger``-Aufruf, Ergebnis fließt per ``.append()`` in die
    Ausgabesammlung. Nachbau von ``trip_report.py:401``
    (``_aggregate_night_block``). Wird das nicht erkannt, ist der Wächter ein
    zahnloses Bestandsprotokoll."""
    bad_file = tmp_path / "synthetic_silent_drop.py"
    bad_file.write_text(
        "from app.metric_catalog import get_metric\n"
        "\n"
        "\n"
        "def build_columns(dc):\n"
        "    columns = []\n"
        "    for mc in dc.metrics:\n"
        "        if not mc.enabled:\n"
        "            continue\n"
        "        try:\n"
        "            metric_def = get_metric(mc.metric_id)\n"
        "        except KeyError:\n"
        "            continue\n"
        "        columns.append(metric_def.col_key)\n"
        "    return columns\n",
        encoding="utf-8",
    )
    found = _find_violations(bad_file)
    locations = _finding_locations(found)
    assert any(loc.endswith("::build_columns") for loc in locations), (
        "Scanner hat den synthetischen stillen Auflösungsverlust nicht "
        f"erkannt: {found}"
    )
    assert all(v.startswith(KIND_SILENT_LOOKUP_MISS) for v in found.values()), (
        f"Unerwartete Fund-Art gemeldet: {found}"
    )


def test_scanner_ignores_logged_drop_in_synthetic_file(tmp_path):
    """AC-5: Gegenprobe zum Referenzmuster der drei Compare-Auflöser — die
    Schleife sammelt das Verworfene in ``unmapped`` und meldet es NACH der
    Schleife per ``logger.warning``. Kein Fund. Nachbau von
    ``compare_metric_ids.py:125`` (``resolve_enabled_metrics``).

    Wichtig: die Meldung steht bewusst NACH der Schleife, nicht im
    ``continue``-Zweig — genau so sieht das Vorbild im Bestand aus. Ein
    Scanner, der nur den Abbruchkörper betrachtet, würde die eigene
    Referenz-Implementierung als Verstoß melden und wäre nie grün zu
    bekommen."""
    good_file = tmp_path / "synthetic_logged_drop.py"
    good_file.write_text(
        "import logging\n"
        "\n"
        "from output.renderers.compare_metric_ids import FRONTEND_TO_RENDERER_METRIC_ID\n"
        "\n"
        "logger = logging.getLogger(__name__)\n"
        "\n"
        "\n"
        "def resolve_enabled_metrics(active_metrics):\n"
        "    resolved = []\n"
        "    unmapped = []\n"
        "    for item in active_metrics:\n"
        "        key = FRONTEND_TO_RENDERER_METRIC_ID.get(item)\n"
        "        if key is None:\n"
        "            unmapped.append(item)\n"
        "            continue\n"
        "        resolved.append(key)\n"
        "    if unmapped:\n"
        "        logger.warning(\n"
        "            'resolve_enabled_metrics: %s ohne Katalog-Entsprechung — '\n"
        "            'Eintrag wird verworfen statt angezeigt (vgl. #1405)', unmapped,\n"
        "        )\n"
        "    return resolved\n",
        encoding="utf-8",
    )
    found = _find_violations(good_file)
    assert not found, (
        "Das Referenzmuster 'Sammeln-und-melden' wurde fälschlich als "
        f"stiller Verlust gezählt: {found}"
    )


def test_scanner_ignores_placeholder_or_fallback_write_in_synthetic_file(tmp_path):
    """AC-6: Gegenprobe zu den Ausschlüssen 2+3 (ein Mechanismus: „markiert
    statt verschwunden"), beide Varianten in EINER Datei:

    * ``dp_to_row`` schreibt VOR dem ``continue`` einen Fallback in dieselbe
      Ausgabesammlung (``row[key] = None``) — es verschwindet nichts.
    * ``fmt_val``/``_cell`` tragen das Hauskonvention-Namensmuster und
      liefern einen sichtbaren Anzeige-Platzhalter ("–") statt eines Werts
      (Vorbild ``email/helpers.py:589`` bzw. ``compare_html.py:945``).

    Spec „Geklärte Punkte" 1: rutscht eine der 13 Fundstellen NUR wegen des
    Namensmuster-Zweigs durch, ist das ein Befund — dann ist das Namensmuster
    zu grob und wird durch die Schreibzugriff-Prüfung ERSETZT, nicht ergänzt.
    """
    good_file = tmp_path / "synthetic_placeholder.py"
    good_file.write_text(
        "from app.metric_catalog import get_metric\n"
        "\n"
        "\n"
        "def dp_to_row(dp, dc):\n"
        "    row = {}\n"
        "    for mc in dc.metrics:\n"
        "        if not mc.enabled:\n"
        "            continue\n"
        "        try:\n"
        "            metric_def = get_metric(mc.metric_id)\n"
        "        except KeyError:\n"
        "            row[mc.metric_id] = None\n"
        "            continue\n"
        "        row[metric_def.col_key] = getattr(dp, metric_def.dp_field, None)\n"
        "    return row\n"
        "\n"
        "\n"
        "def fmt_val(keys, values):\n"
        "    cells = []\n"
        "    for key in keys:\n"
        "        if key not in values:\n"
        "            continue\n"
        "        cells.append(values[key])\n"
        "    return cells or ['–']\n"
        "\n"
        "\n"
        "def _cell(keys, values):\n"
        "    out = {}\n"
        "    for key in keys:\n"
        "        if key not in values:\n"
        "            continue\n"
        "        out[key] = values[key]\n"
        "    return out\n",
        encoding="utf-8",
    )
    found = _find_violations(good_file)
    assert not found, (
        "Ein sichtbarer Platzhalter bzw. ein Fallback-Schreibzugriff wurde "
        f"fälschlich als stiller Verlust gezählt: {found}"
    )


def test_scanner_ignores_aggregation_loop_without_set_relation(tmp_path):
    """AC-7: Gegenprobe zu Ausschluss 4 — eine reine Aggregationsschleife
    (Zähler, Maximum, Schwellenwertvergleich ``if x < schwelle: continue``)
    hat keinen Mengenbezug: das Ergebnis ist ein Skalar, keine Übernahme
    gleichartiger Elemente in eine Ausgabesammlung. Kein Fund — sonst wäre
    der Wächter eine Fehlalarm-Schleuder (naive Signatur trifft in
    ``src/output/`` + ``src/services/`` rund 309 Stellen)."""
    good_file = tmp_path / "synthetic_aggregation.py"
    good_file.write_text(
        "def count_severe_hours(dps, threshold):\n"
        "    hits = 0\n"
        "    worst = 0.0\n"
        "    for dp in dps:\n"
        "        if dp.wind_kmh is None:\n"
        "            continue\n"
        "        if dp.wind_kmh < threshold:\n"
        "            continue\n"
        "        hits += 1\n"
        "        worst = max(worst, dp.wind_kmh)\n"
        "    return hits, worst\n",
        encoding="utf-8",
    )
    found = _find_violations(good_file)
    assert not found, (
        f"Reine Aggregationsschleife fälschlich als stiller Verlust gezählt: {found}"
    )


def test_scanner_ignores_dedup_guard_in_synthetic_file(tmp_path):
    """AC-8: Gegenprobe zu Ausschluss 5 — die Abbruchbedingung ist eine
    Mitgliedschaftsprüfung gegen eine bereits gefüllte ``seen``-Menge
    (Duplikat), kein Katalog-Lookup-Fehltreffer. Ein Duplikat ist kein
    Verlust: der Eintrag ist bereits in der Ausgabesammlung. Nachbau von
    ``compare_outlook_metric_ids.py:70`` — dort steht das Dedup-``continue``
    bewusst ohne Meldung neben einem gemeldeten ``dropped``-Zweig."""
    good_file = tmp_path / "synthetic_dedup.py"
    good_file.write_text(
        "def resolve_outlook_metrics(raw_pairs):\n"
        "    resolved = []\n"
        "    seen = set()\n"
        "    for raw in raw_pairs:\n"
        "        metric_id = raw.get('metric_id')\n"
        "        aggregation = raw.get('aggregation')\n"
        "        if (metric_id, aggregation) in seen:\n"
        "            continue\n"
        "        seen.add((metric_id, aggregation))\n"
        "        resolved.append({'metric_id': metric_id, 'aggregation': aggregation})\n"
        "    return resolved\n",
        encoding="utf-8",
    )
    found = _find_violations(good_file)
    assert not found, (
        f"Dedup-/Idempotenz-Guard fälschlich als stiller Verlust gezählt: {found}"
    )


def test_scan_scope_excludes_go_internal_tree():
    """AC-9: Der Go-Baum ``internal/`` ist NICHT Teil der Scanfläche — ein
    Python-``ast``-Scan erreicht ihn strukturell nicht (andere Sprache, keine
    ``.py``-Dateien). Das ist eine bewusste, dokumentierte Lücke, kein
    Versehen; Vorbild für die Python↔Go-Abdeckung über ein Inventar statt
    über AST ist ``tests/test_egress_inventory_drift.py``.

    Der Test hält die Lücke fest, damit sie nicht später stillschweigend als
    „geprüft" gilt — und prüft zugleich, dass die Scanfläche überhaupt
    gefüllt ist (ein leerer Scan wäre ein grüner Wächter ohne Wirkung)."""
    scanned = _scan_files()
    assert scanned, "Scanfläche ist leer — der Wächter liefe wirkungslos grün."
    internal_dir = REPO_ROOT / "internal"
    inside_go_tree = [p for p in scanned if internal_dir in p.parents]
    assert not inside_go_tree, (
        "Der Go-Baum internal/ liegt in der Scanfläche — ein Python-AST-Scan "
        "kann ihn nicht auswerten. Abgrenzung ist bewusst (Issue #1405, "
        f"'Aus dem Scope ausgeschlossen'). Code reference: {inside_go_tree}"
    )
    assert all(
        _OUTPUT_DIR in p.parents or _SERVICES_DIR in p.parents for p in scanned
    ), (
        "Scanfläche enthält Dateien außerhalb von src/output/** und "
        "src/services/** — die Spec zieht die Grenze dort."
    )
