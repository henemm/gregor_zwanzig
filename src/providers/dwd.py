"""
DWD ICON-D2 Direct Provider (#1144, Slice 3/4 von Epic #1127).

Echter `de_direct`-Provider für den Cross-Provider-Fallback (#1141): ruft die
öffentliche ICON-D2-Open-Data-API (`opendata.dwd.de`, 2,2-km-Gitter,
Deutschland) direkt ab und liest die entpackten GRIB2-Antworten mit dem
bereits im Projekt vorhandenen `rasterio`/GDAL-GRIB-Treiber (keine neue
Dependency, #1143).

SPEC: docs/specs/modules/provider_dwd.md v1.0
Vorlage: src/providers/meteofrance.py (Retry-Muster, Vektor->Speed-Formel,
GRIB2-Pixel-Lookup).

ICON-D2-Open-Data-Eigenheiten (empirisch verifiziert 2026-07-23):
- Anders als bei AROME-WCS (#1143) gibt es KEINEN serverseitigen Punkt-Query
  — pro Parameter/Zeitschritt wird eine eigene, volle Rasterdatei
  (`.grib2.bz2`) geladen, 1 GET-Request je Datei. Bounded: 24h-Horizont
  (PO-Entscheidung 2026-07-23), 4 Parameter x 24 Zeitschritte = ~96 Calls
  pro Fetch — ausschließlich im Total-Ausfall-Fallback-Pfad.
- `t_2m`-Rohwert ist bereits °C, KEINE Kelvin-Umrechnung (GDAL-Tag
  `GRIB_UNIT=[C]`, empirisch bestätigt: München-Rohwert 18.11 an einem
  Sommerabend — als Kelvin wäre das -255°C, physikalisch unmöglich).
- `tot_prec` ist seit Laufbeginn kumuliert (wachsende `lengthOfTimeRange`
  0/60/120min stützt die Kumulations-Annahme). `precip_1h_mm` wird daher
  als Differenz aufeinanderfolgender Zeitschritte gebildet, NICHT wie bei
  AROME (#1143 F003) direkt übernommen — dort war der Rohwert bereits die
  1h-Regenmenge, hier nicht. Beweis (Ostsee-Küstenzelle 53.70N/14.94E,
  Lauf 2026-07-22T21Z): prev(+3h)=3.14, curr(+4h)=15.49, Differenz=12.35mm
  (kräftiger Landregen, plausibel).
"""
from __future__ import annotations

import bz2
import logging
import math
import time
from datetime import datetime, timedelta, timezone
from typing import TYPE_CHECKING, Dict, List, Optional

import httpx
from rasterio.io import MemoryFile
from tenacity import (
    before_sleep_log,
    retry,
    retry_if_exception,
    stop_after_attempt,
    wait_exponential,
)

from app.models import ForecastDataPoint, ForecastMeta, NormalizedTimeseries, Provider
from providers.base import ProviderRequestError

if TYPE_CHECKING:
    from app.config import Location

logger = logging.getLogger("dwd")

BASE_URL = "https://opendata.dwd.de/weather/nwp/icon-d2/grib/"
TIMEOUT = 30.0

RETRY_ATTEMPTS = 5
RETRY_WAIT_MIN = 2   # seconds
RETRY_WAIT_MAX = 60  # seconds
RETRY_STATUS_CODES = {500, 502, 503, 504}

# Gesamt-Zeitbudget je fetch_forecast (analog meteofrance.py F004): bis zu
# 96 sequentielle Calls x bis zu 5 Retries x 2-60s Backoff wären ohne
# Deadline theoretisch sehr lange möglich.
FETCH_DEADLINE_SECONDS = 180.0

# Bounded, konstante Anzahl Zeitschritte je Parameter (24h-Horizont,
# PO-Tech-Lead-Entscheidung 2026-07-23, analog dem FR-MVP-Vorbild).
FORECAST_HOURS: List[int] = list(range(1, 25))

PARAMS = ("t_2m", "u_10m", "v_10m", "tot_prec")


