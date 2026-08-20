"""RED — #1848 A2: aus der Kennung leitet der Katalog die Ausblick-Spalten ab.

SPEC: docs/specs/modules/feat_1848_a2_ausblick_kennungen.md — AC-3, AC-5, AC-6
KONTEXT: docs/context/feat-1848-a2-outlook-kennungen.md (M1, M5, R-A2-2, R-A2-3)

Die Ableitungsregel der Spec:

    Kennung  =>  alle Auswertungen aus available_aggregations(kennung),
                 die eine Zeile im Compare-Katalog haben (key_for != None),
                 in der Reihenfolge von available_aggregations()

🔴 Die Quelle ist ``available_aggregations()``, NICHT ``summary_fields.keys()``:
``precipitation`` und ``thunder`` fuehren dort zusaetzlich ``onset``, und
``summary_field_for('precipitation','onset')`` loest auf. Ueber
``summary_fields`` abgeleitet entstuenden also ``onset``-Spalten (M1).

Beschriftungs-Erwartungen kommen aus dem Compare-Katalog selbst
(``get_compare_metric_catalog()``), nicht aus getippten Literalen — der Test
schreibt keine Beschriftung vor, er prueft nur, dass der Wert unter der
Beschriftung SEINER Groesse steht.

Kern-Schicht: keine Mocks, kein Netz. Pfadregel #1409.
"""
from __future__ import annotations

import json
import logging
import os
import re
import subprocess
import sys
from datetime import timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
for _pfad in (REPO_ROOT, REPO_ROOT / "src"):
    if str(_pfad) not in sys.path:
        sys.path.insert(0, str(_pfad))

_UTC = timezone.utc

# Vier Groessen mit paarweise unterscheidbaren Werten: bei zwei Spalten koennte
# ein nicht gefangener Versatz Zufall sein.
AUSWAHL = ["temperature", "precipitation", "gust", "thunder"]

# Die sieben festen Standardspalten des Altform-Zweiges (outlook.py:157-170).
FESTE_SIEBEN = ["N", "D", "R", "PR", "Wind", "Böen", "Gew"]


def _katalog_label(metric_id: str) -> str:
    """Beschriftung, die der Compare-Katalog fuer diese Groesse fuehrt."""
    from output.renderers.compare_metric_catalog import get_compare_metric_catalog

    for eintrag in get_compare_metric_catalog():
        if eintrag.get("metric_id") == metric_id:
            return eintrag["label"]
    raise AssertionError(f"Der Compare-Katalog kennt {metric_id!r} nicht.")


def _summary():
    from app.models import SegmentWeatherSummary, ThunderLevel

    return SegmentWeatherSummary(
        temp_min_c=9.0, temp_max_c=27.0, precip_sum_mm=2.5,
        gust_max_kmh=44.0, thunder_level_max=ThunderLevel.MED,
    )


