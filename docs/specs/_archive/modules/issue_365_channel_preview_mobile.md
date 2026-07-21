---
entity_id: issue_365_channel_preview_mobile
type: module
created: 2026-05-25
updated: 2026-05-25
status: approved
version: "1.0"
tags: [output, frontend, editor, preview, epic-331, issue-361]
---

# Multi-Kanal-Live-Vorschau im Editor + Mobile

## Purpose

Schritt C (Abschluss) von #361 / Epic #331. Der Bucket-Editor (#364) bekommt die im Design
vorgesehene **4-Kanal-Live-Vorschau**: vier Mini-Karten (Email/Telegram/Signal/SMS) zeigen
beim Editieren sofort, welche Spalten in die Tabelle wandern, was in die Detail-Zeile rutscht
und ein Warn-Badge „⚠ N Spalten verschoben" bei Überlauf. Dazu Preset-Summary-Erweiterung,
eine kleine Fresh-Eyes-Politur und responsives Verhalten auf schmalen Viewports.

Rein **Frontend, client-seitig** (nutzt die vorhandene Bucket-Logik aus #364 für die
Layout-Verteilung; die echte Daten-Vorschau pro Kanal liefern separat die #363-Endpoints im
Output-Vorschau-Tab). Kein Backend-Change.

## Source

- **Design (verbindlich):** `docs/design/epic_331_output_layout/screen-metrics-editor.jsx` (ChannelPreviewBlock/ChannelPreviewCard, Z. 555-667); `screen-output-preview*.jsx`; `screen-metrics-editor-mobile.jsx`. Design-System `docs/design-system/`.
- **Neu:** `frontend/src/lib/components/trip-detail/ChannelPreviewBlock.svelte`, `ChannelPreviewCard.svelte`
- **Geändert:** `frontend/src/lib/components/trip-detail/metricsEditor.ts` — `applyChannel(primary, secondary, budget) -> {inTable, detail, demoted}` (pure; erweitert das vorhandene `channelOverflow`/`CHANNEL_COL_BUDGET`)
- **Geändert:** `WeatherMetricsTab.svelte` — ChannelPreviewBlock einsetzen (ersetzt die schlanke TablePreview), responsive Stapelung
- **Geändert:** `SavePresetDialog.svelte` — Zusammenfassung Spalten/Detail/Skala (nutzt vorhandenes `buildPresetSummary`, bucket-bewusst erweitert)
- **Geändert:** `ChannelLimitMarkers.svelte` — Fresh-Eyes-Politur: Badges enger an die „Spalten"-Überschrift

