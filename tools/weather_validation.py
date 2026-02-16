#!/usr/bin/env python3
"""
Weather Validation Tool — Vergleicht Gregor-Zwanziger-Daten mit Referenzquellen.

Referenzquellen:
- OpenMeteo direkt (gleiche API, gleiche Koordinaten, ohne Pipeline-Transformation)
- yr.no (Norwegisches Met-Institut, unabhaengiges Modell)

Verwendung:
    uv run python3 tools/weather_validation.py                    # Alle aktiven Trips
    uv run python3 tools/weather_validation.py --trip gr221-mallorca
    uv run python3 tools/weather_validation.py --lat 39.77 --lon 2.72 --date 2026-02-16
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import date, timedelta
from typing import Optional

import httpx


def fetch_openmeteo(lat: float, lon: float, target_date: str, endpoint: str = "/v1/meteofrance") -> dict:
    """Fetch hourly data directly from OpenMeteo API using dedicated endpoint."""
    params = {
        "latitude": lat,
        "longitude": lon,
        "hourly": "temperature_2m,wind_gusts_10m,cloud_cover,precipitation",
        "timezone": "UTC",
        "start_date": target_date,
        "end_date": target_date,
    }
    r = httpx.get(f"https://api.open-meteo.com{endpoint}", params=params, timeout=15)
    data = r.json()
    if "error" in data:
        return {"error": data.get("reason", str(data))}
    h = data["hourly"]
    return {
        "source": f"OpenMeteo ({endpoint})",
        "elevation": data.get("elevation"),
        "hours": {
            i: {
                "temp": h["temperature_2m"][i],
                "gust": h["wind_gusts_10m"][i],
                "cloud": h["cloud_cover"][i],
                "precip": h["precipitation"][i],
            }
            for i in range(24)
        },
    }


def fetch_yrno(lat: float, lon: float, target_date: str) -> dict:
    """Fetch hourly data from yr.no (Norwegian Met Institute)."""
    headers = {"User-Agent": "GregorZwanziger/1.0 weather-validation"}
    r = httpx.get(
        f"https://api.met.no/weatherapi/locationforecast/2.0/compact?lat={lat}&lon={lon}",
        headers=headers,
        timeout=15,
    )
    if r.status_code != 200:
        return {"error": f"HTTP {r.status_code}"}

    data = r.json()
    hours = {}
    for entry in data["properties"]["timeseries"]:
        ts = entry["time"]
        if target_date not in ts:
            continue
        hour = int(ts[11:13])
        d = entry["data"]["instant"]["details"]
        hours[hour] = {
            "temp": d.get("air_temperature"),
            "wind_kmh": round(d["wind_speed"] * 3.6, 1) if d.get("wind_speed") else None,
            "gust": round(d["wind_speed_of_gust"] * 3.6, 1) if d.get("wind_speed_of_gust") else None,
            "cloud": d.get("cloud_area_fraction"),
        }
    return {"source": "yr.no", "hours": hours}


def fetch_gregor_pipeline(trip_id: str, report_type: str) -> list[dict]:
    """Fetch data through our pipeline for comparison."""
    from app.loader import load_all_trips
    from services.trip_report_scheduler import TripReportSchedulerService

    service = TripReportSchedulerService()
    trips = load_all_trips()
    trip = next((t for t in trips if t.id == trip_id), None)
    if not trip:
        return []

    target = service._get_target_date(report_type)
    stage = trip.get_stage_for_date(target)
    if not stage:
        return []

    segments = service._convert_trip_to_segments(trip, target)
    weather = service._fetch_weather(segments)

    results = []
    for wd in weather:
        seg_hours = {}
        for dp in wd.timeseries.data:
            seg_hours[dp.ts.hour] = {
                "temp": dp.t2m_c,
                "gust": dp.gust_kmh,
                "cloud": dp.cloud_total_pct,
            }
        results.append({
            "segment_id": wd.segment.segment_id,
            "start_lat": wd.segment.start_point.lat,
            "start_lon": wd.segment.start_point.lon,
            "start_elev": wd.segment.start_point.elevation_m,
            "end_lat": wd.segment.end_point.lat,
            "end_lon": wd.segment.end_point.lon,
            "end_elev": wd.segment.end_point.elevation_m,
            "model": wd.timeseries.meta.model,
            "agg_temp_min": wd.aggregated.temp_min_c,
            "agg_temp_max": wd.aggregated.temp_max_c,
            "agg_gust_max": wd.aggregated.gust_max_kmh,
            "hours": seg_hours,
            "time_window": f"{wd.segment.start_time.strftime('%H:%M')}-{wd.segment.end_time.strftime('%H:%M')}",
        })
    return results


def day_summary(hours: dict, hour_range: tuple[int, int] = (8, 18)) -> dict:
    """Compute day summary (min/max/avg) for given hour range."""
    lo, hi = hour_range
    temps = [h["temp"] for hr, h in hours.items() if lo <= hr <= hi and h.get("temp") is not None]
    gusts = [h["gust"] for hr, h in hours.items() if lo <= hr <= hi and h.get("gust") is not None]
    clouds = [h["cloud"] for hr, h in hours.items() if lo <= hr <= hi and h.get("cloud") is not None]
    return {
        "temp_min": min(temps) if temps else None,
        "temp_max": max(temps) if temps else None,
        "gust_max": max(gusts) if gusts else None,
        "cloud_avg": round(sum(clouds) / len(clouds)) if clouds else None,
    }


def print_comparison(
    label: str,
    lat: float,
    lon: float,
    target_date: str,
    pipeline_data: Optional[list] = None,
):
    """Print comparison table for a single location."""
    print(f"\n{'='*70}")
    print(f"  {label}")
    print(f"  Koordinaten: {lat:.4f}N, {lon:.4f}E | Datum: {target_date}")
    print(f"{'='*70}")

    # Reference sources
    openmeteo = fetch_openmeteo(lat, lon, target_date, endpoint="/v1/meteofrance")
    yrno = fetch_yrno(lat, lon, target_date)

    sources = []
    if "error" not in openmeteo:
        s = day_summary(openmeteo["hours"])
        s["name"] = f"OpenMeteo /v1/meteofrance (elev={openmeteo.get('elevation')}m)"
        sources.append(s)
    if "error" not in yrno:
        s = day_summary(yrno["hours"])
        s["name"] = "yr.no (unabhaengig)"
        sources.append(s)

    # Pipeline data (last segment for this location)
    if pipeline_data:
        last = pipeline_data[-1]
        s = day_summary(last["hours"])
        seg_s = day_summary(last["hours"], (
            int(last["time_window"].split("-")[0].split(":")[0]),
            int(last["time_window"].split("-")[1].split(":")[0]),
        ))
        s["name"] = (
            f"Gregor Pipeline (Seg{last['segment_id']}, "
            f"start={last['start_elev']:.0f}m, {last['model']})"
        )
        s["seg_temp_max"] = seg_s["temp_max"]
        s["time_window"] = last["time_window"]
        sources.append(s)

    # Print table
    print(f"\n  {'Quelle':<45} | T max | T min | Gust  | Cloud")
    print(f"  {'-'*45}-|-------|-------|-------|------")
    for s in sources:
        t_max = f"{s['temp_max']:5.1f}" if s["temp_max"] is not None else "  n/a"
        t_min = f"{s['temp_min']:5.1f}" if s["temp_min"] is not None else "  n/a"
        g_max = f"{s['gust_max']:5.1f}" if s["gust_max"] is not None else "  n/a"
        c_avg = f"{s['cloud_avg']:3d}%" if s["cloud_avg"] is not None else " n/a"
        print(f"  {s['name']:<45} | {t_max} | {t_min} | {g_max} | {c_avg}")
        if "seg_temp_max" in s:
            tw = s["time_window"]
            st = s["seg_temp_max"]
            st_s = f"{st:5.1f}" if st is not None else "  n/a"
            print(f"    ↳ Aggregiert nur {tw:<30} | {st_s} |       |       |")

    # Discrepancy check
    if len(sources) >= 2 and sources[0]["temp_max"] is not None:
        ref = sources[0]["temp_max"]
        for s in sources[1:]:
            if s["temp_max"] is not None:
                diff = s["temp_max"] - ref
                if abs(diff) > 2.0:
                    print(f"\n  ⚠️  ABWEICHUNG: {s['name']}")
                    print(f"      T max Differenz: {diff:+.1f}°C vs {sources[0]['name']}")

    print()


def validate_trip(trip_id: str, report_type: str = "morning"):
    """Validate all waypoints of a trip against reference sources."""
    from app.loader import load_all_trips
    from services.trip_report_scheduler import TripReportSchedulerService

    service = TripReportSchedulerService()
    trips = load_all_trips()
    trip = next((t for t in trips if t.id == trip_id), None)
    if not trip:
        print(f"Trip '{trip_id}' nicht gefunden.")
        return

    target = service._get_target_date(report_type)
    stage = trip.get_stage_for_date(target)
    if not stage:
        print(f"Keine Stage fuer {target} in Trip '{trip_id}'.")
        return

    target_str = target.isoformat()

    # Get pipeline data
    pipeline_data = fetch_gregor_pipeline(trip_id, report_type)

    print(f"\n{'#'*70}")
    print(f"  WEATHER VALIDATION: {trip.name}")
    print(f"  Stage: {stage.name} | Datum: {target_str} | Report: {report_type}")
    print(f"{'#'*70}")

    # Validate each waypoint
    for i, wp in enumerate(stage.waypoints):
        seg_data = None
        # Find matching segment (where this waypoint is start_point)
        if pipeline_data:
            for seg in pipeline_data:
                if abs(seg["start_lat"] - wp.lat) < 0.001 and abs(seg["start_lon"] - wp.lon) < 0.001:
                    seg_data = [seg]
                    break

        print_comparison(
            f"Waypoint {wp.id}: {wp.name} ({wp.elevation_m}m)",
            wp.lat,
            wp.lon,
            target_str,
            pipeline_data=seg_data,
        )

    # Also validate endpoint (last waypoint) separately if it's different
    last_wp = stage.waypoints[-1]
    if pipeline_data:
        last_seg = pipeline_data[-1]
        if abs(last_seg["end_lat"] - last_wp.lat) > 0.001:
            print_comparison(
                f"⚡ ENDPUNKT {last_wp.name} ({last_wp.elevation_m}m) — KEIN eigenes Segment!",
                last_wp.lat,
                last_wp.lon,
                target_str,
            )


def validate_point(lat: float, lon: float, target_date: str):
    """Validate a single point against reference sources."""
    print_comparison(f"Punkt ({lat}, {lon})", lat, lon, target_date)


def main():
    parser = argparse.ArgumentParser(description="Weather Validation Tool")
    parser.add_argument("--trip", help="Trip ID to validate")
    parser.add_argument("--report", default="morning", choices=["morning", "evening"])
    parser.add_argument("--lat", type=float, help="Latitude for point validation")
    parser.add_argument("--lon", type=float, help="Longitude for point validation")
    parser.add_argument("--date", help="Date (YYYY-MM-DD) for point validation")
    args = parser.parse_args()

    if args.lat and args.lon:
        target_date = args.date or date.today().isoformat()
        validate_point(args.lat, args.lon, target_date)
    elif args.trip:
        validate_trip(args.trip, args.report)
    else:
        # Validate all active trips
        from app.loader import load_all_trips
        from services.trip_report_scheduler import TripReportSchedulerService

        service = TripReportSchedulerService()
        for report_type in ("morning", "evening"):
            active = service._get_active_trips(report_type)
            for trip in active:
                validate_trip(trip.id, report_type)


if __name__ == "__main__":
    main()
