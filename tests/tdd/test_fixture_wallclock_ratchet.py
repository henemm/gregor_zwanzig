"""Waechter (#1667 S1): keine Trip-Fixture baut Ankunftszeiten aus der rohen
Wanduhr, ohne sie auf einen Tagesbereich zu klemmen.

Das Anti-Muster
---------------
Eine Fixture setzt das Etappen-Datum aus der Wanduhr (``now.date()`` /
``date.today()``) und die Ankunftszeit ihrer Wegpunkte direkt aus
``(now +/- timedelta(...)).strftime("%H:%M")``. Ab einer bestimmten
Wanduhrzeit — bei ``+1h/+4h`` ab 23:00 UTC, bei ``+2h/+4h`` ab 22:00 UTC —
laeuft die Uhrzeit-Folge ueber Mitternacht und wird dadurch *steigend*
(``00:00 -> 03:00``) statt *fallend*. ``convert_trip_to_segments``
(``src/services/trip_segments.py:151-159``) erkennt eine Tagesgrenze aber nur
bei strikt fallender Uhrzeit, und ``wp_days[0]`` ist strukturell immer 0 —
ein Rollover VOR dem ersten Wegpunkt ist im Datenmodell nicht darstellbar.
Das Segment landet damit 23 Stunden in der Vergangenheit, der Guard „alle
Segmente vorbei" (``src/services/trip_alert.py:749-763``) greift, und
``check_radar_alerts()`` liefert 0 statt 1.

Gemessen, nicht hergeleitet: ``test_alert_urgency.py::
test_convective_radar_logs_high`` ist unter ``freeze_time`` auf
``2026-08-10T12:00:00+00:00`` gruen und unter ``2026-08-10T23:30:00+00:00``
rot (``assert 0 == 1``). Beide Laeufe liegen als Artefakt unter
``docs/artifacts/fix-1667-arrival-midnight-wrap/``.

🔴 **Diese Ratsche bewacht die TESTS, nicht das Produkt.** Sie sagt nichts
ueber die eigentliche Sicherheitsluecke aus #1667 (23:59-Klemme in
``src/core/naismith.py:54-60``, bis zu 11 h 50 min ohne Radar-Alarm fuer
einen Wanderer mit Spaetankunft). Diese wird erst von S2/S3 adressiert. Wer
aus „diese Datei ist gruen" schliesst, die Luecke sei zu, wiederholt genau
den Denkfehler, der #1667 ausgeloest hat.

Was der Scanner meldet
----------------------
``scan_wallclock_arrival_fixtures(tests_root)`` durchsucht ``tests_root``
rekursiv nach ``*.py`` und meldet jede Funktion, in der BEIDE Merkmale
zugleich auftreten:

1. **Wanduhr-Etappendatum** — ein Aufruf ``<jetzt>.date()`` (Empfaenger ist
   ein Name, der mit ``now``/``jetzt``/``heute`` beginnt, oder direkt ein
   ``datetime.now(...)``/``utcnow()``/``today()``-Aufruf) oder
   ``date.today()`` / ``datetime.today()`` / ``date_type.today()``.
2. **Ungeklemmte Ankunftszeit** — ein Aufruf ``X.strftime("%H:%M")``, bei dem
   ``X`` (ggf. ueber ein zwischengeschaltetes ``.astimezone(...)``) ein
   ``BinOp`` ist, in dem ein ``timedelta(...)`` vorkommt. Gemeldet wird die
   Zeile des ``strftime``-Aufrufs.

Gemeldet wird nur die Kombination. Ein Ruhezeitfenster ohne Etappendatum
(``tests/helpers/nowcast_gate_fixtures.py::quiet_window_now``,
``tests/tdd/test_compare_radar_alert.py::_quiet_hours_window_now``) ist
deshalb kein Fund — dort gibt es kein Segment, das in die Vergangenheit
rutschen koennte.

Namensaufloesung — und warum sie das Gegenmuster nicht mitfaengt
----------------------------------------------------------------
Bis 2026-08-10 sah der Scanner nur den direkten Rechenausdruck am
``strftime``. Eine einzige Zwischenvariable genuegte, um ihn zu umgehen —
``ankunft = now + timedelta(hours=1)`` … ``ankunft.strftime("%H:%M")`` ergab
NULL Funde bei identischem Anti-Muster. Das war keine schmale, dateispezifische
Ausnahme, sondern eine generische Bypass-Technik und machte den bleibenden
Schutz weitgehend wertlos (Adversary-Finding F004 zu #1667 S1).

Der Scanner loest Namen deshalb auf. Der Zielkonflikt, an dem die
Namensaufloesung urspruenglich verworfen wurde — das erprobte Gegenmuster
(``test_952_onset_alert_fidelity.py::_active_window``) hat am ``strftime``
ebenfalls nur einen Namen stehen — loest sich ueber die Frage **"ist der Name
AUSSCHLIESSLICH aus roher Wanduhr-Arithmetik gebunden?"**:

* Gegenmuster: ``start`` wird zuerst aus ``now_local + timedelta(...)``
  gebunden, in den Klemm-Zweigen aber ERNEUT aus ``tag_start``/``tag_ende``.
  Nicht alle Zuweisungen sind rohe Rechnungen ⇒ geklemmt ⇒ kein Fund. Genau
  die Klemmung, die den Namen sicher macht, ist das Merkmal, an dem er
  freigesprochen wird.
* Bypass: einzige Zuweisung, rohe Rechnung, nie neu gebunden ⇒ Fund.

Ketten ueber Zwischenschritte (``x = roh``; ``y = x.astimezone(tz)``;
``y.strftime(...)``) werden mitverfolgt. Belegt durch
``test_scanner_erkennt_den_bypass_ueber_eine_zwischenvariable``,
``test_scanner_erkennt_die_kette_ueber_astimezone_und_namen`` und die
Gegenprobe ``test_scanner_schweigt_bei_geklemmtem_namen``.

Grenzen, ehrlich benannt
-------------------------
Der Scanner arbeitet rein syntaktisch und **innerhalb einer Funktion**. Er
sieht nicht:

* Namen, die aus einer ANDEREN Funktion stammen (Rueckgabewerte werden nicht
  verfolgt) — deshalb schweigt er beim Gegenmuster auch dann, wenn der
  Aufrufer die geklemmten Werte weiterreicht;
* Uhrzeiten, die ueber eine Sammlung laufen (Liste, dict, Tupel-Entpackung):
  dort ist die Herkunft nicht mehr eindeutig einem Namen zuzuordnen, und der
  Scanner meldet im Zweifel NICHT — lieber ein uebersehener Fall als ein
  Falsch-Positiv, das die Ratsche unpassierbar macht;
* ob eine Klemmung fachlich RICHTIG ist. Er prueft nur, DASS der Name
  irgendwo anders gebunden wird.

Zwei Stellen im Bestand brauchen das Anti-Muster strukturell und stehen
deshalb begruendet in ``KNOWN_VIOLATIONS`` (Begruendung dort, nicht hier —
sie gehoert an den Eintrag).

Regel-Budget
------------
``EXPIRY`` (2026-11-08, +90 Tage) — Vorbild ``EXPIRY`` in
``.claude/hooks/test_naming_gate.py`` und
``tests/tdd/test_repo_path_hardcoding_ratchet.py``. Am Pruefdatum: hat die
Ratsche einen echten Rueckfall verhindert? Kein Fang => Rueckbau.

Spec: ``docs/specs/modules/fix_1667_s1_fixture_wanduhr.md``.
"""

