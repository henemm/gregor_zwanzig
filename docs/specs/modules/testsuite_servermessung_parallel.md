---
entity_id: testsuite_servermessung_parallel
type: module
created: 2026-11-27
updated: 2026-11-27
status: draft
version: "1.0"
workflow: feat-3323-servermessung
tags: [testsuite, messung, nachweis, gates, "#3323", "#3278", "#1196"]
---

# Servermessung des parallelen sicheren Offline-Volllaufs

## Approval

- [ ] Approved

## Purpose

Messauftrag und Nachweis, kein Produkt- und kein Gate-Code: Auf dem Server wird der serielle und danach der parallele sichere Offline-Volllauf (die beiden wörtlichen Gate-Formen) auf demselben Commit neben laufendem Prod und Staging gemessen. Das Ergebnis schließt den Abschlussnachweis aus #3278 (AC-7, abgetrennt als #3323, Teil von Epic #1196) und ersetzt in der Referenzdoku den Satz „noch nicht gemessen".

## Source

- **File:** `docs/artifacts/feat-3323-servermessung/messprotokoll.md` (neu), `docs/reference/gates_und_ratschen.md` (Abschnitt „Breiter Testlauf gesperrt", Satz „Seriell ca. 42 min; …")
- **Identifier:** Messprotokoll beider Läufe; Satz zur Laufzeit am Ende des Abschnitts „Breiter Testlauf gesperrt"

Schicht: weder Frontend, Go-API noch Python-Core; reine Doku/Artefakte. Gemessen wird auf dem Server in einem eigenen Worktree (`~/gregor_zwanzig/.claude/worktrees/messung-3323`), nie im Prod-Checkout.

Querschnitts-Prüfpunkte: kein Trip/Compare-Pendant (keine Komponente); keine Nutzerdaten bewegt (Echtbaum-Tests schreiben nur im Mess-Worktree, deshalb nie im Prod-Checkout); keine Briefing- oder Alarm-Inhalte, daher keine Kanalwirkung.

## Scope

Im Scope: zwei Messläufe (seriell, dann parallel) auf dem Server in einem eigenen Worktree auf einem Commit, Prod-Selftest während des parallelen Laufs, Messprotokoll, Laufzeitangabe in der Referenzdoku. Nicht im Scope: Änderungen am Gate, an der Worker-Zahl oder an Tests; eine Neubewertung bei Misserfolg läuft als Folge-Issue.

## Estimated Scope

- **LoC:** ca. +60/-1 (Doku)
- **Files:** 3 (Messprotokoll, kleine Rohdaten-Auszüge, Referenzdoku) plus optionaler Doku-Test
- **Effort:** low (Arbeit, aber ca. 1,5 h Wanduhr für zwei Läufe)

### Affected Files

