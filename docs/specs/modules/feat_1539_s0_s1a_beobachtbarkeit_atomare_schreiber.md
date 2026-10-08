---
entity_id: feat_1539_s0_s1a_beobachtbarkeit_atomare_schreiber
type: feature
created: 2026-10-07
updated: 2026-10-07
status: draft
version: "1.0"
tags: [scheduler, beobachtbarkeit, nebenlaeufigkeit, atomares-schreiben, multi-user, epic-2138]
---

# Feature #1539 Workflow 1 — S0 Beobachtbarkeit + S1a atomare Schreiber

Issue #1539, Epic #2138. Dieser Workflow liefert nur die Scheiben **S0** und **S1a**. Das Abrufverhalten
ändert sich nicht. #1539 bleibt danach offen (PR „Refs #1539").

## Approval

- [ ] Approved

## Purpose

Trip-Alarmläufe brechen schon heute an der Zeitobergrenze ab und lassen Trips ungeprüft (7 Tage Produktion:
29 Abbrüche, jedes Mal `checked=2 skipped=2`), während die Überwachung Grün zeigt: Der Go-Status meldet
`users.partial: 0`, weil dieser Wert nur eine Momentaufnahme ist und vom nächsten erfolgreichen Lauf
(15 Minuten später) überschrieben wird. Es gibt keinen kumulativen Zähler, und Go verwirft
`reason`/`skipped`/`duration_s` der Python-Antwort. S0 macht diese Abbrüche und die Laufdauer sichtbar
und bringt sie in die externe Überwachung. S1a macht die Schreiber geteilter Zustandsdateien atomar und
gesperrt. Das ist Vorbedingung für die spätere Parallelisierung (S2–S7), und die Race-Fehler bestehen
heute schon, weil die `def`-Handler im anyio-Threadpool nebenläufig laufen.

**Ehrlich vorweg:** S0 + S1a senken die Abbrüche **nicht**. Sie machen sie messbar und sichern die Schreiber.
Die Senkung kommt erst mit S3 (Trip-Alarm-Etappen parallel).

## Source

- **Go:** `internal/scheduler/scheduler.go` — `jobResult` (`:35`), `triggerResponseBody` (`:~948`),
  `partialRunError`, `triggerEndpointForUser`, `callUserWithBudget` (`:~482-513`), `runUserStep`,
  `harvestLateResult`, `runForAllUsers` (`:318`), `recordRun` (`:~915-935`), `usersField` (`:~1122`),
  Status-Zusammenbau (`:~1249-1252`)
- **Python-Router:** `api/routers/scheduler.py` — `/alert-checks` (`:61`), `/compare-alert-checks`,
  `/compare-official-alert-checks`, `/compare-radar-alert-checks`, `/radar-alert-checks`, `/trip-reports`
- **Python-Dienste (Messung):** `src/services/trip_alert.py` (`check_all_trips`, Logzeile `:1195`),
  `compare_alert.py`, `compare_official_alert.py`, `compare_radar_alert.py`, `trip_report_scheduler.py`
- **Python-Schreiber (S1a):** `src/services/alert_log.py:_append` (`:536-548`), `alert_state.py:77`,
  `weather_snapshot.py` (`:111,138,276`), `compare_weather_snapshot.py:81`, `src/providers/openmeteo.py`
  (`_save_availability_cache :357-360`, Auto-Probe `:1239-1243`), vorhandener Helfer
  `src/services/file_lock.py`
- **Extern:** `/home/hem/henemm-infra/scripts/check-gregor20.sh` (Abschnitt Alarm-Job-Freshness, `:846-900`)

> **Schicht-Hinweis:** Go-API (`internal/scheduler/`) für den Status-Vertrag; Python-Core
> (`api/`, `src/services/`, `src/providers/`) für Messung und Schreiber; Infra-Repo `henemm-infra` für den
> Monitor. Kein Frontend.

## Estimated Scope

- **LoC:** ca. 270 Produktivcode (Go ~100, Python ~150, Monitor ~20) plus ca. 300 Test. `loc_limit_override 500`
  ist gesetzt. Doku (`api_contract.md`) zählt nicht.
