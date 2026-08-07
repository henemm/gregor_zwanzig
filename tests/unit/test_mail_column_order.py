"""Die im Editor eingestellte Metrik-Reihenfolge wirkt in der Briefing-Mail.

Spec: docs/specs/modules/fix_1575_mail_column_order.md (Issue #1575, Scheibe 1).

Gemessen wird am WIRKORT -- der gerenderten Mail (``format_email``), nicht an
der Sortierfunktion isoliert. Lehre aus #1457: eine Zusicherung, die nur dort
geprueft wird, wo der Code steht, kann erfuellt und wirkungslos zugleich sein.

Der Nutzer zieht im Tab "Wetter-Metriken" eine Groesse nach vorn; der Abschnitt
sagt ihm "links -> rechts in der Email-Tabelle". Genau das pruefen diese Tests.
"""
from datetime import datetime, timezone

from app.metric_catalog import (
    build_default_display_config, get_col_defs, get_metric,
)
from app.models import (
    ForecastDataPoint,
    ForecastMeta,
    GPXPoint,
    MetricConfig,
    NormalizedTimeseries,
    Provider,
    SegmentWeatherData,
    SegmentWeatherSummary,
    ThunderLevel,
    TripSegment,
)
from output.renderers.channel_layout import render_for_channel
from output.renderers.trip_report import TripReportFormatter

# Spalten, die der Renderer unabhaengig von der Metrik-Auswahl setzt.
_FRAME_COLUMNS = {"Time", "Risk"}


def _segment() -> SegmentWeatherData:
    segment = TripSegment(
        segment_id=1,
        start_point=GPXPoint(lat=47.0, lon=11.0, elevation_m=1500),
        end_point=GPXPoint(lat=47.1, lon=11.1, elevation_m=1800),
        start_time=datetime(2026, 8, 29, 8, 0, tzinfo=timezone.utc),
        end_time=datetime(2026, 8, 29, 10, 0, tzinfo=timezone.utc),
        duration_hours=2.0, distance_km=5.0, ascent_m=300, descent_m=0,
    )
    summary = SegmentWeatherSummary(
        temp_min_c=12.0, temp_max_c=18.0, temp_avg_c=15.0,
        wind_max_kmh=25.0, gust_max_kmh=40.0, precip_sum_mm=5.0,
    )
    meta = ForecastMeta(
        provider=Provider.OPENMETEO, model="test",
        run=datetime(2026, 8, 29, 0, 0, tzinfo=timezone.utc),
        grid_res_km=2.5, interp="point_grid",
    )
    data = [
        ForecastDataPoint(
            ts=datetime(2026, 8, 29, h, 0, tzinfo=timezone.utc),
            t2m_c=12.0 + h, wind10m_kmh=15.0 + h, gust_kmh=25.0 + h,
            precip_1h_mm=0.5, cloud_total_pct=50,
            thunder_level=ThunderLevel.NONE, wind_chill_c=8.0 + h,
        )
        for h in range(0, 24)
    ]
    return SegmentWeatherData(
        segment=segment,
        timeseries=NormalizedTimeseries(data=data, meta=meta),
        aggregated=summary,
        fetched_at=datetime.now(timezone.utc),
        provider="test",
    )


def _label_of(metric_id: str) -> str:
    """Metrik-ID -> Spaltenbeschriftung, wie sie in der Mail steht."""
    col_key = get_metric(metric_id).col_key
    for key, label, _ in get_col_defs():
        if key == col_key:
            return label
    raise AssertionError(f"keine Spaltenbeschriftung fuer {metric_id}")


def _mail_columns(config) -> list[str]:
    """Spaltenbeschriftungen der HTML-Stundentabelle, links -> rechts."""
    import re

    report = TripReportFormatter().format_email(
        [_segment()], "Reihenfolge Trip", "morning", display_config=config,
    )
    head = re.search(r"<thead><tr>(.*?)</tr></thead>", report.email_html, re.S)
    assert head, "Stundentabelle ohne Kopfzeile gerendert"
    cells = [
        re.sub(r"<[^>]+>", "", th).strip()
        for th in re.findall(r"<th[^>]*>.*?</th>", head.group(1), re.S)
    ]
    return [c for c in cells if c not in _FRAME_COLUMNS]


