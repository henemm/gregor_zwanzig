"""TDD RED -- Issue #2220 C5-63: Telegram-Drilldown-Ampelfarbe ist bandtreu.

``_BAND_EMOJI`` (``src/services/trip_command_processor.py:209``) widerspricht
heute seinem eigenen Bandnamen (``{"green": "⚪", "yellow": "🟢",
"orange": "🟡", "red": "🔴"}``) -- drei von vier Eintraegen zeigen die falsche
Farbe. AC-1 bis AC-3 pruefen, dass der Telegram-Drilldown bandtreu wird
(Zielskala A: NONE=🟢, LOW=🟡, MED=🟠, HIGH=🔴, kanonisch abgeleitet ueber
``thunder_ampel_band()``) und mit der Mail-Ampel (``_AMPEL_DOT_COLORS``)
uebereinstimmt.

Spec: docs/specs/modules/fix_2220_telegram_kommando_befunde.md
Kontext: docs/context/fix-2220-telegram-kommando-befunde.md

Kern-Schicht, deterministisch: keine Mocks/patch()/MagicMock, kein Netz.
Pfadregel #1409: der Pruefling wird relativ zur eigenen Testdatei aufgeloest.
"""
from __future__ import annotations

import re
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import pytest

import services.trip_command_processor as _tcp
from app.loader import save_trip
from app.models import (
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
from app.trip import Stage, Trip, Waypoint
from output.metric_format import thunder_ampel_band
from output.renderers.email.helpers import _ampel_dot_css
from services.trip_command_processor import CommandResult, InboundMessage, TripCommandProcessor
from services.weather_snapshot import WeatherSnapshotService

_BAUM = Path(__file__).resolve().parents[2]
_PRUEFLING = Path(_tcp.__file__).resolve()
assert _PRUEFLING.is_relative_to(_BAUM), (
    f"Pfadregel #1409 verletzt: der Pruefling liegt unter {_PRUEFLING}, "
    f"diese Testdatei aber unter {_BAUM}."
)

TODAY = date(2026, 9, 10)
RECEIVED_AT = datetime(2026, 9, 10, 8, 0, tzinfo=timezone.utc)
_TRIP_ID = "test-2220-gewitter-ampel"
_TRIP_NAME = "Bandtreu-Test-Tour"
_USER_ID = "default"

# Lokale Band->Symbol-Referenz fuer AC-2 -- bewusst NICHT aus `_BAND_EMOJI`
# kopiert, sonst prueft der Test nichts (Spec AC-2).
_ERWARTETES_SYMBOL = {"green": "🟢", "yellow": "🟡", "orange": "🟠", "red": "🔴"}
# Mail-Seite: Hex-Fuellfarbe -> Bandname (aus `_AMPEL_DOT_COLORS`, dort
# "nicht ändern" -- hier nur zur INTERPRETATION der echten Mail-Ausgabe).
_MAIL_HEX_TO_BAND = {
    "#15803d": "green", "#d69500": "yellow", "#d4530a": "orange", "#a8104a": "red",
}
_TELEGRAM_SYMBOL_TO_BAND = {v: k for k, v in _ERWARTETES_SYMBOL.items()}


def _make_trip() -> Trip:
    return Trip(
        id=_TRIP_ID,
        name=_TRIP_NAME,
        stages=[
            Stage(
                id="S1", name="Heute-Etappe", date=TODAY,
                waypoints=[Waypoint(id="W1", name="Start", lat=42.1, lon=9.0, elevation_m=800)],
            ),
        ],
    )


def _make_snapshot_segments(level: ThunderLevel) -> list[SegmentWeatherData]:
    """6 Stundenpunkte mit KONSTANTER Gewitterstufe -- der Drilldown fasst sie
    zu EINER Verlaufszeile zusammen (#2185 Wechselpunkt-Gruppierung)."""
    provider = Provider.OPENMETEO
    meta = ForecastMeta(provider=provider, model="test", grid_res_km=0.0)
    hourly_points = [
        ForecastDataPoint(
            ts=RECEIVED_AT + timedelta(hours=i),
            thunder_level=level, wind10m_kmh=20.0, precip_1h_mm=0.0,
        )
        for i in range(6)
    ]
    timeseries = NormalizedTimeseries(meta=meta, data=hourly_points)
    segment = TripSegment(
        segment_id="seg-2220",
        start_point=GPXPoint(lat=42.1, lon=9.0, elevation_m=800),
        end_point=GPXPoint(lat=42.2, lon=9.1, elevation_m=600),
        start_time=RECEIVED_AT, end_time=RECEIVED_AT + timedelta(hours=5),
        duration_hours=5.0, distance_km=8.0, ascent_m=100.0, descent_m=100.0,
    )
    summary = SegmentWeatherSummary(thunder_level_max=level, wind_max_kmh=20.0, precip_sum_mm=0.0)
    return [SegmentWeatherData(
        segment=segment, timeseries=timeseries, aggregated=summary,
        fetched_at=RECEIVED_AT, provider=provider.value,
    )]


@pytest.fixture
def env():
    """Legt Trip + Snapshot fuer eine Gewitterstufe an -- die Datenwurzel
    isoliert die projektweite autouse-Fixtur (tests/conftest.py)."""
    def _setup(level: ThunderLevel) -> None:
        save_trip(_make_trip(), _USER_ID)
        WeatherSnapshotService(_USER_ID).save(_TRIP_ID, _make_snapshot_segments(level), TODAY)
    return _setup


def _drilldown_gewitter(channel: str) -> CommandResult:
    msg = InboundMessage(
        channel=channel, trip_name=_TRIP_NAME, body="### query: dd_thunder_today",
        sender="test", received_at=RECEIVED_AT, user_id=_USER_ID,
    )
    return TripCommandProcessor().process(msg)


def _text_der_verlaufszeile(body: str) -> str:
    """Die Verlaufszeile ``HH:MM[-HH:MM]  EMOJI WORT`` -- extrahiert den
    Textteil nach dem doppelten Leerzeichen (``_format_drilldown``)."""
    zeilen = [ln for ln in body.splitlines() if re.match(r"^\d{2}:\d{2}", ln)]
    assert zeilen, f"Keine Verlaufszeile im Drilldown-Body:\n{body}"
    return zeilen[0].split("  ", 1)[1].strip()


# ═══════════════════════════ AC-1 ════════════════════════════════════════════


def test_ac1_drilldown_low_traegt_gelb_nicht_gruen(env):
    """AC-1: LOW ("leicht") traegt im Telegram-Drilldown 🟡, nicht 🟢."""
    env(ThunderLevel.LOW)
    ergebnis = _drilldown_gewitter("telegram")
    assert ergebnis.success is True, f"Erwartet success=True: {ergebnis.confirmation_body!r}"
    text = _text_der_verlaufszeile(ergebnis.confirmation_body)
    symbol, wort = text.split(" ", 1)
    assert wort == "leicht", f"Erwartetes Wort 'leicht', erhalten {wort!r}"
    assert symbol == "🟡", f"LOW zeigt {symbol!r}, erwartet 🟡 (nicht 🟢)"


# ═══════════════════════════ AC-2 ════════════════════════════════════════════


@pytest.mark.parametrize(
    "level", [ThunderLevel.NONE, ThunderLevel.LOW, ThunderLevel.MED, ThunderLevel.HIGH],
)
def test_ac2_alle_vier_baender_bandtreu(env, level):
    """AC-2: jedes Symbol entspricht der Farbe seines eigenen Bandnamens --
    das erwartete Symbol wird aus `thunder_ampel_band()` abgeleitet."""
    band = thunder_ampel_band(level)
    erwartet = _ERWARTETES_SYMBOL[band]
    env(level)
    ergebnis = _drilldown_gewitter("telegram")
    assert ergebnis.success is True, f"Erwartet success=True: {ergebnis.confirmation_body!r}"
    symbol = _text_der_verlaufszeile(ergebnis.confirmation_body).split(" ", 1)[0]
    assert symbol == erwartet, (
        f"{level}: Band {band!r} zeigt {symbol!r}, erwartet {erwartet!r}"
    )


# ═══════════════════════════ AC-3 ════════════════════════════════════════════


@pytest.mark.parametrize(
    "level", [ThunderLevel.NONE, ThunderLevel.LOW, ThunderLevel.MED, ThunderLevel.HIGH],
)
def test_ac3_mail_und_telegram_zeigen_dieselbe_farbstufe(env, level):
    """AC-3: E-Mail-Ampelpunkt (`_ampel_dot_css`) und Telegram-Drilldown
    bezeichnen fuer dieselbe Gewitterstufe dieselbe Farbstufe -- keine
    Verschiebung um ein Band."""
    band = thunder_ampel_band(level)
    mail_html = _ampel_dot_css(band)
    treffer = re.search(r"background:(#[0-9a-fA-F]{6})", mail_html)
    assert treffer, f"Kein Fuell-Hex in _ampel_dot_css({band!r}):\n{mail_html}"
    mail_band = _MAIL_HEX_TO_BAND.get(treffer.group(1).lower())
    assert mail_band == band, (
        f"Testaufbau: Mail-Hex-Tabelle im Test veraltet fuer Band {band!r}"
    )

    env(level)
    ergebnis = _drilldown_gewitter("telegram")
    assert ergebnis.success is True, f"Erwartet success=True: {ergebnis.confirmation_body!r}"
    symbol = _text_der_verlaufszeile(ergebnis.confirmation_body).split(" ", 1)[0]
    telegram_band = _TELEGRAM_SYMBOL_TO_BAND.get(symbol)

    assert telegram_band == mail_band, (
        f"{level}: Telegram zeigt Band {telegram_band!r} ({symbol!r}), Mail "
        f"zeigt Band {mail_band!r} -- Farbverschiebung zwischen den Kanaelen"
    )
