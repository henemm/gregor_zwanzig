---
workflow: issue-164-wizard-step4-channels
issue: 164
epic: 136
created: 2026-05-11
phase: 1
---

# Context: Issue #164 — Wizard Step 4: Briefings & Kanaele

## Request Summary

Step 4 des Trip-Wizards (Epic #136) implementieren: Kanal-Toggles
(Email/Signal/Telegram/SMS), ReportRow-Toggles (Morning 06:00 / Evening 18:00),
ThresholdRow-Liste (Boeen, Niederschlag, Gewitter, Schneefallgrenze). Letzter Schritt
loest `state.save()` aus (Save-Pipeline aus Master-Spec).

## Related Files

| File | Relevance |
|------|-----------|
| `docs/specs/modules/epic_136_step4_briefings.md` | **Stub** — muss in Phase 3 gefuellt werden |
| `docs/specs/modules/epic_136_trip_wizard.md` | Master-Spec; §3.1 `BriefingConfig`-Schema, §1.4 Save-Pipeline, Known Limitation: `toTripPayload` mappt `briefings` noch NICHT auf `Trip.report_config` |
| `frontend/src/lib/components/trip-wizard/steps/Step4Briefings.svelte` | Aktueller Platzhalter (9 Zeilen, nur TestID `trip-wizard-step4-briefings`) |
| `frontend/src/lib/components/trip-wizard/wizardState.svelte.ts` | `BriefingConfig`-Interface (Z.15-31), `defaultBriefingConfig` (Z.33-45), `briefings` $state (Z.58), `canAdvanceCurrent` case 4 returnt aktuell `true`, `toTripPayload()` schreibt `briefings` NICHT in `report_config` |
| `frontend/src/lib/components/trip-wizard/TripWizardShell.svelte` | Z.79: `{#if state.currentStep === 4}` mountet Step4Briefings; Z.131: Save-Button ruft `state.save()`. TestID `trip-wizard-step4-briefings` ist in Sub-Spec #163 §10 referenziert (fillStep3-Helper wartet darauf). |
| `frontend/src/lib/types.ts` | `Trip.report_config?: Record<string, unknown>` (Z.51) — Map-Typ ohne Schema-Constraint |
| `internal/model/trip.go` | `ReportConfig map[string]interface{}` mit `omitempty` (Z.28) — freies Map, kein Go-Schema |
| `internal/handler/trip.go` | `validateTrip` (Z.55-76) prueft `report_config` NICHT; `UpdateTripHandler` (Z.171-173) merged via Pointer-Trick (Read-Modify-Write fuer #99 BUG) |
| `src/app/models.py` Z.572-619 | Python-Side `TripReportConfig` dataclass — **kanonische Form des bestehenden Schemas** mit Feldern: `enabled`, `morning_time: time`, `evening_time: time`, `send_email/sms/signal/telegram`, `alert_on_changes`, `change_threshold_{temp_c,wind_kmh,precip_mm}`, `wind_exposition_min_elevation_m`, `show_compact_summary`, `show_daylight`, `multi_day_trend_reports: list[str]` |
| `src/services/trip_report_scheduler.py` Z.134-141 | Liest `trip.report_config.morning_time.hour` und `.evening_time.hour` — Cron-Scheduler-Trigger haengt am bestehenden Schema |
| `src/services/trip_alert.py` Z.89-102 | Liest `report_config.alert_on_changes` und Threshold-Felder fuer Aenderungserkennung |
| `frontend/src/lib/components/wizard/WizardStep4ReportConfig.svelte` | **Altes Wizard-UI** (zu loeschen lt. Master-Spec). Zeigt 1:1 das bestehende Schema mit Checkboxen + Number-Inputs fuer Temp/Wind/Precip-Aenderungs-Schwellen |
| `frontend/src/lib/components/edit/TripEditView.svelte` | Edit-Pfad — verwendet bislang das alte `WizardStep4ReportConfig`. Bleibt waehrend Epic #136 unangetastet (Folge-Issue) |
| `frontend/e2e/trip-wizard-shell.spec.ts` (AC#5a, AC#8, AC#11) | Navigiert bis Step 4, verifiziert Sichtbarkeit. Helper `fillStep3` aus #163 wartet aktuell auf TestID `trip-wizard-step4-briefings`; nach #164 sollte sie auf `trip-wizard-step4-container` umbenannt werden (Step-3-Spec §10 explizit erwaehnt das). |

## Existing Patterns

- **Step-Component-Pattern (#161, #162, #163):** Component liest `wizard = getContext<WizardState>(...)`, definiert Factory-Handler (`makeXyzHandler()` returnt `do...()` — Safari-Closure-Schutz aus CLAUDE.md), bindet UI direkt an `state.*`-Felder.
- **canAdvanceStepN-Getter:** Jeder Schritt hat einen Getter, der ueber `canAdvanceCurrent`-Switch ausgelesen wird. Aktuell `case 4: return true;` — fuer #164 stellt sich die Frage, ob `canAdvanceStep4` als Validations-Hook eingefuehrt wird (z.B. „mindestens ein Kanal aktiviert").
- **Test-ID-Konvention:** `trip-wizard-step{N}-{element}` (z.B. `step3-stage-row-{i}`, `step3-confirm-{i}`). Aktueller Platzhalter benutzt `trip-wizard-step4-briefings` — Umbenennung auf `-container` ist Step-3-Spec-Vereinbarung.
- **Save-Pipeline (Master-Spec §1.4):** Klick Save → `state.save()` → `toTripPayload()` → `api.post('/api/trips')` → Redirect `/trips/{id}`. `toTripPayload` strippt transiente Flags (`Waypoint.suggested`, `Stage.dateOverridden`).
- **Persistenz-Bruecke (NEU bei #164):** Step 4 muss `BriefingConfig` in `Trip.report_config` mappen — bisher leer in der Pipeline.
- **Factory-Pattern auf Svelte (Safari):** `makeToggleHandler(channel)` returnt benannte Funktion, kein anonymer Inline-Closure.
- **Altes `WizardStep4ReportConfig.svelte`:** Verwendet Checkboxes + Inline-onchange-Handler ohne Factory — passt nicht ins neue Pattern.

## Dependencies

- **Upstream:**
  - `WizardState.briefings` — `BriefingConfig`-Schema (channels/reports/thresholds) ist bereits zentral definiert
  - `wizardHelpers.ts` — keine neuen Helper benoetigt; ggf. Mapper `briefingToReportConfig()` neu
  - `$lib/components/ui/btn` (Epic #133) — Save-Button kommt vom Shell, nicht von Step 4
  - `$lib/components/ui/eyebrow` — Abschnitts-Header
- **Downstream:**
  - `state.toTripPayload()` muss erweitert werden, um `briefings` in `trip.report_config` zu mappen
  - `state.save()` selbst bleibt unveraendert (greift auf erweitertes Payload zu)
  - Backend `internal/handler/trip.go::CreateTripHandler` akzeptiert `report_config` als freies Map — kein Backend-Patch noetig
  - Python `TripReportConfig` dataclass (Scheduler/Alert): liest `morning_time`, `evening_time`, `send_email/...`, `alert_on_changes`, `change_threshold_*` — **fundamentaler Schema-Mismatch** mit den neuen `thresholds` (gust/precip/thunder/snow_line); siehe Risk #1
  - E2E-Test `trip-wizard-shell.spec.ts` (AC#5a, AC#8, AC#11) — TestID-Umbenennung muss konsistent sein

## Existing Specs

- `docs/specs/modules/epic_136_trip_wizard.md` — Master-Spec, approved
- `docs/specs/modules/epic_136_step4_briefings.md` — Stub (zu fuellen)
- `docs/specs/modules/epic_136_step3_waypoints.md` — Vorgaenger-Pattern (Layout, TestIDs, fillStepN-Helper)
- `docs/specs/modules/epic_136_step2_stages.md` — Vorgaenger-Pattern (canAdvanceStepN-Getter)
- `docs/specs/modules/epic_136_step1_profile.md` — Vorgaenger-Pattern (Factory-Handler, Pflichtfelder-Validierung)
- `docs/specs/modules/activity_profile.md` — Kanonische Aggregations-Profile (referenziert via `mapActivityToProfile`)
- Epic #139 (Alert-Konfigurator) — explizit als Owner fuer „tiefergehende Threshold-/Alert-Logik" benannt; #164 baut nur das UI-Grundgeruest

## Risks & Considerations

### Risk #1 — Schema-Mismatch BriefingConfig ↔ TripReportConfig (HOCH)

Das im Master-Spec definierte `BriefingConfig.thresholds` hat Felder `gust_kmh / precip_mm / thunder_level / snow_line_m`. Das bestehende, in Python+Go verankerte `TripReportConfig` hat aber `change_threshold_temp_c / change_threshold_wind_kmh / change_threshold_precip_mm` (Aenderungs-Deltas, keine Absolutwerte!). Konsequenz:

- Beim Save aus dem neuen Wizard wuerde der Scheduler/Alert-Code (`src/services/trip_alert.py`, `trip_report_scheduler.py`) die neuen Thresholds NICHT als Aenderungs-Schwellen interpretieren — sie sind semantisch verschieden.
- Phase 2 muss entscheiden: (a) `briefings.thresholds` als neuen Block unter `report_config.alert_thresholds` speichern und Backend-Konsumenten ignorieren das bis Epic #139, oder (b) Spec auf bestehende Felder umstellen.
- Empfehlung fuer Phase 2: Variante (a) — neue Thresholds als opaque Sub-Map unter `report_config.alert_thresholds`, alte Felder bleiben unangetastet; Epic #139 verarbeitet sie spaeter. Begruendung: Issue #164 ist UI-Skelett; Backend-Verhalten zu aendern waere Scope-Creep.

### Risk #2 — Channel-Mapping Email/Signal/Telegram/SMS

Master-Spec `BriefingConfig.channels` enthaelt `sms` — die Python-Seite `TripReportConfig` hat `send_sms` (existiert!). Mapping ist trivial: `{ email, signal, telegram, sms }` ↔ `{ send_email, send_signal, send_telegram, send_sms }`. Allerdings: Der alte FE-Wizard hat **kein** SMS-Toggle gerendert — wir fuegen es als sichtbares Toggle hinzu. Falls Channels ohne Backend-Pipeline (SMS-Provider noch nicht implementiert) Verwirrung stiften, koennte Empfehlung sein, SMS in der UI als „demnaechst"-Hint zu markieren. Phase 2 sollte klaeren.

### Risk #3 — Zeitformat-Bruch HH:MM vs. time-Objekt

`BriefingConfig.reports.{morning,evening}.time` ist `string` (z.B. `"06:00"`). Python `TripReportConfig.morning_time` ist `datetime.time`. Beim Save schreiben wir den String — Python liest den ueber `time.fromisoformat`. Validierung beim FE: `<input type="time">` liefert "HH:MM", saubere Round-Trip-Semantik. Kein Risiko, nur in der Spec festhalten.

### Risk #4 — `enabled`-Feld pro Report vs. global

Master-Spec hat **pro Report** ein `enabled`-Flag (`morning.enabled`, `evening.enabled`). Bestehendes Schema hat ein **globales** `enabled` plus implizites Morgen+Abend (beide oder keiner). Phase 2 muss klaeren, ob das alte `enabled` synthetisch aus `morning.enabled || evening.enabled` abgeleitet wird oder ob das Schema umgebaut wird. Empfehlung: Aktiv lassen wie Spec — alte Konsumenten erhalten `enabled = (morning.enabled || evening.enabled)`.

### Risk #5 — canAdvanceStep4-Pattern existiert noch nicht

In Sub-Spec #163 wurde der `case 4: return true` bewusst belassen. Issue #164 sollte entscheiden, ob mindestens ein Kanal aktiv sein muss (sonst macht Speichern keinen Sinn). Tech-Lead-Empfehlung: `canAdvanceStep4 = at least one channel true` als Save-Button-Disabled-Gate; Master-Spec-Switch ergaenzen analog Step 1-3.

### Risk #6 — TestID-Konvention `trip-wizard-step4-briefings` vs. `-container`

Step-3-Sub-Spec §10 erwartet, dass Step 4 die TestID-Konvention `-container` annimmt. Heutiger Platzhalter benutzt `-briefings`. Issue #164 muss die TestID umbenennen UND den `fillStep3`-Helper sowie die Shell-Tests (AC#5a, AC#8, AC#11) konsistent anpassen.

### Risk #7 — Spec #164 ist nur Stub — kein Layout-Wireframe, keine Akzeptanzkriterien

Sub-Spec #164 ist heute 25 Zeilen Stub. Phase 3 muss eine vollstaendige Sub-Spec analog #161/#162/#163 liefern: Layout-Wireframe, Component-Inventar (ChannelToggle, ReportRow, ThresholdRow), `toTripPayload`-Mapping-Detail, TestID-Inventar, fillStep4-Helper, Akzeptanzkriterien, Migration der Shell-Tests.

### Risk #8 — Edit-Pfad ueberlaesst alten Wizard

`TripEditView.svelte` mountet `WizardStep4ReportConfig` — Edit-Pfad bleibt zwar laut Master-Spec out-of-scope, aber wenn das `report_config`-Mapping aus Step 4 NEU andere Felder schreibt, kann Edit-Pfad sie nicht mehr darstellen (Datenverlust beim Edit!). Phase 2 muss pruefen: schreibt #164 in unbekannte Felder, die TripEditView dann beim Edit ueberschreibt? Pflicht: `src/app/loader.py`-Roundtrip-Test + Edit-Pfad-Read-Modify-Write-Verhalten verifizieren (CLAUDE.md §Daten-Schema-Reworks).

## Phase-2-Entscheidungen (2026-05-11)

| # | Frage | Entscheidung | Konsequenz fuer Phase 3 |
|---|-------|--------------|--------------------------|
| 1 | Threshold-Schema | **Variante A** (Tech-Lead, ohne User-Frage): `report_config.alert_thresholds = { gust_kmh, precip_mm, thunder_level, snow_line_m }` als neuer Sub-Block; alte `change_threshold_*`-Felder unberuehrt. | Mapping in `toTripPayload()` schreibt beide Blocks — alte Felder mit Defaults aus `defaultBriefingConfig`, neue Felder aus `briefings.thresholds`. |
| 2 | SMS-Sichtbarkeit | **Anzeigen, deaktiviert mit Hinweis "demnaechst verfuegbar"** (User-Entscheidung). | ChannelToggle erhaelt `disabled`-Prop; SMS-Row rendert mit Hilfetext. State-Feld `briefings.channels.sms` bleibt erhalten, ist aber UI-gesperrt auf `false`. |
| 3 | `canAdvanceStep4` | **Immer `true` — Trip ohne Kanaele speicherbar** (User-Entscheidung). | Save-Button immer enabled (ausser bei `saveStatus === 'saving'`). Kein Kanal-Validierungs-Gate. Begruendung: ad-hoc-Trip kann nachtraeglich konfiguriert werden. |
| 4 | `enabled`-Mapping | **Synthetisch ableiten** (Tech-Lead, ohne User-Frage): `report_config.enabled = reports.morning.enabled \|\| reports.evening.enabled`. | Kein extra Master-Toggle im UI noetig. |
| 5 | TripEditView-Bruch | **Folge-Issue erstellen, Verlust dokumentieren** (User-Entscheidung). | (a) GitHub-Issue „Edit-Pfad fuer Wizard-Trips refaktorieren" anlegen (Owner: Folge-Sprint). (b) In Sub-Spec #164 §Known Limitations: „Edit ueber `TripEditView` zerstoert `report_config.alert_thresholds` — temporaer akzeptiert weil Backend bis Epic #139 die Felder nicht konsumiert." (c) Code-Kommentar in `TripEditView.svelte` mit Issue-Verweis. |
| 6 | TestID | **`trip-wizard-step4-briefings` → `trip-wizard-step4-container`** (Konvention aus Sub-Spec #163 §10). | `fillStep3`-Helper Wartet-auf-Selector in `helpers.ts` umstellen. Drei Shell-Tests (AC#5a, AC#8, AC#11) verifizieren danach `trip-wizard-step4-container`. |

## Implementation Strategy (Phase 3 Sub-Spec Skelett)

**Komponenten:**
- `Step4Briefings.svelte` (fuellen, ~120 LoC): Layout in drei Sektionen (Kanaele, Reports, Schwellwerte). Eyebrow pro Sektion.
- `ChannelToggle.svelte` (NEU, ~40 LoC): Generischer Toggle mit Label, optional `disabled` + Hilfetext.
- `ReportRow.svelte` (NEU, ~50 LoC): Toggle + `<input type="time">` pro Report-Typ.
- `ThresholdRow.svelte` (NEU, ~50 LoC): Label + Number-Input (oder Select fuer `thunder_level`).
- `WizardState`-Erweiterung in `toTripPayload()` (~30 LoC): Mapping `briefings` → `report_config`.

**State-Erweiterungen:**
- `get canAdvanceStep4(): boolean { return true; }` (Konsistenz mit #163-Pattern).
- `canAdvanceCurrent`-Switch case 4 zeigt auf `canAdvanceStep4` statt literal `true`.

**Tests:**
- Unit-Tests (`wizardState.test.ts`): Mapping briefings→report_config, channels-Mapping, time-Strings, alert_thresholds Sub-Map.
- E2E (`trip-wizard-step4.spec.ts`): Channel-Toggles, Report-Time-Inputs, Threshold-Inputs, Save-Button-Klick, Erfolg via Toast/Redirect.
- Shell-Tests (`trip-wizard-shell.spec.ts`): TestID-Umbenennung AC#5a, AC#8, AC#11.

**fillStep4-Helper** (`helpers.ts`): Toggles setzen, Save-Button klicken, Erfolg verifizieren.

## Scope-Schaetzung

| Bereich | Files NEU | Files EDIT | LoC Code | LoC Tests |
|---------|-----------|------------|----------|-----------|
| Frontend Komponenten | 3 | 1 | ~260 | — |
| WizardState | 0 | 1 | ~30 | ~80 |
| E2E + Helper | 1 | 2 | — | ~180 |
| Spec + Doku | 0 | 2 | — | — |
| **Total** | **4** | **6** | **~290** | **~260** |

Liegt im Bereich „>=4-5 Files" — sauber strukturiert, kein Refactoring-Sog.

## Next

Phase 3 (`/3-write-spec`) — Sub-Spec `epic_136_step4_briefings.md` ausfuellen analog zu #163, mit allen oben getroffenen Entscheidungen. Danach: Approval, dann Folge-Issue „Edit-Pfad TripEditView refaktorieren" auf GitHub.