> Schicht: **Frontend / SvelteKit** (`frontend/src/`). KEIN Go/Python-Change. Damit bleibt der Commit frontend-only — der Backend-Commit-Gate (volle pytest-Suite) wird nicht getriggert.

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `metricsEditor.ts` `CHANNEL_COL_BUDGET`/`channelOverflow` (#364) | const/fn | Budget je Kanal + Überlauf-Erkennung |
| `metricsEditor.ts` `buildPresetSummary` (epic_138) | fn | Preset-Zähler |
| `#363` Vorschau-Endpoints | follow-up | echte Daten-Vorschau pro Kanal (separater Output-Vorschau-Tab) |

## Implementation Details

### applyChannel (pure, design-identisch)

```ts
// budget = CHANNEL_COL_BUDGET[channel] (email Infinity, telegram 7, signal 5, sms 0)
export function applyChannel(primary: string[], secondary: string[], budget: number) {
  if (budget === 0) return { inTable: [], detail: [...primary, ...secondary], demoted: primary.length };
  const inTable = budget === Infinity ? primary : primary.slice(0, budget);
  const overflow = budget === Infinity ? [] : primary.slice(budget);
  return { inTable, detail: [...overflow, ...secondary], demoted: overflow.length };
}
```
Verteilung deckt sich mit Backend `render_for_channel` (#360): Signal-Budget 5 wählbare Spalten (+ feste Uhrzeit = 6), Telegram 7 (+1).

### ChannelPreviewBlock

Vier `ChannelPreviewCard` (Email/Telegram/Signal/SMS) in einem Grid. Pro Karte: Kanal-Label +
Spalten-Zähler (`inTable.length`/Budget bzw. „flach"), Mono-Mini-Tabelle (Kürzel-Header + eine
repräsentative Zeile), `·`-Detail-Zeile aus `detail`, und Warn-Badge „⚠ N Spalten verschoben in Detail"
wenn `demoted > 0` (Zusatz „in Detail" bewusst — sagt dem User, WOHIN sie wandern).
SMS: flache Textzeile statt Tabelle. Reagiert reaktiv auf Bucket-Änderungen.

### Mobile (Desktop-Tool, daher reduziert)

Editor stapelt sauf schmalen Viewports sauber (Preset-Liste über den Buckets statt daneben);
Vorschau reduziert auf Kanal-Auswahl (Dropdown) + 1 Karte. **Das vollständige separate
Mobile-Akkordeon-Redesign aus `screen-metrics-editor-mobile.jsx` wird vertagt** (anderer UX-
Ansatz, niedriger Wert für ein Desktop-Planungstool — siehe Projekt-Konvention „Frontend =
Desktop-Planungstool"). Falls gewünscht: eigenes Folge-Issue.

## Expected Behavior

- **Input:** aktuelle Buckets (primary/secondary) aus dem Editor-State
- **Output:** 4 Vorschau-Karten mit Tabelle/Detail/Badge je Kanal; reaktiv
- **Side effects:** keine (reine Anzeige; kein Fetch, kein Save)

## Acceptance Criteria

- **AC-1:** Given Buckets mit `primary`/`secondary` / When `applyChannel(primary, secondary, budget)` für jeden Kanal läuft / Then liefert Email `inTable==primary`/`demoted==0`, SMS `inTable==[]`/alles in `detail`, und Signal/Telegram kappen `inTable` auf ihr Budget mit `demoted==overflow`.
  - Test: (populated after /tdd-red)

- **AC-2:** Given 7 Metriken im Bucket „Spalten" / When der Vorschau-Block rendert / Then zeigt die Signal-Karte `demoted>0` mit Badge „⚠ 2 Spalten verschoben" und die 2 überzähligen in der Detail-Zeile; die Email-Karte zeigt alle 7 ohne Badge.
  - Test: (populated after /tdd-red)

- **AC-3:** Given irgendeine Bucket-Konfiguration / When die SMS-Karte rendert / Then enthält sie keine Tabelle, sondern eine flache Textzeile aus allen Werten.
  - Test: (populated after /tdd-red)

- **AC-4:** Given eine Bucket-Auswahl mit Spalten/Detail + Skala-Modi / When `buildPresetSummary`/Bucket-Summary läuft / Then zeigt der SavePresetDialog korrekte Zähler für Spalten, Detail und „als Skala".
  - Test: (populated after /tdd-red)

- **AC-5:** Given der Editor auf einem schmalen Viewport (<900px) / When er rendert / Then stapeln Preset-Liste, Buckets und Vorschau vertikal ohne Überlauf/abgeschnittene Bereiche (visuell per Fresh-Eyes/Playwright belegt).
  - Test: (populated after /tdd-red)

- **AC-6:** Given die „Spalten"-Sektion / When `ChannelLimitMarkers` rendert / Then sind die Kanal-Badges sichtbar der Überschrift „Spalten" zugeordnet (Fresh-Eyes-Politur; visuell belegt).
  - Test: (populated after /tdd-red)

## Known Limitations

- Vorschau zeigt repräsentative Werte (Layout/Verteilung), nicht die Live-Wetterdaten — die echte Daten-Vorschau pro Kanal liefert der Output-Vorschau-Tab über die #363-Endpoints (separat).
- Volles Mobile-Akkordeon-Redesign vertagt (s.o.).
- 2 LOW Backend-Test-Nits aus #363 (Telegram-Proxy `user_id`-Assert, signal≠telegram-Assert) NICHT hier — sie berühren Backend-Test-Dateien und würden den Commit-Gate gegen die aktuell rote Backend-Suite triggern; separat erledigen wenn die Suite grün ist.

## Changelog

- 2026-05-25: Initial spec created (Schritt C von #361 / Epic #331, Issue #365)
