---
entity_id: issue_587_metrics_editor_fidelity
type: module
created: 2026-06-04
updated: 2026-06-04
status: implemented
version: "1.0"
tags: [frontend, svelte, metrics-editor, design-fidelity, ui, trip-detail]
parent_epic: 587
implementation_date: 2026-06-04
---

<!-- Issue #587 — [L] Design-Fidelity: Metrics-Editor 1:1 nach screen-metrics-editor.jsx -->

# Issue #587 — Design-Fidelity: Metrics-Editor 1:1 nach screen-metrics-editor.jsx

## Approval

- [ ] Approved

## Purpose

Bringt den Metrics-Editor (Trip-Detail-Tab "Wetter-Metriken") in vollständige Übereinstimmung mit dem bindenden JSX-SOLL `screen-metrics-editor.jsx`. Es gibt drei konkrete Abweichungen: `TablePreview.svelte` existiert, wird aber in `WeatherMetricsTab.svelte` nicht eingebunden; `SavePresetDialog.svelte` nutzt eine shadcn `<Dialog>`-Komponente statt des im JSX definierten custom Fixed-Overlays mit Blur-Backdrop; und mehrere Style-Details in `BucketSection`, `ChannelPreviewBlock` und dem Editor-Header weichen von den JSX-Inline-Styles ab. Ohne diese Fidelity-Korrekturen ist der Editor funktional vollständig, aber visuell nicht auf dem Stand des freigegebenen Designs.

## Source

- **File:** `frontend/src/lib/components/trip-detail/WeatherMetricsTab.svelte` (modifiziert — `TablePreview` einbinden)
- **File:** `frontend/src/lib/components/trip-detail/SavePresetDialog.svelte` (modifiziert — Custom-Overlay statt shadcn Dialog)
- **File:** `frontend/src/lib/components/trip-detail/TablePreview.svelte` (modifiziert — Header-Stil-Audit gegen JSX)
- **File:** `frontend/src/lib/components/trip-detail/ChannelPreviewBlock.svelte` (modifiziert — Style-Audit)
- **File:** `frontend/src/lib/components/shared/OutputLayoutEditor.svelte` (modifiziert — Style-Audit)
- **Identifier:** `WeatherMetricsTab`, `SavePresetDialog`, `TablePreview`, `ChannelPreviewBlock`, `OutputLayoutEditor`

> **Schicht-Hinweis:** Diese Spec betrifft ausschließlich die Frontend-Schicht (SvelteKit unter `frontend/src/`). Kein Backend-Eingriff. Die Abhängigkeiten `TablePreview.svelte`, `horizonHelpers.ts`, `Horizons`-Typ und `POST /api/metric-presets` sind bereits live aus Issue #343/#342.

## Estimated Scope

