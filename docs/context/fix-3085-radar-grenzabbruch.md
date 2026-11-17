# Context: fix-3085-radar-grenzabbruch

## Request Summary
Issue #3085 (Nebenbefund aus #3081): Läuft die Radar-Frist mitten in der Parallelphase ab, endet `parallel_fetch.wait` genau an der Frist; ein noch laufender Worker wird als `skipped="timeout"` (Lücke, AC-8) eingesammelt, statt die Radar-Einheit abzubrechen (AC-4, `hit_deadline=True`), wie ADR-0082 es beabsichtigt. Zu entscheiden: Verhalten so gewollt (Spec/ADR präzisieren) oder Hauptfaden meldet bei Fristablauf den Abbruch der Einheit.

## Related Files
| File | Relevance |
|------|-----------|
| `src/services/parallel_fetch.py` | `fetch_ordered` (Z.129), `_acquire_slots` (Z.100), `wait(..., timeout=deadline_at - monotonic)` (Z.157), `_collect` (Z.163–176): fertig → value/error; cancel gelingt → `skipped="deadline"`; läuft noch → `skipped="timeout"` (Z.176). Inline-Pfad `_fetch_inline` Z.113–125 |
| `src/services/radar_service.py` | `RadarDeadlineExceeded` (Z.478), `_raise_if_deadline` (Z.484), `nowcast_abrufer` (Z.494), `hole_nowcasts` (Z.511–537, parallel nur wenn `monotonic < frist`, sonst seriell mit direktem Raise Z.532), `wirf_radar_grenze` (Z.540–545: raist nur fertige Outcomes mit `error` = RadarDeadlineExceeded) |
| `src/services/trip_alert.py` | `_radar_folgepunkte` Z.1848–1884 (Aufruf hole_nowcasts + wirf_radar_grenze; jedes `out.skipped` → `None` = Lücke, Warnung „der Alarm laeuft weiter“), `check_radar_alerts_run` Z.2058ff (`progress`, Stempel via `state_store.record`, WARNING bei hit_deadline Z.2080, `AlertCheckRunResult(hit_deadline=…)` Z.2089), `_abort_radar_unit` Z.2093–2098, Fristablauf vor nächstem Trip Z.2110, `except RadarDeadlineExceeded` Z.2337 / Z.2381–2388 |
| `src/services/compare_radar_alert.py` | Ortsvergleich-Pendant: hole_nowcasts Z.672–677, wirf_radar_grenze Z.583, except Z.180 |
| `api/routers/scheduler.py` | `_radar_run_response` Z.177ff: `status="partial"` nur bei `hit_deadline`, `reason="deadline"` |

## Existing Patterns
- Frist als absoluter `time.monotonic()`-Wert (`deadline_at`), durchgereicht bis in die Quellenkette (`get_nowcast` prüft vor jeder Quelle).
- Grenzabbruch = Exception `RadarDeadlineExceeded`, Hauptfaden fängt sie je Einheit und ruft `_abort_radar_unit` (Stempel entfernen, `checked -= 1`, `hit_deadline=True`).
- Übersprungene Punkte (`skipped`) werden zu Lücken (`None`) mit Log-Zeile; Auswertung läuft weiter.
- Trip und Ortsvergleich teilen `hole_nowcasts`/`wirf_radar_grenze` (Code-Teilung beachten).

## Dependencies
- Upstream: `concurrent.futures.wait`, `time.monotonic`, `get_nowcast`-Quellenkette, Slot-Semaphore in parallel_fetch.
- Downstream: Stempel (`state_store.record`), Alarmprotokoll/Sperrzeit/Tageslimit, `AlertCheckRunResult.hit_deadline` → Scheduler-Antwort `status` partial/ok → Go-Scheduler.

## Existing Specs / ADRs
- `docs/adr/0082-budget-je-alarmart-radar-im-5-minuten-takt.md`: Z.29–31 Budgetrechnung D + E < Wartebudget (Worker darf bis E nach Frist laufen); Z.37–41 Zeitgrenze reicht in die Quellenkette; Z.46–49 Grenzabbruch ist keine Entwarnung: keine Auswertung, kein Protokolleintrag, keine Sperrzeit-/Tageslimit-Buchung, kein Stempel.
- `docs/specs/modules/feat_1539_s4_radar_parallel.md`: AC-4 (Z.179–184, Worker-RadarDeadlineExceeded → Einheit abbrechen, keine Lücke), AC-8 (Z.207–212, übersprungene Punkte mit Grund Frist/Zeitüberschreitung = gescheitert + Log), Mutation Z.261.
- `docs/specs/modules/feat_2261_a2s2_radar_takt.md`: AC-4 (Z.138), AC-8 (Z.150: Kettenabbruch mitten in der Reststrecke ⇒ kein Alarm, kein Protokolleintrag, kein Stempel) — deckt sich mit dem gewünschten Abbruch.
- `docs/specs/modules/fix_3081_flaky_kerntests.md`: Z.50 („beide Zweige gewollt“ — Testsicht), Z.53 Test-Naht, Z.67/87 Nebenbefund.

