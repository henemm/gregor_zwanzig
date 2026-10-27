# Context: fix-2261-a2s1-alarmlauf-reihenfolge

## Request Summary
Epic #2261, Scheibe **A-2 S1**: Die Abweichungs-Alarmprüfung (`check_all_trips`) bricht bei langsamen Läufen nach 90 s ab und lässt dabei immer dieselben (nach Trip-ID hinteren) Trips aus. Prod 03.10.: 12 Läufe in 24 h mit `checked=2 skipped=2` (henning), Laufzeit 91–154 s, gehäuft um :00–:02 und :45–:47 (neue Modellläufe). Ziel: kein Trip wird systematisch ausgelassen; Zeitgrenze an die heutigen Go-Budgets angepasst.

## Related Files
| File | Relevance |
|------|-----------|
| `src/services/trip_alert.py:61-66` | `ALERT_RUN_DEADLINE_SECONDS = 90.0`; Kommentar verweist veraltet auf 120-s-Go-Timeout |
| `src/services/trip_alert.py:168-179` | `AlertCheckRunResult` (`alerts_sent`, `checked`, `skipped`, `duration_s`, `hit_deadline`) |
| `src/services/trip_alert.py:1002-1159` | `check_all_trips`: Deadline vor jedem Trip geprüft (1035-1038), Reihenfolge fest `sorted(..., key=t.id)` (1033), `checked += 1` sofort (1039, zählt auch Trips, die danach per `continue` rausfallen), `skipped = len - checked` (1138), WARNING ohne Trip-IDs (1140-1147); Docstring „every 30 minutes“ veraltet (1006, real */15) |
| `api/routers/scheduler.py:61-83` | `POST /api/scheduler/alert-checks?user_id=` → `status: partial` bei `hit_deadline`, sonst `ok`; Felder `checked/skipped/duration_s/reason` |
| `internal/scheduler/scheduler.go:190-234` | `alertBudgetJobIDs`; `alertWaitBudget=300s`, `alertRunBudget=720s`, `alertCallCap=1800s`; Client-Timeout 3000 s (217) |
| `internal/scheduler/scheduler.go:249-269` | Takte: `alert_checks` */15, Compare-Alarm/-Official */15, Radar 7,22,37,52 |
| `internal/scheduler/scheduler.go:306-496` | `runForAllUsers`, `rotateUsers` (Rotation über **Nutzer**), `runUserStep` (in-flight-Skip, `not_reached`), `callUserWithBudget` (Wartebudget, Hintergrundweiterlauf bis Deckel) |
| `internal/scheduler/scheduler.go:884-972` | `recordRun`, partial-Klassifikation (`partialRunError`), MQ-Bündelung bei Partial-Flanken |
| `src/services/alert_state.py`, `src/services/throttle_store.py` | Einzige Zeitstempel je Trip — nur nach **Versand**, nicht nach Prüfung; nicht als „zuletzt geprüft“ nutzbar |
| `tests/tdd/test_alert_run_deadline.py` | Bestehende Wächter der Zeitgrenze (siehe unten) |

## Existing Patterns
- **Fairness durch Rotation existiert bereits auf Go-Seite** für Nutzer: `rotateUsers` (scheduler.go:408-417) rotiert den Startpunkt je Lauf. Auf Trip-Ebene in Python fehlt das Pendant.
- **Zeitgrenze unter der Wartezeit des Aufrufers** (ADR-0038) und **aufruferseitige Wartegrenze, Python arbeitet weiter** (ADR-0070) — die 90 s waren aus ADR-0038 gegen 120 s abgeleitet. Seit #1912 wartet Go 300 s (Wartebudget) und läuft im Hintergrund weiter bis 1800 s.
- Kleine JSON-Persistenz mit Datei-Lock: `file_lock.acquire_exclusive` (2 s) für forecast_budget/throttle_store — Muster für einen eventuellen persistierten Prüfzeitstempel/Rotationszähler je Nutzer.
- Fail-soft je Trip (official triggers, check_and_send_alerts 1099-1136).

