"""
Kurz-Zusammenfassung je Ort in der Vergleichs-Mail (#1278).

Kern-Schicht, deterministisch: keine Mocks, kein Netz, kein patch(). Alle
Wetterdaten sind echte ``ForecastDataPoint``-Objekte; die Trip-Referenzwerte
werden vom echten ``WeatherMetricsService`` bzw. vom echten
``CompactSummaryFormatter`` erzeugt (kein selbst ausgedachter Erwartungswert).

SPEC: docs/specs/modules/compare_location_summary.md v2.1

AC-Zuordnung siehe Docstring je Test.

Entwurfs-Entscheidung dieser Tests (bewusst implementierungs-agnostisch):
- Die Auswahl wird IMMER ueber ``resolve_enabled_metrics([<Frontend-IDs>])``
  gebildet — das ist der echte Nutzerpfad (Editor-Auswahl -> Renderer). Die
  Renderer-ID-Strings selbst sind laut Spec Implementierungsdetail und werden
  hier deshalb nirgends hart verdrahtet.
- Der Zusammenfassungs-Block wird ueber seine POSITION im HTML gefunden
  (zwischen dem Ende der UEBERSICHT-Tabelle und dem STUNDEN-Kopf) — die Spec
  legt keinen Marker/keine CSS-Klasse fest, wohl aber die Platzierung.
"""
from __future__ import annotations

import re
from datetime import date, datetime, timezone

import pytest

from app.models import (
    ForecastDataPoint,
    ForecastMeta,
    GPXPoint,
    MetricConfig,
    NormalizedTimeseries,
    Provider,
    SegmentWeatherData,
    ThunderLevel,
    TripSegment,
    UnifiedWeatherDisplayConfig,
)
from app.user import ComparisonResult, LocationResult, SavedLocation
from output.renderers.compact_summary import CompactSummaryFormatter
from output.renderers.compare_metric_ids import resolve_enabled_metrics
from output.renderers.comparison import render_comparison_text
from output.renderers.email.compare_html import render_compare_html
from services.weather_metrics import WeatherMetricsService

TARGET_DATE = date(2026, 7, 8)


# ---------------------------------------------------------------------------
# Fixtures (echte Objekte, deterministisch)
# ---------------------------------------------------------------------------

def _dp(hour: int, **overrides) -> ForecastDataPoint:
    """Eine Stunde der Referenz-Wetterlage.

    Wetterlage (bewusst so gewaehlt, dass jede der geprueften Groessen ein
    unterscheidbares Ergebnis liefert):
      - Temperatur steigt 8 -> 16 °C
      - trocken bis 12:00, dann Regen 13:00-15:00 (Summe 3.0 mm)
      - Gewitter (MED) 13:00 + 14:00
      - Sicht faellt waehrend des Regens auf 3000 m
      - UV-Spitze 6.0 um 12:00
      - Regenwahrscheinlichkeit-Spitze 70 %
    """
    rain = 1.0 if 13 <= hour <= 15 else 0.0
    defaults = dict(
        ts=datetime(2026, 7, 8, hour, 0, tzinfo=timezone.utc),
        t2m_c=float(8 + (hour - 9)),
        wind10m_kmh=20.0,
        wind_direction_deg=270,
        gust_kmh=25.0,
        precip_1h_mm=rain,
        cloud_total_pct=50,
        thunder_level=ThunderLevel.MED if hour in (13, 14) else ThunderLevel.NONE,
        pop_pct=70 if 13 <= hour <= 15 else 20,
        humidity_pct=65,
        uv_index=6.0 if hour == 12 else 3.0,
        visibility_m=3000 if 13 <= hour <= 15 else 20000,
        wind_chill_c=float(6 + (hour - 9)),
    )
    defaults.update(overrides)
    return ForecastDataPoint(**defaults)


def _hourly(**overrides) -> list[ForecastDataPoint]:
    return [_dp(h, **overrides) for h in range(9, 18)]


def _timeseries(hourly: list[ForecastDataPoint]) -> NormalizedTimeseries:
    meta = ForecastMeta(
        provider=Provider.OPENMETEO,
        model="test",
        run=datetime(2026, 7, 8, 0, 0, tzinfo=timezone.utc),
        grid_res_km=1.0,
        interp="point_grid",
    )
    return NormalizedTimeseries(meta=meta, data=hourly)