def zuordnung() -> dict[str, str]:
    """Beschriftung -> Zellentext, aus ZWEI getrennten Wegen zusammengesetzt.

    Genau die Naht aus R-A2-2: die Kopfzeile entsteht in
    ``render_outlook_table()`` aus einem eigenen ``outlook_columns()``-Aufruf,
    die Zellen entstehen in ``build_outlook_row()`` aus einem zweiten. Beide
    sind ausschliesslich ueber den Listenindex verbunden — weicht die
    abgeleitete Spaltenmenge zwischen den Aufrufen ab, verrutschen Werte
    gegen Beschriftungen, still und ohne Ausnahme.

    Modul-Ebene (nicht im Test verschachtelt), damit der Unterprozess-Lauf
    mit abweichendem ``PYTHONHASHSEED`` DIESELBE Funktion treibt statt einer
    zweiten Nachbildung.
    """
    from output.renderers.email.outlook import build_outlook_row, render_outlook_table

    zeile = build_outlook_row(_summary(), points=[], weekday="Mo", tz=_UTC,
                              metrics=AUSWAHL)
    html = render_outlook_table([zeile], show_acc=False, metrics=AUSWAHL)

    kopf = [re.sub(r"<[^>]+>", "", t).strip()
            for t in re.findall(r"<th[^>]*>(.*?)</th>", html, re.DOTALL)]
    zellen = [re.sub(r"<[^>]+>", "", t).strip()
              for t in re.findall(r"<td[^>]*>(.*?)</td>", html, re.DOTALL)]

    if len(kopf) < 2 or len(zellen) < 2:
        raise AssertionError(
            f"Die Ausblick-Tabelle hat keine Wert-Spalten: kopf={kopf!r}, "
            f"zellen={zellen!r}. Die Kennungsauswahl {AUSWAHL!r} wurde "
            "vollstaendig verworfen — der heutige Aufloeser kennt nur Paare "
            "(AC-6)."
        )
    if len(kopf) != len(zellen):
        raise AssertionError(
            f"Kopfzeile ({len(kopf)}) und Wertzeile ({len(zellen)}) haben "
            f"verschiedene Laengen: {kopf!r} / {zellen!r} — die beiden "
            "outlook_columns()-Aufrufe liefern verschiedene Spaltenmengen."
        )
    return dict(zip(kopf[1:], zellen[1:]))


# ---------------------------------------------------------------------------
# AC-5 — die Kennung erzeugt keine onset-Spalte
# ---------------------------------------------------------------------------

def test_ac5_niederschlag_ergibt_genau_eine_spalte_ohne_onset():
    """AC-5: Given die Kennung ``precipitation``, die im Zentralregister neben
    ``sum`` auch ``onset`` fuehrt / When die Spalten abgeleitet werden / Then
    entsteht GENAU EINE Niederschlags-Spalte (die Summe) und keine zusaetzliche
    aus ``onset``.
    """
    from output.renderers.compare_outlook_metric_ids import outlook_columns

    spalten = outlook_columns(["precipitation"])
    felder = [c.get("field") or f"{c.get('field_min')}/{c.get('field_max')}"
              for c in spalten]

    assert len(spalten) == 1, (
        f"Aus der Kennung 'precipitation' entstanden {len(spalten)} Spalten "
        f"({felder!r}) statt genau einer. Erwartet ist die Summe; eine "
        "Ableitung ueber summary_fields.keys() statt ueber "
        "available_aggregations() erzeugt hier zusaetzlich eine "
        "onset-Spalte (AC-5, M1)."
    )
    assert felder == ["precip_sum_mm"], (
        f"Die abgeleitete Niederschlags-Spalte liest {felder!r} statt "
        "['precip_sum_mm'] (AC-5)."
    )


def test_ac5_gewitter_ergibt_genau_eine_spalte_ohne_onset():
    """AC-5, zweite Groesse mit ``onset`` im Zentralregister: ``thunder``."""
    from output.renderers.compare_outlook_metric_ids import outlook_columns

    spalten = outlook_columns(["thunder"])
    felder = [c.get("field") or f"{c.get('field_min')}/{c.get('field_max')}"
              for c in spalten]

    assert len(spalten) == 1 and felder == ["thunder_level_max"], (
        f"Aus der Kennung 'thunder' entstanden {len(spalten)} Spalten "
        f"({felder!r}) statt genau einer auf 'thunder_level_max' (AC-5)."
    )


def test_ac5_keine_abgeleitete_spalte_liest_ein_onset_feld():
    """AC-5, Gegenprobe ueber ALLE waehlbaren Kennungen: keine einzige
    abgeleitete Spalte darf ein ``onset``-Feld lesen. Ein Einzelfall-Test auf
    zwei Groessen koennte eine falsche Ableitungsquelle andernorts uebersehen.
    """
    from output.renderers.compare_metric_catalog import get_compare_metric_catalog
    from output.renderers.compare_outlook_metric_ids import outlook_columns

    kennungen = sorted({e["metric_id"] for e in get_compare_metric_catalog()
                        if e.get("metric_id")})
    assert kennungen, "Der Compare-Katalog ist leer — der Test prueft nichts."

    spalten = outlook_columns(kennungen)
    assert spalten, (
        f"Keine der {len(kennungen)} Katalog-Kennungen ergab eine Spalte — "
        "die Ableitung aus der Kennung fehlt (AC-5)."
    )
    onset = [c for c in spalten
             if "onset" in str(c.get("field", ""))
             or "onset" in str(c.get("field_min", ""))
             or "onset" in str(c.get("field_max", ""))]
    assert not onset, (
        f"Abgeleitete Spalten lesen ein onset-Feld: {onset!r}. 'onset' ist "
        "kein Auswertungs-Vokabular (nicht in _AGGREGATION_ORDER) und darf "
        "nie eine Ausblick-Spalte erzeugen (AC-5)."
    )


