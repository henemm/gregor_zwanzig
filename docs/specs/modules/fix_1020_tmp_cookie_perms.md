---
entity_id: fix_1020_tmp_cookie_perms
type: module
created: 2026-07-06
updated: 2026-07-06
status: draft
version: "1.0"
tags: [security, tests, tmp]
---

# Fix #1020: Sichere Dateirechte für Playwright-Session-State in /tmp

## Approval

- [ ] Approved

## Purpose

Root-Cause-Fix zu `henemm-security#199` (CVSS 8.1): Playwright-`storage_state()`-Dateien mit
echten Staging-Session-Cookies wurden bisher mit Standard-`open()` nach `/tmp` geschrieben, was
unter der Server-`umask 0002` zu Modus `664` (world-readable) führt. Jeder lokale Account auf dem
Server konnte damit gültige `gz_session`-Cookies für `staging.gregor20.henemm.com` auslesen und
Sessions kapern. Dieser Fix stellt sicher, dass neu geschriebene State-Dateien nur für den
Eigentümer les-/schreibbar sind.

## Source

- **Files:** `tests/tdd/test_issue_727_trips_null_safety.py`, `tests/tdd/test_794_mobile_metric_label.py`,
  `tests/tdd/test_issue_846_alert_preset_e2e.py`, `tests/tdd/test_bundle_d_785_yesterday_toggle.py`,
  `tests/tdd/test_702_alerts_mobile_parity.py`
- **Identifier:** jeweils der `open(STATE_FILE, "w")`-Aufruf beim Schreiben von `ctx.storage_state()`

> **Schicht-Hinweis:** Reine Test-Tooling-Dateien unter `tests/tdd/` + 2 Doku-Beispiele unter
> `docs/`. Kein Produktionscode (kein Go-API, kein Frontend, kein Python-Core-Backend) betroffen.

## Estimated Scope

- **LoC:** ~40 (+30/-10)
- **Files:** 7 MODIFY (5 Tests + 2 Doku) + 1 CREATE (neuer TDD-Test)
- **Effort:** low

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| Playwright `BrowserContext.storage_state()` | Upstream | Liefert das Session-State-Dict (inkl. `gz_session`-Cookie), das in die Datei geschrieben wird |
| `tests/tdd/test_794_mobile_metric_label.py` (Fallback-Lesepfad `STATE_FILE_FALLBACK`) | Downstream | Liest ggf. die von `test_702` geschriebene State-Datei — Lesepfad bleibt unverändert |

## Implementation Details

```python
# Vorher (world-readable unter umask 0002):
with open(STATE_FILE, "w") as f:
    json.dump(state, f)

# Nachher (immer 0600, unabhaengig von der Server-umask):
fd = os.open(STATE_FILE, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
with os.fdopen(fd, "w") as f:
    json.dump(state, f)
```

Identischer Patch in allen 5 Testdateien (Zeilen laut Analyse: 66, 107, 81, 63, 66). `import os`
ist in allen 5 Dateien bereits vorhanden — kein neuer Import nötig.

Für die 2 Doku-Beispiele (`docs/specs/modules/fix_698_validator_user_sync.md:93`,
`docs/context/external-validator-auth.md:85`): `curl -c /tmp/...cookies.txt` durch eine
umask-Subshell ersetzen, z.B. `(umask 077; curl -s -c /tmp/validator_cookies.txt ...)`, damit das
Beispiel nicht weiter als unsichere Kopiervorlage dient.

## Expected Behavior

- **Input:** Playwright-Login-Flow erzeugt `ctx.storage_state()` mit `gz_session`-Cookie
- **Output:** State-Datei in `/tmp` mit Inhalt unverändert, aber Dateirechte `0600` (nur Owner)
- **Side effects:** Keine — bestehendes Lese-/Wiederverwendungsverhalten bleibt exakt gleich,
  nur die beim Schreiben gesetzten Rechte ändern sich

## Acceptance Criteria

- **AC-1:** Given ein Playwright-E2E-Test führt einen Login durch und schreibt danach seine
  Session-State-Datei nach `/tmp`, When die Datei auf der Platte angelegt wird, Then sind für
  diese Datei Gruppe und Andere ohne jeden Zugriff (keine Lese-, Schreib- oder Ausführrechte).
  - Test: Realer Testlauf (kein Mock) schreibt über den gefixten Codepfad tatsächlich eine Datei
    und prüft per `os.stat(pfad).st_mode` die tatsächlichen Dateirechte auf Disk — bewiesenes
    Verhalten, nicht Code-Analyse.

- **AC-2:** Given der bestehende Mechanismus, der eine zuvor geschriebene Session-State-Datei
  wiederverwendet um einen erneuten Login zu vermeiden (z.B. `test_794`s Fallback-Lesepfad), When
  der Rechte-Fix angewendet wird, Then funktioniert das Wiedereinlesen einer zuvor mit den neuen
  Rechten geschriebenen State-Datei weiterhin unverändert.
  - Test: Bestehender Test mit Wiederverwendungs-Logik läuft nach dem Fix weiterhin grün (echter
    Playwright-Lauf, kein Mock des Dateisystems).

- **AC-3:** Given die beiden Doku-Beispiele mit `curl -c` zeigen aktuell ein Muster, das unter
  Standard-`umask` world-readable Cookie-Dateien erzeugt, When ein Entwickler das aktualisierte
  Beispiel unverändert kopiert, Then erzeugt das kopierte Snippet keine world-readable Datei mehr
  (umask-Subshell oder gleichwertiges Muster im Beispieltext enthalten).
  - Test: Manuelle Sichtprüfung des Doku-Diffs — reine Textvorlage ohne ausführbaren Code, daher
    kein automatisierter Test (Ausnahme laut `CLAUDE.md`: Dokumentations-Compliance ist kein
    Nutzerverhalten).

## Known Limitations

- Bereits vor diesem Fix in `/tmp` liegende, mit Modus `664` geschriebene Alt-Dateien werden von
  diesem Fix **nicht** rückwirkend korrigiert — das übernimmt bereits der Infra-`monitor.sh`-Job
  (härtet alle 5 Minuten bestehende Treffer, siehe `henemm-security#199`-Kommentar). Dieser Fix
  wirkt ausschließlich auf künftig neu geschriebene Dateien.
- Der Fix ändert nichts an der Tatsache, dass Session-Cookies überhaupt in `/tmp` (statt einem
  privaten Verzeichnis mit Modus 700) landen — das wäre eine weitergehende Härtung, aber laut
  Issue #1020 als Fix-Empfehlung ausreichend, da Modus 0600 in Kombination mit `/tmp`s Sticky-Bit
  bereits verhindert, dass andere Nutzer die Datei lesen oder löschen können.

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** keine
- **Rationale:** Reine Sicherheits-Korrektur an Dateirechten in Test-Tooling, keine
  Architektur- oder Schnittstellenänderung — kein ADR erforderlich (analog zu anderen
  `[no-adr]`-Fixes in diesem Repo).

## Changelog

- 2026-07-06: Initial spec created (Root Cause aus Issue #1020 übernommen)
