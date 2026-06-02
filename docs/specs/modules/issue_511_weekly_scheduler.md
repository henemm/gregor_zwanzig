---
entity_id: issue_511_weekly_scheduler
type: module
created: 2026-06-02
updated: 2026-06-02
status: draft
version: "1.0"
issue: 511
tags: [compare, preset, scheduler, weekly, go, python, frontend, svelte, weekday]
---

# Issue #511 — Weekly-Presets: Go-Scheduler hat keinen weekly-Job

## Approval

- [ ] Approved

## Purpose

Erweitert den bestehenden `compare_presets_daily`-Job um die Verarbeitung von `schedule='weekly'`-Presets: Beim täglichen 06:00-Lauf prüft die Python-Dispatch-Funktion zusätzlich, ob `today.weekday() == preset.weekday`, und versendet fällige weekly-Presets. Damit werden alle vier betroffenen Schichten — Go-Modell, Go-Store, Python-Scheduler, TypeScript-Frontend — konsistent um ein `weekday`-Feld (0=Montag … 6=Sonntag, Default 4=Freitag) ergänzt, so dass User weekly-Presets konfigurieren und automatisch empfangen können.

## Source

**Geänderte Dateien (Go-Backend):**
- `internal/model/compare_preset.go` — `Weekday int` ergänzen
- `internal/store/store.go` — Migration: Default weekday=4 beim Laden alter Presets (~Zeile 466)
- `internal/handler/compare_preset.go` — Validation: weekday 0–6 wenn schedule='weekly'

**Geänderte Dateien (Python-Backend):**
- `api/routers/scheduler.py` — `_run_compare_presets_daily()` um weekly-Branch erweitern

**Geänderte Dateien (Frontend):**
- `frontend/src/lib/types.ts` — `weekday?: number` in `ComparePreset`-Interface
- `frontend/src/lib/components/compare/SavePresetDialog.svelte` — Weekday-Picker bei schedule='weekly'

**Geänderte Dateien (Tests):**
- `tests/tdd/test_issue_461_compare_preset_dispatch.py` — `_make_preset` um `weekday`-Param ergänzen; `test_only_daily_presets_are_processed` umbenennen/anpassen; 2 neue Tests für weekly-Logik

> **Schicht-Hinweis:** Vier-Schichten-Änderung. Das `weekday`-Feld zieht sich von Go-Modell (`internal/model/`) über Go-Store (`internal/store/`) und Python-Scheduler (`api/routers/`) bis ins SvelteKit-Frontend (`frontend/src/lib/`). Der Go-Scheduler-Cron bleibt unverändert (`"0 6 * * *"`). Der Python-Endpoint `/api/scheduler/compare-presets-daily` verarbeitet jetzt beide Schedule-Typen.

## Estimated Scope

- **LoC:** ~75
- **Files:** 7
- **Effort:** medium

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `internal/model/compare_preset.go` — `ComparePreset`-Struct | intern (Go) | Aufnahme des neuen `Weekday int json:"weekday"` Feldes; Default 0 in JSON-Unmarshal |
| `internal/store/store.go` — `LoadComparePresets()` (~Zeile 466) | intern (Go) | Migration: Bestandsdaten ohne `weekday`-Feld erhalten Default 4 (Freitag) — analog zu `LoadSubscriptions()` Zeile 259 |
| `internal/handler/compare_preset.go` — `validateComparePreset()` | intern (Go) | Neue Validation: `if preset.Schedule == "weekly" && (preset.Weekday < 0 || preset.Weekday > 6)` — analog zu `subscription.go:81` |
| `internal/model/subscription.go:14` | intern (Go) | Referenz-Muster: `Weekday int json:"weekday"` |
| `internal/store/store.go:259` | intern (Go) | Referenz-Muster: Default weekday=4 Migration |
| `internal/handler/subscription.go:81` | intern (Go) | Referenz-Muster: Weekday-Validation 0–6 |
| `api/routers/scheduler.py` — `_run_compare_presets_daily()` | intern (Python) | Erweiterung: zusätzlicher weekly-Branch mit `today.weekday() == preset.get("weekday", 4)` |
| `frontend/src/lib/types.ts:260` — `Subscription`-Type | intern (Frontend) | Referenz-Muster: `weekday: number` — `ComparePreset` erhält analoges optionales Feld `weekday?: number` |
| `frontend/src/lib/components/SubscriptionForm.svelte:136` | intern (Frontend) | Referenz-Muster: konditionaler Weekday-Picker bei schedule='weekly' |
| `tests/tdd/test_issue_461_compare_preset_dispatch.py` | Test (Python) | Bestehende Tests erweitern: `_make_preset` + weekday-Param; `test_only_daily_presets_are_processed` umbenennen zu `test_only_scheduled_presets_are_processed`; 2 neue Tests |
| `data/users/{user_id}/compare_presets.json` | Datei (JSON-Array) | Direktes `[...]`-Array; Bestandsdaten ohne `weekday` sind gültig → Store-Migration setzt Default 4 beim Laden |

## Implementation Details

