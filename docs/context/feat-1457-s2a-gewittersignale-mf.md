# Context: feat-1457-s2a-gewittersignale-mf

## Request Summary

Météo-France liefert für Frankreich und Korsika eine **Blitzdichte** und eine
**Hagel-Diagnose**. Beide sollen abgerufen und in neue Felder des gemeinsamen
Datenmodells gelegt werden — **regulär**, nicht nur im Notfall. Erste Scheibe von
S2 aus dem Gewitter-Konzept.

Aufgabenstellung: **#1457**. Konzept und Messwerte: **#1419**.

## Related Files

| Datei | Relevanz |
|---|---|
| `src/app/models.py:96-144` | `ForecastDataPoint` — hier entstehen die neuen Felder |
| `src/providers/meteofrance.py:92-95, 187-245` | Coverage-Konstanten und `_fetch_series`; hier kommen die zwei Größen dazu |
| `src/providers/openmeteo.py:640-680, 1050-1052` | **Vorbild-Muster**: `_fetch_ensemble_spread` + `enrich_ensemble` — genau so wird angereichert |
| `src/providers/region_routing.py:33-46` | Zuständigkeit je Ort — heute **nur Notfallpfad** |
| `src/providers/base.py:41-70` | `fetch_forecast`-Signatur aller Provider (`enrich_*`-Schalter) |

## Existing Patterns

**Anreicherung ist ein etabliertes Muster** (`enrich_ensemble`, `enrich_snow`): Der
Hauptprovider liefert die Grunddaten, ein zusätzlicher Aufruf reichert einzelne Felder
an, **best-effort und fail-soft** — ein Fehler dort darf die Vorhersage nie kippen
(`openmeteo.py:673-680`: jede Ausnahme → `{}`, nie werfen). Genau dieses Muster trägt
auch die Gewittersignale: Open-Meteo bleibt Hauptquelle, die beste Regionalquelle
reichert Gewitter an.

**GRIB2/WCS an einem Punkt lesen:** `meteofrance._read_point_value` (unkomprimiert),
`dwd._read_point_value` (bz2). Ein Request **je Zeitschritt** — die Live-API erlaubt
keinen Multi-Zeitschritt-Request (Modul-Docstring `meteofrance.py`).

**Zeitbudget:** `FETCH_DEADLINE_SECONDS = 180` in `meteofrance.py:85`, vor **jedem**
Request geprüft (`_fetch_series`). #1448-Lehre: Die Grenze muss im innersten Schritt
greifen — hier bereits erfüllt, das Muster ist beim Erweitern beizubehalten.

## 🔴 Risiken und Fallen

1. **Abrufzahl.** `_fetch_series` macht 24 Requests je Größe (`FORECAST_HOURS = 1..25`).
   Heute 4 Größen = ~96 Requests je Ort. Zwei weitere Größen = +48. Das Zeitbudget von
   180 s ist bereits knapp bemessen — **die neuen Größen dürfen es nicht sprengen**,
   sonst fällt die *bestehende* Vorhersage aus. Deshalb Anreicherung mit **eigenem**
   Budget, nicht im selben Topf.
2. **`enrich_*`-Schalter dürfen nicht der Schutz sein.** #1448-Lehre: Wenn ein Parameter
   das Verhalten aktiviert, hängt alles daran, dass jede Aufrufstelle ihn durchreicht.
   Der Default muss die Gewitteranreicherung **einschalten**.
3. **Leer ≠ ungefährlich.** Liefert Météo-France nichts, bleibt das Feld `None` —
   „keine Aussage", nie „kein Gewitter". Harte Vorgabe aus #1419 Abschnitt 5.
4. **Getrennte Felder.** Blitzdichte (MF, Messwert 0,2) und Blitzpotenzial (DWD,
   Messwert 88) sind verschiedene Größen; nie in ein gemeinsames Feld.
5. **Hagel-Einheit ist unbestätigt.** `DIAG_GRELE` lieferte am Messtag 4,9 gegen 0,0.
   Die Bedeutung ist per `DescribeCoverage` zu klären, bevor daraus ein Ja/Nein wird —
   Vorbild: so wurde die Einheit von `LITOTA3` geklärt.
6. **Korsika liegt knapp im FR-Rechteck** (`region_routing.py:36`: bis 9,7 O; Petra
   Piana bei 9,07 O). Das trägt, ist aber eine enge Marge — ein Ort weiter östlich auf
   Korsika fiele heraus. Beim Zuschnitt prüfen.

## Dependencies

- **Upstream:** vorhandener Météo-France-WCS-Zugang, `httpx`, `rasterio`. Keine neue
  Abhängigkeit, kein neuer Vertrag.
- **Downstream:** noch keiner — die Felder werden in S3 gelesen. Bis dahin ändert sich
  **kein** Nutzerverhalten.

## Existing Specs

- `docs/specs/modules/` — Météo-France-Direktprovider stammt aus #1143
- ADR-0041 (Zuständigkeit einer Warn-Quelle nach Endpunkt-Art) — verwandtes Muster für
  die größenabhängige Zuständigkeit, wird in **S2b** relevant

## Abgrenzung

Keine Stufenbildung (S3), keine Ausgabeänderung, kein `merge.py` (S4), kein
Open-Meteo-Abruf (#1329 unberührt), keine Änderung der Zuständigkeit für Temperatur,
Wind und Schnee.
