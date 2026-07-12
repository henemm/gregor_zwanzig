---
entity_id: layout_tab_route
type: feature
created: 2026-07-12
updated: 2026-07-12
status: draft
workflow: feat-1232-layout-tab-3b
---

# LayoutTab (route) — geteilter Layout-Organism im Trip-Editor — Scheibe 3b (letztes Stück von #1232)

- **Issue:** #1232 (Phase 4 — Editor-Konsolidierung, Sub-Issue von Epic #1230) · Scheibe 3b von 2 (LETZTE Scheibe)
- **Vorgänger:** Scheibe 1 (`docs/specs/modules/versand_tab_route.md`, live) · Scheibe 2a (`docs/specs/modules/compare_preset_zeitplan.md`, live) · Scheibe 2b (`docs/specs/modules/versand_tab_vergleich.md`, live) · Scheibe 3a (`docs/specs/modules/layout_tab_vergleich.md`, live — geteilte Primitiva `shared/layout-tab/` + Compare-Editor)
- **Design-Quelle (1:1, strukturell):** `claude-code-handoff/current/jsx/layout-tab.jsx` (370 Z., route-Zweig `LT_RoutePreview`/`LT_RouteOrderDense`) + `soll-29b-desktop-layout-route.png`
- **Typ:** Frontend-Refactor, rein `frontend/src` — kein Datenmodell-/Backend-Change, keine Verhaltensänderung der Wetter-Daten selbst

## Approval

- [ ] Approved

## Purpose

Der Trip-Editor bekommt den zweiten und letzten Teil des in Scheibe 3a
gebauten geteilten Layout-Organism `LayoutTab` (`context="route"`). Er
ersetzt den bisherigen Ausgabe-Teil des Wetter-Metriken-Tabs — das
`.v2-layout`-Grid aus Reihenfolge (`WeatherV2Reihenfolge`) und
Live-Mail-Vorschau (`WeatherV2MailPreview`, inkl. deren INTERNEN
Kanal-Tabs) — durch die geteilte Zwei-Spalten-Shell mit dem geteilten
Kanal-Picker (`LTChannelPicker`), dem geteilten Kappungs-Hinweis
(`LTCapNote`) und der geteilten Cut-Line (`LTCutLine`). Die Metrik-AUSWAHL
(01 Preset, 02 Grundauswahl) sowie die darunterliegenden Karten
(SMS-Schwellwerte, Mail-Inhalt, Amtliche-Warnungen) bleiben unverändert
Trip-eigen. Damit ist die Kappungs-Logik (Email ∞ · Telegram 8 · SMS
flach) für BEIDE Editoren auf eine einzige Quelle (`CHANNEL_COL_BUDGET`)
konsolidiert, und #1232 ist vollständig umgesetzt.

## Source

- **Files:**
  - `frontend/src/lib/components/trip-detail/WeatherMetricsTab.svelte` — MODIFY (888 Z.)
  - `frontend/src/lib/components/trip-detail/WeatherV2Reihenfolge.svelte` — MODIFY
  - `frontend/src/lib/components/trip-detail/WeatherV2MailPreview.svelte` — MODIFY
  - `frontend/e2e/layout-tab-route.spec.ts` — CREATE
  - `frontend/src/lib/components/shared/layout-tab/{LayoutTab,LTChannelPicker,LTCapNote,LTCutLine}.svelte`, `ltChannels.ts` — KEEP, unverändert konsumiert (Scheibe 3a)
  - `frontend/src/lib/components/trip-detail/metricsEditor.ts` (`CHANNEL_COL_BUDGET`, `buildWeatherConfigMetrics`, `move`, `diffHighlight`) — KEEP, unverändert referenziert
- **Identifier:** `<LayoutTab context="route">` (Svelte-Component-Verwendung in `WeatherMetricsTab.svelte`), `function onDndReorder`, `function onMode`, `function onRemove` (bestehende Handler, `WeatherMetricsTab.svelte`)

## Expected Behavior

