# Context: fix-2151-default-fallbacks-entfernen

Issue #2151 (bug, priority:high, Teil von Epic #2138 Multi-User-Readiness).
Grundsatz: ADR-0003 „Konsequente Mandantentrennung, kein `"default"`-Fallback" — ein Rückfall auf
`"default"` in einem authentifizierten Pfad ist verboten (= Cross-User-Datenleck).

## Request Summary
Alle `"default"`-Fallbacks für `user_id` in sendenden/ladenden Pfaden entfernen (Python-Router,
Python-Signatur-Defaults, Go-Config, Go-Store `WithUser("")`), plus Wächter-Test gegen Rückfall.
Mit abzuhaken (aus #1199): C5-60/C5-61 — `"default"` als Sentinel „unbekannter Absender" im
Telegram-Inbound.

## Related Files

### Python — Router (sendend)
| Datei:Zeile | Route | Aufrufer |
|---|---|---|
| `api/routers/scheduler.py:212-213` | `POST /api/scheduler/trips/{trip_id}/send`, `user_id: str = "default"` | Go `proxy.go:261-265` (`appendUserID`) |
| `api/routers/scheduler.py:298-299` | `POST /api/scheduler/compare-presets/{preset_id}/send`, `Query("default")` | Go `compare_preset.go:568-572` |
| `api/routers/debug.py:19-20` | `POST /api/debug/trigger-radar-alert`, `user_id="default"` | nur `GZ_ENV=staging` (`router.go:244`, `api/main.py:116`, `debug.py:51`); `/api/debug/` ist öffentlich (`auth.go:59`) → kein Auth-Kontext, Client-Query geht roh durch |

Kopiervorlage ohne Default: `scheduler.py:27/62/195` (`Query(...)`), `internal.py:30`, `preview.py:59`.
`appendUserID` (`proxy.go:151-153`) reicht bei leerer userID die Client-Query unverändert durch.

### Python — Signatur-Defaults (Prod-Aufrufer, die heute ohne user_id rufen)
| Stelle | Folge |
|---|---|
| `preview_service.py:158` `TripReportSchedulerService(self.settings)` | **aktives Leck heute, nur LESEND (= #2057):** `_user_id="default"` → `_convert_trip_to_segments` (direkt sowie transitiv über `_build_stage_trend` Z.2501 und `_build_thunder_forecast_from_trend_or_fetch`→`_collect_future_stage_weather` Z.2709) → `backfill_stage_distances(trip,"default",persist=False)` liest GPX aus `users/default/gpx` (`track_resolution.py:310`). Schreibwege (`save_trip`, Diagnose-jsonl) sind durch `persist_backfill=False` gesperrt. Snapshot-Zugriffe Z.1499/1562 liegen in `_send_trip_report_outcome`, NICHT im Vorschau-Pfad. |
| `inbound_email_reader.py:72`, `inbound_telegram_reader.py:108` `NotificationService()` | Konstruktor liest `Settings().with_user_profile("default")`; praktisch folgenlos (Methoden bekommen `settings` explizit), bricht aber nach Default-Entfernung mit TypeError |
| `load_trip` (`loader.py:397`) — 4 Prod-Aufrufer ohne user_id | harmlos: Pfad/Dict übergeben, `user_id` wirkt nur mit `data_dir` |

Übrige Defaults ohne Prod-Aufrufer ohne user_id: `alert_state:50`, `compare_alert:80`,
`compare_official_alert:77`, `compare_radar_alert:110`, `compare_weather_snapshot:42`,
`weather_extractor:77`, `weather_snapshot:74`, `trip_alert:343`, `scheduler_dispatch_service:165`,
`preview_service:54/343/367/393`, `trip_command_processor.py` (Dataclass-Feld Z.147 + ~12 Methoden),
`loader.py` (`save_trip`, `load_all_trips`, `get_*_dir`, Locations), `inbound_email_reader:304`,
`inbound_telegram_reader:440`.

### Python — Telegram-Sentinel (C5-60/61)
`inbound_telegram_reader.py:476` `_resolve_user_for_chat` → `lookup_user_by_telegram_chat_id(...) or "default"`;
Z.190 (`_process_update`) und Z.383 (`_process_callback_query`) prüfen `user_id == "default"` →
nur Registrierungshinweis. Kollidiert mit echtem Konto `default`. **Vorbild ohne Sentinel:**
`inbound_email_reader.py:280-302` (`None`, #2147 B2/AC-14), `inbound_sms_reader.py:312` (AC-9).

### Go
| Datei:Zeile | Befund |
|---|---|
| `internal/config/config.go:31` | `UserID envconfig:"USER_ID" default:"default"` (Env `GZ_USER_ID`; nur `frontend/e2e/ci-stack.sh:66` setzt `admin`) |
| `cmd/server/main.go:62` | Basis-Store `store.New(cfg.DataDir, cfg.UserID)` → an Scheduler (`:116`) und Router (`:129`) |
| `cmd/server/main.go:73-89` | Seed-Konto `cfg.UserID` wird angelegt, wenn fehlend und `GZ_AUTH_PASS` gesetzt → Prod/Staging seeden Konto `"default"` |
| `internal/store/store.go:14-28` | `WithUser("")` = No-Op → Basis-UserID |
| `cmd/migrate2154/main.go:19` | `store.New(*dataDir, "default")` (Einmal-Migration) |

`WithUser(`-Aufrufe (~40, trip/compare_preset/group/location/metric_preset/briefing_subscription/
weather_config/cockpit/archive_stats/briefing_history) nehmen **alle** `UserIDFromContext`. Leerer
String in Produktion nicht erreichbar (alle nicht öffentlich; leere Cookie-userId → 401,
`auth.go:84-89`). Basis-Store-Methoden bauen Pfade roh aus `s.UserID` (group/location/log/
metric_preset/briefing_subscription/briefing_lock) — heute kein aktiver Leck-Pfad, Restrisiko ist
allein der No-Op. Scheduler nutzt `ListUserIDs()` + explizite IDs, nie `s.UserID`.

## Existing Patterns
- Pflicht-`user_id` in Routern: `Query(...)` / nackter Parameter.
- Leer-Prüfung mit 401: `briefing_history.go:18`, `data_export.go:27`.
- Python-Wächter gegen leere ID: `compare_preview_service.py:223` (`if not user_id: raise`, ADR-0003).
- Zentrale Kennungs-Validierung: `VALID_USER_ID_RE` (`loader.py:1150`, in `get_data_dir`),
  Go `ValidUserID` (`pathsafe.go:20-29`) — beide akzeptieren `"default"`, lehnen `""` ab.
- Wächter-Tests nach Muster: `tests/test_output_timezone_guard.py`, `tests/test_success_status_guard.py`.

## Dependencies
- Upstream: Go-Auth-Kontext (`middleware.UserIDFromContext`), `Settings.with_user_profile`.
- Downstream: ~190 Python-Test-Aufrufe ohne user_id (v.a. `TripReportSchedulerService` ~60,
  `save_trip` 37, `TripAlertService` 31, `WeatherSnapshotService` 29); Go: `with_user_test.go:32-36`
  (prüft No-Op ausdrücklich), `data_export_test.go:112/403-409`, `config_test.go:28`,
  7 Tests mit `store.New(cfg.DataDir, cfg.UserID)`, 18 Dateien mit `store.New(…,"default")`,
  23 Handler-Testdateien ohne `ContextWithUserID` (+ `newTestStore` in 89 Dateien, Anteil ohne
  Kontext unbekannt).

## Existing Specs
- `docs/adr/0003-multi-tenant-isolation.md` — Grundsatz.
- `docs/specs/modules/fix_2140_pfad_traversal_nutzer_kennung.md:127-130` — hat den `WithUser("")`-No-Op
  nur **beibehalten** (Verhaltenserhalt), nicht sicherheitlich begründet → kein ADR-Konflikt; die
  Code-Kommentare in `store.go:17-20` sind entsprechend nachzuziehen.
- `docs/specs/modules/fix_2353_auth_lookup_fehler_503.md` — `ErrInvalidUserID`-Semantik.

## Risks & Considerations
- **Test-Fan-out ist das Hauptrisiko**, nicht der Produktivcode: harte Pflicht-Parameter brechen
  ~190 Python- und viele Go-Testaufrufe → LoC-Limit (250) sprengt sicher; Scheibenschnitt nötig.
- **`"default"` ist ein echtes Bestandskonto** (Seed via `cfg.UserID`, Cleanup-Skripte führen es in
  `NEVER_DELETE`/`REQUIRED_ACCOUNTS`, Daten unter `users/default/`). „`"default"` als Wert ablehnen"
  (Issue-Erwartung) würde dieses Konto aussperren → mit PO klären bzw. nur als *Fallback* verbieten.
- `cfg.UserID`-Default entfernen ändert das Seed-Verhalten auf Prod/Staging (Seed nur noch mit
  explizitem `GZ_USER_ID`) — Deploy-Umgebung prüfen (`/etc/…`-Env der systemd-Units liegt nicht im Repo).
- Basis-Store `s` ist an Scheduler/Router gebunden — `WithUser("")` panicen lassen darf keinen
  Startup-/Scheduler-Pfad treffen (laut Recherche keiner).
- Debug-Route ist öffentlich und staging-only; Staging-Tests rufen `user_id=default` explizit.
- #2057 (Vorschau-Leck) ist laut Issue eigenständig, der Fix liegt aber in derselben Zeile.

## Analysis

### Type
Bug (Sicherheit/Mandantentrennung, ADR-0003). Ein aktives, lesendes Leck (Vorschau-GPX, #2057),
sonst fehlende Verteidigungslinie gegen künftige Fallbacks.

### Tech-Lead-Entscheidungen
1. **`"default"` bleibt als Kontoname gültig, verboten wird nur der RÜCKFALL.** ADR-0003 verbietet den
   Fallback, nicht den Wert; `default` ist ein echtes Bestandskonto (Seed auf Prod/Staging, Daten unter
   `users/default/`, Cleanup-Schutzlisten). Abweichung vom Issue-Wortlaut („als Wert abgelehnt") →
   in der Spec begründet, PO bestätigt mit der AC-Freigabe.
2. **Go fail-closed über leeren Basis-Store statt `WithUser("")`-Panic.** `cfg.UserID`-Default fällt;
   Basis-Store bekommt in Prod `UserID=""`; jede Store-Methode, die aus `s.UserID` einen Pfad baut,
   verweigert leere Kennung (Fehler; die vier Helfer ohne error-Rückgabe — `briefingsDir`,
   `LocationsDir`, `PresetsFile`, `groupsFile` — dürfen nie `users//…` bauen, `filepath.Join`
   würde sonst still auf `data/users/locations` o.ä. zeigen). Vorteil: 20 Handler-Testdateien ohne
   Auth-Kontext bleiben unverändert (Basis-ID `"test"`), nur `config_test.go:28` bricht. Seed-Konto
   entsteht nur noch bei explizit gesetztem `GZ_USER_ID`; bestehendes Konto `default` bleibt
   unberührt (Datei liegt schon vor). Kein Fail-fast beim Start (Prod/Staging setzen die Variable nicht).
3. **Öffentliche Debug-Route** (`/api/debug/`, staging-only) ist kein Teil dieses Tickets — bekannt
   (#2304); hier nur `user_id` zur Pflicht machen.

### Scheibenschnitt
| Scheibe | Inhalt | Prozess |
|---|---|---|
| **A (dieser Workflow)** | Vorschau reicht echte `user_id` an `TripReportSchedulerService` (schließt Leck #2057) · drei Router ohne Default (`scheduler.py:213/299`, `debug.py:20` → Pflicht) · `NotificationService()`-Aufrufer in den Inbound-Readern · Telegram-Sentinel `"default"` → `None` (C5-60/61, Vorbild E-Mail-Reader) · Wächter-Test: kein user_id-Default `"default"` in `api/`; in `src/` Ratsche (Bestandsliste darf nur schrumpfen) | Python |
| B (Folge-Workflow) | `cfg.UserID`-Default weg, Store fail-closed bei leerer Kennung, Seed nur bei gesetztem `GZ_USER_ID`, Kommentar `store.go:14-20` nachziehen | Go |
| C (Folge-Workflow) | restliche Python-Signatur-Defaults entfernen (~190 Test-Aufrufe), Ratsche leer | Python |

### Affected Files (Scheibe A)
| File | Change | Description |
|---|---|---|
| `src/services/preview_service.py` | MODIFY | `user_id` bis `TripReportSchedulerService(self.settings, user_id=…)` durchreichen |
| `api/routers/scheduler.py` | MODIFY | Z.213 Pflicht, Z.299 `Query(...)` |
| `api/routers/debug.py` | MODIFY | Z.20 Pflicht |
| `src/services/inbound_telegram_reader.py` | MODIFY | `_resolve_user_for_chat` → `None`; Z.190/383 `is None`; Z.108 `NotificationService` |
| `src/services/inbound_email_reader.py` | MODIFY | Z.72 `NotificationService` |
| `tests/…` (Staging-Debug, Telegram-Reader, Vorschau) | MODIFY/CREATE | Nachweise + Wächter |
| `tests/test_user_id_default_guard.py` | CREATE | Wächter + Ratsche |

### Scope Assessment
- Dateien: ~6 Quell- + ~5 Testdateien · geschätzt +250/-40 LoC → `loc_limit_override` ggf. nötig
- Risk Level: MEDIUM (Telegram-Registrierungshinweis muss 1:1 erhalten bleiben; Staging-Debug-Tests übergeben `user_id=default` explizit — bleiben gültig)

### Open Questions
- [ ] (PO, bei Spec-Freigabe) Konto `default` bleibt gültig; nur der Rückfall wird verboten — Abweichung vom Issue-Wortlaut.
