---
entity_id: throttle_store
type: module
created: 2026-07-10
updated: 2026-07-10
status: draft
version: "1.0"
tags: [alerts, cooldown, throttle, refactor, migration]
---

<!-- Issue #1213 -->

# ThrottleStore — Gemeinsamer Cooldown-Speicher

## Approval

- [x] Approved (PO, 2026-07-10)

## Purpose

Ersetzt sechs parallel implementierte Cooldown-("nicht schon wieder alarmieren")-Prüfungen
und drei-plus getrennte State-Dateien durch EINE Klasse `ThrottleStore` mit EINEM
State-File pro Nutzer. Behebt vier latente Bugs: stillen Totalausfall bei defektem
Trip-Eintrag (alle Trips fail-open), gegenteilige `null`-Cooldown-Semantik zwischen
Trip- und Compare-Pfad, Lost-Update/Spam bei nebenläufigem Scheduler+API-Zugriff, und
die fehlende Tageslimit-Prüfung im Compare-Pfad.

## Source

- **File:** `src/services/throttle_store.py` (NEU) — `class ThrottleStore`
- **File:** `src/services/trip_alert.py` (MODIFY) — Trip-, Radar- und Doppel-Alert-Guard
  auf Store umstellen; toten Code `_is_throttled` entfernen; `get_time_until_next_alert`
  auf per-Trip-Cooldown + Store umstellen
- **File:** `src/services/compare_alert.py` (MODIFY) — Cooldown-Check auf Store umstellen,
  Tageslimit-Anbindung, `null`→Default-Auflösung vor Store-Aufruf
- **File:** `src/services/alert_daily_limit.py` (MODIFY) — `increment` atomar machen
  (tmp+`os.replace`), auf `get_data_dir` umstellen
