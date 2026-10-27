"""RED — #2136 / ADR-0068: Spaltenkopf-Kollisionen des 3-Tages-Ausblicks.

SPEC: docs/specs/modules/fix_2136_outlook_col_label.md — AC-6, AC-7, AC-8
ADR:  docs/adr/0068-ausblick-spaltenkopf-nutzt-col-label.md
KONTEXT: docs/context/fix-2136-outlook-col-label.md

ADR-0037 hatte `col_label` als Ausblick-Kopfquelle 2026-07-27 verworfen, weil
`temperature` fuer min/max/avg identisch "Temp" liefert. ADR-0068 haelt
dagegen, dass die seither gebaute Merge-/Dedup-Mechanik in `outlook_columns()`
diesen Einwand generisch aufloest. Genau das pruefen die drei Tests hier:

* **AC-6** — konfigurierbarer Ausblick, drei Temperatur-Auswertungen: Tief+Hoch
  verschmelzen zur Spannen-Spalte, die verbleibende Mittel-Spalte bekommt ihr
  Auswertungs-Suffix. Kein Kopf-Duplikat.
* **AC-7** — Standardfall-Ausblick: die beiden fest verdrahteten Temperatur-
  Spalten bekommen unterscheidbare Koepfe, bleiben aber getrennte Spalten.
* **AC-8** — Mutations-Gegenprobe: ein verfaelschtes `col_label` im Register
  muss auf BEIDE Renderpfade durchschlagen. Schlaegt es nicht durch, steht der
  Name noch ein zweites Mal im Renderer.

Kern-Schicht, deterministisch: keine Mocks/`patch()`/`MagicMock`, kein Netz.
Die beiden Kontextmanager veraendern echte Katalogdaten (eine zusaetzliche
Katalogzeile, ein ersetzter `MetricDefinition`-Wert) und stellen den Bestand
im `finally` nachweislich wieder her — Modul-Zustand, der in einen spaeteren
Test leckte, erzeugte dort ein falsches Rot oder ein falsches Gruen.

Pfadregel #1409: Pruefling relativ zur eigenen Testdatei aufloesen.
"""
from __future__ import annotations

import contextlib
import dataclasses
import re
import sys
from datetime import timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
for _pfad in (REPO_ROOT, REPO_ROOT / "src"):
    if str(_pfad) not in sys.path:
        sys.path.insert(0, str(_pfad))

_UTC = timezone.utc

# Erkennbar fremd, damit ein Durchschlagen nicht mit einem echten Katalogwert
# verwechselt werden kann.
MUTATIONS_MARKE = "ZzPruefmarke"


# ---------------------------------------------------------------------------
# Fixturen auf echten Katalogdaten (kein Mock-Framework)
# ---------------------------------------------------------------------------

@contextlib.contextmanager
def col_label_verfaelscht(metric_id: str, wert: str):
    """Ersetzt `MetricDefinition.col_label` einer Groesse zur Testzeit.

    `MetricDefinition` ist `frozen=True`; ersetzt wird deshalb das Objekt in
    ALLEN DREI Registern (`_METRICS`, `_METRICS_BY_ID`, `_METRICS_BY_COL_KEY`).
    Nur die Liste zu aendern reichte nicht (`get_metric()` liest das Dict), nur
    das Dict zu aendern ebenfalls nicht (`get_col_defs()` liest die Liste) —
    und eine halb verfaelschte Quelle liesse die Stundentabelle gegen den
    Ausblick auseinanderlaufen, wodurch AC-8 ein Rot meldete, das nichts
    beweist.
    """
    from app import metric_catalog as mc

    alt = mc._METRICS_BY_ID[metric_id]
    neu = dataclasses.replace(alt, col_label=wert)
    index = mc._METRICS.index(alt)
    try:
        mc._METRICS[index] = neu
        mc._METRICS_BY_ID[metric_id] = neu
        mc._METRICS_BY_COL_KEY[alt.col_key] = neu
        yield neu
    finally:
        mc._METRICS[index] = alt
        mc._METRICS_BY_ID[metric_id] = alt
        mc._METRICS_BY_COL_KEY[alt.col_key] = alt
    assert mc.get_metric(metric_id).col_label == alt.col_label, (
        "Die Mutation wurde nicht zurueckgenommen — der verfaelschte Wert "
        "leckt in jeden folgenden Test dieses Prozesses."
    )


