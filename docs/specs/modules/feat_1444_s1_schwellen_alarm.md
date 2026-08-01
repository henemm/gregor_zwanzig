---
entity_id: feat_1444_s1_schwellen_alarm
type: module
created: 2026-08-01
updated: 2026-08-01
status: draft
version: "1.0"
tags: [alerts, trips, corridors, threshold]
---

# Schwellen-Alarm — Sofort-Meldung, sobald die Vorhersage eine konfigurierte Grenze reisst (Issue #1444, Scheibe 1)

## Approval

- [ ] Approved

## Purpose

Ein zweiter, nutzerkonfigurierter Alarm-Typ neben dem bestehenden
Aenderungs-Waechter: Reisst die Vorhersage im aktiven Etappenfenster eine vom
Nutzer gesetzte Grenze (`corridors[].notify == true`), geht eine Sofort-Meldung
raus — **auch wenn sich die Vorhersage seit Tagen nicht geaendert hat**. Schliesst
die Luecke, die den Trip „KHW 403" 6 Wochen lang ohne einen einzigen Gewitter-
oder Regen-Alarm liess.

## Source

- **File:** `src/services/corridor_threshold.py` (neu)
- **Identifier:** `evaluate_corridor_thresholds()`

Betroffene Schichten — **ausschliesslich Python-Core**:

| Datei | Aenderung | Zweck |
|---|---|---|
| `src/services/corridor_threshold.py` | CREATE | Reine Auswertung: Korridore + Wetterpunkte → Treffer |
| `src/services/trip_alert.py` | MODIFY | Auswertung in den Lauf einhaengen, Entprellung, Buendelung |
| `src/services/alert_state.py` | MODIFY | Melde-Gedaechtnis um den Schwellen-Schluesselraum erweitern |
| `src/output/renderers/alert/model.py`, `project.py` | MODIFY | Eigener Render-Vertrag fuer Schwellen-Treffer (ADR-0013-Pflicht) |
| `tests/tdd/test_corridor_threshold_alert.py` | CREATE | Verhaltensnachweis zu den ACs |
| `docs/adr/0040-schwellen-alarm-additiver-alarm-typ.md` | CREATE | Grundsatzentscheidung (s.u.) |

Kein Go, kein Frontend. Die Konfigurationsflaeche existiert vollstaendig und
wird nicht angefasst.

## Estimated Scope

- **LoC:** ~280 (+280 / −20)
- **Files:** 6 (2 neu, 4 geaendert) + ADR
- **Effort:** high

> Das Groessenlimit von 250 LoC je Arbeitsgang wird voraussichtlich knapp
> ueberschritten. Sobald das eintritt, wird einmal die Freigabe eingeholt —
> kein stiller Override.

## Dependencies

| Entity | Type | Purpose |
|---|---|---|
| `services/corridor_match.corridor_inside` | nutzt | Vergleich Wert ↔ Grenze; Grenzwert selbst zaehlt als eingehalten |
| `services/weather_change_detection._ALERT_METRIC_TO_SUMMARY_FIELD` | nutzt | Korridor-Metrik → Feld im Wetter-Aggregat |
| `output/metric_format.thunder_ordinal` | nutzt | kanonische Ordnung der Gewitterstufen |
| `app/metric_catalog.MetricDefinition.default_change_threshold` | nutzt | Mass fuer „Verschaerfung" bei stetigen Groessen |
| `services/alert_state.AlertStateService` | erweitert | Melde-Gedaechtnis je Trip |
| `services/trip_alert.TripAlertService` | erweitert | Lauf, Ruhezeiten, Cooldown, Tages-Obergrenze, Versand |
| `output/renderers/alert/*` | erweitert | Darstellung; loest **Renderer-Commit-Gate #811** aus |

## Implementation Details

### 1. Auswertung (rein, ohne Trip-Wissen)

```
fuer jede Etappe im aktiven Fenster:
  fuer jeden Korridor mit notify == true:
    feld  = _ALERT_METRIC_TO_SUMMARY_FIELD[korridor.metric]   # unbekannt -> ueberspringen
    wert  = getattr(aggregat, feld, None)                     # None      -> ueberspringen
    wert  = thunder_ordinal(wert) wenn Enum
    wenn corridor_inside(wert, min, max) is False:
        Treffer(metrik, wert, gerissene_grenze, richtung, etappe, zeitpunkt)
```

