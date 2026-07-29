# Context: fix-1409-worktree-pfade

Issue: [#1409](https://github.com/henemm/gregor_zwanzig/issues/1409) — „Tests verdrahten den Hauptrepo-Pfad fest — aus Worktrees melden sie falsches Gruen"
Erhoben: 2026-07-28, Worktree `session-arbeitsordner` auf `07fe4641`

## Request Summary

Mehrere Tests laden ihren Prüfling über den festen Pfad `/home/hem/gregor_zwanzig/...` statt relativ zum eigenen Checkout. Aus einem Worktree prüfen sie damit die **unveränderte** Hauptrepo-Kopie und melden falsches Grün. Umzustellen ist nur die Teilmenge, bei der die geprüfte Datei im Repo liegt; Umgebungs-/Betriebsdateien bleiben absichtlich fest verdrahtet und werden je Datei begründet.

## Gemessener Bestand (2026-07-28, `grep -rn '/home/hem/gregor_zwanzig' tests/`)

**31 Dateien** mit Treffern (Ticket schätzt „13+"). Die Treffer zerfallen in **drei** Klassen, nicht zwei — die dritte fehlt im Ticket und ist der Grund, warum ein pauschales Ersetzen doppelt falsch wäre.

### Klasse A — echter Bug: Prüfling liegt im Repo, existiert im Worktree

| Datei | Zeile | Verdrahtet | Bemerkung |
|---|---|---|---|
| `tests/tdd/test_issue_862_849_col_labels.py` | 22 | `.claude/hooks/briefing_mail_validator.py` | Am kritischsten: der Mail-Validator ist selbst Gate-Werkzeug |
| `tests/tdd/test_issue_603_design_fidelity_gate.py` | 24, 25 | `design_fidelity_diff.py`, `pre_issue_close_design_gate.py` | REPO wird zusätzlich für `docs/artifacts` + `cwd` genutzt (→ Klasse B, gemischte Datei) |
| `tests/tdd/test_622_fidelity_pre_actions.py` | 34 | `design_fidelity_diff.py` | dito gemischt |
| `tests/tdd/test_prod_selftest_730.py` | 30 | `prod_selftest.py` | Zeile 31 (`REPO_DIR`) ist dagegen Klasse B |
| `tests/tdd/test_issue_465_workflow_optimierung.py` | 27 | `email_spec_validator.py` | Zeile 26 (`workflow.py`) zeigt auf eine Datei, die es **nirgends mehr gibt** (Plugin-Migration) — eigener Befund, siehe Risiken |

Alle `.claude/hooks/*.py` sind git-tracked und liegen damit in jedem Worktree vor — die Umstellung ist hier ohne Nebenwirkung möglich.

### Klasse B — bewusst Hauptrepo, unangetastet lassen + je Datei begründen

| Zweck | Dateien |
|---|---|
| Produktiv-/Staging-`.env` (existiert je Host einmal) | `test_issue_1147_resend_recipient_invariant.py:54`, `test_issue_1007_heute_voll_briefing.py:46`, `test_issue_1113_partial_outage_guard.py:64`, `test_issue_1009_1019_inbound_robustness.py:73`, `test_issue_1012_no_data_guard.py:54`, `test_issue_1049_staging_inbox_isolation.py:18,19` (prüft gerade die Trennung beider) |
| `.claude/validator.env` (Zugangsdaten, gitignored) | `test_794_mobile_metric_label.py:34`, `test_issue_1010_1006_stille_fehler.py:37`, `tests/helpers/staging_auth.py:11` |
| Staging-Installation / Staging-Daten | `test_issue_1068_tier_model_display.py:48`, `_telegram_live_fixture.py:24,100`, `test_issue_1014_live_optin.py:124` |
| `REPO_DIR` als **geteilte Ablage**: HEAD-Ermittlung, Attestation, Report-/Artefakt-Pfad, `cwd` | `test_staging_gate.py:36`, `test_prod_selftest_564.py:43`, `test_prod_selftest_730.py:31`, `test_bundle_h_908_973_987_staging_auth.py:43`, `test_issue_603_*`, `test_622_*` |
| Deploy-Artefakt (gitignored Binary) | `test_issue_1148_prod_send_gate.py:291` (steht zudem nur in einem Beispiel-Kommandostring) |

### Klasse C — gar kein Dateizugriff, nichts zu tun (im Ticket nicht vorgesehen)

| Datei | Warum kein Bug |
|---|---|
| `test_issue_348_parallel_workspaces.py:31` | `HARDCODED_PREFIX` ist ein **Suchmuster**: der Test assertet, dass dieser String **nicht** in `settings.json` steht. Umstellen würde den Test entwerten. Ticket führt ihn fälschlich unter Gruppe A. |
| `test_issue_1004_startzeit_ssot.py:37` | `_MAIN_REPO` ist **Fallback nach** `_REPO_ROOT` (Zeile 43: `for root in (_REPO_ROOT, _MAIN_REPO)`) — Worktree gewinnt bereits. Ticket führt ihn fälschlich unter Gruppe A. |
| `test_issue_784_*`, `test_deploy_gate_evidence_resolution.py`, `test_briefing_log.py`, `test_alert_log.py`, `test_bug717_*`, `test_bug720_*`, `test_prod_testdata_cleanup.py`, `test_issue_1001_telegram_bubbles.py` | Nur Docstring/Kommentar |

### Bereits repariert (Vorbild im Bestand)

`test_staging_gate.py:32-36` und `test_prod_selftest_564.py:40-45` lösen den **Prüfling** repo-relativ auf und behalten `REPO_DIR` bewusst — mit ausführlicher Begründung im Kommentar. `test_bundle_h_908_973_987_staging_auth.py:45-62` ebenso. Das ist genau die Zielform; Ticket zitiert die Zeile 56 dort als Negativbeispiel, tatsächlich begründet der Kommentar das Gegenteil.

## Existing Patterns

- **Kanonische Auflösung:** `REPO_ROOT = Path(__file__).resolve().parents[2]`, `HOOKS_DIR = REPO_ROOT / ".claude" / "hooks"` — `test_issue_784_staging_gate_worktree_head.py:37-40`, `test_deploy_gate_evidence_resolution.py:19-24` (dort auch als Regel ausformuliert), `test_code_gate_allowed_dirs.py:24`, `test_issue_1061_gate_tests_stale.py:16`.
- **Prüfling laden:** `importlib.util.spec_from_file_location(...)` gegen die Worktree-Kopie (784, 564, bundle_h) statt Subprozess mit Hauptrepo-Pfad.
- **Repo-Wächter als pytest-Datei** (nicht als Hook), wenn nur eine Repo-Garantie geprüft wird: `test_code_gate_allowed_dirs.py`. Hook-Wächter existieren daneben: `.claude/hooks/test_naming_gate.py`.

## Dependencies

- **Upstream:** `.claude/hooks/*` (git-tracked, in jedem Worktree vorhanden), `.claude/validator.env` + `.env` (gitignored, Host-Ebene), `openspec.yaml`.
- **Downstream:** Kein Produktivcode. Betroffen sind ausschließlich Test- und Gate-Absicherungen — der Nutzen ist Vertrauen in genau die Tests, die Deploy- und Mail-Gates absichern.

## Existing Specs

- `docs/specs/modules/fix_1382_deploy_gate_evidence.md` — dieselbe Fehlerfamilie (Schreibweg ≠ Leseweg), Formulierung der repo-relativen Regel
- `docs/specs/modules/issue_784_staging_gate_worktree_head.md` — Worktree-HEAD vs. Hauptrepo-HEAD
- `docs/specs/modules/rework_1211b_rot_triage.md` — Hintergrund zur Plugin-Migration von `workflow.py`

## Risks & Considerations

1. **`.claude/validator.env` existiert entgegen der Ticket-Annahme AUCH im Worktree** (dort vom 2026-07-26, Hauptrepo vom 2026-07-05). Die Gruppe-B-Begründung „existiert im Worktree gar nicht" trägt hier nicht; sie muss lauten „Zugangsdaten sollen aus einer Quelle kommen". Gleiches gilt für `data/` und `claude-code-handoff/`.
2. **Doppelrolle in einer Datei:** `test_issue_603`/`test_622` nutzen dieselbe Konstante `REPO` für Prüfling **und** Artefakt-Ablage/`cwd`. Umstellung braucht dort zwei getrennte Konstanten, kein Ersetzen.
3. **`prod_selftest.py` verdrahtet intern selbst `REPO_DIR`** auf das Hauptrepo (geteilte Attestation, Prod wird nur von dort deployt). Ein Test kann das nicht durch Pfadwahl umgehen — die Testkonstante bleibt bewusst.
4. **Toter Pfad `workflow.py`** in `test_issue_465:26`: der Prüfling existiert weder im Hauptrepo noch im Worktree. `test_ac3` läuft darüber. Zu klären: schlägt der Test fehl, oder schluckt er es? Falls Letzteres, ist das dieselbe Fehlerart auf zweiter Ebene.
5. **Wirkungsnachweis (Ticket-Punkt 3)** braucht eine Form, die nicht selbst wieder Kosmetik ist: „im Worktree kaputt gemacht ⇒ Test wird rot" muss real ausgeführt werden, nicht behauptet.
6. **Wächter (Ticket-Punkt 4)** unterliegt dem Regel-Budget: entweder eine bestehende Regel ersetzen oder Prüfdatum +90 Tage. Er muss Klasse B **und** Klasse C durchlassen — ein reiner String-Grep würde `test_issue_348` sofort falsch blockieren. Abgleich mit #1405 (Wächter 2 von 5, läuft parallel) nötig, damit kein zweiter Wächter dieselbe Fläche bewacht.
7. **Parallele Sitzungen:** aktiv sind u.a. #1410 und weitere gesperrte Worktrees. Kein laufender Workflow zu #1409 — geprüft in `.claude/workflows/`.

---

## Analysis

### Type

Bug (Test-Infrastruktur). Kein Produktivcode betroffen; der Schaden ist verlorenes Vertrauen in genau die Tests, die Deploy- und Mail-Gates absichern.

### Empirisch geklärte Fragen aus Phase 1

| Frage | Antwort |
|---|---|
| Schluckt `test_issue_465::test_ac3` den toten Pfad? | **Ja — falsch grün.** Er assertet `returncode != 0`; der Interpreter liefert Exit 2 („can't open file"), weil `workflow.py` seit der Plugin-Migration nirgends mehr existiert. Der Prüfling läuft nie. |
| Lädt `test_ac10` wirklich aus dem Hauptrepo? | **Ja** — durch die DeprecationWarning-Pfadangabe `/home/hem/gregor_zwanzig/.claude/hooks/email_spec_validator.py` im Testlauf belegt. |
| Existiert `.claude/validator.env` / `.env` nur einmal? | **Nein** — beide liegen auch im Worktree, inhaltsgleich. Die Klasse-B-Begründung muss lauten „die **produktive** Konfiguration soll geprüft werden, nicht eine Kopie davon". |
| Tragen die Klasse-A-Prüflinge selbst harte Hauptrepo-Pfade (wie `prod_selftest.py:56`)? | **Nein** bei `design_fidelity_diff.py` und `pre_issue_close_design_gate.py` (letzterer liest sogar `CLAUDE_PROJECT_DIR`). Die Umstellung verpufft dort also nicht. **Aber:** `design_fidelity_diff.py:292-294` löst Soll-Bilder und Artefaktziel über `Path(".")` relativ zum `cwd` auf — welcher Code läuft, entscheidet die Prüfling-Konstante; welche Daten er liest, weiterhin `cwd`. |

### Affected Files

| Datei | Änderung | Beschreibung |
|---|---|---|
| `tests/tdd/test_issue_862_849_col_labels.py:22` | MODIFY | Mail-Validator worktree-relativ laden (kritischste Stelle) |
| `tests/tdd/test_prod_selftest_730.py:30` | MODIFY | Prüfling worktree-relativ; `REPO_DIR` (Z. 31) bleibt bewusst Hauptrepo |
| `tests/tdd/test_issue_465_workflow_optimierung.py:26-27` | MODIFY | `EMAIL_VALIDATOR_PY` umstellen; `test_ac3` + `WORKFLOW_PY` **löschen** (Begründung unten) |
| `tests/tdd/test_issue_603_design_fidelity_gate.py:23-26` | MODIFY | Drei-Konstanten-Split: Prüfling+Soll-Bilder worktree-relativ, `docs/artifacts`+`cwd` Hauptrepo |
| `tests/tdd/test_622_fidelity_pre_actions.py:33-41` | MODIFY | dito |
| `tests/tdd/test_worktree_path_resolution_effect.py` | CREATE | Wirkungsnachweis (Mutations-Beleg) |
| `tests/tdd/test_repo_path_hardcoding_ratchet.py` | CREATE | Wächter mit Allowlist + Prüfdatum |

### Technical Approach

**1. Pfadfix.** Muster ist dreifach vorexerziert (`test_staging_gate.py:32-36`, `test_prod_selftest_564.py:40-45`, `test_bundle_h_908_973_987_staging_auth.py:45-62`) und wird 1:1 übernommen: `_REPO_ROOT = Path(__file__).resolve().parents[2]` für den **Prüfling**, `REPO_DIR = Path("/home/hem/gregor_zwanzig")` unverändert für **geteilte Ablage** (HEAD, Attestation, `docs/artifacts`, `cwd`). Bei den gemischten Dateien werden daraus drei Konstanten statt einer. Soll-Bilder (`claude-code-handoff/current/soll`) sind git-getrackt und gehören zum Prüfling-Teil.

**2. Wirkungsnachweis.** Ein Meta-Test, der nur prüft „der Pfad liegt unter der Worktree-Wurzel", wäre selbst wieder Kosmetik — er hätte auch bei `WORKFLOW_PY` grün gemeldet, obwohl die Datei nirgends existiert. Belastbar ist nur der Mutations-Beleg: Miniatur-Worktree in `tmp_path` (Testkopie + echte Hook-Kopie), Lauf 1 grün → Hook-**Kopie** gezielt brechen → Lauf 2 muss rot werden. Bei fest verdrahtetem Hauptrepo-Pfad bliebe Lauf 2 fälschlich grün — genau das ist der Beweis. Umfang: zwei Exemplare (ein glatter Fall, ein gemischter), nicht alle fünf.

**3. Wächter.** Als pytest-Datei, nicht als Hook: ein Hook sieht nur die eine gerade bearbeitete Datei und müsste raten, ob ein neuer Treffer Klasse A, B oder C ist — mit hohem Fehlklassifikationsrisiko genau bei `test_issue_348` (Suchmuster) und `test_issue_1004` (Fallback). Form: Allowlist-Ratchet über `tests/**/*.py` mit den heute bekannten Klasse-B/C-Fundstellen; jeder neue Treffer außerhalb der Allowlist wird rot und erzwingt eine bewusste Entscheidung. Vorbild `tests/tdd/test_code_gate_allowed_dirs.py`. Regel-Budget: ersetzt keine bestehende Regel → **Prüfdatum 2026-10-26** (+90 Tage), Vorbild `test_naming_gate.py`. Keine Überschneidung mit #1402/#1405 — jene Serie bewacht Laufzeitverhalten der Anwendung (stilles Verschlucken), nicht Test-Infrastruktur.

### Abweichung von der Strategie-Empfehlung

Die Bewertung empfiehlt, `test_ac3` (toter Pfad, falsch grün) unangetastet zu lassen und nach #1211b zu schieben. **Dem wird widersprochen:** ein wissentlich falsch grüner Test ist genau die Fehlerart dieses Tickets, hier gefunden, und die Test-Politik verlangt „sofort fixen ODER löschen, wenn er veraltetes Verhalten prüft". Heilbar ist er nicht — `workflow.py` lebt im Plugin, und Plugin-Code wird laut Bestandsurteil (`test_code_gate_allowed_dirs.py:5-11`) hier bewusst nicht mehr geprüft. Also: `test_ac3` samt `WORKFLOW_PY` löschen (~12 Zeilen weniger).

### Scope Assessment

- Dateien: 5 MODIFY, 2 CREATE
- Geschätzte LoC: Pfadfix ~70 (inkl. Begründungskommentare, minus ~12 gelöschte), Wirkungsnachweis ~110, Wächter ~70 → **~250, am Limit**
- Risiko: **niedrig** — reine Testdateien, kein Produktivcode, Muster im Bestand vorexerziert. Einziges echtes Risiko: der Wirkungsnachweis startet pytest im pytest (Laufzeit) und braucht einen eigenen Timeout-Override wie `test_622` (`pytest.mark.timeout(180)`).

### Nicht Teil dieses Workflows

- `prod_selftest.py`s internes `REPO_DIR` — bewusste Produktentscheidung (geteilte Attestation)
- Klasse B (`.env`, `validator.env`, Staging-Installation, Deploy-Binary) — nur Begründungskommentare, keine Umstellung
- Klasse C (`test_issue_348`, `test_issue_1004`) — kein Bug; Umstellung würde sie entwerten
- #1405 und dessen Wächter 3–5 — andere Fehlerart

### Schnitt (PO-Entscheidung 2026-07-28)

**Zwei Lieferungen**, kein LoC-Override:

| Lieferung | Inhalt | Umfang |
|---|---|---|
| **A — dieser Workflow** | Pfadfix der 5 Klasse-A-Stellen · `test_ac3` löschen · Begründungskommentare für Klasse B/C · Wirkungsnachweis (Mutations-Beleg, 2 Exemplare) | ~180 LoC |
| **B — Folge-Workflow** | Wächter (Allowlist-Ratchet, Prüfdatum 2026-10-26) | ~70 LoC |

Begründung der Reihenfolge: Lieferung A trägt den Nutzen allein (echtes Grün statt falschem Grün) und ist unabhängig auslieferbar; der Wächter braucht die in A festgeschriebene Klassifikation als Allowlist-Grundlage. #1409 bleibt bis Abschluss von B offen.

### Open Questions

Keine offen.