## Dependencies
- **Upstream:** `load_all_trips(user_id)`, `check_official_alert_triggers`, `check_and_send_alerts`, Provider-Abrufe (Open-Meteo; MeteoFrance-Fallback `FETCH_DEADLINE_SECONDS=180` sprengt laut Kommentar schon heute das 90-s-Budget, `meteofrance.py:98-119`), SMTP-Sendebudget (`email.py:819-830`), Telegram-Sendeslot 30 s.
- **Downstream:** Python-Endpoint → Go-Scheduler (`triggerEndpointForUser`, partial → `lastRuns.Status`, MQ-Bündelung „Nutzer-Läufe wiederholt unvollständig“), Status-Endpoint `/api/scheduler/status`, Monitoring `check-gregor20.sh`.

## Existing Specs / ADRs
- `docs/specs/modules/fix_1447_s1_alarm_lauf_zeitgrenze.md` — Herleitung 90 s (Z. 22-31, 128-132); Z. 425-429: „keine empirisch hergeleitete Zahl“, zu knapp wäre „Folge-Befund“ → genau dieser Befund
- `docs/specs/modules/fix_1447_s2a_scheduler_ueberlappung_teilerfolg.md`
- `docs/specs/modules/fix_1912_scheduler_briefing_timeout.md` — 120 s → 3000 s
- `docs/specs/modules/fix_2149_scheduler_budget_teilb.md` — Budgets, Rotation (Abschnitt 7/8, Z. 293-297: Wartebudget „gemessen 91-308 s“)
- `docs/adr/0038-zeitgrenze-je-nutzerlauf-unter-aufrufer-wartezeit.md`, `docs/adr/0070-aufruferseitige-wartegrenze-je-nutzeraufruf.md`
- ADR-0074 betrifft MeteoAlarm-Feed-Raster, nicht den Alarm-Takt (relevant erst für S3)
- Keine Spec für A-2 vorhanden; S4-Entwurf `alarm_latenz_zusage.md` existiert im Worktree nicht (laut Issue-Kommentar nur Entwurf)

## Tests, die betroffen sein können
- `test_alert_run_deadline.py`: Helper `_setup_slow_trips` (194-226, Monkeypatch mit Schlafzeit, Konstante 0.08 s, IDs `trip-0..n`); AC-1 (`checked == len(calls)`), AC-2 (Endpoint `partial`), voller Lauf `skipped == 0`, Logs; AC-7 (474-496) verlangt `ALERT_RUN_DEADLINE_SECONDS >= 60` und Monkeypatch-Änderbarkeit. Reihenfolge wird **nicht** geprüft. Zählsemantik-Änderungen berühren AC-1/AC-2.
- 17 weitere Python-Testdateien nutzen `check_all_trips` (meist nur `.alerts_sent`).
- Go: `TestBudgetDefaults_MatchSpec` (720/300/1800), `TestClientTimeout_Is3000Seconds`, `job_status_partial_test.go` (Fixture mit `duration_s:90.02`) — brechen nicht, solange das Antwortformat bleibt.

## Risks & Considerations
- **Grenze anheben allein reicht nicht:** Bei echten Ausreißern (MF-Fallback 180 s je Abruf) wird auch eine größere Grenze gerissen — dann muss die Reihenfolge rotieren, damit nicht dieselben Trips dauerhaft blind sind. Fairness-Mechanik ist der eigentliche Kern.
- **Grenze vs. Go-Budgets:** Neue Grenze muss unter dem Wartebudget (300 s, ADR-0038) bleiben, sonst wertet Go den Lauf als Budgetüberschreitung und läuft zum nächsten Nutzer weiter (Überlappung). Laufbudget 720 s gilt über **alle** Nutzer — höhere Python-Grenze verbraucht mehr davon und kann andere Nutzer in `not_reached` drücken.
- **Überlappung:** Kein Lock um `check_all_trips`; Läufe desselben Nutzers überlappen nur nach Ablauf des Deckels. Ein persistierter Rotationszustand muss mit parallelen Läufen (Radar/Compare-Jobs schreiben ihn nicht, aber zwei alert_checks nach Deckel-Ablauf) fail-soft umgehen.
- **Persistenz pro Nutzer** unter `data/users/<user_id>/` — Mandantentrennung, nie `"default"`. Neuer Zustand = neue Datei ⇒ Bestandsdaten unberührt, aber Zwei-Nutzer-Test Pflicht.
- **Zählsemantik:** `checked` zählt auch regellose/abgelaufene Trips; ein „zuletzt geprüft“-Stempel darf nur für tatsächlich geprüfte Trips gesetzt werden, sonst verschiebt sich die Fairness.
- **Beobachtbarkeit:** Übersprungene Trip-IDs werden nicht geloggt — ohne das ist der Prod-Nachweis „nicht immer dieselben“ nicht führbar.
- Veraltete Kommentare (trip_alert.py:62-65, 1006, 1010-1011) mitkorrigieren.
- S2 (Radar-Takt 5 Min, Laufbudget je Alarmart an Takt binden) und S4 (Wächter mit Endzahlen) bauen hierauf auf — S1 nicht mit deren Umfang vermischen.

