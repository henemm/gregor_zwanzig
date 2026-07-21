---
entity_id: issue_682_compare_editor_mobile
type: module
created: 2026-06-10
updated: 2026-06-10
status: draft
version: "1.0"
tags: [frontend, mobile, compare, editor, design-compliance, epic-677]
---

# Compare-Editor Slice 5 — Mobile-Editor CEM_ (Create + Edit, ≤899px)

## Approval

- [ ] Approved

## Purpose

`CompareEditor.svelte` hat kein Mobile-Layout. Auf Viewport ≤899px zeigt der Editor
das gebrochene Desktop-Layout (breadcrumb, Hero, Tab-Bar mit `padding: 0 40px`). Dieser
Slice bringt **vollständige Mobile-Parität** für beide Modi (Create + Edit): scrollbare Tab-Bar,
Progress-Anzeige, Lock-Toast, Floating-CTA und ein Bottom-Sheet für die Orts-Bibliothek in
`Step2Orte`. **Frontend-only, additiv. Desktop-Markup bleibt byte-identisch.** Implementierung
folgt exakt dem CSS-only-Switch-Muster aus `TripNewEditor.svelte` (Issue #661, erprobtes Pattern).

## Source

- **Datei A (Kern — Mobile-Markup + `<style>`):** `frontend/src/lib/components/compare/CompareEditor.svelte`
- **Datei B (additiv — Bibliothek-Button + Sheet):** `frontend/src/lib/components/compare/steps/Step2Orte.svelte`

> **Schicht: Frontend / User-UI** → `frontend/src/...` (SvelteKit, gregor20.henemm.com).
> Kein Backend-, Schema- oder API-Change. Routes `/compare/new` und `/compare/[id]/edit` bleiben unverändert.

## Estimated Scope

- **LoC:** ~350–400 (loc_limit_override auf 400 setzen; CompareEditor ~200–280, Step2Orte ~50–80, Style ~50)
- **Files:** 2 (1 Kern-Edit, 1 additives Step-Edit)
- **Effort:** high (parallel gerendertes Mobile-Markup + CSS-only-Switch; Bottom-Sheet-Integration)

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `compareEditorLogic.ts` | reuse | `unlockedTabs`, `doneTabs`, `TAB_ORDER`, `CompareTabId` — unverändert |
| `compareWizardState.svelte.ts` | reuse | `wiz`-Context (name, pickedIds, channelLayouts etc.) — unverändert |
| `mobile/Sheet.svelte` | reuse | `snap="full"` Bottom-Sheet für Orts-Bibliothek |
| `mobile/Toast.svelte` | reuse | Lock-Toast auf gesperrtem Tab-Tap (kind="info", 2000ms) |
| `mobile/MBtn.svelte` | reuse | Touch-CTA-Button im Mobile-Block |
| `mobile/MField.svelte` | reuse | Mobile Form-Felder (falls benötigt in Step2) |
| `mobile/MInput.svelte` | reuse | Mobile Eingabefelder |
| `mobile/TopAppBar.svelte` | reuse | Mobile App-Leiste (title, eyebrow, leftIcon, right-Snippet) |
| `frontend/src/app.css` `@media (max-width:899px)` | constraint | Kanonischer Breakpoint |

## Implementation Details

### Zentrales Muster (identisch zu Issue #661)

CSS-only `@media (max-width:899px)`-Switch, **kein JS-Viewport-Switch**. Desktop- und Mobile-Markup
werden **parallel gerendert** und per CSS toggled:

```
.cm-desktop { display: block; }   .cm-mobile { display: none !important; }
@media (max-width: 899px) {
  .cm-desktop { display: none !important; }
  .cm-mobile  { display: block !important; }
  .cm-mobile-flex { display: flex !important; }
}
```

`!important` ist nötig, weil Mobile-Elemente teilweise inline `display:flex` tragen
(App-Leiste, Tab-Bar) — `!important` überschlägt Inline-Styles (Lehre aus #661).

### CompareEditor.svelte — Mobile-Markup-Block

**Lock-Toast-State (additiv im `<script>`):**
```
let lockToastMsg = $state('');
let lockToastVisible = $state(false);
let _lockToastTimer: ReturnType<typeof setTimeout> | null = null;

function showLockToast(hint: string) {
  lockToastMsg = hint;
  lockToastVisible = true;
  if (_lockToastTimer) clearTimeout(_lockToastTimer);
  _lockToastTimer = setTimeout(() => { lockToastVisible = false; }, 2000);
}
```

Bestehende `handleTabClick(id)` erweitern: wenn `!isEdit && !unlocked.has(id)`, statt
frühem Return → `showLockToast(TAB_DEFS.find(t => t.id === id)?.lockHint ?? 'Tab gesperrt')`.

**Mobile-Block-Struktur** (nach dem bestehenden `</div><!-- /.cm-desktop -->` vor dem `</div>` des Root-Wrappers):

```
<div class="cm-mobile" style="position: relative; min-height: 100vh; display: flex; flex-direction: column;">

  <!-- Toast (immer im DOM, sichtbar wenn lockToastVisible) -->
  {#if lockToastVisible}
    <Toast kind="info" msg={lockToastMsg} />
  {/if}

  <!-- 1. TopAppBar -->
  <div class="cm-mobile-flex" data-testid="cm-mobile-appbar"
       style="position: sticky; top: 0; z-index: 20; align-items: center;
              border-bottom: 1px solid var(--g-rule-soft); background: var(--g-paper);">
    <TopAppBar
      title={TAB_DEFS.find(t => t.id === activeTab)?.label ?? 'Vergleich'}
      eyebrow={wiz.name || (isEdit ? 'Bearbeiten' : 'Neuer Vergleich')}
      leftIcon="arrow_back"
    >
      {#snippet right()}
        {#if isEdit}
          <!-- Edit-Modus: Speichern in App-Leiste, orange bei dirty -->
          <button type="button" data-testid="cm-mobile-save"
                  disabled={!dirty}
                  style="font-size:14px; font-weight:600; color:{dirty ? 'var(--g-accent)' : 'var(--g-ink-4)'}; background:none; border:none; padding:8px 12px; cursor:{dirty ? 'pointer' : 'not-allowed'};"
                  onclick={handleSave}>Speichern</button>
        {:else}
          <!-- Create-Modus: Speichern-Button nur wenn versandVisited -->
          <button type="button" data-testid="cm-mobile-activate"
                  disabled={!versandVisited}
                  style="font-size:14px; font-weight:600; color:{versandVisited ? 'var(--g-accent)' : 'var(--g-ink-4)'}; background:none; border:none; padding:8px 12px; cursor:{versandVisited ? 'pointer' : 'not-allowed'};"
                  onclick={handleActivate}>Aktivieren</button>
        {/if}
      {/snippet}
    </TopAppBar>
  </div>

  <!-- 2. Progress-Bar (nur Create-Modus) -->
  {#if !isEdit}
    <div class="cm-mobile-flex" data-testid="cm-mobile-progress"
         style="align-items:center; gap:8px; padding:8px 16px; background:var(--g-paper);">
      {#each TAB_ORDER as tid, i}
        <div style="flex:1; height:3px; border-radius:2px;
                    background:{doneTabs({...}).has(tid) ? 'var(--g-accent)' : (tid === activeTab ? 'var(--g-accent-soft,#bcd)' : 'var(--g-rule)')};">
        </div>
      {/each}
      <span style="font-family:var(--g-font-mono); font-size:10px; color:var(--g-ink-3);">
        {[...doneTabs({...})].length}/{TAB_ORDER.length}
      </span>
    </div>
  {/if}

  <!-- 3. Scrollbare TabBar -->
  <div class="cm-mobile-flex" data-testid="cm-mobile-tabbar"
       style="overflow-x:auto; border-bottom:1px solid var(--g-rule-soft);
              -webkit-overflow-scrolling:touch; scrollbar-width:none; flex-shrink:0;">
    {#each TAB_DEFS as t}
      {@const open = isEdit || unlocked.has(t.id)}
      <button type="button"
              data-testid="cm-mobile-tab-{t.id}"
              data-locked={open ? 'false' : 'true'}
              style="min-height:44px; padding:0 16px; font-size:14px; font-weight:600;
                     white-space:nowrap; border:none; background:none;
                     color:{activeTab === t.id ? 'var(--g-accent)' : (open ? 'var(--g-ink)' : 'var(--g-ink-4)')};
                     border-bottom:{activeTab === t.id ? '2px solid var(--g-accent)' : '2px solid transparent'};
                     cursor:{open ? 'pointer' : 'not-allowed'}; flex-shrink:0;"
              onclick={() => {
                if (!isEdit && !open) {
                  showLockToast(t.lockHint ?? 'Tab gesperrt');
                  return;
                }
                handleTabClick(t.id);
              }}>
        {t.label}{!open ? ' 🔒' : ''}
      </button>
    {/each}
  </div>

  <!-- 4. Tab-Inhalt (bestehende Step-Komponenten, shared mit Desktop) -->
  <div style="flex:1; padding:16px; overflow-y:auto;">
    {#if activeTab === 'vergleich'}
      <!-- Inline: Name, Region, Aktivitätsprofil — MField/MInput statt Desktop-Grid -->
      ...
    {:else if activeTab === 'orte'}
      <Step2Orte {locations} />
    {:else if activeTab === 'idealwerte'}
      ...
    {:else if activeTab === 'layout'}
      ...
    {:else if activeTab === 'versand'}
      ...
    {/if}
  </div>

  <!-- 5. Floating-CTA (Create-Modus, je Tab ein "Weiter"-Button) -->
  {#if !isEdit}
    <div data-testid="cm-mobile-cta" style="position:sticky; bottom:0; padding:12px 16px;
         background:var(--g-paper); border-top:1px solid var(--g-rule-soft);">
      <MBtn fullwidth onclick={handleMobileNext}
            disabled={!canAdvanceFromTab(activeTab)}>
        {activeTab === 'versand' ? 'Aktivieren' : 'Weiter →'}
      </MBtn>
    </div>
  {/if}

</div><!-- /.cm-mobile -->
```

`handleMobileNext()`: ruft `handleTabClick(TAB_ORDER[TAB_ORDER.indexOf(activeTab) + 1])` auf
(nächster Tab) oder `handleActivate()` wenn `activeTab === 'versand'`.

`canAdvanceFromTab(tab)`: gibt `true` zurück wenn der aktive Tab als „done" gilt oder
mindestens unlock-Bedingung des nächsten Tabs erfüllt ist (aus `unlocked`).

### Step2Orte.svelte — Bibliothek-Button + Sheet (additiv)

Das Desktop-Markup (Inline-Library-Grid) bleibt unverändert. Mobile erhält einen additiven
Button der ein `Sheet` öffnet:

```
<!-- Neuer State (in <script>): -->
let librarySheetOpen = $state(false);

<!-- Im Markup: nach dem Desktop-Library-div, VOR dem schliessenden </div> der Komponente -->
<div class="cm-mobile" data-testid="compare-step2-mobile-library-btn">
  <MBtn onclick={() => { librarySheetOpen = true; }}>
    Ort aus Bibliothek wählen
  </MBtn>
</div>

<Sheet bind:open={librarySheetOpen} snap="full" title="Orts-Bibliothek"
       onClose={() => { librarySheetOpen = false; }}>
  <!-- Bestehende libraryGroups-Iteration mit Checkboxen (identische Logik wie Desktop) -->
  {#each libraryGroups as [groupName, groupLocs] (groupName)}
    <div style="padding:8px 0;">
      <div style="font-size:11px; color:var(--g-ink-3); padding:4px 16px;">{groupName}</div>
      {#each groupLocs as loc (loc.id)}
        <label style="display:flex; align-items:center; gap:12px; padding:12px 16px;
                       min-height:44px; cursor:pointer;">
          <input type="checkbox"
                 checked={ws.pickedIds.has(loc.id)}
                 onchange={() => ws.togglePick(loc.id)}
                 data-testid="compare-step2-mobile-lib-check-{loc.id}" />
          <span>{loc.name}</span>
        </label>
      {/each}
    </div>
  {/each}
</Sheet>
```

Die `.cm-mobile`/`.cm-desktop`-Klassen in Step2Orte benötigen keine eigene `<style>`-Section —
die globalen Regeln aus CompareEditor gelten **nicht** für Step2Orte (scoped styles).
Stattdessen: `cm-mobile`-Div erhält `display:none` als Inline-Style für Desktop,
überschrieben durch globale App-CSS-Regel `@media (max-width:899px) { .cm-mobile { display:block; } }`.
Alternativ: eigene lokale `<style>` in Step2Orte nach demselben Pattern (Entscheidung dem Developer).

### CSS (in CompareEditor.svelte `<style>`)

```css
/* ─── CSS-only Responsive Switch (Issue #682, #661-Pattern) ──────────────────
   Desktop-Markup (.cm-desktop) sichtbar bei ≥900px, Mobile-Markup hidden.
   Auf ≤899px: umgekehrt. !important nötig für inline-display:flex Override. */
.cm-mobile {
  display: none !important;
}
@media (max-width: 899px) {
  .cm-desktop {
    display: none !important;
  }
  .cm-mobile {
    display: block !important;
  }
  .cm-mobile-flex {
    display: flex !important;
  }
}
```

### Playwright-Selector-Regel (Lehre aus #661)

`display:none`-Elemente werden von Playwright gefunden — Selektoren MÜSSEN auf sichtbares
Markup eingeschränkt sein (z.B. `.cm-mobile [data-testid="..."]` oder `locator(...).filter({visible:true})`).
Desktop-Testids die parallel im Mobile-Block existieren müssen mit einem Scope-Locator
isoliert werden.

### Testid-Vertrag (neue Testids)

| Testid | Element |
|--------|---------|
| `cm-mobile-appbar` | Mobiler App-Leisten-Wrapper |
| `cm-mobile-save` | Speichern-Button in App-Leiste (Edit-Modus) |
| `cm-mobile-activate` | Aktivieren-Button in App-Leiste (Create-Modus) |
| `cm-mobile-progress` | Progress-Bar-Wrapper |
| `cm-mobile-tabbar` | Scrollbare Tab-Bar |
| `cm-mobile-tab-{id}` | Einzelner Tab-Button (id = vergleich/orte/idealwerte/layout/versand) |
| `cm-mobile-cta` | Floating-CTA-Wrapper |
| `compare-step2-mobile-library-btn` | Bibliothek-Button-Wrapper in Step2Orte |
| `compare-step2-mobile-lib-check-{loc.id}` | Checkbox je Ort im Bibliothek-Sheet |

Bestehende Desktop-Testids bleiben unverändert.

## Expected Behavior

- **Input:** Aufruf `/compare/new` oder `/compare/[id]/edit` auf Viewport ≤899px als eingeloggter Nutzer.
- **Output:** Mobiles Layout mit scrollbarer Tab-Bar, Progress-Bar (Create-Modus), Lock-Toast bei gesperrtem Tab-Tap, Bottom-Sheet für Orts-Bibliothek, Floating-CTA; Desktop ≥900px byte-identisch.
- **Side effects:** Keine neuen — Persistenz-Pfad identisch zu Desktop (`user_id` aus Auth-Kontext, kein `"default"`-Fallback; mandantengetrennt).

## Acceptance Criteria

**AC-1:** Given ein eingeloggter Nutzer öffnet `/compare/new` auf ≤899px Viewport / When die Seite geladen ist / Then zeigt eine obere App-Leiste den Titel des aktiven Tabs als Haupttitel und den Vergleichs-Namen (oder „Neuer Vergleich") als Eyebrow, eine horizontale scrollbare Tab-Bar mit mindestens 44px Höhe und eine Progress-Segmentleiste — während die Desktop-Breadcrumb-Zeile nicht sichtbar ist; bei ≥900px ist nur das Desktop-Layout sichtbar.
  - Test: Playwright @375×667, `/compare/new` — `cm-mobile-appbar` sichtbar, Desktop-Breadcrumb `display:none` (computed); `cm-mobile-tabbar boundingBox().height ≥ 44`; @1280 umgekehrt.

**AC-2:** Given `/compare/new` auf ≤899px, ein Tab ist gesperrt (z.B. „Orte" ohne Vergleichs-Namen) / When der Nutzer den gesperrten Tab antippt / Then erscheint ein Toast-Hinweis mit dem Lock-Grund für ~2s und der aktive Tab wechselt nicht; die Tab-Bar ist horizontal scrollbar ohne horizontalen Page-Overflow.
  - Test: Playwright @375 — Tap auf `cm-mobile-tab-orte` (Name leer) → `Toast` sichtbar mit hint-Text; `activeTab` bleibt „vergleich"; `document.body.scrollWidth ≤ innerWidth + 1`.

**AC-3:** Given `/compare/new` auf ≤899px, Tab „Orte" ist freigeschaltet / When der Nutzer auf „Ort aus Bibliothek wählen" tippt / Then öffnet sich ein Bottom-Sheet (`snap="full"`) mit der vollen Orts-Bibliothek als Liste mit Checkboxen; Antippen einer Checkbox schaltet den Ort in `wiz.pickedIds` um; Schließen des Sheets zeigt den aktualisierten Zähler.
  - Test: Playwright @375 — Tab „Orte" öffnen (Vergleichs-Name eingeben) → `compare-step2-mobile-library-btn` tippen → Sheet sichtbar → `compare-step2-mobile-lib-check-{id}` tippen → Sheet schließen → `pickedIds`-Zähler im Tab-Inhalt aktualisiert.

**AC-4:** Given `/compare/new` auf ≤899px, Tab ist vollständig ausgefüllt / When der Nutzer den Floating-CTA „Weiter" tippt / Then wechselt `activeTab` zum nächsten Tab; auf dem letzten Tab (Versand) heißt der CTA „Aktivieren" und ruft `handleActivate()` auf; im Edit-Modus (`/compare/[id]/edit`) gibt es keinen Floating-CTA, stattdessen „Speichern" in der App-Leiste (orange bei Änderungen, grau ohne Änderungen).
  - Test: Playwright @375 — Create-Modus: CTA-Btn sichtbar, Tap bei ausgefülltem Tab → `activeTab` wechselt; Edit-Modus: CTA-Div fehlt, `cm-mobile-save` sichtbar, ohne Änderungen grau, nach Änderung orange.

**AC-5:** Given `/compare/new` auf ≤899px, Nutzer A füllt Vergleichs-Name + ≥2 Orte + besucht alle Tabs / When Nutzer „Aktivieren" (App-Leiste oder CTA) tippt / Then wird der Compare-Preset mit `user_id` von Nutzer A angelegt — kein `"default"`-Fallback; ein zweiter Nutzer B sieht diesen Preset nicht; Persistenz byte-identisch zu Desktop.
  - Test: Playwright @375 gegen Staging — als Nutzer A vollständigen Create-Flow durchführen → POST `/api/compare/presets` mit korrekter `user_id`; als Nutzer B einloggen → Preset nicht sichtbar.

## Known Limitations

- **L1 — Tab-Inhalte auf Mobile:** Die Step-Komponenten (Step1–Step5) rendern ihr
  **Desktop-Markup auch auf Mobile** (nur das Wrapper-Padding unterscheidet sich durch den
  mobilen Tab-Inhalts-Container). Dieser Slice bringt nur die Gerüst-Ebene (App-Leiste,
  Tab-Bar, Progress, CTA) — keine interne Step-Restyling-Arbeit außer Step2Orte (Bibliothek-Sheet).
  Überlaufen Step-Inhalte auf 375px, ist das ein Folge-Issue, nicht im Scope dieses Slices.
- **L2 — Lock-Icon in Tab-Bar:** Das `🔒`-Emoji ist Platzhalter; falls das Design-System ein
  eigenes Lock-Icon vorschreibt, ist das eine 1-Zeilen-Änderung nach Implementierung.
- **L3 — doneTabs-Props-Übergabe:** Der `doneTabs()`-Aufruf im Progress-Bar-Block benötigt
  dieselben Argumente wie der `unlocked`-`$derived`-Block in CompareEditor. Der Developer
  soll die bestehende `unlocked`-Variable ableiten statt `doneTabs()` doppelt aufzurufen.

## Changelog

- 2026-06-10: Initiale Spec erstellt (Issue #682, Epic #677, Slice 5/6). Mobile-Parität für CompareEditor (CSS-only-Switch #661-Pattern), Lock-Toast, Progress-Bar, Floating-CTA, Bibliothek-Sheet in Step2Orte.