Das **aktive Etappenfenster** ist die bestehende Regel aus
`_fetch_fresh_weather()`: Etappen, die noch nicht vorbei sind
(`end_time >= jetzt`) und heute oder frueher beginnen
(`start_time.date() <= heute`). Keine neue Definition.

### 2. Entprellung (Melde-Gedaechtnis)

Eigener Schluesselraum `corridor:<metrik>:<etappe>` — der Delta-Zweig
(`<metrik>:<etappe>`) bleibt unberuehrt.

| Lage | Verhalten |
|---|---|
| Grenze neu gerissen | melden, Wert merken |
| gerissen, Wert ~gleich | schweigen |
| **verschaerft** | melden, Wert fortschreiben |
| Grenze wieder eingehalten | Eintrag raeumen (ein spaeterer Rueckfall meldet erneut) |

**„Verschaerft"** heisst:
- **ordinal** (Gewitter): naechsthoehere Stufe erreicht;
- **stetig** (Regen, Boeen, Temperatur): der Wert hat sich von der Grenze um
  mindestens `default_change_threshold` der Metrik weiter entfernt.

### 3. Einhaengen in den Lauf

- Eine Tour, deren **einzige** Alarmquelle Wertebereiche mit `notify` sind, muss
  geprueft werden. Heute faellt sie durch `has_active_rules`
  (`trip_alert.py:342-355`) und wird nie angefasst.
- Ruhezeiten, Zeit-Cooldown und Tages-Obergrenze gelten unveraendert auch fuer
  den Schwellen-Alarm.
