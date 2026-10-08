---
entity_id: fix_2216_ort_loeschen_sperre
type: module
created: 2026-10-08
updated: 2026-10-08
status: draft
version: "1.0"
tags: [locations, compare, delete, 409, versand, bug, epic-2345]
---

# Ort-Löschen-Sperre bei Nutzung in Ortsvergleichen (#2216)

## Approval

- [ ] Approved

## Purpose

Ein Ort, der in einem Ortsvergleich (`ComparePreset.LocationIDs`) steckt, lässt sich heute ohne Warnung
löschen; der Versand scheitert erst später mit einer kryptischen ID-Liste, bei Teilverlust fehlen Orte
still im Briefing. Die Spec sperrt das Löschen mit 409 (Namen der nutzenden Ortsvergleiche) und macht
den Versand bei fehlenden Orten sprechend und sichtbar.

## Source

- **Go-API:** `internal/handler/location.go` (`DeleteLocationHandler`), `internal/store/compare_preset.go` (neue Hilfsfunktion)
- **Python-Core:** `src/services/scheduler_dispatch_service.py` (`send_one_compare_preset`, `send_compare_preset`), `src/services/compare_preview_service.py` (`_resolve_locations`), `api/routers/scheduler.py` (`manual_send_compare_preset`)
- **Frontend:** `frontend/src/routes/locations/+page.svelte`, `frontend/src/routes/compare/[id]/+page.svelte` (`sendMsg`)

## Estimated Scope

- **LoC:** produktiv ~110, Tests ~200
- **Files:** 7 produktiv (3 Go/Frontend-Löschpfad: `compare_preset.go`, `location.go`, `locations/+page.svelte`; 4 Versand: Dispatch-Service, Preview-Service, Scheduler-Router, Hub-Seite) + Tests
- **Effort:** medium

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `Store.WithUser`, `LockLocation` | Go Store | Mandantentrennung (ADR-0003), Ortslock (ADR-0083) |
| `Store.LoadComparePresets` | Go Store | Quelle der Ortsvergleiche (`briefings/*.json`, kind=vergleich) |
| `order_locations_by_ids` | Python | Ortsauflösung; liefert die nicht auflösbaren IDs als Differenz |
| `classifySendResponse` (`sendOutcome.ts`) | Frontend | deutet 409 als „läuft bereits" — deshalb bleibt der Versandgrund 422 |

## Implementation Details

**1. Store** (`compare_preset.go`): `ComparePresetsUsingLocation(locationID string) ([]model.ComparePreset, error)`
auf dem nutzergebundenen Store; filtert `LoadComparePresets()` auf `locationID in LocationIDs`.

**2. Handler** (`DeleteLocationHandler`): Reihenfolge `WithUser` → `rejectInvalidEntityID` → `LockLocation` →
Nutzungsprüfung → `DeleteLocation`. Treffer: 409
`{"error":"location_in_use","compare_presets":[{"id":"…","name":"…"}]}`, Ort bleibt. Kein Treffer: 204 wie bisher.
Fehler der Prüfung: 500 `store_error`, nicht löschen. Der Store ist der aus `s.WithUser(...)` (nie `"default"`).

**3. Frontend Orte-Seite:** Der 409-Zweig im Löschdialog liest `e.body.compare_presets` und zeigt
„Dieser Ort wird noch in diesen Ortsvergleichen verwendet: <Namen>. Entferne ihn dort zuerst." mit Link je
Ortsvergleich auf `/compare/{id}`. Der Ort bleibt in der Liste. Alle anderen Fehler: bisheriger Text.
Es gibt nur diesen einen Aufrufer von `api.del` auf Orte (geprüft).

**4. Versand/Vorschau:**
- Alle Orte nicht auflösbar: bleibt `ValueError` → 422 (nicht 409). Neue Meldung (Dispatch und Preview
  gleich): „Ortsvergleich '<id>' verweist auf gelöschte Orte. Ersetze die Orte im Ortsvergleich." Die ID-Liste
  darf höchstens ergänzend stehen.
- Teilverlust: Versand läuft mit den übrigen Orten weiter. `send_compare_preset` liefert zusätzlich
  `fehlende_orte` (Liste der nicht auflösbaren IDs; leer/fehlend wenn nichts fehlt); `manual_send_compare_preset`
  reicht das Feld durch. Der Scheduler-Lauf schreibt zusätzlich `logger.warning` mit Preset-ID und fehlenden IDs.
  Der Compare-Hub zeigt nach erfolgreichem Test-Versand einen Hinweis (`sendMsg`), dass Orte fehlten.

## Expected Behavior

- **Input:** DELETE `/api/locations/{id}`; POST Versand/Vorschau eines Ortsvergleichs
- **Output:** 409 mit Namen bzw. 204; 422 mit sprechendem Grund bzw. 200 mit `fehlende_orte`
- **Side effects:** keine Schemaänderung, kein Auto-Bereinigen von Bestandsdaten

## Acceptance Criteria

- **AC-1:** Given ein Ort, der in der `LocationIDs` eines Ortsvergleichs desselben Nutzers steht / When der Nutzer DELETE auf diesen Ort sendet / Then antwortet die API mit 409 `location_in_use` samt `compare_presets` (id und name) und der Ort existiert weiterhin.
  - Test: Go-Handlertest, prüft Status, Body und dass die Ortsdatei noch vorhanden ist.

- **AC-2:** Given ein Ort, der in keinem Ortsvergleich des Nutzers steht / When der Nutzer DELETE auf diesen Ort sendet / Then antwortet die API wie bisher mit 204 und der Ort ist gelöscht.
  - Test: Go-Handlertest (Regressionsschutz für den Normalfall).

