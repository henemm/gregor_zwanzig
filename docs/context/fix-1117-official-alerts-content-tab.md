# Context: fix-1117-official-alerts-content-tab

## Request Summary
Issue #1117 (bug, priority:high): Der Schalter „Amtliche Warnungen" (`trip.official_alerts_enabled`) ist aktuell nur im Tab „Alerts" konfigurierbar. Der Nutzer erwartet ihn auch (oder stattdessen) im Tab „Inhalt" (E-Mail-Inhalts-Auswahl), wo alle anderen E-Mail-Bausteine an-/abgeschaltet werden.

## Related Files
| File | Relevance |
|------|-----------|
| `frontend/src/lib/components/edit/EditReportConfigSection.svelte` | Enthält die "E-Mail-Inhalt"-Card (Gruppe A: Ausblick, Etappen-Kennzahlen, Vortag-Vergleich). Hier fehlt der Schalter „Amtliche Warnungen". Wird per `showMailContent`-Prop gesteuert. |
| `frontend/src/lib/components/trip-detail/WeatherMetricsTab.svelte` | Rendert den Tab „Inhalt" (TripTabs `value: 'weather'`, `label: 'Inhalt'`). Bindet `EditReportConfigSection` mit `showMailContent={true} showChannels={false} showSchedule={false}`. Hat bereits `trip` + `onTripUpdate` verfügbar. |
| `frontend/src/lib/components/alerts-tab/AlertsTab.svelte` | Enthält den bestehenden Schalter (Zeilen ~48/85-102/136-140), inkl. eigenem Auto-Save-Pfad `buildOfficialAlertsSaveFn()` → `api.put('/api/trips/{id}', { official_alerts_enabled })`. Dient als 1:1-Vorlage für den neuen Ort. Referenz-Pattern bleibt hier erhalten (Issue sagt nicht "entfernen", nur "fehlt woanders"). |
| `frontend/src/lib/components/edit/reportConfigWrite.ts` | Enthält `CONTENT_MODULE_DESCRIPTIONS` (Label + Beschreibung je Baustein) und `countActiveContentModules`. Falls „Amtliche Warnungen" als vierter Baustein gezählt werden soll, hier ergänzen. |
| `frontend/src/lib/types.ts` (Z. 281, 496) | `Trip.official_alerts_enabled?: boolean` bereits typisiert. Kein Backend-/Typ-Änderungsbedarf. |
| `frontend/src/lib/components/trip-detail/TripTabs.svelte` | Kanonische Live-Route (`/trips/[id]`). Zeigt: `weather`→WeatherMetricsTab (Tab "Inhalt"), `alerts`→AlertsTab (Tab "Alerts"), `briefings`→BriefingScheduleTab (Tab "Versand", `showMailContent={false}` — dort NICHT betroffen). |

## Existing Patterns
- **Auto-Save via `saveController`**: Jeder Tab bekommt `saveController` durchgereicht; Changes werden über `saveController?.schedule(saveFn)` debounced gespeichert (Referenz: `AlertsTab.svelte` `buildOfficialAlertsSaveFn`/`makeOfficialAlertsToggleHandler`, Factory-Pattern gegen Safari-Closure-Bugs, CLAUDE.md-Konvention).
- **Read-Modify-Write**: `EditReportConfigSection` mergt UI-Felder über `originalReportConfig` (Spread), damit unbekannte Felder erhalten bleiben (`$effect` Zeilen 174-216). `official_alerts_enabled` ist aber KEIN `report_config`-Feld, sondern ein Top-Level-Trip-Feld — braucht eigenen Save-Pfad analog AlertsTab, nicht über den `reportConfig`-Merge.
- **Content-Module-Checkbox-Pattern**: `show_outlook`/`show_stage_stats`/`show_yesterday_comparison` nutzen `Checkbox` + Label aus `CONTENT_MODULE_DESCRIPTIONS` + `data-testid="report-show-<name>"`.