### §1 `internal/model/compare_preset.go` — Weekday-Feld ergänzen

Neues Feld additiv einfügen (analog zu `internal/model/subscription.go:14`):

```go
Weekday int `json:"weekday"` // 0=Montag … 6=Sonntag; nur relevant wenn Schedule="weekly"; Default 4=Freitag
```

JSON-Unmarshal liefert 0 für fehlendes Feld. Die Store-Migration korrigiert das auf 4.

### §2 `internal/store/store.go` — Migration beim Laden

In `LoadComparePresets()`, nach dem JSON-Unmarshal, iterieren (analog zu `LoadSubscriptions()` Zeile 259):

```go
for i := range presets {
    if presets[i].Weekday == 0 && presets[i].Schedule == "weekly" {
        presets[i].Weekday = 4 // Default Freitag
    }
}
```

Bestandsdaten mit `schedule='daily'` oder `schedule='manual'` erhalten keinen Weekday-Default — das Feld ist nur für 'weekly' relevant.

### §3 `internal/handler/compare_preset.go` — Validation

In `validateComparePreset()` ergänzen:

```go
if preset.Schedule == "weekly" && (preset.Weekday < 0 || preset.Weekday > 6) {
    return fmt.Errorf("weekday must be between 0 and 6 for weekly presets")
}
```

Für `schedule='daily'` und `schedule='manual'` ist der Weekday-Wert irrelevant und wird nicht validiert.

### §4 `api/routers/scheduler.py` — Weekly-Branch in `_run_compare_presets_daily()`

Die Funktion verarbeitet jetzt zwei Schedule-Typen. Für daily-Presets bleibt die Logik unverändert. Weekly-Presets werden zusätzlich geprüft:

```python
from datetime import date

today_weekday = date.today().weekday()  # 0=Montag … 6=Sonntag

for preset in presets:
    schedule = preset.get("schedule", "")
    if schedule == "daily":
        pass  # wie bisher
    elif schedule == "weekly":
        preset_weekday = preset.get("weekday", 4)
        if preset_weekday != today_weekday:
            continue  # nicht fällig heute
    else:
        continue  # manual und unbekannte Typen überspringen
    # ... restliche Versandlogik unverändert
```

Der Heartbeat-Ping auf Go-Ebene bleibt unverändert — `error_count` gilt für daily und weekly gemeinsam.

### §5 `frontend/src/lib/types.ts` — Interface-Erweiterung

In der `ComparePreset`-Interface-Definition:

```typescript
weekday?: number;  // 0=Montag … 6=Sonntag; nur relevant wenn schedule='weekly'
```

### §6 `frontend/src/lib/components/compare/SavePresetDialog.svelte` — Weekday-Picker

Analog zu `SubscriptionForm.svelte:136`: konditionaler Block, der nur sichtbar ist wenn `schedule === 'weekly'`:

```svelte
{#if form.schedule === 'weekly'}
  <label>
    Wochentag
    <select bind:value={form.weekday}>
      <option value={0}>Montag</option>
      <option value={1}>Dienstag</option>
      <option value={2}>Mittwoch</option>
      <option value={3}>Donnerstag</option>
      <option value={4}>Freitag</option>
      <option value={5}>Samstag</option>
      <option value={6}>Sonntag</option>
    </select>
  </label>
{/if}
```

Default-Wert im Formular: `weekday: 4` (Freitag), damit neu erstellte weekly-Presets sofort einen gültigen Wochentag haben.

### §7 `tests/tdd/test_issue_461_compare_preset_dispatch.py` — Testanpassungen

**`_make_preset` erweitern:**
```python
def _make_preset(
    ...
    weekday: int = 4,  # neu
) -> dict:
    return {
        ...
        "weekday": weekday,  # neu
    }
```

**`test_only_daily_presets_are_processed` umbenennen** zu `test_manual_presets_are_skipped` und Assertion anpassen: manual wird immer übersprungen; weekly wird je nach Wochentag entweder verarbeitet oder übersprungen.

**2 neue Tests:**

- `test_weekly_preset_processed_on_matching_weekday`: `weekday = date.today().weekday()` → fällig → zählt als verarbeitet (oder error_count wegen leerer Locations)
- `test_weekly_preset_skipped_on_non_matching_weekday`: `weekday = (date.today().weekday() + 1) % 7` → nicht fällig heute → wird übersprungen, kein Fehler

### §8 LoC-Budget

| Datei | Änderung | LoC |
|-------|----------|-----|
| `internal/model/compare_preset.go` | +1 Feld + Kommentar | ~3 |
| `internal/store/store.go` | +4 Zeilen Migration | ~4 |
| `internal/handler/compare_preset.go` | +3 Zeilen Validation | ~4 |
| `api/routers/scheduler.py` | Weekly-Branch in Dispatch-Loop | ~15 |
| `frontend/src/lib/types.ts` | +1 Feld | ~2 |
| `frontend/src/lib/components/compare/SavePresetDialog.svelte` | Weekday-Picker Block | ~18 |
| `tests/tdd/test_issue_461_compare_preset_dispatch.py` | _make_preset + 2 neue Tests + 1 Umbenennung | ~30 |
| **Gesamt** | | **~76 LoC** |

