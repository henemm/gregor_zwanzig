---
entity_id: fix_1409_worktree_test_paths
type: bugfix
created: 2026-07-28
updated: 2026-07-28
status: draft
version: "1.0"
tags: [tests, worktree, gates, infrastructure]
---

<!-- Issue #1409 — Lieferung A: Pfadfix Klasse A + Wirkungsnachweis -->

# Fix #1409 (Lieferung A) — Worktree-relative Prüfling-Pfade in Klasse-A-Tests

## Approval

- [ ] Approved

## Purpose

Fünf Testdateien laden ihren Prüfling (das zu prüfende `.claude/hooks/*.py`-Skript)
über den fest verdrahteten Hauptrepo-Pfad `/home/hem/gregor_zwanzig/...` statt
worktree-relativ. Aus einem Git-Worktree heraus prüfen diese Tests damit die
**unveränderte** Hauptrepo-Kopie des Skripts und melden falsches Grün, obwohl die
im Worktree tatsächlich bearbeitete Datei kaputt sein kann. Diese Lieferung stellt
die fünf betroffenen Stellen auf worktree-relative Auflösung um, entfernt einen
zusätzlich gefundenen strukturell falsch-grünen Test (`test_ac3` in
`test_issue_465_workflow_optimierung.py`, der auf einen im Zuge der
Plugin-Migration entfernten Pfad zeigt) und liefert einen Mutations-Beleg, der
beweist, dass die Umstellung wirkt.

## Source

- **File:** `tests/tdd/test_issue_862_849_col_labels.py` (Zeile 22)
- **File:** `tests/tdd/test_prod_selftest_730.py` (Zeile 30; Zeile 31 `REPO_DIR` bleibt unverändert)
- **File:** `tests/tdd/test_issue_465_workflow_optimierung.py` (Zeile 27; Zeile 26 + zugehöriger Test werden gelöscht)
- **File:** `tests/tdd/test_issue_603_design_fidelity_gate.py` (Zeilen 23–26)
- **File:** `tests/tdd/test_622_fidelity_pre_actions.py` (Zeilen 33–41)
- **File:** `tests/tdd/test_worktree_path_resolution_effect.py` (NEU — Mutations-Beleg)

Betroffen ist ausschließlich Test-Infrastruktur (`tests/tdd/`), kein Produktivcode
in `src/`, `api/`, `internal/` oder `frontend/`.

## Estimated Scope

- **LoC:** ~180 (Pfadfix ~70 inkl. Begründungskommentare minus ~12 gelöschte Zeilen aus `test_ac3`; Wirkungsnachweis ~110)
- **Files:** 5 MODIFY, 1 CREATE
- **Effort:** low

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `tests/tdd/test_staging_gate.py:32-36` | Vorbild | Kanonisches Muster `_REPO_ROOT = Path(__file__).resolve().parents[2]` für Prüfling-Auflösung |
| `tests/tdd/test_prod_selftest_564.py:40-45` | Vorbild | Zweites Vorbild desselben Musters |
| `tests/tdd/test_bundle_h_908_973_987_staging_auth.py:45-62` | Vorbild | Drittes Vorbild, inkl. Begründungskommentar für die bewusste Trennung Prüfling (worktree) vs. `REPO_DIR` (Hauptrepo) |
| `.claude/hooks/briefing_mail_validator.py` | Prüfling | Mail-Gate-Werkzeug, kritischste Stelle |
| `.claude/hooks/prod_selftest.py` | Prüfling | trägt selbst `REPO_DIR = Path("/home/hem/gregor_zwanzig")` (Zeile 56) — bewusst unverändert |
| `.claude/hooks/email_spec_validator.py` | Prüfling | ersetzt in `test_issue_465` die `EMAIL_VALIDATOR_PY`-Konstante |
| `.claude/hooks/design_fidelity_diff.py` | Prüfling | löst Soll-Bilder + Artefaktziel zusätzlich über `Path(".")` relativ zum `cwd` auf (Zeilen 292-294) — deshalb Drei-Konstanten-Split |
| `.claude/hooks/pre_issue_close_design_gate.py` | Prüfling | liest `CLAUDE_PROJECT_DIR`, kein harter Hauptrepo-Pfad |
| `docs/specs/modules/fix_1382_deploy_gate_evidence.md` | Spec | Dieselbe Fehlerfamilie (Schreibweg ≠ Leseweg) |
| `docs/specs/modules/issue_784_staging_gate_worktree_head.md` | Spec | Worktree-HEAD vs. Hauptrepo-HEAD |
| `docs/context/fix-1409-worktree-pfade.md` | Kontext | Vollständige Bestandsaufnahme, Klassifikation A/B/C, PO-Schnitt |

