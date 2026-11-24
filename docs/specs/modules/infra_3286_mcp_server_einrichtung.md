---
entity_id: infra_3286_mcp_server_einrichtung
type: module
created: 2026-11-24
updated: 2026-11-24
status: draft
version: "1.0"
workflow: infra-3286-mcp-server
tags: [infra, mcp, nginx, staging, oauth]
---

# Server-Einrichtung MCP-Konnektor „Gregor Wetter“ (#3286)

## Approval

- [ ] Approved

## Purpose

Der MCP-Konnektor „Gregor Wetter“ (#3281, gemergt, ADR-0128) ist im Code live, auf Staging aber von außen nicht erreichbar, weil die nginx-Basic-Schranke die OAuth-Pfade blockt, und für kein Konto freigeschaltet (`GZ_MCP_USER_IDS` fehlt). Diese Spec öffnet auf Staging genau die drei nötigen Pfadgruppen, schaltet das Konto `default` frei, belegt den Ablauf per Skript von außen, führt die PO-Abnahme AC-16 aus `mcp_wetter_konnektor.md` herbei und schaltet danach Produktion für `henning` frei.

## Source

- **File:** `nginx/staging.gregor20.henemm.com.conf` (Repo henemm-infra), `.claude/tools/staging_mcp_pruefen.py` (neu), `.env.example`
- **Identifier:** drei `location`-Blöcke mit `auth_basic off`; Skript `staging_mcp_pruefen.py`; Variable `GZ_MCP_USER_IDS`

> **Schicht-Hinweis:** Keine Änderung an Go-, Python- oder Frontend-Code. Betroffen sind nginx-Konfiguration (Repo henemm-infra), ein Prüfwerkzeug unter `.claude/tools/`, ein Kern-Test unter `tests/tdd/` und `.env.example`. Der Go-Code (`internal/mcp/`, `internal/config/admin.go`, `internal/router/router.go`) und der SvelteKit-Durchreicher (`frontend/src/routes/.well-known/[...pfad]/+server.ts`) bleiben unverändert.

> **Querschnitts-Prüfpunkte:**
> - **Trip/Ortsvergleich-Teilung:** nicht betroffen, es entsteht keine Komponente mit Trip- oder Compare-Pendant.
> - **Mandantentrennung:** wird live mit zwei Konten belegt (`default` gelistet, `gz-staging-admin` nicht gelistet, AC-5); `user_id` stammt aus dem Auth-Kontext, kein Fallback auf `"default"` im Code.
> - **Kanäle:** nicht betroffen, kein Briefing- oder Alarm-Inhalt (E-Mail, Telegram, SMS, Premium-SMS unverändert).

## Estimated Scope

- **LoC (ehrliche Schätzung):** henemm-infra ca. +130 (Conf ca. 50, Textvertrag-Test ca. 80); Repo gregor_zwanzig ca. +215 (`.env.example` ca. 5, Probe-Skript ca. 120, Kern-Test ca. 90). Summe ca. +345.
- **Grenzüberschreitung offen ausgewiesen:** Über beide Repos liegt die Summe über der Grenze von ±250. Je Repo bleibt jeder PR darunter, deshalb wird in **zwei PRs in zwei Repos** geliefert (henemm-infra; gregor_zwanzig). Das Probe-Skript wird bewusst knapp gehalten (keine eigene Argument-Bibliothek, keine Berichtsdatei). Wächst es über ca. 150 Zeilen, wird vor dem Weiterbau neu geschätzt.
- **Files:** 5 versioniert (2 im henemm-infra-Repo, 3 im gregor_zwanzig-Repo) plus 3 Live-Dateien ohne Versionierung (Staging-nginx-Datei, beide `.env`).
- **Effort:** medium. Risiko MEDIUM (öffentliche Öffnung auf Staging, Rechte-Eintrag in Produktion; Rollback einfach).
- **Scope-Detektor:** `.env.example` fällt in `.claude/hooks/_e2e_paths.py` (else-Zweig) unter `backend`, nicht unter docs-only. Der gregor_zwanzig-PR braucht daher den normalen Staging-Nachweis. `.claude/tools/` und `tests/` allein wären docs-only.

## Scope

### Affected Files

| File | Change Type | Description |
|------|-------------|-------------|
| henemm-infra `nginx/staging.gregor20.henemm.com.conf` | MODIFY | drei `location`-Blöcke mit `auth_basic off` (ca. +50) |
| henemm-infra `tests/test_staging_mcp_nginx.py` | CREATE | Textvertrag als Regressionsschutz, Muster `tests/test_mta_sts_policy.py` (ca. 80) |
| `.env.example` | MODIFY | `GZ_MCP_USER_IDS=` mit Kommentar nach `GZ_ADMIN_USER_IDS` (Zeile 50, ca. +5) |
| `.claude/tools/staging_mcp_pruefen.py` | CREATE | Außen-Probe und OAuth-Ablauf gegen Staging, Muster `.claude/tools/staging_befehl_pruefen.py` (ca. 120) |
| `tests/tdd/test_staging_mcp_pruefen.py` | CREATE | Kern-Test der Auswertelogik gegen echten lokalen HTTP-Server, keine Mocks (ca. 90) |
| Server: Staging-nginx-Datei `/etc/nginx/sites-available/staging.gregor20.henemm.com.conf` | MODIFY (live, nicht versioniert) | Kopie der Repo-Datei nach Sicherung |
| Server: `/home/hem/gregor_zwanzig_staging/.env`, `/home/hem/gregor_zwanzig/.env` | MODIFY (live, nicht versioniert) | `GZ_MCP_USER_IDS=default` bzw. `=henning` |

### Estimated Changes

- Files: 5 versioniert (2 henemm-infra, 3 gregor_zwanzig), 3 Live-Dateien
- LoC: +345/-0 (henemm-infra +130, gregor_zwanzig +215)

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `docs/specs/modules/mcp_wetter_konnektor.md` | Spec | Basis-Spec, AC-16 (Abnahme in der Claude-App) wird hier herbeigeführt |
| ADR-0128 | ADR | OAuth-Server in Go, Konnektor-Schnittstelle |
| `internal/mcp/autorisieren.go`, `internal/mcp/oauth.go` | Go-Code | `authorize`: ohne Sitzung 302 auf `/login?redirect=…`, nicht gelistetes Konto mit Sitzung 403 (`mcp.oauth.nicht_freigegeben`) ohne Code, Zustimmung per POST mit gültigem Origin, Code als 303 an die Redirect-URI; Loopback `http://127.0.0.1:<port>` als Redirect-URI erlaubt |
| `internal/config/admin.go` (`ParseMCPUserIDs`) | Go-Code | Kennungen getrimmt, komma-getrennt, leer = niemand, exakter Vergleich |
| `frontend/src/routes/.well-known/[...pfad]/+server.ts` | SvelteKit | reicht die drei OAuth-Metadatenpfade an Go durch (Upstream 3001) |
| Go-API Port 8091 (Staging), SvelteKit Port 3001 | Upstream | Ziele der neuen `location`-Blöcke |
| Env `GZ_VALIDATOR_USER/_PASS` | Zugangsdaten | Basic-Schranke Staging |
| Env `GZ_AUTH_USER/_PASS` | Zugangsdaten | App-Konto `default` (gelistet) |
| Env `GZ_STAGING_ADMIN_USER/_PASS` | Zugangsdaten | zweites, nicht gelistetes Konto `gz-staging-admin` |
| henemm-infra #229 | Befund | Server-IP umgeht die Schranke: Probe nur von außerhalb |
| henemm-infra #397 | Befund | fail2ban `nginx-limit-req` sperrt claude.ai aus: kein `limit_req` |
| `deploy-gregor-prod.sh`, `prod_selftest.py` | Werkzeuge | Produktionsprüfung (Selftest Exit 0) |

## Implementation Details

**Variante A (entschieden):** drei enge Blöcke, `/login` bleibt hinter der Schranke. Abgelehnt: Variante B (zusätzlich `/login` und `/_app/` öffnen, weicht die Staging-Schranke auf) und Variante C (nur in Produktion abnehmen, verletzt „Produktion erst nach Test auf Staging“).

**nginx (Staging):**
- `location = /api/mcp` auf Go 8091 mit `proxy_read_timeout 120s`. Herleitung: 10 s Ortssuche + 5 s Kontingent + 60 s Core = 75 s plus Puffer; der nginx-Standard von 60 s wäre zu kurz.
- `location ^~ /api/mcp/oauth/` auf Go 8091.
- `location ^~ /.well-known/oauth-` auf SvelteKit 3001, wie bisher. Das Präfix deckt alle drei Metadatenpfade ab, auch den mit Suffix `/api/mcp`.
- Je Block `auth_basic off`, alle vier `proxy_set_header`-Zeilen wie im Bestand (`X-Real-IP` ist für die Registrierungsbremse in Go nötig), Begründungskommentar mit #3286. Muster: die bestehenden Blöcke `= /api/health` und `/api/webhooks/…`.
- **Nicht übernehmen:** `satisfy any`/`deny all` aus den Blöcken „/api/“ und „/“ (mit `auth_basic off` sperrt das alle, Kommentar #2316); kein `limit_req` (henemm-infra#397); kein `proxy_buffering off` (in `internal/mcp/` kein `event-stream`, kein `Flusher`); kein eigenes Log-Format (`code` steht nur im Redirect bzw. POST-Body, nie in einer Request-URL).
- `GET`/`DELETE /api/mcp` sind mit offen; Go antwortet ohne Daten.

**Probe-Skript `staging_mcp_pruefen.py`:** liest Zugangsdaten ausschließlich aus der Umgebung und gibt weder Zugangsdaten noch Token oder Codes aus. Es lehnt den Start auf dem Server selbst mit Exit 2 ab (Server-IP umgeht die Schranke, das Ergebnis würde nichts beweisen). Exit-Codes: 0 bestanden, 1 Soll verfehlt, 2 Aufruf- oder Umgebungsfehler (nie als bestanden werten). Teile: (a) Pfadprobe Soll/Verbot, (b) OAuth-Ablauf für `default`, (c) Ablehnung für `gz-staging-admin`, (d) CSP-Zählung. Die Auswertelogik ist von der Netzschicht getrennt, damit der Kern-Test sie gegen einen lokalen HTTP-Server prüfen kann.

**Reihenfolge:**
1. RED: Probe vom iMac vor der Änderung. Gemessen 2026-11-24: alle Pfade 401 Basic, auch `/api/mcp/oauth/token` und `/.well-known/oauth-protected-resource/api/mcp`. Dieser Lauf ist der Rot-Nachweis (Exit 1).
2. Kern-Test und Probe-Skript im gregor_zwanzig-PR; henemm-infra-PR (eigener Klon, nicht im Hauptcheckout), Merge. Kein offener PR dort ändert diese Datei (geprüft).
3. Server: `diff` Live gegen Repo (Drift bisher nur ein Kommentar am Telegram-Webhook), Live-Datei sichern, kopieren, `sudo nginx -t`, `systemctl reload nginx` (Weg wie `fix_2124_versand_nginx_timeout.md`). Alte `*.bak` in `/etc/nginx/conf.d` nicht anfassen.
4. Vor dem `.env`-Eintrag: authorize-Lauf für `default` muss 403 liefern (fail-closed, AC-6).
5. Staging-`.env`: `GZ_MCP_USER_IDS=default`, Dateimodus/ACL unverändert (`fix_2788`), nur `gregor-api-staging` neu starten. Sperrt der Auto-Modus den Eintrag als „Permission Grant“, wird die Freigabe eingeholt und nicht umgangen (PO hat Serverzugriff für das Ticket am 2026-11-24 freigegeben, Produktion erst nach Test auf Staging).
6. Probe vollständig von außen (AC-1 bis AC-5, AC-9), Rollback-Übung (AC-13), `/e2e-verify` für den gregor_zwanzig-PR; danach Zugangsdaten für die Anmeldeseite dem PO bereitstellen.
7. PO: AC-16 in der Claude-App. Danach Produktion: Auslieferung des gemergten Stands mit `deploy-gregor-prod.sh` (falls der Pull-Deploy ihn nicht schon ausgerollt hat; ohne Codeänderung am Dienst), Produktions-`.env` `GZ_MCP_USER_IDS=henning`, nur `gregor-api` neu starten, Prüfung, Selftest, Kommentar in #3281, #3286 schließen.

**Konten:** Produktion `henning` (Admin-Konto, PO-Entscheid 2026-10-01, abgenommen in #2155). Staging `default` (dediziertes App-Anmeldekonto, bleibt Nicht-Admin). Die Annahme im Issue („Konto-ID `u-xxxxxxxx` über die E-Mail des PO“) trifft nicht zu.

## Expected Behavior

- **Input:** Anfragen von außen an `https://staging.gregor20.henemm.com` ohne Basic-Zugangsdaten auf die Pfade `/.well-known/oauth-*`, `POST /api/mcp`, `/api/mcp/oauth/*`; zusätzlich Anfragen auf alle übrigen Pfade.
- **Output:** Die drei Pfadgruppen werden von Go bzw. SvelteKit beantwortet, alle übrigen Pfade bleiben 401 Basic. Das Konto `default` erhält per OAuth ein Token und Wetterdaten, ein nicht gelistetes Konto erhält 403 ohne Code.
- **Side effects:** Offene Registrierung schreibt Dateien unter `GZ_DATA_DIR` (gebremst: 20/h je IP, 500/Tag). Der Live-Probelauf verbraucht dieses Kontingent nur mit wenigen Registrierungen.

## Acceptance Criteria

- **AC-1:** Given Staging nach Rollout der drei Blöcke und ohne Basic-Zugangsdaten / When die Pfade `/.well-known/oauth-authorization-server`, `/.well-known/oauth-protected-resource` und `/.well-known/oauth-protected-resource/api/mcp` abgefragt werden / Then antwortet jeder mit 200 und JSON, dessen Issuer bzw. Resource auf `https://staging.gregor20.henemm.com` zeigt
  - Test: Außen-Probe vom iMac, Auswertung der JSON-Felder; vor der Änderung 401 Basic (RED), danach 200.

- **AC-2:** Given Staging nach Rollout und ohne Basic-Zugangsdaten / When `POST /api/mcp` ohne Token sowie `register`, `authorize` und `token` unter `/api/mcp/oauth/` aufgerufen werden / Then liefert `POST /api/mcp` 401 mit Header `WWW-Authenticate: Bearer resource_metadata=…` (kein Basic) und die drei OAuth-Pfade werden von Go beantwortet, nicht von der Basic-Schranke
  - Test: Außen-Probe prüft den Header-Typ `Bearer` statt `Basic` und dass die Antworten der OAuth-Pfade kein `WWW-Authenticate: Basic` tragen.

- **AC-3:** Given Staging nach Rollout und ohne Basic-Zugangsdaten / When `/`, `/login`, `/api/trips`, `/api/mcpx`, `/api/_internal/mcp/wetter`, `/.well-known/openid-configuration` und `/api/internal/` abgefragt werden / Then antworten die ersten sechs weiterhin mit 401 Basic und `/api/internal/` weiterhin mit 403
  - Test: Vorher-Nachher-Vergleich derselben Pfadliste durch die Außen-Probe (gemessen 2026-11-24 vor der Änderung: `/login` und `/api/_internal/mcp/wetter` 401 Basic, `/api/internal/` 403); kein Verbotspfad darf sich öffnen.

- **AC-4:** Given Staging mit `GZ_MCP_USER_IDS=default` und Konto `default` / When das Skript per OAuth durchläuft (register, Login mit Basic und App-Konto, authorize mit Loopback-Redirect, token mit PKCE, tools/list, tools/call) / Then erhält es einen Code per 303, ein Token, die Werkzeugliste und eine Wetterantwort mit Ortsname und Stundenwerten
  - Test: Skript-Lauf vom iMac gegen Staging, Exit 0; Ausgabe enthält weder Token noch Zugangsdaten.

- **AC-5:** Given Staging mit `GZ_MCP_USER_IDS=default` und das nicht gelistete Konto `gz-staging-admin` mit gültiger Sitzung / When es den authorize-Ablauf durchläuft / Then antwortet Go mit 403 (`mcp.oauth.nicht_freigegeben`) und es entsteht kein Code
  - Test: Skript-Teil mit zweitem Nutzer; geprüft wird 403 und fehlender `code` in `Location`. Belegt die Mandantentrennung mit zwei verschiedenen Nutzern.

- **AC-6:** Given nginx ist neu geladen, `GZ_MCP_USER_IDS` aber noch nicht gesetzt / When der authorize-Ablauf für `default` läuft / Then antwortet Go mit 403 und kein Code wird ausgestellt (leer = niemand, fail-closed)
  - Test: Außen-Probe in der Reihenfolge nginx-Reload vor `.env`-Eintrag; danach wechselt dasselbe Konto nach dem Eintrag auf Code (AC-4).

- **AC-7:** Given der Block `= /api/mcp` ist aktiv / When ein Werkzeugaufruf länger als 60 s, aber kürzer als 75 s dauert / Then bricht nginx nicht vorher ab (`proxy_read_timeout 120s`)
  - Test: Ein Aufruf mit realer Dauer über 60 s ist live nicht ohne Weiteres erzeugbar. Nachweis daher als Textvertrag-Regressionstest in henemm-infra (`test_staging_mcp_nginx.py` prüft `proxy_read_timeout 120s` im Block `= /api/mcp`) plus die Herleitung oben; ausdrücklich kein Verhaltensnachweis, siehe Known Limitations.

- **AC-8:** Given die Registrierungsbremse in Go zählt je Client-IP (20/h, 500/Tag) / When nginx Anfragen an `register` weiterreicht / Then trägt jeder Block die Zeile `proxy_set_header X-Real-IP $remote_addr`, damit die echte Client-IP ankommt
  - Test: Textvertrag-Regressionstest in henemm-infra. Ein Live-Beweis durch 20 Registrierungen bis 429 würde das Kontingent von 20/h und 500/Tag verbrauchen und die Registrierung des PO blockieren und wird deshalb nicht durchgeführt (Known Limitations).

- **AC-9:** Given Staging mit `GZ_MCP_USER_IDS=default` und angemeldetem Konto `default` / When die Zustimmungsseite über `GET /api/mcp/oauth/authorize` mit gültigen Parametern abgerufen wird / Then enthält die Antwort genau einen `Content-Security-Policy`-Header, und dessen Wert ist die von der Go-API gesetzte Richtlinie (nginx fügt keine zweite hinzu)
  - Test: Außen-Probe zählt die CSP-Header der authorize-Antwort (Produktion liefert gemessen genau eine; das eingebundene Snippet setzt keine zweite).

- **AC-10:** Given das Probe-Skript und der Kern-Test / When ein Soll-Pfad noch von der Schranke geblockt wird oder ein Verbotspfad offen ist / Then meldet das Skript Exit 1; bei fehlenden Zugangsdaten oder beim Start auf dem Server selbst Exit 2; Zugangsdaten, Token und Codes erscheinen nie in der Ausgabe
  - Test: Kern-Test `tests/tdd/test_staging_mcp_pruefen.py` startet einen echten lokalen HTTP-Server, der Soll-Pfade blockt bzw. Verbotspfade öffnet, und prüft Exit 1, Exit 2 (Umgebung leer) und die Abwesenheit sämtlicher Geheimnisse in stdout/stderr. Zusätzlich der RED-Lauf gegen Staging vor der Änderung (Exit 1).

- **AC-11:** Given Staging ist freigeschaltet (AC-1 bis AC-6 erfüllt) und der PO hat die Zugangsdaten für die Anmeldeseite / When der PO den Konnektor „Gregor Wetter“ in der Claude-App verbindet und eine Wetterfrage stellt / Then erhält er eine Wetterantwort (Abnahme AC-16 der Basis-Spec); zeigt der In-App-Browser keinen Basic-Dialog, verbindet er einmalig im Desktop-Browser
  - Test: Einziger PO-Schritt, Antwort per `AskUserQuestion`. Der Skript-Nachweis AC-4 geht dem voraus, damit der PO nur die App-Seite prüft.

- **AC-12:** Given der PO hat AC-11 bestätigt / When in der Produktions-`.env` `GZ_MCP_USER_IDS=henning` gesetzt und nur `gregor-api` neu gestartet wird / Then liefert `POST /api/mcp` ohne Token weiter 401 mit `Bearer resource_metadata=…`, die Metadatenpfade weiter 200, `prod_selftest.py` Exit 0
  - Test: Außen-Probe gegen Produktion plus Selftest; danach Nachweis als Kommentar in #3281 (bereits geschlossen) und #3286 geschlossen. Vor AC-11 wird Produktion nicht geändert.

- **AC-13:** Given die neue nginx-Datei ist auf Staging aktiv / When die gesicherte Vorfassung zurückkopiert und nginx nach `nginx -t` neu geladen wird / Then antworten alle Soll-Pfade aus AC-1 und AC-2 wieder mit 401 Basic, und nach erneutem Einspielen der neuen Datei sind die Pfade aus AC-1 und AC-2 wieder offen
  - Test: Einmalige Rollback-Übung auf Staging vor der PO-Abnahme: Sicherung einspielen, Probe von außen (Exit 1, alle Soll-Pfade 401 Basic), neue Datei wieder einspielen, Probe (Exit 0). Der `.env`-Rollback entspricht dem in AC-6 belegten Zustand „nicht gesetzt“.

### Rollback

1. nginx: Sicherung der Live-Datei zurückkopieren, `sudo nginx -t`, `systemctl reload nginx`. Danach sind die Pfade wieder 401 Basic.
2. `.env`: Zeile `GZ_MCP_USER_IDS=…` entfernen, den betroffenen Go-Dienst (`gregor-api-staging` bzw. `gregor-api`) neu starten. Leer heißt niemand.

## Test Plan

### Automated Tests (TDD RED)

- [ ] Test 1: GIVEN lokaler HTTP-Server, der Soll-Pfade mit 401 Basic blockt / WHEN das Probe-Skript läuft / THEN Exit 1 mit Nennung der Pfade (AC-1, AC-2, AC-10)
- [ ] Test 2: GIVEN lokaler HTTP-Server, der einen Verbotspfad mit 200 beantwortet / WHEN das Probe-Skript läuft / THEN Exit 1 (AC-3, AC-10)
- [ ] Test 3: GIVEN lokaler HTTP-Server mit vollständigem Soll-Verhalten samt OAuth-Ablauf / WHEN das Probe-Skript läuft / THEN Exit 0 (AC-4, AC-10)
- [ ] Test 4: GIVEN lokaler Server, der dem zweiten Konto einen Code ausstellt / WHEN das Probe-Skript läuft / THEN Exit 1 (AC-5)
- [ ] Test 5: GIVEN zwei CSP-Header in der authorize-Antwort / WHEN das Probe-Skript läuft / THEN Exit 1 (AC-9)
- [ ] Test 6: GIVEN leere Umgebung bzw. Start auf dem Server / WHEN das Probe-Skript läuft / THEN Exit 2; kein Geheimnis in stdout/stderr aller Läufe (AC-10)
- [ ] Test 7 (henemm-infra, Textvertrag): GIVEN die Staging-Conf / WHEN die drei Blöcke gelesen werden / THEN `auth_basic off`, vier Header-Zeilen, `proxy_read_timeout 120s`, kein `satisfy`, `deny` oder `limit_req` (AC-7, AC-8, nur Regressionsschutz)

### Live-Nachweise

- RED-Lauf gegen Staging vor der Änderung (Exit 1), danach Außen-Probe (AC-1 bis AC-5, AC-9), fail-closed-Lauf (AC-6), Rollback-Übung (AC-13), PO-Abnahme (AC-11), Produktionsprüfung (AC-12).

## Definition of Done

- Kern-Test grün, RED zuvor nachgewiesen; Adversary-Verdict VERIFIED samt Mutations-Gegenprobe des Probe-Skripts.
- Beide PRs gemergt, CI grün; Staging-nginx entspricht der Repo-Datei (`diff` leer).
- AC-1 bis AC-6, AC-9 und AC-13 auf Staging von außen belegt; AC-7 und AC-8 als Regressionsschutz gekennzeichnet.
- PO-Abnahme AC-11 erfolgt, danach Produktion freigeschaltet und Selftest Exit 0 (AC-12).
- Nachweis in #3281 kommentiert, #3286 geschlossen.

## Known Limitations

- **Befund A (wichtigster):** `authorize` leitet auf `/login`, das hinter der Schranke bleibt. Ob der In-App-Browser der Claude-App einen Basic-Dialog zeigt, ist offen; Ausweg ist der Desktop-Browser. `/login` wird bewusst nicht geöffnet.
- **Befund B:** Falsch beantwortete Basic-Abfragen können die Jail `nginx-http-auth` auslösen (5 in 10 min, 1 h Sperre) und sehen dann wie ein Konnektor-Fehler aus. Zugangsdaten dem PO vorab bereitstellen. Ob bloßes Abbrechen zählt, ist ungeprüft.
- **Befund C:** Offene Registrierung schreibt Dateien unter `GZ_DATA_DIR`; gebremst durch 20/h je IP und 500/Tag, kein `limit_req` wegen henemm-infra#397.
- **Befund D:** Textvertrag der Conf (AC-7, AC-8) ist nur Regressionsschutz, kein Verhaltensnachweis. Das Verhalten bei einem Aufruf über 60 s und die Weitergabe der Client-IP sind live nicht gemessen.
- Das Probe-Skript beweist nur von außerhalb des Servers etwas; auf dem Server selbst lehnt es mit Exit 2 ab.
- Der gregor_zwanzig-PR gilt wegen `.env.example` als `backend`, nicht docs-only, und braucht den Staging-Nachweis.

## Out of Scope

- `/login` und Assets für die Anmeldung öffnen (Variante B).
- `limit_req` in nginx (henemm-infra#397).
- Startwarnung für `GZ_MCP_USER_IDS` ohne Konto (`cmd/server/main.go`, `warnPrivilegedIDsWithoutAccount`): Nebenbefund für #1199.
- Token-Entzug live wiederholen (in #3281 durch Tests abgedeckt).
- Änderungen an Go-, Python- oder Frontend-Code.

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** keine neue; ADR-0128 gilt.
- **Rationale:** Es wird nur die bereits entschiedene OAuth-Schnittstelle (ADR-0128) auf Staging erreichbar gemacht und freigeschaltet. Die Öffnung folgt dem bestehenden Muster der `auth_basic off`-Blöcke (Health, Webhooks); keine neue Entscheidungsfläche.

## Changelog

- 2026-11-24: Initial spec created
