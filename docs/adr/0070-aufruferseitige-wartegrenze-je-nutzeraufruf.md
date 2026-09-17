# ADR-0070: Der Scheduler hört je Nutzeraufruf nach einem Wartebudget auf zu warten — der Aufgerufene arbeitet weiter

- **Status:** Akzeptiert (erweitert ADR-0038)
- **Datum:** 2026-09-16
- **Bezug:** GitHub-Issue #2149 Scheibe B, Spec `docs/specs/modules/fix_2149_scheduler_budget_teilb.md`

## Kontext

Der Go-Scheduler ruft innerhalb eines Fan-out-Jobs (z. B. `alert_checks`) die
Nutzer **sequenziell** auf (`docs/specs/modules/scheduler_multi_user.md:32`)
und wartete bisher je Nutzer auf die volle HTTP-Antwort. Seit Issue #1912 liegt
der geteilte Client-Timeout bei 3000 s. Ein einzelner hängender Nutzer konnte
dadurch alle übrigen Nutzer desselben Laufs um bis zu 50 Minuten verzögern —
für Alarm-Jobs im 15-Minuten-Takt heißt das: Alarme anderer Nutzer kommen
mehrere Takte zu spät. Scheibe A (#2149) hat diesen Zustand sichtbar und
alarmfähig gemacht, die Verzögerung selbst aber nicht beseitigt.

ADR-0038 legt fest, dass ein Job seine eigene Zeitgrenze **unter** der
Wartezeit seines Aufrufers trägt. Er sagt nichts darüber, was der Aufrufer tut,
wenn ein einzelner Aufruf trotzdem lange dauert.

## Entscheidung

1. **Wartebudget je Nutzeraufruf (aufruferseitig).** Der Scheduler startet den
   Aufruf in einer Goroutine und wartet höchstens ein Wartebudget (Alarm 300 s,
   Briefing 600 s). Danach bucht er den Nutzer als `budget` und macht mit dem
   nächsten Nutzer weiter. Der Aufruf wird **nicht abgebrochen** — Python
   arbeitet unverändert bis zum Ende weiter.
2. **Laufbudget je Job-Lauf** (Alarm 720 s, Briefing 1440 s je Teiljob). Ist es
   erschöpft, werden die restlichen Nutzer ohne Versuch als `not_reached`
   gebucht; die Nutzerreihenfolge rotiert je Lauf, damit nicht immer derselbe
   Nutzer hinten steht.
3. **In-Flight-Register.** Solange ein aufgegebener Aufruf eines Nutzers noch
   läuft, bekommt dieser Nutzer im Folgelauf **keinen** neuen Aufruf
   (`skipped_in_flight`). Faktisch entsteht dadurch je hängendem Nutzer
   **höchstens eine** zusätzliche Python-Anfrage — nie ein Stapel. Das
   Register lebt nur im Prozessspeicher.
4. **Deckel für Alarm-Aufrufe** (1800 s = zwei Takte): danach wird der Marker
   ohne jede Buchung freigegeben, ein später eintreffendes Ergebnis verworfen.
   Briefing-Aufrufe behalten den Client-Timeout (3000 s) als einzigen Deckel.
5. **Späte Ergebnisse zählen nicht rückwirkend.** Ein nach dem Wartebudget
   eingetroffenes Ergebnis wird nur informativ übernommen; es setzt die
   Fehlerserie nicht zurück. `budget`/`skipped_in_flight` zählen als Fehler
   (Alarm nach drei Läufen), `not_reached` als Teilerfolg.

## Verworfene Alternativen

- **Aufruf nach dem Wartebudget abbrechen (Context-Cancel).** Verworfen: Python
  läuft synchron weiter und bemerkt den Abbruch nicht; der Abbruch würde nur
  die Antwort wegwerfen und beim nächsten Tick sofort einen zweiten,
  parallelen Aufruf für denselben Nutzer erlauben.
- **Echtes paralleles Fan-out über alle Nutzer.** Verworfen für den Moment
  (heute 3 Nutzer): ändert die Sequenziell-Entscheidung aus
  `scheduler_multi_user.md:32` grundsätzlich und vervielfacht die Last auf dem
  Python-Core; bleibt einer eigenen Entscheidung bei ~8–10 Nutzern vorbehalten.
- **Client-Timeout wieder senken.** Verworfen: #1912 hat belegt, dass reguläre
  Einzelversände bis 319 s brauchen; ein kürzerer Timeout würde laufende
  Versände wieder als Fehler zählen.

## Konsequenzen

- **Positiv:** Ein hängender Nutzer verzögert andere höchstens um das
  Wartebudget, nicht mehr um bis zu 3000 s, und wird selbst über die
  bestehende Scheibe-A-Zählkette alarmfähig. `/api/scheduler/status` zeigt
  `in_flight`, `skipped_in_flight`, `not_reached_budget` als reine Zahlen.
- **Negativ / Preis:** Go-Scheduler und laufender Python-Aufruf dürfen erstmals
  bewusst auseinanderlaufen. Neustart-Restfenster: das Register ist nicht
  persistiert, ein Deploy während eines laufenden Hintergrundaufrufs kann im
  nächsten Tick eine zweite Anfrage für diesen Nutzer auslösen (Alarmpfad:
  bekannte Check-then-record-Lücke in `throttle_store.py`). `Scheduler.Stop()`
  wartet nicht auf Hintergrundaufrufe.
- **Folgepflichten:** Wer Wartebudget, Laufbudget, Deckel oder Takt ändert,
  muss die Herleitung (80 % des Takts, Deckel zwei Takte) mitziehen. Echte
  Parallelität der Nutzerschleife braucht ein neues ADR.
