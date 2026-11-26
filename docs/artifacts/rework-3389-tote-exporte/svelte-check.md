# svelte-check vor und nach der Löschung (#3389)

Befehl: `cd frontend && npx svelte-check --threshold error --output machine`

| Stand | Dateien | Fehler | Warnungen | Dateien mit Befund |
|---|---|---|---|---|
| vorher (RED-Commit 3eadb80ef, vor jeder Löschung) | 2255 | 32 | 70 | 49 |
| nachher (GREEN, Arbeitsstand) | 2233 | 32 | 70 | 49 |

Die Fehlerliste (Datei, Zeile, Meldung) ist vorher und nachher identisch (zeilenweiser Vergleich
der sortierten `ERROR`-Zeilen ohne Zeitstempel: keine Abweichung). Die 22 Dateien weniger sind die
21 gelöschten Testdateien und der gelöschte Prüfstand. Keine neuen Fehler, keine neuen Warnungen.
