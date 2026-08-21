"""Waechter (#1480): kein NEUER lokaler Nachbau der Gewitter-Stufenskala
(``ThunderLevel``: NONE/LOW/MED/HIGH) in ``src/`` oder ``api/``.

#1474 gab der Gewitterstaerke eine vierte Stufe. Neun Stellen hatten die
Zuordnung lokal nachgebaut, drei stuerzten ab, drei sagten Falsches. Dieser
Waechter verhindert die NAECHSTE Kopie -- er saniert keine bestehende (Spec
``docs/specs/modules/thunder_scale_guard.md``).

TDD RED: Vertrag und Tests stehen in dieser Datei, die Implementierung des
Erkennungs-Kerns (``ScaleSpec``, ``Finding``, ``scan_source``, ``scan_tree``)
folgt in GREEN OBERHALB dieses Docstrings, unterhalb der Tests -- Bauform-
Vorbild ``tests/tdd/test_repo_path_hardcoding_ratchet.py`` (#1409). Bis dahin
ist jeder Test unten ein absichtlicher ``NameError`` auf einen der vier noch
nicht existierenden Modul-Symbole; die Collection selbst bleibt gruen (AC-23).

Vertrag der Modul-Symbole (GREEN faellig)
------------------------------------------
``EXPIRY: str`` -- ISO-Pruefdatum des Regel-Budgets, s.u. (bereits gesetzt,
kein Kern-Symbol).

``ScaleSpec`` (``@dataclass``, frozen empfohlen) parametrisiert den Kern
(AC-24) mit den Feldern:
    - ``canonical_module: str`` -- z.B. ``"src.app.thunder_scale"``
    - ``symbol_name: str`` -- z.B. ``"ThunderLevel"``
    - ``member_names: tuple[str, ...]`` -- z.B. ``("NONE","LOW","MED","HIGH")``,
      zugleich die kanonische Ordnung fuer Regel D (kein separater Parameter
      auf ``scan_source``-Ebene noetig, da bereits in ``spec`` enthalten)
    - ``name_scope_tokens: tuple[str, ...]`` -- z.B. ``("thunder","gewitter")``
    - ``marker: str`` -- z.B. ``"gz-thunder-scale"``

``Finding`` traegt mindestens ``.file`` (str/Path), ``.line`` (1-basiert),
``.rule`` (``"A"|"B"|"C"|"D"``) und ``.symbol`` (betroffener Name, z.B.
``"_SEV_TO_THUNDER_LEVEL"`` oder ``"<anonym>"``); ``__str__`` liefert
``"Code reference: <file>:<line>"``.

``scan_source(source: str, filename: str, spec: ScaleSpec, *,
rules: tuple[str, ...] = ("A","B","C")) -> list[Finding]`` scannt EINEN
Quelltext (kein Datei-I/O). ``rules`` waehlt, welche Regeln laufen -- Regel
D ist eine Faehigkeit des geteilten Kerns (kein eigenes Budget), daher per
``rules=("D",)`` explizit anzufordern; ``match/case`` gehoert strukturell zu
Regel B und hat KEIN eigenes Buchstaben-Kuerzel.

``scan_tree(roots: Sequence[Path], spec: ScaleSpec, *,
rules: tuple[str, ...] = ("A","B","C"), canonical_order: Sequence[str] |
None = None) -> list[Finding]`` durchsucht alle ``*.py``-Dateien unter den
uebergebenen Wurzeln rekursiv (Regel D bekommt hier zusaetzlich die
Injektionsmoeglichkeit fuer die kanonische Ordnung -- im Normalbetrieb bleibt
sie ``None`` und der Kern nutzt ``spec.member_names``).

Duldung: ``# gz-thunder-scale: <Begruendung>`` (>= 15 sinnvolle Zeichen) an
der Fundstelle laesst den Fund durch (Bauform wie ``# gz-main-path: ...`` im
Vorbild-Ratchet). "Sinnvoll" = Buchstaben/Ziffern; Interpunktion, Leerraum und
Unterstriche zaehlen nicht, und eine reine Zeichen-Wiederholung ebenfalls
nicht.

Scanflaeche dieses Waechters: ``src/**/*.py`` + ``api/**/*.py`` fuer Regel
A/B/C, zusaetzlich ``tests/**/*.py`` fuer Regel D (separat aufgerufen, s.
Spec Abschnitt "Scanflaechen"). Keine Node-/TS-/Svelte-Referenz (AC-23).

Fixture-Quelltexte liegen AUSSERHALB der Scanflaeche in
``tests/fixtures/thunder_scale_guard_cases/faelle.py.txt`` (Endung
``.py.txt``, kein ``*.py``), analog zu ``tests/fixtures/ratchet_cases/faelle.py.txt``.

GREEN-Ergaenzung (Entscheid Team-Lead nach der GREEN-Messung)
------------------------------------------------------------
Der echte Baum liefert 14 Funde, nicht einen. Geduldet wird deshalb
DREISTUFIG -- die Stufen sagen jeweils etwas anderes aus:

1. ``ScaleSpec.canonical_files`` -- die kanonischen Quellen. Sie sind kein
   geduldeter Verstoss, sondern die Wahrheit; ein Waechter ohne sie meldet
   seine eigene Bezugsquelle. Parametrisiert, damit AC-24 traegt.
2. ``ALTLASTEN`` -- benannte, nur schrumpfende Basislinie der bekannten
   Kopien aus #1474. **Symbolgeschluesselt** ``(Datei, Symbol, Regel)``, nie
   ueber Zeilennummern (#1466). Ein Eintrag behauptet ausdruecklich NICHT,
   die Kopie sei gerechtfertigt -- er sagt "bekannter Defekt, nachverfolgt".
   Gegen Verrotten schuetzt der Nicht-Leerlauf-Test weiter unten.
3. ``# gz-thunder-scale: <Begruendung>`` -- die echte, begruendete Duldung an
   der Fundstelle (heute genau eine: ``narrow.py::_SEV_TO_THUNDER_LEVEL``).

Arbeitsteilung: ``scan_source`` kennt NUR die Marker-Duldung (Stufe 3) --
sonst koennte der Nicht-Leerlauf-Test die Altlasten gar nicht mehr sehen.
Whitelist und Basislinie (Stufen 1/2) wirken in ``scan_tree``, das beide per
``canonical_files``- bzw. ``baseline``-Parameter injizierbar haelt.
"""

import ast
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Optional, Sequence

import pytest

# Wurzel DIESES Checkouts (Worktree) -- kein fester Hauptrepo-Pfad, sonst
# misst man aus einem Worktree heraus den falschen Baum.
REPO_ROOT = Path(__file__).resolve().parents[2]
SRC_ROOT = REPO_ROOT / "src"
API_ROOT = REPO_ROOT / "api"
TESTS_ROOT = REPO_ROOT / "tests"

_FAELLE_DATEI = REPO_ROOT / "tests/fixtures/thunder_scale_guard_cases/faelle.py.txt"

# Prüfdatum des Regel-Budgets (+90 Tage ab 2026-08-20, wie im Spec-Changelog
# und in docs/reference/gates_und_ratschen.md verankert). Kein Kern-Symbol,
# darf schon in RED existieren -- reine Konstante ohne Verhalten.
EXPIRY = "2026-11-01"

_THUNDER_KWARGS = dict(
    canonical_module="src.app.thunder_scale",
    symbol_name="ThunderLevel",
    member_names=("NONE", "LOW", "MED", "HIGH"),
    name_scope_tokens=("thunder", "gewitter"),
    marker="gz-thunder-scale",
    # Die kanonischen Quellen der Gewitter-Stufenskala -- SYMBOLWEISE, nicht
    # dateiweise. Eine dateiweite Whitelist liesse diese Dateien vollstaendig
    # unbewacht; die neunte #1474-Kopie entstand aber genau dort, beim
    # Reparieren der vierten. ``metric_format.py`` fuehrt ausserdem Wolken-,
    # Wind- und weitere Metriken -- eine neue Gewitter-Kopie dort waere
    # unsichtbar. Die Kontextanalyse spricht ebenfalls symbolweise
    # ("``_THUNDER_AMPEL_BAND`` fehlte auf der Whitelist").
    #
    # NICHT enthalten, obwohl in der Kontextanalyse-Tabelle als kanonische
    # Quelle gefuehrt: ``models.py::ThunderLevel`` (Enum-Klassenrumpf, kein
    # Literal-Katalog) und
    # ``compare_metric_catalog.py::_THUNDER_ORDINAL_LABELS`` (leitet seit
    # #1911 zur Laufzeit ab). Beide erzeugen heute KEINEN Fund -- ein Eintrag
    # dafuer waere ein Leerlauf-Eintrag, und schlaegt einer von beiden kuenftig
    # doch an, ist das ein echtes Signal (Rueckfall hinter #1911), das man
    # sehen will statt stillzustellen.
    canonical_symbols=(
        ("src/app/thunder_scale.py", "_THUNDER_ORDER"),
        ("src/app/thunder_scale.py", "_THUNDER_LABEL_VALUE"),
        ("src/output/metric_format.py", "THUNDER_LABEL_DE"),
        ("src/output/metric_format.py", "_THUNDER_AMPEL_BAND"),
    ),
)


def _thunder_spec(**overrides):
    """``ScaleSpec`` fuer die kanonische Gewitter-Stufenskala. In eine
    Funktion gekapselt statt Modul-Konstante, damit der ``ScaleSpec``-Aufruf
    erst BEIM TESTLAUF (nicht bei der Collection) den erwarteten ``NameError``
    ausloest."""
    kwargs = dict(_THUNDER_KWARGS)
    kwargs.update(overrides)
    return ScaleSpec(**kwargs)  # noqa: F821 -- GREEN definiert ScaleSpec


def _risk_spec(**overrides):
    """``ScaleSpec`` einer ANDEREN Stufenskala (``RiskLevel``) -- der
    Gegenbeweis zu AC-24: derselbe Kern, nur andere Parameter."""
    kwargs = dict(
        canonical_module="src.app.models",
        symbol_name="RiskLevel",
        member_names=("LOW", "MODERATE", "HIGH"),
        name_scope_tokens=("risk", "risiko"),
        marker="gz-risk-scale",
    )
    kwargs.update(overrides)
    return ScaleSpec(**kwargs)  # noqa: F821 -- GREEN definiert ScaleSpec


def _fall(name: str) -> str:
    """Fixture-Quelltext ``name`` aus der externen Vorlagendatei holen."""
    abschnitte = re.split(
        r"^# === (\S+) ===$\n", _FAELLE_DATEI.read_text("utf-8"), flags=re.M
    )
    vorrat = dict(zip(abschnitte[1::2], abschnitte[2::2]))
    assert name in vorrat, f"Fall {name!r} fehlt in {_FAELLE_DATEI}: {sorted(vorrat)}"
    return vorrat[name]


