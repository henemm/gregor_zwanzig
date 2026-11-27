---
entity_id: feat_2994_alertable_metrics_vocab
type: refactor
created: 2026-11-27
updated: 2026-11-27
status: draft
version: "1.0"
tags: [alerts, cross-stack, codegen, drift-prevention, adr-0045]
workflow: feat-2994-alarm-vokabular
---

# Feat #2994 — Alarm-Metrik-Vokabular wird eine einzige Quelle

## Approval

- [ ] Approved

## Purpose

Das Vokabular der alarmfähigen Metriken (welche `AlertMetric`-Werte überhaupt
eine Alarmregel bekommen können) ist doppelt von Hand gepflegt: Python
`_ALERTABLE_METRIC_VALUES` und Go `AlertableMetrics`, dazu ein dritter
Handspiegel im Paritätstest. Python wird alleiniger Owner; ein Generator
schreibt das Vokabular als eingecheckte JSON-Datei, Go bettet sie per
`go:embed` ein und baut `AlertableMetrics` daraus (ADR-0045). Reine
Drift-Prävention (Paritäts-Bestandsaufnahme #1986, P16a/NEU-13); für Nutzer
ändert sich nichts. Erledigt die in `fix_1435_e5_alert_mapping_unify.md`
unter „Known Limitations" genannte Rest-Doppelung (dort bewusst nicht
angefasst, deshalb dort keine Änderung).

## Source

> **Schicht-Hinweis:** Python-Core (Quelle + Generator) und Go-API
> (Embed-Konsument, `internal/model`). Kein Frontend-Bedarf.

- **File:** `src/services/weather_change_detection.py`
- **Identifier:** `_ALERTABLE_METRIC_VALUES` (Owner), `catalog_id_to_alert_metrics()`
- **File:** `internal/model/trip.go`
- **Identifier:** `AlertableMetrics` (Aufrufer: `ActiveAlertableMetricIDs`, `SyncAlertRules`)
- **File:** `scripts/generate_alert_metric_mapping.py`
- **Identifier:** `write()`, `check()`

Querschnitt: Mandantentrennung nicht berührt (keine Nutzerdaten bewegt).
Kanäle: nicht berührt (kein Briefing-/Alarm-Inhalt ändert sich, das
Vokabular bleibt bei den 6 Metriken). Kein Trip/Compare-Pendant.

## Scope

- **LoC:** ~90-120 (ohne generierte JSON-Datei)
- **Files:** 6
- **Effort:** low-medium (Alarm-Pfad, daher fail-loud-Absicherung nötig)

### Affected Files

| File | Change Type | Description |
|------|-------------|-------------|
| `scripts/generate_alert_metric_mapping.py` | MODIFY | `write()`/`check()` um zweites Ziel `alertable_metrics.generated.json` erweitern |
| `internal/model/alertable_metrics.generated.json` | CREATE | generiert: sortierte Liste der 6 Werte |
| `internal/model/trip.go` | MODIFY | Handliteral durch `go:embed` + `mustParseAlertableMetrics` ersetzen |
| `src/services/weather_change_detection.py` | MODIFY | nur Kommentar: Python ist Owner, Go liest die generierte Datei |
| `tests/tdd/test_alert_metric_mapping_parity.py` | MODIFY | Handspiegel durch Import ersetzen, Ratchet auch für neue Datei |
| `internal/model/alertable_metrics_test.go` | CREATE | Go: Parse-Panics und Schwellen-Abdeckung |

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `docs/adr/0045-generiertes-eingebettetes-artefakt-fuer-cross-stack-abbildung.md` | ADR | Mechanismus (Python Owner, generiertes Artefakt, `go:embed`, Ratchet) |
| `docs/specs/modules/fix_1435_e5_alert_mapping_unify.md` | Spec | Vorbild, Known Limitation wird hiermit erledigt |
| `internal/model/trip.go::DefaultDeltaThreshold` | Go | muss jede alarmfähige Metrik abdecken |
| `internal/model/alert_metric_mapping.generated.json` | Artefakt | bleibt unverändert (Format, Frontend-Import) |
| `catalog_id_to_alert_metrics()` | Python | filtert auf das Vokabular, bleibt unverändert |

