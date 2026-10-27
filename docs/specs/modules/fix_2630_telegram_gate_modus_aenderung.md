---
entity_id: fix_2630_telegram_gate_modus_aenderung
type: module
created: 2026-10-27
updated: 2026-10-27
status: draft
version: "1.0"
tags: [gate, staging, telegram, hooks, tooling]
---

# Telegram-Live-Gate: reine Dateimodus-Änderung ist kein Telegram-Verhalten

## Approval

- [ ] Approved

## Purpose

Das Telegram-Live-Gate im Staging-Verdict (`staging_gate.py --write-verdict`) soll nur dann den Test-Chat verlangen, wenn sich Telegram-**Verhalten** ändert. Heute löst es allein am Dateinamen aus (`telegram` im Pfad) — auch bei #2624, wo `internal/handler/telegram_connect.go` nur einen Import `fsmode` und einen `os.Chmod(…, fsmode.FileMode)`-Aufruf bekam. Issue #2630.

## Source

- **File:** `.claude/hooks/e2e_telegram_live.py` (`_scope_touches_telegram`), `.claude/hooks/staging_gate.py` (`_telegram_live_gate`), `.claude/hooks/_e2e_paths.py` (neuer Helfer `_git_diff_lines`)
- **Identifier:** `_scope_touches_telegram`, `_telegram_live_gate`, `_git_diff_lines`

> Schicht: reines Hooks-/Tooling-Werkzeug (`.claude/hooks/`), kein Produktcode. Kein Nutzerdatenpfad, keine Kanal-Inhalte, kein Trip/Ortsvergleich-Pendant — die drei Querschnitts-Prüfpunkte entfallen.

## Estimated Scope

