---
entity_id: issue_436_wizard_save_navigation
type: module
created: 2026-05-29
updated: 2026-05-29
status: active
version: "1.0"
tags: [frontend, wizard, svelte, navigation, issue-436, epic-135]
---

# Issue #436 — Wizard-Save-Navigation zu Trip-Detail

## Approval

- [x] Approved (2026-05-29)

## Purpose

Nach dem Speichern eines neuen Trips im 5-stufigen Wizard navigiert die App zur Trip-Detail-Seite des neu erstellten Trips (`/trips/${created.id}`) anstatt zur allgemeinen Tripliste (`/trips`). Damit wird der seit Epic #135 offene TODO-Kommentar in `wizardState.svelte.ts` aufgelöst — die Trip-Detail-Route `/trips/[id]` existiert bereits, und die API-Antwort liefert die `id` schon mit, die bislang mit `void created` absichtlich verworfen wurde.

## Source

- **Schicht:** Reines Frontend (SvelteKit). Kein Go-Backend, kein Python-Backend.
- **Datei (geändert):** `frontend/src/lib/components/trip-wizard/wizardState.svelte.ts`
- **Identifier:** `WizardState.save()` — die `async`-Methode, die `POST /api/trips` aufruft und danach navigiert
- **Test (angepasst):** `frontend/src/lib/components/trip-wizard/__tests__/wizardState.test.ts`

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `POST /api/trips` | Go-Backend-Endpoint (vorhanden) | Liefert `Trip`-Objekt mit `.id` zurück; die `id` wird bisher mit `void created` verworfen |
| `goto` — SvelteKit `$app/navigation` | SvelteKit-Import (vorhanden) | Programmatische Navigation nach dem Save |
| `/trips/[id]/+page.svelte` | SvelteKit-Route (vorhanden) | Wertet `page.url.hash.replace(/^#/, '')` als `initialTab` aus — Hash-Navigation funktioniert sofort |
| `WeatherMetricsPreviewCard.svelte` | Frontend-Komponente (vorhanden, keine Änderung) | Hat bereits `<a href="#weather">Bearbeiten →</a>`; nach Navigation zu `/trips/${id}` ist dieser Link sofort erreichbar |
| `BriefingPreviewCard.svelte` | Frontend-Komponente (vorhanden, keine Änderung) | Hat bereits `<a href="#briefings">Bearbeiten →</a>`; Referenz-Pattern für Preview-Cards |

## Scope

**Nur Frontend, nur `wizardState.svelte.ts` + Test.** Keine Änderungen an Step5Reports.svelte, WeatherMetricsPreviewCard.svelte, +page.svelte oder Backend.

Nicht in Scope (explizit):
- „Inhalt im Output-Editor anpassen →"-Link in Step 5 — entschieden: kein Link (Option 3, Wizard = Erstellung, nicht Editierung)
- Label-Anpassung „Bearbeiten →" in WeatherMetricsPreviewCard — Text bleibt unverändert
- Hash-Navigation beim Save (`/trips/${id}#weather`) — nicht nötig, User landet auf Übersichts-Tab

## Implementation Details

### A. `wizardState.svelte.ts` — `save()`-Methode anpassen

**1. `void created` entfernen und `id` auslesen:**

```typescript
// VORHER (existierender Code):
const created = await resp.json() as Trip;
void created;  // TODO(epic-135): navigate to /trips/${created.id} once trip-detail exists
await goto('/trips');

// NACHHER:
const created = await resp.json() as Trip;
const targetPath = created?.id ? `/trips/${created.id}` : '/trips';
await goto(targetPath);
```

Der Fallback `'/trips'` greift nur, wenn die API keine gültige `id` liefert (Edge Case, z.B. ältere API-Version oder Parsing-Fehler). Kein zusätzlicher Error-Handler nötig — der vorhandene `try/catch`-Block in `save()` bleibt unverändert.

**2. TODO-Kommentar entfernen:**

```typescript
// ENTFERNEN: die Kommentarzeile mit TODO(epic-135)
// Die Zeile `void created;` entfällt ebenfalls vollständig.
```

### B. `wizardState.test.ts` — bestehenden Save-Navigationstest anpassen

Der Test, der prüft, dass `save()` nach `/trips` navigiert, wird auf den neuen Pfad umgeschrieben:

