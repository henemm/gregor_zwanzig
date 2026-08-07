# Context: fix-1289-e2e-env-minimal

## Request Summary

`frontend/e2e/start-preview.sh` lädt per `set -a; source ../../.env` alle 41 Schlüssel der
Haupt-`.env` (u.a. `GZ_SMTP_PASS`, `GZ_TELEGRAM_BOT_TOKEN`, `GZ_IMAP_PASS`,
`GZ_METEOFRANCE_APIKEY`) in den Prozess des lokalen E2E-Preview-Servers, obwohl dieser nur
einen Bruchteil davon liest. Ziel: den Kindprozess auf den tatsächlich benötigten Variablensatz
begrenzen.

## Related Files

| File | Relevance |
|------|-----------|
| `frontend/e2e/start-preview.sh` | Zu ändernde Datei — lädt aktuell blanket alle `.env`-Keys |
| `frontend/playwright.config.ts:12` | setzt `GZ_API_BASE`-Default im Playwright-Hauptprozess, spawnt `start-preview.sh` als `webServer.command` |
| `frontend/e2e/global.setup.ts:24-33` | prüft `GZ_API_BASE` gegen Prod-Guard, loggt sich per `E2E_USER`/`E2E_PASS` gegen den echten Login-Endpoint ein — der Login-Erfolg hängt an einem korrekt verifizierbaren `gz_session`-Cookie |
| `frontend/src/hooks.server.ts:16-18` | SvelteKit verifiziert `gz_session` selbst mit `env.GZ_SESSION_SECRET ?? 'dev-secret-change-me'` — **das ist die einzige echte Secret-Abhängigkeit des Preview-Prozesses** |
| `frontend/src/routes/login/+page.server.ts:10`, `frontend/src/routes/register/+page.server.ts:9` | lesen nur `!!env.GZ_GOOGLE_CLIENT_ID` (Boolean-Toggle, keine Anmeldelogik, keine Secret-Nutzung — Client-ID ist ohnehin kein Geheimnis) |
| `.env.e2e` (Repo-Root) | **git-getrackt** (kein `.gitignore`-Treffer, da Pattern `.env` nicht auf `.env.e2e` matcht), aktuell nur `GZ_TEST_FIXTURE_DIR=fixtures/openmeteo` — **darf nie ein Secret enthalten**, sonst neuer #1537-Fall |
| `internal/config/config.go:16` | Go-API: `SessionSecret` via `envconfig:"SESSION_SECRET"` mit Prefix `GZ` → `GZ_SESSION_SECRET`, Default ebenfalls `dev-secret-change-me` |
| `internal/middleware/auth.go:77-111` | `SignSession`/`validateSession` — HMAC-SHA256 mit dem Secret; Cookie ist nur verifizierbar, wenn Signierer (Go) und Prüfer (SvelteKit) denselben Wert nutzen |
| `internal/router/router.go:37,47` | Go-API nutzt `deps.Config.SessionSecret` für `AuthMiddleware` und `LoginHandler` |

## Existing Patterns

- **Playwright-Proxy-Ziel ist Staging, nicht lokal gestartet:** `frontend/e2e/apiProxyTarget.ts:12`
  und `playwright.config.ts:12` zeigen `GZ_API_BASE`/`GZ_E2E_API_PROXY_TARGET` per Default auf
  `http://localhost:8091` — den **dauerhaft laufenden Staging-Go-Server** (`gregor-api-staging`,
  systemd, `EnvironmentFile=/home/hem/gregor_zwanzig_staging/.env`). `start-preview.sh` startet
  **nur** den SvelteKit-Preview-Prozess, nicht die Go-API — die läuft bereits, unabhängig vom
  Skript, mit ihrer **eigenen** Env-Datei.
- **Gemessen: `GZ_SESSION_SECRET` ist zwischen Repo-`.env` und Staging-`.env` aktuell identisch**
  (SHA-256-Vergleich der Zeilen, kein Klartext gelesen). Das ist aber Konvention, keine erzwungene
  Garantie — der Preview-Prozess MUSS weiterhin genau diesen einen Wert aus der Haupt-`.env`
  beziehen, sonst verifiziert `hooks.server.ts` kein vom Staging-Server signiertes Cookie mehr und
  **jeder** authentifizierte E2E-Test scheitert still (Redirect-Loop auf `/login`, kein klarer
  Fehler).