- Schwellen-Treffer und Delta-Aenderungen desselben Laufs gehen in **eine**
  Nachricht (Muster #1088), nicht in zwei Zustellungen.

### 4. Darstellung

Eigener Ereignistyp mit eigenem Wortlaut: **„Gewitter: deine Grenze *keins* ist
gerissen — jetzt *maessig* (Etappe 3, 14–16 Uhr)"**. Kein erfundenes „vorher",
kein `old_value = 0.0` — ADR-0013 fordert das ausdruecklich vor jeder
Reaktivierung absoluter Regeln.

## Expected Behavior

- **Input:** Tour mit `corridors[].notify == true`, frische Vorhersage fuer die
  Etappen im aktiven Fenster, Melde-Gedaechtnis des letzten Laufs.
- **Output:** Null oder eine Sofort-Meldung ueber die fuer die Tour geltenden
  Alarm-Kanaele (`_effective_alert_channels`), mit Groesse, Ist-Wert, gerissener
  Grenze, Etappe und Zeitfenster.
- **Side effects:** Melde-Gedaechtnis fortgeschrieben; Zeit-Cooldown und
  Tageszaehler nur bei tatsaechlichem Versand erhoeht; Eintrag im Alarm-Protokoll.

## Acceptance Criteria

- **AC-1:** Given eine Tour mit der Gewitter-Grenze „hoechstens keins" und einer
  Vorhersage, die im aktiven Etappenfenster Gewitter zeigt, wobei sich die
  Vorhersage seit dem letzten Lauf **nicht** geaendert hat / When der Alarm-Lauf
  laeuft / Then geht genau eine Sofort-Meldung raus, die Groesse, Ist-Wert,
  Etappe und Zeitfenster benennt.
  - Test: Lauf mit identischem Vorher-/Nachher-Wetterstand; geprueft wird die
    erzeugte Nachricht, nicht ein Zwischenzustand.

- **AC-2:** Given dieselbe Tour und eine Vorhersage, die alle gesetzten Grenzen
  einhaelt / When der Alarm-Lauf laeuft / Then geht keine Schwellen-Meldung raus.
  - Test: Lauf mit Werten innerhalb aller Bereiche — kein Versand.

- **AC-3:** Given eine bereits gemeldete gerissene Grenze und eine im naechsten
  Lauf unveraenderte Lage / When der Alarm-Lauf erneut laeuft / Then geht keine
  zweite Meldung raus.
  - Test: zwei aufeinanderfolgende Laeufe mit gleichem Wert — genau ein Versand.

- **AC-4:** Given eine bereits gemeldete gerissene Grenze / When sich die Lage
  verschaerft (Gewitter eine Stufe hoeher bzw. ein stetiger Wert entfernt sich um
  mindestens die Aenderungs-Empfindlichkeit der Metrik weiter von der Grenze) /
  Then geht erneut eine Meldung raus; faellt der Wert zwischenzeitlich zurueck in
  den Bereich und reisst spaeter erneut, meldet der Waechter ebenfalls wieder.
  - Test: Lauf-Folge steigend → erneuter Versand; Folge gerissen → eingehalten →
    gerissen → zwei Versendungen.

- **AC-5:** Given eine Tour, deren einzige eingestellte Alarmquelle Wertebereiche
  mit Sofort-Meldung sind (keine Aenderungs-Empfindlichkeiten, keine Voreinstellung)
  / When der Alarm-Lauf laeuft / Then wird diese Tour geprueft und meldet bei
  gerissener Grenze — nachgewiesen fuer Gewitter (stufig) und Regen (stetig).
  - Test: Tour ohne `metric_alert_levels`/`alert_preset`, nur mit Korridoren;
    beide Groessen einzeln nachgewiesen.

- **AC-6:** Given ein Lauf, in dem sowohl eine Grenze gerissen ist als auch der
  Aenderungs-Waechter anschlaegt / When die Meldung erzeugt wird / Then geht
  **eine** Nachricht raus, in der der Schwellen-Treffer die gerissene Grenze und
  den Ist-Wert nennt und kein erfundenes „vorher" behauptet.
  - Test: gerenderte Nachricht auf beide Anteile pruefen; der Schwellen-Anteil
    enthaelt keinen Vorher-Wert und keine „von A auf B"-Formulierung.

## Known Limitations

- **Ohne Vorhersage-Schnappschuss kein Schwellen-Alarm.** Der Lauf ueberspringt
  eine Tour, solange kein Schnappschuss des Tages vorliegt
  (`trip_alert.py:377`), weil die frische Vorhersage heute an dessen Etappen
  haengt. Fuer Touren mit laufendem Briefing ist das erfuellt; die Entkopplung
  ist bewusst **nicht** Teil dieser Scheibe (Umbau von `_fetch_fresh_weather`).
- **Tages-Summen und Aufzaehlungs-Groessen** (z.B. vorherrschende
  Niederschlagsart) bleiben aussen vor: fuer sie ist ein Zahlenvergleich gegen
  einen Wertebereich nicht definiert (dieselbe strukturelle Ausnahme wie in
  `build_trip_corridor_id_map()`).
- **Nur Touren.** Der Ortsvergleich bekommt denselben Waechter spaeter; der
  Auswertungs-Baustein ist bereits ohne Trip-Wissen geschnitten (ADR-0021).
- Editor-Text (S2) und Ausweitung auf alle alarmfaehigen Groessen (S3) folgen in
  eigenen Arbeitsgaengen.

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** ADR-0040 (neu) — „Schwellen-Alarm als additiver zweiter Alarm-Typ"
- **Rationale:** **ADR-0009 verwirft absolute Schwellen ausdruecklich** („feuert
  bei bereits bekanntem Schlechtwetter → Alarm-Muedigkeit"); **ADR-0013** nennt
  den stillgelegten Absolut-Pfad als Known Limitation und macht zur Bedingung,
  dass er **vor einer Reaktivierung einen eigenen Render-Vertrag** bekommt.
  Diese Spec darf beides nicht still uebergehen.
  Der reale Befund aus 6 Wochen KHW 403 ist die Gegenerfahrung zur Annahme von
  ADR-0009: bei **konstant** hoher Gefahr ist der Abweichungs-Waechter
  strukturell stumm, und Stille bei bekannter Gefahr wiegt schwerer als Laerm.
  Beide Beobachtungen gelten — fuer verschiedene Wetterlagen.
  **Entscheidung daher: kein Rueckbau von ADR-0009, sondern ein additiver
  zweiter Typ** (Vorbild ADR-0016, amtliche Warnungen). Der Abweichungs-Waechter
  bleibt unveraendert das Standardverhalten; der Schwellen-Waechter feuert
  ausschliesslich dort, wo der Nutzer selbst eine Grenze gesetzt hat, und
  erfuellt die Auflage aus ADR-0013 durch einen eigenen Render-Vertrag.

## Changelog

- 2026-08-01: Initial spec created (Issue #1444, Scheibe 1)
