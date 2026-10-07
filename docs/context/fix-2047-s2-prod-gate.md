# Context: fix-2047-s2-prod-gate

## Request Summary

Issue #2047 Scheibe 2: Das Prod-Deploy-Gate soll wirken. Heute schreibt der CI-Job `deploy` sich nach
einem reinen ROOT+HEALTH-Smoke-Test selbst ein `VERIFIED`-Verdict und deployt eine Zeile später damit
nach Produktion. PO-Entscheid 2026-08-21 „Weg A mit Automatisierung“: Verdict nur aus einer Prüfung,
die Verhalten misst; Auto-Deploy bleibt möglich, aber erst nach bestandener Verhaltensprüfung; Doku und
Wirklichkeit zur Deckung bringen. PO-Vermerk 2026-10-05: CI darf keinen eigenen Verdict mehr schreiben,
sie verlangt einen echten `/e2e-verify`-Nachweis für den SHA; dazu C4-71 (`deploy.needs` auf alle 6
Ampel-Checks erweitern). Scheibe 1 (WIP-Sicherung vor dem CI-Reset) ist seit 2026-08-22 live.

## Kernbefund

Der CI-Schritt schreibt **dieselbe Datei**, die das Prod-Gate liest: `.claude/e2e_verified/<sha>.json`.
Das Gate (`staging_gate.py gate_check()`) prüft nur `verified_commit`, Verdict-Präfix `VERIFIED` und
Alter < 24 h. Herkunft und Inhalt der Findings werden nicht geprüft; es gibt kein Feld `source`.
Ein CI-Smoke-Nachweis ist für das Gate ununterscheidbar von einem `/e2e-verify`-Nachweis.

## Related Files

| File | Relevance |
|------|-----------|
| `.github/workflows/ci.yml:510-643` | Job `deploy`: `needs: [test, lint]` (Z.511), `if:` main+push (Z.513), Staging-Poll Z.519-539, Smoke Z.541-551, **Verdict-Schritt Z.553-583** (SSH: `wip_safety.sh`, `git reset --hard origin/main`, `staging_gate.py --write-verdict 'VERIFIED: CI smoke test…'`), Prod-Deploy Z.585-596, Telegram Z.605/624 |
| `.github/workflows/ci.yml:17,65,76,121,169,188` | Die 6 Ampel-Jobs `test`, `go-test`, `frontend-test`, `svelte-check`, `lint`, `e2e` — alle ohne Job-`if`, laufen auch auf main-Push |
| `.claude/hooks/staging_gate.py:330-492` | `--write-verdict`: Datei `<Hauptrepo>/.claude/e2e_verified/<HEAD-sha>.json`, Felder `verified_commit`, `staging_verdict`, `findings[]` (mit `workflow`), `verified_at`, `scope`, `environment`, optional `frontend_browser_gate`; Telegram-Live-Gate Z.354; Frontend-Browser-Gate #1558 Z.265-327; **Merge bei bestehender Datei überschreibt `staging_verdict`/`verified_at`** Z.425-481 |
| `.claude/hooks/staging_gate.py:495-701` | `gate_check()`: `GZ_SKIP_E2E_GATE`, docs-only-Durchlass, Ancestor-Relaxierung (VERIFIED, <24 h, Zuwachs docs-only), Präfix, Frische |
| `.claude/hooks/_e2e_paths.py:15,283` | `STALE_HOURS=24`, `commit_e2e_path` |
| `/home/hem/henemm-infra/scripts/deploy-gregor-prod.sh` | flock `-w 1200` (Z.106-111), Preflight `staging_gate.py --check --expected-commit origin/main` (Z.206-218), zweiter `--check` nach `checkout -f -B` (Z.340-346), Briefing-Fenster-Guard, schreibt `.claude/last_prod_deploy.json` (Z.563-567). **Liegt im Repo henemm-infra** (Arbeitsbaum ist sofort live) |
| `.claude/commands/e2e-verify.md:127-149` | Einziger regulärer Schreiber eines echten Nachweises (nach Browser, IMAP+Mail-Validator, Telegram-Live). Z.69 nennt veraltet `e2e_verified.json` |
| `.claude/agents/staging-validator.md:79-91` | Zweiter regulärer Schreiber |
| `.claude/hooks/prod_selftest.py` | Post-Deploy-Selftest (Attestation für HEAD, Prod-Health, HTTP-Probe je Finding). **Läuft im CI-Pfad nicht** |
| `scripts/wip_safety.sh` | Scheibe 1, läuft vor dem CI-Reset |

