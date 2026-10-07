# Context: fix-2218-s1-dispatch-status

## Request Summary
Epic #2505, Unter-Issue #2218, Scheibe A = Eintrag **C4-53**: Der Trip-Versand meldet
`status: "ok"`, obwohl bei `channels_unreachable` niemand etwas erhalten hat. Erfolg muss aus
der Zustellung abgeleitet werden, nicht aus „kein Fehler" (Klasse #1405).

## Befund (am Code belegt, Stand origin/main 045c7bb2b)
- `src/services/dispatch_orchestrator.py:88-91` (`TripDispatchStrategy.dispatch_one`):
  `if outcome == "no_weather": self._failed += 1 else: self._sent += 1`.
  Damit zählen `no_stage`, `no_channels` und **`channels_unreachable`** als `sent`.
- `api/routers/scheduler.py:55-57`: `status = "partial" if failed > 0 else "ok"` —
  erbt die falsche Zählung. Bei `channels_unreachable` kommt `ok` zurück.
- Go-Scheduler wertet nur `failed > 0` / `status == "partial"` aus
  (`internal/scheduler/scheduler.go:809, 967`) → `last_run.status` und Heartbeat hängen daran.
  Ein falsches `ok` schaltet also Monitoring/Heartbeat ab (CLAUDE.md „Readiness statt Liveness").

## Ausgänge von `_send_trip_report_outcome` (`trip_report_scheduler.py`)
| Ausgang | Bedeutung | Heute | Soll (Vorschlag für die Spec) |
|---|---|---|---|
| `sent` | mind. ein Kanal hat zugestellt | sent | sent |
| `no_weather` | Wetterabruf komplett ausgefallen | failed | failed |
| `channels_unreachable` | Kanäle konfiguriert, keiner erreicht (`:1814-1822`), Vermerk wird freigegeben, Nachholfall | **sent** | **failed** |
| `no_channels` | nichts konfiguriert, „nichts vorgesehen" (`:1805-1808`) | sent | weder sent noch failed (neutral) |
| `no_stage` | kein passender Abschnitt (z. B. Trip beendet) | sent | weder sent noch failed (neutral) |
| unbekannter Wert | #2231: Slot gesperrt (`:672-684`) | sent | failed (ehrlich: unbekannt ≠ zugestellt) |

Designentscheidung: `no_channels`/`no_stage` sind **kein Fehler** (legitim, sonst Dauer-Alarm je
Trip ohne Kanal), dürfen aber auch nicht als „gesendet" gezählt werden → `count` ehrlich.

## Related Files
| Datei | Relevanz |
|---|---|
| `src/services/dispatch_orchestrator.py` | Zählung in `TripDispatchStrategy.dispatch_one` (Kern der Änderung) |
| `api/routers/scheduler.py:25-58` | Statusableitung `/trip-reports`; ggf. Antwort um neutrale Zählung erweitern |
| `src/services/trip_report_scheduler.py:97-103, 623-690, 1800-1823` | Ausgangswerte, `VERMERK_AUSGAENGE`, Freigabe-Logik |
| `internal/scheduler/scheduler.go:809, 915-970` | Go liest `failed`/`status` — Antwortschema darf nicht brechen |
| `docs/specs/modules/dispatch_orchestrator.md` | Spec, wird geändert (Version hochziehen, ACs) |
| `tests/test_success_status_guard.py` | Wächter „Erfolgsstatus wird abgeleitet" — Muster/Nachbar |
| `tests/test_scheduler_unknown_outcome_locks_slot.py` | #2231-Test, prüft unbekannten Ausgang (nicht kaputt machen) |

## Existing Patterns
- Tupel `(sent, failed)` aus der Orchestrator-Schleife, Status daraus abgeleitet (#766, #1290).
- Compare-Strategie zählt `False` aus `_dispatch_due_preset` als failed — dort schon korrekt.
- Fehler-Isolation je Trip bleibt: Ausnahme ⇒ `failed`, Schleife läuft weiter.

## Dependencies / Dependents
- Upstream: `_dispatch_due_item` → `_send_trip_report_outcome`.
- Downstream: Go-Scheduler (`last_run`, Heartbeat, `/api/scheduler/status`), `check-gregor20.sh`
  (extern), Parallelsitzung #2217 (Stapellauf abschotten, `cron.Recover`, Phase 6) — **Berührung
  vermeiden:** #2217 arbeitet an `internal/scheduler`, diese Scheibe bleibt in Python.

## Existing Specs
- `docs/specs/modules/dispatch_orchestrator.md` (maßgeblich)
- `docs/specs/modules/trip_report_scheduler.md`, `fix_1912_scheduler_briefing_timeout.md`

## Risks & Considerations
- **Blast Radius:** `channels_unreachable` ⇒ `failed` lässt Go-Läufe künftig `partial` melden und
  den Heartbeat aussetzen. Gewollt (Epic-Ziel), aber Folgeverhalten prüfen: Dauer-`partial`, wenn
  ein Trip dauerhaft unerreichbar ist (Nachholfenster ruft stündlich erneut → mehrfach `failed`).
- `count` ändert die Bedeutung (nur echte Zustellungen) — Konsumenten von `count` prüfen.
- Zwei-Nutzer-Test Pflicht (Multi-User-Regel); Mutations-Gegenprobe: `channels_unreachable`
  wieder auf `sent` zählen muss einen Test rot machen, und zwar am Endpunkt (`/trip-reports`),
  nicht nur an der Strategie.
- Rest von #2218 (Scheiben B/C) bleibt unberührt.

## Analysis

### Type
Bug (Klasse #1405: Erfolg aus „kein Fehler" statt aus Zustellung abgeleitet)

### Affected Files (with changes)
| File | Change Type | Description |
|------|-------------|-------------|
| src/services/dispatch_orchestrator.py | MODIFY | `TripDispatchStrategy.dispatch_one`: `sent` nur bei Ausgang `sent`; `channels_unreachable` + unbekannter Ausgang ⇒ `failed`; `no_channels`/`no_stage` neutral |
| docs/specs/modules/dispatch_orchestrator.md | MODIFY | Version hoch, ACs Given/When/Then |
| tests/test_dispatch_status_delivery.py | CREATE | Endpunkt-Test `/api/scheduler/trip-reports` mit zwei Nutzern, je Ausgang |

`api/routers/scheduler.py:55-57` und `internal/scheduler/scheduler.go` bleiben unverändert: Der Router leitet `partial` aus `failed > 0` ab, Go wertet nur `Failed`/`Status` aus; `Count` fließt nur in die Fehlermeldung (Schema bleibt kompatibel).

### Scope Assessment
- Files: 3 (1 Produktivcode, 1 Spec, 1 Test)
- Estimated LoC: +25/-5 produktiv
- Risk Level: MEDIUM (Go-Läufe melden bei unerreichbaren Trips künftig `partial`, Heartbeat setzt aus — gewollt)

### Technical Approach
In `dispatch_one` explizit nach Ausgang verzweigen. `sent` ⇒ `_sent`; `no_weather`, `channels_unreachable` und jeder unbekannte Wert ⇒ `_failed`; `no_channels`/`no_stage` ⇒ weder noch. Der `pre_pass`-Nachholzähler (`_process_pending_markers`) zählt nur echte Nachlieferungen und bleibt unberührt. Mutations-Gegenprobe: `channels_unreachable` wieder als `sent` zählen muss den Endpunkt-Test rot machen.

### Dependencies
Upstream `_dispatch_due_item` → `_send_trip_report_outcome`; Downstream Go-Scheduler (`last_run`, Heartbeat), `check-gregor20.sh`. Parallelsitzung #2217 arbeitet in `internal/scheduler` — keine Berührung.

### Open Questions
- [ ] Dauer-`partial` bei dauerhaft unerreichbarem Trip (stündlicher Nachholversuch): als gewollte Sichtbarkeit in die Spec aufnehmen, kein Drosseln in dieser Scheibe.
