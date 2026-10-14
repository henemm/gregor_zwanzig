"""AvalancheReportSource -- amtlicher Lawinen-Lagebericht (Issue #1441, Slice 1).

SPEC: docs/specs/modules/avalanche_report_bulletin.md
ADR: docs/adr/0087-lawinen-lagebericht-zweite-skala.md (ergaenzt ADR-0016)

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

from utils.timezone import to_utc

from services.official_alerts import warn_egress
from services.official_alerts.models import AVALANCHE_BULLETIN, OfficialAlert
from services.official_alerts.region_mapper import RegionMapper

logger = logging.getLogger("avalanche_report")

SERVICE_NAME = "avalanche_report"
SOURCE_PREFIX = "avalanche_report"
DEFAULT_URL_PATTERN = "https://static.avalanche.report/bulletins/latest/{X}_de_CAAMLv6.json"
BULLETIN_URL = "https://avalanche.report/bulletin/{date}?region={region}"
TIMEOUT = 8.0
_DATA_DIR = Path(__file__).resolve().parent / "data"

# EAWS-Stufe (CAAML ``mainValue``) -> Originalstufe 1-5.
_MAIN_VALUES: dict[str, int] = {
    "low": 1, "moderate": 2, "considerable": 3, "high": 4, "very_high": 5,
}
EAWS_WORDS_DE: dict[int, str] = {
    1: "gering", 2: "mäßig", 3: "erheblich", 4: "groß", 5: "sehr groß",
}
# Gleichstand der Hoechststufe: all_day vor later vor earlier (Vertrag Abschnitt 2).
_PERIOD_RANK: dict[str, int] = {"all_day": 0, "later": 1, "earlier": 2}


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


def _parse_time(value: object) -> Optional[datetime]:
    if not isinstance(value, str) or not value:
        return None
    return to_utc(datetime.fromisoformat(value.replace("Z", "+00:00")))


def _elevation(rating: dict) -> tuple[Optional[str], Optional[str]]:
    """(Wert, Richtung) woertlich -- ``treeline`` -> "Waldgrenze", kein erfundener Wert."""
    elevation = rating.get("elevation") or {}
    for bound, direction in (("lowerBound", "above"), ("upperBound", "below")):
        value = elevation.get(bound)
        if value is not None:
            return ("Waldgrenze" if value == "treeline" else str(value)), direction
    return None, None


def _time_of_day(rated: list[tuple[int, dict]]) -> Optional[str]:
    """Nur bei verschiedener Hoechststufe von Vor-/Nachmittag: die Periode der Hoechststufe."""
    def _max(period: str) -> int:
        return max((lvl for lvl, r in rated
                    if r.get("validTimePeriod", "all_day") in (period, "all_day")), default=0)

    if not any(r.get("validTimePeriod") in ("earlier", "later") for _l, r in rated):
        return None
    earlier, later = _max("earlier"), _max("later")
    if earlier == later:
        return None
    return "earlier" if earlier > later else "later"


def _carrier(rated: list[tuple[int, dict]]) -> tuple[int, dict]:
    """Rating der Hoechststufe; Gleichstand: ohne Hoehenbegrenzung (breiteste
    Aussage), dann all_day/later/earlier, dann Bulletin-Reihenfolge."""
    top = max(lvl for lvl, _r in rated)
    candidates = [(i, lvl, r) for i, (lvl, r) in enumerate(rated) if lvl == top]
    _i, lvl, rating = min(candidates, key=lambda c: (
        _elevation(c[2])[0] is not None,
        _PERIOD_RANK.get(c[2].get("validTimePeriod", "all_day"), 0), c[0],
    ))
    return lvl, rating


def _problems(bulletin: dict) -> tuple[str, ...]:
    out: list[str] = []
    for problem in bulletin.get("avalancheProblems") or []:
        code = problem.get("problemType")
        if code and code not in out:
            out.append(code)
    return tuple(out)


def _rated(bulletin: dict, region_id: str) -> list[tuple[int, dict]]:
    """Ratings mit bekannter EAWS-Stufe; unbekannte Werte (z. B. ``no_rating``)
    werden verworfen und gemeldet -- nie still (#1405)."""
    rated: list[tuple[int, dict]] = []
    dropped: list[object] = []
    for rating in bulletin.get("dangerRatings") or []:
        value = rating.get("mainValue")
        if value in _MAIN_VALUES:
            rated.append((_MAIN_VALUES[value], rating))
        else:
            dropped.append(value)
    if dropped:
        logger.info("avalanche_report (#1441): %s -- Stufen ohne EAWS-Zuordnung verworfen: %s",
                    region_id, dropped)
    return rated


def _find_region(doc: dict, region_id: str) -> Optional[tuple[dict, dict]]:
    for bulletin in doc.get("bulletins") or []:
        for region in bulletin.get("regions") or []:
            if region.get("regionID") == region_id:
                return bulletin, region
    return None


def parse_region_alert(doc: dict, region_id: str, *, source: str = SOURCE_PREFIX) -> Optional[OfficialAlert]:
    """CAAML v6 -> ein ``OfficialAlert`` fuer eine Mikroregion. Rein, KEINE
    Gueltigkeitspruefung. ``None``, wenn die Region in keinem Bulletin steht
    oder das Bulletin keine bekannte Stufe traegt.

    Datum der Bulletin-URL = Ausgabetag = Datum von ``validTime.endTime``. Die
    Warndienste setzen ``endTime`` auf 17:00 Ortszeit (15:00 UTC Sommer, 16:00
    UTC Winter) -- das UTC-Datum ist damit stets das Ortsdatum, ohne festes
    Zonen-Literal und ohne stillen tz-Rueckfall (Waechter #1402)."""
    found = _find_region(doc, region_id)
    if found is None:
        return None
    bulletin, region = found
    rated = _rated(bulletin, region_id)
    if not rated:
        return None
    native, rating = _carrier(rated)
    elevation_value, direction = _elevation(rating)
    valid = bulletin.get("validTime") or {}
    valid_to = _parse_time(valid.get("endTime"))
    url = None
    if valid_to is not None:
        day = valid_to.date().isoformat()
        url = BULLETIN_URL.format(date=day, region=region_id)
    return OfficialAlert(
        source=source, hazard=AVALANCHE_BULLETIN, level=min(native, 4),
        label=f"Lawinenstufe {native} ({EAWS_WORDS_DE[native]})",
        valid_from=_parse_time(valid.get("startTime")), valid_to=valid_to, url=url,
        region_label=region.get("name"), dedup_id=f"{AVALANCHE_BULLETIN}:{region_id}",
        scale="eaws", native_level=native, elevation_value=elevation_value,
        elevation_direction=direction, problems=_problems(bulletin),
        time_of_day=_time_of_day(rated),
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
