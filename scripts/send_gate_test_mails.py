#!/usr/bin/env python3
"""Renderer-Mail-Gate (#811) — Nachweis-Sender fuer Issue #1233 / #1216-WarnBlock.

SICHERHEIT (HART):
  - Sendet AUSSCHLIESSLICH ueber `Settings.for_testing()`. Das #1122-Default-
    Deny in `app.config.Settings` lenkt jeden Versand ueber diesen Weg auf das
    lokale Stalwart-Testpostfach (mail.henemm.com) um -- KEIN Resend-Versand,
    KEIN Produktivkontingent.
  - Empfaenger ist immer `gregor-test@henemm.com` (Test-Postfach), NIE eine
    echte Nutzer-Adresse.
  - Alle Inhalte sind SYNTHETISCHE Fixture-Daten (Vorbild: tests/tdd/
    test_official_alert_standalone_render.py, test_warn_block_render.py,
    test_warn_block_trip_placement.py, test_warn_block_compare_banner.py,
    tests/tdd/test_issue_811_mode_matrix.py). Es werden NIE echte Nutzerdaten
    aus data/users/<realer_user> gelesen.
  - Kein git-Zugriff, keine Aenderung an Validatoren/Hooks.

ZWECK: Erzeugt fuer die drei Mail-Pfade, die der Renderer-Mail-Gate (#811)
fuer commit-2 (#1233 amtliche-Warnung-Redesign + #1216 eingebetteter
WarnBlock) verlangt, echte zugestellte Test-Mails, gegen die die
kanonischen Validatoren (official_alert_mail_validator.py,
briefing_mail_validator.py, optional email_spec_validator.py) laufen
koennen:

  (a) Standalone amtliche Warnung   -> X-GZ-Mail-Type: official-alert
  (b) Trip-Briefing (full) + WarnBlock -> X-GZ-Mail-Type: trip-briefing,
                                          X-GZ-Format: full
  (c) Orts-Vergleich + WarnBlock     -> X-GZ-Mail-Type: compare

Idempotent nutzbar: jeder Lauf erzeugt einen frischen Zufalls-Token im
Betreff, keine Seiteneffekte auf persistente Daten (data/users/ bleibt
unberuehrt -- der Trip fuer den Official-Alert-Pfad existiert nur transient
im Speicher, wird NICHT gespeichert).

Usage:
    uv run python3 scripts/send_gate_test_mails.py                # alle drei
    uv run python3 scripts/send_gate_test_mails.py --only official
    uv run python3 scripts/send_gate_test_mails.py --only briefing
    uv run python3 scripts/send_gate_test_mails.py --only compare
"""
from __future__ import annotations

import argparse
import sys
import uuid
from datetime import date, datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from app.config import Settings  # noqa: E402
from app.metric_catalog import build_default_display_config  # noqa: E402
from app.models import (  # noqa: E402
    ForecastDataPoint, ForecastMeta, GPXPoint, NormalizedTimeseries, Provider,
    SegmentWeatherData, SegmentWeatherSummary, ThunderLevel, TripSegment,
)
from app.profile import ActivityProfile  # noqa: E402
from app.trip import Stage, Trip, Waypoint  # noqa: E402
from app.user import ComparisonResult, LocationResult, SavedLocation  # noqa: E402
from output.channels.email import EmailOutput  # noqa: E402
from output.renderers.email import render_email  # noqa: E402
from output.renderers.email.helpers import dp_to_row  # noqa: E402
from output.renderers.comparison import render_compare_email  # noqa: E402
from output.tokens.dto import TokenLine  # noqa: E402
from services.notification_service import NotificationService  # noqa: E402
from services.official_alerts.models import OfficialAlert  # noqa: E402

UTC = timezone.utc
VIENNA = ZoneInfo("Europe/Vienna")
TEST_RECIPIENT = "gregor-test@henemm.com"


def _test_settings() -> Settings | None:
    """Vorbild tests/tdd/test_952_onset_alert_e2e.py::_test_settings.

    Erzwingt Stalwart-Testpostfach (for_testing) + festen Test-Empfaenger,
    unabhaengig davon, was in der lokalen .env als mail_to konfiguriert ist.
    """
    settings = Settings().for_testing()
    if not settings.can_send_email():
        return None
    return settings.model_copy(update={"mail_to": TEST_RECIPIENT})


