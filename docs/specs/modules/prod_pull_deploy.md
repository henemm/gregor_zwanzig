---
entity_id: prod_pull_deploy
type: feature
created: 2026-11-23
updated: 2026-11-23
status: draft
version: "1.0"
workflow: feat-3289-pull-deploy
tags: [deploy, e2e-nachweis, git-notes, henemm-infra]
---

# Prod-Deploy per Pull (Issue #3289)

## Approval

- [ ] Approved

## Purpose

Ein Gregor-Ticket soll von einer Sitzung ausserhalb des Servers (iMac, Cloud) bis live laufen: Der Server liefert Prod selbst aus, sobald `origin/main` einen gueltigen Staging-Nachweis traegt, und meldet das Ergebnis zurueck. Ohne Nachweis wird nie deployt und nie still uebersprungen.

## Source

- **File:** `.claude/hooks/staging_gate.py`, `scripts/e2e_nachweis_holen.py` (neu), `scripts/ci_prod_gate.sh`; im Repo `henemm-infra`: `scripts/pull-deploy-gregor-prod.sh` (neu)
- **Identifier:** `write_verdict` (Veroeffentlichung der Note), `e2e_nachweis_holen.py main()`, `ci_prod_gate.sh`, `pull-deploy-gregor-prod.sh`

Schicht: reine Betriebs-/Werkzeug-Schicht (Hooks, Skripte, Befehlsdateien, Doku). Kein Frontend, keine Go-API, kein Python-Core, keine Nutzerdaten, keine Kanalinhalte (Mandantentrennung, Trip/Vergleich-Teilung und Vier-Kanal-Regel nicht beruehrt).

## Scope

### Affected Files

Teil 1 — Repo `gregor_zwanzig`:

| File | Change Type | Description |
|------|-------------|-------------|
| `.claude/hooks/staging_gate.py` | MODIFY | `write_verdict` veroeffentlicht den Nachweis nach dem lokalen Schreiben als Git-Note (mit Push-Wiederholung); Fehlschlag => Exit != 0 |
| `scripts/e2e_nachweis_holen.py` | CREATE | Holt die Notes-Ref und legt passende Notes als `.claude/e2e_verified/<sha>.json` ab |
| `scripts/ci_prod_gate.sh` | MODIFY | Ruft vor dem Gate `e2e_nachweis_holen.py` auf |
| `.claude/commands/70-deploy.md` | MODIFY | Abschnitt "ausserhalb des Servers": auf Status `deploy/prod` warten |
| `.claude/commands/e2e-verify.md` | MODIFY | Abschnitt "ausserhalb des Servers": Staging-Schritte per ssh im Staging-Checkout |
| `docs/reference/operations_playbook.md` | MODIFY | Pull-Deploy, Nachweis-Transport, Alarm- und Retry-Regeln |
| `docs/adr/0129-prod-deploy-per-pull-nachweis-als-git-note.md` | CREATE | ADR (siehe Abschnitt ADR); Nummer vor dem Anlegen gegen `origin/main` pruefen |
| `docs/adr/README.md` | MODIFY | Indexzeile fuer das neue ADR (`tests/test_adr_index_drift.py`) |
| `tests/test_e2e_nachweis_transport.py` | CREATE | Wegwerf-Git-Repos mit lokalem Bare-Remote (Vorbild `tests/test_wip_safety.py`, `tests/test_ci_prod_gate.py`) |

Teil 2 — Repo `henemm-infra` (eigener PR dort):

| File | Change Type | Description |
|------|-------------|-------------|
| `scripts/pull-deploy-gregor-prod.sh` | CREATE | Timer-Skript, Cron `*/5`, flock, Heartbeat nach Readiness-Regel, MQ-Alarm einmal je SHA, Commit-Status `deploy/prod` |
| Crontab-Eintrag / Doku | MODIFY | Cron-Zeile und Eintrag in der Infra-Doku, BetterStack-Heartbeat anlegen |
| `scripts/deploy-gregor-prod.sh` | MODIFY | Nur Kopfkommentar: "NICHT in cron" ersetzt durch Verweis auf den Timer |
| `tests/` (Infra-Testordner) | CREATE | Test des Timer-Skripts gegen Wegwerf-Repo, Deploy-/Selftest-Kommandos ueber Umgebungsvariablen gestubbt (Pfade ueberschreibbar) |

