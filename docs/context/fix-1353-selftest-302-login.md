# Context: fix-1353-selftest-302-login

## Request Summary
Der Post-Deploy-Selbsttest (`prod_selftest.py`) wertet **jeden** HTTP-302-Redirect als „PASS" (`ok = status in (200, 302)`). Dadurch besteht ein geschützter Endpoint, der unauthentifiziert nur auf die Login-Seite umleitet, den Test blind — ohne dass der eigentliche AC-Inhalt je geprüft wurde. Ziel: Ein 302 auf die Anmeldeseite darf ein AC nicht mehr als bewiesen ausweisen.

## Related Files
| File | Relevance |
|------|-----------|
| `.claude/hooks/prod_selftest.py:283` | Der Bug: `ok = status in (200, 302)` — 302 pauschal wie 200 gewertet |
| `.claude/hooks/prod_selftest.py:149-170` (`_http_get`) | Fängt 3xx via `_NoRedirectHandler` ab; `HTTPError` trägt den `Location`-Header, gibt aber nur `(status, body)` zurück → Location muss durchgereicht werden |
| `.claude/hooks/prod_selftest.py:199-297` (`_probe_ac`) | Baut das Ergebnis pro AC-Finding; enthält die zu ändernde Statuslogik |
| `.claude/hooks/prod_selftest.py:276-282` | **Präzedenz-Muster:** 405 → `SKIPPED_METHOD_NOT_PROBEABLE` (Status nach der Probe inspizieren → eigener SKIPPED-Wert statt FAIL) |
| `.claude/hooks/prod_selftest.py:444-458` (`_derive_verdict`) | Zählt nur `prod_status == "FAIL"` als PARTIAL-Auslöser; alle `SKIPPED_*` blockieren PASS nicht → ein neuer Status fügt sich ohne Änderung ein |
| `.claude/commands/e2e-verify.md:129-147` | Schema von `e2e_verified.json` → `findings[].url` (Herkunft der geprüften URLs, teils `/`, `/trips/new`, `/api/…`) |
| `tests/tdd/test_prod_selftest_564.py` | PASS-Erwartungen laufen über `url:"/"` → **faktisch der Kanal, über den der reale Prod-302 als PASS durchläuft** (Regressionsrisiko) |
| `tests/tdd/test_prod_selftest_internal_url_skip.py:171-192` | Regressionsanker: 401-Auth-Wall auf öffentlicher URL MUSS `FAIL` bleiben — konzeptionell dasselbe wie 302-auf-Login |
| `docs/specs/modules/gate_honesty_mail_selftest.md` | Aktive Spec, Leitmotiv „Wächter meldet Erfolg ohne zu prüfen" + Invariante „ohne legitime Nachweise zu brechen" — adressiert den 302-Fall aber NICHT (nur `_scope_diff_base`) |
| `CLAUDE.md:230` / `docs/reference/operations_playbook.md:76` | Deploy-Schritt 4b: nur Exit 0 erlaubt `gh issue close` |

