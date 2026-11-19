# Adversary Dialog — feat-3158-hoehe-fixture
Spec: docs/specs/modules/handler_hoehen_fixture.md
Datum: 2026-11-19 11:20

## Checkliste
- [x] **Input:** Handler-Aufruf mit Koordinaten (Dezimal, DMS, per Content-Type-Variante) ohne Höhenangabe, bei aktivem `hoehenDienstAuf(t, 1234.6)`.
- [x] **Output:** Antwort-JSON enthält `elevation_m: 1235`; der Fixture-Server hat die erwarteten `locations` empfangen.
- [x] **Side effects:** Während des Tests liegt ein Umleiter über `http.DefaultTransport`; nach dem Test ist exakt der vorige Transport (die Sperre) wiederhergestellt.
- [x] **AC-1:** Given der Helfer `hoehenDienstAuf` ist mit Höhe 1234.6 aktiv / When der Orts-Auflöser mit Dezimal-Koordinaten (47.0789, 11.6856) ohne Höhe aufgerufen wird / Then enthält die Antwort `elevation_m` = 1235 (Rundung des Fixture-Werts) und der Fixture-Server hat genau die Abfrage `locations=47.078900,11.685600` erhalten.
- [x] **AC-2:** Given der Helfer ist mit Höhe 1234.6 aktiv / When der Orts-Auflöser mit DMS-Koordinaten bzw. in der Content-Type-Variante aufgerufen wird / Then enthält die Antwort jeweils `elevation_m` = 1235 und der Fixture-Server hat die in Dezimalgrad umgerechneten Koordinaten empfangen.
- [x] **AC-3:** Given der Helfer ist aktiv / When ein Test über `http.DefaultTransport` einen Fremd-Host (nicht `api.open-elevation.com`) abruft / Then bleibt dieser Abruf von der Netzsperre abgelehnt und erreicht den Fixture-Server nicht (Umleitung gilt nur für den exakten Host).
- [x] **AC-4:** Given ein Test hat `hoehenDienstAuf` verwendet und ist beendet / When dessen Cleanup gelaufen ist / Then ist `http.DefaultTransport` wieder exakt der vorige Transport und die Netzsperre wirkt erneut (Open-Elevation-Abruf wird abgelehnt, `pruefeNetzsperreInstalliert` bleibt grün).
- [x] **AC-5:** Given Duldungs-Helfer `erwarteAbgelehntenHoehenNachschlag` und Konstante `hoehenNachschlagPraefix` sind entfernt / When irgendein Handler-Test ohne Fixture einen echten Open-Elevation-Abruf auslöst / Then wird der Abruf von der Sperre abgelehnt und der Testlauf wird über `TestMain` rot, statt stillschweigend geduldet zu werden.
- [x] **AC-6:** Given die Doku `docs/reference/gates_und_ratschen.md` beschreibt die Netzsperre der Go-Kern-Tests / When ein Leser den Abschnitt zum Handler-Paket liest / Then steht dort, dass der Höhen-Nachschlag gegen einen lokalen Fixture-Server läuft und keine Duldung mehr besteht.

## Dialog

### Runde 1
**Adversary:** Tests gelaufen (Output: docs/artifacts/feat-3158-hoehe-fixture/adversary-test-output.txt): gezielte Regex 10 PASS, ganzes Paket `ok` (158 s), `go vet -tags integration` ok, pytest Doku-Test ok. Code gelesen:
Code reference: internal/handler/hoehen_fixture_test.go:37 (Host-Vergleich exakt per `Hostname() !=`), :52-76 (Server, Merken, Cleanup stellt `vorher` her).
Code reference: internal/handler/location_resolve_test.go:51 (gemeinsamer Pruefer: elevation_m == 1235, genau eine locations-Abfrage), :12/:156/:180 (Helferaufruf in den drei Tests).
Code reference: internal/handler/hoehen_fixture_wirkung_test.go:56 (AC-3 inkl. Lookalike-Host `api.open-elevation.com.netzsperre-probe.invalid`), :80 (AC-4/AC-5 Cleanup + Register-Eintrag, gezielt entfernt).
Code reference: internal/handler/netzsperre_test.go:46 (Duldungs-Helfer und Praefix-Konstante entfernt, Import `testing` mit entfernt; Diff -31 Zeilen).
Code reference: docs/reference/gates_und_ratschen.md:218 (Fixture-Verweis, "keine Ausnahme mehr"); tests/test_netzsperre_doku_hoehen_fixture.py:20 (doc-compliance-test, prueft Verweis und Abwesenheit des Duldungs-Satzes).
Befund-Skepsis: Spec-Erwartung `Decimal` = `47.078900,11.685600` stimmt mit Testdaten ueberein (Eingabe 47.0789, 11.6856); DMS-Wert 47.078889,11.685611 korrekt umgerechnet. Keine Produktionsdatei veraendert (git diff nur Doku + Testdatei).
**Implementierer:** (nicht beteiligt, Kontext-Isolation)