| File | Change Type | Description |
|------|-------------|-------------|
| `docs/artifacts/feat-3323-servermessung/messprotokoll.md` | CREATE | Nachweis: beide Läufe nacheinander, Laufzeit, Spitzen-RSS/CPU, rote Tests je Lauf, Selftest-Ergebnis |
| `docs/artifacts/feat-3323-servermessung/` (Rohdaten-Auszüge: time-v-Ausgabe, Rote-Listen, RSS-Abtastung) | CREATE | Belege zum Protokoll, klein halten, keine volle junit-XML |
| `docs/reference/gates_und_ratschen.md` | MODIFY | Satz „Seriell ca. 42 min; … noch nicht gemessen (#3323)" durch gemessene Werte beider Formen mit Datum und Commit ersetzen |
| `tests/test_servermessung_doku.py` | CREATE (optional) | `# doc-compliance-test`: Protokoll existiert, Referenzdoku ohne „noch nicht gemessen (#3323)" |

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `docs/reference/gates_und_ratschen.md` Z. 250-290 | Doku | Die zwei wörtlichen Gate-Formen (seriell, parallel `-n 2`) |
| `.claude/hooks/broad_test_run_gate.py` | Hook | Vergleicht den Rohstring exakt; Messskript nutzt die Literale unverändert |
| `.claude/hooks/prod_selftest.py` | Hook | Prod-Selbsttest, Exit 0 = grün, läuft während des parallelen Laufs |
| `docs/context/perf-3209-pytest-laufzeit.md` Z. 58-75 | Kontext | Methode der seriellen Referenz (Worktree, `/usr/bin/time -v`, junit-XML); Referenz 56:17 min vom 2026-11-22 |
| `docs/context/rework-3278-lokaler-volllauf-parallel.md` | Kontext | Herkunft der parallelen Form, Schätzung `-n 2` ca. 30-35 min |
| Server `ssh henemm` (4 Kerne, ca. 7 GB, ca. 4 GB verfügbar) | Infrastruktur | Messort neben laufendem Prod und Staging |
| `uv`, `pytest-xdist`, `pytest-socket` im Server-Worktree | Werkzeug | Ausführung beider Formen |

## Implementation Details

Ablauf (Details in `docs/context/feat-3323-servermessung.md`, Abschnitt Analysis):

1. Eigener Server-Worktree auf dem aktuellen `origin/main`-Commit, `uv sync`. Beide Läufe auf diesem einen Commit.
2. Kleines Messskript im Worktree-Scratch (nicht eingecheckt), per `nohup` im Hintergrund. Es führt die zwei Gate-Formen wörtlich aus, jeweils mit `/usr/bin/time -v` davor und ` > datei 2>&1` dahinter, streng nacheinander: erst seriell, dann parallel.
3. Spitzen-RSS des parallelen Laufs per Abtastung (`ps` alle ca. 10 s über die Prozessgruppe), Summe Controller plus Worker, Maximum protokollieren; zusätzlich CPU-% und Max-RSS aus `time -v`.
4. Sicherheitsabbruch: Das Skript prüft `MemAvailable` mit; fällt der Wert unter 1 GB, wird der Lauf abgebrochen und als „gescheitert (Speicher)" protokolliert.
5. Während des parallelen Laufs `prod_selftest.py` im Prod-Checkout (rein lesend), etwa zur Halbzeit und kurz vor Ende; vorab ein Kontrollwert ohne Last.
6. Auswertung: Laufzeit parallel < seriell; rote Test-IDs (parallel) ⊆ rote Test-IDs (seriell); jede zusätzliche Rote im parallelen Volllauf heißt AC-2 nicht erfüllt; ein benannter Einzelnachlauf wird nur zur Einordnung protokolliert und heilt nichts. Ergebnis ins Protokoll, Laufzeiten in die Referenzdoku.
7. Ausgang: Erfolg ⇒ #3278 kann geschlossen werden. Misserfolg ⇒ Messung als gescheitert protokollieren, Folge-Issue zur Neubewertung (Rücknahme oder andere Worker-Zahl, Gate-Adversary 2 Runden) anlegen, #3278 bleibt offen.

## Expected Behavior

- **Input:** Server-Worktree auf einem Commit; die zwei wörtlichen Gate-Formen; laufendes Prod und Staging.
- **Output:** Messprotokoll mit beiden Läufen und Referenzdoku mit gemessenen Laufzeiten.
- **Side effects:** Zusätzliche Last auf dem Server während ca. 1,5 h (parallele Form unter `nice -n 10`); keine Änderung an Prod-Daten oder Prod-Checkout.

## Test Plan

Es gibt kein Verhalten im Code, das ein roter Test zeigen könnte; der Nachweis ist das Messprotokoll selbst. Optional:

- [ ] doc-compliance-Test (`# doc-compliance-test`): `docs/artifacts/feat-3323-servermessung/messprotokoll.md` existiert, und `docs/reference/gates_und_ratschen.md` enthält keinen Satz „noch nicht gemessen (#3323)" mehr.

## Acceptance Criteria

- **AC-1:** Given ein Abschlusslauf auf dem Server, auf demselben Commit wie die serielle Baseline und neben laufendem Prod und Staging / When die parallele Form einmal vollständig läuft und währenddessen `prod_selftest.py` ausgeführt wird / Then ist die Laufzeit kleiner als seriell auf demselben Commit und Server (Referenz 56:17 min vom 2026-11-22, anderer Commit)
  - Test: Das Messprotokoll nennt beide Wanduhr-Laufzeiten desselben Commits nebeneinander; parallel ist kleiner als seriell.

- **AC-2:** Given beide Läufe auf demselben Commit / When die roten Tests je Lauf ausgewertet werden / Then gibt es keine zusätzlichen roten Tests gegenüber der seriellen Baseline auf demselben Commit
  - Test: Das Protokoll listet die roten Test-IDs je Lauf; die parallele Menge ist Teilmenge der seriellen. Jede zusätzliche Rote, auch ein Wackler, bedeutet: AC-2 nicht erfüllt, Messung gescheitert (siehe AC-8). Ein benannter Einzelnachlauf dient nur der Einordnung im Protokoll und macht AC-2 nicht grün.

- **AC-3:** Given der parallele Lauf auf dem Server / When er läuft / Then sind Spitzen-RSS und CPU gemessen und protokolliert
  - Test: Das Protokoll enthält für beide Läufe CPU-% und Max-RSS aus `/usr/bin/time -v` sowie die Spitzen-RSS-Abtastung des parallelen Laufs.

- **AC-4:** Given der parallele Lauf läuft neben Prod / When `prod_selftest.py` währenddessen ausgeführt wird / Then ist der Prod-Selftest während des Laufs grün (Exit 0)
  - Test: Das Protokoll nennt Zeitpunkt, Exit-Code und Verdict jedes Selftest-Aufrufs während des Laufs sowie den Kontrollwert ohne Last.

- **AC-5:** Given die Messung ist geplant / When die Läufe ausgeführt werden / Then laufen beide in einem eigenen Server-Worktree (nie im Prod-Checkout), streng nacheinander und mit den wörtlichen Gate-Formen aus der Referenzdoku
  - Test: Das Protokoll nennt Worktree-Pfad, Commit-SHA und die ausgeführten Befehlszeilen; diese stimmen Zeichen für Zeichen mit den Literalen der Referenzdoku überein (zuzüglich `/usr/bin/time -v` und ` > datei 2>&1`).

- **AC-6:** Given der parallele Lauf mit Controller und zwei Workern / When der Speicherbedarf bestimmt wird / Then ist die Spitzen-RSS als Summe Controller plus Worker per Abtastung protokolliert, nicht nur das Max-RSS eines einzelnen Prozesses
  - Test: Das Protokoll zeigt Abtastintervall und Maximum der Summe, getrennt vom Max-RSS aus `time -v`.

- **AC-7:** Given der Lauf läuft / When `MemAvailable` unter 1 GB fällt / Then wird der Lauf abgebrochen und als gescheitert (Speicher) protokolliert
  - Test: Das Messskript enthält die Abbruchprüfung; das Protokoll nennt den kleinsten beobachteten `MemAvailable`-Wert und bestätigt, dass die Schwelle nicht unterschritten wurde (oder dokumentiert den Abbruch).

- **AC-8:** Given die Messung ist ausgewertet / When sie scheitert (nicht schneller, zusätzliche rote Tests, Selftest rot oder Speicherabbruch) / Then wird ein Folge-Issue zur Neubewertung (Rücknahme oder andere Worker-Zahl, Gate-Adversary 2 Runden) angelegt und #3278 bleibt offen; bei Erfolg kann #3278 geschlossen werden
  - Test: Das Protokoll trägt ein Gesamt-Verdict (bestanden/gescheitert) mit Verweis auf das Folge-Issue bzw. auf den Schluss von #3278.

- **AC-9:** Given die Messung ist abgeschlossen / When die Referenzdoku gelesen wird / Then nennt `docs/reference/gates_und_ratschen.md` die gemessenen Laufzeiten beider Formen mit Datum und Commit und enthält keinen Satz „noch nicht gemessen (#3323)" mehr
  - Test: Optionaler `# doc-compliance-test` prüft die Abwesenheit des Satzes und die Existenz des Protokolls; inhaltlich belegt durch das Protokoll.

## Definition of Done

- Messprotokoll unter `docs/artifacts/feat-3323-servermessung/` belegt AC-1 bis AC-7 mit Zahlen (Laufzeit, Spitzen-RSS/CPU, rote Test-IDs je Lauf, Selftest-Exit und Uhrzeit)
- Bei Erfolg: Referenzdoku nennt gemessene Laufzeiten beider Formen mit Datum und Commit (AC-9), #3278 kann geschlossen werden
- Bei Misserfolg: Folge-Issue zur Neubewertung angelegt, #3278 bleibt offen (AC-8); Protokoll dokumentiert das Scheitern ehrlich
- Adversary-Prüfung des Protokolls gegen die Rohdaten VERIFIED, alle 6 CI-Checks grün, Merge nach main

## Known Limitations

- Eine Einzelmessung je Form; Wackler (Timeouts unter Last) sind möglich; sie zählen als zusätzliche Rote (AC-2 nicht erfüllt) und werden nicht durch Wiederholung des Volllaufs weggemessen.
- Die Referenz 56:17 min (2026-11-22) stammt von einem anderen Commit und dient nur als Einordnung; der Vergleich gilt auf dem Mess-Commit.
- Die 9 failed / 2 errors der Referenz sind Server-Umgebungsartefakte; maßgeblich ist nur „keine zusätzlichen Roten".
- Der `henemm-pruefen`-Zugang kennt keinen Testlauf; gemessen wird über `ssh henemm`. Das Gate prüft Befehle der Claude-Sitzung, nicht das Server-Skript; die Literale stehen trotzdem wörtlich im Skript.

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** keine
- **Rationale:** Es wird nur gemessen und dokumentiert; die Worker-Zahl 2 und die Gate-Form sind in #3278 entschieden. Bei einem gescheiterten Ergebnis wäre eine Neubewertung ein eigenes Issue und gegebenenfalls ein ADR dort.

## Changelog

- 2026-11-27: Initial spec created (Issue #3323)
