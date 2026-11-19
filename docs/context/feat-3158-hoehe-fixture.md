# Context: feat-3158-hoehe-fixture

## Request Summary
Issue #3158 (Folgebefund aus #3115, Refs #1196, ADR-0094/ADR-0114): Drei Koordinaten-Tests im
Go-Handler-Paket lösen den Höhen-Nachschlag (Open-Elevation) aus; die Netzsperre lehnt ihn ab, der
Helfer `erwarteAbgelehntenHoehenNachschlag` duldet das. Folge: Die Höhe wird auf Handler-Ebene nie
geprüft. Ziel: Nachschlag gegen lokalen Fixture-Server, Höhe prüfen, Duldung entfernen — ohne
Laufzeitschalter in Produktion (ADR-0114).

## Related Files
| File | Relevance |
|------|-----------|
| `internal/handler/location_resolve_test.go` | 3 Tests (`Decimal`, `DMS`, `ContentType`) rufen `erwarteAbgelehntenHoehenNachschlag`; prüfen `elevation_m` nicht |
| `internal/handler/netzsperre_test.go` | Netzsperre-Transport + Duldungs-Helfer `erwarteAbgelehntenHoehenNachschlag` + Konstante `hoehenNachschlagPraefix` (zu entfernen) |
| `internal/handler/netzsperre_main_test.go` | `TestMain` installiert Sperre über `http.DefaultTransport` (nur `!integration`), macht Lauf rot bei jedem Fremdabruf |
| `internal/handler/netzsperre_wirkung_test.go` | prüft, dass `http.DefaultTransport` die Sperre ist (darf nach Cleanup nicht kippen) |
| `internal/handler/location_resolve.go` | `ResolveLocationHandler()` ruft `resolver.Resolve` direkt (kein Injektionspunkt) |
| `internal/resolver/elevation.go` | `lookupElevation`: `&http.Client{}` ohne eigenen Transport ⇒ nutzt `http.DefaultTransport`; GET `elevationLookupURL?locations=%f,%f`, Antwort `{"results":[{"elevation":x}]}`, gerundet `int(x+0.5)`, Soft-Fail |
| `internal/resolver/resolver.go:74-84` | `finalize` ruft `lookupElevation` nur, wenn Höhe fehlt; JSON-Feld `elevation_m` |
| `internal/resolver/export_test.go` | `OhneNachschlagDienste` (nur im Resolver-Testbinary sichtbar) |
| `docs/adr/0114-…md` | Testöffnungen nur über Testdateien, kein Env-/Laufzeitschalter |

## Existing Patterns
- Resolver-Paket: Testhebel über `export_test.go` (Paketvariable tauschen, Cleanup stellt zurück).
- Handler-Paket: Netzsperre als `RoundTripper` über `http.DefaultTransport`; Kommentar sieht vor,
  dass Tests sich mit eigenem Transport „darüberlegen“ und beim Aufräumen zurückstellen.
- Fixture-Server per `httptest.NewServer` (Loopback, von der Sperre durchgelassen).

## Analyse / Lösungsansatz (Summe 2: Context + Analyse in einem Durchgang)
Optionen:
1. **Test-Transport im Handler-Paket (empfohlen):** Neuer Testhelfer (z. B. `hoehenDienstAuf(t)`),
   der einen lokalen Open-Elevation-Nachbau startet und über `http.DefaultTransport` einen
   umleitenden `RoundTripper` legt: Anfragen an Host `api.open-elevation.com` gehen an den
   Loopback-Server (Schema/Host umgeschrieben, Pfad+Query bleiben), alles andere an den vorigen
   Transport (die Sperre). Cleanup stellt den vorigen Transport wieder her. Null Produktionsänderung,
   kein Laufzeitschalter, wirkt auch im `integration`-Build (keine Abhängigkeit von `TestMain`).
   Der Fixture-Server merkt sich die angefragten `locations` ⇒ Test prüft, dass die Koordinaten
   ankommen, und dass `elevation_m` = gerundeter Fixture-Wert im Handler-JSON steht.
