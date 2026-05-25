# Context: Issue #347 — Berechnung Sonnenstunden

## Request Summary

Die Sonnenstunden-Anzeige ist unplausibel: Bei z. B. 45 % Bewölkung sollte
teilweise die Sonne scheinen, der Wert wirkt aber zu niedrig/falsch. Zusätzlich
gewünscht (User): Die Berechnung soll **konfigurierbar** werden und **konsistent**
in **Ortsvergleich (Compare)** und **Trip-Summary** wirken.

## Root-Cause-Analyse (Kern-Befund)

Die zentrale Funktion `WeatherMetricsService.calculate_sunny_hours()`
(`src/services/weather_metrics.py:245-295`) hat zwei Methoden:

1. **Method 1 (Primary, „most accurate"):** summiert `dp.sunshine_duration_s`
   über alle Stunden (`/3600` → Stunden).
2. **Method 2 (Fallback, NUR bei Höhe ≥ 2500 m):** zählt Stunden binär, in denen
   `effective_cloud < 30 %` ist → +1 volle Stunde, sonst 0.

   `return max(api_hours, spec_hours)`

**Zwei Defekte:**

- **Method 1 ist toter Code.** Das Datenmodell `ForecastDataPoint`
  (`src/app/models.py:84-130`) hat **kein Feld `sunshine_duration_s`**, und
  `src/providers/openmeteo.py` ruft die Open-Meteo-Variable `sunshine_duration`
  **nirgends ab**. Damit ist `hasattr(dp, 'sunshine_duration_s')` immer `False`
  → `api_hours = 0` **konstant**.
- **Method 2 greift nur im Hochgebirge** (≥ 2500 m) und zählt **binär** mit hartem
  30 %-Cutoff.

**Folge:**
- Lagen **unter 2500 m**: Sonnenstunden **immer 0**.
- Lagen **ab 2500 m**: binär — eine Stunde mit 45 % Bewölkung zählt als **0**,
  obwohl real teils Sonne scheint. Genau die vom User beschriebene Unplausibilität.

Das vorhandene Feld `dni_wm2` (Direct Normal Irradiance, W/m²) wird **befüllt**
(`openmeteo.py:675` ← `direct_normal_irradiance`), aber für die Stundenzahl
**nicht** genutzt.

## Zwei verschiedene „Sonnen"-Größen — Konsistenzproblem

| Pfad | Größe | Einheit | Quelle |
|------|-------|---------|--------|
| **Compare** (`comparison_engine.py:141`) | `sunny_hours` (Stundenzahl) | h | `calculate_sunny_hours()` |
| **Trip-Summary** (`trip_report.py:686`) | Metrik `sunshine` = **DNI avg** | W/m² | `metric_catalog.py:269` (`dp_field="dni_wm2"`) |

→ Compare zeigt „Sonnenstunden" (Stunden), die Trip-Summary zeigt unter „Sonnenschein"
einen **DNI-Mittelwert in W/m²** — zwei verschiedene Konzepte/Einheiten unter
ähnlichem Namen. Der User-Wunsch nach Konsistenz zielt hierauf.

## Related Files

| File | Relevance |
|------|-----------|
| `src/services/weather_metrics.py:245-295` | **Kern:** `calculate_sunny_hours()` + Konstanten `HIGH_ELEVATION_THRESHOLD_M=2500`, `SUNNY_HOUR_CLOUD_THRESHOLD_PCT=30` (Z. 208-209) |
| `src/app/models.py:84-130` | `ForecastDataPoint` — kein `sunshine_duration_s`, hat `dni_wm2`, `cloud_total_pct`, cloud layers |
| `src/providers/openmeteo.py:150,290,668-685` | Param-Liste + Feld-Mapping; ruft `sunshine_duration` NICHT ab; befüllt `dni_wm2` |
| `src/providers/geosphere.py:336-392` | Geosphere liefert **kein DNI/sunshine** — nur Cloud-Layer (Open-Meteo-Beimischung) |
| `src/services/comparison_engine.py:140-143` | Compare → `metrics["sunny_hours"]` |
| `src/services/comparison_scoring.py:160-235` | Score-Boni: Sonnenstunden ≥7/≥5/≥3 → +20/+12/+5 (wandern), analog allgemein |
| `src/services/comparison_renderers.py:225-226` | Compare-Tabelle Zeile „Sonnenstunden" |
| `src/formatters/trip_report.py:686-696` | Trip-Summary: Metrik `sunshine` als DNI-W/m²-Wert/Emoji |
| `src/app/metric_catalog.py:268-276` | Metrik-Def `sunshine` = DNI (W/m²), `default_aggregations=("avg",)` |
| `src/output/renderers/email/helpers.py:404` | E-Mail-Rendering key `sunshine` |
| `src/output/renderers/channel_layout.py:35` | Spalten-Priorität `sunshine: 25` |

## API-Best-Practices (Internet-Recherche)

**Open-Meteo `sunshine_duration` (offizielle Definition):**
- **WMO-Standard:** Sonnenschein = Direct Normal Irradiance (DNI) **> 120 W/m²**.
- Open-Meteo nutzt **lineare Interpolation über 60–180 W/m²** statt hartem Cutoff
  bei 120 → realistischer für stundengemittelte Daten (eine Stunde kann 0,5 h
  Sonne liefern).
- **Einheit: Sekunden** (verfügbar als **hourly** Variable = Sekunden pro Stunde,
  und als **daily** Summe).
- Berechnung ist **unabhängig von cloud_cover** — basiert auf modellierter
  Direktstrahlung. (Bekannte Modellschwäche: gelegentlich „100 % Wolken + viel
  Sonne", da Strahlungs-Bias des Wettermodells, nicht der Methode.)

**Sonnenstunden aus Bewölkung ableiten (für Provider ohne DNI, z. B. Geosphere):**
- Treiber ist die **totale Bewölkung zwischen Sonnenauf-/-untergang**, mit
  **zeitlicher Auflösung** (stündlich), nicht Tagesmittel.
- Etablierte empirische Ansätze: **Ångström-Methode**, lineare/nichtlineare
  Cloud-Index-Modelle (Sonnenanteil ≈ 1 − f(cloud)). Typische Standardfehler
  0,2–0,84 h. → **lineare/proportionale** Ableitung statt binärem Cutoff.

**Konsequenz für die Lösung (Vorschau, gehört in Phase 2/3):**
- **Open-Meteo:** entweder `sunshine_duration` (Sekunden/h) abrufen **oder** aus
  bereits vorhandenem `dni_wm2` ableiten (lineare Interpolation 60–180 W/m²,
  WMO-konform) — letzteres ohne neuen API-Call.
- **Geosphere/ohne DNI:** proportionale Cloud-Ableitung statt binär (45 % Wolken
  → ~0,55 h statt 0).
- **Konfigurierbar:** DNI-Schwelle/Interpolationsband, Cloud-Methode,
  Höhen-Schwelle als Settings statt hartcodierter Klassen-Konstanten.

## Existing Patterns

- Schwellwerte heute als **Klassen-Konstanten** in `WeatherMetricsService`
  (`HIGH_ELEVATION_THRESHOLD_M`, `SUNNY_HOUR_CLOUD_THRESHOLD_PCT`,
  DNI-Schwellen in `weather_metrics.py:26-35`).
- `calculate_effective_cloud()` mischt in großer Höhe nur mid+high Clouds
  (ignoriert tiefe Wolken) — dasselbe Höhenkonzept würde die neue Berechnung erben.
- Provider-Capability-Flags im `metric_catalog` (`providers={"openmeteo":True,
  "geosphere":False}`) — Muster für „DNI nur bei Open-Meteo".

## Dependencies

- **Upstream:** `ForecastDataPoint` (`dni_wm2`, `cloud_*`), Open-Meteo-Provider,
  Geosphere-Provider, `calculate_effective_cloud()`.
- **Downstream:** Compare-Engine/-Scoring/-Renderer (Ortsvergleich), Trip-Report-
  Formatter (Summary), E-Mail-Renderer, Channel-Layout.

## Existing Specs

- `docs/specs/modules/weather_metrics.md` — referenziert von `calculate_sunny_hours`
  (Verhalten/Schwellwerte hier dokumentiert; muss mit Fix aktualisiert werden).
- `docs/specs/data_sources.md` — Governance erlaubter Open-Meteo-Parameter
  (`sunshine_duration` müsste ggf. aufgenommen werden, falls neuer Abruf).
- `weather_emoji_dni.md` — DNI-basierte Emoji-Logik (verwandt, nicht zu brechen).

## Risks & Considerations

- **Daten-Governance (#338):** Jeder neue Open-Meteo-Parameter ist ein zusätzlicher
  API-Abruf und muss in `data_sources.md` freigegeben + im Call-Log gezählt werden.
  Die DNI-Ableitung vermeidet das (DNI wird bereits geholt).
- **Provider-Asymmetrie:** Geosphere hat kein DNI → braucht zwingend den
  Cloud-Pfad; Methode muss pro Provider sauber wählen.
- **Höhenlogik beibehalten:** „über den tiefen Wolken" (≥ 2500 m) darf nicht
  bestraft werden — der vorhandene `effective_cloud`-Ansatz sollte erhalten bleiben.
- **Score-Stabilität:** `comparison_scoring.py` hängt an `sunny_hours`-Schwellen
  (≥7/≥5/≥3). Realistischere (höhere, gebrochene) Werte verschieben Compare-Scores
  → bewusst gegenchecken, ggf. Schwellen anpassen.
- **Konsistenz Compare ↔ Summary:** Entscheidung nötig, ob die Trip-Summary künftig
  ebenfalls „Sonnenstunden" (h) statt DNI-Mittel (W/m²) zeigt — sonst bleibt der
  Eindruck zweier widersprüchlicher „Sonnen"-Werte.
- **KEINE Mocks:** Tests müssen gegen echte Provider-Daten/Fixtures laufen
  (Fixture-Provider #263 vorhanden).

---

## Analyse-Ergebnis (Phase 2)

### Gewählter Lösungsansatz

1. **Hauptweg DNI-Ableitung (kein neuer API-Parameter):** `calculate_sunny_hours()`
   nutzt das bereits befüllte `dp.dni_wm2`. Pro Stunde WMO-konform mit linearer
   Interpolation:
   - `dni >= max (Default 180)` → +1,0 h
   - `min <= dni < max` → +(dni − min)/(max − min) h
   - `dni < min (Default 60)` oder None → +0
2. **Notweg proportionaler Cloud-Fallback** (nur wenn kein DNI verfügbar, z. B.
   Geosphere): `(100 − effective_cloud)/100` h pro Stunde — **kein** binärer
   30 %-Schnitt mehr. `calculate_effective_cloud()` (Höhenlogik „über tiefen
   Wolken") bleibt unverändert.
3. **Rückgabe als Float** (gerundet, 1 Dezimalstelle) statt Int. Anzeige-Stellen
   auf `int()`-Casts prüfen (`comparison_renderers.py:226`).
4. **Konfigurierbar via `src/app/config.py`** (Pydantic `Settings`, GZ_-Prefix —
   NICHT config.ini): neue Felder `sunny_dni_min_wm2=60`, `sunny_dni_max_wm2=180`,
   `sunny_cloud_threshold_pct=30`. `calculate_sunny_hours(data, elevation_m=None,
   settings=None)`; ohne Settings = Defaults. Bestehende Klassen-Konstanten bleiben
   (von compare.py referenziert), werden nur per Settings-Injection ergänzt.
5. **`max(api_hours, spec_hours)`-Hack entfällt** — war nur Workaround für den
   toten Method-1-Pfad.

### Produkt-Entscheidung (User, 2026-05-24)

**Trip-Summary zeigt künftig ebenfalls Sonnenstunden (h)** statt DNI-Mittelwert
(W/m²) — einheitlich mit dem Ortsvergleich (gewählte Option B). Umsetzung:
`metric_catalog.py` Metrik-Definition + `trip_report.py:686-696` Rendering auf
`sunny_hours`-Float. DNI-W/m² bleibt intern als Hilfsgröße (Emoji-Logik) erhalten.

### Scope

| Datei | Änderung | ~LoC |
|-------|----------|------|
| `src/services/weather_metrics.py` | `calculate_sunny_hours` neu (DNI + proportional), Signatur | ~30 |
| `src/app/config.py` | 3 Settings-Felder | ~10 |
| `src/services/comparison_engine.py` | `settings` an 2 Aufrufstellen (Z. 141, 429) | ~5 |
| `tests/unit/test_weather_metrics_legacy.py` | bestehende 0-h-Erwartung anpassen + neue Tests | ~40 |
| `src/app/metric_catalog.py` | `sunshine`-Metrik auf Sonnenstunden | ~15 |
| `src/formatters/trip_report.py` | Rendering `sunny_hours` (h) | ~15 |

**6 Dateien, ~115 LoC — unter dem 250-LoC-Limit.**

### Risiken

- **Score-Drift im Ortsvergleich (hoch):** `comparison_scoring.py`-Schwellen
  (≥7/≥5/≥3 h → Punkte) wurden mit de-facto-0-Werten kalibriert. Echte Werte
  verschieben Scores/Rankings → Schwellen im selben Schritt auf Plausibilität
  prüfen, Verhaltensänderung kommunizieren.
- **Provider-Asymmetrie:** Open-Meteo (DNI-Methode) vs. Geosphere (Cloud-Methode)
  liefern bei gleicher Lage leicht unterschiedliche Werte. Kein Blocker; ggf. später
  im Rendering transparent machen.
- **Float statt Int:** Anzeige-/Format-Stellen auf harte `int`-Annahmen prüfen.
- **Daten-Governance #338:** kein neuer Open-Meteo-Parameter → unkritisch.
