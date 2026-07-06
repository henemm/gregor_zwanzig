# Context: fix-1020-tmp-cookie-perms

## Request Summary
Root-Cause-Fix zu Security-Finding `henemm-security#199` (CVSS 8.1): Playwright
`storage_state()`-Dateien mit echten Staging-Session-Cookies werden von 5 TDD-Testdateien
per einfachem `open(STATE_FILE, "w")` nach `/tmp` geschrieben. Unter Server-`umask 0002`
ergibt das Modus `664` (world-readable) — jeder lokale Account kann die Session kapern.
Zusätzlich zeigen 2 Doku-Dateien ein `curl -c /tmp/...cookies.txt`-Beispiel mit demselben
unsicheren Muster als Kopiervorlage für künftige Skripte.

## Related Files
| File | Relevance |
|------|-----------|
| `tests/tdd/test_issue_727_trips_null_safety.py` | Zeile 31 `STATE_FILE`, Zeile 66 `open(STATE_FILE, "w")` — schreibt `/tmp/tdd-727-storage-state.json` |
| `tests/tdd/test_794_mobile_metric_label.py` | Zeile 55/56 `STATE_FILE`/`STATE_FILE_FALLBACK`, Zeile 107 `open(STATE_FILE, "w")` — liest zusätzlich als Fallback `tdd-702-storage-state.json` |
| `tests/tdd/test_issue_846_alert_preset_e2e.py` | Zeile 39 `STATE_FILE`, Zeile 81 `open(STATE_FILE, "w")` |
| `tests/tdd/test_bundle_d_785_yesterday_toggle.py` | Zeile 30 `STATE_FILE`, Zeile 63 `open(STATE_FILE, "w")` |
| `tests/tdd/test_702_alerts_mobile_parity.py` | Zeile 28 `STATE_FILE`, Zeile 66 `open(STATE_FILE, "w")` |
| `docs/specs/modules/fix_698_validator_user_sync.md` | Zeile 93 — `curl -c /tmp/validator_cookies.txt` als Bash-Beispiel |
| `docs/context/external-validator-auth.md` | Zeile 85 — `curl -c cookies.txt` als Bash-Beispiel |

Alle 5 Testdateien folgen identisch diesem Muster:
```python
STATE_FILE = "/tmp/tdd-NNN-storage-state.json"
...
if os.path.exists(STATE_FILE):
    with open(STATE_FILE) as f:
        ...
...
state = ctx.storage_state()
with open(STATE_FILE, "w") as f:
    json.dump(state, f)
```

## Existing Patterns
- Kein gemeinsamer Test-Helper/Fixture für Playwright-Login-State vorhanden (`tests/conftest.py`,
  `tests/tdd/conftest.py` enthalten dazu nichts) — jede Testdatei dupliziert das Muster eigenständig.
  Eine Konsolidierung in einen Helper wäre wünschenswert, ist aber für diesen Security-Fix
  bewusst **nicht** im Scope (Minimal-Footprint-Prinzip; Konsolidierung wäre ein separates
  Refactoring-Issue).
- Andere geprüfte Kandidaten aus der ursprünglichen Vermutung in `henemm-security#199`
  (`email_spec_validator.py`, `briefing_mail_validator.py`, `e2e_browser_test.py`, verwandt mit
  `#972`) sind **nicht** betroffen — sie nutzen IMAP-Credentials, keine Session-Cookies/`storage_state`.
  Verifiziert per Grep über das gesamte Repo (`storage_state`/`STATE_FILE`/`cookies.txt`-Muster) —
  keine weiteren Fundstellen außer den 7 im Issue genannten.

## Dependencies
- Upstream: Playwright `BrowserContext.storage_state()` (liefert dict mit Cookies inkl.
  `gz_session`, `httpOnly=true`, domain=staging.gregor20.henemm.com)
- Downstream: Die geschriebenen `STATE_FILE`s werden von denselben Tests (und in `test_794` auch
  von einem anderen Test als Fallback) wieder eingelesen, um wiederholte Logins zu vermeiden.
  Der Fix darf dieses Wiederverwendungs-Verhalten nicht brechen — nur die Datei-Rechte ändern sich.

## Existing Specs
- Keine bestehende Spec zu Test-Tooling-Sicherheit. Neue Mini-Spec/Spec für dieses Issue nötig.

## Risks & Considerations
- **Race/Kompatibilität:** `os.open(..., 0o600)` statt `open()` muss weiterhin von `json.dump`
  beschreibbar sein (`os.fdopen(fd, "w")`) — sonst brechen die Tests.
- **Bestehende Dateien:** Alte, bereits mit 664 geschriebene State-Dateien in `/tmp` sind nicht
  Teil dieses Fixes (Infra-`monitor.sh` räumt sie bereits automatisch weg, siehe
  `henemm-security#199`-Kommentar). Dieser Fix verhindert nur künftiges Neu-Schreiben mit falschem Modus.
