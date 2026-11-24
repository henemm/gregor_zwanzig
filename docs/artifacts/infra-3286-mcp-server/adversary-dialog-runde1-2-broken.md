# Adversary Dialog — infra-3286-mcp-server
Spec: docs/specs/modules/infra_3286_mcp_server_einrichtung.md
Datum: 2026-11-24 20:30

## Checkliste
- [-] **Input:** Anfragen von außen an `https://staging.gregor20.henemm.com` ohne Basic-Zugangsdaten auf die Pfade `/.well-known/oauth-*`, `POST /api/mcp`, `/api/mcp/oauth/*`; zusätzlich Anfragen auf alle übrigen Pfade.
  => TEILWEISE: Implementierungsteil belegt, Live-Nachweis steht aus
- [-] **Output:** Die drei Pfadgruppen werden von Go bzw. SvelteKit beantwortet, alle übrigen Pfade bleiben 401 Basic. Das Konto `default` erhält per OAuth ein Token und Wetterdaten, ein nicht gelistetes Konto erhält 403 ohne Code.
  => TEILWEISE: Live-Nachweis steht aus
- [x] **Side effects:** Offene Registrierung schreibt Dateien unter `GZ_DATA_DIR` (gebremst: 20/h je IP, 500/Tag). Der Live-Probelauf verbraucht dieses Kontingent nur mit wenigen Registrierungen.
  => belegt: eine Registrierung je Lauf (Probe-Skript:81-98)
- [-] **AC-1:** Given Staging nach Rollout der drei Blöcke und ohne Basic-Zugangsdaten / When die Pfade `/.well-known/oauth-authorization-server`, `/.well-known/oauth-protected-resource` und `/.well-known/oauth-protected-resource/api/mcp` abgefragt werden / Then antwortet jeder mit 200 und JSON, dessen Issuer bzw. Resource auf `https://staging.gregor20.henemm.com` zeigt
  => Logik belegt (Probe-Skript:86-89), Live steht aus, Issuer einzeln ungeschuetzt (F003)
- [-] **AC-2:** Given Staging nach Rollout und ohne Basic-Zugangsdaten / When `POST /api/mcp` ohne Token sowie `register`, `authorize` und `token` unter `/api/mcp/oauth/` aufgerufen werden / Then liefert `POST /api/mcp` 401 mit Header `WWW-Authenticate: Bearer resource_metadata=…` (kein Basic) und die drei OAuth-Pfade werden von Go beantwortet, nicht von der Basic-Schranke
  => Logik belegt (Probe-Skript:90-95), Live steht aus
- [-] **AC-3:** Given Staging nach Rollout und ohne Basic-Zugangsdaten / When `/`, `/login`, `/api/trips`, `/api/mcpx`, `/api/_internal/mcp/wetter`, `/.well-known/openid-configuration` und `/api/internal/` abgefragt werden / Then antworten die ersten sechs weiterhin mit 401 Basic und `/api/internal/` weiterhin mit 403
  => Skript belegt (Probe-Skript:96-98), Live steht aus, Conf-Textvertrag bewacht Schranke nicht (F001)
- [-] **AC-4:** Given Staging mit `GZ_MCP_USER_IDS=default` und Konto `default` / When das Skript per OAuth durchläuft (register, Login mit Basic und App-Konto, authorize mit Loopback-Redirect, token mit PKCE, tools/list, tools/call) / Then erhält es einen Code per 303, ein Token, die Werkzeugliste und eine Wetterantwort mit Ortsname und Stundenwerten
  => gegen echten Go-Server belegt, Staging steht aus, Ergebnispruefung schwach (F003)
- [-] **AC-5:** Given Staging mit `GZ_MCP_USER_IDS=default` und das nicht gelistete Konto `gz-staging-admin` mit gültiger Sitzung / When es den authorize-Ablauf durchläuft / Then antwortet Go mit 403 (`mcp.oauth.nicht_freigegeben`) und es entsteht kein Code
  => gegen echten Go-Server belegt, Live steht aus, 403-Herkunft schwach getestet (F004)
