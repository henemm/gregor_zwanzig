# Context: feat-1895-s4-alert-rules-rueckbau

## Request Summary
Issue #1895, Scheibe S4: Rückbau von `trip.alert_rules` (Alarm-Modus „Absolut/Delta/Beides“), nachdem S1–S3b die Kanalzuordnung je Metrik in `alert_metric_channels` verlegt haben. Ziel laut Issue: kein Konfigurationsrest ohne Wirkung (ADR-0043), Kanalwahl ohne Verlust.

Gemessen am 2026-11-05 auf `20b38d383` (Explore-Agent, nur lesend).

## Related Files

### Python — Leser von `trip.alert_rules` (genau vier)
| Datei | Rolle |
|---|---|
| `src/services/trip_alert.py:696-700` | Prüf-Gate `has_active_rules` im send-Pfad (`has_preset or has_metric_levels or any(r.enabled for r in trip.alert_rules)`), Abbruch `:701-707` |
| `src/services/trip_alert.py:1199-1203` | dasselbe Gate kopiert in `check_all_trips`, Skip `:1213-1218` |
| `src/services/alert_channels.py:120-127` | `_trip_channel_inputs`: Union der aktiven Regel-Kanäle als Basis für alle metrikfreien Alarme (Radar `trip_alert.py:2157`, amtlich `:3411`, `:609`, `:802`, `:1414`) |
| `api/routers/validator.py:118-121,139-141` | Diagnose „from_alert_rules“, Rangfolge seit #946 fachlich falsch, nicht im Versand |

### Python — Entität/Persistenz
| Datei | Rolle |
|---|---|
| `src/app/models.py:1212-1285` | `AlertRuleKind`, `AlertRule` — **bleibt** als internes Transportobjekt (`alert_preset.expand_per_metric_levels`, `weather_change_detection.from_alert_rules`, `deviation_alert_engine:193-204` lesen nie `trip.alert_rules`) |
| `src/app/trip.py:199` | `Trip.alert_rules` |
| `src/app/loader.py:192-206,384-415,654,688,721,1906-1919` | Deserialisierung, Legacy-Migration aus `change_threshold_*`, immer serialisiert |
| `src/app/loader.py:854-883` (Aufruf `:659`) | S2-Migration `alert_rules[].channels` → `alert_metric_channels` (kopierend, beim Laden, persistiert erst beim nächsten Python-Save) |
| `src/services/alert_preset.py:149` | `expand_preset` ohne produktiven Aufrufer (toter Code) |

### Go
| Datei | Rolle |
|---|---|
| `internal/model/trip.go:21-27,56-67,123,370-419` | Modell; `SyncAlertRules` erzeugt bei jedem Load/Save je aktiver alarmfähiger Metrik eine DELTA-Regel `enabled=true`, wandelt ABSOLUTE in DELTA |
| `internal/store/trip.go:66-67,256-259,301-304` | nil→`[]`, Sync bei Load (Speicher) und Save (Platte) |
| `internal/handler/trip.go:268,402-404` | PUT-DTO, Blind-Replace wenn gesendet |
| `internal/handler/weather_config.go:106-108` | Sync beim weather-config-PUT |
| `internal/store/migrate_1257.go`, `cmd/migrate1257/main.go` | einmalige Altmigration |

### Frontend
| Datei | Rolle |
|---|---|
| `alerts-tab/AlertsTab.svelte`, `AlertMetricTable.svelte` (Modus absolute/delta/both), `AlertCard.svelte`, `trip-detail/AlertsPreviewCard.svelte` | **nicht gemountet** (tote UI) |
| `alertMetricTable.ts:119,151,359` | Regel-Umrechner, nur von toter UI genutzt |
| `shared/AlarmeTab.svelte:608` → `AlertPreviewCard.svelte:30-35,45` | **produktiv**: Alarm-Vorschau nutzt `trip.alert_rules`; leer = „keine alarmfähigen Metriken“ |
| `alertPreviewHelpers.ts:64-130` | Vergleich baut synthetische `absolute`-Regeln für die Vorschau |
| `TripTabs.svelte:62` | Badge „wertebereiche“ zählt aktivierte Regeln |
| `hubUebersichtModell.ts:136` | `hatRegel`, Spiegel des Gates |
| `types.ts:72,96,384` | Typen |

