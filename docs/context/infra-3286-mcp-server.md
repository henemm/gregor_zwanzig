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

## Analysis

Stand 2026-11-24 (drei Explore-Berichte, eine Plan-Bewertung; Aussagen unten mit „gemessen“ selbst geprüft).

### Type
Feature (Infrastruktur/Server-Einrichtung). Keine Änderung an Go-, Python- oder Frontend-Code.

### Affected Files (with changes)
| File | Change Type | Description |
|------|-------------|-------------|
| henemm-infra `nginx/staging.gregor20.henemm.com.conf` | MODIFY | drei `location`-Blöcke mit `auth_basic off` (ca. +50) |
| henemm-infra `tests/test_staging_mcp_nginx.py` | CREATE | Textvertrag der Conf, Muster `tests/test_mta_sts_policy.py` (ca. 80) |
| `.env.example` | MODIFY | `GZ_MCP_USER_IDS=` mit Kommentar nach `GZ_ADMIN_USER_IDS` (ca. +5) |
| `.claude/tools/staging_mcp_pruefen.py` | CREATE | Außen-Probe und OAuth-Ablauf gegen Staging, Muster `staging_befehl_pruefen.py` (ca. 100-150) |
| Server: Staging-nginx-Datei, beide `.env` | MODIFY (live) | nicht versioniert; siehe Reihenfolge |

### Scope Assessment
- Files: 4 versioniert (zwei Repos, zwei PRs) plus drei Live-Dateien
- Estimated LoC: +235 bis +285 / -0. **Grenze ±250 beachten**; notfalls Probe-Skript kürzen.
- Risk Level: MEDIUM (öffentliche Öffnung auf Staging, Rechte-Eintrag in Produktion; Rollback trivial)

### Technical Approach
Variante A (empfohlen), verglichen mit:

| Variante | Conf-Zeilen | Öffnung | Bewertung |
|---|---|---|---|
| A: drei enge Blöcke | ca. 50 | 3 Pfade | empfohlen; `/login` bleibt hinter der Schranke |
| B: A plus `/login`, `/_app/` | ca. 70 | Anmeldeoberfläche offen | weicht die Staging-Schranke auf, abgelehnt |
| C: nur in Produktion abnehmen | 0 | keine | verletzt „Produktion erst nach Test auf Staging“ |

- `location = /api/mcp` → 8091, `proxy_read_timeout 120s` (Herleitung: 10 s Ortssuche + 5 s Kontingent + 60 s Core = 75 s plus Puffer; nginx-Standard 60 s wäre zu kurz)
- `location ^~ /api/mcp/oauth/` → 8091; `location ^~ /.well-known/oauth-` → 3001 (SvelteKit, wie bisher). Das Präfix deckt alle drei Metadatenpfade; exakte Treffer verfehlen leicht den dritten mit Suffix `/api/mcp`.
- Je Block `auth_basic off`, alle vier `proxy_set_header`-Zeilen wie im Bestand (`X-Real-IP` ist nötig für die Registrierungsbremse), Begründungskommentar mit #3286. **Kein** `satisfy`/`deny`, **kein** `limit_req` (henemm-infra#397 ist offen).
- `GET`/`DELETE /api/mcp` sind mit offen; Go antwortet ohne Daten (`OhnePost`).
- Kein `proxy_buffering off`: `internal/mcp/` enthält weder `event-stream` noch `Flusher` (gemessen per grep).
- Kein eigenes Log-Format: `code` steht nur im Redirect an den Client bzw. im POST-Body, nie in einer Request-URL an Staging.
- CSP-Kollision: Produktion `GET /api/mcp/oauth/authorize` liefert genau eine CSP, die von Go (gemessen); das Snippet setzt keine. Staging bindet dasselbe Snippet ein, nach dem Reload erneut prüfen.

