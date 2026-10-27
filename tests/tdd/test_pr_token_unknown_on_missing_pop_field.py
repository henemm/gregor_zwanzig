"""PR-Token (SMS/Telegram/Premium-SMS): `?` statt `-` bei isoliert
fehlendem `pop_pct` OHNE segmentweite Datenluecke (#1794).

Spec: docs/specs/modules/fix_1794_arome_precip_prob_null.md

`compute_has_gap()` (`src/services/notification_service.py:356-389`) prueft
nur, ob fuer jede erwartete Fensterstunde ueberhaupt ein Datenpunkt
existiert -- NICHT, ob ein einzelnes Feld (`pop_pct`) innerhalb eines
vorhandenen Datenpunkts `None` ist. Eine vollstaendige Stundenreihe, bei der
jeder Datenpunkt `pop_pct=None` traegt (z.B. weil der WEATHER-05b-Fallback
fuer dieses Feld fehlgeschlagen ist), ergibt also `has_data_gap=False`,
waehrend `pop_hourly` (gebaut in `sms_trip.py:321-323`, Filter
`pop is not None and pop > 0`) leer bleibt. `_gap_or()`
(`src/output/tokens/builder.py:156-166`) macht "-" nur zu "?", wenn
`has_gap=True` -- hier bleibt es faelschlich bei "-" ("geprueft, kein
Regen"), obwohl in Wahrheit keine Daten vorlagen.

TDD RED: AC-1 muss mit dem heutigen Code fehlschlagen (PR zeigt `PR:-`/`PR-`
statt `PR?`).

Keine Mocks, keine Dateiinhalt-Checks. Reale Fixtures (echte
`ForecastDataPoint`/`SegmentWeatherData`-Objekte, wie sie der echte
Versandpfad erzeugt), reale Aufrufe von `compute_has_gap()` und
`SMSTripFormatter().format_sms()`.
"""
from __future__ import annotations

from datetime import datetime, timezone
from zoneinfo import ZoneInfo

from src.app.models import (
    ForecastDataPoint,
    ForecastMeta,
    GPXPoint,
    NormalizedTimeseries,
    Provider,
    SegmentWeatherData,
    SegmentWeatherSummary,
    ThunderLevel,
    TripSegment,
)
from src.output.renderers.sms_trip import SMSTripFormatter
from src.output.tokens.dto import MetricSpec
from src.services.notification_service import compute_has_gap

_YEAR, _MONTH, _DAY = 2026, 7, 20
_TZ = ZoneInfo("UTC")


def _dp_pop_none(hour: int) -> ForecastDataPoint:
    """Ein Stunden-Datenpunkt wie bei einem WEATHER-05b-Fallback-Fehlschlag:
    alle uebrigen Felder vorhanden, NUR `pop_pct` ist `None` (nicht 0 --
    0 waere ein echter Messwert)."""
    return ForecastDataPoint(
        ts=datetime(_YEAR, _MONTH, _DAY, hour, 0, tzinfo=timezone.utc),
        t2m_c=15.0,
        wind10m_kmh=5.0,
        gust_kmh=5.0,
        precip_1h_mm=0.0,
        pop_pct=None,
        cloud_total_pct=50,
        thunder_level=ThunderLevel.NONE,
        humidity_pct=55,
    )


def _dp_pop_zero(hour: int) -> ForecastDataPoint:
    """Wie `_dp_pop_none()`, aber mit einem ECHTEN Messwert `pop_pct=0` --
    das Gegenstueck fuer ein GEMISCHTES Fenster (Adversary-Finding F001):
    mindestens eine Stunde mit belegtem `pop_pct`, Rest weiterhin `None`."""
    return ForecastDataPoint(
        ts=datetime(_YEAR, _MONTH, _DAY, hour, 0, tzinfo=timezone.utc),
        t2m_c=15.0,
        wind10m_kmh=5.0,
        gust_kmh=5.0,
        precip_1h_mm=0.0,
        pop_pct=0,
        cloud_total_pct=50,
        thunder_level=ThunderLevel.NONE,
        humidity_pct=55,
    )