- [-] **AC-6:** Given nginx ist neu geladen, `GZ_MCP_USER_IDS` aber noch nicht gesetzt / When der authorize-Ablauf für `default` läuft / Then antwortet Go mit 403 und kein Code wird ausgestellt (leer = niemand, fail-closed)
  => gegen echten Go-Server belegt (--vor-freigabe), Live-Reihenfolge steht aus (F004)
- [x] **AC-7:** Given der Block `= /api/mcp` ist aktiv / When ein Werkzeugaufruf länger als 60 s, aber kürzer als 75 s dauert / Then bricht nginx nicht vorher ab (`proxy_read_timeout 120s`)
  => Textvertrag (nur Regressionsschutz), 35 Tests gruen, Mutation C09 gefangen
- [x] **AC-8:** Given die Registrierungsbremse in Go zählt je Client-IP (20/h, 500/Tag) / When nginx Anfragen an `register` weiterreicht / Then trägt jeder Block die Zeile `proxy_set_header X-Real-IP $remote_addr`, damit die echte Client-IP ankommt
  => Textvertrag (nur Regressionsschutz), Mutation C10 gefangen
- [-] **AC-9:** Given Staging mit `GZ_MCP_USER_IDS=default` und angemeldetem Konto `default` / When die Zustimmungsseite über `GET /api/mcp/oauth/authorize` mit gültigen Parametern abgerufen wird / Then enthält die Antwort genau einen `Content-Security-Policy`-Header, und dessen Wert ist die von der Go-API gesetzte Richtlinie (nginx fügt keine zweite hinzu)
  => Logik belegt (Probe-Skript:120), P09/P10 gefangen, Live steht aus
- [x] **AC-10:** Given das Probe-Skript und der Kern-Test / When ein Soll-Pfad noch von der Schranke geblockt wird oder ein Verbotspfad offen ist / Then meldet das Skript Exit 1; bei fehlenden Zugangsdaten oder beim Start auf dem Server selbst Exit 2; Zugangsdaten, Token und Codes erscheinen nie in der Ausgabe
  => belegt: Exit 1/2, kein Geheimnis in 76 Laeufen, RED traegt; Ausnahmepfad ungeschuetzt (F005)
- [ ] **AC-11:** Given Staging ist freigeschaltet (AC-1 bis AC-6 erfüllt) und der PO hat die Zugangsdaten für die Anmeldeseite / When der PO den Konnektor „Gregor Wetter“ in der Claude-App verbindet und eine Wetterfrage stellt / Then erhält er eine Wetterantwort (Abnahme AC-16 der Basis-Spec); zeigt der In-App-Browser keinen Basic-Dialog, verbindet er einmalig im Desktop-Browser
  => Live-Nachweis steht aus (PO-Schritt)
- [ ] **AC-12:** Given der PO hat AC-11 bestätigt / When in der Produktions-`.env` `GZ_MCP_USER_IDS=henning` gesetzt und nur `gregor-api` neu gestartet wird / Then liefert `POST /api/mcp` ohne Token weiter 401 mit `Bearer resource_metadata=…`, die Metadatenpfade weiter 200, `prod_selftest.py` Exit 0
  => Live-Nachweis steht aus (Produktion)
- [-] **AC-13:** Given die neue nginx-Datei ist auf Staging aktiv / When die gesicherte Vorfassung zurückkopiert und nginx nach `nginx -t` neu geladen wird / Then antworten alle Soll-Pfade aus AC-1 und AC-2 wieder mit 401 Basic, und nach erneutem Einspielen der neuen Datei sind die Pfade aus AC-1 und AC-2 wieder offen
  => Skript-Teil belegt (Exit 1 bei gesperrten Soll-Pfaden), Rollback-Uebung live steht aus

## Dialog