def _line_of(source: str, needle: str) -> int:
    for n, line in enumerate(source.splitlines(), 1):
        if needle in line:
            return n
    raise AssertionError(f"Ankertext {needle!r} fehlt im Fixture-Quelltext")


def _refs(findings) -> str:
    return ", ".join(str(f) for f in findings) or "(keine)"


# ===========================================================================
# Erkennungs-Kern (#1480)
#
# Parametrisiert ueber ``ScaleSpec`` -- eine andere Stufenskala (etwa
# ``RiskLevel``) bewacht derselbe Kern ohne eine geaenderte Zeile (AC-24).
# Die Regeln sind an drei Korpora GEMESSEN, nicht entworfen (Kontextanalyse
# ``docs/context/feat-1480-thunder-scale-guard.md``); jede Verfeinerung unten
# traegt den Fehlalarm, den sie verhindert, im Kommentar.
# ===========================================================================

# Woerter, die sich mehrere Schwere-Skalen teilen (``RiskLevel``,
# ``alert_urgency``, ``ChangeSeverity``). Sie allein sind kein Beweis fuer
# EINE bestimmte Skala -- deshalb verlangt Regel A bei Dicts zusaetzlich ein
# distinktives Token. Die Liste ist skalen-UNABHAENGIG (allgemeiner
# Schwere-Wortschatz), damit der Kern parametrisiert bleibt.
GENERISCHE_SCHWERE_WOERTER = frozenset(
    {"LOW", "HIGH", "MEDIUM", "MODERATE", "MINOR", "SEVERE", "CRITICAL", "EXTREME"}
)

# Mindestlaenge der Marker-Begruendung, gemessen in Buchstaben/Ziffern (Bauform
# wie ``# gz-main-path:``, identische Schreibweise wie ``_UNWORT`` in
# ``tests/tdd/test_repo_path_hardcoding_ratchet.py``). Interpunktion und
# Unterstriche zaehlen NICHT: fuenfzehn Punkte sind keine Begruendung, und der
# Marker ist der Notausgang der Ratsche -- er soll Arbeit kosten.
MARKER_MINDESTLAENGE = 15
_UNWORT = re.compile(r"[\W_]+")
# Zusaetzlich zum Vorbild: eine Wiederholung EINES Zeichens ("aaaaaaaaaaaaaaa")
# ueberlebt die Unwort-Filterung mit voller Laenge, ist aber genauso wenig eine
# Begruendung wie fuenfzehn Punkte. Schwelle 5 mit grossem Abstand nach beiden
# Seiten (gemessen 2026-08-20: echte Begruendungen 11-20 verschiedene Zeichen,
# entartete Wiederholungen 1-2).
MARKER_MIND_VERSCHIEDEN = 5

# Regel D: BELEGTE Wortlaute aus dem Bestand, keine erfundenen (Messung:
# 8 von 16 Fixtures behaupten Paritaet, 0 Fehlalarme).
_PARITAETS_BEHAUPTUNG = re.compile(
    r"1:1"
    r"|wortw(?:oe|ö)rt"
    r"|identische reihenfolge"
    r"|eingefroren aus dem"
    r"|unver(?:ae|ä)ndert (?:aus|uebernommen)",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class ScaleSpec:
    """Beschreibt EINE Stufenskala. Alles, was der Kern ueber die bewachte
    Skala weiss, steht hier -- nichts davon im Kern selbst (AC-24)."""

    canonical_module: str
    symbol_name: str
    member_names: tuple[str, ...]
    name_scope_tokens: tuple[str, ...]
    marker: str
    # Kanonische Quellen als ``(Datei, Symbol)``-Paare: die Stellen, die die
    # Skala fuehren DUERFEN. Keine Duldung eines Verstosses, sondern die
    # Bezugsquelle selbst -- und bewusst symbolscharf, damit die uebrige Datei
    # bewacht bleibt.
    canonical_symbols: tuple = ()
    # Vorbelegung wird aus ``member_names`` abgeleitet; explizit setzbar, falls
    # eine Skala ausschliesslich generische Woerter fuehrt.
    distinctive_members: Optional[tuple[str, ...]] = None

    @property
    def tokens(self) -> frozenset:
        return frozenset(m.upper() for m in self.member_names)

    @property
    def distinktive_tokens(self) -> frozenset:
        if self.distinctive_members is not None:
            return frozenset(m.upper() for m in self.distinctive_members)
        return frozenset(t for t in self.tokens if t not in GENERISCHE_SCHWERE_WOERTER)

    def ordnung(self, canonical_order: Optional[Sequence[str]] = None) -> tuple:
        quelle = canonical_order if canonical_order else self.member_names
        return tuple(m.upper() for m in quelle)


@dataclass(frozen=True)
class Altlast:
    """EIN Eintrag der Basislinie -- symbolgeschluesselt, nie ueber
    Zeilennummern (#1466). ``grund`` haelt fest, WARUM die Stelle heute noch
    steht; ``tracking`` das Issue, wo bekannt."""

    file: str
    symbol: str
    rule: str
    grund: str
    tracking: str = ""

    @property
    def key(self) -> tuple:
        return (self.file, self.symbol, self.rule)


# Bekannte lokale Kopien aus #1474, Stand der GREEN-Messung 2026-08-20. Diese
# Liste darf NUR schrumpfen -- jede Sanierung streicht ihre Zeile. Sie
# behauptet ausdruecklich NICHT, die Kopien seien gerechtfertigt (mehrere sind
# nutzersichtbare Defekte); sie sagt "bekannt, nachverfolgt, bewacht".
# Gegen Verrotten schuetzt ``test_altlasten_basislinie_hat_keinen_leerlauf_eintrag``.
ALTLASTEN = (
    Altlast(
        "src/app/day_window.py",
        "_NIGHT_ADDENDUM_WORD",
        "A",
        "Nacht-Zusatz fuehrt LOW/MED/HIGH lokal, NONE absichtlich ausgelassen",
    ),
    Altlast(
        "src/output/renderers/email/html.py",
        "_thunder_risk_level",
        "B",
        "eigene Stufen-Wort-Kette statt thunder_ampel_band(), obwohl der "
        "Docstring die Angleichung behauptet",
        "#2011",
    ),
    Altlast(
        "src/output/renderers/email/html.py",
        "_thunder_risk_level",
        "C",
        "Zahlen-Fallback verschmilzt LOW und MED zu 'watch'",
        "#2011",
    ),
    Altlast(
        "src/services/trip_command_processor.py",
        "_THUNDER_LABEL",
        "A",
        "Telegram-Label mit Wortdrift ('maessig' statt 'mittel')",
        "#2010",
    ),
    Altlast(
        "src/services/trip_command_processor.py",
        "_MAP_EMOJI",
        "A",
        "Emoji-Karte mit Wortdrift ('keins'/'maessig')",
        "#2010",
    ),
    Altlast(
        "src/services/trip_command_processor.py",
        "_MAP_PLAIN",
        "A",
        "Klartext-Karte, unabhaengig gepflegtes Duplikat von _MAP_EMOJI",
        "#2010",
    ),
    Altlast(
        "src/services/trip_command_processor.py",
        "_handle_hours_drilldown",
        "B",
        "Stundentabelle verzweigt auf rohe Stufen-Strings mit eigenen Woertern",
        "#2010",
    ),
    Altlast(
        "src/services/trip_report_scheduler.py",
        "_thunder_entry_from_trend_row",
        "B",
        "eigene Satzvorlagen je Stufe",
    ),
    Altlast(
        "src/services/trip_report_scheduler.py",
        "_build_thunder_forecast",
        "B",
        "exaktes Duplikat derselben Satzvorlagen, unabhaengig gepflegt",
    ),
)


@dataclass(frozen=True)
class Finding:
    file: str
    line: int
    rule: str
    symbol: str = "<anonym>"
    detail: str = ""

    def __str__(self) -> str:
        return f"Code reference: {self.file}:{self.line}"


def _token_of(node, spec: ScaleSpec):
    """Stufen-Token eines Knotens -- als String-Konstante ODER als
    Enum-Attributkette (``ThunderLevel.MED`` ist ein ``ast.Attribute``, fuer
    das ``tests/helpers/metrik_listen_scan.py`` blind ist)."""
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        oben = node.value.strip().upper()
        return oben if oben in spec.tokens else None
    if isinstance(node, ast.Attribute):
        oben = node.attr.upper()
        return oben if oben in spec.tokens else None
    return None


def _delegiert(node) -> bool:
    """Liest der Teilbaum eine externe Quelle (Subscript/Call)?"""
    return any(isinstance(n, (ast.Subscript, ast.Call)) for n in ast.walk(node))


def _eigenes_rohes_literal(body) -> bool:
    """Erzeugt der Zweigkoerper eine EIGENE rohe Beschriftung/Zahl? Ein
    fremder Enum-Konstruktor (``Risk(level=RiskLevel.HIGH)``) zaehlt nicht --
    das ist das Trennmerkmal zwischen ``risk_engine.py`` (legitim) und
    ``email/html.py`` (Kopie)."""
    for stmt in body:
        for n in ast.walk(stmt):
            wert = getattr(n, "value", None) if isinstance(n, (ast.Assign, ast.Return)) else None
            if wert is None:
                continue
            if isinstance(wert, ast.Constant) and isinstance(wert.value, (str, int, float)):
                return True
            if isinstance(wert, ast.JoinedStr) and not _delegiert(wert):
                return True
    return False


def _stmt_von(node):
    cur = node
    while cur is not None and not isinstance(cur, ast.stmt):
        cur = getattr(cur, "parent", None)
    return cur


def _symbol_von(node) -> str:
    """Qualifizierter Name der Fundstelle -- Ausnahmen werden NIE ueber
    Zeilennummern geschluesselt (#1466)."""
    cur = node
    while cur is not None:
        if isinstance(cur, ast.Assign):
            for ziel in cur.targets:
                if isinstance(ziel, ast.Name):
                    return ziel.id
                if isinstance(ziel, ast.Attribute):
                    return ziel.attr
        if isinstance(cur, ast.AnnAssign) and isinstance(cur.target, ast.Name):
            return cur.target.id
        if isinstance(cur, (ast.FunctionDef, ast.AsyncFunctionDef)):
            return cur.name
        cur = getattr(cur, "parent", None)
    return "<anonym>"


def _fund(rule: str, node, zeilen, filename: str, spec: ScaleSpec, detail: str = ""):
    """Fundstelle -- ``None``, wenn ein begruendeter Marker sie deckt."""
    if _marker_deckt(zeilen, node, spec.marker):
        return None
    return Finding(
        file=filename,
        line=node.lineno,
        rule=rule,
        symbol=_symbol_von(node),
        detail=detail,
    )


# --- Regel A: Literal-Katalog ----------------------------------------------


def _regel_a(tree, zeilen, filename: str, spec: ScaleSpec) -> list:
    # Verfeinerung 4: ein Tupel rechts von ``x in (...)`` zaehlt nicht fuer A
    # (sonst Fehlalarm auf outlook.py:229, reine Nicht-NONE-Waechterbedingung).
    membership = {
        id(vergleich)
        for n in ast.walk(tree)
        if isinstance(n, ast.Compare)
        for op, vergleich in zip(n.ops, n.comparators)
        if isinstance(op, (ast.In, ast.NotIn))
    }
    funde = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Dict):
            schluessel = set()
            delegiert = False
            for k, v in zip(node.keys, node.values):
                if k is None:  # ``**rest`` -- liest eine fremde Quelle
                    delegiert = True
                    continue
                tok = _token_of(k, spec)
                if tok:
                    schluessel.add(tok)
                if v is not None and _delegiert(v):
                    # Verfeinerung 1: delegiert auch nur EIN Wert an die Quelle
                    # (``THUNDER_LABEL_DE["LOW"]``), gilt das GANZE Dict als
                    # "liest die Quelle" (sonst Fehlalarm auf helpers.py,
                    # outlook.py, compare_html.py).
                    delegiert = True
            # Verfeinerung 2: ohne distinktives Token ist LOW/HIGH allein kein
            # Beweis fuer diese Skala (alert_urgency.py, RiskLevel).
            if len(schluessel) >= 2 and (schluessel & spec.distinktive_tokens) and not delegiert:
                funde.append(
                    _fund(
                        "A", node, zeilen, filename, spec, f"Dict-Schluessel {sorted(schluessel)}"
                    )
                )
        elif isinstance(node, (ast.List, ast.Tuple, ast.Set)):
            if id(node) in membership:
                continue
            tokens = {t for t in (_token_of(e, spec) for e in node.elts) if t}
            # Verfeinerung 3: Liste/Tupel/Set erst ab DREI distinkten Token
            # (sonst Fehlalarm auf alert_preset.py, 2er-Tupel als Bereich).
            if len(tokens) >= 3:
                funde.append(
                    _fund("A", node, zeilen, filename, spec, f"Elemente {sorted(tokens)}")
                )
    return [f for f in funde if f is not None]


