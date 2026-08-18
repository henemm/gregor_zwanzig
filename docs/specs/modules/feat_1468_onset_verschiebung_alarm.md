---
entity_id: feat_1468_onset_verschiebung_alarm
type: feature
created: 2026-08-18
updated: 2026-08-18
status: approved
version: "1.0"
tags: [thunder, precipitation, alert, onset, issue-1468, issue-1493, issue-1954]
---

<!-- Issue #1468 ("Alarm, wenn sich der Beginn eines Ereignisses deutlich
     verschiebt"). Grundlage: PFLICHTLEKTUERE
     docs/context/feat-1468-onset-verschiebung.md — Abschnitt "PO-Entscheide
     (2026-08-18, Intake)" und die drei Entwurfs-Entscheidungen E1/E2/E3 sind
     BINDEND und werden hier nicht neu verhandelt. Abgrenzung zu #1493
     (Anzeige der Onset-Stunde im Briefing, bereits approved/geliefert) und
     #1954 (Alarm-Protokoll, auf main). -->

# Onset-Verschiebungs-Alarm: Gewitter- und Starkregen-Beginn als Alarmgröße (#1468)

## Approval

- [x] Approved — PO (Henning), 2026-08-18. Freigegeben inklusive der drei
  Entscheidungspunkte: Preset-Schwellen wie tabelliert · Beginn- und
  Stufenänderung beide melden, im Text zusammengefasst · Starkregen-Onset mit
  `precip_1h_mm`-Fallback gegen dieselbe 4,0-mm/h-Schwelle.

## Purpose

Der Änderungs-Wächter vergleicht heute ausschließlich **Aggregate je
Segment** (`thunder_level_max`, `precip_sum_mm`, …). Verschiebt sich ein
Gewitter von 17 auf 15 Uhr, bleibt jedes Aggregat unverändert ⇒ Delta 0 ⇒
**kein Alarm**, obwohl der Wanderer mit einer inzwischen falschen Uhrzeit
weiterplant. Diese Spec macht den **Beginn** von Gewitter und Starkregen zu
einer eigenen, vergleichbaren Alarmgröße: Verschiebt sich der Beginn deutlich
gegenüber dem letzten Stand, entsteht ein Alarm — asymmetrisch, weil ein
**vorgezogener** Beginn gefährlicher ist als ein hinausgezögerter (wer um 15
statt 17 Uhr ins Gewitter läuft, ist bereits im Gelände).

## Source

> **Schicht-Hinweis:** Kern liegt im **Python-Core**
> (`src/app/`, `src/services/`, `src/output/renderers/alert/`). Zusätzlich
> betroffen: **Go-Spiegel** (`internal/model/trip.go` — `AlertMetric`-
> Konstanten müssen mit dem Python-Katalog übereinstimmen, sonst schlägt
> `tests/test_alert_metric_mapping_parity.py`/das Go-Pendant fehl) und
> **Frontend** (`frontend/src/lib/generated/alertPresetThresholds.generated.json`
> — generiert, nicht von Hand pflegen — sowie `alertMetricTable.ts`/
> `alertMetricLabels.ts` im Alarme-Tab).

- **File:** `src/app/models.py`
  - **Identifier:** `SegmentWeatherSummary` (neue Felder `thunder_onset_utc`,
    `precip_heavy_onset_utc`), `AlertMetric`-Enum (zwei neue Werte)
- **File:** `src/services/weather_metrics.py`
  - **Identifier:** `WeatherMetricsService.compute_basis_metrics()` — zwei
    neue `_compute_*_onset()`-Methoden nach dem Muster der bestehenden
    `_compute_*`-Methoden
- **File:** `src/services/weather_change_detection.py`
  - **Identifier:** `detect_changes()` — dritte Weiche neben
    `_ordinal_change_triggers()`, `_ALERT_METRIC_TO_SUMMARY_FIELD`,
    `_ALERT_DELTA_METRIC_TO_FIELDS`
- **File:** `src/services/alert_preset.py`
  - **Identifier:** `_PRESET_TABLE`, `ORDINAL_LEVEL_METRICS`-Pendant für
    Onset (`ONSET_METRICS`), `expand_preset()`
