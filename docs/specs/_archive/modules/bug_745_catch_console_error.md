---
entity_id: bug_745_catch_console_error
type: bugfix
created: 2026-06-11
updated: 2026-06-11
status: draft
version: "1.0"
tags: [frontend, logging, tdd]
---

# Bug #745: Fehlende console.error(e) in catch-Blöcken

## Approval

- [ ] Approved

## Purpose

Drei API-catch-Blöcke im Frontend protokollieren Fehler nicht in der Konsole.
Durch #683 (Stepper-Entfernung) verschoben sich Zeilennummern, wodurch der
TDD-Test `bug_601_api_catch_logging.test.ts` an falschen Zeilen prüft und
gleichzeitig echte Logging-Lücken sichtbar wurden.

## Source

- **File:** `frontend/src/lib/bug_601_api_catch_logging.test.ts`
- **File:** `frontend/src/routes/trips/[id]/+page.svelte`
- **File:** `frontend/src/lib/components/trip-detail/WeatherMetricsTab.svelte`
- **File:** `frontend/src/lib/components/trip-wizard/steps/Step3Weather.svelte`

## Estimated Scope

- **LoC:** ~5
- **Files:** 4
- **Effort:** low

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `bug_601_api_catch_logging.test.ts` | test | Wächter-Test für AC-1 (source-inspection) |

## Implementation Details

**Änderung 1 — trips/[id]/+page.svelte Zeile 133:**
```diff
-   } catch {
+   } catch (e) {
+       console.error(e);
        testBriefingStatus = 'error';
```

**Änderung 2 — WeatherMetricsTab.svelte Zeile 364:**
```diff
    } catch (e: unknown) {
+       console.error(e);
        saveError = (e as { error?: string })?.error ?? 'Speichern fehlgeschlagen';
```

**Änderung 3 — Test: catchLine-Werte aktualisieren:**
```diff
-  { file: 'routes/trips/[id]/+page.svelte', catchLine: 110, ... }
+  { file: 'routes/trips/[id]/+page.svelte', catchLine: 133, ... }
-  { file: 'lib/components/trip-detail/WeatherMetricsTab.svelte', catchLine: 156, ... }
+  { file: 'lib/components/trip-detail/WeatherMetricsTab.svelte', catchLine: 364, ... }
-  { file: 'lib/components/trip-wizard/steps/Step3Weather.svelte', catchLine: 90, ... }
+  { file: 'lib/components/trip-wizard/steps/Step3Weather.svelte', catchLine: 91, ... }
```

## Expected Behavior

- Alle 5 Subtests in `bug_601_api_catch_logging.test.ts` grün
- Netzwerk- und Speicherfehler erscheinen in der Browser-Konsole (kein stiller Fehler)
- Kein Verhalten aus Nutzerperspektive ändert sich

## Acceptance Criteria

**AC-1:** Given der TDD-Wächter-Test `bug_601_api_catch_logging.test.ts` / When `node --experimental-strip-types --test src/lib/bug_601_api_catch_logging.test.ts` ausgeführt wird / Then schlagen alle 5 Subtests durch (pass: 5, fail: 0).

**AC-2:** Given ein Netzwerkfehler beim Test-Briefing-POST in `trips/[id]/+page.svelte` / When der catch-Block ausgelöst wird / Then ist der Exception-Wert über `console.error(e)` im catch-Block protokolliert (kein stilles Schlucken des Fehlers).

**AC-3:** Given ein Speicherfehler beim Metriken-Speichern in `WeatherMetricsTab.svelte` / When der catch-Block auf Zeile 364 ausgelöst wird / Then ist der Exception-Wert über `console.error(e)` protokolliert.

## Known Limitations

- Die inner-catch-Blöcke in `trips/[id]/+page.svelte` (Zeilen 129, 133) nutzen `catch {` ohne `(e)`. Zeile 133 wird in diesem Fix adressiert. Zeile 129 (JSON-Parse-Fehler-Fallback) liegt außerhalb des Test-Scopes von Issue #601.

## Changelog

- 2026-06-11: Spec erstellt für Issue #745
