"""Département-Zuordnung: Point-in-Polygon + Nächste-Nachbar-Fallback (Issue #1254).

`lookup_department(lat, lon)` prüft zuerst per Point-in-Polygon gegen die
gebündelten echten Département-Grenzen (`data/department_polygons.json`,
analog `massif_zones.py`, Issue #1037). Das behebt Fehlzuordnungen an
exzentrischen Rändern (z.B. Draguignan/Fréjus im Département Var, dessen
Präfektur Toulon im Südwest-Eck liegt — die frühere reine
Nächster-Zentroid-Näherung ordnete diese Orte faelschlich Nachbar-Départements
zu). Nur wenn die Polygondatei fehlt/leer ist (degradierter Fall), greift die
bisherige euklidische Nächster-Nachbar-Suche über ``DEPARTMENT_CENTROIDS`` als
Fallback — unverändert, deckt den Ausfall der Datenquelle ab. Sind Polygone
geladen, trifft aber keines, liefert `lookup_department()` seit Issue #1400
`None` — der Punkt liegt ausserhalb Frankreichs (bzw. ausserhalb des
Randpuffers, s.u.). Vorher griff der Zentroid-Notbehelf auch in diesem Fall
bedingungslos und lieferte fuer JEDEN Punkt der Erde (Sydney, Moskau, Mailand,
Bern, Freiburg …) einen franzoesischen Département-Code — sicherheitsrelevant
ueber `VigilanceSource.covers()`, deren AROME-Bbox u.a. Mailand, Turin, Bern,
Freiburg und Barcelona einschliesst.

Adversary-Nachbesserung F001 (Issue #1400 Fix-Loop): das bare `None` bei
"kein Polygon trifft" traf auch ECHTE franzoesische Orte, deren Landmasse
durch die Polygon-Vereinfachung (`simplify(0.005, ...)`, s.u.) verschwunden
war — belegt fuer Île de Ré (0,05 km ausserhalb), Camaret-sur-Mer/Presqu'île
de Crozon (0,09 km), Île de Noirmoutier (2,89 km). Deshalb greift bei einem
Nicht-Treffer zusaetzlich `_nearest_department_within_threshold()`: liegt der
naechste Polygonrand hoechstens `_NEAR_BORDER_THRESHOLD_KM` (5 km) entfernt,
gilt dessen Département; darueber bleibt es bei `None`. 5 km wurden bewusst
grosszuegig ueber dem schlechtesten belegten Fall (Noirmoutier, 2,89 km)
gewaehlt (PO-Praeferenz: ein stiller Warnungs-Verlust auf einer bewohnten
franzoesischen Insel wiegt schwerer als eine Warnung fuer einen Nachbarort
jenseits der Grenze). Gemessene Nebenwirkung: Basel (1,81 km), Genf (4,33 km)
und Saarbruecken (3,27 km) fallen bei 5 km ebenfalls in den Puffer — vertret-
bar (Wetter haelt sich nicht an Staatsgrenzen). Freiburg i.Br. (16,60 km),
Karlsruhe (13,22 km), Luxemburg-Stadt (11,74 km), Andorra la Vella (11,93 km),
Bern (49,78 km), Zuerich (75,44 km), Mailand (156,72 km) und Barcelona
(107,56 km) bleiben unveraendert `None`.

Adversary-Nachbesserung F003 (Issue #1400 Fix-Loop, KRITISCH): der Randpuffer
durchsuchte urspruenglich nur Exterior-Ringe und ignorierte Holes — fuer
Département 66 (Pyrénées-Orientales) gibt es ein VERWAISTES Hole (Llívia,
spanische Gemeinde vollstaendig von franzoesischem Staatsgebiet umschlossen,
im Datensatz ohne eigenes Polygon, weil Spanien darin nicht vorkommt). Ohne
Vorabpruefung haette der Puffer Llívia faelschlich Département 66 zugeordnet
(Aussenrand nur ~2,9-4,2 km entfernt, deutlich innerhalb der 5-km-Schwelle) —
exakt die Fehlerart, gegen die #1400 antritt, diesmal fuer den unmittelbaren
Nachbarort statt fuer Sydney. `_point_in_any_hole()` prueft deshalb VOR jeder
Abstandsrechnung, ob der Punkt in irgendeinem Hole liegt (Enklave MIT eigenem
Polygon wie Enclave des Papes ODER verwaist wie Llívia) und liefert dann
sofort `None`, unabhaengig vom Abstand zu jedem Aussenrand. Gewaehlte Variante:
Vorab-Mitgliedschaftspruefung statt Hole-Raender in die Abstandssuche
einzubeziehen — ein Punkt IN einem Hole ist ein binaerer geometrischer
Tatbestand (das Hole ist explizit NICHT das umschliessende Département),
keine Abwaegungsfrage wie "wie nah ist der naechste Rand".

Performance-Nachbesserung F004 (Issue #1400 Fix-Loop): der volle Segment-Scan
(96 Départements, 22.387 Aussenrand-Vertices) kostet ~12 ms je Nicht-Treffer
und liefe bei jedem Trip-/Vergleichs-Rendern erneut fuer dieselben, ortsfesten
Wegpunkte. `lookup_department()` cacht deshalb ueber `_lookup_cache`, geschluesselt
auf eine auf 2 Nachkommastellen gerundete Koordinate (~1,1 km Gitterzelle bei
diesen Breiten — klar unterhalb der 5-km-Schwelle, verwischt also keinen
Grenz-/Enklavenfall) und begrenzt (LRU-artig, `_LOOKUP_CACHE_MAX_ENTRIES`) auf
10.000 Eintraege (mehr als die realistische Zahl aktiver Wegpunkte).

Datenherkunft `department_polygons.json` (einmalig offline erzeugt, Scratch-venv
AUSSERHALB des Projekts, analog `massif_zones.py`-Rezept):
1. Quelle: `gregoiredavid/france-geojson` `departements.geojson`
   (Property `properties.code` = Département-Code, Korsika "2A"/"2B").
2. Scratch-venv: `python3 -m venv /tmp/geo-venv && pip install shapely`.
3. Je Feature: `shapely.geometry.shape(geom).simplify(0.005, preserve_topology=True)`,
   je (Multi)Polygon Exterior-Ring UND Interior-Ringe (Holes) gesammelt —
   Holes sind fuer Enklaven (Issue #1254 AC-8, Enclave des Papes: 84-Exklave
   als Loch in 26) zwingend noetig.
4. Ausgabe: Liste von
   `{"code": "26", "polygons": [{"exterior": [[lon,lat],...], "holes": [[[lon,lat],...], ...]}, ...]}`.

Öffentliche Näherungs-Zentroide (Präfektur-Koordinaten) für die volle
französische Metropole (Départements 01–95, Korsika als "2A"/"2B" statt "20").
Keine Sonderfall-Logik: Korsika sind zwei ganz normale Tabellenzeilen.

SPEC: docs/specs/modules/issue_1254_department_boundaries.md
      docs/specs/modules/issue_1035_vigilance_source.md (Ursprungs-Zentroide)
"""
from __future__ import annotations

