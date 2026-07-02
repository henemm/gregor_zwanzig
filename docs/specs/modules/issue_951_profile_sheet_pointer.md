---
entity_id: issue_951_profile_sheet_pointer
type: bugfix
created: 2026-07-01
updated: 2026-07-01
status: implemented
version: "1.0"
tags: [frontend, mobile, sheet, bottomnav, pointer-events]
workflow: fix-951-profile-sheet-host-pointer
---

<!-- Issue #951 -->

# Issue 951 — ProfileSheetEmbedded blockiert BottomNav-Klicks (Mobil)

## Approval

- [ ] Approved

## Purpose

Auf Mobil-Viewport im Etappen-Editor (`/trips/:id?tab=stages`) verhindert der
dauerhaft eingebettete Wegpunkt-Sheet (`ProfileSheetEmbedded`) echte Klicks auf
die App-weite BottomNav, weil er die gemeinsam genutzte `Sheet.svelte`
missbräuchlich als Dauer-Panel statt als kurzzeitiges Modal nutzt und dadurch
den Nav-Bereich geometrisch überlappt. Diese Spec führt einen additiven
`variant`-Prop an `Sheet.svelte` ein, der den Backdrop entfernt und den
Panel-Boden um die BottomNav-Höhe anhebt, damit die Navigation im Etappen-Editor
wieder klickbar ist — ohne die 5 bestehenden Modal-Nutzungen zu verändern.

## Source

- **File:** `frontend/src/lib/components/mobile/Sheet.svelte`
- **Identifier:** `Sheet.svelte` Props-Interface + Backdrop-Div (Zeile 44-52) + Snap-Panel-Div (Zeile 53-68)
- **File:** `frontend/src/lib/components/edit/ProfileSheetEmbedded.svelte`
- **Identifier:** `<Sheet open={true} ...>` (Zeile 71), `.profile-sheet-host` pointer-events-Regeln (Zeile 107-114)

> **Schicht-Hinweis:** Reiner Frontend-Fix (`frontend/src/...`, SvelteKit). Keine
> Go-API- oder Python-Backend-Anteile betroffen.

## Estimated Scope

- **LoC:** ~+20/-6 (Sheet.svelte-Prop-Verzweigung, ProfileSheetEmbedded-Anpassung), ~+15 Testcode
- **Files:** 2 Code-Dateien + 1 Testdatei (neu oder Erweiterung von `feat-880-autosave-overlay.spec.ts`)
- **Effort:** low

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `frontend/src/lib/components/mobile/Sheet.svelte` | Frontend-Komponente | Gemeinsame Bottom-Sheet-Komponente, wird um `variant`-Prop erweitert |
| `frontend/src/lib/components/edit/ProfileSheetEmbedded.svelte` | Frontend-Komponente | Einziger Aufrufer, der auf `variant="embedded"` wechselt |
| `frontend/src/lib/components/ui/sidebar/BottomNav.svelte` | Frontend-Komponente | Liefert die Referenz-Höhe (64px), die der Panel-Boden aussparen muss — wird selbst nicht verändert |
| `frontend/src/lib/components/edit/EditStagesPanelNew.svelte` | Frontend-Komponente | Mountet `ProfileSheetEmbedded` permanent im Mobile-Editor-Block — wird selbst nicht verändert |
| `frontend/e2e/feat-880-autosave-overlay.spec.ts` (AC-5) | Test | Bestehender Test mit `elementFromPoint`-Workaround, wird auf echten Klick umgestellt bzw. durch neuen Regressionstest ergänzt |

## Implementation Details

### Sheet.svelte — additiver `variant`-Prop

```
interface Props {
  open?: boolean;
  onClose?: () => void;
  title?: string;
  eyebrow?: string;
  snap?: SheetSnap;
  variant?: 'modal' | 'embedded';   // NEU, Default 'modal'
  footer?: Snippet;
  children?: Snippet;
}
```

Verzweigung im Markup:
- Backdrop-Div (aktuell Zeile 45-52, `role="presentation" onclick={onClose}`)
  wird nur gerendert, wenn `variant !== 'embedded'`.