## Implementation Details

1. **Generator:** Neue Konstante `ALERTABLE_JSON_PATH`
   (`internal/model/alertable_metrics.generated.json`). Serialisierung:
   `json.dumps(sorted(_ALERTABLE_METRIC_VALUES), indent=2) + "\n"`.
   `write()` schreibt zusätzlich diese Datei; `check()` meldet für sie
   konkrete Abweichungen: Datei fehlt, kein gültiges JSON, fehlende bzw.
   zusätzliche Werte (jeweils mit Wertnamen und Pfad), im selben Meldungsstil
   wie die bestehende Mapping-Prüfung. Bestehendes Mapping-Format bleibt
   unverändert.
2. **Go:** `//go:embed alertable_metrics.generated.json` in
   `alertableMetricsJSON []byte`; `var AlertableMetrics =
   mustParseAlertableMetrics(alertableMetricsJSON)`. Typ bleibt
   `map[AlertMetric]struct{}`, Aufrufer unverändert. Die Parse-Funktion
   wird (wie `mustParseAlertMetricMapping`) als eigene, direkt testbare
   Funktion geschnitten und paniced mit Meldung, die
   `alertable_metrics.generated.json` nennt, bei: ungültigem JSON, leerer
   Liste (sonst würden alle Alarmregeln still entfernt) und einem Eintrag
   ohne `DefaultDeltaThreshold` (sonst stille Null-Schwelle). Go löst die
   Initialisierungsreihenfolge von `DefaultDeltaThreshold` selbst auf.