- **Kein Produktionscode betroffen** — reine Test-Fixtures + 2 Doku-Beispiele. Blast Radius bleibt
  niedrig, aber die Testdateien müssen weiterhin lokal wie in CI lauffähig bleiben (kein Mock-Verbot
  verletzt, da hier kein E-Mail/API-Verhalten getestet wird, sondern nur Datei-I/O geändert wird).
- **Doku-Beispiele:** Sollten auf ein sicheres Muster umgestellt werden (z.B. `(umask 077; curl -c ...)`
  oder `mktemp -d` mit Modus 700), damit sie nicht weiter als Vorlage für neue unsichere Skripte dienen.

## Analysis

### Type
Bug (Security-Fix, Root Cause zu `henemm-security#199` / gregor-Issue `#1020`)

Kein paralleler Explore-/bug-intake-Dispatch nötig: Root Cause ist bereits vollständig verifiziert
(Issue #1020 benennt exakt 7 Fundstellen mit Zeilennummern), eigene Grep-Verifikation in der
Kontext-Phase bestätigt Vollständigkeit und schließt weitere Kandidaten aus. Ein zusätzlicher
Agenten-Umlauf würde dieselbe bereits bekannte Antwort reproduzieren (Standard-Track-Prinzip:
Aufwand proportional zur verbleibenden Unsicherheit — hier: keine).

### Affected Files (with changes)
| File | Change Type | Description |
|------|-------------|-------------|
| `tests/tdd/test_issue_727_trips_null_safety.py` | MODIFY | `open(STATE_FILE, "w")` (Z.66) → `os.open(STATE_FILE, os.O_WRONLY\|os.O_CREAT\|os.O_TRUNC, 0o600)` + `os.fdopen` |
| `tests/tdd/test_794_mobile_metric_label.py` | MODIFY | Gleicher Fix an Z.107 |
| `tests/tdd/test_issue_846_alert_preset_e2e.py` | MODIFY | Gleicher Fix an Z.81 |
| `tests/tdd/test_bundle_d_785_yesterday_toggle.py` | MODIFY | Gleicher Fix an Z.63 |
| `tests/tdd/test_702_alerts_mobile_parity.py` | MODIFY | Gleicher Fix an Z.66 |
| `docs/specs/modules/fix_698_validator_user_sync.md` | MODIFY | `curl -c /tmp/validator_cookies.txt` (Z.93) → sicheres Muster (umask-Subshell oder `mktemp -d` 700) |
| `docs/context/external-validator-auth.md` | MODIFY | `curl -c cookies.txt` (Z.85) → sicheres Muster |
| `tests/tdd/test_issue_1020_tmp_cookie_perms.py` | CREATE | Neuer TDD-Test: schreibt via einer der Fix-Funktionen eine State-Datei und prüft `stat().st_mode & 0o077 == 0` (kein Gruppen-/Other-Zugriff) |

Alle 5 Testdateien haben `import os` bereits vorhanden — kein neuer Import nötig.
Import bestätigt: `test_issue_727` (Z.15), `test_794`, `test_issue_846`, `test_bundle_d_785`,
`test_702` (Z.15) — je 1 Treffer für `^import os$`.

### Scope Assessment
- Files: 7 MODIFY + 1 CREATE (Test) = 8
- Estimated LoC: +~40/-10 (5x kleiner Block-Austausch ~4 Zeilen je Datei, 2x Doku-Zeile, 1 neuer Testdatei ~30 Zeilen)
- Risk Level: LOW — reine Test-Fixtures und Doku, kein Produktionscode, kein Auth-Pfad, keine
  Breaking Changes am Storage-State-Wiederverwendungs-Verhalten (nur Rechte ändern sich)

### Technical Approach
Für alle 5 Testdateien denselben Patch anwenden (Muster aus Issue #1020 übernommen):
```python
fd = os.open(STATE_FILE, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
with os.fdopen(fd, "w") as f:
    json.dump(state, f)
```
Das ersetzt `with open(STATE_FILE, "w") as f: json.dump(state, f)` 1:1 — funktional identisch,
nur mit explizitem Modus 0600, unabhängig von der Server-`umask`.

Für die beiden Doku-Beispiele: `curl -c` in eine `(umask 077; curl -c /tmp/... )`-Subshell packen
oder auf `mktemp` mit Verzeichnis-Modus 700 umstellen, damit kopierte Snippets künftig sicher sind.

Neuer TDD-Test beweist das Verhalten nach KEINE-MOCKS-Regel real: schreibt tatsächlich eine Datei
über den Fix-Codepfad (kein Mock von `os.open`) und prüft per `os.stat(...).st_mode` die tatsächlichen
Dateirechte auf Disk — das ist Verhalten, keine Code-Analyse.

### Dependencies
- Kein Produktionscode betroffen, keine Downstream-Konsumenten außer den Tests selbst
  (`test_794` liest `tdd-702-storage-state.json` als Fallback — Lesepfad bleibt unverändert,
  nur der Schreibpfad ändert sich)

### Open Questions
- Keine. Scope, Root Cause und Fix-Muster sind vollständig bekannt.