# --- Regel B: Verzweigungsketten (inkl. match/case) ------------------------


def _stufen_vergleiche(node, spec: ScaleSpec) -> list:
    """(Variable, Token)-Paare einer Bedingung -- rekursiv durch ``and``/``or``
    hindurch (ohne BoolOp-Rekursion entginge #1474-Verstoss 5)."""
    if isinstance(node, ast.BoolOp):
        paare = []
        for wert in node.values:
            paare += _stufen_vergleiche(wert, spec)
        return paare
    if isinstance(node, ast.Compare) and len(node.ops) == 1:
        op, links, rechts = node.ops[0], node.left, node.comparators[0]
        if isinstance(op, (ast.Eq, ast.NotEq)):
            tok = _token_of(rechts, spec)
            if tok:
                return [(ast.dump(links), tok)]
            tok = _token_of(links, spec)
            if tok:
                return [(ast.dump(rechts), tok)]
        if isinstance(op, (ast.In, ast.NotIn)) and isinstance(
            rechts, (ast.Tuple, ast.List, ast.Set)
        ):
            for elt in rechts.elts:
                tok = _token_of(elt, spec)
                if tok is None and isinstance(elt, ast.Constant) and isinstance(elt.value, str):
                    # ``str(v) in ("MED", "ThunderLevel.MED")`` -- die zweite
                    # Schreibweise ist #1474-Verstoss 5.
                    oben = elt.value.upper()
                    tok = next((t for t in spec.tokens if oben.endswith("." + t)), None)
                if tok:
                    return [(ast.dump(links), tok)]
    return []


def _kette_bewerten(kette, spec: ScaleSpec):
    """Liefert die Variable, gegen deren Stufen >= 2 verglichen wird und deren
    Zweige ein eigenes rohes Literal erzeugen -- sonst ``None``."""
    tokens: dict = {}
    koerper: dict = {}
    for knoten in kette:
        for var, tok in _stufen_vergleiche(knoten.test, spec):
            tokens.setdefault(var, set()).add(tok)
            koerper.setdefault(var, []).append(knoten.body)
    for var, toks in tokens.items():
        if len(toks) >= 2 and any(_eigenes_rohes_literal(b) for b in koerper[var]):
            return sorted(toks)
    return None


def _bloecke(tree):
    for node in ast.walk(tree):
        for _, wert in ast.iter_fields(node):
            if isinstance(wert, list):
                stmts = [v for v in wert if isinstance(v, ast.stmt)]
                if stmts:
                    yield stmts


def _pattern_tokens(pattern, spec: ScaleSpec) -> set:
    tokens = set()
    for n in ast.walk(pattern):
        if isinstance(n, ast.MatchValue):
            tok = _token_of(n.value, spec)
            if tok:
                tokens.add(tok)
    return tokens


def _regel_b(tree, zeilen, filename: str, spec: ScaleSpec) -> list:
    funde = []
    behandelt = set()
    kopf_mit_fund = set()

    # (1) klassische if/elif-Kette
    for node in ast.walk(tree):
        if not isinstance(node, ast.If) or id(node) in behandelt:
            continue
        kette = [node]
        behandelt.add(id(node))
        cur = node
        while len(cur.orelse) == 1 and isinstance(cur.orelse[0], ast.If):
            cur = cur.orelse[0]
            kette.append(cur)
            behandelt.add(id(cur))
        toks = _kette_bewerten(kette, spec)
        if toks:
            kopf_mit_fund.add(id(node))
            funde.append(_fund("B", node, zeilen, filename, spec, f"if/elif {toks}"))

    # (2) Kette aus SEPARATEN if-Statements im selben Block -- ohne diesen Pfad
    #     greift email/html.py:187-196 nicht.
    for block in _bloecke(tree):
        koepfe = [s for s in block if isinstance(s, ast.If)]
        if len(koepfe) < 2 or any(id(k) in kopf_mit_fund for k in koepfe):
            continue
        toks = _kette_bewerten(koepfe, spec)
        if toks:
            funde.append(_fund("B", koepfe[0], zeilen, filename, spec, f"separate if {toks}"))

    # (3) match/case -- strukturell dieselbe Verzweigung, gleicher Pfad.
    for node in ast.walk(tree):
        if not isinstance(node, ast.Match):
            continue
        tokens = set()
        koerper = []
        for fall in node.cases:
            fall_tokens = _pattern_tokens(fall.pattern, spec)
            if fall_tokens:
                tokens |= fall_tokens
                koerper.append(fall.body)
        if len(tokens) >= 2 and any(_eigenes_rohes_literal(b) for b in koerper):
            funde.append(
                _fund("B", node, zeilen, filename, spec, f"match/case {sorted(tokens)}")
            )
    return [f for f in funde if f is not None]


# --- Regel C: Zahlen-Schwelle in ein Wort ----------------------------------


def _im_namens_scope(node, spec: ScaleSpec) -> bool:
    name = node.name.lower()
    if any(h in name for h in spec.name_scope_tokens):
        return True
    argumente = [a.arg.lower() for a in node.args.args + node.args.kwonlyargs]
    return any(any(h in a for h in spec.name_scope_tokens) for a in argumente)


def _zahlen_kette(node):
    """(Anzahl numerischer Vergleiche, Anzahl Wort-Zweige) EINER if-Kette."""
    kette = [node]
    cur = node
    while len(cur.orelse) == 1 and isinstance(cur.orelse[0], ast.If):
        cur = cur.orelse[0]
        kette.append(cur)
    numerisch = 0
    worte = 0
    for n in kette:
        if isinstance(n.test, ast.Compare) and any(
            isinstance(c, ast.Constant) and isinstance(c.value, (int, float))
            for c in n.test.comparators
        ):
            numerisch += 1
        if _eigenes_rohes_literal(n.body):
            worte += 1
    return numerisch, worte


