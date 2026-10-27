# Context: feat-2261-sz8-messpunkt-position

## Request Summary
#2261 Teil A, Szenario 8 (B-3, aus #2050): Der Radar-Alarm misst dort, wo der Nutzer sein wird. Lange Etappe, Position weit vom Startpunkt: Messpunkt = Position zum Ereigniszeitpunkt; Wegpunkt verschieben muss den Messpunkt verschieben (Herkunft #2017).

## Befund zum Ist-Stand (Vorab-Kartierung)
- #2017 (CLOSED) hat den Messpunkt vom Segmentstart auf die Position zur **Fenstermitte** (`RADAR_ONSET_THRESHOLD_MIN // 2` ab `now_utc`) verlegt. Bewusste Näherung: die Position zum Onset ist mit einem Abruf ein Zirkelschluss (Onset entsteht erst aus dem Abruf). Siehe `docs/context/fix-2017-nowcast-messpunkt.md`.
- #2051 S2a hat daraus bis zu `RADAR_ZONE_MAX_POINTS = 6` Messpunkte entlang der Reststrecke gemacht; der erste Punkt bleibt der #2017-Messpunkt und trägt die Auslöseregel.
- Höhe wandert mit (#1991/#2017), gerundet auf ganze Meter an der Aufrufstelle.

## Related Files
| File | Relevance |
|------|-----------|
| src/services/trip_alert.py:1798-1880 | Radar-Block: `_at`, `points_along_remaining_route`, `_pos = _punkte[0]`, `get_nowcast(lat, lon, elevation_m)` |
| src/services/trip_segments.py:561 | `position_at_time()` — Interpolation, Segment-/Tagesgrenze, fail-soft-Klemmung |
| src/services/trip_segments.py:37,686-740 | `RADAR_ZONE_MAX_POINTS`, `points_along_remaining_route()` |
| tests/tdd/test_position_at_time.py | Bausteintests der Positionsberechnung (AC-1..AC-11) |
| tests/tdd/test_issue_822_radar_nowcast_segment.py, test_radar_alert_follows_ortstag.py, test_regen_ausdehnung_messpunkte.py | Bestehende Tests mit `get_nowcast`-Bezug — prüfen, ob sie "Wegpunkt verschieben ⇒ abgefragte Koordinate verschiebt sich" auf Auslöseebene bewachen |
| tests/tdd/test_alarm_szenario_*.py | Muster der Szenario-Wächter über die `AlarmPruefstrecke` (S1), kein Mock-Theater |

## Existing Patterns
- Szenario-Wächter: `AlarmPruefstrecke` gegen echte `check_radar_alerts()`, Frames über DI-Naht `frame_source=` eines echten `RadarNowcastService`.
- Positionsberechnung wird geteilt (Scheduler-Briefing und Alarm rufen `position_at_time`).

## Dependencies / Dependents
- Upstream: `resolve_current_segment`, `convert_trip_to_segments`, `naismith` (Gehzeit mit Steigung), `RadarNowcastService.get_nowcast`.
- Downstream: Radar-Alarm Trip; Zonen/Ausdehnung (S2a); Cache-Schlüssel `lat_lon_region` (TTL 300 s).

## Existing Specs
- docs/specs/modules/ — #2017-Spec (Messpunkt), #2051 S2a (Ausdehnung), alarm_pruefstrecke.md (S1)

## Risks & Considerations
- Radar-Block ist heiß umkämpft (#2065, #2051, #2050 S4a/b) — nur additiv, Wächter-first.
- "Position zur Fenstermitte" ≠ "Position zum Ereigniszeitpunkt": Ob das gegenüber B-3 eine echte Lücke ist, entscheidet die Analyse (Mehrpunkt-Abfrage deckt die Strecke ab). Gegebenenfalls nur Wächter + Doku der Näherung, kein Produktivcode.
- Mutationen nur per String-Ersetzung mit Sicherungskopie.

## Analysis

### Type
Feature (Nachweis-Szenario aus Epic #2261 Teil A, Herkunft #2050 B-3 / #2017). Voraussichtlich **nur Test + Doku, kein Produktivcode**.

### Befund
- Die Zusicherung „Messpunkt wandert mit dem Wegpunkt" ist auf Bausteinebene (`test_position_at_time.py`) und für den **Jetzt-Pfad** (`test_jetzt_misst_am_aufenthaltsort.py` AC-3) bewacht. Für den **Radar-Auslösepfad** bewacht `test_issue_822_radar_nowcast_segment.py::test_2017_ac8` die Koordinate zur Fenstermitte — aber gegen eine **feste** Trip-Konfiguration: Es gibt keinen Test, der denselben Lauf mit **verschobenem Wegpunkt** wiederholt und prüft, dass sich die abgefragte Koordinate (alle bis zu 6 Punkte) mitverschiebt. Das ist die B-3-Lücke: der Nachweis „Wegpunkt verschieben ⇒ Messpunkt verschieben" an der Stelle, an der er WIRKT (Argumente von `get_nowcast` im echten `check_radar_alerts()`).
- Lange Etappe: `points_along_remaining_route` legt bis zu 6 Punkte im 2-km-Abstand ab der Fenstermitte-Position (+27 Min) entlang der Reststrecke. Der Zeitpunkt der Fenstermitte ist die dokumentierte Näherung (Zirkelschluss-Schutz, `fix_2017_nowcast_messpunkt.md`); Position zum echten Onset (bis +55 Min, ≈ 3–4 km weiter) wird von Punkt 2–3 abgedeckt.
- Restrisiko (zu dokumentieren, nicht zu bauen): Die **Auslöseregel** wird nur am ersten Punkt ausgewertet, die Folgepunkte liefern nur Zonen. Ein Ereignis, das nur über Punkt 2+ liegt, löst nicht aus. Bewusste Entscheidung aus #2051 S2a.

### Affected Files (with changes)
| File | Change Type | Description |
|------|-------------|-------------|
| tests/tdd/test_alarm_szenario_messpunkt_position.py | CREATE | Szenario-Wächter Sz.8: lange Etappe (>12 km), Lauf A vs. Lauf B mit verschobenem Wegpunkt; Koordinaten (alle Punkte) + Höhe verschieben sich; Mutationsgegenprobe |
| docs/specs/modules/feat_2261_sz8_messpunkt_position.md | CREATE | Spec mit ACs |
| docs/specs/modules/fix_2017_nowcast_messpunkt.md | MODIFY (Doku) | Näherung „Fenstermitte vs. Onset" + Restrisiko Auslöseregel nur am ersten Punkt festhalten |
| src/services/trip_alert.py | KEINE Änderung erwartet | nur falls der Wächter echte Abweichung beweist |

### Scope Assessment
- Files: 1 Test, 2 Specs/Doku
- Estimated LoC: +120–160 Test (Doku zählt nicht)
- Risk Level: LOW (kein Produktivcode; Radar-Block bleibt unangetastet)

### Technical Approach
Muster der vorhandenen Szenario-Wächter: echter `check_radar_alerts()`, DI-Naht `frame_source`/aufzeichnender Nowcast-Dienst (wie `_alarm_lauf_2017`), gestellte Uhr. Zwei Läufe mit identischem Trip bis auf einen verschobenen Zwischen-/Zielwegpunkt; Erwartung aus `position_at_time` unabhängig berechnet NICHT als Spiegel, sondern als Ungleichheit + Richtungsprüfung (Koordinate wandert zum neuen Wegpunkt). Mutations-Gegenproben: Messpunkt auf `start_point` zurückdrehen / Wegpunkt-Verschiebung ignorieren ⇒ Test muss rot werden.

### Dependencies
`trip_segments.position_at_time`/`points_along_remaining_route`, `RadarNowcastService.get_nowcast`, Helfer in `test_issue_822_radar_nowcast_segment.py` (`_alarm_lauf_2017`) — prüfen, ob in `tests/helpers/` teilbar.

### Open Questions
- [ ] Spec-Entscheidung: Doku-Restrisiko (Auslöseregel nur Punkt 1) nur festhalten — oder ein eigenes Ticket? Empfehlung: nur festhalten (Sammel-Issue #1199), da bewusste #2051-Entscheidung.
