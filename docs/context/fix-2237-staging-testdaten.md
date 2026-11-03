# Context: fix-2237-staging-testdaten

## Request Summary
#2237 (Sammel-Issue, 11 Einträge aus Triage #1199): Staging-Testdaten bereinigen und die Ursache beheben, warum sie sich wieder ansammeln. Stand der Messung: 2026-11-03.

## Zentraler Befund (gemessen)
Das nächtliche Sweep-Script `henemm-infra/scripts/gregor-staging-sweep.sh` (Cron 04:30, als `claude-gregor`) arbeitet auf `R=/home/hem/gregor_zwanzig_staging/data` (Zeile 25). Der Staging-Dienst läuft aber mit `GZ_DATA_DIR=/var/lib/gregor-staging` (`systemctl cat gregor-python-staging`). Der Sweep meldet täglich "OK" (zuletzt 2026-11-03T04:30:02Z), trifft aber nur den alten Baum mit 3 Nutzern (`default`, `tg-live-e2e`, `validator-issue110`). Der echte Baum hat 122 Nutzerordner.

Messung im echten Baum `/var/lib/gregor-staging/users` (nur per `sudo -n -u claude-gregor` lesbar):
| Messwert | Wert |
|---|---|
| Briefing-JSONs | 84, davon 82 älter als 12 h |
| Location-JSONs | 83 |
| Trip-JSONs | 0 |
| `.lock`-Dateien | 663 |
| Dateien in `compare_weather_snapshots/` | 130 |
| `telegram_chat_id` doppelt | 2 Nutzer teilen `-5369694790` |
| `mail_to=gregor-test@henemm.com` | 5 Konten |
| `mail_to=gregor-staging@henemm.com` | 2 Konten |

Die `.lock`-Dateien (663) stehen nicht in #2237. Der Sweep-Fix muss sie mitnehmen.

## Related Files
| File | Relevance |
|------|-----------|
| `/home/hem/henemm-infra/scripts/gregor-staging-sweep.sh` | falscher Datenpfad `R=` (Z.25); schützt `validator-issue110` und drei Seed-Orte; löscht Briefings/Orte/Trips nach 12 h; Backup per tar vorab |
| Cron-Zeile (crontab von `hem`) | `sudo -u claude-gregor bash -s < ...sweep.sh`, Erfolgsdatei `~/backups/gregor-staging-sweep.success` |
| `src/services/compare_weather_snapshot.py` | `CompareWeatherSnapshotService`: nur `save`/`load`, kein `delete` (B2-16) |
| `internal/handler/compare_preset.go:450` / `internal/store/compare_preset.go:299` | Löschen eines Compare-Presets, räumt Snapshots nicht auf |
| `internal/store/user.go:542` | listet `compare_weather_snapshots/` als Teil des Nutzerbaums (Konto-Löschung) |
| `src/app/loader.py:1256` | `lookup_user_by_chat_id`/`mail_to`-Auflösung (Code laut Triage korrekt) |

## Einträge: Stand
- C1-34 `e2e-cockpit-test.json` (admin): Datei liegt bei `default/briefings`, Ladbarkeit ist in der Analyse zu prüfen.
- B1-50 / B1-54 (Konto `gregor_zwanzig_staging`, Test-Presets): in der Analyse prüfen.
- C3-01 / C3-66 / C3-76 Preset `cp-21e198c1b74020dd`: liegt noch unter `default/briefings`, Orte in der Analyse prüfen.
- C3-18: bestätigt, aber anders als im Issue vermutet: nicht der Ausschluss, sondern der falsche Pfad.
- B2-16: bestätigt (kein Aufräumen beim Löschen).
- B1-23 / C3-65: bestätigt als Daten (2 Nutzer teilen eine chat_id; 5+2 Konten teilen mail_to). Code-Ursache war #2173, nach Epic-Stand geschlossen (Analyse bestätigt).
- C4-06 `E2E-1613-WC-Test`: in der Analyse suchen.

## Existing Patterns
- Sweep: Backup-first, `find -delete` mit Ausschlüssen, Heartbeat nur bei Erfolg (Readiness-Regel aus der globalen CLAUDE.md).
- Daten-Schema-Regel: Read-Modify-Write mit Merge, nie Replace; vor Löschen die Zielobjekte ansehen.

## Dependencies
- Upstream: Staging-Dienst und sein Datenpfad (`GZ_DATA_DIR`), Rechte nur `claude-gregor`.
- Downstream: alle Staging-Verifikationen (`/e2e-verify`, `staging-validator`) und der Prod-Deploy-Gate-Fixture `validator-issue110`, der nie gelöscht werden darf.

## Risks & Considerations
- Der Sweep-Fix löscht erstmals wirklich im echten Baum: Schutzliste muss vorher stimmen (Seed-Orte `e2e-loc-*` bei `admin`/`default`, Fixture `validator-issue110`, Konten und `user.json` nie anfassen). Backup vorab, Probelauf ohne Löschen.
- Der Fixture-Nutzer `validator-issue110` liegt im echten Baum evtl. unter anderem Namen: Schutzliste gegen den echten Baum abgleichen.
- Die Konto-Bereinigung (mail_to/chat_id) berührt Konten: nur eindeutig als Test erkennbare Konten, Entscheidung in der Spec.
- Das Löschen mit Snapshot-Aufräumen ist Go (Handler) + Python (Snapshot-Dienst): ADR-0031 beachten (Python schreibt in `data/users`).
- Zwei-Nutzer-Test für den Snapshot-Cleanup (Mandantentrennung).

