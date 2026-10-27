---
entity_id: id_eindeutigkeit_trip_vergleich_2359
type: module
created: 2026-10-24
updated: 2026-10-24
status: draft
version: "1.0"
tags: [bugfix, datenverlust, briefings, etag, mandantentrennung, epic-2507]
---

# ID-Eindeutigkeit Trip / Ortsvergleich (Issue #2359)

## Approval

- [ ] Approved

## Purpose

Trips und Ortsvergleiche liegen in derselben Ablage (`data/users/<uid>/briefings/<id>.json`, ADR-0023, Unterscheidung nur über das Feld `kind`) und teilen damit einen Kennungsraum. Heute kann `POST /api/trips` mit der Kennung eines bestehenden Ortsvergleichs diesen **still überschreiben** (Datenverlust); die Spec macht die Eindeutigkeit der Kennung über beide Arten zu einer Server-Invariante (doppelter Riegel: Handler-Vorab-Check + Store-Wächter) und stellt damit auch klar, dass der Browser-ETag-Schlüsselraum (ein Raum) ausreicht.

## Hintergrund und Befund

Der Ticket-Text beschreibt nur das Symptom (Frontend-Registry verwechselt Stempel bei gleicher Kennung). Die Kontextphase (`docs/context/fix-2359-etag-schluesselraum.md`) hat die Ursache gefunden:

