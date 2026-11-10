# Context: fix-2424-verdict-ueberschreiben

## Request Summary
Issue #2424 (go-live-pflicht, Sicherheitsrisiko): Schreiben zwei Läufe ein Staging-Verdict für
denselben Commit, gewinnt der zuletzt geschriebene Top-Level-Wert (`staging_verdict`, `scope`).
Ein späteres oberflächliches `VERIFIED` überschreibt so ein gründliches `AMBIGUOUS`, und
`staging_gate.py --check` öffnet den Prod-Deploy.

## Ursache (am Stand `dc48066aa` nachvollzogen)
`.claude/hooks/staging_gate.py` `write_verdict()` Z. 345–516:
- Z. 422–428: `payload` wird aus dem aktuellen Aufruf gebaut (`staging_verdict`, `scope`, `verified_at`).
- Z. 445–504: bei `existing.verified_commit == sha` werden NUR `findings` gemergt
  (eigener Workflow ersetzt eigene, fremde bleiben — #1197/#1327/F002).
- Top-Level-Felder (`staging_verdict`, `scope`, `langs`, `frontend_pages_checked`,
  `frontend_browser_gate`) werden ungemergt überschrieben → „last writer wins".
- Leser: `gate_check()` Z. 691 prüft nur `data["staging_verdict"].startswith("VERIFIED")`.

Konkreter Schreiber von damals (CI-Deploy-Job „VERIFIED: CI smoke test (ROOT+HEALTH)") ist seit
#2047 S2 aus `.github/workflows/ci.yml` entfernt (grep: kein `write-verdict` mehr in ci.yml);
AGENTS.md:183 nennt ihn noch (Doku-Altlast). Die Lücke besteht für jeden zweiten Schreiber.

## Related Files
| File | Relevance |
|------|-----------|
| `.claude/hooks/staging_gate.py` | `write_verdict` (Merge), `gate_check` (Leser) — einzige Code-Änderung |
| `.claude/hooks/_e2e_paths.py` | `partition_findings`, `langs_vollstaendig`, `ERFORDERLICHE_SPRACHEN` |
| `tests/tdd/test_staging_gate_verdict_merge.py` | Bestehende Merge-Tests (AC-1..6, F002); Helfer `_write(...)` mit tmp `e2e_path`, `scope_override="backend"`, Gates per monkeypatch neutralisiert (Z. 77) — Vorlage für neue Tests |
| `tests/tdd/test_staging_gate.py`, `test_staging_gate_sprachen.py`, `test_attestation_findings_typsicher.py`, `test_e2e_verified_retention.py`, `test_issue_668_head_sha_dedup.py` | weitere Konsumenten/Wächter von write_verdict — dürfen nicht brechen |
| `.claude/agents/staging-validator.md` | Schreiber (VERIFIED/AMBIGUOUS), Regel „nie VERIFIED bei FAIL/SKIPPED" |
| `.claude/commands/e2e-verify.md`, `70-deploy.md` | Aufrufer/Leser; 70-deploy: AMBIGUOUS nur mit ausdrücklichem PO-OK |
| `AGENTS.md:183` | veraltete Erwähnung des CI-Smoke-Verdicts |

## Existing Patterns
- Workflow-Kennung je Schreiber: `OPENSPEC_ACTIVE_WORKFLOW` / `GZ_ACTIVE_WORKFLOW` / `"unknown"` (Z. 403–407), schon für Findings genutzt.
- Merge-Semantik der Findings: eigener Workflow ersetzt eigene Einträge, fremde bleiben. Dieselbe Semantik auf Verdict/Scope übertragen ist naheliegend.

## Lösungsrichtung (für die Analyse)
- Verdict je Workflow führen (z. B. `verdicts: {workflow: {verdict, scope, at}}`); eigener
  Workflow darf seinen eigenen Eintrag ersetzen (legitimer Re-Run nach Flake), fremder nicht.
- Top-Level `staging_verdict` = schwächstes über alle Workflows (AMBIGUOUS < VERIFIED);
  Top-Level `scope` = breitester (full-stack > frontend-only/backend > docs-only).
- `gate_check` bleibt bei Top-Level-Prüfung → keine Leser-Änderung nötig; optional Warnung bei Widerspruch.
- Altbestand ohne `verdicts`-Feld: bestehendes Top-Level als Eintrag des Workflows `legacy` übernehmen.

## Dependencies
- Upstream: `_e2e_paths`, `_detect_committed_scope`, `_frontend_browser_gate`, `_telegram_live_gate`.
- Downstream: `gate_check` (Prod-Deploy-Hard-Gate), `prod_selftest.py` (liest `verified_commit`), Issue-Close-Gate.

## Risks & Considerations
- Blast Radius hoch: falsches Merge kann den Prod-Deploy dauerhaft sperren (z. B. ein altes AMBIGUOUS
  eines fremden Workflows blockt jeden Folge-Lauf auf demselben Commit). Ausweg muss existieren:
  derselbe Workflow kann korrigieren; ein neuer Commit startet frisch.
- Nachbar #1640 (Scope-Cache `.claude/last_gate_scope.json` stuft zweiten Lauf auf docs-only):
  anderer Mechanismus (Scope-Erkennung), aber „breitester Scope gewinnt" dämpft die Wirkung beim
  Schreiben. Nicht in diesem Ticket lösen, nur nicht verschlimmern.
- Hook-/Gate-Code ⇒ Adversary-Risiko hoch, mindestens 2 Runden.

## Analysis

### Type
Bug (Sicherheitslücke im Prod-Deploy-Gate, Tooling)

### Befund (am Stand `a89d42464` erneut geprüft)
- `write_verdict()` (`.claude/hooks/staging_gate.py`) baut `payload` komplett aus dem aktuellen Aufruf;
  beim gleichen `verified_commit` werden nur `findings` gemergt. `staging_verdict`, `scope`, `langs`,
  `verified_at`, `frontend_pages_checked`, `frontend_browser_gate` → last writer wins.
- Leser des Top-Level-`staging_verdict` (alle drei prüfen nur `startswith("VERIFIED")`):
  `staging_gate.gate_check` (Exakt-Treffer), `_e2e_paths._nearest_verified_ancestor` (Vorfahren-Pfad),
  `prod_selftest.py` (Exakt-Treffer). Top-Level-`scope` wird von keinem Gate gelesen (Gate rechnet
  Scope selbst / per `--scope`), ist also nur Information; `langs` liest `_langs_fehlen`.
- Fix allein auf der Schreibseite reicht: korrekt gemergtes Top-Level ⇒ alle drei Leser automatisch richtig.

### Affected Files (with changes)
| File | Change Type | Description |
|------|-------------|-------------|
| `.claude/hooks/staging_gate.py` | MODIFY | `write_verdict`: `verdicts`-Map je Workflow, Top-Level aus Map ableiten (Helfer-Funktion) |
| `tests/tdd/test_staging_gate_verdict_merge.py` | MODIFY | neue Fälle: fremdes VERIFIED überschreibt AMBIGUOUS nicht; eigener Re-Run ersetzt; Scope breitester; Altbestand; `--check` blockt end-to-end |
| `AGENTS.md` | MODIFY | Z. 183: veralteten CI-Smoke-Verdict-Schreiber streichen |
| `docs/reference/gates_und_ratschen.md` | MODIFY | Merge-Semantik des Verdicts (1–3 Sätze) |

### Scope Assessment
- Files: 4 (1 Code, 1 Test, 2 Doku)
- Estimated LoC: +60/-5 Code, +120 Tests
- Risk Level: MEDIUM — kleine Änderung, aber im Hard Gate vor Prod; Fehler sperrt Deploys (fail-closed) oder öffnet sie (fail-open)

### Technical Approach (Entscheidung Tech Lead)
1. Neues Feld `verdicts: {<workflow>: {"verdict", "scope", "langs", "at"}}` in der Nachweis-Datei.
   Bei gleichem `verified_commit`: bestehende Map laden, eigenen Eintrag (Schlüssel = Workflow-Kennung,
   wie bei Findings) ersetzen, fremde behalten. Abweichender/fehlender/kaputter Commit ⇒ frische Map (wie heute).
2. Top-Level abgeleitet (eine reine Funktion, z. B. `_aggregate_verdicts(map)`):
   - `staging_verdict`: gibt es irgendeinen AMBIGUOUS-Eintrag ⇒ dessen Text (bei mehreren der erste nach
     Workflow-Name, deterministisch) mit Hinweis auf den Urheber-Workflow; sonst der VERIFIED-Text des aktuellen Schreibers.
   - `scope`: breitester Rang `full-stack > frontend-only = backend > docs-only` (frontend-only+backend ⇒ full-stack).
   - `langs`: Vereinigung über alle Einträge (jeder Lauf bezeugt nur seine Sprachen; Schnittmenge würde
     einen docs-only-Eintrag zum Dauerblocker machen).
   - `verified_at`: Zeitpunkt des aktuellen Schreibens (Verhalten wie heute; gleicher Commit ⇒ gleicher Code auf Staging).
   - `frontend_pages_checked`: Vereinigung; `frontend_browser_gate`-Vermerk bleibt erhalten, sobald ein Eintrag ihn trägt.
3. Altbestand (Datei mit gleichem Commit, aber ohne `verdicts`): Top-Level als Eintrag `legacy` übernehmen,
   damit ein vor dem Fix geschriebenes AMBIGUOUS nicht durch einen fremden Lauf verschwindet.
4. Leser (`gate_check`, `_nearest_verified_ancestor`, `prod_selftest`) bleiben unverändert. `gate_check` nennt
   bei AMBIGUOUS bereits den Verdict-Text; durch Schritt 2 steht darin der blockierende Workflow ⇒ Ausweg sichtbar.
5. Ausweg gegen Dauersperre: derselbe Workflow schreibt neu (Re-Run nach Flake ersetzt eigenen Eintrag);
   ein neuer Commit startet ohnehin frisch. Kein Override-Schalter (wäre genau die Lücke, die geschlossen wird).
6. BROKEN schreibt weiterhin nichts (unverändert) — BROKEN eines Workflows lässt dessen alten Eintrag stehen;
   ist der VERIFIED, bleibt das so (unverändert gegenüber heute, nicht Teil dieses Tickets).

### Befunde gegen den Plan
- Workflow-Kennung `unknown` (Aufruf ohne Env-Variable) teilt sich einen Schlüssel: zwei anonyme Läufe
  überschreiben sich weiterhin gegenseitig. Hinnehmbar: Aufrufer (`/e2e-verify`, staging-validator) setzen
  die Variable; Spec soll das als bekannte Grenze nennen, nicht lösen.
- Abgeschlossener Fremd-Workflow mit AMBIGUOUS auf demselben Commit kann nur mit dessen Kennung
  (`OPENSPEC_ACTIVE_WORKFLOW=<name>`) korrigiert werden — bewusst so, Meldung muss den Namen zeigen.
- Nachbar #1640 (Scope-Cache) unberührt; „breitester Scope" verschlimmert nichts.

### Dependencies
`_e2e_paths.partition_findings`, `ERFORDERLICHE_SPRACHEN`, `_detect_committed_scope`, `_frontend_browser_gate`,
`_telegram_live_gate` (unverändert). Downstream unverändert: `gate_check`, `_nearest_verified_ancestor`, `prod_selftest`.
Bestehende Wächter, die grün bleiben müssen: `test_staging_gate*.py`, `test_attestation_findings_typsicher.py`,
`test_e2e_verified_retention.py`, `test_issue_668_head_sha_dedup.py`, `test_issue_784_staging_gate_worktree_head.py`.

### Open Questions
- keine (rein technisch; keine Produktentscheidung nötig)