- **`.env`-Ausnahmen sind die wiederkehrende Fehlerquelle in diesem Projekt** (#1537: Negation in
  `.gitignore` für `frontend/.env.test`). Konsequenz hier: keine neue Datei mit Secret-Inhalt
  anlegen, insbesondere nicht `.env.e2e` (ist bereits getrackt).
- **Referenz-Stil für gezielte Env-Weitergabe:** kein bestehendes Beispiel im Repo für "Werte aus
  `.env` gezielt herausgreifen statt blanket sourcen" — das ist Neuland für dieses Skript, aber ein
  einfaches `grep -m1 '^KEY=' .env | cut -d= -f2-`-Muster genügt.

## Dependencies

- **Upstream (was der Preview-Prozess selbst braucht):** `GZ_API_BASE` (kein Secret, bereits mit
  Inline-Default abgesichert), `GZ_SESSION_SECRET` (Secret, **muss** mit Staging-Go
  übereinstimmen), `GZ_GOOGLE_CLIENT_ID` (kein Secret), `NODE_ENV` (kein Secret, bereits separat
  exportiert).
- **Downstream (was von `start-preview.sh` abhängt):** `playwright.config.ts` (`webServer.command`),
  darüber alle ~150 Spec-Dateien in `frontend/e2e/`, die einen laufenden Preview-Server
  voraussetzen. Ein zu knapper Variablensatz bricht die gesamte lokale E2E-Suite, nicht nur
  einzelne Tests.
- **Nicht benötigt vom Preview-Prozess (verifiziert durch Grep, 0 Treffer in `frontend/`):**
  `GZ_TEST_FIXTURE_DIR` (nur Python-Core), alle SMTP-/IMAP-/Telegram-/API-Key-Variablen (0
  Fundstellen in `frontend/src` oder `frontend/e2e`).

## Existing Specs

- `docs/specs/_archive/modules/fix_1284_admin_prod_testdata.md` — führte den Staging-Proxy
  (Port 8091) und die Guard-Kette (`assertNotProdApiProxyTarget`) ein; direkter Vorgänger-Kontext
  für dieses Skript.
- Kein bestehendes Spec-Modul zu `start-preview.sh` selbst.

## Risks & Considerations

- **Größtes Risiko:** `GZ_SESSION_SECRET` versehentlich weglassen oder falsch extrahieren → alle
  authentifizierten E2E-Tests scheitern lokal, mit einer irreführenden Fehlermeldung (Redirect
  statt klarer Secret-Fehler), da `hooks.server.ts` klaglos auf den Dev-Fallback zurückfällt.
- **Zweitgrößtes Risiko:** eine neue/duplizierte Env-Datei mit dem extrahierten Secret anlegen und
  dabei versehentlich in einer getrackten Datei landen (`.env.e2e` ist bereits getrackt) — das
  wäre ein neuer #1537-Fall, diesmal selbst verursacht.
- **Testbarkeit:** Der Kern-Testlayer darf keine echten Netzwerkaufrufe machen. Eine Prüfung
  „welche Variablen landen im Kindprozess" muss ohne echten `npm run build`/`preview`-Lauf
  auskommen — die Env-Extraktionslogik muss so geschnitten sein, dass sie isoliert (z. B. per
  `bash -c 'source ...; env'` vor der letzten Zeile) prüfbar ist, ohne den Server tatsächlich zu
  starten.
- **Kein Blast-Radius auf Staging/Prod:** Das Skript läuft ausschließlich lokal (Playwright
  `webServer`), nicht als systemd-Unit — Änderungen hier berühren keine laufenden Dienste.

## Analysis

### Type
Bug (GitHub-Label `bug`) — unerwünschtes Verhalten (Secret-Überexposition), keine neue
Funktionalität.

### Vollständige Env-Lesestellen des Frontend-Server-Codes (erschöpfend gegrept, `env\.[A-Z]`
über `frontend/src`, ohne Tests)

