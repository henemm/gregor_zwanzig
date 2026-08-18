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
    # #1758: additive Zusatzquellen desselben Gebiets (ADR-0057) -- die
    # PRIMAERE Quelle (`provider` oben) bleibt fuer Bestandsaufrufer
    # unveraendert; Zusatzquellen kommen NUR ueber `thunder_providers_for()`
    # zum Zug, nie ueber `thunder_provider_for()`.
    zusatzquellen: tuple = ()


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
# #1758 (ADR-0057): DE_ALPEN bekommt `geosphere` als ZUSAETZLICHE, additive
# Gewitterquelle -- Oesterreich (Teil dieses Gebiets) hat mit dem AROME-Modell
# (2,5 km) ein zweites, unabhaengiges Konvektionssignal (cape/cin), das der
# DWD nicht ersetzt. FR/EU_REST bekommen bewusst KEINE Zusatzquelle in dieser
# Spec (Scope-Abgrenzung).
_REGIONS: tuple[_ThunderRegion, ...] = (
    _ThunderRegion("FR", 41.3, 51.1, -5.2, 9.7, "fr_direct"),
    _ThunderRegion("DE_ALPEN", 43.17, 58.09, -3.95, 20.35, "de_direct", ("geosphere",)),
    _ThunderRegion("EU_REST", -90.0, 90.0, -180.0, 180.0, "eu_direct"),
)


def thunder_region_for(lat: float, lon: float) -> Optional[str]:
    """Name des Gewitter-Zustaendigkeitsgebiets fuer (lat, lon), oder None.

    Issue #1592 C1: nutzt DASSELBE ``_REGIONS``-Raster (first-match-wins)
    wie ``thunder_provider_for()`` -- liefert aber den Gebietsnamen statt
    des Provider-Namens. KEIN zweites Raster (Vorgabe der Spec). ``None``
    ist hier strukturell unerreichbar, solange die letzte Zeile des
    Rasters die ganze Welt abdeckt -- bleibt trotzdem explizit typisiert,
    falls sich das Raster kuenftig aendert.
    """
    for region in _REGIONS:
        if (region.min_lat <= lat <= region.max_lat
                and region.min_lon <= lon <= region.max_lon):
            return region.name
    return None


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


def _region_fuer(lat: float, lon: float) -> Optional[_ThunderRegion]:
    """Internes Gegenstueck zu `thunder_provider_for()`, liefert die GANZE
    Region (inkl. Zusatzquellen) statt nur des Providernamens. Fragt DASSELBE
    Raster ab, aber UNABHAENGIG von `thunder_provider_for()` -- so bleibt
    `thunder_providers_for()` unten erkennbar, ob dessen primaere Quelle von
    aussen ueberschrieben wurde (s. dort)."""
    for region in _REGIONS:
        if (region.min_lat <= lat <= region.max_lat
                and region.min_lon <= lon <= region.max_lon):
            return region
    return None


def thunder_providers_for(lat: float, lon: float) -> tuple[str, ...]:
    """Alle fuer (lat, lon) zustaendigen Gewitterquellen, additiv (#1758,
    ADR-0057) -- nicht nur die primaere.

    Baut auf `thunder_provider_for()` auf (bleibt fuer Bestandsaufrufer und
    -Tests patchbar, first-match-wins unveraendert) und ergaenzt die
    REGION-eigenen Zusatzquellen aus `_REGIONS` NUR, wenn die Primaerquelle
    NICHT von aussen ueberschrieben wurde. Ohne diese Absicherung wuerde ein
    Test, der nur `thunder_provider_for()` patcht (z.B. auf eine Test-Quelle),
    unbemerkt eine ECHTE Zweitquelle (GeoSphere) mit auf die Reise schicken --
    genau das Regressionsrisiko, vor dem die Spec warnt (Fill-only-Waechter
    sitzt am gemeinsamen Anschlusspunkt fuer ALLE Gebiete).
    """
    primaer = thunder_provider_for(lat, lon)
    if primaer is None:
        return ()
    region = _region_fuer(lat, lon)
    if region is None or region.provider != primaer:
        return (primaer,)
    zusatz = tuple(
        quelle for quelle in region.zusatzquellen
        if _zusatzquelle_zustaendig(quelle, lat, lon)
    )
    return (primaer, *zusatz)


def _zusatzquelle_zustaendig(quelle: str, lat: float, lon: float) -> bool:
    """Prueft, ob eine additive Zusatzquelle (lat, lon) innerhalb ihres
    EIGENEN Modellgitters bedient -- nicht nur innerhalb des groesseren
    Gebietsrechtecks der Primaerquelle (#1758 AC-12, Team-Lead-Korrektur nach
    initialem GREEN).

    Konkret: `DE_ALPEN` (Grundvorhersage-/DWD-Gebiet, bis 58.09 N) ist
    ERHEBLICH groesser als das AROME-Gitter von GeoSphere (bis 51.819 N,
    gemessen 2026-08-18) -- Hamburg/Berlin liegen in DE_ALPEN, aber
    ausserhalb des AROME-Gitters. Ohne diese Pruefung wuerde dort bei jedem
    Punkt ein GeoSphere-Abruf feuern, der garantiert mit HTTP 400 "outside
    of dataset bounds" endet -- genau die sinnlose Last, die
    `thunder_provider_for()` fuer die PRIMAERE Quelle bereits verhindert.

    Lazy Import (Zyklus-Vermeidung, wie `region_routing`-Import-Regel oben):
    `geosphere.py` importiert `thunder_routing` nicht, ein Modul-Import
    waere unkritisch, bleibt hier trotzdem lazy fuer Konsistenz mit dem
    uebrigen Modul."""
    if quelle == "geosphere":
        from providers.geosphere import arome_grid_covers
        return arome_grid_covers(lat, lon)
    return True


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