- **LoC:** ~180
- **Files:** 5
- **Effort:** medium

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `TablePreview.svelte` (`frontend/src/lib/components/trip-detail/TablePreview.svelte`) | Bestehende Komponente (aus #343) | Wird in `WeatherMetricsTab` unterhalb von BucketSection "Detail-Werte" eingebunden; empfängt `catalog`, `enabledMap`, `friendlyMap`, `horizonsMap`, `categoryOrder`, `indicatorCapable` |
| `WeatherMetricsTab.svelte` (`frontend/src/lib/components/trip-detail/WeatherMetricsTab.svelte`) | Eltern-Komponente | Übergabepunkt für `TablePreview`; liefert State und Props |
| `SavePresetDialog.svelte` (`frontend/src/lib/components/trip-detail/SavePresetDialog.svelte`) | Modifizierte Komponente | Ersetzt shadcn `<Dialog>` durch custom Fixed-Overlay gemäß JSX-SOLL |
| `$lib/components/ui/dialog/index.js` (shadcn Dialog) | Zu entfernende Abhängigkeit | Wird aus `SavePresetDialog.svelte` herausgelöst; Import wird gelöscht |
| `ChannelPreviewBlock.svelte` (`frontend/src/lib/components/trip-detail/ChannelPreviewBlock.svelte`) | Modifizierte Komponente | Style-Token-Audit gegen `screen-metrics-editor.jsx` und `screen-channel-preview-redesign.jsx` |
| `OutputLayoutEditor.svelte` (`frontend/src/lib/components/shared/OutputLayoutEditor.svelte`) | Modifizierte Komponente | Style-Audit gegen JSX-Inline-Styles; wird nur angepasst falls Abweichungen gefunden |
| `frontend/src/lib/types.ts` | Typ-Quelle | `Horizons`-Typ, `HORIZONS_ALL`-Const (aus #342/#343, keine Änderung) |
| `frontend/src/lib/utils/horizonHelpers.ts` | Utility | `computeHorizonSummary`, `dotsForHorizons` (aus #343, keine Änderung) |
| `POST /api/metric-presets` | Backend-API | Preset-Speicherung — wird von `SavePresetDialog` aufgerufen; API unverändert |
| `claude-code-handoff/current/jsx/screen-metrics-editor.jsx` | JSX-SOLL | Bindende Referenz für `SavePresetDialog`-Overlay und Editor-Layout |
| `claude-code-handoff/current/jsx/screen-channel-preview-redesign.jsx` | JSX-SOLL | Bindende Referenz für `ChannelPreviewBlock`-Styling |
| `claude-code-handoff/current/jsx/tokens.css` | Design-Token-Quelle | `--g-paper`, `--g-card-alt`, `--g-rule`, `--g-rule-soft`, `--g-ink-3`, `--g-accent` u.a. |
| `claude-code-handoff/current/soll/L-metrics-editor-table-preview.png` | SOLL-Screenshot | Referenz für TablePreview-Layout (3 Tabellen, HEUTE/MORGEN/ÜBERMORGEN) |
| `claude-code-handoff/current/soll/L-metrics-editor-save-preset.png` | SOLL-Screenshot | Referenz für SavePresetDialog Custom-Overlay |
| `claude-code-handoff/current/soll/L-metrics-editor-signal-preview.png` | SOLL-Screenshot | Referenz für ChannelPreviewBlock (Signal) |
| `claude-code-handoff/current/soll/L-metrics-editor-sms-preview.png` | SOLL-Screenshot | Referenz für ChannelPreviewBlock (SMS) |

## Implementation Details

### §1 TablePreview in WeatherMetricsTab einbinden

`WeatherMetricsTab.svelte` importiert `TablePreview` aktuell NICHT — die Komponente existiert (`frontend/src/lib/components/trip-detail/TablePreview.svelte`), ist aber nie eingebunden worden.

**Änderung:**

1. Import hinzufügen: `import TablePreview from './TablePreview.svelte';`
2. `TablePreview` unterhalb der `BucketSection` für "Detail-Werte" (Secondary-Bucket) und oberhalb von `ChannelPreviewBlock` in das Template einfügen.
3. Alle benötigten Props übergeben: `catalog`, `enabledMap`, `friendlyMap`, `horizonsMap`, `categoryOrder`, `indicatorCapable` — alle sind bereits als State-Variablen in `WeatherMetricsTab.svelte` vorhanden.

**Position im Template (nach aktueller Struktur):**

```svelte
<!-- Nach BucketSection "Detail-Werte" -->
<TablePreview
  {catalog}
  {enabledMap}
  {friendlyMap}
  {horizonsMap}
  {categoryOrder}
  {indicatorCapable}
/>

<!-- danach ChannelPreviewBlock (bereits vorhanden) -->
```

**Keine State-Änderungen nötig** — alle Props sind bereits verfügbar.

### §2 SavePresetDialog — Custom Fixed-Overlay

Die aktuelle Implementierung wickelt den Dialog in `<Dialog.Root>`, `<Dialog.Content>`, `<Dialog.Header>`, `<Dialog.Footer>` von shadcn ein. Das JSX-SOLL (`screen-metrics-editor.jsx` Z. 641–680) definiert stattdessen ein Custom-Overlay.

**Zu entfernende Imports:**
```typescript
import * as Dialog from '$lib/components/ui/dialog/index.js';
```

**Neue Overlay-Struktur (exakt nach JSX-SOLL):**

Äußeres Wrapper-`<div>` (Overlay):
```
position: fixed; inset: 0;
background: rgba(26,26,24,0.45);
backdrop-filter: blur(2px);
display: flex; align-items: center; justify-content: center;
z-index: 100;
```
Klick auf Overlay → Dialog schließen (`onClose()`).

Innerer Dialog-Container:
```
width: 520px;
background: var(--g-paper);
border: 1px solid var(--g-rule);
border-radius: 6px;
box-shadow: 0 24px 80px rgba(26,26,24,0.25);
overflow: hidden;
```
Klick auf inneres Div → `stopPropagation()`.

**Header:**
```
padding: 18px 24px;
border-bottom: 1px solid var(--g-rule-soft);
display: flex; justify-content: space-between; align-items: center;
```
- `<Eyebrow>EIGENES PRESET</Eyebrow>` (uppercase mono, aktuell `<Dialog.Title>Als Preset speichern</Dialog.Title>` ist falsch)
- Titel: `<div style="font-size:18px; font-weight:600; margin-top:2px">Auswahl als Preset speichern</div>`
- Close-Button: `×` rechts, `background:none`, `border:none`, `fontSize:18`, `color:var(--g-ink-3)`

**Body:**
```
padding: 18px 24px;
```
- Label `NAME` (mono uppercase, `fontSize:10, color:var(--g-ink-3), letterSpacing:0.08em`)
- Input mit `autoFocus`, `padding: 10px 12px`, `fontSize:15`, `background:var(--g-card)`, `border:1px solid var(--g-rule)`, `borderRadius:4`
- Optional: Label `BESCHREIBUNG · OPTIONAL` (gleicher Stil)
- "WIRD GESPEICHERT"-Box: `padding:12px 14px`, `background:var(--g-card-alt)`, `borderRadius:4`, `border:1px solid var(--g-rule-soft)`
  - Eyebrow-Label `WIRD GESPEICHERT` (mono uppercase, `fontSize:10, color:var(--g-ink-3)`)
  - Statuszeile: N Spalten · N Detail · N als Einfach
  - ZEITHORIZONTE-Block aus #343 (Eyebrow, computeHorizonSummary, Dot-Grid) **bleibt erhalten**

**Footer:**
```
padding: 14px 24px;
border-top: 1px solid var(--g-rule-soft);
background: var(--g-card-alt);
display: flex; justify-content: flex-end; gap: 8px;
```
- `<Btn variant="ghost" size="sm">Abbrechen</Btn>`
- `<Btn variant="primary" size="sm">Preset speichern</Btn>` (Primär-Aktion, Text laut JSX-SOLL)

**Sichtbarkeitssteuerung:** Wird über `bind:open` (Eltern-Prop aus `WeatherMetricsTab`) gesteuert. Wenn `open === false`, nichts rendern (`{#if open}`).

**Bestehende Logik (Submit, Save-Payload, ZEITHORIZONTE-Box, Default-Checkbox) bleibt 1:1 erhalten.** Nur die Hülle (shadcn Dialog → Custom Overlay) wird ausgetauscht.

### §3 Style-Token-Audit (BucketSection, ChannelPreviewBlock, TablePreview-Header)

Für jede der folgenden Dateien gilt: JSX-Referenz öffnen, relevante Inline-Styles extrahieren, gegen die aktuelle Svelte-Implementierung vergleichen, Abweichungen auf Design-Tokens korrigieren.

**Prüf-Reihenfolge und JSX-Quellen:**

| Svelte-Datei | JSX-Referenz | Was prüfen |
|---|---|---|
| `TablePreview.svelte` | `screen-metrics-editor.jsx` (gibt es dort eine TablePreview-Sektion?) + SOLL-Screenshot `L-metrics-editor-table-preview.png` | Sektion-Header-Eyebrow, Tabellen-Caption-Stil, Grid-Gap |
| `ChannelPreviewBlock.svelte` | `screen-channel-preview-redesign.jsx` + `L-metrics-editor-signal-preview.png` + `L-metrics-editor-sms-preview.png` | Container-Padding, Kanal-Tab-Styling, Preview-Hintergrund |
| `OutputLayoutEditor.svelte` | `screen-metrics-editor.jsx` (BucketSection, SectionH) | Section-Header-Abstände, Hint-Text-Farbe (`var(--g-ink-2)`) |

**Vorgehen für jeden Fund:** Nur Abweichungen korrigieren, die sichtbar und durch JSX belegt sind. Keine spekulativen Verbesserungen. Jede Änderung mit JSX-Zeilenreferenz kommentieren.

## Expected Behavior

- **Input:** User navigiert zu Trip-Detail → Tab "Wetter-Metriken". Trip hat `display_config.metrics[]` mit aktivierten Metriken und Horizon-Konfiguration.
- **Output (AC-1):** Unterhalb der "Detail-Werte"-Sektion und oberhalb des Kanal-Previews erscheint eine "Tabellen-Vorschau" mit drei nebeneinanderliegenden Mini-Tabellen für HEUTE / MORGEN / ÜBERMORGEN. Jede Tabelle zeigt nur die Metriken, deren `horizonsMap[id][day] === true`. Jede Tabellen-Caption hat das Format "HEUTE — N METRIKEN" (Eyebrow-Stil, mono uppercase).

- **Input:** User klickt "+ Als Preset speichern".
- **Output (AC-2):** Statt des shadcn-Dialogs öffnet sich ein custom Fixed-Overlay mit Blur-Backdrop. Header zeigt Eyebrow "EIGENES PRESET" + Titel "Auswahl als Preset speichern". "WIRD GESPEICHERT"-Box ist vorhanden. Footer-Primär-Button heißt "Preset speichern". Dialog hat 520 px Breite. Klick auf Backdrop schließt den Dialog.

- **Input:** User öffnet SavePresetDialog, bestätigt mit "Preset speichern".
- **Output (AC-3):** ZEITHORIZONTE-Box (aus #343) — Eyebrow, computeHorizonSummary-Text, Dot-Grid — ist unverändert vorhanden und zeigt korrekte Horizont-Zusammenfassung.

- **Input:** `fresh-eyes-inspector` Agent wird mit Mode 2 gegen `L-metrics-editor-*.png` aufgerufen.
- **Output (AC-4):** PASS — kein visueller Befund der Kategorie "Abweichung vom SOLL".

- **Side effects:** Keine Daten-Änderungen; rein visuelle/strukturelle Umbauten. Bestehende API-Calls (`PUT /api/trips/{id}/weather-config`, `POST /api/metric-presets`) bleiben unverändert.

## Acceptance Criteria

- **AC-1:** Given der Trip-Detail-Tab "Wetter-Metriken" ist geöffnet und mindestens eine Metrik ist aktiviert / When der Tab vollständig gerendert ist / Then ist unterhalb der "Detail-Werte"-Sektion und oberhalb des Kanal-Previews eine Tabellen-Vorschau sichtbar, die genau drei separate `<table>`-Elemente mit `data-day="today"`, `data-day="tomorrow"` und `data-day="day_after"` enthält; jede `<caption>` trägt den Eyebrow-Text im Format "HEUTE — N METRIKEN" mit der korrekten Anzahl aktiver Metriken für diesen Horizont
  - Test: (populated after /4-tdd-red)

- **AC-2:** Given der User klickt auf "+ Als Preset speichern" im Metrics-Editor / When der Dialog geöffnet ist / Then ist im DOM kein Element mit `data-slot="dialog-content"` oder `data-radix-dialog-content` (shadcn-Artefakte) vorhanden; stattdessen existiert ein `<div>` mit `position:fixed` und `backdrop-filter:blur(2px)` als Overlay; der Dialog-Container hat eine Breite von 520 px (`data-testid="save-preset-dialog"`); die Eyebrow im Header lautet "EIGENES PRESET"; der Primär-Button im Footer trägt den Text "Preset speichern"
  - Test: (populated after /4-tdd-red)

- **AC-3:** Given der SavePresetDialog ist geöffnet und der Trip hat Metriken mit gemischten Horizont-Konfigurationen (z. B. 3 Metriken mit `{today:true, tomorrow:true, day_after:true}` und 1 Metrik mit `{today:true, tomorrow:false, day_after:false}`) / When der Dialog gerendert ist / Then enthält er einen Block `data-testid="save-preset-horizon-summary"` mit dem durch `computeHorizonSummary` generierten Text (z. B. "3 alle drei Tage · 1 nur heute") und darunter die Dot-Grid-Liste mit `●●●`/`●●○`/`●○○`-Indikatoren — exakt wie durch Issue #343 implementiert; dieser Block bleibt durch den Overlay-Umbau inhaltlich unverändert
  - Test: (populated after /4-tdd-red)

- **AC-4:** Given die SOLL-Screenshots `L-metrics-editor-table-preview.png`, `L-metrics-editor-save-preset.png`, `L-metrics-editor-signal-preview.png`, `L-metrics-editor-sms-preview.png` sind als Referenz geladen / When `fresh-eyes-inspector` in Mode 2 gegen Screenshots der implementierten Oberfläche auf Staging ausgeführt wird / Then lautet das Verdict PASS — kein Befund der Kategorie "Abweichung vom SOLL-Design" mit Schwere hoch oder kritisch
  - Test: (populated after /4-tdd-red)

- **AC-5:** Given die Codebase ist im Zustand nach allen Änderungen aus dieser Spec / When `uv run pytest` und `npm run test` (Frontend-Vitest) ausgeführt werden / Then ist die Exit-Code beider Befehle 0 — keine zuvor bestehende Tests brechen durch den Umbau von SavePresetDialog oder das Einbinden von TablePreview
  - Test: (populated after /4-tdd-red)

## Affected Files

| Pfad | Änderung | Schicht |
|------|----------|---------|
| `frontend/src/lib/components/trip-detail/WeatherMetricsTab.svelte` | `TablePreview` importieren und nach BucketSection "Detail-Werte" einbinden | Frontend |
| `frontend/src/lib/components/trip-detail/SavePresetDialog.svelte` | shadcn `<Dialog>` durch Custom Fixed-Overlay ersetzen (exakt nach JSX-SOLL Z. 641–680); ZEITHORIZONTE-Block bleibt erhalten | Frontend |
| `frontend/src/lib/components/trip-detail/TablePreview.svelte` | Style-Audit: Sektion-Header, Caption-Stil gegen JSX-SOLL prüfen und ggf. korrigieren | Frontend |
| `frontend/src/lib/components/trip-detail/ChannelPreviewBlock.svelte` | Style-Audit: Container-Padding, Kanal-Tab gegen `screen-channel-preview-redesign.jsx` prüfen | Frontend |
| `frontend/src/lib/components/shared/OutputLayoutEditor.svelte` | Style-Audit: Section-Header-Abstände gegen `screen-metrics-editor.jsx` prüfen | Frontend |

## Out of Scope

- Backend-Änderungen jeglicher Art — kein Eingriff in Go-API oder Python-Backend
- Neue UI-Features im Metrics-Editor (HorizonChip-Toggles etc. — bereits in #343 implementiert)
- Mobile-Layout-Änderungen für TablePreview unter 1100 px — als Pragmatik in #343 dokumentiert
- Änderungen an `MetricCheckbox.svelte` oder `HorizonChip.svelte` — diese sind aus #343 korrekt
- Account-Karte zur Preset-Verwaltung (#344) und EditWeatherSection-Konsolidierung (#345)

## Known Limitations

- Der Style-Audit für `ChannelPreviewBlock` und `OutputLayoutEditor` ist ergebnisabhängig: Wenn keine Abweichungen gefunden werden, entfällt die Änderung an der Datei. Das ist kein Fehler.
- `SavePresetDialog` verliert durch den Umbau die shadcn-interne Fokus-Trap und `aria-dialog`-Rolle. Mitigation: `role="dialog"` und `aria-modal="true"` manuell auf das innere Container-Div setzen; Fokus bei Öffnen via `autoFocus` auf das Name-Input gesetzt (per JSX-SOLL `autoFocus` auf dem Input).

## Changelog

- 2026-06-04 (SPEC CREATED): Initial spec erstellt. Design-Fidelity-Korrekturen für den Metrics-Editor (Trip-Detail-Tab): TablePreview-Einbindung in WeatherMetricsTab, SavePresetDialog-Umbau von shadcn Dialog zu Custom Fixed-Overlay nach JSX-SOLL, Style-Token-Audit für TablePreview/ChannelPreviewBlock/OutputLayoutEditor. ~180 LoC netto, 5 Dateien. 5 Acceptance Criteria im AC-N-Format. Bindende Referenz: `claude-code-handoff/current/jsx/screen-metrics-editor.jsx` + 4 SOLL-Screenshots.

- 2026-06-04 (IMPLEMENTED): Design-Fidelity vollständig umgesetzt.
  - SavePresetDialog.svelte: shadcn Dialog → Custom Fixed-Overlay (blur-Backdrop, 520px, Eyebrow "EIGENES PRESET", Button "Preset speichern")
  - WeatherMetricsTab.svelte: TablePreview importiert und nach BucketSection "Detail-Werte" eingebunden
  - Test-Datei erstellt mit 7 AC-Checks (Import, Blur-Backdrop, Eyebrow, Button-Text, position:fixed, ZEITHORIZONTE-Box)
  - Style-Audit: Keine Abweichungen in TablePreview/ChannelPreviewBlock/OutputLayoutEditor gefunden
  - 173 LoC produktiv, 145 LoC Tests
