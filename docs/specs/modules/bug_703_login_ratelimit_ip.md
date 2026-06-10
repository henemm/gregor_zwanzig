# Spec: Login Rate-Limiter IP-Weitergabe (#703)

## Status
In Arbeit

## Problem
Der Go-Backend-Rate-Limiter für `/api/auth/login` und `/api/auth/register` ist pro Client-IP konfiguriert (30 Anfragen/Stunde). SvelteKit leitet diese Anfragen **serverseitig** weiter (`http://localhost:8090/...`) — ohne die echte Client-IP zu übermitteln. Der Rate-Limiter sieht deshalb alle Anfragen als `127.0.0.1`. Nach 30 Login-Versuchen (aller Nutzer zusammen, inkl. E2E-Tests) werden **alle** Nutzer für den Rest der Stunde gesperrt. Das Frontend übersetzt HTTP 429 fälschlicherweise als „falsches Passwort".

## Lösung

### SvelteKit-Seite
- `+page.server.ts` (Login) und `+page.server.ts` (Register): echte Client-IP via `event.getClientAddress()` als `X-Real-IP`-Header an Go weiterleiten
- HTTP 429 separat behandeln: eigene Fehlermeldung „Zu viele Versuche — bitte in einigen Minuten erneut versuchen."

### Go-Seite
Keine Änderung nötig — der Rate-Limiter liest `X-Real-IP` bereits korrekt (`ratelimit.go:101`).

## Betroffene Dateien
- `frontend/src/routes/login/+page.server.ts`
- `frontend/src/routes/register/+page.server.ts`

## Acceptance Criteria

**AC-1:** Given ein Nutzer sendet gültige Zugangsdaten über das Login-Formular / When die SvelteKit-Action die Anfrage an Go weiterleitet / Then enthält der ausgehende HTTP-Request an Go den Header `X-Real-IP` mit der echten Browser-IP des Nutzers (nicht `127.0.0.1`).

**AC-2:** Given der Go-Rate-Limiter gibt HTTP 429 zurück / When SvelteKit die Antwort verarbeitet / Then zeigt das Login-Formular die Meldung „Zu viele Versuche — bitte in einigen Minuten erneut versuchen." statt „Benutzername oder Passwort nicht korrekt.".

**AC-3:** Given ein Nutzer sendet ungültige Zugangsdaten über das Login-Formular / When Go HTTP 401 zurückgibt / Then zeigt das Formular weiterhin „Benutzername oder Passwort nicht korrekt." (keine Regression).

**AC-4:** Given ein Nutzer sendet Registrierungsdaten / When die Register-Action die Anfrage an Go weiterleitet / Then enthält der ausgehende HTTP-Request an Go den Header `X-Real-IP` mit der echten Browser-IP (selbe Korrektur wie Login).

**AC-5:** Given zwei verschiedene Nutzer mit verschiedenen IPs senden Login-Anfragen / When beide auf 127.0.0.1 gebündelt wären, wäre ein Rate-Limit möglich / Then werden ihre Anfragen nach der Korrektur über getrennte Rate-Limit-Buckets gezählt und der erste Nutzer hat kein Limit-Problem durch den zweiten.

## Changelog
- 2026-06-10: Spec erstellt (Issue #703)
