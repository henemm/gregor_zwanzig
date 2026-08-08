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
Raster. Je Gebiet eine GEORDNETE LISTE fest verdrahteter Referenzpunkte
(Issue #1592 Scheibe C2; vorher genau ein Punkt je Gebiet):
- FR: (1) GR20/Korsika (42.22, 9.07) -- derselbe Punkt wie in der
  Analyse-Messung und in der Orientierungs-Abfrage des Auftrags;
  (2) franzoesische Alpen (45.00, 6.50).
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

Liefert KEIN Punkt der Liste eines Gebiets fuer eine (Modell, Gebiet)-
Kombination Werte (jede Reihe leer bzw. durchgaengig "null"), entsteht KEIN
Tabelleneintrag (Spec Abschnitt 1 Punkt 4) -- kein Fehler, sondern "nicht
abgedeckt".
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

# Mindestzahl stuendlicher Werte, damit ein Referenzpunkt ueberhaupt als
# "abgedeckt" zaehlt (Adversary-Fund Issue #1592 C2: `statistics.quantiles()`
# wirft `StatisticsError`, sobald ein Punkt genau EINEN Nicht-Null-Wert
# liefert -- die alte Pruefung `if not values` deckte nur die leere Liste
# ab). Eine volle Woche Stundenwerte (24 * 7) ist die Untergrenze, ab der
# ein 95. Perzentil ueberhaupt eine Aussage ueber die Verteilung sein kann:
# bei P95 wird statistisch nur jeder zwanzigste Wert erwartet, der ueber der
# Schwelle liegt -- mit weniger als 168 Werten waere das rechnerische P95
# nicht mehr aus Verteilung, sondern aus wenigen Einzelwerten abgeleitet,
# also Rauschen statt Klimatologie. Zu wenige Werte gelten deshalb wie die
# leere Liste als "keine Abdeckung" -- das Skript geht zum naechsten Punkt
# der Liste weiter statt abzustuerzen.
MIN_SAMPLE_SIZE = 24 * 7

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

# Gebiet -> GEORDNETE Liste von Referenzpunkten [(lat, lon), ...].
# Dieselben Gebietsnamen wie `thunder_routing._REGIONS`.
#
# `calibrate()` probiert die Punkte eines Gebiets der Reihe nach; der ERSTE
# Punkt, an dem das Modell tatsaechlich CAPE-Werte liefert, bestimmt die
# Eichung dieser (Modell, Gebiet)-Kombination.
#
# FR, Punkt 1: GR20 Refuge de Petra Piana -- derselbe Punkt wie
# `tests/tdd/test_cape_model_threshold.py::_KORSIKA`. Korsika steht BEWUSST
# zuerst: jedes bisher belegte FR-Modell liefert dort Werte, damit bleiben
# alle in Scheibe B0 erhobenen FR-Schwellen beim Umstieg auf Punktlisten
# unveraendert (Regressionsschutz, Spec C2 AC-2). Wuerde ein anderer Punkt
# zuerst geprueft, verschoeben sich bestehende Werte.
#
# FR, Punkt 2: franzoesische Alpen (45.00, 6.50) -- noetig, weil Korsika
# ausserhalb des ICON-D2-Gitters liegt (dort 0 Werte) und `icon_d2 x FR`
# deshalb in B0 keinen Eintrag bekam, obwohl ICON-D2 in Frankreich real als
# AROME-Fallback zum Zug kommt. Gewaehlt wurden die Alpen und NICHT das
# Rhone-Tal (44.50, 4.80), obwohl beide ICON-D2-Werte liefern: die Alpen
# sind dieselbe Landschaftsart wie der erste FR-Punkt (Gebirge) und passen
# zur Zielgruppe, die im Gebirge unterwegs ist. Das Rhone-Tal wuerde eine
# Flachland-Klimatologie auf Bergetappen anwenden -- derselbe Fehler, den
# Issue #1592 behebt, nur eine Ebene tiefer. Die Punktwahl entscheidet ueber
# die Zahl: Alpen P95=230 -> Schwelle 300.0 (Untergrenze greift),
# Rhone-Tal P95=390 -> Schwelle 390.0.
#
# DE_ALPEN (Muenchen-Raum) und EU_REST (Stockholm) behalten je genau einen
# Punkt -- dort ist keine Eichluecke gemessen worden.
_REGION_REFERENCE_POINTS: dict[str, list[tuple[float, float]]] = {
    "FR": [(42.22, 9.07), (45.00, 6.50)],
    "DE_ALPEN": [(48.14, 11.58)],
    "EU_REST": [(59.33, 18.06)],
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
        for region, points in _REGION_REFERENCE_POINTS.items():
            # Punkte der Reihe nach; der ERSTE mit GENUG Werten eicht die
            # Kombination. Liefert keiner genug Werte -> kein Tabelleneintrag.
            for lat, lon in points:
                values = _fetch_hourly_cape(archive_id, lat, lon)
                if len(values) < MIN_SAMPLE_SIZE:
                    continue
                p95 = statistics.quantiles(values, n=100)[94]
                threshold = max(p95, MIN_THRESHOLD_JKG)
                table[(model_id, region)] = round(threshold, 1)
                print(
                    f"  {model_id:20s} x {region:9s} -> P95={p95:.1f} "
                    f"J/kg -> Schwelle={threshold:.1f} J/kg ({len(values)} "
                    f"Werte, Punkt {lat}/{lon})"
                )
                break
            else:
                print(
                    f"  {model_id:20s} x {region:9s} -> keine Abdeckung "
                    f"(kein Punkt von {len(points)} lieferte mindestens "
                    f"{MIN_SAMPLE_SIZE} Werte)"
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
