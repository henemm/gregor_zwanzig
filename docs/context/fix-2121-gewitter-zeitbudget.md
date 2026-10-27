# Context: fix-2121-gewitter-zeitbudget

> **Ausgang:** Der Workflow wurde für #2121 gestartet und in Phase 1 beendet, weil die
> Recherche ergab, dass **beide** Symptome des Tickets bereits aufgeklärt sind. #2121 ist
> am 11.09.2026 geschlossen worden. Der dabei gefundene, unabhängige Befund lebt als
> **#2302** weiter. Dieses Dokument hält die Recherche fest, damit #2302 nicht bei null
> anfängt.

## Request Summary

#2121 meldete zwei Dinge: Météo-France liefert HTTP 401 bei der Blitzdichte, und der
Gewitter-Fallback hängt 30 s in `bz2.decompress`. Beides sollte behoben werden.

## Ergebnis: beide Symptome sind erledigt, keines durch neuen Code

| Symptom | Befund |
|---|---|
| HTTP 401 (Météo-France) | Messung 09.09.2026 zu #1647 (PR #2290): Zugang trägt vollständig — `GetCoverage` Blitzdichte **200**, mit leerem `apikey`-Header 401. Der August-401 bleibt unerklärt, läuft als Beobachtbarkeits-Thema in #1647 weiter. |
| „30 s in `bz2.decompress`" | War die Zeitgrenze des **Testwerkzeugs**, nicht des Abrufs. `test_ac3_all_seven_commands_produce_meaningful_content` fehlte der Timeout-Override seines Nachbarn; es griff der globale pytest-Default (30 s, `pyproject.toml`, #1210 AC-1). Gefixt 07.09.2026 unter #1196, Commit `814a1ab9`, in `main`; Marke heute auf `tests/tdd/test_issue_686_telegram_functional_live.py:144`. Isoliert mit `--timeout=600`: **1 passed in 52,52 s**. |

**Zusatzbeleg gegen die Retry-Kaskaden-Hypothese:** Der beobachtete Fehler war ein **401**.
`_is_retryable_error` (`src/providers/dwd_eu.py:154-163`) wiederholt nur bei
`{500,502,503,504}` sowie `ConnectError`/`ReadTimeout`. Ein 401 löst keine Wiederholung aus
— eine Retry-Kaskade ist von diesem Fehlerbild strukturell nicht erreichbar.

**Lehre:** Die runde Zahl „>30,0 s" war der Fingerabdruck eines Timeouts, und der Eintrag
`bz2.decompress` bezeichnete die Stelle, an der die Uhr ablief — nicht die Ursache.

## Der unabhängige Befund → #2302

Vier der fünf Wetterquellen prüfen ihr Zeitbudget nur **zwischen** zwei HTTP-Abrufen, nie
**während** eines Abrufs.

| Datei | Budget | Prüfung zwischen den Calls | Abruf |
|---|---|---|---|
| `src/providers/dwd.py` | `FETCH 180 s` (`:69`), `THUNDER 150 s` (`:119`) | `:341` | `:326` ohne `timeout=` |
| `src/providers/dwd_eu.py` | `THUNDER 25 s` (`:134`) | `:408` (`_thunder_budget_erschoepft`, `:275-285`) | `:315` ohne `timeout=` |
| `src/providers/meteofrance.py` | `FETCH 180 s` (`:93`), `THUNDER 45 s` (`:114`) | `:501` | `_request` (`:434`) reicht `timeout` nicht an `_request_once` (`:478`) durch |
| `src/providers/geosphere.py` | keines für `fetch` | — | `:320` ohne `timeout=`; Gewittersignal fest auf 3 s (`:134`) |

Alle vier: `TIMEOUT = 30.0`, `RETRY_ATTEMPTS = 5`, `RETRY_WAIT_MIN/MAX = 2/60`,
`httpx.ReadTimeout` **wiederholbar**, httpx-Client nur mit **Skalar**-Timeout (nirgends
`httpx.Timeout(connect=…, read=…)`). Ernstfall je Abruf: `5 × 30 s + 4 × bis 60 s ≈ 390 s`,
erst danach greift die Budgetprüfung wieder.