## Dependencies
- Upstream: `PUT /api/trips/{id}` (Go-Handler `internal/handler/trip.go` Z. 154, Merge-Semantik bereits vorhanden über `OfficialAlertsEnabled *bool` Pointer-Pattern — `nil` = unverändert).
- Downstream: `src/services/trip_report_scheduler.py:652` (`if trip.official_alerts_enabled is not False`) — strukturelles Gate für den Abruf amtlicher Warnungen in Trip-Briefings (Issue #1087, bereits live). Keine Backend-Änderung nötig, nur ein zweiter UI-Einstiegspunkt zum selben Feld.

## Existing Specs
- `docs/specs/modules/issue_587_weather_tab_v2.md` — Wetter-Tab v2 (Grundlage für WeatherMetricsTab)
- `docs/specs/modules/issue_619_mail_elements_ui.md` — Mail-Elemente-UI (Grundlage für EditReportConfigSection Content-Bausteine)

## Risks & Considerations
- **Toter Code entdeckt (Nebenbefund, NICHT in diesem Workflow anfassen):** `TripTabs.svelte` importiert `BriefingsTab` (Zeile 8), rendert es aber nirgends. `TripEditView.svelte` und `BriefingsTab.svelte` sind über keine Route erreichbar (nur von einem Content-Check-Test referenziert). → Folge-Issue anlegen, nicht in diesem Fix mit anfassen.
- **Zwei Orte für denselben Schalter** (Alerts-Tab behält ihn, Inhalt-Tab bekommt ihn zusätzlich) — Auto-Save-Race möglich, wenn beide Tabs gleichzeitig offen wären; in der Praxis nicht möglich (ein Tab aktiv zur Zeit), aber State-Sync über `onTripUpdate` muss sauber laufen, damit ein Wechsel zwischen Tabs den aktuellen Wert zeigt.
- **Create-Modus (`mode="create"`, kein `trip.id`)**: `EditReportConfigSection` wird auch in `TripNewEditor.svelte` mit `mode="create"` verwendet — dort existiert noch keine Trip-ID für den separaten PUT. Scope-Entscheidung nötig: Toggle im Create-Wizard weglassen (Default `true` bleibt aktiv, Nutzer passt später im Inhalt-Tab an) — das entspricht dem bestehenden Verhalten des Alerts-Tab-Onboardings.
- **Naming-Konsistenz**: Bestehendes Label „Amtliche Warnungen" (aus AlertsTab, via `ChannelToggle`) sollte 1:1 übernommen werden, keine neue Formulierung.

## Analysis

### Type
Bug (label `type:bug`, `priority:high`)

### Bug-Intake-Verifikation (unabhängig bestätigt)
- Root Cause bestätigt: Schalter fehlt strukturell in der "E-Mail-Inhalt"-Card des Inhalt-Tabs.
- Zusätzlicher Fund: `TripNewEditor.svelte` (Create-Wizard) hat den Schalter ebenfalls nicht — bewusst nicht in Scope (siehe unten).
- Compare-Wizard `Step5Versand.svelte` hat den Schalter bereits — andere Feature-Domäne (Orts-Vergleich), nicht betroffen.
- Semantische Prüfung: Alerts-Tab = "Sofort-Alarm bei amtlicher Warnung", Inhalt-Tab = "amtliche Warnung im Briefing zeigen" — beide nutzen dasselbe Datenfeld, aber unterschiedlichen Nutzerkontext. Kein Grund für absichtliche Trennung gefunden — echter Bug, kein Feature-Missverständnis.

### Affected Files (with changes)
| File | Change Type | Description |
|------|-------------|--------------|
| `frontend/src/lib/components/trip-detail/WeatherMetricsTab.svelte` | MODIFY | Neuer State `officialAlertsEnabled` (Init aus `trip.official_alerts_enabled ?? true`, analog `telegramKurzform`), `ChannelToggle`-Import, Einbindung in `snapshot`/`isDirty`/`handleDiscard`, Mitschicken in den bestehenden zweiten PUT (`api.put('/api/trips/{id}', { report_config: reportConfig, official_alerts_enabled: officialAlertsEnabled })`) in `handleSave()` und `scheduleAutoSave()`, Markup-Ergänzung in der Card „E-Mail-Inhalt"-Umgebung. |
| Tests (TDD RED, Datei folgt in Phase 4) | CREATE | Playwright-E2E gegen Staging: Toggle im Inhalt-Tab ändern → Reload/Tab-Wechsel zu Alerts → Wert synchron. Kein Mock (CLAUDE.md-Pflicht). |

**Explizit NICHT geändert:** `EditReportConfigSection.svelte` (keine neuen Props — Blast Radius auf 5 Call-Sites inkl. 2 totem Code vermeiden), `AlertsTab.svelte` (Schalter bleibt dort bestehen), `TripNewEditor.svelte` (Create-Modus, Begründung s.u.), Backend (bereits vollständig verdrahtet).

### Scope Assessment
- Files: 1 Kern-Datei (+ 1 Testdatei)
- Estimated LoC: +25–35 (Komponente) + ~15–20 (Test)
- Risk Level: LOW — reiner UI-Zusatz auf bereits verdrahtetem Feld, kein Backend-Eingriff, kein Touch auf geteilte Komponente.

### Technical Approach
Schalter wird **direkt in `WeatherMetricsTab.svelte`** gerendert (nicht über neue Props in `EditReportConfigSection.svelte`), integriert in den bereits vorhandenen zweiten PUT-Call (`report_config`-Aktualisierung), NICHT über einen dritten separaten `saveController.schedule()`-Aufruf — vermeidet Race auf dem geteilten `SaveStatus`-Controller (nur eine pending Funktion gleichzeitig).

**Create-Modus:** Bewusst weggelassen. Kein `trip.id` vorhanden, Backend-Default (`true`) greift beim POST automatisch, entspricht bestehendem Onboarding-Verhalten (Alerts-Tab zeigt initial „keine Alerts konfiguriert"). Kein zusätzlicher POST-Body-Support vorhanden/nötig.

**Zwei Schalter-Orte:** Bewusst beibehalten (Alerts-Tab UND Inhalt-Tab), da beide einen unterschiedlichen Nutzerkontext für dasselbe Feld abbilden und das Issue kein Entfernen aus Alerts fordert.

### Dependencies
Keine neuen — Backend-Endpoint und Datenmodell sind bereits vollständig vorhanden (Issue #1087, #1040).

### Open Questions
- [ ] UI-Komponente für den neuen Schalter: `ChannelToggle` (wie im Alerts-Tab) oder `Checkbox` + `CONTENT_MODULE_DESCRIPTIONS`-Pattern (wie die anderen 3 Content-Bausteine in der Card)? → Wird in Phase 3 (Spec) als AC festgelegt, visuelle Konsistenz mit der "E-Mail-Inhalt"-Card hat Vorrang vor 1:1-Kopie vom Alerts-Tab.
- [ ] Zusatztext im Inhalt-Tab ("auch im Briefing") zur Abgrenzung vom Alerts-Tab-Kontext — PO entscheidet bei Spec-Freigabe.