## Expected Behavior

- **Input:** Täglicher Cron-Trigger um 06:00 vom Go-Scheduler via `POST /api/scheduler/compare-presets-daily`; `compare_presets.json` enthält daily- und/oder weekly-Presets; `today.weekday()` bestimmt welche weekly-Presets fällig sind.
- **Output:**
  - Alle `daily`-Presets werden verarbeitet (unverändert zu #461)
  - Weekly-Presets mit `preset.weekday == today.weekday()` werden verarbeitet und Compare-E-Mail versendet
  - Weekly-Presets mit nicht übereinstimmendem Wochentag werden still übersprungen (kein `error_count`-Increment)
  - HTTP 200 `{"status": "ok", "count": ...}` — `count` ist `error_count` über daily und weekly gemeinsam
- **Side effects:**
  - `data/users/{user_id}/compare_presets.json` wird nach jedem erfolgreichen Versand (daily oder weekly) per Read-Modify-Write aktualisiert (`letzter_versand`, `top_ort_letzter_versand`) — BUG-DATALOSS-GR221-konform
  - Go-Store-Migration schreibt `weekday=4` in Speicher für Bestandsdaten ohne weekday-Feld; die JSON-Datei selbst wird nicht überschrieben (nur beim nächsten Update-Call persistiert)
  - Frontend zeigt Weekday-Picker nur bei schedule='weekly' (konditionaler Block)

## Acceptance Criteria

**AC-1:** Given ein weekly-Preset mit `weekday = date.today().weekday()` in `compare_presets.json` / When der Scheduler `POST /api/scheduler/compare-presets-daily` ausführt / Then wird das weekly-Preset als fällig erkannt und in die Versandlogik übergeben (nicht übersprungen, error_count nicht erhöht wegen schedule-Typ)
  - Test: (populated after /tdd-red)

**AC-2:** Given ein weekly-Preset mit `weekday = (date.today().weekday() + 1) % 7` (morgen) / When der Scheduler den Dispatch-Endpoint aufruft / Then wird das Preset ohne Fehler übersprungen (kein error_count-Increment durch falsche Wochentag-Prüfung, kein Versand)
  - Test: (populated after /tdd-red)

**AC-3:** Given ein Bestandsdatensatz in `compare_presets.json` ohne `weekday`-Feld und `schedule='weekly'` / When `LoadComparePresets()` im Go-Store aufgerufen wird / Then hat das geladene Preset `Weekday == 4` (Freitag-Default) — kein Crash, keine Daten-Korruption
  - Test: (populated after /tdd-red)

**AC-4:** Given ein Create- oder Update-Request für ein weekly-Preset mit `weekday = 7` (ungültig) / When der Go-Handler `validateComparePreset()` aufruft / Then antwortet der Endpoint mit HTTP 400 und einer Fehlermeldung die "weekday" enthält
  - Test: (populated after /tdd-red)

**AC-5:** Given ein User öffnet den SavePresetDialog und wählt `schedule = 'weekly'` / When der Dialog gerendert wird / Then ist ein Weekday-Picker mit 7 Optionen (Montag–Sonntag) sichtbar; bei `schedule = 'daily'` oder `schedule = 'manual'` ist der Picker nicht sichtbar
  - Test: (populated after /tdd-red)

**AC-6:** Given `compare_presets.json` mit einem daily- und einem weekly-Preset (weekly heute fällig) / When `_run_compare_presets_daily()` aufgerufen wird / Then werden beide Presets verarbeitet; ein manually-Preset in derselben Datei wird übersprungen ohne error_count zu erhöhen
  - Test: (populated after /tdd-red)

## Known Limitations

- **Go-Cron bleibt täglich 06:00 UTC:** Kein separater weekly-Cron; die Wochentag-Prüfung erfolgt im Python-Dispatcher. Der tatsächliche Versandtag kann bei Empfängern in anderen Zeitzonen um einen Tag abweichen.
- **Kein Retry bei verpasstem weekly-Preset:** Schlägt ein weekly-Preset an seinem Wochentag fehl, wird es erst in 7 Tagen erneut versucht.
- **Store-Migration nur im Speicher:** `LoadComparePresets()` setzt `Weekday=4` in der geladenen Struct, schreibt aber nicht sofort zurück. Der Wert wird erst persistiert, wenn das Preset über einen Update-Call gespeichert wird.
- **Kein User hat aktuell weekly-Presets:** Issue #509 hat nur daily/manual-Presets migriert. Das Feature ist für zukünftige Presets relevant.
- **`forecast_hours` fest auf 48:** Wie in #461 — weekly-Presets erben diese Einschränkung.

## Changelog

- 2026-06-02: Initial spec — Issue #511. Weekly-Preset-Support durch Erweiterung des bestehenden daily-Jobs: Go-Modell/Store/Handler um weekday-Feld, Python-Dispatcher um weekly-Branch, Frontend um Weekday-Picker; 6 AC im AC-N-Format.