- **Input:** Der Nutzer öffnet den Wetter-Metriken-Tab eines Trips. Oben
  sieht er unverändert 01 — Profil (Preset) und 02 — Grundauswahl.
  Darunter sieht er den geteilten Layout-Bereich: links Kanal-Picker
  (Email/Telegram/SMS mit Badges ∞/8/—) + Reihenfolge (Drag & Drop,
  Roh/Einfach-Segmented, "Aus"-Button je Metrik), rechts die Live-Vorschau.
  Er klickt einen Kanal-Button ODER zieht eine Metrik-Zeile um ODER
  schaltet eine Zeile auf "Einfach"/"Roh" ODER entfernt eine Metrik ODER
  öffnet mobil den FAB "So kommt es an".
- **Output:** Ein Kanal-Klick ist ein reiner Ansichtswechsel ohne
  Datenänderung: er schaltet gleichzeitig (a) ob die Cut-Line
  ("✂ ab hier Telegram-Limit …") in der Reihenfolge sichtbar ist (nur bei
  Kanal Telegram, an Position `CHANNEL_COL_BUDGET.telegram` = 8) und (b)
  welches Vorschau-Template rechts gerendert wird (Email-Tabelle ↔
  Telegram-Bubble ↔ SMS-Zeile) — die zuvor in `WeatherV2MailPreview`
  eingebauten internen Kanal-Tabs sind entfallen, der geteilte
  `LTChannelPicker` übernimmt diese Rolle allein. Reihenfolge-Bearbeitung
  (Drag & Drop, Modus-Wechsel, Entfernen) verhält sich exakt wie vor
  dieser Scheibe: sie ändert `buckets.primary`/`friendlyMap`, löst den
  Diff-Highlight (2,5 s) aus und triggert den bestehenden debounced
  Auto-Save (`saveController.schedule` → `PUT /api/trips/{id}/weather-config`
  + `PUT /api/trips/{id}`); nach einem Seiten-Reload sind die Änderungen
  weiterhin sichtbar. SMS-Schwellwerte (04), Mail-Inhalt-Karte und
  Amtliche-Warnungen-Checkbox bleiben unterhalb des geteilten Bereichs
  unverändert bedienbar und lösen wie bisher Auto-Save aus. Mobil öffnet
  der FAB "So kommt es an" weiterhin ein Bottom-Sheet mit derselben
  Vorschau-Komponente — sie folgt jetzt dem im (eingeklappten oder
  sichtbaren) Kanal-Picker gewählten Kanal statt eines fest verdrahteten
  `'email'`.
- **Side effects:** Der Kanal (`channel`) ist reiner UI-View-State ohne
  Persistenz — er geht NIE in `snapshot()`/`isDirty` ein (analog zu
  Scheibe 3a: ein reiner Kanalwechsel macht den Tab NICHT dirty und löst
  KEINEN Auto-Save aus). Die Kappungs-Konsolidierung ändert keine
  sichtbaren Zahlenwerte in der Vorschau (Telegram bleibt bei 8 Spalten,
  Email bleibt unbegrenzt) — nur die Quelle der Zahl (jetzt ausschließlich
  `CHANNEL_COL_BUDGET` über `ltChannels.ts`, bereits in Scheibe 3a
  konsolidiert) und der Ort der Kappungs-Anzeige (geteilte Primitiva statt
  duplizierter Markup-/Text-Logik in `WeatherV2Reihenfolge`/
  `WeatherV2MailPreview`).

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `docs/specs/modules/layout_tab_vergleich.md` (Scheibe 3a, live) | module | Liefert die geteilten Primitiva (`LayoutTab`, `LTChannelPicker`, `LTCapNote`, `LTCutLine`, `ltChannels.ts`) — diese Scheibe konsumiert sie unverändert, keine erneute Implementierung |
| `frontend/src/lib/components/trip-detail/metricsEditor.ts` (`CHANNEL_COL_BUDGET`, `buildWeatherConfigMetrics`, `move`, `diffHighlight`, `indicatorCapable`) | module | Bleibt die Kern-Editor-Logik des Trip-Editors, unverändert genutzt — `LayoutTab` ist reine Hülle darum |
| `docs/specs/modules/versand_tab_route.md` (Scheibe 1, live) | module | Versand-Tab (Kanal ein/aus je Trip) bleibt strukturell getrennt — kein Layout-Bezug, außerhalb dieser Scheibe |
| Epic #1231 (Korridor-Editor) | workflow | Tab-Umbenennung „Wertebereiche" und Korridor-Editor sind explizit NICHT Teil dieser Scheibe (Out of Scope, KL-4/KL-5) |
| `frontend/e2e/epic-138-metriken-editor.spec.ts`, `epic-138-block-b.spec.ts`, `issue-736/723/619/343/690/1117/932`-Specs | tests | Regressionsgates — bestehende Selektoren (`wm2-*`, `weather-metrics-*`, `sms-thresholds`, `report-mail-content`, `report-show-official-alerts`) müssen unverändert grün bleiben |
| Compare-Editor (`context="vergleich"`, Scheibe 3a) | module | Bleibt vollständig unberührt — diese Scheibe ändert keine Compare-Dateien |