# ---------------------------------------------------------------------------
# AC-6 — Wert steht unter der Beschriftung SEINER Groesse, prozessstabil
# ---------------------------------------------------------------------------

def test_ac6_jeder_wert_steht_unter_der_beschriftung_seiner_groesse():
    """AC-6: Given eine Ausblick-Auswahl mit mehreren Groessen / When Kopfzeile
    und Wertzeilen erzeugt werden / Then steht in jeder Spalte der Wert unter
    der zu ihm gehoerenden Beschriftung.

    Die Werte sind so gewaehlt, dass jeder eindeutig einer Groesse gehoert:
    ``9/27`` (Temperaturspanne), ``2.5`` (Niederschlag), ``44`` (Böen), ein
    deutsches Wort (Gewitter, ordinal). Ein Spaltenversatz faellt damit auf,
    ohne dass der Test eine Reihenfolge vorschreibt.
    """
    tabelle = zuordnung()

    assert tabelle.get(_katalog_label("temperature")) == "9/27", (
        f"Unter der Temperatur-Beschriftung steht "
        f"{tabelle.get(_katalog_label('temperature'))!r} statt '9/27'. "
        f"Gesamte Zuordnung: {tabelle!r} (AC-6)."
    )
    niederschlag = tabelle.get(_katalog_label("precipitation")) or ""
    assert "2.5" in niederschlag, (
        f"Unter der Niederschlags-Beschriftung steht {niederschlag!r} statt "
        f"des Niederschlagswerts 2.5. Gesamte Zuordnung: {tabelle!r} (AC-6)."
    )
    boeen = tabelle.get(_katalog_label("gust")) or ""
    assert "44" in boeen, (
        f"Unter der Böen-Beschriftung steht {boeen!r} statt des Böenwerts 44. "
        f"Gesamte Zuordnung: {tabelle!r} (AC-6)."
    )
    gewitter = tabelle.get(_katalog_label("thunder")) or ""
    assert gewitter and not re.search(r"\d", gewitter), (
        f"Unter der Gewitter-Beschriftung steht {gewitter!r} — erwartet ist "
        f"das deutsche Stufenwort, keine Zahl. Zuordnung: {tabelle!r} (AC-6)."
    )


