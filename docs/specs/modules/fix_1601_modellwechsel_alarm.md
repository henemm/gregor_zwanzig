---
entity_id: fix_1601_modellwechsel_alarm
type: bugfix
created: 2026-08-09
updated: 2026-08-09
status: draft
version: "1.0"
tags: [cape, alarme, delta, modellwechsel, issue-1601]
---

# #1601 — Modellwechsel zwischen Δ-Anker und frischem Wert löst allein einen Alarm aus

## Approval

- [x] Approved — PO-go 2026-08-09 (alle 6 ACs unverändert freigegeben)

## Purpose

Der CAPE-Änderungsalarm vergleicht den gespeicherten Δ-Anker mit dem frisch abgerufenen Wert,
ohne zu prüfen, ob beide vom selben Wettermodell stammen. Wechselt zwischen zwei Läufen das
liefernde Modell (z.B. `meteofrance_arome` → `icon_d2`), springt die Zahl allein durch den
Modellwechsel — und kann einen Alarm auslösen, obwohl sich das Wetter nicht geändert hat.
Diese Scheibe fügt einen Herkunfts-Vergleich in den bestehenden CAPE-Sonderpfad ein: stimmen
Alt- und Neu-Herkunft nicht überein, entsteht kein Änderungs-Alarm.

## Source

- **File:** `src/services/weather_change_detection.py`
- **Identifier:** `WeatherChangeDetectionService.detect_changes()`, CAPE-Sonderpfad, direkt
  nach `threshold = effective_threshold` (aktuell Zeile 634)

Schicht: **Python-Core** (`src/services/`). Kein Go-, kein Frontend-Code betroffen.

## Dependencies

