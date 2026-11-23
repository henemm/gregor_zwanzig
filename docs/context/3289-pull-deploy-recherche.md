# Vorrecherche #3289 (Pull-Deploy), 2026-11-23

- Nachweis heute: nur `staging_gate.py --write-verdict` (aus `/e2e-verify`) schreibt `.claude/e2e_verified/<sha>.json` in den Haupt-Checkout (git-common-dir). Felder: verified_commit, findings[{workflow,url,…}], verified_at, environment, staging_verdict, scope, langs, verdicts{workflow:{…}}. Frische 24 h (`_e2e_paths.STALE_HOURS`). Höchstens 20 Dateien.
- Prüfung: `staging_gate.py --check --expected-commit X` (gate_check :588-801): docs-only-Diff → offen; exakte Datei VERIFIED+frisch+langs; sonst nächster verifizierter Vorfahre (max 40) mit docs-only-Zuwachs.
- `henemm-infra/scripts/deploy-gregor-prod.sh`: flock `/home/hem/.gregor-deploy-prod.lock`, idempotent über `.claude/last_prod_deploy.json` (deployed_commit == origin/main → „bereits ausgeliefert“), WIP-Sicherung, Preflight-Gate (staging_gate --check --expected-commit), Briefing-Fenster-Schutz, Kopfkommentar „NICHT in cron“. Kein Heartbeat/Telegram.
- CI-Job `deploy` (`.github/workflows/ci.yml:565-810`): nach 6 Checks auf main, SSH `gz-deploy`, `scripts/ci_prod_gate.sh` → PROD_GATE=open → deploy-Skript + `prod_selftest.py` per SSH, Telegram. Bei closed: Notice, Deploy über `/70-deploy`.
- Staging-Vorbild: `henemm-infra/scripts/auto-deploy-gregor-staging.sh`, Cron */5 von hem, flock, Heartbeat am Ende.
- `prod_selftest.py`: REPO_DIR fest Server, liest e2e_verified (findings-URLs für Prod-Probe), Exit 0/1.
- GitHub-Commit-Status: bisher nirgends genutzt.
- Feste Pfade: settings.json SessionStart (#3294), `e2e_frontend_browser_gate.py:46` STAGING_ENV_PATH (Override GZ_STAGING_ENV_PATH), `.claude/commands/e2e-verify.md` (staging .env, cd staging), `70-deploy.md:58`, prod_selftest (nur Server), origin_guard PROD_ROOT (fail-safe).
- Mail-Validatoren: IMAP direkt (mail.henemm.com:993) mit `GZ_TEST_IMAP_*` aus `.env` im Arbeitsordner → vom iMac direkt möglich, wenn `.env` dort die Test-Postfach-Daten hat.