def _trip_summary(hourly: list[ForecastDataPoint]):
    """Trip-Pfad-Aggregat aus denselben Stundendaten (echter Service)."""
    return WeatherMetricsService().compute_basis_metrics(_timeseries(hourly))


def _saved_location(name: str, loc_id: str | None = None) -> SavedLocation:
    return SavedLocation(
        id=loc_id or re.sub(r"\W+", "_", name.lower()),
        name=name,
        lat=39.76,
        lon=2.71,
        elevation_m=200,
    )


def _location_result(
    name: str,
    hourly: list[ForecastDataPoint] | None = None,
    *,
    error: str | None = None,
) -> LocationResult:
    """LocationResult mit echten Stundendaten.

    Bewusst werden hier NUR die heute existierenden Tages-Felder gesetzt. Die
    fuenf Groessen aus #1285 (Regen/Gewitter/UV/Sicht/Regenwahrscheinlichkeit)
    kommen ausschliesslich aus ``hourly_data`` — genau das ist das ``Given``
    von AC-15 ("Given ein Ort im Vergleich hat stuendliche ... Werte in
    hourly_data").
    """
    if error is not None:
        return LocationResult(location=_saved_location(name), error=error)
    hourly = hourly if hourly is not None else _hourly()
    if not hourly:
        return LocationResult(location=_saved_location(name), hourly_data=[])
    s = _trip_summary(hourly)
    return LocationResult(
        location=_saved_location(name),
        score=50,
        temp_min=s.temp_min_c,
        temp_max=s.temp_max_c,
        wind_max=s.wind_max_kmh,
        gust_max=s.gust_max_kmh,
        cloud_avg=s.cloud_avg_pct,
        sunny_hours=4,
        hourly_data=hourly,
    )


def _comparison_result(locations: list[LocationResult]) -> ComparisonResult:
    return ComparisonResult(
        locations=locations,
        time_window=(0, 23),
        target_date=TARGET_DATE,
        created_at=datetime(2026, 7, 8, 4, 1),
    )


def _trip_sentence(
    hourly: list[ForecastDataPoint],
    stage_name: str,
    metric_ids: list[str],
) -> str:
    """Erzeugt den Satz ueber den ECHTEN Trip-Pfad (CompactSummaryFormatter)."""
    ts = _timeseries(hourly)
    summary = WeatherMetricsService().compute_basis_metrics(ts)
    seg = TripSegment(
        segment_id=1,
        start_point=GPXPoint(lat=39.75, lon=2.65, elevation_m=100.0),
        end_point=GPXPoint(lat=39.76, lon=2.66, elevation_m=200.0),
        start_time=datetime(2026, 7, 8, hourly[0].ts.hour, 0, tzinfo=timezone.utc),
        end_time=datetime(2026, 7, 8, hourly[-1].ts.hour + 1, 0, tzinfo=timezone.utc),
        duration_hours=float(hourly[-1].ts.hour + 1 - hourly[0].ts.hour),
        distance_km=5.0,
        ascent_m=200.0,
        descent_m=100.0,
    )
    swd = SegmentWeatherData(
        segment=seg,
        timeseries=ts,
        aggregated=summary,
        fetched_at=datetime(2026, 7, 8, 4, 0, tzinfo=timezone.utc),
        provider="openmeteo",
    )
    dc = UnifiedWeatherDisplayConfig(
        trip_id="ref",
        metrics=[
            MetricConfig(metric_id=m, enabled=True, aggregations=["max"], use_friendly_format=True)
            for m in metric_ids
        ],
    )
    return CompactSummaryFormatter().format_stage_summary([swd], stage_name, dc)


# ---------------------------------------------------------------------------
# Block-Lokalisierung (Position statt Marker — s. Modul-Docstring)
# ---------------------------------------------------------------------------

def _summary_region(html: str) -> str:
    """HTML zwischen dem Ende der UEBERSICHT-Tabelle und dem STUNDEN-Kopf.

    Genau dort verlangt AC-2 den Zusammenfassungs-Block. Heute ist dieser
    Bereich leer (nur Whitespace/schliessende Divs).
    """
    table_start = html.index("min-width:760px")
    marker = "</tbody></table>"
    table_end = html.index(marker, table_start) + len(marker)
    stunden = html.find("STUNDEN", table_end)
    return html[table_end:stunden] if stunden != -1 else html[table_end:]


