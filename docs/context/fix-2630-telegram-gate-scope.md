# Context: fix-2630-telegram-gate-scope

## Request Summary
Das Telegram-Live-Gate im Staging-Verdict (`staging_gate.py --write-verdict`) schlägt bei jeder Änderung an einer Datei an, deren Name „telegram" enthält — auch bei reiner Dateimodus-Änderung (`internal/handler/telegram_connect.go`, +5 Zeilen `fsmode`, #2624). Das Gate soll nur bei Änderungen an Telegram-**Verhalten** auslösen. Zweiter Befund: Teardown-Error nach `test_heute_ohne_namen_bei_trip_und_vergleich_fragt_live_zurueck`, Ursache offen.

## Related Files
| File | Relevance |
|------|-----------|
| `.claude/hooks/e2e_telegram_live.py:47-74` | `_scope_touches_telegram(changed_files)` — Namens-Substring-Heuristik (`telegram`, `inbound_telegram`, `trip_command_processor`); bekommt NUR Dateinamen, keinen Diff-Inhalt |
| `.claude/hooks/e2e_telegram_live.py:77-87` | `_is_neutral_path` — Doku/Tooling/Tests neutral (#728) |
| `.claude/hooks/e2e_telegram_live.py:14-44` | `gate()` — prüft nur, ob `GZ_TELEGRAM_TEST_CHAT_ID` gesetzt ist (führt den Live-Test selbst NICHT aus) |
| `.claude/hooks/staging_gate.py:229-263` | `_telegram_live_gate()` — Diff `HEAD~1..HEAD` über `_e2e_paths._git_diff_names`; `None` (Diff-Fehler) ⇒ konservativ blockend (#1121) |
| `.claude/hooks/_e2e_paths.py:172` | `_git_diff_names` — liefert nur Namen |
| `tests/tdd/test_issue_728_telegram_scope_neutral.py` | echte temporäre git-Repos, Vorbild für neue Tests |
| `tests/tdd/test_issue_686_telegram_functional_live.py:510-570` | der Live-Test mit dem Teardown-Error (`GZ_TELEGRAM_LIVE=1`) |
| `tests/tdd/test_issue_1121_git_diff_returncode.py` | sichert fail-closed bei Diff-Fehler |

Auslöser: Commit `04b8e0472` — `telegram_connect.go` bekam nur `import fsmode` + `os.Chmod(tmpName, fsmode.FileMode)`.

## Existing Patterns
- #728: Neutral-Pfade vor der Namensprüfung herausfiltern, Test mit echtem git-Repo.
- #1121: Unklarer Diff ⇒ fail-closed (als Telegram-relevant behandeln). Muss erhalten bleiben.

## Dependencies
- Upstream: `git diff`, `_e2e_paths`.
- Downstream: `staging_gate.write_verdict` (Hard Gate für Prod-Deploy), `tests/tdd/test_attestation_findings_typsicher.py` referenziert das Modul.

## Existing Specs
- Archiv: `docs/specs/_archive/modules/issue_686_telegram_functional_live_tests.md`, `issue_728_telegram_scope_neutral_paths.md`.

## Befunde zum zweiten Punkt (Teardown-Error)
Der Test ruft im `finally` `antwort_im_update(...)` und `delete_message(...)` für jede gesendete Nachricht. Ein Fehler dort (z. B. Telegram-Rate-Limit, bereits gelöschte Nachricht, `sent_message_ids` leer) würde als Fehler beim Aufräumen sichtbar. Ursache nicht reproduziert — braucht einen Live-Lauf (`GZ_TELEGRAM_LIVE=1`). Nicht Teil des Gate-Fixes; in der Analyse einschätzen, ggf. #1199.

## Risks & Considerations
- Das Gate ist ein Hard Gate: zu lasche Erkennung lässt echte Telegram-Änderungen ohne Test-Chat durch. Daher nur eng definierte „reine Modus-Änderung" als neutral (jede geänderte Zeile der Datei bezieht sich auf `fsmode`/`os.Chmod`/Import), alles andere bleibt Telegram-Scope.
- Mehrere Dateien im Diff: neutral nur, wenn JEDE Telegram-namige Datei rein modusbedingt geändert ist.
- Diff-Inhalt statt Namen heißt ein zweiter git-Aufruf; Fehler dort ⇒ fail-closed.
- Hooks-Code: Mutationsprobe Pflicht, Adversary mind. 2 Runden.

## Analysis

### Type
Bug (Gate-Fehlalarm im Staging-Verdict; Hooks-Tooling, kein Produktcode)

### Root Cause
`_scope_touches_telegram` (`.claude/hooks/e2e_telegram_live.py:47-74`) entscheidet allein am Dateinamen (Substring `telegram`). Der Aufrufer `staging_gate._telegram_live_gate` (`staging_gate.py:251-253`) übergibt nur Namen aus `_git_diff_names`. Eine reine Modus-Änderung (`import fsmode` + `os.Chmod(..., fsmode.FileMode)`) in `telegram_connect.go` ist daher nicht von einer Verhaltensänderung unterscheidbar.

### Affected Files (with changes)
| File | Change Type | Description |
|------|-------------|-------------|
| `.claude/hooks/e2e_telegram_live.py` | MODIFY | Neue Prüfung „reine Modus-Änderung": Telegram-namige Datei gilt als neutral, wenn JEDE geänderte Zeile `fsmode`/`os.Chmod`/Import betrifft |
| `.claude/hooks/staging_gate.py` | MODIFY | `_telegram_live_gate` liefert Diff-Inhalt (zweiter git-Aufruf, Fehler ⇒ fail-closed) |
| `.claude/hooks/_e2e_paths.py` | MODIFY (ggf.) | Helfer für Zeilen-Diff einer Datei neben `_git_diff_names` |
| `tests/tdd/test_telegram_gate_modus_aenderung.py` | CREATE | Echte temporäre git-Repos (Vorbild #728): nur Modus ⇒ kein Block; Modus + Logik ⇒ Block; Diff-Fehler ⇒ Block; mehrere Dateien |
| `docs/specs/modules/...` | CREATE | Spec mit ACs |

### Scope Assessment
- Files: 3 Hooks + 1 Test + 1 Spec
- Estimated LoC: +70/-5 produktiv, +90 Test
- Risk Level: MEDIUM — Hard Gate für Prod-Deploy; zu lasche Erkennung ließe echte Telegram-Änderungen ohne Live-Test durch

### Technical Approach
Neutralität nur, wenn der Diff der Datei ausschließlich aus einer eng definierten Whitelist besteht (Import `internal/fsmode`, `fsmode.*`, `os.Chmod`/Modus-Argument, Leerzeilen/Klammern). Jede andere geänderte Zeile ⇒ weiterhin Telegram-Scope. Mehrere Dateien: neutral nur, wenn alle Telegram-namigen Dateien rein modusbedingt sind. Diff-Inhalt nicht lesbar ⇒ fail-closed (#1121 bleibt). Alternative „Ausnahme per Spec-Feld" verworfen: Selbstfreigabe durch den Autor, schwächer als maschinelle Prüfung.

### Dependencies
Upstream: `git diff`, `_e2e_paths`. Downstream: `staging_gate.write_verdict`; `test_issue_728_*` und `test_issue_1121_*` müssen grün bleiben; `test_attestation_findings_typsicher.py` referenziert das Modul.

### Zweiter Befund (Teardown-Error)
Ursache nicht reproduziert (braucht `GZ_TELEGRAM_LIVE=1`-Lauf). Vermutlich Aufräumfehler im `finally` (`delete_message`/`antwort_im_update`, z. B. Rate-Limit oder bereits gelöschte Nachricht). Nicht Teil des Gate-Fixes; als Checkbox in #1199 (Test-Befund, nicht nutzersichtbar).

### Open Questions
- [ ] Keine für den PO. Whitelist-Muster werden in der Spec konkret festgelegt.