```typescript
// VORHER:
expect(mockGoto).toHaveBeenCalledWith('/trips');

// NACHHER (wenn API trip.id = '42' liefert):
expect(mockGoto).toHaveBeenCalledWith('/trips/42');

// ZUSÄTZLICH — Fallback-Test (API liefert kein id):
// Wenn created.id fehlt → expect(mockGoto).toHaveBeenCalledWith('/trips');
```

Der Test-Setup (Mock für `goto`, Mock für `fetch`/`POST /api/trips`) ist bereits vorhanden und muss nur in der Assert-Zeile angepasst werden.

### LoC-Budget

| Datei | Δ LoC |
|-------|-------|
| `wizardState.svelte.ts` (void + goto + Kommentar) | −2 / +2 (netto ±0) |
| `wizardState.test.ts` (Assert-Anpassung + Fallback-Test) | +8 |
| **Summe** | **~+8 LoC** |

Kein `loc_limit_override` nötig (weit unter 250).

## Expected Behavior

- **Input:** User klickt „Trip speichern" in Step 5 des Wizards; `POST /api/trips` antwortet mit einem `Trip`-Objekt, das ein nicht-leeres `id`-Feld enthält.
- **Output:** Browser navigiert zu `/trips/${created.id}` (Trip-Detail-Übersichtsseite des neu erstellten Trips).
- **Side effects:** Kein zusätzlicher API-Call. Navigation erfolgt einmalig nach erfolgreichem Save. Der vorhandene `try/catch`-Block in `save()` behandelt API-Fehler weiterhin unverändert.

**Fallback:** Wenn `created?.id` leer oder `undefined` ist, navigiert `save()` nach `/trips` (Tripliste). Dieser Pfad ist ein Sicherheitsfallback und kein normaler Flow.

## Acceptance Criteria

**AC-1:** Given der User hat einen neuen Trip im Wizard ausgefüllt (Step 5) und klickt „Trip speichern" / When die API mit `{ id: "42", ... }` antwortet / Then navigiert die App zu `/trips/42` (Trip-Detail-Seite des neuen Trips) — nicht zu `/trips` (Tripliste).
  - Test: (populated after /tdd-red)

**AC-2:** Given die API-Antwort enthält kein gültiges `id`-Feld (Edge Case: `created.id` ist `undefined` oder leer) / When `save()` die API-Antwort verarbeitet / Then navigiert die App sicher nach `/trips` als Fallback — kein unbehandelter Fehler, kein Navigation-in-Void.
  - Test: (populated after /tdd-red)

**AC-3:** Given der User ist in Step 5 des Wizards und sieht die Reports-Cards / When die Seite gerendert ist / Then enthält Step5Reports.svelte keinen „Inhalt im Output-Editor anpassen"-Link und keinen neuen Link zu Trip-Detail — der Wizard ist Erstellungs-Flow, nicht Editier-Flow (Option 3 entschieden).
  - Test: (populated after /tdd-red)

**AC-4:** Given `wizardState.svelte.ts` wird im Code-Review geprüft / When der Quellcode auf TODO-Kommentare und `void created`-Ausdrücke untersucht wird / Then enthält die Datei weder `TODO(epic-135)` noch `void created` — beide Zeilen sind vollständig entfernt.
  - Test: (populated after /tdd-red)

## Known Limitations

- **Hash-Navigation nicht im Scope:** Der User landet nach dem Save auf dem Übersichts-Tab von Trip-Detail, nicht direkt auf dem Wetter- oder Layout-Tab. Von dort führt der vorhandene „Bearbeiten →"-Link in `WeatherMetricsPreviewCard` zum `#weather`-Tab. Ein direktes `goto(\`/trips/${id}#weather\`)` wäre möglich, ist aber nicht Bestandteil dieser Spec.
- **ESLint `void`-Pattern:** Das Entfernen von `void created` kann einen ESLint-Unused-Variable-Fehler auslösen, wenn `created` nicht weiter genutzt wird. Da `created.id` jetzt genutzt wird, entfällt der Bedarf für `void` vollständig — kein ESLint-Suppress nötig.

## Changelog

- 2026-05-29: Initial spec erstellt für Issue #436. Löst TODO(epic-135) in `wizardState.svelte.ts` auf: `void created` entfernen, Navigation von `/trips` zu `/trips/${created.id}` mit Fallback. Kein Link in Step 5 (Option 3, PO-Entscheidung). Scope: 2 Dateien, ~8 LoC netto.
