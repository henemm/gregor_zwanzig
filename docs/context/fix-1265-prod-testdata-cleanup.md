# Context: fix-1265-prod-testdata-cleanup

**Issue:** #1265 — Prod-Testdaten-Altlasten aufräumen + Schutz vor Test-Artefakten in Produktion
**Track:** Standard (Intake-Score 3: Scope Medium, Blast Radius High, Unsicherheit Low)
**Quelle:** Prod-Audit 2026-07-16 (Befund 1, PO-Priorität 1), Inventur-Agent 2026-07-16 (read-only)

## Request Summary

Die Produktions-Daten enthalten Altlasten alter Testläufe: 35+ Test-User-
Verzeichnisse unter `data/users/`, 4 Test-Presets im default-User (davon 3
aktiv vom Scheduler versandt), Test-Snapshots. Aufräumen mit PO-bestätigter
Liste + Backup; danach strukturelle Guards, damit das nie wieder passiert.

## Inventur (verifiziert, Stand 2026-07-16)

### Echte Konten — NIE anfassen
`default` (produktiver Hauptaccount), `henning`, `steffi`, `admin`.
Im default-User ECHT: `trips/gr221-mallorca.json`,
`weather_snapshots/gr221-mallorca*.json`, `user.json` + Betriebs-Dateien.

### Löschkandidaten
| Gruppe | Einträge | Beleg | Scheduler-aktiv? |
|---|---|---|---|
| `tdd-1012-*` (10), `tdd-1113-*` (5), `tdd-768-*` (3) | 18 Verz. | user.json mit gregor-test@, mtime ≤2026-07-12 | **JA** — `ListUserIDs()` (internal/store/user.go:16) filtert nur auf user.json-Existenz; `runForAllUsers` (internal/scheduler/scheduler.go:131,141-149) verarbeitet sie in JEDEM Lauf |
| `tdd-1007-*` (8), `tdd-1009-usera`, `tdd-773-*` (2), `design_tdd` | 12 Verz. | leer, kein user.json | nein |
| `tdd-638-*` (6) | 6 Verz. | nur alert_log/alert_state, kein user.json | nein |
| default: `compare_presets.json` | ALLE 4 Presets (cp-923d0c80712de2f1 „Test #517"/test@example.com; cp-c7c3a2ba83996ac0, cp-956455a97aa5cb22, cp-4c9284f8a22eb3d6 „Screenshot-1106…"/screenshot-1106@example.com, enabled/daily, letzter_versand 2026-07-10, Orte e2e-loc-*) | kein echtes Preset in der Datei | **JA** (3x daily versandt) |
| default: `weather_snapshots/` Test-Reste | `34ab4f37*`, `5f534011*`, `bug663-isolation-trip*`, `t802-*`, `test-884-validation*` | zu Test-Trips gehörig | nein |

### Klärungsfall (NICHT in dieser Runde löschen)
`validator-issue110/` — 8 Validator-Trips, mtime 2026-07-15 11:02 (frisch,
vermutlich prod_selftest/Validator-Infrastruktur). Erst Nutzung klären.

### Nicht lesbar (Permission, claude-gregor-owned)
`default/briefings/`, `default/compare_weather_snapshots/`,
Inhalte von `validator-issue110/briefings/` u.a. — Lösch-Script muss als
claude-gregor laufen (Regel: Daten-Migration = per-Host-Schritt, idempotent
+ Backup).

## Verursacher-Befund (Guard-Ziele)

1. **Fünf Kern-Testdateien schreiben an der Isolation vorbei direkt in
   `<repo>/data/users/`** (im Haupt-Checkout = PROD-Daten):
   `test_issue_1007_heute_voll_briefing.py:42,78-86`,
   `test_issue_1012_no_data_guard.py:50,79,142`,
   `test_issue_1113_partial_outage_guard.py:60,89,127,135`,
   `test_issue_768_test_briefing_fallback.py:47,49,124`,
   `test_issue_638_alerts_redesign.py:273,470,533,583` (cwd-relativ).
2. **Isolations-Lücke:** autouse `_isolate_data_root` (tests/conftest.py:37-58,
   #1133) biegt nur `app.loader._DATA_ROOT` um — direkte `_REPO_ROOT/data`-
   und cwd-Pfade laufen vorbei; Opt-out-Marker `real_data_root`/`live`.
   `tests/tdd/conftest.py:48` kennt tdd-638-User sogar explizit.
3. **„Screenshot-1106 <epoch-ms>":** zur Laufzeit generierter Name eines
   E2E-/Screenshot-Laufs zu #1106, der gegen den PROD-default-User Presets
   anlegte (Orte `e2e-loc-innsbruck/stubai` aus frontend/e2e/global.setup.ts);
   letzter_versand beweist Prod-Scheduler-Versand.
4. **Prod-Datentopf ungeschützt:** Staging hat via `GZ_STAGING_DATA_DIR`
   einen eigenen Topf; für `/home/hem/gregor_zwanzig/data/users` existiert
   kein Write-Guard. `is_test_user_id()` existiert bereits
   (src/app/config.py:30; Go-Spiegel internal/mail/sender.go:48) — wird vom
   Scheduler NICHT genutzt.

## Analysis (Standard, inline)

### Ansatz (4 Teile, ein Workflow)
- **A Bereinigung:** idempotentes Script `scripts/cleanup_1265_prod_testdata.py`
  nach Migrations-Muster (--dry-run default / --execute; tar.gz-Voll-Backup
  von data/users vor Löschung; exakte Positivliste aus der PO-Freigabe —
  KEINE Muster-Löschung zur Laufzeit; echte Konten hart ausgenommen).
  Läuft als claude-gregor auf dem Host (Permission-Lage).
- **B Scheduler-Härtung (Defense in Depth):** `runForAllUsers` überspringt
  Test-User-IDs via Go-Prädikat (Spiegel von `is_test_user_id`) — künftige
  Leaks werden nicht mehr verarbeitet.
- **C pytest-Guard:** `_isolate_data_root` härten — Kern-Testlauf ohne
  `real_data_root`/`live`-Marker FAILT bei Write unter `<repo>/data/users`
  (chdir auf tmp + Assertion-Wächter); die 5 Leak-Testdateien auf
  `get_data_dir()`/tmp umstellen (Verhalten unverändert, nur Pfad-Quelle).
- **D E2E-Prod-Sperre:** global.setup.ts/Compare-Specs verweigern Läufe,
  wenn Base-URL auf die Prod-Domain zeigt (Assertion, kein stiller Skip).

### Scope: ~9 Dateien, ~280-380 LoC → LoC-Override 400 bei Freigabe
### Risk: HIGH nur in Teil A (Prod-Löschung) — durch Positivliste + Backup + dry-run kontrolliert; B/C/D sind kleine, isolierte Härtungen.

## Risks & Considerations
- Löschliste ist eine POSITIVLISTE in der Spec — das Script löscht exakt
  diese Pfade/IDs, nichts per Wildcard zur Laufzeit.
- `validator-issue110` bleibt stehen (Klärungsfall, eigener Checkpunkt).
- Backup-Pfad `.backups/` (Retention beachten), Restore-Weg dokumentieren.
- Teil C ändert 5 Bestands-Testdateien — deren Beweiskraft (Live-Contract-
  Charakter) darf nicht verwässern: nur Pfad-Bezug ändern, Marker prüfen.
- Nach Teil A: Scheduler-Log beobachten (kein Fehler durch fehlende Dirs).
