"""TDD RED — Issue #1475 Scheibe S5a (Epic #1419), AC-5/AC-7/AC-8: der
Hagel-Hinweis erscheint rein deskriptiv neben der Gewitterstufe -- in der
Trip-Mail (Klartext + HTML) UND im Telegram-`GEWITTER`-Kommando, ueber EINEN
geteilten Formatierungshelfer (`output.metric_format.format_hail_note`,
Spec Implementation Details Abschnitt 5), niemals als Ratschlagstext
(ADR-0007).

RED-Ursache (heute): `SegmentWeatherSummary`/`ForecastDataPoint` kennen kein
Feld `hail_flag` -> jede Fixture-Konstruktion wirft `TypeError`.
`output.metric_format.format_hail_note` existiert nicht.

Keine Mocks/patch()/MagicMock. `monkeypatch.setattr(modul, name, ...)` wird
NUR fuer die DRY-Strukturpruefung (AC-7) genutzt, um zu beobachten, ob zwei
Aufrufer tatsaechlich dieselbe Funktion aufrufen -- analog zum bereits im
Projekt etablierten Muster, eine echte Quelle (z.B. `BASE_HOST`) fuer einen
Test umzubiegen, nicht um Verhalten vorzutaeuschen.
"""
from __future__ import annotations

import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