import functools
import json
import logging
import math
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from services.official_alerts.geo_ray_cast import _point_in_ring

logger = logging.getLogger("department_mapper")

_DATA_PATH = Path(__file__).resolve().parent / "data" / "department_polygons.json"

# Département-Code -> (lat, lon) Näherungs-Zentroid (Präfektur-Koordinaten).
DEPARTMENT_CENTROIDS: Dict[str, Tuple[float, float]] = {
    "01": (46.2057, 5.2256),   # Ain — Bourg-en-Bresse
    "02": (49.5641, 3.6244),   # Aisne — Laon
    "03": (46.5667, 3.3333),   # Allier — Moulins
    "04": (44.0921, 6.2358),   # Alpes-de-Haute-Provence — Digne-les-Bains
    "05": (44.5594, 6.0797),   # Hautes-Alpes — Gap
    "06": (43.7102, 7.2620),   # Alpes-Maritimes — Nice
    "07": (44.7348, 4.5992),   # Ardèche — Privas
    "08": (49.7719, 4.7161),   # Ardennes — Charleville-Mézières
    "09": (42.9637, 1.6045),   # Ariège — Foix
    "10": (48.2973, 4.0744),   # Aube — Troyes
    "11": (43.2130, 2.3491),   # Aude — Carcassonne
    "12": (44.3496, 2.5730),   # Aveyron — Rodez
    "13": (43.2965, 5.3698),   # Bouches-du-Rhône — Marseille
    "14": (49.1829, -0.3707),  # Calvados — Caen
    "15": (44.9256, 2.4433),   # Cantal — Aurillac
    "16": (45.6484, 0.1562),   # Charente — Angoulême
    "17": (46.1603, -1.1511),  # Charente-Maritime — La Rochelle
    "18": (47.0810, 2.3987),   # Cher — Bourges
    "19": (45.2673, 1.7714),   # Corrèze — Tulle
    "2A": (41.9192, 8.7386),   # Corse-du-Sud — Ajaccio
    "2B": (42.6979, 9.4508),   # Haute-Corse — Bastia
    "21": (47.3220, 5.0415),   # Côte-d'Or — Dijon
    "22": (48.5136, -2.7658),  # Côtes-d'Armor — Saint-Brieuc
    "23": (46.1710, 1.8720),   # Creuse — Guéret
    "24": (45.1848, 0.7218),   # Dordogne — Périgueux
    "25": (47.2380, 6.0243),   # Doubs — Besançon
    "26": (44.9333, 4.8924),   # Drôme — Valence
    "27": (49.0270, 1.1508),   # Eure — Évreux
    "28": (48.4439, 1.4890),   # Eure-et-Loir — Chartres
    "29": (47.9960, -4.0970),  # Finistère — Quimper
    "30": (43.8367, 4.3601),   # Gard — Nîmes
    "31": (43.6047, 1.4442),   # Haute-Garonne — Toulouse
    "32": (43.6469, 0.5855),   # Gers — Auch
    "33": (44.8378, -0.5792),  # Gironde — Bordeaux
    "34": (43.6108, 3.8767),   # Hérault — Montpellier
    "35": (48.1173, -1.6778),  # Ille-et-Vilaine — Rennes
    "36": (46.8103, 1.6910),   # Indre — Châteauroux
    "37": (47.3941, 0.6848),   # Indre-et-Loire — Tours
    "38": (45.1885, 5.7245),   # Isère — Grenoble
    "39": (46.6742, 5.5548),   # Jura — Lons-le-Saunier
    "40": (43.8913, -0.4990),  # Landes — Mont-de-Marsan
    "41": (47.5861, 1.3359),   # Loir-et-Cher — Blois
    "42": (45.4397, 4.3872),   # Loire — Saint-Étienne
    "43": (45.0430, 3.8850),   # Haute-Loire — Le Puy-en-Velay
    "44": (47.2184, -1.5536),  # Loire-Atlantique — Nantes
    "45": (47.9029, 1.9093),   # Loiret — Orléans
    "46": (44.4478, 1.4416),   # Lot — Cahors
    "47": (44.2032, 0.6161),   # Lot-et-Garonne — Agen
    "48": (44.5180, 3.5008),   # Lozère — Mende
    "49": (47.4784, -0.5632),  # Maine-et-Loire — Angers
    "50": (49.1158, -1.0889),  # Manche — Saint-Lô
    "51": (48.9566, 4.3637),   # Marne — Châlons-en-Champagne
    "52": (48.1120, 5.1389),   # Haute-Marne — Chaumont
    "53": (48.0698, -0.7695),  # Mayenne — Laval
    "54": (48.6921, 6.1844),   # Meurthe-et-Moselle — Nancy
    "55": (48.7710, 5.1608),   # Meuse — Bar-le-Duc
    "56": (47.6582, -2.7608),  # Morbihan — Vannes
    "57": (49.1193, 6.1757),   # Moselle — Metz
    "58": (46.9896, 3.1590),   # Nièvre — Nevers
    "59": (50.6292, 3.0573),   # Nord — Lille
    "60": (49.4295, 2.0807),   # Oise — Beauvais
    "61": (48.4306, 0.0915),   # Orne — Alençon
    "62": (50.2910, 2.7772),   # Pas-de-Calais — Arras
    "63": (45.7772, 3.0870),   # Puy-de-Dôme — Clermont-Ferrand
    "64": (43.2951, -0.3708),  # Pyrénées-Atlantiques — Pau
    "65": (43.2328, 0.0781),   # Hautes-Pyrénées — Tarbes
    "66": (42.6887, 2.8948),   # Pyrénées-Orientales — Perpignan
    "67": (48.5734, 7.7521),   # Bas-Rhin — Strasbourg
    "68": (48.0794, 7.3585),   # Haut-Rhin — Colmar
    "69": (45.7640, 4.8357),   # Rhône — Lyon
    "70": (47.6216, 6.1554),   # Haute-Saône — Vesoul
    "71": (46.3069, 4.8283),   # Saône-et-Loire — Mâcon
    "72": (48.0061, 0.1996),   # Sarthe — Le Mans
    "73": (45.5646, 5.9178),   # Savoie — Chambéry
    "74": (45.8992, 6.1294),   # Haute-Savoie — Annecy
    "75": (48.8566, 2.3522),   # Paris
    "76": (49.4432, 1.0993),   # Seine-Maritime — Rouen
    "77": (48.5399, 2.6608),   # Seine-et-Marne — Melun
    "78": (48.8014, 2.1301),   # Yvelines — Versailles
    "79": (46.3239, -0.4588),  # Deux-Sèvres — Niort
    "80": (49.8941, 2.2958),   # Somme — Amiens
    "81": (43.9289, 2.1480),   # Tarn — Albi
    "82": (44.0179, 1.3550),   # Tarn-et-Garonne — Montauban
    "83": (43.1242, 5.9280),   # Var — Toulon
    "84": (43.9493, 4.8055),   # Vaucluse — Avignon
    "85": (46.6705, -1.4269),  # Vendée — La Roche-sur-Yon
    "86": (46.5802, 0.3404),   # Vienne — Poitiers
    "87": (45.8336, 1.2611),   # Haute-Vienne — Limoges
    "88": (48.1744, 6.4515),   # Vosges — Épinal
    "89": (47.7982, 3.5735),   # Yonne — Auxerre
    "90": (47.6379, 6.8628),   # Territoire de Belfort — Belfort
    "91": (48.6293, 2.4415),   # Essonne — Évry
    "92": (48.8924, 2.2154),   # Hauts-de-Seine — Nanterre
    "93": (48.9106, 2.4397),   # Seine-Saint-Denis — Bobigny
    "94": (48.7904, 2.4556),   # Val-de-Marne — Créteil
    "95": (49.0361, 2.0631),   # Val-d'Oise — Cergy
}


