"""Wanduhr-robuste Ankunftszeiten fuer Trip-Fixturen (Issue #1667 Scheibe S1).

SPEC: docs/specs/modules/fix_1667_s1_fixture_wanduhr.md

Das Problem
-----------
Rund dreissig Alarm-/Radar-Tests bauten ihre Etappen-Wegpunkte als
``(now +/- timedelta(...)).strftime("%H:%M")`` bei Etappendatum
``now.date()``. Ab einer bestimmten Wanduhrzeit lief die Uhrzeit-Folge ueber
Mitternacht und wurde dadurch *steigend* (``00:00 -> 03:00``) statt
*fallend*. ``convert_trip_to_segments`` (``src/services/trip_segments.py``,
``wp_days``) erkennt eine Tagesgrenze aber nur bei **strikt fallender**
Uhrzeit; das Segment landete 23 Stunden in der Vergangenheit, der Guard
„alle Segmente vorbei" (``src/services/trip_alert.py``) griff, und
``check_radar_alerts()`` lieferte 0 statt 1.

Warum die naheliegende „02:00-22:00 Ortszeit"-Klemmung NICHT reicht
--------------------------------------------------------------------
Nachgemessen (nicht hergeleitet) unter ``freeze_time`` fuer Korsika
(UTC+2), Etappendatum ``date.today()``:

======================  =====================  =========================
Wanduhr (UTC)           Fenster laut Klemmung  Segment in UTC
======================  =====================  =========================
2026-08-10 21:59:59     00:59 -> 01:59         08-09 22:59 .. 23:59  VORBEI
2026-08-10 23:30:00     02:30 -> 05:30         08-10 00:30 .. 03:30  VORBEI
======================  =====================  =========================

Der Grund ist **nicht** die vom Spec-Entwurf vermutete undichte obere
Klemme, sondern ein Bezugstag-Bruch: das Fenster wird um ``now_local``
gebaut, das Segment aber auf ``date.today()`` gesetzt. Sobald Ortszeit und
Systemtag auseinanderlaufen — bei UTC+2 ab 22:00 UTC — zeigt ``now_local``
schon auf den Folgetag, das Etappendatum noch auf den Vortag, und jede
Ortszeit-Uhrzeit wird beim Segmentbau einen ganzen Tag zu frueh eingesetzt.
Die Klemmung verschiebt die Kippkante damit von 23:00 auf 22:00 UTC, statt
sie zu beseitigen.

Zweite gemessene Einsicht: ``wp_days == [0, 0]`` ist als Leitplanke ab
~22:00 UTC **unerfuellbar**. Auf dem Etappentag ist die spaeteste
darstellbare Ortszeit 23:59; bei UTC+2 sind das 21:59 UTC. Wer ``now_utc``
danach noch erreichen will, MUSS ueber den Rollover gehen — die richtige
Antwort ist also eine *fallende* Folge (``wp_days == [0, 1]``), nicht eine
steigende.

Wie dieser Helfer es loest
---------------------------
Er rechnet in **Minuten seit Ortszeit-Mitternacht des Etappentags** — also
in genau der Groesse, die ``convert_trip_to_segments`` beim Zusammensetzen
wieder auseinandernimmt — und klemmt dort:

* Der erste Wegpunkt liegt zwingend im Bereich ``[0, 1439]``: ``wp_days[0]``
  ist strukturell immer 0, ein Rollover *vor* dem ersten Wegpunkt ist im
  Datenmodell nicht darstellbar.
* Jeder Folge-Wegpunkt liegt ``1..1439`` Minuten nach seinem Vorgaenger.
  Die untere Grenze haelt die Folge streng monoton (sonst kollabiert das
  Segment am ``end_dt <= start_dt``-Guard), die obere Grenze garantiert,
  dass ein Tageswechsel sich als *fallende* Uhrzeit zeigt und deshalb von
  ``wp_days`` erkannt wird. Ein Abstand von genau 1440 Minuten wuerde
  dieselbe Uhrzeit erzeugen und den Rollover verschlucken.

Damit ist das Ergebnis zu jeder Wanduhrzeit entweder aktiv oder in der
Zukunft — beides laesst ``check_radar_alerts()`` ein Segment waehlen — und
nie „vorbei".

Bezugstag
---------
``stage_date(lat, lon)`` liefert dieselbe Formel, die ``trip_alert.py`` seit
Issue #1697 fuer ``convert_trip_to_segments`` benutzt (Ortstag der Tour ueber
``trip_local_today``, ADR-0044, nicht mehr ``date.today()``). Fixturen
nehmen das Etappendatum daraus statt aus
``datetime.now(timezone.utc).date()``: sonst zeigen Etappendatum und
Ankunftszeiten in der 22:00-00:00-UTC-Randzeit auf verschiedene Tage und
``get_stage_for_date()`` findet nichts.

Kein Mock: die Funktionen rechnen mit echten Zeitzonen ueber
``utils.timezone.tz_for_coords`` und geben dieselben ``HH:MM``-Strings
zurueck, die auch die Anwendung schreibt.

Pfadregel #1409: keine Pfadaufloesung noetig — dieser Helfer liest nichts von
der Platte.
"""
from __future__ import annotations