## Scope

### Affected Files

| File | Change Type | Description |
|------|-------------|-------------|
| `frontend/src/lib/components/trip-detail/WeatherMetricsTab.svelte` | MODIFY | Restrukturierung des Ausgabe-Teils: 01 Preset + 02 Grundauswahl bleiben oben unverändert; das bisherige `.v2-layout`-Grid (Reihenfolge + Vorschau) wird ersetzt durch `<LayoutTab context="route" bind:channel={activeChannel} colCount={buckets.primary.length + 1} subjectLabel="Metriken">` mit `WeatherV2Reihenfolge` im `editor`-Snippet (erhält `activeChannel={channel}` statt hartkodiert `"telegram"`) und `WeatherV2MailPreview` im `preview`-Snippet (erhält `channel={channel}` statt eigenem internen State); neuer lokaler `activeChannel` $state (`ChannelId`, Default `'email'`) — reiner View-State, geht NICHT in `snapshot()`/`isDirty` ein; SMS-Schwellwerte (04), `EditReportConfigSection` und die Amtliche-Warnungen-Checkbox bleiben unverändert einspaltig darunter; Mobile-FAB+Sheet erhält zusätzlich `channel={activeChannel}` für die Sheet-Instanz von `WeatherV2MailPreview`; CSS-Override versteckt die `LayoutTab`-Vorschau-Spalte im mobilen Breakpoint (ersetzt das bisherige `.preview-col{display:none}`) |
| `frontend/src/lib/components/trip-detail/WeatherV2Reihenfolge.svelte` | MODIFY | Die eigene, inline gebaute Cut-Line-Markup wird durch die geteilte `LTCutLine`-Komponente ersetzt (`label="Telegram"`, `max={tgBudget}`), gewrappt in ein Element mit `data-testid="wm2-cut-line"` (Testid bleibt am Wrapper erhalten, `LTCutLine` liefert zusätzlich intern `data-testid="lt-cut-line"`); die `activeChannel`-Prop-Signatur bleibt unverändert — sie kommt jetzt vom `channel`-Snippet-Parameter des `LayoutTab` statt vom bisherigen hartkodierten String `"telegram"` in `WeatherMetricsTab` |
| `frontend/src/lib/components/trip-detail/WeatherV2MailPreview.svelte` | MODIFY | Der interne `activeChannel`-`$state` und das zugehörige `.ch-tabs`-Markup (Kanal-Buttons + CSS) entfallen vollständig; neue Prop `channel: ChannelId` (controlled) steuert stattdessen, welches Template (Email/Telegram/SMS) gerendert wird; alle bestehenden `wm2-*`-Testids (`wm2-mail-preview`, `wm2-sample-badge`, `wm2-diff-banner`, `wm2-email-table`, `wm2-telegram-bubble`, `wm2-sms-line`) bleiben unverändert erhalten |
| `frontend/e2e/layout-tab-route.spec.ts` | CREATE | Verhaltens-Playwright: Kanal-Picker-Wechsel schaltet Vorschau-Template + Cut-Line-Sichtbarkeit; Reihenfolge-DnD + Auto-Save + Reload-Beweis; reiner Kanalwechsel macht NICHT dirty; Mobile FAB+Sheet folgt dem gewählten Kanal; Desktop + Mobile (`:visible`) |
| `frontend/src/lib/components/shared/layout-tab/{LayoutTab,LTChannelPicker,LTCapNote,LTCutLine}.svelte`, `ltChannels.ts` | KEEP | Aus Scheibe 3a unverändert konsumiert — kein Rework nötig, Snippet-Slot-Schnitt bereits kontextfähig |
| `frontend/e2e/epic-138-metriken-editor.spec.ts`, `epic-138-block-b.spec.ts`, `issue-736-tabs-reorg.spec.ts`, `issue-723-email-tab-eindampfen.spec.ts`, `issue-619-mail-elements-ui.spec.ts`, `issue-343-horizon-chips.spec.ts`, `issue-1117-official-alerts-content-tab.spec.ts`, `issue-932-activity-type-route-tab.spec.ts` | KEEP | Regressionsgates — geprüft: keiner dieser Specs klickt die bisherigen internen `WeatherV2MailPreview`-Kanal-Tabs (`.ch-tab`/`data-channel` im Mail-Preview-Kontext), daher kein Navigations-Schritt anzupassen; Selektoren unverändert |