def _plain_region(text: str) -> str:
    """Klartext vor dem STUNDENVERLAUF-Abschnitt (= Orts-Uebersicht + Block)."""
    idx = text.find("STUNDENVERLAUF")
    return text[:idx] if idx != -1 else text


# ===========================================================================
# AC-1 — geteilter Baustein
# ===========================================================================

def test_shared_formatter_used_by_both_contexts():
    """AC-1: Compare- und Trip-Zusammenfassung durchlaufen denselben
    Formatierungs-Baustein.

    Verhaltens-Nachweis statt Behauptung: Bei identischer Stundenliste muss
    der Vergleich WOERTLICH denselben Wetterteil erzeugen wie der
    CompactSummaryFormatter im Trip-Kontext. Geprueft wird mit Temperatur +
    Niederschlag — beide Zweige sind unabhaengig von ``use_friendly_format``,
    der Satz ist also eindeutig vorhersagbar. Der Regen-Zeitmuster-Anteil
    ("trocken, Regen ab 13:00") stammt aus der Trip-eigenen
    ``_find_rain_pattern``-Logik und laesst sich praktisch nicht zufaellig
    reproduzieren — erscheint er im Vergleich, lief derselbe Code.
    """
    hourly = _hourly()
    expected = _trip_sentence(hourly, "Sóller", ["temperature", "precipitation"])
    assert expected == "Sóller: 8–16°C, trocken, Regen ab 13:00"  # Trip-Pfad, aufgezeichnet

    result = _comparison_result([_location_result("Sóller", hourly)])
    enabled = resolve_enabled_metrics(["temp_max_c", "precip_sum_mm"])

    html = render_compare_html(result, enabled_metrics=enabled)
    region = _summary_region(html)

    assert expected in region, (
        "Vergleichs-Mail erzeugt den Ort-Satz nicht mit dem geteilten "
        f"Trip-Baustein. Erwartet: {expected!r}. Bereich unter der Matrix: {region!r}"
    )


# ===========================================================================
# AC-2 / AC-3 — Platzierung HTML + Klartext
# ===========================================================================

def test_html_summary_block_position():
    """AC-2: Je Ort mit Daten ein Satz zwischen UEBERSICHT-Tabelle und
    STUNDEN-Kopf."""
    hourly = _hourly()
    result = _comparison_result([
        _location_result("Andermatt", hourly),
        _location_result("Zermatt", hourly),
    ])
    enabled = resolve_enabled_metrics(["temp_max_c", "precip_sum_mm"])

    html = render_compare_html(result, enabled_metrics=enabled)
    region = _summary_region(html)

    for name in ("Andermatt", "Zermatt"):
        assert f"{name}: 8–16°C" in region, (
            f"Kein Zusammenfassungssatz fuer {name} zwischen Matrix und "
            f"STUNDEN-Kopf. Bereich: {region!r}"
        )


def test_plaintext_summary_block_position():
    """AC-3: Klartext enthaelt denselben Satz nach der Orts-Uebersicht und vor
    dem STUNDENVERLAUF-Abschnitt; Wortlaut deckungsgleich mit HTML."""
    hourly = _hourly()
    expected = _trip_sentence(hourly, "Sóller", ["temperature", "precipitation"])
    result = _comparison_result([_location_result("Sóller", hourly)])
    enabled = resolve_enabled_metrics(["temp_max_c", "precip_sum_mm"])

    text = render_comparison_text(result, enabled_metrics=enabled)

    assert expected in text, (
        f"Klartext-Vergleich enthaelt keinen Ort-Zusammenfassungssatz. "
        f"Erwartet: {expected!r}"
    )
    assert expected in _plain_region(text), (
        "Zusammenfassungssatz steht nicht vor dem STUNDENVERLAUF-Abschnitt."
    )

    html_region = _summary_region(render_compare_html(result, enabled_metrics=enabled))
    assert expected in html_region, "HTML- und Klartext-Wortlaut weichen ab."