- **LoC:** ~70 produktiv (+ ~90 Test)
- **Files:** 3 Hooks + 1 Testdatei
- **Effort:** low–medium (Hard Gate: Mutationsprobe Pflicht)

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `_e2e_paths._git_diff_names` | Funktion | liefert weiter die Dateinamen; `None` ⇒ fail-closed (#1121) |
| `tests/tdd/test_issue_728_telegram_scope_neutral.py` | Test | Vorbild (echte temporäre git-Repos), muss grün bleiben |
| `tests/tdd/test_issue_1121_git_diff_returncode.py` | Test | fail-closed bei Diff-Fehler, muss grün bleiben |

## Implementation Details

1. **`_e2e_paths._git_diff_lines(base, target, repo_dir, path)`** — `git diff -U0 <base> <target> -- <path>`; liefert die geänderten Zeilen (mit `+`/`-` Präfix, ohne `+++`/`---`-Kopf), `None` bei git-Fehler.
2. **`_scope_touches_telegram(changed_files, diff_reader=None)`** — neuer optionaler Parameter. Ohne `diff_reader`: Verhalten unverändert (nur Namen). Mit `diff_reader`: Eine Telegram-namige Datei gilt als **neutral**, wenn `_is_mode_only_change(zeilen)` wahr ist; `diff_reader` liefert `None` ⇒ Datei zählt als Telegram-Scope (fail-closed).
3. **`_is_mode_only_change(zeilen)`** — wahr nur, wenn
   - die Zeilenliste nicht leer ist (leerer Diff, Binär-/Umbenennungs-/Neuanlage-Diff ohne Hunk ⇒ **nicht** neutral),
   - JEDE geänderte Zeile (hinzugefügt UND entfernt) nach `strip()` in der Whitelist liegt: leer · nur `}`/`)`/`{` · reiner Kommentar (`//`, `#`) · Import-Zeile, die `fsmode` nennt · Zeile mit `fsmode.` · `os.Chmod(`/`os.chmod(`-Aufruf mit `fsmode` im Argument · `if <bezeichner> == nil {` (Klammer-Zeile des Chmod-Blocks),
   - und mindestens EINE geänderte Zeile `fsmode` enthält (sonst ist es keine Modus-Änderung, sondern z. B. nur Klammer-Umbau).
4. **`staging_gate._telegram_live_gate`** — übergibt `diff_reader` (Closure über `_e2e_paths._git_diff_lines("HEAD~1", "HEAD", _verified_repo_dir(), pfad)`). `changed is None` bleibt blockend wie bisher.
5. Mehrere Dateien: das Gate bleibt zu, sobald **eine** Telegram-namige Datei nicht rein modusbedingt ist.

## Expected Behavior

- **Input:** Änderungssatz `HEAD~1..HEAD`
- **Output:** `_telegram_live_gate` = 0, wenn jede Telegram-namige Datei nur die Modus-Whitelist berührt (oder `GZ_TELEGRAM_TEST_CHAT_ID` gesetzt ist); sonst 1 ohne Chat-ID.
- **Side effects:** keine; kein Schreibzugriff, ein zusätzlicher lesender `git diff` je Telegram-namiger Datei.

## Acceptance Criteria

- **AC-1:** Given ein git-Repo, in dem `internal/handler/telegram_connect.go` nur den `fsmode`-Import und den `os.Chmod(tmpName, fsmode.FileMode)`-Block (inkl. `if werr == nil {`/`}`) hinzugefügt bekommt, und `GZ_TELEGRAM_TEST_CHAT_ID` ist nicht gesetzt / When `_telegram_live_gate()` läuft / Then Rückgabe 0 (Gate blockt nicht).
  - Test: echtes temporäres git-Repo mit dem Diff aus Commit 04b8e0472.

- **AC-2:** Given dieselbe Modus-Änderung plus eine weitere geänderte Logikzeile in derselben Datei (z. B. geänderte Bedingung oder Rückgabewert) ohne Chat-ID / When das Gate läuft / Then Rückgabe 1 (Telegram-Scope bleibt).
  - Test: temporäres git-Repo, Modus-Block + eine Nicht-Whitelist-Zeile.

- **AC-3:** Given eine entfernte (nicht hinzugefügte) Logikzeile in der Telegram-Datei, kombiniert mit einer Modus-Zeile, ohne Chat-ID / When das Gate läuft / Then Rückgabe 1.
  - Test: temporäres Repo mit gelöschter Logikzeile.

- **AC-4:** Given der Diff einer Telegram-namigen Datei ist nicht lesbar (`git diff` scheitert) oder `HEAD~1` fehlt, ohne Chat-ID / When das Gate läuft / Then Rückgabe 1 (fail-closed, #1121 bleibt).
  - Test: Repo mit nur einem Commit bzw. ungültigem Pfad; bestehender #1121-Test bleibt grün.

- **AC-5:** Given zwei Telegram-namige Dateien, eine rein modusbedingt, eine mit Logikänderung, ohne Chat-ID / When das Gate läuft / Then Rückgabe 1; sind beide rein modusbedingt, Rückgabe 0.
  - Test: temporäre Repos für beide Konstellationen.

- **AC-6:** Given ein Diff, dessen geänderte Zeilen nur Leer-/Klammerzeilen sind, aber keine Zeile `fsmode` nennt, bzw. eine neu angelegte Telegram-Datei, ohne Chat-ID / When das Gate läuft / Then Rückgabe 1.
  - Test: temporäres Repo (Klammer-Umbau; Neuanlage `telegram_x.go`).

- **AC-7:** Given Änderungen nur in Dateien ohne „telegram" im Pfad bzw. nur in Neutral-Pfaden (#728) / When das Gate läuft / Then Rückgabe 0 wie bisher; die bestehenden Tests `test_issue_728_*` und `test_issue_1121_*` bleiben grün.
  - Test: bestehende Testdateien unverändert laufen lassen.

- **AC-8:** Given ein Python-Telegram-Modul (z. B. `src/channels/telegram_x.py`) bekommt nur `from … import fsmode`-Äquivalent und `os.chmod(pfad, fsmode.FILE_MODE)` / When das Gate läuft / Then Rückgabe 0; mit zusätzlicher Logikzeile Rückgabe 1.
  - Test: temporäres Repo mit Python-Datei.

## Known Limitations

- Ein bloßes Dateimodus-Bit (`chmod +x`, kein Hunk) gilt weiter als Telegram-Scope (konservativ).
- Whitelist ist bewusst eng; künftige andere Querschnittsänderungen (nicht `fsmode`) lösen das Gate weiter aus.
- **Zweiter Befund des Tickets** (Teardown-Error von `test_heute_ohne_namen_bei_trip_und_vergleich_fragt_live_zurueck`): nicht Teil dieses Fixes, Ursache nicht reproduziert (braucht `GZ_TELEGRAM_LIVE=1`-Lauf). Wird als Checkbox in #1199 gebucht; nicht nutzersichtbar.
- Die Alternative „Ausnahme per Spec-Feld" ist verworfen (Selbstfreigabe durch den Autor).

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** keine
- **Rationale:** Schärfung einer Gate-Heuristik innerhalb der bestehenden Entscheidung (#686/#728/#1121); keine neue Grundsatzentscheidung. Regel-Budget: ersetzt die reine Namensheuristik, keine neue Pflicht-Regel.

## Changelog

- 2026-10-27: Initial spec created (#2630)