### Estimated Changes

- Files: ~4 geänderte/neue Dateien (3 MODIFY, 1 CREATE) + 5 unveränderte Primitiva aus Scheibe 3a konsumiert + 8 Regressions-Specs unangetastet
- LoC (Produktivcode ohne Tests): ~150–220 (Restrukturierung `WeatherMetricsTab.svelte` inkl. CSS-Anpassung, Cut-Line-Wrapper in `WeatherV2Reihenfolge.svelte`, Entfernen der internen Kanal-Tabs + neue Prop in `WeatherV2MailPreview.svelte`)
- LoC Tests (zusätzlich): ~150–200 (neuer Playwright `layout-tab-route.spec.ts`)
- Effort: medium-high — Trip-Tab hat die dichteste Test-Abdeckung des Projekts (epic-138-Specs) und den produktiven Auto-Save-Pfad; `channel` darf unter keinen Umständen in `snapshot()`/`isDirty` durchsickern

## Implementation Details

### 1. `WeatherMetricsTab.svelte` — Restrukturierung

```
01 — Profil (WeatherV2PresetBar)          ← unverändert, oben
02 — Grundauswahl (WeatherV2Grundauswahl) ← unverändert, oben
<LayoutTab context="route"
           bind:channel={activeChannel}
           colCount={buckets.primary.length + 1}
           subjectLabel="Metriken">
  {#snippet editor({ channel })}
    <WeatherV2Reihenfolge primaryColumns={buckets.primary} {metricById}
      {friendlyMap} activeChannel={channel} {highlight}
      {onRemove} {onDndReorder} {onMode}/>
  {/snippet}
  {#snippet preview({ channel })}
    <WeatherV2MailPreview primaryColumns={buckets.primary} {metricById}
      {friendlyMap} {telegramKurzform} {highlight} {channel}/>
  {/snippet}
</LayoutTab>
04 — Schwellwerte (sms-thresholds)        ← unverändert, darunter
EditReportConfigSection (report-mail-content) ← unverändert, darunter
Amtliche Warnungen (report-show-official-alerts) ← unverändert, darunter
```

`activeChannel` ist ein neuer lokaler `$state<ChannelId>('email')` in
`WeatherMetricsTab.svelte` — reiner View-State, TAUCHT NICHT in
`snapshot()`/`isDirty` auf (analog zur bereits in Scheibe 3a getroffenen
Entscheidung für den Compare-Editor). Das bisherige `.v2-layout`-Grid
(Z. 510 ff.) entfällt für den Ausgabe-Teil; die darunterliegenden Karten
(04, Mail-Inhalt, Official-Toggle) bleiben in einer eigenen, einspaltigen
`editor-col`-artigen Struktur bestehen (kein Bezug zum `LayoutTab`).