- `POST /api/trips` übernimmt die Kennung aus dem Rumpf (`internal/handler/trip.go`, Anlegen ab ca. Zeile 162; `validateTrip` prüft nur das Format). Die Existenzprüfung `s.LoadTrip(trip.ID)` (`trip.go:214`) liefert für eine Datei mit `kind:"vergleich"` `nil` (`internal/store/trip.go:218`, Wächter „fremde Art ⇒ nil"). Der Handler hält die Kennung deshalb für „frei" und `SaveTrip` (`trip.go:233`) überschreibt die Ortsvergleichs-Datei mit einem Trip. Kein Test deckt das.
- Gegenrichtung: Die Server-Kennung für neue Ortsvergleiche (`cp-<16hex>`, `internal/handler/compare_preset.go:~83-89`, Anlegen :284) kollidiert praktisch nie; Alt-Ortsvergleiche tragen aber Slug-Kennungen ohne Präfix (z. B. `zillertal-t-glich`). Die Zusicherung „`cp-` schließt eine Kollision aus" in `docs/specs/modules/issue_1395_s6_ortsvergleich_etag.md` (ca. :228-234) und der Kommentar in `frontend/src/lib/etagRegistry.ts` (ca. :67-78) ist damit nur für neue Kennungen richtig.
- Server-Schutz gegen fremde Stempel trägt bereits: Der Fingerprint ist der sha256 der Datei-Bytes (`internal/store/briefing_fingerprint.go`), `PUT` auf die falsche Art liefert 404 **vor** der If-Match-Prüfung (`trip.go:336` vor :345). Das war bisher nur gelesen, nicht per Test bewacht.

### Messungen aus dem Ticket

1. **Kollision im Bestand: NOT_MEASURABLE.** `/var/lib/gregor` gehört `claude-gregor`; der ausführende Nutzer hat keinen Lesezugriff (Mandantenschutz, bewusst nicht per sudo umgangen). Es gibt daher **keine** Aussage „im Bestand gibt es keine Kollision". Strukturell gilt: pro Kennung existiert nur EINE Datei; eine bestehende Kollision wäre bereits ein vollzogener stiller Verlust. Unterscheider für eine spätere Messung durch eine berechtigte Instanz: Kennung aus dem alten `compare_presets.json`, deren `briefings/<id>.json` heute `kind≠vergleich` trägt.
2. **Fremder Stempel am Server: sicher** (siehe oben), wird in dieser Spec per Test bewacht (AC-7).

## Source

- **File:** `internal/handler/trip.go`, `internal/store/trip.go`, `internal/store/compare_preset.go`, `internal/handler/compare_preset.go`
- **Identifier:** `POST /api/trips` (Handler-Anlegen), `Store.SaveTrip`, `Store.SaveComparePreset`, neu `ErrKindConflict`

## Estimated Scope

- **LoC:** ~+60 Produktivcode, ~+150 Tests (Doku-/Kommentarkorrekturen zählen nicht)
- **Files:** 4 Go-Produktivdateien + 1 Frontend-Kommentar + 1 Spec-Korrektur + neue Testdateien
- **Effort:** low–medium (zentraler Speicherpfad, Wächter greift aber nur bei fremder Art)

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `ValidEntityID` (Store) | Funktion | Kennungsformat, bleibt unverändert |
| Briefing-Lock (`lockBriefingOr503`) | Mechanismus | Wächter im Store läuft unter diesem Lock (schließt TOCTOU) |
| `LockQuota` / `quotaAllows` (#2482) | Mechanismus | Kollisionsprüfung muss VOR der Quota-Prüfung laufen |
| ADR-0023 | Entscheidung | Ein Modell, eine Ablage, gemeinsamer Kennungsraum — wird durchgesetzt, nicht geändert |
| `internal/handler/etag.go`, `store/briefing_fingerprint.go` | Bestand | Fremdstempel-Verhalten (nur Tests) |

## Implementation Details

Alles Go-API-Schicht (`internal/`), Frontend nur ein Kommentar. Kein Python-Anteil: `save_trip` in `src/app/loader.py` hat keinen produktiven Aufrufer; der Python-Scheduler schreibt nur Read-Modify-Write auf bestehende Dateien.

```
Store (internal/store):
  var ErrKindConflict = errors.New("kennung von anderer art belegt")
  Helfer idBelegtDurchFremdeArt(id, erwarteteArt) -> (bool, error):
    Datei briefings/<id>.json lesen; Probe {kind}
    - Datei fehlt / nicht lesbar / leer / korrupt JSON -> false (fail-open, wie DeleteComparePreset)
    - SaveTrip:          kind == "vergleich"            -> belegt   (kind=="" zaehlt als Trip)
    - SaveComparePreset: kind != "vergleich" (inkl. "") -> belegt   (nur bei lesbarer, gueltiger Datei)
  SaveTrip / SaveComparePreset: nach ValidEntityID, vor dem Schreiben pruefen;
    belegt -> return ErrKindConflict, Datei unveraendert.
  (Aufrufer halten bereits den Briefing-Lock -> Pruefung + Schreiben atomar.)

Handler POST /api/trips (internal/handler/trip.go):
  Reihenfolge: ... LockQuota -> LoadTrip -> [NEU] Vorab-Check "Kennung von Ortsvergleich belegt?"
               -> Quota-Pruefung -> LockBriefing -> SaveTrip
  Vorab-Check belegt -> 409 {"error":"id_conflict","detail":"Ein Ortsvergleich traegt bereits diese Kennung - bitte anderen Namen waehlen."}
  (im Quelltext mit korrekten Umlauten: "Ortsvergleich trägt bereits diese Kennung — bitte anderen Namen wählen.")
  SaveTrip liefert ErrKindConflict (Rennen) -> ebenfalls 409 id_conflict, nicht 500.
  Eigener Trip (auch Alt-Datei ohne kind) -> unveraendert Upsert 201 (AC-6 #2482).

Handler Compare (internal/handler/compare_preset.go, Anlegen :284; weitere SaveComparePreset-Aufrufer
  :436/:558 laden vorher art-gefiltert): ErrKindConflict -> 409 {"error":"id_conflict","detail":<deutsch>} statt 500.
  (briefing_subscription.go:285 PATCH: laedt vorher kind-gefiltert per LoadComparePresets/findComparePresetIdx, uebernimmt KEINE Client-Kennung ⇒ Wächter kann dort nicht greifen; unveraendert, kein Test noetig.)

Frontend: nur Kommentar in etagRegistry.ts korrigieren — Eindeutigkeit ueber beide Arten wird serverseitig
  erzwungen (Verweis auf Waechter + Test); Registry bleibt bei EINEM Schluesselraum (nicht nach Art schluesseln).
Doku: issue_1395_s6_ortsvergleich_etag.md — falsche Zusicherung "cp- schliesst Kollision aus" korrigieren
  (gilt nur fuer neu erzeugte Kennungen; Alt-Ortsvergleiche tragen Slugs; Schutz ist der Waechter aus #2359).
```

Warum doppelter Riegel: Der Handler-Check liefert die nutzerverständliche Meldung und greift vor der Quota (eine Quota-Ablehnung würde den Kollisionsfall sonst maskieren). Der Store-Wächter ist die Invariante für künftige Aufrufer und schließt das Zeitfenster zwischen Check und Schreiben.

Warum Registry nicht nach Art schlüsseln: Die Ablage erzwingt ohnehin einen gemeinsamen Kennungsraum; mit dem Wächter gibt es nie zwei Ressourcen mit gleicher Kennung, ein Schlüssel pro Kennung genügt.

## Expected Behavior

- **Input:** `POST /api/trips` mit einer Kennung, unter der im Konto des Nutzers ein Ortsvergleich liegt; oder jeder Store-Aufruf `SaveTrip`/`SaveComparePreset` auf eine Datei der anderen Art.
- **Output:** HTTP 409 `{"error":"id_conflict","detail":"<deutsche Meldung>"}` (Store: `ErrKindConflict`). Ortsvergleich bleibt byte-gleich bestehen, kein neuer Trip entsteht.
- **Side effects:** keine Schreibzugriffe, keine Quota-Änderung im Konfliktfall. Eigene Kennung (Upsert) und freie Kennung verhalten sich unverändert (201). Die Meldung erreicht den Nutzer im GPX-Upload, weil dort `e.detail ?? e.error` angezeigt wird (`frontend/src/routes/gpx-upload/+page.svelte`, Speicher-Fehlerpfad ca. :114); `api.ts` markiert nur 412 als Konflikt-Banner, 409 löst keinen aus und läuft als normale Fehlermeldung durch.

## Acceptance Criteria

- **AC-1:** Given ein Nutzer besitzt einen Ortsvergleich mit der Kennung `x` / When er (oder ein API-Client) `POST /api/trips` mit einem Trip der Kennung `x` sendet / Then antwortet der Server 409 mit `{"error":"id_conflict","detail":<deutscher Text>}`, der Ortsvergleich ist byte-gleich unverändert (gleicher Fingerprint, `LoadComparePreset` identisch) und `LoadTrips` zählt keinen neuen Trip.
  - Test: Go-Handlertest `internal/handler/id_eindeutigkeit_test.go`. Ortsvergleich über den Produktpfad `SaveComparePreset` anlegen (kein handgeschriebenes JSON), Bytes der Datei vorher/nachher vergleichen, `LoadComparePreset` und `LoadTrips` nachprüfen.

- **AC-2:** Given Nutzer A besitzt einen Ortsvergleich `x`, Nutzer B besitzt keine Ressource `x` / When B `POST /api/trips` mit Kennung `x` sendet und danach A dasselbe tut / Then erhält B 201 (eigener Trip angelegt, A's Ortsvergleich unberührt) und A erhält 409 `id_conflict`.
  - Test: Go-Handlertest mit zwei verschiedenen Nutzern (echte `user_id` über den Auth-Kontext, kein `"default"`); prüft beide Antworten und beide Datenordner.

- **AC-3:** Given ein Nutzer besitzt einen eigenen Trip `t1` (auch eine Alt-Datei ohne `kind`-Feld) / When er `POST /api/trips` mit Kennung `t1` erneut sendet (Upsert, AC-6 aus #2482) / Then antwortet der Server weiterhin 201 und der Trip ist aktualisiert; weder Handler-Check noch Store-Wächter blockieren das Überschreiben der eigenen Art.
  - Test: Go-Handlertest für zwei Fälle (Trip mit `kind:"route"`, Trip-Datei ohne `kind`, Letztere über den Produktpfad angelegt und dann das Feld entfernt, Zustand „Alt-Datei" belegt durch Dateilesen im Test).

- **AC-4:** Given eine Zieldatei `briefings/<id>.json` / When `SaveTrip` auf eine Datei mit `kind:"vergleich"` bzw. `SaveComparePreset` auf eine Datei mit `kind:"route"` (oder ohne `kind`, aber gültig) zielt / Then liefert der Store `ErrKindConflict` und lässt die Datei byte-gleich; ist die Zieldatei dagegen fehlend, leer oder korruptes JSON, wird gespeichert (fail-open), und `kind==""` zählt beim Trip-Speichern als eigene Art.
  - Test: Go-Storetest `internal/store/id_eindeutigkeit_test.go`, beide Richtungen plus Fail-open-Fälle (fehlend, 0 Byte, `{kaputt`); Bytevergleich vorher/nachher.

- **AC-5:** Given ein Nutzer hat sein Trip-Limit (#2482) erreicht und besitzt einen Ortsvergleich `x` / When er `POST /api/trips` mit Kennung `x` sendet / Then lautet die Antwort 409 `id_conflict` und nicht der Quota-Fehler, weil die Kollisionsprüfung vor der Quota-Prüfung läuft.
  - Test: Go-Handlertest mit gefülltem Trip-Limit (Quota-Konfiguration wie im bestehenden Quota-Test); prüft Statuscode und `error`-Code.

- **AC-6:** Given ein Nutzer sendet `POST /api/trips` / When zwischen Vorab-Check und Schreiben eine Ortsvergleichs-Datei mit derselben Kennung entsteht (Rennen) / Then liefert der Handler ebenfalls 409 `id_conflict` (Store-Sentinel wird abgebildet, kein 500) und der Ortsvergleich bleibt erhalten.
  - Test (feste Anordnung): Beide Handler bilden Save-Fehler über EINEN gemeinsamen Helfer `writeSaveError(w, err)` ab (`ErrKindConflict` ⇒ 409 `id_conflict` + deutscher `detail`, sonst 500 `store_error`). Go-Test ruft den Helfer mit dem ECHTEN Sentinel auf, den ein realer `SaveTrip` auf eine per `SaveComparePreset` angelegte Ortsvergleichs-Datei liefert (kein Mock, kein konstruierter Fehler) ⇒ 409 + `id_conflict`; zusätzlich ein beliebiger anderer Fehler ⇒ 500 `store_error`. Die Verdrahtung des Helfers im Compare-Handler belegt AC-8 Ende-zu-Ende; im Trip-Handler ist das Rennen ohne Test-Naht nicht auslösbar (siehe Known Limitations).

- **AC-7:** Given ein Ortsvergleich `c1` und ein Trip `t1` desselben Nutzers mit je eigenem ETag / When `PUT /api/trips/c1` mit dem ETag des Ortsvergleichs und `PUT /api/compare/presets/t1` mit dem ETag des Trips gesendet werden / Then antwortet der Server in beiden Fällen 404 (`not_found`) und die Datei-Bytes beider Ressourcen sind unverändert.
  - Test: Go-Handlertest `internal/handler/id_eindeutigkeit_test.go`, beide Richtungen, Bytevergleich; belegt den bislang nur gelesenen Schutz.

- **AC-8:** Given ein Ortsvergleich oder Preset-Speichern trifft auf eine Datei fremder Art / When der Compare-Handler `SaveComparePreset` aufruft und `ErrKindConflict` erhält / Then antwortet er 409 `{"error":"id_conflict","detail":<deutscher Text>}` statt 500 `store_error`.
  - Test (feste Anordnung): `newComparePresetID` wird von `func` zur Paket-Variable (Test-Naht, Produktverhalten unverändert). Go-Handlertest legt über den Produktpfad (`POST /api/trips` bzw. `SaveTrip`) einen Trip `t1` an, setzt die Naht für die Testdauer auf `t1` (mit `t.Cleanup`-Rücksetzung) und sendet `POST` an die Compare-Anlage ⇒ 409 `id_conflict` mit deutschem `detail`; die Bytes von `briefings/t1.json` sind vorher/nachher gleich und `LoadComparePresets` enthält keinen neuen Eintrag.

- **AC-9:** Given ein Nutzer legt im GPX-Upload einen Trip an, dessen Namens-Slug der Kennung eines seiner Ortsvergleiche entspricht / When der Server 409 `id_conflict` antwortet / Then sieht der Nutzer den deutschen `detail`-Text („Ein Ortsvergleich trägt bereits diese Kennung — bitte anderen Namen wählen.") als Fehlermeldung, nicht einen technischen Code, und es entsteht kein Konflikt-Banner (der nur für 412 vorgesehen ist).
  - Test: Frontend-Test (`node --test`) auf die Fehleraufbereitung `api.post` → Meldung (`detail ?? error`) mit einer 409-Antwort; ergänzend Prüfung, dass `markiereKonflikt` bei 409 nicht aufgerufen wird. Die Aussage zum Anzeigepfad wurde im Quelltext gegengeprüft (`+page.svelte` Speicherfehler `detail ?? error`).

## Out of Scope

- **GPX-Upload-Slug überschreibt eigenen Trip** (gleichnamiger eigener Trip wird still überschrieben, Upsert-Semantik AC-6): eigener Befund, gebucht als #2612.
- Frontend-Registry nach Art schlüsseln (bewusst verworfen, siehe Implementation Details).
- Bereinigung bereits kollidierter Bestandsdaten (Messung nicht möglich, siehe oben; ein vollzogener Verlust wäre ohnehin nicht rekonstruierbar).
- Tote Funktion `SaveBriefing` (`internal/store/briefing_subscription.go`), Python-`save_trip`: ohne produktiven Aufrufer, unverändert.
- Migrationen `migrate_1257`/`migrate_1258`: laden art-gefiltert, vom Wächter unberührt.

## Known Limitations

- Bestandskollisionen (falls vorhanden) bleiben unentdeckt, bis eine berechtigte Instanz die Messung (siehe „Unterscheider") ausführt.
- Der Wächter schützt nur Schreibwege über `SaveTrip`/`SaveComparePreset`; direkte Dateischreibungen außerhalb des Stores (z. B. manuelle Eingriffe) sind nicht erfasst.
- Rennen im Trip-Anlegen (Ortsvergleichs-Datei entsteht zwischen Vorab-Check und `SaveTrip`): praktisch ausgeschlossen, da Compare-Kennungen serverseitig `cp-<16hex>` sind; die Abbildung Sentinel ⇒ 409 ist über den gemeinsamen Helfer (AC-6) bewacht, der Helfer-Aufruf im Trip-Handler selbst ist ohne zusätzliche Test-Naht nicht durch einen Test erzwungen.
- Eine korrupte Zieldatei lässt das Speichern zu (fail-open, wie `DeleteComparePreset`), damit sich ein Konto nicht an einer defekten Datei selbst blockiert.
- Schreibende Aufrufer, die ihren Datensatz vorher art-gefiltert laden (`compare_preset.go` :436/:558, `trip.go` PUT/PATCH), sind durch den Wächter zusätzlich abgesichert, ändern ihr Verhalten aber nicht.

## Risiken

- Zentraler Speicherpfad: Der Wächter liest vor jedem Save die Zieldatei (ein zusätzlicher Dateizugriff, vernachlässigbar). Bulk-Wrapper `SaveComparePresets` ruft `SaveComparePreset` je Eintrag; bei einem Konflikt bricht der Wrapper mit `ErrKindConflict` ab, bereits geschriebene Einträge bleiben. Bestehende Aufrufer laden vorher art-gefiltert, ein Konflikt ist dort nicht erwartbar; /40 deckt den Wrapper mit einem Test ab.
- AC-6/AC-8 brauchen eine feste Anordnung (Handler vergibt `cp-…` selbst): gemeinsamer Helfer `writeSaveError` plus Test-Naht `newComparePresetID` als Paket-Variable (siehe AC-6/AC-8). Kein handgeschriebenes JSON, kein Mock.
- Wortlaut der 409-Meldung ist mit dieser Spec festgelegt; Änderungen brauchen Anpassung von AC-1/AC-9.

## Geplante Tests (Zuordnung)

| Datei (nach Verhalten benannt) | ACs |
|---|---|
| `internal/handler/id_eindeutigkeit_test.go` | AC-1, AC-2, AC-3, AC-5, AC-6, AC-7, AC-8 |
| `internal/store/id_eindeutigkeit_test.go` | AC-4 (und Bulk-Wrapper) |
| `frontend/src/lib/__tests__/apiIdKonfliktMeldung.test.ts` | AC-9 |

Querschnitt: Mandantentrennung durch AC-2 (zwei Nutzer). Trip/Ortsvergleich-Teilung: der Wächter liegt symmetrisch in beiden Save-Funktionen, es entsteht keine einseitige neue Komponente. Kanäle: nicht betroffen (kein Briefing-/Alarminhalt).

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** keine (ADR-0023 wird durchgesetzt)
- **Rationale:** ADR-0023 legt Ablage und gemeinsamen Kennungsraum bereits fest; der Wächter macht dessen Eindeutigkeit zur geprüften Invariante, ohne die Entscheidung zu ändern.

## Changelog

- 2026-10-24: Initial spec created (Issue #2359, Epic #2507)
