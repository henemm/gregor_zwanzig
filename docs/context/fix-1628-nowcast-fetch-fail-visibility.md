# Context: fix-1628-nowcast-fetch-fail-visibility

**Issue:** [#1628](https://github.com/henemm/gregor_zwanzig/issues/1628) · Labels `bug`, `priority:critical`, `area:alerts`, `session:alarm`
**Track:** Full Process (Intake-Score 4/6) · Modell Opus
**Erstellt:** 2026-08-08

## Request Summary

Ein fehlgeschlagener NowCast-Radarabruf erzeugt ein `NowcastResult`, das **bitidentisch** mit einem echten „kein Regen"-Ergebnis ist (`frames=[]`, `onset_minutes=None`, `intensity_label="Kein Niederschlag"`). Der Alarm bleibt in beiden Fällen aus — ohne dass irgendwo sichtbar wird, dass die Datengrundlage fehlte. Gemessen an Trip „KHW 403" (Karnischer Höhenweg, 46.73042 / 12.321643): 14 von 14 Radar-Alert-Läufen am 2026-08-08 scheiterten mit HTTP 503.

## 🔴 Korrektur der Issue-Hypothese (Recherche-Kernbefund)

Das Issue vermutet eine **„Bounding-Box-Lücke direkt an der Staatsgrenze"** — dass keine der regionalen Quellen greife. **Das ist am Code falsifiziert.** Die Koordinate liegt in **drei** Boxen:

| Prädikat | Box (lat / lon) | 46.73042 / 12.321643 |
|---|---|---|
| `_within_radolan` (`radar_service.py:574`) | 47.0–55.1 / 5.8–15.1 | ❌ (lat < 47.0) |
| `_within_inca` (`radar_service.py:582`) | 46.3–49.1 / 9.5–17.2 | ✅ |
| `_within_dpc` (`radar_service.py:589`) | 36.0–47.5 / 6.5–19.0 | ✅ |
| `_within_arome_france` (`radar_service.py:596`) | 41.0–51.5 / −5.5–10.0 | ❌ (lon > 10.0) |
| `_within_icon_d2` (`radar_service.py:603`) | 44.0–58.0 / 2.0–19.0 | ✅ |

**Die regionalen Quellen werden alle versucht — sie scheitern nur lautlos.** Aus dem Log-Muster (nur `models=None` failed, keine Zeile für `icon_d2`/`italia_meteo_arpae_icon_2i`) folgt zwingend: hätte einer der regionalen Open-Meteo-Zweige den `except`-Pfad genommen, hätte er (a) geloggt und (b) `_openmeteo_unavailable_this_call=True` gesetzt, was den finalen `models=None`-Aufruf bei `radar_service.py:421-428` stumm abgeschnitten hätte — die 503-Zeile gäbe es dann gar nicht. Also: **ARPAE und ICON-D2 antworteten mit HTTP 200, hatten aber für diesen Punkt keine Daten** (All-None-Guard `:459-461` oder leere `minutely_15`-Sektion `:462-475` — beide loggen nichts).

Damit verschiebt sich der Schwerpunkt: **das eigentliche Problem sind nicht die Bounding-Boxen, sondern die Zahl stiller `[]`-Ausgänge.**

### Inventar der stillen Ausgänge (jeder liefert `[]` ohne Log und ohne Marker)

| Ort | Ursache | Log? | Flag? |
|---|---|---|---|
| `providers/geosphere.py:345-349` | `except httpx.HTTPStatusError: return None` | **nein** | — |
| `radar_service.py:340-341` | INCA `if not ts or not ts.data` | nein | nein |
| `providers/radar_dpc.py:136-137` | Pixel außerhalb Raster | **nein** | — |
| `radar_service.py:380-381` | DPC `if not frames` | nein | nein |
| `radar_service.py:421-428` | Doppelverbrauch-Guard | nein | (liest Flag) |
| `radar_service.py:431-434` | Budget-Drosselung | nein | ja (`throttled`) |
| `radar_service.py:459-461` | **All-None-Guard** (HTTP 200, Punkt außerhalb Modellgitter) | **nein** | **nein** |
| `radar_service.py:462-475` | leere `minutely_15`-Sektion | **nein** | **nein** |
| `radar_service.py:476-482` | echter Fehlschlag | ja (WARNING) | ja (intern) |

Nur der letzte Fall loggt — und auch er hinterlässt **keine Spur im `NowcastResult`**.

## Related Files

| Datei | Relevanz |
|---|---|
| `src/services/radar_service.py` | Kern. `NowcastResult:78-92`, Quellenkette `_fetch_frames_with_fallback:283-316`, gemeinsamer Open-Meteo-Trichter `_fetch_openmeteo_15:410-482`, Ergebnisbildung `_derive_result:525-573`, interne Flags `:126-127`/`:175-176` |
| `src/services/trip_alert.py` | `radar_alert_due():82-85` (3 Zeilen, liest NUR `onset_minutes`), `check_radar_alerts()` mit Gate `:781-793`, Fetch `:819`, stilles `continue` `:825-826` |
| `src/services/compare_radar_alert.py` | Compare-Pfad, Fetch `:239`, importiert dieselbe `radar_alert_due` (`:30`) |
| `src/services/alert_gate.py` | #1467-S3-Freigabe-Baustein, `check_nowcast_gate():160-215` — sitzt **VOR** dem Fetch, sieht das `NowcastResult` nie |
| `src/services/alert_log.py` | `append_entry():135`, `append_suppressed_entry():241-315` (nur Gate-Abweisungen, `gate_reason` Pflicht), Reason-Konstanten `:45-58` |
| `src/services/forecast_budget.py` | `ForecastBudgetGate`, Prioritäten `:65-75`, Zustandsdatei `:46-51`, ungenutztes `snapshot():93-119` |
| `src/providers/call_log.py` | `log_api_call():56-80`, Quellen-Marker `_CALL_SOURCE_MARKERS:31-43` — **kein Radar-Marker** |
| `src/services/official_alerts/warn_egress.py:212-266` | **Vorbild:** `log_warn_service_call()` mit `ok`/`self_throttled` — genau die gesuchte Unterscheidung, bereits bis in den Status-Endpoint durchgereicht |
| `src/providers/geosphere.py`, `src/providers/radar_dpc.py` | Stille `[]`-Pfade (s. Inventar) |
| `internal/scheduler/forecast_budget_health.go` | Go-Seite des Budget-Blocks im Status-Endpoint |
| `internal/scheduler/warn_service_health.go:262-306` | **Vorbild** für einen Health-Block aus einer JSONL-Diagnosedatei |
| `internal/scheduler/scheduler.go:611-680` | `Status()` — hier hinge ein neuer Block |
| `tests/unit/test_radar_budget_and_priority.py` | `_TripwireClient:53-89` — die einzige bestehende Technik, einen HTTP-Fehlschlag deterministisch nachzustellen |
| `tests/helpers/nowcast_gate_fixtures.py` | Mock-freie Helfer für den Gate-/Alarm-Pfad |

## Existing Patterns

1. **Zustandstransfer Python → Go läuft ausschließlich über Dateien** im geteilten `DataDir` (`data/diagnostics/*.jsonl|json`), **nie** über HTTP. Der HTTP-Kanal geht nur Go→Python (Trigger).
2. **Status-Endpoint liefert Rohzahlen, keine Bewertung** — die Schwelle sitzt im externen Monitor `check-gregor20.sh` (henemm-infra, nicht in diesem Repo). Mehrfach explizit kommentiert (`warn_service_health.go:240-249`).
3. **Datenschutz #252:** keine `user_id`/`trip_id`/E-Mail im öffentlichen Status-Endpoint. Der einzige pro-Nutzer-Pfad (`users/*/diagnostics/corrupt_trips.json`) wird zu einer anonymen Zahl verdichtet. → Die Issue-Formulierung „für Trip X war die NowCast-Prüfung heute N mal ohne Datengrundlage" ist **so** im Status-Endpoint nicht zulässig; pro-Trip-Sichtbarkeit müsste über `alert_log.json` (pro Nutzer) laufen.
4. **`ok`/`self_throttled`-Muster** in `warn_egress.py` als fertige Blaupause für „Abruf fand statt und war gültig" vs. „Abruf fand nicht statt/scheiterte".
5. **Fail-soft überall** — kein Provider-Ausfall kommt je als Exception oben an. Die `try/except` in `trip_alert.py:820-822` und `compare_radar_alert.py:240-242` fangen faktisch nur Programmierfehler.

## Dependencies

- **Upstream:** `httpx` direkt in `radar_service.py:447-450` (baut die URL selbst, benutzt **keinen** Provider) · `ForecastBudgetGate` · `providers.geosphere`, `providers.radar_dpc`, `providers.brightsky` · `GZ_TEST_FIXTURE_DIR`
- **Downstream:** `trip_alert.check_radar_alerts` · `compare_radar_alert._detect_triggered_locations` · `trip_report_scheduler` (Starkregen-Kurzhinweis `:1170`) · `trip_command_processor._show_now` (`/jetzt`, `:1293`) · `notification_service.send_radar_alert` / `send_multi_location_radar_alert` · `output/renderers/alert/project.py:246-279` · `alert_urgency.urgency_from_radar`

## Existing Specs & ADRs

| Dokument | Inhalt |
|---|---|
| **`docs/adr/0018-provider-fallback-ohne-kaschieren.md`** | **Zentral.** Punkt 3 „Nicht-Kaschieren-Invariante": jedes Ausweichen muss in den Daten markiert, protokolliert und im Health-Aggregat sichtbar sein, mit einem **mit der Ausfalldauer wachsenden** Signal. Folgepflicht wörtlich: „Neue degradierbare Datenpfade müssen dieselbe Invariante erfüllen." Der Radar-Pfad erfüllt sie **nicht** — #1628 ist ein Verstoß gegen ein bereits akzeptiertes ADR, keine neue Designfrage. |
| `docs/specs/modules/radar_nowcast.md` | Ursprungs-Spec #656: Quellenkette, `NowcastResult`, Alarm-Schwelle |
| `docs/specs/modules/fix_1329_c2_radar_nowcast_cache.md` | Radar-Cache + Budget/Priority; **AC-6 führt `throttled` ein** |
| `docs/specs/modules/rework_1467_s3_nowcast.md` | Gemeinsamer Freigabe-Baustein `alert_gate.py` (vor dem Fetch) |
| `docs/specs/modules/fix_1555_nowcast_alert_priority.md` | NowCast-Vorrang im Tagesbudget (implemented) |
| `docs/specs/fast/verify-1555-nowcast-fix.md` | Verifikations-Mini-Spec — **hier wurde #1628 als Folgefund gebucht** (`af1a1262`) |
| `docs/adr/0021-shared-deviation-alert-engine.md` | EIN geteilter Baustein für Trip + Ortsvergleich |
| `docs/reference/api_contract.md:1074-1160` | Status-Endpoint — Doku unvollständig (`briefing_health`/`warn_service_health`/`forecast_budget` fehlen; Endpoint fehlt ganz in `openapi.yaml`) |

## Verwandte offene Issues

| # | Bezug |
|---|---|
| **#1581** | **Direktes Geschwister:** identische ADR-0018-Lücke für die Gewitter-Direktquellen — „Marker vorhanden, aber kein Health-Signal, Dauerausfall unsichtbar". Gleiche Lösungsform; Doppelarbeit vermeiden. |
| #1348 | MeteoAlarm 429 — „Warn-Dienste ohne Budget/Backoff/Isolation, Ausfall still" (Scheibe 2 von #1337) |
| #1329 (geschlossen) | Radar-Pfad dominiert das Open-Meteo-Kontingent (555 Radar-429 vs. 2 Forecast-429 an einem Tag). Diagnose-Log erfasst Radar **nicht** |
| #1443 | Optional: DWD Radolan/Radvor Nowcast Stufe B |

## Risks & Considerations

1. **🔴 Ursachenkette des Issues ist teilweise widerlegt.** Die Spec darf nicht auf „Bounding-Box-Lücke" aufbauen. Der Umfang muss in der Analyse-Phase neu abgesteckt werden: Sichtbarkeit (sicher) vs. Bounding-Box-Korrektur (vermutlich gegenstandslos) vs. Umgang mit dem All-None-Guard.
2. **🔴 Das `throttled`-Feld ist selbst ein Negativbeispiel** — es hat **null Leser im Produktivcode** (Python wie Go), nur einen Test. Ein zweites Feld nach demselben Muster hinzuzufügen, würde das Problem verdoppeln statt lösen. Die Wirkung muss **am Wirkort** geprüft werden, nicht am Setzort (vgl. Memory „Prüfort muss dem Wirkort entsprechen").
3. **Diagnose 503 vs. 429 ungeklärt.** 429 wäre der Code für Kontingent, 503 spricht für eine Störung bei Open-Meteo. Manueller Nachtest lieferte Minuten später 200. Da `openmeteo_calls.jsonl` den Radar-Pfad nicht erfasst, ist der Radar-Verbrauch heute **gar nicht messbar** — die Diagnose ist ohne den Sichtbarkeits-Fix nicht abschließend zu klären. Das ist ein Argument, Sichtbarkeit zuerst zu liefern.
4. **Pro-Trip-Sichtbarkeit kollidiert mit dem Datenschutz-Design des Status-Endpoints** (#252). Zwei getrennte Orte nötig: aggregiert/anonym im Status-Endpoint, pro Trip im `alert_log.json`.
5. **Nicht in eine Alarm-Verhaltensänderung abrutschen.** Ein Fehlschlag darf **nicht** zu einem Alarm führen (Fehlalarm-Risiko). Der `throttled`-Kommentar hält bewusst fest: „a missed poll beats a quota outage". #1628 fordert **Sichtbarkeit**, nicht mehr Alarme — das muss in den ACs scharf getrennt sein.
6. **Teststrategie:** Es existiert **kein** Test, der einen Open-Meteo-Fehlschlag bis in `check_radar_alerts()` durchreicht. Die Fixture-Mechanik kann Fehlschlag **nicht** von „trocken" unterscheiden (Known Limitation a). Verfügbar ist nur die `_TripwireClient`-Technik (`test_radar_budget_and_priority.py:53-89`), die `GZ_TEST_FIXTURE_DIR` löschen muss — das autouse-Fixture in `tests/conftest.py:18-34` setzt es sonst für jeden nicht-`live`-Test.
7. **LoC-Limit 250** — die Fläche ist groß (Python-Kern + Diagnose-Datei + evtl. Go-Health-Block + Doku). Scheibenschnitt in der Spec-Phase mitdenken.
8. **Doku-Nachzug fällig:** Status-Endpoint fehlt in `openapi.yaml`, `api_contract.md` beschreibt drei von vier Health-Blöcken nicht. Wenn ein neuer Block entsteht, nicht denselben Fehler wiederholen.

---

# Analysis (Phase 2, 2026-08-09)

## Type

**Bug** — Verstoß gegen die bereits akzeptierte Nicht-Kaschieren-Invariante aus ADR-0018.

## Diagnose 503: GEKLÄRT — Open-Meteo-Störung, nicht unser Kontingent

Gemessen am Produktionssystem (`journalctl -u gregor-python.service --since "2026-08-07"`):

| Messgröße | Ergebnis |
|---|---|
| `minutely_15.*failed` 07.–08.08. | **28 Treffer, ausnahmslos `503`, ausnahmslos `models=None`** |
| davon `429` (= Kontingent) | **0** |
| `Provider failed for segment` (Forecast-Pfad) im selben Fenster | **0** |
| `GeoSphere INCA failed` / `Radar-DPC failed` | **0** — bestätigt die stillen `[]`-Pfade |
| Kontingent heute (`/api/scheduler/status`) | `calls_today: 33` / 9000 = **0,37 %** (Drosselschwelle 80 %) |
| 09.08. bis 05:18 UTC | **0 Radar-503** — Ereignis abgeschlossen |
| Koordinaten-Bindung | keine — mehrere Punkte betroffen |

**Urteil:** endpunkt-spezifische Störung bei Open-Meteo. 429 wäre der Code für eigenes Kontingent; es kam ausschließlich 503, und der parallele Forecast-Pfad lief fehlerfrei. **Der Bezug zu #1329 ist damit ausgeräumt.** Die Bounding-Box-Frage aus dem Issue ist gegenstandslos (s. Korrektur oben).

Einschränkung: Nur der Ausschnitt bis 09.08. 05:18 UTC ist gemessen.

## 🔴 Nebenbefund mit Vorrang: vier fest verdrahtete Datenpfade — Beobachtbarkeit prod-weit blind

Beim Nachprüfen der Messung aufgefallen und am laufenden System belegt. **Eigenständiger Fehler, nicht Teil von #1628 — aber Vorbedingung für dessen Lösung.**

Die Produktivdaten liegen seit dem 08.08. unter `/var/lib/gregor` (`GZ_DATA_DIR`, systemd-Env beider Dienste). Commit `ae0553b3` (#1595, gemerged 08.08.) stellte 13 fest verdrahtete Stellen auf `get_data_root()` um und hielt die Inventur für vollständig. **Vier Stellen blieben übrig:**

| Stelle | Datei | Folge |
|---|---|---|
| `src/providers/call_log.py:21` | `openmeteo_calls.jsonl` | gespalten seit 09.08. 05:00 |
| `src/services/official_alerts/warn_egress.py:100` | `warn_service_calls.jsonl` | gespalten seit 08.08. 17:00 |
| `src/providers/openmeteo.py:78` | `openmeteo_calls.jsonl` (zweite Konstante) | s.o. |
| `src/providers/openmeteo.py:204` | `model_availability.json` (**Cache**) | Cache landet außerhalb der Datenwurzel |

Der Python-Kern schreibt seither nach `/home/hem/gregor_zwanzig/data/diagnostics/`, die Go-API liest `/var/lib/gregor/diagnostics/` — **die dortigen Dateien sind eingefroren.**

**Belegt am laufenden `/api/scheduler/status`:**
- `briefing_health.provider_errors_recent_count: 0`, `last_provider_error_at: 2026-08-08T05:00` — obwohl heute 05:00:04 ein `503` auf `/v1/meteofrance` protokolliert wurde (in der Repo-Kopie).
- `warn_service_health.geosphere_warn.last_attempt_at: 2026-08-08T16:01` — obwohl die Repo-Kopie für genau diesen Dienst einen Eintrag von **heute 05:15:00** enthält.

**Damit ist exakt das Health-Signal tot, das ADR-0018 Punkt 3 zwingend vorschreibt.** Ein Anbieter-Dauerausfall bliebe unbemerkt. Zusatzrisiko: `warn_service_calls.jsonl` hat 370.315 Zeilen / 57 MB seit 22.07. (~3,2 MB/Tag) und rotiert nie — jetzt existiert die Datei doppelt.

**Konsequenz für #1628:** Der empfohlene Lösungsweg (Wiederverwendung von `log_warn_service_call`) würde denselben kaputten Pfad erben. Reihenfolge daher: **erst Pfade heilen, dann #1628.**

## Technischer Ansatz für #1628

**EINE Naht statt neun Stellen.** `_derive_result()` (`radar_service.py:525-573`) ist der gemeinsame Konvergenzpunkt aller neun stillen Ausgänge. Begründung: `_fetch_frames_with_fallback` fällt immer bis zum globalen `minutely_15`-Fallback durch, und der liefert bei Erfolg **immer** eine nicht-leere Frame-Liste — auch bei echtem „kein Regen" (dann mit `precip=0`-Einträgen). Ein Cache-Treffer kann nie `[]` sein (`put()` nur `if frames:`, `:202-203`).

⇒ **`frames == []` bedeutet ausschließlich „Datenbeschaffung gescheitert", nie „trocken".** Ein einziger `not frames`-Check in `_derive_result()` erfasst alle neun Ausgänge, ohne `geosphere.py` oder `radar_dpc.py` anzufassen.

🔴 **Diese Kette ist aus dem Code hergeleitet, nicht gemessen.** Sie MUSS der erste RED-Test der Scheibe 1 sein (Tripwire-Technik, `test_radar_budget_and_priority.py:53-89`), nicht als gegeben angenommen werden. Vgl. Memory `feedback_geloestes_problem_als_offenes_risiko_behandelt`.

**Neues Feld** `data_unavailable: bool = not frames` — unbedingt, **nicht** an `_budget_throttled_this_call` gekoppelt. `throttled` bleibt unangetastet (unbekannte Leser).

**Signalweg:** Der bestehende Egress-Kanal wird wiederverwendet, statt einen neuen zu bauen. `warn_service_health.go` aggregiert generisch nach Dienstnamen (kein warn-spezifischer Code) und hängt bereits im Status-Endpoint (`scheduler.go:677`) — ein Eintrag mit `service="radar_nowcast"` erzeugt `last_success_at`/`last_attempt_at`, also **das von ADR-0018 geforderte wachsende Signal, mit null neuen Go-Zeilen und einem Leser ab Tag 1.** Genau das fehlte dem `throttled`-Feld.

Offener Zielkonflikt für die Spec: Modul und Datei heißen „Warn-Dienst-Egress" — fachfremde Mitbenutzung durch Radar vermischt die Zuständigkeit in der Benennung. Alternative: eigene `radar_calls.jsonl` plus parametrisiert extrahierte Go-Aggregation (mehr LoC, sauberer, direkt für #1581 nachnutzbar).

**Verworfen:** Eintrag ins `alert_log.json`. Dort gilt „ein Eintrag = eine Meldung" (Vertrag D1, `AlertCountByEntity()`); ein „Prüfung ohne Daten"-Eintrag würde Alarmstatistiken verfälschen.

## Affected Files (Scheibe 1)

| Datei | Änderung | Beschreibung |
|---|---|---|
| `src/services/radar_service.py` | MODIFY | Feld `data_unavailable` + `not frames`-Check in `_derive_result()`, fail-soft-geschützter Protokoll-Aufruf (~15–25 LoC) |
| `tests/unit/test_radar_data_unavailable.py` | CREATE | Tripwire-Test: (a) Feld gesetzt, (b) Journal-Zeile mit `ok=false`, (c) Alarmausgang **unverändert** (~40–60 LoC) |

**Scope:** 2 Dateien, ~70–100 LoC — sicher unter dem Limit von 250. **Risiko: MEDIUM** (kritischer Alarmpfad, aber rein additiv).

## Risiken

1. 🔴 **Fail-soft ist Pflicht, nicht Kür.** `trip_alert.py:815-822` umschließt `get_nowcast()` mit `try/except: continue`. Ein ungeschützter Protokoll-Schreibversuch würde bei Fehler den **kompletten Alarm-Check des Trips überspringen** — Observability-Code verursacht dann einen echten Alarmausfall. Muss eigene AC werden.
2. 🔴 **Keine Änderung am Alarmverhalten.** `data_unavailable` darf `onset_minutes`, `is_convective` und den Ausgang von `radar_alert_due()` nicht beeinflussen. Ein Fehlschlag darf weiterhin **keinen** Alarm auslösen. Positiver Nachweis nötig („kein Alarm bei reinem Datenausfall"), nicht bloß Abwesenheit einer Verdrahtung.
3. **Dateirechte:** `data/diagnostics/` gehört teils `claude-gregor`. Vor dem ersten Testlauf `sudo -u claude-gregor test -w data/diagnostics` prüfen (Memory `reference_loc_gate_data_dir_permission_phantom_delta`).
4. **Kein zusätzlicher Egress** — reine lokale Datei-I/O, kein Kontingent-Risiko.
5. **Journal-Wachstum** — s. Nebenbefund; Rotation ist Bestandsproblem, kein Auftrag dieser Scheibe.

## Verhältnis zu #1581

**Getrennt lösen, Baustein teilen.** Unterschiedlicher Startzustand: #1581 hat den Daten-Marker bereits und braucht nur das Health-Signal; #1628 hat **weder noch**. Gemeinsam gelöst reißt es das LoC-Budget und vermischt zwei Specs. Geteilt werden kann später die pfad-parametrisierte Aggregation (Go) plus ein generisches `log_service_call()` (Python).

## Empfehlung

1. **Vorziehen:** vier Datenpfade heilen (eigenes Issue, klein, Regression von gestern, blockiert #1628).
2. Dann **Scheibe 1** von #1628: `data_unavailable` + Wiederverwendung des Egress-Journals.
3. **Nicht** mitziehen: #1581, Pro-Trip-Sichtbarkeit, Bounding-Box-Korrektur (gegenstandslos), Journal-Rotation.

## Open Questions (für den PO)

- [ ] Nebenbefund als eigenes Issue anlegen und vorziehen?
- [ ] Signalweg: bestehendes Egress-Journal mitbenutzen (schlank, Leser ab Tag 1, unsaubere Benennung) **oder** eigene `radar_calls.jsonl` (sauberer, mehr LoC, für #1581 nachnutzbar)?
