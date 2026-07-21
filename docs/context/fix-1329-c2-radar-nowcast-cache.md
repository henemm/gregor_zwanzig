# Context: fix-1329-c2-radar-nowcast-cache (Issue #1329, Scheibe C2)

## Request Summary
Nach Auslieferung von C (`31e807e4`, geteilter Forecast-Cache) zeigt die Messung: **555 von 557** fehlgeschlagenen open-meteo-Aufrufen am 2026-07-20 stammen aus `radar_service.get_nowcast()`, nur 2 aus dem Forecast-Pfad. Diese Scheibe zieht den Nowcast-Pfad in dieselbe geteilte Schicht (Cache + Budget/Priorität). PO-Direktive: Tech Lead entscheidet Priorisierung selbst.

## Root Causes (verifiziert)

1. **Kein Cache, kein Throttle im Radar-Pfad.** `radar_service.py` enthält weder Cache-Objekt noch `ForecastBudgetGate`-Import; jeder `get_nowcast()`-Aufruf löst mindestens einen HTTP-Request aus (`_fetch_openmeteo_15` `:317-363`).
2. **Zwei Jobs holen denselben Ort unabhängig.** Trip-Radar (`trip_alert.py:676-677`, ein Call je Trip) und Compare-Radar (`compare_radar_alert.py:130-146`, ein Call je Ort je Preset) laufen über getrennte Endpunkte (`api/routers/scheduler.py:67-84`), jeder baut pro Request einen eigenen `RadarNowcastService` (`trip_alert.py:556-561`, `compare_radar_alert.py:172-176`). Kein gemeinsamer Speicher — derselbe Ort in Trip UND Preset wird doppelt geholt.
3. **NEUER FUND — Doppelverbrauch bei Fehlschlag.** Für Südfrankreich (Beispiel aus dem Prod-Log: 43.118/6.359) greift `_within_arome_france` (`:40-43`) → `_fetch_arome_france_hd` → open-meteo. Schlägt der Call fehl (429), liefert `_fetch_openmeteo_15` `[]` (`:361-363`), die Kette läuft weiter, `_within_icon_d2` ist False (lat < 44.0, `:53`) und landet beim Endfallback `_fetch_openmeteo_minutely15` (`:233-234`) — **derselbe open-meteo-Endpunkt**. Ein 429 erzeugt also zwei fehlgeschlagene Aufrufe statt einem.
4. **Sidecar-Calls:** INCA (`:262`) und DPC (`:291`) rufen für `is_convective` zusätzlich open-meteo — auch außerhalb der reinen open-meteo-Zweige entsteht Verbrauch.
5. **Keine Alternativquelle für Frankreich.** RADOLAN endet bei lat ≥ 47.0 (`:28`), DPC bei lon ≥ 6.5 (`:48`); 43.118/6.359 liegt außerhalb beider. Es existiert keine Météo-France-Anbindung. **Umleiten ist für diese Region keine Option** — der Hebel ist Cache + Drosselung, nicht Quellenwechsel. (Damit ist Punkt 2 meiner Übernahme-Ankündigung beantwortet: verworfen.)

## Cache-Tauglichkeit (entscheidend)
- Quell-Auflösung: RADOLAN 5 Min (`providers/brightsky.py:115`), INCA 15 Min (`geosphere.py:70`), open-meteo `minutely_15` 15 Min (`radar_service.py:329`). Ein TTL ≤ 5 Min liefert daher fast immer denselben Frame — Zwischenspeichern verliert fachlich nichts.
- **ABER:** `NowcastResult.onset_minutes` wird relativ zu `now` berechnet (`_derive_result` `:367`). Ein gecachtes fertiges Ergebnis würde nach 8 Minuten einen um 8 Minuten falschen Onset zeigen. ⇒ Es dürfen **nur die rohen `RadarFrame`-Listen** gecacht werden, die Ableitung läuft je Aufruf neu — exakt die Lehre aus dem F001-Fund in C (`weather_cache.py:39-63`).

## Related Files
| File | Relevance |
|---|---|
| `src/services/radar_service.py:118-132` | `get_nowcast` — Einbaupunkt für Cache + Budget |
| `src/services/radar_service.py:201-234` | Quellenkette/Bounding-Boxen; Ort des Doppelverbrauchs |
| `src/services/radar_service.py:317-363` | `_fetch_openmeteo_15` — alle open-meteo-Zweige laufen hier zusammen |
| `src/services/radar_service.py:367` | `_derive_result` — zeitrelativ, darf NICHT gecacht werden |
| `src/services/segment_weather.py:127-201` | Vorbild für Budget-Anbindung (Cache-Hit → `record_cache_hit`, Miss → `allow(priority)` → `record_call`) |
| `src/services/weather_cache.py:294-305` | Vorbild Singleton + „covers"-Trefferregel + Rohdaten-Caching |
| `src/services/trip_alert.py:556-561,676-677` | Trip-Radar-Aufrufer |
| `src/services/compare_radar_alert.py:130-146,172-176` | Compare-Radar-Aufrufer |
| `src/services/trip_command_processor.py:1109-1111` | `/jetzt`-Befehl — Nutzeraktion, NICHT `polling` |

## Existing Patterns
- Test-Seam ohne Mocks: `RadarNowcastService(frame_source=callable(lat,lon)->list[RadarFrame])` (`radar_service.py:79-81`); echte `RadarFrame`-Objekte statt `patch()`. Bestand: u.a. `test_feature_656_radar_nowcast.py` (8), `test_feature_734_arome_france_nowcast.py` (6), `test_compare_radar_alert.py` (8), `test_issue_827_radar_throttle_recording.py` (2).
- `ForecastBudgetGate.PROVIDER = "openmeteo"` (`forecast_budget.py:26`) — derselbe Tageszähler wie der Forecast-Pfad; Radar zahlt in denselben Topf ein, was fachlich korrekt ist (ein Kontingent).

## Risks & Considerations
- **Alarm-Empfindlichkeit:** Radar-Alarme sind der zeitkritischste Pfad (Gewitter-Anzug). TTL muss deutlich unter dem 15-Minuten-Takt liegen (Vorschlag 300 s) und der Onset MUSS je Aufruf neu gerechnet werden.
- **Priorität:** Scheduler-Radar = `polling` (bei Budget-Druck zuerst drosseln). Der `/jetzt`-Befehl ist eine Nutzeraktion ⇒ `user_briefing`, darf nie gedrosselt werden. Diese Unterscheidung ist der eigentliche Sinn der Klassen aus C.
- **Negativ-Ergebnisse:** Ein Fehlschlag (leere Frames) darf nicht dauerhaft gecacht werden (sonst Alarm-Blindheit), aber der Doppelversuch auf denselben Provider innerhalb eines Aufrufs sollte unterbleiben.
- **Kein Mock-Theater:** Cache-Nachweis über den `frame_source`-Seam mit zählender Callable (Bestandsmuster), nicht über `patch()`.
- Prod ist aktuell degradiert — Lieferung zügig, aber ohne Abkürzung bei Adversary/Staging-Nachweis.
