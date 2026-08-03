# Context: #1474 — Gewitter-Befund, durchgängig vier Stufen

**Workflow:** `feat-1474-gewitter-befund-stufen` · Full Process · Issue #1474 (S3 zu #1419)

## Request Summary

Aus der heutigen Ja/Nein-Gewitteraussage soll ein abgestufter **Befund** werden
(keine · möglich · wahrscheinlich · akut). Die seit heute live anliegende Blitzdichte
(Météo-France) und später das DWD-Blitzpotenzial sollen darauf abgebildet werden —
**je Größe mit eigener Skala**. Schwellen kommen aus veröffentlichter Doku, keine
eigene Forschung (PO-Vorgabe 2026-08-03).

---

## 🔴 Der Befund, der den Zuschnitt bestimmt: stille Umdeutung bestehender Alarme

Eine vierte Stufe zwischen `NONE` und `MED` deutet **jede bestehende
Gewitter-Alarmeinstellung still um** — ohne dass an einer Tour etwas geändert wird.

Ursache: Die Nutzereinstellung ist nur ein **String** (`"standard"` in
`display_config.metric_alert_levels["thunder_level"]`, `models.py:624`,
`loader.py:877`). Ihre **Bedeutung** wird bei *jeder* Auswertung frisch aus zwei
hartkodierten Tabellen abgeleitet:

| Stelle | Inhalt | Problem |
|---|---|---|
| `output/metric_format.py:218` `_THUNDER_ORDER` | `{NONE:0, MED:1, HIGH:2}` | fest auf 3 Stufen |
| `services/alert_preset.py:82-86` `ORDINAL_LEVEL_BOUNDS` | `entspannt=(2,0)`, `standard=(2,2)`, `sensibel=(1,2)` | `reach_min`/`from_max` als 0/1/2 |

Verschiebt sich die Ordinal-Skala, bedeutet `"standard"` beim nächsten Lauf etwas
anderes. **Keine Datenmigration nötig — und genau das ist die Gefahr**, weil nichts
auffällt.

⚠️ Die in `trip.alert_rules[].threshold` gespeicherte Zahl (real: immer `1`) ist
**kosmetisch** — `deviation_alert_engine.py:150-158` liest sie bei der Auswertung
gar nicht, sie dient nur als Gate „gibt es überhaupt eine aktive Regel"
(`trip_alert.py:191-195`, `:1179`). Wer nur die Persistenz migriert, hat nichts
erreicht.

**⇒ Zentrale Designfrage für die Spec:** Wie wird die Skala erweitert, ohne dass eine
bestehende Einstellung ihre Bedeutung ändert? (Optionen z. B.: neue Stufe **unten**
einfügen und Ordinalwerte der Bestandsstufen beibehalten; oder Bounds versionieren;
oder Empfindlichkeit auf benannte Stufen statt Ordinalzahlen umstellen.)

---

## 🔴 Korrektur an bisherigem Projektwissen

**Die Annahme „die Empfindlichkeitsstufe ist bei Gewitter wirkungslos" ist VERALTET.**
Seit #1460 P1b wirkt sie — über ein Overlay, nicht über den Zahlenwert:
`alert_preset.py:88-90` `ORDINAL_LEVEL_METRICS = {THUNDER_LEVEL}` (Gewitter ist der
**einzige** Eintrag, bewusst keine generische Registry). Wirkung heute:

| Empfindlichkeit | löst aus bei |
|---|---|
| entspannt | nur voller Sprung NONE ↔ HIGH |
| standard | Erreichen/Verlassen von HIGH |
| sensibel | jedem Stufenwechsel, inkl. NONE ↔ MED |

Der Δ-Schwellwert ist bei allen drei identisch `1` — wer nur `_PRESET_TABLE` liest,
hält die Empfindlichkeit fälschlich für wirkungslos.

---

## Related Files

