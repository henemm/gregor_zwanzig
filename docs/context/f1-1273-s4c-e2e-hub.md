# Context: f1-1273-s4c-e2e-hub

**Issue:** #1301 Scheibe F1-Rest = Epic #1273 Scheibe S4c
**Datum:** 2026-07-19 · **Track:** Standard (Kontext + Analyse kombiniert)

## Request Summary

Seit #1273 S3 ist `/compare/[id]/edit` ein reiner 307-Redirect auf den Hub `/compare/[id]` — der Redirect verwirft dabei die `?tab=`-Query. ~21 E2E-Playwright-Specs steuern die tote Route weiter an bzw. warten auf Editor-Chrome, das der Hub nicht rendert. Diese Scheibe migriert sie strukturell auf den Hub (bzw. auf den weiterlebenden Create-Wizard `/compare/new`), **bevor** S5/F2 den `CompareEditor.svelte` löschen darf — sonst reißt die Löschung gültige Fachtests (Datenerhalt #102, Mandantentrennung, Autosave-Semantik) ersatzlos weg.

## Befund: Klassifikation der 21 Dateien (Explore-Agent, very thorough)

### KEEP — bereits korrekt (3)
| Datei | Grund |
|---|---|
| `compare-edit-redirect.spec.ts` | Prüft den Redirect selbst — bleibt unverändert |
| `bug-626-compare-menu-actions.spec.ts` | Bereits in S4a redirect-aware gemacht |
| `compare-hub-briefing-times.spec.ts` | Hub-basiert; **nur AC-5/AC-6 URL-FIX** (erwarten `/edit?tab=…`-Stift-Nav bzw. Default-Tab `vergleich` — Redirect droppt Query, Hub-Default ist `uebersicht`) |