from __future__ import annotations

import ast
import re
from dataclasses import dataclass
from datetime import date
from pathlib import Path

# Wurzel DIESES Checkouts (Worktree) — bewusst nicht das Hauptrepo (#1409):
# der Waechter muss den Baum pruefen, in dem gerade gearbeitet wird.
REPO_ROOT = Path(__file__).resolve().parents[2]
TESTS_ROOT = REPO_ROOT / "tests"

# Fixture-Quelltexte liegen AUSSERHALB der Scanflaeche `tests/**/*.py`
# (Endung .py.txt) — sonst meldete der Waechter seine eigenen Fixtures.
_FAELLE_DATEI = REPO_ROOT / "tests/fixtures/ratchet_cases/wallclock_arrival_faelle.py.txt"

# Pruefdatum des Regel-Budgets: 2026-11-08
EXPIRY = date(2026, 11, 8)

_HHMM = "%H:%M"
_WANDUHR_NAMEN = ("now", "jetzt", "heute")
_HEUTE_TRAEGER = {"date", "datetime", "date_type", "datetime_type"}

# 🔴 Diese Liste darf nur SCHRUMPFEN, nie wachsen — und sie darf NICHT gefuellt
# werden, um den Waechter gruen zu bekommen. Ein Eintrag ist nur zulaessig, wenn
# die Fixture das Anti-Muster STRUKTURELL braucht: wenn es keine Wegpunktzeit
# gibt, die die Pruefaussage traegt UND auf dem Etappentag darstellbar ist.
# „Umstellen waere aufwendig" ist kein Grund.
#
# Die beiden Eintraege unten entstanden, als die Namensaufloesung eingebaut
# wurde (Adversary-Finding F004): sie legte zwei Stellen frei, die der Scanner
# vorher gar nicht sehen konnte. Beide sind geprueft und begruendet:
#
# 1) test_alarm_zeitfenster_ziel.py::_radar_mails_fuer_spaetankunft
#    Baut die Ankunft aus `jetzt - 3 min` und braucht das auch: die Fixture
#    beweist den Randfall-Guard fuer eine SPAETANKUNFT relativ zum
#    Tagesfenster, und `day_window_end_hour` wird aus der Ortsstunde ebendieser
#    Ankunft abgeleitet. Ein geklemmtes Fenster wuerde die Ankunft verschieben
#    und damit die Pruefaussage zerstoeren. Statt der Klemmung kompensiert die
#    Fixture ueber die ORTSWAHL (Reykjavik, sonst Auckland), sodass Ortsdatum
#    == Etappendatum und Ortsstunde >= 1 gilt. Diese Kompensation ist der
#    einzige Fix im ganzen Slice, der ueber ALLE 1440 Minuten eines Tages
#    deterministisch bewacht wird —
#    `test_radar_fixture_ist_zu_jeder_tageszeit_kein_mitternachtsfenster`
#    iteriert 1440+3 synthetische Zeitpunkte, ohne gestellte Uhr. Der Schutz
#    ist hier also NICHT schwaecher als die Ratsche, sondern staerker.
#
# 2) test_starkregen_kurzfristhinweis.py::_trip_with_segment_offset
#    Die Pruefaussage IST die exakte Vorlaufzeit: 90 Minuten (jenseits von
#    NOWCAST_HORIZON_MIN=60) darf keinen Nowcast-Abruf ausloesen, 30 Minuten
#    schon. Jede Klemmung wuerde 90 auf weniger stauchen und den Test ins
#    Gegenteil verkehren. „Segmentbeginn exakt +90 min, auf dem Etappentag" ist
#    aber unrepraesentierbar, sobald weniger als 90 Minuten des lokalen Tages
#    uebrig sind — der erste Wegpunkt MUSS auf dem Etappentag liegen
#    (`wp_days[0]` ist strukturell 0), und ein Etappendatum ist genau ein
#    Kalendertag. Keine Zeitzone loest das: sie verschiebt das Fenster nur.
#    Die Datei erkennt das selbst und ueberspringt an der Grenze laut
#    (`pytest.skip`) — sie ist dort also nicht still falsch, sondern
#    hoerbar abwesend. Ein echter Fix braeuchte tagesuebergreifende Etappen,
#    also Produktivcode — Gegenstand von #1667 S3, nicht von S1.
#
# 🔴 Der Shrink-Waechter unten faengt nur VERALTETE Eintraege, nicht neue
# unbegruendete: eine Ausnahmeliste kann sich strukturell nicht selbst gegen
# Zuwachs schuetzen, und Code kann das nicht loesen. Jeder neue Eintrag ist
# deshalb review-pflichtig und braucht die Begruendung hier im Klartext —
# wer einen hinzufuegt, ohne dass ein Reviewer sie geprueft hat, hebelt den
# Waechter aus (Adversary-Finding F008 zu #1667 S1).
#
# Format je Eintrag: (repo-relativer Pfad, Funktionsname)
KNOWN_VIOLATIONS: frozenset[tuple[str, str]] = frozenset({
    ("tests/unit/test_alarm_zeitfenster_ziel.py", "_radar_mails_fuer_spaetankunft"),
    ("tests/tdd/test_starkregen_kurzfristhinweis.py", "_trip_with_segment_offset"),
})


