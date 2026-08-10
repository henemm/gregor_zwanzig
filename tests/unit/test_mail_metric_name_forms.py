"""Namensformen der Mail-Beschriftungen: Kurzform englisch, voller Name deutsch.

PO-Entscheidung 2026-08-02 (Issue #1453): **wo wenig Platz ist, steht die
englische Fachkurzform; wo Platz ist, steht der ausgeschriebene deutsche
Name.** Konkret heisst das drei Dinge, die diese Datei nachweist:

* Die **Stundentabelle** (bis 22 Spalten, harte Platzgrenze) bleibt bei der
  englischen Kurzform ``MetricDefinition.col_label`` -- in der Vergleichs-Mail
  UND in der Tour-Mail (AC-1). Das ist ein Nicht-Regressions-Nachweis: er ist
  heute gruen und muss gruen bleiben. Er steht hier, weil Uebersichts- und
  Stundentabelle des Vergleichs aus DERSELBEN Funktion beschriftet werden
  (``compare_html.derive_row_labels``) -- die Umstellung der Uebersicht auf
  Deutsch ist genau die Aenderung, die versehentlich auch den Stundenkopf
  treffen kann.
* Zwei Kurzformen sind fachlich schlecht gewaehlt und werden korrigiert:
  ``Cond°`` -> ``Dew`` (Taupunkt ist kein Kondensationsgrad) und ``hPa`` ->
  ``Press`` (das war die Einheit, nicht der Name). Beide Mail-Typen ziehen mit,
  weil sie dieselbe Registerspalte lesen (AC-2). ``CAPE`` bleibt (AC-5).
* Die **Uebersichtstabelle** des Vergleichs (Zeilenkopf, praktisch unbegrenzt
  Platz) zeigt den ausgeschriebenen deutschen Namen ``label_de`` -- im
  HTML-Teil und im Klartext-Teil derselben Mail (AC-3). Sind zwei Auswertungen
  derselben Groesse gleichzeitig sichtbar, traegt jede Zeile die deutsche
  Auswertungs-Ergaenzung ("Temperatur Maximum"), nicht den rohen Schluessel
  ("Temp max") (AC-4).
* Die deutschen Namen kommen nachweislich aus dem zentralen Register und nicht
  aus einer abgeschriebenen Liste (AC-8) -- ``comparison._PLAIN_ROWS`` fuehrt
  dieselben Woerter als Telegram/SMS-Vokabular und waere die naheliegende
  falsche Quelle.

Kern-Schicht, deterministisch: echte ``ForecastDataPoint``-Objekte, echte
Renderer-Aufrufe, kein ``Mock()``/``patch()``, kein Netz. Die einzige
Manipulation ist in AC-8 ausdruecklich der Gegenstand des Tests (Registerwert
verstellen und schauen, ob er in der Mail ankommt).

SPEC: docs/specs/modules/fix_1453_namensformen.md (AC-1..AC-5, AC-8)
"""
from __future__ import annotations

import dataclasses
import re
from datetime import date, datetime, timezone

from app import metric_catalog as mc
from app.metric_catalog import get_metric
from app.models import (
    ForecastDataPoint, ForecastMeta, NormalizedTimeseries, Provider, ThunderLevel,
)
import pytest

from app.user import ComparisonResult, LocationResult, SavedLocation
from output.renderers.compare_metric_ids import resolve_enabled_metrics
from output.renderers.comparison import render_comparison_text
from output.renderers.email.compare_html import (
    HOUR_METRICS, derive_row_labels, render_compare_html,
)
from output.renderers.email.html import _render_html_table

TARGET_DATE = date(2026, 7, 8)

# Alle 26 waehlbaren Uebersichts-Groessen (Frontend-IDs, genau der Weg der
# Editor-Auswahl) -- sonst nagelte der Test nur die Haelfte der Zeilen fest.
ALL_OVERVIEW_SELECTION = [
    "temp_max_c", "wind_max_kmh", "precip_sum_mm", "pop_max_pct",
    "thunder_level_max", "sunny_hours_h", "cloud_avg_pct", "uv_index_max",
    "visibility_min_m", "snow_depth_cm", "snow_new_sum_cm", "temp_min_c",
    "gust_max_kmh", "cape_max_jkg", "freezing_level_m", "wind_direction_deg",
    "wind_chill_min_c", "wind_chill_max_c", "cloud_low_avg_pct",
    "cloud_mid_avg_pct", "cloud_high_avg_pct", "humidity_avg_pct",
    "dewpoint_avg_c", "pressure_avg_hpa", "precip_type_dominant",
    "snowfall_limit_m",
]

