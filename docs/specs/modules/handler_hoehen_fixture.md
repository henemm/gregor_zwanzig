---
entity_id: handler_hoehen_fixture
type: feature
created: 2026-11-19
updated: 2026-11-19
status: draft
version: "1.0"
workflow: feat-3158-hoehe-fixture
tags: [go, testinfrastruktur, netzsperre, hoehe]
---

# Höhen-Nachschlag-Fixture für Go-Handler-Tests

## Approval

- [ ] Approved

## Purpose

Die drei Koordinaten-Tests des Orts-Auflösers (`/api/locations/resolve`) lösen den Höhen-Nachschlag bei Open-Elevation aus. Die Netzsperre lehnt ihn ab, ein Duldungs-Helfer überspielt das, und die Höhe wird auf Handler-Ebene nie geprüft. Ein lokaler Open-Elevation-Nachbau als Testhelfer lässt den echten Nachschlag-Pfad gegen Loopback laufen, prüft die Höhe und macht die Duldung überflüssig (Issue #3158, Folgebefund aus #3115).

## Source

- **File:** `internal/handler/hoehen_fixture_test.go` (neu, ungetaggt)
- **Identifier:** `func hoehenDienstAuf(t *testing.T, hoehe float64) *hoehenFixture`

> Schicht: Go-API (`internal/handler/`), ausschließlich Testcode plus Doku. Keine Produktionsänderung, kein Laufzeitschalter (ADR-0114). Kein Trip/Ortsvergleich-Pendant, keine Nutzerdaten, keine Kanalinhalte betroffen.

## Estimated Scope

- **LoC:** ca. +70 / -30
- **Files:** 4 (1 neu, 3 geändert)
- **Effort:** low

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `resolver.Resolve` → `finalize` → `lookupElevation` (`internal/resolver/elevation.go`, `resolver.go`) | module | Echter Nachschlag-Pfad; nutzt `http.DefaultTransport`, GET `.../api/v1/lookup?locations=%f,%f`, Antwort `{"results":[{"elevation":x}]}`, Rundung `int(x+0.5)` |
| `internal/handler/netzsperre_test.go`, `netzsperre_main_test.go` | test | Netzsperre als Transport über `http.DefaultTransport`; `TestMain` macht Fremdabrufe rot |
| `internal/handler/netzsperre_wirkung_test.go` | test | Prüft, dass `http.DefaultTransport` die Sperre ist (Cleanup darf sie nicht kippen) |
| `internal/handler/location_resolve.go` | module | `ResolveLocationHandler()`, ruft `resolver.Resolve` direkt |
| `net/http/httptest` | stdlib | Loopback-Server als Open-Elevation-Nachbau |
| ADR-0114 | adr | Testöffnungen nur über Testdateien, kein Env-/Laufzeitschalter |
| ADR-0094 | adr | Netzsperre / Testpolitik Kern-Schicht |

## Scope

### Affected Files

| File | Change Type | Description |
|------|-------------|-------------|
| `internal/handler/hoehen_fixture_test.go` | CREATE | Helfer `hoehenDienstAuf` (Open-Elevation-Nachbau + umleitender Transport nur für `api.open-elevation.com`) und Helfer-Selbsttests (AC-3, AC-4, AC-5) |
| `internal/handler/location_resolve_test.go` | MODIFY | `Decimal`, `DMS`, `ContentType`: Duldung durch `hoehenDienstAuf(t, 1234.6)` ersetzt; prüfen `elevation_m == 1235` und angekommene Koordinaten |
| `internal/handler/netzsperre_test.go` | MODIFY | `erwarteAbgelehntenHoehenNachschlag` und `hoehenNachschlagPraefix` entfernt |
| `docs/reference/gates_und_ratschen.md` | MODIFY | Duldungs-Satz (Folgebefund #3158) durch Verweis auf den Fixture-Helfer ersetzt |

### Estimated Changes

- Files: 4
- LoC: +70/-30

## Implementation Details

Neue Datei `internal/handler/hoehen_fixture_test.go` (ohne Build-Tag, damit sie auch im `integration`-Build läuft):

- `hoehenDienstAuf(t, hoehe)` startet einen `httptest.NewServer`, der die Open-Elevation-Antwort `{"results":[{"elevation":hoehe}]}` liefert und die angefragte `locations`-Query in einem Feld des zurückgegebenen `hoehenFixture` merkt.
- Der Helfer merkt sich den vorigen `http.DefaultTransport` und ersetzt ihn durch einen umleitenden `RoundTripper`. Dieser schreibt Anfragen an den **exakten** Host `api.open-elevation.com` auf den Loopback-Server um (Schema und Host; Pfad und Query bleiben). Alle anderen Anfragen gehen unverändert an den vorigen Transport (die Sperre).
- `t.Cleanup` stellt exakt den vorigen Transport wieder her und schließt den Server.
- Nicht in `t.Parallel`-Tests verwenden (globaler Zustand); die drei Tests sind sequenziell.

Änderungen in `location_resolve_test.go` (Tests `Decimal`, `DMS`, `ContentType`): `erwarteAbgelehntenHoehenNachschlag` wird durch `hoehenDienstAuf(t, 1234.6)` ersetzt. Die Tests prüfen zusätzlich `elevation_m == 1235` und die beim Fixture angekommenen Koordinaten (Decimal: `47.078900,11.685600`).

Änderungen in `netzsperre_test.go`: Helfer `erwarteAbgelehntenHoehenNachschlag` und Konstante `hoehenNachschlagPraefix` entfernen. Danach macht jeder echte Open-Elevation-Abruf den Kern-Lauf über `TestMain` rot.

Änderung in `docs/reference/gates_und_ratschen.md` (um Zeile 218): Der Satz zur Duldung im Handler-Paket (Folgebefund #3158) wird ersetzt durch: Der Höhen-Nachschlag der Handler-Tests läuft gegen einen lokalen Fixture-Server (`hoehenDienstAuf`); es gibt keine Ausnahme mehr.

Abweichung bei der Umsetzung (Phase 7 festgehalten): Die Helfer-Selbsttests zu AC-3 bis AC-5 liegen in der eigenen Datei `internal/handler/hoehen_fixture_wirkung_test.go` (Build-Tag `!integration`, wie `netzsperre_wirkung_test.go`), weil sie die Sperre voraussetzen, die nur im Kern-Build installiert ist. Der Doku-Nachweis zu AC-6 liegt in `tests/test_netzsperre_doku_hoehen_fixture.py` (`# doc-compliance-test`). Beide Dateien sind reine Tests; Produktionscode ist unverändert (LoC-Delta 0).

## Expected Behavior

- **Input:** Handler-Aufruf mit Koordinaten (Dezimal, DMS, per Content-Type-Variante) ohne Höhenangabe, bei aktivem `hoehenDienstAuf(t, 1234.6)`.
- **Output:** Antwort-JSON enthält `elevation_m: 1235`; der Fixture-Server hat die erwarteten `locations` empfangen.
- **Side effects:** Während des Tests liegt ein Umleiter über `http.DefaultTransport`; nach dem Test ist exakt der vorige Transport (die Sperre) wiederhergestellt.

## Test Plan

Kern-Schicht (deterministisch, ohne Netz, Go-Tests im Handler-Paket; kein Mock-Theater: der Test läuft durch den echten Handler, Resolver und Höhen-Nachschlag, ersetzt ist nur die Gegenstelle durch einen Loopback-Server):

### Automated Tests (TDD RED)

- [ ] **go test** `./internal/handler -run 'TestResolveHandler(DecimalCoordinates|DMSCoordinates|ContentType)'`: GIVEN `hoehenDienstAuf(t, 1234.6)` / WHEN Endpunkt mit Dezimal-, DMS- und Content-Type-Variante ohne Höhe aufgerufen / THEN `elevation_m == 1235` und Fixture hat die erwarteten `locations` (Decimal `47.078900,11.685600`) empfangen (rot vor der Umsetzung: Helfer fehlt, Höhe leer).
- [ ] **go test** Helfer-Selbsttest Fremd-Host: GIVEN aktive Umleitung / WHEN Abruf eines fremden Hosts über `http.DefaultTransport` / THEN Sperrfehler, Fixture zählt keine Anfrage, Versuch steht im Sperr-Register (danach gezielt entfernt).
- [ ] **go test** Helfer-Selbsttest Cleanup: GIVEN Unter-Test mit `hoehenDienstAuf` beendet / WHEN Open-Elevation-Abruf / THEN `http.DefaultTransport` ist exakt der vorige Transport, Abruf abgelehnt und im Sperr-Register vermerkt (keine Duldung mehr).
- [ ] **go test** gesamtes Paket `./internal/handler` (inkl. `netzsperre_wirkung_test.go`) grün, auch mit `-tags integration` kompilierbar.
- [ ] Doku-Abschnitt: `# doc-compliance-test` für den Satz in `docs/reference/gates_und_ratschen.md`.

## Definition of Done

- [ ] AC-1 und AC-2 durch die drei Handler-Tests belegt (Höhe 1235, Koordinaten), vor der Umsetzung rot nachgewiesen
- [ ] AC-3 bis AC-5 durch die Helfer-Selbsttests belegt; Mutations-Gegenprobe (Helfer-Aufruf entfernt, Rundung verändert, Koordinaten vertauscht, Cleanup fehlt) jeweils rot
- [ ] Duldungs-Helfer und Konstante entfernt; Doku-Satz nachgezogen (AC-6)
- [ ] Keine Produktionsänderung, kein Laufzeitschalter (ADR-0114)
- [ ] Adversary-Verdict VERIFIED, alle 6 CI-Checks grün, ausgeliefert, Selftest grün

## Acceptance Criteria

- **AC-1:** Given der Helfer `hoehenDienstAuf` ist mit Höhe 1234.6 aktiv / When der Orts-Auflöser mit Dezimal-Koordinaten (47.0789, 11.6856) ohne Höhe aufgerufen wird / Then enthält die Antwort `elevation_m` = 1235 (Rundung des Fixture-Werts) und der Fixture-Server hat genau die Abfrage `locations=47.078900,11.685600` erhalten.
  - Test: `Decimal`-Handlertest ruft den Endpunkt, prüft gerundete Höhe und die vom Fixture gemerkten Koordinaten.

- **AC-2:** Given der Helfer ist mit Höhe 1234.6 aktiv / When der Orts-Auflöser mit DMS-Koordinaten bzw. in der Content-Type-Variante aufgerufen wird / Then enthält die Antwort jeweils `elevation_m` = 1235 und der Fixture-Server hat die in Dezimalgrad umgerechneten Koordinaten empfangen.
  - Test: `DMS`- und `ContentType`-Handlertests prüfen Höhe und angekommene Koordinaten.

- **AC-3:** Given der Helfer ist aktiv / When ein Test über `http.DefaultTransport` einen Fremd-Host (nicht `api.open-elevation.com`) abruft / Then bleibt dieser Abruf von der Netzsperre abgelehnt und erreicht den Fixture-Server nicht (Umleitung gilt nur für den exakten Host).
  - Test: Helfer-Selbsttest mit aktiver Umleitung: Abruf eines fremden Hosts schlägt mit Sperrfehler fehl, Fixture zählt keine Anfrage, und der Versuch steht im Sperr-Register. Der Selbsttest entfernt danach genau diesen einen, von ihm selbst ausgelösten Eintrag (geprüft, nicht pauschal), damit `TestMain` nicht rot wird.

- **AC-4:** Given ein Test hat `hoehenDienstAuf` verwendet und ist beendet / When dessen Cleanup gelaufen ist / Then ist `http.DefaultTransport` wieder exakt der vorige Transport und die Netzsperre wirkt erneut (Open-Elevation-Abruf wird abgelehnt, `pruefeNetzsperreInstalliert` bleibt grün).
  - Test: Helfer-Selbsttest in Unter-Test mit Cleanup, danach Vergleich des Transports mit dem Stand vorher und Abruf von `api.open-elevation.com`, der abgelehnt wird; Register-Eintrag wie bei AC-3 geprüft und gezielt entfernt.

- **AC-5:** Given Duldungs-Helfer `erwarteAbgelehntenHoehenNachschlag` und Konstante `hoehenNachschlagPraefix` sind entfernt / When irgendein Handler-Test ohne Fixture einen echten Open-Elevation-Abruf auslöst / Then wird der Abruf von der Sperre abgelehnt und der Testlauf wird über `TestMain` rot, statt stillschweigend geduldet zu werden.
  - Test: Verhaltensnachweis im Selbsttest aus AC-4: Ein Open-Elevation-Abruf ohne aktive Umleitung landet im Sperr-Register (nicht mehr herausgefiltert), das `TestMain` am Laufende rot macht. Zusätzlich Mutations-Gegenprobe: Helfer-Aufruf in einem der drei Handler-Tests entfernt ⇒ Test rot (Höhe fehlt) und `TestMain` rot.

- **AC-6:** Given die Doku `docs/reference/gates_und_ratschen.md` beschreibt die Netzsperre der Go-Kern-Tests / When ein Leser den Abschnitt zum Handler-Paket liest / Then steht dort, dass der Höhen-Nachschlag gegen einen lokalen Fixture-Server läuft und keine Duldung mehr besteht.
  - Test: # doc-compliance-test: Abschnitt enthält den Fixture-Verweis und nicht mehr den Duldungs-Satz zu #3158.

## Known Limitations

- Der Helfer verändert den globalen `http.DefaultTransport`; er darf nicht in `t.Parallel`-Tests genutzt werden.
- Die Umleitung gilt nur im Handler-Paket; das Resolver-Paket nutzt weiter `export_test.go` (`OhneNachschlagDienste`).

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** keine neue (folgt ADR-0114 und ADR-0094)
- **Rationale:** Reiner Testhelfer ohne Produktionsänderung; verworfen wurden Handler-Injektion (verfehlt den echten Pfad) und ein exportierter Resolver-Setter (Laufzeitschalter, ADR-0114-Verstoß).

## Changelog

- 2026-11-19: Initial spec created (Issue #3158)
- 2026-11-19: Implementation Details um die zwei zusätzlichen Testdateien ergänzt (Validierung)