@dataclass(frozen=True)
class Finding:
    """Eine Fundstelle: Datei, Funktion, Zeile des ``strftime``-Aufrufs."""

    path: Path
    function: str
    line: int

    @property
    def ref(self) -> str:
        return f"{self.path}:{self.line} ({self.function})"


def _ist_timedelta(node: ast.AST) -> bool:
    if not isinstance(node, ast.Call):
        return False
    f = node.func
    if isinstance(f, ast.Name) and f.id == "timedelta":
        return True
    return isinstance(f, ast.Attribute) and f.attr == "timedelta"


def _ist_wanduhr_traeger(node: ast.AST) -> bool:
    """Traegt ``node`` die aktuelle Wanduhr? (Empfaenger eines ``.date()``)."""
    if isinstance(node, ast.Name):
        # Fuehrende Unterstriche abstreifen: ``_now`` traegt die Wanduhr genauso
        # wie ``now``. Ohne das genuegte ein Unterstrich, um den Waechter zu
        # umgehen — gemessen an einer Mutation, die genau daran vorbeilief.
        return node.id.lstrip("_").lower().startswith(_WANDUHR_NAMEN)
    if isinstance(node, ast.Call):
        f = node.func
        if isinstance(f, ast.Attribute) and f.attr in {"now", "utcnow", "today"}:
            return True
        if isinstance(f, ast.Name) and f.id in {"now", "utcnow"}:
            return True
    return False