# Zielbeschriftung der Uebersicht: ausgeschriebener deutscher Registername,
# mit deutscher Auswertungs-Ergaenzung NUR bei Namensgleichheit (Temperatur
# und Gefuehlte Temperatur fuehren je zwei Auswertungen). Reihenfolge =
# Auswahl-Reihenfolge oben. Woertlich abgetippt, NICHT aus dem Register
# berechnet -- eine Berechnung waere gegen eine Verfaelschung des Registers
# blind und damit tautologisch gruen.
EXPECTED_OVERVIEW_LABELS = [
    "Amtliche Warnungen",
    "Temperatur Maximum", "Wind", "Niederschlag", "Regenwahrscheinlichkeit",
    "Gewitter", "Sonnenstunden", "Bewölkung", "UV-Index", "Sichtweite",
    "Schneehöhe", "Neuschnee", "Temperatur Minimum", "Böen",
    # Issue #1585: "Gewitterenergie (CAPE)" entfallen -- zentral nicht mehr
    # waehlbar, keine Uebersichtszeile mehr.
    "Nullgradgrenze", "Windrichtung",
    "Gefühlte Temperatur Minimum", "Gefühlte Temperatur Maximum",
    "Tiefe Wolken", "Mittelhohe Wolken", "Hohe Wolken", "Luftfeuchtigkeit",
    "Taupunkt", "Luftdruck", "Niederschlagsart", "Schneefallgrenze",
]

# Der Klartext-Zwilling kennt die Warn-Zeile nicht (dort stehen amtliche
# Warnungen als eigene "⚠️"-Zeilen, nicht als Tabellenzeile).
EXPECTED_OVERVIEW_LABELS_PLAIN = EXPECTED_OVERVIEW_LABELS[1:]


# ---------------------------------------------------------------------------
# Fixture
# ---------------------------------------------------------------------------

def _dp(hour: int) -> ForecastDataPoint:
    return ForecastDataPoint(
        ts=datetime(2026, 7, 8, hour, 0, tzinfo=timezone.utc),
        t2m_c=float(8 + (hour - 9)),
        wind10m_kmh=20.0,
        wind_direction_deg=270,
        gust_kmh=25.0,
        precip_1h_mm=1.0 if 13 <= hour <= 15 else 0.0,
        cloud_total_pct=50,
        thunder_level=ThunderLevel.MED if hour in (13, 14) else ThunderLevel.NONE,
        pop_pct=70 if 13 <= hour <= 15 else 20,
        humidity_pct=65,
        uv_index=6.0 if hour == 12 else 3.0,
        visibility_m=3000 if 13 <= hour <= 15 else 20000,
        wind_chill_c=float(6 + (hour - 9)),
        dewpoint_c=float(4 + (hour - 9) * 0.5),
        pressure_msl_hpa=1013.0,
    )


def _result() -> ComparisonResult:
    hourly = [_dp(h) for h in range(9, 18)]
    meta = ForecastMeta(
        provider=Provider.OPENMETEO, model="test",
        run=datetime(2026, 7, 8, 0, 0, tzinfo=timezone.utc),
        grid_res_km=1.0, interp="point_grid",
    )
    from services.weather_metrics import WeatherMetricsService

    ts = NormalizedTimeseries(meta=meta, data=hourly)
    svc = WeatherMetricsService()
    s = svc.compute_basis_metrics(ts)
    loc = LocationResult(
        location=SavedLocation(
            id="andermatt", name="Andermatt", lat=39.76, lon=2.71, elevation_m=200,
        ),
        score=50,
        temp_min=s.temp_min_c, temp_max=s.temp_max_c, wind_max=s.wind_max_kmh,
        gust_max=s.gust_max_kmh, cloud_avg=s.cloud_avg_pct, sunny_hours=4,
        wind_chill_min=svc._compute_wind_chill(ts),
        wind_chill_max=svc._compute_wind_chill_max(ts),
        hourly_data=hourly,
    )
    return ComparisonResult(
        locations=[loc], time_window=(0, 23), target_date=TARGET_DATE,
        created_at=datetime(2026, 7, 8, 4, 1),
    )


# ---------------------------------------------------------------------------
# Ausgabe auslesen
# ---------------------------------------------------------------------------

_TAGS = re.compile(r"<[^>]+>")


