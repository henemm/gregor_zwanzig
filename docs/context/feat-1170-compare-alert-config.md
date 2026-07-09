# Context: feat-1170-compare-alert-config

## Request Summary
Issue #1170 (Scheibe 3/3 von Epic #1095): Der Nutzer soll die Orts-Vergleich-Alarme im
Compare-Editor konfigurieren können — Empfindlichkeit pro Wetterwert, Cooldown, Ruhezeiten —
analog zum Trip-Alerts-Tab. Backend #1168/#1169 wertet die Alarme bereits aus; heute liest die
Auswertung eine **hartkodierte Default-Config** (standard/120min/nur-Email). Diese Scheibe macht
sie **pro Preset editierbar** — additive Persistenz-Felder + Bedien-UI.

## Vorbedingung (bereits live)
- **#1168** (373fd09a): `DeviationAlertEngine` location-generisch herausgelöst.
- **#1169** (6442704d): Compare als 2. Consumer. `compare_alert.py` liest die Alarm-Config
  bereits **vorwärtskompatibel** via `preset.get(feld, DEFAULT)` — d.h. neue Preset-Felder
  werden sofort wirksam, sobald sie persistiert sind. Cooldown-Store keyed `preset_id`,
  Dedup entity_id `preset_id:location_id`.

## Related Files

### Backend — Model & Handler & Store
| Datei | Relevanz |
|------|-----------|
| `internal/model/compare_preset.go:13-45` | `ComparePreset`-Struct. Pointer-Blaupause `OfficialAlertsEnabled *bool` (:38), `HourlyEnabled *bool` (:44). `DisplayConfig map[string]interface{}` (:33) — hier lebt `metric_alert_levels` (KEIN Struct-Feld) |
| `internal/model/trip.go:53-64` | Typdefinition `AlertRule` (bereits im Package `model`, direkt nutzbar) |
| `internal/model/trip.go:97-100` | Trip-Alarm-Felder: `AlertRules []AlertRule` (:97, kein Pointer/omitempty), `AlertCooldownMinutes *int` (:98), `AlertQuietFrom *string` (:99), `AlertQuietTo *string` (:100) — die 4 additiv zu übernehmenden Felder |
| `internal/model/trip.go:120-255` | `AlertableMetrics`, Defaults, `ActiveAlertableMetricIDs(display_config["metrics"])`, `SyncAlertRules()` (Self-Heal-Merge, genau 1 delta-Regel pro aktiver Metrik) |
| `internal/handler/compare_preset.go:191-246` | `UpdateComparePresetHandler` RMW-nil-Merge. **Decodiert in volle `model.ComparePreset`, NICHT in Pointer-DTO.** Pointer-nil-Merge-Muster `official_alerts_enabled` :217-219, `hourly_enabled` :221-223. `DisplayConfig` wird bei nil **blind ersetzt** (:207-209) — kein Feld-Level-Merge wie beim Trip |
| `internal/handler/trip.go:140-156` | `tripUpdateRequest`-Pointer-DTO als Vorbild: `AlertRules *[]model.AlertRule` (:148) etc. — kann „absent" (nil) von „explizit leer gesendet" unterscheiden |
| `internal/handler/trip.go:230-253` | Trip-Merge: `if req.AlertRules != nil { existing.AlertRules = *req.AlertRules }` usw. |
| `internal/store/compare_preset.go:11-60` | Load/Save `data/users/{userId}/compare_presets.json`. Nur Weekday-/ForecastHours-Default-Migration, **kein Alert-Sync**. JSON additiv-tolerant → kein Schema-Bruch |
| `internal/store/trip.go:82-114` | Trip: nil-Coercion `AlertRules` + `SyncAlertRules` compute-on-save + `migrateMetricAlertLevels(display_config)` (`metric_alert_levels` = Sub-Key von `display_config`) |

### Frontend — Vorbild (Trip-Alerts-Tab)
| Datei | Relevanz |
|------|-----------|
| `frontend/src/lib/components/alerts-tab/AlertsTab.svelte:59-75` | Zentraler Save: `display_config.metric_alert_levels` (Record metric→SensLevel) + `alert_cooldown_minutes` + `alert_quiet_from/to`. **Per-Tab-Autosave** via `saveController.schedule()` |
| `frontend/src/lib/components/alerts-tab/AlertMetricLevelTable.svelte` | Empfindlichkeit pro Metrik (`off\|entspannt\|standard\|sensibel`), nur aktiv gewählte Metriken |
| `frontend/src/lib/components/alerts-tab/AlertCooldownCard.svelte` | `$bindable cooldown_minutes?: number` |
| `frontend/src/lib/components/alerts-tab/AlertQuietHoursCard.svelte` | `$bindable quiet_from/to`, Toggle + 2 time-Inputs, Mitternachts-Wrap |
| `frontend/src/lib/components/alerts-tab/alertMetricTable.ts` | `activeAlertableMetrics()`, `ALERTABLE_METRICS`, `migrateAlertPreset()` |
| `frontend/src/lib/components/trip-detail/TripTabs.svelte:169` | Einbindung `<AlertsTab {trip} {onTripUpdate} {saveController} />` |