def _meta() -> ForecastMeta:
    return ForecastMeta(
        provider=Provider.OPENMETEO,
        model="test",
        run=datetime(_YEAR, _MONTH, _DAY, 0, 0, tzinfo=timezone.utc),
        grid_res_km=1.0,
        interp="point_grid",
    )


def _trip_segment(start_h: int, end_h: int) -> TripSegment:
    return TripSegment(
        segment_id=1,
        start_point=GPXPoint(lat=42.22, lon=9.07, elevation_m=1791.0),
        end_point=GPXPoint(lat=42.25, lon=9.10, elevation_m=1850.0),
        start_time=datetime(_YEAR, _MONTH, _DAY, start_h, 0, tzinfo=timezone.utc),
        end_time=datetime(_YEAR, _MONTH, _DAY, end_h, 0, tzinfo=timezone.utc),
        duration_hours=float(end_h - start_h),
        distance_km=8.0,
        ascent_m=200.0,
        descent_m=0.0,
    )


def _segment_all_pop_missing(start_h: int = 9, end_h: int = 17) -> SegmentWeatherData:
    """Vollstaendiges, fehlerfreies Segment mit 24h-Zeitreihe -- JEDER
    Datenpunkt vorhanden (kein Segment-/Provider-Fehler), aber `pop_pct`
    durchgaengig `None`. Das ist der Fall, den `compute_has_gap()` nicht
    erkennt (es prueft nur Datenpunkt-EXISTENZ, keine Feld-Vollstaendigkeit)."""
    data = [_dp_pop_none(h) for h in range(0, 24)]
    ts = NormalizedTimeseries(meta=_meta(), data=data)
    return SegmentWeatherData(
        segment=_trip_segment(start_h, end_h),
        timeseries=ts,
        aggregated=SegmentWeatherSummary(
            temp_min_c=10.0,
            temp_max_c=20.0,
            wind_max_kmh=15.0,
            gust_max_kmh=25.0,
            precip_sum_mm=0.0,
            thunder_level_max=ThunderLevel.NONE,
        ),
        fetched_at=datetime(_YEAR, _MONTH, _DAY, 6, 0, tzinfo=timezone.utc),
        provider="openmeteo",
    )


def _segment_mixed_pop(start_h: int = 9, end_h: int = 17,
                        real_value_hour: int = 12) -> SegmentWeatherData:
    """Vollstaendiges Segment wie `_segment_all_pop_missing()`, aber mit EINER
    Stunde (`real_value_hour`, Default 12 -- innerhalb des 04-19-Uhr-Tages-
    fensters, `DAY_WINDOW_START_HOUR`/`DAY_WINDOW_END_HOUR`) mit echtem
    `pop_pct=0` statt `None`. Adversary-Finding F001 (Mutation `all()`->
    `any()` in `sms_trip.py` blieb unbemerkt): dieses GEMISCHTE Fenster
    grenzt "durchgaengig None" (`all(...)`) scharf von "irgendeine None"
    (`any(...)`) ab -- die Spec-Bedingung ist ausdruecklich "durchgaengig"."""
    data = [
        _dp_pop_zero(h) if h == real_value_hour else _dp_pop_none(h)
        for h in range(0, 24)
    ]
    ts = NormalizedTimeseries(meta=_meta(), data=data)
    return SegmentWeatherData(
        segment=_trip_segment(start_h, end_h),
        timeseries=ts,
        aggregated=SegmentWeatherSummary(
            temp_min_c=10.0,
            temp_max_c=20.0,
            wind_max_kmh=15.0,
            gust_max_kmh=25.0,
            precip_sum_mm=0.0,
            thunder_level_max=ThunderLevel.NONE,
        ),
        fetched_at=datetime(_YEAR, _MONTH, _DAY, 6, 0, tzinfo=timezone.utc),
        provider="openmeteo",
    )


