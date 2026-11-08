---
entity_id: fix_2815_delete_fremd_404
type: module
created: 2026-11-07
updated: 2026-11-08
status: implemented
version: "1.0"
tags: [trips, locations, groups, delete, 404, mandantentrennung, bug, epic-2138, go-live-pflicht]
---

# DELETE fremder/unbekannter Trips, Orte, Gruppen antwortet 404 statt 204 (#2815)

## Approval

- [x] Approved

## Purpose

`DELETE /api/trips/{id}` antwortet 204, auch wenn die ID einem anderen Nutzer gehört oder gar nicht existiert
(Nebenbefund aus #2237, Epic #2138). Es ist kein Datenleck (der Store ist per `WithUser` an den Aufrufer
gebunden, gelöscht wird nichts Fremdes), aber uneinheitlich zu Compare-Presets und Metrik-Presets, die 404
liefern. Dieselbe Lücke haben Orte und Gruppen; alle drei werden gemeinsam behoben, damit der Vertrag einheitlich
ist: fremde oder unbekannte Objekte antworten wie nicht vorhandene, nämlich mit 404 `not_found`.

## Source

- **Go-API / Store:** `internal/store/trip.go` (`DeleteTrip`, Z. 331), `internal/store/location.go` (`DeleteLocation`, Z. 114), `internal/store/group.go` (`DeleteGroup` Z. 226, `DeleteGroupLocked` Z. 235), neuer Sentinel `store.ErrNotFound` (neben `ErrInvalidEntityID` in `internal/store/pathsafe.go:54` oder in der bestehenden Fehler-Datei des Stores)
- **Go-API / Handler:** `internal/handler/trip.go` (`DeleteTripHandler`, Z. 669), `internal/handler/location.go` (`DeleteLocationHandler`, Z. 232), `internal/handler/group.go` (`DeleteGroupHandler`, Z. 151)
- **Vorbild:** `internal/handler/compare_preset.go:458` und `internal/handler/metric_preset.go:199` (nicht gefunden: `WriteError(w, r, 404, "not_found", nil)`)
- **Erbt den Fix:** `internal/handler/briefing_subscription.go:159` (`DELETE /api/briefings/{id}?kind=route` delegiert an `DeleteTripHandler`)
- **Frontend:** unverändert (siehe Known Limitations)

Schicht: reine Go-API, kein Python-Core, kein Frontend.

## Scope

Im Scope: die Antwort der drei Lösch-Endpunkte `DELETE /api/trips/{id}` (samt `DELETE /api/briefings/{id}?kind=route`),
`DELETE /api/locations/{id}` und `DELETE /api/groups/{id}` für fremde und unbekannte IDs (404 `not_found`), das
Aufräumen der Trip-Sperrdatei auch im 404-Fall, das Nullen verwaister `group_id`-Verweise auch bei unbekannter
Gruppe, sowie die Vertragszeilen in `docs/reference/api_contract.md`.

