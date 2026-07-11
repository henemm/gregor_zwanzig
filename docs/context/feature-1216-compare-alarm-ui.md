# Context: feature-1216-compare-alarm-ui (#1216 Slice 2b)

## Request Summary
Sichtbarer Schalter im Ortsvergleich-Editor für den amtlichen Standalone-Alarm
(Trigger + Telegram/SMS-Kanäle) **plus** Go-Scheduler-Eintrag für
`/api/scheduler/compare-official-alert-checks`. Sende-Logik (Slice 2a) ist live,
aber die steuernden Preset-Felder sind heute weder persistierbar noch im UI, und
der Alarm feuert nur bei manuellem Endpoint-Aufruf.

## Die drei zu steuernden Preset-Felder
Der Python-Service `src/services/compare_official_alert.py` liest bereits aus dem
persistierten Preset-JSON (`data/users/<uid>/compare_presets.json`):

| Feld | Bedeutung | Default | Quelle |
|------|-----------|---------|--------|
| `official_alert_triggers_enabled` | Standalone-Alarm feuert für diesen Vergleich | `True` (an) | `compare_official_alert.py:71` |
| `send_telegram` | Kanal-Opt-in Telegram | falsy (aus) | `compare_official_alert.py:151` |
| `send_sms` | Kanal-Opt-in SMS | falsy (aus) | `compare_official_alert.py:153` |

**Wichtig:** Der Trigger heißt `official_alert_triggers_enabled` und ist **getrennt**
vom bestehenden „Fetch"-Toggle `official_alerts_enabled` (steuert nur, ob Quellen
abgefragt werden). Beide dürfen nicht vermischt werden.

