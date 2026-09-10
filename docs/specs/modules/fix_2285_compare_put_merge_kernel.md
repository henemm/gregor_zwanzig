---
entity_id: fix_2285_compare_put_merge_kernel
type: refactor
created: 2026-09-10
updated: 2026-09-10
status: draft
version: "1.0"
tags: [compare, trips, go-api, persistence]
---

# Ein Merge-Kernel für beide Vergleichs-PUT-Wege (Issue #2285, Dach-Epic #1374)

## Approval

- [ ] Approved

## Purpose

Die beiden Vergleichs-Schreibwege (`PUT /api/compare/presets/{id}` und
`PUT /api/briefings/{id}?kind=vergleich`) haben heute zwei unabhängige
Merge-Implementierungen: der Compare-PUT dekodiert in das volle
`model.ComparePreset` und rettet danach ~20 Felder einzeln zurück (jedes neue
Struct-Feld ist ein Datenverlust-Kandidat der GR221-Klasse, #102), der
Briefing-PUT nutzt bereits einen generischen JSON-Overlay-Merge, dupliziert
aber die Server-Feld-Restauration und die Legacy-Sentinels separat. Zusätzlich
liefert der `route`-Zweig von `GetBriefingHandler` weder Sperre noch ETag,
anders als sein `vergleich`-Geschwister und `GetTripHandler`. Diese Scheibe
zieht **eine** Funktion `applyComparePresetPatch`, auf die beide Compare-PUT-
Wege delegieren, entfernt damit den doppelten Schwellen-Merge und macht den
`route`-GET-Zweig symmetrisch zum Rest des Systems.

## Source

- **File:** `internal/handler/compare_preset.go`, `internal/handler/briefing_subscription.go`
- **Identifier:** `applyComparePresetPatch` (neu), `UpdateComparePresetHandler`,
  `UpdateBriefingHandler`, `GetBriefingHandler`

Betroffene Schicht: ausschließlich **Go-API** (`internal/handler/`). Kein
Python-Code, kein Frontend-Code in dieser Scheibe (siehe Known Limitations).

## Affected Files

| File | Change Type | Description |
|------|-------------|--------------|
| `internal/handler/compare_preset.go` | MODIFY | Neue Funktion `applyComparePresetPatch`; `UpdateComparePresetHandler` liest den Body per `io.ReadAll` und delegiert, der Feldrettungs-Block (~Zeilen 330–505) entfällt |
| `internal/handler/briefing_subscription.go` | MODIFY | `UpdateBriefingHandler` vergleich-Zweig ruft `applyComparePresetPatch` statt des eigenen Merge-/Restaurations-Blocks; `GetBriefingHandler` route-Zweig bekommt Sperre + ETag |
| `internal/handler/put_partial_body_preserves_all_fields_test.go` | CREATE | AC-1: reflektionsbasierter Roundtrip für alle vier PUT-Wege |
| `internal/handler/compare_preset_put_server_fields_test.go` | CREATE | AC-3, AC-7: Fälschungsschutz + Mandantentrennung auf beiden Compare-PUT-Wegen |
| `internal/handler/briefing_route_get_lock_etag_test.go` | CREATE | AC-4: ETag-Parität `GET /api/briefings?kind=route` vs. `GET /api/trips` |
| `internal/handler/alert_channel_thresholds_merge_location_test.go` | CREATE | AC-5: doc-compliance-Test, zählt Treffer des Schwellen-Feld-Merges im handler-Paket |

## Estimated Scope

- **LoC:** Produktivcode netto negativ (~−150: Feldrettung entfällt, neue Kernel-Funktion + Restauration/Sentinels ist deutlich kürzer), Tests ~+250
- **Files:** ~6 (2 geändert, 4 neu)
- **Effort:** medium

Wegen der Testmenge (Reflection-Roundtrip, Server-Feld-Fälschungsschutz,
ETag-Parität, doc-compliance-Zähler) ist `loc_limit_override 500`
wahrscheinlich nötig.

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `mergeBriefingPatch` (`briefing_subscription.go:168`) | function | JSON-Overlay-Merge, Basis des Kernels — bleibt unverändert, wird jetzt von beiden Wegen genutzt |
| `mergeConfigMap` (`config_merge.go`) | function | nested-Merge-Baustein innerhalb `mergeBriefingPatch` (#1159) |
| `store.MaterializePausedAt`, `store.NormalizeComparePreset`, `store.ClampComparePresetDayWindow` | function | Normalisierungskette nach dem Merge, unverändert aufgerufen |
| `validateComparePreset` (`compare_preset.go`) | function | Validierung bleibt im jeweiligen Handler, NICHT im Kernel |
| `ifMatchAllows`, `setETagHeader`, `writePreconditionFailed`, `bailIf` (`etag.go`, `briefing_subscription.go`) | function | Sperre/ETag-Infrastruktur, unverändert |
| `store.LockBriefing`, `store.BriefingFingerprint` | method | Sperre je Nutzer+ID, SHA256-Fingerabdruck — im route-Zweig neu genutzt |

## Implementation Details

### 1. Neue Funktion `applyComparePresetPatch`

Signatur in `compare_preset.go`:

```go
func applyComparePresetPatch(original model.ComparePreset, id string, patch []byte, now time.Time) (model.ComparePreset, error)
```

Ablauf:

1. `merged, err := mergeBriefingPatch(original, patch)` — der bestehende
   JSON-Overlay-Merge aus `briefing_subscription.go:168` (Top-Level-Felder
   überschreiben, fehlende bleiben erhalten; ist ein Feld auf beiden Seiten
   ein JSON-Objekt, wird es per `mergeConfigMap` eine Ebene tiefer gemergt —
   das deckt `display_config`, `official_warnings` und
   `alert_channel_thresholds` strukturell gleich ab, ohne Feld-Enumeration).
   Fehler wird durchgereicht (der Aufrufer meldet `bad_request`).
2. `json.Unmarshal(merged, &p)` in ein frisches `model.ComparePreset`. Fehler
   wird durchgereicht.
3. Server-verwaltete Felder aus `original` restaurieren — UNBEDINGT, ein vom
   Client mitgesendeter Wert wird ignoriert (Fälschungsschutz, AC-3):
   ```go
   p.ID = id
   p.UserID = original.UserID
   p.CreatedAt = original.CreatedAt
   p.LetzterVersand = original.LetzterVersand
   p.TopOrtLetzterVersand = original.TopOrtLetzterVersand
   p.PausedAt = original.PausedAt
   p.ArchivedAt = original.ArchivedAt
   p.Kind = original.Kind
   ```
   Das ist eine Angleichung: `UpdateComparePresetHandler` schützt heute weder
   `ArchivedAt` noch `Kind` (nur der Briefing-PUT schützt `ArchivedAt`) — nach
   dieser Scheibe schützen beide Wege denselben Achter-Feldsatz. Archivieren
   bleibt ausschließlich über den State-Endpoint möglich (wie beim Trip).
4. Legacy-Sentinels, in dieser Reihenfolge (unverändert zur heutigen Compare-
   PUT-Semantik, jetzt an einer Stelle statt zweimal):
   - `p.PreviousSchedule == ""` → `p.PreviousSchedule = original.PreviousSchedule`
     (#631 — Feld fehlte im Body).
   - `p.ForecastHours == 0` → `p.ForecastHours = original.ForecastHours`;
     danach, falls immer noch `0` (auch das Original hatte nie einen
     Horizont, Legacy-Daten) → `p.ForecastHours = 48` (#764/#781).
   - `p.Schedule == "weekly" && p.Weekday == nil` → `p.Weekday = &four` mit
     `four := 4` (#511 F001).
   - `p.EndDate != nil && *p.EndDate == ""` → `p.EndDate = nil` (#1232
     Scheibe 2b, expliziter Lösch-Sentinel — MUSS NACH der Server-Feld-
     Restauration stehen, sonst würde ein leerer String fälschlich als
     „Feld fehlte" behandelt).
5. `store.MaterializePausedAt(&p, now)` — materialisiert `PausedAt` bei
   erstmaligem Pausieren (`schedule=="manual"`).
6. `store.NormalizeComparePreset(&p)` — einzige Normalisierungsquelle
   (Corridors/LocationIDs/Empfänger), muss nach dem Merge laufen.
7. `store.ClampComparePresetDayWindow(&p)` — klemmt ein ungültiges
   Tagesfenster-Paar, muss nach dem Merge laufen (ein bewusst gesendetes
   ungültiges Paar wird geprüft, nicht der erhaltene Alt-Wert).
8. `return p, nil`.

Validierung (`validateComparePreset`) bleibt **außerhalb** des Kernels, im
jeweiligen Handler — die Fehlerantwort (`validation_error` + `detail`) ist
Handler-Zuständigkeit, nicht Merge-Zuständigkeit.

### 2. `UpdateComparePresetHandler` (compare_preset.go)

Body wird per `io.ReadAll(r.Body)` gelesen (statt `json.NewDecoder(...).Decode`
direkt ins Struct). Der komplette Feldrettungs-Block (aktuell ca. Zeilen
330–505: Preserve-Zeilen für `DisplayConfig`, `PreviousSchedule`,
`OfficialAlertsEnabled`, `RadarAlertEnabled`, `HourlyEnabled`,
`OutlookEnabled`, `DayWindowStartHour/EndHour`, `AlertCooldownMinutes`,
`AlertQuietFrom/To`, `OfficialAlertTriggersEnabled`, `OfficialWarnings` (+
Sources-Feld-Merge), `SendTelegram/Sms/PremiumSms`,
`AlertChannelThresholds` (+ 4 Kanal-Feld-Merges), `ForecastHours`,
`Weekday`-Default, die 5 Slot-Felder, `Corridors`, `PausedAt`, `EndDate`-
Sentinel, `NormalizeComparePreset`, `ClampComparePresetDayWindow`) fällt komplett
weg und wird durch einen Aufruf ersetzt:

```go
updated, err := applyComparePresetPatch(original, id, bodyBytes, time.Now().UTC())
if err != nil {
    writeJSON(w, http.StatusBadRequest, map[string]string{"error": "bad_request"})
    return
}
```

Unverändert bleiben: Segment-Prüfung, `LockBriefing`-Sperre, Fingerabdruck vor
dem Schreiben, If-Match-Vorbedingung VOR dem Body-Verarbeiten (die Reihenfolge
„erst If-Match prüfen, dann Body verarbeiten" bleibt erhalten — sie steht
schon vor der Body-Verarbeitung im Code und wird nicht verschoben),
`validateComparePreset`, `s.SaveComparePreset`, neuer ETag.

### 3. `UpdateBriefingHandler` vergleich-Zweig (briefing_subscription.go)

Der Block ab `merged, err := mergeBriefingPatch(original, patch)` bis vor
`validateComparePreset` (aktuell Zeilen 255–278) wird ersetzt durch:

```go
preset, err := applyComparePresetPatch(original, id, patch, time.Now().UTC())
if bailIf(w, err != nil, http.StatusBadRequest, "bad_request") {
    return
}
```

Damit bekommt dieser Weg zusätzlich zur bisherigen Server-Feld-Restauration
(die schon `ArchivedAt` schützte) auch `Kind`-Schutz, die
`PreviousSchedule`-, `ForecastHours`- und `Weekday`-Sentinels sowie
`ClampComparePresetDayWindow` — die bisher NUR im Handarbeits-Compare-PUT
liefen, im Briefing-PUT-Weg aber fehlten (ein PUT mit `schedule:"weekly"`
ohne `weekday` über `/api/briefings/{id}?kind=vergleich` bekam bisher KEINEN
Default — das wird mit dieser Scheibe angeglichen).

### 4. `GetBriefingHandler` route-Zweig (briefing_subscription.go)

Der route-Zweig (aktuell Zeilen 63–74) bekommt Sperre und ETag symmetrisch
zum vergleich-Zweig darunter und zu `GetTripHandler` (`trip.go:60-65`):

```go
if kind == briefingKindRoute {
    defer s.LockBriefing(id)()
    trip, err := s.LoadTrip(id)
    if bailIf(w, err != nil, http.StatusInternalServerError, "store_error") {
        return
    }
    if bailIf(w, trip == nil, http.StatusNotFound, "not_found") {
        return
    }
    trip.Kind = briefingKindRoute
    fp, fpErr := s.BriefingFingerprint(id)
    setETagHeader(w, fp, fpErr)
    writeJSON(w, http.StatusOK, trip)
    return
}
```

Die Sperre steht VOR `LoadTrip` (gleiche Reihenfolge wie beim vergleich-Zweig
und bei `GetTripHandler`: „Sperre auch beim Lesen — sonst könnte ein
gleichzeitiger PUT zwischen Fingerabdruck und Serialisierung
dazwischenfunken"). Kein Selbst-Blockierer: dieser Zweig lädt selbst über
`s.LoadTrip` und delegiert NICHT an `GetTripHandler` — anders als
`UpdateBriefingHandler`, wo der route-PUT-Zweig an `UpdateTripHandler`
delegiert und deshalb bewusst KEINE eigene Sperre nimmt (Kommentar
`briefing_subscription.go:207-211` bleibt unverändert gültig, betrifft nur
PUT).

### 5. Schwellen-Merge nur noch einmal

Mit (1)–(3) verschwindet die Compare-eigene Ausschreibung des Vier-Kanal-
Feld-Merges für `AlertChannelThresholds` (Email/Telegram/Sms/PremiumSms)
vollständig aus `internal/handler/*.go` mit Ausnahme von `trip.go:405-437`
(Trip-Pointer-DTO, Punkt 6). Der Vergleich deckt das Sub-Objekt jetzt generisch
über `mergeConfigMap` innerhalb von `mergeBriefingPatch` ab — kein
Feld-Enumerations-Code mehr nötig.

### 6. Trip-PUT bleibt unverändert

`UpdateTripHandler` (`trip.go`) wird in dieser Scheibe NICHT angefasst
(Tech-Lead-Entscheidung 2, `docs/context/fix-2285-put-merge.md`). Der
Pointer-DTO ist bereits strukturell preserve-by-default; ein Umbau wäre
Refactor ohne Nutzerwert bei hohem Regressionsrisiko am meistgenutzten
Schreibpfad. Die Angleichung erfolgt stattdessen über AC-1 (gemeinsamer
Reflection-Test über Trip UND Vergleich).

### 7. Explizit außerhalb dieser Scheibe

Kein Frontend-Code, kein Python-Code, keine Migration. Issue-Punkt 4
(Pause-Dual-Write) → Known Limitations, eigene Folge-Scheibe.

## Expected Behavior

- **Input:** Teil-JSON-Body an einem der vier PUT-Endpunkte
  (`PUT /api/compare/presets/{id}`, `PUT /api/briefings/{id}?kind=vergleich`,
  `PUT /api/trips/{id}`, `PUT /api/briefings/{id}?kind=route`).
- **Output:** Gespeicherte Ressource mit den im Body enthaltenen Feldern
  geändert, allen anderen Feldern unverändert aus dem Bestand, Server-Feldern
  unabhängig vom Body-Inhalt aus dem Bestand, neuer `ETag`-Header.
- **Side effects:** Datei unter `data/users/<user_id>/briefings/<id>.json`
  (Vergleich) bzw. dem Trip-Pendant wird per-Datei überschrieben; bei
  fehlgeschlagener If-Match-Vorbedingung KEINE Schreibung (412, Datei
  unverändert).

## Acceptance Criteria

- **AC-1:** Given ein gespeicherter Vergleich UND ein gespeicherter Trip, bei denen per Reflection jedes Struct-Feld mit einem Nicht-Null-Wert belegt ist / When ein PUT nur `{"name":"neu"}` schickt (Compare-PUT, Briefing-PUT vergleich, Trip-PUT, Briefing-PUT route) / Then trägt die gespeicherte Datei alle anderen Felder unverändert (JSON-Vergleich der Datei vor/nach, nur `name` darf abweichen).
  - Test: `internal/handler/put_partial_body_preserves_all_fields_test.go` — `reflect` füllt jedes exportierte Feld beider Structs (`model.ComparePreset`, `model.Trip`) mit einem synthetischen Nicht-Null-Wert (Strings/Ints/Bools/Pointer/Slices je Kind), speichert, sendet den minimalen PUT über den echten HTTP-Router, lädt danach neu und vergleicht per `reflect.DeepEqual` (mit `name`/`Name` ausgenommen) gegen den Ausgangszustand. Deckt automatisch jedes künftige Feld ab, ohne den Test anzufassen — das ist das „synthetische Zukunftsfeld".

- **AC-2:** Given ein Vergleich mit gesetztem `alert_channel_thresholds` (alle vier Kanäle) und `official_warnings.sources` / When ein PUT nur `{"alert_channel_thresholds":{"email":"HIGH"}}` bzw. `{"official_warnings":{"enabled":false}}` schickt / Then bleiben die anderen drei Kanäle bzw. `sources` erhalten (Sub-Objekt-Merge über den Kernel, nicht über ausgeschriebene Rettungszeilen).
  - Test: bestehende `compare_preset_alert_channel_thresholds_test.go` und `compare_preset_official_warnings_test.go` bleiben grün und beweisen dies weiterhin end-to-end über beide PUT-Wege (Weg 1 + Weg 2 sind in beiden Dateien bereits als Testpaare angelegt).

- **AC-3:** Given ein Vergleich / When ein PUT `paused_at`, `archived_at`, `created_at`, `user_id`, `kind:"route"` im Body mitschickt / Then bleiben alle acht Server-Felder wie im Bestand (Fälschungsschutz, beide Compare-PUT-Wege).
  - Test: `internal/handler/compare_preset_put_server_fields_test.go` — legt einen Vergleich mit bekannten Werten in allen acht Feldern an, sendet über `comparePresetEtagRouter` UND `briefingVergleichEtagRouter` je einen PUT, dessen Body explizit gefälschte Werte für `id`, `user_id`, `created_at`, `letzter_versand`, `top_ort_letzter_versand`, `paused_at`, `archived_at`, `kind` enthält, lädt danach neu und prüft, dass alle acht Felder dem Bestand entsprechen (nicht dem gefälschten Body-Wert).

- **AC-4:** Given ein Trip / When `GET /api/briefings/{id}?kind=route` / Then trägt die Antwort einen `ETag`, der identisch zum `ETag` von `GET /api/trips/{id}` ist, und ein `PUT /api/briefings/{id}?kind=route` mit `If-Match: <dieser ETag>` liefert 200, mit einem falschen ETag 412.
  - Test: `internal/handler/briefing_route_get_lock_etag_test.go` — echter Trip im TempDir-Store, `GET /api/trips/{id}` und `GET /api/briefings/{id}?kind=route` über echte Router, `mustETag` auf beiden Antworten vergleichen (identisch, weil `BriefingFingerprint` kind-neutral ist), danach `PUT /api/briefings/{id}?kind=route` einmal mit korrektem und einmal mit `"falsch"` als If-Match — 200 bzw. 412.

- **AC-5:** Given der Code nach dem Umbau / When `git grep -c "AlertChannelThresholds\.\(Email\|Telegram\|Sms\|PremiumSms\) == nil" internal/handler/*.go` (Nicht-Test-Dateien) / Then genau eine Datei mit Treffern (`trip.go`).
  - Test: `internal/handler/alert_channel_thresholds_merge_location_test.go` (`# doc-compliance-test` — hier ist die Struktur selbst die Zusicherung) — liest per `os.ReadDir`/`filepath.Glob` alle `internal/handler/*.go`-Dateien OHNE `_test.go`-Suffix, zählt je Datei die Vorkommen des Musters `AlertChannelThresholds.<Kanal> == nil` per Regex und erwartet, dass ausschließlich `trip.go` Treffer hat, `compare_preset.go` und `briefing_subscription.go` null Treffer.

- **AC-6:** Given die Bestands-Sentinels / When ein PUT `end_date:""`, `forecast_hours` fehlend, `previous_schedule` fehlend, `schedule:"weekly"` ohne weekday schickt / Then: `end_date` gelöscht, `forecast_hours` = Bestand (bzw. 48 falls auch Bestand 0 war), `previous_schedule` = Bestand, `weekday` = 4 (Regressionsschutz).
  - Test: bestehende `compare_preset_prev_schedule_test.go`, `compare_preset_511_test.go`, `compare_preset_slot_schedule_test.go` bleiben ohne Änderung grün (laufen unverändert gegen `UpdateComparePresetHandler`, jetzt intern über `applyComparePresetPatch`).

- **AC-7:** Given zwei Nutzer A und B mit je einem Vergleich gleicher ID / When A per PUT ändert / Then ist Bs Datei byte-identisch wie vorher (Mandantentrennung, CLAUDE.md-Pflicht).
  - Test: `internal/handler/compare_preset_put_server_fields_test.go` (zweiter Testfall in derselben Datei) — zwei `store.Store`-Instanzen mit `WithUser("usera")`/`WithUser("userb")`, je ein Vergleich mit identischer ID gespeichert, PUT nur für Nutzer A über den Router (User aus Auth-Kontext wie in `doReq(..., user)`), danach Bs Datei per `os.ReadFile` vor/nach dem PUT byte-identisch vergleichen.

## Mutations-Gegenprobe

| Verfälschung | Fängt es ein Test? |
|---|---|
| (a) Restauration von `ArchivedAt` (oder `Kind`) in `applyComparePresetPatch` entfernen | AC-3 wird rot (`compare_preset_put_server_fields_test.go`) — der gefälschte Body-Wert landet in der gespeicherten Datei. |
| (b) `defer s.LockBriefing(id)()` im route-Zweig von `GetBriefingHandler` entfernen | **Nicht mutationsfest per HTTP-Test.** Ein einzelner sequentieller Request beweist die Sperre nicht — es bräuchte einen nebenläufigen Test analog `TestDeleteComparePresetHandler_WaitsForBriefingLock_NoIfMatchCheck` (`compare_preset_etag_ifmatch_test.go:317`): Sperre in einer Goroutine über `s.LockBriefing(id)()` von außen halten, `GET /api/briefings/{id}?kind=route` in einer zweiten Goroutine mit Timeout starten und beweisen, dass der GET blockiert statt sofort zurückzukommen. Wird in dieser Scheibe **nicht** als eigener Test aufgenommen (Aufwand/Nutzen bei einem reinen Lese-Pfad ohne Schreibkonflikt-Risiko gering) — hier bewusst als nicht durch AC-4 gedeckte Zusicherung ausgewiesen, damit der Adversary sie nicht als übersehenes Loch meldet.
| (c) `setETagHeader` im route-Zweig entfernen | AC-4 wird rot — `mustETag` schlägt fehl (kein `ETag`-Header). |
| (d) in `applyComparePresetPatch` den nested-Merge (`mergeBriefingPatch`) durch ein blindes `json.Unmarshal(patch, &p)` direkt auf `original` ohne Overlay ersetzen (Blind-Replace) | AC-2 wird rot — die drei nicht mitgesendeten Kanäle in `alert_channel_thresholds` bzw. `sources` gehen verloren. |
| (e) ein Struct-Feld-Restore in Schritt 3 der Kernel-Funktion weglassen (z.B. `p.PausedAt = original.PausedAt` streichen) | AC-1 UND AC-3 werden rot — AC-1 über das Reflection-Struct (jedes Feld ist belegt, die fehlende Restaurierung zeigt sich als Abweichung von JEDEM Feld, nicht nur `PausedAt`), AC-3 gezielt über den expliziten Fälschungsversuch auf `paused_at`. |
| (f) die `EndDate`-Sentinel-Prüfung vor statt nach der Server-Feld-Restauration einordnen | AC-6 wird rot (`compare_preset_prev_schedule_test.go`/vergleichbare Slot-Tests) — betrifft zwar nicht direkt `EndDate` als Server-Feld, aber die Reihenfolge-Doku in Schritt 4 der Implementation Details ist die geprüfte Zusicherung von AC-6 in Kombination mit den Bestandstests, die die Sentinel-Reihenfolge (Preserve vor Lösch-Sentinel) voraussetzen. |

## Known Limitations

- **Explizites `null` im Body = Löschen** (Overlay-Semantik, seit #1250
  Scheibe 6 AC-22 am Briefing-PUT-Weg etabliert) vs. **Pointer-DTO beim Trip**
  (explizites `null` = „unverändert", weil `*T`-Felder bei `null` genauso wie
  bei fehlendem Key zu `nil` decodieren). Dieser Unterschied bleibt bestehen
  und wird durch diese Scheibe auf den zweiten Compare-PUT-Weg vereinheitlicht
  (beide Compare-Wege nutzen jetzt denselben Kernel, also dieselbe
  `null`-Semantik) — kein bekannter Frontend-Aufrufer sendet explizite
  `null`-Werte für Preserve-Felder, daher kein beobachtbares Risiko.
- **Pause-Dual-Write (Issue-Punkt 4 aus #2285):** `paused_at` wird weiterhin
  aus `schedule=="manual"` abgeleitet (`MaterializePausedAt`), nicht
  umgekehrt als alleinige Quelle geführt. Ein Schema-Rework mit Migration und
  Frontend-Berührung (`tripStatus.ts`, `subscriptionHelpers.ts`) — eigene
  Folge-Scheibe.
- **Trip-PUT bleibt Pointer-DTO**, keine strukturelle Angleichung an den
  Vergleich-Merge-Kernel in dieser Scheibe (Tech-Lead-Entscheidung 2).
- **Lock-Nebenläufigkeit im `route`-GET-Zweig** ist nach dieser Scheibe
  vorhanden, aber nicht durch einen eigenen nebenläufigen Test belegt (siehe
  Mutations-Gegenprobe (b)) — Symmetrie zum vergleich-Zweig ist der
  Rechtfertigungsgrund, kein direkter Beweis der Race-Freiheit.

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** keine (kein neues ADR nötig — reiner Implementierungs-Merge
  innerhalb einer bereits durch ADR-0023 beschlossenen Modellgrenze:
  kind-diskriminiertes Briefing-Modell über bestehende Stores, keine neue
  Persistenzform).
- **Rationale:** Diese Scheibe verschiebt keine Entscheidungsfläche (Kanäle,
  Provider, Datenmodell, Auth, Editor-Paradigma, Test-/Deploy-Strategie) —
  sie konsolidiert Merge-Logik nach demselben Muster wie `mergeConfigMap`
  (#1159, ADR-frei) und referenziert Issue #1159 als Präzedenzfall für
  „geteilter Merge-Kernel statt sechsfach wiederholter Blind-Replace-Klasse".

## Changelog

- 2026-09-10: Initial spec created
