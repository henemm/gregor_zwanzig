# Context: infra-3286-mcp-server (#3286)

Stand 2026-11-24. Baut auf `docs/context/mcp-wetter-3281.md` auf.

## Request Summary

Der MCP-Konnektor „Gregor Wetter“ (#3281, gemergt) soll auf Staging von außen erreichbar und für den PO
freigeschaltet werden, danach Abnahme AC-16 in der Claude-App und Freischaltung in Produktion.

## Gemessener Ist-Stand

| Punkt | Staging | Produktion |
|---|---|---|
| `/.well-known/oauth-authorization-server` | 401 Basic-Auth (nginx) | 200 JSON |
| `/.well-known/oauth-protected-resource` | 401 Basic-Auth | 200 JSON |
| `POST /api/mcp` ohne Token | 401 Basic-Auth | 401 `Bearer resource_metadata=…` (richtig) |
| `GZ_PUBLIC_HOST` | `https://staging.gregor20.henemm.com` (richtig) | `https://gregor20.henemm.com` (richtig) |
| `GZ_MCP_USER_IDS` | fehlt in der `.env` | fehlt in der `.env` |

Der Code ist also in beiden Umgebungen live. #3281 ist bereits geschlossen (2026-11-22, automatisch durch PR #3282);
Schritt „#3281 schließen“ entfällt, stattdessen Nachweis AC-16 dort kommentieren.

## Related Files

| Ort | Relevanz |
|---|---|
| henemm-infra `nginx/staging.gregor20.henemm.com.conf` | drei neue `location`-Blöcke mit `auth_basic off` (eigener PR dort) |
| Server `/etc/nginx/sites-available/staging.gregor20.henemm.com.conf` | Live-Datei; wird **nicht** automatisch ausgerollt (henemm-infra `CLAUDE.md`), manuell kopieren |
| Server `/home/hem/gregor_zwanzig_staging/.env`, `/home/hem/gregor_zwanzig/.env` | Ort der `GZ_*`-Variablen von `gregor-api-staging` / `gregor-api` (EnvironmentFile) |
| `internal/config/admin.go`, `internal/router/router.go:306-321` | `ParseMCPUserIDs` (komma-getrennt, leer = niemand), Routen |
| `frontend/src/routes/.well-known/[...pfad]/+server.ts` | reicht genau die drei OAuth-Metadatenpfade an Go durch |

## Konten (geklärt, nicht erneut fragen)

- **Produktion: `henning`** — Admin-Konto, PO-Entscheid 2026-10-01, vom PO abgenommen (#2155).
- **Staging: `default`** — dediziertes App-Anmeldekonto (`GZ_AUTH_USER` der Staging-`.env`). `gz-staging-admin` ist nur für
  Admin-Prüfungen; `default` bleibt dort Nicht-Admin (#2155).
- Die Annahme des Issues „Konto-ID im Format `u-xxxxxxxx` über die E-Mail des PO“ trifft nicht zu: kein Treffer in beiden Datenbäumen.
- Zugang Staging hat drei Schichten (Server-Gedächtnis `reference_staging_hat_drei_zugangsschichten`): nginx-Schranke
  `GZ_VALIDATOR_*`, App-Anmeldung `GZ_AUTH_*` der **Staging**-`.env`, Postfach.

## Existing Patterns

- `auth_basic off`-Blöcke in derselben nginx-Datei: `= /api/health`, `/api/webhooks/{telegram,sms,mail}/`, je mit Begründungskommentar
  und vollständigen `proxy_set_header`-Zeilen; App authentifiziert fail-closed selbst.
- `.env`-Änderung plus Neustart nur des Go-Dienstes (Muster `GZ_ADMIN_USER_IDS`, #2155).

## Dependencies

- Upstream: OAuth-Server in Go (ADR-0128), Anmeldung `gz_session`, SvelteKit-Durchreicher.
- Downstream: claude.ai ruft Metadaten, `register`, `token` und `/api/mcp` serverseitig auf; `authorize` und `/login` ruft der Browser des PO.

## Existing Specs

- `docs/specs/modules/mcp_wetter_konnektor.md` (AC-16), `docs/adr/0128-mcp-konnektor-abfrage-schnittstelle-oauth-in-go.md`.

## Risks & Considerations

- **Öffnung eng halten:** exakte Pfade statt breiter Präfixe (`= /api/mcp`, `/api/mcp/oauth/`, `/.well-known/oauth-`); übrige Staging-Pfade
  behalten die Schranke. `satisfy any`/`deny all` aus „/api/“ und „/“ **nicht** übernehmen: mit `auth_basic off` sperrt das alle (Kommentar #2316).
- **Kein `limit_req` ungeprüft:** henemm-infra#397 (fail2ban `nginx-limit-req` sperrt claude.ai aus). Registrierung ist in Go gebremst (20/h je IP).
- **Anmeldeseite bleibt hinter der Schranke:** `/login` und Assets verlangen beim PO zuerst die nginx-Zugangsdaten. Ob der In-App-Browser der
  Claude-App den Basic-Auth-Dialog zeigt, ist offen; Ausweichweg: Konnektor einmalig im Desktop-Browser verbinden.
- **Drift:** Live-Datei und Repo unterscheiden sich derzeit nur in einem Kommentar (Telegram-Webhook); Kopieren ist unschädlich, vorher erneut `diff`.
- **Alte `*.bak`-Dateien** in `/etc/nginx/conf.d` werden nicht geladen (`*.conf`), nicht anfassen.
- **Rechte-Eintrag in `.env`:** laut Server-Gedächtnis sperrt der Auto-Modus das als „Permission Grant“; dann Freigabe des PO einholen,
  nicht umgehen. PO hat den Serverzugriff für das ganze Ticket am 2026-11-24 freigegeben (Produktion erst nach Test auf Staging).
- **Arbeitsort:** Sitzung läuft im Worktree auf dem iMac; henemm-infra-Änderung über eigenen Klon/PR, nicht im Hauptcheckout.

## Offen für die Analyse

1. Exakte `location`-Auswahl je Pfad und Upstream (8091 Go, 3001 SvelteKit), `proxy_read_timeout`.
2. Reihenfolge: nginx-PR → Staging-`.env` + Neustart → curl-Proben → Abnahme AC-16 → Produktion.
3. Automatischer Nachweis ohne PO: OAuth-Ablauf per Skript gegen Staging (Loopback-Redirect ist erlaubt); die Claude-App selbst bleibt PO-Schritt.
