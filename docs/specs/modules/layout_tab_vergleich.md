---
entity_id: layout_tab_vergleich
type: feature
created: 2026-07-12
updated: 2026-07-12
status: draft
workflow: feat-1232-layout-tab
---

# LayoutTab (vergleich) — geteilter Layout-Organism + Primitiva — Scheibe 3a/3b

- **Issue:** #1232 (Phase 4 — Editor-Konsolidierung, Sub-Issue von Epic #1230) · Scheibe 3a von 2 (3b = route folgt als eigener Workflow)
- **Vorgänger:** Scheibe 1 (`docs/specs/modules/versand_tab_route.md`, live) · Scheibe 2a (`docs/specs/modules/compare_preset_zeitplan.md`, live) · Scheibe 2b (`docs/specs/modules/versand_tab_vergleich.md`, live — `CompareInhaltSection` als Zwischenlösung)
- **Nachfolger:** Scheibe 3b (`context="route"` im `WeatherMetricsTab`, eigener Workflow — dockt an die hier gebauten Primitiva an)
- **Design-Quelle (1:1):** `claude-code-handoff/current/jsx/layout-tab.jsx` (370 Z., vergleich-Zweig `LT_ComparePreview`/`LT_CompareOrderList`) + `soll-29b-desktop-layout-vergleich.png`
- **Typ:** Frontend-Refactor, rein `frontend/src` — kein Datenmodell-/Backend-Change

## Approval

- [ ] Approved

## Purpose

Der Compare-Editor bekommt den ersten Teil des geteilten Layout-Organism
`LayoutTab` (`context="vergleich"`). Er ersetzt die bisherigen Kanal-Tabs von
`Step4Layout.svelte` (`CE_CHANNELS`) sowie die Vorschau-Komponente
`LayoutPreview.svelte` durch geteilte Primitiva (`shared/layout-tab/`) und
eine neue, design-treue Vorschau `LTComparePreview`, die Orte als Spalten
statt als Zeilen zeigt und — anders als der Bestand — keinen Rang, keinen
Score und kein Empfehlungs-Banner mehr rendert (Design-Prinzip C1: der
Orts-Vergleich ist neutral, keine Werbung für einen "Gewinner"-Ort). Die
Kappungs-Logik (Email ∞ · Telegram 8 · SMS flach) wird dabei auf eine
einzige Quelle (`CHANNEL_COL_BUDGET`) konsolidiert — bisher existierte sie
in vier Varianten. Das Bucket-Modell des bestehenden `OutputLayoutEditor`
bleibt als Editor-Slot unverändert bestehen (keine Datenmodell-Vereinheitlichung
mit dem Trip-Editor — das ist bewusst Scheibe 3b vorbehalten).

## Source

- **Files:**
  - `frontend/src/lib/components/shared/layout-tab/ltChannels.ts` — NEU
  - `frontend/src/lib/components/shared/layout-tab/LTChannelPicker.svelte` — NEU
  - `frontend/src/lib/components/shared/layout-tab/LTCapNote.svelte` — NEU
  - `frontend/src/lib/components/shared/layout-tab/LTCutLine.svelte` — NEU
  - `frontend/src/lib/components/shared/layout-tab/LayoutTab.svelte` — NEU
  - `frontend/src/lib/components/shared/layout-tab/LTComparePreview.svelte` — NEU
  - `frontend/src/lib/components/compare/steps/Step4Layout.svelte` — MODIFY (mountet `LayoutTab`)
  - `frontend/src/lib/components/compare/LayoutPreview.svelte` — DELETE
  - `frontend/src/lib/components/compare/CompareTabs.svelte` — MODIFY (Kappungs-Konsolidierung)
  - `frontend/src/lib/components/molecules/CompareChatBubble.svelte` — MODIFY (Kappungs-Konsolidierung)
  - `frontend/src/lib/components/shared/versand-tab/VTBriefingChannels.svelte` — MODIFY (Text-Interpolation)
  - `frontend/src/lib/components/trip-detail/metricsEditor.ts` — Quelle `CHANNEL_COL_BUDGET`/`channelOverflow` (unverändert, nur referenziert)
- **Identifier:** `function LayoutTab` (Svelte-Component), `export const LT_CHANNELS`, `export function ltOverflow`, `class Step4Layout` (Svelte-Component)

## Expected Behavior

- **Input:** Im Layout-Tab des Compare-Editors klickt der Nutzer einen der
  drei Kanal-Buttons (Email/Telegram/SMS) im geteilten `LTChannelPicker`.
  Zusätzlich beeinflusst die aktuelle Orts-Auswahl (`wizard.pickedIds`) die
  Spaltenzahl der Vorschau.
