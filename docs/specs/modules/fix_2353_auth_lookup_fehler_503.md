---
entity_id: fix_2353_auth_lookup_fehler_503
type: bugfix
created: 2026-09-17
updated: 2026-09-18
status: draft
version: "1.0"
tags: [auth, middleware, session]
workflow: fix-2353-auth-lookup-fehler-503
---

# Fix #2353: Auth-Middleware verwechselt Lesefehler der Gästeliste mit „nicht angemeldet"

## Approval

- [ ] Approved

## Purpose

`AuthMiddleware` behandelt aktuell zwei verschiedene Ergebnisse von `sessions.HasSession` gleich:
eine Kennung, die schlicht nicht (mehr) auf der Gästeliste steht (`!listed`, korrekt 401), und einen
Lesefehler der Gästeliste-Datei selbst (I/O-Fehler, kaputtes JSON — ein Serverfehler, keine Aussage
über die Anmeldung). Beide enden heute in `http.StatusUnauthorized`, ungeloggt. Das wirft Nutzer mit
gültiger Anmeldung bei einem vorübergehenden Serverfehler aus der App (`frontend/src/lib/api.ts:120`
springt bei jedem 401 hart auf `/login?expired=1`). Diese Spec trennt die beiden Fälle: Lesefehler
→ 503 + Log, `!listed` → weiterhin 401.

## Source

- **File:** `internal/middleware/auth.go`
- **Identifier:** `func AuthMiddleware` (Gästeliste-Prüfung, Zeilen 78-82)

## Estimated Scope

