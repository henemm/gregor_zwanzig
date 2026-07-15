---
entity_id: versand_tab_vergleich
type: feature
created: 2026-07-12
updated: 2026-07-12
status: draft
workflow: feat-1232-versand-tab-2b
---

# VersandTab (vergleich) — geteilter Versand-Organism im Compare-Editor — Scheibe 2b/3

- **Issue:** #1232 (Phase 4 — Editor-Konsolidierung, Sub-Issue von Epic #1230) · Scheibe 2b/3
- **Vorgänger:** #1232 Scheibe 1 (`docs/specs/modules/versand_tab_route.md`, live) · Scheibe 2a (`docs/specs/modules/compare_preset_zeitplan.md`, Backend live — 5 Slot-Felder, Cron, Python-Dispatch)
- **Nachfolger:** Scheibe 3 (LayoutTab-Organism, `CompareReportContentSection` ist Zwischenlösung)
- **Design-Quelle (1:1):** `claude-code-handoff/current/jsx/versand-tab.jsx` (vergleich-Zweig) + `soll-29b-desktop-versand-vergleich.png` + `soll-29b-mobile.png`
- **Typ:** Frontend-Refactor (rein `frontend/src`), **eine erlaubte Backend-Ausnahme:** End-Datum-Lösch-Sentinel in `internal/handler/compare_preset.go` (~5 LoC + Test, s. u.)

## Approval

- [ ] Approved

## Purpose

Der Compare-Editor bekommt denselben geteilten Versand-Organism `VersandTab`
wie der Trip-Editor (`context="vergleich"`). Er ersetzt `Step5Versand` und
bündelt Briefing-Kanäle, Briefing-Zeitplan (Morgen/Abend, editierbare
Uhrzeiten — Scheibe 2a hat die Datenfelder dafür bereits geschaffen),
editierbare Laufzeit („bis auf Weiteres" / „bis Datum") und die komplette
Alert-Zustellung (Cooldown, Stille Stunden, Beispiel-Warnung). Anders als der
Trip-Editor speichert der Compare-Editor zentral (`handleSave`/
`buildComparePresetSavePayload`) — `VersandTab` bindet im vergleich-Zweig
daher direkt an den geteilten Wizard-State statt selbst zu speichern (Grund:
Doppel-Mount Desktop+Mobile, Create-Modus ohne Preset-ID, zentrales
Dirty-Tracking/Verwerfen im `CompareEditor`).

## Source

- **Files:**
  - `frontend/src/lib/components/shared/VersandTab.svelte` — vergleich-Zweig, `wiz`-Prop, `activation`-Snippet
  - `frontend/src/lib/components/shared/versand-tab/VTSchedulePlan.svelte` — `context`-Diskriminierung (Trend-Karte nur route)
  - `frontend/src/lib/components/shared/versand-tab/VTLaufzeitVergleich.svelte` — NEU
  - `frontend/src/lib/components/shared/versand-tab/VTAlertSample.svelte` — NEU
  - `frontend/src/lib/components/compare/CompareEditor.svelte` — Mounts (Desktop Z.604-607, Mobile Z.760-763), `handleSave`, Dirty-Snapshot
  - `frontend/src/lib/components/compare/CompareReportContentSection.svelte` — NEU (Rest-Felder-Extraktion)
  - `frontend/src/lib/components/compare/CompareAlarmSection.svelte` — Cooldown/Quiet-Karten raus
  - `frontend/src/lib/components/compare/compareEditorSave.ts` — 5 Slot-Felder + End-Datum-Sentinel
  - `frontend/src/lib/components/compare/compareWizardState.svelte.ts` — 5 neue Runen
  - `internal/handler/compare_preset.go` — End-Datum-Lösch-Sentinel
- **Identifier:** `function VersandTab`, `class CompareEditor` (Svelte-Component), `function buildComparePresetSavePayload`, `func UpdateComparePresetHandler`

## Expected Behavior