def _ist_wanduhr_datum(node: ast.AST) -> bool:
    """``now.date()``, ``date.today()``, ``datetime.today()``,
    ``date_type.today()`` — und ``stage_date()``.

    ``stage_date()`` gehoert dazu, weil es genau ``date.today()`` zurueckgibt.
    Ohne diesen Zweig entstuende ausgerechnet durch S1 eine neue Luecke: die
    zwoelf umgestellten Fixturen holen ihr Etappendatum jetzt aus
    ``stage_date()`` statt aus ``now.date()``. Faellt eine von ihnen spaeter auf
    rohe Ankunftszeiten zurueck, laege wieder dieselbe Kombination vor — der
    Scanner haette sie aber nicht mehr gesehen, weil er nur die alte
    Datums-Schreibweise kannte. Nachgemessen: mit dem Rueckfall auf rohe
    Wanduhr-Arithmetik in ``test_alert_urgency.py::_save_radar_trip`` blieb die
    Ratsche gruen, bis dieser Zweig dazukam.
    """
    if not isinstance(node, ast.Call):
        return False
    if isinstance(node.func, ast.Name) and node.func.id == "stage_date":
        return True
    if not isinstance(node.func, ast.Attribute):
        return False
    attr = node.func.attr
    if attr == "stage_date":
        return True
    if attr == "date":
        return _ist_wanduhr_traeger(node.func.value)
    if attr in {"today", "utcnow"}:
        v = node.func.value
        return isinstance(v, ast.Name) and v.id in _HEUTE_TRAEGER
    return False


def _ohne_astimezone(node: ast.AST) -> ast.AST:
    """``x.astimezone(tz)`` -> ``x`` (beliebig oft geschachtelt)."""
    while (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
           and node.func.attr == "astimezone"):
        node = node.func.value
    return node


def _ist_rohe_rechnung(node: ast.AST, zuweisungen=None, gesehen=frozenset()) -> bool:
    """Ein Ausdruck, der DIE WANDUHR um einen ``timedelta`` verschiebt.

    Beide Haelften zaehlen: es muss ein ``timedelta`` vorkommen UND der andere
    Operand muss die Wanduhr tragen. Ohne die zweite Bedingung meldete der
    Scanner auch ``tagesbeginn + timedelta(minutes=m)`` — also ausgerechnet
    die geklemmte Rechnung im Helfer, der das Anti-Muster beseitigt. Ein
    Waechter, der seine eigene Loesung anzeigt, ist unbrauchbar.
    """
    node = _ohne_astimezone(node)
    if not isinstance(node, ast.BinOp):
        return False
    if not any(_ist_timedelta(n) for n in ast.walk(node)):
        return False
    for seite in (node.left, node.right):
        seite = _ohne_astimezone(seite)
        if _ist_wanduhr_traeger(seite):
            return True
        if (isinstance(seite, ast.Name) and zuweisungen is not None
                and _ist_roher_name(seite.id, zuweisungen, gesehen)):
            return True
        if isinstance(seite, ast.BinOp) and _ist_rohe_rechnung(seite, zuweisungen, gesehen):
            return True
    return False