# ===========================================================================
# AC-5 — Zusammenfassung folgt der Matrix-Auswahl
# ===========================================================================

def test_summary_respects_enabled_metrics_filter():
    """AC-5: Nur Temperatur + Wind gewaehlt -> Satz nennt keine Bewoelkung,
    obwohl die Wetterdaten Bewoelkung enthalten (cloud_total_pct=50)."""
    from src.output.metric_format import cloud_emoji

    hourly = _hourly()
    result = _comparison_result([_location_result("Sóller", hourly)])
    enabled = resolve_enabled_metrics(["temp_max_c", "wind_max_kmh"])

    region = _summary_region(render_compare_html(result, enabled_metrics=enabled))

    # Der Satz muss ueberhaupt da sein — sonst prueft der Rest nichts.
    assert "Sóller: 8–16°C" in region, (
        f"Kein Zusammenfassungssatz vorhanden. Bereich: {region!r}"
    )
    assert "20 km/h" in region, "Wind wurde gewaehlt, fehlt aber im Satz."
    assert "Wolken" not in region, "Wolken abgewaehlt, erscheinen aber im Satz."
    assert cloud_emoji(50) not in region, (
        "Wolken abgewaehlt, erscheinen aber als Emoji im Satz."
    )


# ===========================================================================
# AC-6 — Regen + Gewitter im Fliesstext, sobald gewaehlt
# ===========================================================================

def test_summary_includes_rain_and_thunder_when_selected():
    """AC-6: Regen und Gewitter gewaehlt + Wetterdaten geben Anlass -> beide
    Anteile stehen im Satz (keine Sonderregel)."""
    hourly = _hourly()
    result = _comparison_result([_location_result("Sóller", hourly)])
    enabled = resolve_enabled_metrics([
        "temp_max_c", "precip_sum_mm", "thunder_level_max",
    ])

    region = _summary_region(render_compare_html(result, enabled_metrics=enabled))

    assert "Regen ab 13:00" in region, (
        f"Regen gewaehlt, fehlt aber im Zusammenfassungssatz. Bereich: {region!r}"
    )
    assert re.search(r"(⚡|Gewitter) möglich 13:00–15:00", region), (
        f"Gewitter gewaehlt, fehlt aber im Zusammenfassungssatz. Bereich: {region!r}"
    )


# ===========================================================================
# AC-7 — gleiche Wetterlage, gleiche Zahlen wie im Trip
# ===========================================================================

def test_aggregate_matches_trip_path_same_hourly_data():
    """AC-7: Identische Stundendaten -> identische Aggregatwerte in Trip- und
    Vergleichs-Satz (Temperaturspanne, Regenmenge/-adjektiv, Windspitze,
    Gewitterfenster).

    Die Erwartungswerte kommen aus dem echten Trip-Pfad
    (``WeatherMetricsService.compute_basis_metrics``), nicht aus einer
    Wunschliste im Test.
    """
    hourly = _hourly()
    trip = _trip_summary(hourly)

    result = _comparison_result([_location_result("Sóller", hourly)])
    enabled = resolve_enabled_metrics([
        "temp_max_c", "wind_max_kmh", "precip_sum_mm", "thunder_level_max",
    ])
    region = _summary_region(render_compare_html(result, enabled_metrics=enabled))

    temp_token = f"{int(round(trip.temp_min_c))}–{int(round(trip.temp_max_c))}°C"
    wind_token = f"{int(round(trip.wind_max_kmh))} km/h"
    # Der Regen-Anteil kommt aus dem ECHTEN Trip-Pfad, nicht aus
    # `_precip_adjective(3.0)`: bei dieser Wetterlage (trockener Vormittag,
    # Regen ab 13:00) waehlt der Trip-Formatter den Zeitmuster-Zweig
    # ``starts_later`` (compact_summary.py:189) und gibt "trocken, Regen ab
    # 13:00" aus — das Mengen-Adjektiv erscheint dort bewusst NICHT. Auf
    # "mäßiger Regen" zu pruefen hiesse, vom Vergleich eine EIGENE Regen-Logik
    # zu verlangen — genau das Gegenteil von AC-1 (geteilter Baustein) und
    # unvereinbar mit dem aufgezeichneten Trip-Satz aus AC-11.
    rain_token = _trip_sentence(hourly, "X", ["precipitation"]).split(": ", 1)[1]
    assert trip.precip_sum_mm == 3.0  # Vorbedingung: Tagessumme wie erwartet

    assert temp_token in region, f"Temperaturspanne weicht vom Trip-Pfad ab: {region!r}"
    assert wind_token in region, f"Windspitze weicht vom Trip-Pfad ab: {region!r}"
    assert rain_token in region, f"Regenmenge weicht vom Trip-Pfad ab: {region!r}"
    assert trip.thunder_level_max is ThunderLevel.MED
    assert "13:00–15:00" in region, f"Gewitterfenster weicht vom Trip-Pfad ab: {region!r}"