def _html_overview_labels(html: str) -> list[str]:
    """Erste Spalte (Beschriftung) jeder Zeile der Uebersichtstabelle."""
    start = html.index("min-width:760px")
    body = html[html.index("<tbody>", start) + len("<tbody>"):html.index("</tbody>", start)]
    labels = []
    for row_html in re.findall(r"<tr[^>]*>(.*?)</tr>", body, re.S):
        cells = [
            _TAGS.sub("", c).strip()
            for c in re.findall(r"<td[^>]*>(.*?)</td>", row_html, re.S)
        ]
        if cells:
            labels.append(cells[0])
    return labels


def _html_hour_header(html: str) -> list[str]:
    """Spaltenkopf der Vergleichs-Stundentabelle (erste Spalte immer "Zeit")."""
    for head in re.findall(r"<thead>(.*?)</thead>", html, re.S):
        cols = [
            _TAGS.sub("", c).strip()
            for c in re.findall(r"<th[^>]*>(.*?)</th>", head, re.S)
        ]
        if cols and cols[0] == "Zeit":
            return cols
    return []


def _tour_hour_header(html: str) -> list[str]:
    """Spaltenkopf der TOUR-Stundentabelle (erste Spalte "Time", letzte
    "Risk" -- beides feste Nicht-Metrik-Spalten)."""
    head = re.search(r"<thead>(.*?)</thead>", html, re.S)
    cols = [
        _TAGS.sub("", c).strip()
        for c in re.findall(r"<th[^>]*>(.*?)</th>", head.group(1) if head else "", re.S)
    ]
    return [c for c in cols if c not in ("Time", "Risk")]


def _plain_overview_labels(text: str) -> list[str]:
    """Beschriftungen des Uebersichtsblocks des ersten Ortes im Klartext."""
    lines = text.splitlines()
    sep = next(i for i, ln in enumerate(lines) if ln.startswith("-" * 50))
    labels = []
    for line in lines[sep + 2:]:
        if not line.strip():
            break
        if not line.startswith("   ") or ": " not in line:
            continue
        labels.append(line.strip().split(": ", 1)[0])
    return labels


def _tour_rows() -> list[dict]:
    """Eine Tour-Stundenzeile mit Taupunkt- UND Luftdruck-Spalte. Die
    Spaltenmenge der Tour ergibt sich allein aus den Schluesseln der Zeile
    (``helpers.visible_cols``, der Beschriftungsweg der Tour)."""
    return [{
        "time": "08", "temp": 14.0, "wind": 12.0, "gust": 22.0, "precip": 0.0,
        "dewpoint": 8.0, "pressure": 1013.0, "cape": 300.0,
    }]


# ===========================================================================
# AC-1 -- Nicht-Regression: die Stundentabelle bleibt englisch
# ===========================================================================


def test_compare_hour_table_keeps_the_english_short_forms():
    """AC-1: GIVEN der Nutzer oeffnet die Stundentabelle einer Vergleichs-Mail
    / WHEN er die Spaltenueberschriften ansieht / THEN steht dort weiterhin die
    englische Kurzform jeder Groesse -- und ausdruecklich NICHT der
    ausgeschriebene deutsche Name.

    Heute gruen und nach der Lieferung ebenso. Genau deshalb steht er hier:
    Uebersichts- und Stundentabelle werden von derselben Funktion beschriftet
    (``derive_row_labels``, compare_html.py:425). Ohne diesen Nachweis faellt
    es niemandem auf, wenn die Umstellung der Uebersicht auf die
    ausgeschriebenen Namen auch den Stundenkopf trifft.
    """
    html = render_compare_html(
        _result(),
        enabled_metrics=resolve_enabled_metrics(ALL_OVERVIEW_SELECTION),
        hourly_metrics=[m["key"] for m in HOUR_METRICS],
    )
    header = _html_hour_header(html)

    assert header, "Keine Stundentabelle in der Vergleichs-Mail gefunden."
    assert header[0] == "Zeit"
    assert header[1:] == [get_metric(m["metric_id"]).col_label for m in HOUR_METRICS], (
        "Der Spaltenkopf der Stundentabelle ist nicht mehr die englische "
        f"Kurzform des Registers: {header}"
    )
    # Gegenprobe: kein Kopf traegt den ausgeschriebenen Namen. Groessen, deren
    # Kurzform woertlich der ausgeschriebene Name IST ("Wind"), bleiben aussen
    # vor -- bei ihnen ist der Unterschied nicht beobachtbar.
    ausgeschrieben = {
        get_metric(m["metric_id"]).label_de for m in HOUR_METRICS
        if get_metric(m["metric_id"]).label_de != get_metric(m["metric_id"]).col_label
    }
    assert not (set(header) & ausgeschrieben), (
        "Ausgeschriebene deutsche Namen im Stundenkopf -- die Umstellung der "
        f"Uebersichtstabelle ist auf die Stundentabelle durchgeschlagen: "
        f"{sorted(set(header) & ausgeschrieben)}"
    )
    for kurz in ("Temp", "Gust", "Rain", "Thdr", "Visib", "Cloud"):
        assert kurz in header, f"Kurzform '{kurz}' fehlt im Stundenkopf: {header}"


