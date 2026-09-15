# Context: Legacy-Session-Zweig (LegacyRevokedAt) nach ADR-0060 entfernen

## Request Summary

ADR-0060 hat am 2026-09-06 die dauerhafte Anmeldung (Gästeliste je Nutzer) eingeführt und
das alte dreiteilige Anmelde-Merkmal (`{userId}.{timestamp}.{hmacSig}`, 24 h Gültigkeit)
abgelöst. Der Übergangs-Code, der alte Merkmale beim Zugriff noch akzeptiert und still auf
das neue Format hebt, ist laut ADR spätestens 24 h nach dem Deploy verzichtbar — dieser
Zeitpunkt ist seit über einer Woche verstrichen. Issue #2262 fordert den ersatzlosen Rückbau
in `internal/middleware/auth.go` (14 Fundstellen) sowie den Vermerk in ADR-0060.

## Related Files

| File | Relevance |
|------|-----------|
| `internal/middleware/auth.go` | Trägt den Legacy-Zweig: `legacySessionValid`, `upgradeLegacySession`, den `isNew`-Verzweigungspunkt in `AuthMiddleware`, `SignSession` (alte Signierfunktion), Konstante `legacyMaxAgeSeconds`. |
| `internal/store/sessions.go` | Feld `LegacyRevokedAt` in `sessionFile`, Methode `LegacyRevokedAt(userId)`, Methode `RevokeLegacySessions`, Schreiben von `LegacyRevokedAt` in `ClearSessions`. |
| `internal/handler/auth.go:660-673` | `LogoutHandler`: verzweigt bei leerer `sessionId` (= altes Merkmal) auf `RevokeLegacySessions` statt `RemoveSession`. |
| `frontend/src/lib/auth.ts` | Zweite, unabhängige Prüfstelle. `verifySession` akzeptiert bislang BEIDE Formate (3-teilig alt, 4+-teilig neu) und zerlegt von rechts. `LEGACY_MAX_AGE_SECONDS`-Konstante nur fürs alte Format relevant. |
| `internal/middleware/sign_session_test.go` | Testet explizit das alte Format (`SignSession`, `isNew`-Rückgabewert von `validateSession`) — nach dem Rückbau gegenstandslos, muss entfernt/ersetzt werden. |
| `internal/handler/logout_revocation_test.go:575,610,642` | Testet den Widerruf ALTER Merkmale beim Logout (`RevokeLegacySessions`-Pfad) — nach dem Rückbau gegenstandslos. |
| `internal/router/legacy_subscription_routes_removed_test.go:77` | Nutzt `SignSession` NICHT um Legacy-Verhalten zu testen, sondern nur als bequemen Weg zu einem gültigen Auth-Cookie. Muss auf das neue Format umgestellt werden (`SignSessionWithID` + `AddSession`), sonst schlägt der Test nach dem Rückbau grundlos fehl. |
| `internal/router/briefing_subscription_test.go:104` | Gleiche Lage: `SignSession` nur als Cookie-Helfer, nicht als Legacy-Test. Muss mit umgestellt werden. |
| `internal/middleware/session_allowlist_test.go` | Testet bereits den `isNew`-Rückgabewert von `validateSession` für BEIDE Fälle — nach dem Rückbau hat `validateSession` kein Alt-Format mehr zu erkennen; der Legacy-Fall-Teil des Tests entfällt, der Neu-Format-Teil bleibt. |
| `docs/adr/0060-dauerhafte-anmeldung-mit-widerrufsliste.md` | Beschreibt den Migrationspfad und sagt explizit: „der Legacy-Zweig kann danach ersatzlos entfallen". AC-3 verlangt einen Vermerk „erledigt am ⟨Datum⟩" hier. |
| `docs/reference/api_contract.md:2381` | Dokumentiert `legacy_revoked_at` als Feld — muss nach dem Rückbau als entfernt/historisch markiert werden (kein API-Vertrag mehr, da das Feld nicht mehr geschrieben/gelesen wird). |