from datetime import date, datetime, time, timedelta, timezone

from utils.timezone import local_dt, tz_for_coords

__all__ = [
    "MINUTEN_PRO_TAG",
    "active_window_offsets",
    "fenster_minuten",
    "past_window_offsets",
    "stage_date",
]

MINUTEN_PRO_TAG = 24 * 60


def fenster_minuten(minuten_jetzt: int, *offsets_min: int) -> tuple[int, ...]:
    """Die tragende Rechnung von :func:`active_window_offsets`, OHNE Uhr.

    Eingabe ist die Minute seit Ortszeit-Mitternacht des Etappentags, in der
    *jetzt* liegt (darf negativ sein: der lokale Tag hat noch nicht begonnen;
    darf ueber 1439 liegen: er ist schon vorbei). Ausgabe sind die
    Wegpunkt-Minuten desselben Bezugs.

    Bewusst als reine Funktion herausgezogen, damit die drei Zusicherungen
    unten ueber ALLE Minuten eines Tages deterministisch pruefbar sind — ohne
    gestellte Uhr, ohne Zeitzonendaten, in jedem CI-Lauf. Vorher hingen sie an
    einmaligen ``freeze_time``-Handlaeufen, deren Ergebnis nur als Text in
    einem Artefakt lag; eine Verfaelschung der Monotonie-Untergrenze oder der
    oberen Klemme blieb im gesamten committeten Testbestand unbemerkt
    (Adversary-Findings F002/F003 zu #1667 S1).

    Zusicherungen — jede einzeln in
    ``tests/unit/test_arrival_window_fixtures.py`` bewacht:

    1. ``0 <= ergebnis[0] <= 1439`` — der erste Wegpunkt liegt auf dem
       Etappentag. ``wp_days[0]`` ist in ``convert_trip_to_segments``
       strukturell immer 0; ein Rollover VOR dem ersten Wegpunkt ist im
       Datenmodell nicht darstellbar.
    2. Streng monoton steigend. Zwei gleiche Zeiten kollabieren das Segment am
       ``end_dt <= start_dt``-Guard.
    3. Jeder Abstand hoechstens ``MINUTEN_PRO_TAG - 1``. Bei genau 1440 waere
       die Uhrzeit identisch und der Tageswechsel wuerde verschluckt — die
       Rollover-Erkennung in ``convert_trip_to_segments`` greift nur bei
       STRIKT fallender Uhrzeit.
    4. Ein NEGATIV gewuenschter Versatz liegt bei oder vor ``minuten_jetzt``
       (Issue #1940). Ist das an der gegebenen Ortsminute nicht darstellbar,
       wird :class:`ValueError` geworfen statt still ein Fenster geliefert, in
       dem der Wegpunkt in der Zukunft liegt. Die Zusicherung gilt ueber den
       ganzen Wertebereich, auch fuer negatives ``minuten_jetzt``: hat der
       lokale Etappentag noch gar nicht begonnen, ist dort ueberhaupt kein
       Vergangenheits-Wegpunkt darstellbar.
    """
    if len(offsets_min) < 2:
        raise ValueError(
            "Ein Segment braucht mindestens zwei Wegpunkte — "
            f"erhalten: {offsets_min!r}"
        )

    jetzt = int(minuten_jetzt)
    roh = [jetzt + int(v) for v in offsets_min]

    # Hat der lokale Etappentag noch gar nicht begonnen (westliche Zeitzonen
    # kurz nach UTC-Mitternacht), wird das GANZE Fenster nach vorne geschoben
    # statt nur sein Anfang — sonst bliebe ein Segment von einer Minute Laenge
    # uebrig. Nach hinten wird NICHT geschoben: das nimmt den spaeteren
    # Wegpunkten ihre Reichweite in die Zukunft und laesst das Segment
    # oestlich von UTC (nachgemessen: Neuseeland ab 22:00 UTC) doch wieder in
    # der Vergangenheit landen.
    verschiebung = max(0, -roh[0])
    roh = [r + verschiebung for r in roh]

    # Zusicherung 1.
    minuten: list[int] = [min(roh[0], MINUTEN_PRO_TAG - 1)]
    for r in roh[1:]:
        vorher = minuten[-1]
        # Zusicherungen 2 und 3.
        minuten.append(min(max(r, vorher + 1), vorher + MINUTEN_PRO_TAG - 1))

    # Zusicherung 4 (#1940). Geprueft wird das FERTIGE Fenster, nicht die
    # Zwischenrechnung: auch die Klemmungen oben koennen einen Wegpunkt nach
    # hinten schieben.
    verloren = [
        (int(v), m)
        for v, m in zip(offsets_min, minuten)
        if int(v) < 0 and m > jetzt
    ]
    if verloren:
        raise ValueError(
            f"An Ortsminute {jetzt} des Etappentags ist die gewuenschte "
            f"VERGANGENHEIT nicht darstellbar: die Versaetze "
            f"{[v for v, _ in verloren]} wurden vor *jetzt* verlangt, liegen "
            f"im geklemmten Fenster aber bei {[m for _, m in verloren]} und "
            f"damit dahinter (vollstaendiges Fenster: {tuple(minuten)}). Der "
            "lokale Tag ist noch nicht weit genug fortgeschritten, und ein "
            "Wegpunkt vor Ortszeit-Mitternacht ist im Datenmodell nicht "
            "darstellbar. Abhilfe: die Uhr des Tests auf eine Ortszeit in der "
            "Tagesmitte stellen (freeze_time) ODER Koordinaten waehlen, deren "
            "Etappentag zu jeder UTC-Uhrzeit weit genug fortgeschritten ist."
        )
    return tuple(minuten)


