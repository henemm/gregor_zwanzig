# Kontext — Bug #1135: „Hitze aber nicht heiß" (amtliche Risiken)

**Stand:** HEAD `5ccda0ab` (inkl. #1254 Point-in-Polygon-Zuordnung)
**Phase:** 10-context

## Zwei getrennte Symptome

### Symptom 1 — Hitze-Warnung trotz gefühlter Max-Temp < 20 °C
- Vigilance-Warnungen sind **Département-weit** (Météo-France gibt keine Höhen-/Punktauflösung).
- Zuordnung Warnung→Punkt: `department_mapper.py:196-214` (`lookup_department`) nutzt nach #1254 Point-in-Polygon — aber **nur `lat`/`lon`, keine Höhe**. Ein hochgelegener, kühler Trip-Punkt erbt die Tal-/Département-Hitzewarnung.
- Anzeige ab Level ≥ 2 (gelb): `vigilance.py:135`. Phänomen „6" → `extreme_heat`: `vigilance.py:49-53`.
- **Es gibt NIRGENDS einen Plausibilitäts-Check** amtliche Warnung ↔ tatsächliche/gefühlte Trip-Temperatur (bestätigt). Die einzigen „plausibility"-Checks (`weather_metrics.py`) sind reine Wertebereichs-Checks einzelner Metriken.
- Gefühlte Temperatur liegt vor als `wind_chill_c` (`app/models.py:121`, aus OpenMeteo `apparent_temperature`). Pro Segment aber **nur MIN** aggregiert (`wind_chill_min_c`, `weather_metrics.py:817-819`). Ein gefühltes **MAX pro Segment existiert im Trip-Pfad nicht** — nur im Compare-Pfad (`comparison_engine.py:432-433`).

### Symptom 2 — dieselbe Hitze-Warnung erscheint 3×
- **Korrektur der ursprünglichen Issue-Diagnose:** Nicht „3 Zeitperioden". Perioden werden pro Punkt bereits via `best_by_hazard` gefaltet (`base.py:79-88`) → pro Koordinate genau ein `extreme_heat`.
- **Echte Ursache:** Der Trip kreuzt **mehrere Départements** unter derselben nationalen Hitzewelle. Der Briefing-HTML-Pfad (`html.py:1428-1452`) rendert nur nach `dedupe_official_alerts` (Schlüssel enthält `region_label` = Département-Code, `vigilance.py:146`) — verschiedene Départements kollabieren also NICHT.
- Die zweite Verdichtungsstufe `_bundle_by_hazard_level` (`official_alerts.py:301-376`, bündelt gleiche `hazard`+`level` über Regionen) läuft im **Alarm-** und **Compare-Pfad** (`:1615`, `:1685`), aber **nicht** im Briefing-HTML-Pfad.
- **#1254 verschärft real:** Exakte Polygon-Zuordnung mappt eng benachbarte Trip-Punkte jetzt auf die tatsächlich verschiedenen Départements (früher fielen sie oft auf dieselbe nächste Präfektur → deduplizierte zu 1).

## Drei Render-/Sammel-Pfade (unterschiedliche Dedup-Tiefe)

| Pfad | Sammelstelle | Dedup |
|------|-------------|-------|
| Trip-**Briefing** (HTML) | `trip_report_scheduler.py:660-680` → `html.py:1428-1452` | nur `dedupe_official_alerts` — **KEIN** `_bundle_by_hazard_level` ← Symptom 2 |
| Trip-**Alarm** (Standalone) | `trip_alert.py:914-939` | `dedupe_official_alerts` + `_bundle_by_hazard_level` |
| **Compare**-Mail | `compare_html.py:262-320` | `_dedup_alerts` + Bündelung |

## Fix-Richtungen (Entscheidung in /20-analyse + /30-write-spec)

**Symptom 2 (klar, risikoarm):** Bündelungsstufe auch im Briefing-HTML-Pfad anwenden, bzw. `dedupe_official_alerts`-Schlüssel für Vigilance-Hitze département-unabhängig machen. Achtung: `_bundle_by_hazard_level`-Schlüssel enthält `valid_from`/`valid_to` (`:364`) — bündelt nur bei identischen Gültigkeitszeiträumen.

**Symptom 1 (Produkt-Entscheidung, PO nötig):** Eine amtliche Météo-France-Warnung zu unterdrücken ist sicherheitsrelevant. Optionen:
- (a) Plausibilitäts-Gate `extreme_heat` gegen gefühltes Segment-MAX (dieses MAX müsste im Trip-Pfad erst aggregiert werden).
- (b) Höhen-/Punkt-Kontext statt reiner Département-Zuordnung.
- (c) Hitze erst ab Level ≥ 3 (orange) zeigen.
- Zu klären: Warnung ganz unterdrücken vs. mit Hinweis relativieren („Département-Warnung, in dieser Höhenlage ggf. nicht zutreffend").

## Design-Entscheidungen (20-analyse, PO-bestätigt 2026-07-15)

**Symptom 2:** `_bundle_by_hazard_level` (Stufe 2) auch im Briefing-HTML-Pfad (`html.py:1428-1452`) anwenden — analog Alarm-/Compare-Pfad. Bündelt gleiche Gefahr+Stufe über Départements zu einer Karte, die alle betroffenen Regionen nennt. Vigilance `label` ist fix pro Gefahr (`vigilance.py:143`), also bündeln Hitzewarnungen verschiedener Départements bei gleicher Stufe + gleichem Gültigkeitsfenster korrekt zu einer.

**Symptom 1 — PO-Entscheidung: „Ausblenden bei klarem Widerspruch".**
- Plausibilitäts-Gate: `extreme_heat`-Warnung wird für eine Etappe unterdrückt, wenn die dort modellierte **gefühlte Höchsttemperatur** klar unter einer Hitzeschwelle liegt.
- **Empfohlene Schwelle: gefühlt-max < 25 °C** (konservativ — echte Canicule-Spitzen liegen bei ~33-36 °C; bei <25 °C besteht kein plausibles Hitzerisiko; Bereich 25-30 °C bleibt bewusst sichtbar, um Fehl-Unterdrückung zu vermeiden). Final in ACs zu bestätigen.
- **Gate greift NUR auf Hitze-Gefahren** (`extreme_heat`), nicht auf Wind/Sturm/etc.
- **Filter-Ort:** pro Etappe VOR Dedup/Bündelung (auf der Segment-Tagging-Ebene `_tagged` in `html.py:1428`). So bleibt die Warnung nur an Etappen sichtbar, wo Hitze plausibel ist; diese werden dann gebündelt.
- **Neues Datum nötig:** gefühltes **MAX pro Segment** existiert im Trip-Pfad nicht — muss aus `wind_chill_c` (`app/models.py:121`) je Segment-Zeitreihe aggregiert werden (analog vorhandenem `wind_chill_min_c`).

**Scope:** Beide Symptome in einem Workflow (gleicher Code-Bereich). LoC-Schätzung moderat; falls >250, Symptom 1 (neues Segment-Feld) und Symptom 2 (Render-Pfad) ggf. splitten.

## Tests (Bestand)
`test_issue_1035_vigilance_source.py`, `test_department_boundary_lookup.py`, `test_issue_1172_official_alert_dedup_info.py`, `test_issue_1087_trip_official_alerts.py`, `test_official_alert_warn_section.py`. **Lücke:** Kein Test deckt (a) Département-übergreifende Hitze-Bündelung im Briefing-HTML noch (b) einen Höhen-/Temperatur-Plausibilitätscheck ab.
