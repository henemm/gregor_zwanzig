# Kontext: Provider-Ausfall-Alarm endet nie (#1421)

**Workflow:** fix-1421-provider-streak-karenz · **Track:** Standard (Intake-Summe 1)
**Erstellt:** 2026-07-29

## Auslöser

BetterStack-Vorfall „Gregor20 Wetterquellen", vom PO gemeldet. Untersuchung ergab: kein Defekt
am Produkt, sondern ein Alarm, der nach einem einminütigen Fremdsystem-Aussetzer nicht mehr
aufhört.

## Analyse

| Frage | Befund |
|---|---|
| Lag ein echter Ausfall vor? | Ja, aber nur am 2026-07-29 um 05:00:04 UTC für knapp eine Minute. Open-Meteo antwortete mit HTTP 503 `{"reason":"The service is overloaded"}`. Vier Abrufe betroffen, automatischer Retry und Modell-Fallback griffen. |
| Kontingentproblem? | Nein. 503 (Überlastung), nicht 429 (Limit). Abgrenzung zu #1329/#1348. |
| Aktueller Zustand der Quellen? | Direkt geprüft: Open-Meteo Forecast, Open-Meteo Ensemble und GeoSphere antworten mit HTTP 200 in unter 0,1 s. |
| Warum alarmiert es trotzdem? | `provider_error_streak_since` bleibt gesetzt, solange irgendein Fehler in den letzten 24 h liegt. Der externe Prüfer rechnet `now − streakStart` und eskaliert mit der Dauer. |
| Belegte Häufigkeit | Derselbe Vorfall löste am 28.07. 11:15, 28.07. 22:15 und 29.07. 11:15 aus. |

Zustandsabfrage zum Untersuchungszeitpunkt:

```
last_provider_error_at:       2026-07-29T05:00:05.066089+00:00
provider_error_streak_since:  2026-07-29T05:00:05Z
provider_errors_recent_count: 4
```

Beide Zeitstempel identisch — es gab genau eine Fehlerserie, und sie war beendet.

## Betroffene Dateien

| Datei | Art | Grund |
|---|---|---|
| `internal/scheduler/briefing_health.go` | ÄNDERN | `analyzeBriefingProviderErrors` (`:199`) und Aufrufstelle (`:118-121`) |
| `internal/scheduler/briefing_health_test.go` | ÄNDERN | neue Prüffälle, Bestandsfälle `:276-420` bleiben |

## Wichtigste Erkenntnis der Analyse

Die Lösung braucht **keinen neuen Parameter**. `providerErrorStreakGapThreshold = 2 * time.Hour`
existiert bereits, samt einer Begründung, die den Fix vollständig trägt: Briefings laufen etwa
stündlich, ein echter Dauerausfall erzeugt also Fehler in Abständen unter zwei Stunden. Die
Schwelle wird bisher nur rückwärts angewandt (Serienbeginn), nicht nach vorne (Serienende).

Mein ursprünglicher Vorschlag im Issue („30 Minuten Karenzzeit") war dadurch überflüssig und
wurde dort zurückgezogen.

## Risiko

Ein Fehler in dieser Änderung macht die Überwachung blind statt laut. Das ist die teurere
Richtung und der Grund, warum trotz ~5 Zeilen Umfang der Standard-Track statt Fast-Track
gewählt wurde.

## Abgrenzung

Nicht Teil dieses Vorgangs: die sporadischen `FAIL[EXT]: Open-Meteo Forecast API nicht
erreichbar` des Prüfers selbst — dieselbe 503-Episode aus seiner Sicht, kein eigener Defekt.
Ebenfalls nicht: `check-gregor20.sh` (Infrastruktur-Repo, Eskalationsstufen bleiben unberührt).
