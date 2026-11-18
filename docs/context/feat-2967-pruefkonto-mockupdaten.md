# Context: feat-2967-pruefkonto-mockupdaten

## Request Summary
Issue #2967 (Refs #2913): Der Staging-Elementlisten-Abgleich vergleicht das Mockup (`docs/context/einstellungen_neu/seiten/mockup-hub-fassung4.html`, fassung3 ist abgelöst) mit einem Prüfkonto, dessen Daten nicht zum Mockup-Beispiel passen. Ziel: idempotentes Seed-Skript legt im Staging-Prüfkonto Trip „GR221 Mallorca“ (Vorlage Alpen-Trekking) und Orts-Vergleich „Münsterland“ (Vorlage Allgemein) mit den Mockup-Daten an; der Abgleich nutzt sie; danach echte Restabweichungen der Metrik-Liste einer Scheibe zuordnen und die 247 Besitzer-Einträge von #2967 auflösen bzw. umhängen.

## Mockup-Beispieldaten (fassung4)
- Trip (Z.347-348, 667, 692): „GR221 Mallorca“, Region Mallorca, 23.–26.02.2026, 4 Etappen, 31,5 km, ↑1.737 m, Vorlage `alpen-trekking`, Tempo 4,0 km/h, 300 Hm/h, zu Fuß.
  - E1 Port d'Andratx → Estellencs 7,8 km ↑520 · E2 Estellencs → Esporles 8,4 km ↑610 (24.02.) · E3 Esporles → Valldemossa 6,9 km ↑380 · E4 Valldemossa → Deià 8,4 km ↑227
- `TRIP_METRICS` (Z.316-331), Reihenfolge: temperature, temperature_night, wind_chill, wind, gust, wind_direction(aus), precipitation, thunder, rain_probability, visibility, cloud_low, uv_index, freezing_level, snowfall_limit. `TRIP_OFF`: cloud_total, sunshine, fresh_snow, snow_depth, dewpoint, humidity, pressure.
- Eigene Vorlage „Mallorca Frühling – eigene · aus GR221 gespeichert“ (Z.357).
- Orts-Vergleich (Z.349, 703): „Münsterland“, 3 Orte Münster (60 m), Telgte (52 m), Tecklenburg (235 m), Morgen-Briefing 07:00, Vorlage Allgemein; `ORTE_METRICS` Z.333-343.

## Related Files
| File | Relevance |
|------|-----------|
| `frontend/e2e/elementliste-abgleich.staging.spec.ts` | Z.325 Trip/Orte über `ELEMENTLISTE_TRIP_ID`/`ELEMENTLISTE_ORTE_ID`, sonst kurzlebige E2E-GZ-Datensätze (Z.144-205); Wetter-Bedienabschnitte nutzen eigenen `wetterPruefDaten` (Z.213-276, Z.430) |
| `frontend/e2e/elementliste_abgleich_logik.ts` | browserfreie Logik, Unit-getestet |
| `scripts/elementliste_abgleich.ts` | Starter; liest nur GZ_AUTH_* aus Staging-`.env` |
| `scripts/staging_e2e_user_en.py` | Muster: HTTP gegen Staging-API, idempotent, injizierbarer Transport, Exit 0/1/2; Test `tests/tdd/test_staging_e2e_nutzer_en.py` |
| `scripts/setup_staging_validator_trip.py` | Muster: Dateien direkt (save_trip, Merge) |
| `src/app/metric_catalog.py:1441-1449` | `WEATHER_TEMPLATES["alpen-trekking"]` — Reihenfolge/Inhalt weicht vom Mockup ab (cloud_total drin, wind_direction fehlt) |
| `src/app/ampel_templates.py:25-46` | Ampel-Schwellen Alpen-Trekking (cloud_total aktiv 70/90, Mockup: aus) |
| `src/app/ampel.py:143-157` | Vorlage-Auflösung `display_config.ampel.template` / `preset_name` |
| `docs/context/einstellungen_neu/elementliste_besitzer.json` | 247 Einträge #2967 (142 zusaetzlich, 103 element, 2 abschnitt) |
| `tests/test_2913_c2_besitzerliste.py:115-125` | feste Zählung je Verweis, `#2967: 247` |

