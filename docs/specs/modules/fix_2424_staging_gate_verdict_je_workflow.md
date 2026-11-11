---
entity_id: fix_2424_staging_gate_verdict_je_workflow
type: bugfix
created: 2026-11-10
updated: 2026-11-10
status: draft
workflow: fix-2424-verdict-ueberschreiben
---

# Staging-Verdict je Workflow führen statt "last writer wins" (#2424)

## Approval

- [ ] Approved

## Purpose

Schreiben zwei Läufe ein Staging-Verdict für denselben Commit, überschreibt heute der zuletzt schreibende Lauf `staging_verdict` und `scope`. Ein späteres oberflächliches `VERIFIED` öffnet so den Prod-Deploy, obwohl ein gründlicherer Lauf `AMBIGUOUS` gemeldet hat. Die Nachweis-Datei führt künftig je Workflow ein eigenes Verdict und leitet das Top-Level daraus ab (schwächstes Verdict gewinnt).

## Source

- **File:** `.claude/hooks/staging_gate.py`
- **Identifier:** `write_verdict` (Merge-Block für gleichen `verified_commit`) und neue reine Hilfsfunktion `_aggregate_verdicts`

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `_e2e_paths.partition_findings`, `ERFORDERLICHE_SPRACHEN`, `langs_vollstaendig` | module | Findings-Bereinigung, Sprach-Whitelist (unverändert) |
| `_detect_committed_scope`, `_frontend_browser_gate`, `_telegram_live_gate` | function | Scope-Erkennung und vorgelagerte Gates (unverändert) |
| `gate_check` | function | Prod-Deploy-Hard-Gate, liest Top-Level `staging_verdict` (unverändert) |
| `_e2e_paths._nearest_verified_ancestor` | function | Vorfahren-Pfad, liest Top-Level `staging_verdict` (unverändert) |
| `prod_selftest.py` | script | liest `verified_commit` / Top-Level-Verdict (unverändert) |
| Spec `fix_1197_staging_gate_verdict_merge` | spec | Findings-Merge (#1197/#1327/F002), muss unverändert bleiben |

## Scope

### Affected Files
| File | Change Type | Description |
|------|-------------|-------------|
| `.claude/hooks/staging_gate.py` | MODIFY | `write_verdict`: `verdicts`-Map je Workflow pflegen, Top-Level über `_aggregate_verdicts` ableiten |
| `tests/tdd/test_staging_gate_verdict_merge.py` | MODIFY | neue Fälle zu AC-1 bis AC-9 (Verdict-Merge) |
| `AGENTS.md` | MODIFY | Z. ~183: veralteten CI-Smoke-Verdict-Schreiber streichen (seit #2047 S2 nicht mehr in `ci.yml`) |
| `docs/reference/gates_und_ratschen.md` | MODIFY | 1-3 Sätze zur Merge-Semantik des Verdicts |

### Estimated Changes
- **LoC:** +60/-5 Code, +120 Tests, wenige Zeilen Doku
- **Files:** 4
- **Effort:** medium

## Implementation Details

**Neues Feld** `verdicts` in `.claude/e2e_verified/<sha>.json`: Map `{<workflow>: {"verdict", "scope", "langs", "at"}}`, Schlüssel ist dieselbe Workflow-Kennung wie bei Findings (`OPENSPEC_ACTIVE_WORKFLOW`, sonst `GZ_ACTIVE_WORKFLOW`, sonst `unknown`).

**Ablauf in `write_verdict`** (nach den bestehenden Prüfungen, Vorbedingungen und Fehlerpfade unverändert): Existiert die Datei mit gleichem `verified_commit`, wird die bestehende `verdicts`-Map geladen, der Eintrag des eigenen Workflows ersetzt, fremde Einträge bleiben. Bei abweichendem, fehlendem oder kaputtem Commit oder Nicht-Dict-JSON entsteht eine frische Map mit nur dem eigenen Eintrag (wie heute).

**Altbestand:** Hat die Datei gleichen Commit, aber kein `verdicts`, wird das vorhandene Top-Level (`staging_verdict`, `scope`, `langs`) als Eintrag `legacy` übernommen, damit ein vor dem Fix geschriebenes `AMBIGUOUS` nicht durch einen fremden Lauf verschwindet.

**Reine Funktion `_aggregate_verdicts(verdicts, aktuell)`** leitet das Top-Level ab:
- `staging_verdict`: Gibt es mindestens einen `AMBIGUOUS`-Eintrag, wird dessen Text (bei mehreren der erste nach Workflow-Name sortiert, deterministisch) mit Urheber-Hinweis ausgegeben, z. B. `AMBIGUOUS (Workflow <name>): <Text>`. Das Präfix `AMBIGUOUS` bleibt vorn, damit der Lese-Check (`startswith("VERIFIED")`) sicher blockt. Sonst gilt der VERIFIED-Text des aktuellen Schreibers.
- `scope`: breitester Rang `full-stack > frontend-only = backend > docs-only`; frontend-only plus backend ergibt `full-stack`.
- `langs`: Vereinigung über alle Einträge (Schnittmenge würde einen docs-only-Eintrag zum Dauerblocker machen).
- `verified_at`: Zeitpunkt des aktuellen Schreibens (wie heute).
- `frontend_pages_checked`: Vereinigung; `frontend_browser_gate`-Vermerk bleibt erhalten, sobald ein Eintrag ihn trägt.

**Findings-Merge** (#1197/#1327/F002) bleibt unverändert; er läuft unabhängig vom Verdict-Merge.

**Leser unverändert:** `gate_check`, `_e2e_paths._nearest_verified_ancestor` und `prod_selftest.py` prüfen nur das Top-Level; ein korrekt abgeleitetes Top-Level macht sie automatisch richtig. Top-Level-`scope` wird von keinem Gate gelesen (nur Information). `gate_check` nennt bei Blockade bereits den Verdict-Text, in dem nun der blockierende Workflow steht.

**Ausweg gegen Dauersperre:** Der blockierende Workflow schreibt neu (ersetzt seinen eigenen Eintrag), oder ein neuer Commit startet frisch. Es gibt bewusst keinen Override-Schalter, er wäre genau die Lücke, die hier geschlossen wird. `BROKEN` schreibt weiterhin nichts und lässt bestehende Einträge unberührt.

## Bekannte Grenzen

- **Kennung `unknown`:** Läufe ohne gesetzte Workflow-Variable teilen sich einen Schlüssel und überschreiben sich weiterhin gegenseitig. Hinnehmbar, da `/e2e-verify` und der staging-validator die Variable setzen; wird hier nicht gelöst.
- **Fremdes AMBIGUOUS korrigieren:** Ein `AMBIGUOUS` eines anderen (womöglich abgeschlossenen) Workflows lässt sich nur mit dessen Kennung (`OPENSPEC_ACTIVE_WORKFLOW=<name>`) ersetzen. Das ist gewollt; die Meldung nennt den Namen.
- **BROKEN:** Ein BROKEN-Lauf lässt den alten Eintrag desselben Workflows stehen (unverändert gegenüber heute).
- **#1640 (Scope-Cache `.claude/last_gate_scope.json`)** bleibt unberührt; "breitester Scope gewinnt" verschlimmert dort nichts.

## Test Plan

### Automated Tests (TDD RED)

Datei `tests/tdd/test_staging_gate_verdict_merge.py`, bestehende Helfer (`_write_findings`, `_write_existing`, `_call`) und das vorhandene autouse-monkeypatch-Muster werden weiterverwendet; keine zusätzlichen Mocks/`patch`. Workflow-Kennung wird per `monkeypatch.setenv("OPENSPEC_ACTIVE_WORKFLOW", ...)` gesetzt. Geprüft wird die geschriebene Datei per `json.loads` und, für AC-1, der echte Aufruf `gate_check`/`staging_gate.py --check` auf dieser Datei.

- [ ] `test_ac1_fremdes_verified_ueberschreibt_ambiguous_nicht`: GIVEN Workflow A schrieb AMBIGUOUS, WHEN Workflow B VERIFIED schreibt, THEN Top-Level beginnt mit AMBIGUOUS und nennt A.
- [ ] `test_ac1_gate_check_blockt_und_nennt_workflow`: GIVEN obige Datei, WHEN `gate_check` läuft, THEN Rückgabe 1 und Ausgabe enthält den Namen von A.
- [ ] `test_ac2_eigener_rerun_ersetzt_eigenen_eintrag`: GIVEN A schrieb AMBIGUOUS, WHEN A VERIFIED schreibt, THEN Top-Level VERIFIED und `gate_check` gibt 0.
- [ ] `test_ac3_scope_breitester_rang_kein_herabstufen`: full-stack danach docs-only bleibt full-stack; frontend-only danach backend ergibt full-stack.
- [ ] `test_ac4_langs_vereinigung`: A bezeugt `["de"]`, B `["en"]`, Top-Level `langs` enthält beide.
- [ ] `test_ac5_frontend_pages_vereinigung_und_browser_gate_vermerk`: A trägt `frontend_pages_checked` ["/trips"], B ["/compare"] und einen `frontend_browser_gate`-Vermerk, Top-Level enthält beide Seiten und den Vermerk.
- [ ] `test_ac6_altbestand_wird_legacy_und_bleibt_blockierend`: Datei ohne `verdicts` mit AMBIGUOUS, fremder Lauf schreibt VERIFIED, Top-Level bleibt AMBIGUOUS, `verdicts` enthält `legacy`.
- [ ] `test_ac7_neuer_commit_startet_frisch`: bestehende Datei mit anderem `verified_commit` und AMBIGUOUS, neuer Schreibvorgang ergibt nur den eigenen Eintrag.
- [ ] `test_ac8_findings_merge_unveraendert`: Findings fremder Workflows bleiben, eigene werden ersetzt (Regression zu #1197/#1327/F002; bestehende Tests bleiben grün).
- [ ] `test_ac9_leser_sehen_korrektes_toplevel`: `_e2e_paths._nearest_verified_ancestor` akzeptiert die Datei bei reinem VERIFIED und lehnt sie bei gemischtem Stand (AMBIGUOUS) ab.
- [ ] `test_aggregate_verdicts_deterministisch`: reine Funktion liefert bei zwei AMBIGUOUS-Einträgen unabhängig von der Einfügereihenfolge denselben (nach Workflow-Name ersten) Text.

Bestehende Wächter müssen grün bleiben: `test_staging_gate*.py`, `test_attestation_findings_typsicher.py`, `test_e2e_verified_retention.py`, `test_issue_668_head_sha_dedup.py`, `test_issue_784_staging_gate_worktree_head.py`.

## Acceptance Criteria

- **AC-1:** Given Workflow A hat für den Commit AMBIGUOUS geschrieben / When ein fremder Workflow B für denselben Commit VERIFIED schreibt und danach `staging_gate.py --check` läuft / Then bleibt das Top-Level-Verdict AMBIGUOUS, der Prod-Deploy wird blockiert und die Meldung nennt Workflow A als Urheber.
  - Test: Deploy-Gate-Aufruf auf der geschriebenen Nachweis-Datei endet mit Exit 1 und zeigt den Namen von A.
- **AC-2:** Given Workflow A hat AMBIGUOUS geschrieben / When derselbe Workflow A (Re-Run nach Flake) für denselben Commit VERIFIED schreibt / Then ersetzt dies seinen eigenen Eintrag, das Top-Level ist VERIFIED und das Deploy-Gate öffnet.
  - Test: Schreiben mit gleicher Workflow-Kennung, danach `--check` mit Exit 0.
- **AC-3:** Given mehrere Workflows haben für denselben Commit Einträge mit unterschiedlichem Scope geschrieben / When ein späterer Lauf mit schmalerem Scope (z. B. docs-only) schreibt oder frontend-only und backend zusammentreffen / Then bleibt der Top-Level-Scope der breiteste (full-stack > frontend-only = backend > docs-only), frontend-only plus backend ergibt full-stack.
  - Test: Schreibreihenfolge full-stack, docs-only liefert full-stack; frontend-only, backend liefert full-stack.
- **AC-4:** Given zwei Workflows haben für denselben Commit je andere Sprachen bezeugt (de bzw. en) / When die Nachweis-Datei geschrieben ist / Then enthält das Top-Level `langs` die Vereinigung beider Sprachen, sodass ein docs-only-Eintrag das Sprach-Gate nicht dauerhaft blockiert.
  - Test: Zwei Schreibvorgänge mit `["de"]` und `["en"]` ergeben `["de", "en"]`.
- **AC-5:** Given Einträge mehrerer Workflows tragen geprüfte Frontend-Seiten / When das Top-Level abgeleitet wird / Then ist `frontend_pages_checked` die Vereinigung und ein vorhandener `frontend_browser_gate`-Vermerk bleibt erhalten.
  - Test: Zwei Schreibvorgänge mit verschiedenen Seitenlisten ergeben die Vereinigung, der Vermerk eines Eintrags bleibt sichtbar.
- **AC-6:** Given eine vor dem Fix geschriebene Nachweis-Datei mit AMBIGUOUS ohne `verdicts`-Feld / When ein fremder Workflow VERIFIED für denselben Commit schreibt / Then wird der Altbestand als Eintrag `legacy` übernommen und das AMBIGUOUS bleibt wirksam, das Gate blockt weiter.
  - Test: Datei im Altformat vorbereiten, fremder Lauf schreibt VERIFIED, Top-Level bleibt AMBIGUOUS und `verdicts` enthält `legacy`.
- **AC-7:** Given eine Nachweis-Datei mit AMBIGUOUS gehört zu einem anderen Commit / When für den aktuellen Commit VERIFIED geschrieben wird / Then startet die Datei frisch, es gibt keinen Fremd-Eintrag und das Gate öffnet.
  - Test: Bestehende Datei mit abweichendem `verified_commit`, nach dem Schreiben nur eigener Eintrag und `--check` Exit 0.
- **AC-8:** Given zwei Workflows haben Findings für denselben Commit geschrieben / When der Verdict-Merge läuft / Then verhält sich der Findings-Merge unverändert (eigene Findings ersetzt, fremde und taglose bleiben, Dedup nur gegen taglosen Altbestand, #1197/#1327/F002).
  - Test: Die bestehenden Findings-Merge-Tests bleiben grün, ein zusätzlicher Fall prüft Findings und Verdicts im selben Schreibvorgang.
- **AC-9:** Given die Nachweis-Datei hat ein abgeleitetes Top-Level / When `gate_check`, `_e2e_paths._nearest_verified_ancestor` und `prod_selftest.py` sie lesen / Then treffen alle drei ohne Code-Änderung die richtige Entscheidung (VERIFIED öffnet, gemischter Stand mit AMBIGUOUS blockt).
  - Test: `gate_check` und `_nearest_verified_ancestor` auf einer Datei mit reinem VERIFIED bzw. gemischtem Stand aufrufen; keine Änderung an diesen Lesern im Diff.

## Definition of Done

- [ ] AC-1 bis AC-9 sind durch Tests in `tests/tdd/test_staging_gate_verdict_merge.py` abgedeckt und grün.
- [ ] Bestehende Wächter (`test_staging_gate*.py`, `test_attestation_findings_typsicher.py`, `test_e2e_verified_retention.py`, `test_issue_668_head_sha_dedup.py`, `test_issue_784_staging_gate_worktree_head.py`) bleiben grün.
- [ ] Mutations-Gegenprobe: „last writer wins" wiederhergestellt (Top-Level aus aktuellem Aufruf statt aus `verdicts`) macht mindestens AC-1 und AC-6 rot.
- [ ] `AGENTS.md` nennt den entfernten CI-Smoke-Verdict-Schreiber nicht mehr; `docs/reference/gates_und_ratschen.md` beschreibt die Merge-Semantik.

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** keine
- **Rationale:** Keine neue Entscheidung: Die Spec überträgt die bestehende Merge-Semantik der Findings (#1197/#1327/F002, eigener Workflow ersetzt eigene Einträge, fremde bleiben) auf Verdict und Scope und schließt damit eine Lücke im bestehenden Prod-Deploy-Gate. Test- und Deploy-Strategie bleiben unverändert.

## Changelog

- 2026-11-10: Initial spec created (Issue #2424)