Warum Orte und Gruppen mit drin sind, obwohl das Ticket nur Trips nennt: Sie haben denselben Defekt an derselben
Stelle (idempotentes Löschen ohne Existenz-Check), und das Ticket fordert ausdrücklich ein einheitliches Verhalten
„wie bei Presets“. Ein Fix nur für Trips ließe den Vertrag weiter uneinheitlich und erzeugte ein Folge-Ticket für
dieselbe Zeilenart (Epic #2138 wird themenweise abgeschlossen).

Nicht im Scope: Frontend-Behandlung „404 = schon weg“ (siehe Known Limitations), Lösch-Endpunkte von Presets
(liefern bereits 404), Python-Core.

## Definition of Done

- AC-1 bis AC-13 sind durch deterministische Go-Tests (ohne Mocks, Zwei-Nutzer-Tests je Endpunkt) abgedeckt und grün.
- Die vier bewusst umgestellten Bestandstests (siehe Test Plan) erwarten das neue Verhalten und sind grün; alle übrigen Lösch-Tests (204 für eigene Einträge) bleiben grün.
- `docs/reference/api_contract.md` nennt 404 `not_found` für alle drei Endpunkte (AC-14).
- Mutations-Gegenprobe zeigt, dass jede Zusicherung bewacht ist.
- Auf Staging liefert das Löschen einer fremden Trip-ID durch einen zweiten Nutzer 404, der Trip des ersten Nutzers bleibt erhalten.

## Estimated Scope

- **LoC:** produktiv ca. +60/-10, Tests ca. +150
- **Files:** ca. 7 produktiv (Sentinel, `trip.go`, `location.go`, `group.go` im Store; drei Handler) + 5 Testdateien + 1 Doku (`docs/reference/api_contract.md`)
- **Effort:** medium (zentrale Löschpfade, Risiko niedrig bis mittel, da kein Datenleck und Store per `WithUser` gebunden)

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `Store.WithUser`, `requireUser` | Go Store | Mandantentrennung (ADR-0003): nur der Bestand des Aufrufers ist sichtbar |
| `ValidEntityID`, `rejectInvalidEntityID` | Go | Segment-Prüfung vor jedem Pfad-Join (bleibt unverändert, ungültige ID weiter 400) |
| `lockBriefingOr503`, `RemoveBriefingLockFile` | Go | Schreibsperre Trip (#1395) und Aufräumen der Sperrdatei (#2237) |
| `LockLocation`, `LockGroups` | Go Store | Sperren Ort/Gruppe (#2158, ADR-0083, Reihenfolge Gruppe -> Ort) |
| `ComparePresetsUsingLocation` | Go Store | Nutzungsprüfung 409 `location_in_use` (#2216) |
| `WriteError` | Go Handler | einheitliche Fehlerantwort (`code`/`error` = `not_found`) |

## Implementation Details

**Technische Entscheidung (kein PO-Thema):** Sentinel-Fehler `store.ErrNotFound`, die Store-Signaturen bleiben
unverändert (`error`). Verworfen: `(bool, error)` (zusätzlicher Eingriff in alle Aufrufer und die
Signaturtabelle in `user_scope_guard_test.go`, kein Mehrwert) und Handler-Existenzprüfung per `LoadTrip`
(eine kaputte JSON-Datei ergäbe 500 und wäre nie mehr löschbar). Der Sentinel erlaubt die Prüfung unter der
bereits gehaltenen Sperre ohne zusätzlichen Lesezugriff.

**1. Store**
- Neuer Sentinel `var ErrNotFound = errors.New("not found")`.
- `DeleteTrip`: liefert `ErrNotFound`, wenn `<id>.json` fehlt (`os.IsNotExist`) UND im `kind=="vergleich"`-Zweig
  (Compare-Preset unter derselben ID; die Datei bleibt unangetastet, Schutz Adversary F006 bleibt). Eine kaputte,
  nicht als JSON lesbare Datei wird weiterhin gelöscht (fail-open, Rückgabe `nil`).
- `DeleteLocation`: liefert `ErrNotFound`, wenn `locations/<id>.json` fehlt. Eine kaputte Datei wird weiter entfernt.
- `DeleteGroupLocked`: liefert `ErrNotFound`, wenn keine Gruppe entfernt wurde (`len(filtered) == len(groups)`),
  ohne `saveGroups` aufzurufen (kein unnötiges Umschreiben). `DeleteGroup` reicht den Fehler durch.

**2. Handler Trip** (`DeleteTripHandler`): Reihenfolge unverändert `WithUser` -> `rejectInvalidEntityID` ->
`lockBriefingOr503` -> `DeleteTrip`. `errors.Is(err, store.ErrNotFound)` -> 404 `not_found`; andere Fehler -> 500
`store_error`; sonst 204. Das Aufräumen der Sperrdatei (#2237) läuft bei Erfolg UND bei 404 (Flag `cleanup`
statt `deleted`), in derselben Closure erst nach `unlock`. Begründung: `lockBriefingOr503` legt `<id>.json.lock`
an; ohne Aufräumen bei 404 entstünde pro fremder oder zufälliger ID eine verwaiste Sperrdatei (Regression).
`RemoveBriefingLockFile` ist selbst abgesichert (entfernt nur, wenn `<id>.json` fehlt und der flock frei ist);
liegt unter der ID ein Compare-Preset, kehrt es früh zurück, Datei und Sperrdatei bleiben.
`DELETE /api/briefings/{id}?kind=route` erbt dieses Verhalten unverändert.

**3. Handler Ort** (`DeleteLocationHandler`): Reihenfolge `WithUser` -> `rejectInvalidEntityID` -> `LockLocation` ->
`LoadLocation` (`nil, nil` = nicht vorhanden -> 404 `not_found`; ein Ladefehler wegen kaputter Datei fällt durch
und führt weiter) -> Nutzungsprüfung (409 `location_in_use`, unverändert) -> `DeleteLocation` (`ErrNotFound`
als Rückfall -> 404). Der Existenz-Check steht vor der Nutzungsprüfung, damit eine unbekannte ID mit
veraltetem Preset-Verweis 404 statt 409 liefert.

**4. Handler Gruppe** (`DeleteGroupHandler`): Bei `ErrNotFound` aus `DeleteGroupLocked` läuft die
Aufräumschleife der `group_id`-Verweise an Orten trotzdem (Heilpfad nach einem Absturz mitten im Löschen: Gruppe
weg, Verweise noch da), danach 404 `not_found`. Bei Erfolg wie bisher 204.

**5. Doku:** `docs/reference/api_contract.md`: Statuszeile 404 `not_found` für `DELETE /api/trips/{id}`
(inkl. `DELETE /api/briefings/{id}?kind=route`), `DELETE /api/locations/{id}` (Tabelle ab Z. 1344) und
`DELETE /api/groups/{id}` (Endpunkttabelle Z. 256 bzw. eigener Abschnitt).

## Expected Behavior

- **Input:** `DELETE /api/trips/{id}`, `DELETE /api/briefings/{id}?kind=route`, `DELETE /api/locations/{id}`, `DELETE /api/groups/{id}` mit einer ID, die dem Aufrufer nicht gehört, nicht existiert oder existiert.
- **Output:** eigener existierender Eintrag -> 204 (weg); fremde oder unbekannte ID -> 404 `not_found`; Ort in Benutzung -> 409 `location_in_use`; ungültige ID -> 400 wie bisher; Speicherfehler -> 500 `store_error`.
- **Side effects:** Bei 404 wird nichts gelöscht und nichts umgeschrieben (Ausnahme: Gruppen-Heilpfad räumt verwaiste `group_id`-Verweise auf). Keine verwaiste `<id>.json.lock` nach Trip-404. Keine Schemaänderung, keine Datenmigration.

## Acceptance Criteria

- **AC-1:** Given Nutzer A besitzt einen Trip und Nutzer B ist angemeldet / When B `DELETE /api/trips/{id}` mit der Trip-ID von A sendet / Then antwortet die API mit 404 `not_found` und der Trip von A lässt sich danach unverändert laden.
  - Test: Go-Handlertest mit zwei Auth-Kontexten (ADR-0003); prüft Status, Fehlercode und dass A's Datei inhaltlich unverändert vorhanden ist.

- **AC-2:** Given Nutzer A besitzt einen Trip und Nutzer B ist angemeldet / When B `DELETE /api/briefings/{id}?kind=route` mit der Trip-ID von A sendet / Then antwortet die API mit 404 `not_found` und der Trip von A existiert unverändert weiter.
  - Test: Go-Handlertest mit zwei Nutzern über den Briefing-Pfad (erbt den Fix über `DeleteTripHandler`).

- **AC-3:** Given Nutzer A besitzt einen Ort und Nutzer B ist angemeldet / When B `DELETE /api/locations/{id}` mit der Orts-ID von A sendet / Then antwortet die API mit 404 `not_found` und der Ort von A lädt danach unverändert.
  - Test: Go-Handlertest mit zwei Auth-Kontexten; prüft Status, Fehlercode und A's Ortsdatei.

- **AC-4:** Given Nutzer A besitzt eine Gruppe und Nutzer B ist angemeldet / When B `DELETE /api/groups/{id}` mit der Gruppen-ID von A sendet / Then antwortet die API mit 404 `not_found` und die Gruppe von A sowie deren Orte bleiben unverändert.
  - Test: Go-Handlertest mit zwei Nutzern; prüft Status und dass A's Gruppenliste und Orts-Verweise unverändert sind.

- **AC-5:** Given ein angemeldeter Nutzer ohne Eintrag unter einer gültigen, unbekannten ID / When er DELETE auf `/api/trips/{id}`, `/api/briefings/{id}?kind=route`, `/api/locations/{id}` bzw. `/api/groups/{id}` mit dieser ID sendet / Then antwortet jeder dieser Endpunkte mit 404 `not_found`.
  - Test: Go-Handlertest, tabellengetrieben über die vier Endpunkte.

- **AC-6:** Given ein angemeldeter Nutzer besitzt einen eigenen Trip, Ort bzw. eine eigene Gruppe / When er den jeweiligen Eintrag per DELETE löscht / Then antwortet die API weiterhin mit 204 und der Eintrag ist danach weg (ein zweites DELETE liefert 404).
  - Test: Go-Handlertest als Regressionsschutz für den Normalfall; bestehende Seeds-Löschungen (`user_scoped_test.go:156`, `schreibsperre_frist_haltedauer_test.go:50`, `mengen_quote_test.go:512/562`) bleiben grün.

- **AC-7:** Given ein angemeldeter Nutzer sendet DELETE für eine unbekannte oder fremde Trip-ID / When die Antwort 404 zurückkommt / Then liegt im Briefing-Verzeichnis des Nutzers keine Datei `<id>.json.lock` zurück.
  - Test: Go-Handlertest, prüft nach dem 404 per Verzeichnisliste, dass weder Trip- noch Sperrdatei unter dieser ID existiert (Regressionsschutz zu #2237).

- **AC-8:** Given unter der Trip-ID liegt eine kaputte, nicht als JSON lesbare Datei / When der Nutzer DELETE auf diesen Trip sendet / Then antwortet die API mit 204 und die Datei ist entfernt.
  - Test: Go-Handlertest und Store-Test mit absichtlich beschädigter Datei (fail-open bleibt erhalten, sonst wäre sie nie mehr löschbar).

- **AC-9:** Given unter einer ID liegt ein Compare-Preset (`kind` = `vergleich`) / When der Nutzer DELETE über den Trip-Pfad `/api/trips/{id}` mit dieser ID sendet / Then antwortet die API mit 404 `not_found` und sowohl die Preset-Datei als auch deren Sperrdatei bleiben unverändert bestehen.
  - Test: Go-Handlertest (umgestellter `TestDeleteTripHandler_VergleichBleibtSamtSperrdatei`) und Store-Test; vorher 204.

- **AC-10:** Given unter der Orts-ID liegt eine kaputte, nicht lesbare Ortsdatei / When der Nutzer DELETE auf diesen Ort sendet / Then antwortet die API mit 204 und die Datei ist entfernt.
  - Test: Go-Handlertest mit beschädigter Datei.

- **AC-11:** Given ein Ortsvergleich verweist veraltet auf eine Orts-ID, die nicht mehr existiert / When der Nutzer DELETE auf diese Orts-ID sendet / Then antwortet die API mit 404 `not_found` und nicht mit 409.
  - Test: Go-Handlertest mit Preset, dessen `LocationIDs` eine nicht vorhandene ID enthält.

- **AC-12:** Given ein existierender Ort steht in `LocationIDs` eines Ortsvergleichs desselben Nutzers / When der Nutzer DELETE auf diesen Ort sendet / Then antwortet die API weiterhin mit 409 `location_in_use` samt `compare_presets` und der Ort bleibt bestehen.
  - Test: bestehender Handlertest aus #2216 bleibt unverändert grün (Existenz-Check darf die Sperre nicht aushebeln).

- **AC-13:** Given Orte verweisen per `group_id` auf eine Gruppen-ID, die in der Gruppenliste nicht mehr existiert (Absturz mitten im Löschen) / When der Nutzer DELETE auf diese Gruppen-ID sendet / Then antwortet die API mit 404 `not_found` und die verwaisten `group_id`-Verweise dieser Orte sind danach genullt.
  - Test: Go-Handlertest mit gesetzten Orts-Verweisen ohne zugehörige Gruppe; prüft Status und die geladenen Orte.

- **AC-14:** Given der Vertrag `docs/reference/api_contract.md` / When ein Leser die DELETE-Endpunkte für Trips, Orte und Gruppen nachschlägt / Then ist für alle drei 404 `not_found` (fremde oder unbekannte ID) dokumentiert, für Trips auch über `/api/briefings/{id}?kind=route`.
  - Test: `# doc-compliance-test` (reine Dokumentationszusicherung); das Verhalten selbst beweisen AC-1 bis AC-13.

## Known Limitations

- **Zweiter Tab:** Löscht ein zweiter Browser-Tab einen bereits gelöschten Trip, zeigt die Oberfläche künftig einen Fehler
  (`subscriptionExec.deleteSubscription` wirft bei `!ok`, Archiv-Seite „DELETE failed: 404“) statt stillem Erfolg. Beim Ortsvergleich
  verhält sie sich schon heute so; der Trip wird damit einheitlicher, nicht neu kaputt. `busyId` verhindert Doppelklicks.
- **„404 = schon weg“ im UI** ist bewusst nicht Teil dieses Tickets (Scope-Erweiterung im Frontend); das Frontend bleibt unverändert.
- E2E-Aufräumcode (Playwright `request.delete` mit `.catch`) und Python-Tests (`session.delete`) prüfen den Status nicht
  oder akzeptieren 404 ausdrücklich (z. B. `kurzform-…spec.ts:148`, `weather-metrics-tab-autosave.spec.ts:70`).
- Kein Datenleck-Fix: Es gab keines, der Unterschied ist rein der Statuscode. Die Existenz fremder IDs wird weder vorher noch nachher preisgegeben, da 404 für fremd und unbekannt identisch ist.

## Test Plan

Deterministische Go-Tests (Kern-Schicht, ohne Netz) in `internal/handler` und `internal/store`; echte Dateien in
`t.TempDir()`, kein Mock-Theater. Zwei-Nutzer-Tests je Endpunkt sind Pflicht (ADR-0003, Epic-DoD); die Nutzer-ID kommt
aus dem Auth-Kontext, nie `"default"`.

Neue Tests (Handler, Dateien nach Verhalten benannt): AC-1 bis AC-13, jeweils gegen die HTTP-Antwort des Handlers,
nicht nur gegen den Store. Neue Store-Tests: `ErrNotFound` für `DeleteTrip` (fehlend, Compare-Preset), `DeleteLocation`
(fehlend), `DeleteGroupLocked` (keine Gruppe entfernt, `saveGroups` nicht aufgerufen); kaputte Datei liefert `nil`.

**Bestehende Tests, die bewusst umgestellt werden** (erwarten heute `nil`/204, künftig `ErrNotFound`/404):

| Datei:Zeile | Heute | Künftig |
|---|---|---|
| `internal/store/store_trip_write_test.go:125` (`DeleteTrip("nonexistent")`) | `nil` | `ErrNotFound` |
| `internal/store/store_location_write_test.go:60` (`DeleteLocation("nonexistent")`) | `nil` | `ErrNotFound` |
| `internal/store/store_trip_briefings_test.go:183` (`DeleteTrip("shared-id")`, Compare-Preset unter derselben ID) | `nil` | `ErrNotFound`, Preset-Datei bleibt unverändert |
| `internal/handler/delete_lock_cleanup_test.go:107` (`TestDeleteTripHandler_VergleichBleibtSamtSperrdatei`) | 204 | 404, Preset-Datei und Sperrdatei bleiben |

Unverändert grün bleiben müssen: `user_scoped_test.go:156`, `schreibsperre_frist_haltedauer_test.go:50`,
`mengen_quote_test.go:512/562`, die #2216-Tests (409) sowie die Signaturtabelle in `user_scope_guard_test.go`.
Die Live-E2E-Schicht (`/e2e-verify`) prüft gegen Staging mit Wegwerf-Nutzern: fremde Trip-ID löschen -> 404, eigener Trip -> 204.

## Mutations-Gegenprobe (Hinweise für den Adversary)

Geprüft wird dort, wo die Zusicherung wirkt, nämlich an der HTTP-Antwort des Handlers:
- `ErrNotFound`-Mapping im Trip-Handler entfernen (Fehler wird 500 oder 204): AC-1, AC-2, AC-5 müssen rot werden.
- Im Store `os.IsNotExist` wieder auf `return nil` setzen: AC-5 und die umgestellten Store-Tests müssen rot werden.
- `kind=="vergleich"`-Zweig wieder `nil` liefern lassen: AC-9 muss rot werden.
- Sperrdatei-Aufräumen nur bei Erfolg (`deleted`) statt auch bei 404: AC-7 muss rot werden.
- Kaputte Datei als `ErrNotFound` behandeln: AC-8 und AC-10 müssen rot werden.
- Existenz-Check im Orts-Handler hinter die Nutzungsprüfung verschieben: AC-11 muss rot werden.
- Aufräumschleife im Gruppen-Handler bei `ErrNotFound` überspringen: AC-13 muss rot werden.
- Store über `"default"` statt `WithUser`: die Zwei-Nutzer-Tests AC-1 bis AC-4 müssen rot werden.

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** keine neue. Berührt: ADR-0003 (Mandantentrennung, `WithUser` Pflicht), ADR-0083 (Schreibsperre Gruppen -> Ort, unverändert).
- **Rationale:** Kleine, rückwärtskompatible Vereinheitlichung des Statuscodes nach vorhandenem Vorbild (Compare-/Metrik-Presets);
  keine Entscheidungsfläche aus `docs/adr/` wird verändert. Trip/Ortsvergleich-Teilung: nicht berührt, es entsteht keine neue Komponente.

## Changelog

- 2026-11-07: Initial spec created (#2815)
