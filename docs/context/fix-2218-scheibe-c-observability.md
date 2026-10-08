# Context: fix-2218-scheibe-c-observability

## Request Summary
#2218 Scheibe C: die sechs verbleibenden Observability-Einträge (C5-53, C5-15, C5-37, B2-71, C5-47, C5-02) schließen, damit #2218 vollständig erledigt ist (Epic #2505 „Erfolg heißt Zustellung, nichts geht still verloren"). Repo-Stand: nach Scheibe B (`25b514327`).

## Vorbild-Muster aus Scheibe A + B
- Spec A: `docs/specs/modules/dispatch_orchestrator.md` (v1.1) — Status aus Zustellung, `tests/test_dispatch_status_delivery.py`
- Spec B: `docs/specs/modules/fix_2218_alarm_ausfaelle.md` — Out-of-Scope (Z.231) nennt exakt diese sechs Einträge
- Health-Journal: `src/providers/enrichment_health.py:55` `log_enrichment_call(path, outcome, detail=None, unit=None)` → `data/diagnostics/enrichment_calls.jsonl`; Ausgänge `ok/fallback/unavailable/self_throttled`
- Go-Leser: `internal/scheduler/enrichment_health.go` (`failedUnits()` Z.57, `EnrichmentHealth()` Z.184) → `/api/scheduler/status` `enrichment_health.<path>.failed_units`
- **Doku-Lücke aus B:** `docs/reference/api_contract.md` (Abschnitt `GET /api/scheduler/status` Z.1359-1505) kennt weder `failed_units` noch Pfad `alert_fetch` → in C nachziehen

## Einträge

