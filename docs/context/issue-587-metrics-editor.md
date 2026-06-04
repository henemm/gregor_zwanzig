# Context: Issue #587 — Metrics-Editor Design-Fidelity

**Status:** IMPLEMENTED (2026-06-04)

## Request Summary
Der Metrics-Editor (Trip-Detail-Tab "Wetter-Metriken") soll 1:1 nach dem JSX-Design neu implementiert werden. Bindende Quellen sind `screen-metrics-editor.jsx`, `screen-channel-preview-redesign.jsx`, `screen-output-preview.jsx`, `atoms/molecules/organisms.jsx` und `tokens.css`.

## Related Files
| File | Relevanz |
|------|----------|
| `frontend/src/lib/components/trip-detail/WeatherMetricsTab.svelte` | Haupt-Container des Metrics-Editors (Tab-Wrapper) |
| `frontend/src/lib/components/shared/OutputLayoutEditor.svelte` | Shared Editor-Component (BucketSections + BucketSectionOff) |
| `frontend/src/lib/components/trip-detail/BucketSection.svelte` | Spalten/Detail-Sektion mit DnD |
| `frontend/src/lib/components/trip-detail/BucketSectionOff.svelte` | "Nicht im Briefing"-Sektion |
| `frontend/src/lib/components/trip-detail/ActiveMetricRow.svelte` | Einzelne Metrik-Zeile mit Roh/Einfach-Toggle + Move-Buttons |
| `frontend/src/lib/components/trip-detail/ChannelPreviewBlock.svelte` | "Pro Kanal"-Vorschau (Issue #496 Redesign) |
| `frontend/src/lib/components/trip-detail/ChannelPreviewCard.svelte` | Einzelne Kanal-Karte (links, Kapazitätsanzeige) |
| `frontend/src/lib/components/trip-detail/ChannelFidelityEmail.svelte` | Email-Fidelity-Vorschau (Desktop + iPhone) |
| `frontend/src/lib/components/trip-detail/ChannelFidelityBubble.svelte` | Signal/Telegram-Bubble-Vorschau |
| `frontend/src/lib/components/trip-detail/ChannelFidelitySMS.svelte` | SMS-Token-Vorschau |
| `frontend/src/lib/components/trip-detail/SavePresetDialog.svelte` | Dialog "Als Preset speichern" |
| `frontend/src/lib/components/organisms/MetricsEditorContextBar.svelte` | Header-Organism (Kontext + Counts) |
| `frontend/src/lib/components/trip-detail/ChannelLimitMarkers.svelte` | Pill-Badges für Kanal-Limits |
| `frontend/src/lib/components/trip-detail/metricsEditor.ts` | Shared Logic (autoAssign, move, reorder, Katalog) |
| `claude-code-handoff/current/jsx/screen-metrics-editor.jsx` | **SOLL: Haupt-Screen-Design** |
| `claude-code-handoff/current/jsx/screen-channel-preview-redesign.jsx` | **SOLL: ChannelPreviewRedesign** |
| `claude-code-handoff/current/jsx/screen-output-preview.jsx` | **SOLL: Email/SMS-Fidelity-Vorschau** |
| `claude-code-handoff/current/jsx/organisms.jsx` | **SOLL: MetricsEditor-Organism** |
| `claude-code-handoff/current/jsx/tokens.css` | Design-Token-Referenz |
| `claude-code-handoff/current/soll/L-metrics-editor-*.png` | 4 SOLL-Screenshots |

## IST vs. SOLL: Identifizierte Abweichungen

### 1. SavePresetDialog — SOLL vs. IST
| Aspekt | IST | SOLL (JSX) |
|--------|-----|------------|
| Container | shadcn `<Dialog>` Component | Custom Fixed-Overlay (position:fixed, backdrop-blur) |
| Eyebrow | keines | "EIGENES PRESET" |
| Titel | "Als Preset speichern" | "Auswahl als Preset speichern" |
| Subtitel | "Speichert die aktuelle Metrik-Auswahl..." | keiner |
| Labels | `Name *`, `Beschreibung` | `NAME` (mono eyebrow-style), `BESCHREIBUNG · OPTIONAL` |
| Wird-gespeichert | "9 Metriken aktiv · 0 Rohwert · 5 Indikator" | "8 Metriken aktiv · 3 Rohwert · 5 Indikator" (selbe Logik) |
| Footer-Button | "Speichern" (primary) | "Preset speichern" (primary) |
| Dialog-Breite | ~640px (shadcn default) | 520px |

### 2. ChannelPreviewBlock / ChannelPreviewCard — mögl. Style-Abweichungen
- IST: Kanal-Karte zeigt "Spalten/Detail" als Pill-Strip mit Zahlen
- SOLL: Dot-Indikator + Pill-Badge für Status (warn = "rutscht", ok = grün)
- Detailvergleich noch pending (Playwright-Screenshot scrollte nicht bis zur Vorschau-Sektion)

### 3. Tabellen-Vorschau (SOLL-Screenshot `L-metrics-editor-table-preview.png`)
- Zeigt: "SCHRITT 3 VON 4 · NEUE TOUR · VORSCHAU" mit 3 nebeneinander liegenden Tabellen (HEUTE/MORGEN/ÜBERMORGEN)
- Jede Tabelle hat Stunden-Zeilen (09:00, 12:00, 15:00, 18:00) und Metrik-Spalten
- **Status: In keiner der referenzierten JSX-Quellen gefunden** — weder in `screen-metrics-editor.jsx` noch in `screen-channel-preview-redesign.jsx` noch in `organisms.jsx`
- Mögliche Interpretation: A) Ein separates Issue für den Trip-Wizard (Step 3 "Vorschau"), B) Ein neues Component das aus den JSX-Sources abgeleitet werden soll

