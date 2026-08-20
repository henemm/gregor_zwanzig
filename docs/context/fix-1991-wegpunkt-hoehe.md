# Context: fix-1991-wegpunkt-hoehe

**Issue:** #1991 — Wegpunkt-Höhe wird an keinen Wetter-Provider übergeben (Audit-Befund B-01)
**Track:** Full Process · **Phase:** 1 (Context)
**PO-Entscheid 2026-08-20:** Option A — Höhe wird als `elevation=` an die Provider-API durchgereicht
(API-seitiges Downscaling, keine eigene Physik), **ohne** Transparenzhinweis im Briefing.

## Request Summary

Die Geländehöhe eines Wegpunkts wird bis an die Providergrenze mitgeführt, dort aber beim Bau der
HTTP-Anfrage verworfen. Open-Meteo rechnet deshalb mit der Höhe seiner eigenen, geglätteten
Geländekarte statt mit der echten Wegpunkt-Höhe. Der Fehler geht dadurch in **beide** Richtungen:
Gipfel werden abgetragen (Prognose zu warm), Talpunkte und Hütten aufgefüllt (Prognose zu kalt) —
siehe Messreihe im Analyse-Teil. Der Fix reicht die Höhe an alle Provider durch, die sie
annehmen können.

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
   Nullgradgrenze Δ 600/400/200 m (entspannt/standard/sensibel). **Durch die Messung überholt:**
   die tatsächlichen Sprünge reichen bis 6,2 °C (Temperatur) und 460 m (Nullgradgrenze) und
   reißen damit auch die Standardschwellen — nicht nur die sensiblen. Der gefährdetere
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

---

# Analysis (Phase 2)

## Type

**Bug** — mit Anteilen einer Grundsatzentscheidung (Höhen-Soll war nie festgelegt), daher zusätzlich ein ADR.

## Messung vor der Spec (2026-08-20, echte API, echte Wegpunkte)

| Punkt | echte Höhe | Höhe im Modell | ΔT max | ΔT min |
|---|---|---|---|---|
| Dresdner Hütte (Stubai) | 2302 m | 3078 m | **+6,2 °C** | +5,8 °C |
| Obstanserseehütte (KHW) | 2304 m | 1794 m | −4,8 °C | −3,3 °C |
| Schaufelspitze (Stubai) | 3333 m | 2925 m | −3,5 °C | −2,8 °C |
| Sillianer Hütte (KHW) | 2447 m | 2028 m | −2,6 °C | −1,9 °C |
| Bocca di Foggiale (GR20) | 1962 m | 1716 m | −1,6 °C | −1,6 °C |
| Refuge de Tighjettu (GR20) | 1683 m | 1411 m | −0,4 °C | +0,1 °C |

**Der Fehler geht in beide Richtungen.** Die Höhenkarte, auf die Open-Meteo ohne `elevation`
zurückfällt, glättet das Gelände: Gipfel werden abgetragen (Prognose zu warm), Talpunkte
aufgefüllt (Prognose zu kalt). Die Formulierung „systematisch zu warm" im Issue beschreibt nur
den Gipfelfall. Die **größte** gemessene Abweichung trifft eine Hütte, und zwar nach unten
(6,2 °C zu kalt an der Dresdner Hütte; mit drei Koordinaten im Umkreis gegengeprüft, also kein
Koordinatenfehler der Beispieldatei).

**Betroffen ist mehr als die Temperatur** (stundenscharfer Vergleich, 48 h):

| Größe | Schaufelspitze | Obstanserseehütte | Bocca di Foggiale |
|---|---|---|---|
| Nullgradgrenze, Bandbreite der Änderung | −260 … +150 m | **−460 … +10 m** | 0 m |
| Stunden mit veränderter Nullgradgrenze | 47/48 | 40/48 | 0/48 |
| Niederschlag, größte Änderung | 2,40 mm | 1,00 mm | 0,00 mm |
| Stunden mit verändertem Wettercode | 11/48 | 7/48 | 0/48 |

Achtung, Messfalle: Ein Vergleich der *Tagesmaxima* zeigt für die Nullgradgrenze nur 0–90 m und
suggeriert Entwarnung. Erst der **stundenweise** Vergleich zeigt Verschiebungen bis 460 m — mehr
als die Standard-Alarmschwelle von 400 m. Der Alpenraum ist durchgehend betroffen, Korsika (GR20)
in dieser Probe gar nicht.

Alle drei produktiv genutzten Modell-Endpunkte (`dwd-icon`, `meteofrance`, `ecmwf`) nehmen
`elevation` an und melden die verwendete Höhe zurück.

