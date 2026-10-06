# Context: fix-2158-schreibsperren

## Request Summary
Issue #2158 (Epic #2138, Mittel): Lost Updates auf Nutzerdateien verhindern. Python schreibt
entgegen ADR-0031 `briefings/<id>.json` ohne Sperre und nicht atomar; die Go-Sperren wirken nur
prozessintern; Orte, Gruppen und Metrik-Vorlagen haben in Go gar keine Sperre beim
Read-Modify-Write.

## Ist-Stand (gemessen am Worktree auf origin/main, 2026-10-05)

### ADR-Lage
- `docs/adr/0031-persistenz-dateibasiert-data-users.md` Z.9-11, 17-18: „Go-Store einzige
  Schreib-Autorität, Python liest". Nennt noch `locations.json` (tatsächlich `locations/<id>.json`).
- ADR-0036 (`0036-nebenlaeufigkeitsschutz-inhalts-fingerabdruck.md:23-29`) räumt faktisch ein,
  dass Go **und** Python `briefings/<id>.json` schreiben; Z.88-90 fordert nur „Bewusstsein".
  Zeilenbelege dort veraltet. Z.97-112 Nachtrag aus #1433.
- ADR-0076:33-36: `forecast_budget.json` „ein Schreiber, unter fcntl-Sperre" (nur Python).
- Kein ADR zu `flock` zwischen Go und Python.

### Python-Schreiber auf Dateien, die auch Go schreibt
`src/app/loader.py:1922-1988` `save_trip` → `briefings/<id>.json`: lädt `existing`, deep-merge,
`open("w")`+`json.dump` (1985-1986). **Nicht atomar, nicht gesperrt.** Lesefehler wird
geschluckt (1976-1981) → halb geschriebene Datei ⇒ `existing={}` ⇒ Go-only-Felder gehen verloren.

| Aufrufer | Auslöser |
|---|---|
| `src/services/trip_command_processor.py:2387,2467,2633,2660,2961,2977` (`_apply_ruhetag`, `_shift_start`, `_apply_pause`, `_apply_skip`, `_cancel_trip`, `_resume_trip`) | Inbound-Kommando (Telegram-Webhook Echtzeit, Poll */5, Mail/SMS) |
| `trip_report_scheduler.py:987` `_skip_next_verbrauchen` | Briefing-Lauf stündlich; Trip aus `load_all_trips` zu Laufbeginn (stale) |
| `track_resolution.py:333` `backfill_stage_distances` (persist=True default) | Alarmlauf */15 (`trip_alert.py:1734`), Briefing-Lauf (`trip_report_scheduler.py:2183`), `_show_strecke` (`trip_command_processor.py:2802`), „Jetzt senden" (`api/routers/scheduler.py:239`, `trip_report_scheduler.py:446`). Vorschau: persist=False (`preview_service.py:172`) |
| `scripts/*` (Backfill/Migration/Staging-Setup) | manuell |

`src/services/scheduler_dispatch_service.py` — Compare-Presets in `briefings/<id>.json`, RMW,
`open("w")`, ungesperrt: `save_compare_preset_status` (221-280; Aufruf :697),
`save_compare_preset_pause` (283-340; :122 + `trip_command_processor.py:1322`),
`resume_compare_preset` (343-400; `trip_command_processor.py:1343`).

Nur-Python-Dateien (kein Konflikt mit Go): `pending_briefings.json` (atomar), `briefing_log.json`,
Kommando-Log, Snapshots, `alert_state`. Python schreibt **keine** Orte (`loader.save_location`
ohne Aufrufer), `groups.json`, `metric_presets.json`, `user.json`.

### Python-Sperrbaustein
`src/services/file_lock.py`: `acquire_exclusive(fd, timeout_s)`, `fcntl.flock(LOCK_EX|LOCK_NB)`
mit 20-ms-Poll, Timeout 2 s. Konvention: Sperrdatei `<ziel>.lock` daneben (weil `os.replace` die
Inode tauscht) + tempfile/`os.replace`. Genutzt von `throttle_store`, `briefing_slots`,
`forecast_budget`, `sms_daily_limit`, `alert_check_state`, `meteoalarm_budget`. **Nicht** für
Trip-/Briefing-Dateien. Spec: `docs/specs/modules/fix_1448_s2_dateisperren.md`.

