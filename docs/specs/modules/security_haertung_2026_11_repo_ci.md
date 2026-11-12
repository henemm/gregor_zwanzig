---
entity_id: security_haertung_2026_11_repo_ci
type: module
created: 2026-11-12
updated: 2026-11-12
status: approved
version: "1.0"
tags: [security, ci, secrets, tooling, mail-validator]
---

# Sicherheits-Härtung Repo, CI und Werkzeuge (#2961)

## Approval

- [x] Approved (2026-11-12, PO-Auftrag in #2961: alle Befunde des Reviews 2026-11 ohne Rückfragen beheben)

## Purpose

Das Repository ist öffentlich. Diese Härtung entfernt eingecheckte Zugangsdaten aus dem
Arbeitsstand, verhindert neue (Ignorier-Regeln, Geheimnis-Suche in der CI), schränkt die Rechte
der CI ein und sorgt dafür, dass Werkzeuge Geheimnisse weder in Prozesslisten noch in festen,
für andere lesbaren Pfaden ablegen. Die Mail-Validatoren prüfen nur noch Mails des eigenen
Dienstes und rendern deren HTML ohne Skript und ohne Netzzugriff.

## Source

- **File:** `.gitignore`, `.gitleaks.toml`, `.github/workflows/ci.yml`, `tests/tdd/` (Live-Staging-Tests),
  `scripts/setup-validator-user.sh`, `scripts/telegram_set_webhook.sh`, `scripts/telegram_set_commands.sh`,
  `scripts/seven_hooks.sh`, `.claude/validate-external.sh`, `.claude/hooks/_mail_trust.py` (neu),
  `.claude/hooks/{briefing_mail,email_spec,official_alert_mail,radar_alert_mail}_validator.py`,
  `.claude/commands/{e2e-verify,next-ticket,radar}.md`, `.claude/agents/{staging,external}-validator.md`
- **Identifier:** `_mail_trust.fehler`, `_mail_trust.aus_settings`, CI-Schritte „SSH-Zugang vorbereiten",
  „Geheimnis-Suche (gitleaks, Arbeitsstand)"

> Schicht: nur Werkzeuge, Tests, CI und Doku. Kein Code in `src/`, `api/`, `internal/`, `cmd/`, `frontend/`.

## Estimated Scope

- **LoC:** ~700 (Werkzeuge, Tests, CI, Doku; Override durch den Orchestrator)
- **Files:** ~30
- **Effort:** medium

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `app.config.Settings` | Python | Quelle des erwarteten Dienst-Absenders (`for_testing`, `mail_from`, `inbound_address`, `smtp_user`) und der authserv-id (`mail_server_hostname`) |
| gitleaks 8.30.1 | Werkzeug (CI) | Geheimnis-Suche über den Arbeitsstand |
| GitHub-Secrets `DEPLOY_*` | CI | Deploy; neues optionales Secret `DEPLOY_KNOWN_HOSTS` |

## Implementation Details

```
1. Zugangsdaten: .claude/validator.env.bak entfernt; Live-Staging-Tests lesen Passwörter aus
   der Umgebung (GZ_VALIDATOR_*, GZ_TEST_*, GZ_TDD727_PASS) bzw. .claude/validator.env und
   überspringen ohne sie. storageState pro Lauf in einem 0700-Verzeichnis.
2. .gitignore: .env.* (Ausnahmen: getrackte Vorlagen), .claude/*.env*, Override-Token,
   *.pem, *.key, cookies.txt, **/playwright/.auth/.
3. CI: permissions contents:read; Actions auf Commit-SHA; uv-Version fest; SSH mit
   Host-Key-Prüfung, sobald DEPLOY_KNOWN_HOSTS gesetzt ist (sonst bisheriges Verhalten plus
   ::warning::); Secrets nur per env; gitleaks im Job lint.
4. Mail-Validatoren: Auswahl nur bei genau einem From des Dienst-Absenders und, wenn der
   eigene Mailserver Authentication-Results setzt, DKIM oder SPF pass. Render ohne
   JavaScript, Netzanfragen außer file:/data: werden abgebrochen.
5. Werkzeuge: Geheimnisse an curl per stdin-Konfiguration (-K -) bzw. 0600-Datei; Cookie
   des externen Validators in einer 0600-Datei statt im Prompt; feste /tmp-Pfade durch
   mktemp ersetzt; /next-ticket und /radar laden nur Issues des Eigentümers.
```

## Expected Behavior

- **Input:** Arbeitsstand des Repos, CI-Lauf, Mails im Test-Postfach, Aufrufe der Ops-Skripte
- **Output:** keine Zugangsdaten im Arbeitsstand; CI rot bei neuen Geheimnissen; Validatoren werten nur Dienst-Mails
- **Side effects:** Live-Staging-Tests brauchen ihre Zugangsdaten jetzt aus der Umgebung

## Acceptance Criteria

- **AC-1:** Given der bereinigte Arbeitsstand / When die Geheimnis-Suche der CI (gitleaks mit `.gitleaks.toml`) darüber läuft / Then meldet sie keinen Fund, und eine neu angelegte Datei mit einer Passwort-Zuweisung aus 24–32 Hex-Zeichen macht den Lauf rot.
  - Test: CI-Schritt lokal ausgeführt über einen sauberen Export des Index (grün) und über ein Verzeichnis mit synthetischen Hex-Passwörtern (rot, 4 Funde)

- **AC-2:** Given ein Live-Staging-Test aus `tests/tdd` ohne gesetzte Zugangsdaten-Variablen / When er gesammelt wird / Then wird er mit einem Grund übersprungen, der die fehlende Variable nennt, und kein Passwort steht im Quelltext.
  - Test: Lauf der betroffenen Testdateien ohne Variablen ergibt nur Übersprünge bzw. Abwahl

- **AC-3:** Given der CI-Deploy-Job / When das Secret `DEPLOY_KNOWN_HOSTS` gesetzt ist / Then verbindet SSH mit `StrictHostKeyChecking yes` gegen genau diese Host-Schlüssel; ist es leer, läuft der Deploy wie bisher weiter und der Lauf zeigt eine `::warning::`-Zeile.
  - Test: Schritt „SSH-Zugang vorbereiten" mit Platzhalterwerten ausgeführt (beide Fälle, Dateirechte 0600/0700); bestehende Deploy-Schritt-Tests laufen grün

- **AC-4:** Given die Ops-Skripte für Telegram, seven.io und das Validator-Konto / When sie laufen / Then erscheinen Bot-Token, Secrets, API-Schlüssel und Passwörter nicht in den Argumenten des curl-Prozesses, und der Empfänger erhält dieselbe Anfrage wie vorher.
  - Test: echter curl gegen ein lokales Antwort-Double mit argv-Mitschnitt (seven.io), curl-Stub mit Konfigurationsmitschnitt (Telegram), Loopback-Trockenlauf (Validator-Konto)

- **AC-5:** Given im Test-Postfach liegt nach der echten Dienst-Mail eine jüngere fremde Mail mit denselben Marker-Köpfen / When einer der vier Mail-Validatoren seine Mail wählt / Then prüft er die echte Mail; liegt nur die fremde Mail vor oder meldet der eigene Mailserver DKIM/SPF fail, endet die Auswahl mit einem Fehler, der den Grund nennt.
  - Test: Auswahl je Validator über das IMAP-Double, Regeln der Prüfung, Ableitung des Absenders aus der Versandkonfiguration

- **AC-6:** Given Mail-HTML mit Skript und externem Bild / When der Briefing-Validator es rendert / Then läuft das Skript nicht und keine Anfrage erreicht das Netz.
  - Test: echter Headless-Chromium-Render gegen einen lokalen HTTP-Empfänger (null Anfragen, Tabelle bleibt sichtbar)

## Known Limitations

- Entfernte Werte bleiben in der Git-Historie; wirksam wird die Bereinigung erst mit der
  Rotation der betroffenen Zugänge (Eigentümer/Server).
- Environment `production`, Branch-Bindung der Deploy-Secrets, `DEPLOY_KNOWN_HOSTS` und die
  Begrenzung des SSH-Schlüssels per `command=…,restrict` liegen beim Eigentümer
  (`docs/reference/operations_playbook.md`, „Deploy-Geheimnisse an main binden").
- Ob der Stalwart-Server bei lokal eingelieferten Mails einen eigenen
  `Authentication-Results`-Kopf mit `dkim=none`/`spf=none` setzt, ist nicht belegt; dann
  würde der Validator die Mail verwerfen und der Grund in der Fehlermeldung stehen.
- `frontend/e2e` enthält weiterhin Rückfallwerte für Testpasswörter; außerhalb dieses Pakets.

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** keine
- **Rationale:** Härtung innerhalb bestehender Entscheidungen (ADR-0085 Deploy-Nachweis, ADR-0098 Liefer-Workflow); die Deploy-Logik bleibt unverändert.

## Changelog

- 2026-11-12: Erstfassung (#2961)
