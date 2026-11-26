# Context: feat-3423-imac-pruefzugang

## Request Summary

Issue #3423 (Folge aus henemm/henemm-infra#487): `/e2e-verify`, Abschnitt „Außerhalb des
Servers (iMac, Cloud)“, nennt heute frei formulierte `ssh henemm '…'`-Befehle. Der
Nachweis-Schritt (`cat > "$D/f.json"` neben `.claude/hooks/staging_gate.py`) wird vom
PreToolUse-Hook `bash_gate.py` als „Direct state file manipulation“ geblockt (#3402,
#3415); außerdem braucht jeder freie ssh-Befehl auf dem Produktivserver ein PO-Okay.
Seit 26.11.2026 gibt es den festen Prüfzugang `ssh henemm-pruefen <befehl>` (Wrapper
`henemm-infra/scripts/imac-pruefzugang.py`, Doku `henemm-infra/docs/imac-pruefzugang.md`)
mit genau fünf Prüfbefehlen: `rev`, `staging-deploy`, `mail-pruefen`, `write-verdict`
(Findings per stdin), `spec-run` (nur eingecheckte, unveränderte Playwright-Config/Specs).

Ziel: Der Abschnitt nutzt nur noch diese Befehle; Abnahme-Specs/Configs für den
iMac-Weg werden eingecheckt statt ad hoc geschrieben; danach #3402/#3415 schließen.

## Related Files

| Datei | Bezug |
|---|---|
| `.claude/commands/e2e-verify.md:360-393` | Abschnitt „Außerhalb des Servers“ — Hauptänderung |
| `.claude/commands/e2e-verify.md:26-50` | Schritt 1 (Staging-Aktualität, ruft `auto-deploy-gregor-staging.sh` lokal) — iMac-Pendant `staging-deploy` + `rev gregor-staging` |
| `.claude/commands/e2e-verify.md:66-82` | Schritt 3a (Playwright gegen Staging) — iMac-Pendant `spec-run` |
| `.claude/commands/e2e-verify.md:310-335` | Schritt 5 Nachweis — iMac-Pendant `write-verdict … < findings.json` |
| `.claude/commands/70-deploy.md:85-110` | „Schritt 4 außerhalb des Servers“ — wartet auf `deploy/prod`, unverändert; verweist auf `/e2e-verify` Schritt 5 |
| `docs/reference/operations_playbook.md:320-324` | „Rückmeldung an die Sitzung“ — nennt `/e2e-verify läuft dort per ssh henemm` → auf Prüfzugang umstellen |
| `tests/test_e2e_nachweis_transport.py:538-544` | doc-compliance-Test AC-9: Abschnitt muss `ssh henemm`, `gregor_zwanzig_staging`, `--write-verdict`, `e2e-verified`/`Note` enthalten |
| `frontend/playwright.*.staging.config.ts` | eingecheckte Abnahme-Configs (Beispiel `playwright.3037-wsw-abnahme.staging.config.ts`) |

## Existing Patterns

- Nachweis ist die Git-Note `refs/notes/e2e-verified` auf `origin` (Pull-Deploy #3289);
  der Ort der lokalen Datei ist egal. Kontrolle per `git fetch origin '+refs/notes/…'` +
  `git notes --ref e2e-verified show <sha>` — bleibt.
- „Wer attestiert, misst selbst“: Sitzung startet Werkzeuge per ssh und liest das Ergebnis.
- Doc-Compliance-Tests sichern Pflicht-Stichworte in Befehlsdateien (`# doc-compliance-test`).

## Dependencies

- Server-Wrapper `imac-pruefzugang.py` (henemm-infra, live). Grenzen laut Doku:
  - `write-verdict`: Begründung ein Argument ≤500 Zeichen; Verdict-Wort als eigenes Argument
    (`write-verdict VERIFIED '<Begründung>' --langs de,en [--scope …]`), Findings per stdin ≤1 MB.
  - `spec-run`: Config + mindestens eine Spec, eingecheckt und unverändert, `frontend/` sauber;
    keine eigenen Umgebungsvariablen (z. B. `ABNAHME_KONTEXTE` aus #3037 geht NICHT durch),
    nur `--lang en`. Lädt `.env` + `.claude/validator.env` des Staging-Checkouts.
  - `mail-pruefen <trip|compare|beide> [de|en] [morning|evening]` — keine weiteren Flags
    (`--format`, `--timeout`, `--ohne-cleanup` nicht verfügbar).
  - Nicht abgedeckt: `staging_befehl_pruefen.py` (Befehl per Mail-Eingang), Telegram-Live,
    `e2e_browser_test.py`, Premium-SMS-Empfang, Staging-API-Seeds → auf dem Server
    (Server-Sitzung) oder per Vollzugang mit PO-Okay.
- Lokaler Hook `bash_gate.py`: Probe-Aufruf mit den vier neuen Befehlsformen
  (inkl. `ssh henemm-pruefen "write-verdict VERIFIED '…' --langs de,en" < findings.json`)
  ergibt Exit 0 — keine Sperre, weil weder ein `.claude/`-Pfad noch eine Schreib-Umleitung
  vorkommt.

## Existing Specs

- `docs/specs/` zu #3289 (Pull-Deploy, AC-8/AC-9 „außerhalb des Servers“).
- Keine Spec für den Prüfzugang in diesem Repo (liegt in henemm-infra
  `docs/specs/network/imac-pruefzugang.md`).

## Risks

- Doku-Änderung an einem Abnahme-Pfad: falsche Befehlsform ⇒ iMac-Sitzung scheitert erst
  beim Ausliefern. Gegenmittel: Befehlsformen wörtlich aus der Wrapper-Doku, Hook-Probe.
- AC-9-Test muss weiter grün bleiben (`ssh henemm-pruefen` enthält `ssh henemm`).
- Nachweis eines echten Ticket-Durchlaufs vom iMac (Issue Punkt 4) ist nur von einer
  iMac-Sitzung aus erbringbar; diese Server-Sitzung kann die Wrapper-Befehle nicht über
  den eingeschränkten Schlüssel aufrufen (Schlüssel nur am iMac, `from=`-Bindung).

## Analysis

**Type:** Feature (Änderung eines bestehenden Abnahme-Ablaufs; löst die Bugs #3402/#3415 mit).
Score 1 ⇒ Kontext und Analyse in einem Durchgang (keine parallelen Explore-Agenten nötig,
alle betroffenen Stellen sind per gezielter Suche gefunden: `grep -rn "ssh henemm"` über
`.claude/commands`, `.claude/agents`, `docs/reference`).

### Affected Files

| Datei | Change | Inhalt |
|---|---|---|
| `.claude/commands/e2e-verify.md` | MODIFY | Abschnitt „Außerhalb des Servers“ neu: Zuordnung Schritt → Prüfbefehl (`rev gregor-staging`/`staging-deploy` für Schritt 1, `spec-run` für 3a, `mail-pruefen` für 3b, `write-verdict … < findings.json` für 5), Pflicht zum Einchecken von Abnahme-Config/-Spec, Grenzen (was der Prüfzugang nicht kann ⇒ Server-Sitzung), Verbot freier `ssh henemm '…'`-Befehle in der Abnahme |
| `docs/reference/operations_playbook.md` | MODIFY | Satz „`/e2e-verify` läuft dort per `ssh henemm`“ ⇒ Prüfzugang `ssh henemm-pruefen` |
| `tests/test_e2e_nachweis_transport.py` | MODIFY | doc-compliance-Test AC-9 nachziehen; neue Tests: Abschnitt nennt alle fünf Prüfbefehle, enthält keine freie `ssh henemm '…'`-Form, keine Schreib-Umleitung und keinen `.claude/`-Pfad in ssh-Zeilen (genau das Muster, das `bash_gate` als Zustandsmanipulation sperrt) |

### Scope / Risk

~3 Dateien, ~60–90 LoC (überwiegend Anleitungstext + Tests). Risiko niedrig (nur Anleitung,
Doku, Tests — `adversary_dialog.py risk` erwartet „niedrig“). Kein Produkt-Code, kein Server-Code.

### Technical Approach

1. Befehlsformen wörtlich aus `henemm-infra/docs/imac-pruefzugang.md` übernehmen
   (Verdict-Wort und Begründung als getrennte Argumente, Findings-Datei lokal im Scratchpad,
   per `<` übergeben).
2. Probe gegen `bash_gate.py` (Plugin 4.27.0) bereits gemacht: alle vier Formen Exit 0.
   Ein Repo-Test kann den Plugin-Hook nicht laden (liegt nicht im Repo, nicht in CI) ⇒ statt
   dessen sichern die Tests die Sperr-Bedingung strukturell (kein `.claude/`, kein `>`,
   kein `cat >` in ssh-Zeilen des Abschnitts).
3. Grenzen dokumentieren: keine Zusatz-Umgebungsvariablen bei `spec-run` (Abnahme-Specs müssen
   mit Standardwerten laufen), `mail-pruefen` ohne `--format/--timeout/--ohne-cleanup`,
   Befehls-/Telegram-/Premium-SMS-Pfade und Seeds nur auf dem Server.
4. Cloud-Sitzungen: kein Prüfzugang (Schlüssel an iMac gebunden) ⇒ Abnahme übernimmt eine
   Server- oder iMac-Sitzung.
5. Nach Merge/Deploy: #3402 und #3415 mit Verweis schließen; Punkt 4 des Issues (echter
   Ticket-Durchlauf vom iMac) kann diese Server-Sitzung nicht erbringen ⇒ als Kommentar in
   henemm-infra#487 und #3423 festhalten, #3423 bleibt bis dahin offen bzw. wird mit
   klarem Rest-Hinweis geführt (Entscheid in Phase 8).

### Dependencies

`staging_gate.py --write-verdict` (unverändert, läuft im Staging-Checkout), Pull-Deploy
(`refs/notes/e2e-verified`), Wrapper in henemm-infra (live).

### Open Questions

Keine Produktfrage. Technisch offen nur der iMac-Nachweis (Punkt 4), siehe oben.