- Snap-Panel-Div (aktuell Zeile 53-68) erhält bei `variant === 'embedded'` ein
  `style:bottom` in Höhe der BottomNav (64px) statt `bottom:0`. Bei `'modal'`
  bleibt `bottom:0` unverändert.

Body-Scroll-Lock-Effekt (Zeile 32-41) bleibt unverändert — das ist laut
Analyse expliziter Nicht-Scope dieses Issues (siehe Known Limitations).

### ProfileSheetEmbedded.svelte — Umstellung auf `variant="embedded"`

```
<Sheet variant="embedded" snap={snapPosition} title="Wegpunkte" eyebrow="Etappe · {stage.name}">
```

Die pointer-events-Klimmzüge in `.profile-sheet-host` (Zeile 107-114:
`pointer-events: none` auf dem Host, `pointer-events: auto` auf `[data-snap]`)
bleiben als Sicherheitsnetz bestehen (kein Scope-Änderungsbedarf durch diese
Spec) — sie werden durch den Bottom-Offset-Fix obsolet für den Überlappungsfall,
schaden aber nicht und werden nicht in diesem Zug entfernt (Cleanup optional,
außerhalb des AC-Scopes).

### Referenz-Höhe BottomNav

64px, siehe `BottomNav.svelte:28` (`style="height: 64px; ..."`). Kein neuer
gemeinsamer Konstanten-Ort vorgesehen — Wert wird lokal in `Sheet.svelte`
als Literal übernommen (konsistent mit bestehendem Stil der Komponente, die
bereits mit Literalen wie `84%/55%/32%` arbeitet).

## Expected Behavior

- **Input:** `ProfileSheetEmbedded` wird im Mobile-Editor (`EditStagesPanelNew.svelte`, `@media max-width:899px`) permanent gemountet, wie bisher.
- **Output:** Der Wegpunkt-Sheet-Panel zeigt weiterhin Profil-SVG + Wegpunktliste, ragt aber nicht mehr über den unteren 64px-Streifen der BottomNav hinaus; kein Backdrop wird gerendert; die BottomNav bleibt in jedem Snap-Zustand (`peek`/`half`/`full`) klickbar.
- **Side effects:** Die 5 bestehenden Modal-Aufrufer (`TripNewEditor.svelte`, `StageSelectSheet.svelte`, `CompareEditor.svelte`, `WeatherMetricsTab.svelte`, `MCompareActionSheet.svelte`) erhalten weder Prop-Änderungen noch Verhaltensänderungen, da sie `variant` nicht setzen und damit den Default `'modal'` behalten.

## Acceptance Criteria

- **AC-1:** Given der Etappen-Editor ist auf Mobil-Viewport (390×844) geöffnet (`/trips/:id?tab=stages`) und `ProfileSheetEmbedded` ist sichtbar / When ein echter Playwright-`.click()` (kein `elementFromPoint`-Workaround) auf `bottom-nav-item-compare` ausgeführt wird / Then navigiert die Seite erfolgreich zu `/compare`.
  - Test: Playwright-E2E gegen Staging, echter `page.getByTestId('bottom-nav-item-compare').click()` gefolgt von `expect(page).toHaveURL(/\/compare/)` — kein DOM-Introspektions-Workaround, echtes Klick-Ereignis muss durchdringen.

- **AC-2:** Given `ProfileSheetEmbedded` ist im `peek`-Snap-Zustand (kleinste Höhe, 32%) / When der Nutzer auf ein beliebiges anderes BottomNav-Item klickt (z.B. `bottom-nav-item-trips`) / Then reagiert die Navigation, nicht der Sheet-Panel — auch im kleinsten Snap-Zustand überlappt der Panel-Boden die Nav-Zone nicht mehr.
  - Test: Playwright-E2E, Snap explizit auf `peek` setzen (via `snap-cycle`-Button oder Prop), dann echten Klick auf `bottom-nav-item-trips` ausführen und Navigation zu `/trips` verifizieren.