## Analysis

### Type
Bug (Daten-Hygiene + Infra-Skript + 1 Code-Lücke). Messung 2026-11-03.

### Zusätzliche Messungen (echter Baum `/var/lib/gregor-staging/users`)
- C4-06: `E2E-1613-WC-Test` steckt in 4 Dateien `default/briefings/{277aa63f,38e358d0,56231a2b,67017042}.json` (Trips liegen im Briefings-Ordner).
- C3-01/66/76: `cp-21e198c1b74020dd.json` (+2 `.bak-*`) liegt unter `default/briefings`, nicht unter `validator-issue110`. Der Sweep (falls auf dem richtigen Pfad) würde es nach 12 h löschen, `default` ist nicht geschützt. Das "geteilte Preset" ist ein Teil-Grund für die Drift.
- C1-34: `default/briefings/e2e-cockpit-test.json` (+ `e2e-mutation-check.json`) vorhanden; Ladbarkeit ist in der Spec per Lade-Test zu prüfen.
- `.lock`-Dateien: nur in `default/briefings` sind es hunderte (`cp-*.json.lock`, `e2e-gz-*.json.lock`). Sie gehören nicht `claude-gregor` (Lesen verweigert) und entstehen beim Schreiben im Store, werden nie entfernt. Das ist eine Code-Ursache (Lock-Datei wird beim Löschen nicht mitgelöscht), nicht nur Sweep.
- Sweep-Muster `*/briefings/*.json` trifft `.json.lock` und `.json.bak-*` nicht.
- `validator-issue110` existiert im echten Baum unter diesem Namen (Schutzliste stimmt).

### Affected Files (with changes)
| File | Change Type | Description |
|------|-------------|-------------|
| `/home/hem/henemm-infra/scripts/gregor-staging-sweep.sh` | MODIFY | `R` auf `/var/lib/gregor-staging` (bzw. `GZ_DATA_DIR`-Auflösung), `.lock`/`.bak-*` mitnehmen, Schutz `cp-21e198c1b74020dd`/Seed, Trockenlauf-Modus, Plausibilitätsprüfung (Pfad existiert, >N Nutzer) damit "OK" nicht mehr lügt |
| `internal/store/compare_preset.go` (+ Handler `compare_preset.go:450`) | MODIFY | Beim Löschen: Snapshots des Presets und Lock-Datei entfernen |
| `src/services/compare_weather_snapshot.py` | MODIFY | `delete(user_id, preset_id)` ergänzen (Mandantentrennung, ADR-0031) |
| `internal/store/*` (Briefing-/Trip-Store) | MODIFY | `.lock` beim Löschen mitlöschen |
| `tests/…`, `internal/store/*_test.go` | CREATE | Zwei-Nutzer-Test Snapshot-Cleanup; Lock-Cleanup |
| Staging-Daten (einmalig, per Skript, Backup vorab) | DATA | Test-Konten/doppelte chat_id/mail_to, Alt-Trips, Orphan-Snapshots, Locks |

### Scope Assessment
- Files: ~6 (2 Repos), LoC ca. +150/-10, Daten-Bereinigung einmalig
- Risk Level: MEDIUM (Sweep löscht erstmals im echten Baum; Gate-Fixture `validator-issue110` und Seed-Orte müssen geschützt bleiben)

### Technical Approach
1. Sweep zuerst: Pfad korrigieren, Trockenlauf, Erfolgsmeldung nur bei plausibler Nutzerzahl; Backup bleibt. Schutzliste um das Validator-Preset erweitern (oder Preset nach `validator-issue110` verlegen; Entscheidung in der Spec, bevorzugt Verlegen = kein Racing zwischen Sessions, C3-76).
2. Code: Preset-Löschen räumt Snapshots ab (B2-16); Store löscht `.lock` mit.
3. Einmal-Bereinigung der Konten: nur eindeutig als Test erkennbare Konten (`e2e*`, `tg-live-e2e` usw.) deduplizieren/löschen; `gregor_zwanzig_staging` mit Kontaktdaten versehen (B1-50), Presets dort aufräumen (B1-54).
4. B1-23/C3-65: Code (#2173) geschlossen, nur Daten.

### Dependencies
Staging-Dienst-Datenpfad `GZ_DATA_DIR`; Rechte nur `claude-gregor`; Infra-Repo-Änderung gehört in `henemm-infra` (Issue dort, Commit-Verweis). Prod-Deploy-Gate hängt an `validator-issue110`.

### Open Questions
- [ ] Preset `cp-21e198c1b74020dd`: nach `validator-issue110` verlegen oder im Sweep schützen? (Empfehlung: verlegen) 
- [ ] Welche der 122 Konten gelten eindeutig als Test (Namensmuster) und dürfen gelöscht werden? Spec legt Muster fest, nichts raten.