Nicht geaendert: `.claude/settings.json`, Gate-Konfiguration, `prod_selftest.py`, `origin_guard.py`, `gate_check` samt Vorfahren-Regel (#1382). Keine Schritte, die eine menschliche Sperre (Override) brauchen.

## Estimated Scope

- Files: 9 (gregor_zwanzig) + 4 (henemm-infra)
- LoC: ca. +520/-20 (Skripte und Hook ca. 280, Tests ca. 200, Doku ca. 60)
- Effort: medium

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `git notes` (`refs/notes/e2e-verified`) | Git-Funktion | Transport des vollen Nachweis-JSON, gebunden an die SHA |
| `gh api` Commit-Status (`deploy/prod`) | GitHub-API | Rueckmeldung des Deploy-Ergebnisses an die Sitzung |
| BetterStack-Heartbeat | Dienst | Ueberwachung des neuen Crons (Readiness-Regel) |
| `/home/hem/claude-mq/send.sh` | Skript | Alarm `high` bei Fehlschlag, einmal je SHA |
| `scripts/ci_prod_gate.sh`, `gate_check` | bestehend | Gate unveraendert, Vorfahren-Regel (40 Commits) unveraendert |
| `henemm-infra/scripts/deploy-gregor-prod.sh` | bestehend | Eigentliches Ausliefern (flock, idempotent ueber `last_prod_deploy.json`) |
| `.claude/hooks/prod_selftest.py` | bestehend | Selbsttest nach dem Deploy, liest `findings`-URLs aus dem Nachweis |
| `.claude/hooks/staging_gate.py` | bestehend | Schreibt den Nachweis lokal (`--write-verdict`) |

## Implementation Details

Ist-Stand: Der Nachweis liegt nur als Datei `.claude/e2e_verified/<sha>.json` im Haupt-Checkout des Servers. Eine Sitzung ausserhalb des Servers kann ihn nicht erzeugen, und der Prod-Deploy ist ein manueller Schritt (`/70-deploy`). Der CI-Job `deploy` sieht beim Merge meist noch keinen Nachweis, weil der erst nach dem Staging-Deploy entsteht.

**E1 — Nachweis-Transport als Git-Note (nicht als Commit-Status).** Das Issue nennt den Commit-Status nur als Beispiel. Gewaehlt wird die Git-Note, weil:
- ein Commit-Status nur 140 Zeichen Beschreibung traegt, Gate und Selbsttest aber das volle JSON brauchen (`langs`, `verdicts`, `findings`);
- Notes an die SHA gebunden und versioniert sind, keinen CI-Lauf ausloesen und dieselbe Vertrauensstufe haben wie heute (wer pushen darf, darf attestieren);
- so kein zweiter Mechanismus mit Drift entsteht: der Server legt die Note als die gewohnte Datei ab, `gate_check`, Vorfahren-Regel und `prod_selftest.py` bleiben unveraendert.
Der Commit-Status bleibt fuer die Rueckrichtung (Deploy-Ergebnis, ein kurzer Wert) die richtige Wahl.

`staging_gate.py --write-verdict`: nach dem lokalen Schreiben Notes-Ref holen, `git notes --ref e2e-verified add -f <sha>`, pushen; bei abgelehntem Push bis zu 3 Versuche mit frischem Fetch. Scheitert die Veroeffentlichung, Exit != 0 mit klarer Meldung. Nur fuer Tests abschaltbar ueber `GZ_E2E_PUBLISH=0`.

`scripts/e2e_nachweis_holen.py <repo>`: holt `refs/notes/e2e-verified`; fuer `origin/main` und dessen 40 letzte Vorfahren wird die Note als `.claude/e2e_verified/<sha>.json` in die geteilte Ablage geschrieben, aber nur wenn `verified_commit` der Note der SHA entspricht (fail-closed: unlesbar, fehlend, anderer Commit => nichts schreiben). Bestehende gleiche Datei bleibt unveraendert. `ci_prod_gate.sh` ruft das Skript vor dem Gate; `GZ_SKIP_E2E_GATE` bleibt dort neutralisiert.

**E2 — Server-Timer (henemm-infra).** `pull-deploy-gregor-prod.sh`, Cron `*/5`, eigener flock:
1. `git fetch`; `origin/main` == `deployed_commit` => Heartbeat, Ende.
2. Sonst `ci_prod_gate.sh`: `closed` => Logzeile "wartet auf Nachweis fuer <sha>", Heartbeat, Ende. Das ist der Normalfall, kein Fehler; der Stand bleibt offen und wird bei jedem Lauf neu geprueft.
3. `open` => `deploy-gregor-prod.sh`, danach `prod_selftest.py`. Erfolg => Commit-Status `deploy/prod` = success am Ziel-Commit (Beschreibung mit Live-SHA) und Heartbeat.
4. Fehlschlag => Commit-Status failure, Alarm `high` per Claude MQ einmal je SHA (entprellt ueber eine Statusdatei), kein Heartbeat, kein erneuter Versuch fuer dieselbe SHA, bis ein neuer Stand auf main liegt oder `GZ_FORCE_REDEPLOY` gesetzt ist.
Doppel-Deploy zwischen CI-Job und Timer ist unschaedlich (beide ueber `deploy-gregor-prod.sh`: flock, idempotent). Heartbeat nur bei fachlich sauberem Lauf (Readiness-Regel aus der globalen CLAUDE.md).

**E3 — Rueckmeldung.** `/70-deploy` Schritt 4 auf einem Rechner ohne Prod-Checkout: nicht selbst deployen, sondern auf den Commit-Status `deploy/prod` am Ziel-Commit warten (`gh api repos/henemm/gregor_zwanzig/commits/<sha>/status`, mit Wecker und eigener Nachpruefung). success = live und Selbsttest Exit 0 => Issue schliessen. failure => mit Befund eskalieren. Auf dem Server bleibt der direkte Weg erlaubt.

**E4 — `/e2e-verify` ausserhalb des Servers.** Die Staging-Werkzeuge brauchen Server-Ressourcen (Staging-`.env`, Kern auf `127.0.0.1:8001`, Staging-Checkout). Ausserhalb laufen diese Schritte per `ssh henemm 'cd ~/gregor_zwanzig_staging && ...'` im Staging-Checkout, der nach dem Staging-Deploy auf dem zu pruefenden Commit steht; `--write-verdict` laeuft dort, die Note macht den Ablageort egal. Die Sitzung misst weiter selbst ("wer attestiert, misst selbst"); keine Test-Postfach-Zugangsdaten auf dem iMac.

Risiken: Notes-Push-Konflikt (Wiederholung mit Fetch); Push-Recht im Staging-Checkout (vor Umsetzung pruefen); Timer darf nie ohne Nachweis deployen.

## Expected Behavior

- **Input:** Ein attestierter Commit auf `origin/main` (Note vorhanden) bzw. ein neuer Stand ohne Nachweis.
- **Output:** Prod laeuft auf dem attestierten Stand; Commit-Status `deploy/prod` zeigt success oder failure; bei Fehlschlag genau ein Alarm je SHA.
- **Side effects:** Notes-Ref `refs/notes/e2e-verified` auf `origin`; Dateien in `.claude/e2e_verified/`; Statusdatei des Timers; Heartbeat-Pings.

## Test Plan

Alle Tests laufen gegen echte Wegwerf-Git-Repos mit lokalem Bare-Remote, ohne Mock-Theater. Das Timer-Skript nutzt echte Git-Operationen; nur die externen Kommandos Deploy, Selftest, MQ, Heartbeat und Status-Aufruf sind ueber Umgebungsvariablen durch protokollierende Stub-Skripte ersetzt.

### Automated Tests (TDD RED)

- [ ] Test 1: GIVEN Wegwerf-Repo mit Bare-Remote und lokalem Nachweis / WHEN `--write-verdict` / THEN Note auf dem Remote gelesen und gleich dem Nachweis-JSON
- [ ] Test 2: GIVEN Remote lehnt den Push ab / WHEN `--write-verdict` / THEN Exit != 0 mit Meldung
- [ ] Test 3: GIVEN Notes fuer passenden, falschen und fehlenden `verified_commit` / WHEN `e2e_nachweis_holen.py` / THEN nur die passende Note wird Datei
- [ ] Test 4: GIVEN geholte Notes / WHEN `gate_check` und Vorfahren-Regel / THEN Ergebnis wie bei lokal geschriebenem Nachweis
- [ ] Test 5: Timer-Laeufe (Nachweis da / fehlt / gleicher Stand / Fehlschlag zweimal) / THEN Deploy-Aufrufe, Status, Alarmzahl und Heartbeats wie in AC-4 bis AC-8
- [ ] Test 6: Mutationsgegenprobe: Verfaelschung von `verified_commit`-Vergleich, Alarm-Entprellung und Heartbeat-Bedingung faengt je ein Test

## Acceptance Criteria

- **AC-1:** Given ein lokal geschriebener Staging-Nachweis fuer einen Commit / When `staging_gate.py --write-verdict` laeuft / Then liegt der volle Nachweis als Git-Note am Commit auf dem Remote, und scheitert das Veroeffentlichen, endet der Befehl mit Exit ungleich 0 und klarer Meldung.
  - Test: Wegwerf-Repo mit Bare-Remote; Note vom Remote lesen und vergleichen; zweiter Lauf mit abgelehntem Push prueft Exit-Code und Meldung.

- **AC-2:** Given Notes mit passendem, abweichendem und fehlendem `verified_commit` auf dem Remote / When `e2e_nachweis_holen.py` laeuft / Then entstehen Dateien in `.claude/e2e_verified/` nur fuer passende Notes (fail-closed), und `gate_check` samt Vorfahren-Regel bewertet sie unveraendert wie lokal geschriebene.
  - Test: drei Commits mit je einer Note-Variante; Ablage-Inhalt pruefen; `gate_check` fuer Commit und Nachfolger aufrufen.

- **AC-3:** Given ein neuer Stand auf `origin/main` mit Note / When der Timer laeuft / Then wird `deploy-gregor-prod.sh` und danach `prod_selftest.py` aufgerufen und der Commit-Status `deploy/prod` am Ziel-Commit auf success mit Live-SHA gesetzt.
  - Test: Wegwerf-Repo, gestubbte Deploy-/Selftest-/Status-Kommandos; Aufrufreihenfolge und Statuswert aus dem Stub-Protokoll.

- **AC-4:** Given ein neuer Stand auf `origin/main` ohne Nachweis / When der Timer laeuft / Then wird nicht deployt, die Logzeile "wartet auf Nachweis" mit SHA erscheint, der Stand bleibt offen und wird beim naechsten Lauf erneut geprueft.
  - Test: zwei Laeufe ohne Note, dann Note veroeffentlichen und dritter Lauf; Deploy-Stub wird erst im dritten Lauf aufgerufen.

- **AC-5:** Given Deploy oder Selbsttest scheitert / When der Timer laeuft / Then steht der Commit-Status `deploy/prod` auf failure und genau ein Alarm der Stufe high geht raus, auch bei weiteren Laeufen auf derselben SHA, ohne erneuten Deploy-Versuch.
  - Test: Selftest-Stub mit Exit 1, drei Laeufe; Alarm-Stub genau einmal, Deploy-Stub genau einmal; mit `GZ_FORCE_REDEPLOY` ein weiterer Versuch.

- **AC-6:** Given `origin/main` entspricht dem zuletzt ausgelieferten Stand / When der Timer laeuft / Then tut er nichts ausser einem Heartbeat-Ping.
  - Test: `deployed_commit` gleich `origin/main`; kein Deploy-, Status- oder Alarm-Aufruf, ein Heartbeat-Aufruf im Stub-Protokoll.

- **AC-7:** Given ein fehlgeschlagener Deploy oder Selbsttest / When der Timer-Lauf endet / Then wird kein Heartbeat gesendet, bei fachlich sauberem Lauf (auch "wartet auf Nachweis") dagegen genau einer.
  - Test: Heartbeat-Stub zaehlt Aufrufe fuer Fehlschlag-, Warte- und Erfolgslauf.

- **AC-8:** Given eine Sitzung ausserhalb des Servers hat gemergt / When sie `/70-deploy` ausfuehrt / Then deployt sie nicht selbst, sondern wartet auf den Status `deploy/prod` am Ziel-Commit und schliesst das Issue erst bei success.
  - Test: Befehlsbeschreibung nach `# doc-compliance-test`-Ausnahme gegen die verbindliche Warte-Reihenfolge; Verhalten selbst durch AC-3/AC-5 belegt.

- **AC-9:** Given eine Sitzung ausserhalb des Servers / When sie `/e2e-verify` ausfuehrt / Then laufen die Staging-Schritte per ssh im Staging-Checkout auf dem zu pruefenden Commit, und der dort geschriebene Nachweis ist per Note auf `origin` sichtbar.
  - Test: Befehlsbeschreibung (doc-compliance) plus AC-1 fuer die Veroeffentlichung; Live-Nachweis im ersten echten Lauf von `/e2e-verify` ausserhalb des Servers.

## Definition of Done

- Alle ACs durch gruene Tests belegt (AC-8/AC-9 Doku-Anteil als `# doc-compliance-test`), Mutationsgegenprobe ohne ueberlebende Verfaelschung.
- Alle 6 CI-Checks gruen; Teil 2 in `henemm-infra` per eigenem PR gemergt und mit dem Skript-Test gruen.
- Cron-Zeile und BetterStack-Heartbeat fuer den Timer eingerichtet; erster echter Lauf ohne Nachweis zeigt "wartet auf Nachweis" ohne Alarm.
- ADR-0129 angelegt und im Index eingetragen; Playbook und beide Befehlsdateien aktualisiert; Kopfkommentar von `deploy-gregor-prod.sh` angepasst.
- `.claude/settings.json` und Gate-Konfiguration unveraendert.

## Known Limitations

- Notes tragen die Vertrauensstufe "Schreibrecht im Repo"; wer pushen darf, kann attestieren (wie bisher).
- Das Staging-Pruefen (`/e2e-verify`) bleibt serverabhaengig und laeuft von aussen nur per ssh.
- Nach einem Fehlschlag gibt es bewusst keinen automatischen Wiederholversuch fuer dieselbe SHA.

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** neu, ADR-0129 "Prod-Deploy per Pull, Nachweis als Git-Note" (Nummer vor dem Anlegen gegen `origin/main` pruefen)
- **Rationale:** Deploy-Strategie ist Entscheidungsflaeche. Bestehende ADRs: ADR-0085 (CI-Deploy nur mit echtem Nachweis), ADR-0098 (Liefer-Workflow), ADR-0099 (autonomer Deploy). Das neue ADR schreibt sie fort, loest keines ab: Hard Gates (Nachweis je Stand, Selbsttest) und Autonomie bleiben, neu sind der Transport (Notes), der Pull-Ausloeser (Timer) und die Rueckmeldung (Commit-Status). Verworfen: Commit-Status als Nachweis-Transport (140 Zeichen), Push-Deploy per SSH aus der Sitzung (Zugang zum Prod-Server auf iMac/Cloud), manueller Ausloeser.

## Changelog

- 2026-11-23: Initial spec created (Issue #3289)
