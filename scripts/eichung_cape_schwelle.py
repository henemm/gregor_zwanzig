#!/usr/bin/env python3
"""Issue #1592 Scheibe B0 -- Einmaliges Eichskript fuer die CAPE-Schwelle je
Modell x Gebiet.

SPEC: docs/specs/modules/fix_1592_s1_cape_modellschwelle.md Abschnitt 1 (B0)

Eichregel (woertlich): Schwelle = max(95. Perzentil der CAPE-Klimatologie
dieses Modells in diesem Gebiet ueber eine Konvektionssaison
April-September, 300.0 J/kg).

Kein Laufzeit-Abruf -- dieses Skript wird EINMALIG von Hand ausgefuehrt, sein
Ergebnis wird als statisches Literal `CAPE_THRESHOLDS_JKG` in
`src/app/model_registry.py` committed. Eine erneute Eichung (neue Saison,
geaendertes Modellgitter) ist ein bewusster manueller Schritt.

Modelle: die fuenf in `openmeteo.REGIONAL_MODELS` tatsaechlich produktiv
waehlbaren IDs. GFS ist NICHT dabei -- Gregor Zwanzig waehlt es nie aus.

Gebiete: dieselben Gewitter-Zustaendigkeitsgebiete wie
`providers.thunder_routing._REGIONS` (FR, DE_ALPEN, EU_REST) -- KEIN zweites
Raster. Je Gebiet EIN fest verdrahteter Referenzpunkt:
- FR: GR20/Korsika (42.22, 9.05) -- derselbe Punkt wie in der
  Analyse-Messung und in der Orientierungs-Abfrage des Auftrags.
- DE_ALPEN: Muenchen-Raum (48.14, 11.58) -- derselbe Punkt wie in der
  Analyse-Messung, bereits kanonischer Referenzpunkt im Repo
  (`tests/unit/test_openmeteo_endpoint_routing.py`).
- EU_REST: Stockholm (59.33, 18.06) -- neu gewaehlt fuer diese Scheibe;
  liegt ausserhalb der FR- UND DE_ALPEN-Rechtecke aus `thunder_routing`
  (FR: lat 41.3-51.1; DE_ALPEN: lat 43.17-58.09) und damit sicher im
  first-match-wins-EU_REST-Zweig; repraesentativ fuer Nordeuropa, wo weder
  AROME noch das ICON-D2-Rechteck zustaendig sind.

Zeitraum: April-September 2025 (letzte vollstaendige Konvektionssaison,
wortgetreu nach Spec). Die vermutete Notwendigkeit einer Abweichung
(Juni-August, erste Fassung dieses Skripts, 2026-08-08) beruhte auf einem zu
schmalen Beispielpaar bei der AC-1-Verifikation (`icon_d2 x DE_ALPEN` fiel
in einer fruehen Messung knapp unter 300) -- eine PO-Nachmessung mit
mehreren Modell/Gebiet-Paaren zeigt, dass April-September die Untergrenze
NICHT flaechendeckend zieht: fuenf von neun Eintraegen liegen strikt
darueber. AC-1 selbst wurde entsprechend verallgemeinert (mind. EIN Eintrag
== 300, mind. EIN Eintrag strikt zwischen 300 und 1000 -- nicht mehr an ein
bestimmtes Modell/Gebiet-Paar gebunden).

Open-Meteo-Modellbezeichner der Historical Forecast API weichen fuer ZWEI
Modelle vom REGIONAL_MODELS-`id` ab -- s. Kommentar an `_MODEL_ARCHIVE_ID`
unten fuer die empirische Herleitung (Endpunkt-vs-benannte-Variante-
Vergleich, PO-Korrektur 2026-08-08).

Liefert die API fuer eine (Modell, Gebiet)-Kombination keine oder eine
durchgaengig leere ("null") Reihe, entsteht KEIN Tabelleneintrag (Spec
Abschnitt 1 Punkt 4) -- kein Fehler, sondern "nicht abgedeckt".
"""
from __future__ import annotations

import json
import statistics
import urllib.error
import urllib.request

HISTORICAL_API = "https://historical-forecast-api.open-meteo.com/v1/forecast"

# Letzte vollstaendige Konvektionssaison April-September 2025 (Spec-Wortlaut).
SEASON_START = "2025-04-01"
SEASON_END = "2025-09-30"

# Untergrenze der Eichregel (NWS/SPC-Leiter, Gesamtkonzept 3.5b).
MIN_THRESHOLD_JKG = 300.0

