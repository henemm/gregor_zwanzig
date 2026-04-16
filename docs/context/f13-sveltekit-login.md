# F13 Phase 2b: SvelteKit Login-Umbau

## Analyse-Ergebnis (2026-04-15)

### Ist-Zustand
- Login-Action prüft `GZ_AUTH_USER`/`GZ_AUTH_PASS` aus ENV
- `signSession()` wird client-side aufgerufen mit hardcoded `userId = 'default'`
- Cookie wird von SvelteKit direkt gesetzt

### Soll-Zustand
- Login-Action ruft `POST http://localhost:8090/api/auth/login` auf
- Go-Backend prüft Credentials (bcrypt), setzt Cookie mit echtem userId
- SvelteKit extrahiert `Set-Cookie` aus Go-Response und setzt ihn im Browser
- `signSession` Import entfällt, ENV-Credentials nicht mehr nötig

### Betroffene Dateien (1)

| Datei | Änderung | LoC |
|-------|----------|-----|
| `frontend/src/routes/login/+page.server.ts` | Login-Action umbauen | ~25 LoC (Rewrite) |

### Keine Änderung nötig
- `hooks.server.ts` — validiert Cookie weiterhin (gleicher Cookie, gleiches Format)
- `auth.ts` — `verifySession()` wird vom Hook weiter gebraucht, `signSession()` wird obsolet

### Risiken
- Cookie-Weiterleitung: Go setzt Cookie auf Response, SvelteKit muss ihn an Browser weitergeben
- Secure-Flag: Go setzt `Secure` basierend auf `X-Forwarded-Proto`, SvelteKit Proxy muss Header weiterleiten
