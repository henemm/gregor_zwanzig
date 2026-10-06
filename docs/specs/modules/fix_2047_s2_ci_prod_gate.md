---
entity_id: fix_2047_s2_ci_prod_gate
type: bugfix
created: 2026-10-06
updated: 2026-10-06
status: draft
version: "1.0"
workflow: fix-2047-s2-prod-gate
tags: [ci, deploy, prod-gate, adr-0006]
---

# #2047 Scheibe 2 — Prod-Gate wirksam machen: CI wartet auf den echten Staging-Nachweis

## Approval

- [ ] Approved

## Purpose

Heute stellt sich der CI-Job `deploy` nach einem reinen Erreichbarkeits-Test (Startseite + Health)
selbst einen „VERIFIED"-Nachweis aus und liefert damit nach Produktion aus — das Prod-Gate prüft also
nichts. Diese Spec macht die CI zum reinen Leser: Sie schreibt keinen Nachweis mehr, wartet auf den
echten `/e2e-verify`-Nachweis (Verhaltensprüfung mit echter Mail, Browser, Telegram) für genau den
gemergten Stand und liefert nur dann aus. Fehlt der Nachweis, liefert wie dokumentiert die Session
per `/70-deploy` — die CI bleibt dabei grün und meldet das offen.

## Source

- **File:** `.github/workflows/ci.yml` (Job `deploy`), neu `scripts/ci_wait_for_verdict.sh`
- **Identifier:** Job `deploy`; Shell-Skript `ci_wait_for_verdict.sh <sha>`; Fremd-Repo-Datei
  `/home/hem/henemm-infra/scripts/deploy-gregor-prod.sh` (Idempotenz-Kurzschluss)

## Kontext / Befund

- Der CI-Schritt „Staging-Verdict schreiben (CI smoke)" (`ci.yml` ca. Z.553-583) schreibt in
  dieselbe Datei, die das Prod-Gate liest (`.claude/e2e_verified/<sha>.json`). Das Gate
  (`staging_gate.py gate_check`, ab Z.495) prüft nur `verified_commit`, Verdict-Präfix `VERIFIED`
  und Alter unter 24 h — ein CI-Smoke-Nachweis ist von einem echten nicht zu unterscheiden.
- **Belegt (2026-10-06 am Bestand geprüft):** Echte `/e2e-verify`-Nachweise landen auf dem
  Merge-Commit, also auf `github.sha` (Beispiele `709b2c5`, `2ab82b8`, `1962d32` in
  `.claude/e2e_verified/`). Gleichzeitig zeigt derselbe Bestand, dass CI-Smoke-Verdicts die
  Mehrheit der Nachweisdateien ausmachen — das Gate wurde in der Mehrzahl der Fälle durch die
  Selbst-Attestation geöffnet, nicht durch eine Verhaltensprüfung.
- Der Schritt führt zudem `git reset --hard origin/main` im Hauptordner aus — außerhalb des
  Deploy-Locks (`flock`), im Arbeitsordner interaktiver Sessions und zugleich Produktions-
  Serving-Ordner. Scheibe 1 (`ci_wip_sicherung`) hat nur den Datenverlust abgefedert, nicht die Ursache.
- PO-Vermerk 2026-10-05 (verbindlich): CI schreibt keinen eigenen Nachweis mehr, sie verlangt einen
  echten `/e2e-verify`-Nachweis für den SHA; dazu `deploy.needs` auf alle 6 Ampel-Jobs (C4-71);
  Auto-Deploy bleibt möglich, aber nur mit echtem Nachweis; Doku und Wirklichkeit zur Deckung bringen.