## Related Files
| Datei | Relevanz |
|------|-----------|
| `src/services/compare_official_alert.py` | Liest die 3 Felder aus dem Preset-JSON; Gating `:71`, Kanäle `:147-155` |
| `api/routers/scheduler.py:90-98` | Endpoint `/compare-official-alert-checks` existiert bereits (Slice 2a) |
| `internal/model/compare_preset.go:14-61` | `ComparePreset`-Struct — **keine** der 3 Felder vorhanden; Pointer-Pattern-Vorbild `OfficialAlertsEnabled`/`RadarAlertEnabled` |
| `internal/store/compare_preset.go:47-60` | `SaveComparePresets` **ersetzt** die Datei, serialisiert nur Struct-Felder → Nicht-Struct-Felder gehen verloren (kein JSON-Passthrough außer `DisplayConfig`) |
| `internal/handler/compare_preset.go:173-276` | RMW-Merge im `UpdateComparePresetHandler`; nil-Pointer-Merge je Feld (`:216-239`); `user_id` aus Auth-Kontext (`middleware.UserIDFromContext` + `s.WithUser`) |
| `internal/scheduler/scheduler.go:91-102` | Jobs-Tabelle (8 Jobs); `compareRadarAlertChecks` `:176-180` als Vorbild; **hartkodiertes** `"Started: 8 jobs"` `:114` |
| `internal/scheduler/scheduler_test.go:199-201` | Test asserted `len(jobs) != 8` → muss auf 9 |
| `frontend/src/lib/components/compare/compareWizardState.svelte.ts:33-49` | Wizard-State ($state-Runes); `sendTelegram/sendSms` existieren (fließen aber in Legacy-Subscription-Save, nicht Preset!) |
| `frontend/src/lib/components/compare/steps/Step5Versand.svelte:104-142` | Kanal-Toggles + „Amtliche Warnungen"-Toggle via `ChannelToggle` |
| `frontend/src/lib/components/compare/CompareAlarmSection.svelte:2-6` | Doku: „**Kein Kanal-Selektor: Compare-Alarme bleiben E-Mail-only** (#1169)" — Design-Spannung, s.u. |
| `frontend/src/lib/components/compare/compareEditorSave.ts:13-121` | PUT-Payload; Spread-Guard-Muster je Feld; Endpoint `PUT /api/compare/presets/{id}` |
| `frontend/src/lib/types.ts:480-505` | `ComparePreset`-Typ — `send_telegram/send_sms` fehlen |
| `frontend/src/lib/components/compare/CompareEditor.svelte:91-216` | Baseline-Snapshot/Dirty-Tracking (5 Stellen) |

## Existing Patterns
- **Go Pointer-Pattern:** `*bool`/`*int` mit `json:",omitempty"`, nil = Feld fehlte
  (Altdaten) → Python-Default greift; gesetzter Wert = bewusste Wahl. Vorbild
  `OfficialAlertsEnabled`/`RadarAlertEnabled` (`compare_preset.go:39,46`).
- **Go RMW-Merge im Handler:** `if updated.X == nil { updated.X = original.X }`
  (`compare_preset.go:216-239`) — Pflicht, sonst überschreibt PUT das Feld.
- **Scheduler-Job:** schlanker Wrapper `recordRun(id, runForAllUsers(id, path))` +
  Zeile in Jobs-Tabelle + Job-Anzahl in Log **und** Test anheben.
- **Frontend-Toggle:** `ChannelToggle` (Callback `onchange:(checked)=>...`, kein
  `bind:`), plus Feld an 6 Stellen führen (State, Typ, Render, PUT-Save,
  POST-Save, Dirty-Baseline).

## Dependencies
- **Upstream (was wir nutzen):** bestehender Python-Endpoint + Service (Slice 2a),
  `ChannelToggle`-Atom, `runForAllUsers`/`triggerEndpointForUser`.
- **Downstream (was auf uns baut):** der Scheduler feuert dann automatisch alle
  15 Min für alle User; die persistierten Felder steuern Python direkt.

## Existing Specs
- `docs/specs/modules/issue_1216_slice2_compare_official_alert.md` — Slice 2a-Spec (Service/Endpoint)
- Slice-1-Spec (Trip) als Renderer-Referenz

## Risks & Considerations
1. **Design-Spannung E-Mail-only (#1169) vs. Telegram/SMS-Opt-in (#1216):** Der
   Deviation-Alarm (#1169) ist bewusst E-Mail-only; der amtliche Standalone-Alarm
   (#1216 Slice 2a) unterstützt bewusst Telegram/SMS. Die neuen Kanal-Schalter
   dürfen **nur** den amtlichen Alarm betreffen, nicht den Deviation-Alarm. UI-
   Platzierung + Beschriftung müssen das eindeutig machen (→ Analyse/Spec).
2. **Namens-/Pfad-Kollision `sendTelegram`/`sendSms`:** Diese Wizard-Felder
   existieren schon, fließen aber in den **Legacy-Subscription**-Save
   (`/api/subscriptions`), NICHT in den Preset-Save. Klären, ob wiederverwenden
   oder neue Preset-Felder — Verwechslungsgefahr.
3. **Persistenz-Lücke = Kern der Arbeit:** Ohne Struct-Felder + Handler-Merge
   gehen die 3 Felder bei jedem Save verloren. Read-Modify-Write mit Merge ist
   Pflicht (Daten-Schema-Regel), nil-Pointer-Pattern.
4. **Multi-User:** `user_id` konsequent aus Auth-Kontext, nie `"default"`. Test
   mit zwei verschiedenen Nutzern.
5. **Scheduler-Doppelpflege:** Job-Anzahl an **zwei** Stellen (`scheduler.go:114`
   Log + `scheduler_test.go:199` Assertion) synchron halten, sonst roter Test.
6. **Trigger-Default `True`:** Bestehende Vergleiche ohne Feld feuern sofort
   (Alt-Presets) — bewusst? Alarm ist amtliche Warnung (sicherheitsrelevant),
   Default-an ist plausibel, aber PO-Bestätigung in ACs.

## Analysis

### Type
Feature (additive Verdrahtung + Scheduler-Job; kein Verhaltensfix am bestehenden Code)

### Entscheidungen (Best Practice)
- **Persistenz-Ort:** Alle drei Felder auf `ComparePreset` (das Objekt, das der
  Python-Service liest), JSON-Keys **`official_alert_triggers_enabled`**,
  **`send_telegram`**, **`send_sms`** → **keine Python-Änderung** nötig.
  Pointer-Pattern (`*bool`, nil=Default). Der Legacy-Subscription-Pfad wird
  **nicht** wiederverwendet — er beschreibt ein anderes Objekt.
- **Kanäle vereinheitlicht statt dupliziert:** Die bestehenden Versand-Toggles
  E-Mail/Telegram/SMS (Step5Versand) werden **zusätzlich in den Preset-Save
  geschrieben**, sodass der amtliche Alarm sie respektiert. Keine neuen,
  parallelen Kanal-Schalter (Vermeidung von Redundanz + „welcher gilt jetzt?").
  Deckt „generell um Alarme": eine Kanalwahl gilt überall, wo Kanäle unterstützt
  werden; Deviation/Radar bleiben strukturell E-Mail-only.
- **Ein neuer Toggle:** Der Standalone-Alarm-An/Aus (`official_alert_triggers_enabled`)
  gehört in den **Alarme-Tab** (`CompareAlarmSection`) neben den Radar-Alarm —
  denn es ist eine Alarm-Einstellung. Der `#1169`-Kommentar „kein Kanal-Selektor"
  bleibt gewahrt (An/Aus ist kein Kanal-Selektor). Der bestehende „Amtliche
  Warnungen"-Toggle (Fetch/Anzeige, `official_alerts_enabled`) in Versand bleibt
  unverändert — klare Label-Abgrenzung nötig.

### Affected Files (with changes)
| File | Change | Description |
|------|--------|-------------|
| `internal/model/compare_preset.go` | MODIFY | +3 Felder `OfficialAlertTriggersEnabled *bool`, `SendTelegram *bool`, `SendSms *bool` |
| `internal/handler/compare_preset.go` | MODIFY | nil-Pointer-Merge der 3 Felder im Update-Handler (RMW) |
| `internal/scheduler/scheduler.go` | MODIFY | Job-Methode `compareOfficialAlertChecks` + Jobs-Zeile + Log „8"→"9" |
| `internal/scheduler/scheduler_test.go` | MODIFY | `len(jobs)` 8→9 + Cron-/Endpoint-Test für neuen Job |
| `internal/handler/compare_preset_official_alerts_test.go` | MODIFY/CREATE | Roundtrip-Test der 3 Felder, zwei User |
| `frontend/src/lib/types.ts` | MODIFY | `ComparePreset` +3 optionale Felder |
| `frontend/src/lib/components/compare/compareWizardState.svelte.ts` | MODIFY | +`officialAlertTriggersEnabled` Rune; Kanäle in Preset-Save |
| `frontend/src/lib/components/compare/CompareAlarmSection.svelte` | MODIFY | +Trigger-Toggle (ChannelToggle) |
| `frontend/src/lib/components/compare/compareEditorSave.ts` | MODIFY | +Trigger im Edits-Interface + Spread-Guards (Trigger + Kanäle) |
| `frontend/src/lib/components/compare/CompareEditor.svelte` | MODIFY | Baseline-Snapshot/Dirty-Tracking (5 Stellen) |
| `frontend/src/lib/components/compare/*.test.ts` | MODIFY/CREATE | Save-Payload-Test |
| **Python** | KEINE | Endpoint + Service lesen die Keys bereits |

### Scope Assessment
- Files: ~10–12
- Estimated LoC: +130 / −5 (inkl. Tests; unter 250-Limit)
- Risk Level: MEDIUM (Alert-Pfad + neuer All-User-Scheduler-Job; Sende-Logik selbst schon getestet)

### Technical Approach
Reine Verdrahtungs-/Persistenz-Arbeit über etablierte Muster (Slice 1/2a). Kern:
die drei Preset-Felder end-to-end round-trippen (FE-State → PUT/POST → Go-Struct +
Merge → JSON → Python) und den Scheduler-Job registrieren. Kein neuer Sende-Code.

### Dependencies & Reihenfolge
1. Go-Modell + Handler-Merge (Persistenz-Fundament) → 2. Go-Scheduler-Job →
3. Frontend-State/Typ/Render/Save → 4. Tests (Go-Roundtrip, Scheduler, FE-Save).

### Open Questions (für Spec/ACs)
- [ ] Trigger-Default für Alt-Presets = an (sofortiges Feuern) — bestätigen.
- [ ] Label-Abgrenzung „Amtliche Warnungen" (Fetch) vs. „Amtliche-Warnungen-Alarm" (Trigger).
- [ ] Kanal-Vereinheitlichung (Versand-Toggles gelten auch für Alarm) — bestätigen.
