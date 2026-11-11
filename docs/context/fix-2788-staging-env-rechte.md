# Context: fix-2788-staging-env-rechte

## Request Summary
Issue #2788: `scripts/staging_e2e_user_en.py` (legt den englischen Staging-E2E-Nutzer an, #2681)
sperrt beim Erstlauf den Staging-Dienst aus (chmod 600 zerstört die ACL-Maske der Staging-`.env`)
und scheitert vorher schon mit `ValueError`, weil `GZ_TEST_IMAP_USER` ein reiner Benutzername ist.

## Related Files
| File | Relevance |
|------|-----------|
| `scripts/staging_e2e_user_en.py:66-77` | `schreibe_fehlende_schluessel`: hängt an, dann `os.chmod(pfad, 0o600)` (Zeile 77) — Ursache 1 |
| `scripts/staging_e2e_user_en.py:46-49` | `adresse_en`: `split("@", 1)` ohne `@` → `ValueError` — Ursache 2 |
| `scripts/staging_e2e_user_en.py:137-139` | Aufrufer: leitet Mail aus `GZ_TEST_IMAP_USER` ab |
| `tests/tdd/test_staging_e2e_nutzer_en.py` | Bestehende Tests; Fixture schreibt `GZ_TEST_IMAP_USER=gregor-test@henemm.com` (volle Adresse) — deshalb blieb Ursache 2 unentdeckt; `test_adresse_en` (Z. 109) prüft nur volle Adressen |
| `docs/runbooks/staging_e2e_nutzer_en.md:60` | Runbook behauptet „Dateirechte 600" — muss korrigiert werden |
| `docs/specs/modules/i18n_a2_e2e_zweisprachig_2681.md:87,193` | Spec von #2681, Annahme 1 zur Subadresse |
| `.claude/tools/staging_befehl_pruefen.py:81` | `baue_plus_adresse`: festes `@henemm.com` als Domain |
| `src/app/config.py:387-388` | Gleiches Muster: `f"{test_smtp_user}@henemm.com"` (Benutzername ohne Domain) |

## Ist-Zustand Staging-`.env` (gemessen 2026-11-11)
- `-rw-r-----+ hem:claude-gregor`, ACL `user:gregor-staging:r--`, `mask::r--` → per Hand repariert.
- `GZ_TEST_IMAP_USER="gregor-test"` (reiner Benutzername, Stalwart-Konvention).
- `GZ_E2E_EN_*` sind bereits vorhanden (Nutzer existiert) → der Schreibpfad läuft im Normalbetrieb nicht mehr; der Fehler trifft jede Neuanlage (Runbook-Wiederherstellung, neue Staging-Umgebung).

## Existing Patterns
- Domain-Ergänzung für Stalwart-Benutzernamen: fest `henemm.com` (`config.py:387`, `staging_befehl_pruefen.py:82`, `email.py:79 LOCAL_MAIL_DOMAINS`).
- Anhängen per `open("a")` erhält Modus und ACL einer bestehenden Datei; nur `chmod` verändert die Maske.

## Dependencies
- Upstream: `.claude/tools/staging_befehl_pruefen.py` (StagingApi, http_transport).
- Downstream: E2E-Läufe mit englischem Nutzer (`GZ_E2E_EN_*`), `/e2e-verify`, Validatoren mit `--lang en`; Staging-Dienste lesen dieselbe `.env` (gregor-staging per ACL).

## Existing Specs
- `docs/specs/modules/i18n_a2_e2e_zweisprachig_2681.md` (Ursprungs-Spec des Skripts).

## Risks & Considerations
- Kein chmod auf eine bestehende Datei; bei NEU angelegter Datei restriktive Rechte (600) beibehalten — Geheimnisse dürfen nicht weltlesbar entstehen.
- Volle Adresse in `GZ_TEST_IMAP_USER` muss weiter funktionieren (Rückwärtskompatibilität).
- Test darf echte ACL nicht voraussetzen (CI ohne setfacl?) — Modus-Erhalt (z. B. 640) als beobachtbare Wirkung prüfen; ACL-Maske folgt Gruppenbits.
- Runbook-Satz „Dateirechte 600" korrigieren.