## Affected Files

| Datei | Änderung | Beschreibung |
|---|---|---|
| `src/providers/openmeteo.py` | MODIFY | Ein gemeinsamer Params-Erbauer `_punkt_params(location, **rest)`; 4 Baustellen (`:973`, `:1175`, `:724`, `:807`) darauf umstellen; `_fetch_uv_data` von `lat, lon` auf `location` heben |
| `src/app/models.py` | MODIFY | `ForecastMeta.model_elevation_m` — die von der API gemeldete Höhe als Wirksamkeitsnachweis |
| `src/providers/geosphere.py` | MODIFY | `_fetch_openmeteo_clouds` (`:508`) — Höhe in den hartkodierten Open-Meteo-URL |
| `src/services/weather_cache.py` | MODIFY | Höhe in `_bucket_key` (`:226`) |
| `src/services/point_weather.py` | MODIFY | `LocationWeatherSource.fetch` — Höhe im Protokoll |
| `src/services/compare_location_weather_source.py` | MODIFY | `:150` — Höhe nicht mehr auf `None` setzen |
| `src/services/compare_alert.py`, `src/services/scheduler_dispatch_service.py` | MODIFY | Höhe aus `SavedLocation` durchreichen |
| `src/services/segment_weather.py` | MODIFY | Diagnosezeile „angefordert/gemeldet" im bestehenden Debug-Kanal |
| `src/services/radar_service.py` | MODIFY | Nowcast-Kette (`get_nowcast` + 6 interne Methoden + `:458`) — Scheibe S3 |
| `docs/specs/data_sources.md` | MODIFY | Antrag #4: `elevation` auf die Positivliste |
| `docs/adr/0058-*.md` | CREATE | Höhen-Soll als Grundsatzentscheidung |
| `docs/reference/decision_matrix.md` | MODIFY | Provider-Asymmetrie vermerken |
| Tests | CREATE | MockTransport-Request-Test, AST-Aufrufstellen-Wächter, Cache-Bucket, Compare-Höhe, Doc-Compliance |

## Scope Assessment

- Produktiv: ~90–110 LoC über 9 Dateien (S3 eingerechnet) — **unter** dem Limit von 250
- Tests: ~280 LoC — unter dem eigenen Testbudget von 500
- `docs/`/`*.md` zählen nicht mit
- Risiko: **MEDIUM** — kleiner Eingriff, große Reichweite (jeder Wert in jedem Kanal)

## Technische Entscheidungen

**E1 — Wo durchreichen.** Ein gemeinsamer Params-Erbauer in `openmeteo.py`, **nicht** in
`_request()`: `_request` (`:598`) kennt die `Location` gar nicht und deckt nur 4 von 6
Baustellen ab — ein Engpass, der sich als einer anfühlt, aber leckt. Abgesichert wird die
Vollständigkeit stattdessen durch einen **AST-Wächter** nach dem Hausmuster
`tests/test_onset_callsite_timezone_guard.py`: kein Dict-Literal in `src/`/`api/` darf
`"latitude"` tragen, ohne über den Erbauer zu laufen oder namentlich mit Begründung in der
Ausnahmeliste zu stehen. Das ist die einzige Bauform, die den **sechsten** Aufrufer fängt, den
noch niemand geschrieben hat — der fünfte (`radar_service.py:458`) existiert bereits.