- Henne-Ei: `/e2e-verify` läuft erst nach dem Merge gegen Staging, der CI-Deploy-Job direkt danach.
  Lösung: die CI wartet (Fenster 60 min) auf den Nachweis, statt ihn selbst zu erzeugen.

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `.claude/hooks/staging_gate.py` (`--check --expected-commit`) | Hook (bleibt unverändert) | Einzige Gate-Logik; rohe SHA wird per `rev-parse` aufgelöst (Z.536); docs-only-Durchlass und Ancestor-Relaxierung bleiben wirksam |
| `.claude/hooks/prod_selftest.py` | Hook | Post-Deploy-Selftest, läuft künftig auch im CI-Pfad |
| `/home/hem/henemm-infra/scripts/deploy-gregor-prod.sh` | Skript (Fremd-Repo, sofort live) | Eigentliche Auslieferung; erhält Idempotenz-Kurzschluss |
| `scripts/wip_safety.sh` (Scheibe 1) | Skript | Bleibt als eigenständiges Werkzeug; CI-Aufrufer entfällt |
| `.github/workflows/ci.yml` Jobs `test`, `lint`, `go-test`, `frontend-test`, `svelte-check`, `e2e` | CI-Jobs | Die 6 Ampel-Checks, auf die `deploy` künftig wartet |
| GitHub-Secrets `DEPLOY_SSH_KEY`, `DEPLOY_USER`, `DEPLOY_HOST`, `HENEMM_DEPLOY_*` | Secrets | SSH-Zugang und Telegram-Meldung (unverändert) |
| `docs/adr/0006-no-mocked-tests-e2e-staging.md` | ADR | Prod-Deploy als Hard Gate; neues ADR-0084 ergänzt |
| `tests/test_wip_safety.py` | Test | Veralteter AC-8-Test wird gelöscht |

## Scope

### Affected Files
| File | Change Type | Description |
|------|-------------|-------------|
| `.github/workflows/ci.yml` | MODIFY | `needs` auf 6 Jobs, Verdict-Schritt und Smoke-Test-Verdict ersatzlos entfernen, Warteschritt (ruft Repo-Skript), `concurrency: prod-deploy`, Selftest-Schritt, drei Telegram-Texte |
| `scripts/ci_wait_for_verdict.sh` | CREATE | Poll-Logik als Repo-Skript, drei unterscheidbare Ausgänge |
| `/home/hem/henemm-infra/scripts/deploy-gregor-prod.sh` | MODIFY (Fremd-Repo) | Idempotenz-Kurzschluss innerhalb des flock, Notausgang `GZ_FORCE_REDEPLOY=1` |
| `/home/hem/henemm-infra/tests/test_deploy_gregor_prod_idempotenz.py` | CREATE (Fremd-Repo) | Verhaltenstest des Kurzschlusses gegen Wegwerf-Repo |
| `tests/tdd/test_ci_deploy_gate.py` | CREATE | YAML-Struktur-Wächter (`# doc-compliance-test`) |
| `tests/test_ci_wartet_auf_staging_nachweis.py` | CREATE | Verhaltenstests des Warte-Skripts gegen Wegwerf-Git-Repo |
| `tests/test_wip_safety.py` | MODIFY | Test `test_ci_ruft_die_sicherung_vor_dem_harten_reset_aus_origin_main_auf` löschen |
| `docs/specs/modules/ci_wip_sicherung.md` | MODIFY | Nachtrag „CI-Aufrufer mit #2047 S2 entfallen; AC-8 gegenstandslos" (erst in der Umsetzung, nicht beim Schreiben dieser Spec) |
| `docs/adr/0084-ci-auto-deploy-nur-mit-echtem-e2e-nachweis.md` | CREATE | Neues ADR (ergänzt ADR-0006) |
| `docs/adr/README.md` | MODIFY | Index-Eintrag 0084 (Drift-Test `tests/test_adr_index_drift.py`) |
| `CLAUDE.md`, `.claude/commands/70-deploy.md`, `.claude/commands/e2e-verify.md`, `docs/reference/operations_playbook.md`, `docs/reference/gates_und_ratschen.md` | MODIFY | Doku ↔ Wirklichkeit |

`staging_gate.py` bleibt ausdrücklich unverändert: die Gate-Logik ist korrekt, der Defekt war allein der Selbst-Schreiber.

### Estimated Changes
- Files: 14 (davon 2 im Repo `henemm-infra`)
- LoC: ca. +330/-60 (ci.yml +70/-60, Warte-Skript +70, Deploy-Skript +20, Tests +170; Doku nicht gezählt)

## Implementation Details