- **File:** `src/app/loader.py` (READ-ONLY Dependency) — `get_data_dir(user_id)`
  (`:774-803`), kanonische Datenpfad-Auflösung (`GZ_DATA_DIR`/`_DATA_ROOT`, #1133)

> Alle betroffenen Dateien liegen im Python-Core-Backend (`src/services/`, `src/app/`).
> Keine Go-API- oder Frontend-Anteile.

## Estimated Scope

- **LoC:** ~370 produktiv (Store ~150, trip_alert.py-Umbau ~120, compare_alert.py-Umbau
  ~100) plus Tests
- **Files:** 4 MODIFY (`trip_alert.py`, `compare_alert.py`, `alert_daily_limit.py`,
  `tests/integration/test_trip_alert.py`) + 2 CREATE (`throttle_store.py`,
  `tests/tdd/test_throttle_store.py`)
- **Effort:** high (kritischer Alarm-Pfad, Nebenläufigkeit, Migration von Bestandsdaten)

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `loader.get_data_dir(user_id)` | intern (`src/app/loader.py`) | Kanonische Nutzer-Datenpfad-Auflösung, respektiert `GZ_DATA_DIR`/`_DATA_ROOT` (#1133) |
| `DeviationAlertEngine.is_cooldown_active` | intern (`src/services/deviation_alert_engine.py:85-97`) | Referenz-Semantik für „gedrosselt?" — falsy Cooldown → nicht gedrosselt |
| `alert_daily_limit.is_allowed` / `.increment` | intern (`src/services/alert_daily_limit.py:48/56`) | Tageslimit-Mechanik (#1070), künftig auch vom Compare-Pfad genutzt |
| `tempfile.mkstemp` / `os.replace` | stdlib | Atomare Writes ohne Lock-Datei-Reste |
| `datetime` / `zoneinfo` | stdlib | UTC-Normalisierung gespeicherter Zeitstempel |
| `AlertStateService.save` | intern (`src/services/alert_state.py:60`) | Read-Modify-Write-Vorbild für die Radar-Migration (Key `radar_throttle` darf nicht den restlichen State überschreiben) |

## Implementation Details

### Store-API

```python
class ThrottleStore:
    def __init__(self, user_id: str, data_dir: Path | None = None): ...
    def last_sent(self, scope: str, key: str) -> datetime | None       # aware UTC
    def is_throttled(self, scope: str, key: str, cooldown_minutes: int, now: datetime) -> bool
    def record(self, scope: str, key: str, now: datetime) -> None
    def clear(self, scope: str, key: str) -> None
```

- **File:** `data/users/<uid>/throttle_state.json`, Pfad über `get_data_dir(user_id)`
  (respektiert `GZ_DATA_DIR`/`_DATA_ROOT`); optionaler `data_dir`-Konstruktor-Override
  für Tests.
- **Struktur:** `{scope: {key: iso_timestamp}}`. Scopes: `trip`, `radar`, `compare_preset`.
- **`is_throttled`-Semantik:** identisch zu `is_cooldown_active` — `cooldown_minutes`
  falsy (`0`, `None`) → nicht gedrosselt (`False`); zusätzlich tz-Normalisierung
  des gespeicherten Werts (naive Timestamps werden als UTC interpretiert, bevor
  verglichen wird).
- **Write:** temp-File im selben Verzeichnis + `os.replace` (atomar auf POSIX).
  Vor jedem Write wird die Datei neu geladen und der eine betroffene
  `scope/key`-Eintrag gemerged (Lost-Update-Schutz zwischen API-Prozess und
  Scheduler, die beide eine eigene Instanz halten).
- **Load:** pro Eintrag tolerant — ein defekter/nicht-parsbarer Timestamp verwirft
  NUR diesen einen `scope/key`-Eintrag, nicht die gesamte Datei (Fix für den
  heutigen Trip-Bug: aktuell verwirft ein defekter Eintrag alle Trips → Spam für
  alle Nutzer).

### Migration (idempotent, beim ersten Store-Load pro Nutzer)

| Quelle | Format | Ziel-Scope/Key | Hinweis |
|---|---|---|---|
| `alert_throttle.json` | `{trip_id: iso}` | `trip/<trip_id>` | direkte Übernahme |
| `compare_alert_throttle.json` | `{preset_id: iso}` | `compare_preset/<preset_id>` | direkte Übernahme |
| `alert_state/<trip_id>.json`, Key `radar_throttle.reported_at` | eingebettet | `radar/<trip_id>` | **Read-Modify-Write** — nur der eine Schlüssel wird herausgezogen, der Rest von `alert_state/<trip_id>.json` bleibt unangetastet (Datenverlust-Regel #102) |
| `radar_alert_throttle.json` (Legacy) | `{trip_id: iso}` | `radar/<trip_id>` | Fallback-Quelle; bei Konflikt mit dem alert_state-Wert gewinnt der **jüngere** Timestamp |

Migration läuft lazy beim ersten `ThrottleStore(user_id)`-Zugriff (kein separates
Migrations-Skript nötig, da pro-Nutzer und idempotent — bereits migrierte
`scope/key`-Einträge werden nicht erneut aus der Altquelle überschrieben).
Migration selbst nutzt denselben tmp+`os.replace`-Schreibpfad wie reguläre Writes.

### null-Cooldown-Auflösung (Aufrufer-Verantwortung)

Der Store selbst sieht niemals `None` als `cooldown_minutes`. Jeder Aufrufer löst
`None`/fehlend VOR dem Store-Aufruf auf den jeweiligen Default auf:

- **Trip-Pfad:** `None` → `throttle_hours * 60` (per-Trip-Konfiguration, i.d.R. 120
  Minuten) — bereits heutiges Verhalten von `_is_throttled_with_cooldown`.
- **Compare-Pfad:** `None` → identischer Default wie Trip-Pfad (heute Bug: `None`
  wurde 1:1 an `is_cooldown_active` durchgereicht, welches `None` als "kein Limit"
  interpretiert — Compare-Alerts liefen dadurch ungedrosselt).
- **`0`** bleibt in beiden Pfaden „kein Limit" (#181, unverändert).

### Radar-Konsolidierung

Der Store wird die alleinige Radar-Throttle-Quelle. Nach dem Umbau:
- `_is_radar_throttled` liest über `store.is_throttled("radar", trip_id, cooldown_min, now)`.
- Erfolgreicher Radar-Versand schreibt über `store.record("radar", trip_id, now)`.
- `clear_radar_throttle` wird zu `store.clear("radar", trip_id)`.
- Der alert_state-Schlüssel `radar_throttle` und die Legacy-Datei
  `radar_alert_throttle.json` werden künftig **nicht mehr geschrieben** (nur noch
  als Migrationsquellen gelesen, s.o.).

### Compare-Tageslimit-Anbindung

`compare_alert.py` ruft vor dem Versand zusätzlich `alert_daily_limit.is_allowed(user_id, now)`
auf (analog zu den sechs bestehenden Aufrufstellen in `trip_alert.py`) und nach
erfolgreichem Versand `alert_daily_limit.increment(user_id, now)`. `increment` wird
dafür selbst atomar gemacht (tmp+`os.replace` statt direktem `write_text`) und auf
`get_data_dir` umgestellt (statt hartkodiertem `data/users/{user_id}/...`-Pfad).

### Toter Code / Anzeige-Fix

- `_is_throttled` (`trip_alert.py:422-437`) wird entfernt — heute nur von
  `tests/integration/test_trip_alert.py:80-144` gehalten; dieser Test wird auf
  `_is_throttled_with_cooldown` bzw. den Store migriert.
- `get_time_until_next_alert` (`trip_alert.py:439-459`) rechnet heute mit der
  globalen `throttle_hours`-Einstellung statt dem per-Trip-Cooldown — die Anzeige
  „nächster Alarm möglich ab" widerspricht damit dem tatsächlichen Drossel-Verhalten.
  Wird auf per-Trip-Cooldown + `store.last_sent(...)` umgestellt.
- `check_official_alert_triggers` (Level-Dedup ohne Timestamp) bleibt konzeptionell
  getrennt vom Cooldown und wird NICHT in den Store gezogen.

## Expected Behavior

- **Input:** Aufrufer (Trip-Alert-Service, Compare-Alert-Service) übergeben `scope`,
  `key` (z.B. `trip_id` oder `preset_id`), einen bereits auf Default aufgelösten
  `cooldown_minutes`-Wert (nie `None`) sowie `now` (aware UTC datetime, Funktionsparameter
  — kein `datetime.now()` innerhalb des Stores).
- **Output:** `is_throttled(...)` liefert `bool`; `last_sent(...)` liefert
  `datetime | None`. Kein Rückgabewert bei `record`/`clear` (reine Side-Effects).
- **Side effects:** Schreibt/liest `data/users/<uid>/throttle_state.json`. Beim
  ersten Zugriff pro Nutzer werden die vier Altquellen (falls vorhanden und noch
  nicht migriert) idempotent eingelesen; `alert_state/<trip_id>.json` wird dabei
  per Read-Modify-Write nur um den einen Schlüssel bereinigt, nicht ersetzt.

## Acceptance Criteria

- **AC-1:** Given ein Nutzer mit drei Altdateien (`alert_throttle.json`,
  `compare_alert_throttle.json`, `alert_state/<trip_id>.json` mit `radar_throttle`-Key)
  / When der erste `ThrottleStore(user_id)`-Zugriff erfolgt / Then existiert genau
  eine `throttle_state.json` mit allen drei migrierten Scopes (`trip`, `compare_preset`,
  `radar`), und keine der Altdateien wird künftig noch beschrieben.
  - Test: Fixture mit drei präparierten Altdateien anlegen, Store instanziieren,
    `last_sent()` für alle drei Scopes prüfen; anschließend `record()` aufrufen und
    verifizieren, dass NUR `throttle_state.json` sich ändert.

- **AC-2:** Given ein naiver (tz-loser) Timestamp im Alt-State eines Trips / When
  der Trip-Pfad (`_is_throttled_with_cooldown` bzw. Store) diesen liest / Then
  crasht nichts, und NUR dieser eine Trip fällt aus (andere Trips im selben State
  bleiben normal drosselbar) — kein globaler Ausfall wie beim heutigen
  `alert_throttle.json`-Loader.
  - Test: Zwei Trip-Einträge in `alert_throttle.json`, einer mit gültigem ISO-Timestamp,
    einer mit korrumpiertem Wert; nach Migration/Load muss der gültige Trip
    weiterhin korrekt gedrosselt sein, der korrumpierte Eintrag darf nur sich selbst
    (nicht den ganzen Store) ausfallen lassen.

- **AC-3:** Given ein naiver (tz-loser) Timestamp im Compare-Alt-State / When der
  Compare-Pfad diesen liest / Then bricht NUR das eine betroffene Preset aus, alle
  anderen Presets bleiben normal drosselbar — im Gegensatz zum heutigen Verhalten,
  bei dem ein defekter Eintrag ALLE Presets abreißt.
  - Test: Zwei Preset-Einträge in `compare_alert_throttle.json`, einer korrumpiert;
    nach Migration muss das gültige Preset weiterhin korrekt gedrosselt sein.

- **AC-4:** Given `alert_cooldown_minutes` ist `null` oder fehlt in der
  Trip-Konfiguration / When der Trip-Pfad UND der Compare-Pfad den Cooldown prüfen
  / Then verhalten sich beide identisch (Default-Cooldown greift, keine Alarmierung
  vor Ablauf) — statt der heutigen gegenteiligen Semantik (Compare ließ bei `null`
  ungedrosselt durch).
  - Test: `cooldown_minutes=None` an Trip- und Compare-Aufrufer übergeben, jeweils
    kurz nach einem `record()`-Aufruf `is_throttled` prüfen — beide müssen `True`
    liefern.

- **AC-5:** Given zwei nebenläufige Prozesse (z.B. API-Instanz + Scheduler) rufen
  gleichzeitig `record()` für unterschiedliche `scope/key`-Kombinationen auf demselben
  `throttle_state.json` auf / When beide Writes abgeschlossen sind / Then sind
  BEIDE Einträge in der Datei vorhanden — kein Lost Update durch fehlendes Reload
  vor dem Write.
  - Test: Zwei `ThrottleStore`-Instanzen (gleicher `user_id`, gleicher `data_dir`)
    gegeneinander laufen lassen, je einen anderen Key schreiben; abschließend eine
    dritte frische Instanz laden und beide Keys verifizieren.

- **AC-6:** Given ein Compare-Preset unterhalb des Cooldowns, aber das Tageslimit
  (#1070) ist für den Nutzer bereits erreicht / When der Compare-Alert-Service einen
  Alarm auslösen möchte / Then wird der Versand unterdrückt, weil
  `alert_daily_limit.is_allowed(user_id, now)` `False` liefert — analog zum
  bestehenden Trip-Verhalten.
  - Test: `alert_daily_count.json` auf das Tageslimit setzen, Compare-Alert mit
    unproblematischem Cooldown auslösen, Versand-Unterdrückung verifizieren.

- **AC-7:** Given ein Trip mit per-Trip-`alert_cooldown_minutes` ungleich der
  globalen `throttle_hours`-Einstellung / When `get_time_until_next_alert` für
  diesen Trip aufgerufen wird / Then basiert die Rückgabe auf dem per-Trip-Cooldown
  und `store.last_sent(...)`, nicht auf der globalen `throttle_hours`-Einstellung.
  - Test: Trip mit abweichendem `alert_cooldown_minutes` und einem `record()`-Zeitpunkt
    vorbereiten, `get_time_until_next_alert` aufrufen, Restzeit gegen den per-Trip-Wert
    (nicht den globalen) verifizieren.

## Known Limitations

- Die Migration läuft lazy pro Nutzer beim ersten Store-Zugriff, nicht als
  einmaliges globales Skript — bei sehr vielen inaktiven Nutzern bleiben deren
  Altdateien bis zum ersten Zugriff unmigriert liegen (harmlos, da idempotent und
  ohne Datenverlust).
- `check_official_alert_triggers` (Level-Dedup) wird bewusst NICHT in den Store
  integriert, da es kein Timestamp-Cooldown-Konzept ist — eine künftige
  Konsolidierung wäre ein separates Follow-up.
- Symlink-/Lock-freie Atomarität (`tempfile` + `os.replace`) schützt vor
  Lost Updates zwischen unabhängigen Prozessen, aber nicht vor echten
  Race-Conditions innerhalb derselben Millisekunde bei identischem `scope/key` aus
  zwei Prozessen gleichzeitig — letzter Schreiber gewinnt (wie bisher, kein
  Verschlechterung ggü. Ist-Zustand).

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** keine
- **Rationale:** Reines Refactoring einer internen Service-Schicht (Konsolidierung
  bestehender Cooldown-Logik hinter einer neuen, aber konzeptionell unveränderten
  Schnittstelle). Keine neue Technologie, kein neues architektonisches Muster, keine
  Auswirkung auf externe Schnittstellen (API-Contract, DTOs bleiben unverändert).

## Test Plan

Kern-Schicht (deterministisch, keine Mocks — echte State-Files als Fixtures unter
`tests/tdd/test_throttle_store.py`):

- `test_migration_pulls_all_three_legacy_sources` (AC-1)
- `test_migration_is_idempotent_on_second_load` (AC-1, Regel-Budget: verhindert
  doppelte Migration/Überschreiben bereits migrierter Werte)
- `test_corrupt_trip_entry_isolates_single_trip` (AC-2)
- `test_corrupt_compare_entry_isolates_single_preset` (AC-3)
- `test_null_cooldown_resolves_to_default_trip_path` (AC-4)
- `test_null_cooldown_resolves_to_default_compare_path` (AC-4)
- `test_concurrent_record_no_lost_update` (AC-5)
- `test_compare_alert_blocked_by_daily_limit` (AC-6)
- `test_daily_limit_increment_is_atomic`
- `test_get_time_until_next_alert_uses_per_trip_cooldown` (AC-7)
- `test_radar_throttle_migration_prefers_newer_timestamp` (Legacy-vs-alert_state-Konflikt)
- `test_radar_migration_preserves_other_alert_state_keys` (Read-Modify-Write, #102)
- `test_dead_code_is_throttled_removed` (`doc-compliance`-artiger Regressionstest:
  Import-Fehler bei Referenz auf entferntes Symbol)

Ergänzend MODIFY: `tests/integration/test_trip_alert.py` — bestehende Tests gegen
`_is_throttled` werden auf `_is_throttled_with_cooldown`/Store migriert, kein
Testverlust.

## Changelog

- 2026-07-10: Initial spec erstellt — Issue #1213
