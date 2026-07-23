"""
Météo-France AROME Direct Provider (#1143, Slice 2/4 von Epic #1127).

Echter `fr_direct`-Provider für den Cross-Provider-Fallback (#1141): ruft die
öffentliche Météo-France-WCS-API für das AROME-HIGHRES-Modell (0,01 Grad
Frankreich) direkt ab und liest die GRIB2-Antworten mit dem bereits im
Projekt vorhandenen `rasterio`/GDAL-GRIB-Treiber (keine neue Dependency).

SPEC: docs/specs/modules/provider_meteofrance.md v1.0
Vorlage: src/providers/geosphere.py (Retry-Muster, Vektor->Speed-Formel).

WCS-Eigenheiten (empirisch verifiziert 2026-07-22 gegen die Live-API):
- `subset=time(...)` akzeptiert NUR einen einzelnen Zeitwert pro Aufruf
  ("Slicing on time is mandatory: only a 2D coverage can be downloaded") —
  ein Multi-Zeitschritt-Request in einem Call ist technisch nicht möglich,
  anders als in der Spec zunächst angenommen. Der Provider ruft daher pro
  Parameter und Zeitschritt einen eigenen `GetCoverage`-Request ab, begrenzt
  auf `FORECAST_HOURS` (bounded: 24h-Horizont, 4 Parameter x 24 Zeitschritte
  = 96 Calls pro Fetch — ausschließlich im Totalausfall-Fallback-Pfad,
  PO-Entscheidung 2026-07-23, Nachfolger von zuvor 6h/~24 Calls).
- TOTAL_PRECIPITATION-Semantik EMPIRISCH GEMESSEN UND KORRIGIERT (Adversary
  #1143 F003, Runde 2, 2026-07-23, gegen die Live-API, Coverage
  `TOTAL_PRECIPITATION__GROUND_OR_WATER_SURFACE___<run>_PT1H`): das GRIB-
  GDAL-Tag `GRIB_UNIT` = `[kg/(m^2*s)]` ist ein generisches Fehletikett —
  die tatsaechliche Semantik ergibt sich aus dem GRIB-PDS-Feld
  `typeOfStatisticalProcessing=1` ("Accumulation") mit
  `lengthOfTimeRange=1h`: der Rohwert IST bereits die 1h-Regenmenge in
  kg/m^2 (= mm), KEINE Rate. Beweis: Alpenzelle 44.04N/7.84E,
  2026-07-23T15:00Z, Rohwert `5.178` — `5.178 * 3600` = 18641,6 mm/h
  (physikalisch unmoeglich, waere ein katastrophaler Starkregen um den
  Faktor >1000 zu hoch), Direktwert `5.178` mm/h (plausibel, entspricht
  kraeftigem Gewitterregen). Konsequenz: `precip_1h_mm` wird DIREKT aus dem
  Rohwert uebernommen (gerundet, floor 0.0), OHNE `* 3600`. Die zuvor als
  AC-7-Hilfsfunktion vorgehaltene `_precip_1h_from_cumulative`
  (Differenzbildung ueber eine kumulierte Reihe) traf auf diese Coverage
  NICHT zu und wurde als toter Code entfernt (nie aus `fetch_forecast`
  aufgerufen).
"""
from __future__ import annotations

import logging
import math
import os
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

logger = logging.getLogger("meteofrance")

BASE_URL = (
    "https://public-api.meteofrance.fr/public/arome/1.0/wcs/"
    "MF-NWP-HIGHRES-AROME-001-FRANCE-WCS/"
)
TIMEOUT = 30.0

RETRY_ATTEMPTS = 5
RETRY_WAIT_MIN = 2   # seconds
RETRY_WAIT_MAX = 60  # seconds
# 500 ergaenzt (Adversary #1143 F002): der Spike dokumentierte sporadische
# 500 ("backend error") als reales Live-Symptom des WCS-Backends, das ohne
# Aufnahme in diese Menge 0 statt 5 Retries ausgeloest haette.
RETRY_STATUS_CODES = {500, 502, 503, 504}

# Gesamt-Zeitbudget je fetch_forecast (Adversary #1143 F004): ohne Deadline
# waeren bis zu 96 sequentielle Calls x bis zu 5 Retries x 2-60s Backoff
# theoretisch >90 Min moeglich. Minimal gehalten: einfache Wall-Clock-Grenze,
# bei Ueberschreitung sofortiger Abbruch mit ProviderRequestError statt
# endlos weiterer Calls.
FETCH_DEADLINE_SECONDS = 180.0

