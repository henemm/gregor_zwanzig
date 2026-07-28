"""Vollstaendigkeits-Waechter fuer die Namens-Verknuepfung der Vergleichs-Mail
(#1401 Scheibe A2a, AC-3).

Die beiden Mail-Tabellen des Ortsvergleichs -- Uebersichtstabelle
(``CV2_METRICS``) und Stundentabelle (``HOUR_METRICS``) in
``src/output/renderers/email/compare_html.py`` -- sollen ihre Beschriftung
kuenftig aus dem zentralen Wetter-Namensregister (``src/app/metric_catalog.py``)
ableiten statt sie zu tippen. Das setzt voraus, dass JEDE Zeile ihre zentrale
Groesse (``metric_id``) und die gezeigte Auswertung (``aggregation``) benennt.

Genau diese Verknuepfung wurde bei #1296 und #1324 zweimal vergessen, ohne dass
etwas anschlug: die neuen Zeilen kamen ohne ``metric_id`` in die Liste. Dieser
Waechter macht das sichtbar -- er nennt die betroffene Zeile beim Namen (ihren
``key``), statt nur "assert False" zu sagen.

Geprueft wird gegen die ECHTEN Renderer-Listen und das ECHTE Register
(``get_metric``); keine Mocks, kein ``patch()``, kein Netz, kein Datei-I/O --
Kern-Schicht.

Die beiden Tabellen werden UNTERSCHIEDLICH streng geprueft (Tech-Lead-
Entscheidung 2026-07-28):

* ``CV2_METRICS`` (Uebersichtstabelle) zeigt TAGESWERTE. Jede Zeile braucht
  daher ``metric_id`` UND ``aggregation`` -- welche Auswertung der Groesse dort
  steht (Hoechst-/Tiefstwert/Mittel/Summe), ist eine echte Aussage und in A2b
  der Unterscheider bei gleichnamigen Zeilen ("Temp max"/"Temp min").
* ``HOUR_METRICS`` (Stundentabelle) zeigt MOMENTANWERTE. Dort waere eine
  ``aggregation`` eine erfundene Angabe (die 12-Uhr-Zelle ist kein Maximum),
  und ihr einziger Zweck -- der Kollisions-Zusatz in A2b -- kann strukturell
  nie greifen, weil alle 9 Zeilen paarweise verschiedene ``metric_id`` tragen.
  Deshalb wird hier nur ``metric_id`` verlangt und ``aggregation`` ausdruecklich
  VERBOTEN: ein Feld, das nichts traegt und nicht stimmt, ist schlechter als
  kein Feld.

Zur Pruefung der Auswertung: massgeblich ist ``MetricDefinition.summary_fields``
des zentralen Registers, also die Auswertungen, fuer die die Groesse ueberhaupt
einen Tageswert kennt. Das ist derselbe Massstab, mit dem der bereits
produktive Compare-Katalog (``output/renderers/compare_metric_catalog.py``)
seine ``aggregation``-Werte belegt (dort im Modul-Docstring als "gemessen am
zentralen Katalog (MetricDefinition.summary_fields), nicht geraten"
beschrieben) und den ``tests/unit/test_compare_catalog_derives_from_central_
catalog.py::_aggregation_violations`` dort anlegt. Der Massstab traegt hier
ohne Ausnahmeliste: alle 26 im Vergleich gezeigten Groessen fuehren
``summary_fields``.

SPEC: docs/specs/modules/fix_1401_a2_mailtabellen.md (AC-3)
"""
from __future__ import annotations

import copy

import pytest

from app.metric_catalog import get_metric
from output.renderers.email.compare_html import CV2_METRICS, HOUR_METRICS