def test_tour_hour_table_keeps_the_english_short_forms():
    """AC-1 (zweiter Mail-Typ): dieselbe Aussage fuer die Tour-Stundentabelle.

    Der Tour-Pfad ist vollstaendig getrennt (``helpers.visible_cols`` ->
    ``metric_catalog.get_col_defs``), liest aber dieselbe Registerspalte -- er
    muss von der Umstellung der Vergleichs-Uebersicht unberuehrt bleiben."""
    html = _render_html_table(_tour_rows(), friendly_keys=set())
    header = _tour_hour_header(html)

    assert header, f"Keine Spaltenkoepfe in der Tour-Stundentabelle: {html[:200]}"
    for kurz, ausgeschrieben in (
        ("Temp", "Temperatur"), ("Wind", "Wind"), ("Gust", "Böen"),
        ("Rain", "Niederschlag"), ("CAPE", "Gewitterenergie (CAPE)"),
    ):
        assert kurz in header, f"Kurzform '{kurz}' fehlt im Tour-Stundenkopf: {header}"
        if ausgeschrieben != kurz:
            assert ausgeschrieben not in header, (
                f"Ausgeschriebener Name '{ausgeschrieben}' im Tour-Stundenkopf "
                f"-- die Tour-Stundentabelle bleibt bei der Kurzform: {header}"
            )


# ===========================================================================
# AC-2 -- zwei schlecht gewaehlte Kurzformen werden korrigiert
# ===========================================================================


def test_dewpoint_and_pressure_short_forms_name_the_quantity():
    """AC-2 (Registerebene): der Taupunkt heisst "Dew" (nicht "Cond°", das
    beschrieb keine Groesse) und der Luftdruck "Press" (nicht "hPa", das war
    die Einheit)."""
    assert get_metric("dewpoint").col_label == "Dew"
    assert get_metric("pressure").col_label == "Press"


def test_compare_hour_table_shows_dew_and_press():
    """AC-2: GIVEN eine Vergleichs-Mail zeigt Taupunkt- und Luftdruck-Spalte im
    Stundenverlauf / WHEN die Spaltenueberschriften gerendert werden / THEN
    heissen sie "Dew" und "Press"."""
    html = render_compare_html(
        _result(),
        enabled_metrics=resolve_enabled_metrics(["temp_max_c"]),
        hourly_metrics=["t2m_c", "dewpoint_c", "pressure_msl_hpa"],
    )

    assert _html_hour_header(html) == ["Zeit", "Temp", "Dew", "Press"], (
        f"Taupunkt-/Luftdruck-Spalte falsch beschriftet: {_html_hour_header(html)}"
    )


def test_tour_hour_table_shows_dew_and_press():
    """AC-2 (zweiter Mail-Typ): dieselben zwei Spalten in der Tour-Mail. Das
    ist gewollt -- ein schlechtes Kuerzel ist in beiden Mails schlecht."""
    header = _tour_hour_header(_render_html_table(_tour_rows(), friendly_keys=set()))

    assert "Dew" in header and "Press" in header, (
        f"Tour-Stundenkopf zeigt nicht 'Dew'/'Press': {header}"
    )
    assert "Cond°" not in header and "hPa" not in header, (
        f"Die alten Kuerzel stehen weiterhin im Tour-Stundenkopf: {header}"
    )


# ===========================================================================
# AC-3 -- Uebersichtstabelle: ausgeschriebener deutscher Name,
#         im HTML-Teil UND im Klartext-Teil derselben Mail
# ===========================================================================