3. **Python:** `_ALERTABLE_METRIC_VALUES` bleibt unverändert; nur der
   Kommentar kehrt die Rolle um („Owner; Go liest die generierte Datei").
4. **Paritätstest:** Der Handspiegel entfällt, der Test importiert
   `_ALERTABLE_METRIC_VALUES` aus der Quelle; der Ratchet ruft das erweiterte
   `check()` auf.

## Expected Behavior

- **Input:** Entwickler ändert `_ALERTABLE_METRIC_VALUES` und führt den
  Generator aus.
- **Output:** `alertable_metrics.generated.json` wird aktualisiert, Go
  übernimmt den Stand beim nächsten Build. Vergessener Generatorlauf macht
  den Ratchet rot; eine neue Metrik ohne `DefaultDeltaThreshold` lässt Go
  beim Start bzw. im Go-Test scheitern.
- **Side effects:** Keine. Für Nutzer bleiben `SyncAlertRules` und
  `ActiveAlertableMetricIDs` bei den 6 Metriken ergebnisgleich.

## Test Plan

Echte Verhaltenstests, kein Mock/patch (Mock-Theater verboten). Fehlerfälle
im Generator werden mit echten Dateien in `tmp_path` bzw. über die
überschreibbaren Modul-Pfade (wie bei `_targets()`) erzeugt, nicht gemockt.

### Automated Tests (TDD RED)

- [ ] Python: GIVEN Generator-Lauf in `tmp_path` WHEN `write()` THEN Datei ist sortierte Liste der 6 Werte, `indent=2`, endet mit `\n`
- [ ] Python: GIVEN fehlende / ungültige / um einen Wert gekürzte / um einen Wert erweiterte Datei WHEN `check()` THEN konkrete Meldung mit Wertname bzw. Pfad
- [ ] Python: GIVEN eingecheckte Datei WHEN `check()` THEN keine Abweichung (Ratchet)
- [ ] Go: GIVEN eingebettetes Vokabular WHEN `AlertableMetrics` THEN genau die 6 Metriken, jede mit `DefaultDeltaThreshold`
- [ ] Go: GIVEN kaputtes JSON / `[]` / unbekannter Wert WHEN `mustParseAlertableMetrics` THEN Panic mit Dateiname
- [ ] Go: bestehende `alert_sync_test.go`, `alert_delta_817_test.go`, `alert_metric_mapping_panic_test.go` unverändert grün

## Acceptance Criteria

- **AC-1:** Given `_ALERTABLE_METRIC_VALUES` in Python enthält die 6 alarmfähigen Metriken / When der Generator `write()` ausführt / Then entsteht `internal/model/alertable_metrics.generated.json` als alphabetisch sortierte JSON-Liste dieser Werte mit `indent=2` und abschließendem Zeilenumbruch
  - Test: Generator gegen echte Quelle in ein Temp-Verzeichnis laufen lassen, Dateiinhalt byte-genau gegen die erwartete Serialisierung prüfen.

- **AC-2:** Given die generierte Vokabular-Datei fehlt, ist kein gültiges JSON, enthält einen Wert zu viel oder einen zu wenig / When `check()` läuft / Then meldet es je Fall eine konkrete Abweichung mit Pfad bzw. dem betroffenen Wertnamen, und bei übereinstimmender Datei eine leere Liste
  - Test: vier verfälschte Echtdateien plus der eingecheckte Stand; Meldung muss den Wertnamen enthalten (Mutations-Gegenprobe: Wert aus Python-Quelle entfernen macht den Ratchet rot).

- **AC-3:** Given `AlertableMetrics` wird aus der eingebetteten Datei gebaut (kein Handliteral mehr) / When `ActiveAlertableMetricIDs` und `SyncAlertRules` für Trips mit den 6 Metriken laufen / Then sind die Ergebnisse identisch zu vorher und der Typ `map[AlertMetric]struct{}` samt Aufrufern bleibt unverändert
  - Test: bestehende Go-Tests (`alert_sync_test.go`, `alert_delta_817_test.go`) unverändert grün; neuer Test prüft, dass `AlertableMetrics` genau die 6 Metriken enthält.

- **AC-4:** Given die Parse-Funktion erhält ungültiges JSON, eine leere Liste oder einen Eintrag ohne `DefaultDeltaThreshold` / When `mustParseAlertableMetrics` aufgerufen wird / Then löst sie einen Panic aus, dessen Meldung `alertable_metrics.generated.json` nennt, statt still eine leere oder unvollständige Menge zu liefern
  - Test: drei direkte Aufrufe mit kaputten Bytes, jeweils `recover()` und Meldungsprüfung.

- **AC-5:** Given der Paritätstest spiegelte das Vokabular bisher von Hand / When er nach der Änderung läuft / Then importiert er `_ALERTABLE_METRIC_VALUES` aus der Python-Quelle, enthält keine eigene Wertliste mehr, und das Nutzerverhalten (Katalog-ID-Zuordnung, Alarm-Sync) bleibt unverändert
  - Test: Paritätstest grün; Mutationsprobe — neuer Wert in der Quelle ohne Generatorlauf lässt den Ratchet rot werden.

## Definition of Done

- [ ] Spec freigegeben (`approved`), Tests zu AC-1 bis AC-5 rot vor Umsetzung, danach grün
- [ ] Generator erzeugt `alertable_metrics.generated.json`, `check()` meldet keine Abweichung
- [ ] Mutationsprobe: Wert aus der generierten Datei entfernt bzw. Handliteral zurück färbt Go- oder Python-Test rot
- [ ] PR mit allen 6 CI-Checks grün, Merge, Deploy, Prod-Selftest Exit 0

## Known Limitations

- Ein neuer Wert in `_ALERTABLE_METRIC_VALUES` braucht weiterhin einen Go-Eintrag in `DefaultDeltaThreshold` (Cross-Lang-Wertekontrakt); das Fehlen wird jetzt laut erkannt (Panic bzw. Go-Test), nicht automatisch erzeugt.
- Das Vokabular steht in einer eigenen Datei, nicht abgeleitet aus den Mapping-Werten: Ableitung würde das Sicherheitsnetz in `ActiveAlertableMetricIDs` tautologisch machen und eine alarmfähige Metrik ohne Katalog-ID verlieren.
- Löst die Known Limitation „Go-seitiges Alarm-Vokabular bleibt separates Duplikat" aus `fix_1435_e5_alert_mapping_unify.md`.

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** keine (Anwendung von ADR-0045)
- **Rationale:** Bestehender Mechanismus (Python Owner, generiertes eingebettetes Artefakt, Ratchet-Test) wird auf ein weiteres Vokabular angewendet; keine neue Entscheidungsfläche.

## Changelog

- 2026-11-27: Initial spec created (Issue #2994).
