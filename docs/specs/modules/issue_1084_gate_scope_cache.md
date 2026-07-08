---
entity_id: issue_1084_gate_scope_cache
type: bugfix
created: 2026-07-07
updated: 2026-07-07
status: draft
version: "1.0"
workflow: fix-1084-stale-gate-marker
tags: [gate, tooling, bugfix, deploy]
---

# Gate-Scope-Cache — Post-Deploy-Selftest übersprang sich still bei stale Marker (#1084)

## Approval

- [ ] Approved

## Purpose

`staging_gate.py::gate_check()` schreibt bei Erfolg den Gate-Marker
(`.claude/last_gate_scope.json`) auf den aktuellen HEAD (eingeführt durch #916).
Läuft `prod_selftest.py` — ein separater Prozess, ausgeführt als Post-Deploy-Schritt
(Schritt 4b) unmittelbar nach `deploy-gregor-prod.sh`s eigenem
`staging_gate.py --check`-Aufruf (Schritt 4) — im selben Repo-Zustand, liest es
denselben, jetzt bereits auf HEAD stehenden Marker über seine eigene gespiegelte
Scope-Erkennung (`_detect_committed_scope()`/`_scope_diff_base()`). `git diff
HEAD..HEAD` ist leer → Scope wird fälschlich `docs-only` → die Post-Deploy-
Verifikation überspringt sich still, obwohl echter Code deployt wurde (beobachtet
bei der #1080-Deploy-Pipeline). Diese Spec behebt das über einen Scope-Cache im
Marker selbst (kein naiver `HEAD~1`-Fallback — der würde den ursprünglichen
Multi-Commit-Bug #916 für `prod_selftest.py` wieder einschleppen) und behebt
zusätzlich (separater, risikoarmer Nebenfix) das Ignorieren eines übergebenen
`--scope`-Overrides in `write_verdict()`.

## Source

- **File:** `.claude/hooks/_e2e_paths.py`
- **Identifier:** `def write_last_gate_scope`, neue `def read_last_gate_scope_entry`
- **File:** `.claude/hooks/staging_gate.py`
- **Identifier:** `def gate_check` (Zeilen 276-344, Marker-Schreiben Zeile 285 +
  343), `def write_verdict` (Zeilen 234-273, Zeile 254 `_detect_committed_scope()`
  ohne Override), `def main` (Zeilen 347-372, Zeile 365 reicht `args.scope` nicht
  an `write_verdict()` durch)
- **File:** `.claude/hooks/prod_selftest.py`
- **Identifier:** `def _scope_diff_base` (Zeilen 393-408), `def
  _detect_committed_scope` (Zeilen 411-459), `def run_selftest` (Zeilen 462+)

> **Schicht-Hinweis:** Alle betroffenen Dateien liegen in `.claude/hooks/` —
> reines Deploy-/Test-Tooling, kein Produktcode in `frontend/`, `cmd/server/`,
> `internal/`, `api/` oder `src/`. Kein Prod-Deploy für diesen Workflow nötig
> (analog #916/#988-Präzedenzfall).

## Estimated Scope

- **LoC:** ~55-70 Produktivcode, ~150-220 Testcode
- **Files:** 3 MODIFY + 1 CREATE
- **Effort:** medium (Risk Level MEDIUM — kritischer Deploy-Pfad, aber
  Backward-kompatibel + bestehende Regressionstests bleiben unverändert grün)

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `_e2e_paths.py` | module | Bestehender Shared-Helper (`write_last_gate_scope`, `read_last_gate_scope`), wird um optionales Scope-Feld + neue Lesefunktion ergänzt — Voraussetzung für den Cache in beiden Gate-Dateien |
| `docs/specs/modules/issue_916_988_gate_scope_robustness.md` | spec | Direkter Vorläufer, führt den Marker-Mechanismus selbst ein; diese Spec ergänzt dessen "Known Limitations", ohne dessen AC-1..AC-6 zu brechen |
| `deploy-gregor-prod.sh` (henemm-infra) | script | Ruft `staging_gate.py --check` (Schritt 4) unmittelbar vor `prod_selftest.py` (Schritt 4b) auf — bestätigt den genauen Auslöse-Zeitpunkt des Bugs; wird selbst NICHT verändert |
| `tests/tdd/test_issue_916_gate_scope_marker.py` | test | Bestehende AC-1..AC-4-Tests für den Marker-Mechanismus, MÜSSEN unverändert grün bleiben (Regressionsschutz) |
| `tests/tdd/test_staging_gate.py` | test | Bestehende `write_verdict`/`gate_check`-Tests, MÜSSEN unverändert grün bleiben |
| `tests/tdd/test_bundle_e_gate_tooling.py` | test | AC-3/AC-4 (#786), `run_selftest(scope=...)`-Parameter, MÜSSEN unverändert grün bleiben |

## Implementation Details

### Fix 1 (Kern) — Scope-Cache im Marker statt Diff-Neuberechnung bei Selbstreferenz

**`_e2e_paths.py`:**

- `write_last_gate_scope(repo_dir, sha, scope=None) -> None`: optionales
  `scope`-Argument ergänzt. Ist `scope` gesetzt, wird
  `{"gate_scope_sha": sha, "gate_last_scope": scope}` geschrieben, sonst wie
  bisher nur `{"gate_scope_sha": sha}`. Bestehende Aufrufer ohne `scope`-Argument
  bleiben unverändert kompatibel (Default `None`).
- Neue Funktion `read_last_gate_scope_entry(repo_dir) -> dict | None`: liest die
  Marker-Datei und gibt den vollen, geparsten Eintrag zurück (oder `None` bei
  fehlender/kaputter Datei) — Pendant zu `read_last_gate_scope()`, das
  ausschließlich `gate_scope_sha` liefert und für alle bestehenden Aufrufer
  unverändert bleibt.

**`staging_gate.py::gate_check()`:** beide Erfolgspfade (Zeile 285: docs-only-
Skip, Zeile 343: vollständige Prüfung bestanden) übergeben den bereits
berechneten `scope`-Wert mit an `write_last_gate_scope()` — keine
Neuberechnung, der Wert liegt zum Zeitpunkt beider Aufrufe bereits vor
(`scope` in Zeile 282 bzw. das für den zweiten Pfad implizit bekannte Nicht-
docs-only-Scope, das für den Marker-Zweck genügt: der konkrete
Nicht-docs-only-Wert wird an derselben Stelle wie `scope` in Zeile 282
mitgeführt).

**`prod_selftest.py::_detect_committed_scope()`/`run_selftest()`:** Kurzschluss
vor der bestehenden Diff-Herleitung — wenn
`_e2e_paths.read_last_gate_scope_entry(repo_dir)` einen Eintrag liefert, dessen
`gate_scope_sha` EXAKT dem aktuellen HEAD entspricht UND ein
`gate_last_scope`-Feld vorhanden ist, wird dieser gecachte Wert DIREKT
zurückgegeben statt über den (in diesem Fall bedeutungslosen,
selbstreferenziellen) Diff `HEAD..HEAD` neu hergeleitet zu werden. In JEDEM
anderen Fall — kein Marker, Marker zeigt auf einen anderen Commit als HEAD,
altes Marker-Format ohne `gate_last_scope`-Feld — bleibt die bestehende,
bereits getestete Diff-Basis-Logik (`_scope_diff_base()`: Marker..HEAD,
Fallback `HEAD~1`) vollständig unverändert.

### Fix 2 (Nebenfix, unabhängig) — `write_verdict()` honoriert `--scope`-Override

`write_verdict()` erhält einen neuen, optionalen `scope_override: str | None =
None`-Parameter. Ist er gesetzt, wird er anstelle von `_detect_committed_scope()`
(aktuell Zeile 254) für das `scope`-Feld der Attestation verwendet — analog zu
`gate_check()`, das den Override bereits korrekt honoriert (Zeile 282).
`main()` reicht `args.scope` (bereits als CLI-Flag `--scope` vorhanden, Zeile
353) zusätzlich an den `write_verdict()`-Aufruf (Zeile 365) durch. Das
`scope`-Feld in `e2e_verified.json` ist rein informativ (per grep verifiziert:
wird von keiner Gate-Logik zurückgelesen), daher niedrigeres Risiko.

## Expected Behavior

- **Input:** Zwei aufeinanderfolgende Prozessaufrufe im selben Repo-Zustand —
  erst `staging_gate.py --check` (schreibt Marker inkl. Scope auf HEAD), dann
  `prod_selftest.py` (liest Marker) — sowie, separat, ein `--scope`-Override
  beim `--write-verdict`-Aufruf.
- **Output:** `prod_selftest.py` liefert bei exakter Commit-Übereinstimmung mit
  frischem Marker den gecachten (korrekten) Scope statt `docs-only`; alle
  anderen Fälle (kein Marker, älterer Marker, altes Format) liefern weiterhin
  das unveränderte, diff-basierte Ergebnis. `write_verdict()` schreibt bei
  gesetztem Override exakt diesen Wert ins `scope`-Feld der Attestation.
- **Side effects:** `.claude/last_gate_scope.json` enthält nach jedem
  erfolgreichen `gate_check()`-Lauf zusätzlich `gate_last_scope`. Kein anderer
  Prozess schreibt diese Datei (unverändert seit #916 — `prod_selftest.py`
  bleibt reiner Leser).

## Acceptance Criteria

- **AC-1:** Given ein Temp-Git-Repo, in dem `gate_check()` gerade erfolgreich
  für den aktuellen HEAD gelaufen ist (Marker zeigt auf HEAD, `gate_last_scope`
  z.B. `"frontend-only"` gesetzt) / When `prod_selftest.py`s
  `_detect_committed_scope()` (bzw. `run_selftest()`) direkt danach im selben
  Repo-Zustand aufgerufen wird / Then liefert es den gecachten Scope
  (`frontend-only`), NICHT `docs-only`.
  - Test: echtes Temp-Git-Repo (`git init`, echte Commits mit
    Frontend-Änderung), echter `gate_check()`-Aufruf als Subprozess/Direktimport
    gegen dieses Repo, gefolgt von einem echten `_detect_committed_scope()`- bzw.
    `run_selftest()`-Aufruf gegen denselben Repo-Zustand; Assertion auf den
    zurückgegebenen String, kein Dateiinhalt-Check.

- **AC-2:** Given Marker-SHA == aktueller HEAD mit gesetztem `gate_last_scope`
  / When die Scope-Erkennung läuft / Then wird der gecachte Wert verwendet —
  beobachtbar am Verhalten (korrekter Scope trotz leerem `HEAD..HEAD`-Diff),
  nicht an einem Implementierungsdetail wie "kein `git diff`-Subprozess wurde
  gestartet".
  - Test: echtes Temp-Repo mit Marker-SHA == HEAD und `gate_last_scope=
    "backend"`; Aufruf von `_detect_committed_scope()`; Assertion, dass das
    Ergebnis `backend` ist, obwohl seit dem letzten realen Commit keine
    weiteren Backend-Änderungen existieren (der Diff allein würde `docs-only`
    liefern) — beweist, dass der Cache-Pfad tatsächlich greift.

- **AC-3:** Given ein Marker im alten Format (`{"gate_scope_sha": sha}`, ohne
  `gate_last_scope`) mit SHA == HEAD / When die Scope-Erkennung läuft / Then
  fällt sie auf die bestehende Diff-Logik zurück (identisch zum
  Vor-Fix-Verhalten: `HEAD..HEAD` leer → `docs-only`) statt abzustürzen.
  - Test: echtes Temp-Repo, Marker-Datei manuell im alten Format geschrieben
    (nur `gate_scope_sha`), SHA == aktueller HEAD; Aufruf von
    `_detect_committed_scope()`; Assertion auf `docs-only` (Vor-Fix-Ergebnis)
    ohne Exception/Traceback.

- **AC-4:** Given Marker-SHA != aktueller HEAD (z.B. isolierter Lauf oder neue
  Commits seither, Szenario aus #916 AC-1: Commit B ändert Backend-Code, Commit
  C danach ändert nur Docs) / When die Scope-Erkennung läuft / Then bleibt das
  bestehende Marker-Diff-Verhalten unverändert korrekt (liefert `backend`, NICHT
  `docs-only`) — KEIN Cache-Wert wird fälschlich verwendet, auch wenn ein
  `gate_last_scope`-Feld im (jetzt veralteten) Marker steht.
  - Test: echtes Temp-Repo, Marker zeigt auf Commit A mit `gate_last_scope=
    "docs-only"`; danach Commit B (Backend-Änderung) und Commit C (nur Docs)
    als HEAD; Aufruf von `_detect_committed_scope()`; Assertion auf `backend`
    — beweist, dass der veraltete Cache-Wert (`docs-only`) NICHT verwendet
    wird, weil `gate_scope_sha` != HEAD ist.

- **AC-5:** Given ein `gate_check()`-Lauf, der `scope="backend"` (bzw.
  `docs-only`) erfolgreich abschließt / When der Marker danach gelesen wird /
  Then enthält er sowohl den korrekten `gate_scope_sha` (== `git rev-parse
  HEAD` des Repos zum Zeitpunkt des Laufs) als auch das passende
  `gate_last_scope`-Feld (== der tatsächlich verwendete Scope-Wert).
  - Test: echtes Temp-Repo, zwei `gate_check()`-Läufe (einmal mit
    `scope_override="docs-only"`, einmal nach echtem Commit mit vollständiger
    Prüfung und `scope_override="backend"`); nach jedem Lauf wird die
    Marker-Datei geparst (echtes JSON) und beide Felder gegen den erwarteten
    Wert verglichen — kein reiner String-in-Datei-Check.

- **AC-6:** Given ein `--scope`-Wert wird explizit an `staging_gate.py
  --write-verdict` übergeben / When die Attestation geschrieben wird / Then
  enthält `e2e_verified.json` genau diesen Scope-Wert, nicht das Ergebnis von
  `_detect_committed_scope()`.
  - Test: echtes Temp-Repo mit einem Commit, der laut Diff eigentlich
    `frontend-only` wäre; `staging_gate.py --write-verdict "VERIFIED (...)"
    --scope backend` als echter Subprozess-Aufruf; danach `e2e_verified.json`
    geparst und `scope == "backend"` (der Override, NICHT `frontend-only`)
    geprüft.

## Test Plan

Alle Tests laufen gegen echte Temp-Git-Repos (`git init`, echte Commits) mit
echten Subprozess- bzw. Direktimport-Aufrufen der echten Hook-Skripte (Muster:
`_setup_repo`/`_run_staging_gate` in `tests/tdd/test_issue_916_gate_scope_marker.py`).
KEINE Mocks — Projektregel (CLAUDE.md "KEINE MOCKED TESTS"). Kein
Dateiinhalt-String-Check; jeder Test verifiziert das zurückgegebene bzw.
geschriebene Verhalten (Scope-String, Exit-Code, geparstes JSON-Feld).

- Neue Testdatei `tests/tdd/test_issue_1084_gate_scope_cache.py` deckt AC-1 bis
  AC-6 ab.
- **Regressionsschutz (kein neuer AC, aber Pflicht-Prüfpunkt vor Merge):**
  `tests/tdd/test_issue_916_gate_scope_marker.py` (AC-1..AC-4),
  `tests/tdd/test_staging_gate.py` (bestehende `write_verdict`/`gate_check`-
  Tests) und `tests/tdd/test_bundle_e_gate_tooling.py` (AC-3/AC-4, `
  run_selftest(scope=...)`) MÜSSEN nach der Implementierung unverändert grün
  bleiben.

## Known Limitations

- Der Cache greift NUR, wenn `prod_selftest.py` (oder ein erneuter
  `staging_gate.py`-Aufruf) unmittelbar nach einem erfolgreichen
  `gate_check()`-Lauf für exakt denselben Commit läuft — in jedem anderen Fall
  (isolierter Lauf, spätere Commits) gilt weiterhin die bestehende,
  diff-basierte Herleitung mit ihren bekannten Grenzen (siehe "Known
  Limitations" in `issue_916_988_gate_scope_robustness.md`: Marker-Mechanismus
  funktioniert korrekt nur im offiziellen, linearen Deploy-Baum; History-
  Rewrite fällt auf `HEAD~1` zurück).
- Verwandtes Issue #1072 (Fremd-Commit landet zwischen Push und Deploy) wird
  durch diesen Fix voraussichtlich indirekt mitgelöst — das Szenario ist bereits
  durch die #916-Marker-Logik abgedeckt (AC-1 in
  `test_issue_916_gate_scope_marker.py`), sobald der `marker==HEAD`-Sonderfall
  aus #1084 korrekt behandelt wird. Kein eigener AC hier, aber als Notiz für
  die spätere Verifikation/Issue-Schließung festgehalten.
- Verwandtes Issue #1078 (`e2e_commit_gate.py`, andere Root Cause: `git diff
  --cached` ist nach einem Commit immer leer) ist bewusst NICHT Teil dieser
  Spec — anderes Skript, eigene Ursache, würde Scope/Risiko dieses Workflows
  unnötig vergrößern.
- Der `write_verdict()`-`--scope`-Override (Fix 2) wirkt ausschließlich auf das
  informative `scope`-Feld der Attestation. Er ändert nichts an der
  `verified_commit`/`staging_verdict`-Prüfung in `gate_check()` — ein falsch
  gesetzter Override kann daher keinen fehlerhaften Deploy durchwinken, nur die
  Attestation "falsch beschriften".

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** keine
- **Rationale:** Reines Bugfix-Tooling innerhalb bestehender Gate-Skripte
  (`.claude/hooks/`), die bereits durch die Vorgänger-Spec
  (`issue_916_988_gate_scope_robustness.md`) eingeführt wurden — keine neue
  Architektur-Entscheidung, kein neues Subsystem, keine Änderung an
  Produktcode, API-Verträgen oder Datenmodellen. Es wurde geprüft: keine der
  vorhandenen ADRs (`docs/adr/0001`-`0017`) behandelt Deploy-Gate-Mechanik oder
  Scope-Erkennung; die Vorgänger-Spec kam zum selben Schluss.

## Changelog

- 2026-07-07: Initial spec created