def test_overview_rows_show_the_written_out_german_names():
    """AC-3 (HTML-Teil): GIVEN ein Nutzer liest die Uebersichtstabelle einer
    Vergleichs-Mail / WHEN er die Zeilenbeschriftungen ansieht / THEN steht
    dort der ausgeschriebene deutsche Name der Wettergroesse statt der
    englischen Kurzform."""
    html = render_compare_html(
        _result(), enabled_metrics=resolve_enabled_metrics(ALL_OVERVIEW_SELECTION),
    )

    assert _html_overview_labels(html) == EXPECTED_OVERVIEW_LABELS, (
        "Die Uebersichtstabelle zeigt nicht die ausgeschriebenen deutschen "
        f"Registernamen: {_html_overview_labels(html)}"
    )


def test_plaintext_overview_shows_the_same_german_names_as_the_html_part():
    """AC-3 (Klartext-Teil derselben Mail): dieselbe Beschriftung Zeile fuer
    Zeile. Der Pflicht-Pruefer liest nur den HTML-Teil -- ohne diesen Nachweis
    bliebe ein Fix, der nur den HTML-Pfad trifft, unbemerkt."""
    result = _result()
    enabled = resolve_enabled_metrics(ALL_OVERVIEW_SELECTION)

    html_labels = _html_overview_labels(render_compare_html(result, enabled_metrics=enabled))
    plain_labels = _plain_overview_labels(
        render_comparison_text(result, enabled_metrics=enabled)
    )

    assert plain_labels == EXPECTED_OVERVIEW_LABELS_PLAIN, (
        f"Klartext-Uebersicht zeigt nicht die deutschen Namen: {plain_labels}"
    )
    assert html_labels[1:] == plain_labels, (
        f"HTML- und Klartext-Teil derselben Mail weichen voneinander ab -- "
        f"HTML: {html_labels[1:]}, Klartext: {plain_labels}"
    )


# ===========================================================================
# AC-4 -- zwei Auswertungen derselben Groesse: deutsche Ergaenzung
# ===========================================================================


def test_single_evaluation_shows_the_plain_german_name():
    """AC-4 (Gegenprobe): ist nur EINE Auswertung sichtbar, braucht die Zeile
    keine Unterscheidung -- sie zeigt den blanken deutschen Namen."""
    result = _result()

    nur_max = _html_overview_labels(
        render_compare_html(result, enabled_metrics=resolve_enabled_metrics(["temp_max_c"]))
    )
    nur_min = _html_overview_labels(
        render_compare_html(result, enabled_metrics=resolve_enabled_metrics(["temp_min_c"]))
    )

    assert nur_max == ["Amtliche Warnungen", "Temperatur"], nur_max
    assert nur_min == ["Amtliche Warnungen", "Temperatur"], nur_min


def test_two_evaluations_of_the_same_quantity_get_the_german_evaluation_word():
    """AC-4: GIVEN Temperatur-Maximum und -Minimum (bzw. gefuehlte Temperatur)
    sind gleichzeitig sichtbar / WHEN die Uebersicht gerendert wird / THEN
    tragen beide Zeilen eine vollstaendig deutsche, unterscheidbare
    Bezeichnung -- nicht die gekuerzte Form mit rohem Auswertungscode
    ("Temp max")."""
    result = _result()
    enabled = resolve_enabled_metrics([
        "temp_max_c", "temp_min_c", "wind_chill_min_c", "wind_chill_max_c",
    ])

    labels = _html_overview_labels(render_compare_html(result, enabled_metrics=enabled))

    assert labels == [
        "Amtliche Warnungen",
        "Temperatur Maximum", "Temperatur Minimum",
        "Gefühlte Temperatur Minimum", "Gefühlte Temperatur Maximum",
    ], labels


# ===========================================================================
# AC-5 -- entfallen mit Issue #1585
#
# Der frühere `test_cape_column_keeps_its_international_short_form` bewachte
# die Schreibweise der CAPE-Spalte in Stunden- und Uebersichtstabelle des
# Ortsvergleichs. CAPE ist seit #1585 zentral nicht mehr waehlbar und
# erscheint in keiner der beiden Tabellen mehr -- der Test hat keinen
# Gegenstand mehr. Die Abwesenheit selbst ist in
# tests/tdd/test_cape_not_selectable.py geprueft.
# ===========================================================================


# ===========================================================================
# AC-8 -- die deutschen Namen kommen aus dem Register, nicht aus einer Kopie
# ===========================================================================


