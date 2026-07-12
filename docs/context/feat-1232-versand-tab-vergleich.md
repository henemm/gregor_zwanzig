# Context: feat-1232-versand-tab-vergleich (#1232 Scheibe 2)

## Request Summary

Der Orts-Vergleich-Editor bekommt denselben Versand-Tab wie der Trip-Editor:
`VersandTab` (Scheibe 1, live seit 2026-07-12) wird `context="vergleich"`-fähig
und ersetzt `Step5Versand`. Dazu gehört der Datenmodell-Reshape: ComparePreset
kennt heute nur EINEN Zeitplan-Slot (`schedule`-Enum) — das Design verlangt das
Trip-identische Zwei-Slot-Modell (Morgen/Abend, editierbare Uhrzeiten) plus
editierbare Laufzeit (`endDate`, nullable). Full-Stack.

## Verbindliche Quellen

| Quelle | Inhalt |
|---|---|
| Issue #1232 Body (stable_id `editor-konsolidierung-phase4`) | Zielstruktur beide Kontexte, PO-Modell-Korrektur 2026-07-11: **kein** rollierendes Zeitfenster, **kein** Versandrhythmus im Vergleich-Versand (erfundene Features); Zeitplan identisch zum Trip (Morgen=heute, Abend=morgen); Laufzeit vergleich editierbar („bis auf Weiteres \| bis Datum") |
| `claude-code-handoff/current/jsx/versand-tab.jsx` | Design 1:1 — vergleich-Zweig: VT_BriefingChannels → VT_SchedulePlan(context="vergleich") → VT_LaufzeitVergleich (CompareEndDateControl) → VT_AlertDelivery; `endDate/onEndDate` Props; `activation`-Slot (Create-Banner) |
| `claude-code-handoff/screenshots/soll-29b-desktop-versand-vergleich.png` + `soll-29b-mobile.png` | Soll-Screens |
| `docs/specs/modules/versand_tab_route.md` | Scheibe-1-Spec (Muster, KLs, Changelog AC-10) |

## Related Files (Ist-Zustand, Stand fd07724a)