def _load_department_polygons(path: Path = _DATA_PATH) -> List[dict]:
    """Laedt die gebündelten Département-Polygone. Fail-soft (Issue #1254,
    analog `massif_zones._load_massifs`): fehlt/kaputt die Datei, wird eine
    Warnung geloggt und [] geliefert — NIE ein Raise, das den Import von
    `services.official_alerts` mitreissen wuerde.

    Je Département eine Liste von Polygonen, je Polygon Exterior-Ring UND
    Interior-Ringe (Holes) getrennt (Issue #1254 AC-8, Enklaven-Behandlung).
    """
    try:
        raw = json.loads(path.read_text())
        entries = []
        for entry in raw:
            polygons = []
            for poly in entry["polygons"]:
                exterior = [(float(pt[0]), float(pt[1])) for pt in poly["exterior"]]
                holes = [
                    [(float(pt[0]), float(pt[1])) for pt in hole]
                    for hole in poly.get("holes", [])
                ]
                polygons.append({"exterior": exterior, "holes": holes})
            entries.append({"code": entry["code"], "polygons": polygons})
        return entries
    except Exception:
        logger.warning(
            "department_mapper: Polygon-Daten nicht ladbar (%s) — falle auf "
            "Nächster-Nachbar-Zentroid zurück",
            path, exc_info=True,
        )
        return []


