# Context: fix-2218-alarm-stumme-ausfaelle

## Request Summary
#2218 Scheibe B (Epic #2505): Alarm-Ausfälle sollen nicht mehr stumm bleiben. Drei Einträge aus dem Sammel-Issue:
B2-70 (Ortsvergleich-Alarm: Fehler je Ort nur geloggt), B1-09 (Trip-Alarm „No fresh weather data“ = Dauerrauschen,
echter Ausfall nicht von Normalfall trennbar), C5-32 (`enrichment_health` zählt pro Pfad, nicht pro Ort).
Scheibe A (C4-53, Versand-Status aus Zustellung) ist live (PR #2532). Alle Nachweise unten am Code von `main` (c0855414b) geprüft.

## Related Files
| File | Relevanz |
|------|----------|
| `src/services/compare_alert.py:525-551` | `_detect_triggered_locations`: `except Exception → logger.error(...) ; continue` — B2-70. Ein dauerhaft scheiternder Ort fällt still aus; das Ergebnis `(sent, failed)` zählt nur gescheiterte *Presets* (`_check_all_counted`, Z.189-206), nie Orte. |
| `src/services/trip_alert.py:688-694` | `if not fresh_weather: logger.warning("No fresh weather data ..."); return False` — B1-09. |
| `src/services/trip_alert.py:2816-2872` | `_fetch_fresh_weather`: überspringt absolvierte/morgige Segmente (LEGITIM, leer ist dann normal) UND schluckt Abruffehler je Segment (`logger.error`, kein Zähler). Beide Ursachen enden in derselben leeren Liste → ununterscheidbar. Das ist die Kernursache von B1-09. |
| `src/services/trip_alert.py:181-196` | `AlertCheckRunResult` (alerts_sent/checked/skipped/failed). `failed` zählt nur Trips mit Ausnahme (#2217). |
| `src/providers/enrichment_health.py` | Schreibseite des Health-Journals (`log_enrichment_call(path, outcome, detail)`), JSONL `diagnostics/enrichment_calls.jsonl`, fail-soft. Kein Feld für Ort/Trip. Pfad-Vokabular: thunder, thunder_additive, radar_nowcast, snowgrid, forecast_capture. |
| `internal/scheduler/enrichment_health.go` | Leseseite: aggregiert pro `path` (last_attempt/success/fallback, self_throttled) → `/api/scheduler/status` Schlüssel `enrichment_health`. Gruppiert generisch nach freiem String. |
| `/home/hem/henemm-infra/scripts/check-gregor20.sh:775-830` | Monitor-Auswertung („2e-e“): Alter von `last_success_at` je Pfad, Schwelle `ENRICHMENT_MAX_AGE_H`=48 → EXT_FAIL. Liest nur Top-Level-Pfade, kennt keine Unterstruktur. |
| `docs/specs/modules/fix_1581_enrichment_health.md` | Bestehende Spec (approved) des Journals; Scheibe B erweitert sie. |
| `docs/specs/modules/trip_alert.md`, `feat_1459_alert_protokoll.md` | Trip-Alarm-Spec bzw. Alarm-Protokoll (`alert_log`) — mögliche Ablage für Ausfälle. |
| `docs/adr/0018-provider-fallback-ohne-kaschieren.md` | Verlangt wachsendes Health-Signal je degradierbarem Pfad. |

## Existing Patterns
- **Pfad-Journal + Go-Aggregator + Monitor-Skript** (#1581): Python schreibt JSONL, Go liest roh (nur Zeitstempel/Flags, keine Schwellenentscheidung), `check-gregor20.sh` bildet Alter/Schwelle. Neuer `path`-String erscheint automatisch im Aggregat (Kommentar `enrichment_health.py:23`, #1992 AC-8).
- **Einheiten-Fehler zählen statt schlucken** (#2217): `report_unit_failure(...)` + `failed`-Zähler im Ergebnis, Go macht daraus `error`.
- **Dedupe/Dämpfung gegen Log-Rauschen:** `track_resolution_health` / `_failed_lookups` (Vorbild für C5-47, nicht Teil dieser Scheibe).

## Dependencies
- Upstream: `SegmentWeatherService.fetch_segment_weather`, `_evaluate_one_location` (Snapshot/Provider), `app.loader.get_data_root`.
- Downstream: Go-Scheduler (`/api/scheduler/status`, Fehlerstatus aus `failed`), `check-gregor20.sh` (BetterStack-Heartbeat nur bei ERRORS==0), Alarm-Protokoll.

## Existing Specs
`fix_1581_enrichment_health.md`, `feat_1992_geosphere_health_amendment.md`, `trip_alert.md`, `feat_1459_alert_protokoll.md`, `compare_official_alert_channels.md`.

## Risks & Considerations
1. **„Leer“ ist nicht gleich „Ausfall“.** Bei B1-09 muss der Fix die zwei Ursachen trennen (alle Segmente legitim übersprungen = normal, kein Signal; Abruf gescheitert = Ausfall). Ein naiver „jedes leere Ergebnis zählt als Fehler“ erzeugt Fehlalarme (Etappenpausen, Ruhetage).
2. **Mandanten:** Journal liegt unter der Datenwurzel; Ort-/Trip-Kennungen dürfen nicht nutzerübergreifend in einem Status landen, der anderen Nutzern gezeigt wird. Test mit zwei Nutzern Pflicht.
3. **Granularität C5-32:** Pro-Ort-Auswertung im Journal braucht ein Zusatzfeld (z. B. `unit`/`location`) oder eigene Pfadnamen — Go-Aggregator ist Pfad-generisch, Monitor liest nur Top-Level. Änderung am Format muss abwärtskompatibel zu Bestandszeilen bleiben (Zeilen ohne Feld).
4. **Cross-Repo:** `check-gregor20.sh` liegt in `henemm-infra` und läuft aus dem Arbeitsbaum SOFORT live — Änderungen dort erst nach Gegenprobe, Mutationen nur in einer Kopie (siehe Memory). Heartbeat-Pflicht „Readiness statt Liveness“ gilt.
5. **Alarm-Entscheidung unangetastet:** Es ändert sich nur die Sichtbarkeit, nie, ob alarmiert wird. Kein stilles Verhalten im Hauptpfad ändern (Zusage fail-closed bleibt).
6. **Log-Rauschen:** B1-09 heißt „~1350 Treffer“. Ziel ist ein wachsendes Aggregat statt Einzelzeilen, nicht noch mehr Zeilen.
7. **Alle vier Kanäle:** Betrieb-sichtbar heißt Monitoring, kein Kanal-Thema; Nutzerseitig keine neue Meldung ohne PO-Entscheid.
8. **Abgrenzung:** C5-02, C5-15, C5-37, B2-71, C5-47, C5-53 bleiben in #2218 offen (spätere Scheiben).

## Analysis

### Type
Bug (Observability-Lücke: Ausfälle bleiben stumm). Alarm-Entscheidung bleibt unangetastet.

### Scope dieser Scheibe B
B2-70 (Compare-Alarm: Ortsfehler), B1-09 (Trip-Alarm: leer vs. Ausfall), C5-32 (Health-Journal pro Ort/Einheit).
Bestätigt am Code (Branch = main c0855414b): `compare_alert.py:545-547` (`logger.error` → `continue`),
`trip_alert.py:688-690` (`No fresh weather data` → `return False`), `trip_alert.py:2816-2872` (zwei Ursachen → eine leere Liste).

### Affected Files (with changes)
| File | Change Type | Description |
|------|-------------|-------------|
| `src/services/trip_alert.py` | MODIFY | `_fetch_fresh_weather` trennt „legitim übersprungen“ von „Abruf gescheitert“ (Zähler); bei Ausfall Health-Eintrag statt Dauer-Warning |
| `src/services/compare_alert.py` | MODIFY | `_detect_triggered_locations` zählt/meldet gescheiterte Orte (Health-Eintrag je Ort) |
| `src/providers/enrichment_health.py` | MODIFY | neuer Pfad (z. B. `alert_fetch`) + optionales Feld `unit` (abwärtskompatibel, Altzeilen ohne Feld) |
| `internal/scheduler/enrichment_health.go` | MODIFY (klein) | optional: Aggregat je Einheit; Altzeilen ohne `unit` weiter lesbar |
| `tests/test_alert_stumme_ausfaelle.py` | CREATE | Verhaltenstests (leer ≠ Ausfall, Ort fällt aus ⇒ Signal, 2 Nutzer) |
| `docs/specs/modules/fix_1581_enrichment_health.md` | MODIFY | Erweiterung als Amendment oder neue Spec `fix_2218_alarm_ausfaelle.md` |
| `henemm-infra/scripts/check-gregor20.sh` | MODIFY (Cross-Repo, später) | Schwelle für neuen Pfad; erst nach Gegenprobe in Kopie |

### Scope Assessment
- Files: 4–5 Produktivdateien + 1 Testdatei (+ Infra-Skript separat)
- Estimated LoC: +150/-20 (unter Limit 250)
- Risk Level: MEDIUM — Alarm-Hauptpfad wird berührt, Verhalten (ob alarmiert wird) darf sich NICHT ändern; Gefahr: Fehlalarme bei Etappenpausen.

### Technical Approach
1. **B1-09:** `_fetch_fresh_weather` liefert zusätzlich, wie viele Segmente *versucht* wurden und wie viele *scheiterten*. Leer + 0 Versuche (alles absolviert/morgen) = Normalfall, nur `debug`. Leer + Fehler ≥ 1 = Ausfall ⇒ `log_enrichment_call(PATH_ALERT_FETCH, unavailable, detail=trip)` und `report_unit_failure`; Dauer-Warning entfällt zugunsten des wachsenden Aggregats. Rückgabewert/`return False` bleibt (fail-closed).
2. **B2-70:** Im `except` zusätzlich Health-Eintrag mit `unit=<preset>/<location>` und Zähler; das Ergebnis `(sent, failed)` bleibt, Orts-Fehler laufen als eigener Zähler ins Journal (Presets nicht fälschlich als gescheitert werten, solange andere Orte liefen).
3. **C5-32:** Optionales Feld `unit` im JSONL; Go-Aggregat ergänzt pro Pfad eine Liste „zuletzt fehlgeschlagene Einheiten“. Pfad-Ebene bleibt unverändert ⇒ Monitor-Skript und Altzeilen bleiben kompatibel.
4. Mandant: Journal liegt unter der Nutzer-/Datenwurzel; `unit` enthält nur IDs des eigenen Nutzers, Test mit zwei Nutzern.

### Dependencies
Upstream: `SegmentWeatherService.fetch_segment_weather`, `_evaluate_one_location`, `alert_check_state.report_unit_failure`. Downstream: Go-Scheduler-Status, `check-gregor20.sh` (Heartbeat nur bei ERRORS==0), ADR-0018.

### Open Questions
- [ ] Neuer Pfadname vs. Wiederverwendung von `radar_nowcast`? Empfehlung: eigener Pfad `alert_fetch` (Ausfall nicht hinter gesundem Pfad verstecken, vgl. C5-32).
- [ ] Soll das Monitor-Skript bei dauerhaft gescheitertem Ort (z. B. >48 h) EXT_FAIL melden? Empfehlung: ja, gleiche Schwelle wie `ENRICHMENT_MAX_AGE_H`, als eigener Folgeschritt in Infra.
- [ ] Spec-Form: Amendment an #1581 oder eigene Spec? Empfehlung: eigene Spec, ACs auf Deutsch zur Freigabe.
