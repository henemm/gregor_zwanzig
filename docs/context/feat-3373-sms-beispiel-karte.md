# Context: feat-3373-sms-beispiel-karte

## Request Summary
Issue #3373 (aus #3164 E/F/G, Epic #3122): Das SMS-Beispiel der Trip-Karte „Was steht wo“ muss zeichengleich mit der echten Versand-SMS sein (AC-17 der Spec `feat_3122_was_steht_wo.md`). Heute weichen Kopf (`Tag 1` statt `E1`), Nachtwerte (`N` fällt auf Tageswert zurück), Spitzen (nur bis Ankunft) und `TH+` (immer `-`) ab. Zusätzlich zeigt die Eltern-Zeile „Temperatur“ die Token ihrer Kinder doppelt und trägt einen SMS-Haken ohne Wirkung.

## Related Files
| File | Relevance |
|------|-----------|
| `src/services/placements_view_service.py` (`_trip_muster`, ~Z. 434–470) | Baut das Beispiel: `stage_name = trip.stages[0].name` (roh), ruft `TripReportFormatter().format_email(...)` OHNE `night_weather` und `thunder_forecast` |
| `src/services/placements_view_service.py` (`_trip_sms_rumpf`, `_trip_sms_werte`, `_trip_sms_fehlt`) | Zerlegt die SMS in Token je Metrik; `_trip_sms_werte` hängt Kind-Token zusätzlich an die Eltern-Metrik (`eltern.get(mid)`) → Ursache der Doppelung in der Eltern-Zeile |
| `src/services/trip_briefing_aufbau.py` (`trip_anreicherung_bauen`, Z. 79–158) | Versandweg: `stage_name = trip.numbered_stage_label(stage)`, holt `night_weather` (`scheduler._fetch_night_weather`) und baut `thunder_forecast` (`scheduler._build_thunder_forecast_from_trend_or_fetch`) |
| `src/app/trip.py:303` `numbered_stage_label` | „Etappe N: Name“ → SMS-Kopf `E<N>` über `_sms_stage_prefix` (`src/output/renderers/sms_trip.py:50`) |
| `src/output/renderers/sms_trip.py` `format_sms` (Z. 579ff.) | `N` aus `night_weather` (Fallback Tageswert), `TH+` aus `thunder_forecast["+1"]` |
| `src/services/placements_beispiel.py` | Fester Beispiel-Datensatz (VERSION 1): Tagespunkte, zwei Segmente, Ausblick-Tage; **keine Nachtpunkte, kein Folgetag-Gewitter** |
| `src/app/loader.py:988` `_DERIVED_METRIC_RULES` | Eltern/Kind: temperature → temperature_night/_day_low/_day_high; wind_chill → …_night/_day_low/_day_high |
| `tests/tdd/test_placements_tabelle_endpoint.py:148–166` (`_trip_versand_sms`) | Orakel für AC-17 bildet dieselbe falsche Annahme nach (roher Name, ohne Nacht/Gewitter) |
| `frontend/src/lib/components/organisms/wetter-tab/WasStehtWoKarte.svelte`, `MetrikZeile.svelte`, `shared/wetter-tab/wasStehtWoStand.ts` | Karte; Zeilen tragen `parent` (Server liefert ihn, `placements_view_service.py:260`), Frontend behandelt Eltern-Zeilen beim SMS-Haken nicht besonders |
| `docs/reference/sms_format.md` §3.1 | Kennt `Etappe N` → `EN` bereits (Doku-Lücke aus #3164 ist erledigt) |

## Existing Patterns
- Spec Teil A Nr. 9: Beispielwerte entstehen in denselben Renderer-Funktionen wie der Versand, aus festem versioniertem Datensatz ohne Wetterabruf → Nachtwetter und Folgetag-Gewitter müssen ebenfalls aus dem Datensatz kommen (Datensatz erweitern, `VERSION` erhöhen), nicht aus einem Abruf.
- Orte-Pendant: `orte_kennung(1)` (#3172) nummeriert Orte wie Etappen.
- `_sms_fenster_kinder()` (Z. 479) blendet abgeleitete Fenster-Kinder im Beispiel aus (#3283 B2) — das Beispiel kennt schon Eltern/Kind-Sonderfälle.

## Dependencies
- Upstream: `TripReportFormatter.format_email`, `format_sms`, `numbered_stage_label`, Beispiel-Datensatz.
- Downstream: GET `/api/briefings/{id}/placements` (Karte Trip, Anlegen und Bearbeiten), Vorschau-Entwurf (#3304), „passt nicht mehr“-Markierung (`_trip_sms_fehlt`), Elementlisten/Staging-Prüfungen der Karte.

## Existing Specs
- `docs/specs/modules/feat_3122_was_steht_wo.md` (AC-17, Teil A Nr. 9)
- `docs/specs/modules/feat_3174_trip_sms_ohne_doppelpunkt.md` (Kopf ohne Doppelpunkt)
- `docs/specs/modules/issue_760_stage_number.md` (Etappennummer)

## Risks & Considerations
- Nachtwetter im Beispiel verändert die angezeigten Werte (`N`, Spitzen bis 19 Uhr) und kann die Länge verschieben → „passt nicht mehr“ kann für andere Metriken umschlagen; Frontend-/Staging-Prüfungen mit festen Beispielwerten müssen nachgezogen werden.
- Morgen- vs. Abend-Fassung: `N` nur abends (sms_format.md, Hinweis zu `N`).
- Eltern-Zeile: Entscheidung zwischen „Haken an Eltern-Zeile sperren“ und „auf Kinder durchreichen“ — ist eine sichtbare Bedienänderung (Analyse/Spec).
- Trip ohne Etappen: Fallback `trip.name` beibehalten.
- Orte-Karte darf sich nicht ändern.

## Analysis

### Type
Bug (Beispiel der Karte verletzt AC-17 von `feat_3122_was_steht_wo.md`); Versand selbst ist richtig.

### Affected Files (with changes)
| File | Change Type | Description |
|------|-------------|-------------|
| `src/services/placements_beispiel.py` | MODIFY | `nacht_zeitreihe()` (Ankunft 16 Uhr bis 06 Uhr Folgetag aus `tagespunkte(TAG)` + `tagespunkte(TAG+1)` h<=6, `_meta()`), `VERSION = 2` |
| `src/services/placements_view_service.py` | MODIFY | `_trip_muster`: Etappe = erste nach Datum, Kopf über `trip.numbered_stage_label(etappe)` (Fallback `trip.name`), `night_weather=pb.nacht_zeitreihe()`, `thunder_forecast` aus dem Beispiel-Trend; `_trip_sms_werte`: Eltern ohne eigenes SMS-Symbol bekommen keine Kind-Token mehr; `_trip_sms_fehlt` entsprechend |
| `src/services/trip_report_scheduler.py` | MODIFY | reinen Teil von `_build_thunder_forecast_from_trend_or_fetch` (Zeilen-Abgleich je Offset, `_thunder_entry_from_trend_row`) als netzfreie Funktion herauslösen; Scheduler ruft sie weiter auf (Versand unverändert) |
| `src/services/placements.py` (`stellen_sperre`) | MODIFY | SMS-Stelle einer Eltern-Metrik ohne eigenes SMS-Kürzel (heute: `temperature`) gesperrt, Grund `kein_kuerzel` (bestehender Mechanismus `locked`, Frontend zeigt gesperrten Haken bereits) |
| `tests/tdd/test_placements_tabelle_endpoint.py` | MODIFY | Orakel `_trip_versand_sms` über den echten Versandaufbau (nummerierte Etappe, Nacht, Gewitter); `test_f001` Kopf `E1` |
| neue Testdatei `tests/tdd/test_3373_sms_beispiel_karte.py` | CREATE | RED-Nachweise E/F/G |

### Scope Assessment
- Files: 5–6 (+ ggf. Nachzug von Golden/Frontend-Prüfungen mit festen Beispielwerten)
- Estimated LoC: +120/−40
- Risk Level: MEDIUM (Versand-Code wird für Gewitter-Ableitung umgebaut; Sperre wirkt auf gespeicherte Tabellen)

### Technical Approach
1. **Kopf (E):** gleiche Funktion wie der Versand: `numbered_stage_label` der ersten Etappe nach Datum → `_sms_stage_prefix` → `E1`. `_trip_sms_rumpf` bekommt dasselbe Label (schneidet `E1 ` korrekt).
2. **Werte (F):** Datensatz um eine Nacht erweitern, Folgetag-Gewitter aus dem bereits gebauten Beispiel-Trend über dieselbe Ableitung wie der Versand (herausgelöste reine Funktion, kein zweiter Code-Weg, kein handgebautes Dict). Folge: E-Mail-/Telegram-Beispiel zeigen bei eingeschaltetem Nachtblock ebenfalls die Nacht — das ist gewollt (Beispiel = Versand).
3. **Eltern-Zeile (G):** Option „Haken sperren“ statt „auf Kinder durchreichen“: Temperatur hat kein eigenes SMS-Kürzel, die Kinder haben eigene Zeilen und Haken; ein Durchreichen gäbe zwei Stellen für dieselbe Wirkung (widerspricht „eine steuernde Stelle“, Spec Teil A Nr. 6/8). `wind_chill` hat eigenes Kürzel `TF` → bleibt schaltbar. Eltern-Zeile zeigt im SMS-Beispiel kein Token.
4. **Invariante:** Versand-SMS, -Mail, -Telegram bestehender Trips byte-gleich (Gewitter-Herauslösung und Sperre ändern den Versand nicht); Orte-Karte unverändert.

### Dependencies
Downstream: Karten-Endpunkt (Trip, Anlegen/Bearbeiten/Vorschau-Entwurf #3304), „passt nicht mehr“, Golden `tests/fixtures/ein_vokabular_3101/b2b_tabelle.golden.json`, e2e `kurzform-gefuehlte-temperatur-kind-mitnahme.spec.ts`, `kanal-grenzen-und-hinweise.staging.spec.ts`.

### Open Questions
- keine Produktfrage: G folgt der Spec-Regel „eine steuernde Stelle“; sichtbare Änderung (gesperrter Haken) wird in der Spec beschrieben und mit der Freigabe bestätigt.