_DEPARTMENT_POLYGONS: List[dict] = _load_department_polygons()


def _nearest_centroid(lat: float, lon: float) -> Optional[str]:
    """Reine euklidische Nächste-Nachbar-Suche über ``DEPARTMENT_CENTROIDS``.

    Gibt ``None`` nur zurück, wenn die Tabelle leer wäre (praktisch nie).
    """
    best_code: Optional[str] = None
    best_dist = float("inf")
    for code, (c_lat, c_lon) in DEPARTMENT_CENTROIDS.items():
        dist = (lat - c_lat) ** 2 + (lon - c_lon) ** 2
        if dist < best_dist:
            best_dist = dist
            best_code = code
    return best_code


# Adversary-Nachbesserung F001 (Issue #1400 Fix-Loop): Grenzabstand, ab dem
# ein Nicht-Treffer noch dem naechstgelegenen Département zugerechnet wird
# (s. Modul-Docstring fuer die vollstaendige Messreihe/Begruendung). 5 km
# liegen bewusst deutlich ueber dem schlechtesten belegten Vereinfachungs-
# Artefakt (Île de Noirmoutier, 2,89 km).
_NEAR_BORDER_THRESHOLD_KM = 5.0

# Grobe, aber fuer diese Distanz-Groessenordnung (Meter bis niedrige
# zweistellige Kilometer) ausreichend genaue Kilometer-je-Grad-Skalierung
# (Breitengrad-abhaengige Laengengrad-Stauchung, Erdradius wie
# `services.utils.geo.haversine_km`).
_KM_PER_DEG_LAT = 111.32