### Ortsvergleich
Kein `alert_rules`-Äquivalent (`model/compare_preset.go:116` nur `AlertMetricChannels`; `alert_channels.py:136`). Kein Gate.

## Existing Patterns
- Was `alert_rules` heute praktisch bedeutet: „im Wetter-Tab ist eine alarmfähige Metrik aktiv“ — von Go `SyncAlertRules` abgeleitet, also redundante Ableitung aus `display_config.metrics`.
- Gleichwertige Ableitung existiert in Python: `DeviationAlertEngine._has_active_alert_metric(display_config)` (`deviation_alert_engine.py:188-194`, Detektor-Backfill #961).
- Feld-Rückbau nach Invariante 4 (Epic #2345): aus Bedienung/Logik entfernen, nicht aus Persistenz; Read-Modify-Write mit Merge (#102).

## Dependencies
- Upstream: `display_config.metrics`, `metric_alert_levels`, `alert_metric_channels`, `report_config.alert_on_changes`.
- Downstream: Alarm-Prüfung aller Trips (Gate), Kanalauflösung aller metrikfreien Alarme (Radar, amtlich), Alarm-Vorschau, Hub-Badge, Validator-Diagnose.

## Existing Specs / ADRs
- `docs/specs/modules/alert_metric_channels.md` — S1–S3b; `:1256-1258` „`has_active_rules` bleibt unangetastet … S1–S4“ (Wegfall wäre nicht verhaltensneutral, überstimmt `alert_on_changes=False`).
- ADR-0077 `:69-71` — Rückbau als S4 vorgesehen.
- ADR-0043 — keine Konfigurationsfläche ohne Wirkung.
- ADR-0013 `:50-51` — ABSOLUTE im Versandpfad tot seit #816.
- ADR-0021 `:126-133` — Radar erbt die `alert_rules`-Union.
- **ADR-0106 `:30` (Epic #2791 „Einstellungen neu“)** — `metric_alert_levels` UND `alert_rules` entfallen als eigene Einstellungen; Migration ist **#2793 (S2)**. `docs/specs/modules/feat_2792_s1_profil_ampel.md:169,174,287,304`: `alert_rules` bis S2 unverändert (AC-17); `corridors` notify=True/mark=False tragen Δ-Werte aus `alert_rules`.

## Risks & Considerations
1. **Gate-Verhalten:** Wegfall des Regel-Arms ändert Verhalten für Trips ohne Preset und ohne `metric_alert_levels`, aber mit aktiven Alarm-Metriken und `alert_on_changes=False` bzw. ohne `report_config`. Ersatz nur mit identischer Wahrheitstabelle (Kandidat `_has_active_alert_metric`).
2. **Kanal-Union für metrikfreie Alarme:** Regel-Kanäle fließen heute in Radar/amtlich ein. Prod-Zählung in der Spec: 0 Regeln mit `channels` — vor Rückbau frisch auf Prod messen (`data/users/*/briefings/*.json`, nicht `trips/`), Go migriert nicht.
3. **Überschneidung mit #2793 / ADR-0106:** dort wird `alert_rules` ohnehin abgelöst, und #2792-Spec verlangt es bis S2 unverändert. Abgrenzung S4 vs. #2793 ist vor der Spec zu klären (gegebenenfalls S4 auf tote UI + Leser beschränken, Persistenz-Ende an #2793).
4. **Go `SyncAlertRules` schreibt das Feld bei jedem Save** — Rückbau ohne Go-Änderung lässt das Feld weiter wachsen; Rückbau mit Go-Änderung berührt Persistenz (Pre-Snapshot-Hook).
5. **Produktive Vorschau** (`AlarmeTab` → `AlertPreviewCard`) hängt an `trip.alert_rules`; muss auf `display_config`-Ableitung umgestellt werden, sonst „keine alarmfähigen Metriken“.
6. Testbestand groß: 74 Python-, 20 Go-, 32 Frontend-Testdateien referenzieren `alert_rules`.
7. Kollisionsabsprache: Sitzung an #2792 (S1c-3) fasst weder Alarm-Pfad noch `alert_rules` an, zieht #2793 nicht ohne Meldung (2026-11-05).

## Analysis

### Type
Feature (Rückbau/Aufräumen, Scheibe S4 von #1895)

### Entscheidung zum Schnitt (Tech-Lead, 2026-11-05)
Drei Varianten bewertet (Plan-Agent, nur lesend):

| | A: tote UI + Leser umstellen | B: Vollrückbau inkl. Persistenz | C: nur Totes löschen |
|---|---|---|---|
| Verhaltensneutral | nein (Gate-Fälle 1-4 unten) | nein | ja |
| Konflikt #2792 (Known Limitations „Alarm-Logik unverändert“) / #2793 | mittel (Doppelarbeit) | hoch (gegen AC-17, Invariante 4) | keiner |
| Risiko | mittel-hoch | hoch (Datenverlust-Klasse #102) | niedrig |
| Scope | ~25 Dateien | 40+ Dateien | ~10 Dateien, überwiegend Löschung |

**Gewählt: C.** Der nutzersichtbare Kern von #1895 (Modus „Absolut“ verspricht wirkungslose Schwelle) ist heute nicht mehr erreichbar, weil der alte Regel-Editor nicht mehr gemountet ist; die Kanalzuordnung je Metrik ist mit S1–S3b umgezogen. Was bleibt, ist toter Code. Die produktiven Leser von `trip.alert_rules` und die Persistenz gehen an **#2793** (Epic #2791 S2), das `alert_rules` und `metric_alert_levels` als Alarm-Auslöser ohnehin ablöst. Dort ist der Rückbau der Leser fachlich neu definiert; ihn jetzt vorzuziehen wäre nicht verhaltensneutral und doppelte Arbeit.

**Warum das Gate nicht jetzt umgestellt wird** (`trip_alert.py:696-700`, `:1199-1203`; Ersatzkandidat `DeviationAlertEngine._has_active_alert_metric`, `deviation_alert_engine.py:156-171`, ist NICHT äquivalent):
1. Vom Nutzer deaktivierte Regel (`enabled=false`) bleibt in Go erhalten (`SyncAlertRules`: `rule := ex`) → Gate heute False, Ableitung True → Alarm-Prüfung würde bei `alert_on_changes=False` wieder anspringen.
2. Trips mit nie synchronisierter Regelliste: Regeln leer, Ableitung True.
3. `_ALERT_METRIC_TO_CATALOG_ID` ist eine andere Metrik-Menge als Go `AlertableMetrics`.
4. Fehlende `report_config` wird in send-Pfad (:701-705) und `check_all_trips` (:1213) verschieden behandelt.

Go `SyncAlertRules` (`internal/model/trip.go:370-419`) setzt bei neuen Regeln keine `channels`; Regel-Kanäle stammen nur aus Altbestand/totem Editor. Die Kanal-Union (`alert_channels.py:120-127`) bleibt bis #2793.

### Affected Files (with changes)
| File | Change Type | Description |
|------|-------------|-------------|
| `frontend/src/lib/components/alerts-tab/AlertsTab.svelte`, `AlertCard.svelte`, `AlertMetricTable.svelte`, `AlertMetricRow.svelte`, `AlertMetricLevelRow.svelte`, `AlertPresetSelector.svelte` (+ weitere nur von dort genutzte Dateien im Ordner) | DELETE | tote UI, nicht gemountet; Importe vor dem Löschen je Datei nachweisen |
| `frontend/src/lib/components/trip-detail/AlertsPreviewCard.svelte` + Export in `trip-detail/index.ts` | DELETE/MODIFY | tote Vorschaukarte |
| `frontend/src/lib/components/alerts-tab/alertMetricTable.ts` | MODIFY/MOVE | **nicht ganz tot:** `ALERTABLE_METRICS` wird produktiv importiert von `shared/alarme-tab/activeAlertMetricsFromCatalog.ts:6` und `tripAlertMetricsFromCatalog.ts:11`. Konstante behalten (ggf. nach `shared/alarme-tab/` verlegen), Regel-Umrechner (`:119,151,359`) löschen |
| `frontend/src/lib/components/alerts-tab/alertPreviewHelpers.ts` | PRÜFEN | importiert `METRIC_DEFAULTS`; produktiv genutzt vom Vergleich (synthetische Regeln für `AlertPreviewCard`) → bleibt, sofern produktiv erreichbar |
| `src/services/alert_preset.py:149` `expand_preset` | DELETE | ohne produktiven Aufrufer; Kommentar `compare_alert.py:56` nachziehen |
| `tests/tdd/test_issue_846_alert_preset.py`, `tests/tdd/test_issue_889_feuchte_alerts.py` | MODIFY | Tests auf `expand_preset` streichen bzw. auf `expand_per_metric_levels`/`_PRESET_TABLE` umstellen, wo die Zusicherung (z. B. keine HUMIDITY-Regel) weiter gilt |
| Frontend-Tests zu den toten Komponenten (`__tests__`, `*.test.ts`, `f9Pruefstand.ts:255`) | DELETE/MODIFY | mit dem Prüfling entfernen |
| Gate, Kanal-Union, `AlarmeTab`→`AlertPreviewCard`, `TripTabs.svelte:62`, `hubUebersichtModell.ts:136`, `api/routers/validator.py`, Go-Modell/Store/Handler, Loader | UNVERÄNDERT | Übergabe an #2793 (Kommentar dort mit dieser Liste) |

### Scope Assessment
- Files: ~10–15 (überwiegend Löschungen)
- Estimated LoC: +~20 / −1500…2500
- Risk Level: LOW (kein produktiver Pfad ändert Verhalten; Risiko nur durch übersehene Importe → svelte-check + Frontend-Suite + Import-Grep als Nachweis)

### Technical Approach
1. Je zu löschender Datei Import-Nachweis (grep über `frontend/src`, ohne Tests) — nur Dateien ohne produktiven Importeur löschen.
2. `ALERTABLE_METRICS` (und ggf. `METRIC_DEFAULTS`, `DELTA_ONLY_METRICS`, falls produktiv) aus `alertMetricTable.ts` erhalten; restliche Umrechner löschen.
3. `expand_preset` löschen, betroffene Tests umstellen; Wächter-Test: kein produktiver Code importiert die gelöschten Symbole.
4. Doku: ADR-0077 Abschnitt S4 nachtragen (Schnitt + Übergabe an #2793, kein stilles Zurückdrehen), Spec `alert_metric_channels.md` S4-Abschnitt.
5. Übergabe-Kommentar in #2793 mit den unverändert gelassenen Lesern, den Gate-Fällen 1–4 und der Bitte um Prod-Messung der Regel-`channels` (`data/users/*/briefings/*.json`) vor Abbau der Kanal-Union.
6. Nach Lieferung kann #1895 geschlossen werden (alle drei Fragen des Issues beantwortet: Absolut-Modus weg, Kanalzuordnung umgezogen, Bestandsdaten unangetastet).

### Dependencies
- Keine Laufzeit-Abhängigkeit; Abgrenzung zu #2792 (Sitzung fasst Alarm-Pfad nicht an) und #2793 (übernimmt Leser + Persistenz).

### Open Questions
- keine an den PO (Schnitt ist technische Entscheidung, nutzersichtbar ändert sich nichts).
