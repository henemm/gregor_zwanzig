---
entity_id: fix_1066_store_write_logging
type: bugfix
created: 2026-07-08
updated: 2026-07-08
status: draft
workflow: fix-1066-store-write-logging
---

# Store-Schreibfehler werden serverseitig geloggt (#1066)

## Approval

- [ ] Approved

## Purpose

Schreibfehler im Persistenz-Pfad `internal/store/` werden derzeit stumm zum generischen
HTTP-Fehler `{"error":"store_error"}` verdichtet — der zugrundeliegende OS-Fehler (z.B.
"permission denied") geht dabei verloren. Dieser Fix schließt die **Diagnostik-Lücke**: jeder
fehlgeschlagene Schreibvorgang wird künftig serverseitig mit Dateipfad und Ursache geloggt, damit
eine zukünftige Berechtigungs-Regression (wie am 2026-07-07) sofort erkennbar ist statt tagelang
unbemerkt zu bleiben. Der eigentliche Berechtigungs-Ausfall selbst ist bereits per `setfacl`
behoben und NICHT Teil dieses Fixes.

## Source

- **File:** `internal/store/trip.go` (und 7 weitere Store-Dateien, siehe Scope)
- **Identifier:** neuer Helper `func writeFileLogged(path string, data []byte) error`

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `os` (Go stdlib) | package | `os.WriteFile` bleibt der zugrundeliegende Schreibaufruf |
| `log` (Go stdlib) | package | `log.Printf` — bestehende Logging-Konvention im Store (52 Vorkommen) |
| `fmt` (Go stdlib) | package | `%w`-Error-Wrapping für Pfad-Kontext im Rückgabefehler |
| `internal/handler/trip.go:275-280` | consumer | Handler-Grenze prüft nur `err != nil` → `500 store_error`; bleibt unveraendert |

## Scope

### Affected Files
| File | Change Type | Description |
|------|-------------|--------------|
| `internal/store/trip.go` | MODIFY | Neuer Helper `writeFileLogged`; Zeile 128 auf Helper umgestellt |
| `internal/store/user.go` | MODIFY | Zeilen 78 und 101 (`SaveUser`, Password-Reset) auf Helper umgestellt |
| `internal/store/group.go` | MODIFY | Zeile 152 (`SaveGroups`) auf Helper umgestellt |
| `internal/store/subscription.go` | MODIFY | Zeile 120 auf Helper umgestellt |
| `internal/store/compare_preset.go` | MODIFY | Zeile 59 auf Helper umgestellt |
| `internal/store/location.go` | MODIFY | Zeile 91 auf Helper umgestellt |
| `internal/store/metric_preset.go` | MODIFY | Zeile 142 auf Helper umgestellt |
| `internal/store/store_write_logging_test.go` | CREATE | Neue Test-Datei: Log-Verhalten bei Schreibfehler/-erfolg |

### Estimated Changes
- Files: 8
- LoC: +60/-24 (grobe Schaetzung: 1 Helper-Funktion ~10 Zeilen, 8 Call-Sites je ~1 Zeile geaendert, Tests ~40 Zeilen)

## Implementation Details

Package-privater Helper in `internal/store/` (z.B. neue Datei `internal/store/write.go` oder in
`trip.go` co-lokalisiert):

```go
func writeFileLogged(path string, data []byte) error {
    if err := os.WriteFile(path, data, 0644); err != nil {
        log.Printf("store: write %s failed: %v", path, err)
        return fmt.Errorf("write %s: %w", path, err)
    }
    return nil
}
```

Alle 8 produktiven `os.WriteFile(...)`-Aufrufe in `internal/store/` (trip.go:128, user.go:78,
user.go:101, group.go:152, subscription.go:120, compare_preset.go:59, location.go:91,
metric_preset.go:142) werden 1:1 durch `writeFileLogged(path, data)` ersetzt. Rückgabewert und
Fehlerverhalten bleiben fuer die Aufrufer aequivalent (weiterhin nur `err != nil`-Pruefung noetig,
kein `errors.Is`/String-Match im Callgraph gefunden). Die HTTP-Response-Schicht
(`internal/handler/*.go`) wird NICHT geaendert — sie gibt bei `err != nil` weiterhin
`{"error":"store_error"}` mit Status 500 zurueck, ohne den gewrappten Fehler (der den Dateipfad
enthaelt) an den Client durchzureichen.

Warum Store-Layer statt Handler-Layer: Der Store ist der einzige Choke-Point fuer alle Schreiber
(Handler, Scheduler, CLI). Ein zentraler Helper loggt alles einheitlich; eine Handler-seitige
Loesung waere ueber ~15 verstreute `store_error`-Stellen verteilt.

## Test Plan

### Automated Tests (TDD RED)
- [ ] Test 1: GIVEN eine Zieldatei im Store-Verzeichnis ist nicht schreibbar (chmod 0444) WHEN
  ein Store-Save-Aufruf (z.B. `SaveTrip`) versucht dorthin zu schreiben THEN wird eine Log-Zeile
  erzeugt, die sowohl den Dateipfad als auch die zugrundeliegende OS-Fehlerursache
  ("permission denied") enthaelt (echtes `log.SetOutput(buf)`, kein Mock).
- [ ] Test 2: GIVEN derselbe fehlgeschlagene Schreibversuch WHEN der Store-Aufruf zurueckkehrt
  THEN ist der zurueckgegebene Fehler nicht nil und traegt den Dateipfad als Kontext (verifiziert
  per `err.Error()`-Inhalt oder `errors.Unwrap`).
