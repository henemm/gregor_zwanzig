# Context: storagestate-1321

## Request Summary
Issue #1321: Die sechs verbleibenden Compare-E2E-Spec-Dateien im `chromium-login`-Projekt der Config `playwright.1273-s4c.staging.config.ts` sollen vom Pro-Test-UI-Login (`login(page)` aus `helpers.ts`) auf das bereits produktive storageState-Muster (`chromium-storagestate`-Projekt derselben Config) umgestellt werden. Ziel: ein Volllauf verbraucht ≤2 statt ~23 Logins und bleibt unter dem Staging-Rate-Limit von 30 Logins/Stunde/IP.

## Related Files

| File | Relevance |
|------|-----------|
| `frontend/playwright.1273-s4c.staging.config.ts` | Zentrale Config mit drei Projekten: `setup`, `chromium-login` (6 Ziel-Dateien), `chromium-storagestate` (2 Dateien, Referenzmuster). Migration = `testMatch`-Einträge von `chromium-login` nach `chromium-storagestate` verschieben. |
| `frontend/e2e/f1-1273-s4c.staging.setup.ts` | Setup-Projekt, das per API-Login (`POST /api/auth/login`) einmalig einen storageState nach `frontend/playwright/.auth/staging-1273-s4c.json` schreibt (chmod 0600). Existiert bereits seit `fafede36`, funktioniert nachweislich für 2 Dateien. Keine Änderung nötig. |
| `frontend/e2e/helpers.ts` (Zeile 8-17) | `login(page)`-Helper: navigiert zu `/`, füllt bei Redirect auf `/login` das UI-Formular aus. Erzeugt den Pro-Test-Login-Traffic, der das Rate-Limit sprengt. Import wird aus den 6 Zieldateien entfernt (Helper selbst bleibt, wird von anderen Suiten weiter gebraucht). |
| `frontend/e2e/compare-radar-toggle.spec.ts` | Ziel 1/6. `beforeEach`: `login(page)` + `setViewportSize`. |
| `frontend/e2e/compare-alarm-config.spec.ts` | Ziel 2/6. `beforeEach`: `login(page)` + `setViewportSize`. |
| `frontend/e2e/compare-legacy-fields-survive-save.spec.ts` | Ziel 3/6. `beforeEach`: nur `login(page)`, kein `setViewportSize`. |
| `frontend/e2e/versand-tab-vergleich.spec.ts` | Ziel 4/6. `beforeEach`: `login(page)` + `setViewportSize`. |
| `frontend/e2e/layout-tab-vergleich.spec.ts` | Ziel 5/6. `beforeEach`: `login(page)` + `setViewportSize`. |
| `frontend/e2e/issue-718-idealwert-validation.spec.ts` | Ziel 6/6. `beforeEach`: `login(page)` + `setViewportSize`. |
| `frontend/e2e/compare-editor-autosave.spec.ts` | Referenzmuster (bereits im `chromium-storagestate`-Projekt): `beforeEach` enthält NUR `setViewportSize`, kein Login-Import, kein Login-Aufruf — Session kommt vollständig aus dem geladenen storageState. |
| `internal/router/router.go:45` | `loginLimiter := authmw.NewIPRateLimiter(30, time.Hour)` — Token-Bucket 30/h pro IP, bestätigt Zahl aus der Issue-Beschreibung. Kein Code-Change nötig, nur Kontext für die Akzeptanzkriterien. |

## Existing Patterns

- **storageState-Konsolidierung ist bereits etabliert:** `chromium-storagestate`-Projekt in derselben Config lädt `playwright/.auth/staging-1273-s4c.json` (per `dependencies: ['setup']` + `use: { storageState: ... }`) und deckt 12 Tests über 2 Dateien mit nur 1 Login ab (~15s Setup-Overhead statt Pro-Test-Login).
- Alle 6 Zieldateien navigieren in den eigentlichen Tests direkt zu ihrer Zielroute (`/compare/{id}` oder `/compare/new`) via `page.goto(...)` — nicht über den `login()`-Helper. Der Login war ausschließlich ein Vorab-Schritt in `beforeEach`, keine funktionale Abhängigkeit innerhalb der Testlogik.
- `page.request.post(...)`-Aufrufe (z.B. `compare-radar-toggle.spec.ts:32` für Preset-Erstellung via API) nutzen den Browser-Context und damit automatisch die storageState-Cookies — kein separates Auth-Handling nötig.