### Dependencies / Reihenfolge
1. RED: Außen-Probe vom iMac **vor** der Änderung. Gemessen 2026-11-24: alle Pfade 401 Basic, auch `/api/mcp/oauth/token` und `/.well-known/oauth-protected-resource/api/mcp`.
2. henemm-infra-PR (eigener Klon, kein Arbeiten im Hauptcheckout; dieser liegt 4 Commits hinter main), Merge. Kein offener PR dort ändert diese Datei (geprüft).
3. Server: `diff` Live/Repo, Live-Datei sichern, kopieren, `sudo nginx -t`, `systemctl reload nginx` (Weg wie `fix_2124_versand_nginx_timeout.md`). Rollback = Sicherung zurück + reload.
4. Staging-`.env`: `GZ_MCP_USER_IDS=default`, Dateimodus/ACL unverändert (`fix_2788`), nur `gregor-api-staging` neu starten.
5. Außen-Probe (nur von außerhalb: die Server-IP umgeht die Schranke, infra#229). Soll: Metadaten 200 JSON mit Staging-Issuer; `POST /api/mcp` 401 mit `Bearer resource_metadata=`; weiter 401 Basic: `/`, `/login`, `/api/trips`, `/api/mcpx`, `/.well-known/openid-configuration`; `/api/internal/` gesperrt.
6. OAuth-Ablauf per Skript ohne PO: `register` → Login (Basic `GZ_VALIDATOR_*` + `GZ_AUTH_*` der Staging-`.env`) → `authorize` mit Loopback-Redirect, Code aus `Location` (Antwort 303) → `token` mit PKCE → `tools/call`. Zwei Nutzer: `default` bekommt Daten, ein nicht gelistetes Konto keinen Code. Token-Entzug ist in #3281 durch Tests abgedeckt, live nicht wiederholen.
7. PO: AC-16 in der Claude-App. Danach Produktions-`.env` `GZ_MCP_USER_IDS=henning`, nur `gregor-api` neu starten, Probe, Selftest, Nachweis in #3281 kommentieren, #3286 schließen.

### Befunde gegen den Plan
- **A (wichtigster):** `authorize` leitet auf `/login` hinter der Schranke. Zeigt der In-App-Browser keinen Basic-Dialog, verbindet der PO einmalig am Desktop-Browser; `/login` wird **nicht** geöffnet.
- **B:** Falsch beantwortete Basic-Abfragen können die Jail `nginx-http-auth` auslösen (5 in 10 min → 1 h); sieht dann wie ein Konnektor-Fehler aus. Zugangsdaten dem PO vorab bereitstellen. Ob bloßes Abbrechen zählt, ist ungeprüft.
- **C:** Offene Registrierung schreibt Dateien unter `GZ_DATA_DIR`; gebremst durch 20/h je IP und 500/Tag.
- **D:** Textvertrag der Conf ist nur Regressionsschutz; der Verhaltensnachweis ist die Außen-Probe (Regel gegen Dateiinhalt-Checks).

### Nicht in diesem Ticket
Startwarnung für `GZ_MCP_USER_IDS` ohne Konto (`cmd/server/main.go`, `warnPrivilegedIDsWithoutAccount`): Nebenbefund für #1199. Hier genügt: Kennung wird über den OAuth-Lauf positiv belegt.

### Open Questions
- [ ] Spec: gilt `.env.example` im Deploy-Gate als docs-only? Vor dem Commit am Scope-Detektor prüfen.
- [ ] Rechte-Eintrag in `.env`: sperrt der Auto-Modus, die Freigabe beim PO einholen, nicht umgehen.
- [ ] Keine Produktfrage an den PO offen.

## Stand nach TDD RED (2026-11-24)

- Kern-Test `tests/tdd/test_staging_mcp_pruefen.py` (76 rot, Werkzeug fehlt). Der Kopf der Datei ist der Schnittstellen-Vertrag
  für `.claude/tools/staging_mcp_pruefen.py`: `main(argv, *, env, basis, server_merkmal)`, Schalter `--vor-freigabe` für AC-6.
- Textvertrag nginx (Test 7, 35 rot): Datei liegt fertig unter `docs/artifacts/infra-3286-mcp-server/henemm-infra-test_staging_mcp_nginx.py`
  (noch uncommittet) und gehört in henemm-infra nach `tests/test_staging_mcp_nginx.py`. Branch `feat-gregor-3286-mcp-staging` ist dort
  angelegt, aber noch ohne Commit (Commit-Sperre ab Phase 6 bis zum Adversary-Verdict). Klon: `gh repo clone henemm/henemm-infra`.
- Live-Ist-Stand vor der Änderung: `docs/artifacts/infra-3286-mcp-server/red-live-pfade.txt`. Den Exit-1-Lauf des Skripts gegen
  Staging (AC-10) in Phase 6 **vor** dem nginx-Rollout nachholen, sobald das Skript existiert.
- Zugangsdaten liegen nicht auf dem iMac, sondern auf dem Server: `/home/hem/gregor_zwanzig/.claude/validator.env`
  (`GZ_VALIDATOR_*`), `/home/hem/gregor_zwanzig/.claude/staging_admin.env` (`GZ_STAGING_ADMIN_*`), Staging-`.env` (`GZ_AUTH_*`).
  Für den Lauf per Umgebung reichen, nie ausgeben oder ablegen.
- AC-12 (Produktion) per curl prüfen, das Skript ist nur für Staging.

## Stand Phase 6 (2026-11-24)

- Probe-Skript fertig: 172 Zeilen (146 nicht leer), über der 150er-Marke der Spec; nach Neuschätzung akzeptiert, kein Weiterbau. Kern-Test 76 grün.
- nginx-Blöcke und Textvertrag (35 grün) liegen uncommittet in einem henemm-infra-Klon im Sitzungs-Scratchpad; gesichert als
  `docs/artifacts/infra-3286-mcp-server/henemm-infra-conf.diff` (per `git apply`) und `henemm-infra-test_staging_mcp_nginx.py`.
- RED-Lauf gegen Staging (AC-10) erledigt: Exit 1, sieben Soll-Pfade 401 (`red-live-skript.txt`), Zugangsvariablen mit Platzhaltern.
- `red-live-pfade.txt` war als RED-Artefakt fehlregistriert (Messung, kein Testlauf) und ist abgemeldet; Datei bleibt.
- **Offen:** Lesen der Zugangsdaten per `ssh henemm` hat der Auto-Modus am 2026-11-24 abgelehnt („Unauthorized Access“). Nicht umgehen;
  vor AC-1 bis AC-6, AC-9, AC-13 (Läufe mit echten Konten) braucht es die ausdrückliche Freigabe des PO.
- Adversary Durchgang 1: **BROKEN** (F001 bis F009, Protokoll `adversary-dialog-runde1-2-broken.md`). Ist-Code trägt, aber Tests fangen 24 Mutationen nicht.
  Neuschätzung (F002): Skript ca. 180, Kern-Test ca. 450, Textvertrag ca. 100 Zeilen; über ±250, der Überhang ist Testcode. Weiterbau entschieden.
- Fix-Loop 1 erledigt: F001, F003 bis F008 geschlossen, 23 nicht äquivalente Mutationen gefangen (P30 äquivalent). Kern-Test 114 grün,
  Textvertrag 37 grün. Zeilen: Skript 176, Kern-Test 478, Textvertrag 97. Offen: Adversary Runde 3. Artefakte unter `docs/artifacts/` brauchen `git add -f`.
- Adversary Runde 3: **VERIFIED** (114 + 37 grün; offen nur F009, F010, beide LOW). Protokoll registriert und gestempelt.
- QA-Gate: **CHECKLIST FAILED**, weil AC-11 (PO-Abnahme) und AC-12 (Produktion) im Protokoll `[ ]` sind. Beide liegen laut Spec nach Merge und
  Staging-Rollout, sind in Phase 6b also nicht beweisbar. AC-1 bis AC-6, AC-9, AC-13 stehen als `[-]` (Implementierung belegt, live offen); diese
  Markierung sieht das Gate nicht. Protokoll nicht eigenmächtig umgetragen, um das Gate zu öffnen; Entscheidung des PO eingeholt.
- **PO-Entscheid 2026-11-24 (Auswahldialog):** AC-11/AC-12 sowie die Live-Teile von AC-1 bis AC-6, AC-9, AC-13 dürfen im Protokoll als „später
  nachzuweisen“ (`[-]`) stehen; Pflicht vor Schließen von #3286, sonst bleibt das Ticket offen.
- **PO-Freigabe 2026-11-24 (Auswahldialog):** die sechs Zugangswerte (`GZ_VALIDATOR_*`, `GZ_AUTH_*` der Staging-`.env`, `GZ_STAGING_ADMIN_*`) per SSH
  nur in den Arbeitsspeicher lesen, ausschließlich für Prüfläufe gegen Staging, nicht anzeigen oder speichern. Produktion nicht betroffen.
- **Übergabe an Phase 7:** Umsetzung hier committet und gepusht; henemm-infra-Branch `feat-gregor-3286-mcp-staging` ist committet und gepusht
  (die Angabe „uncommittet“ oben ist überholt), PRs noch nicht angelegt. QA-Gate VERIFIED. Server, Staging und Produktion unverändert.

## Stand Phase 8 (2026-11-24)

- Validierung bestanden: Kern-Test und Textvertrag (37) grün, betroffene Ratschen grün (Teilmenge, volle Suite nur CI), keine AC im Code verfehlt.
- Umfang über der Spec-Schätzung (Skript 176, Kern-Test 478, beide Repos ca. 800 statt 345 Zeilen); Claude-Entscheidung ohne vorherige Rückfrage, dem PO offengelegt.
- **Offen, Pflicht vor Schließen von #3286:** nginx-Rollout, AC-1 bis AC-6, AC-9, AC-13 live auf Staging, dann AC-11 (PO), AC-12 (Produktion).
  `/70-deploy`: Reihenfolge der Spec einhalten (AC-6 vor dem `.env`-Eintrag); PRs mit „Refs“ statt „Closes“.
