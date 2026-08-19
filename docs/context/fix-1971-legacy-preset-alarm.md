# Context: fix-1971-legacy-preset-alarm

Issue: [#1971](https://github.com/henemm/gregor_zwanzig/issues/1971) — „Alt-Ortsvergleiche ohne
migrierte `active_metrics` bekommen nie eine Alarm-Regel (stiller Alarm-Ausfall)"

## Request Summary

Das Issue behauptet: Ein Ortsvergleich, dessen `display_config` `None` ist (nie auf
`active_metrics` migriert), bekommt für neu eingeführte Metriken — konkret die
Beginn-Verschiebungs-Alarme aus #1468 — **nie** eine Alarm-Regel. Der Alarm bliebe still.
Herkunft: zurückgestelltes Adversary-Finding F004 aus #1468.

**Die Behauptung in dieser Form ist durch Messung widerlegt** (siehe „Messungen"). Es gibt
eine Lücke, aber unter einer deutlich engeren Bedingung als beschrieben, und sie ist in
Produktion aktuell unbesetzt.

## Messungen (Phase 1, belegt)

### M1 — Produktions-Ausmaß: 0 betroffene Presets

Das Issue nennt „erst zählen" als ersten Schritt. Gemessen wurde auf dem **echten**
Produktions-Datenverzeichnis `/var/lib/gregor` (aus `systemctl show gregor-api -p Environment`
→ `GZ_DATA_DIR=/var/lib/gregor`), **nicht** im Repo-`data/`.

| Ablage | Vergleichs-Presets | davon ohne `active_metrics` |
|---|---|---|
| `/var/lib/gregor/users/*/briefings/*.json` (aktuell, seit #1250 S7b) | 5 | **0** |
| `/var/lib/gregor/users/*/compare_presets.json` (Alt-Ablage) | 5 | **0** |

Alle fünf Presets (Nutzer `henning`) tragen `active_metrics` mit 4–11 Metriken.
Nutzer `default`, `steffi`, `validator-issue110` haben keine Vergleichs-Presets.

> **Zwei Messfallen, beide umgangen:** (1) Das Repo-`data/`-Verzeichnis ist **nicht** die
> Produktionsablage — dort hätte die Messung fälschlich „0 von 0" ergeben. (2) Presets liegen
> seit #1250 Scheibe 7b in `briefings/<id>.json`; nur `compare_presets.json` zu messen hätte
> die aktuelle Ablage verfehlt. Beide Ablagen wurden gemessen.

### M2 — Kernbehauptung widerlegt: der Legacy-Pfad erzeugt sehr wohl Onset-Regeln

Ausgeführt, nicht aus dem Code geschlossen:

```
expand_per_metric_levels(_STANDARD_METRIC_LEVELS, display_config=None)
  → 14 Regeln, darunter thunder_onset UND precipitation_heavy_onset
```

Grund: `compare_alert.py:530-533` setzt bei fehlendem `metric_alert_levels` den Fallback
`_STANDARD_METRIC_LEVELS`, und der leitet sich aus `_PRESET_TABLE` ab
(`compare_alert.py:51`). Beide Onset-Metriken **stehen** in `_PRESET_TABLE`
(`alert_preset.py:74-75`, dort per #1468 eingetragen). Der im Issue genannte Backfill-Pfad
wird also gar nicht gebraucht — die Regeln entstehen über den Level-Fallback.

**Positivkontrolle:** `expand_per_metric_levels({}, display_config=None)` → **0 Regeln**.
Die Messung kann „keine Regel" darstellen; das Ergebnis ist nicht trivial wahr.

### M3 — Die tatsächliche Lücke

Sie öffnet sich nur, wenn **beide** Bedingungen zusammentreffen:

1. `display_config.metric_alert_levels` ist **gesetzt** → der `_STANDARD_METRIC_LEVELS`-Fallback
   greift nicht, es zählen nur die dort gelisteten Metriken; **und**
2. `display_config.active_metrics` **fehlt** → `_display_config_from_active_metrics()` liefert
   `None` (`compare_alert.py:568-570`) → der Backfill in `alert_preset.py:346` läuft nicht.

Gemessen:

```
expand_per_metric_levels({wind_gust, precipitation_sum, thunder_level}, display_config=None)
  → 3 Regeln, thunder_onset NICHT dabei
```

Genau diese Konstellation hat in Produktion **kein** Preset: das einzige Preset mit gesetztem
`metric_alert_levels` („Le Var", `cp-eb6ba0b239d90e37`) hat auch `active_metrics` (11 Metriken)
— sein `metric_alert_levels` listet 7 Metriken **ohne** Onset, doch weil `display_config` nicht
`None` ist, füllt der Backfill die Onset-Regeln nach.

### M4 — Register-Differenz (strukturelles Restrisiko)

| Register | Größe |
|---|---|
| `_ALERT_METRIC_TO_CATALOG_ID` (speist den Backfill) | 15 |
| `_PRESET_TABLE` (speist `_STANDARD_METRIC_LEVELS`) | 14 |
| Nur im Backfill-Register | `snow_line` |
| Nur in der Preset-Tabelle | — (leer) |

`snow_line` ist per #959 bewusst nach `freezing_level` konsolidiert (Alt-Levels migriert in
`loader._migrate_metric_alert_levels`), also keine echte Lücke. **Aber:** Die beiden Register
sind getrennt gepflegt. Eine künftige Metrik, die nur in `_ALERT_METRIC_TO_CATALOG_ID`
landet, wäre im Legacy-Pfad still — das ist die eigentliche, dauerhafte Fehlerquelle hinter
diesem Issue.

### M5 — Der Legacy-Zustand ist **nicht** historisch, er kann neu entstehen

Das Issue behandelt fehlendes `active_metrics` als Altlast („Alt-Ortsvergleiche", „vor der
Migration"). Das trifft nicht zu:

- `frontend/src/lib/.../compareEditorSave.ts:407-409` lässt den Schlüssel `active_metrics`
  **weg**, solange `fields.activeMetricKeys === null` — und `null` ist der Init-Wert
  (`compareWizardState.svelte.ts:32`).
- `internal/handler/compare_preset.go:193-277` (`CreateComparePresetHandler`) setzt zwar
  Defaults für `weekday`, `forecast_hours`, `morning_time`, `official_warnings` — aber
  **keinen** für `active_metrics`.
- Weder `internal/store/compare_preset.go:89-132` (`normalizeLoadedComparePreset`) noch
  `src/app/loader.py:262` heilen das Feld beim Laden.

Ein heute angelegter Ortsvergleich, bei dem der Nutzer die Metrik-Auswahl nie anfasst, wird
also **ohne** `active_metrics` persistiert. Trifft das mit einem gesetzten
`metric_alert_levels` zusammen (Nutzer stellt im Alarme-Reiter Empfindlichkeiten ein, ohne
den Metriken-Reiter zu berühren), steht genau die Konstellation aus M3 — und neue Metriken
bleiben still.

Für den **Render**-Pfad ist das abgefedert: `resolve_enabled_metrics(None)` bedeutet „alle
Metriken sichtbar" (`compare_metric_ids.py:168-169`). Nur der **Alarm**-Pfad hat diesen
Auffang nicht.

> Damit verschiebt sich die Bewertung: Weg 3 des Issues („dokumentieren, wenn die
> Produktionszahl 0 ist") stützt sich auf einen Bestand, der jederzeit wieder wachsen kann.
> Die Zahl 0 ist eine Momentaufnahme, keine Eigenschaft des Systems.

## Related Files

| Datei | Relevanz |
|---|---|
| `src/services/alert_preset.py:178-181` | Signatur `expand_per_metric_levels(levels, display_config=None)` |
| `src/services/alert_preset.py:315-321` | #961-Deaktivieren-Filter — bei `display_config=None` übersprungen |
| `src/services/alert_preset.py:346-385` | Backfill-Pfad — komplett hinter `if display_config is not None` |
| `src/services/alert_preset.py:53-77` | `_PRESET_TABLE` inkl. beider Onset-Zeilen (#1468) |
| `src/services/compare_alert.py:51` | `_STANDARD_METRIC_LEVELS` = alle `_PRESET_TABLE`-Metriken auf `standard` |
| `src/services/compare_alert.py:530-533` | Level-Fallback — der Grund, warum M2 Regeln liefert |
| `src/services/compare_alert.py:544-570` | `_display_config_from_active_metrics()` — `None` bei fehlendem `active_metrics` |
| `src/services/deviation_alert_engine.py:174-200` | `_select_detector()` — einzige Detektor-Wahl für Trip UND Vergleich (seit #1168) |
| `src/services/weather_change_detection.py:96-118` | `_ALERT_METRIC_TO_CATALOG_ID` (Backfill-Register) |
| `src/services/weather_change_detection.py:200-259` | `is_alert_metric_active()` — leere `metrics[]` = konservativ aktiv; `None` → `False` |
| `scripts/migrate_1191_compare_active_metrics.py` | Bestehende Migration: füllt fehlendes `active_metrics` auf vollen Satz |
| `scripts/migrate_1373_compare_active_metrics_format.py` | Format-Migration String → `{metric_id, aggregation}` |

## Existing Patterns

- **Eine Detektor-Wahl für beide Flächen:** Seit #1168 delegiert `TripAlertService._select_change_detector()`
  (`trip_alert.py:438-453`) an `DeviationAlertEngine._select_detector()`. Trip und Ortsvergleich
  laufen durch **denselben** Code — passend zur PO-Vorgabe „möglichst viel Code teilen".
- **`display_config=None` ist bewusst konservativ:** `compare_alert.py:548-559` (Bug #1191,
  Adversary F001) hält ausdrücklich fest, dass ein fehlendes `active_metrics` als Legacy gilt
  und dann *alles* feuern soll — statt still zu verstummen. Ein Fix muss diese Absicht
  fortschreiben, nicht umkehren.
- **Leere `metrics[]` = konservativ aktiv** (`weather_change_detection.py:224-227`, Finding F002):
  dasselbe Prinzip an der Trip-Seite.
- **Migration statt Dauer-Fallback:** Für `active_metrics` existieren bereits zwei
  Einmal-Migrationsskripte mit Dry-Run-Default (`--execute` nötig).

## Dependencies

- **Upstream:** `_PRESET_TABLE` / `_STANDARD_METRIC_LEVELS`, `_ALERT_METRIC_TO_CATALOG_ID`,
  `is_alert_metric_active`, Preset-Persistenz (Go `internal/handler/compare_preset.go`,
  `internal/store/compare_preset.go` — Read-Modify-Write-Merge auf `DisplayConfig`)
- **Downstream:** `WeatherChangeDetectionService.from_alert_rules()` → Änderungs-Alarme in
  **beiden** Flächen (Trip + Ortsvergleich) und **allen vier** Kanälen

## Existing Specs

- `docs/specs/modules/issue_1191_compare_alert_deactivated_metric.md` (AC-4: die Migration)
- `docs/specs/modules/feat_1373_s2b_metrik_speicherformat.md` (AC-6/AC-7: Formatwechsel)
- `docs/features/rework_1467_s2_aenderungsalarm.md` — Leitsatz „Der gefährlichste Fehler ist
  der ausbleibende Alarm."

## Testabdeckung (Ist-Stand)

- `tests/tdd/test_onset_alert_armed_from_weather_tab.py` — bewacht die Onset-Scharfschaltung,
  aber **ausschließlich mit gesetztem `display_config`** (Zeilen 128, 159, 192). Kein
  `None`-Pendant.
- `tests/tdd/test_compare_alert_metric_gating.py` — #1191-Gating (Deaktivieren-Lücke).
- `tests/tdd/test_issue_946_alert_architecture.py`, `test_issue_1168_alert_engine_extract.py` —
  #961-Backfill.
- **Kein einziger Test** schickt ein Vergleichs-Preset **ohne** `active_metrics` durch die volle
  Alarm-Kette. Das ist die im Issue benannte Testlücke — sie besteht, unabhängig davon, dass die
  Kernbehauptung so nicht zutrifft.

## Risks & Considerations

- **R1 — Das Issue beschreibt den Mechanismus falsch.** Ein Fix, der stur „den Backfill auch für
  `display_config=None` öffnen" umsetzt (Weg 1 im Issue), behebt für die Onset-Metriken nichts,
  was nicht schon funktioniert, und ändert für `snow_line` das Verhalten. Vor der Spec muss der
  Ziel-Zustand am tatsächlichen Mechanismus (M3) ausgerichtet werden.
- **R2 — Produktionszahl ist 0.** Nach der Logik des Issues („ist die Zahl 0, reicht eine
  dokumentierte Notiz") ist Weg 3 der belegte Kandidat. Das ist eine PO-Entscheidung, keine
  technische.
- **R3 — Alarm-Flut statt Stille.** Öffnet man den Backfill für `display_config=None`, erben
  Alt-Presets die volle Grundauswahl. Das ist die konservative Richtung (Leitsatz #1467), kann
  aber bei einem Preset mit bewusst reduziertem `metric_alert_levels` als ungewollte
  Zusatz-Alarmierung ankommen.
- **R4 — Zwei getrennte Register (M4) sind die eigentliche Fehlerquelle.** Ein Fix, der nur den
  heutigen Symptomfall abdeckt, lässt sie bestehen; ein Wächter-Test auf Register-Deckung würde
  die Klasse schließen statt des Einzelfalls.
- **R5 — Datenbestand.** Jede Migrations-Variante fällt unter die Read-Modify-Write-Pflicht
  (BUG-DATALOSS-GR221 / #102); die bestehenden Skripte haben Dry-Run-Default und lassen ein
  bewusst leeres `active_metrics: []` unangetastet.
