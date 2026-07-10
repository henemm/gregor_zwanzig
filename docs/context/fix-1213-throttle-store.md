# Context: fix-1213-throttle-store

## Request Summary
Die „nicht schon wieder alarmieren"-Logik (Cooldown/Throttle) ist sechsmal parallel implementiert mit drei+ getrennten State-Dateien und vier latenten Bugs (stiller Totalausfall, gegenteilige `null`-Semantik, Lost Updates/Spam, Tageslimit-Lücke). Ziel: **ein** `ThrottleStore(user_id, data_dir=None)` mit **einem** State-File pro Nutzer, atomaren Writes, tz-toleranter Migration der Altdateien und geschlossener Tageslimit-Lücke im Compare-Pfad.

## Related Files (verifiziert per Explore, Zeilen ggü. Issue leicht verschoben)

| Datei | Relevanz |
|------|-----------|
| `src/services/trip_alert.py` | Enthält 5 der 6 Throttle-Stellen + 3 State-Files. Hartkodierte Pfade (`:79`, `:556`, `:821`), keine atomaren Writes (kein `os`/`tempfile`-Import). |
| `src/services/compare_alert.py` | Compare-Cooldown (`:84-90`, keyed by `preset_id`), eigenes File `compare_alert_throttle.json` (`:57`). **Keine** Tageslimit-Prüfung. Cooldown-Check liegt AUSSERHALB jedes try. |
| `src/services/deviation_alert_engine.py` | Kanonischer Vergleich `is_cooldown_active` (`:85-97`) — ohne tz-Normalisierung; `if not cooldown_minutes` behandelt `0` und `None` gleich. `_highest_severity`/`_filter_against_alert_state` sind ein ANDERES Konzept (Ranking, nicht Cooldown). |
| `src/services/alert_daily_limit.py` | Modul (`is_allowed`/`increment` `:48/:56`), File `alert_daily_count.json` (`:22`, hartkodiert). Nur von `trip_alert.py` aufgerufen, NICHT von `compare_alert.py`. increment nicht atomar (`:68-69`). |
| `src/app/loader.py` | `get_data_root()`/`get_data_dir(user_id)` (`:774-803`) = kanonischer `GZ_DATA_DIR`/`_DATA_ROOT`-Mechanismus (#1133). Keiner der Throttle-Pfade nutzt ihn. |
| `src/services/alert_state.py` | `AlertStateService.save` (`:60`) — File `alert_state/<id>.json`, `mkdir` + direktes `write_text` (nicht atomar). Trägt den Radar-Throttle-Schlüssel `radar_throttle`. |

## State-Files heute (Ist-Zustand)

| File | Format | Schreiber | Atomar? |
|------|--------|-----------|---------|
| `alert_throttle.json` | `{trip_id: iso}` | `_save_throttle_times` (`trip_alert.py:491`) | Nein |
| `compare_alert_throttle.json` | `{preset_id: iso}` | `_save_throttle_times` (`compare_alert.py:233`) | Nein |
| `radar_alert_throttle.json` (Legacy) | `{...: iso}` | `check_radar_alerts` (`trip_alert.py:826`) | Nein |
| `alert_state/<trip_id>.json` → Key `radar_throttle.reported_at` | eingebettet | `check_radar_alerts` (`trip_alert.py:818`) | Nein |
| `alert_daily_count.json` | `{date, count}` | `increment` (`alert_daily_limit.py:68`) | Nein |
| `alert_log.json` | `{entries:[]}` | `_append_alert_log` (`trip_alert.py:564`) | Nein (kein mkdir) |

## Die 6 Throttle-Implementierungen (verifiziert)

1. `trip_alert.py:397-420` `_is_throttled_with_cooldown` — **aktiv**, delegiert an `is_cooldown_active`. Per-Trip-Cooldown (`None`→Fallback `throttle_hours*60`).
2. `trip_alert.py:422-437` `_is_throttled` — **TOTER Produktivcode**, nur von `tests/integration/test_trip_alert.py` aufgerufen. Nutzt globale `throttle_hours` statt per-Trip-Cooldown.
3. `trip_alert.py:439-459` `get_time_until_next_alert` — **nur Tests**. Rechnet mit globaler `throttle_hours` → Anzeige widerspricht echtem Verhalten (Bug: sollte per-Trip-Cooldown zeigen).
4. `trip_alert.py:575-588` `_is_radar_throttled` — eigenständig, Minuten, liest `radar_throttle` aus alert_state. **MIT** tz-Normalisierung.
5. `trip_alert.py:722-740` Doppel-Alert-Guard in `check_radar_alerts` — eigene naive-Normalisierung. **MIT** tz-Normalisierung.
6. `compare_alert.py:84-90` — delegiert an `is_cooldown_active`, keyed by `preset_id`.

Zusätzlich: `check_official_alert_triggers` (`trip_alert.py:951-977`) — Dedup per Level-Vergleich, KEINE Timestamps (kein Cooldown-Konzept i.e.S.).

## Existing Patterns
- **Kanonischer Vergleich**: `DeviationAlertEngine.is_cooldown_active` — Ziel-Design injiziert genau diese Logik in den Store.
- **tz-Normalisierung** existiert korrekt in `_is_radar_throttled` (`:583-584`) und Doppel-Guard (`:731-732`) — als Vorlage nutzbar.
- **Read-Modify-Write** bereits bei Legacy-Radar (`:824-826`) und `_append_alert_log` (`:557-564`) — aber ohne tmp+replace.
- **Kanonische data-dir-Auflösung**: `get_data_dir(user_id)` (`loader.py:796`) — Store soll darauf aufsetzen (statt hartkodiert), `data_dir`-Override respektieren.
- **Tageslimit-Verdrahtung**: `is_allowed`/`increment` an 6 Stellen in `trip_alert.py` — Muster für Compare-Anbindung.

## Dependencies
- **Upstream (Store nutzt):** `loader.get_data_root/get_data_dir` (#1133), `is_cooldown_active` (Vergleichslogik), `datetime/timezone`, `os.replace`/`tempfile` (neu, für Atomarität).
- **Downstream (nutzt Store künftig):** `TripAlertService` (Trip + Radar + Doppel-Guard), `CompareAlertService`, `get_time_until_next_alert` (Anzeige-Fix), `alert_daily_limit` (Compare-Anbindung).

## Existing Specs / Referenzen
- `docs/reference/operations_playbook.md` — Daten-Schema-Reworks: Read-Modify-Write mit Merge, Migration + Roundtrip-Test (BUG-DATALOSS-GR221 #102).
- #1133 — GZ_DATA_DIR / Test-Isolation (`_DATA_ROOT`-Override in `tests/conftest.py`).
- #1070 — Tageslimit (`alert_daily_limit.py`), Vienna-Reset.
- #181 — `cooldown = 0` = kein Limit (bestehende Semantik).
- #827/#822/#656/#660 — bestehende Radar-Throttle-Tests (echte State-Files, keine Mocks).

## Bestehende Tests (relevant, keine Mocks — echte State-Files/In-Memory)
- `tests/integration/test_trip_alert.py:80-144` — einziger Aufrufer des toten `_is_throttled` + `get_time_until_next_alert` (In-Memory-Dict). **Muss beim Umbau angepasst/migriert werden.**
- `tests/tdd/test_alert_cooldown_quiet.py` — `_is_throttled_with_cooldown`, Loader-Roundtrip `alert_cooldown_minutes`.
- `tests/tdd/test_issue_827_radar_throttle_recording.py`, `test_feature_656_radar_nowcast.py`, `test_feature_660_convective_stage.py`, `test_issue_822_radar_nowcast_segment.py` — Radar-Throttle „einmal senden, dann throttle", echte `radar_alert_throttle.json`.
- `tests/tdd/test_issue_1070_daily_alert_limit.py` — Tageslimit, echte `alert_daily_count.json`, Tier-Reset Vienna.
- Keine `ThrottleStore`-Klasse, keine Throttle-Fixtures vorhanden.

## Risks & Considerations
- **Radar-Doppelschrieb:** Radar-Throttle wird HEUTE in ZWEI Orte geschrieben (`radar_alert_throttle.json` Legacy **und** alert_state-Key `radar_throttle`), aber `_is_radar_throttled` liest nur aus alert_state. Migration muss beide Quellen berücksichtigen und darf den restlichen alert_state (Read-Modify-Write!) nicht zerstören. **Klärungsbedarf in Analyse:** Issue-Kommentar nennt nur den alert_state-Schlüssel als Quelle.
- **null-Cooldown Entscheidung (Tech-Lead-Default, PO kann überstimmen):** `null`/fehlend → Default greift (fail-safe); `0` → kein Limit (#181). Compare wird an Trip-Verhalten angepasst.
- **Datenverlust-Regel (#102):** Store-Writes und Migration strikt Read-Modify-Write; alert_state-Radar-Migration darf nur den einen Schlüssel herausziehen.
- **Test-Isolation:** Store MUSS `get_data_dir`/`_DATA_ROOT` respektieren, sonst bleiben Tests cwd-abhängig (#1133).
- **Nebenläufigkeit:** API-Prozess und Scheduler cachen `_last_alert_times` je Instanz beim Init → Lost Updates. Store muss vor Write reloaden (oder pro-Operation lesen), Writes atomar (tmp+`os.replace`).
- **Fail-open vs. fail-closed bei defektem Eintrag:** trip-Load verwirft heute die GANZE Datei (alle Trips fail-open→Spam), Radar verwirft nur den Eintrag. Store soll per-Eintrag-tolerant sein.
- **Toter Code + Test-Abhängigkeit:** `_is_throttled` (tot) wird von einem Integrationstest gehalten — beim Entfernen Test mitziehen.
- **LoC-Limit:** Issue plant 3 Scheiben à ≤250 LoC; ganzes Issue in einem Workflow → LoC-Override wird nötig (erst PO fragen, Memory-Regel).
- **Renderer-Mailgate / Validator-Scope:** Änderungen an Alert-Render-Pfaden könnten `renderer_mail_gate` triggern — prüfen, ob `src/output/renderers/alert/*` berührt wird (voraussichtlich nein, reiner Service-Umbau).

## Analysis

### Type
Bug (Refactoring gegen 4 latente Bugs; Label `type:bug`, `priority:high`, PO-beauftragt).

### Ziel-Design (Store-API)
```python
class ThrottleStore:
    def __init__(self, user_id: str, data_dir: Path | None = None): ...
    def last_sent(self, scope: str, key: str) -> datetime | None      # aware UTC
    def is_throttled(self, scope, key, cooldown_minutes: int, now) -> bool
    def record(self, scope: str, key: str, now: datetime) -> None
    def clear(self, scope: str, key: str) -> None
```
- **File:** `data/users/<uid>/throttle_state.json` über `get_data_dir(user_id)` (respektiert `GZ_DATA_DIR`/`_DATA_ROOT`); optionaler `data_dir`-Override.
- **Struktur:** `{scope: {key: iso}}`. Scopes: `trip`, `radar`, `compare_preset`.
- **Write:** tmp-File + `os.replace` (atomar). **Vor jedem Write reload** (Lost-Update-Schutz zwischen API-Prozess & Scheduler).
- **Load:** per-Eintrag-tolerant (defekter Eintrag verwirft NUR sich selbst, nicht die ganze Datei), naive→UTC-Normalisierung.
- **`is_throttled`:** übernimmt `is_cooldown_active`-Semantik (`0`/falsy → nicht gedrosselt), aber mit tz-Normalisierung des gespeicherten Werts.

### Design-Entscheidungen (technisch, von mir festgelegt)
1. **null-Cooldown-Fix wandert in die Aufrufer:** `null`/fehlend → Aufrufer löst auf Default-Cooldown auf, BEVOR er den Store ruft; `0` bleibt „kein Limit" (#181). Store selbst sieht nie `None`. Damit verhalten sich Trip- und Compare-Pfad identisch (Compare-Bug behoben).
2. **Radar-Doppelschrieb konsolidieren:** Heute Schreiben in ZWEI Orte (Legacy `radar_alert_throttle.json` + alert_state-Key `radar_throttle`), gelesen wird NUR alert_state. Künftig: Store ist alleinige Quelle (`record(radar, trip_id)`). `_is_radar_throttled` liest aus Store, `clear_radar_throttle` → `store.clear(radar, trip_id)`. Alert_state-Radar-Key + Legacy-File werden nicht mehr geschrieben. **Migration** liest beide Altquellen (alert_state-Key als primär, Legacy-File als Fallback, jüngerer Timestamp gewinnt).
3. **Doppel-Alert-Guard (`check_radar_alerts` #5) + Dedup (`check_official_alert_triggers` #6):** Falten wo sinnvoll; #6 ist Level-Dedup ohne Timestamp — bleibt konzeptionell getrennt vom Cooldown, wird NICHT in den Store gezogen (nur Cooldown-mit-Timestamp gehört in den Store).
4. **Toter Code `_is_throttled` entfernen**, `get_time_until_next_alert` auf per-Trip-Cooldown + Store umstellen; die haltenden Tests in `test_trip_alert.py` mitziehen.
5. **Compare an Tageslimit anbinden** (`is_allowed`/`increment` analog trip_alert) + `increment` atomar machen.

### Migration (idempotent, beim ersten Store-Load)
| Quelle | Ziel-Scope/Key | Hinweis |
|---|---|---|
| `alert_throttle.json` `{trip_id: iso}` | `trip/<trip_id>` | |
| `compare_alert_throttle.json` `{preset_id: iso}` | `compare_preset/<preset_id>` | |
| `alert_state/<trip_id>.json` Key `radar_throttle.reported_at` | `radar/<trip_id>` | Read-Modify-Write; nur Key herausziehen, Rest unangetastet |
| `radar_alert_throttle.json` (Legacy) | `radar/<trip_id>` | Fallback; jüngerer Timestamp gewinnt |

### Affected Files
| File | Change | Description |
|------|--------|-------------|
| `src/services/throttle_store.py` | CREATE | Neue `ThrottleStore`-Klasse + Migration |
| `src/services/trip_alert.py` | MODIFY | Trip/Radar/Doppel-Guard auf Store; `_is_throttled` entfernen; `get_time_until_next_alert` fixen; null→default in Aufrufer |
| `src/services/compare_alert.py` | MODIFY | Store + Tageslimit-Anbindung + null→default |
| `src/services/alert_daily_limit.py` | MODIFY | `increment` atomar (tmp+replace) + `get_data_dir` |
| `tests/integration/test_trip_alert.py` | MODIFY | Aufrufer des toten `_is_throttled` migrieren |
| `tests/tdd/test_throttle_store.py` | CREATE | Store-Unit + Migration + naive-Timestamp + Race |
| ggf. weitere Radar-/Compare-Tests | MODIFY | Von `radar_alert_throttle.json` auf Store-Verhalten |

### Scope Assessment
- Dateien: ~5 src + Tests
- Geschätzte LoC: **~370 LoC produktiv** (Issue-Plan: 150+120+100) + Tests → deutlich über dem 250-Limit → **LoC-Override nötig** (PO-Permission einholen, Memory-Regel).
- Risk Level: **HIGH** — kritischer Alarm-Pfad, Nebenläufigkeit, Migration von Bestandsdaten (Datenverlust-Regel #102).

### Open Questions (an PO)
- [ ] LoC-Override auf 500+ freigeben (ganzes Issue = 3 Scheiben in einem Workflow)?
- [ ] null-Cooldown-Default (null→Default greift, 0→kein Limit) bestätigen — PO darf laut Issue überstimmen.

### Zu prüfen in Spec/TDD
- `get_time_until_next_alert` ist heute test-only — echten Anzeige-Pfad („nächster Alarm möglich ab") im Renderer/Mail suchen, damit der Anzeige-Fix (AC) wirklich greift.
