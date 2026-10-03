# Context: fix-2211-optional-felder-null

## Request Summary
`PUT /api/trips/{id}` kann optionale Felder nie auf „ungesetzt" zurücksetzen: JSON `null` und „Feld fehlt" landen beide als nil-Pointer im DTO und werden gleich behandelt („Bestand behalten"). Staging-Trip behielt `alert_cooldown_minutes=45`, obwohl der Nutzer das Feld geleert hatte. Der RMW-Kontrakt aus #99 (fehlendes Feld = Bestand behalten) muss erhalten bleiben.

## Kernbefund
- Die Spec `docs/specs/bugfix/update_trip_handler_merge.md` (#99) verspricht in „Semantic Rules": *„Field present, value `null` → explicit clear is permitted"*. Mit Go `encoding/json` ist das **nie umgesetzt** — `null` auf einen Pointer ergibt nil = identisch mit „fehlt". Die Spec vermerkt selbst „not actively tested". Der Fix stellt also den dokumentierten Kontrakt her, statt ihn zu ändern.
- Das Frontend leert bereits korrekt mit explizitem `null` (`alarmeDeliveryPayload.ts:104-107`: `alert_cooldown_minutes: x ?? null`, `alert_quiet_from/to: x || null`). Der Fehler sitzt im Go-Handler.

## Related Files
| File | Relevance |
|------|-----------|
| `internal/handler/trip.go:244-286` | `tripUpdateRequest`-DTO (Pointer + omitempty) |
| `internal/handler/trip.go:343-468` | Merge in den Bestand; danach `validateTrip` :474, `SaveTrip` :484 |
| `internal/handler/config_merge.go:11-22` | `mergeConfigMap` (Map-Feld-Merge, löscht nie einen Key) |
| `internal/model/trip.go:114-167` | Modell: `AlertCooldownMinutes *int` :124, `AlertQuietFrom/To *string` :125-126, `OfficialAlertsEnabled *bool` :135, `OfficialAlertTriggersEnabled *bool` :139, `Region string` :129, `Activity string` :128 |
| `frontend/src/lib/components/shared/alarme-tab/alarmeDeliveryPayload.ts:104-107` | sendet `null` beim Leeren |
| `frontend/src/lib/components/alerts-tab/AlertCooldownCard.svelte:16-19`, `AlertQuietHoursCard.svelte:15-21` | UI, die leert (leeres Feld / Toggle aus) |
| `frontend/src/lib/components/trip-detail/TripTabs.svelte:186-191` | Activity: sendet `undefined` (Key fehlt) → auch nicht leerbar |
| `frontend/src/lib/components/shared/tripSpeicherung.ts:65`, `frontend/src/lib/api.ts:198` | PUT-Weg mit If-Match |
| `frontend/src/lib/__tests__/fakeTripServer.ts` | Fake ersetzt Rumpf komplett, bildet Go-Merge NICHT nach → Bug in Frontend-Tests unsichtbar |
| `src/app/loader.py:1817-1822, 1708-1712, 1983, 135-147` | Python `_trip_to_dict` lässt None-Felder weg → `_deep_merge_preserve_unknown` behält Plattenwert (gleiche Nicht-Leeren-Semantik, Python-intern) |
| `src/services/trip_alert.py:1539/1564/1882`, `radar_alert_service.py:24` | Leser: None → Default |

## Feld-Klassen im DTO
- **Skalar-Optionals (betroffen):** `alert_cooldown_minutes`, `alert_quiet_from`, `alert_quiet_to`, `official_alerts_enabled`, `official_alert_triggers_enabled`; `region`/`activity` (Modell `string`, `""` leert heute schon, `null` nicht).
- **Listen (ganz ersetzt):** `stages`, `avalanche_regions`, `alert_rules`, `corridors`.
- **Maps (Feld-Merge via `mergeConfigMap`):** `aggregation`, `weather_config`, `display_config`, `report_config`, `alert_metric_channels`.
- **Structs mit innerem Feld-Merge:** `official_warnings`, `alert_channels`, `alert_channel_thresholds`.
- `name`: Pflicht, `""` → 400.

## Existing Patterns (null vs. absent)
- `map[string]json.RawMessage` + `if raw, ok := patch[key]; ok` → Unmarshal → `null` = nil = leeren: `UpdateGroupHandler` (`group.go:121-158`), `PatchLocationHandler` (`location.go:212-224`).
- Compare-PUT `mergeBriefingPatch` (`briefing_subscription.go:174-197`): Overlay-Map, Top-Level-`null` leert bereits.
- Kein eigener Nullable-Typ im Code.

## Dependencies
- Upstream: `encoding/json`, `validateTrip`, Store `SaveTrip`, ETag/If-Match (`trip_etag_ifmatch_test.go`).
- Downstream: Alarm-Logik (Python liest None → Default 120 bzw. keine Ruhezeit), Frontend-Editoren (Alarme-Tab, TripTabs, Header, Etappen, Korridore).

## Existing Tests
- `internal/handler/trip_write_test.go:125-366` (Update/Preserves/Merges/NameOnly), `fix_go_rmw_merge_1082_1103_test.go`, `trip_etag_ifmatch_test.go`, `trip_region_test.go`, `trip_response_null_fields_test.go`, `config_merge_structure_test.go`, diverse `trip_official_*`/`trip_alert_*`/`trip_corridors_write`-Tests.
- **Kein** Test für `alert_cooldown_minutes`/`alert_quiet_*` am PUT, **keiner** für „null leert".

## Existing Specs
- `docs/specs/bugfix/update_trip_handler_merge.md` (#99) — RMW-Kontrakt, verspricht null-leert.

## Risks & Considerations
- **Kern-Risiko Datenverlust (#99/#102):** Leeren darf NUR bei explizit gesendetem `null` greifen, nie bei fehlendem Key. Jede Lösung braucht Tests in beide Richtungen (null leert / fehlt behält).
- Semantik von `null` auf Listen/Maps/Structs entscheiden: Listen-`null` heute = behalten; ein „null leert alle Etappen" wäre gefährlich (`stages` null ⇒ Datenverlust). Vermutlich Scope auf Skalar-Optionals begrenzen, Rest explizit unverändert lassen.
- Andere PUT-Aufrufer schicken evtl. unbeabsichtigt `null` (z. B. `x ?? null` in Payload-Buildern anderer Tabs) — vor Umstellung alle Trip-PUT-Payloads auf `null`-Werte prüfen, sonst wird aus „kann nicht leeren" ein „leert versehentlich".
- Activity: Frontend sendet `undefined` statt `null` → zusätzlich Frontend-Fix nötig, falls im Scope.
- Python-Pfad (`_trip_to_dict` lässt None weg) hat dieselbe Semantik, ist aber ein interner Schreiber (Scheduler-Nachträge), kein Nutzer-Leeren — Scope-Frage für die Analyse.
- `fakeTripServer.ts` bildet den Go-Merge nicht nach — Nachweis muss im Go-Handler-Test und auf Staging erfolgen.
- Gleiches Muster in `UpdateProfileHandler`, `PatchMetricPresetHandler`, Compare-Frontend (`compareEditorSave.ts` lässt `undefined` weg) — Nebenbefunde, nicht Scope.

## Analysis

### Type
Bug (nutzersichtbar: geleerte Alarm-Pause/Ruhezeit bleibt gespeichert)

### Aufrufer-Audit (Explore-Agent + Gegenprobe)
- Einziger Trip-PUT-Aufrufer, der diese Felder als `null` sendet: Alarme-Reiter (`alarmeDeliveryPayload.ts:105-107`).
- **Befund des Explore-Agenten „AlarmeTab leert nach Umstellung unbeabsichtigt" ist VERWORFEN.** Gegenprobe: Der Trip-Zweig füttert den Builder ausschließlich aus dem Routen-Zustand (`AlarmeTab.svelte:381-383`), und der wird aus dem gespeicherten Trip initialisiert (`:343-345`). Nutzer-Eingaben schreiben im Trip-Zweig genau diesen Zustand (`handle*Change`, `:349-367`, kein `onCooldownChange` im Trip-Kontext). `null` geht also nur raus, wenn das Feld schon leer ist oder der Nutzer es geleert hat. Das ist kein Datenverlust, sondern genau die gewünschte Semantik.
- Der vorgeschlagene „Fix" (conditional spread, `undefined` weglassen) würde das Leeren **dauerhaft unmöglich** machen ⇒ **nicht übernehmen**.
- Die Props `cooldownMinutes/quietFrom/quietTo` (`:435`) gehören zum **Vergleich-Zweig** (`alarmeVergleichSpeicherung.ts`, Compare-Endpunkt), nicht zum Trip-PUT.
- Weitere Decoder in `trip.go` (`tripStateRequest` :549, `confirmWaypointRequest` :625) schreiben diese Felder nicht.
- Übrige Trip-PUT-Aufrufer (TripTabs, TripHeader, WeatherMetricsTab, CorridorEditor, Etappen, BriefingScheduleTab, Python-Test 674) senden kein `null` für die 7 Felder. GET lässt leere Felder weg (`omitempty`), es gibt kein „GET-Objekt mit null zurückschicken".

### Affected Files (with changes)
| File | Change Type | Description |
|------|-------------|-------------|
| `internal/handler/optional_field.go` (Name offen) | CREATE | Generischer Drei-Zustands-Typ (fehlt / null / Wert) als **Wert**-Feld mit `UnmarshalJSON` |
| `internal/handler/trip.go` | MODIFY | 7 DTO-Felder auf den Typ umstellen; Merge :388-412: fehlt → behalten, null → leeren (Pointer nil bzw. `""`), Wert → setzen |
| `internal/handler/trip_optional_clear_test.go` (verhaltensbenannt) | CREATE | Matrix je Feld: null leert / fehlt behält / Wert setzt, plus Wächter `stages: null` behält, `name: null` behält |
| bestehende Tests mit `tripUpdateRequest{` | ggf. MODIFY | grep ergab keine Literal-Konstruktionen ⇒ voraussichtlich keine |
| `docs/specs/bugfix/update_trip_handler_merge.md` | MODIFY | „not actively tested" ⇒ Verweis auf neue Tests, Geltungsbereich (nur Skalar-Optionals) |

### Scope Assessment
- Files: 2–3 Code + 1 Test + Doku
- Estimated LoC: +60/-15 (Code), Tests ~+150
- Risk Level: MEDIUM. Der PUT-Handler ist der zentrale Trip-Schreibweg. Fehler in Richtung „fehlt = leeren" wären Datenverlust (#99/#102), deshalb Matrix-Tests in beide Richtungen.

### Technical Approach (Empfehlung)
1. Generischer Typ, z. B. `optionalField[T]{ Set, Null bool; Value T }` als Nicht-Pointer-Feld. `encoding/json` ruft `UnmarshalJSON` auch bei `null` auf, wenn das Feld ein Wert-Typ mit Unmarshaler ist. Fehlt der Key, gibt es keinen Aufruf ⇒ `Set=false`. **Erster RED-Test auf Decode-Ebene belegt diese Annahme.** Bewährtes Go-Muster (vgl. `sql.Null*`, guregu/null). Gleichwertige Alternative wäre ein Presence-Scan per `map[string]json.RawMessage` wie in `group.go`/`location.go`, aber der Typ ist lokaler und typsicher.
2. Nur die 7 Skalar-Optionals: `alert_cooldown_minutes`, `alert_quiet_from`, `alert_quiet_to`, `official_alerts_enabled`, `official_alert_triggers_enabled`, `region`, `activity`. Für `region`/`activity` gilt `null` ⇒ `""` (wie heute `""`). `validateTrip` lehnt leeres `activity` nicht ab (grep ohne Treffer).
3. **Ausdrücklich unverändert:** `name` (Pflicht), Listen (`stages`, `avalanche_regions`, `alert_rules`, `corridors`), Maps, Structs. Dort heißt `null` weiter „behalten". Wächter-Tests sichern das.
4. Frontend Trip: keine Änderung nötig, sendet schon `null`. Activity sendet `undefined`, das Frontend kann Activity also nicht leeren. Aktuell gibt es keine UI „Activity leeren", deshalb nicht im Scope.
5. Nachweis: Go-Handler-Tests (Kern) + Staging (Cooldown setzen → leeren → GET zeigt Feld nicht mehr). `fakeTripServer.ts` bildet den Go-Merge nicht nach, ein Frontend-Test beweist hier nichts.

### Nutzersichtbare Wirkung (für die deutschen ACs)
- Alarm-Pause (Cooldown) leeren ⇒ **Standardwert greift** (Python liest None als 120 Min). Das heißt **nicht** „keine Pause".
- Ruhezeit von/bis leeren ⇒ **keine Ruhezeit** mehr.
- Amtliche Warnungen/Trigger `null` ⇒ Systemstandard.

### Dependencies
- `encoding/json`, `validateTrip`, `SaveTrip`, ETag/If-Match unverändert.
- Python-Leser (`trip_alert.py`, `radar_alert_service.py`) behandeln None bereits als Default. Keine Änderung.

### Parität Ortsvergleich (Entscheidung nötig)
- Der Compare-Alarm-Speicherweg (`alarmeVergleichSpeicherung.ts` → `buildComparePresetSavePayload`; vgl. `compareEditorSave.ts:233-236`) **lässt `undefined` weg**. Der Server (`mergeBriefingPatch`) würde `null` leeren, bekommt aber keins. Vermutlich kann also auch der Ortsvergleich Cooldown/Ruhezeit nicht leeren (gleiches Nutzersymptom, Kriterium a).
- **Empfehlung:** Ins selbe Ticket aufnehmen, als Teil B. Begründung: gleiche Nutzerfrage, Trip/Vergleich-Parität ist PO-Vorgabe, und Epics werden themenweise abgeschlossen. Fix: Frontend sendet beim Leeren `null` statt das Feld wegzulassen. In `/30` zuerst per Test/Staging belegen, dass der Defekt besteht.

### Nebenbefunde (nicht Scope)
- Gleiches Muster in `UpdateProfileHandler`, `PatchMetricPresetHandler` ⇒ #1199-Zeile, falls nutzersichtbar ungeklärt.
- Python `_trip_to_dict` lässt None weg. Das betrifft interne Schreiber, ist kein Nutzer-Leeren.

### Open Questions
- [ ] Teil B (Ortsvergleich) im Scope? Empfehlung: ja, nach Nachweis des Defekts in `/30`.
- [ ] Hinweis: Die Plan/Sonnet-Bewertung aus Skill-Schritt 3 wurde nicht als eigener Agent gefahren. Die Bewertung oben stammt aus dem Hauptkontext plus Advisor-Review.

## Erkenntnisse aus Phase 5 (TDD RED, 2026-10-03) — für /50-implement

- **Compare-Bug sitzt anders als in der Spec-Analyse vermutet:** Der Key fehlt im heutigen Payload NICHT — der Bestandswert (45 / 22:00) wird über den `...original`-Spread in `buildComparePresetSavePayload` zurückgeschickt und von `waehleEigenfelder` übernommen. Fix-Stelle: `buildComparePresetSavePayload` (Overlay bei `edits.alertCooldownMinutes === undefined` und vorhandenem Bestandswert ⇒ `null`), nicht nur `alarmSnapshotAus`.
- Echter Testweg Frontend: `alarmSnapshotAus` → `flushPendingAlarmSave` → `baueAlarmNutzlast` → `buildComparePresetSavePayload` → `waehleEigenfelder` (`compareAlarmLeerenNull.test.ts`). Fixture-Preset castet `alert_cooldown_minutes`/`alert_quiet_*` per `as ComparePreset` — svelte-check prüfen, ob die Felder im Typ fehlen.
- **Go-Typ-Vertrag:** `Optional[T]` in `internal/handler/optional_field.go`, Wert-Typ mit Feldern `Set bool`, `Null bool`, `Value T` (Test `optional_field_test.go`). Bis die Datei existiert, kompiliert das ganze Paket `internal/handler` nicht — zuerst anlegen.
- `go` liegt nicht im PATH: `/usr/local/go/bin/go test ./internal/handler/ -run 'TestTripOptional|TestComparePresetOptional|TestOptional' -v`.
- Trip-PUT braucht kein If-Match. Router für Briefing-Delegation: `briefingVergleichEtagRouter(s)` (`briefing_subscription_vergleich_etag_test.go:20`).
- Erwartet grün schon in RED (Wächter): AbsentKeepsAll, ValueSetsAll, NullOnStagesAndNameKeepsExisting, ComparePresetOptionalClear_* sowie Frontend AC-5/AC-13.