| Entity | Type | Purpose |
|---|---|---|
| `app.models.SegmentWeatherSummary.cape_model_id` | vorhanden (#1592 C0) | Herkunft am Δ-Anker (`old_summary`) und am frischen Wert (`new_summary`) |
| `app.model_registry.cape_delta_threshold_jkg()` | vorhanden (#1592 C3) | Bestehender Abstain-Nachschlag; läuft unverändert vor dem neuen Guard |
| `providers.thunder_routing.thunder_region_for()` | vorhanden | Gebietsbestimmung für die Schwellenumrechnung, unverändert |
| `services.deviation_alert_engine.DeviationAlertEngine.evaluate()` | vorhanden | Einziger live erreichbarer Aufrufer von `detect_changes()`; Prüfort für AC-5 |
| `services.compare_location_weather_source` → `services.segment_weather` → `services.weather_metrics` | vorhanden | Schreibt `cape_model_id` auch für Ortsvergleichs-Anker; Nachweis am laufenden System in AC-6 |

## Scope

### Affected Files
| File | Change Type | Description |
|---|---|---|
| `src/services/weather_change_detection.py` | MODIFY | Guard nach `threshold = effective_threshold` (:634): `old_summary.cape_model_id != new_summary.cape_model_id` ⇒ `continue` |
| `tests/tdd/test_cape_delta_modellschwelle.py` | MODIFY | Testfälle zur Modell-Identität + Erweiterung des bestehenden Helfers `_cape_pair` (:88-111), der aktuell nur EINEN gemeinsamen `cape_model_id`-Wert für Alt und Neu kennt und für getrennte Alt-/Neu-Herkunft erweitert werden muss |

### Estimated Changes
- Files: 2 (1 Produktiv, 1 Test)
- LoC: Produktivcode ~3-6 / Test ~50-90 (Summe ~55-95, Limit 250)

## Implementation Details

Der Guard sitzt **nach** dem bestehenden Schwellen-Abstain, nicht davor: `cape_delta_threshold_jkg()`
bricht bereits ab, wenn die Herkunft des **frischen** Werts unbelegt ist. Nach dieser Zeile ist
`new_summary.cape_model_id` garantiert belegt — der neue Vergleich prüft damit faktisch nur noch,
ob die Alt-Seite mit der (belegten) Neu-Seite übereinstimmt.

```
if metric == "cape_max_jkg":
    ... (bestehender Abstain-Block, unverändert bis :634)
    threshold = effective_threshold
    if old_summary.cape_model_id != new_summary.cape_model_id:
        continue
```

`None` zählt als Abweichung (Regel a, siehe Vorgänger-Kontextdokument
`docs/context/fix-1601-modellwechsel-alarm.md` Abschnitt „Entscheidung: `None` zählt als
Abweichung"): ein Δ-Anker ohne Herkunft (Altbestand vor #1592 C0, oder eine gemischte Etappe,
die nach der Aggregationsregel `agreement` keine einheitliche Herkunft trägt) ist mit einem
belegten frischen Wert nicht vergleichbar. Konsistent zum bestehenden Muster: „unbekannte
Herkunft" führt im Δ-Pfad an jeder Stelle zu Abstain, nicht zu einem Ersatzwert.

Der Sonderpfad wirkt für beide Alarmwege identisch, weil beide dieselbe
`DeviationAlertEngine.evaluate()` → `detect_changes()`-Kette durchlaufen (Trip über
`trip_alert.py:265`, Ortsvergleich über `compare_alert.py:371-374`).

## Test Plan

### Automated Tests (TDD RED)

- [ ] Test 1 (Modellwechsel unterdrückt): GIVEN ein CAPE-Δ-Paar mit `old_summary.cape_model_id
  = "meteofrance_arome"`, `new_summary.cape_model_id = "icon_d2"` und einem Sprung weit über
  die wirksame Schwelle WHEN `detect_changes()` läuft THEN entsteht kein `WeatherChange` für
  `cape_max_jkg`.
- [ ] Test 2 (Vergleichspunkt ohne Herkunft): GIVEN `old_summary.cape_model_id = None`
  (Zustand vor #1592 C0) und `new_summary.cape_model_id` belegt, großer Sprung WHEN
  `detect_changes()` läuft THEN entsteht kein `WeatherChange` für `cape_max_jkg`.
- [ ] Test 3 (Gegenprobe gleiches Modell): GIVEN Alt- und Neu-Herkunft identisch belegt
  (z.B. beide `icon_d2`), Sprung über der wirksamen Schwelle WHEN `detect_changes()` läuft
  THEN entsteht weiterhin ein `WeatherChange` für `cape_max_jkg` — der Guard unterdrückt nicht
  mehr als beabsichtigt.
- [ ] Test 4 (Normalfall): GIVEN Alt- und Neu-Herkunft identisch belegt, Sprung UNTER der
  wirksamen Schwelle WHEN `detect_changes()` läuft THEN entsteht kein `WeatherChange` —
  unverändert zu heute, kein Nebeneffekt des neuen Guards.
- [ ] Test 5 (Wirkort, Modellwechsel über die Engine): GIVEN dieselbe Modellwechsel-Situation
  wie Test 1, aber aufgerufen über `DeviationAlertEngine.evaluate()`
  (`src/services/deviation_alert_engine.py:264`, den einzigen live erreichbaren Aufrufer) WHEN
  die Auswertung läuft THEN ist `EvaluationResult.triggered is False` — ein Nachweis nur über
  den direkten Aufruf von `detect_changes()` genügt nicht, weil der Alarmpfad in Produktion
  ausschließlich über die Engine läuft.
- [ ] Test 6 (Wirkort, Gegenprobe über die Engine): GIVEN dieselbe Situation wie Test 3, aber
  aufgerufen über `DeviationAlertEngine.evaluate()` WHEN die Auswertung läuft THEN ist
  `EvaluationResult.triggered is True` mit einem `cape_max_jkg`-Change — bestätigt, dass der
  Guard den bestehenden, gewollten Alarmweg nicht mitunterdrückt.

## Acceptance Criteria

- **AC-1 (Modellwechsel unterdrückt):** Given ein CAPE-Δ-Vergleich, bei dem der Δ-Anker Modell
  `meteofrance_arome` trägt und der frisch abgerufene Wert Modell `icon_d2`, mit einem Sprung
  weit über die für das frische Modell wirksame Schwelle / When `detect_changes()` diesen
  Vergleich auswertet / Then entsteht kein Änderungs-Alarm für `cape_max_jkg`, obwohl der
  Sprung nominell alarmwürdig wäre.

- **AC-2 (Vergleichspunkt ohne Herkunft):** Given ein Δ-Anker mit `cape_model_id = None` (Stand
  vor #1592 C0 oder eine Etappe mit uneiniger Modellherkunft über ihre Segmente) und ein
  frischer Wert mit belegtem Modell, mit einem großen CAPE-Sprung / When `detect_changes()`
  diesen Vergleich auswertet / Then entsteht kein Änderungs-Alarm für `cape_max_jkg`, weil
  `None` als Abweichung zählt und Alt- und Neu-Seite nicht vergleichbar sind.

- **AC-3 (Gegenprobe gleiches Modell — die wichtigste):** Given ein Δ-Anker und ein frischer
  Wert mit identischem, belegtem Modell (z.B. beide `icon_d2`), mit einem Sprung über der für
  dieses Modell wirksamen Schwelle / When `detect_changes()` diesen Vergleich auswertet / Then
  entsteht weiterhin ein Änderungs-Alarm für `cape_max_jkg` — der Guard darf den bestehenden,
  gewollten Alarmweg nicht mitunterdrücken.

- **AC-4 (Normalfall):** Given ein Δ-Anker und ein frischer Wert mit identischem, belegtem
  Modell, mit einem Sprung unter der wirksamen Schwelle / When `detect_changes()` diesen
  Vergleich auswertet / Then entsteht kein Änderungs-Alarm für `cape_max_jkg` — unverändert
  zum heutigen Verhalten, kein Nebeneffekt des neuen Guards.

- **AC-5 (Wirkort statt Codeort):** Given dieselben zwei Situationen aus AC-1 (Modellwechsel)
  und AC-3 (gleiches Modell), aber aufgerufen über `DeviationAlertEngine.evaluate()`
  (`src/services/deviation_alert_engine.py:264`) statt direkt über `detect_changes()` / When
  die Auswertung läuft / Then bleibt `EvaluationResult.triggered` bei AC-1 `False` und bei AC-3
  `True` — `DeviationAlertEngine.evaluate()` ist der einzige live erreichbare Aufrufer von
  `detect_changes()` (Trip über `trip_alert.py:265`, Ortsvergleich über
  `compare_alert.py:371-374`); ein Nachweis nur über den direkten Aufruf von `detect_changes()`
  würde den toten, seit #1168 unerreichbaren Pfad in `trip_alert.py:604-632` genauso grün
  zeigen wie den echten, ohne dass der Guard dort wirkt.

- **AC-6 (Nachweis am laufenden System für den Ortsvergleich):** Given ein auf Staging frisch
  ausgelöster Ortsvergleichs-Report für einen Ort mit bekanntem CAPE-Modell / When der Report
  läuft und der dabei geschriebene Compare-Vergleichspunkt geöffnet wird / Then enthält dessen
  gespeicherter Datensatz das Feld `cape_model_id` mit einem nicht-leeren Wert — bislang ist
  diese Aussage nur aus dem Code hergeleitet, weil alle Compare-Anker in Produktion vom 31.07.
  stammen und das Feld nicht tragen (seither kein Compare-Versand, und #1584 Scheibe C verwirft
  Anker älter als 26 h ohnehin). Vorgehen: Compare-Report auf Staging für einen Testort
  auslösen, die geschriebene Snapshot-Datei öffnen, `cape_model_id` am Aggregat prüfen.

## Nicht in dieser Scheibe

- **Andere Metriken als CAPE.** Nur CAPE trägt eine Herkunftsangabe (`cape_model_id`); ein
  analoger Guard für Wind, Niederschlag o.ä. wäre ohne eigenes Fundament nicht baubar.
- **Der tote Pfad `src/services/trip_alert.py:604-632`.** Ein zweites, seit #1168
  unerreichbares `_detect_all_changes` — wird nicht angefasst, der Prüfort bleibt
  `DeviationAlertEngine`.
- **Das Dauerschweigen auf Etappen mit gemischter Modellherkunft.** Etappen an einer
  Modell-Gitter-Grenze liefern jeden Tag `cape_model_id = None` (Aggregationsregel
  `agreement`, `weather_metrics.py:837,1196-1203`) — dort greift schon heute der #1592-C3-
  Abstain auf der Neu-Seite, CAPE-Änderungsalarme feuern dort also bereits seit dieser Scheibe
  nie. Das ist Erbe von #1592 C3, nicht Folge des hier gebauten Guards, und wird hier nicht
  korrigiert.
- **Kein Reason-/Begründungs-Tracking pro Metrik.** `detect_changes()` kennt kein
  Reason-Tracking, `EvaluationResult.suppressed_reason` kennt nur drei feste Werte auf einer
  höheren Ebene — Begründungs-Infrastruktur für „unterdrückt wegen Modellwechsel" wird hier
  nicht gebaut.

## Risiko

Ein zugestellter Falschalarm durch Modellwechsel ist bislang **nicht belegt**: im
Alarm-Log aller drei Nutzer stehen in Produktion genau 2 CAPE-Änderungsalarme (05.08. und
06.08.), beide an Tagen ohne gemessenen Modellwechsel. Der Mechanismus, der zu einem
Falschalarm führen könnte, ist dagegen belegt: 10+ Modellwechsel binnen 60 Tagen in den
Produktivlogs, davon mehrere transient (Lauf N liefert Modell A, Lauf N+1 Modell B, Lauf N+2
wieder A) — jeder transiente Wechsel wirkt doppelt, da er einen Δ-Vergleich in beide
Richtungen verfälscht. Der Weg ist offen und wird begangen, ein Schaden ist noch nicht
nachgewiesen. Das rechtfertigt den Fix, nicht Eile — und die Gegenprobe (AC-3/AC-4) ist wegen
der Gefahr eines zu weit gefassten Guards (vgl. #1584, #1555: Alarme, die strukturell nie
bzw. nie zugestellt auslösen konnten) der wichtigste Testfall dieser Scheibe.

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** keine
- **Rationale:** Kein neues ADR nötig — die Scheibe ergänzt einen bestehenden Sonderpfad um
  einen zusätzlichen Abstain-Grund, ohne das Eichungs- oder Schwellenmodell aus ADR-0043/
  ADR-0048 zu ändern.

## Changelog

- 2026-08-09: Initial spec created. Bezug: Issue #1601, Vorgänger #1592 (C0/C3), Epic #1419.
