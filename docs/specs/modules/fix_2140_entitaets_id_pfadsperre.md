---
entity_id: fix_2140_entitaets_id_pfadsperre
type: module
created: 2026-09-06
updated: 2026-09-06
status: draft
version: "1.0"
tags: [security, path-traversal, multi-tenant, entity-id]
---

# Entitäts-ID-Sperre gegen Pfad-Traversal (Scheibe 2 von 2)

## Approval

- [ ] Approved

## Purpose

Client-gesetzte **Entitäts-IDs** (Trip, Ort, Ortsvergleichs-Preset) fließen ungeprüft in
Dateipfade — sowohl im Request-Body (`POST /api/trips`, `POST /api/locations`) als auch im
URL-Pfad-Parameter (`PUT`/`PATCH`/`DELETE`/`GET` auf `/{id}`). Der Router (`chi`) matcht ein rohes
`..`-Segment als gewöhnlichen Wert; `POST /api/trips` mit `{"id":"../../bob/user"}` überschreibt
die `user.json` eines fremden Kontos, das danach nicht mehr anmeldbar ist. Lesend und löschend
gilt derselbe Weg. Eine Entitäts-ID-Validierung existiert nirgends — weder in Go noch in Python;
`validateTrip`/`validateLocation` prüfen ausschließlich auf Leerstring.

Diese Spec schließt die Lücke für die Entitäts-Achse (Achse B): eine kanonische
Pfadsegment-Prüfung `ValidEntityID` an jedem Pfad-Join in `internal/store` (Verteidigung in der
Tiefe) plus Pre-Check in den Handlern für einen sauberen 400er, gespiegelt im Python-Kern für die
von dort aus erreichbaren Lese-Routen. Fortsetzung von Scheibe 1 (Nutzer-Kennungen, live seit
`37559f9f`), die diese Achse bewusst zurückstellte.

## Source

- **File:** `internal/store/pathsafe.go` (bestehend, aus Scheibe 1)
- **Identifier:** `ValidEntityID` (NEU), `ErrInvalidEntityID` (NEU), neben bestehendem
  `ValidUserID`
- **File:** `internal/store/trip.go`
- **Identifier:** `SaveTrip`, `LoadTrip`, `DeleteTrip`
- **File:** `internal/store/location.go`
- **Identifier:** `SaveLocation`, `LoadLocation`, `DeleteLocation`
- **File:** `internal/store/compare_preset.go`
- **Identifier:** `SaveComparePreset`, `LoadComparePreset`, `DeleteComparePreset`
- **File:** `internal/store/briefing_fingerprint.go`
- **Identifier:** `BriefingFingerprint`
- **File:** `internal/handler/trip.go`
- **Identifier:** `validateTrip` plus die fünf Trip-Handler (Create/Get/Update/Patch/Delete)
- **File:** `internal/handler/location.go`
- **Identifier:** `validateLocation` plus die vier Location-Handler
- **File:** `internal/handler/compare_preset.go`
- **Identifier:** die vier Compare-Preset-Handler (via `bailIf`)
- **File:** `internal/handler/weather_config.go`
- **Identifier:** die vier Weather-Config-Handler
- **File:** `internal/handler/briefing_subscription.go`
- **Identifier:** die zwei Briefing-Subscription-Handler (via `bailIf`)
- **File:** `src/app/loader.py`
- **Identifier:** `VALID_ENTITY_ID_RE` (NEU), Guard in Orts-/Trip-Pfadbau
- **File:** `src/services/preview_service.py`
- **Identifier:** Guard vor Trip-Pfadbau (`:67-68`)
- **File:** `api/routers/validator.py`
- **Identifier:** Guard vor Trip-Pfadbau (`:52`)
- **File:** `internal/store/entity_id_test.go` (NEU)
- **File:** `internal/handler/entity_traversal_test.go` (NEU)
- **File:** `tests/unit/test_entity_id_pattern_parity.py` (NEU)