Mobile FAB+Sheet (KL-1, bleibt): Der bestehende FAB "So kommt es an" und
das `Sheet` bleiben unverändert im Markup; die darin gemountete zweite
`WeatherV2MailPreview`-Instanz erhält zusätzlich `channel={activeChannel}`
— sie folgt damit demselben Kanal, den der Nutzer im (inline sichtbaren)
`LTChannelPicker` gewählt hat, statt fest auf `'email'` zu stehen.

CSS: Die `LayoutTab`-eigene Vorschau-Spalte (`.lt-col-preview`) wird im
mobilen Breakpoint (`max-width: 899px`) per globalem Selektor in
`WeatherMetricsTab.svelte` versteckt (`:global(.layout-tab[data-context="route"] .lt-col-preview) { display: none; }`)
— das ersetzt das bisherige `.preview-col { display: none; }` und erhält
das etablierte Muster: Editor-Spalte (inkl. Kanal-Picker + Reihenfolge)
bleibt mobil sichtbar, die inline Vorschau weicht dem FAB+Sheet.

### 2. `WeatherV2Reihenfolge.svelte` — Cut-Line über geteiltes Primitiv

Die bisherige inline `<div class="cut-line" data-testid="wm2-cut-line">…</div>`-
Markup wird ersetzt durch:

```svelte
{#if showCutLine && i === tgBudget}
  <div data-testid="wm2-cut-line">
    <LTCutLine label="Telegram" max={tgBudget}/>
  </div>
{/if}
```

Der Text ("✂ ab hier Telegram-Limit (max 8)") und die Optik (gestrichelte
Warnlinie) kommen jetzt 1:1 aus `LTCutLine` (bereits in Scheibe 3a
gebaut, bisher von keiner UI konsumiert — diese Scheibe ist der erste
Konsument, KL-1 aus Scheibe 3a wird hiermit aufgelöst). Das äußere
`data-testid="wm2-cut-line"` bleibt für bestehende Tests erhalten; das
eigene `.cut-line`-CSS in `WeatherV2Reihenfolge.svelte` entfällt.

### 3. `WeatherV2MailPreview.svelte` — controlled `channel`-Prop

Entfernt: lokaler `let activeChannel = $state('email')` sowie das
`.ch-tabs`-Markup (Kanal-Buttons mit `data-channel`) inkl. CSS
(`.ch-tabs`, `.ch-tab`, `.ch-tab.on`, `.overflow-badge`). Neu:

```ts
interface Props {
  primaryColumns: string[];
  metricById: Record<string, MetricEntry>;
  friendlyMap: Record<string, boolean>;
  telegramKurzform: boolean;
  highlight: Highlight | null;
  channel: ChannelId; // NEU — controlled, ersetzt internen State
}
```

Alle Stellen, die bisher `activeChannel` lasen (Template-Auswahl
Email/Telegram/SMS, Overflow-Berechnung), lesen stattdessen die
`channel`-Prop. Das `sample-badge` "Beispieldaten" sowie sämtliche
`wm2-*`-Testids bleiben unverändert an derselben Stelle im DOM.

### 4. Kein Rework der Primitiva aus Scheibe 3a

`LayoutTab.svelte`, `LTChannelPicker.svelte`, `LTCapNote.svelte`,
`LTCutLine.svelte` und `ltChannels.ts` werden unverändert übernommen —
der `context`/`channel`/`colCount`/`subjectLabel`/`editor`/`preview`-
Schnitt aus Scheibe 3a ist bereits so allgemein, dass der route-Kontext
ohne Änderung an der Hülle andockt. Das bestätigt die in Scheibe 3a
getroffene Design-Entscheidung, den Organism kontextfähig, aber
zustandsarm zu schneiden.

## Test Plan

### Automated Tests (TDD RED)

