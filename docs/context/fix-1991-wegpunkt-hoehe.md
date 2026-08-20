# Context: fix-1991-wegpunkt-hoehe

**Issue:** #1991 — Wegpunkt-Höhe wird an keinen Wetter-Provider übergeben (Audit-Befund B-01)
**Track:** Full Process · **Phase:** 1 (Context)
**PO-Entscheid 2026-08-20:** Option A — Höhe wird als `elevation=` an die Provider-API durchgereicht
(API-seitiges Downscaling, keine eigene Physik), **ohne** Transparenzhinweis im Briefing.

## Request Summary

Die Geländehöhe eines Wegpunkts wird bis an die Providergrenze mitgeführt, dort aber beim Bau der
HTTP-Anfrage verworfen. Open-Meteo rechnet deshalb mit seiner Modellgitter-Höhe statt mit der
echten Wegpunkt-Höhe — Gipfel- und Passprognosen sind systematisch zu warm. Der Fix reicht die
Höhe an alle Provider durch, die sie annehmen können.

## Live-Gegenprobe (2026-08-20, eigenständig reproduziert)

Schaufelspitze 47.0614 N / 11.1211 E, echte Höhe 3333 m, Endpunkt `api.open-meteo.com/v1/dwd-icon`
(dasselbe Modell, das der Produktivpfad für die Alpen wählt):

| Anfrage | zurückgemeldete Modellhöhe | Temperatur 12 UTC |
|---|---|---|
| ohne `elevation` (heutiger Stand) | 2925 m | **9,0 °C** |
| mit `elevation=3333` | 3333 m | **5,8 °C** |

Δ 408 m Höhe ⇒ **3,2 °C** zu warm. Die API beherrscht die Korrektur, wir fordern sie nicht an.

## Related Files

### Der eigentliche Defekt — Request-Bau ohne Höhe

| Datei | Relevanz |
|---|---|
| `src/providers/openmeteo.py:973` | `fetch_forecast` — Hauptvorhersage, baut `params` nur aus `latitude`/`longitude`/`hourly`/`timezone` |
| `src/providers/openmeteo.py:724` | `_fetch_ensemble_spread` — zweiter Open-Meteo-Request (Ensemble) |
| `src/providers/openmeteo.py:1176` | `fb_params` — Fallback-Request beim Metrik-Gap |
| `src/providers/openmeteo.py:598` | `_request()` — gemeinsamer Ausgang aller Open-Meteo-Aufrufe |
| `src/providers/geosphere.py:508` | `_fetch_openmeteo_clouds` — **zweiter, hartkodierter Open-Meteo-URL** außerhalb von `openmeteo.py` |
| `src/providers/openmeteo.py:807` | `_fetch_uv_data` — Air-Quality/CAMS-Endpunkt, kennt **kein** `elevation` |

### Stellen, die die Höhe schon vorher wegwerfen

| Datei | Relevanz |
|---|---|
| `src/services/compare_location_weather_source.py:150` | `GPXPoint(..., elevation_m=None)` hartkodiert — der **Ortsvergleich** verliert die Höhe vor dem Provider |
| `api/routers/forecast.py:51` | `Location(latitude=lat, longitude=lon)` ohne Höhe |
| `src/providers/regional_stubs.py:88` | reicht nur `lat`/`lon` an GeoSphere durch, `location.elevation_m` fällt weg |

### Datenfluss, der bereits funktioniert (kein Umbau nötig)

| Datei | Relevanz |
|---|---|
| `src/app/config.py:82-97` | `Location` — hat **bereits** `elevation_m: Optional[int]` |
| `src/services/trip_forecast.py:142` | befüllt `Location.elevation_m` aus dem Wegpunkt |
| `src/services/segment_weather.py:184`, `src/services/comparison_engine.py:417`, `src/services/trip_report_scheduler.py:2093`, `src/app/config.py:298` | weitere Konstruktionsstellen, alle mit Höhe |
| `src/app/models.py:364/374` | `GPXPoint.elevation_m`, `Waypoint.elevation_m` |
| `src/app/user.py:58` | `SavedLocation.elevation_m` (Pflichtfeld) — auch Orte tragen eine Höhe |
| `internal/model/location.go:10`, `internal/resolver/elevation.go:18` | Go-Seite: Höhe wird beim Anlegen eines Orts via Open-Elevation aufgelöst |

