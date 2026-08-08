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
# (FR, DE_ALPEN, EU_REST) -- KEIN zweites Raster. Fehlende Kombinationen
# (z. B. icon_d2 x FR: das ICON-D2-Gitter deckt Korsika nicht ab;
# metno_nordic: die Historical Forecast API liefert fuer dieses Modell
# durchgaengig kein CAPE) haben BEWUSST keinen Eintrag -- das ist "nicht
# belegt", kein Fehler.
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