## Existing Patterns

- Nachweis = eine Datei je Commit unter `.claude/e2e_verified/`, SHA-gebunden, 24 h frisch, Retention 20.
- Notausgänge per Env (`GZ_SKIP_E2E_GATE`, `GZ_SKIP_FRONTEND_BROWSER_GATE`, `GZ_SKIP_BRIEFING_WINDOW`) mit Log nach `.claude/deploy-overrides.log`.
- Gate-Logik zentral im Repo-Hook `staging_gate.py`; `deploy-gregor-prod.sh` ruft nur `--check`.
- Deploy-Konkurrenz über `flock`; Skript nutzt bewusst `checkout -f -B` statt `reset --hard`.

## Dependencies

- Upstream: GitHub-Secrets `STAGING_BASIC_AUTH`, `DEPLOY_SSH_KEY`, `DEPLOY_USER`, `DEPLOY_HOST`, `HENEMM_DEPLOY_*`; Staging-Auto-Deploy (Cron */5); Staging-`.env` (Telegram-Live-Gate #686/#1031).
- Downstream: jede Session-Lieferung (`/70-deploy` → `deploy-gregor-prod.sh`), `prod_selftest.py` (liest Attestation + `last_prod_deploy.json`), Issue-Close-Regel.

## Existing Specs

- `docs/specs/modules/ci_wip_sicherung.md` — Scheibe 1; Known Limitations Z.183-187 verweisen auf Scheibe 2
- `docs/specs/modules/fix_1382_deploy_gate_evidence.md`, `fix_1776_staging_gate_selfref.md`, `fix_1872_deploy_prod_branch_selfheal.md`, `fix_1197_*`
- Archiv: `issue_521_staging_validator.md`, `issue_1130_expected_commit_gate.md`, `issue_564_post_deploy_selftest.md`
- ADR-0006 (`docs/adr/0006-no-mocked-tests-e2e-staging.md:15-30`): Prod-Deploy als Hard Gate über `verified_commit`/`staging_verdict` — CI-Smoke-Verdict widerspricht dem Geist; Änderung am Deploy-Ablauf ⇒ ADR-Nachtrag oder neues ADR. ADR-0054: `e2e` parallel ohne `needs`. Kein ADR zum CI-Auto-Prod-Deploy.

## Tests

- Bestehend: `tests/tdd/test_staging_gate.py`, `test_deploy_gate_evidence_resolution.py`, `test_staging_gate_verdict_merge.py`, `test_staging_gate_ancestor_scope.py`, `test_e2e_commit_namespacing.py`, `test_e2e_verified_retention.py`, `test_fix_1428_preflight_scope_base.py`, `test_issue_1109_prod_deploy_marker.py`, `test_prod_selftest_564.py`, `test_attestation_findings_typsicher.py`, `test_frontend_browser_gate*.py`, `tests/test_wip_safety.py` (Z.457 liest ci.yml), `tests/unit/test_e2e_positivliste_ratschen_bindung.py` (liest ci.yml).
- **Lücken:** kein Test zu `deploy.needs`, keiner zur Herkunft eines Verdicts.

## Doku, die angepasst werden muss

- `CLAUDE.md` Z.63/106 (Ablauf als Sitzungskette, CI-Auto-Deploy nirgends erwähnt), Z.119/137/139 („6 Checks“), Z.129.
- `.claude/commands/70-deploy.md` Z.24 („5 Checks“ veraltet), Z.40-49, Z.58-64, Z.99, Z.106.
- `docs/reference/operations_playbook.md` Z.53-55, 71-73, 232 („5 Checks“ veraltet), 236-241, 330-341.
- `docs/reference/gates_und_ratschen.md` Z.9-21, 55-58, 396 („5 Checks“ veraltet).

## Risks & Considerations

1. **Henne-Ei:** `/e2e-verify` läuft erst nach dem Merge gegen Staging, der CI-Deploy-Job direkt nach dem Merge. Verlangt die CI einen echten Nachweis, existiert er zum Zeitpunkt des CI-Laufs nicht. Optionen (für die Analyse): CI-Deploy-Job wartet/pollt auf Nachweis · CI-Deploy entfällt und die Session deployt (`/70-deploy` tut das bereits) · CI führt die Verhaltensprüfung selbst aus (Mail-Validatoren + IMAP), was PO-Entscheid 2026-08-21 nahelegt.
2. **Verdict-Überschreibung:** Selbst ein echter `/e2e-verify`-Nachweis wird heute vom späteren CI-Lauf überschrieben (Merge Z.425-481).
3. **Unterscheidbarkeit:** Ohne Herkunftsfeld kann das Gate CI-Smoke und echten Nachweis nicht trennen; Altbestand ohne Feld muss definiert behandelt werden.
4. **Race außerhalb des Locks:** Der CI-Verdict-Schritt macht `git reset --hard` im Hauptordner **außerhalb** des flock — kann mitten in einen Session-Deploy fallen. Wenn der Schritt entfällt, entfällt auch dieses Risiko.
5. **SHA-Bindung an Server-HEAD statt `github.sha`:** Liegt `origin/main` weiter, wird der neuere, ungeprüfte Stand attestiert.
6. **Docs-only-Lieferungen** dürfen nicht blockieren (Durchlass existiert im Gate).
7. **Cross-Repo:** Änderungen an `deploy-gregor-prod.sh` liegen in `henemm-infra` und sind sofort live — selbst ändern (keine Delegation), Mutationen nur in einer Kopie.
8. **`needs` auf alle 6:** `e2e` ist der langsamste Job und nachts strukturell rot (`test`-Job 22:00–02:30 UTC) — Deploy würde in diesem Fenster ausbleiben; muss bewusst entschieden werden.
9. Telegram-Meldungen der CI (Erfolg/Fehlschlag) müssen zum neuen Verhalten passen.

## Analysis

### Type
Bug (Prozess-/Infrastruktur-Defekt): Das Prod-Hard-Gate ist wirkungslos, weil die CI sich den Nachweis selbst ausstellt.

### Verbindlicher Rest-Scope (PO-Vermerk 2026-10-05, ersetzt die Fassung vom 2026-08-21)
1. Die CI schreibt **keinen** Verdict mehr. Sie **verlangt** einen echten `/e2e-verify`-Nachweis für den SHA.
2. C4-71: `deploy.needs` umfasst alle 6 Ampel-Jobs.
3. Auto-Deploy bleibt möglich — aber nur mit echtem Nachweis.
4. Doku ↔ Wirklichkeit zur Deckung bringen.

**Bewusst NICHT im Scope:** Mail-Validatoren/IMAP in GitHub Actions ausführen (daran ist #1031 gescheitert; IMAP-/Bot-Zugangsdaten
existieren in Actions nicht). Ebenso nicht: CI-Auto-Deploy streichen (widerspräche „Auto-Deploy bleibt möglich").
Kein Herkunftsfeld `source` im Nachweis: es würde von derselben CLI geschrieben, die die CI benutzt hat — es kann
Aufrufer nicht unterscheiden und wäre Schein-Schutz. Alt-Nachweise „CI smoke" verfallen ohnehin nach 24 h (`STALE_HOURS`).

### Technischer Ansatz (Empfehlung)
**„Warten auf echten Nachweis, dann idempotent ausliefern."**

1. **`ci.yml`, Job `deploy`:**
   - `needs: [test, lint, go-test, frontend-test, svelte-check, e2e]` (C4-71).
   - Schritt „Staging-Verdict schreiben (CI smoke)" **ersatzlos löschen**. Damit entfallen zugleich: Selbst-Attestation,
     `git reset --hard` im Serving-Ordner außerhalb des flock (Risiko 4), SHA-Bindung an Server-HEAD statt `github.sha`
     (Risiko 5), Code-Wechsel unter laufendem `gregor-python`, Überschreiben echter Nachweise durch den Merge-Pfad (Risiko 2).
   - Neuer Schritt „Auf echten Staging-Nachweis warten": per SSH, im Hauptordner, `git fetch` + `staging_gate.py --check
     --expected-commit <github.sha>`, Takt 60 s, Fenster 60 min. Nutzt dieselbe Gate-Logik wie das Deploy-Skript
     (inkl. docs-only-Durchlass und Ancestor-Relaxierung) — keine zweite Gate-Implementierung.
     *Nebenwirkung geprüft:* `gate_check` schreibt im Preflight-Modus `write_preflight_base(target, base=live-HEAD)`
     (`staging_gate.py:557`). Bei jedem Poll dieselben Werte, gleiches Verhalten wie der Preflight von
     `deploy-gregor-prod.sh` → unschädlich; in der Spec festhalten.
   - **Drei neutrale/grüne Ausgänge, kein Rot im Normalfall:**
     (a) Nachweis da → deployen; (b) kein Nachweis im Fenster → Exit 0 mit Hinweis „nicht ausgeliefert, Session
     liefert per `/70-deploy`"; (c) `github.sha` ist nicht mehr die Spitze von `origin/main` (überholter Merge) → Exit 0
     „überholt, der neuere Lauf übernimmt". Sonst würde `main` nach jedem normalen Merge rot und Drive-to-green feuerte
     dauernd. Rot nur bei echtem Fehlschlag (Deploy-Skript ≠ 0, Selftest ≠ 0, SSH-Fehler).
   - `concurrency: group: prod-deploy, cancel-in-progress: false` — Abbruch mitten im SSH-Deploy wäre schlimmer als Warten.
   - Nach erfolgreichem CI-Deploy `prod_selftest.py` per SSH ausführen (heute läuft er im CI-Pfad nie → Doku-Lüge).
   - Telegram: drei Texte — „ausgeliefert", „bereits ausgeliefert", „kein Nachweis – nicht ausgeliefert"; Fehlschlag-Text bleibt.
2. **`henemm-infra/scripts/deploy-gregor-prod.sh` — Idempotenz (Pflicht):** Heute stoppt/startet das Skript die Dienste
   auch, wenn der Code schon auf `origin/main` steht (Z.328 läuft weiter). Sobald der Nachweis erscheint, liefern Session
   (`/70-deploy`) und CI denselben SHA → doppelter Neustart inkl. Briefing-Fenster-Wartezeit. Kurzschluss **innerhalb des
   flock**: `.claude/last_prod_deploy.json`-Commit == `origin/main` ⇒ „bereits ausgeliefert", Exit 0, keine Dienst-Aktion.
   Nicht auf `LOCAL==NEW` stützen (Serving-Ordner kann auf `origin/main` stehen, ohne dass Dienste neu gestartet wurden).
   Mit Notausgang (z. B. `GZ_FORCE_REDEPLOY=1`) für bewusste Neu-Auslieferung. Repo henemm-infra, Arbeitsbaum sofort live
   → selbst ändern, Mutationen nur in einer Kopie.
3. **Scheibe-1-Folgen:** Mit dem Verdict-Schritt entfällt der einzige Aufrufer von `scripts/wip_safety.sh`.
   Skript bleibt als eigenständig dokumentiertes Werkzeug (Playbook Z.366) samt Verhaltenstests; der doc-compliance-Test
   `tests/test_wip_safety.py::test_ci_ruft_die_sicherung_vor_dem_harten_reset_aus_origin_main_auf` (AC-8) prüft
   veraltetes Verhalten → löschen. `docs/specs/modules/ci_wip_sicherung.md`: Nachtrag „CI-Aufrufer mit #2047 S2 entfallen".
4. **Wächter-Test (neu, struktureller YAML-Check, `# doc-compliance-test`):** `ci.yml` per `yaml.safe_load` —
   `deploy.needs ⊇` die 6 Ampel-Jobs; kein Schritt im Job ruft `--write-verdict`; kein `git reset --hard` im Job.
   Mutations-Gegenprobe: Verdict-Schritt wieder einfügen / einen `needs`-Eintrag entfernen → rot.
   Verhaltens-Tests für das Deploy-Skript-Kurzschluss gegen Wegwerf-Repo (Muster wie `test_wip_safety.py`).
5. **ADR:** Nachtrag zu ADR-0006 (oder neues ADR) „CI-Auto-Deploy nur mit echtem `/e2e-verify`-Nachweis" — Index-Drift-Test beachten.
6. **Doku:** CLAUDE.md (Ablauf + „6 Checks"), `.claude/commands/70-deploy.md`, `operations_playbook.md`,
   `gates_und_ratschen.md` (jeweils „5 Checks" → 6, CI-Auto-Deploy beschreiben), `e2e-verify.md:69` (veralteter Dateiname).

### Affected Files (with changes)
| File | Change Type | Description |
|------|-------------|-------------|
| `.github/workflows/ci.yml` | MODIFY | `needs` auf 6, Verdict-Schritt weg, Warte-Schritt, concurrency, Selftest, 3 Telegram-Texte |
| `/home/hem/henemm-infra/scripts/deploy-gregor-prod.sh` | MODIFY (Fremd-Repo) | Idempotenz-Kurzschluss im flock |
| `tests/tdd/test_ci_deploy_gate.py` (Name nach Verhalten) | CREATE | YAML-Struktur-Wächter |
| `tests/…/test_prod_deploy_idempotenz.py` | CREATE | Kurzschluss gegen Wegwerf-Repo |
| `tests/test_wip_safety.py` | MODIFY | AC-8-Test löschen |
| `docs/specs/modules/ci_wip_sicherung.md` | MODIFY | Nachtrag |
| `docs/adr/0006-…` bzw. neues ADR + `docs/adr/README.md` | MODIFY/CREATE | Entscheidung festhalten |
| CLAUDE.md, `70-deploy.md`, `e2e-verify.md`, `operations_playbook.md`, `gates_und_ratschen.md` | MODIFY | Doku ↔ Wirklichkeit |

`staging_gate.py` bleibt **unverändert** (Gate-Logik ist korrekt; Defekt war ausschließlich der Selbst-Schreiber).

### Scope Assessment
- Dateien: ~12 (davon 1 im Repo henemm-infra)
- LoC: ci.yml ~+70/-35, Deploy-Skript ~+20, Tests ~+150, Rest Doku
- Risk Level: **HIGH** — ändert die Auslieferungskette jeder Session; Deploy-Skript-Änderung ist sofort live.

### Bewusste Entscheidungen (in die Spec übernehmen)
- `needs` auf alle 6: Im nächtlichen Rot-Fenster des `test`-Jobs (22:00–02:30 UTC) bzw. bei rotem `e2e` wird der
  CI-Deploy-Job übersprungen. Akzeptiert — der Session-Pfad (`/70-deploy`) liefert weiterhin, das Gate schützt beide.
- Normalfall nach der Änderung: Die Session liefert (wie dokumentiert); die CI ist Sicherheitsnetz für „Nachweis
  geschrieben, Deploy vergessen/abgebrochen" und liefert docs-only-Stände sofort.
- Rollout-Reihenfolge: Idempotenz im Deploy-Skript **zuerst** (henemm-infra), dann der ci.yml-PR — sonst doppelte Neustarts ab Merge.

### Open Questions
- keine an den PO (alle Punkte technisch, begründet entschieden).
