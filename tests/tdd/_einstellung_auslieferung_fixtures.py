"""Gemeinsame Fixtures fuer Issue #2422 S1 (Invarianten-Test „Einstellung =
Auslieferung"). Kein Test-Modul (fuehrender Unterstrich -> pytest sammelt es
nicht ein), nur echte Datenmodell-Objekte, ein Golden-Loader und ein
Versand-Helfer ueber den echten ``NotificationService``.

Vorbild synthetische Wetter-Fixture: ``tests/tdd/_min_temp_felt_fixtures.py``.
Vorbild Aufzeichner/Nutzeranlage: ``tests/tdd/test_kanaltreue_adhoc_antwort.py``.

Kein ``Mock()``/``patch()``/``MagicMock``. Die einzige Naht ist der geteilte
Transport-Aufzeichner (``tests/helpers/transport_mitschrift.py``), der die
vier Ausgangs-Klassen in ``services.notification_service`` ersetzt -- Loader,
Kaskade und Formatter laufen unveraendert echt.
"""
from __future__ import annotations

import json
import uuid
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

from app.loader import get_data_dir, load_trip
from app.models import (
    ForecastDataPoint, ForecastMeta, GPXPoint, NormalizedTimeseries, Provider,
    SegmentWeatherData, SegmentWeatherSummary, ThunderLevel, TripSegment,
)
from services.notification_service import NotificationService, TripReportRequest
from tests.helpers.transport_mitschrift import Kanalmitschrift, aufzeichner_installieren

TZ = ZoneInfo("Europe/Paris")
YEAR, MONTH, DAY = 2026, 7, 20
STAGE_NAME = "E1"

GOLDEN_DIR = Path(__file__).resolve().parents[1] / "fixtures" / "einstellung_auslieferung"


# ---------------------------------------------------------------------------
# Synthetische Voll-Wetter-Fixture (AC-12) -- Vorbild _min_temp_felt_fixtures.py
# ---------------------------------------------------------------------------


def _local_to_utc(day: int, hour: int) -> datetime:
    return datetime(YEAR, MONTH, day, hour, 0, tzinfo=TZ).astimezone(timezone.utc)


def _meta() -> ForecastMeta:
    return ForecastMeta(
        provider=Provider.OPENMETEO, model="test",
        run=datetime(YEAR, MONTH, DAY, 0, 0, tzinfo=timezone.utc),
        grid_res_km=1.0, interp="point_grid",
    )


def _voller_datenpunkt(day: int, hour: int) -> ForecastDataPoint:
    """EIN Datenpunkt mit ALLEN Feldern belegt, die die bestehenden
    ``openmeteo``-Fixtures nicht abdecken (humidity, dewpoint, pressure,
    wind_chill_c, cloud_mid/high, precip_type, snow_new_24h) -- AC-12: rote
    Zellen sollen an Konfig-Logik entstehen, nicht an fehlenden Rohdaten.
    Werte oberhalb der konfigurierten SMS-Schwellen (precipitation>0.1,
    rain_probability>10) und Gewitter auf einer NICHT-Null-Stufe, damit keine
    Null-Form die "erscheint"-Dimension verfaelscht.
    """
    return ForecastDataPoint(
        ts=_local_to_utc(day, hour),
        t2m_c=15.0, wind_chill_c=13.0,
        wind10m_kmh=20.0, gust_kmh=45.0,
        precip_1h_mm=2.0, pop_pct=60,
        cloud_total_pct=70, cloud_low_pct=40, cloud_mid_pct=30, cloud_high_pct=20,
        thunder_level=ThunderLevel.MED,
        humidity_pct=65, dewpoint_c=8.0, pressure_msl_hpa=1013.0,
        wind_dir_deg=250, visibility_m=8000, uv_index=5.0,
        snow_depth_cm=0, snow_new_24h_cm=0, precip_type="rain",
        freezing_level_m=2500, snowfall_limit_m=2200,
        wmo_code=61, is_day=1, dni_wm2=300,
    )


def segment(day: int = DAY) -> SegmentWeatherData:
    seg = TripSegment(
        segment_id=1,
        start_point=GPXPoint(lat=42.0, lon=9.0, elevation_m=500.0, distance_from_start_km=0.0),
        end_point=GPXPoint(lat=42.1, lon=9.1, elevation_m=1400.0, distance_from_start_km=12.0),
        start_time=_local_to_utc(day, 8), end_time=_local_to_utc(day, 12),
        duration_hours=4.0, distance_km=12.0, ascent_m=900.0, descent_m=100.0,
    )
    data = [_voller_datenpunkt(day, h) for h in range(24)]
    return SegmentWeatherData(
        segment=seg, timeseries=NormalizedTimeseries(meta=_meta(), data=data),
        aggregated=SegmentWeatherSummary(
            temp_min_c=12.0, temp_max_c=20.0, temp_avg_c=15.0,
            wind_chill_min_c=10.0, wind_chill_max_c=18.0,
            wind_max_kmh=20.0, gust_max_kmh=45.0, precip_sum_mm=8.0,
            pop_max_pct=60, cloud_avg_pct=70, thunder_level_max=ThunderLevel.MED,
        ),
        fetched_at=datetime(YEAR, MONTH, day, 6, 0, tzinfo=timezone.utc),
        provider="openmeteo",
    )


def night_weather(day: int = DAY) -> NormalizedTimeseries:
    points = [_voller_datenpunkt(day, h) for h in range(12, 24)]
    points += [_voller_datenpunkt(day + 1, h) for h in range(0, 7)]
    return NormalizedTimeseries(meta=_meta(), data=points)