def _fliesst_in_eine_datenstruktur(strftime_knoten: ast.AST,
                                   funktion: ast.AST,
                                   zuweisungen: dict[str, list[ast.AST]]) -> bool:
    """Wird die formatierte Uhrzeit WEITERGEGEBEN — oder nur verglichen?

    Eine Ankunftszeit landet immer in einer Datenstruktur oder einem Aufruf:
    ``{"arrival_calculated": ...}``, ``Waypoint(arrival_calculated=...)``,
    ``_make_waypoint(id, lat, lon, ...)``. Ein ERWARTUNGSWERT dagegen wird
    einer Variablen zugewiesen und danach nur noch verglichen — z.B.
    ``expected_local_hhmm = onset_utc.astimezone(tz).strftime("%H:%M")`` in
    ``test_bundle_791_847_844_alerts.py``, das den gerenderten Onset in der
    Mail prueft und mit Wegpunkten nichts zu tun hat.

    Ohne diese Unterscheidung meldete die Namensaufloesung solche
    Erwartungswerte mit — und haette Aenderungen an voellig gesunden Tests
    erzwungen.

    Die erste Fassung zaehlte konkrete Knotenarten auf (dict-Werte und
    Aufruf-Argumente). Damit war die demonstrierte FORM behoben, nicht die
    KLASSE: eine Liste (``zeiten = [ankunft.strftime("%H:%M"), ...]``) und eine
    Tupel-Rueckgabe (``return heute, (ankunft.strftime("%H:%M"), ...)``)
    umgingen sie vollstaendig (Adversary-Finding F007). Statt der Aufzaehlung
    entscheidet jetzt die ELTERNKETTE: die Uhrzeit fliesst, wenn sie —
    unmittelbar oder durch beliebig geschachtelte Sammlungen hindurch — in
    einem Aufruf oder einem ``return`` landet. Eine Sammlung ist dabei selbst
    schon ein Ziel: eine Liste von Uhrzeiten IST eine Datenstruktur.

    Nicht als Fluss zaehlt die reine BINDUNG (``x = ...``, auch parallel als
    ``a, b = ...``): dort entscheidet der gebundene Name weiter, nicht der
    Ausdruck. Ebenso wenig zaehlen Vergleiche und f-Strings — das ist die
    Signatur des Erwartungswerts.
    """
    eltern: dict[int, ast.AST] = {}
    for k in ast.walk(funktion):
        for kind in ast.iter_child_nodes(k):
            eltern[id(kind)] = k

    def _fliesst(knoten: ast.AST) -> bool:
        aktuell = knoten
        while True:
            elter = eltern.get(id(aktuell))
            if elter is None:
                return False
            if isinstance(elter, (ast.Return, ast.Yield, ast.YieldFrom)):
                return True
            if isinstance(elter, ast.keyword):
                return True
            if isinstance(elter, ast.Call):
                # Der Empfaenger eines Methodenaufrufs (``x.strftime()``) ist
                # kein Fluss — sonst floesse jede Uhrzeit in sich selbst.
                return aktuell is not elter.func
            if isinstance(elter, ast.Dict):
                return aktuell in elter.values
            if isinstance(elter, (ast.List, ast.Set)):
                return True
            if isinstance(elter, ast.Tuple):
                grosselter = eltern.get(id(elter))
                if (isinstance(grosselter, ast.Assign)
                        and any(isinstance(z, ast.Tuple) for z in grosselter.targets)):
                    # Parallele Bindung ``a, b = x, y`` — keine Datenstruktur,
                    # sondern zwei Zuweisungen. Weiter ueber die Namen.
                    return False
                aktuell = elter
                continue
            if isinstance(elter, (ast.Starred, ast.comprehension, ast.GeneratorExp,
                                  ast.ListComp, ast.SetComp, ast.DictComp)):
                aktuell = elter
                continue
            return False

    namen_mit_uhrzeit: set[str] = set()
    for k in ast.walk(funktion):
        if not isinstance(k, ast.Assign):
            continue
        werte = (k.value.elts if isinstance(k.value, ast.Tuple) else [k.value])
        if strftime_knoten not in werte:
            continue
        for ziel in k.targets:
            teile = ziel.elts if isinstance(ziel, ast.Tuple) else [ziel]
            if isinstance(ziel, ast.Tuple) and isinstance(k.value, ast.Tuple):
                # Elementweise paaren: nur der Name, der WIRKLICH diese
                # Uhrzeit bekommt, gilt als Traeger.
                for t, w in zip(teile, k.value.elts):
                    if w is strftime_knoten and isinstance(t, ast.Name):
                        namen_mit_uhrzeit.add(t.id)
            else:
                for t in teile:
                    if isinstance(t, ast.Name):
                        namen_mit_uhrzeit.add(t.id)

    if _fliesst(strftime_knoten):
        return True
    for k in ast.walk(funktion):
        if (isinstance(k, ast.Name) and k.id in namen_mit_uhrzeit
                and isinstance(k.ctx, ast.Load) and _fliesst(k)):
            return True
    return False


def _zuweisungen(funktion: ast.AST) -> dict[str, list[ast.AST]]:
    """Alle Zuweisungen an einfache Namen INNERHALB dieser Funktion.

    Bewusst alle, nicht nur die erste: ob ein Name eine ungeklemmte Uhrzeit
    traegt, entscheidet sich erst, wenn man SAEMTLICHE Zuweisungen kennt (s.
    ``_ist_roher_name``)."""
    gefunden: dict[str, list[ast.AST]] = {}
    for k in ast.walk(funktion):
        ziele: list[ast.AST] = []
        if isinstance(k, ast.Assign):
            ziele = list(k.targets)
        elif isinstance(k, (ast.AnnAssign, ast.AugAssign)):
            ziele = [k.target]
        if not ziele or getattr(k, "value", None) is None:
            continue
        for z in ziele:
            if isinstance(z, ast.Name):
                gefunden.setdefault(z.id, []).append(k.value)
            else:
                # Tupel-Entpackung o.ae.: die Herkunft ist nicht mehr
                # eindeutig einem Namen zuzuordnen. Alle darin gebundenen
                # Namen werden als "nicht roh" behandelt (s. Docstring oben:
                # im Zweifel NICHT melden, um Falsch-Positive zu vermeiden).
                for t in ast.walk(z):
                    if isinstance(t, ast.Name):
                        gefunden.setdefault(t.id, []).append(ast.Constant(value=None))
    return gefunden


