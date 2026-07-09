# Context: feat-1095-compare-alerts

## Request Summary
Issue #1095 (Teil von Epic #1092, Punkt 7): Alerts sind im Orts-Vergleich (ComparePreset)
gar nicht konfigurierbar. Sie sollen **analog zu den Alerts in Trips** funktionieren
(gleiche Bedienung/Optionen). Nächster Schritt laut Issue: Trip-Alert-Konfiguration als
Vorbild analysieren, dann auf Compare übertragen.

## Zentrale Erkenntnis (scope-entscheidend)

**Der Orts-Vergleich besitzt heute KEINE Alert-Auswertungs-Engine.**
- Die komplette Alert-Engine (Threshold-Vergleich, Severity, Cooldown, Quiet-Hours,
  Tageslimit, State-Dedup, Sofort-Trigger amtlicher Warnungen) liegt in Python:
  `src/services/trip_alert.py` (`TripAlertService.check_all_trips()`), getrieben vom
  15-Minuten-Job `POST /api/scheduler/alert-checks`.
- Der Compare-Pfad (`src/services/scheduler_dispatch_service.py`
  `run_compare_presets_daily()` → `send_one_compare_preset()`) **rendert und versendet
  nur einen Report** — kein Threshold-Vergleich, keine Severity, kein Cooldown, keine
  Quiet-Hours, kein Dedup.
- Einzige „Alert"-Berührung auf der Compare-Seite: `official_alerts_enabled` (#1040) —
  **reines Display** (amtliche Warnungen werden geholt und in den Vergleichsreport
  gerendert, NICHT als Trigger ausgewertet).

→ „Analog zu Trips" kann zwei sehr verschiedene Dinge bedeuten. **Das ist die
Kern-Scope-Frage für die Analyse-Phase + PO-Entscheidung** (siehe Risiken).

## Related Files

### Trip-Alerts — Vorbild (Backend)
| Datei | Relevanz |
|------|----------|
| `internal/model/trip.go:18-64` | Enums `AlertRuleKind`/`AlertSeverity`/`AlertMetric`, Struct `AlertRule` |
| `internal/model/trip.go:97-114` | Trip-Felder `AlertRules`, `AlertCooldownMinutes`, `AlertQuietFrom/To`, official-Flags |
| `internal/model/trip.go:120-255` | `AlertableMetrics`, Defaults, `ActiveAlertableMetricIDs()`, `SyncAlertRules()` (RMW-Merge) |
| `internal/store/trip.go:86-129` | Self-Heal + Compute-on-Save via `SyncAlertRules` |
| `internal/handler/trip.go:140-241` | `tripUpdateRequest`-DTO + `UpdateTripHandler` (nil-Merge pro Pointer-Feld) |

### Trip-Alerts — Vorbild (Frontend)
| Datei | Relevanz |
|------|----------|
| `frontend/src/lib/components/alerts-tab/AlertsTab.svelte` | Haupt-Editor (Level/Preset-basiert), Cooldown, Ruhezeiten, official-Toggle |
| `frontend/src/lib/components/alerts-tab/AlertCooldownCard.svelte` / `AlertQuietHoursCard.svelte` | Cooldown- + Ruhezeiten-Eingabe |
| `frontend/src/lib/components/alerts-tab/alertMetricTable.ts` | `METRIC_PRESETS`, Rules↔UI-Mapping |
| `frontend/src/lib/components/alert-rules-editor/*` | Klassischer Regel-Editor (kind/threshold/severity), im TripEditView |
| `frontend/src/lib/types.ts:69-104,275-278` | FE-Typen `AlertRule`, Trip-Alert-Felder |

