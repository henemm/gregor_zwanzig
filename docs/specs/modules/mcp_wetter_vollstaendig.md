---
entity_id: mcp_wetter_vollstaendig
type: feature
created: 2026-11-26
updated: 2026-11-26
status: draft
version: "1.0"
tags: [mcp, wetter, nowcast, metriken, go-api, python-core, adr-0128]
workflow: feat-3398-mcp-vollstaendig
---

# MCP-Konnektor „Gregor Wetter“ vollständig (alle Katalog-Metriken + Regen-/Gewitter-Nowcast)

## Approval

- [ ] Approved

## Purpose

Erweitert den Konnektor aus `mcp_wetter_konnektor.md` (#3281, ADR-0128) so, dass Gregor über den MCP **vollständig** verfügbar ist (PO-Vorgabe 2026-11-26: „bitte kein Stückwerk. Gregor soll vollständig über den MCP verfügbar sein, mit allen Metriken.“, Issue #3398). Das Werkzeug `wetter` liefert künftig alle wählbaren Katalog-Metriken stündlich (inkl. gefühlter Temperatur und Schnee), und ein neues Werkzeug `regen_nowcast` liefert den Regen-/Gewitter-Nowcast (Radar) wie Briefings und Alarme.

## Source

- **File:** `api/routers/mcp_wetter.py` (MODIFY), `api/routers/mcp_nowcast.py` (CREATE), `internal/mcp/werkzeuge.go` (MODIFY), `internal/handler/mcp_nowcast.go` (CREATE, Abruf analog `MCPWetterAbrufen`)
- **Identifier:** `GET /api/_internal/mcp/wetter` (erweitert), `GET /api/_internal/mcp/nowcast?lat&lon` (neu), MCP-Werkzeug `regen_nowcast` (neu), Parameter `felder` am Werkzeug `wetter`

> **Schicht-Hinweis (geprüft):** Wetter-Domäne und Nowcast bleiben in Python (`api/`, `src/services/radar_service.py`, ADR-0127); Go (`internal/`) reicht durch und trägt Auth, Mengenbremse, Kontingent und i18n. Kein Frontend-Anteil.

> **Querschnitts-Prüfpunkte:**
> - **Trip/Ortsvergleich-Teilung:** kein Pendant, reine Abfrage-Schnittstelle ohne Editor.
> - **Mandantentrennung:** keine Nutzerdaten in Antworten; `regen_nowcast` ruft den Core ohne `user_id` (`user_id=None`), die Token-Bindung an die echte `user_id` bleibt in Go; Test mit zwei verschiedenen Konten (AC-11).
> - **Kanäle:** weiterhin Abfrage-Weg, kein Kanal im Sinn von ADR-0095; E-Mail, Telegram, SMS, Premium-SMS bleiben unberührt.

## Estimated Scope

- **LoC:** drei Lieferscheiben, je eigener PR, ein Workflow: S1 ca. 150, S2 ca. 250, S3 ca. 250 Produktivcode (Tests zusätzlich). Jede Scheibe bleibt unter dem Limit von 250 LoC bzw. 4 bis 5 Dateien.
- **Files:** S1 ca. 3 (`mcp_wetter.py`, Test, Spec #3281); S2 ca. 3 (`mcp_nowcast.py`, `api/main.py`, Test); S3 ca. 6 (`werkzeuge.go`, Handler, `mcp.json` de/en, Fixtures, Go-Tests).
- **Effort:** medium bis high

## Scope

**Im Scope**
- Werkzeug `wetter`: alle wählbaren Katalog-Metriken stündlich, inkl. gefühlter Temperatur, Schnee (SNOWGRID wie im Briefing), Parameter `felder`.
- Neues Werkzeug `regen_nowcast` mit Core-Endpunkt `GET /api/_internal/mcp/nowcast` (Zusammenfassung + Frame-Reihe bis 180 min).
- Mengenbremse/Kontingent auch für `regen_nowcast`; Texte de/en über `mcp.json`.
- Nachzug der Basis-Spec `mcp_wetter_konnektor.md` (Feldliste, Limitation „kein Nowcast“ aufgehoben, Changelog).

**Nicht im Scope**
- `confidence_pct` (#710), `cape_jkg` (#1585), Rohfelder ohne wählbare Katalog-Metrik.
- Trip-, Orts-, Vergleichs- oder Empfängerdaten (ADR-0128 Folgepflicht).
- Änderungen an Briefings, Alarmen, Kanälen, Frontend, Gate-Konfiguration.

## Definition of Done

- [ ] Spec freigegeben; Tests je Scheibe vor der Umsetzung rot, danach grün
- [ ] Adversary mit Mutations-Gegenprobe VERIFIED (u. a.: Feld aus Ausgabe entfernt, `confidence_pct` hinzugefügt, Nowcast-Flag verfälscht → je ein Test rot)
- [ ] S1, S2, S3 je als PR mit allen 6 CI-Checks grün gemergt, Deploy, Selftest Exit 0
- [ ] `/e2e-verify` auf Staging: AC-13 (Claude-App-Frage gefühlte Temperatur und „Regnet es in der nächsten Stunde?“) bestanden
- [ ] Basis-Spec `mcp_wetter_konnektor.md` mit Changelog nachgezogen

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `mcp_wetter_konnektor.md`, ADR-0128 | spec/adr | Basis: OAuth, Allowlist, Werkzeuge `ort_suchen`/`wetter`; wird erweitert |
| `src/app/metric_catalog.py` (`get_all_metrics()`, `dp_field`, `unit`) | module | einzige Quelle der Feldmenge und Einheiten (ADR-0127) |
| `src/services/weather_metrics.py` | module | Sonnenminuten aus `dni_wm2` (eine Umrechnung) |
| `src/providers/openmeteo.py` (`enrich_snow`, `_enrich_thunder`) | module | Stundenwerte inkl. SNOWGRID-Schnee wie im Briefing |
| `src/services/radar_service.py` (`RadarNowcastService.get_nowcast`, `NowcastResult`) | module | Nowcast-Quellkette RADOLAN, INCA, AROME-Korsika, ARPAE, AROME-HD, ICON-D2, Open-Meteo `minutely_15`; Cache 240 s, Budget-Gate |
| `internal/handler/forecast.go` (`reserviereForecastBudget`), Mengenbremse `vorhersage` | module | Kontingent und Bremse gelten auch für `regen_nowcast` |
| `internal/i18n/messages/{de,en}/mcp.json` (ADR-0104) | module | Beschreibungen und Hinweise de/en |
| Core-Auth `X-GZ-Core-Auth` (ADR-0062) | module | Go ruft den neuen Core-Endpunkt authentifiziert auf |
| `GZ_TEST_FIXTURE_DIR` Offline-Fixtures | testinfra | deterministische Tests ohne Netz |
| #710, #1585 | issues | `confidence_pct` und `cape_jkg` sind nicht wählbar und bleiben ausgeschlossen |

## Implementation Details

### S1: Felder, Schnee, `felder` (Python)

1. **Feldmenge aus dem Katalog:** Die ausgegebenen Stundenfelder werden aus `get_all_metrics()` (nur wählbare Metriken) über deren `dp_field` abgeleitet, dedupliziert (Fenstermetriken wie `*_night`, `*_day_low/high` teilen `dp_field`). Sonderfälle: `dni_wm2` erscheint nur als abgeleitetes `sonnenminuten` (ADR-0127), zusätzlich `wmo_code`. Einheit je Feld aus dem Katalog (`einheiten`), leere Katalogeinheit ergibt `""`, Enums als `.value`. Eine neu wählbare Katalogmetrik erscheint ohne Codeänderung. Nie ausgegeben: `confidence_pct` (#710) und `cape_jkg` (#1585, nicht wählbar). Das ersetzt die Handliste `_ROHFELDER`.
2. **Gefühlte Temperatur:** `wind_chill_c` (°C) ist ausdrücklich Teil der Ausgabe.
3. **Schnee:** Abruf mit `enrich_snow=True` wie im Briefing. Schneehöhe, Neuschnee und Schneefallgrenze werden im SNOWGRID-Gebiet (Alpenraum) gefüllt, außerhalb fehlen die Felder (Known Limitation, auch im Briefing). `precip_type` wird nur gefüllt, wenn die Quelle es liefert (GeoSphere), sonst leer, wie im Briefing. Ensemble bleibt aus (`enrich_ensemble=False`).
4. **`felder` (optional):** Standard = alle Felder. Mit `felder` (Liste von Feldnamen) wird die Stundenausgabe und `einheiten` auf die Auswahl reduziert (Zeit bleibt immer). Unbekannter Feldname ergibt einen Eingabefehler (`isError`) mit Katalogtext, der die gültigen Feldnamen nennt, de/en.

### S2: Nowcast-Endpunkt (Python)

`GET /api/_internal/mcp/nowcast?lat&lon` (mit `X-GZ-Core-Auth`) in `api/routers/mcp_nowcast.py`, in `api/main.py` registriert. Aufruf `RadarNowcastService().get_nowcast(lat, lon, elevation_m, priority="user_briefing", user_id=None, ...)`; kein zweiter Quellenabruf. Die Priorität bucht im Core nicht doppelt, weil Go das Kontingent bereits belegt.

**Festgelegte Antwortfelder (deutsche Protokoll-Token, nie übersetzt, ADR-0104):**

- `beginn_min` (Minuten bis zum Beginn, `null` wenn keiner), `ende_min` (Minuten bis zum Ende, `null` wenn unbekannt), `laeuft_bereits` (bool)
- `intensitaet` (stabiler Token: `trocken` | `leicht` | `maessig` | `stark` | `gewitter` | `hagel_gewitter`, gleiche Suffixe wie die Katalogschlüssel `alarm.radar.intensitaet.*` zu den `INTENSITY_*`-Konstanten, `radar_service.py:179-186`) und `intensitaet_text` (übersetzte Anzeige in der Sprache des Kontos)
- `konvektiv` (bool), `hagel` (bool, aus den Frames)
- `max_mm_h_erste_stunde`, `summe_erste_stunde_mm` (ausdrücklich als erste Stunde ab jetzt benannt, nicht als Gesamtfenster)
- `quelle` (z. B. `radar`, `INCA`, `AROME-FR`, `minutely_15`), `reichweite_min` (Quellreichweite, höchstens 180), `ueber_horizont_hinaus` (bool, Regen läuft über den Horizont hinaus, Ende ist dann eine Untergrenze)
- `gedrosselt` (bool), `nicht_verfuegbar` (bool)
- `frames`: Liste von `{zeit, mm_h, konvektiv, hagel}` mit `zeit` in Ortszeit (ISO mit Offset), höchstens 180 Minuten
- `trocken` (bool): ausdrückliche Aussage „kein Niederschlag im Fenster“, nie eine leere Antwort

Außerhalb der Radarabdeckung liefert der Dienst das modellbasierte `minutely_15` von Open-Meteo; `quelle` nennt das ehrlich. Bei `gedrosselt` oder `nicht_verfuegbar` trägt die Antwort die Flags und keine erfundenen Werte; Go ergänzt daraus einen Hinweistext.

### S3: Go-Werkzeug, `felder`, i18n, Fixtures

- Neues Werkzeug `regen_nowcast(ort | lat+lon)` in `internal/mcp/werkzeuge.go`: Ortsauflösung wie `wetter` (eindeutig = Abruf; mehrdeutig = Kandidatenliste; unbekannt = `isError`). Go bucht Kontingent `user_interactive` und prüft Mengenbremse `vorhersage` vor dem Core-Aufruf, dann Durchreichung des Core-JSON plus `intensitaet_text`, Ortsname, Zeitzone.
- Werkzeug `wetter` bekommt den Parameter `felder` (Schema, Durchreichung an den Core, Fehlertext bei unbekanntem Feld).
- `mcp.json` (de/en): Beschreibungen `wetter` (nachgezogene Feldliste), `regen_nowcast`, `mcp.feld.felder`, Intensitätstexte, Hinweise „gedrosselt/nicht verfügbar“, „trocken“, „über Horizont hinaus“, Fehlertext unbekanntes Feld; Katalogparität de/en.
- Go-Fixtures in `internal/mcp/testdata/` für das neue `wetter`-Antwortformat und die Nowcast-Antwort.
- Spec `mcp_wetter_konnektor.md` wird bei der Umsetzung aktualisiert: Feldliste, `felder`, Werkzeug `regen_nowcast`, Known Limitation „Kein Regenradar und kein Nowcast“ aufgehoben, Changelog.

## Expected Behavior

- **Input:** MCP-Aufrufe `wetter(ort | lat+lon, von, bis, felder?)` und `regen_nowcast(ort | lat+lon)` mit gültigem Bearer-Token.
- **Output:** `wetter`: alle wählbaren Katalogfelder je Stunde (bzw. die Auswahl) mit Einheiten. `regen_nowcast`: Zusammenfassung plus Frame-Reihe bis 180 Minuten, in Ortszeit, mit Quelle.
- **Side effects:** Kontingentbuchung je Aufruf beider Werkzeuge, Radar-Abrufe (Cache 240 s). Keine Nutzerdaten, keine Änderung an Trips, Orten, Vergleichen, Empfängern.

## Test Plan

### Automated Tests (TDD RED)

- [ ] Test 1 (Python, `tests/tdd/test_mcp_wetter_core_endpunkt.py`): GIVEN Offline-Fixture WHEN `GET /api/_internal/mcp/wetter` THEN Stundenfelder == abgeleitete Menge aus `get_all_metrics()` (dedupliziert, plus `sonnenminuten`, `wmo_code`), je Feld eine Einheit.
- [ ] Test 2: GIVEN Katalog mit zusätzlicher wählbarer Testmetrik WHEN Endpunkt THEN neues Feld erscheint ohne Codeänderung; `confidence_pct` und `cape_jkg` fehlen immer.
- [ ] Test 3: GIVEN Ort im SNOWGRID-Gebiet (Fixture) WHEN `wetter` THEN Schneehöhe und Neuschnee gefüllt; GIVEN Ort außerhalb THEN Felder fehlen.
- [ ] Test 4: GIVEN `felder=[...]` WHEN Endpunkt THEN nur Auswahl; unbekannter Name ergibt Eingabefehler mit Katalogtext.
- [ ] Test 5 (Python, `tests/tdd/test_mcp_nowcast_core_endpunkt.py`): GIVEN Radar-Fixture mit Regenbeginn WHEN `GET /api/_internal/mcp/nowcast` THEN Beginn, Ende, Intensitäts-Token, Summe erste Stunde, Quelle, Frame-Reihe in Ortszeit.
- [ ] Test 6: GIVEN trockene Fixture THEN `trocken` ausdrücklich; GIVEN Ort außerhalb Radar THEN `quelle` = `minutely_15`; GIVEN Drosselung/Ausfall THEN Flags statt leerer Antwort.
- [ ] Test 7 (Go, `internal/mcp/`): GIVEN Fixture-Core WHEN `tools/call regen_nowcast` und `wetter` mit `felder` THEN Format, Hinweistexte de/en, mehrdeutiger/unbekannter Ort wie bei `wetter`.
- [ ] Test 8 (Go): GIVEN erschöpftes Kontingent oder Bremse WHEN `regen_nowcast` THEN Werkzeugfehler, kein Core-Abruf; zwei Konten, keine Nutzerdaten in Antworten.
- [ ] Test 9 (Go): GIVEN je ein Konto mit `language` de und en WHEN `tools/list` und jeder neue Hinweis-/Fehlerfall aufgerufen wird THEN liefert jede Sprache einen nicht leeren, sprachrichtigen Text (kein Rückfall auf den Schlüssel).
- [ ] Test 10 (E2E Staging, `/e2e-verify`): Claude-App beantwortet Fragen nach gefühlter Temperatur und „regnet es in der nächsten Stunde“ über die Werkzeuge.

Tests laufen ohne `Mock()`-Theater: Python gegen den echten Endpunkt mit Offline-Fixtures (`GZ_TEST_FIXTURE_DIR`, aufgezeichnete Daten), Go gegen echte Handler mit Fixtures in `internal/mcp/testdata/`. Keine Dateiinhalt-Prüfungen.

## Acceptance Criteria

- **AC-1:** Given ein freigegebener Nutzer / When `wetter` für einen Ort aufgerufen wird / Then enthält jede Stunde genau die Felder aller wählbaren Katalog-Metriken (aus `get_all_metrics()` abgeleitet, dedupliziert, Sonnenstrahlung nur als `sonnenminuten`, plus `wmo_code`), und `einheiten` nennt zu jedem Feld die Katalogeinheit.
  - Test: Aufruf des Core-Endpunkts mit Offline-Fixture; Feldmenge wird gegen die aus dem Katalog berechnete Menge verglichen, jedes Feld hat eine Einheit.

- **AC-2:** Given eine neu wählbare Katalog-Metrik, sowie die nicht wählbaren `confidence_pct` (#710) und `cape_jkg` (#1585) / When `wetter` aufgerufen wird / Then erscheint die neue Metrik automatisch, `confidence_pct` und `cape_jkg` erscheinen nie.
  - Test: Test-Katalog mit zusätzlicher wählbarer Metrik, Antwort enthält das Feld; die beiden nicht wählbaren Felder fehlen in jeder Antwort (auch mit `felder`).

- **AC-3:** Given ein Nutzer fragt nach der gefühlten Temperatur / When `wetter` aufgerufen wird / Then liefert jede Stunde `wind_chill_c` mit Einheit °C.
  - Test: Aufruf mit Offline-Fixture; `wind_chill_c` in jeder Stunde vorhanden, Einheit „°C“ in `einheiten`.

- **AC-4:** Given ein Ort im SNOWGRID-Gebiet (Alpenraum) und ein Ort außerhalb / When `wetter` aufgerufen wird / Then sind Schneehöhe und Neuschnee im Alpenraum wie im Briefing gefüllt, außerhalb fehlen diese Felder ohne Fehler, und `precip_type` erscheint nur, wenn die Quelle es liefert.
  - Test: zwei Fixtures (Alpenort, Flachlandort); Alpenort mit Schneewerten, Flachlandort ohne Schneefelder und ohne Fehlerstatus.

- **AC-5:** Given der optionale Parameter `felder` / When `wetter` mit einer Auswahl, ohne `felder`, und mit einem unbekannten Feldnamen aufgerufen wird / Then liefert er mit Auswahl nur diese Felder samt Einheiten, ohne `felder` alle Felder, und bei unbekanntem Namen einen Werkzeugfehler (`isError`) mit Katalogtext (de/en), der die gültigen Namen nennt.
  - Test: drei Aufrufe über den MCP-Endpunkt mit Fixtures; Feldmengen und Fehlertext in beiden Sprachen werden geprüft.

- **AC-6:** Given ein Ort mit Regen in den nächsten 180 Minuten / When `regen_nowcast` aufgerufen wird / Then enthält die Antwort `beginn_min`, `ende_min`, `laeuft_bereits`, `intensitaet` (stabiler Token) samt übersetztem `intensitaet_text`, `konvektiv`, `hagel`, `max_mm_h_erste_stunde` und `summe_erste_stunde_mm` (als erste Stunde benannt), `quelle`, `reichweite_min`, `ueber_horizont_hinaus` und die Frame-Reihe `{zeit, mm_h, konvektiv, hagel}` in Ortszeit bis höchstens 180 Minuten.
  - Test: Core-Endpunkt mit Radar-Offline-Fixture (Regenbeginn in 30 Minuten); alle Felder, Ortszeit-Offset der Frames und höchstens 180 Minuten werden geprüft; Go-Werkzeugaufruf gegen Fixture liefert dasselbe Format.

- **AC-7:** Given ein Ort ohne Niederschlag im Nowcast-Fenster / When `regen_nowcast` aufgerufen wird / Then sagt die Antwort ausdrücklich, dass es trocken bleibt (`trocken`, `intensitaet` = `trocken`), statt leer zu sein.
  - Test: trockene Radar-Fixture; Antwort enthält `trocken: true` und Hinweistext in der Sprache des Kontos.

- **AC-8:** Given ein Ort außerhalb der Radarabdeckung / When `regen_nowcast` aufgerufen wird / Then wird das modellbasierte `minutely_15` von Open-Meteo genutzt und in `quelle` ehrlich benannt.
  - Test: Fixture mit Ort außerhalb aller Radar-Boxen; `quelle` = `minutely_15`, Frames vorhanden.

- **AC-9:** Given der Nowcast ist gedrosselt oder die Quelle nicht verfügbar / When `regen_nowcast` aufgerufen wird / Then trägt die Antwort `gedrosselt` bzw. `nicht_verfuegbar` und einen Hinweistext, und sie behauptet weder „trocken“ noch erfundene Werte.
  - Test: Fixtures für Drosselung und Upstream-Ausfall; Flags gesetzt, Hinweis vorhanden, `trocken` nicht wahr.

- **AC-10:** Given ein mehrdeutiger oder unbekannter Ortsname / When `regen_nowcast` aufgerufen wird / Then verhält es sich wie `wetter`: Kandidatenliste bei Mehrdeutigkeit, `isError` mit Hinweis bei unbekanntem Ort, kein Radarabruf.
  - Test: Aufrufe „Frankfurt“ und Unsinnsname über den MCP-Endpunkt mit Fake-Nominatim; Core-Zähler steigt nicht.

- **AC-11:** Given ein erschöpftes Kontingent oder die Mengenbremse und zwei Konten / When `regen_nowcast` aufgerufen wird / Then kommt ein Werkzeugfehler mit Wartehinweis ohne Radarabruf, die Buchung erfolgt je Aufruf auf das eigene Konto, und keine Antwort von `wetter` oder `regen_nowcast` enthält Daten des anderen Nutzers.
  - Test: zwei Nutzer mit Testdaten; Kontingent von A erschöpft, B ruft weiterhin erfolgreich ab; Antworten werden nach Nutzerdaten durchsucht (kein Treffer).

- **AC-12:** Given Konten mit `language` Deutsch bzw. Englisch / When sie `tools/list` abrufen oder Hinweise und Fehler auslösen / Then sind Werkzeugbeschreibungen (`wetter`, `regen_nowcast`) und alle neuen Texte in der Sprache des Kontos, kein Text fällt auf den Schlüssel oder die andere Sprache zurück, Feldnamen und Protokoll-Token bleiben unübersetzt.
  - Test: beide Konten rufen `tools/list` und Fehlerfälle auf; Texte differieren sprachrichtig, Namen identisch; jeder neue Hinweis- und Fehlerfall wird in beiden Sprachen ausgelöst.

- **AC-13:** Given Staging mit dem Konnektor in der Claude-App / When ein freigegebener Nutzer nach der gefühlten Temperatur an einem Ort fragt und „Regnet es in der nächsten Stunde?“ / Then beantwortet die App beide Fragen über die Werkzeuge `wetter` und `regen_nowcast` mit Werten aus Gregor.
  - Test: Ende-zu-Ende auf Staging in `/e2e-verify` (Werkzeugaufrufe `wetter` mit `wind_chill_c` und `regen_nowcast`, Antwort mit Quelle und Ortszeit).

## Known Limitations

- Schneefelder (Schneehöhe, Neuschnee, Schneefallgrenze aus SNOWGRID) nur im SNOWGRID-Gebiet; außerhalb fehlen sie, auch im Briefing.
- `precip_type` nur dort, wo die Quelle es liefert (GeoSphere); im Open-Meteo-Pfad leer, wie im Briefing.
- Nowcast-Horizont höchstens 180 Minuten; darüber hinaus nur die Untergrenze `ueber_horizont_hinaus`.
- Außerhalb der Radar-Boxen ist der Nowcast modellbasiert (`minutely_15`), gröber (15-Minuten-Raster).
- `max_mm_h_erste_stunde` und `summe_erste_stunde_mm` beziehen sich auf die erste Stunde ab jetzt, nicht auf das ganze 180-Minuten-Fenster.
- Volle 7 Tage mit allen Feldern ergeben eine große Antwort (ca. 50 KB); dafür gibt es `felder`.
- Die Known Limitation „Kein Regenradar und kein Nowcast“ aus `mcp_wetter_konnektor.md` wird durch diese Spec aufgehoben (Aktualisierung samt Changelog bei der Umsetzung).

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** keine (ADR-0128 gilt weiter)
- **Rationale:** Der Nowcast ist ein Wetterdatum und fällt unter ADR-0128 („Abfrage-Schnittstelle, kein Kanal“, nur Orts- und Wetterdaten); weder Auth, Kanäle, Provider-Wahl noch Datenmodell ändern sich. Die Feldmenge folgt dem Katalog (ADR-0127), die Texte folgen ADR-0104. Eine Erweiterung der Werkzeugmenge innerhalb derselben Schnittstelle ist keine neue Entscheidungsfläche.

## Changelog

- 2026-11-26: Initial spec created (Issue #3398, Workflow feat-3398-mcp-vollstaendig)
