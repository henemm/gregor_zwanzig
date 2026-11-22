---
entity_id: mcp_wetter_konnektor
type: module
created: 2026-11-22
updated: 2026-11-22
status: draft
version: "1.0"
tags: [mcp, oauth, wetter, go-api, python-core, adr-0128]
workflow: mcp-wetter-3281
---

# MCP-Konnektor „Gregor Wetter“

## Approval

- [ ] Approved

## Purpose

Der Konnektor „Gregor Wetter“ ist ein Remote-MCP-Server, den ein freigegebener Nutzer in der Claude-App (Handy/Web) hinzufügt, um freie Wetterfragen zu beliebigen Orten zu stellen („Regnet es in den nächsten 2 Stunden in Frankfurt am Main?“, „Wie viel Sonne hat Münster in den nächsten 3 Tagen?“). Gregor löst den Ort auf und liefert stündliche Rohwerte in Ortszeit; Claude interpretiert selbst (keine Ampel, keine Bewertung, kein Gregor-Renderer). Zugang haben nur Nutzer in `GZ_MCP_USER_IDS` (fail-closed: leer = niemand), und der Konnektor hat keinerlei Zugriff auf Trips, Orte, Vergleiche, Empfänger oder andere Nutzerdaten (Issue #3281).

## Source

- **File:** `internal/mcp/` (neu, Go: OAuth-2.1-Server und MCP-Endpunkt), `internal/resolver/ortssuche.go` (neu, Go: Freitext-Ortssuche), `api/routers/mcp_wetter.py` (neu, Python-Core: Stundenwerte)
- **Identifier:** `mcp.Handler` (JSON-RPC `initialize`/`tools/list`/`tools/call`), `resolver.OrtSuchen`, `GET /api/_internal/mcp/wetter`

Vorlage (Verhalten inhaltlich 1:1, in Go übertragen, Ablage als Dateien statt SQLite): Repo henemm/frieda-reist, `engine/oauth.py` (OAuth 2.1), `engine/konnektor.py` (`frieda_antwort`, `antwort_auf`, `PROTOKOLLE`, HTTP-Klasse mit `do_POST`/`do_GET`), `engine/konten.py` (`_tokens_ausstellen`, `oauth_code_einloesen`, `oauth_erneuern`, Tabellen `oauth_tokens`/`oauth_codes`). Laufzeiten wie dort: Access-Token 3600 s (`ACCESS_SEKUNDEN`), Refresh-Token 90 Tage (`REFRESH_TAGE`). Einziger Unterschied: Der Anmeldeschritt nutzt Gregors bestehende Session (`gz_session`); ohne Session Umleitung auf `/login?redirect=<authorize-URL>` (vorhandener Rücksprung, `safeRedirectPath`).

> **Schicht-Hinweis (geprüft per Glob/Grep):** Auth, Sessions, Kontosperre, Allowlist, Kontingent-Anbindung und öffentliches Routing liegen in Go (`internal/`); die Wetter-Domäne bleibt in Python (`api/`, `src/`, ADR-0127). Neu sind `internal/mcp/`, `internal/resolver/ortssuche.go`, `api/routers/mcp_wetter.py`, `frontend/src/routes/.well-known/[...pfad]/+server.ts` und `internal/i18n/messages/{de,en}/mcp.json`. Vorhanden und zu ändern: `internal/middleware/auth.go`, `internal/middleware/request_guard.go`, `internal/router/router.go`, `internal/config/config.go`, `internal/egress/inventory.go` (Nominatim-Host ist bereits eingetragen), `internal/handler/nutzer_mengenbremse.go`, `api/main.py`.

> **Querschnitts-Prüfpunkte:**
> - **Trip/Ortsvergleich-Teilung:** kein Trip-/Compare-Pendant; reine Abfrage-Schnittstelle ohne Editor, daher keine `shared/`-Komponente.
> - **Mandantentrennung:** Jeder Token ist an genau eine echte `user_id` gebunden (aus der Session beim Autorisieren, nie `"default"`); der Konnektor liest keine Nutzerdaten. Test mit zwei verschiedenen Nutzern (AC-5).
> - **Kanäle:** Der Konnektor ist ein Abfrage-Weg und **kein Kanal** im Sinn von ADR-0095 (kein Briefing, kein Alarm, kein Versand); die vier Kanäle E-Mail, Telegram, SMS, Premium-SMS bleiben unberührt. Das hält ADR-0128 fest.

## Estimated Scope

- **LoC:** Scheibe 1 ca. 250 (Go ca. 120, Python ca. 100, Katalog/Tests-Fixtures ca. 30 ohne Tests); Scheibe 2 ca. 450 Produktivcode (OAuth ca. 280, MCP ca. 120, Verdrahtung/Durchreichung ca. 50); Tests zusätzlich. Wegen des Umfangs zwei Scheiben, jede mit eigenem PR.
- **Files:** Scheibe 1: 8; Scheibe 2: 12; zusätzlich eine Datei im Fremd-Repo henemm-infra.
- **Effort:** high

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `gz_session` / `issueSession` (`internal/handler/auth.go`) | module | bestehende Anmeldung; `/authorize` liest die Session, ADR-0060 |
| `GZ_ADMIN_USER_IDS`-Muster (`internal/config/admin.go`, ADR-0078) | pattern | Vorbild für `GZ_MCP_USER_IDS`, fail-closed |
| Kontosperre `disabled` (ADR-0080) | module | gesperrte Konten bekommen keinen Code/Token; vorhandene Tokens werden ungültig |
| `AuthMiddleware` (`internal/middleware/auth.go`) | module | öffentliche Pfade für OAuth/MCP, Bearer-Prüfung nur im MCP-Pfad |
| `OriginGuard`/`RequireJSONBody`/`LimitBody`, `IsMachinePath` (`internal/middleware/request_guard.go`) | module | gezielte Ausnahmen für `/token` und `/register` (Maschinenaufrufe); `/authorize` POST bleibt Browser-Formular mit Herkunftsprüfung |
| Abgeschotteter Client und Erlaubnisliste (`internal/resolver/safefetch.go`, `internal/egress/inventory.go`, ADR-0114) | module | Nominatim-Freitext, auch CIMD-Abruf der `client_id` |
| Mengenbremsen (`internal/handler/nutzer_mengenbremse.go`, Bremse `aufloesen`, `vorhersage`) | module | Bremse für Ortssuche und Wetterabruf je Nutzer |
| Kontingent `user_interactive` (`internal/handler/forecast.go`, `reserviereForecastBudget`, ADR-0117) | module | jeder Wetterabruf bucht wie `/api/forecast` |
| Core-Auth `X-GZ-Core-Auth` (ADR-0062) | module | Go ruft den neuen internen Core-Endpunkt authentifiziert auf |
| `src/app/metric_catalog.py`, `src/services/weather_metrics.py` (ADR-0127) | module | Sonnenminuten je Stunde abgeleitet (`dni_wm2` > 120 W/m²), Metrik-Wissen nur im Katalog |
| `src/providers/openmeteo.py`, `src/services/forecast.py` | module | Rohdatenquelle des Core |
| i18n-Katalog Go (`internal/i18n/messages/{de,en}/`, ADR-0104) | module | Werkzeugbeschreibungen und Fehlertexte in der Sprache des Kontos |
| `frontend/src/routes/login/`, `safeRedirectPath` | module | Login mit Rücksprung auf `/authorize` |
| Nominatim (`nominatim.openstreetmap.org`) | extern | Geocoding Freitext (Name, Land, lat/lon, Zeitzone) |
| henemm-infra `nginx/staging.gregor20.henemm.com.conf` | extern | `auth_basic off` für OAuth-/MCP-/well-known-Pfade auf Staging |

## Implementation Details

### Scheibe 1: Ortssuche und Wetter-Datenweg

**Ortssuche (Go, `internal/resolver/ortssuche.go`):** `OrtSuchen(ctx, text, sprache)` fragt Nominatim per Freitext über den abgeschotteten Client (ADR-0114) und liefert je Kandidat Anzeigename, Land, lat/lon und IANA-Zeitzone (Zeitzone aus Koordinaten abgeleitet, Fallback über den Core-Hinweis). Höchstens 5 Kandidaten, Eingabe auf sinnvolle Länge begrenzt und als Freitext kodiert (nie als Pfad). Die Mengenbremse `aufloesen` gilt je Nutzer; Überschreitung ergibt einen verständlichen Fehler mit Wartezeit.

**Core-Endpunkt (`api/routers/mcp_wetter.py`):** `GET /api/_internal/mcp/wetter?lat&lon&von&bis` (mit `X-GZ-Core-Auth`, ADR-0062). Er liefert kompakte stündliche Rohwerte in **Ortszeit** (naiv-UTC wird in die Zeitzone des Ortes umgerechnet, ISO-Zeit mit Offset) samt Einheiten je Feld: Temperatur, Niederschlag (mm), Niederschlagswahrscheinlichkeit, Wind, Böen, Windrichtung, Bewölkung, Gewitterstufe, **Sonnenminuten je Stunde** (abgeleitet nach Katalog, ADR-0127: Schwelle `dni_wm2` > 120 W/m², nicht in Go oder im Frontend nachgebaut), WMO-Wettercode, Schneefallgrenze/Nullgrenze. Maximal 7 Tage; ein längerer Zeitraum wird begrenzt und die Antwort trägt `begrenzt: true` samt tatsächlichem Ende. Provider-Fehler liefern 502 mit Katalogtext, Ausnahmetext nur im Log (wie `api/routers/forecast.py`).

**Kontingent:** Vor jedem Core-Aufruf bucht Go über `reserviereForecastBudget` (Priorität `user_interactive`, 1500/Nutzer/Tag, ADR-0117); zusätzlich Mengenbremse `vorhersage` (60/min). Ist das Kontingent erschöpft, entsteht ein Werkzeugfehler mit Hinweis auf die Wartezeit, kein Abruf.

### Scheibe 2: OAuth 2.1 und MCP-Endpunkt (Go, `internal/mcp/`)

**Pfade:** unter `/api/…` (`/api/mcp`, `/api/mcp/oauth/authorize`, `/api/mcp/oauth/token`, `/api/mcp/oauth/register`) sowie `/.well-known/oauth-protected-resource` und `/.well-known/oauth-authorization-server`. Die `/.well-known/`-Pfade gehen per nginx an SvelteKit; eine Route `frontend/src/routes/.well-known/[...pfad]/+server.ts` reicht sie ohne Änderung an Go durch (kein Eingriff in henemm-infra dafür).

**OAuth-Verhalten 1:1 wie Frieda:** Metadaten (Ressource und Server, `iss` in jeder Autorisierungsantwort), Dynamic Client Registration mit IP-Mengenbremse, Client-ID-Metadaten-Dokument (CIMD) für `claude.ai` über den abgeschotteten Client, Redirect-Allowlist `https://claude.ai/api/mcp/auth_callback` plus Loopback-Adressen (Port frei), PKCE S256 Pflicht, Zustimmungsseite mit CSP, Authorization-Code (kurzlebig, einmalig), Access-Token 3600 s, Refresh-Token 90 Tage mit Rotation und Token-Familie (Wiederverwendung eines rotierten Refresh-Tokens entwertet die ganze Familie). `WWW-Authenticate: Bearer resource_metadata="…"` bei fehlendem/ungültigem Token.

**Abweichung Anmeldeschritt:** `GET /authorize` prüft `gz_session`. Ohne Session: 302 auf `/login?redirect=<authorize-URL>`. Mit Session, aber `user_id` nicht in `GZ_MCP_USER_IDS` oder Konto gesperrt: Fehlerseite, kein Code. Sonst Zustimmungsseite; erst das POST derselben Herkunft (Cookie `SameSite=Lax` trägt die Top-Level-Navigation) erzeugt den Code und leitet an die Redirect-URI weiter.

**Ablage:** Clients, Tokens und Familien als Dateien unter `GZ_DATA_DIR` (Datei-Sperre wie Sessions, ADR-0060, Schreiben atomar), **nur als Hash** (`sha256`, nie Klartext). Authorization-Codes und CIMD-Cache im RAM (kurzlebig). Jeder Token trägt `user_id`, `client_id`, Familie und Ablauf. Die Token-Prüfung schlägt zusätzlich in Konto-Zustand (`disabled`) und `GZ_MCP_USER_IDS` nach, sodass Sperre oder Entzug der Freigabe sofort wirken.

**Schutzschichten:** `AuthMiddleware` bekommt gezielte öffentliche Ausnahmen (Metadaten, `/token`, `/register`, `/authorize`; der MCP-Pfad prüft das Bearer-Token selbst). `IsMachinePath` nimmt nur `/token` und `/register` aus (kein Browser-Origin, Form bzw. JSON von claude.ai); `RequireJSONBody` erlaubt für `/token` `application/x-www-form-urlencoded`. `/authorize` POST bleibt unter `OriginGuard`. Der SvelteKit-Durchreicher `apiPfad.ts` bleibt unverändert (`/api/*` geht per nginx direkt an Go).

**MCP-Endpunkt:** Streamable HTTP, nur POST mit JSON-Antwort, GET → 405 (wie Frieda); Protokollversionen `2025-11-25`, `2025-06-18`, `2025-03-26`, `2024-11-05` (`PROTOKOLLE`); Methoden `initialize`, `tools/list`, `tools/call`, `ping`. Zwei Werkzeuge:

- `ort_suchen(text)`: liefert Kandidaten (Name, Land, lat/lon, Zeitzone).
- `wetter(ort | lat+lon, von, bis, felder?)`: löst `ort` über dieselbe Ortssuche auf; ist er eindeutig, ruft Go den Core und antwortet mit Ortsname, Zeitzone, Einheiten und Stundenwerten. Mehrdeutiger Ort → Kandidatenliste statt Wetter, unbekannter Ort → Werkzeugfehler (`isError`) mit Hinweis, Zeitraum >7 Tage → begrenzt mit Hinweis im Ergebnis.

Werkzeugbeschreibungen und alle Fehlertexte kommen aus dem Katalog `mcp.json` (de/en) in der Sprache des Kontos (`language`, ADR-0104); Protokoll-Token und Feldnamen werden nicht übersetzt. Die Antworten enthalten ausschließlich Wetter- und Ortssuchdaten.

### Lieferung und Begleitarbeiten

- **ADR-0128** „MCP-Konnektor als Abfrage-Schnittstelle (kein Kanal) mit eigenem OAuth-2.1-Server in Go“ (`docs/adr/0128-mcp-konnektor-abfrage-schnittstelle-oauth-in-go.md`, Eintrag in `docs/adr/README.md`; `tests/test_adr_index_drift.py`). Grenzt gegen ADR-0095 ab und hält fest: erster OAuth-Server in Gregor, Allowlist `GZ_MCP_USER_IDS`, Tokens nur als Hash.
- **Staging:** eigener PR im Repo henemm-infra mit `auth_basic off` für `/api/mcp`, `/api/mcp/oauth/`, `/.well-known/oauth-*` in `nginx/staging.gregor20.henemm.com.conf`; ohne ihn ist kein Test mit der Claude-App auf Staging möglich.
- **Konfiguration:** `GZ_MCP_USER_IDS` (komma-getrennt, leer = niemand) in `internal/config/config.go` und in den Betriebs-Umgebungen von Staging und Produktion.

## Expected Behavior

- **Input:** MCP-JSON-RPC-POST mit `Authorization: Bearer <access_token>`; Werkzeugaufrufe `ort_suchen` und `wetter`.
- **Output:** Ortsname, Zeitzone und stündliche Rohwerte mit Einheiten in Ortszeit (maximal 7 Tage); bei Mehrdeutigkeit Kandidaten; bei Fehlern ein verständlicher Werkzeugfehler in der Sprache des Kontos.
- **Side effects:** Buchung auf das Kontingent `user_interactive` je Wetterabruf; Anlage von Client-, Token- und Familien-Dateien (nur Hashes); Zugriff auf Nominatim und Open-Meteo. Keine Änderung an Trips, Orten, Vergleichen, Empfängern.

## Test Plan

### Automated Tests (TDD RED)

- [ ] Test 1: GIVEN Nominatim-Antwort mit Frankfurt am Main WHEN `ort_suchen`/`wetter` für „Frankfurt am Main“ läuft THEN Ortsname und Stundenwerte der nächsten 2 Stunden in Ortszeit.
- [ ] Test 2: GIVEN Core mit Strahlungsdaten WHEN `wetter` für Münster über 3 Tage läuft THEN je Stunde Sonnenminuten, in Summe je Tag ableitbar.
- [ ] Test 3: GIVEN zwei Nutzer, nur einer in `GZ_MCP_USER_IDS` WHEN beide `/authorize` bestätigen THEN nur der freigegebene bekommt einen Code.
- [ ] Test 4: GIVEN Token von Nutzer A WHEN Nutzer B Antworten/Daten abfragt THEN B erhält mit A-Token nichts von B; Antworten enthalten nie Trip-/Orts-/Empfängerdaten.
- [ ] Test 5: GIVEN MCP-Aufruf ohne Token THEN 401 mit `WWW-Authenticate` inkl. `resource_metadata`.
- [ ] Test 6: GIVEN Redirect-URI außerhalb der Allowlist THEN Autorisierung/Registrierung abgelehnt.
- [ ] Test 7: GIVEN Code ohne oder mit falschem `code_verifier` WHEN `/token` THEN `invalid_grant`.
- [ ] Test 8: GIVEN Refresh-Token WHEN zweimal eingelöst THEN zweites Mal `invalid_grant` und Familie entwertet.
- [ ] Test 9: GIVEN gültiges Token WHEN Konto gesperrt wird THEN Token ungültig (401).
- [ ] Test 10: GIVEN erschöpftes Kontingent WHEN `wetter` THEN Werkzeugfehler mit Hinweis, kein Core-Abruf.
- [ ] Test 11: GIVEN unbekannter/mehrdeutiger Ort und Zeitraum >7 Tage THEN Werkzeugfehler bzw. Kandidaten bzw. begrenzte Antwort mit Hinweis.
- [ ] Test 12: GIVEN Konto mit `language=en` THEN Werkzeugbeschreibung und Fehlertext englisch.
- [ ] Test 13 (E2E auf Staging, `/e2e-verify`): Konnektor in Claude-App hinzufügen, anmelden, zustimmen, Wetterfrage stellen.

Tests laufen gegen echte Handler/Router mit lokalem Fake-Nominatim-Server und echtem Core bzw. aufgezeichneten Open-Meteo-Antworten, ohne `Mock()`-Theater und ohne Dateiinhalt-Prüfungen.

## Acceptance Criteria

- **AC-1:** Given ein freigegebener Nutzer mit gültigem Token / When er fragt „Regnet es in den nächsten 2 Stunden in Frankfurt am Main?“ und Claude `wetter` mit diesem Ort aufruft / Then enthält die Antwort den aufgelösten Ortsnamen und die Stundenwerte (u. a. Niederschlag mm und Niederschlagswahrscheinlichkeit) der nächsten 2 Stunden in Ortszeit mit Einheiten.
  - Test: Werkzeugaufruf `wetter` über den echten MCP-Endpunkt; geprüft werden Ortsname, zwei Stundeneinträge mit Offset der Ortszeit und Einheitenangaben.

- **AC-2:** Given ein freigegebener Nutzer / When er die Sonne in Münster für die nächsten 3 Tage erfragt / Then liefert `wetter` je Stunde Sonnenminuten, sodass Sonnenstunden je Tag und über 3 Tage ableitbar sind.
  - Test: Aufruf für Münster über 72 Stunden; je Stunde ein Sonnenminutenwert 0 bis 60, die Summe je Tag entspricht den Stundenwerten.

- **AC-3:** Given ein Nutzer, dessen Kennung nicht in `GZ_MCP_USER_IDS` steht (oder die Liste leer ist) / When er `/authorize` aufruft und zustimmen will / Then erhält er keinen Code und kein Token, sondern eine verständliche Fehlerseite.
  - Test: angemeldeter Nutzer ohne Freigabe durchläuft den Ablauf; kein Redirect mit `code`, `/token` liefert nichts; bei leerer Liste dasselbe für jeden Nutzer.

- **AC-4:** Given ein Nutzer ohne Session / When er `/authorize` aufruft / Then wird er auf `/login?redirect=…` mit Rücksprung auf die Autorisierung umgeleitet und landet nach der Anmeldung wieder auf der Zustimmungsseite.
  - Test: Aufruf ohne Cookie liefert 302 auf Login mit korrektem `redirect`; nach Login mit Cookie erscheint die Zustimmungsseite.

- **AC-5:** Given zwei verschiedene Nutzer, beide freigegeben, jeder mit eigenen Trips, Orten und Empfängern / When Nutzer B das Token von Nutzer A verwendet / Then handelt es ausschließlich als A, und keine Antwort des Konnektors (Werkzeugliste, Ergebnisse, Fehler) enthält Trip-, Orts-, Vergleichs- oder Empfängerdaten irgendeines Nutzers.
  - Test: zwei Nutzer mit Testdaten; Antworten beider Werkzeuge werden auf diese Namen und Adressen durchsucht (kein Treffer); Token A erlaubt keine Anmeldung als B.

- **AC-6:** Given ein MCP-Aufruf ohne oder mit ungültigem Bearer-Token / When er an den MCP-Endpunkt geht / Then antwortet Gregor mit 401 und `WWW-Authenticate: Bearer … resource_metadata="…"`, und die dort verlinkten Metadaten sind abrufbar.
  - Test: POST ohne Token; Header geprüft; die `resource_metadata`-URL (`/.well-known/oauth-protected-resource`) liefert JSON über SvelteKit-Durchreichung, ebenso `/.well-known/oauth-authorization-server`.

- **AC-7:** Given eine Autorisierung oder Client-Registrierung mit einer Redirect-URI außerhalb der Allowlist (`https://claude.ai/api/mcp/auth_callback`, Loopback) / When sie abgeschickt wird / Then wird sie abgelehnt und es entsteht weder Code noch Client.
  - Test: Registrierung und Autorisierung mit `https://evil.example/cb` werden abgewiesen; die Claude-Callback-URI wird akzeptiert.

- **AC-8:** Given ein gültiger Authorization-Code / When `/token` ohne `code_verifier` oder mit falschem Verifier aufgerufen wird / Then antwortet Gregor mit `invalid_grant`, und der Code ist verbraucht.
  - Test: Austausch ohne und mit falschem Verifier scheitert; mit richtigem Verifier und frischem Code entsteht ein Token (S256).

- **AC-9:** Given ein ausgegebenes Refresh-Token / When es eingelöst wird / Then erhält der Client neue Tokens und der alte Refresh-Token ist ungültig; wird ein bereits rotierter Refresh-Token erneut benutzt, sind alle Tokens der Familie entwertet.
  - Test: erster Refresh gelingt; zweite Nutzung des alten Tokens gibt `invalid_grant`; danach scheitert auch der neue Refresh-Token und der neue Access-Token liefert 401.

- **AC-10:** Given ein gültiges Token / When der Administrator das Konto des Nutzers sperrt (ADR-0080) / Then liefert der MCP-Endpunkt mit diesem Token 401, und ein neuer Code wird nicht ausgestellt.
  - Test: Token funktioniert; Konto sperren; derselbe Aufruf gibt 401, `/authorize` verweigert den Code.

- **AC-11:** Given ein freigegebener Nutzer mit erschöpftem Kontingent `user_interactive` / When `wetter` aufgerufen wird / Then kommt ein verständlicher Werkzeugfehler (`isError`) in der Sprache des Kontos mit Hinweis auf die Wartezeit, und es findet kein Wetterabruf statt.
  - Test: Kontingent des Testnutzers wird ausgeschöpft; Antwort enthält Fehlertext mit Wartezeit; der Core-Zähler steigt nicht weiter.

- **AC-12:** Given ein Ortsname, den Nominatim nicht kennt / When `wetter` oder `ort_suchen` aufgerufen wird / Then antwortet das Werkzeug mit einem Fehler samt Hinweis, den Ort genauer zu schreiben, und liefert keine erfundenen Werte.
  - Test: Anfrage mit Unsinnsname; Werkzeugfehler mit Hinweis, kein Wetterblock.

- **AC-13:** Given ein mehrdeutiger Ort wie „Frankfurt“ / When `wetter` aufgerufen wird / Then nennt das Werkzeug die Kandidaten (Name, Land, Koordinaten) und bittet um Auswahl, statt zu raten; mit eindeutigem Kandidaten (Koordinaten) liefert es Wetter.
  - Test: Anfrage „Frankfurt“ ergibt mindestens zwei Kandidaten ohne Stundenwerte; Folgeaufruf mit Koordinaten eines Kandidaten liefert Stundenwerte.

- **AC-14:** Given eine Anfrage für 10 Tage / When `wetter` aufgerufen wird / Then wird der Zeitraum auf 7 Tage begrenzt und das Ergebnis weist ausdrücklich auf die Begrenzung und das tatsächliche Ende hin.
  - Test: Aufruf mit 10 Tagen; höchstens 168 Stundeneinträge und Begrenzungshinweis im Ergebnis.

- **AC-15:** Given zwei Konten mit `language` Deutsch bzw. Englisch / When sie `tools/list` abrufen oder einen Fehler auslösen / Then sind Werkzeugbeschreibungen und Fehlertexte in der Sprache des jeweiligen Kontos, Werkzeug- und Feldnamen bleiben unübersetzt.
  - Test: beide Konten rufen `tools/list` und einen Fehlerfall auf; Texte differieren sprachrichtig, Namen identisch.

- **AC-16:** Given Staging mit den `auth_basic off`-Ausnahmen / When ein freigegebener Nutzer den Konnektor „Gregor Wetter“ in der Claude-App hinzufügt, sich anmeldet, zustimmt und eine Wetterfrage stellt / Then erscheint die Antwort mit Ortsname und Stundenwerten in der App.
  - Test: Ende-zu-Ende auf Staging in `/e2e-verify` (Anmeldung über Claude-App-Ablauf, Zustimmung, Werkzeugaufruf).

## Known Limitations

- Kein Regenradar und kein Nowcast; Auflösung stündlich. „Regnet es in 2 Stunden?“ wird aus Stundenwerten beantwortet.
- Zeitraum maximal 7 Tage je Aufruf.
- Staging liegt hinter Basic-Auth; die nötigen `auth_basic off`-Ausnahmen liegen im Repo henemm-infra und sind Teil der Lieferung (eigener PR dort).
- Authorization-Codes und CIMD-Cache liegen im RAM und gehen bei Neustart verloren (Codes sind kurzlebig, ein neuer Anmeldeversuch genügt); Tokens und Clients bleiben als Dateien erhalten.
- Zunächst nur für Nutzer in `GZ_MCP_USER_IDS`; weitere Nutzer brauchen eine Env-Änderung (kein Selbstbedienungs-Zugang).
- Ortsauflösung hängt an Nominatim (Nutzungsrichtlinie, Mengenbremse `aufloesen`).

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** ADR-0128 (neu, Teil der Lieferung)
- **Rationale:** Der MCP-Konnektor ist eine Abfrage-Schnittstelle, kein Kanal im Sinn von ADR-0095, und führt den ersten OAuth-2.1-Server in Gregor ein (Entscheidungsfläche Auth). Er wird in Go gebaut, weil dort Sessions, Kontosperre, Allowlists und Routing liegen; die Wetter-Domäne bleibt in Python (ADR-0127). Berührt ADR-0060, 0062, 0078, 0080, 0104, 0114, 0117.

## Changelog

- 2026-11-22: Initial spec created (Issue #3281, Workflow mcp-wetter-3281)