- **Output:** Der Klick schaltet gleichzeitig (a) die Kappung des
  `OutputLayoutEditor` (Bucket-Modell bleibt unverändert je Kanal) und (b)
  das gerenderte Vorschau-Template um: Email zeigt eine volle Tabelle
  (Orte als Spalten, alle Metrik-Zeilen inkl. Sonnenstunden), Telegram
  dieselbe Tabelle mit Kappungs-Chip "−n" sobald mehr als 8 Spalten
  (Label + Orte) nötig wären, SMS zeigt Fließtext mit Zeichenzähler statt
  einer Tabelle. Werte im nutzerdefinierten Idealbereich erscheinen grün,
  ohne Rang/Score/Empfehlung. Bei 0 gewählten Orten erscheint der Hinweis
  "Keine Orte ausgewählt — zurück zu „Orte"." statt eines Crashs.
- **Side effects:** Die Kanal-Auswahl ist reiner UI-View-State ohne
  Persistenz und ohne eigenen Save-Effekt (`LayoutTab` ist zustandsarm und
  save-frei) — sie divergiert zwischen dem Desktop- und dem Mobile-Mount
  von `Step4Layout` wie heute (KL-5, akzeptiert). Das Bucket-Modell
  (Spalte/Detail/Aus, Reihenfolge, Presets) persistiert unverändert über
  den zentralen `CompareEditor`-Save-Pfad (`channel_layouts`). Die
  Kappungs-Konsolidierung ändert keine sichtbaren Zahlenwerte in den
  Vergleichs-Kacheln (`CompareTabs.svelte`) oder der Telegram-Bubble
  (`CompareChatBubble.svelte`) — nur die Quelle der Zahl wechselt.

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `docs/specs/modules/versand_tab_vergleich.md` (Scheibe 2b, live) | module | `CompareInhaltSection` bleibt unverändert am Ende von `Step4Layout` gemountet — kein Layout-Bezug, außerhalb dieser Scheibe |
| `frontend/src/lib/components/trip-detail/metricsEditor.ts` (`CHANNEL_COL_BUDGET`, `channelOverflow`) | module | Kanonische Kappungs-Quelle (Email ∞ · Telegram 8 · SMS 0) — `ltChannels.ts` leitet `LT_CHANNELS` direkt daraus ab, keine eigene Zahl |
| `frontend/src/lib/components/shared/OutputLayoutEditor.svelte` | module | Bleibt unverändert der Editor-Slot für `context="vergleich"` (Bucket-Modell, Presets, Detail-Pills) — KEIN Ersatz durch `LT_CompareOrderList` (KL-2) |
| `frontend/src/lib/components/compare/layoutPreviewRows.ts` (`selectPreviewRows`) | module | Wird von `LTComparePreview` weiterverwendet (Crash-Guard #1093, statische Demo-Zeilen skaliert auf `pickedIds.length`) |
| `frontend/src/lib/components/compare/channelChipCount.ts` | module | Bleibt unverändert (`Math.min(budget, locationCount)`) — nur der übergebene `budget`-Wert in `CompareTabs.svelte` wechselt von `99` auf `CHANNEL_COL_BUDGET.email` (`Infinity`), Ergebnis bleibt für alle real vorkommenden Orts-Anzahlen identisch |
| Epic #1231 (Korridor-Editor) | workflow | Tab-Umbenennung „Wertebereiche" und Korridor-Editor sind explizit NICHT Teil dieser Scheibe (Out of Scope, KL-4) |
| Scheibe 3b (`context="route"`, eigener Workflow) | workflow | Konsumiert dieselben Primitiva (`ltChannels.ts`, `LTChannelPicker`, `LTCapNote`, `LTCutLine`, `LayoutTab`) für den Trip-Editor — `LTCutLine` wird in 3a gebaut, aber noch von keiner UI konsumiert (KL-1) |

## Scope

### Affected Files

| File | Change Type | Description |
|------|-------------|-------------|
| `frontend/src/lib/components/shared/layout-tab/ltChannels.ts` | CREATE | `LT_CHANNELS`/`LT_CH_BY_ID` (Kappung aus `CHANNEL_COL_BUDGET` abgeleitet, `note`-Texte 1:1 aus dem JSX), `ltBadge(max)` (∞/8/—), `ltOverflow(colCount)` (Partial-Record der überschreitenden Spaltenzahl je Kanal, komplementär zu `channelOverflow` — dieses liefert Booleans für den Trip-Kontext, `ltOverflow` liefert die Zahl für den Chip) |
| `frontend/src/lib/components/shared/layout-tab/LTChannelPicker.svelte` | CREATE | Kanal-Umschalter; `data-testid="channel-tab-{id}"` UND `data-channel={id}` (bestehende Compare-Selektoren überleben); Badge via `ltBadge`; Overflow-Chip "−n" via `ltOverflow` |
| `frontend/src/lib/components/shared/layout-tab/LTCapNote.svelte` | CREATE | Kappungs-Hinweis unter der Reihenfolge/dem Bucket-Editor (1:1-Text-Logik aus JSX `LT_CapNote`: "passt"/"zu breit — max N, weiter vorne = sicherer") |
| `frontend/src/lib/components/shared/layout-tab/LTCutLine.svelte` | CREATE | Geteilte Trennlinie "✂ ab hier {Kanal}-Limit (max {N})" — als Primitiv jetzt gebaut (Auftrag Punkt 1), in 3a von keiner Vergleichs-UI konsumiert (die Vergleichs-Vorschau nutzt weiterhin die bestehenden Detail-Pills für Überlauf), Konsument ist Scheibe 3b (KL-1) |
| `frontend/src/lib/components/shared/layout-tab/LayoutTab.svelte` | CREATE | Organism: `context`-Prop (`'route' \| 'vergleich'`), `channel`-`$bindable` (Default `email`), `colCount`/`subjectLabel`-Props (Aufrufer liefert die kontextspezifische Zählung), Zwei-Spalten-Shell (Desktop) / Stapel (dense), Eyebrows „Kanal · Vorschau & Kappung" / „So kommt es an · {Kanal}", `editor`- und `preview`-Snippet-Props als Slots — zustandsarm und save-frei (kein `$effect`, keine Persistenz) |
| `frontend/src/lib/components/shared/layout-tab/LTComparePreview.svelte` | CREATE | NEUBAU design-treu: Orte als SPALTEN, Metrik-Zeilen (Schnee/Neuschnee/Wind-Böen/Temp gef., + Sonne nur bei Email), Idealbereichs-Treffer grün, KEIN Rang/Score/Empfehlungs-Banner (C1); Header „Übersicht · {Zeitraum}" + Zeile „…grün… Kein Ranking."; SMS-Zweig: alle gewählten Orte (bis 3) nacheinander als Fließtext + Zeichenzähler; explizite Empty-State-Weiche bei `pickedIds.length === 0` (JSX-Text „Keine Orte ausgewählt — zurück zu „Orte".", VOR dem Aufruf von `selectPreviewRows`, das bei leerer Auswahl sonst alle Dummy-Zeilen zurückgäbe); nutzt `selectPreviewRows` weiter; Testids `compare-step4-layout-preview` + `compare-step4-preview-sms` wandern 1:1 |
| `frontend/src/lib/components/shared/layout-tab/ltChannels.test.ts` | CREATE | node:test — `LT_CHANNELS`-Ableitung aus `CHANNEL_COL_BUDGET`, `ltBadge`, `ltOverflow` |
| `frontend/src/lib/components/compare/steps/Step4Layout.svelte` | MODIFY | `CE_CHANNELS`-Konstante + Kanal-Tabs-Markup (Z.49-53, Z.301-331) + zugehöriges CSS raus; mountet `<LayoutTab context="vergleich" bind:channel={activeChannel} colCount={activeAllCols.length} subjectLabel={...}>` mit `OutputLayoutEditor` (Bucket-Modell + Handler + Detail-Pills funktional unverändert) im `editor`-Snippet und `LTComparePreview` im `preview`-Snippet; `$effect`-Persistenz nach `wizard.channelLayouts` bleibt unverändert in `Step4Layout`; `CompareInhaltSection` bleibt am Ende gemountet |
| `frontend/src/lib/components/compare/LayoutPreview.svelte` | DELETE | Verletzt C1 aktiv (Rang-Badges, Score-Spalte, Empfehlungs-Banner) — vollständig ersetzt durch `LTComparePreview` |
| `frontend/src/lib/components/compare/CompareTabs.svelte` | MODIFY | `CHANNEL_COLS` (Z.104, `email: 99`) → `CHANNEL_COL_BUDGET` aus `metricsEditor.ts` importiert (`email: Infinity`); `channelChipCount`-Aufruf unverändert (Ergebnis für alle real vorkommenden Orts-Anzahlen identisch, da `Math.min(Infinity, N) === N === Math.min(99, N)` für jedes praktisch vorkommende `N < 99`) |
| `frontend/src/lib/components/molecules/CompareChatBubble.svelte` | MODIFY | `MAXCOLS` (Z.44, `{ telegram: 8 }`) → `CHANNEL_COL_BUDGET.telegram` aus `metricsEditor.ts` |
| `frontend/src/lib/components/shared/versand-tab/VTBriefingChannels.svelte` | MODIFY | `SUB.telegram`-Text (Z.80, hartkodiert `'Layout · 8 Spalten'`) → Interpolation `` `Layout · ${CHANNEL_COL_BUDGET.telegram} Spalten` `` |
| `frontend/src/lib/components/compare/channelChipCount.test.ts` | MODIFY | Testbeschreibungen/Werte, die den alten Literal-Wert `99` als Email-Budget verwenden, auf `Infinity` umgestellt (Verhalten identisch: `channelChipCount(Infinity, N) === N`) |
| `frontend/src/lib/components/compare/layoutPreviewRows.test.ts` | KEEP | Bleibt unverändert — `selectPreviewRows` wird unverändert von `LTComparePreview` weiterverwendet |
| `frontend/e2e/compare-editor-slice4.spec.ts` | MODIFY | AC-1/AC-3-Assertions auf die neutrale Spalten-Vorschau angepasst (kein `.recommendation-banner`, kein Rang-Badge, Text enthält „Kein Ranking"; SMS-Text-Längentoleranz angepasst an "alle Orte nacheinander"); Selektoren selbst (`channel-tab-*`, `compare-step4-layout-preview`, `compare-step4-preview-sms`) unverändert |
| `frontend/e2e/issue-1093-compare-layout-crash.spec.ts` | KEEP | Muss grün bleiben (kein Code-Change nötig) — Crash-Guard-Mechanismus (`selectPreviewRows`) unverändert weiterverwendet |
| `frontend/e2e/layout-tab-vergleich.spec.ts` | CREATE | Verhaltens-Playwright: Kanal-Wechsel email→telegram→sms — Badge-Wechsel, Overflow-Chip bei >8 Orten, Vorschau-Template-Wechsel (Tabelle→Fließtext), Empty-State bei 0 Orten, Desktop+Mobile (`:visible`) |

### Estimated Changes

- Files: ~15 (6 neue Primitiva + 1 neuer Unit-Test, 5 modifizierte Bestandsdateien, 1 gelöschte Datei, 2 Test-Dateien)
- LoC (Produktivcode ohne Tests): ~380–450 (6 neue Komponenten/Module + Step4Layout-Umbau + 3 Kappungs-Konsolidierungs-Edits)
- LoC Tests (zusätzlich): ~170–220 (node:test `ltChannels.test.ts`, angepasste `channelChipCount.test.ts`, neuer/erweiterter Playwright)
- Effort: medium-high — geteilte Primitiva müssen so geschnitten sein, dass Scheibe 3b (route) sie ohne Rework konsumieren kann; zwei bestehende E2E-Suiten (`compare-editor-slice4`, `issue-1093-compare-layout-crash`) dürfen nicht brechen

## Implementation Details

### 1. `ltChannels.ts` — einzige Kappungs-Quelle für die Primitiva

```ts
import { CHANNEL_COL_BUDGET } from '$lib/components/trip-detail/metricsEditor';

export type ChannelId = 'email' | 'telegram' | 'sms';

export const LT_CHANNELS: { id: ChannelId; label: string; max: number; note: string }[] = [
  { id: 'email', label: 'Email', max: CHANNEL_COL_BUDGET.email,
    note: 'alle Spalten · kein Limit' },
  { id: 'telegram', label: 'Telegram', max: CHANNEL_COL_BUDGET.telegram,
    note: 'max 8 Spalten' },
  { id: 'sms', label: 'SMS', max: CHANNEL_COL_BUDGET.sms,
    note: 'kein Raster · ≤ 140 Zeichen' },
];
export const LT_CH_BY_ID = Object.fromEntries(LT_CHANNELS.map((c) => [c.id, c]));

export function ltBadge(max: number): string {
  return max === Infinity ? '∞' : max === 0 ? '—' : String(max);
}

export function ltOverflow(colCount: number): Partial<Record<ChannelId, number>> {
  const result: Partial<Record<ChannelId, number>> = {};
  for (const ch of LT_CHANNELS) {
    if (ch.max === Infinity || ch.max === 0) continue;
    if (colCount > ch.max) result[ch.id] = colCount - ch.max;
  }
  return result;
}
```

`ltOverflow` dupliziert nicht `channelOverflow` aus `metricsEditor.ts` — letzteres
liefert Booleans für den (Trip-)Dirty-Check bei einer einzigen `primaryCount`,
`ltOverflow` liefert die überschreitende Zahl für den Chip im `LTChannelPicker`.
Beide leiten aus derselben `CHANNEL_COL_BUDGET`-Quelle ab.

### 2. `LayoutTab.svelte` — Hülle, keine Datenmodell-Vereinheitlichung

```
Props: context: 'route' | 'vergleich'
       channel = $bindable('email')
       dense?: boolean
       colCount: number        // Aufrufer liefert die kontextspezifische Zaehlung
       subjectLabel: string    // z.B. "4 Orte" (vergleich) — Metriken (route, Scheibe 3b)
       editor: Snippet<[{ channel: ChannelId }]>
       preview: Snippet<[{ channel: ChannelId }]>
```

Rendert die geteilte Zwei-Spalten-Shell (Desktop `grid-template-columns:
minmax(380px,1fr) minmax(380px,1.1fr)`, dense/mobile gestapelt), die Eyebrows
„Kanal · Vorschau & Kappung" (links) und „So kommt es an · {Kanal-Label}"
(rechts), den `LTChannelPicker` (bindet `channel`), ruft `{@render
editor({channel})}` + `LTCapNote` darunter und `{@render preview({channel})}`
rechts. Keine `$effect`, kein Save-Aufruf — reiner Präsentations-Organism.
Der `context`-Prop steuert in dieser Scheibe nur `data-context`-Attribut am
Root (für 3b reserviert); die eigentliche Editor-/Preview-Logik kommt
vollständig aus den Snippet-Props des Aufrufers (`Step4Layout` übergibt
`OutputLayoutEditor` + `LTComparePreview`).

### 3. `Step4Layout.svelte` — Umbau

`CE_CHANNELS` und das Kanal-Tabs-Markup (inkl. `.channel-tab*`-CSS) entfallen.
`activeChannel` (weiterhin lokaler `$state`) wird per `bind:channel` an
`LayoutTab` durchgereicht — die bestehenden Handler (`handleMove`,
`handleReorder`, `handleDndReorder`, `handleMode`, `handleSelectPreset`,
`bucketsForChannel`, der `$effect` nach `wizard.channelLayouts`) bleiben
unverändert, da sie bereits auf `channelBuckets[activeChannel]` etc.
operieren. `OutputLayoutEditor` (inkl. Detail-Pills-Logik, Testid
`layout-editor`, `compare-step4-detail-pill-{i}`) wandert unverändert in
das `editor`-Snippet; `LTComparePreview` ersetzt die bisherige
`LayoutPreview`-Instanz im `preview`-Snippet. `CompareInhaltSection` bleibt
unverändert am Ende von `Step4Layout` gemountet (2b-Scope, kein
Layout-Bezug).

### 4. `LTComparePreview.svelte` — Orte als Spalten (Design-Neubau)

Ersetzt `LayoutPreview.svelte` vollständig. Kernunterschied zum Bestand:
Bestand rendert Orte als ZEILEN mit Rang-Badge (#1/#2/#3), Score-Spalte und
einem "Empfehlung"-Banner ("weil X cm Schnee..."). Das verletzt aktiv das
Design-Prinzip C1 (Orts-Vergleich ist neutral, keine Werbung für einen
"Gewinner"). Der Neubau zeigt stattdessen:

- Header: Eyebrow „Übersicht · {Zeitraum}" + Zeile „Werte nebeneinander —
  grün = in deinem Idealbereich. Kein Ranking."
- Tabelle: erste Spalte „Metrik" (Zeilenlabel), je gewähltem Ort eine
  weitere Spalte (Ortsname als Spaltenkopf). Zeilen: Schnee, Neuschnee,
  Wind/Böen, Temp gef., + Sonne nur bei `channel === 'email'`. Zellen mit
  Idealbereichs-Treffer (JSX-Schwellen: `snow>=80`, `newSnow>=10`,
  `wind<=30`, `feels` zwischen -8 und 2, `sun>=3`) werden grün + fett.
- Footer: „Email · alle Metrik-Zeilen + Stunden je Ort" bzw. „Telegram ·
  Label + {N} Orte = {N+1} Spalten (max 8)".
- SMS-Zweig: Fließtext über alle gewählten Orte (bis zu 3) nacheinander
  (`GZ {Zeitraum}: Ort1 Werte · Ort2 Werte · Ort3 Werte`) + Zeichenzähler
  darunter (mono, `{n} Zeichen · keine Tabelle — alle Orte nacheinander,
  ohne Rangfolge.`) statt der bisherigen Beschränkung auf `rows[0]`.
- Empty-State: WENN `pickedIds.length === 0` wird VOR dem Aufruf von
  `selectPreviewRows` der Hinweis „Keine Orte ausgewählt — zurück zu
  „Orte"." gerendert (dashed Rahmen, wie im JSX). Das ist eine zusätzliche
  Absicherung ÜBER dem bestehenden Crash-Guard von #1093
  (`selectPreviewRows` selbst gibt bei 0 `pickedIds` unverändert alle
  Dummy-Zeilen zurück — das bleibt für den Fall unverändert, dass die
  Komponente ohne den expliziten Empty-State-Zweig eingebunden würde, z. B.
  in einem künftigen Testkontext).
- Datenquelle: statische Demo-Zeilen (KL-3, kein API-Call) via
  `selectPreviewRows(pickedIds, DUMMY_LOCATIONS)` — unverändert
  wiederverwendet, keine Änderung an `layoutPreviewRows.ts`.

Testids `compare-step4-layout-preview` (Wrapper) und
`compare-step4-preview-sms` (SMS-Block) wandern 1:1 aus `LayoutPreview.svelte`.

### 5. Kappungs-Konsolidierung

`CompareTabs.svelte:104` (`CHANNEL_COLS.email: 99`),
`CompareChatBubble.svelte:44` (`MAXCOLS.telegram: 8`) und
`VTBriefingChannels.svelte:80` (`SUB.telegram` Text-Literal `8 Spalten`)
werden auf `CHANNEL_COL_BUDGET` aus `metricsEditor.ts` umgestellt (Import,
kein neuer Wert). `channelChipCount.test.ts` wird angepasst, da es bislang
den Literal-Wert `99` als "Email-Budget" in Testbeschreibungen und
Aufrufen verwendet — Verhalten (`Math.min(budget, locationCount)`) bleibt
identisch, da `Math.min(Infinity, N) === N === Math.min(99, N)` für jede
praktisch vorkommende Orts-Anzahl `N < 99`.

## Test Plan

### Automated Tests (TDD RED)

- [ ] node:test (`ltChannels.test.ts`): GIVEN `CHANNEL_COL_BUDGET` WHEN `LT_CHANNELS` gelesen wird THEN sind `email.max === Infinity`, `telegram.max === 8`, `sms.max === 0` (keine eigene Zahl, reine Ableitung).
- [ ] node:test (`ltChannels.test.ts`): GIVEN `ltBadge` WHEN mit `Infinity`/`0`/`8` aufgerufen THEN liefert es `'∞'`/`'—'`/`'8'`.
- [ ] node:test (`ltChannels.test.ts`): GIVEN `ltOverflow(10)` WHEN ausgewertet THEN enthält das Ergebnis `{ telegram: 2 }` und KEINEN `email`/`sms`-Schlüssel; GIVEN `ltOverflow(5)` THEN ist das Ergebnis ein leeres Objekt.
- [ ] node:test (`channelChipCount.test.ts`, angepasst): GIVEN `CHANNEL_COL_BUDGET.email === Infinity` WHEN `channelChipCount(Infinity, 8)` aufgerufen wird THEN ist das Ergebnis `8` (identisch zum bisherigen `channelChipCount(99, 8)`).
- [ ] Playwright (`layout-tab-vergleich.spec.ts`): GIVEN der Layout-Tab ist offen WHEN Email→Telegram→SMS geklickt wird THEN zeigen die Badges `∞`/`8`/`—` und die Vorschau wechselt von Tabelle (Email/Telegram) zu Fließtext (SMS), Desktop UND Mobile (`:visible`).
- [ ] Playwright (`layout-tab-vergleich.spec.ts`): GIVEN >8 gewählte Orte (Telegram-Budget überschritten) WHEN der Telegram-Kanal aktiv ist THEN zeigt der Telegram-Button den Overflow-Chip „−n" mit `n = Spaltenzahl - 8`.
- [ ] Playwright (`layout-tab-vergleich.spec.ts`): GIVEN 0 gewählte Orte WHEN der Layout-Tab betrachtet wird THEN zeigt die Vorschau den Hinweis „Keine Orte ausgewählt" statt eines Crashs oder leerer Tabelle.
- [ ] Playwright (`layout-tab-vergleich.spec.ts`): GIVEN die neutrale Vorschau ist sichtbar WHEN der DOM geprüft wird THEN existiert KEIN Rang-Badge (`#1`), KEINE Score-Spalte, KEIN Empfehlungs-Banner-Element, aber der Text „Kein Ranking" ist vorhanden.
- [ ] Playwright (`compare-editor-slice4.spec.ts`, angepasst): AC-1/AC-3 prüfen die Spalten-Vorschau (Orte als Spaltenköpfe) statt der alten Zeilen-Struktur; bestehende Selektoren unverändert.
- [ ] Playwright (`issue-1093-compare-layout-crash.spec.ts`, unverändert): bleibt grün — Crash-Guard-Mechanismus unverändert wiederverwendet.

### Fixtures

- Kern-Schicht: node:test ohne Browser/Netz (reine Funktionen: `ltBadge`, `ltOverflow`, `channelChipCount`, `selectPreviewRows`).
- Playwright: Staging, echte Preset-Anlage via `/api/compare/presets` mit echten Bibliotheks-Orten (kein Mock) — analog `issue-1093-compare-layout-crash.spec.ts`.

## Acceptance Criteria

**AC-1:** Given der Layout-Tab des Compare-Editors ist geöffnet / When ich den Kanal-Picker betrachte / Then zeigt er die drei Kanäle mit Kappungs-Badges `∞` (Email), `8` (Telegram), `—` (SMS), und bei Telegram-Überlauf (mehr Spalten als 8) einen zusätzlichen Overflow-Chip „−n".
  - Test: Playwright prüft Badge-Text je Kanal-Button und den Overflow-Chip bei >8 gewählten Orten.

**AC-2:** Given der Layout-Tab ist offen / When ich zwischen Email, Telegram und SMS wechsle / Then schaltet sowohl die Kappung des Bucket-Editors als auch das Vorschau-Template um (Email: Tabelle mit allen Spalten inkl. Sonne; Telegram: Tabelle gekappt auf 8 Spalten; SMS: Fließtext ohne Tabelle).
  - Test: Playwright klickt jeden Kanal, prüft Vorhandensein/Abwesenheit von `<table>` und die jeweilige Spaltenzahl.

**AC-3:** Given die Vorschau ist sichtbar / When der DOM geprüft wird / Then sind die Orte als SPALTEN dargestellt (nicht als Zeilen), es gibt keinen Rang, keinen Score und kein Empfehlungs-Banner; Werte im Idealbereich sind grün markiert.
  - Test: Playwright — kein `.recommendation-banner`/Rang-Badge-Element, Header-Text enthält „Kein Ranking", mindestens eine grün markierte Zelle bei entsprechenden Demo-Werten.

**AC-4:** Given eine unterschiedliche Anzahl gewählter Orte (`wizard.pickedIds`) / When der Layout-Tab betrachtet wird / Then passt sich die Spaltenzahl der Vorschau entsprechend an, und bei 0 gewählten Orten erscheint der Hinweis „Keine Orte ausgewählt" statt eines Crashs oder einer leeren Tabelle.
  - Test: Playwright variiert die Orts-Auswahl (0/1/mehrere) und prüft die resultierende Spaltenzahl bzw. den Empty-State-Text.

**AC-5:** Given der Bucket-Editor (Spalte/Detail/Aus, Reihenfolge, Presets) / When ich Metriken verschiebe, umsortiere oder ein Preset wähle und speichere / Then funktioniert das exakt wie vor dieser Scheibe und persistiert unverändert über den zentralen Save (`display_config.channel_layouts`).
  - Test: Playwright — bestehende `compare-editor-slice4.spec.ts`-Assertions zu Bucket-Verschiebung/Preset/Persistenz bleiben grün.

**AC-6:** Given die Kappungswerte existieren jetzt nur noch an einer Quelle (`CHANNEL_COL_BUDGET`) / When die Vergleichs-Kacheln (`CompareTabs.svelte`) oder die Telegram-Bubble (`CompareChatBubble.svelte`) gerendert werden / Then zeigen sie unverändert dieselben korrekten Zahlenwerte wie vor der Konsolidierung.
  - Test: node:test (`channelChipCount.test.ts`) + Playwright-Sichtprüfung der Kachel-Chip-Zahlen unverändert.

**AC-7:** Given die bestehenden Testids `channel-tab-*`, `compare-step4-layout-preview`, `compare-step4-preview-sms`, `compare-step4-detail-pill-*`, `layout-editor`, `compare-step5-*` (der `CompareInhaltSection`) / When die Seite gerendert ist / Then existieren sie unverändert (nur anderer interner Aufbau).
  - Test: Playwright — dieselben Selektoren wie vor dieser Scheibe funktionieren weiterhin.

**AC-8:** Given Desktop UND Mobile (Doppel-Mount `.cm-desktop`/`.cm-mobile`) / When der Layout-Tab in beiden Ansichten genutzt wird / Then verhält er sich konsistent, mobil einspaltig gestapelt ohne horizontales Scrollen.
  - Test: Playwright prüft `:visible`-Selektoren in beiden Mount-Instanzen sowie `scrollWidth <= clientWidth` im Mobile-Viewport.

**AC-9:** Given die Umsetzung ist fertig / When man API-Endpunkte und Datenmodell vergleicht / Then ist keine Backend-/API-/Datenmodell-Änderung vorgenommen worden (rein `frontend/src`).
  - Test: Diff-Review — nur Dateien unterhalb `frontend/src`/`frontend/e2e` verändert.

**AC-10:** Given der Trip-Editor (`context="route"`, `WeatherMetricsTab`) / When diese Scheibe abgeschlossen ist / Then verhält er sich unverändert — Scheibe 3b (route) ist noch nicht umgesetzt.
  - Test: Diff-Review — keine Änderung an `WeatherMetricsTab.svelte`, `WeatherV2Reihenfolge.svelte`, `WeatherV2MailPreview.svelte`.

## Known Limitations

- **KL-1 · route-Kontext folgt in Scheibe 3b:** `LayoutTab` ist strukturell `context`-fähig (Prop-Typ `'route' | 'vergleich'`), aber der route-Zweig rendert in dieser Scheibe noch nichts — kein Konsument im `WeatherMetricsTab` bindet ihn an. `LTCutLine` wird als Primitiv bereits jetzt gebaut, aber von keiner Vergleichs-UI konsumiert (Konsument ist 3b).
- **KL-2 · `LT_CompareOrderList` aus dem JSX wird NICHT übernommen:** Der bestehende `OutputLayoutEditor` (Bucket-Modell, Presets, Detail-Pills) ist funktional reicher und bereits testgedeckt — er bleibt der Editor-Slot für `context="vergleich"`. Keine Datenmodell-Vereinheitlichung mit dem route-Editor.
- **KL-3 · Vorschau nutzt weiterhin statische Beispieldaten:** Kein API-Call, wie im Bestand (`DUMMY_LOCATIONS`/`selectPreviewRows`) — echte Live-Vorschau ist nicht Gegenstand dieser Scheibe.
- **KL-4 · Tab-Umbenennungen NICHT Teil dieser Scheibe:** „Idealwerte" → „Wertebereiche" etc. gehören zu Epic #1231 (Korridor-Editor), bewusst ausgelassen.
- **KL-5 · Kanal-Auswahl (View-State) divergiert zwischen Desktop-/Mobile-Mount:** Wie heute — `activeChannel` lebt lokal in jeder `Step4Layout`-Instanz, kein geteilter Zustand zwischen `.cm-desktop` und `.cm-mobile`. Akzeptiert, kein neuer Bug.
- **KL-6 · LoC-Limit überschritten:** ~380–450 LoC Produktivcode + ~170–220 LoC Tests — über dem 250-LoC-Standardlimit. Grund: sechs neue geteilte Primitiva müssen bereits für Scheibe 3b tragfähig geschnitten sein, plus Kappungs-Konsolidierung über vier Bestandsdateien. Override wird vor Phase 6 explizit beim PO eingeholt (`workflow.py set-field loc_limit_override`), nicht eigenmächtig gesetzt.

## Edge Cases

| Fall | Verhalten |
|---|---|
| 0 gewählte Orte (`pickedIds.length === 0`) | Vorschau zeigt Empty-State „Keine Orte ausgewählt — zurück zu „Orte"." statt Tabelle oder Crash |
| >8 gewählte Orte bei Telegram | `LTChannelPicker` zeigt Overflow-Chip „−n"; Vorschau-Footer weist auf das 8er-Limit hin; Editor kappt wie bisher via `OutputLayoutEditor` |
| SMS-Kanal | Kein Raster/Tabelle — Fließtext mit allen gewählten Orten (bis 3) nacheinander + Zeichenzähler |
| genau 1 gewählter Ort | Vorschau zeigt eine einzelne Orts-Spalte, kein Sonderfall-Rendering |
| Doppel-Mount Desktop/Mobile, Kanalwechsel | Jede `LayoutTab`-Instanz hat ihren eigenen `channel`-View-State (KL-5) — Wechsel in einer Instanz wirkt sich nicht auf die andere aus |

## Out of Scope

- Scheibe 3b: `context="route"` im `WeatherMetricsTab` (eigener Workflow).
- Tab-Umbenennungen („Wertebereiche" etc., Epic #1231).
- Korridor-Editor / Idealbereichs-Konfiguration selbst (nur die bestehenden `ideal_ranges` werden in der Vorschau gelesen, nicht editiert).
- Datenmodell-Vereinheitlichung von Trip- und Compare-Layout (Bucket-Modell bleibt getrennt vom künftigen route-Modell).
- Mail-Renderer / echter Versand-Content (Vorschau bleibt statisch, KL-3).

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** keine
- **Rationale:** Fortführung des in Scheibe 1 etablierten Organism-Musters (geteilte Komponente mit `context`-Prop, hier zusätzlich mit Snippet-Slots für kontextspezifische Editor-/Preview-Inhalte) — keine neue Architekturentscheidung, nur Anwendung des bestehenden Musters auf einen weiteren Tab.

## Test-Nachweis

- Kern: node:test (`ltChannels.test.ts`, angepasstes `channelChipCount.test.ts`, kein Netz/Browser) — 100% grün als Commit-Gate.
- RED-Phase: FE-Testdateien sind per `edit_gate` in RED gesperrt (mark-red-Mechanismus).
- Staging-E2E (`/60-validate`): Playwright gegen echten Compare-Preset (kein Mock), Tab-Klick-Pfad, `:visible`; Fresh-Eyes gegen `soll-29b-desktop-layout-vergleich.png`.
- Mail-Renderer/Mail-Validator sind NICHT betroffen (kein Renderer-Datei-Touch in dieser Scheibe) — Renderer-Commit-Gate #811 greift nicht.

## Changelog

- 2026-07-12: Initial spec created
- 2026-07-12 (nach Freigabe, Adversary-Fund F003): Spec-interner Widerspruch aufgelöst — Expected Behavior + Out of Scope („nutzerdefinierte ideal_ranges werden in der Vorschau GELESEN") sind verbindlich; die statischen „JSX-Schwellen" in Implementation Details §4 waren fehlerhaft übernommener Design-Demo-Stand. Umsetzung: Vorschau liest `wizard.idealRanges` (Prop-Durchreiche via Step4Layout), Fallback auf Demo-Schwellen nur für Metriken ohne konfigurierten Range (dokumentiert). Kein AC geändert.
