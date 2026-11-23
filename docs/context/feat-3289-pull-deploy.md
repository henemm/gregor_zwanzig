# Context + Analyse: feat-3289-pull-deploy (Issue #3289)

Vorrecherche (Fundstellen mit Zeilen): `docs/context/3289-pull-deploy-recherche.md`.

## Ziel
Ein Gregor-Ticket läuft von einer Sitzung außerhalb des Servers (iMac, Cloud) bis live; Prod
liefert der Server selbst aus, sobald `origin/main` einen gültigen Staging-Nachweis trägt.
Ergebnis kommt zurück. Ohne Nachweis kein Deploy, nie still übersprungen.

## Ist-Stand (kurz)
- Nachweis = `.claude/e2e_verified/<sha>.json` im Haupt-Checkout des Servers, nur von
  `staging_gate.py --write-verdict` geschrieben (aus `/e2e-verify`). Volles JSON wird gebraucht:
  `gate_check` (verdict, Frische 24 h, langs, Vorfahren-Regel #1382) und `prod_selftest.py`
  (findings-URLs werden gegen Prod geprobt).
- Prod-Deploy: `henemm-infra/scripts/deploy-gregor-prod.sh` (flock, idempotent über
  `last_prod_deploy.json`, Preflight-Gate) + `prod_selftest.py`. CI-Job `deploy` ruft per SSH
  `scripts/ci_prod_gate.sh` und liefert nur bei `PROD_GATE=open` aus — beim Merge ist der Nachweis
  meist noch nicht da (er entsteht erst nach dem Staging-Deploy), deshalb heute manuell `/70-deploy`.
- Staging-Vorbild: Cron `*/5` `auto-deploy-gregor-staging.sh`, flock, Heartbeat.

## Entscheidungen (Tech Lead)

**E1 — Nachweis-Transport: Git-Notes statt Commit-Status.** Der Nachweis wird zusätzlich als
Git-Note unter `refs/notes/e2e-verified` an den verifizierten Commit gehängt (Inhalt = dasselbe
JSON) und nach `origin` gepusht. Begründung: Ein GitHub-Commit-Status trägt nur 140 Zeichen
Beschreibung; Gate und Selbsttest brauchen das volle JSON (langs, verdicts, findings). Notes sind
an die SHA gebunden, versioniert, lösen keinen CI-Lauf aus, Schreibrecht = Repo-Schreibrecht
(gleiche Vertrauensstufe wie heute: wer pushen darf, darf attestieren). Kein zweiter
Mechanismus, keine Drift. Der Server holt die Notes und legt sie als die gewohnten Dateien ab —
`gate_check`, Vorfahren-Regel und `prod_selftest.py` bleiben unverändert.
- `staging_gate.py --write-verdict` veröffentlicht nach dem lokalen Schreiben die Note
  (fetch der Notes-Ref, `git notes add -f`, push; bei abgelehntem Push bis 3 Versuche neu
  holen). Scheitert die Veröffentlichung, Exit ≠ 0 mit klarer Meldung (sonst glaubt die Sitzung,
  Prod werde ausgeliefert). Abschaltbar nur für Tests (`GZ_E2E_PUBLISH=0`).
- Neues `scripts/e2e_nachweis_holen.py <repo>`: holt `refs/notes/e2e-verified` und schreibt für
  `origin/main` und seine letzten 40 Vorfahren (Fenster der Vorfahren-Regel) die Note als
  `.claude/e2e_verified/<sha>.json` in die geteilte Ablage, nur wenn `verified_commit` == sha
  (fail-closed), bestehende gleiche Datei unverändert lassen.
- `scripts/ci_prod_gate.sh` ruft vor dem Gate `e2e_nachweis_holen.py` auf (CI-Job und Timer
  sehen damit denselben Nachweis).

**E2 — Server-Timer (henemm-infra).** Neues `scripts/pull-deploy-gregor-prod.sh`, Cron `*/5`
(wie Staging): eigenes flock; `git fetch`; ist `origin/main` == `deployed_commit` → Heartbeat,
Ende. Sonst `ci_prod_gate.sh` (holt Notes): `closed` → Logzeile „wartet auf Nachweis für <sha>“,
Heartbeat, Ende (Normalfall, kein Fehler, kein stilles Überspringen: der Stand bleibt offen und
wird bei jedem Lauf neu geprüft). `open` → `deploy-gregor-prod.sh`, danach `prod_selftest.py`.
Erfolg → Commit-Status `deploy/prod` = success am Ziel-Commit (Beschreibung mit Live-SHA) +
Heartbeat. Fehlschlag → Commit-Status failure, Alarm `high` per Claude MQ **einmal je SHA**
(entprellt über Statusdatei), kein Heartbeat, kein erneuter Versuch für dieselbe SHA (neuer Stand
auf main oder `GZ_FORCE_REDEPLOY` setzt zurück). Heartbeat nur bei fachlich sauberem Lauf
(Readiness-Regel). Kopfkommentar „NICHT in cron“ in `deploy-gregor-prod.sh` wird durch den Verweis
auf den Timer ersetzt (das Skript bleibt manuell aufrufbar).

**E3 — Rückmeldung an die Sitzung.** `/70-deploy` Schritt 4 auf einem Rechner ohne
Prod-Checkout: nicht selbst deployen, sondern auf Commit-Status `deploy/prod` am Ziel-Commit
warten (`gh api repos/henemm/gregor_zwanzig/commits/<sha>/status`); success heißt live +
Selbsttest Exit 0 → Issue schließen. Auf dem Server bleibt der direkte Weg erlaubt (schneller,
flock-serialisiert, idempotent).

**E4 — /e2e-verify von anderen Rechnern.** Die Staging-Werkzeuge brauchen Server-Ressourcen
(`/home/hem/gregor_zwanzig_staging/.env`, Kern auf `127.0.0.1:8001`, Staging-Checkout für
`send_gate_test_mails.py`). Außerhalb des Servers laufen diese Schritte per
`ssh henemm 'cd ~/gregor_zwanzig_staging && …'` im Staging-Checkout (steht nach dem
Staging-Deploy auf genau dem zu prüfenden Commit); auch `--write-verdict` läuft dort, die
Veröffentlichung als Note macht den Ablageort egal. Die Sitzung misst also weiterhin selbst
(Regel „wer attestiert, misst selbst“). IMAP (Stalwart, Port 993) wäre direkt erreichbar, wird
aber über denselben Weg genutzt — keine Test-Postfach-Zugangsdaten auf dem iMac.
Feste Pfade: `e2e-verify.md`/`70-deploy.md` bekommen je einen Abschnitt „außerhalb des
Servers“; `e2e_frontend_browser_gate.py` hat schon `GZ_STAGING_ENV_PATH`; `prod_selftest.py`
und `origin_guard.py` (PROD_ROOT) bleiben bewusst serverseitig.

## Risiken
- Notes-Push-Konflikt bei gleichzeitigen Nachweisen → Wiederholung mit frischem Fetch.
- Push-Rechte im Staging-Checkout (hem, gh-Credential) — vor Umsetzung prüfen.
- Doppel-Deploy CI-Job + Timer → beide über `deploy-gregor-prod.sh` (flock, idempotent).
- Timer darf nie ohne Nachweis deployen: `ci_prod_gate.sh` neutralisiert `GZ_SKIP_E2E_GATE`.
- Heartbeat-Pflicht (BetterStack) für den neuen Cron.
