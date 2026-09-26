"""TDD RED — Issue #2205, AC-1 / AC-2: Hagel im Stufen-Aenderungsalarm
(E-Mail + Telegram).

SPEC: docs/specs/modules/fix_2205_hagel_im_text_wettercode_bleibt.md

Wettercode 95/96/99 bleibt auf Stufe "hoch" (PO 15.09.). Die Hagel-
Unterscheidung (96/99 = mit Hagel, 95 = ohne) muss deshalb im TEXT des
Stufen-Aenderungsalarms stehen -- heute fehlt sie dort (`AlertEvent` hat kein
Hagelfeld, `alert/project.py` reicht nichts durch, `alert/render.py` schreibt
nichts).

Aufrufkette (keine Mocks, kein Netz, kein Versand) -- dieselbe wie
`NotificationService.send_deviation_alert()` -> `_dispatch_alert_message()`
(notification_service.py:1584-1589):

    Stundenreihe (nur `wmo_code` gesetzt)
      -> OpenMeteoProvider._derive_thunder_fields()      (Produktiv-Uebersetzung
                                                          Code -> thunder_level/hail_flag)
      -> WeatherMetricsService.compute_basis_metrics()   (Aggregat inkl. hail_flag)
      -> WeatherChangeDetectionService.detect_changes()  (Stufenaenderung mittel->hoch)
      -> alert.project.to_alert_message()
      -> alert.render.render_email() / render_telegram()

Geprueft wird am GERENDERTEN Text, der erwartete Wortlaut kommt aus der
einzigen Wortlautquelle `metric_format.format_hail_note(True)`.
"""
from __future__ import annotations

import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

from app.models import (  # noqa: E402
    ForecastDataPoint,
    ForecastMeta,
    GPXPoint,
    NormalizedTimeseries,
    Provider,
    SegmentWeatherData,
    ThunderLevel,
    TripSegment,
)
from output.metric_format import format_hail_note  # noqa: E402
from output.renderers.alert.project import to_alert_message  # noqa: E402
from output.renderers.alert.render import (  # noqa: E402
    render_email,
    render_sms,
    render_telegram,
)
from providers.openmeteo import OpenMeteoProvider  # noqa: E402
from services.weather_change_detection import (  # noqa: E402
    WeatherChangeDetectionService,
)
from services.weather_metrics import WeatherMetricsService  # noqa: E402

ALERT_TZ = ZoneInfo("Europe/Vienna")
# Wettercode ohne Gewitter (bedeckt) fuer alle uebrigen Stunden.
CODE_OHNE_GEWITTER = 3
HAGEL_WORT = "Hagel"


def _now() -> datetime:
    """Referenzzeit je Aufruf (NICHT auf Modulebene): der Korridor-Waechter
    liest die Wanduhr selbst und filtert auf das aktive Etappenfenster."""
    return datetime.now(timezone.utc).replace(minute=0, second=0, microsecond=0)


def _segment(now: datetime) -> TripSegment:
    return TripSegment(
        segment_id="1",
        start_point=GPXPoint(lat=47.0, lon=11.0, elevation_m=1000,
                             distance_from_start_km=0.0),
        end_point=GPXPoint(lat=47.1, lon=11.1, elevation_m=1500,
                           distance_from_start_km=8.0),
        start_time=now - timedelta(hours=1),
        end_time=now + timedelta(hours=4),
        duration_hours=5.0,
        distance_km=8.0,
        ascent_m=500,
        descent_m=0,
    )


def segment_weather(spitzen_code: int | None) -> SegmentWeatherData:
    """Etappe mit sechs Stunden; die dritte Stunde traegt `spitzen_code`
    (95/96/99 -> Spitzenstunde auf "hoch"), alle anderen Code 3.

    Nur `wmo_code` wird gesetzt -- `thunder_level`/`hail_flag` leitet der
    Produktivpfad `OpenMeteoProvider._derive_thunder_fields()` ab, damit die
    Fixture nie von der echten 95/96/99-Uebersetzung abweicht. `None` =
    eine Reihe ganz ohne Gewitterstunde.
    """
    now = _now()
    codes = [CODE_OHNE_GEWITTER] * 6
    if spitzen_code is not None:
        codes[2] = spitzen_code
    punkte = [
        ForecastDataPoint(ts=now + timedelta(hours=i - 1), t2m_c=15.0, wmo_code=c)
        for i, c in enumerate(codes)
    ]
    reihe = NormalizedTimeseries(
        meta=ForecastMeta(provider=Provider.OPENMETEO, model="icon_d2",
                          grid_res_km=2.0),
        data=punkte,
    )
    OpenMeteoProvider()._derive_thunder_fields(reihe)
    aggregat = WeatherMetricsService().compute_basis_metrics(reihe, tz=None)
    return SegmentWeatherData(
        segment=_segment(now), timeseries=reihe, aggregated=aggregat,
        fetched_at=now, provider="openmeteo",
    )


