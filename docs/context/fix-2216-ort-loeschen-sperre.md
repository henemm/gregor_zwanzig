# Context: fix-2216-ort-loeschen-sperre

## Request Summary
Issue #2216 (Milestone „Going Live: externe Nutzer", Epic #2345): Ein Ort, der in einem Ortsvergleich
(`ComparePreset.LocationIDs`) steckt, lässt sich ohne Warnung löschen. Der Versand scheitert danach erst
später. Geplante Lösung: Löschen wird mit 409 abgelehnt und nennt die nutzenden Ortsvergleiche; das Frontend
zeigt die Namen; der Versand bei verwaistem Preset meldet einen sprechenden Grund.

## Related Files
| File | Relevance |
|------|-----------|
| internal/router/router.go:231 | Route `DELETE /api/locations/{id}` |
| internal/handler/location.go:276-297 | `DeleteLocationHandler`: WithUser, `rejectInvalidEntityID`, `LockLocation` (Z.284), `DeleteLocation`; jeder Fehler wird 500 `store_error`. Die 409-Prüfung gehört nach den Lock, vor `DeleteLocation` |
| internal/store/location.go:113-127 | `Store.DeleteLocation`: `os.Remove`, nicht vorhanden = nil, keine Abhängigkeitsprüfung |
| internal/store/location_lock.go:57-62 | `LockLocation`, Schlüssel `UserID\0id`; Lock-Reihenfolge Gruppen -> Ort laut ADR-0083 |
| internal/store/compare_preset.go:123, :176 | `LoadComparePresets()` (globbt `briefings/*.json`, kind=="vergleich"), `LoadComparePreset(id)` |
| internal/model/compare_preset.go:18 | `LocationIDs []string` |
| src/services/scheduler_dispatch_service.py:491-493 | Wurfstelle: `Preset {id}: Orte [ids] nicht aufloesbar` (ValueError) |
| src/services/scheduler_dispatch_service.py:691-730 | `send_compare_preset` ruft `send_one_compare_preset` |
| src/services/compare_preview_service.py:238, :246 | Parallelstelle der Vorschau |
| api/routers/scheduler.py:345-365 | `manual_send_compare_preset`: ValueError -> 422 `detail=str(e)`, KeyError -> 404, `already_in_progress` -> 409 |
| internal/handler/compare_preset.go:609-650 | `SendComparePresetHandler` reicht Status und Body durch |
| frontend/src/routes/locations/+page.svelte:39, :71, :75, :116-117, :218-229 | Löschdialog, `api.del`, Fehleranzeige als `text-destructive`, kein Konflikt-Zweig |
| frontend/src/lib/api.ts:141-145 | wirft `ApiError {…body, status}`; Body eines 409 kommt in `e` an |
| frontend/src/lib/utils/sendOutcome.ts | `classifySendResponse`: 4xx zeigt `detail`, 409 immer „Versand läuft bereits" |
| frontend/src/routes/compare/[id]/+page.svelte:213-221 | Hub-Anzeige `sendMsg` |

## Existing Patterns
- 409-Antworten: `writeJSON(w, http.StatusConflict, map[string]interface{}{...})` (quota.go:175,
  metric_preset.go:164). Ein Muster „Löschen wegen Abhängigkeit verweigert" gibt es noch nicht.
- Frontend-409: CreateGroupDialog.svelte:8, AlertsPreviewCard.svelte, profileSaveError.ts.
- Lösch-Bestätigung als Vorbild: docs/specs/modules/bug_2214_compare_hub_delete_confirm.md.
- Trips referenzieren keine Orts-IDs (`Waypoint`, trip.go:82). Gruppen halten die Zugehörigkeit nicht selbst.
  Nur `ComparePreset.LocationIDs` hängt am Ort.

## Dependencies
- Upstream: Store (`WithUser`, `requireUser`), Lock-Mechanik ADR-0083.
- Downstream: Orte-Seite, `Step2Orte.svelte`, `LocationNewModal.svelte`, `CompareTabs.svelte` (Aufrufer nur per grep
  gefunden), Versand-Hub.

## Existing Specs / ADRs
- Specs: go_location_write.md, sveltekit_locations.md, generic_locations.md, orts_gruppen.md,
  compare_247_location_model.md, compare_preset_zeitplan.md, fix_2124_versand_nginx_timeout.md,
  bug_2214_compare_hub_delete_confirm.md.
- ADRs: 0003 (Mandantentrennung), 0031 (Persistenz data/users), 0083 (Schreibsperre Go/Python),
  0036 (Nebenläufigkeit), 0023 (Briefing-Subscription-Modell).

## Tests vorhanden
- Go: internal/handler/location_write_test.go:106, internal/store/store_location_write_test.go:37/:54,
  location_parallel_test.go, location_id_drift_test.go.
- Python: tests/tdd/test_compare_preset_access.py, test_compare_dispatch_fixed_window.py,
  tests/test_scheduler_router_requires_user_id.py. Kein Test für gelöschten Ort beim Versand.