# ===========================================================================
# AC-8 — Ortsname wird nicht wie ein Etappenname gekuerzt
# ===========================================================================

@pytest.mark.parametrize(
    "name",
    [
        "von Bergen nach Voss",  # trifft die Etappen-Kuerzungsregel
        "Sant Elm de la Serra de Tramuntana Mirador",  # > 40 Zeichen
    ],
)
def test_location_title_not_shortened_like_stage_name(name: str):
    """AC-8: Der Ort-Satz beginnt mit dem VOLLEN Ortsnamen — keine
    'X → Y'-Kuerzung, keine 40-Zeichen-Kappung.

    Gegenprobe, dass die Kuerzungsregel im Trip-Kontext ueberhaupt greifen
    wuerde (sonst waere der Test wertlos).
    """
    hourly = _hourly()
    if name.startswith("von "):
        assert "→" in _trip_sentence(hourly, name, ["temperature"]), (
            "Vorbedingung verletzt: Trip-Kuerzungsregel greift bei diesem "
            "Namen gar nicht, der Test wuerde nichts beweisen."
        )

    result = _comparison_result([_location_result(name, hourly)])
    enabled = resolve_enabled_metrics(["temp_max_c"])
    region = _summary_region(render_compare_html(result, enabled_metrics=enabled))

    assert f"{name}: " in region, (
        f"Ortsname wurde nicht vollstaendig uebernommen. Bereich: {region!r}"
    )
    assert "→" not in region, "Etappen-Kuerzungsregel wurde auf den Ortsnamen angewendet."


# ===========================================================================
# AC-9 — Fehler-/Leerfall erzeugt keinen Block
# ===========================================================================

def test_error_location_produces_no_empty_block():
    """AC-9: Ort mit Fehler taucht in der Zusammenfassungs-Sektion nicht auf —
    keine leere Zeile, kein Crash."""
    hourly = _hourly()
    result = _comparison_result([
        _location_result("Andermatt", hourly),
        _location_result("Bergen", error="Provider timeout"),
    ])
    enabled = resolve_enabled_metrics(["temp_max_c", "precip_sum_mm"])

    region = _summary_region(render_compare_html(result, enabled_metrics=enabled))

    assert "Andermatt: 8–16°C" in region, (
        f"Ort mit Daten fehlt in der Zusammenfassung. Bereich: {region!r}"
    )
    assert "Bergen" not in region, "Fehler-Ort erzeugt einen Zusammenfassungs-Eintrag."
    assert "Provider timeout" not in region


def test_empty_hourly_data_produces_no_empty_block():
    """AC-9: Ort ohne Stundendaten taucht in der Zusammenfassungs-Sektion
    nicht auf."""
    hourly = _hourly()
    result = _comparison_result([
        _location_result("Andermatt", hourly),
        _location_result("Chamonix", []),
    ])
    enabled = resolve_enabled_metrics(["temp_max_c", "precip_sum_mm"])

    region = _summary_region(render_compare_html(result, enabled_metrics=enabled))

    assert "Andermatt: 8–16°C" in region, (
        f"Ort mit Daten fehlt in der Zusammenfassung. Bereich: {region!r}"
    )
    assert "Chamonix" not in region, "Ort ohne Stundendaten erzeugt einen Eintrag."


# ===========================================================================
# AC-10 — alphabetische Reihenfolge, kein Score/Winner
# ===========================================================================

