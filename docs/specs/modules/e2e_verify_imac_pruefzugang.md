---
entity_id: e2e_verify_imac_pruefzugang
type: feature
created: 2026-11-26
updated: 2026-11-26
status: draft
version: "1.0"
workflow: feat-3423-imac-pruefzugang
tags: [e2e-verify, imac, pruefzugang, doku, issue-3423]
---

# /e2e-verify: Abschnitt „Außerhalb des Servers“ auf den festen Prüfzugang umstellen

## Approval

- [ ] Approved

## Purpose

Eine Sitzung auf dem iMac soll ein Ticket abnehmen können, ohne frei formulierte `ssh henemm '…'`-Befehle auf dem Produktivserver. Der Abschnitt „Außerhalb des Servers“ in `/e2e-verify` nennt deshalb nur noch die fünf festen Prüfbefehle von `ssh henemm-pruefen`. Der bisherige Nachweis-Schritt (`cat >` neben `.claude/hooks/staging_gate.py`) wird vom Hook `bash_gate` als „Direct state file manipulation“ gesperrt (#3402, #3415).

## Source

- **File:** `.claude/commands/e2e-verify.md`
- **Identifier:** Abschnitt „## Außerhalb des Servers (iMac, Cloud)“ (ab ca. Zeile 360)

> Schicht: reine Anleitung, Doku und Doc-Compliance-Tests. Kein Frontend-, Go- oder Python-Produktcode, kein Server-Code.
> Querschnitt: keine Nutzerdaten bewegt, kein Trip/Vergleich-Pendant, keine Kanal-Inhalte betroffen.

## Estimated Scope

- **LoC:** ~60–90
- **Files:** 3
- **Effort:** low

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `ssh henemm-pruefen` (Wrapper `henemm-infra/scripts/imac-pruefzugang.py`, live) | extern | die fünf Prüfbefehle `rev`, `staging-deploy`, `mail-pruefen`, `write-verdict`, `spec-run`; Befehlsformen laut `henemm-infra/docs/imac-pruefzugang.md` |
| `.claude/hooks/staging_gate.py --write-verdict` | Hook (unverändert) | schreibt Nachweis und veröffentlicht Git-Note `refs/notes/e2e-verified` |
| `bash_gate.py` (Plugin) | Hook (unverändert) | Sperrbedingung: `.claude/`-Pfad oder Schreib-Umleitung in der Befehlszeile |
| `tests/test_e2e_nachweis_transport.py` | Test | bestehender AC-9-Test, Helfer `_abschnitt_ausserhalb`, `CMD_E2E` |
| Issues #3402, #3415, henemm-infra#487 | Tracking | werden nach Auslieferung geprüft und geschlossen |

## Scope

### Affected Files

| File | Change Type | Description |
|------|-------------|-------------|
| `.claude/commands/e2e-verify.md` | MODIFY | Abschnitt „Außerhalb des Servers“ neu: Zuordnung Schritt → Prüfbefehl, Einchecken der Abnahme-Dateien, Grenzen, Kontrolle der Note |
| `docs/reference/operations_playbook.md` | MODIFY | Satz „Rückmeldung an die Sitzung“ (Zeile ~323): `ssh henemm` → Prüfzugang `ssh henemm-pruefen` |
| `tests/test_e2e_nachweis_transport.py` | MODIFY | neue Doc-Compliance-Tests; AC-9-Test bleibt unverändert grün |

## Implementation Details

Befehlsformen wörtlich aus der Server-Doku (`henemm-infra/docs/imac-pruefzugang.md`):

- Schritt 1 (Staging-Aktualität): `ssh henemm-pruefen rev gregor-staging` mit dem eigenen Ziel-Commit vergleichen; steht er nicht darauf, `ssh henemm-pruefen staging-deploy`, danach erneut `rev gregor-staging`.
- Schritt 3a (Playwright gegen Staging): `ssh henemm-pruefen spec-run <playwright.*.config.ts> e2e/<name>.spec.ts [weitere Specs] [--lang en]`.
- Schritt 3b (Mail): `ssh henemm-pruefen mail-pruefen <trip|compare|beide> [de|en] [morning|evening]`.
- Schritt 5 (Nachweis): Findings-Datei lokal im Scratchpad ablegen, dann `ssh henemm-pruefen "write-verdict VERIFIED '<Begründung>' --langs de,en" < findings.json`. Verdict-Wort und Begründung sind getrennte Argumente, Begründung höchstens 500 Zeichen, Findings höchstens 1 MB, Scope-Angabe optional (`--scope frontend-only|backend|full-stack|docs-only`).
- Kontrolle bleibt: `git fetch origin '+refs/notes/e2e-verified:refs/notes/e2e-verified'` und `git notes --ref e2e-verified show <ziel-sha>`.

Neu im Abschnitt:

- Abnahme-Config (`frontend/playwright.*.staging.config.ts`) und Abnahme-Spec (`frontend/e2e/*.spec.ts`) müssen im selben PR wie die Änderung eingecheckt sein, damit sie nach Merge und Staging-Deploy im Staging-Checkout liegen; `spec-run` führt nur eingecheckte, unveränderte Dateien aus.
- `spec-run` reicht keine Zusatz-Umgebungsvariablen durch (nur `--lang en`); Abnahme-Specs müssen mit Standardwerten laufen.
- `mail-pruefen` kennt keine weiteren Flags (`--format`, `--timeout`, `--ohne-cleanup`).
- Grenzen: Befehl per Mail-Eingang (`staging_befehl_pruefen.py`), Telegram-Live, `e2e_browser_test.py`, Premium-SMS-Empfang und Staging-API-Seeds deckt der Prüfzugang nicht ab, dafür gilt: Abnahme in einer Server-Sitzung.
- Cloud-Sitzungen haben keinen Prüfzugang (Schlüssel an die iMac-Adresse gebunden); Abnahme macht eine Server- oder iMac-Sitzung.
- Verbot: keine freien `ssh henemm '…'`-Befehle in der Abnahme.
- In den ssh-Zeilen des Abschnitts kommen weder ein `.claude/`-Pfad noch eine Schreib-Umleitung (`>`, `cat >`) vor; die einzige Umleitung ist die Eingabe `< findings.json`.

## Expected Behavior

- **Input:** iMac-Sitzung führt `/e2e-verify` aus und folgt dem Abschnitt „Außerhalb des Servers“.
- **Output:** Alle Abnahmeschritte laufen über `ssh henemm-pruefen`, der Nachweis liegt als Note `e2e-verified` auf `origin`.
- **Side effects:** keine; `bash_gate` blockt die Befehlszeilen nicht mehr (Probe mit allen vier Formen ergab Exit 0).

## Test Plan

### Automated Tests (TDD RED)

Alle als Doc-Compliance-Tests (`# doc-compliance-test`) in `tests/test_e2e_nachweis_transport.py`, ohne Mock, über den vorhandenen Helfer `_abschnitt_ausserhalb`.

- [ ] Test 1: GIVEN Abschnitt WHEN gelesen THEN nennt er `rev gregor-staging`, `staging-deploy`, `spec-run`, `mail-pruefen`, `write-verdict`.
- [ ] Test 2: GIVEN alle Zeilen des Abschnitts mit `ssh ` THEN beginnt jede mit `ssh henemm-pruefen`, keine mit `ssh henemm '` oder `ssh henemm "`.
- [ ] Test 3: GIVEN ssh-Zeilen THEN kein `.claude/`, kein `>` (außer `<`-Eingabe), kein `cat >`.
- [ ] Test 4: GIVEN Abschnitt THEN nennt er Einchecken im selben PR, `--lang en` als einzige Zusatzoption von `spec-run` und die Grenzen (Server-Sitzung, Cloud ohne Prüfzugang).
- [ ] Test 5: GIVEN Playbook THEN steht im Absatz „Rückmeldung an die Sitzung“ `ssh henemm-pruefen`.
- [ ] Test 6: bestehender AC-9-Test bleibt unverändert grün.

## Definition of Done

- [ ] Abschnitt „Außerhalb des Servers“ ordnet jedem Abnahmeschritt einen Prüfbefehl zu, ohne freie `ssh henemm '…'`-Form (AC-1, AC-2)
- [ ] ssh-Zeilen ohne `.claude/`-Pfad und ohne Schreib-Umleitung, Findings nur per `< findings.json` (AC-3)
- [ ] Einchecken von Abnahme-Config/-Spec, Grenzen und Cloud-Hinweis beschrieben, Note-Kontrolle erhalten (AC-4, AC-5, AC-6)
- [ ] Playbook-Satz umgestellt, bestehender AC-9-Test grün (AC-7, AC-8)
- [ ] Doc-Compliance-Tests mit Marker `# doc-compliance-test` grün, Mutations-Gegenprobe rot, alle 6 CI-Checks grün, Adversary-Verdict VERIFIED

## Acceptance Criteria

- **AC-1:** Given eine iMac-Sitzung führt `/e2e-verify` aus / When sie den Abschnitt „Außerhalb des Servers“ liest / Then ist jedem Abnahmeschritt genau ein Prüfbefehl zugeordnet: Schritt 1 `rev gregor-staging` und `staging-deploy`, Schritt 3a `spec-run`, Schritt 3b `mail-pruefen`, Schritt 5 `write-verdict`.
  - Test: Doc-Compliance-Test prüft, dass alle fünf Befehlsnamen im Abschnitt stehen (Test 1).

- **AC-2:** Given der Abschnitt enthält ssh-Beispielzeilen / When man alle Zeilen mit `ssh` prüft / Then beginnt jede mit `ssh henemm-pruefen` und es gibt keine freie Form `ssh henemm '…'` oder `ssh henemm "…"`.
  - Test: Doc-Compliance-Test über alle ssh-Zeilen des Abschnitts (Test 2).

- **AC-3:** Given die ssh-Zeilen des Abschnitts / When man sie auf die Sperrbedingung von `bash_gate` prüft / Then enthalten sie keinen `.claude/`-Pfad und keine Schreib-Umleitung (`>`, `cat >`); die Findings gehen ausschließlich per `< findings.json` als Eingabe.
  - Test: Doc-Compliance-Test über die ssh-Zeilen (Test 3).

- **AC-4:** Given eine Abnahme braucht eine eigene Playwright-Config und Spec / When die Sitzung die Anleitung befolgt / Then steht dort die Pflicht, beide Dateien im selben PR einzuchecken, und der Hinweis, dass `spec-run` keine Zusatz-Umgebungsvariablen durchreicht und nur `--lang en` kennt.
  - Test: Doc-Compliance-Test auf Einchecken, `spec-run` und `--lang en` im Abschnitt (Test 4).

- **AC-5:** Given ein Prüfschritt liegt außerhalb des Prüfzugangs (Befehl per Mail-Eingang, Telegram-Live, Premium-SMS-Empfang, Staging-API-Seeds, `e2e_browser_test.py`) / When die Sitzung den Abschnitt liest / Then wird sie auf eine Server-Sitzung verwiesen, und es steht dort, dass Cloud-Sitzungen keinen Prüfzugang haben.
  - Test: Doc-Compliance-Test auf Grenzen-Absatz und Cloud-Hinweis (Test 4).

- **AC-6:** Given der Nachweis wurde per `write-verdict` geschrieben / When die Sitzung ihn kontrolliert / Then bleibt die Kontrolle der veröffentlichten Note `e2e-verified` auf `origin` (`git fetch … refs/notes/e2e-verified`, `git notes --ref e2e-verified show`) im Abschnitt erhalten.
  - Test: Doc-Compliance-Test auf `refs/notes/e2e-verified` und `git notes --ref e2e-verified` (Test 4).

- **AC-7:** Given das Betriebshandbuch beschreibt die Rückmeldung an die Sitzung / When man den Absatz „Rückmeldung an die Sitzung“ liest / Then steht dort, dass `/e2e-verify` außerhalb des Servers über den Prüfzugang `ssh henemm-pruefen` läuft, nicht mehr über `ssh henemm`.
  - Test: Doc-Compliance-Test auf den Absatz im Playbook (Test 5).

- **AC-8:** Given der bestehende Test AC-9 in `tests/test_e2e_nachweis_transport.py` / When die Testdatei nach der Umstellung läuft / Then bleibt er grün, weil `ssh henemm-pruefen`, `gregor_zwanzig_staging`, `--write-verdict` bzw. `write-verdict` und `e2e-verified` weiterhin im Abschnitt stehen.
  - Test: Lauf der Datei `tests/test_e2e_nachweis_transport.py` (Test 6). Falls `--write-verdict` im Abschnitt entfällt, wird der Test minimal nachgezogen, ohne ihn abzuschwächen.

## Known Limitations

- Der Nachweis eines echten Tickets vom iMac bis zur Auslieferung kann nur eine iMac-Sitzung erbringen. Bis dahin wird #3423 mit klarem Rest-Hinweis geführt; #3402 und #3415 werden nach Auslieferung und iMac-Nachweis geprüft und geschlossen.
- Ein Repo-Test kann den Plugin-Hook `bash_gate` nicht laden (liegt nicht im Repo, nicht in CI); die Sperrbedingung wird deshalb strukturell geprüft.
- Nicht-Ziele: Änderungen am Wrapper (henemm-infra), am Plugin-Hook und an `staging_gate.py`.

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** keine
- **Rationale:** reine Anleitungsänderung; der Prüfzugang selbst ist in henemm-infra spezifiziert, ADR-0129 (Pull-Deploy, Note `e2e-verified`) bleibt unberührt.

## Changelog

- 2026-11-26: Initial spec created (Issue #3423)