- **AC-3:** Given einer der 5 bestehenden Modal-Aufrufer (z.B. `CompareEditor.svelte` mit `mobileLibraryOpen`) öffnet sein Sheet auf Mobil-Viewport / When das Sheet sichtbar ist / Then wird weiterhin ein abdunkelnder Backdrop gerendert und ein Klick auf den Backdrop schließt das Sheet (`onClose` feuert) — unverändertes Verhalten gegenüber vor diesem Fix.
  - Test: Playwright-E2E im Compare-Editor, Bibliotheks-Sheet öffnen (echter Klick auf den auslösenden Button), Backdrop-Element (`role="presentation"`) auf Sichtbarkeit prüfen, dann Klick auf den Backdrop ausführen und verifizieren, dass das Sheet danach nicht mehr sichtbar ist.

- **AC-4:** Given `ProfileSheetEmbedded` ist im Etappen-Editor sichtbar / When die Etappe Wegpunkte enthält / Then zeigt der Sheet weiterhin das Etappenprofil (SVG) und die Wegpunktliste korrekt an, und es ist kein Backdrop-Element im DOM vorhanden.
  - Test: Playwright-E2E, `profile-row` und `waypoint-list` (Test-IDs aus `ProfileSheetEmbedded.svelte`) auf Sichtbarkeit mit realen Wegpunkt-Daten prüfen; zusätzlich verifizieren, dass kein Element mit `role="presentation"` (Backdrop) innerhalb von `profile-sheet-host` existiert.

## Known Limitations

- **Korrektur nach Adversary-Review (2026-07-01):** Entgegen der ursprünglichen
  Annahme in dieser Sektion sperrt der Body-Scroll-Lock-Effekt in `Sheet.svelte`
  (`$effect`, prüft `if (open)`) bei `ProfileSheetEmbedded` NICHT mehr aktiv,
  da die Implementierung `<Sheet variant="embedded" ...>` ohne `open`-Prop
  aufruft (Default `false`) — der Effect reagiert nur auf `open`, nicht auf
  `variant`. Das ist eine tatsächliche Verhaltensänderung gegenüber dem
  IST-Zustand vor dem Fix (vorher `open={true}` fest gesetzt → Lock aktiv).
  Funktional folgenlos: Der eigentliche Scroll-Container der Seite ist das
  innere `<main class="mobile-scroll-pad overflow-auto">` aus
  `+layout.svelte` — `document.body.style.overflow` hat diesen Container nie
  gesperrt, der Body-Lock war für dieses Layout bereits vor dem Fix wirkungslos.
  Kein AC betroffen, keine sichtbare Regression. Vom Adversary-Agent per
  `document.body.style.overflow`-Messung und `git show main`-Vergleich
  verifiziert (siehe `docs/artifacts/fix-951-profile-sheet-host-pointer/adversary-dialog.md`, Fund F001).
- Die bestehenden pointer-events-Overrides in `ProfileSheetEmbedded.svelte`
  (Zeile 107-114) werden nicht entfernt, auch wenn sie durch den Bottom-Offset
  redundant werden könnten — Cleanup ist optionaler Folgeschritt, kein Teil
  dieser Spec.
- Die BottomNav-Höhe (64px) wird als Literal in `Sheet.svelte` übernommen statt
  aus einer gemeinsamen Konstante importiert; bei künftigen Änderungen an der
  BottomNav-Höhe muss dieser Wert manuell synchron gehalten werden.

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** keine
- **Rationale:** Additive, rückwärtskompatible Erweiterung einer bestehenden
  Shared-Komponente (`Sheet.svelte`) um einen opt-in Prop mit unverändertem
  Default (`'modal'`). Kein Architektur-Richtungswechsel — folgt der
  bestehenden Projekt-Konvention "eine Quelle, andere wird Thin-Wrapper"
  (Memory-Regel `feedback_consolidate_duplicates`) und dem bereits etablierten
  additiven-Props-Muster (siehe Kommentar in `BottomNav.svelte:8-9`, Issue
  #373). Eine separate Duplikat-Komponente für "Sheet ohne Backdrop" wurde
  bewusst verworfen.

## Changelog

- 2026-07-01: Initial spec created — Issue #951
- 2026-07-01: Known Limitations korrigiert nach Adversary-Review (Body-Scroll-Lock-Aussage war falsch, funktional aber folgenlos, siehe F001 im Adversary-Protokoll)
