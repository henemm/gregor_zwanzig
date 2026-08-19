"""Issue #1592 F003 (Adversary-Befund, Runde 1) — `cape_model_id` muss die
Etappen-Aggregation (`aggregate_stage()`) ueberleben.

SPEC: docs/specs/modules/fix_1592_s1_cape_modellschwelle.md Abschnitt 2 (C0)

`compute_extended_metrics()` befuellt `SegmentWeatherSummary.cape_model_id`
(Issue #1592 C0), aber `aggregate_stage()` (Level-2, Etappe aus mehreren
Segmenten) liest ausschliesslich `aggregation_config` als Fahrplan. Ohne
einen Eintrag `"cape_model_id": "agreement"` dort faellt das Feld beim
Zusammenfassen mehrerer Segmente STILLSCHWEIGEND heraus (generischer
`else: values[0]`-Fallback bei unbekannter Regel liefert zufaellig den
ERSTEN Rohwert -- kein Fehler, kein Test schlaegt an).

Warum das mehr als kosmetisch ist: C2 (RiskEngine) und C3 (Δ-Alarme) lesen
in ihren Folgescheiben `agg.cape_model_id` GENAU an dieser Stelle (nach der
Etappen-Aggregation). Bliebe der Verlust drin, wuerden beide Folgescheiben
STILL ueber den Abstain-Pfad laufen und ueberall abstinieren -- ohne dass
ein Test anschlaegt. Das ist exakt die Fehlerklasse ("leer != unbekannt",
#1492), die dieses Issue ueberhaupt erst behebt, nur eine Aggregationsstufe
tiefer.

Kern-Schicht, deterministisch, keine Mocks/patch()/MagicMock.
"""
from __future__ import annotations

from datetime import datetime, timezone

from app.models import (
    ForecastDataPoint,
    ForecastMeta,
    GPXPoint,
    NormalizedTimeseries,
    Provider,
    SegmentWeatherData,
    TripSegment,
)
from services.weather_metrics import WeatherMetricsService, aggregate_stage


def _segment_mit_herkunft(model: str, start_hour: int, cape_jkg: float) -> SegmentWeatherData:
    """Ein Segment, dessen `.aggregated` ueber den ECHTEN Trip-Pfad
    entsteht (`compute_basis_metrics` + `compute_extended_metrics`), nicht
    handgestrickt -- die Zusicherung soll den vollen Weg (Herkunft ->
    normalisierter Schluessel -> Segment-Aggregat) pruefen, nicht nur ein
    isoliertes DTO."""
    seg = TripSegment(
        segment_id=start_hour,
        start_point=GPXPoint(lat=42.22, lon=9.07, elevation_m=400.0),
        end_point=GPXPoint(lat=42.25, lon=9.10, elevation_m=900.0),
        start_time=datetime(2026, 8, 4, start_hour, 0, tzinfo=timezone.utc),
        end_time=datetime(2026, 8, 4, start_hour + 2, 0, tzinfo=timezone.utc),
        duration_hours=2.0, distance_km=5.0, ascent_m=100.0, descent_m=50.0,
    )
    ts = NormalizedTimeseries(
        meta=ForecastMeta(provider=Provider.METEOFRANCE, model=model, grid_res_km=1.3),
        data=[ForecastDataPoint(
            ts=datetime(2026, 8, 4, start_hour, 0, tzinfo=timezone.utc),
            t2m_c=15.0, cape_jkg=cape_jkg,
        )],
    )
    svc = WeatherMetricsService()
    basis = svc.compute_basis_metrics(ts, tz=None)
    aggregiert = svc.compute_extended_metrics(ts, basis)
    return SegmentWeatherData(
        segment=seg, timeseries=ts, aggregated=aggregiert,
        fetched_at=datetime.now(timezone.utc), provider="openmeteo",
    )


