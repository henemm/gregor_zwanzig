# Context: fix-1695-anker-ortsmitternacht

## Request Summary
Ortsvergleich-Anker (Δ-Alarm-Snapshot) darf nicht auf zwei Kalendertage zerfallen, wenn eine Ortsmitternacht zwischen den `fetch()`-Aufrufen der Orte eines Presets liegt (Issue #1695, Folge von #1661 Finding F005).

## Ursache (belegt)
- `src/services/compare_location_weather_source.py:121` — `now = datetime.now(timezone.utc)` wird in JEDEM `fetch()` neu bestimmt; `local_today` (Z.125) und `window_day` (Z.130/132) folgen daraus.
- `src/services/scheduler_dispatch_service.py:1288` (`_write_compare_alert_snapshots`) — Schleife über Orte, ein `fetch()` je Ort, jeder mit eigenem `now`. Fällt Ortsmitternacht dazwischen, tragen Orte desselben Presets verschiedene `target_date`.
- Zweites, schmaleres Fenster: Ortsmitternacht innerhalb eines einzelnen Laufs (Sammlung → Schreiben). Der Versatz `tage_ab_ortstag` bleibt richtig, der Bezugspunkt wandert.

## Related Files
| File | Relevanz |
|------|----------|
| src/services/compare_location_weather_source.py | `fetch()`: Zeitpunkt einmalig selbst aufgelöst; hier optionaler `now`-Parameter |
| src/services/point_weather.py:95-125 | `LocationWeatherSource`-Protocol; Docstring zu optionalen Kwargs (`target_date`, `tage_ab_ortstag`) |
| src/services/scheduler_dispatch_service.py:1228 | `_write_compare_alert_snapshots`: ein Zeitpunkt je Preset festhalten und durchreichen |
| src/services/compare_alert.py:681 | Leseseite (15-Min-Check), nutzt `target_date` aus dem Anker; vermutlich unverändert |
| docs/specs/modules/fix_1661_anker_vom_falschen_tag.md | Known Limitations, Vorgänger-Spec |
| docs/artifacts/fix-1661-anker-vom-falschen-tag/adversary-dialog.md | Finding F005 |
| tests/tdd/_compare_*_fixtures.py, test_compare_*.py | Fixtures nutzen `tage_ab_ortstag`; Fake-Quellen müssen neuen Kwarg tolerieren |

## Existing Patterns
- Optionale Kwargs nur durchreichen, wenn ein Bezug vorliegt (Protocol-Signatur bleibt schlank, Docstring point_weather.py).
- Werte werden DURCHGEREICHT, nie nachträglich berechnet (#1661 F003).
- Pflicht-Kwargs ohne Default gegen stillen Rückfall (F001, `user_id` #2387).

## Lösungsrichtung
`_write_compare_alert_snapshots` bestimmt EINMAL `now = datetime.now(timezone.utc)` und gibt es als optionalen Kwarg `now` an alle `fetch()` eines Presets. `fetch()` nutzt `now` falls gegeben, sonst wie bisher. Je Ort wird `local_today` weiter aus der Ortszeit gebildet (Kamtschatka-Test aus #1661 bleibt gültig). Verboten: Wächter „Anker-Tag == Mail-Tag" (feuert ab UTC+6 dauerhaft).

## Dependencies / Dependents
- Upstream: `tz_for_coords`, `local_dt`, `day_window`, `SegmentWeatherService`.
- Downstream: Anker-Snapshots (`CompareWeatherSnapshotService`), 15-Min-Alarm-Check (`compare_alert.py`), Test-Fakes der Quelle.

## Risks & Considerations
- Fake-/Test-Quellen ohne `now`-Kwarg würden bei bedingungsloser Übergabe brechen → Fakes prüfen, nur beim Schreiben übergeben.
- Ein festgehaltenes `now` darf die Fenster-Berechnung nicht verfälschen: im Mitternachts-Fallback (Z.154) ist `now` der Fensterbeginn, gleiche Semantik prüfen.
- Test muss Ortsmitternacht zwischen zwei Orten simulieren (Uhr springt zwischen den Aufrufen) und vor dem Fix rot sein.
- Issue ist `priority:low`/`status:deferred`; PO hat es explizit aufgerufen.

## Analysis

### Type
Bug (nutzersichtbar: Anker-Satz über zwei Kalendertage → Änderungsalarm ohne geänderte Vorhersage)

### Affected Files (with changes)
| File | Change Type | Description |
|------|-------------|-------------|
| src/services/compare_location_weather_source.py | MODIFY | `fetch()` bekommt optionalen Kwarg `now` (tz-aware UTC); statt `datetime.now(timezone.utc)` (Z.~121) wird `now` genutzt, falls gegeben. Fensterbildung und Mitternachts-Fallback (Z.~154) bleiben unverändert |
| src/services/scheduler_dispatch_service.py | MODIFY | `_write_compare_alert_snapshots`: EIN `now` vor der Orte-Schleife, in `zusatz` an jedes `fetch()` |
| src/services/point_weather.py | MODIFY (Docstring/Protocol) | `now` als optionaler Kwarg dokumentieren |
| tests/tdd/test_compare_anker_ortsmitternacht.py | CREATE | Test: Uhr springt zwischen Ort 1 und Ort 2 über die Ortsmitternacht → beide Anker tragen dasselbe `target_date`; vor Fix rot |
| tests/tdd/_compare_*_fixtures.py | MODIFY (ggf.) | Fake-Quelle (`_compare_alert_parallel_fixtures.py:212`) muss `now` tolerieren |

### Scope Assessment
- Files: 3 Quell- + 1–2 Testdateien
- Estimated LoC: +~15 Quelle / +~60 Test
- Risk Level: LOW (neuer optionaler Kwarg, Default = bisheriges Verhalten; Leseseite `compare_alert.py` unverändert)

### Technical Approach
Ein Zeitpunkt je Preset-Lauf, durchgereicht statt je Ort neu bestimmt (Muster #1661 F003). `local_today` wird weiter je Ort aus der Ortszeit gebildet (Kamtschatka-Test #1661 bleibt gültig). Die Übergabe erfolgt nur auf der Schreibseite; die 15-Min-Leseseite nutzt weiter `target_date` aus dem Anker. Kein Wächter „Anker-Tag == Mail-Tag" (würde ab UTC+6 dauerhaft feuern, reißt F002 auf). Das Protocol-Kwarg `now` darf nur bedingt durchgereicht werden, falls Fakes es nicht kennen – hier aber unbedingt im Schreibpfad, da `CompareLocationWeatherSource` der einzige Schreib-Impl ist; Fakes im Test-Fixture werden angepasst.
Nicht gelöst (bewusst): Fenster 1 (Ortsmitternacht zwischen Fälligkeits-Sammlung und Schreiben) wird nur insoweit entschärft, als `now` einmal im Schreibpfad gefroren wird; die Sammlung selbst liegt in `compare_slot_scheduler`. Spec muss klären, ob dessen Zeitpunkt ebenfalls durchgereicht wird (Empfehlung: nein – Versatz `tage_ab_ortstag` bleibt richtig, Bezugspunkt wird im Schreibpfad einheitlich).

### Dependencies
Upstream: `tz_for_coords`, `local_dt`, `day_window`, `SegmentWeatherService`. Downstream: `CompareWeatherSnapshotService`, `compare_alert.py`, Test-Fakes.

### Open Questions
- [ ] Soll auch der Zeitpunkt der Fälligkeits-Sammlung (Fenster 1) bis ins Schreiben durchgereicht werden, oder genügt das Einfrieren im Schreibpfad? (Empfehlung: genügt; Spec legt das als Known Limitation fest)
