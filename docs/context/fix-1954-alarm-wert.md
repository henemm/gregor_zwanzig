# Context: #1954 — Alarm-Protokoll haelt den Wert der gemeldeten Groesse fest

Workflow: `fix-1954-alarm-wert` · Branch: `fix-1954-alarm-wert-protokollieren` · Track: Standard
Issue: https://github.com/henemm/gregor_zwanzig/issues/1954 (Folgebefund B3 aus #1459, Epic #1458)

## Request Summary

Das Alarm-Protokoll haelt je Meldung fest, **welche** Wettergroesse gemeldet wurde
(Register-Paar `metric_id` + `aggregation`), aber nicht **welchen Wert** sie hatte.
Damit ist nicht auflösbar, ob eine zweite Meldung zur selben Groesse eine Wiederholung
oder eine neue Information war — Kennzahl **K1** aus Epic #1458 bleibt dauerhaft nur
teilweise messbar (Basislinie 66,7 % ist heute eine Obergrenze, kein exakter Wert).

## Related Files

| File | Relevance |
|------|-----------|
| `src/services/alert_log.py:226-229` | Schreibstelle: `metrics`-Liste im Eintrag, heute nur `metric_id`+`aggregation` |
| `src/services/alert_log.py:66-69` | `_norm_pairs()` — dedupliziert per `(metric_id, aggregation)`-Tupel, sortiert |
| `src/services/alert_log.py:72-81` | `register_pairs_from_changes()` — nutzt nur `c.metric`, verwirft `c.new_value` |
| `src/services/alert_log.py:84-96` | `register_pairs_from_corridor_hits()` — **kein Produktiv-Aufrufer** (nur Test) |
| `src/services/alert_log.py:99-109` | `register_pairs_for_nowcast()` — nimmt nur `bool`, **hat strukturell keinen Messwert** |
| `src/services/alert_log.py:322` | `append_suppressed_entry()` schreibt bewusst `"metrics": []` (Gate-Zeitpunkt, nichts erkannt) |
| `src/services/alert_log.py:444-460` | **Leseseite** `undelivered_incidents()`: extrahiert gezielt nur `(metric_id, aggregation)` |
| `src/app/models.py:533-561` | `WeatherChange` mit `old_value`/`new_value`/`delta`/`threshold` (alle `float`) |
| `src/services/corridor_threshold.py:56-65` | `CorridorHit` mit `value` + `bound` (`float`) |
| `src/services/trip_alert.py:361-373` | Aufrufer Vorhersage-Aenderung → `register_pairs_from_changes(to_report)` |
| `src/services/trip_alert.py:1331-1338` | Aufrufer Radar-Nowcast → `register_pairs_for_nowcast(...)` |
| `src/services/compare_alert.py:327-333` | Aufrufer Vergleich/Vorhersage-Aenderung → `register_pairs_from_changes(alle_changes)` |
| `src/services/compare_radar_alert.py:214-221` | Aufrufer Vergleich/Radar → `register_pairs_for_nowcast(...)` |
| `src/output/renderers/email/undelivered_hint.py:85-102` | `_subject()` — Docstring behauptet explizit „keinen Messwert"; entpackt Paare als 2-Tupel |
| `src/output/renderers/email/undelivered_hint.py:120-126` | `_group_key()` gruppiert u.a. ueber `inc.metrics` |
| `tests/tdd/test_alert_log_metrics.py` | Bestandstests AC-1..AC-4/AC-7 zum `metrics`-Feld |
| `docs/specs/modules/feat_1459_alert_protokoll.md:264-265, 510` | Spec legt das Schema heute **zweigliedrig** fest |

## Existing Patterns