### Wo die Stufe entsteht (nur zwei Erzeuger)
| Datei | Relevanz |
|---|---|
| `providers/openmeteo.py:621-638`, `:821` | `_parse_thunder_level`: WMO 95/96/99 → `HIGH`, sonst `NONE`. **Der einzige produktive Erzeuger.** Wirft die Hagel-Unterscheidung (96/99) weg → #1475 |
| `providers/fixture.py:65-66`, `:124` | reicht Fixture-Werte durch (Testdaten) |

**`MED` wird von keiner Wetterquelle je gesetzt** — ~12 Stellen lesen sie, keine schreibt.
Der italienische Warnbericht (`official_alerts/dpc.py:195`) erzeugt **kein**
`ThunderLevel`, sondern eine separate 2/3/4-Ampel (`OfficialAlert.level`) auf einem
komplett getrennten Weg.

### Aggregation und die ZWEI Skalen (ADR-0025 — nie vermischen)
| Datei | Relevanz |
|---|---|
| `services/weather_metrics.py:586-603` | `_compute_thunder_level` → Tages-Peak in `SegmentWeatherSummary.thunder_level_max` |
| `output/metric_format.py:221-229` | `thunder_ordinal` = **Sortier**-Skala `{0,1,2}` — nur für `max()`/Vergleiche |
| `output/metric_format.py:236-263` | `thunder_label_value` = **Render**-Skala `{NONE:0, MED:2, HIGH:3}` — zielt auf `tokens/metrics.LEVELS` |
| `output/tokens/metrics.py:14` | `LEVELS = {0:'-', 1:'L', 2:'M', 3:'H'}` — **Platz 1 („leicht") ist heute unerreichbar**, weil `thunder_label_value` nie `1` erzeugt |

### Der Schwellen-Katalog (die vorgesehene Heimat der Grenzwerte)
| Datei | Relevanz |
|---|---|
| `app/metric_catalog.py:27-78` | `MetricDefinition`, u.a. `display_thresholds: dict[str,float]` |
| `app/metric_catalog.py:279-296` | Eintrag `thunder` — **hat KEINE `display_thresholds`** |
| `app/metric_catalog.py:297-321` | Eintrag `cape` — **hat** `{yellow:300, orange:800, red:1500}` |
| — | **`lightning_density_per_km2_3h` hat KEINEN Katalogeintrag.** Feld existiert (`models.py:146`), wird befüllt (`thunder_enrichment.py:136`), ist dem Katalog aber unbekannt |
| `output/metric_format.py:115-150` | **`severity_from_thresholds()` — das Vorbild für Zahl → Stufe.** SSoT seit #1377; Keys `yellow/orange/red` (+ `*_lt` abwärts); fehlen alle → `None` statt irreführendem „grün" |

### Alarm-Kette
| Datei | Relevanz |
|---|---|
| `app/models.py:841` | `AlertMetric.THUNDER_LEVEL` |
| `services/alert_preset.py:126`, `:207` | `expand_per_metric_levels()` baut Regeln aus der Empfindlichkeit |
| `services/deviation_alert_engine.py:136-161` | **ignoriert `trip.alert_rules`**, baut Detektor immer frisch aus `display_config` |
| `services/weather_change_detection.py:617-624`, `:664-684` | **die Vergleichsstelle** — Ordinal gegen `ORDINAL_LEVEL_BOUNDS` |
| `services/weather_change_detection.py:706-724` | zweiter, faktisch toter Absolut-Pfad (Go migriert alle Absolute-Regeln zu `delta`, `internal/model/trip.go:309-336`) |
| `services/trip_alert.py:251`, `:271` | Auswertung + Versand |

### Radar-Naht (für Stufe „akut")
| Datei | Relevanz |
|---|---|
| `services/radar_service.py:74`, `:142-144`, `:541-545` | `NowcastResult.is_convective` aus WMO 95/96/99 |
| `services/trip_alert.py:776` | konvektiv durchbricht die Briefing-Unterdrückung |
| — | ⚠️ **Kein Code übersetzt `is_convective` in ein `ThunderLevel`.** Reine Bool-Semantik, komplett getrennt vom Vorhersagepfad. „Beobachtung schlägt Vorhersage" muss neu verdrahtet werden |

### Ausgaben: 7 hartkodierte Label-/Farbtabellen in 6 Dateien
Alle müssten eine vierte Stufe kennen:
1. `email/outlook.py:165-166` — `_THUNDER_LEVEL_LABEL`, `_THUNDER_LEVEL_BG`
2. `email/compare_html.py:164-165` — `_THUNDER_LEVEL_LABEL`, `_THUNDER_SEV` (zentrale Quelle, von `outlook.py`/`comparison.py` re-importiert)
3. `email/helpers.py:736-758` — `_THUNDER_MAP` (5 Felder × 3 Stufen, die umfassendste)
4. `email/helpers.py:850` — `_TREND_THUNDER_LABELS`
5. `email/html.py:168-175` + `:785-788` — Risk-Wort-Mapping + Farb-Dict
6. `narrow.py:226-233` — Inline-Wortkette
7. `trip_report.py:735-736` — Risk-Label-Dict

Reine ID-Mappings ohne Label (unkritisch): `compare_metric_ids.py`,
`compare_metric_catalog.py:104`, `compare_hourly_metric_ids.py`, `trip_metric_ids.py`.

---

## Existing Patterns

- **Zahl → Stufe:** `severity_from_thresholds()` (`metric_format.py:115-150`) — genau
  das Muster, das die Gewitter-Einstufung braucht. Liefert bewusst `None` statt „grün",
  wenn keine Schwellen hinterlegt sind.
- **Zahl-Alarm ohne Ordinal-Sonderweg:** CAPE (`models.py:848`, Summary `cape_max_jkg`,
  Δ-Schwellen 1200/600/200) — Vorbild für eine Blitzdichte-Alarmgröße.
- **`selectable=false`** (`metric_catalog.py:67`, Beispiel `confidence`): Größe bleibt
  intern nutzbar, verschwindet aber aus `/api/metrics` und damit aus dem Editor.
  Offene Produktentscheidung, ob die Blitzdichte selbst wählbar sein soll.

## Dependencies

- **Upstream:** `lightning_density_per_km2_3h` (seit `c33e7b28` live, nur FR/Korsika),
  `cape_jkg`, `wmo_code`, `NowcastResult.is_convective`
- **Downstream:** 156 Fundstellen in 36 Dateien; nutzersichtbar in Mail, SMS, Telegram,
  Ortsvergleich **und** in den Alarmen

## Existing Specs

- `docs/specs/modules/feat_1457_s2a_blitzdichte_meteofrance.md` (S2a, mit Nachtrag)
- `docs/specs/fast/fix-1457-s2a-echte-abrufnamen.md`
- ADR-0025 (zwei Thunder-Skalen), ADR-0041 (Zuständigkeit nach Endpunkt-Art)
- `docs/reference/decision_matrix.md` — Abschnitt „Abrufnamen gegen GetCapabilities prüfen"

## Risks & Considerations

1. **🔴 Stille Umdeutung bestehender Alarme** (s.o.) — das Hauptrisiko. Muss in der
   Spec als eigenes AC mit Nachweis behandelt werden: *eine bestehende Einstellung
   „standard" muss nach der Änderung dieselben Fälle auslösen wie vorher.*
2. **Zwei Skalen, die nie vermischt werden dürfen** (ADR-0025). Eine vierte Stufe
   belegt erstmals `LEVELS[1]='L'` — beide Skalen müssen konsistent neu kalibriert
   werden, sonst erscheint „mittel" als „L".
3. **Nur Frankreich/Korsika hat heute Blitzdichte.** Überall sonst gibt es weiterhin
   nur den WMO-Code. Die Einstufung muss „keine Aussage" von „keine Gefahr"
   unterscheiden (#1419: leer heißt nie „sicher").
4. **7 Hartkode-Stellen** in den Ausgaben — hohe Wahrscheinlichkeit, eine zu übersehen.
   Kandidat für eine geteilte Quelle statt sieben Kopien.
5. **Hagel-Information wird beim Einlesen weggeworfen** (WMO 96/99 → `HIGH`). Gehört
   nach #1475, aber die Einstufung muss den Platz dafür offenlassen.
6. **Radar-Naht ist Bool, kein Level** — „akut" braucht eine neue Verdrahtung, kein
   vorhandener Code leistet das.
7. **Ortsvergleich** nutzt teils eigene Katalog-/Formatwege
   (`compare_metric_catalog.py`) — Trip/Compare-Teilung ist laut CLAUDE.md ein
   ausdrücklicher Review-Punkt.

---

# Analysis (Phase 2)

**Type:** Feature · **Scope:** ~16–18 Dateien, ~200–250 LoC Code + ~250–350 LoC Tests
· **Risk:** HIGH (nutzersichtbar in allen Ausgaben **und** in den Alarmen)

## 🔴 Drei Funde, die in der Kontext-Phase fehlten

1. **`output/renderers/email/helpers.py:1549`** — ein **drittes** hartkodiertes
   Ordinal-Literal: `thunder_ordinal(lvl) >= 1`. Es bestimmt den „Gewitter ab HH:00"-Text
   in der Mail. Verschiebt sich `MED` von 1 auf 2, löst dieser Text künftig **lautlos
   schon bei „möglich"** aus. Kein Test fängt das, weil „möglich" heute in keiner
   Erwartung vorkommt.
2. **`output/tokens/metrics.py:14`** — `LEVELS.get(int(round(value)), "-")` fällt bei
   unbekanntem Wert **stillschweigend auf „-"** zurück. Würde „akut" naiv als
   Render-Wert 4 eingeführt, zeigte die Kurznachricht ausgerechnet im **gefährlichsten**
   Fall „kein Gewitter". ⇒ härtester Grund, „akut" NICHT in diese Scheibe zu nehmen.
3. **`providers/openmeteo.py:621-638`** — `_parse_thunder_level(None)` liefert
   `ThunderLevel.NONE` statt `None`. Vorbestehende Verletzung von „leer heißt nie
   sicher" (#1419). Darf sich nicht in die Fusion vererben, sonst gewinnt ein
   voreiliges „keine Gefahr" gegen ein echtes „möglich" aus der Blitzdichte.

Gegenprobe der Analyse: **alle übrigen** Nutzer von `thunder_ordinal()`
(`day_comparison.py:352`, `weather_metrics.py:1135`, `corridor_threshold.py:98`,
`narrow.py:170`, `day_window.py:51`, `corridor_mark.py:56`) verwenden sie **relativ**
(`max()`, Differenz) — dort ist eine Neunummerierung ungefährlich. Gefährlich sind nur
absolute Zahl-Literale: die zwei bekannten plus dieses dritte.

## Empfehlung Frage 1 — Skala erweitern ohne stille Umdeutung

**Die Bedeutung darf nicht mehr an einer Zahl hängen, sondern am Namen der Stufe.**

Heute steht in der Empfindlichkeitstabelle wörtlich „Ordinalwert 2" — dass 2 gerade
`HIGH` ist, steht nirgends. Deshalb:

1. `ThunderLevel` um `POSSIBLE` ergänzen (`app/models.py:33-37`)
2. Sortier-Skala neu durchnummerieren: `NONE=0, POSSIBLE=1, MED=2, HIGH=3` — **sicher**,
   weil `thunder_ordinal()` laut eigenem Docstring nie persistiert und nie gerendert wird
3. `ORDINAL_LEVEL_BOUNDS` (`alert_preset.py:85-89`) von Zahlen auf **benannte Stufen**
   umstellen (`"standard": (ThunderLevel.HIGH, ThunderLevel.HIGH)`), Auflösung erst zur
   Auswertungszeit
4. `email/helpers.py:1549` — `>= 1` durch `>= thunder_ordinal(ThunderLevel.MED)` ersetzen
5. **Render-Skala bleibt unverändert:** `_THUNDER_LABEL_VALUE` wird nur **additiv**
   ergänzt (`POSSIBLE=1`) — der Platz 1 in `LEVELS` ist heute frei und wird endlich
   belegt. `NONE=0/MED=2/HIGH=3` bleiben, wo sie sind.

**Verworfen:** Bounds relativ zur höchsten Stufe — dann springt „standard" automatisch
auf „akut" mit, sobald diese Stufe existiert. „standard" bedeutete je nach Datenlage
etwas anderes; in einer Freigabe nicht erklärbar.

**Pflicht-Zusicherung (eigenes AC):** Eine Tour mit „standard" meldet nach der Änderung
**exakt dieselben** Fälle wie vorher, solange keine neue Datenquelle anliegt.

## Empfehlung Frage 2 — drei Größen, eine Stufe

**Gewitterstufe ≠ Ampelfarbe.** Beide sind zufällig vierstufig, aber die Ampel bewertet
**eine** Zahl lokal und folgenlos; die Gewitterstufe ist eine **fusionierte Aussage**
aus artverschiedenen Quellen, die selbst wieder Alarme auslöst.

**Belegtes Gegenargument zur Wiederverwendung:** Die CAPE-Schwellen (300/800/1500,
`metric_catalog.py:302-306`) wurden am 2026-07-22 ausdrücklich für die **Berg-Kalibrierung
der Anzeige** geändert. Läse die Gewitterstufe sie direkt, verschöbe eine künftige
Anzeige-Entscheidung ungewollt die Warnstufe — derselbe Fehlertyp wie in Frage 1.

⇒ `severity_from_thresholds()` bleibt der **Rechenkern** (SSoT seit #1377), aber jedes
Signal bekommt **eigene, entkoppelte** Schwellen. Neue reine Funktion
`thunder_level_from_signals(...)` in `output/metric_format.py` (dort wohnt die Skala,
ADR-0025; von Trip **und** Ortsvergleich gemeinsam nutzbar ⇒ erfüllt die
Teilungs-Vorgabe). Fusion über das bereits vorhandene `max_thunder()`.

**„Keine Aussage" ≠ „keine Gefahr":** Rückgabe `None`, wenn **kein** Signal vorliegt;
`NONE` nur, wenn mindestens ein Signal aktiv „geprüft, unauffällig" meldet. Muster
existiert bereits in `thunder_enrichment.py:78-79,131-132`.

**Anschluss:** in `providers/thunder_enrichment.py` — laut eigenem Docstring bereits
„DER gemeinsame Anschluss für Gewittersignale", an dem Trip und Ortsvergleich ohnehin
vorbeikommen.

## Scheiben

| # | Inhalt | Nutzerwirkung |
|---|---|---|
| **A** | Fundament: Stufe ergänzen, Bedeutung an Namen binden, drei Zahl-Literale entschärfen, Regressionsnachweis „standard" | **keine** — bewusst unsichtbar, risikoarm, blockiert nichts |
| **B** | Blitzdichte als Signal: Katalogeintrag, Fusion, Anschluss, 7 Ausgabestellen um „möglich" | **erste sichtbare Wirkung**, zunächst FR/Korsika |
| C | DWD-Blitzpotenzial als zweites Signal | mit #1457 S2b |
| D | „akut" (Radar-Beobachtung) | **bewusst separat** — s. Fund 2 oben |

## Open Questions (Product Owner)

- [ ] Ab welcher Blitzdichte gilt „wahrscheinlich" statt „möglich"?
- [ ] Speist die Gewitterenergie (CAPE) in die Stufe ein — und mit eigenen Grenzen?
- [ ] Reagiert „sensibel" künftig auch auf den Sprung von „keine" auf „möglich"?
- [ ] Scheiben A+B zusammen, oder A zuerst allein?
