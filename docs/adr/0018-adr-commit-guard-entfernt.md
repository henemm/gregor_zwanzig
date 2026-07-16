# ADR-0018: Lokales ADR-Commit-Gate (adr_guard.py) entfernt

- **Status:** Akzeptiert
- **Datum:** 2026-07-16
- **Bezug:** GitHub-Issue #1197 (Gate-Audit), #1164, #1176; löst die Enforcement-Seite von #885 ab

## Kontext

`#885` führte `adr_guard.py` ein: ein Commit-Gate, das Commits an „Entscheidungs-
flächen" (`src/output/`, `src/providers/`, `.claude/hooks/*_(gate|guard).py`, …)
blockiert, wenn weder eine `docs/adr/*.md` mitgestaged noch `[no-adr]` in der
Commit-Message steht.

Seit der Plugin-Migration (`#33`, Commit `465380c1` „Legacy-Hook-Kopien entfernt")
ist dieses Gate **nicht mehr verdrahtet** (#1164): `adr_guard.check()` wird von
keinem Hook aufgerufen, `adr_guard.py` ist in keiner `settings.json`-Hook-Sektion
registriert und hat kein `main()`/stdin-Handling. Es ist reine, unaufgerufene
Bibliotheks-Funktion — toter Code. Live-Beleg (Gate-Audit-Session 2026-07-16):
mehrere Commits an `*_gate.py`-Entscheidungsflächen wurden ohne ADR und ohne
`[no-adr]` durchgelassen; niemand hat den fehlenden Guard über Wochen bemerkt.

**Wichtige Abgrenzung — ADR-Enforcement bleibt bestehen:**
- Die **ADR-Praxis** (`docs/adr/*.md`, aktuell 18 Records) ist unberührt.
- Die **Spec-Zeit-Prüfung** (Plugin `workflow.py::_check_adr`) verlangt weiter,
  dass jede Spec eine ausgefüllte ADR-Deklaration (`**ADR-Nr.:**` Nummer oder
  begründetes „keine") trägt. Diese Prüfung ist aktiv und ersetzt die
  Enforcement-Rolle des toten Commit-Gates.

## Entscheidung

**`adr_guard.py` und seine Testsuite (`tests/tdd/test_issue_885_adr_guard.py`)
werden entfernt** (PO-Entscheidung 2026-07-16, Regel-Budget-Rückbau: „kein Fang →
raus"). Die Coverage-Lücke #1176 (`src/services` nicht abgedeckt) wird damit
hinfällig.

## Verworfene Alternativen

- **Reaktivieren** (als echtes Commit-Gate verdrahten + #1176-Coverage) —
  verworfen: würde Commit-Zeit-Friktion neu einführen (jeder Entscheidungsflächen-
  Commit bräuchte ADR/`[no-adr]`), während das ADR-Denken bereits durch Praxis +
  Spec-Zeit-Prüfung geschützt ist. Widerspricht der Anti-Friktions-Zielsetzung des
  Gate-Audits (#1197).
- **So lassen** (toten Code liegenlassen) — verworfen: Wartungslast + Widerspruch
  („warum blockt der Guard nicht?").

## Konsequenzen

- **Positiv:** Weniger toter Code; ein Gate weniger im Audit-Register; kein
  Wieder-Aufflammen der Coverage-Debatte (#1176).
- **Negativ / Preis:** Commits an Entscheidungsflächen **außerhalb** des
  Spec-Workflows (Direkt-Edits ohne Spec) werden nicht mehr commit-seitig auf ADR
  geprüft — nur noch spec-seitig. Als akzeptabel bewertet, da Entscheidungs-
  flächen in der Praxis über Specs laufen.
- **Folgepflicht:** Eine Wiedereinführung eines Commit-Zeit-ADR-Gates erfordert
  ein neues ADR (das dieses hier ablöst) samt Fang-Nachweis.