### MIGRATE auf Hub — Feature lebt im Hub, nur Chrome/Save-Muster umbauen (9)
`compare-radar-toggle` · `compare-alarm-config` · `compare-legacy-fields-survive-save` (#102-Datenerhalt!) · `compare-editor-autosave` (575 Z., Kernsemantik #1261) · `compare-editor-autosave-user-isolation` (Mandantentrennung, Zwei-Kontext) · Compare-Blöcke von `feat-880-autosave-overlay`, `issue-758-save-indicator`, `save-status-indicator-honesty` (#1269 „kein PUT beim Tab-Öffnen" = exakt die Hub-Hydration-Bridges), `versand-tab-vergleich`.

**Mechanisches Ersetzungsmuster:**
- `compare-editor-tab-{id}` → `compare-detail-tab-{value}` (Werte: uebersicht·orte·wetter-metriken·idealwerte·layout·alarme·versand·vorschau)
- `compare-editor-save`/`-discard`-Klick → Autosave-Warten über `save-indicator` (im Hub vorhanden, `CompareTabs.svelte:976`)
- `compare-editor-name` → `compare-hub-name-edit`/`compare-hub-name-save`
- Inhalts-Anker tragen bereits: `alarme-*`, `alert-*`, `corridor-editor-vergleich`/`corridor-row-*`, `versand-tab`/`briefings-*`/`report-*-time`, API-GET-Asserts.

### MIGRATE auf /compare/new — testet Wizard-Editier-UI, die nur dort existiert (5)
`compare-editor-slice3` (Step2/Step3-Fidelity) · `compare-editor-slice4` (LayoutTab-Organism) · `layout-tab-vergleich` · `sortable-list-shared` (DnD im OutputLayoutEditor) · `issue-951-sheet-bottomnav` AC-3 (Mobile-Bibliotheks-Sheet).
Grund: Der Hub-Layout-Tab ist bewusst View-only-Summary (`CompareLayoutRow` + C2-Stundenverlauf-Steuerung); `layout-tab`/`channel-tab-*`/`compare-step*-*`/`sms-row-*`/`drag-handle` leben nur im Wizard.

### DELETE — abgeschaffte Editor-Chrome, kein Rest-AC zu retten (3 Blöcke)
- `issue-682-compare-editor-mobile` AC-4b (`top-app-bar-save` Dirty-Farbwechsel)
- `versand-tab-vergleich` AC-8 (Verwerfen-Button — im Autosave-Modell gegenstandslos)
- `compare-editor-fidelity-s8d` AC-19 (Edit-Modus ohne Create-CTA — im Hub gegenstandslos)

### UNSICHER (in Spec-Phase klären)
- `issue-718-idealwert-validation` AC-1/AC-3: ob Hub-`CorridorEditor` dieselbe min>max-Validierung führt (`corridor-editor-error` existiert, Semantik ungeprüft). AC-2 (Wizard) bleibt.
- `compare-flow-navigation` F001-Block (Z. 653): läuft nach Redirect vermutlich durch, Absicht auf Hub-Hydration umformulieren.

**Nicht anfassen:** Trip-Blöcke in `feat-880` (AC-1..5), `issue-758` (AC-1/2/4/5/7), `save-status-indicator-honesty` (AC-3/4), `issue-951` (AC-1/2/4).

## Related Files (Produktivcode, nur lesend als Anker)
| File | Relevanz |
|---|---|
| `frontend/src/routes/compare/[id]/edit/+page.server.ts` | 307-Redirect ohne `?tab=`-Passthrough — Verhaltensgrundlage |
| `frontend/src/lib/components/compare/CompareTabs.svelte` | Hub-Testids (`compare-detail-tab-*`, `save-indicator` Z. 976) |
| `frontend/src/routes/compare/[id]/+page.svelte` | `compare-hub-name-edit/-save`, Inline-Editing S2 |
| `frontend/src/lib/components/shared/{AlarmeTab,VersandTab,WeatherMetricsTab}.svelte` | Geteilte Organismen, Testid-Anker identisch Editor↔Hub |
| `frontend/src/lib/components/shared/corridor-editor/` | Hub-Idealwerte (`corridor-editor-vergleich`) |
| `frontend/src/routes/compare/new/+page.svelte` | `<CompareEditor mode="create">` — Ziel für Wizard-UI-Specs |

## Existing Patterns
- **Vorbild S4a:** `docs/specs/modules/epic_1273_s4a_test_migration.md` — gleiche Scheibenart, Muster für URL-Fix (`new RegExp('/compare/${id}(\\?|$)')` aus `compare-edit-redirect.spec.ts:75`) und API-basierte Mandantentrennung (`compare-cross-user-write-block.spec.ts`).
- **Autosave-Warten statt Save-Klick:** `compare-hub-name-region-profil.spec.ts` und `compare-flow-navigation.spec.ts` (Hub-Blöcke) zeigen das Muster.
- **storageState statt Per-Test-Login** (429-Rate-Limit, Memory-Regel) — bestehende `.auth/`-Configs weiterverwenden.

## Dependencies
- Upstream: Hub-Testids (stehen seit S1/S2/C1/C2/D2/D3 — D3 `e203a2d5` ist gelandet, Alarm-Tab-Struktur final).
- Downstream: **S5/F2 (Editor-Löschung) ist durch diese Scheibe blockiert.**

## Risks & Considerations
1. **Widerspruch im Zielbild (für F2, hier nur dokumentiert):** `epic-1273-compare-one-surface.md` sagt „Create-Wizard bleibt unverändert", Epic #1301 F2 sagt „CompareEditor.svelte löschen". Die 5 auf `/compare/new` migrierten Specs sind unter beiden Lesarten korrekt platziert, solange F2 die Anlege-Strecke klärt — dort erneut anfassen, wenn der Wizard fällt.
2. **Redirect droppt `?tab=`** — Tests dürfen nicht mehr `/edit?tab=…` als Einstieg nutzen, sondern direkt `/compare/{id}?tab=…`.
3. **Staging-Specs:** echte Läufe nur gegen Staging (GZ_API_BASE-Falle: Default PROD — Config prüfen). Kern-CI-Lauf lokal via `npx playwright test --list` als Struktur-Smoke.
4. **DnD-Fallen** (`sortable-list-shared`): boundingBox scrollt nicht, FLIP-Timing — bei Repoint auf Wizard unverändert lassen, nur Einstieg ändern.
5. **Parallel-Session:** D3 ist gelandet; keine bekannte offene Parallel-Arbeit an Compare-Flächen mehr.
6. **LoC:** reine Testarbeit (`frontend/e2e/*.spec.ts`) — zählt regulär ins 250-LoC-Limit; Umbau ist groß (~21 Dateien, aber je Datei kleine Diffs; `compare-editor-autosave.spec.ts` allein 575 Z. mit vielen Ankern). Ggf. Override oder Unterscheiben nötig.

## Existing Specs
- `docs/specs/modules/epic_1273_s4a_test_migration.md` (Vorbild, abgeschlossen)
- `docs/specs/modules/epic_1273_s4b_unit_test_migration.md` (abgeschlossen)
- `docs/features/epic-1273-compare-one-surface.md` (Scheiben-Plan, S4c-Definition)
