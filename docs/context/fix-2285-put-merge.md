# Context: fix-2285-put-merge (Issue #2285, Dach-Epic #1374)

## Request Summary

Die beiden Vergleichs-PUT-Wege (`PUT /api/compare/presets/{id}` und
`PUT /api/briefings/{id}?kind=vergleich`) und der Trip-PUT haben drei
verschiedene Merge-Idiome; der Compare-PUT dekodiert in das volle Struct und
rettet ~20 Felder einzeln zurück (jedes neue Feld = Datenverlust-Kandidat,
GR221-Klasse). Dazu: der Schwellen-Merge ist doppelt ausgeschrieben, und der
`route`-Zweig von `GetBriefingHandler` liefert weder Sperre noch ETag.

## Related Files

| File | Relevance |
|------|-----------|
| `internal/handler/compare_preset.go:280-535` | `UpdateComparePresetHandler` — Voll-Dekodierung + Feldrettung (das Problem) |
| `internal/handler/briefing_subscription.go:160-291` | `mergeBriefingPatch` (JSON-Overlay-Merge, #1250 S6 AC-22) + `UpdateBriefingHandler` vergleich-Zweig (zweiter Compare-PUT-Weg, bereits Overlay-Merge) |
| `internal/handler/briefing_subscription.go:46-96` | `GetBriefingHandler` — route-Zweig ohne `LockBriefing`/ETag, vergleich-Zweig mit |
| `internal/handler/trip.go:55-90, 262-470` | Trip-GET (Sperre+ETag, Vorlage) und Trip-PUT (Pointer-DTO `tripUpdateRequest`, Schwellen-Merge `:423-437`) |
| `internal/handler/config_merge.go` | `mergeConfigMap` — geteilter Map-Merge-Kernel (#1159) |
| `internal/model/compare_preset.go` | ComparePreset-Struct (Server-verwaltete Felder: ID, UserID, CreatedAt, LetzterVersand, TopOrtLetzterVersand, PausedAt, ArchivedAt, Kind) |
| `internal/store/compare_preset.go` | `NormalizeComparePreset`, `MaterializePausedAt`, `ClampComparePresetDayWindow`, `SaveComparePreset` (setzt `Kind="vergleich"` hart) |
| `internal/store/briefing_lock.go`, `briefing_fingerprint.go` | `LockBriefing(id)` (Mutex je Nutzer+ID, nicht wiedereintrittsfähig) und `BriefingFingerprint(id)` (SHA256 der Datei, kind-neutral) |
| `internal/handler/compare_preset_*_test.go` (23 Dateien) | Bestandserwartungen an den Compare-PUT: nil-Preserve je Feld, `end_date:""`-Sentinel, `previous_schedule` "" → Bestand, `forecast_hours` 0 → Bestand/48, weekday-Default |
| `internal/handler/briefing_subscription_vergleich_etag_test.go` | ETag/If-Match-Erwartung am gemeinsamen Endpoint (nur vergleich) |
| `frontend/src/lib/components/compare/compareEditorSave.ts:206` | Voll-Spread-Payload `{ ...original, ... }` — trägt auch `paused_at`/`archived_at`/`created_at`/`kind` aus dem Original mit |
| `src/services/compare_alert_guard.py:39` | `is_silenced`: liest `paused_at` **zuerst**, dann `schedule=="manual"` — AC-4 des Issues ist heute schon erfüllt |

## Existing Patterns

- **Pointer-DTO (Trip):** `tripUpdateRequest` mit `*T` je Feld, `existing` wird
  in place mutiert → strukturell „fehlt im Body = unverändert" für ALLE
  Struct-Felder, auch solche, die das DTO nicht kennt (die bleiben schlicht
  unangetastet).
- **JSON-Overlay-Merge (Briefing-PUT vergleich):** `mergeBriefingPatch` marshallt
  den Bestand, legt den Patch als Map darüber, nested Objekte eine Ebene tief per
  `mergeConfigMap`. Strukturell „fehlt im Body = unverändert" ohne Feldliste;
  Server-verwaltete Felder werden danach aus dem Original restauriert.
- **Voll-Dekodierung + Feldrettung (Compare-PUT):** lose-by-default — jedes Feld
  braucht eine explizite Rettungszeile (20+ Issues als Kommentar-Historie).
- **Sperre + ETag beim GET:** `defer s.LockBriefing(id)()` vor dem Laden,
  `BriefingFingerprint` nach dem Laden, `setETagHeader` (Trip-GET `trip.go:61,85`,
  Compare-GET, Briefing-GET vergleich).

## Dependencies

- Upstream (nutzt unser Code): `store.LoadComparePresets/LoadComparePreset`,
  `store.SaveComparePreset`, `store.NormalizeComparePreset`,
  `store.MaterializePausedAt`, `store.ClampComparePresetDayWindow`,
  `validateComparePreset`, `ifMatchAllows`, `setETagHeader`, `mergeConfigMap`.
- Downstream (nutzt unseren Code): Frontend `compareEditorSave.ts`
  (Voll-Spread-Payload, `feat_1273_s2_*`), Compare-Hub Toggles
  (`list_toggle_read_modify_write`), Staging-E2E `feat-1395-s3-etag-ifmatch`,
  Python-Scheduler liest nur die Datei.

## Existing Specs

- `docs/specs/modules/config_merge_helper.md` (#1159, `mergeConfigMap`)
- `docs/specs/modules/issue_458_compare_preset_backend.md` (Compare-PUT Ursprung)
- `docs/specs/modules/rework_2279_s1_alert_kanal_aufloesung.md` (Vorgänger-Scheibe)
- `docs/context/rework-2279-alert-kanal-aufloesung.md` (Scheibenschnitt S1/S2)
- ADR-0023 (kind-diskriminiertes Briefing-Modell), #1395 (ETag/If-Match)

## Analyse / Tech-Lead-Entscheidungen

1. **Ein Merge-Kernel für beide Compare-PUT-Wege.** `UpdateComparePresetHandler`
   und der vergleich-Zweig von `UpdateBriefingHandler` rufen dieselbe Funktion
   `applyComparePresetPatch(original, id, patch, now)` (Overlay-Merge über
   `mergeBriefingPatch` + Restauration der Server-Felder + Legacy-Sentinels +
   Normalisierung). Die ~170 Zeilen Feldrettung fallen. Das ist strukturell
   preserve-by-default: ein neues Struct-Feld braucht keine Handler-Zeile mehr.
2. **Trip bleibt auf dem Pointer-DTO.** Das DTO ist bereits preserve-by-default
   (mutiert `existing` in place); ein Umbau wäre Refactor ohne Nutzerwert bei
   hohem Regressionsrisiko am meistgenutzten Schreibpfad. Die Angleichung wird
   stattdessen als **eine gemeinsame Zusicherung** getestet: ein reflektionsbasierter
   Roundtrip-Test füllt JEDES Struct-Feld und beweist für Trip UND Vergleich, dass
   ein Teil-PUT nichts davon verliert — ein künftiges Feld ist automatisch mit
   abgedeckt (das „synthetische Zukunftsfeld" aus AC-1).
3. **Schwellen-Merge einmal.** Mit (1) verschwindet die Compare-Kopie; die
   Trip-Kopie bleibt als einzige Stelle (Overlay-Merge deckt Sub-Objekte beim
   Vergleich generisch ab).
4. **GET route symmetrisch:** `defer s.LockBriefing(id)()` + ETag im route-Zweig
   (kein Selbst-Blockierer: der route-Zweig lädt selbst, delegiert nicht).
5. **Scope-Schnitt:** Punkt 4 des Issues (Pause-Dual-Write auf `paused_at`
   zurückführen, Store-Normalisierungs-Asymmetrie) ist ein Schema-Rework mit
   Migration und Frontend-Berührung (`tripStatus.ts`, `subscriptionHelpers.ts`,
   20+ Tests) — eigene Folge-Scheibe. AC-4 (Guard erkennt `paused_at` allein)
   ist heute erfüllt und wird als Regressionstest mitgenommen.

## Risks & Considerations

- **Semantik-Delta explizites `null`:** Pointer-DTO behandelt `"x":null` wie
  „fehlt" (nil → unverändert); Overlay-Merge behandelt `"x":null` als Löschen.
  Frontend sendet keine expliziten nulls für Preserve-Felder; Bestandstests
  prüfen „Feld fehlt", nicht „Feld null". Briefing-PUT hat diese Semantik seit
  #1250 S6 — sie wird zur gemeinsamen.
- **Server-verwaltete Felder** nach dem Overlay-Merge restaurieren:
  `ID, UserID, CreatedAt, LetzterVersand, TopOrtLetzterVersand, PausedAt,
  ArchivedAt, Kind`. Heute schützt der Compare-PUT `ArchivedAt` und `Kind` NICHT
  (nur der Briefing-PUT `ArchivedAt`) — Angleichung: Archiv nur über den
  State-Endpoint (wie beim Trip).
- **Legacy-Sentinels bleiben:** `end_date:""` löscht; `forecast_hours` 0 → 48;
  `schedule=="weekly"` ohne weekday → 4; `previous_schedule:""` → Bestand
  (Test `compare_preset_prev_schedule_test.go` F001); `MaterializePausedAt`.
- **Baseline-Rot (origin/main, umgebungsbedingt, nicht diese Scheibe):**
  `TestForecastHandler_ValidRequest_Returns200`, `TestResolveHandlerKomootHighlight`
  (Netz), `TestUpdateTripStateHandler_WriteFailureReturnsGenericStoreError`
  (läuft als root). CI-Ampel ist der Maßstab.
- **LoC:** netto negativ erwartet (Löschung Feldrettung), Tests zählen mit —
  Limit 250 im Blick, ggf. `loc_limit_override 500`.