> **PFLICHT — Schicht-Hinweis:** Diese Spec betrifft **zwei getrennte Schichten**:
> - **Go-API** (`internal/store`, `internal/handler`) — Produktions-API auf Port 8090.
> - **Python-Core** (`src/app/loader.py`, `src/services/preview_service.py`,
>   `api/routers/validator.py`) — FastAPI-Kern über `api.main:app`, erreichbar über den Go-Proxy
>   (`internal/handler/proxy.go`, `preview_proxy.go`), der die Entitäts-ID roh in den
>   Python-URL-Pfad spliced, ohne sie zu prüfen.
> Beide Schichten bekommen dieselbe Zusicherung (`ValidEntityID` / `VALID_ENTITY_ID_RE`), analog
> zum bestehenden Paritätsmuster für Nutzer-Kennungen (`ValidUserIDRe` / `VALID_USER_ID_RE`).

## Estimated Scope

- **LoC:** ~175 (Go ~135, Python ~40)
- **Files:** 16 (13 MODIFY, 3 CREATE)
- **Effort:** medium

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `internal/store.ValidUserID` / `ValidUserIDRe` | go function/var | Aus Scheibe 1, lebt unverändert in derselben Datei `pathsafe.go` weiter — `ValidEntityID` ergänzt, ersetzt nichts |
| `src/app/loader.VALID_USER_ID_RE` | python constant | Vorbild für `VALID_ENTITY_ID_RE`, gleiche Datei |
| ADR-0003 | adr | Konsequente Mandantentrennung, Zwei-Nutzer-Pflichttest — diese Spec setzt sie für Entitäts-IDs durch |
| `internal/handler/bailIf` | go helper | Bestehendes Pre-Check-Muster in Compare-Preset- und Briefing-Subscription-Handlern, wird für den neuen Guard wiederverwendet |
| `tests/unit/test_user_id_pattern_parity.py` | python test | Bauart-Vorlage für den neuen `test_entity_id_pattern_parity.py` |
| `internal/handler/proxy.go::appendUserID` | go function | Zeigt das bestehende Muster, wie die Nutzer-ID vor dem Splice in die Python-URL geprüft wird — die Entitäts-ID braucht dieselbe Behandlung |

## Implementation Details

