---
entity_id: fix_2261_a2s1_alarmlauf_reihenfolge
type: module
created: 2026-10-03
updated: 2026-10-03
status: draft
version: "1.0"
tags: [alerts, scheduler, fairness, epic-2261, python-core]
---

# Alarmlauf-Reihenfolge: kein Trip wird systematisch ausgelassen (Epic #2261, A-2 S1)

## Approval

- [ ] Approved

## Purpose

Die Abweichungsprüfung `TripAlertService.check_all_trips` bricht bei langsamen Läufen nach 90 s ab und lässt dabei wegen der festen Reihenfolge nach Trip-ID immer dieselben (ID-hinteren) Trips aus. Diese Spec macht die Reihenfolge fair (älteste zuletzt-erreicht-Zeit zuerst, persistiert je Nutzer), passt die veraltete Zeitgrenze an das heutige Go-Wartebudget an und macht übersprungene Trips sichtbar.

Beleg (Issue #2261, Scheibe A-2 S1): „Abweichungsprüfung lässt bei langsamen Läufen immer dieselben Trips aus: veraltete 90-s-Grenze (`trip_alert.py:66`, bezogen auf einen 120-s-Go-Timeout, der heute 3000 s beträgt) + feste Reihenfolge nach Trip-ID. Prod 03.10.: 12 Läufe in 24 h mit ‚checked=2 skipped=2', gehäuft zur vollen Stunde (neue Modellläufe)."

Ursache (bestätigt): (1) feste Reihenfolge `sorted(..., key=t.id)` plus Abbruch vor dem nächsten Trip ⇒ dieselben Trips fallen bei jedem langsamen Lauf weg (eigentlicher Defekt); (2) Grenze 90 s stammt aus dem 120-s-Go-Timeout, heute wartet Go 300 s; (3) Auslöser der langen Läufe sind Provider-Störungen zur Modelllaufzeit (nicht Umfang dieser Scheibe).

## Source

- **File:** `src/services/trip_alert.py`
- **Identifier:** `TripAlertService.check_all_trips`, `ALERT_RUN_DEADLINE_SECONDS`, `AlertCheckRunResult`
- **Neu:** `src/services/alert_check_state.py` (Store „zuletzt erreicht")
- **Endpoint:** `api/routers/scheduler.py` (`trigger_alert_checks`, `POST /api/scheduler/alert-checks`)

Schicht: ausschließlich **Python-Core** (`src/services/`, `api/`). Die Go-API (`internal/scheduler/`) wird **nicht angefasst**, nur gelesen.

Code-Referenzen (Stand Worktree):

- `src/services/trip_alert.py:61-66` — Konstante `ALERT_RUN_DEADLINE_SECONDS = 90.0` mit veraltetem 120-s-Kommentar
- `src/services/trip_alert.py:168-179` — `AlertCheckRunResult`
- `src/services/trip_alert.py:1002-1159` — `check_all_trips` (Sortierung 1033, Grenzprüfung 1035-1038, `checked += 1` 1039, `skipped` 1138, WARNING 1140-1147; Docstring „every 30 minutes" 1006 veraltet, real alle 15 Minuten)
- `api/routers/scheduler.py:61-83` — Endpoint-Antwort
- `src/services/throttle_store.py:58-66` — Pfad-/Lock-Muster (`get_data_dir(user_id)`, `file_lock.acquire_exclusive`)
- `internal/scheduler/scheduler.go:190-234` — `alertWaitBudget=300 s`, `alertRunBudget=720 s`, `alertCallCap=1800 s`; Client-Timeout 3000 s (Z. 217)
- `internal/scheduler/scheduler.go:408-417` — `rotateUsers` (Rotation über Nutzer, besteht bereits)
- `docs/specs/modules/fix_1447_s1_alarm_lauf_zeitgrenze.md` — Herleitung der 90 s (Z. 22-31, 128-132); Z. 425-429: „keine empirisch hergeleitete Zahl, zu knapp wäre Folge-Befund" — genau dieser Befund ist hier eingetreten
- `docs/adr/0038-zeitgrenze-je-nutzerlauf-unter-aufrufer-wartezeit.md`, `docs/adr/0070-aufruferseitige-wartegrenze-je-nutzeraufruf.md`

## Estimated Scope

- **LoC:** ca. +90 bis +120 produktiv (Limit 250/Workflow); Tests und Spec zählen nicht
- **Files:** 3 produktiv (`trip_alert.py` ändern, `alert_check_state.py` neu, `scheduler.py` ändern) + 1 Testdatei neu (`tests/tdd/test_alert_run_fairness.py`) + diese Spec
- **Effort:** medium (zentraler Alarmpfad, aber Änderung beschränkt auf Reihenfolge und Zustand; Alarmlogik je Trip unverändert)

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `app.loader.get_data_dir(user_id)` | Funktion | Nutzerverzeichnis `data/users/<user_id>/`, Mandantentrennung |
| `file_lock.acquire_exclusive` | Funktion | Datei-Lock (2 s) für Merge-Write, Muster aus `throttle_store.py` |
| `app.loader.load_all_trips(user_id)` | Funktion | Liefert die Trips des Nutzers (Quelle für Prune gelöschter Trips) |
| `internal/scheduler/scheduler.go` | Go-Konsument | Dekodiert die Endpoint-Antwort ohne `DisallowUnknownFields` — additives Feld `skipped_ids` unschädlich; `partial`/`ok`-Klassifikation bleibt |
| ADR-0038, ADR-0070 | Entscheidungen | Prinzip „Grenze spürbar unter Aufrufer-Wartezeit"; Go wartet nicht weiter, Python läuft fertig |

## Implementation Details

### 1. Store `src/services/alert_check_state.py` (neu)

Datei `data/users/<user_id>/alert_last_checked.json`, Inhalt `{trip_id: ISO-8601-UTC-Zeitstempel}`.

- Pfad ausschließlich über `get_data_dir(user_id)` mit der echten `user_id` des Service; **nie** ein Fallback auf `"default"` (Cross-User-Datenleck).
- `load(known_trip_ids)` liest die Datei; fehlende Datei, kaputtes JSON oder Lesefehler ⇒ leeres Ergebnis plus WARNING (fail-open).
- `record(reached: dict[str, datetime], known_trip_ids)` schreibt unter `file_lock.acquire_exclusive`: aktuelle Datei frisch lesen, je Trip `max(alt, neu)` mergen, Einträge für Trip-IDs, die nicht mehr in `known_trip_ids` stehen, entfernen (prunen), atomar schreiben (temporäre Datei im selben Verzeichnis, dann `os.replace`).
- Lock-Timeout oder Schreibfehler ⇒ WARNING, kein Raise. Folge: schadet nur der Fairness des nächsten Laufs, nie dem Versand.

### 2. `check_all_trips` (Änderung)

- **Reihenfolge:** `trips` werden nach (Stempel aufsteigend, fehlender Stempel = ältester, Trip-ID als Tie-Break) sortiert statt nach Trip-ID. Kann der Zustand nicht geladen werden, ist die Reihenfolge das alte `key=id` (fail-open).
- **Stempel:** Jeder Trip, der vor der Zeitgrenze **erreicht** wurde (also dort, wo heute `checked += 1` steht), wird in `reached` mit dem Zeitpunkt des Erreichens (`datetime.now(timezone.utc)`) vermerkt — unabhängig davon, ob er danach per `continue` (regellos, abgelaufen, kein Anker) oder per Exception verlassen wird. Sonst würde ein Giftfall die Warteschlange blockieren oder regellose Trips würden vorne stehen bleiben und die Fairness verschieben.
- **Schreiben:** einmal am Laufende in einem `finally`-Block (auch nach unerwarteter Exception im Schleifenkörper). Ein hart abgebrochener Prozess (Kill/OOM) verliert den Fortschritt genau dieses Laufs; der nächste Lauf beginnt dann mit dem alten Stand. Das ist akzeptiert, weil nur die Fairness betroffen ist.
- **Semantik von `checked`:** bleibt „vor der Grenze erreicht" (unverändert, `trip_alert.py:1039`); nur die Spec-/Docstring-Formulierung wird präzisiert, die Zählung nicht geändert.
- **`skipped_ids`:** `AlertCheckRunResult` erhält das Feld `skipped_ids: list[str]` (Default leere Liste, in Sortierreihenfolge). Bei Grenzabbruch enthält es die nicht erreichten Trip-IDs; bei vollem Lauf ist es leer. Das WARNING (`trip_alert.py:1140-1147`) nennt die übersprungenen IDs.
- Docstring und Kommentare korrigieren: „every 30 minutes" ⇒ alle 15 Minuten (Cron `*/15`); „Tour/Touren" ⇒ „Trip/Trips"; 120-s-Bezug entfernen.

### 3. Zeitgrenze `ALERT_RUN_DEADLINE_SECONDS = 180.0`

Die Grenze wird nur **vor** einem Trip geprüft; ein Lauf endet real bei *Grenze + Dauer des zuletzt begonnenen Trips*. Dokumentierte Invariante am Konstantenort:

> **Grenze + längster beobachteter Einzel-Trip-Überhang ≤ Go-Wartebudget (`alertWaitBudget` = 300 s).**

Beobachtet: Überhang bis ca. 64 s (Prod 03.10.: 154 s bei 90 s Grenze); 180 s + 64 s = 244 s ≤ 300 s. Der alte Herleitungskommentar (120-s-Bezug, `scheduler.go:82`) wird durch diese Herleitung ersetzt.

Warum 180 s: Die 90 s waren gegen einen 120-s-Timeout abgeleitet, der seit #1912 3000 s (Client) bzw. 300 s (Wartebudget) beträgt. 180 s hält die Invariante für alle gemessenen Störfälle und lässt Normalläufe (bis 88 s) vollständig durchlaufen.

Nicht abgedeckt, bewusst: Der MeteoFrance-Extremfall (`FETCH_DEADLINE_SECONDS=180 s` je Abruf, `meteofrance.py:98-119`) kann auch eine 180-s-Grenze überschreiten. Das ist keine Schranke darunter, sondern wird getragen durch ADR-0070 (Go wartet nicht weiter, Python läuft bis zum Deckel fertig) und durch die neue Rotation, die verhindert, dass dieselben Trips dauerhaft blind bleiben.

Die Grenze ist zweitrangig; die Rotation ist der eigentliche Fix.

### 4. Laufbudget-Rechnung über Nutzer (Trade-off)

`alertRunBudget = 720 s` (`scheduler.go:190-234`) gilt über **alle** Nutzer eines Laufs. Provider-Störungen zur Modelllaufzeit treffen alle Nutzer gleichzeitig. Bei 90 s Grenze und ca. 154 s realem Störlauf passen rund 4 Nutzer ins Budget, bei 180 s und ca. 244 s rund 2-3. Weitere Nutzer landen im Go-Scheduler auf `not_reached`; die bestehende Nutzerrotation `rotateUsers` (`scheduler.go:408`) verteilt das fair über aufeinanderfolgende Läufe. Die Nutzerzahl auf Prod ist vom Worktree aus nicht lesbar.

Bekannter Trade-off: Abdeckung **innerhalb** eines Nutzers (alle seine Trips pro Lauf) gewinnt gegenüber Abdeckung **über** Nutzer. Im Normalfall braucht ein Lauf Sekunden, betroffen ist nur der Störfall. Das ist eine Tech-Entscheidung mit Begründung, kein PO-Thema.

### 5. Endpoint `POST /api/scheduler/alert-checks` (Änderung)

Antwort zusätzlich um `skipped_ids` (Liste) erweitert; alle bisherigen Felder (`status`, `count`, `checked`, `skipped`, `duration_s`, `reason`) und die `partial`/`ok`-Klassifikation bleiben unverändert. Go-Code, `TestBudgetDefaults_MatchSpec`, `TestClientTimeout_Is3000Seconds` und `job_status_partial_test.go` bleiben unverändert grün.

### 6. Tageslimit-Wirkung

`alert_daily_limit` zählt pro Nutzer (`user_id`, Ortszone), nicht pro Trip. Die neue Reihenfolge verändert daher, **welcher** Trip am Limit noch seinen Alarm erhält: statt immer der ID-vordere derjenige, der am längsten nicht erreicht wurde. Das ist gewollt (fairer). Fundstellen im Test-Bestand (per grep auf `check_all_trips` + `alert_daily_limit` in `tests/`): nur `tests/helpers/official_alert_gate_fixtures.py:212-222` (Helper für einen einzelnen Trip, keine Reihenfolgeabhängigkeit erkennbar). Alle anderen `alert_daily_limit`-Tests rufen `check_and_send_alerts` direkt statt `check_all_trips`; kein Test mit mehreren Trips plus Limit erwartet implizit die ID-Reihenfolge. In /40 wird das mit einem Lauf der 17 Testdateien, die `check_all_trips` rufen, bestätigt.

## Expected Behavior

- **Input:** `TripAlertService(user_id=…).check_all_trips()`, aufgerufen vom Go-Scheduler über `POST /api/scheduler/alert-checks?user_id=…` alle 15 Minuten.
- **Output:** `AlertCheckRunResult(alerts_sent, checked, skipped, skipped_ids, duration_s, hit_deadline)`; Endpoint-Antwort wie bisher plus `skipped_ids`.
- **Side effects:** Schreibt/aktualisiert `data/users/<user_id>/alert_last_checked.json` (nur dieser Nutzer); WARNING mit übersprungenen Trip-IDs bei Grenzabbruch. Versand, Alarmregeln, Throttle und Tageslimit je Trip bleiben unverändert.

## Acceptance Criteria

- **AC-1:** Given ein Nutzer mit N Trips und eine Zeitgrenze, die je Lauf nur k < N Trips zulässt (echte Schlafzeit je Trip, Grenze klein gesetzt) / When zwei aufeinanderfolgende Läufe ausgeführt werden / Then ist die Vereinigung der in beiden Läufen erreichten Trips gleich allen N Trips und der zweite Lauf beginnt mit genau den Trips, die der erste übersprungen hat (kein Trip zweimal hintereinander ausgelassen).
  - Test: Rückmutation auf `sorted(key=id)` lässt Lauf 2 dieselben ID-vorderen Trips erneut prüfen ⇒ rot.

- **AC-2:** Given vorbelegte Stempel in `alert_last_checked.json` (ein Trip mit ältestem, einer mit neuestem Stempel, ein Trip ganz ohne Eintrag) und zwei Trips mit identischem Stempel / When `check_all_trips` läuft / Then werden die Trips in der Reihenfolge ohne Stempel, dann ältester bis neuester Stempel geprüft, und bei gleichem Stempel entscheidet die Trip-ID.
  - Test: Aufruf-Reihenfolge der geprüften Trips wird aufgezeichnet und mit der erwarteten Liste verglichen; ID-Sortierung oder fehlender Stempel-Vorrang wird rot.

- **AC-3:** Given ein gespeicherter Stempel für einen Trip, der inzwischen gelöscht wurde / When der nächste Lauf schreibt / Then ist der Eintrag des gelöschten Trips nicht mehr in der Datei, die Einträge der vorhandenen Trips bleiben erhalten.
  - Test: Datei wird nach dem Lauf eingelesen; Weglassen des Prune macht den Test rot.

- **AC-4:** Given je ein Trip, der (a) eine Exception in der Prüfung auslöst, (b) keine Alarmregeln hat und (c) abgelaufen ist, alle vor der Zeitgrenze erreicht / When der Lauf endet / Then trägt jeder dieser Trips einen neuen Stempel in der Datei und der Lauf liefert die übrigen Trips normal weiter.
  - Test: Stempel nur im Erfolgspfad zu setzen lässt (a)-(c) ohne Eintrag ⇒ rot; zusätzlich wird geprüft, dass ein nach der Grenze nicht erreichter Trip keinen neuen Stempel bekommt.

- **AC-5:** Given zwei überlappende Läufe desselben Nutzers, die verschiedene Stempel für verschiedene und für denselben Trip schreiben / When beide ihr Ergebnis speichern (nacheinander, zweiter mit älterem Wert für einen gemeinsamen Trip) / Then enthält die Datei je Trip das Maximum beider Werte und keinen verlorenen Eintrag.
  - Test: Zwei `record`-Aufrufe mit sich kreuzenden Werten; ein Überschreiben statt Max-Merge wird rot.

- **AC-6:** Given zwei Nutzer A und B mit je eigenen Trips (auch gleiche Trip-IDs) / When ein Lauf für A ausgeführt wird / Then wird nur `data/users/A/alert_last_checked.json` geschrieben, die Datei von B bleibt byte-identisch (oder nicht vorhanden) und es entsteht keine Datei unter `data/users/default/`.
  - Test: Zwei Nutzer in einem `tmp_path`-Datenverzeichnis; Fallback auf `"default"` oder gemeinsamer Pfad wird rot (Pflicht-Zwei-Nutzer-Test).

- **AC-7:** Given eine unlesbare/kaputte Zustandsdatei bzw. ein nicht erhältlicher Lock (Lock-Timeout) / When `check_all_trips` läuft / Then werden alle Trips normal geprüft und Alarme versendet, die Reihenfolge fällt auf Trip-ID zurück, eine Warnung steht im Log und es wird keine Exception nach außen gereicht.
  - Test: Datei mit ungültigem JSON bzw. extern gehaltener Lock; Raise statt fail-open wird rot, ausgebliebener Versand wird rot.

- **AC-8:** Given ein Lauf, der wegen der Zeitgrenze Trips auslässt, und ein Lauf, der alle Trips schafft / When die Ergebnisse, das WARNING und die Endpoint-Antwort betrachtet werden / Then enthalten `AlertCheckRunResult.skipped_ids`, die WARNING-Zeile und die Antwort von `POST /api/scheduler/alert-checks` genau die nicht erreichten Trip-IDs (mit `len(skipped_ids) == skipped`), und beim vollen Lauf ist `skipped_ids` leer.
  - Test: Log-Capture und Endpoint-Aufruf über den echten FastAPI-Router; fehlendes Feld oder fehlende IDs im Log werden rot.

- **AC-9:** Given das Modul `services.trip_alert` / When `ALERT_RUN_DEADLINE_SECONDS` gelesen wird / Then ist der Wert 180 und kleiner als das Go-Wartebudget von 300 s, und der bestehende Test AC-7 aus `tests/tdd/test_alert_run_deadline.py` (`>= 60`, per Monkeypatch änderbar) bleibt grün.
  - Test: Vergleich gegen 180 und `< 300`; Rückmutation auf 90 oder auf einen Wert ≥ 300 wird rot.

- **AC-10:** Given die Go-Antwortverarbeitung des Schedulers (`partial`/`ok`-Klassifikation, `job_status_partial_test.go`, `TestBudgetDefaults_MatchSpec`, `TestClientTimeout_Is3000Seconds`) / When die Python-Antwort das zusätzliche Feld `skipped_ids` enthält / Then bleiben diese Go-Tests ohne Änderung am Go-Code grün und die Statusableitung (`partial` nur bei `hit_deadline`) ist unverändert.
  - Test: `go test ./internal/scheduler/...` unverändert; zusätzlich Python-Test, dass `status` weiterhin nur bei `hit_deadline` `partial` ist.

## Tests

Neue Datei `tests/tdd/test_alert_run_fairness.py` (nach Verhalten benannt). Kein Mock-Theater: Es wird das echte Sleep-Muster `_setup_slow_trips` aus `tests/tdd/test_alert_run_deadline.py:194-226` verwendet (Trips mit echter Schlafzeit, die Grenze per Monkeypatch von `ALERT_RUN_DEADLINE_SECONDS` klein gesetzt, damit sie real unterschritten wird) und ein echtes `tmp_path`-Datenverzeichnis, kein gemockter Store.

| AC | Test (Name in `test_alert_run_fairness.py`) |
|----|---------------------------------------------|
| AC-1 | `test_zwei_langsame_laeufe_decken_alle_trips_ab` |
| AC-2 | `test_vorbelegte_stempel_bestimmen_reihenfolge_id_ist_tiebreak` |
| AC-3 | `test_geloeschter_trip_verschwindet_aus_zustandsdatei` |
| AC-4 | `test_stempel_auch_bei_exception_regellos_und_abgelaufen` |
| AC-5 | `test_zwei_schreiber_mergen_mit_maximum` |
| AC-6 | `test_zwei_nutzer_isolation_nie_default` |
| AC-7 | `test_kaputte_zustandsdatei_und_lock_timeout_sind_fail_open` |
| AC-8 | `test_skipped_ids_in_ergebnis_warning_und_endpoint` |
| AC-9 | `test_laufgrenze_180_unter_go_wartebudget` |
| AC-10 | `go test ./internal/scheduler/...` unverändert + `test_status_partial_nur_bei_hit_deadline` |

Testisolation: 17 Testdateien rufen `check_all_trips`. In /40 wird vorher und nachher `ls data/users/*/alert_last_checked.json` im Hauptdatenbaum verglichen; es darf keine neue Datei unter echten `data/users/*` entstehen. Wo ein Test kein eigenes Datenverzeichnis setzt, wird es gesetzt (Store nutzt denselben `get_data_dir`-Weg wie `throttle_store`).

## E2E- und Staging-Plan

- **Nicht messbar auf Staging (`NOT_MEASURABLE_ON_STAGING`):** Inhalt und Existenz der Zustandsdatei `alert_last_checked.json` — der Staging-Datenbestand ist für den Benutzer `hem` nicht lesbar. Diese Zusicherung ist im Kern (AC-1 bis AC-7) bewiesen und wird auf Staging nicht als PASS behauptet.
- **Messbar auf Staging:** das Feld `skipped_ids` sowie `checked`/`status` der Antwort, direkt über den Python-Kern (Staging-Kern Port 8001, Header `X-GZ-Core-Auth`), weil der Go-Trigger auf Staging Admin-only ist und Staging keinen Admin hat (403). Verwendet wird ein Wegwerf-/Testnutzer mit Test-Trips; **kein** Sammelversand über alle Trips. Erwartung: Antwort enthält `skipped_ids` (bei vollem Lauf leer), `status: ok`. Zusätzlich HTTP-Smoke: `/` liefert 200/302, `/api/health` liefert 200.
- **Prod-Nachweis nach Deploy (beobachtend, kein Gate):** In den Logs stehen bei Grenzabbrüchen WARNINGs mit **wechselnden** `skipped_ids` statt immer derselben IDs.

## Known Limitations

- Ein hart abgebrochener Prozess (Kill/OOM) verliert den Stempel-Fortschritt genau dieses Laufs; nächster Lauf beginnt mit altem Stand (nur Fairness betroffen).
- Der MeteoFrance-Extremfall (180 s je Abruf) kann auch die 180-s-Grenze überschreiten; er ist nicht Teil dieser Scheibe (siehe Risiken, ADR-0070).
- Bei Provider-Störung können weniger Nutzer pro Go-Lauf drankommen (Abschnitt 4); Rotation gleicht über Läufe aus.
- Die Garantie „jeder Trip ist nach höchstens ⌈N/k⌉ Läufen dran" gilt für k ≥ 1 erreichte Trips je Lauf; ist kein einziger Trip vor der Grenze schaffbar (k = 0), hilft die Reihenfolge nicht.

## Nicht im Umfang

- **A-2 S2:** Radar-Takt auf 5 Minuten, Laufbudget je Alarmart an den Takt gebunden.
- **A-2 S3:** Provider-Retry/Backoff, Circuit-Breaker, Feed-Auffrischung (Auslöser der langen Läufe wird hier nicht behoben).
- **A-2 S4:** Latenz-Zusage-Wächter mit Endzahlen (Entwurf `alarm_latenz_zusage.md`).
- Änderungen am Go-Scheduler (Budgets, Nutzerrotation) und an der Alarmlogik je Trip.

## Risiken

- **Laufbudget-Trade-off (Abschnitt 4):** Höhere Grenze verbraucht mehr vom 720-s-Laufbudget über alle Nutzer; im Störfall mehr `not_reached`-Nutzer je Lauf. Gemildert durch `rotateUsers`; nur Störfall betroffen. Prod-Nutzerzahl nicht lesbar ⇒ Nachweis über die Prod-Logs nach Deploy.
- **Tageslimit-Reihenfolge (Abschnitt 6):** Welcher Trip am Nutzer-Limit noch alarmiert wird, ändert sich zugunsten des am längsten nicht erreichten Trips. Gewollt; Tests dazu: siehe Fundstellen.
- **Überlappung:** Kein Lock um `check_all_trips`. Zwei Läufe desselben Nutzers überlappen nur nach Ablauf des 1800-s-Deckels; der Merge-Write (`max`) ist dafür harmlos (AC-5).
- **Mandantentrennung:** Neuer Zustand je Nutzer; falscher Pfad wäre ein Cross-User-Leck ⇒ AC-6 mit zwei Nutzern ist Pflicht.
- **Zählsemantik:** Stempel nur für tatsächlich erreichte Trips (AC-4), sonst verschiebt sich die Fairness.

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** keine (neues ADR nicht nötig)
- **Rationale:** ADR-0038 legt nur das Prinzip fest („Grenze spürbar unter der Aufrufer-Wartezeit"), ausdrücklich keine Zahl. 180 s liegt unter dem Go-Wartebudget von 300 s und ist damit ADR-konform; ADR-0070 trägt den Extremfall. `fix_1447_s1` (Z. 425-429) nannte die 90 s „keine empirisch hergeleitete Zahl"; diese Spec ersetzt sie durch eine begründete Invariante. Verworfene Alternativen für die Fairness: Offset-Rotation (neue/gelöschte Trips verschieben Positionen), Zufall (keine Garantie, nicht deterministisch testbar), zustandslose Rotation aus dem Viertelstunden-Slot (Garantie bricht bei ausgefallenen oder übersprungenen Läufen).

## Changelog

- 2026-10-03: Initial spec created (Epic #2261, Scheibe A-2 S1)
