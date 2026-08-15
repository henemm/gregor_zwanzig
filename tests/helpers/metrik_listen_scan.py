"""Erkennungs-Kern der Metrik-Listen-Ratsche (Issue #1856, Epic #1435 E7).

SPEC: docs/specs/modules/fix_1856_e7_metrik_listen_waechter.md

Stufe 1 — Entdeckung (``scanne_register_listen``): AST-Scan ueber
``dict``/``set``/``list``/``tuple``. Eine Sammlung gilt als Register-Liste,
wenn sie >= 2 verschiedene konstante String-Elemente hat und ALLE davon
Register-Kennungen sind. Bei ``dict`` zaehlen Schluessel und Werte getrennt —
eine Uebersetzungstabelle INS Register traegt die Kennungen als Werte.

Stufe 2 — Gueltigkeit (``REGISTERED_LISTS``, ``pruefe_registrierte_liste``):
jede registrierte Liste wird ueber ihren NAMEN aufgeloest und ihre Kennungen
UNGEFILTERT gegen ``_METRICS`` geprueft.

🔴 Stufe 2 haengt bewusst nicht an der Quote aus Stufe 1. Haengte sie daran,
kippte ein einzelner Tippfehler die Liste aus der Prueffmenge — und der
Waechter schwiege genau dort, wo er reden soll. ``_literal`` gibt deshalb
zurueck, was im Quelltext STEHT, nicht was das Register kennt.

Bauprinzipien (E3b-Ratsche): echter AST statt Regex · Soll-Kennungen aus dem
Register statt von Hand · Nichtstun ist kein Bestehen · Pruefling aus DIESEM
Arbeitsbaum (#1409, ``parents[2]``).

Grenzen (Spec „Known Limitations"):

* ``if metric_id == "…"``-Ketten und Comprehensions bleiben unsichtbar. Dazu
  zaehlt ``if metric_id in ("wind", "gust")``: ein Tupel rechts von ``in``
  ordnet nichts je Groesse ZU, es prueft Zugehoerigkeit — keine Festlegung im
  Sinne von AC-2. Wuerde es gemeldet, braeuchten fuenf harmlose Stellen ein
  Fluchtventil, und eine Ausnahmeliste aus Rauschen entwertet die echten
  Eintraege. Ausgeschlossen wird strukturell (Elternknoten ``ast.Compare``
  mit ``ast.In``), nicht per Namensheuristik.
* Quote 0 % bleibt unsichtbar (Pruefstein ``HAZARD_SMS_SYMBOLS``, 0/10):
  Falsch-Positive sind schlimmer als eine Restluecke.
* ``_literal`` sieht nur Literale, keine zur Laufzeit berechnete Sammlung.
  Zwei Registrierungen lesen deshalb das ECHTE Objekt statt des Literals:
  ``METRIC_PRIORITY`` (dort zaehlt der Laufzeitstand fuer die
  Vollstaendigkeit) und ``HOURLY_EXCLUSION_REASON`` (#1728 S1 traegt vier von
  sieben Schluesseln per Schleife nach). Die uebrigen 40 bleiben literal —
  Laufzeit-Lesen fuer alle hiesse, den Wirksamkeitsnachweis gegen ERFUNDENE
  Eingaben aufzugeben: eine Wegwerf-Datei laesst sich scannen, aber nicht
  importieren.
* Sind bei einem ``dict`` BEIDE Seiten vollstaendig Kennungen, meldet Stufe 1
  nur die Schluesselseite (``_scanne_datei`` bricht nach der ersten
  qualifizierenden Seite ab). Bewusst so: keine reale Registrierung hat diese
  Form, und zwei Fundstellen je Sammlung verdoppelten die Registrierung jeder
  gewoehnlichen Tabelle. Wer eine solche Tabelle anlegt, registriert die
  Werteseite ausdruecklich — Stufe 2 prueft sie dann unabhaengig vom Scan.

Regel-Budget (CLAUDE.md): Pruefdatum 2026-11-15.
"""
from __future__ import annotations

import ast
import io
import re
import tokenize
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Iterable, Iterator, Mapping, Optional