- **File:** `src/app/metric_catalog.py`
  - **Identifier:** `MetricDefinition` für `thunder`/`precipitation` —
    `summary_fields["onset"]`, `alert_metrics["onset"]`, `alert_label`,
    `sms_code`
- **File:** `src/output/renderers/alert/project.py`
  - **Identifier:** `to_alert_message()`, `_fmt_occurred_at()` (Vorbild für
    den neuen Zeitpunkt-Formatierpfad der Onset-Werte selbst)
- **File:** `src/output/renderers/alert/render.py`
  - **Identifier:** `_val()`/`_num()` (dürfen Onset-Werte NICHT durchlaufen),
    `render_sms()` (Zeichenbudget)

## Estimated Scope

- **LoC:** ~+200 bis +250 produktiv (siehe Affected Files) — **voraussichtlich
  über dem Workflow-Limit von 250**, `loc_limit_override` ist einzuplanen.
- **Files:** ~12 Produktivdateien + 2 generierte Dateien + neue Testdateien
  (siehe Test Plan)
- **Effort:** high — Alarm-Pfad, Persistenz-Schema, Go/Python-Parität, vier
  Kanäle, zwei Flächen (Trip + Ortsvergleich), 18+ Registrierungsstellen.

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `radar_service.INTENSITY_HEAVY`/`radar_service.py:77` | Konstante (SSoT) | Definiert „Starker Regen" ≥ 4,0 mm/h — dieselbe Zahl, dieselbe Bedeutung wie im Nowcast, PO-Entscheid bewusst kein neues Vokabular |
| `_ordinal_change_triggers()` / `ORDINAL_LEVEL_BOUNDS` (`weather_change_detection.py:692-696`, `alert_preset.py:102-111`) | Funktion + Tabelle | Strukturelles Vorbild für die dritte Weiche (E3) — Niveau-Vergleich statt `abs(delta) > threshold` |
| `_fmt_occurred_at()` (`project.py:56-63`) | Funktion | Vorbild für den eigenen Onset-Formatierpfad — `local_fmt()`, UTC-naive-Guard, NICHT über `format_metric_value()` |
| `metric_and_aggregation_for_field()` (`metric_catalog.py:1166-1196`) | Funktion | Reverse-Lookup Summary-Feld → Register-Paar — Grundlage für die vom #1954-Protokoll geforderte Trennung `("thunder","onset")` vs. `("thunder","max")` |
| `_ist_extremer()`/`_norm_pairs()` (`src/services/alert_log.py`) | Funktion | Gruppiert Protokoll-Einträge nach `(metric_id, aggregation)` — der Grund, warum Onset ein **eigenes** `summary_fields`-Paar braucht, nicht ein geteiltes |
| `_deserialize_summary()` (`weather_snapshot.py:357-373`) | Funktion | Feld-generischer Anker-Loader über `dataclasses.fields()` — macht die neuen Felder automatisch bestandssicher (`None` bei alten Ankern) ohne Zusatzcode |
| `summarize_points()` (`weather_metrics.py:1108-1160`) | Funktion | Dünner Wrapper um `compute_basis_metrics()` — Ortsvergleich erbt die Onset-Berechnung ohne Zusatzarbeit (Teilungs-Invariante) |
| `day_window.py:20-21` / Tagesfenster-Filterung (`helpers.py:1005-1007`) | Modul | Muss die Onset-Berechnung erreichen (E2) — heute nur in der Render-Schicht angewendet, nicht in der Aggregation |

## Implementation Details

### E1 — Zwei eigene Summary-Felder (BINDEND)

`SegmentWeatherSummary` bekommt zwei neue Felder, Typ `Optional[datetime]`
(UTC, naiv — Hausnorm `src/utils/timezone.py:107-109`), **kein** Feld für
beide Größen gemeinsam:

| Feld | Bedeutung | Schwelle |
|---|---|---|
| `thunder_onset_utc` | erste Stunde im Tagesfenster mit `thunder_level >= LOW` | `ThunderLevel.LOW` |
| `precip_heavy_onset_utc` | erste Stunde im Tagesfenster mit Regenintensität ≥ 4,0 mm/h | identisch mit `INTENSITY_HEAVY` |

