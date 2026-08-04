---
entity_id: fix_1307a_hook_fail_open
type: module
created: 2026-08-04
updated: 2026-08-04
status: draft
version: "1.0"
tags: [hooks, gates, tooling, issue-1307, issue-384]
---

# Fix #1307 Scheibe A — Fail-open-Absicherung aller Hook-Einträge

## Approval

- [ ] Approved

## Purpose

Jeder in `.claude/settings.json` registrierte Hook wird als
`python3 "${CLAUDE_PROJECT_DIR}/.claude/hooks/<name>.py"` verdrahtet. Fehlt die Datei
dort, bricht der Aufruf mit „can't open file" ab — und **jeder** Werkzeug-Aufruf in
**jeder** Sitzung ist blockiert. Diese Scheibe bringt die acht noch ungeschützten
Einträge auf die abgesicherte Form und entfernt gleichzeitig die Ausnahme im Test,
die verhindert hat, dass die Regel beißt.

## Source

- **File:** `.claude/settings.json` (Hook-Verdrahtung)
- **File:** `tests/tdd/test_issue_384_hook_fail_open.py` (Wächter)
- **Identifier:** `_build_params(mark_unguarded_xfail=…)`, `_is_fail_open_guarded`

## Gemessener Ausgangsstand (2026-08-04, Stand `5d034b79`)

| | Einträge |
|---|---|
| **ungeschützt (8)** | `renderer_mail_gate` · `prod_send_gate` · `nebenbefund_gate` · `broad_test_run_gate` · `touched_tests_gate` · `test_naming_gate` · `track_token_usage` · `terminology_gate` |
| bereits geschützt (3) | `pendant_gate` · `notify_sound` · `auto_restart_server` |

16 Testfälle (8 Einträge × 2 Prüfungen) stehen als „bekannt offen" (`xfail`) und sind
deshalb grün. Bei Aufnahme des Befundes waren es 5 Einträge — der Bestand ist auf 8
gewachsen, weil nichts ihn stoppt.

**Belegter Schaden:** 2026-08-04 während #1481 B — eine Stunde Totalblockade in allen
Sitzungen, weil `touched_tests_gate.py` im Hauptordner (8 Commits zurück) noch nicht
existierte.

## Estimated Scope

- **LoC:** ~25 (8 Zeilen `settings.json` + Rückbau der xfail-Mechanik)
- **Files:** 2
- **Effort:** low

## Acceptance Criteria

**AC-1:** Given `.claude/settings.json` mit den acht bisher ungeschützten Hook-Einträgen,
When die Datei nach dieser Änderung gelesen wird,
Then trägt **jeder** Eintrag, der `${CLAUDE_PROJECT_DIR}` verwendet, exakt die Form
`if [ -f "<pfad>" ]; then python3 "<pfad>"; fi`.

**AC-2:** Given ein Hook-Eintrag in der abgesicherten Form,
When der Aufruf läuft, während die Hook-Datei am Zielort **fehlt**,
Then endet er mit Rückgabewert 0 (Werkzeug erlaubt) — es entsteht keine Blockade.

**AC-3:** Given ein Hook-Eintrag in der abgesicherten Form,
When die Hook-Datei vorhanden ist und mit Rückgabewert 2 blockieren will,
Then kommt Rückgabewert 2 unverändert an — die Absicherung weicht echte Blockaden
**nicht** auf. (Deshalb `if … then … fi` und ausdrücklich **nicht** `&&` oder `||`:
diese verschlucken die 2.)

**AC-4:** Given `tests/tdd/test_issue_384_hook_fail_open.py`,
When ein Testlauf über diese Datei ausgeführt wird,
Then existiert **kein** `xfail`-Mechanismus mehr für ungeschützte Einträge — alle
Parameter laufen als normale Testfälle, und kein Fall steht auf „bekannt offen".

**AC-5:** Given ein neuer, ungeschützt eingetragener Hook in `.claude/settings.json`,
When der Test aus AC-4 läuft,
Then wird er **rot** und benennt den betroffenen Eintrag — die Regel beißt ab sofort,
statt nur dazustehen.

**AC-6:** Given `.claude/settings.json` nach der Änderung,
When sie als JSON eingelesen wird,
Then ist sie gültiges JSON und die Reihenfolge sowie die Zuordnung der Hooks zu ihren
Ereignissen (`PreToolUse`, `Stop`, …) ist unverändert.

## Was sich NICHT ändern darf

- Der externe Eintrag `bash /home/hem/claude-mq/check-messages.sh` (absoluter Pfad, kein
  `${CLAUDE_PROJECT_DIR}`) bleibt unangetastet — er ist nicht Teil des Befundes.
- Kein Wächter wird inhaltlich abgeschwächt: Alle Prüfungen laufen unverändert, sobald
  die Datei vorhanden ist.
- Die drei bereits geschützten Einträge bleiben, wie sie sind.

## Bewusst NICHT in dieser Scheibe

- **Die Kehrseite:** Die Absicherung sorgt dafür, dass ein fehlender Wächter
  **stillschweigend nicht läuft** — keine Blockade, aber auch keine Prüfung. Sie
  verwandelt eine laute Störung in eine stille Lücke. Der zweite Teil der Antwort wäre,
  den Hauptordner automatisch aktuell zu halten; das ist eine eigene Scheibe und hier
  nicht enthalten.
- Befunde 2–5 aus #1307 (Design-Wächter, `staging_gate`, Mail-Prüfer) — eigene Scheibe B.
- Die Wächter aus dem Werkzeug-Paket `agent-os-openspec` (#1478) — anderes Repo.

## Test Plan

| Test | Prüft |
|---|---|
| `test_settings_json_is_valid_json` | AC-6 |
| `test_every_hook_is_fail_open_guarded` (11 Fälle) | AC-1, AC-5 |
| `test_missing_hook_file_allows_tool` (11 Fälle) | AC-2 |
| `test_present_blocking_hook_still_blocks` (11 Fälle) | AC-3 |
| `test_present_ok_hook_allows` (11 Fälle) | Unverändertes Verhalten |

Erwartung nach dem Fix: **45 bestanden, 0 „bekannt offen"** (vorher: 29 bestanden,
16 bekannt offen).

**Mutations-Gegenprobe (Pflicht):** Einen der acht Einträge testweise auf `&&` statt
`if … fi` umschreiben — `test_present_blocking_hook_still_blocks` MUSS rot werden.
Wird er es nicht, bewacht der Test die Zusicherung aus AC-3 nicht.

## Dependencies

- Issue #384 (ursprüngliche Anforderung), Issue #1307 Befund 1, Issue #1504 (Dublette,
  geschlossen)
- Vorbild für die korrekte Form: `pendant_gate.py`-Eintrag aus #1481 B
