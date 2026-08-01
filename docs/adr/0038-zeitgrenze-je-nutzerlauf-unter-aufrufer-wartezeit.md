# ADR-0038: Jeder wiederkehrende Job-Lauf bekommt eine Zeitgrenze unter der Wartezeit seines Aufrufers

- **Status:** Akzeptiert
- **Datum:** 2026-08-01
- **Bezug:** GitHub-Issue #1447 (Ursprung: henemm-infra#147), Spec `docs/specs/modules/fix_1447_s1_alarm_lauf_zeitgrenze.md`

## Kontext

Der Go-Scheduler ruft die Python-Trigger-Endpunkte (`/api/scheduler/*`) synchron
mit einem geteilten HTTP-Client-Timeout von 120 Sekunden auf
(`internal/scheduler/scheduler.go:82`). Der Python-Lauf hinter diesen
Endpunkten kennt diese Wartezeit nicht und hat selbst keine Obergrenze —
weder für die Summe seiner Arbeit (z. B. `check_all_trips()` iteriert über
alle Trips eines Nutzers ohne Gesamtbudget) noch für einzelne mögliche
Blockierer.

Drei belegte Vorfälle (30.07., zweimal 31.07.2026, `journalctl -u gregor-api`)
zeigten `context deadline exceeded` nach genau 120 Sekunden, während der
Normalfall unter einer Sekunde liegt. Die Ursache im Einzelfall ließ sich aus
den Produktionsdaten **nicht** rekonstruieren — kein Netzabruf, keine
Logzeile, keine geschriebene Statusdatei im Vorfallsfenster. Das ist selbst
ein Befund: Ohne eigene Zeitgrenze kann ein Job unbegrenzt lange laufen, ohne
dass irgendetwas davon sichtbar wird, bis der Aufrufer die Verbindung kappt.

Im Repository existiert bereits ein etabliertes Muster für genau dieses
Problem auf Ebene einzelner Provider-Abrufe (`FETCH_DEADLINE_SECONDS` in
`src/providers/meteofrance.py`/`dwd.py`: monotone Uhr, Prüfung vor jedem
Einzelschritt, sichtbarer Fehler statt stillem Teilergebnis). Es existiert
aber **kein** Grundsatz für die nächsthöhere Ebene — den wiederkehrenden
Job-Lauf als Ganzes, der von einem externen Aufrufer mit eigener Wartezeit
angestoßen wird. Beide bestehenden Retry-Specs (#1128, #1155) haben das
geprüft und ausdrücklich festgehalten, dass hierzu kein ADR existiert.

## Entscheidung

Jeder wiederkehrende Job-Lauf, der von einem Aufrufer mit eigener
Wartezeit-/Timeout-Grenze angestoßen wird, bekommt eine **harte eigene
Zeitobergrenze**, die spürbar unter dieser Aufrufer-Wartezeit liegt.

Wird die Obergrenze gerissen, bricht der Lauf **sichtbar** ab: er meldet
**Teilerfolg** (was er bis dahin geschafft hat, was er ausgelassen hat,
warum), statt entweder unbegrenzt weiterzulaufen oder einen Vollerfolg
vorzutäuschen. Der Abbruch wird sowohl im Rückgabewert des Laufs als auch im
Log festgehalten (siehe ADR-0018: Ausweichen ja, Kaschieren nein).

Diese Zeitgrenze ist eine **Konstante im Code des Jobs selbst**, nicht eine
Anhebung der Aufrufer-Wartezeit — der Aufrufer bekommt dadurch keine neue
Verantwortung, und der Job bleibt für sich genommen beobachtbar und
begrenzbar.

## Verworfene Alternativen

- **Aufrufer-Wartezeit anheben** (z. B. Go-Timeout von 120 s auf 300 s). Das
  war der ursprüngliche Vorschlag im Issue. Verworfen, weil der
  Go-Cron-Scheduler ohne Überlappungsschutz läuft (`cron.New()` ohne
  `cron.WithChain(cron.SkipIfStillRunning(...))`,
  `internal/scheduler/scheduler.go:79`) und die Wartezeit **pro Nutzer**
  gilt: bei mehreren Nutzern reißen schon wenige langsame Läufe den
  15-Minuten-Takt, und zwei überlappende Läufe schreiben gleichzeitig in
  denselben Zustand (`lastRuns`). Eine höhere Wartezeit vergrößert das
  Zeitfenster für genau dieses Problem, statt es zu verkleinern. Der
  Überlappungsschutz selbst ist als eigene Maßnahme vorgesehen (Fix #1447
  Scheibe S2), ersetzt aber nicht die Notwendigkeit einer job-eigenen Grenze.
- **Keine eigene Grenze, stattdessen nur besseres Logging.** Verworfen, weil
  Sichtbarkeit allein das eigentliche Risiko nicht schließt: ein Job ohne
  Obergrenze kann weiterhin beliebig lange Ressourcen (Thread, Dateisperren,
  Verbindungen) binden und Folge-Nutzer verzögern, unabhängig davon, ob der
  Vorfall danach im Log sichtbar ist.
- **Globales, für alle Jobs identisches Zeitbudget an einer zentralen
  Stelle.** Verworfen für den Moment, weil die Aufrufer-Wartezeiten je nach
  Job unterschiedlich sind (unterschiedliche HTTP-Clients/Timeouts je nach
  Aufrufpfad) und eine zentrale Konstante entweder für manche Jobs zu knapp
  oder für andere zu großzügig wäre. Diese Entscheidung schreibt das
  **Prinzip** fest (Grenze unter Aufrufer-Wartezeit), nicht eine einzelne
  globale Zahl.

## Konsequenzen

- **Positiv:** Ein hängender oder ungewöhnlich langsamer Lauf kann den
  Aufrufer nicht mehr unbemerkt in einen Timeout laufen lassen, dessen
  Ursache im Nachhinein nicht mehr feststellbar ist. Teilerfolg ist von
  Totalausfall unterscheidbar, sowohl im Rückgabewert als auch im Log.
- **Negativ / Preis:** Zusätzliche Konstante und Prüfpunkt in jedem
  betroffenen Job; bei künftigen Änderungen an der Aufrufer-Wartezeit muss
  die Job-Konstante mitgezogen werden, sonst verliert sie ihre Reserve oder
  wird unnötig eng.
- **Folgepflichten:** Neue wiederkehrende Jobs, die von einem Aufrufer mit
  eigener Wartezeit angestoßen werden, brauchen ab sofort dieselbe
  Betrachtung — eine eigene Obergrenze unter der Aufrufer-Wartezeit, sichtbar
  gemeldeter Teilerfolg bei Überschreitung. Diese Entscheidung begrenzt
  ausdrücklich nur die **Summe** der Arbeit eines Laufs, nicht einzelne in
  sich unbegrenzt blockierende Schritte (SMTP ohne Timeout, ungedeckelte
  Warteschleifen, Dateisperren ohne Timeout) — diese Klasse ist gesondert zu
  behandeln (Issue #1448) und wird durch dieses ADR nicht abgedeckt.