## Dependencies

- **Upstream:** `f1-1273-s4c.staging.setup.ts` (unverändert wiederverwendet), `internal/router/router.go` Login-Rate-Limit (nur Kontext, kein Change), Staging-Umgebungsvariablen `GZ_VALIDATOR_*` (nginx) und `GZ_AUTH_*`/`E2E_USER`/`E2E_PASS` (App-Login).
- **Downstream:** Keine — reine Testinfrastruktur, kein Produktionscode betroffen.

## Existing Specs

- Kein dediziertes Entity-Spec vorhanden — reine Test-Tooling-Änderung ohne Produktcode-Bezug. `docs/context/f1-1273-s4c-e2e-hub.md` dokumentiert die S4c-Migration selbst (Vorarbeit aus #1301 F1-Rest), ist aber kein normatives Spec für dieses Issue.

## Risks & Considerations

- **Reihenfolge-Kopplung innerhalb des Projekts:** Wenn alle 6 Dateien gleichzeitig ins `chromium-storagestate`-Projekt wandern, teilen sie sich mit den 2 bestehenden Dateien (Mandantentrennung/Autosave-Tests) denselben storageState/User. Falls einzelne der 6 Migrations-Tests Zustand hinterlassen, der die bestehenden 2 Autosave-Tests stört (oder umgekehrt), könnte das zu Flakes führen, die vorher durch getrennte Logins/Sessions maskiert waren. Muss im Adversary-Test explizit geprüft werden (Volllauf zweimal hintereinander, wie im AC gefordert).
- **`login`-Import muss vollständig entfernt werden**, sonst bleibt totes Import + ungenutzter Login-Traffic im Testlauf (ESLint `no-unused-vars` sollte das ohnehin fangen).
- **`compare-legacy-fields-survive-save.spec.ts`** hat kein `setViewportSize` im `beforeEach` — beim Verschieben nicht versehentlich eines hinzufügen, das vorher nicht da war (Scope-Kriech vermeiden).
- Akzeptanzkriterien sind messbar (≤2 Logins, <2 Minuten Laufzeit, zwei Volläufe hintereinander grün) — das erfordert einen echten Staging-Lauf zur Verifikation, nicht nur Code-Review.

## Score Recap (aus Intake)
Standard Track, Sum=1 (Scope=Medium/7 Dateien, Blast Radius=Low, Unsicherheit=Low). Muster bereits produktiv erprobt.

## Analysis

### Type
Feature (Test-Infrastruktur-Konsolidierung, kein Produktcode-Bug)

### Zusatzfund (Explore-Agent, Schritt 2)
Keine versteckten Referenzen außerhalb der 7 Zieldateien: weder `frontend/package.json`, noch `.github/workflows/*.yml`, noch eine andere Playwright-Config referenzieren die sechs Spec-Dateien oder das Projekt `chromium-login`. `docs/specs/modules/epic_1273_s4c_e2e_migration.md` (Epic #1273 S4c, bereits live seit `fafede36`) dokumentiert, dass genau diese sechs Dateien im Zuge der Hub/Wizard-Migration auf lebende Routen (`/compare/{id}`, `/compare/new`) umgestellt wurden, aber bewusst mit Pro-Test-Login im `chromium-login`-Projekt verblieben — die Login-Konsolidierung war dort explizit nicht im Scope und ist genau der Gegenstand von #1321. Kein Widerspruch, keine offene Altlast aus S4c.

### Affected Files (with changes)

| File | Change Type | Description |
|------|-------------|-------------|
| `frontend/e2e/compare-radar-toggle.spec.ts` | MODIFY | `import { login } ...` entfernen; `await login(page);` aus `beforeEach` entfernen (Zeile `setViewportSize` bleibt). |
| `frontend/e2e/compare-alarm-config.spec.ts` | MODIFY | Gleiches Muster. |
| `frontend/e2e/compare-legacy-fields-survive-save.spec.ts` | MODIFY | Gleiches Muster; `beforeEach` enthält NUR `login(page)` → nach Entfernung leer, kompletter `test.beforeEach(...)`-Block wird entfernt (kein toter Hook). |
| `frontend/e2e/versand-tab-vergleich.spec.ts` | MODIFY | Gleiches Muster. |
| `frontend/e2e/layout-tab-vergleich.spec.ts` | MODIFY | Gleiches Muster. |
| `frontend/e2e/issue-718-idealwert-validation.spec.ts` | MODIFY | Gleiches Muster. |
| `frontend/playwright.1273-s4c.staging.config.ts` | MODIFY | Die 6 `testMatch`-Regex aus dem `chromium-login`-Projekt in das `chromium-storagestate`-Projekt verschieben (dort `dependencies: ['setup']` + `use.storageState` bereits vorhanden — gilt automatisch für alle `testMatch`-Einträge des Projekts). Das dadurch leere `chromium-login`-Projekt komplett entfernen (kein totes `testMatch: []`). Kopfkommentar (Zeilen 7-11, beschreibt aktuell zwei Projekttypen) auf ein Projekt reduzieren. |

Keine Änderung an `f1-1273-s4c.staging.setup.ts` (deckt bereits alle 8 Dateien im `chromium-storagestate`-Projekt ab, kein Anpassungsbedarf) und an `helpers.ts` (bleibt für andere Suiten mit echtem Pro-Test-Login bestehen).

### Scope Assessment
- Files: 7 (6 Spec + 1 Config)
- Estimated LoC: ca. -20/+10 (Netto-Abnahme: Imports/Login-Aufrufe/leerer Hook entfallen; Config-Umbau ist reine Verschiebung + Streichung, kein Nettozuwachs). Deutlich unter dem 250-LoC-Limit, kein Override nötig.
- Risk Level: LOW

### Technical Approach
Rein mechanische Migration nach bereits etabliertem, produktiv laufendem Muster (`compare-editor-autosave.spec.ts` als 1:1-Vorbild). Kein neues Verhalten, keine neue Fachlogik. Reihenfolge irrelevant (alle 7 Änderungen unabhängig, landen gemeinsam in einem Commit, da Config und Specs zusammen konsistent sein müssen für einen validen Playwright-Projektlauf).

### Risiken (unverändert aus Kontext-Phase, hier bestätigt)
- **Geteilter storageState/User zwischen 6 neuen + 2 bestehenden Dateien im selben Projekt:** Playwright lädt `storageState` pro Testfall in einen frischen Browser-Context (kein literal geteilter Tab) — dasselbe Session-Cookie wird aber parallel von mehreren Workern verwendet, genau wie schon jetzt bei den 2 bestehenden Dateien (12 Tests, nachweislich stabil). Kein grundsätzlich neues Risikomuster, aber der Fan-out verdreifacht sich (8 statt 2 Dateien) — das geforderte AC „zwei Volläufe hintereinander bleiben grün" ist der richtige Nachweis dafür und gehört als Pflicht-Prüfschritt in die Spec.
- Testdaten-Namenskollisionen zwischen den 6 neuen und 2 bestehenden Dateien sind unwahrscheinlich (alle beobachteten Preset-Namen nutzen `Date.now()`-Suffixe zur Eindeutigkeit), aber nicht explizit verifiziert für alle 6 Dateien — wird beim Volllauf-Nachweis miterledigt.

### Dependencies
- Upstream: `f1-1273-s4c.staging.setup.ts`, `internal/router/router.go:45` (Rate-Limit, nur Kontext).
- Downstream: keine.

### Open Questions
Keine blockierenden. Entscheidung „leeres `chromium-login`-Projekt löschen statt leer stehen lassen" wird hier getroffen (Dead-Code-Vermeidung) und fließt direkt in die Spec ein — keine Rückfrage nötig.