## Existing Patterns
- **SKIPPED-Sentinel-Modell:** `_probe_ac` kennt bereits `ATTESTED_SKIPPED`, `SKIPPED_NO_URL`, `SKIPPED_PREVIEW_TEST_TRIP`, `SKIPPED_NOT_MAPPABLE`, `SKIPPED_METHOD_NOT_PROBEABLE`. „Strukturell nicht per unauth-GET prüfbar" wird als eigener Status modelliert, der weder PASS blockiert noch FAIL/PARTIAL auslöst. Das 405-Muster (`:276-282`) ist die direkte Vorlage.
- **401-auf-öffentlicher-URL → FAIL** ist bereits etabliert (#1197). Ein 302-auf-Login ist die Redirect-Variante desselben Problems.

## Dependencies
- **Upstream:** liest `e2e_verified.json` → `findings[].url`; `PROD_BASE`; `_staging_to_prod_url`.
- **Downstream:** Deploy-Schritt 4b ruft `prod_selftest.py` auf; Exit 0 ist die **einzige** Freigabe für `gh issue close` (`run_selftest` → `return 0 if verdict in ("PASS","SKIPPED_ALL") else 1`, `:633`).

## Existing Specs
- `docs/specs/modules/gate_honesty_mail_selftest.md` — liefert die Ehrlichkeits-Leitplanken, aber keinen fertigen AC für den 302-Fall → dieser Bug braucht eigene AC.

## Risks & Considerations
- **Regressionsgefahr Nr. 1 — legitimer 302 muss PASS bleiben:** Root `/` und Frontend-Routen liefern in Prod erwartungsgemäß 302 (App-/SPA-/Login-Redirect); der Ops-Playbook-Smoke akzeptiert `/` → 200/302 ausdrücklich. Ein pauschales Entfernen von 302 aus der PASS-Menge kippt diese Findings zu FAIL/PARTIAL und bricht `test_prod_selftest_564` (`/`-basierte PASS-Erwartungen). **Der Fix muss diskriminieren, nicht global streichen.**
- **Kern-Design-Frage (für Analyse/Spec):** Wie unterscheidet man den legitimen Redirect (öffentliche/Root-Route, Smoke-erreichbar) vom blinden Redirect (geschützter Endpoint → Auth-Wall, kein AC-Beweis)? Kandidaten: (a) `Location`-Header prüfen (zeigt auf Anmeldeseite?), (b) Pfadklasse (`/api/…` vs. Frontend), (c) Kombination. `_http_get` muss dafür den `Location`-Header mitliefern.
- **Ergebnis-Modellierung:** FAIL vs. neuer `SKIPPED_*`-Status. Da der Selftest unauthentifiziert läuft, ist ein Auth-Redirect auf einem geschützten Endpoint „strukturell nicht prüfbar" — ein SKIPPED-Status (analog 405) ist ehrlicher als FAIL und deutlich ehrlicher als das heutige blinde PASS. Zu klären: Führt zu-viel-SKIPPED zu einem aussagelosen Selbsttest? (Abwägung Aussagekraft vs. Ehrlichkeit.)
- **Blast Radius:** Fix zu streng → blockiert legitime Deploys; zu lasch → bleibt blind. Kritischer Pfad; verlangt Adversary-Gegenprüfung.

## Analysis

### Type
Bug (Fehlerkorrektur an einem Deploy-Gate). Root Cause eindeutig: `.claude/hooks/prod_selftest.py:283` wertet 302 pauschal wie 200.

### Affected Files (with changes)
| File | Change Type | Description |
|------|-------------|-------------|
| `.claude/hooks/prod_selftest.py` | MODIFY | (1) `_http_get` reicht den `Location`-Header mit zurück (aus `resp.headers` bzw. `exc.headers`); (2) `_probe_ac` klassifiziert einen Redirect auf die Anmeldeseite als neuen `prod_status = "SKIPPED_AUTH_REDIRECT"` statt PASS; (3) Login-Pfad-Erkennung (Location-Path vs. bekannter Login-Pfad). Aufrufer von `_http_get` (2: `_check_health`, `_probe_ac`) an die neue Signatur anpassen. |
| `tests/tdd/test_selftest_auth_redirect.py` (o.ä., verhaltensbenannt) | CREATE | Repro (rot vor Fix): 302→Anmeldeseite ergibt NICHT PASS. Regression: 302→Nicht-Login bleibt PASS; 200 bleibt PASS; 401 bleibt FAIL (bestehender Anker). |

### Scope Assessment
- Files: 1 Quelldatei + 1 Testdatei
- Estimated LoC: ~+40 / -3 (Kern-Datei), Test separat
- Risk Level: **MEDIUM** — kleiner Diff, aber Deploy-Gate (kritischer Pfad)

### Technical Approach
1. **`_http_get` → Location durchreichen:** Rückgabe um das Redirect-Ziel erweitern (z.B. `(status, body, location)`; `location=""` wenn kein Redirect). Bei abgefangenem `HTTPError` liegt der Header in `exc.headers["Location"]`.
2. **`_probe_ac` klassifiziert:** Ist `status` ein Redirect (301/302/303/307/308) UND zeigt das Ziel auf die Anmeldeseite (Location-Path == Login-Pfad bzw. beginnt damit; robust gegen absolute/relative URL) → `prod_status = "SKIPPED_AUTH_REDIRECT"`. Andernfalls bleibt ein 302 auf ein Nicht-Login-Ziel PASS (echter inhaltlicher Redirect, z.B. Root-Smoke). Also aus `ok = status in (200, 302)` wird: `200` → PASS; Redirect-auf-Login → SKIPPED_AUTH_REDIRECT; Redirect-auf-Nicht-Login → PASS.
3. **`_derive_verdict` bleibt unverändert** — `SKIPPED_*` blockiert PASS nicht und löst kein FAIL/PARTIAL aus (bestehende Logik, `:444-458`). Der Report zeigt den neuen Status generisch an.

### Dependencies
- Upstream: `e2e_verified.json` → `findings[].url`; `PROD_BASE`; Login-Pfad der Frontend-App (zu bestätigen: Route `/login`).
- Downstream: Deploy-Schritt 4b; `gh issue close` hängt an Exit 0.

### Design-Entscheidung (Tech Lead, PO-Mandat „nach Best Practice entscheiden")
**Auth-Redirect → `SKIPPED_AUTH_REDIRECT` (ehrlich), NICHT FAIL.** Begründung: Der Selbsttest läuft unauthentifiziert; dass ein geschützter Endpoint auf die Anmeldeseite umleitet, ist **kein Defekt**, sondern strukturell nicht per unauth-GET prüfbar (exakt wie 405 → `SKIPPED_METHOD_NOT_PROBEABLE`). Das reine „lebt Prod?"-Signal liefert der **separate** Health-Check (`/api/health` → 200, Exit-1-scharf). FAIL wäre daher ein Fehlalarm, der legitime Deploys blockiert. Der Kern des Bugs — blind „PASS" behaupten — wird durch den ehrlichen SKIPPED-Status behoben: Der Report weist solche ACs sichtbar als „unauth nicht geprüft" aus, statt Prüfung vorzutäuschen.

### Open Questions
- [ ] **Für PO bei AC-Freigabe:** Bestätigung, dass ein Auth-Redirect als „ehrlich übersprungen" (Deploy läuft weiter) statt als „Fehler" (Deploy-Block) modelliert wird — meine Empfehlung ist SKIPPED (s.o.). Falls maximale Strenge gewünscht (jeder unauth nicht prüfbare AC = Deploy-Block), wäre es FAIL.
- [ ] Login-Pfad der App bestätigen (Annahme: `/login`) — wird in der Spec fixiert.