# ---------------------------------------------------------------------------
# (a) Standalone amtliche Warnung -- ueber den echten Versandpfad
#     NotificationService.send_official_alert() (#1233 Slice B Redesign).
# ---------------------------------------------------------------------------
def send_official_alert_mail(settings: Settings, token: str) -> bool:
    stage = Stage(
        id="s1", name="Tag 1", date=date(2026, 7, 13),
        waypoints=[Waypoint(id="w1", name="Gate-Test-Start", lat=46.62, lon=13.68,
                             elevation_m=600)],
    )
    trip = Trip(id=f"gate-1233-official-{token}", name=f"GATE1233 {token}", stages=[stage])

    alert = OfficialAlert(
        source="geosphere_warn", hazard="thunderstorm", level=3,
        label="Gewitter",
        valid_from=datetime(2026, 7, 13, 15, 0, tzinfo=UTC),
        valid_to=datetime(2026, 7, 13, 21, 0, tzinfo=UTC),
        region_label="Hermagor-Pressegger See",
    )
    notices = [(alert, ["1"])]

    ns = NotificationService(settings, f"gate-1233-official-{token}")
    result = ns.send_official_alert(
        trip=trip, notices=notices, effective_channels={"email"},
    )
    return bool(result.sent and "email" in result.sent_channels)


# ---------------------------------------------------------------------------
# (b) Trip-Briefing (full) mit eingebettetem #1216-WarnBlock -- ueber den
#     echten Renderer-Einstiegspunkt render_email() (segments tragen
#     official_alerts, analog test_warn_block_trip_placement.py).
# ---------------------------------------------------------------------------
def _briefing_dps() -> list[ForecastDataPoint]:
    return [
        ForecastDataPoint(
            ts=datetime(2026, 7, 13, h, 0, tzinfo=UTC),
            t2m_c=t, wind10m_kmh=w, gust_kmh=w + 8, precip_1h_mm=p,
            pop_pct=15, cloud_total_pct=c, thunder_level=ThunderLevel.NONE,
            visibility_m=20000, freezing_level_m=3000,
        )
        for h, t, w, c, p in (
            (8, 14.0, 10.0, 30, 0.0),
            (10, 17.0, 12.0, 35, 0.0),
            (12, 20.0, 14.0, 40, 0.2),
            (14, 19.0, 13.0, 38, 0.0),
        )
    ]


def build_briefing_mail(token: str) -> tuple[str, str, str]:
    """Returns (subject, html, plain)."""
    dps = _briefing_dps()
    seg = TripSegment(
        segment_id=1,
        start_point=GPXPoint(lat=46.62, lon=13.68, elevation_m=600.0),
        end_point=GPXPoint(lat=46.60, lon=13.70, elevation_m=1200.0,
                            distance_from_start_km=8.0),
        start_time=dps[0].ts, end_time=dps[-1].ts,
        duration_hours=6.0, distance_km=8.0, ascent_m=600.0, descent_m=0.0,
    )
    meta = ForecastMeta(provider=Provider.OPENMETEO, model="gate-1233-fixture", grid_res_km=1.3)
    ts = NormalizedTimeseries(meta=meta, data=dps)
    agg = SegmentWeatherSummary(
        temp_min_c=14.0, temp_max_c=20.0, temp_avg_c=17.5,
        wind_max_kmh=14.0, gust_max_kmh=22.0, precip_sum_mm=0.2,
        cloud_avg_pct=35, humidity_avg_pct=55, thunder_level_max=ThunderLevel.NONE,
    )
    alert = OfficialAlert(
        source="geosphere_warn", hazard="thunderstorm", level=2,
        label="Gewitter",
        valid_from=datetime(2026, 7, 13, 12, 0, tzinfo=UTC),
        valid_to=datetime(2026, 7, 13, 18, 0, tzinfo=UTC),
        region_label="Hermagor-Pressegger See",
    )
    seg_data = SegmentWeatherData(
        segment=seg, timeseries=ts, aggregated=agg,
        fetched_at=datetime.now(UTC), provider="openmeteo",
        official_alerts=[alert],
    )

    dc = build_default_display_config()
    seg_tables = [[dp_to_row(dp, dc, tz=VIENNA) for dp in dps]]
    tl = TokenLine(
        trip_name=f"GATE1233 {token}", report_type="morning",
        stage_name="Etappe 1: Gate-Test-Strecke",
    )
    html, plain = render_email(
        tl, segments=[seg_data], seg_tables=seg_tables,
        display_config=dc, tz=VIENNA, friendly_keys=set(),
        email_format="full",
        compact_summary="Wechselhaft mit einzelnen Gewittern am Nachmittag.",
        stage_name="Etappe 1: Gate-Test-Strecke",
        stage_stats={"distance_km": 8.0, "ascent_m": 600.0, "descent_m": 0.0,
                     "max_elevation_m": 1200.0},
        sent_at=datetime.now(UTC),
    )
    subject = f"[GATE1233 {token}] Etappe 1 Morgen-Briefing"
    return subject, html, plain


