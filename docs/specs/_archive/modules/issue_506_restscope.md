---
entity_id: issue_506_restscope
type: module
created: 2026-06-01
updated: 2026-06-01
status: draft
version: "1.0"
tags: [frontend, cleanup, svelte, typescript, navigation, waypoint, deprecated]
---

# Spec: Issue #506 — Rest-Scope: Tote Props + @deprecated-Annotation + Navigation-Doku

## Approval

- [ ] Approved

## Purpose

Bereinigt drei unabhängige Rest-Scope-Items aus dem #503/#518-Cleanup-Zyklus: (1) entfernt die toten `onConfirm`/`onReject`-Props aus `WaypointCard` und den zugehörigen `noop()`-Glue-Code in `EditStagesPanelNew`, (2) annotiert `Waypoint.suggested?` in `types.ts` als `@deprecated` ohne das Feld zu entfernen (da `stripSuggested()` es per Destructuring liest), und (3) legt eine kanonische Navigations-Dokumentation in `docs/architecture/navigation.md` an, die die `?tab=`-Konvention, valide Tab-Werte und die `goto`-Muster verbindlich festhält. Ziel ist ein widerspruchsfreier Codestand ohne tote Stubs und mit einer Single Source of Truth für URL-Navigation.

## Source

- **Files:**
  - `frontend/src/lib/components/trip-detail/waypoints/WaypointCard.svelte`
  - `frontend/src/lib/components/edit/EditStagesPanelNew.svelte`
  - `frontend/src/lib/components/edit/issue_503_etappen_waypoints.test.ts`
  - `frontend/src/lib/types.ts`
  - `docs/architecture/navigation.md` (neu anlegen)
- **Identifier:** `WaypointCard`, `EditStagesPanelNew`, `Waypoint`

## Estimated Scope

- **LoC:** ~−30 (Löschungen), ~+3 (Kommentar-Annotation), ~+40 (navigation.md — zählt nicht als Code-LoC)
- **Files:** 4 geänderte + 1 neue Datei
- **Effort:** low

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `frontend/src/lib/types.ts` | Typdefinition | `Waypoint.suggested?: boolean` muss erhalten bleiben — `stripSuggested()` in `waypointEditor.ts` liest es per Destructuring |
| `frontend/src/lib/utils/waypointEditor.ts` | Utility | `stripSuggested()` nutzt `suggested`-Feld; dieses Modul wird nicht berührt |
| `frontend/src/lib/components/compare/CompareWizard.svelte` | Komponente | Eigene `onConfirm`/`onReject`-Nutzung in anderem Kontext (Orts-Vergleich) — nicht berühren |
| `frontend/src/routes/trips/[id]/edit/+page.server.ts` | SvelteKit Server-Route | Liefert Referenz-Implementierung für 301-Redirect-Konvention in navigation.md |

## Implementation Details

### Item 1: WaypointCard.svelte — tote Props entfernen

In `WaypointCard.svelte` (Zeile 9, 21, 23):
- Den `@deprecated`-Kommentar-Block über `onConfirm`/`onReject` entfernen
- Die beiden Props `onConfirm?: () => void` und `onReject?: () => void` aus der Props-Interface entfernen
- Keine weiteren Änderungen — der Rest der Komponente bleibt unverändert

### Item 2: EditStagesPanelNew.svelte — noop()-Glue entfernen

In `EditStagesPanelNew.svelte`:
- Zeilen 192–194: `noop()`-Funktion und zugehörigen Kommentar entfernen
- Zeilen 309–310: `onConfirm={noop}` und `onReject={noop}` aus dem `<WaypointCard>`-Aufruf entfernen
- Import von `noop` entfernen, falls er dadurch ungenutzt wird

### Item 3: issue_503_etappen_waypoints.test.ts — Gegentest entfernen

- Zeile 296: Den Test `'onConfirm/onReject bleiben als optionale @deprecated Props (Backward-Compat)'` vollständig entfernen — dieser Test prüft das Gegenteil des Zielzustands nach Item 1

### Item 4: types.ts — @deprecated-Annotation ergänzen

In `frontend/src/lib/types.ts`, Waypoint-Interface:
- Die Zeile `suggested?: boolean;` mit einem JSDoc-Kommentar versehen:
  ```ts
  /** @deprecated — wird von stripSuggested() gestrippt, keine UI liest dieses Feld mehr */
  suggested?: boolean;
  ```