### Trip-Alerts — Auswertung/Versand (Engine)
| Datei | Relevanz |
|------|----------|
| `src/services/trip_alert.py:85-373` | Gesamte Auswertung: Quiet-Hours `:423`, Cooldown `:448`, Threshold `:247`, Severity `:598`, official-Trigger `:983` |
| `src/services/alert_state.py` | Melde-Gedächtnis / Dedup |
| `src/services/notification_service.py` | Versand (`send_trip_report`, `send_official_alert`) |
| `src/output/renderers/alert/*` | Alert-Renderer (email/telegram/sms) — **shared** Official-Alert-Helper `official_alerts.py` |
| `api/routers/scheduler.py:50-57` | `/api/scheduler/alert-checks` → `check_all_trips()` |
| `internal/scheduler/scheduler.go:93,153` | Cron `*/15` → alertChecks |

### Compare — Zielsystem (Backend)
| Datei | Relevanz |
|------|----------|
| `internal/model/compare_preset.go:13-45` | `ComparePreset`-Struct; `OfficialAlertsEnabled *bool` (:38), `HourlyEnabled *bool` (:44) = Pointer-Blaupause |
| `internal/store/compare_preset.go:15-60` | Load/Save (Full-Array-Write); Merge passiert im Handler |
| `internal/handler/compare_preset.go:176-227` | `UpdateComparePresetHandler` — nil-Merge-Blöcke (`official_alerts_enabled` :217, `hourly_enabled` :221) = RMW-Blaupause |
| `internal/handler/compare_preset.go:106,199,265,300,340` | `s.WithUser(middleware.UserIDFromContext(...))` — user_id-Isolation |
| `internal/router/router.go:180-186` | Compare-Routen (PUT `/api/compare/presets/{id}` = primärer Schreibpfad) |

### Compare — Zielsystem (Frontend + Scheduler)
| Datei | Relevanz |
|------|----------|
| `frontend/src/lib/components/compare/steps/Step5Versand.svelte:135-150` | Toggle-Blaupause (official-alerts + hourly), testids |
| `frontend/src/lib/components/compare/compareWizardState.svelte.ts:40-42,158-227` | State-Defaults + Save-Pfade (create/edit) |
| `frontend/src/lib/components/compare/compareEditorSave.ts:13-96` | Payload-Builder (Round-Trip-Spread `{...original}`) |
| `frontend/src/lib/components/compare/CompareEditor.svelte:138-175` | **Doppelpfad**: eigene `handleSave()` reicht Alert-Felder NICHT durch — beim Erweitern beachten |
| `frontend/src/routes/compare/[id]/edit/+page.svelte:36-37` | Edit-Init (Load → State, `?? true`-Fallback) |
| `frontend/src/lib/types.ts:480-499` | FE-Typ `ComparePreset` |
| `src/services/scheduler_dispatch_service.py:20,198-303` | Compare-Versand (rendert nur, keine Alert-Eval) |
| `src/services/comparison_engine.py:189-205` | `official_alerts_enabled`-Fetch (nur Display) |

## Existing Patterns
- **Pointer-`*bool`-Feld für neue Config-Flags** (Altdaten-sicher): `OfficialAlertsEnabled`,
  `HourlyEnabled` — `nil` = Feld fehlte (Default aktiv), `false` = bewusst aus.
- **Read-Modify-Write-Merge im Handler** statt Blind-Replace: nil-Check pro Feld
  (`compare_preset.go:217-227`) — Client-unbekannte Felder gehen nicht verloren (Pflicht laut CLAUDE.md).
- **user_id konsequent aus Auth-Kontext** (`WithUser`/`UserIDFromContext`), nie aus Body, nie `"default"`.
- **Trip-Alert-Regeln**: `SyncAlertRules` synchronisiert Regeln gegen aktive Metriken
  (`display_config["metrics"]`) — Regeln werden gemerged, nicht ersetzt.
- **Shared Official-Alert-Renderer** ist der EINZIGE bestehende gemeinsame Code Trip↔Compare.

## Dependencies
- **Upstream (was Compare-Alerts bräuchte):** Wetterdaten pro Ort (bereits via
  `ComparisonEngine`), Alert-Engine-Bausteine (Threshold/Severity/Cooldown/Quiet/State) —
  heute nur in `trip_alert.py`, an Trip-Datenmodell gekoppelt.
