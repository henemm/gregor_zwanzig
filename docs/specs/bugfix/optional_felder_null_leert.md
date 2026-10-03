---
entity_id: optional_felder_null_leert
type: bugfix
created: 2026-10-03
updated: 2026-10-03
status: draft
version: "1.0"
workflow: fix-2211-optional-felder-null
tags: [bugfix, go, frontend, trip, ortsvergleich, alarme, persistence, issue-2211]
---

# Optionale Felder per null leeren (Trip + Ortsvergleich)

## Approval

- [ ] Approved

## Purpose

Wer bei einem Trip oder Ortsvergleich die Alarm-Pause oder die Ruhezeit leert und speichert, soll danach wirklich keinen gespeicherten Wert mehr haben. Heute behält der Server den alten Wert (Issue #2211: Staging-Trip behielt `alert_cooldown_minutes=45`), weil JSON `null` und "Feld fehlt" im Go-Handler nicht unterscheidbar sind (Trip) bzw. weil das Frontend beim Leeren den Key weglässt (Ortsvergleich). Der Fix stellt den in #99 versprochenen, nie umgesetzten Kontrakt her: "Feld vorhanden, Wert null = ausdrücklich leeren; Feld fehlt = Bestand behalten".

## Source

- **Trip (Go):** `internal/handler/trip.go`, `UpdateTripHandler` / DTO `tripUpdateRequest`; erreichbar auch über `PUT /api/briefings/{id}?kind=route` (delegiert per `UpdateTripHandler(s).ServeHTTP(w, r)`, Body unverändert).
- **Ortsvergleich (Frontend):** `frontend/src/lib/components/compare/compareEditorSave.ts` (`buildComparePresetSavePayload`), `frontend/src/lib/components/shared/alarmeVergleichSpeicherung.ts` (`alarmSnapshotAus`, `baueAlarmNutzlast`), `frontend/src/lib/components/compare/alarmePropsAus.ts`.
- **Server Ortsvergleich:** `UpdateComparePresetHandler` / `mergeBriefingPatch` (`internal/handler/briefing_subscription.go`) leert `null` bereits korrekt; wird nur durch Test abgesichert.

## Estimated Scope

- **LoC:** Code ca. +90/-15 (Go ca. +60/-15, Frontend ca. +30), Tests ca. +250
- **Files:** 1 neu (Typ) + 3 Code-Dateien + 2 neue Testdateien (+ Doku-Nachzug)
- **Effort:** medium

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `encoding/json` | stdlib | ruft `UnmarshalJSON` bei Wert-Typ auch für `null` auf, bei fehlendem Key nicht |
| `validateTrip` | Funktion | läuft nach dem Merge, unverändert |
| `store.SaveTrip` / `LoadTrip` | Store | Persistenz, unverändert; Nutzerbindung über `s.WithUser(...)` |
| `mergeBriefingPatch` | Funktion | Overlay-Merge am Compare-PUT, unverändert |
| `deviation_alert_engine.is_quiet_hours` | Python-Leser | `not quiet_from or not quiet_to` ⇒ keine Ruhezeit |
| `trip_alert.py` (Cooldown-Leser), `radar_alert_service.py:24` | Python-Leser | `None` ⇒ Standard 120 Min; keine Änderung |
| `alarmeDeliveryPayload.ts` (Trip-Frontend) | Frontend | sendet beim Leeren bereits `null`; keine Änderung |
| `docs/specs/bugfix/update_trip_handler_merge.md` | Spec | Kontrakt aus #99, wird im Geltungsbereich nachgezogen |

## Implementation Details

### Teil A: Go, Trip-PUT

1. Neuer generischer Drei-Zustands-Typ (fehlt / null / Wert) als **Wert-Feld** (kein Pointer) mit `UnmarshalJSON`, neue Datei `internal/handler/optional_field.go`. `encoding/json` ruft `UnmarshalJSON` bei einem Wert-Typ auch für `null` auf; bei fehlendem Key gibt es keinen Aufruf (Zustand "nicht gesetzt"). **Der erste RED-Test belegt diese Annahme auf Decode-Ebene.**
2. Genau **7 Felder** in `tripUpdateRequest` umstellen: `alert_cooldown_minutes`, `alert_quiet_from`, `alert_quiet_to`, `official_alerts_enabled`, `official_alert_triggers_enabled`, `region`, `activity`.
3. Merge-Semantik je Feld: fehlt ⇒ Bestand behalten; `null` ⇒ leeren (Pointer-Modellfelder auf nil; bei `region`/`activity` auf `""`); Wert ⇒ setzen.
4. **Ausdrücklich unverändert** (`null` heißt weiter "behalten"): `name` (Pflicht), Listen `stages`/`avalanche_regions`/`alert_rules`/`corridors`, Maps `aggregation`/`weather_config`/`display_config`/`report_config`/`alert_metric_channels`, Structs `official_warnings`/`alert_channels`/`alert_channel_thresholds`. Ein "null leert alle Etappen" wäre Datenverlust (#99/#102).
5. Implementierungshinweis: Falls `tripUpdateRequest` irgendwo gemarshalt wird (Developer prüft per grep), braucht der Typ zusätzlich `MarshalJSON`.
6. Frontend Trip: keine Änderung. Activity hat keine UI zum Leeren, im Scope ist nur die Server-Semantik.

### Teil B: Ortsvergleich-Parität (Frontend-only)

Befund (Code-Spur): Der Compare-Alarme-Reiter setzt beim Leeren `alertCooldownMinutes` bzw. `quietFrom/To` auf `undefined` (`alarmePropsAus.ts:158-164`). `alarmSnapshotAus` (JSON-Rundreise) lässt `undefined` fallen, `buildComparePresetSavePayload` (`compareEditorSave.ts:233-236`) sendet nur bei `!== undefined`, `baueAlarmNutzlast` übernimmt über `waehleEigenfelder` nur vorhandene Keys. Der Key fehlt, der Server behält den alten Wert. Der Server leert `null` am Compare-PUT bereits korrekt (Overlay `base[k]=v`, Unmarshal in `*int`/`*string`).

**Festgelegte Fix-Form:** Für `alert_cooldown_minutes`, `alert_quiet_from`, `alert_quiet_to` wird ein explizites `null` gesendet, **nur wenn der gespeicherte Bestand (preset) einen Wert hatte und der aktuelle Zustand leer ist**; andernfalls wird der Key weggelassen. Das schützt gegen nicht oder falsch hydrierten Zustand (Lehre #2381: ETag fängt keinen Same-Tab-Stale-Payload) und damit gegen Datenverlust.

**Verworfen:** Die Trip-gleiche Variante "immer `?? null` senden". Begründung: Beim Trip ist der Zustand garantiert aus dem gespeicherten Trip initialisiert; im Compare-Editor läuft die Alarm-Nutzlast über Snapshot und Rundreise, in der ein nicht hydrierter Zustand von "Nutzer hat geleert" nicht unterscheidbar wäre. Ein stilles `null` würde dann gespeicherte Werte löschen (Datenverlust-Richtung).

**Prüfpunkt für den Adversary:** Kann die Vergleich-Seite dieselbe Null-Konvention bzw. dieselbe Hilfsfunktion wie die Trip-Seite nutzen (CLAUDE.md-Invariante Code-Teilung)? Eine Compare-eigene Parallel-Konvention ist nur mit dokumentierter Begründung zulässig.

### Testform

- **Go (Kern-Schicht):** ROHE JSON-Bodies (`{"alert_cooldown_minutes":null}` vs. `{}` vs. `{"alert_cooldown_minutes":30}`) durch den echten HTTP-Handler, Rücklesen aus Store bzw. per GET. Struct-Literale sind ungeeignet, sie können "fehlt" und `null` nicht unterscheiden. Mindestens ein Test läuft über `PUT /api/briefings/{id}?kind=route` (Router), damit belegt ist, dass `null` die Delegation übersteht. Matrix je Feld: null leert / fehlt behält / Wert setzt. Zwei-Nutzer-Isolation (Nutzer B unberührt). Testdatei: `internal/handler/trip_optional_clear_test.go`. Zusätzlich ein Go-Test am Compare-PUT: `null` leert, fehlt behält.
- **Frontend:** `node --test` (kein Vitest), Test über den echten Payload-Weg (`buildComparePresetSavePayload` bzw. `baueAlarmNutzlast`/Speicherweg), nicht nur über die Hilfsfunktion. Der `fakeTripServer` bildet den Go-Merge nicht nach und beweist hier nichts.
- Keine Mocks, die nur die eigene Annahme spiegeln.

## Expected Behavior

- **Input:** PUT mit Body, in dem eines der 7 Felder `null` ist, fehlt oder einen Wert hat (Trip); Compare-Speichern mit geleertem Alarm-Feld.
- **Output:** `null` ⇒ Feld nach Rücklesen nicht mehr gespeichert (Standard greift); fehlt ⇒ Bestand unverändert; Wert ⇒ gesetzt.
- **Side effects:** Alarm-Leser (Python) lesen `None` als Standard: Cooldown 120 Min, keine Ruhezeit. "Leer" heißt ausdrücklich **nicht** "keine Pause".

## Acceptance Criteria

- **AC-1:** Given ein Trip mit gespeicherter Alarm-Pause von 45 Minuten / When der Nutzer im Alarme-Reiter das Feld leert und speichert (PUT mit `"alert_cooldown_minutes": null`) / Then zeigt der Abruf des Trips keinen gespeicherten Wert mehr für die Alarm-Pause, es greift der Standard von 120 Minuten (nicht "keine Pause").

- **AC-2:** Given ein Ortsvergleich mit gespeicherter Alarm-Pause von 45 Minuten / When der Nutzer im Alarme-Reiter das Feld leert und speichert / Then enthält die Speicheranfrage ein explizites `null` für die Alarm-Pause und der Abruf des Ortsvergleichs zeigt keinen gespeicherten Wert mehr, es greift der Standard von 120 Minuten.

- **AC-3:** Given ein Trip mit eingeschalteter Ruhezeit (von und bis gesetzt) / When der Nutzer die Ruhezeit ausschaltet und speichert / Then sind `alert_quiet_from` und `alert_quiet_to` beide nicht mehr gespeichert und es gilt keine Ruhezeit.

- **AC-4:** Given ein Ortsvergleich mit eingeschalteter Ruhezeit / When der Nutzer die Ruhezeit ausschaltet und speichert / Then sendet das Frontend für von und bis je ein explizites `null` und der Abruf zeigt beide Felder nicht mehr, es gilt keine Ruhezeit.

- **AC-5:** Given ein Trip bzw. Ortsvergleich mit Alarm-Pause 45 Minuten / When der Nutzer nur die Ruhezeit ändert und speichert / Then bleibt die Alarm-Pause bei 45 Minuten (Anti-Regression Datenverlust; geprüft über den echten Payload-Builder und auf Staging durchgeklickt).

- **AC-6:** Given ein Trip mit gesetzten Werten in allen 7 Feldern / When ein PUT-Body ohne diese Felder gesendet wird (z. B. `{"name":"X"}` oder nur Etappen) / Then bleiben alle Bestandswerte unverändert (#99-Kontrakt: fehlt = behalten).

- **AC-7:** Given ein Trip ohne gesetzte Alarm-Felder / When ein PUT mit konkreten Werten gesendet wird (z. B. Pause 30, Ruhezeit 22:00 bis 06:00, Region, Activity) / Then sind genau diese Werte gespeichert und beim Abruf sichtbar.

- **AC-8:** Given ein Trip mit Etappen und Namen / When ein PUT mit `"stages": null` bzw. `"name": null` gesendet wird / Then bleiben Etappen und Name unverändert (Wächter: Listen, Maps, Structs und Name behalten bei `null` den Bestand).

- **AC-9:** Given ein Trip mit gesetzten Werten für amtliche Warnungen und deren Trigger / When ein PUT mit `"official_alerts_enabled": null` und `"official_alert_triggers_enabled": null` gesendet wird / Then sind beide nicht mehr gespeichert und es greift der Systemstandard.

- **AC-10:** Given ein Trip mit Ruhezeit von 22:00 bis 06:00 / When ein PUT nur `"alert_quiet_from": null` sendet (bis bleibt) / Then speichert der Server genau das, nämlich bis=06:00 bleibt und von ist weg, und die Alarm-Prüfung wertet das halbe Paar als keine Ruhezeit (`not quiet_from or not quiet_to` ⇒ nicht ruhig); dokumentierte Lesart, kein Fehler.

- **AC-11:** Given zwei Nutzer A und B mit je einem Trip mit Alarm-Pause / When Nutzer A seine Alarm-Pause per `null` leert / Then ist die Alarm-Pause von Nutzer B unverändert; dasselbe gilt für Ortsvergleiche.

- **AC-12:** Given derselbe Trip mit gesetzter Alarm-Pause / When das Leeren über `PUT /api/briefings/{id}?kind=route` statt `PUT /api/trips/{id}` erfolgt / Then ist das Ergebnis identisch (null leert), das `null` übersteht die Delegation.

- **AC-13:** Given ein Ortsvergleich, dessen Alarm-Zustand nicht aus dem Bestand hydriert wurde (Alarm-Felder im gespeicherten Preset gesetzt, im Editor-Zustand leer ohne Nutzeraktion) / When gespeichert wird / Then ist ohne Bestandswert kein `null` im Payload; hatte der Bestand einen Wert und der Zustand ist leer, geht `null` raus, so dass kein stiller Datenverlust entsteht, wo nichts geleert wurde (Regel: `null` nur bei Bestandswert und leerem Zustand, sonst Key weglassen).

## Test Plan

### Automated Tests (TDD RED)

- [ ] Test 1: GIVEN Decode-Ebene des Typs WHEN Bodies `{"f":null}`, `{}`, `{"f":5}` dekodiert werden THEN unterscheidet der Typ die drei Zustände (belegt die `encoding/json`-Annahme).
- [ ] Test 2: GIVEN Trip mit allen 7 Feldern gesetzt WHEN roher Body mit `null` je Feld an `PUT /api/trips/{id}` THEN ist das Feld nach Rücklesen leer, die anderen 6 unverändert (Matrix).
- [ ] Test 3: GIVEN dieselbe Ausgangslage WHEN Body `{}` bzw. Teil-Body ohne die Felder THEN bleiben alle Werte.
- [ ] Test 4: GIVEN Trip WHEN Body mit Wert je Feld THEN Wert gesetzt.
- [ ] Test 5: GIVEN Trip WHEN `{"stages":null}` bzw. `{"name":null}` THEN Bestand bleibt (Wächter).
- [ ] Test 6: GIVEN Router WHEN `PUT /api/briefings/{id}?kind=route` mit `"alert_cooldown_minutes":null` THEN leer.
- [ ] Test 7: GIVEN zwei Nutzer WHEN A leert THEN B unberührt (Trip und Compare).
- [ ] Test 8: GIVEN Compare-Preset WHEN `PUT /api/compare/presets/{id}` mit `null` bzw. ohne Key THEN null leert, fehlt behält (sichert die Server-Annahme für Teil B).
- [ ] Test 9: GIVEN Compare-Editor-Zustand (`node --test`) WHEN Alarm-Pause bzw. Ruhezeit geleert, Bestand hatte Wert, über `buildComparePresetSavePayload`/`baueAlarmNutzlast` THEN steht explizites `null` im Payload.
- [ ] Test 10: GIVEN Compare-Zustand WHEN nur Ruhezeit geändert, Pause 45 unverändert THEN steht Pause 45 im Payload (nicht `null`, nicht fehlend-und-verloren) und bei leerem Zustand ohne Bestandswert fehlt der Key.

### Staging-Nachweis

Trip und Ortsvergleich je: Alarm-Pause setzen, speichern, leeren, speichern, GET ⇒ Feld nicht mehr vorhanden. Zusätzlich: Pause 45, nur Ruhezeit ändern ⇒ Pause bleibt 45. Durchklicken im Alarme-Reiter, nicht nur per API.

## Out of Scope

- `UpdateProfileHandler`, `PatchMetricPresetHandler` (gleiches Muster) ⇒ #1199-Nebenbefunde.
- Python `_trip_to_dict` (lässt None-Felder weg; interner Schreiber für Scheduler-Nachträge, kein Nutzer-Leeren).
- UI zum Leeren von Activity.
- `null` auf Listen, Maps, Structs oder `name` (bleibt "behalten").

## Affected Files

| File | Change Type | Description |
|------|-------------|-------------|
| `internal/handler/optional_field.go` | CREATE | Generischer Drei-Zustands-Typ (fehlt / null / Wert) mit `UnmarshalJSON` |
| `internal/handler/trip.go` | MODIFY | 7 DTO-Felder umstellen, Merge fehlt/null/Wert |
| `internal/handler/trip_optional_clear_test.go` | CREATE | Go-Matrix mit rohen JSON-Bodies, Router-Test, Zwei-Nutzer, Compare-PUT |
| `frontend/src/lib/components/compare/compareEditorSave.ts` | MODIFY | `null` bei Bestandswert und leerem Zustand |
| `frontend/src/lib/components/shared/alarmeVergleichSpeicherung.ts` | MODIFY | Leeren bis zum Payload tragen, ggf. gemeinsame Null-Konvention mit Trip |
| `frontend/src/lib/components/compare/alarmePropsAus.ts` | MODIFY (ggf.) | Leer-Zustand explizit statt `undefined`, falls nötig |
| `frontend/src/lib/components/compare/*.test.ts` (verhaltensbenannt, `node --test`) | CREATE | Payload-Tests über echten Speicherweg |
| `docs/specs/bugfix/update_trip_handler_merge.md` | MODIFY | Nachzug durch Developer: "not actively tested" ⇒ Verweis auf neue Tests; `null` leert nur für die 7 Skalar-Optionals, sonst weiter "behalten" |

## Risks

- **Datenverlust-Richtung (#99/#102):** Leeren darf nur bei explizit gesendetem `null` greifen, nie bei fehlendem Key. Deshalb Matrix in beide Richtungen und die Bestand-Bedingung auf Compare-Seite.
- Andere Trip-PUT-Aufrufer könnten unbeabsichtigt `null` für die 7 Felder senden. Audit: nur der Alarme-Reiter sendet `null`, und dort kommt der Zustand aus dem gespeicherten Trip. Kein weiterer Aufrufer betroffen.
- `fakeTripServer.ts` bildet den Go-Merge nicht nach, Frontend-Tests beweisen die Server-Seite nicht; Nachweis über Go-Handler-Tests und Staging.

## Known Limitations

- Halbes Ruhezeit-Paar wird gespeichert, aber als "keine Ruhezeit" gelesen (AC-10).
- Leerer Cooldown heißt Standard 120 Min, nicht "keine Pause".

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** keine
- **Rationale:** Stellt den bestehenden Kontrakt aus #99 her, keine neue Entscheidungsfläche (Kanäle/Provider/Persistenzmodell bleiben).

## Changelog

- 2026-10-03: Initial spec created (Issue #2211)
