"""Validator render service.

Encapsulates alert-channel and compare-email rendering used by the validator
router so that api/routers/validator.py does not import output.renderers.*
directly.
"""
from __future__ import annotations

from datetime import date as date_type
from datetime import datetime, time, timedelta, timezone
from typing import Any

from app.models import (
    ChangeSeverity,
    ForecastMeta,
    GPXPoint,
    NormalizedTimeseries,
    Provider,
    SegmentWeatherData,
    SegmentWeatherSummary,
    TripSegment,
    WeatherChange,
)
from app.profile import ActivityProfile
from app.trip import Trip
from app.user import ComparisonResult, LocationResult, SavedLocation
from output.renderers.alert.model import AlertMessage, OnsetEvent
from output.renderers.alert.project import to_alert_message
from output.renderers.alert.render import (
    render_email,
    render_sms,
    render_subject,
    render_telegram,
)
from output.renderers.email.compare_html import render_compare_html
from output.renderers.sms_trip import SMS_MULTI_SYMBOLS_BY_METRIC, SMS_SYMBOL_BY_METRIC
from output.tokens.builder import build_token_line
from output.tokens.dto import DailyForecast, HourlyValue, MetricSpec, NormalizedForecast
from output.tokens.render import render_line_with_survivors
from utils.timezone import local_fmt, tz_for_coords


def _alert_tz_for_trip(trip_obj: Trip):
    """Best-effort timezone for alert rendering from trip coordinates."""
    stages = getattr(trip_obj, "stages", None) or []
    for stage in stages:
        waypoints = getattr(stage, "waypoints", None) or []
        for wp in waypoints:
            lat = getattr(wp, "lat", None)
            lon = getattr(wp, "lon", None)
            if lat is not None and lon is not None:
                return tz_for_coords(float(lat), float(lon))
    return timezone.utc


def _stub_segment(seg_time: Any) -> SegmentWeatherData:
    """Minimal renderer stub. Pattern from tests/unit/test_issue_131_alert_klarheit.py."""
    today = datetime.now(timezone.utc).date()
    start_h, start_m = (int(p) for p in seg_time.start.split(":"))
    end_h, end_m = (int(p) for p in seg_time.end.split(":"))
    start_dt = datetime.combine(today, time(start_h, start_m), tzinfo=timezone.utc)
    end_dt = datetime.combine(today, time(end_h, end_m), tzinfo=timezone.utc)
    segment = TripSegment(
        segment_id=seg_time.segment_id,
        start_point=GPXPoint(lat=0.0, lon=0.0, elevation_m=0),
        end_point=GPXPoint(lat=0.0, lon=0.0, elevation_m=0),
        start_time=start_dt,
        end_time=end_dt,
        duration_hours=max(0.0, (end_dt - start_dt).total_seconds() / 3600.0),
        distance_km=0.0,
        ascent_m=0.0,
        descent_m=0.0,
    )
    return SegmentWeatherData(
        segment=segment,
        timeseries=NormalizedTimeseries(
            meta=ForecastMeta(
                provider=Provider.OPENMETEO, model="validator-stub",
                run=datetime.now(timezone.utc), grid_res_km=1.0, interp="stub",
            ),
            data=[],
        ),
        aggregated=SegmentWeatherSummary(),
        fetched_at=datetime.now(timezone.utc),
        provider="openmeteo",
    )