## Tests
- `tests/tdd/test_radar_parallel_fetch.py`: `_Uhr` (steuerbare monotonic, Z.24/76/103–118), `_wait_mit_signal` (Z.167), `test_ac4_trip_grenzabbruch_im_worker_bricht_die_einheit_ab` (Z.670), `test_ac5_compare_grenzabbruch_…` (Z.710), `test_ac4_compare_frist_schon_abgelaufen_…` (Z.794), AC-8-Tests Z.961/990/1016.
- Weitere hit_deadline-Tests: `tests/tdd/test_radar_alarmlauf_fairness.py`, `tests/tdd/test_alert_run_deadline.py`, `tests/tdd/test_alert_run_fairness.py` (`test_status_partial_nur_bei_hit_deadline`), `tests/test_success_status_guard.py`, `tests/tdd/test_radar_alarmlauf_zeitgrenze.py`. Reset: `tests/conftest.py` Z.686.

## Kernbefund
Im Ist-Zustand wird bei Fristablauf mitten in der Parallelphase ein Trip mit Lücken **ausgewertet**: Alarm kann auslösen, Stempel wird gesetzt, Status „ok“. Das widerspricht ADR-0082 Z.46–49 und feat_2261 AC-8 (kein Alarm/Eintrag/Stempel bei Grenzabbruch). Keine falsche Entwarnung, aber Auswertung auf unvollständiger Datenlage und kein `partial`-Status.

## Lösungsrichtungen (für /20-analyse)
1. Hauptfaden: Frist abgelaufen und Outcome `skipped="timeout"` (Worker lief noch) ⇒ als Grenzabbruch werten (`wirf_radar_grenze` erweitert) → `_abort_radar_unit`.
2. `wait` bis Frist + Einzelschritt-Toleranz E (ADR-Rechnung D + E), damit Worker ihr `RadarDeadlineExceeded` noch liefern.
3. Nur Spec/ADR präzisieren (Lücken gewollt) — kollidiert mit ADR-0082 Z.46–49 und feat_2261 AC-8.
Unterscheidung `skipped="deadline"` (nie gestartet, AC-8 Compare „Grenzabbruch“) vs. `"timeout"` beachten; Compare-Pfad gleich behandeln (Code-Teilung).

## Risks & Considerations
- Wartebudget des Go-Schedulers: Option 2 verlängert den Lauf um bis zu E.
- Bestehende AC-8-Tests (Trip Z.1016, Compare Z.990) erwarten Lücke/Ausfall bei Zeitüberschreitung — müssten angepasst werden (Spec-Änderung, kein stilles Umbiegen).
- Abgebrochene Einheit muss im nächsten Lauf fair zuerst drankommen (Fairness-Tests).
- Kein Produktionscode-Wechsel ohne neues/ergänztes ADR, falls Spec-AC-8 inhaltlich geändert wird.

## Analysis

### Type
Bug (Abweichung Ist-Verhalten von ADR-0082 Punkt 5 / feat_2261 AC-8)

### Befunde (verifiziert)
- Frist D=45 s gilt **je Nutzeraufruf** (`check_radar_alerts_run` setzt `deadline_at` je Aufruf neu); Go ruft Nutzer seriell (`runForAllUsers`/`runUserStep`), Wartebudget je Nutzer min(240, Rest von 270).
- Einzelschritt real bis E=188 s (geosphere TIMEOUT 30 je Request, Retries bis FETCH_DEADLINE_SECONDS=180, Sidecar 8 s) — ein laufender HTTP-Call ist nicht unterbrechbar.
- Trip/Compare divergieren heute: Trip behandelt `skipped="deadline"` UND `"timeout"` als Lücke; Compare wirft bei `"deadline"` (`_wirf_bei_nie_gestarteten`) Grenzabbruch, wertet `"timeout"` als Ausfall (mit Protokollspur).
- `skipped` im Radar-Pfad entsteht ausschließlich durch Fristablauf (wait-Timeout = Frist; Inline-Pfad prüft ebenfalls Frist) ⇒ jedes `skipped` ist fachlich ein Grenzabbruch.

