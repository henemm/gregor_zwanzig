---
entity_id: issue_1109_1116_1121_gate_scope
type: bugfix
created: 2026-07-09
updated: 2026-07-09
status: draft
version: "1.0"
workflow: gate-scope-1109-1116-1121
tags: [gate, tooling, bugfix, deploy]
---

# Gate-Scope-Erkennung — drei Lücken: Marker-Vergiftung (bereits behoben), fehlende Returncode-Prüfung, fehlender Prod-Deploy-Marker (#1109/#1116/#1121)

## Approval

- [ ] Approved

## Purpose

Diese Spec bündelt drei zusammenhängende, aber unabhängige Fixe an der Scope-Klassifikation
(`docs-only` / `frontend-only` / `backend` / `full-stack`), die entscheidet, ob der
Post-Deploy-Selftest (`prod_selftest.py`) für einen Prod-Deploy läuft:

- **Teil A (#1116):** kein Code-Fix — Verifikation, dass das im Issue beschriebene
  Marker-Vergiftungsszenario bereits durch #1096 (`fab61d76`) strukturell unmöglich geworden ist,
  dokumentiert als Reproduktionsbeweis für den Issue-Close.
- **Teil B (#1121):** `git diff --name-only`-Aufrufe in der Scope-Erkennung prüfen aktuell ihren
  Returncode nicht — ein fehlgeschlagener Git-Aufruf liefert leeren `stdout`, was identisch zu
  einem echten leeren Diff behandelt wird und fälschlich `docs-only` liefert. Fix: neuer,
  konsolidierter Shared-Helper mit Returncode-Guard, der zusätzlich die bisher zweifach
  duplizierte Klassifizierungslogik zusammenführt.
- **Teil C (#1109):** `prod_selftest.py` leitet die Diff-Basis vom letzten Gate-**Check**-Lauf ab,
  nicht vom letzten tatsächlich live **deployten** Commit — bei mehreren Gate-Läufen zwischen zwei
  echten Prod-Deploys kann der beim tatsächlichen Deploy relevante Scope zu klein ausfallen. Fix:
  neuer, von `deploy-gregor-prod.sh` (henemm-infra, separates Repo) geschriebener Marker
  `.claude/last_prod_deploy.json`, den `prod_selftest.py` bevorzugt als Diff-Basis liest.

## Source

- **File:** `.claude/hooks/_e2e_paths.py`
- **Identifier:** neue `def _detect_scope_from_git_diff(base, target, repo_dir)` (Teil B)
- **File:** `.claude/hooks/staging_gate.py`
- **Identifier:** `def _detect_committed_scope` (Z.136-199, Git-Diff-Aufruf Z.161-165), `def
  _telegram_live_gate` (Z.226-259, Git-Diff-Aufruf Z.244-248) — beide auf Shared-Helper umgestellt
  (Teil B)
- **File:** `.claude/hooks/prod_selftest.py`
- **Identifier:** `def _detect_committed_scope` (Z.415-472, Git-Diff-Aufruf Z.434-438) auf
  Shared-Helper umgestellt (Teil B); `def _scope_diff_base` (Z.393-412) erweitert um bevorzugtes
  Lesen von `last_prod_deploy.json` (Teil C)
- **File:** `docs/artifacts/gate-scope-1109-1116-1121/repro-1116.md` (neu, Teil A)
- **File:** `/home/hem/henemm-infra/scripts/deploy-gregor-prod.sh` (separates Repo, Teil C —
  siehe Abschnitt "Repo-Grenze" unten)

> **Schicht-Hinweis:** Alle Änderungen in diesem Repo liegen in `.claude/hooks/` — reines
> Deploy-/Test-Tooling, kein Produktcode in `frontend/`, `cmd/server/`, `internal/`, `api/` oder
> `src/`. Kein Prod-Deploy für diesen Workflow im üblichen Sinn nötig — Verifikation läuft über
> hermetische Tests, nicht über Staging-E2E (analog #1084/#1096-Präzedenzfall).

## Estimated Scope

- **LoC (dieses Repo, zählt gegen das 250-LoC-Limit):** ~60 netto
  (~35 Teil B: Shared-Helper + Umstellung dreier Aufrufstellen; ~10 Teil C:
  `_scope_diff_base()`-Erweiterung in `prod_selftest.py`; ~15 Teil A: keine Produktivcode-LoC,
  nur das Doku-Artefakt, zählt nicht gegen das Limit)
- **LoC (henemm-infra, separates Repo, zählt NICHT gegen dieses Limit):** ~5
  (`deploy-gregor-prod.sh`, Marker-Write nach Smoke-Test)
- **Files (dieses Repo):** 3 MODIFY (`_e2e_paths.py`, `staging_gate.py`, `prod_selftest.py`) +
  2 CREATE (Testdateien) + 1 CREATE (Doku-Artefakt) = 6
- **Files (henemm-infra, separater Commit):** 1 MODIFY
- **Effort:** low-medium (Risk Level HIGH wegen kritischem Deploy-Pfad, aber
  Änderungsrichtung durchgängig konservativ: Fallback `backend` statt `docs-only`, neuer Marker
  additiv mit Fallback auf bisheriges Verhalten)

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `_e2e_paths.py` | module | Bestehender Shared-Helper (`cached_scope_for_sha`, `read_last_gate_scope`, `write_last_gate_scope`); wird um `_detect_scope_from_git_diff()` (Teil B) ergänzt |
| `docs/specs/modules/issue_916_988_gate_scope_robustness.md` | spec | Erste Iteration: Marker-SHA als Diff-Basis (#916) |
| `docs/specs/modules/issue_1084_gate_scope_cache.md` | spec | Zweite Iteration: Scope-Cache im Marker (#1084) |
| `docs/context/fix-1096-gate-scope.md` | context | Dritte Iteration: symmetrischer Cache-Guard beider Gate-Dateien (#1096, `fab61d76`) — direkte Voraussetzung für Teil A dieser Spec |
| `deploy-gregor-prod.sh` (henemm-infra) | script | Ruft `staging_gate.py --check --expected-commit` (Preflight) und danach `--check` (Post-Reset) auf; wird für Teil C um das Schreiben von `last_prod_deploy.json` ergänzt (separater Commit, MQ an `infra`) |
| `tests/tdd/test_issue_916_gate_scope_marker.py` | test | Bestehende Marker-Tests, MÜSSEN unverändert grün bleiben |
| `tests/tdd/test_issue_1084_gate_scope_cache.py` | test | Bestehende Cache-Tests, MÜSSEN unverändert grün bleiben — **einzige bewusste Ausnahme:** `test_ac3_old_marker_format_falls_back_without_crash` wird von erwartetem `docs-only` auf `backend` angepasst, weil der alte erwartete Wert exakt das #1121-Bugverhalten testete (siehe Implementation Details Teil B) |
| `tests/tdd/test_staging_gate.py` | test | Bestehende `write_verdict`/`gate_check`-Tests (inkl. #1096-Migration auf hermetisches Temp-Repo), MÜSSEN unverändert grün bleiben |
| `tests/tdd/test_bundle_e_gate_tooling.py` | test | Bestehende `run_selftest(scope=...)`-Tests, MÜSSEN unverändert grün bleiben |

## Implementation Details

### Teil A (#1116) — Reproduktionsbeweis "bereits behoben", kein Produktivcode

Kein Code-Fix. Ein neuer Test stellt exakt das im Issue #1116 beschriebene Vergiftungsszenario
nach: Marker zeigt nach einem vorherigen erfolgreichen `gate_check()`-Lauf auf HEAD (Voll-Check,
Nicht-docs-only-Scope), danach erneuter `--check`- bzw. `--detect-scope`-Aufruf im selben
Repo-Zustand. Erwartung: der zweite Aufruf liefert weiterhin den korrekten (gecachten) Scope,
NICHT `docs-only` — weil drei Schutzlagen aus #1096 kombiniert greifen (F001-Guard in
`cached_scope_for_sha()`, F002-Fallback in `_scope_diff_base()`, Write-Guard in `gate_check()`
Z.347-350). Der Testlauf-Output (grün) plus die drei referenzierten Code-Stellen werden als Beleg
in `docs/artifacts/gate-scope-1109-1116-1121/repro-1116.md` festgehalten — dieses Dokument dient
als Nachweis für den Issue-Close von #1116 mit Verweis auf `fab61d76`.

### Teil B (#1121) — Shared-Helper mit Returncode-Guard

Neue Funktion in `_e2e_paths.py`:

```
_detect_scope_from_git_diff(base: str, target: str, repo_dir) -> str
```

Führt `git diff --name-only <base> <target>` im gegebenen `repo_dir` aus und klassifiziert die
geänderten Pfade nach demselben Präfix-Matching, das aktuell dupliziert in
`staging_gate.py::_detect_committed_scope()` (Z.169-199) und
`prod_selftest.py::_detect_committed_scope()` (Z.442-472) steht
(`frontend/` → `frontend-only`-Kandidat, `src/`/`api/`/`internal/`/`cmd/` → `backend`-Kandidat,
`docs/`/`.claude/`/`*.md`/`README`/`.gitignore`/`tests/` → ignoriert, alles andere → `backend`;
beide gesetzt → `full-stack`). **Neu:** wird der `subprocess.run(...)`-Aufruf mit
`returncode != 0` beendet (z.B. `base` nicht auflösbar), liefert der Helper NICHT `docs-only`
(das wäre der #1121-Bug), sondern **`"backend"`** — konservativer Fallback, fail-closed, konsistent
mit der Projekt-Philosophie "im Zweifel prüfen statt überspringen" (vgl. #1130 F001) und mit allen
anderen git-Aufrufen im Code, die ihren Returncode bereits prüfen (`cat-file`, `rev-parse`,
`merge-base`).

Drei Aufrufstellen werden auf den Helper umgestellt (Duplikat-Eliminierung, ~30 LoC weniger
Klassifizierungslogik):

- `staging_gate.py::_detect_committed_scope()` (Z.161-165 der Diff-Subprozess-Aufruf + die
  anschließende Klassifizierung Z.169-199)
- `staging_gate.py::_telegram_live_gate()` (Z.244-248, fester `base="HEAD~1"`) — hier wird nur der
  Diff-Aufruf selbst über den neuen Returncode-Guard abgesichert; die Telegram-Pfad-Erkennung
  (`mod._scope_touches_telegram(changed)`) bleibt unverändert, da sie eine andere Klassifikation
  (Telegram-Pfad-Treffer, nicht frontend/backend/docs) verwendet — nur die
  Returncode-Prüfung des zugrunde liegenden `git diff` wird über denselben Helper-Mechanismus
  gehärtet (Fallback: bei Fehler wird `changed` als nicht-leer/konservativ behandelt, siehe AC-5).
- `prod_selftest.py::_detect_committed_scope()` (Z.434-438 der Diff-Subprozess-Aufruf + die
  anschließende Klassifizierung Z.442-472)

Alle drei behalten ihre bestehende Vorstufen-Logik (Cache-Check via `cached_scope_for_sha()`,
Preflight-Sonderfall in `staging_gate.py`) unverändert — nur der eigentliche `git
diff`-Aufruf + die Pfad-Klassifikation wandert in den Shared-Helper.

### Teil C (#1109) — Neuer Prod-Deploy-Marker

**Neue Datei** `.claude/last_prod_deploy.json` (Format:
`{"deployed_commit": "<sha>", "deployed_at": "<ISO-Timestamp>", "status": "success"}`),
geschrieben von `deploy-gregor-prod.sh` (henemm-infra) **NACH** erfolgreichem Smoke-Test — nicht
vor dem Reset, nicht bei fehlgeschlagenem Smoke-Test. Atomarer Write analog den bestehenden
Marker-Writes in `_e2e_paths.py` (`write_text` nach `mkdir(parents=True, exist_ok=True)`,
Schreibfehler geschluckt, das Deploy-Ergebnis selbst bleibt davon unbeeinflusst).

**`prod_selftest.py::_scope_diff_base()`** (aktuell Z.393-412) wird erweitert: liest bevorzugt
`.claude/last_prod_deploy.json` (Feld `deployed_commit`) als Diff-Basis. Ist die Datei vorhanden
UND `deployed_commit` im Repo auflösbar (`git cat-file -e`, analog dem bestehenden
Marker-Auflösbarkeits-Check) UND ungleich dem aktuellen HEAD → `deployed_commit` als Basis.
Andernfalls (Datei fehlt — Erst-Deploy/Migration; Datei kaputt/nicht parsebar; `deployed_commit`
nicht auflösbar; `deployed_commit == HEAD`) fällt die Funktion auf das bisherige, unveränderte
Verhalten zurück: erst `last_gate_scope.json`-Marker, dann `HEAD~1`.

**Repo-Grenze (verbindlich):** Die Änderung an `deploy-gregor-prod.sh` liegt in
`henemm-infra` — einem anderen Repo mit eigener Claude-Instanz. Sie wird **nicht** vom
`developer`-Agent dieses `gregor_zwanzig`-Workflows umgesetzt. Stattdessen: MQ-Nachricht an die
`infra`-Instanz (siehe `~/.claude/CLAUDE.md` → "Inter-Instance Messaging") mit der exakten
Marker-Spezifikation (Pfad, JSON-Format, Schreibzeitpunkt nach Smoke-Test). Die
`gregor_zwanzig`-seitige Änderung (`prod_selftest.py`) kann unabhängig implementiert und getestet
werden (hermetisches Temp-Repo, Marker-Datei wird im Test direkt geschrieben, kein Abhängen vom
tatsächlichen infra-Deploy-Lauf) — sie ist aber erst in echter Prod-Nutzung wirksam, sobald
`deploy-gregor-prod.sh` den Marker tatsächlich schreibt (siehe "Known Limitations").

## Expected Behavior

- **Input (Teil A):** Zwei aufeinanderfolgende Aufrufe im selben Repo-Zustand — erst ein
  vollständiger `gate_check()`-Lauf für HEAD, danach ein erneuter Scope-Erkennungs-Aufruf
  (`--detect-scope` oder erneuter `--check`) für denselben HEAD.
- **Output (Teil A):** Der zweite Aufruf liefert denselben, korrekten (Nicht-docs-only-)Scope wie
  der erste — kein Vergiftungspfad zu `docs-only` beobachtbar.
- **Input (Teil B):** `git diff --name-only <base> <target>` schlägt fehl (z.B. `base` ist ein
  nicht existierender/nicht auflösbarer Commit-Ausdruck).
- **Output (Teil B):** Scope-Erkennung liefert `"backend"`, NICHT `"docs-only"`. Bei erfolgreichem
  Diff bleibt das Klassifikationsergebnis identisch zum bisherigen Verhalten (keine
  Verhaltensänderung im Erfolgsfall).
- **Input (Teil C):** Mehrere Gate-Läufe (`--check`) zwischen zwei echten Prod-Deploys, wobei der
  Scope seit dem letzten `deployed_commit` mehr Änderungen umfasst als seit dem letzten
  Gate-Marker.
- **Output (Teil C):** `prod_selftest.py` klassifiziert den Scope über den größeren Bereich seit
  `deployed_commit`, nicht über den kleineren Bereich seit dem letzten Gate-Marker-Lauf — ein
  echter Code-Deploy wird nicht mehr fälschlich als `docs-only` übersprungen.
- **Side effects:** `.claude/last_prod_deploy.json` wird ausschließlich von
  `deploy-gregor-prod.sh` (henemm-infra) geschrieben — `prod_selftest.py` bleibt reiner Leser
  (analog zur bestehenden Rollenteilung bei `last_gate_scope.json`).

## Acceptance Criteria

**Teil A — #1116 (Reproduktionsbeweis, kein neuer Produktivcode)**

- **AC-1 (#1116):** Given ein hermetisches Temp-Git-Repo, in dem `gate_check()` gerade
  erfolgreich mit vollem Prüfpfad für den aktuellen HEAD gelaufen ist (Marker zeigt exakt auf
  HEAD, `gate_last_scope` z.B. `"backend"` gesetzt) / When direkt danach im selben Repo-Zustand
  ein erneuter `--detect-scope`- bzw. `--check`-Aufruf für denselben HEAD läuft / Then liefert
  dieser erneute Aufruf weiterhin `"backend"` (den korrekten, gecachten Wert), NICHT `docs-only`
  — das im Issue #1116 beschriebene Vergiftungsszenario tritt nicht ein.
  - Test: echtes Temp-Git-Repo (`git init`, echter Backend-Commit), zwei echte
    Subprozess-Aufrufe des echten `staging_gate.py` (erst `--check` mit vollem Prüfpfad, dann
    `--detect-scope`) gegen denselben Repo-Zustand; Assertion auf `stdout` des zweiten Aufrufs.
    Kein Dateiinhalt-Check als alleiniger Beweis — das beobachtbare Prozessverhalten (Exit-Code +
    stdout) ist der Beweis.

**Teil B — #1121 (Shared-Helper + Returncode-Fallback)**

- **AC-2 (#1121):** Given ein Ein-Commit-Temp-Repo ohne auflösbare Diff-Basis (z.B. `base` ist ein
  frei erfundener, nicht existierender Commit-Ausdruck) / When
  `_detect_scope_from_git_diff(base, "HEAD", repo_dir)` aufgerufen wird / Then liefert die
  Funktion `"backend"`, NICHT `"docs-only"`.
  - Test: echtes Temp-Git-Repo (`git init`, ein Commit), direkter Funktionsaufruf mit einer
    garantiert nicht auflösbaren `base` (z.B. `"0000000000000000000000000000000000000000"`);
    Assertion auf den zurückgegebenen String `== "backend"`.

- **AC-3 (#1121):** Given `staging_gate.py::_detect_committed_scope()` bzw.
  `prod_selftest.py::_detect_committed_scope()` läuft in einem Repo-Zustand, in dem die
  ermittelte Diff-Basis nicht auflösbar ist (z.B. Marker verweist auf einen SHA, der im
  aktuellen Repo nicht existiert und auch der `HEAD~1`-Fallback nicht existiert, weil das Repo
  nur einen Commit hat) / When der volle `--check`- bzw. `--detect-scope`-Aufruf läuft / Then
  liefert der Prozess `"backend"` als Scope (Fallback greift end-to-end, nicht nur im
  isolierten Helper-Unit-Test).
  - Test: echtes Ein-Commit-Temp-Repo, echter Subprozess-Aufruf von `staging_gate.py
    --detect-scope` (und separat `prod_selftest.py` via Direktimport-Aufruf von
    `_detect_committed_scope()`); Assertion auf `"backend"` im `stdout` bzw. Rückgabewert.

- **AC-4 (#1121):** Given ein normaler, erfolgreicher Diff (auflösbare Basis, echte
  Dateiänderungen in `frontend/` und `src/`) / When die Scope-Erkennung über den neuen
  Shared-Helper läuft / Then bleibt das Klassifikationsergebnis identisch zum
  Vor-Fix-Verhalten (`"full-stack"`) — die Refactoring auf den Shared-Helper ändert das
  Ergebnis im Erfolgsfall nicht.
  - Test: echtes Temp-Repo mit zwei Commits (einer ändert `frontend/foo.ts`, einer
    `src/bar.py`), Aufruf von `_detect_scope_from_git_diff("HEAD~2", "HEAD", repo_dir)`;
    Assertion auf `"full-stack"`.

- **AC-5 (#1121):** Given `_telegram_live_gate()` läuft in einem Repo-Zustand, in dem
  `git diff --name-only HEAD~1 HEAD` fehlschlägt (z.B. flaches Repo mit nur einem Commit,
  `HEAD~1` existiert nicht) / When die Funktion aufgerufen wird / Then verhält sie sich
  konservativ (Telegram-Gate wird NICHT stillschweigend als "kein Treffer" behandelt, sondern
  löst denselben Fail-Closed-Pfad aus wie ein tatsächlicher Telegram-Pfad-Treffer ohne gesetzte
  `GZ_TELEGRAM_TEST_CHAT_ID`), NICHT identisch zu einem echten leeren Diff (der `0`
  zurückliefern würde).
  - Test: echtes Ein-Commit-Temp-Repo (kein `HEAD~1` auflösbar), echter Aufruf von
    `_telegram_live_gate()` ohne gesetzte `GZ_TELEGRAM_TEST_CHAT_ID`; Assertion auf Rückgabewert
    `1` (blockt), nicht `0`.

**Teil C — #1109 (Prod-Deploy-Marker)**

- **AC-6 (#1109):** Given `.claude/last_prod_deploy.json` existiert mit `deployed_commit` = einem
  frühen Commit A, und seither gibt es mehrere weitere Commits sowie einen oder mehrere
  `gate_check()`-Läufe, deren Marker (`last_gate_scope.json`) auf einen späteren Commit B zeigt
  (B liegt zwischen A und HEAD) / When `prod_selftest.py::_scope_diff_base()` aufgerufen wird /
  Then liefert sie Commit A (aus `last_prod_deploy.json`) als Diff-Basis, NICHT Commit B (aus
  dem Gate-Marker) — der größere, für den echten Prod-Sprung relevante Bereich wird geprüft.
  - Test: echtes Temp-Repo mit mind. 3 Commits (A: Backend-Änderung, B: weitere
    Backend-Änderung + Gate-Marker-Schreibpunkt, C=HEAD: Docs-only-Commit); `last_prod_deploy.json`
    zeigt auf A, `last_gate_scope.json` zeigt auf B; Aufruf von `_scope_diff_base()`; Assertion
    auf Rückgabewert `== SHA(A)`. Zusätzlich End-to-End: `_detect_committed_scope()` liefert für
    dieses Szenario `"backend"` (aus der Backend-Änderung in A→B), obwohl der reine
    Gate-Marker-Diff (B→HEAD) `"docs-only"` liefern würde.

- **AC-7 (#1109):** Given `.claude/last_prod_deploy.json` existiert NICHT (Erst-Deploy oder
  Migration) / When `_scope_diff_base()` aufgerufen wird / Then verhält sie sich exakt wie vor
  diesem Fix (Fallback auf `last_gate_scope.json`-Marker, dann `HEAD~1`) — keine
  Verhaltensänderung ohne den neuen Marker.
  - Test: echtes Temp-Repo ohne `last_prod_deploy.json`, aber mit vorhandenem
    `last_gate_scope.json`; Aufruf von `_scope_diff_base()`; Assertion auf den Marker-SHA aus
    `last_gate_scope.json` (identisch zum dokumentierten Vor-Fix-Verhalten in AC-2 von
    `issue_1084_gate_scope_cache.md`).

- **AC-8 (#1109):** Given `.claude/last_prod_deploy.json` enthält einen `deployed_commit`, der im
  aktuellen Repo nicht auflösbar ist (z.B. History-Rewrite, Force-Push) / When
  `_scope_diff_base()` aufgerufen wird / Then wird dieser Wert verworfen und auf den
  bestehenden Fallback-Pfad (Gate-Marker, dann `HEAD~1`) zurückgefallen, kein Absturz.
  - Test: echtes Temp-Repo, `last_prod_deploy.json` mit einem frei erfundenen, nicht
    existierenden SHA; Aufruf von `_scope_diff_base()`; Assertion, dass kein Exception geworfen
    wird und der Rückgabewert dem Fallback-Pfad entspricht (Gate-Marker-SHA bzw. `"HEAD~1"`).

## Test Plan

Alle Tests laufen gegen echte Temp-Git-Repos (`git init`, echte Commits) mit echten
Subprozess- bzw. Direktimport-Aufrufen der echten Hook-Skripte (Muster: `_setup_repo()` /
`_run_staging_gate()` aus `tests/tdd/test_issue_916_gate_scope_marker.py`). KEINE Mocks —
Projektregel (CLAUDE.md "KEINE MOCKED TESTS"). Kein Dateiinhalt-String-Check als alleiniger
Beweis; jeder Test verifiziert das zurückgegebene bzw. beobachtbare Prozessverhalten
(Scope-String, Exit-Code, stdout).

- **Teil A:** AC-1 wird in einer neuen, kleinen Testfunktion abgedeckt (kann in
  `tests/tdd/test_issue_916_gate_scope_marker.py` oder einer neuen, schlanken
  `tests/tdd/test_issue_1116_repro.py` liegen — Entscheidung beim Implementieren anhand
  bestehender Datei-Kohäsion). Testoutput (grün) wird für
  `docs/artifacts/gate-scope-1109-1116-1121/repro-1116.md` verwendet.
- **Neue Testdatei `tests/tdd/test_issue_1121_git_diff_returncode.py`** deckt AC-2 bis AC-5 ab.
- **Neue Testdatei `tests/tdd/test_issue_1109_prod_deploy_marker.py`** deckt AC-6 bis AC-8 ab.
- **Regressionsschutz (kein neuer AC, aber Pflicht-Prüfpunkt vor Merge):**
  `tests/tdd/test_issue_916_gate_scope_marker.py`, `tests/tdd/test_issue_1084_gate_scope_cache.py`,
  `tests/tdd/test_staging_gate.py`, `tests/tdd/test_bundle_e_gate_tooling.py` MÜSSEN nach der
  Implementierung unverändert grün bleiben. **Einzige bewusste Ausnahme:** die Assertion in
  `test_issue_1084_gate_scope_cache.py::test_ac3_old_marker_format_falls_back_without_crash` wird von
  `docs-only` auf `backend` geändert (inkl. Docstring). Grund: dieser alte erwartete Wert war exakt
  das #1121-Bugverhalten (fehlgeschlagener Diff wie leerer Diff behandelt → fälschlich `docs-only`),
  das Teil B dieser Spec bewusst korrigiert. Das ist die einzige Abweichung von der
  „unverändert grün"-Regel in diesem Workflow.

## Known Limitations

- **Teil C (#1109) ist ohne die henemm-infra-Änderung wirkungslos.** Der neue Code in
  `prod_selftest.py::_scope_diff_base()` liest bevorzugt `.claude/last_prod_deploy.json` — diese
  Datei wird aber ausschließlich von `deploy-gregor-prod.sh` geschrieben. Solange dieses Script
  (separates Repo `henemm-infra`) nicht entsprechend angepasst ist, existiert die Datei nie, und
  `_scope_diff_base()` fällt in jedem Fall auf das bisherige Verhalten zurück (AC-7). Das ist eine
  **bewusste Abhängigkeit, kein Bug** — der gregor_zwanzig-seitige Teil ist eigenständig getestet
  und korrekt, wird aber erst nach der koordinierten infra-Änderung in echter Prod-Nutzung
  wirksam. Reihenfolge: henemm-infra-Änderung zuerst committen (MQ an `infra`-Instanz), danach ist
  der gregor_zwanzig-Teil bereits deploybar und wartet passiv auf die erste Marker-Datei.
- **Teil A (#1116) ist ein Doku-Close, kein neuer Schutzmechanismus.** Sollte künftig eine vierte
  Änderung an der Marker-/Cache-Semantik den in #1096 geschlossenen Vergiftungspfad wieder öffnen,
  deckt AC-1 dieser Spec das ab (Regressionstest bleibt aktiv), aber es gibt keinen zusätzlichen
  Code-Schutz über #1096 hinaus.
- **Teil B (#1121) ändert den Fallback-Wert für `_telegram_live_gate()` konzeptionell (AC-5):**
  bei nicht auflösbarer Basis wird konservativ geblockt statt "kein Treffer" angenommen. Das kann
  in seltenen Fällen (Ein-Commit-Repo, z.B. bei einem frisch initialisierten Test-Setup) das
  Telegram-Gate auslösen, obwohl kein echter Telegram-Pfad-Treffer vorliegt — bewusst in Kauf
  genommen (fail-closed über fail-open), betrifft in der Praxis nur pathologische Repo-Zustände,
  die im normalen linearen Deploy-Baum nicht auftreten.
- Der Marker `.claude/last_gate_scope.json` behält seine bisherige Doppelrolle (Diff-Basis für den
  nächsten Gate-Lauf UND Cache-Key für denselben Commit, siehe #1084/#1096). Der neue
  `last_prod_deploy.json`-Marker führt bewusst eine **dritte, sauber getrennte** Bedeutung ein
  ("zuletzt tatsächlich live deployter Commit") statt in denselben Marker gemischt zu werden — wie
  in der Analyse-Phase als Risiko identifiziert und hier vermieden.
- Verwandtes Issue #1078 (`e2e_commit_gate.py`, andere Root Cause: `git diff --cached` ist nach
  einem Commit immer leer) ist bewusst NICHT Teil dieser Spec — anderes Skript, eigene Ursache.

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** keine
- **Rationale:** Reines Bugfix-/Konsolidierungs-Tooling innerhalb bestehender Gate-Skripte
  (`.claude/hooks/`), vierte Iteration am selben, bereits in `issue_916_988_gate_scope_robustness.md`
  und `issue_1084_gate_scope_cache.md` etablierten Mechanismus. Der neue `last_prod_deploy.json`-
  Marker ist strukturell identisch zum bestehenden `last_gate_scope.json`-Muster (einfache
  JSON-Datei, ein Schreiber, mehrere Leser), keine neue Architektur-Entscheidung, kein neues
  Subsystem, keine Änderung an Produktcode, API-Verträgen oder Datenmodellen. Geprüft: keine der
  vorhandenen ADRs (`docs/adr/0001`-`0018`) behandelt Deploy-Gate-Mechanik oder Scope-Erkennung;
  die beiden Vorgänger-Specs kamen zum selben Schluss.

## Changelog

- 2026-07-09: Initial spec created