def _place(config, metric_ids: list[str], bucket: str = "primary") -> None:
    """Setzt Bucket + Position genau so, wie der Editor es beim Ziehen tut."""
    by_id = {mc.metric_id: mc for mc in config.metrics}
    for position, metric_id in enumerate(metric_ids):
        by_id[metric_id].bucket = bucket
        by_id[metric_id].order = position


# --- AC-1 -----------------------------------------------------------------

def test_configured_order_drives_mail_columns():
    """AC-1: Eine nach vorn gezogene Groesse steht in der Mail auch vorn."""
    config = build_default_display_config()
    active = [mc.metric_id for mc in config.metrics if mc.enabled]
    # Nutzer zieht die letzte Groesse auf Position 1.
    _place(config, [active[-1]] + active[:-1])

    columns = _mail_columns(config)
    moved_to_front = _label_of(active[-1])

    assert columns[0] == moved_to_front, (
        f"Die nach vorn gezogene Groesse '{moved_to_front}' muesste die erste "
        f"Spalte sein, die Mail zeigt aber: {columns}"
    )


# --- AC-2 -----------------------------------------------------------------

def test_swapping_two_positions_swaps_mail_columns():
    """AC-2: Werden zwei Positionen getauscht, tauschen auch die Spalten."""
    order = ["temperature", "wind", "gust", "precipitation", "cloud_total"]

    config_a = build_default_display_config()
    _place(config_a, order)
    columns_a = _mail_columns(config_a)

    config_b = build_default_display_config()
    _place(config_b, ["wind", "temperature"] + order[2:])
    columns_b = _mail_columns(config_b)

    temp, wind = _label_of("temperature"), _label_of("wind")
    assert columns_a.index(temp) < columns_a.index(wind)
    assert columns_b.index(wind) < columns_b.index(temp), (
        f"Nach dem Tausch muesste '{wind}' vor '{temp}' stehen, "
        f"die Mail zeigt aber: {columns_b}"
    )


# --- AC-3 -----------------------------------------------------------------

def test_legacy_config_without_order_keeps_catalog_order():
    """AC-3: Altbestand (alle order = 0) behaelt exakt seine Reihenfolge.

    Die Sortierung muss stabil sein -- sonst wuerde sie fuer Bestands-Trips,
    die nie eine Reihenfolge gesetzt haben, eine neue erfinden.

    Der Sollwert ist der GEMESSENE Vorzustand (2026-08-07 gegen 9a932ef), nicht
    die ideale Katalog-Reihenfolge: 'TmpMin' steht hinten, weil
    `temperature_cold.selectable = False` es aus `_col_order` fallen laesst und
    der `remaining`-Zweig es anhaengt (html.py:1024/1680). Diese Abweichung ist
    Bestand und gehoert zu Scheibe 2 -- dieser Test haelt sie fest, damit die
    Sortierung sie nicht versehentlich mitverschiebt.
    """
    config = build_default_display_config()
    assert all(mc.order == 0 for mc in config.metrics if mc.enabled), (
        "Vorbedingung verletzt: die Vorgabe-Konfiguration traegt bereits "
        "Positionen, dieser Test prueft dann nicht mehr den Altbestand"
    )

    baseline = [
        "Temp", "Feels", "Wind", "Gust", "Rain",
        "Thdr", "SnowL", "Cloud", "Sun", "TmpMin",
    ]
    assert _mail_columns(config) == baseline, (
        "Altbestand-Reihenfolge veraendert -- ein Trip ohne je gesetzte "
        "Positionen darf seine Mail nicht anders sortiert bekommen"
    )


# --- AC-4 -----------------------------------------------------------------

def test_primary_metrics_come_before_secondary():
    """AC-4: primary steht vollstaendig vor secondary.

    Beide Buckets zaehlen ihre Positionen ab 0 -- eine Sortierung allein nach
    `order` wuerde sie verschraenken (Wind[0] neben Temperatur[0]).
    """
    config = build_default_display_config()
    _place(config, ["wind", "gust"], bucket="primary")
    _place(config, ["temperature", "precipitation"], bucket="secondary")
    for mc in config.metrics:
        if mc.metric_id not in {"wind", "gust", "temperature", "precipitation"}:
            mc.enabled = False

    columns = _mail_columns(config)
    last_primary = max(columns.index(_label_of(m)) for m in ("wind", "gust"))
    first_secondary = min(
        columns.index(_label_of(m)) for m in ("temperature", "precipitation")
    )

    assert last_primary < first_secondary, (
        f"primary-Groessen muessen vor secondary stehen, Mail zeigt: {columns}"
    )