# REGIONAL_MODELS-id -> Historical-Forecast-API-Bezeichner.
#
# WICHTIG (PO-Korrektur 2026-08-08): der Produktivcode ruft dedizierte
# ENDPUNKTE ab (`/v1/meteofrance`, `/v1/dwd-icon`, `/v1/ecmwf` --
# `providers.openmeteo.REGIONAL_MODELS["endpoint"]`, Abruf ohne `models=`-
# Parameter, `openmeteo.py:350`), NICHT den generischen `/v1/forecast` mit
# einem gewaehlten `models=`-Wert. Die Zuordnung Endpunkt -> benannte
# Modellvariante wurde deshalb EMPIRISCH ermittelt, nicht geraten:
# Produktiv-Endpunkt UND die jeweils kandidierende benannte Variante wurden
# fuer denselben Referenzpunkt und dasselbe Zeitfenster Wert-fuer-Wert
# verglichen (2026-08-08, `curl .../v1/meteofrance` vs.
# `curl .../v1/forecast?models=...`):
# - `/v1/meteofrance` liefert IDENTISCH zu `meteofrance_seamless`
#   (Muenchen UND Korsika, alle Stunden exakt gleich). `meteofrance_arome_
#   france_hd` (die zunaechst angenommene Variante) weicht bereits in der
#   ersten Stunde ab -- das waere die Eichung einer Modellwelt gewesen, die
#   der Produktivcode gar nicht bezieht (derselbe Fehlerklasse, die dieses
#   Issue beheben soll, nur eine Ebene tiefer).
# - `/v1/dwd-icon` liefert IDENTISCH zu `icon_d2` (Muenchen) bzw. `icon_eu`
#   (je nach Gitterlage) -- keine Korrektur noetig.
# - `/v1/ecmwf` liefert IDENTISCH zu `ecmwf_ifs025` -- keine Korrektur
#   noetig. `ecmwf_ifs04` (der REGIONAL_MODELS-`id`) ist als Historical-
#   Forecast-API-Modellname VERALTET und liefert dort durchgaengig `null`;
#   der Tabellenschluessel bleibt trotzdem `ecmwf_ifs04`, weil das der Wert
#   ist, der zur Laufzeit tatsaechlich in `ForecastMeta.model` steht (der
#   REGIONAL_MODELS-`id`, nicht der Archiv-Bezeichner) -- NICHT aufraeumen,
#   sonst bricht der Nachschlag in `model_registry.cape_threshold_jkg()`.
_MODEL_ARCHIVE_ID = {
    "meteofrance_arome": "meteofrance_seamless",
    "icon_d2": "icon_d2",
    "metno_nordic": "metno_nordic",
    "icon_eu": "icon_eu",
    "ecmwf_ifs04": "ecmwf_ifs025",
}

# Gebiet -> Referenzpunkt (lat, lon). Dieselben Gebietsnamen wie
# `thunder_routing._REGIONS`. FR: GR20 Refuge de Petra Piana -- derselbe
# Punkt wie `tests/tdd/test_cape_model_threshold.py::_KORSIKA`.
_REGION_REFERENCE_POINTS = {
    "FR": (42.22, 9.07),
    "DE_ALPEN": (48.14, 11.58),
    "EU_REST": (59.33, 18.06),
}


def _fetch_hourly_cape(archive_model_id: str, lat: float, lon: float) -> list:
    """Ruft die stuendliche CAPE-Reihe fuer eine Konvektionssaison ab.

    Liefert eine leere Liste, wenn die API einen Fehler meldet (Modell
    deckt den Punkt gar nicht ab) -- kein Ausnahme-Durchschlag, das ist
    hier der erwartete "keine Abdeckung"-Fall.
    """
    url = (
        f"{HISTORICAL_API}?latitude={lat}&longitude={lon}"
        f"&start_date={SEASON_START}&end_date={SEASON_END}"
        f"&hourly=cape&models={archive_model_id}&timezone=UTC"
    )
    try:
        with urllib.request.urlopen(url, timeout=60) as resp:
            payload = json.load(resp)
    except (urllib.error.URLError, urllib.error.HTTPError, json.JSONDecodeError):
        # Manche Kombinationen (z. B. metno_nordic ohne CAPE im Archiv)
        # liefern eine kaputte/leere Antwort statt eines sauberen Fehlers --
        # das ist ebenfalls "keine Abdeckung", kein Skript-Fehler.
        return []
    if "error" in payload:
        return []
    values = payload.get("hourly", {}).get("cape", [])
    return [v for v in values if v is not None]


def calibrate() -> dict:
    """Fuehrt die Eichung fuer jede (Modell, Gebiet)-Kombination durch und
    liefert `{(model_id, region): threshold_jkg}`."""
    table: dict = {}
    for model_id, archive_id in _MODEL_ARCHIVE_ID.items():
        for region, (lat, lon) in _REGION_REFERENCE_POINTS.items():
            values = _fetch_hourly_cape(archive_id, lat, lon)
            if not values:
                print(f"  {model_id:20s} x {region:9s} -> keine Abdeckung (0 Werte)")
                continue
            p95 = statistics.quantiles(values, n=100)[94]
            threshold = max(p95, MIN_THRESHOLD_JKG)
            table[(model_id, region)] = round(threshold, 1)
            print(
                f"  {model_id:20s} x {region:9s} -> P95={p95:.1f} "
                f"J/kg -> Schwelle={threshold:.1f} J/kg ({len(values)} Werte)"
            )
    return table


def main() -> None:
    print(f"Eichlauf {SEASON_START}..{SEASON_END} gegen {HISTORICAL_API}\n")
    table = calibrate()
    print("\nCAPE_THRESHOLDS_JKG: dict[tuple[str, str], float] = {")
    for (model_id, region), value in sorted(table.items()):
        print(f'    ("{model_id}", "{region}"): {value},')
    print("}")


if __name__ == "__main__":
    main()