- **Downstream (wer Compare-Presets nutzt):** Compare-Scheduler (daily/weekly), Frontend-Editor,
  Compare-Report-Renderer, `/api/compare/presets/{id}/send`.

## Existing Specs
- `docs/specs/modules/issue_458_compare_preset_backend.md` — ComparePreset-Backend
- `docs/features/epic-438-compare-wizard.md` — Compare-Wizard (5 Steps)
- Trip-Alert-Specs: siehe geschlossene Issues #205/#638/#946/#1087/#1088 + `docs/specs/modules/`

## Risks & Considerations
1. **SCOPE-KERNFRAGE (PO-Entscheidung nötig):** „Analog zu Trips" —
   - **Variante A (Konfig-Erweiterung, klein):** Nur die amtliche-Warnungen-Konfiguration
     bzw. Anzeige-Optionen im Compare-Editor angleichen — kein neuer Auswertungs-Job.
   - **Variante B (volle Alert-Engine für Compare, groß):** Compare-Presets bekommen echte
     Alarmregeln, die alle 15 Min gegen Live-Wetter ausgewertet, dedupliziert und als
     Push-Alerts versendet werden. Das bedeutet eine **neue Auswertungs-Engine** (oder
     Verallgemeinerung von `trip_alert.py` auf Orte statt Etappen), neuen Scheduler-Job,
     State-Dedup pro Ort, Kanal-Routing. Das ist ein Epic, kein Einzel-Issue.
   - Die Analyse-Phase muss beide Varianten mit Aufwand/Trade-offs sauber darstellen; der
     PO entscheidet. ACs dürfen den Mechanismus nicht voraussetzen.
2. **Alert-Zweck ist „Abweichungs-Wächter"** (Memory: Nowcast vs. letztes Briefing) — passt
   das konzeptionell auf Orts-Vergleich (Vor-Ort-Urlauber, Konfig vor Urlaub)? Muss geklärt werden.
3. **Datenschema-Merge:** Neues Feld MUSS per RMW gemerged werden (BUG-DATALOSS-Historie).
   `compare_preset.go` Edits triggern `data_schema_backup.py`.
4. **Frontend-Doppelpfad:** `CompareEditor.handleSave()` vs. `wiz.saveComparePreset()` —
   beide müssen neue Felder durchreichen, sonst stiller Datenverlust beim Speichern.
5. **user_id-Isolation:** Mandantenfähig — neuer Endpoint/Feld mit zwei Nutzern testen.
6. **Zwei parallele Compare-Pfade:** `scheduler_dispatch_service.py` (compare_presets.json)
   UND `compare_subscription.py` (compare_subscriptions.json, CLI). Nicht doppelt bauen.
7. **Mail-Validator-Gate:** Änderungen an Compare-Mail-Rendering triggern `email_spec_validator.py`
   (X-GZ-Mail-Type: compare) — nur bei Exit 0 „E2E bestanden".

## Analysis

