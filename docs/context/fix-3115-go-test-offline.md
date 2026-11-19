# Context: fix-3115-go-test-offline

## Request Summary
CI-Job `go-test` darf nicht vom Netz abhängen (Test-Politik ADR-0094, Sammelprojekt #1196). Der Open-Meteo-Teil von #3115 ist durch #3106 (Commit 2c99fd655) bereits erledigt. Rest-Scope laut Intake-Kommentar 19.11.: die Go-Kern-Tests mit echtem Netzabruf im Resolver-Umfeld nach dem #3106-Muster offline machen (lokaler httptest-Server + Fixture im Originalformat, Live-Variante hinter `//go:build integration`).

## Netzabhängige Kern-Tests (Ist-Stand)
| Test | Netzabruf | Befund |
|---|---|---|
| `internal/resolver/resolver_test.go::TestResolveKomootHighlight` | Komoot-API `https://www.komoot.com/api/v007/highlights/126361` | im Intake genannt |
| `internal/handler/location_resolve_test.go::TestResolveHandlerKomootHighlight` | dieselbe Komoot-API über `ResolveLocationHandler()` | im Intake genannt |
| `internal/resolver/resolver_test.go::TestResolveMobileGoogleMapsLink` | Redirect-Abruf `maps.google.com` (Link-Client) + Nominatim-Fallback | im Intake genannt |
| `internal/resolver/resolver_test.go::TestResolveDesktopGoogleMapsPlaceLink` | Redirect-Abruf `www.google.com` über `followGoogleMapsRedirect` — bei Netzfehler `resolve_failed` | **NEU gefunden, im Intake übersehen** (Kommentar im Test: „echter HTTP-Call") |
| Dezimal/DMS/UTM-Tests (`TestResolveDecimal*`, `TestResolveTimezoneAlwaysSet`, Handler-Pendants) | `lookupElevation` → open-elevation.com (finalize(..., true)) | scheitert still (ElevationM bleibt nil), Zusicherungen hängen nicht daran; nur Laufzeit bis 8 s Timeout je Aufruf. Kein Rot-Risiko, aber Netzkontakt im Kern |

**Warum die Intake-Gegenprobe den Desktop-Test nicht fand:** sie sperrte das Netz per Proxy (127.0.0.1:9). Der abgeschottete Link-Client (`newLinkClient`, safefetch.go) nutzt bewusst **keinen** Umgebungs-Proxy (`Transport.Proxy == nil`, ADR-0114) und ging daher trotzdem ins echte Netz. `unshare -rn` ist auf diesem Host nicht erlaubt (uid_map). Die Gegenprobe im Fix braucht eine andere Netzsperre (z. B. Dial-Sperre im Test oder CI-Lauf ohne Netz) — in der Analyse festlegen.

## Related Files
| File | Relevance |
|---|---|
| `internal/resolver/komoot.go` | `resolveKomoot`: API-URL **fest verdrahtet** (`fmt.Sprintf("https://www.komoot.com/api/v007/highlights/%s", id)`), eigener `&http.Client{Timeout:10s}` (DefaultTransport). Braucht Paket-Variable (analog `nominatimSearchURL`), nur über export_test.go ersetzbar |
| `internal/resolver/googlemaps.go` | `resolveGoogleMaps`, `followGoogleMapsRedirect` (Link-Client), `nominatimSearchURL` (Paket-Var), Fallback-Kette @lat,lon → Pfad → ll/q → Nominatim |
| `internal/resolver/elevation.go` | `elevationLookupURL` (Paket-Var) |
| `internal/resolver/safefetch.go` | Abschottung ADR-0114: `linkHostAllowed`, `linkSchemes`, `linkPortErlaubt`, `dialIPAllowed` (nur über export_test.go ersetzbar), `komootLinkHosts` |
| `internal/resolver/export_test.go` | Test-Hebel nur im Testbinary: `ErlaubeTestHosts`, `ErlaubeHTTPSchema`, `ErlaubeLoopbackVerbindung`, `OhneNachschlagDienste` (lenkt Höhe+Nominatim auf 404-Server) |
| `internal/resolver/link_abruf_abschottung_test.go` | Vorbild offline-Google-Pfad: Link `http://localhost:<port>/maps?q=.google.` erfüllt die Dispatch-Bedingung in `Resolve()` und läuft gegen httptest |
| `internal/resolver/resolver.go` | `Resolve()`-Dispatch (`komoot.com` → Komoot; `.google.`+`maps` → Google), `finalize` |
| `internal/handler/location_resolve.go` | `ResolveLocationHandler()` ruft paketglobal `resolver.Resolve` — **kein Injektionspunkt** |
| `internal/provider/openmeteo/fixture_server_test.go`, `provider_live_test.go`, `internal/handler/forecast_test.go` | Muster #3106 (Fixture-Server merkt unerwartete Pfade; Live-Datei mit `//go:build integration`) |
| `.github/workflows/*.yml` Job `go-test` | `go test ./...` (ohne Tags) |

## Existing Patterns
- #3106: httptest-Server mit Antwort im Originalformat aus `testdata/`, Server protokolliert Pfade und meldet unerwartete Anfragen als Testfehler; Live-Variante in `*_live_test.go` mit `//go:build integration`.
- Resolver: Anbieter-Endpunkte als Paket-Variablen, die **nur** export_test.go ersetzt (kein Laufzeitschalter in Produktion, ADR-0114).
- Test-Politik: kein Mock-Theater; lokaler echter HTTP-Server ist erlaubt (ADR-0006, ADR-0094).

## Dependencies
- Upstream: Komoot-API (HAL-JSON: `name`/`base_name`, `mid_point`/`start_point`, `_embedded.coordinates.items`, `elevation`), Google-Redirects, Nominatim (JSON-Liste mit lat/lon als Strings), open-elevation, `openmeteo.TimezoneForCoords` (offline).
- Downstream: `POST /api/locations/resolve` (Frontend Orts-Import), keine weiteren Go-Aufrufer von `resolver.Resolve`.

## Existing Specs / ADRs
- ADR-0114 (abgeschotteter Client für nutzerbestimmte Ziele) — Test-Hebel nur in export_test.go.
- ADR-0094 (zwei Testschichten), ADR-0006 (keine gemockten Tests).
- Keine eigene Resolver-Modul-Spec gefunden; Herkunft der ACs: #276 (Google-Links), #2961 (Abschottung).

## Risks & Considerations
1. **Handler-Test kann export_test.go des Resolver-Pakets nicht nutzen** (anderes Paket). Optionen für die Analyse: (a) Handler-Komoot-Test auf Fixture-Ebene über einen exportierten Test-Hebel in einem neutralen Testhilfe-Paket (z. B. `internal/resolver/resolvertest`) — aber ohne Produktions-Laufzeitschalter; (b) Handler-Test ersetzt `http.DefaultTransport` für die Testdauer durch einen Transport, der `www.komoot.com` auf den lokalen Server lenkt (Komoot nutzt DefaultTransport; kein Produktionseingriff; Achtung Parallelität/`t.Parallel`); (c) Handler-Test auf Fehlerabbildung reduzieren und Komoot-Erfolgspfad nur im Resolver-Paket prüfen. Empfehlung in /20-analyse treffen.
2. Komoot-API-URL muss zur Paket-Variable werden (kleine Produktionsänderung, Verhalten unverändert); darf nicht per Env/Flag umschaltbar sein.
3. Fixture im **Originalformat** der Komoot-Antwort für Highlight 126361 (Gavia-Pass) — Aufzeichnung einmalig live, Herkunft im Test vermerken.
4. Mobiler Google-Link offline: Test-Link über `localhost`-Muster; Server antwortet wie Google (Redirect auf Einwilligungsseite ohne Koordinaten) → Nominatim-Fixture-Server liefert Wangels. Die Zusicherung „q= aus der Original-URL wird an Nominatim gegeben" sollte am Fixture-Server geprüft werden (Query-Parameter), sonst prüft der Test nur sich selbst.
5. Desktop-Place-Link: Koordinaten stehen schon in der Eingabe; offline nachstellen über localhost-Link mit `@47.2692,11.4041` im Pfad.
6. Elevation-Lookups der Koordinaten-Tests: per `OhneNachschlagDienste` netzfrei machen (gleich miterledigen, kleiner Aufwand, macht Kern-Lauf schneller).
7. Netzfreiheits-Nachweis: Proxy-Sperre reicht nicht (Link-Client ohne Proxy). Analyse muss eine belastbare Gegenprobe festlegen.
8. Live-Varianten (`//go:build integration`) für Komoot und Google-Mobil beibehalten, damit der echte Anbieter-Vertrag weiter prüfbar bleibt.

## Analysis

### Type
Bug (Test-Infrastruktur: Kern-Schicht `go-test` hängt am Netz, verstößt gegen ADR-0094)

### Affected Files (with changes)
| File | Change Type | Description |
|------|-------------|-------------|
| `internal/resolver/komoot.go` | MODIFY | API-URL als Paket-Variable (`komootAPIURLFormat`), Verhalten unverändert, kein Env/Flag-Schalter |
| `internal/resolver/export_test.go` | MODIFY | Test-Hebel `KomootAPIAuf(t, url)` (nur Testbinary, ADR-0114) |
| `internal/resolver/testdata/komoot_highlight_126361.json` | CREATE | Komoot-Antwort im Originalformat (HAL-JSON), einmalig live aufgezeichnet, minimiert, Herkunft/Datum im Test vermerkt |
| `internal/resolver/resolver_test.go` | MODIFY | Komoot-, Google-Mobil-, Google-Desktop-Test offline gegen httptest; Koordinaten-Tests mit `OhneNachschlagDienste` |
| `internal/resolver/resolver_live_test.go` | CREATE | `//go:build integration`: Live-Varianten Komoot, Google-Mobil, Google-Desktop (Anbieter-Vertrag) |
| `internal/resolver/netzsperre_test.go` | CREATE | `//go:build !integration`, `package resolver`: `TestMain` mit Netzsperre (s. u.) |
| `internal/handler/location_resolve_test.go` | MODIFY | `TestResolveHandlerKomootHighlight` entfernt |
| `internal/handler/location_resolve_live_test.go` | CREATE | `//go:build integration`: Handler-Komoot-Test live |
| `internal/handler/netzsperre_test.go` | CREATE (bedingt) | `TestMain` mit loopback-only-DefaultTransport, nur wenn Probelauf des Handler-Pakets sauber; sonst Folge-Issue |

### Scope Assessment
- Files: 6–9
- Estimated LoC: ca. +300/−40 (überwiegend Tests; Produktionscode ca. +5/−2)
- Risk Level: LOW (Produktion: nur Konstante → Paket-Variable; Rest ist Testcode)

### Technical Approach
1. **Komoot offline:** Paket-Variable für die API-URL, ersetzbar nur über export_test.go. Fixture-Server (Muster #3106) prüft Pfad `/api/v007/highlights/126361` und `Accept: application/hal+json`, meldet jede unerwartete Anfrage per `t.Errorf`. Zusicherungen gegen die konkreten Werte der Fixture (Name, Koordinaten, Höhe), nicht nur Bereiche.
2. **Google Mobil offline:** localhost-Link nach Vorbild `link_abruf_abschottung_test.go` (`ErlaubeTestHosts("localhost")`, `ErlaubeHTTPSchema`, `ErlaubeLoopbackVerbindung`); Dispatch braucht `.google.` und `maps` im Input (z. B. als Pfadsegment). Link-Server antwortet wie Google ohne Koordinaten; Nominatim-Fixture-Server (via `nominatimSearchURL`-Hebel) liefert Wangels im Originalformat (lat/lon als Strings) und **prüft am Server**, dass `q=Freden op'n Kliff, 23758 Wangels` aus der Original-URL ankommt — sonst prüft der Test sich selbst.
3. **Google Desktop offline:** localhost-Link mit `/maps/place/Innsbruck/@47.2692,11.4041,13z`; Server antwortet 200. Der echte Redirect-Vertrag bleibt in der Live-Variante.
4. **Handler-Komoot-Test → Live-Datei.** Kein Injektionspunkt im Handler (paketglobal `resolver.Resolve`), `http.DefaultTransport` wird von egress/coreauth gewrappt; Umlenk-RoundTripper wäre heikel. Handler-Erfolgspfad bleibt durch `TestResolveHandlerDecimalCoordinates`, Fehlerabbildung durch `TestResolveHandlerKomootTourUnsupported` abgedeckt; Komoot-Erfolgspfad offline im Resolver-Paket.
5. **Netzsperre als dauerhafte Ratsche (Gegenprobe).** Proxy-Sperre greift nicht (Link-Client ohne Proxy), `unshare`/firejail/sudo nicht verfügbar, der egress-Wächter erlaubt komoot/google/nominatim/open-elevation als TestAccess (ungeeignet). Daher `TestMain` im Resolver-Paket (`package resolver`, gilt für das ganze Testbinary inkl. `resolver_test`):
   - `dialIPAllowed = func(netip.Addr) bool { return false }` (**deny-all**, nicht loopback-only — sonst werden die Abschottungstests rot, die ohne `ErlaubeLoopbackVerbindung` „kein Abruf" erwarten; `ErlaubeLoopbackVerbindung` bildet `loopback || orig` und bleibt korrekt),
   - `http.DefaultTransport` mit RoundTripper umhüllen, der nur `127.0.0.1`/`::1`/`localhost` durchlässt (trifft Komoot, Nominatim, Elevation).
   - Datei mit `//go:build !integration`, damit Live-Tests nicht blockiert werden.
   - **Gegenprobe Pflicht:** Netzsperre zuerst auf dem unveränderten Teststand laufen lassen → die vier Tests müssen rot werden (belegt, dass die Sperre greift); danach mit Fix grün.
6. **Handler-Paket:** Probelauf mit loopback-only-DefaultTransport-TestMain. Sauber → aufnehmen. Rot an fremden Tests → diese sind eigene Netzabhängigkeiten: Folge-Issue (Refs #1196) anlegen, Handler-TestMain dorthin; #3115 nicht daran hängen.

### Dependencies
- `resolver.Resolve` einziger Go-Aufrufer: `ResolveLocationHandler` (`POST /api/locations/resolve`).
- Testhebel in export_test.go: `ErlaubeTestHosts`, `ErlaubeHTTPSchema`, `ErlaubeLoopbackVerbindung`, `OhneNachschlagDienste`.
- egress/coreauth-Tests sichern/restaurieren `http.DefaultTransport` selbst (order_test.go, transport_test.go) — verträglich mit einem TestMain-Wrapper als Boden.
- CI: `go test ./...` ohne Tags bleibt unverändert; Live-Tests via `go test -tags integration ./internal/resolver/ ./internal/handler/`.

### Open Questions
- keine Produktfrage. Technische Restunsicherheit (Handler-Probelauf) ist im Ansatz mit Entscheidungsregel abgedeckt.

## TDD RED (2026-11-19)

- **Einzige Produktionsänderung für GREEN:** in `internal/resolver/komoot.go` `var komootAPIURLFormat = "https://www.komoot.com/api/v007/highlights/%s"` und `apiURL := fmt.Sprintf(komootAPIURLFormat, id)`. Testhebel `KomootAPIAuf`, `KomootAPIStandard`, `NominatimAuf` stehen bereits in `export_test.go`. Probelauf per `go test -overlay` mit genau dieser Änderung: Resolver-Paket grün, keine Netzversuche; Live-Tests mit `-tags integration` grün.
- **Netzsperre Resolver:** `internal/resolver/netzsperre_test.go` (`!integration`): deny-all-Dial + loopback-only-DefaultTransport; abgelehnte Versuche werden vermerkt und machen den Lauf am Ende rot (auch still geschluckte Höhen-Nachschläge). Koordinaten-Tests nutzen `OhneNachschlagDienste`.
- **AC-9 Handler-Probelauf:** sauber → Sperre aufgenommen (`internal/handler/netzsperre_test.go` ohne Tag mit Helfer `erwarteAbgelehntenHoehenNachschlag`, `netzsperre_main_test.go` mit `TestMain`, `!integration`). Alter Stand: nur Handler-Komoot + 3 Höhen-Abrufe; Anfragen ohne Host (leere Core-Adresse in sms_verify-Tests) sind kein Netzabruf und werden durchgereicht. Neuer Stand: Handler-Paket grün (`probelauf-handler-neuer-teststand.txt`). Kein Folge-Issue nötig.
- Live-Varianten: `internal/resolver/resolver_live_test.go`, `internal/handler/location_resolve_live_test.go` (`integration`).
