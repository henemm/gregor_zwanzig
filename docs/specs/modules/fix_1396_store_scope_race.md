---
entity_id: fix_1396_store_scope_race
type: module
created: 2026-07-31
updated: 2026-08-01
status: implemented
version: "1.0"
tags: [go-api, multi-user, tenant-isolation, concurrency, bug]
---

<!-- Issue #1396 — Scheibe S1 von 2. S2 (Wächter) ist seit 2026-08-01 ebenfalls
     ausgeliefert (68bac9c3), Spec: fix_1396_s2_store_scope_guard.md.
     Issue #1396 ist damit komplett geschlossen. -->

# Fix #1396 S1 — Nutzerkennung je Anfrage statt geteilt

## Approval

- [x] Approved — PO-go 2026-07-31 (Zuschnitt: zwei Scheiben, S2 als eigener Workflow)

## Purpose

25 HTTP-Zugriffswege der Go-API halten die Nutzerkennung der laufenden Anfrage
an einem Platz fest, den sich **alle gleichzeitigen Anfragen derselben Route
teilen**. Fragen zwei angemeldete Nutzer im selben Moment dieselbe Route ab,
kann der eine mit der Kennung des anderen weiterarbeiten und dessen Daten unter
`data/users/<user_id>/` lesen oder schreiben.

Diese Scheibe repariert alle 25 Stellen und sichert das Ergebnis mit einem
Nachweis ab, der zwei Nutzer wirklich gleichzeitig durch die Zugriffswege
schickt. Die strukturelle Absicherung gegen Rückfälle ist **Scheibe S2** und
nicht Teil dieser Spec.

## Source

