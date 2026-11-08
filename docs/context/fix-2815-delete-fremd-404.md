# Context: fix-2815-delete-fremd-404

## Request Summary
`DELETE /api/trips/{id}` antwortet 204, wenn die ID einem anderen Nutzer gehört (oder gar nicht existiert). Fremde Objekte sollen wie nicht vorhandene antworten: 404, wie es Compare-Presets und Metrik-Presets bereits tun. Kein Datenleck (der Store ist per `WithUser` an den Aufrufer gebunden, gelöscht wird nichts Fremdes), aber uneinheitlich (Nebenbefund aus #2237, Epic #2138).

## Ursache (belegt)
- `internal/store/trip.go:331` `DeleteTrip`: `os.Remove` mit `os.IsNotExist(err) → return nil` (idempotent). Zusätzlich: liegt unter der ID ein Compare-Preset (`kind=="vergleich"`), gibt es still `nil` zurück (Schutz Adversary F006).
- `internal/handler/trip.go:669` `DeleteTripHandler` mappt `nil` immer auf 204 — kein Existenz-Check vor dem Löschen.
- Gleiches Muster: `internal/handler/location.go:232` / `internal/store/location.go:114` (`DeleteLocation`, ebenfalls idempotent → 204) und `internal/handler/group.go:151` (`DeleteGroupLocked`, 204 ohne Existenz-Check).

## Related Files
| File | Relevance |
|------|-----------|
| internal/handler/trip.go:669 | DeleteTripHandler — hier fehlt der Existenz-Check |
| internal/store/trip.go:331 | DeleteTrip — idempotent, schützt Compare-Presets |
| internal/handler/compare_preset.go:458 | Vorbild: lädt Presets, `findComparePresetIdx < 0 → 404 not_found`, dann Delete |
| internal/handler/metric_preset.go:199 | Vorbild: `!found → 404 not_found` |
| internal/handler/location.go:232, internal/store/location.go:114 | gleicher Defekt bei Orten (Kandidat für Mitbehebung) |
| internal/handler/group.go:151 | gleicher Defekt bei Gruppen (Kandidat) |
| internal/handler/briefing_subscription.go:159 | `DELETE /api/briefings/{id}?kind=route` delegiert an DeleteTripHandler → erbt Fix automatisch |
| internal/handler/user_scoped_test.go:156 | Zwei-Nutzer-Test Trip-Delete (eigener Trip → 204) |
| internal/handler/delete_lock_cleanup_test.go:107 | `TestDeleteTripHandler_VergleichBleibtSamtSperrdatei` erwartet heute **204** für Compare-Preset-ID über den Trip-Pfad → muss auf 404 umgestellt werden (Datei + Sperrdatei bleiben weiterhin) |
| internal/handler/delete_lock_cleanup_test.go (unbekannt) | Sperrdatei darf ohne erfolgreiches Löschen nicht entfernt werden — Invariante bleibt |
| internal/handler/schreibsperre_frist_haltedauer_test.go:50, mengen_quote_test.go:512/562 | löschen existierende Seeds → 204 bleibt |
| docs/reference/api_contract.md:1378 | Vertragszeile `DELETE /api/trips/{id}` — Statuscodes nachtragen |

## Existing Patterns
- Compare-/Metrik-Preset-Delete: erst laden, nicht gefunden → `WriteError(w, r, 404, "not_found", nil)`, sonst löschen → 204.
- Trip-Load mit Kind-Guard: `LoadTrip` liefert für Compare-Preset-IDs „nicht gefunden“ (analog F006).
- Sperren: `lockBriefingOr503` vor dem Existenz-Check halten (Race DELETE vs. PUT, #1395); Sperrdatei nur bei `deleted=true` entfernen (#2237).

## Dependencies
- Upstream: `store.Store.WithUser`, `LoadTrip`/`DeleteTrip`, `ValidEntityID`, `lockBriefingOr503`.
- Downstream (Aufrufer):
  - Frontend `subscriptionExec.deleteSubscription` (`pruefe` wirft bei !ok) und `routes/archiv/+page.svelte:90` (wirft „DELETE failed: 404“) — betrifft nur den Fall „schon gelöscht“ (zweiter Tab); `busyId` verhindert Doppelklick.
  - Frontend `routes/locations/+page.svelte:75` (`api.del`, zeigt Fehlertext).
  - E2E-Aufräumcode (Playwright `request.delete`, `.catch`) und Python-Tests (`session.delete`) prüfen den Status nicht oder akzeptieren 404 ausdrücklich (`kurzform-…spec.ts:148`, `weather-metrics-tab-autosave.spec.ts:70`).

## Existing Specs
- `docs/specs/modules/fix_2216_ort_loeschen_sperre.md` — Orts-Löschsperre (409 location_in_use)
- `docs/reference/api_contract.md` §DELETE /api/locations/{id} (Z. 1344)

## Risks & Considerations
- Compare-Preset-ID über den Trip-Pfad: heute 204 ohne Wirkung, künftig 404 — bestehender Test wird bewusst umgestellt.
- Existenz-Check muss unter der Sperre passieren (sonst TOCTOU mit parallelem PUT/DELETE).
- Kaputte (nicht-JSON) Trip-Datei: heute fail-open gelöscht → darf weiterhin löschbar bleiben (nicht 404, sonst nie wieder entfernbar).
- Zweiter Tab löscht bereits gelöschten Trip → UI zeigt jetzt Fehler statt still Erfolg; prüfen, ob 404 im UI als „schon weg“ behandelt werden soll.
- Zwei-Nutzer-Test im deterministischen Kern ist Pflicht (Epic-DoD, ADR-0003).

## Analysis

### Type
Bug (Nebenbefund aus #2237, Epic #2138, Label `go-live-pflicht`)

### Scope-Entscheidung (technisch, kein PO-Thema)
Trip, Ort und Gruppe werden gemeinsam behoben, weil alle drei denselben Defekt haben und der Vertrag einheitlich sein soll (Epics themenweise abschließen). `DELETE /api/briefings/{id}?kind=route` erbt den Fix über `DeleteTripHandler`.

### Affected Files (with changes)
| File | Change Type | Description |
|------|-------------|-------------|
| internal/store/ (bestehende Fehler-Datei oder trip.go) | MODIFY | neuer Sentinel `store.ErrNotFound` |
| internal/store/trip.go | MODIFY | `DeleteTrip`: `ErrNotFound` bei fehlender Datei UND im `kind=="vergleich"`-Zweig; kaputte JSON-Datei wird weiter gelöscht (fail-open) |
| internal/store/location.go | MODIFY | `DeleteLocation`: `ErrNotFound` bei fehlender Datei |
| internal/store/group.go | MODIFY | `DeleteGroupLocked`: `ErrNotFound`, wenn keine Gruppe entfernt wurde (`len(filtered)==len(groups)`), ohne `saveGroups`; `DeleteGroup` reicht durch |
| internal/handler/trip.go | MODIFY | `DeleteTripHandler`: `errors.Is(err, ErrNotFound)` → 404 `not_found`; Sperrdatei-Aufräumen auch bei 404 (Flag `cleanup` statt `deleted`) |
| internal/handler/location.go | MODIFY | Reihenfolge: Sperre → `LoadLocation` (`nil,nil` → 404; Fehler bei kaputter Datei → weiter) → 409 `location_in_use` → `DeleteLocation` (`ErrNotFound` → 404 als Rückfall) |
| internal/handler/group.go | MODIFY | `ErrNotFound`: Aufräumschleife der `group_id`-Verweise trotzdem laufen lassen (Heilpfad nach Absturz), dann 404 |
| internal/store/store_trip_write_test.go:125, store_location_write_test.go:60, store_trip_briefings_test.go:183 | MODIFY | erwarten heute `nil` → künftig `ErrNotFound` (Preset-Datei bleibt unverändert) |
| internal/handler/delete_lock_cleanup_test.go:107 | MODIFY | Compare-Preset-ID über Trip-Pfad: 204 → 404, Datei + Sperrdatei bleiben |
| internal/handler/*_test.go | CREATE/MODIFY | neue Tests (s. u.) |
| docs/reference/api_contract.md (~Z.1344, ~1378, Gruppen-Zeile) | MODIFY | 404 `not_found` für alle drei DELETE-Endpunkte nachtragen |

### Scope Assessment
- Files: ~7 Produktiv + ~5 Test + 1 Doku
- Estimated LoC: Produktiv ~+60/-10, Tests ~+150
- Risk Level: LOW–MEDIUM (zentrale Löschpfade, aber kein Datenleck; Store per `WithUser` gebunden)

### Technical Approach
Sentinel-Fehler `store.ErrNotFound` statt `(bool, error)` oder Handler-Existenzprüfung:

| Variante | Bricht | Bewertung |
|---|---|---|
| Sentinel `ErrNotFound` | 3 Store-Tests (erwarten nil) | gewählt: Prüfung unter der Sperre, kein Extra-Read, Signaturen unverändert (`user_scope_guard_test.go`-Tabelle bleibt) |
| `(bool, error)` | zusätzlich Compile-Fehler in `user_scope_guard_test.go`, alle Aufrufer | mehr Eingriff, kein Mehrwert |
| Handler prüft per `LoadTrip` | – | kaputte JSON → 500, Datei nie mehr löschbar ⇒ verworfen |

Sperrdatei (#2237): `lockBriefingOr503` legt `<id>.json.lock` an. Ohne Aufräumen bei 404 entstünde pro fremder/zufälliger ID eine verwaiste Sperrdatei (Regression). `RemoveBriefingLockFile` ist selbst abgesichert (entfernt nur, wenn `<id>.json` fehlt und der flock frei ist), daher bei Erfolg UND bei 404 aufrufen. Compare-Preset unter Trip-Pfad: `.json` existiert → `RemoveBriefingLockFile` kehrt früh zurück, Datei + Sperrdatei bleiben.

Frontend: keine Änderung. `deleteSubscription` wirft beim Ortsvergleich schon heute bei 404 (zweiter Tab); der Trip verhält sich danach gleich, das ist einheitlicher, nicht neu kaputt. „404 = schon weg“ im UI wäre eine Scope-Erweiterung.

### Test-Plan (für RED)
- Zwei-Nutzer je Endpunkt (Pflicht, ADR-0003): B löscht A's ID → 404 `not_found`, A's Objekt lädt danach unverändert. Trip über BEIDE Wege (`/api/trips/{id}` und `/api/briefings/{id}?kind=route`).
- Unbekannte ID je Endpunkt → 404.
- Trip: unbekannte ID hinterlässt keine `<id>.json.lock`.
- Trip: kaputte JSON-Datei → 204 und weg.
- Ort: kaputte Datei → 204 und weg; unbekannte ID mit veraltetem Preset-Verweis → 404, nicht 409.
- Gruppe: unbekannte ID → 404, verwaiste `group_id`-Verweise auf diese ID werden trotzdem genullt.
- Bestehende Seeds-Löschungen (204) bleiben grün: `user_scoped_test.go:156`, `schreibsperre_frist_haltedauer_test.go:50`, `mengen_quote_test.go:512/562`.

### Dependencies
Upstream: `WithUser`, `ValidEntityID`, `lockBriefingOr503`, `RemoveBriefingLockFile`, `LockLocation`, `LockGroups`. Downstream: Frontend-Löschaufrufe (unverändert), E2E-Aufräumcode (prüft Status nicht bzw. akzeptiert 404).

### Open Questions
- keine (Scope, Frontend-Verhalten und Gruppen-Heilpfad technisch entschieden, s. o.)