def _regel_c(tree, zeilen, filename: str, spec: ScaleSpec) -> list:
    funde = []

    def block_pruefen(body, im_scope, wurzel):
        if im_scope:
            numerisch = 0
            worte = 0
            erste = None
            for stmt in body:
                if isinstance(stmt, ast.If):
                    n_num, n_wort = _zahlen_kette(stmt)
                    numerisch += n_num
                    worte += n_wort
                    if erste is None:
                        erste = stmt
            if erste is not None and numerisch >= 2 and worte >= 1:
                funde.append(
                    _fund("C", erste, zeilen, filename, spec, f"{numerisch} Zahlen-Vergleiche")
                )
        for stmt in body:
            # Verschachtelte def/async def bekommen ihren EIGENEN Scope-Check
            # -- ohne diese Vererbungs-Sperre war html.py::_confidence_dot_color
            # ein Fehlalarm (AC-9).
            if isinstance(stmt, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            for _, wert in ast.iter_fields(stmt):
                if isinstance(wert, list):
                    verschachtelt = [v for v in wert if isinstance(v, ast.stmt)]
                    if verschachtelt:
                        block_pruefen(verschachtelt, im_scope, wurzel)

    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            block_pruefen(node.body, _im_namens_scope(node, spec), node)
    return [f for f in funde if f is not None]


# --- Regel D: Paritaets-Behauptung -----------------------------------------


def _kommentarblock_ueber(zeilen, lineno: int) -> str:
    """Zusammenhaengender Kommentarblock oberhalb (plus Zeilenkommentar auf der
    Zeile selbst), auf EINE Zeile normalisiert -- sonst zerreisst ein
    mehrzeiliger Wortlaut."""
    teile = []
    idx = lineno - 2
    while idx >= 0 and zeilen[idx].lstrip().startswith("#"):
        teile.append(zeilen[idx])
        idx -= 1
    teile.reverse()
    if 0 <= lineno - 1 < len(zeilen) and "#" in zeilen[lineno - 1]:
        teile.append(zeilen[lineno - 1].split("#", 1)[1])
    roh = " ".join(teile).replace("#", " ")
    return re.sub(r"\s+", " ", roh).strip()


def _positionsfolge(tokens, ordnung) -> Optional[list]:
    idxs = [ordnung.index(t) for t in tokens if t in ordnung]
    if len(idxs) < 2 or idxs[0] != 0:
        # Greift nur, wenn die Folge beansprucht, beim ersten Rang zu beginnen
        # -- eine bewusste Teilfolge ab Rang 1 ist kein Positionsfehler.
        return None
    return idxs


def _regel_d(tree, zeilen, filename: str, spec: ScaleSpec, canonical_order) -> list:
    ordnung = spec.ordnung(canonical_order)
    funde = []
    for node in ast.walk(tree):
        if not isinstance(node, (ast.List, ast.Tuple, ast.Set)):
            continue
        tokens = [t for t in (_token_of(e, spec) for e in node.elts) if t]
        if len(tokens) < 2:
            continue
        stmt = _stmt_von(node)
        kommentar = _kommentarblock_ueber(zeilen, (stmt or node).lineno)
        if not _PARITAETS_BEHAUPTUNG.search(kommentar):
            continue
        idxs = _positionsfolge(tokens, ordnung)
        if idxs is not None and idxs != list(range(len(idxs))):
            funde.append(
                _fund("D", node, zeilen, filename, spec, f"behauptete Paritaet, Folge {idxs}")
            )
    return [f for f in funde if f is not None]


# --- Duldung, Einstiegspunkte ----------------------------------------------


def _ist_begruendung(text: str) -> bool:
    """Traegt ``text`` genug SINNVOLLE Zeichen fuer eine Duldung (AC-21)?

    Interpunktion, Leerraum und Unterstriche fallen weg (Bauform ``_UNWORT``
    aus ``test_repo_path_hardcoding_ratchet.py``), zusaetzlich muss die
    Begruendung mehr als eine Zeichen-Wiederholung sein.
    """
    kern = _UNWORT.sub("", text)
    return (
        len(kern) >= MARKER_MINDESTLAENGE
        and len(set(kern.lower())) >= MARKER_MIND_VERSCHIEDEN
    )


def _marker_deckt(zeilen, node, marker: str) -> bool:
    muster = re.compile(r"#\s*" + re.escape(marker) + r"\s*:(.*)")
    anker = {node.lineno}
    stmt = _stmt_von(node)
    if stmt is not None:
        anker.add(stmt.lineno)
    for lineno in anker:
        kandidaten = []
        idx = lineno - 1
        if 0 <= idx < len(zeilen):
            kandidaten.append(zeilen[idx])
        idx -= 1
        while idx >= 0 and zeilen[idx].lstrip().startswith("#"):
            kandidaten.append(zeilen[idx])
            idx -= 1
        for zeile in kandidaten:
            treffer = muster.search(zeile)
            if treffer and _ist_begruendung(treffer.group(1)):
                return True
    return False


def scan_source(
    source: str,
    filename: str,
    spec: ScaleSpec,
    *,
    rules: tuple = ("A", "B", "C"),
    canonical_order: Optional[Sequence[str]] = None,
) -> list:
    """Scannt EINEN Quelltext (kein Datei-I/O)."""
    try:
        tree = ast.parse(source)
    except (SyntaxError, ValueError):
        return []
    for eltern in ast.walk(tree):
        for kind in ast.iter_child_nodes(eltern):
            kind.parent = eltern
    zeilen = source.splitlines()

    roh = []
    if "A" in rules:
        roh += _regel_a(tree, zeilen, filename, spec)
    if "B" in rules:
        roh += _regel_b(tree, zeilen, filename, spec)
    if "C" in rules:
        roh += _regel_c(tree, zeilen, filename, spec)
    if "D" in rules:
        roh += _regel_d(tree, zeilen, filename, spec, canonical_order)

    eindeutig = []
    gesehen = set()
    for f in sorted(roh, key=lambda f: (f.line, f.rule)):
        schluessel = (f.file, f.line, f.rule, f.symbol)
        if schluessel in gesehen:
            continue
        gesehen.add(schluessel)
        eindeutig.append(f)
    return eindeutig


def _ist_pfad(kandidat: str, repo_relativ: str) -> bool:
    """Pfadvergleich ueber das Repo-relative Ende -- ein Worktree misst so
    seinen EIGENEN Baum, ohne dass irgendwo ein absoluter Pfad steht."""
    return kandidat.replace("\\", "/").endswith("/" + repo_relativ.lstrip("/"))


def scan_tree(
    roots: Sequence,
    spec: ScaleSpec,
    *,
    rules: tuple = ("A", "B", "C"),
    canonical_order: Optional[Sequence[str]] = None,
    baseline: Optional[Sequence[Altlast]] = None,
    besucht: Optional[set] = None,
) -> list:
    """Durchsucht alle ``*.py`` unter den Wurzeln rekursiv und wendet die
    beiden Baum-Stufen der Duldung an: Whitelist kanonischer Quellen
    (``spec.canonical_symbols``, SYMBOLscharf -- die uebrige Datei bleibt
    bewacht) und benannte Altlasten-Basislinie. Beide sind injizierbar --
    ``baseline=()`` bzw. eine ``spec``-Kopie ohne ``canonical_symbols``
    liefern den jeweils ungefilterten Bestand fuer die Nicht-Leerlauf-
    Pruefungen.

    ``besucht``: optionaler Sammel-Set. Wird er uebergeben, traegt der Lauf
    JEDE tatsaechlich gescannte Datei als ``Path`` ein -- damit ist die
    besuchte Menge von aussen pruefbar (sonst waere ein Waechter, der nur die
    halbe Baumflaeche laeuft, von einem Nullbefund nicht zu unterscheiden).
    Der Waechter kennt KEINE Ausschluesse: die Soll-Menge ist genau
    ``rglob("*.py")`` unter den Wurzeln. Eine unlesbare Datei wird
    uebersprungen und erscheint dann bewusst NICHT in ``besucht`` -- ein
    stiller Skip soll sichtbar werden, nicht als "besucht" durchgehen."""
    altlasten = ALTLASTEN if baseline is None else tuple(baseline)
    funde = []
    for root in roots:
        pfad = Path(root)
        if not pfad.exists():
            continue
        for datei in sorted(pfad.rglob("*.py")):
            name = str(datei)
            try:
                quelle = datei.read_text("utf-8")
            except (OSError, UnicodeDecodeError):
                continue
            if besucht is not None:
                besucht.add(datei)
            for fund in scan_source(
                quelle, name, spec, rules=rules, canonical_order=canonical_order
            ):
                if any(
                    fund.symbol == symbol and _ist_pfad(fund.file, kanonisch)
                    for kanonisch, symbol in spec.canonical_symbols
                ):
                    continue
                if any(
                    fund.symbol == eintrag.symbol
                    and fund.rule == eintrag.rule
                    and _ist_pfad(fund.file, eintrag.file)
                    for eintrag in altlasten
                ):
                    continue
                funde.append(fund)
    return funde


# ---------------------------------------------------------------------------
# Selbstbezug: Fixture-Vorlagen liegen ausserhalb der Scanflaeche (AC-19)
# ---------------------------------------------------------------------------


def test_fixture_vorlagen_liegen_ausserhalb_der_scanflaeche():
    """Voraussetzung der Auslagerung -- empirisch, nicht angenommen: die
    Vorlagendatei enthaelt echte Verstoesse und wird von ``rglob("*.py")``
    trotzdem nie erfasst, weil sie ``.py.txt`` heisst."""
    assert "ThunderLevel.NONE" in _FAELLE_DATEI.read_text("utf-8"), (
        "Vorlage ohne echten Enum-Attribut-Verstoss -- taugt nicht als Fixture"
    )
    assert _FAELLE_DATEI not in set(TESTS_ROOT.rglob("*.py"))


def test_ac19_scan_ueber_die_eigene_fixture_ablage_bleibt_leer():
    """AC-19: Ein voller Scan ueber ``tests/fixtures/thunder_scale_guard_cases/``
    liefert null Funde, obwohl die Datei den vollen Stufen-Wortschatz fuehrt
    -- die Ablage ist nachweislich ausserhalb der Scanflaeche, nicht nur der
    Annahme nach."""
    spec = _thunder_spec()
    findings = scan_tree(  # noqa: F821
        [_FAELLE_DATEI.parent], spec, rules=("A", "B", "C", "D")
    )
    assert findings == [], (
        f"Scan der Fixture-Ablage darf keine eigenen Vorlagen melden: {_refs(findings)}"
    )


# ---------------------------------------------------------------------------
# Regel A -- Literal-Katalog (AC-1 bis AC-5)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "form,anker",
    [
        ("a1-string-dict", "_ANZEIGE = {"),
        ("a1-enum-attribut-dict", "_RANG = {"),
        ("a1-liste", "_REIHENFOLGE = ["),
        ("a1-tupel", "_STUFEN_TUPEL = ("),
        ("a1-set", "_STUFEN_SET = {"),
    ],
)
def test_ac1_literal_katalog_wird_je_form_gemeldet(form, anker):
    """AC-1: Dict (String- und Enum-Attribut-Form), Liste, Tupel, Set melden
    je genau einen Fund."""
    quelle = _fall(form)
    findings = scan_source(quelle, f"<{form}>", _thunder_spec())  # noqa: F821
    assert len(findings) == 1, f"{form}: erwartet 1 Fund, bekommen: {_refs(findings)}"
    assert findings[0].line == _line_of(quelle, anker)


def test_ac2_dict_mit_werte_delegation_bleibt_gruen():
    """AC-2: Delegiert auch nur ein Wert an die externe Quelle
    (``THUNDER_LABEL_DE["LOW"]``), gilt das ganze Dict als "liest die Quelle"."""
    quelle = _fall("a2-delegiert-dict")
    findings = scan_source(quelle, "<a2>", _thunder_spec())  # noqa: F821
    assert findings == [], f"Delegiertes Dict darf keinen Fund ausloesen: {_refs(findings)}"


def test_ac3_dict_ohne_med_oder_none_token_bleibt_gruen():
    """AC-3: Nur LOW/HIGH als Schluessel -- gehoert auch zu RiskLevel/
    alert_urgency, kein Gewitter-Vokabular ohne MED/NONE-Token."""
    quelle = _fall("a3-low-high-only")
    findings = scan_source(quelle, "<a3>", _thunder_spec())  # noqa: F821
    assert findings == [], f"LOW/HIGH allein darf keinen Fund ausloesen: {_refs(findings)}"


def test_ac4_liste_mit_nur_zwei_distinkten_tokens_bleibt_gruen():
    """AC-4: Liste/Tupel/Set brauchen >= 3 distinkte Stufen-Token, anders als
    die 2er-Ausnahme bei Dicts."""
    quelle = _fall("a4-zwei-tokens")
    findings = scan_source(quelle, "<a4>", _thunder_spec())  # noqa: F821
    assert findings == [], f"2 Token im Tupel duerfen keinen Fund ausloesen: {_refs(findings)}"


def test_ac5_tupel_als_rechter_operand_von_in_bleibt_gruen():
    """AC-5: Ein Tupel ausschliesslich rechts von ``x in (...)`` zaehlt nicht
    fuer Regel A -- das ist Regel Bs Aufgabe, die zusaetzlich ein eigenes
    Literal im Zweig verlangt (hier nicht vorhanden)."""
    quelle = _fall("a5-membership-tupel")
    findings = scan_source(quelle, "<a5>", _thunder_spec())  # noqa: F821
    assert findings == [], f"Membership-Tupel darf keinen Regel-A-Fund ausloesen: {_refs(findings)}"