### Go-Seite
- `internal/store/briefing_lock.go`: Map `UserID\x00id` → `sync.Mutex` mit Refcount; bewusst
  prozessintern (Z.9-10). Aufrufer: `handler/trip.go`, `weather_config.go:29,66`,
  `briefing_subscription.go`, `compare_preset.go`.
- `store/quota_lock.go` `LockQuota` je Nutzer; Reihenfolge Quota → Briefing.
- `store/write.go:34-58` `writeFileAtomic` (Temp + Rename, kein fsync); alle Store-Writes darüber.
- **Kein `syscall.Flock` / `gofrs/flock` im Go-Code.**
- Ablage: Trips/Vergleiche `briefings/<id>.json`; Orte `locations/<id>.json` (eine Datei je Ort);
  Gruppen `groups.json` (Sammeldatei); Metrik-Vorlagen `metric_presets.json` (Sammeldatei).
- RMW **ohne** Sperre: `handler/location.go` Update 133-185, Patch 190-250, Delete 270-290
  (Create nur `LockQuota`); `weather_config.go` `PutLocationWeatherConfigHandler` ~170-198;
  `handler/group.go` Create/Update/Delete (Delete iteriert Orte 187-203); `store/group.go`
  `LoadGroups` → `migrateGroups` (70-133) schreibt beim Lesen; `handler/metric_preset.go`
  Create/Delete/Patch. Sammeldateien ⇒ parallele Änderung an *verschiedenen* Gruppen/Vorlagen
  verliert eine.
