# Context: Bug #730 — prod_selftest.py crasht (InvalidURL) bei Findings ohne echte URL

## Request Summary
`prod_selftest.py` crasht mit `http.client.InvalidURL`, wenn ein Attestation-Finding
eine `url` enthält, die kein valider HTTP-Pfad ist (Freitext mit Leerzeichen/Steuerzeichen,
z.B. eine Backend-AC-Beschreibung `/api/trips/{id} PUT/GET`). Das blockiert fälschlich
den legitimen Issue-Close jeder Session, deren HEAD-Attestation eine solche Finding trägt.

## Root Cause
`_probe_ac` (Z. 124-141) baut `prod_url` via `_staging_to_prod_url` und ruft `_http_get`.
Bei Leer-/Steuerzeichen in der URL wirft `http.client` (in `putrequest`, Regex
`[\x00-\x20\x7f]`) `InvalidURL`. Dessen MRO ist `HTTPException → Exception` — **kein**
Subtyp von `urllib.error.URLError`/`OSError`. Der `except (URLError, OSError)` in
`_probe_ac` greift nicht → Exception propagiert → `list(pool.map(_probe_ac, findings))`
(Z. 358) re-raised sie → Script-Exit 1, obwohl der Deploy erfolgreich war.

## Related Files
| File | Relevance |
|------|-----------|
| `.claude/hooks/prod_selftest.py` | `_probe_ac` (Z.114-141), `_staging_to_prod_url` (Z.75-81), `_derive_verdict` (Z.288-302), Report-Render (Z.214-244) |
| `tests/tdd/test_prod_selftest_564.py` | Mock-freie Subprozess-Tests gegen echtes Prod; `_make_e2e`-Helper setzt `verified_commit=HEAD`; Vorlage für RED |
| `.claude/hooks/_e2e_paths.py` | Pfadauflösung der Attestationen (unverändert) |

## Existing Patterns
- **SKIPPED-Branch** in `_probe_ac` (Z.116-122): Finding mit `status=="SKIPPED"` → ohne
  Netzwerk `prod_status="ATTESTED_SKIPPED"`. Vorlage für die neue „nicht-probebare URL"-SKIP.
- **Verdict-Logik** klassifiziert nach `finding["status"]` (PASS/SKIPPED), Block nur bei
  `prod_status=="FAIL"`. Ein neuer `prod_status` ≠ FAIL blockt nicht → Verdict bleibt PASS.
- **Tests** laufen als echter Subprozess (`subprocess.run` auf das Script), treffen echtes
  Prod, kein Mock/Patch. Commit-Attestation via `verified_commit=$(git rev-parse HEAD)`.

## Dependencies
- Upstream: `urllib`/`http.client` (stdlib), `_e2e_paths`.
- Downstream: `deploy-gregor-prod.sh` ruft das Script nach jedem Deploy; CLAUDE.md koppelt
  `gh issue close` an Exit 0. Crash = Close blockiert.

## Existing Specs
- `docs/specs/modules/issue_564_post_deploy_selftest.md` — Basis-Spec des Selftests
- `docs/specs/modules/issue_685_selftest_menu_gate.md` — Bot-Menü-Gate (additive Phase 4)

## Fix-Richtung (Vorschau)
Vor dem HTTP-Probe in `_probe_ac` prüfen, ob die abgeleitete `prod_url` gefahrlos
probebar ist (mirror von urllibs Disallowed-Char-Regex `[\x00-\x20\x7f]` + Pfad
beginnt mit `/`). Nicht-probebare Findings → neuer `prod_status` (z.B. `SKIPPED_NO_URL`),
als Skip gezählt, in Report-Tabelle transparent, **kein** Verdict-Block, kein Crash.

## Risks & Considerations
- **Tooling-only** (`.claude/hooks/`): kein Prod-Deploy nötig, wirkt beim nächsten Deploy.
- Verdict-Semantik darf sich für valide Findings **nicht** ändern (PASS/PARTIAL/FAIL/SKIPPED_ALL).
- Defense-in-depth: ggf. zusätzlich `InvalidURL`/`ValueError` im `except` abfangen, falls
  eine URL die Prüfung passiert, urllib aber dennoch ablehnt.
- Test muss `verified_commit=HEAD` setzen, sonst greift Commit-Mismatch vor der AC-Phase.