- [ ] Playwright (`layout-tab-route.spec.ts`): GIVEN der Wetter-Metriken-Tab ist offen WHEN Email→Telegram→SMS im `LTChannelPicker` geklickt wird THEN wechselt die Vorschau von `wm2-email-table` zu `wm2-telegram-bubble` zu `wm2-sms-line`, ohne dass die alten internen `.ch-tab`-Buttons im DOM existieren.
- [ ] Playwright (`layout-tab-route.spec.ts`): GIVEN mehr als 8 aktive Metriken WHEN der Kanal Telegram aktiv ist THEN erscheint `wm2-cut-line` an Position 9 der Reihenfolge UND der `channel-tab-telegram`-Button zeigt den Overflow-Chip „−n".
- [ ] Playwright (`layout-tab-route.spec.ts`): GIVEN die Reihenfolge WHEN eine Metrik-Zeile per Drag & Drop verschoben wird THEN ändert sich die Spaltenreihenfolge in der Email-Vorschau UND nach einem Seiten-Reload ist die neue Reihenfolge weiterhin aktiv (Auto-Save-Beweis).
- [ ] Playwright (`layout-tab-route.spec.ts`): GIVEN der Tab ist gespeichert (nicht dirty) WHEN nur der Kanal im `LTChannelPicker` gewechselt wird THEN bleibt `weather-metrics-dirty-pill` unsichtbar und es wird KEIN Auto-Save-Request ausgelöst.
- [ ] Playwright (`layout-tab-route.spec.ts`): GIVEN eine Metrik wird per "Aus"-Button entfernt oder auf "Einfach" umgeschaltet THEN funktioniert dies wie vor dieser Scheibe UND `weather-metrics-dirty-pill` erscheint bzw. Auto-Save greift.
- [ ] Playwright (`layout-tab-route.spec.ts`): GIVEN Mobile-Viewport WHEN der FAB "So kommt es an" geklickt wird THEN öffnet sich das Bottom-Sheet mit der Vorschau des zuvor im Kanal-Picker gewählten Kanals, und der Tab hat keinen horizontalen Scroll (`scrollWidth <= clientWidth`).
- [ ] Playwright (`layout-tab-route.spec.ts`): GIVEN SMS-Schwellwerte, Mail-Inhalt-Karte und Amtliche-Warnungen-Checkbox WHEN sie unterhalb des Layout-Bereichs bedient werden THEN funktionieren `sms-thresholds`, `report-mail-content`, `report-show-official-alerts` unverändert.
- [ ] Playwright (bestehend, `epic-138-metriken-editor.spec.ts` + `epic-138-block-b.spec.ts`, unverändert): bleiben grün — keine Anpassung an Selektoren nötig.
- [ ] Playwright (bestehend, `issue-736/723/619/343/690/1117/932`-Specs, unverändert): bleiben grün.

### Fixtures

- Kern-Schicht: keine neuen node:test-Fixtures nötig (`CHANNEL_COL_BUDGET`, `ltBadge`, `ltOverflow` bereits in Scheibe 3a getestet und unverändert wiederverwendet).
- Playwright: Staging, echter Trip via `/api/trips` (kein Mock) — analog `epic-138-metriken-editor.spec.ts`.

## Acceptance Criteria

**AC-1:** Given der Wetter-Metriken-Tab eines Trips ist geöffnet / When der Tab betrachtet wird / Then zeigt er oberhalb unverändert 01 — Profil und 02 — Grundauswahl, darunter den geteilten Layout-Bereich mit Kanal-Picker (Badges ∞/8/—, Overflow-Chip) links und der Live-Vorschau rechts.
  - Test: Playwright prüft Reihenfolge der Sektionen im DOM sowie Sichtbarkeit von `lt-channel-picker` und der Vorschau-Spalte.

**AC-2:** Given der Kanal-Picker ist sichtbar / When zwischen Email, Telegram und SMS gewechselt wird / Then schaltet die Vorschau (`wm2-email-table` ↔ `wm2-telegram-bubble` ↔ `wm2-sms-line`) um, die alten internen Vorschau-Tabs (`.ch-tab`) existieren nicht mehr, alle `wm2-*`-Testids bleiben unverändert.
  - Test: Playwright klickt jeden Kanal, prüft das jeweils sichtbare Template und die Abwesenheit der alten `.ch-tab`-Buttons.