- **Input:** Preset-Edit über den geteilten Wizard-State (`CompareWizardState`)
  — die 5 Slot-Felder (Morgen/Abend an/aus + Uhrzeit, End-Datum inkl.
  „bis auf Weiteres"-Lösch-Sentinel), Briefing-Kanäle (E-Mail/Telegram/SMS)
  sowie Cooldown-Minuten/Stille-Stunden werden direkt in `wiz.*` geschrieben
  (Checkbox-Toggle, Zeit-/Datumsfeld, Segmented-Auswahl).
- **Output:** Nach Klick auf „Speichern" (Edit) bzw. „Briefing aktivieren"
  (Create) enthält der persistierte Zustand alle geänderten Felder — per
  Reload verifizierbar (Edit: `PUT /api/compare/presets/{id}`; Create:
  `POST /api/compare/presets` mit den 5 Slot-Feldern im Body). „Bis auf
  Weiteres" nach zuvor gesetztem Datum führt zu einem gelöschten `end_date`
  nach Reload, nicht zu einem unveränderten Altwert.
- **Side effects:** Der Doppel-Mount (Desktop + Mobile) bleibt über den
  geteilten `wiz`-State konsistent — eine Änderung in einer Instanz ist
  sofort in der anderen sichtbar, ohne eigenen Save-Zustand pro Instanz.
  Jede Feldänderung markiert den Editor als dirty (Save-Button aktiv);
  „Verwerfen" stellt alle Felder auf den zuletzt gespeicherten Stand zurück.
  Der Alarme-Tab verliert die Cooldown-/Stille-Stunden-Controls (ziehen in
  den Versand-Tab um), behält aber Radar-/Official-Toggle und die
  Metrik-Level-Tabelle. Der Layout-Tab gewinnt die neue
  `CompareReportContentSection` (Zeitfenster, Horizont, Top-N,
  Stundenverlauf) als Zwischenlösung bis Scheibe 3.

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `docs/specs/modules/compare_preset_zeitplan.md` (Scheibe 2a, live) | module | Liefert die 5 Slot-Felder (`morning_enabled/morning_time/evening_enabled/evening_time/end_date`) und den stündlichen Dispatch, an die diese Scheibe im Frontend bindet |
| `docs/specs/modules/versand_tab_route.md` (Scheibe 1, live) | module | Vorbild für Organism-Struktur, `VTBriefingChannels`/`VTSchedulePlan`-Bausteine, KL-Nummerierung |
| `frontend/src/lib/components/shared/versand-tab/VTBriefingChannels.svelte` | module | Bereits context-fähig (Lead-Copy für vergleich vorhanden), Gating/Hint-Logik wird wiederverwendet — Testid-Präfix wird parametrisiert (s. Implementation Details) |
| `frontend/src/lib/components/alerts-tab/AlertCooldownCard.svelte` + `AlertQuietHoursCard.svelte` | module | Unverändert wiederverwendet, ziehen aus `CompareAlarmSection` in `VersandTab` um |
| `frontend/src/lib/components/ui/segmented/Segmented.svelte` | module | Wiederverwendet für „Bis auf Weiteres / Bis Datum" (Muster `CompareEndDateControl`) |
| `frontend/src/lib/components/compare/compareWizardState.svelte.ts` | module | Zentraler State — 5 neue Runen, Save-Pfade (`saveNewPreset`, `handleSave` in `CompareEditor`) |
| `frontend/src/routes/compare/[id]/edit/+page.svelte` | module | Hydration der 5 neuen Felder aus `data.preset` beim Edit-Mount |
| Epic #1231 (Korridor-Editor) | workflow | Tab-Beschriftung „Wertebereiche" im Soll-Screenshot ist Epic #1231-Scope, NICHT Teil dieser Scheibe (Out of Scope) |

## Scope

### Affected Files

| File | Change Type | Description |
|------|-------------|-------------|
| `frontend/src/lib/components/shared/VersandTab.svelte` | MODIFY | vergleich-Zweig aktivieren; optionale `wiz`-Prop (`CompareWizardState`); alle Controls binden direkt an `wiz.*` (kein lokaler `$state`, kein Self-Save-`$effect`); `activation`-Snippet-Prop (1:1 JSX) |
| `frontend/src/lib/components/shared/versand-tab/VTSchedulePlan.svelte` | MODIFY | `context`-Prop; Mehrtages-Trend-Karte nur bei `context="route"` rendern (KL-2); vergleich-Intro-Copy „Wie beim Trip…" |
| `frontend/src/lib/components/shared/versand-tab/VTBriefingChannels.svelte` | MODIFY | optionale Testid-Präfix-Props (Default = bestehende `channel-*`, vergleich übergibt `compare-step5-channel-*` — s. Implementation Details) |
| `frontend/src/lib/components/shared/versand-tab/VTLaufzeitVergleich.svelte` | CREATE | Segmented „Bis auf Weiteres / Bis Datum" + `<input type="date">`, bindet `value`/`onChange` (kein eigener State — controlled) |
| `frontend/src/lib/components/shared/versand-tab/VTAlertSample.svelte` | CREATE | statische Beispiel-Warnung, kontext-abhängiges Subjekt (Ort statt Etappe), 1:1 aus `VT_ALERT_SAMPLE.vergleich` |
| `frontend/src/lib/components/compare/CompareEditor.svelte` | MODIFY | Desktop (Z.604-607) + Mobile (Z.760-763): `<VersandTab context="vergleich" {wiz} ...>` statt `<Step5Versand>`; `activation`-Snippet mit dem bestehenden Banner-Markup; `initial`/`dirty`/`handleSave`/`buildComparePresetSavePayload`-Aufruf um 5 Slot-Felder erweitert |
| `frontend/src/lib/components/compare/steps/Step5Versand.svelte` | DELETE | vollständig ersetzt durch `VersandTab` (Kanäle/Zeitplan/Laufzeit/Aktivierung) + `CompareReportContentSection` (Rest-Felder) |
| `frontend/src/lib/components/compare/CompareReportContentSection.svelte` | CREATE | Extrahierte Rest-Felder aus `Step5Versand`: Info-Kacheln, Horizont, Zeitfenster, Stundenverlauf-Toggle+TopN+Metriken, `official_alerts_enabled`-Toggle — alle `compare-step5-*`-Testids UNVERÄNDERT |
| `frontend/src/lib/components/compare/steps/Step4Layout.svelte` | MODIFY | mountet `CompareReportContentSection` am Ende |
| `frontend/src/lib/components/compare/CompareAlarmSection.svelte` | MODIFY | `AlertCooldownCard`/`AlertQuietHoursCard` raus (ziehen in `VersandTab`); Heading, Radar-/Official-Trigger-Toggle, `AlertMetricLevelTable` bleiben |
| `frontend/src/lib/components/compare/compareEditorSave.ts` | MODIFY | `CompareEditorEdits` um `morningEnabled/morningTime/eveningEnabled/eveningTime/endDate` (endDate: `string \| null \| undefined` — `null` = Lösch-Sentinel); Payload-Building analog Round-Trip-Muster |
| `frontend/src/lib/components/compare/compareWizardState.svelte.ts` | MODIFY | 5 neue Runen (`morningEnabled/morningTime/eveningEnabled/eveningTime/endDate`); `saveNewPreset()`-Defaults (`07:00`/an, `18:00`/aus, `end_date` weglassen); `saveComparePreset()`-Aufruf erweitert |
| `frontend/src/routes/compare/[id]/edit/+page.svelte` | MODIFY | 5 Felder aus `data.preset` in `state.*` hydrieren (Defaults identisch zur Go-Migration: `morning_enabled ?? true`, `morning_time ?? '06:00'`, `evening_enabled ?? false`, `evening_time ?? '18:00'`, `endDate ?? null`) |
| `frontend/src/lib/types.ts` | MODIFY | `ComparePreset` um `morning_enabled?/morning_time?/evening_enabled?/evening_time?/end_date?` ergänzen |
| `internal/handler/compare_preset.go` | MODIFY | End-Datum-Lösch-Sentinel: expliziter Leerstring `end_date: ""` im PUT-Body löscht ein gesetztes `EndDate` (statt Nil-Preserve); ~5 LoC |
| `internal/handler/compare_preset_test.go` | MODIFY | neuer Test für den Lösch-Sentinel |
| `frontend/src/lib/components/compare/__tests__/compare_versand_slot_payload.test.ts` | CREATE | node:test — Payload-Builder deckt die 5 Slot-Felder + Sentinel ab (Namensregel: Verhalten statt Issue-Nummer) |
| `frontend/e2e/versand-tab-vergleich.spec.ts` | CREATE | Verhaltens-Playwright: 4 Sektionen, Slot-Bindung, Laufzeit-Sentinel, Dirty/Verwerfen, Create-Flow |
| `frontend/e2e/issue-763-step5-select.spec.ts` | MODIFY | Navigations-Ziel für Horizont/Zeitfenster/TopN/Stundenverlauf: `compare-editor-tab-layout` statt `compare-editor-tab-versand` |
| `frontend/e2e/issue-1134-compare-timewindow-save.spec.ts` | MODIFY | dito (Zeitfenster liegt jetzt im Layout-Tab) |
| `frontend/e2e/compare-editor-slice4.spec.ts` | MODIFY | Navigations-Ziel je nach betroffenem Feld anpassen |
| `frontend/e2e/issue-609-sms-profil.spec.ts` | MODIFY | AC-6 navigiert weiterhin zu Versand, Selektor bleibt `compare-step5-channel-sms` (Testid-Präfix-Parametrisierung erhält ihn) |
| `frontend/e2e/compare-alarm-config.spec.ts` | MODIFY | AC-1 (Cooldown/Quiet) navigiert neu zu `compare-editor-tab-versand` statt `alarme`; Empfindlichkeits-Tabelle-Tests bleiben auf `alarme` |

### Estimated Changes

- Files: ~19 (7 Frontend-Bausteine, 6 Compare-Editor-Dateien, 1 Backend-Datei, 5 Test-/Spec-Dateien)
- LoC (Produktivcode ohne Tests): **+650/-380** (Rahmen 650–850 gesamt inkl. Overhead) — **überschreitet das 250-LoC-Standardlimit deutlich, Override erforderlich** (siehe Known Limitations KL-8; PO-Zustimmung zum Override wird vor Phase 6 explizit eingeholt, kein Selbstbedienungs-Override)
- LoC Tests (zusätzlich): ~250–300 (node:test-Unit + neue/geänderte Playwright-Specs)
- Effort: high (Full-Stack-Bindung an bereits live Backend-Modell, sechs bestehende Frontend-Bausteine + zwei neue, fünf bestehende Playwright-Specs müssen Navigation anpassen)

## Implementation Details

### 1. `VersandTab.svelte` — kein Self-Save im vergleich-Zweig

Der vergleich-Zweig bekommt eine optionale Prop `wiz?: CompareWizardState`.
Anders als im route-Zweig (eigener `$state` + `onMount`-Hydration +
Debounce-`$effect` + `saveController.schedule()`) binden ALLE Controls
**direkt** an `wiz.*`:

```
channels={{ email: wiz.sendEmail, telegram: wiz.sendTelegram, sms: wiz.sendSms }}
onEmailChange={(e) => (wiz.sendEmail = e.target.checked)}
morning_enabled={wiz.morningEnabled}
morning_time={wiz.morningTime}
...
```

Kein `$effect`, kein `saveController`-Aufruf, kein `onTripUpdate` — die
Persistenz übernimmt ausschließlich `CompareEditor.handleSave()` (Edit) bzw.
`wiz.saveNewPreset()` (Create), wie bisher. Grund (Kontext-Doku Punkt 3):
Doppel-Mount Desktop+Mobile würde bei Self-Save zu zwei konkurrierenden
Debounce-Timern führen; Create hat keine Preset-ID für einen PUT.

Die Laufzeit-Sektion bindet `value={wiz.endDate}` /
`onChange={(v) => (wiz.endDate = v)}` an `VTLaufzeitVergleich`.

Die Alert-Zustellung (`VT_AlertDelivery`-Äquivalent) bindet
`AlertCooldownCard`/`AlertQuietHoursCard` per `bind:cooldown_minutes={wiz.alertCooldownMinutes}`
etc. — identisch zum bisherigen Muster in `CompareAlarmSection.svelte`, nur
der Wohnort der Karten ändert sich.

**`activation`-Snippet (1:1 JSX):** `VersandTab` bekommt eine optionale
Svelte-5-Snippet-Prop `activation?: Snippet`, gerendert als letztes Element
der Sektions-Spalte (wie im JSX `{activation && <div>{activation}</div>}`).
`CompareEditor` übergibt das bestehende Aktivierungs-Banner-Markup
(`compare-step5-activation-banner`) als Snippet — Inhalt/Verhalten
unverändert, nur der Mount-Ort wechselt von `Step5Versand` in den
`VersandTab`-Slot. Der bereits bestehende `display:none`-DOM-Anker für den
AC-5-`isAttached()`-Test (CompareEditor Z.610-619) bleibt unverändert an
seiner heutigen Stelle (unabhängig vom aktiven Tab gerendert).

### 2. Sektionen vergleich (Design-Reihenfolge)

1. **Briefing-Kanäle** — `VTBriefingChannels` (bestehende Gating-/Hint-Logik
   aus Scheibe 1 wiederverwendet: `/api/auth/profile`-Fetch, Disabled-Hinweise
   bei fehlender Mail/Telegram-Chat-ID/SMS-Nummer). `sendTelegram`/`sendSms`
   binden an die bestehenden Preset-Felder; E-Mail-Checkbox bindet an
   `wiz.sendEmail` wie in `Step5Versand` heute (**vorbestehende Lücke,
   unverändert**: `ComparePreset` hat kein `send_email`-Feld, der Toggle
   wurde nie persistiert — s. KL-6, nicht Gegenstand dieser Scheibe).
2. **Briefing-Zeitplan** — `VTSchedulePlan` mit `context="vergleich"`:
   Morgen-/Abend-Karte identisch zum Trip (`<input type="time">`,
   `morning-master-switch`/`evening-master-switch`/`report-morning-time`/
   `report-evening-time`), bindet an `wiz.morningEnabled/wiz.morningTime/
   wiz.eveningEnabled/wiz.eveningTime`. Beschriftungs-Hinweis „Morgen = heute,
   Abend = morgen" (Intro-Copy aus JSX, nur `context="vergleich"`).
   Mehrtages-Trend-Karte wird ausgeblendet (KL-2). Warnbox
   `briefings-channel-empty` „Kein Kanal aktiv" erscheint wie im route-Zweig,
   wenn `send_email/sendTelegram/sendSms` alle aus sind.
3. **Laufzeit** — `VTLaufzeitVergleich`: Segmented „Bis auf Weiteres" (id
   `open`) / „Bis Datum" (id `date`), bindet `wiz.endDate`
   (`null` = unbegrenzt, `"YYYY-MM-DD"` = Datum). Testids:
   `compare-versand-enddate-open`, `compare-versand-enddate-date`,
   `compare-versand-enddate-input`. Wechsel von „Bis Datum" zurück auf
   „Bis auf Weiteres" setzt `wiz.endDate = null` — der Payload-Builder
   übersetzt `null` beim Speichern in den Lösch-Sentinel `end_date: ""`
   (s. Punkt 5). Wechsel von „Bis auf Weiteres" auf „Bis Datum" ohne
   Datumsauswahl belässt `wiz.endDate` auf `null`, bis der Nutzer ein Datum
   wählt (kein Auto-Fülldatum) — Speichern in diesem Zwischenzustand sendet
   `end_date: ""` (kein Sentinel-Effekt, da ohnehin `null`).