def _temperatur_mittel_katalogzeile() -> dict:
    """Eine dritte Temperatur-Katalogzeile (Mittel), aus der bestehenden
    Hoch-Zeile abgeleitet.

    Ohne sie ist AC-6 ueberhaupt nicht erreichbar: seit #1848 A2 leitet
    `derived_aggregations()` die Auswertungen aus dem Katalog ab, und
    `COMPARE_METRIC_CATALOG` fuehrt fuer `temperature` nur `min` und `max`.
    `MetricDefinition.summary_fields` kennt `avg` (`temp_avg_c`) bereits — es
    fehlt allein die Katalogzeile.
    """
    from output.renderers.compare_metric_catalog import COMPARE_METRIC_CATALOG

    vorlage = next(e for e in COMPARE_METRIC_CATALOG if e.get("key") == "temp_max_c")
    return {**vorlage, "key": "temp_avg_c", "aggregation": "avg"}


@contextlib.contextmanager
def zusaetzliche_katalogzeile(zeile: dict):
    """Haengt eine Katalogzeile an `COMPARE_METRIC_CATALOG` und nimmt sie
    nachweislich wieder heraus.

    Die Paar-Aufloesung `key_for()` liest einen beim Modul-Import gebauten
    Index (`_KEY_BY_METRIC_AGGREGATION`) — ohne Eintrag dort bliebe die neue
    Zeile fuer `_catalog_entry()` unsichtbar und der Test pruefte still
    weiterhin nur zwei Auswertungen.
    """
    from output.renderers import compare_metric_catalog as cmc

    paar = (zeile["metric_id"], zeile["aggregation"])
    vorher = len(cmc.COMPARE_METRIC_CATALOG)
    try:
        cmc.COMPARE_METRIC_CATALOG.append(zeile)
        cmc._KEY_BY_METRIC_AGGREGATION[paar] = zeile["key"]
        yield zeile
    finally:
        cmc.COMPARE_METRIC_CATALOG.remove(zeile)
        cmc._KEY_BY_METRIC_AGGREGATION.pop(paar, None)
    assert len(cmc.COMPARE_METRIC_CATALOG) == vorher, (
        "Die Testzeile wurde nicht aus dem Compare-Katalog entfernt — sie "
        "leckt in jeden folgenden Test dieses Prozesses."
    )
    assert cmc.key_for(*paar) is None, (
        "Der Paar-Index kennt die Testzeile noch — sie leckt in jeden "
        "folgenden Test dieses Prozesses."
    )


def _th_texte(html: str) -> list[str]:
    return [re.sub(r"<[^>]+>", "", t).strip()
            for t in re.findall(r"<th[^>]*>(.*?)</th>", html, re.DOTALL)]


def _ausblick_kopf(metrics: list[str]) -> list[str]:
    """Kopfzeile des konfigurierbaren Ausblicks, ueber den echten Renderer."""
    from app.models import SegmentWeatherSummary, ThunderLevel
    from output.renderers.email.outlook import build_outlook_row, render_outlook_table

    summary = SegmentWeatherSummary(
        temp_min_c=9.0, temp_max_c=27.0, temp_avg_c=18.0,
        precip_sum_mm=2.5, gust_max_kmh=44.0,
        thunder_level_max=ThunderLevel.MED,
    )
    zeile = build_outlook_row(summary, points=[], weekday="Mo", tz=_UTC,
                              metrics=metrics)
    return _th_texte(render_outlook_table([zeile], show_acc=False, metrics=metrics))


# ---------------------------------------------------------------------------
# AC-6 — konfigurierbarer Ausblick, drei Temperatur-Auswertungen
# ---------------------------------------------------------------------------

