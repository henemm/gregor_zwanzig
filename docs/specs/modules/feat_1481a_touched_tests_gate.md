# Spec: Commit-Gate „Tests der berührten Dateien"

- **Issue:** #1481 Scheibe A
- **Workflow:** `feat-1481a-leser-vorlage`
- **created:** 2026-08-03
- **Kontext & Messungen:** `docs/context/feat-1481a-leser-vorlage.md`
- **Status:** Entwurf — wartet auf PO-Freigabe der Acceptance Criteria

## Zweck in einem Satz

Ein Commit kommt nicht mehr durch, wenn er einen Test rot macht, der zu einer der geänderten
Dateien gehört — geprüft wird beim Commit, nicht später.

## Warum

Bei #1453 stand der passende Wächter **zwei Tage rot** und meldete den Fehler korrekt; gelesen
hat den Lauf niemand. Der Fehler fiel erst durch ein Audit auf. Die Information war da, sie
hat nur nichts blockiert. Genau das ändert diese Scheibe.

Verallgemeinert das seit #811 bewährte `renderer_mail_gate.py` (verlangt für Mail-Dateien
einen grünen Testlauf vor dem Commit), statt ein zweites Werkzeug danebenzustellen.

## Acceptance Criteria

**AC-1: Roter Test der berührten Datei blockiert den Commit**
Given eine Änderung an `src/<modul>.py`, zu der eine Testdatei gehört, und diese Testdatei
schlägt fehl
When `git commit` ausgeführt wird
Then bricht der Vorgang ab, und die Meldung nennt die fehlgeschlagenen Tests namentlich sowie
den Befehl, mit dem sie einzeln nachgestellt werden können.

**AC-2: Grüne Tests lassen den Commit unverändert durch**
Given eine Änderung, deren zugehörige Tests alle bestehen
When `git commit` ausgeführt wird
Then läuft der Commit ohne Zutun durch, und die zusätzliche Wartezeit beträgt bei einer
typischen Änderung höchstens 30 Sekunden (gemessener Richtwert: 9 s für 236 Tests).

**AC-3: Was vorher schon rot war, blockiert nicht — gemessen, nicht geglaubt**
Given ein Test, der bereits im letzten Commit fehlschlug
When ein Commit eine zugehörige Quelldatei ändert, ohne neue Fehlschläge zu erzeugen
Then läuft der Commit durch, und die Meldung weist auf den vorbestehenden Fehlschlag hin,
ohne zu blockieren. Der Vorzustand wird an einem **Wegwerf-Abzug des letzten Commits
gemessen** — es gibt keine gepflegte Liste bekannter Fehlschläge.

**AC-4: Aus grün wird rot — die Gegenprobe**
Given derselbe Test, der im letzten Commit noch bestand
When die Änderung ihn zum Fehlschlagen bringt
Then blockiert der Commit. AC-3 und AC-4 zusammen sind die Zusicherung: ohne AC-4 wäre
„blockiert nicht" trivial erfüllbar, indem das Gate nie blockiert.

> **Warum keine Bestandsliste** (Adversary-Runden 1 und 2, beide CRITICAL): Der erste
> Entwurf hielt bekannte Fehlschläge in einer Datei. Sie ließ sich mit einem einzigen
> Schreibzugriff fälschen. Die Bindung an den committeten Stand verschob das Problem nur:
> Ein Commit, der ausschließlich diese Liste ändert, berührt keine Quelldatei und läuft am
> Gate vorbei — in zwei Schritten blieb die Ratsche wertlos. **Eine Liste, die gepflegt
> werden muss, ist immer fälschbar.** Kosten der Messung: ein zweiter Testlauf, und zwar
> nur, wenn überhaupt etwas rot ist (am echten Repo gemessen: 8 s → 14 s).

**AC-5: Kein Versand durch das Gate**
Given ein Commit berührt Dateien, deren Tests Live-Marker tragen (`live`, `email`, `staging`)
When das Gate seinen Testlauf startet
Then werden diese Tests ausgeschlossen, und es geht keine echte Mail, Telegram-Nachricht oder
SMS hinaus.

**AC-6: Zuordnung Datei → Tests ist nachvollziehbar und leer-sicher**
Given eine geänderte Quelldatei
When das Gate die zugehörigen Tests bestimmt
Then nutzt es die Nennung des Moduls in Testdateien und meldet, welche Testdateien es
gefunden hat; findet es keine, lässt es den Commit durch und sagt ausdrücklich „keine
zugehörigen Tests gefunden" — Schweigen ist nicht zulässig.