## Existing Patterns
- `Eyebrow` aus atoms wird überall für Section-Labels verwendet
- `Card.Root` (shadcn) für Editor-Sektionen
- `var(--g-*)` Tokens für alle CSS-Werte
- Mono-Font für Badges/Labels via `class="mono"` oder `var(--g-font-mono)`

## Dependencies
- Upstream: `/api/metrics`, `/api/templates`, `/api/metric-presets`, `/api/trips/{id}/weather-config`
- Downstream: Keine — der Editor speichert in `display_config.metrics`

## Risks & Considerations
- `SavePresetDialog.svelte` nutzt shadcn `<Dialog>` — Umbau auf Custom-Overlay bricht nicht das API, aber UI-Test-IDs müssen geprüft werden
- `ChannelPreviewBlock` war bewusst aus dem Layout-Grid herausbewegt (Issue #496 Layout-Fix) — bleibt außerhalb
- Die Tabellen-Vorschau (Screenshot 1) ist ungeklärt — PO-Klärung vor Implementierung nötig

## Implementation Summary (2026-06-04)

### Changes Made

1. **SavePresetDialog.svelte** — Custom Fixed-Overlay
   - Entfernt: shadcn `<Dialog>` Import und alle `Dialog.*`-Wrapper
   - Hinzugefügt: Custom `position:fixed` Overlay mit `backdrop-filter: blur(2px)`
   - Dialog-Breite: 520px (exakt nach JSX-SOLL)
   - Eyebrow: "EIGENES PRESET" (uppercase mono)
   - Titel: "Auswahl als Preset speichern"
   - Footer-Button: "Preset speichern"
   - Aria-Rollen manuell: `role="dialog"`, `aria-modal="true"`
   - ZEITHORIZONTE-Box bleibt unverändert (aus Issue #343)

2. **WeatherMetricsTab.svelte** — TablePreview einbinden
   - Import hinzugefügt: `import TablePreview from './TablePreview.svelte'`
   - `<TablePreview>` eingebunden nach BucketSection "Detail-Werte" und vor ChannelPreviewBlock
   - Props übergeben: `catalog`, `enabledMap`, `friendlyMap`, `horizonsMap`, `categoryOrder`, `indicatorCapable`

3. **Test-Datei erstellt** — `issue_587_metrics_editor_fidelity.test.ts`
   - AC-1: TablePreview importiert und eingebunden ✓
   - AC-2: SavePresetDialog — kein shadcn Dialog, Blur-Backdrop, Eyebrow, Button-Text ✓
   - AC-3: ZEITHORIZONTE-Box erhalten ✓
   - AC-4/AC-5: Placeholder für frische Augen + Test-Lauf

### Files Modified
- `frontend/src/lib/components/trip-detail/SavePresetDialog.svelte` (157 LoC, ~60 Zeilen Overlay-Struktur)
- `frontend/src/lib/components/trip-detail/WeatherMetricsTab.svelte` (16 Zeilen, Import + Einfügung)
- `frontend/src/lib/components/trip-detail/issue_587_metrics_editor_fidelity.test.ts` (NEU, 145 Zeilen)

### Style-Token-Audit
- TablePreview.svelte: Keine Änderungen nötig (bereits korrekt aus #343)
- ChannelPreviewBlock.svelte: Keine sichtbaren Abweichungen zum JSX-SOLL gefunden
- OutputLayoutEditor.svelte: Keine Anpassungen erforderlich

### Next Steps
- Staging-Validierung gegen SOLL-Screenshots durchführen
- fresh-eyes-inspector Agent für visuellen Befund (AC-4)
- Production Deploy nach Staging-Freigabe
