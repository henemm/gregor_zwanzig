---
entity_id: fix_1435_e5_alert_mapping_unify
type: refactor
created: 2026-08-05
updated: 2026-08-05
status: draft
version: "1.0"
tags: [metric-catalog, alerts, cross-stack, codegen, register, drift-prevention]
workflow: fix-1435-e5-alert-mapping
---

# Fix #1435 Etappe E5 — Katalog-ID→AlertMetric-Zuordnung wird eine einzige Quelle

## Approval

- [x] Approved (PO Henning, 2026-08-05)

## Purpose

Die Zuordnung „Katalog-Metrik-ID → alarmfähige AlertMetric(s)" (z. B.
`"gust"` → `wind_gust`, `"temperature"` → `temperature_min`+`temperature_max`)
existiert heute **dreifach handgepflegt**: als Go-Literal
(`catalogIDToAlertMetrics` in `internal/model/trip.go`), als Python-Master-Dict
(`_ALERT_METRIC_TO_CATALOG_ID`/`catalog_id_to_alert_metrics()` in
`src/services/weather_change_detection.py`) und als TS-Literal
(`ROUTE_CORRIDOR_CATALOG_IDS` in `corridorEditorState.ts`). Nur Python↔TS ist
gegeneinander automatisiert geprüft (`tests/tdd/test_alert_metric_mapping_parity.py`,
Issue #1387); die Go-Kopie ist unbewacht, und ihr eigener Kommentar behauptet
fälschlich, sie sei durch diesen Test abgedeckt. E5 löst die letzte
handgepflegte Dublette auf: Python bleibt die einzige Quelle, ein
Erzeuger-Skript generiert daraus eingecheckte JSON-Artefakte, Go bindet sein
Artefakt beim Kompilieren per `go:embed` fest ein, und ein Frische-Ratchet-Test
lässt keine Abweichung mehr unbemerkt durch. Reine Drift-Prävention — kein
heute bekannter Nutzerfehler (anders als der Vorläufer-Vorfall #1387).

## Source

> **Schicht-Hinweis:** betrifft alle drei Schichten — Python-Core (Quelle +
> neues Erzeuger-Skript), Go-API (Embed-Konsument, synchroner
> Persistenzpfad), Frontend (SvelteKit-Konsument, Wertebereiche-Editor).

- **File:** `src/services/weather_change_detection.py`
- **Identifier:** `_ALERT_METRIC_TO_CATALOG_ID` (Zeile 82), `catalog_id_to_alert_metrics()` (Zeile 121)
- **File:** `internal/model/trip.go`
- **Identifier:** `catalogIDToAlertMetrics` (Zeile 226-240), `ActiveAlertableMetricIDs()` (Zeile 242-288)
- **File:** `frontend/src/lib/components/shared/corridor-editor/corridorEditorState.ts`
- **Identifier:** `ROUTE_CORRIDOR_CATALOG_IDS` (Zeile 120-126)
- **File (neu):** `scripts/generate_alert_metric_mapping.py`
- **File (neu, generiert):** `internal/model/alert_metric_mapping.generated.json`,
  `frontend/src/lib/generated/alertMetricMapping.generated.json`

## Estimated Scope

- **LoC:** Produktivcode ~150-190 Zeilen (Erzeuger-Skript ~70-90, `trip.go`-Diff
  ~30-40, `corridorEditorState.ts`-Diff ~30-40, Kommentar-Korrektur in
  `weather_change_detection.py` ~10-15) — bleibt **unter** dem 250-Zeilen-Deckel,
  keine Override-Anfrage nötig. Die beiden generierten JSON-Dateien selbst
  zählen laut CLAUDE.md nicht auf den Deckel (generierte Dateien). Testcode
  ~150-220 Zeilen (erweiterter Ratchet-Test + ein neuer, kleiner Go-Test für
  den Fail-Loud-Pfad bei defektem Embed). Doku (ADR-Vorschlag + Index-Zeile)
  ~50-70 Zeilen, zählt laut CLAUDE.md ebenfalls nicht auf den Deckel.
- **Files:** 3 Produktivdateien geändert (`trip.go`, `corridorEditorState.ts`,
  `weather_change_detection.py`), 1 neu (`scripts/generate_alert_metric_mapping.py`);
  2 generierte JSON-Dateien neu (checked in); 1 Testdatei erweitert
  (`test_alert_metric_mapping_parity.py`), 1 neue kleine Go-Testdatei; 1 neue
  ADR-Datei + 1 Index-Zeile.
- **Effort:** medium — die Datenzuordnung selbst ändert sich nicht (Byte-für-
  Byte-Verhaltensneutralität ist Pflicht-AC), der Aufwand steckt im neuen,
  im Projekt bisher unüblichen Baustein (generiertes, eingebettetes Artefakt)
  und im Nachweis, dass er wirklich etwas fängt.

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `src/services/weather_change_detection.py::catalog_id_to_alert_metrics()` | READ (unverändert) | bleibt die alleinige Quelle; das Erzeuger-Skript liest ihre Ausgabe |
| `scripts/generate_alert_metric_mapping.py` | NEU | erzeugt beide generierten JSON-Dateien aus der Python-Quelle, bietet `--check` für den Ratchet-Test |
| `internal/model/alert_metric_mapping.generated.json` | NEU (generiert, eingecheckt) | Go-`go:embed`-Ziel |
| `frontend/src/lib/generated/alertMetricMapping.generated.json` | NEU (generiert, eingecheckt) | TS-Import-Ziel (Vite `resolveJsonModule`, bereits aktiv laut `frontend/tsconfig.json`) |
| `internal/model/trip.go::catalogIDToAlertMetrics` | MODIFY | wird beim Package-Init aus dem Embed geparst statt als Literal gepflegt |
| `frontend/.../corridorEditorState.ts::ROUTE_CORRIDOR_CATALOG_IDS` | MODIFY | wird aus dem JSON-Import abgeleitet, minus der zwei dokumentierten, weiterhin bewachten Ausnahmen |
| `tests/tdd/test_alert_metric_mapping_parity.py` | MODIFY | wird vom Python↔TS-Paritätstest zum Dreifach-Frische-Ratchet erweitert (Python-Quelle ⇔ beide generierten Dateien ⇔ TS-Ableitung) |
| `src/services/deviation_alert_engine.py`, `src/services/alert_preset.py`, `src/services/compare_alert.py` | UNVERÄNDERT | Direktimporteure des Python-Master-Dicts `_ALERT_METRIC_TO_CATALOG_ID` — die Python-interne Struktur ändert sich nicht, nur ihre Auslieferung an Go/TS |
| `internal/model/alert_metric_mapping_1257_test.go`, `internal/model/alert_sync_test.go`, `internal/store/store_809_test.go` | READ (Regressionsnachweis) | bestehende Go-Tests mit echten Katalog-IDs — müssen nach der Umstellung unverändert grün bleiben (Neutralitätsbeweis) |
| `docs/adr/0015-dual-stack-zielarchitektur.md` (Regel 3) | REFERENCE | diese Etappe setzt „keine Logik-Duplizierung zwischen den Stacks" konkret um; neues ADR-0045 dokumentiert das dabei entstehende, wiederverwendbare Muster |

## Implementation Details

### 1. Erzeuger-Skript (neue, alleinige Übersetzungsstelle)

`scripts/generate_alert_metric_mapping.py` importiert
`catalog_id_to_alert_metrics()` aus `src/services/weather_change_detection.py`
und schreibt eine deterministische JSON-Serialisierung (sortierte Schlüssel,
sortierte Wertelisten, `indent=2`, abschließender Zeilenumbruch) an zwei
Zielpfade:

- `internal/model/alert_metric_mapping.generated.json`
- `frontend/src/lib/generated/alertMetricMapping.generated.json`

Beide Dateien haben denselben Inhalt — dieselben 7 Schlüssel wie das heutige
Go-Literal (inkl. `temperature_cold`), da `catalog_id_to_alert_metrics()`
bereits auf das alarmfähige Vokabular gefiltert ist. Das Skript bietet zwei
Modi: `write` (Dateien schreiben) und `--check` (nur vergleichen, Exit ≠ 0 mit
konkreter Diff-Meldung bei Abweichung — kein Seiteneffekt). `--check` ist die
Grundlage des Ratchet-Tests (Abschnitt 4).

**Warum zwei physische Dateien statt einer:** `go:embed` kann nur Dateien
einbinden, die im selben Verzeichnis-Teilbaum liegen wie die Quelldatei mit
der Direktive (`internal/model/trip.go` kann keine Datei außerhalb von
`internal/model/` referenzieren, kein `../`). Ein einzelner Dateiort, der von
beiden Toolchains gleichzeitig gelesen wird, ist damit ohne Symlink-Trick
(nicht plattformübergreifend git-sicher) nicht möglich. Beide Dateien
entstehen aber aus **einem** Lauf **eines** Skripts aus **einer** Quelle und
werden vom Ratchet-Test gegeneinander UND gegen die Python-Quelle geprüft
(Abschnitt 4) — mechanisch so dicht wie eine einzelne Datei, ohne Go oder
Vite in einen Konflikt mit ihren jeweiligen Sicherheits-/Verzeichnisgrenzen
zu bringen (Go-Embed-Teilbaum-Regel; Vite `server.fs.allow` würde für einen
Import außerhalb von `frontend/` sonst erweitert werden müssen).

### 2. Go: `go:embed` ersetzt das Literal

`internal/model/trip.go` verliert die Literal-Map `catalogIDToAlertMetrics`.
Stattdessen:

```go
//go:embed alert_metric_mapping.generated.json
var alertMetricMappingJSON []byte

var catalogIDToAlertMetrics = mustParseAlertMetricMapping(alertMetricMappingJSON)

func mustParseAlertMetricMapping(raw []byte) map[string][]AlertMetric {
    var parsed map[string][]string
    if err := json.Unmarshal(raw, &parsed); err != nil {
        panic(fmt.Sprintf("internal/model: embedded alert_metric_mapping.generated.json is invalid: %v", err))
    }
    result := make(map[string][]AlertMetric, len(parsed))
    for catalogID, metrics := range parsed {
        vals := make([]AlertMetric, len(metrics))
        for i, m := range metrics {
            vals[i] = AlertMetric(m)
        }
        result[catalogID] = vals
    }
    return result
}
```

`mustParseAlertMetricMapping` ist bewusst als eigene, testbare Funktion
geschnitten (nicht anonym im `var`-Initializer), damit ein Go-Test sie direkt
mit kaputten Bytes aufrufen kann, ohne den echten Embed zu manipulieren
(AC-4). Läuft zur Package-Init-Zeit — **kein Laufzeit-HTTP-Call**, kein neues
Fehlermodell im synchronen Persistenzpfad `store.SaveTrip`/`LoadTrip` →
`ActiveAlertableMetricIDs()` → `SyncAlertRules()` (bestätigt vollständig
synchron, kein Async-Offload). Ein defektes Embed führt zum sofortigen,
lauten Programmabsturz beim Start (fail fast), nicht zu einer schleichend
leeren Map, die alle Alarmregeln stillschweigend abschaltet.

`ActiveAlertableMetricIDs()` selbst, seine Signatur und alle 23 bekannten
Verbraucher (`store.SaveTrip`/`LoadTrip`, `weather_config.go`) bleiben
unverändert — nur die Herkunft der internen Tabelle wechselt.

### 3. TypeScript: Import statt Literal, Ausnahmen bleiben Code

`corridorEditorState.ts` importiert die generierte Datei (Vite/SvelteKit,
`resolveJsonModule` ist bereits aktiv) und leitet `ROUTE_CORRIDOR_CATALOG_IDS`
daraus ab, indem es die zwei dokumentierten Ausnahmen herausfiltert — dieselbe
Menge, die heute schon in `tests/tdd/test_alert_metric_mapping_parity.py`
bewacht wird (`_FE_BRIDGE_EXCEPTIONS = {"temperature_cold"}`,
`_FE_BRIDGE_THUNDER_EXCEPTION = {"thunder"}`):

```ts
import rawMapping from '$lib/generated/alertMetricMapping.generated.json';

const FRONTEND_EXCLUDED_CATALOG_IDS = new Set(['temperature_cold', 'thunder']);

export const ROUTE_CORRIDOR_CATALOG_IDS: Record<string, string[]> = Object.fromEntries(
	Object.entries(rawMapping as Record<string, string[]>).filter(
		([catalogId]) => !FRONTEND_EXCLUDED_CATALOG_IDS.has(catalogId)
	)
);
```

Die beiden Ausnahmen selbst ziehen NICHT in die generierte Datei — sie bleibt
die vollständige, ungefilterte Abbildung (identisch zu Go). Die Ausnahmen
bleiben, wo sie fachlich begründet sind: im TS-Konsumentencode, weiterhin
über die bestehenden Rechtfertigungs-Wächter im Ratchet-Test abgesichert
(Abschnitt 4). Der große erklärende Kommentarblock über
`ROUTE_CORRIDOR_CATALOG_IDS` wird aktualisiert: „dritte, unbewachte Kopie"
stimmt nach E5 nicht mehr — es gibt keine dritte Handkopie mehr, sondern eine
generierte Ableitung mit zwei benannten, bewachten Filtern.

### 4. Ratchet-Test (Erweiterung von `test_alert_metric_mapping_parity.py`)

Der bestehende Test prüft heute Python↔TS über Quelltext-Parsing. Er wird um
zwei Prüfungen erweitert, ohne die bestehende Ausnahme-Governance
(`_GUARDED_FE_BRIDGE_EXCEPTIONS`, Rechtfertigungs-Wächter) zu verlieren:

1. **Python ⇔ generierte Dateien:** `scripts/generate_alert_metric_mapping.check()`
   wird direkt aufgerufen (kein Subprozess, deterministisch, kein Netz —
   passt in die Kernschicht). Er vergleicht die frisch aus
   `catalog_id_to_alert_metrics()` berechnete Abbildung gegen den Inhalt
   beider eingecheckter JSON-Dateien und meldet jede Abweichung mit
   Schlüssel/erwartetem/gefundenem Wert. Das ist die eigentliche
   Mutations-Falle: Ändert sich die Python-Quelle, ohne dass jemand das
   Skript erneut laufen lässt, driften die eingecheckten Dateien vom
   Quellcode ab — genau das fängt diese Prüfung.
2. **TS-Ableitung ⇔ generierte Datei minus Ausnahmen:** wie heute, aber die
   TS-Seite wird nicht mehr als Literal geparst, sondern die generierte TS-
   JSON-Datei wird gelesen und die zwei Ausnahmen abgezogen — die
   bestehenden `test_frontend_exception_is_still_justified` und
   `test_thunder_exception_is_still_justified` bleiben inhaltlich
   unverändert bestehen (sie prüfen die Rechtfertigung der Ausnahme, nicht
   die Kopiermethode).

Die Go-Seite braucht **keinen eigenen Python-seitigen Prüfschritt** mehr:
Weil `catalogIDToAlertMetrics` in Go nach dieser Etappe ausschließlich durch
Deserialisieren derselben eingecheckten JSON-Datei entsteht, die auch Prüfung
1 gegen die Python-Quelle validiert, kann Go strukturell nicht mehr von
Python abweichen — es gibt dort keine Handkopie mehr, die driften könnte. Die
verbleibende Go-seitige Prüfpflicht ist eine andere: dass der Embed-Mechanismus
selbst korrekt lädt und bei Defekt laut scheitert (AC-3, AC-4), nicht dass er
inhaltlich mit Python übereinstimmt.

## Expected Behavior

- **Input:** Ein Entwickler ändert `_ALERT_METRIC_TO_CATALOG_ID` in
  `weather_change_detection.py` (z. B. eine neue Katalog-ID für eine
  alarmfähige Größe) und führt `scripts/generate_alert_metric_mapping.py`
  aus.
- **Output:** Beide generierten JSON-Dateien werden aktualisiert und
  eingecheckt; beim nächsten Go-Build übernimmt `go:embed` automatisch den
  neuen Stand; das Frontend liest ihn beim nächsten Vite-Build ebenso ohne
  Codeänderung an `corridorEditorState.ts`. Vergisst der Entwickler den
  Skriptlauf, meldet der Ratchet-Test die Abweichung konkret, statt sie
  unbemerkt zu lassen.
- **Side effects:** Keine — die drei heute wirksamen Werte (7 Go-Einträge, 13
  Python-Einträge in `_ALERT_METRIC_TO_CATALOG_ID`, 5 TS-Einträge + 2
  Ausnahmen) bleiben inhaltlich exakt erhalten (Byte-für-Byte-
  Verhaltensneutralität, s. AC-3/AC-5/AC-9). Kein Nutzerverhalten ändert
  sich, kein Migrations-Schritt nötig (reine Bauzeit-/Quellcode-Änderung,
  keine Persistenzformat-Änderung).

## Acceptance Criteria

- **AC-1:** Given `catalog_id_to_alert_metrics()` berechnet heute die
  7-Einträge-Vorwärtsabbildung (inkl. `temperature_cold`) / When
  `scripts/generate_alert_metric_mapping.py` ausgeführt wird / Then schreibt
  es `internal/model/alert_metric_mapping.generated.json` UND
  `frontend/src/lib/generated/alertMetricMapping.generated.json` mit exakt
  denselben 7 Schlüsseln und denselben Wertemengen wie die Python-Funktion —
  und beide generierten Dateien sind inhaltlich identisch zueinander.
  - Test: Skript gegen das reale Python-Modul ausführen, beide
    Ausgabedateien parsen und gegen `catalog_id_to_alert_metrics()` sowie
    gegeneinander vergleichen (Kernschicht, kein Netz).

- **AC-2 (Mutations-Gegenprobe, PFLICHT):** Given eine der beiden
  eingecheckten generierten Dateien wird lokal (nicht committet) so verändert,
  dass sie nicht mehr zur aktuellen Python-Quelle passt — ODER die
  Python-Quelle wird geändert, ohne das Skript erneut laufen zu lassen / When
  der Ratchet-Test läuft / Then schlägt er fehl und benennt konkret die
  abweichende Katalog-ID mit erwartetem und gefundenem Wert — kein stilles
  Grün. Nachweis-Protokoll: einen Eintrag (z. B. `"gust"`) aus einer lokalen
  Kopie von `_ALERT_METRIC_TO_CATALOG_ID` entfernen, Ratchet-Test laufen
  lassen (muss rot werden und `"gust"` in der Meldung nennen), Änderung
  zurücknehmen, Ratchet-Test läuft wieder grün. Protokollierung Pflicht
  analog `fix_1435_e3b_sms_kuerzel.md` Abschnitt „Wirksamkeitsnachweis der
  Ratsche" (s. u.).
  - Test: `tests/tdd/test_alert_metric_mapping_parity.py`, neuer Prüfschritt
    aus Implementation Details Punkt 4.1.

- **AC-3:** Given `internal/model/trip.go` bindet die generierte JSON-Datei
  per `go:embed` ein und baut `catalogIDToAlertMetrics` daraus / When Go
  gebaut und die bestehenden Golden-Tests mit echten Katalog-IDs laufen /
  Then liefern `TestActiveAlertableMetricIDs_AllSixCatalogMetrics`,
  `TestActiveAlertableMetricIDs_TemperatureOnlyYieldsBothMinAndMax` und
  `TestActiveAlertableMetricIDs_SnowfallLimitAndFreezingLevelDedup`
  (`internal/model/alert_metric_mapping_1257_test.go`) sowie
  `TestActiveAlertableMetricIDsDeduplicated`
  (`internal/model/alert_sync_test.go`) unverändert dieselben Ergebnisse wie
  vor der Umstellung — Byte-für-Byte-Verhaltensneutralität für Go, ohne dass
  diese Tests selbst angepasst werden mussten.
  - Test: bestehende Go-Testdateien, unverändert, grün nach der Umstellung.

- **AC-4:** Given die eingebettete JSON-Datei wäre kaputt (simuliert, nicht
  der echte Embed) / When `mustParseAlertMetricMapping()` mit fehlerhaften
  Bytes aufgerufen wird / Then löst die Funktion einen Panic mit einer
  konkreten Fehlermeldung aus — sie liefert NIE eine leere Map, die
  `ActiveAlertableMetricIDs()` stillschweigend nutzlos machen würde (jeder
  Trip-Speichervorgang würde dann lautlos keine Alarmregeln mehr
  synchronisieren).
  - Test: neuer Go-Unit-Test ruft `mustParseAlertMetricMapping([]byte("{invalid"))`
    direkt auf und erwartet einen `recover()`-fähigen Panic mit
    aussagekräftiger Meldung.

- **AC-5:** Given `corridorEditorState.ts` leitet `ROUTE_CORRIDOR_CATALOG_IDS`
  aus dem JSON-Import ab (minus `temperature_cold`/`thunder`) / When der
  Wertebereiche-Editor mit einem Trip aufgebaut wird, der
  `snowfall_limit`+`freezing_level` gleichzeitig aktiv hat (die
  Dedup-Regressionsszene aus #1387) / Then bietet „+ Metrik" weiterhin genau
  den Schneefallgrenzen-Korridor an — dieselbe Menge wählbarer Korridore wie
  vor der Umstellung, ohne dass `corridorEditorState.ts` dafür eine eigene
  Literal-Tabelle pflegt.
  - Test: bestehende Frontend-Tests für `buildRoutePool()`/den Korridor-Pool,
    unverändert grün (Neutralitätsbeweis TS-Seite).

- **AC-6:** Given ein Entwickler ändert eine der generierten Dateien direkt
  von Hand, statt das Skript laufen zu lassen (z. B. um schnell eine ID
  hinzuzufügen) / When der Ratchet-Test läuft / Then erkennt er die
  Abweichung von der frisch aus Python berechneten Abbildung genauso wie bei
  AC-2 — der Schutz gilt unabhängig davon, ob die Drift durch Python-Änderung
  ohne Regenerierung oder durch direkte Handbearbeitung der generierten Datei
  entsteht.
  - Test: Teil desselben Prüfschritts wie AC-2, zusätzlicher Fall: generierte
    Datei manuell verfälschen (Python-Quelle unverändert lassen), Ratchet-Test
    muss trotzdem rot werden.

- **AC-7:** Given die zwei dokumentierten Ausnahmen (`temperature_cold` nicht
  selectable, `thunder` seit #1425 S2 ordinal umgezogen) / When die generierte
  Datei geschrieben wird / Then enthält sie BEIDE Katalog-IDs weiterhin
  vollständig (Go braucht `temperature_cold` unverändert für den
  Kältealarm-Pfad) — die Ausnahmen wirken ausschließlich im TS-Filtercode,
  verschwinden aber nie aus der generierten Rohdatei.
  - Test: `test_frontend_exception_is_still_justified` und
    `test_thunder_exception_is_still_justified` (bestehend, inhaltlich
    unverändert) bleiben grün; zusätzlich eine Assertion, dass die generierte
    Datei `"temperature_cold"` und `"thunder"` als Schlüssel führt.

- **AC-8 (`# doc-compliance-test`):** Given die Kommentare in
  `internal/model/trip.go:230-231` und
  `src/services/weather_change_detection.py` behaupten fälschlich, der
  bestehende Test decke die Go-Kopie inhaltlich ab bzw. Go rufe die
  Python-Funktion direkt auf / When E5 ausgeliefert ist / Then beschreiben
  beide Kommentare den tatsächlichen Mechanismus (generiertes, eingebettetes
  Artefakt + Ratchet-Test) korrekt.
  - Test: Datei-Inhalts-Assertion auf die korrigierten Kommentartexte
    (bewusst als reiner Doku-Compliance-Test markiert, kein
    Verhaltensnachweis).

- **AC-9:** Given ein Trip mit `display_config.metrics[]`, in dem
  `snowfall_limit` UND `freezing_level` gleichzeitig aktiviert sind / When
  `store.SaveTrip` läuft und dabei `ActiveAlertableMetricIDs()` (jetzt
  Embed-basiert) aufruft / Then entsteht weiterhin genau EINE
  `snow_line`-Delta-Alarmregel (Dedup unverändert) — der synchrone
  Persistenzpfad bleibt ohne neuen Netzwerk-Aufruf und ohne verändertes
  Fehlermodell.
  - Test: `internal/model/alert_metric_mapping_1257_test.go::TestActiveAlertableMetricIDs_SnowfallLimitAndFreezingLevelDedup`
    (bestehend, unverändert, grün).

## Known Limitations

- **Zwei physische generierte Dateien statt einer.** `go:embed` kann keine
  Datei außerhalb des Verzeichnis-Teilbaums der einbindenden Go-Quelldatei
  referenzieren; ein Vite-Import über die Projektgrenze von `frontend/`
  hinaus bräuchte eine Erweiterung von `server.fs.allow` (Sicherheitsgrenze
  des Dev-Servers). Die „echte Zusammenlegung" besteht deshalb aus EINEM
  Skript, EINER Quelle und einer wechselseitigen Prüfung beider generierten
  Dateien gegeneinander und gegen die Quelle — nicht aus einer einzigen
  Datei auf der Platte. Sollte künftig ein geteiltes `shared/generated/`-
  Verzeichnis mit belastbarer Build-Integration für beide Toolchains
  entstehen, kann das zu einer echten Einzeldatei vereinfacht werden; das ist
  nicht Teil dieser Etappe.
- **Go-seitiges Alarm-Vokabular `AlertableMetrics` bleibt ein separates,
  unverändertes Duplikat.** `internal/model/trip.go::AlertableMetrics` (Go)
  wird weiterhin in Python (`_ALERTABLE_METRIC_VALUES` in
  `weather_change_detection.py`) UND im Ratchet-Test selbst
  (`_ALERTABLE_METRIC_VALUES` in `test_alert_metric_mapping_parity.py`,
  Zeile 30-38) von Hand gespiegelt. Das ist ein **anderes** Vokabular
  (welche AlertMetric-Werte überhaupt alarmfähig sind) als die in dieser
  Etappe vereinheitlichte Katalog-ID→AlertMetric-**Zuordnung** — E5 löst es
  bewusst NICHT mit, um den Scope nicht zu sprengen (PO-Entscheidung
  2026-08-05 grenzt E5 explizit auf die Zuordnung ein). Mögliche
  Folge-Etappe von #1435.
- **`alertMetricTable.ts::CATALOG_TO_ALERT_METRICS` bleibt unverändert und
  unvereinheitlicht.** Verwandte, aber bewusst andere vierte Tabelle (23
  Einträge, Alerts-Tab-Sensitivität inkl. Delta-Metriken, führt `snow_line`
  seit #959 nicht mehr) — laut bestehendem TS-Kommentar ausdrücklich NICHT
  dieselbe Abbildung. Wird durch E5 nicht angefasst.
- **Kein sichtbarer Nutzerfehler heute bekannt** (anders als der
  Vorläufer-Vorfall #1387) — E5 ist reine Drift-Prävention für eine
  strukturell wiederkehrende Fehlerklasse, nicht die Behebung eines
  gemeldeten Symptoms.

## Wirksamkeitsnachweis der Ratsche

Analog zur Erfahrung aus Etappe E3a (zwei Wächter waren grün, ohne je etwas
geprüft zu haben) gilt der Ratchet-Test aus AC-2/AC-6 erst als geliefert,
wenn folgender Nachweis erbracht und im PR/Commit protokolliert ist:

1. Eine Katalog-ID (z. B. `"gust"`) wird in einer lokalen, nicht committeten
   Kopie aus `_ALERT_METRIC_TO_CATALOG_ID` entfernt, OHNE das Skript erneut
   laufen zu lassen.
2. Der Ratchet-Test wird gegen diesen Zustand ausgeführt.
3. Die Ausgabe wird protokolliert und muss zeigen: (a) der Test schlägt fehl
   (nicht grün, nicht übersprungen), (b) die Fehlermeldung nennt die
   betroffene Katalog-ID beim Namen.
4. Zweiter Durchlauf: Python-Quelle unverändert lassen, stattdessen eine der
   beiden generierten Dateien direkt von Hand verfälschen — derselbe Nachweis
   (a)/(b) muss auch hierfür erbracht werden.
5. Beide Verfälschungen werden danach zurückgenommen; der reguläre, korrekte
   Code läuft grün.

Ohne diesen protokollierten Nachweis gilt der Ratchet-Test als nicht
abgenommen, unabhängig davon, ob er „grün" ist.

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** Neues ADR-0045 vorgeschlagen (nächste freie Nummer, Stand
  2026-08-05: höchste vergebene ist 0044) — **ergänzt** ADR-0015, ersetzt
  nichts.
- **Rationale:** ADR-0015 Regel 3 fordert „keine Logik-Duplizierung zwischen
  den Stacks — pro Fall EINE Seite als Owner bestimmen, andere abbauen",
  benennt aber keinen Mechanismus dafür. E5 ist im Repo der **erste** Fall,
  der das nicht durch einen reinen Testabgleich (Python↔TS-Parität, wie beim
  Vorläufer #1387) löst, sondern durch ein **generiertes, zur Kompilierzeit
  eingebettetes Artefakt** (`go:embed`, Go-Standardbibliothek, kein externes
  Werkzeug) — ein im Projekt bisher unbelegtes Muster (geprüft: kein
  bestehendes `go:embed`, kein Codegen-Schritt aus Python-Quelltext). Ein
  eigenes ADR lohnt sich, weil dieses Muster für strukturell ähnliche
  Cross-Stack-Duplikate (z. B. den in Issue #1000 dokumentierten Fall, oder
  das in „Known Limitations" benannte `AlertableMetrics`-Vokabular selbst)
  als Vorbild dienen kann, statt dass jeder Fall neu diskutiert, ob ein
  Live-HTTP-Call, ein reiner Paritätstest oder ein generiertes Artefakt die
  richtige Lösung ist. Anders als bei `fix_1435_e3b_sms_kuerzel.md` (dort:
  Nachtrag zu ADR-0011, weil nur eine dort früher gewährte Ausnahme
  zurückgenommen wurde) wird hier kein bestehender ADR-Inhalt korrigiert
  oder ergänzt, sondern ein neuer, wiederverwendbarer Mechanismus erstmals
  dokumentiert — das rechtfertigt eine eigene Nummer statt eines Nachtrags.
  Das neue ADR bleibt kurz: Kontext (Regel 3 ohne Mechanismus), Entscheidung
  (generiertes Artefakt, Python als Owner, Go/TS als Embed-/Import-
  Konsumenten, Ratchet-Test als Drift-Wächter), verworfene Alternativen
  (Laufzeit-HTTP-Call im synchronen Persistenzpfad — neues Ausfallrisiko;
  reiner erweiterter Paritätstest ohne echte Konsolidierung — drei
  Handkopien blieben bestehen), Konsequenzen (neues, aber leichtgewichtiges
  Muster; zwei physische Dateien statt einer, s. Known Limitations).
  Das Anlegen der ADR-Datei und der Index-Zeile ist Teil der
  Implementierungsphase dieser Spec, nicht der Spec-Erstellung selbst.

## Changelog

- 2026-08-05: Initial spec created. Umfang, Randbedingungen und PO-Entscheidung
  aus `docs/context/fix-1435-e5-alert-mapping.md` übernommen. Alle Fundstellen
  (Go, Python, TS, bestehender Paritätstest) gegen den aktuellen Code-Stand
  verifiziert, nicht unbesehen aus dem Kontext-Dokument übernommen. Go-Embed-
  Verzeichnis-Restriktion und Vite-`fs.allow`-Grenze recherchiert und als
  Grund für „zwei generierte Dateien statt einer" dokumentiert (Known
  Limitations).