def render_alert_preview(
    trip_obj: Trip,
    body: Any,
) -> dict:
    """Render alert preview across all channels.

    Returns a dict with subject, email_html, email_plain, telegram, sms.
    Issue #1948 Scheibe S2: ``official`` (Zweig b) und ``nowcast_frames``
    (Zweig c) sind zwei weitere exklusive Payload-Typen neben ``onset``
    und ``changes`` — der Router garantiert bereits Vier-Wege-Exklusivitaet.
    """
    if getattr(body, "official", None):
        return _render_official_preview(trip_obj, body.official)
    if getattr(body, "nowcast_frames", None) is not None:
        return _render_nowcast_replay(trip_obj, body.nowcast_frames)

    alert_tz = _alert_tz_for_trip(trip_obj)
    # Issue #2020 Scheibe 2: dieselbe Referenzzeit fuer Stand-Zeile und
    # Zeitbezug der Vorschau (Muster `notification_service`).
    now_utc = datetime.now(timezone.utc)
    stand_at = local_fmt(now_utc, alert_tz)
    has_onset = body.onset is not None

    if has_onset:
        onset_ev = OnsetEvent(
            onset_minutes=body.onset.onset_minutes,
            onset_time=body.onset.onset_time,
            km_from=body.onset.km_from,
            km_to=body.onset.km_to,
            is_convective=body.onset.is_convective,
            intensity_label=body.onset.intensity_label,
            source_label=body.onset.source_label,
            # #1948 S5 (AC-15): die Segment-Kennung des Payloads erreicht das
            # Event -- sonst faellt der Ortskopf auf "km N-M" zurueck.
            segment_id=getattr(body.onset, "segment_id", None),
            # Issue #2046: Mengenangabe der Kurznachricht. `getattr`, weil
            # dieser Zweig sowohl den API-Payload (`OnsetPayload`) als auch
            # den Replay-SimpleNamespace bedient -- Muster `segment_id` o.
            onset_precip_mm=getattr(body.onset, "onset_precip_mm", None),
        )
        msg = AlertMessage(
            trip_short=trip_obj.name,
            stand_at=stand_at,
            events=(onset_ev,),
            source=body.onset.source_label,
            cooldown_display=body.onset.cooldown_display,
        )
    else:
        changes = [
            WeatherChange(
                metric=c.metric,
                old_value=c.old_value,
                new_value=c.new_value,
                delta=c.delta,
                threshold=c.threshold,
                severity=ChangeSeverity(c.severity),
                direction=c.direction,
                segment_id=c.segment_id,
            )
            for c in body.changes
        ]
        segments = [_stub_segment(st) for st in body.segment_times]
        msg = to_alert_message(
            changes, segments, trip_obj.name,
            tz=alert_tz, stand_at=stand_at, now_utc=now_utc,
        )

    subject = render_subject(msg)
    email_html, email_plain = render_email(msg)
    telegram = render_telegram(msg)
    sms = render_sms(msg)
    return {
        "subject": subject,
        "email_html": email_html,
        "email_plain": email_plain,
        "telegram": telegram,
        "sms": sms,
    }


def _parse_official_dt(value: "str | None") -> "datetime | None":
    return None if value is None else datetime.fromisoformat(value)


def _render_official_preview(trip_obj: Trip, payloads: list) -> dict:
    """Issue #1948 Scheibe S2 (Zweig b): Render-Sequenz aus
    ``notification_service.send_official_alert`` (Z. 846-882) gespiegelt --
    der zustandslose Preview braucht weder Versandkanaele noch
    Trip-Notification-Historie. #1929-Sperrzone (``official_alerts.py``:
    1896-2104) wird ausschliesslich AUFGERUFEN, keine Zeile darin geaendert.
    """
    from services.official_alerts.models import OfficialAlert
    from output.renderers.alert.official_alerts import (
        build_official_alert_notices, render_official_alert_mail_plain,
        render_official_alert_sms, render_official_alert_subject,
        render_official_alert_telegram, render_warn_block,
    )
    from services.notification_service import (
        _official_source_label_for, _official_source_url_for,
    )

    alert_tz = _alert_tz_for_trip(trip_obj)
    tagged = [
        (
            OfficialAlert(
                source=p.source, hazard=p.hazard, level=p.level, label=p.label,
                valid_from=_parse_official_dt(p.valid_from),
                valid_to=_parse_official_dt(p.valid_to),
                url=p.url, region_label=p.region_label, dedup_id=p.dedup_id,
            ),
            p.segment_ids,
        )
        for p in payloads
    ]
    dto_notices = build_official_alert_notices(trip_obj, tagged)
    source_label = _official_source_label_for(dto_notices)
    source_url = _official_source_url_for(dto_notices)
    stand_at = local_fmt(datetime.now(timezone.utc), alert_tz)
    subject = render_official_alert_subject(dto_notices, prefix=trip_obj.name, tz=alert_tz)
    html = render_warn_block(
        dto_notices, variant="standalone", source_label=source_label,
        source_url=source_url, stand_at=stand_at, tz=alert_tz,
        context_label=trip_obj.name,
    )
    plain = render_official_alert_mail_plain(
        dto_notices, source_label=source_label, stand_at=stand_at,
        tz=alert_tz, context_label=trip_obj.name,
    )
    telegram = render_official_alert_telegram(
        dto_notices, prefix=trip_obj.name, source_label=source_label, tz=alert_tz,
    )
    sms = render_official_alert_sms(dto_notices, tz=alert_tz)
    return {
        "subject": subject, "email_html": html, "email_plain": plain,
        "telegram": telegram, "sms": sms,
    }


