# Context: feat-1232-layout-tab (#1232 Scheibe 3)

## Request Summary

Letzter Teil von #1232 (Phase 4, Epic #1230): EIN geteilter Organism `LayoutTab`
(context="route"|"vergleich") ersetzt die heute doppelt gebauten Layout-Flächen —
(Trip) den Ausgabe-Teil des Wetter-Metriken-Tabs (Reihenfolge + Kanal-Kappung +
Live-Mail-Vorschau) und (Compare) den Layout-Tab (Kanal-Tabs + OutputLayoutEditor
+ LayoutPreview). Metrik-AUSWAHL (Preset + Grundauswahl) bleibt Trip-eigen. Rein
Frontend, kein Datenmodell-Change (C4).

## Verbindliche Quellen

| Quelle | Inhalt |
|---|---|
| Issue #1232 Body | „Trip: Ausgabe-Teil (WM2_Reihenfolge + WM2_MailPreview) · Vergleich: CE_LayoutTab + CE_LayoutPreview → LayoutTab"; E9: zwei Vorschau-Templates bleiben getrennt, geteilt nur Kanal-Picker + Kappung + Cut-Line; AC „Kappungs-Logik einmal implementiert (LT_CHANNELS), von beiden Kontexten genutzt" |
| `claude-code-handoff/current/jsx/layout-tab.jsx` (370 Z.) | Design 1:1 — LT_CHANNELS (email ∞ · telegram 8 · sms 0), LT_ChannelPicker (mit Kappungs-Chip + Overflow-Badge), LT_CapNote, LT_CompareOrderList, LT_ComparePreview (vergleich), LT_RoutePreview + LT_RouteOrderDense (route); Props route CONTROLLED: `state onMove onReorder onMode highlight telegramSuffix onSuffix` („identische Signatur wie WM2_*"); vergleich self-contained: `pickedIds`; `dense`/`noScroll`/`bottomPad` für Mobile |
| `soll-29b-desktop-layout-route.png` + `soll-29b-desktop-layout-vergleich.png` + `soll-29b-mobile.png` | Soll-Screens |

## Ist-Zustand (Stand 7d6ef081, Explore 2026-07-12)

**Trip — `WeatherMetricsTab.svelte` (888 Z.), 2-Spalten `.v2-layout` (Z.510):**
- Sektion 01 Preset (`WeatherV2PresetBar` Z.516) + 02 Grundauswahl (`WeatherV2Grundauswahl` Z.529) = AUSWAHL → bleibt.
- Sektion 03 Reihenfolge & Darstellung (`WeatherV2Reihenfolge` Z.543; testids `wm2-reihenfolge`, `wm2-reihenfolge-row`, `wm2-cut-line`) + 04 SMS-Schwellwerte (`ThresholdMetricRow`×7, `sms-thresholds`, ab Z.565) + rechte Spalte Live-Vorschau (`WeatherV2MailPreview` Z.687; `wm2-mail-preview`, `wm2-email-table`, `wm2-telegram-bubble`, `wm2-sms-line`; mobil FAB+Sheet Z.698-712) = AUSGABE-Teil.
- Mail-Inhalt-Karte (`report-mail-content` Z.660) + Amtliche-Warnungen-Checkbox (Z.670) hängen ebenfalls im Tab — NICHT Teil des LayoutTab-Designs (Verbleib klären).
- Vorschau ist rein statisch (Sample-Daten `WM2_S`, kein Endpoint); eigene interne Kanal-Tabs (`data-channel`); Telegram-Kappung `tgBudget=8`.
- Handler-Realität: `onMode(id,useIndicator)` Z.318, `onToggleMetric` Z.327, `onRemove` Z.347, `onDndReorder(fromId,toId)` Z.356 (DnD statt Pfeile seit #848), `telegramKurzform` $state (Z.80). KEIN `onMove/onReorder` wie im JSX — Trip ist Single-Column (secondary leer seit #587). **Design-Signatur ≠ Code-Realität** → controlled-Props an echte Handler anpassen.
- Persistenz: `buildWeatherPayload()` Z.392 → PUT `/api/trips/{id}/weather-config` + zweiter PUT `/api/trips/{id}` (report_config, official_alerts); Auto-Save `saveController.schedule` Z.439; testids `weather-metrics-tab-save`, `weather-metrics-dirty-pill`, `weather-metrics-discard`.

**Compare — `Step4Layout.svelte` (502 Z.):**
- Kanal-Tabs Z.301-331 (`channel-tab-email|telegram|sms`, Badge ∞/8/—), Layout-Editor = geteilter Organism `OutputLayoutEditor` Z.335 (volles primary/secondary/off-Bucket-Modell; Handler handleMove/handleReorder/handleDndReorder/handleMode/handleSelectPreset Z.230-283), Detail-Pills `compare-step4-detail-pill-{i}` Z.357, Vorschau `LayoutPreview` Z.373-375 (`compare-step4-layout-preview`; Orte-als-ZEILEN, DUMMY_LOCATIONS, filtert nicht nach pickedIds; SMS `compare-step4-preview-sms`).
- `CompareInhaltSection` (2b) hängt am Ende Z.382 — kein Layout-Bezug, bleibt außen vor.
- Persistenz: `channelLayouts` in wizardState (Z.32, $effect Z.188-201) → `display_config.channel_layouts` + `active_metrics`; zentraler Editor-Save.

**Kappung ∞/8/0 — 4+ Duplikate:** kanonisch `metricsEditor.ts:226` `CHANNEL_COL_BUDGET` (+ `channelOverflow` Z.322); Trip nutzt sie (`WeatherV2Reihenfolge.svelte:25`, `WeatherV2MailPreview.svelte:23`); Compare dupliziert eigenständig (`Step4Layout.svelte:49-53` CE_CHANNELS; ferner `CompareTabs.svelte:104`, `CompareChatBubble.svelte:44`, `VTBriefingChannels.svelte:80` Text).

**Kein `layout{}`-Feld im Modell** — Layout lebt als `WeatherConfigMetric[]` (bucket/order/enabled/use_friendly_format/horizons/sms_threshold) bzw. `DisplayConfig.channel_layouts` (types.ts:220/231).

## Abhängige Tests

Compare: `compare-editor-slice4.spec.ts` (channel-tab-*, layout-preview, detail-pill, preview-sms), `issue-1093-compare-layout-crash.spec.ts`. Trip: `epic-138-metriken-editor.spec.ts` + `epic-138-block-b.spec.ts` (wm2-reihenfolge-row, dirty-pill, discard, save), `issue-736/723/619/343/690/1117/932`-Specs (weather-metrics-tab, report-mail-content, sms-thresholds, …). Unit: `layoutPreviewRows.test.ts`, `compareEditorSlice3.test.ts`, `channelChipCount.test.ts`.

## Zentrale Spannungsfelder (→ Analyse)

1. **Design-Props vs. Code-Realität (route):** JSX verlangt `onMove/onReorder` — Trip hat DnD-Single-Column (`onDndReorder`, `onMode`, `onRemove`). Controlled-Interface muss auf die ECHTEN Trip-Handler zugeschnitten werden (Design-Fidelity strukturell, nicht API-wörtlich).
2. **Zwei Editor-Modelle bleiben:** Trip Single-Column-Reihenfolge vs. Compare Bucket-Modell (`OutputLayoutEditor`) — LayoutTab ist HÜLLE (Kanal-Picker + Kappung + Zwei-Spalten-Shell + Cut-Line geteilt), keine Datenmodell-Vereinheitlichung.
3. **Verbleib SMS-Schwellwerte + Mail-Inhalt-Karte + Official-Toggle im Trip-Tab:** nicht Teil des LayoutTab-Designs; Optionen: unterhalb belassen (analog 2b-CompareInhaltSection-Muster) — Design-Screens prüfen.
4. **Kappungs-Konsolidierung:** LT_CHANNELS aus `CHANNEL_COL_BUDGET` speisen; Compare-Duplikate (Step4Layout/CompareTabs/CompareChatBubble) auf die Quelle umziehen (Issue-AC!).
5. **Vorschau-Fidelity vergleich:** Design LT_ComparePreview = Orte-als-SPALTEN; Ist LayoutPreview = Orte-als-Zeilen. Design gewinnt? → Umbau der Compare-Vorschau (neutral, kein Rang, Idealbereich grün, C1) ODER Bestand behalten (KL). Design-PNG prüfen; JSX ist verbindlich (1:1).
6. **Testid-Erhalt:** `channel-tab-*`, `compare-step4-layout-preview`, `wm2-*`, `weather-metrics-*` — C6.
7. **Tab-Umbenennungen** („Wertebereiche" etc., Fresh-Eyes-Fund 2b): gehören zu #1231/29a-Nachgang bzw. Design-Nav — klären ob Scheibe 3 oder separat.

## Risks & Considerations

- Größte FE-Scheibe des Issues (~2 große Tabs umgebaut); Schnitt 3a (vergleich) / 3b (route) prüfen.
- Trip-Tab hat dichte Test-Abdeckung (epic-138-Specs) — Reihenfolge-/Save-/Dirty-Pfade dürfen nicht brechen.
- Mobile: Trip nutzt FAB+Bottom-Sheet für Vorschau; Design `dense noScroll` inline — Abweichung klären.

## Analysis

### Type
Feature (Frontend-Refactor, kein Datenmodell-Change)

### Entscheidungen (Plan-Agent 2026-07-12)

1. **Organism-Zuschnitt:** Geteilte Primitiva `shared/layout-tab/` = ltChannels.ts (aus CHANNEL_COL_BUDGET gespeist — einzige Kappungs-Quelle), LTChannelPicker (trägt `channel-tab-{id}`-Testids + data-channel), LTCapNote, LTCutLine, LayoutTab.svelte (channel-$bindable, Zwei-Spalten-Shell, Overflow, Eyebrows). Kontext-Slots: route = WeatherV2Reihenfolge + WeatherV2MailPreview (controlled, interne ch-tabs entfallen); vergleich = OutputLayoutEditor (Bucket-Modell BLEIBT — Hülle, keine Datenmodell-Vereinheitlichung; LT_CompareOrderList aus JSX wird NICHT übernommen) + neue LTComparePreview.
2. **route-Interface = Code-Realität:** Props primaryColumns/metricById/friendlyMap/telegramKurzform/highlight + onDndReorder/onMode/onRemove (+channel $bindable für Mobile-Sheet) — JSX-onMove/onReorder/Pfeiltasten sind Design-Altstand vor #848/#587; Fidelity strukturell, dokumentiert.
3. **Compare-Vorschau NEUBAU design-treu (Orte-als-SPALTEN):** LTComparePreview ersetzt LayoutPreview.svelte (löschen). Bestand verletzt C1 aktiv (Rang-Badges, Score, Empfehlungs-Banner) — PNG+JSX bestätigen neutral/Spalten/Idealbereich-grün. selectPreviewRows bleibt wiederverwendbar. Testids compare-step4-layout-preview/-preview-sms wandern 1:1.
4. **SMS-Schwellwerte/Mail-Inhalt/Official-Toggle bleiben unterhalb** im WeatherMetricsTab (2b-Muster); „Wertebereiche"-Zieltab existiert nicht (#1231-Materie). Vorschau nicht mehr sticky neben 01/02 — designkonform.
5. **Kappungs-Umzugsliste:** Step4Layout CE_CHANNELS entfällt; CompareTabs.svelte:104 + CompareChatBubble.svelte:44 + VTBriefingChannels.svelte:80 auf CHANNEL_COL_BUDGET; WM2-Seite nutzt Quelle bereits.
6. **Tab-Umbenennungen („Wertebereiche") RAUS** — null Kopplung, braucht #1231-Inhalte; als bewusste Auslassung dokumentieren.
7. **Schnitt: 3a vergleich+Primitiva (~550–650 LoC, zuerst) / 3b route (~300–400 LoC)** — je eigener Workflow/Commit; 3b dockt an Primitiva an; Trip-Seite hat dichteste Test-Abdeckung (epic-138) + Auto-Save-Pfade (channel NIE in snapshot/isDirty).
8. **Risiken:** Doppel-Mount (Compare cm-desktop+mobile, TripNewEditor) → LayoutTab zustandsarm+save-frei; Trip-Mobile behält FAB+Sheet (KL, #618), dense-Inline-Vorschau = dokumentierte Abweichung; issue-1093-Crash-Guard → Empty-State „Keine Orte ausgewählt".

### Affected Files (3a)
CREATE: shared/layout-tab/{ltChannels.ts, LTChannelPicker.svelte, LTCapNote.svelte, LTCutLine.svelte, LayoutTab.svelte, LTComparePreview.svelte} · MODIFY: compare/steps/Step4Layout.svelte, compare/CompareTabs.svelte, molecules/CompareChatBubble.svelte, shared/versand-tab/VTBriefingChannels.svelte, layoutPreviewRows.test.ts, e2e/compare-editor-slice4.spec.ts · DELETE: compare/LayoutPreview.svelte

### Scope Assessment
3a: ~550–650 LoC (Risk MEDIUM: 2 E2E-Specs, Doppel-Mount); 3b: ~300–400 LoC (Risk MEDIUM-HIGH: epic-138-Dichte, Auto-Save)
