"""Gebiet -> zustaendige GEWITTER-Quelle (#1457 S2a, Konzept #1419).

WARUM eine ZWEITE Tabelle neben `providers.region_routing`?
Weil die Zustaendigkeit **groessenabhaengig** ist: Ein Dienst kann fuer
Temperatur, Wind und Schnee die beste Quelle sein und trotzdem ueberhaupt
kein Gewittersignal liefern. Konkreter Fall Oesterreich: Schnee kommt von
GeoSphere (`at_direct`, SNOWGRID), ein Blitz-/Gewittersignal hat GeoSphere
aber nicht — dort wird in S2b der DWD zustaendig. Wuerde man beides in EINE
Tabelle zwingen, muesste der Anreicherungsweg Sonderfaelle je Groesse
kennen; genau das verbietet Spec AC-8. Verwandtes Muster: ADR-0041
(Zustaendigkeit einer Warn-Quelle wird nach Endpunkt-Art bestimmt).

Stand dieser Scheibe (S2a): NUR der FR-Eintrag. Folge-Scheiben tragen hier
je EINE Zeile nach und implementieren `fetch_thunder_signals` in ihrem
Provider — mehr nicht:
  - S2b: DWD fuer DE + Alpenraum
  - S2c: Lueckenfueller fuer den Rest

Import-Regel (Zyklus-Vermeidung, wie `region_routing`): dieses Modul darf
`providers.openmeteo` NICHT importieren.
"""
from __future__ import annotations

from typing import Dict, NamedTuple, Optional


class _ThunderRegion(NamedTuple):
    name: str
    min_lat: float
    max_lat: float
    min_lon: float
    max_lon: float
    provider: str


# Erste treffende Region gewinnt. Das FR-Rechteck ist bewusst identisch zu
# `region_routing._REGIONS` gewaehlt (Frankreich inkl. Korsika); es ist
# trotzdem eine EIGENE Zeile, damit S2b die Gewitter-Zustaendigkeit
# verschieben kann, ohne die Grundvorhersage-Zustaendigkeit anzufassen.
# Bekannte Grenze (Spec "Known Limitations" 3): die Ostgrenze 9,7 O laesst
# fuer Korsika (9,07 O) nur eine kleine Marge.
# #1457 S2b: Das ICON-D2-Gitter (Rechteck der ausgelieferten
# `regular-lat-lon`-Dateien, gemessen 2026-08-03 an einer echten Antwort:
# left=-3,95 bottom=43,17 right=20,35 top=58,09) deckt DE, den Alpenraum und
# Oesterreich ab — und damit auch den Karnischen Hoehenweg, dessen
# Grundvorhersage von GeoSphere kommt, das kein Gewittersignal hat.
# REIHENFOLGE IST TRAGEND: das ICON-D2-Rechteck reicht bis -3,95 O und
# ueberdeckt damit halb Frankreich. Stuende diese Zeile VOR der FR-Zeile,
# verloere Korsika seine bereits produktive Blitzdichte.
# Bekannte Grenze: das Rechteck ist rund 17 % groesser als das eigentliche
# Modellgebiet; ausserhalb davon liefert der Dienst einen Fuellwert, den der
# Provider auf "keine Aussage" abbildet (Spec AC-2).
# #1457 S2c: ICON-EU (~6,5 km) als Lueckenfueller fuer alles Uebrige. Diese
# Zeile MUSS die LETZTE bleiben — sie trifft jede Koordinate. Stuende sie
# frueher, verschluckte sie sowohl Frankreich (Blitzdichte, produktiv seit
# S2a) als auch DE/Alpen/Oesterreich (Blitzpotenzial, produktiv seit S2b);
# beide Gebiete bekaemen still die grobmaschigere Quelle, und an der Ausgabe
# saehe man den Unterschied nicht (Spec AC-8).
# Bekannte Grenze: das Rechteck ist absichtlich die ganze Welt, das
# ICON-EU-Gitter deckt aber nur Europa ab (gemessen: -23,53..62,53 O /
# 29,47..70,53 N). Ausserhalb liefert der Provider "keine Aussage" statt
# eines geklemmten Randwerts (dwd_eu._read_point_value).
_REGIONS: tuple[_ThunderRegion, ...] = (
    _ThunderRegion("FR", 41.3, 51.1, -5.2, 9.7, "fr_direct"),
    _ThunderRegion("DE_ALPEN", 43.17, 58.09, -3.95, 20.35, "de_direct"),
    _ThunderRegion("EU_REST", -90.0, 90.0, -180.0, 180.0, "eu_direct"),
)


def thunder_provider_for(lat: float, lon: float) -> Optional[str]:
    """Name der fuer Gewittersignale zustaendigen Quelle, oder None.

    None heisst: fuer dieses Gebiet ist (noch) keine Gewitterquelle
    eingetragen — dann wird gar nicht erst abgerufen, statt sinnlose Last
    ausserhalb eines Modellgebiets zu erzeugen (Spec AC-6).
    """
    for region in _REGIONS:
        if (region.min_lat <= lat <= region.max_lat
                and region.min_lon <= lon <= region.max_lon):
            return region.provider
    return None


# Benannte Ersatzquelle bei ECHTEM Ausfall einer Direktquelle (#1492 S2a,
# ADR-0047). Bewusst NEBEN `_REGIONS`/`thunder_provider_for`, nicht darin --
# die Primaerauswahl (first-match-wins) bleibt unangetastet (AC-8-Schutz aus
# `feat_1457_s2c_icon_eu_luekenfueller.md`).
_VERTRETUNG: Dict[str, Optional[str]] = {
    "de_direct": "eu_direct",
    "fr_direct": "eu_direct",
    "eu_direct": None,
}


def thunder_vertretung_for(quelle: str) -> Optional[str]:
    """Benannte Ersatzquelle bei echtem Ausfall von `quelle`, oder None."""
    return _VERTRETUNG.get(quelle)