**AC-3:** Given die Reihenfolge-Bearbeitung (Drag & Drop, Roh/Einfach-Modus, Entfernen) / When eine dieser Aktionen ausgeführt wird / Then funktioniert sie exakt wie vor dieser Scheibe und der Auto-Save persistiert die Änderung nachweisbar über einen Seiten-Reload.
  - Test: Playwright führt DnD/Modus-Wechsel/Entfernen aus, reloadet die Seite und prüft den persistierten Zustand.

**AC-4:** Given mehr aktive Metriken als das Telegram-Budget (8) / When der Kanal Telegram aktiv ist / Then erscheint die Cut-Line an der Budget-Grenze in der Reihenfolge, und die Kappungs-Quelle bleibt ausschließlich `CHANNEL_COL_BUDGET` (über `ltChannels.ts`).
  - Test: Playwright prüft `wm2-cut-line` an Index 8 sowie den Overflow-Chip im Kanal-Picker bei >8 aktiven Metriken.

**AC-5:** Given SMS-Schwellwerte, Mail-Inhalt-Karte und Amtliche-Warnungen-Checkbox / When sie unterhalb des geteilten Layout-Bereichs bedient werden / Then bleiben sie unverändert funktionsfähig, testid-stabil (`sms-thresholds`, `report-mail-content`, `report-show-official-alerts`).
  - Test: Playwright bedient je einen Schwellwert, die Mail-Inhalt-Karte und die Checkbox und prüft Persistenz/Sichtbarkeit.

**AC-6:** Given der Tab ist gespeichert (nicht dirty) / When ausschließlich der Kanal im Kanal-Picker gewechselt wird / Then bleibt der Tab nicht-dirty (`weather-metrics-dirty-pill` unsichtbar) und es wird kein Auto-Save-Request ausgelöst.
  - Test: Playwright wechselt den Kanal mehrfach und prüft die Abwesenheit von `weather-metrics-dirty-pill` sowie Netzwerk-Requests.

**AC-7:** Given ein Mobile-Viewport / When der FAB "So kommt es an" geklickt wird / Then öffnet sich das Bottom-Sheet mit der Vorschau des zuvor gewählten Kanals, und der Tab ist einspaltig ohne horizontalen Scroll.
  - Test: Playwright im Mobile-Viewport wählt einen Kanal, öffnet den FAB, prüft das gezeigte Vorschau-Template im Sheet und `scrollWidth <= clientWidth`.

**AC-8:** Given die bestehenden Testids und Regressions-Specs (`wm2-*`, `weather-metrics-*`, `sms-thresholds`, `report-mail-content`, `report-show-official-alerts`, `epic-138-*`, `issue-736/723/619/343/690/1117/932`) / When die Seite gerendert bzw. die Specs ausgeführt werden / Then existieren die Testids unverändert und alle genannten Bestands-Specs bleiben grün.
  - Test: Playwright-Regressionslauf der genannten Specs, unverändert grün.

**AC-9:** Given die Umsetzung ist fertig / When Diff und API-Endpunkte geprüft werden / Then ist ausschließlich `frontend/src`/`frontend/e2e` verändert — keine Compare-Editor-Datei, kein Backend, kein Datenmodell.
  - Test: Diff-Review — nur die in Scope gelisteten Dateien verändert.

**AC-10:** Given der Compare-Editor (`context="vergleich"`, Scheibe 3a) / When diese Scheibe abgeschlossen ist / Then verhält er sich unverändert — keine Datei aus Scheibe 3a wurde angefasst.
  - Test: Diff-Review — keine Änderung an `Step4Layout.svelte`, `LTComparePreview.svelte` oder weiteren 3a-Dateien.

## Known Limitations