# Bounded, konstante Anzahl Zeitschritte je Parameter (siehe Modul-Docstring
# zur "nur ein Zeitwert pro Call"-Einschränkung der Live-API). 24h-Horizont
# (PO-Entscheidung 2026-07-23, Nachfolger von zuvor 1..6).
FORECAST_HOURS: List[int] = list(range(1, 25))

TEMPERATURE_COVERAGE = "TEMPERATURE__SPECIFIC_HEIGHT_LEVEL_ABOVE_GROUND"
U_WIND_COVERAGE = "U_COMPONENT_OF_WIND__SPECIFIC_HEIGHT_LEVEL_ABOVE_GROUND"
V_WIND_COVERAGE = "V_COMPONENT_OF_WIND__SPECIFIC_HEIGHT_LEVEL_ABOVE_GROUND"
PRECIP_COVERAGE = "TOTAL_PRECIPITATION__GROUND_OR_WATER_SURFACE"


def _is_retryable_error(exception: BaseException) -> bool:
    """1:1-Muster geosphere.py: retryable bei 502/503/504 + Connection-Errors."""
    if isinstance(exception, httpx.HTTPStatusError):
        return exception.response.status_code in RETRY_STATUS_CODES
    if isinstance(exception, (httpx.ConnectError, httpx.ReadTimeout)):
        return True
    return False


def _vector_to_speed_kmh(u: float, v: float) -> float:
    """AC-6: U/V-Windkomponenten (m/s) -> Betrag in km/h, ident zu
    geosphere._vector_to_speed_kmh."""
    speed_ms = math.sqrt(u**2 + v**2)
    return round(speed_ms * 3.6, 1)