def _ist_roher_name(name: str, zuweisungen: dict[str, list[ast.AST]],
                    gesehen: frozenset[str] = frozenset()) -> bool:
    """Traegt ``name`` garantiert eine UNGEKLEMMTE Wanduhr-Uhrzeit?

    Der RED-Agent hatte die Namensaufloesung verworfen, weil sie das erprobte
    Gegenmuster mitfinge: dort steht am ``strftime`` ebenfalls nur ein Name.
    Der Zielkonflikt loest sich ueber die Frage „ist der Name AUSSCHLIESSLICH
    aus roher Wanduhr-Arithmetik gebunden?":

    * Gegenmuster (``test_952_onset_alert_fidelity.py::_active_window``):
      ``start`` wird zuerst aus ``now_local + timedelta(...)`` gebunden, danach
      in den Klemm-Zweigen erneut aus ``tag_start``/``tag_ende``. Eine dieser
      Zuweisungen ist KEINE rohe Rechnung => der Name gilt als geklemmt =>
      kein Fund. Genau die Klemmung, die den Namen sicher macht, ist also das
      Merkmal, an dem der Scanner ihn freispricht.
    * Bypass (``arrival = now + timedelta(hours=1)`` ... ``arrival.strftime``):
      einzige Zuweisung, rohe Rechnung, nie neu gebunden => Fund.

    Ketten ueber Zwischenschritte werden mitverfolgt
    (``arrival_local = arrival.astimezone(tz)``), mit Zyklusschutz.
    """
    if name in gesehen or name not in zuweisungen:
        return False
    gesehen = gesehen | {name}
    werte = zuweisungen[name]
    if not werte:
        return False
    for wert in werte:
        if _ist_rohe_rechnung(wert, zuweisungen, gesehen):
            continue
        kern = _ohne_astimezone(wert)
        if isinstance(kern, ast.Name) and _ist_roher_name(kern.id, zuweisungen, gesehen):
            continue
        return False
    return True


def _ist_ungeklemmte_uhrzeit(node: ast.AST,
                             zuweisungen: dict[str, list[ast.AST]] | None = None) -> bool:
    """``<rohe Wanduhr>.strftime("%H:%M")`` — direkt als Rechenausdruck ODER
    ueber eine Zwischenvariable, die nur aus roher Wanduhr-Arithmetik gebunden
    ist. Ein geklemmter Name (irgendwo anders zugewiesen) ist kein Fund."""
    if not (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)):
        return False
    if node.func.attr != "strftime":
        return False
    if not (node.args and isinstance(node.args[0], ast.Constant)
            and node.args[0].value == _HHMM):
        return False
    ziel = _ohne_astimezone(node.func.value)
    if isinstance(ziel, ast.BinOp):
        return _ist_rohe_rechnung(ziel, zuweisungen)
    if isinstance(ziel, ast.Name) and zuweisungen is not None:
        return _ist_roher_name(ziel.id, zuweisungen)
    return False