def send_briefing_mail(settings: Settings, token: str) -> bool:
    subject, html, plain = build_briefing_mail(token)
    EmailOutput(settings).send(
        subject=subject, body=html, plain_text_body=plain,
        mail_type="trip-briefing", mail_format="full",
    )
    return True


# ---------------------------------------------------------------------------
# (c) Orts-Vergleich mit eingebettetem #1216-WarnBlock -- ueber den echten
#     Renderer-Einstiegspunkt render_compare_email() (analog
#     test_warn_block_compare_banner.py).
# ---------------------------------------------------------------------------
def _compare_hourly_data(base_temp: float) -> list[ForecastDataPoint]:
    return [
        ForecastDataPoint(
            ts=datetime(2026, 7, 13, h, 0, tzinfo=UTC),
            t2m_c=base_temp + (h - 9) * 0.6, wind10m_kmh=12.0, gust_kmh=20.0,
            wind_chill_c=base_temp + (h - 9) * 0.6 - 1.0,
            precip_1h_mm=0.0, pop_pct=10, uv_index=4.0,
            thunder_level=ThunderLevel.NONE, visibility_m=20000,
        )
        for h in range(9, 17)
    ]


def build_compare_mail(token: str) -> tuple[str, str, str]:
    """Returns (subject, html, plain)."""
    loc1 = SavedLocation(id=f"gate-loc-1-{token}", name="Gatehausen Nord", lat=47.0, lon=11.0,
                          elevation_m=1200)
    loc2 = SavedLocation(id=f"gate-loc-2-{token}", name="Gatehausen Mitte", lat=47.2, lon=11.3,
                          elevation_m=900)
    loc3 = SavedLocation(id=f"gate-loc-3-{token}", name="Gatehausen Sued", lat=46.8, lon=10.8,
                          elevation_m=1500)

    alert = OfficialAlert(
        source="geosphere_warn", hazard="extreme_heat", level=2,
        label="Hitze",
        valid_from=datetime(2026, 7, 13, 0, 0, tzinfo=UTC),
        valid_to=datetime(2026, 7, 13, 23, 59, tzinfo=UTC),
        region_label="Gatehausen Nord",
    )

    results = [
        LocationResult(
            location=loc1, score=0, temp_max=24.0, wind_max=16.0,
            sunny_hours=6, cloud_avg=30,
            hourly_data=_compare_hourly_data(20.0),
            official_alerts=[alert],
        ),
        LocationResult(
            location=loc2, score=0, temp_max=22.0, wind_max=14.0,
            sunny_hours=5, cloud_avg=40,
            hourly_data=_compare_hourly_data(18.0),
        ),
        LocationResult(
            location=loc3, score=0, temp_max=19.0, wind_max=18.0,
            sunny_hours=4, cloud_avg=55,
            hourly_data=_compare_hourly_data(15.0),
        ),
    ]
    result = ComparisonResult(
        locations=results, time_window=(9, 16), target_date=date(2026, 7, 13),
    )
    html, plain = render_compare_email(
        result, profile=ActivityProfile.ALLGEMEIN,
        preset_name=f"GATE1233 Compare {token}",
    )
    subject = f"[GATE1233 {token}] Orts-Vergleich"
    return subject, html, plain


def send_compare_mail(settings: Settings, token: str) -> bool:
    subject, html, plain = build_compare_mail(token)
    EmailOutput(settings).send(
        subject=subject, body=html, plain_text_body=plain,
        mail_type="compare", mail_format="full",
    )
    return True


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--only", choices=["official", "briefing", "compare"], default=None,
        help="Nur einen der drei Mail-Pfade senden (default: alle drei).",
    )
    args = parser.parse_args()

    settings = _test_settings()
    if settings is None:
        print("SMTP-Testpfad nicht konfiguriert (GZ_TEST_SMTP_USER/PASS fehlen) "
              "-- kann nicht senden.", file=sys.stderr)
        return 2

    token = uuid.uuid4().hex[:8]
    print(f"Token fuer diesen Lauf: {token}")

    targets = [args.only] if args.only else ["official", "briefing", "compare"]

    ok = True
    if "official" in targets:
        sent = send_official_alert_mail(settings, token)
        print(f"(a) Standalone amtliche Warnung gesendet: {sent}")
        ok = ok and sent
    if "briefing" in targets:
        sent = send_briefing_mail(settings, token)
        print(f"(b) Trip-Briefing (full) + WarnBlock gesendet: {sent}")
        ok = ok and sent
    if "compare" in targets:
        sent = send_compare_mail(settings, token)
        print(f"(c) Orts-Vergleich + WarnBlock gesendet: {sent}")
        ok = ok and sent

    print(f"An: {TEST_RECIPIENT} -- Token: {token}")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
