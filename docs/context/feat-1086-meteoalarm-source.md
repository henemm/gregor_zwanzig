# Analyse — Feature #1086: MeteoAlarm-Quelle (AT/IT Slice 2)

Workflow: `feat-1086-meteoalarm-source` · Phase 2 (Analyse) · 2026-07-15

## Type
Feature — neue amtliche Warnquelle `MeteoAlarmSource` im steckbaren `official_alerts`-System (Epic #1073, Slice 2). Bringt **Italien** in die amtlichen Warnungen (für IT praktisch die einzige freie amtliche Warnquelle).

## Ausgangslage
- Token da und live getestet: `GZ_METEOALARM_APIKEY` in Prod- + Staging-`.env`. Auth: `Authorization: Bearer <token>` (auch `?token=` möglich).
- Endpoint: OGC API EDR, `https://api.meteoalarm.org/edr/v1`. Collection `warnings`.
- Slice 1 (#1085, LIVE) deckt Österreich bereits gemeindegenau über GeoSphere/ZAMG ab.

## Grundwahrheit aus der echten API (Live-Proben 2026-07-15)
Die im Issue skizzierte „Punktabfrage, mappt Warn-Level" trifft **nicht** zu. Reales Verhalten:

1. **Nur `locations`-Query, keine Punktabfrage.** Die Collection meldet `data_queries: ['locations']`. Es gibt **kein** `/position?coords=POINT(...)`. Abgefragt wird pro **Land**: `/collections/warnings/locations/{COUNTRY}?datetime=<start>/<end>`. Ländercodes u.a. `AT`, `IT`.
2. **`datetime` ist Pflicht und muss ein Bereich < 24 h sein** (Fehler sonst: „daterange must be less than 24 hours"; „is required"). Der Bereich filtert auf die **Sende-/Publikationszeit** (`sent_range`), nicht auf die Gültigkeit.
3. **Hartes 100er-Limit pro Land, keine Pagination.** `limit=500` liefert weiter 100; keine `next`-Links, kein `numberMatched`. Für Italien im Sommer real überschreitbar → potenzielles stilles Verschlucken.
4. **EDR-Antwort ist nur ein Index, kein Inhalt.** Jedes Feature: `properties` = Metadaten (`alertId`, `countryCode`, `geometryType: "bbox"`, `hubTime`, `hubLink`), `geometry` = grobe **bbox-Polygon**, `links` = u.a. `canonical`/`xml` (CAP-XML), `geometry` (exakte Fläche als geo+json).
5. **Die Warnfelder stehen erst in der nachgeladenen CAP-XML** (`hubLink`, präsignierte URL, kein Auth). Bestätigt an echter AT-Warnung:
   - `event`/`headline` mehrsprachig, inkl. **deutsch** („Hitzewarnung"), `areaDesc` = Gemeinde/Region („Villach (Stadt)").
   - `onset`/`expires`/`effective` als ISO-8601.
   - CAP-`<parameter>`: `awareness_level = "2; yellow; Moderate"`, `awareness_type = "5; high-temperature"`.

**Konsequenz:** zwei-stufiger Abruf (Länder-Index → pro Treffer CAP-XML), client-seitige Punkt-in-Fläche-Prüfung, XML-Parsing. Schwerer als `geosphere_warn.py`.

## Kernentscheidung — AT-Doppelabdeckung (PO-Entscheid 2026-07-15)
**PO wählt: BEIDE Quellen für Österreich aktiv, mit Deduplizierung.** MeteoAlarm deckt AT **und** IT ab; für AT bleibt zusätzlich GeoSphere aktiv (Redundanz: fällt eine Quelle aus, trägt die andere). Duplikate werden zusammengefasst, sodass der Nutzer jede Warnung nur einmal sieht.

**Live-Gegenprobe (Villach 46.61/13.85), bestätigt echte Duplikate UND die Dedup-Herausforderung:**
- GeoSphere: warntyp 5 (Gewitter) Stufe→level 2 · warntyp 6 (Hitze) →level 2. region_label = „Villach".
- MeteoAlarm: „Gewitterwarnung" level 2 type 3 · „Hitzewarnung" level 2 type 5. areaDesc = „Villach (Stadt)" (und zusätzlich „Villach Land" für Gewitter).
- ⇒ Beide melden **dieselben Gefahren + Stufe** für den Ort = echte Duplikate. **Aber Ortsnamen unterscheiden sich** („Villach" ≠ „Villach (Stadt)"), und MeteoAlarm liefert per grober Bbox mehrere Regionen pro Gefahr.

**Dedup-Design (zentrale Spec-Frage):**
1. **`fetch()` fragt BEIDE Länder ab** (`/locations/AT` + `/locations/IT`), `covers()` = AT+IT-Box (`_INCA_*` ∪ `_DPC_*`).
2. **Präzise Punkt-in-Fläche über den `geometry`-Link (exakte geo+json-Fläche), nicht nur die Bbox** — reduziert MeteoAlarm-intern „Villach Stadt/Land" auf die real den Punkt enthaltende Region.
3. **Cross-Source-Dedup pro Ort über `(hazard)` statt `region_label`**, höchste `level` gewinnt, **Label/region_label der feineren Quelle (GeoSphere, gemeindegenau) bevorzugt.** Ortsname ist als Schlüssel untauglich (Namensdivergenz).
   - **Risiko/Vorsicht:** Dieser Dedup-Pfad (`dedupe_official_alerts` im Renderer) wird auch von den **Frankreich-Quellen** genutzt. Änderung muss (a) innerhalb eines Ortes/Punkts scopen (nicht global über Compare-Orte hinweg kollabieren) und (b) darf FR nicht regressiv zusammenwerfen. Adversary-Schwerpunkt. Minimal-invasive Variante prüfen: MeteoAlarm-AT-Alerts erhalten einen `dedup_id`, der bewusst mit dem GeoSphere-Schlüssel kollidiert (gleiche Gemeinde+hazard) — dann greift die bestehende Dedup ohne Renderer-Änderung. Setzt eine belastbare Gemeinde-Normalisierung voraus (》„Villach (Stadt)" → „Villach").
- **AC-2 des Issues** wird konkretisiert: AT über BEIDE Quellen, dedupliziert (statt „Doppelabdeckung zulässig").

## Technisches Mapping (Tech-Lead-Entscheidung, kein PO-Eingriff nötig)
- **Level:** MeteoAlarm `awareness_level` nutzt exakt die App-Skala (1 grün … 4 rot) → `level = awareness_level`, 1:1. `level < 2` (grün) wird gefiltert (wie Vigilance/GeoSphere).
- **Hazard → bestehendes Vokabular** (kein Renderer-Hazard-Change): 1 wind→`wind_gust`, 2 snow/ice→`snow`, 3 thunderstorm→`thunderstorm`, 5 high-temp→`extreme_heat`, 6 low-temp→`extreme_cold`, 8 forest-fire→`wildfire_risk`, 10 rain→`rain`, 12 rain-flood→`rain`. **Übersprungen** (keine App-Kategorie, `continue` wie unbekannte GeoSphere-Typen): 4 fog, 7 coastal, 9 avalanche, 11 flood.
- **region_label:** `areaDesc` aus CAP (stabil für Dedup/State-Key).
- **label:** deutsches `event`/`headline` aus CAP.
- **valid_from/to:** CAP `onset`/`expires` (ISO).

## Affected Files
| Datei | Typ | Beschreibung |
|------|------|--------------|
| `src/services/official_alerts/meteoalarm.py` | CREATE | `MeteoAlarmSource`: `covers()` (AT+IT-Bbox), `fetch()` (Länder-Index `/locations/AT`+`/locations/IT` → präziser Punktfilter via geometry-Link → CAP-XML-Nachladen → Mapping → `dedup_id` für AT-Cross-Source-Kollision), per-Land-Index-Cache, Bearer/ENV fail-soft |
| `tests/tdd/test_meteoalarm_source.py` | CREATE | Kern: Parse-/Mapping-Unit-Tests gegen aufgezeichnete EDR+CAP-Fixtures; präziser Punktfilter; **AT-Dedup gegen GeoSphere-Alert** (gleiche Gemeinde+hazard kollabiert, höchste level, GeoSphere-Label bevorzugt); fail-soft (fehlende ENV, Timeout, kaputtes XML/JSON). Live-Schicht (`live`-Marker): echter IT-Punkt (Südtirol) → nicht leer, echter AT-Punkt (Villach) → GeoSphere+MeteoAlarm dedupliziert |
| `src/services/official_alerts/__init__.py` | MODIFY | Import + `register_official_alert_source(MeteoAlarmSource())` + `__all__` |
| `src/output/renderers/alert/official_alerts.py` | MODIFY | `_SOURCE_LABELS["meteoalarm"] = "MeteoAlarm"`; ggf. Dedup-Anpassung (nur falls `dedup_id`-Kollisionsweg nicht ausreicht — Adversary-geprüft, FR-regressionssicher) |

## Wiederverwendung (Projektregel)
Struktur von `geosphere_warn.py` (Cache-Mechanik, `covers()`-Bbox, fail-soft try/except, `_extract_alerts`-Muster). ENV/Bearer + `_warn_once_missing_key` von `vigilance.py`/`meteo_forets.py`. Bbox-Konstanten `_DPC_*` (IT) aus `radar_service.py`. `httpx`, `TIMEOUT=8.0`, ISO-Zeit-Parser wie Vigilance. Keine Modell-/Registry-/Dedup-Änderung.

## Scope & Risiko
- **Geschätzte src-LoC: ~200–260** (deutlich mehr als `geosphere_warn.py`, weil zweistufiger Abruf + CAP-XML-Parsing + Punkt-in-Fläche-Filter + Index-Cache). **Kann das 250-LoC-Workflow-Limit streifen → LoC-Override auf 500 evtl. nötig (PO-Freigabe).**
- Risk Level: **MEDIUM**.
- **Bekannte Grenzen (offen, in Spec als Known Limitations):**
  1. **100er-Cap ohne Pagination:** bei >100 aktiven IT-Warnungen im Fenster können welche fehlen. Milderung: enges/rollierendes Zeitfenster; für Punktabfrage in der Praxis selten kritisch, aber dokumentieren.
  2. **`sent_range < 24 h`:** eine Warnung, die vor >24 h publiziert und noch gültig ist, wird verpasst. MeteoAlarm re-publiziert i.d.R. täglich → Risiko gering, aber real. In Spec benennen.
  3. **CAP-Nachladen pro Treffer:** N zusätzliche HTTP-Calls; Index- und ggf. CAP-Cache nötig, um Call-Sturm pro Ort zu vermeiden.

## Open Questions (PO)
- [ ] **AT/IT-Trennung:** Option (b) bestätigen (Österreich = GeoSphere, Italien = MeteoAlarm; keine Doppel-Badges)?
- [ ] **LoC-Override:** Freigabe, das 250-Limit für diesen Workflow auf 500 zu heben, falls die zweistufige Abruflogik es überschreitet?

## Reihenfolge
1. (erledigt) Live-Probe EDR + CAP-Schema.
2. Spec (`/30-write-spec`) mit AC-N, Known Limitations wörtlich.
3. TDD RED (aufgezeichnete EDR+CAP-Fixtures als Kern; Live-Marker für echten IT/AT-Punkt).
4. Implement nach `geosphere_warn.py`-Vorlage.
5. Register + `_SOURCE_LABELS`.
6. Validate (Staging-Live: IT-Punkt Südtirol zeigt Warnung, AT-Punkt nicht).
