---
entity_id: issue_1258_alarme_tab_official_warnings
type: module
created: 2026-07-15
updated: 2026-07-15
status: approved
version: "1.0"
tags: [compare, trip, alerts, shared-components, data-model, official-warnings]
---

<!-- Issue #1258 — Compare: eigener Alarme-Tab analog Trip + amtliche Warnungen
     als Abo-Feld (+ gebündelt R5 Kanal-Verbindungsstatus aus #1256) -->

# Issue 1258 — Alarme-Tab + officialWarnings-Abo-Feld (Programm-Spec)

## Approval

- [x] Approved — PO 2026-07-15 („Approved", Session feat-1258-compare-alarme-tab)

## Purpose

Der Ortsvergleich bekommt — analog zum (wiederhergestellten) Trip-Editor —
einen eigenen Alarme-Tab: die gesamte Alert-Zustellung (Kanäle, Cooldown,
Stille Stunden, amtliche Warnungen, Beispiel-Warnung) zieht aus dem
Versand-Tab in einen neuen **geteilten** Organism `AlarmeTab.svelte`
(context `route`|`vergleich`) um. Amtliche Warnungen bekommen ein neues,
funktional scharfes Feld `official_warnings.enabled` (+ optionales
`sources[]`), das Trip UND Vergleich gemeinsam nutzen und das die bisherige
Sofort-Alarm-Steuerung ablöst — ohne bei Bestandsdaten das gesendete
Verhalten zu ändern. Gebündelt: R5 aus #1258/#1256 — ehrlicher
Kanal-Verbindungsstatus im geteilten `VTBriefingChannels`.

Diese Spec ist die **Programm-Spec** für das gesamte Issue #1258. Die
Umsetzung erfolgt in sechs Scheiben (S1–S6), je eigener Workflow. Jedes AC
ist einer Scheibe zugeordnet (siehe „Scheiben-Zuordnung").

## Source

> **Schicht-Hinweis geprüft:** Go-API (`internal/`), Python-Core
> (`src/services/`, `src/app/`), Frontend (`frontend/src/lib/components/`).
> Alle drei Schichten sind betroffen, siehe Dateiliste je Scheibe.

- **File (Go, Datenmodell):** `internal/model/trip.go:126-130`
  (`OfficialAlertsEnabled`, `OfficialAlertTriggersEnabled`) — neues Feld
  `OfficialWarnings *OfficialWarningsConfig` ergänzt
- **File (Go, Datenmodell):** `internal/model/compare_preset.go:47-91`
  (analoge Bestandsfelder) — dito
- **File (Go, Handler RMW):** `internal/handler/trip.go:236-262`,
  `internal/handler/compare_preset.go:285-319`
- **File (Go, Store/Migration):** `internal/store/trip.go`,
  `internal/store/compare_preset.go`, neu `internal/store/migrate_1258.go`
  (Vorbild `internal/store/migrate_1257.go`)
- **File (Go, Profil):** `internal/handler/auth.go:442-458`
  (`profileResponse`) — R5-Feld ergänzen
- **File (Python, Parität):** `src/app/trip.py:192-203`,
  `src/app/models.py:847-895` (`ComparePreset`)
- **File (Python, Pipeline):** `src/services/trip_alert.py:328`
  (`check_official_alert_triggers`), `src/services/compare_official_alert.py:161-169`
  (`_effective_channels`)
- **File (Python, Quellen-Registry):** `src/services/official_alerts/__init__.py:22-26`
- **File (Frontend, neu, geteilt):**
  `frontend/src/lib/components/shared/AlarmeTab.svelte`,
  `frontend/src/lib/components/shared/AlertChannelPicker.svelte`
- **File (Frontend, geteilt, betroffen):**
  `frontend/src/lib/components/shared/VersandTab.svelte:263-314/362-366`,
  `frontend/src/lib/components/shared/versand-tab/VTBriefingChannels.svelte`,
  `frontend/src/lib/components/shared/versand-tab/VTAlertSample.svelte`,
  `frontend/src/lib/components/shared/corridor-editor/CorridorEditor.svelte:84`
- **File (Frontend, Trip):**
  `frontend/src/lib/components/trip-detail/TripTabs.svelte:70-77`,
  `frontend/src/lib/components/trip-detail/BriefingScheduleTab.svelte:104-116`
- **File (Frontend, Compare):**
  `frontend/src/lib/components/compare/CompareEditor.svelte:110-117`,
  `frontend/src/lib/components/compare/CompareAlarmSection.svelte` (entfällt),
  `frontend/src/lib/components/compare/CompareTabs.svelte:75-82`,
  `frontend/src/lib/components/compare/compareWizardState.svelte.ts:45-58`,
  `frontend/src/lib/components/compare/compareHubWizardBridge.ts`,
  `frontend/src/lib/components/compare/compareEditorSave.ts:75/161`

## Estimated Scope

- **LoC:** ~950-1250 netto über alle 6 Scheiben (jede Scheibe einzeln
  <=250-300 LoC, S1 mit Override-Bedarf lt. Analyse)
- **Files:** ~25-30
- **Effort:** high

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `internal/store/migrate_1257.go` | Vorbild | Idempotente rückwirkende Batch-Migration (Read-Modify-Write via LoadTrip/SaveTrip) |
| `src/services/official_alerts/` (Registry) | intern | Quellen-Vokabular für `official_warnings.sources[]`-Filter |
| `/api/auth/profile` (`internal/handler/auth.go`) | API | Kanal-Kontaktdaten + (neu) E-Mail-Bestätigungsstatus für R5 |
| `frontend/src/lib/components/shared/VersandTab.svelte` | Frontend | Muster für `context="route"|"vergleich"`-Organismen, Auto-Save-$effect |
| `frontend/src/lib/components/shared/corridor-editor/CorridorEditor.svelte` | Frontend | `notify`-Toggles (bleiben dort), Zähler `notifyN` für Read-only-Zusammenfassung im Alarme-Tab |
| `docs/specs/modules/versand_tab_vergleich.md` | Spec | AC-4 wird durch dieses Issue revidiert |
| `docs/specs/modules/issue_1256_compare_ui_rewire.md` | Spec | KL-2 wird als entschieden markiert |
| `docs/specs/modules/issue_1231_korridor_editor.md` | Spec | Abgrenzung notify-Toggle-Verortung |
| `docs/specs/modules/issue_1170_compare_alert_config.md` | Spec | Ursprung `CompareAlarmSection`, wird durch geteilten Organism abgelöst |

## Implementation Details

### 1. Datenmodell (S1)

Neues Pointer-Feld auf Trip **und** ComparePreset, additiv zu den
bestehenden Bestandsfeldern (die als JSON weiter existieren, aber von
UI/Pipeline nicht mehr geschrieben/gelesen werden):

```go
// Go — analog Pointer-Pattern OfficialAlertsEnabled (#1040/#1087)
type OfficialWarningsConfig struct {
    Enabled bool     `json:"enabled"`
    Sources []string `json:"sources,omitempty"`
}
// Trip: OfficialWarnings *OfficialWarningsConfig `json:"official_warnings,omitempty"`
// ComparePreset: OfficialWarnings *OfficialWarningsConfig `json:"official_warnings,omitempty"`
```

```python
# Python — models.py / trip.py, Optional-Parität
official_warnings: Optional[dict] = None  # {"enabled": bool, "sources": list[str] | None}
```

- `nil`/fehlend = noch nicht migriert (Migration füllt es, s.u.)
- `sources` unset/leer = alle Quellen berücksichtigt; gesetzt = Filter auf
  exakte Quellen-Namen der Registry (`src/services/official_alerts/__init__.py`,
  aktuell 5: Vigilance/MeteoForets/MassifClosure/GeoSphereWarn/MeteoAlarm —
  **exaktes String-Vokabular bei S1-Implementierung anhand `OfficialAlertSource.name`
  verifizieren**, kein stabiles ID-Feld heute vorhanden)
- Altes Feld `official_alert_triggers_enabled` bleibt in den Daten
  (Rollback-Sicherheit), wird ab S1 von UI und Pipeline nicht mehr
  geschrieben/gelesen (dokumentierte Deprecation, kein Löschen)

### 2. Migration (S1)

Idempotente Batch-Migration nach Vorbild `migrate_1257.go`
(`internal/store/migrate_1258.go`): pro Trip/ComparePreset unter
`data/users/*/` — LoadTrip/LoadComparePreset (Self-Heal) + Save (RMW) —,
`official_warnings.enabled := (official_alert_triggers_enabled != false)`
(effektiv: nil/true → true, false → false). Zweiter Lauf ändert an bereits
migrierten Objekten nichts. Neuanlagen (kein Bestandsfeld vorhanden)
erhalten stattdessen `enabled: false` beim ersten Save (Default im
Konstruktor/Loader, nicht in der Migration).

### 3. Pipeline-Umstellung (S1)

- `src/services/trip_alert.py:328` (`check_official_alert_triggers`) liest
  `official_warnings.enabled` statt `official_alert_triggers_enabled`
- `src/services/compare_official_alert.py` liest analog
  `official_warnings.enabled`; `sources`-Filter wird vor der
  Alarmentscheidung auf die abgefragten Quellen angewendet

### 4. Geteilter Organism `AlarmeTab.svelte` (S2, gewired in S3/S4)

Inhalt in fester Reihenfolge, `context="route"|"vergleich"`:
(a) Korridor-Auslöser Read-only-Zusammenfassung „N × Warnen aktiv" +
Jump-Link zu „Wertebereiche" (notify-Toggles bleiben im CorridorEditor,
#1231-Sync-Brücke unangetastet) · (b) Amtliche Warnungen an/ab
(`official_warnings.enabled`) · (c) `AlertMetricLevelTable` (Schwellen) ·
(d) `AlertChannelPicker` (neu, Design `corridor-editor.jsx:469-489`) ·
(e) Cooldown-Karte · (f) Stille-Stunden-Karte · (g) Radar-Schalter (NUR
`context="vergleich"`) · (h) Beispiel-Warnung (`VTAlertSample`/`AlertPreviewCard`).
Auto-Save: EIN `$effect` + eine konsolidierte Payload-Funktion für alle
Felder (F002-Lektion aus `VersandTab.svelte:255-260` übernehmen, nicht neu
erfinden).

### 5. AlertChannelPicker-Persistenz-Mapping (S2/S3/S4)

- **Compare:** bindet an bestehende `send_telegram`/`send_sms`
  (E-Mail-Pfad bleibt implizit über `_effective_channels`,
  `compare_official_alert.py:161-169` unverändert)
- **Trip:** erhält additives Kanal-Set (kein Bestandsfeld heute — Feldname
  wird bei S3-Implementierung final festgelegt, analog Compare-Pattern)
- **Bestand:** angezeigter State wird aus dem heutigen Ist-Verhalten
  rekonstruiert (kein stiller Kanal-Wechsel)
- **Neuanlagen:** Design-Default (Telegram/SMS an, E-Mail aus) greift nur
  hier

### 6. R5 — Kanal-Verbindungsstatus (S6)

`internal/handler/auth.go` `profileResponse` bekommt ein aus
`email_verified_at` **abgeleitetes** Boolean-Feld (kein Zeitstempel-Leak).
`VTBriefingChannels.svelte` zeigt je Kanal Dot + Label nach
`screen-compare-detail.jsx:289-309`: E-Mail „bestätigt"/Telegram
„verbunden"/SMS „hinterlegt", sonst „nicht verbunden". Wirkt geteilt in
Trip- und Compare-Fläche.

### 7. Flächen (S3/S4/S5)

Trip-Editor (`TripTabs.svelte` Desktop+Mobile, neuer Tab „Alarme"
zwischen „Wertebereiche" und „Versand"), Compare-Editor (create **und**
edit, Tab-Reihenfolge Orte/Metriken → Wertebereiche → Alarme → Versand,
edit-only-Gating in `CompareEditor.svelte:116` entfällt), Compare-Hub
(`CompareTabs.svelte`, 7. Tab + `handleAlarmeCommit` analog
`handleVersandCommit` + Hydration der Alarm-Felder, die heute dort noch
nicht geladen werden).

### 8. Spec-Revisionen (Programm-Abschluss)

`versand_tab_vergleich.md` AC-4 wird per Changelog-Eintrag revidiert (nicht
stillschweigend überschrieben), `issue_1256_compare_ui_rewire.md` KL-2 wird
als entschieden markiert, `feat_1256_s8c_hub_fidelity.md`/
`feat_1256_s8d_mobile_editor_fidelity.md` markieren ihre R5-Verweise als
eingelöst.

### 9. S3-Detail-Festlegungen (Trip-Integration, 2026-07-15)

Löst die Known Limitation „Trip-Kanal-Feld noch nicht benannt" ein.
Analyse-Basis: `docs/context/feat-1258-s3-trip-alarme-tab.md` (D1–D5).

- **Tab-Reihenfolge (D1):** Die Trip-Tab-Leiste wird an das
  Compare-Zielbild angeglichen: overview, stages, weather, alerts
  („Wertebereiche"), **alarme („Alarme", NEU)**, briefings („Versand"),
  preview. `value`-Schlüssel bleiben unverändert (URL-Parameter,
  Testids); nur die Array-Reihenfolge in `TripTabs.svelte` ändert sich
  und der neue Eintrag kommt hinzu. Flush-Guard-Liste
  (`TripTabs.svelte:143`) wird um `alarme` erweitert.
- **Trip-Kanal-Feld (D2):** `alert_channels` als Objekt-Pointer
  (Go `AlertChannels *AlertChannelsConfig` mit `Email/Telegram/Sms bool`
  + omitempty; Python `Optional`-Parität; TS
  `alert_channels?: { email: boolean; telegram: boolean; sms: boolean }`).
  All-or-nothing-Semantik: `nil` = Legacy-Verhalten (Alert-Kanäle erben
  die Briefing-Kanäle aus `report_config`, `{"email"}` bei fehlendem
  `report_config`). Gesetzt = ersetzt in `_effective_alert_channels`
  (`trip_alert.py:988-1022`) NUR den geerbten Briefing-Anteil (beide
  Verwendungsstellen: Legacy-Pfad ohne aktive Regeln und
  per-Regel-Fallback); nicht-leere `rule.channels`-Overrides (#638)
  gewinnen unverändert weiter, das SMS-Tier-Gate bleibt aktiv.
  Handler-Merge nach dem Pointer-Muster `AlertCooldownMinutes`
  (`internal/handler/trip.go:250-252`), Read-Modify-Write.
- **Container (D4):** Neuer dünner Container
  `trip-detail/AlarmeScheduleTab.svelte` (Vorbild
  `BriefingScheduleTab.svelte`): bettet `AlarmeTab context="route"` ein,
  berechnet `activeMetrics`/`metricLevels` aus
  `display_config.metric_alert_levels`, `notifyCount` aus
  `trip.corridors` (notify-Zähler), rekonstruiert `existingChannels`
  für AC-15 (`alert_channels` falls gesetzt, sonst Briefing-Kanäle aus
  `report_config.send_*`) und persistiert Kanal-Toggles per PUT
  `alert_channels` über den `saveController`.
- **Atomarer Umzug (D5):** Tab-Einfügung und Rückbau der
  Alert-Zustellungs-Sektion im `VersandTab`-route-Zweig (State/Effect
  und Markup) erfolgen in EINEM Schritt — kein Zwischenzustand, in dem
  zwei `$effect`-Schreibpfade dieselben Trip-Felder schreiben
  (F002-Race-Lektion). Der vergleich-Zweig des VersandTab bleibt bis S4
  unangetastet. Nebenwirkung des Umzugs: Der bisherige Versand-Toggle
  „Amtliche Warnungen lösen Alert aus" schrieb seit S1 nur noch das
  tote Legacy-Feld `official_alert_triggers_enabled` — im Alarme-Tab
  bindet der Toggle auf `official_warnings.enabled` (Bestandsdefekt
  behoben).
- **F003-Nachzug (S2-Adversary, #1199):** Laufzeit-Guard in
  `alarme-tab/alarmeDeliveryPayload.ts` wird symmetrisch auf
  `officialAlertsEnabled` gespiegelt.
- **E2E-Umverdrahtung:** `frontend/e2e/versand-tab.spec.ts` und
  `frontend/e2e/issue-1117-official-alerts-content-tab.spec.ts`
  erwarten die Alert-Sektion heute im briefings-Panel — Selektoren und
  Klickpfade ziehen auf Tab/Panel `alarme` um. Compare-Specs
  (`compare-alarm-config.spec.ts`, `versand-tab-vergleich.spec.ts`)
  bleiben unangetastet.
- **Radar/Onset-Divergenz:** bleibt bestehen (s. Known Limitations) —
  Out of Scope „Änderung der Radar-Alarm-Fachlogik" gilt.

## Expected Behavior

- **Input:** Bestehende Trips/ComparePresets mit `official_alert_triggers_enabled`,
  `send_telegram`/`send_sms`, Profil-Kontaktdaten; neue Nutzeraktionen im
  Alarme-Tab (Toggle amtliche Warnungen, Kanal-Wahl, Cooldown, Stille
  Stunden)
- **Output:** Persistierte `official_warnings`-Struktur auf Trip/ComparePreset;
  unveränderte Alarm-Auslösung für Bestand, neuer Default `false` für
  Neuanlagen; ehrlicher Kanal-Status im Versand-/Alarme-Bereich
- **Side effects:** Schema-Dateien (`trip.go`, `compare_preset.go`,
  `models.py`, `trip.py`) triggern `data_schema_backup.py`; Migration
  erzeugt Pre-Snapshot analog `migrate_1257.go`

## Acceptance Criteria

**AC-1 (S1):** Given ein Bestandstrip mit `official_alert_triggers_enabled` ungesetzt oder `true` / When die Migration läuft / Then trägt der Trip danach `official_warnings.enabled = true`, ohne dass sich das gesendete Alarmverhalten ändert.
  - Test: Migration auf Fixture-Trip anwenden, `check_official_alert_triggers`-Ergebnis vor/nach Migration vergleichen — identisch.

**AC-2 (S1):** Given ein Bestandstrip mit `official_alert_triggers_enabled = false` / When die Migration läuft / Then trägt der Trip `official_warnings.enabled = false`, identisch zum vorherigen Ist-Verhalten (kein Alarm).
  - Test: Fixture-Trip mit `false`, Migration + Alarm-Check zeigt weiterhin keinen Sofort-Alarm.

**AC-3 (S1):** Given ein Bestands-ComparePreset / When die Migration läuft / Then gilt dieselbe Ist-Verhalten-Übernahme wie bei Trips, und ein zweiter Lauf derselben Migration ändert an bereits migrierten Presets nichts mehr (idempotent).
  - Test: Migration zweimal laufen lassen, `official_warnings`-Wert nach Lauf 1 == nach Lauf 2.

**AC-4 (S1):** Given ein neu angelegter Trip oder Vergleich ohne vorherige Konfiguration / When er zum ersten Mal gespeichert wird / Then ist `official_warnings.enabled = false` (bewusster Verhaltenswechsel nur für Neuanlagen).
  - Test: Neuen Trip via API anlegen, `official_warnings.enabled` prüfen.

**AC-5 (S1):** Given zwei verschiedene Nutzer mit je eigenem Trip / When Nutzer A `official_warnings` seines Trips ändert / Then bleibt der Trip von Nutzer B unverändert (Isolation über user_id, kein Cross-User-Leck).
  - Test: PUT für User A, anschließend GET für User B — unverändert.

**AC-6 (S1):** Given ein Trip mit `official_warnings.enabled = false` / When der Scheduler amtliche Warn-Alarme prüft / Then wird für diesen Trip kein Sofort-Alarm ausgelöst — unabhängig vom alten, weiterhin gespeicherten `official_alert_triggers_enabled`-Wert.
  - Test: Trip mit `official_warnings.enabled=false` aber `official_alert_triggers_enabled=true` (Konflikt-Fixture), `check_official_alert_triggers` liefert leere Liste.

**AC-7 (S1):** Given ein ComparePreset mit `official_warnings.enabled = true` und `official_warnings.sources = ["vigilance"]` / When die amtliche Warnprüfung läuft / Then fließen nur Warnungen der Quelle „vigilance" in die Alarmentscheidung ein, andere Quellen werden ignoriert.
  - Test: Fixture mit Warnungen aus zwei Quellen, Filter auf eine Quelle, Ergebnis enthält nur diese.

**AC-8 (S1):** Given `official_warnings.sources` ist nicht gesetzt oder leer / When die amtliche Warnprüfung läuft / Then werden weiterhin alle registrierten Quellen berücksichtigt (unverändertes Verhalten).
  - Test: Fixture ohne `sources`, alle Quellen fließen wie vor der Migration ein.

**AC-9 (S2):** Given der neue geteilte Baustein `AlarmeTab.svelte` / When er mit `context="route"` bzw. `context="vergleich"` gerendert wird / Then zeigt er in beiden Kontexten dieselbe Abschnittsreihenfolge, und der Radar-Abschnitt erscheint ausschließlich bei `context="vergleich"`.
  - Test: Component-Test/Playwright rendert beide Kontexte, prüft Testid-Reihenfolge und An-/Abwesenheit des Radar-Testids.

**AC-10 (S2):** Given der Korridor-Zusammenfassungs-Abschnitt im Alarme-Tab / When mindestens ein Korridor mit `notify=true` existiert / Then zeigt der Abschnitt „N × Warnen aktiv" und einen Sprung-Link zum Tab „Wertebereiche" — die notify-Toggles selbst bleiben ausschließlich im CorridorEditor editierbar.
  - Test: Playwright klickt Sprung-Link, landet auf `Wertebereiche`-Tab; Alarme-Tab enthält keine `ce-effect notify`-Buttons.

**AC-11 (S2):** Given `AlertChannelPicker.svelte` als neuer geteilter Baustein / When er ohne übergebenen Bestands-State gerendert wird (Neuanlage) / Then zeigt er den Design-Default Telegram an, SMS an, E-Mail aus, in der Reihenfolge Telegram → SMS → E-Mail, und bei null aktiven Kanälen erscheint der Warnhinweis „kein Kanal — Alerts gehen nirgends hin".
  - Test: Component-Test mit leerem State prüft Default-Toggle-Zustände + Warnhinweis-Text bei allen drei ausgeschaltet.

**AC-12 (S2):** Given der Alarme-Tab ändert mehrere Felder kurz hintereinander (z. B. Cooldown und amtliche Warnungen) / When die Auto-Save-Logik greift / Then läuft genau ein `$effect` mit einer konsolidierten Payload-Funktion, nicht mehrere unabhängige Speichervorgänge.
  - Test: Zwei Felder in schneller Folge ändern, PUT-Aufrufe zählen — genau ein konsolidierter Request pro Debounce-Fenster.

**AC-13 (S3):** Given der Trip-Editor (Desktop und Mobile) / When ich die Tab-Leiste öffne / Then existiert ein Tab „Alarme" zwischen „Wertebereiche" und „Versand", der den geteilten `AlarmeTab` mit `context="route"` rendert.
  - Test: Playwright Desktop + Mobile-Viewport, Tab-Klick auf „Alarme", `data-testid` des Organism sichtbar.

**AC-14 (S3):** Given der Trip-Versand-Tab nach der Umstellung / When ich ihn öffne / Then enthält er nur noch Kanäle des geplanten Briefings und den Zeitplan — Cooldown, Stille Stunden, amtliche-Warnungen-Toggle und Beispiel-Warnung erscheinen dort nicht mehr.
  - Test: Playwright — `alert-cooldown-card` und `alerts-tab-official-alerts-toggle` NICHT im Versand-Tab, aber im Alarme-Tab vorhanden.

**AC-15 (S3):** Given ein Bestandstrip mit heute aktiven Alert-Kanälen / When der Alarme-Tab zum ersten Mal geöffnet wird / Then zeigt der AlertChannelPicker den aus dem Ist-Zustand rekonstruierten Kanal-Status, nicht den Neuanlage-Default.
  - Test: Fixture-Trip mit Bestandskonfiguration öffnen, Picker-State gegen erwarteten rekonstruierten Wert prüfen (kein stiller Kanal-Wechsel).

**AC-16 (S4):** Given der Compare-Editor im Anlege-Modus (create) / When ich die Tab-Leiste öffne / Then ist der Tab „Alarme" zwischen „Wertebereiche" und „Versand" sichtbar und nutzbar, nicht mehr nur im Edit-Modus.
  - Test: Playwright startet Create-Wizard, navigiert bis Alarme-Tab vor Versand, Tab ist nicht gesperrt.

**AC-17 (S4):** Given der Compare-Editor (Edit-Modus) / When ich den Alarme-Tab öffne / Then rendert er den geteilten `AlarmeTab` mit `context="vergleich"` inklusive Radar-Schalter, und `CompareAlarmSection.svelte` wird nicht mehr eingebunden.
  - Test: Grep/Import-Check `CompareAlarmSection` nicht mehr in `CompareEditor.svelte`; Playwright prüft Radar-Testid sichtbar.

**AC-18 (S4):** Given der Compare-Versand-Tab nach der Umstellung / When ich ihn öffne / Then enthält er nur noch geplantes Briefing (Kanäle, Zeitplan, Laufzeit) — Radar-Toggle, amtliche-Warnungen-Toggle und Metrik-Level-Tabelle erscheinen dort nicht mehr.
  - Test: Playwright — `alert-metric-level-table` NICHT im Versand-Tab, sondern im Alarme-Tab; ersetzt `versand_tab_vergleich.md` AC-4.

**AC-19 (S5):** Given der Compare-Hub (`CompareTabs.svelte`) / When ich einen bestehenden Vergleich öffne / Then existiert ein 7. Tab „Alarme", der beim Öffnen die Alarm-Felder aus dem Preset hydriert und Änderungen über einen `handleAlarmeCommit`-Handler analog `handleVersandCommit` persistiert.
  - Test: Playwright öffnet Hub eines Presets mit gesetzten Alarm-Werten, prüft dass Alarme-Tab diese Werte vorbelegt zeigt (nicht Defaults) und eine Änderung nach Reload erhalten bleibt.

**AC-20 (S6):** Given `/api/auth/profile` nach der Erweiterung / When ein eingeloggter Nutzer sein Profil abruft / Then enthält die Antwort ein aus `email_verified_at` abgeleitetes Feld, ohne den Zeitstempel selbst preiszugeben.
  - Test: API-Test mit verifiziertem und unverifiziertem Fixture-User, JSON-Response geprüft — Zeitstempel nicht im Body.

**AC-21 (S6):** Given `VTBriefingChannels` (geteilt, wirkt in Trip und Compare) / When ein Kanal aktiv und für E-Mail zusätzlich bestätigt ist / Then zeigt die Zeile einen grünen Punkt und den Text „bestätigt" (E-Mail) bzw. „verbunden" (Telegram) bzw. „hinterlegt" (SMS); ist ein Kanal nicht konfiguriert, zeigt sie „nicht verbunden" mit neutralem Punkt.
  - Test: Playwright mit drei Profil-Fixtures (voll konfiguriert, teilweise, keiner) prüft Label + Dot-Farbe je Kanal.

**AC-22 (S6):** Given ein Nutzer öffnet den Trip-Versand-Tab (nicht nur Compare) / When die Kanal-Sektion rendert / Then zeigt sie denselben Verbindungsstatus wie im Compare-Hub — der geteilte Organismus wirkt in beiden Flächen identisch.
  - Test: Playwright vergleicht gerenderte Kanal-Zeile in Trip-Versand-Tab und Compare-Hub für denselben Profil-Fixture-User.

**AC-23 (Programm-Abschluss, keiner Einzelscheibe zugeordnet):** Given alle Scheiben S1–S6 sind live / When die begleitenden Spec-Dokumente geprüft werden / Then ist `versand_tab_vergleich.md` AC-4 per Changelog-Eintrag revidiert, `issue_1256_compare_ui_rewire.md` KL-2 als entschieden markiert, und die R5-Verweise in `feat_1256_s8c_hub_fidelity.md`/`feat_1256_s8d_mobile_editor_fidelity.md` sind als eingelöst gekennzeichnet.
  - Test: Doc-Compliance-Check (`# doc-compliance-test`) — Changelog-Einträge und Markierungen vorhanden.

**AC-24 (S3):** Given ein Bestandstrip ohne `alert_channels` (Feld nicht gesetzt) / When ein Abweichungs-Alert oder ein amtlicher Sofort-Alert versendet wird / Then ergeben sich die effektiven Kanäle exakt wie heute (geerbte Briefing-Kanäle aus `report_config`, per-Regel-Overrides, `{"email"}`-Default ohne `report_config`) — kein Verhaltenswechsel für Bestand.
  - Test: `_effective_alert_channels` mit Fixture-Trips (mit/ohne `report_config`, mit/ohne `rule.channels`) vor und nach der Änderung — identische Ergebnisse bei `alert_channels=None`.

**AC-25 (S3):** Given ein Trip mit gesetztem `alert_channels` (z. B. nur Telegram aktiv) / When ein Alert versendet wird / Then ersetzt das Kanal-Set den geerbten Briefing-Anteil (Regeln ohne eigene `channels` senden an genau diese Kanäle), während nicht-leere `rule.channels`-Overrides weiterhin gewinnen und das SMS-Tier-Gate weiterhin greift.
  - Test: Fixture-Trip mit `alert_channels={telegram:true, email:false, sms:false}` — effektive Kanäle `{telegram}`; zusätzliche Regel mit eigenem `channels=["email"]` → Union `{telegram, email}`; SMS aktiviert aber Tier verbietet → SMS nicht im Set.

**AC-26 (S3):** Given ich ändere im Trip-Alarme-Tab die Alert-Kanäle / When die Änderung gespeichert und der Trip neu geladen wird / Then zeigt der AlertChannelPicker die persistierten Werte (Roundtrip über `alert_channels`), und alle übrigen Trip-Felder bleiben durch den Read-Modify-Write-Merge unangetastet.
  - Test: Go-Handler-Test PUT mit nur `alert_channels` → Feld persistiert, Etappen/report_config/Corridors unverändert; Staging-E2E Toggle → Reload → Zustand erhalten.

## Scheiben-Zuordnung

| Scheibe | Inhalt | ACs (Nummern) |
|---|---|---|
| **S1** | Datenmodell + Migration (Go+Python), Pipeline-Umstellung Trip+Compare | 1 … 8 |
| **S2** | Geteilter Alarme-Organism als Baustein (AlarmeTab.svelte + AlertChannelPicker.svelte, ungewired) | 9 … 12 |
| **S3** | Trip-Integration (Versand-Tab-Rückbau, Tab-Ergänzung Desktop+Mobile, Kanal-Feld `alert_channels`) | 13 … 15, 24 … 26 |
| **S4** | Compare-Editor-Integration (CompareAlarmSection ablösen, Create-Sichtbarkeit) | 16 … 18 |
| **S5** | Compare-Hub-Integration (7. Tab, Commit-Handler, Hydration) | 19 |
| **S6** | R5 Status-Dot (+ email_verified exponieren) | 20 … 22 |
| **Programm-Abschluss** | Spec-Revisionen als Dokupflicht des Gesamtissues | 23 |

S2 und S6 sind unabhängig von S1/S3/S4/S5 startbar (S6 komplett
unabhängig, S2 baut den Baustein ohne funktionale Kopplung an S1). S3/S4
setzen S1 (Datenmodell) und S2 (Baustein) voraus. S5 setzt S4 voraus.

## Known Limitations

- Kein Quellen-Picker im UI in diesem Issue — `sources[]` ist reine
  Datenmodell- und Pipeline-Vorbereitung, der Alarme-Tab zeigt nur
  amtliche Warnungen an/ab (kein Quellen-Feinauswahl-Control)
- `official_alert_triggers_enabled` bleibt in den JSON-Daten dauerhaft
  erhalten (Rollback-Sicherheit), wird aber ab S1 von UI und Pipeline
  nicht mehr geschrieben/gelesen — künftige Aufräum-Migration wäre ein
  eigenes Issue
- SMS hat kein Verifikationskonzept — Status bleibt dauerhaft auf
  „hinterlegt" begrenzt, keine Bestätigungs-Logik in diesem Issue
- Das genaue Trip-seitige Feld für „additives Kanal-Set" im
  AlertChannelPicker (Analogon zu `send_telegram`/`send_sms` bei Compare)
  ist zum Zeitpunkt dieser Spec noch nicht final benannt — wird bei
  S3-Implementierung festgelegt und dort im Detail dokumentiert
  *(eingelöst 2026-07-15: `alert_channels`, s. Implementation Details
  Abschnitt 9)*
- Der Radar/Onset-Alert-Pfad (`trip_alert.py:743-767`) baut sein
  Kanal-Set weiterhin eigenständig direkt aus `report_config` (E-Mail
  default, TG/SMS opt-in) und liest weder `rule.channels` noch das neue
  `alert_channels` — bewusste Divergenz, da „Änderung der
  Radar-Alarm-Fachlogik" Out of Scope ist; Angleichung wäre ein eigenes
  Issue
- Exaktes String-Vokabular der Quellen-IDs für `sources[]` ist nicht als
  stabiles ID-Feld im Code hinterlegt (nur `OfficialAlertSource.name`) —
  muss bei S1-Implementierung verifiziert und ggf. um ein stabiles
  `id`-Attribut in der Registry ergänzt werden

## Out of Scope

- BriefingSubscription-API-Konsolidierung (Epic #29 Phase 2-3) — das neue
  Feld liegt bewusst weiterhin auf Trip + ComparePreset, nicht auf einer
  neuen Entität
- Mobile-Editor-Shell-Rework (unabhängiges Programm, S8d)
- Quellen-Picker-UI für `official_warnings.sources`
- Neuer Verifikationsmechanismus für SMS (nur Label-Ehrlichkeit „hinterlegt",
  kein Opt-In-Flow)
- Änderung der Radar-Alarm-Fachlogik selbst (nur Verortung im neuen Tab,
  kein Verhaltenswechsel)
- S9 `/edit`-Redirect (Mobile-Pencil-Icon, KL-1 aus S8c) — unabhängig

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** keine
- **Rationale:** Wiederverwendung etablierter Muster (Pointer-Feld +
  omitempty, idempotente Batch-Migration nach `migrate_1257.go`, geteilter
  `context`-Organism nach `VersandTab`-Vorbild). Kein neues
  Architekturmuster wird eingeführt.

## Test Coverage

### Kern-Tests (deterministisch, echte Fixtures, KEINE Mocks)

- `test_official_warnings_migration_preserves_behavior` — Bestand behält
  Alarme (AC-1, AC-2)
- `test_official_warnings_migration_idempotent` — zweiter Lauf ändert
  nichts (AC-3)
- `test_official_warnings_new_entity_defaults_disabled` — Neuanlage
  `enabled=false` (AC-4)
- `test_official_warnings_two_user_isolation` — Cross-User-Leck-Test
  (AC-5)
- `test_trip_alert_reads_official_warnings_not_legacy_field` — Pipeline
  liest neues Feld (AC-6)
- `test_compare_official_alert_source_filter` — `sources[]`-Filterung
  (AC-7, AC-8)
- `test_alarme_tab_context_route_vs_vergleich_section_order` (AC-9)
- `test_alert_channel_picker_defaults_and_empty_warning` (AC-11)
- `test_alarme_tab_single_effect_consolidated_save` (AC-12)
- `test_profile_exposes_email_confirmed_without_timestamp` (AC-20)
- `test_trip_alert_channels_legacy_unchanged` — `alert_channels=None`
  liefert exakt heutige effektive Kanäle (AC-24)
- `test_trip_alert_channels_replaces_briefing_inheritance` — gesetztes
  Feld ersetzt Briefing-Erbe, `rule.channels`-Präzedenz + SMS-Tier-Gate
  bleiben (AC-25)
- Go: `TestUpdateTripAlertChannelsRMW` — PUT nur mit `alert_channels`
  lässt übrige Felder unangetastet (AC-26)

### Staging-E2E (Marker `live`/`staging`, Playwright gegen echten Login)

- Trip-Editor Desktop+Mobile: Alarme-Tab vorhanden, Versand-Tab bereinigt
  (AC-13, AC-14, AC-15)
- Compare-Editor create+edit: Alarme-Tab-Sichtbarkeit + Radar-Weiche
  (AC-16, AC-17, AC-18)
- Compare-Hub: Hydration + Commit-Roundtrip nach Reload (AC-19)
- Kanal-Verbindungsstatus in Trip UND Compare mit echten Profil-Fixtures
  (AC-21, AC-22)

**Namensregel:** Testdateien nach Verhalten benennen (z. B.
`test_official_warnings_migration.py`, `test_alarme_tab_shared.spec.ts`),
NICHT nach Issue-Nummer (`test_naming_gate.py` blockt neue
issue-nummerierte Testdateien).

## Changelog

- 2026-07-15: **S3-Detail-Festlegungen ergänzt** (Workflow
  `feat-1258-s3-trip-alarme-tab`, Analyse-Doc
  `docs/context/feat-1258-s3-trip-alarme-tab.md`): neuer Implementation-
  Details-Abschnitt 9 (Tab-Reihenfolge-Konvergenz, Trip-Kanal-Feld
  `alert_channels` als Objekt-Pointer mit scharfer nil=Legacy-Semantik,
  Container `AlarmeScheduleTab.svelte`, atomarer Umzug, F003-Spiegelung,
  E2E-Umverdrahtung), neue ACs 24–26 (S3), Known Limitations um
  Radar/Onset-Divergenz ergänzt und Feldnamen-Limitation als eingelöst
  markiert, Kern-Tests ergänzt. Bestehende ACs 1–23 wortgleich
  unverändert.

- 2026-07-15: **S2 implementiert** (AC-9…AC-12, geteilter Alarme-Organism als
  Baustein, ungewired): neu `shared/AlarmeTab.svelte` (Abschnitte a–h über
  `alarmeTabSections(context)` strukturell erzwungen, Radar nur vergleich,
  route-Zweig mit EINEM `$effect` + JSON-Diff-Guard + `saveController`),
  `shared/AlertChannelPicker.svelte` (Design corridor-editor.jsx:469-489),
  Logik-Module `shared/alarme-tab/` (Sections/ChannelState/Payload/
  CompareMetricMapping). Additiv: `types.ts` Trip.official_warnings-Typ
  (S1-Nachzug), `compareWizardState.svelte.ts` officialWarningsEnabled
  (Persistenz-Verdrahtung folgt S4). Adversary-Verdict **VERIFIED** nach
  Fix-Loop 1 (3 Runden, `docs/artifacts/feat-1258-s2-alarme-organism/`):
  F001 (MEDIUM) `resolveAlertChannels({})` ergab „alles aus" statt
  Neuanlage-Default → `hasAnyExplicitChannelValue()`-Weiche; F002 (MEDIUM)
  Payload-Builder defaultete still auf `enabled:false` → Pflichtfelder +
  Laufzeit-Guard (Error bei nicht-boolean). F003 (LOW, #1199): Guard-
  Asymmetrie `officialAlertsEnabled` — Spiegelung beim S3-Wiring.
  Kern-Tests 25 grün (node:test, verhaltensbasiert gegen Logik-Module —
  Repo hat keine Component-Render-Infrastruktur); DOM-/Playwright-Nachweise
  AC-9/AC-10 folgen beim S3/S4-Wiring per Staging-E2E wie in Test Coverage
  vorgesehen. Vollsuite 1682 Tests / 0 fail.
- 2026-07-15: **Notations-Korrektur ohne inhaltliche Änderung:** Spalte „ACs"
  der Scheiben-Zuordnungstabelle von `AC-1 … AC-8` auf reine Nummern (`1 … 8`)
  umgestellt. Grund: `edit_gate.py` (Plugin 3.9.1) parst `AC-N`-Vorkommen im
  GESAMTEN Dokument als AC-Einträge und blockierte die S2-Implementierung
  wegen „AC entry too short" auf den Tabellenzellen (False Positive). Die
  Acceptance Criteria selbst sind wortgleich unverändert. Gate-Bug separat
  als Issue gemeldet.
- 2026-07-15: Initial spec erstellt — Issue #1258, Programm-Spec für
  Scheiben S1–S6, PO-Entscheidungen F1 (officialWarnings scharf, Bestand
  bleibt an), F2 (ehrliche Kanal-Labels), F3 (Alarme-Tab auch im
  Create-Wizard) eingearbeitet.
- 2026-07-15: **S1 implementiert** (AC-1…AC-8, Datenmodell + Migration +
  Pipeline-Umstellung Go+Python). Adversary-Verdict **VERIFIED** nach
  Fix-Loop 1 (`docs/artifacts/feat-1258-compare-alarme-tab/adversary-dialog.md`).
  Runde 1 fand drei Findings, alle in Fix-Loop 1 behoben und in Runde 2
  live nachgestellt/regressionsgetestet:
  - **F001 (CRITICAL):** `scripts/setup_staging_validator_trip.py` setzte
    bei jedem wiederkehrenden Lauf `official_warnings` des namensstabilen
    Rolling-Trips über den Bare-Konstruktor-Default (`{"enabled": False}`)
    + „overlay wins"-Merge hart zurück und markierte den Trip fälschlich
    als migriert. Fix: Skript übergibt explizit `official_warnings=None`
    + Regressionstest `tests/tdd/test_official_warnings_rolling_setup_preserves.py`.
  - **F002 (MEDIUM):** PUT-RMW griff nur auf Objekt-Ebene — ein Body mit
    nur `{"enabled": false}` (ohne `sources`) löschte eine bestehende
    `sources[]`-Liste. Fix: Feld-Level-Preserve für `Sources` in
    `internal/handler/trip.go` und `internal/handler/compare_preset.go`
    (fehlender `sources`-Key im Body → Bestand bleibt erhalten; explizites
    `"sources": []` löscht weiterhin bewusst) + 4 neue Go-Tests.
  - **F003 (LOW/MEDIUM):** Ein `{}`-Wert für `official_warnings` (Key
    vorhanden, `enabled` fehlt) wurde in Go fail-closed (als migriert,
    `enabled=false`) und in Python fail-open (`.get("enabled", True)`)
    unterschiedlich interpretiert. Fix: `officialWarningsRawHasEnabledKey()`
    (Go) bzw. `"enabled" in ow`-Check (Python-Migration) + `{}`≡`None`-
    Fallback in `trip_alert.py` und `compare_official_alert.py`, beide
    Sprachen jetzt identisch (Legacy-Fallback statt `enabled=false`).
  Test-Nachweis: 22 Python- + 16 Go-Tests grün, `go build`/`go vet`
  sauber. Details/Feld-Semantik dokumentiert in
  `docs/reference/api_contract.md` Section 10.5 „official_warnings
  (Issue #1258)" (Trip) und Section 16 Notes (ComparePreset, Verweis auf
  10.5).