def _latest_run(now: datetime) -> datetime:
    """Jüngster AROME-Lauf (alle 3h) mit Sicherheitsabstand, damit die
    WCS-Antwort tatsächlich veröffentlicht ist (empirisch verifiziert
    2026-07-22: ein ~4-5h alter Lauf war verfügbar)."""
    floored_hour = (now.hour // 3) * 3
    run = now.replace(hour=floored_hour, minute=0, second=0, microsecond=0)
    return run - timedelta(hours=3)


def _run_str(run: datetime) -> str:
    """Coverage-ID-Zeitformat, z.B. '2026-07-22T18.00.00Z'."""
    return run.strftime("%Y-%m-%dT%H.%M.%SZ")


def _read_point_value(raw: bytes, lat: float, lon: float) -> Optional[float]:
    """Liest den Pixelwert von Band 1 an (lat, lon) aus GRIB2-Rohbytes."""
    try:
        with MemoryFile(raw) as memfile, memfile.open() as dataset:
            row, col = dataset.index(lon, lat)
            row = min(max(row, 0), dataset.height - 1)
            col = min(max(col, 0), dataset.width - 1)
            return float(dataset.read(1)[row, col])
    except Exception:
        logger.warning("GRIB2-Parsing fehlgeschlagen", exc_info=True)
        return None


class MeteoFranceDirectProvider:
    """Issue #1143: `fr_direct`-Direktprovider (AROME-WCS), direkt in der
    Registry (`providers.base._load_providers`) registriert — keine
    Stub-Adapter-Zwischenschicht mehr wie zuvor bei RegionalStubProvider."""

    def __init__(self, client: Optional[httpx.Client] = None) -> None:
        self._client = client or httpx.Client(
            timeout=TIMEOUT,
            headers={"apikey": os.environ.get("GZ_METEOFRANCE_APIKEY", "")},
        )

    @property
    def name(self) -> str:
        return "fr_direct"

    @retry(
        stop=stop_after_attempt(RETRY_ATTEMPTS),
        wait=wait_exponential(multiplier=1, min=RETRY_WAIT_MIN, max=RETRY_WAIT_MAX),
        retry=retry_if_exception(_is_retryable_error),
        before_sleep=before_sleep_log(logger, logging.WARNING),
        reraise=True,
    )
    def _request(
        self, coverage_id: str, lat: float, lon: float,
        height: Optional[int], time_str: str,
    ) -> bytes:
        """GetCoverage-Request mit Retry-Logik (SPEC: api_retry.md-Muster,
        502/503/504 + Connection-Errors, 5 Versuche, 2-60s Backoff)."""
        params: list[tuple[str, str]] = [
            ("service", "WCS"),
            ("version", "2.0.1"),
            ("coverageId", coverage_id),
            ("format", "application/wmo-grib"),
            ("subset", f"long({lon - 0.05:.4f},{lon + 0.05:.4f})"),
            ("subset", f"lat({lat - 0.05:.4f},{lat + 0.05:.4f})"),
        ]
        if height is not None:
            params.append(("subset", f"height({height})"))
        params.append(("subset", f"time({time_str})"))

        response = self._client.get(f"{BASE_URL}GetCoverage", params=params)
        if response.status_code in RETRY_STATUS_CODES:
            response.raise_for_status()  # loest Retry via HTTPStatusError aus
        response.raise_for_status()  # nicht-retryable Fehler (4xx)
        return response.content

    def _fetch_series(
        self, coverage_id: str, lat: float, lon: float,
        run: datetime, height: Optional[int], deadline_at: float,
    ) -> Dict[int, Optional[float]]:
        """Ein Request je Zeitschritt (Live-API erlaubt keinen
        Multi-Zeitschritt-Request, s. Modul-Docstring).

        F004 (Adversary #1143): `deadline_at` ist ein `time.monotonic()`-
        Zeitpunkt fuer das Gesamt-Zeitbudget des uebergeordneten
        `fetch_forecast`-Aufrufs; vor jedem Request wird geprueft, ob das
        Budget bereits ausgeschoepft ist (verhindert Worst-Case-Laufzeiten
        ueber viele Dutzend Calls x Retries hinweg)."""
        values: Dict[int, Optional[float]] = {}
        for offset in FORECAST_HOURS:
            if time.monotonic() > deadline_at:
                raise ProviderRequestError(
                    self.name,
                    f"Gesamt-Zeitbudget ({FETCH_DEADLINE_SECONDS:.0f}s) "
                    "ueberschritten",
                )
            time_str = (run + timedelta(hours=offset)).strftime("%Y-%m-%dT%H:%M:%SZ")
            raw = self._request(coverage_id, lat, lon, height, time_str)
            values[offset] = _read_point_value(raw, lat, lon)
        return values

    def fetch_forecast(
        self,
        location: "Location",
        start: Optional[datetime] = None,
        end: Optional[datetime] = None,
        enrich_ensemble: bool = True,  # ignored, AROME hat kein Ensemble-API
        enrich_snow: bool = True,  # ignored, kein Snow-Datensatz in diesem Slice
    ) -> NormalizedTimeseries:
        """SPEC AC-1/AC-3/AC-4: liefert NormalizedTimeseries oder wirft
        ProviderRequestError (httpx-Fehler werden hier uebersetzt, analog
        GeoSphereProvider.fetch_forecast)."""
        run = _latest_run(datetime.now(timezone.utc))
        run_str = _run_str(run)
        lat, lon = location.latitude, location.longitude
        deadline_at = time.monotonic() + FETCH_DEADLINE_SECONDS

        try:
            temps = self._fetch_series(f"{TEMPERATURE_COVERAGE}___{run_str}", lat, lon, run, height=2, deadline_at=deadline_at)
            us = self._fetch_series(f"{U_WIND_COVERAGE}___{run_str}", lat, lon, run, height=10, deadline_at=deadline_at)
            vs = self._fetch_series(f"{V_WIND_COVERAGE}___{run_str}", lat, lon, run, height=10, deadline_at=deadline_at)
            precs = self._fetch_series(f"{PRECIP_COVERAGE}___{run_str}_PT1H", lat, lon, run, height=None, deadline_at=deadline_at)
        except httpx.HTTPStatusError as e:
            raise ProviderRequestError(
                self.name, f"HTTP {e.response.status_code}: {e.response.text}",
                status_code=e.response.status_code,
            )
        except httpx.RequestError as e:
            raise ProviderRequestError(self.name, f"Request failed: {e}")

        data_points: List[ForecastDataPoint] = []
        for offset in FORECAST_HOURS:
            t = temps.get(offset)
            u = us.get(offset)
            v = vs.get(offset)
            p = precs.get(offset)
            wind_kmh = _vector_to_speed_kmh(u, v) if u is not None and v is not None else None
            # F003 (Adversary #1143 Runde 2): Rohwert ist bereits die
            # 1h-Akkumulation in mm (typeOfStatisticalProcessing=1,
            # lengthOfTimeRange=1h) — KEIN *3600 (s. Modul-Docstring).
            precip_mm = max(0.0, round(p, 1)) if p is not None else None
            data_points.append(
                ForecastDataPoint(
                    ts=run + timedelta(hours=offset),
                    t2m_c=round(t, 1) if t is not None else None,
                    wind10m_kmh=wind_kmh,
                    precip_1h_mm=precip_mm,
                )
            )

        meta = ForecastMeta(
            provider=Provider.METEOFRANCE,
            model="AROME-HIGHRES",
            grid_res_km=1.3,
            interp="grid_point",
        )
        return NormalizedTimeseries(meta=meta, data=data_points)
