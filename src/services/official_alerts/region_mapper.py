"""Generischer Punkt-in-Region-Mapper fuer GeoJSON-Regionen (Issue #1441).

SPEC: docs/specs/modules/avalanche_report_bulletin.md (Abschnitt 9, AC-9/AC-10)

Laedt eine GeoJSON-FeatureCollection (``Feature.properties.id`` = Regions-ID)
fail-soft und beantwortet "in welchen Regionen liegt dieser Punkt?" -- ALLE
Treffer, sortiert. Ein Point-in-Polygon ueber den geteilten Ray-Cast
``geo_ray_cast._point_in_ring`` (einzige Implementierung); Loecher werden
beachtet. ``point_in_geometry`` ist zugleich der Polygon-Test von
``meteoalarm.py`` (vormals eine lokale Kopie).
"""
from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Optional

from services.official_alerts.geo_ray_cast import _point_in_ring

logger = logging.getLogger(__name__)

_Feature = tuple[str, list, tuple[float, float, float, float]]


def _point_in_polygon_coords(lat: float, lon: float, coords: list) -> bool:
    """Ein GeoJSON-Polygon (Aussenring + Loecher, ``[lon, lat]``-Paare)."""
    if not coords:
        return False
    if not _point_in_ring(lat, lon, coords[0]):
        return False
    return not any(_point_in_ring(lat, lon, hole) for hole in coords[1:])


def point_in_geometry(lat: float, lon: float, geometry: dict) -> bool:
    """Polygon/MultiPolygon (inkl. Loecher); jeder andere Typ -> False."""
    gtype = geometry.get("type")
    coords = geometry.get("coordinates")
    if gtype == "Polygon":
        return _point_in_polygon_coords(lat, lon, coords)
    if gtype == "MultiPolygon":
        return any(_point_in_polygon_coords(lat, lon, poly) for poly in coords or [])
    return False


def _geometry_bbox(geometry: dict) -> Optional[tuple[float, float, float, float]]:
    coords = geometry.get("coordinates") or []
    polys = [coords] if geometry.get("type") == "Polygon" else coords
    points = [p for poly in polys for ring in poly[:1] for p in ring]
    if not points:
        return None
    lons = [p[0] for p in points]
    lats = [p[1] for p in points]
    return min(lons), min(lats), max(lons), max(lats)


def _load_features(path: Path) -> list[_Feature]:
    """Fail-soft: fehlende/kaputte Datei oder falscher Typ -> leere Liste."""
    try:
        doc = json.loads(Path(path).read_text(encoding="utf-8"))
        features = doc.get("features") or []
        out: list[_Feature] = []
        for feature in features:
            region_id = (feature.get("properties") or {}).get("id")
            geometry = feature.get("geometry") or {}
            bbox = _geometry_bbox(geometry)
            if region_id and bbox is not None:
                out.append((str(region_id), geometry, bbox))
        return out
    except Exception:
        logger.warning("region_mapper: Regionsdatei %s nicht ladbar", path, exc_info=True)
        return []


class RegionMapper:
    """Punkt -> Regions-IDs fuer EINE GeoJSON-Datei (Cache je Instanz)."""

    def __init__(self, geojson_path: Path | str) -> None:
        self._path = Path(geojson_path)
        self._features: Optional[list[_Feature]] = None

    def _loaded(self) -> list[_Feature]:
        if self._features is None:
            self._features = _load_features(self._path)
        return self._features

    def regions_at(self, lat: float, lon: float) -> list[str]:
        """ALLE getroffenen Regions-IDs, sortiert (String-Vergleich)."""
        hits = {
            region_id
            for region_id, geometry, (x0, y0, x1, y1) in self._loaded()
            if x0 <= lon <= x1 and y0 <= lat <= y1 and point_in_geometry(lat, lon, geometry)
        }
        return sorted(hits)

    def bbox(self) -> Optional[tuple[float, float, float, float]]:
        """(min_lon, min_lat, max_lon, max_lat) ueber alle Features; None wenn leer."""
        boxes = [box for _id, _geo, box in self._loaded()]
        if not boxes:
            return None
        return (
            min(b[0] for b in boxes), min(b[1] for b in boxes),
            max(b[2] for b in boxes), max(b[3] for b in boxes),
        )