**1. `ci.yml`, Job `deploy`** (siehe Datei, Z.510ff):
- `needs: [test, lint, go-test, frontend-test, svelte-check, e2e]`.
- `concurrency: { group: prod-deploy, cancel-in-progress: false }` — ein Abbruch mitten im SSH-Deploy wäre schlimmer als Warten.
- Die Schritte „Staging-Verdict schreiben (CI smoke)" und der damit verbundene Findings-Upload entfallen
  ersatzlos. Damit entfallen zugleich das `git reset --hard` im Hauptordner außerhalb des Locks, die Bindung
  des Nachweises an den Server-HEAD statt an `github.sha` und das Überschreiben echter Nachweise.
  Der bestehende „Warten bis Staging aktuellen Commit hat" bleibt; der reine Smoke-Test ROOT/HEALTH kann
  bleiben, hat aber keine Gate-Wirkung mehr.
- Neuer Schritt „Auf echten Staging-Nachweis warten": per SSH im Hauptordner wird
  `scripts/ci_wait_for_verdict.sh` aufgerufen — **bezogen aus `origin/main`** (`git show origin/main:…`, wie in Scheibe 1), nicht aus dem Server-Arbeitsbaum. Der Schritt übersetzt den Exit-Code in ein Step-Ergebnis (siehe unten) und setzt einen Ausgabewert `outcome` für die Folge-Schritte.
- Folge-Schritte (Deploy, Selftest, Telegram) laufen nur bei `outcome == deliver`.

**2. `scripts/ci_wait_for_verdict.sh <sha>`** (neu, testbar ohne CI):
- Parameter/Env: Repo-Pfad (`GZ_REPO_DIR`, Default Hauptordner), Takt (`GZ_WAIT_INTERVAL`, Default 60 s), Fenster (`GZ_WAIT_WINDOW`, Default 3600 s) — verkürzbar für Tests.
- Je Durchlauf: `git fetch origin`; ist `<sha>` nicht mehr die Spitze von `origin/main` ⇒ Exit 11 (überholt).
  Sonst `python3 .claude/hooks/staging_gate.py --check --expected-commit <sha>`; Exit 0 des Gates ⇒ Exit 0 (Nachweis da).
  Sonst schlafen, bis das Fenster abgelaufen ist ⇒ Exit 10 (kein Nachweis im Fenster).
- Exit 1 bei echtem Fehler (z. B. `git fetch` schlägt fehl, Repo-Pfad ungültig).
- **Kein Reset, kein Checkout, keine Schreibzugriffe** im Hauptordner durch das Skript selbst.
- Festgehalten (geprüft): `staging_gate.py --check --expected-commit` akzeptiert eine rohe SHA (`rev-parse`, Z.536). Im Preflight-Modus schreibt `gate_check` je Aufruf `write_preflight_base` (Z.557) mit denselben Werten wie der Preflight von `deploy-gregor-prod.sh` — wiederholte Polls sind daher unschädlich.
- Ausgang → Verhalten in `ci.yml`: 0 ⇒ ausliefern; 10 ⇒ Job grün, nicht ausgeliefert, Hinweis „Session liefert per /70-deploy"; 11 ⇒ Job grün (neutral), „überholt, neuerer Lauf übernimmt"; 1/andere/SSH-Fehler ⇒ Job rot.

**3. Auslieferung:** `ssh … bash /home/hem/henemm-infra/scripts/deploy-gregor-prod.sh`, danach per SSH
`python3 .claude/hooks/prod_selftest.py` im Hauptordner. Exit ≠ 0 bei einem von beiden ⇒ Job rot.

**4. `deploy-gregor-prod.sh` — Idempotenz (Pflicht, vor dem ci.yml-PR):** Innerhalb des `flock` (nach
Erwerb des Locks, vor dem Dienst-Stopp): steht in `.claude/last_prod_deploy.json` derselbe Commit wie das
Ziel (`origin/main`), dann Meldung „bereits ausgeliefert", Exit 0, keine Dienst-Aktion. Nicht auf
`LOCAL==NEW` stützen (der Serving-Ordner kann auf `origin/main` stehen, ohne dass die Dienste neu gestartet wurden).
Notausgang `GZ_FORCE_REDEPLOY=1` erzwingt die Auslieferung und schreibt einen Eintrag nach
`.claude/deploy-overrides.log` (bestehendes Muster der Notausgänge).