def stage_date(lat: float, lon: float) -> date:
    """Etappendatum, das zur Segmentauswahl in ``trip_alert.py`` passt.

    Issue #1697: ``check_radar_alerts()`` sucht die Etappe seither ueber
    ``trip_local_today(trip, now_utc)`` (Ortstag der Tour, ADR-0044) statt
    ueber ``date.today()`` (Serverdatum). ``lat``/``lon`` sind deshalb
    PFLICHT (kein Default) — jeder Aufrufer muss bewusst dieselben
    Koordinaten uebergeben, die er auch fuer
    ``active_window_offsets``/``past_window_offsets`` benutzt, sonst laufen
    Etappendatum und Ankunftszeiten in der 22:00-00:00-UTC-Randzeit
    auseinander (exakt die Fehlerklasse, die #1697 in Produktion behebt).

    Bewusst NICHT ``services.trip_day.trip_local_today`` — die Fixture kennt
    ihre Koordinaten bereits direkt (keine Henne-Ei-Falle, kein Trip zum
    Nachschlagen), sie bleibt bei der einfacheren Formel mit den bereits
    importierten Bausteinen.
    """
    return local_dt(datetime.now(timezone.utc), tz_for_coords(lat, lon)).date()


def active_window_offsets(lat: float, lon: float, *offsets_min: int) -> tuple[str, ...]:
    """Ankunftszeiten (``HH:MM`` Ortszeit) fuer zwei oder mehr Wegpunkte.

    ``offsets_min`` sind die gewuenschten Abstaende zu *jetzt* in Minuten,
    aufsteigend gemeint (z.B. ``60, 240`` fuer das alte ``now+1h`` /
    ``now+4h``). Zurueck kommt ein Tupel gleicher Laenge, das mit dem
    Etappendatum aus :func:`stage_date` ein Segment ergibt, das zu jeder
    Wanduhrzeit aktiv oder zukuenftig ist — nie „vorbei".

    Die gewuenschten Abstaende werden dabei nur so weit veraendert, wie die
    Tagesgrenzen es erzwingen; in der Tagesmitte kommen sie unveraendert
    heraus.

    🔴 **Das Vorzeichen eines Versatzes IST eine Zusicherung — seit Issue
    #1940 durchgesetzt statt nur erbeten.** Nahe der Ortszeit-Mitternacht ist
    "zwei Stunden vor jetzt" auf dem Etappentag nicht darstellbar. Frueher
    rutschte der Wegpunkt dann still nach vorne und lag NACH *jetzt*; ein
    Test, der ein bereits VERGANGENES erstes Segment brauchte, pruefte danach
    eine Konstellation, die er gar nicht hergestellt hatte (nachgemessen an
    ``test_issue_822_radar_nowcast_segment.py``: AC-3 taeglich 12:00-13:30 UTC
    rot, AC-2 taeglich 23:00-00:00 UTC — unabhaengig vom PR-Inhalt).

    Heute scheitert :func:`fenster_minuten` in diesem Fall laut mit
    :class:`ValueError`. Ein Aufrufer mit Vergangenheits-Bedarf hat zwei Wege:
    die Uhr selbst auf eine Ortszeit in der Tagesmitte stellen (``freeze_time``
    — so machen es die drei Stellen in ``test_issue_822_...``), oder
    Koordinaten waehlen, deren Etappentag zu jeder UTC-Uhrzeit weit genug
    fortgeschritten ist. Ein Ort allein genuegt nicht: auch Neuseeland
    (UTC+12) hat eine Ortszeit-Mitternacht, sie liegt nur bei 12:00 UTC.
    """
    tagesbeginn, minuten_jetzt = _tagesbezug(lat, lon)
    return tuple(
        (tagesbeginn + timedelta(minutes=m)).strftime("%H:%M")
        for m in fenster_minuten(minuten_jetzt, *offsets_min)
    )


