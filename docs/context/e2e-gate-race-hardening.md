# Context: E2E-Gate Race-Hardening (Issue #662)

## Request Summary

Die E2E-Attestation `e2e_verified.json` ist ein Singleton mit hartkodiertem Pfad
im Hauptrepo. Parallele Sessions überschreiben sich gegenseitig (last-writer-wins).
Lösung: Attestation pro verifiziertem Commit ablegen (`.claude/e2e_verified/<sha>.json`),
sodass jede Session ihre eigene Datei schreibt und das Deploy-Gate genau die zum
zu deployenden HEAD passende Attestation liest.

## Related Files

| Datei | Relevanz |
|-------|----------|
| `.claude/hooks/staging_gate.py` | `REPO_DIR`/`CANONICAL_E2E_PATH` (Z.40-41); `write_verdict()` schreibt die Datei (Z.101-128); `gate_check()` liest+prüft `verified_commit==HEAD` (Z.132-194); `--e2e-path`-Override existiert bereits |
| `.claude/hooks/prod_selftest.py` | `REPO_DIR`/`CANONICAL_E2E_PATH` (Z.36-37); `run_selftest()` liest Attestation + Commit-Attestation (Z.252-280); `--e2e-path`-Override existiert bereits |
| `henemm-infra/scripts/deploy-gregor-prod.sh` | ruft `staging_gate.py --check` (Z.92) **ohne** `--e2e-path` auf — läuft NACH `git reset --hard origin/main` (HEAD == Deploy-Commit). Cross-Repo → MQ an `infra` |
| `.claude/agents/staging-validator.md` | Step 7: ruft `staging_gate.py --write-verdict` auf (Z.86-91); dokumentiert Artefakt-Pfad |
| `.claude/commands/7-deploy.md` | ruft `prod_selftest.py` (Z.93); liest `staging_verdict` für Tech-Lead-Brief (Z.59) |
| `.claude/commands/e2e-verify.md` | Backend-Pfad schreibt `e2e_verified.json` per `python3 -c` direkt (Z.112-133) — **muss mitgezogen werden**, sonst schreibt der Backend-Pfad weiterhin ins Singleton |
| `.gitignore` | Z.42 ignoriert `.claude/e2e_verified.json` — neues Verzeichnis `.claude/e2e_verified/` muss ebenfalls ignoriert werden |

## Existing Patterns

- **`--e2e-path`-Override existiert bereits** in beiden Hooks (argparse). Das ist der
  saubere Hebel: Default-Pfad commit-getaggt ableiten, Override bleibt für Tests.
- **`_head_sha()`** in beiden Hooks liest `git rev-parse HEAD` mit `cwd=REPO_DIR` —
  der Anker für den commit-getaggten Dateinamen.
- **Scope-Detection** (`_detect_committed_scope`) klassifiziert HEAD~1..HEAD;
  docs-only → Gate übersprungen → keine Attestation nötig. Bleibt unberührt.
- **Mein eigener #660-Workaround** (Memory): `prod_selftest --e2e-path /tmp/eigene.json`
  war ein manueller Notbehelf gegen genau diese Race. Diese Lösung macht ihn überflüssig.

## Dependencies

- **Upstream (was wir nutzen):** `git rev-parse HEAD`, `pathlib`, `json`. Keine neuen Deps.
- **Downstream (was uns nutzt):**
  - `deploy-gregor-prod.sh` (henemm-infra, **Cross-Repo**) ruft `--check`.
  - `staging-validator`-Agent ruft `--write-verdict`.
  - `7-deploy`-Skill ruft `prod_selftest.py` + liest Verdict.
  - `e2e-verify`-Skill (Backend-Pfad) schreibt direkt.

## Existing Specs

- `docs/specs/modules/issue_521_staging_validator.md` — definiert e2e_verified.json + Gate-Semantik (verified_commit==HEAD, VERIFIED-Verdict, <24h).
- `docs/specs/modules/issue_564_post_deploy_selftest.md` — prod_selftest liest dieselbe Attestation.
- `docs/specs/modules/e2e_scope_detection.md` — Scope-Klassifikation (docs-only-Skip).

## Risks & Considerations

- **Cross-Repo-Atomarität:** Hook-Änderung (gregor_zwanzig) und Deploy-Script (henemm-infra)
  müssen zusammenpassen. Da `--check` Default-Pfad-Logik selbst kennt, kann das Script
  unverändert bleiben **wenn** der commit-getaggte Default + Singleton-Fallback im Hook liegt.
  Trotzdem: MQ an `infra` über den Mechanismus.
- **Fallback-Pflicht (AC-3):** Laufende Workflows haben evtl. noch das alte Singleton
  geschrieben → `gate_check`/`run_selftest` müssen Singleton als Fallback lesen, sonst
  brechen Deploys mitten in der Migration.
- **Backend-Pfad in e2e-verify.md:** Schreibt das JSON per inline `python3 -c` — wenn nicht
  mitgezogen, landet die Backend-Attestation weiterhin im Singleton. Entweder auf
  `staging_gate.py --write-verdict` umstellen oder commit-getaggten Pfad inline ableiten.
- **Stale-Datei-Akkumulation:** `.claude/e2e_verified/<sha>.json` wächst monoton. Retention
  nötig (analog `.backups/`-Pattern, z.B. letzte N oder Alter > X). Designentscheidung in Spec.
- **`deploy-gregor-prod.sh` verwirft e2e_verified.json bewusst** (Z.11 Kommentar) beim Sync —
  das neue Verzeichnis ist gitignored, übersteht `git reset --hard` als untracked. Prüfen
  dass kein `git clean` es löscht (Script nutzt kein clean → ok).
- **Keine Mocks:** Test muss echtes paralleles Schreiben + Gate-Check beweisen (zwei
  verschiedene SHAs, beide Dateien intakt, Gate akzeptiert nur die HEAD-passende).