**5. Telegram:** Drei Texte — „ausgeliefert" (`gregor20 deployed: …`), „bereits ausgeliefert" (Idempotenz-Fall) und
„kein Nachweis — nicht ausgeliefert, Session liefert per /70-deploy"; der Fehlschlag-Text bleibt. Commit-Message
weiterhin nur per `env:`, nie per `${{ }}` in den Shell-Text.

**6. Regel-Budget:** Der Warteschritt **ersetzt** die Selbst-Attestation (CI-Smoke-Verdict). Es kommt kein
zusätzliches Gate hinzu, die Zahl der Gates sinkt nicht ab, steigt aber auch nicht — daher kein Prüfdatum nötig.

**7. Rollout-Reihenfolge (zwingend):** (1) Idempotenz in `henemm-infra` einbauen, dort lokal testen,
committen und pushen — selbst ausgeführt, keine Delegation. (2) Erst danach der `ci.yml`-PR in
`gregor_zwanzig` (PR-Liefer-Workflow, 6 grüne Checks). Andernfalls gäbe es ab dem Merge doppelte Neustarts
inkl. Briefing-Fenster-Wartezeit, wenn Session und CI denselben Stand liefern.

## Test Plan

### Automated Tests (TDD RED)

**A. `tests/tdd/test_ci_deploy_gate.py`** (`# doc-compliance-test`, `yaml.safe_load` auf `ci.yml`, Pfad relativ zur Testdatei)
- [ ] Test 1: GIVEN `ci.yml` WHEN Job `deploy` gelesen THEN `needs` enthält alle 6 Ampel-Jobs. Mutation: einen Eintrag aus `needs` entfernen ⇒ rot.
- [ ] Test 2: GIVEN alle Schritte des Jobs `deploy` WHEN `run`-Texte durchsucht THEN kommt `--write-verdict` nirgends vor. Mutation: Verdict-Schritt wieder einfügen ⇒ rot.
- [ ] Test 3: GIVEN Job `deploy` WHEN `run`-Texte durchsucht THEN kommt kein `git reset --hard` vor. Mutation: Reset in einen Schritt einfügen ⇒ rot.
- [ ] Test 4: GIVEN Job `deploy` WHEN Schritte gelesen THEN ruft ein Schritt `ci_wait_for_verdict.sh` auf, steht vor dem Deploy-Schritt, und der Job hat `concurrency.group == prod-deploy` mit `cancel-in-progress: false`. Mutation: Warteschritt entfernen oder `cancel-in-progress` auf true ⇒ rot.

**B. `tests/test_ci_wartet_auf_staging_nachweis.py`** (Verhalten, Wegwerf-Git-Repo mit echtem `origin` als lokales Bare-Repo, Prüfling relativ zur Testdatei aufgelöst; Takt/Fenster auf 1-2 s verkürzt; Gate = echte Nachweisdatei bzw. kleiner Ersatz-Hook mit gleichem Exit-Vertrag)
- [ ] Test 5: GIVEN Nachweisdatei für die Spitze von `origin/main` existiert WHEN das Skript läuft THEN Exit 0. Mutation: Exit-Code-Auswertung des Gates umkehren ⇒ rot.
- [ ] Test 6: GIVEN kein Nachweis WHEN das Fenster abläuft THEN Exit 10 und Laufzeit ≥ Fenster. Mutation: Fenster-Prüfung weglassen (Endlosschleife/Sofort-Exit) ⇒ rot.
- [ ] Test 7: GIVEN `origin/main` ist nach dem Aufruf-SHA weitergezogen WHEN das Skript läuft THEN Exit 11, ohne das Gate zu befragen. Mutation: Spitzen-Prüfung entfernen ⇒ rot.
- [ ] Test 8: GIVEN ein Nachweis erscheint erst im zweiten Durchlauf WHEN das Skript läuft THEN Exit 0 nach dem Warten (Poll wirkt). Mutation: Schleife auf einen Durchlauf kürzen ⇒ rot.
- [ ] Test 9: GIVEN beliebiger Ausgang WHEN das Skript beendet THEN sind HEAD, Branch und Arbeitsbaum des Repos unverändert. Mutation: `git reset --hard`/`checkout` ins Skript einfügen ⇒ rot.
- [ ] Test 10: GIVEN ungültiger Repo-Pfad oder fehlschlagender `git fetch` WHEN das Skript läuft THEN Exit 1 (nicht 10/11). Mutation: Fehlerzweig auf 10 setzen ⇒ rot.

