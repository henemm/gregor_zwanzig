---
entity_id: rework_1460_t1_relevanzfilter
type: refactor
created: 2026-08-02
updated: 2026-08-03
status: draft
version: "1.2"
tags: [alerts, trip, compare, epic-1458, adr-0040-ablösung]
---

# Relevanz-Filter Teil 1: Grenzwert wird Empfindlichkeit, Gedächtnis überlebt das Briefing, amtliche Warnung bekommt Zeitbezug (Issue #1460, Epic #1458 Scheibe 2, Teil 1 von 2)

## Approval

- [x] Approved — PO-„go" 2026-08-02 (28 ACs freigegeben, inkl. Anhebung des LoC-Limits für diesen Durchgang)
- [x] Approved — PO-„go" 2026-08-03 (v1.2: Entwarnung wird symmetrisch gemeldet; dadurch 34 ACs)

## Purpose

Drei reale Fehler in der Alarm-Auswertung werden behoben, ohne ein neues Steuerkonzept
einzuführen: (P1) der Wertebereich (`corridors[].notify`) fällt als eigener Alarm-Auslöser weg —
er widerspricht ADR-0009/ADR-0013 als absolute Grenze; die Empfindlichkeitsstufe (`entspannt` ·
`standard` · `sensibel`) bleibt der einzige Regler und wird für Gewitter (eine Gefahrenstufen-Größe)
tatsächlich wirksam gemacht — heute meldet keine Stufe einen Sprung um genau eine Stufe, weder
aufwärts (Verschärfung) noch abwärts (Entwarnung); beide Richtungen melden künftig symmetrisch
je Stufe. (P2) Das
Melde-Gedächtnis wird beim Briefing-Versand nicht mehr vollständig gelöscht — nur der
Änderungs-Raum, nicht der Raum der amtlichen Warnungen, die dadurch heute jedes Mal ihre Entprellung
verlieren. (P4) Amtliche Warnungen bekommen für Tour UND Ortsvergleich einen echten Zeit-**und**-
Ort-Bezug, statt wie heute jede irgendwann gültige Warnung an jeder Etappen-Koordinate sofort zu
melden — unabhängig davon, ob der Nutzer zur Gültigkeitszeit dort überhaupt ist. Diese Scheibe ist
reiner Python-Kern-Code (kein Go, kein Frontend) und bereitet die Zusammenführung der vier
Ablaufsteuerungen in Teil 2 (#1467) vor, indem sie zuerst festlegt, welches Verhalten dort gilt.

## Source

- **File:** `src/services/trip_alert.py`
- **Identifier:** `TripAlertService._evaluate_corridors`, `TripAlertService.check_official_alert_triggers`

Betroffene Schicht — **ausschließlich Python-Core**, kein Go, kein Frontend:

| Datei | Änderung | Zweck |
|---|---|---|
| `src/services/trip_alert.py` | MODIFY | P1a: `_evaluate_corridors()` (`:358-427`) + Aufruf (`:248-249`) + `_CORRIDOR_STATE_PREFIX`/`_ORDINAL_CORRIDOR_METRICS`-Konstanten (`:51-55`) + `has_corridors`-Flag (`:188`, `:485`) entfernt. P4: `check_official_alert_triggers()` (`:1100-1169`) gibt JEDEM Segment der Restroute (nicht nur dem aktiven) sein eigenes Zeitfenster mit, Dedup-Schlüssel erweitert von `Koordinate` auf `(Koordinate, Fenster)`, Übergabe an `get_official_alerts_for_location()` (`:1151`) |
| `src/services/corridor_threshold.py` | **unverändert** | `evaluate_corridor_thresholds()`/`resolve_corridor_summary_field()`/`CorridorHit` bleiben bestehen — ohne Aufrufer aus `trip_alert.py`, s. Known Limitations |
| `src/services/alert_preset.py` | MODIFY | P1b: `_PRESET_TABLE`-Zeile `THUNDER_LEVEL` trägt Stufen-Semantik statt Delta-Zahl; `_make_rule()`/`expand_per_metric_levels()` reichen sie durch |
| `src/services/weather_change_detection.py` | MODIFY | P1b: `detect_changes()` (`:602`) bekommt einen Ordinal-Zweig für `thunder_level_max`, unverändert für alle anderen Felder |
| `src/services/alert_state.py` | MODIFY | P2: `reset()` (`:68-75`) löscht nur noch Schlüssel ohne `official_alert:`-Präfix statt der ganzen Datei |
| `src/services/compare_official_alert.py` | MODIFY | P4: `_detect()` (`:158-177`, Aufruf `:176`) übergibt Tagesfenster an `get_official_alerts_for_location()` |
| `internal/store/log.go`, `frontend/` | **unverändert** | reiner Python-Kern-Umbau, keine Schema-/API-Änderung |

## Estimated Scope

- **LoC:** ~250-400 Quellcode, ~400-600 Tests (v1.2: sieben zusätzliche Entwarnungs-ACs) — überschreitet das
  250-LoC-Workflow-Limit voraussichtlich; `workflow.py set-field loc_limit_override` braucht
  PO-Freigabe vor Implementierungsbeginn.
- **Files:** 6 geändert (0 neu, 0 gelöscht), 4-5 Testdateien neu
- **Effort:** high

## Dependencies

| Entity | Type | Purpose |
|---|---|---|
| `docs/specs/modules/feat_864_859_alert_presets.md` | Grundlage | Empfindlichkeitsstufen-Konzept (`metric_alert_levels`), auf dem P1b aufbaut |
| `docs/specs/modules/feat_1459_alert_protokoll.md` | Vorgänger-Scheibe | `alert_log.append_entry()`/`register_pairs_from_changes()` bleiben unverändert nutzbar; `register_pairs_from_corridor_hits()` wird durch P1a unerreichbar (s. Known Limitations) |
| `services.deviation_alert_engine.DeviationAlertEngine` | nutzt/erweitert | Wählt weiterhin den Detektor (`_select_detector()`); P1b ändert nur, was `WeatherChangeDetectionService.detect_changes()` intern für `thunder_level_max` tut |
| `TripAlertService._get_cached_weather` | nutzt (unverändert) | Liefert weiterhin die GESAMTE gecachte Restroute (`SegmentWeatherData` mit `segment.start_time`/`end_time`) als Quelle für P4 (Trip) — **kein** Wechsel auf `convert_trip_to_segments()`, das nur die heutige Etappe liefern würde |
| `output.renderers.day_window.resolve_configured_window` | nutzt | Tagesfenster-Auflösung für P4 (Ortsvergleich), ADR-0035-konform |
| `services.official_alerts.base.get_official_alerts_for_location` | nutzt | Nimmt `window_start`/`window_end`/`now` bereits entgegen (`base.py:179-241`) — P4 liefert sie nur nach |
| `output.renderers.alert.project.to_alert_message`/`to_corridor_events` | **wird unerreichbar** | Erhält ab dieser Scheibe nie mehr eine nicht-leere `corridor_hits`-Liste (s. Known Limitations) |
| Issue #1467 (Teil 2) | blockiert durch diese Scheibe | Zusammenführung der vier Ablaufsteuerungen braucht das hier festgelegte Zielverhalten als Grundlage |

## Ablösung von ADR-0040

ADR-0040 („Der nutzerkonfigurierte Schwellen-Alarm ist ein additiver zweiter Alarm-Typ") wird mit
dieser Scheibe **abgelöst**. Sein Kernanliegen — Stille bei anhaltender Gefahr (Belegfall KHW 403)
— bleibt gültig, wird aber nicht mehr über einen zweiten Alarm-Typ mit absoluter Grenze bedient,
sondern darüber, dass die Empfindlichkeitsstufe bei Gefahrenstufen-Größen (aktuell: Gewitter)
tatsächlich wirkt (P1b). Ein Nutzer, der heute Gewitter auf `sensibel` steht, hätte den KHW-403-Fall
korrekt gemeldet bekommen, sobald die Vorhersage von „kein Gewitter" auf „mittel" oder „hoch"
steigt — das genau ist P1b.

**ADR-0009** (Alerts sind Abweichungs-Wächter) und **ADR-0013** (`threshold` ist Δ-Sensitivität)
werden **bestätigt, nicht berührt**: Die Auswertung bleibt in beiden Paketen ein Vergleich gegen
den zuletzt versendeten Briefing-Snapshot (`alert_state`), nie gegen einen absoluten Systemwert.
Bei Gefahrenstufen-Größen ist die „Δ-Sensitivität" nicht mehr eine Zahl (Sprunggröße), sondern das
Niveau, das erreicht (Verschärfung) bzw. verlassen (Entwarnung) werden muss — eine Präzisierung der
bestehenden Entscheidung, keine neue. Dass beide Richtungen melden, ist ebenfalls keine Neuerung:
der Δ-Vergleich der stetigen Größen ist über `abs(delta)` seit jeher richtungsneutral.

Ein neues ADR (nächste freie Nummer: **ADR-0043**) wird im Rahmen der Implementierung dieser
Scheibe geschrieben; ADR-0040 erhält den Status „Abgelöst durch ADR-0043".

## Implementation Details

### P1a — Wertebereich (`corridors[].notify`) entfällt als Alarm-Auslöser

`_evaluate_corridors()` (`trip_alert.py:358-427`) samt Aufruf (`:248-249`, `corridor_to_report`),
dem Melde-Gedächtnis-Schreiben für den `corridor:`-Schlüsselraum (`:326-331`), den Konstanten
`_CORRIDOR_STATE_PREFIX`/`_ORDINAL_CORRIDOR_METRICS` (`:51-55`) und dem `has_corridors`-Anteil an
`has_active_rules` (`:188` in `check_and_send_alerts()`, `:485` in `check_all_trips()`) entfallen.
`corridor_hits` wird an den beiden verbleibenden Aufrufstellen (`_send_alert()` → `to_alert_message()`
über `NotificationService.send_deviation_alert()`) implizit immer eine leere Liste — der bestehende
Render-Vertrag (`output/renderers/alert/project.py`, `CorridorEvent`) bekommt dadurch nie wieder
Inhalt, ohne dass Renderer-Code angefasst werden muss (s. Known Limitations).

`Corridor.range`/`Corridor.mark` (Anzeige-Markierung, `models.py:886/888`) bleiben **vollständig
unverändert** — sie sind ein eigenes Feld, unabhängig von `notify`, und werden von keiner der
geänderten Funktionen gelesen. `Corridor.notify` bleibt im Datenmodell und in der Persistenz
bestehen (kein Feld-Entfernen), verliert nur seine Wirkung.

### P1b — Empfindlichkeitsstufe wirkt bei Gefahrenstufen-Größen über das Niveau, nicht die Sprunggröße

Betroffen ist aktuell ausschließlich `thunder_level_max` (`ThunderLevel` = NONE(0)/MED(1)/HIGH(2),
Ordinal über `thunder_ordinal()`, `output/metric_format.py:221-229`). `weather_change_detection.py:602`
vergleicht heute für ALLE Felder `abs(delta) > threshold`; das bleibt für stetige Größen
(Böen, Regen, Temperatur, Nullgradgrenze, …) **unverändert** — nur für als „ordinal" markierte
Felder tritt ein zweiter Vergleichszweig an die Stelle des Delta-Vergleichs.

**Zielsemantik (PO-go 2026-08-02, Entwarnungs-Richtung ergänzt PO-go 2026-08-03):**

| Empfindlichkeit | meldet die Verschärfung, wenn … | meldet die Entwarnung, wenn … |
|---|---|---|
| sensibel | die Gewitterneigung überhaupt steigt — auch auf die Mittelstufe (`neu > alt`) | sie überhaupt sinkt — auch von der Mittelstufe (`neu < alt`) |
| standard | sie die höchste Stufe erreicht (`neu > alt AND neu == HIGH`) | sie die höchste Stufe verlässt (`neu < alt AND alt == HIGH`) |
| entspannt | sie von „kein Gewitter" direkt auf die höchste Stufe springt (`alt == NONE AND neu == HIGH`) | sie von der höchsten Stufe direkt auf „kein Gewitter" zurückgeht (`alt == HIGH AND neu == NONE`) |

**Beide Richtungen melden, symmetrisch je Stufe.** Ein unveränderter Wert (`neu == alt`) meldet nie.
Begründung (PO-Entscheidung 2026-08-03): Bei den stetigen Größen (Böen, Regen, Temperatur) meldet
der Bestand über `abs(delta)` ohnehin **beide** Richtungen — die Symmetrie ist damit das bestehende
Verhalten des Änderungs-Wächters, und die ordinale Sonderbehandlung führt es fort, statt es für
Gefahrenstufen-Größen als Sonderfall zu brechen. Für den Wanderer ist „die Gefahr ist weg" eine
ebenso entscheidungsrelevante Nachricht wie „die Gefahr kommt": beide werfen die bisherige Planung
um, und genau das ist laut ADR-0009 das Auslöse-Kriterium. ADR-0009 selbst kennt **keine**
Richtungs-Einschränkung — es fordert lediglich den Vergleich gegen den Briefing-Snapshot statt gegen
eine absolute Schwelle; eine frühere Fassung dieser Spec hatte ihm die Aussage „Entwarnung ist kein
Ereignis" fälschlich zugeschrieben (s. Changelog v1.2).

Die Bedingungen lassen sich einheitlich als Ordinal-Schranken je Richtung ausdrücken, die aus der
gewählten Stufe abgeleitet werden — die konkrete
Kodierung (z. B. eine kleine Stufen-Tabelle in `weather_change_detection.py` oder ein Zusatzfeld
an der bestehenden `_PRESET_TABLE`-Zeile in `alert_preset.py`) ist eine Implementierungs-
entscheidung; maßgeblich sind die Tabellenwerte oben. `_PRESET_TABLE`s Zeile `THUNDER_LEVEL`
(`alert_preset.py:42`) trägt heute für alle drei Stufen denselben Delta-Wert `1` — das reicht
nicht aus, weil „Mittelstufe erreicht" (delta=1, `standard` soll NICHT feuern) und „Höchststufe
von der Mittelstufe erreicht" (delta=1, `standard` MUSS feuern) dieselbe Sprunggröße, aber
unterschiedliches Soll-Verhalten haben — ein Vergleich `>=` allein löst das nicht. Auf der
Entwarnungs-Seite gilt dasselbe spiegelbildlich: „Höchststufe verlassen" (delta=-1, `standard` MUSS
feuern) und „Mittelstufe verlassen" (delta=-1, `standard` soll NICHT feuern) sind über `abs(delta)`
ebenfalls nicht unterscheidbar. Maßgeblich ist deshalb in beiden Richtungen das erreichte bzw.
verlassene **Niveau**, nie die Sprunggröße.

Die Skala ist praktisch zweiwertig: `_parse_thunder_level()` (`providers/openmeteo.py:621-638`)
liefert nur `HIGH` (WMO-Code 95/96/99) oder `NONE` — die Mittelstufe hat noch keine Quelle
(„Fehler 2" aus #1418, Nachfolge #1419 S3). Die ACs unten müssen deshalb über eine **aufgezeichnete
Fixture** geprüft werden, die `ThunderLevel.MED` als Wert konstruiert (z. B. direkt am
`SegmentWeatherSummary`), nicht über einen Live-Provider-Abruf.

### P2 — Melde-Gedächtnis überlebt das Briefing (nur der Änderungs-Raum wird zurückgesetzt)

`AlertStateService.reset()` (`alert_state.py:68-75`) löscht heute die komplette Zustandsdatei.
Der Schlüsselraum der amtlichen Warnungen ist eindeutig am Präfix `official_alert:` erkennbar
(`official_alert_state_key()`, `output/renderers/alert/official_alerts.py:401-417`, Format
`official_alert:<ident>:<hazard>:<valid_from>:<valid_to>`). `reset()` wird auf ein
Löschen **aller Schlüssel außer denen mit diesem Präfix** umgestellt — der Änderungs-Raum
(`<feld>:<segment>`, unpräfigiert) verschwindet weiterhin vollständig, der amtliche Raum bleibt
über den Briefing-Versand hinaus erhalten. Mit P1a entfällt der `corridor:`-Raum ohnehin (keine
neuen Einträge mehr); etwaige Alt-Einträge mit diesem Präfix werden vom Reset mit gelöscht
(kein separater Sonderfall nötig, sie werden nirgends mehr gelesen).

`_reset_alert_state_after_briefing()` (`trip_report_scheduler.py:1036-1042`, Aufruf `:972`, nur im
regulären Briefing-Pfad, nicht bei Ad-hoc-Abruf laut Docstring „Issue #1007") ruft weiterhin
dieselbe `reset()`-Methode auf — die Änderung liegt vollständig in `alert_state.py`, kein
Aufrufer-Umbau nötig.

### P4 — Amtliche Warnungen bekommen Ort UND Zeit gemeinsam (Trip UND Ortsvergleich)

**Der eigentliche Fehler (B6) ist die Entkopplung von Ort und Zeit, nicht die Reichweite.** Heute
fragt `check_official_alert_triggers()` (`trip_alert.py:1100-1169`) alle Koordinaten der GESAMTEN
Restroute ab (dedupliziert über `coord_to_segments`, `:1130-1148`) und meldet jede irgendwann
gültige Warnung — unabhängig davon, ob der Nutzer zu ihrer Gültigkeitszeit an diesem Ort überhaupt
ist. Eine Warnung, die erst in drei Tagen beginnt, wird heute genauso gemeldet wie eine akute — auch
wenn der Nutzer in drei Tagen zwei Etappen weiter ist.

**Trip — Reparatur bleibt bei derselben Reichweite, ergänzt aber jedes Segment um sein eigenes
Zeitfenster:** Für **jedes** Segment der Restroute (nicht nur das aktive) ab jetzt gilt:

- Segment bereits vollständig vorbei (`segment.end_time < jetzt`) → keine Abfrage für dieses
  Segment (irrelevant, seine Warnzeit ist um).
- sonst: `window_start = max(jetzt, segment.start_time)`, `window_end = segment.end_time` — für
  das gerade aktive Segment also „jetzt bis Etappenende", für ein künftiges Segment dessen volle
  Spanne.

Amtliche Warnungen werden je Segment an dessen eigener Koordinate mit diesem eigenen Fenster
geprüft. Die vorhandene Coord→Segment-Zuordnung (`:1130-1138`) bleibt die Grundlage, der Dedup-
Schlüssel wird aber von **Koordinate** auf **(Koordinate, Fenster)** erweitert: Zwei Segmente mit
derselben Koordinate, aber unterschiedlichem Zeitfenster (z. B. ein Ort, der an zwei verschiedenen
Tagen der Route liegt), dürfen NICHT mehr zusammengefasst werden — sonst fällt eines der beiden
Segmente und seine Warnzeit still weg. Teilen sich zwei Segmente exakt dasselbe `(Koordinate,
Fenster)`-Paar, bleibt ein gemeinsamer Abruf unverändert korrekt (Normalfall: eine Koordinate pro
Segment, keine Mehrfachabfrage gegenüber heute).

**Bewusst ANDERS als der Nowcast-Pfad (`check_radar_alerts()`, `:814-829`):** Der Nowcast wählt
genau EIN aktives/nächstes Segment, weil er nur rund zwei Stunden vorausschaut — jenseits des
nächsten Segments wäre eine Nowcast-Aussage ohnehin wertlos. Amtliche Warnungen haben dagegen eine
Vorlaufzeit von Tagen; eine Beschränkung auf ein einzelnes Segment würde relevante Vorwarnungen für
spätere Etappen unterdrücken — genau der gefährlichste Fehler, den diese Scheibe beheben soll
(**dieser Fehler steckte in einer früheren Fassung dieser Spec und wurde im Team-Lead-Review
2026-08-02 korrigiert**, s. Changelog). Vom Nowcast-Muster wird deshalb **nur** die Formel
`window = [max(jetzt, start), end]` je Segment übernommen, **nicht** die Beschränkung auf ein
einzelnes Segment. Diese Begründung steht hier bewusst ausführlich, damit ein späterer
Adversary-Lauf die Reichweite nicht „zur Konsistenz mit dem Nowcast" zurück auf ein Segment
verengt.

**Ortsvergleich (`compare_official_alert.py:_detect`, `:158-177`, Aufruf `:176`):** Orte haben
keine Etappen — hier bleibt die Menge der geprüften Orte unverändert (alle Orte des Presets), nur
das Zeitfenster kommt hinzu: `window_start=jetzt`, `window_end=Ende des heutigen Tagesfensters`
(pro Ort in dessen Ortszeit; Tagesfenster über `resolve_configured_window(preset.day_window_start_hour,
preset.day_window_end_hour)`, ADR-0035-Standard 4-19 Uhr, wenn nicht gesetzt).

Beide Pfade bleiben **fail-soft**: Eine Warnung ohne `valid_from`/`valid_to` bleibt laut
`filter_alerts_to_window()` (`official_alerts/base.py:59-87`) immer erhalten — dieses Verhalten
wird nicht angefasst.

## Nicht-Ziele / bewusst unverändert

- **Zusammenführung der vier Ablaufsteuerungen** (Trip/Compare-Änderung/Compare-Nowcast/
  Compare-Amtlich) — Teil 2, Issue #1467.
- **Schwelle je Kanal** — Issue #1461.
- **Bedienoberfläche für die Alarm-Steuerung** (Korridor-Editor-UI, Empfindlichkeits-Auswahl) —
  Issue #1462. Diese Scheibe ändert keine Bedienfläche, nur Backend-Auswertung.
- **Datenbeschaffung/Provider-Schicht der Gewitter-Signale** — Issue #1419/#1457. `_parse_thunder_level()`
  wird nicht angefasst; P1b baut auf der heutigen (zweiwertigen) Skala auf.
- **Doppelte `corridor.metric`-Namensräume** (#1455) — nicht verschlimmert, nicht aufgelöst.
  `resolve_corridor_summary_field()` bleibt unverändert bestehen (nur ohne Aufrufer aus `trip_alert.py`).
- **`alert_metric_for()`** bleibt tabu (Rückwärts-Mehrdeutigkeit, Präzedenzfälle #1257/#1444 S2a).
- **Amtliche Eskalation ohne Zeit-Cooldown** (`compare_official_alert.py:10-19`, aus #1233/F002):
  bleibt unverändert — ein Cooldown würde eine echte GELB→ORANGE-Verschärfung unterdrücken.
- **Die vollständige Entfernung des Korridor-Render-Vertrags** (`output/renderers/alert/project.py`
  `to_corridor_events()`/`CorridorEvent`, `services/corridor_threshold.py`, `alert_log.
  register_pairs_from_corridor_hits()`) ist **nicht** Teil dieser Scheibe — s. Known Limitations.
- **Keine Verengung der Trip-Prüfreichweite auf ein einzelnes Segment** — bewusst NICHT wie der
  Nowcast-Pfad, s. Implementation Details P4.

## Regressionsgefahr

| Paket | Fehlerrichtung | Prüfung |
|---|---|---|
| P1a | **Weniger Alarme** — beabsichtigt (Wertebereich war ohnehin nie eine legitime Alarm-Quelle laut ADR-0009), aber ein Trip, der bisher ausschließlich über Korridore alarmiert wurde, alarmiert nach dieser Scheibe **gar nicht mehr**. AC-1 macht das explizit sichtbar statt es stillschweigend geschehen zu lassen. |
| P1b | **Mehr Alarme** bei Gewitter — in BEIDEN Richtungen (heute stumm bei genau einem Stufensprung, aufwärts wie abwärts). Harmlos, das ist der Zweck der Reparatur (B4). Die zusätzlichen Entwarnungs-Meldungen (PO-go 2026-08-03) sind gewollt und beim Nutzer nie mehr als eine je Stufenwechsel; das Tageslimit (`alert_daily_limit`) bleibt die Obergrenze. Kein Risiko für andere Metriken (AC-18 sichert die stetigen Größen ausdrücklich ab). |
| P2 | Falsch geschnitten → **Alarm-Stau** (ein amtlicher Zustand wird als „neu" erneut gemeldet, obwohl er es nicht ist) — harmlos im Vergleich zur heutigen Lage, aber sichtbar in AC-22. |
| P4 | **Alarm-Verlust** — die gefährlichste Richtung, und der Punkt, an dem eine frühere Fassung dieser Spec selbst zu eng geschnitten war (auf ein einzelnes Segment verengt, Team-Lead-Korrektur 2026-08-02). AC-25 ist das entscheidende Gegen-Beispiel: eine relevante Warnung für ein SPÄTERES Segment darf nicht verloren gehen. AC-24/AC-26 beweisen die Fenster-Grenzfälle am aktiven Segment, AC-27/AC-28 dass ein Ruhetag bzw. eine Etappen-Pause spätere Segmente NICHT ausschließt, AC-29 den vollständigen Touren-Abschluss, AC-31/AC-32 die Ortsvergleichs-Fenstergrenzen. |

## Prüfung mit zwei Nutzern

Jedes der vier Pakete wird mit zwei verschiedenen `user_id`s (`alice`, `bob`) durchlaufen: gleiche
Trip-/Preset-Konfiguration, unterschiedliche `data/users/<user_id>/`-Verzeichnisse. Geprüft wird,
dass Melde-Gedächtnis (P2), Alarm-Protokoll und Auslöse-Entscheidung (P1/P4) für einen Nutzer
niemals von den Daten des anderen beeinflusst werden oder in dessen Verzeichnis schreiben (AC-34).

## Abhängigkeit zu #1457/#1419 S3

#1457 (Gewitter-Signale je Gebiet aus der besten Quelle) ist offen und aktiv in Bearbeitung
(zuletzt 2026-08-02). Es ändert die **Datenbeschaffung** der Gewittersignale (welche Quelle
`ThunderLevel` liefert), nicht die hier festgelegte Niveau-Semantik. Sobald #1419 S3 der
Mittelstufe (`MED`) eine reale Quelle gibt, muss die dortige Einstufung exakt mit der Tabelle in
P1b übereinstimmen (WMO/Quellen-Schwelle für „mittel" muss sich als `ThunderLevel.MED` niederschlagen,
nicht als eigener vierter Wert) — sonst driften Datenbeschaffung und Alarm-Semantik auseinander.
Diese Abhängigkeit ist **keine Blockade** für diese Scheibe (die Fixture-basierten ACs beweisen
die Semantik unabhängig vom Live-Provider), aber ein Prüfpunkt für die Spec von #1419 S3.

## Acceptance Criteria

**P1a — Wertebereich entfällt als Alarm-Auslöser**

- **AC-1:** Given ein Trip, dessen EINZIGE konfigurierte Alarmquelle ein Wertebereich mit
  `notify: true` ist (kein `metric_alert_levels`, kein `alert_preset`, keine aktiven `alert_rules`),
  When die Vorhersage diese Grenze reißt und `check_and_send_alerts()` bzw. `check_all_trips()`
  läuft, Then wird KEIN Alarm ausgelöst — der Trip gilt als „keine aktive Alarmquelle" (Zustand vor
  Issue #1444 S1).
  - Test: Trip-Fixture mit ausschließlich `corridors=[Corridor(metric="wind_gust", range=[None, 20], notify=True)]`, Vorhersage mit Böen 25 km/h durch `check_and_send_alerts()` schleusen, `False`/kein Log-Eintrag erwarten.

- **AC-2:** Given derselbe Trip zusätzlich mit `metric_alert_levels={"wind_gust": "standard"}`,
  When sich die Böen um ≥20 km/h seit dem Briefing-Snapshot ändern, Then feuert der Alarm wie vor
  dieser Scheibe — die Empfindlichkeitsstufe ist unbeeinflusst vom (nun wirkungslosen) Korridor-Feld.
  - Test: identischer Trip + `metric_alert_levels`, Δ-Böen 25 km/h, Alarm wird ausgelöst (Regressionsschutz).

- **AC-3:** Given ein Bestandstrip mit gespeichertem `corridors[].notify: true`, When der Trip
  geladen und ohne Änderung an den Korridoren erneut gespeichert wird, Then bleibt das Feld
  `notify` byte-für-Feld unverändert in der JSON-Datei erhalten — kein Datenverlust trotz
  Wirkungslosigkeit (Read-Modify-Write, CLAUDE.md „Daten-Schema-Reworks").
  - Test: Trip mit `corridors=[...notify=True]` speichern, laden, unverändert erneut speichern, JSON-Diff auf das `corridors`-Array prüfen.

**P1b — Empfindlichkeitsstufe wirkt über das Niveau bei Gefahrenstufen-Größen**

- **AC-4:** Given Empfindlichkeit „sensibel" für Gewitter und ein Briefing-Snapshot mit
  `ThunderLevel.NONE`, When die aktuelle Vorhersage auf `ThunderLevel.MED` steigt, Then wird ein
  Alarm ausgelöst.
  - Test: Fixture mit `old=ThunderLevel.NONE`, `new=ThunderLevel.MED`, `metric_alert_levels={"thunder_level": "sensibel"}`, `detect_changes()` liefert eine `WeatherChange` für `thunder_level_max`.

- **AC-5:** Given Empfindlichkeit „sensibel", Snapshot `ThunderLevel.MED`, When die Vorhersage auf
  `ThunderLevel.HIGH` steigt, Then wird ein Alarm ausgelöst.
  - Test: analog AC-4 mit `old=MED`, `new=HIGH`.

- **AC-6:** Given Empfindlichkeit „standard", Snapshot `ThunderLevel.NONE`, When die Vorhersage auf
  `ThunderLevel.MED` steigt, Then wird KEIN Alarm ausgelöst (die Mittelstufe ist nicht die höchste
  Stufe).
  - Test: Fixture `old=NONE`, `new=MED`, `metric_alert_levels={"thunder_level": "standard"}`, `detect_changes()` liefert KEINE `WeatherChange` für dieses Feld.

- **AC-7:** Given Empfindlichkeit „standard", Snapshot `ThunderLevel.MED`, When die Vorhersage auf
  `ThunderLevel.HIGH` steigt, Then WIRD ein Alarm ausgelöst (die höchste Stufe wird erreicht).
  - Test: Fixture `old=MED`, `new=HIGH`, Stufe „standard".

- **AC-8:** Given Empfindlichkeit „standard", Snapshot `ThunderLevel.NONE`, When die Vorhersage
  direkt auf `ThunderLevel.HIGH` springt, Then WIRD ein Alarm ausgelöst.
  - Test: Fixture `old=NONE`, `new=HIGH`, Stufe „standard".

- **AC-9:** Given Empfindlichkeit „entspannt", Snapshot `ThunderLevel.MED`, When die Vorhersage auf
  `ThunderLevel.HIGH` steigt, Then wird KEIN Alarm ausgelöst (kein voller Sprung von „kein
  Gewitter").
  - Test: Fixture `old=MED`, `new=HIGH`, Stufe „entspannt", KEINE `WeatherChange`.

- **AC-10:** Given Empfindlichkeit „entspannt", Snapshot `ThunderLevel.NONE`, When die Vorhersage
  direkt auf `ThunderLevel.HIGH` springt, Then WIRD ein Alarm ausgelöst.
  - Test: Fixture `old=NONE`, `new=HIGH`, Stufe „entspannt".

- **AC-11:** Given Empfindlichkeit „sensibel", Snapshot `ThunderLevel.HIGH`, When die Vorhersage auf
  `ThunderLevel.MED` sinkt, Then WIRD ein Alarm ausgelöst — die Entwarnung wird symmetrisch zur
  Verschärfung gemeldet.
  - Test: Fixture `old=HIGH`, `new=MED`, Stufe „sensibel"; eine `WeatherChange` für `thunder_level_max` mit `direction="decrease"`.

- **AC-12:** Given Empfindlichkeit „sensibel", Snapshot `ThunderLevel.MED`, When die Vorhersage auf
  `ThunderLevel.NONE` sinkt, Then WIRD ein Alarm ausgelöst.
  - Test: Fixture `old=MED`, `new=NONE`, Stufe „sensibel".

- **AC-13:** Given Empfindlichkeit „standard", Snapshot `ThunderLevel.HIGH`, When die Vorhersage auf
  `ThunderLevel.MED` sinkt, Then WIRD ein Alarm ausgelöst — die höchste Stufe wird verlassen
  (Spiegelbild von AC-7).
  - Test: Fixture `old=HIGH`, `new=MED`, Stufe „standard".

- **AC-14:** Given Empfindlichkeit „standard", Snapshot `ThunderLevel.HIGH`, When die Vorhersage
  direkt auf `ThunderLevel.NONE` zurückgeht, Then WIRD ein Alarm ausgelöst.
  - Test: Fixture `old=HIGH`, `new=NONE`, Stufe „standard".

- **AC-15:** Given Empfindlichkeit „standard", Snapshot `ThunderLevel.MED`, When die Vorhersage auf
  `ThunderLevel.NONE` sinkt, Then wird KEIN Alarm ausgelöst — die höchste Stufe war nicht beteiligt
  (Spiegelbild von AC-6).
  - Test: Fixture `old=MED`, `new=NONE`, Stufe „standard", KEINE `WeatherChange`.

- **AC-16:** Given Empfindlichkeit „entspannt", Snapshot `ThunderLevel.HIGH`, When die Vorhersage
  direkt auf `ThunderLevel.NONE` zurückgeht, Then WIRD ein Alarm ausgelöst — der volle Rückgang
  (Spiegelbild von AC-10).
  - Test: Fixture `old=HIGH`, `new=NONE`, Stufe „entspannt".

- **AC-17:** Given Empfindlichkeit „entspannt", Snapshot `ThunderLevel.HIGH`, When die Vorhersage
  auf `ThunderLevel.MED` sinkt, Then wird KEIN Alarm ausgelöst — kein voller Rückgang auf „kein
  Gewitter" (Spiegelbild von AC-9).
  - Test: Fixture `old=HIGH`, `new=MED`, Stufe „entspannt", KEINE `WeatherChange`.

- **AC-18 (Regressionsschutz stetige Größen):** Given eine kontinuierliche Metrik (z. B. Böen,
  Schwelle 20 km/h bei „standard"), When sich der Wert seit dem Snapshot um exakt 20 km/h ändert,
  Then bleibt das heutige Verhalten unverändert: `abs(delta) > threshold` mit striktem `>` — bei
  genau 20 km/h wird KEIN Alarm ausgelöst (keine Auswirkung von P1b auf nicht-ordinale Felder).
  - Test: bestehende Δ-Fixture für `gust_max_kmh` mit Δ=20.0 unverändert grün; zusätzlich Δ=20.01 löst aus (Grenzfall-Nachweis, dass die generische Logik unangetastet blieb).

- **AC-19 (Fixture statt Live-Provider):** Given eine aufgezeichnete `SegmentWeatherSummary`-Fixture
  mit `thunder_level_max=ThunderLevel.MED` als Wert (nicht durch einen Live-`_parse_thunder_level()`-
  Aufruf erzeugt, da dieser MED nie liefert), When AC-4 bis AC-17 gegen diese Fixture laufen, Then
  verhalten sie sich exakt nach der Tabelle in „Implementation Details" — in BEIDEN Richtungen und
  unabhängig davon, ob ein Live-Provider die Mittelstufe je liefert.
  - Test: alle Fixtures, die die Mittelstufe brauchen (AC-4/AC-6/AC-7/AC-9 aufwärts, AC-11/AC-13/AC-15/AC-17 abwärts), konstruieren `ThunderLevel.MED` direkt als Testdaten, ohne Provider-Mock.

**P2 — Melde-Gedächtnis überlebt das Briefing**

- **AC-20:** Given ein Melde-Gedächtnis mit sowohl einem Änderungs-Eintrag (`gust_max_kmh:seg1`)
  als auch einem amtlichen Eintrag (`official_alert:region:X:thunderstorm:...`), When
  `AlertStateService.reset(trip_id)` aufgerufen wird, Then bleibt der amtliche Eintrag unverändert
  erhalten, der Änderungs-Eintrag wird gelöscht.
  - Test: `alert_state.json` mit beiden Schlüsseln vorab schreiben, `reset()` aufrufen, danach `load()` prüfen: amtlicher Schlüssel vorhanden mit unveränderten Werten, Änderungs-Schlüssel fehlt.

- **AC-21 (nutzersichtbar):** Given eine Tour mit einer bereits gemeldeten Wetter-Änderung, When
  danach das reguläre Briefing versendet wird und derselbe (unveränderte) Wert erneut geprüft
  wird, Then wird KEINE erneute Meldung ausgelöst — der Briefing-Snapshot selbst ist jetzt der
  Vergleichsanker, nicht der gelöschte Alt-Zustand. Die früher beobachtete zweimal-täglich-
  Wiederholung nach jedem Briefing entfällt.
  - Test: End-to-End über `TripReportSchedulerService` mit anschließendem `TripAlertService.check_and_send_alerts()`-Lauf gegen denselben Wert; kein zweiter Alarm.

- **AC-22 (die eigentliche B1-Reparatur):** Given eine amtliche Warnung wurde bereits gemeldet
  (State-Eintrag vorhanden), When danach das reguläre Briefing versendet und anschließend
  dieselbe (nicht eskalierte) Warnung erneut abgerufen wird, Then wird sie NICHT erneut gemeldet —
  die Entprellung bleibt über den Briefing-Reset hinweg wirksam.
  - Test: `official_alert_state_key()`-Eintrag vorab setzen, Briefing-Reset auslösen, `check_official_alert_triggers()` mit identischer Warnung erneut laufen lassen: leere Rückgabe (kein „neu oder eskaliert").

- **AC-23:** Given ein Ad-hoc-Abruf (kein reguläres Briefing), When der Ad-hoc-Versand läuft,
  Then wird `_reset_alert_state_after_briefing()` NICHT aufgerufen — unverändertes
  Bestandsverhalten (Issue #1007).
  - Test: bestehender Regressionstest für Ad-hoc-Pfad bleibt grün (kein neuer Test nötig, nur Nachweis der Unveränderheit).

**P4 — Amtliche Warnungen bekommen Ort UND Zeit gemeinsam (Trip)**

- **AC-24:** Given ein Trip mit einem Segment, auf dem der Nutzer HEUTE ist (endet in 2 Stunden),
  und eine amtliche Warnung an DESSEN Koordinaten mit `valid_from` in 3 Tagen, When
  `check_official_alert_triggers()` läuft, Then wird die Warnung für DIESES Segment NICHT gemeldet
  — ihr Gültigkeitsbeginn liegt nach dem Ende von dessen Zeitfenster (`window_end = segment.end_time`).
  - Test: Segment-Fixture mit `end_time = jetzt+2h`, `OfficialAlert(valid_from=jetzt+3 Tage)` an dessen Koordinate, `check_official_alert_triggers()` liefert für dieses Segment keinen Treffer.

- **AC-25 (wichtigstes AC dieses Pakets):** Given derselbe Trip hat ein SPÄTERES Segment (z. B.
  Etappe 5), auf dem der Nutzer in 3 Tagen sein wird, und dieselbe amtliche Warnung liegt an
  DESSEN Koordinaten (`valid_from` in 3 Tagen, innerhalb von dessen Zeitfenster), When der Check
  läuft, Then WIRD die Warnung gemeldet — zugeordnet zu diesem späteren Segment. Ohne dieses AC
  könnte eine zu enge Segmentwahl eine relevante Vorwarnung stillschweigend verlieren.
  - Test: zweites Segment-Fixture mit `start_time`/`end_time` um „jetzt+3 Tage", `OfficialAlert(valid_from=jetzt+3 Tage)` an dessen Koordinate, Treffer erscheint, getaggt mit der `segment_id` dieses späteren Segments.

- **AC-26:** Given eine Warnung beginnt STATTDESSEN innerhalb der nächsten 2 Stunden (noch
  innerhalb des Zeitfensters des heutigen aktiven Segments), When der Check läuft, Then WIRD sie
  für dieses Segment gemeldet.
  - Test: gleiche Fixture wie AC-24, aber `valid_from=jetzt+1h` → Treffer.

- **AC-27 (kein Segment heute schließt spätere nicht aus):** Given ein Ruhetag ohne Etappe für
  HEUTE, aber mit regulären KÜNFTIGEN Segmenten im Cache (z. B. morgen und übermorgen), When der
  Check läuft, Then wird für das fehlende heutige Segment nichts geprüft (keine Koordinate dafür
  vorhanden), aber die künftigen Segmente werden UNVERÄNDERT mit ihren eigenen Fenstern geprüft —
  ein Ruhetag schließt spätere Etappen nicht aus.
  - Test: gecachte Wetterdaten ohne Eintrag für heute, aber mit Einträgen für morgen/übermorgen; `OfficialAlert` an den Koordinaten von morgen, innerhalb von dessen Fenster → wird gemeldet.

- **AC-28 (Etappen-Pause schließt spätere Segmente nicht aus):** Given der aktuelle Zeitpunkt liegt
  zwischen dem Ende von Segment 1 und dem Start von Segment 2 desselben Tages (eine Pause), When
  der Check läuft, Then bleibt Segment 2 (und jedes spätere Segment) UNVERÄNDERT mit seinem eigenen
  Zeitfenster prüfbar — die Pause zwischen zwei Etappen schließt nachfolgende Segmente NICHT aus
  (anders als beim Nowcast-Pfad, der in dieser Lage komplett überspringt — die Abweichung ist
  gewollt, s. Implementation Details).
  - Test: Segment 1 endet vor `jetzt`, Segment 2 beginnt nach `jetzt`; Warnung an Segment-2-Koordinaten innerhalb von dessen Fenster → Treffer, trotz der Lücke.

- **AC-29 (letzter Tourtag):** Given der letzte Tourtag, das letzte Segment ist bereits beendet
  (`end_time < jetzt`) und kein weiteres Segment existiert, When der Check läuft, Then wird kein
  amtlicher Alarm mehr ausgewertet — Ergebnis leer.
  - Test: Trip mit `end_date`=gestern bzw. letztes Segment `end_time` in der Vergangenheit, `[]` erwartet.

- **AC-30 (fail-safe unverändert):** Given eine amtliche Warnung ohne `valid_from`/`valid_to`,
  When das neue Zeitfenster angewendet wird, Then bleibt sie trotzdem erhalten (unverändertes
  `filter_alerts_to_window()`-Verhalten, `official_alerts/base.py:59-87`).
  - Test: `OfficialAlert(valid_from=None, valid_to=None, ...)` durch den vollen Trip-Pfad schleusen, Warnung erscheint im Ergebnis trotz gesetztem Fenster.

**P4 — Amtliche Warnungen bekommen ein Zeitfenster (Ortsvergleich)**

- **AC-31:** Given ein Ortsvergleich-Preset mit Tagesfenster 4-19 Uhr Ortszeit, eine amtliche
  Warnung beginnt morgen um 3 Uhr Ortszeit, When `CompareOfficialAlertService._detect()` heute
  läuft, Then wird sie NICHT gemeldet — sie liegt außerhalb „jetzt bis Ende des heutigen
  Tagesfensters".
  - Test: Compare-Preset-Fixture mit Standard-Tagesfenster, `OfficialAlert(valid_from=morgen 03:00 Ortszeit, ...)`, `_detect()` liefert keinen Treffer für diesen Ort.

- **AC-32:** Given dieselbe Warnung beginnt STATTDESSEN noch HEUTE innerhalb des Tagesfensters
  (z. B. 14 Uhr Ortszeit), When der Check läuft, Then WIRD sie gemeldet.
  - Test: identische Fixture mit `valid_from=heute 14:00 Ortszeit`, Treffer erscheint.

- **AC-33 (Ortsvergleich prüft weiterhin alle Orte):** Given ein Preset mit drei Orten, von denen
  nur einer eine im Tagesfenster liegende Warnung hat, When der Check läuft, Then werden weiterhin
  ALLE drei Orte geprüft (keine Einschränkung auf einen „aktiven Ort" — anders als beim Trip gibt
  es kein Segment-Konzept), nur die eine im Fenster liegende Warnung wird gemeldet.
  - Test: drei-Orte-Preset, nur ein Ort mit gültiger Warnung im Fenster, Ergebnis enthält genau diesen einen Ort/diese eine Warnung.

**Mandantentrennung**

- **AC-34:** Given zwei Nutzer `alice` und `bob` mit strukturell identischen Trips/Presets
  (gleiche Korridore, gleiche Empfindlichkeitsstufen, gleiche amtlichen Warnungen an denselben
  Segment-Koordinaten), When P1/P2/P4 für beide Nutzer nacheinander laufen, Then landet jeder
  Melde-Gedächtnis- und Protokoll-Effekt ausschließlich in `data/users/alice/...` bzw.
  `data/users/bob/...` — niemals im Verzeichnis des jeweils anderen Nutzers.
  - Test: paralleler Lauf für beide `user_id`s, Kreuz-Kontamination der jeweiligen `alert_state/`- und `alert_log.json`-Dateien ausschließen.

## Known Limitations

- **Der Korridor-Render-Vertrag wird nicht entfernt, nur nie mehr gefüttert.** `output/renderers/
  alert/project.py` (`to_alert_message(corridor_hits=...)`, `to_corridor_events()`, `CorridorEvent`
  in `model.py`), `services/corridor_threshold.py` (`evaluate_corridor_thresholds()`,
  `resolve_corridor_summary_field()`, `CorridorHit`) und `alert_log.register_pairs_from_corridor_hits()`
  bleiben nach dieser Scheibe bestehen, werden aber nie wieder mit einer nicht-leeren Liste
  aufgerufen — `_send_alert()` übergibt ab jetzt strukturell immer `corridor_hits=[]`. Vollständiges
  Entfernen wäre eine cross-cutting Änderung über Renderer/Templates hinweg (E-Mail, Telegram, SMS)
  mit höherem Risiko als der eigentliche Auftrag dieser Scheibe rechtfertigt — Kandidat für einen
  Sammel-Eintrag in #1199, falls das PO das später aufräumen lassen will.
- **P1b deckt nur `thunder_level_max` ab** — die einzige heute alertfähige Gefahrenstufen-Größe.
  Eine künftige weitere ordinale Größe (z. B. eine feinere Gefahrenskala) müsste dieselbe
  Niveau-Tabelle explizit bekommen; es gibt keinen generischen Mechanismus „erkenne ordinale
  Felder automatisch".
  - **Warum keine Ratsche/kein Registry-Ansatz:** Mit exakt einer betroffenen Größe würde eine
    generische Erkennungs-Infrastruktur (z. B. eine Registry „welche Felder sind ordinal") reinen
    Vorgriff auf eine Anforderung bauen, die es noch nicht gibt — Over-Engineering für einen
    Einzelfall. Kommt eine zweite ordinale Größe hinzu, macht genau diese Wiederholung sichtbar,
    ob eine Verallgemeinerung lohnt; vorher lässt sie sich nicht sinnvoll entwerfen (Regel-Budget-
    Prinzip: keine Struktur ohne nachweisbaren zweiten Anwendungsfall).
- **Solange `_parse_thunder_level()` (#1419 S3 offen) nur NONE/HIGH liefert, ist der Unterschied
  zwischen `standard` und `entspannt` im Live-Betrieb wirkungslos** — beide verhalten sich
  identisch, bis die Mittelstufe eine reale Quelle bekommt. Die ACs beweisen die Semantik trotzdem
  über Fixtures, damit #1419 S3 nicht mit einem stillen Fehler live geht.
- **P4 (Trip) behält die volle Restroute als Prüfreichweite bei** (bewusst anders als der
  Nowcast-Pfad, s. Implementation Details) — dadurch bleibt die Anzahl der Fetch-Aufrufe
  gegenüber heute unverändert (weiterhin ein Aufruf je distinktem `(Koordinate, Fenster)`-Paar,
  im Regelfall eine Koordinate je Segment); es wächst nur die Präzision, nicht die Reichweite.
- **Kein Go-Test, keine Frontend-Änderung** — diese Scheibe ist reiner Python-Kern-Umbau; nichts
  hier berührt `internal/store/log.go`, Cockpit oder Frontend.

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** ADR-0040 wird durch diese Scheibe abgelöst (neues **ADR-0043**, im Rahmen der
  Implementierung geschrieben; Status von ADR-0040 wird auf „Abgelöst durch ADR-0043" gesetzt).
- **Rationale:** ADR-0009 (Abweichungs-Wächter) und ADR-0013 (`threshold` = Δ-Sensitivität) werden
  bestätigt und dienen als Grundlage — kein Widerspruch, keine Rücknahme. ADR-0040 wird abgelöst,
  weil sein additiver Grenzwert-Alarm eine absolute Schwelle war (Widerspruch zu ADR-0009); die
  hier eingeführte Niveau-Semantik der Empfindlichkeitsstufe bedient dasselbe Betriebsbedürfnis
  (Stille bei Dauergefahr, KHW-403-Fall) ohne diesen Widerspruch. Details und Herleitung stehen in
  `docs/context/rework-1460-alerts-relevanzfilter.md`, Abschnitt „🔴 KORREKTUR 2026-08-02".

## Changelog

- 2026-08-02: Initial spec created (Issue #1460 Teil 1, Epic #1458 Scheibe 2 von 5).
- 2026-08-02: **v1.1** — P4 (Trip) korrigiert (Team-Lead-Review): v1.0 hatte die Prüfreichweite
  fälschlich auf das aktive/nächste Segment verengt (Nowcast-Muster fehlerhaft als Vorlage für die
  Segment-*Auswahl* übernommen statt nur für die Fenster-Formel). Korrigiert auf „jedes Segment der
  Restroute bekommt sein eigenes Zeitfenster", Dedup-Schlüssel von Koordinate auf
  (Koordinate, Fenster) erweitert. AC-18 invertiert, AC-19 neu (wichtigstes AC des Pakets), AC-21/
  AC-22 auf „künftige Segmente bleiben prüfbar" umgestellt. AC-Zahl 27 → 28.
  *(Die AC-Nummern dieses Eintrags beziehen sich auf die Zählung von v1.1 — s. Umnummerierungs-
  Tabelle im v1.2-Eintrag unten.)*
- 2026-08-03: **v1.2** — **P1b: die Entwarnung wird gemeldet, symmetrisch zur Verschärfung**
  (PO-Entscheidung, wörtlich: „Ja, eine Entwarnung ist auch wichtig, also wenn sich der Forecast
  positiv entwickelt."). v1.0/v1.1 hatten festgelegt, dass ein Rückgang bei KEINER Stufe meldet, und
  das mit ADR-0009 begründet — **diese Berufung war falsch**: ADR-0009 fordert den Vergleich gegen
  den Briefing-Snapshot statt gegen eine absolute Schwelle und trifft zur Richtung der Abweichung
  gar keine Aussage. Sachlich stützt ADR-0009 die Symmetrie sogar, weil auch eine Entwarnung die
  Planungsgrundlage des Nutzers umwirft; zudem melden die stetigen Größen über `abs(delta)` schon
  heute beide Richtungen, sodass die Symmetrie das bestehende Verhalten fortführt statt es zu
  brechen. Geändert: Zielsemantik-Tabelle in „Implementation Details" (P1b) um die Entwarnungs-
  Spalte erweitert, der Satz „Entwarnung ist kein Ereignis (ADR-0009)" ersatzlos gestrichen,
  „Regressionsgefahr" (P1b-Zeile) auf „mehr Alarme in BEIDEN Richtungen" umgestellt. Das alte
  AC-11 (nebst dem in der RED-Phase ergänzten AC-11b) wird durch **sieben** ACs ersetzt, die die
  drei Stufen abwärts einzeln prüfen (AC-11 … AC-17); dadurch verschieben sich alle folgenden
  Nummern um +6. **AC-Zahl 28 → 34.**

  | v1.1 | v1.2 | | v1.1 | v1.2 |
  |---|---|---|---|---|
  | AC-1 … AC-10 | unverändert | | AC-19 | AC-25 |
  | AC-11 (+AC-11b) | ersetzt durch AC-11 … AC-17 | | AC-20 | AC-26 |
  | AC-12 | AC-18 | | AC-21 | AC-27 |
  | AC-13 | AC-19 | | AC-22 | AC-28 |
  | AC-14 | AC-20 | | AC-23 | AC-29 |
  | AC-15 | AC-21 | | AC-24 | AC-30 |
  | AC-16 | AC-22 | | AC-25 | AC-31 |
  | AC-17 | AC-23 | | AC-26 | AC-32 |
  | AC-18 | AC-24 | | AC-27 | AC-33 |
  | | | | AC-28 | AC-34 |
