# ADR-0128: MCP-Konnektor als Abfrage-Schnittstelle (kein Kanal) mit eigenem OAuth-2.1-Server in Go

- **Status:** Akzeptiert (Spec freigegeben vom PO 2026-11-22)
- **Datum:** 2026-11-22
- **Bezug:** Issue #3281, Spec `docs/specs/modules/mcp_wetter_konnektor.md`, Kontext `docs/context/mcp-wetter-3281.md`. Berührt [ADR-0060](0060-dauerhafte-anmeldung-mit-widerrufsliste.md) (Sitzung), [ADR-0062](0062-python-core-authentifiziert-gegenueber-go.md) (Core-Auth), [ADR-0078](0078-admin-rolle-ueber-env-liste-statt-profilfeld.md) (Admin-Allowlist als Muster), [ADR-0080](0080-kontosperre.md) (Kontosperre), [ADR-0095](0095-kanal-paritaet-jeder-kanal-jede-frage.md) (Kanal-Parität), [ADR-0104](0104-zweisprachigkeit-de-en.md) (Zweisprachigkeit), [ADR-0114](0114-ausgehende-abrufe-nutzerbestimmter-ziele-nur-ueber-abgeschotteten-client.md) (abgeschotteter Client), [ADR-0117](0117-interaktive-abrufe-eigenes-kontingent-am-fairen-anteil.md) (Kontingent), [ADR-0127](0127-ein-katalog-eine-verarbeitung.md) (Metrik-Wissen im Katalog).

## Kontext

Der PO will in der Claude-App (Handy, Web) freie Wetterfragen zu beliebigen Orten stellen („Regnet es in den nächsten 2 Stunden in Frankfurt am Main?“). Claude bindet entfernte Werkzeuge als MCP-Konnektor an; die App verlangt dafür OAuth 2.1 mit Dynamic Client Registration oder Client-ID-Metadaten-Dokument, PKCE S256 und Refresh-Tokens. Gregor hatte bisher keinen OAuth-Server (Google-Login nur als Client) und keine Bearer-Tokens. Die Inbound-Befehle per Mail/SMS/Telegram sind trip-gebunden und beantworten keine Freitext-Ortsfragen. Das Schwesterprojekt Frieda (henemm/frieda-reist) betreibt einen mit claude.ai erprobten Konnektor samt OAuth-Server (`engine/oauth.py`, `engine/konnektor.py`).

## Entscheidung

