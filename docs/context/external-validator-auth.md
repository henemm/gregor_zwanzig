# Context: External Validator Auth (Issue #110)

## Request Summary

Der External Validator (`bash .claude/validate-external.sh`) startet eine isolierte `claude --print`-Session, die das Feature gegen die laufende App prüfen soll. Da Production und Staging hinter Login-Auth (`gz_session`-Cookie) liegen und der Validator keine Credentials kennt, scheitert er bei jedem Feature mit eingeloggter Route an „fehlenden Anmeldedaten" und liefert AMBIGUOUS — ein Validator, der nicht testen kann.

Ziel: Validator kann eingeloggte Routen prüfen, ohne dass im Production-Code ein Auth-Bypass entsteht und ohne dass Credentials im Repo landen.

## Related Files

| File | Relevance |
|------|-----------|
| `.claude/validate-external.sh` | Launcher — startet die isolierte Validator-Session, setzt `GZ_VALIDATION_URL`. Hier wird Cookie/Auth eingebracht. |
| `.claude/agents/external-validator.md` | Agent-Spec — beschreibt Verhalten und Isolation. Muss um Auth-Verwendung ergänzt werden. |
| `.claude/commands/5-implement.md` | Skill ruft `validate-external.sh` in Step 8 auf. Doku/Beispiele anpassen. |
| `internal/middleware/auth.go` | `AuthMiddleware`, `SignSession(userId, secret)` — exportierte HMAC-Signatur des Cookies, Format `{userId}.{ts}.{hmacSig}`. |
| `internal/handler/auth.go` | `LoginHandler` — Referenz, wie das Cookie regulär gesetzt wird (Name `gz_session`, MaxAge 86400, HttpOnly, SameSite Lax). |
| `internal/config/config.go:15` | `SessionSecret` ENV `SESSION_SECRET`, default `dev-secret-change-me`. |
| `/home/hem/gregor_zwanzig_staging/.env` | Staging-Secret `GZ_SESSION_SECRET=...` — Quelle für den HMAC. |
| `/home/hem/gregor_zwanzig/.env` | Prod-Secret (aktuell identisch zu Staging — nicht ideal, aber Status quo). |
| `data/users/<userId>/` | Test-User-Verzeichnis muss existieren, sonst LoadUser scheitert. |
| `docs/features/openspec_workflow.md` | Spec des Validator-Workflows — muss aktualisiert werden. |

## Existing Patterns

- **HMAC-Signatur statt Bypass:** `middleware.SignSession` ist bereits öffentlich exportiert und wird auch vom regulären `LoginHandler` benutzt — ein Helper kann ohne API-Call ein Cookie produzieren, das durch dieselbe Validierung läuft wie ein echtes Login.
- **Skill ruft Bash auf, Output ist sichtbar:** `5-implement.md` ruft `bash .claude/validate-external.sh` direkt auf — das Skript ist die natürliche Stelle, um vor dem `claude --print`-Spawn ein Cookie zu erzeugen und in den Prompt zu injizieren.
- **`GZ_VALIDATION_URL`-Pattern:** Ziel-Server wird via ENV gesteuert. Analog können wir `GZ_VALIDATION_USER` / `GZ_VALIDATION_COOKIE` nutzen, ohne Code-Pfade zu zerschneiden.
- **Validator-Isolation:** Agent darf weder `src/` noch `git log` lesen — alles, was er braucht, kommt im Prompt-Text. Heißt: das Cookie muss in den Prompt eingebettet werden, nicht aus einer Datei gelesen.
- **Server-Architektur:** Auth läuft im Go-Backend (`gregor-api`, Port 8090 prod / 8091 staging) hinter Nginx. Frontend (SvelteKit) liest Cookie aus dem Browser. Ein curl-/HTTP-Client mit `Cookie: gz_session=...` reicht für API-Calls und HTML-Routen.

## Dependencies

**Upstream (was wir nutzen):**
- Go-Funktion `middleware.SignSession` (HMAC-Signatur)
- ENV-Variable `GZ_SESSION_SECRET` aus dem Staging-`.env`
- Existierender Test-User in `data/users/<id>/` (Staging)

**Downstream (was uns nutzt):**
- Skill `5-implement.md` Step 8 — ruft Validator pro Feature
- Skill `6-validate.md` (Phase 7) — könnte Validator ebenfalls aufrufen
- CLAUDE.md §„External Validator" und `docs/features/openspec_workflow.md`

## Existing Specs

- `docs/features/openspec_workflow.md` — Beschreibt die Phasen inkl. External-Validator-Step (muss erweitert werden).
- `.claude/agents/external-validator.md` — Verhaltens-Spec des Agents (muss erweitert werden).

Es existiert **noch keine** dedizierte Modul-Spec für die Auth-Integration. → Phase 3 schreibt `docs/specs/modules/external_validator_auth.md`.

## Risks & Considerations

