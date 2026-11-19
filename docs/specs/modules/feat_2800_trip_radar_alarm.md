---
entity_id: feat_2800_trip_radar_alarm
type: feature
created: 2026-11-19
updated: 2026-11-19
status: draft
version: "1.0"
workflow: feat-2800-trip-radar-alarm
tags: [einstellungen-neu, radar, alarm, trip, S8, "#2800", "#2791"]
---

# Trip-Radar-Alarm-Schalter (Einstellungen neu, Scheibe S8)

## Approval

- [ ] Approved

## Purpose

Der Radar-Regen-Alarm („Regen in der nächsten Stunde auf deiner Etappe") läuft für Trips bereits seit #822, aber für jeden Trip ohne Schalter. Diese Scheibe macht ihn pro Trip ein- und ausschaltbar (Reiter Wetter, Karte „Amtliche Warnungen & Radar"), ohne dass Bestandstrips ihren laufenden Alarm verlieren, und sichert die vorhandene Fachlogik (alle vier Kanäle, Stille Stunden) per Abnahmekriterien ab.

## Source

- **File:** `src/services/trip_alert.py`
- **Identifier:** `TripAlertService._check_radar_trips` (Schalter-Prüfung), Feld `Trip.radar_alert_enabled` in `src/app/trip.py`, Go-Pendant in `internal/model/trip.go` und `internal/handler/trip.go`, Frontend-Wetter-Reiter unter `frontend/src/lib/components/`

> **Schicht-Hinweis:** Alle drei Schichten sind betroffen. Python-Core (`src/app/`, `src/services/`), Go-API (`internal/model/`, `internal/handler/`, Persistenz ohne Catch-all, daher Feld zwingend nötig) und SvelteKit-Frontend (`frontend/src/lib/`).

> **Trip/Ortsvergleich-Teilung:** Der Wetter-Reiter ist bereits geteilt (`context="route"|"vergleich"`, ADR-0097/0109). Es entsteht keine neue Komponente; `MIT_RADAR.route` wird auf `true` gesetzt, der Text wird je Kontext gewählt. Keine einseitige Neuanlage.

> **Mandantentrennung:** Das Feld wird über den PUT-Pfad des Trips geschrieben (`user_id` aus dem Auth-Kontext). Test mit zwei verschiedenen Nutzern.

> **Kanäle:** Der Radar-Alarm erreicht alle vier Kanäle (E-Mail, Telegram, SMS, Premium-SMS) mit gleichem Inhalt (ADR-0095); der Schalter gilt für alle Kanäle gleichzeitig.

## Estimated Scope

- **LoC:** Produktiv ca. +70, Tests ca. +200, Doku ca. +40
- **Files:** ca. 21 (laut Tabelle unten, inkl. Doku und Tests)
- **Effort:** medium (Risiko MEDIUM: Go/Python-Drift, Default-Asymmetrie Trip/Compare, Elementlisten- und Alt-AC-Tests)

### Affected Files

