---
entity_id: security_haertung_2026_11_go_anmeldung
type: module
created: 2026-11-12
updated: 2026-11-12
status: implemented
version: "1.0"
tags: [security, auth, go-api, rate-limit, csrf, testkonto, issue-2961]
---

# Sicherheits-Härtung Anmeldung und Sitzung in der Go-API (Issue #2961, Paket GO-AUTH)

## Approval

- [x] Approved — PO-Auftrag 2026-11-12 (Issue #2961): alle Befunde des Sicherheits-Reviews ohne Rückfrage beheben; dieser Auftrag ist die Vorgabe.

## Purpose

Härtet Anmeldung und Sitzung der Go-API nach dem Sicherheits-Review 2026-11: Einmal-Code per
Mail mit Bremsen je Zieladresse, Testkonto-Schalter nur in Test-Umgebungen, Herkunftsprüfung
schreibender Anfragen, Bremsen für weitere Konto-Aktionen, Zeit- und Größengrenzen sowie
Kleinteile (Zugriffslog, Maschinen-Geheimnisse, Enumeration). Architektur-Entscheidung:
ADR-0113.

## Source

- **Files:** `internal/handler/auth_magic.go`, `internal/handler/attempt_guard.go`,
  `internal/handler/auth.go`, `internal/handler/sms_verify.go`, `internal/handler/keyed_lock.go`,
  `internal/handler/telegram_connect.go`, `internal/middleware/ratelimit.go`,
  `internal/middleware/request_guard.go`, `internal/middleware/access_log.go`,
  `internal/config/origins.go`, `internal/config/secret_min.go`, `internal/store/user.go`,
  `internal/router/router.go`, `cmd/server/main.go`,
  `frontend/src/routes/magic-link/verify/+page.svelte`, `frontend/src/routes/magic-link/verify/+page.server.ts`,
  `frontend/src/lib/i18n/messages/{de,en}/auth.json`, `internal/i18n/messages/{de,en}/fehler.json`
- **Schicht:** Go-API (`internal/`, `cmd/server/`), dazu das Eingabefeld des Anmelde-Codes im
  SvelteKit-Frontend. Kein Python-Core.

> **Querschnitts-Prüfpunkte:** Keine Trip-/Ortsvergleich-Bausteine betroffen. Mandantentrennung:
> alle Bremsen sind je Nutzer bzw. je Adresse geschlüsselt und mit zwei Nutzern/Adressen
> getestet. Keine Briefing-/Alarm-Inhalte betroffen.

## Estimated Scope

- **LoC:** ~900 (davon ~60 % Tests)
- **Files:** ~35 (Code, Tests, Doku)
- **Effort:** high

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `MailFloodLimiter` | Go-Typ | Bremse je Schlüssel (Adresse/Nutzer) für Mails und Anträge |
| `config.Config` | Go-Konfiguration | `PublicHost`, `Env`, `TestFixtureDir`, `AdminUserIDs`, Maschinen-Geheimnisse |
| ADR-0060, ADR-0072, ADR-0078, ADR-0105 | ADR | werden durch ADR-0113 ergänzt |

## Implementation Details

1. **Einmal-Code (GA1).** `attemptGuard` (Zähler je Schlüssel, vor dem Vergleich erhöht,
   Sperre nach `max` Versuchen) mit 5/15 min/15 min je Zieladresse; je Code weiterhin höchstens
   3 Vergleiche (atomar reserviert). Anforderung: `MailFloodLimiter(5, 1h)` je Adresse, über dem
   Kontingent neutrale 200 ohne Versand; ein nutzbarer Code (nicht abgelaufen, Vergleiche übrig)
   wird erneut zugestellt. Code: `rand.Int(rand.Reader, 10^8)`, 8 Ziffern, Vergleich mit
   `subtle.ConstantTimeCompare`. IP-Limiter: IPv6 auf /64, Tabelle mit Obergrenze (Bereinigung,
   notfalls Verdrängung).
2. **Testkonto-Schalter (GA4).** `is_test_user` nur bei `Env=staging`, `TestFixtureDir` gesetzt
   oder gültiger Admin-Sitzung (Cookie selbst geprüft, die Route ist öffentlich), sonst
   `400 validation_failed`. Reservierte Kennungen. `UserExists` = Kontoordner vorhanden.
   `Store.CreateUser` legt den Ordner per `os.Mkdir` exklusiv an. Startwarnung für privilegierte
   Kennungen ohne Konto; das Seed-Konto prüft die `user.json`.
3. **Herkunftsprüfung (GA5).** Middleware-Kette vor der Anmeldeprüfung: `LimitBody` (1 MB,
   GPX 10 MB, 413) → `OriginGuard` (403 `origin_forbidden`) → `RequireJSONBody` (415).
   Ausnahmen: `/api/webhooks/`, `/api/internal/`, `/api/_internal/`, `/api/scheduler/status`,
   `/api/auth/google/callback`. Erlaubte Ursprünge: `config.BrowserOrigins`.
4. **SMS-Bestätigungscode (GA7).** Sperre je Nutzer um Laden/Zählen/Vergleichen/Speichern,
   Zähler wird vor dem Vergleich gespeichert, Bremse 10 je 10 min je Nutzer.
5. **Bremsen und Grenzen (GA8).** Passwortwechsel 5 Fehlversuche/15 min je Nutzer (429).
   Tarif-Antrag 3/Tag je Nutzer, identische Wiederholung eines gemeldeten Antrags ohne Mail.
   Telegram-Link: ein Token je Nutzer, Ablage als SHA-256 (der Python-Kern liest die Datei nicht,
   er löst über `POST /api/internal/telegram-connect` ein), Alt-Schlüssel werden beim Laden
   umgerechnet, Bremse 10/h. `http.Server` mit `ReadHeaderTimeout` 10 s, `ReadTimeout` und
   `IdleTimeout` 2 min, ohne `WriteTimeout` (Versand bis 300 s, vgl.
   `fix_2124_versand_nginx_timeout.md`).
6. **Kleinteile (GA10).** Zugriffslog maskiert Webhook-Pfadgeheimnisse und `code`/`state`/`token`.
   Maschinen-Geheimnisse unter 32 Zeichen: nur Warnzeile beim Start, der Endpunkt bleibt mit dem
   konfigurierten Wert in Betrieb (kein stilles Schließen eines Eingangskanals beim Deploy);
   fail-closed bleibt allein „kein Geheimnis gesetzt“ (Seven-Signierschlüssel ausgenommen). Reset-/Bestätigungs-Token: erst Vergleich, dann Ablauf. Passkey-Start: schon
   gleichförmig, per Test festgehalten. `/api/health` bleibt unverändert (die CI liest die
   Commit-Kennung unangemeldet vom Staging).

## Expected Behavior

- **Input:** HTTP-Anfragen an die Go-API.
- **Output:** wie bisher; zusätzlich 403 `origin_forbidden`, 413 `payload_too_large`,
  415 `unsupported_media_type`, 429 `rate_limit_exceeded` an den genannten Stellen.
- **Side effects:** Warnzeilen beim Start; Telegram-Tokendatei enthält nur Hashes.

## Acceptance Criteria

**AC-1:** Given eine Adresse mit angefordertem Einmal-Code / When fünf falsche Codes innerhalb von 15 Minuten eingegeben werden, auch über eine Neuanforderung hinweg / Then wird für diese Adresse 15 Minuten lang jeder Code, auch der richtige, mit derselben neutralen Antwort abgelehnt, eine andere Adresse ist nicht betroffen, und gleichzeitige Fehlversuche führen zu höchstens fünf gezählten Versuchen.
  - Test: `internal/handler/anmelde_code_haertung_2961_test.go` (Sperre, zweite Adresse, Parallelität)

**AC-2:** Given eine Adresse / When innerhalb einer Stunde mehr als fünf Codes angefordert werden / Then antwortet der Dienst immer gleich neutral, verschickt aber ab der sechsten Anforderung keine Mail mehr, und eine andere Adresse bekommt ihre Mail weiterhin.
  - Test: `TestAnmeldeCode_AnforderungsBremseJeAdresse`

**AC-3:** Given ein noch gültiger Einmal-Code / When dieselbe Adresse erneut einen Code anfordert / Then wird derselbe Code mit unverändertem Ablauf erneut zugestellt und bleibt einlösbar.
  - Test: `TestAnmeldeCode_NeuanforderungStelltDenselbenCodeErneutZu`

**AC-4:** Given eine Code-Anforderung / When die Mail zugestellt wird / Then trägt sie einen achtstelligen Ziffern-Code, den das Eingabefeld (acht Ziffern) annimmt und der einlösbar ist; kürzere Eingaben weist die Seite ab.
  - Test: `TestAnmeldeCode_HatAchtZiffernUndStehtInDerMail`, Frontend `auth_seiten_zweisprachig.test.ts` (Fall `code_nicht_achtstellig`)

**AC-5:** Given Anfragen aus vielen Adressen eines IPv6-/64-Netzes bzw. sehr vielen Absendern / When sie den IP-Limiter treffen / Then teilen sich alle Adressen eines /64 ein Kontingent, und die Limiter-Tabelle überschreitet ihre Obergrenze nicht.
  - Test: `internal/middleware/ratelimit_ipv6_2961_test.go`

**AC-6:** Given ein Code, dessen drei Vergleiche verbraucht sind, und eine noch nicht gesperrte Adresse / When die Adresse erneut einen Code anfordert / Then wird ein frischer Code zugestellt, der nach Ablauf einer etwaigen Sperre einlösbar ist.
  - Test: `TestAnmeldeCode_FehlversuchsSperreJeAdresseUeberlebtNeuanforderung`

**AC-7:** Given eine Produktionskonfiguration ohne Staging und Fixture-Modus / When jemand ohne Admin-Sitzung mit `is_test_user` registriert / Then antwortet der Dienst 400 `validation_failed`, und es entsteht weder Konto noch Kontoordner; ohne Schalter klappt die Registrierung wie bisher.
  - Test: `TestTestkontoSchalter_ProduktionOhneAdminAbgelehnt`

**AC-8:** Given Staging, Fixture-Modus oder eine gültige Admin-Sitzung / When ein Testkonto mit fester Kennung registriert wird / Then entsteht es mit genau dieser Kennung und `is_test_user`.
  - Test: `TestTestkontoSchalter_StagingFixtureUndAdminErlaubt`

**AC-9:** Given ein vorhandener Kontoordner ohne `user.json` / When dieselbe Kennung registriert wird / Then antwortet der Dienst 409 `user_already_exists` und übernimmt keine verwaisten Daten.
  - Test: `TestTestkontoSchalter_VerwaisterOrdnerIstBelegt`

**AC-10:** Given eine reservierte Kennung wie `default` / When sie registriert werden soll / Then lehnt der Dienst mit 400 ab, auch im Staging.
  - Test: `TestTestkontoSchalter_ReservierteKennungAbgelehnt`

**AC-11:** Given zwei oder mehr gleichzeitige Registrierungen derselben Kennung / When sie verarbeitet werden / Then gewinnt genau eine, alle anderen erhalten 409.
  - Test: `TestTestkontoSchalter_KontoanlageIstExklusiv`

**AC-12:** Given Kennungen in `GZ_ADMIN_USER_IDS`/`GZ_QUOTA_EXEMPT_USER_IDS`, zu denen kein Konto existiert / When der Server startet / Then steht je Kennung eine Warnzeile im Log, für vorhandene Konten keine.
  - Test: `cmd/server/start_warnungen_2961_test.go`

**AC-13:** Given ein angemeldeter Nutzer / When eine schreibende API-Anfrage mit fremdem `Origin` oder mit `Sec-Fetch-Site` `cross-site`/`same-site` eintrifft / Then antwortet der Dienst 403 `origin_forbidden` und ändert nichts; das gilt auch für die öffentliche Anmeldung.
  - Test: `TestHerkunft_FremdeHerkunftWirdAbgewiesen`

**AC-14:** Given der eigene Ursprung, `same-origin`/`none` oder fehlende Herkunftsheader / When eine schreibende Anfrage eintrifft / Then wird sie normal bearbeitet; im Fixture-Modus und im Staging sind zusätzlich localhost-Ursprünge erlaubt, lesende Anfragen sind nie betroffen.
  - Test: `TestHerkunft_EigeneHerkunftUndServerAufrufeErlaubt`, `TestHerkunft_LoopbackNurImFixtureOderStaging`

**AC-15:** Given ein Webhook- oder interner Pfad / When eine Anfrage mit fremder Herkunft oder ohne JSON eintrifft / Then greift die Schutzschicht nicht, die Pfade behalten ihre eigenen Nachweise.
  - Test: `TestHerkunft_MaschinenpfadeAusgenommen`

**AC-16:** Given eine schreibende Anfrage mit Rumpf / When ihr Inhaltstyp nicht `application/json` ist / Then antwortet der Dienst 415 `unsupported_media_type`; der GPX-Upload nimmt `multipart/form-data` an, Anfragen ohne Rumpf sind nicht betroffen.
  - Test: `TestSchutz_JSONPflichtFuerRumpfe`

**AC-17:** Given ein Rumpf über 1 MB (GPX-Upload: über 10 MB) / When er an die API geht / Then antwortet der Dienst 413 `payload_too_large`, ein GPX-Upload von 3 MB geht durch.
  - Test: `TestSchutz_GroessenBegrenzung`

**AC-18:** Given ein Webhook-Pfad mit eigener Größenprüfung / When ein Rumpf über 1 MB eintrifft / Then greift die globale Rumpfgrenze dort nicht.
  - Test: `TestSchutz_GroessenBegrenzung` (Webhook-Teil)

**AC-19:** Given ein ausstehender SMS-Bestätigungscode / When viele falsche Codes gleichzeitig eingehen / Then werden höchstens fünf verglichen, danach ist auch der richtige Code verbrannt.
  - Test: `TestSmsVerify_GleichzeitigeFehlversucheHoechstensFuenfVergleiche`

**AC-20:** Given ein Nutzer / When er mehr als zehn Einlöse-Versuche in zehn Minuten schickt / Then antwortet der Dienst 429 mit `Retry-After`, ein anderer Nutzer ist nicht betroffen.
  - Test: `TestSmsVerify_MengenbremseJeNutzer`

**AC-21:** Given ein angemeldeter Nutzer / When er fünfmal ein falsches altes Passwort beim Passwortwechsel angibt / Then antwortet der Dienst danach 15 Minuten lang 429, auch mit richtigem Passwort, und ein anderer Nutzer kann weiter wechseln.
  - Test: `TestPasswortwechsel_FehlversuchsBremseJeNutzer`

**AC-22:** Given ein Nutzer mit gemeldetem Tarif-Antrag / When er denselben Antrag wiederholt bzw. mehr als drei Anträge am Tag stellt / Then geht für die Wiederholung keine weitere Betreiber-Mail hinaus, und der vierte Antrag erhält 429.
  - Test: `TestTarifAntrag_BremseUndKeineDoppelMail`

**AC-23:** Given ein Nutzer fordert mehrfach einen Telegram-Verknüpfungslink an / When die Tokendatei geschrieben wird / Then gilt nur das jüngste Token dieses Nutzers, die Datei enthält nur SHA-256-Werte und keine abgelaufenen Einträge, Tokens anderer Nutzer und Alt-Dateien mit Klartextschlüsseln bleiben einlösbar.
  - Test: `TestTelegramLink_EinTokenJeNutzerNurAlsHash`, `TestTelegramLink_AltdateiMitKlartextBleibtEinloesbar`

**AC-24:** Given ein Nutzer / When er mehr als zehn Verknüpfungslinks in einer Stunde anfordert / Then antwortet der Dienst 429, ein anderer Nutzer ist nicht betroffen.
  - Test: `TestTelegramLink_MengenbremseJeNutzer`

**AC-25:** Given der HTTP-Server / When ein Client seinen Anfragekopf nicht fertig sendet bzw. eine Bearbeitung länger als die Einlesegrenze dauert / Then wird die hängende Verbindung geschlossen, die lange Bearbeitung aber zu Ende beantwortet (kein `WriteTimeout`).
  - Test: `cmd/server/server_zeitgrenzen_2961_test.go`

**AC-26:** Given Anfragen an Webhooks mit Pfadgeheimnis oder mit `code`/`state`/`token` in der Query / When das Zugriffslog schreibt / Then stehen diese Werte maskiert im Log, der übrige Pfad bleibt lesbar.
  - Test: `TestZugriffslog_MaskiertGeheimnisse`

**AC-27:** Given ein gesetztes, aber kürzer als 32 Zeichen langes Maschinen-Geheimnis / When der Router aufgebaut wird / Then erscheint je Geheimnis eine Warnzeile im Log, der betroffene Endpunkt arbeitet mit dem konfigurierten Wert weiter (richtiger Wert angenommen, falscher abgewiesen); geschlossen bleibt ein Endpunkt nur, wenn gar kein Geheimnis gesetzt ist.
  - Test: `TestMaschinenGeheimnisse_KurzWarntUndBleibtInBetrieb`

**AC-28:** Given ein abgelaufenes Reset- bzw. Bestätigungs-Token / When ein falsches Token eingereicht wird / Then lautet die Antwort `invalid_token`; `token_expired` erst, wenn das Token selbst stimmt.
  - Test: `TestResetToken_AblaufErstNachVergleich`, `TestBestaetigungsToken_AblaufErstNachVergleich`

**AC-29:** Given eine unbekannte Kennung bzw. ein Konto ohne Passkey / When der Passkey-Anmeldestart aufgerufen wird / Then sind Status und Rumpf beider Antworten gleich.
  - Test: `TestPasskeyStart_UnbekanntUndOhnePasskeyGleichfoermig`

## Known Limitations

- Alle neuen Bremsen leben im Arbeitsspeicher; ein Neustart setzt sie zurück.
- Ein unangekündigter (chunked) zu großer Rumpf bricht erst beim Lesen ab; die Antwort ist dann
  die Fehlerantwort des jeweiligen Handlers (meist 400), nicht 413.
- `/api/health` nennt die Commit-Kennung weiter unangemeldet: die CI (`.github/workflows/ci.yml`)
  liest sie vom Staging. Eine Umstellung braucht zuerst einen Maschinen-Token-Weg dort.
- Der Seven-Signierschlüssel ist von der Mindestlänge ausgenommen (Format vom Anbieter).
- Nicht in diesem Paket (Welle 2): Re-Auth bei Adresswechsel/Passkey-Verwaltung, Verhalten
  unbestätigter Konten bei erneuter Registrierung, Schreibsperre für `user.json`,
  Cookie-Name.

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** ADR-0113
- **Rationale:** Ändert Entscheidungsflächen Auth (Rate-Limits der E-Mail-Anmeldung aus ADR-0105,
  Testkonto-Flag aus ADR-0072) und führt eine neue Schutzschicht für alle schreibenden Anfragen ein.

## Changelog

- 2026-11-12: Erstfassung und Umsetzung (Issue #2961).
- 2026-11-12: AC-27 geändert — kurze Maschinen-Geheimnisse nur noch Warnung, Endpunkt bleibt in Betrieb (Längen der Betriebswerte nicht prüfbar, Deploy darf keinen Kanal schließen).