# ---------------------------------------------------------------------------
# Regel B, C, match/case (AC-6 bis AC-10)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("form", ["b6-elif-kette", "b6-separate-if", "b6-boolop"])
def test_ac6_verzweigungsketten_mit_eigenem_literal_werden_gemeldet(form):
    """AC-6: elif-Kette, separate if-Statements und BoolOp-verknuepfte
    Bedingungen melden je genau einen Fund, wenn mindestens ein Zweigkoerper
    ein eigenes rohes Literal erzeugt."""
    quelle = _fall(form)
    findings = scan_source(quelle, f"<{form}>", _thunder_spec())  # noqa: F821
    assert len(findings) == 1, f"{form}: erwartet 1 Fund, bekommen: {_refs(findings)}"


def test_ac7_verzweigung_mit_nur_fremden_enum_konstruktoren_bleibt_gruen():
    """AC-7: Zweigkoerper, die ausschliesslich fremde Enum-Konstruktoren
    erzeugen (``Risk(level=RiskLevel.HIGH)``), sind kein Fund."""
    quelle = _fall("b7-fremde-enum-konstruktoren")
    findings = scan_source(quelle, "<b7>", _thunder_spec())  # noqa: F821
    assert findings == [], f"Fremde Enum-Konstruktoren duerfen keinen Fund ausloesen: {_refs(findings)}"


def test_ac8_zahlenschwelle_im_namens_scope_wird_gemeldet():
    """AC-8: Zahlen-Schwellenkette in einer Funktion mit thunder/gewitter im
    Namen wird gemeldet."""
    quelle = _fall("c8-zahlen-schwelle-thunder")
    findings = scan_source(quelle, "<c8-fund>", _thunder_spec())  # noqa: F821
    assert len(findings) == 1, f"erwartet 1 Fund, bekommen: {_refs(findings)}"


def test_ac8_strukturell_identische_kette_ausserhalb_des_namens_scope_bleibt_gruen():
    """AC-8 Gegenprobe: dieselbe Zahlen-Schwellenkette ohne thunder/gewitter
    im Namen (Windstaerke-Formatierung) bleibt unbemeldet."""
    quelle = _fall("c8-kontrolle-windstaerke")
    findings = scan_source(quelle, "<c8-kontrolle>", _thunder_spec())  # noqa: F821
    assert findings == [], f"Windstaerke-Formatierung darf keinen Fund ausloesen: {_refs(findings)}"


def test_ac9_verschachtelte_funktion_erbt_namens_scope_nicht():
    """AC-9: Eine innere ``def`` ohne eigenen thunder/gewitter-Namensbezug
    erbt den Scope NICHT von der umgebenden Funktion."""
    quelle = _fall("c9-innere-func-ohne-vererbten-scope")
    findings = scan_source(quelle, "<c9-kein-erbe>", _thunder_spec())  # noqa: F821
    assert findings == [], (
        f"Innere Funktion ohne eigenen Namensbezug darf keinen Fund erben: {_refs(findings)}"
    )


def test_ac9_verschachtelte_funktion_mit_eigenem_namensbezug_wird_gemeldet():
    """AC-9 Umkehrprobe: traegt die innere ``def`` den Namensteil SELBST,
    wird sie gemeldet -- ohne diesen Fall waere der AC auch von einer
    Implementierung erfuellt, die verschachtelte Funktionen pauschal
    uebergeht."""
    quelle = _fall("c9-innere-func-mit-eigenem-scope")
    findings = scan_source(quelle, "<c9-eigener-scope>", _thunder_spec())  # noqa: F821
    assert len(findings) == 1, f"erwartet 1 Fund, bekommen: {_refs(findings)}"


def test_ac10_match_case_wird_wie_verzweigungskette_gemeldet():
    """AC-10: ``match/case`` mit eigenem rohen Literal im ``case``-Zweig wird
    wie eine if/elif-Kette gemeldet."""
    quelle = _fall("b10-match-case-fund")
    findings = scan_source(quelle, "<b10-fund>", _thunder_spec())  # noqa: F821
    assert len(findings) == 1, f"erwartet 1 Fund, bekommen: {_refs(findings)}"


def test_ac10_match_case_mit_nur_fremden_enum_konstruktoren_bleibt_gruen():
    """AC-10 Gegenprobe: ``case``-Zweige, die ausschliesslich fremde
    Enum-Konstruktoren enthalten, bleiben gruen -- dieselbe Abgrenzung wie
    AC-7 fuer if/elif, hier eigens fuer match/case geprueft."""
    quelle = _fall("b10-match-case-fremde-enum")
    findings = scan_source(quelle, "<b10-fremde-enum>", _thunder_spec())  # noqa: F821
    assert findings == [], f"Fremde Enum-Konstruktoren in case-Zweigen: {_refs(findings)}"


# ---------------------------------------------------------------------------
# Treffsicherheit gegen die acht echten #1474-Verstoesse (AC-11)
# ---------------------------------------------------------------------------

_REAL_1474_FAELLE = [
    ("real1-num-dict", "_NUM = {"),
    ("real2-ord-if-elif", "if level == ThunderLevel.NONE:"),
    ("real3-liste-vorkommen-a", "_KURZ_REIHENFOLGE_A = ["),
    ("real4-liste-vorkommen-b", "_KURZ_REIHENFOLGE_B = ["),
    ("real5-str-membership-if-elif", 'if s in ("MED", "ThunderLevel.MED"):'),
    ("real6-thunder-label-dict", "_THUNDER_LABEL = {"),
    ("real7-map-emoji-dict", "_MAP_EMOJI = {"),
    ("real8-level-rank-dict", "level_rank = {"),
]


@pytest.mark.parametrize("form,anker", _REAL_1474_FAELLE)
def test_ac11_jede_der_acht_echten_1474_vorlagen_erzeugt_genau_einen_fund_an_der_erwarteten_stelle(
    form, anker
):
    """AC-11: die acht Fixture-Vorlagen der echten #1474-Verstoesse werden
    EINZELN geprueft -- je Vorlage genau ein Fund an der erwarteten
    Fundstelle. Eine Gesamtsumme "acht" allein genuegt ausdruecklich NICHT
    (koennte auch bei ungleich verteilten Fehlfunden zufaellig zustande
    kommen); dieser parametrisierte Test macht jede der acht Zeilen einzeln
    zu einem eigenen pytest-Fall mit eigenem Fund-/Zeilen-Nachweis."""
    quelle = _fall(form)
    findings = scan_source(quelle, f"<{form}>", _thunder_spec())  # noqa: F821
    assert len(findings) == 1, f"{form}: erwartet 1 Fund, bekommen: {_refs(findings)}"
    assert findings[0].line == _line_of(quelle, anker), (
        f"{form}: Fund an falscher Zeile ({findings[0].line} statt "
        f"{_line_of(quelle, anker)})"
    )


def test_ac11_alle_acht_vorlagen_zusammen_ergeben_acht_einzelfunde():
    """Ergaenzende Gesamtprobe (Wirkungsnachweis ueber die volle Menge) --
    ersetzt NICHT die achtfache Einzelpruefung oben, die bleibt Pflicht."""
    spec = _thunder_spec()
    gesamt = 0
    for form, _ in _REAL_1474_FAELLE:
        gesamt += len(scan_source(_fall(form), f"<{form}>", spec))  # noqa: F821
    assert gesamt == 8, f"Summe der acht Vorlagen muss 8 sein, war {gesamt}"


# ---------------------------------------------------------------------------
# Fehlalarm-Obergrenze gegen den echten Repo-Baum (AC-12)
# ---------------------------------------------------------------------------


def _rel(pfad: str) -> str:
    """Repo-relativer Pfad einer Fundstelle -- fuer Vergleiche mit der
    symbolgeschluesselten Basislinie."""
    return str(Path(pfad).resolve().relative_to(REPO_ROOT)).replace("\\", "/")


@pytest.fixture(scope="module")
def bestand_ohne_basislinie():
    """Der echte Baum OHNE die Altlasten-Stufe -- Whitelist und Marker wirken
    weiter. Genau die Menge, gegen die die Basislinie sich rechtfertigen muss.
    Ein Lauf fuer beide Zusicherungen unten."""
    return scan_tree(  # noqa: F821
        [SRC_ROOT, API_ROOT], _thunder_spec(), rules=("A", "B", "C"), baseline=()
    )


def test_ac12_echter_backend_baum_hat_ausser_den_drei_duldungsstufen_keinen_fund():
    """AC-12: voller Scan gegen ``src/`` + ``api/`` ist gruen, weil jeder Fund
    entweder auf der Whitelist kanonischer Quellen steht, in der benannten
    Altlasten-Basislinie gefuehrt wird oder einen Marker-Kommentar traegt
    (``narrow.py::_SEV_TO_THUNDER_LEVEL``). Dass jede dieser drei Stufen
    WIRKSAM ist und keine still ins Leere laeuft, pruefen die Tests darunter --
    dieser hier allein waere sonst auch von einem Waechter erfuellt, der
    ueberhaupt nichts mehr meldet."""
    spec = _thunder_spec()
    findings = scan_tree([SRC_ROOT, API_ROOT], spec, rules=("A", "B", "C"))  # noqa: F821
    assert findings == [], (
        "Fehlalarm auf dem echten Backend-Baum -- erwartet 0 unbegruendete Funde:\n"
        + "\n".join(f"{str(f)}  ({f.symbol}, Regel {f.rule})" for f in findings)
    )


def test_altlasten_basislinie_hat_keinen_leerlauf_eintrag(bestand_ohne_basislinie):
    """PFLICHT (Team-Lead-Entscheid): JEDER Basislinien-Eintrag muss heute noch
    einen echten Fund erzeugen. Ein Eintrag, dessen Symbol verschwunden oder
    umbenannt ist, macht diesen Test ROT statt still durchzulaufen -- ohne ihn
    verrottet die Liste und "keine neuen Kopien" wird trivial wahr, sobald sie
    nicht mehr passt. Sanierte Stelle => Zeile in ``ALTLASTEN`` streichen."""
    gefunden = {(_rel(f.file), f.symbol, f.rule) for f in bestand_ohne_basislinie}
    tot = [e for e in ALTLASTEN if e.key not in gefunden]
    assert not tot, (
        "Basislinien-Eintraege ohne echten Fund (saniert/umbenannt/verschoben?) "
        "-- Zeile streichen, die Liste darf nur schrumpfen:\n"
        + "\n".join(f"  {e.file}::{e.symbol} [Regel {e.rule}] {e.tracking}" for e in tot)
    )


def test_altlasten_basislinie_deckt_nichts_zu_das_nicht_in_ihr_steht(bestand_ohne_basislinie):
    """Gegenrichtung: die Basislinie darf keine Stelle stillstellen, die nicht
    namentlich in ihr steht. Zusammen mit dem Test darueber ergibt das
    Mengengleichheit -- und damit die Zusicherung der AC: entfernt man einen
    einzelnen Eintrag, wird genau diese eine Stelle rot, keine andere."""
    gefunden = {(_rel(f.file), f.symbol, f.rule) for f in bestand_ohne_basislinie}
    unbekannt = sorted(gefunden - {e.key for e in ALTLASTEN})
    assert not unbekannt, (
        "Neue lokale Kopie der Gewitter-Stufenskala -- nicht stillschweigend in "
        "ALTLASTEN aufnehmen, sondern beheben:\n"
        + "\n".join(f"  Code reference: {d} ({s}, Regel {r})" for d, s, r in unbekannt)
    )


