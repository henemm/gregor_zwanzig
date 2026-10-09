# Context: fix-2159-interne-endpunkte-secret

## Request Summary
Die internen Go-Endpunkte `POST /api/internal/telegram-connect` und `POST /api/internal/premium-sms-learn`
sollen über das bestehende Go↔Python-Geheimnis (`GZ_CORE_SHARED_SECRET`, Header `X-GZ-Core-Auth`, ADR-0062)
geschützt werden statt über „Loopback + kein nginx-Header" (#2159). Mitgenommen aus #2163: Rate-Limiter
vertraut `X-Real-IP` nur bei Loopback-Absender, `Secure`-Flag am Session-Cookie unabhängig von
`X-Forwarded-Proto`, konstantzeitiger Vergleich des Telegram-Webhook-Secrets.

## Related Files
| File | Relevance |
|------|-----------|
| `internal/handler/localhost_guard.go:28-46` | `requireLocalOnly` + `isProxiedRequest` — wird ersetzt/ergänzt |
| `internal/handler/telegram_connect.go:269-271` | `PostTelegramConnectHandler(s, ts)` ruft Guard |
| `internal/handler/premium_sms_connect.go:54-56` | `PostPremiumSmsLearnHandler(s, rl)` ruft Guard (iteriert alle Nutzer) |
| `internal/router/router.go:153,164` | Routen ohne eigene Middleware; `AuthMiddleware` lässt `/api/internal/` durch (`middleware/auth.go:57`) |
| `internal/config/config.go:40` | `CoreSharedSecret` (`GZ_CORE_SHARED_SECRET`) |
| `internal/config/core_secret_gate.go:20` | Fail-Fast (<32 Zeichen), Ausnahme `TestFixtureDir` (CI-Stack) |
| `internal/coreauth/transport.go:27` | `HeaderName`; nur Senden Go→Python, **keine** Vergleichsfunktion |
| `internal/middleware/status_token.go:28` | Vorbild konstantzeitiger Vergleich (sha256 + `subtle`) |
| `api/main.py:125-160` | Python-Middleware `enforce_core_auth`, `_core_shared_secret()` (Env, sonst Settings) |
| `src/app/config.py:197,481` | `core_shared_secret`, in `_SENSITIVE_FIELDS` |
| `src/services/inbound_telegram_reader.py:635-639` | `httpx.post` auf hart `localhost:8090`, **ohne Header** |
| `src/services/inbound_sms_reader.py:78,251` | `LEARN_ENDPOINT` hart `localhost:8090`, **ohne Header** |
| `internal/middleware/ratelimit.go:99-108` | `clientIP` vertraut `X-Real-IP` ungeprüft |
| `internal/middleware/auth.go:141-152` | `SetSessionCookie`, `Secure` an `X-Forwarded-Proto`/`r.TLS` |
| `internal/handler/auth_oauth.go:54,62` | Cookie `gz_oauth_state`, gleiche Secure-Logik |
| `frontend/src/routes/login/+page.server.ts:59-65` | SvelteKit setzt Session-Cookie selbst, `secure` per `NODE_ENV` |
| `internal/handler/telegram_webhook.go:40-46` | `!=`-Vergleich des Webhook-Secrets |
| `tests/tdd/test_egress_single_dial_point.py:560-571` | Ausnahmen per `datei:ZEILE` + Höchstzahl 3 — bricht bei Zeilenverschiebung |

