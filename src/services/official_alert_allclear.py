"""Entwarnung amtlicher Warnungen -- Erkennung gegen das Melde-Gedaechtnis
(Issue #1441 Scheibe S2, ADR-0090).

SPEC: docs/specs/modules/feat_1441_s2_entwarnung.md (Abschnitte 1, 3, 4, 6)

Reine Funktionen ueber dem Gedaechtnis-Dict EINER Entitaet (Trip bzw.
``preset_id:loc_id``). Geteilt von Trip-Alarm, Ortsvergleich-Alarm und beiden
Briefing-Schreibpfaden. Grundsatz "im Zweifel still": nur Eintraege mit
``source`` und ``scope`` werden bewertet, nur bei gesunder MELDENDER Quelle,
nur wenn ihr Zeitraum das abgefragte Fenster am selben Ort ueberlappt und
noch nicht planmaessig abgelaufen ist.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Optional

from output.renderers.alert.official_alerts import (
    _identity_hazard_prefix, official_alert_state_key,
)
from services.alert_state import OFFICIAL_ALERT_KEY_PREFIX
from services.official_alerts.models import OfficialAlert, comparable_level

LOWERED = "lowered"
ENDED = "ended"


@dataclass(frozen=True)
class AllClearQuery:
    """Ein Abruf des Laufs: Ort (``scope``), Anzeige-IDs, Fenster, Pro-Quelle-
    Ergebnis (``None`` = unbekannt -> nie Entwarnung) und die gezeigten
    (zusammengefuehrten) Warnungen."""
    scope: str
    scope_ids: tuple
    window_start: datetime
    window_end: Optional[datetime]
    sources: Optional[dict]
    shown: tuple = ()


@dataclass(frozen=True)
class OfficialAllClear:
    """Eine Entwarnung: ``alert`` traegt die Identitaet aus dem Gedaechtnis."""
    key: str
    kind: str
    alert: OfficialAlert
    old_rank: int
    new_rank: int
    old_level: int
    new_level: int
    scope_ids: tuple = ()
    current_keys: tuple = ()


def scope_token(lat: float, lon: float) -> str:
    """Ortskennung des Trip-Gedaechtnisses (gleiche Rundung wie die Abrufe)."""
    return f"{round(lat, 3)},{round(lon, 3)}"


def _aware(value) -> Optional[datetime]:
    if value is None:
        return None
    try:
        dt = value if isinstance(value, datetime) else datetime.fromisoformat(value)
    except (TypeError, ValueError):
        return None
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


def entry_alert(key: str, entry: dict) -> Optional[OfficialAlert]:
    """Identitaet eines Gedaechtnis-Eintrags als ``OfficialAlert`` (Gefahr,
    Region/Kennung, Zeitraum) -- der Schluessel ist
    ``official_alert:{art}:{wert}:{hazard}:{von}:{bis}``."""
    suffix = f":{entry.get('valid_from') or 'none'}:{entry.get('valid_to') or 'none'}"
    if not key.startswith(OFFICIAL_ALERT_KEY_PREFIX) or not key.endswith(suffix):
        return None
    ident, _sep, hazard = key[len(OFFICIAL_ALERT_KEY_PREFIX):-len(suffix)].rpartition(":")
    kind, _sep, value = ident.partition(":")
    if not hazard or not value or kind not in ("id", "region", "label"):
        return None
    rank = int(entry.get("last_reported_value") or 0)
    return OfficialAlert(
        source=str(entry.get("source") or ""), hazard=hazard,
        level=int(entry.get("level") or min(max(rank, 1), 4)),
        label=value if kind == "label" else hazard,
        region_label=value if kind == "region" else None,
        dedup_id=value if kind == "id" else None,
        valid_from=_aware(entry.get("valid_from")), valid_to=_aware(entry.get("valid_to")),
    )


def _touches(a: OfficialAlert, ident: OfficialAlert) -> bool:
    vf, vt = _aware(a.valid_from), _aware(a.valid_to)
    if vf is None or vt is None:
        return True  # ohne Zeitraum: im Zweifel "noch da"
    return vf <= ident.valid_to and ident.valid_from <= vt


def _in_window(ident: OfficialAlert, q: AllClearQuery) -> bool:
    start, end = _aware(q.window_start), _aware(q.window_end)
    return start <= ident.valid_to and (end is None or ident.valid_from <= end)


def _scopes(entry: dict) -> set:
    scope = entry.get("scope")
    return set(scope) if isinstance(scope, (list, tuple)) else ({scope} if scope else set())


def _observe(key: str, entry: dict, queries: list, now: datetime):
    """``(ident, present, scope_ids)`` oder ``None`` (nicht bewertbar)."""
    if not isinstance(entry, dict) or not entry.get("source") or entry.get("ended_at"):
        return None
    ident = entry_alert(key, entry)
    if ident is None or ident.valid_from is None or ident.valid_to is None:
        return None
    if ident.valid_to <= now:
        return None  # planmaessiger Ablauf ist keine Entwarnung (AC-9)
    scopes = _scopes(entry)
    matches = [q for q in queries if q.scope in scopes and _in_window(ident, q)]
    if not matches:
        return None  # vergangenes Segment / Tagesfenster-Ende (AC-8)
    results = [(q.sources or {}).get(entry["source"]) if q.sources is not None else None
               for q in matches]
    if any(r is None or not r[0] for r in results):
        return None  # meldende Quelle nicht abrufbar -> keine Information (AC-6)
    prefix = _identity_hazard_prefix(ident)
    present = [a for _ok, alerts in results for a in alerts
               if _identity_hazard_prefix(a) == prefix and _touches(a, ident)]
    scope_ids = tuple(dict.fromkeys(str(i) for q in matches for i in q.scope_ids))
    return ident, present, scope_ids


def detect_official_allclear(
    state: dict, queries: list, now: datetime, *, confirm_ended: bool = True,
) -> tuple[list[OfficialAllClear], bool]:
    """Erkennung "gesenkt" / "vorzeitig beendet" (Spec Abschnitt 3). Setzt bzw.
    loescht ``absent_since`` direkt in ``state``; liefert ``(entwarnungen,
    state_geaendert)``. ``confirm_ended=False`` (Briefing): "beendet" ohne
    Zwei-Lauf-Bestaetigung -- das zugestellte Briefing hat das Fehlen gezeigt."""
    now = _aware(now)
    found: list[OfficialAllClear] = []
    changed = False
    for key, entry in list(state.items()):
        observed = _observe(key, entry, queries, now)
        if observed is None:
            continue
        ident, present, scope_ids = observed
        old_rank = int(entry.get("last_reported_value") or 0)
        if present:
            if entry.pop("absent_since", None):
                changed = True
            best = max(present, key=comparable_level)
            if comparable_level(best) < old_rank:
                found.append(OfficialAllClear(
                    key, LOWERED, ident, old_rank, comparable_level(best), ident.level,
                    best.level, scope_ids, tuple(official_alert_state_key(a) for a in present),
                ))
            continue
        if confirm_ended and not entry.get("absent_since"):
            entry["absent_since"] = now.isoformat()
            changed = True
            continue
        found.append(OfficialAllClear(key, ENDED, ident, old_rank, 0, ident.level, 0, scope_ids))
    return found, changed


def apply_official_allclears(state: dict, allclears: list, now: datetime) -> bool:
    """Expliziter Schreibweg NACH Zustellung (ADR-0086): "gesenkt" senkt
    ``last_reported_value``/``level``, "beendet" setzt den Tombstone (Rang 0).
    Getrennt vom Revision-Merge, der weiter ``max`` behaelt."""
    changed = False
    for ac in allclears:
        keys = (ac.key, *ac.current_keys) if ac.kind == LOWERED else (ac.key,)
        for key in dict.fromkeys(keys):
            entry = state.get(key)
            if not isinstance(entry, dict):
                continue
            entry.pop("absent_since", None)
            if ac.kind == LOWERED:
                entry["last_reported_value"] = float(ac.new_rank)
                entry["level"] = int(ac.new_level)
            else:
                entry["ended_at"] = _aware(now).isoformat()
                entry["last_reported_value"] = 0.0
            changed = True
    return changed


def _delivering_names(alert: OfficialAlert, q: AllClearQuery) -> set:
    """Registry-Namen, deren Pre-Merge-Satz IN DIESEM Abruf genau die gezeigte
    Warnung traegt (Schluessel, Quelle und Stufe gleich) -- nicht bloss eine
    Warnung mit gleichem Schluessel (Adversary F001: Reihenfolge der Registry)."""
    key, rank = official_alert_state_key(alert), comparable_level(alert)
    return {name for name, (_ok, alerts) in (q.sources or {}).items()
            if any(official_alert_state_key(a) == key and a.source == alert.source
                   and comparable_level(a) == rank for a in alerts)}


def reported_meta(queries: list) -> dict:
    """Schluessel -> ``{"source", "scope"}`` fuer die gezeigten Warnungen:
    ``scope`` vereint alle Orte, an denen die Warnung gezeigt wurde. ``source``
    nur bei EINDEUTIGER Zuordnung, sonst ``None`` (im Zweifel still)."""
    meta: dict = {}
    names: dict = {}
    for q in queries:
        for a in q.shown:
            key = official_alert_state_key(a)
            item = meta.setdefault(key, {"source": None, "scope": []})
            if q.scope not in item["scope"]:
                item["scope"].append(q.scope)
            names.setdefault(key, set()).update(_delivering_names(a, q))
    for key, found in names.items():
        meta[key]["source"] = next(iter(found)) if len(found) == 1 else None
    return meta


def tag_reported_entries(state: dict, meta: dict) -> bool:
    """Schreibt ``source``/``scope`` in bereits vorhandene Eintraege (Briefing-
    Pfad: der Bestands-Record kennt Ort und Registry-Namen nicht)."""
    changed = False
    for key, item in meta.items():
        entry = state.get(key)
        if not isinstance(entry, dict):
            continue
        if item.get("source"):
            entry["source"] = item["source"]
        entry["scope"] = list(dict.fromkeys([*sorted(_scopes(entry)), *item["scope"]]))
        changed = True
    return changed


def allclear_settled(result) -> bool:
    """Issue #1441 S2 (ADR-0086, AC-12): die Entwarnung gilt als erledigt, wenn
    ein Kanal, dessen Nachricht sie TATSAECHLICH enthielt, zugestellt hat --
    oder wenn der Versand rein gesperrt war (Sperre ist terminal wie bei
    Warnungen, sonst wiederholte sie sich jeden Lauf und verbraeuchte das
    Tageskontingent). Transportfehler und SMS-Kuerzung bleiben offen."""
    if result.delivery_outcome == "blocked_only":
        return True
    return bool(set(result.delivered_channels) & set(getattr(result, "allclear_channels", [])))
