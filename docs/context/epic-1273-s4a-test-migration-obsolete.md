# Context: Epic #1273 Scheibe S4a — Test-Migration (nur echte Löschungen/URL-Fixes)

## Request Summary
Seit S3 (Commit `080e96d8`) ist `/compare/[id]/edit` ein reiner Redirect auf den Compare-Hub — `CompareEditor.svelte` (mit `compare-editor-*`-Testids, explizitem Save/Discard) rendert dort nicht mehr. S4a bereinigt nur die Testfälle, die wirklich totes Verhalten prüfen (Editor-Chrome, die per PO-Entscheid abgeschafft wurde) oder nur eine URL-Assertion brauchen. Business-Logik-Regressionstests werden **nicht** gelöscht, sondern in S4b strukturell auf den Hub umgezogen (siehe Risiken).

## Related Files

| File | Relevance |
|------|-----------|
| `frontend/e2e/compare-editor-edit.spec.ts` | AC-1/2/4/6 testen abgeschaffte Editor-Chrome (Fortschrittsbalken, Dirty-Pill, Save/Discard-Button, Status-Dot) → löschen. AC-5 (Mandanten-Isolation, rein API-basiert) muss erhalten bleiben. |
| `frontend/e2e/bug-626-compare-menu-actions.spec.ts` | Kebab-Menü „Bearbeiten“ → erwartet aktuell URL-Assert auf `/edit`; nach S3 landet man (nach Redirect) auf `/compare/{id}` ohne `/edit`. Nur URL-Assertion anpassen. |
| `frontend/e2e/compare-detail-edit-entry.spec.ts` | Analog: Bearbeiten-Button-Klick → URL-Assert auf `/edit` anpassen. |
| `frontend/e2e/compare-editor-autosave-user-isolation.spec.ts` | Bereits bestehender Mandanten-Isolationstest für den Autosave-Pfad (Issue #1261 AC-12). Deckt GET-Cross-Access (A→B) und "B's Daten bleiben unverändert" ab — **deckt NICHT** den PUT-Cross-User-Block (fremdes Preset per PUT überschreiben → 404) aus altem AC-5. Diese eine Assertion braucht ein neues Zuhause. |
| `frontend/e2e/compare-edit-redirect.spec.ts` | Bereits grün, testet das neue Redirect-Verhalten (S3, AC-1) — nicht anfassen, dient als Vorbild für URL-Pattern (`toHaveURL(new RegExp(...))`). |
| `frontend/e2e/issue-758-save-indicator.spec.ts` | **Gemischte Datei**: AC-1/2/4/5/7 testen den Save-Indikator im **Trip**-Editor (`/trips/{id}?tab=stages`), völlig unabhängig von Compare/`/edit`. AC-3/AC-6 sind Compare-spezifisch. **Aus S4a-Scope komplett entfernt** — gehört in S4b, weil die Compare-ACs strukturell (Hub-Selektoren) migriert werden müssen, nicht gelöscht. |

## Existing Patterns
- **URL-Pattern nach Redirect:** `await expect(page).toHaveURL(new RegExp(`/compare/${id}(\\?|$)`))` — Vorbild `compare-edit-redirect.spec.ts` Zeile 75.
- **Cross-User-Test-Pattern:** zweiter `browser.newContext()` + eigene Registrierung (`/api/auth/register`) + eigene Session — Vorbild `compare-editor-autosave-user-isolation.spec.ts` (aktuell) und die zu migrierende AC-5 aus `compare-editor-edit.spec.ts`.
- **Testid-Wechsel Hub vs. altem Editor:** `compare-editor-tab-*` (alt, Editor) → `compare-detail-tab-*` (neu, Hub). Betrifft S4a nicht direkt (keine Tab-Navigation in den verbleibenden Dateien), ist aber der Kernunterschied für S4b.

## Dependencies
- Upstream: Redirect-Implementierung aus S3 (`+page.server.ts` unter `frontend/src/routes/compare/[id]/edit/`).
- Downstream: keine — reine Testdateien, kein Produktivcode betroffen (Blast Radius Low laut Intake).

## Existing Specs
- `docs/specs/modules/feat_1273_s3_redirect.md` — S3-Spec, AC-1 (Redirect-Verhalten), Referenz für URL-Assertions.

## Risiken & Überlegungen
- **Datenverlust-Risiko vermieden:** Ursprüngliche Grobeinschätzung wollte 8 Dateien komplett löschen. Beim Lesen zeigte sich: 6 davon (`compare-editor-slice3/4`, `compare-alarm-config`, `compare-radar-toggle`, `compare-legacy-fields-survive-save`, `versand-tab-vergleich`) prüfen weiterhin gültige Fachlogik (u. a. „Altfelder überleben Speichern“ — direkter Bezug zu BUG-DATALOSS-GR221/#102) und wurden aus dem Löschumfang genommen → S4b.
- **AC-5-Teilaspekt (PUT-Cross-User-Block) fehlt sonst ersatzlos.** S4a muss diese eine Assertion (fremdes Preset per PUT ändern → 404) irgendwo unterbringen, bevor `compare-editor-edit.spec.ts` gelöscht wird — sonst Sicherheits-Regressionsschutz-Lücke ohne Ersatz.
- **`issue-758-save-indicator.spec.ts` nicht anfassen** in S4a — Gefahr, versehentlich Trip-Tests mitzureißen, wenn nur nach Dateiname statt Inhalt gearbeitet wird.

## Analysis

### Type
Feature (Test-Migration als eigene Scheibe des laufenden Epics #1273; kein Bugfix).

### Affected Files (with changes)
| File | Change Type | Description |
|------|-------------|-------------|
| `frontend/e2e/compare-editor-edit.spec.ts` | DELETE | Ganze Datei entfällt — AC-1/2/4/6 testen abgeschaffte Editor-Chrome, AC-5 zieht vorher um (siehe nächste Zeile). |
| `frontend/e2e/compare-editor-autosave-user-isolation.spec.ts` | MODIFY | Neue Assertion ergänzen: fremdes Preset per PUT ändern → 404 (bisher nur GET-Cross-Access + "Bs Daten unverändert" abgedeckt, PUT-Block fehlt). |
| `frontend/e2e/bug-626-compare-menu-actions.spec.ts` | MODIFY | URL-Assert nach Kebab-„Bearbeiten“-Klick: `/compare/{id}/edit` → `/compare/{id}` (Redirect-Ziel). |
| `frontend/e2e/compare-detail-edit-entry.spec.ts` | MODIFY | URL-Assert nach Bearbeiten-Button-Klick: gleiche Anpassung. |

Kein Produktivcode betroffen (nur `frontend/e2e/*.spec.ts`).

### Scope Assessment
- Files: 4 (1 delete, 3 modify)
- Estimated LoC: -176 (Datei-Löschung) / +~15 (neue PUT-Assertion) / ~4 Zeilen URL-Fixes → netto deutlich negativ, weit unter dem 250-LoC-Workflow-Limit.
- Risk Level: LOW — reine Testdateien, kein Produktivpfad; einziges Risiko (Sicherheits-Regressionslücke durch PUT-Block-Verlust) wird durch die MODIFY-Zeile oben explizit geschlossen.

### Technical Approach
1. In `compare-editor-autosave-user-isolation.spec.ts` einen zusätzlichen Testfall (oder eine zusätzliche Assertion im bestehenden Testflow) ergänzen: Nutzer B versucht per `PUT /api/compare/presets/{presetA}` das Preset von Nutzer A zu überschreiben → erwartet 404. Nutzt das vorhandene Zwei-Kontext-Setup (`ctxB`/`pageB`) wieder, keine neue Fixture-Infrastruktur nötig.
2. `compare-editor-edit.spec.ts` danach vollständig löschen (erst nach Schritt 1, damit die Sicherheitsassertion nie unbeobachtet fehlt).
3. In den beiden URL-Fix-Dateien nur die Ziel-URL der `toHaveURL`-Assertion ändern (Muster aus `compare-edit-redirect.spec.ts` Zeile 75 übernehmen: `new RegExp(`/compare/${id}(\\?|$)`)`), Rest der Testlogik unverändert.

### Dependencies
- Upstream: Redirect-Implementierung aus S3 (bereits live, `compare-edit-redirect.spec.ts` bestätigt sie grün).
- Downstream: keine.

### Open Questions
- Keine offenen — Scope ist eng genug, dass keine Rückfrage an den User nötig ist.
