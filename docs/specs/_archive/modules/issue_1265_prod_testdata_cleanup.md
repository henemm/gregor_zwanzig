---
entity_id: issue_1265_prod_testdata_cleanup
type: module
created: 2026-07-16
updated: 2026-07-16
status: approved
---

# Issue #1265 — Prod-Testdaten-Altlasten aufräumen + Schutz vor Test-Artefakten

## Approval

- [x] Approved — PO 2026-07-16 (inkl. Löschliste + LoC-Override 400)

## Purpose

Die Produktions-Daten (`/home/hem/gregor_zwanzig/data/users/`) enthalten
Altlasten alter Testläufe: 36 Test-User-Verzeichnisse, 4 Test-Presets im
default-User (3 davon aktiv daily versandt), Test-Snapshots. 13 Test-Konten
werden vom Scheduler in jedem Lauf mitverarbeitet. Der PO sieht beim Öffnen
der Vergleichs-Liste eine Testdaten-Halde (Auslöser der Eskalation
2026-07-16). Dieses Modul bereinigt die Altlasten über eine PO-bestätigte
Positivliste mit Backup und errichtet vier strukturelle Guards, damit
Testläufe nie wieder in Produktions-Daten schreiben.

## Source

- Prod-Audit 2026-07-16: `docs/artifacts/audit-1256-prod/` + Memory
  `project_audit_compare_prod_2026_07_16`