def stufen_aenderungsalarm(spitzen_code: int):
    """Stufenaenderung mittel -> hoch fuer eine Etappe, deren Spitzenstunde
    `spitzen_code` traegt -> kanonische `AlertMessage` (echte Erkennung +
    echte Projektion)."""
    frisch = segment_weather(spitzen_code)
    alt = segment_weather(None)
    alt.aggregated.thunder_level_max = ThunderLevel.MED
    assert frisch.aggregated.thunder_level_max == ThunderLevel.HIGH, (
        "Fixture-Fehler: Spitzenstunde muss auf 'hoch' stehen"
    )
    detektor = WeatherChangeDetectionService(
        thresholds={"thunder_level_max": 1.0},
        ordinal_levels={"thunder_level_max": "sensibel"},
    )
    changes = detektor.detect_changes(alt, frisch, include_absolute=False)
    assert [c.metric for c in changes] == ["thunder_level_max"], (
        f"Fixture-Fehler: genau eine Gewitter-Stufenaenderung erwartet, {changes!r}"
    )
    return to_alert_message(
        changes, [frisch], "Test-Trip", tz=ALERT_TZ, stand_at="10:00",
    )


def gerenderte_texte(msg) -> dict[str, str]:
    """Dieselben Render-Aufrufe wie `_dispatch_alert_message()`."""
    html, plain = render_email(msg)
    return {
        "email_html": html,
        "email_plain": plain,
        "telegram": render_telegram(msg),
        "sms_body": render_sms(msg),
    }


def _assert_gewitter_alarm_gerendert(kanal: str, text: str) -> None:
    """Anker gegen leeres Gruen: ueberhaupt ein Gewitter-Stufenalarm."""
    assert "Gewitter" in text, f"{kanal}: kein Gewitter-Alarmtext gerendert:\n{text}"
    assert "mittel" in text and "hoch" in text, (
        f"{kanal}: Stufenangabe mittel->hoch fehlt:\n{text}"
    )


@pytest.mark.parametrize("kanal", ["email_html", "email_plain", "telegram"])
@pytest.mark.parametrize("spitzen_code", [96, 99])
def test_ac1_stufenalarm_mit_hagelcode_nennt_hagel_in_mail_und_telegram(
    spitzen_code: int, kanal: str,
) -> None:
    """AC-1.

    GIVEN eine Stufenaenderung mittel -> hoch, deren Spitzenstunde
          Wettercode 96 bzw. 99 traegt (hail_flag=True aus dem Produktivpfad)
    WHEN  der Stufen-Aenderungsalarm fuer E-Mail (HTML + Plain) und Telegram
          gerendert wird
    THEN  enthaelt der Text die bestehende Hagelaussage aus
          `format_hail_note(True)`.
    """
    erwartet = format_hail_note(True)
    assert erwartet, "format_hail_note(True) muss einen Wortlaut liefern"

    text = gerenderte_texte(stufen_aenderungsalarm(spitzen_code))[kanal]

    _assert_gewitter_alarm_gerendert(kanal, text)
    assert erwartet in text, (
        f"{kanal}: Hagelaussage {erwartet!r} fehlt im Stufenalarm "
        f"(Spitzenstunde Code {spitzen_code}):\n{text}"
    )


@pytest.mark.parametrize("kanal", ["email_html", "email_plain", "telegram"])
def test_ac2_stufenalarm_mit_code_95_nennt_keinen_hagel(kanal: str) -> None:
    """AC-2.

    GIVEN eine Stufenaenderung mittel -> hoch, deren Spitzenstunde
          ausschliesslich Wettercode 95 traegt (kein Hagel-Code)
    WHEN  derselbe Stufen-Aenderungsalarm fuer E-Mail und Telegram gerendert
          wird
    THEN  enthaelt der Text keine Hagelaussage -- bei gleichzeitig
          gerendertem Gewitter-Stufenalarm (kein leeres Gruen).
    """
    text = gerenderte_texte(stufen_aenderungsalarm(95))[kanal]

    _assert_gewitter_alarm_gerendert(kanal, text)
    assert HAGEL_WORT not in text, (
        f"{kanal}: Code 95 ist kein Hagel-Code, Text behauptet Hagel:\n{text}"
    )
