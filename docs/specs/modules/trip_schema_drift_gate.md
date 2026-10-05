---
entity_id: trip_schema_drift_gate
type: module
created: 2026-10-05
updated: 2026-10-05
status: draft
version: "1.0"
tags: [gate, trip, schema, drift, python, go, "#2058", "#2260"]
---

# Trip-Schema-Drift-Gate (Python ↔ Go)

## Approval

- [ ] Approved

## Purpose

Ein Test-Paar (Python + Go) verhindert, dass ein Trip-, Etappen- oder Wegpunkt-Schlüssel nur in einem der beiden Modelle existiert. Hintergrund (#2058): Der Merge beim Speichern ersetzt Listen als Ganzes; ein nur einseitig bekanntes Wegpunkt-Feld ginge beim Speichern still verloren. Entscheidung (Tech-Lead 2026-09-09): **Gate statt schlüsselbasiertem Listen-Merge** — kein Verhaltenswechsel beim Speichern.

## Source

- **Neu:** `tests/fixtures/trip_schema_full.json` (gemeinsame, voll besetzte Fixture)
- **Neu:** `tests/test_trip_schema_drift.py` (Python-Seite)
- **Neu:** `internal/model/trip_schema_drift_test.go` (Go-Seite)
- **Ändern:** `internal/model/trip.go` (Waypoint + `suggestion_reason`, omitempty)
- **Ändern:** `docs/reference/gates_und_ratschen.md` (Gate + Prüfdatum 2027-01-03)
- **Unverändert:** `_deep_merge_preserve_unknown` (`src/app/loader.py:135`)

Schicht: Go-API (`internal/model`) und Python-Core (`src/app/loader.py`, nur gelesen); sonst Tests.

## Estimated Scope

- **LoC:** ca. +200 (Tests + 1 Go-Zeile; Fixture/Doku zählen nicht)
- **Files:** 5
- **Effort:** low–medium

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `src/app/loader.py` `_parse_trip` / `_trip_to_dict` | Python | Lesen/Schreiben der Python-Seite |
| `internal/model/trip.go` | Go | Go-Modell (json-Tags) |
| `tests/test_mail_recipient_parity.py`, `internal/mail/recipient_parity_test.go` | Vorbild | Gemeinsame Fixture, Pfadauflösung relativ zur Testdatei bzw. `go.mod`-Aufstieg |

## Implementation Details

1. **Fixture** `trip_schema_full.json`: ein Trip mit **allen** optionalen Feldern auf Trip-, Etappen- und Wegpunkt-Ebene besetzt (Python emittiert bedingt, Go lässt leere `omitempty` weg — nur ein voll besetzter Trip macht alle Schlüssel sichtbar).
2. **Python-Test:** Fixture laden (Pfad relativ zur Testdatei) → `_parse_trip` → `_trip_to_dict`; Schlüsselmengen von Trip, Etappe und Wegpunkt mit denen der Fixture vergleichen. Abweichung in beide Richtungen ⇒ rot, mit Ausgabe der betroffenen Schlüssel und der Ebene.
3. **Go-Test:** dieselbe Fixture (Pfad per `go.mod`-Aufstieg, `-trimpath`-fest) → `json.Unmarshal` in `model.Trip` → `json.Marshal`; Schlüsselmengen auf denselben drei Ebenen mit der Fixture vergleichen, beide Richtungen.
4. **Benannte Allowlist** (identisch in beiden Tests, je Eintrag mit Begründung, keine Pauschal-Ausnahme):
   - `send_premium_sms` (Trip): Go-only, in Go aus `report_config.send_premium_sms` abgeleitet.
   - `trip` (Trip): Python-Legacy-Wrapper in `KNOWN_TOP_LEVEL`, wird nie geschrieben.
   - Ein Allowlist-Eintrag, der in keinem Modell mehr vorkommt, macht den Test rot (keine Karteileichen).
5. **Echte Drift im selben Ticket schließen:** Wegpunkt-Feld `suggestion_reason` existiert nur in Python (`trip.py:81`, `loader.py:499,1673`) — Go ergänzt `SuggestionReason string \`json:"suggestion_reason,omitempty"\`` am Waypoint (additiv, ADR-0077). Weitere Treffer beim Fixture-Bau (Trip-Ebene: `corridors`, `alert_*`, `official_*` u. a.) werden ebenfalls im selben Ticket geklärt, nicht vertagt.
6. **Doku:** Eintrag im Gates-Dokument mit Prüfdatum 2027-01-03 (Regel-Budget) und Hinweis „neues Trip-/Etappen-/Wegpunkt-Feld ⇒ in beiden Modellen + Fixture anlegen".

## Expected Behavior

- **Input:** gemeinsame Fixture, beide Modelle.
- **Output:** grün, wenn Schlüsselmenge je Ebene in Python, Go und Fixture übereinstimmt (abzüglich Allowlist); sonst rot mit Schlüsselnamen.
- **Side effects:** keine Laufzeit-/Speicherwirkung. Einzige Verhaltensänderung: Ein Go-Editor-Save verwirft `suggestion_reason` nicht mehr still.

## Acceptance Criteria

- **AC-1:** Given die gemeinsame voll besetzte Fixture, When der Python-Test sie über `_parse_trip` und `_trip_to_dict` zurückschreibt, Then stimmen die Schlüsselmengen von Trip, Etappe und Wegpunkt mit der Fixture überein (abzüglich Allowlist).
  - Test: `tests/test_trip_schema_drift.py` — Roundtrip über echten Lade-/Schreibpfad, kein Mock.

- **AC-2:** Given dieselbe Fixture, When der Go-Test sie in `model.Trip` entpackt und wieder serialisiert, Then stimmen die Schlüsselmengen aller drei Ebenen mit der Fixture überein (abzüglich Allowlist).
  - Test: `internal/model/trip_schema_drift_test.go` — echter Unmarshal/Marshal-Roundtrip.

- **AC-3:** Given ein neues Wegpunkt-, Etappen- oder Trip-Feld, das nur in einem der beiden Modelle angelegt wird, When die Tests laufen, Then wird mindestens der Test der anderen Seite rot und nennt Ebene und Schlüssel (beide Richtungen).
  - Test: Mutations-Gegenprobe im Adversary (Feld nur in Python; Feld nur in Go) — beide müssen rot werden.

- **AC-4:** Given ein Wegpunkt mit `suggestion_reason`, When ein Go-Editor-Save den Trip liest und schreibt, Then bleibt `suggestion_reason` erhalten.
  - Test: Go-Roundtrip im Drift-Test mit besetztem `suggestion_reason`; rot vor, grün nach der Go-Ergänzung.

- **AC-5:** Given die Allowlist (`send_premium_sms`, `trip`), When ein Eintrag davon in keinem Modell mehr existiert oder ein nicht gelisteter einseitiger Schlüssel auftaucht, Then ist der Test rot.
  - Test: beide Tests prüfen die Allowlist gegen die tatsächlichen Schlüssel.

- **AC-6:** Given der Speicherpfad, When das Ticket umgesetzt ist, Then ist `_deep_merge_preserve_unknown` unverändert und Listen werden weiterhin als Ganzes ersetzt.
  - Test: bestehende Merge-Tests (`update_trip_handler_merge`) bleiben unverändert grün.

- **AC-7:** Given `gates_und_ratschen.md`, When das Gate eingeführt ist, Then steht dort das Gate mit Prüfdatum 2027-01-03.
  - Test: `# doc-compliance-test` — Eintrag mit Prüfdatum vorhanden.

## Test Plan

| Test | Datei | Beweist |
|------|-------|---------|
| Python-Roundtrip-Schlüsselabgleich | `tests/test_trip_schema_drift.py` | AC-1, AC-3, AC-5 |
| Go-Roundtrip-Schlüsselabgleich inkl. `suggestion_reason` | `internal/model/trip_schema_drift_test.go` | AC-2, AC-3, AC-4, AC-5 |
| Bestehende Merge-Tests unverändert grün | `update_trip_handler_merge` | AC-6 |
| Gates-Doku-Eintrag (`# doc-compliance-test`) | `tests/test_trip_schema_drift.py` | AC-7 |

Alle Tests laufen offline (`--disable-socket`), ohne Mocks. Mutations-Gegenprobe (Feld nur in Python / nur in Go) im Adversary per String-Ersetzung mit externer Sicherungskopie.

## Known Limitations

- Geprüft werden nur Schlüsselnamen auf Trip-/Etappen-/Wegpunkt-Ebene, keine Wertetypen und keine tieferen Ebenen (z. B. AlertRule `pair_id`/`delta_window`, nur Go — nicht Gegenstand).
- Die Fixture muss bei neuen Feldern von Hand mitwachsen; ein vergessenes Feld macht den Test **nicht** rot, wenn es in keinem Modell steht — abgefangen wird nur der einseitige Fall.
- Das Gate schützt vor dem Entstehen neuer Drift, nicht vor beliebigen Listen-Ersetzungs-Effekten (bewusst, siehe Entscheid).

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** keine neue; berührt ADR-0031 (Go-Store Schreib-Autorität), ADR-0077 (additive Schemaerweiterung)
- **Rationale:** Schlüsselbasierter Listen-Merge würde absichtlich gelöschte Felder wiederbeleben; ein Gate fängt die Ursache (einseitiges Feld) ohne Verhaltenswechsel.

## Changelog

- 2026-10-05: Initial spec created (#2058)
