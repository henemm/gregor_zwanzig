"""TDD RED — Mail-Herkunft-Footer + Date-Header (Spec: mail_origin_footer.md).

Issues #1241 (Herkunfts-Footer) + #1247 (Date-Header), gebündelt.

KEINE Mocks. Alle Tests rendern echte Mail-Objekte über die echten Renderer
mit minimalen, aber echten Fixture-Daten und prüfen das tatsächlich
gerenderte Verhalten (Footer-String-Vorkommen im Output, ASCII-Eigenschaft,
Byte-Limit, Date-Header-Parsbarkeit, Commit-Hash-Format/Fallback).

RED-Erwartung gegen den unveränderten Ausgangscode:
  AC-1/2/3/4/5/8  — die neuen Footer-Zeilen fehlen noch im Renderer-Output
                    → AssertionError (Footer-Text nicht vorhanden bzw. Count 0).
  AC-6/AC-7       — render_official_alert_html() kennt den Parameter
                    context_label noch nicht → TypeError.
  AC-9            — build_origin_footer/_deployed_commit existieren noch nicht
                    in helpers.py → ImportError.
  AC-10           — build_mime_message() setzt heute keinen Date-Header
                    → AssertionError (msg["Date"] is None).

AC-11 (Nicht-Regression / Live-E2E) ist NICHT Teil dieser Kern-Suite.
"""
from __future__ import annotations

import re
import sys
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
for _p in (str(REPO_ROOT), str(REPO_ROOT / "src")):
    if _p not in sys.path:
        sys.path.insert(0, _p)


# ---------------------------------------------------------------------------
# Label-Konstanten aus der freigegebenen Spec-Label-Tabelle
# ---------------------------------------------------------------------------
# Zeile-1-Bausteine getrennt geprüft, damit HTML-Escaping des Trenn-Mittel-
# punktes (·/&middot;/&#183;) den Nachweis nicht bricht.
LBL_FULL_A = "Etappen-Briefing"
LBL_FULL_B = "Vollversion"
LBL_COMPACT_B = "Kompakt"
LBL_COMPARE = "Ortsvergleich"
LBL_DEVIATION = "Abweichungs-Alarm"
LBL_RADAR = "Regen-/Gewitter-Alarm"
LBL_OFFICIAL_TAIL = "Amtliche Warnung"


# ---------------------------------------------------------------------------
# Echte Trip-Fixtures (kein Mock) — Muster aus test_briefing_mail_inhalt.py
# ---------------------------------------------------------------------------
def _build_seg_data(official_alerts=None):
    from app.models import (
        ForecastDataPoint, ForecastMeta, GPXPoint, NormalizedTimeseries,
        Provider, SegmentWeatherData, SegmentWeatherSummary, ThunderLevel,
        TripSegment,
    )
    seg = TripSegment(
        segment_id=1,
        start_point=GPXPoint(lat=42.13, lon=9.13, elevation_m=900.0),
        end_point=GPXPoint(lat=42.10, lon=9.18, elevation_m=1450.0),
        start_time=datetime(2026, 7, 11, 8, 0, tzinfo=timezone.utc),
        end_time=datetime(2026, 7, 11, 12, 0, tzinfo=timezone.utc),
        duration_hours=4.0, distance_km=14.5, ascent_m=820.0, descent_m=440.0,
    )
    meta = ForecastMeta(
        provider=Provider.OPENMETEO, model="demo", grid_res_km=1.3,
        run=datetime(2026, 7, 11, 0, 0, tzinfo=timezone.utc),
    )
    data = [
        ForecastDataPoint(
            ts=datetime(2026, 7, 11, h, 0, tzinfo=timezone.utc),
            t2m_c=15.0 + h * 0.3, wind10m_kmh=15.0,
            precip_1h_mm=0.2, cloud_total_pct=50,
            thunder_level=ThunderLevel.NONE,
        )
        for h in range(8, 14)
    ]
    ts = NormalizedTimeseries(meta=meta, data=data)
    agg = SegmentWeatherSummary(
        temp_min_c=14.0, temp_max_c=22.0, temp_avg_c=18.0,
        wind_max_kmh=22.0, gust_max_kmh=35.0,
        precip_sum_mm=0.8, cloud_avg_pct=50, humidity_avg_pct=55,
        thunder_level_max=ThunderLevel.NONE,
    )
    kwargs = dict(
        segment=seg, timeseries=ts, aggregated=agg,
        fetched_at=datetime.now(timezone.utc), provider="demo",
    )
    if official_alerts is not None:
        kwargs["official_alerts"] = official_alerts
    return SegmentWeatherData(**kwargs)