def _render_nowcast_replay(trip_obj: Trip, body_nf: Any) -> dict:
    """Issue #1948 Scheibe S2 (Zweig c): Replay eines Frame-Mitschnitts ueber
    dieselbe ``_derive_result``-Ableitung wie der Live-Radar-Pfad. Kein
    Onset im Fenster -> expliziter Leerbefund statt Exception/HTTP 500."""
    from types import SimpleNamespace

    from providers.brightsky import RadarFrame
    from services.radar_service import RadarNowcastService

    frames = [
        RadarFrame(
            timestamp=datetime.fromisoformat(f.timestamp),
            precip_mm_h=f.precip_mm_h, is_convective=f.is_convective,
        )
        for f in body_nf.frames
    ]
    svc = RadarNowcastService()
    now = datetime.now(timezone.utc)
    result = svc._derive_result(frames, body_nf.source, now=now)
    if result.onset_minutes is None:
        return {
            "onset_detected": False, "subject": None, "email_html": None,
            "email_plain": None, "telegram": None, "sms": None,
        }

    alert_tz = _alert_tz_for_trip(trip_obj)
    onset_time = now + timedelta(minutes=result.onset_minutes)
    onset_ns = SimpleNamespace(
        onset_minutes=result.onset_minutes,
        onset_time=local_fmt(onset_time, alert_tz)[-5:],  # "HH:MM"-Anteil
        km_from=body_nf.km_from, km_to=body_nf.km_to,
        is_convective=result.is_convective,
        intensity_label=result.intensity_label,
        source_label=RadarNowcastService._SOURCE_LABELS.get(
            result.source, result.source,
        ),
        cooldown_display=None,
        segment_id=getattr(body_nf, "segment_id", None),
        # Issue #2046: aus DEMSELBEN `_derive_result`-Ergebnis wie
        # onset_minutes/intensity_label -- der Replay-Weg muss dieselbe Zahl
        # zeigen wie der Produktivpfad (AC-10).
        onset_precip_mm=result.onset_precip_mm,
    )
    out = render_alert_preview(
        trip_obj, SimpleNamespace(onset=onset_ns, official=None, nowcast_frames=None),
    )
    out["onset_detected"] = True
    return out