| File | Change Type | Description |
|------|-------------|-------------|
| src/app/trip.py | MODIFY | Feld `radar_alert_enabled: Optional[bool] = None` |
| src/app/loader.py | MODIFY | Lesen, Schreiben nur wenn nicht None, `KNOWN_TOP_LEVEL` ergänzen |
| src/services/trip_alert.py | MODIFY | Schalter-Prüfung in `_check_radar_trips` vor Segmentwahl, Kanal-Auflösung und Nowcast-Abruf |
| internal/model/trip.go | MODIFY | `RadarAlertEnabled *bool` mit `json:"radar_alert_enabled,omitempty"` |
| internal/handler/trip.go | MODIFY | PUT-Request `Optional[bool]` plus `ApplyPtr` (Dreizustand, Read-Modify-Write) |
| internal/model/trip_schema_drift_test.go | MODIFY | Drift-Gate Go-Seite |
| tests/test_trip_schema_drift.py | MODIFY | Drift-Gate Python-Seite |
| internal/handler/trip_radar_alert_enabled_test.go | CREATE | PUT-Dreizustand, zwei Nutzer (Vorbild `trip_official_alerts_test.go`) |
| tests/tdd/test_trip_radar_schalter.py | CREATE | aus = kein Nowcast-Abruf und kein Versand; None/True = Lauf; Kanäle; Stille Stunden |
| frontend/src/lib/types.ts | MODIFY | Trip-Typ `radar_alert_enabled?: boolean` |
| frontend/src/lib/components/organisms/wetter-tab/WetterTabInhalt.svelte | MODIFY | `MIT_RADAR.route = true` |
| frontend/src/lib/components/shared/wetter-tab/wetterZustand.ts | MODIFY | kontextabhängiger Default (route `!== false`, vergleich `=== true`) |
| frontend/src/lib/components/shared/wetter-tab/ampelSchreiben.ts, wetterTabSpeicherung.ts | MODIFY | Trip-Speicherpfad schreibt `radar_alert_enabled` |
| frontend/src/lib/components/organisms/wetter-tab/WarnungenRadarKarte.svelte, warnungenRadarZeilen.ts | MODIFY | Trip-Text „deine Etappe" |
| frontend/src/lib/i18n/messages/de/wetter.json, en/wetter.json | MODIFY | neuer Beschreibungstext Trip („deine Etappe" / „your stage") |
| docs/context/einstellungen_neu/elementliste_freigaben.json | MODIFY | Freigabe „Trip ohne Radar" entfernen |
| frontend/src/lib/__tests__/elementliste_abgleich_fixloop2.test.ts | MODIFY | gleichzeitig mit der Freigabe angepasst |
| docs/specs/modules/feat_2794_s3a_reiter_wetter.md | MODIFY | AC-21 als abgelöst durch #2800 markieren |
| docs/specs/modules/feat_2913_scheibe_c_wetter_rest.md | MODIFY | AC-3/AC-9 als abgelöst durch #2800 markieren |
| docs/reference/api_contract.md | MODIFY | Trip-DTO §10.5 und Dreizustandsliste |
| docs/context/einstellungen_neu.md | MODIFY | „nur Ortsvergleich" korrigieren |