def _tagesbezug(lat: float, lon: float) -> tuple[datetime, int]:
    """Ortszeit-Mitternacht des Etappentags und die Minute, in der *jetzt* liegt.

    Genau dieser Bezug wird in ``convert_trip_to_segments`` wieder aufgebaut
    (``datetime.combine(target_date, wp_time).replace(tzinfo=seg_tz)``).
    """
    tz = tz_for_coords(lat, lon)
    tagesbeginn = datetime.combine(stage_date(lat, lon), time(0, 0)).replace(tzinfo=tz)
    jetzt = datetime.now(timezone.utc)
    return tagesbeginn, int((jetzt - tagesbeginn).total_seconds() // 60)


def past_window_offsets(lat: float, lon: float, *offsets_min: int) -> tuple[str, ...]:
    """Ankunftszeiten fuer ein Segment, das garantiert schon VORBEI ist.

    Gegenstueck zu :func:`active_window_offsets` fuer die Regressionswaechter
    des „alle Segmente vorbei"-Guards. Alle Wegpunkte liegen auf dem
    Etappentag und mindestens eine Minute vor *jetzt*.

    🔴 **Das allein genuegt nicht, damit ein Trip als „vorbei" gilt.** Seit
    Issue #1584 endet das Ziel-Segment nicht mehr bei „Ankunft + 2 h", sondern
    am Ende des konfigurierten Tagesfensters (Default 4-19 Uhr Ortszeit,
    ``src/services/trip_segments.py``). Eine Fixture, die nur die Wegpunkte in
    die Vergangenheit legt, haelt das Ziel-Segment trotzdem bis 19:00 Ortszeit
    offen. Aufrufer muessen deshalb zusaetzlich ein Tagesfenster setzen, dessen
    Ende vor der Ankunft liegt — dann faellt das Ziel-Segment auf das minimale
    Fenster von einer Stunde nach Ankunft zurueck.

    🔴 **Die gewuenschte Spanne wird eingehalten oder gar nicht geliefert**
    (Issue #1940 AC-7). Reicht der bereits vergangene Teil des Etappentags
    nicht fuer die gewuenschten Abstaende (fruehe Ortszeit), wird
    :class:`ValueError` geworfen. Bis 2026-08-17 wurde hier still auf den
    verfuegbaren Platz **gestaucht** — der letzte Wegpunkt landete dann eine
    Minute vor *jetzt*, das Ziel-Segment blieb nach dem Randfall-Guard aber
    noch eine Stunde offen, und der Trip galt genau dann NICHT als „vorbei",
    wenn der Test das Gegenteil pruefen wollte. Nachgemessen an
    ``test_issue_818_radar_briefing_integration.py::test_ac5_...``: taeglich
    12:00-16:00 UTC rot (Neuseeland, Ortsminute 0-239).
    """
    if len(offsets_min) < 2:
        raise ValueError(
            "Ein Segment braucht mindestens zwei Wegpunkte — "
            f"erhalten: {offsets_min!r}"
        )

    tz = tz_for_coords(lat, lon)
    tag = stage_date(lat, lon)
    tagesbeginn = datetime.combine(tag, time(0, 0)).replace(tzinfo=tz)
    jetzt = datetime.now(timezone.utc)
    minuten_jetzt = int((jetzt - tagesbeginn).total_seconds() // 60)

    anzahl = len(offsets_min)
    obergrenze = min(MINUTEN_PRO_TAG - 1, minuten_jetzt - 1)

    roh = [minuten_jetzt + int(v) for v in offsets_min]
    for i in range(1, anzahl):
        roh[i] = max(roh[i], roh[i - 1] + 1)
    # Das ganze Fenster so weit nach hinten schieben, dass der letzte Wegpunkt
    # vor jetzt liegt (nach vorne wird nicht geschoben — das machte es spaeter).
    verschiebung = min(0, obergrenze - roh[-1])
    roh = [r + verschiebung for r in roh]

    # EINE Bedingung statt zweier: der frueher separat gepruefte Fall „gar kein
    # Platz mehr" (obergrenze < anzahl - 1) ist hierin enthalten — die Folge ist
    # nach der Monotonie-Korrektur mindestens ``anzahl - 1`` Minuten lang, ihr
    # Anfang liegt also erst recht vor Tagesbeginn. Zwei Bedingungen, von denen
    # eine die andere umfasst, laden nur dazu ein, die falsche zu pflegen.
    if roh[0] < 0:
        raise ValueError(
            f"Auf dem Etappentag {tag} ist an Ortsminute {minuten_jetzt} kein "
            f"vergangenes Fenster mit {anzahl} Wegpunkten ueber "
            f"{roh[-1] - roh[0]} Minuten darstellbar: vor *jetzt* liegen nur "
            f"{max(obergrenze + 1, 0)} Minuten dieses Tages, und ein Wegpunkt "
            "vor Ortszeit-Mitternacht ist im Datenmodell nicht darstellbar. "
            "Frueher wurde hier still auf den verfuegbaren Platz gestaucht — "
            "der letzte Wegpunkt landete dann eine Minute vor jetzt und das "
            "Ziel-Segment blieb noch eine Stunde offen, der Trip war also "
            "gerade NICHT vorbei (Issue #1940). Abhilfe: die Uhr des Tests "
            "auf eine spaete Ortszeit stellen (freeze_time) ODER kuerzere "
            "Versaetze waehlen."
        )

    return tuple((tagesbeginn + timedelta(minutes=m)).strftime("%H:%M") for m in roh)