- **KL-1 · Trip-Mobile behält FAB+Bottom-Sheet:** statt der im Design gezeigten dense-Inline-Vorschau bleibt das getestete #618-Muster (FAB "So kommt es an" + Bottom-Sheet) bestehen; die Sheet-Vorschau folgt dem im Kanal-Picker gewählten Kanal.
- **KL-2 · Reihenfolge bleibt DnD ohne Pfeiltasten:** das JSX (`LT_RouteOrderDense`) zeigt Auf/Ab-Pfeiltasten — das ist Design-Altstand vor #848 (DnD ersetzte die Pfeiltasten bereits produktiv); die controlled-Props (`onDndReorder`/`onMode`/`onRemove`) bilden die echte Code-Realität ab, nicht die JSX-Signatur (`onMove`/`onReorder`).
- **KL-3 · `LT_RouteOrderDense` aus dem JSX wird nicht übernommen:** Trip-Mobile nutzt dieselbe DnD-Liste (`WeatherV2Reihenfolge`) wie Desktop, keine separate kompakte Pfeiltasten-Variante.
- **KL-4 · SMS-Schwellwerte/Mail-Inhalt/Official-Toggle bleiben unterhalb im Tab:** sie sind nicht Teil des `LayoutTab`-Designs; ein Zieltab „Wertebereiche" existiert noch nicht (#1231-Materie).
- **KL-5 · Tab-Umbenennungen weiterhin ausgelassen:** „Wertebereiche" etc. bleiben #1231-Materie, bewusst nicht Teil dieser Scheibe.
- **KL-6 · LoC-Schätzung ~300–400 (Produktivcode + Tests):** über dem 250-LoC-Standardlimit. Override wird vor Phase 6 explizit beim PO eingeholt (`workflow.py set-field loc_limit_override`), nicht eigenmächtig gesetzt.

## Edge Cases

| Fall | Verhalten |
|---|---|
| >8 aktive Metriken bei Kanal Telegram | `LTChannelPicker` zeigt Overflow-Chip „−n"; `wm2-cut-line` erscheint in der Reihenfolge an Index 8 |
| 0 aktive Metriken (`buckets.primary` leer) | Reihenfolge zeigt eine leere Liste, Vorschau zeigt eine Tabelle ohne Spalten (bestehendes Verhalten, unverändert) |
| `telegramKurzform`-Suffix aktiv + Telegram-Overflow | Der Tages-Max-Suffix in `WeatherV2MailPreview` erscheint unverändert unterhalb der gekappten Telegram-Tabelle |
| Doppel-Mount `TripNewEditor` (Desktop + Mobile, `createMode`) | `activeChannel`-View-State lebt pro `WeatherMetricsTab`-Instanz getrennt (analog KL-5 aus Scheibe 3a); kein Save-Pfad im `createMode` (unverändert) |

## Out of Scope

- Epic #1231 (Korridor-Editor, Tab-Umbenennung „Wertebereiche" etc.).
- Datenmodell-Vereinheitlichung von Trip- (Single-Column) und Compare-Layout (Bucket-Modell) — bleibt bewusst getrennt.
- Compare-Editor (`context="vergleich"`) — vollständig unberührt, Scheibe 3a bleibt Referenz.
- Mail-Renderer / echter Versand-Content (Vorschau bleibt statisch mit Beispieldaten, wie vor dieser Scheibe).

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** keine
- **Rationale:** Abschluss des in Scheibe 1 etablierten und in Scheibe 3a fortgeführten Organism-Musters (geteilte Komponente mit `context`-Prop und Snippet-Slots) — keine neue Architekturentscheidung, reine Anwendung des bereits gebauten, kontextfähigen Organism auf den zweiten (letzten) Editor.

## Test-Nachweis

- Kern: keine neuen node:test-Fixtures nötig — bestehende `ltChannels.test.ts`/`channelChipCount.test.ts` aus Scheibe 3a bleiben unverändert grün als Commit-Gate.
- RED-Phase: FE-Testdateien sind per `edit_gate` in RED gesperrt (mark-red-Mechanismus).
- Staging-E2E (`/60-validate`): Playwright gegen einen echten Trip (kein Mock), Tab-Klick-Pfad, `:visible`; Fresh-Eyes gegen `soll-29b-desktop-layout-route.png`.
- Mail-Renderer/Mail-Validator sind NICHT betroffen (kein Renderer-Datei-Touch in dieser Scheibe) — Renderer-Commit-Gate #811 greift nicht.

## Changelog

- 2026-07-12: Initial spec created
