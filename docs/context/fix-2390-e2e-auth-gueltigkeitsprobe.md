# Context: fix-2390-e2e-auth-gueltigkeitsprobe

## Request Summary
Der lokale E2E-Messweg ist still falsch-rot: `global.setup.ts::isAuthFileValid()` hält
`playwright/.auth/admin.json` allein anhand der Cookie-Ablaufzeit für gültig. Nach einem
Neustart des isolierten Stacks (`ci-stack.sh`, neues Zufalls-Session-Secret) liefern alle
gespeicherten Cookies 401, das Setup bleibt grün, jede Folge-Spec scheitert ohne Hinweis
(gemessen #2276 S6b: 202 Fehlschläge, kein Produktfehler). Ziel: echte Gültigkeitsprobe
gegen den laufenden Server; bei ≠ 200 Datei verwerfen und regulär neu anmelden.

## Related Files
| File | Relevance |
|------|-----------|
| `frontend/e2e/global.setup.ts:10-21` | `isAuthFileValid()` — nur Ablaufzeit; Zeile 39-54: Login-Zweig vs. `addCookies`-Zweig (dort wird die Datei nicht neu geschrieben) |
| `frontend/e2e/ci-stack.sh:9-10` | `GZ_SESSION_SECRET` bewusst ungesetzt ⇒ jedes `start` erzeugt neues Signaturgeheimnis |
| `frontend/playwright.config.ts:33-63` | Projekt `setup` als Dependency, `storageState: playwright/.auth/admin.json` |
| `frontend/playwright.mobile-ux.local.config.ts:59` | nutzt dieselbe Datei als storageState |
| `frontend/e2e/pwaHelpers.ts:14` | `AUTH_STATE` = dieselbe Datei |
| `frontend/e2e/pwa-update-und-abmelden.spec.ts:~750-765` | `afterAll` stellt nach „auf allen Geräten abmelden" per echtem Login wieder her (Vorbild für Neuanmelde-Pfad) |
| `frontend/e2e/admin-nutzerverwaltung.staging.setup.ts:51-55` | Muster: `ctx.get('/api/auth/profile')` als Sitzungsprobe |
| `internal/router/router.go:130` | `GET /api/auth/profile` — authentifiziert (401 ohne gültige Sitzung); `/api/health` (Z. 233) ist öffentlich und taugt NICHT als Probe |
| `frontend/e2e/e2eTestUserResolution.test.ts` | Muster für deterministische `node --test`-Tests an E2E-Helfern mit Stub-Page (kein Mock-Theater) |
| `docs/reference/gates_und_ratschen.md:149-172, 350-360` | Filter-B-Aufnahmeregel (3× grün lokal); Abschnitt erwähnt „nur einloggt, wenn admin.json fehlt/abgelaufen" — nach Fix nachziehen |

## Existing Patterns
- Sitzungsprobe über `GET /api/auth/profile` (Staging-Setup #2155 S4).
- Frontend-Tests laufen über `node --test` mit `test-lib-loader.mjs` (kein Vitest); Helfer
  werden mit schlanken Stub-Objekten getestet (`e2eTestUserResolution.test.ts`).
- Login-Ablauf (Formular `form[action="?/login"]`, Pfad `/` nach Passkey-Marker #2248).

## Dependencies
- Upstream: Go-Auth-Middleware (401 bei ungültiger Signatur), SvelteKit-Proxy `/api/*` → `GZ_API_BASE`,
  `resolveE2EUser()` (`testUser.ts`), Prod-Guards (`prodUrlGuard.ts`) — Probe muss NACH den Guards laufen.
- Downstream: alle Playwright-Projekte mit `dependencies: ['setup']`, PWA-Strecke, mobile-ux-Config,
  CI-Job `e2e` (dort existiert `admin.json` nie vorher ⇒ Verhalten in CI unverändert).

## Existing Specs
- `docs/specs/modules/fix_2226_testdaten_isolation.md` (E2E-Testnutzer-Auflösung)
- `docs/specs/modules/e2e_scope_detection.md` (Scope-Erkennung, nur am Rande)

## Risks & Considerations
- Probe darf kein Login-Kontingent verbrauchen (IP-Rate-Limit 30/h, router.go:45; Reihenfolge-Falle
  PWA vs. bug-703): Probe ist ein GET auf `/api/auth/profile`, kein Login ⇒ unkritisch; Neuanmeldung
  nur bei tatsächlich ungültiger Sitzung (wie heute bei fehlender Datei).
- Probe muss gegen den Server laufen, gegen den auch die Tests laufen (baseURL/Proxy), nicht direkt gegen 8091.
- Netzfehler bei der Probe ⇒ als ungültig behandeln (fail-closed: neu anmelden), nicht still weiter.
- Nach erfolgreichem Neu-Login muss die Datei überschrieben werden (heutiger Pfad tut das).
- Gegenprobe muss aus Nutzersicht rot sein: abgelaufene Signatur bei gültiger Ablaufzeit ⇒ heute
  „gültig", nach Fix „ungültig" — deterministisch testbar mit einem Stub-Request (Status 401).
- Abnahme laut Issue: Zwei-Zyklen-Lauf mit Stack-Neustart dazwischen, `admin.json` absichtlich stehen gelassen.
- Doku-Satz in `gates_und_ratschen.md` (~Z. 351) beschreibt das alte Verhalten.
- Folgearbeit (nicht Teil dieses Tickets): Aufnahme `compare-stundenverlauf-wertprops.spec.ts` in die CI-Positivliste (#2276).

## Analysis

### Type
Bug (Test-Infrastruktur, lokaler E2E-Messweg; kein Produktcode betroffen)

### Root Cause
`global.setup.ts::isAuthFileValid()` (Z. 10-21) prüft nur `gz_session.expires`. Die Signatur
hängt am Session-Secret des laufenden Go-Servers; `ci-stack.sh start` erzeugt bei jedem Start ein
neues. Der `else`-Zweig (Z. 50-54) setzt die alten Cookies per `addCookies` und läuft ohne jede
Prüfung weiter ⇒ Setup grün, alle Folge-Specs 401. Gleiches gilt für jeden anderen Sitzungs-
Widerruf (z. B. „auf allen Geräten abmelden" ohne geglückte Wiederherstellung).

### Affected Files (with changes)
| File | Change Type | Description |
|------|-------------|-------------|
| `frontend/e2e/authStateProbe.ts` | CREATE | Reine Entscheidungsfunktion: Datei lesen/Ablaufzeit (bisherige Logik) + Gültigkeitsprobe über injiziertes `request` (`GET /api/auth/profile`, nur Status 200 = gültig; Exception/Netzfehler = ungültig, fail-closed) |
| `frontend/e2e/global.setup.ts` | MODIFY | Vorprüfung Ablaufzeit bleibt; ist sie ok, Cookies setzen und `page.request.get('/api/auth/profile')` proben; ≠ 200 ⇒ Cookies verwerfen und regulären Login-Zweig nehmen (schreibt `admin.json` neu). Kurze Konsolenzeile, warum neu angemeldet wurde |
| `frontend/e2e/authStateProbe.test.ts` | CREATE | `node --test` mit Stub-Request (Status 200 / 401 / wirft) und temporärer Datei: abgelehnte Sitzung bei gültiger Ablaufzeit ⇒ „neu anmelden" (heute: „wiederverwenden" ⇒ RED) |
| `docs/reference/gates_und_ratschen.md` | MODIFY | Satz ~Z. 351 („nur einloggt, wenn admin.json fehlt/abgelaufen") um „oder vom laufenden Server abgelehnt wird" ergänzen |

### Scope Assessment
- Files: 4 (2 neu, 2 geändert)
- Estimated LoC: +~110 / -~15 (davon ~60 Test)
- Risk Level: LOW — nur Test-Setup; CI-Verhalten unverändert (dort fehlt `admin.json` immer ⇒ Login-Zweig wie heute)

### Technical Approach
1. Probe über `page.request` (nutzt baseURL ⇒ SvelteKit-Proxy ⇒ derselbe Server wie die Tests),
   NACH den Prod-Guards und NACH `addCookies`. Endpoint `GET /api/auth/profile` (authentifiziert;
   `/api/health` ist öffentlich und ungeeignet).
2. Kein Login-Kontingent-Verbrauch durch die Probe (reiner GET); Neu-Login nur bei tatsächlich
   ungültiger Sitzung — derselbe Pfad wie bei fehlender Datei.
3. Bei ungültig: `context.clearCookies()`, dann Login-Formular, dann überschreibt `storageState` die Datei.
4. Entscheidungslogik in eigener Datei, damit sie ohne Browser deterministisch testbar ist
   (Muster `e2eTestUserResolution.test.ts`; Stub-Request ist Test-Double, kein Mock-Theater).
5. Abnahme aus Nutzersicht (Issue-AC): Zwei-Zyklen-Lauf gegen `ci-stack.sh` mit Neustart dazwischen,
   `admin.json` absichtlich stehen gelassen ⇒ beide Zyklen gleiche grüne Zahlen (Kontrollverbund
   aus bereits in CI gelisteten Specs).

### Dependencies
Upstream: Go-Auth-Middleware (401 bei falscher Signatur), SvelteKit-`/api/[...path]`-Proxy,
`resolveE2EUser()`, Prod-Guards. Downstream: alle Playwright-Projekte mit `dependencies: ['setup']`,
PWA-Strecke (`pwaHelpers.AUTH_STATE`), mobile-ux-local-Config — profitieren alle, keine Schnittstelle ändert sich.

### Verworfene Alternative
`admin.json` in `ci-stack.sh start` löschen: behandelt nur das Symptom, schützt nicht vor anderen
Sitzungs-Widerrufen (Secret-Wechsel, „überall abmelden", Datenreset).

### Open Questions
- keine (reine Test-Infrastruktur, keine Produktentscheidung)