### Das Gegenmittel steht schon im Haus

`src/providers/openmeteo.py`, gebaut unter **#1448 S3**:
- `:666-673` schrumpfende Wartezeit `min(TIMEOUT, restzeit)`, übergeben an `:677`
- `:621` `stop=stop_after_attempt(RETRY_ATTEMPTS) | _stop_at_request_deadline` (`:304-313`)
- `:624` `before=_resolve_request_deadline` (`:286-301`) — Frist **einmal je Retry-Kette**

`docs/specs/modules/fix_1448_s3_telegram_openmeteo.md` formuliert die Anforderung wörtlich:
*„Die Zeitgrenze muss bereits innerhalb eines einzelnen `_request`-Aufrufs greifen."*
Es gibt **keine** gemeinsame Basisklasse — das Muster ist in jede Datei kopiert.

### Warum der Alarm-Pfad der empfindliche ist

`ALERT_RUN_DEADLINE_SECONDS = 90.0` (`src/services/trip_alert.py:66`) wird in
`check_all_trips` nur **zwischen den Touren** geprüft (`:867`), der Lauf ist seriell. Die
90 s sind bewusst unter den 120 s des Go-Schedulers gewählt (ADR-0038, #1447 S1).

### Der bestehende Wächter misst die Zusicherung nicht

`tests/tdd/test_dwd_eu_thunder_time_budget.py:43-95` zählt **Abrufe**, nicht **Zeit**
(`abrufe < ohne_zeitdruck`, `abrufe <= _ABRUF_SCHWELLE`). Ein 390 s hängender Abruf lässt
ihn grün. Eine Zusicherung muss als Obergrenze der **tatsächlich verstrichenen Zeit**
formuliert werden.

## Existing Patterns / Bausteine für den Nachweis

- `tests/tdd/test_mail_send_deadline.py:63-116` — `_HangingServer`: echter TCP-Server,
  nimmt an, antwortet nie, zählt Verbindungsversuche
- `tests/tdd/_dwd_eu_fixtures.py:54-72` — `eu_server(monkeypatch, verzoegerung_s=…)`
- `tests/tdd/test_meteofrance_direct_fallback.py:476-517` — Deadline-Konstante im Test auf
  Millisekunden setzen
- `tests/tdd/test_alert_run_deadline.py:234-256` — misst über **nicht** aufgerufene Trips

## Existing Specs & ADRs

- **ADR-0018** — Fallback ohne Kaschieren: 4xx nicht ausweichen, jedes Ausweichen markieren
- **ADR-0038** — Zeitgrenze je Nutzerlauf; **Punkt 94** nimmt „einzelne in sich unbegrenzt
  blockierende Schritte" ausdrücklich aus und verweist auf **#1448**
- **ADR-0047** Entscheidung 6 — Ersatzquelle bekommt volles eigenes Budget, keine Restzeit
- `docs/specs/modules/fix_1448_s1_mail_zeitgrenze.md` — „fest statt rollend", strukturelle
  Reserve `primaer_deadline = deadline_at - FALLBACK_RESERVE_SECONDS`
- `docs/specs/modules/fix_1448_s3_telegram_openmeteo.md` — die Vorlage für #2302

## Risks & Considerations

- **Nie beobachtet.** Braucht eine Gegenstelle, die annimmt und schweigt. Der 401 kann es
  nachweislich nicht auslösen. Produktionsprotokolle ergaben keine Treffer, aber die
  Leserechte des Laufs sind **nicht abgesichert** — zählt nicht als Beleg.
- Vier Provider + mögliche Zusammenführung zu einem geteilten Baustein: das
  250-Zeilen-Limit wird voraussichtlich nicht reichen.
- Zu scharfe Grenzen schneiden echte Daten weg — Gewitter ist eine Alarm-Eingangsgröße.
- Abgrenzung zu **#1993**: dort geht es um die **Sichtbarkeit** des Fehlers (429-Drosselung),
  hier um seine **Dauer**. Kein Konflikt.