Nicht im Umfang: #3186 (pausierte Trips bekommen weiter Alarme, betrifft alle Trip-Alarmarten) und Test-Alarm S5 (#2797, testet den Kanal und umgeht den Schalter bewusst).

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| TripAlertService.check_radar_alerts_run | service | bestehender Trip-Radarlauf (#822), erhält die Schalter-Prüfung |
| RadarNowcastService | service | Nowcast-Abruf, darf bei Schalter aus nicht aufgerufen werden (ADR-0082-Budget) |
| check_nowcast_gate | function | Gate Stille Stunden, Cooldown, Tageslimit (unverändert) |
| alert_channels.resolve_alert_channels / effective_alert_channels | module | Kanal-Auflösung auf alle vier Kanäle (ADR-0095) |
| NotificationService.send_radar_alert | service | Versand der Radar-Mail bzw. Kurzform |
| compare_radar_alert.py | module | Vorbild des Schalters (Default aus, bleibt unverändert) |
| amtliche_warnungen_schalter.py / official_alerts_enabled | module | Vorbild für Default „None = an" |
| radar_alert_mail_validator.py | hook | Mail-Validator, Exit 0 gegen echte Staging-Mail |
| api/routers/debug.py | router | Debug-Trigger Trip-Radar für Staging-E2E |
| i18n-Kataloge wetter.json DE/EN | catalog | Nutzertexte (ADR-0104) |
| ADR-0082, 0095, 0096, 0102, 0109 | adr | Budget, Kanalparität, Radar-Onset, GPS-Fix, Reiter-Ordnung |

## Implementation Details

Der Radarlauf bleibt fachlich unverändert: aktives bzw. nächstes Segment über `resolve_current_segment` (ADR-0044, Etappe des Tages nach Ortszeit), Punkte mit Durchgangszeit nach Naismith-Tempo, plausibler GPS-Fix übersteuert die Planposition (ADR-0102), Abrufbegrenzung über Takt `3-58/5`, `RADAR_RUN_DEADLINE_SECONDS` und faire Reihenfolge (ADR-0082/0117). Keine neue Fachlogik.

Änderungen:

1. **Modell:** `radar_alert_enabled: Optional[bool] = None` am Trip (Python), `*bool` mit `omitempty` in Go, Loader schreibt das Feld nur, wenn es nicht None ist. PUT nutzt den Dreizustand (`Optional[bool]` plus `ApplyPtr`): fehlt das Feld, bleibt der Bestand; true/false setzt es. Drift-Tests beidseitig.
2. **Default am Trip: None bedeutet AN** (`radar_alert_enabled is not False`), Vorbild `official_alerts_enabled`. Begründung: Der Radarlauf läuft heute für jeden Trip; None = aus würde Bestandstrips ohne Migration still verstummen lassen. **Dokumentierte Abweichung:** Beim Ortsvergleich bleibt None = aus (`compare_radar_alert.py`). Beides steht in `api_contract.md`.
3. **Prüfung:** in `_check_radar_trips` direkt nach dem Setzen des „zuletzt erreicht"-Stempels, als `continue` im `try`, also vor Segmentwahl, Kanal-Auflösung und Nowcast-Abruf. Der Zähler `progress["checked"]` und die faire Reihenfolge bleiben unberührt.
4. **Frontend:** `MIT_RADAR.route = true`; in `wetterZustand.ts` liest `route` den Zustand mit `!== false`, `vergleich` weiter mit `=== true`. Der Trip-Speicherpfad schreibt `radar_alert_enabled` mit dem Zustand des Reiters (Read-Modify-Write; ein Bestandstrip ohne Feld wird als „an" gelesen und nicht still auf false geschrieben). Eigener Trip-Text über den i18n-Katalog (DE „… auf deiner Etappe", EN „… on your stage"), Protokoll-Token bleiben unübersetzt.
5. **Aufräumen:** Elementlisten-Freigabe „Trip ohne Radar" und der zugehörige Test werden gleichzeitig entfernt; Alt-ACs feat_2794 AC-21 und feat_2913 AC-3/AC-9 werden als „abgelöst durch #2800" markiert und ihre Frontend-Tests angepasst.

## Expected Behavior

- **Input:** Trip mit `radar_alert_enabled` = true, false oder nicht gesetzt; Nowcast-Daten für Punkte der aktuellen Etappe.
- **Output:** Bei an: Radar-Alarm an alle effektiven Alarm-Kanäle des Nutzers, sobald in der nächsten Stunde Regen einsetzt und das Gate offen ist. Bei aus: kein Abruf, kein Versand.
- **Side effects:** Gate-Zustand (Cooldown, Tageslimit) wird nur bei tatsächlichem Versand fortgeschrieben; „zuletzt erreicht"-Stempel auch bei aus.

## Test Plan

### Automated Tests (TDD RED)

- [ ] Test 1: GIVEN Trip mit `radar_alert_enabled=false` und Regen-Onset WHEN der Radarlauf läuft THEN kein Nowcast-Abruf und kein Versand (Python, `tests/tdd/test_trip_radar_schalter.py`)
- [ ] Test 2: GIVEN Trip ohne gesetztes Feld und mit `true` WHEN Regen-Onset auf der Etappe THEN Alarm an alle effektiven Kanäle (Python)
- [ ] Test 3: GIVEN Stille Stunden aktiv WHEN Radar-Onset THEN Alarm zurückgehalten, außerhalb der Stillen Stunden zugestellt (Python)
- [ ] Test 4: GIVEN PUT mit true, false und ohne Feld WHEN Bestandstrip gespeichert wird THEN Dreizustand (Bestand bleibt bei fehlendem Feld), Go-Test `trip_radar_alert_enabled_test.go`
- [ ] Test 5: GIVEN zwei Nutzer WHEN Nutzer A seinen Trip-Schalter setzt THEN bleibt der Trip von Nutzer B unverändert und ist nicht abrufbar (Go)
- [ ] Test 6: Drift-Gates `internal/model/trip_schema_drift_test.go` und `tests/test_trip_schema_drift.py` laufen grün: ein Trip mit `radar_alert_enabled` übersteht Laden und Speichern auf beiden Seiten (Go-Store und Python-Loader) unverändert
- [ ] Test 7: Frontend (`node --test`): Trip-Reiter Wetter zeigt die Radar-Zeile mit „deine Etappe"; Bestandstrip ohne Feld erscheint als an; Umschalten schreibt `radar_alert_enabled`; Vergleich bleibt bei None aus
- [ ] Test 8: Staging-E2E über Debug-Trigger: Seed-Trip an = Mail, Validator `radar_alert_mail_validator.py` Exit 0; Gegenprobe aus = keine Mail

## Acceptance Criteria

- **AC-1:** Given ein Trip mit eingeschaltetem Radar-Alarm und einem Regen-Beginn in der nächsten Stunde auf der aktuellen Etappe / When der Radarlauf läuft / Then erhält der Nutzer den Radar-Alarm auf allen seinen Alarm-Kanälen (E-Mail, Telegram, SMS, Premium-SMS) mit gleichem Inhalt
  - Test: Radarlauf mit gestelltem Nowcast und allen vier Kanälen konfiguriert; je Kanal wird genau ein Alarm zugestellt.

- **AC-2:** Given eine Trip-Mail zum Radar-Alarm auf Staging / When der Radar-Mail-Validator gegen die zugestellte Mail läuft / Then endet er mit Exit 0 (Etappe, Uhrzeit, Intensität und Cooldown stimmen)
  - Test: Debug-Trigger löst Alarm für einen Seed-Trip aus, Mail im Stalwart-Test-Postfach, `radar_alert_mail_validator.py` Exit 0.

- **AC-3:** Given ein Trip mit ausgeschaltetem Radar-Alarm und einem Regen-Beginn auf der Etappe / When der Radarlauf läuft / Then wird weder Wetterradar abgefragt noch ein Alarm auf irgendeinem Kanal gesendet
  - Test: Radarlauf mit `radar_alert_enabled=false`; Nowcast-Dienst erhält keinen Aufruf, Versandprotokoll bleibt leer; Staging-Gegenprobe ohne Mail.

- **AC-4:** Given ein Bestandstrip, bei dem der Schalter nie gesetzt wurde / When der Radarlauf läuft und es regnen wird / Then wird der Alarm wie bisher gesendet, der Trip verstummt nicht still
  - Test: Trip ohne Feld `radar_alert_enabled` löst Alarm aus; im Ortsvergleich bleibt derselbe Zustand „nicht gesetzt" dagegen aus.

- **AC-5:** Given ein eingeschalteter Radar-Alarm und aktive Stille Stunden des Nutzers / When ein Regen-Beginn erkannt wird / Then wird der Alarm zurückgehalten und nicht sofort zugestellt
  - Test: Radarlauf mit gestellter Uhr in den Stillen Stunden; kein Versand, Gate meldet „zurückgehalten".

- **AC-6:** Given ein Nutzer öffnet im Trip den Reiter Wetter, Karte „Amtliche Warnungen & Radar" / When er die Radar-Zeile sieht und umschaltet / Then lautet der Text „deine Etappe" (EN „your stage"), ein Bestandstrip steht auf „an", und der gewählte Zustand bleibt nach Speichern und Neuladen erhalten
  - Test: Frontend-Test und Playwright auf Staging: Zeile sichtbar, Umschalten auf aus, Speichern, Neuladen zeigt aus; EN-Sprache zeigt „your stage".

- **AC-7:** Given ein Trip mit gespeichertem Schalter / When er per PUT ohne das Feld, mit true oder mit false gespeichert wird / Then bleibt der Wert bei fehlendem Feld erhalten, sonst wird er gesetzt, und andere Trip-Felder gehen nicht verloren
  - Test: Go-Handler-Test mit drei Fällen gegen den echten Store; Drift-Tests Go und Python: ein Trip mit gesetztem Schalter (true und false) kommt nach Speichern und Laden auf beiden Seiten mit demselben Wert zurück.

- **AC-8:** Given zwei verschiedene Nutzer mit je einem Trip / When Nutzer A den Radar-Alarm seines Trips ausschaltet / Then bleibt der Trip von Nutzer B unverändert und für A nicht erreichbar
  - Test: Go-Handler-Test mit zwei Nutzer-Kontexten; Zugriff von A auf B liefert nicht gefunden.

- **AC-9:** Given die Elementliste der Einstellungen und die Alt-Specs feat_2794 AC-21 sowie feat_2913 AC-3/AC-9 / When der Elementlisten-Abgleich läuft / Then gibt es keine freigegebene Abweichung „Trip ohne Radar" mehr, und die Alt-ACs sind als abgelöst durch #2800 markiert
  - Test: Elementlisten-Abgleich-Test (`node --test`) grün: der Abgleich verlangt für den Trip-Kontext die Radar-Zeile im gerenderten Wetter-Reiter und meldet sie ohne Freigabe als vorhanden.

## Scope

- **Im Umfang:** Schalter `radar_alert_enabled` am Trip (Python, Go, PUT-Dreizustand, api_contract, Drift-Tests), Schalterprüfung im Trip-Radarlauf vor dem Nowcast-Abruf, Radar-Zeile im Trip-Reiter Wetter (Karte „Amtliche Warnungen & Radar") mit Text DE/EN, Trip-Speicherpfad, Aufräumen der Elementlisten-Freigabe und der abgelösten Alt-ACs, Staging-Nachweis mit Radar-Mail-Validator.
- **Nicht im Umfang:** neue Fachlogik für Punktwahl, Tempo, GPS-Fix oder Abrufbegrenzung (bleibt aus #822/#2480/#2261); pausierte Trips (#3186); Test-Alarm für Radar. Der Test-Alarm entsteht erst in S5 (#2797, noch offen); das Issue sieht die Abdeckung ausdrücklich erst vor, „sobald beide da sind“. Die Pflicht ist in #2797 vermerkt.

## Definition of Done

- AC-1 bis AC-9 grün, Adversary VERIFIED inklusive Mutations-Gegenprobe (Schalterprüfung entfernt, Default auf aus gedreht, Dreizustand durch Replace ersetzt).
- Staging: echte Trip-Radar-Mail, `radar_alert_mail_validator.py` Exit 0; Gegenprobe Schalter aus ohne Mail.
- Auslieferung mit allen CI-Checks grün, Prod-Deploy und Selftest Exit 0.

## Known Limitations

- Pausierte Trips erhalten weiterhin Alarme (#3186, alle Trip-Alarmarten, bewusst außerhalb dieser Scheibe).
- Der Test-Alarm (S5, #2797) prüft den Kanal und umgeht den Schalter bewusst.
- Default-Asymmetrie: Trip None = an, Ortsvergleich None = aus (dokumentiert in `api_contract.md`).
- Staging-Mailweg war zeitweise gestört (#2774); E2E-Nachweis benennt ehrlich, was lokal und was auf Staging gemessen wurde.

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** keine
- **Rationale:** Es wird kein bestehender Entscheid geändert. Der Schalter folgt dem Muster `official_alerts_enabled` (None = an) und ADR-0095 (alle Kanäle); die Default-Asymmetrie zu Compare ist durch die Bestandslage begründet und in Spec und API-Contract festgehalten. Prüfung vor dem Abruf wahrt ADR-0082.

## Changelog

- 2026-11-19: Initial spec created (Issue #2800, Epic #2791, Scheibe S8)
- 2026-11-19: Abschnitte Scope und Definition of Done ergänzt; Test-Alarm-Abdeckung an S5 (#2797) verwiesen