- **Additive Schema-Erweiterung ohne Migration** ist im Modul etabliert: `hazards`, `reason`,
  `blocked_reason_codes`, `below_threshold_channels` kamen nacheinander additiv dazu.
  Die Modul-Docstring nennt das ausdruecklich („kommt additiv dazu, ohne Schema-Migration", `:41-44`).
- **Read-Modify-Write ueber die volle Datei** (`_append()`, `:250-256`) — Alt-Eintraege bleiben
  unangetastet, fehlende Felder werden beim Lesen tolerant behandelt.
- **Fail-soft bei nicht aufloesbarer Groesse**: `metric_and_aggregation_for_field()` darf `None`
  liefern, das einzelne Register-Paar faellt weg, der Alarm-Lauf laeuft weiter (`:67-69`).
- **Ordinale Groessen tragen intern eine Zahl, nach aussen nie** — `thunder_ordinal()`
  (`weather_change_detection.py:680-682, 811-812`) macht aus `ThunderLevel` einen Rang; die
  Renderer zeigen das Wort, nie die Zahl (#1503/#1474).

## Dependencies

**Upstream** (was liefert den Wert):
- `WeatherChange.new_value` / `.old_value` / `.delta` / `.threshold` — liegt an beiden
  `register_pairs_from_changes()`-Aufrufstellen bereits im uebergebenen Objekt vor.
- `CorridorHit.value` / `.bound` — vorhanden, aber der Pfad ist produktiv tot (s. Risiken).
- Radar-Nowcast: **kein** Wert im Signaturpfad (`is_convective: bool`).

**Downstream** (wer liest `metrics`):
- `src/services/alert_log.py:444-460` `undelivered_incidents()` → `UndeliveredIncident.metrics`
  als `tuple[tuple[str, str], ...]`. Liest **gezielt zwei Schluessel** aus jedem Dict —
  ein zusaetzlicher Schluessel wird still ignoriert, die Struktur bleibt zweigliedrig.
- `src/output/renderers/email/undelivered_hint.py` `_subject()` (entpackt 2-Tupel) und
  `_group_key()` (Gruppierung von Wiederholungen im „nicht zugestellt"-Hinweis der Mail).
- **Go liest `metrics` NICHT** — `internal/store/log.go` kennt das Feld nicht
  (nur `entity_id`/`entity_type`/Zaehlung). Keine Go-Aenderung noetig.

## Existing Specs

- `docs/specs/modules/feat_1459_alert_protokoll.md` — Protokoll-Spec. Legt in Z.264-265 die
  JSON-Form als `list[{"metric_id", "aggregation"}]` fest und in Z.510 die Signatur als
  `metrics: list[tuple[str, str]]`. **#1954 schreibt diese Spec fort** (v1.2), sie ersetzt sie nicht.
- Spec v1.1 AC-15 (zitiert in `undelivered_hint.py:89-91`) haelt fest, dass das Protokoll
  „ohnehin nur das Register-Paar" fuehrt — diese Begruendung wird durch #1954 hinfaellig und
  muss dort nachgezogen werden, **ohne** die dahinterliegende Zusicherung (#1503/#1474:
  ordinale Groessen nie als Zahl anzeigen) zu beruehren.

## Risks & Considerations

1. **Mehrfachtreffer derselben Groesse in EINEM Lauf** (Hauptentscheidung fuer die Spec).
   `_norm_pairs()` dedupliziert heute per `(metric_id, aggregation)`. Aendern in einem Lauf
   z.B. Boeen auf zwei Etappen, kollabieren sie zu EINEM Paar. Nimmt man den Wert ins
   Dedupe-Tupel auf, zerfaellt die Dedupe-Semantik (zwei nahezu gleiche Fliesskommawerte
   ergaeben zwei Eintraege) und AC-7 aus #1459 („beide Ausloeser in EINEM Eintrag") geraet
   in Gefahr. Die Spec muss festlegen, **welcher** Wert bei mehreren Treffern gewinnt
   (Vorschlag: der fuer die Meldung ausschlaggebende Extremwert) — und dass der Wert
   **nicht** Teil des Dedupe-Schluessels wird.

2. **Radar-Nowcast hat strukturell keinen Wert.** `register_pairs_for_nowcast()` bekommt nur
   `is_convective: bool`. Entweder bleibt das Wert-Feld dort leer (`null`/fehlend) oder der
   Niederschlagswert wird aus dem Radar-Request nachgereicht (groesserer Eingriff, beruehrt
   `trip_alert.py` + `compare_radar_alert.py`). Ein **fehlender** Wert muss vom Schema
   ausdruecklich erlaubt sein, sonst ist K1 fuer Nowcast-Alarme falsch statt unbekannt.

3. **Amtliche Warnungen schreiben `metrics` gar nicht** (sie tragen `hazards`, O1).
   K1 bleibt fuer diese Klasse ueber `hazards` messbar — kein Handlungsbedarf, aber die Spec
   sollte die Grenze benennen, damit sie nicht spaeter als Luecke gemeldet wird.

4. **`append_suppressed_entry()` schreibt bewusst `"metrics": []`** — zum Gate-Zeitpunkt ist
   nichts erkannt. Das bleibt so; ein erfundener Wert waere schlimmer als kein Wert.

5. **Ordinale Groessen (Gewitterstufe) tragen als `new_value` einen Rang, keine Messgroesse.**
   Der Wert darf protokolliert werden (Maschinen-Seite/K1), aber die Leseseite gibt ihn
   ohnehin nicht an die Renderer weiter — die Zusicherung #1503/#1474 („nie als Zahl
   anzeigen") bleibt dadurch unberuehrt. Das ist in der Spec explizit festzuhalten, sonst
   haertet ein spaeterer Umbau den falschen Pfad.

6. **`register_pairs_from_corridor_hits()` hat keinen Produktiv-Aufrufer** (belegt: nur die
   eigene Definition `alert_log.py:84` und `tests/tdd/test_alert_log_metrics.py:94,109`).
   Passt zu ADR-0043 / #1460 P1a: gerissene Wertebereiche sind kein Alarm-Ausloeser mehr.
   Zu klaeren: den toten Pfad mitziehen (Symmetrie, minimale Zusatzkosten, `CorridorHit.value`
   liegt vor) oder unangetastet lassen. Empfehlung: **mitziehen**, damit der Pfad bei einer
   Reaktivierung nicht als einziger ohne Wert dasteht.

7. **Bestandsdaten**: rein additiv, Alt-Eintraege ohne Wert bleiben lesbar (Leseseite liest
   gezielt Schluessel, kein strikter Schema-Check). Keine Migration. Roundtrip-Test noetig,
   der einen Alt-Eintrag OHNE Wert weiterhin korrekt liest.

## PO-Entscheide (Henning, 2026-08-18) — verbindlich fuer die Spec

**E1 — Wertumfang: neuer Wert UND alter Wert.**
Je Register-Eintrag kommen zwei Felder dazu: `value` (der neue, ausschlaggebende Wert) und
`previous_value` (der Wert davor). Begruendung: erst der alte Wert macht einen Stufenwechsel
sichtbar. Zweimal „Boeen 60" ist eine Wiederholung; „20→60" gefolgt von „60→85" sind zwei
echte Informationen. Damit wird K1 exakt statt naeherungsweise messbar.
Die Ausloese-Schwelle (`threshold`) kommt NICHT mit — sie steht in der Trip-Konfiguration.

```json
{"metric_id": "gust", "aggregation": "max", "value": 60.0, "previous_value": 20.0}
```

**E2 — Radar-Nowcast: kein Wert-Feld.**
Nowcast-Eintraege tragen weder `value` noch `previous_value`. Kein Eingriff in
`trip_alert.py` / `compare_radar_alert.py`. Fachliche Begruendung des PO: „Gewitter zieht auf"
IST dieselbe Aussage, unabhaengig von der Staerke — ein erfundener Wert waere schlechter als
keiner. K1 erkennt Nowcast-Wiederholungen weiterhin ueber Groesse + Grund.
**Folge fuer das Schema:** die Wert-Felder sind OPTIONAL. Ein Eintrag ohne Wert bedeutet
„kein Wert erhebbar", nicht „Wert 0" — die K1-Auswertung darf beides nie gleichsetzen.

**E3 — Mehrfachtreffer: der ausschlaggebende Extremwert, EIN Eintrag je Groesse.**
Loest dieselbe Groesse in einem Lauf mehrfach aus (z.B. Boeen auf zwei Etappen), bleibt es bei
EINEM Register-Eintrag; protokolliert wird der Wert der schwerwiegendsten Aenderung.
Operationalisierung: es gewinnt die `WeatherChange` mit dem groessten `abs(delta)` — bei
gleicher Groesse gilt dieselbe Schwelle, groesstes `abs(delta)` ist damit deckungsgleich mit
der hoechsten `ChangeSeverity`. Bei Gleichstand entscheidet stabile Sortierung nach
`segment_id`, damit das Ergebnis reproduzierbar ist.
**Harte Nebenbedingung:** der Wert wird **NICHT** Teil des Dedupe-Schluessels. Dedupliziert
wird weiterhin ausschliesslich ueber `(metric_id, aggregation)` — sonst zerfiele die
Buendelung an Fliesskomma-Rauschen und AC-7 aus #1459 („mehrere Ausloeser → EIN Eintrag")
waere gebrochen.

**E4 — toter Corridor-Pfad wird mitgezogen** (Tech-Lead-Entscheid, nicht PO-vorgelegt).
`register_pairs_from_corridor_hits()` bekommt die Wert-Durchreichung ebenfalls
(`CorridorHit.value` liegt vor, `bound` bleibt draussen — Schwelle, s. E1). Kosten: wenige
Zeilen. Grund: der Pfad soll bei einer Reaktivierung nicht als einziger ohne Wert dastehen.

## Abgeleitete Zusicherungen fuer die Spec

- Rein additiv, keine Migration: Alt-Eintraege ohne die neuen Felder bleiben unveraendert und
  lesbar (Roundtrip-Test noetig).
- Die Leseseite (`undelivered_incidents()`, `:444-460`) bleibt zweigliedrig — die Wert-Felder
  erreichen **nicht** den Mail-Renderer. Damit bleibt die Zusicherung #1503/#1474 („ordinale
  Groessen nie als Zahl anzeigen") unberuehrt, obwohl die Gewitterstufe intern als Rang
  (`thunder_ordinal()`) protokolliert wird.
- `append_suppressed_entry()` bleibt bei `"metrics": []` — zum Gate-Zeitpunkt ist nichts erkannt.
- Amtliche Warnungen bleiben ohne `metrics` (sie tragen `hazards`) — Grenze in der Spec benennen.
- Die Docstring-Aussage in `undelivered_hint.py:89-91` („das Protokoll haelt ohnehin nur das
  Register-Paar fest, keinen Messwert, Spec v1.1 AC-15") wird durch #1954 falsch und ist
  nachzuziehen.
