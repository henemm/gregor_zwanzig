# Context: fix-2353-auth-lookup-fehler-503

**Issue:** #2353 — Auth-Middleware verwechselt Lesefehler der Gästeliste mit „nicht angemeldet" (401 statt 5xx)
**Herkunft:** Nebenbefund #1199 (2026-09-06, Adversary zu #2128), PO-Auftrag 2026-09-17.

## Analysis

### Type
Bug

### Root Cause (verifiziert)
`internal/middleware/auth.go:78-82`: `if lookupErr != nil || !listed → 401`. Ein Lesefehler der
Gästeliste (`internal/store/sessions.go:47-64`, alles außer `IsNotExist` propagiert) wird als
„nicht angemeldet" maskiert und nicht geloggt. Frontend (`frontend/src/lib/api.ts:120`) springt bei
jedem 401 hart auf `/login?expired=1` — der Nutzer wird trotz gültiger Anmeldung rausgeworfen.

Entkräfteter Teil des Originalbefunds: der Gerätespeicher wird bei `expired=1` NICHT geräumt
(`frontend/src/routes/login/+page.svelte:40-47`, `frontend/src/lib/pwa/geraetespeicher.ts:18-41`,
AC-12/AC-19 aus #2128 — kamen nach der Beobachtung).

### Fehlerquellen in `HasSession`
| Quelle | Bewertung | Ziel-Antwort |
|---|---|---|
| `store.ErrInvalidUserID` (`sessionsPath`, Traversal #2140) | ungültiges Merkmal, kein Serverfehler | **401** (unverändert; `TestTraversalUserIDInCookie_Returns401NotServerError` bleibt) |
| I/O-Fehler `os.ReadFile` (Rechte, EISDIR, Handles) | vorübergehender Serverfehler | **503** + Log |
| `json.Unmarshal`-Fehler (kaputte Datei; Schreiben atomar → nur externe Beschädigung) | dauerhafter Serverfehler, Neu-Login hilft nicht | **503** + Log |
| `!listed` ohne Fehler | abgemeldet/widerrufen | **401** (unverändert) |

### Affected Files (with changes)
| File | Change Type | Description |
|------|-------------|-------------|
| `internal/middleware/auth.go` | MODIFY | `errors.Is(lookupErr, store.ErrInvalidUserID)` → 401; anderer `lookupErr` → 503 + `log.Printf` (userId + Fehler, NIE sessionId/Cookie); `!listed` → 401 |
| `internal/middleware/session_allowlist_test.go` | MODIFY | `TestCorruptAllowlistFile_Rejected`: Erwartung 401 → 503 (Positivkontrolle + „nicht 200" bleiben) |
| `internal/middleware/session_allowlist_test.go` (oder neue Testdatei) | CREATE | I/O-Fehler-Test (`sessions.json` als Verzeichnis → EISDIR): 503, `next` NICHT aufgerufen, Log-Zeile ohne sessionId; Regression: `!listed` → 401; zwei Nutzer |
| `docs/adr/0060-dauerhafte-anmeldung-mit-widerrufsliste.md` | MODIFY | Nachtragssatz: Lesefehler bei gültigem Merkmal → 503, kein 401 |

**Explizit AUSSERHALB des Scopes:** `internal/handler/auth_corrupt_userjson_test.go:37/56` (401 bei
kaputter `user.json` im LOGIN-Pfad — bewusste Enumerations-Abwehr, anderes Muster). Frontend: keine
Änderung (5xx läuft in `api.ts` generisch: Meldung, kein Redirect; Service-Worker cached nur 200;
Offline-Ansicht/Gerätespeicher unberührt). Frontend-SSR (`hooks.server.ts` → `verifySession`) prüft
nur HMAC, kein Store-Zugriff — nicht betroffen.

### Scope Assessment
- Files: 3–4
- Estimated LoC: +25/-5 (Go) — weit unter 250
- Risk Level: LOW

### Technical Approach
Kandidat B (Plan-Bewertung): Fehlerklassen in der Middleware trennen. 503 ist ebenso fail-closed
wie 401 (gewährt nichts), macht den Serverfehler aber sichtbar (Log) und hält den Nutzer in der App
(nächster Abruf versucht es erneut). Kein Informationsleck: 503 ist erst NACH erfolgreicher
HMAC-Prüfung erreichbar. `prod_selftest.py` (`AUTH_REQUIRED_STATUSES = {401, 403}`) und
`check-gregor20.sh` (`/health`) nicht betroffen. Kandidat C (Fehler-Typisierung, JSON-Fehler weiter
401) abgelehnt: Mehraufwand für praktisch unerreichbaren Fall, und 401 würde dort den Nutzer in einen
Login treiben, der an derselben Datei scheitert.

### Dependencies
- ADR-0060 / `docs/specs/modules/session_allowlist.md:91`: 401 dort nur für widerrufen/manipuliert/
  unbekannt/Alt-Format festgelegt — Lookup-Fehler bei gültigem Merkmal nicht erfasst ⇒ Nachtrag,
  kein neues ADR.
- #2140-Zusicherung (Traversal → 401, nie 5xx) bleibt über `errors.Is` erhalten.

### Open Questions
- keine (Traversal bleibt 401 — die Ticket-Formulierung „503 … ebenso ein Nein" war Rückversicherung,
  kein Mandat; Spec legt das fest)