- [ ] Test 3: GIVEN ein schreibbares Zielverzeichnis (Temp-Dir) WHEN ein Store-Save-Aufruf normal
  durchlaeuft THEN wird KEINE Fehler-Log-Zeile erzeugt, der Rueckgabewert ist nil, und die Datei
  ist mit dem erwarteten Inhalt lesbar (Roundtrip-Beweis, kein Dateiinhalt-String-Check).
- [ ] Test 4: GIVEN ein fehlgeschlagener Schreibversuch WHEN der zugehoerige HTTP-Handler
  (`internal/handler/trip.go`) den Store-Fehler verarbeitet THEN antwortet er weiterhin exakt mit
  `{"error":"store_error"}` und Status 500 — ohne Dateipfad oder OS-Fehlertext im Response-Body.

## Acceptance Criteria

- **AC-1:** Given eine Zieldatei im Store-Verzeichnis ist nicht schreibbar (z.B. `chmod 0444`) /
  When ein Store-Schreibvorgang (`os.WriteFile` ueber den neuen Helper) fehlschlaegt / Then
  loggt der Store eine Zeile, die sowohl den betroffenen Dateipfad als auch die zugrundeliegende
  Fehlerursache (z.B. "permission denied") enthaelt.
  - Test: Echter `os.Chmod(...,0444)` auf Temp-Dir-Datei, echter `log.SetOutput(buf)`, Log-Inhalt
    auf Pfad + Fehlerursache geprueft — kein Mock.

- **AC-2:** Given derselbe fehlgeschlagene Schreibvorgang / When der Store-Save-Aufruf
  zurueckkehrt / Then liefert er einen Fehler ungleich nil, der ueber `%w`-Wrapping Pfad-Kontext
  traegt, statt den rohen `os.WriteFile`-Fehler unveraendert oder gar nil zurueckzugeben.
  - Test: Rueckgabewert des Store-Aufrufs pruefen (`err != nil`, `errors.Unwrap(err)` bzw.
    `err.Error()` enthaelt Pfad) auf echtem Temp-Dir-Fehlerfall.

- **AC-3:** Given ein schreibbares Zielverzeichnis (Temp-Dir, normale Rechte) / When ein
  Store-Save-Aufruf regulaer durchlaeuft / Then wird KEIN Fehler-Log erzeugt, der Rueckgabewert
  ist nil, und die geschriebenen Daten sind per erneutem Lesevorgang unveraendert abrufbar
  (Roundtrip) — das Verhalten entspricht exakt dem Vor-Fix-Zustand.
  - Test: Echter Schreib-Lese-Roundtrip auf Temp-Dir; Log-Buffer bleibt leer; kein
    Dateiinhalt-String-Check, sondern struktureller Vergleich der geschriebenen/gelesenen Daten.

- **AC-4:** Given ein Store-Schreibfehler tritt auf / When der zustaendige HTTP-Handler
  (`internal/handler/trip.go` bzw. analoge Handler) darauf reagiert / Then bleibt die
  HTTP-Response exakt `{"error":"store_error"}` mit Status 500 — es wird zu keinem Zeitpunkt ein
  Dateipfad oder eine OS-Fehlermeldung an den Client geleakt.
  - Test: Echter HTTP-Call gegen den betroffenen Endpoint mit erzwungenem Schreibfehler im
    Store-Verzeichnis; Response-Body und Status-Code pruefen (kein Pfad-Substring im Body).

- **AC-5:** Given der vollstaendige `internal/store/`-Produktivcode / When nach allen bekannten
  direkten `os.WriteFile`-Aufrufen gesucht wird / Then laufen alle 8 zuvor identifizierten
  Schreibstellen (trip.go, user.go ×2, group.go, subscription.go, compare_preset.go, location.go,
  metric_preset.go) ueber den zentralen `writeFileLogged`-Helper — keine verbleibende direkte
  `os.WriteFile`-Nutzung im Produktivcode von `internal/store/`.
  - Test: `grep -n "os.WriteFile" internal/store/*.go` ausserhalb von `_test.go`-Dateien liefert
    ausschliesslich den einen Aufruf innerhalb des Helpers selbst.

## Known Limitations

- **Monitoring/Selftest ist NICHT Teil dieses Fixes** — ein aktiver Schreib-Selftest, der
  Berechtigungsprobleme proaktiv erkennt (statt nur reaktiv zu loggen), ist Folge-Issue #1120.
- Die **0644-Permission-Subtilitaet** bei bereits existierenden Dateien wird nicht
  verhaltensseitig geaendert: `os.WriteFile` ignoriert `perm`, wenn die Zieldatei bereits
  existiert (nur bei Neuanlage relevant) — dieser Fix aendert daran nichts, dokumentiert es nur.
- Das Logging erfolgt ausschliesslich serverseitig (`log.Printf` -> stdout/Journal); es gibt
  keine Benachrichtigung (E-Mail/Telegram/BetterStack) bei einem geloggten Schreibfehler — das
  waere Gegenstand von #1120.

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** keine
- **Rationale:** Reiner Diagnostik-Fix innerhalb einer bestehenden Schicht (Store-Layer), keine
  neue Architekturentscheidung — folgt der bereits etablierten Logging-Konvention (`log.Printf`
  fuer I/O-Fehler, siehe `trip.go:34/40`, `location.go:37/43`).

## Changelog

- 2026-07-08: Initial spec created
