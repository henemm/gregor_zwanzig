# Context: fix-1047-mail-content-tab-restore

## Request Summary

Issue #1047 meldet, dass `frontend/e2e/issue-619-mail-elements-ui.spec.ts` und
`frontend/e2e/issue-723-email-tab-eindampfen.spec.ts` vermutlich rot sind, weil sie
auf `?tab=briefings` nach der E-Mail-Inhalt-Karte suchen, die dort seit #736 nicht
mehr gerendert wird (`showMailContent={false}`). Recherche ergab: das Problem ist
größer als reine Test-Drift — seit Commit `f5249782` (#942) fehlt die E-Mail-Inhalt-
Karte (Ausblick/Etappen-Kennzahlen/Vortagesvergleich/Format-Schalter) **komplett**
aus dem Bearbeiten-Modus bestehender Trips (weder im Inhalt- noch im Versand-Reiter
sichtbar). PO-Entscheidung (siehe unten): Karte im Reiter "Wetter-Metriken" (=
"Inhalt", `?tab=weather`) wiederherstellen — ohne die doppelten Zeitplan-Felder,
die #942 eigentlich entfernen wollte —, danach beide Testdateien auf die
tatsächliche Ziel-Oberfläche migrieren (analog zu #971 für issue-774/issue-776).

## PO-Entscheidung (2026-07-06)

Frage: Karte wiederherstellen oder als bewusst entfernt behandeln?
Antwort: **Wiederherstellen, im Reiter "Wetter-Metriken" (nicht "Briefing-Zeitplan")**.

## Related Files

| File | Relevance |
|------|-----------|
| `frontend/src/lib/components/edit/EditReportConfigSection.svelte` | Enthält die E-Mail-Inhalt-Karte (`report-mail-content`, gated durch `showMailContent`) sowie die Morgen-/Abend-Report-Karten (aktuell **ungated**, immer sichtbar sobald die Komponente gemountet wird — das war die Ursache für den #942-"Doppel-UI"-Bug). Braucht eine neue Prop, um die Zeitplan-Karten optional auszublenden. |
| `frontend/src/lib/components/trip-detail/WeatherMetricsTab.svelte` | Reiter "Inhalt" / value `weather`. Import + Einbindung von `EditReportConfigSection` wurde in Commit `f5249782` (#942) komplett entfernt (Zeilen ~624-629 im alten Stand). Muss wiederhergestellt werden, diesmal mit einer Prop, die die Zeitplan-Karten ausblendet. Einfügeort: nach der Schwellwerte-`Card` (aktuell Zeile 638 `</Card>`), vor dem schließenden `</div>` der linken Spalte (Zeile 640). `reportConfig` als `$state` existiert dort bereits (Zeile 85-87), Binding ist vorbereitet. `createMode`-Prop existiert (Zeile 46/53) — Karte muss wie vorher mit `{#if !createMode}` gated bleiben (Regression-Schutz für #934). |
| `frontend/src/lib/components/trip-detail/BriefingScheduleTab.svelte` | Reiter "Versand" / value `briefings`. Zeile 105: `showMailContent={false}` — bleibt unverändert korrekt (PO-Entscheidung: Karte gehört NICHT hierher). |
| `frontend/src/lib/components/trip-detail/TripTabs.svelte` | Tab-Dispatcher. `value: 'weather'` → Label "Inhalt", `value: 'briefings'` → Label "Versand" (Labels seit #736). Keine Änderung nötig. |
| `frontend/e2e/issue-619-mail-elements-ui.spec.ts` | Navigiert aktuell zu `?tab=briefings` (Zeile 61 `openReportsSection`). Referenziert `report-show-metrics-summary` (AC-1, AC-5) — dieser Testid existiert nicht mehr im DOM (Checkbox wurde in #971/#774 entfernt, Feld wird seit #790 im Mail-Renderer unconditional gerendert). Muss auf `?tab=weather` migriert werden; AC-1/AC-5 müssen auf die tatsächlich vorhandenen 3 Bausteine (`report-show-outlook`, `report-show-stage-stats`, `report-show-yesterday-comparison`) bzw. auf Bestandsdaten-Erhalt-Pattern (analog AC-2 im selben File) umgestellt werden. |
| `frontend/e2e/issue-723-email-tab-eindampfen.spec.ts` | Gleiche Drift: `?tab=briefings` (Zeile 68), `report-show-metrics-summary` (Zeilen 103-105, 161). `REMOVED_TESTIDS`-Liste (Zeilen 72-81) muss geprüft werden — enthält bereits einige inzwischen entfernte IDs, aber nicht `report-show-metrics-summary` selbst (das wird an anderer Stelle als "vorhanden" erwartet, muss korrigiert werden). |

## Existing Patterns

- **Migrations-Vorbild #971** (Commit `aacb3084`, betrifft `issue-774-metrics-summary-persist.spec.ts` und `issue-776-metrics-toggle.spec.ts`): dieselbe Grundursache (verwaiste `show_metrics_summary`-UI-Referenz nach #664/#790-Vereinfachung) wurde durch Umbau der Tests auf reine Persistenz-Prüfung (kein UI-Checkbox-Klick mehr für dieses Feld) gelöst, analog zu AC-2 in `issue-619` ("daily_summary_metrics bleiben nach Save erhalten").
- **Prop-Gating-Pattern in `EditReportConfigSection.svelte`**: `showMailContent`, `showChannels` (beide Default `true`) steuern bereits, welche Karten gerendert werden. Eine dritte Prop (z.B. `showSchedule`, Default `true`) für die Morgen-/Abend-Report-Karten folgt demselben Muster.
- **`createMode`-Gating** in `WeatherMetricsTab.svelte` (`{#if !createMode}`) verhindert, dass der Anlege-Assistent (`TripNewEditor.svelte`) die Karte doppelt zeigt (Issue #934) — muss beim Wiedereinbau erhalten bleiben.

## Dependencies

- **Upstream:** `ReportConfig`-Typ (`$lib/types`), `reportConfigWrite.ts` (`CONTENT_MODULE_DESCRIPTIONS`), Backend-Felder `show_outlook`/`show_stage_stats`/`show_yesterday_comparison`/`email_format` (bereits seit #721/#722/#785 live, keine Backend-Änderung nötig).
- **Downstream:** `frontend/e2e/issue-619-mail-elements-ui.spec.ts`, `frontend/e2e/issue-723-email-tab-eindampfen.spec.ts` (zu migrierende Tests); ggf. weitere E2E-Tests, die `?tab=weather` oder `?tab=briefings` referenzieren, müssen auf Kollision geprüft werden (kurzer Scan im Implementierungsschritt).

## Existing Specs

- `docs/specs/modules/issue_736_tabs_reorg.md` — Ursprungsdesign: E-Mail-Inhalt-Karte gehört in den Inhalt-Reiter (AC-2 dort).
- `docs/specs/fast/fix-942-inhalt-tab-doppel-ui.md` — Mini-Spec, die die Karte komplett entfernt hat (Overreach: wollte nur Zeitplan-Duplikat beheben, hat aber die ganze Komponente entfernt).
- Test-Header verweisen auf `docs/specs/modules/issue_619_mail_elements_ui.md` und `docs/specs/modules/issue_723_email_tab_eindampfen.md` (nicht separat geprüft, da AC-Inhalt bereits vollständig aus den Testdateien selbst ableitbar ist).

## Zusatzfund: dritte betroffene Testdatei (nicht in #1047 erwähnt)

`frontend/e2e/issue-736-tabs-reorg.spec.ts` (AC-2, Zeilen 108-127) prüft bereits exakt
das Zielbild dieses Fixes: `report-mail-content` muss auf `?tab=weather` sichtbar sein,
kein Kanal-Toggle dort. AC-3 (Zeilen 129-147) prüft das Gegenstück für `?tab=briefings`
(kein `report-mail-content`, Kanäle genau einmal). Dieser Test ist vermutlich seit #942
ebenfalls rot (AC-2), wird aber durch denselben Code-Fix automatisch wieder grün — keine
zusätzliche Testmigration nötig, nur Verifikation im Rahmen der Validierung.

## Analyse: Technischer Lösungsweg

1. **`EditReportConfigSection.svelte`:** neue Prop `showSchedule?: boolean = true` einführen,
   die Morgen-/Abend-Report-`Card`-Blöcke (aktuell Zeilen 232-337, ungated) in
   `{#if showSchedule}...{/if}` wickelt. Default `true` heißt: `BriefingScheduleTab.svelte`
   und `TripNewEditor.svelte` (keine Prop übergeben) bleiben unverändert im Verhalten.
2. **`WeatherMetricsTab.svelte`:** Import wiederherstellen, Einbindung nach der
   Schwellwerte-`Card` (vor dem schließenden `</div>` der linken Spalte) mit
   `{#if !createMode}<EditReportConfigSection bind:reportConfig mode="edit" showMailContent={true} showChannels={false} showSchedule={false} />{/if}`.
3. **Testmigration `issue-619` / `issue-723`:** `openReportsSection`-Helper auf
   `?tab=weather` umstellen; `report-show-metrics-summary`-Referenzen entfernen/ersetzen
   durch die drei tatsächlich vorhandenen Bausteine (`report-show-outlook`,
   `report-show-stage-stats`, `report-show-yesterday-comparison`); AC-5 in `issue-619`
   (aktuell: UI-Checkbox-Klick auf `show_metrics_summary`) auf Bestandsdaten-Erhalt-Pattern
   umstellen (analog AC-2 im selben File und dem #971-Vorbild).

## Risks & Considerations

- **Doppel-UI-Regression vermeiden:** Ohne neue Gating-Prop für die Zeitplan-Karten würde der #942-Bug (Morgen-/Abend-Report doppelt sichtbar in Inhalt UND Versand) sofort zurückkehren.
- **Nicht die Kanal-Karte mit zurückbringen:** `showChannels={false}` muss beim Wiedereinbau gesetzt bleiben (Kanäle gehören laut #736 exklusiv in den Versand-Reiter).
- **`createMode`-Gating nicht vergessen:** sonst kollidiert es mit #934 (Anlege-Assistent zeigt die Karte schon separat über `TripNewEditor.svelte`).
- **Zwei-Nutzer-Test:** Da es sich um eine trip-bezogene Bearbeiten-Ansicht handelt, sollten die E2E-Tests (wie bisher in beiden Dateien üblich) mit isolierten Test-Trip-IDs pro Testlauf arbeiten (bereits der Fall via `tripId()`-Helper) — keine neue Mandanten-Anforderung, Muster bleibt unverändert.
