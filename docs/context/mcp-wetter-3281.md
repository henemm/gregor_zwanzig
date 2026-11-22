# Kontext: MCP-Konnektor „Gregor Wetter“ (#3281)

Stand 2026-11-22. Analyse für die Spec.

## Auftrag (PO-Entscheidungen 2026-11-22)

- Remote-MCP-Konnektor, den der PO in der Claude-App (Handy/Web) hinzufügt; freie Wetterfragen zu beliebigen Orten
  („Regnet es in den nächsten 2 Stunden in Frankfurt am Main?“, „Wie viel Sonne hat Münster in den nächsten 3 Tagen?“).
- Zunächst nur für den PO; **kein** Zugriff auf Trips, Orte, Vergleiche, Empfänger oder sonstige Nutzerdaten.
- Rohdaten: Gregor löst den Ort auf und liefert stündliche Werte in Ortszeit für den gefragten Zeitraum; Claude
  interpretiert selbst. Keine Ampel, keine Bewertung, kein Gregor-Renderer.
- Anmeldung 1:1 nach Vorbild Frieda (henemm/frieda-reist): `engine/oauth.py` (OAuth 2.1, ~360 Zeilen stdlib) und
  MCP-JSON-RPC in `engine/konnektor.py` (`frieda_antwort`, `PROTOKOLLE`), mit claude.ai erprobt. Statt Friedas
  E-Mail-Code-Anmeldung meldet sich der Nutzer mit seinem bestehenden Gregor-Konto an.

## Was es gibt / was fehlt

| Baustein | Ist-Stand | Bedarf |
|---|---|---|
| Inbound-Befehle (Mail/SMS/Telegram) | `src/services/trip_command_processor.py`, trip-gebunden | nicht nutzbar, keine Freitext-Ortsfragen |
| Login | Go, Cookie `gz_session`, 6 Wege, `issueSession` (`internal/handler/auth.go:396`), Login-Seite mit `?redirect=` (`frontend/src/routes/login/`, `safeRedirectPath`) | `/authorize` prüft Session, sonst Umleitung auf Login mit Rücksprung |
| Bearer-Token / OAuth-Server | gibt es nicht (Google OAuth nur als Client) | neu, nach Frieda |
| Nutzer-Beschränkung | `GZ_ADMIN_USER_IDS` + `RequireAdmin` (ADR-0078), fail-closed | eigene Env-Allowlist `GZ_MCP_USER_IDS` nach demselben Muster |
| Kontosperre | `disabled` (ADR-0080) | muss auch für Tokens wirken |
| Geocoding Freitext | Nominatim nur als Fallback in Google-Maps-Links (`internal/resolver/googlemaps.go:116`); Host schon im Egress-Inventar | Freitext-Ortssuche (Kandidaten mit Name, Land, lat/lon, Zeitzone) über abgeschotteten Client (ADR-0114) |
| Wetterabruf | Go `GET /api/forecast` (eigener Go-Provider, UTC + `timezone`), Python `GET /forecast` (`NormalizedTimeseries`, naive UTC) | Rohdaten in Ortszeit, kompakte Feldauswahl mit Einheiten |
| Sonnenstunden | kein Feld; abgeleitet aus `dni_wm2 > 120 W/m²` (`src/app/metric_catalog.py:679`, `src/services/weather_metrics.py:28`) | je Stunde mitliefern (Metrik-Wissen bleibt im Python-Katalog, ADR-0127) |
| Kontingent | `user_interactive` 1500/Nutzer/Tag (ADR-0117), Mengenbremse `vorhersage` 60/min (ADR-0114) | jeder Wetterabruf bucht wie `/api/forecast` |
| Ablage | Dateien unter `GZ_DATA_DIR`, keine DB; Sessions `data/users/<id>/sessions.json` mit Datei-Sperre (ADR-0060) | Clients, Codes, Tokens (nur Hash) als Dateien |

## Schutzschichten, die ein MCP-/OAuth-Pfad durchlaufen muss (Go)

- `AuthMiddleware` (`internal/middleware/auth.go:42-66`): öffentliche Ausnahmen fest verdrahtet → MCP/OAuth-Pfade ergänzen.
- `OriginGuard`, `RequireJSONBody`, `LimitBody` (`internal/router/router.go:54-60`); Ausnahme nur `IsMachinePath`
  (`internal/middleware/request_guard.go:30-36`). `/token` und `/register` sind form-/JSON-Aufrufe von claude.ai ohne
  Browser-Origin, `/authorize` POST ist ein Browser-Formular derselben Herkunft.
- SvelteKit-Durchreicher reicht kein `Authorization` weiter (`frontend/src/lib/server/apiPfad.ts:84-90`); `/api/*`
  geht per nginx direkt an Go, das genügt.
- **Root-Pfade `/.well-known/oauth-*`** gehen per nginx an SvelteKit, nicht an Go. Lösung im Repo: SvelteKit-Route
  unter `/.well-known/` reicht an Go durch (kein Eingriff in henemm-infra nötig).
- **Staging** hat vorgeschaltete Basic-Auth; MCP-/OAuth-/well-known-Pfade brauchen `auth_basic off`-Ausnahmen in
  henemm-infra (`nginx/staging.gregor20.henemm.com.conf`), sonst ist kein Test mit der Claude-App auf Staging möglich.

## Technische Entscheidung (Tech Lead)

- **OAuth-Server und MCP-Endpunkt in Go**: Go besitzt Auth, Sessions, Kontosperre, Allowlists, Kontingent-Anbindung
  und das öffentliche Routing. Friedas `oauth.py` wird inhaltlich 1:1 übertragen (Endpunkte, Redirect-Allowlist
  `https://claude.ai/api/mcp/auth_callback` + Loopback, DCR, CIMD von `claude.ai`, PKCE S256 Pflicht, `iss` in der
  Antwort, Refresh-Rotation mit Token-Familie, Tokens nur als Hash, Zustimmungsseite).
- **Wetter-Domäne bleibt in Python** (ADR-0127): neuer interner Core-Endpunkt liefert für lat/lon + Zeitraum die
  kompakten Stundenwerte in Ortszeit inkl. abgeleiteter Sonnenminuten; Go reserviert vorher das Kontingent.
- **Ortssuche in Go** (Resolver, abgeschotteter Client, Nominatim, Mengenbremse `aufloesen`).
- **Transport**: Streamable HTTP, nur POST mit JSON-Antwort, GET → 405 (wie Frieda).
- **Werkzeuge**: `ort_suchen` (Kandidaten) und `wetter` (Ort als Text oder Koordinaten, Zeitraum, optional Felder).
- Neues ADR: MCP-Konnektor ist Abfrage-Schnittstelle, **kein** Kanal im Sinne ADR-0095; erster OAuth-Server in Gregor.

## Risiken

- nginx-Ausnahmen auf Staging liegen im Fremd-Repo henemm-infra.
- Umfang > 250 LoC → zwei Scheiben (1: Ortssuche + Wetter-Datenweg, 2: OAuth + MCP).
- Session-Cookie `SameSite=Lax`: Top-Level-Navigation von claude.ai auf `/authorize` trägt das Cookie, POST der
  Zustimmung kommt von derselben Herkunft.