def _render_trip_html(official_alerts=None):
    from app.metric_catalog import build_default_display_config
    from output.renderers.email.html import render_html

    seg = _build_seg_data(official_alerts=official_alerts)
    return render_html(
        segments=[seg], seg_tables=[[]],
        trip_name="Graveltour im Münsterland", report_type="morning",
        dc=build_default_display_config(), night_rows=[],
        thunder_forecast=None, changes=None,
        stage_name="Etappe 2", stage_stats={"distance_km": 14.5, "ascent_m": 820},
        multi_day_trend=None, compact_summary="Guter Tag.",
        tz=ZoneInfo("Europe/Berlin"), friendly_keys=set(),
    )


def _render_trip_plain():
    from app.metric_catalog import build_default_display_config
    from output.renderers.email.plain import render_plain

    seg = _build_seg_data()
    return render_plain(
        segments=[seg], seg_tables=[[]],
        trip_name="Graveltour im Münsterland", report_type="morning",
        dc=build_default_display_config(), night_rows=[],
        thunder_forecast=None, changes=None,
        stage_name="Etappe 2", stage_stats={"distance_km": 14.5, "ascent_m": 820},
        multi_day_trend=None, compact_summary="Guter Tag.",
        tz=ZoneInfo("Europe/Berlin"), friendly_keys=set(),
    )


def _render_compact():
    from app.metric_catalog import build_default_display_config
    from output.renderers.email.compact import render_compact

    seg = _build_seg_data()
    return render_compact(
        segments=[seg], dc=build_default_display_config(),
        multi_day_trend=None, stability_result=None,
        tz=ZoneInfo("Europe/Berlin"), report_type="morning",
        trip_name="Graveltour im Münsterland", stage_name="Etappe 2",
        stage_stats={"distance_km": 14.5, "ascent_m": 820},
    )


def _deployed_commit_value():
    """Lazy-Import: existiert in RED noch nicht → ImportError (gewollt)."""
    from src.output.renderers.email.helpers import _deployed_commit
    return _deployed_commit()


# ---------------------------------------------------------------------------
# Alert-Fixtures (kein Mock)
# ---------------------------------------------------------------------------
def _deviation_message():
    from output.renderers.alert.model import AlertEvent, AlertMessage
    ev = AlertEvent(
        metric_id="wind", value_from=20.0, value_to=48.0, threshold=15.0,
        cmp="über", occurred_at="14:00", km_from=5.0, km_to=12.0,
    )
    return AlertMessage(trip_short="GR20", stand_at="09:30", events=(ev,))


def _radar_message():
    from output.renderers.alert.model import AlertMessage, OnsetEvent
    ev = OnsetEvent(
        onset_minutes=45, onset_time="14:30", km_from=5.0, km_to=12.0,
        is_convective=False, intensity_label="mäßig", source_label="Radar (DWD)",
    )
    return AlertMessage(
        trip_short="GR20", stand_at="09:30", events=(ev,),
        source="radar", cooldown_display="30 Min",
    )


def _official_notices():
    from services.official_alerts.models import OfficialAlert
    from output.renderers.alert.official_alerts import OfficialAlertNotice
    alert = OfficialAlert(
        source="geosphere_warn", hazard="thunderstorm", level=3,
        label="Gewitter", region_label="Hermagor",
        valid_from=datetime(2026, 7, 11, 15, 0, tzinfo=timezone.utc),
        valid_to=datetime(2026, 7, 11, 21, 0, tzinfo=timezone.utc),
    )
    return [OfficialAlertNotice(
        alert=alert, scope_label="gesamte Route", sms_scope="ges.Route",
        affected_chips=["gesamte Route"], free_chips=[],
    )]


# ===========================================================================
# AC-1 — Trip-Briefing Vollversion (HTML + Plain): Herkunfts-Footer
# ===========================================================================
class TestAC1TripFullFooter:
    def test_html_and_plain_contain_origin_footer(self):
        html = _render_trip_html()
        plain = _render_trip_plain()

        # Zeile 1 (Mail-Art) in beiden Ausgaben.
        for out, name in ((html, "HTML"), (plain, "Plain")):
            assert LBL_FULL_A in out, f"{name}: Footer-Label '{LBL_FULL_A}' fehlt"
            assert LBL_FULL_B in out, f"{name}: Footer-Label '{LBL_FULL_B}' fehlt"

        # Zeile 2 (Renderer + Commit-Stand) — Commit muss im Output stehen.
        commit = _deployed_commit_value()
        assert commit in html, "HTML-Footer trägt keinen Commit-Stand"
        assert commit in plain, "Plain-Footer trägt keinen Commit-Stand"


