---
entity_id: issue_498_stage_date_autosave
type: module
created: 2026-06-11
updated: 2026-06-11
status: draft
version: "1.0"
tags: [frontend, trips, stages, autosave, bugfix]
---

# Issue #498 — Etappen-Datum verschieben muss sofort persistieren

## Approval

- [x] Approved (PO 'go' 2026-06-11)

## Purpose

Das nachträgliche Verschieben eines Etappen-Datums (und die Kaskade „ganze Tour rückt
N Tage") muss **wirklich** gespeichert werden — sofort, ohne einen separaten, leicht zu
übersehenden „Etappen speichern"-Klick. Heute mutiert die Datum-Änderung nur den lokalen
UI-Zustand; der grüne Kaskaden-„verschoben ✓"-Zustand signalisiert fälschlich Abschluss,
obwohl nichts persistiert wurde → Nutzer verlieren die Änderung beim Verlassen/Reload.

## Source

- **File:** `frontend/src/lib/components/edit/EditStagesPanelNew.svelte`
- **File:** `frontend/src/lib/components/edit/EditStagesSection.svelte`
- **File:** `frontend/src/lib/components/trip-detail/TripTabs.svelte`
- **Identifier:** `handleDateChange`, `applyCascade`, `save`, Prop-Kette `onTripUpdate`

> **Schicht:** Frontend / User-UI (SvelteKit). Backend bleibt unverändert — das
> Go-Handler-`PUT /api/trips/{id}` persistiert `stage.date` bereits korrekt und gibt das
> aktualisierte Trip zurück (verifiziert per httptest-Roundtrip).

## Estimated Scope

- **LoC:** ~60
- **Files:** 3 (EditStagesPanelNew, EditStagesSection, TripTabs)
- **Effort:** low

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `PUT /api/trips/{id}` | Backend-API | persistiert Stages, liefert aktualisiertes Trip zurück |
| `formatDateRange` (tripHero.ts) | Helper | leitet Header-Datums-Eyebrow aus `stage.date` ab |
| `WeatherMetricsTab` (#694) | Referenz | bereits korrekt mit `onTripUpdate` verdrahtet — gleiches Muster |

## Implementation Details

```
1. onTripUpdate?: (updated: Trip) => void durch die Kette reichen:
   TripTabs (besitzt onTripUpdate vom +page) → EditStagesSection → EditStagesPanelNew.

2. EditStagesPanelNew.save() gibt das aktualisierte Trip aus der PUT-Antwort an
   onTripUpdate?.(updatedTrip) weiter (PUT antwortet mit dem ganzen Trip).

3. handleDateChange(): nach lokaler Mutation sofort persistieren (save()).
   - Bei Nicht-Kaskaden-Fällen (mittlere/Pausen-Etappe): direkt auto-save.
   - Bei erster Etappe mit Kaskaden-Vorschlag: zuerst nur das geänderte Datum
     auto-save; die Folge-Etappen erst nach applyCascade.

4. applyCascade(): nach der Verschiebung der Folge-Etappen sofort persistieren.
   Der grüne „verschoben ✓"-Done-State (cascade.done=true) wird erst gesetzt,
   NACHDEM das Auto-Save erfolgreich war.

5. Fehlerbehandlung: Schlägt das Auto-Save fehl (non-2xx/Netzwerk), wird saveError
   angezeigt und der Done-State NICHT gesetzt; lokaler Zustand bleibt erhalten.
```

## Expected Behavior

- **Input:** Nutzer ändert in `?tab=stages` ein Etappen-Datum bzw. bestätigt die Kaskade.
- **Output:** Das/die Datum/Daten sind sofort in der DB; das Trip-Datum (Header-Eyebrow,
  Etappen-Liste) zeigt unmittelbar den neuen Wert — auch nach Hard-Reload.
- **Side effects:** Pro Datum-Aktion ein `PUT /api/trips/{id}`. Der „Etappen speichern"-
  Button bleibt für Wegpunkt-Edits bestehen und unverändert.

## Acceptance Criteria

- **AC-1:** Given ein gespeicherter Trip mit Etappe (Datum A) in `?tab=stages` / When der
  Nutzer das Datum-Feld auf B ändert (ohne „Etappen speichern" zu klicken) und die Seite
  hart neu lädt / Then liefert `GET /api/trips/{id}` für diese Etappe Datum B.
  - Test: Playwright gegen laufenden Stack als eingeloggter Nutzer; Datum-Input füllen,
    KEIN Save-Klick, `page.reload()`, danach API-Roundtrip prüft `stages[i].date === B`.

- **AC-2:** Given ein Trip mit ≥2 Etappen, erste Etappe Datum A / When der Nutzer die erste
  Etappe auf A+N verschiebt und im Kaskaden-Strip „Alle mitverschieben" bestätigt (KEIN
  „Etappen speichern"-Klick) und hart neu lädt / Then sind nach Reload ALLE Etappen-Daten
  um N Tage verschoben (`GET /api/trips/{id}` bestätigt jede `stage.date`).
  - Test: Playwright; erste Etappe ändern, „Alle mitverschieben" klicken, `page.reload()`,
    API-Roundtrip prüft alle Daten = ursprünglich + N.

- **AC-3:** Given die Trip-Detail-Seite mit Header-Eyebrow `REGION · DATUM` / When der
  Nutzer im Etappen-Tab ein Datum ändert / Then aktualisiert sich das Header-Datum SOFORT
  ohne Hard-Reload auf den neuen Wert.
  - Test: Playwright; Header-Text vor Edit erfassen (z. B. „AUGUST 2026"), Datum auf einen
    anderen Monat ändern, ohne Reload prüfen dass der Header den neuen Monat zeigt.

- **AC-4:** Given der Kaskaden-Strip ist sichtbar / When „Alle mitverschieben" geklickt wird
  und das Auto-Save erfolgreich ist / Then erscheint der grüne Done-State
  („X Folge-Etappen verschoben") — und er erscheint NICHT, wenn das Auto-Save fehlschlägt.
  - Test: Erfolgsfall Playwright (Done-State sichtbar + API bestätigt Persistenz). Der
    Fehlerfall wird als Verhaltens-Guard geprüft (Done-State nur nach erfolgreichem PUT).

- **AC-5 (Guard, alt-treu):** Given der Etappen-Editor / When der Nutzer Wegpunkte ändert und
  „Etappen speichern" klickt bzw. ein Pausentag-Datum ändert / Then funktioniert beides wie
  bisher: Wegpunkt-Edits persistieren via Button, Pausentag-Datum persistiert sofort (AC-1
  gilt auch für Pausentage).
  - Test: Playwright; Pausentag-Datum ändern → Reload → API zeigt neues Pausen-Datum;
    „Etappen speichern"-Button bleibt vorhanden und funktionsfähig.

## Edge Cases

| Fall | Verhalten |
|---|---|
| Δ = 0 (gleiches Datum gewählt) | Kein Kaskaden-Strip; Auto-Save optional (kein Schaden), kein Done-State |
| Folge-Etappe ohne Datum bei Kaskade | Übersprungen (kein addDays auf leer) — wie bisher |
| Auto-Save schlägt fehl (Netz/4xx) | saveError sichtbar, Done-State NICHT gesetzt, lokaler Wert bleibt |
| Trip ohne `tripId` | Auto-Save no-op (wie save() heute: `if (!tripId) return`) |

## Out of Scope

- Debouncing mehrerer schneller Datum-Picks (ein PUT pro Change ist akzeptabel).
- Auto-Save für Wegpunkt-Edits (bleibt am „Etappen speichern"-Button).

## Changelog

- **2026-06-11:** Initial-Spec nach Re-Open #498. Root Cause: Datum-/Kaskaden-Änderung
  persistierte nur lokal; grüner Done-State täuschte Abschluss vor → Datenverlust beim
  Verlassen. Fix: sofortiges Auto-Save für Datum-Änderungen + Kaskade, `onTripUpdate`-
  Propagation für sofortige Header-Aktualisierung.
