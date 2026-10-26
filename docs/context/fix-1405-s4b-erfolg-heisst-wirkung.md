# Context: fix-1405-s4b-erfolg-heisst-wirkung

## Request Summary
#1405 Scheibe S4b: Die letzten 8 Einträge in `KNOWN_VIOLATIONS` von
`tests/test_success_status_guard.py:1531-1626` reparieren („Erfolg heißt Wirkung"),
außerhalb der Befehlsverarbeitung (die war S4a). Nicht im Umfang: die 22 Funde des
Auflösungs-Wächters (`test_resolution_loss_guard.py`) und S3 — eigene Folgescheiben
im selben Ticket.

## Die 8 Fundstellen

| # | Schlüssel | Klasse | Befund | Aufrufer |
|---|-----------|--------|--------|----------|
| 1 | `api/routers/scheduler.py::trigger_compare_alert_checks` (B3) | 1 constant_success | `failed` wird gezählt, `"status": "ok"` fest (`:154`) | Go `scheduler.go:859` → `triggerEndpointForUser` (`:1137-1203`) — wertet `failed>0` SCHON als error (`:1176`), `partial` → `partialRunError` |
| 2 | `api/routers/scheduler.py::trigger_inbound` (B7) | 1 | fest `{"status":"ok","count","processed"}` (`:205-223`); skipped/busy korrekt | Go `push_kick.go:63` → `triggerGlobalEndpointRes` (`scheduler.go:1218-1243`) liest NUR `processed`/`busy` (`fillPollResult :1246`) |
| 3 | `src/services/inbound_email_reader.py::poll_and_process` (B19) | 2 partial_success_blind | `except` nur `logger.error` (`:169`), IMAP/OSError ebenso (`:171-174`), `return processed` | nur `scheduler.py:221` |
| 4 | `notification_service.py::_send_telegram_incomplete_hint` (B21) | 4 unacknowledged_dispatch | `-> None`, fail-soft (`:935-951`) | `send_trip_report :898`, `_dispatch_alert_message :2130` |
| 5 | `notification_service.py::send_command_reply_email` (B21) | 4 | `-> None` (`:2204-2216`) | `inbound_email_reader.py:243` (trip_not_found), `:267` |
| 6 | `notification_service.py::_send_service_error_email` (B21) | 4 | nacktes `return` (`:2411-2434`) | nur `send_trip_report :906` |
| 7 | `trip_report_scheduler.py::send_reports` (B17) | 2 | `sent_count` ohne Gegenzähler (`:701-737`) | **keine Produktionsaufrufer** — nur Docstring `:673` + `tests/e2e/test_e2e_story3_reports.py:455-464` (live/email); Spec nennt es toten Code |
| 8 | `trip_report_scheduler.py::_process_pending_markers` | 2 | `delivered += 1` nur bei `outcome=="sent"` (`:1029`, `:1065`), kein Gegenzähler | `dispatch_orchestrator.py:76` `TripDispatchStrategy.pre_pass`: `self._sent += …` |

## Wichtige Detail-Befunde
- **#3:** `_process_single_inner` fängt Verarbeitungs-/Versandfehler selbst ab
  (`inbound_email_reader.py:262-273`, `return 0`, Seen im `finally`). Ein Gegenzähler nur im
  äußeren `except` sähe diese Fehler nie → Rückgabe von `_process_single` muss Fehler signalisieren.
- **#5:** Ein `bool` aus `send_command_reply_email` kann direkt in den B19-Gegenzähler fließen
  (Antwort an den Nutzer nicht zugestellt = Fehler des Laufs).
- **#2:** Ohne Go-Änderung bliebe ein neues `failed`/`partial` in `/api/scheduler/status`
  unsichtbar. Vorbild Go: `triggerPremiumSmsPollEndpointRes` (`scheduler.go:941-985`).
  Kommentar `:935`: `triggerGlobalEndpoint` soll für inbound_command_poll unverändert bleiben →
  eigener Pfad in `pollRun` (`push_kick.go:59-64`). Kick/Retry hängt nur an `Processed`/`Busy`
  (`kickRound push_kick.go:152-169`) — ein Fehlerfeld löst keine Nachversuche aus.
- **#8:** Outcome-Werte: `already_in_progress :1433`, `no_stage :1660`, `no_weather :1814`,
  `no_channels :2134`, `channels_unreachable :2146`, `sent :2147`. Einordnung wie `dispatch_one`
  (`dispatch_orchestrator.py:78-106`): sent → sent, `no_channels`/`no_stage` neutral, Rest failed.
  `already_in_progress` gesondert entscheiden.
- **#7:** Löschen statt reparieren zulässig (Präzedenz B13/#1407). Mitziehen:
  `tests/tdd/test_pytest_collection_and_timeout_safety.py:171` (Zähl-Anker live-Tests),
  `tests/tdd/test_issue_339_verify_timing.py:133`, `docs/specs/modules/trip_report_scheduler.md`.

## Scanner-Bedingungen (was der Code erfüllen muss)
- Klasse 1 (`_asserts_constant_success :721`): Statuswert aus Variable statt Literal genügt.
- Klasse 2 (`:895-1023`): lokaler Name im **except-Handler** hochgezählt UND im `return`
  (`_failure_counter_names :567` ∩ `_returned_names :492`). `self.x += 1` zählt nicht;
  ein `elif`/`else`-Zweig zählt laut Implementierung NICHT (Docstring `:927` sagt anders —
  in der Analyse gegenprüfen, ggf. ist ein Wächter-Fehler zu korrigieren statt umzugehen).
- Klasse 4 (`:1182-1300`): raus, wenn Funktion `bool` liefert, im Handler wirft oder Zustand ändert.
  S4a AC-17: `return` ohne Auswertung beim Aufrufer = verbotene Umgehung (Präzedenz #1459:
  Rückgabe UND Verwertung).

## Anker im Wächter, die mitgezogen werden
- `SPEC_LISTED_FINDINGS` (`:1718-1786`) hält 7 der 8 (ohne `_process_pending_markers`);
  Längenanker `:1838` `== 7`/`sum == 7` → nach S4b 0/0 bzw. umformulieren.
- AC-18 `inbound_expected` (`:1891-1904`) fest auf B19 → entfernen.
- `test_known_violations_only_shrink` (`:1943`) meldet stale Einträge rot;
  `test_no_unlisted_success_status_findings` (`:1907`) neue Funde.
- `INTENTIONAL_CONSTANT_SUCCESS` hat Wachstumssperre (`:3315`) — keine neuen Ausnahmen.
- Header-/Docstring-Zahlen `:1490-1530`, `:1655-1716`, `:1793-1800`, `:1225-1240`, `:1580-1600`.

## Existing Patterns
- `trigger_trip_reports` (`scheduler.py:91`), `trigger_compare_presets_daily` (`:286`):
  `status = "partial" if failed > 0 else "ok"`, HTTP 200.
- `trigger_inbound_sms` (`:226-267`) + `inbound_sms_reader.py:186-190`:
  Helfer liefert `(learned, failed, rejected)`, Reader setzt `self.last_failed_count`,
  Router → `status="partial"` + `failed`.
- `run_briefing_dispatch` (`dispatch_orchestrator.py` ~`:230-270`): Strategie `_sent`/`_failed` → `(sent, failed)`.
  Compare-`pre_pass` (`:173-187`): `self._failed += …`.
- #2217: lokaler `failed`-Zähler je Einheit + `report_unit_failure(label, id)` (`alert_check_state.py:114`).
- `send_command_reply_telegram` liefert `int | None` (`notification_service.py:2244`).

## Dependencies
- Upstream: `EmailOutput`, `TelegramOutput`, IMAP, `send_test_report_outcome`-Outcomes.
- Downstream: Go-Scheduler (`internal/scheduler/scheduler.go`, `push_kick.go`), `/api/scheduler/status`
  (`last_run.status ok|partial|error`, api_contract `:1603`), Monitoring
  `henemm-infra/scripts/check-gregor20.sh:185-206` (alarmiert bei `error`; `trip_reports_hourly`
  und `compare_presets_daily` sofort, sonst ab Streak 2; `partial` wird nicht ausgewertet).

## Existing Specs
- `docs/specs/modules/feat_1405_s4a_befehlsantwort_erfolg_wirkung.md` — Vorlage (AC-Stil A–F,
  Ratschen-AC mit Anker-Zahl, Anti-Gaming-AC, Mutations-AC, echte Eingänge, benannte Alt-Test-Änderungen).
- `docs/specs/modules/waechter_1405_erfolg_wirkung.md` — Changelog je Scheibe (`:833` S4a).
- `docs/specs/modules/fix_1405_s1_alarm_zustellung.md`, ADR-0086 (sent = zugestellt;
  `failed_channels` speist Backoff — Vorsicht bei B21-Hinweisen).
- `docs/reference/api_contract.md`: compare-alert-checks `:1958-1965` (partial nur deadline
  dokumentiert), `/inbound-commands` ohne dokumentierte Antwortform (`:1492`).

## Betroffene Tests (Auswahl)
- #1: `test_compare_alert_checks_faltet_amtliche_warnungen.py`, `test_scheduler_run_duration_reporting.py:116`,
  `test_issue_1169_compare_alert_consumer.py:816`, `test_alarmlauf_einheit_abschottung.py`
- #2/#3: `test_scheduler_triggers.py:62-90`, `test_inbound_poll_lock.py:302,379`, `test_inbound_gate_errors.py`,
  `test_issue_1009_1019_inbound_robustness.py`, Staging-Fakes `test_staging_messlauf.py:534`; Go `scheduler_kick_test.go` u. a.
- #5: Fakes `-> None` in `test_inbound_reader_no_default_settings_lookup.py:129`,
  `tdd/test_inbound_unresolved_sender_no_default.py:128`, `tdd/test_inbound_email_sender_authentication.py:173`,
  `test_befehl_antwortzeit.py:1516`
- #4: `tests/tdd/test_telegram_recipient_contract.py:815-831`; #6: `tests/unit/test_provider_error_handling.py:210-220`
- #8: `test_briefing_anchor_survives_dispatch_failure.py:1469`, `test_issue_1012_no_data_guard.py:458-610`,
  `test_dispatch_orchestrator.py:346`

## Risks & Considerations
- **Monitoring-Lärm (#8):** neues `failed` aus Nachlieferungen macht `trip_reports_hourly` zu `error`
  → Sofort-Alarm. Outcome-Einordnung (`no_weather`, `already_in_progress`) bewusst festlegen.
- **Monitoring (#2/#3):** wertet Go inbound künftig aus, wird ein IMAP-Ausfall alle 5 Min zu error
  (Alarm ab Streak 2) — gewollt, aber neu; Infra-Monitor ggf. anpassen (Instanz `infra`).
- **Keine Retry-/Doppelversand-Kopplung:** Seen wird im `finally` gesetzt; Marker vor Versand entfernt.
  Status darf keinen Retry auslösen.
- **B21-Semantik:** Hinweis-/Fehlermail-Fehlschlag nicht blind in `failed_channels` (ADR-0086:
  speist Backoff) — eigene Verwertung festlegen.
- **Anti-Gaming:** Reparatur muss die Zusicherung dort prüfen, wo sie wirkt (Aufrufer-Verwertung),
  nicht nur den Scanner beruhigen.
- Multi-User: alle Pfade laufen je Nutzer; keine `default`-Fallbacks einführen.

## Analysis

### Type
Feature (Reparatur-Scheibe im Wächter-Epic #1405, keine Nutzer-Funktion neu)

### Affected Files (with changes)
| File | Change Type | Description |
|------|-------------|-------------|
| `tests/test_success_status_guard.py` | MODIFY | Wächterfehler Klasse 2 korrigieren (s. u.), `KNOWN_VIOLATIONS` 8 → 0, `SPEC_LISTED_FINDINGS`/Längenanker `:1838`, AC-18 `inbound_expected`, Header-Zahlen |
| `api/routers/scheduler.py` | MODIFY | #1 `trigger_compare_alert_checks`: `status = "partial" if failed else "ok"`; #2 `trigger_inbound`: `failed` + `status` aus Reader |
| `src/services/inbound_email_reader.py` | MODIFY | #3 Gegenzähler bis in `_process_single_inner`; `last_failed_count` |
| `src/services/notification_service.py` | MODIFY | #4/#6 `-> bool` + Verwertung beim Aufrufer; #5 `send_command_reply_email -> bool` |
| `src/services/trip_report_scheduler.py` | MODIFY | #7 `send_reports` löschen; #8 `_process_pending_markers -> (delivered, failed)` |
| `src/services/dispatch_orchestrator.py` | MODIFY | `TripDispatchStrategy.pre_pass`: `self._failed += f` |
| `internal/scheduler/push_kick.go`, `scheduler.go` | MODIFY | #2 eigener inbound-commands-Pfad in `pollRun`, Spiegel von `triggerPremiumSmsPollEndpointRes` (:941-985) |
| Alt-Tests/Fakes (Liste oben „Betroffene Tests") | MODIFY | Fakes `send_command_reply_email` → `True`; Staging-Fake `last_failed_count`; `send_reports`-Test + Zähl-Anker 13→12 (`test_pytest_collection_and_timeout_safety.py:171`), `test_issue_339_verify_timing.py:133` |
| `docs/specs/modules/trip_report_scheduler.md`, `docs/reference/api_contract.md`, `docs/specs/modules/waechter_1405_erfolg_wirkung.md` | MODIFY | `send_reports` raus; `partial`/`failed` für compare-alert-checks + `/inbound-commands`; S4b-Changelog |

### Scope Assessment
- Dateien produktiv: ~7 (Python 5, Go 2)
- Geschätzte LoC produktiv: ~+150/−50 (netto unter 250; falls drüber: `loc_limit_override 500`, KEINE Abspaltung)
- Risk Level: MEDIUM (Monitoring-Wirkung neu, viele Alt-Tests/Fakes; Versandpfade selbst unverändert)

### Technical Approach (je Fundstelle, entschieden)
- **Wächter-Korrektur zuerst (bestätigter Wächterfehler):** `_failure_counter_names` (`:567-580`) liest nur `except`-Handler,
  Docstring `:925-930` verspricht auch „Fehlausgangs-Zweig". Korrektur: zusätzlich gilt ein Zähler, der im `orelse` eines `if`
  hochgezählt wird, dessen Rumpf einen Geschwister-Erfolgszähler erhöht. Beliebiges `else: failed += 1` genügt NICHT.
  AC-8-Attrappe (`failed = 0`, nie erhöht) bleibt Fund. Positiver + negativer Selbsttest. Kein künstliches try/except (= Gaming).
- **#1:** Statusvariable statt Literal, wie `trigger_trip_reports`. Go wertet `failed>0` schon als error (`scheduler.go:1176`) → keine Go-Änderung.
- **#2:** Router liefert `failed` + `status` (`partial` bei failed). Go: `pollRun` (`push_kick.go:59-64`) bekommt eigenen inbound-commands-Zweig
  (`fillPollResult` + `Failed>0` → error, `partial` → `partialRunError`); `triggerGlobalEndpoint` bleibt unverändert (Kommentar `:935`).
  Bestätigt: Kick/Retry hängt nur an `Busy`/`Processed` (`kickRound :152-169`) → Fehler löst KEINEN Nachversuch/Doppelversand aus.
  Python zuerst, Go danach (Go fehlendes Feld = 0, abwärtskompatibel).
- **#3/#5:** `_process_single` liefert `(processed, failed)`; `failed += 1` im inneren Handler (`:262-273`), bei nicht zugestellter
  Befehlsantwort (`send_command_reply_email -> bool`, inkl. trip_not_found `:243`) und in den IMAP-/OSError-Handlern (`:171-174`) —
  sonst bleibt ein IMAP-Ausfall stumm. `poll_and_process` bleibt `-> int`, setzt `self.last_failed_count` (Muster `inbound_sms_reader :186-190`).
  Router liest das Attribut genau wie `trigger_inbound_sms` (KEIN `getattr(..., 0)`-Stillrückfall im Produkt; Fakes setzen es selbst).
  Fehlende Zugangsdaten bleiben `skipped`, kein Fehler. `can_send_email()` falsch = kein Versuch = kein Fehler.
- **#4/#6 (B21):** `-> bool`. Verwertung: neues Feld in `NotificationResult` (Hinweis-/Fehlermail-Fehlschlag), das der
  Briefing-Lauf auswertet und als `failed`/`partial` des Laufs sichtbar macht. **`failed_channels`/Backoff (ADR-0086) bleiben unberührt**
  (Briefing selbst zugestellt). Ein Feld ohne Leser = verbotene Umgehung (S4a AC-17, #1459) → Spec muss den Leser und die Stelle,
  wo es sichtbar wird, benennen und testen; Test: `failed_channels` bleibt bei Hinweis-Fehlschlag leer. Besonders #6: scheitert die
  Service-Fehlermail, hat der SMS-only-Nutzer weder Briefing-Daten noch Erklärung → muss im Lauf sichtbar werden.
- **#7:** `send_reports` ist toter Code (keine Produktionsaufrufer) → löschen (Präzedenz B13/#1407) inkl. Mitziehliste oben.
- **#8:** `_process_pending_markers -> (delivered, failed)`, outcome-basiert an beiden Sendestellen (`:1029`, `:1065`).
  Einordnung wie `dispatch_one` (`dispatch_orchestrator.py:99-104`): `sent` → delivered; `no_channels`/`no_stage` neutral;
  `no_weather`/`channels_unreachable` → failed.

### Entscheidungen (Tech Lead, Begründung am Code geprüft)
- **`already_in_progress` tritt in #8 gar nicht auf:** Der Lock sitzt nur in `send_test_report_outcome` (`:1433`, Test-Versand-Knopf);
  die Nachlieferung ruft `_send_trip_report_outcome` direkt. Kein Marker-Verlust-Restrisiko in dieser Scheibe; die Plan-Agent-Sorge entfällt.
- **Kein stündlicher Fehlalarm bei Wetterdienst-Störung:** Liefert ein zuvor fehlendes Segment weiterhin keine Daten, wird gar nicht
  gesendet (`:1035-1042`, `attempts += 1`, Lärmschutz #1012) → kein Outcome, kein Zähler, neutral. `failed` entsteht nur bei echtem
  gescheitertem Nachliefer-Versand — genau das muss sichtbar sein (verpasstes Briefing = Schaden, vgl. Kommentar `check-gregor20.sh:180-185`).
- **IMAP-Ausfall (Inbound-Befehle) alarmiert ab 2. Lauf in Folge:** gewollt — stummer Ausfall der Befehlsverarbeitung ist genau der
  Defekt-Typ von #1405. `check-gregor20.sh:187-206` iteriert über ALLE Jobs, `inbound_command_poll` ist damit ohne Infra-Änderung
  erfasst (Streak ≥ 2); `partial` wertet das Monitoring nicht aus. **Keine Infra-Änderung nötig.**

### Dependencies
- Reihenfolge: Wächter-Korrektur (RED #8) → Python #1, #7, #8+Orchestrator, #4/#6, #3/#5 → Router #2 → Go #2 → Ratsche leeren, Anker, Docs.
- Downstream: `/api/scheduler/status`, `check-gregor20.sh` (unverändert), api_contract.

### Open Questions
- keine für den PO (fachliche Folgen oben als Entscheidung festgehalten; Freigabe erfolgt mit den ACs in /30)
- Für die Spec zu klären: genaue Leser-Stelle des B21-Feldes im Briefing-Lauf (`send_outcomes.py:55` / `_send_trip_report_outcome`) und ob `_dispatch_alert_message :2130` dasselbe Feld in die Alarm-Bilanz führt.