def _point_to_segment_km(
    lat: float, lon: float, lat1: float, lon1: float, lat2: float, lon2: float,
) -> float:
    """Kuerzester Abstand (km) eines Punktes zu einem Liniensegment, ueber
    eine lokale, am Punkt zentrierte Plattkarten-Projektion (ausreichend
    genau fuer die hier relevanten Abstaende von wenigen Kilometern)."""
    km_per_deg_lon = _KM_PER_DEG_LAT * math.cos(math.radians(lat))
    px, py = lon * km_per_deg_lon, lat * _KM_PER_DEG_LAT
    ax, ay = lon1 * km_per_deg_lon, lat1 * _KM_PER_DEG_LAT
    bx, by = lon2 * km_per_deg_lon, lat2 * _KM_PER_DEG_LAT
    dx, dy = bx - ax, by - ay
    if dx == 0.0 and dy == 0.0:
        return math.hypot(px - ax, py - ay)
    t = max(0.0, min(1.0, ((px - ax) * dx + (py - ay) * dy) / (dx * dx + dy * dy)))
    return math.hypot(px - (ax + t * dx), py - (ay + t * dy))


def _point_in_any_hole(lat: float, lon: float) -> bool:
    """Adversary-Nachbesserung F003 (Issue #1400 Fix-Loop): True, wenn der
    Punkt in IRGENDEINEM Hole eines beliebigen Département-Polygons liegt —
    unabhaengig davon, ob dieses Hole eine Enklave mit eigenem Polygon im
    Datensatz ist (Enclave des Papes, 84 in 26) oder eine VERWAISTE Flaeche
    OHNE eigenes Polygon (Llívia, spanische Gemeinde vollstaendig von
    Département 66 umschlossen — Spanien kommt im Datensatz nicht vor). In
    beiden Faellen ist der Punkt NICHT dem umschliessenden Département
    zuzurechnen, auch wenn dessen Aussenrand naeher als
    `_NEAR_BORDER_THRESHOLD_KM` liegt."""
    for entry in _DEPARTMENT_POLYGONS:
        for poly in entry["polygons"]:
            for hole in poly["holes"]:
                if _point_in_ring(lat, lon, hole):
                    return True
    return False


