"""Normalisierte Wettermodell-Herkunft + geeichte CAPE-Schwelle je Modell x
Gebiet (Issue #1592 Scheiben B0+C0, Vorbild `providers.thunder_routing`).

CAPE ist ein modellabhaengiges Konstrukt (unterschiedliche Parcel-
Definitionen je Modell) -- eine einzelne feste Schwelle ist deshalb fuer
kein Modell wirklich belegt (Spec Befund A). Dieses Modul buendelt:

1. ``normalize_model_id()`` -- das uneinheitliche Roh-Vokabular
   (Open-Meteo-Technikschluessel, DWD-/Meteo-France-/GeoSphere-Direktworte,
   kuenstliche Werte wie "aggregate"/"snapshot") auf einen kanonischen
   Schluessel je Modellwelt.
2. ``effective_cape_model_id()`` -- die Fallback-Vorrang-Regel fuer CAPE
   EINMAL fuer beide Nutzstellen (C0 Aggregat-Befuellung, C1 Fusion).
3. ``CAPE_THRESHOLDS_JKG`` / ``cape_threshold_jkg()`` -- die statische,
   per ``scripts/eichung_cape_schwelle.py`` einmalig erhobene Eichtabelle
   (95. Perzentil der Modellklimatologie je Modell x Gebiet, mindestens
   300 J/kg; Gebiete = ``providers.thunder_routing._REGIONS``).

Unbekannte Herkunft ODER eine fehlende Kalibrierung fuer eine Kombination
heissen an JEDEM Nachschlag-Ort identisch "nicht belegt" (``None``) --
niemals ein geratener Ersatzwert (Spec Abschnitt 2/3).
"""
from __future__ import annotations

from typing import TYPE_CHECKING, Dict, Optional, Tuple

if TYPE_CHECKING:
    from app.models import ForecastMeta

# Kuenstliche/Nicht-Modell-Werte -- tragen definitionsgemaess KEINE
# Modell-Herkunft (Ortsvergleichs-Aggregat, Schnappschuss-Reload, Fixtures).
_KEINE_HERKUNFT = frozenset({"aggregate", "snapshot", "fixture"})

# Roh-Bezeichner je Modellwelt -> kanonischer Schluessel (Open-Meteo-
# Technikschluessel, s. `providers.openmeteo.REGIONAL_MODELS`). Jede
# Schreibweise derselben Modellwelt MUSS auf denselben Wert abbilden --
# sonst haette die Eichtabelle (unten) zwei Eintraege fuer dieselbe Welt.
_MODEL_ALIASES: Dict[str, str] = {
    "icon_d2": "icon_d2",
    "icon-d2": "icon_d2",
    "meteofrance_arome": "meteofrance_arome",
    "arome-highres": "meteofrance_arome",
    "arome": "meteofrance_arome",
    "icon_eu": "icon_eu",
    "metno_nordic": "metno_nordic",
    "ecmwf_ifs04": "ecmwf_ifs04",
}


def normalize_model_id(raw: Optional[str]) -> Optional[str]:
    """Buendelt das uneinheitliche Modell-Vokabular auf einen kanonischen
    Schluessel (Spec AC-4). Gross-/Kleinschreibung wird ignoriert.
    Kuenstliche Werte (``aggregate``/``snapshot``/``fixture``) und jeder
    unbekannte Wert liefern ``None`` -- "keine Herkunft", nicht "irgendein
    Modell"."""
    if raw is None:
        return None
    lower = raw.lower()
    if lower in _KEINE_HERKUNFT:
        return None
    return _MODEL_ALIASES.get(lower)


def effective_cape_model_id(meta: "ForecastMeta") -> Optional[str]:
    """Fallback-Vorrang-Regel fuer CAPE, EINMAL fuer C0 und C1 (DRY).

    Steht ``"cape"`` in ``meta.fallback_metrics`` (WEATHER-05b-
    Luekenfueller hat CAPE nachgefuellt), gilt der normalisierte
    ``fallback_model`` -- sonst das normalisierte primaere ``model``."""
    if "cape" in meta.fallback_metrics:
        return normalize_model_id(meta.fallback_model)
    return normalize_model_id(meta.model)