def test_ac6_drei_temperatur_auswertungen_ergeben_keine_doppelte_ueberschrift():
    """AC-6: Given eine Ausblick-Auswahl, in der `temperature` mit Tief, Hoch
    UND Mittel darstellbar ist / When `outlook_columns()` die Spalten baut /
    Then verschmelzen Tief+Hoch zu EINER Spannen-Spalte (`_merge_min_max_pairs
    ()`, unveraendert) und die verbleibende Mittel-Spalte traegt
    `col_label + " " + aggregation_label_de("avg")` — nie zweimal derselbe
    Spaltenkopf.

    Genau dieser Fall ist der Einwand, mit dem ADR-0037 `col_label` verworfen
    hatte; ADR-0068 behauptet, die seither gebaute Merge-/Dedup-Mechanik loese
    ihn generisch auf. Der Test haelt diese Behauptung fest.
    """
    from app.metric_catalog import aggregation_label_de, get_metric
    from output.renderers.compare_outlook_metric_ids import (
        derived_aggregations, outlook_columns,
    )

    with zusaetzliche_katalogzeile(_temperatur_mittel_katalogzeile()):
        assert derived_aggregations("temperature") == ["min", "max", "avg"], (
            "Die Testzeile hat die dritte Auswertung nicht wirksam gemacht — "
            f"abgeleitet wurden {derived_aggregations('temperature')!r}. Ohne "
            "drei Auswertungen prueft dieser Test die Kollision gar nicht."
        )

        temp = get_metric("temperature").col_label
        erwartet = [temp, f"{temp} {aggregation_label_de('avg')}"]

        spalten = outlook_columns(["temperature"])
        labels = [c["label"] for c in spalten]
        assert labels == erwartet, (
            f"Die drei Temperatur-Auswertungen ergeben die Spaltenkoepfe "
            f"{labels!r} statt {erwartet!r} — erwartet ist die Spannen-Spalte "
            f"{temp!r} plus die mit ihrer Auswertung unterschiedene "
            "Mittel-Spalte (AC-6, ADR-0068)."
        )
        assert len(set(labels)) == len(labels), (
            f"Zwei Ausblick-Spalten tragen denselben Kopf: {labels!r}. Genau "
            "das war der ADR-0037-Einwand gegen `col_label` (AC-6)."
        )

        soll = ["Tag"] + erwartet
        kopf = _ausblick_kopf(["temperature"])
        assert kopf == soll, (
            f"Die gerenderte Ausblick-Tabelle traegt {kopf!r} statt {soll!r} "
            "— die Spaltenbeschreibung stimmt, der Renderer uebernimmt sie "
            "aber nicht (AC-6)."
        )


# ---------------------------------------------------------------------------
# AC-7 — Standardfall-Ausblick, zwei feste Temperaturspalten
# ---------------------------------------------------------------------------

