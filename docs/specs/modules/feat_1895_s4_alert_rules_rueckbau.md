---
entity_id: feat_1895_s4_alert_rules_rueckbau
type: module
created: 2026-11-05
updated: 2026-11-05
status: draft
version: "1.0"
workflow: feat-1895-s4-alert-rules-rueckbau
tags: [alarm-regeln, rueckbau, toter-code, frontend, python, adr-0077, adr-0043]
---

# #1895 Schritt 4 — Toten Code rund um `alert_rules` entfernen (Schnitt C)

## Approval

- [ ] Approved

## Purpose

Nach den Scheiben S1 bis S3b liegt die Kanalzuordnung je Wettergröße in `alert_metric_channels`,
und der alte Regel-Editor (Modus „Absolut/Delta/Beides") ist nirgends mehr eingebunden. Übrig
sind Svelte-Komponenten, Umrechner-Funktionen und eine Python-Hilfe (`expand_preset`), die
niemand mehr aufruft, aber Konfigurationsflächen ohne Wirkung vortäuschen (ADR-0043). Diese
Scheibe löscht genau diesen toten Code samt seiner Tests und ändert kein Nutzerverhalten.
Damit sind die Fragen von #1895 beantwortet: Absolut-Modus weg, Kanalzuordnung umgezogen,
Bestandsdaten unangetastet.

## Abgrenzung: Was hier NICHT passiert (bitte zuerst lesen)

Das Issue heißt „Rückbau `alert_rules`". **Geliefert wird nur das Entfernen der toten UI und
der toten Leser-Hilfen** (Schnitt C, in der Analyse entschieden, nicht neu verhandelt).
**Unverändert bleiben** und gehen an **#2793** (Epic #2791 S2, ADR-0106, löst `alert_rules` und
`metric_alert_levels` ohnehin als Auslöser ab):