@pytest.fixture(scope="module")
def bestand_ohne_whitelist():
    """Der echte Baum OHNE die Whitelist-Stufe (Basislinie und Marker wirken
    weiter) -- die Menge, gegen die sich jeder Whitelist-Eintrag rechtfertigen
    muss."""
    return scan_tree(  # noqa: F821
        [SRC_ROOT, API_ROOT], _thunder_spec(canonical_symbols=()), rules=("A", "B", "C")
    )


def test_whitelist_kanonischer_quellen_hat_keinen_leerlauf_eintrag(bestand_ohne_whitelist):
    """Wie bei ``ALTLASTEN``: jeder Whitelist-Eintrag muss heute noch einen
    echten Fund erzeugen. Ein Eintrag, dessen Symbol verschwunden oder
    umbenannt ist, macht diesen Test ROT statt still durchzulaufen -- sonst
    stellt die Whitelist irgendwann etwas anderes stumm als gedacht."""
    gefunden = {(_rel(f.file), f.symbol) for f in bestand_ohne_whitelist}
    tot = [e for e in _THUNDER_KWARGS["canonical_symbols"] if e not in gefunden]
    assert not tot, (
        "Whitelist-Eintraege ohne echten Fund (umbenannt/verschoben/entfallen?) "
        "-- Zeile streichen oder korrigieren:\n"
        + "\n".join(f"  {datei}::{symbol}" for datei, symbol in tot)
    )


def test_whitelist_wirkt_symbolscharf_nicht_dateiweit(tmp_path):
    """Der eigentliche Punkt der Symbol-Granularitaet: eine Kopie IN einer
    kanonischen Datei, aber unter einem ANDEREN Symbolnamen, wird gemeldet.
    Bei dateiweiter Whitelist bliebe dieser Test gruen -- er unterscheidet die
    beiden Bauweisen also am Verhalten, nicht am Quelltext.

    Die eingeschmuggelte Kopie stammt aus der ausgelagerten Vorlagendatei
    (``a1-enum-attribut-dict`` -> ``_RANG``), damit dieses Modul kein eigenes
    Stufen-Literal zusammensetzt."""
    kanonisch_rel, kanonisch_symbol = _THUNDER_KWARGS["canonical_symbols"][0]
    original = (REPO_ROOT / kanonisch_rel).read_text("utf-8")
    ziel = tmp_path / kanonisch_rel
    ziel.parent.mkdir(parents=True, exist_ok=True)
    ziel.write_text(original + "\n\n" + _fall("a1-enum-attribut-dict"), encoding="utf-8")

    spec = _thunder_spec()
    funde = scan_tree([tmp_path], spec, rules=("A", "B", "C"))  # noqa: F821
    symbole = sorted(f.symbol for f in funde)
    assert symbole == ["_RANG"], (
        "Erwartet: die fremde Kopie _RANG wird gemeldet, das kanonische Symbol "
        f"{kanonisch_symbol} nicht. Bekommen: {symbole or '(keine)'}"
    )


def test_ac12_positivkontrolle_der_baumlauf_erreicht_den_echten_bestand_wirklich():
    """Ohne diese Kontrolle waere der Nullbefund oben auch dann wahr, wenn
    ``scan_tree`` gar keine Datei besucht haette. Mit einem Marker-Namen, den
    kein einziger Kommentar traegt, MUSS derselbe Lauf melden -- das beweist
    Walk UND Duldungs-Mechanik in einem.

    "Mindestens ein Fund" genuegt dafuer ausdruecklich NICHT: ein Waechter,
    der nur die halbe Baumflaeche laeuft, liefert weiterhin Funde und einen
    leeren Bestandslauf. Geprueft wird deshalb die BESUCHTE DATEIMENGE gegen
    die Soll-Menge -- als Mengenvergleich, damit die Fehlermeldung sagt,
    WELCHE Datei fehlt. Die Soll-Menge wird zur Laufzeit aus dem Baum
    abgeleitet (``rglob``), NIE als Zahl festgeschrieben: eine feste Zahl
    briche bei jeder neuen ``.py``-Datei im Repo und waere ein Fehlalarm."""
    spec = _thunder_spec(marker="gz-marker-den-es-nicht-gibt")
    besucht: set = set()
    findings = scan_tree(  # noqa: F821
        [SRC_ROOT, API_ROOT], spec, rules=("A", "B", "C"), besucht=besucht
    )

    soll = set(SRC_ROOT.rglob("*.py")) | set(API_ROOT.rglob("*.py"))
    assert soll, "Soll-Menge leer -- src/ und api/ sind nicht auffindbar"
    fehlend = sorted(str(p.relative_to(REPO_ROOT)) for p in soll - besucht)
    ueberzaehlig = sorted(str(p) for p in besucht - soll)
    assert not fehlend and not ueberzaehlig, (
        "Der Baumlauf hat NICHT den ganzen Baum besucht -- ein Nullbefund waere "
        "damit nur fuer den gelaufenen Ausschnitt wahr.\n"
        f"Nicht besucht ({len(fehlend)} von {len(soll)}): {fehlend[:10]}\n"
        f"Ausserhalb der Wurzeln besucht: {ueberzaehlig[:10]}"
    )
    assert len(findings) > 0, (
        "Der Baumlauf hat keine einzige Fundstelle erreicht -- der Nullbefund "
        "des Bestandslaufs waere damit trivial wahr"
    )


def test_ac12_marker_entfernt_in_einer_kopie_macht_genau_diese_stelle_rot(tmp_path):
    """AC-12 Gegenprobe: ein temporaer entfernter Marker (nur in einer Kopie
    im tmp-Verzeichnis, NIE am Repo-Stand) macht denselben Lauf an genau der
    Stelle rot, die vorher geduldet war."""
    spec = _thunder_spec()
    quelle = (SRC_ROOT / "output/renderers/narrow.py").read_text("utf-8")
    ohne_marker = re.sub(r"(?m)^.*#\s*gz-thunder-scale:.*\n", "", quelle)
    assert ohne_marker != quelle, (
        "narrow.py traegt (noch) keinen gz-thunder-scale-Marker -- GREEN muss "
        "ihn an _SEV_TO_THUNDER_LEVEL setzen (Spec Affected Files)."
    )
    kopie = tmp_path / "narrow.py"
    kopie.write_text(ohne_marker, encoding="utf-8")
    findings = scan_source(ohne_marker, str(kopie), spec, rules=("A", "B", "C"))  # noqa: F821
    # Mengengleichheit statt any(...): der echte Baum liefert an dieser Stelle
    # GENAU einen Fund (_SEV_TO_THUNDER_LEVEL, Regel A) -- ein any(...) waere
    # auch dann wahr, wenn zusaetzlich eine ANDERE Stelle faelschlich mitrot
    # wuerde. Die Zeile selbst pruefen wir nicht (der Marker-Kommentar
    # verschiebt beim Entfernen die nachfolgenden Zeilen), wohl aber Symbol
    # UND Regel als vollstaendige Fundmenge.
    assert [(f.symbol, f.rule) for f in findings] == [("_SEV_TO_THUNDER_LEVEL", "A")], (
        "Ohne Marker haette GENAU EIN Fund an _SEV_TO_THUNDER_LEVEL (Regel A) "
        f"entstehen muessen -- weder mehr noch eine andere Stelle: {_refs(findings)}"
    )


# ---------------------------------------------------------------------------
# Beide Waechter: Regel D, Wirkungsnachweis, Duldung, Selbstbezug, Pruefdatum
# ---------------------------------------------------------------------------


def test_ac18_regel_d_meldet_behauptete_paritaet_bei_abweichung():
    """AC-18: Ein Testdatei-Kommentar, der Uebereinstimmung mit der echten
    Quelle behauptet ("1:1 aus ..."), aber tatsaechlich abweicht (MED/LOW
    vertauscht), wird gemeldet."""
    quelle = _fall("d18-behauptet-und-abweichend")
    findings = scan_source(quelle, "<d18-behauptet>", _thunder_spec(), rules=("D",))  # noqa: F821
    assert len(findings) == 1, f"Behauptete Paritaet + Abweichung: {_refs(findings)}"


def test_ac18_regel_d_ignoriert_dieselbe_abweichung_ohne_behauptung():
    """AC-18 Gegenprobe: strukturell identische Abweichung OHNE
    Paritaetsbehauptung im Kommentar bleibt unbemeldet."""
    quelle = _fall("d18-unbehauptet-gleiche-abweichung")
    findings = scan_source(quelle, "<d18-unbehauptet>", _thunder_spec(), rules=("D",))  # noqa: F821
    assert findings == [], f"Ohne Behauptung darf Regel D nicht melden: {_refs(findings)}"


def test_ac18_regel_d_erkennt_mehrzeilige_paritaetsbehauptung():
    """AC-18: die Kommentar-Extraktion normalisiert Zeilenumbrueche/Marker,
    sonst zerreisst ein mehrzeiliger Wortlaut ("eingefroren aus dem heutigen
    Stand der kanonischen Quelle")."""
    quelle = _fall("d18-mehrzeiliger-kommentar")
    findings = scan_source(quelle, "<d18-mehrzeilig>", _thunder_spec(), rules=("D",))  # noqa: F821
    assert len(findings) == 1, f"Mehrzeilige Behauptung nicht erkannt: {_refs(findings)}"


def test_ac18_regel_d_erkennt_phrase_die_mitten_im_wortlaut_ueber_die_zeile_bricht():
    """AC-18, geschaerfte Normalisierungs-Probe: bei
    ``d18-mehrzeiliger-kommentar`` (Test oben) steht die volle
    Behauptungsphrase ("eingefroren aus dem heutigen") bereits vollstaendig
    auf EINER Quelltextzeile -- die Zusammenfuegung mehrerer Kommentarzeilen
    wird dort nie wirklich beansprucht. Hier bricht die Phrase selbst MITTEN
    im Wortlaut ("eingefroren" endet Zeile 1, "aus dem ..." beginnt Zeile 2)
    -- nur wenn ``_kommentarblock_ueber`` die Zeilen tatsaechlich
    zusammenfuegt (und den Whitespace dazwischen normalisiert), bleibt die
    gesuchte Teilphrase "eingefroren aus dem" als zusammenhaengender
    Substring erhalten."""
    quelle = _fall("d18-phrase-reisst-mitten-im-wortlaut")
    findings = scan_source(quelle, "<d18-mitten-im-wortlaut>", _thunder_spec(), rules=("D",))  # noqa: F821
    assert len(findings) == 1, f"Ueber die Zeilengrenze gerissene Phrase nicht erkannt: {_refs(findings)}"