## Analysis

### Type
Bug (systematische Blindstelle der Abweichungsprüfung)

### Ursache (bestätigt)
1. **Feste Reihenfolge** `sorted(trips, key=t.id)` (`trip_alert.py:1033`) + Abbruch vor dem nächsten Trip, sobald die Grenze überschritten ist (1035-1038) ⇒ bei jedem langsamen Lauf fallen dieselben (ID-hinteren) Trips weg. Das ist der eigentliche Defekt.
2. **Grenze 90 s** (`trip_alert.py:66`) stammt aus dem 120-s-Go-Timeout (ADR-0038), heute Wartebudget 300 s. Schon Normalläufe erreichen bis 88 s.
3. Auslöser der langen Läufe: Provider-Störungen zur Modelllaufzeit (Open-Meteo 503 + Retry, GeoSphere ReadTimeout + Retry), ~37-60 s je Trip im Störfall. **Retry/Backoff/Circuit-Breaker sind NICHT S1** (gehört zu S3).
- Belegzahlen: die Context-Zahlen (Prod 03.10.: 12 Läufe/24 h `checked=2 skipped=2`, 91-154 s) gelten. Der Log-Agent sah nur 2 Läufe ab 02.10. — Log-Zugriff vermutlich unvollständig, nicht übernehmen.

### Affected Files (with changes)
| File | Change Type | Description |
|------|-------------|-------------|
| `src/services/trip_alert.py` | MODIFY | Sortierung nach „zuletzt erreicht“ (älteste/fehlende zuerst, Trip-ID als Tie-Break); Zustand laden/schreiben (try/finally am Laufende); Grenzwert + Herleitungskommentar; `AlertCheckRunResult.skipped_ids`; WARNING mit übersprungenen IDs; Docstring „30 minutes“ → */15 |
| `src/services/alert_check_state.py` | CREATE | Kleiner Store `data/users/<user_id>/alert_last_checked.json` `{trip_id: ISO-UTC}`, Pfad über `app.loader.get_data_dir(user_id)` (wie `throttle_store.py:58-66`), atomar schreiben, `file_lock.acquire_exclusive`, Merge-Write `max(alt, neu)`, gelöschte Trips prunen, fail-open bei Lock-/Lesefehler (nur Fairness leidet, nie der Versand) |
| `api/routers/scheduler.py` | MODIFY | `skipped_ids` zusätzlich in die Antwort (Go dekodiert per `json.Unmarshal` ohne `DisallowUnknownFields`, `scheduler.go:799/957` ⇒ Zusatzfeld unschädlich) — macht den Nachweis „nicht immer dieselben“ auf Staging über die API messbar statt nur über Logs |
| `tests/tdd/test_alert_run_fairness.py` | CREATE | Zwei Läufe unter Grenze decken alle Trips ab; vorbelegter Zustand bestimmt Reihenfolge; Zwei-Nutzer-Isolation; neue/gelöschte Trips; Stempel auch bei Exception/regellosem Trip; Merge-Write bei zwei Schreibern |
| `docs/specs/modules/fix_2261_a2s1_alarmlauf_reihenfolge.md` | CREATE | Spec |
| `internal/scheduler/*.go` | — | unverändert (nur lesen) |

### Scope Assessment
- Files: 3 produktiv + 1 Test + Spec
- Estimated LoC: +90..+120 / -10 produktiv (Limit 250)
- Risk Level: MEDIUM — zentraler Alarmpfad, aber Änderung beschränkt auf Reihenfolge/Zustand; Alarmlogik je Trip unverändert