def test_summary_order_alphabetical_no_score():
    """AC-10: Orte in Score-Reihenfolge im Input -> Zusammenfassung ist
    alphabetisch, identisch zur Matrix-Kopfzeile."""
    hourly = _hourly()
    zermatt = _location_result("Zermatt", hourly)
    zermatt.score = 99
    andermatt = _location_result("Andermatt", hourly)
    andermatt.score = 10
    result = _comparison_result([zermatt, andermatt])  # nicht-alphabetisch
    enabled = resolve_enabled_metrics(["temp_max_c", "precip_sum_mm"])

    html = render_compare_html(result, enabled_metrics=enabled)
    region = _summary_region(html)

    assert "Andermatt: " in region and "Zermatt: " in region, (
        f"Nicht beide Orte in der Zusammenfassung. Bereich: {region!r}"
    )
    assert region.index("Andermatt: ") < region.index("Zermatt: "), (
        "Zusammenfassung ist nicht alphabetisch sortiert."
    )
    # deckungsgleich mit der Matrix-Kopfzeile darueber
    header = html[html.index("min-width:760px"):html.index("</thead>")]
    assert header.index("Andermatt") < header.index("Zermatt")


# ===========================================================================
# AC-11 — Trip-Regression (GRUEN by design, kein RED-Kandidat)
# ===========================================================================

def test_trip_summary_text_unchanged_byte_identical():
    """AC-11: Regressionsschutz — der Trip-Zusammenfassungstext bleibt
    zeichengleich.

    Der Erwartungswert ist eine VORHER (Commit d32bd0a5, vor Beginn dieser
    Arbeit) aufgezeichnete echte Ausgabe von
    ``CompactSummaryFormatter.format_stage_summary()``, kein ausgedachter Wert.
    Dieser Test ist absichtlich schon jetzt gruen und muss gruen bleiben.
    """
    hourly = _hourly()
    recorded = (
        "Sóller → Tossals Verds: 8–16°C, ⛅, trocken, Regen ab 13:00, "
        "mäßiger Wind 20 km/h, ⚡ möglich 13:00–15:00"
    )
    actual = _trip_sentence(
        hourly,
        "Tag 3: von Sóller nach Tossals Verds",
        ["temperature", "cloud_total", "precipitation", "rain_probability",
         "wind", "gust", "wind_direction", "thunder"],
    )
    assert actual == recorded, (
        "Trip-Zusammenfassung hat sich geaendert (Regression). "
        f"vorher: {recorded!r} / jetzt: {actual!r}"
    )


# ===========================================================================
# AC-12 — totes Zeitfenster im STUNDEN-Kopf
# ===========================================================================

def test_hourly_head_no_dead_time_window_string():
    """AC-12: Der STUNDEN-Kopf zeigt keine feste Uhrzeitangabe '09–16 Uhr'
    mehr (toter Rest des mit #1268 abgeschafften Zeitfensters)."""
    result = _comparison_result([_location_result("Sóller", _hourly())])

    html = render_compare_html(result)

    assert "09–16 Uhr" not in html, (
        "STUNDEN-Kopf behauptet weiterhin ein Zeitfenster 09–16 Uhr, obwohl "
        "die Bewertung seit #1268 ueber den ganzen Tag laeuft."
    )


# ===========================================================================
# AC-13 — keine Confidence im Satz
# ===========================================================================

def test_summary_never_contains_confidence():
    """AC-13: Confidence-Werte im Input erscheinen in keinem
    Zusammenfassungssatz (ADR-0005, Issue #710)."""
    hourly = _hourly(confidence_pct=55)
    assert all(dp.confidence_pct == 55 for dp in hourly)  # Vorbedingung

    result = _comparison_result([_location_result("Sóller", hourly)])
    enabled = resolve_enabled_metrics([
        "temp_max_c", "wind_max_kmh", "precip_sum_mm", "thunder_level_max",
        "cloud_avg_pct",
    ])
    region = _summary_region(render_compare_html(result, enabled_metrics=enabled))

    assert "Sóller: " in region, (
        f"Kein Zusammenfassungssatz vorhanden. Bereich: {region!r}"
    )
    for forbidden in ("onfidence", "onfidenz", "erlässlich", "erlaesslich", "Sicherheit"):
        assert forbidden not in region, (
            f"Verlaesslichkeits-Angabe {forbidden!r} im Zusammenfassungssatz: {region!r}"
        )
