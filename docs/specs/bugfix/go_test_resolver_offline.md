---
entity_id: go_test_resolver_offline
type: bugfix
created: 2026-11-19
updated: 2026-11-19
status: draft
version: "1.0"
workflow: fix-3115-go-test-offline
tags: [go, test-politik, resolver, adr-0094, adr-0114]
---

# Go-Kern-Tests im Resolver-Umfeld netzfrei (Rest von #3115)

## Approval

- [ ] Approved

## Purpose

Der CI-Job `go-test` (Kern-Schicht, ADR-0094) darf nicht vom Internet abhaengen. Vier Tests im Resolver-/Handler-Umfeld rufen noch echte Anbieter (Komoot, Google Maps, Nominatim) auf; sie werden gegen lokale Fixture-Server netzfrei gemacht, die Live-Varianten wandern hinter `//go:build integration`, und eine dauerhafte Netzsperre im Test-Binary verhindert Rueckfaelle.

## Source

- **File:** `internal/resolver/resolver_test.go`, `internal/resolver/komoot.go`, `internal/handler/location_resolve_test.go`
- **Identifier:** `TestResolveKomootHighlight`, `TestResolveMobileGoogleMapsLink`, `TestResolveDesktopGoogleMapsPlaceLink`, `TestResolveHandlerKomootHighlight`, `resolveKomoot`

> **Schicht:** Go-API (`internal/resolver/`, `internal/handler/`). Python-Core, Frontend und Kanaele sind nicht betroffen. Keine Nutzerdaten, daher keine Zwei-Nutzer-Pruefung noetig; kein Trip/Vergleich-Pendant.

## Scope

