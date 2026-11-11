---
entity_id: fix_2390_e2e_auth_gueltigkeitsprobe
type: bugfix
created: 2026-11-11
updated: 2026-11-11
status: draft
version: "1.0"
workflow: fix-2390-e2e-auth-gueltigkeitsprobe
issue: 2390
tags: [tests, e2e, auth, playwright, messweg]
---

# fix_2390_e2e_auth_gueltigkeitsprobe

## Approval

- [ ] Approved

## Purpose

Der lokale E2E-Messweg meldet still falsch-rot: `frontend/e2e/global.setup.ts` hält den gespeicherten
Anmeldezustand `playwright/.auth/admin.json` allein anhand der Cookie-Ablaufzeit für gültig. Nach einem
Neustart des isolierten Stacks (`ci-stack.sh`, neues Zufalls-Session-Secret) lehnt der Server alle
gespeicherten Cookies mit 401 ab, das Setup bleibt trotzdem grün und jede Folge-Spec scheitert ohne
Hinweis (gemessen in #2276: 202 Fehlschläge ohne Produktfehler). Der Fix ersetzt die reine Zeitprüfung
durch eine echte Gültigkeitsprobe gegen den laufenden Server.

## Source

- **File:** `frontend/e2e/global.setup.ts` (Funktion `isAuthFileValid()`, Login- und `addCookies`-Zweig),
  neues Modul `frontend/e2e/authStateProbe.ts`
- **Identifier:** `isAuthFileValid`, neue Entscheidungsfunktion für die Sitzungsprobe

> Schicht: reines E2E-Tooling (`frontend/e2e/`, Playwright-Ebene) plus ein Doku-Satz. Kein Produktcode in
> `src/`, `api/`, `internal/` oder `frontend/src/`. Trip/Ortsvergleich-Teilung, Mandantentrennung und
> Kanäle sind nicht berührt (keine Nutzerdaten, keine Briefing-Inhalte).

## Estimated Scope

- **LoC:** ca. +110 / -15 (davon ca. 60 Test)
- **Files:** 4 (2 neu, 2 geändert)
- **Effort:** low

## Scope

### Affected Files

| File | Change Type | Description |
|------|-------------|-------------|
| `frontend/e2e/authStateProbe.ts` | CREATE | Reine Entscheidungsfunktion: Ablaufzeit prüfen (bisherige Logik), danach Gültigkeitsprobe über injiziertes `request` (`GET /api/auth/profile`; nur Status 200 = gültig; Exception = ungültig, fail-closed) |
| `frontend/e2e/global.setup.ts` | MODIFY | Nutzt die Entscheidungsfunktion nach den Prod-Guards und nach `addCookies`; bei „ungültig" Cookies verwerfen (`context.clearCookies()`), regulären Login-Zweig nehmen (überschreibt `admin.json`); kurze Konsolenzeile mit Grund |
| `frontend/e2e/authStateProbe.test.ts` | CREATE | Deterministischer `node --test`-Test mit Stub-Request (200 / 401 / wirft) und temporärer Datei |
| `docs/reference/gates_und_ratschen.md` | MODIFY | Satz zum Setup (ca. Z. 351, „nur einloggt, wenn admin.json fehlt/abgelaufen") um „oder vom laufenden Server abgelehnt wird" ergänzen |

### Nicht-Ziele

- **Kein Produktcode.** Go-Auth, SvelteKit-Proxy und Session-Handling bleiben unverändert.
- **Keine Aufnahme von `compare-stundenverlauf-wertprops.spec.ts` in die CI-Positivliste.** Das ist
  Folgearbeit aus #2276 und ein eigenes Ticket.
- **Keine Änderung am CI-Job `e2e`.** Dort existiert `admin.json` vorher nie, der Login-Zweig läuft wie heute.

### Verworfene Alternative

`admin.json` in `ci-stack.sh start` löschen. Das behandelt nur das Symptom „Stack-Neustart" und schützt
nicht vor anderen Sitzungs-Widerrufen (Secret-Wechsel von außen, „auf allen Geräten abmelden", Daten-Reset).
Die Probe am Verbraucher (Setup) fängt alle Ursachen mit einer Stelle ab.

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `GET /api/auth/profile` (`internal/router/router.go:130`) | Go-Endpoint | Authentifiziert, 401 ohne gültige Sitzung; taugt als Probe (`/api/health` ist öffentlich und ungeeignet) |
| SvelteKit-Proxy `/api/*` | Frontend-Server | Probe läuft über baseURL, trifft denselben Server wie die Tests |
| `frontend/e2e/prodUrlGuard.ts` | E2E-Guard | Probe muss nach den Prod-Guards laufen |
| `resolveE2EUser()` (`testUser.ts`) | E2E-Helfer | Login-Zweig beim Neuanmelden |
| `frontend/e2e/e2eTestUserResolution.test.ts` | Test-Muster | Vorbild für `node --test` an E2E-Helfern mit schlankem Stub |
| `frontend/e2e/admin-nutzerverwaltung.staging.setup.ts` | Vorbild | Gleiche Sitzungsprobe `ctx.get('/api/auth/profile')` (#2155 S4) |

## Implementation Details

1. `authStateProbe.ts` kapselt die Entscheidung „Datei wiederverwenden oder neu anmelden", ohne Browser:
   Ablaufzeit prüfen wie bisher; ist die Datei fehlend oder abgelaufen, lautet das Ergebnis sofort
   „neu anmelden" (keine Probe nötig). Sonst Probe über das injizierte `request`; nur Status 200 heißt
   „wiederverwenden", jeder andere Status und jede Exception heißt „neu anmelden" (fail-closed). Das
   Ergebnis trägt einen kurzen Grund-Text für die Konsolenzeile.
2. `global.setup.ts`: Prod-Guards laufen unverändert zuerst. Danach werden gespeicherte Cookies per
   `addCookies` gesetzt und über `page.request` (baseURL, SvelteKit-Proxy) geprobt. Bei „neu anmelden":
   `context.clearCookies()`, dann der reguläre Login über das Formular; dessen `storageState` überschreibt
   `admin.json`. Eine Zeile nennt den Grund (z. B. „Anmeldezustand vom Server abgelehnt (401) – melde neu an").
3. Die Probe ist ein reiner GET und verbraucht kein Login-Kontingent (IP-Rate-Limit 30/h, `router.go:72`);
   eine Neuanmeldung gibt es nur bei tatsächlich ungültiger Sitzung, wie heute bei fehlender Datei.
4. Der Stub-Request im Test ist ein Test-Double für die Netzgrenze; geprüft wird die Entscheidung
   (Rückgabewert), nicht der Aufruf.

## Expected Behavior

- **Input:** `playwright/.auth/admin.json` (vorhanden, fehlend oder abgelaufen) und ein laufender Server.
- **Output:** Setup endet immer mit einer vom Server akzeptierten Sitzung oder bricht beim Login sichtbar ab.
- **Side effects:** Bei abgelehnter Sitzung wird `admin.json` durch den frischen Login überschrieben.
  Eine Konsolenzeile nennt den Grund der Neuanmeldung.

## Test Plan

### Automated Tests (TDD RED)

- [ ] `frontend/e2e/authStateProbe.test.ts` (`node --test`, kein Vitest, kein Mock-Theater):
  - GIVEN temporäre Datei mit gültiger Ablaufzeit und Stub-Request mit Status 401 WHEN Entscheidung
    getroffen wird THEN „neu anmelden". **RED-Nachweis:** die heutige Logik liefert hier „wiederverwenden".
  - GIVEN gültige Ablaufzeit und Stub-Status 200 THEN „wiederverwenden".
  - GIVEN gültige Ablaufzeit und Stub, der eine Exception wirft THEN „neu anmelden" (fail-closed).
  - GIVEN fehlende oder abgelaufene Datei THEN „neu anmelden" und der Stub wird nicht aufgerufen.
  - GIVEN Status 200 THEN der Stub wurde mit dem Pfad `/api/auth/profile` gefragt.
- [ ] Zwei-Zyklen-Abnahme (manuell, lokal, siehe AC-6) gegen `ci-stack.sh` mit Kontrollverbund aus bereits
  in der CI gelisteten Specs.

## Acceptance Criteria

- **AC-1:** Given `admin.json` enthält Cookies mit noch gültiger Ablaufzeit, der laufende Server lehnt sie aber mit 401 ab (z. B. nach Stack-Neustart) / When das E2E-Setup startet / Then meldet es sich regulär neu an und überschreibt `admin.json` mit einer vom Server akzeptierten Sitzung, statt die abgelehnten Cookies weiterzuverwenden.
  - Test: Entscheidungstest mit Stub-Status 401 und gültiger Ablaufzeit liefert „neu anmelden"; heute „wiederverwenden" (RED).

- **AC-2:** Given `admin.json` hat gültige Ablaufzeit und der Server antwortet auf die Probe mit 200 / When das E2E-Setup startet / Then werden die gespeicherten Cookies ohne Login wiederverwendet und es wird kein Login-Kontingent verbraucht.
  - Test: Entscheidungstest mit Stub-Status 200 liefert „wiederverwenden"; im Setup erfolgt kein Formular-Login.

- **AC-3:** Given die Probe scheitert mit Netzfehler oder Exception / When das E2E-Setup entscheidet / Then gilt der Zustand als ungültig (fail-closed) und das Setup meldet sich neu an, statt still weiterzulaufen.
  - Test: Entscheidungstest mit einem Stub, der wirft, liefert „neu anmelden".

- **AC-4:** Given `admin.json` fehlt oder ist abgelaufen / When das E2E-Setup startet / Then meldet es sich wie bisher per Login an und die Probe wird nicht benötigt (kein Aufruf).
  - Test: Entscheidungstest mit fehlender und mit abgelaufener temporärer Datei liefert „neu anmelden"; der Stub registriert keinen Aufruf.

- **AC-5:** Given das Setup läuft gegen einen beliebigen Server / When die Probe ausgeführt wird / Then läuft sie erst nach den Prod-Guards, über dieselbe baseURL wie die Tests und gegen `GET /api/auth/profile` (nicht den öffentlichen `/api/health`).
  - Test: Entscheidungstest prüft, dass der Stub genau mit `/api/auth/profile` gefragt wird; im Setup steht die Probe hinter den Guard-Aufrufen und nutzt `page.request`.

- **AC-6:** Given ein lokaler Stack über `ci-stack.sh` und eine absichtlich stehengelassene `admin.json` / When ein Kontrollverbund bereits in der CI gelisteter Specs zweimal läuft, mit Stack-Neustart zwischen den Zyklen / Then liefern beide Zyklen dieselben grünen Zahlen.
  - Test: Zwei-Zyklen-Lauf aus Nutzersicht (Abnahme laut Issue #2390), beide Ergebnisse im Issue dokumentiert.

- **AC-7:** Given die Doku `docs/reference/gates_und_ratschen.md` beschreibt das Setup-Verhalten / When ein Leser den Abschnitt zur Anmeldung liest / Then steht dort, dass sich das Setup neu anmeldet, wenn die Datei fehlt, abgelaufen ist oder vom laufenden Server abgelehnt wird.
  - Test: Doku-Satz vorhanden (`# doc-compliance-test`, einzige Ausnahme vom Verbot der Dateiinhalt-Checks).

- **AC-8:** Given das Setup verwirft gespeicherte Cookies / When es sich neu anmeldet / Then nennt eine kurze Konsolenzeile den Grund (z. B. abgelehnt mit Status 401, Probe fehlgeschlagen, Datei fehlt oder abgelaufen), sodass kein stiller Falsch-Rot-Lauf mehr entsteht.
  - Test: Entscheidungsfunktion liefert zu jedem „neu anmelden"-Ergebnis einen nicht leeren Grund-Text; Test prüft ihn je Fall.

## Definition of Done

- [ ] AC-1 bis AC-5 und AC-8 durch `frontend/e2e/authStateProbe.test.ts` (`node --test`) belegt; RED vor der Umsetzung nachgewiesen, Kern-Schicht grün
- [ ] AC-6: Zwei-Zyklen-Lauf gegen `ci-stack.sh` (Neustart dazwischen, `admin.json` stehen gelassen) mit gleichen grünen Zahlen in beiden Zyklen; Ergebnis im Issue #2390 dokumentiert
- [ ] AC-7: Doku-Satz in `docs/reference/gates_und_ratschen.md` nachgezogen
- [ ] Adversary-Verdict VERIFIED, alle 6 CI-Checks grün, PR gemergt

## Known Limitations

- Die Probe erkennt nur, ob der Server die Sitzung akzeptiert, nicht, ob der Nutzer die richtigen Rechte hat.
- Ein Server, der kurz nicht antwortet, führt zu einer Neuanmeldung (fail-closed); schlägt auch der Login fehl,
  bricht das Setup sichtbar ab.

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** keine
- **Rationale:** Reine Test-Infrastruktur ohne Entscheidungsfläche aus `docs/adr/`; kein Kanal-, Provider-,
  Datenmodell-, Auth- oder Deploy-Eingriff.

## Changelog

- 2026-11-11: Initial spec created (Issue #2390)