def _linkage_findings(
    rows: list[dict], source: str, *, expect_aggregation: bool = True,
) -> list[str]:
    """Lesbare Befunde zu fehlenden/unaufloesbaren Verknuepfungen (leer = in
    Ordnung).

    Als aufrufbare Funktion herausgezogen, damit der Waechter (echte Daten) und
    der Wirkungsnachweis (kuenstlich beschaedigte Kopie) DIESELBE Logik
    ausfuehren -- eine im Test nachgebaute zweite Pruefung wuerde nichts
    beweisen.

    ``expect_aggregation=True`` (Tageswert-Tabelle): ``aggregation`` ist
    Pflicht und muss eine zentrale Auswertung der Groesse sein.
    ``expect_aggregation=False`` (Stundentabelle, Momentanwerte):
    ``aggregation`` ist verboten (s. Modul-Docstring).

    Zeilen mit ``kind == "warn"`` (die amtlichen Warnungen) sind bewusst
    ausgenommen: sie zeigen keine Wettergroesse, sondern Warn-Chips.
    """
    findings: list[str] = []
    for row in rows:
        if row.get("kind") == "warn":
            continue
        key = row.get("key")
        metric_id = row.get("metric_id")
        if not metric_id:
            findings.append(
                f"{source}-Zeile {key!r}: kein `metric_id` -- die Zeile nennt "
                f"ihre zentrale Wettergroesse nicht, ihre Beschriftung ist "
                f"damit nicht aus dem Register ableitbar (Bug-Typ #1296/#1324)."
            )
            continue
        try:
            metric = get_metric(metric_id)
        except KeyError:
            findings.append(
                f"{source}-Zeile {key!r}: `metric_id`={metric_id!r} ist im "
                f"zentralen Register (src/app/metric_catalog.py) unbekannt."
            )
            continue
        aggregation = row.get("aggregation")
        if not expect_aggregation:
            if aggregation is not None:
                findings.append(
                    f"{source}-Zeile {key!r}: traegt `aggregation`="
                    f"{aggregation!r} -- die Stundentabelle zeigt "
                    f"Momentanwerte, keine Auswertung, die Angabe waere also "
                    f"eine falsche Behauptung."
                )
            continue
        if not aggregation:
            findings.append(
                f"{source}-Zeile {key!r}: keine `aggregation` -- welche "
                f"Auswertung von {metric_id!r} die Zeile zeigt, ist nicht "
                f"hinterlegt (zentral moeglich: "
                f"{sorted(metric.summary_fields)})."
            )
            continue
        if aggregation not in metric.summary_fields:
            findings.append(
                f"{source}-Zeile {key!r}: `aggregation`={aggregation!r} ist "
                f"keine Auswertung von {metric_id!r} (zentral: "
                f"{sorted(metric.summary_fields)})."
            )
    return findings


# ---------------------------------------------------------------------------
# Waechter gegen die echten Daten
# ---------------------------------------------------------------------------


def test_every_overview_row_links_to_the_central_catalog():
    """AC-3: jede Zeile der Uebersichtstabelle (ausser den amtlichen
    Warnungen) nennt eine im Register aufloesbare Groesse UND die gezeigte
    Auswertung."""
    findings = _linkage_findings(CV2_METRICS, "CV2_METRICS")

    assert not findings, (
        "Zeilen der Uebersichtstabelle ohne belastbare Verknuepfung ins "
        "zentrale Namensregister:\n" + "\n".join(f"  - {f}" for f in findings)
    )


def test_every_hour_row_links_to_the_central_catalog():
    """AC-3 fuer die Stundentabelle -- mit dem anderen Massstab: jede Spalte
    nennt eine im Register aufloesbare Groesse, traegt aber KEINE
    ``aggregation`` (Momentanwert, s. Modul-Docstring).

    Dieser Test ist heute bereits erfuellt (alle 9 Spalten tragen seit #1106
    eine ``metric_id``, keine traegt eine ``aggregation``) -- er haelt den
    Zustand fest, statt ihn herzustellen. Der RED-Nachweis von A2a haengt
    allein an der Uebersichtstabelle.
    """
    findings = _linkage_findings(
        HOUR_METRICS, "HOUR_METRICS", expect_aggregation=False
    )

    assert not findings, (
        "Spalten der Stundentabelle mit fehlerhafter Verknuepfung ins "
        "zentrale Namensregister:\n" + "\n".join(f"  - {f}" for f in findings)
    )