def _is_retryable_error(exception: BaseException) -> bool:
    """1:1-Muster meteofrance.py: retryable bei 500/502/503/504 +
    Connection-Errors."""
    if isinstance(exception, httpx.HTTPStatusError):
        return exception.response.status_code in RETRY_STATUS_CODES
    if isinstance(exception, (httpx.ConnectError, httpx.ReadTimeout)):
        return True
    return False


def _vector_to_speed_kmh(u: float, v: float) -> float:
    """AC-6: U/V-Windkomponenten (m/s) -> Betrag in km/h, ident zu
    meteofrance._vector_to_speed_kmh."""
    speed_ms = math.sqrt(u**2 + v**2)
    return round(speed_ms * 3.6, 1)


def _latest_run(now: datetime) -> datetime:
    """Jüngster ICON-D2-Lauf (alle 3h) mit Sicherheitsabstand, damit die
    Antwort tatsächlich veröffentlicht ist (analog meteofrance._latest_run)."""
    floored_hour = (now.hour // 3) * 3
    run = now.replace(hour=floored_hour, minute=0, second=0, microsecond=0)
    return run - timedelta(hours=3)


def _build_url(run: datetime, offset: int, param: str) -> str:
    """URL-Template (SPEC): <BASE_URL><HH>/<param>/icon-d2_germany_regular-
    lat-lon_single-level_<YYYYMMDDHH>_<TTT>_2d_<param>.grib2.bz2"""
    hh = f"{run.hour:02d}"
    run_str = run.strftime("%Y%m%d%H")
    ttt = f"{offset:03d}"
    return (
        f"{BASE_URL}{hh}/{param}/icon-d2_germany_regular-lat-lon_"
        f"single-level_{run_str}_{ttt}_2d_{param}.grib2.bz2"
    )


def _read_point_value(compressed: bytes, lat: float, lon: float) -> Optional[float]:
    """Entpackt eine `.grib2.bz2`-Antwort und liest den Pixelwert von Band 1
    an (lat, lon) — Muster meteofrance._read_point_value, ergänzt um den
    `bz2.decompress`-Schritt (ICON-D2 liefert komprimiert, AROME-WCS nicht)."""
    try:
        raw = bz2.decompress(compressed)
        with MemoryFile(raw) as memfile, memfile.open() as dataset:
            row, col = dataset.index(lon, lat)
            row = min(max(row, 0), dataset.height - 1)
            col = min(max(col, 0), dataset.width - 1)
            return float(dataset.read(1)[row, col])
    except Exception:
        logger.warning("GRIB2-Parsing fehlgeschlagen", exc_info=True)
        return None


def _precip_series_from_cumulative(raw_by_offset: Dict[int, Optional[float]]) -> Dict[int, Optional[float]]:
    """AC-5: `tot_prec` ist seit Laufbeginn kumuliert — precip_1h_mm[t] ist
    die Differenz zum vorherigen Zeitschritt, precip_1h_mm[erster
    Zeitschritt] entspricht dem Rohwert direkt (Laufbeginn implizit 0)."""
    result: Dict[int, Optional[float]] = {}
    prev_cumulative = 0.0
    for offset in sorted(raw_by_offset):
        raw = raw_by_offset[offset]
        if raw is None:
            result[offset] = None
            continue
        result[offset] = max(0.0, round(raw - prev_cumulative, 1))
        prev_cumulative = raw
    return result


class DwdDirectProvider:
    """Issue #1144: `de_direct`-Direktprovider (ICON-D2-Open-Data), direkt
    in der Registry (`providers.base._load_providers`) registriert —
    ersetzt den bisherigen `RegionalStubProvider`."""

    def __init__(self, client: Optional[httpx.Client] = None) -> None:
        self._client = client or httpx.Client(timeout=TIMEOUT)

    @property
    def name(self) -> str:
        return "de_direct"

    @retry(
        stop=stop_after_attempt(RETRY_ATTEMPTS),
        wait=wait_exponential(multiplier=1, min=RETRY_WAIT_MIN, max=RETRY_WAIT_MAX),
        retry=retry_if_exception(_is_retryable_error),
        before_sleep=before_sleep_log(logger, logging.WARNING),
        reraise=True,
    )
    def _request(self, url: str) -> bytes:
        """GET-Request mit Retry-Logik (500/502/503/504 + Connection-Errors,
        5 Versuche, 2-60s Backoff, ADR-0018: 4xx bleibt sichtbar)."""
        response = self._client.get(url)
        if response.status_code in RETRY_STATUS_CODES:
            response.raise_for_status()  # loest Retry via HTTPStatusError aus
        response.raise_for_status()  # nicht-retryable Fehler (4xx)
        return response.content

    def _fetch_series(
        self, param: str, lat: float, lon: float,
        run: datetime, deadline_at: float,
    ) -> Dict[int, Optional[float]]:
        """Ein Request je Zeitschritt (kein serverseitiger Punkt-Query, s.
        Modul-Docstring). `deadline_at` begrenzt das Gesamt-Zeitbudget des
        uebergeordneten `fetch_forecast`-Aufrufs (Muster meteofrance.py)."""
        values: Dict[int, Optional[float]] = {}
        for offset in FORECAST_HOURS:
            if time.monotonic() > deadline_at:
                raise ProviderRequestError(
                    self.name,
                    f"Gesamt-Zeitbudget ({FETCH_DEADLINE_SECONDS:.0f}s) "
                    "ueberschritten",
                )
            url = _build_url(run, offset, param)
            raw = self._request(url)
            values[offset] = _read_point_value(raw, lat, lon)
        return values

    def fetch_forecast(
        self,
        location: "Location",
        start: Optional[datetime] = None,
        end: Optional[datetime] = None,
        enrich_ensemble: bool = True,  # ignored, ICON-D2 hat kein Ensemble-API
        enrich_snow: bool = True,  # ignored, kein Snow-Datensatz in diesem Slice
    ) -> NormalizedTimeseries:
        """SPEC AC-1/AC-3/AC-4: liefert NormalizedTimeseries oder wirft
        ProviderRequestError (httpx-Fehler werden hier uebersetzt, analog
        MeteoFranceDirectProvider.fetch_forecast)."""
        run = _latest_run(datetime.now(timezone.utc))
        lat, lon = location.latitude, location.longitude
        deadline_at = time.monotonic() + FETCH_DEADLINE_SECONDS

        try:
            temps = self._fetch_series("t_2m", lat, lon, run, deadline_at)
            us = self._fetch_series("u_10m", lat, lon, run, deadline_at)
            vs = self._fetch_series("v_10m", lat, lon, run, deadline_at)
            precs_raw = self._fetch_series("tot_prec", lat, lon, run, deadline_at)
        except httpx.HTTPStatusError as e:
            raise ProviderRequestError(
                self.name, f"HTTP {e.response.status_code}: {e.response.text}",
                status_code=e.response.status_code,
            )
        except httpx.RequestError as e:
            raise ProviderRequestError(self.name, f"Request failed: {e}")

        precs = _precip_series_from_cumulative(precs_raw)

        data_points: List[ForecastDataPoint] = []
        for offset in FORECAST_HOURS:
            t = temps.get(offset)
            u = us.get(offset)
            v = vs.get(offset)
            wind_kmh = _vector_to_speed_kmh(u, v) if u is not None and v is not None else None
            data_points.append(
                ForecastDataPoint(
                    ts=run + timedelta(hours=offset),
                    t2m_c=round(t, 1) if t is not None else None,
                    wind10m_kmh=wind_kmh,
                    precip_1h_mm=precs.get(offset),
                )
            )

        meta = ForecastMeta(
            provider=Provider.DWD,
            model="ICON-D2",
            grid_res_km=2.2,
            interp="grid_point",
        )
        return NormalizedTimeseries(meta=meta, data=data_points)