def render_compare_email_preview(body: Any) -> str:
    """Render compare-email HTML for the validator without fetching weather data."""
    profile_enum = ActivityProfile(body.profile)
    target_date = date_type.fromisoformat(body.target_date)

    stub_location = SavedLocation(
        id="preview-1",
        name="Vorschau-Ort",
        lat=47.0,
        lon=11.0,
        elevation_m=2000,
    )
    loc_result = LocationResult(
        location=stub_location,
        score=85,
        error=None,
    )
    result = ComparisonResult(
        locations=[loc_result],
        time_window=(body.time_window[0], body.time_window[1]),
        target_date=target_date,
    )
    # Issue #1406 Scheibe B (AC-8): die Stundenverlauf-Auswahl wird
    # durchgereicht -- bis dahin zeigte die Vorschau immer die volle
    # Spaltenmenge und ein Nachweis ueber diesen Endpunkt sah die Wirkung der
    # Auswahl gar nicht (Muster #1435 E3b: `build_token_line()` ohne
    # `profile=`). `getattr` statt `body.hourly_metrics`, damit auch aeltere
    # Aufrufer ohne das Feld weiterhin durchlaufen.
    return render_compare_html(
        result,
        profile=profile_enum,
        hourly_enabled=body.hourly_enabled,
        hourly_metrics=getattr(body, "hourly_metrics", None),
    )


# ---------------------------------------------------------------------------
# SMS-Fidelity-Vorschau (Issue #923, ADR-0011).
# ---------------------------------------------------------------------------

# Feste Beispiel-Vorhersage fuer die Metrik-Editor-SMS-Vorschau -- kein
# Live-Wetter, keine Trip-Daten (siehe Source-Kommentar der Spec: zustandslos
# wie alert-preview/compare-email-preview). Bewusst ein Extremsturm-Szenario
# (Wind/Boeen/Niederschlag/Schnee ueber realistischen Spitzenwerten): nur so
# ueberschreitet die volle Token-Zeile aller SMS-faehigen Metriken zusammen
# die 160-Zeichen-Grenze und macht die §6-Kuerzung (AC-2) ueberhaupt sichtbar
# -- mit rein realistischen Sturmwerten bleibt die kompakte Token-Zeile fuer
# nur eine Etappe strukturell unter 160 Zeichen. Temperatur/gefuehlte
# Temperatur bleiben in einem realistischen Bereich (weniger auffaellig fuer
# Nutzer als Wind/Niederschlag/Schnee-Groessenordnungen).
# Issue #1824 (A): der Bereichs-Token ('D-12/28' statt 'K-12 D28') macht die
# Zeile um 3 Zeichen kuerzer und schob sie unter die 160er-Grenze -- die
# Kuerzung waere damit unsichtbar geworden und AC-2 haette den falschen Zweig
# geprueft. Die drei Schnee-Groessen tragen deshalb je eine Stelle mehr; sie
# waren schon vorher bewusst unrealistisch und dienen allein diesem Zweck.
SMS_FIDELITY_SAMPLE_FORECAST = NormalizedForecast(
    days=(
        DailyForecast(
            temp_min_c=-12.0, temp_max_c=28.0,
            night_temp_min_c=-15.0,
            wind_chill_min_c=-18.0, wind_chill_max_c=24.0,
            night_wind_chill_min_c=-21.0,
            wind_chill_c=-18.0,
            rain_hourly=tuple(
                HourlyValue(h, v) for h, v in zip(
                    range(6, 18),
                    (245.0, 318.0, 432.0, 555.0, 585.0, 625.0,
                     670.0, 720.0, 845.0, 660.0, 445.0, 260.0),
                )
            ),
            pop_hourly=tuple(
                HourlyValue(h, v) for h, v in zip(
                    range(6, 18), (15, 25, 35, 48, 60, 70, 82, 90, 98, 85, 60, 30),
                )
            ),
            wind_hourly=tuple(
                HourlyValue(h, v) for h, v in zip(
                    range(6, 18),
                    (850, 926, 938, 952, 970, 990, 1012, 1128, 1142, 1180, 1420, 1350),
                )
            ),
            gust_hourly=tuple(
                HourlyValue(h, v) for h, v in zip(
                    range(6, 18),
                    (1200, 1244, 1258, 1278, 1302, 1330, 1358, 1385, 1415, 1455, 2080, 1980),
                )
            ),
            thunder_hourly=tuple(
                HourlyValue(h, v) for h, v in zip(
                    range(6, 18), (0, 0, 1, 1, 2, 2, 3, 3, 3, 2, 1, 0),
                )
            ),
            # Fix #1887 E6 Scheibe A: der Wegfall von 'WC-18' (~6 Zeichen)
            # drueckte die volle Zeile von vormals 161 auf 155 Zeichen --
            # unter die 160er-Kuerzungsgrenze, wodurch die Vorschau gar
            # nichts mehr kuerzt und ihren Zweck verliert. Die 1-Zeichen-
            # Reserve von vorher war selbst die Ursache: ein einzelnes
            # entfallendes Kuerzel konnte sie kippen. Alle drei Schnee-
            # Groessen (s. Issue #1824 (A) oben) tragen deshalb je eine
            # weitere Stelle mehr -- dieselbe Technik, nur wiederholt
            # angewendet, kein neues Muster. Ergebnis (s. Testnachweis):
            # volle Zeile 176 Zeichen, gekuerzte Zeile genau 160 -- die
            # Kuerzung reizt die Grenze wieder aus, statt sie deutlich zu
            # unterschreiten.
            snow_depth_cm=2450000000000.0,
            snowfall_limit_m=9800000000000.0,
            snow_new_24h_cm=1850000000000.0,
        ),
        DailyForecast(thunder_hourly=(HourlyValue(10, 2.0),)),
    ),
)