- **Files:** ca. 18 (siehe Affected Files)
- **Effort:** medium — zentrale Alarmpfade, aber kein geändertes Abrufverhalten

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `docs/context/feat-1539-parallele-abrufe.md` | Analyse | Messungen, Scheibenplan, Race-Tabelle |
| `fix_2149_scheduler_nutzer_sichtbarkeit.md` | Spec (live) | `userRunState`, `users{}`-Aggregat, Mandantenregel „nur Zahlen, keine IDs" |
| `fix_2149_scheduler_budget_teilb.md` | Spec (live) | Wartebudget, Nachzügler-Goroutine, `in_flight`-Zahlen |
| `fix_1447_s1_alarm_lauf_zeitgrenze.md` | Spec (live) | `status:"partial"`/`reason:"deadline"` der Python-Antwort |
| `fix_1448_s2_dateisperren.md`, ADR-0083 | Spec/ADR | Sperrdatei-Vertrag `<ziel>.lock`, `exclusive_lock`, `LockTimeout` |
| ADR-0038 / ADR-0070 | ADR | Zeitgrenzen; S0 verändert keine Grenze |
| #2155 S2 | Ticket (live) | `/api/scheduler/status` nur mit `X-GZ-Status-Token`; Mandantentrennung bleibt Pflicht |
| `check-gregor20.sh` | Externer Konsument | liest `last_run.time` und `overlap.skipped_since_last_run`; beide ändern ihre Bedeutung nicht |

## Implementation Details

### A. S0 — Status-Vertrag (Go), ausschließlich additiv

**1. Ursache (belegt).** Python liefert den Abbruch korrekt (`status:"partial"`, `reason:"deadline"`,
`checked/skipped/skipped_ids/duration_s`; `scheduler.py:61-84`, Radar `_radar_run_response :94-108`).
Go liest in `triggerResponseBody` nur `status/count/failed` und verbucht `partial` als `partialRunError`
(`jobResult.Status="partial"`). `users.partial` ist `ConsecutivePartial >= 1`
(`user_run_state.go:232-247`) und wird vom nächsten `ok`-Lauf auf 0 gesetzt (`recordLocked :173-176`);
`last_run` wird ebenso überschrieben. `reason`, `skipped`, `duration_s` werden verworfen.

**2. Neue Felder je Job.**

- `last_run.duration_s` (Zahl, Sekunden, 3 Nachkommastellen) für **alle** Jobs, auch global und
  `data_write_selftest`. Quelle ist die **Go-Wanduhr**, nicht die Python-Angabe, denn nur sie gibt es für
  jeden Job einheitlich. Feld `omitempty` entfällt: 0 ist ein gültiger Wert.