from app.metric_catalog import _METRICS, get_all_metrics
from output.renderers.channel_layout import METRIC_PRIORITY
from output.renderers.compare_hourly_metric_ids import HOURLY_EXCLUSION_REASON

REPO_ROOT = Path(__file__).resolve().parents[2]

#: Soll-Menge: alle 32 Registereinheiten (28 vor #1728 S1). NICHT
#: ``get_all_metrics()`` (29) — dessen ``selectable=False``-Filter wirft
#: ``cape``, ``confidence`` und ``temperature_cold`` weg, die dann
#: faelschlich als unbekannt gaelten.
KENNUNGEN: frozenset[str] = frozenset(m.id for m in _METRICS)

MARKER = "gz-fremdvokabular:"
MINDEST_BEGRUENDUNG = 15
MINDEST_ELEMENTE = 2
TICKET = re.compile(r"#\d+")


@dataclass(frozen=True)
class Fundstelle:
    """Eine Sammlung, die nach Wettergroesse schluesselt."""

    datei: Path
    zeile: int
    seite: str                          # "schluessel" | "wert" | "element"
    kennungen: tuple[str, ...]
    name: Optional[str] = None
    freigestellt: Optional[str] = None  # Begruendung aus dem Fluchtventil

    @property
    def schluessel(self) -> str:
        """Registrierungs-Schluessel: Modulname + Name der Sammlung."""
        return f"{self.datei.stem}.{self.name}"

    def __str__(self) -> str:
        try:
            pfad = self.datei.resolve().relative_to(REPO_ROOT).as_posix()
        except ValueError:
            pfad = str(self.datei)
        return f"{pfad}:{self.zeile} {self.name or '<unbenannt>'} [{self.seite}]"

def _seiten(knoten: ast.AST) -> list[tuple[str, list[str]]]:
    """Die getrennt zu zaehlenden Seiten einer Sammlung."""
    def konstant(teile: Iterable[Optional[ast.expr]]) -> list[str]:
        return [t.value for t in teile
                if isinstance(t, ast.Constant) and isinstance(t.value, str)]
    if isinstance(knoten, ast.Dict):
        return [("schluessel", konstant(knoten.keys)),
                ("wert", konstant(knoten.values))]
    if isinstance(knoten, (ast.Set, ast.List, ast.Tuple)):
        return [("element", konstant(knoten.elts))]
    return []

def _benennung(baum: ast.AST) -> dict[int, tuple[str, int]]:
    """Knoten-Id -> (Name, Zeile). Steigt durch Sammlungen, Aufrufe und
    ``lambda`` hindurch ab, damit auch verschachtelte Listen einen sprechenden
    Namen tragen (``WEATHER_TEMPLATES['wandern']['metrics']``)."""
    treffer: dict[int, tuple[str, int]] = {}

    def vergib(knoten: ast.AST, name: str, zeile: int) -> None:
        treffer.setdefault(id(knoten), (name, zeile))
        if isinstance(knoten, ast.Dict):
            for schl, wert in zip(knoten.keys, knoten.values):
                if schl is not None:
                    vergib(wert, f"{name}[{ast.unparse(schl)}]", wert.lineno)
        elif isinstance(knoten, (ast.List, ast.Tuple, ast.Set)):
            for nr, teil in enumerate(knoten.elts):
                vergib(teil, f"{name}[{nr}]", teil.lineno)
        elif isinstance(knoten, ast.Call):
            for arg in knoten.args:
                vergib(arg, name, arg.lineno)
            for kw in knoten.keywords:
                vergib(kw.value, name if kw.arg is None else f"{name}.{kw.arg}",
                       kw.value.lineno)
        elif isinstance(knoten, ast.Lambda):
            vergib(knoten.body, name, knoten.body.lineno)

    for anw in ast.walk(baum):
        ziel = None
        if (isinstance(anw, ast.Assign) and len(anw.targets) == 1
                and isinstance(anw.targets[0], ast.Name)):
            ziel = anw.targets[0].id
        elif isinstance(anw, ast.AnnAssign) and isinstance(anw.target, ast.Name):
            ziel = anw.target.id
        if ziel is not None and anw.value is not None:
            vergib(anw.value, ziel, anw.lineno)
    return treffer