**C. `/home/hem/henemm-infra/tests/test_deploy_gregor_prod_idempotenz.py`** (Verhalten gegen Wegwerf-Repo; **lebt im Repo henemm-infra**, nicht in gregor-CI; läuft lokal vor dem infra-Commit; spricht `/home/hem/henemm-infra` nicht absolut an, sondern löst das Skript relativ zur Testdatei auf; Dienstaufrufe durch Ersatz-Kommandos im PATH, die ihren Aufruf protokollieren; Muster der Nachbardatei `test_deploy_gregor_prod_briefing_window.py`)
- [ ] Test 11: GIVEN `last_prod_deploy.json` nennt den Ziel-Commit WHEN das Skript läuft THEN Exit 0, Meldung „bereits ausgeliefert", kein Dienst-Neustart protokolliert. Mutation (nur auf Kopie des Skripts): Kurzschluss-Bedingung entfernen ⇒ rot.
- [ ] Test 12: GIVEN derselbe Zustand und `GZ_FORCE_REDEPLOY=1` WHEN das Skript läuft THEN wird ausgeliefert (Dienst-Aktion protokolliert) und der Override geloggt. Mutation: Notausgang ignorieren ⇒ rot.
- [ ] Test 13: GIVEN `last_prod_deploy.json` nennt einen älteren Commit WHEN das Skript läuft THEN wird normal ausgeliefert. Mutation: Vergleich auf „immer gleich" ⇒ rot.
- [ ] Test 14: GIVEN der Lock ist von einem anderen Prozess gehalten, der den Zielstand gerade ausliefert WHEN das Skript nach Lock-Erwerb prüft THEN greift der Kurzschluss (Prüfung liegt innerhalb des flock, nicht davor). Mutation: Prüfung vor den Lock verschieben ⇒ rot.

**D. Bestand:** `tests/test_wip_safety.py::test_ci_ruft_die_sicherung_vor_dem_harten_reset_aus_origin_main_auf` wird gelöscht (prüft veraltetes Verhalten, die Zusicherung existiert nicht mehr). Die übrigen `wip_safety`-Verhaltenstests bleiben, `wip_safety.sh` bleibt als Werkzeug.

**Mutations-Gegenprobe:** nur per String-Ersetzung mit externer Sicherungskopie (nie `git checkout/stash/reset`). Mutationen am Deploy-Skript ausschließlich an einer Kopie in einem Wegwerf-Verzeichnis — der Arbeitsbaum von `henemm-infra` ist sofort live.

## Acceptance Criteria