# ===========================================================================
# AC-2 — Compact: Footer, vollständig ASCII, < 2048 Bytes, kein U+00B7
# ===========================================================================
class TestAC2CompactFooter:
    def test_compact_footer_ascii_and_bytelimit(self):
        out = _render_compact()

        # Footer-Label vorhanden (ASCII-gefaltet: '·' -> '-').
        assert LBL_FULL_A in out, f"Compact-Footer-Label '{LBL_FULL_A}' fehlt"
        assert LBL_COMPACT_B in out, f"Compact-Footer-Label '{LBL_COMPACT_B}' fehlt"

        assert out.isascii(), "Compact-Ausgabe ist nicht rein ASCII"
        assert "·" not in out, "Compact enthält verbotenes '·' (U+00B7)"
        assert len(out.encode("utf-8")) < 2048, (
            f"Compact überschreitet das Byte-Limit: {len(out.encode('utf-8'))} Bytes"
        )


# ===========================================================================
# AC-3 — Ortsvergleich-Mail: Footer 'Ortsvergleich' + Renderer/Commit
# ===========================================================================
class TestAC3CompareFooter:
    def _result(self):
        from app.user import ComparisonResult, LocationResult, SavedLocation
        from datetime import date

        def loc(i, name, elev):
            return SavedLocation(id=i, name=name, lat=47.0, lon=11.0, elevation_m=elev)

        lr_a = LocationResult(
            location=loc("a", "Alpspitze", 2600), score=70, snow_depth_cm=120.0,
            snow_new_cm=10.0, sunny_hours=5, wind_max=20.0, gust_max=35.0,
            cloud_avg=20, temp_max=-1.0, wind_chill_min=-7.0, above_low_clouds=True,
        )
        lr_b = LocationResult(
            location=loc("b", "Talkessel", 1300), score=50, snow_depth_cm=40.0,
            snow_new_cm=2.0, sunny_hours=2, wind_max=8.0, gust_max=14.0,
            cloud_avg=60, temp_max=3.0, wind_chill_min=-1.0, above_low_clouds=False,
        )
        return ComparisonResult(
            locations=[lr_a, lr_b], time_window=(9, 16),
            target_date=date.today(), created_at=datetime.now(),
        )

    def test_compare_footer_shows_ortsvergleich_and_commit(self):
        from output.renderers.email.compare_html import render_compare_html
        from app.profile import ActivityProfile

        html = render_compare_html(self._result(), profile=ActivityProfile.WINTERSPORT)

        assert LBL_COMPARE in html, "Compare-Footer-Label 'Ortsvergleich' fehlt"
        commit = _deployed_commit_value()
        assert commit in html, "Compare-Footer trägt keinen Commit-Stand"


# ===========================================================================
# AC-4 — Abweichungs-Alarm (deviation): Footer-Zeile 'Abweichungs-Alarm'
# ===========================================================================
class TestAC4DeviationFooter:
    def test_deviation_footer_label(self):
        from output.renderers.alert.render import render_email

        html, plain = render_email(_deviation_message())
        assert LBL_DEVIATION in html, "Deviation-HTML-Footer-Label fehlt"
        assert LBL_DEVIATION in plain, "Deviation-Plain-Footer-Label fehlt"


# ===========================================================================
# AC-5 — Regen-/Gewitter-Alarm (radar/onset): Footer 'Regen-/Gewitter-Alarm'
# ===========================================================================
class TestAC5RadarFooter:
    def test_radar_footer_label(self):
        from output.renderers.alert.render import render_email

        html, plain = render_email(_radar_message())
        assert LBL_RADAR in html, "Radar-HTML-Footer-Label fehlt"
        assert LBL_RADAR in plain, "Radar-Plain-Footer-Label fehlt"


# ===========================================================================
# AC-6 — Amtliche Warnung aus Trip-Kontext: Trip-Name im Footer
# ===========================================================================
class TestAC6OfficialTripContext:
    def test_trip_name_in_official_footer(self):
        from output.renderers.alert.official_alerts import render_official_alert_html

        trip_name = "GR20-Nordkorsika-Testroute"
        html = render_official_alert_html(
            _official_notices(), source_label="GeoSphere Austria",
            stand_at="09:30", tz=ZoneInfo("UTC"), context_label=trip_name,
        )
        assert trip_name in html, "Trip-Name fehlt im Herkunfts-Footer"
        assert LBL_OFFICIAL_TAIL in html, "'Amtliche Warnung' fehlt im Footer"