1. **Abfrage-Schnittstelle, kein Kanal.** Der Konnektor beantwortet Fragen eines angemeldeten Nutzers; er versendet nichts, hat keine Briefings und keine Alarme. Die vier Kanäle (E-Mail, Telegram, SMS, Premium-SMS) und ihre Parität nach ADR-0095 bleiben unberührt.
2. **Eigener OAuth-2.1-Server in Go** (`internal/mcp/`), Verhalten 1:1 nach Frieda: Metadaten nach RFC 9728/8414 (Ressource `<GZ_PUBLIC_HOST>/api/mcp`), DCR mit Bremse, Client-ID-Metadaten-Dokumente nur von `claude.ai` über den abgeschotteten Client (ADR-0114), Redirect-Allowlist `https://claude.ai/api/mcp/auth_callback` plus Loopback (Port frei), PKCE S256 Pflicht, `iss` in jeder Autorisierungsantwort, Code 5 Minuten und einmalig, Access-Token 3600 s, Refresh-Token 90 Tage mit Rotation und Token-Familie. Einzige fachliche Abweichung: die Anmeldung nutzt Gregors Sitzung (`gz_session`, ADR-0060); ohne Sitzung geht es über `/login?redirect=…` zurück zur Zustimmung.
3. **Zugang nur per Allowlist `GZ_MCP_USER_IDS`** (Muster ADR-0078, leer = niemand). Jede Token-Prüfung schlägt zusätzlich die Kontosperre (ADR-0080) und die Allowlist nach; Sperre und Entzug wirken sofort, auch auf ausgegebene Tokens.
4. **Tokens nur als Hash.** Clients und Tokens liegen als Dateien unter `GZ_DATA_DIR/mcp/` (sha256, nie Klartext), atomar geschrieben unter einer prozessweiten Sperre; Codes und Client-Dokumente nur im Speicher.
5. **Keine Nutzerdaten im Konnektor.** Die Werkzeuge `ort_suchen` und `wetter` liefern ausschließlich Orts- und Wetterdaten (stündliche Rohwerte in Ortszeit, Claude deutet sie). Jeder Wetterabruf bucht auf das Kontingent `user_interactive` des Token-Nutzers (ADR-0117) und läuft durch die Mengenbremsen; die Wetter-Domäne bleibt im Python-Core (ADR-0127).
6. **Schutzschichten gezielt geöffnet:** `AuthMiddleware` lässt nur die genannten Pfade durch (der MCP-Pfad prüft das Bearer-Token selbst), `IsMachinePath` nimmt nur `/token`, `/register` und `/api/mcp` aus (der MCP-Endpunkt wirkt nur mit Bearer-Token, nie mit dem Sitzungs-Cookie; eine Herkunft wie `https://claude.ai` ist dort kein CSRF-Risiko), die Zustimmung (POST `/authorize`) bleibt unter der Herkunftsprüfung und darf ein Formular sein. Die Wurzelpfade `/.well-known/oauth-*` reicht SvelteKit unverändert an Go durch. Alle Anmeldewege der Login-Seite (Passwort, Passkey, Code, Google) führen nach Erfolg auf den per `safeRedirectPath` erlaubten Rücksprung zurück.

## Verworfene Alternativen

- **OAuth-Server im Python-Core** — Sessions, Kontosperre, Allowlists und öffentliches Routing liegen in Go; ein zweiter Ort für Anmeldung wäre eine zweite Wahrheit.
- **Fremder Identitätsanbieter (z. B. Auth0, Keycloak)** — zusätzlicher Betrieb und eine zweite Nutzerverwaltung für einen einzelnen Konnektor; Friedas erprobter Ablauf ist klein und bekannt.
- **Statischer API-Schlüssel statt OAuth** — die Claude-App verlangt für entfernte Konnektoren OAuth; ein Schlüssel ließe sich zudem nicht pro Nutzer sperren.
- **Konnektor als fünfter Kanal** — er versendet nichts; Kanalparität (ADR-0095) passt nicht auf eine Frage-Antwort-Schnittstelle.

## Konsequenzen

- **Positiv:** Der PO fragt das Wetter beliebiger Orte direkt in Claude; Gregor liefert Daten, Claude formuliert. Sperre und Freigabe wirken sofort.
- **Negativ / Preis:** Erster OAuth-Server im Projekt mit eigener Angriffsfläche (öffentliche Registrierung und Token-Tausch). Codes gehen bei einem Neustart verloren (neu verbinden genügt). Auf Staging braucht es `auth_basic off`-Ausnahmen in henemm-infra.
- **Folgepflichten:** Neue Werkzeuge liefern nie Trip-, Orts-, Vergleichs- oder Empfängerdaten ohne neues ADR. Neue Nutzertexte nur über den Katalog `mcp.json` (de/en). `GZ_MCP_USER_IDS` muss in Staging und Produktion gesetzt sein, sonst kann niemand verbinden. „Auf allen Geräten abmelden“ beendet Konnektor-Tokens nicht; Entzug geht über Sperre oder Allowlist.

## Nachtrag (2026-11-26, #3398)

Die Werkzeugmenge ist um `regen_nowcast` erweitert (Radar-Nowcast, Spec `docs/specs/modules/mcp_wetter_vollstaendig.md`); `wetter` liefert jetzt alle wählbaren Katalogmetriken. Die Entscheidung bleibt unverändert: Wetterdaten, kein Kanal, keine Nutzerdaten.
