"""Issue #2030 — Vorhersage-Mitschnitt am Verbrauchspunkt.

Zeichnet rollierend auf, WAS das System zu einem Zeitpunkt fuer welchen Ort und
welches Zeitfenster erwartete. Bei #2020 war die Frage "wann sprang die
Vorhersage von 7,4 mm auf 29,4 mm?" mit keiner vorhandenen Quelle beantwortbar;
ohne diesen Mitschnitt bleibt unentscheidbar, ob eine Schwelle zu hoch stand
oder die Vorhersage zu spaet hochkam.

Einziger Einbaupunkt ist `SegmentWeatherService._aggregate_for_segment` — die
Verbrauchsstelle, die Cache-Treffer UND frischen Abruf durchlaeuft. Der
Schreibweg ist durchgehend fail-soft: Diagnose darf Briefing und Alarm NIE
beeintraechtigen. Ablage:
`<Datenwurzel>/diagnostics/forecast_capture_YYYY-MM-DD.jsonl`, angehaengt.
"""
from __future__ import annotations

import json
import os
import re
import threading
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Optional

from app.models import SegmentWeatherSummary, TripSegment
from providers import call_log
from providers.enrichment_health import (
    OUTCOME_OK, OUTCOME_UNAVAILABLE, PATH_FORECAST_CAPTURE, log_enrichment_call,
)

DATEI_PRAEFIX = "forecast_capture_"
UNTERORDNER = "diagnostics"
AUFBEWAHRUNG_TAGE = 30
TAKT_MINUTEN = 60
HEALTH_DROSSEL_MINUTEN = 15

_DATUM_RE = re.compile(re.escape(DATEI_PRAEFIX) + r"(\d{4}-\d{2}-\d{2})\.jsonl$")

# Prozessweiter Zustand. Zulaessig, weil der Python-Kern ein Langlaeufer ist
# (Praezedenz `get_shared_weather_cache()`); nach einem Neustart schreibt jeder
# Schluessel einmal — das ist die gewuenschte Grundlinie. Der Lock ist Pflicht:
# `comparison_parallel.py:118` verbraucht aus mehreren Threads gleichzeitig.
_lock = threading.Lock()
_letzte_werte: dict[str, tuple[dict, datetime]] = {}
_letztes_prune_datum: Optional[date] = None
_letzte_health: Optional[datetime] = None


def _utcnow() -> datetime:
    """Die EINZIGE Uhr-Quelle dieses Moduls — Produktion und Test laufen
    denselben Pfad, es gibt keinen `now`-Parameter."""
    return datetime.now(timezone.utc)


def reset_capture_state() -> None:
    """Prozesszustand raeumen (Dedup-dict, Prune-Datum, Health-Drossel)."""
    global _letztes_prune_datum, _letzte_health
    with _lock:
        _letzte_werte.clear()
        _letztes_prune_datum = None
        _letzte_health = None


def _aktiv() -> bool:
    """Kill-Switch `GZ_FORECAST_CAPTURE=0` — die einzige deploy-freie
    Rueckzugsoption, wenn der Mitschnitt in Produktion auffaellig wird."""
    return os.environ.get("GZ_FORECAST_CAPTURE", "1").strip().lower() not in (
        "0", "false", "no", "off",
    )


def _werte(aggregated: SegmentWeatherSummary) -> dict:
    """Die alarmrelevanten Aggregatwerte — flache Skalare, nie Zeitreihe oder
    Stundenwerte: die Zeile muss unter 4 KiB bleiben, weil aus mehreren Threads
    in EINEM `write` angehaengt wird."""
    return {
        "precip_sum_mm": aggregated.precip_sum_mm,
        "wind_max_kmh": aggregated.wind_max_kmh,
        "gust_max_kmh": aggregated.gust_max_kmh,
        "thunder_level_max": getattr(aggregated.thunder_level_max, "value", None),
        "temp_min_c": aggregated.temp_min_c,
        "temp_max_c": aggregated.temp_max_c,
        "pop_max_pct": aggregated.pop_max_pct,
        "cape_max_jkg": aggregated.cape_max_jkg,
        "snow_new_sum_cm": aggregated.snow_new_sum_cm,
        "snowfall_limit_m": aggregated.snowfall_limit_m,
    }


def _dedup_schluessel(segment: TripSegment) -> str:
    """`lat_lon_startstunde`, gleiche Koordinatenrundung wie
    `radar_service._nowcast_source_key` — damit der Vorhersage-Mitschnitt mit
    dem bestehenden Nowcast-Mitschnitt korrelierbar ist. BEWUSST ohne
    `trip_id`: die Trennung von Trip- und Compare-Identitaet an dieser Stelle
    (#1329 F001) wird nicht aufgebrochen.

    Die Startstunde geht als VOLLER Zeitstempel ein, nicht als blosse
    Stundenzahl: auf einer mehrtaegigen Tour traefe dieselbe Uhrzeit
    verschiedener Tage sonst denselben Schluessel."""
    stunde = segment.start_time.replace(minute=0, second=0, microsecond=0)
    return (
        f"{round(segment.start_point.lat, 4)}_"
        f"{round(segment.start_point.lon, 4)}_{stunde.isoformat()}"
    )