# metric_id -> SMS-Symbol(e), die diese Metrik in der Token-Zeile traegt.
# SMS_MULTI_SYMBOLS_BY_METRIC hat Vorrang (deckt mehr Symbole ab, u.a.
# 'thunder' -> ('TH:','TH+:') statt nur 'TH:' aus SMS_SYMBOL_BY_METRIC).
def _symbols_for_metric(metric_id: str) -> tuple[str, ...]:
    syms = SMS_MULTI_SYMBOLS_BY_METRIC.get(metric_id)
    if syms is not None:
        return syms
    sym = SMS_SYMBOL_BY_METRIC.get(metric_id)
    return (sym,) if sym else ()


def build_sms_fidelity_specs(metric_ids: list[str]) -> list[MetricSpec]:
    """Disabled-Specs fuer alle nicht angefragten SMS-Symbole -- Spiegel von
    trip_report.py:283-307 (Bug #944/#1415), hier mit `metric_ids` (Editor-
    Auswahl) statt `dc.metrics` (Trip-Konfiguration) als Aktivmenge."""
    active_metric_ids = set(metric_ids)
    specs: list[MetricSpec] = [
        MetricSpec(symbol=sym, enabled=False)
        for metric_id, sym in SMS_SYMBOL_BY_METRIC.items()
        if metric_id not in active_metric_ids
    ]
    specs += [
        MetricSpec(symbol=sym, enabled=metric_id in active_metric_ids)
        for metric_id, syms in SMS_MULTI_SYMBOLS_BY_METRIC.items()
        for sym in syms
    ]
    return specs


def render_sms_fidelity_preview(metric_ids: list[str]) -> dict:
    """Rendert die SMS-Kurzform fuer die Metrik-Editor-Vorschau ueber
    dieselbe Pipeline wie der Versandpfad (build_token_line()+render_line()-
    Familie) -- kein zweiter Renderer im Frontend (ADR-0011)."""
    specs = build_sms_fidelity_specs(metric_ids)
    token_line = build_token_line(
        SMS_FIDELITY_SAMPLE_FORECAST, specs,
        report_type="evening", stage_name="Etappe",
    )
    line, survivor_symbols = render_line_with_survivors(token_line, 160)
    carried_ids = [
        metric_id for metric_id in metric_ids
        if any(sym in survivor_symbols for sym in _symbols_for_metric(metric_id))
    ]
    return {
        "line": line,
        "char_count": len(line),
        "max_length": 160,
        "carried_ids": carried_ids,
    }