def _mitglieds_operanden(baum: ast.AST) -> set[int]:
    """Ids der Literale rechts von ``in``/``not in`` — Zugehoerigkeitspruefung,
    keine Festlegung je Groesse (s. Modul-Docstring, Grenzen)."""
    ids: set[int] = set()
    for knoten in ast.walk(baum):
        if isinstance(knoten, ast.Compare) and any(
                isinstance(op, (ast.In, ast.NotIn)) for op in knoten.ops):
            ids.update(id(v) for v in knoten.comparators)
    return ids

def _kommentare(quelltext: str) -> dict[int, tuple[str, bool]]:
    """Zeile -> (Kommentartext, steht allein auf der Zeile)."""
    zeilen = quelltext.splitlines()
    gefunden: dict[int, tuple[str, bool]] = {}
    try:
        for tok in tokenize.generate_tokens(io.StringIO(quelltext).readline):
            if tok.type == tokenize.COMMENT:
                nr, spalte = tok.start
                vorspann = zeilen[nr - 1][:spalte] if nr <= len(zeilen) else ""
                gefunden[nr] = (tok.string, not vorspann.strip())
    except (tokenize.TokenError, IndentationError, SyntaxError):
        return {}
    return gefunden

def _begruendung(kommentar: str) -> Optional[str]:
    if MARKER not in kommentar:
        return None
    text = kommentar.split(MARKER, 1)[1].strip()
    return text if len(text) >= MINDEST_BEGRUENDUNG else None

def _freistellung(kommentare: dict[int, tuple[str, bool]],
                  von: int, bis: int) -> Optional[str]:
    """``# gz-fremdvokabular:`` AN der Fundstelle oder im zusammenhaengenden
    Kommentarblock DIREKT darueber — nicht als Umgebungsfenster. Sonst stellte
    ein Kommentar alles frei, was zufaellig in der Naehe steht (in
    ``metric_catalog.py`` liegen sieben Register-Listen dicht beieinander)."""
    for nr in range(von, bis + 1):
        eintrag = kommentare.get(nr)
        if eintrag and (grund := _begruendung(eintrag[0])):
            return grund
    nr = von - 1
    while (eintrag := kommentare.get(nr)) is not None and eintrag[1]:
        if grund := _begruendung(eintrag[0]):
            return grund
        nr -= 1
    return None

def _python_dateien(wurzeln: Iterable[Path | str]) -> Iterator[Path]:
    """``wurzeln`` sind Verzeichnisse ODER einzelne Dateien."""
    for wurzel in wurzeln:
        pfad = Path(wurzel)
        if pfad.is_dir():
            yield from sorted(pfad.rglob("*.py"))
        elif pfad.suffix == ".py":
            yield pfad

def _scanne_datei(pfad: Path) -> list[Fundstelle]:
    quelltext = pfad.read_text(encoding="utf-8")
    baum = ast.parse(quelltext, filename=str(pfad))
    namen, bedingungen = _benennung(baum), _mitglieds_operanden(baum)
    kommentare = _kommentare(quelltext)
    funde: list[Fundstelle] = []
    for knoten in ast.walk(baum):
        if id(knoten) in bedingungen:
            continue
        for seite, strings in _seiten(knoten):
            kennungen = set(strings)
            if len(kennungen) < MINDEST_ELEMENTE or not kennungen <= KENNUNGEN:
                continue
            name, zeile = namen.get(id(knoten), (None, knoten.lineno))
            funde.append(Fundstelle(
                datei=pfad, zeile=zeile, seite=seite,
                kennungen=tuple(sorted(kennungen)), name=name,
                freigestellt=_freistellung(kommentare, min(zeile, knoten.lineno),
                                           knoten.end_lineno or knoten.lineno)))
            break  # Schluesselseite hat Vorrang vor der Wertseite
    return funde