# ===========================================================================
# AC-7 — Amtliche Warnung aus Compare-Kontext: 'Ortsvergleich · Amtliche W.'
# ===========================================================================
class TestAC7OfficialCompareContext:
    def test_ortsvergleich_in_official_footer(self):
        from output.renderers.alert.official_alerts import render_official_alert_html

        html = render_official_alert_html(
            _official_notices(), source_label="GeoSphere Austria",
            stand_at="09:30", tz=ZoneInfo("UTC"), context_label="Ortsvergleich",
        )
        assert LBL_COMPARE in html, "'Ortsvergleich' fehlt im Herkunfts-Footer"
        assert LBL_OFFICIAL_TAIL in html, "'Amtliche Warnung' fehlt im Footer"


# ===========================================================================
# AC-8 — Embedded Warn-Block: Footer-Text erscheint GENAU EINMAL (nicht doppelt)
# ===========================================================================
class TestAC8EmbeddedNoDoubleFooter:
    def test_footer_appears_exactly_once_with_embedded_warn_block(self):
        from services.official_alerts.models import OfficialAlert

        alert = OfficialAlert(
            source="geosphere_warn", hazard="thunderstorm", level=3,
            label="Gewitter", region_label="Hermagor",
            valid_from=datetime(2026, 7, 11, 15, 0, tzinfo=timezone.utc),
            valid_to=datetime(2026, 7, 11, 21, 0, tzinfo=timezone.utc),
        )
        html = _render_trip_html(official_alerts=[alert])

        # Die Wirts-Mail trägt den Herkunfts-Footer genau einmal; der
        # eingebettete Warn-Block darf keine zweite Kopie beisteuern.
        assert html.count(LBL_FULL_A) == 1, (
            f"Footer-Label '{LBL_FULL_A}' erscheint {html.count(LBL_FULL_A)}x "
            "(erwartet: genau 1x — kein doppelter Footer durch den Warn-Block)"
        )


# ===========================================================================
# AC-9 — _deployed_commit(): Hex-Hash im Git-Repo, Fallback 'unknown' ohne .git
# ===========================================================================
class TestAC9DeployedCommit:
    def test_returns_hex_hash_in_real_git_repo(self):
        from src.output.renderers.email.helpers import _deployed_commit

        commit = _deployed_commit()
        assert isinstance(commit, str)
        assert re.match(r"^[0-9a-f]{7,}$", commit), (
            f"Commit-Stand ist kein kurzer Hex-Hash: {commit!r}"
        )

    def test_fallback_unknown_without_git(self, tmp_path, monkeypatch):
        from src.output.renderers.email.helpers import _deployed_commit

        # tmp_path liegt außerhalb jedes Git-Checkouts → git rev-parse scheitert.
        monkeypatch.chdir(tmp_path)
        assert _deployed_commit() == "unknown", (
            "Ohne .git muss der Fallback 'unknown' sein (keine Exception)"
        )


# ===========================================================================
# AC-10 — build_mime_message() setzt einen RFC-2822-parsbaren Date-Header
# ===========================================================================
class TestAC10DateHeader:
    def _kwargs(self, html: bool):
        return dict(
            subject="Test", body="<p>Hallo</p>" if html else "Hallo",
            from_addr="gregor@henemm.com", to_header="gregor-test@henemm.com",
            reply_to=None, html=html, plain_text_body=None,
        )

    def test_date_header_present_html_branch(self):
        from output.channels.email import build_mime_message

        msg = build_mime_message(**self._kwargs(html=True))
        assert msg["Date"] is not None, "HTML-Zweig setzt keinen Date-Header"
        assert isinstance(parsedate_to_datetime(msg["Date"]), datetime), (
            "Date-Header ist nicht RFC-2822-parsbar (HTML-Zweig)"
        )

    def test_date_header_present_plain_branch(self):
        from output.channels.email import build_mime_message

        msg = build_mime_message(**self._kwargs(html=False))
        assert msg["Date"] is not None, "Plain-Zweig setzt keinen Date-Header"
        assert isinstance(parsedate_to_datetime(msg["Date"]), datetime), (
            "Date-Header ist nicht RFC-2822-parsbar (Plain-Zweig)"
        )