def _complete_night_weather(start_h: int = 17, end_h: int = 23) -> NormalizedTimeseries:
    """Vollstaendige (ereignislose) Nacht-Zeitreihe -- verhindert, dass eine
    unbeobachtete Ziel-Stunde nach Ankunft als zusaetzliche Luecken-Quelle
    in `compute_has_gap()` einfliesst (Issue #1331)."""
    data = [_dp_pop_none(h) for h in range(start_h, end_h + 1)]
    return NormalizedTimeseries(meta=_meta(), data=data)


# Abwahl aller Metriken ausser PR, damit die Assertions sich ausschliesslich
# auf das Pruefziel (Regenwahrscheinlichkeit) konzentrieren -- Vorbild:
# _TEMPERATURE_OFF/_NEW_14_OFF in test_sms_unknown_on_missing_data.py.
_ALL_EXCEPT_PR_OFF: list[MetricSpec] = [
    MetricSpec(symbol=sym, enabled=False)
    for sym in (
        "N", "L", "D", "FN", "FL", "FD", "WC",
        "HU", "DP", "WD", "CP", "PT", "CT", "CL", "CM", "CH", "VS", "SU",
        "UV", "HP", "FZ",
    )
]


def _format(segments: list[SegmentWeatherData], night_weather: NormalizedTimeseries) -> tuple[str, bool]:
    """Baut die SMS ueber den echten Versandpfad (Issue #1331/#1334 F008:
    einziger Berechnungspunkt fuer die Luecke ist `compute_has_gap()`).
    Gibt (sms, has_gap) zurueck, damit der Test die Praemisse
    `has_gap is False` selbst verifizieren kann."""
    has_gap = compute_has_gap(segments, night_weather, _TZ)
    sms = SMSTripFormatter().format_sms(
        segments, stage_name="GR20", report_type="morning", tz=_TZ,
        night_weather=night_weather, has_gap=has_gap,
        disabled_specs=_ALL_EXCEPT_PR_OFF,
    )
    return sms, has_gap


class TestAC1PRTokenShowsUnknownOnIsolatedMissingPop:
    """AC-1 (Spec fix_1794_arome_precip_prob_null.md): ein vollstaendiges
    Segment (kein Provider-/Segment-Fehler, `has_data_gap=False`), dessen
    `pop_pct` durchgaengig `None` ist, muss `PR?` zeigen -- nicht `PR-`
    (das saehe nach "geprueft, kein Regen" aus, obwohl keine Daten vorlagen)."""

    def test_pr_token_shows_unknown_when_pop_missing_without_segment_gap(self):
        night = _complete_night_weather()
        segments = [_segment_all_pop_missing(start_h=9, end_h=17)]
        sms, has_gap = _format(segments, night)

        assert has_gap is False, (
            f"Testpraemisse verletzt: compute_has_gap() meldet eine "
            f"segmentweite Luecke, obwohl alle Datenpunkte vorhanden sind. "
            f"has_gap={has_gap}, SMS: {sms}"
        )
        assert "PR?" in sms, (
            f"Erwartet `PR?` (unbekannt -- pop_pct war in jeder Stunde "
            f"None, obwohl kein Segment-Fehler vorlag), stattdessen "
            f"faelschliche Entwarnung.\nSMS: {sms}"
        )
        assert "PR-" not in sms, (
            f"Fehl-Entwarnung `PR-` darf nicht erscheinen, wenn keine "
            f"einzige Regenwahrscheinlichkeits-Stichprobe vorlag.\nSMS: {sms}"
        )
        # Adversary-Finding F002 (MEDIUM): Spec-Claim "keine Seitenwirkung
        # auf andere Metriken" war ungetestet -- die `sym == "PR"`-
        # Restriktion in builder.py koennte entfernt werden, ohne dass ein
        # Test rot wird. Diese Fixture hat fuer R/W/G/TH unauffaellige,
        # reale Werte (precip=0.0, wind=5.0, gust=5.0, thunder=NONE) -- nur
        # `pop_pct` fehlt durchgaengig. Andere Symbole muessen daher bei
        # ihrer normalen Entwarnung `-` bleiben und duerfen NICHT auf `?`
        # kippen (Kreuzkontamination durch den `pop`-spezifischen Fehlbestand).
        # Tokenweise (nicht per Substring) geprueft, sonst matcht "R?" auch
        # innerhalb von "PR?" (Substring-Falle).
        sms_tokens = set(sms.split())
        for sym in ("R-", "W-", "G-", "TH:-"):
            assert sym in sms_tokens, (
                f"Erwartet Token `{sym}` (unveraendert, reale unauffaellige "
                f"Werte) -- die `pop_pct`-Datenluecke darf NICHT auf andere "
                f"Metriken uebergreifen.\nSMS: {sms}\nTokens: {sms_tokens}"
            )
        for sym in ("R?", "W?", "G?", "TH:?"):
            assert sym not in sms_tokens, (
                f"Seiteneffekt: Token `{sym}` darf nicht erscheinen -- nur "
                f"`PR` ist von der fehlenden `pop_pct`-Stichprobe betroffen, "
                f"nicht andere Metriken.\nSMS: {sms}\nTokens: {sms_tokens}"
            )