def scan_wallclock_arrival_fixtures(tests_root: Path) -> list[Finding]:
    """Alle Funktionen unter ``tests_root``, die ein Wanduhr-Etappendatum mit
    einer ungeklemmten Ankunftszeit kombinieren."""
    funde: list[Finding] = []
    for datei in sorted(tests_root.rglob("*.py")):
        try:
            baum = ast.parse(datei.read_text(encoding="utf-8"))
        except (SyntaxError, UnicodeDecodeError):
            continue
        for knoten in ast.walk(baum):
            if not isinstance(knoten, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            zuw = _zuweisungen(knoten)
            uhrzeiten = [n for n in ast.walk(knoten)
                         if _ist_ungeklemmte_uhrzeit(n, zuw)
                         and _fliesst_in_eine_datenstruktur(n, knoten, zuw)]
            if not uhrzeiten:
                continue
            if not any(_ist_wanduhr_datum(n) for n in ast.walk(knoten)):
                continue
            for treffer in uhrzeiten:
                funde.append(Finding(path=datei, function=knoten.name,
                                     line=treffer.lineno))
    return funde


def _relativ(f: Finding) -> str:
    try:
        return str(f.path.relative_to(REPO_ROOT))
    except ValueError:
        return str(f.path)


def _fall(name: str) -> str:
    """Fixture-Quelltext ``name`` aus der externen Vorlagendatei holen."""
    abschnitte = re.split(r"^# === (\S+) ===$\n",
                          _FAELLE_DATEI.read_text("utf-8"), flags=re.M)
    vorrat = dict(zip(abschnitte[1::2], abschnitte[2::2]))
    assert name in vorrat, f"Fall {name!r} fehlt in {_FAELLE_DATEI}: {sorted(vorrat)}"
    return vorrat[name]


def _attrappe(tmp_path: Path, quelltext: str) -> Path:
    """Echte Testdatei-Attrappe auf die Platte schreiben (kein Mock)."""
    f = tmp_path / "test_attrappe.py"
    f.write_text(quelltext, encoding="utf-8")
    return f


# ══════════════ Die Ratsche selbst (heute ROT, gruen nach S1) ══════════════

def test_keine_fixture_baut_ankunft_aus_der_rohen_wanduhr():
    """#1667 S1: keine Trip-Fixture kombiniert ein Wanduhr-Etappendatum mit
    einer ungeklemmten ``(now +/- timedelta).strftime("%H:%M")``-Ankunft."""
    funde = scan_wallclock_arrival_fixtures(TESTS_ROOT)
    offen = [f for f in funde if (_relativ(f), f.function) not in KNOWN_VIOLATIONS]
    zeilen = "\n".join(f"  - {_relativ(f)}:{f.line} in {f.function}()" for f in offen)
    dateien = sorted({_relativ(f) for f in offen})
    assert not offen, (
        f"{len(offen)} Fundstellen in {len(dateien)} Dateien bauen die "
        f"Ankunftszeit aus der rohen Wanduhr und werden dadurch zwischen "
        f"~22:00 und 00:00 UTC reproduzierbar rot:\n"
        f"{zeilen}\n\n"
        f"Abhilfe: das erprobte, auf 02:00-22:00 Ortszeit geklemmte Fenster "
        f"aus tests/tdd/test_952_onset_alert_fidelity.py::_active_window "
        f"verwenden (S1 zieht es nach tests/helpers/). KNOWN_VIOLATIONS zu "
        f"fuellen ist KEINE Abhilfe."
    )


def test_known_violations_enthaelt_keine_veralteten_eintraege():
    """Die Ausnahmeliste darf nur schrumpfen: was der Scanner nicht mehr
    findet, muss raus — sonst schleppt sie tote Ausnahmen mit."""
    aktuell = {(_relativ(f), f.function)
               for f in scan_wallclock_arrival_fixtures(TESTS_ROOT)}
    veraltet = sorted(KNOWN_VIOLATIONS - aktuell)
    assert not veraltet, (
        "Diese KNOWN_VIOLATIONS-Eintraege werden nicht mehr gefunden und "
        f"muessen entfernt werden: {veraltet}"
    )


# ══════════ Kann dieser Waechter ueberhaupt scheitern? (Selbstbeleg) ══════════

def test_scanner_meldet_das_antimuster(tmp_path):
    """Echte Lage: Wanduhr-Datum + ungeklemmte Ankunft => Fund."""
    _attrappe(tmp_path, _fall("roh-unclamped"))
    funde = scan_wallclock_arrival_fixtures(tmp_path)
    assert len(funde) == 2, f"erwartet 2 Funde, bekommen: {[f.ref for f in funde]}"
    assert all(f.function == "_save_radar_trip" for f in funde)


def test_scanner_schweigt_bei_geklemmtem_muster(tmp_path):
    """Kuenstlich saubere Eingabe: dasselbe Fixture-Ziel, aber auf
    02:00-22:00 Ortszeit geklemmt (das Muster, das S1 einfuehrt) => 0 Funde.

    Ohne diesen Beleg waere unklar, ob der Waechter ueberhaupt zwischen
    krank und gesund unterscheidet — und ob S1 ihn gruen bekommen KANN."""
    _attrappe(tmp_path, _fall("sauber-geklemmt"))
    funde = scan_wallclock_arrival_fixtures(tmp_path)
    assert funde == [], f"Falsch-Positiv am geklemmten Muster: {[f.ref for f in funde]}"


def test_scanner_schweigt_ohne_etappendatum(tmp_path):
    """Ruhezeitfenster aus der Wanduhr ohne Etappendatum ist kein Fund —
    dort gibt es kein Segment, das in die Vergangenheit rutschen koennte."""
    _attrappe(tmp_path, _fall("nur-uhrzeit-ohne-datum"))
    assert scan_wallclock_arrival_fixtures(tmp_path) == []


def test_scanner_erkennt_astimezone_zwischenschritt(tmp_path):
    """``(now +/- timedelta).astimezone(tz).strftime("%H:%M")`` — die Form aus
    tests/tdd/test_bundle_791_847_844_alerts.py:196 — wird ebenfalls gefunden."""
    _attrappe(tmp_path, _fall("astimezone-dazwischen"))
    funde = scan_wallclock_arrival_fixtures(tmp_path)
    assert len(funde) == 2, f"erwartet 2 Funde, bekommen: {[f.ref for f in funde]}"


def test_scanner_erkennt_den_bypass_ueber_eine_zwischenvariable(tmp_path):
    """Adversary-Finding F004: EINE Zwischenvariable vor dem ``strftime``
    genuegte, um den Waechter zu umgehen — bei identischem Anti-Muster meldete
    er 0 Funde. Das war keine schmale Ausnahme, sondern eine generische
    Umgehung; damit war der bleibende Schutz weitgehend wertlos."""
    _attrappe(tmp_path, _fall("bypass-zwischenvariable"))
    funde = scan_wallclock_arrival_fixtures(tmp_path)
    assert len(funde) == 2, f"erwartet 2 Funde, bekommen: {[f.ref for f in funde]}"
    assert all(f.function == "_save_radar_trip" for f in funde)


def test_scanner_erkennt_die_kette_ueber_astimezone_und_namen(tmp_path):
    """Zweistufige Kette (rohe Rechnung -> Name -> ``.astimezone`` -> Name).
    Die Spec hatte dieses Muster als strukturell unerfassbar beschrieben."""
    _attrappe(tmp_path, _fall("bypass-zwischenvariable-mit-astimezone"))
    funde = scan_wallclock_arrival_fixtures(tmp_path)
    assert len(funde) == 1, f"erwartet 1 Fund, bekommen: {[f.ref for f in funde]}"


def test_scanner_erkennt_uhrzeiten_in_einer_liste(tmp_path):
    """Adversary-Finding F007: die Uhrzeiten landen in einer LISTE statt direkt
    in einem dict-Wert. Die erste Fassung der Fluss-Erkennung zaehlte nur dict
    und Call auf — damit war die demonstrierte FORM behoben, nicht die KLASSE."""
    _attrappe(tmp_path, _fall("bypass-liste"))
    funde = scan_wallclock_arrival_fixtures(tmp_path)
    assert len(funde) == 2, f"erwartet 2 Funde, bekommen: {[f.ref for f in funde]}"
    assert all(f.function == "_save_radar_trip" for f in funde)


def test_scanner_erkennt_uhrzeiten_in_einer_tupel_rueckgabe(tmp_path):
    """Zweite Form aus F007: ``return heute, (…strftime(…), …)``. Weder dict
    noch Aufruf-Argument — der Fluss laeuft ueber geschachtelte Tupel in ein
    ``return``."""
    _attrappe(tmp_path, _fall("bypass-tupel-rueckgabe"))
    funde = scan_wallclock_arrival_fixtures(tmp_path)
    assert len(funde) == 2, f"erwartet 2 Funde, bekommen: {[f.ref for f in funde]}"
    assert all(f.function == "_fenster" for f in funde)


def test_scanner_schweigt_bei_einem_nur_verglichenen_erwartungswert(tmp_path):
    """Die Kehrseite der Fluss-Erkennung: eine wanduhr-abgeleitete Uhrzeit, die
    nur verglichen wird, ist kein Wegpunkt und kein Fund.

    Ohne diese Unterscheidung meldete die Namensaufloesung den Onset-Vergleich
    in ``test_bundle_791_847_844_alerts.py`` mit und erzwaenge Aenderungen an
    einem voellig gesunden Test."""
    _attrappe(tmp_path, _fall("erwartungswert-nur-verglichen"))
    funde = scan_wallclock_arrival_fixtures(tmp_path)
    assert funde == [], f"Falsch-Positiv am Erwartungswert: {[f.ref for f in funde]}"


def test_scanner_schweigt_bei_geklemmtem_namen(tmp_path):
    """Die Kehrseite der Namensaufloesung: ein Name, der in einem Klemm-Zweig
    NEU gebunden wird, ist kein Fund.

    Ohne diesen Beleg waere die Ratsche moeglicherweise unpassierbar — genau
    der Zielkonflikt, an dem der RED-Agent die Namensaufloesung verworfen
    hatte. Er loest sich, weil die Klemmung selbst das Merkmal ist."""
    _attrappe(tmp_path, _fall("sauber-geklemmt-ueber-namen"))
    funde = scan_wallclock_arrival_fixtures(tmp_path)
    assert funde == [], f"Falsch-Positiv am geklemmten Namen: {[f.ref for f in funde]}"


def test_scanner_erkennt_date_today_als_etappendatum(tmp_path):
    """Nicht nur ``now.date()``, auch ``date.today()`` ist ein Wanduhr-Datum."""
    _attrappe(tmp_path, _fall("datum-aus-date-today"))
    assert len(scan_wallclock_arrival_fixtures(tmp_path)) == 1


# ═══════════════════════════ Regel-Budget ═══════════════════════════

def test_regel_budget_pruefdatum_steht_als_text_in_der_datei():
    assert EXPIRY == date(2026, 11, 8), (
        "Pruefdatum des Regel-Budgets (+90 Tage), Vorbild EXPIRY in "
        ".claude/hooks/test_naming_gate.py"
    )
    text = Path(__file__).read_text(encoding="utf-8").splitlines()
    assert [n for n, z in enumerate(text, 1) if EXPIRY.isoformat() in z], (
        "Das ISO-Pruefdatum muss als Text in dieser Datei stehen, damit das "
        "Gate-Audit es per grep findet."
    )
