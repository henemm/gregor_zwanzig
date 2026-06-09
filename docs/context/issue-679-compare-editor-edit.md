# Context: Issue #679 — Compare-Editor Slice 2 (Edit-Modus + Dirty/Save-Flow)

## Request Summary
Edit-Modus des Orts-Vergleichs auf den neuen Tab-Editor (`CompareEditor`, Slice 1 #678) umstellen: `/compare/[id]/edit` rendert `CompareEditor mode="edit"` — alle Tabs sofort frei, **kein** Fortschrittsbalken, Dirty/Save-Flow (Speichern/Verwerfen + „Ungespeichert"-Pill). Löst #644 (CompareWizard ablösen). Epic #677, Slice 2/6.

## Related Files
| Datei | Relevanz |
|------|-----------|
| `frontend/src/lib/components/compare/CompareEditor.svelte` | Neuer Tab-Editor (Slice 1). Braucht `isEdit`-Zweig: Breadcrumb mit Name + Status-Dot, Ungespeichert-Pill, Speichern/Verwerfen, kein Progress. `isEdit`-Lock-Logik schon vorhanden (`open = isEdit || unlocked.has`). |
| `frontend/src/routes/compare/[id]/edit/+page.svelte` | Lädt `data.preset.*`, rendert aktuell `CompareWizard` → umstellen auf `CompareEditor mode="edit"`. **Lädt `empfaenger` NICHT** (Datenverlust-Risiko). |
| `frontend/src/routes/compare/[id]/edit/+page.server.ts` | Loader: `GET /api/compare/presets/{id}` (korrekt, ComparePreset). |
| `frontend/src/lib/components/compare/compareWizardState.svelte.ts` | State-Klasse. **`save()` schickt PUT an `/api/subscriptions/{id}` — FALSCHER Store!** Muss `/api/compare/presets/{id}` treffen. |
| `frontend/src/lib/components/compare/CompareWizard.svelte` | Alte Stepper-Shell (Edit-Header Speichern/Abbrechen). Nach diesem Slice tot (Entfernung Slice 6). |
| `frontend/src/lib/components/compare/CompareTabs.svelte:175` | Kanonisches Preset-PUT-Muster: `api.put('/api/compare/presets/{id}', {...preset, ...})`. |
| `claude-code-handoff/.../jsx/screen-compare-editor.jsx` (Z. 583–699) | Design-Quelle `isEdit`-Zweig: `dirty`/`markDirty`, Breadcrumb `Orts-Vergleiche / [Name]`, Status-Dot (aktiv/pausiert), Pill, Speichern/Verwerfen. |
| `internal/handler/compare_preset.go:166` (`UpdateComparePresetHandler`) | **Backend korrekt & unverändert:** RMW-Merge, `s.WithUser(UserIDFromContext)`, preserve display_config/previous_schedule/server-managed. |

## Existing Patterns
- **Preset-PUT:** `api.put('/api/compare/presets/{id}', {...preset, geänderteFelder})` — voller Preset-Spread, nur geänderte Felder überschreiben (CompareTabs).
- **ConfirmDialog** für Verwerfen/Abbrechen existiert (CompareWizard nutzt `cancelDialogOpen`/`discardDialogOpen`).
- **aktiv/pausiert:** `schedule === 'manual'` = pausiert, sonst aktiv (CompareTabs/CompareTile). `archived_at` = archiviert.
- **Tab-Lock im Edit:** in `CompareEditor`/`compareEditorLogic` schon `isEdit`-aware (`switchTab` lässt im Edit alle zu, `open = isEdit || unlocked.has`).
- Test-Muster: `frontend/e2e/compare-editor-slice1.spec.ts` (Playwright), `docs/specs/modules/issue_678_compare_editor_shell.md`.

## Dependencies
- **Upstream:** ComparePreset-Modell (`internal/model/compare_preset.go`), `PUT /api/compare/presets/{id}` (RMW, mandantengetrennt), Step2-5-Komponenten (vom Editor gemountet).
- **Downstream:** `/compare/[id]/edit`-Route; CompareWizard wird obsolet.

## Existing Specs
- `docs/specs/modules/issue_678_compare_editor_shell.md` — Slice 1 (Gerüst + Lock-Engine + Tab Vergleich).
- `docs/specs/modules/issue_458_compare_preset_backend.md` — ComparePreset-Backend.

## Risks & Considerations
1. **DATENVERLUST `empfaenger` (kritisch, CLAUDE.md Schema-Regel):** Edit-Loader lädt `empfaenger` nicht; State hat kein Feld. Backend ersetzt `empfaenger` aus dem Body (kein Merge wie bei display_config) und setzt nil→`[]`. → Save ohne Round-Trip **löscht Empfänger**. Lösung: Save sendet vollen Preset-Spread (`{...data.preset, ...edits}`), alle nicht editierten Felder round-trippen.
2. **Falscher Save-Endpoint (kritisch):** `state.save()` → `/api/subscriptions/{id}` (Trip-Subscriptions-Store), nicht Compare-Presets. AC-3 (Persistenz) unmöglich ohne Fix. Das ist die #644-Kernursache (Edit war effektiv kaputt / 404).
3. **schedule-Repräsentations-Mismatch:** State nutzt `daily_morning|daily_evening|weekly`, ComparePreset nutzt `daily|weekly|manual` + `hour_from/hour_to`. Save muss valides ComparePreset-`schedule` emittieren; geladenen Wert + hour_from/to per Round-Trip erhalten, nicht aus Step5-Repräsentation neu ableiten.
4. **Mandantentrennung (AC-3/AC-5):** Backend isoliert bereits über `UserIDFromContext`; Server-Loader reicht Session-Cookie durch. Kein `default`-Fallback. Mit 2 Nutzern testen.
5. **Frontend-only:** Kein Backend-Change nötig — E2E-Pfad = staging-validator (Playwright) gegen alle ACs.