# F004 (Issue #1400 Fix-Loop, Performance): Rundung fuer den Lookup-Cache-
# Schluessel. 4 Nachkommastellen (~11 m bei diesen Breiten) — dieselbe
# Praezision wie das bestehende Vorbild `geosphere_warn._round_coord()`.
# ~11 m liegen ~450x unterhalb der 5-km-Schwelle (`_NEAR_BORDER_THRESHOLD_KM`)
# und damit auch weit unterhalb der Ausdehnung der kleinsten bekannten
# Enklave (Llívia, ~2 km).
#
# Adversary-Nachbesserung F005 (Issue #1400 Fix-Loop, KRITISCH): TROTZDEM
# erzeugt jede Rundung zwangslaeufig ein schmales Fehlerband entlang JEDER
# Grenze, die sie beruehrt — belegt fuer 5 Feingitter-Punkte, die roh
# nachweislich IN Llívia lagen, nach der Rundung aber knapp ausserhalb des
# Holes landeten und faelschlich `"66"` statt `None` bekamen (z.B.
# (42,45855 / 2,00006), 5,3 m von der echten Grenze). Deshalb gilt seit F005:
# **jede Hole-Mitgliedschaftspruefung laeuft IMMER auf der ROHEN, unge-
# rundeten Koordinate** (`_point_in_any_hole()`, Schritt 1 unten) — NUR das
# teure Abstands-Ranking gegen die 22.387 Aussenrand-Vertices wird ueber die
# gerundete Koordinate gecacht (`_lookup_department_cached()`). Das kostet
# fast nichts (15 Holes total gegenueber 22.387 Aussenrand-Vertices) und
# behaelt den Performance-Gewinn von F004 fuer den teuren Teil.
#
# Restbandbreite (dokumentiert, folgenlos): das gecachte Abstands-Ranking
# selbst bleibt gerundet — ein Punkt kann im Millimeter- bis Meterbereich an
# der 5-km-Schwelle oder an einer Départements-Départements-Grenze kippen.
# Das ist hier ausdruecklich in Kauf genommen (wir akzeptieren an der
# 5-km-Schwelle ohnehin 5 km Unschaerfe, s. Basel/Genf oben) — der
# GEFAEHRLICHE Fall ist ausschliesslich fremdes Staatsgebiet INNERHALB
# Frankreichs (ein Hole), und der ist durch die rohe Hole-Pruefung
# strukturell erledigt, unabhaengig von jeder Rundung.
_LOOKUP_CACHE_ROUND_DECIMALS = 4

# Deckel gegen unbegrenztes Wachstum (`functools.lru_cache` wirft die
# aeltesten Eintraege raus, sobald das Limit erreicht ist) — 10.000 liegt
# weit ueber der realistischen Zahl gleichzeitig aktiver Wegpunkte ueber
# alle Nutzer/Trips/Vergleiche hinweg.
_LOOKUP_CACHE_MAX_ENTRIES = 10_000


@functools.lru_cache(maxsize=_LOOKUP_CACHE_MAX_ENTRIES)
def _lookup_department_cached(lat: float, lon: float) -> tuple[tuple[tuple[int, int], ...], Optional[str]]:
    """Teure, gecachte Geometrie-Vorarbeit fuer eine BEREITS GERUNDETE
    Koordinate (F004) — IGNORIERT Holes vollstaendig (F005: jede
    Hole-Entscheidung laeuft separat auf der rohen Koordinate, s.
    `lookup_department()`). Liefert ein Tupel aus:

    1. Allen (entry_index, poly_index)-Paaren aus `_DEPARTMENT_POLYGONS`,
       deren Exterior-Ring den Punkt enthaelt, in Datensatz-Reihenfolge
       (Issue #1254 AC-8-Vorarbeit: mehrere Treffer sind moeglich, wenn ein
       aeusseres Département ein Hole hat, das mit dem Exterior eines
       ANDEREN Départements zusammenfaellt — Enclave des Papes, 84 in 26).
    2. Dem Département-Code des naechstgelegenen Exterior-Rand-Segments
       ueber ALLE Départements, wenn dessen Abstand
       `_NEAR_BORDER_THRESHOLD_KM` nicht ueberschreitet (Fund F001), sonst
       `None` — faengt Vereinfachungsartefakte auf echten franzoesischen
       Inseln/Halbinseln ab (Île de Ré, Camaret-sur-Mer, Île de Noirmoutier).

    Beide Ergebnisse in EINEM Scan ueber `_DEPARTMENT_POLYGONS` (96
    Départements, 22.387 Aussenrand-Vertices) berechnet — das ist der teure
    Teil, der F004 motiviert hat."""
    exterior_candidates: list[tuple[int, int]] = []
    best_code: Optional[str] = None
    best_dist = float("inf")
    for entry_idx, entry in enumerate(_DEPARTMENT_POLYGONS):
        for poly_idx, poly in enumerate(entry["polygons"]):
            ring = poly["exterior"]
            if _point_in_ring(lat, lon, ring):
                exterior_candidates.append((entry_idx, poly_idx))
            n = len(ring)
            for i in range(n):
                lon1, lat1 = ring[i]
                lon2, lat2 = ring[(i + 1) % n]
                dist = _point_to_segment_km(lat, lon, lat1, lon1, lat2, lon2)
                if dist < best_dist:
                    best_dist = dist
                    best_code = entry["code"]
    nearest_within_threshold = best_code if best_dist <= _NEAR_BORDER_THRESHOLD_KM else None
    return tuple(exterior_candidates), nearest_within_threshold