### Nachgelagert

| Datei | Relevanz |
|---|---|
| `src/services/weather_cache.py:226` | `_bucket_key` = `{lat}_{lon}_{model_id}_{ens}_{snow}` — **ohne Höhe** |
| `docs/specs/data_sources.md:104-152` | Positivliste genehmigter Open-Meteo-Parameter — `elevation` fehlt |
| `src/services/weather_snapshot.py:456/460` | `start_elevation_m`/`end_elevation_m` liegen im Anker, dienen aber nur der Geometrie-Rekonstruktion |

## Existing Patterns

- **Governance-Nachtrag als Doc-Compliance-Test:** `docs/specs/data_sources.md` führt genehmigte
  Parameter je Quelle; ein neuer Parameter wird per „Antrag #N" nachgetragen (`:228` für
  `minutely_15`) und mit einem `# doc-compliance-test` abgesichert
  (`tests/tdd/test_starkregen_kurzfristhinweis.py:639`). Für `elevation` ist Antrag #4 fällig.
- **Höhe wird bereits fachlich ausgewertet** — nur lokal: `src/services/weather_metrics.py:258`
  ignoriert ab 2500 m die tiefen Wolken (`HIGH_ELEVATION_THRESHOLD_M`). Das Muster „Höhe
  beeinflusst die Auswertung" ist also etabliert, neu ist nur „Höhe beeinflusst die Abfrage".
- **Fallback ohne Kaschieren** (ADR-0018): unterschiedliche Provider dürfen unterschiedlich gute
  Daten liefern, das wird ausgewiesen statt geglättet.

## Dependencies

**Upstream (woher die Höhe kommt):** GPX-Import → `Waypoint.elevation_m` → `TripSegment` →
`Location.elevation_m`. Für Orte: Go-Resolver über Open-Elevation → `SavedLocation.elevation_m`.

**Downstream (was sich mitverschiebt):**

- `src/app/metric_catalog.py:110-133` — Temperatur-Ampelbänder (Hitze 28/31/34, Kälte 0/−5/−15),
  absolute Schwellen, verschieben sich mit den Werten.
- `src/app/metric_catalog.py:646` — `freezing_level` (ADR-0019), Δ-Schwelle 200 m Default.
- `src/services/corridor_threshold.py:68` — nutzergesetzte **Absolut**-Schwellen (ADR-0040).
- `src/services/weather_metrics.py:1012` — Taupunkt (nur Anzeige, keine Alarmschwelle).
- Alle vier Ausgabekanäle: E-Mail, Telegram, SMS, Premium-SMS zeigen dieselben Werte.

## Existing Specs & ADRs

- **Kein ADR zum Höhen-Soll** — `grep elevation docs/adr/*.md` findet nichts. Der PO-Entscheid vom
  20.08. ist damit die Grundlage für ein **neues ADR**.
- `docs/specs/data_sources.md:104-152` — Quellen-Governance, Positivliste (siehe oben).
- `docs/adr/0029-openmeteo-standard-provider.md` — Open-Meteo als Standardquelle, schweigt zur Höhe.
- `docs/adr/0018-provider-fallback-ohne-kaschieren.md` — relevant für die Provider, die keine Höhe können.
- `docs/adr/0056-rollierender-alarm-anker-statt-briefing-only-snapshot.md` — Anker-Mechanik (siehe Risiken).
- `docs/specs/issue-451-location-datenmodell.md:62` — Herkunft von `SavedLocation.elevation_m`.
- `docs/project/known_issues.md:580-590` — Vorgeschichte: Snapshots verloren schon einmal Koordinaten und Höhe.

## Risks & Considerations

1. **Nicht alle Provider können die Höhe.** Open-Meteo ja (belegt). GeoSphere-Timeseries,
   DWD-GRIB2 (`dwd.py:194`) und DWD-EU (`dwd_eu.py:210`) sind reine Gitterpunkt-Abfragen ohne
   Höhenparameter; MeteoFrance kennt zwar `height(...)` im WCS-Subset, meint damit aber die
   **Modellebene** (2 m/10 m), nicht das Gelände. Nach dem Fix liefert dieselbe Tour je nach
   aktiver Quelle unterschiedlich korrigierte Temperaturen. Das muss die Spec als bewusste,
   dokumentierte Asymmetrie festhalten (ADR-0018), sonst entsteht ein stiller Qualitätssprung
   beim Provider-Wechsel.