### Frontend — Zielsystem (Compare-Editor)
| Datei | Relevanz |
|------|-----------|
| `frontend/src/lib/components/compare/CompareEditor.svelte:44-50` | `TAB_DEFS` = `vergleich\|orte\|idealwerte\|layout\|versand` — **kein Alarm-Tab heute** |
| `frontend/src/lib/components/compare/CompareEditor.svelte:69-85` | `initial`-Snapshot + `dirty`-Derived → Speichern-Button (:587). Neue Felder müssen hier + Post-Save-Reset (:163-168) rein, sonst wird Button bei Alarm-Änderung nicht aktiv |
| `frontend/src/lib/components/compare/CompareEditor.svelte:138-175` | **Pfad A** `handleSave()` → ruft `buildComparePresetSavePayload` direkt. Reicht `forecastHours/officialAlertsEnabled/topN/hourlyEnabled` **nicht** explizit durch (nur Round-Trip-Spread rettet sie) |
| `frontend/src/lib/components/compare/compareEditorSave.ts:13-99` | **Gemeinsame Pure-Function** beider Edit-Pfade: `CompareEditorEdits`-Interface (:13-32) + `displayConfig`-Bau (:46-79). Alarm-Felder hier zentral einhängen |
| `frontend/src/lib/components/compare/compareWizardState.svelte.ts:14-47` | `wiz`-State: nur `officialAlertsEnabled` (:40), **keine Alarm-State-Felder** |
| `frontend/src/lib/components/compare/compareWizardState.svelte.ts:200-227` | **Pfad B** `saveComparePreset()` (Edit via wiz) → ebenfalls `buildComparePresetSavePayload` |
| `frontend/src/lib/components/compare/compareWizardState.svelte.ts:158-192` | **Pfad C** `saveNewPreset()` (Create, POST) — eigener Payload, `display_config`-Bau :161-181 |
| `frontend/src/routes/compare/[id]/edit/+page.svelte:18-57` | Edit-Init/Hydration: `data.preset.*`→`state.*` mit `?? default`-Fallbacks (:36 official, :38 topN, :46-57 metrics). Neue Alarm-Felder brauchen je einen Init |
| `frontend/src/lib/types.ts:480-499` | FE-Typ `ComparePreset`. `display_config?: Record<string,unknown>` (:496, untypisiert → `metric_alert_levels` ohne Typänderung schreibbar). Top-Level-Alarm-Felder bräuchten Interface-Erweiterung |
| `frontend/src/lib/types.ts:70,232-240,275-278` | `SensLevel`, `DisplayConfig` (getypt, nur Trip), Trip-Alarm-Felder als Referenz |

