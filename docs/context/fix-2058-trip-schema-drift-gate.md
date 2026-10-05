# Context: fix-2058-trip-schema-drift-gate

## Request Summary
Drift-Gate (#2058, Epic #2260): Ein Test, der Trip-, Etappen- und Wegpunkt-Schlüssel zwischen Python-Core und Go-Modell abgleicht und rot wird, sobald ein Schlüssel nur auf einer Seite existiert. Tech-Lead-Entscheid 2026-09-09 (Kommentar am Issue): **Gate statt schlüsselbasiertem Listen-Merge**. `_deep_merge_preserve_unknown` bleibt unverändert; Listen bleiben „ganz ersetzt“. Kein Verhaltenswechsel beim Speichern.

## Related Files
| File | Relevanz |
|------|----------|
| `internal/model/trip.go:82-192` | Go-Structs Waypoint/Stage/Trip mit json-Tags (Quelle der Go-Schlüsselmenge) |
| `src/app/trip.py:62,97,176` | Python-Dataclasses Waypoint/Stage/Trip |
| `src/app/loader.py:475-740` | `_parse_trip` (Lesen), `KNOWN_TOP_LEVEL` :670-696 |
| `src/app/loader.py:1649-1920` | `_trip_to_dict` (Schreiben; bedingte Emission je Feld) |
| `src/app/loader.py:135` | `_deep_merge_preserve_unknown` (bleibt unverändert) |
| `internal/store/trip_distance_roundtrip_test.go` | Vorbild: Roundtrip-Absicherung aus #2036 |
| `internal/mail/recipient_parity_test.go:24ff` | Vorbild Go-Fixture-Pfad (go.mod-Aufstieg, `-trimpath`-fest) |
| `tests/test_mail_recipient_parity.py:49-50` | Vorbild Python-Fixture-Pfad (relativ zur Testdatei) |
| `tests/fixtures/mail_recipient_parity/faelle.json` | Vorbild: dieselbe JSON-Fixture von Go und Python gelesen |

## Existing Patterns
- Paritätstest mit gemeinsamer Fixture, von beiden Seiten gelesen (mail_recipient_parity).
- Python-Test löst Fixture relativ zur eigenen Datei auf (CLAUDE.md-Pflicht, Worktree-Falle).
- Go-Fixture-Pfad per `os.Getwd()`-Aufstieg bis `go.mod` (neueres Muster), nicht `runtime.Caller`.
- Neue pytest-Dateien in `tests/` laufen automatisch in der CI (Ratsche `.github/ci_tdd_excludes.txt` betrifft nur `tests/tdd/`). Neue `*_test.go` unter `internal/` laufen automatisch. Test muss offline laufen (`--disable-socket`).

## Erster Abgleich (Explore-Agent, per grep nachgeprüft: suggestion_reason)
Stage: deckungsgleich (id, name, date, waypoints, start_time).
Waypoint: Python-only **`suggestion_reason`** (`trip.py:81`, `loader.py:499,1673`, erzeugt in `src/services/route_analyzer.py:44`). Go kennt es nicht (nur Kommentar `trip.go:98`). Echte Drift: ein Go-Editor-Save verwirft den Wert still. Historie: #303 führte es ein, #523 (C8 aus #506) entfernte „suggested/waypoint.ai“ aus Frontend/Backend — Python-Reste blieben.
Trip: Go-only **`send_premium_sms`** (`trip.go:182`; in Go aus `report_config.send_premium_sms` abgeleitet, `store/trip.go:65,86-89`); Python-Pseudo-Key `trip` in `KNOWN_TOP_LEVEL` (Legacy-Wrapper, nie emittiert); `extra` ist kein JSON-Key.
Sub-Ebene (nicht Gegenstand, nur Info): AlertRule `pair_id`/`delta_window` nur Go.

## Dependencies
- Upstream: Go-Reflektion über json-Tags; Python `dataclasses.fields` bzw. `_trip_to_dict` mit voll befülltem Trip (bedingte Emission!).
- Downstream: CI-Jobs `test` und `go-test`; jedes künftige neue Trip-/Etappen-/Wegpunkt-Feld muss auf beiden Seiten angelegt werden.

## Existing Specs / ADRs
- `docs/specs/bugfix/update_trip_handler_merge.md` (RMW-Kontrakt, bleibt unberührt)
- ADR-0031 (Go-Store einzige Schreib-Autorität, Python liest), ADR-0023, ADR-0077 (additive Schemaerweiterung)

## Risks & Considerations
- **Neuer Test wäre beim Einführen sofort rot** (suggestion_reason, send_premium_sms). Befunde im selben Ticket klären, keine befristete Ausnahme (PO-Regel). Für `suggestion_reason`: Entscheidung nötig, ob Go das Feld bekommt oder Python es nach #523 entfernt — vorher prüfen, ob Produktivdaten es enthalten (im Worktree liegen keine Nutzerdaten; `data/users` nicht greifbar).
- `send_premium_sms` und `trip` sind begründete, dauerhafte Ausnahmen (abgeleitet bzw. Legacy) — als **benannte** Allowlist mit Begründung je Eintrag im Test, nicht als Pauschal-Ausnahme.
- Python emittiert Felder bedingt: Gate muss einen voll besetzten Trip verwenden, sonst sieht es Felder nicht.
- Go lässt leere omitempty-Felder weg: ebenfalls voll besetzte Fixture nötig.
- Mutations-Gegenprobe: neues Feld nur in einem Modell anlegen muss den Test rot machen (beide Richtungen).
- Regel-Budget: neues Gate ⇒ Prüfdatum +90 Tage (2027-01-03) in `docs/reference/gates_und_ratschen.md`.

## Analysis

### Type
Bug (Datenverlust-Risiko, Vorsorge) — als Vertrags-/Drift-Gate umgesetzt, kein Verhaltenswechsel beim Speichern.

### Affected Files (with changes)
| File | Change Type | Description |
|------|-------------|-------------|
| `tests/fixtures/trip_schema_full.json` | CREATE | Voll besetzter Trip (alle optionalen Felder, inkl. Etappe/Wegpunkt), von beiden Seiten gelesen |
| `tests/test_trip_schema_drift.py` | CREATE | Python liest Fixture → `_parse_trip` → `_trip_to_dict`; Schlüsselmengen rekursiv (Trip/Etappe/Wegpunkt) gegen Fixture; Allowlist mit Begründung |
| `internal/model/trip_schema_drift_test.go` | CREATE | Go liest dieselbe Fixture → Unmarshal → Marshal; Schlüsselmengen gegen Fixture; gleiche Allowlist |
| `internal/model/trip.go` | MODIFY | Waypoint bekommt `suggestion_reason` (omitempty), additiv nach ADR-0077 |
| `docs/reference/gates_und_ratschen.md` | MODIFY | Neues Gate + Prüfdatum 2027-01-03 (Regel-Budget) |

### Scope Assessment
- Files: 5 (2 Tests, 1 Fixture, 1 Go-Zeile, 1 Doku)
- Estimated LoC: ca. +200 / -0 (Doku und Fixture zählen nicht)
- Risk Level: LOW (Test-only plus ein additives omitempty-Feld; kein Eingriff in `_deep_merge_preserve_unknown`)

### Technical Approach
Wie im Tech-Lead-Entscheid: Gate statt Listen-Merge. Beide Tests lesen dieselbe Fixture (Python relativ zur Testdatei, Go per `go.mod`-Aufstieg), schreiben sie über das eigene Modell zurück und vergleichen die Schlüsselmengen rekursiv mit der Fixture. Ein Feld nur auf einer Seite fällt in einer der beiden Ampeln (`test` / `go-test`) durch.

Entscheidung `suggestion_reason` (Analyse-Empfehlung): **Go-Feld ergänzen**, nicht Python entfernen. Gründe: Python erzeugt den Wert noch aktiv (`route_analyzer.py:44`, Tests in `tests/tdd/test_issue_303…`); Entfernen wäre Verhaltensänderung und größerer Eingriff. Ergänzen ist additiv, schließt die echte Drift (Go-Save verwirft Wert sonst still) und braucht keine befristete Ausnahme (PO-Regel).

Benannte, dauerhafte Allowlist (je Eintrag begründet): `send_premium_sms` (Go-only, abgeleitet aus `report_config`), `trip` (Python-Legacy-Wrapper in `KNOWN_TOP_LEVEL`, nie emittiert). `extra` ist kein JSON-Key.

### Dependencies
CI-Jobs `test` + `go-test`; künftige Trip-/Etappen-/Wegpunkt-Felder müssen auf beiden Seiten angelegt werden. Vorbild: `mail_recipient_parity`. Hinweis: `tests/tdd/` ist nicht Ziel (Ratsche); neue Datei in `tests/`.

### Open Questions
- [ ] Trip-Ebene hat viele Go-Felder (z. B. `corridors`, `alert_*`, `official_*`): Beim Fixture-Bau prüfen, ob Python sie alle emittiert — Treffer sind weitere Drift-Befunde, im selben Ticket klären.
- [ ] Mutations-Gegenprobe in beide Richtungen (Feld nur in Python / nur in Go) ist Pflicht im Adversary.
