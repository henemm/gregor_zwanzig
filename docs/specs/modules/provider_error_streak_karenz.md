# Provider-Ausfall-Alarm: Serie endet, wenn keine Fehler mehr kommen

**Issue:** #1421
**Workflow:** fix-1421-provider-streak-karenz
**Status:** Entwurf — wartet auf PO-Freigabe
**Created:** 2026-07-29
**Betroffen:** `internal/scheduler/briefing_health.go`, `internal/scheduler/briefing_health_test.go`

## Problem

Am 2026-07-29 um 05:00:04 UTC war Open-Meteo knapp eine Minute überlastet (HTTP 503,
`{"reason":"The service is overloaded"}`). Vier Abrufe schlugen fehl, das System wiederholte
und wich auf Ersatzmodelle aus. Danach kein einziger weiterer Fehler.

Der Überwachungszustand meldete dennoch acht Stunden später:

```
FAIL[EXT]: Wetter-Provider-Ausfall seit 8h (4 Fehler/24h, seit 2026-07-29T05:00:05Z)
ALERT: Gregor20 EXT — Heartbeat NICHT gepingt
```

Der Vorfall „Gregor20 Wetterquellen" löste dadurch in zwei Tagen dreimal aus (28.07. 11:15,
28.07. 22:15, 29.07. 11:15) — jedes Mal, ohne dass zum Alarmzeitpunkt ein Fehler vorlag.

## Ursache

`analyzeBriefingProviderErrors` (`briefing_health.go:199`) besitzt bereits die richtige
Schwelle:

```go
const providerErrorStreakGapThreshold = 2 * time.Hour
// Chosen at 2h: briefing slots fire on roughly hourly cadence, so a genuinely
// persistent channel outage produces errors well within 2h of each other […]
```

Sie wird jedoch **nur rückwärts** angewandt: Die Funktion läuft vom jüngsten Fehler zurück und
bricht ab, sobald die Lücke zwischen zwei Fehlern die Schwelle überschreitet. `streakStart` ist
damit korrekt der Beginn der letzten zusammenhängenden Serie.

**Ob diese Serie noch andauert, wird nie geprüft.** Ausgegeben wird sie, solange irgendein
Fehler in den letzten 24 Stunden liegt (`recent > 0`, `:118`). Der externe Prüfer rechnet
`now − streakStart` und eskaliert mit der Dauer (`check-gregor20.sh:158-163`: >1 h WARN,
>6 h CRITICAL, CRITICAL blockt den Heartbeat).

Damit sind ein einminütiger Aussetzer und ein achtstündiger Totalausfall im Alarm nicht
unterscheidbar.

## Lösung in einem Satz

Dieselbe Zwei-Stunden-Schwelle wird auch **nach vorne** angewandt: Liegt der jüngste Fehler
weiter zurück als die Schwelle, gilt der Ausfall als beendet.

Die im Code stehende Begründung trägt das wörtlich — ein echter Dauerausfall erzeugt Fehler in
Abständen *unter* zwei Stunden und bleibt dadurch sichtbar. Es wird **keine neue Schwelle**
eingeführt.

## Acceptance Criteria

- **AC-1:** Given der jüngste Provider-Fehler liegt länger zurück als die Lücken-Schwelle, When der Briefing-Gesundheitszustand abgefragt wird, Then meldet er keinen laufenden Ausfall mehr — das Feld für den Ausfallbeginn ist leer.

- **AC-2:** Given Provider-Fehler treten fortlaufend in Abständen unterhalb der Lücken-Schwelle auf, When der Zustand abgefragt wird, Then bleibt der gemeldete Ausfallbeginn der Start dieser Serie und wächst mit der Ausfalldauer — das Verhalten aus Issue #1115 AC-4 bleibt unverändert erhalten.

- **AC-3:** Given ein Ausfall ist nach AC-1 als beendet gemeldet, es gab aber Fehler in den letzten 24 Stunden, When der Zustand abgefragt wird, Then bleibt die Fehleranzahl der letzten 24 Stunden unverändert sichtbar — die Häufigkeitsangabe geht nicht verloren und blockiert den Heartbeat weiterhin nicht.

- **AC-4:** Given kein laufender Ausfall liegt vor, When der Zustand als JSON ausgeliefert wird, Then enthält das Feld für den Ausfallbeginn einen echten Leerwert und nicht die leere Zeichenkette — der externe Prüfer unterscheidet beides.

- **AC-5:** Given die bestehenden Prüffälle aus `briefing_health_test.go:276-420`, When die Änderung angewandt ist, Then bleiben sie unverändert grün — insbesondere der Fall „nur ein alter Fehler ergibt keinen Ausfallbeginn" und der Fall „inhaltlicher 4xx-Fehler zählt nicht als Provider-Ausfall".

## Was sich nicht ändern darf

- Die Schwelle selbst (2 Stunden) und ihre Begründung.
- `provider_errors_recent_count` als 24-Stunden-Häufigkeitssignal.
- Die Eskalationsstufen des externen Prüfers (`check-gregor20.sh`) — dort wird nichts angefasst.
- Das Fail-soft-Verhalten: fehlende oder unlesbare Diagnosedatei führt weiterhin zu „kein
  Befund", nie zu einem Absturz.

## Die eine Gefahr, die zu prüfen ist

Ein Fehler in dieser Änderung macht die Überwachung **blind** statt laut. Der Adversary hat
genau eine Frage zu beantworten: **Kann ein echter, andauernder Ausfall nach dieser Änderung
unbemerkt bleiben?** Zu prüfen ist insbesondere ein Ausfall mit Fehlerabständen knapp unterhalb
und knapp oberhalb der Schwelle.

## Testplan

| Test | Prüft |
|---|---|
| Einzelner Fehler, dann Ruhe jenseits der Schwelle | AC-1 |
| Fehlerserie mit Abständen unter der Schwelle, über Stunden | AC-2 |
| Beendeter Ausfall, aber Fehler innerhalb 24 h | AC-3 |
| Feldtyp im ausgelieferten JSON | AC-4 |
| Bestandsfälle `briefing_health_test.go:276-420` | AC-5 |
| Fehlerabstände exakt an der Schwelle (darunter/darüber) | Adversary-Frage |

Alle Tests sind deterministisch (Go, feste Zeitstempel, keine Netzabhängigkeit) — die Funktion
nimmt `now` bereits als Parameter entgegen.

## Umfang

Zwei Stellen in `internal/scheduler/briefing_health.go`:
1. `analyzeBriefingProviderErrors` (`:199`) — Prüfung des Abstands zum jüngsten Fehler.
2. Aufrufstelle (`:118-121`) — leeren Ausfallbeginn nicht als Wert übernehmen.

Geschätzt ~5 Zeilen Produktivcode, dazu die Prüffälle.
