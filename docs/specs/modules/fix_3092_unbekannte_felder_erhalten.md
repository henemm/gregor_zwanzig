---
entity_id: fix_3092_unbekannte_felder_erhalten
type: bugfix
created: 2026-11-27
updated: 2026-11-27
status: draft
version: "1.0"
workflow: fix-3092-put-unbekannte-felder
tags: [go, store, datenverlust, adr-0101, trip, ortsvergleich]
---

# Go-Speichern bewahrt unbekannte Top-Level-Felder (Trip + Ortsvergleich)

## Approval

- [ ] Approved

## Purpose

Beim Speichern eines Trips oder Orts-Vergleichs ersetzt die Go-API die Datei komplett aus dem Go-Modell. Top-Level-Felder, die das Modell nicht kennt, gehen dabei verloren (Issue #3092, Verstoss gegen ADR-0101 "Read-Modify-Write mit Merge, niemals Replace"). Der Fix baut an den beiden Store-Schreibstellen einen Roh-Merge ein, sodass alle Go-Schreibwege unbekannte Felder erhalten.

## Source

- **File:** `internal/store/trip.go`, `internal/store/compare_preset.go`, `internal/store/user.go`
- **Identifier:** `func (s *Store) SaveTrip`, `func (s *Store) SaveComparePreset`, `userJSONKeys` (wird zu generischem `jsonKeysOf` verallgemeinert)

Schicht: Go-API (`internal/store/`). Python-Core und Frontend sind nicht betroffen. Das Modell (`internal/model`) bleibt unveraendert.

Querschnitts-Pruefpunkte:
- **Trip/Ortsvergleich-Teilung:** Beide Pendants nutzen denselben generischen Helper (kein doppelter Code).
- **Mandantentrennung:** Daten pro Nutzer unter `data/users/<user_id>/`; Test mit zwei verschiedenen Nutzern.
- **Kanaele:** Kein Briefing- oder Alarm-Inhalt betroffen; kein Kanal-Effekt.

## Scope

- **LoC:** ~250 (davon ~60 Produktivcode, Rest Tests)
- **Files:** 5
- **Effort:** low

### Affected Files

| Datei | Change | Zweck |
|---|---|---|
| `internal/store/user.go` | MODIFY | `userJSONKeys` zu generischem Schlüssel-Helper verallgemeinern (SaveUser-Verhalten unverändert) |
| `internal/store/trip.go` | MODIFY | `SaveTrip`: Roh-Merge vor dem Schreiben |
| `internal/store/compare_preset.go` | MODIFY | `SaveComparePreset`: Roh-Merge vor dem Schreiben |
| `internal/store/unbekannte_felder_3092_test.go` | CREATE | Store-Tests (AC-1..AC-9) |
| `internal/handler/unbekannte_felder_3092_test.go` | CREATE | Handler-Tests PUT/PATCH mit zwei Nutzern |

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `internal/store/user.go` (`saveUserLocked`, `userJSONKeys`) | module | Vorbild des Merge-Musters (#2687); Schluessel-Reflection wird verallgemeinert, SaveUser-Verhalten bleibt gleich |
| `internal/store/pathsafe.go` (`pruefeEntityGroesse`) | function | Groessenpruefung, laeuft kuenftig auf dem gemergten Ergebnis |
| `internal/store/write.go` (`writeFileLogged`) | function | Schreibt die Datei |
| `internal/model` (`Trip`, `ComparePreset`) | module | Quelle der bekannten json-Tags (unveraendert) |
| ADR-0101 | adr | Vorgabe Read-Modify-Write mit Merge |
| ADR-0083 | adr | Gemeinsame Briefing-Sperre mit Python; Merge liest dieselbe Datei unter bestehender Sperre |
| `docs/specs/modules/feat_3277*.md` | spec | Altfelder (z. B. `outlook_enabled`) werden von Go nicht entfernt |

## Implementation Details

Ansatz (Variante A der Analyse): generischer Roh-Merge-Helper am Store-Seam, gemeinsam fuer `SaveTrip` und `SaveComparePreset`.

1. `userJSONKeys()` wird zu `jsonKeysOf(t reflect.Type)` verallgemeinert (json-Tags, Top-Level; eingebettete anonyme Structs werden korrekt aufgeloest). `SaveUser` nutzt den Helper mit `model.User`, Verhalten unveraendert.
2. Neuer Helper (`mergeUnknownTopLevel` o. ae., in `internal/store/user.go` oder neuer Datei `raw_merge.go`): Eingabe sind Zieldatei, Modell als Struct und die bekannten Schluessel.
3. Reihenfolge im Save: Altdatei als `map[string]json.RawMessage` lesen, alle Modell-Schluessel daraus loeschen, Modell-Map darueberlegen, `pruefeEntityGroesse` auf das Ergebnis, schreiben.
4. Fehlende, nicht lesbare oder kein JSON-Objekt enthaltende Altdatei: Modellstand wird geschrieben (Anlegen funktioniert unveraendert).
5. Weil zuerst alle bekannten Schluessel aus der Altdatei geloescht werden, leben geleerte `omitempty`-Felder (z. B. `paused_at`, `archived_at`) nicht wieder auf; nur UNBEKANNTE Schluessel ueberleben.

Abgrenzung: Nur Top-Level. Verschachtelte unbekannte Felder (z. B. in `stages`) sind nicht Gegenstand. Python-Schreibpfad (hat eigenes Deep-Merge) ist nicht im Scope.

## Expected Behavior

- **Input:** Beliebiger Go-Schreibweg ueber `SaveTrip` / `SaveComparePreset` (PUT, State-PATCH, Trip-PATCH, Briefing-PUT, Weather-Config-PUT, Migrationen).
- **Output:** Datei enthaelt Modellstand plus alle dem Modell unbekannten Top-Level-Felder der Altdatei.
- **Side effects:** Keine Modell-, API- oder Antwortaenderung; Dateien koennen kuenftig zusaetzliche unbekannte Schluessel behalten.

## Acceptance Criteria

- **AC-1:** Given ein vorhandener Orts-Vergleich mit einem dem Go-Modell unbekannten Top-Level-Feld auf der Platte / When der Nutzer ihn per PUT `/api/compare/presets/{id}` speichert / Then enthaelt die Datei auf der Platte das unbekannte Feld weiterhin unveraendert (Dateiinhalt gelesen, nicht nur die Antwort geprueft).
  - Test: Handler-Test mit echtem Store auf `t.TempDir`; Feld in die Datei schreiben, PUT senden, Datei neu einlesen.

- **AC-2:** Given ein vorhandener Trip mit einem dem Go-Modell unbekannten Top-Level-Feld auf der Platte / When der Nutzer ihn per PUT speichert / Then enthaelt die Trip-Datei auf der Platte das unbekannte Feld weiterhin unveraendert.
  - Test: Handler-Test mit echtem Store; Datei nach PUT neu einlesen.

- **AC-3:** Given ein Orts-Vergleich bzw. ein Trip mit einem unbekannten Top-Level-Feld / When ein anderer Go-Schreibweg ueber denselben Seam speichert (State-PATCH archivieren eines Orts-Vergleichs, Trip-PATCH) / Then bleibt das unbekannte Feld in der Datei erhalten, waehrend die gewollte Aenderung (z. B. archiviert) gespeichert ist.
  - Test: Handler-Tests je Schreibweg; Datei nach dem Aufruf pruefen, Aenderung und unbekanntes Feld gleichzeitig vorhanden.

- **AC-4:** Given eine Datei mit einem bekannten, optionalen Feld (z. B. `paused_at` beim Trip, `archived_at` beim Orts-Vergleich) / When der Request dieses Feld leert bzw. entfernt und gespeichert wird / Then steht das Feld nach dem Speichern NICHT mehr in der Datei, auch nicht mit dem alten Wert aus der Altdatei.
  - Test: Store-Test `SaveTrip` und `SaveComparePreset` mit geleertem omitempty-Feld; Datei einlesen und Schluessel-Abwesenheit pruefen.

- **AC-5:** Given zwei verschiedene Nutzer A und B, bei A traegt die Datei ein unbekanntes Feld / When B speichert (PUT) und danach A speichert / Then behaelt A sein Feld, B's Datei enthaelt kein fremdes Feld und A's Datei wird durch B's Speichern nicht veraendert.
  - Test: Handler-Test mit zwei Nutzern und echten Auth-Kontexten, Ortsvergleich und Trip; beide Dateien einlesen und vergleichen.

- **AC-6:** Given eine fehlende oder kaputte (kein gueltiges JSON-Objekt) Altdatei / When ein Trip oder Orts-Vergleich gespeichert wird / Then gelingt das Speichern ohne Fehler und die Datei enthaelt genau den Modellstand (Anlegen funktioniert unveraendert).
  - Test: Store-Tests fuer neue Datei, leere Datei und Datei mit Muelltext; danach Laden und Vergleich mit dem gespeicherten Modell.

- **AC-7:** Given die bestehende SaveUser-Merge-Testsuite / When die Reflection auf den generischen Helper umgestellt ist / Then sind alle bestehenden SaveUser-Tests (`user_saveuser_merge_test.go`) unveraendert gruen und der Merge-Effekt bei `user.json` ist derselbe.
  - Test: Lauf der bestehenden Testdatei ohne Aenderung an den Erwartungen (Schluessel-Test ggf. nur auf den neuen Funktionsnamen angepasst).

- **AC-8:** Given eine Trip- oder Vergleichsdatei mit einem Altfeld aus #3277 (z. B. `outlook_enabled`) / When Go speichert / Then bleibt das Altfeld in der Datei erhalten (kein Go-Strip, spec-konform zu feat_3277).
  - Test: Store-Test mit `outlook_enabled` in der Altdatei; nach `SaveTrip`/`SaveComparePreset` weiterhin vorhanden.

- **AC-9:** Given ein gemergter Inhalt, der die Entity-Groessengrenze ueberschreitet / When gespeichert wird / Then lehnt `SaveTrip`/`SaveComparePreset` ab wie bisher und die Altdatei bleibt unveraendert (Pruefung laeuft auf dem Ergebnis des Merge).
  - Test: Store-Test mit grossem unbekanntem Feld in der Altdatei; Fehler erwartet, Datei unveraendert.

## Test Plan

### Automated Tests (TDD RED)

- [ ] Test 1: GIVEN Orts-Vergleich mit Feld `zukunftsfeld` auf Platte WHEN PUT ausgefuehrt THEN steht `zukunftsfeld` weiter in der Datei (rot vor dem Fix).
- [ ] Test 2: GIVEN Trip mit `zukunftsfeld` WHEN PUT ausgefuehrt THEN steht das Feld weiter in der Datei.
- [ ] Test 3: GIVEN State-PATCH (archivieren) und Trip-PATCH WHEN ausgefuehrt THEN bleibt `zukunftsfeld`, Aenderung gespeichert.
- [ ] Test 4: GIVEN geleertes `paused_at`/`archived_at` WHEN gespeichert THEN Schluessel nicht mehr vorhanden.
- [ ] Test 5: GIVEN Nutzer A mit Feld und Nutzer B WHEN B speichert THEN A unveraendert und B ohne fremdes Feld.
- [ ] Test 6: GIVEN fehlende/kaputte Altdatei WHEN Save THEN Modellstand ohne Fehler.
- [ ] Test 7: GIVEN `outlook_enabled` in Altdatei WHEN Save THEN Feld bleibt.
- [ ] Test 8: GIVEN bestehende SaveUser-Tests WHEN Suite laeuft THEN gruen.

Alle Tests: Go, ohne Mocks, echter Store auf `t.TempDir()`, Store-Ebene (`internal/store/unbekannte_felder_3092_test.go`) und Handler-Ebene (`internal/handler/unbekannte_felder_3092_test.go`, zwei Nutzer).

## Definition of Done

- [ ] Alle ACs durch Go-Tests ohne Mocks belegt (echter Store auf `t.TempDir`), vorher RED
- [ ] `go test ./internal/...` grün, bestehende SaveUser-/Trip-/Preset-Tests unverändert grün
- [ ] Adversary-Mutationsprobe: Merge entfernt → Tests rot; Schlüssel-Löschung entfernt → AC-4 rot
- [ ] Staging-Verifikation: unbekanntes Feld überlebt echtes Speichern (Datei auf Staging geprüft)
- [ ] Prod-Deploy + Selftest Exit 0

## Known Limitations

- Nur Top-Level-Felder; unbekannte verschachtelte Felder (z. B. in `stages`, `display_config`) werden weiterhin vom Modell als Ganzes geschrieben.
- Python-Schreibpfad (`save_trip`) und Python-Presets bleiben unveraendert.
- Unbekannte Felder bleiben dauerhaft in der Datei, bis ein anderes System sie entfernt.
- Altdatei mit Inhalt `null` unter einer Orts-Vergleich-ID: die vorbestehende Art-Pruefung (#2359, `idBelegtDurchFremdeArt`) wertet sie als Trip und `SaveComparePreset` lehnt mit `ErrKindConflict` ab, bevor der Merge laeuft. Kein Datenverlust, Verhalten unveraendert gegenueber vor #3092; AC-6 fuer `null` ist am Trip belegt.

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** keine
- **Rationale:** Umsetzung der bestehenden Entscheidung ADR-0101 (Read-Modify-Write mit Merge) auf zwei weitere Schreibstellen; keine neue Entscheidungsflaeche.

## Changelog

- 2026-11-27: Initial spec created (Issue #3092)
- 2026-11-27: Umsetzung: Helper in neuer Datei `internal/store/raw_merge.go`; zusaetzlich `internal/store/raw_merge_test.go` (Unit-Test `jsonKeysOf`, Adversary F002) und Anpassung des Bestandstests `internal/store/trip_archive_fields_roundtrip_test.go` an AC-8/ADR-0101 (entfernte Analytics-Altfelder `accuracy_pct`, `headline`, `briefings_count`, `alerts_count` bleiben wie jedes Altfeld in der Datei, das geladene Modell zeigt sie nicht).