| Variable | Datei | Secret? | Quelle |
|---|---|---|---|
| `GZ_SESSION_SECRET` | `hooks.server.ts:16` | **JA** | muss mit Staging-Go (`internal/config/config.go:16`) übereinstimmen |
| `GZ_API_BASE` | `lib/server/apiBase.ts:5` | nein (URL) | kommt NICHT aus `.env` (0 Treffer dort) — ausschließlich über Shell-Env/Playwright-Default gesetzt |
| `GZ_GOOGLE_CLIENT_ID` | `routes/login/+page.server.ts:10`, `routes/register/+page.server.ts:9` | nein (Client-ID ist kein Geheimnis) | nur Boolean-Toggle, kein E2E-Test prüft ihn |
| `NODE_ENV` | `routes/login/+page.server.ts:47`, `routes/magic-link/verify/+page.server.ts:46` | nein | bereits separat exportiert |

Kein weiterer Treffer — insbesondere **keine** SMTP-/IMAP-/Telegram-/API-Key-Variable wird vom
Frontend-Code je gelesen. Die verbleibenden 37 in `.env` gesetzten Schlüssel sind für
`start-preview.sh` beweisbar überflüssig.

### Affected Files (with changes)

| File | Change Type | Description |
|------|-------------|-------------|
| `frontend/e2e/start-preview.sh` | MODIFY | Blanket-`source ../../.env` ersetzen durch gezielten Export von genau `GZ_SESSION_SECRET` + `GZ_GOOGLE_CLIENT_ID`; `.env.e2e`-Sourcing bleibt (enthält kein Secret, ist getrackt) |
| `frontend/e2e/e2e-env.sh` (neu) | CREATE | Ausgelagerte, isoliert testbare Extraktionslogik (kein `npm run build`/`preview` darin) — `start-preview.sh` sourced sie |
| `frontend/src/lib/__tests__/e2e_env_minimal.test.ts` (neu) | CREATE | Kern-Test (kein Netz): sourced `e2e-env.sh` gegen eine Fixture-`.env`, prüft per `env`-Ausgabe, dass NUR die erlaubten Keys exportiert werden |

### Scope Assessment
- Files: 3 (1 modify, 2 create)
- Estimated LoC: ~+45/-4 (deutlich unter dem 250-LoC-Limit)
- Risk Level: **LOW** — lokal laufendes Skript, keine systemd-Unit, kein Staging-/Prod-Pfad berührt; einziges echtes Risiko ist ein falsch extrahierter `GZ_SESSION_SECRET` (durch den Kern-Test abgesichert)

### Technical Approach
1. `e2e-env.sh` liest `GZ_SESSION_SECRET` und `GZ_GOOGLE_CLIENT_ID` gezielt aus der
   Haupt-`.env` (`grep -m1 '^KEY=' … | cut -d= -f2-`) und exportiert nur diese beiden — keine
   Duplizierung des Wertes in eine zweite Datei (vermeidet einen neuen #1537-Fall über
   `.env.e2e`, die getrackt ist).
2. `start-preview.sh` sourced `e2e-env.sh` statt blanket `.env` zu sourcen; `.env.e2e`
   (unverändert, secret-frei) bleibt wie bisher.
3. Kommentar an der Stelle referenziert #1289 und die Messung (welche Variablen der
   Preview-Prozess tatsächlich liest), damit eine künftige Erweiterung bewusst erfolgt statt
   versehentlich auf Blanket-Sourcing zurückzufallen.
4. Kern-Test sourced `e2e-env.sh` mit `GZ_REPO_ENV_FILE` auf eine Scratch-Fixture umgebogen
   (kein Zugriff auf die echte `.env`, kein Netz), prüft: erlaubte Keys vorhanden, mindestens
   ein bekannter Secret-Key (`GZ_SMTP_PASS` o. ä.) explizit NICHT in der resultierenden
   Umgebung.

### Dependencies
- Kein Downstream-Bruch erwartet: `playwright.config.ts` ruft `start-preview.sh` unverändert per
  `webServer.command` auf; das Interface (welche Env-Variablen am Ende im Kindprozess sichtbar
  sind) bleibt für die 4 tatsächlich gelesenen Variablen identisch, nur die 37 unnötigen
  entfallen.
- `npm run test` (node:test, `frontend/package.json`) ist der bestehende Testrunner für den
  neuen Kern-Test — kein neues Tool nötig.

### Open Questions
Keine offenen Fragen — alle Unsicherheiten aus der Context-Phase (Secret-Übereinstimmung
Staging/Repo, tatsächlich gelesene Variablen, Tracked-Status von `.env.e2e`) wurden durch
direkte Messung geklärt.