# ---------------------------------------------------------------------------
# Wirkungsnachweis -- der Waechter darf nicht nur zufaellig gruen sein
# (Vorbild: test_compare_metric_catalog_consistency.py::
#  test_guard_actually_fails_when_a_catalog_metric_has_no_cv2_row)
# ---------------------------------------------------------------------------


def _row_with_metric_id(rows: list[dict]) -> dict:
    """Erste Zeile, die heute eine ``metric_id`` traegt -- an ihr laesst sich
    ein Verlust der Verknuepfung ueberhaupt erst herbeifuehren."""
    for row in rows:
        if row.get("kind") != "warn" and row.get("metric_id"):
            return row
    pytest.fail(
        "Keine einzige CV2_METRICS-Zeile traegt eine `metric_id` -- der "
        "Wirkungsnachweis haette nichts, das er beschaedigen koennte."
    )


def test_guard_reports_a_row_whose_metric_id_was_removed():
    """Wirkungsnachweis 1: einer KOPIE der echten Zeilenliste wird die
    ``metric_id`` einer Zeile genommen (so kamen die Zeilen aus #1296/#1324 in
    die Liste). Der Waechter muss diese Zeile daraufhin beim Namen nennen --
    und der Assert-Ausdruck des Waechters muss gegen die beschaedigte Kopie
    tatsaechlich fehlschlagen. Mutiert keine Produktivdaten (deepcopy)."""
    rows = copy.deepcopy(CV2_METRICS)
    victim = _row_with_metric_id(rows)
    victim_key = victim["key"]
    before = _linkage_findings(rows, "CV2_METRICS")

    del victim["metric_id"]
    after = _linkage_findings(rows, "CV2_METRICS")

    assert after != before, (
        f"Das Entfernen der `metric_id` von {victim_key!r} aendert das "
        f"Waechter-Ergebnis nicht -- der Waechter prueft die Verknuepfung "
        f"nicht wirklich."
    )
    named = [f for f in after if repr(victim_key) in f and "`metric_id`" in f]
    assert named, (
        f"Kein Befund nennt die beschaedigte Zeile {victim_key!r} samt "
        f"fehlender `metric_id` -- der Waechter sagt nicht, WAS kaputt ist. "
        f"Befunde: {after}"
    )

    # Derselbe Assert-Ausdruck wie im Waechter-Test oben muss gegen die
    # beschaedigte Kopie tatsaechlich einen AssertionError werfen.
    with pytest.raises(AssertionError):
        assert not after, (
            "Zeilen der Uebersichtstabelle ohne belastbare Verknuepfung ins "
            "zentrale Namensregister:\n" + "\n".join(f"  - {f}" for f in after)
        )


def test_guard_reports_a_row_with_an_evaluation_the_catalog_does_not_know():
    """Wirkungsnachweis 2: eine Zeile behauptet eine Auswertung, die es zu
    ihrer Groesse zentral nicht gibt (z.B. "Summe" der Temperatur). Der
    Waechter muss die Zeile nennen und die zentral moeglichen Auswertungen
    dazusagen -- sonst faellt eine Bedeutungsverwechslung (min statt max) nie
    auf."""
    rows = copy.deepcopy(CV2_METRICS)
    victim = _row_with_metric_id(rows)
    victim_key = victim["key"]
    metric = get_metric(victim["metric_id"])
    bogus = "auswertung_die_es_zentral_nicht_gibt"
    assert bogus not in metric.summary_fields, "Vorbedingung: Wert ist unbekannt"

    victim["aggregation"] = bogus
    findings = _linkage_findings(rows, "CV2_METRICS")

    named = [f for f in findings if repr(victim_key) in f and bogus in f]
    assert named, (
        f"Kein Befund nennt die Zeile {victim_key!r} mit der erfundenen "
        f"Auswertung {bogus!r}. Befunde: {findings}"
    )
    assert any(str(sorted(metric.summary_fields)) in f for f in named), (
        f"Der Befund nennt die zentral moeglichen Auswertungen nicht "
        f"({sorted(metric.summary_fields)}) -- ohne sie weiss niemand, was "
        f"stattdessen dort stehen muesste: {named}"
    )


