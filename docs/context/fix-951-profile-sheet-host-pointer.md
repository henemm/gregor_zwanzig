# Context: Mobil — profile-sheet-host fängt BottomNav-Klicks ab (#951)

## Request Summary
Auf Mobil-Viewport (390×844) im Etappen-Editor (`/trips/:id?tab=stages`) fängt der
eingebettete Wegpunkt-Sheet (`ProfileSheetEmbedded`) reale Klicks auf die BottomNav
ab. Verifiziert per echtem lokalem Playwright-Repro (nicht gemockt): `.click()` auf
`bottom-nav-item-compare` läuft in Timeout, `elementFromPoint` an der Nav-Item-Mitte
liefert ein `position:fixed; z-index:61; pointer-events:auto`-Element ohne eigene
Test-ID (der Sheet-Snap-Panel), nicht die BottomNav (`z-index:50`).

## Root Cause (verifiziert, nicht nur vermutet)
`profile-sheet-host` selbst hat bereits korrekt `pointer-events: none`
(`ProfileSheetEmbedded.svelte:110`) — das ist NICHT das Problem.

Der eigentliche Übeltäter ist der Sheet-Inhalts-Panel `[data-snap]` in
`Sheet.svelte:53-68`: `position:fixed; bottom:0; z-index:61`, bekommt bewusst
`pointer-events:auto` zurück (`ProfileSheetEmbedded.svelte:112-114`, nötig damit die
Wegpunktliste bedienbar bleibt). `ProfileSheetEmbedded` übergibt `<Sheet open={true}>`
**dauerhaft** (nie geschlossen, kein `onClose`) — das Sheet verhält sich wie ein
permanent offenes Modal statt eines mit der Seite koexistierenden eingebetteten
Panels. Der Panel-Boden bleibt IMMER bei `bottom:0`, auch im kleinsten Snap-Zustand
(`peek` = 32% Höhe) — das überlappt geometrisch den Bereich, in dem die BottomNav
(`z-index:50`, `height:64px`, `position:fixed;bottom:0`) sitzt. Da der Sheet-Panel
`z-index:61 > 50` hat, gewinnt er im überlappenden Bereich die Klick-Priorität.

Der zusätzliche darkening-Backdrop (`Sheet.svelte:45-52`, `z-index:60`) fängt hier
NICHT ab (er hat kein `pointer-events` override, erbt korrekt `none` vom Host) — nur
der Panel selbst.

## Related Files
| File | Relevance |
|------|-----------|
| `frontend/src/lib/components/edit/ProfileSheetEmbedded.svelte` | Bettet `<Sheet open={true}>` dauerhaft ein (Zeile 71); Host hat `pointer-events:none` (Zeile 110), Snap-Panel bekommt `auto` zurück (Zeile 112-114) |
| `frontend/src/lib/components/mobile/Sheet.svelte` | Gemeinsame Bottom-Sheet-Komponente. Backdrop Zeile 44-52 (`z-index:60`), Snap-Panel Zeile 53-68 (`position:fixed;bottom:0;z-index:61`) |
| `frontend/src/lib/components/edit/EditStagesPanelNew.svelte` | Mountet `<ProfileSheetEmbedded>` permanent im `.mobile-editor`-Block (Zeile 402-409, `@media max-width:899px`) |
| `frontend/src/lib/components/ui/sidebar/BottomNav.svelte` | Echte App-weite BottomNav (nicht `mobile/BottomNav.svelte`, das ist unbenutzt/Showcase). `position:fixed;bottom:0;z-index:50;height:64px` |
| `frontend/e2e/feat-880-autosave-overlay.spec.ts` (AC-5) | Wo das Problem beim Testschreiben auffiel; nutzt bewusst `elementFromPoint` statt echtem `.click()`, um den Bug zu umgehen |

## Andere Sheet-Konsumenten (Blast-Radius-Check)
Alle 6 anderen Verwender öffnen/schließen das Sheet ECHT (toggle `open` + `onClose`),
nutzen also den Backdrop/Modal-Charakter korrekt und bewusst:
- `trip-new/TripNewEditor.svelte:951` — `open={mobileSheetStageId !== null}`
- `edit/StageSelectSheet.svelte:40` — `{open}` (Thin-Wrapper, weitergereicht)
- `compare/CompareEditor.svelte:709` — `open={mobileLibraryOpen}`
- `trip-detail/WeatherMetricsTab.svelte:659` — `open={mailSheetOpen}`
- `mobile/MCompareActionSheet.svelte:30` — `{open}` (Thin-Wrapper, weitergereicht)

→ Nur `ProfileSheetEmbedded` missbraucht `Sheet` als Dauer-Panel. Ein Fix, der NUR
diesen einen Aufrufer betrifft (additiver, standardmäßig deaktivierter Sheet-Prop),
lässt alle anderen 5 Aufrufer unverändert.