# --- AC-5 -----------------------------------------------------------------

def test_telegram_layout_is_not_disturbed():
    """AC-5: Telegram/Ortsvergleich sortieren selbst -- nichts darf sich dort
    verschieben, egal in welcher Array-Reihenfolge die Liste ankommt."""
    # ALLE aktiven Groessen bekommen eine eigene Position -- sonst pruefte der
    # Test nur, wie Gleichstaende (lauter order = 0) aufgeloest werden, und
    # nicht die Zusicherung.
    def _fully_placed():
        cfg = build_default_display_config()
        active = [mc.metric_id for mc in cfg.metrics if mc.enabled]
        _place(cfg, ["wind", "temperature", "gust", "precipitation"]
               + [m for m in active
                  if m not in {"wind", "temperature", "gust", "precipitation"}])
        return cfg

    before = render_for_channel("telegram", _fully_placed(), "morning").table_columns

    scrambled = _fully_placed()
    scrambled.metrics = list(reversed(scrambled.metrics))

    after = render_for_channel("telegram", scrambled, "morning").table_columns

    assert before == after, (
        "Die Telegram-Spalten haengen an der Array-Reihenfolge statt an der "
        f"eingestellten Position: {before} vs. {after}"
    )


# --- AC-6 -----------------------------------------------------------------

def test_channel_layout_keeps_selection_and_applies_order():
    """AC-6: Bei kanal-eigenen Listen aendert sich nur die Reihenfolge."""
    config = build_default_display_config()
    # Array-Reihenfolge (temperature, wind, gust) weicht bewusst von den
    # Positionen ab -- sonst waere der Test auch ohne Sortierung gruen.
    config.per_channel_layouts = {
        "email": [
            MetricConfig(metric_id="temperature", enabled=True, bucket="primary", order=2),
            MetricConfig(metric_id="wind", enabled=True, bucket="primary", order=0),
            MetricConfig(metric_id="gust", enabled=True, bucket="primary", order=1),
        ],
    }

    columns = _mail_columns(config)

    assert columns == [_label_of("wind"), _label_of("gust"), _label_of("temperature")], (
        f"Kanal-Liste: Auswahl oder Reihenfolge stimmt nicht -- Mail zeigt {columns}"
    )


def test_per_report_layout_applies_order():
    """AC-6, hoechste Kaskadenebene: auch der Pro-Report-Override sortiert.

    Ohne diesen Test bliebe Ebene 1 (`per_report_layouts`, #434) unsortiert,
    ohne dass ein Test rot wird -- aufgedeckt durch die Mutations-Gegenprobe.
    """
    config = build_default_display_config()
    config.per_report_layouts = {
        "morning": {
            "email": [
                MetricConfig(metric_id="temperature", enabled=True, bucket="primary", order=2),
                MetricConfig(metric_id="wind", enabled=True, bucket="primary", order=0),
                MetricConfig(metric_id="gust", enabled=True, bucket="primary", order=1),
            ],
        },
    }

    columns = _mail_columns(config)

    assert columns == [_label_of("wind"), _label_of("gust"), _label_of("temperature")], (
        f"Pro-Report-Liste ignoriert die eingestellte Position -- Mail zeigt {columns}"
    )


def test_unknown_bucket_never_jumps_ahead_of_primary():
    """Ein unbekannter Bucket-Wert sortiert ans ENDE, nie nach vorn.

    Bestandsdaten koennen einen Bucket tragen, den der Editor heute nicht mehr
    schreibt. So ein Wert darf die bewusst gesetzten Positionen nicht
    ueberholen -- sonst verschoebe ein Altdaten-Artefakt die Mail-Spalten.
    """
    config = build_default_display_config()
    _place(config, ["wind", "gust"], bucket="primary")
    for mc in config.metrics:
        if mc.metric_id == "temperature":
            mc.bucket = "unbekannt"
            mc.order = 0
        elif mc.metric_id not in {"wind", "gust"}:
            mc.enabled = False

    columns = _mail_columns(config)

    assert columns.index(_label_of("temperature")) > columns.index(_label_of("gust")), (
        f"Groesse mit unbekanntem Bucket ueberholt die gesetzten Positionen: {columns}"
    )