4. **Alert-Zustellung** — `AlertCooldownCard` + `AlertQuietHoursCard`
   (`bind:cooldown_minutes={wiz.alertCooldownMinutes}`,
   `bind:quiet_from={wiz.alertQuietFrom}`, `bind:quiet_to={wiz.alertQuietTo}`)
   + `VTAlertSample` (statisch, `context="vergleich"`, Zeilen „Wind (Mittel)"/
   „Neuschnee"/„Sichtweite" mit Orts-Subjekten aus dem JSX-Sample). KEIN
   `AlertChannelPicker`-Neubau (KL-4), KEIN `AlertPreviewCard`/Compare-Endpoint
   (kein Live-Preview-Datenmodell für Vergleiche vorhanden).
5. **activation-Slot** — Create-Banner (`compare-step5-activation-banner`)
   unverändert.

### 3. Rest-Felder → `CompareReportContentSection` (Layout-Tab)

Extrahiert aus `Step5Versand.svelte`, alle Testids unverändert:

- Info-Kacheln (`compare-step5-timewindow-tile`, `compare-step5-horizon-tile`)
  bleiben unverändert. Die dritte Info-Kachel `compare-step5-schedule-tile`
  zeigte bisher `state.schedule`-basiert einen festen Uhrzeit-Wert
  („07:00 Uhr"/„18:00 Uhr", „täglich"). Da `state.schedule` ab sofort NUR
  noch Pause-Semantik trägt (2a) und die tatsächlichen Sendezeiten in
  `wiz.morningTime`/`wiz.eveningTime` liegen, zeigt die Kachel jetzt die
  aktiven Slot-Zeiten (`"07:00 · 18:00"` bei beiden aktiv, nur die aktive bei
  einem Slot, `"—"` bei keinem aktiven Slot), Sub-Label „Slots" statt
  „täglich" (Judgment Call — kein Datenverlust, keine Verhaltensänderung am
  Versand selbst, nur an der Anzeige).