## Existing Patterns
- Additive, rückwärtskompatible Props sind in diesem Codebase Konvention (siehe
  Kommentar in `BottomNav.svelte:8-9`: "additive mobile-shell-Props
  (backward-compatible, Default undefined)").
- `[[feedback_consolidate_duplicates]]`-Memory-Regel: eine Quelle, andere wird
  Thin-Wrapper — spricht gegen eine separate Duplikat-Komponente für "eingebettetes
  Sheet ohne Backdrop", dafür für einen opt-in Prop an `Sheet.svelte`.

## Dependencies
- Upstream: `Sheet.svelte` hat keine Abhängigkeiten außer `IconBtn.svelte` und
  `$app/environment` (Body-Scroll-Lock-Effekt, nur bei `open=true` — bei dauerhaft
  offenem Sheet aktuell dauerhaft `document.body.style.overflow:hidden`, was aber
  außerhalb des Issue-Scopes liegt).
- Downstream: 6 Aufrufer (s.o.), keiner davon betroffen von einem additiven Prop mit
  Default `false`.

## Existing Specs
- `docs/specs/modules/issue_373_mobile.md` (AC-4, AC-6) — ursprüngliche Sheet-Spec
- `docs/specs/modules/feat_880_autosave_overlay.md` — AC-5 dort dokumentiert bereits
  die Abgrenzung ("Scope dieser Spec ist ausschließlich das Overlay")

## Analysis

### Type
Bug (reproduzierbares Fehlverhalten, kein neuer Funktionsumfang).

### Affected Files (with changes)
| File | Change Type | Description |
|------|-------------|-------------|
| `frontend/src/lib/components/mobile/Sheet.svelte` | MODIFY | Neuer additiver Prop `variant?: 'modal' \| 'embedded' = 'modal'`. Bei `'embedded'`: kein Backdrop-Div, Snap-Panel bekommt `bottom` = BottomNav-Höhe statt `0` (verhindert Überlappung), Body-Scroll-Lock bleibt unverändert. Default `'modal'` → alle 5 bestehenden Aufrufer unverändert. |
| `frontend/src/lib/components/edit/ProfileSheetEmbedded.svelte` | MODIFY | `<Sheet variant="embedded">` statt `open={true}` pur; die pointer-events-Klimmzüge (Zeile 110-114) werden obsolet, da der Panel den Nav-Bereich nicht mehr physisch überlappt — Cleanup nach Fix-Verifikation. |
| `frontend/e2e/feat-880-autosave-overlay.spec.ts` (AC-5) oder neue Datei | MODIFY/CREATE | Regressionstest: echter `.click()` auf `bottom-nav-item-compare` (statt bisherigem `elementFromPoint`-Workaround) muss zur `/compare`-Route navigieren. |

### Scope Assessment
- Files: 2 Code-Dateien + 1 Testdatei
- Estimated LoC: +~20/-~6 (Sheet.svelte-Prop-Verzweigung, ProfileSheetEmbedded-Anpassung), +~15 Testcode
- Risk Level: **LOW** — additiver Prop mit unverändertem Default, nur 1 von 6 Aufrufern betroffen, Root Cause bereits per echtem Playwright-Repro bewiesen (nicht spekulativ)

### Technical Approach
Sheet.svelte um einen opt-in `variant`-Prop erweitern statt eine Parallel-Komponente
zu bauen (konsolidiert statt dupliziert, siehe `[[feedback_consolidate_duplicates]]`).
`ProfileSheetEmbedded` ist der einzige Aufrufer, der das Sheet als Dauer-Panel statt
als Modal nutzt — genau dort greift `variant="embedded"`. Die BottomNav-Höhe (64px)
wird als Konstante/Prop übergeben, damit der Snap-Panel-Boden sie automatisch
ausspart, unabhängig vom Zoom/Gerät.

### Dependencies
Keine neuen Abhängigkeiten. Reihenfolge: Sheet.svelte-Prop zuerst (rückwärtskompatibel,
für sich testbar), dann ProfileSheetEmbedded-Anpassung, dann Regressionstest.

### Open Questions
- [ ] Body-Scroll-Lock bei dauerhaft "offenem" Embedded-Sheet: aktuell sperrt es
  permanent `document.body.style.overflow`. Das ist bereits IST-Zustand vor diesem
  Fix und liegt außerhalb des AC-Scopes von #951 (nur Pointer-Event-Interception ist
  der gemeldete Bug) — wird nicht mit angefasst, aber als Beobachtung dokumentiert.

## Risks & Considerations
- Body-Scroll-Lock: Aktuell sperrt `Sheet.svelte`'s `$effect` bei jedem `open=true`
  den Body-Scroll. Bei `ProfileSheetEmbedded` ist das dauerhaft aktiv (Karte + Liste
  scrollen ohnehin intern, evtl. unkritisch) — sollte im Fix NICHT versehentlich neu
  eingeführt/geändert werden, nur der Panel-Bottom-Offset/Backdrop ist Scope dieses
  Issues.
- Der Fix darf die 5 echten Modal-Nutzungen nicht verändern (Backdrop + volle Höhe
  bis Bildschirmunterkante bleiben dort korrekt, da BottomNav während eines echten
  Modal-Overlays absichtlich nicht bedienbar sein soll).
- Snap-Höhen (`peek`/`half`/`full` = 32/55/84% viewport) sind fachlich vom
  Wegpunkt-Editor-Feature vorgegeben (Kommentar `ProfileSheetEmbedded.svelte:5-6`) —
  nicht verändern, nur den Bottom-Offset um die BottomNav-Höhe (64px) reduzieren.