class TestPRTokenDistinguishesAllMissingFromPartiallyMissing:
    """Adversary-Finding F001 (LOW): die Spec-Bedingung "pop_pct in JEDER
    Stunde None" (`all(...)` in `sms_trip.py`) war an keiner Stelle von der
    schwaecheren Bedingung "mindestens eine Stunde fehlt" (`any(...)`)
    abgegrenzt -- eine Mutation `all()` -> `any()` blieb unbemerkt, weil
    die einzige Fixture (AC-1) durchgaengig `pop_pct=None` setzt und beide
    Bedingungen dort identisch `True` liefern.

    Dieser Test nutzt ein GEMISCHTES Fenster (eine Stunde mit echtem
    `pop_pct=0`, Rest `None`): hier liefert `all(...)` False (kein
    durchgaengiger Fehlbestand) und `any(...)` True -- die beiden
    Bedingungen fallen erstmals auseinander. `PR` muss weiterhin `-`
    zeigen (nicht `?`), weil nicht "durchgaengig" None vorliegt."""

    def test_pr_token_shows_dash_when_only_some_hours_have_missing_pop(self):
        night = _complete_night_weather()
        segments = [_segment_mixed_pop(start_h=9, end_h=17, real_value_hour=12)]
        sms, has_gap = _format(segments, night)

        assert has_gap is False, (
            f"Testpraemisse verletzt: compute_has_gap() meldet eine "
            f"segmentweite Luecke, obwohl alle Datenpunkte vorhanden sind. "
            f"has_gap={has_gap}, SMS: {sms}"
        )
        assert "PR-" in sms, (
            f"Erwartet `PR-` -- mindestens eine Stunde im Fenster hatte "
            f"einen echten `pop_pct`-Messwert (0 %), die Bedingung "
            f"'durchgaengig None' (Spec-Wortlaut) ist NICHT erfuellt. Ein "
            f"faelschliches `PR?` hier zeigt, dass die Erkennung bereits "
            f"bei EINER fehlenden Stunde ausloest (`any()` statt "
            f"`all()`).\nSMS: {sms}"
        )
        assert "PR?" not in sms, (
            f"`PR?` darf nicht erscheinen, wenn eine echte "
            f"Regenwahrscheinlichkeits-Stichprobe im Fenster vorlag.\n"
            f"SMS: {sms}"
        )