def test_hour_guard_reports_missing_metric_id_and_a_fabricated_aggregation():
    """Wirkungsnachweis 3: derselbe Nachweis fuer die Stundentabelle, gegen
    ihren eigenen Massstab. Einer KOPIE der echten Spaltenliste wird der ersten
    Spalte die ``metric_id`` genommen und einer zweiten faelschlich eine
    ``aggregation`` verpasst. Beide Beschaedigungen muessen benannt werden --
    sonst waere der (heute schon erfuellte) Stunden-Waechter nur zufaellig
    gruen. Mutiert keine Produktivdaten (deepcopy)."""
    rows = copy.deepcopy(HOUR_METRICS)
    assert len(rows) >= 2, "Vorbedingung: mindestens zwei Stundenspalten"
    stripped, fabricated = rows[0], rows[1]
    stripped_key, fabricated_key = stripped["key"], fabricated["key"]

    assert _linkage_findings(rows, "HOUR_METRICS", expect_aggregation=False) == [], (
        "Vorbedingung verletzt: die echten Stundenspalten sind schon vor der "
        "kuenstlichen Beschaedigung auffaellig -- der Nachweis waere nicht "
        "aussagekraeftig."
    )

    del stripped["metric_id"]
    fabricated["aggregation"] = "max"
    findings = _linkage_findings(rows, "HOUR_METRICS", expect_aggregation=False)

    assert [f for f in findings if repr(stripped_key) in f and "`metric_id`" in f], (
        f"Kein Befund nennt die Spalte {stripped_key!r} samt fehlender "
        f"`metric_id`. Befunde: {findings}"
    )
    assert [
        f for f in findings
        if repr(fabricated_key) in f and "`aggregation`" in f and "Momentanwerte" in f
    ], (
        f"Kein Befund nennt die Spalte {fabricated_key!r} samt der faelschlich "
        f"gesetzten `aggregation` (und den Grund). Befunde: {findings}"
    )

    # Derselbe Assert-Ausdruck wie im Stunden-Waechter oben muss gegen die
    # beschaedigte Kopie tatsaechlich einen AssertionError werfen.
    with pytest.raises(AssertionError):
        assert not findings, (
            "Spalten der Stundentabelle mit fehlerhafter Verknuepfung ins "
            "zentrale Namensregister:\n" + "\n".join(f"  - {f}" for f in findings)
        )


def test_guard_stays_silent_on_a_fully_linked_row_set():
    """Gegenprobe: eine vollstaendig verknuepfte Zeilenmenge (echte Kennungen
    aus dem Register) erzeugt KEINEN Befund -- inklusive der bewusst
    ausgenommenen Warn-Zeile. Ohne diese Probe koennte der Waechter alles
    anmeckern und waere als Nachweis wertlos."""
    healthy = [
        {"key": "warn", "label": "Amtliche Warnungen", "kind": "warn"},
        {"key": "temp_max", "metric_id": "temperature", "aggregation": "max"},
        {"key": "temp_min", "metric_id": "temperature", "aggregation": "min"},
        {"key": "wind_max", "metric_id": "wind", "aggregation": "max"},
        {"key": "precip_sum", "metric_id": "precipitation", "aggregation": "sum"},
        {"key": "humidity_avg", "metric_id": "humidity", "aggregation": "avg"},
    ]

    assert _linkage_findings(healthy, "PROBE") == [], (
        "Der Waechter meldet Befunde fuer eine vollstaendig verknuepfte "
        "Zeilenmenge -- er misst etwas anderes als die Verknuepfung."
    )
