"""Statische Département-Zentroid-Tabelle + Nächste-Nachbar-Lookup (Issue #1035).

Öffentliche Näherungs-Zentroide (Präfektur-Koordinaten) für die volle
französische Metropole (Départements 01–95, Korsika als "2A"/"2B" statt "20").
Keine Sonderfall-Logik: Korsika sind zwei ganz normale Tabellenzeilen.

``lookup_department(lat, lon)`` sucht per euklidischer Nächster-Nachbar-Distanz
den passenden Code — kein Geo-Package. Für Vigilance-Granularität (selbst nur
Département-genau) ausreichend; an Grenzen sind seltene Fehlnachbarn möglich
(siehe Spec "Known Limitations").

SPEC: docs/specs/modules/issue_1035_vigilance_source.md
"""
from __future__ import annotations

from typing import Dict, Optional, Tuple

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


def lookup_department(lat: float, lon: float) -> Optional[str]:
    """Ermittelt den Département-Code des nächstgelegenen Zentroids.

    Reine euklidische Nächste-Nachbar-Suche über ``DEPARTMENT_CENTROIDS``.
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