# ---------------------------------------------------------------------------
# Golden-Trip-JSONs laden (Persistenzformat des Editors)
# ---------------------------------------------------------------------------


def golden_dict(name: str) -> dict:
    """Rohes ``json.load``-Dict des Golden-Trip-JSON (``"golden_a"``/
    ``"golden_b"``) -- NUR die Stage-Daten werden relativ zu heute
    nachgezogen (einzige Nachbearbeitung, sonst 1:1 der Datei-Inhalt)."""
    pfad = GOLDEN_DIR / f"{name}.json"
    data = json.loads(pfad.read_text())
    heute = date.today()
    for i, s in enumerate(data["stages"]):
        s["date"] = (heute + timedelta(days=i - 1)).isoformat()
    return data


def golden_trip(name: str):
    """Golden-JSON ueber den ECHTEN ``load_trip``-Loader eingelesen."""
    return load_trip(golden_dict(name), user_id="default")


# ---------------------------------------------------------------------------
# Nutzeranlage + Versand (Naht ausschliesslich am Transport)
# ---------------------------------------------------------------------------


def frisches_profil(*, tier: str = "premium") -> str:
    """Echtes ``user.json`` auf der isolierten Datenwurzel -- KEIN
    "tdd"/"test" in der Kennung (Herkunftssperre, #2406/origin_guard.py:29-34),
    ``sms_verified_number`` gesetzt (#2406). Jeder Aufruf legt ein FRISCHES
    Profil an, damit ``sms_daily_limit``/``briefing_log``/``undelivered``
    zwischen mehreren Sende-Laeufen (z.B. AC-9 mit ~10 Laeufen) nicht
    interferieren."""
    uid = f"einstellung-{uuid.uuid4().hex[:10]}"
    ordner = get_data_dir(uid)
    ordner.mkdir(parents=True, exist_ok=True)
    (ordner / "user.json").write_text(json.dumps({
        "id": uid, "tier": tier,
        "mail_to": f"{uid}@example.invalid", "telegram_chat_id": f"chat-{uid}",
        "sms_to": "+490000000009", "sms_verified_number": "+490000000009",
        "sms_verified_at": "2026-01-01T00:00:00Z",
        "premium_sms_reply_to": "+490000000008",
        "premium_sms_reply_at": datetime.now(timezone.utc).isoformat(),
    }))
    return uid


#: Jedes Transport-Feld ausdruecklich unbrauchbar belegt (#1477) -- Vorbild
#: ``test_kanaltreue_adhoc_antwort.py::_TRANSPORT_ENV``.
TRANSPORT_ENV = {
    "GZ_ENV": "development",
    "GZ_SMTP_HOST": "smtp.invalid", "GZ_SMTP_USER": "unbrauchbar",
    "GZ_SMTP_PASS": "unbrauchbar", "GZ_MAIL_FROM": "gregor@example.invalid",
    "GZ_MAIL_TO": "globaler-rueckfall@example.invalid",
    "GZ_TELEGRAM_BOT_TOKEN": "0000000:unbrauchbar",
    "GZ_TELEGRAM_CHAT_ID": "globaler-rueckfall-chat",
    "GZ_SMS_GATEWAY_URL": "https://gateway.invalid/api/sms",
    "GZ_SEVEN_API_KEY": "unbrauchbar",
    "GZ_SMS_TO": "+490000000000",
}


def render_golden(monkeypatch, name: str) -> tuple[Kanalmitschrift, object]:
    """Ein Golden-Trip-JSON ueber den ECHTEN Loader/Kaskade/Formatter senden.

    Naht ausschliesslich am Transport (AC-13): ``EmailOutput``/``SMSOutput``/
    ``PremiumSmsOutput``/``TelegramOutput`` werden per ``monkeypatch`` durch
    den geteilten Aufzeichner ersetzt. ``TripReportRequest`` wird direkt
    konstruiert (kein Scheduler, keine Provider-Naht noetig) -- die
    Versand-Flags kommen aus dem GELADENEN ``report_config`` (echte
    Einstellung), nie hartcodiert.

    Gibt (Mitschrift, geladener Trip) zurueck. Jeder Aufruf nutzt ein
    FRISCHES Nutzerprofil.
    """
    for k, v in TRANSPORT_ENV.items():
        monkeypatch.setenv(k, v)
    mitschrift = aufzeichner_installieren(monkeypatch)

    uid = frisches_profil()
    trip = golden_trip(name)
    assert trip is not None, f"Golden {name!r} liess sich nicht laden"

    rc = trip.report_config
    request = TripReportRequest(
        trip=trip, report_type="evening", segment_weather=[segment()],
        trip_tz=TZ, night_weather=night_weather(), stage_name=STAGE_NAME,
        report_config=rc, display_config=trip.display_config,
        send_email=rc.send_email, send_sms=rc.send_sms,
        send_telegram=rc.send_telegram, send_premium_sms=rc.send_premium_sms,
    )
    ergebnis = NotificationService(user_id=uid).send_trip_report(request)
    assert ergebnis.sent, f"Vorbedingung: Golden {name!r} muss versendet werden: {ergebnis}"
    return mitschrift, trip


def format_direkt(dc):
    """Reiner Formatter-Aufruf ohne Versand (fuer AC-1-Vergleiche, bei denen
    nur die geladene ``UnifiedWeatherDisplayConfig`` interessiert -- kein
    Renderer-Aufruf noetig)."""
    return dc
