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

**Fuer die ZWEITE Fundregel (``scan_indirekte_wanduhr_fixtures``, #1709)
gilt zusaetzlich eine Luecke, bewusst NICHT geschlossen** (Adversary-Finding
F-ADV2): Wird das Wanduhr-Datum im AUFRUFER berechnet und als Parameter an
eine GESCHWISTER-Funktion uebergeben, die ihrerseits ``Stage(...)`` baut, so
sieht KEINE der beiden Funktionen fuer sich beide Merkmale zugleich —
Merkmal 2 (Wanduhr-Datum) steht im Aufrufer, Merkmal 1/3/4 (``Stage(...)``
mit >= 2 Wegpunkten etc.) in der Geschwister-Funktion, und Ruecksprung- bzw.
Parameter-Fluss ueber Funktionsgrenzen hinweg wird nicht verfolgt (teuer,
s. oben). Diese Struktur ist im Bestand bereits ETABLIERT:
``tests/tdd/test_issue_760_stage_number.py:31`` (Helferfunktion ``_stage(...,
d: date)``, die ``date`` als Parameter entgegennimmt und ``Stage(date=d,
...)`` baut) ist heute nur deshalb ungefaehrlich, weil dort ausschliesslich
mit EINEM Wegpunkt gebaut wird — eine Erweiterung dieser Helferfunktion auf
ZWEI Wegpunkte wuerde dort bereits genuegen, um die Ratsche zu umgehen, ohne
dass irgendein Merkmal der UND-Kette lokal fehlt. Aufrufketten ueber
Funktionsgrenzen zu verfolgen ist teuer, und #1709 erlaubt der Regel
ausdruecklich, eine Naeherung zu bleiben — SOLANGE die Grenze wie hier
benannt ist.

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

# Fixture-Quelltexte fuer die ZWEITE Fundregel (#1709, indirekte Variante) —
# derselbe Grund fuer die .py.txt-Endung wie oben.
_INDIREKT_FAELLE_DATEI = (
    REPO_ROOT / "tests/fixtures/ratchet_cases/indirekte_wanduhr_faelle.py.txt"
)

# Pruefdatum des Regel-Budgets: 2026-11-08
EXPIRY = date(2026, 11, 8)

# Pruefdatum des Regel-Budgets der ZWEITEN Fundregel (#1709): 2026-11-10, aus
# dem Ticket uebernommen.
EXPIRY_INDIREKT = date(2026, 11, 10)

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


def _fall_indirekt(name: str) -> str:
    """Fixture-Quelltext ``name`` aus der externen Vorlagendatei der ZWEITEN
    Fundregel (#1709) holen."""
    abschnitte = re.split(r"^# === (\S+) ===$\n",
                          _INDIREKT_FAELLE_DATEI.read_text("utf-8"), flags=re.M)
    vorrat = dict(zip(abschnitte[1::2], abschnitte[2::2]))
    assert name in vorrat, (
        f"Fall {name!r} fehlt in {_INDIREKT_FAELLE_DATEI}: {sorted(vorrat)}"
    )
    return vorrat[name]


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


# ═══════════ #1709: zweite Fundregel — indirekte Wanduhr-Abhaengigkeit ═══════════
#
# Anders als die erste Regel (Ankunftszeit direkt aus der Wanduhr gerechnet)
# meldet diese Regel das LOGISCHE GEGENTEIL: eine Fixture, die GAR KEINE
# Ankunftszeit setzt, wodurch der Pruefling (nicht die Fixture) eine
# Tageszeit-Grenze selbst berechnet (Naismith-Default 08:00 Start, s.
# ``src/services/trip_segments.py``). Fundbedingung, ALLE Merkmale zugleich:
#
#   1. die Funktion baut eine Etappe mit >= 2 Wegpunkten,
#   2. das Etappendatum stammt aus der Wanduhr (dieselbe Erkennung wie
#      _ist_wanduhr_datum oben),
#   3. KEIN Wegpunkt traegt arrival_calculated ODER arrival_override,
#   4. stage.start_time ist nicht gesetzt,
#   5. die Datei nutzt WEDER arrival_window_fixtures NOCH briefing_zeiten,
#   6. die Datei importiert einen zeitgrenzen-auswertenden Pfad (trip_alert,
#      compare_alert, trip_report_scheduler, compare_slot_scheduler,
#      alert_gate, deviation_alert, alert_daily_limit, official_alert).
#
# Die ersten vier Merkmale sind AM PRUEFLING abgelesen, nicht geraten
# (``src/services/trip_segments.py``, HEAD ``b6674c94``):
#   - >= 2 Wegpunkte:        :121-123 "if len(stage.waypoints) < 2: return []"
#   - kein arrival_calculated: :125-127 Self-Heal-Ausloeser
#     "all(wp.arrival_calculated is None ...)"
#   - kein arrival_override: :36-52 _known_time_for_index, Kette
#     arrival_override > stage.start_time (idx 0) > arrival_calculated --
#     arrival_override GEWINNT, auch wenn der Self-Heal-Ausloeser erfuellt
#     waere (AC-2 Fall c, der heikelste)
#   - kein stage.start_time: :132 "default_start = stage.start_time if
#     stage.start_time else time(8, 0)"
#
# Verworfen: eine Fundregel, die den Pruefling analysiert -- bei acht
# gemessenen Kippkanten-Familien in verschiedenen Modulen fuehrte das zu
# einer Regel, die entweder alles oder nichts meldet (Spec, Abschnitt
# "Gewaehlte Loesung").


def _importierte_konstruktor_aliase(baum: ast.AST, kanonischer_name: str) -> set[str]:
    """Alias-Namen, unter denen ``kanonischer_name`` per ``from ... import
    <kanonischer_name> as <alias>`` in diese Datei gelangt ist -- z.B.
    ``from app.trip import Stage as S`` -> ``{"S"}``. Gleiche Bauart wie
    ``_importierte_haertungs_namen`` unten, aber OHNE Modul-Einschraenkung:
    ein Konstruktor-Alias kann aus jedem Modul kommen. Ohne diese Aufloesung
    machte ein Alias denselben Anti-Muster-Fall unsichtbar -- 0 statt 1 Fund
    (Adversary-Finding F-ADV1 zu #1709)."""
    aliase: set[str] = set()
    for n in ast.walk(baum):
        if not isinstance(n, ast.ImportFrom):
            continue
        for alias in n.names:
            if alias.name == kanonischer_name and alias.asname:
                aliase.add(alias.asname)
    return aliase


def _stage_calls(funktion: ast.AST, stage_aliase: frozenset[str] = frozenset()) -> list[ast.Call]:
    """Alle ``Stage(...)``-Aufrufe innerhalb dieser Funktion -- auch unter
    einem importierten Alias (F-ADV1)."""
    return [n for n in ast.walk(funktion) if isinstance(n, ast.Call)
            and ((isinstance(n.func, ast.Name)
                  and (n.func.id == "Stage" or n.func.id in stage_aliase))
                 or (isinstance(n.func, ast.Attribute) and n.func.attr == "Stage"))]


def _ist_waypoint_call(node: ast.AST, waypoint_aliase: frozenset[str] = frozenset()) -> bool:
    """Auch unter einem importierten Alias (F-ADV1)."""
    return (isinstance(node, ast.Call)
            and ((isinstance(node.func, ast.Name)
                  and (node.func.id == "Waypoint" or node.func.id in waypoint_aliase))
                 or (isinstance(node.func, ast.Attribute) and node.func.attr == "Waypoint")))


def _hat_kwargs_entpackung(call: ast.Call) -> bool:
    """``Stage(**irgendwas)`` -- die Schluesselwoerter stammen aus einem
    Dict, dessen Inhalt der Scanner nicht einsehen kann (Adversary-Finding
    F002 zu #1709)."""
    return any(kw.arg is None for kw in call.keywords)


def _wegpunkte_wert(stage_call: ast.Call) -> ast.AST | None:
    """Der Wert des ``waypoints=``-Arguments, oder ``None`` wenn keins
    gesetzt ist."""
    for kw in stage_call.keywords:
        if kw.arg == "waypoints":
            return kw.value
    return None


def _wegpunkte_liste(wert: ast.AST, zuweisungen: dict[str, list[ast.AST]],
                     gesehen: frozenset[str] = frozenset(),
                     waypoint_aliase: frozenset[str] = frozenset()) -> list[ast.Call] | None:
    """Loest ``wert`` (den Wert von ``waypoints=``) zu einer VOLLSTAENDIG
    einsehbaren flachen Liste von ``Waypoint(...)``-Aufrufen auf.

    ``None`` heisst: die Menge ist NICHT vollstaendig einsehbar -- ein
    Aufruf einer Hilfsfunktion (F001, ``waypoints=_bau_wegpunkte()``), eine
    Comprehension (F003, ``[Waypoint(...) for x in liste]``, deren Laenge
    erst zur Laufzeit feststeht) oder ein Name, dessen Herkunft sich nicht
    aufloesen laesst. Uebertragen aus #1431 (``hook_utils.is_git_subcommand``):
    nicht "erkenne ich das Muster", sondern "bin ich sicher, dass es NICHT
    vorliegt". Eine Etappe gilt deshalb nur dann als sicher unter zwei
    Wegpunkten, wenn diese Funktion eine LEERE Liste zurueckgibt -- bei
    ``None`` bleibt die Etappe pruefbeduerftig statt immun."""
    if _ist_waypoint_call(wert, waypoint_aliase):
        return [wert]
    if isinstance(wert, ast.List):
        ergebnis: list[ast.Call] = []
        for element in wert.elts:
            teil = _wegpunkte_liste(element, zuweisungen, gesehen, waypoint_aliase)
            if teil is None:
                return None
            ergebnis.extend(teil)
        return ergebnis
    if isinstance(wert, ast.Name):
        if wert.id in gesehen:
            return None
        zuweisungswerte = zuweisungen.get(wert.id)
        if not zuweisungswerte:
            return None
        gesehen = gesehen | {wert.id}
        ergebnis = []
        for einzelwert in zuweisungswerte:
            teil = _wegpunkte_liste(einzelwert, zuweisungen, gesehen, waypoint_aliase)
            if teil is None:
                return None
            ergebnis.extend(teil)
        return ergebnis
    # Aufruf einer Hilfsfunktion, Comprehension, Attribute, Entpackung
    # (``*rest``) o.ae. -- die Menge ist nicht statisch zaehlbar.
    return None


def _keyword_ist_gesetzt(call: ast.Call, name: str) -> bool:
    """Traegt ``call`` das Keyword ``name`` mit einem Wert, der NICHT ``None``
    ist? Ein fehlendes Keyword oder ``name=None`` zaehlt als "nicht gesetzt"."""
    for kw in call.keywords:
        if kw.arg == name:
            return not (isinstance(kw.value, ast.Constant) and kw.value.value is None)
    return False


def _stage_ist_anfaellig(stage_call: ast.Call, zuweisungen: dict[str, list[ast.AST]],
                         waypoint_aliase: frozenset[str] = frozenset()) -> bool:
    """Merkmale 1, 3, 4 fuer EINEN ``Stage(...)``-Aufruf: >= 2 Wegpunkte,
    keiner mit arrival_calculated/arrival_override, kein gesetztes
    stage.start_time -- direkt an trip_segments.py:121-132 abgelesen (s.
    Tabelle oben).

    Merkmal 1 (>= 2 Wegpunkte) gilt als erfuellt, sobald die Menge NICHT
    beweisbar unter zwei liegt -- s. ``_wegpunkte_liste`` (F001-F003).

    Merkmal 4 (``stage.start_time``) wird ZUERST geprueft, VOR der
    Wegpunkt-Aufloesung: ein direkt gesetztes ``start_time=`` macht die
    Etappe unabhaengig davon immun, ob die Wegpunkt-Menge einsehbar ist --
    sonst uebersteuerte eine unaufloesbare ``waypoints=``-Angabe (F001-F003)
    faelschlich eine bereits vorhandene Haertung ueber ``start_time``."""
    if _keyword_ist_gesetzt(stage_call, "start_time"):
        return False
    if _hat_kwargs_entpackung(stage_call):
        return True
    wert = _wegpunkte_wert(stage_call)
    if wert is None:
        return False  # kein waypoints=... -> Default ist eine leere Liste
    wegpunkte = _wegpunkte_liste(wert, zuweisungen, waypoint_aliase=waypoint_aliase)
    if wegpunkte is None:
        return True  # Menge nicht einsehbar -> pruefbeduerftig, nicht immun
    if len(wegpunkte) < 2:
        return False
    if any(_keyword_ist_gesetzt(wp, "arrival_calculated")
           or _keyword_ist_gesetzt(wp, "arrival_override") for wp in wegpunkte):
        return False
    return True


# Zeitgrenzen-auswertende Pfade (Merkmal 6) bleiben DATEI-weit (Import): sie
# entscheiden, ob der Pruefling in dieser Datei ueberhaupt eine Tageszeit-
# Grenze auswertet, nicht ob eine EINZELNE Funktion gehaertet ist.
#
# Haertungs-Helfer (Merkmal 5) sind dagegen FUNKTIONS-weit (Adversary-Finding
# F004 zu #1709): die urspruengliche Fassung machte am Import fest -- eine
# Fixture galt schon dann als geschuetzt, wenn IRGENDEINE Funktion derselben
# Datei den Helfer importierte, nicht wenn sie ihn selbst BENUTZTE. Eine
# zweite, ungehaertete Funktion derselben Datei blieb dadurch unsichtbar.
# Die Ausnahme greift jetzt nur, wenn die betroffene Funktion selbst einen
# der importierten Namen (``stage_date``, ``briefing_zeiten_fuer_trip`` o.ae.)
# AUFRUFT -- geprueft an den bestehenden Gegenproben (e)/(f), die den Aufruf
# bereits jeweils in der eigenen Funktion haben.
_HAERTUNGS_HELFER_INDIREKT = ("arrival_window_fixtures", "briefing_zeiten")
_ALARMPFADE_INDIREKT = (
    "trip_alert", "compare_alert", "trip_report_scheduler", "compare_slot_scheduler",
    "alert_gate", "deviation_alert", "alert_daily_limit", "official_alert",
)


def _importierte_module(baum: ast.AST) -> set[str]:
    module: set[str] = set()
    for n in ast.walk(baum):
        if isinstance(n, ast.ImportFrom) and n.module:
            module.add(n.module)
        elif isinstance(n, ast.Import):
            for alias in n.names:
                module.add(alias.name)
    return module


def _importiert_eines_von(module: set[str], namen: tuple[str, ...]) -> bool:
    return any(name in m for name in namen for m in module)


def _importierte_haertungs_namen(baum: ast.AST) -> set[str]:
    """Namen, die per ``from <haertungs-modul> import <name>`` in diese Datei
    gelangt sind -- z.B. ``stage_date`` aus
    ``tests.helpers.arrival_window_fixtures``. Grundlage fuer die
    FUNKTIONS-weite Pruefung (F004), nicht mehr fuer eine dateiweite."""
    namen: set[str] = set()
    for n in ast.walk(baum):
        if not isinstance(n, ast.ImportFrom) or not n.module:
            continue
        if not any(helfer in n.module for helfer in _HAERTUNGS_HELFER_INDIREKT):
            continue
        for alias in n.names:
            namen.add(alias.asname or alias.name)
    return namen


def _funktion_nutzt_haertungs_helfer(funktion: ast.AST, haertungs_namen: set[str]) -> bool:
    """Ruft die FUNKTION SELBST einen der importierten Haertungs-Bausteine
    auf? (Adversary-Finding F004: vorher entschied allein der Import
    irgendwo in der Datei, nicht die tatsaechliche Nutzung durch diese
    Funktion.)"""
    if not haertungs_namen:
        return False
    return any(isinstance(n, ast.Call) and isinstance(n.func, ast.Name)
               and n.func.id in haertungs_namen for n in ast.walk(funktion))


def scan_indirekte_wanduhr_fixtures(tests_root: Path) -> list[Finding]:
    """Alle Funktionen unter ``tests_root``, die eine Etappe mit
    Wanduhr-Datum und nicht beweisbar unter 2 Wegpunkten bauen, OHNE jede
    Ankunftszeit, OHNE dass die Funktion SELBST einen Haertungs-Helfer
    aufruft, UND mit Alarmpfad-Import in der Datei (zweite Fundregel, #1709
    -- s. Kommentarblock oben)."""
    funde: list[Finding] = []
    for datei in sorted(tests_root.rglob("*.py")):
        try:
            baum = ast.parse(datei.read_text(encoding="utf-8"))
        except (SyntaxError, UnicodeDecodeError):
            continue

        module = _importierte_module(baum)
        if not _importiert_eines_von(module, _ALARMPFADE_INDIREKT):
            continue
        haertungs_namen = _importierte_haertungs_namen(baum)
        stage_aliase = frozenset(_importierte_konstruktor_aliase(baum, "Stage"))
        waypoint_aliase = frozenset(_importierte_konstruktor_aliase(baum, "Waypoint"))

        for knoten in ast.walk(baum):
            if not isinstance(knoten, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            if _funktion_nutzt_haertungs_helfer(knoten, haertungs_namen):
                continue
            zuw = _zuweisungen(knoten)
            anfaellige_stages = [s for s in _stage_calls(knoten, stage_aliase)
                                 if _stage_ist_anfaellig(s, zuw, waypoint_aliase)]
            if not anfaellige_stages:
                continue
            if not any(_ist_wanduhr_datum(n) for n in ast.walk(knoten)):
                continue
            funde.append(Finding(path=datei, function=knoten.name,
                                 line=anfaellige_stages[0].lineno))
    return funde


# 🔴 Wie bei KNOWN_VIOLATIONS oben: nur SCHRUMPFEN, nie fuellen um gruen zu
# werden. Die 11 Eintraege unten sind der GEMESSENE, nicht geratene Bestand
# (Scanner-Lauf ueber tests/ bei Implementierung dieser Scheibe): jede Datei
# baut eine Etappe mit Wanduhr-Datum, >= 2 Wegpunkten, ohne jede Ankunftszeit
# und importiert einen Alarmpfad -- strukturell exakt das Anti-Muster.
#
# Sanierung ist laut Spec (Abschnitt "Nicht in dieser Scheibe") ausdruecklich
# NICHT Gegenstand dieser Scheibe: "Keine Sanierung von Bestandsdateien
# (gemessen: nicht noetig, s. Source)". Die Source-Messung dort (Tabelle
# "Bestandsmenge ist gemessen, nicht geschaetzt") belegt per
# matrix_differenz()-Lauf ueber vergleichbare Kandidatenmengen, dass diese
# Bauart bei den gemessenen Uhrzeiten NICHT tatsaechlich kippt -- anders als
# der eine Fall aus #1871 (dort NICHT in dieser Liste, weiterhin offen,
# ausdruecklich ausserhalb dieser Scheibe). Diese Regel meldet strukturelles
# Risiko, nicht gemessene Flakiness (s. Kommentarblock oben, "Verworfen").
#
# Anders als bei der ERSTEN Regel oben ist die Rechtfertigung hier NICHT "die
# Fixture braucht das Anti-Muster", sondern "Sanierung ist fuer diese Scheibe
# explizit nicht beauftragt" -- eine bewusst andere Kategorie, review-pflichtig
# wie dort.
KNOWN_VIOLATIONS_INDIREKT: frozenset[tuple[str, str]] = frozenset({
    # #1709 Haertung (2026-08-15): 9 von 10 Bestandsstellen sind gehaertet
    # (arrival_calculated gesetzt, s. Commits dieser Scheibe). Der letzte
    # Eintrag bleibt, solange der Datei-Claim-Gate die Haertung von
    # tests/tdd/test_alert_undelivered_hint.py blockiert (fremde Session
    # auf Worktree fix-1676-s2-sms-versand / Branch fix-1750-sperrzeit-wortwahl).
    ("tests/tdd/test_alert_undelivered_hint.py", "_trip"),
})


def test_scanner_meldet_die_indirekte_variante(tmp_path):
    """AC-1: Etappe mit Wanduhr-Datum OHNE jede Ankunftszeit, ohne
    Haertungs-Helfer, mit Alarmpfad-Import -> wird gemeldet (Datei,
    Funktionsname, Zeile)."""
    _attrappe(tmp_path, _fall_indirekt("indirekt-antimuster"))
    funde = scan_indirekte_wanduhr_fixtures(tmp_path)
    assert len(funde) == 1, f"erwartet 1 Fund, bekommen: {[f.ref for f in funde]}"
    assert funde[0].function == "_trip_ohne_ankunftszeiten"


def test_scanner_schweigt_bei_nur_einem_wegpunkt(tmp_path):
    """AC-2 (a): eine Ein-Wegpunkt-Etappe erzeugt gar kein Segment
    (trip_segments.py:121-123) — kein Fund."""
    _attrappe(tmp_path, _fall_indirekt("nur-ein-wegpunkt"))
    funde = scan_indirekte_wanduhr_fixtures(tmp_path)
    assert not funde, f"Falsch-Positiv bei nur einem Wegpunkt: {[f.ref for f in funde]}"


def test_scanner_schweigt_bei_gesetztem_arrival_calculated(tmp_path):
    """AC-2 (b): arrival_calculated ist gesetzt -> der Self-Heal-Ausloeser
    greift nicht — kein Fund."""
    _attrappe(tmp_path, _fall_indirekt("arrival-calculated-gesetzt"))
    funde = scan_indirekte_wanduhr_fixtures(tmp_path)
    assert not funde, f"Falsch-Positiv bei arrival_calculated: {[f.ref for f in funde]}"


def test_scanner_schweigt_bei_gesetztem_arrival_override(tmp_path):
    """AC-2 (c), der heikelste Fall: arrival_calculated ist bei ALLEN
    Wegpunkten None (der Self-Heal-Ausloeser waere erfuellt), aber
    arrival_override gewinnt in _known_time_for_index (trip_segments.py:
    36-52) noch vor dem Default -> kein Fund. Eine Regel, die nur auf
    arrival_calculated schaut, meldet diese Fixture faelschlich."""
    _attrappe(tmp_path, _fall_indirekt("arrival-override-gesetzt"))
    funde = scan_indirekte_wanduhr_fixtures(tmp_path)
    assert not funde, f"Falsch-Positiv bei arrival_override: {[f.ref for f in funde]}"


def test_scanner_schweigt_bei_gesetztem_stage_start_time(tmp_path):
    """AC-2 (d): stage.start_time ist gesetzt -> ersetzt den
    Naismith-Default 08:00 (trip_segments.py:132) — kein Fund."""
    _attrappe(tmp_path, _fall_indirekt("stage-start-time-gesetzt"))
    funde = scan_indirekte_wanduhr_fixtures(tmp_path)
    assert not funde, f"Falsch-Positiv bei stage.start_time: {[f.ref for f in funde]}"


def test_scanner_schweigt_bei_arrival_window_fixtures_import(tmp_path):
    """AC-2 (e): die Datei nutzt den Haertungs-Helfer
    arrival_window_fixtures -> kein Fund."""
    _attrappe(tmp_path, _fall_indirekt("nutzt-arrival-window-fixtures"))
    funde = scan_indirekte_wanduhr_fixtures(tmp_path)
    assert not funde, (
        f"Falsch-Positiv trotz arrival_window_fixtures-Import: "
        f"{[f.ref for f in funde]}"
    )


def test_scanner_schweigt_bei_briefing_zeiten_import(tmp_path):
    """AC-2 (f): die Datei nutzt den Haertungs-Helfer briefing_zeiten ->
    kein Fund."""
    _attrappe(tmp_path, _fall_indirekt("nutzt-briefing-zeiten"))
    funde = scan_indirekte_wanduhr_fixtures(tmp_path)
    assert not funde, (
        f"Falsch-Positiv trotz briefing_zeiten-Import: {[f.ref for f in funde]}"
    )


def test_scanner_schweigt_ohne_alarmpfad_import(tmp_path):
    """AC-2 (g): die Datei importiert keinen zeitgrenzen-auswertenden Pfad
    -> kein Fund, obwohl die Fixture-Bauart sonst identisch mit dem
    Anti-Muster ist."""
    _attrappe(tmp_path, _fall_indirekt("kein-alarmpfad-import"))
    funde = scan_indirekte_wanduhr_fixtures(tmp_path)
    assert not funde, (
        f"Falsch-Positiv ohne Alarmpfad-Import: {[f.ref for f in funde]}"
    )


def test_scanner_erkennt_wegpunkte_aus_einer_hilfsfunktion(tmp_path):
    """Adversary-Finding F001: ``waypoints=_bau_wegpunkte()`` -- eine
    Hilfsfunktion baut die Wegpunkte AUSSERHALB des ``Stage(...)``-Aufrufs.
    Die alte Zaehlung sah im Syntaxbaum des Aufrufs 0 ``Waypoint(...)``-
    Knoten und stufte die Etappe faelschlich als immun ein."""
    _attrappe(tmp_path, _fall_indirekt("wegpunkte-aus-hilfsfunktion"))
    funde = scan_indirekte_wanduhr_fixtures(tmp_path)
    assert len(funde) == 1, f"erwartet 1 Fund, bekommen: {[f.ref for f in funde]}"
    assert funde[0].function == "_trip_ueber_hilfsfunktion"


def test_scanner_erkennt_stage_aus_kwargs_entpackung(tmp_path):
    """Adversary-Finding F002: ``Stage(**stage_kwargs)`` -- die Keywords
    stammen aus einem Dict, das der Scanner nicht einsehen kann. Die alte
    Zaehlung fand am Aufruf gar kein ``waypoints=``-Keyword und stufte die
    Etappe faelschlich als immun ein."""
    _attrappe(tmp_path, _fall_indirekt("stage-kwargs-entpackung"))
    funde = scan_indirekte_wanduhr_fixtures(tmp_path)
    assert len(funde) == 1, f"erwartet 1 Fund, bekommen: {[f.ref for f in funde]}"
    assert funde[0].function == "_trip_ueber_kwargs"


def test_scanner_erkennt_wegpunkte_aus_einer_comprehension(tmp_path):
    """Adversary-Finding F003: ``waypoints=[Waypoint(...) for x in liste]``
    -- die alte Zaehlung sah GENAU EINEN Syntaxknoten, obwohl zur Laufzeit
    ``len(liste)`` (hier 3) Wegpunkte entstehen, und stufte die Etappe unter
    der Schwelle von 2 faelschlich als immun ein."""
    _attrappe(tmp_path, _fall_indirekt("wegpunkte-aus-comprehension"))
    funde = scan_indirekte_wanduhr_fixtures(tmp_path)
    assert len(funde) == 1, f"erwartet 1 Fund, bekommen: {[f.ref for f in funde]}"
    assert funde[0].function == "_trip_ueber_comprehension"


def test_scanner_erkennt_ungehaertete_funktion_trotz_dateiweitem_import(tmp_path):
    """Adversary-Finding F004: die Datei importiert den Haertungs-Helfer,
    aber nur EINE von zwei Funktionen nutzt ihn. Die alte, dateiweite
    Pruefung sprach beide frei; jetzt wird nur die tatsaechlich gehaertete
    Funktion ausgenommen."""
    _attrappe(tmp_path, _fall_indirekt("haertungs-helfer-nur-in-anderer-funktion"))
    funde = scan_indirekte_wanduhr_fixtures(tmp_path)
    assert len(funde) == 1, f"erwartet 1 Fund, bekommen: {[f.ref for f in funde]}"
    assert funde[0].function == "_ungehaertete_funktion"


def test_scanner_erkennt_stage_und_waypoint_hinter_import_alias(tmp_path):
    """Adversary-Finding F-ADV1 (HIGH): ``from app.trip import Stage as S,
    Waypoint as WP`` machte denselben Anti-Muster-Fall unsichtbar, wenn der
    Scanner Konstruktoren nur am literalen Namen erkennt -- 0 statt 1 Fund
    bei identischem Muster."""
    _attrappe(tmp_path, _fall_indirekt("indirekt-antimuster-mit-alias"))
    funde = scan_indirekte_wanduhr_fixtures(tmp_path)
    assert len(funde) == 1, f"erwartet 1 Fund, bekommen: {[f.ref for f in funde]}"
    assert funde[0].function == "_trip_ohne_ankunftszeiten_alias"


def test_scanner_schweigt_bei_literalem_etappendatum(tmp_path):
    """AC-2 (h), Adversary-Finding F-ADV3 (MEDIUM): eigene Gegenprobe fuer
    Merkmal 2 (Wanduhr-Etappendatum) -- ein LITERALES Datum statt
    Wanduhr-Arithmetik, sonst identisch zum Anti-Muster -> kein Fund. Ohne
    diesen Test faengt keine Attrappe die Mutation "Merkmal 2 aus der
    UND-Kette entfernen" gezielt ab."""
    _attrappe(tmp_path, _fall_indirekt("literales-datum-statt-wanduhr"))
    funde = scan_indirekte_wanduhr_fixtures(tmp_path)
    assert not funde, f"Falsch-Positiv bei literalem Etappendatum: {[f.ref for f in funde]}"


def test_scanner_schweigt_bei_start_time_vor_unaufloesbaren_wegpunkten(tmp_path):
    """Regressionsschutz (Adversary-Finding F-ADV4, MEDIUM): stage.start_time
    gesetzt UND waypoints= nicht statisch einsehbar (Modulkonstante) -- die
    Immunitaet ueber start_time muss VOR der Wegpunkt-Aufloesung greifen,
    sonst erzeugt die unaufloesbare Menge faelschlich einen Fund, obwohl
    start_time die Etappe bereits immun macht (trip_segments.py:132).
    Bewacht die Reihenfolge in ``_stage_ist_anfaellig()`` direkt, statt nur
    ueber zwei thematisch unbeteiligte Bestandsdateien."""
    _attrappe(tmp_path, _fall_indirekt("start-time-mit-unaufloesbaren-wegpunkten"))
    funde = scan_indirekte_wanduhr_fixtures(tmp_path)
    assert not funde, (
        f"Falsch-Positiv trotz start_time vor unaufloesbaren Wegpunkten: "
        f"{[f.ref for f in funde]}"
    )


def test_echter_testbaum_ohne_fehlalarm_der_zweiten_regel():
    """AC-5: der echte Baum tests/ erzeugt keinen Fehlalarm — Fundmenge leer
    oder vollstaendig durch KNOWN_VIOLATIONS_INDIREKT gedeckt, UND mindestens
    20 geprueft Kandidatenfunktionen.

    Die Kandidatenzaehlung ist ABSICHTLICH UNABHAENGIG von
    scan_indirekte_wanduhr_fixtures() implementiert (Vorbild
    test_ac3_echter_testbaum_ohne_fehlalarm in
    test_repo_path_hardcoding_ratchet.py) — sonst wuerde ein Bug in der
    Kandidatensuche des Scanners auch die Sicherung selbst reissen und ein
    leerer Scan waere von einem kaputten Scanner nicht zu unterscheiden."""
    kandidaten: list[str] = []
    for datei in sorted(TESTS_ROOT.rglob("*.py")):
        try:
            baum = ast.parse(datei.read_text(encoding="utf-8", errors="replace"))
        except (SyntaxError, UnicodeDecodeError):
            continue
        for knoten in ast.walk(baum):
            if not isinstance(knoten, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            waypoint_aufrufe = sum(
                1 for c in ast.walk(knoten)
                if isinstance(c, ast.Call)
                and ((isinstance(c.func, ast.Name) and c.func.id == "Waypoint")
                     or (isinstance(c.func, ast.Attribute) and c.func.attr == "Waypoint"))
            )
            if waypoint_aufrufe >= 2:
                kandidaten.append(f"{datei}:{knoten.name}")
    assert len(kandidaten) >= 20, (
        f"nur {len(kandidaten)} Kandidatenfunktionen (>=2 Waypoint(...)-Aufrufe) "
        "im Testbaum gefunden — die Untergrenze verhindert, dass ein leerer "
        "Scan durch eine kaputte Kandidatensuche vorgetaeuscht wird"
    )

    funde = scan_indirekte_wanduhr_fixtures(TESTS_ROOT)
    offen = [f for f in funde if (_relativ(f), f.function) not in KNOWN_VIOLATIONS_INDIREKT]
    zeilen = "\n".join(f"  - {_relativ(f)}:{f.line} in {f.function}()" for f in offen)
    assert not offen, (
        f"{len(offen)} Fundstellen bauen eine Etappe mit Wanduhr-Datum ohne "
        f"jede Ankunftszeit, ohne Haertungs-Helfer und mit Alarmpfad-Import:\n"
        f"{zeilen}"
    )


def test_known_violations_der_neuen_regel_ohne_veraltete_eintraege():
    """AC-6: KNOWN_VIOLATIONS_INDIREKT darf nur SCHRUMPFEN — was der Scanner
    nicht mehr findet, muss raus. Muster der bestehenden Regel oben
    (test_known_violations_enthaelt_keine_veralteten_eintraege)."""
    aktuell = {(_relativ(f), f.function)
               for f in scan_indirekte_wanduhr_fixtures(TESTS_ROOT)}
    veraltet = sorted(KNOWN_VIOLATIONS_INDIREKT - aktuell)
    assert not veraltet, (
        "Diese KNOWN_VIOLATIONS_INDIREKT-Eintraege werden nicht mehr gefunden "
        f"und muessen entfernt werden: {veraltet}"
    )


def test_regel_budget_pruefdatum_der_neuen_regel_steht_als_text():
    """AC-8: das Pruefdatum der zweiten Fundregel ist maschinell auffindbar —
    als Konstante UND als Text in der Datei (Muster Z. 663-672 oben)."""
    assert EXPIRY_INDIREKT == date(2026, 11, 10), (
        "Pruefdatum des Regel-Budgets der zweiten Fundregel (aus dem Ticket "
        "#1709 uebernommen)"
    )
    text = Path(__file__).read_text(encoding="utf-8").splitlines()
    assert [n for n, z in enumerate(text, 1) if EXPIRY_INDIREKT.isoformat() in z], (
        "Das ISO-Pruefdatum der zweiten Fundregel muss als Text in dieser "
        "Datei stehen, damit das Gate-Audit es per grep findet."
    )


def test_neue_waechter_sind_nicht_von_der_ci_ausgenommen():
    """AC-9: ein Waechter, der nicht auf der CI-Ampel laeuft, ist keiner.
    Weder diese Datei noch test_wanduhr_matrix.py duerfen in der
    tests/tdd/-Ausschlussliste stehen.

    Dieser Test ist heute schon erfuellt — er ist eine Regressionssperre,
    kein Arbeitsnachweis fuer diese Scheibe: als einziger AC-Test bleibt er
    von Anfang an gruen."""
    text = (REPO_ROOT / ".github/ci_tdd_excludes.txt").read_text(encoding="utf-8")
    for name in ("test_fixture_wallclock_ratchet", "test_wanduhr_matrix"):
        assert name not in text, (
            f"{name} steht in .github/ci_tdd_excludes.txt und laeuft damit "
            "nicht auf der CI-Ampel — ein Waechter, der nicht laeuft, ist "
            "kein Waechter."
        )