- [ ] **AC-1:** Given die CI-Konfiguration / When der Auslieferungs-Job `deploy` gelesen wird / Then wartet er auf alle sechs Ampel-Prüfungen (test, lint, go-test, frontend-test, svelte-check, e2e), nicht nur auf test und lint.
- [ ] **AC-2:** Given der Auslieferungs-Job der CI / When alle seine Schritte durchsucht werden / Then schreibt kein Schritt mehr einen Nachweis (`--write-verdict`); die CI kann sich die Freigabe nicht mehr selbst ausstellen.
- [ ] **AC-3:** Given der Auslieferungs-Job der CI / When alle seine Schritte durchsucht werden / Then enthält keiner ein `git reset --hard` im Hauptordner; die CI ändert den Arbeitsordner der Sessions und den Produktionsordner nicht mehr außerhalb des Deploy-Skripts.
- [ ] **AC-4:** Given ein Merge nach main mit grüner Ampel / When der Auslieferungs-Job den Warteschritt ausführt / Then ruft er das Repo-Skript `ci_wait_for_verdict.sh` auf (Takt 60 s, Fenster 60 min), und das Skript befragt dieselbe Gate-Logik (`staging_gate.py --check --expected-commit <sha>`) wie das Deploy-Skript — keine zweite Prüfung.
- [ ] **AC-5:** Given für den gemergten Stand (github.sha) liegt ein echter /e2e-verify-Nachweis vor / When das Warte-Skript läuft / Then endet es mit Exit 0 und die CI liefert nach Produktion aus.
- [ ] **AC-6:** Given innerhalb von 60 Minuten erscheint kein Nachweis für den Stand / When das Fenster abläuft / Then endet das Warte-Skript mit Exit 10, der CI-Job bleibt grün, es wird nichts ausgeliefert, und die Meldung nennt: Session liefert per /70-deploy.
- [ ] **AC-7:** Given github.sha ist nicht mehr die Spitze von origin/main (ein neuerer Merge hat überholt) / When das Warte-Skript prüft / Then endet es mit Exit 11, der CI-Job bleibt grün, es wird nichts ausgeliefert, und die Meldung nennt: überholt, der neuere Lauf übernimmt.
- [ ] **AC-8:** Given die drei Ausgänge Nachweis da, kein Nachweis, überholt / When der Job läuft / Then wird er nur rot bei einem echten Fehlschlag: Deploy-Skript endet ≠ 0, Selbsttest endet ≠ 0, SSH-Verbindung scheitert oder das Warte-Skript meldet einen Fehler (Exit 1) — ein normaler Merge ohne Nachweis macht main nicht rot.
- [ ] **AC-9:** Given die CI hat ausgeliefert / When das Deploy-Skript erfolgreich endet / Then läuft anschließend `prod_selftest.py` per SSH, und ein Exit ≠ 0 des Selbsttests lässt den Job rot enden (die Doku-Aussage „Selftest nach Deploy" stimmt damit auch für den CI-Pfad).
- [ ] **AC-10:** Given die Ausgänge ausgeliefert, bereits ausgeliefert, kein Nachweis und fehlgeschlagen / When die Telegram-Meldung gesendet wird / Then passt der Text zum Ausgang (zum Beispiel sagt „kein Nachweis" nie „deployed"), und es wird je Lauf genau eine Meldung gesendet.
- [ ] **AC-11:** Given in `.claude/last_prod_deploy.json` steht bereits der Ziel-Commit von origin/main / When `deploy-gregor-prod.sh` innerhalb des flock prüft / Then meldet es „bereits ausgeliefert", endet mit Exit 0 und startet keinen Dienst neu — Session und CI liefern denselben Stand nicht doppelt.
- [ ] **AC-12:** Given der Zielstand ist schon ausgeliefert / When `GZ_FORCE_REDEPLOY=1` gesetzt ist / Then liefert das Deploy-Skript trotzdem aus und protokolliert den Notausgang in `.claude/deploy-overrides.log`.
- [ ] **AC-13:** Given zwei Merges kurz hintereinander / When beide Auslieferungs-Jobs starten / Then laufen sie nacheinander (`concurrency` Gruppe prod-deploy, `cancel-in-progress: false`), und ein laufender Deploy wird nie abgebrochen.
- [ ] **AC-14:** Given ein Stand, der nur Dokumentation oder Werkzeug-Dateien ändert / When das Gate geprüft wird / Then blockiert er nicht (bestehender Durchlass in `gate_check` bleibt wirksam, `staging_gate.py` ist unverändert) und wird ohne Wartefenster ausgeliefert.
- [ ] **AC-15:** Given das Warte-Skript läuft im Hauptordner / When es beendet ist (egal mit welchem Exit) / Then sind Branch, HEAD und Arbeitsbaum des Hauptordners unverändert — es führt weder Reset noch Checkout aus.
- [ ] **AC-16:** Given die Umsetzung / When die Reihenfolge der Lieferung geprüft wird / Then liegt die Idempotenz in `henemm-infra` zuerst committet und gepusht vor dem ci.yml-PR in gregor_zwanzig (andernfalls doppelte Neustarts ab Merge).
- [ ] **AC-17:** Given die Entscheidung „CI-Auto-Deploy nur mit echtem /e2e-verify-Nachweis" / When die ADRs gelesen werden / Then existiert ADR-0084 als Ergänzung zu ADR-0006, mit Eintrag im ADR-Index, und `tests/test_adr_index_drift.py` ist grün.
- [ ] **AC-18:** Given der alte Test, der die Reihenfolge „Sicherung vor Reset" in ci.yml prüft / When die Umsetzung fertig ist / Then ist er gelöscht (er prüfte veraltetes Verhalten), und `wip_safety.sh` samt seinen Verhaltenstests bleibt bestehen.
- [ ] **AC-19:** Given die Doku (CLAUDE.md, 70-deploy.md, e2e-verify.md Z.69, operations_playbook.md, gates_und_ratschen.md) / When sie mit der CI verglichen wird / Then steht dort überall „6 Checks" statt „5 Checks", der CI-Auto-Deploy mit Warten auf den echten Nachweis ist beschrieben, und der veraltete Dateiname `e2e_verified.json` in e2e-verify.md ist korrigiert.
- [ ] **AC-20:** Given jeder Ausgang des Warte-Skripts und die Idempotenz des Deploy-Skripts / When die Tests laufen / Then ist jeder Ausgang durch einen Verhaltenstest gegen ein Wegwerf-Git-Repo bewacht, und jede der im Testplan genannten Mutationen färbt mindestens einen Test rot.

## Known Limitations

- **Nächtliches Rot-Fenster:** Der `test`-Job ist täglich 22:00-02:30 UTC strukturell rot; ebenso verhindert ein rotes `e2e` den Job. In diesen Fällen wird der CI-Deploy übersprungen. Akzeptiert — der Session-Pfad (`/70-deploy`) liefert weiter, das Gate schützt beide Wege gleich.
- **Normalfall nach der Änderung:** Die Session liefert (wie dokumentiert); die CI ist Sicherheitsnetz für „Nachweis geschrieben, Deploy vergessen oder abgebrochen" und liefert Docs-only-Stände sofort.
- **Kein Herkunftsfeld `source`** im Nachweis: Es würde von derselben Kommandozeile geschrieben, die die CI benutzt hat, könnte Aufrufer nicht unterscheiden und wäre Schein-Schutz. Wirksam ist stattdessen, dass die CI gar nicht mehr schreibt. Alt-Nachweise „CI smoke" verfallen nach 24 h (`STALE_HOURS`).
- **Keine Mail-Validatoren / IMAP in GitHub Actions** (daran ist #1031 gescheitert; es gibt dort keine IMAP-/Bot-Zugangsdaten). Die Verhaltensprüfung bleibt `/e2e-verify` in der Session.
- **Auto-Deploy bleibt** (PO-Vermerk 2026-10-05) — er wird nur an den echten Nachweis gebunden, nicht gestrichen.
- **Poll-Nebenwirkung:** Jeder Poll schreibt `write_preflight_base` mit denselben Werten wie der Preflight des Deploy-Skripts; unschädlich, aber nicht „lesend rein".
- Die Wirksamkeit eines Nachweises hängt weiter davon ab, dass `/e2e-verify` selbst sauber ausgeführt wurde (Schreiber: `e2e-verify.md` und `staging-validator`); das Gate prüft SHA, Verdict-Präfix und Frische, nicht den Inhalt der Findings.

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** ADR-0084 (neu, nächste freie Nummer; 0083 ist auf origin/main bereits vergeben)
- **Rationale:** Der Deploy-Ablauf ändert sich grundsätzlich (Auto-Deploy nur mit echtem Nachweis statt Selbst-Attestation); ADR-0006 nennt das Hard Gate, schweigt aber zum CI-Auto-Prod-Deploy. Das ADR ergänzt ADR-0006 und hält fest: CI schreibt nie einen Nachweis, wartet auf den echten, liefert sonst nicht aus.

## Changelog

- 2026-10-06: Initial spec created