2. **Der Cache würde den Fix teilweise unterlaufen.** `weather_cache.py:226` schlüsselt bewusst auf
   den *Ort* (`lat_lon_model_…`), damit zwei Touren am selben Punkt sich einen Eintrag teilen.
   Solange der Ortsvergleichs-Pfad die Höhe wegwirft (`compare_location_weather_source.py:150`)
   und der Trip-Pfad sie mitschickt, teilen sich beide denselben Bucket — wer zuerst kommt,
   bestimmt, ob der andere korrigierte oder unkorrigierte Werte sieht. Zwei Auswege, die sich
   ergänzen: Höhe in den Bucket-Key aufnehmen **und** den Compare-Pfad die Höhe nicht mehr
   verwerfen lassen.

3. **Einmaliger Alarm-Sprung beim Umschalten — begrenzt, aber real.** Der Δ-Vergleich
   (`src/services/weather_change_detection.py:757`, `abs(delta) > threshold`) kann nicht
   unterscheiden zwischen „das Wetter hat sich geändert" und „wir fragen seit heute anders".
   Die Schwellen (`src/services/alert_preset.py:53ff`): Temperatur-Minimum Δ 8/5/3 °C,
   Nullgradgrenze Δ 600/400/200 m (entspannt/standard/sensibel). Ein 3-°C-Sprung bleibt bei
   „standard" **unter** der Temperaturschwelle, bei „sensibel" löst er aus. Der gefährdetere
   Kandidat ist die **Nullgradgrenze**: 200 m sind bei einer höhenkorrigierten
   `freezing_level_height` schnell erreicht. Dämpfer: das Melde-Gedächtnis
   (`deviation_alert_engine.py:234`) unterdrückt Wiederholungen, der Sprung feuert höchstens
   einmal je Metrik und Segment. **Nicht** gedämpft sind die Absolut-Korridore
   (`corridor_threshold.py:68`) — die reagieren sofort und dauerhaft, was allerdings korrekt ist:
   dort ändert sich die Wahrheit, nicht nur die Wahrnehmung.

4. **Kein Weg, alte Anker zu erkennen.** Snapshots (`weather_snapshot.py:80-91`) tragen kein
   Konfigurations-Fingerprint; „dieser Anker entstand vor der Höhenkorrektur" ist nicht
   feststellbar. Ein gezieltes Zurücksetzen ginge heute nur durch Löschen der Dateien unter
   `data/users/<user_id>/weather_snapshots/` bzw. `compare_weather_snapshots/`. Die Spec muss
   entscheiden, ob das Teil des Deploys wird oder ob der einmalige Sprung hingenommen wird.

5. **Die Abweichung ist heute unsichtbar.** Das Response-Feld `elevation` von Open-Meteo wird
   nirgends gelesen. Es gibt also keine Stelle, die Modellgitter-Höhe und Wegpunkt-Höhe kennt —
   weder für die Diagnose vorher noch für den Nachweis, dass die Korrektur greift. Ein
   Mitschreiben der gemeldeten Modellhöhe wäre der prüfbare Beleg dafür, dass die Anfrage wirkt.

6. **Governance-Drift als Nebenbefund.** Der Produktiv-Request sendet heute schon Parameter, die
   in der Positivliste fehlen (`apparent_temperature`, `cape`, `visibility`, `uv_index`,
   `freezing_level_height`, `is_day`, `precipitation_probability`, `direct_normal_irradiance` —
   letzterer bei verwandtem `direct_radiation` sogar als NOT APPROVED geführt). Nicht Teil dieses
   Tickets, gehört als Sammel-Eintrag nach #1199.

7. **Was sich NICHT ändern darf:** Wegpunkte ohne Höhe (`elevation_m is None`) müssen weiterhin
   ohne `elevation`-Parameter abgefragt werden — kein erfundener Wert, kein Absturz. Und die
   Fixtures (`fixtures/openmeteo/*.json`) sind bereits normalisiert und enthalten keine
   Request-URL, sind also vom Zusatzparameter nicht betroffen.