- **LoC:** ~30 (Go)
- **Files:** 4
- **Effort:** low

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `store.ErrInvalidUserID` (`internal/store/pathsafe.go`) | sentinel error | Trennt Traversal-Versuch (#2140, bleibt 401) von echtem Lesefehler (503) |
| `sessions.HasSession` (`internal/store/sessions.go:99-116`) | Store-Methode | Liefert `(false, ErrInvalidUserID)` bei unsicherer Kennung, `(false, err)` bei I/O-/Parse-Fehler, `(false, nil)` bei fehlender/nicht gelisteter Kennung |
| ADR-0060 (`docs/adr/0060-dauerhafte-anmeldung-mit-widerrufsliste.md`) | ADR | Legt die bestehenden 401-Fälle fest; bekommt hier einen Nachtrag für den neuen 503-Fall |
| `frontend/src/lib/api.ts:118-131` | Frontend-Modul | Generischer 5xx-Fehlerpfad (keine Änderung nötig) läuft bereits korrekt; nur AC-7 verifiziert das |

## Implementation Details

`internal/middleware/auth.go`, Gästeliste-Prüfung (ersetzt Zeilen 78-82). Neue Imports: `errors`,
`log`.

```go
listed, lookupErr := sessions.HasSession(userId, sessionId)
if lookupErr != nil {
    if errors.Is(lookupErr, store.ErrInvalidUserID) {
        // #2140: Traversal-Versuch bleibt 401, kein Serverfehler.
        http.Error(w, `{"error":"unauthorized"}`, http.StatusUnauthorized)
        return
    }
    // Gästeliste nicht lesbar (I/O-Fehler, kaputtes JSON) — Serverfehler,
    // keine Aussage über die Anmeldung. NIE sessionId/Cookie-Wert loggen.
    log.Printf("auth: Gaesteliste fuer Nutzer %q nicht lesbar: %v", userId, lookupErr)
    http.Error(w, `{"error":"service_unavailable"}`, http.StatusServiceUnavailable)
    return
}
if !listed {
    http.Error(w, `{"error":"unauthorized"}`, http.StatusUnauthorized)
    return
}
```

`internal/middleware/session_allowlist_test.go`: `TestCorruptAllowlistFile_Rejected` stellt die
Erwartung von `http.StatusUnauthorized` auf `http.StatusServiceUnavailable` um; Kommentar wird
präzisiert („fail-closed heißt: nicht 200, nicht zwingend 401").

Neue Testdatei `internal/middleware/session_lookup_error_test.go`: I/O-Fehler-Fall (`sessions.json`
als Verzeichnis anlegen → `os.ReadFile` scheitert mit `EISDIR`), Log-Umleitung via `log.SetOutput`,
Mandantentrennungs-Fall mit zwei Nutzern im selben `dataDir`.

`docs/adr/0060-dauerhafte-anmeldung-mit-widerrufsliste.md`, Abschnitt „Konsequenzen": ein
Nachtragssatz, kein neues ADR (siehe unten).

## Expected Behavior

- **Input:** Authentifizierte Anfrage mit korrekt signiertem, vierteiligem Anmelde-Merkmal gegen
  einen geschützten Pfad; die Gästeliste-Datei des betroffenen Nutzers ist entweder (a) lesbar und
  enthält die Kennung nicht, (b) lesbar und enthält die Kennung, oder (c) aus einem Serverfehler
  heraus nicht lesbar (I/O-Fehler oder kaputtes JSON).
- **Output:** (a) → 401 `{"error":"unauthorized"}` (unverändert). (b) → 200, Anfrage geht durch
  (unverändert). (c) → 503 `{"error":"service_unavailable"}`, `next` wird NICHT aufgerufen. Eine
  pfadunsichere Kennung (`store.ErrInvalidUserID`) bleibt in jedem Fall 401, nie 503 (#2140).
- **Side effects:** Fall (c) schreibt eine Log-Zeile mit der Nutzerkennung und dem Fehlertext, aber
  ohne Anmelde-Kennung (sessionId) oder Cookie-Rohwert. Frontend (`api.ts`) leitet bei 503 nicht auf
  `/login?expired=1` um, sondern wirft ein angereichertes Fehlerobjekt (`status: 503`) über den
  bestehenden generischen Fehlerpfad — unverändert, keine Code-Änderung im Frontend.

## Acceptance Criteria

- **AC-1:** Given eine Anmelde-Kennung steht NICHT (mehr) auf einer lesbaren Gästeliste / When eine
  Anfrage mit korrekt signiertem Merkmal eintrifft / Then antwortet die Middleware weiterhin mit 401
  (Regression, unverändertes Verhalten).
  - Test: bestehende Tests `TestNewFormatCookie_NoAllowlistFile_Returns401NotServerError` und die
    `!listed`-Fälle bleiben ohne Codeänderung grün.

- **AC-2:** Given die Gästeliste-Datei eines Nutzers ist wegen eines I/O-Fehlers nicht lesbar (z. B.
  `sessions.json` liegt als Verzeichnis statt als Datei vor) / When eine Anfrage mit korrekt
  signiertem Merkmal eintrifft / Then antwortet die Middleware mit 503 und ruft den nachgelagerten
  Handler NICHT auf.
  - Test: neuer Test in `internal/middleware/session_lookup_error_test.go` legt
    `data/users/<id>/sessions.json` als Verzeichnis an, schickt eine echte Anfrage über `authProbe`
    auf einen geschützten Pfad, prüft `rr.Code == http.StatusServiceUnavailable` und dass der
    Body/Kontext des dahinterliegenden `dummyHandler` NICHT die Nutzerkennung enthält (Beleg, dass
    `next` nicht lief).

- **AC-3:** Given zwei Nutzer im selben Datenbestand — einer mit kaputter Gästeliste, einer mit
  intakter, gelisteter Kennung / When beide je eine Anfrage mit gültigem, korrekt signiertem Merkmal
  stellen / Then bekommt der Nutzer mit kaputter Gästeliste 503, der andere unverändert 200 mit
  seiner eigenen Nutzerkennung im Kontext — die Fehlerbehandlung des einen Nutzers wirkt sich nicht
  auf den anderen aus.
  - Test: derselbe Testfall wie AC-2, erweitert um einen zweiten Nutzer mit intakter Gästeliste im
    selben `dataDir`; beide Anfragen werden nacheinander über `authProbe` gestellt und einzeln
    geprüft (Mandantentrennung).

- **AC-4:** Given ein I/O-Fehler beim Lesen der Gästeliste tritt auf / When die Middleware mit 503
  antwortet / Then enthält die geschriebene Log-Zeile die Nutzerkennung und den Fehlertext, aber
  NICHT die Anmelde-Kennung (sessionId) oder den rohen Cookie-Wert.
  - Test: `log.SetOutput` im Testfall auf einen `bytes.Buffer` umleiten (und am Ende zurücksetzen),
    Anfrage aus AC-2 auslösen, Pufferinhalt auf Vorkommen der Nutzerkennung UND auf Abwesenheit der
    verwendeten sessionId prüfen.

- **AC-5:** Given eine pfadunsichere Nutzerkennung im Anmelde-Merkmal (Traversal-Versuch, z. B.
  `../bob`) / When die Middleware `HasSession` aufruft und dabei `store.ErrInvalidUserID`
  zurückbekommt / Then bleibt die Antwort 401, nicht 503 — dieselbe Zusicherung wie bisher (#2140).
  - Test: bestehender `TestTraversalUserIDInCookie_Returns401NotServerError` bleibt ohne Anpassung
    grün (regressionsbeweisend, da `errors.Is(lookupErr, store.ErrInvalidUserID)` diesen Fall vor
    dem neuen 503-Zweig abfängt).

- **AC-6:** Given die Gästeliste-Datei enthält kaputtes JSON (halb geschriebene oder extern
  beschädigte Datei) / When eine Anfrage mit korrekt signiertem Merkmal eintrifft / Then antwortet
  die Middleware jetzt mit 503 statt bisher 401 — die Positivkontrolle mit intaktem Datenbestand
  bleibt unverändert 200.
  - Test: bestehender `TestCorruptAllowlistFile_Rejected` wird auf die Erwartung 503 umgestellt; die
    Positivkontrolle im selben Test bleibt unverändert 200.

- **AC-7:** Given die Auth-Middleware antwortet mit 503 / When `frontend/src/lib/api.ts` diese
  Antwort verarbeitet / Then leitet sie den Nutzer NICHT auf `/login?expired=1` um, sondern wirft ein
  Fehlerobjekt mit `status: 503`, das über den bestehenden generischen Fehlerpfad läuft.
  - Test: neuer `node --test`-Test `frontend/src/lib/__tests__/apiServerErrorNoRedirect.test.ts`.
    Nach dem Muster von `apiSchreibsperre.test.ts` wird `globalThis.window` vor dem (dynamischen)
    Import von `api.ts` durch einen minimalen Stand-in mit beschreibbarem `location.href` ersetzt
    (unter `node:test` existiert kein DOM). `globalThis.fetch` liefert eine echte `Response`-Instanz
    mit Status 503 (kein `Mock()`/`vi.fn()` — ein nachgebildeter, aber echter HTTP-Antwortwert,
    analog zum bestehenden `fakeTripServer.ts`-Muster). `assert.rejects(api.get(...))` prüft, dass
    der geworfene Fehler `status === 503` trägt; anschließend wird geprüft, dass
    `window.location.href` unverändert geblieben ist (kein Sprung nach `/login`).

## Known Limitations

- Ein extern beschädigtes `sessions.json` (kaputtes JSON) ist wegen des atomaren Schreibens in
  `writeFileLogged` (tmp + rename, `internal/store/write.go:35`) praktisch unerreichbar; der
  realistische Live-Pfad ist ein vorübergehender I/O-Fehler (Rechte, Dateihandle-Erschöpfung). AC-6
  deckt den JSON-Fall dennoch ab (Regressionsschutz für `TestCorruptAllowlistFile_Rejected`).
- Kandidat C (Fehler-Typisierung: I/O-Fehler → 503, JSON-Parse-Fehler → weiterhin 401) wurde in der
  Analyse geprüft und verworfen: Mehraufwand für einen praktisch unerreichbaren Fall, und ein 401 im
  JSON-Fall würde den Nutzer in einen Neu-Login treiben, der an derselben kaputten Datei erneut
  scheitert.
- Außerhalb des Scopes: `internal/handler/auth_corrupt_userjson_test.go` (401 bei kaputter
  `user.json` im LOGIN-Pfad — bewusste Enumerations-Abwehr, anderes Muster, nicht Teil dieses Fixes).
  Frontend-SSR (`hooks.server.ts` → `verifySession`) prüft nur die HMAC-Signatur, keinen
  Store-Zugriff — von diesem Fix nicht betroffen, keine Änderung nötig.
- `docs/specs/modules/session_allowlist.md` beschreibt weiterhin ausschließlich die 401-Fälle
  (widerrufen/manipuliert/unbekannt/Alt-Format) — bewusst unverändert, da der neue 503-Fall kein
  Gültigkeits-/Anmeldeverhalten ist, sondern eine Server-Verfügbarkeitsfrage; dokumentiert wird er
  stattdessen im ADR-Nachtrag (siehe unten).

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** ADR-0060 (Nachtrag im Abschnitt „Konsequenzen", kein neues ADR)
- **Rationale:** ADR-0060 legt fest, dass eine Anfrage mit widerrufenem, manipuliertem, unbekanntem
  oder im Altformat vorliegendem Merkmal 401 liefert — ein Lesefehler der Gästeliste bei einem
  gültig signierten Merkmal ist davon nicht erfasst und war eine stille Lücke. Der Fix ändert keine
  Grundsatzentscheidung (Cookie-Format, Prüf-Reihenfolge, Widerrufs-Mechanik bleiben unverändert),
  sondern schärft eine bestehende Fehlerbehandlung um einen bisher unbenannten Fall — dafür genügt
  ein Nachtragssatz statt eines neuen ADR. Formulierungsvorschlag für den Nachtrag: „Ein Lesefehler
  der Gästeliste bei einem gültig signierten Merkmal liefert 503, kein 401 — ein Serverfehler ist
  keine Aussage über die Anmeldung. Eine pfadunsichere Nutzerkennung (Traversal, #2140) bleibt 401."
  `tests/test_adr_index_drift.py` ist nicht betroffen, da der Index-Eintrag zu 0060 unverändert
  bleibt (nur der ADR-Dateiinhalt bekommt den Nachtrag).

## Changelog

- 2026-09-17: Initial spec created
- 2026-09-18: Implementiert, Adversary VERIFIED (F001/F002 Testlücken behoben)