1. **Production-Test-User wäre gefährlich** — auf Prod liegen echte User-Daten. Test-User darf **nur in Staging** existieren. Validator-Default-URL wird auf `staging.gregor20.henemm.com` festgelegt; Prod-Validierung nur explizit per ENV.
2. **Secret-Leak:** `GZ_SESSION_SECRET` darf nicht ins Repo. Cookie wird **on-the-fly** im Launcher signiert (Bash + `openssl dgst -sha256 -hmac` oder kleines Go-Helfer-Binary). Quelle: `~/gregor_zwanzig_staging/.env` außerhalb des Repos.
3. **Cookie-Lifetime:** Ein signiertes Cookie ist 24h gültig — nicht vorab signieren, sondern jedes Mal neu beim Validator-Start.
4. **Idempotenter Test-User-Setup:** Setup-Skript prüft, ob User existiert, legt ihn sonst über `POST /api/auth/register` an. Kein Hard-Fail, wenn schon da.
5. **Prod-Staging-Secret-Identität:** Aktuell nutzen beide denselben `GZ_SESSION_SECRET`. Das ist ein separates Sicherheitsthema (eigener Issue), aber für #110 nutzen wir nur den Staging-Secret und nur den Staging-Endpoint.
6. **Validator-Isolation bewahren:** Cookie wird via Prompt-Text in die `claude --print`-Session injiziert, nicht via `.env`-Datei im Repo. Der Validator-Agent darf keinen Repo-Code lesen — das Prinzip bleibt.
7. **Browser- vs. API-Tests:** Cookie funktioniert für `curl`/HTTP-Calls. Falls der Validator Playwright o.ä. nutzen will, muss er das Cookie über `page.context().addCookies(...)` setzen — Hinweis in Agent-Spec.
8. **Timing (Issue #110 Kommentar):** Validator gegen Staging **nach** Auto-Deploy (Skill ist bereits angepasst). Phase 1 Context bestätigt: Pre-Push gegen `localhost`/Staging, Post-Push gegen Staging, nach `deploy-gregor-prod.sh` gegen Prod — letzteres benötigt **keinen** Test-User auf Prod (manuelle Smoke-Tests reichen, oder die User-Session des Owners).
9. **Account-Isolation:** Test-User darf keine Trips/Locations anderer User schreiben — er hat sein eigenes `data/users/validator/`-Verzeichnis und kann darin Daten frei manipulieren.
10. **Logout/Blacklist:** `BlacklistSession` ist In-Memory (`sync.Map`). Bei Service-Restart leer — also kein Problem, aber kein „forget me" möglich, falls Validator einmal auslogged. Empfehlung: Validator triggert kein Logout.

## Phase 2 — Analyse-Ergebnisse

### Aus Recherche neu hinzugekommen

1. **`openspec.yaml` schützt Validator-Dateien als `e2e_validators`** (Lines 49-52). Hooks blockieren Edits — vor jeder Änderung an `validate-external.sh` oder `external-validator.md` muss der Pfad über die Whitelist freigegeben werden, bzw. der Hook muss die Änderung zulassen, weil sie aus Phase-6/7-Workflow legitim erfolgt. **Kein Bypass!** (Memory: „Hook-Whitelist nicht editieren, Root Cause finden".)
2. **Validator wird nur in Phase 6 (`5-implement.md`) gestartet** — Phase 7 (`6-validate.md`) konsumiert nur den existierenden Report. Skill-Updates also nur an einer Stelle.
3. **`.claude/commands/e2e-verify.md` nutzt ebenfalls `GZ_VALIDATION_URL`** — gleicher ENV-Pattern, beide Skripte ziehen mit.
4. **Existierender HMAC-Helper im Test-Code:** `internal/middleware/auth_test.go:17-22` enthält bereits eine `makeSessionCookie(userId, ts, secret)`-Funktion. Exakter Twin von `SignSession`. Bestätigt: dasselbe Pattern wird intern schon zum Test-Cookie-Erzeugen genutzt.
5. **Frontend E2E hat einen funktionierenden Login-Flow:** `frontend/e2e/global.setup.ts` macht Form-Login mit `admin/test1234` → speichert Cookie via `storageState` nach `playwright/.auth/admin.json`. Das ist der **kanonische Weg**, an ein gültiges Cookie zu kommen — ohne den HMAC-Pfad zu duplizieren.
6. **Python-Tests (`tests/tdd/test_account_page.py` etc.) machen echten `httpx.post("/api/auth/login", ...)` und extrahieren das Cookie aus dem Set-Cookie-Header.** Auch hier: Login-Call, kein HMAC-Bypass.
7. **`AuthMiddleware` schützt nur `/api/*`** — Frontend HTML wird von SvelteKit separat ausgeliefert (lokal auf Port 4173, prod direkt unter `gregor20.henemm.com`). Heißt: Cookie wird nur für `/api/*`-Requests gebraucht, HTML-Smoke-Tests gehen ohne Auth.
8. **Validator-Agent hat keinen `tools:`-Header:** Tools werden ad-hoc geladen. `Bash` ist global erlaubt, `curl ... -H "Cookie: ..."` ist in `settings.local.json` bereits whitelisted. WebFetch unterstützt **keinen** Cookie-Header → `curl via Bash` ist die einzige Option für authentifizierte Requests.
9. **`secrets_guard.py`-Hook** könnte ein Cookie im Bash-Befehl als Credential flaggen → verifizieren, ggf. Whitelist-Pattern für `gz_session`-Cookies in Validator-Aufrufen.

### Strategische Konsequenz

**Cookie-Erzeugung über Login-Call statt direkt HMAC.**

Begründung:
- **Kein Code-Duplikat:** Frontend-E2E, Python-Tests und der Login-Handler nutzen alle den `POST /api/auth/login`-Pfad. Wenn der Validator denselben Pfad geht, gibt es nur **eine** Stelle, die das Cookie-Format kennt. Bei einer späteren Änderung am Cookie-Format (z.B. JWT statt HMAC) muss nur der Server ran — Validator zieht automatisch mit.
- **Kein Repo-Secret:** Nur Test-User-Username/Password in `.claude/validator.env` (gitignored). Der `GZ_SESSION_SECRET` muss **nicht** ins Validator-Skript exportiert werden.
- **Weniger Bash-Komplexität:** Keine HMAC-Bash-Implementierung mit `openssl dgst`-Boilerplate — ein `curl -c cookies.txt -d '{"username":...}' .../api/auth/login` reicht.
- **Realistischere Validierung:** Wenn der Login-Pfad kaputt geht, soll der Validator das auch merken — direkt-HMAC würde diesen Bug verstecken.

Der direkte HMAC-Pfad bleibt **nur** als Fallback denkbar, falls der Validator den Login-Endpoint selbst testet und ihn deshalb nicht voraussetzen kann. Das ist aktuell nicht der Fall.

### Test-User-Strategie

- **Username:** `validator` (oder `qa-validator`) — eindeutig, kein Konflikt mit `admin`/`default`/`test_*`-Mustern.
- **Anlegen:** Idempotent via `curl POST /api/auth/register` im Setup-Phase des Launchers — bei `409 user already exists` (siehe `RegisterHandler` Line 49) einfach weitermachen.
- **Nur Staging:** Default-`GZ_VALIDATION_URL` auf `staging.gregor20.henemm.com`. Auf Prod kein Test-User — manuelle Smoke-Tests reichen für die Final-Validation.
- **Daten:** Test-User darf in seinem `data/users/validator/`-Bereich frei Trips/Locations anlegen. Keine Cross-Contamination zu echten Usern.

### Validator-Agent-Verhalten

- Bekommt das Cookie als Wert im Prompt-Text (z.B. ein Block: `Auth-Cookie für API-Calls: gz_session=<value>`).
- Soll für eingeloggte Routen `curl -H "Cookie: gz_session=<value>" ...` nutzen.
- Public-Routen (Health, HTML) brauchen kein Cookie — bleibt unverändert.
- Falls Browser-Test (Playwright o.ä.) nötig: Hinweis in Agent-Spec mit `page.context().addCookies(...)`-Snippet.

## Scope-Schätzung

| Datei | Art | LoC |
|-------|-----|-----|
| `.claude/validate-external.sh` | Edit (Login-Call + Prompt-Erweiterung) | +30 |
| `.claude/agents/external-validator.md` | Edit (Auth-Verwendung dokumentieren) | +20 |
| `.claude/validator.env.example` | Neu (Template, gitignored) | +10 |
| `.gitignore` | Edit (`.claude/validator.env` ergänzen) | +1 |
| `.claude/commands/5-implement.md` | Edit (Hinweis zu Validator-Setup) | +10 |
| `docs/specs/modules/external_validator_auth.md` | Neu (Modul-Spec) | +60 |
| `docs/features/openspec_workflow.md` | Edit (Validator-Auth-Block) | +15 |
| `scripts/setup-validator-user.sh` | Neu (idempotenter Test-User-Setup) | +25 |

**Gesamt:** 8 Dateien, ~170 LoC. Das **überschreitet** die Soft-Limit von „4-5 Dateien, ±250 LoC" aus dem Skill marginal in der Datei-Anzahl — ist aber überwiegend Konfiguration/Doku, nicht produktiver Code. Akzeptabel.

## Risiken (verbleibend)

1. **`secrets_guard.py`-Hook** könnte den Cookie-curl als Credential-Leak flaggen — muss vor TDD verifiziert werden, ggf. Hook-Pattern erweitern (legitime Whitelist, kein Bypass).
2. **Test-User-Datenintegrität:** Bei einem späteren Daten-Schema-Rework darf der `validator`-User nicht aus Versehen migriert werden. → in `data/users/`-Skript-Audits ausnehmen.
3. **Cookie-TTL 24h:** Bei sehr langen Validator-Läufen (>24h) würde das Cookie ablaufen. Praktisch irrelevant — Validator-Sessions laufen Minuten.
4. **Staging-Prod-Secret-Identität (Status quo):** Wir nutzen nur Staging — wenn die Secrets später getrennt werden, muss der Launcher das berücksichtigen (separate Test-User pro Stage).

## Next Step

Phase 3 (`/3-write-spec`) — Modul-Spec `docs/specs/modules/external_validator_auth.md` aus diesem Plan erstellen.
