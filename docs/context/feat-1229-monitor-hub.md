# Context: feat-1229-monitor-hub

## Request Summary

Issue #1229 (Phase 2 von Epic #1230) — Rest-Umfang: Die Compare-Hub/Monitor-Ansicht
(`/compare/[id]`) neutralisieren (kein Ranking/Score) und auf Briefing-Uhrzeiten
umstellen (statt „Rhythmus & Vorausschau"). Der Editor-Pfad ist bereits durch
#1231/#1232 geliefert; Rest-Scope-Vermessung: Kommentar 2026-07-13 in #1229
(https://github.com/henemm/gregor_zwanzig/issues/1229#issuecomment-4956746222).

## Offener Rest (aus der Ist-Vermessung)

1. Hub · Versand-Tab: „Rhythmus & Vorausschau" → „Briefing-Zeiten" (Morgen = heute ·
   Abend = morgen) + „kein Enddatum"-Hinweis — AC 5 (PO-korrigierte Fassung).
2. Hub · Monitoring-Streifen: Stat „Briefings" mit Uhrzeiten statt
   `presetScheduleLabel`/`hour_from–hour_to` — AC 6.
3. Hub · Copy „…Metriken bestimmen das Ranking" neutralisieren — AC 2.
4. Hub · Briefing-Vorschau: V1-Pfad mit Rang+Score (`CompareSmsPreview`) ersetzen — AC 2/7.
5. Aufräumen: `hour_from`/`hour_to`/`schedule`-Rest-Surface in Labels/Helpers +
   toter `RecommendationBanner.svelte` — AC 1/2.

## Related Files

| File | Relevance |
|------|-----------|
| `frontend/src/lib/components/compare/CompareTabs.svelte` (800 Z.) | Zentrum der Änderung. 6 Tabs (Z.60-67): Übersicht Z.214-308 (Monitoring-Streifen Z.219-257, SummaryCards Z.265-295), Orte Z.310-325, Wertebereiche Z.327-346, Layout Z.348-354, Versand Z.356-442 (read-only DetailRows „Zeitplan/Zeitfenster/Nächster Versand" Z.364-366), Vorschau Z.444-523 (`CompareBriefingPreview` Z.514-519). Ranking-Copy Z.277. Save-Logik nur `handleToggleActive()` Z.176-190 (PUT Full-Preset!) + `handleSend()` Z.153-167. |
| `frontend/src/lib/components/compare/CompareDetail.svelte` | Thin-Shell (20 Z.), reicht `preset/locations/initialTab` durch (Z.19). |
| `frontend/src/routes/compare/[id]/+page.svelte` | Route; nutzt ebenfalls `presetScheduleLabel`. |
| `frontend/src/lib/components/compare/subscriptionHelpers.ts` | `presetScheduleLabel` Z.63-69 (daily → „Täglich hour_from–hour_to"), `presetTileScheduleLabel` Z.158-167, `formatNextSend`/`formatLastSent`/`relativeLastSent`. Neue Ableitung aus `morning_/evening_enabled+time` nötig („Morgen 07:00 · Abend 18:00"). Konsumenten: CompareTabs, CompareTile, AutoReportCard, compare/[id]/+page.svelte; Tests `__tests__/issue_582_list_helpers.test.ts`. |
| `frontend/src/lib/components/shared/versand-tab/VTSchedulePlan.svelte` (241 Z.) | Geteilter Organism aus #1232. Rein präsentational/controlled: Props `context`, `hasActiveChannel`, 4 Wert-Props (`morning_enabled/time`, `evening_enabled/time`), 6 Callbacks; KEIN Store, KEIN API. `context="vergleich"` (Z.65-70) ohne Mehrtages-Trend. Direkt im Hub einbettbar, wenn Hub Werte + Persistenz hält. Testids: `report-morning-time`, `report-evening-time`, `morning-master-switch`, `evening-master-switch`, `briefings-channel-empty`. |
| `frontend/src/lib/components/shared/versand-tab/VTLaufzeitVergleich.svelte` | „Der Versand läuft ohne Enddatum weiter."-Hinweis (Z.76), Testid `briefings-laufzeit-vergleich`. |
| `frontend/src/lib/components/shared/layout-tab/LTComparePreview.svelte` | Neutrale Vorschau (kein Rang/Score, Header Z.1-13). Props-only (`channel`, `pickedIds`, `idealRanges`), Datenquelle statische Demo-Zeilen (`selectPreviewRows`, KL-3), kein API-Call. Kandidat als Ersatz für V1-SMS-Preview im Hub. Bisher nur in `steps/Step4Layout.svelte`. |
| `frontend/src/lib/components/molecules/CompareBriefingPreview.svelte` (34 Z.) | Dispatcher Kanal→`CompareChatBubble`/`CompareSmsPreview`/`ComparePreviewMissing`; braucht `profile`+`data`, wird im Hub OHNE gemountet → rendert faktisch „missing". Echte E-Mail-Vorschau kommt aus iframe `/api/_validator/compare-email-preview` (CompareTabs.svelte:131-136). |
| `frontend/src/lib/components/molecules/CompareSmsPreview.svelte` (78 Z.) | V1: erwartet `data.rows[]` mit `rank`+`score` (Z.15-20), rendert „1.Ort score(val)" (Z.48) — Ranking-behaftet, zu ersetzen/entfernen. Hat ≤140-Zähler (Z.7,58,75). |
| `frontend/src/lib/components/compare/RecommendationBanner.svelte` | Toter Code („Empfehlung", Winner-Score) — nirgends importiert; Lösch-Kandidat. |
| `frontend/src/lib/types.ts` (Z.387-410, 497-528) | `RankingEntry`/`ranking`-Types + ComparePreset-Felder (`schedule`, `hour_from/hour_to`, `forecast_hours`, `morning_*`, `evening_*`, `end_date`). |
| `frontend/src/lib/components/compare/compareEditorSave.ts` | `buildComparePresetSavePayload` Z.152-156: Persistenz-Vorbild für `morning_enabled/time`, `evening_enabled/time` (via `toHHMMSS`), `end_date`; Round-Trip-Spread aus `original`. |
| `internal/model/compare_preset.go` | Slot-Felder Z.84-88 (`MorningEnabled/MorningTime/EveningEnabled/EveningTime/EndDate`); Alt-Felder Z.24-33 (`Schedule`, `PreviousSchedule`, `HourFrom/HourTo`, `ForecastHours`, `Weekday` deprecated). |
| `src/services/compare_slot_scheduler.py` | Backend-Versand bereits slot-basiert (`resolve_preset_slots` Z.46-98) — Backend braucht für diesen Rest KEINE Änderung. |

## Design-SOLL (kanonisch)

`claude-code-handoff/current/jsx/screen-compare-detail.jsx` (437 Z., `CHub_`):

- Header-Direktive Z.13-15: stehender Monitor, Briefing-Uhrzeiten (Morgen=heute ·
  Abend=morgen), KEIN Zeitfenster/Rhythmus, KEIN Ranking/Score.
- `CHub_OverviewTab` Z.130-153: FÜNF Stats — Status · Nächster Versand ·
  **Briefings** (Z.145, neu ggü. IST) · Zuletzt raus · Kanäle.
- Idealwerte-SummaryCard Z.163-167: „Kein Score, kein Ranking."
- `CHub_SendTab` Z.268-328: Sektion „Briefing-Zeiten" (Z.282), DetailRows
  „Briefings"/„Nächster Versand" (Z.284-285) + `CHub_EditIcon` (Bearbeiten-Stift);
  Kanal-Toggle-Liste Z.289-310; Aktivierungs-Card Z.313-325.
- `CHub_PreviewTab` Z.331-391: `CompareChannelSwitch` + Email-View-Toggle +
  `CompareBriefingPreview` (Z.380-386).

## Existing Patterns

- **Geteilter Organism, controlled Props** (#1232): VTSchedulePlan wird im Editor
  über `shared/VersandTab.svelte` gemountet, Persistenz zentral im Editor-Save
  (PUT `/api/compare/presets/{id}`). Gleiches Muster im Hub möglich.
- **Neutrale Vorschau props-only** (LTComparePreview, KL-3 statische Demo-Zeilen).
- **Hub-Save-Vorsicht:** `handleToggleActive` PUT-tet das GANZE preset-Objekt
  (`{...preset, schedule…}`) — Full-Replace-Muster! Bei neuen Hub-Saves
  Read-Modify-Write-Regel beachten (#1159, BUG-DATALOSS-GR221).

## Dependencies

- Upstream: ComparePreset-API (Go, PUT `/api/compare/presets/{id}`), Slot-Felder
  aus #1232 — vorhanden, keine Backend-Änderung nötig.
- Downstream: `presetScheduleLabel`-Konsumenten (CompareTile, AutoReportCard,
  Liste) zeigen ebenfalls noch Rhythmus-Sprache — Scope-Frage für Analyse:
  mitziehen oder nur Hub?

## Existing Specs

- `docs/specs/modules/issue_517_compare_hub.md` — Grundlagen-Spec des 6-Tab-Hubs.
- `docs/specs/modules/versand_tab_vergleich.md` — #1232 Versand-Organism (Vorbild).
- `docs/specs/modules/versand_tab_route.md` — VTSchedulePlan-Ursprung.
- `docs/specs/modules/layout_tab_vergleich.md` — LTComparePreview-Neutralität.
- `docs/specs/modules/issue_646_compare_detail_fidelity.md`, `issue_514_compare_vorschau_tab.md`, `issue_627_631_compare_send_rhythm.md` — Alt-Stände des Hubs.
- #1229 hat noch KEINE eigene Spec-Datei — entsteht in Phase 3 (Spec).

## Analysis

### Type
Feature (Design-Compliance-Rest aus #1229; PO-Entscheidung liegt vor, JSX ist Wahrheit)

### Technical Approach (Empfehlung Plan-Agent, 2026-07-13)

1. **Versand-Tab = Anzeige + Absprung, KEIN Inline-Edit.** JSX `CHub_SendTab` zeigt
   read-only DetailRows „Briefings"/„Nächster Versand" mit Edit-Stift (Z.284-285);
   der `CHub_EditIcon` (Z.428-434) hat bewusst keinen In-Hub-onClick → externer
   Sprung in den Editor. Dafür Editor-Deep-Link `?tab=versand` nachrüsten
   (CompareEditor.svelte:93 initialisiert `activeTab` fix; `switchTab` ist im
   Edit-Modus ungegated → kleiner additiver Fix nach dem Muster
   `compare/[id]/+page.svelte:32`). Kein neuer Hub-Save → Full-Replace-Risiko umgangen.
2. **Stat „Briefings":** neue Ableitung `presetBriefingTimesLabel(preset)` in
   `subscriptionHelpers.ts` aus `morning_/evening_enabled+time` →
   `"Morgen 06:30 · Abend 18:00"` / `"—"` (Mock-SOLL: `mock-locations.jsx:123/148/173/197`).
   Zeiten `HH:MM` (Backend liefert `HH:MM:SS`).
3. **Ranking-Copy-Swap** (CompareTabs.svelte:277): Zieltext 1:1 aus JSX Z.165
   „{n} Metriken mit Idealbereich — im Briefing pro Wert markiert. Kein Score, kein Ranking."
4. **Vorschau-Tab:** JSX behält `CompareBriefingPreview` — kein LTComparePreview-Umbau.
   Fix im Dispatcher (`CompareBriefingPreview.svelte`): telegram/sms-Zweige (Rang+Score,
   faktisch nie mit Daten erreicht) auf `ComparePreviewMissing` umlenken; Molecules
   selbst unangetastet (Design-Fidelity-Tests lesen deren Dateiinhalt).
5. **Aufräumen** (`RecommendationBanner` löschen + 2 Struktur-Tests anpassen,
   `RankingEntry`-Types raus): nur wenn LoC-Budget reicht → Slice 2, sonst #1199.
   `presetScheduleLabel`-Konsumenten außerhalb der Route (CompareTile,
   AutoReportCard, Liste) bleiben AUSSER Scope (eigene Kurz-Copy, nicht Teil des
   JSX-Screens) — als Known Limitation ausweisen. Der Mobile-Zweig derselben Route
   (`compare/[id]/+page.svelte:162-232`, eigenes Stat-Grid!) zieht MIT.

### Affected Files (Kern-Slice S1)
| File | Change | ~LoC |
|------|--------|------|
| `frontend/src/lib/components/compare/subscriptionHelpers.ts` | MODIFY: `presetBriefingTimesLabel()` | +15 |
| `frontend/src/lib/components/compare/CompareTabs.svelte` | MODIFY: Stat, Versand-Tab, Copy | +35/-15 |
| `frontend/src/routes/compare/[id]/+page.svelte` | MODIFY: Mobile-Stat-Zweig | +10 |
| `frontend/src/lib/components/compare/CompareEditor.svelte` | MODIFY: `?tab=`-Deep-Link | +12 |
| `frontend/src/lib/components/molecules/CompareBriefingPreview.svelte` | MODIFY: Dead-Zweige → Missing | +4/-8 |
| `__tests__/issue_582_list_helpers.test.ts` | MODIFY: Vitest neue Ableitung | +30 |
| `frontend/e2e/compare-hub-briefing-times.spec.ts` | CREATE: erste Hub-E2E | +70 |

### Scope Assessment
- Files: 7 (S1) · Estimated LoC: ~185–210 (S1, unter 250) · Slice 2 (Aufräumen): ~50–90
- Risk Level: LOW-MEDIUM (frontend-only, kein Backend; Risiken: Mobile-Duplikat-Zweig,
  Svelte-Whitespace bei Join-Copy, CompareEditor ist 1016 Z. mit Adversary-Historie)

### Slices
- **S1 (Kern, AC 2/5/6):** Versand-Tab + Deep-Link, Stat „Briefings" (Desktop+Mobile), Copy-Swap, Helper+Tests+Hub-E2E.
- **S2 (AC 2/7 + Aufräumen):** CompareBriefingPreview-Dispatcher, RecommendationBanner/RankingEntry löschen (oder #1199, PO-Frage in Freigabe).

### Test-Strategie
Vitest: `presetBriefingTimesLabel` 4 Fälle (beide/nur morning/nur evening/aus→„—").
Playwright-Staging (neu, Muster `versand-tab-vergleich.spec.ts`, echter Klick-Pfad,
`:visible` wegen Desktop+Mobile-Doppel-Mount): Preset per API anlegen → Übersicht-Stat
prüfen → Versand-Tab DetailRow → Edit-Stift → `/edit?tab=versand` aktiv →
Negativ-Assertion „Ranking" auf Idealwerte-Card → Draft zeigt „—" → alle 6
`compare-detail-tab-*`-Testids weiterhin vorhanden (AC 8).

## Risks & Considerations

- **Full-Replace-PUT im Hub** (`handleToggleActive`): Jede neue Hub-Persistenz
  muss Read-Modify-Write folgen; bestehendes Muster nicht kopieren.
- **Editierbarkeit im Hub:** JSX zeigt im SendTab einen Edit-Stift an
  „Briefing-Zeiten" — ob Inline-Edit (VTSchedulePlan einbetten) oder Link in den
  Editor, ist Design-/Analyse-Entscheidung (JSX ist die Wahrheit; DetailRow +
  EditIcon spricht eher für Anzeige + Absprung/Inline-Toggle, kein voller Organism).
- **Keine E2E-Abdeckung des Hubs:** `compare-detail-tab-*`-Testids in keiner Spec
  referenziert → Playwright-Coverage muss mit dieser Arbeit entstehen (AC 8:
  bestehende Testids erhalten).
- **`briefings[]`-Array existiert nicht** — flache Slot-Felder sind der Stand;
  Array-Entscheidung gehört zu Phase 3 (#1250), NICHT hierher.
- Kern-Copy-Stellen außerhalb des Hubs (CompareTile „tägl. HH", Liste) — Scope
  in Analyse klären, sonst bleibt Rhythmus-Sprache sichtbar.
- Vorschau-Tab: E-Mail kommt real aus Validator-iframe; SMS/Telegram-V1-Molecules
  sind faktisch tot verdrahtet (kein `profile`/`data`) — Ersatz durch
  LTComparePreview ODER Entfernen der toten Zweige; Analyse entscheidet.
