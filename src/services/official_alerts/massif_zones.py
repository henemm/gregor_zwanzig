"""Amtliche Massiv-Polygone fuer Praefektur-Zugangssperren (Issue #1037, Fix-Runde 2).

Ersetzt die fruehere Zentrum+Radius-Naeherung (Adversary Runde 2 BROKEN: F004
falsch geratene IDs fuer 13/20, F005 Radius-Fehlzuordnung an Kuesten) durch
**exakte amtliche Massiv-Grenzen** + Point-in-Polygon (reines Python-Ray-Casting,
keine neue Laufzeit-Abhaengigkeit).

Datenherkunft (einmalig offline erzeugt, siehe Spec Architektur-Entscheidung 1+2):
1. curl https://www.risque-prevention-incendie.fr/static/{DEPT}/massifs_{DEPT}.fgb
   fuer DEPT in 83 (Var), 13 (Bouches-du-Rhone), 20 (Korsika, kombiniert).
2. Scratch-venv (NICHT im Projekt): `uv venv` + `uv pip install flatgeobuf shapely`,
   `flatgeobuf.geojson.fc_deserialize()` -> GeoJSON-Features. Feature-Properties:
   `ID` (int, entspricht dem massifs-Key im Tages-JSON als String) und
   `NOM_MASSIF` (amtlicher Name, GROSSBUCHSTABEN).
3. Nur Features behalten, deren `str(ID)` ein Key im Tages-JSON
   (`.../import_data/{YYYYMMDD}.json` -> `"massifs"`) ist (volle Abdeckung der
   tatsaechlich unter Zugangs-Restriktionsregime gefuehrten Massive).
4. `shapely.geometry.shape(...).simplify(0.002, preserve_topology=True)` (grobe
   Toleranz ~200m, Massiv-Grenzen brauchen keine Meter-Praezision).
5. Exterior-Ringe je Sub-Polygon (Multi-Ring bei z.B. Iles d'Hyeres) gesammelt,
   Holes bewusst ignoriert (siehe `massif_at()`-Docstring).
6. Ergebnis als `data/massif_polygons.json` gebuendelt (generierte Datendatei,
   zaehlt nicht zum LoC-Limit). Das Erzeugungs-Skript selbst ist NICHT Teil des
   Projekts (Scratch-Wegwerf-Werkzeug).

Koordinaten-Konvention: **GeoJSON lon,lat** (nicht lat,lon!) — jeder Ring-Punkt
ist `[lon, lat]`, exakt wie in den amtlichen `.fgb`-Properties. `massif_at()`
nimmt Aufrufer-seitig `(lat, lon)` entgegen (Konsistenz zu `covers(lat, lon)`)
und rechnet intern konsistent um.

SPEC: docs/specs/modules/issue_1037_official_alerts_massif_closure.md
"""
from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from services.official_alerts.geo_ray_cast import _point_in_ring

logger = logging.getLogger("massif_zones")

_DATA_PATH = Path(__file__).resolve().parent / "data" / "massif_polygons.json"


@dataclass(frozen=True)
class Massif:
    src: str
    massif_id: str
    name: str
    rings: list[list[tuple[float, float]]]  # je Ring: Liste von (lon, lat)


def _load_massifs(path: Path = _DATA_PATH) -> list[Massif]:
    """Laedt die Massiv-Polygone. Fail-soft (Issue #1037 F007): fehlt/kaputt die
    Datei, wird eine Warnung geloggt und [] geliefert — NIE ein Raise, das den
    Import von `services.official_alerts` (und damit Vigilance + MeteoForets +
    Compare-Mail) mitreissen wuerde."""
    try:
        raw = json.loads(path.read_text())
        massifs = []
        for entry in raw:
            rings = [[(float(pt[0]), float(pt[1])) for pt in ring] for ring in entry["rings"]]
            massifs.append(
                Massif(src=entry["src"], massif_id=entry["massif_id"], name=entry["name"], rings=rings)
            )
        return massifs
    except Exception:
        logger.warning(
            "massif_zones: Polygon-Daten nicht ladbar (%s) — Massiv-Sperren deaktiviert",
            path, exc_info=True,
        )
        return []


MASSIFS: list[Massif] = _load_massifs()


def massifs_at(lat: float, lon: float) -> list[Massif]:
    """ALLE Massive, in deren Polygon der Punkt liegt (Issue #1037 F009).

    Manche Massive ueberlappen real (z.B. Sainte-Baume in DEPT 83 UND 13) —
    fuer eine Zugangsfrage muss der Aufrufer alle Treffer kennen, um daraus
    das strengste (hoechste) Niveau zu waehlen.

    Bei Multi-Ring-Massiven (z.B. Iles d'Hyeres, mehrere Inseln) reicht "any
    ring" (OR): Holes werden bewusst ignoriert (kein XOR-Test) — ein Punkt in
    einem inneren Loch eines Massiv-Polygons (seltene Enklave) gilt als
    innerhalb, was fuer die Zugangsfrage praktisch irrelevant/unschaedlich ist.
    """
    hits = []
    for massif in MASSIFS:
        for ring in massif.rings:
            if _point_in_ring(lat, lon, ring):
                hits.append(massif)
                break
    return hits


def massif_at(lat: float, lon: float) -> Optional[Massif]:
    """Erstes Massiv, in dessen Polygon der Punkt liegt (`massifs_at()`[0]).

    Fuer Aufrufer, denen ein Einzelergebnis genuegt (z.B. `covers()`). Bei
    Ueberlappungen liefert `massifs_at()` das vollstaendige Bild.
    """
    hits = massifs_at(lat, lon)
    return hits[0] if hits else None
