---
entity_id: security_haertung_2026_11_go_schnittstellen
type: module
created: 2026-11-12
updated: 2026-11-12
status: approved
version: "1.0"
tags: [security, go-api, resolver, rate-limit, staging, premium-sms, issue-2961]
---

# Sicherheits-Härtung der Go-Schnittstellen (Review 2026-11, Paket GO-CORE)

## Approval

- [x] Approved — Auftrag des PO (Issue #2961): alle Befunde des Reviews 2026-11 ohne Rückfrage
  beheben; dieser Auftrag ist die Freigabe. Zielkonflikt zu Punkt 7 siehe Known Limitations.

## Purpose

Die Go-API rief vom Nutzer eingegebene Kartenlinks ungeprüft ab, setzte Kennungen ungeschützt in
Upstream-URLs, hinterließ Dateien für erfundene Kennungen, ließ gespeicherte Daten unbegrenzt
wachsen und hatte für zustellende oder teure Klicks keine Obergrenze je Nutzer. Diese Spec legt das
sichere Soll-Verhalten der Go-Schnittstellen fest (Grundsatzentscheidungen in ADR-0114).

## Source

- **Go-API:** `internal/resolver/safefetch.go` (neu), `googlemaps.go`, `komoot.go`;
  `internal/egress/guard.go` (`HTTPAllowed`); `internal/handler/nutzer_mengenbremse.go` (neu),
  `wachstumsgrenzen.go` (neu), `staging_zugang.go` (neu), `send_proxy.go` (`coreKennung`),
  `proxy.go`, `preview_proxy.go`, `briefing_send.go`, `briefing_preview.go`, `compare_preset.go`,
  `trip.go`, `location.go`, `weather_config.go`, `briefing_subscription.go`, `forecast.go`,
  `staging_verify_token.go`, `staging_sms_code.go`, `staging_seed.go`, `premium_sms_ratelimit.go`;
  `internal/store/pathsafe.go`, `briefing_lock.go`, `briefing_subscription.go`, `trip.go`,
  `location.go`, `compare_preset.go`; `internal/router/router.go` (nur die betroffenen Routen).
- Kein Frontend, kein Python. Trip/Ortsvergleich-Teilung: keine neue Komponente.
- **Mandantentrennung:** alle Bremsen, Grenzen und Kennungsprüfungen arbeiten mit der `user_id`
  aus dem Auth-Kontext; Tests mit je zwei Nutzern.

## Estimated Scope

- **LoC:** ~900 Produktiv + ~1100 Tests (Override durch den Orchestrator: Sammelauftrag 8 Punkte)
- **Files:** ~30
- **Effort:** high

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| ADR-0062 | ADR | Dienstgeheimnis am `http.DefaultTransport` (bleibt, ergänzt durch ADR-0114) |
| ADR-0083 | ADR | gemeinsame Schreibsperre Go/Python (Protokoll unverändert) |
| ADR-0072 | ADR | Testkonto über Profilfeld `is_test_user` |
| ADR-0092 | ADR | eine Mail pro Klick (ergänzt um Obergrenze) |
| `QuotaPolicyMiddleware` | Go | Ausnahme-Policy (Admins, `GZ_QUOTA_EXEMPT_USER_IDS`) |

## Implementation Details

1. **Kartenlinks (GC1).** Google-Zweig: Eingabe mit `url.Parse`, nur `https`, Host exakt aus
   `maps.app.goo.gl`, `goo.gl`, `www.google.com`, `maps.google.com`, `google.com` oder
   `^(www\.|maps\.)?google\.(com|[a-z]{2}|co\.[a-z]{2}|com\.[a-z]{2})$`; keine Nutzer-Info.
   Sonst `resolve_failed`/`fach.resolver.maps_aufloesen` ohne Abruf. Abruf über
   `newLinkClient`: eigener `http.Transport` (kein Proxy, keine Keep-Alives, 64 KB Kopfgrenze),
   `net.Dialer.Control` prüft die verbundene IP (`isPublicUnicastIP`), `CheckRedirect` prüft jeden
   Hop gegen dieselbe Liste (≤ 5), ein umhüllender RoundTripper fragt `egress.HTTPAllowed`. Der
   Rumpf wird nie gelesen. Komoot: Host aus `www.komoot.com`/`komoot.com`/`www.komoot.de`/
   `komoot.de`, abgerufen wird weiterhin nur die feste Komoot-API. Testöffnung nur über
   `internal/resolver/export_test.go`.
2. **Kennungen (GC2).** `coreKennung` (Prüfung `ValidEntityID` → 400, dann `url.PathEscape`) auf
   allen Alt-Routen; kind-neutrale Routen escapen zusätzlich. `ValidEntityIDRe` sperrt
   `\x00-\x1f`, `\x7f`, `?`, `#`, `%` (Leerzeichen bleiben erlaubt).
3. **Sperrdateien (GC3).** `LockBriefing`/`LockBriefingErr` hängen an die Freigabe
   `RemoveBriefingLockFile`, wenn keine `<id>.json` existiert.
4. **Wachstum (GC4).** Neue Config-Schlüssel `^[a-z0-9_.-]{1,64}$`, ≤ 200 je Map (vor dem Merge
   geprüft, Bestandsschlüssel frei); ≤ 100 Etappen, ≤ 500 Wegpunkte je Etappe; `Save*` verweigert
   Dateien > 2 MB (`store.ErrEntityTooLarge` → 413). `sessions.json` unverändert (ADR-0060: keine
   Ablaufprüfung, jede Kennung auf der Liste ist eine gültige Anmeldung; Datei gehört zum
   Anmeldebereich).
5. **Bremsen (GC5).** `NutzerBremsen` (gleitendes Fenster je Nutzer, geteilte Parallel-Grenze),
   im Router um die Routen gelegt; aus bei `TestFixtureDir != ""`. GPX: `MaxBytesReader` 10 MB,
   vollständig gelesen vor dem Upstream-Aufruf. Forecast: Anbieter-Fehler nur ins Log.
6. **Staging (GC6).** `StagingZugang{Admins, Betreiber=GZ_AUTH_USER}`; Testkonto über
   `model.IsTestAccount`.
7. **Premium-SMS (GC7 c/d).** Fehlversuche je gleitender Stunde (10), Warn-Log bei Erschöpfung,
   Kommentar zum Schlüsselraum (23³·8³ ≈ 6,2 Mio.). Kein Ablauf/keine Entwertung des Codes.
8. **GC8.** `LoadBriefing`/`SaveBriefing` prüfen die Kennung.

## Expected Behavior

- **Input:** Anfragen an die genannten Routen.
- **Output:** wie bisher; zusätzlich 400/403/404/413/422/429 laut `docs/reference/api_contract.md`
  Abschnitt 0.6.
- **Side effects:** keine verwaisten Sperrdateien; Warn-Log bei erschöpfter Premium-SMS-Bremse.

## Acceptance Criteria

- **AC-1:** Given ein angemeldeter Nutzer / When er als Ort einen Link eingibt, der nur nach
  Kartenlink aussieht (fremder Host, Kartenwort in Pfad oder Query, Nutzer-Info vor dem Host) /
  Then antwortet die Ortsauflösung „nicht auflösbar" und der fremde Host erhält keine Anfrage;
  ein http-Link wird auch für einen erlaubten Host nicht abgerufen.
  - Test: `internal/resolver/link_abruf_abschottung_test.go` (Empfänger-Zähler am httptest-Server)
- **AC-2:** Given ein erlaubter Kartenlink leitet auf einen Host außerhalb der Erlaubnisliste
  weiter / When die Ortsauflösung ihm folgt / Then wird das Weiterleitungsziel nicht abgerufen,
  und eine Kette wird nach höchstens fünf Weiterleitungen abgebrochen.
  - Test: `TestLinkAbruf_RedirectAufFremdenHostWirdNichtVerfolgt`, `…HoechstensFuenfWeiterleitungen`
- **AC-3:** Given ein erlaubter Hostname löst auf eine interne Adresse auf (Loopback, privat,
  Link-Local, CGNAT, Multicast, IPv4-mapped) / When die Ortsauflösung ihn abrufen will / Then
  kommt keine Verbindung zustande.
  - Test: `TestLinkAbruf_InterneAdresseWirdNichtVerbunden`, `…ErlaubnislisteUndAdresssperre`
- **AC-4:** Given das Dienstgeheimnis für den Python-Core ist installiert / When die
  Ortsauflösung eine Adresse abruft (auch die des Cores, mit im Test geöffneten Sperren) / Then
  trägt die Anfrage den Header `X-GZ-Core-Auth` nicht; ohne Testöffnung findet gar kein Abruf
  statt.
  - Test: `TestLinkAbruf_TraegtKeinDienstgeheimnis`
- **AC-5:** Given ein Nutzer / When er mehr als 30 Ortsauflösungen in einer Minute auslöst /
  Then erhält er 429 mit `Retry-After` und verständlichem Text in seiner Sprache.
  - Test: `TestMengenbremse_Ortsaufloesung30JeMinute`
- **AC-6:** Given eine Kennung mit Query-, Fragment-, Kodierungs- oder Steuerzeichen im Pfad /
  When sie an eine Versand-, Vorschau-, Etappenwetter- oder Lade-Route geht (auch Alt-Routen) /
  Then antwortet die API 400 und der Core erhält keine Anfrage.
  - Test: `internal/router/kennung_kodiert_an_core_test.go`
- **AC-7:** Given eine zulässige Kennung mit Umlaut oder Leerzeichen und eine mitgeschickte
  fremde `user_id` / When die Route an den Core weiterreicht / Then kommt die Kennung als genau
  ein kodiertes Pfadsegment an, mit genau einer `user_id` — der des angemeldeten Nutzers.
  - Test: `TestKennung_WirdKodiertWeitergereicht`
- **AC-8:** Given Bestandskennungen (Slugs mit Umlauten, `cp-`-Kennungen, kurze Zufallskennungen)
  / When sie geprüft werden / Then bleiben sie gültig; `?`, `#`, `%` und Steuerzeichen nicht.
  - Test: `internal/store/entity_id_upstream_zeichen_test.go`
- **AC-9:** Given ein Nutzer / When er 25 erfundene Kennungen über Lesen, Schreiben, Status,
  Wetter-Konfiguration und Löschen von Trips, Ortsvergleichen und Briefings anfragt / Then bleibt
  im Nutzerverzeichnis keine einzige Sperrdatei zurück, und ein echter Trip bleibt danach les- und
  schreibbar.
  - Test: `internal/router/sperrdatei_unbekannte_kennung_test.go`
- **AC-10:** Given ein gespeicherter Trip, Ort oder Ortsvergleich / When eine Änderung neue
  Schlüssel außerhalb von `^[a-z0-9_.-]{1,64}$`, mehr als 200 Schlüssel je Map, mehr als 100
  Etappen, mehr als 500 Wegpunkte je Etappe oder eine Datei über 2 MB bringen würde / Then
  antwortet die API 400 bzw. 413 im bestehenden Fehlerformat, die Datei bleibt unverändert,
  vorhandene Schlüssel bleiben schreibbar und eine größere Bestandsdatei bleibt lesbar.
  - Test: `internal/router/wachstumsgrenzen_test.go`
- **AC-11:** Given ein Nutzer mit Sprache Englisch / When er mehr als 10 Kanal-Testnachrichten in
  einer Stunde anfordert / Then erhält er 429 mit `Retry-After` und englischem Katalogtext.
  - Test: `TestMengenbremse_Testnachricht10JeStundeZweisprachig`
- **AC-12:** Given zwei Nutzer / When der erste über Trip-, Ortsvergleichs- und kind-neutrale
  Versandroute zusammen mehr als 20 Sofort-Versände in einer Stunde auslöst / Then erreicht der
  21. den Core nicht (429), während der zweite Nutzer weiter versenden kann.
  - Test: `TestMengenbremse_HandversandGeteilt20JeStunde`
- **AC-13:** Given ein Nutzer / When er Wettervergleich, Etappenwetter oder Vorschauen je Route
  mehr als 60-mal in einer Minute abruft / Then erhält er 429; das Fenster einer Route belastet
  die andere nicht.
  - Test: `TestMengenbremse_Vergleich60JeMinute`
- **AC-14:** Given ein Nutzer hat vier schwere Abrufe gleichzeitig laufen / When er einen fünften
  startet / Then erhält er 429 (Variante „parallel"), ein anderer Nutzer nicht, und nach dem Ende
  der Abrufe ist wieder Platz.
  - Test: `TestMengenbremse_HoechstensVierGleichzeitig`
- **AC-15:** Given ein Nutzer / When er eine GPX-Datei über 10 MB oder mehr als 30 GPX-Dateien in
  einer Stunde hochlädt / Then antwortet die API 413 bzw. 429 und der zu große Rumpf erreicht den
  Core nicht.
  - Test: `TestMengenbremse_GpxGroesseUndMenge`
- **AC-16:** Given ein Admin oder ein Konto aus `GZ_QUOTA_EXEMPT_USER_IDS` / When es mehr als die
  Grenze versendet / Then wird es nie gebremst.
  - Test: `TestMengenbremse_AdminUndAusnahmelisteUngebremst`
- **AC-17:** Given der CI-Stack im Fixture-Modus / When ein E2E-Lauf viele Versände auslöst /
  Then greift keine Bremse.
  - Test: `TestMengenbremse_FixtureModusOhneBremse`
- **AC-18:** Given Staging und ein gewöhnliches, nicht frisch angelegtes Konto / When es
  Bestätigungstoken, SMS-Code oder Seed anfordert / Then erhält es 403 und sein Tarif bleibt
  unverändert.
  - Test: `internal/router/staging_hilfswege_zugang_test.go`
- **AC-19:** Given Staging und ein Admin-, Betreiber- oder Testkonto / When es ein
  Bestätigungstoken für ein frisch registriertes, unbestätigtes Konto anfordert / Then erhält es
  das Token; für ein fremdes bestätigtes Konto erhält es dieselbe 404-Antwort wie für ein
  unbekanntes, und es entsteht kein Token.
  - Test: `TestStagingHilfswege_ZugangUndZielkonten`
- **AC-20:** Given Staging und ein vor wenigen Minuten registriertes Wegwerfkonto / When es seinen
  eigenen SMS-Bestätigungscode anfordert / Then erhält es den Code (Live-Spec
  `feat-2406-sms-verify.spec.ts` bleibt lauffähig).
  - Test: `TestStagingHilfswege_ZugangUndZielkonten`
- **AC-21:** Given zehn falsche Verknüpfungscodes innerhalb einer Stunde / When danach der
  richtige Code eintrifft / Then wird er abgewiesen (429) und eine Warnung steht im Log; eine
  Stunde nach dem ersten Fehlversuch verknüpft derselbe Code wieder.
  - Test: `internal/handler/premium_sms_ratelimit_zeitfenster_test.go`
- **AC-22:** Given eine Kennung mit Pfadtrenner / When `LoadBriefing` oder `SaveBriefing`
  aufgerufen wird / Then kommt `ErrInvalidEntityID` zurück und außerhalb des Nutzerverzeichnisses
  entsteht nichts.
  - Test: `internal/store/briefing_subscription_kennung_test.go`
- **AC-23:** Given der Wetteranbieter liefert einen Fehler mit interner Adresse im Text / When ein
  Nutzer `/api/forecast` abruft / Then erhält er 502 `provider_error` mit Katalogtext, ohne den
  Anbieter-Text.
  - Test: `TestForecastHandler_AnbieterFehlerOhneRohtext`

## Known Limitations

- **Zielkonflikt Premium-SMS-Code (GC7 d) — bewusst nicht umgesetzt.** Ein Ablauf nach 24 Stunden
  und die Entwertung nach der ersten Einlösung würden die Neuverknüpfung unterwegs verhindern: die
  gelernte Rückadresse gilt 30 Tage (`PremiumSmsReplyTTL`); danach (oder bei einer neuen
  Garmin-Rückadresse) braucht der Nutzer den notierten Code erneut — ohne Web-Zugang kann er
  keinen neuen erzeugen. Die Oberfläche sagt „notiere ihn jetzt", Erneuern entwertet den alten
  (fix_2154). Umgesetzt sind nur Zeitfenster-Bremse und Kommentar. Produktentscheidung offen.
- **Staging-Testkonten sind selbst erklärbar.** `is_test_user` lässt sich bei der Registrierung
  setzen (ADR-0072, Konsequenzen); die Aufrufer-Prüfung der Staging-Wege hält daher vor allem
  gewöhnliche Konten fern, die tragende Grenze ist die Zielkonto-Regel.
- **Kennungsmuster Python.** `app.loader.VALID_ENTITY_ID_RE` ist nicht nachgezogen; die geteilte
  Wahrheitstabelle enthält die neuen Fälle bewusst nicht.
- **Mengenbremsen im Arbeitsspeicher**, je Prozess; ein Neustart setzt sie zurück.
- **Staging-E2E-Konten** (`GZ_AUTH_USER`, `GZ_E2E_EN_USER`, Validator-Konten) laufen in die
  Bremsen, wenn sie weder Admin noch in `GZ_QUOTA_EXEMPT_USER_IDS` stehen.

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** ADR-0114
- **Rationale:** neue dauerhafte Regeln für ausgehende Abrufe, das Weiterreichen von Kennungen und
  Obergrenzen interaktiver Auslöser; ergänzt ADR-0062, ADR-0003, ADR-0092.

## Changelog

- 2026-11-12: Erstfassung (Issue #2961).
