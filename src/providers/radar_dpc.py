"""
Radar-DPC (Protezione Civile) Precipitation Nowcast Provider — Italy.

Fetches the latest national SRI radar product (surface rain intensity, mm/h) from
the Italian Protezione Civile radar API and extracts the rain rate at a single
coordinate via GeoTIFF point sampling.

3-step REST flow against https://radar-api.protezionecivile.it/:
  1. GET  /findLastProductByType?type=SRI  -> last available product timestamp
  2. POST /downloadProduct                 -> presigned S3 URL for the GeoTIFF
  3. GET  <S3-URL>                          -> raw GeoTIFF bytes

Feature: Issue #1162
SPEC: docs/specs/modules/issue_1162_radar_dpc.md
"""
from __future__ import annotations

import io
import logging
from datetime import datetime, timezone

import httpx
from tenacity import (
    before_sleep_log,
    retry,
    retry_if_exception,
    stop_after_attempt,
    wait_exponential,
)

from providers.brightsky import RadarFrame

logger = logging.getLogger("radar_dpc")

BASE_URL = "https://radar-api.protezionecivile.it"
TIMEOUT = 20.0

# Retry configuration (SPEC: docs/specs/modules/api_retry.md), mirrors GeoSphere.
RETRY_ATTEMPTS = 5
RETRY_WAIT_MIN = 2
RETRY_WAIT_MAX = 60
RETRY_STATUS_CODES = {502, 503, 504}

# SRI GeoTIFF nodata sentinel (ds.nodata is unset; raster encodes -9999 for
# "no radar coverage"). Values below zero are treated as dry.
_NODATA = -9990.0


def _is_retryable_error(exception: BaseException) -> bool:
    if isinstance(exception, httpx.HTTPStatusError):
        return exception.response.status_code in RETRY_STATUS_CODES
    if isinstance(exception, (httpx.ConnectError, httpx.ReadTimeout)):
        return True
    return False


class RadarDPCProvider:
    """Italian national radar nowcast (SRI product) via Protezione Civile API."""

    @property
    def name(self) -> str:
        return "radar_dpc"

    @retry(
        stop=stop_after_attempt(RETRY_ATTEMPTS),
        wait=wait_exponential(multiplier=1, min=RETRY_WAIT_MIN, max=RETRY_WAIT_MAX),
        retry=retry_if_exception(_is_retryable_error),
        before_sleep=before_sleep_log(logger, logging.WARNING),
        reraise=True,
    )
    def _find_last_product(self, client: httpx.Client) -> int:
        """Return the millisecond UTC timestamp of the latest SRI product."""
        resp = client.get(
            f"{BASE_URL}/findLastProductByType", params={"type": "SRI"}
        )
        resp.raise_for_status()
        products = resp.json().get("lastProducts", [])
        return int(products[0]["time"])

    @retry(
        stop=stop_after_attempt(RETRY_ATTEMPTS),
        wait=wait_exponential(multiplier=1, min=RETRY_WAIT_MIN, max=RETRY_WAIT_MAX),
        retry=retry_if_exception(_is_retryable_error),
        before_sleep=before_sleep_log(logger, logging.WARNING),
        reraise=True,
    )
    def _download_url(self, client: httpx.Client, product_ms: int) -> str:
        """Return the presigned S3 URL for the SRI GeoTIFF at product_ms."""
        resp = client.post(
            f"{BASE_URL}/downloadProduct",
            json={"productType": "SRI", "productDate": product_ms},
        )
        resp.raise_for_status()
        return resp.json()["url"]

    @retry(
        stop=stop_after_attempt(RETRY_ATTEMPTS),
        wait=wait_exponential(multiplier=1, min=RETRY_WAIT_MIN, max=RETRY_WAIT_MAX),
        retry=retry_if_exception(_is_retryable_error),
        before_sleep=before_sleep_log(logger, logging.WARNING),
        reraise=True,
    )
    def _download_tif(self, client: httpx.Client, url: str) -> bytes:
        """Download the raw GeoTIFF bytes from the presigned S3 URL.

        Same connect/timeout retry as steps 1/2; presigned S3 responses do not
        surface the 502/503/504 API statuses, but _is_retryable_error still
        covers ConnectError/ReadTimeout here.
        """
        resp = client.get(url)
        resp.raise_for_status()
        return resp.content

    def fetch_nowcast(self, lat: float, lon: float) -> list[RadarFrame]:
        """
        Fetch the latest SRI radar rain rate at a coordinate.

        Returns a single-element list with one RadarFrame (SRI is an observation
        snapshot, not a time series). Empty list on any failure (fail-soft).
        """
        try:
            import rasterio
            from rasterio.warp import transform

            with httpx.Client(timeout=TIMEOUT) as client:
                product_ms = self._find_last_product(client)
                url = self._download_url(client, product_ms)
                tif_bytes = self._download_tif(client, url)

            with rasterio.open(io.BytesIO(tif_bytes)) as dataset:
                # SRI raster is a projected (Transverse Mercator) grid, not lon/lat —
                # reproject the query point into the dataset CRS before sampling.
                xs, ys = transform("EPSG:4326", dataset.crs, [lon], [lat])
                row, col = dataset.index(xs[0], ys[0])
                height, width = dataset.shape
                if not (0 <= row < height and 0 <= col < width):
                    return []
                raw = float(dataset.read(1)[row, col])

            if raw != raw or raw <= _NODATA or raw < 0.0:
                precip_mm_h = 0.0
            else:
                precip_mm_h = raw

            ts = datetime.fromtimestamp(product_ms / 1000.0, tz=timezone.utc)
            return [RadarFrame(timestamp=ts, precip_mm_h=precip_mm_h, is_convective=False)]
        except Exception as e:
            logger.warning(f"Radar-DPC fetch failed: {e}")
            return []