## Implementation Details

### 1. Pfadfix (fünf Stellen)

**Kanonisches Muster** (dreifach im Bestand vorexerziert):

```
_REPO_ROOT = Path(__file__).resolve().parents[2]
_HOOKS_SRC = _REPO_ROOT / ".claude" / "hooks"
PRUEFLING = _HOOKS_SRC / "<datei>.py"
```

- **`test_issue_862_849_col_labels.py:22`** — `_load_validator()` lädt
  `briefing_mail_validator.py` derzeit über den festen String-Pfad. Wird auf die
  worktree-relative Konstante umgestellt.
- **`test_prod_selftest_730.py:30`** — `PROD_SELFTEST` wird worktree-relativ.
  `REPO_DIR` (Zeile 31) bleibt unverändert Hauptrepo, weil `prod_selftest.py`
  selbst intern `REPO_DIR` auf das Hauptrepo verdrahtet (geteilte Attestation,
  Prod wird nur von dort deployt) — ein Test kann das nicht durch Pfadwahl
  umgehen.
- **`test_issue_465_workflow_optimierung.py:27`** — `EMAIL_VALIDATOR_PY` wird
  worktree-relativ. Zeile 26 (`WORKFLOW_PY`) und der darauf laufende Test
  `test_ac3_start_type_invalid_exits_with_error` werden **gelöscht** (siehe
  unten).
- **`test_issue_603_design_fidelity_gate.py:23-26`** und
  **`test_622_fidelity_pre_actions.py:33-41`** — Drei-Konstanten-Split statt
  einer einzigen `REPO`-Konstante:
  1. Prüfling (`design_fidelity_diff.py`, `pre_issue_close_design_gate.py`) →
     worktree-relativ über `_REPO_ROOT`.
  2. Soll-Bilder (`claude-code-handoff/current/soll/`), `docs/artifacts`-Ausgabepfad
     und `cwd=`-Argument beim Subprozess-Aufruf → bleiben gemeinsam Hauptrepo, weil
     `design_fidelity_diff.py` selbst Soll-Bilder und Artefaktziel relativ zum `cwd`
     auflöst (Zeilen 292-294) und `.claude/validator.env` ebenso liest (Zeile 145).
     Soll-Bilder worktree-relativ zu prüfen hieße, die Existenz einer anderen Datei
     zu belegen als die, die anschließend verglichen wird.

### 2. `test_ac3` löschen