## Existing Patterns
- Go→Python: zentraler RoundTripper hängt `X-GZ-Core-Auth` an (ADR-0062 „ein Ort, nicht jede Aufrufstelle"); Python prüft fail-closed mit `secrets.compare_digest`.
- Konstantzeit-Vergleich in Go: `status_token.go:28`, `auth_oauth.go:102`.
- Prod/HTTPS-Kennzeichen in Go: `PublicHost` (`GZ_PUBLIC_HOST`, Default `https://gregor20.henemm.com`; CI-Stack `http://localhost:4173`) und `Env` (`GZ_ENV`).

## Dependencies
- Upstream: `config.Config.CoreSharedSecret`, `router.Deps.Config`.
- Downstream: Telegram-Webhook → Python `api/routers/webhook.py:70-88` → telegram-connect; Scheduler-Trigger `api/routers/scheduler.py:191-230` → inbound_sms → premium-sms-learn.

## Existing Specs / Doku
- ADR `docs/adr/0062-python-core-authentifiziert-gegenueber-go.md` — regelt nur Go→Python; Rückrichtung fehlt (ADR-Nachtrag oder neues ADR nötig).
- `docs/specs/bugfix/core_shared_secret_auth.md`, `docs/specs/modules/telegram_chat_id_ownership.md`, `feat_1676_s1_premium_sms_rueckkanal.md`, `fix_2154_premium_sms_verknuepfungscode.md`, `store_scope_call_guard.md`.
- `docs/reference/api_contract.md` Z.234-235, ~3521-3560 (beschreibt `requireLocalOnly`/403).

## Tests heute
- Go: `telegram_connect_localhost_guard_test.go`, `premium_sms_connect_test.go` (`TestLearnRejects…`), ~33 Handler-Aufrufe in 9 Testdateien ohne Header; `ratelimit_test.go` (`_PrefersXRealIP`); `telegram_webhook_test.go`; `internal/router/core_auth_sweep_test.go`.
- Python: kein Test prüft Header auf den Go-Aufrufen (Recorder-Fakes schlucken `headers`).

## Messbefunde (gelesen 2026-10-09)
- **nginx blockt `/api/internal/` bereits extern** (Prod Z.41, Staging Z.40: `deny all`). Der Fix ist also Verteidigung in der Tiefe — nicht eine aktuell offene Lücke. Jeder Proxy-Block setzt `X-Real-IP`, `X-Forwarded-For`, `X-Forwarded-Proto`.
- **Nebenbefund: Staging-Python ruft Prod-Go.** Beide Aufrufer zeigen hart auf `localhost:8090`; Staging-Go läuft auf 8091. Telegram-/start-Verknüpfung und Premium-SMS-Lernen auf Staging landen heute im Prod-Store (fachlich ins Leere). Mit dem Fix würde Staging zusätzlich an abweichendem Secret scheitern ⇒ Go-Basis-URL muss konfigurierbar werden.
- `#2163`-Zeilenangaben zum Secure-Flag sind veraltet; Logik liegt zentral in `SetSessionCookie`.

## Risks & Considerations
- Fail-closed: leeres `CoreSharedSecret` (CI-Stack) darf **nicht** "" == "" durchlassen.
- Signaturänderung der zwei Handler bricht ~33 Testaufrufe + `router.go` — alternativ Prüfung als Middleware auf `/api/internal/*`-Routen.
- Python braucht einen zentralen Sende-Helfer (ein Ort, ADR-0062-Geist); Egress-Ratsche hängt an Zeilennummern.
- Deploy: Go und Python müssen gemeinsam ausgerollt werden (Deploy-Script restartet alle 3 Dienste — ok).
- Secure-Flag: Kopplung an `GZ_PUBLIC_HOST`-Schema; lokale Läufe ohne Env bekommen den https-Default; SvelteKit-Login setzt Cookie separat; `gz_oauth_state` mitziehen.
- Rate-Limiter: Frontend-Server-Routen reichen `X-Real-IP` an Go durch — Anfragen kommen dann von Loopback (SvelteKit :3000), also bleibt die Kette intakt.
- Statuscode bei fehlendem/falschem Secret (401 vs 403): Python-Aufrufer unterscheiden „abgelehnt" vs „vorübergehend" nach Status (`inbound_sms_reader.py` ~293/300).

## Analysis

### Type
Bug (Sicherheitshärtung, Verteidigung in der Tiefe — nginx blockt `/api/internal/` extern bereits mit `deny all`)

### Affected Files (with changes)
| File | Change Type | Description |
|------|-------------|-------------|
| `internal/coreauth/verify.go` (o. ä. neben `transport.go`) | CREATE | `Verify(r, secret)` konstantzeitig (sha256 + `subtle`, Vorbild `middleware/status_token.go:28`) + Middleware `RequireCoreAuth(secret)`: leeres Secret ⇒ 503, fehlend/falsch ⇒ 401 |
| `internal/router/router.go:153,163` | MODIFY | die zwei `/api/internal/*`-Routen mit `RequireCoreAuth(cfg.CoreSharedSecret)` umhüllen (keine weiteren Go-Routen unter `/api/internal/`) |
| `internal/handler/localhost_guard.go` | KEEP | `requireLocalOnly` bleibt zusätzlich in den Handlern (Defense in Depth, Handler-Tests bleiben unverändert) |
| `src/app/config.py` | MODIFY | neues Feld `go_api_url` (Env `GZ_GO_API_URL`, Default `http://localhost:8090`) |
| `src/lib/go_internal.py` (Name offen) | CREATE | zentraler Python→Go-Sende-Helfer: Basis-URL aus Config, Header `X-GZ-Core-Auth` (Secret wie `api/main.py:_core_shared_secret()`: Env, sonst Settings), leeres Secret ⇒ nicht senden + loggen |
| `src/services/inbound_sms_reader.py:78,251,286-305` | MODIFY | Helfer nutzen; **401/403 als vorübergehend behandeln** (heute: jeder 4xx ⇒ Zeiger rückt vor ⇒ Garmin-Nachricht still verloren bei Fehlkonfiguration). 409/429 bleiben dauerhaft |
| `src/services/inbound_telegram_reader.py:635-639,~679` | MODIFY | Helfer nutzen; 401/503 als `error` loggen |
| `tests/tdd/test_egress_single_dial_point.py:560-571` | MODIFY | zwei `datei:ZEILE`-Ausnahmen entfallen; Helfer als benannter erlaubter Ausgang (Funktion statt Zeile), Höchstzahl senken |
| `internal/middleware/ratelimit.go:99-108` | MODIFY | `X-Real-IP` nur bei Loopback-`RemoteAddr` (SvelteKit :3000 / nginx kommen von Loopback ⇒ Kette bleibt intakt) |
| `internal/handler/telegram_webhook.go:40-46` | MODIFY | Webhook-Secret konstantzeitig vergleichen (aus #2163) |
| `internal/middleware/auth.go:142-151`, `internal/handler/auth_oauth.go:54-62` | MODIFY | `Secure` aus Schema von `Config.PublicHost` (`https://` ⇒ Secure) statt `X-Forwarded-Proto`; `r.TLS`-Zweig bleibt. `auth_magic.go` nutzt `SetSessionCookie`, kein eigener Eingriff. SvelteKit-Login (`NODE_ENV`) unberührt (aus #2163) |
| Tests Go | CREATE/MODIFY | Middleware 401/503/200 + Loopback ohne Secret ⇒ abgelehnt; `ratelimit_test.go` `_PrefersXRealIP` auf Loopback-Absender + Spoofing-Test; Webhook; Secure-Matrix (https/http) |
| Tests Python | CREATE | Helfer setzt Header + Basis-URL; SMS-Reader: 401 ⇒ Zeiger bleibt |
| `docs/adr/0062-…md` | MODIFY | Nachtrag Rückrichtung Python→Go (oder neues ADR) |
| `docs/reference/api_contract.md` Z.234-235, ~3521-3560 | MODIFY | 401/503 statt nur `requireLocalOnly`/403 |

### Scope Assessment
- Files: ~10 produktiv + ~6 Tests + 2 Doku
- Estimated LoC: produktiv ca. +150/-20, Tests ca. +250 — unter dem 250-LoC-Limit
- Risk Level: MEDIUM (zentrale Auth-/Cookie-Pfade; Fehlkonfiguration würde Telegram-`/start` und Premium-SMS-Lernen ausfallen lassen)

### Technical Approach
Ein Ticket, eine Spec, eine Auslieferung. Scheibenschnitt (Python vor Go) ist **nicht** nötig: `deploy-gregor-prod.sh` restartet alle drei Dienste gemeinsam, Prod- und Staging-`.env` enthalten `GZ_CORE_SHARED_SECRET` bereits (gemessen 2026-10-09, nur Schlüsselname geprüft). Go prüft per Middleware an den zwei Routen; Python sendet über einen zentralen Helfer (ADR-0062-Geist „ein Ort"). Statuscodes analog ADR-0062: 401 fehlend/falsch, 503 Secret nicht konfiguriert (fail-closed, nie `"" == ""`).

### Dependencies
- CI-E2E-Stack (`frontend/e2e/ci-stack.sh:37,58,66`) setzt in Go und Python dasselbe Secret; im E2E ruft nichts diese Endpunkte.
- **Betriebsschritt außerhalb des Repos:** `GZ_GO_API_URL=http://localhost:8091` in `/home/hem/gregor_zwanzig_staging/.env` ergänzen (Staging-Python ruft heute Prod-Go auf 8090 — Nebenbefund behoben). Prod braucht keinen Eintrag (Default 8090). Achtung Memory „Default == Produktionsadresse macht fehlenden Eintrag unsichtbar" ⇒ Wert auf Staging messbar machen (z. B. Log beim Start oder Health-Feld).
- Nebenhinweis: CI-Stack nutzt `GO_PORT` 8091 wie Staging (nur lokal relevant).

### Open Questions
- keine PO-Fragen; Restpunkte von #2163 (Enumeration, Timing, os.Getenv, ProxyHandler, Python-Pfadbauten, Log, .env.tpl) bleiben in #2163.
