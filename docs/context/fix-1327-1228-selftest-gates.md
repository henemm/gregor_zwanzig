# Context: fix-1327-1228-selftest-gates

## Request Summary
#1327 (+gebündelt #1228): Deploy-Gates erzeugen PARTIAL-Falschbefunde — (a) Findings-Vermischung paralleler Workflows in der commit-getaggten Attestation, (b) Freitext-/Pseudo-URLs werden als HTTP-Probe gewertet, (c) POST-only-Endpoints per GET → 405 → FAIL, (d) `--write-verdict` akzeptiert Platzhalter-Verdicts (`"TEST"`), (e) Selftest-Berichtspfad zeigt auf fremden/alten Workflow.

## Root Causes (verifiziert, mit Fundstellen)

1. **Pseudo-URL-Konkatenation** (`prod_selftest.py:140-146`): `_staging_to_prod_url` baut `f"{PROD_BASE}{path}{query}"`; bei Freitext ohne führenden `/` (urlparse: scheme="", path="compareMetricDefs.ts/ALL_METRICS") entsteht `https://gregor20.henemm.comcompareMetricDefs.ts/ALL_METRICS` — ein syntaktisch valider Host, der `_is_probeable_url` (`:183-196`) PASSIERT und erst per DNS-Fehler in ERR/FAIL läuft (`:261-268`). Die Sentinel-Prüfung (`:212`, `_URL_SENTINELS` `:58`) greift nur für n/a/-/leer, nicht für beliebigen Freitext.
2. **405 = FAIL** (`prod_selftest.py:252-260`): Probe ist GET-only (`:155`), `ok = status in (200, 302)` — POST-only-Endpoints (z.B. `/api/auth/register`) liefern korrekt 405 und werden strukturell IMMER FAIL (#1228; früherer Fall dokumentiert auch GET→405 als False-Negative).
3. **Findings-Merge ohne Workflow-Trennung** (`staging_gate.py:259-278`): Bei gleichem `verified_commit` wird additiv gemerged, Dedup-Schlüssel = voll-serialisiertes Finding (`json.dumps(f, sort_keys=True)`, `:271`) → korrigierte Fassungen (andere url) ersetzen alte NICHT; `staging_verdict` wird schlicht vom letzten Schreiber überschrieben (`:253`). Kein Replace-Modus, kein Herkunfts-Feld. Zwei parallele Sessions auf gleichem TIP (real passiert 2026-07-20: #1324 + F3 auf `ef3f39d8`) vermischen unentwirrbar.
4. **Verdict-Schreibvalidierung nur negativ** (`staging_gate.py:235-239`): blockt nur `BROKEN*`; `"TEST"` u.ä. passieren. Der Lese-Check verlangt `VERIFIED`-Präfix (`:452`) → Schreiber kann unbemerkt eine Attestation erzeugen, die jedes spätere Gate scheitern lässt.
5. **Berichtspfad-Workflow-Quelle** (`prod_selftest.py:670-677`): `--workflow`-Arg → `OPENSPEC_ACTIVE_WORKFLOW`-Env → "unknown"; real landete der Bericht vom 2026-07-20 unter `docs/artifacts/epic-1273-s3-redirect/` (stale Quelle) — genaue Kette in Analyse-Phase des Developers zu verifizieren (Verdacht: stale Env/settings-Injektion; Zeile 673 erwähnt laut Explore `GZ_ACTIVE_WORKFLOW` — Inkonsistenz).

## Related Files
| File | Relevance |
|---|---|
| `.claude/hooks/staging_gate.py` (515 Z.) | write_verdict `:229-289` (Merge `:259-278`, Verdict-Check `:235-239`), gate_check `:349-483` (VERIFIED-Präfix `:452`, Staleness 24h `:460-476`) |
| `.claude/hooks/prod_selftest.py` (683 Z.) | `_probe_ac` `:199-268`, `_staging_to_prod_url` `:140-146`, `_is_probeable_url` `:183-196`, Verdict `:419-428`, Exit `:604`, Workflow-Name `:670-677` |
| `.claude/hooks/_e2e_paths.py` | geteilte Pfad-Helper (Singleton vs. commit-getaggt) |
| `tests/tdd/test_staging_gate.py` | Bestands-Suite Mode A/B — RED-Tests hier andocken |
| `tests/tdd/test_prod_selftest_564.py` | Bestands-Suite AC-Proben/Verdicts — RED-Tests hier andocken |
| `tests/tdd/test_staging_gate_verdict_merge.py` | Bestands-Merge-Tests (#1197) — Semantikänderung muss diese respektieren/anpassen |
| `/home/hem/henemm-infra/scripts/deploy-gregor-prod.sh:90-135` | Leser: `--check --expected-commit origin/main` (Preflight) + `--check` nach Reset — Vertrag darf nicht brechen |

## Existing Patterns
- SKIP-Statusklassen existieren bereits: `SKIPPED_NO_URL` (#788/#730), `SKIPPED_PREVIEW_TEST_TRIP` (#908), `SKIPPED_NOT_MAPPABLE` (#1197) — neue Fälle (Freitext, 405) folgen demselben Muster statt neuer Mechanik.
- Attestation-Felder-Vertrag: `verified_commit`, `staging_verdict` (VERIFIED-Präfix beim Lesen), `findings[{ac,status,url,evidence}]`, `verified_at` (24h-Staleness), `scope`, `environment`.
- Workflow-Namens-Quelle Standard: `OPENSPEC_ACTIVE_WORKFLOW` (9 Hooks), `GZ_ACTIVE_WORKFLOW` Legacy-Fallback (prod_send_gate.py).
- Hook-Tests leben in `tests/tdd/` (pytest, kein Netz — Kern-Schicht).

## Dependencies / Dependents
- Upstream: `_e2e_paths.py` (Pfad/Scope), Git (HEAD/Ancestor-Checks).
- Downstream: `deploy-gregor-prod.sh` (Hard Gate), Issue-Close-Regel „Selftest Exit 0", staging-validator-Agent (Schreiber), alle künftigen Workflows.

## Risks & Considerations
- **Beide Fehlrichtungen teuer:** Zu lasche Bewertung (405→PASS?) weicht das Gate auf; zu strenge blockt weiter falsch. Empfehlung: 405 und Freitext-URLs → neue SKIP-Klassen (SKIPPED_*), NICHT PASS — konservativ, kein Beweis-Theater.
- **Merge-Semantik-Änderung** muss `test_staging_gate_verdict_merge.py` (#1197-Schutz: Evidenz-Verlust des Erstschreibers verhindern) weiter erfüllen: Vorschlag `workflow`-Feld pro Finding + Replace nur eigener Workflow-Einträge, fremde bleiben. `staging_verdict` bei Multi-Workflow: Lesecheck verlangt EIN Präfix — Verdict-Feld darf durch zweiten Schreiber nicht von VERIFIED weg kippen, außer BROKEN.
- Edits an `.claude/hooks/` können Hook-Selbstschutz auslösen (User-Override nötig — [[reference_infra_hooks_edit_needs_user_override]]).
- Spec-Spiegelung: Gate-Fixes nach Merge sofort docs-only pushen (Deploy-Reset-Race, [[reference_spec_mirror_deploy_reset_race]]).
- #1228 nennt zusätzlich fehlende Methode/Body in der Attestation — Scope-Grenze: KEIN neues Findings-Schema-Feld `method` in dieser Scheibe erzwingen (nur 405-Bewertung fixen); Schema-Erweiterung wäre eigener Vorschlag.