### Variantenvergleich
| Variante | Laufzeit Worst-Case je Nutzer | Aushungerung | ADR-0082-konform |
|---|---|---|---|
| Ist | 45 s (+ verwaister Nachlauf) | nein, aber Auswertung auf Lücken, Stempel, Status ok | nein |
| 1 jedes `skipped` ⇒ Grenzabbruch | 45 s | wie ADR-Design (Trip bleibt per Fairness vorn), kein neues Risiko | ja |
| 2 warten bis D+E, dann wie 1 | 233 s (Reserve 7 s zu 240), Folgenutzer rutschen in not_reached | wie ADR, minimal besser | ja, aber knapp |
| 3 nur Spec/ADR präzisieren | 45 s | – | nein (Spec gegen ADR) |

### Technical Approach (Empfehlung: Option 1)
- `radar_service.wirf_radar_grenze(outcomes)`: zusätzlich zu Worker-`RadarDeadlineExceeded` bei **jedem** `skipped` (deadline/timeout) `RadarDeadlineExceeded` werfen. Geteilt von Trip und Compare ⇒ Divergenz beseitigt (Code-Teilung).
- Trip `_radar_folgepunkte`: Zweig `out.skipped` wird unerreichbar → entfernen; Abbruch läuft über bestehendes `except RadarDeadlineExceeded` → `_abort_radar_unit` (kein Stempel, `hit_deadline=True`, Status partial).
- Compare: `_wirf_bei_nie_gestarteten` redundant → entfernen bzw. in `wirf_radar_grenze` aufgehen lassen (Log-Zeile je übersprungenem Ort erhalten: „nicht erreicht“); `skipped`-Ausfall-Zweig entfällt ⇒ kein Ausfall-Protokolleintrag bei Grenzabbruch (ADR-0082 Punkt 5: Grenzabbruch ist kein Quellenausfall).
- `parallel_fetch.fetch_ordered` bleibt **unverändert** (andere Aufrufer: Briefing, compare_alert, compare_official_alert, trip_alert Z.3081).
- Log je übersprungenem Punkt/Ort bleibt (nichts still weglassen).

### Affected Files
| File | Change Type | Description |
|------|-------------|-------------|
| src/services/radar_service.py | MODIFY | `wirf_radar_grenze` wirft auch bei `skipped` (+Logzeile je Punkt) |
| src/services/trip_alert.py | MODIFY | toten `skipped`-Zweig in `_radar_folgepunkte` entfernen, Docstring |
| src/services/compare_radar_alert.py | MODIFY | `_wirf_bei_nie_gestarteten` + `skipped`-Ausfallzweig entfallen |
| tests/tdd/test_radar_parallel_fetch.py | MODIFY | AC-8 Trip (Z.1016) und Compare-timeout (Z.990) fachlich auf Grenzabbruch umstellen; neue Fälle „Worker läuft bei D noch“ Trip+Compare |
| tests/tdd/test_radar_alarmlauf_fairness.py | MODIFY | Fall „Worker läuft bei D noch ⇒ kein Stempel, im Folgelauf vorn“ |
| docs/specs/modules/feat_1539_s4_radar_parallel.md | MODIFY | AC-8 neu formulieren (übersprungen ⇒ Grenzabbruch) |
| docs/specs/modules/fix_3085_radar_grenzabbruch.md | CREATE | Bugfix-Spec |
| docs/adr/0082-… | ggf. Präzisierung (keine Entscheidungsänderung — Code wird ADR-konform) |

### Scope Assessment
- Files: 3 Produktcode, 2 Tests, 2 Doku
- Estimated LoC: Produkt +15/-25, Tests +80/-30
- Risk Level: LOW–MEDIUM (lokal im Radar-Pfad, Baustein unberührt; fachliche Umkehr zweier AC-8-Tests ist durch ADR gedeckt)

### Dependencies
`_abort_radar_unit`, Fairness-Stempel (`AlertCheckStateStore`), Scheduler-Antwort partial bei `hit_deadline`, Compare-`except RadarDeadlineExceeded` (Z.180).

### Bekannte Restwirkung (kein Teil des Fixes)
Kopf-der-Schlange: dauerhaft langsamer Trip bleibt per Fairness vorn und bricht jeden Lauf ab — besteht im ADR-Design genauso, beobachtbar über `skipped_ids`/`hit_deadline`. Verwaiste Worker laufen nach Abbruch bis zur nächsten Quellengrenze weiter (wie heute).

### Open Questions
- keine technischen. Fachliche Änderung (Compare: Zeitüberschreitung erzeugt keinen Ausfall-Protokolleintrag mehr, Trip wird bei Fristablauf nicht mit Lücken ausgewertet) wird über die Spec-Freigabe abgenommen.
