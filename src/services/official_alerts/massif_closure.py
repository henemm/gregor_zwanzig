"""MassifClosureSource — Praefektur-Zugangssperren einzelner Wander-Massive
bei akuter Waldbrandgefahr (Issue #1037, Slice 3 des Epics #1033).

Leitszenario Cote d'Azur (Var/Bouches-du-Rhone), Korsika als zweiter
gleichrangiger Anwendungsfall ueber denselben Mechanismus. Matching laeuft
ueber **exakte amtliche Massiv-Polygone + Point-in-Polygon** (`massif_at()` in
`massif_zones.py`, Spec Architektur-Entscheidung 1+2, Fix-Runde 2 nach
Adversary Runde 2 BROKEN): kein Departement-Gate, keine Zentrum+Radius-
Naeherung mehr — diese hatte falsch geratene IDs (F004) und
Radius-Fehlzuordnung an Kuesten (F005) produziert. Das getroffene Massiv kennt
seinen Source-DEPT (`Massif.src`) und bestimmt damit die Fetch-URL.

Quelle: undokumentierter, auth-freier Tages-JSON-Endpoint von
`risque-prevention-incendie.fr`, pro Source-DEPT gecacht (TTL 300s Erfolg /
60s Fehlschlag, analog `meteo_forets.py`). Fail-soft: HTTP-Fehler oder
unerwartete Struktur -> `fetch()` liefert `[]`, kein Crash der Compare-Mail.

SPEC: docs/specs/modules/issue_1037_official_alerts_massif_closure.md
"""
from __future__ import annotations

import logging
import time
from datetime import datetime
from typing import Optional

import httpx

from services.official_alerts.massif_zones import Massif, massif_at, massifs_at
from services.official_alerts.models import OfficialAlert

logger = logging.getLogger("massif_closure")

_ENDPOINT = "https://www.risque-prevention-incendie.fr/static/{src}/import_data/{ymd}.json"
TIMEOUT = 15.0
CACHE_TTL = 300.0  # Sekunden — Erfolgs-Fenster pro Source-DEPT
FAILURE_CACHE_TTL = 60.0  # Sekunden — kurzes Failure-Fenster

# Modul-Level-Cache PRO Source-DEPT: {src: {"data": ..., "fetched_at": ..., "ttl": ...}}
_cache: dict = {}

# Leichtgewichtiges Monitoring (Projektregel "kein Job ohne Observability").
_STATUS: dict = {"last_run": None, "last_error": None, "error_count": 0}


def _niveau_to_alert(niveau: int, name: str) -> Optional[OfficialAlert]:
    """Bildet ein Massiv-Niveau (1-5) auf einen Zugangsverbot-Alert ab.

    Niveau < 3 -> None (Zugang amtlich erlaubt). Niveau 3 -> "eingeschraenkt",
    Niveau 4 -> "gesperrt", Niveau >=5 -> "gesperrt (total)".
    """
    if niveau < 3:
        return None
    if niveau == 3:
        label = f"Zugang eingeschränkt — {name}"
    elif niveau == 4:
        label = f"Zugang gesperrt — {name}"
    else:
        label = f"Zugang gesperrt (total) — {name}"
    return OfficialAlert(source="massif_closure", hazard="access_ban", level=niveau, label=label)


def _extract_alert(data, hit: Massif) -> list[OfficialAlert]:
    """Struktur- + Shape-Guard + Umwandlung der Tages-JSON-Antwort in eine Alert-Liste.

    Der Badge-Name wird aus dem amtlichen (GROSSBUCHSTABEN-)Namen per
    `.title()` in Title-Case gewandelt (z.B. "MAURES" -> "Maures",
    "CORNICHE DES MAURES" -> "Corniche Des Maures").
    """
    if (
        not isinstance(data, dict)
        or not isinstance(data.get("massifs"), dict)
        or hit.massif_id not in data["massifs"]
    ):
        logger.warning("massif_closure: unerwartete Struktur fuer massiv=%s", hit.massif_id)
        return []
    raw = data["massifs"][hit.massif_id]
    if not isinstance(raw, list) or not raw or not isinstance(raw[0], int):
        logger.warning("massif_closure: unerwartete Niveau-Struktur fuer massiv=%s", hit.massif_id)
        return []
    niveau = raw[0]  # J1 (Index 0)
    alert = _niveau_to_alert(niveau, hit.name.title())
    return [alert] if alert is not None else []


def _get_cached_daily_json(src: str) -> Optional[dict]:
    """Tages-JSON fuer ein Source-DEPT, gecacht mit TTL. ``None`` bei Fehler."""
    now = time.monotonic()
    entry = _cache.get(src)
    if entry is not None and (now - entry["fetched_at"]) < entry["ttl"]:
        return entry["data"]

    ymd = datetime.now().strftime("%Y%m%d")
    try:
        resp = httpx.get(_ENDPOINT.format(src=src, ymd=ymd), timeout=TIMEOUT)
        resp.raise_for_status()
        data = resp.json()
    except Exception:
        logger.warning("massif_closure: Abruf fehlgeschlagen fuer src=%s", src, exc_info=True)
        _cache[src] = {"data": None, "fetched_at": now, "ttl": FAILURE_CACHE_TTL}
        return None

    _cache[src] = {"data": data, "fetched_at": now, "ttl": CACHE_TTL}
    return data


class MassifClosureSource:
    """Praefektur-Zugangssperren-Quelle fuer die Official-Alerts-Registry (#1037)."""

    @property
    def name(self) -> str:
        return "massif_closure"

    def covers(self, lat: float, lon: float) -> bool:
        return massif_at(lat, lon) is not None

    def fetch(self, lat: float, lon: float) -> list[OfficialAlert]:
        hits = massifs_at(lat, lon)
        if not hits:
            return []

        _STATUS["last_run"] = datetime.now().isoformat()
        best_alert: Optional[OfficialAlert] = None
        for hit in hits:
            data = _get_cached_daily_json(hit.src)
            if data is None:
                _STATUS["last_error"] = f"fetch failed for src={hit.src}"
                _STATUS["error_count"] += 1
                continue
            for alert in _extract_alert(data, hit):
                if best_alert is None or alert.level > best_alert.level:
                    best_alert = alert
        return [best_alert] if best_alert is not None else []