- **File:** `internal/handler/compare_preset.go` — 6 Stellen (Z. 166, 183, 264, 464, 502, 543)
- **File:** `internal/handler/location.go` — 6 Stellen (Z. 28, 57, 119, 174, 224, 246)
- **File:** `internal/handler/group.go` — 4 Stellen (Z. 17, 35, 93, 174)
- **File:** `internal/handler/metric_preset.go` — 4 Stellen (Z. 122, 137, 193, 231)
- **File:** `internal/handler/briefing_subscription.go` — 3 Stellen (Z. 50, 83, 194)
- **File:** `internal/handler/weather_config.go` — 2 Stellen (Z. 130, 152; nur die **Orts**-Varianten, die Trip-Varianten sind seit #1395 S2 repariert)
- **File:** `internal/handler/store_scope_race_test.go` (NEU) — Nachweis
- **Identifier:** die Zuweisung `s = s.WithUser(...)` an den Store-Parameter der
  äußeren Funktion, innerhalb der zurückgegebenen `http.HandlerFunc`
- **Vorlage:** `internal/handler/trip.go:10-28` (Erklärkommentar aus #1395 S2)

Schicht: **Go-API** (`internal/`). Kein Python-Core, kein Frontend beteiligt.

## Estimated Scope

- **LoC:** ~240 (added+deleted): 25 Zeilen Reparatur → ~50, Kurzverweise in
  6 Dateien → ~30, Nachweis-Datei → ~160
- **Files:** 6 MODIFY + 1 CREATE
- **Effort:** low (Reparatur mechanisch, Vorbild vorhanden)

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `store.Store.WithUser` (`internal/store/store.go:16`) | intern | liefert eine Kopie des Stores mit gesetzter `UserID`; bestimmt `data/users/<user_id>/` |
| `middleware.UserIDFromContext` (`internal/middleware/auth.go:70`) | intern | Nutzerkennung aus dem Anfrage-Kontext |
| `middleware.ContextWithUserID` | intern | Test-Hilfe: setzt die Kennung, wie es die Anmeldeprüfung tut |
| `internal/handler/user_scoped_test.go` | Test | vorhandene Zwei-Nutzer-Testhilfen (`addUserToContext`, `alice`/`bob`-Muster) |
| `internal/handler/trip_etag_ifmatch_test.go:390` | Test | Vorbild für den Parallel-Aufbau (12 Goroutinen, `sync.WaitGroup`) |
| #1395 S2 | Issue | dort gefunden, `trip.go` bereits repariert |

## Implementation Details

Je Stelle wird die **Zuweisung** an den geteilten Parameter durch eine
**anfragelokale Deklaration** ersetzt. Die rechte Seite meint weiterhin den
äußeren Store:

```go
// vorher — schreibt in die von allen Anfragen geteilte Variable
func LocationsHandler(s *store.Store) http.HandlerFunc {
    return func(w http.ResponseWriter, r *http.Request) {
        s = s.WithUser(middleware.UserIDFromContext(r.Context()))

// nachher — jede Anfrage bekommt ihre eigene
        s := s.WithUser(middleware.UserIDFromContext(r.Context()))
```

Geprüfte Voraussetzungen (Analyse, `docs/context/fix-1396-store-race-handler.md`):

- Alle 25 Stellen stehen unmittelbar im Rumpf der zurückgegebenen Funktion,
  nicht in einem `if`/`for`-Block. Die Deklaration gilt damit für den ganzen
  Handler — **keine** Verengung der Sichtbarkeit.
- Jeder betroffene Handler hat **genau eine** solche Stelle.
- `compare_preset.go:183` lautet `s = s.WithUser(userID)` (Zwischenvariable
  statt Aufruf) — inhaltlich derselbe Fehler, muss mitrepariert werden.

Statt den 18-zeiligen Erklärkommentar aus `trip.go` sechsmal zu wiederholen,
bekommt jede der 6 Dateien einen Zweizeiler mit Verweis darauf.

## Expected Behavior

- **Input:** zwei gleichzeitige, angemeldete Anfragen verschiedener Nutzer auf
  dieselbe Route
- **Output:** jede Antwort enthält ausschließlich Daten des jeweils anfragenden
  Nutzers
- **Side effects:** keine. Kein Verhaltenswechsel für einzelne Anfragen, keine
  Änderung an Datenformat, Persistenz oder Schnittstelle. Nichts zu migrieren.

## Nachweis-Lage (wichtig für die Testkonstruktion)

Die Ausgangsmessung ist **grün**:

```
go test -race -count=1 ./internal/handler/...   →  ok  (29,9 s)
```

Nicht weil der Fehler fehlt, sondern weil heute **kein** Test einen der 25
Handler nebenläufig aufruft. Der rote Test muss also erst entstehen.

**Der belastbare Nachweis ist der Wettlauf-Detektor (`-race`), nicht die
Datenprüfung.** Ob zwei parallele Anfragen sich tatsächlich die Kennung
überschreiben, hängt am Zeitverhalten — eine reine Inhaltsprüfung kann auch am
unreparierten Stand zufällig grün sein. Ein Test, der sich allein darauf
stützt, würde flackern. Die Inhaltsprüfung läuft deshalb **zusätzlich** mit,
nicht als alleiniger Beleg.

## Acceptance Criteria

- **AC-1:** Given zwei angemeldete Nutzer mit je eigenen Orten, Gruppen,
  Orts-Vergleichen, Metrik-Vorlagen, Briefing-Abos und Wetter-Einstellungen /
  When beide gleichzeitig und wiederholt dieselbe Route abfragen / Then enthält
  jede Antwort ausschließlich die Daten des Nutzers, der sie gestellt hat, und
  keine einzige Antwort Daten des jeweils anderen.
  - Test: `store_scope_race_test.go` — je eine Route aus jeder der 6 Dateien,
    N Goroutinen wechselweise als `alice` und `bob`, Vergleich der
    Antwortinhalte gegen die je Nutzer angelegten Daten.

- **AC-2:** Given der Wettlauf-Detektor läuft über die Zugriffswege der Go-API /
  When der Nachweis aus AC-1 ausgeführt wird / Then meldet er keinen Konflikt
  mehr, während er gegen den unreparierten Stand derselben Datei einen meldet.
  - Test: `go test -race -count=1 ./internal/handler/...` → Exit 0 nach der
    Reparatur; dokumentierter Gegenbeweis, dass derselbe Test vor der Reparatur
    `WARNING: DATA RACE` an der betroffenen Zeile ausgibt.

- **AC-3:** Given die bestehenden Zugriffswege für Orte, Gruppen,
  Orts-Vergleiche, Metrik-Vorlagen, Briefing-Abos und Wetter-Einstellungen /
  When die Reparatur eingespielt ist / Then verhalten sie sich für eine einzelne
  Anfrage unverändert — gleiche Antworten, gleiche Statuscodes, gleiche
  Dateien unter `data/users/<user_id>/`.
  - Test: die vorhandene Handler-Testsuite bleibt vollständig grün
    (`go test -count=1 ./internal/handler/...`), gemessen gegen die
    Ausgangsmessung.

- **AC-4:** Given ein Entwickler sieht sich künftig eine der 6 Dateien an /
  When er wissen will, warum dort eine anfragelokale Deklaration steht / Then
  findet er in jeder der 6 Dateien einen Hinweis, der ihn zur ausführlichen
  Begründung führt, ohne dass diese sechsmal wiederholt wird.
  - Test: `# doc-compliance-test` — je Datei ein Verweis auf `trip.go`
    vorhanden. (Bewusst ein Inhalts-Check: Der Zweck **ist** hier der Text.)

## Known Limitations

- **Vollständigkeit ist in dieser Scheibe nicht strukturell abgesichert.** AC-1
  belegt das Verhalten an 6 repräsentativen Routen, nicht an allen 25. Dass
  keine Stelle vergessen wurde und keine neue entsteht, leistet der Wächter aus
  **S2** — seit 2026-08-01 ausgeliefert (`68bac9c3`,
  `internal/handler/store_scope_guard_test.go`, Spec
  `fix_1396_s2_store_scope_guard.md`). Diese Einschränkung gilt damit **nicht
  mehr**; sie bleibt hier nur als Beschreibung des Standes von S1 stehen.
- **Der Fehler ist heute schwer auszulösen.** Er braucht zwei angemeldete
  Nutzer im selben Sekundenbruchteil auf derselben Route. Bei aktuellem
  Nutzungsstand ist das unwahrscheinlich — die Reparatur erfolgt, weil es sich
  um undefiniertes Verhalten handelt und das Risiko mit jedem Nutzer wächst,
  nicht wegen eines beobachteten Vorfalls.
- **Der Weg ohne Nutzerkennung ist bereits zu.** Alle betroffenen Routen sind
  anmeldepflichtig; eine leere Kennung wird abgewiesen
  (`internal/middleware/auth.go:98`). Ein Datenleck ohne Gleichzeitigkeit ist
  damit ausgeschlossen — diese Spec deckt es folglich nicht ab.

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** keine
- **Rationale:** Keine Entscheidungsfläche berührt. Die Mandantentrennung über
  `s.WithUser(middleware.UserIDFromContext(r.Context()))` ist in CLAUDE.md
  bereits als verbindlich festgehalten; diese Scheibe stellt den vorgeschriebenen
  Zustand her, statt eine neue Entscheidung zu treffen.

## Changelog

- 2026-07-31: Initial spec created (Scheibe S1 von 2 zu Issue #1396)
- 2026-08-01: Status auf `implemented`. Scheibe S2 (Wächter) ist mit `68bac9c3`
  ausgeliefert, Issue #1396 geschlossen. Die Einschränkung „Vollständigkeit
  nicht strukturell abgesichert" unter Known Limitations gilt seither nicht
  mehr und ist entsprechend gekennzeichnet.