- Prüf-Gate `has_active_rules` (`src/services/trip_alert.py:696-700` und `:1199-1203`)
- Kanal-Union der Regel-Kanäle (`src/services/alert_channels.py:120-127`)
- `shared/AlarmeTab.svelte` → `AlertPreviewCard.svelte` (Vorschau liest `trip.alert_rules`)
- Badge in `TripTabs.svelte:62` und `hubUebersichtModell.ts:136`
- `api/routers/validator.py` (Diagnose „from_alert_rules")
- Go-Modell mit Store, Handler und `SyncAlertRules` (`internal/model/trip.go`,
  `internal/store/trip.go`, `internal/handler/trip.go`, `internal/handler/weather_config.go`)
- Loader (`src/app/loader.py`) und Persistenz des Feldes

**Warum nicht mitgenommen:** (1) Das Gate umzustellen ist nicht verhaltensneutral. Die Gate-
Fälle 1 bis 4 stehen in der Analyse (`docs/context/feat-1895-s4-alert-rules-rueckbau.md`):
deaktivierte Regel bleibt in Go erhalten, nie synchronisierte Regelliste, abweichende
Metrik-Menge (`_ALERT_METRIC_TO_CATALOG_ID` gegen Go `AlertableMetrics`) und unterschiedliche
Behandlung fehlender `report_config` im send-Pfad gegen `check_all_trips`. Der Kandidat
`_has_active_alert_metric` ist **nicht äquivalent**. (2) #2793 definiert die Leser fachlich neu;
sie jetzt vorzuziehen wäre Doppelarbeit. (3) Weil die Persistenz unverändert bleibt, gibt es
kein Datenverlust-Risiko (#102, Read-Modify-Write bleibt gewahrt).

## Source

- **File:** `frontend/src/lib/components/alerts-tab/` (Löschung), `src/services/alert_preset.py`
- **Identifier:** Komponenten `AlertsTab`, `AlertCard`, `AlertMetricTable`, `AlertMetricRow`,
  `AlertPresetSelector`, `AlertsPreviewCard`; Funktion `expand_preset`

> Schicht: **Frontend / User-UI** (`frontend/src/lib/...`) und **Python-Core**
> (`src/services/`, `tests/tdd/`). Kein Go, kein Schema, keine Migration.

> **Trip/Ortsvergleich:** Der geteilte `shared/AlarmeTab.svelte` bleibt unverändert und trägt
> weiter alle vier Flächen (Trip-Hub, `/trips/new`, Ortsvergleich-Editor, `/compare/new`).
> Es entsteht keine neue Compare-Datei; gelöscht wird nur Trip-seitig toter Code.
> **Mandantentrennung:** Es bewegen sich keine Nutzerdaten. **Kanäle:** Mail-Inhalt und Kanäle
> aller vier (E-Mail · Telegram · SMS · Premium-SMS) bleiben unverändert.

## Estimated Scope

- **LoC:** +~50 / −~2000 (das LoC-Gate zählt nur hinzugefügte Zeilen)
- **Files:** ca. 15 bis 25, überwiegend Löschungen
- **Effort:** low (Risiko LOW; einzige Gefahr sind übersehene Importe, abgefangen durch
  svelte-check, Build, Frontend-Suite und die Import-Wächter-Tests)

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| ADR-0077 | adr | Rückbau als S4 vorgesehen; bekommt Nachtrag „S4" |
| ADR-0043 | adr | keine Konfigurationsfläche ohne Wirkung |
| ADR-0106 / #2793 | adr / issue | übernimmt Leser, Gate, Kanal-Union und Persistenz |
| `docs/specs/modules/alert_metric_channels.md` | spec | S1–S3b; bekommt S4-Abschnitt (Stelle `:1256-1258`) |
| `expand_per_metric_levels` | python | produktiver Ersatz für die Zusicherungen aus test_846/889 |
| `shared/AlarmeTab.svelte` | svelte | produktiver Konsument von `AlertMetricLevelTable` u. a. |

## Implementation Details

### 1. Frontend löschen (unter `frontend/src/lib/components/`)

Gemessener Befund am 2026-11-05 auf `20b38d383`, Tests nicht mitgezählt.

**TOT, wird gelöscht:**
`alerts-tab/AlertsTab.svelte` (kein Importeur), `alerts-tab/AlertCard.svelte` (keiner),
`alerts-tab/AlertMetricTable.svelte` (keiner), `alerts-tab/AlertMetricRow.svelte` (nur von
AlertMetricTable), `alerts-tab/AlertPresetSelector.svelte` (keiner),
`trip-detail/AlertsPreviewCard.svelte` (nur der ungenutzte Re-Export in
`trip-detail/index.ts:7`; Export-Zeile entfernen).

**PRODUKTIV, bleibt unverändert:** `alerts-tab/AlertMetricLevelTable.svelte` und
`AlertMetricLevelRow.svelte` (über `shared/AlarmeTab.svelte`; die Kontextdatei nennt
AlertMetricLevelRow fälschlich als tot), `AlertCooldownCard`, `AlertQuietHoursCard`,
`AlertMetricChannelsBlock`, `AlertPreviewCard.svelte`, `alertPreviewHelpers.ts`.

### 2. `alerts-tab/alertMetricTable.ts` verschlanken (ohne Verlegung, ohne Importpfad-Änderung)

**Bleiben:** `ALERTABLE_METRICS` (für `shared/alarme-tab/activeAlertMetricsFromCatalog.ts` und
`tripAlertMetricsFromCatalog.ts`), `METRIC_DEFAULTS` (für `alertPreviewHelpers.ts`),
`levelToThreshold`, `thresholdTitle` (für AlertMetricLevelRow) sowie alles, was diese intern
brauchen (z. B. `THRESHOLD_CROSSING_METRICS`, Typ `SensLevel`).

**Werden gelöscht** (kein produktiver Nutzer): `DELTA_ONLY_METRICS`, `METRIC_PRESETS`,
`PresetName`, `ALL_ALERT_METRICS`, `MetricRowState`, `RowStateMap`, `alertRulesToRowState`,
`rowStateToAlertRules`, `migrateAlertPreset`, `activeAlertableMetrics`, `deriveAlertMode`,
`applyModeToRowState`. Der Developer prüft beim Löschen mit svelte-check und Build, dass
nichts Produktives daran hängt; was dort doch gebraucht wird, bleibt.

Kommentare nachziehen: `lib/utils/alertMetricLabels.ts:88` (nennt AlertsPreviewCard) und
`lib/utils/alertMetricCatalogIds.ts:35` (nennt `DELTA_ONLY_METRICS`).

### 3. Python

`src/services/alert_preset.py:149` `expand_preset` hat keinen produktiven Aufrufer und wird
gelöscht. Nachzuziehen: Kommentar `src/services/compare_alert.py:56` und Docstring
`alert_preset.py:185`. Betroffene Tests: `tests/tdd/test_issue_846_alert_preset.py`,
`tests/tdd/test_issue_889_feuchte_alerts.py`. Zusicherungen, die weiter gelten (z. B. keine
HUMIDITY-Regel), werden auf `expand_per_metric_levels` umgestellt; Zusicherungen, die nur das
Verhalten von `expand_preset` beschrieben, entfallen.

### 4. Test-Infrastruktur

Regel: **Tests eines gelöschten Prüflings fallen mit weg, Tests produktiver Prüflinge bleiben
grün.** Mit anzupassen, weil sie tote Komponenten oder gelöschte Symbole referenzieren
(Developer ermittelt die vollständige Liste per grep):
`alerts-tab/__tests__/f7Pruefstand.ts` (lädt AlertsTab, AlertCard, AlertMetricTable,
AlertPresetSelector), `lib/i18n/__tests__/keine_hartkodierten_nutzertexte.test.ts:510-516`
(Scan-Liste), `shared/__tests__/legacy_wizard_removed.test.ts:41,116`,
`alerts-tab/alertMetricTable.test.ts` (nur noch bleibende Exporte), `issue_850_*.test.ts`,
`issue_864_*.test.ts` und weitere Tests, die gelöschte Symbole importieren. Frontend-Tests
laufen über `node --test`, nicht über Vitest.

### 5. Doku

- ADR-0077: Nachtrag „S4" (Schnitt C, Übergabe an #2793, ausdrücklich kein stilles
  Zurückdrehen der Entscheidung, nur Aufschub der Leser-Abbauten).
- `docs/specs/modules/alert_metric_channels.md`: S4-Abschnitt; bei `:1256-1258`
  („`has_active_rules` bleibt unangetastet … S1–S4") klarstellen, dass das auch für diese
  Scheibe gilt und an #2793 übergeht. Tabellenzeile S4 (`:1289`) auf den tatsächlichen Schnitt
  anpassen.

### 6. Übergabe an #2793

Vor dem Schließen von #1895 steht in #2793 ein Kommentar mit: den unverändert gelassenen
Lesern (Liste oben), den Gate-Fällen 1 bis 4, dem Hinweis, dass `_has_active_alert_metric`
nicht äquivalent ist, und der Bitte um eine frische Prod-Messung der Regel-`channels` in
`data/users/*/briefings/*.json` (nicht `trips/`) vor dem Abbau der Kanal-Union.

## Scope: Affected Files

| File | Change Type | Description |
|------|-------------|-------------|
| `frontend/src/lib/components/alerts-tab/AlertsTab.svelte` | DELETE | tot, kein Importeur |
| `frontend/src/lib/components/alerts-tab/AlertCard.svelte` | DELETE | tot |
| `frontend/src/lib/components/alerts-tab/AlertMetricTable.svelte` | DELETE | tot |
| `frontend/src/lib/components/alerts-tab/AlertMetricRow.svelte` | DELETE | nur von AlertMetricTable genutzt |
| `frontend/src/lib/components/alerts-tab/AlertPresetSelector.svelte` | DELETE | tot |
| `frontend/src/lib/components/trip-detail/AlertsPreviewCard.svelte` | DELETE | nur ungenutzter Re-Export |
| `frontend/src/lib/components/trip-detail/index.ts` | MODIFY | Export-Zeile `:7` entfernen |
| `frontend/src/lib/components/alerts-tab/alertMetricTable.ts` | MODIFY | tote Exporte löschen, genannte behalten |
| `frontend/src/lib/utils/alertMetricLabels.ts` | MODIFY | Kommentar `:88` |
| `frontend/src/lib/utils/alertMetricCatalogIds.ts` | MODIFY | Kommentar `:35` |
| zugehörige Tests der gelöschten Komponenten (`*.test.ts`, `__tests__/`) | DELETE | fallen mit dem Prüfling weg |
| `alerts-tab/__tests__/f7Pruefstand.ts`, `keine_hartkodierten_nutzertexte.test.ts`, `legacy_wizard_removed.test.ts`, `alertMetricTable.test.ts`, `issue_850_*`, `issue_864_*` | MODIFY | Verweise auf Gelöschtes bereinigen |
| `frontend/src/lib/components/alerts-tab/AlertMetricLevelTable.svelte`, `AlertMetricLevelRow.svelte`, `AlertCooldownCard`, `AlertQuietHoursCard`, `AlertMetricChannelsBlock`, `AlertPreviewCard.svelte`, `alertPreviewHelpers.ts`, `shared/AlarmeTab.svelte` | UNCHANGED | produktiv |
| `src/services/alert_preset.py` | MODIFY | `expand_preset` löschen, Docstring `:185` |
| `src/services/compare_alert.py` | MODIFY | Kommentar `:56` |
| `tests/tdd/test_issue_846_alert_preset.py`, `tests/tdd/test_issue_889_feuchte_alerts.py` | MODIFY | auf `expand_per_metric_levels` umstellen |
| `tests/tdd/test_issue_1895_s4_rueckbau.py` und ein Frontend-Gegenstück (`node --test`) | CREATE | Import-Nachweise aus AC-4 |
| `docs/adr/0077-*.md` | MODIFY | Nachtrag „S4" |
| `docs/specs/modules/alert_metric_channels.md` | MODIFY | S4-Abschnitt |
| `src/services/trip_alert.py`, `src/services/alert_channels.py`, `api/routers/validator.py`, `src/app/loader.py`, `src/app/models.py`, `src/app/trip.py`, `internal/**`, `cmd/**`, `TripTabs.svelte`, `hubUebersichtModell.ts` | UNCHANGED | Übergabe an #2793 |

## Expected Behavior

- **Input:** unverändert (Trips, Ortsvergleiche, Alarm-Konfiguration).
- **Output:** unverändert; Alarme-Reiter, Vorschau, Versand und Alarm-Prüfung verhalten sich wie
  vorher.
- **Side effects:** keine. Weniger Code, keine Persistenzänderung.

## Test Plan

### Automated Tests (TDD RED)

- [ ] Python: `from src.services.alert_preset import expand_preset` wirft `ImportError` (rot
  vor der Löschung, grün danach); `expand_per_metric_levels` bleibt importierbar.
- [ ] Frontend (`node --test`): dynamischer Import der gelöschten Module (`AlertsTab`,
  `AlertCard`, `AlertMetricTable`, `AlertMetricRow`, `AlertPresetSelector`, `AlertsPreviewCard`)
  schlägt fehl; Import von `ALERTABLE_METRICS`, `METRIC_DEFAULTS`, `levelToThreshold`,
  `thresholdTitle` liefert Werte.
- [ ] test_846/889 auf `expand_per_metric_levels`: GIVEN Feuchte-Metrik, WHEN Stufen expandiert
  werden, THEN entsteht keine HUMIDITY-Regel.
- [ ] Bestehende Tests der Helfer unter `shared/alarme-tab/` (Metrik-Menge aus
  `ALERTABLE_METRICS`) bleiben grün.
- [ ] Bestehende Python-Alarmtests (Gate, Kanalauflösung, Radar, amtlich) bleiben grün.
- [ ] Gesamte Frontend-Suite per `node --test`, svelte-check und Build grün.
- [ ] Staging-Sichtprüfung des Alarme-Reiters auf allen vier Flächen.

## Acceptance Criteria

- **AC-1:** Given ein Nutzer öffnet den Alarme-Reiter / When er Trip-Hub, `/trips/new`,
  Ortsvergleich-Editor und `/compare/new` nacheinander aufruft / Then zeigt jede der vier
  Flächen weiterhin Empfindlichkeitsstufen-Tabelle, Vorschau, Block „Kanäle je Wettergröße",
  Ruhezeiten und Cooldown wie vor dem Rückbau.
  - Test: bestehende Frontend-Suite grün plus Sichtprüfung auf Staging an allen vier Flächen
    (Nutzerverhalten: Reiter vollständig und bedienbar).

- **AC-2:** Given die Metrik-Liste für Alarme wird aus dem Katalog abgeleitet / When die
  Helfer in `shared/alarme-tab/` (`activeAlertMetricsFromCatalog`, `tripAlertMetricsFromCatalog`)
  `ALERTABLE_METRICS` nutzen / Then liefern sie dieselbe Menge alarmfähiger Metriken wie vorher.
  - Test: bestehende Helfer-Tests laufen unverändert grün; die Vorschau-Logik
    (`alertPreviewHelpers`) nutzt weiter `METRIC_DEFAULTS`.

- **AC-3:** Given die Tests 846 und 889 prüfen die Stufen-Expansion / When sie auf
  `expand_per_metric_levels` umgestellt laufen / Then bleiben die weiter geltenden Zusicherungen
  (z. B. keine HUMIDITY-Regel) grün.
  - Test: `tests/tdd/test_issue_846_alert_preset.py` und `test_issue_889_feuchte_alerts.py`
    grün, ohne Verweis auf `expand_preset`.

- **AC-4:** Given der tote Code ist entfernt / When ein Test die gelöschten Module bzw.
  Symbole dynamisch importiert / Then schlägt der Import fehl (Python:
  `from src.services.alert_preset import expand_preset` wirft `ImportError`; Frontend: die
  sechs gelöschten Komponenten und die gelöschten Exporte aus `alertMetricTable.ts` sind nicht
  auflösbar).
  - Test: Import-Versuch mit erwartetem Fehler. Rot vor, grün nach der Löschung; kein
    grep-Dateiinhalt-Test.

- **AC-5:** Given die Löschungen sind umgesetzt / When svelte-check und der Frontend-Build
  laufen / Then melden sie keine neuen Fehler und der Build ist grün.
  - Test: svelte-check-Lauf (Fehlerzahl nicht höher als auf `20b38d383`) und Build ohne Fehler.

- **AC-6:** Given Gate, Kanal-Union und Kanalauflösung bleiben unverändert / When Alarm-Prüfung
  und Versand laufen (Wetteränderung, Radar, amtliche Warnung, alle vier Kanäle) / Then
  ändert sich weder die Entscheidung „prüfen oder überspringen" noch die Kanalwahl.
  - Test: bestehende Python-Alarmtests (Trip-Alarm, Kanalauflösung, Radar, amtlich) bleiben
    ohne Anpassung grün.

- **AC-7:** Given die Doku hält Entscheidungen fest / When ein Leser ADR-0077 und
  `alert_metric_channels.md` öffnet / Then findet er einen Abschnitt „S4" mit dem Schnitt,
  der Übergabe an #2793 und dem Hinweis, dass nichts stillschweigend zurückgedreht wird.
  - Test: `tests/test_adr_index_drift.py` bleibt grün; Abschnitt ist per Review prüfbar
    (Doku-Nachweis, `# doc-compliance-test`).

- **AC-8:** Given #1895 soll geschlossen werden / When der Abschluss ansteht / Then steht
  vorher in #2793 ein Kommentar mit den unverändert gelassenen Lesern, den Gate-Fällen 1 bis 4,
  dem Hinweis auf die Nicht-Äquivalenz von `_has_active_alert_metric` und der Bitte um eine
  Prod-Messung der Regel-`channels` in `data/users/*/briefings/*.json` vor dem Abbau der
  Kanal-Union.
  - Test: Kommentar in #2793 per `gh issue view 2793 --json comments` vorhanden, bevor
    `gh issue close 1895` läuft.

## Known Limitations

- `alert_rules` wird bis #2793 weiter von Go geschrieben (`SyncAlertRules`) und gelesen; das
  Feld wächst weiter. Das ist gewollt (Invariante 4, Epic #2345; ADR-0106; AC-17 aus #2792).
- Die Alarm-Vorschau (`AlertPreviewCard`) hängt weiter an `trip.alert_rules`.
- **Kein Mail-Validator-Lauf nötig:** Es ändert sich kein Mail-Inhalt und keine Kanalauflösung;
  gelöscht wird nur nicht eingebundene UI und eine Python-Hilfe ohne Aufrufer. Weder
  Renderer noch Mail-Inhalts-Dateien werden angefasst, das Renderer-Commit-Gate greift nicht.
- Übersehene Importe sind das einzige Restrisiko; sie fallen in svelte-check, Build oder der
  Frontend-Suite auf.

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** ADR-0077 (Nachtrag „S4"), bezieht sich auf ADR-0043 und ADR-0106
- **Rationale:** Der Schnitt (nur Totes löschen, Leser und Persistenz an #2793) ist eine
  Auslegung der bestehenden Entscheidung, kein neues ADR; der Nachtrag hält ihn fest, damit
  niemand die Übergabe als vergessen liest.

## Changelog

- 2026-11-05: Initial spec created (Schnitt C, gemessener Import-Befund auf 20b38d383)