- Das Feld MUSS erhalten bleiben — `stripSuggested()` in `waypointEditor.ts` nutzt `{ suggested: _suggested, ...rest } = w`

### Item 5: docs/architecture/navigation.md — neu anlegen

Verzeichnis `docs/architecture/` anlegen (existiert noch nicht) und `navigation.md` mit folgendem Inhalt erstellen:

**Pflicht-Abschnitte:**
1. **Überschrift + Kurzbeschreibung** — dieses Dokument ist die verbindliche Referenz für URL-Navigation in der SvelteKit-Frontend-Schicht
2. **?tab= Konvention** — Tab-State wird ausschließlich als Query-Parameter `?tab=<value>` kodiert, niemals als URL-Fragment (`#hash`)
3. **Valide Tab-Werte für Trip-Detail** — abschließende Liste: `overview`, `stages`, `weather`, `briefings`, `alerts`, `preview`
4. **goto-Muster** — kanonische Schreibweise mit allen erforderlichen Optionen:
   ```ts
   void goto(`?tab=${value}`, { replaceState: true, noScroll: true, keepFocus: true });
   ```
5. **301-Redirect-Konvention** — veraltete Routen leiten mit HTTP 301 auf die kanonische URL um; Referenzbeispiel: `edit/+page.server.ts` redirectet auf `/trips/[id]?tab=stages`
6. **Warum kein Hash?** — kurze Begründung: SvelteKit-SSR liest `#fragment` nicht; Query-Parameter sind server-seitig auswertbar und linkbar

## Expected Behavior

- **Input:** Kein Laufzeit-Input — reine Code-Bereinigung und neue Dokumentationsdatei
- **Output:** `WaypointCard` ohne tote Props; `EditStagesPanelNew` ohne `noop`-Glue; `Waypoint.suggested` klar als deprecated gekennzeichnet; `docs/architecture/navigation.md` als lesbare Referenz vorhanden
- **Side effects:** TypeScript-Build bleibt fehlerfrei; kein bestehendes Verhalten ändert sich; `stripSuggested()` funktioniert weiterhin unverändert

## Acceptance Criteria

- **AC-1:** Given `WaypointCard.svelte`, When der Quelltext analysiert wird, Then enthält er NICHT `onConfirm` oder `onReject` in der Props-Interface — keine DEPRECATED-Props mehr vorhanden.
  - Test: (populated after /tdd-red)

- **AC-2:** Given `EditStagesPanelNew.svelte`, When der Quelltext analysiert wird, Then enthält er NICHT `noop` und übergibt NICHT `onConfirm` oder `onReject` an WaypointCard.
  - Test: (populated after /tdd-red)

- **AC-3:** Given `frontend/src/lib/types.ts` Waypoint-Interface, When der Quelltext analysiert wird, Then ist `suggested?: boolean` mit einem `@deprecated`-Kommentar versehen, und das Feld existiert weiterhin (nicht entfernt).
  - Test: (populated after /tdd-red)

- **AC-4:** Given `docs/architecture/navigation.md`, When die Datei gelesen wird, Then enthält sie: (a) `?tab=` als kanonische URL-Konvention, (b) valide Tab-Werte für Trip-Detail, (c) das goto-Muster mit `replaceState/noScroll/keepFocus`, (d) die 301-Redirect-Konvention.
  - Test: (populated after /tdd-red)

- **AC-5:** Given TypeScript-Build im frontend Verzeichnis (`npm run check`), When der Check läuft, Then keine TypeScript-Fehler durch die Änderungen an `types.ts` oder `WaypointCard`.
  - Test: (populated after /tdd-red)

## Known Limitations

- `stripSuggested()` in `waypointEditor.ts` bleibt aktiv und liest `suggested` per Destructuring — eine vollständige Entfernung des Felds aus dem Typ würde erfordern, dass diese Funktion ebenfalls angepasst wird. Das ist out of scope für dieses Issue.
- `docs/architecture/` ist ein neues Verzeichnis — weitere Architektur-Dokumente (z.B. Auth-Flow, API-Vertrag) könnten hier in zukünftigen Issues nachgezogen werden.

## Changelog

- 2026-06-01: Initial spec created