def scanne_register_listen(wurzeln: Iterable[Path | str]) -> list[Fundstelle]:
    """Alle Sammlungen unter ``wurzeln``, die nach Wettergroesse schluesseln —
    einschliesslich der registrierten und der freigestellten."""
    funde: list[Fundstelle] = []
    for pfad in _python_dateien(wurzeln):
        funde.extend(_scanne_datei(pfad))
    return funde


@dataclass(frozen=True)
class RegisteredList:
    """Eine bekannte Register-Liste und wie ihre Kennungen zu lesen sind."""

    ist: Callable[[], set[str]]
    ort: str
    soll_vollstaendig: Optional[Callable[[], set[str]]] = None
    fehlend_erlaubt: frozenset[str] = frozenset()
    begruendung: str = ""

_CACHE: dict[Path, tuple[dict[int, tuple[str, int]], ast.AST]] = {}

def _literal(pfad: Path, name: str, seite: str) -> tuple[list[str], int]:
    """Die konstanten Strings der benannten Sammlung — UNGEFILTERT.

    Aufgeloest wird ueber den NAMEN, nie ueber die Quote aus Stufe 1: nur so
    faellt ein Tippfehler auf, statt die Liste aus der Prueffmenge zu kippen.
    Steht derselbe Name mehrfach in einer Datei (zwei Funktionen, dieselbe
    lokale Tabelle), werden ALLE Vorkommen zusammengefasst — sonst bliebe das
    zweite unter demselben Schluessel ungeprueft.
    """
    if pfad not in _CACHE:
        baum = ast.parse(pfad.read_text(encoding="utf-8"), filename=str(pfad))
        _CACHE[pfad] = (_benennung(baum), baum)
    namen, baum = _CACHE[pfad]
    strings: list[str] = []
    zeile: Optional[int] = None
    for knoten in ast.walk(baum):
        treffer = namen.get(id(knoten))
        if treffer is None or treffer[0] != name:
            continue
        for gefunden, gelesen in _seiten(knoten):
            if gefunden == seite:
                strings += gelesen
                zeile = treffer[1] if zeile is None else zeile
    if zeile is None:
        raise LookupError(f"{name!r} ({seite}) steht nicht mehr in {pfad.name} "
                          "— umbenannt oder geloescht?")
    return strings, zeile

