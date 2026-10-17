"""Reine CAAML-v6-Funktionen der Lawinen-Lageberichte (Issue #1441, S1 + S3).

SPEC: docs/specs/modules/feat_1441_s3_slf.md (Implementation Details 1, 5, 6)
ADR: docs/adr/0091-slf-eigene-lawinenquelle.md (ergaenzt ADR-0089)

Ohne Netz und ohne Quellen-Konfiguration: geteilt von ``AvalancheReportSource``
(avalanche.report) und ``SlfSource`` (aws.slf.ch). Zwei Ergaenzungen fuer das SLF,
die S1-Bulletins nicht beruehren: Hoehe aus dem Lawinenproblem (nur wenn das
Traeger-Rating KEINE ``elevation`` hat) und die Feinstufe
(``customData.CH.subdivision``).
"""
from __future__ import annotations

import logging
from datetime import datetime
from typing import Optional

from utils.timezone import to_utc

from services.official_alerts.models import AVALANCHE_BULLETIN, OfficialAlert

logger = logging.getLogger("avalanche_report")

BULLETIN_URL = "https://avalanche.report/bulletin/{date}?region={region}"

# EAWS-Stufe (CAAML ``mainValue``) -> Originalstufe 1-5.
_MAIN_VALUES: dict[str, int] = {
    "low": 1, "moderate": 2, "considerable": 3, "high": 4, "very_high": 5,
}
EAWS_WORDS_DE: dict[int, str] = {
    1: "gering", 2: "mäßig", 3: "erheblich", 4: "groß", 5: "sehr groß",
}
# Gleichstand der Hoechststufe: all_day vor later vor earlier (Vertrag Abschnitt 2).
_PERIOD_RANK: dict[str, int] = {"all_day": 0, "later": 1, "earlier": 2}
# SLF-Feinstufe (``customData.CH.subdivision``); neutral/fehlend -> keine Angabe.
_SUBDIVISIONS: dict[str, str] = {"minus": "-", "plus": "+"}


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


def _problem_bound(problem: dict) -> tuple[Optional[str], Optional[str]]:
    """Grenze eines Lawinenproblems; ``lowerBound 0`` heisst "keine Begrenzung"
    und ergibt keine Hoehe (nichts erfinden, #1405)."""
    elevation = dict(problem.get("elevation") or {})
    if str(elevation.get("lowerBound")) == "0":
        elevation.pop("lowerBound")
    return _elevation({"elevation": elevation})


def elevation_from_problems(bulletin: dict, level: int, rating: dict) -> tuple[Optional[str], Optional[str]]:
    """Hoehe aus den Problemen, die das Traeger-Rating tragen (Spec Abschnitt 5):
    gleiche Stufe UND passende Tageszeit. Nur wenn ALLE Kandidaten dieselbe Grenze
    haben, wird sie uebernommen; sonst (mehrdeutig, ohne Grenze, kein Kandidat) keine."""
    period = rating.get("validTimePeriod", "all_day")
    bounds = {
        _problem_bound(problem)
        for problem in bulletin.get("avalancheProblems") or []
        if _MAIN_VALUES.get(problem.get("dangerRatingValue")) == level
        and problem.get("validTimePeriod", "all_day") in ("all_day", period)
    }
    if len(bounds) != 1:
        return None, None
    return next(iter(bounds))


def _level_modifier(rating: dict) -> Optional[str]:
    """Feinstufe "-"/"+" aus ``customData.CH.subdivision``; sonst ``None``."""
    sub = ((rating.get("customData") or {}).get("CH") or {}).get("subdivision")
    return _SUBDIVISIONS.get(sub) if isinstance(sub, str) else None


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


def parse_region_alert(
    doc: dict, region_id: str, *, source: str = "avalanche_report",
    url_pattern: str = BULLETIN_URL, problem_elevation: bool = False,
) -> Optional[OfficialAlert]:
    """CAAML v6 -> ein ``OfficialAlert`` fuer eine Mikroregion. Rein, KEINE
    Gueltigkeitspruefung. ``None``, wenn die Region in keinem Bulletin steht
    oder das Bulletin keine bekannte Stufe traegt.

    ``url_pattern`` mit ``{date}``/``{region}`` (S1: Datum = Ausgabetag = Datum von
    ``validTime.endTime``, 17:00 Ortszeit -> UTC-Datum = Ortsdatum, Waechter #1402);
    ohne Platzhalter (SLF) ist es die konstante Link-URL. ``problem_elevation``
    (SLF): Hoehe aus den Problemen, wenn das Traeger-Rating keine ``elevation`` hat."""
    found = _find_region(doc, region_id)
    if found is None:
        return None
    bulletin, region = found
    rated = _rated(bulletin, region_id)
    if not rated:
        return None
    native, rating = _carrier(rated)
    elevation_value, direction = _elevation(rating)
    if problem_elevation and not rating.get("elevation"):
        elevation_value, direction = elevation_from_problems(bulletin, native, rating)
    valid = bulletin.get("validTime") or {}
    valid_to = _parse_time(valid.get("endTime"))
    url = None
    if valid_to is not None:
        url = url_pattern.format(date=valid_to.date().isoformat(), region=region_id)
    return OfficialAlert(
        source=source, hazard=AVALANCHE_BULLETIN, level=min(native, 4),
        label=f"Lawinenstufe {native} ({EAWS_WORDS_DE[native]})",
        valid_from=_parse_time(valid.get("startTime")), valid_to=valid_to, url=url,
        region_label=region.get("name"), dedup_id=f"{AVALANCHE_BULLETIN}:{region_id}",
        scale="eaws", native_level=native, elevation_value=elevation_value,
        elevation_direction=direction, problems=_problems(bulletin),
        time_of_day=_time_of_day(rated), level_modifier=_level_modifier(rating),
    )
