"""Radar-Nowcast-Frame-Cache -- geteilter, prozessweiter TTL-Cache fuer rohe
RadarFrame-Listen (Issue #1329, Scheibe C2).

Analog zu `weather_cache.py::get_shared_weather_cache`, aber bewusst
eigenstaendig und einfacher: kein "Covers"-Fenster-Konzept (eine
Nowcast-Frame-Serie ist keine feste Zeitspanne wie ein Forecast-Segment,
sondern eine rollierende Reihe) -- ein reiner Koordinaten-Schluessel mit
TTL genuegt.

WICHTIG (Lehre aus Adversary-Fund F001 der Vorgaenger-Scheibe C,
`weather_cache.py`-Docstring): gecacht wird AUSSCHLIESSLICH die ROHE
`list[RadarFrame]` + `source`-Label + `cached_at` -- NIEMALS ein fertiges
`NowcastResult`, weil `onset_minutes` (`radar_service.py::_derive_result`)
relativ zu `now` berechnet wird. Ein gecachtes fertiges Ergebnis wuerde bei
jedem Cache-Hit einen zunehmend falschen Onset liefern.

SPEC: docs/specs/modules/fix_1329_c2_radar_nowcast_cache.md
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from threading import Lock
from typing import Optional


@dataclass
class RadarCacheEntry:
    """Rohe Provider-Frame-Liste + Metadaten -- NIE ein abgeleitetes
    NowcastResult (Adversary-Fund F001-Lehre)."""

    frames: list
    source: str
    cached_at: datetime


class RadarNowcastCacheService:
    """Koordinaten- UND regionsbasierter TTL-Cache fuer rohe Radar-Frame-
    Listen.

    Schluessel = gerundete Koordinate + Region-Bucket (Adversary-Fund F001,
    Issue #1329 C2 -- BROKEN-Verdict behoben): eine reine Koordinaten-
    Rundung allein war NICHT ausreichend, weil zwei Koordinaten beidseits
    einer harten Routing-Grenze (z.B. RADOLAN-Rand bei lat=47.0, nur ~1m
    auseinander) auf denselben gerundeten Schluessel fallen koennen, aber
    zu VERSCHIEDENEN Regionen (und damit potenziell verschiedenen Quellen)
    gehoeren. Ohne Region im Schluessel haette der zweite Aufruf die
    Frames/Quelle des ersten geerbt, OHNE die eigene Quellenkette zu
    durchlaufen -- Kernrisiko "falsche Regen-in-X-Minuten-Aussage".

    Die Region ist eine reine, deterministische Funktion der Koordinate
    (`services.radar_service._region_bucket`, dieselbe Reihenfolge wie die
    tatsaechliche Quellenkette in `_fetch_frames_with_fallback`) und steht
    VOR dem Fetch fest -- der Aufrufer (`RadarNowcastService.get_nowcast`)
    berechnet sie und uebergibt sie explizit an `get`/`put`. `source`
    bleibt zusaetzlich als Metadatum im Eintrag (der TATSAECHLICH
    resolvte Wert nach evtl. Fallback, z.B. "minutely_15" trotz
    Region-Bucket "arome_france"), nicht als weiterer Schluesselbestandteil.

    Der ~11m-Dedup-Nutzen INNERHALB einer Region bleibt erhalten: zwei
    Koordinaten, die auf denselben gerundeten Wert fallen UND in derselben
    Region liegen, teilen sich weiterhin einen Eintrag.

    Thread-safe (interner Lock, Muster `WeatherCacheService`).
    """

    def __init__(self, ttl_seconds: int = 300) -> None:
        self._cache: dict[str, RadarCacheEntry] = {}
        self._lock = Lock()
        self._ttl_seconds = ttl_seconds

    def _key(self, lat: float, lon: float, region: str) -> str:
        # Gerundete Koordinaten (~11m Aufloesung) + Region-Bucket
        # (Adversary-Fund F001) -- beide zusammen bilden den Schluessel.
        return f"{round(lat, 4)}_{round(lon, 4)}_{region}"

    def get(self, lat: float, lon: float, region: str, now: datetime) -> Optional[RadarCacheEntry]:
        """Treffer nur wenn (now - entry.cached_at).total_seconds() <= ttl_seconds
        UND dieselbe Region."""
        key = self._key(lat, lon, region)
        with self._lock:
            entry = self._cache.get(key)
            if entry is None:
                return None
            age = (now - entry.cached_at).total_seconds()
            if age > self._ttl_seconds:
                return None
            return entry

    def put(
        self, lat: float, lon: float, region: str, frames: list, source: str, now: datetime
    ) -> None:
        if not frames:
            return  # Negativ-Ergebnisse werden NIE gecacht (Alarm-Blindheit vermeiden)
        key = self._key(lat, lon, region)
        with self._lock:
            self._cache[key] = RadarCacheEntry(frames=frames, source=source, cached_at=now)

    def clear(self) -> None:
        with self._lock:
            self._cache.clear()


# --- Process-wide shared cache (Muster weather_cache.py) --------------------

_shared_radar_cache: Optional["RadarNowcastCacheService"] = None
_shared_radar_cache_lock = Lock()


def get_shared_radar_cache(ttl_seconds: int = 300) -> "RadarNowcastCacheService":
    """Prozessweiter Singleton (thread-safe, double-checked locking) --
    TTL default 300s (unter der feinsten Quell-Aufloesung RADOLAN 5 Min,
    weit unter dem 15-Minuten-Alarmtakt): der Radar-Pfad ist der
    zeitkritischste Alarm-Pfad (Gewitter-Anzug)."""
    global _shared_radar_cache
    if _shared_radar_cache is None:
        with _shared_radar_cache_lock:
            if _shared_radar_cache is None:
                _shared_radar_cache = RadarNowcastCacheService(ttl_seconds=ttl_seconds)
    return _shared_radar_cache


def reset_shared_radar_cache_for_tests() -> None:
    """Test-only: resettet den Singleton (Test-Isolation zwischen Testfaellen)."""
    global _shared_radar_cache
    with _shared_radar_cache_lock:
        _shared_radar_cache = None