`test_issue_465_workflow_optimierung.py::test_ac3_start_type_invalid_exits_with_error`
ruft `workflow.py` über den toten Pfad `WORKFLOW_PY` auf. `workflow.py` existiert
seit der Plugin-Migration (Commits `33da201c`/`465380c1`/`f1e3acc1`, siehe
`docs/specs/modules/rework_1211b_rot_triage.md`) weder im Hauptrepo noch im
Worktree. Der Test assertet `returncode != 0`; der Python-Interpreter liefert
Exit 2 („can't open file"), weil die Datei fehlt — der Prüfling läuft nie, der
Test ist strukturell falsch grün. Test-Politik verlangt „sofort fixen ODER
löschen, wenn er veraltetes Verhalten prüft" — heilbar ist er nicht, weil
`workflow.py` jetzt Plugin-Code ist und laut Bestandsurteil
(`test_code_gate_allowed_dirs.py:5-11`) hier bewusst nicht mehr geprüft wird.
Gelöscht werden: die Funktion `test_ac3_start_type_invalid_exits_with_error`
und die Konstante `WORKFLOW_PY` (Zeile 26). `EMAIL_VALIDATOR_PY` und
`test_ac10_email_validator_creates_yaml_log` bleiben erhalten und werden auf
worktree-relative Auflösung umgestellt.

### 3. Begründungskommentare (Klasse B und Klasse C)

Jede Datei, die einen `/home/hem/gregor_zwanzig`-Treffer behält (Klasse B:
bewusst Hauptrepo/geteilte Ablage; Klasse C: gar kein Dateizugriff), bekommt
einen Ein-Satz-Kommentar direkt an der betroffenen Stelle, der begründet, warum
der feste Pfad dort korrekt ist bzw. warum kein Pfadzugriff vorliegt.
Betroffene Klasse-C-Dateien laut Kontextdokument:

- `test_issue_348_parallel_workspaces.py:31` (`HARDCODED_PREFIX` ist ein
  Suchmuster, kein Ladepfad — Umstellen würde den Test entwerten)
- `test_issue_1004_startzeit_ssot.py:37` (`_MAIN_REPO` ist Fallback **nach**
  `_REPO_ROOT`, Worktree gewinnt bereits)

Betroffene Klasse-B-Dateien (Auswahl, vollständige Liste im Kontextdokument):
`.env`/`validator.env`-Nutzer (`test_issue_1147_resend_recipient_invariant.py`,
`test_794_mobile_metric_label.py`, u.a.), Staging-Installation
(`test_issue_1068_tier_model_display.py`, `_telegram_live_fixture.py`), sowie
Dateien, die `REPO_DIR` als geteilte Ablage nutzen (HEAD-Ermittlung,
Attestation, `docs/artifacts`, `cwd`) — dort wo nach Schritt 1 nicht bereits ein
Kommentar aus dem Muster (`test_staging_gate.py:25-31`,
`test_bundle_h_908_973_987_staging_auth.py:46-58`) übernommen werden kann,
wird ein knapper eigener Ein-Satz-Kommentar ergänzt.

### 4. Wirkungsnachweis (Mutations-Beleg)

Neue Datei `tests/tdd/test_worktree_path_resolution_effect.py`. Ein reiner
Pfad-Assert („liegt der Pfad unter der Worktree-Wurzel?") wäre selbst wieder
Kosmetik — er hätte auch bei `WORKFLOW_PY` grün gemeldet, obwohl die Zieldatei
nirgends existiert. Belastbar ist nur der tatsächliche Mutations-Beleg:

1. Miniatur-Worktree in `tmp_path` anlegen: Kopie der Testdatei-Logik plus eine
   **echte Kopie** der zu prüfenden Hook-Datei (z.B.
   `briefing_mail_validator.py`) unter `<tmp_path>/.claude/hooks/`.
2. Lauf 1: Prüfling unverändert → erwartetes Verhalten (grün/Exit 0).
3. Hook-**Kopie** in `tmp_path` gezielt brechen (z.B. eine Zeile durch
   `raise RuntimeError(...)` ersetzen oder eine geprüfte Konstante ändern).
4. Lauf 2: derselbe Test-Aufruf muss jetzt fehlschlagen (rot).
5. Wäre der Pfad fest auf das Hauptrepo verdrahtet, bliebe Lauf 2 fälschlich
   grün, weil er die unveränderte Hauptrepo-Kopie sieht statt der gebrochenen
   `tmp_path`-Kopie — genau das ist der zu erbringende Beweis.

Umfang: **zwei Exemplare**, nicht alle fünf Stellen — ein glatter Fall (nur
Prüfling-Pfad, z.B. `briefing_mail_validator.py` analog zur Klasse-A-Stelle in
`test_issue_862_849_col_labels.py`) und ein gemischter Fall (Drei-Konstanten-
Split, z.B. `design_fidelity_diff.py` analog zu `test_issue_603`/`test_622`).
Startet pytest im pytest (Subprozess-Lauf gegen die `tmp_path`-Kopie) und
braucht daher einen eigenen `pytest.mark.timeout`-Override, wie in
`test_622_fidelity_pre_actions.py:31` vorexerziert.

## Expected Behavior

- **Input:** Eine im Arbeitsordner (Worktree) geänderte Prüfling-Datei unter
  `.claude/hooks/`.
- **Output:** Die fünf umgestellten Tests laden diese geänderte Datei und
  reagieren auf ihren tatsächlichen Zustand — nicht auf den Zustand der
  gleichnamigen Datei im Hauptrepo.
- **Side effects:** Keine Produktivcode-Änderung. `test_ac3` und `WORKFLOW_PY`
  entfallen ersatzlos aus `test_issue_465_workflow_optimierung.py`.

## Acceptance Criteria

- **AC-1:** Given eine im Arbeitsordner geänderte Kopie von `briefing_mail_validator.py` / When `test_issue_862_849_col_labels.py` läuft / Then spiegeln die Testergebnisse den geänderten Zustand dieser Kopie wider, nicht den unveränderten Zustand der Hauptrepo-Kopie
  - Test: Bestehende ACs des Files (z.B. `test_thunder_col_label_is_thdr`) laufen unverändert grün gegen die Worktree-Kopie; Wirkungsnachweis (AC-6) erbringt den Mutationsbeleg.

- **AC-2:** Given eine im Arbeitsordner geänderte Kopie von `prod_selftest.py` / When `test_prod_selftest_730.py` läuft / Then wird der Prüfling worktree-relativ geladen, während `REPO_DIR` weiterhin auf das Hauptrepo zeigt (HEAD-Ermittlung, Attestation)
  - Test: Bestehende ACs (`test_ac1`…`test_ac4`) bleiben grün; `REPO_DIR`-Nutzung für `_head_sha()` bleibt unverändert funktionsfähig.

- **AC-3:** Given eine im Arbeitsordner geänderte Kopie von `email_spec_validator.py` / When `test_issue_465_workflow_optimierung.py` läuft / Then lädt `test_ac10_email_validator_creates_yaml_log` diese Worktree-Kopie, erkennbar daran, dass eine im Worktree eingebrachte Verhaltensänderung im Testergebnis sichtbar wird
  - Test: `test_ac10_email_validator_creates_yaml_log` bleibt grün nach Umstellung; keine DeprecationWarning mehr mit Hauptrepo-Pfad im Testlauf.

- **AC-4:** Given im Arbeitsordner geänderte Kopien von `design_fidelity_diff.py` bzw. `pre_issue_close_design_gate.py` / When `test_issue_603_design_fidelity_gate.py` oder `test_622_fidelity_pre_actions.py` läuft / Then wird der Prüfling worktree-relativ geladen, während Soll-Bilder, Artefakt-Ablage (`docs/artifacts`) und `cwd`-Argument gemeinsam auf das Hauptrepo zeigen — so wird die geänderte Fassung des Prüflings ausgeführt und dabei genau die Datei geprüft, die der Vergleich auch liest
  - Test: Bestehende ACs beider Dateien bleiben grün; keine Regression bei Soll-Bild-Abgleich (Soll-Bilder bleiben Hauptrepo-relativ, weil `design_fidelity_diff.py` sie über `Path(".")` relativ zum `cwd` liest — worktree-relative Auflösung würde die Existenz einer anderen Datei prüfen als die verglichene).

- **AC-5:** Given der gelöschte `test_ac3_start_type_invalid_exits_with_error` / When die Testsuite von `test_issue_465_workflow_optimierung.py` läuft / Then existiert keine Lücke, die stillschweigend als Grün gilt — die verbleibenden Tests (`test_ac10_...`) decken weiterhin reales Verhalten ab, und `WORKFLOW_PY` taucht in keiner verbleibenden Testfunktion mehr auf
  - Test: `grep -n WORKFLOW_PY tests/tdd/test_issue_465_workflow_optimierung.py` liefert keinen Treffer; verbleibende Tests laufen unverändert grün.

- **AC-6:** Given ein in `tmp_path` künstlich gebrochener Hook (z.B. eine korrumpierte Kopie von `briefing_mail_validator.py`) / When der Wirkungsnachweis-Test läuft / Then ist Lauf 1 (unveränderter Prüfling) grün und Lauf 2 (gebrochener Prüfling) rot — bei fest auf das Hauptrepo verdrahtetem Pfad bliebe Lauf 2 fälschlich grün
  - Test: `tests/tdd/test_worktree_path_resolution_effect.py` enthält zwei Exemplare (ein glatter Fall, ein gemischter Fall mit Drei-Konstanten-Split) und erbringt den Vorher-grün/Nachher-rot-Beleg für beide.

- **AC-7:** Given die Klasse-B/C-Dateien mit unverändert bewusst festem Pfad / When die zugehörigen Testsuiten laufen / Then bleiben sie unverändert grün und tragen nach dieser Lieferung je einen Ein-Satz-Begründungskommentar an der betroffenen Stelle
  - Test: Betroffene Klasse-B/C-Dateien (u.a. `test_issue_348_parallel_workspaces.py`, `test_issue_1004_startzeit_ssot.py`) laufen unverändert grün; Kommentar ist an der Fundstelle vorhanden (Sichtprüfung, kein automatisierter Test — reine Doku-Ergänzung, `# doc-compliance-test`-Ausnahme gilt sinngemäß).

## Test Plan

Referenz je AC. Alle Läufe erfolgen über `uv run pytest <datei>` im Sitzungs-Worktree.

- **AC-1 (Mail-Validator-Stelle):**
  - Input: `tests/tdd/test_issue_862_849_col_labels.py` nach Pfadfix; unveränderte Worktree-Kopie von `briefing_mail_validator.py`.
  - Vorgehen: `uv run pytest tests/tdd/test_issue_862_849_col_labels.py -v` ausführen; anschließend prüfen, dass `_load_validator()` den Pfad über `_REPO_ROOT` (worktree-relativ) auflöst, nicht über den String `/home/hem/gregor_zwanzig/...`.
  - Erwarteter Output: Bestehende Tests (u.a. `test_thunder_col_label_is_thdr`) bleiben grün; kein harter Hauptrepo-Pfad mehr im Quelltext (`grep -n '/home/hem/gregor_zwanzig' tests/tdd/test_issue_862_849_col_labels.py` liefert keinen Treffer).

- **AC-2 (`prod_selftest.py`-Stelle):**
  - Input: `tests/tdd/test_prod_selftest_730.py` nach Pfadfix.
  - Vorgehen: `uv run pytest tests/tdd/test_prod_selftest_730.py -v -m staging` ausführen (Marker `staging`, dialt real); Quelltext-Diff prüfen, dass Zeile 30 (`PROD_SELFTEST`) worktree-relativ ist und Zeile 31 (`REPO_DIR`) unverändert bleibt.
  - Erwarteter Output: `test_ac1`…`test_ac4` bleiben grün; `_head_sha()` liefert weiterhin einen validen Commit-Hash über `REPO_DIR`.

- **AC-3 (`email_spec_validator.py`-Stelle):**
  - Input: `tests/tdd/test_issue_465_workflow_optimierung.py` nach Pfadfix und Löschung von `test_ac3`/`WORKFLOW_PY`.
  - Vorgehen: `uv run pytest tests/tdd/test_issue_465_workflow_optimierung.py -v` ausführen; Testlauf-Output auf DeprecationWarnings mit Hauptrepo-Pfad prüfen.
  - Erwarteter Output: `test_ac10_email_validator_creates_yaml_log` bleibt grün; keine Warnung mit `/home/hem/gregor_zwanzig/.claude/hooks/email_spec_validator.py` im Log.

- **AC-4 (Design-Fidelity-Stellen, Drei-Konstanten-Split):**
  - Input: `tests/tdd/test_issue_603_design_fidelity_gate.py` und `tests/tdd/test_622_fidelity_pre_actions.py` nach Pfadfix.
  - Vorgehen: `uv run pytest tests/tdd/test_issue_603_design_fidelity_gate.py tests/tdd/test_622_fidelity_pre_actions.py -v` ausführen (Timeout-Override `180s` bleibt aktiv); Quelltext-Diff prüfen, dass der Prüfling über `_REPO_ROOT` läuft, während Soll-Bilder, Artefakt-Ablage und `cwd` gemeinsam über die Hauptrepo-Konstante `MAIN_REPO` laufen (der Bildvergleich löst seine Datenpfade über `Path(".")` relativ zum `cwd` auf).
  - Erwarteter Output: Beide Dateien laufen unverändert grün gegenüber dem Stand vor dieser Lieferung; kein neuer Fehlschlag beim Soll-Bild-Abgleich.

- **AC-5 (`test_ac3`-Löschung ohne Grün-Lücke):**
  - Input: `tests/tdd/test_issue_465_workflow_optimierung.py` nach Löschung.
  - Vorgehen: `grep -n WORKFLOW_PY tests/tdd/test_issue_465_workflow_optimierung.py` ausführen (erwartet: kein Treffer); danach vollen Testlauf der Datei ausführen und Testanzahl vorher/nachher vergleichen (minus genau ein Test).
  - Erwarteter Output: Kein `WORKFLOW_PY`-Treffer mehr; verbleibender Test (`test_ac10_...`) grün; Testanzahl um exakt 1 reduziert, keine sonstige Veränderung der Collection.

- **AC-6 (Wirkungsnachweis/Mutations-Beleg):**
  - Input: `tests/tdd/test_worktree_path_resolution_effect.py` (neu), zwei Exemplare (glatter Fall `briefing_mail_validator.py`, gemischter Fall `design_fidelity_diff.py`).
  - Vorgehen: `uv run pytest tests/tdd/test_worktree_path_resolution_effect.py -v` ausführen. Je Exemplar: Lauf 1 gegen unveränderte `tmp_path`-Hook-Kopie, Lauf 2 gegen gezielt gebrochene Kopie derselben Datei.
  - Erwarteter Output: Lauf 1 grün, Lauf 2 rot, für beide Exemplare. Schlägt Lauf 2 fälschlich grün fehl (weil der Test heimlich die Hauptrepo-Kopie lädt), gilt der Nachweis als nicht erbracht.

- **AC-7 (Klasse-B/C-Begründungskommentare, keine Regression):**
  - Input: Klasse-B/C-Dateien mit unverändert festem Pfad, u.a. `test_issue_348_parallel_workspaces.py`, `test_issue_1004_startzeit_ssot.py`.
  - Vorgehen: `uv run pytest tests/tdd/test_issue_348_parallel_workspaces.py tests/tdd/test_issue_1004_startzeit_ssot.py -v` ausführen; anschließend Sichtprüfung, dass an jeder betroffenen Fundstelle ein Ein-Satz-Begründungskommentar steht.
  - Erwarteter Output: Beide Tests laufen unverändert grün (keine Verhaltensänderung); Kommentar ist an der jeweiligen Zeile vorhanden und benennt den Grund (Suchmuster bzw. Fallback-Reihenfolge).

## Known Limitations

- Der Wächter (Allowlist-Ratchet gegen neue unbegründete Hauptrepo-Pfad-Treffer)
  ist explizit **nicht** Teil dieser Lieferung — folgt als Lieferung B in einem
  eigenen Workflow, sobald diese Klassifikation als Allowlist-Grundlage
  vorliegt.
- `prod_selftest.py`s internes `REPO_DIR = Path("/home/hem/gregor_zwanzig")`
  (Zeile 56) bleibt unangetastet — bewusste Produktentscheidung (geteilte
  Attestation, Prod wird nur vom Hauptrepo deployt), kein Testfix kann das
  umgehen.
- Klasse-B/C-Dateien außerhalb der fünf Klasse-A-Stellen werden **nicht**
  umgestellt, nur kommentiert — Umstellung würde bei Klasse C (Suchmuster,
  Fallback-Reihenfolge) die geprüfte Aussage entwerten.

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** keine
- **Rationale:** Reine Testinfrastruktur-Korrektur ohne Auswirkung auf
  Produktarchitektur, Datenmodell, Kanäle oder Provider — kein
  Entscheidungsfläche im Sinne der ADR-Kriterien.

## Changelog

- 2026-07-28: Initial spec erstellt — Issue #1409, Lieferung A