### Runde 1
**Adversary:**
Tests selbst gelaufen: `uv run pytest tests/tdd/test_staging_mcp_pruefen.py -v` => 76 passed (Ausgabe: docs/artifacts/infra-3286-mcp-server/adversary-test-output.txt); Textvertrag im Klon 35 passed. Wiederholbarer Lauf gegen den ECHTEN Go-Server (lauf.py, 5 Konfigurationen): `GZ_MCP_USER_IDS=""` + `--vor-freigabe` Exit 0, `""` ohne Flag Exit 1 (default 403), `default` Exit 0, `default` + `--vor-freigabe` Exit 1, `default,gz-staging-admin` Exit 1 (Zweitkonto bekommt 200). Testserver und echter Go-Server laufen in diesen Punkten nicht auseinander.
Code reference: .claude/tools/staging_mcp_pruefen.py:61-63 (von_go), :66-70 (code_aus), :73-78 (wetter_ok), :81-98 (pfadregeln), :111-137 (pruefe_konto), :140-168 (main), :164-166 (Ausnahmepfad).
Code reference: tests/tdd/test_staging_mcp_pruefen.py:238-380 (keine Mocks, echter HTTP-Server; `lauf` prueft in jedem Lauf alle Geheimnisse, :221-231).
Code reference: .env.example:52-55 (`GZ_MCP_USER_IDS=` leer = fail-closed, deckt sich mit internal/config/admin.go ParseMCPUserIDs).
RED-Nachweis AC-10: docs/artifacts/infra-3286-mcp-server/red-live-skript.txt zeigt Exit 1 mit allen sieben Soll-Pfaden als `HTTP 401`, die Verbotspfade (red-live-pfade.txt) sind unauffaellig. Das traegt als RED fuer AC-1/AC-2/AC-10 (Skript erreicht Staging, Exit 1 und nicht 2, Grund Basic-Schranke). Einschraenkung: kein Hash/Stand des Skripts im Artefakt; Zugangsvariablen waren Platzhalter, daher sind AC-4/AC-5 dort nicht beruehrt (korrekt, register ist blockiert).
Mutations-Gegenprobe Probe-Skript (41 Mutationen, Sicherungskopie im Scratchpad, am Ende per `cmp` identisch): gefangen 23, ueberlebt 18 (P03, P04, P05, P06, P07, P08, P14, P18, P19, P22, P23, P25, P26, P30, P31, P32, P33, P41; P30 ist aequivalent, weil ohne Cookie der GET-Schritt ohnehin scheitert). Nginx-Conf (16 Mutationen): gefangen 10, ueberlebt 6 (C01, C02, C03, C12, C15, C17). Mutation P16 (Redirects verfolgen) zunaechst falsch gebaut (www aus der 302-Antwort), sauber wiederholt und gefangen (`test_offener_verbotspfad[/-302]`).
Findings: F001 (HIGH), F002 bis F005 (MEDIUM), F006 bis F009 (LOW), Details im Abschnitt Verdict.
**Implementierer:**
(steht aus; Findings F001 bis F009 zur Behandlung)