# Alle Fundstellen des AC-2-Scans (nachgemessen 2026-08-15 NACH #1728 S3:
# 46 in 12 Dateien unter src/ + api/; vor S3 waren es 42 — die vier
# Tagesrichtungs-Regelzeilen wurden erst sichtbar, als das Auswertungswort
# aus ``_DERIVED_METRIC_RULES`` fiel). Hier stehen 44 davon, die beiden
# uebrigen (``METRIC_PRIORITY``, ``HOURLY_EXCLUSION_REASON``) stehen unten als
# Laufzeit-Eintraege — zusammen 46 Registrierungen fuer 46 Fundstellen, 1:1;
# eigenstaendige Sammlungen 34 (``WEATHER_TEMPLATES`` 7,
# ``_ALERT_METRIC_TO_CATALOG_ID`` 2 und ``_DERIVED_METRIC_RULES`` 6 Zeilen
# gehoeren je zu einer).
# Datei, Name, geprueffte Seite — je Fundstelle EINE Zeile; die Aufloesung
# macht ``_literal`` generisch. Die Seite ist fachlich verschieden:
# "schluessel"/"element" = die Kennung STEHT dort; "wert" = Uebersetzung INS
# Register, deren Schluessel bewusst fremdes Vokabular sind (``col_key``,
# ``frontend_key``) und deshalb NIE geprueft werden.
_R = "src/output/renderers/"
_BESTAND: tuple[tuple[str, str, str], ...] = (
    ("src/app/loader.py", "report_config.daily_summary_metrics", "element"),
    # #1728 S1/S3: je Regel-Zeile eine Fundstelle. Bis S3 trugen die vier
    # Tagesrichtungs-Zeilen ([2]..[5]) neben den Kennungen ein Auswertungswort
    # ("min"/"max") und blieben damit beiden Stufen verborgen (Quote-Grenze,
    # s. Modul-Docstring). Mit S3 DEC-1 ist ``MetricConfig.aggregations``
    # abgeschafft, alle sechs Zeilen fuehren nur noch Kennungen — alle sechs
    # sind deshalb registriert.
    ("src/app/loader.py", "_DERIVED_METRIC_RULES[0]", "element"),
    ("src/app/loader.py", "_DERIVED_METRIC_RULES[1]", "element"),
    ("src/app/loader.py", "_DERIVED_METRIC_RULES[2]", "element"),
    ("src/app/loader.py", "_DERIVED_METRIC_RULES[3]", "element"),
    ("src/app/loader.py", "_DERIVED_METRIC_RULES[4]", "element"),
    ("src/app/loader.py", "_DERIVED_METRIC_RULES[5]", "element"),
    ("src/app/metric_catalog.py", "SMS_NULLFORM_METRIC_IDS", "element"),
    ("src/app/metric_catalog.py", "_SMS_SYMBOL_METRIC_IDS", "element"),
    ("src/app/metric_catalog.py", "SMS_SYMBOL_GRAMMAR", "schluessel"),
    ("src/app/metric_catalog.py", "SMS_MULTI_SYMBOLS_BY_METRIC", "schluessel"),
    ("src/app/metric_catalog.py", "COMPACT_LABEL_EXCEPTIONS", "schluessel"),
    ("src/app/metric_catalog.py", "WEATHER_TEMPLATES['alpen-trekking']['metrics']", "element"),
    ("src/app/metric_catalog.py", "WEATHER_TEMPLATES['wandern']['metrics']", "element"),
    ("src/app/metric_catalog.py", "WEATHER_TEMPLATES['skitouren']['metrics']", "element"),
    ("src/app/metric_catalog.py", "WEATHER_TEMPLATES['wintersport']['metrics']", "element"),
    ("src/app/metric_catalog.py", "WEATHER_TEMPLATES['radtour']['metrics']", "element"),
    ("src/app/metric_catalog.py", "WEATHER_TEMPLATES['wassersport']['metrics']", "element"),
    ("src/app/metric_catalog.py", "WEATHER_TEMPLATES['allgemein']['metrics']", "element"),
    ("src/app/models.py", "daily_summary_metrics.default_factory", "element"),
    # #1728 S1 hat ``_NIGHT_SCALAR_IDS`` in ``VISIBILITY_GATE_IDS`` umbenannt
    # und von 2 auf 6 Kennungen erweitert (die vier Tagesrichtungen kamen
    # hinzu) — dieselbe Liste, legitim gewachsen. Der alte Name meldete sich
    # als "zeigt ins Leere"; genau dafuer loest Stufe 2 ueber den Namen auf.
    (_R + "channel_layout.py", "VISIBILITY_GATE_IDS", "element"),
    (_R + "compare_hourly_metric_ids.py", "FRONTEND_TO_HOURLY_METRIC_ID", "wert"),
    (_R + "compare_hourly_metric_ids.py", "HOURLY_EXCLUDED_METRIC_IDS", "element"),
    (_R + "compare_hourly_metric_ids.py", "HOURLY_DEFAULT_METRIC_IDS", "element"),
    (_R + "compare_metric_ids.py", "RENDERER_TO_TRIP_METRIC_ID", "wert"),
    (_R + "email/compare_html.py", "_HOUR_FMT_OVERRIDES", "schluessel"),
    (_R + "email/compare_html.py", "_HOUR_SEV_OVERRIDES", "schluessel"),
    (_R + "email/helpers.py", "NO_HOURLY_COLUMN_METRIC_IDS", "element"),
    (_R + "email/helpers.py", "_AMPEL_KEY_TO_METRIC_ID", "wert"),
    (_R + "email/helpers.py", "_AMPEL_CAPABLE_METRIC_IDS", "element"),
    (_R + "email/helpers.py", "_PILL_CATALOG_ORDER", "element"),
    (_R + "email/helpers.py", "_PILL_CLASS1", "element"),
    (_R + "email/helpers.py", "_PILL_CLASS2", "element"),
    (_R + "email/helpers.py", "_id_to_sms_symbol", "schluessel"),
    (_R + "email/helpers.py", "_AGGREGATION_PILL_METRICS", "schluessel"),
    (_R + "email/helpers.py", "_DAY_WINDOW_PILL_IDS", "element"),
    (_R + "email/html.py", "_COL_KEY_TO_METRIC_ID", "wert"),
    (_R + "email/html.py", "_FALLBACK_COL_KEY_TO_METRIC_ID", "wert"),
    ("src/services/compare_alert.py", "_SUMMARY_KEY_TO_CATALOG_ID", "wert"),
    ("src/services/day_comparison.py", "_METRIC_ID_TO_ENTRY_ATTR", "schluessel"),
    ("src/services/day_comparison.py", "_DIRECTION_WORDS", "schluessel"),
    ("src/services/day_comparison.py", "_DISPLAY_SALIENCE_OVERRIDES", "schluessel"),
    ("src/services/weather_change_detection.py",
     "_ALERT_METRIC_TO_CATALOG_ID[AlertMetric.TEMPERATURE_MIN]", "element"),
    ("src/services/weather_change_detection.py",
     "_ALERT_METRIC_TO_CATALOG_ID[AlertMetric.SNOW_LINE]", "element"),
)

