---
entity_id: feat_3373_sms_beispiel_karte
type: bugfix
created: 2026-11-25
updated: 2026-11-25
status: draft
version: "1.0"
workflow: feat-3373-sms-beispiel-karte
tags: [was-steht-wo, sms, beispiel, trip, epic-3122]
---

# SMS-Beispiel der Trip-Karte „Was steht wo“ gleich dem echten Versand

## Approval

- [ ] Approved

## Purpose

Das SMS-Beispiel der Trip-Karte „Was steht wo“ muss zeichengleich mit der SMS sein, die der Versand wirklich schickt (AC-17 von `feat_3122_was_steht_wo.md`). Heute weichen Kopf, Nachtwert, Spitzen und Folgetag-Gewitter ab, und die Zeile „Temperatur“ zeigt Token ihrer Kinder doppelt und trägt einen SMS-Haken ohne Wirkung. Der Versand selbst ist richtig und bleibt unverändert.

## Source

- **File:** `src/services/placements_view_service.py`
- **Identifier:** `_trip_muster`, `_trip_sms_rumpf`, `_trip_sms_werte`, `_trip_sms_fehlt`

> **Schicht-Hinweis:** Python-Core (`src/services/`, `src/app/`) plus eine kleine Frontend-Anzeigeänderung: die Einstell-Tabelle zeigt das Beispiel einer gesperrten SMS-Zelle (heute nur bei Zustand `on`), sonst stünde der Tagesbereich `D…` der Zeile „Temperatur“ nirgends sichtbar (Adversary-Befund F001). Kein Go-Umbau. Der Sperrgrund `kein_kuerzel` samt DE/EN-Text im Katalog `wetter.json` und die Anzeige gesperrter Haken existieren bereits (#3122), es entstehen keine neuen Nutzertexte.
>
> **Trip/Ortsvergleich:** Orte-Karte und Orte-Beispiel bleiben unverändert. Die Änderung betrifft nur den Trip-Zweig; der Orte-Zweig nutzt weder Etappenkopf noch Nacht.
>
> **Mandantentrennung:** Der Endpunkt `GET /api/briefings/{id}/placements` liefert Trip-Daten; getestet mit zwei verschiedenen Nutzern, `user_id` aus dem Auth-Kontext.
>
> **Kanäle:** SMS (und damit Premium-SMS, gleiche Formatfunktion) ändern nur das Beispiel, nicht den Versand. E-Mail- und Telegram-Beispiel zeigen bei eingeschaltetem Nachtblock künftig ebenfalls die Nacht, weil sie denselben Beispiel-Datensatz nutzen. Der Versand aller Kanäle bleibt byte-gleich.

## Estimated Scope

- **LoC:** +120/-40
- **Files:** 6
- **Effort:** medium (Risiko mittel: Versand-Code wird für die Gewitter-Ableitung umgebaut)

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `TripReportFormatter.format_email` / `format_sms` | module | Beispiel entsteht in denselben Renderer-Funktionen wie der Versand |
| `Trip.numbered_stage_label` (`src/app/trip.py`) | function | Etappenbezeichnung „Etappe N: Name“ → SMS-Kopf `E<N>` |
| `trip_anreicherung_bauen` (`src/services/trip_briefing_aufbau.py`) | function | Versandweg als Orakel (Nacht, Gewitter, Etappenlabel) |
| `TripReportScheduler._build_thunder_forecast_from_trend_or_fetch` | method | Gewitter-Ableitung, reiner Teil wird netzfrei herausgelöst |
| `placements_beispiel.py` | module | Fester versionierter Beispiel-Datensatz |
| `stellen_sperre` (`src/app/metric_catalog.py`) | function | Sperr-Mechanismus `locked` mit Grund |
| `feat_3122_was_steht_wo.md` | spec | AC-17, Teil A Nr. 2, 6, 8, 9 |
| `docs/reference/sms_format.md` | doc | `N` nur abends, Kopf `E<N>` |

## Scope

### Affected Files

| File | Change Type | Description |
|------|-------------|-------------|
| `src/services/placements_beispiel.py` | MODIFY | `nacht_zeitreihe()` (Ankunft 16 Uhr bis 06 Uhr Folgetag aus den Tagespunkten), `VERSION = 2` |
| `src/services/placements_view_service.py` | MODIFY | `_trip_muster`: erste Etappe nach Datum, Kopf über `numbered_stage_label` (Fallback Trip-Name), Nachtreihe und Folgetag-Gewitter aus dem Beispiel; `_trip_sms_werte`/`_trip_sms_fehlt`: Eltern ohne eigenes SMS-Kürzel zeigen nur die Token ihrer Kinder ohne eigenes Beispiel (Fenster-Kinder seit #3283 B2, z. B. `D14/18`), nie ein Token, das eine Kind-Zeile selbst zeigt |
| `src/services/trip_report_scheduler.py` | MODIFY | reinen Teil der Gewitter-Ableitung als netzfreie Funktion herauslösen; Scheduler ruft sie auf (Versand unverändert) |
| `src/app/metric_catalog.py` | MODIFY | `stellen_sperre`: SMS-Stelle einer Eltern-Metrik ohne eigenes SMS-Kürzel (`temperature`) gesperrt, Grund `kein_kuerzel`; `wind_chill` (Kürzel `TF`) bleibt schaltbar |
| `tests/tdd/test_placements_tabelle_endpoint.py` | MODIFY | Orakel `_trip_versand_sms` über den echten Versandaufbau; Kopf `E1` |
| `tests/tdd/test_3373_sms_beispiel_karte.py` | CREATE | RED-Nachweise E/F/G und Zwei-Nutzer-Test |

Nachzug bei Bedarf (feste Beispielwerte): Golden `tests/fixtures/ein_vokabular_3101/b2b_tabelle.golden.json`, E2E `kurzform-gefuehlte-temperatur-kind-mitnahme.spec.ts`, `kanal-grenzen-und-hinweise.staging.spec.ts`.

## Implementation Details

1. **Kopf:** Beispiel nimmt die Etappe mit dem frühesten Datum (nicht Listenposition). Name über `trip.numbered_stage_label(etappe)`, derselbe Aufruf wie im Versand; `_sms_stage_prefix` macht daraus `E1`. Trip ohne Etappen: Trip-Name wie bisher. `_trip_sms_rumpf` bekommt dasselbe Label, damit der Kopf korrekt abgeschnitten wird.
2. **Werte:** Der Datensatz bekommt eine Nacht (`VERSION` 2). `_trip_muster` übergibt sie als `night_weather` und baut `thunder_forecast` über die herausgelöste Ableitung aus dem Beispiel-Trend. Kein handgebautes Dict, kein zweiter Code-Weg, kein Wetterabruf. Ergebnis: `N` aus der Nacht (nur Abend-Fassung), Spitzen bis Fensterende nach Ankunft, `TH+` aus dem Folgetag-Gewitter.
3. **Eltern-Zeile:** Option „Haken sperren“ statt „auf Kinder durchreichen“. Begründung: Temperatur hat kein eigenes SMS-Kürzel, die Kinder haben eigene Zeilen und Haken; Durchreichen ergäbe zwei Stellen für dieselbe Wirkung und widerspricht „eine steuernde Stelle“ (Spec 3122 Teil A Nr. 6/8). Sichtbare Bedienänderung: der SMS-Haken der Zeile „Temperatur“ erscheint gesperrt mit dem vorhandenen Grundtext. Ein gespeicherter Haken bleibt erhalten, wirkt aber nicht (Spec 3122 Nr. 3.4).
4. **Invariante:** Versand von SMS, Mail und Telegram bestehender Trips bleibt byte-gleich; die Orte-Karte bleibt unverändert.

## Expected Behavior

- **Input:** `GET /api/briefings/{id}/placements` für einen Trip (Anlegen, Bearbeiten, Vorschau-Entwurf).
- **Output:** SMS-Beispiel, Token je Metrik und „passt nicht mehr“ entsprechen der Versand-SMS desselben Datensatzes; SMS-Zelle der Eltern-Zeile Temperatur ist `locked` mit Grund `kein_kuerzel`.
- **Side effects:** keine; Beispiel-Datensatz erhöht `VERSION`, E-Mail-/Telegram-Beispiel zeigen bei Nachtblock die Nacht.

## Acceptance Criteria

- **AC-1:** Given ein Trip mit Etappe „Tag 1“, ein Trip mit Etappe und freiem Namen, ein Trip ohne Etappen und ein Trip mit unsortiert gespeicherten Etappen / When die Karte „Was steht wo“ abgerufen wird / Then beginnt das SMS-Beispiel bei Etappen mit `E1` (bei unsortierten Etappen mit der Nummer der ersten Etappe nach Datum) und beim Trip ohne Etappen mit dem Trip-Namen, jeweils wie in der versandten SMS.
  - Test: Endpunkt-Antwort der Karte gegen den Kopf der SMS aus dem echten Versandaufbau, vier Trips.

- **AC-2:** Given ein Trip mit Nacht-Tiefstwert und Spitzenwerten (Wind, Böen) in der Beispielwetterlage / When die Abend-Fassung des Beispiels abgerufen wird / Then zeigt `N` den Tiefstwert der Nacht (nicht den Tageswert), die Spitzen gelten bis Fensterende nach Ankunft, und die Morgen-Fassung enthält kein `N`.
  - Test: Beispiel-SMS Abend gegen Versandaufbau mit Nachtreihe vergleichen; Morgen-SMS enthält kein `N` (sms_format.md).

- **AC-3:** Given ein Beispiel-Trend mit Gewitter am Folgetag / When das SMS-Beispiel gebaut wird / Then trägt es `TH+` mit der Stufe aus diesem Folgetag-Gewitter, abgeleitet über dieselbe Funktion wie im Versand, und ohne Folgetag-Gewitter erscheint kein `TH+`.
  - Test: Beispiel-SMS gegen Versand-SMS mit der Ableitung aus derselben Trend-Zeile; zusätzlich die herausgelöste Ableitung direkt gegen die Scheduler-Ableitung gleicher Eingabe.

- **AC-4:** Given ein Trip mit nummerierter Etappe, Nacht und Gewitter, dessen Metriken nicht alle in 160 Zeichen passen / When Karte abgerufen und über den echten Versandweg eine SMS aus demselben Datensatz erzeugt wird / Then ist das SMS-Beispiel zeichengleich mit der versandten SMS, die Zeichenzahl stimmt, und genau die Metriken, die in der SMS fehlen, tragen „passt nicht mehr“.
  - Test: Orakel `_trip_versand_sms` baut über `trip_anreicherung_bauen`-Logik (nummerierte Etappe, Nacht, Gewitter); Vergleich Zeichen für Zeichen, Länge und Menge der „passt nicht mehr“-Zeilen.

- **AC-5:** Given die Karte eines Trips mit Metrik „Temperatur“ und Kind-Zeilen (Nachttiefst, Tagestief, Tageshöchst) sowie „Gefühlte Temperatur“ / When die Tabelle abgerufen wird / Then ist die SMS-Zelle der Zeile „Temperatur“ gesperrt (`locked`, Grund `kein_kuerzel`), jedes Token der SMS steht in höchstens einer Zeile der Karte (die Zeile Nachttiefst zeigt `N`, die Zeile „Temperatur“ zeigt nur die Token der Kinder ohne eigenes Beispiel, also den Tagesbereich `D…`, und kein `N`), und die SMS-Zelle der Eltern-Zeile „Gefühlte Temperatur“ bleibt schaltbar.
  - Test: Endpunkt-Antwort prüfen: Zellzustand und Grund der Eltern-Zeile, Token-Anzahl je Zeile, `wind_chill`-Zelle nicht gesperrt. Zusätzlich Komponententest der Einstell-Tabelle: gesperrte SMS-Zelle mit Beispiel zeigt den Beispielwert.

- **AC-6:** Given bestehende Trips, auch mit gespeichertem `temperature.sms = on` / When SMS, E-Mail und Telegram über den Versandweg erzeugt werden und die Orte-Karte abgerufen wird / Then sind alle drei Versandtexte byte-gleich zu vor der Änderung, das gespeicherte `temperature.sms = on` ändert den Versand nicht, und die Orte-Karte ist unverändert.
  - Test: Versandtexte aus festem Datensatz gegen vorab festgehaltene Referenz; Gewitter-Ableitung des Schedulers liefert nach der Herauslösung gleiche Ergebnisse; Orte-Antwort gegen Golden.

- **AC-7:** Given ein Trip mit eingeschaltetem Nachtblock / When das E-Mail- und Telegram-Beispiel der Karte abgerufen werden / Then zeigen beide die Nacht wie der Versand mit demselben Datensatz.
  - Test: Beispiel E-Mail und Telegram gegen Versandaufbau mit Nachtreihe, Vergleich der Nacht-Teile.

- **AC-8:** Given zwei verschiedene Nutzer mit je einem eigenen Trip / When jeder die Karte seines Trips abruft und einer versucht, den Trip des anderen abzurufen / Then bekommt jeder nur seine eigene Karte mit Kopf und Werten seines Trips, und der fremde Abruf wird abgewiesen.
  - Test: Zwei Nutzer über den Endpunkt (Multi-User-Pflicht), Kopf `E1`/Trip-Name je Nutzer verschieden, Fremdzugriff 404/403.

## Test Plan

- **Kern-Schicht (ohne Netz):** neue Testdatei für #3373 mit AC-1 bis AC-8 über die Endpunkt-Antwort der Karte; Orakel der bestehenden AC-17-Tests (`tests/tdd/test_placements_tabelle_endpoint.py`) läuft über denselben Versandaufbau (nummerierte Etappe, Nachtwetter, Folgetag-Gewitter); Versand-Invariante (AC-6) als Vorher/Nachher-Vergleich von SMS, Mail und Telegram bestehender Trips; zwei Nutzer (AC-8).
- **Nachzug:** Golden `tests/fixtures/ein_vokabular_3101/b2b_tabelle.golden.json` und Frontend-/Browser-Prüfungen mit festen Beispielwerten, soweit sie sich durch Kopf, Nacht oder `TH+` ändern.
- **Mutations-Gegenprobe:** roher Etappenname statt Nummer; Nachtwetter weggelassen; Folgetag-Gewitter weggelassen; Sperre der Eltern-Zelle entfernt; Kind-Token wieder an die Eltern-Zeile gehängt; Gewitter-Ableitung im Versand verändert.
- **Staging:** Karte eines Prüf-Trips zeigt `E1`-Kopf und gesperrten SMS-Haken der Zeile Temperatur; Versand-SMS desselben Trips unverändert.

## Definition of Done

- AC-1 bis AC-8 durch benannte Tests grün, Adversary mit Mutations-Gegenprobe ohne offenen Befund, alle sechs CI-Checks grün.
- Staging-Verifikation der Karte, Prod-Deploy mit Selftest Exit 0.
- `sms_format.md` bleibt gültig; `api_contract.md` nennt den Sperrgrund der Eltern-Zelle, falls die Antwort der Karte sich ändert.

## Known Limitations

- Feste Beispielwerte in Golden- und E2E-Prüfungen verschieben sich durch Nacht und Gewitter im Datensatz und müssen nachgezogen werden; „passt nicht mehr“ kann für andere Metriken umschlagen, das ist gewollt (Beispiel = Versand).
- Das Beispiel nutzt weiterhin einen festen Datensatz ohne Wetterabruf; es bildet echte Wetterlagen nicht nach.

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** keine
- **Rationale:** Bugfix im Rahmen bestehender Entscheidungen (Spec 3122 Teil A Nr. 6, 8, 9 und AC-17; ADR-0095 Kanal-Parität). Keine neue Entscheidungsfläche.

## Changelog

- 2026-11-25: Initial spec created (Issue #3373, Epic #3122)
- 2026-11-25: AC-5 präzisiert (RED-Befund): Tagesbereich `D…` bleibt an der Zeile „Temperatur“, weil die Tages-Kinder seit #3283 B2 kein eigenes Beispiel zeigen; doppelt war nur `N`.
- 2026-11-25: Frontend-Anzeige ergänzt (Adversary F001): Beispielwert einer gesperrten SMS-Zelle wird angezeigt, Komponententest zu AC-5.