- Inventur + Verursacher-Analyse: `docs/context/fix-1265-prod-testdata-cleanup.md`
- Betroffener Code: `internal/scheduler/scheduler.go:131-149` (runForAllUsers),
  `internal/store/user.go:16-40` (ListUserIDs), `tests/conftest.py:37-58`
  (_isolate_data_root, #1133), 5 Leak-Testdateien (s. Context-Doc),
  `frontend/e2e/global.setup.ts`, `src/app/config.py:30` (is_test_user_id)

## Estimated Scope

- Files: ~9 (1 neues Script, scheduler.go, user.go o. Prädikat-Datei,
  conftest.py, 5 Testdateien, global.setup.ts)
- LoC: ~280–380 → Override 400 (PO-go)
- Effort: 1 Workflow

## Dependencies

| Entity | Type | Purpose |
|---|---|---|
| `is_test_user_id` (src/app/config.py:30, Spiegel internal/mail/sender.go:48) | Prädikat | Test-User-Erkennung für Scheduler-Filter |
| `_isolate_data_root` (tests/conftest.py, #1133) | Fixture | Härtungs-Ziel Guard C |
| `data_schema_backup.py` / `.backups/` | Hook/Ablage | Backup-Konvention |
| Prod-Host-Ausführung als `claude-gregor` | Betrieb | Permission-Lage data/users (Regel: Migration = per-Host-Schritt) |

## Implementation Details

### 1. Teil A — Bereinigungs-Script (Positivliste, dry-run-first)

`scripts/cleanup_1265_prod_testdata.py`, Muster `migrate_1257`/`migrate_1258`:
`--dry-run` (Default, druckt exakt was gelöscht würde) / `--execute`.
Vor jeder Löschung: tar.gz-Voll-Backup von `data/users/` nach
`.backups/cleanup-1265-<timestamp>.tar.gz` (Restore-Kommando wird geloggt).
Idempotent (zweiter Lauf: 0 Aktionen). Läuft auf dem Prod-Host als
`claude-gregor`. Harte Sicherung: die vier echten Konten `default`,
`henning`, `steffi`, `admin` sind im Script als NIE-löschen-Konstante
verankert; das Script löscht ausschließlich die folgende POSITIVLISTE
(keine Wildcard-Auflösung zur Laufzeit — die Liste steht wörtlich im Script):

**A1 — User-Verzeichnisse (36):**
`tdd-1007-ac1, tdd-1007-ac2, tdd-1007-ac4, tdd-1007-ac6,
tdd-1007-adv-verify, tdd-1007-f001, tdd-1007-usera, tdd-1007-userb,
tdd-1009-usera, tdd-1012-ac1, tdd-1012-ac2, tdd-1012-ac3, tdd-1012-ac4,
tdd-1012-ac4b, tdd-1012-ac6, tdd-1012-ac6b, tdd-1012-ac6c, tdd-1012-ac7,
tdd-1012-f001, tdd-1113-ac1, tdd-1113-ac2, tdd-1113-ac3a, tdd-1113-ac3b,
tdd-1113-ac5, tdd-638-ac1, tdd-638-ac2, tdd-638-ac3, tdd-638-f001,
tdd-638-legacy, tdd-638-mixed, tdd-768-future, tdd-768-multi,
tdd-768-past, tdd-773-ac3, tdd-773-ac4, design_tdd`

**A2 — default-User, `compare_presets.json`:** Entfernen der vier Einträge
`cp-923d0c80712de2f1` („Test #517"), `cp-c7c3a2ba83996ac0`,
`cp-956455a97aa5cb22`, `cp-4c9284f8a22eb3d6` („Screenshot-1106…") per
Read-Modify-Write (Datei bleibt, wird zur leeren Liste; kein echtes Preset
vorhanden — verifiziert).

**A3 — default-User, `weather_snapshots/`:** Dateien mit Präfixen
`34ab4f37`, `5f534011`, `bug663-isolation-trip`, `t802-`,
`test-884-validation` (aufgelöste Ist-Liste wird im dry-run gedruckt und
im Execute-Log festgehalten; `gr221-mallorca*` bleibt).

**NICHT in dieser Runde:** `validator-issue110/` (mtime 2026-07-15, aktive
Validator-Infrastruktur — Klärung separat), `default/briefings/` und
`compare_weather_snapshots/` (nicht inventarisiert; Folge-Kandidat nach
Sichtung als claude-gregor, nur dry-run-Ausgabe in dieser Runde).

### 2. Teil B — Scheduler-Härtung (Defense in Depth)

`runForAllUsers` (`internal/scheduler/scheduler.go:141`) überspringt IDs,
für die das neue Go-Prädikat `model.IsTestUserID` (Spiegel von
`is_test_user_id`, Ort analog internal/mail/sender.go:48 —
konsolidieren statt duplizieren) wahr ist, mit einmaligem Log je Lauf.
Wirkung: künftig geleakte Test-Konten werden nie mehr verarbeitet/versandt.

### 3. Teil C — pytest-Guard (Verursacher abstellen)

`_isolate_data_root` (tests/conftest.py) wird gehärtet: Tests ohne
`real_data_root`/`live`-Marker laufen mit cwd auf tmp UND einem Wächter,
der am Test-Ende prüft, dass unter `<repo>/data/users` keine neuen/geänderten
Einträge entstanden sind — sonst FAIL mit Klartext-Hinweis. Die fünf
Leak-Testdateien (1007/1012/1113/768/638) werden auf `get_data_dir()`-
bzw. tmp-Pfade umgestellt — nur die Pfad-Quelle ändert sich, Assertions
und Live-Contract-Charakter bleiben unangetastet.

### 4. Teil D — E2E-Prod-Sperre

`frontend/e2e/global.setup.ts` (und damit alle datenanlegenden Specs)
bricht hart ab, wenn die Base-URL auf die Prod-Domain
(`gregor20.henemm.com` ohne `staging.`-Präfix) zeigt — Assertion mit
Klartext-Fehler, kein stiller Skip.

## Expected Behavior

- **Input:** PO-bestätigte Positivliste (diese Spec), Prod-Datenbestand
- **Output:** Bereinigte `data/users/` (nur echte Konten + validator-issue110),
  leere `compare_presets.json`-Liste im default-User, Backup-Archiv,
  Execute-Log; Scheduler ohne Test-User-Verarbeitung; Kern-Tests, die in
  Repo-Daten schreiben wollen, schlagen fehl; E2E gegen Prod bricht ab
- **Side effects:** einmalig weniger Scheduler-Arbeit (13 Konten weniger);
  keine Schema-Änderung; kein Mail-Versand

## Acceptance Criteria

**AC-1:** Given der Prod-Datenbestand mit den 36 gelisteten Test-User-Verzeichnissen / When das Bereinigungs-Script mit `--execute` läuft / Then existiert vorher ein tar.gz-Backup von `data/users/`, danach sind exakt die 36 Verzeichnisse entfernt, und `default`, `henning`, `steffi`, `admin` sowie `validator-issue110` sind byte-identisch unangetastet.
  - Test: Script-Kern-Test gegen tmp-Fixture-Baum (Positivliste, Backup-Datei entsteht, echte Konten unverändert); zweiter Lauf = 0 Aktionen (idempotent).

**AC-2:** Given die `compare_presets.json` des default-Users mit den vier Test-Presets / When das Script läuft / Then enthält die Datei danach eine leere Preset-Liste, bleibt valides JSON im erwarteten Schema, und die Vergleichs-Liste der App zeigt keine Einträge mehr (statt vier Müll-Kacheln).
  - Test: Kern-Test RMW auf Fixture-Kopie; Prod-Nachweis per API-GET nach Ausführung.

**AC-3:** Given ein Prod-Datenbestand, in den (künftig) ein Test-User-Verzeichnis mit `user.json` geleakt ist / When der Scheduler `runForAllUsers` ausführt / Then wird dieses Konto übersprungen (mit Log-Hinweis) und für keine Job-Art verarbeitet, während echte Konten unverändert verarbeitet werden.
  - Test: Go-Test mit Fixture-Store (test-User + echter User): Job-Callback wird nur für den echten User aufgerufen.

**AC-4:** Given ein Kern-Test ohne `real_data_root`/`live`-Marker, der versucht, unter `<repo>/data/users/` zu schreiben / When die Suite läuft / Then schlägt genau dieser Test mit einem Klartext-Hinweis fehl, und die fünf umgestellten Bestands-Testdateien laufen grün ohne Schreibspuren im Repo-Datenverzeichnis.
  - Test: Wächter-Selbsttest (bewusst schreibender Dummy-Test → FAIL erwartet); die 5 umgestellten Suiten grün; `git status data/` sauber nach Volllauf.

**AC-5:** Given die Playwright-E2E-Konfiguration / When ein Lauf mit Base-URL der Prod-Domain gestartet wird / Then bricht das globale Setup mit einem Klartext-Fehler ab, bevor irgendein Spec Daten anlegen kann; gegen Staging läuft es unverändert an.
  - Test: Setup-Funktion isoliert mit beiden URLs aufrufen (node:test oder Playwright-Setup-Probe): Prod-URL → throw, Staging-URL → ok.

## Known Limitations

- `validator-issue110/` bleibt stehen (aktive Validator-Infrastruktur,
  mtime 2026-07-15) — Nutzungs-Klärung und ggf. Umzug in einen eigenen
  Topf ist ein Folgepunkt, nicht Teil dieser Runde.
- `default/briefings/` und `default/compare_weather_snapshots/` sind
  claude-gregor-owned und wurden nicht inventarisiert — das Script druckt
  ihre Kandidaten im dry-run (als claude-gregor), löscht dort in dieser
  Runde aber nichts.
- Der pytest-Wächter (Teil C) erkennt Schreibspuren am Test-Ende — er
  verhindert den Write nicht physisch (kein chroot); Schutzniveau =
  fail-fast im Kern-Gate, nicht OS-Härtung.

## Out of Scope

- Bereinigung von Staging-Daten (eigener Topf, eigene Konvention)
- systemd-/OS-seitige Schreibrechte-Härtung von data/ (ReadWritePaths
  existiert bereits für Services)
- Klärung/Umzug validator-issue110

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** keine
- **Rationale:** Wiederverwendung etablierter Muster (idempotentes
  Migrations-Script mit dry-run/Backup, bestehendes is_test_user_id-Prädikat,
  bestehende Isolations-Fixture). Kein neues Architekturmuster.

## Test Coverage

### Kern-Tests (deterministisch, echte Fixtures, KEINE Mocks)
- `test_cleanup_prod_testdata_positivliste` — AC-1 (tmp-Baum, Backup,
  Idempotenz, echte Konten unangetastet)
- `test_cleanup_compare_presets_rmw` — AC-2
- Go: `TestRunForAllUsersSkipsTestUsers` — AC-3
- `test_data_root_write_guard` — AC-4 (Wächter-Selbsttest + 5 Suiten grün)
- `test_e2e_prod_url_guard` — AC-5

### Prod-Nachweis (Phase 7, nach Ausführung)
- API-GET Vergleichs-Liste default-User = leer (AC-2)
- `ls data/users/` = nur echte Konten + validator-issue110 (AC-1)
- Scheduler-Status/-Log: ein Lauf ohne Test-User-Verarbeitung (AC-3)

## Changelog

- 2026-07-16: Initial spec erstellt — Issue #1265, Positivliste aus
  Inventur 2026-07-16, vier Guard-Teile (Script, Scheduler, pytest, E2E).