- **AC-3:** Given Nutzer A hat einen Ortsvergleich mit Ort X und Nutzer B hat einen eigenen Ort mit derselben ID / When Nutzer B seinen Ort löscht / Then erhält B 204, und in einer 409-Antwort an A erscheinen nie Ortsvergleiche von B (und umgekehrt).
  - Test: Go-Handlertest mit zwei Nutzern und zwei Auth-Kontexten.

- **AC-4:** Given ein Ort wird in einem Ortsvergleich verwendet / When der Nutzer ihn auf der Orte-Seite im Löschdialog bestätigt / Then zeigt der Dialog die Namen der nutzenden Ortsvergleiche mit Hinweis, sie dort zuerst zu entfernen, statt „Fehler beim Löschen", und der Ort bleibt in der Liste.
  - Test: Frontend-Test (`node --test`) für die Aufbereitung der 409-Antwort in Text/Links; E2E gegen Staging (Hinweis unten).

- **AC-5:** Given ein Ortsvergleich, dessen Orte alle nicht mehr existieren / When Versand oder Vorschau ausgelöst wird / Then antwortet die API mit 422 (nicht 409) und einer Meldung, dass der Ortsvergleich gelöschte Orte referenziert und die Orte zu ersetzen sind.
  - Test: Python-Test für Versand (`manual_send_compare_preset`, Status 422) und Vorschau, prüft Statuscode und Meldungstext.

- **AC-6:** Given ein Ortsvergleich, bei dem nur ein Teil der Orte fehlt / When der Versand ausgelöst wird / Then läuft er mit den übrigen Orten weiter und das Ergebnis enthält `fehlende_orte` mit genau den nicht auflösbaren IDs; ohne fehlende Orte ist das Feld leer oder fehlt.
  - Test: Python-Test für `send_compare_preset` und `manual_send_compare_preset` (Durchreichen).

- **AC-7:** Given der Teilverlust aus AC-6 tritt im Scheduler-Lauf oder im Hub-Test-Versand auf / When der Versand abgeschlossen ist / Then steht im Scheduler-Log eine Warnung mit Preset-ID und fehlenden IDs, und der Compare-Hub zeigt einen Hinweis auf die fehlenden Orte.
  - Test: Python-Test mit `caplog`; Frontend-Test für die `sendMsg`-Aufbereitung.

## Known Limitations (Nicht-Ziele und Risiken)

- **Keine Mail-Änderung:** Der Hinweis erscheint in Ergebnis, Log und Hub, nicht in der Mail. Mail-Inhalte
  unterliegen Renderer-Commit-Gate und Validator-Pflicht; das wäre eine eigene Scheibe mit eigenem Nachweis.
- **Kein Auto-Bereinigen:** Bereits verwaiste Presets bleiben unverändert (Datenerhalt-Regel); sie bekommen
  nur die klare Meldung aus AC-5/AC-6.
- **Restrisiko Race:** Ortsvergleich-Speichern nimmt den Ortslock nicht. Wird ein Preset mit Ort X gespeichert,
  während X gelöscht wird, kann ein verwaistes Preset entstehen. Bewusst nicht gelöst: ein zusätzlicher Lock im
  Preset-Save berührt die Lock-Reihenfolge nach ADR-0083; das Zeitfenster ist schmal, und der Versandgrund
  (AC-5/AC-6) fängt den Fall sichtbar auf.
- Trips und Gruppen referenzieren keine Ort-IDs und sind nicht betroffen.

## Test-Plan

- Go: `internal/handler/location_write_test.go` (AC-1..3 gegen den Handler, nicht nur den Store) und
  `internal/store/compare_preset_location_usage_test.go` für `ComparePresetsUsingLocation` (Treffer, kein Treffer, Nutzertrennung).
- Python: neue Testdatei nach Verhalten (z. B. `tests/tdd/test_compare_missing_locations.py`), echte
  Preset-/Orte-Dateien in `tmp_path`, kein Mock-Theater.
- Frontend: `node --test` für Aufbereitung der 409-Antwort und des `fehlende_orte`-Hinweises.
- E2E (Live-Schicht, `/e2e-verify`): Staging, Wegwerf-Nutzer: Ort in Ortsvergleich anlegen, Löschen versuchen,
  409-Hinweis sehen, Ort aus Ortsvergleich entfernen, erneut löschen.

## Mutations-Gegenprobe (Hinweise für den Adversary)

Geprüft werden muss an der Stelle, an der die Zusicherung wirkt, nämlich der HTTP-Antwort des Handlers:
- Prüfung nach `DeleteLocation` verschieben oder entfernen: AC-1-Handlertest muss rot werden (Ort weg).
- Store-Hilfsfunktion über den `"default"`-Nutzer statt `WithUser` laufen lassen: AC-3 muss rot werden.
- Filter auf `LocationIDs` entfernen (alle Presets zählen): AC-2 muss rot werden.
- Status 409 durch 422 ersetzen oder `compare_presets` weglassen: AC-1 rot.
- Versand-Grund auf 409 ändern: AC-5-Test muss rot werden.
- `fehlende_orte` im Router nicht durchreichen: AC-6 muss auf Router-Ebene rot werden, nicht nur im Service.

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** keine neue. Berührt: ADR-0003 (Mandantentrennung, `WithUser` Pflicht), ADR-0083 (Schreibsperre
  Gruppen → Ort; unverändert, Prüfung läuft unter dem bereits gehaltenen Ortslock).

## Changelog

- 2026-10-08: Initial spec created (#2216)