### Runde 2
**Adversary:**
Zweite Runde, gezielt auf Fehlzuordnung der Exit-Codes und Geheimnisse. (a) Server nicht erreichbar, Anmeldung abgelehnt, fehlende/leere Variablen, unbekanntes Argument, Start auf Server: alle Exit 2 und ohne Netzzugriff getestet (test_fehlende_zugangsdaten, test_start_auf_dem_server, test_unbekanntes_argument). (b) Leere/kaputte Antworten: `objekt()` (Probe-Skript:39-44) macht aus allem Unlesbaren `{}`, jede Regel scheitert dann als Befund (Exit 1), nie als Bestanden. (c) client_id fehlt: Register-Regel scheitert (Befund), Kontopruefung entfaellt, Exit 1 (Probe-Skript:162). (d) Zwischenfehler/Timeout: jede Ausnahme => Exit 2 mit Typname (Probe-Skript:164-166); Timeout 100 s ungetestet (F007). (e) Registrierungsbremse 429 => Exit 1 statt 2, Text sieht aus wie geschlossene Schranke (F008). (f) Geheimnisse: im Ist-Zustand keine Ausgabe von Werten (nur feste Texte, Statuszahlen, Pfade, Variablennamen); der Schutz des Ausnahmepfads ist aber nicht getestet (P14, F005).
nginx (nur gelesen, kein nginx installiert, kein Live-Aufruf): kein Regex-Block, daher keine `^~`-Konflikte; Praefix `^~ /api/mcp/oauth/` oeffnet nur Unterpfade, die Go ueber die EXAKTE Map `mcpPublicPaths` (internal/middleware/auth.go:117-125) oeffentlich macht; alles andere unter dem Praefix verlangt in Go eine Sitzung (401, Go-Antwort). `= /api/mcp` ist exakt: `/api/mcp/`, `/api/mcpx`, `/API/MCP` (Gross-/Kleinschreibung) fallen auf `/api/` bzw. `/` (Basic). Doppelschraegstrich und `%2e%2e` normalisiert nginx vor der Location-Wahl; `%2F`-Varianten gingen roh an Go, wo kein Nicht-Public-Pfad ohne Sitzung antwortet. Kein Umgehungsweg gefunden; die Probe prueft solche Varianten aber nicht (F009, Empfehlung). `^~ /.well-known/oauth-` geht an SvelteKit, dessen Durchreicher gibt andere Pfade 404 (frontend/src/routes/.well-known/[...pfad]/+server.ts:9-11).
Offene Live-Punkte (nur live beweisbar, hier NICHT als bewiesen): AC-1 bis AC-6, AC-9 live (insbesondere: setzt das eingebundene `snippets/security-headers.conf` ein eigenes Content-Security-Policy? Dann waeren es zwei Header), AC-11, AC-12, AC-13, sowie GZ_PUBLIC_HOST auf Staging (Issuer/Resource muessen auf https://staging.gregor20.henemm.com zeigen) und fail2ban (die Probe sendet je Lauf sechs anmeldungslose Anfragen auf gesperrte Pfade; die bisherigen Staging-Laeufe mit ueber 25 solcher Anfragen blieben ohne Sperre, das spricht gegen Zaehlung, ist aber kein Beweis).
**Implementierer:**
(steht aus)

## Herkunft der Vorbedingungen

<!-- vom Prüfer auszufüllen, siehe `precondition_origins.py` -->
- kein Sprachprofil konfiguriert (`precondition_origins.default_lang`)
- Testlauf selbst im Worktree ausgefuehrt, nichts aus Implementiererangaben uebernommen; Mutationen mit externer Sicherung, am Ende `cmp` identisch.

## Verdict

### Findings

```
Finding F001
  Severity: HIGH
  Category: edge_case
  Code reference: henemm-infra tests/test_staging_mcp_nginx.py:69-73 (test_nur_die_bekannten_bloecke_sind_offen)
  Description: Der Test wertet nur `location`-Bloecke aus. Server-Ebene (`auth_basic "Staging";`, `auth_basic_user_file`), der Block `location /api/internal/ { deny all; }` und `allow`-Listen in `/api/` bleiben unbewacht, obwohl der Docstring "Keine Oeffnung nebenbei" behauptet.
  Spec requirement: AC-3 / Test 7 - nichts ausser den drei Bloecken oeffnet sich
  Conflict: Mutationen ueberleben: C01 (`auth_basic off;` auf Server-Ebene = ganze Staging offen), C02 (Zeile entfernt), C12 (htpasswd entfernt), C03 (`deny all` bei /api/internal/ entfernt), C15 (neuer Block `^~ /login` mit satisfy any und allow all), C17 (/api/ `allow all`): alle 35 Tests bleiben gruen.
  Remediation: Test um Server-Ebene (Text ausserhalb der location-Bloecke enthaelt `auth_basic "Staging";` und die htpasswd-Zeile), `/api/internal/` mit `deny all` und "kein Block ausser den Bestandsbloecken hat `satisfy any` oder `allow all`" erweitern.

Finding F002
  Severity: MEDIUM
  Category: spec_violation
  Code reference: .claude/tools/staging_mcp_pruefen.py:172 (Dateiende); tests/tdd/test_staging_mcp_pruefen.py:380
  Description: Probe-Skript 172 Zeilen, Kern-Test 380 Zeilen, `.env.example` +5 = ca. 557 Zeilen im Repo gregor_zwanzig.
  Spec requirement: Estimated Scope: ca. +215 je Repo, "Waechst das Skript ueber ca. 150 Zeilen, wird vor dem Weiterbau neu geschaetzt"; Scoping Limit +-250 LoC
  Conflict: Beide Grenzen ueberschritten (Skript 172 > 150; Repo-Summe ca. 2,5-fach), ohne dokumentierte Neuschaetzung.
  Remediation: Neuschaetzung in der Spec nachtragen und Abweichung ausweisen oder den Kern-Test straffen.

Finding F003
  Severity: MEDIUM
  Category: edge_case
  Code reference: .claude/tools/staging_mcp_pruefen.py:73-78 (wetter_ok), :86-89 (Metadaten), :128 (Token), :133 (tools/list)
  Description: Ergebnispruefungen schwach getestet. Ueberlebt: P06 (Stunde ohne `zeit` genuegt), P07 (`all` -> `any`), P08 (Stunde ohne Zahlenwert genuegt), P18 (Issuer-Pruefung der authorization-server-Metadaten entfernt), P19 (`authorization_servers`-Pruefung entfernt), P25 (Token ohne Status 200), P26 (tools/list nur `wetter`).
  Spec requirement: AC-1 (Issuer bzw. Resource), AC-4 (Ortsname und Stundenwerte, Werkzeugliste)
  Conflict: Das Skript koennte BESTANDEN melden, obwohl diese Zusicherungen verloren gingen. `test_oauth_ablauf_unvollstaendig` hat nur Faelle, in denen mehrere Merkmale zugleich fehlen (:301, `ort` leer UND `zeit` fehlt); `test_metadaten_und_bearer_hinweis_falsch` ersetzt die Basis in allen drei Dokumenten gleichzeitig, die Ressourcen-Dokumente fangen den Fehler.
  Remediation: Je Merkmal ein Einzelfall (Stunde ohne zeit; Stunde ohne Zahl; zweite Stunde leer; nur authorization-server mit falschem Issuer; nur eine Ressource falsch).

Finding F004
  Severity: MEDIUM
  Category: edge_case
  Code reference: .claude/tools/staging_mcp_pruefen.py:61-63 (von_go), :118, :123
  Description: Fuer das nicht gelistete Konto (AC-5) und `--vor-freigabe` (AC-6) fehlt ein Test, in dem die Ablehnung NICHT von Go stammt oder keine 403 ist. Ueberlebt: P22 (CSP-Herkunftspruefung entfernt: jede 403, etwa aus nginx, gilt als Go-Ablehnung), P23 (Location egal), P41 (statt 403 genuegt "nicht 200": 302, 401, 500 zaehlen als abgelehnt).
  Spec requirement: AC-5 / AC-6 - Go antwortet mit 403 (`mcp.oauth.nicht_freigegeben`), kein Code
  Conflict: Die Zusicherung "403 von Go" ist nur dort bewacht, wo der Code steht, nicht durch einen Gegenfall.
  Remediation: Testfaelle: Zweitkonto GET 302 auf /login, 500, 403 ohne Go-CSP => je Exit 1.

Finding F005
  Severity: MEDIUM
  Category: security
  Code reference: .claude/tools/staging_mcp_pruefen.py:164-166
  Description: Der Ausnahmepfad gibt nur den Typnamen aus. Mutation P14 (`Abbruch ({e})`) ueberlebt: kein Test erzeugt eine Ausnahme, deren Text ein Geheimnis traegt (http.client nennt in `Invalid header value` den Wert, z. B. bei ungueltigem Set-Cookie des Servers).
  Spec requirement: AC-10 - Zugangsdaten, Token und Codes erscheinen nie in der Ausgabe
  Conflict: Der Ist-Code ist sicher, die Schutzmassnahme hat aber keinen Wachposten; eine Rueckkehr zu `{e}` bliebe unbemerkt.
  Remediation: Test mit Testserver, der ein Set-Cookie mit unzulaessigem Zeichen liefert; erwartet Exit 2 ohne Sitzungswert in der Ausgabe.

Finding F006
  Severity: LOW
  Category: edge_case
  Code reference: .claude/tools/staging_mcp_pruefen.py:66-70 (code_aus)
  Description: P03 (302 statt 303 genuegt), P04 (`iss` nicht geprueft), P05 (`state` nicht geprueft), P33 (Redirect-URI-Praefix egal) ueberleben.
  Spec requirement: AC-4 - Code per 303 (Go: internal/mcp/autorisieren.go:150-157 setzt state und iss)
  Conflict: Nur Code-Status 200 ist getestet (`code_status`); die uebrigen Merkmale der Weiterleitung sind ungeschuetzt.
  Remediation: Je ein Fall im Testserver (302; ohne iss; falscher state; fremde Redirect-URI).

Finding F007
  Severity: LOW
  Category: edge_case
  Code reference: .claude/tools/staging_mcp_pruefen.py:31 (TIMEOUT_S = 100)
  Description: P31 (1000 s) und P32 (1 s) ueberleben; kein Test mit haengendem Server.
  Spec requirement: AC-7 Herleitung (75 s plus Puffer), AC-10 Exit 2 bei Aufruffehlern
  Conflict: Zeitgrenze ohne Wachposten.
  Remediation: Zeitgrenze als Parameter von main, Testserver mit Schlaf, erwartet Exit 2.

Finding F008
  Severity: LOW
  Category: edge_case
  Code reference: .claude/tools/staging_mcp_pruefen.py:91-92, :158-161
  Description: Antwortet register mit 429 (eigene Wiederholungslaeufe, 20/h), meldet die Probe "Soll ohne Zugangsdaten verfehlt (HTTP 429)", Exit 1, und ueberspringt AC-4/5/6 still (client leer). Liest sich wie eine geschlossene Schranke.
  Spec requirement: Exit-Codes: 2 = Aufruf- oder Umgebungsfehler
  Conflict: Kontingent erschoepft ist ein Umgebungsfehler, kein verfehltes Soll.
  Remediation: 429 bei register als Umgebungsfehler (Exit 2) mit festem Text.

Finding F009
  Severity: LOW
  Category: anti_pattern
  Code reference: .claude/tools/staging_mcp_pruefen.py:27 (GESPERRT); .env.example:52-55
  Description: (a) Pfadvarianten (`/api/mcp/`, `/API/MCP`, `/api/mcp/oauth/`, `%2F`) werden nicht geprueft; beim Lesen kein Umgehungsweg gefunden, live unbelegt. (b) Kein Test bewacht `.env.example` (Zeile entfernbar ohne roten Test). (c) lauf.py liegt nur im Scratchpad und bildet die Schranke von Hand nach (nicht aus der Conf); im Repo nicht wiederholbar.
  Spec requirement: AC-3 - kein Verbotspfad darf sich oeffnen
  Conflict: Empfehlung.
  Remediation: Varianten in GESPERRT aufnehmen; lauf.py oder dessen Ergebnis als Artefakt ablegen.
```

### Mutationsliste

Probe-Skript (Test: tests/tdd/test_staging_mcp_pruefen.py), 41 Mutationen:
- gefangen (23): P01 Zweitkonto-Pruefung entfernt, P02 /api/internal/ 401 toleriert, P09/P10 CSP gelockert, P11 Exit 2->1, P12 Befund->Exit 0, P13 Server-Sperre weg, P16 Redirects verfolgen, P17 gesperrt nur Status 401, P20 Bearer-Hinweis gelockert, P21 Token-Fehlerfeld egal, P24 --vor-freigabe ignoriert, P27 tools/list ignoriert, P28 Origin weg, P29 isError egal, P34 register <500, P35 authorize-GET egal, P36 Umgebungsfehler verschluckt, P37 fehlende Variable erlaubt, P38/P39 Admin meldet sich als AUTH an, P40 Argumentpruefung weg, P42 POST des Zweitkontos egal.
- UEBERLEBT (18): P03, P04, P05, P06, P07, P08, P14, P18, P19, P22, P23, P25, P26, P30 (aequivalent), P31, P32, P33, P41.
Conf (Test: tests/test_staging_mcp_nginx.py im Klon), 16 Mutationen:
- gefangen (10): C04, C05, C06, C07, C08, C09 (Timeout 60 s), C10 (X-Real-IP weg), C11, C13 (limit_req), C14.
- UEBERLEBT (6): C01, C02, C03, C12, C15, C17 (F001).
Ruecknahme: Probe, Kern-Test, .env.example, Conf und Textvertrag per cmp byte-identisch zur Sicherung.

### Bestaetigungen (Implementierungsteil)

Confirmation: AC-1, Code reference: .claude/tools/staging_mcp_pruefen.py:86-89, Evidence: Status 200 plus Issuer/Resource/authorization_servers gegen basis, CONFIRMED (Logik), Live-Nachweis steht aus.
Confirmation: AC-2, Code reference: .claude/tools/staging_mcp_pruefen.py:90-95, Evidence: exakter Bearer-Header, OAuth-Pfade nur als Go-Antwort akzeptiert, CONFIRMED (Logik), Live steht aus.
Confirmation: AC-3, Code reference: .claude/tools/staging_mcp_pruefen.py:96-98, Evidence: sechs Pfade 401+Basic, /api/internal/ 403, CONFIRMED (Skript); Conf-Seite siehe F001.
Confirmation: AC-4, Code reference: .claude/tools/staging_mcp_pruefen.py:111-137, Evidence: echter Go-Server Exit 0, CONFIRMED mit F003/F006.
Confirmation: AC-5/AC-6, Code reference: .claude/tools/staging_mcp_pruefen.py:123 und :163, Evidence: echter Go-Server Exit-Matrix, CONFIRMED mit F004.
Confirmation: AC-7/AC-8, Code reference: henemm-infra tests/test_staging_mcp_nginx.py:57-66, Evidence: Textvertrag, C09/C10/C13 gefangen, CONFIRMED (nur Regressionsschutz, wie die Spec ausweist).
Confirmation: AC-9, Code reference: .claude/tools/staging_mcp_pruefen.py:120, Evidence: genau eine CSP gleich Go-Wert, P09/P10 gefangen, CONFIRMED (Logik), Live steht aus.
Confirmation: AC-10, Code reference: .claude/tools/staging_mcp_pruefen.py:140-168, Evidence: Exit 0/1/2, 76 Tests, kein Geheimnis, CONFIRMED mit F005.
AC-11, AC-12: Live-Nachweis steht aus. AC-13: Skript-Teil belegt (Exit 1 bei gesperrten Soll-Pfaden), Rollback-Uebung live steht aus.

VERDICT: BROKEN
Tests: 76 passed + 35 passed (Textvertrag), 0 failed. 18 Probe- und 6 Conf-Mutationen ueberleben (F001 bis F009).
Der Kern des Probe-Skripts stimmt (gegen echten Go-Server in allen fuenf Konfigurationen deckungsgleich, keine Geheimnisse, keine Redirect-Folge). BROKEN wegen F001 (Conf-Textvertrag laesst Totalfreigabe von Staging unbemerkt) und der ueberlebenden Mutationen F003 bis F005.
