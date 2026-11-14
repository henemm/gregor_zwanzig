---
entity_id: alert_preview_echte_segmente
type: bugfix
created: 2026-11-13
updated: 2026-11-13
status: draft
version: "1.0"
workflow: fix-2069-alert-preview-echte-segmente
tags: [alert-preview, validator, trip, issue-2069]
---

# Alarm-Vorschau rendert echte Trip-Segmente (Issue #2069)

## Approval

- [ ] Approved

## Purpose

Die Alarm-Vorschau (`POST /api/trips/{id}/alert-preview`, dieselbe Logik hinter der Beispiel-Warnung im Alarme-Reiter) soll im Abweichungs-Zweig (`changes`) und im Zweig `official` die echten Etappen-Segmente des Trips verwenden, also genau das zeigen, was auch versendet würde. Unbekannte oder erfundene Segment-IDs werden nicht mehr still akzeptiert, damit weder Nutzer noch Validatoren aus einem selbst erzeugten Fehlen falsche Schlüsse ziehen (#2036, #2020 S2).

## Source

- **File:** `api/routers/validator.py` (Endpoint `alert_preview`, ID-Prüfung, `segment_times`-Synthese)
- **File:** `src/services/validator_render_service.py` (`_deviation_preview_message`, `_render_official_preview`, `_stub_segment`)
- **Identifier:** `alert_preview`, `_reject_unknown_segment_id`, `_synthesize_segment_times`, neu `preview_reference_date`

> **Schicht:** Python-Core (`api/`, `src/services/`) plus Frontend `frontend/src/lib/components/alerts-tab/` (gleiche Komponente `AlertPreviewCard.svelte`). Go-API unverändert (reiner Proxy).
>
> **Trip/Ortsvergleich-Teilung:** Der Hinweis wird in der bestehenden Komponente `AlertPreviewCard` ergänzt (Pendant zu `alert-preview-no-locations`), keine neue Komponente.
>
> **Mandantentrennung:** Der Trip wird weiterhin user-scoped über `_load_trip_for_validator` geladen (`user_id` aus Auth-Kontext, nie `"default"`). Der Bezugstag und alle Segmente stammen aus dem Trip des anfragenden Nutzers. Zwei-Nutzer-Test in AC-9.
>
> **Kanäle:** Alle vier Ausgaben (E-Mail, Telegram, SMS, Premium-SMS) und der Betreff entstehen weiter aus demselben Nachrichtenobjekt; Inhalt identisch, Form kanalgerecht (unverändert, durch AC-1/AC-2 mitgeprüft).

## Scope

- **LoC:** ca. +180/-60 (davon ca. 100 Tests)
- **Files:** ca. 8 Code/Test plus 3 Doku
- **Effort:** medium

### Affected Files

| File | Change Type | Description |
|------|-------------|-------------|
| `api/routers/validator.py` | MODIFY | ID-Prüfung und `segment_times`-Synthese auf Bezugstag; leere Menge bei genannter `segment_id` ⇒ 422 `trip_ohne_segmente`; Antwort um `bezugstag`, `stundenreihe` |
| `src/services/validator_render_service.py` | MODIFY | Rückfallpfad rendert echte `TripSegment`s des Bezugstags statt `_stub_segment`; `official` mit `segment_km=measured_segment_km(...)` |
| `src/services/trip_day.py` | MODIFY | Neu `preview_reference_date(trip, now)`: heute, sonst nächste Etappe, sonst letzte |
| `src/i18n/messages/de/api.json`, `src/i18n/messages/en/api.json` | MODIFY | Fehlercode `trip_ohne_segmente` (Katalog-Parität) |
| `frontend/src/lib/components/alerts-tab/AlertPreviewCard.svelte` (+ i18n-Katalog) | MODIFY | Hinweis statt Fehlertext bei Trip ohne Etappe mit mindestens 2 Wegpunkten |
| `tests/tdd/test_alert_preview_echte_segmente.py` | CREATE | RED-Tests zu AC-1 bis AC-9 |
| `tests/tdd/test_alert_preview_payload_exclusivity.py`, `tests/tdd/test_alert_preview_input_validation.py`, `tests/tdd/test_alert_preview_official_render.py`, `tests/tdd/test_alert_preview_no_side_effects.py`, `tests/integration/test_issue_221_validator_endpoints.py` (und weitere der ca. 13 Dateien mit `stages: []`) | MODIFY | Testmigration der `stages: []`-Fixtures auf Trips mit Etappe (`tests/helpers/ortstag.py`) |
| `docs/reference/api_contract.md` | MODIFY | Alarm-Vorschau-Vertrag: Bezugstag, neue Felder, neuer Fehlercode |
| `docs/specs/modules/issue_221_validator_observability_endpoints.md` | MODIFY | Stub-Zuschnitt (Z. 48, 190) und Rückgabeform (Z. 248) nachziehen |
| `.claude/agents/external-validator.md` | MODIFY | Warnung zum Messaufbau anpassen |

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `convert_trip_to_segments` (`src/services/trip_segments.py`) | function | echte Segmente (Distanz, Höhenmeter, Koordinaten, `distance_measured`) für den Bezugstag |
| `measured_segment_km` (`src/services/trip_segments.py`) | function | gemessene km-Spanne, wie im Versand (`trip_alert.py`) |
| `trip_local_today` (`src/services/trip_day.py`) | function | Ortstag in der Trip-Zone |
| `Trip.get_stage_for_date` | method | Etappe je Datum |
| `trip_preview_series` (`src/services/alert_preview_hours.py`) | function | Anker-Pfad #1737 (unverändert) |
| `to_alert_message` | function | Renderer, ein Nachrichtenobjekt für alle Kanäle |
| `build_official_alert_notices` (`src/output/renderers/alert/official_alerts.py`) | function | nur aufrufen, nicht ändern (#1929-Sperrzone) |
| `api_fehler` und i18n-Katalog `api.json` | module | 422-Fehler mit Code, de/en-Parität (`tests/test_i18n_api_katalog_paritaet.py`) |

## Implementation Details

**1. Bezugstag (eine Quelle).** `preview_reference_date(trip, now)` liefert: heute (Ortstag, `trip_local_today`), wenn der Trip heute eine Etappe hat; sonst das Datum der nächsten kommenden Etappe; sonst das Datum der letzten Etappe; `None`, wenn der Trip keine Etappe hat. ID-Prüfung, `segment_times`-Synthese und Rendering rufen ausschließlich diese Funktion auf, es gibt keine zweite „heute"-Ermittlung mehr. Als Etappe zählt dabei nur eine auswertbare Etappe, also eine mit mindestens 2 Wegpunkten (dieselbe Regel wie der Hinweis in `AlertPreviewCard`); eine Etappe mit nur einem Wegpunkt wird bei der Wahl des Bezugstags übersprungen, hat der Trip keine auswertbare Etappe, ist das Ergebnis `None`.

**2. `changes`-Rückfall.** Gibt es keinen Anker bzw. keine Stundenreihe (Anker-Pfad #1737 bleibt unverändert und hat Vorrang), rendert `_deviation_preview_message` die echten `TripSegment`s aus `convert_trip_to_segments(trip, bezugstag)`, beschränkt auf die im Payload genannten `segment_id`s. `segment_times` aus dem Payload überschreiben nur Start und Ende; das Datum ist der Bezugstag in der Trip-Zone (nicht UTC-heute). Distanz, Höhenmeter, Koordinaten, `distance_measured` und km-Spanne bleiben die echten Werte. `_stub_segment` entfällt für diesen Pfad.

**3. `official`-Zweig.** `segment_km = measured_segment_km(<Segmente des Bezugstags>)` wird an `build_official_alert_notices` übergeben, wie im Versand. `segment_ids=[]` bleibt erlaubt.

**4. ID-Prüfung.** Unbekannte `segment_id` ⇒ 422 mit bestehendem Code. Hat der Trip gar keine auswertbaren Etappen/Wegpunkte und der Payload nennt eine `segment_id` (`changes`, oder `official` mit nicht-leerer `segment_ids`) ⇒ 422 mit neuem Code `trip_ohne_segmente` (de/en). Der bisherige stille No-Op bei leerer Menge entfällt.

**5. Antwort additiv.** Zusätzliche Felder `bezugstag` (ISO-Datum, `null` wenn kein Bezug nötig, z. B. `onset`/Compare) und `stundenreihe` (bool: lag eine echte Stundenreihe über den Anker-Pfad vor). Bestehende Felder unverändert, bricht keine Clients.

**6. Tagesbezug im Alarmtext (Festlegung).** Der Text bezieht sich auf den Bezugstag so, wie er im Versand an diesem Tag lauten würde: Das Segmentdatum ist der Bezugstag, und relative Tageswörter („heute", „morgen", Wochentag) werden relativ zum Bezugstag als Versandtag berechnet, nicht relativ zum realen Heute. Eine Vorschau für einen Trip, der in drei Tagen startet, darf also nie „morgen" für den Bezugstag sagen, sondern formuliert wie ein Versand am Bezugstag selbst. Umsetzung: das Segmentdatum und der Referenz-Zeitpunkt des Renderers kommen beide aus dem Bezugstag. Testbar durch Vergleich der Vorschau mit einem direkten Render derselben Segmente mit Referenztag = Bezugstag.

**7. Frontend.** `AlertPreviewCard` zeigt bei einem Trip ohne Etappe mit mindestens 2 Wegpunkten einen Hinweistext (eigener `data-testid`, Pendant zu `alert-preview-no-locations`) und ruft den Endpoint nicht ab. Trips mit Etappen, auch geplante (nicht heute laufende), liefern weiter die Beispiel-Warnung. `buildAlertPreviewPayload` bleibt unverändert (`segment_id: '1'`).

**Nicht im Zuschnitt:** `onset`-Zweig (Payload ist das synthetische Ereignis), Compare-Zweig, Änderungen an `official_alerts.py`.

## Expected Behavior

- **Input:** Alarm-Vorschau-Payload (`changes`, `official` oder `onset`) für einen Trip des angemeldeten Nutzers.
- **Output:** Alarmnachricht (alle Kanäle) auf Basis echter Segmente des Bezugstags; Antwort zusätzlich mit `bezugstag` und `stundenreihe`.
- **Side effects:** keine (Vorschau versendet nichts, bleibt seiteneffektfrei).

## Test Plan

### Automated Tests (TDD RED)

Datei `tests/tdd/test_alert_preview_echte_segmente.py`, echter Endpoint mit echten Trip-Dateien im Test-Datenverzeichnis, keine Mocks.

- [ ] Test 1: GIVEN Trip mit Etappe heute, kein Anker WHEN `changes`-Vorschau THEN Nachricht enthält echte Distanz/km-Spanne statt 0.
- [ ] Test 2: GIVEN Trip mit Etappe erst in 5 Tagen WHEN `changes`-Vorschau THEN 200 mit `bezugstag` = Etappendatum und echten Werten.
- [ ] Test 3: GIVEN Trip, dessen letzte Etappe vorbei ist WHEN Vorschau THEN `bezugstag` = letzte Etappe.
- [ ] Test 4: GIVEN Trip mit Etappen WHEN `official`-Vorschau THEN gemessene km-Spanne erscheint im Text, identisch zu direktem Aufruf mit `measured_segment_km`.
- [ ] Test 5: GIVEN Trip mit Etappen WHEN erfundene `segment_id` THEN 422 mit bestehendem Code, auch bei nicht heute laufendem Trip.
- [ ] Test 6: GIVEN Trip ohne Etappen (`stages: []`) WHEN Payload nennt `segment_id` THEN 422 `trip_ohne_segmente`; `official` mit `segment_ids=[]` bleibt 200.
- [ ] Test 7: Tagesbezug-Vergleich Bezugstag ≠ heute gegen Direkt-Render mit Referenztag = Bezugstag.
- [ ] Test 8: Zwei Nutzer, gleiche Trip-ID-Struktur, unterschiedliche Etappen ⇒ jeder sieht nur eigene Werte; fremde Trip-ID bleibt abgelehnt (`test_preview_alert_preview_reject_foreign_trip_id.py` bleibt grün).
- [ ] Test 9: Katalog-Parität de/en für `trip_ohne_segmente`.
- [ ] Test 10: Frontend (`node --test` bzw. Playwright E2E): Hinweis bei Trip ohne Etappe, Beispiel-Warnung bei geplantem Trip.

## Definition of Done

- [ ] AC-1 bis AC-10 durch automatisierte Tests grün nachgewiesen (Kern-Schicht ohne Netz, ohne Mocks)
- [ ] Beispiel-Warnung im Alarme-Reiter auf Staging für einen geplanten Trip mit echten Kilometern/Höhenmetern sichtbar, für einen Trip ohne Etappe mit Hinweis statt Fehlertext
- [ ] Erfundene `segment_id` liefert auf Staging 422, auch bei einem nicht heute laufenden Trip
- [ ] `api_contract.md`, Spec #221 und `external-validator.md` nachgezogen; Katalog-Parität de/en grün

## Acceptance Criteria

- **AC-1:** Given ein Trip hat heute eine Etappe und es gibt keinen tagesgleichen Anker bzw. keine Stundenreihe / When die Alarm-Vorschau im Abweichungs-Zweig mit `segment_id` und `segment_times` abgerufen wird / Then zeigen alle Kanäle und der Betreff die echte Distanz, Höhenmeter und km-Spanne der Etappe (nicht 0) und `stundenreihe` ist `false`.
  - Test: Trip-Datei mit Etappe anlegen, Endpoint aufrufen, in der Antwort die echte km-Spanne der Etappe finden und prüfen, dass sie nicht 0 ist.

- **AC-2:** Given ein Trip hat heute keine Etappe, aber eine kommende / When die Alarm-Vorschau im Abweichungs-Zweig abgerufen wird / Then antwortet der Endpoint mit 200, `bezugstag` ist das Datum der nächsten Etappe und die Nachricht nutzt deren echte Segmentwerte; liegen alle Etappen in der Vergangenheit, ist `bezugstag` das Datum der letzten Etappe.
  - Test: geplanten Trip (Etappe in 5 Tagen) und vergangenen Trip anlegen, jeweils Endpoint aufrufen, `bezugstag` und Segmentwerte prüfen.

- **AC-3:** Given ein Trip mit Etappen / When die Vorschau im Zweig `official` abgerufen wird / Then enthält die amtliche Warnung dieselbe gemessene km-Spanne wie der echte Versand (`measured_segment_km` der Segmente des Bezugstags), bei `segment_ids=[]` weiterhin ohne Fehler.
  - Test: Endpoint im Zweig `official` aufrufen und die km-Spanne im Text mit dem erwarteten Wert aus den Segmenten des Trips vergleichen.

- **AC-4:** Given ein Trip mit Etappen / When der Payload eine `segment_id` nennt, die im Bezugstag nicht existiert (auch bei einem nicht heute laufenden Trip) / Then antwortet der Endpoint mit 422 und dem bestehenden Fehlercode, nie mit einer stillen Vorschau.
  - Test: erfundene `segment_id` (z. B. `"99"`) an Trip mit Etappe in der Zukunft senden, 422 erwarten.

- **AC-5:** Given ein Trip ohne auswertbare Etappen oder Wegpunkte / When der Payload eine `segment_id` nennt (`changes`, oder `official` mit nicht-leerer `segment_ids`) / Then antwortet der Endpoint mit 422 und dem neuen Code `trip_ohne_segmente`, in Deutsch und Englisch mit gleichem Katalogeintrag (Parität).
  - Test: Trip mit `stages: []` anlegen, Endpoint aufrufen, 422 mit Code `trip_ohne_segmente` und passende de/en-Meldung prüfen.

- **AC-6:** Given eine Vorschau mit Bezugstag, der nicht heute ist / When die Nachricht gerendert wird / Then lautet der Tagesbezug im Text wie bei einem Versand an diesem Bezugstag (relative Tageswörter und Wochentag relativ zum Bezugstag, Segmentdatum in Trip-Zone), nie „morgen" oder „heute" relativ zum realen Heute.
  - Test: Vorschau für Trip mit Etappe in 3 Tagen abrufen und Text mit direktem Render derselben Segmente mit Referenztag = Bezugstag vergleichen (gleicher Tagesbezug).

- **AC-7:** Given eine erfolgreiche Alarm-Vorschau / When die Antwort gelesen wird / Then enthält sie additiv `bezugstag` (ISO-Datum) und `stundenreihe` (bool), und alle bisherigen Felder sind unverändert vorhanden; mit Anker und Stundenreihe (#1737) ist `stundenreihe` `true` und das Ergebnis identisch zu vorher.
  - Test: Antwort auf neue Felder und auf unveränderte Altfelder prüfen; Anker-Pfad-Test (#1737) bleibt grün.

- **AC-8:** Given ein Nutzer öffnet den Alarme-Reiter eines Trips, der keine einzige Etappe mit mindestens 2 Wegpunkten hat / When die Beispielwarnung angezeigt werden soll / Then sieht er in `AlertPreviewCard` einen Hinweis („Trip hat noch keine Etappen mit Wegpunkten") statt eines Fehlertexts und es erfolgt kein Abruf; bei einem geplanten, nicht heute laufenden Trip mit Etappen erscheint die Beispiel-Warnung weiterhin.
  - Test: Playwright E2E gegen Staging bzw. lokalen Stack: Trip ohne Etappe öffnen und Hinweis sichtbar prüfen; geplanten Trip öffnen und Beispielwarnung sichtbar prüfen.

- **AC-9:** Given zwei verschiedene Nutzer mit je einem eigenen Trip (unterschiedliche Etappen) / When beide die Alarm-Vorschau abrufen oder Nutzer B die Trip-ID von Nutzer A nennt / Then sieht jeder nur Segmente, Bezugstag und km-Spanne des eigenen Trips, und der Zugriff auf die fremde Trip-ID bleibt abgelehnt.
  - Test: zwei Nutzer mit getrennten Trip-Daten anlegen, Endpoint je Nutzer aufrufen, Werte vergleichen und fremde ID prüfen.

- **AC-10:** Given die bestehenden Tests mit `stages: []` und `segment_id` im `changes`/`official`-Payload / When sie auf Trips mit Etappe (`tests/helpers/ortstag.py`) umgestellt sind / Then laufen alle Alarm-Vorschau-Testdateien grün, und `onset`- und Compare-Zweig verhalten sich unverändert.
  - Test: die migrierten Testdateien (Payload-Exklusivität, Eingabeprüfung, official-Render, Seiteneffekte, #221-Endpoints) mit benannten Dateien ausführen.

## Known Limitations

- Ohne Anker (Trip läuft nicht heute, Cache leer, Abruf scheitert) bleibt die Stundenreihe leer; das ist jetzt über `stundenreihe: false` erkennbar statt still.
- `onset`-Zweig nimmt `km_from/km_to` weiter aus dem Payload; Plausibilisierung gegen die Trip-Länge ist ein eigenes Thema.
- Compare-Zweig unverändert.
- Segment-IDs sind je Tag `1..N`; das Frontend sendet fest `'1'`, das passt zu jedem Bezugstag mit mindestens 2 Wegpunkten.

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** keine
- **Rationale:** Konsequenz aus #1737/#918 (Vorschau zeigt, was versendet würde); keine neue Entscheidungsfläche (Kanäle, Provider, Datenmodell, Auth).

## Changelog

- 2026-11-13: Initial spec created (Issue #2069)
- 2026-11-14: Fix-Loop 1 (Adversary F005): Bezugstag berücksichtigt nur auswertbare Etappen (mindestens 2 Wegpunkte), Implementation Details 1 ergänzt.