### Auswertung (liest die Config bereits — nicht zu ändern)
| Datei | Relevanz |
|------|-----------|
| `src/services/compare_alert.py` | `CompareAlertService`, liest `preset.get(feld, DEFAULT)` vorwärtskompatibel (#1169) |
| `src/services/deviation_alert_engine.py` | Location-generischer Auswertungskern (#1168), `AlertEvaluationConfig` |

## Existing Patterns
- **Pointer-`*bool`/`*int`/`*string` für neue Config-Felder** (Altdaten-sicher): `nil` = Feld fehlte
  (Default aktiv), gesetzter Wert = bewusste Wahl.
- **RMW-nil-Merge im Handler** statt Blind-Replace (BUG-DATALOSS-Pflicht, CLAUDE.md).
- **`metric_alert_levels` lebt in `display_config`** (Sub-Key), NICHT als eigenes Struct-Feld —
  sowohl Backend (`map[string]interface{}`) als auch FE (`Record<string,unknown>`) tragen das
  bereits ohne Typänderung.
- **user_id konsequent aus Auth-Kontext** (`WithUser`/`UserIDFromContext`), nie `"default"`.
- **JSON additiv-tolerant** → keine explizite Schema-Migration für neue Felder nötig.

## Dependencies
- **Upstream:** #1168/#1169 (Auswertung liest Config bereits vorwärtskompatibel) — live.
- **Downstream:** `compare_alert.py` (Config-Konsument), Compare-Editor-UI, PUT
  `/api/compare/presets/{id}` (Pfad A/B), POST `/api/compare/presets` (Pfad C).

## Existing Specs
- `docs/context/feat-1095-compare-alerts.md` — Epic-Architektur-Analyse (Trip↔Compare-Kopplung)
- `docs/specs/modules/issue_458_compare_preset_backend.md` — ComparePreset-Backend
- `docs/features/epic-438-compare-wizard.md` — Compare-Wizard (5 Steps)

## Risks & Considerations / Offene Design-Fragen (für Analyse-Phase)
1. **PO-Frage #1182 — Cooldown-Granularität:** wirkt der Cooldown **pro Ort** oder **preset-weit**?
   #1169 keyed den Cooldown-Store aktuell auf `preset_id`. Diese Scheibe entscheidet mit.
2. **Backend-Merge-Architektur:** Der Compare-Handler decodiert in die volle `model.ComparePreset`,
   nicht in ein Pointer-DTO. Für `AlertRules []AlertRule` (kein Pointer) kann er „absent" nicht von
   „leer gesendet" unterscheiden. Optionen: (a) Pointer-DTO wie `tripUpdateRequest` einführen
   (sauber, mehr Code), (b) Alarm-Config vollständig in `display_config` ablegen (nutzt bestehenden
   Blind-Replace, weniger neue Top-Level-Felder). **Analyse-Entscheidung.**
3. **Frontend-Muster-Bruch:** AlertsTab nutzt Per-Tab-Autosave (`saveController`), Compare nutzt
   zentrales `handleSave()`+dirty-Tracking. 1:1-Wiederverwendung von AlertsTab unmöglich. Optionen:
   Controls gegen `wiz.*`-State neu verdrahten vs. analogen Autosave-Pfad einführen.
4. **Drei Save-Pfade — stiller Datenverlust:** Pfad A (`CompareEditor.handleSave`), Pfad B
   (`wiz.saveComparePreset`), Pfad C (`saveNewPreset`) + Edit-Hydration MÜSSEN alle die neuen
   Felder führen. Pfad A reicht heute schon `forecastHours` etc. nicht explizit durch.
5. **Datenschema-Merge:** `compare_preset.go`-Edit triggert `data_schema_backup.py`. RMW Pflicht.
6. **user_id-Isolation:** 2-Nutzer-Test bei jedem datenbewegenden Endpoint.
7. **Mail-Validator-Gate:** falls Compare-Mail-Rendering berührt wird → `email_spec_validator.py`
   (X-GZ-Mail-Type: compare), nur Exit 0 = „E2E bestanden". (Diese Scheibe ist primär Config-UI;
   Rendering sollte unberührt bleiben — verifizieren.)

## Analysis

### Type
Feature (Bedien-UI + additive Persistenz). Kein Bug.

### ENTSCHEIDENDER BEFUND (Verifikation `src/services/compare_alert.py`, live #1169)
Die Scheibe-2-Auswertung liest die Alarm-Config aus diesen Preset-Keys (`_build_eval_config` :149-158):
- `preset.get("cooldown_minutes", 120)` — **Top-Level** (Trip nutzt `alert_cooldown_minutes`)
- `preset.get("quiet_from")` / `preset.get("quiet_to")` — **Top-Level** (Trip: `alert_quiet_from/to`)
- `preset.get("metric_alert_levels")` — **Top-Level** (Trip: in `display_config`)
- `channels={"email"}` — **hartkodiert**, wird NICHT aus dem Preset gelesen
- **`alert_rules` wird NICHT gelesen** — die Regeln werden zur Laufzeit aus `metric_alert_levels`
  via `expand_per_metric_levels()` erzeugt. `metric_alert_levels: dict[str,str]` = metric→SensLevel
  (`off|entspannt|standard|sensibel`) — **identisches Vokabular/Format wie Trip-`AlertsTab`**.

**Konsequenz 1 (Scope-Vereinfachung):** Es ist **KEIN** `AlertRules []AlertRule`-Feld im Compare-Model
nötig. Damit entfällt das Pointer-DTO-Problem komplett (der einzige Nicht-Pointer-Typ). Alle neuen
persistierten Felder sind Pointer/`display_config` → sauberer nil-Merge analog `official_alerts_enabled`
(`compare_preset.go:217-223`), **kein Handler-DTO-Refactor**.

**Konsequenz 2 (Naming-Angleichung):** Die aktuell von #1169 gelesenen Keys werden heute von NICHTS
geschrieben (Auswertung fällt immer auf Defaults zurück) → **null Daten-Migrationsrisiko**, freie
Namenswahl. Entscheidung: **Trip-identische Keys/Struktur** (Epic-Prinzip „analog zu Trips",
Konsolidierung). Dazu 4 Read-Zeilen in `compare_alert.py` angleichen:
`alert_cooldown_minutes`, `alert_quiet_from`, `alert_quiet_to` (Top-Level) + `metric_alert_levels`
aus `display_config`. So gilt EIN Vokabular Trip+Compare und die FE-Controls sind 1:1 wiederverwendbar.

### Affected Files (with changes)
| File | Change | Description |
|------|--------|-------------|
| `internal/model/compare_preset.go` | MODIFY | +3 Pointer-Felder `AlertCooldownMinutes *int`, `AlertQuietFrom/To *string` (Trip-JSON-Tags). `metric_alert_levels` nutzt bestehendes `DisplayConfig` |
| `internal/handler/compare_preset.go` | MODIFY | +3 nil-Merge-Blöcke analog :217-223 (RMW). `display_config`-Blind-Replace trägt `metric_alert_levels` bereits |
| `src/services/compare_alert.py` | MODIFY | 4 Read-Zeilen auf Trip-Keys angleichen (`alert_cooldown_minutes`/`alert_quiet_from`/`alert_quiet_to` + `metric_alert_levels` aus `display_config`) |
| `frontend/src/lib/components/compare/CompareEditor.svelte` | MODIFY | Neuer Tab „Alarme" (TAB_DEFS/Panel); `initial`+`dirty`+Post-Save-Reset + `handleSave`-Payload um Alarm-Felder |
| `frontend/src/lib/components/compare/CompareAlarmSection.svelte` | CREATE | Sektion, die `AlertMetricLevelTable`+`AlertCooldownCard`+`AlertQuietHoursCard` gegen `wiz.*`-State verdrahtet |
| `frontend/src/lib/components/compare/compareEditorSave.ts` | MODIFY | `CompareEditorEdits` +Alarm-Felder; `metric_alert_levels`→displayConfig, cooldown/quiet→Top-Level body |
| `frontend/src/lib/components/compare/compareWizardState.svelte.ts` | MODIFY | +4 `$state`-Felder; Pfad B (`saveComparePreset`) + Pfad C (`saveNewPreset`) führen sie |
| `frontend/src/routes/compare/[id]/edit/+page.svelte` | MODIFY | Edit-Init mit `?? default`-Fallback je Feld |
| `frontend/src/lib/types.ts` | MODIFY | `ComparePreset` +Top-Level-Alarm-Felder (display_config bleibt `Record`) |

Wiederverwendet ohne Änderung: `AlertMetricLevelTable`, `AlertCooldownCard`, `AlertQuietHoursCard`,
`alertMetricTable.ts` (`activeAlertableMetrics`).

### Scope Assessment
- Files: ~9 (1 CREATE, 8 MODIFY)
- Est. LoC: +180…230 (FE-lastig). **Über 250-Default möglich** — ggf. Override nach Rückfrage.
- Risk: **MEDIUM** (Persistenz-Merge + 3 Save-Pfade + live-`compare_alert.py`-Read-Angleichung)

### Technical Approach
1. Backend: 3 Pointer-Felder + nil-Merge (RMW) + `metric_alert_levels` via display_config.
2. Python: 4 Read-Zeilen Trip-angleichen (kein Verhaltensbruch, keine Persistenzdaten betroffen).
3. Frontend: neuer „Alarme"-Tab, vorhandene Alarm-Controls wiederverwendet, an alle 3 Save-Pfade
   + Edit-Hydration angeschlossen. Kein Kanal-Selektor (Compare = email-only, Scheibe 2).
4. Kein Compare-Mail-Rendering-Change → Mail-Validator-Gate erwartungsgemäß nicht betroffen (verifizieren).

### Open Questions
- [x] **#1182 Cooldown-Granularität** — **PO-ENTSCHEIDUNG 2026-07-09: preset-weit.** Eine Mail pro
  Zeitfenster, alle Orte gebündelt. Bestätigt Ist-Verhalten #1169 (Cooldown-Gate keyed `preset_id`).
  KEINE Änderung am Cooldown-Keying nötig. UI zeigt EIN Cooldown-Feld (Trip-analog). #1182 erledigt.