Grund für getrennte Felder: Das Alarm-Protokoll (#1954) bildet sein
Register-Paar über den Summary-Feldnamen
(`metric_and_aggregation_for_field()`). Ein eigenes Feld je Größe ergibt
automatisch das Paar `("thunder", "onset")` bzw.
`("precipitation", "onset")` — getrennt von `("thunder", "max")`. Ohne
eigenen Katalog-Eintrag (`summary_fields["onset"] = "..."`) fiele die
Beginn-Änderung **still** aus dem Protokoll.

Zwei neue `AlertMetric`-Werte (Namensvorschlag, kein PO-Bezug nötig — folgt
bestehender Konvention wie `FRESH_SNOW`/`WIND_CHANGE`):
`AlertMetric.THUNDER_ONSET = "thunder_onset"`,
`AlertMetric.PRECIPITATION_HEAVY_ONSET = "precipitation_heavy_onset"`.

### E2 — Lokale, tagesfenster-gefilterte Berechnung (BINDEND)

Die Onset-Berechnung muss **dieselbe Zahl** liefern, die im Briefing steht
(Tagesfenster Default 4–19 Uhr, `day_window.py:20-21`, Ortszeit). Eine im
gesamten Zeitraum inklusive Nachtstunden berechnete Onset-Zeit wäre eine
**andere** Zahl als die im Briefing gezeigte — der Alarm würde über eine
Verschiebung informieren, die im Briefing nie stand. Zeitzone und
Tagesfenster müssen deshalb bereits in `compute_basis_metrics()` ankommen,
nicht erst in der Render-Schicht. **Nicht nachrüstbar:** ein global
berechnetes Onset lässt sich nicht nachträglich auf ein fenstergefiltertes
umrechnen (die erste Überschreitung nachts und die erste im Tagesfenster
sind verschiedene Stunden) — muss von Anfang an korrekt sein.

### E3 — Asymmetrische dritte Weiche, kein neuer `AlertRuleKind` (BINDEND)

`detect_changes()` bekommt neben der bestehenden Niveau-Weiche
(`_ordinal_levels`) eine dritte, analoge Weiche (eigenes `_onset_levels`-
Dict, eigenes Prädikat), kein neuer `AlertRuleKind`. Die Richtungs-Asymmetrie
lebt in der Preset-Tabelle, die für Onset-Metriken **zwei** Schwellen je
Stufe führt (`früher`/`später` statt einer symmetrischen `abs(delta)`-
Schwelle):

| Stufe | früher (vorgezogen) | später (verschoben) |
|---|---|---|
| entspannt | ab 2 h | ab 4 h |
| standard | ab 1 h | ab 3 h |
| sensibel | ab 1 h | ab 2 h |

> ✅ **PO-freigegeben 2026-08-18.** Die Tabelle gilt wie oben. Ausgangspunkt
> war der Issue-Text („entspannt ab 3 h, standard ab 2 h, sensibel ab 1 h"),
> nach vorn verschärft und nach hinten gelockert, weil ein vorgezogener
> Beginn gefährlicher ist als ein verzögerter. Die ACs sind so geschrieben,
> dass sie mit dieser Tabelle stehen und fallen, nicht mit konkreten Zahlen
> im Fließtext.

**Vergleichsbasis muss echte Zeitpunkte nutzen, nicht nackte Stundenzahlen**
(Risiko 8): Die Verschiebung 23:00 → 01:00 ist eine Verschiebung um 2 Stunden
über die Kalendergrenze, nicht um 22 Stunden zurück. `WeatherChange.old_value`/
`new_value`/`delta` sind heute `float`-typisiert (`models.py:556ff`) — die
Onset-Weiche muss die Differenz **vor** der Umwandlung in dieses DTO als
echte Zeitspanne (z. B. Sekunden zwischen den beiden `datetime`-Werten)
berechnen, nicht als Differenz zweier Stundenzahlen. Dasselbe gilt für das
Melde-Gedächtnis (`deviation_alert_engine.py:242`, filtert über
`abs(new_value - last)`) — zweite Stelle mit demselben Fehlerrisiko.

**Nur wenn beide Seiten gesetzt sind** (Risiko 7, PO-Entscheid): Die
bestehende Schleife in `detect_changes()` überspringt Metriken bereits heute,
wenn altes oder neues Feld `None` ist („Skip if either value is None",
`weather_change_detection.py:606`) — dieses bestehende Verhalten deckt
`None → 15:00` automatisch ab, wenn die Onset-Felder über denselben
Mechanismus eingehängt werden. Kein Sonderfall-Code nötig, aber ein
Wächter-Test ist Pflicht (AC-6).

### Formatierung

Onset-Werte dürfen `_val()`/`_num()` (`render.py:40-74`) **nicht**
durchlaufen — `_HANDLED_UNITS` kennt weder `"h"` noch `"Uhr"`, das Ergebnis
wäre „15 h" statt „15:00" und ein negatives Delta erschiene als „−2 h" statt
„2 h früher". Ein eigener Formatierpfad nach Vorbild `_fmt_occurred_at()`
(`project.py:56-63`) liefert Uhrzeiten als `"HH:MM"` in Ortszeit und die
Verschiebung als Text „N h früher"/„N h später" (kein Vorzeichen im Text).

### Doppelmeldung bei gleichzeitiger Beginn- und Stufenänderung

Ändert sich Beginn **und** Stufe eines Ereignisses gleichzeitig (Gewitter
kommt früher **und** wird stärker), entstehen zwei `WeatherChange`-Objekte
für dieselbe Größe.

> ✅ **PO-freigegeben 2026-08-18.** **Beide melden**, aber im
> zusammengesetzten Alarmtext derselben Nachricht zusammenfassen (nicht zwei
> getrennte Nachrichten) — folgt der PO-Linie aus `feat_1493`, dass dieselbe
> Information nicht doppelt in zwei Textformen erscheinen darf. Im
> Alarm-Protokoll bleiben es dagegen zwei getrennte Einträge (AC-7), damit
> der größere nackte Betrag den kleineren nicht verdeckt.

### ⚠️ Ergänzender Befund (Spec-Phase, 2026-08-18): Starkregen-Onset ist beim Primärprovider nicht berechenbar

Die Analyse setzt `precip_heavy_onset_utc` auf die stündliche Intensität
`precip_rate_mmph` (≥ 4,0 mm/h). Verifiziert: **`precip_rate_mmph` wird
ausschließlich vom Geosphere-Provider befüllt**
(`src/providers/geosphere.py:571`). Der **Open-Meteo-Provider** — laut
CLAUDE.md der primäre Provider — setzt das Feld hart auf `None`
(`src/providers/openmeteo.py:885`, Kommentar: „Not available (Open-Meteo
provides hourly totals, not rates)"). Für alle Open-Meteo-basierten
Segmente (die Mehrheit) wäre `precip_heavy_onset_utc` damit strukturell
immer `None` — kein Fehlalarm, aber auch **nie ein Alarm**, obwohl die Daten
zur Beurteilung vorlägen: Open-Meteos stündlicher Niederschlagswert
(`precip_1h_mm`) ist bei 1-Stunden-Auflösung numerisch dieselbe Größe wie
eine mm/h-Rate.

> ✅ **PO-freigegeben 2026-08-18.** Die Schwelle **bleibt 4,0 mm/h**, nur die
> Datenquelle wird ergänzt: `_compute_*_onset()` nutzt `precip_rate_mmph`,
> wenn gesetzt (Geosphere), sonst `precip_1h_mm` als Fallback (Open-Meteo) —
> beide gegen dieselbe 4,0-mm/h-Schwelle. Rechnerisch identisch: Geosphere
> setzt `precip_rate_mmph` selbst auf den Stundenwert `precip_1h`
> (`src/providers/geosphere.py:571`), bei 1-Stunden-Auflösung ist mm/h
> dieselbe Zahl wie mm je Stunde. Ohne diese Ergänzung wäre die
> Starkregen-Hälfte des Tickets bei Open-Meteo-Segmenten strukturell
> wirkungslos.

## Expected Behavior

- **Input:** Zwei aufeinanderfolgende Wetter-Läufe (Anker vs. frischer Stand)
  für dieselbe Etappe/denselben Ort, mit unterschiedlicher Onset-Stunde für
  Gewitter und/oder Starkregen im Tagesfenster.
- **Output:** Verschiebt sich der Beginn um mindestens die für die
  Empfindlichkeitsstufe und Richtung geltende Schwelle, entsteht ein Alarm
  auf allen vier konfigurierten Kanälen (E-Mail, Telegram, SMS,
  Premium-SMS), sowohl im Trip- als auch im Ortsvergleichs-Pfad. Der
  Alarmtext nennt alte und neue Uhrzeit sowie „N h früher"/„N h später" in
  lesbarer Form.
- **Side effects:** Neues Katalog-/Register-Paar erscheint im Alarm-Protokoll
  (#1954), getrennt vom bestehenden Stufen-Alarm derselben Größe. Alte
  Wetter-Anker ohne die neuen Felder laden unverändert weiter (`None`, kein
  Fehlalarm beim ersten Vergleich nach dem Rollout).

## Test Plan

### Automated Tests (TDD RED)

- [ ] Test 1: GIVEN ein Anker mit Gewitterbeginn 17:00 und ein frischer Stand
      mit Beginn 15:00 (Empfindlichkeit „standard") WHEN `detect_changes()`
      läuft THEN entsteht genau eine `WeatherChange` mit Metrik
      Gewitter-Beginn.
- [ ] Test 2: GIVEN dieselbe Verschiebung in die Gegenrichtung (17:00 →
      19:00, „standard") WHEN `detect_changes()` läuft THEN entsteht **keine**
      `WeatherChange` (2 h < 3 h Schwelle für „später").
- [ ] Test 3: GIVEN Anker 23:00 und frischer Stand 01:00 (Kalendergrenze)
      WHEN der Alarm gerendert wird THEN nennt der Text „2 h später", nicht
      „22 h früher".
- [ ] Test 4: GIVEN eine Etappe mit Gewitterbeginn 14:00 im Tagesfenster
      WHEN dieselbe Fixture sowohl das Briefing als auch
      `compute_basis_metrics()` durchläuft THEN sind Briefing-Onset-Stunde
      und `thunder_onset_utc` gleich (Ortszeit, tagesfenstergefiltert).
- [ ] Test 5: GIVEN ein persistierter Anker aus der Zeit vor #1468 (ohne
      `thunder_onset_utc`/`precip_heavy_onset_utc`) WHEN er geladen und mit
      einem frischen Stand verglichen wird THEN entsteht kein Beginn-Alarm
      und keine Ausnahme.
- [ ] Test 6: GIVEN Anker-Onset `None`, frischer Stand 15:00 WHEN
      `detect_changes()` läuft THEN entsteht kein Beginn-Alarm (Erscheinen
      eines Ereignisses ist Sache der Stufen-Änderung, nicht der Onset-Weiche).
- [ ] Test 7: GIVEN Gewitter verschiebt sich UND die Stufe ändert sich
      gleichzeitig WHEN das Alarm-Protokoll (#1954) den Lauf auswertet THEN
      liegen zwei getrennte Einträge vor, Register-Paare `("thunder","max")`
      und `("thunder","onset")`.
- [ ] Test 8: GIVEN eine Verschiebung ohne Kalendergrenze (z. B. 12:00 →
      10:00) WHEN der Alarmtext gerendert wird THEN steht „10:00"/„12:00" und
      „2 h früher" im Text — nicht „10 h", nicht „−2 h".
- [ ] Test 9: GIVEN ein Beginn-Alarm für eine Trip-Etappe WHEN E-Mail-,
      Telegram-, SMS- und Premium-SMS-Ausgabe für denselben Lauf gerendert
      werden THEN enthält jeder der vier Kanäle den Beginn-Alarm; derselbe
      Nachweis wird für den Ortsvergleichs-Pfad erbracht.

## Acceptance Criteria

- **AC-1:** Given ein Trip-Segment mit Gewitterbeginn 17:00 im letzten
  Wetter-Anker und einem frischen Wetterstand mit Gewitterbeginn 15:00 bei
  Empfindlichkeit „standard" / When der Änderungs-Wächter den Lauf auswertet
  / Then erhält der Nutzer genau einen Beginn-Alarm für dieses Segment — die
  Verschiebung um 2 Stunden nach vorn überschreitet die Schwelle „ab 1 h
  früher". Analog gilt derselbe Mechanismus für einen Starkregen-Beginn
  (`precip_heavy_onset_utc`) mit eigener Fixture.
  - Test: Test 1 aus dem Test Plan — Alarm-Auslösung aus Nutzersicht
    (entstandene `WeatherChange`/`AlertEvent`), kein Dateiinhalt-Check.

- **AC-2:** Given dieselbe Ausgangslage wie AC-1, aber die Verschiebung geht
  in die Gegenrichtung (Beginn 17:00 → 19:00, „standard") / When der
  Änderungs-Wächter denselben Lauf auswertet / Then erhält der Nutzer
  **keinen** Alarm — 2 Stunden Verzögerung liegen unter der für „später"
  geltenden Schwelle von 3 Stunden. Bewacht die vom PO verlangte Asymmetrie
  (früher ist gefährlicher als später).
  - Test: Test 2 aus dem Test Plan — Gegenprobe zu AC-1 auf denselben
    Rohdaten, nur die Richtung ändert sich.

- **AC-3:** Given ein Gewitterbeginn, der sich über Mitternacht verschiebt
  (23:00 im Anker, 01:00 im frischen Stand) / When der Nutzer den
  resultierenden Alarmtext liest / Then liest er „2 h später" — nicht eine
  aus nackten Stundenzahlen fehlberechnete „22 h früher". Bewacht, dass die
  Verschiebung über echte Zeitpunkte, nicht über Stundenzahlen, berechnet
  wird.
  - Test: Test 3 aus dem Test Plan — Alarmtext einer Kalendergrenz-Fixture
    auf Richtung und Betrag prüfen.

- **AC-4:** Given eine Etappe mit Gewitterbeginn 14:00 innerhalb des
  Tagesfensters / When derselbe Datenstand sowohl das Trip-Briefing rendert
  als auch die Alarm-Vergleichsbasis berechnet / Then zeigen beide dieselbe
  Onset-Stunde 14:00 — der Alarm bezieht sich auf exakt die Zahl, die der
  Nutzer im Briefing liest, nicht auf eine ungefilterte, evtl. nächtliche
  Ersterkennung.
  - Test: Test 4 aus dem Test Plan — Gleichheitsprüfung beider Größen aus
    derselben Fixture (Muster #1493 AC-9), keine zwei getrennten
    Textprüfungen.

- **AC-5:** Given einen Wetter-Anker, der vor Einführung dieses Features
  gespeichert wurde und die neuen Onset-Felder nicht enthält / When dieser
  Anker geladen und gegen einen frischen Stand verglichen wird / Then bricht
  die Auswertung nicht ab und es entsteht kein fälschlicher Beginn-Alarm —
  Bestandsdaten bleiben nutzbar (Read-Modify-Write, kein Datenverlust).
  - Test: Test 5 aus dem Test Plan — Anker-Fixture ohne die neuen Felder,
    Vergleichslauf schlägt weder mit Ausnahme noch mit Fehlalarm fehl.

- **AC-6:** Given ein Ereignis, das im alten Stand noch gar nicht existierte
  (Onset `None`) und im frischen Stand erstmals auftritt (Onset 15:00) / When
  der Änderungs-Wächter den Lauf auswertet / Then entsteht **kein**
  Beginn-Verschiebungs-Alarm für dieses Auftauchen — das Erscheinen eines
  Ereignisses ist bereits Sache des bestehenden Stufen-Alarms, nicht der
  neuen Onset-Weiche, sonst würde derselbe Vorgang doppelt gemeldet.
  - Test: Test 6 aus dem Test Plan — `None → Wert` erzeugt keine
    `WeatherChange` über die Onset-Weiche.

- **AC-7:** Given ein Lauf, in dem sich Beginn **und** Stufe eines Gewitters
  gleichzeitig ändern / When der Nutzer das Alarm-Protokoll (#1954) für
  diesen Lauf einsieht / Then findet er zwei getrennt ausgewiesene Einträge
  für Gewitter — einen für den Stufenwechsel, einen für den
  Beginn-Wechsel — statt eines Eintrags, in dem der größere nackte Betrag den
  anderen verdeckt.
  - Test: Test 7 aus dem Test Plan — Protokoll-Register-Paare
    `("thunder","max")` und `("thunder","onset")` beide vorhanden und
    inhaltlich unterschieden.

- **AC-8:** Given einen Beginn-Alarm ohne Kalendergrenze (z. B. Verschiebung
  12:00 → 10:00) / When der Nutzer den Alarmtext auf einem beliebigen der
  vier Kanäle liest / Then liest er Uhrzeiten im Format „10:00"/„12:00" und
  die Verschiebung als „2 h früher" — nicht als gerundete Zahl mit
  Einheit „h" (die für Uhrzeiten Unfug wäre) und nicht mit Minuszeichen
  statt Richtungswort.
  - Test: Test 8 aus dem Test Plan — Textform-Prüfung auf dem gerenderten
    Alarmtext, kein Dateiinhalt-Grep auf Formatierfunktionen.

- **AC-9:** Given einen ausgelösten Beginn-Alarm für ein Trip-Segment und
  denselben Alarm-Typ im Ortsvergleichs-Pfad für einen verglichenen Ort /
  When die Nachrichten für E-Mail, Telegram, SMS und Premium-SMS erzeugt
  werden / Then enthält jeder der vier Kanäle in **beiden** Flächen (Trip und
  Ortsvergleich) den Beginn-Alarm — kein Kanal und keine Fläche wird
  ausgelassen (CLAUDE.md: alle vier Kanäle sind gleichrangig relevant).
  - Test: Test 9 aus dem Test Plan — vier Kanal-Renderer plus
    Ortsvergleichs-Pfad aus demselben Alarm-Lauf, Beginn-Alarm-Inhalt in
    jedem einzeln nachgewiesen.

## Known Limitations

- **Alle drei PO-Freigabe-Punkte sind entschieden (2026-08-18):**
  Preset-Schwellen wie tabelliert · Beginn- und Stufenänderung werden beide
  gemeldet, im Alarmtext zusammengefasst und im Protokoll getrennt ·
  Starkregen-Onset nutzt `precip_1h_mm` als Fallback gegen dieselbe
  4,0-mm/h-Schwelle. Siehe die ✅-Markierungen in „Implementation Details".
- **Aktivierungs-Kopplung (gewollt):** Der Alarme-Tab zeigt nur Metriken,
  deren Katalog-Größe im Wetter-Tab aktiv ist. Da der Beginn-Alarm an den
  bestehenden Katalog-IDs `thunder`/`precipitation` hängt, erbt er deren
  Sichtbarkeits-Gate automatisch — wer Gewitter nicht beobachtet, sieht auch
  keinen Gewitterbeginn-Alarm. Kein Zusatzcode nötig.
- **Kein Bezug zu #1493:** Die Darstellung der Onset-Stunde im Briefing
  selbst ist bereits geliefert (#1493) und wird hier nicht verändert — diese
  Spec fügt ausschließlich die Alarm-Auswertung hinzu und liest dieselbe
  Zahl mit, die #1493 sichtbar macht.
- **Kein Nowcast-Bezug:** Der Radar-Nowcast-Weg („in ~20 Minuten") bleibt
  unverändert; dieser Alarm läuft ausschließlich über den Forecast-
  Vergleichspfad.
- **Go/Frontend-Parität:** Nach jeder Änderung an `_PRESET_TABLE` bzw. am
  `AlertMetric`-Katalog müssen `scripts/generate_alert_preset_table.py` und
  `scripts/generate_alert_metric_mapping.py` laufen, sonst schlagen die
  Frische-Ratschen (`test_alert_preset_table_parity.py`,
  `test_alert_metric_mapping_parity.py`) fehl.

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** keine
- **Rationale:** Erweitert ausschließlich bestehende, bereits etablierte
  Mechanismen (Summary-Feld → Alarm-Metrik → Preset-Tabelle → Renderer,
  vollständig analog zur bestehenden Niveau-Weiche für `thunder_level_max`).
  Kein neuer Kanal, kein neuer Provider, kein neues Auth-/Persistenz-Modell,
  kein neues Editor-Paradigma — keine der in CLAUDE.md genannten
  Entscheidungsflächen ist strukturell betroffen. Die Asymmetrie (zwei
  Schwellen statt einer) ist neu in ihrer Konkretisierung, folgt aber
  demselben Preset-Tabellen-Muster, das die bestehende Architektur bereits
  für die Niveau-Weiche etabliert hat.

## Changelog

- 2026-08-18: Initial spec created
