# Context: fix-2624-store-modi-default-acl

## Request Summary
Der Go-Store legt Verzeichnisse mit festem Modus 0755 und Dateien mit 0644 an. Unter einer Default-ACL
(`d:g:gregor-staging-data:rwX`) begrenzt dieser Modus die ACL-Maske auf `r-x` bzw. `r--`; die Gruppe verliert
das Schreibrecht, der Datenrechte-Wächter in `check-gregor20.sh` schlägt an (Herkunft: henemm-infra#331).
Soll: Verzeichnisse `0770`, Dateien `0660`. Epic #2138, Meilenstein „Going Live".

## Related Files

### Go — Produktivstellen im Issue genannt
| Datei:Zeile | Modus | Rolle |
|---|---|---|
| `internal/store/write.go:50` | `Chmod(tmp, 0644)` | atomarer Schreiber, **zentral** für alle Store-Dateien (Kommentar Z.29 nennt „0644" mit) |
| `internal/store/user.go:82,224,237,290,332,386` | `MkdirAll 0755` | `ProvisionUserDirs` u. a. |
| `internal/store/trip.go:291`, `location.go:101`, `group.go:169`, `metric_preset.go:138`, `compare_preset.go:256`, `briefing_subscription.go:61`, `sessions.go:72` | `MkdirAll 0755` | je Entität |
| `internal/provider/openmeteo/cache.go:59,68` | `0755` / `WriteFile 0644` | Wetter-Cache |

### Go — NICHT im Issue, gleiche Klasse (Scope-Entscheidung nötig)
| Datei:Zeile | Modus | Bemerkung |
|---|---|---|
| `internal/store/invite.go:66` | `MkdirAll 0o755` | Einladungen |
| `internal/store/briefing_lock.go:172,175` | `0o755` / `0o600` | Lock-Datei; 0600 macht Maske `---` für die Gruppe |
| `internal/scheduler/user_run_state.go:125,142` | `CreateTemp` + `Chmod 0644` | zweiter atomarer Schreiber (Kopie von write.go) |
| `internal/handler/telegram_connect.go:69` | `CreateTemp` (0600, **kein** Chmod) | Datei bleibt 0600 |
| `internal/provider/openmeteo/calllog.go:67,72` | `0o755` / `0o644` | Drift-Journal |

### Python — NICHT im Issue, gleiche Klasse (Python schreibt in `data/users`, ADR-0031)
Sperrdateien mit `os.open(..., 0o644)`: `src/services/file_lock.py:86`, `forecast_budget.py:465`,
`throttle_store.py:191`, `briefing_slots.py:238,512`, `sms_daily_limit.py:164,225,272`,
`alert_check_state.py:58`, `official_alerts/meteoalarm_budget.py:281`.
`file_lock.atomic_write_json` übernimmt den Modus der Zieldatei (`path.stat().st_mode`), neue Dateien
entstehen über `open(tmp, "w")` (Standard 0666 & umask) — dort ist die Maske unkritisch.
Python-Seite ist durch das Issue nicht abgedeckt; Prozess-Umgebung dort: `UMask=` in systemd, ACL-Maske
wird vom übergebenen Modus bestimmt (Issue-Befund).

## Existing Patterns
- Alle Store-Dateien laufen über `writeFileLogged` → `writeFileAtomic` (`write.go`); **ein** Änderungspunkt für Dateien.
- Verzeichnis-Anlage ist **nicht** zentralisiert: ~15 verstreute `os.MkdirAll(dir, 0755)`.
- Naheliegende Lösung: Konstanten (`DirMode = 0o770`, `FileMode = 0o660`) im Paket `store`, an allen Stellen verwenden.
  Ein Wächter-/Quelltext-Test ist laut Test-Politik verboten (Dateiinhalt-Check) → Nachweis nur über Verhalten (ACL-Test).
- Zwei Kopien des atomaren Schreibers (`store/write.go`, `scheduler/user_run_state.go`) → Pendant beachten.

## Dependencies / Dependents
- Upstream: `os`/Dateisystem, Default-ACL des Verzeichnisses (nicht im Code, vom Betrieb gesetzt — henemm-security#255).
- Downstream: Python-Core liest/schreibt dieselben Dateien als anderer Benutzer; `claude-gregor` (Sweep, Migrationen, Validator);
  `claude-security` (Audit, Prod: Default-ACL `user:claude-security:r-x`); Datenrechte-Wächter `henemm-infra/scripts/check-gregor20.sh`.
- Prod: `/var/lib/gregor/users`, `UMask=0077`, Gruppe `claude-gregor`, `other ---`. Mit 0770/0660 öffnet sich laut Issue nichts weiter
  (`claude-security` bleibt effektiv r-x/r; bei `other` ändert sich nichts).

## Tests
- Rund 382 Testzeilen setzen 0755/0644 für Fixtures — betreffen den Produktivpfad **nicht** und bleiben unverändert.
- Regressionstest (Issue): unter Verzeichnis mit Default-ACL `g:<gruppe>:rwX` anlegen → `mask::rwx`. Braucht `setfacl`/`getfacl`
  und ein ACL-fähiges Dateisystem im Testlauf; alternativ Modus-Parameter group-writable prüfen. **Offen:** ob CI (GitHub Actions)
  ACLs auf dem Test-Tmpdir unterstützt — sonst Skip-Marker mit Begründung, aber dann ist der Kern-Test nicht deterministisch.
  Verhaltensnahe Alternative ohne ACL: `Stat().Mode().Perm()` einer vom Store angelegten Datei/eines Ordners = 0660/0770 unter `umask 0`.

## Existing Specs
- `docs/adr/0031-persistenz-dateibasiert-data-users.md` — Persistenz-Entscheidung (Python schreibt mit)
- `docs/adr/0003-multi-tenant-isolation.md` — Mandantentrennung (Epic #2138)
- `docs/specs/modules/user_scoped_store.md` — Store je Nutzer
- Schema-relevante Datei: `internal/store/store.go`-Familie → Edits lösen den Pre-Snapshot-Hook `data_schema_backup.py` aus (kein Schema, nur Hook-Auslöser).

## Risks & Considerations
- **Sicherheit Prod:** 0770/0660 macht Dateien für die **Gruppe** schreibbar. In Prod ist die Besitzergruppe `claude-gregor`, `other` bleibt `---`
  (Issue prüft das). Die ACL-Maske begrenzt `claude-security` weiter auf r-x. Muss der Selftest nach Deploy messen (`getfacl`).
- **Bestandsdaten:** Nur *neu angelegte* Pfade ändern sich. Bestehende Dateien behalten ihren Modus, bis sie neu geschrieben werden
  (`writeFileAtomic` setzt den Modus bei jedem Schreiben → Dateien wandern von selbst auf 0660). Kein Migrationsschritt nötig; Verzeichnisse bleiben 0755, solange sie existieren (`MkdirAll` ändert bestehende nicht).
- **Python-Sperrdateien (0o644)** bleiben sonst mit Maske `r--` zurück → gleiche Wächter-Meldung bei neuen Konten. Scope-Frage für die Spec.
- **Zweiter Schreiber** `scheduler/user_run_state.go` und `invite.go`/`briefing_lock.go`/`calllog.go` ebenso — sonst bleiben Reste.
- **Akzeptanz auf Staging:** Neu registriertes Konto → für `claude-gregor` beschreibbar, `check-gregor20.sh` grün, `getfacl users/default/sessions.json` zeigt nach Login `mask::rw-`.
  Staging-Datenbestand ist für `hem` nicht lesbar → Messung nur über `sudo -n -u claude-gregor` bzw. als `NOT_MEASURABLE_ON_STAGING` melden, nie PASS erfinden.
- Mehrnutzer-Pflicht: nutzerbezogene Endpunkte unverändert; Test mit zwei Nutzern nicht berührt, aber Konto-Anlage (zwei Konten nacheinander) sinnvoll.

## Analysis

### Type
Bug (Priorität high, Epic #2138 „Going Live"). Ursache gemessen in henemm-infra#331: fester Modus 0755/0644 begrenzt unter Default-ACL die Maske auf r-x/r--.

### Affected Files (with changes)
| File | Change Type | Description |
|------|-------------|-------------|
| `internal/store/modes.go` | CREATE | Konstanten `DirMode=0o770`, `FileMode=0o660` (eine Quelle) |
| `internal/store/write.go` | MODIFY | `Chmod(tmp, FileMode)`, Kommentar Z.29 anpassen |
| `internal/store/{user,trip,location,group,metric_preset,compare_preset,briefing_subscription,sessions,invite}.go` | MODIFY | `MkdirAll(..., DirMode)` |
| `internal/store/briefing_lock.go` | MODIFY | Dir 0770, Lock-Datei 0600→0660 (sonst Maske `---`) |
| `internal/scheduler/user_run_state.go` | MODIFY | zweiter atomarer Schreiber: Chmod 0660 (Pendant zu write.go) |
| `internal/provider/openmeteo/{cache,calllog}.go` | MODIFY | Dir 0770 / Datei 0660 |
| `internal/handler/telegram_connect.go` | MODIFY | `CreateTemp` ohne Chmod bleibt 0600 → Chmod 0660 ergänzen |
| `internal/store/modes_test.go` (o. ä.) | CREATE | Verhaltenstest über echte Store-Anlage |
| Python-Sperrdateien (`src/services/*`, 0o644) | Scope-Frage | siehe Offene Fragen |

### Scope Assessment
- Files: ca. 16 Go-Produktivdateien + 1 Konstanten-Datei + 1–2 Testdateien
- Estimated LoC: +60/-30 (überwiegend Einzeiler); Tests +120
- Risk Level: MEDIUM — mechanisch einfach, aber Rechte-/Sicherheitsfläche in Prod (Gruppe bekommt Schreibrecht). Prod-Prüfung im Issue: `other ---` bleibt, `claude-security` effektiv r-x.

### Technical Approach
1. Paketweite Konstanten im Paket `store`; alle Produktivstellen (auch nicht im Issue genannte gleicher Klasse: invite, briefing_lock, user_run_state, telegram_connect, calllog) darauf umstellen — sonst bleiben Reste, die den Wächter bei neuen Konten erneut auslösen.
2. `provider/openmeteo` und `scheduler` importieren `store` nicht zwingend → eigene Konstanten dort vermeiden: Prüfen, ob ein Import zyklenfrei möglich ist, sonst kleines gemeinsames Paket (z. B. `internal/fsmode`).
3. Test (Kern, deterministisch, ohne Netz): Store in `t.TempDir()` mit `umask 0`-unabhängiger Prüfung — nach `ProvisionUserDirs` und einem Schreibvorgang `Stat().Perm()` == 0770/0660. Zusätzlich ACL-Test mit `setfacl -d -m g::rwX` + `getfacl` (`mask::rwx`), mit `t.Skip` und Begründung wenn `setfacl` fehlt oder Dateisystem keine ACL kann. Zwei Konten nacheinander anlegen.
4. Keine Migration: `writeFileAtomic` setzt den Modus bei jedem Schreiben; bestehende Verzeichnisse behalten 0755 (Infra hat sie repariert).
5. Abnahme Staging: neues Wegwerf-Konto registrieren, Messung per `sudo -n -u claude-gregor` (Staging-Daten für `hem` nicht lesbar), `check-gregor20.sh` grün, `getfacl users/default/sessions.json` → `mask::rw-`. Nicht messbar ⇒ `NOT_MEASURABLE_ON_STAGING`, kein erfundenes PASS. Prod: nach Deploy `getfacl`-Gegenprobe (Selftest).

### Dependencies
Dateisystem + Default-ACL (Betrieb, henemm-security#255); Python-Core schreibt in dieselben Dateien (ADR-0031); Wächter `henemm-infra/scripts/check-gregor20.sh`. Kein Schema-Eingriff (nur Hook `data_schema_backup.py` löst aus).

### Open Questions
- [ ] Python-Sperrdateien (`os.open(..., 0o644)` in 8 Dateien): in diesem Ticket mitziehen? Empfehlung: ja, sonst bleibt dieselbe Wächter-Meldung bei neuen Konten (neue Lock-Dateien unter `data/users`) — alternativ eigenes Ticket, aber PO-Regel „Reste nicht abspalten" spricht für dasselbe Ticket.
- [ ] Zyklus-freie Ablage der Konstanten für `provider/openmeteo` + `scheduler` (technisch, löse ich in der Spec).