## Existing Patterns

- **Zwei getrennte Prüfstellen für dasselbe Cookie** (Go-Backend `internal/middleware/auth.go`,
  Frontend-Server `frontend/src/lib/auth.ts`) — beide müssen bei jeder Format-Änderung
  synchron bleiben (ADR-0060 nennt das explizit als vorherige strukturelle Divergenz, die
  behoben wurde). Der Rückbau muss daher **beide Stellen gleichzeitig** ändern, sonst
  akzeptiert eine Seite ein Format, das die andere schon ablehnt.
- **`SessionStore`-Interface in der Middleware** (`internal/middleware/auth.go:38-43`)
  entkoppelt die Middleware vom konkreten Store — beim Rückbau muss `LegacyRevokedAt` aus
  diesem Interface UND aus der `*store.Store`-Implementierung verschwinden, sonst bleibt die
  Schnittstelle breiter als nötig (unbenutzte Methode).
- **`validateSession` liefert `(userId, sessionId, issuedAt, isNew, ok)`** — `isNew`
  unterscheidet aktuell neues vs. altes Format. Nach dem Rückbau gibt es nur noch ein
  Format; die Signatur kann vereinfacht werden (kein `isNew` mehr nötig), was Rückwirkungen
  auf alle Aufrufer/Tests hat, die `isNew` auswerten.

## Dependencies

- **Upstream:** ADR-0060 (Entscheidung, dass der Legacy-Zweig zeitlich befristet ist),
  ADR-0030 (die ursprüngliche 24h-Session, die ADR-0060 abgelöst hat).
- **Downstream:** Keine anderen Features hängen vom Legacy-Zweig ab — er ist reine
  Übergangs-Logik ohne Produktfunktion. Der Abmelde-Fluss (`LogoutHandler`) verzweigt
  aktuell auf ihn, muss danach nur noch den Gästelisten-Pfad kennen.

## Existing Specs

Keine dedizierte Spec-Datei unter `docs/specs/modules/` für Sessions/Auth gefunden — die
Anmelde-Logik ist in ADR-0060 spezifiziert, nicht in einer separaten Modul-Spec.

## Risks & Considerations

- **Kritischer Pfad:** Ein Fehler in der Anmeldeprüfung sperrt alle Nutzer aus oder lässt
  Unbefugte durch. Änderungen an `AuthMiddleware`/`verifySession` brauchen sorgfältige
  Tests mit echten (aktuellen) Cookies vor und nach der Änderung.
- **Bestandsdaten:** Manche `sessions.json`-Dateien tragen noch `legacy_revoked_at`. Kein
  Migrationsskript nötig — das Feld wird beim nächsten Schreiben der Datei (jede
  Session-Änderung durchläuft `writeSessionFile`) stillschweigend nicht mehr mitgeschrieben,
  sobald es aus dem Go-Struct entfernt ist (Read-Modify-Write-Prinzip aus CLAUDE.md bleibt
  gewahrt, da das Feld nie befüllt zurückgeschrieben wird).
- **Tests, die nur zufällig den Legacy-Pfad nutzen** (`briefing_subscription_test.go`,
  `legacy_subscription_routes_removed_test.go`): brechen sonst grundlos, obwohl sie mit dem
  eigentlichen Thema des Rückbaus nichts zu tun haben. Müssen im selben Zug auf
  `SignSessionWithID` + `AddSession` umgestellt werden.
- **AC-3 aus dem Issue** verlangt einen Vermerk in ADR-0060 selbst — das ist eine
  Doku-Änderung im selben PR, kein separates Ticket.
- **`docs/reference/api_contract.md`** erwähnt `legacy_revoked_at` als Feld — sollte im
  selben Zug aktualisiert werden, damit die Referenz nicht auf ein nicht mehr existierendes
  Feld verweist (verhindert spätere Verwirrung, ist aber kein hartes AC aus dem Issue).