def _schreibgrund(schluessel: str, werte: dict, jetzt: datetime) -> Optional[str]:
    """Aenderungs- PLUS Takt-Regel (Volumengrenze ~1 MB/Tag statt ~8 MB/Tag).
    Der erzwungene Takt ist kein Beiwerk: ohne ihn waere "keine Zeile"
    mehrdeutig zwischen unveraendert, Mitschnitt kaputt und Ort nie abgerufen."""
    with _lock:
        letzte = _letzte_werte.get(schluessel)
    if letzte is None or letzte[0] != werte:
        return "aenderung"
    if jetzt - letzte[1] > timedelta(minutes=TAKT_MINUTEN):
        return "takt"
    return None


def _ordner() -> Path:
    """Bei JEDEM Schreibvorgang frisch aufgeloest, nie als Modulkonstante beim
    Import gebunden (Falle #1633)."""
    from app.loader import get_data_root

    return get_data_root() / UNTERORDNER


def _prune(ordner: Path, heute: date) -> None:
    """Tagesdateien aelter als 30 Tage entfernen — enger Glob PLUS Datums-Regex,
    damit Nachbardateien (`openmeteo_calls.jsonl`, `enrichment_calls.jsonl`) und
    undatierte Namensvettern unangetastet bleiben (#1987-Falle)."""
    grenze = heute - timedelta(days=AUFBEWAHRUNG_TAGE)
    for pfad in ordner.glob(f"{DATEI_PRAEFIX}*.jsonl"):
        treffer = _DATUM_RE.search(pfad.name)
        if treffer is None:
            continue
        try:
            datum = date.fromisoformat(treffer.group(1))
        except ValueError:
            continue
        if datum < grenze:
            pfad.unlink()


def _anhaengen(zeile: str, jetzt: datetime) -> None:
    """Eine Zeile in EINEM `write` an die Tagesdatei anhaengen. Der Prune laeuft
    nur beim Datumswechsel — nicht bei jedem Schreibvorgang (AC-6b)."""
    global _letztes_prune_datum
    ordner = _ordner()
    ordner.mkdir(parents=True, exist_ok=True)
    heute = jetzt.date()
    with _lock:
        faellig = _letztes_prune_datum != heute
        _letztes_prune_datum = heute
    if faellig:
        _prune(ordner, heute)
    pfad = ordner / f"{DATEI_PRAEFIX}{heute.isoformat()}.jsonl"
    with pfad.open("a", encoding="utf-8") as fh:
        fh.write(zeile + "\n")


def _melde(outcome: str, jetzt: datetime) -> None:
    """Ausfall-Sichtbarkeit nach ADR-0018, gedrosselt auf hoechstens eine
    Meldung je 15 Minuten — `enrichment_calls.jsonl` bleibt unrotiert und wird
    bei JEDEM Status-Abruf komplett gescannt."""
    global _letzte_health
    with _lock:
        if _letzte_health is not None and (
            jetzt - _letzte_health <= timedelta(minutes=HEALTH_DROSSEL_MINUTEN)
        ):
            return
        _letzte_health = jetzt
    log_enrichment_call(PATH_FORECAST_CAPTURE, outcome)


def capture_segment_forecast(
    *, segment: TripSegment, aggregated: SegmentWeatherSummary,
    fetched_at: datetime, cache_hit: bool, provider: str, model: str,
) -> bool:
    """Einen Verbrauch mitschneiden, wenn er schreibwuerdig ist. Gibt True
    zurueck, wenn eine Zeile geschrieben wurde. Wirft NIE nach aussen — der
    Aufrufer liegt im heissen Pfad von Briefing und Alarm."""
    try:
        if not _aktiv():
            return False
        jetzt = _utcnow()
        werte = _werte(aggregated)
        schluessel = _dedup_schluessel(segment)
        grund = _schreibgrund(schluessel, werte, jetzt)
        if grund is None:
            return False
        # Erst JETZT aufloesen: `resolve_call_source()` nutzt `inspect.stack()`
        # und ist teuer — im uebersprungenen Fall darf es nie laufen (AC-12).
        zeile = json.dumps({
            "written_at": jetzt.isoformat(),
            "fetched_at": fetched_at.isoformat(),
            "cache_hit": bool(cache_hit),
            "grund": grund,
            "lat": segment.start_point.lat,
            "lon": segment.start_point.lon,
            "segment_id": segment.segment_id,
            "fenster_start": segment.start_time.isoformat(),
            "fenster_ende": segment.end_time.isoformat(),
            "day_window_start_hour": segment.day_window_start_hour,
            "day_window_end_hour": segment.day_window_end_hour,
            "provider": provider,
            "model": model,
            "source": call_log.resolve_call_source(),
            "werte": werte,
        })
        _anhaengen(zeile, jetzt)
        # Erst NACH erfolgreichem Schreiben fortschreiben: ein Stand, der nie in
        # der Datei landete, darf nicht als "zuletzt geschrieben" gelten -- sonst
        # verschluckt ein einzelner Schreibfehler die naechste echte Aenderung.
        with _lock:
            _letzte_werte[schluessel] = (werte, jetzt)
        _melde(OUTCOME_OK, jetzt)
        return True
    except Exception:
        # Fail-soft Stufe 1 (Stufe 2 sitzt an der Aufrufstelle): ein Ausfall
        # darf nicht stumm bleiben (ADR-0018), aber auch nichts blockieren.
        try:
            _melde(OUTCOME_UNAVAILABLE, _utcnow())
        except Exception:
            pass
        return False