**E2 — Provider ohne Höhenannahme.** Nichts tun, Asymmetrie dokumentieren. DWD-GRIB2 und DWD-EU
liefern im Regelbetrieb gar keine Temperatur, sondern Gewittersignale; GeoSphere liefert Schnee
und CAPE. Der Alpen-Normalfall ist Open-Meteo/ICON-D2 — also genau der Pfad, der die Höhe kann.
Die Asymmetrie greift praktisch nur beim Totalausfall aller Open-Meteo-Kandidaten, und dort gilt
ADR-0018 („Fallback ohne Kaschieren") bereits mit ausgewiesenem `fallback_reason`. Eine eigene
Höhenphysik ist durch den PO-Entscheid ausgeschlossen.

**E3 — Cache und Ortsvergleich zusammen.** Beides, nicht eines: Der Bucket-Key
(`weather_cache.py:226`) trennt die Kollision nur, er repariert den Ortsvergleich nicht. Heute
teilen sich Trip-Pfad (mit Höhe) und Compare-Pfad (Höhe hart auf `None`) denselben Cache-Eintrag
am selben Punkt — wer zuerst fragt, entscheidet für die TTL-Dauer, was der andere sieht. Nicht
deterministisch, kein Test fängt das. Die Höhe ist an beiden Stellen verfügbar
(`GPXPoint.elevation_m`, `SavedLocation.elevation_m` ist sogar Pflichtfeld).

**E4 — Anker beim Deploy NICHT löschen.** Ohne Anker liefert `trip_alert.py:720-723` keinen
Vergleichspunkt und damit **gar keinen** Abweichungsalarm — bis zum nächsten Briefing-Versand,
also bei laufender Tour bis zu ~12 h blinde Wache, plus eine Ablehnungsmeldung je Tour und Lauf.
Dem steht ein einmaliger Fehlalarm gegenüber, den das Melde-Gedächtnis
(`deviation_alert_engine.py:234`) auf einmal je Metrik und Segment begrenzt. Die Projektregel
„ausbleibender Alarm ist der gefährlichere Fehler" entscheidet das. Der Sprung ist nach der
Messung allerdings **größer als zunächst angenommen**: die Nullgradgrenze verschiebt sich bis
460 m und reißt damit auch die Standardschwelle (400 m). Es wird also beim Umschalten sichtbar
Alarme geben — einmalig, und das gehört so in den Deploy-Text, damit der erste Rückfrage-Fall
nicht als Regression gelesen wird.

**E5 — Wirksamkeit nachweisbar machen.** Open-Meteo meldet die verwendete Höhe in jeder Antwort
zurück; heute liest das niemand. Minimal erfassen: `ForecastMeta.model_elevation_m` (wird
nirgends serialisiert, also kein Snapshot-Formatbruch) plus eine Zeile im bestehenden
Debug-Kanal von `segment_weather.py`. **Nicht** ins `enrichment_health`-Journal — das hat ein
geschlossenes Vokabular und würde Go-Aggregator und API-Vertrag nachziehen.

**E6 — Nowcast-Pfad als eigene Scheibe S3.** `radar_service.py` führt nur `lat`/`lon` durch acht
Signaturen; die Höhe fehlt dort komplett. Das Issue verlangt `elevation` in **allen**
Open-Meteo-Requests, und die Messung zeigt, dass Niederschlag (bis 2,4 mm) und Wettercode
(11 von 48 Stunden) tatsächlich reagieren — bei einem Kurzfristhinweis entscheidet das über
„Regen" oder „Schnee". Daher enthalten, aber als klar abgegrenzte dritte Scheibe, damit S1/S2
unabhängig liefern können. Der Nowcast-Cache (`radar_cache.py:72`) braucht dann dieselbe
Key-Erweiterung wie der Wetter-Cache.

## Umsetzungsreihenfolge

1. Governance zuerst: Antrag #4 in `data_sources.md` + Doc-Compliance-Test — sonst sendet der
   erste GREEN-Commit einen Parameter, der nicht auf der Positivliste steht
2. ADR-0058 (Höhen-Soll, Asymmetrie, Verweis auf ADR-0018)
3. **S1 Trip-Pfad:** Params-Erbauer, 4 Baustellen, `geosphere.py`, Meta-Erfassung, AST-Wächter
4. **S2 Ortsvergleich + Cache:** Protokoll-Durchreichung und Bucket-Key gemeinsam
5. **S3 Nowcast:** Höhe durch die `radar_service`-Kette, Cache-Key nachziehen
6. Deploy ohne Anker-Löschung, mit Beobachtung der neuen Diagnosezeile

## Testbauform (kein Netz, kein Mock-Theater)

`httpx.MockTransport` nach dem Vorbild `tests/test_provider_tz_normalization.py:184` — der
Handler bekommt ein echtes `httpx.Request` samt fertig kodierter Query. Vier Behauptungen:
(1) `elevation` steht in der Query, wenn eine Höhe vorliegt; (2) `elevation` ist **abwesend** —
nicht leer — wenn keine vorliegt; (3) auch der Ensemble-Request trägt sie; (4) die gemeldete
Höhe landet in `meta`.

**Pflicht-Mutation:** Den Erbauer-Aufruf in `fetch_forecast` durch das alte Dict-Literal
ersetzen. Die Unit-Tests des Erbauers bleiben dabei grün — nur Behauptung 1 fällt. Genau die
Lücke zwischen „die Funktion kann es" und „die Zusicherung wirkt an der Stelle, wo sie zählt".

## Open Questions

Keine offenen technischen Fragen — E1–E6 sind entschieden. Freigabepflichtig sind allein die ACs.