@pytest.fixture(scope="module")
def tests_baum_scan():
    """EIN Lauf ueber ``tests/**/*.py`` fuer beide Zusicherungen unten (Regel D
    und ihre Positivkontrolle) -- zwei getrennte Laeufe kosteten die doppelte
    Zeit im Commit-Gate."""
    return scan_tree(  # noqa: F821
        [TESTS_ROOT], _thunder_spec(), rules=("A", "D")
    )


def test_regel_d_ueber_den_echten_tests_baum_meldet_keine_unerfuellte_behauptung(
    tests_baum_scan,
):
    """Die zweite Scanflaeche dieses Waechters: Regel D laeuft auf
    ``tests/**/*.py`` (Regel A/P/C dort nicht -- eine korrekte Fixture fuehrt
    zwangslaeufig alle vier Stufen-Woerter und erzeugte Dauerfeuer)."""
    findings = [f for f in tests_baum_scan if f.rule == "D"]
    assert findings == [], (
        f"Behauptete Paritaet ohne Deckung im Testbestand: {_refs(findings)}"
    )


def test_regel_d_nullbefund_ist_nicht_trivial_der_lauf_erreicht_die_testdateien(
    tests_baum_scan,
):
    """Positivkontrolle zum Nullbefund darueber: derselbe Baumlauf trifft mit
    Regel A sehr wohl -- ohne diese Kontrolle waere ``findings == []`` auch
    dann wahr, wenn der Lauf keine einzige Datei besucht haette."""
    treffer = [f for f in tests_baum_scan if f.rule == "A"]
    assert len(treffer) > 0, (
        "Der Testbaum-Lauf hat keine einzige Datei erreicht -- der Nullbefund "
        "von Regel D waere damit trivial wahr"
    )


def test_ac20_wirkungsnachweis_trefferzahl_ist_selbst_groesser_null():
    """AC-20: der Waechter behauptet seine eigene Trefferzahl > 0 gegen eine
    Fixture mit bekanntem Verstoss -- eine leere Trefferliste wuerde jede
    "kein ist schlecht"-Aussage trivial wahr machen."""
    quelle = _fall("a1-enum-attribut-dict")
    findings = scan_source(quelle, "<ac20>", _thunder_spec())  # noqa: F821
    assert len(findings) > 0, "Bekannter Verstoss haette > 0 Funde liefern muessen"


def test_ac21_marker_mit_ausreichender_begruendung_laesst_durch():
    """AC-21: Marker mit >= 15 sinnvollen Zeichen laesst den Fund durch."""
    quelle = _fall("e21-marker-ausreichend")
    findings = scan_source(quelle, "<e21-ok>", _thunder_spec())  # noqa: F821
    assert findings == [], f"Ausreichender Marker muss durchlassen: {_refs(findings)}"


def test_ac21_marker_ohne_ausreichende_begruendung_bleibt_rot():
    """AC-21 Gegenprobe: derselbe Marker mit einer Alibi-Begruendung unter 15
    Zeichen ("x") zaehlt nicht."""
    quelle = _fall("e21-marker-unzureichend")
    findings = scan_source(quelle, "<e21-alibi>", _thunder_spec())  # noqa: F821
    assert len(findings) == 1, f"Alibi-Marker darf nicht durchlassen: {_refs(findings)}"


@pytest.mark.parametrize(
    "fall",
    [
        "e21-marker-nur-punkte",  # 15 Punkte
        "e21-marker-nur-striche",  # 15 Bindestriche
        "e21-marker-nur-wiederholung",  # 15 gleiche Buchstaben
        "e21-marker-grenze-14",  # 14 sinnvolle Zeichen
    ],
)
def test_ac21_fuellzeichen_statt_begruendung_bleiben_rot(fall):
    """AC-21: Zeichen ohne Aussage sind keine Begruendung.

    Fuenfzehn Punkte/Bindestriche haben Laenge 15, aber null sinnvolle Zeichen;
    fuenfzehn gleiche Buchstaben haben Laenge 15, aber nur EIN verschiedenes.
    Wer den Notausgang der Ratsche so oeffnen koennte, stellt den Waechter
    still, ohne eine Begruendung zu formulieren.
    """
    findings = scan_source(_fall(fall), f"<{fall}>", _thunder_spec())  # noqa: F821
    assert len(findings) == 1, f"{fall} darf nicht durchlassen: {_refs(findings)}"


@pytest.mark.parametrize(
    "fall",
    [
        "e21-marker-umlaute",  # 16 sinnvolle Zeichen, deutsche Begruendung
        "e21-marker-grenze-15",  # exakt 15 sinnvolle Zeichen
    ],
)
def test_ac21_deutsche_begruendung_mit_umlauten_laesst_durch(fall):
    """AC-21 Gegenprobe: Umlaute zaehlen als sinnvolle Zeichen -- unsere
    Begruendungen sind auf Deutsch, ein zu scharfer Filter wuerde echte
    Duldungen abweisen. Zusammen mit der 14er-Probe die Grenze von beiden
    Seiten."""
    findings = scan_source(_fall(fall), f"<{fall}>", _thunder_spec())  # noqa: F821
    assert findings == [], f"{fall} muss durchlassen: {_refs(findings)}"


def test_ac22_pruefdatum_ist_in_beiden_waechterdateien_und_der_ratschen_tabelle_auffindbar():
    """AC-22: ``grep -n "2026-11-01"`` findet einen Treffer in beiden
    Waechterdateien UND in der Tabelle "Regel-Budget: Pruefdaten im
    Ueberblick" in ``docs/reference/gates_und_ratschen.md``. Die Ratschen-
    Tabellenzeile ist ausdruecklich GREEN-Arbeit (Spec Affected Files) --
    dieser Test bleibt bis dahin rot, weil die dritte Fundstelle fehlt.
    Ausdrueckliche Ausnahme von der Dateiinhalt-Check-Regel (CLAUDE.md): hier
    wird reine Metadaten-Praesenz gezaehlt, kein Laufzeitverhalten.

    Die Ratschen-Tabelle traegt BEREITS zwei fremde Eintraege mit demselben
    Datum (Mutations-Gegenprobe, Breiter Testlauf gesperrt) -- eine reine
    ``"2026-11-01" in text``-Pruefung waere dort unabhaengig von dieser
    Lieferung immer schon wahr und damit ein Scheinbefund. Verlangt wird
    deshalb eine ZEILE, die BEIDES traegt: das Datum UND einen erkennbaren
    Bezug auf diesen Waechter (Thunder-Scale/Gewitter-Stufenskala).
    """  # doc-compliance-test
    waechterdateien = [
        REPO_ROOT / "tests/tdd/test_thunder_scale_local_copy_guard.py",
        REPO_ROOT
        / "frontend/src/lib/components/shared/weather-metrics-tab/__tests__/thunderScaleLocalCopyGuard.test.ts",
    ]
    fehlend = [str(z) for z in waechterdateien if "2026-11-01" not in z.read_text("utf-8")]

    ratschen = REPO_ROOT / "docs/reference/gates_und_ratschen.md"
    eigene_zeile = [
        zeile
        for zeile in ratschen.read_text("utf-8").splitlines()
        if "2026-11-01" in zeile
        and ("thunder" in zeile.lower() or "gewitter" in zeile.lower())
    ]
    if not eigene_zeile:
        fehlend.append(f"{ratschen} (keine Zeile mit 2026-11-01 UND Thunder-/Gewitter-Bezug)")

    assert not fehlend, f"Pruefdatum 2026-11-01 fehlt in: {fehlend}"


_AC23_PROGRAMME = {"node", "npm", "npx", "tsc", "svelte"}

# Subprozess-Einstiegspunkte, die die Waechterdatei NIE mit einem Node-/TS-/
# Svelte-Programm aufrufen darf. Bewusste, dokumentierte Grenze -- fuer den
# SELBSTBEZUEGLICHEN Pruefzweck dieses eigenen Moduls als theoretisch
# eingestuft und daher NICHT implementiert: Alias-Importe
# (``import subprocess as sp``), ein indirekter Aufruf ueber eine Variable
# (``lauf = subprocess.run; lauf(...)``), ein per f-String zusammengesetzter
# Programmname sowie ``shell=True`` mit einem einzigen Kommando-String.
_AC23_SUBPROZESS_EINSTIEGSPUNKTE = {
    ("subprocess", "run"),
    ("subprocess", "check_output"),
    ("subprocess", "check_call"),
    ("subprocess", "call"),
    ("subprocess", "Popen"),
    ("os", "system"),
    ("os", "popen"),
}


def _ist_subprozess_aufruf(func) -> bool:
    if not isinstance(func, ast.Attribute) or not isinstance(func.value, ast.Name):
        return False
    paar = (func.value.id, func.attr)
    return paar in _AC23_SUBPROZESS_EINSTIEGSPUNKTE or (
        func.value.id == "os" and func.attr.startswith("exec")
    )


def _ac23_sammle_stringargs(node, ziel):
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        ziel.append(node.value)
    elif isinstance(node, (ast.List, ast.Tuple)):
        for e in node.elts:
            _ac23_sammle_stringargs(e, ziel)


def _programmwort(text: str) -> str:
    """Eigenes Wort bzw. Pfad-Endstueck von ``text`` -- kein Teilstring-
    Zufallstreffer, sonst schluege z.B. "node_modules" faelschlich an."""
    erstes = text.strip().split()[0] if text.strip() else ""
    return erstes.replace("\\", "/").rsplit("/", 1)[-1].lower()


def _ac23_subprozess_treffer(baum) -> list:
    """Findet Subprozess-Aufrufe (``subprocess.run`` & Co., ``os.system``,
    ``os.popen``, ``os.exec*``-Familie) deren Argumente auf Node-/TS-/Svelte-
    Werkzeuge verweisen -- das ist die inhaltlich gemeinte Zusicherung von
    AC-23, nicht eine Substring-Suche ueber ALLE String-Konstanten (die auf
    dieser Datei selbst IMMER anschlaegt, weil Testnamen/Docstrings/Fixture-
    Texte die Woerter zwangsläufig fuehren)."""
    treffer = []
    for node in ast.walk(baum):
        if not isinstance(node, ast.Call) or not _ist_subprozess_aufruf(node.func):
            continue
        args: list = []
        for a in node.args:
            _ac23_sammle_stringargs(a, args)
        treffer += [wert for wert in args if _programmwort(wert) in _AC23_PROGRAMME]
    return treffer


def _ac23_import_treffer(baum) -> list:
    """Findet Importe eines Node-/TS-/Svelte-Pakets -- die zweite Haelfte der
    AC-23-Zusicherung ('Importe UND Subprozess-Aufrufe', Spec
    ``docs/specs/modules/thunder_scale_guard.md:434-440``). Ohne diese
    Haelfte waere ein eingeschmuggeltes ``import svelte`` fuer die
    Subprozess-Pruefung oben unsichtbar."""
    treffer = []
    for node in ast.walk(baum):
        if isinstance(node, ast.Import):
            treffer += [
                a.name for a in node.names if a.name.split(".")[0] in _AC23_PROGRAMME
            ]
        elif isinstance(node, ast.ImportFrom) and node.module:
            if node.module.split(".")[0] in _AC23_PROGRAMME:
                treffer.append(node.module)
    return treffer


