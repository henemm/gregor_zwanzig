---
entity_id: issue_1096_gate_scope_selfpoison
type: bugfix
created: 2026-07-08
updated: 2026-07-08
status: implemented
version: "1.0"
workflow: fix-1096-gate-scope
tags: [gate, tooling, bugfix, deploy, testing]
---

# Gate-Scope-Selbstvergiftung beheben + Gate-Tests hermetisieren (#1096)

## Approval

- [x] Approved (PO „go", 2026-07-08)

## Purpose

`staging_gate.py::gate_check()` hat seit #1084 einen Scope-Cache in
`prod_selftest.py`, aber nie selbst bekommen — die Schreibseite
(`staging_gate.py`) hat den asymmetrischen Cache-Guard nie erhalten. Läuft
`gate_check()` ein zweites Mal auf demselben, bereits geprüften HEAD (wie beim
Deploy von `3f5d3cfa`, #1097), liefert die eigene Diff-Logik einen leeren
`HEAD..HEAD`-Diff → fälschlich `docs-only` → dieser falsche Wert wird in den
Marker geschrieben und von `prod_selftest.py`s Cache-Guard anschließend als
korrekt übernommen. Ein echter Code-Deploy wird dadurch als docs-only
klassifiziert, die Attestation trägt den falschen Scope, und der
Post-Deploy-Selftest wird stillschweigend übersprungen — Gate-Erosion am
kritischsten Pfad des Projekts. Zusätzlich läuft `TestGateCheckModeB`
(6 Tests) ohne `--scope`-Override gegen das echte, bewegliche Hauptrepo und
wird instabil (rot ohne Code-Regress), sobald der Scope zufällig auf
`docs-only` steht, weil der Skip-Zweig dann vor der eigentlich getesteten
Prüflogik greift. Diese Spec behebt beide Defekte an ihrer gemeinsamen
Wurzel: ein Shared-Helper macht den Cache-Zugriff für beide Gate-Skripte
identisch, und die Tests werden auf ein hermetisches Temp-Repo umgestellt.

## Source

- **File:** `.claude/hooks/_e2e_paths.py`
- **Identifier:** neue Funktion `cached_scope_for_sha(repo_dir, sha)`
- **File:** `.claude/hooks/staging_gate.py`
- **Identifier:** `def _detect_committed_scope` (Zeilen 127-171, Cache-Check
  ergänzen), `def gate_check` (Zeilen 277-345, docs-only-Skip-Zweig Zeile
  284-287 gegen Überschreiben eines bestehenden Nicht-docs-only-Cache-Eintrags
  für dieselbe SHA härten)
- **File:** `.claude/hooks/prod_selftest.py`
- **Identifier:** `def _detect_committed_scope` (Zeilen 411-471, Cache-Logik
  Zeilen 420-430 durch Aufruf des Shared-Helpers ersetzen)
- **File:** `tests/tdd/test_staging_gate.py`
- **Identifier:** `class TestGateCheckModeB` (Zeilen 85-195) — Umstellung auf
  hermetisches Temp-Git-Repo nach Muster
  `tests/tdd/test_issue_916_gate_scope_marker.py::_setup_repo`

> **Schicht-Hinweis:** Alle betroffenen Dateien liegen in `.claude/hooks/`
> (Deploy-/Test-Tooling) bzw. `tests/tdd/` — kein Produktcode in `frontend/`,
> `cmd/server/`, `internal/`, `api/` oder `src/`. Kein Prod-Deploy im Sinne der
> Frontend-/Backend-Bausteine für diesen Workflow nötig (analog #916/#988/#1084
> -Präzedenzfall); der Fix wird trotzdem regulär über den Post-Push-Workflow
> ausgeliefert, da er selbst den Deploy-Gate-Pfad ändert.

## Estimated Scope

- **LoC:** ~15-20 netto Produktivcode (Hooks), Testdatei-Umbau zusätzlich
  (zählt nicht gegen das 250-LoC-Limit lt. Konvention für Testcode-Migration
  ohne neues fachliches Verhalten)
- **Files:** 4 (3 Hooks + 1 Testdatei)
- **Effort:** medium (kleine Diffs, aber Risk Level HIGH wegen kritischem
  Deploy-Gate-Pfad)

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `_e2e_paths.py::read_last_gate_scope_entry` | intern | Bestehende Lesefunktion für den vollen Marker-Eintrag — Basis für den neuen Shared-Helper |
| `_e2e_paths.py::head_sha` | intern | Liefert den aktuellen HEAD-SHA für den Cache-Abgleich |
| `docs/specs/modules/issue_1084_gate_scope_cache.md` | spec | Direkter Vorläufer — führt den Marker-Scope-Cache in `prod_selftest.py` ein; diese Spec spiegelt ihn nach `staging_gate.py` und konsolidiert die Duplikat-Logik |
| `docs/specs/modules/issue_916_988_gate_scope_robustness.md` | spec | Ursprünglicher Marker-Mechanismus (Diff-Basis), bleibt als Fallback-Pfad unverändert bestehen |
| `tests/tdd/test_issue_916_gate_scope_marker.py::_setup_repo` | test-pattern | Vorbild für hermetisches Temp-Git-Repo, wird für die Migration von `TestGateCheckModeB` wiederverwendet |
| `tests/tdd/test_issue_1084_gate_scope_cache.py` | test | Bestehende Cache-Tests für `prod_selftest.py` — müssen nach der Konsolidierung auf den Shared-Helper unverändert grün bleiben |
| `deploy-gregor-prod.sh` (henemm-infra) | script | Ruft `staging_gate.py --check` ohne `--scope` auf — bleibt unverändert, profitiert aber von der Fix-Korrektheit bei Wiederholungsläufen |

## Implementation Details

### Fix 1 (Kern) — Shared-Cache-Helper, von beiden Gate-Skripten genutzt

**`_e2e_paths.py`:** neue Funktion

```python
def cached_scope_for_sha(repo_dir, sha) -> "str | None":
    """Gibt den im Marker gecachten Scope zurück, aber NUR wenn der Marker
    exakt auf `sha` zeigt UND ein gate_last_scope-Feld vorhanden ist. Sonst
    None (Aufrufer fällt auf die bestehende Diff-Logik zurück).

    Extrahiert aus prod_selftest.py (#1084), damit staging_gate.py und
    prod_selftest.py denselben Cache-Zugriff verwenden — Schreibseite und
    Leseseite dürfen nicht mehr auseinanderlaufen (Issue #1096).
    """
    entry = read_last_gate_scope_entry(repo_dir)
    if entry is None:
        return None
    cached = entry.get("gate_last_scope")
    if cached is not None and entry.get("gate_scope_sha") == sha:
        return cached
    return None
```

**`staging_gate.py::_detect_committed_scope()`:** ruft am Anfang
`_e2e_paths.cached_scope_for_sha(_shared_repo_dir(), _head_sha())` auf. Liefert
das einen Wert, wird dieser sofort zurückgegeben — **ohne** den
`HEAD..HEAD`-Diff überhaupt zu berechnen. Erst wenn der Helper `None` liefert
(kein Marker, Marker zeigt auf anderen Commit, altes Marker-Format), läuft die
bestehende Diff-Logik (Zeilen 132-171) unverändert weiter. Damit liefert ein
zweiter `gate_check()`-Lauf auf demselben HEAD den beim ersten Lauf tatsächlich
ermittelten (korrekten) Scope statt eines selbstreferenziellen leeren Diffs —
Selbstvergiftung wird strukturell unmöglich, weil der Marker-Schreib- und
-Lesepfad jetzt symmetrisch sind (vorher nur in `prod_selftest.py` vorhanden).

**`prod_selftest.py::_detect_committed_scope()`:** die bisherige, eigens
duplizierte Cache-Logik (Zeilen 420-430) wird durch denselben Aufruf von
`_e2e_paths.cached_scope_for_sha()` ersetzt (Duplikat entfernt, Konvention
„eine Quelle" aus CLAUDE.md).

### Fix 2 (Härtung) — docs-only-Skip überschreibt keinen besseren Cache-Eintrag

`staging_gate.py::gate_check()`, docs-only-Skip-Zweig (Zeilen 284-287): bevor
`write_last_gate_scope(..., "docs-only")` geschrieben wird, wird geprüft, ob
bereits ein Cache-Eintrag für exakt dieselbe SHA mit einem Nicht-docs-only-Wert
existiert (`_e2e_paths.cached_scope_for_sha(...)` liefert einen Wert !=
`"docs-only"`). Ist das der Fall, wird der bestehende (bessere) Wert
beibehalten statt überschrieben — deckt den Restfall ab, dass ein expliziter
`--scope`-Override oder ein vorheriger vollständiger Lauf für denselben Commit
bereits den echten Scope ermittelt hat.

### Fix 3 — Test-Migration `TestGateCheckModeB` auf hermetisches Temp-Repo

Alle 9 Tests der Klasse (Zeilen 85-195) laufen künftig gegen ein
`_setup_repo(tmp_path)`-Temp-Git-Repo (Muster identisch zu
`test_issue_916_gate_scope_marker.py`: `git init`, Hook-Dateien nach
`<repo>/.claude/hooks/` kopieren, Baseline-Commit, `staging_gate.py --check`
via `subprocess` mit `cwd=<temp-repo>`). Kein Test läuft mehr mit
`cwd=Hauptrepo` und mutiert damit nie mehr den echten, produktiven
`.claude/last_gate_scope.json`. Tests, die nicht die Scope-Erkennung selbst
prüfen (sondern z.B. Attestation-Alter oder `verified_commit`-Mismatch),
erhalten zusätzlich einen expliziten `--scope=backend`, damit der docs-only-
Skip-Zweig ihre eigentliche Prüflogik nicht vor der Zeit greift.

## Expected Behavior

- **Input:** Zwei aufeinanderfolgende `staging_gate.py --check`-Läufe im
  selben Repo-Zustand auf demselben HEAD (z.B. Deploy-Script ruft das Gate,
  anschließend der Validator `write_verdict()` oder ein manueller
  Wiederholungslauf).
- **Output:** Der zweite Lauf liefert denselben, tatsächlich beim ersten Lauf
  ermittelten Scope (z.B. `frontend-only`) statt fälschlich `docs-only`. Die
  Attestation (`e2e_verified/<sha>.json`) trägt nie einen falschen `docs-only`-
  Scope für einen Commit, der echten Code enthält. Der Post-Deploy-Selftest
  wird für echte Code-Deploys nie mehr wegen eines falsch gecachten Werts
  übersprungen.
- **Side effects:** `.claude/last_gate_scope.json` wird weiterhin nur von
  `staging_gate.py` geschrieben (unverändert seit #916); `prod_selftest.py`
  bleibt reiner Leser. Die 6+ betroffenen Tests in `TestGateCheckModeB`
  hinterlassen nach der Migration keine Spuren mehr in der echten
  Hauptrepo-Marker-Datei.

## Acceptance Criteria

- **AC-1:** Given ein Code-Commit (z.B. Frontend-Änderung) hat einen ersten,
  vollständigen Gate-Lauf mit korrekt erkanntem Scope bereits erfolgreich
  bestanden / When das Gate für exakt denselben Commit ein zweites Mal läuft
  (z.B. weil der Validator unmittelbar danach die Attestation schreibt, oder
  ein Wiederholungslauf desselben Deploys erfolgt) / Then wird der Commit
  weiterhin mit seinem echten, bereits ermittelten Scope behandelt — der Lauf
  wird NICHT als „docs-only" heruntergestuft und die Prüfung wird NICHT
  übersprungen, sondern regulär (inkl. Attestations-Check) durchlaufen.
  - Test: echtes Temp-Git-Repo mit echtem Frontend-Commit, zwei reale
    `staging_gate.py --check`-Aufrufe hintereinander gegen denselben HEAD;
    Assertion auf Exit-Code und gemeldeten Scope des zweiten Laufs, kein
    Dateiinhalt-Grep.

- **AC-2:** Given ein Code-Commit wird unmittelbar nach einem erfolgreichen
  Gate-Lauf für denselben Commit verifiziert (Validator schreibt die
  Attestation) / When die Attestation geschrieben wird / Then trägt sie nie
  fälschlich `"scope": "docs-only"`, obwohl der Commit tatsächlich Code
  enthält.
  - Test: echtes Temp-Repo, echter Backend-Commit, realer
    `gate_check()`-Lauf gefolgt von einem realen Attestations-Schreibvorgang
    für denselben HEAD; die geschriebene, geparste JSON-Datei wird auf ihr
    `scope`-Feld geprüft (erwartet: der echte Scope, z.B. `backend`).

- **AC-3:** Given ein echtes Code-Deploy (Commit enthält Frontend- und/oder
  Backend-Änderungen) durchläuft den vollständigen Post-Push-Workflow / When
  der Post-Deploy-Selftest nach dem Prod-Deploy läuft / Then wird er niemals
  wegen eines falsch als „docs-only" gecachten Scopes übersprungen — er prüft
  den Deploy tatsächlich.
  - Test: echtes Temp-Repo, das die Deploy-Reihenfolge nachstellt (Gate-Lauf,
    dann Selftest-Scope-Ermittlung für denselben HEAD), Assertion, dass der
    von `prod_selftest.py`s Scope-Ermittlung gelieferte Wert für einen
    Code-Commit niemals `docs-only` ist.

- **AC-4:** Given ein Commit enthält tatsächlich nur Dokumentation/Tooling
  (Erstlauf ohne Marker, oder Commits ausschließlich unter `docs/`, `.claude/`,
  `*.md`, `tests/` seit dem letzten Gate-Lauf) / When das Gate oder der
  Selftest laufen / Then verhalten sie sich unverändert wie vor diesem Fix:
  Gate und Selftest überspringen die Prüfung mit Exit 0 — kein Regress zu den
  bestehenden docs-only-Garantien aus #786/#916.
  - Test: echtes Temp-Repo mit einem Commit, der ausschließlich eine
    Markdown-Datei ändert (kein vorheriger Marker); realer
    `staging_gate.py --check`-Aufruf; Assertion auf Exit 0 und
    Skip-Meldung/Scope `docs-only`.

- **AC-5:** Given die migrierten Gate-Tests laufen / When ein beliebiger Test
  aus `TestGateCheckModeB` ausgeführt wird / Then verändert dieser Testlauf zu
  keinem Zeitpunkt die echten Gate-State-Dateien des Hauptrepos
  (`.claude/last_gate_scope.json`, `.claude/e2e_verified/*.json` im
  Hauptrepo-Arbeitsbaum) — jeder Test operiert ausschließlich auf einem
  isolierten Temp-Repo.
  - Test: vor und nach dem vollständigen Testklassen-Lauf wird
    `.claude/last_gate_scope.json` im Hauptrepo (mtime + Inhalt) verglichen —
    unverändert. Kein Mock; echter Dateisystem-Vergleich.

- **AC-6:** Given die migrierten Gate-Tests / When die gesamte Testklasse
  mehrfach hintereinander ausgeführt wird (z.B. 20 Wiederholungen) / Then
  bestehen alle Tests deterministisch, unabhängig vom aktuellen Scope-Zustand
  des echten Hauptrepos zum Ausführungszeitpunkt.
  - Test: `pytest tests/tdd/test_staging_gate.py::TestGateCheckModeB` 20-mal
    hintereinander real ausgeführt (z.B. `pytest-repeat` oder Shell-Schleife);
    alle Läufe grün.

## Known Limitations

- **Verhaltensänderung bei Re-Deploy desselben Commits:** Statt eines
  fälschlichen Skips läuft künftig der volle Gate-Check erneut. Das setzt
  voraus, dass die zugrunde liegende Attestation (`e2e_verified/<sha>.json`)
  noch gültig und frisch ist (< konfiguriertes Alterslimit, `STALE_HOURS`);
  ist sie es nicht, blockt das Gate den Re-Deploy, statt ihn (fälschlich)
  durchzuwinken. Das ist eine bewusst konservative Entscheidung — im Zweifel
  blocken statt Gate-Erosion riskieren.
- **Doppel-Lauf-Ursache separat verfolgt:** Warum `gate_check()` beim
  #1097-Deploy überhaupt zweimal für denselben Commit lief (paralleler Deploy
  vs. Retry im Deploy-Script), wird in Issue #1119 geklärt — dieser Fix macht
  den Doppel-Lauf selbst sicher (idempotent korrekt), beseitigt aber nicht
  dessen Ursache und ist davon unabhängig.
- **Bestehender vergifteter Marker korrigiert sich selbst:** Der aktuell im
  Hauptrepo falsch auf `docs-only` stehende Marker für `3f5d3cfa` wird NICHT
  von Hand editiert (User-Stopp 2026-07-08, Gate-State-Dateien nie per Hand
  anfassen). Er korrigiert sich beim nächsten regulären, vollständigen
  Gate-Lauf auf einen neuen Commit von selbst, da dieser Lauf den Marker mit
  dem dann echten Scope überschreibt.
- **Cache-Fenster bleibt exakt-SHA-gebunden:** Der Cache greift weiterhin nur,
  wenn `gate_scope_sha` exakt dem aktuellen HEAD entspricht (unverändert seit
  #1084) — bei jedem neuen Commit läuft wieder die volle, diff-basierte
  Herleitung.

## Test Plan

Alle Tests laufen gegen echte Temp-Git-Repos (`git init`, echte Commits) mit
echten Subprozess-Aufrufen der echten Hook-Skripte — KEINE Mocks (Projektregel
CLAUDE.md „KEINE MOCKED TESTS"). Kein Dateiinhalt-String-Grep; jeder Test
verifiziert das zurückgegebene bzw. geschriebene Verhalten (Scope-String,
Exit-Code, geparstes JSON-Feld).

- `TestGateCheckModeB` (`tests/tdd/test_staging_gate.py`) komplett auf
  hermetisches Temp-Repo umgestellt (Muster `_setup_repo` aus
  `test_issue_916_gate_scope_marker.py`) — deckt AC-1, AC-4, AC-5 ab.
- Neue Tests für das Selbstvergiftungs-Szenario (Doppel-Lauf auf demselben
  HEAD) decken AC-1, AC-2, AC-3 ab — entweder als Ergänzung in
  `test_staging_gate.py` oder in einer neuen Datei
  `tests/tdd/test_issue_1096_gate_scope_selfpoison.py`.
- AC-6 (Determinismus) wird durch einen wiederholten realen Testlauf
  (mindestens 20 Durchläufe) nachgewiesen, kein separater Unit-Test.
- **Regressionsschutz (Pflicht-Prüfpunkt vor Merge, keine eigenen ACs):**
  `tests/tdd/test_issue_916_gate_scope_marker.py`,
  `tests/tdd/test_issue_1084_gate_scope_cache.py` und
  `tests/tdd/test_bundle_e_gate_tooling.py` müssen nach der Konsolidierung auf
  den Shared-Helper unverändert grün bleiben.

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** keine
- **Rationale:** Reines Bugfix-Tooling innerhalb bestehender Gate-Skripte
  (`.claude/hooks/`), dritte Iteration am selben, bereits etablierten
  Marker-Mechanismus (#916 → #988 → #1084 → dieses Issue). Keine neue
  Architektur-Entscheidung, kein neues Subsystem, keine Änderung an
  Produktcode, API-Verträgen oder Datenmodellen. Keine der vorhandenen ADRs
  behandelt Deploy-Gate-Mechanik oder Scope-Erkennung — die Vorgänger-Specs
  kamen zum selben Schluss.

## Changelog

- 2026-07-08: Initial spec created
- 2026-07-08: Fix-Loop nach Adversary-Findings F001/F002 — docs-only-Cache-Werte
  gelten als Cache-Miss, HEAD~1-Fallback bei Marker==HEAD; F003 → #1121
