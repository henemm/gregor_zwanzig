# Context: feat-3323-servermessung

## Request Summary
Abschlussnachweis aus #3278 (dort AC-7, wortgleich in #3323): Auf dem Server, auf EINEM Commit, neben laufendem
Prod und Staging, erst den seriellen, dann den parallelen sicheren Offline-Volllauf messen; während des parallelen
Laufs `prod_selftest.py` ausführen. Ergebnis als Messprotokoll unter `docs/artifacts/`, Laufzeit in
`docs/reference/gates_und_ratschen.md` eintragen. Kein Produktcode.

## Related Files
| Datei | Rolle |
|---|---|
| `docs/reference/gates_und_ratschen.md` (Z. 256-276) | Wörtliche Formen seriell/parallel; Satz „Laufzeit der parallelen Form am Server noch nicht gemessen (#3323)“ wird ersetzt |
| `.claude/hooks/broad_test_run_gate.py` | Gate, vergleicht den Rohstring exakt; Messbefehle müssen die freigegebenen Literale wörtlich verwenden |
| `.claude/hooks/prod_selftest.py` | Prod-Selbsttest (Commit/Health/AC-Attestation), Exit 0 = grün |
| `docs/context/perf-3209-pytest-laufzeit.md` (Z. 58-75) | Methode der seriellen Referenz: Worktree des Prod-Checkouts, `/usr/bin/time -v`, junit-XML |
| `docs/context/rework-3278-lokaler-volllauf-parallel.md` | Herkunft, Schätzungen (`-n 2` ca. 30-35 min), offene Serverfrage |
| `docs/artifacts/feat-3323-servermessung/` | Ziel des Messprotokolls (neu) |

## Existing Patterns
- Referenzlauf 2026-11-22 lief in einem Worktree unter `~/gregor_zwanzig/.claude/worktrees/`, NICHT im Prod-Checkout
  selbst (Echtbaum-Tests schreiben unter `data/users` des Checkouts). Gemessen mit `/usr/bin/time -v` (Wanduhr,
  user/sys, CPU-%, Max-RSS) plus `--junitxml`. Ergebnis damals: 56:17 min, 51 % CPU, 0,9 GB, 9 failed / 2 errors
  (Server-Umgebungsartefakte, CI auf demselben Commit grün).
- Vergleichsgröße ist nicht „grün“, sondern: Laufzeit kleiner UND keine ZUSÄTZLICHEN Roten gegenüber seriell auf demselben Commit.

## Dependencies
- Serverzugang `ssh henemm` (Tailnet). Am 2026-11-27 ist eine Lese-Abfrage durchgegangen (Last 0,9, 4 Kerne,
  7 GB, ca. 4 GB verfügbar; `gregor-python` und `gregor-python-staging` aktiv). Der feste Prüfzugang
  `henemm-pruefen` kennt nur fünf Prüfbefehle, keinen Testlauf; daher `ssh henemm`.
- `uv`, `pytest-xdist` im Server-Checkout (CI nutzt xdist bereits, #3209).

## Dependents
- #3278 bleibt offen bis zu diesem Nachweis; danach schließbar.
- #1196 (Epic Testsuite-Laufzeit).

## Risks
- **Last neben Prod:** zwei Worker plus Controller ca. 2 GB RSS, ca. 1 Kern; `nice -n 10` ist Teil der Form. Bei
  ca. 4 GB verfügbarem Speicher tragbar; Selbsttest während des Laufs ist genau die Probe dafür.
- **Dauer:** zwei Läufe nacheinander, zusammen ca. 1,5 h; im Hintergrund auf dem Server (`nohup`/`systemd-run`
  im Wrapper-Skript), Gate-Literal steht unverändert im Skript.
- **Gate auf Rohstring:** ein `ssh henemm '… pytest …'` aus der Sitzung kann vom Hook geblockt werden; Messung über
  ein kleines Skript im Server-Worktree, das die wörtlichen Formen ausführt.
- **Gleichzeitige Läufe im selben Checkout** werden rot (gewollt) → eigener Worktree, Läufe streng nacheinander.
- **Scheitert die Messung** (nicht schneller, zusätzliche Rote, Selbsttest rot): laut Issue Neubewertung der Form
  (Rücknahme oder andere Worker-Zahl) mit Gate-Adversary, 2 Runden; das wäre ein eigener Schritt, nicht dieses Ticket.

## Analysis

**Type:** Messauftrag (Nachweis), kein Produkt- und kein Gate-Code. Score 2 → Kontext und Analyse kombiniert.

**Vorprüfung Server (2026-11-27, 13:48 Ortszeit Server):** `ssh henemm` erreichbar; 4 Kerne, Last ca. 0,9-1,4,
ca. 4 GB verfügbar, 42 GB Platte frei; Prod-Checkout auf `cf1a2db0d`; `.venv` mit pytest-xdist 3.8.0 und pytest-socket.

### Affected Files
| Datei | Change | Grund |
|---|---|---|
| `docs/artifacts/feat-3323-servermessung/messprotokoll.md` | CREATE | Nachweis: beide Läufe, Laufzeit, Spitzen-RSS/CPU, Rote je Lauf, Selftest |
| `docs/artifacts/feat-3323-servermessung/` Rohdaten (time-v-Ausgabe, Rote-Listen) | CREATE | Belege zum Protokoll (klein halten, keine junit-XML voll einchecken) |
| `docs/reference/gates_und_ratschen.md` (Z. 276) | MODIFY | „Seriell ca. 42 min; … noch nicht gemessen (#3323)“ ⇒ gemessene Werte beider Formen mit Datum |

Kein Code, keine Tests unter `src/`/`api/`; ±60 LoC Doku.

### Technical Approach (Messablauf)
1. Auf dem Server einen eigenen Worktree `~/gregor_zwanzig/.claude/worktrees/messung-3323` auf dem aktuellen
   `origin/main`-Commit anlegen (Methode wie Referenz 2026-11-22; nie im Prod-Checkout testen). `uv sync` dort.
2. Messskript im Worktree-Scratch (nicht eingecheckt), im Hintergrund per `nohup`:
   a) seriell: `/usr/bin/time -v` + wörtliche serielle Form (mit `--ignore=tests/red/`, damit beide Läufe dieselbe Menge
      sehen) `> seriell.txt 2>&1`, zusätzlich `--junitxml` NICHT anhängen (Gate-Literal), Rote aus der pytest-Zusammenfassung
      (`-rfE` ist nicht Teil des Literals → Rote aus den `FAILED`/`ERROR`-Zeilen der Kurzfassung bzw. `short test summary`).
   b) danach parallel: `/usr/bin/time -v` + wörtliche parallele Form `> parallel.txt 2>&1`.
   `/usr/bin/time -v` misst Wanduhr, CPU-% und Max-RSS je Prozess; für xdist (Controller + 2 Worker) zusätzlich
   Summen-RSS per Abtastung (`ps` alle 10 s über die Prozessgruppe, Maximum protokollieren), weil Max-RSS von `time`
   nur den größten Einzelprozess zeigt.
   Hinweis: Das Gate prüft Bash-Befehle der Claude-Sitzung, nicht ein Skript auf dem Server; die Literale stehen trotzdem
   wörtlich im Skript, damit genau die freigegebene Form gemessen wird.
3. Während des parallelen Laufs (etwa zur Halbzeit und einmal kurz vor Ende) `python3 .claude/hooks/prod_selftest.py`
   im Prod-Checkout ausführen (rein lesend: Commit-Attestation + HTTP-Proben gegen Prod), Exit-Code und Verdict festhalten.
   Vorher einmal ohne Last als Kontrollwert (falls der Selftest schon ohne Last nicht 0 liefert, ist das kein Lastbefund).
4. Auswertung: Laufzeit parallel < seriell; Menge Rote(parallel) ⊆ Rote(seriell) (Test-IDs); RSS/CPU beider Läufe;
   Selftest-Exit. Ergebnis ins Protokoll, Laufzeit in die Referenzdoku.

### Scope/Risk
- Risiko für Prod: mittel-niedrig. Zwei Worker unter `nice -n 10`, geschätzt ca. 2 GB RSS bei ca. 4 GB verfügbar.
  Abbruchkriterium im Messskript: fällt `MemAvailable` unter 1 GB, Lauf abbrechen und als „gescheitert (Speicher)“ protokollieren.
- Rote Tests sind kein Ausschlusskriterium, nur ZUSÄTZLICHE gegenüber seriell. Wackler (Timeout 30 s unter Last) können
  einzeln zusätzlich auftreten: dann den betroffenen Test einzeln (benannt) im Worktree nachlaufen lassen, Ergebnis
  protokollieren; die Bewertung bleibt beim AC-Wortlaut („keine zusätzlichen roten Tests“) — bei echter Zusatz-Rote
  gilt die Messung als gescheitert und es folgt das Folge-Issue zur Neubewertung.
- Dauer ca. 1,5 h Wanduhr; Sitzung wartet im Hintergrund (Monitor auf Ende-Marker), kein Polling in kurzen Abständen.

### TDD-Hinweis
Es gibt kein Verhalten, das ein roter Test zeigen könnte; der „Test“ ist die Messung selbst. Phase RED/GREEN wird
über den Workflow-Weg für Nachweis-/Doku-Aufträge abgewickelt (Protokoll als Artefakt); falls ein Gate einen roten
Test verlangt, Doku-Konsistenztest prüfen (`# doc-compliance-test` nur, wenn nötig).

### Open Questions
Keine Produktfrage. (Worker-Zahl 2 ist in #3278 festgelegt; dieses Ticket misst nur.)
