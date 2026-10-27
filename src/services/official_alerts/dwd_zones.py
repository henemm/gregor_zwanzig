"""Eingecheckte DWD-Kreisgeometrie (``dwd:Warngebiete_Kreise``) fuer die
Punkt->Warnzelle-Zuordnung der deutschen MeteoAlarm-Feed-Quelle (Issue #1681).

Muster A nach ADR-0041, Loader analog ``dpc.py`` (``_ZONES_PATH``,
``_load_zones``), Ray-Cast ueber den geteilten ``geo_ray_cast._point_in_ring``.
Quellenvermerk: ``data/README.md``. Kuesten-/Seezellen (``501...``) sind
bewusst NICHT enthalten (Spec Known Limitations).

SPEC: docs/specs/modules/feat_1681_meteoalarm_de.md
"""
from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Optional

from services.official_alerts.geo_ray_cast import _point_in_ring

logger = logging.getLogger("dwd_zones")

_ZONES_PATH = Path(__file__).resolve().parent / "data" / "dwd_warngebiete_kreise.json"


def _load_zones(path: Path = _ZONES_PATH) -> list[dict]:
    """Fail-soft wie ``dpc._load_zones``: defekte/fehlende Datei -> Warnung
    + [], nie ein Raise beim Modul-Import (DE ist dann nirgends zustaendig)."""
    try:
        return json.loads(path.read_text(encoding="utf-8"))["kreise"]
    except Exception:
        logger.warning("dwd_zones: Kreisgeometrie nicht ladbar (%s) -- DE deaktiviert", path, exc_info=True)
        return []


_ZONES: list[dict] = _load_zones()
KNOWN_WARNCELLIDS: frozenset[str] = frozenset(z["WARNCELLID"] for z in _ZONES)


def warncell_at(lat: float, lon: float) -> Optional[str]:
    """Punkt -> WARNCELLID oder ``None``. Even-Odd ueber ALLE Ringe eines
    Kreises (Aussen- und Innenringe): ein Punkt in einer Enklave (Loch) zaehlt
    damit nicht zum umschliessenden Kreis."""
    for zone in _ZONES:
        inside = False
        for ring in zone["rings"]:
            if _point_in_ring(lat, lon, ring):
                inside = not inside
        if inside:
            return zone["WARNCELLID"]
    return None