def test_cape_model_id_uebersteht_etappen_aggregation_bei_einheitlicher_herkunft():
    """Zwei Segmente derselben Etappe, BEIDE mit AROME-Herkunft (real
    ueber `compute_extended_metrics()` erzeugt, nicht handgestrickt) ->
    `aggregate_stage()` muss `cape_model_id == 'meteofrance_arome'`
    liefern.

    DIESER Test faengt die Mutation "Config-Zeile fehlt": entfernt man den
    Eintrag `"cape_model_id": "agreement"` aus dem `aggregation_config`-
    Dict in `compute_extended_metrics()`, wird das Feld beim Bau des
    Ergebnis-DTOs in `aggregate_stage()` gar nicht mehr gesetzt (der
    generische Loop kennt kein `cape_model_id` mehr) -- der Konstruktor-
    Default `None` bleibt stehen, und diese Zusicherung (`== 'meteofrance_
    arome'`) schlaegt fehl (manuell verifiziert, s. Bericht).

    Fuer die ZWEITE moegliche Mutation -- die Regel `"agreement"` existiert
    zwar im Dispatch, prueft aber nicht wirklich auf Uebereinstimmung
    (z. B. faellt sie mit `values[0]` statt eines Vergleichs auf den
    generischen Fallback zurueck) -- ist DIESER Test hier blind: zwei
    UEBEREINSTIMMENDE Segmente liefern bei `values[0]` zufaellig denselben
    (richtigen) Wert. Diese zweite Mutation faengt stattdessen
    `test_cape_model_id_wird_none_bei_uneinigkeit_zwischen_segmenten()`
    unten -- dort weichen die Segmente voneinander ab, und `values[0]`
    liefert dann faelschlich `"meteofrance_arome"` statt `None`."""
    segmente = [
        _segment_mit_herkunft("meteofrance_arome", 8, 840.0),
        _segment_mit_herkunft("meteofrance_arome", 10, 350.0),
    ]

    ergebnis = aggregate_stage(segmente)

    assert ergebnis.cape_model_id == "meteofrance_arome", (
        f"Etappen-Aggregat aus zwei AROME-Segmenten muss "
        f"cape_model_id == 'meteofrance_arome' tragen, erhalten "
        f"{ergebnis.cape_model_id!r}"
    )


def test_cape_model_id_wird_none_bei_uneinigkeit_zwischen_segmenten():
    """AC-Gegenprobe: ein Segment AROME, ein Segment ICON-D2 --
    unterschiedliche Modell-Herkunft in derselben Etappe (z. B. weil die
    Etappe eine Gebietsgrenze quert). Uneinigkeit MUSS `None` liefern,
    NICHT "irgendeine der beiden" -- sonst waere die spaeter (C2/C3)
    angewendete Schwelle vom zufaelligen `values[0]` abhaengig, nicht von
    einer tatsaechlich fuer BEIDE Segmente belegten Herkunft.

    DIESER Test faengt die Mutation "Regel dispatcht, prueft aber nicht
    wirklich": faellt die `"agreement"`-Regel (versehentlich oder durch
    eine kuenftige Verfaelschung) auf `values[0]` statt eines echten
    Uebereinstimmungs-Vergleichs zurueck, liefert sie hier faelschlich
    `"meteofrance_arome"` (den ersten Wert) statt `None` -- die
    UNTERSCHIEDLICHEN Segmente machen den Unterschied erst sichtbar. Die
    Mutation "Config-Zeile fehlt" (s. Test oben) faengt DIESER Test NICHT
    zuverlaessig: faellt das Feld komplett aus dem Ergebnis-DTO heraus,
    bleibt der Konstruktor-Default `None` stehen -- das sieht hier
    zufaellig identisch zum korrekten Ergebnis aus."""
    segmente = [
        _segment_mit_herkunft("meteofrance_arome", 8, 840.0),
        _segment_mit_herkunft("icon_d2", 10, 900.0),
    ]

    ergebnis = aggregate_stage(segmente)

    assert ergebnis.cape_model_id is None, (
        f"Etappen-Aggregat aus zwei Segmenten UNTERSCHIEDLICHER Modell-"
        f"Herkunft (meteofrance_arome, icon_d2) muss cape_model_id "
        f"None liefern (Uneinigkeit != 'irgendeine davon'), erhalten "
        f"{ergebnis.cape_model_id!r}"
    )