def test_overview_label_follows_the_register_not_a_typed_copy(monkeypatch):
    """AC-8: GIVEN die deutschen Uebersichtsnamen sind ausgeliefert / WHEN man
    den Registerwert EINER Testgroesse verstellt / THEN schlaegt das sichtbar
    in der gerenderten Uebersichtszeile durch -- im HTML- wie im Klartext-Teil.

    Das prueft die HERKUNFT, nicht den Wert: schriebe der Renderer die Namen
    ab (naheliegend waere ``comparison._PLAIN_ROWS``, das dieselben Woerter
    als Telegram/SMS-Vokabular fuehrt), bliebe die Zeile beim alten Wort und
    dieser Test rot.
    """
    original = get_metric("humidity")
    assert original.label_de == "Luftfeuchtigkeit", (
        "Vorbedingung: der Registername der Testgroesse hat sich geaendert -- "
        f"die Gegenprobe unten prueft dann das Falsche ({original.label_de})."
    )

    result = _result()
    enabled = resolve_enabled_metrics(["humidity_avg_pct"])

    # Gegenprobe zuerst: unveraendertes Register -> Registername in der Zeile.
    assert "Luftfeuchtigkeit" in _html_overview_labels(
        render_compare_html(result, enabled_metrics=enabled)
    )

    monkeypatch.setitem(
        mc._METRICS_BY_ID, "humidity",
        dataclasses.replace(original, label_de="Pruefname Feuchte"),
    )

    html_labels = _html_overview_labels(
        render_compare_html(result, enabled_metrics=enabled)
    )
    plain_labels = _plain_overview_labels(
        render_comparison_text(result, enabled_metrics=enabled)
    )

    assert "Pruefname Feuchte" in html_labels, (
        "Der verstellte Registername kommt im HTML-Teil nicht an -- die "
        f"Beschriftung stammt aus einer zweiten, getippten Liste: {html_labels}"
    )
    assert "Pruefname Feuchte" in plain_labels, (
        "Der verstellte Registername kommt im Klartext-Teil nicht an -- der "
        f"Klartext fuehrt eine eigene Namenskopie: {plain_labels}"
    )


# ===========================================================================
# Adversary F001 -- eine unbekannte Namensform scheitert LAUT
# ===========================================================================


def test_unknown_name_form_fails_loudly_instead_of_silently_shortening():
    """F001: GIVEN jemand ruft die Beschriftungs-Ableitung mit einer
    Namensform auf, die es nicht gibt (Tippfehler wie "Long"/"lang", ein
    kuenftiges drittes Format) / WHEN die Funktion laeuft / THEN bricht sie mit
    einem ``ValueError`` ab, der den uebergebenen Wert nennt -- sie faellt NICHT
    still auf die englische Kurzform zurueck.

    Warum das zaehlt, obwohl beide heutigen Aufrufer Literale uebergeben: ein
    stiller Rueckfall ist hier unsichtbar. Die Mail wuerde erzeugt, zugestellt
    und plausibel aussehen -- nur waere die ganze Uebersichtstabelle wieder
    englisch beschriftet, also genau die Regression, die #1453 behebt. Kein
    Test und kein Pflicht-Pruefer wuerde anschlagen, weil "Kurzform in der
    Uebersicht" formal gueltiges Markup ist. Dasselbe Muster hat in dieser
    Sitzung bereits dreimal echte Fehler verdeckt (#1450 build_token_line ohne
    profile, render_compare_html ohne hourly_metrics, _visible_hour_metrics
    (None) = "alle Spalten").
    """
    zeilen = [{"key": "temp_max", "metric_id": "temperature", "aggregation": "max"}]

    # Gegenprobe zuerst: die beiden ZULAESSIGEN Formen funktionieren weiter und
    # liefern nachweislich VERSCHIEDENE Beschriftungen. Ohne diese Haelfte
    # bliebe der Test auch dann gruen, wenn die Funktion gar nichts mehr kann.
    assert derive_row_labels(zeilen, form="short")[0]["label"] == "Temp"
    assert derive_row_labels(zeilen, form="long")[0]["label"] == "Temperatur"

    for unbekannt in ("Long", "lang", "kurz", "deutsch", "", "SHORT"):
        with pytest.raises(ValueError) as exc:
            derive_row_labels(zeilen, form=unbekannt)
        assert repr(unbekannt) in str(exc.value), (
            f"Die Fehlermeldung muss den uebergebenen Wert {unbekannt!r} "
            f"nennen, sonst sucht der Aufrufer im Dunkeln: {exc.value}"
        )