from app.loader import save_trip  # noqa: E402
from app.metric_catalog import build_default_display_config  # noqa: E402
from app.models import (  # noqa: E402
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
from app.trip import Stage, Trip, Waypoint  # noqa: E402

_TZ = ZoneInfo("Europe/Berlin")

_VERBOTENE_WORTLISTE = ("Schutz suchen", "Vorsicht", "meiden")


def _segment_mit_hail(hail_flag) -> SegmentWeatherData:
    """Ein-Segment-Etappe, Gewitterstufe HIGH (damit der Hagel-Hinweis
    ueberhaupt 'neben der Gewitterstufe' Sinn ergibt), variables hail_flag."""
    seg = TripSegment(
        segment_id=1,
        start_point=GPXPoint(lat=42.0, lon=9.0, elevation_m=400.0),
        end_point=GPXPoint(lat=42.1, lon=9.1, elevation_m=900.0),
        start_time=datetime(2026, 8, 4, 6, 0, tzinfo=timezone.utc),
        end_time=datetime(2026, 8, 4, 14, 0, tzinfo=timezone.utc),
        duration_hours=8.0, distance_km=12.0, ascent_m=500.0, descent_m=0.0,
    )
    data = [ForecastDataPoint(
        ts=datetime(2026, 8, 4, h, 0, tzinfo=timezone.utc),
        t2m_c=15.0, wind10m_kmh=5.0, gust_kmh=10.0, precip_1h_mm=0.0,
        cloud_total_pct=50, thunder_level=ThunderLevel.HIGH, humidity_pct=55,
        hail_flag=hail_flag if h == 12 else None,
    ) for h in range(6, 15)]
    ts = NormalizedTimeseries(
        meta=ForecastMeta(provider=Provider.OPENMETEO, model="test", grid_res_km=1.0),
        data=data,
    )
    return SegmentWeatherData(
        segment=seg, timeseries=ts,
        aggregated=SegmentWeatherSummary(
            temp_min_c=10.0, temp_max_c=20.0, wind_max_kmh=10.0,
            gust_max_kmh=15.0, precip_sum_mm=0.0,
            thunder_level_max=ThunderLevel.HIGH, hail_flag=hail_flag,
        ),
        fetched_at=datetime.now(timezone.utc), provider="openmeteo",
    )


def _render_html(dc, hail_flag) -> str:
    from output.renderers.email.html import render_html

    return render_html(
        segments=[_segment_mit_hail(hail_flag)], seg_tables=[[]],
        trip_name="Test-Trip", report_type="evening", dc=dc, night_rows=[],
        night_weather=None, changes=None, stage_name="Test-Etappe",
        stage_stats=None, multi_day_trend=None, compact_summary=None,
        tz=_TZ, friendly_keys=set(),
    )


def _render_plain(dc, hail_flag) -> str:
    from output.renderers.email.plain import render_plain

    return render_plain(
        segments=[_segment_mit_hail(hail_flag)], seg_tables=[[]],
        trip_name="Test-Trip", report_type="evening", dc=dc, night_rows=[],
        night_weather=None, changes=None, stage_name="Test-Etappe",
        stage_stats=None, multi_day_trend=None, compact_summary=None,
        tz=_TZ, friendly_keys=set(),
    )


# =============================================================================
# AC-5 — E-Mail (Klartext + HTML): Hinweis NUR bei der True-Etappe
# =============================================================================

def test_ac5_email_html_zeigt_hagel_hinweis_nur_bei_true_etappe():
    dc = build_default_display_config()
    html_true = _render_html(dc, True)
    html_unbekannt = _render_html(dc, None)

    assert "Hagel: ja" in html_true, (
        "Die HTML-Mail einer Etappe mit hail_flag=True muss den Hinweis "
        "'Hagel: ja' zeigen"
    )
    assert "Hagel: ja" not in html_unbekannt, (
        "Eine Etappe mit hail_flag=None (unbekannt) darf KEINEN "
        "Hagel-Zusatztext zeigen (kein Rauschen)"
    )


def test_ac5_email_plain_zeigt_hagel_hinweis_nur_bei_true_etappe():
    dc = build_default_display_config()
    plain_true = _render_plain(dc, True)
    plain_unbekannt = _render_plain(dc, None)

    assert "Hagel: ja" in plain_true, (
        "Die Klartext-Mail einer Etappe mit hail_flag=True muss den Hinweis "
        "'Hagel: ja' zeigen"
    )
    assert "Hagel: ja" not in plain_unbekannt, (
        "Eine Etappe mit hail_flag=None (unbekannt) darf KEINEN "
        "Hagel-Zusatztext zeigen (kein Rauschen)"
    )


# =============================================================================
# AC-7 — GEWITTER-Kommando (Telegram/Mail-Antwort), DRY ueber denselben Helfer
# =============================================================================

_WP_LAT, _WP_LON = 42.0, 9.0
_TRIP_ID = "hail-flag-gewitter-kommando"
_TRIP_NAME = "Hagel-Kommando-Tour"
_USER_ID = "default"


def _make_trip(day: datetime) -> Trip:
    return Trip(
        id=_TRIP_ID, name=_TRIP_NAME,
        stages=[Stage(
            id="S1", name="Heute-Etappe", date=day.date(),
            waypoints=[Waypoint(id="W1", name="Start", lat=_WP_LAT, lon=_WP_LON, elevation_m=900)],
        )],
    )


@pytest.fixture
def gewitter_kommando_env(tmp_path: Path, monkeypatch):
    from services.weather_snapshot import WeatherSnapshotService

    redirect = lambda user_id="default": tmp_path / user_id
    monkeypatch.setattr("app.loader.get_data_dir", redirect)
    monkeypatch.setattr("services.trip_command_processor.get_data_dir", redirect)

    now = datetime.now(tz=timezone.utc)
    save_trip(_make_trip(now), _USER_ID)
    WeatherSnapshotService(_USER_ID).save(
        _TRIP_ID, [_segment_mit_hail(True)], now.date(),
    )
    return now


def test_ac7_gewitter_kommando_zeigt_denselben_hagel_hinweis(gewitter_kommando_env):
    """AC-7: `_fmt_gewitter()` (der Handler des `GEWITTER`-Kommandos) zeigt
    fuer einen Tag mit aggregiertem hail_flag=True denselben Hinweis-Text
    wie die E-Mail-Renderer ('Hagel: ja')."""
    from services.trip_command_processor import InboundMessage, TripCommandProcessor

    msg = InboundMessage(
        channel="telegram", trip_name=_TRIP_NAME, body="GEWITTER",
        sender="4711", received_at=gewitter_kommando_env, user_id=_USER_ID,
    )
    result = TripCommandProcessor().process(msg)

    assert result.success is True, (
        f"GEWITTER-Kommando muss antworten, nicht scheitern: "
        f"{result.confirmation_body!r}"
    )
    assert "Hagel: ja" in result.confirmation_body, (
        f"Erwartet den Hagel-Hinweis 'Hagel: ja' in der GEWITTER-Antwort, "
        f"bekam: {result.confirmation_body!r}"
    )


def test_ac7_mail_renderer_und_gewitter_kommando_rufen_denselben_helfer(
    gewitter_kommando_env, monkeypatch,
):
    """AC-7 struktureller DRY-Nachweis (#1481): wird der geteilte Helfer
    `output.metric_format.format_hail_note` auf einen Sentinel-Text
    umgebogen, MUESSEN sowohl die HTML-Mail-Rendering-Seite als auch die
    `GEWITTER`-Kommando-Antwort diesen Sentinel zeigen -- ein Duplikat
    (zweiter, eigener Textbaustein) wuerde den Sentinel an mindestens einer
    Stelle NICHT zeigen.
    """
    from output import metric_format
    from services.trip_command_processor import InboundMessage, TripCommandProcessor

    sentinel = "SENTINEL-HAGEL-1475-DRY-PROBE"
    monkeypatch.setattr(
        metric_format, "format_hail_note",
        lambda flag: sentinel if flag else None, raising=False,
    )

    dc = build_default_display_config()
    html = _render_html(dc, True)
    assert sentinel in html, (
        "Der HTML-Mail-Renderer zeigt den Sentinel nicht -- er ruft "
        "format_hail_note() nicht auf (oder haelt eine eigene Kopie)"
    )

    msg = InboundMessage(
        channel="telegram", trip_name=_TRIP_NAME, body="GEWITTER",
        sender="4711", received_at=gewitter_kommando_env, user_id=_USER_ID,
    )
    result = TripCommandProcessor().process(msg)
    assert sentinel in (result.confirmation_body or ""), (
        "Die GEWITTER-Kommando-Antwort zeigt den Sentinel nicht -- "
        "_fmt_gewitter() ruft format_hail_note() nicht auf (oder haelt eine "
        "eigene Kopie, #1481 DRY-Verstoss)"
    )


# =============================================================================
# AC-8 — keine Handlungsempfehlung (ADR-0007) in irgendeinem der drei Kanaele
# =============================================================================

def test_ac8_kein_ratschlagstext_in_mail_und_telegram_antwort(
    gewitter_kommando_env,
):
    dc = build_default_display_config()
    html_true = _render_html(dc, True)
    plain_true = _render_plain(dc, True)

    from services.trip_command_processor import InboundMessage, TripCommandProcessor
    msg = InboundMessage(
        channel="telegram", trip_name=_TRIP_NAME, body="GEWITTER",
        sender="4711", received_at=gewitter_kommando_env, user_id=_USER_ID,
    )
    telegram_text = TripCommandProcessor().process(msg).confirmation_body or ""

    for kanal_name, text in (
        ("HTML-Mail", html_true), ("Klartext-Mail", plain_true),
        ("GEWITTER-Kommando", telegram_text),
    ):
        for verbotenes_wort in _VERBOTENE_WORTLISTE:
            assert verbotenes_wort not in text, (
                f"{kanal_name} enthaelt Ratschlagstext {verbotenes_wort!r} -- "
                f"ADR-0007 verbietet Handlungsempfehlungen (nur Fakt, kein "
                f"Rat), AC-8"
            )