- Frontend/E2E: routes/locations/__tests__/, sendOutcome-Tests (node --test), e2e/locations.spec.ts,
  compare-hub-versand-inline.spec.ts, orts-vergleich-c1.spec.ts, orts-vergleich-c4.spec.ts.

## Risks & Considerations
- **Befund Teilverlust:** Der Versand scheitert nur, wenn ALLE Orte nicht auflösbar sind (leere Liste).
  Fehlt nur ein Teil, geht das Preset still mit den übrigen Orten raus. Das ist ein stilles Verwerfen
  (Invariante 2 des Epics) und muss in der Analyse entschieden werden.
- **Bestandsdaten:** Presets mit bereits verwaisten Orts-IDs existieren evtl. schon; die Sperre allein heilt sie
  nicht. Kein Auto-Bereinigen (Datenerhalt-Regel), aber der Versand braucht einen sprechenden Grund.
- **Mandantentrennung:** Die Preset-Abfrage muss über `s.WithUser(...)` laufen; Test mit zwei Nutzern
  (Nutzer B darf Nutzer As Ort nicht durch Presets blockiert sehen).
- **Race:** Preset-Speichern mit Ort X parallel zu Ort-X-Löschen. Prüfung und Löschen sollten unter demselben
  Ortslock stehen; offen ist, ob das Speichern von Presets denselben Lock nimmt.
- **Frontend:** Der 409 darf nicht in den generischen „Fehler beim Löschen"-Zweig fallen. Versandseitig darf
  der neue Grund nicht über 409 laufen (sendOutcome deutet 409 als „läuft bereits"), sondern bleibt 422.
- **Nicht geprüft:** die weiteren Aufrufer des Ort-Löschens außer der Orte-Seite; ob `Location.Group` beim
  Löschen etwas nachzieht.

## Analysis

### Type
Bug (nutzersichtbar, Kriterium (a)). Reproduktion aus dem Code belegt: `DeleteLocationHandler` (internal/handler/location.go:276-297) löscht ohne Abhängigkeitsprüfung; `send_one_compare_preset` (scheduler_dispatch_service.py:491-493) wirft erst später `ValueError` → 422.

### Affected Files (with changes)
| File | Change Type | Description |
|------|-------------|-------------|
| internal/store/compare_preset.go | MODIFY | Hilfsfunktion: Ortsvergleiche des Nutzers, die Ort-ID in `LocationIDs` führen |
| internal/handler/location.go | MODIFY | Nach `LockLocation`, vor `DeleteLocation`: bei Treffern 409 `{error:"location_in_use", compare_presets:[{id,name}]}` |
| frontend/src/routes/locations/+page.svelte | MODIFY | 409-Zweig im Löschdialog: Namen der nutzenden Ortsvergleiche anzeigen, Ort bleibt |
| src/services/scheduler_dispatch_service.py (+ compare_preview_service.py:238/246) | MODIFY | Sprechender Grund bei nicht auflösbaren Orten (bleibt 422, nicht 409) |
| internal/handler/location_write_test.go, tests/… , frontend __tests__ | CREATE/MODIFY | Tests inkl. Zwei-Nutzer-Test |

### Scope Assessment
- Files: ~6-8 produktiv + Tests
- Estimated LoC: +150/-10 (produktiv ~100)
- Risk Level: MEDIUM — Löschpfad für Orte, Mandantentrennung, Lock-Reihenfolge (ADR-0083); keine Schema-Änderung

### Technical Approach
1. Go: Prüfung unter dem bereits gehaltenen Ortslock, Preset-Abfrage strikt über `s.WithUser(...)` (kein "default").
2. 409 mit Namen der Ortsvergleiche; Frontend zeigt sie, kein generisches "Fehler beim Löschen".
3. Versand: sprechender Grund (Ortsvergleich nennt fehlende Orte), Status bleibt 422, da `sendOutcome` 409 als "läuft bereits" deutet.
4. Bestandsdaten: kein Auto-Bereinigen; verwaiste Presets bekommen nur die klare Meldung.
5. Race Preset-Speichern vs. Ort-Löschen: Preset-Save nimmt den Ortslock nicht. In der Spec entscheiden (Save prüft Ort-Existenz unter Ortslock oder Restrisiko dokumentieren).

### Dependencies
Store (`WithUser`, `LockLocation`), ComparePreset-Persistenz (`briefings/*.json`), Orte-Seite, Send-Pfad Go-Proxy → Python. Trips referenzieren keine Orts-IDs; Gruppen nicht betroffen.

### Open Questions
- [ ] Teilverlust: Fehlt nur ein Teil der Orte, geht der Versand still mit den übrigen raus (stilles Verwerfen). Empfehlung: Versand läuft weiter, benennt aber die fehlenden Orte in Ergebnis/Mail-Hinweis — in der Spec als AC festlegen.
- [ ] Race Preset-Save vs. Ort-Löschen (siehe Ansatz 5).
- [ ] Weitere Aufrufer des Ort-Löschens (Step2Orte, LocationNewModal, CompareTabs) prüfen; ob `Location.Group` etwas nachzieht.