- `telegram_tokens.json` bereits atomar + `s.mu` (#2160 AC-14) — Teilpunkt des Tickets erledigt.

### Python ↔ Go Kopplung
- Python → Go: nur `POST /api/internal/telegram-connect`, `/api/internal/premium-sms-learn`;
  Schutz allein `requireLocalOnly` (`localhost_guard.go:28-46`, vgl. #2159). Kein Trip-Schreib-Endpunkt.
- Go → Python: `X-GZ-Core-Auth` / `GZ_CORE_SHARED_SECRET` (ADR-0062).

### ETag (#1395, Frontend-Teil #1433)
`BriefingFingerprint` = sha256 der Dateibytes; If-Match optional. Schützt nur Browser-nach-Python
(412), nie Python-nach-Browser; das Fenster Prüfung→Schreiben (`trip.go:309-471`) ist nur gegen
Go-Anfragen gesperrt.

## Realistische Gleichzeitigkeit
Pro Trip: 1 Browser-Schreiber + 1-3 Python-Schreiber, gebündelt auf :00/:15/:30/:45 (Briefing- und
Alarmlauf starten zur vollen Stunde gleichzeitig; Überlappungsschutz nur je jobID) und bei
Kommandos. Python kann mit sich selbst kollidieren (FastAPI-Threadpool, kein Lock um `save_trip`).
Backfill schreibt je Etappe höchstens einmal; skip_next nur bei `true`.

## Existing Patterns
- Python: `<ziel>.lock` + `fcntl.flock` + tempfile/`os.replace` (`throttle_store.py:30,183`,
  `briefing_slots.py:53,398`, `forecast_budget.py:41,377`).
- Go: prozessinterne Lock-Map je (Nutzer, Entität) + `writeFileAtomic`.
- Go `flock(2)` und Python `fcntl.flock` sind auf Linux kompatibel (BSD-Locks auf Open-File-Description),
  sofern beide dieselbe `.lock`-Datei sperren.

## Dependencies
- Upstream: `internal/store/*`, `src/app/loader.py`, `src/services/file_lock.py`.
- Downstream: alle Trip-/Compare-/Orts-/Gruppen-/Vorlagen-Handler, Scheduler-Läufe, Inbound-Kommandos.

## Existing Specs
- `docs/specs/modules/fix_1448_s2_dateisperren.md`, `issue_1395_s2_etag_ifmatch.md` … `s6`,
  `fix_1756_send_idempotenz_lock.md`, `fix_1396_store_scope_race.md`, `user_scoped_store.md`,
  `throttle_store.md`, `docs/specs/bugfix/trip_mehrreiter_konfliktschutz.md`,
  `compare_konfliktschutz_teilfelder.md`.

## Tests (Bestand)
Go: `store/briefing_lock_test.go`, `handler/trip_etag_ifmatch_test.go` (ConcurrentWrites :211, :390,
:533), `compare_preset_etag_ifmatch_test.go`, `mengen_quote_test.go:352`. Keine Nebenläufigkeitstests
für Orte/Gruppen/Vorlagen. Python: `tests/tdd/test_file_lock_timeout.py`, Briefing-Slot-Tests; kein
Test zu nebenläufigem `save_trip`.

## Risks & Considerations
- **Datenverlust-Historie (#102):** halb gelesene Datei ⇒ `existing={}` ⇒ Replace statt Merge.
- Architekturwahl: (a) ADR-0031 ablösen, beide Prozesse sperren dieselbe `.lock`-Datei per flock;
  (b) Python-Schreibzugriffe über Go-Endpunkt routen (neue interne API, Auth heute nur
  Localhost-Guard, #2159). Entscheidung in `/20-analyse`.
- Lock-Reihenfolge Go (Quota → Briefing → neu Datei-flock) muss deadlock-frei bleiben; Python-Timeout
  2 s vs. lange Go-Handler.
- Python-Stale-State: Scheduler hält Trip-Objekt seit Laufbeginn — Sperre allein heilt das nicht,
  RMW muss *unter* der Sperre neu laden.
- LoC-Limit 250: Go-Locks (Orte/Gruppen/Vorlagen) + Cross-Process-Lock + ADR können über das Limit
  gehen → Scheibenschnitt in der Analyse prüfen.
- Staging-Daten für `hem` nicht lesbar ⇒ Nachweis über deterministische Kern-Tests (parallele
  Schreiber, zwei Nutzer).

## Analysis

### Type
Bug (Datenverlust-Risiko: Lost Updates auf Nutzerdateien, Epic #2138)

### Verifizierte Zusatzbefunde (Phase 2)
- **Keine Verklemmungsgefahr:** Kein Go-Handler hält `LockBriefing` während eines synchronen
  Python-Aufrufs. `LockBriefing` sitzt nur um Store-Zugriffe (`trip.go:61,225,304,519,603,674`,
  `weather_config.go:29,66`, `compare_preset.go:275,378,455,506,564`,
  `briefing_subscription.go:67,86,233`); Proxys (`proxy.go:265` Senden, `compare_preset.go:586-612`,
  `preview_proxy.go:38,76`) nehmen keine Sperre.
- **Sperre allein heilt nicht:** `loader._deep_merge_preserve_unknown` (`loader.py:135-148`):
  Overlay (Python-Trip) gewinnt, Listen (`stages`) werden komplett ersetzt. Ein zu Laufbeginn
  geladenes Trip-Objekt überschreibt neuere Browser-Änderungen auch MIT Sperre. Parse-Fehler
  (`loader.py:1974-1978` `except Exception: pass`) ⇒ `existing={}` ⇒ #102-Muster.
- **Compare-Preset-Schreiber** (`scheduler_dispatch_service.py:221-400`) lesen frisch, ändern nur
  Einzelfelder, `return` bei Lesefehler — nur nicht atomar/ungesperrt.
- **Lock-Dateien in Listen:** Alle Listen filtern `*.json` (Go `store/trip.go:144`,
  `compare_preset.go:134`, `location.go:34`, Migrationen, `scheduler/selftest.go:52`; Python
  `loader.py:341,1489,1625`, `trip_report_scheduler.py:346`, Skripte). `<id>.json.lock` wird nicht
  gezählt/geparst. **Ausnahmen:** Export `store/user.go:400-429` (Präfix `briefings/`,`locations/`
  ohne Suffixfilter ⇒ Lock-Datei landet im Archiv), `scripts/cleanup_1708c_dead_trips.py:69`
  (`rglob("*")`). Konvention `<ziel>.lock` existiert bereits (`briefing_slots.json.lock` u.a.).
- **Gruppen:** `LoadGroups` (`store/group.go:41-67`) → `migrateGroups` (70-135) schreibt beim GET
  (Orte zuerst, dann `groups.json`). `DeleteGroup` (185-206) schreibt `groups.json`, danach
  `handler/group.go:~186-203` je Ort `SaveLocation`. Alles ungesperrt.
- **Metrik-Vorlagen:** `handler/metric_preset.go` Create 153→185, Delete 199→219, Patch 237→289,
  RMW auf Sammeldatei, ungesperrt.
- **telegram_tokens.json:** bereits atomar + `s.mu` (#2160 AC-14) ⇒ Teilpunkt erledigt, nur Nachweis.
- **ADR:** höchste Nummer 0081 ⇒ neues **ADR-0082**; ADR-0031 Datei+Index auf
  „Abgelöst durch ADR-0082" (Muster ADR-0002/0030; `tests/test_adr_index_drift.py` prüft
  Index-Eintrag + Statusklasse Datei↔Index). ADR-0036 Zeilenbelege korrigieren.

### Architektur-Entscheidung (Tech Lead)
**flock-Variante, kein Go-Schreib-Endpunkt.** Begründung: ein interner Go-Endpunkt hätte nur
`requireLocalOnly` (#2159 offen) ⇒ neuer Cross-User-Schreibweg; flock erzeugt keine neue
Angriffsfläche und (s.o.) keine Verklemmung. Go und Python sperren **dieselbe** Datei
`data/users/<uid>/briefings/<id>.json.lock` (BSD-flock, Linux-kompatibel). Pfad wird in ADR-0082
und Spec festgenagelt und auf beiden Seiten getestet (sonst stilles Nichtwirken).

### Affected Files (with changes)
| File | Change Type | Description |
|------|-------------|-------------|
| `docs/adr/0082-*.md` | CREATE | Zwei Schreiber unter gemeinsamer `.lock`-Datei; Lock-Pfad, Reihenfolge, Timeouts |
| `docs/adr/0031-*.md`, `docs/adr/README.md`, `docs/adr/0036-*.md` | MODIFY | Status „Abgelöst durch ADR-0082"; veraltete Zeilenbelege |
| `internal/store/briefing_lock.go` | MODIFY | nach Mutex `syscall.Flock(LOCK_EX\|LOCK_NB)`+Poll auf `<id>.json.lock`, Frist ~5 s; `LockBriefingErr` |
| `internal/handler/trip.go`, `weather_config.go`, `compare_preset.go`, `briefing_subscription.go` | MODIFY | Lock-Timeout ⇒ 503 + Retry-After |
| `internal/store/location_lock.go` (o.ä.) / `handler/location.go`, `weather_config.go` | CREATE/MODIFY | Sperre je (Nutzer, Ort) um Update/Patch/Delete/PutWeatherConfig |
| `internal/store/group.go`, `handler/group.go` | MODIFY | Sperre je Nutzer um jedes RMW inkl. `migrateGroups`-beim-GET; Reihenfolge Gruppen → Orte |
| `internal/store/metric_preset.go`, `handler/metric_preset.go` | MODIFY | Sperre je Nutzer |
| `internal/store/user.go` | MODIFY | Export: nur `*.json` unter `briefings/`/`locations/` |
| `src/app/loader.py` | MODIFY | `update_trip(user_id, trip_id, mutate)`: Sperre → frisch lesen (Parse-Fehler wirft) → mutate → atomar `os.replace`; `save_trip` intern gesperrt+atomar, kein `existing={}` |
| `src/services/file_lock.py` | MODIFY (klein) | ggf. Helfer `locked_json_rmw(path, mutate_dict)` |
| `src/services/trip_command_processor.py` | MODIFY | 6 Kommandos als Mutations-Closures auf frischem Trip |
| `src/services/trip_report_scheduler.py` | MODIFY | `_skip_next_verbrauchen` unter Sperre idempotent (nur wenn noch `true`) |
| `src/services/track_resolution.py` | MODIFY | Backfill nur auf Etappen anwenden, deren ID+Wegpunkte in frischer Datei unverändert sind |
| `src/services/scheduler_dispatch_service.py` | MODIFY | 3 Compare-Preset-Schreiber gesperrt + atomar |
| `scripts/cleanup_1708c_dead_trips.py` | MODIFY | `*.lock` überspringen |
| Tests Go (`internal/store/*_test.go`, `internal/handler/*_test.go`) + Python (`tests/tdd/test_trip_schreibsperre.py` o.ä.) | CREATE | siehe Testplan |

### Scope Assessment
- Dateien: ~20 produktiv
- Geschätzte LoC: ~+550 produktiv, ~+500 Test ⇒ **`loc_limit_override` nötig (Vorschlag 700)**.
  Alles in EINEM Workflow (kein Abspalten), Reihenfolge der Teilschritte so, dass nach jedem
  Schritt alles grün bleibt: (1) ADR + Go-Sperren Orte/Gruppen/Vorlagen → (2) Go-flock +
  503 + Export-/Skript-Filter → (3) Python `update_trip`/`save_trip` → (4) Aufrufer-Umstellung →
  (5) Compare-Preset-Schreiber.
- Risiko: **MITTEL-HOCH** — zentrale Speicherwege beider Prozesse; größte Regressionsfläche ist
  die Umstellung der Kommando-Closures (bestehende Kommando-Tests müssen grün bleiben) und
  Stage-Arrival-Berechnung beim Speichern (bit-gleich).

### Timeout-Verhalten je Aufrufer (Frist 5 s)
| Aufrufer | Bei Timeout |
|---|---|
| Go-Schreib-Handler | 503 + Retry-After, nichts geschrieben |
| Inbound-Kommando | nichts schreiben, Nutzer bekommt Antwort „bitte erneut senden" — nie still verwerfen |
| `_skip_next_verbrauchen` | Trip in diesem Lauf NICHT senden (Überspringen-Zusage gilt), nächster Lauf erneut |
| Backfill Distanzen | Warn-Log, mit In-Memory-Ergebnis weiterrechnen, nicht persistieren |
| Compare-Status/Pause/Resume | Warn-Log, `False`; Kommando-Pfad meldet Fehler an Nutzer |
| Kein Pfad | fällt auf ungesperrtes Schreiben zurück |

### Lock-Reihenfolge (deadlock-frei, verbindlich)
Quota → Gruppen/Vorlagen (je Nutzer) → Ort → Briefing-Mutex → Datei-flock. Nie umgekehrt.
`migrateGroups` läuft unter bereits gehaltener Gruppen-Sperre (interne `loadGroupsLocked`-Variante,
keine Reentranz).

### Testplan (Kern, deterministisch, keine Sleeps als Beweis)
- **Achtung:** Der Issue-Test „paralleler PATCH auf zwei Orte" ist heute schon grün (eine Datei je Ort)
  ⇒ ersetzt durch: **gleicher Ort, parallel, disjunkte Felder** ⇒ beide erhalten.
- Zwei verschiedene Gruppen parallel ⇒ beide in `groups.json`; `DeleteGroup` ‖ Orts-Update ohne
  Verklemmung; GET mit Migration ‖ Schreiber.
- Zwei verschiedene Metrik-Vorlagen parallel ⇒ beide erhalten.
- Roher `flock` (eigener FD) auf `<id>.json.lock` ⇒ Go-Schreiber wartet / 503 bei kurzer Frist.
- Go hält `LockBriefing` ⇒ Python-Subprozess mit `acquire_exclusive` wartet (Pipe-Handshake).
- Python hält Sperre ⇒ `update_trip`-Timeout liefert definierten Fehler; jeder Aufrufer-Pfad einmal.
- **Stale-Objekt:** Trip laden, Browser-Änderung (neue Etappenliste, Name) auf Platte, dann
  `_skip_next_verbrauchen`/Backfill/Kommando mit altem Objekt ⇒ Browser-Änderung bleibt.
- `update_trip` bei kaputter Datei wirft, Datei unverändert.
- Zwei Nutzer, gleiche Trip-ID ⇒ getrennte Lock-Dateien, kein gegenseitiges Blockieren.
- Export/Listen enthalten keine `.lock`-Datei.
- Compare-Status ‖ Pause ⇒ beide Felder erhalten.
- Mutationsprobe: je Sperre festlegen, welcher Test rot wird, wenn sie entfernt wird.

### Dependencies
- Upstream: `internal/store/*`, `src/app/loader.py`, `src/services/file_lock.py`.
- Downstream: Trip-/Compare-/Orts-/Gruppen-/Vorlagen-Handler, Briefing-/Alarmlauf, Inbound-Kommandos.
- Verwandt: #2159 (Localhost-Guard, Grund gegen Go-Endpunkt), #1433/#1395 (ETag), #2160 AC-14.

### Open Questions
- Keine PO-Fragen offen (Architekturwahl technisch entschieden, s.o.).
- Annahme: Datenablage lokal (kein NFS) — flock-Semantik gilt nur lokal; in Spec als Annahme festhalten.