### C5-53 — Mail-Erfolg ohne Message-ID im Log (besteht)
| Datei | Relevanz |
|---|---|
| `src/output/channels/email.py` `build_mime_message` (~309-345) | setzt keine `Message-ID` (nirgends `make_msgid` im Repo) |
| `src/output/channels/email.py` `_dial_and_send` (~493-535) | verwirft Rückgabe von `sendmail` (Z.503/509) |
| `src/output/channels/email.py` `send()` (~868-870) | Erstversuch-Erfolg loggt nichts; nur `attempt>0` bzw. `[SMTP-FALLBACK]` (Z.602/932) |
| `src/services/trip_report_scheduler.py:1767`, `:479` | Sammelzeilen belegen nur SMTP-Annahme |
| `src/services/scheduler_dispatch_service.py:571` | Compare-Zeile |
- Muster: `email.utils.make_msgid()` in `build_mime_message`, dieselbe ID in Erfolgszeile; Empfänger maskiert via `mask_addr_for_pii_log` (#2157)
- Tests: `tests/tdd/test_mail_transport_dial_behaviour.py`, `test_mail_send_deadline.py`, `test_mail_fallback_guard.py`, `test_927_smtp_fallback.py`, `test_issue_457_email_per_recipient.py`, `test_egress_single_dial_point.py`, `test_issue_766_smtp_retry.py`, `tests/unit/test_briefing_recipient_logging.py`
- Achtung: Mail-Inhalts-Datei → Renderer-Commit-Gate; Validatoren lesen `X-GZ-*`-Header

### C5-15 — `running` hartkodiert `true` (besteht)
- `internal/scheduler/scheduler.go:1377`; `Start()` Z.334 / `Stop()` Z.340 merken keinen Zustand; robfig/cron hat keinen Getter → eigenes Flag (Mutex/atomic)
- Leser: `/home/hem/henemm-infra/scripts/check-gregor20.sh:170` (`not running` ⇒ harter Alarm „Scheduler nicht aktiv"); Go-Test `internal/scheduler/scheduler_test.go:185-187` (prüfen, ob dort `Start()` läuft); `briefing_health_test.go:530`; Frontend nur Test-Payload
- Risiko: falsche Verdrahtung ⇒ Prod-Alarm in check-gregor20; Staging ohne laufenden Scheduler meldet künftig `false` (gewollt — ist das in check-gregor20 für Staging relevant?)

### C5-37 — leere INCA-Antwort journalt `ok` (besteht)
- `src/services/radar_service.py` `_fetch_geosphere_inca` Z.879; leer-Zweig ~Z.892 setzt `_inca_unavailable_this_call` nicht (nur `except` Z.911); Journal Z.606-616 bucht `OUTCOME_OK`; Reset Z.483/552
- Nicht verwechseln: `_offline_fixture_active()` → `[]` (Z.883) darf kein Fallback werden
- Vorbild: #1658 S2, `_openmeteo_unavailable_this_call`
- Leser: Go `radar_nowcast.last_fallback_at/_detail`; check-gregor20 Block 2e-e (Z.778ff); Tests `tests/tdd/test_radar_inca_fallback_journal.py`, `test_inca_fehlerstatus_journal.py`, `test_radar_nowcast_health_journal.py`; api_contract Z.1502 (fallback nur HTTP-Fehler beschrieben)

### B2-71 — Nowcast-Mitschnitt verdrängt sich selbst (besteht)
- `src/services/alert_input_capture.py`: `_MAX_FILES_PER_DIR=50` (Z.32), `_prune` verzeichnisweit (Z.41); Dateiname `{_safe_key(source_key)}_{ts}.json` (Z.112-113), `_safe_key` ≤80 Zeichen, kann `_` enthalten
- Nowcast-Key `radar_service._nowcast_source_key` (Z.1405) = `lat_lon_region`; Aufruf auch bei Cache-Treffer (Z.572) → zusätzliches Volumen
- Mitbetroffen bei globaler Änderung: Zweig b `warn_egress.py:494`, Zweig a `trip_alert.py:817`
- Leser: `latest_capture_id()` (Z.126, liest alle Dateien, filtert `source_key`) ← `trip_alert.py:2753` → `capture_id` im `alert_log`
- Vorbild: `weather_snapshot._prune_dated_snapshots(trip_id)` (Z.198) pro Schlüssel
- Tests: `tests/unit/test_alert_input_capture_retention.py` (nagelt 50/Verzeichnis fest), `..._failopen.py`, `..._payload_schema.py`, `test_alert_log_capture_correlation.py`, `test_radar_service_capture.py`, `test_warn_egress_capture_*.py`; Spec `docs/specs/modules/alarm_eingangsprotokoll.md`
- Risiko: ohne Gesamtobergrenze/Alterslimit unbeschränktes Plattenwachstum

### C5-47 — `implausible_measurement` ungedämpft (besteht, laut Docstring bewusst)
- `src/services/track_resolution.py:213-234` `_melde_unplausible_messung`, Aufruf Z.342 **vor** `_failed_lookups`-Check (Z.345) → jede 15-Min-Runde eine Zeile
- Ziel-Journal: `users/<uid>/diagnostics/track_resolution_failures.jsonl` (`track_resolution_health.py:38/65`)
- Leser: `internal/scheduler/briefing_health.go` ~203-290 (`track_resolution_failure_streak_since`, `..._recent_count` 24h, Lücke 26h Z.226 — Kommentar Z.215-225 setzt Dämpfung beim Schreiber voraus); check-gregor20 Z.586-625
- Vorbild: `_failed_lookups: set` (Z.201) — einmal pro (user,trip,stage) und Prozess
- Tests: `tests/tdd/test_track_resolution_failure_visibility.py`, `test_track_resolution_legacy_trip.py`, `briefing_health_test.go`

### C5-02 — Alarm-Pfad im Betrieb blind (teilweise)
- Heute: Go-Cron ruft fünf Python-Alarm-Endpunkte (`scheduler.go:783-813`; Python `api/routers/scheduler.py:71/98/135/145/157`); Go-Router Admin-Proxy nur für `trip-reports`, `alert-checks`, `inbound-commands` (`internal/router/router.go:324-328`); Debug-Trigger nur `GZ_ENV=staging`; Scheibe B journalt `alert_fetch` mit `unit`
- Fehlt: (a) Admin-Proxy für radar-alert-checks, compare-alert-checks, compare-radar-alert-checks, compare-official-alert-checks; (b) Fenstergrenze wird nirgends geloggt (`src/app/day_window.py` ohne Logger, `trip_segments.py:209-210/336`, `trip_alert.py` `_delta_event_window` Z.150 / `aufenthaltsfenster_min` Z.228); (c) Trip-Nowcast `radar-alert-checks` bucht kein `alert_fetch` mit `unit`
- Achtung: Routen-Zählung `api_contract.md` Z.266 + evtl. Router-Zähltest; `tests/unit/test_ziel_segment_anzeige_invarianz.py` bewacht Trennung Alarm-/Anzeigefenster (#1599)

## Dependencies
- Upstream: smtplib/email.utils, robfig/cron, GeoSphere-INCA-Provider, Health-Journal
- Downstream: `/api/scheduler/status` (Go), `check-gregor20.sh` (henemm-infra, live aus dem Arbeitsbaum!), Mail-Validatoren, Alarm-Log `capture_id`

## Risks & Considerations
- Umfang: sechs Einträge, Go + Python — LoC-Limit 250 vermutlich überschritten ⇒ Zuschnitt in der Analyse entscheiden (ggf. `loc_limit_override`)
- C5-15 und C5-37 ändern Signale, die check-gregor20 auswertet ⇒ Infra-Gegenstück prüfen (Staging-`running=false`, mehr `fallback`-WARN)
- C5-53 berührt Mail-Inhalts-Datei ⇒ Renderer-Commit-Gate, Validator-Lauf
- C5-02 ist der unschärfste Eintrag — Zuschnitt (a)/(b)/(c) in der Analyse festlegen
- B2-71: Prune-Änderung wirkt auf alle drei Capture-Zweige

## Analysis

### Type
Bug (Observability-Lücken, Sammel-Issue #2218 Scheibe C, Epic #2505) — alle sechs Einträge in EINER Spec, kein Abspalten.

### Affected Files (with changes)
| File | Change Type | Description |
|------|-------------|-------------|
| `internal/scheduler/scheduler.go` | MODIFY | C5-15: `atomic.Bool` in `Start()`/`Stop()` setzen, `Status()` (Z.1377) liest Flag statt `true` |
| `internal/scheduler/scheduler_test.go` | MODIFY | C5-15: `running=false` vor `Start()` und nach `Stop()` |
| `internal/router/router.go` | MODIFY | C5-02a: 4 Admin-Proxy-Routen (radar-, compare-, compare-radar-, compare-official-alert-checks) neben Z.324-328 |
| `internal/router/admin_trigger_test.go` | MODIFY | C5-02a: `triggerPfade` (Z.35-39) erweitern; `core_auth_sweep_test.go` zählt mit (`minPythonCallsReached=24`, Ist 27) |
| `src/services/trip_alert.py` | MODIFY | C5-02b: eine Logzeile je Alarmprüfung mit Trip-ID, Fenster start/ende, Quelle (Δ-Zweig Z.843, Radar-Zweig Z.2127); C5-02c: `alert_fetch` `unavailable`+`unit` im Nowcast-Ausnahmezweig (~Z.2167) |
| `src/services/radar_service.py` | MODIFY | C5-37: leer-Zweig Z.892 setzt `_inca_unavailable_this_call = True` + WARN |
| `src/services/alert_input_capture.py` | MODIFY | B2-71: `_prune` pro `source_key` (Key = Dateiname ohne `_`+21-Zeichen-Zeitstempel) + Gesamtdeckel je Verzeichnis |
| `src/services/track_resolution.py` | MODIFY | C5-47: zeitbasierte Dämpfung je (user,trip,stage), Intervall < 26h (Vorschlag 12h); Docstring korrigieren |
| `internal/scheduler/briefing_health.go` | MODIFY (Kommentar) | C5-47: Kommentar Z.215-225 an neue Dämpfung anpassen |
| `src/output/channels/email.py` | MODIFY | C5-53: `Message-ID` via `make_msgid(domain="henemm.com")` in `build_mime_message`; Erfolgs-Logzeile auch beim Erstversuch mit ID + maskiertem Empfänger |
| `docs/reference/api_contract.md` | MODIFY | `failed_units`, Pfad `alert_fetch` (Lücke aus B), `fallback` bei leerer INCA-Antwort, Routenzahl Z.266 |
| Tests | MODIFY/CREATE | `test_alert_input_capture_retention.py` (nagelt 50/Verzeichnis fest → neu), `test_track_resolution_failure_visibility.py`, `test_radar_inca_fallback_journal.py`, Mail-Tests, neue Verhaltens-Testdateien |

### Befunde (verifiziert)
- **C5-15:** Prod startet Scheduler in `cmd/server/main.go:109-112` vor `router.New` (Z.114); Staging hat ihn per `scheduler_gate.go:12` aus ⇒ `running=false` dort korrekt. `check-gregor20.sh` fragt nur Prod (8090) ⇒ kein Fehlalarm, kein Infra-Gegenstück. Weitere Leser (`briefing_health_test.go:530`, `status_token_test.go:168`) prüfen nur Typ/Präsenz. `scheduler_test.go:180` ruft `Start()` vor `Status()`.
- **C5-37:** Trockenes Wetter liefert KEINE leere Liste (Nullwerte → Trockenframes, Z.896-897); `ts.data` leer nur bei kaputter Antwort ohne Zeitstempel ⇒ kein Fehlalarm-Risiko. Flag wird nur im Journal (Z.613) gelesen ⇒ reine Observability, keine Provider-Umschaltung. Offline-Fixture-Zweig (Z.882) bleibt unberührt.
- **B2-71:** Zeitstempel `%Y%m%dT%H%M%S%f` fest 21 Zeichen am Dateiende ⇒ Key sicher abtrennbar trotz `_` im Key. `latest_capture_id` filtert per JSON-`source_key`, unabhängig vom Prune. Wirkt auf Zweige a (`trip_alert.py:817`) und b (`warn_egress.py:494`) mit.
- **C5-47:** Die Vorgänger-Spec `fix_2073_s2_sichtbarer_fehlschlag.md:252-256` hat die Dämpfung ausdrücklich als „eigene Scheibe" ausgelagert ⇒ kein Bruch einer Entscheidung, sondern genau diese Scheibe. Leser: `check-gregor20.sh:611-621` schwellt nach Streak-Alter (48h), `recent_count` ist nur Anzeige ⇒ Dämpfung senkt keinen Alarm unter Schwelle. Prozess-Dämpfung (Set) würde den Streak nach 26h abreißen ⇒ zeitbasiert < 26h.
- **C5-53:** `build_mime_message` wird je `send()`-Aufruf gebaut (`email.py:797`); ob je Empfänger eigene ID → in Spec festnageln (#457 per-recipient). Kein Test vergleicht Header-Sets gefunden.
- **C5-02:** „Debug-Trigger nur Staging" wird durch (a) erledigt (Admin-Proxy auf Prod für alle fünf Alarm-Endpunkte). (c) gehört in den Scope (Nowcast-Ausfall journalt heute nichts mit `unit`), nicht optional. Logzeile (b): `_delta_event_window` einmal je Trip-Prüfung; Radar-Zweig Z.2127 liegt in einer Schleife je Segment ⇒ in der Spec festlegen, dass genau eine Zeile je Prüfung/Segment entsteht und keine Fenster-Logik verändert wird (`test_ziel_segment_anzeige_invarianz.py`, #1599).

### Scope Assessment
- Files: ~8 produktiv (2 Go, 5 Python, 1 Go-Kommentar) + Doku + ~8 Testdateien
- Estimated LoC: produktiv ~+75/-10 (unter 250); mit Tests evtl. darüber → ggf. `loc_limit_override`
- Risk Level: MEDIUM — viele kleine, isolierte Änderungen; einzige Verhaltensänderung mit Außenwirkung: Message-ID-Header in jeder Mail (Renderer-Commit-Gate + `briefing_mail_validator`/`email_spec_validator`)

### Technical Approach
Eine Spec, ein Workflow. Reihenfolge: Go (C5-15, C5-02a) → Python (C5-37, B2-71, C5-47, C5-53, C5-02b/c) → `api_contract.md`. Muster: kleinste Änderung am Schreiber, Leser bleiben kompatibel.

### Staging-Nachweis (vorab festgelegt)
- **C5-53:** zugestellte Staging-Mail (Wegwerf-Nutzer `gregor-test+…`) per IMAP lesen; `Message-ID` muss mit der Logzeile übereinstimmen (beweist, dass Resend die ID durchreicht). Bestmessbarer Punkt.
- **C5-15:** Staging `/api/scheduler/status` → `running=false`; Prod nach Deploy → `true` (Selftest/check-gregor20).
- **C5-02a:** Go-Admin-Trigger auf Staging 403 (kein Admin) ⇒ Nachweis über Kern-Port 8001 mit `X-GZ-Core-Auth` bzw. Prod-Admin nach Deploy; Routing über Go-Tests.
- **C5-37/B2-71/C5-47/C5-02b/c:** Staging-Daten für `hem` nicht lesbar ⇒ Kern-Tests; ehrlich `NOT_MEASURABLE_ON_STAGING` ausweisen.

### Dependencies
- Downstream: `/api/scheduler/status`, `check-gregor20.sh` (keine Änderung nötig), Mail-Validatoren (lesen `X-GZ-*`, unberührt), `alert_log.capture_id`

### Open Questions (Spec-Entscheidungen, keine PO-Fragen)
- [ ] B2-71: N je Key (Vorschlag 10) und Gesamtdeckel (Vorschlag 500) bzw. Alterslimit
- [ ] C5-47: Intervall (Vorschlag 12h)
- [ ] C5-53: eine ID je Empfänger-Versand bestätigen