2. Handler-Injektion (`ResolveLocationHandlerMit(fn)`): Produktionsänderung, und der Test liefe
   dann nicht mehr durch den echten Resolver/Höhen-Nachschlag ⇒ verfehlt das Ziel. Verworfen.
3. Exportierter Setter im Resolver: wäre ein Laufzeitschalter in Produktion ⇒ ADR-0114-Verstoß. Verworfen.

Nach Umstellung: `erwarteAbgelehntenHoehenNachschlag` und `hoehenNachschlagPraefix` entfallen; jeder
verbleibende echte Open-Elevation-Abruf macht den Kern-Lauf über `TestMain` rot.

## Dependencies
- Upstream: `resolver.Resolve` → `finalize` → `lookupElevation` → `http.DefaultTransport`.
- Downstream: nur Testcode; Router/Produktion unberührt.

## Existing Specs
- Keine Modul-Spec für die Netzsperre im Handler; Referenz `docs/reference/gates_und_ratschen.md`
  (Abschnitt Netzsperre Go-Kern-Tests aus #3115) — Duldungs-Erwähnung dort ggf. nachziehen.

## Risks & Considerations
- `http.DefaultTransport` ist global: Helfer nicht in `t.Parallel`-Tests verwenden (die drei Tests
  sind sequenziell; parallele Tests laufen erst nach den sequenziellen Top-Level-Tests).
- Cleanup muss exakt den vorigen Transport zurückstellen, sonst kippt `netzsperre_wirkung_test`.
- Umleitung nur für den exakten Host, sonst würde sie andere Abrufe an der Sperre vorbeischleusen.
- Rundung: Fixture-Wert mit Nachkomma wählen (z. B. 1234.6 → 1235), damit auch die Rundung geprüft ist.
- Weitere Handler-Tests (`fach_fehler_zweisprachig_test.go`) rufen den Endpunkt nur ohne Koordinaten auf ⇒ kein Nachschlag, unbetroffen.

## Analysis

### Type
Feature (Test-Infrastruktur, Folgebefund #3115; keine Produktionsänderung)

### Verifikation der Annahmen (2026-11-19, am Code geprüft)
- `lookupElevation` baut `&http.Client{Timeout: 8s}` ohne Transport ⇒ nutzt `http.DefaultTransport` zur Aufrufzeit ⇒ eine Umleitung über `DefaultTransport` greift.
- URL-Form: `https://api.open-elevation.com/api/v1/lookup?locations=%f,%f` (6 Nachkommastellen); Antwort `{"results":[{"elevation":x}]}`, Rundung `int(x+0.5)`.
- `location_resolve_test.go` und `netzsperre_test.go` tragen **kein** Build-Tag ⇒ der neue Helfer muss ebenfalls ungetaggt sein und auch im `integration`-Build ohne `TestMain`-Sperre funktionieren (er wickelt dann den echten Transport ein; die Umleitung verhindert auch dort den Live-Abruf).
- Doku `docs/reference/gates_und_ratschen.md:218` nennt die Duldung („Ausnahme im Handler-Paket … Folgebefund #3158“) ⇒ Satz ersetzen durch Verweis auf den Fixture-Helfer.

### Affected Files (with changes)
| File | Change Type | Description |
|------|-------------|-------------|
| `internal/handler/hoehen_fixture_test.go` | CREATE | Helfer `hoehenDienstAuf(t, hoehe float64) *hoehenFixture`: `httptest.NewServer` als Open-Elevation-Nachbau (merkt `locations`-Query, liefert `{"results":[{"elevation":hoehe}]}`), legt umleitenden `RoundTripper` über `http.DefaultTransport` (nur exakter Host `api.open-elevation.com` → Loopback, Pfad+Query bleiben; Rest an vorigen Transport), Cleanup stellt exakt den vorigen Transport her und schließt den Server |
| `internal/handler/location_resolve_test.go` | MODIFY | 3 Tests (`Decimal`, `DMS`, `ContentType`): `erwarteAbgelehntenHoehenNachschlag` → `hoehenDienstAuf`; neu prüfen: `elevation_m` == gerundeter Fixture-Wert (z. B. 1234.6 → 1235) und angefragte Koordinaten stimmen (Decimal: `47.078900,11.685600`) |
| `internal/handler/netzsperre_test.go` | MODIFY | `erwarteAbgelehntenHoehenNachschlag` + `hoehenNachschlagPraefix` entfernen; Paketkommentar unverändert gültig |
| `docs/reference/gates_und_ratschen.md` | MODIFY | Duldungs-Satz ersetzen (Höhen-Nachschlag läuft gegen lokalen Fixture-Server, keine Ausnahme mehr) |

### Scope Assessment
- Files: 4 (1 neu, 3 geändert), nur Testcode + Doku
- Estimated LoC: +~70 / -~30
- Risk Level: LOW (Produktion unberührt; einziges Risiko: globaler `DefaultTransport` → Cleanup-Reihenfolge, kein `t.Parallel`)

### Technical Approach
Option 1 aus obiger Analyse (Test-Transport im Handler-Paket). Optionen 2 (Handler-Injektion, Produktionsänderung und verfehlt echten Pfad) und 3 (exportierter Setter = Laufzeitschalter, ADR-0114-Verstoß) verworfen.
Prüfbarkeit (für TDD/Adversary):
- Ohne Helfer (Mutation: Aufruf entfernt) ⇒ Sperre lehnt ab, `elevation_m` fehlt ⇒ Test rot; zusätzlich `TestMain` rot (Fremdabruf vermerkt, keine Duldung mehr).
- Mutation Rundung im Resolver (`+0.5` weg) ⇒ 1234 statt 1235 ⇒ rot.
- Mutation Koordinaten-Reihenfolge in der URL ⇒ Fixture-Prüfung der `locations` ⇒ rot.
- Cleanup-Fehler (Transport nicht zurückgestellt) ⇒ `netzsperre_wirkung_test` (`pruefeNetzsperreInstalliert`) rot.
- Umleitung zu breit (alle Hosts) ⇒ `TestNetzsperre_StandardClientBlocktFremdenHost` liefe nur dann falsch, wenn der Helfer aktiv bliebe; Host-Exaktheit wird im Helfer-Selbsttest geprüft (fremder Host während aktiver Umleitung weiter abgelehnt).

### Dependencies
`resolver.Resolve` → `finalize` (nur wenn Höhe fehlt) → `lookupElevation` → `http.DefaultTransport`. Downstream: nur Testcode.

### Open Questions
- keine (reine Test-Infrastruktur, keine Produktentscheidung)

## RED-Stand (Phase 5, 2026-11-19)

Vertrag, den die RED-Tests vom Helfer erwarten (`internal/handler/hoehen_fixture_test.go`, ohne Build-Tag):
- `type hoehenFixture struct{...}` mit Methode `locations() []string` (alle empfangenen `locations`-Query-Werte in Reihenfolge, mutex-geschützt).
- `func hoehenDienstAuf(t *testing.T, hoehe float64) *hoehenFixture`: Umleitung nur für den exakten Host `api.open-elevation.com` (auch `api.open-elevation.com.<x>` bleibt gesperrt); Cleanup stellt exakt den vorigen `http.DefaultTransport` wieder her (Vergleich per `==`).
- Antwort-Body enthält den Wert als JSON-Zahl (`{"results":[{"elevation":1234.6}]}`).
- Selbsttests liegen in `internal/handler/hoehen_fixture_wirkung_test.go` (`//go:build !integration`, weil die Sperre nur dann installiert ist; deshalb nicht in der ungetaggten Helferdatei).
- Doku-Test: `tests/test_netzsperre_doku_hoehen_fixture.py` (AC-6): Absatz nennt `hoehenDienstAuf` und „Fixture", Duldungs-Satz zu #3158 entfernt.
- Danach `erwarteAbgelehntenHoehenNachschlag` und `hoehenNachschlagPraefix` aus `netzsperre_test.go` entfernen.
- Go liegt unter `/usr/local/go/bin` (nicht im PATH der Bash-Sitzung).