def test_ac7_standardfall_ausblick_unterscheidet_tief_und_hoch_temperatur():
    """AC-7: Given eine Mail OHNE konfigurierte Auswahl (Pfad 1, zwei fest
    verdrahtete Temperaturspalten `N`/`D`) / When der Ausblick gerendert wird
    / Then tragen die beiden Spalten unterscheidbare Koepfe mit `col_label`
    als gemeinsamem Praefix — und bleiben strukturell ZWEI Spalten, die
    Gesamtzahl bleibt bei acht.

    Die Merge-Mechanik aus Pfad 2 greift hier nicht: Pfad 1 ruft
    `outlook_columns()` gar nicht auf. Eine nackte `col_label`-Ersetzung
    ergaebe deshalb zweimal denselben Kopf — dieser Test schliesst beides aus,
    die Dopplung UND die Zusammenfuehrung zur Spannen-Spalte (das waere eine
    Layout-Aenderung ausserhalb des Scopes).
    """
    from app.metric_catalog import get_metric
    from tests.tdd.test_compare_outlook_metric_selection import (
        _headers, _outlook_tables, _render_mail,
    )

    html, _text = _render_mail(outlook_metrics=None)
    tabellen = _outlook_tables(html)
    assert tabellen, "Ohne Auswahl muss der 3-Tages-Ausblick erscheinen"
    kopf = _headers(tabellen[0])

    temp = get_metric("temperature").col_label
    treffer = [h for h in kopf if h.startswith(temp)]
    assert len(treffer) == 2, (
        f"Der Standardfall-Ausblick fuehrt {len(treffer)} Spalten mit dem "
        f"Temperatur-Praefix {temp!r} statt zweier (Tief und Hoch). Kopfzeile: "
        f"{kopf!r} — die beiden Kuerzel 'N'/'D' stammen noch aus der eigenen, "
        "handgepflegten Namensliste in outlook.py (AC-7)."
    )
    assert treffer[0] != treffer[1], (
        f"Beide Temperaturspalten tragen denselben Kopf {treffer[0]!r} — genau "
        "die Kollision, die ADR-0037 gegen `col_label` ins Feld gefuehrt hat. "
        "Pfad 1 braucht das Auswertungs-Suffix (AC-7)."
    )
    assert len(kopf) == 8, (
        f"Der Standardfall-Ausblick zeigt {len(kopf)} Spalten statt acht "
        f"(Tag + 7): {kopf!r}. Tief und Hoch duerfen NICHT zu einer "
        "Spannen-Spalte zusammengefuehrt werden — das waere eine "
        "Layout-Aenderung ausserhalb des Scopes (AC-7, Abgrenzung)."
    )


# ---------------------------------------------------------------------------
# AC-8 — Mutations-Gegenprobe: der Kopf ist abgeleitet, nicht doppelt gepflegt
# ---------------------------------------------------------------------------

def test_ac8_verfaelschtes_col_label_schlaegt_auf_beide_ausblick_pfade_durch():
    """AC-8: Given ein zur Testzeit verfaelschtes `col_label` einer im Ausblick
    sichtbaren Groesse / When dieselben Pruefbloecke wie in AC-1 und AC-2
    laufen / Then stimmen die gerenderten Spaltenkoepfe mit dem VERFAELSCHTEN
    Wert ueberein — nicht mit dem alten Literal.

    Das ist die eigentliche Zusicherung dieses Fixes: nicht "der Kopf heisst
    jetzt Temp", sondern "der Kopf wird aus dem Register ABGELEITET". Bliebe
    irgendwo ein hartkodiertes Kuerzel stehen (im `thead` von Pfad 1 oder in
    der Label-Quelle von Pfad 2), liefe die Mutation daran vorbei und der
    Pruefblock schluege fehl.

    Die Pruefbloecke werden importiert, nicht nachgebaut — ein zweiter,
    hier getippter Assertion-Block pruefte nur sich selbst.
    """
    from tests.tdd.test_compare_outlook_metric_selection import (
        SEL_NIEDERSCHLAG, SEL_TEMPERATUR, pruefe_pfad1_kopfzeile_html,
        pruefe_pfad2_kopfzeile_html,
    )

    with col_label_verfaelscht("temperature", MUTATIONS_MARKE):
        with col_label_verfaelscht("gust", MUTATIONS_MARKE + "G"):
            kopf1 = pruefe_pfad1_kopfzeile_html()
            kopf2 = pruefe_pfad2_kopfzeile_html([SEL_TEMPERATUR, SEL_NIEDERSCHLAG])

    assert sum(1 for h in kopf1 if h.startswith(MUTATIONS_MARKE)) == 3, (
        f"Die Standardfall-Kopfzeile {kopf1!r} traegt die Pruefmarke nicht an "
        "allen drei verfaelschten Stellen (Temperatur Tief, Temperatur Hoch, "
        "Böen) — dort steht der Name noch ein zweites Mal im Renderer (AC-8)."
    )
    assert MUTATIONS_MARKE in kopf2, (
        f"Die Kopfzeile des konfigurierbaren Ausblicks {kopf2!r} traegt die "
        "Pruefmarke nicht — die Beschriftung stammt nicht aus "
        "`MetricDefinition.col_label` (AC-8)."
    )