- **LoC:** ca. +300/-40 (ueberwiegend Testcode; Produktion ca. +5/-2)
- **Files:** 6 bis 9
- **Effort:** medium
- **In Scope:** die vier netzabhaengigen Kern-Tests (Komoot-Resolver, Google mobil, Google Desktop-Place, Handler-Komoot), Hoehen-Nachschlag der Koordinaten-Tests, Netzsperre im Resolver-Paket, Probelauf Handler-Paket.
- **Out of Scope:** Open-Meteo-Tests (erledigt durch #3106); Netzabhaengigkeiten in anderen Go-Paketen (eigene Issues unter #1196); jede Verhaltensaenderung im Produktionscode ausser der Komoot-URL als Paket-Variable.

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `internal/resolver/export_test.go` | Test-Hebel | `ErlaubeTestHosts`, `ErlaubeHTTPSchema`, `ErlaubeLoopbackVerbindung`, `OhneNachschlagDienste` (nur im Testbinary, ADR-0114) |
| `internal/resolver/link_abruf_abschottung_test.go` | Vorbild | localhost-Link-Muster fuer den Google-Pfad |
| `internal/provider/openmeteo/fixture_server_test.go` | Vorbild | Fixture-Server meldet unerwartete Pfade (#3106) |
| `internal/resolver/safefetch.go` | Modul | `dialIPAllowed`, Link-Client ohne Umgebungs-Proxy |
| `internal/resolver/googlemaps.go` | Modul | `nominatimSearchURL`, `followGoogleMapsRedirect` |
| ADR-0094 | ADR | zwei Testschichten, Kern netzfrei |
| ADR-0006 | ADR | keine Mocks; lokaler echter HTTP-Server erlaubt |
| ADR-0114 | ADR | Test-Hebel nur in `export_test.go`, kein Laufzeitschalter |

## Implementation Details

Details zur Analyse: `docs/context/fix-3115-go-test-offline.md`.

1. **Komoot:** Die fest verdrahtete API-URL in `komoot.go` wird zur Paket-Variable `komootAPIURLFormat` (gleiches Verhalten, kein Env/Flag). Ersetzbar nur ueber den neuen Hebel `KomootAPIAuf(t, url)` in `export_test.go`. Fixture `internal/resolver/testdata/komoot_highlight_126361.json` im Originalformat (HAL-JSON, einmalig live aufgezeichnet, Herkunft und Datum im Test vermerkt). Der Fixture-Server prueft Pfad `/api/v007/highlights/126361` und Header `Accept: application/hal+json`; jede andere Anfrage wird per `t.Errorf` gemeldet.
2. **Google mobil:** localhost-Link nach Vorbild der Abschottungstests (Dispatch braucht `.google.` und `maps`). Der Link-Server antwortet wie Google ohne Koordinaten; ein Nominatim-Fixture-Server (Originalformat, lat/lon als Strings) liefert Wangels und prueft am Server, dass `q=` aus der Original-URL ankommt.
3. **Google Desktop-Place:** localhost-Link mit `/maps/place/Innsbruck/@47.2692,11.4041,13z`, Server antwortet 200; Koordinaten kommen aus dem Pfad.
4. **Handler-Komoot-Test** wandert in `internal/handler/location_resolve_live_test.go` (integration). Der Handler hat keinen Injektionspunkt; Erfolgspfad deckt der Resolver-Test, Handler-Pfad `TestResolveHandlerDecimalCoordinates`, Fehlerabbildung `TestResolveHandlerKomootTourUnsupported`.
5. **Koordinaten-Tests** (Dezimal/DMS/UTM, Zeitzone) nutzen `OhneNachschlagDienste`, damit der Hoehen-Nachschlag nicht ins Netz geht.
6. **Netzsperre (Ratsche):** `internal/resolver/netzsperre_test.go` mit `//go:build !integration` und `TestMain`: `dialIPAllowed` wird auf deny-all gesetzt (Abschottungstests erwarten ohne `ErlaubeLoopbackVerbindung` "kein Abruf"), `http.DefaultTransport` wird von einem RoundTripper umhuellt, der nur `127.0.0.1`, `::1` und `localhost` durchlaesst. Eine reine Proxy-Sperre genuegt nicht, weil der Link-Client keinen Proxy nutzt.
7. **Handler-Paket:** Probelauf mit loopback-only-`TestMain` (`internal/handler/netzsperre_test.go`). Nur bei sauberem Lauf aufnehmen; sonst Folge-Issue (Refs #1196) und #3115 nicht daran haengen.
8. **Live-Varianten:** `internal/resolver/resolver_live_test.go` (Komoot, Google mobil, Google Desktop) mit `//go:build integration`.

## Expected Behavior

- **Input:** `go test ./internal/resolver/ ./internal/handler/` ohne Tags (wie CI-Job `go-test`).
- **Output:** gruen; kein Verbindungsaufbau zu Hosts ausserhalb Loopback.
- **Side effects:** keine; Produktionsverhalten von `Resolve()` und `POST /api/locations/resolve` unveraendert.

## Acceptance Criteria

- **AC-1:** Given der Testlauf ohne Build-Tags / When `go test ./internal/resolver/ ./internal/handler/` laeuft / Then ist er gruen und es erfolgt kein Verbindungsaufbau ausserhalb von Loopback (Netzsperre im Resolver-Paket greift, Handler-Paket gemaess AC-9).
  - Test: Lauf der beiden Pakete ohne Tags unter der Netzsperre; ein Abruf an einen externen Host wuerde den Test rot machen.

- **AC-2:** Given der alte, unveraenderte Teststand im Resolver-Paket / When nur die Netzsperre (`TestMain`) hinzugefuegt wird, bevor irgendein Test umgebaut wird / Then werden die drei Resolver-Tests (Komoot-Highlight, Google-Mobil, Google-Desktop-Place) rot, und mit dem Fix bei aktiver Sperre wieder gruen. Der Handler-Komoot-Test wird in derselben Gegenprobe mit loopback-only-Sperre im Handler-Paket rot gesehen, bevor er in die Live-Datei wandert.
  - Test: dokumentierte Gegenprobe im Workflow-Nachweis (Ausgabe rot ohne Fix, gruen mit Fix).

- **AC-3:** Given der Komoot-Test mit lokalem Fixture-Server im Originalformat der Komoot-Antwort / When der Highlight-Link 126361 aufgeloest wird / Then entsprechen Name, Koordinaten und Hoehe exakt den Werten der Fixture, und der Server hat Pfad `/api/v007/highlights/126361` und Accept-Header `application/hal+json` gesehen; jede unerwartete Anfrage macht den Test rot.
  - Test: Aufruf von `Resolve()` mit Komoot-Link gegen httptest, Zusicherung auf konkrete Fixture-Werte und Server-Protokoll.

- **AC-4:** Given ein mobiler Google-Link, dessen Redirect keine Koordinaten liefert, und ein Nominatim-Fixture-Server / When der Link aufgeloest wird / Then kommt beim Nominatim-Server `q=` mit dem Text aus der Original-URL an und das Ergebnis enthaelt die Koordinaten aus der Fixture (Wangels).
  - Test: Server prueft den Query-Parameter `q`; fehlt oder weicht er ab, schlaegt der Test fehl.

- **AC-5:** Given ein Desktop-Place-Link mit `@47.2692,11.4041` im Pfad auf einem localhost-Server / When der Link aufgeloest wird / Then liefert die Aufloesung genau diese Koordinaten ohne Netzzugriff ausserhalb Loopback.
  - Test: `Resolve()` mit dem localhost-Link, Zusicherung auf Breite und Laenge.

- **AC-6:** Given der Produktionscode / When Komoot-Links aufgeloest werden / Then bleibt das Verhalten unveraendert (gleiche Anbieter-URL), die URL ist nur ueber den Hebel in `export_test.go` ersetzbar und es gibt keinen Env- oder Flag-Schalter.
  - Test: Aufloesung eines Komoot-Links ohne Hebel nutzt weiterhin die echte Komoot-URL (Integrationslauf, AC-7); im Normalbinary ist kein exportierter Setter vorhanden (Paketuebersetzung ohne Testdatei).

- **AC-7:** Given die Live-Varianten (Komoot, Google mobil, Google Desktop, Handler-Komoot) / When `go test -tags integration ./internal/resolver/ ./internal/handler/` laeuft / Then werden sie ausgefuehrt und pruefen den echten Anbieter-Vertrag; ohne Tag laufen sie nicht und die Netzsperre blockiert sie nicht.
  - Test: Lauf mit `-tags integration` listet die Live-Tests (`-run` bzw. `-v`), Lauf ohne Tag enthaelt sie nicht.

- **AC-8:** Given die Koordinaten-Tests (Dezimal, DMS, UTM, Zeitzone) / When sie laufen / Then findet kein Hoehen-Netzabruf statt und die Zusicherungen auf Koordinaten und Zeitzone bleiben gueltig.
  - Test: Lauf unter deny-all-Netzsperre mit `OhneNachschlagDienste` ist gruen und deutlich unter dem fruehren 8-Sekunden-Timeout je Aufruf.

- **AC-9:** Given der Probelauf des Handler-Pakets mit loopback-only-Transport / When er sauber gruen ist / Then wird die Netzsperre dort dauerhaft aufgenommen; zeigt er fremde Netzabhaengigkeiten, entsteht ein Folge-Issue (Refs #1196) und #3115 bleibt davon unabhaengig abschliessbar.
  - Test: Ergebnis des Probelaufs im Workflow-Nachweis; bei Aufnahme schlaegt ein externer Abruf im Handler-Paket fehl.

## Test Plan

Alle Kern-Tests laufen ohne Build-Tag im CI-Job `go-test`; Live-Tests nur mit `-tags integration`.

- [ ] Gegenprobe (AC-2): Netzsperre auf dem alten Teststand, die drei Resolver-Tests und der Handler-Komoot-Test werden rot; Ausgabe im Workflow-Nachweis.
- [ ] `TestResolveKomootHighlight` gegen Komoot-Fixture-Server (AC-3, AC-6).
- [ ] `TestResolveMobileGoogleMapsLink` gegen localhost-Link-Server und Nominatim-Fixture-Server mit Pruefung von `q` (AC-4).
- [ ] `TestResolveDesktopGoogleMapsPlaceLink` gegen localhost-Link-Server (AC-5).
- [ ] Koordinaten-Tests mit `OhneNachschlagDienste` unter deny-all-Sperre (AC-8).
- [ ] `netzsperre_test.go` im Resolver-Paket, Lauf beider Pakete ohne Tags gruen (AC-1).
- [ ] Probelauf Handler-Paket mit loopback-only-Sperre, Ergebnis dokumentiert (AC-9).
- [ ] `go test -tags integration` fuehrt die Live-Varianten aus (AC-7).

## Definition of Done

- Alle AC-1 bis AC-9 erfuellt und im Workflow-Nachweis belegt (inkl. Gegenprobe rot/gruen).
- CI-Job `go-test` gruen ohne Netzabruf ausserhalb Loopback im Resolver-Paket.
- Live-Varianten laufen mit `-tags integration` gruen gegen die echten Anbieter.
- Bei fremden Netzabhaengigkeiten im Handler-Paket: Folge-Issue angelegt (Refs #1196).
- Issue #3115 mit Verweis auf #3106 (Open-Meteo-Teil) und diesen Fix geschlossen.

## Known Limitations

- Der echte Redirect- und Anbieter-Vertrag (Google, Komoot) wird nur in der Integrations-Schicht (`-tags integration`, `/e2e-verify`/Deploy) geprueft, nicht im Kern.
- Der Handler-Komoot-Erfolgspfad hat keinen eigenen Offline-Test (kein Injektionspunkt, bewusst kein Produktionsschalter).
- Die Fixture ist eine Momentaufnahme der Komoot-Antwort; aendert Komoot das Format, zeigt dies nur der Live-Test.

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** keine
- **Rationale:** Umsetzung bestehender Entscheidungen (ADR-0094, ADR-0006, ADR-0114); kein neuer Entscheidungsgehalt.

## Changelog

- 2026-11-19: Initial spec created (Issue #3115, Rest-Scope)