def test_ac23_backend_waechter_ruft_weder_node_tsc_svelte_auf_noch_importiert_es():
    """AC-23: der Backend-Waechter enthaelt strukturell weder einen Import
    noch einen Subprozess-Aufruf einer Node-/TS-/Svelte-Laufzeit -- beide
    Haelften der Zusicherung ZUSAMMEN, wie von der Spec verlangt
    (``docs/specs/modules/thunder_scale_guard.md:434-440``: "Importe UND
    Subprozess-Aufrufe"). Per AST geprueft, nicht per naiver Substring-Suche
    ueber alle String-Konstanten -- eine naive Pruefung waere auf DIESER
    Datei immer rot, weil sie die Woerter "node"/"tsc"/"svelte" zwangslaeufig
    in Testnamen, Docstrings und Fixture-Texten fuehrt."""
    baum = ast.parse(Path(__file__).read_text("utf-8"), filename=__file__)
    subprozess_treffer = _ac23_subprozess_treffer(baum)
    import_treffer = _ac23_import_treffer(baum)
    assert not subprozess_treffer and not import_treffer, (
        "Verbotene Node-/TS-/Svelte-Referenz in der unveraenderten "
        f"Waechterdatei gefunden -- Subprozess: {subprozess_treffer}, "
        f"Import: {import_treffer}"
    )


def test_ac23_positivkontrolle_erkennt_eingeschmuggelten_node_subprozessaufruf():
    """AC23 Positivkontrolle: ohne sie waere der Nullbefund oben auch dann
    wahr, wenn die Erkennung selbst blind ist (Muster "Nullbefund ohne
    Varianz ist kein Nullbefund"). Genau die Aufrufform, die der
    Frontend-Waechter selbst benutzt (``subprocess.run(["node", ...])``),
    MUSS anschlagen -- als Quelltext-String konstruiert, KEINE echte Datei."""
    geschmuggelt = 'import subprocess\nsubprocess.run(["node", "--eval", "1"])\n'
    baum = ast.parse(geschmuggelt, filename="<geschmuggelt>")
    treffer = _ac23_subprozess_treffer(baum)
    assert treffer == ["node"], (
        f"Eingeschmuggelter node-Subprozessaufruf haette gefunden werden muessen: {treffer}"
    )


@pytest.mark.parametrize(
    "modul,attribut",
    [
        ("subprocess", "run"),
        ("subprocess", "check_output"),
        ("subprocess", "check_call"),
        ("subprocess", "call"),
        ("subprocess", "Popen"),
        ("os", "system"),
        ("os", "popen"),
    ],
)
def test_ac23_positivkontrolle_erkennt_jeden_subprozess_einstiegspunkt(modul, attribut):
    """AC-23 F002: jeder Subprozess-Einstiegspunkt EINZELN geprueft, mit
    einer vom Prod-Wortlaut UNABHAENGIG hier ausgeschriebenen Liste -- stuende
    diese Liste stattdessen ``_AC23_SUBPROZESS_EINSTIEGSPUNKTE`` gleich, wuerde
    das Streichen eines Eintrags dort den zugehoerigen Testfall stillschweigend
    MITLOESCHEN statt ihn rot zu faerben. ``os.system``/``os.popen`` nehmen ein
    einzelnes Kommando entgegen, alle anderen eine Argv-Liste."""
    if modul == "os":
        quelle = f'import os\nos.{attribut}("node")\n'
    else:
        quelle = f'import subprocess\nsubprocess.{attribut}(["node", "--eval", "1"])\n'
    baum = ast.parse(quelle, filename=f"<geschmuggelt-{modul}-{attribut}>")
    treffer = _ac23_subprozess_treffer(baum)
    assert treffer == ["node"], (
        f"{modul}.{attribut} haette den eingeschmuggelten node-Aufruf finden "
        f"muessen: {treffer}"
    )


@pytest.mark.parametrize(
    "quelle,modul_name",
    [
        ('import svelte\n', "svelte"),
        ('import svelte.compiler\n', "svelte"),
        ('from svelte import compile as c\n', "svelte"),
        ('import node\n', "node"),
    ],
)
def test_ac23_positivkontrolle_erkennt_eingeschmuggelten_node_svelte_import(quelle, modul_name):
    """AC-23 F001 Positivkontrolle fuer die Import-Haelfte -- analog zur
    Subprozess-Positivkontrolle: ein eingeschmuggeltes ``import svelte`` bzw.
    ``from svelte import x`` MUSS anschlagen, als Quelltext-String
    konstruiert, KEINE echte Datei."""
    baum = ast.parse(quelle, filename=f"<geschmuggelt-import-{modul_name}>")
    treffer = _ac23_import_treffer(baum)
    assert treffer, f"Eingeschmuggelter Import haette gefunden werden muessen: {quelle!r}"


@pytest.mark.parametrize("text", ["node", "node --eval 1"])
def test_ac23_programmwort_erkennt_eigenes_wort(text):
    """AC-23 F003: ``node`` als EIGENES Wort (mit und ohne Argumente danach)
    muss anschlagen."""
    assert _programmwort(text) == "node"
    assert _programmwort(text) in _AC23_PROGRAMME


def test_ac23_programmwort_erkennt_pfad_endstueck():
    """AC-23 F003 Gegenrichtung: ``/usr/bin/node`` als Pfad-Endstueck muss
    ebenso anschlagen -- ohne die Pfad-Aufspaltung waere der volle Pfadstring
    kein Treffer gegen die Programmnamen-Menge."""
    assert _programmwort("/usr/bin/node") == "node"
    assert _programmwort("/usr/bin/node") in _AC23_PROGRAMME


@pytest.mark.parametrize(
    "text", ["node_modules", "node_modules/.bin/webpack", "renderer.js node_modules"]
)
def test_ac23_programmwort_node_modules_und_aehnliche_bleiben_unauffaellig(text):
    """AC-23 F003 Nicht-Treffer-Richtung: ``node_modules`` und Varianten davon
    duerfen NICHT anschlagen -- ohne Wortgrenzen-/Pfad-Endstueck-Logik wuerde
    ein naiver Teilstring-Vergleich (``"node" in text``) hier faelschlich
    zuschlagen."""
    assert _programmwort(text) not in _AC23_PROGRAMME


def test_ac23_node_modules_als_subprozess_argument_bleibt_unauffaellig():
    """AC-23 F003 Ende-zu-Ende: dieselbe Nicht-Treffer-Probe nicht nur gegen
    ``_programmwort`` direkt, sondern durch den vollen Erkennungspfad --
    schuetzt zusaetzlich gegen eine Mutation an der AUFRUFSTELLE (z.B.
    ``any(p in wert for p in PROGRAMME)`` statt der Wortgrenzen-Pruefung)."""
    quelle = 'import subprocess\nsubprocess.run(["node_modules/.bin/webpack", "--config", "x"])\n'
    baum = ast.parse(quelle, filename="<node-modules-kein-treffer>")
    assert _ac23_subprozess_treffer(baum) == []


def test_ac23_waechtermodul_ist_syntaktisch_parsebar():
    """AC-23: dieses Modul selbst bleibt beim Hinzufuegen syntaktisch
    parsebar -- der eigentliche Nachweis fuer die volle ``tests/``-Collection
    laeuft separat ueber ``uv run pytest tests/ --collect-only -q`` (Artefakt
    ``collect-only-red.txt``); dieser Test prueft absichtlich NUR, was sein
    Name behauptet (``ast.parse`` auf ``__file__``), keine volle Collection."""
    import ast as _ast

    _ast.parse(Path(__file__).read_text("utf-8"), filename=__file__)


# ---------------------------------------------------------------------------
# Wiederverwendbarkeit des Erkennungs-Kerns (AC-24)
# ---------------------------------------------------------------------------


def test_ac24_kern_meldet_eine_andere_stufenmenge_ohne_kernaenderung():
    """AC-24: derselbe Kern, aufgerufen mit ``RiskLevel``-Parametern statt
    ``ThunderLevel``, meldet die Fundstellen dieser anderen Skala. Ein
    Aufruf mit den Gewitter-Parametern gegen dieselbe Fixture bleibt still
    -- der Kern richtet sich nach den uebergebenen Parametern, nicht nach
    einer eingebauten Annahme."""
    quelle = _fall("f24-risklevel-liste")
    risk_findings = scan_source(quelle, "<f24-risk>", _risk_spec())  # noqa: F821
    assert len(risk_findings) == 1, (
        f"RiskLevel-Parameter haetten einen Fund liefern muessen: {_refs(risk_findings)}"
    )

    thunder_findings = scan_source(quelle, "<f24-thunder>", _thunder_spec())  # noqa: F821
    assert thunder_findings == [], (
        f"Gewitter-Parameter muessen auf einer RiskLevel-Fixture still bleiben: "
        f"{_refs(thunder_findings)}"
    )


def test_ac24_auch_der_namens_scope_von_regel_c_stammt_aus_den_parametern():
    """AC-24, zweiter Beleg -- fuer REGEL C statt Regel A. Der Test oben laeuft
    ueber eine reine Liste und beruehrt die Namens-Scope-Kette nie; eine in
    ``_im_namens_scope`` fest verdrahtete Annahme ("thunder"/"gewitter") bliebe
    davon unberuehrt und der AC-Wortlaut ("richtet sich nach den uebergebenen
    Parametern") waere unbelegt.

    Dieselbe Fixture, zwei Parametersaetze: mit ``name_scope_tokens=("risk",
    "risiko")`` MUSS die Zahlen-Schwellenkette in ``_risiko_stufe_aus_zahl``
    gemeldet werden, mit den Gewitter-Parametern MUSS derselbe Quelltext still
    bleiben. Nur beides zusammen zeigt, dass der Scope-Vergleich aus ``spec``
    kommt und nicht aus dem Kern."""
    quelle = _fall("f24-risklevel-zahlen-schwelle")

    risk_findings = scan_source(quelle, "<f24-risk-c>", _risk_spec())  # noqa: F821
    assert [f.rule for f in risk_findings] == ["C"], (
        "RiskLevel-Parameter haetten genau einen Regel-C-Fund liefern muessen "
        f"(Namens-Scope 'risiko'): {_refs(risk_findings)}"
    )

    thunder_findings = scan_source(quelle, "<f24-thunder-c>", _thunder_spec())  # noqa: F821
    assert thunder_findings == [], (
        "Gewitter-Parameter duerfen auf einer Funktion ohne thunder/gewitter im "
        f"Namen nicht melden: {_refs(thunder_findings)}"
    )