1. **`internal/store/pathsafe.go`** — `ValidEntityID(id string) bool` prüft ein Pfadsegment, keine
   Zeichen-Whitelist: nicht leer, kein `/`, kein `\`, kein NUL-Byte, nicht `.` und nicht `..`, kein
   führender Punkt. Unicode-Buchstaben bleiben zulässig. `ErrInvalidEntityID` als Sentinel-Fehler
   für die Store-Methoden.

2. **Store-Schicht (`trip.go`, `location.go`, `compare_preset.go`,
   `briefing_fingerprint.go`)** — jede betroffene Methode prüft `ValidEntityID(id)` als erste
   Anweisung, vor jedem `filepath.Join`. Verteidigung in der Tiefe: fängt auch Aufrufer, die den
   Handler-Pre-Check umgehen (z. B. interne Kommando-/Scheduler-Pfade, direkte Store-Aufrufe in
   Tests). Keine Signaturänderung — alle Methoden geben bereits `error` zurück.

3. **Handler-Schicht (`trip.go`, `location.go`, `compare_preset.go`, `weather_config.go`,
   `briefing_subscription.go`)** — Pre-Check vor dem ersten Store-Aufruf, für den sauberen
   Statuscode. Bei Fehltreffer: **400** mit dem bestehenden `validation_error`-Antwortmuster
   (Vorbild: `trip.go:163-171`, `location.go:74-82`) — bewusst **nicht** byte-identisch zum
   „existiert nicht"-Zweig, weil diese Routen authentifiziert und user-scoped sind (nichts zu
   enumerieren, anders als bei den öffentlichen Auth-Routen aus Scheibe 1).

4. **Python-Kern (`loader.py`, `preview_service.py`, `validator.py`)** — `VALID_ENTITY_ID_RE` in
   `loader.py` neben `VALID_USER_ID_RE`; Guard vor dem Pfadbau in `preview_service.py:67-68` und
   `validator.py:52`, erreichbar über `GET /api/preview/{trip_id}/email|sms|telegram` und
   `POST /api/trips/{trip_id}/alert-preview`. Der Go-Proxy spliced die Entitäts-ID roh in den
   Python-URL-Pfad (`proxy.go:169,261,304`, `preview_proxy.go:38,76`) — die Prüfung muss auf der
   Python-Seite sitzen, weil der Proxy sie nicht filtert.

5. **Musterparität** — `tests/unit/test_entity_id_pattern_parity.py` (neu, Bauart wie
   `test_user_id_pattern_parity.py`) prüft, dass `ValidEntityID` (Go) und `VALID_ENTITY_ID_RE`
   (Python) für dieselbe Menge an Eingaben (gültig, Traversal, Umlaut, führender Punkt,
   Leerstring) identisch entscheiden.

### Warum die im Issue vorgeschlagene ASCII-Whitelist verworfen wurde

Das Issue verlangt ein Pendant zu `VALID_USER_ID_RE` (`^[a-zA-Z0-9_-]+$`) auch für Entitäts-IDs.
Für Nutzer-Kennungen war das korrekt (Scheibe 1), für Entitäts-IDs bricht es Produktivdaten: im
Bestand von `/var/lib/gregor/users/henning/locations/` liegen aktive Orte mit Diakritika
(`hochfügen.json`, `mühlbach.json`, `pollença.json`,
`serfaus-schöngamp-berg.json`, `übergangsjoch-zillertal-arena.json`) — referenziert u. a. in
`alert_state/zillertal:hochfügen.json`. Der Weg zu ihnen ist lückenlos belegt:
`frontend/src/routes/locations/+page.svelte:49,71` ruft Bearbeiten/Löschen mit der
Original-ID vom Datenträger auf, die Slug-Bildung im Frontend
(`LocationForm.svelte:22`, `/[^a-z0-9äöüß]+/g`) erhält Umlaute **absichtlich**. Eine
ASCII-Whitelist im Store-Join würde diese Orte unerreichbar machen und jeden neuen Ort mit
deutschem Namen serverseitig mit 400 abweisen. Der Ausbruch entsteht bei Entitäts-IDs
ausschließlich über einen Pfad-Trenner im Wert (verifiziert über alle
`filepath.Join`-Stellen: jede Methode joint `id+".json"`, nie einen rohen
Verzeichnis-Join). Die richtige Regel ist deshalb eine Pfadsegment-Prüfung, keine
Zeichen-Whitelist.

## Expected Behavior

- **Input:** Client-gesetzte Entitäts-ID im Request-Body (`POST /api/trips`,
  `POST /api/locations`) oder im URL-Pfad-Parameter (`PUT`/`PATCH`/`DELETE`/`GET` auf `/{id}` für
  Trips, Orte, Compare-Presets) der jeweils authentifizierten, user-scoped Route.
- **Output:** Für eine Kennung, die `ValidEntityID` verletzt, antwortet jede betroffene Route mit
  **400** im bestehenden `validation_error`-Format. Für eine gültige Kennung — inklusive Umlauten
  und anderen Unicode-Buchstaben — ändert sich nichts am bestehenden Verhalten.
- **Side effects:** Bei ungültiger Kennung entsteht/verändert/verschwindet **keine** Datei
  außerhalb des Verzeichnisses des aufrufenden Nutzers — weder über den Handler-Pfad noch über
  einen direkten Store-Aufruf unter Umgehung des Handlers.

## Acceptance Criteria

> **Zur Ausbruchs-Kennung — nicht „vereinfachen":** Die Entitäts-Pfade sind
> `data/users/<uid>/briefings/<id>.json` bzw. `.../locations/<id>.json`, also **zwei** Ebenen unter
> dem Nutzerverzeichnis. Nur `../../<fremder-nutzer>/user` erreicht wirklich die `user.json` eines
> fremden Kontos; ein einfaches `../<fremder-nutzer>/user` landet im **eigenen** Verzeichnis und
> würde einen Test erzeugen, der auch ohne den Fix grün ist. Die Tests müssen vorher belegen, dass
> die gewählte Kennung ohne Guard tatsächlich in fremdem Gebiet landet (Positivkontrolle).

> **Nachtrag aus der RED-Phase (2026-09-06) — gemessen, nicht angenommen:** Nicht jedes AC
> reproduziert einen offenen Bug. Die Messung am unveränderten Produktivcode ergab:
>
> - **Reproduzieren einen offenen Bug:** AC-1, AC-2, AC-7, AC-8. Die Kennung kommt hier aus dem
>   **Request-Body** bzw. über einen **direkten Store-Aufruf** — kein Routing dazwischen, das
>   filtern könnte. `POST /api/trips` mit `{"id":"../../<opfer>/user"}` überschreibt die
>   `user.json` des fremden Kontos nachweislich; `DeleteTrip` löscht sie.
> - **Nageln einen heute vom Router getragenen Schutz fest (Regressionswächter):** AC-9 und AC-11.
>   Eine Kennung mit echtem Trenner erreicht die Handler der Pfad-Parameter-Routen nicht: chi
>   matcht das Ein-Segment-Muster nicht mehr (404 **vom Router**), und prozent-kodierte Trenner
>   (`%2F`, `%2e%2e%2f`) dekodiert chi nicht — `chi.URLParam` liefert den Wert weiterhin kodiert,
>   sodass nie ein echter Trenner in `filepath.Join` ankommt. Starlette löst Dot-Segmente bereits
>   vor dem Routing auf.
> - **Vereinheitlichen den Statuscode, sind aber keine Sicherheits-ACs:** AC-3, AC-4, AC-5. Ein
>   ungültiges, aber trennerfreies Segment wie `.` erreicht den Handler sehr wohl und führt heute
>   zu 404/204/409 statt zu 400. Gefährlich ist das nicht (`.` + `.json` ergibt `..json`, ein
>   harmloser Dateiname im eigenen Verzeichnis).
>
> **Der Guard gehört trotzdem an alle diese Stellen.** Der heutige Schutz der Pfad-Parameter-Routen
> ist eine Eigenschaft des Routers, keine Zusicherung dieses Systems: ein Router-Wechsel, ein
> zugeschaltetes `chimw.CleanPath` oder ein neuer nicht-HTTP-Aufrufer hebt ihn auf, ohne dass ein
> Test anschlägt. Die ACs 9 und 11 sind genau deshalb als Wächter formuliert — sie halten fest,
> was heute gilt, damit ein späterer Wegfall auffällt.

- **AC-1:** Given ein angemeldeter Nutzer und die Kennung eines zweiten, real angelegten Nutzers /
  When `POST /api/trips` mit `{"id":"../../<zweiter-nutzer>/user"}` aufgerufen wird / Then antwortet
  die Route mit 400, und die `user.json` des zweiten Nutzers ist danach byte-identisch (Inhalt und
  Änderungszeit unverändert) zum Stand vor dem Aufruf.
  - Test: `internal/handler/entity_traversal_test.go`, Inhalt/`mtime` von Bobs `user.json` vor dem
    Aufruf sichern, `POST /api/trips` mit der Ausbruchs-ID senden, danach erneut lesen und
    vergleichen.

- **AC-2:** Given dieselbe Ausgangslage / When `POST /api/locations` mit
  `{"id":"../../<zweiter-nutzer>/user"}` aufgerufen wird / Then antwortet die Route mit 400, und die
  `user.json` des zweiten Nutzers bleibt byte-identisch unverändert.
  - Test: analog zu AC-1, `POST /api/locations` statt `POST /api/trips`.

- **AC-3:** Given ein angemeldeter Nutzer mit eigenem Trip / When `PUT`, `PATCH` und `DELETE
  /api/trips/{id}` jeweils mit einer Ausbruchs-ID (`../../<zweiter-nutzer>/user`) als Pfad-Parameter
  aufgerufen werden / Then antwortet jeder der drei Aufrufe mit 400, und nichts außerhalb des
  Verzeichnisses des aufrufenden Nutzers wird berührt.
  - Test: `internal/handler/entity_traversal_test.go`, drei Aufrufe (PUT/PATCH/DELETE) mit der
    Ausbruchs-ID im Pfad, Statuscode prüfen, Bobs `user.json` vor/nach vergleichen.

- **AC-4:** Given dieselbe Ausgangslage / When `PUT`, `PATCH` und `DELETE /api/locations/{id}`
  jeweils mit derselben Ausbruchs-ID aufgerufen werden / Then antwortet jeder Aufruf mit 400, und
  nichts außerhalb des eigenen Nutzerverzeichnisses wird berührt.
  - Test: analog zu AC-3, `/api/locations/{id}` statt `/api/trips/{id}`.

- **AC-5:** Given ein angemeldeter Nutzer / When `PUT`, `PATCH` und `DELETE
  /api/compare/presets/{id}` jeweils mit derselben Ausbruchs-ID aufgerufen werden / Then antwortet
  jeder Aufruf mit 400, und nichts außerhalb des eigenen Nutzerverzeichnisses wird berührt.
  - Test: analog zu AC-3, `/api/compare/presets/{id}`.

- **AC-6:** Given ein real angelegter Ort mit Umlaut in der Kennung (`hochfügen`) / When er über
  `GET`, `PUT` und `DELETE /api/locations/hochfügen` aufgerufen wird / Then bleibt der Ort über
  alle drei Operationen normal lesbar, änderbar und löschbar (Positivkontrolle) — genau das
  unterscheidet die Segment-Prüfung von der verworfenen ASCII-Whitelist.
  - Test: `internal/handler/entity_traversal_test.go`, Test-Ort mit der Kennung `hochfügen`
    anlegen, nacheinander `GET`, `PUT` (Änderung) und `DELETE` aufrufen, jeweils 200 erwarten und
    den geänderten/gelöschten Zustand verifizieren.

- **AC-7:** Given zwei real angelegte Nutzer A und B / When Nutzer A mit einer beliebigen der in
  dieser Spec geprüften Ausbruchs-Kennungen gegen Trip-, Location- oder Compare-Preset-Routen
  agiert / Then kann A zu keinem Zeitpunkt eine Datei im Verzeichnis von B erzeugen, ändern, lesen
  oder löschen — der Zwei-Nutzer-Nachweis nach ADR-0003.
  - Test: `internal/handler/entity_traversal_test.go`, Nutzer `alice` und `bob` anlegen, alle in
    AC-1 bis AC-5 verwendeten Aufrufe unter Alices Session ausführen, nach jedem Aufruf Bobs
    kompletten Nutzerordner (rekursiver Verzeichnis-Diff) unverändert vorfinden.

- **AC-8:** Given eine Ausbruchs-Kennung wie `../../bob/user` / When `Store.SaveTrip`, `Store.LoadTrip`
  oder `Store.DeleteTrip` direkt — unter Umgehung des HTTP-Handlers — mit dieser Kennung
  aufgerufen werden / Then liefert jeder Aufruf einen Fehler, und es entsteht/verändert/verschwindet
  keine Datei außerhalb des Verzeichnisses der aufrufenden Nutzer-ID — der Guard sitzt im Store,
  nicht nur im Handler.
  - Test: `internal/store/entity_id_test.go`, drei direkte Store-Aufrufe mit `"../../bob/user"` als
    Trip-ID; `err != nil` prüfen und Bobs realen Nutzerordner unverändert vorfinden.

- **AC-9:** Given ein Trip eines fremden Nutzers und eine Ausbruchs-Trip-ID / When
  `GET /api/preview/{trip_id}/email`, `.../sms`, `.../telegram` sowie
  `POST /api/trips/{trip_id}/alert-preview` jeweils mit der Ausbruchs-ID aufgerufen werden / Then
  weist jede der vier Routen die Anfrage ab, und keine liefert Inhalt des fremden Trips zurück.
  - Test: Neuer Test gegen den laufenden Python-Kern (nicht als Unit-Test der internen Funktion,
    sondern über den tatsächlichen HTTP-Draht), vier Aufrufe mit einer auf einen fremden
    Nutzerordner zielenden Trip-ID, Statuscode und Response-Body auf Abwesenheit fremden
    Trip-Inhalts prüfen.

- **AC-10:** Given der neue Python↔Go-Paritätstest für Entitäts-IDs / When er mit derselben Menge
  an Eingaben (gültig, Traversal-Segmente, Umlaute, führender Punkt, Leerstring) gegen
  `store.ValidEntityID` (Go) und `VALID_ENTITY_ID_RE` (Python) läuft / Then liefern beide
  Implementierungen für jede Eingabe dasselbe Ergebnis.
  - Test: `tests/unit/test_entity_id_pattern_parity.py` (neu, Bauart wie
    `test_user_id_pattern_parity.py`).

- **AC-11:** Given eine Ausbruchs-Kennung mit URL-kodiertem Trenner (`%2F` bzw. `%2e%2e%2f`) im
  ID-Pfadsegment / When sie über die volle Kette chi-Router → Go-Proxy → Starlette bis zu einer
  Trip- oder Location-Route läuft / Then erfolgt kein Zugriff auf eine Datei außerhalb des
  Verzeichnisses des aufrufenden Nutzers, unabhängig davon, ob der Trenner dekodiert ankommt oder
  bereits vorher als ungültiges Segment abgewiesen wird.
  - Test: `internal/handler/entity_traversal_test.go`, Aufruf mit URL-kodiertem Pfadsegment gegen
    eine Trip- und eine Location-Route; ob der Trenner überhaupt dekodiert durchkommt, wird in der
    RED-Phase empirisch gemessen (offene Frage der Analyse), das AC deckt in jedem Fall das
    beobachtbare Ergebnis „kein fremder Dateizugriff" ab.

## Known Limitations

- **Symlinks im Datenverzeichnis** sind nicht Gegenstand dieser Spec — durch ID-Validierung nicht
  schließbar, außerhalb dieser Angriffsklasse.
- **Alarm-Zustandsschlüssel mit Doppelpunkt** (`zillertal:hochfügen`, `src/services/alert_state.py`)
  laufen nicht über die hier geprüften Go-Store-Pfade und bleiben unangetastet.
- **GPX-Dateinamen** sind bereits über `Path(filename).name` auf den Basename reduziert
  (`src/services/gpx_processing.py:66-67`, Fix zu #1352) — kein offener Vektor, nicht Teil dieser
  Spec.
- Migrationen (`migrate_1257.go:39`, `migrate_1258.go:85,124`) rekonstruieren IDs aus dem
  Verzeichnislisting (reine ASCII-Hex) und rufen den neuen Guard nicht auf — kein Risiko im
  Bestand, aber ein pathologischer Dateiname wie `..json` würde bei künftigen Migrationen
  übersprungen statt migriert.
- Vollscans (`LoadTrips`, `LoadLocations`, `LoadComparePresets`) rekonstruieren keine
  IDs aus Nutzereingaben und rufen den Guard nicht auf — kein Risiko, keine Deckung nötig.

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** ADR-0003 (Konsequente Mandantentrennung, kein `"default"`-Fallback)
- **Rationale:** Diese Spec trifft keine neue Grundsatzentscheidung, sondern setzt die bereits
  getroffene Isolation pro Nutzer (`data/users/<user_id>/`, Pflicht zum Zwei-Nutzer-Test) für die
  Entitäts-Achse durch, die Scheibe 1 bewusst zurückstellte. Ein eigenes ADR ist nicht nötig, weil
  weder eine neue Alternative abgewogen noch eine bestehende Entscheidung geändert wird.

## Changelog

- 2026-09-06: Initial spec (Issue #2140, Scheibe 2 von 2)
