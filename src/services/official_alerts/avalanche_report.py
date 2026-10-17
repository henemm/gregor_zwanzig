"""AvalancheReportSource -- amtlicher Lawinen-Lagebericht (Issue #1441, Slice 1).

SPEC: docs/specs/modules/avalanche_report_bulletin.md
ADR: docs/adr/0089-lawinen-lagebericht-zweite-skala.md (ergaenzt ADR-0016)

Liest die CAAML-v6-Bulletins von ``avalanche.report`` (Euregio Tirol-Suedtirol-
Trentino, Lawinenwarndienst Kaernten; CC BY 4.0) und liefert je Punkt GENAU
EINEN ``OfficialAlert`` der Gefahrenart ``avalanche_bulletin`` mit der
Originalstufe 1-5 (``native_level``), Hoehenangabe, Lawinenproblemen und
Bulletin-URL. Die Laenderliste ist eine Konfigurationstabelle: ein weiteres
Land = eine Tabellenzeile + Regionsdatei + Egress-Host, kein Code.

Drei Zustaende ohne neues Flag: Netz-/5xx-/Parse-Fehler -> ``[]`` + Fehler-
marker (``unavailable``); HTTP 404 oder abgelaufenes Bulletin -> ``[]`` ohne
Hinweis ("kein aktueller Bericht", Cache hoechstens 1800 s); Stufe 1 ist ein
sichtbarer Alert.
"""
from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, Optional, Sequence
from urllib.parse import urlsplit

import httpx

from services.official_alerts import warn_egress
# #1441 S3 (ADR-0091): die reinen CAAML-Funktionen liegen in caaml.py (geteilt mit SlfSource).
from services.official_alerts.caaml import (  # noqa: F401  (Re-Export fuer den S1-Bestand)
    BULLETIN_URL, EAWS_WORDS_DE, _carrier, _elevation, _find_region, _parse_time,
    _problems, _rated, _time_of_day, parse_region_alert,
)
from services.official_alerts.models import OfficialAlert
from services.official_alerts.region_mapper import RegionMapper

logger = logging.getLogger("avalanche_report")

SERVICE_NAME = "avalanche_report"
SOURCE_PREFIX = "avalanche_report"
DEFAULT_URL_PATTERN = "https://static.avalanche.report/bulletins/latest/{X}_de_CAAMLv6.json"
TIMEOUT = 8.0
_DATA_DIR = Path(__file__).resolve().parent / "data"


@dataclass(frozen=True)
class AvalancheRegionConfig:
    """Eine Zeile der Konfigurationstabelle (ein Land/Warndienst)."""
    key: str
    url_pattern: str
    regions_file: Path
    display_name: str


def _row(key: str, name: str) -> AvalancheRegionConfig:
    return AvalancheRegionConfig(
        key=key, url_pattern=DEFAULT_URL_PATTERN,
        regions_file=_DATA_DIR / f"avalanche_regions_{key}.geojson.json",
        display_name=name,
    )


# PO-Entscheid 2026-10-13 ("Belegte zuerst"): nur Laender mit belegter Lizenz.
AVALANCHE_REGION_TABLE: tuple[AvalancheRegionConfig, ...] = (
    _row("AT-07", "Lawinenwarndienst Tirol"),
    _row("IT-32-BZ", "Lawinenwarndienst Südtirol"),
    _row("IT-32-TN", "Lawinenwarndienst Trentino"),
    _row("AT-02", "Lawinenwarndienst Kärnten"),
)


def _parse_document(resp: httpx.Response) -> dict:
    """Antwort -> CAAML-Dokument; alles andere ist ein Parse-Fehler (Ausfall)."""
    doc = resp.json()
    if not isinstance(doc, dict) or not isinstance(doc.get("bulletins"), list):
        raise ValueError("keine CAAML-v6-Bulletinliste")
    return doc


class AvalancheReportSource:
    """Lawinen-Lagebericht fuer die Official-Alerts-Registry (#1441)."""

    def __init__(
        self, table: Sequence[AvalancheRegionConfig] = AVALANCHE_REGION_TABLE, *,
        transport: Optional[httpx.BaseTransport] = None,
        clock: Callable[[], float] = time.monotonic,
        now_fn: Optional[Callable[[], datetime]] = None,
        cache: Optional[dict] = None,
    ) -> None:
        self._table = tuple(table)
        self._transport = transport
        self._clock = clock
        self._now_fn = now_fn or (lambda: datetime.now(timezone.utc))
        self._cache: dict = {} if cache is None else cache
        self._mappers = {row.key: RegionMapper(row.regions_file) for row in self._table}

    @property
    def name(self) -> str:
        return SERVICE_NAME

    def covers(self, lat: float, lon: float) -> bool:
        """Nur die Bounding-Boxen der Tabellenzeilen (aus den Regionsdateien), kein Netz."""
        for row in self._table:
            box = self._mappers[row.key].bbox()
            if box is not None and box[0] <= lon <= box[2] and box[1] <= lat <= box[3]:
                return True
        return False

    def _fetch_document(self, row: AvalancheRegionConfig) -> Optional[dict]:
        url = row.url_pattern.replace("{X}", row.key)

        def _request() -> httpx.Response:
            # Redirect static.avalanche.report -> avalanche.report MUSS gefolgt werden.
            with httpx.Client(transport=self._transport, follow_redirects=True,
                              timeout=TIMEOUT) as client:
                return client.get(url)

        return warn_egress.cached_fetch(
            cache=self._cache, cache_key=row.key, service=SERVICE_NAME,
            host=urlsplit(url).hostname or "", request_fn=_request,
            parse_fn=_parse_document, clock=self._clock, log=logger,
            not_covered_statuses=frozenset({404}),
            not_covered_ttl=warn_egress.WARN_SUCCESS_TTL,
        )

    def _candidates(self, lat: float, lon: float) -> list[OfficialAlert]:
        now = self._now_fn()
        out: list[OfficialAlert] = []
        for row in self._table:
            region_ids = self._mappers[row.key].regions_at(lat, lon)
            if not region_ids:
                continue
            doc = self._fetch_document(row)
            if not doc:
                continue
            for region_id in region_ids:
                alert = parse_region_alert(doc, region_id, source=f"{SOURCE_PREFIX}:{row.key}")
                # Gueltigkeit bei JEDEM fetch: endTime >= jetzt (Gleichheit = gueltig).
                if alert is not None and alert.valid_to is not None and alert.valid_to >= now:
                    out.append(alert)
        if not out:
            # Bounding-Box ja, Region nein -- ODER "kein aktueller Bericht" (404 bzw.
            # abgelaufenes Bulletin): nicht zustaendig, kompensiert also keinen
            # Ausfall einer anderen Quelle. Ein echter Abruffehler hat Vorrang (base.py).
            warn_egress.mark_not_covered()
        return out

    def fetch(self, lat: float, lon: float) -> list[OfficialAlert]:
        """GENAU EIN Alert je Punkt: hoechste Originalstufe, Gleichstand kleinste
        Regions-ID. Wirft nie."""
        try:
            candidates = self._candidates(lat, lon)
        except Exception:
            logger.warning("avalanche_report: Auswertung fehlgeschlagen", exc_info=True)
            warn_egress.mark_fetch_incomplete()
            return []
        if not candidates:
            return []
        return [min(candidates, key=lambda a: (-(a.native_level or 0), a.dedup_id or ""))]