- Horizont (`compare-step5-forecast-hours`), Zeitfenster
  (`compare-step5-time-window-start/-end`, `compare-step5-time-overlap-error`),
  Stundenverlauf (`compare-step5-topn`, `compare-step5-hourly-metrics`,
  `compare-step5-hourly-metric-{key}`), `official_alerts_enabled`-Toggle
  (`compare-step5-official-alerts-toggle` — Content-Flag „amtliche
  Warnquellen im Vergleich abfragen", KEINE Versand-Zustell-Kategorie, daher
  hier statt in `VT_AlertDelivery` — Judgment Call) und
  `hourly_enabled`-Toggle (`compare-step5-hourly-enabled-toggle`) ziehen
  unverändert in die neue Komponente.
- Die **Versandzeit-Buttons** (`compare-step5-schedule`,
  `state.schedule = 'daily_morning'|'daily_evening'`) entfallen ersatzlos.
  Auswirkungsfrei: `wiz.schedule` bleibt auf seinem Default
  `'daily_morning'`, das in `saveNewPreset()` ohnehin nur auf den
  Pause-Wert `'daily'` (= aktiv) abbildet — beide Buttons mappten
  bisher auf denselben Pause-Wert, ihr Entfernen ändert also keinerlei
  gespeichertes Verhalten (nur die tote UI verschwindet).