| Datei | Relevanz |
|---|---|
| `frontend/src/lib/components/shared/VersandTab.svelte` | Scheibe-1-Organism; `context`-Prop existiert, `vergleich`-Zweig rendert nichts (Guard Z.27-40); speichert selbst (debounced `saveController.schedule()` + PUT auf Trips-API Z.169-218) — kollidiert mit Compare-Save-Konzept |
| `frontend/src/lib/components/shared/versand-tab/VT{BriefingChannels,SchedulePlan,LaufzeitRoute}.svelte` + `alertDeliveryPayload.ts` | Scheibe-1-Bausteine; SchedulePlan muss context-diskriminiert werden, LaufzeitVergleich fehlt |
| `frontend/src/lib/components/compare/CompareEditor.svelte` | Editor-Shell, Tabs `vergleich\|orte\|idealwerte\|layout\|versand` (+`alarme` nur Edit, Z.51-58); Desktop Z.604-607 + Mobile Z.760-763 mounten dieselben Steps; **zentraler Save**: `handleSave()` Z.168-241, eigene SaveStatus-Instanz Z.43, Dirty-Tracking Z.77-115, `api.put` Z.217; Buttons `compare-editor-save` / `cm-mobile-save` |
| `frontend/src/lib/components/compare/steps/Step5Versand.svelte` | Wird ersetzt. Enthält heute: Info-Kacheln, Kanäle (`compare-step5-channel-*`, `-official-alerts-toggle`, `-hourly-enabled-toggle`), Horizont `-forecast-hours`, **Zeitfenster** `-time-window-start/-end`, Top-N, Stundenverlauf-Metriken, **Versandzeit-Buttons** (`schedule='daily_morning'\|'daily_evening'`), Aktivierungs-Banner (nur Create) |
| `frontend/src/lib/components/compare/CompareAlarmSection.svelte` | `alarme`-Tab (nur Edit): Radar-Toggle, Official-Trigger-Toggle, `AlertMetricLevelTable`, `AlertCooldownCard`, `AlertQuietHoursCard` → Zustell-Teile (Cooldown/Quiet/Kanäle/Beispiel) ziehen in Versand-Tab; Level-Tabelle bleibt (Korridor-Vorstufe #1231) |
| `frontend/src/lib/components/compare/compareEditorSave.ts` | Payload-Builder `buildComparePresetSavePayload` Z.56-140, PUT `/api/compare/presets/{id}` |
| `frontend/src/lib/components/compare/wizardState...` (getContext `compare-wizard-state`) | Wizard-State: flache Felder (`wiz.schedule`, `wiz.sendEmail`…); Create nutzt `wiz.saveNewPreset()` → POST |
| `internal/model/compare_preset.go:14-70` | Go-Struct: `Schedule string` (daily/weekly/manual), `PreviousSchedule`, `HourFrom/HourTo` (Bewertungsfenster, NICHT Sendezeit), `ForecastHours`, `Weekday *int`, `SendTelegram/SendSms *bool`, `OfficialAlertsEnabled`, `AlertCooldownMinutes/QuietFrom/QuietTo`; **kein** morning/evening-Slot-Paar, **kein** `end_date`, **kein** `briefings[]` |
| `frontend/src/lib/types.ts:480-509` | FE-Spiegel der Go-Struct |
| `internal/handler/compare_preset.go` | POST Z.116, PUT Z.173 (Pointer-Merge-Muster wie trip.go) |
| `internal/scheduler/scheduler.go` | Go feuert fixen Cron 06:00 → Python-Global-Endpoint (`comparePresetsDaily` Z.239-248); Auswertung `schedule`/`weekday` liegt **Python-seitig**; Alarm-Crons alle 15 Min Z.100-102 |
| Python-Core (Versand-Auswertung Compare) | Wertet heute `schedule`-Enum aus — beim Zwei-Slot-Reshape anzupassen (Fundstelle in Analyse präzisieren) |

## Existing Patterns

- **Scheibe-1-Muster:** context-Prop, 1:1-JSX-Übersetzung, Checkbox statt Switch (AC-7-testid-Erhalt), Warnbox „Kein Kanal aktiv", konsolidierte Alert-Delivery-Payload (`alertDeliveryPayload.ts`) — EIN Debounce-Slot-Prinzip.
- **Flush-Guard-Lektion (Adversary Scheibe 1):** `TripTabs.svelte:117` listet editierende Tabs explizit; CompareEditor hat eigenes Dirty-/Save-Modell — Tab-Wechsel-Semantik dort prüfen.
- **Daten-Schema-Rework-Pflicht (CLAUDE.md):** Read-Modify-Write mit Merge, Migration + Roundtrip-Test; `internal/model/*.go`-Edits triggern Pre-Snapshot-Hook.
- **Konvergenz-Richtung (Epic #1204/#1230):** Baustein teilen, nie nachbauen.

## Dependencies

- Upstream: ComparePreset-Modell (Go+TS), Compare-PUT-Handler, Python-Compare-Versand-Auswertung, wizardState/getContext, saveStatusStore.
- Downstream: Go-Alarm-Crons (Cooldown/Quiet aus Preset), Compare-Mail-Renderer (Zeitfenster/Horizont-Felder!), bestehende Playwright-Specs (`compare-editor-*.spec.ts`, `compare-alarm-config.spec.ts`, `issue-758`…), Cockpit/Status (`BuildCompareSubscriptionsStatus`).

## Zentrale Spannungsfelder (→ Analyse)

1. **Reshape-Umfang:** Issue sagt „kein neues Datenmodell (C4)" — ABER die spätere PO-Modell-Korrektur (Zeitplan identisch Trip, editierbare Uhrzeiten, editierbares Enddatum) ist mit dem heutigen `schedule`-Enum nicht darstellbar. Minimal-Reshape: `morning_enabled/morning_time/evening_enabled/evening_time` + `end_date` (nullable) am ComparePreset + Migration bestehender `schedule`-Werte (`daily_morning`→morning an, …) + Python-Auswertung. Memory-Notiz nennt dies „briefings[]-Reshape"; ein echtes `briefings[]`-Array wäre Epic-#29-Phase-3-Scope (BriefingSubscription) — NICHT hier.
2. **Was passiert mit Zeitfenster (`hour_from/to`), Horizont, Top-N, Stundenverlauf, weekly/weekday?** PO: Zeitfenster + Rhythmus raus aus dem Versand-UI. Felder behalten (render-relevant?) oder deprecaten? → Analyse/PO.
3. **Save-Strategie vergleich:** VersandTab-Self-Save (route) vs. CompareEditor-Zentral-Save mit Dirty-Tracking. Optionen: (a) VersandTab schreibt nur wiz-State, zentraler Save persistiert; (b) Save-Fn-Prop injizieren. Muster E9/C6 beachten.
4. **AlertPreviewCard** nimmt `trip`-Prop — vergleich braucht Ort-Subjekt (VT_AlertSample kontext-abhängig).
5. **Create- vs. Edit-Modus:** Step5 dient beiden; `activation`-Slot nur Create. Alarme-Tab existiert nur im Edit — Zustell-Umzug ändert Tab-Zuschnitt beider Modi.
6. **Testids:** `compare-step5-*`-Selektoren in bestehenden Specs; C6 verlangt Erhalt beim Umzug (gleiche IDs, neuer Parent) — kollidiert teils mit „Kacheln/Felder entfallen" (Zeitfenster etc.).

## Risks & Considerations

- Full-Stack + Migration → deutlich größer als Scheibe 1; Scheibenschnitt innerhalb des Workflows prüfen (z. B. 2a Modell+Migration+Python, 2b UI).
- Python-Compare-Versand: Fundstellen noch nicht verifiziert (Analyse-Phase).
- `data/users/*`-Bestandspresets: Migration idempotent + Backup (Deploy-Schritt, per-Host).
- Zwei parallele Scheduler-Pfade (Go-Cron 06:00 global) — Zwei-Slot-Zeiten brauchen ggf. Python-seitige Uhrzeit-Prüfung analog Trips.

## Analysis

### Type
Feature (Full-Stack-Refactor + Datenmodell-Reshape)

### Entscheidungen (Plan-Agent 2026-07-12)

1. **Reshape additiv:** 5 neue Pointer-Felder am ComparePreset (`morning_enabled/morning_time/evening_enabled/evening_time/end_date`); `schedule`/`previous_schedule` bleiben als Pause-/Lifecycle-Felder (manual=pausiert), `weekday` bleibt als deprecated Altdaten-Träger. Load-Migration in-memory, idempotent (Weekday-Muster): Altdaten → morning@06:00 an, evening aus (verhaltensidentisch zum heutigen 06:00-Cron); 07:00 nur Seed für NEUE Presets. weekly→täglich = PO-gedeckte bewusste Änderung (Changelog).
2. **Scheduling = Trip-Muster:** Go-Cron `compare_presets_daily` von `0 6 * * *` auf `0 * * * *` (Job-ID bleibt); Python `run_compare_presets_daily(hour)` prüft Slot-Stunde (Europe/Vienna), morning→target_date=heute, evening→morgen; Dedup=Stunden-Gleichheit (kein letzter_versand-Abgleich). Python braucht eigenen Slot-Fallback (liest JSON roh, Go-Migration materialisiert erst beim Save). Guards mitfixen: `archived_at` + `end_date < heute` → skip.
3. **Rest-Felder** (Zeitfenster hour_from/to, Horizont, Top-N, Stundenverlauf): ziehen in Scheibe 2b als extrahierte `CompareReportContentSection` ans Ende des Layout-Tabs — Testids `compare-step5-*` UNVERÄNDERT (C6), nur Tab-Navigation von 4 Specs ändert sich.
4. **Save-Strategie 2b:** KEIN Self-Save im vergleich-Zweig (Doppel-Mount Desktop+Mobile, Create ohne ID, zentrales Dirty-Tracking). VersandTab bekommt `wiz`-Prop und bindet direkt an den geteilten Wizard-State; Persistenz bleibt zentral (`handleSave`/`buildComparePresetSavePayload` + POST-Pfad). Beispiel-Warnung: statisches VT_AlertSample (kein AlertPreviewCard — kein Compare-Endpoint, kein Fake).
5. **Scheibenschnitt:** 2a Backend (dieser Workflow, ~350–450 LoC): Go-Modell+Validierung+PUT-Merge+Load-Migration+Tests, Cron-Umstellung, Python-Slot-Dispatch+target_date+Guards+Tests, openapi. 2b Frontend (eigener Workflow, ~650–850 LoC): VersandTab-vergleich-Zweig, Step5-Ersatz, CompareReportContentSection, Alarme-Tab-Reduktion, Spec-Anpassungen.

### Affected Files (Scheibe 2a)
| File | Change | Description |
|---|---|---|
| internal/model/compare_preset.go | MODIFY | 5 Pointer-Felder + Deprecated-Kommentare |
| internal/store/compare_preset.go | MODIFY | idempotente Load-Migration (Weekday-Muster) |
| internal/handler/compare_preset.go | MODIFY | nil-Preserve + Validierung (HH:MM(:SS), ISO-Datum) |
| internal/scheduler/scheduler.go | MODIFY | Cron `0 * * * *` |
| src/services/scheduler_dispatch_service.py | MODIFY | Slot-Dispatch, target_date, end_date/archived_at-Guards, Slot-Fallback |
| Go-Store-/Handler-Tests + Python-Tests | CREATE/MODIFY | Roundtrip + Migration + Slot-Fälligkeit + Guards |

### Scope Assessment
- Scheibe 2a: ~6 Kern-Dateien, +350–450 LoC, Risk MEDIUM (Bestandsdaten, Scheduler)
- Risiken: Go↔Python-Default-Drift (beidseitige Fixture-Tests), 24×-Cron-Last (Lazy-Loading #649 macht Leerticks billig), Mail-Footer #1110 zeigt weiter "daily" (kosmetisch, bewusst)

### Open Questions (für Spec/PO)
- weekly-Bestandspresets auf Prod vor Deploy sichten (Verhaltensänderung täglich)