### Runde 2 (Mutations-Gegenprobe, je per String-Ersetzung, Sicherungskopie im Scratchpad, danach cmp identisch)
**Adversary:**
- (a) Helferaufruf je in Decimal / DMS / ContentType entfernt: alle drei GEFANGEN (Test rot + TestMain meldet Fremdabruf).
- (b) Fixture-Hoehe 1234.4 (DMS): gefangen; Fixture liefert hoehe+1: gefangen (4 Tests); Pruefer 1235->1234: gefangen.
- (c) Fixture liest falschen Query-Key / merkt nichts: gefangen. Produktion `elevation.go` lat/lon vertauscht (dort, wo es wirkt): gefangen von allen 3 Handlertests. Pruefer-Koordinatenvergleich auf `false`: nicht gefangen (erwartet, Pruefer prueft sich nicht selbst; durch Produktionsmutation oben abgedeckt, kein Finding).
- (d) Cleanup stellt nichts her: gefangen (u.a. TestNetzsperre_*); Cleanup setzt Basistransport statt `vorher`: gefangen (FremderHost-Test).
- (e) Host-Vergleich: Contains gefangen, HasPrefix gefangen, alles umleiten gefangen, Scheme-Umschreibung entfernt gefangen. **HasSuffix NICHT gefangen** (F001).
- (f) Duldung in der Sperre wieder eingebaut: gefangen. Duldungs-Filter im TestMain-Auswerteblock (netzsperre_main_test.go): **NICHT gefangen** (F002).
**Implementierer:** (nicht beteiligt)

Finding F001: Severity LOW, Category: edge_case, Code reference: internal/handler/hoehen_fixture_test.go:37. Der Host-Vergleich waere mit `HasSuffix` aufgeweicht (z.B. `evil.api.open-elevation.com` wuerde umgeleitet) und kein Test faengt es; AC-3 testet nur Prefix-Lookalike (`api.open-elevation.com.<fremd>`) und `*.invalid`. Spec-Anforderung AC-3 ("exakter Host"). Remediation: im Selbsttest AC-3 zusaetzlich `http://vorsatz.api.open-elevation.com/...` abrufen.

Finding F002: Severity LOW, Category: anti_pattern, Code reference: internal/handler/netzsperre_main_test.go:21. Eine erneute Duldung im TestMain-Auswerteblock (Filter auf open-elevation) bleibt gruen, weil kein Test das Lauf-Ende-Verhalten pruefen kann (in-process unbeobachtbar). AC-5 "TestMain wird rot" ist damit nur indirekt bewiesen (Register-Eintrag im Selbsttest + Mutation f in der Sperre). Remediation: optional Unterprozess-Test oder Doku-Hinweis; kein Blocker.

## Herkunft der Vorbedingungen

Kein Sprachprofil konfiguriert (`precondition_origins.default_lang`); keine Vorbedingungen aus Fremdquellen. Testdaten stammen aus der Spec (Hoehe 1234.6, Koordinaten 47.0789/11.6856).

## Verdict

VERDICT: VERIFIED

VERIFIED mit zwei LOW-Anmerkungen (F001, F002), keine CRITICAL/HIGH/MEDIUM. Alle Mutationen zurueckgespielt (cmp identisch, git diff --stat unveraendert: gates_und_ratschen.md +1/-1, netzsperre_test.go -31).

## Geprüfte Dateien

- sha256:427c75d38ffe0d9965d819a106a43df9e9e75e51cd48768984eb0b663d58412f  docs/reference/gates_und_ratschen.md
- sha256:f3d0bb394ebf264e248bb917ee2e44fe858a708538bc64f58a54fe105d201ca6  internal/handler/hoehen_fixture_test.go
- sha256:f03a0a0aad85006540a789ff24a62e2eef5f2137d353826f3e11bcc99c94fe43  internal/handler/hoehen_fixture_wirkung_test.go
- sha256:0486adce03acab16d91a0ef8b2b9e8c60e3103da680ce70f7480946258a3edc9  internal/handler/location_resolve_test.go
- sha256:88bee57d9747c029437318ca8ca6102f7518462b15e0d1c83fc2ed38b3e1c2d8  internal/handler/netzsperre_test.go

## Prüfbasis

- base: 0ceaa14de47c092b456051e1d31071d0c592561e
- blob:656c8647ad1c2b1a668b1657381fe20b12deef29  docs/reference/gates_und_ratschen.md
- blob:637c356e8b64f0b7b3d342d4aea1d99d0fde5fa5  internal/handler/hoehen_fixture_test.go
- blob:7b01f46c432fc0f04d94020d023b0c6c6ed7c350  internal/handler/hoehen_fixture_wirkung_test.go
- blob:e6917ce25b43e0058a680a0501ea6fc67e63d6ad  internal/handler/location_resolve_test.go
- blob:1d9792f58d6ee8acb819e377a565f52c442926a4  internal/handler/netzsperre_test.go