### Type
Feature (mit Bug-Framing im Issue „gar nicht konfigurierbar"). Kern ist eine
Produkt-/Scope-Entscheidung, kein reiner Fix.

### Epic-Einordnung
#1092 ist eine Serie von Konfigurierbarkeits-Regressionen des Orts-Vergleichs. Punkte 2–6
(#1105/#1106/#1107) betrafen die **Report-Darstellung** und sind erledigt. Punkt 7 (#1095)
verweist explizit auf das Trip-Alarm-System — ein anderer Mechanismus (laufender Wächter),
nicht bloß Report-Konfiguration.

### Kern-Befund
Trip-„Alerts" = laufender Abweichungs-Wächter: Ein 15-Minuten-Job wertet konfigurierte
Grenzwerte gegen Live-Wetter aus und schickt bei Überschreitung sofort eine Push-Meldung
(`src/services/trip_alert.py`). Der Orts-Vergleich hat davon **nichts** — er rendert und
versendet nur einen Report zum Termin. „Alerts analog zu Trips" ist damit nicht 1:1
übertragbar, ohne einen neuen Auswertungs-Mechanismus zu bauen. Zusätzlich konzeptionell
fraglich: Der Vergleich ist ein Planungs-Snapshot vor dem Urlaub — man vergleicht, um sich
für einen Ort zu **entscheiden**; für den gewählten Ort legt man dann einen Trip an (der
seine eigenen Alarme hat). Ein Dauer-Wächter über alle Vergleichs-Orte passt darum nicht
offensichtlich zum Nutzungskontext.

### Handlungsvarianten (zur PO-Entscheidung)
- **Variante A — Grenzwerte im Report markieren (empfohlen, mittel):** Pro Metrik
  Grenzwerte im Compare-Editor einstellbar (Bedienung optisch analog Trips). Der
  Vergleichs-Report hebt hervor, welche Orte/Stunden die Grenzwerte reißen. KEIN Wächter,
  keine Push-Meldungen — der Report wird schlauer. Reine Config + Render-Logik, kein neuer
  Scheduler-Job. Datei-Scope: `compare_preset.go` (+Feld), Handler-Merge, Frontend-Step +
  State, Compare-Renderer. ~120–200 LoC, MEDIUM Risiko (Mail-Renderer-Gate).
- **Variante B — voller Alarm-Wächter für Compare (Epic, groß):** Compare-Presets bekommen
  echte Alarmregeln, ein neuer 15-Min-Job wertet sie pro Ort aus (Threshold/Severity/
  Cooldown/Quiet/Dedup/Kanäle) und versendet eigenständige Push-Alerts. Erfordert
  Verallgemeinerung von `trip_alert.py` auf Orte, neuen State-Store, neuen Scheduler-Job.
  Mehrere hundert LoC über Go+Python+Frontend, HIGH Risiko. → eigenes Epic, nicht ein Issue.
- **Variante C — nur amtliche Warnungen (klein):** Nur die bestehende
  `official_alerts_enabled`-Konfiguration im Compare-Editor sichtbar/rund machen. Existiert
  großteils bereits (#1040 Backend, Step5-Toggle). ~30–60 LoC, LOW Risiko.

### Empfehlung
**Variante A.** Sie liefert echten, zum Nutzungskontext passenden Mehrwert („welcher Ort
reißt meine Grenzen"), sieht in der Bedienung aus wie Trip-Alarme, bleibt aber im
Report-Paradigma des Vergleichs (der Report ist das Produkt) und vermeidet einen
konzeptionell fragwürdigen Dauer-Wächter. Variante B nur, falls der PO bewusst ein echtes
Überwachungs-Feature will — dann als eigenes Epic neu schneiden.

### PO-Richtungsentscheidung (2026-07-09)
PO wählte **Variante B (Rund-um-die-Uhr-Wächter)** — MIT der Rückfrage: „Warum alles neu
erfinden? Vergleich und Trip sind fast dasselbe — leg beide nebeneinander und finde heraus,
was wirklich doppelt existieren muss." → Analyse-Fokus verschoben von „neue Engine bauen"
auf „was ist bereits geteilt / teilbar vs. was unterscheidet sich echt".

### Architektur-Gegenüberstellung Trip ↔ Compare (Ergebnis der Kopplungs-Analyse)

**Der Alarm-Auswertungskern ist NICHT trip-verdrahtet — er ist faktisch schon
location-generisch.** Er arbeitet auf `List[SegmentWeatherData]` (Wetter an einem Geo-Punkt)
+ Config-Feldern, liest KEINE stages/waypoints/arrival/dates:
- Generisch/teilbar: Change-Detection (`_detect_all_changes`), Filter
  (`_filter_significant_changes`, `_filter_against_alert_state`), Severity
  (`_highest_severity`), Gating (`_is_quiet_hours`, `_is_throttled_with_cooldown`),
  Kanalwahl (`_effective_alert_channels`), Detektor-Auswahl (`_select_change_detector`).
- **Rendering bereits geteilt** (ADR-0011: ein Renderer, 4 Kanäle) und **Versand bereits
  konsolidiert** (ADR-0017: `NotificationService` als einziger Orchestrierer).
- **State/Dedup:** `trip_id` ist nur ein Datei-Namespace, innere Keys sind
  metrik-/geo-basiert (`metric:segment_id`) → trivial auf `preset_id + location` umschaltbar.

**Was echt trip-gebunden bleibt (der eigentliche Aufwand):**
1. **Wetter-Beschaffung:** Trip fährt über `SegmentWeatherService`/`TripSegment`, Compare
   über `ForecastService`/`Location` — zwei Wrapper über DERSELBEN Provider-Ebene. Eine
   geteilte location-generische Beschaffungs-Schnittstelle muss eingezogen werden.
2. **Der Δ-Anker (ADR-0009) — die konzeptionelle Kernfrage:** Trip-Alarme sind KEIN
   Absolut-Schwellwert-System. Sie melden „Wetter weicht ab von dem, was wir dir zuletzt
   im Briefing gemeldet haben" (persistierter Snapshot = Vergleichsanker). Der Orts-Vergleich
   ist heute ein **zustandsloses One-Shot-Ranking** ohne pro-Ort-Snapshot → ihm fehlt der
   Anker, gegen den ein „Wächter analog zu Trips" vergleichen würde.

**Datenmodell:** 5 fast deckungsgleiche Geo-Punkt-Typen (`Waypoint` Go/Py, `SavedLocation`,
`Location`, `GPXPoint`), gemeinsamer Nenner `lat/lon/elevation/name`. Kein geteiltes
Coordinate-Modell. Trip = `Stages[]→Waypoints[]` (zeitlich sequenziert), Compare = flache
`LocationIDs[]` + ein Zeitfenster (parallel). Precedent für „shared statt dupliziert":
epic_1073 baut bereits einen generischen Official-Alerts-Eingang, den „sowohl Compare als
auch Trip füllen".

### Empfehlung (revidiert)
**Nicht duplizieren — konsolidieren.** Die Alarm-„Gehirn"-Logik, das Rendering und der
Versand sind bereits geteilt oder trivial teilbar. Der richtige Weg ist: die
Deviation-Alert-Auswertung aus `trip_alert.py` in einen **location-generischen Shared-Service**
herauslösen (Trip bleibt unverändert funktionsfähig = erster Consumer) und den Orts-Vergleich
als **zweiten Consumer** anschließen. Nur der Report bleibt getrennt (das ist der einzige
echt unterschiedliche Teil). → Das ist größer als ein Einzel-Issue: **eigenes ADR + Epic
mit 3 Scheiben** (1: Engine location-generisch herauslösen ohne Verhaltensänderung; 2:
Compare bekommt pro-Ort-Snapshot-Anker + wird als Consumer verdrahtet; 3: Config-UI im
Compare-Editor analog Trip-Alerts-Tab).

### Verbleibende Design-Frage (BLOCKIEREND — PO, produktseitig)
**Wann soll der Orts-Vergleich Alarm schlagen?**
- **Abweichung (wie Trips, ADR-0009-konform):** Alarm, wenn sich die Vorhersage deutlich
  gegenüber dem zuletzt gemeldeten Stand ändert. Maximale Wiederverwendung, echt „analog zu
  Trips". Braucht den pro-Ort-Snapshot-Anker (Scheibe 2).
- **Absoluter Grenzwert:** Alarm, sobald ein fester Grenzwert gerissen wird (z.B. Böen
  >60 km/h), unabhängig von Vorhersage-Änderung. Einfacher verständlich, aber technisch
  NICHT wie Trip-Alarme → eigene Logik, weniger Wiederverwendung, widerspricht „analog".