## Existing Patterns
- Staging-Seed per HTTP mit Login aus Staging-`.env`, feste IDs, idempotent, Exit-Codes (staging_e2e_user_en.py).
- Trip-Anlage `POST /api/trips` (409 bei vorhandener ID) bzw. `PUT`, Wetterkonfig `PUT /api/trips/{id}/weather-config` mit ETag; Compare `POST/PUT /api/compare/presets`, Orte `POST /api/locations`, `active_metrics` nur Objektform.
- Eigene Vorlagen `/api/metric-presets`.
- Zeilenfolge im Reiter Wetter kommt aus Katalograng `_REITER_WETTER` (metric_catalog.py:1302-1335), nicht aus gespeicherter Liste.

## Dependencies
- Upstream: Go-API Staging (Auth, Trips, Compare, Locations, metric-presets), Staging-`.env` (GZ_AUTH_USER/PASS).
- Downstream: Abgleich-Spec, Besitzerliste und deren Zählwächter, Folge-Scheiben von Epic #2913.

## Existing Specs
- `docs/specs/modules/einstellungen_neu_neustart_adr_waechter_elementliste.md` (Z.74: Abgleich nutzt nur Test-Konto, liest)
- `docs/specs/modules/feat_2966_abgleich_haken.md`, `docs/specs/modules/feat_2913_abgleich_ganzseite.md`

## Risks & Considerations
- Seed schreibt ins Staging-Prüfkonto: Regel „Abgleich liest nur“ bleibt für die Spec; Schreiben nur im separaten Seed-Skript. Prod-Schutz Pflicht (`assertNotProdBaseURL`-Pendant).
- Read-Modify-Write: vorhandene Daten des Kontos nicht ersetzen; nur eigene feste IDs anlegen/abgleichen.
- Trip-Datum Feb. 2026 liegt in der Vergangenheit → Status „fertig“ passt zum Mockup, aber Wetter-/Vorschau-Teile könnten sich anders verhalten; prüfen.
- Echte Unterschiede Katalog-Vorlage vs. Mockup (cloud_total, wind_direction) sind keine Kontodaten → Befund für eine Scheibe, nicht im Seed wegdrücken.
- „Nur E-Mail verbunden“ (64) und Adressen/Laufzeit (35): Kanäle/Empfänger des Kontos; ob der Seed das abdeckt, klärt die Analyse.
- Zählwächter `#2967: 247` muss beim Umhängen nachgezogen werden.

## Analysis

### Type
Feature (Prüfwerkzeug / Staging-Testdaten)

### Schnitt (Tech-Lead-Entscheidung)
- **In #2967:** Seed Trip „GR221 Mallorca“ (4 Etappen, 23.–26.02.2026, Vorlage `alpen-trekking`, Metrik-Flags wie Mockup) + eigene Vorlage „Mallorca Frühling“ (`/api/metric-presets`, deckt die 4 `vorlage-auswahl`-Einträge) + Orts-Vergleich „Münsterland“ (Münster/Telgte/Tecklenburg, Vorlage Allgemein, 07:00). Abgleich-Lauf mit `ELEMENTLISTE_TRIP_ID`/`ELEMENTLISTE_ORTE_ID`; Restabweichungen von Wetter/`metriken`/`laufzeit`/`vorlage-auswahl` auflösen oder einer Scheibe zuordnen (bei echten Code-Abweichungen neues Kind-Issue von #2913 anlegen).
- **Abgespalten #3145:** Kanäle/Empfänger (95 `kanaele`-Einträge + ~21 Zustellungstexte). Grund: Telegram/Premium-SMS-Verbinden nur per Loopback (`internal/handler/localhost_guard.go`), braucht Host-Lauf oder neuen Staging-Testweg. Diese Besitzer-Einträge werden in #2967 auf #3145 umgehängt.
- **Bekannte echte Code-Abweichungen (nicht seedbar), nach dem Abgleich-Lauf bestätigen und als Kind-Issue von #2913 anlegen (vorher gegen #3122/#3111 auf Dublette prüfen):**
  - Reihenfolge „Nicht im Briefing“: Trip Luftfeuchte vor Taupunkt, Luftdruck nach Sonnenstunden (Rang `_REITER_WETTER` metric_catalog.py:1302-1335, `ampelModell.ts:372-376`); Orte: Gefühlte Temperatur zuerst.
  - Widerspruch Vorlage „allgemein“: `temperature_night`/`thunder` in `metric_catalog.py:1486-1491` vs. `ampel_templates.py:159/168`.

