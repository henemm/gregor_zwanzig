---
entity_id: fix_2788_staging_env_rechte
type: bugfix
created: 2026-11-11
updated: 2026-11-11
status: draft
version: "1.0"
workflow: fix-2788-staging-env-rechte
issue: 2788
tags: [staging, e2e, i18n, runbook]
---

# Fix #2788: Staging-E2E-Nutzer-Skript erhält Dateirechte der .env und akzeptiert reinen Benutzernamen

## Approval

- [ ] Approved

## Purpose

Das Skript `scripts/staging_e2e_user_en.py` (legt den englischen Staging-E2E-Nutzer an, Ursprung #2681) darf die Staging-`.env` nicht mehr für den Staging-Dienst unlesbar machen und muss mit dem in Stalwart üblichen reinen Benutzernamen in `GZ_TEST_IMAP_USER` zurechtkommen. Beide Fehler treffen jede Neuanlage des Nutzers (Runbook-Wiederherstellung, neue Staging-Umgebung).

## Source

- **File:** `scripts/staging_e2e_user_en.py`
- **Identifier:** `schreibe_fehlende_schluessel`, `adresse_en`, `main`

> Schicht: Hilfsskript und Runbook für die Staging-Umgebung, kein Frontend, keine Go-API, kein Produktivpfad im Python-Core. Kein Trip/Vergleich-Pendant, keine Nutzerdaten-Bewegung, kein Briefing- oder Alarm-Inhalt (Kanäle nicht betroffen).

## Estimated Scope

- **LoC:** ca. +45/-5 (davon Code ca. 12)
- **Files:** 3
- **Effort:** low

### Affected Files

| File | Change Type | Description |
|------|-------------|-------------|
| `scripts/staging_e2e_user_en.py` | MODIFY | `adresse_en`: ohne `@` Domain `henemm.com` ergänzen, volle Adresse unverändert. `schreibe_fehlende_schluessel`: bestehende Datei nur anhängen (Modus und ACL unangetastet), neue Datei direkt mit 0o600 anlegen, kein nachträgliches `chmod` |
| `tests/tdd/test_staging_e2e_nutzer_en.py` | MODIFY | Neue Tests (siehe Test Plan), echter Lauf von `main()` gegen den vorhandenen Fake-Server |
| `docs/runbooks/staging_e2e_nutzer_en.md` | MODIFY | Satz „Dateirechte 600" ersetzen |

## Scope

- **In Scope:** Rechte-Erhalt beim Anhängen an die Staging-`.env`; neue Datei direkt mit 0o600; Subadresse aus reinem Benutzernamen (Domain `henemm.com`); Tests dazu; Runbook-Satz.
- **Out of Scope:** Domain aus der Konfiguration ableiten (bleibt Projektkonvention `henemm.com`); Änderungen an Staging-Diensten, ACL-Einrichtung oder Produktion; andere Skripte mit eigenem `chmod`.

## Definition of Done

- AC-1 bis AC-6 durch die genannten Tests grün nachgewiesen (ACL-Test läuft, wo `setfacl` verfügbar ist).
- Bestehende Tests in `tests/tdd/test_staging_e2e_nutzer_en.py` bleiben grün.
- Staging-`.env` behält nach dem Deploy Modus `640` und `mask::r--`; Staging-Versand liefert kein HTTP 500.
- Runbook korrigiert.

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `.claude/tools/staging_befehl_pruefen.py` | module (unverändert) | `StagingApi`, `http_transport`; Projektkonvention Domain `henemm.com` (`baue_plus_adresse`) |
| `src/app/config.py:387` | Referenz | gleiche Konvention: Benutzername + `@henemm.com` |
| `docs/specs/modules/i18n_a2_e2e_zweisprachig_2681.md` | Ursprungs-Spec | Annahme 1 zur Subadresse `+en` |
| Staging-Dienste (`gregor-*-staging`) | Verbraucher | lesen dieselbe `.env` per ACL (`user:gregor-staging:r--`) |

## Root Cause

1. **Rechte:** `schreibe_fehlende_schluessel` ruft nach dem Anhängen bedingungslos `os.chmod(pfad, 0o600)`. Bei einer Datei mit POSIX-ACL setzt `chmod` die Gruppenbits, also die ACL-Maske, auf `---`; der Eintrag `user:gregor-staging:r--` wird wirkungslos. Folge: Staging-Dienst `PermissionError: '.env'`, HTTP 500 bei jedem Versand.
2. **Adresse:** `adresse_en` entpackt `split("@", 1)` in zwei Werte. Bei `GZ_TEST_IMAP_USER="gregor-test"` (Stalwart-Konvention, reiner Benutzername) kommt es zu `ValueError` vor der Registrierung. Die bestehenden Tests nutzen nur volle Adressen, daher blieb das unentdeckt.

## Implementation Details

- `adresse_en`: Enthält der Wert kein `@`, wird `@henemm.com` ergänzt (gleiche Konvention wie `config.py:387` und `baue_plus_adresse`); danach unverändert Subadresse `<name>+en@<domain>`. Enthält er `@`, bleibt das Verhalten identisch.
- `schreibe_fehlende_schluessel`: Existiert die Datei, wird nur per Anhängen (`open(..., "a")`) geschrieben; Anhängen erhält Modus und ACL. Existiert sie nicht, wird sie per `os.open(pfad, O_CREAT | O_WRONLY | O_APPEND, 0o600)` angelegt, sodass sie ohne weltlesbares Zeitfenster entsteht. Kein `chmod` mehr.
- Runbook: „Dateirechte 600" ersetzen durch „bestehende Rechte und ACL bleiben erhalten; nur eine neu angelegte Datei bekommt 600".

## Verworfene Alternative

**`chmod 640` statt 600 (Variante aus dem Issue):** verworfen. Es würde bewusst gesetzte fremde Rechte ebenso überschreiben, erzwänge Leserecht für die Gruppe `claude-gregor` und lässt die ACL-Maske weiterhin vom Skript statt vom Betreiber bestimmen. Rechte einer bestehenden Datei gar nicht anzufassen ist strikt besser.

## Expected Behavior

- **Input:** `.env` mit oder ohne vorhandene `GZ_E2E_EN_*`-Schlüssel; `GZ_TEST_IMAP_USER` als reiner Benutzername oder volle Adresse.
- **Output:** Fehlende Schlüssel werden angehängt, Nutzer unter `<name>+en@henemm.com` registriert.
- **Side effects:** Keine Änderung an Modus oder ACL einer bestehenden `.env`.

## Test Plan

Kein Mock-Theater: echter Lauf von `main()` gegen den vorhandenen Fake-Server in `tests/tdd/test_staging_e2e_nutzer_en.py`, Dateimodus per `os.stat`.

### Automated Tests (TDD RED)

- [ ] `test_adresse_en_reiner_benutzername`: GIVEN `gregor-test` WHEN `adresse_en` THEN `gregor-test+en@henemm.com`
- [ ] `test_adresse_en_volle_adresse_unveraendert`: GIVEN `gregor-test@henemm.com` THEN `gregor-test+en@henemm.com` (Rückwärtskompatibilität)
- [ ] `test_bestehende_env_behaelt_modus_640`: GIVEN `.env` mit 0o640 und fehlenden Schlüsseln WHEN `main()` THEN Modus per `os.stat` weiterhin 0o640 und Schlüssel angehängt
- [ ] `test_neue_env_entsteht_mit_600`: GIVEN keine `.env` WHEN `main()` THEN Datei existiert mit 0o600
- [ ] `test_erstanlage_mit_reinem_benutzernamen`: GIVEN Fixture `GZ_TEST_IMAP_USER=gregor-test` WHEN `main()` THEN Fake-Server hat `gregor-test+en@henemm.com` registriert, kein `ValueError`
- [ ] `test_acl_maske_bleibt_erhalten`: GIVEN `.env` mit ACL-Eintrag und Maske `r--` WHEN `main()` THEN `getfacl` zeigt weiterhin `mask::r--`; skip, wenn `setfacl`/`getfacl` nicht verfügbar

## Acceptance Criteria

- **AC-1:** Given eine bestehende `.env` mit Modus 640 und fehlenden E2E-Schlüsseln / When das Skript die fehlenden Schlüssel anhängt / Then hat die Datei danach exakt weiterhin Modus 640 und enthält die neuen Schlüssel.
  - Test: Echter Lauf von `main()` gegen den Fake-Server, Modus per `os.stat` vor und nach dem Lauf verglichen.

- **AC-2:** Given eine bestehende `.env` mit ACL-Eintrag für den Staging-Dienst und Maske `r--` / When das Skript fehlende Schlüssel anhängt / Then bleiben ACL-Eintrag und Maske `r--` unverändert, der Staging-Dienst kann die Datei weiter lesen.
  - Test: Echter Lauf von `main()`, ACL per `getfacl` geprüft; wird übersprungen, wenn `setfacl` nicht verfügbar ist.

- **AC-3:** Given es existiert noch keine `.env` / When das Skript die Schlüssel schreibt / Then entsteht die Datei direkt mit Modus 600, ohne dass sie zwischenzeitlich weltlesbar war.
  - Test: Echter Lauf von `main()` ohne vorhandene Datei, Modus per `os.stat` ist 0o600.

- **AC-4:** Given `GZ_TEST_IMAP_USER` enthält nur den Benutzernamen `gregor-test` / When der Erstanlage-Lauf startet / Then wird die Adresse `gregor-test+en@henemm.com` gebildet und am Fake-Server als englischer Nutzer registriert, ohne Fehler.
  - Test: Echter Lauf von `main()` mit Fixture-Wert `gregor-test`; die registrierte Adresse wird am Fake-Server geprüft.

- **AC-5:** Given `GZ_TEST_IMAP_USER` enthält die volle Adresse `gregor-test@henemm.com` / When das Skript läuft / Then ergibt sich weiterhin `gregor-test+en@henemm.com` (Rückwärtskompatibilität).
  - Test: `adresse_en` und Erstanlage-Lauf mit voller Adresse, registrierte Adresse identisch.

- **AC-6:** Given das Runbook `docs/runbooks/staging_e2e_nutzer_en.md` / When ein Betreiber den Abschnitt zu den Dateirechten liest / Then steht dort nicht mehr „Dateirechte 600", sondern dass bestehende Rechte und ACL erhalten bleiben und nur eine neu angelegte Datei 600 bekommt.
  - Test: `# doc-compliance-test`: Runbook enthält die korrigierte Aussage und nicht mehr „Dateirechte 600" (reine Doku-Korrektur, Verhalten selbst in AC-1 bis AC-3 bewiesen).

## Known Limitations

- ACL-Test läuft nur, wo `setfacl`/`getfacl` vorhanden sind; der CI-taugliche Nachweis ist der Modus-Erhalt (AC-1), da die ACL-Maske den Gruppenbits folgt.
- Domain `henemm.com` ist fest verdrahtet, wie überall im Projekt für Stalwart-Benutzernamen.
- Im Normalbetrieb (Schlüssel vorhanden) läuft der Schreibpfad nicht; der Fehler zeigt sich nur bei Neuanlage.

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** keine
- **Rationale:** Lokale Fehlerkorrektur in einem Hilfsskript, keine Entscheidungsfläche (Kanäle, Provider, Datenmodell, Auth, Deploy-Strategie) berührt.

## Changelog

- 2026-11-11: Initial spec created (Bug #2788)