def lookup_department(lat: float, lon: float) -> Optional[str]:
    """Ermittelt den Département-Code einer Koordinate.

    Schritt 1: fuer jeden Exterior-Kandidaten aus der gecachten,
    GERUNDETEN Geometrie-Vorarbeit (`_lookup_department_cached()`, F004) —
    in Datensatz-Reihenfolge, erster Treffer gewinnt — wird die Hole-
    Ausnahme auf der ROHEN Koordinate geprueft (Adversary F005: eine
    gerundete Hole-Pruefung erzeugt ein Fehlerband entlang jeder Enklaven-
    grenze). Kein Treffer, weil der Punkt in einem der Holes dieses
    Kandidaten liegt (Issue #1254 AC-8: Enklaven wie die Enclave des
    Papes — 84-Exklave als Loch im 26-Polygon) -> naechster Kandidat.

    Schritt 2 (Fallback, NUR im degradierten Fall, Issue #1400): sind KEINE
    Polygone geladen (Datei fehlt/kaputt, s. `_load_department_polygons`),
    greift die bestehende Nächster-Nachbar-Zentroid-Suche über
    ``DEPARTMENT_CENTROIDS`` — unbedingt, liefert IMMER einen Code.

    Schritt 3 (kein Exterior-Kandidat matcht, Issue #1400 + Adversary-
    Nachbesserung F001/F003/F005): liegt der Punkt in IRGENDEINEM Hole
    (`_point_in_any_hole()`, IMMER auf der rohen Koordinate), ist das
    Ergebnis sofort `None` — unabhaengig davon, wie nah ein Aussenrand
    liegt (Llívia liegt nur ~2,9-4,2 km vom Aussenrand von Département 66
    entfernt, also klar innerhalb der 5-km-Schwelle; ohne diese Pruefung
    haette der F001-Puffer den in #1254 fuer Enklaven gebauten Schutz fuer
    jedes Hole OHNE eigenes Polygon ausgehebelt). Sonst liefert die
    gecachte Geometrie-Vorarbeit das Département des naechstgelegenen
    Aussenrand-Segments, wenn dessen Abstand `_NEAR_BORDER_THRESHOLD_KM`
    nicht ueberschreitet, sonst `None` — der Punkt liegt tatsaechlich
    ausserhalb Frankreichs. Vor #1400 griff der Zentroid-Notbehelf
    UNBEDINGT bei jedem Nicht-Treffer und ordnete damit JEDEM Punkt der
    Erde (Sydney, Moskau, Nordpol …) faelschlich einen franzoesischen
    Département-Code zu.
    """
    rounded_lat = round(lat, _LOOKUP_CACHE_ROUND_DECIMALS)
    rounded_lon = round(lon, _LOOKUP_CACHE_ROUND_DECIMALS)
    exterior_candidates, nearest_within_threshold = _lookup_department_cached(rounded_lat, rounded_lon)

    for entry_idx, poly_idx in exterior_candidates:
        poly = _DEPARTMENT_POLYGONS[entry_idx]["polygons"][poly_idx]
        if not any(_point_in_ring(lat, lon, hole) for hole in poly["holes"]):
            return _DEPARTMENT_POLYGONS[entry_idx]["code"]

    if not _DEPARTMENT_POLYGONS:
        return _nearest_centroid(lat, lon)

    if _point_in_any_hole(lat, lon):
        return None
    return nearest_within_threshold