# ---------------------------------------------------------------------------
# Eichtabelle (Issue #1592 Scheibe B0)
#
# Erhoben per `scripts/eichung_cape_schwelle.py`, Open-Meteo Historical
# Forecast API, Konvektionssaison April-September 2025 (letzte vollstaendige
# Saison, wortgetreu nach Spec Abschnitt 1). Regel je Eintrag: max(95.
# Perzentil, 300.0 J/kg). Gebiete = `providers.thunder_routing._REGIONS`
# (FR, DE_ALPEN, EU_REST) -- KEIN zweites Raster.
#
# Je Gebiet fuehrt das Skript eine GEORDNETE LISTE von Referenzpunkten
# (Issue #1592 Scheibe C2); der erste Punkt, an dem ein Modell Werte
# liefert, eicht die Kombination. FR: Korsika (42.22, 9.07) zuerst, dann
# franzoesische Alpen (45.00, 6.50); DE_ALPEN und EU_REST je ein Punkt.
# Der Eintrag ("icon_d2", "FR") stammt vom zweiten FR-Punkt -- Korsika liegt
# ausserhalb des ICON-D2-Gitters. Alle uebrigen zehn Werte stammen
# unveraendert vom jeweils ersten Punkt (Regressionsschutz, C2 AC-2).
#
# Die verbliebenen zwei fehlenden Kombinationen haben BEWUSST keinen Eintrag
# -- das ist "nicht belegt", kein Fehler, und in beiden Faellen eine
# gemessene leere Menge, keine offene Luecke:
# - `icon_d2 x EU_REST`: die einzige Flaeche, auf der ICON-D2-Gitter und
#   EU_REST-Gebiet zusammenfallen, liegt unterhalb 43,17 Grad N (darueber
#   beginnt laut `thunder_routing._REGIONS` das Gebiet DE_ALPEN); an vier
#   dort geprueften Punkten liefert ICON-D2 ueberall 0 Werte. Ein weiterer
#   Referenzpunkt wuerde nichts eichen, was der Produktivpfad je erreicht.
# - `metno_nordic x *`: der Produktiv-Endpunkt `/v1/metno` liefert
#   ueberhaupt kein CAPE (Stockholm, Jotunheimen, Tromsoe je 0 Werte;
#   Gegenprobe `/v1/dwd-icon` am selben Ort: 48 Werte). Wo nie ein Wert
#   ankommt, fehlt keine Schwelle.
#
# WICHTIG (PO-Korrektur 2026-08-08): `meteofrance_arome` wird ueber die
# benannte Variante `meteofrance_seamless` geeicht, NICHT
# `meteofrance_arome_france_hd` -- der Produktiv-Endpunkt `/v1/meteofrance`
# liefert nachweislich (Wert-fuer-Wert-Vergleich, s. Skript-Docstring)
# `meteofrance_seamless`. Der Tabellenschluessel bleibt trotzdem
# `"meteofrance_arome"` (== `normalize_model_id()`-Ergebnis fuer den
# REGIONAL_MODELS-`id`, den `ForecastMeta.model` zur Laufzeit traegt).
# Ebenso bleibt der Schluessel `"ecmwf_ifs04"`, obwohl die Historical
# Forecast API dafuer den Namen `ecmwf_ifs025` erwartet (`ecmwf_ifs04` ist
# dort ein veralteter Name und liefert `null`) -- NICHT "aufraeumen", der
# Nachschlag in `cape_threshold_jkg()` erwartet exakt diesen Schluessel.
#
# Statisch, keine Laufzeit-Abhaengigkeit von der Historical Forecast API.
# Eine erneute Eichung (neue Saison, geaendertes Modellgitter) ist ein
# manueller, bewusster Schritt.
CAPE_THRESHOLDS_JKG: Dict[Tuple[str, str], float] = {
    ("meteofrance_arome", "FR"): 300.0,
    ("meteofrance_arome", "DE_ALPEN"): 380.0,
    ("meteofrance_arome", "EU_REST"): 310.0,
    ("icon_d2", "DE_ALPEN"): 300.0,
    ("icon_d2", "FR"): 300.0,
    ("icon_eu", "FR"): 850.0,
    ("icon_eu", "DE_ALPEN"): 360.0,
    ("icon_eu", "EU_REST"): 300.0,
    ("ecmwf_ifs04", "FR"): 710.0,
    ("ecmwf_ifs04", "DE_ALPEN"): 650.0,
    ("ecmwf_ifs04", "EU_REST"): 420.0,
}


def cape_threshold_jkg(model_id: Optional[str], region: Optional[str]) -> Optional[float]:
    """Schlaegt die kalibrierte CAPE-Schwelle fuer (``model_id``, ``region``)
    nach. ``None``, wenn ``model_id`` oder ``region`` ``None`` ist, oder
    keine Kalibrierung fuer die Kombination vorliegt -- beide Faelle heissen
    hier identisch "nicht belegt" (Spec Abschnitt 1 Punkt 4)."""
    if model_id is None or region is None:
        return None
    return CAPE_THRESHOLDS_JKG.get((model_id, region))


# Issue #1592 Scheibe C3: kein neu gesetzter Wert -- die bis Scheibe C1
# ueberall gueltige, modellblinde CAPE-Schwelle. Genau fuer DIESE Welt wurde
# die Empfindlichkeitsleiter der CAPE-Aenderungsalarme (1200/600/200,
# `services.alert_preset._PRESET_TABLE`) geschrieben. Als benannte Konstante
# abgelegt, damit sie nirgends als nackte 1000 im Code auftaucht.
CAPE_REFERENZ_NIVEAU_JKG = 1000.0


def cape_delta_threshold_jkg(
    nominal: float, model_id: Optional[str], region: Optional[str]
) -> Optional[float]:
    """Rechnet eine nominale Delta-Schwelle (aus der Empfindlichkeitsleiter)
    in die Modellwelt von (``model_id``, ``region``) um:

        wirksame Schwelle = nominal * cape_threshold_jkg(model_id, region)
                             / CAPE_REFERENZ_NIVEAU_JKG

    ``None``, wenn ``cape_threshold_jkg()`` ``None`` liefert (unbekannte
    Herkunft ODER Kombination ohne Eichwert) -- "nicht belegt" heisst hier
    identisch zu jedem anderen Nachschlag in diesem Modul (Spec Abschnitt
    2/3). Kein Rueckfall auf ``nominal``."""
    geeicht = cape_threshold_jkg(model_id, region)
    if geeicht is None:
        return None
    return nominal * geeicht / CAPE_REFERENZ_NIVEAU_JKG
