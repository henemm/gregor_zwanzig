---
entity_id: feat_1444_s2a_schwellen_namensraum
type: module
created: 2026-08-01
updated: 2026-08-01
status: draft
version: "1.1"
tags: [alerts, trips, corridors, threshold, metric-catalog]
---

# Schwellen-Wächter erreicht beide Metrik-Namensräume — Gewitter und Regen melden endlich (Issue #1444, Scheibe 2a)

## Approval

- [x] Approved — PO-Freigabe 2026-08-01 („go"), 7 ACs

## Purpose

Der Schwellen-Wächter aus Scheibe 1 (#1444 S1) erkennt eine gerissene
Nutzer-Grenze nur, wenn `corridor.metric` im alten `AlertMetric`-Namensraum
benannt ist (10 Kennungen). Seit der #1425-Migration schreibt der
Korridor-Editor Wertebereichs-Zeilen zunehmend im Katalog-`key`-Namensraum
(18 weitere Pool-Größen, darunter Gewitter und Regen) — dort schlägt der Wächter
heute still fehl, und genau das ist der Grund, warum AC-4 des Issues
(„nachgewiesen mindestens für Gewitter und Regen") von Scheibe 1 nicht erfüllt
wurde. Diese Scheibe erweitert die Auflösung additiv über das zentrale
Register, ohne den Änderungs-Wächter zu berühren.

**Die maßgebliche Zahl** (alle anderen Zählungen in dieser Spec leiten sich
daraus ab): Der Trip-Wertebereichs-Pool hat **23 Zeilen** — 5 fest verdrahtete
(`ROUTE_METRIC_DEFS`, `AlertMetric`-Namensraum) plus 18 Katalog-Zusätze
(`buildRouteMetricDefsFromCatalog`, Katalog-`key`-Namensraum; 26 Katalog-Einträge
minus 6 bereits durch die 5 alten abgedeckte minus 2 als Von/Bis-Bereich
untaugliche). **Heute auswertbar: 5 von 23. Nach dieser Scheibe: 23 von 23.**
Auf der Ebene der Kennungen: bisher 10 auflösbare `AlertMetric`-Kennungen,
zusätzlich 25 auflösbare Katalog-Kennungen (alle 26 lösen auf,
`precip_type_dominant` wird bewusst ausgeschlossen — s. AC-7).

## Source

- **File:** `src/services/corridor_threshold.py`
- **Identifier:** `evaluate_corridor_thresholds()` (erweiterte Metrik-Auflösung), neue private Hilfsfunktion `_resolve_summary_field()`

Betroffene Schichten — **ausschließlich Python-Core**, kein Frontend:

| Datei | Änderung | Zweck |
|---|---|---|
| `src/services/corridor_threshold.py` | MODIFY | Neue Hilfsfunktion `_resolve_summary_field()`: primär `_ALERT_METRIC_TO_SUMMARY_FIELD` (unverändert), additiver Rückfall über den Compare-Metrik-Katalog. `evaluate_corridor_thresholds()` nutzt sie statt des direkten Dict-Zugriffs. Enum-Erkennung auf `ThunderLevel` verengt (sonst Absturz bei `precip_type_dominant`). |
| `src/output/renderers/alert/project.py` | MODIFY | `_resolve_corridor_metric_id()` (Zeile ~104–140) importiert und nutzt dieselbe `_resolve_summary_field()` statt des lokalen `_ALERT_METRIC_TO_SUMMARY_FIELD.get()` — sonst wird ein im Wächter erkannter Treffer bei der Projektion erneut verschluckt. |
| `tests/tdd/test_corridor_threshold_alert.py` | MODIFY | Nachweis Gewitter + Regen über den Katalog-Namensraum (AC-1/AC-2), eine bisher unerreichbare, nicht-`alarm_capable` Größe (AC-3), Regression der alten Kennungen (AC-4), Grenze eingehalten (AC-5), Gegenprobe Änderungs-Wächter (AC-6), `precip_type_dominant` (AC-7). |

Keine neue Datei, kein neues ADR (ADR-0040 deckt den Alarm-Typ bereits ab —
siehe Abschnitt „Architektur-Entscheidung").

## Estimated Scope

- **LoC:** ~30 Produktivcode (`corridor_threshold.py` ~20, `project.py` ~10) / ~130 Tests
- **Files:** 3 (2 geändert Produktivcode, 1 Testdatei erweitert)
- **Effort:** medium

Beide Werte liegen deutlich unter dem 250-Zeilen-Limit; kein Override nötig.

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `services.weather_change_detection._ALERT_METRIC_TO_SUMMARY_FIELD` | nutzt (unverändert) | primärer Auflösungsweg für die 10 alten `AlertMetric`-Kennungen; bleibt exklusiv Grundlage des Änderungs-Wächters |
| `output.renderers.compare_metric_catalog.COMPARE_METRIC_CATALOG` | nutzt | liefert je Katalog-`key` das Paar `(metric_id, aggregation)` — Quelle des additiven Rückfalls |
| `app.metric_catalog.summary_field_for(metric_id, aggregation)` | nutzt | löst das Paar auf ein `SegmentWeatherSummary`-Feld auf (bestehende Funktion, unverändert) |
| `app.models.ThunderLevel` | nutzt | verengt die Enum-Erkennung in `evaluate_corridor_thresholds()`, damit `precip_type_dominant` nicht über `thunder_ordinal()`/`float()` läuft |
| `services.corridor_threshold.evaluate_corridor_thresholds()` | erweitert | einzige Stelle, die Korridor-Metrik in ein Summary-Feld auflöst — Quelle für `project.py` |
| `output.renderers.alert.project._resolve_corridor_metric_id()` | erweitert | übernimmt denselben Auflösungsweg für die Label-Projektion |

**Ausdrücklich NICHT verwendet:** `app.metric_catalog.alert_metric_for()`. Diese
Funktion beantwortet die Rückwärtsrichtung (Katalog-ID → `AlertMetric`) und
trägt die Mehrdeutigkeit, die in Scheibe 1 den CRITICAL (`ValueError` bei
`snow_line`) verursacht hat. Sie berührt die hier benötigte Vorwärtsrichtung
(`key` → Summary-Feld) nicht und darf für diese Auflösung nicht herangezogen
werden — `summary_field_for()` ist die unzweideutige, bereits vorhandene
Quelle.

## Implementation Details

### 1. Eine Auflösungsfunktion, additiver Rückfall

```
_resolve_summary_field(metric: str) -> str | None:
    feld = _ALERT_METRIC_TO_SUMMARY_FIELD.get(metric)      # unveraendert, 10 alte Kennungen
    wenn feld: return feld
    eintrag = COMPARE_METRIC_CATALOG-Eintrag mit key == metric
    wenn kein eintrag: return None
    return summary_field_for(eintrag.metric_id, eintrag.aggregation)
```

Die Katalog-Eintraege werden einmalig bei Modulimport nach `key` indiziert
(Vorbild: der bestehende Umkehr-Index `_KEY_BY_METRIC_AGGREGATION` in
`compare_metric_catalog.py`). Der alte Weg bleibt textuell und funktional
unangetastet — er wird nur zuerst gefragt und bei Treffer nicht mehr verlassen.
`evaluate_corridor_thresholds()` (Zeile 61 heute) ruft `_resolve_summary_field()`
statt `_ALERT_METRIC_TO_SUMMARY_FIELD.get()` auf; `project.py`
(`_resolve_corridor_metric_id`, Zeile 128 heute) importiert dieselbe Funktion
aus `services.corridor_threshold` statt eine zweite Kopie der Logik zu
pflegen.

### 2. Enum-Erkennung verengen (Absturzschutz für `precip_type_dominant`)

`summary_field_for("precip_type", "max")` löst regulär auf
`precip_type_dominant` auf — der Katalog-Rückfall macht diese Größe damit
technisch erreichbar, obwohl sie keine Ordinalskala hat (S1-Known-Limitation).
Der heutige Code in `evaluate_corridor_thresholds()` behandelt **jeden**
`Enum`-Wert über `thunder_ordinal()`; für `PrecipType` (kein `ThunderLevel`)
liefert das kein aussagekräftiges Ordinal, und das anschließende `float(value)`
würde auf einem `PrecipType`-Wert eine `ValueError` werfen — ein Absturz des
gesamten Alarm-Laufs für die betroffene Tour. Fix: die Enum-Prüfung wird auf
`ThunderLevel` verengt; jeder andere Enum-Wert überspringt den Korridor
(`continue`, dieselbe R6-Semantik wie „unbekannte Metrik" oder „fehlender
Wert" direkt daneben) statt in `float()` zu laufen.

### 3. `project.py` unverändert in der Tie-Break-Logik

`_resolve_corridor_metric_id()` sucht nach dem aufgelösten Feld weiterhin
unter `_METRICS` nach Kandidaten (`field in m.summary_fields.values()`) und
wählt bei Mehrdeutigkeit per `cmp`-Übereinstimmung — diese Logik ist vom
F001-Fix aus S1 und bleibt unverändert. Sie bekommt durch die erweiterte
`_resolve_summary_field()` lediglich mehr Fälle, für die sie überhaupt
aufgerufen wird.

## Expected Behavior

- **Input:** `corridor.metric` in einem der zwei Namensräume (10 alte
  `AlertMetric`-Kennungen ODER 25 Katalog-`key`-Kennungen mit Zahlenwert je
  Etappe), Wetterpunkt mit passendem Summary-Feld.
- **Output:** `CorridorHit`, wenn die Grenze gerissen ist — unabhängig davon,
  aus welchem Namensraum die Metrik-Kennung stammt. `precip_type_dominant`
  erzeugt nie einen Treffer (keine Ordinalskala).
- **Side effects:** keine über die in S1 beschriebenen hinaus (Melde-Gedächtnis,
  Cooldown, Tageszähler — alles unverändert; diese Scheibe ändert nur, *welche*
  Metriken die Auswertung erreicht, nicht *wie* sie entprellt wird).

## Invarianten (nicht verhandelbar)

1. **Der Änderungs-Wächter verhält sich byteidentisch weiter.**
   `_ALERT_METRIC_TO_SUMMARY_FIELD` wird von `weather_change_detection.py`
   direkt und unverändert weiterbenutzt; diese Scheibe fügt dort keine Zeile
   hinzu und importiert es nur lesend. Eine `AlertRule`, deren `metric`-Wert
   ausschließlich im Katalog-Namensraum existiert (z.B. `"thunder_level_max"`),
   darf im Änderungs-Wächter weiterhin **nicht** auflösen — der additive
   Rückfall ist ausschließlich in `corridor_threshold.py`/`project.py`
   verdrahtet, nicht in `weather_change_detection.py`.
2. **`snow_line` bleibt eindeutig.** Die feldbasierte Auflösung in
   `project.py:104-140` (F001-Fix aus S1) bleibt der einzige Weg zur
   Katalog-Metrik-ID; kein Rückfall auf die `AlertMetric`-Enum-Mehrdeutigkeit.
3. **Ein nicht projizierbarer Treffer verschluckt die restliche Nachricht
   nicht.** Die F001-Härtung in `to_corridor_events()` (Try/Except je Treffer,
   ADR-0018: ausweichen ja, kaschieren nein) bleibt unverändert bestehen.
4. **Kein Frontend in dieser Scheibe.** Der Schalter „Warnen" und der
   ehrliche Editor-Text sind Scheibe 2b; diese Scheibe ändert `data/`-Verhalten
   auf einer Ebene, die der Nutzer nicht direkt bedient.
5. **`alert_metric_for()` ist für diese Auflösung tabu.** Die Vorwärts-Auflösung
   `key → Summary-Feld` läuft ausschließlich über `summary_field_for()`. Die
   Rückwärts-Funktion `alert_metric_for()` (Katalog-ID → `AlertMetric`) trägt
   die S1-CRITICAL-Mehrdeutigkeit und darf hier nicht herangezogen werden —
   auch nicht als vermeintliche Abkürzung in einer späteren Refaktorierung.

## Acceptance Criteria

- **AC-1:** Given eine Tour mit dem Gewitter-Wertebereich `thunder_level_max`
  (Katalog-Namensraum, „höchstens keins") und einer Vorhersage, die im aktiven
  Etappenfenster Gewitter zeigt / When der Alarm-Lauf läuft / Then geht genau
  eine Sofort-Meldung raus, die Größe, Ist-Wert, Etappe und Zeitfenster nennt.
  - Test: `check_and_send_alerts()` mit einem Korridor `metric="thunder_level_max"`
    (nicht `"thunder_level"`) — heute still übersprungen, da nur der alte
    Namensraum aufgelöst wird.

- **AC-2:** Given eine Tour mit dem Regen-Wertebereich `precip_sum_mm`
  (Katalog-Namensraum) und einer Vorhersage, die die Grenze reißt / When der
  Alarm-Lauf läuft / Then geht genau eine Sofort-Meldung raus, die Größe,
  Ist-Wert, Etappe und Zeitfenster nennt.
  - Test: `check_and_send_alerts()` mit einem Korridor `metric="precip_sum_mm"`
    (nicht `"precipitation_sum"`) — analog zu AC-1 für eine stetige Größe.

- **AC-3:** Given eine Tour mit einem Wertebereich auf einer bisher
  unerreichbaren Größe, die NICHT `alarm_capable` ist (z.B. `snow_depth_cm`
  oder `sunny_hours_h`) und einer Vorhersage, die die Grenze reißt / When der
  Alarm-Lauf läuft / Then geht eine Sofort-Meldung raus.
  - Test: Korridor `metric="snow_depth_cm"` mit gerissener Grenze — belegt die
    Korrektur an der Ticket-Skizze: `alarm_capable` ist NICHT die maßgebliche
    Bedingung, ein Zahlenwert je Etappe genügt.

- **AC-4:** Given eine Tour mit Wertebereichen unter den alten
  `AlertMetric`-Kennungen `snow_line` und `wind_gust` und einer Vorhersage, die
  deren Grenzen reißt / When der Alarm-Lauf läuft / Then melden sie unverändert
  weiter wie vor dieser Scheibe.
  - Test: je ein Regressionsfall für **`snow_line`** (die Kennung, deren
    Mehrdeutigkeit in Scheibe 1 den CRITICAL ausgelöst hat — hier zusätzlich mit
    OBERER Grenze, dem damaligen Absturzfall) und für **`wind_gust`** (stetige
    Größe, häufigster Realfall). Beide sind Zeilen des heutigen Pools, nicht nur
    Altbestand. Zusätzlich muss die gesamte S1-Testsuite
    (`tests/tdd/test_corridor_threshold_alert.py`) grün bleiben.

- **AC-5:** Given eine Tour mit einem Wertebereich im Katalog-Namensraum
  (z.B. `thunder_level_max`) und einer Vorhersage, die die Grenze einhält /
  When der Alarm-Lauf läuft / Then geht keine Meldung raus.
  - Test: `check_and_send_alerts()` mit Wert innerhalb des Bereichs — kein
    Versand, auch im neuen Namensraum.

- **AC-6:** Given eine `AlertRule` des Änderungs-Wächters mit einer Metrik-
  Kennung, die ausschließlich im Katalog-Namensraum existiert (z.B.
  `"thunder_level_max"`) / When die Änderungs-Erkennung
  (`weather_change_detection`) darüber läuft / Then bleibt sie wirkungslos wie
  vor dieser Scheibe — der additive Rückfall bleibt strukturell auf den
  Schwellen-Pfad beschränkt.
  - Test: `_ALERT_METRIC_TO_SUMMARY_FIELD.get("thunder_level_max")` ist weiterhin
    `None`, UND ein direkter Aufruf der Änderungs-Erkennungsfunktion mit einer
    entsprechenden Regel liefert kein Ergebnis — Gegenprobe, kein bloßer
    Konstanten-Check.
  - Zusatz-Assert in derselben Testfunktion (kein eigenes Gate, kein neuer
    Wächter im Sinne des Regel-Budgets): die beiden Namensräume sind
    **kollisionsfrei** — die Schlüsselmenge von `COMPARE_METRIC_CATALOG` und die
    von `_ALERT_METRIC_TO_SUMMARY_FIELD` überschneiden sich nicht (heute gemessen:
    26 vs. 10, Schnittmenge leer). Das ist die Voraussetzung dafür, dass der
    Rückfall keinen bestehenden Fall überschreiben kann; bricht ein künftiger
    Katalog-Eintrag sie, schlägt dieser Test an statt still das Verhalten zu
    verschieben.

- **AC-7:** Given eine Tour mit einem Wertebereich auf `precip_type_dominant`
  (Niederschlagsart, Aufzählung ohne Ordinalskala) / When der Alarm-Lauf läuft
  / Then bricht der Lauf nicht ab und es geht keine Meldung für diese Größe
  raus.
  - Test: Korridor `metric="precip_type_dominant"` mit beliebigem
    `PrecipType`-Wert im Wetterpunkt — kein Crash, `hits == []` für diesen
    Korridor.

## Known Limitations

- **`precip_type_dominant` bleibt dauerhaft ausgeschlossen**, nicht nur für
  diese Scheibe — dieselbe strukturelle Ausnahme wie in S1 (Aufzählung ohne
  Ordinalskala). Eine künftige Ordinal-Definition für Niederschlagsarten wäre
  ein eigener Arbeitsgang.
- **Kein Bedienelement.** Ob der Nutzer für eine der 18 neu erreichbaren
  Pool-Zeilen überhaupt „warnen" einschalten kann, hängt vom Editor ab
  (Scheibe 2b). Diese Scheibe macht den Wächter ehrlich für Korridore, die
  bereits existieren — und das sind nicht wenige: Neu angelegte Trip-Zeilen
  stehen fest auf `notify: true` (`ROUTE_CTX_DEFAULTS`,
  `corridorEditorState.ts:56`), jeder seit #1425 im Editor gesetzte
  Wertebereich meldet also ab dieser Scheibe.
- **`precip_type_dominant` steht gar nicht im Pool** — der Editor filtert es
  über `_COMPARE_RANGE_UNSUPPORTED`
  (`compareMetricCatalogLoader.ts:38`) heraus. AC-7 sichert daher keinen über
  die Oberfläche erreichbaren Weg ab, sondern gespeicherte bzw. über die
  Schnittstelle gesetzte Korridore. Der Absturz wäre trotzdem real (kompletter
  Alarm-Lauf der Tour), deshalb bleibt die Absicherung.
- **Kein neues Capability-Feld.** Weil alle 23 Pool-Zeilen nach dieser Scheibe
  schwellenfähig sind, braucht Scheibe 2b weder ein zusätzliches Registerfeld
  noch eine Endpoint-Erweiterung noch eine `alarmCapable`-Durchreiche durch
  `buildRouteMetricDefsFromCatalog`. Das bestehende `alarmCapable` bleibt
  unangetastet — es beantwortet ausschließlich die Änderungs-Wächter-Frage und
  ist per `test_alert_metric_identity_delivery.py` auf 10 Schlüssel
  festgenagelt. Der naheliegende Fehler wäre, den Schalter aus Scheibe 2b an
  `alarmCapable` zu hängen; dann bekäme z.B. die Wind-Zeile (`wind_max_kmh` →
  `wind_change`) einen bedienbaren, aber wirkungslosen Schalter — exakt der
  #1425-Fehlertyp, den diese Arbeit beseitigt.
- **Mehrfachmeldung bei zwei Namen für dasselbe Wetterfeld → #1455**
  (Adversary-Finding F001, MEDIUM, 2026-08-02). Mehrere `corridor.metric`-Namen können auf
  dasselbe `SegmentWeatherSummary`-Feld zeigen; die Entprellung in `trip_alert.py:388-389`
  schlüsselt nach dem **rohen** Namen, nicht nach dem aufgelösten Feld — dieselbe Wetterlage
  kann dann mehrfach melden, und zwar dauerhaft.
  **Überwiegend vorbestehend seit S1:** `AlertMetric.SNOW_LINE` und
  `AlertMetric.FREEZING_LEVEL` zeigen beide auf `freezing_level_m` (gemessen). Diese Scheibe
  erweitert das um den Katalog-Namensraum, praktisch relevant nur für Gewitter
  (`thunder_level` alt vs. `thunder_level_max` neu); `freezing_level_m` ist über die
  Oberfläche nicht als Wertebereich anlegbar (Namensraum-Brücke filtert ihn aus dem Pool).
  **Bewusst hier nicht behoben:** Blindes Entdoppeln nach Feld wäre falsch — zwei
  Wertebereiche auf demselben Zahlenwert können verschiedene, legitime Absichten sein
  („Schneefallgrenze höchstens 1500" und „Nullgradgrenze mindestens 2000"). Der Fix braucht
  eine fachliche Entscheidung und berührt persistierte Gedächtnis-Schlüssel. Siehe #1455.
- **Rauschen:** mehr auswertbare Größen bedeuten potenziell mehr Meldungen;
  die bestehende Entprellung (S1, Schlüsselraum `corridor:<metrik>:<etappe>`)
  greift unverändert, wird aber in dieser Scheibe nicht erneut bewiesen
  (bereits durch AC-3/AC-4 der S1-Spec abgedeckt).

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** ADR-0040 (bestehend, keine neue ADR)
- **Rationale:** ADR-0040 legt den Schwellen-Alarm als additiven, vom
  Änderungs-Wächter unabhängigen zweiten Alarm-Typ fest. Diese Scheibe
  ändert an dieser Konstruktion nichts — sie repariert lediglich die
  **Reichweite** der Metrik-Auflösung innerhalb des bereits entschiedenen
  additiven Pfads. Invariante 1 aus dem Abschnitt „Invarianten" oben ist die
  Umsetzung der in ADR-0040 Punkt 3 („eigener Render-Vertrag") und implizit
  Punkt 1 („kein systemseitiger Absolutwert") verankerten Trennung: der
  Änderungs-Wächter bekommt durch diese Scheibe keine neue Reichweite.

  **Korrektur an der Ticket-Skizze:** Das ursprüngliche Ticket schlug vor,
  Alarmfähigkeit aus dem Register-Feld `alarm_capable` abzuleiten. Gemessen
  beantwortet dieses Feld eine andere Frage — „hat eine Alarm-Identität für
  den Änderungs-Wächter" — und deckt nur 10 von 26 Katalog-Größen ab, teils
  mit falschem Ergebnis in beide Richtungen (`wind_max_kmh`: `alarmCapable:
  true`, aber die zugehörige Alarm-Identität ist eine Änderungsrate, als
  Schwellwert sinnlos; `sunny_hours_h`/`snow_depth_cm`/`uv_index_max`/
  `pop_max_pct`: `alarmCapable: false`, obwohl ein Zahlenwert je Etappe
  vorliegt und ein Schwellen-Alarm dafür sinnvoll ist). Die für den
  Schwellen-Alarm maßgebliche Frage ist stattdessen „existiert ein Zahlenwert
  je Etappe" — beantwortet durch `summary_fields`/`summary_field_for()`. Das
  ist konsistent mit ADR-0040: der Schwellen-Alarm ist additiv und nicht an
  die Identitäten des Änderungs-Wächters gebunden. AC-3 dieser Spec belegt das
  konkret an einer nicht-`alarm_capable` Größe.

## Changelog

- 2026-08-01: Initial spec created (Issue #1444, Scheibe 2a)
- 2026-08-01: Zweitprüfung eingearbeitet — `alert_metric_for()` explizit als
  Tabu markiert (Dependencies + Invariante 5), Known Limitations um „kein
  neues Capability-Feld" ergänzt (alarmCapable bleibt unangetastet, 10
  Schlüssel per `test_alert_metric_identity_delivery.py` festgenagelt).