def _registriere(pfad_rel: str, name: str, seite: str) -> RegisteredList:
    pfad = REPO_ROOT / pfad_rel
    try:
        ort = f"{pfad_rel}:{_literal(pfad, name, seite)[1]}"
    except LookupError:
        ort = pfad_rel
    return RegisteredList(ist=lambda: set(_literal(pfad, name, seite)[0]), ort=ort)

REGISTERED_LISTS: dict[str, RegisteredList] = {
    f"{Path(pfad).stem}.{name}": _registriere(pfad, name, seite)
    for pfad, name, seite in _BESTAND
}

# Sondereintrag: die einzige Liste, bei der auch VOLLSTAENDIGKEIT fachlich
# gilt — sie entscheidet die Top-5-Anzeige fuer ALLE waehlbaren Groessen
# (channel_layout.py:143, ``METRIC_PRIORITY.get(pair[1], 0)``). Gelesen wird
# hier das echte Objekt statt des Literals: bei dieser einen zaehlt der Stand
# zur Laufzeit.
REGISTERED_LISTS["channel_layout.METRIC_PRIORITY"] = RegisteredList(
    ist=lambda: set(METRIC_PRIORITY),
    ort="src/output/renderers/channel_layout.py:60",
    soll_vollstaendig=lambda: {m.id for m in get_all_metrics()},
    fehlend_erlaubt=frozenset({
        "temperature_night", "wind_chill_night",
        "temperature_day_low", "temperature_day_high",
        "wind_chill_day_low", "wind_chill_day_high",
    }),
    begruendung=(
        "Befund #1856 (Epic #1435, Etappe E7): alle sechs Groessen sind "
        "eigenstaendig waehlbar (Nachtfenster seit #1484/#1660 A, die vier "
        "Tagesrichtungen seit #1728 Scheibe 1), stehen aber nicht in "
        "METRIC_PRIORITY und liegen ueber ``.get(pair[1], 0)`` "
        "(channel_layout.py:143) daher auf Prioritaet 0 — bei knappem Platz "
        "fallen sie als erste heraus. #1728 S1 haelt das fuer folgenlos, weil "
        "``VISIBILITY_GATE_IDS`` sie in ``render_for_channel`` (Zeile 107) "
        "vorher wegfiltert; ``auto_distribute`` filtert sie NICHT, weshalb die "
        "Bewertung offen ist. Entschieden und behoben wird sie in E6, nicht "
        "hier — E7 macht sie nur mechanisch reproduzierbar. Die Ausnahme darf "
        "nur schrumpfen; gewachsen ist sie allein um die vier neuen Groessen "
        "aus #1728, nicht um neue Nachsicht bei bestehenden."
    ),
)