def test_ac6_zuordnung_ist_ueber_frisch_gestartete_prozesse_unveraendert():
    """AC-6, zweiter Teil: dieselbe Zuordnung in FRISCH gestarteten Prozessen
    mit abweichendem ``PYTHONHASHSEED``.

    Ein Lauf im selben Prozess genuegt nicht: eine ueber ``set``/``dict``
    gebaute Ableitung kann innerhalb eines Prozesses stabil sein und trotzdem
    zwischen Prozessen die Reihenfolge wechseln — und die Naht Kopf/Zellen
    haengt allein am Listenindex (R-A2-2).

    Der Unterprozess ruft DIESELBE ``zuordnung()`` auf; er baut nichts nach.
    """
    programm = (
        "import json, sys;"
        f"sys.path.insert(0, {str(REPO_ROOT)!r});"
        "from tests.tdd.test_outlook_columns_from_metric_ids import zuordnung;"
        "print(json.dumps(zuordnung(), ensure_ascii=False))"
    )
    ergebnisse = {}
    for seed in ("0", "12345"):
        umgebung = dict(os.environ, PYTHONHASHSEED=seed)
        lauf = subprocess.run([sys.executable, "-c", programm], env=umgebung,
                              capture_output=True, text=True, timeout=180)
        assert lauf.returncode == 0, (
            f"Der Lauf mit PYTHONHASHSEED={seed} scheiterte "
            f"(Exit {lauf.returncode}):\n{lauf.stderr.strip()[-1500:]}"
        )
        ergebnisse[seed] = json.loads(lauf.stdout.strip().splitlines()[-1])

    assert ergebnisse["0"] == ergebnisse["12345"], (
        "Die Beschriftung-Wert-Zuordnung haengt von der Hash-Streuung ab:\n"
        f"  PYTHONHASHSEED=0     -> {ergebnisse['0']!r}\n"
        f"  PYTHONHASHSEED=12345 -> {ergebnisse['12345']!r}\n"
        "Die Ableitung aus der Kennung muss streng deterministisch und "
        "reihenfolgestabil sein (AC-6, R-A2-2)."
    )
    assert ergebnisse["0"] == zuordnung(), (
        "Der Prozess dieses Testlaufs sieht eine andere Zuordnung als ein "
        f"frisch gestarteter: {zuordnung()!r} gegen {ergebnisse['0']!r} (AC-6)."
    )


# ---------------------------------------------------------------------------
# AC-3 — unaufloesbar ist NICHT dasselbe wie bewusst geleert
# ---------------------------------------------------------------------------

def test_ac3_unaufloesbare_auswahl_zeigt_die_sieben_festen_spalten_und_warnt(caplog):
    """AC-3: Given ein Trip, dessen gespeicherte Ausblick-Auswahl
    ausschliesslich unaufloesbare Eintraege enthaelt / When das Briefing
    gerendert wird / Then erscheint der 3-Tages-Ausblick mit den sieben festen
    Standardspalten UND eine Warnung wird protokolliert — der Block
    verschwindet NICHT.

    Heute kollabiert die Auswahl zu ``[]`` (M5), und ``[]`` heisst in der
    Drei-Werte-Semantik 'bewusst geleert': der Ausblick verschwindet
    kommentarlos, statt zurueckzufallen. Genau das ist der Rueckroll-Fehlerpfad
    R-A2-3 — nicht als Fehler sichtbar, sondern als stille Abwesenheit.
    """
    from tests.helpers.trip_outlook_selection import (
        display_config, html_outlook_headers, html_outlook_table,
        outlook_rows, plain_outlook_block, render_trip_mail,
    )

    dc = display_config(outlook_metrics=["einhorn", "confidence"])

    with caplog.at_level(logging.WARNING):
        zeilen = outlook_rows(trip_display_config=dc)
        html, plain = render_trip_mail(dc, zeilen)

    assert html_outlook_table(html) is not None, (
        "Der 3-Tages-Ausblick fehlt in der HTML-Mail vollstaendig. Eine "
        "unaufloesbare Auswahl wurde wie 'bewusst geleert' behandelt und hat "
        "den Block abgeschaltet, statt auf die sieben festen Standardspalten "
        "zurueckzufallen (AC-3, R-A2-3/M5)."
    )
    kopf = html_outlook_headers(html)
    assert kopf[:1] == ["Tag"] and all(k in kopf for k in FESTE_SIEBEN), (
        f"Der Ausblick zeigt die Kopfzeile {kopf!r} statt der sieben festen "
        f"Standardspalten {FESTE_SIEBEN!r} (AC-3)."
    )
    assert plain_outlook_block(plain), (
        "Im Klartext-Teil derselben Mail fehlt der Ausblick-Block (AC-3)."
    )

    warnungen = "\n".join(r.getMessage() for r in caplog.records
                          if r.levelno >= logging.WARNING)
    assert "einhorn" in warnungen, (
        "Die unaufloesbaren Eintraege wurden still verworfen — es fehlt die "
        f"Protokollwarnung. Gesehene Warnungen:\n{warnungen}"
    )