### Technical Approach
**Fairness: persistierter Zeitstempel „zuletzt erreicht“ je Trip und Nutzer, älteste zuerst.** Garantie: jeder Trip ist nach höchstens ⌈N/k⌉ Läufen dran (k = Trips je Lauf). Verworfen: Offset-Rotation (neue/gelöschte Trips verschieben Positionen, konkurrierende Offsets), Zufall (keine Garantie, nicht deterministisch testbar), zustandslose Rotation aus dem Viertelstunden-Slot (Garantie bricht, sobald Läufe ausfallen, im Flug übersprungen werden oder k schwankt) — der Stempel trägt auch dann.
- Stempel wird für **jeden vor der Grenze erreichten** Trip gesetzt — auch regellos, abgelaufen, per `continue` verlassen oder mit Exception (sonst blockiert ein Giftfall die Warteschlange). Konsistent mit `checked` = „erreicht“ (`trip_alert.py:1039`); Spec-Wort präzisieren statt Semantik ändern.
- Einmal schreiben am Laufende (`finally`), unter Lock, Merge mit `max(alt, neu)` — harmlos auch bei überlappenden Läufen (nur nach 1800-s-Deckel möglich).

**Zeitgrenze — Invariante statt Bauchzahl:** Die Grenze wird nur VOR einem Trip geprüft, also endet der Lauf real bei *Grenze + Dauer des zuletzt begonnenen Trips*. Invariante für die Spec: **Grenze + längster Einzel-Trip ≤ Wartebudget 300 s** (ADR-0038). Beobachtet: Überhang bis ~64 s (154 s bei 90 s Grenze), Einzel-Trip im Störfall 37-60 s; MeteoFrance-Fallback (`FETCH_DEADLINE_SECONDS=180` je Abruf, mehrere Segmente) ist KEINE obere Schranke darunter. Kandidat ~180 s hält die Invariante für den beobachteten Störfall (180+64=244 s), nicht für den MF-Extremfall. Die exakte Zahl legt die Spec fest: entweder Wert so wählen, dass die Invariante für die gemessenen Fälle hält und ADR-0038 unberührt bleibt (dann kein neues ADR; MF-Extremfall trägt ADR-0070 — Go wartet nicht weiter, Python läuft fertig, Rotation verhindert Blindstellen), oder Abweichung ⇒ ADR-Nachtrag. Die Grenze ist zweitrangig; die Rotation ist der Fix.
- Laufbudget 720 s gilt über alle Nutzer: höhere Grenze verbraucht mehr davon; Nutzer-Rotation (`scheduler.go:408`) verteilt `not_reached` fair. Nutzerzahl auf Prod vom Worktree aus nicht lesbar (`data/users` hier nur `default`, `validator-issue110`) — Spec nimmt die Budgetrechnung je Nutzer, kein PO-Thema.

**Beobachtbarkeit:** `skipped_ids` im Ergebnis, im WARNING (`trip_alert.py:1140-1147`) und in der Endpoint-Antwort.

### Dependencies
- `app.loader.get_data_dir(user_id)`, `file_lock.acquire_exclusive` (Muster `throttle_store.py`)
- Downstream Go-Scheduler: Antwortformat additiv, `TestBudgetDefaults_MatchSpec`, `TestClientTimeout_Is3000Seconds`, `job_status_partial_test.go` bleiben grün

### Risiken für /40 (konkret)
- **Testisolation der neuen Zustandsdatei:** 17 Testdateien rufen `check_all_trips` (Liste: `grep -rln check_all_trips tests/`); 12 davon setzen erkennbar ein eigenes Datenverzeichnis/`tmp_path`. Da der Store denselben Pfadweg wie `throttle_store` nimmt (`get_data_dir`), schreiben die Tests dorthin, wo sie heute schon Throttle-State schreiben — die 5 übrigen in /40 per Lauf gegen echte Pfade prüfen (vorher/nachher `ls data/users/*/alert_last_checked.json`).
- **Implizite ID-Reihenfolge:** prüfen, ob ein Test zwei Läufe desselben Nutzers fährt und danach die alte ID-Reihenfolge erwartet (`test_alert_run_deadline.py` AC-1/AC-2/„voller Lauf“ prüfen die Reihenfolge NICHT; AC-7 `>= 60` bleibt grün).
- Kein Mock-Theater: Fairness-Tests nutzen das Sleep-Muster `_setup_slow_trips` (`test_alert_run_deadline.py:194-226`) mit echter Deadline-Unterschreitung.

### Nicht im Umfang
S2 (Radar-Takt 5 Min, Laufbudget je Alarmart), S3 (Provider-Retry/Verarbeitung, Feed-Auffrischung), S4 (Latenz-Zusage-Wächter mit Endzahlen).

### Open Questions
- keine PO-Fragen. Grenzwert-Zahl und ADR-Frage entscheidet die Spec anhand der obigen Invariante.