- `CompareReportContentSection` wird an das Ende von `Step4Layout.svelte`
  gemountet (Zwischenlösung bis Scheibe 3 den echten LayoutTab-Organism
  baut).

### 4. `CompareAlarmSection.svelte` — Reduktion

Bleibt: Heading „Alarme · Sofort-Meldung", `compare-alarm-radar-toggle`,
`compare-alarm-official-toggle`, `AlertMetricLevelTable`
(Korridor-Vorstufe #1231). Entfernt: `AlertCooldownCard`/
`AlertQuietHoursCard` inkl. `.extra-cards`-Grid-Styles (ziehen in
`VersandTab`).

### 5. Save-Pfad + End-Datum-Sentinel

`CompareEditorEdits` (compareEditorSave.ts) bekommt:

```ts
morningEnabled?: boolean;
morningTime?: string;   // "HH:MM"
eveningEnabled?: boolean;
eveningTime?: string;   // "HH:MM"
endDate?: string | null; // undefined = unangetastet (Round-Trip),
                         // null = "bis auf Weiteres" (Lösch-Sentinel → sendet ""),
                         // string = "YYYY-MM-DD"
```

`buildComparePresetSavePayload` ergänzt analog zum bestehenden
Round-Trip-Muster:

```ts
...(edits.morningEnabled !== undefined ? { morning_enabled: edits.morningEnabled } : {}),
...(edits.morningTime !== undefined ? { morning_time: edits.morningTime } : {}),
...(edits.eveningEnabled !== undefined ? { evening_enabled: edits.eveningEnabled } : {}),
...(edits.eveningTime !== undefined ? { evening_time: edits.eveningTime } : {}),
...(edits.endDate !== undefined ? { end_date: edits.endDate === null ? '' : edits.endDate } : {}),
```

`CompareEditor.svelte` (`handleSave`) snapshottet die 5 neuen Felder analog
zu den bestehenden Alarm-Feldern (siehe Z.180-191-Muster) und reicht sie in
`buildComparePresetSavePayload` durch; `initial`-Snapshot + `dirty`-Derive
werden um dieselben 5 Felder erweitert (Muster Z.77-115).

`compareWizardState.svelte.ts::saveNewPreset()` bekommt die 5 Felder mit
Neu-Preset-Defaults (identisch zur Go-POST-Default-Tabelle aus Scheibe 2a):
`morning_enabled: true, morning_time: '07:00:00', evening_enabled: false,
evening_time: '18:00:00'`; `end_date` wird nur gesendet, wenn
`wiz.endDate` gesetzt ist (kein Sentinel nötig beim Create — Feld ist noch
nie gesetzt).

**Backend-Ausnahme (End-Datum-Lösch-Sentinel, ~5 LoC):**
`internal/handler/compare_preset.go` (`UpdateComparePresetHandler`, nach dem
bestehenden Nil-Preserve-Block, vor `validateComparePreset`):

```go
if updated.EndDate != nil && *updated.EndDate == "" {
    updated.EndDate = nil
}
```

Ein fehlendes Feld im Request-Body bleibt Nil-Preserve (Original bleibt
erhalten); ein explizit gesendeter Leerstring löscht das Datum. Die
bestehende Validierung (`validateComparePresetEndDate`) prüft `nil` bereits
als „kein Fehler" — kein weiterer Anpassungsbedarf. Neuer Handler-Test:
GIVEN ein Preset mit gesetztem `end_date` WHEN PUT mit `end_date: ""`
THEN ist `EndDate` danach `nil`.

### 6. Testid-Präfix-Parametrisierung (`VTBriefingChannels`)

Bestehende Compare-Playwright-Specs (`issue-609-sms-profil.spec.ts` AC-6 u.a.)
erwarten `compare-step5-channel-{email,telegram,sms}`, während `VTBriefingChannels`
(Scheibe 1, route) `channel-{email,telegram,sms}` verwendet. Damit die
bestehende Gating-/Hint-Logik (Fetch `/api/auth/profile`, Disabled-Hinweise)
wiederverwendet werden kann UND die bestehenden Compare-Testids erhalten
bleiben (Punkt 6 im Auftrag: „Selektoren unverändert"), bekommt
`VTBriefingChannels` optionale Testid-Override-Props
(`emailTestid`/`telegramTestid`/`smsTestid`, Default = `channel-*`).
`VersandTab` reicht im vergleich-Zweig `compare-step5-channel-email`/
`-telegram`/`-sms` durch; der route-Zweig bleibt unverändert (keine Prop
übergeben → Default greift).

## Test Plan

### Automated Tests (TDD RED)

- [ ] node:test (compareEditorSave): GIVEN ein Preset mit gesetzten Slot-Feldern WHEN `buildComparePresetSavePayload` ohne diese Edits aufgerufen wird THEN bleiben die 5 Werte im Body identisch zum Original (Round-Trip).
- [ ] node:test (compareEditorSave): GIVEN `edits.endDate = null` (Preset hatte ein gesetztes `end_date`) WHEN der Payload gebaut wird THEN enthält der Body `end_date: ""`.
- [ ] node:test (compareEditorSave): GIVEN `edits.endDate = '2026-09-01'` WHEN der Payload gebaut wird THEN enthält der Body `end_date: '2026-09-01'`.
- [ ] node:test (compareEditorSave): GIVEN `edits.morningTime = '08:15'` und die übrigen 4 Slot-Edits `undefined` WHEN der Payload gebaut wird THEN wird NUR `morning_time` überschrieben, die anderen 4 Felder kommen unverändert aus `original`.
- [ ] Go-Handler: GIVEN ein Preset mit gesetztem `end_date="2026-08-01"` WHEN PUT mit Body `{"end_date": ""}` (restliche Felder unverändert) THEN ist `EndDate` nach dem Save `nil` und die Datei zeigt keinen `end_date`-Key mehr (`omitempty`).
- [ ] Go-Handler: GIVEN ein Preset mit gesetztem `end_date` WHEN PUT ohne `end_date`-Feld im Body THEN bleibt `EndDate` unverändert (Nil-Preserve weiterhin intakt, keine Regression durch den Sentinel).
- [ ] Playwright (`versand-tab-vergleich.spec.ts`): GIVEN der Compare-Editor (Edit) ist offen WHEN der Tab „Versand" geklickt wird THEN sind die 4 Sektionen in Design-Reihenfolge sichtbar (Kanäle → Zeitplan → Laufzeit → Alert-Zustellung), Desktop UND Mobile (`:visible`).
- [ ] Playwright: GIVEN der Versand-Tab ist offen und mindestens ein Kanal aktiv WHEN Uhrzeit im Morgen-Feld geändert und „Speichern" geklickt wird THEN persistiert `morning_time` und ist nach Reload korrekt gesetzt.
- [ ] Playwright: GIVEN ein Preset mit gesetztem `end_date` WHEN „Bis auf Weiteres" gewählt und gespeichert wird THEN ist `end_date` nach Reload `null`/nicht mehr vorhanden.
- [ ] Playwright: GIVEN „Bis auf Weiteres" ist aktiv WHEN „Bis Datum" gewählt und ein Datum gesetzt + gespeichert wird THEN ist `end_date` nach Reload das gewählte Datum.
- [ ] Playwright: GIVEN der Versand-Tab ist offen WHEN Cooldown-Minuten geändert und gespeichert werden THEN persistiert der Wert; der Alarme-Tab zeigt KEINE Cooldown-Karte mehr, aber weiterhin die Empfindlichkeits-Tabelle.
- [ ] Playwright: GIVEN alle Briefing-Kanäle sind aus WHEN der Versand-Tab betrachtet wird THEN erscheint die Warnbox „Kein Kanal aktiv" statt der Zeitplan-Karten.
- [ ] Playwright: GIVEN der Create-Wizard erreicht den Versand-Tab WHEN Kanal + Zeitplan konfiguriert und „Briefing aktivieren" geklickt wird THEN enthält der POST-Body die 5 Slot-Felder mit den gewählten Werten.
- [ ] Playwright: GIVEN der Versand-Tab hat unsaved Änderungen WHEN „Verwerfen" bestätigt wird THEN springen alle 5 Slot-Felder auf den zuletzt gespeicherten Stand zurück.
- [ ] Playwright (angepasste Bestandsspecs): `issue-763-step5-select.spec.ts`, `issue-1134-compare-timewindow-save.spec.ts`, `compare-editor-slice4.spec.ts` navigieren zu `compare-editor-tab-layout` für die umgezogenen Rest-Felder; Selektoren selbst bleiben `compare-step5-*`.

### Fixtures

- Kern-Schicht: node:test ohne Browser/Netz (reine Payload-Funktionen); Go-Test mit In-Memory-Store-Fixture (kein Netz).
- Playwright: Staging, echte Preset-Anlage via `/api/compare/presets` (kein Mock).

## Acceptance Criteria

**AC-1:** Given der Compare-Editor (Edit-Modus) ist geöffnet / When ich den Tab „Versand" öffne / Then sehe ich die vier Versand-Sektionen in Design-Reihenfolge: Briefing-Kanäle → Briefing-Zeitplan → Laufzeit → Alert-Zustellung.
  - Test: Playwright-Klick auf `compare-editor-tab-versand`, alle vier Sektions-Container `:visible`.

**AC-2:** Given der Versand-Tab ist offen und mindestens ein Kanal aktiv / When ich Uhrzeit oder Schalter der Morgen- oder Abend-Karte ändere und auf „Speichern" klicke / Then werden `morning_enabled`/`morning_time`/`evening_enabled`/`evening_time` über den zentralen Save-Button persistiert und sind nach einem Seiten-Reload korrekt wieder angezeigt.
  - Test: Playwright ändert Uhrzeit, klickt `compare-editor-save`, reloadet, prüft Feldwert.

**AC-3:** Given ein Preset mit gesetztem Laufzeit-Ende / When ich in der Laufzeit-Sektion „Bis auf Weiteres" wähle und speichere / Then ist das Enddatum nach Reload gelöscht (unbegrenzte Laufzeit); umgekehrt setzt „Bis Datum" + Datumsauswahl + Speichern das Enddatum reload-fest — inklusive des Backend-Lösch-Sentinels (`end_date: ""`).
  - Test: Playwright Rundtrip beide Richtungen; Go-Handler-Test für den Sentinel isoliert.

**AC-4:** Given der Compare-Editor (Edit-Modus) ist geöffnet / When ich Cooldown-Minuten oder Stille-Stunden im Versand-Tab ändere / Then persistieren sie wie bisher; der Alarme-Tab enthält diese Controls NICHT mehr, zeigt aber weiterhin Radar-/Official-Toggle und die Metrik-Level-Tabelle. *(revidiert 2026-07-15 durch #1258 AC-18, s. Changelog)*
  - Test: Playwright — Cooldown-Karte NUR im Versand-Tab sichtbar, Alarme-Tab zeigt `alert-metric-level-table`, aber kein `alert-cooldown-card`.

**AC-5:** Given der Compare-Editor ist geöffnet / When ich den Layout-Tab öffne / Then sind Zeitfenster, Horizont, Top-N, Stundenverlauf-Toggle+Metriken editierbar, Werte persistieren wie bisher, und alle `compare-step5-*`-Testids existieren unverändert (nur neuer Parent-Tab).
  - Test: Playwright navigiert zu `compare-editor-tab-layout`, prüft bestehende Selektoren.

**AC-6:** Given der Create-Wizard (Compare) erreicht den Versand-Tab / When Kanal, Zeitplan konfiguriert und „Briefing aktivieren" geklickt wird / Then funktioniert der Aktivierungs-Banner wie bisher und der POST-Body an `/api/compare/presets` enthält die 5 Slot-Felder.
  - Test: Playwright prüft Request-Body von `POST /api/compare/presets`.

**AC-7:** Given kein Briefing-Kanal ist aktiv / When ich den Versand-Tab betrachte / Then erscheint statt der Zeitplan-Karten die Warnbox „Kein Kanal aktiv".
  - Test: Playwright deaktiviert alle 3 Kanäle, prüft `briefings-channel-empty`.

**AC-8:** Given der Versand-Tab hat unsaved Änderungen / When ich „Verwerfen" bestätige / Then werden alle Felder (inkl. der 5 Slot-Felder) auf den zuletzt gespeicherten Stand zurückgesetzt.
  - Test: Playwright ändert Werte, klickt Verwerfen-Bestätigung, prüft Rückstellung.

**AC-9:** Given die bestehenden `compare-step5-*`/`compare-alarm-*`-Testids / When die Seite gerendert ist / Then existieren sie unverändert (nur anderer Parent-Tab), auf Desktop UND Mobile konsistent (Doppel-Mount, `:visible`).
  - Test: Playwright prüft dieselben Selektoren in `.cm-desktop` und `.cm-mobile`.

**AC-10:** Given der mobile Viewport / When ich den Versand-Tab nutze / Then sind alle Sektionen einspaltig bedienbar, ohne horizontales Scrollen.
  - Test: Playwright, Viewport ≤899px, `page.evaluate` auf `document.documentElement.scrollWidth <= clientWidth`.

**AC-11:** Given die Umsetzung ist fertig / When man API-Endpunkte und Datenmodell vergleicht / Then ist außer dem End-Datum-Lösch-Sentinel (~5 LoC + Test in `internal/handler/compare_preset.go`) keine Backend-/API-Änderung vorgenommen worden.
  - Test: Diff-Review — nur die eine benannte Go-Datei + ihr Test außerhalb `frontend/src` verändert.

## Known Limitations

- **KL-1 · Kanal-Chips je Karte entfallen weiterhin:** Wie in Scheibe 1 — kein Backend-Feld für per-Briefing-Kanal-Auswahl. Die globale Kanalwahl (Sektion 1) gilt für beide Briefings.
- **KL-2 · Mehrtages-Trend-Karte entfällt im vergleich-Kontext:** Kein `multi_day_trend`-Feld am `ComparePreset` — das Design zeigt die Trend-Karte nur für `route`.
- **KL-3 · Checkboxen statt Design-Switches:** Bestehende Testid-/Suite-Erhalt-Entscheidung aus Scheibe 1, unverändert übernommen.
- **KL-4 · Alert-Kanalwahl bleibt E-Mail-only:** Bewusste Bestandsentscheidung (`CompareAlarmSection`, #1169) — kein `AlertChannelPicker`-Neubau, obwohl das JSX-Design ihn für beide Kontexte zeigt.
- **KL-5 · Mail-Footer-Label (2a-KL-3) wird hier NICHT angefasst:** separater Renderer-Pfad (Mail-Gate-relevant) — bei Bedarf eigene Folge-Scheibe.
- **KL-6 · E-Mail-Kanal-Checkbox bleibt unpersistiert (vorbestehende Lücke):** `ComparePreset` hat kein `send_email`-Feld; die E-Mail-Checkbox in `Step5Versand` war schon vor dieser Scheibe rein clientseitig ohne Backend-Wirkung. Diese Scheibe übernimmt das Verhalten unverändert (kein neuer Bug, keine Behebung — außerhalb des beauftragten Scopes).
- **KL-7 · Info-Kachel „Versand" zeigt jetzt Slot-Zeiten statt fixem Enum-Wert:** Judgment Call (s. Implementation Details Punkt 3) — kosmetische Anpassung der Kachel-Anzeige, kein neues Datenfeld, kein AC-Verstoß.
- **KL-8 · LoC-Limit deutlich überschritten:** Produktivcode ~650-850 LoC + ~250-300 LoC Tests — weit über dem 250-LoC-Standardlimit. Grund: Bindung an ein bereits live Backend-Modell (2a) über sechs bestehende + zwei neue Frontend-Bausteine plus Anpassung von fünf bestehenden Playwright-Specs. Override wird vor Phase 6 explizit beim PO eingeholt (`workflow.py set-field loc_limit_override`), nicht eigenmächtig gesetzt.

## Edge Cases

| Fall | Verhalten |
|---|---|
| Doppel-Mount Desktop/Mobile | Beide Instanzen binden an denselben `wiz`-State; Änderung in einer Instanz sofort in der anderen sichtbar (kein eigener Save-Zustand pro Instanz) |
| `end_date` in der Vergangenheit gesetzt | Kein zusätzlicher „abgelaufen"-Hinweis im UI (JSX zeigt keinen solchen State) — Dispatch-seitiger Skip läuft bereits über Scheibe 2a (AC-7 dort); reine Anzeige bleibt neutral |
| Create ohne Kanalwahl | Aktivierungs-Banner bleibt im „nicht bereit"-Zustand (`data-ready="false"`), Zeitplan-Sektion zeigt die Kein-Kanal-Warnbox — unverändert zu heute |
| Preset mit `schedule="manual"` (pausiert) im Editor | Versand-Tab bleibt voll editierbar (Pause ist unabhängig vom Zeitplan-Inhalt — Reaktivierung nutzt `previous_schedule`, unberührt von dieser Scheibe) |
| Wechsel „Bis Datum" → „Bis auf Weiteres" ohne vorheriges Speichern, dann direkt „Bis Datum" zurück | Lokaler `wiz.endDate` verliert das zuvor eingegebene Datum (kein Zwischenspeicher) — Nutzer muss das Datum erneut wählen, bevor gespeichert wird (kein Datenverlust am Server, nur UI-Zustand vor dem Speichern) |
| Testids doppelt im DOM (Mobile+Desktop) | Playwright nutzt `:visible` (etabliertes Muster) |

## Out of Scope

- LayoutTab-Organism (Scheibe 3) — `CompareReportContentSection` ist eine Zwischenlösung, kein finaler Organism.
- `briefings[]`-Reshape / echtes `BriefingSubscription`-Modell (Epic #29 Phase 3).
- Mail-Footer-Label-Update (2a-KL-3/KL-5 hier).
- Trip-Editor (`context="route"`, bereits live seit Scheibe 1).
- Tab-Umbenennung „Idealwerte" → „Wertebereiche" (Epic #1231, Korridor-Editor).
- `AlertChannelPicker`-Einführung für Compare-Alarme (KL-4).
- Jegliche Python-/Go-Scheduler-Änderung über den einen benannten Sentinel-Fix hinaus (bereits Gegenstand von Scheibe 2a).

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** keine
- **Rationale:** Fortführung des in Scheibe 1 etablierten Organism-Musters (geteilte Komponente mit `context`-Prop); der End-Datum-Sentinel folgt dem bereits im Projekt etablierten Pointer-Merge-Muster (vgl. Sammel-Issue #1199, PUT-null-Semantik) — keine neue Architekturentscheidung.

## Test-Nachweis

- Kern: node:test (compareEditorSave, Payload-Builder, kein Netz/Browser) + Go-Test (Handler-Sentinel, In-Memory-Store) — 100% grün als Commit-Gate.
- RED-Phase: FE-Testdateien sind per `edit_gate` in RED gesperrt (mark-red-Mechanismus); Go-Test analog.
- Staging-E2E (`/60-validate`): Playwright gegen echten Compare-Preset (kein Mock), Tab-Klick-Pfad, `:visible`; Fresh-Eyes gegen `soll-29b-desktop-versand-vergleich.png` + `soll-29b-mobile.png`.
- Mail-Renderer/Mail-Validator sind NICHT betroffen (kein Renderer-Datei-Touch in dieser Scheibe) — Renderer-Commit-Gate #811 greift nicht.

## Changelog

- 2026-07-15: **AC-4 revidiert** durch #1258 AC-18 (Programm-Abschluss-
  Dokupflicht, AC-23): die Alert-Zustellung (Cooldown, Stille Stunden,
  amtliche-Warnungen-Toggle, Metrik-Level-Tabelle, Beispiel-Warnung) ist
  aus dem Versand-Tab in den neuen, geteilten Alarme-Tab (`AlarmeTab.svelte`,
  #1258 S4) umgezogen — der Versand-Tab trägt seither nur noch das
  geplante Briefing (Kanäle, Zeitplan, Laufzeit). AC-4-Wortlaut bleibt
  unverändert stehen (Historie), Markierung am Punkt selbst.
- 2026-07-12: Initial spec created
- 2026-07-12 (vor Freigabe): `## Expected Behavior` ergänzt (Input/Output/Side effects) — Pflicht-Sektion aus dem Template nachgetragen (spec-validator-Fund), keine inhaltliche Änderung an Scope/ACs.