# Zweiter Laufzeit-Eintrag: #1728 S1 traegt vier der sieben Schluessel per
# Schleife nach (compare_hourly_metric_ids.py:84-96). ``_literal`` saehe nur
# die drei literalen — ein Tippfehler in genau den vier neuen Kennungen
# entkaeme damit BEIDEN Stufen (Stufe 1 sieht die Schleife ohnehin nicht).
# Deshalb hier das echte Objekt. Bewacht wird die Fundstelle in ihrem
# Endzustand, nicht ihre Schreibweise.
REGISTERED_LISTS["compare_hourly_metric_ids.HOURLY_EXCLUSION_REASON"] = (
    RegisteredList(
        ist=lambda: set(HOURLY_EXCLUSION_REASON),
        ort="src/output/renderers/compare_hourly_metric_ids.py:69",
    )
)

def _ort_passt(fund: Fundstelle, ort: str) -> bool:
    """Schuetzt gegen gleiche Modulnamen in verschiedenen Verzeichnissen."""
    return fund.datei.resolve().as_posix().endswith(ort.rsplit(":", 1)[0])

def unregistrierte_register_listen(
        wurzeln: Iterable[Path | str]) -> list[Fundstelle]:
    """Die Fundstellen, die weder registriert noch freigestellt sind."""
    offen: list[Fundstelle] = []
    for fund in scanne_register_listen(wurzeln):
        reg = REGISTERED_LISTS.get(fund.schluessel)
        if fund.freigestellt or (reg is not None and _ort_passt(fund, reg.ort)):
            continue
        offen.append(fund)
    return offen

def pruefe_registrierte_liste(schluessel: str, reg: RegisteredList) -> list[str]:
    """Befund-Zeilen zu einer registrierten Liste; leere Liste = in Ordnung."""
    try:
        ist = set(reg.ist())
    except LookupError as fehler:
        return [f"{schluessel}: {fehler} Die Registrierung zeigt ins Leere."]
    befunde = [
        f"{schluessel}: {kennung!r} ist keine Register-Kennung — Tippfehler "
        f"oder geloeschte Groesse? Fundstelle {reg.ort}"
        for kennung in sorted(ist - KENNUNGEN)
    ]
    if reg.soll_vollstaendig is not None:
        befunde += [
            f"{schluessel}: {kennung!r} ist waehlbar, fehlt in dieser Liste "
            f"aber und steht in keiner Ausnahme. Fundstelle {reg.ort}"
            for kennung in sorted(
                set(reg.soll_vollstaendig()) - ist - set(reg.fehlend_erlaubt))
        ]
    text = reg.begruendung.strip()
    if reg.fehlend_erlaubt and (
            len(text) < MINDEST_BEGRUENDUNG or not TICKET.search(text)):
        befunde.append(
            f"{schluessel}: die Ausnahme {sorted(reg.fehlend_erlaubt)!r} traegt "
            f"keine Begruendung mit Ticket-Bezug (mind. {MINDEST_BEGRUENDUNG} "
            f"Zeichen und eine '#N'-Nummer) — {text!r}. Ein stiller Filter ist "
            "keine Ausnahme.")
    return befunde

def finde_kuerzel_kollisionen(kuerzel: Mapping[str, str]) -> list[str]:
    """Kuerzel, die zwei VERSCHIEDENE Groessen bezeichnen (AC-1).

    Gruppiert wird nach Metrik-Kennung (Schluessel), nicht nach Kuerzel-Wert —
    ``TH`` steht zweimal fuer dieselbe Groesse ``thunder``. Leere Kuerzel
    werden uebersprungen, nicht gruppiert: ``confidence`` fuehrt bewusst
    keines (#710), und zwei Luecken sind keine Doppelvergabe.
    """
    nach_wert: dict[str, list[str]] = {}
    for kennung, wert in sorted(kuerzel.items()):
        if wert and wert.strip():
            nach_wert.setdefault(wert, []).append(kennung)
    return [f"{wert!r} bezeichnet {len(kenn)} verschiedene Groessen: "
            + ", ".join(kenn)
            for wert, kenn in sorted(nach_wert.items()) if len(kenn) > 1]