- Neuer Block `deadline_aborts` neben `users`/`overlap`, **immer vorhanden bei Fan-out-Jobs**
  (`fanOutJobIDs`), sonst fehlend („nicht anwendbar", analog `usersField`):

```json
"deadline_aborts": {
  "total": 3,
  "last_at": "2026-10-07T06:02:11+02:00",
  "last_skipped": 2,
  "counting_since": "2026-10-06T21:14:03+02:00"
}
```

  - `total`: kumulative Zahl der Nutzerläufe dieses Jobs, die Python mit `reason:"deadline"` beendet hat.
    Sie wird **nie** vom nächsten `ok`-Lauf zurückgesetzt. Das ist der Kern der Fehlerbehebung.
  - `last_at`: Zeitpunkt des letzten solchen Abbruchs; fehlt, solange `total == 0`.
  - `last_skipped`: Anzahl der im **letzten** Abbruch ungeprüft gebliebenen Einheiten (nur die Zahl).
  - `counting_since`: Zeitpunkt, ab dem der Zähler zählt (Prozessstart des Go-Dienstes).

**3. Wo gezählt wird.** `triggerResponseBody` bekommt `Reason`, `Skipped`, `DurationS`.
`partialRunError` bekommt ein Kennzeichen `deadline` und die Zahl `skipped`. Gezählt wird an **genau einer**
Stelle, die `jobID` kennt (Auswertung des `partialRunError` im Nutzerschritt) **und** beim Einsammeln eines
Nachzüglers (`harvestLateResult`). Ein Abbruch, dessen Antwort erst nach dem Wartebudget eintrifft, geht
sonst verloren. Jeder Abbruch zählt genau einmal.

**4. Zähler-Lebensdauer (Entscheidung).** **In-Memory mit `counting_since`, keine Persistenz.**
Begründung: Eine Persistenz bräuchte einen neuen Schreibweg ins Datenverzeichnis, und S1a baut gerade
Schreibrisiken ab. Ein Neustart (Deploy) setzt den Zähler auf 0, aber `counting_since` macht das ehrlich
lesbar. Maßgebliche Messquelle für den 7-Tage-Wirkungsnachweis ist die **Python-Logzeile**
(`journalctl -u gregor-python`, „Zeitobergrenze" und „Lauf beendet nach"), die Deploys überlebt.
Der Status-Zähler dient der Live-Überwachung und dem Monitor, nicht der Langzeitstatistik.

**5. Was `duration_s` misst (Entscheidung).** Wanduhr von Laufbeginn bis Ende der Nutzerschleife
(`runForAllUsers`) **ohne Nachzügler**. `callUserWithBudget` lässt nach Wartebudget-Ablauf eine Goroutine
weiterlaufen. Deren Restlaufzeit zählt nicht in `duration_s`. Nachzügler bleiben über die bestehenden
`in_flight`-/`skipped_in_flight`-Zahlen sichtbar. Für Nicht-Fan-out-Jobs ist es die Dauer von `fn()` in
`recordRun`. Gemessen wird in `recordRun` um `runRecovered`, damit auch `error`- und `partial`-Läufe eine
Dauer tragen.

**6. Mandantentrennung.** Im globalen Status stehen **keine** `skipped_ids` (Trip-IDs) und **keine**
`user_id`. Nur Zählwerte, aggregiert über alle Nutzer. Der Endpoint ist halb-öffentlich (Token, #2155 S2).
`skipped_ids` werden von Go gelesen, wenn überhaupt, nur zur Zählung und nie gespeichert oder ausgegeben.
`/api/scheduler/status/me` bleibt unverändert; ein Eigenwert je Nutzer ist nicht Teil dieser Scheibe.

**7. Verträglichkeit.** `last_run.time`, `last_run.status`, `overlap.skipped_since_last_run` und alle
`users{}`-Felder behalten Name, Typ und Bedeutung. `docs/reference/api_contract.md` §Scheduler-Status wird
um `last_run.duration_s` und `deadline_aborts{}` ergänzt (additiv).

### B. S0 — Python: Messung vereinheitlichen

Keine neue Laufgrenze für `compare_alert`/`compare_official` (das ist S6). Nur Messung.

| Route | Heute | S0 |
|---|---|---|
| `/alert-checks` | `duration_s`, `partial`/`deadline` | unverändert; Dauer je Trip und je Etappe als Log |
| `/radar-alert-checks`, `/compare-radar-alert-checks` | `duration_s`, `partial`/`deadline` | unverändert; Logzeile ergänzen, falls dort noch keine „Lauf beendet nach" |
| `/compare-alert-checks`, `/compare-official-alert-checks` | `status`, `count`, `failed` | zusätzlich `duration_s`, `checked`; `status` bleibt `ok`/`partial` ausschließlich nach bestehender Regel (keine neue Grenze ⇒ kein `deadline`) |
| `/trip-reports` | `status`, `count`, `failed` | zusätzlich `duration_s` |

Einheitliche Logzeile in allen Pfaden, Format wie `trip_alert.py:1195`:
`<dienst>: Lauf beendet nach {duration_s:.3f}s fuer user_id=<id> (checked=… skipped=… …)`.
Dauer je Trip und je Etappe in `trip_alert` als `logger.info` (z. B. „Trip <name>: geprüft in X s",
„Etappe <n>: Abruf in X s"). Das macht die heute unprotokollierte 10–30-s-Lücke je Etappe messbar.
Die Routen-Antworten ergänzen nur Felder, Go ignoriert Unbekanntes.

### C. S0 — Monitor (Entscheidung: in DIESER Scheibe, als WARN)

`check-gregor20.sh` (Repo `henemm-infra`) wertet im Abschnitt Alarm-Job-Freshness zusätzlich
`deadline_aborts.total` aus. Es meldet **WARN** (nicht FAIL), wenn der Wert seit dem letzten Check gestiegen
ist. Der letzte Wert wird im vorhandenen Zustandsfile `STATE_PATH` (`/home/hem/.check-gregor20-jobstate.json`)
je Job geführt. Ändert sich `counting_since` (Neustart), wird die Basis auf 0 zurückgesetzt, ein Abbruch
kurz nach dem Deploy wird also nicht verschluckt. Begründung: Eine sichtbare, aber von niemandem
beobachtete Lücke wiederholt genau den Fehler, den S0 beheben soll. WARN statt FAIL, weil ein Abbruch einen
Teilausfall bedeutet und kein Totalausfall ist (analog `overlap`). Keine Änderung an den bestehenden
Prüfungen. **Der Arbeitsbaum von `henemm-infra` ist sofort live:** Änderung zuerst in einer Kopie
(Scratchpad) mit Testdaten prüfen, erst dann übernehmen. Commit im Repo `henemm-infra`.

### D. S1a — atomare Schreiber (Python)

Wiederverwendet wird `src/services/file_lock.py`; **kein neuer Helfer**. Vorhanden:
`exclusive_lock(target)` (Kontextmanager, `flock` auf `<ziel>.lock`, `LockTimeout`), `atomic_write_json(path, data)`
(Temp-Datei im selben Ordner, `fsync`, `os.replace`, Aufräumen bei Fehler, Temp-Name endet nicht auf `.json`),
`locked_json_rmw`, `acquire_exclusive`.

| Datei | Änderung |
|---|---|
| `alert_log.py:_append` | gesamter Read-Modify-Write unter `exclusive_lock(alert_log.json)`, Schreiben per `atomic_write_json`; kaputte Datei wird wie bisher mit Warnung neu angelegt |
| `alert_state.py:77` (`save`) | `atomic_write_json` (Zustand je Entität, ein Schreiber je Datei, daher nur atomar, keine Sperre) |
| `weather_snapshot.py` (3 Stellen), `compare_weather_snapshot.py:81` | `atomic_write_json` |
| `openmeteo.py:357-360` (C4-63) | `atomic_write_json` statt `write_text` |
| `openmeteo.py:1239-1243` | Auto-Probe unter `exclusive_lock(Verfügbarkeits-Cache)`. Nach dem Erwerb wird der Cache **erneut geladen**; ist er inzwischen gültig, wird nicht geprobt (Double-Checked-Locking). So probt nicht jeder Thread gleichzeitig |

**Lock-Timeout für `alert_log` (Entscheidung).** Fail-open nach Timeout hieße Eintragsverlust, und gerade
das ist der heutige Fehler. Deshalb:

1. Der gesperrte Abschnitt dauert Millisekunden, ein Timeout bedeutet also einen toten Sperrhalter.
   `exclusive_lock` bekommt dafür einen **optionalen** Parameter `timeout_s` (Standard unverändert
   `BRIEFING_LOCK_TIMEOUT_SECONDS`, bestehende Aufrufer unberührt). `alert_log` wartet bis zu 30 s.
2. Läuft auch das ab, wird der Eintrag **nicht still verworfen**: `logger.error` mit dem vollständigen Eintrag
   als JSON (aus dem Journal wiederherstellbar) und Hochzählen eines Prozess-Zählers
   `alert_log_lost_entries`. Es wird **nicht** ungesperrt geschrieben (würde andere Einträge zerstören) und
   **nicht** geworfen (ein Protokollproblem darf keinen Alarmversand abbrechen).

Für `weather_snapshot`, `compare_weather_snapshot`, `alert_state` entsteht kein neues Sperrverhalten; sie
werden nur atomar, also nie halb geschrieben.

## Expected Behavior

- **Input:** unverändert (Cron-Ticks, Python-Antworten).
- **Output:** `/api/scheduler/status` zusätzlich `last_run.duration_s` und je Fan-out-Job `deadline_aborts{}`;
  Python-Antworten zusätzlich `duration_s`/`checked`; Logzeilen „Lauf beendet nach Xs" in allen Pfaden.
  Monitor meldet WARN bei Zuwachs von `deadline_aborts.total`.
- **Side effects:** neue Sperrdateien `*.json.lock` neben `alert_log.json` und dem Verfügbarkeits-Cache
  (Listen filtern `*.json`, Temp-Dateien enden auf `.tmp`). Ein zusätzlicher Statuswert im Monitor-Zustandsfile.
  Das Abrufverhalten, die Zeitgrenzen und die Reihenfolge ändern sich nicht.

## Acceptance Criteria

- **AC-1:** Given ein Fan-out-Job, dessen Python-Antwort für einen Nutzer `status:"partial"`, `reason:"deadline"`
  und `skipped:2` liefert, und danach ein Lauf, der `ok` meldet / When der Status-Endpunkt abgefragt wird /
  Then zeigt `deadline_aborts.total` weiterhin `1`, `last_at` ist gesetzt und `last_skipped` ist `2`, obwohl
  `users.partial` wieder `0` ist.
  - Test: Go-Test mit Fake-Python-Server; beweist den Kern-Bug aus Nutzersicht (heute verschwindet der Abbruch).

- **AC-2:** Given ein Status-Aufruf nach einem Abbruchlauf mit zwei Nutzern, von denen nur Nutzer A abbricht /
  When der Status-Body ausgegeben wird / Then ist `deadline_aborts.total` genau `1`, und der Body enthält weder
  eine Nutzer-ID noch eine Trip-ID noch den Schlüssel `skipped_ids`.
  - Test: Go-Test mit zwei Nutzern (`internal/scheduler/deadline_abort_visibility_test.go`), Body-Text auf beide IDs und die Trip-ID geprüft.

- **AC-3:** Given eine Antwort, die erst nach Ablauf des Wartebudgets eintrifft (Nachzügler) und
  `reason:"deadline"` trägt / When der Nachzügler eingesammelt wird / Then zählt `deadline_aborts.total` den
  Abbruch genau einmal, und `last_run.duration_s` enthält die Nachzüglerzeit nicht.
  - Test: Go-Test mit verzögertem Fake-Server und kurzem Wartebudget; `in_flight` ist im selben Moment `1`.

- **AC-4:** Given beliebige Jobs (Fan-out und global) nach einem Lauf / When der Status abgefragt wird / Then
  trägt jedes `last_run` ein Feld `duration_s` größer oder gleich 0, und `last_run.time`, `last_run.status`,
  `overlap.skipped_since_last_run` und `users{}` haben unveränderte Namen, Typen und Bedeutung.
  - Test: Go-Test über alle Job-IDs; zusätzlich Vertragstest gegen die bisherigen Feldnamen.

- **AC-5:** Given ein frisch gestarteter Scheduler ohne Abbruch / When der Status abgefragt wird / Then enthält
  jeder Fan-out-Job `deadline_aborts` mit `total` gleich `0`, ohne `last_at`, mit gesetztem `counting_since`,
  und Nicht-Fan-out-Jobs enthalten den Block nicht.
  - Test: Go-Test; legt fest, dass „0" von „nicht anwendbar" unterscheidbar ist.

- **AC-6:** Given die Routen `/compare-alert-checks`, `/compare-official-alert-checks` und `/trip-reports` / When
  sie mit einem Nutzer aufgerufen werden / Then enthält die Antwort `duration_s` (Zahl größer oder gleich 0),
  `status`, `count`, `failed` bleiben unverändert, und im Log steht je Lauf genau eine Zeile „Lauf beendet nach"
  mit der `user_id`.
  - Test: `tests/tdd/test_scheduler_run_duration_reporting.py`, FastAPI-Testclient mit echten Diensten auf Fixture-Daten, `caplog`.

- **AC-7:** Given ein Trip-Alarmlauf über einen Trip mit mehreren Etappen / When der Lauf endet / Then steht im
  Log je Trip und je Etappe eine Dauerzeile, und das Gesamtergebnis (`checked`, `skipped`, `alerts_sent`) ist
  gleich dem Ergebnis ohne diese Messung.
  - Test: `tests/tdd/test_trip_alert_duration_logging.py`; Gegenprobe: Ergebnisobjekt vor/nach identisch.

- **AC-8:** Given N Threads (z. B. 12), die über eine `threading.Barrier` gleichzeitig einen Eintrag in das
  Alarm-Log desselben Nutzers schreiben / When alle fertig sind / Then enthält `alert_log.json` genau N
  Einträge, jeder genau einmal, und die Datei ist gültiges JSON.
  - Test: `tests/tdd/test_alert_log_concurrent_append.py`. **Gegenprobe Pflicht:** ohne Sperre (Mutation: `exclusive_lock` entfernen) wird der Test nachweislich rot (Eintragsverlust).

- **AC-9:** Given ein Schreibvorgang, dessen Serialisierung mitten im Schreiben scheitert (nicht
  serialisierbares Objekt) / When `alert_log`, `alert_state`, `weather_snapshot`, `compare_weather_snapshot`
  und der Verfügbarkeits-Cache jeweils so beschrieben werden / Then bleibt die vorherige Datei byte-genau
  unverändert und im Ordner liegt keine Temp-Leiche.
  - Test: `tests/tdd/test_state_writers_atomic.py`, je Schreiber ein Fall mit vorher geschriebenem Inhalt. Gegenprobe: mit `write_text` statt `atomic_write_json` wird er rot.

- **AC-10:** Given ein abgelaufener Verfügbarkeits-Cache und N gleichzeitige Abrufe / When alle gleichzeitig die
  Modellverfügbarkeit brauchen / Then läuft die Auto-Probe genau einmal, alle Abrufe sehen danach den
  gültigen Cache.
  - Test: `tests/tdd/test_openmeteo_availability_probe_single.py` mit `Barrier` und einem zählenden Probe-Ersatz an der HTTP-Grenze. Gegenprobe: ohne Sperre läuft die Probe mehrfach, Test rot.

- **AC-11:** Given ein Sperrhalter, der die Sperre auf `alert_log.json` über die Wartefrist hinaus hält (Frist im
  Test verkürzt) / When ein Eintrag geschrieben werden soll / Then wird er nicht still verworfen, sondern mit
  `ERROR` samt vollständigem Eintrag protokolliert, `alert_log_lost_entries` steigt um 1, die Datei bleibt
  unverändert, und der Aufrufer erhält keine Ausnahme.
  - Test: `tests/tdd/test_alert_log_lock_timeout_is_loud.py`.

- **AC-12:** Given `check-gregor20.sh` und ein Status mit `deadline_aborts.total` größer als der gespeicherte
  Wert / When das Skript läuft / Then gibt es eine WARN-Zeile mit Job-ID und Zuwachs aus, endet nicht mit FAIL,
  und bei unverändertem Wert sowie bei geändertem `counting_since` mit `total` 0 bleibt es ohne Warnung.
  - Test: Lauf der Skript-Kopie gegen Status-Attrappen (Zuwachs / gleich / Neustart), Ausgabe geprüft; bestehende Alarm-Job-Prüfungen unverändert grün.

## Geplante Tests

Deterministisch, ohne Netz, kein Mock-Theater, keine Dateiinhalt-Checks. Testdateien nach Verhalten benannt;
jeder Test löst seinen Prüfling relativ zur eigenen Datei auf (Worktree-sicher).

| Datei | Prüft |
|---|---|
| `internal/scheduler/deadline_abort_visibility_test.go` | AC-1 bis AC-5, mit **zwei Nutzern**, Fake-Python-Server mit echten Antwortkörpern |
| `tests/tdd/test_scheduler_run_duration_reporting.py` | AC-6 |
| `tests/tdd/test_trip_alert_duration_logging.py` | AC-7 |
| `tests/tdd/test_alert_log_concurrent_append.py` | AC-8, `threading.Barrier`, N Threads, **zwei Nutzer** (kein Übersprechen zwischen Dateien) |
| `tests/tdd/test_state_writers_atomic.py` | AC-9 |
| `tests/tdd/test_openmeteo_availability_probe_single.py` | AC-10 |
| `tests/tdd/test_alert_log_lock_timeout_is_loud.py` | AC-11 |
| Monitor-Probelauf (Kopie) | AC-12 |

**Mutations-Gegenprobe (Pflicht für den Adversary):** (1) Zähler beim `ok`-Lauf zurücksetzen ⇒ AC-1 rot;
(2) `skipped_ids` in den Body schreiben ⇒ AC-2 rot; (3) Nachzügler doppelt zählen ⇒ AC-3 rot;
(4) Sperre in `_append` entfernen ⇒ AC-8 rot; (5) `atomic_write_json` durch `write_text` ersetzen ⇒ AC-9 rot;
(6) Double-Check nach Sperrerwerb entfernen ⇒ AC-10 rot; (7) `LockTimeout` still schlucken ⇒ AC-11 rot.
Mutationen nur per String-Ersetzung mit externer Sicherungskopie. Konkurrenztests müssen zusätzlich mit der
Warnungs-Strenge des Testlaufs laufen (Thread-Ausnahmen dürfen nicht untergehen, C4-62).

## Wirkungsnachweis

**Vorher (Messung Produktion 2026-10-07):**

- 7 Tage `journalctl -u gregor-python`: 29× „Zeitobergrenze … überschritten" für einen Nutzer, jedes Mal
  `checked=2 skipped=2` (27× mit der alten 90-s-Grenze, 1× 180 s, 1× Radar 45 s).
- Seit der Anhebung auf 180 s (06.10.): in ca. 1,5 Tagen ein Trip-Alarm- und ein Radar-Abbruch.
  Nicht als „29 pro Woche" verkaufen: Der Schaden ist gedämpft, nicht beseitigt.
- Trip-Alarm-Laufdauer (n=2012): p50 0,01 s, p90 13,8 s, p95 37 s, p99 104 s, max 215 s.
- Go-Status zeigt in dieser Zeit `users.partial: 0` und keinen `overlap`-Block. Andere Jobs loggen keine Dauer.

**Nachher (nach Prod-Deploy, 7 Tage):**

- Sichtbarkeit: `deadline_aborts.total` und `last_run.duration_s` je Job im Status; der Monitor meldet WARN bei
  jedem Zuwachs. Erfolgskriterium dieser Scheibe ist, dass **jeder** in `journalctl` gezählte Abbruch seit
  dem Deploy auch im Status-Zähler steht (gleiche Anzahl, abgeglichen über `counting_since`).
- Messquelle für Dauer-Perzentile (p95/p99) und Abbruchzahl über Deploys hinweg: die Python-Logzeilen.
- **S0 + S1a senken die Abbruchzahl nicht.** Eine unveränderte oder gleiche Zahl ist hier das erwartete
  Ergebnis. Die Senkung wird erst mit S3 gemessen, gegen die hier erhobene Basis.
- Schutzgrößen, die nicht schlechter werden dürfen: Open-Meteo-Calls und -503 pro Tag, `cache_hits`,
  Einträge im Alarm-Log (nur mehr, nie weniger).

## Nicht in diesem Workflow

- Cache-Schlüssel-Rundung (teilen 2–4 km entfernte Etappen eine Kachel?), Provider-Semaphoren und der
  Umgang mit `fail_fast` im Briefing gehören zu S2 bzw. S5 und werden dort entschieden.
- Keine Parallelisierung, keine neue Laufgrenze für `compare_alert`/`compare_official` (S6).
- Kein Persistenzpfad für den Abbruch-Zähler; kein Eigenwert je Nutzer in `/status/me`.
- `forecast_budget.py`, `meteoalarm_budget.py`, `warn_egress.cached_fetch` (C4-64): S1b.

## Verbleibt in #1539 (Folge-Workflows)

Keine neuen Issues, #1539 bleibt offen. PR-Text „Refs #1539", nie „Closes".

| Scheibe | Inhalt |
|---|---|
| S1b | Cache und Budget: `cached_fetch` mit Sperre und Single-flight (C4-64), `ForecastBudgetGate.reserve()` atomar, Zähler bei fail-open, `meteoalarm_budget.py` analog |
| S2 | Baustein `src/services/parallel_fetch.py` (begrenzter Pool, Semaphore je Provider, ContextVars, Index-Reihenfolge) und Single-flight im Wetter-Cache |
| S3 | Trip-Alarm-Etappen über den Baustein (`trip_alert._fetch_fresh_weather`), größter Nutzen |
| S4 | Radar-Zonenpunkte (`RadarDeadlineExceeded` im Hauptthread neu werfen) |
| S5 | Trip-Briefing (`_fetch_weather`, Kopplung mit `fail_fast`) |
| S6 | Compare-Alarm und amtliche Warnungen: Abruf vorziehen, Laufgrenze ergänzen |
| S7 | Go-Nutzer-Fan-out, nur mit Messauslöser `not_reached_budget` größer 0 im Echtbetrieb |

## Affected Files

| Datei | Änderung | LoC ca. |
|---|---|---|
| `internal/scheduler/scheduler.go` | MODIFY: Antwortkörper, `partialRunError`, Dauer, Zähler, Status-Block | 100 |
| `internal/scheduler/deadline_abort_visibility_test.go` | CREATE | 150 |
| `api/routers/scheduler.py` | MODIFY: `duration_s`/`checked` für drei Routen | 25 |
| `src/services/trip_alert.py` | MODIFY: Dauer je Trip/Etappe | 20 |
| `src/services/compare_alert.py`, `compare_official_alert.py`, `compare_radar_alert.py`, `trip_report_scheduler.py` | MODIFY: Laufdauer messen/loggen | 40 |
| `src/services/file_lock.py` | MODIFY: optionaler `timeout_s` in `exclusive_lock` | 8 |
| `src/services/alert_log.py` | MODIFY: Sperre, atomar, lauter Timeout | 30 |
| `src/services/alert_state.py`, `weather_snapshot.py`, `compare_weather_snapshot.py` | MODIFY: `atomic_write_json` | 15 |
| `src/providers/openmeteo.py` | MODIFY: atomar, Probe-Sperre mit Double-Check | 25 |
| `tests/tdd/` (7 Dateien, s. o.) | CREATE | 200 |
| `docs/reference/api_contract.md` | MODIFY: additive Felder (zählt nicht ins LoC-Limit) | — |
| `/home/hem/henemm-infra/scripts/check-gregor20.sh` | MODIFY (anderes Repo): WARN bei Zuwachs | 20 |

## Known Limitations

- Der Abbruch-Zähler im Status steht nach jedem Deploy auf 0 (`counting_since` zeigt es an). Langzeitzahlen
  kommen aus dem Log.
- `duration_s` im Status enthält keine Nachzügler; ein hängender Aufruf zeigt sich über `in_flight`.
- Ein Abbruch nach dem Deploy und vor dem ersten Monitor-Lauf wird erkannt (Basis 0 bei neuem `counting_since`),
  ein Abbruch, der durch einen weiteren Neustart vor dem Check wieder auf 0 fällt, nicht.
- Der Status-Zähler ist über alle Nutzer aggregiert; wer betroffen ist, steht nur im Python-Log.

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** keine neue ADR.
- **Rationale:** additive Felder und Wiederverwendung des Helfers aus ADR-0083. Die Zähler-Lebensdauer
  (In-Memory plus `counting_since`) ist eine Detailentscheidung dieser Scheibe und ändert keine Grundsatzfläche.
  Die Entscheidung zur Parallelisierung selbst (ein Baustein, Trips/Nutzer seriell) wird mit S2 als ADR
  festgehalten.

## Changelog

- 2026-10-07: Initial spec created (Workflow feat-1539-parallele-abrufe, S0 + S1a)