## Analysis

### Type
Bug (zwei Ursachen, beide in `scripts/staging_e2e_user_en.py`, gemessen und im Code bestätigt; Analyse inline, da Ursachen bereits am Live-Zustand der Staging-`.env` nachgewiesen und der Umfang zwei Funktionen umfasst)

### Root Cause
1. **Rechte:** `schreibe_fehlende_schluessel` ruft nach dem Anhängen bedingungslos `os.chmod(pfad, 0o600)`. Bei einer Datei mit POSIX-ACL setzt chmod die Gruppenbits = ACL-Maske auf `---`; der Eintrag `user:gregor-staging:r--` wird damit unwirksam → Staging-Dienst `PermissionError: '.env'` → HTTP 500 bei jedem Versand.
2. **Adresse:** `adresse_en` macht `split("@", 1)` und entpackt zwei Werte; `GZ_TEST_IMAP_USER="gregor-test"` (Stalwart-Konvention: reiner Benutzername) → `ValueError` vor der Registrierung. Die Tests nutzen nur volle Adressen, daher unentdeckt.

### Affected Files (with changes)
| File | Change Type | Description |
|------|-------------|-------------|
| `scripts/staging_e2e_user_en.py` | MODIFY | `adresse_en`: ohne `@` Domain `henemm.com` ergänzen (Projektkonvention wie `config.py:387`, `staging_befehl_pruefen.baue_plus_adresse`); volle Adresse unverändert. `schreibe_fehlende_schluessel`: bestehende Datei nur anhängen, Modus/ACL unangetastet; nur eine NEU entstehende Datei mit 0o600 anlegen (per `os.open(..., O_CREAT, 0o600)`, kein nachträgliches chmod) |
| `tests/tdd/test_staging_e2e_nutzer_en.py` | MODIFY | (a) `adresse_en("gregor-test") == "gregor-test+en@henemm.com"`; (b) bestehende Datei mit 0o640 bleibt nach Anhängen 0o640; (c) neu entstehende Datei hat 0o600; (d) Erstanlage-Lauf mit Fixture `GZ_TEST_IMAP_USER=gregor-test` (reiner Benutzername) registriert `gregor-test+en@henemm.com`; (e) wenn `setfacl`/`getfacl` verfügbar: ACL-Maske `r--` bleibt nach Anhängen erhalten (sonst skip) |
| `docs/runbooks/staging_e2e_nutzer_en.md` | MODIFY | „Dateirechte 600" → „bestehende Rechte und ACL bleiben erhalten; nur eine neu angelegte Datei bekommt 600" |

### Scope Assessment
- Files: 3
- Estimated LoC: +~45/-~5 (davon Code ~12)
- Risk Level: LOW — Hilfsskript für Staging, kein Produktivpfad; Normalbetrieb (Schlüssel vorhanden) berührt den Schreibpfad nicht.

### Technical Approach
Beobachtbare Wirkung testen, nicht die Implementierung: Dateimodus per `os.stat` nach echtem Lauf von `main()` gegen den vorhandenen Fake-Server der Testdatei (kein Mock). Die ACL-Maske folgt den Gruppenbits; Modus-Erhalt 640 ist daher der CI-taugliche Nachweis, der echte ACL-Test läuft zusätzlich, wo `setfacl` vorhanden ist. Rückwärtskompatibel: volle Adresse in `GZ_TEST_IMAP_USER` funktioniert weiter. Kein neues Geheimnis-Leck: neue Datei entsteht ohne Zeitfenster direkt mit 600.

Verworfen: „chmod 640" (Issue-Variante) — würde fremde, bewusst gesetzte Rechte ebenso überschreiben und Gruppe `claude-gregor`-Leserecht erzwingen; Erhalt der vorhandenen Rechte ist strikt besser.

### Dependencies
- Upstream: `.claude/tools/staging_befehl_pruefen.py` (unverändert).
- Downstream: `/e2e-verify` mit Nutzer `en`, Validatoren `--lang en`; Staging-Dienste lesen dieselbe `.env`.

### Open Questions
- keine (rein technisch, keine Produktentscheidung)
