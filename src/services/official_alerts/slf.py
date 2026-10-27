"""SlfSource -- amtlicher Schweizer Lawinen-Lagebericht des SLF (Issue #1441, Scheibe S3).

SPEC: docs/specs/modules/feat_1441_s3_slf.md
ADR: docs/adr/0091-slf-eigene-lawinenquelle.md (ergaenzt ADR-0089)

Liest das CAAML6-JSON von ``aws.slf.ch`` (WSL-Institut fuer Schnee- und
Lawinenforschung SLF): EIN Dokument fuer die ganze Schweiz, ein Abruf je
Cache-Zeitraum fuer alle Punkte. Zustaendig ist die Quelle nur fuer Punkte in
einer CH-Mikroregion (Polygon, keine Bounding-Box). Je Punkt GENAU EIN
``OfficialAlert`` der Gefahrenart ``avalanche_bulletin`` -- Parser geteilt mit
avalanche.report (``caaml.py``), zusaetzlich Hoehe aus dem Problem und Feinstufe.

Zustaende: Netz-/5xx-/Parse-Fehler -> ``[]`` + Fehlermarker (``unavailable``);
leere Saison (HTTP 200, ``{"bulletins":[]}``), abgelaufenes Bulletin oder eine
im Bulletin nicht bewertete Region -> ``[]`` ohne Hinweis, "nicht zustaendig"
(Cache hoechstens 1800 s). Es gibt bewusst KEINE Liste ausgeschlossener Regionen.
"""
from __future__ import annotations

import logging
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, Optional
from urllib.parse import urlsplit

import httpx

from services.official_alerts import warn_egress
from services.official_alerts.caaml import parse_region_alert
from services.official_alerts.models import OfficialAlert
from services.official_alerts.region_mapper import RegionMapper

logger = logging.getLogger("slf_bulletin")

SERVICE_NAME = "slf_bulletin"
# Ohne ``activeAt``: die API liefert genau die gerade gueltige Ausgabe.
API_URL = "https://aws.slf.ch/api/bulletin/caaml/de/json"
# Die API hat kein Link-Feld -- konstanter Link zum Originalbericht (Antrag #7).
BULLETIN_URL = "https://www.slf.ch/de/lawinenbulletin-und-schneesituation/"
TIMEOUT = 8.0
REGIONS_FILE = Path(__file__).resolve().parent / "data" / "avalanche_regions_CH.geojson.json"


def _parse_document(resp: httpx.Response) -> dict:
    """Antwort -> CAAML-Dokument; ohne ``bulletins``-Liste ist es ein Ausfall."""
    doc = resp.json()
    if not isinstance(doc, dict) or not isinstance(doc.get("bulletins"), list):
        raise ValueError("keine CAAML-v6-Bulletinliste")
    return doc


class SlfSource:
    """SLF-Lawinen-Lagebericht fuer die Official-Alerts-Registry (#1441 S3)."""

    def __init__(
        self, *, transport: Optional[httpx.BaseTransport] = None,
        clock: Callable[[], float] = time.monotonic,
        now_fn: Optional[Callable[[], datetime]] = None,
        cache: Optional[dict] = None, regions_file: Path = REGIONS_FILE,
    ) -> None:
        self._transport = transport
        self._clock = clock
        self._now_fn = now_fn or (lambda: datetime.now(timezone.utc))
        self._cache: dict = {} if cache is None else cache
        self._mapper = RegionMapper(regions_file)

    @property
    def name(self) -> str:
        return SERVICE_NAME

    def covers(self, lat: float, lon: float) -> bool:
        """Punkt in mindestens einer CH-Mikroregion (Polygon), kein Netz."""
        return bool(self._mapper.regions_at(lat, lon))

    def _fetch_document(self) -> Optional[dict]:
        def _request() -> httpx.Response:
            with httpx.Client(transport=self._transport, timeout=TIMEOUT) as client:
                return client.get(API_URL)

        # Erfolg (auch die leere Saison) mit der Erfolgs-TTL von 1800 s.
        return warn_egress.cached_fetch(
            cache=self._cache, cache_key="CH", service=SERVICE_NAME,
            host=urlsplit(API_URL).hostname or "", request_fn=_request,
            parse_fn=_parse_document, clock=self._clock, log=logger,
        )

    def _candidates(self, lat: float, lon: float) -> list[OfficialAlert]:
        out: list[OfficialAlert] = []
        region_ids = self._mapper.regions_at(lat, lon)
        doc = self._fetch_document() if region_ids else None
        if doc:
            now = self._now_fn()
            for region_id in region_ids:
                alert = parse_region_alert(
                    doc, region_id, source=f"{SERVICE_NAME}:{region_id}",
                    url_pattern=BULLETIN_URL, problem_elevation=True,
                )
                # Gueltigkeit bei JEDEM fetch: endTime >= jetzt (Gleichheit = gueltig).
                if alert is not None and alert.valid_to is not None and alert.valid_to >= now:
                    out.append(alert)
        if not out:
            # Leere Saison, abgelaufenes Bulletin, Region nicht bewertet: nicht
            # zustaendig -- kompensiert keinen fremden Ausfall, ist keine Entwarnung.
            # Ein echter Abruffehler hat Vorrang (base.py).
            warn_egress.mark_not_covered()
        return out

    def fetch(self, lat: float, lon: float) -> list[OfficialAlert]:
        """GENAU EIN Alert je Punkt: hoechste Originalstufe, Gleichstand kleinste
        Regions-ID. Wirft nie."""
        try:
            candidates = self._candidates(lat, lon)
        except Exception:
            logger.warning("slf_bulletin: Auswertung fehlgeschlagen", exc_info=True)
            warn_egress.mark_fetch_incomplete()
            return []
        if not candidates:
            return []
        return [min(candidates, key=lambda a: (-(a.native_level or 0), a.dedup_id or ""))]