### Affected Files (with changes)
| File | Change Type | Description |
|------|-------------|-------------|
| `scripts/staging_pruefkonto_mockupdaten.py` | CREATE | Idempotenter HTTP-Seed (Muster `staging_e2e_user_en.py`): Login aus Staging-`.env`, Prod-Schutz, feste IDs, GET→POST bzw. Read-Modify-Write-PUT nur auf eigenen IDs, Exit 0/1/2, gibt IDs für den Abgleich aus |
| `tests/tdd/test_staging_pruefkonto_mockupdaten.py` | CREATE | Kern-Test mit injizierbarem Transport (Fake-Server-Zustand, kein Mock-Theater): Idempotenz (2. Lauf ändert nichts), Prod-Schutz, fremde Datensätze unberührt, Payload = Mockup-Daten |
| `frontend/e2e/elementliste-abgleich.staging.spec.ts` | MODIFY (klein) | Kopfkommentar/Hinweis auf Seed; Abgleich bleibt lesend |
| `docs/context/einstellungen_neu/elementliste_besitzer.json` | MODIFY | #2967-Einträge auflösen bzw. auf #3145 / neue Kind-Issues umhängen |
| `tests/test_2913_c2_besitzerliste.py`, `tests/test_3007_besitzerliste.py` | MODIFY | Zählwächter `#2967: 247` nachziehen |
| `docs/runbooks/` (Seed-Aufruf) | CREATE | kurzes Runbook |

### Scope Assessment
- Files: ~6
- Estimated LoC: +~550 (Skript ~280, Test ~200, Rest Doku/JSON) / -~0
- Risk Level: LOW (nur Staging-Testkonto, Prod-Schutz, keine Produktlogik)

### Technical Approach
- Python statt TS: Seed ist separat vom lesenden Abgleich (Regel „Abgleich liest nur“).
- Trip: `POST /api/trips` (409 ⇒ GET + Merge-PUT) mit Etappen inkl. Wegpunkten (Koordinaten/Höhen der GR221-Orte), dann `PUT /api/trips/{id}/weather-config` mit If-Match: `ampel.template=alpen-trekking`, `metrics[].enabled` UND `ampel.metrics[].enabled` parallel (cloud_total aus, wind_direction aus/nur Anzeige; Rest laut `TRIP_METRICS`/`TRIP_OFF`).
- Orte: `POST /api/locations` mit festen IDs (Dubletten vermeiden), dann `POST/PUT /api/compare/presets` (Name „Münsterland“, profil allgemein, morning 07:00). Region darf im Seed „Münsterland“ heißen nur, wenn Textsuche nicht kollidiert — Kommentar spec.ts:181-182 prüfen; im Zweifel Region „Westfalen“.
- Datum Feb. 2026 liegt in der Vergangenheit ⇒ Trip-Status „fertig“ (wie Mockup). Beim ersten Abgleich-Lauf prüfen, ob Wetter/Zustellung für fertige Trips Zusatzhinweise zeigen; dann Abweichung zuordnen, Datum nicht verbiegen.
- Kein Cron ⇒ kein Heartbeat.

### Dependencies
Go-API Staging (Trips, weather-config mit ETag, Locations, Compare-Presets, Metric-Presets), Staging-`.env` (GZ_AUTH_USER/PASS). Downstream: Besitzerliste + Zählwächter, Kind-Issue #3145.

### Open Questions
- keine Produktfrage offen (Schnitt ist Tech-Lead-Entscheidung, Mockup ist die freigegebene Vorlage)