**AC-7: Eigene Fehler blockieren niemals die Arbeit**
Given das Gate selbst scheitert (Zeitüberschreitung, defekter Bestand, pytest nicht
aufrufbar)
When `git commit` ausgeführt wird
Then läuft der Commit durch, und die Störung wird sichtbar gemeldet. Ein defektes Gate darf
nie die Ursache dafür sein, dass nicht mehr gearbeitet werden kann.

**AC-8: Nur Commits, aber alle drei Schichten**
Given ein Bash-Aufruf, der kein `git commit` ist, oder ein Commit ohne geänderte Quelldateien
When das Gate greift
Then tut es nichts und verzögert nichts messbar. Als Quelldateien gelten `.py` unter `src/`
und `api/`, `.go` unter `internal/` und `cmd/`, sowie `.svelte`/`.ts` unter `frontend/src/`.

**AC-10: Go-Änderungen werden über ihr Paket geprüft**
Given eine Änderung an `internal/<paket>/<datei>.go`
When das Gate läuft
Then führt es die Tests genau dieses Pakets aus (`go test ./internal/<paket>/`) und wendet
dieselben Regeln an wie auf die Python-Schicht (AC-1 bis AC-4, AC-7). Gemessener Richtwert:
8 Sekunden kalt, 0 Sekunden bei unverändertem Paket-Cache.

**AC-11: Frontend-Änderungen werden über ihre Testdatei geprüft**
Given eine Änderung an einer Komponente oder einem Modul unter `frontend/src/`
When das Gate läuft
Then führt es die zugehörigen Testdateien mit dem Projektlauf (`node --import
./test-lib-loader.mjs --experimental-strip-types --test`) aus; es gelten dieselben Regeln
wie oben. Gemessener Richtwert: ~1 Sekunde je Testdatei.

**AC-12: Das Gate sagt, was es NICHT geprüft hat**
Given ein Commit berührt Dateien mehrerer Schichten, und eine davon lässt sich nicht prüfen
(Werkzeug fehlt, Abhängigkeiten nicht installiert, keine Tests gefunden)
When das Gate durchläuft
Then nennt die Meldung ausdrücklich die ungeprüfte Schicht. „Commit ging durch" darf nie den
Eindruck erwecken, alles sei geprüft worden — der Fall `An 0 Empfänger` (#1471) saß in einer
Svelte-Datei und wäre einem reinen Python-Gate entgangen.

**AC-9: Der Nachweis prüft Wirkung, nicht Anwesenheit**
Given der Verhaltensnachweis dieser Scheibe
When er läuft
Then arbeitet er auf einem Wegwerf-Repository mit echten Dateien und echtem `git commit`,
ohne Netz — und belegt sowohl das Blockieren (AC-1) als auch das Durchlassen (AC-2, AC-3,
AC-7). Ein Test, der nur die Anwesenheit von Zeichenketten im Hook prüft, zählt nicht.

## Nicht in dieser Scheibe

- Die Pendant-Sperre für neue einseitige Dateien (#1481, eigene Scheibe)
- Der Abschluss-Hook nach dem PO-Kurzbefehl (#1481, eigene Scheibe)
- Rückbau von `renderer_mail_gate.py` — die Mail-Regel bleibt strenger und unberührt

## Regel-Budget

Neues Gate → **Prüfdatum 2026-11-03**. Bis dahin muss ein belegter Fang vorliegen
(mindestens ein Commit, den es zu Recht blockiert hat), sonst Rückbau. Eintrag im
Gate-Audit #1197.

## Umfang

4 Dateien, geschätzt +300 LoC (drei Zuordnungsregeln statt einer). **LoC-Grenze für diese
Lieferung einmalig auf 400 angehoben — PO-Freigabe 2026-08-03**, Begründung: Ein Gate, das
nur eine von drei Schichten prüft und bei den anderen schweigt, erzeugt falsche Sicherheit
(AC-12).

Risiko MITTEL: Das Gate betrifft jeden Commit — deshalb ist AC-7 (fail-open) nicht
verhandelbar.

## Gemessene Grundlagen (Analyse, nicht Annahme)

| Schicht | Zuordnung | Laufzeit |
|---|---|---|
| Python | Modulnennung in Testdateien | 9 s / 236 Tests (20 Dateien, `compare_html.py`) |
| Go | Datei → ihr Paket | 8 s kalt · 0 s warm (`internal/handler`) |
| Frontend | Testdatei je Komponente | ~1 s je Datei |

Werkzeug-Fund am Rande: `pytest-socket` ist **nicht installiert**, obwohl CLAUDE.md
`--disable-socket` als sicheren Weg nennt. Für dieses Gate genügt der Marker-Ausschluss
(AC-5); der Widerspruch in der Regel geht als Sammel-Eintrag weiter.
