# Context: fix-2286-compare-betrieb-health

Issue #2286 · Epic #2345, Etappe P4 (nach #2280, #2281) · Stand HEAD `7c05d534e` (2026-10-21)

## Request Summary

Der Ortsvergleich-Versand soll dieselbe Betriebs-Beobachtbarkeit bekommen wie der Trip-Versand: Totalausfall-/Recovery-Meldung, Korrupt-Zähler in `briefing_health`, gleiche Status-Felder je Sub-Job; `smtp_guard`-Unterschied und Job-Zuschnitt amtliche Warnungen angleichen oder begründen.

## Related Files

| File | Relevance |
|------|-----------|
| `internal/scheduler/scheduler.go:782-816` | `tripReports()` — Flankenlogik über `lastHardStatus` (Feld `:143-155`, Init `:302`), MQ „Trip-Briefing-Totalausfall (#1346)" / „wieder OK" |
| `internal/scheduler/scheduler.go:976-981` | `comparePresetsDaily()` — nur `recordRun`, keine Flanke. Aufruf aus `briefingDispatch()` `:751-769` (Heartbeat nur wenn beide Sub-Jobs ok) |
| `internal/scheduler/scheduler.go:1115-1188, 396-480` | `triggerEndpointForUser` / `runForAllUsers` — „error" = HTTP≥400, Transportfehler, `failed>0`; Rangfolge error > partial > ok |
| `internal/scheduler/scheduler.go:860-900` | `dataWriteSelftest()` — zweite Vorlage für Flankenmeldung |
| `internal/scheduler/scheduler.go:1395-1460` | `Status()` — Zeilen je Job; `briefing_health` bei `:1454` |
| `internal/scheduler/briefing_health.go:67-223, 479-511, 424-470` | Felder von `briefing_health`; `aggregateCorruptTrips` (glob `users/*/diagnostics/corrupt_trips.json`); Dispatch-Failures aus `briefing_dispatch_failures.jsonl` |
| `api/routers/scheduler.py:54-90 / 261-275` | Antwort Trip `{status,count,failed,duration_s}` vs. Compare `{status,count,failed}` |
| `src/app/loader.py:309-360` | `load_compare_presets` — Parse VOR kind-Filter; `strict=True` wirft `LoaderError` |
| `src/services/scheduler_dispatch_service.py:47-71, 724, 742, 825` | Compare-Dispatch: `LoaderError` → ERROR-Log, `None` → `(0,0)` → Go sieht „ok"; Failure-Log mit `kind="vergleich"`; `send_lock` |
| `src/services/trip_report_scheduler.py:440-517, 662` | `record_corrupt_trip_observability` → `diagnostics/corrupt_trips.json` `{notified, last_skipped_count, last_run}`, MQ-Dedup per Dateiname |
| `src/services/dispatch_orchestrator.py:45, 108-120, 240` | `smtp_guard` Trip=True / Compare=False (Docstring: „per-Preset statt global", Altverhalten aus #1207) |
| `src/services/compare_slot_scheduler.py:137` | Compare-Fälligkeit nur Stundengleichheit, kein Pending (#1777) |
| `internal/store/compare_preset.go:123-171` | Go überspringt kaputte Presets mit `log.Printf` |
| `/home/hem/henemm-infra/scripts/check-gregor20.sh` | Externer Konsument — siehe Risiken |

## Existing Patterns

- **Flanke:** vorherigen Status lesen → Lauf → bei Wechsel nach error MQ `high` an `infra`, bei error→ok MQ `normal`; `partial` überschreibt den gespeicherten Status nicht (`tripReports()`).
- **Korrupt-Beobachtbarkeit:** Python schreibt pro Nutzer `diagnostics/*.json` (nur Zahlen/Zeitstempel/Dateinamen zur Dedup), Go aggregiert per Glob über `users/*/` und gibt nur Summen + jüngsten Zeitstempel aus (Datenschutz #252).
- **Nutzer-Flankenalarme (#2149)** gelten bereits für beide Sub-Jobs (`sendBundledUserAlerts` `:713-740`, `fanOutJobIDs` `user_run_state.go:320-328`); es fehlt nur der Job-weite Alarm.
- `briefing_dispatch_failures.jsonl` trägt schon `kind` (`route|vergleich`); `briefing_log.json` (#2281) nutzt `entity_type` `trip|compare` und enthält nur Erfolge.

## Dependencies

- Upstream: Python-Endpoints `/api/scheduler/trip-reports` + Compare-Pendant, `load_compare_presets`, MQ-Notifier, Datenablage `data/users/<id>/`.
- Downstream: `GET /api/scheduler/status` (`router.go:314`, `statusGuard`/`GZ_STATUS_TOKEN`) → `check-gregor20.sh` (liest `jobs[].last_run.*`, `deadline_aborts`, `SOFORT_ALARM_JOBS={trip_reports_hourly, compare_presets_daily}` `:185`, sowie `briefing_health`-Felder `open_pending_*`, `degraded_segments_total`, `provider_error_*`, `track_resolution_*`, `alert_anchor_rejected_*`, `briefing_dispatch_error_*`; **nicht** `corrupt_trips_*`). BetterStack-Heartbeat via `briefingDispatch()`.

## Existing Specs

- `docs/specs/modules/compare_dispatch_observability_telegram_guard.md` (#1290)
- `docs/specs/modules/dispatch_orchestrator.md` (`:94, :285` smtp_guard)
- `docs/specs/modules/fix_1912_scheduler_briefing_timeout.md`, `fix_1447_s2a_scheduler_ueberlappung_teilerfolg.md`, `fix_2149_scheduler_nutzer_sichtbarkeit.md`, `fix_2149_scheduler_budget_teilb.md`, `scheduler_multi_user.md`, `trip_report_scheduler.md`, `fix_1629_briefing_anker_versandfehler.md`, `compare_preset_zeitplan.md`, `feat_2281_vergleich_versand_historie.md`
- ADRs: `0018-provider-fallback-ohne-kaschieren.md`, `0023-briefing-subscription-shared-model.md`

## Existing Tests

- Go: `internal/scheduler/timeout_kein_ausfall_test.go:84-589` (Trip-Flanke/Recovery), `scheduler_test.go:714,745` (Compare-Heartbeat), `scheduler_unify_test.go:232`, `user_failure_alarm_test.go`, `briefing_health_test.go:548,578`, `scheduler_status_privacy_test.go`
- Python: `tests/tdd/test_scheduler_corrupt_trip_observability.py`, `test_scheduler_corrupt_trip_wiring.py`, `test_corrupt_trip_state_atomic_write.py`, `test_compare_preset_loader.py:172,278,305`, `test_dispatch_orchestrator.py:310`, `test_compare_dispatch_failed_tally.py`, `test_briefing_sammellauf_einheit_abschottung.py:116`, `tests/test_dispatch_status_delivery.py`, `test_briefing_slot_idempotenz.py`

## Key Findings (für /20-analyse)

1. **Stiller Totalausfall bei kaputter Datei (schwerster Befund):** Eine einzige kaputte JSON-Datei in `briefings/` — auch ein Trip — lässt `load_compare_presets(strict=True)` werfen; der Dispatch liefert `(0,0)`, Go meldet „ok". Alle Vergleiche dieses Nutzers fallen still aus. Test `test_compare_preset_loader.py:305` schreibt `(0,0)` heute fest.
2. **Kaputtes JSON zählt heute schon als „corrupt trip"** (kind nicht lesbar). AC-2 „kind=vergleich" verlangt eine Klassifizierungsregel für unparsbare Dateien — Doppelzählung (trip + vergleich) vermeiden.
3. Gültiges JSON mit kaputter Struktur wird nirgends gezählt.
4. Status-Struktur je Job ist bereits gleich; Unterschied ist nur inhaltlich (`duration_s` aus Body, `deadline_aborts` immer 0 bei Compare). AC-3 ist also weitgehend ein Schema-Test plus Body-Angleichung.
5. „error" bedeutet in Go „mindestens ein Nutzer mit `failed>0`", nicht „alle". Die Trip-MQ heißt trotzdem „Totalausfall" — dieselbe Semantik für Compare übernehmen, nicht neu erfinden.
6. `smtp_guard=False` bei Compare ist dokumentiert (per-Preset statt global). Trip-Variante gibt bei fehlendem SMTP still `(0,0)` → das ist eher beim Trip fragwürdig. Entscheidung „angleichen oder begründet lassen" gehört in die Analyse.

## Risks & Considerations

- **Monitoring-Vertrag:** Feldnamen, die `check-gregor20.sh` liest, nicht umbenennen; neue Felder nur ergänzen. `corrupt_trips_*` bleibt aus Kompatibilitätsgründen bestehen (falls kind-neutral ergänzt wird: zusätzlich, nicht stattdessen).
- **Alarm-Lautstärke:** Wird der kaputte Ladefall künftig als `failed` gezählt, schlägt `SOFORT_ALARM_JOBS` sofort an — gewollt (kein stilles Verwerfen), aber spürbare Verhaltensänderung; bricht `test_compare_preset_loader.py:305`.
- **Doppelmeldung:** Job-weite Compare-Flanke + #2149-Nutzeralarm = zwei Meldungen pro Störung (beim Trip heute identisch).
- **Datenschutz/Mandanten:** Aggregate nur Zahlen + Zeitstempel, keine IDs/Dateinamen in `/status`; Dedup-State pro Nutzer, eigene Datei oder `kind`-Feld.
- **Infra-Gegenstück:** Falls `check-gregor20.sh` neue Felder auswerten soll → Änderung in `henemm-infra` (Arbeitsbaum dort ist sofort live).
- Pending/Nachlieferung für Compare ist #1777 — nicht in diesen Umfang ziehen, nur abgrenzen.
- Amtliche-Warnungen-Job-Zuschnitt: berührt #2258/#2261 — Umfang in der Analyse klären. → geklärt: #2258/#2261 behandeln den Zuschnitt nicht; er gehört in dieses Ticket (siehe Analysis).

## Korrekturen zur Kontextsammlung (verifiziert in /20-analyse)

- **Befund 2 korrigiert:** `record_corrupt_trip_observability` (`trip_report_scheduler.py:473-482`) zählt jede **unparsbare** Datei in `briefings/` schon kind-neutral. Er läuft im Trip-Lauf je Nutzer, also auch für reine Vergleichsnutzer: Go `runForAllUsers` ruft `/trip-reports?user_id=` auf, ohne early-return. Der MQ-Betreff lautet aber „Kaputter Trip“. Eine unparsbare Vergleichs-Datei wird also schon heute gezählt, nur falsch etikettiert. Ein **parsbares** Vergleichs-Preset mit kaputter Struktur zählt dagegen nirgends, weil kind=vergleich vor `load_trip` übersprungen wird.
- Die Zeilenangaben im Issue (`scheduler.go:331-367`, `:522-527`) sind veraltet. Stand HEAD: `tripReports()` `:782-816`, `comparePresetsDaily()` `:976-981`.
- `compare_presets_daily` ist bereits ein Fan-out-Job (`user_run_state.go:320-328`, `budgetsFor` `scheduler.go:487`). `deadline_aborts` wird ausgegeben, ist bei Compare aber praktisch immer 0, weil der Body kein `reason` trägt.
- Der festschreibende Test steht bei `tests/tdd/test_compare_preset_loader.py:303-327`, nicht bei :305. Er erwartet `(0,0)` und ein ERROR-Log bei `{not valid json`.
- `briefingDispatch()` ruft beide Sub-Jobs **strikt nacheinander** auf (`scheduler.go:751-769`). Es gibt also keine gleichzeitigen Schreiber.
- Trips und Compare-Presets liegen im **selben** Verzeichnis `briefings/<id>.json` (`internal/store/briefing_subscription.go`). Es gibt kein Präfix und keinen Index. Die Art steht nur im Feld `kind`.

## Analysis

### Type
Bug (Beobachtbarkeitslücke: Vergleichs-Versand fällt still aus)

### Ursachen (verifiziert)

1. **Stiller Totalausfall durch eine kaputte Datei.** `load_compare_presets(strict=True)` (`loader.py:345-357`) wirft beim ersten unparsbaren JSON im gemeinsamen `briefings/`. Das gilt auch, wenn die kaputte Datei ein Trip ist. Die Kette danach:
   - `_load_presets_for_dispatch` (`scheduler_dispatch_service.py:47-71`) gibt `None` zurück.
   - `collect_due` liefert `[]` (`dispatch_orchestrator.py:146-147`), das Ergebnis ist `(0,0)` und `status:"ok"`.
   - Folge: **alle** Vergleiche dieses Nutzers fallen aus, und Go sieht „ok“.

   Der Trip-Pfad überspringt dagegen nur die kaputte Datei (`loader.py:1666-1675`).
2. **Keine Job-weite Flanke.** `comparePresetsDaily()` macht nur `recordRun`. Die Trip-Flanke steckt inline in `tripReports()`: eine `lastHardStatus`-Map, MQ high „Totalausfall“, MQ normal „wieder OK“, und `partial` überschreibt den gespeicherten Status nicht.
3. **Provider-Totalausfall im Cron gilt als „sent“.** In `send_one_compare_preset` (`scheduler_dispatch_service.py:566-585`) landen Fehler an einzelnen Orten in `lr.error`, gerendert und versendet wird trotzdem. Nur der Handversand macht per `weather_failure_as_outcome` aus „alle Orte fehlerhaft“ ein `no_weather`. Ohne Änderung kann die Flanke im Motiv-Szenario des Issues („Provider-Störung“) also **nie** feuern. Sendefehler bei E-Mail (Exception) und Fehler der Fälligkeitsprüfung kommen dagegen schon heute als `failed>0` an (`test_compare_dispatch_failed_tally.py`).
4. **Korrupt-Etikett.** Wie oben korrigiert: unparsbare Dateien werden als „Trip“ gemeldet, strukturell kaputte Vergleichs-Presets gar nicht.
5. **Body:** Compare liefert `{status,count,failed}`, Trip zusätzlich `duration_s`.
6. **smtp_guard:**
   - Trip steht auf `True`. Ohne SMTP liefert er still `(0,0)` (`dispatch_orchestrator.py:240-241`). `can_send_email` verlangt host, user, pass und mail_to (`config.py:349`).
   - Compare steht auf `False`. Gezählt wird pro Preset (#1207, Spec `dispatch_orchestrator.md:94`).
   - CI hat kein SMTP konfiguriert, Staging schon.
7. **Job-Zuschnitt amtliche Warnungen:** Beim Trip laufen die amtlichen Warnungen **im** `alert_checks`-Job mit (`trip_alert.py:495`). Compare hat dafür einen **eigenen** Job `compare_official_alert_checks` neben `compare_alert_checks` (`scheduler.go:343-356`, Handler `:820-854`). `check-gregor20.sh:865` führt alle drei IDs in `ALARM_JOB_IDS`.

### Tech-Lead-Entscheidungen (begründet)

| Thema | Entscheidung | Begründung |
|---|---|---|
| Schnitt | **Ein Workflow** für alle Punkte des Zielbilds. Bei Bedarf `loc_limit_override 500`. | Regel: Epics werden themenweise abgeschlossen, Reste werden nicht abgespalten. Das LoC-Limit zählt nur produktive Dateien. |
| Kaputte Datei im Compare-Lauf | Der Loader wird im Dispatch **tolerant**: kaputte Datei überspringen, die übrigen laden, WARN-Log. Das zählt **nicht** als `failed`. | Parität zum Trip. Eine fremde kaputte Datei darf nicht alle Vergleiche eines Nutzers abschalten. Sichtbar bleibt sie über den Korrupt-Zähler und die MQ-Meldung, nicht über `SOFORT_ALARM_JOBS`. |
| Korrupt-Zählung | Es bleibt bei **einem** Scanner und **einem** Dedup-Stand, dem bestehenden in `record_corrupt_trip_observability`, nur verallgemeinert:<br>• Er klassifiziert jede Datei als `trip`, `vergleich` oder `unbekannt`.<br>• Parsbare Vergleichs-Presets prüft er zusätzlich strukturell (`compare_preset_from_dict`).<br>• `corrupt_trips.json` bekommt **zusätzlich** das Feld `by_kind`, die alten Felder bleiben.<br>• Der MQ-Betreff richtet sich nach der Art. | Keine zweite Datei und keine zweite `notified`-Liste, also keine doppelte Meldung. Die Sub-Jobs laufen nacheinander. Der Scanner läuft schon heute für alle Nutzer. |
| Art einer unparsbaren Datei | Rohtext-Heuristik: das Muster `"kind"\s*:\s*"vergleich"` ergibt `vergleich`, sonst `unbekannt`. | Trips und Vergleiche liegen im selben Ordner, und es gibt keinen Index. `briefing_log.json` kennt nur Entitäten, die schon einmal versendet wurden. Ein ehrliches `unbekannt` ist besser als Raten. |
| Go `briefing_health` | **Zusätzlich** `corrupt_briefings_total` und `corrupt_briefings_by_kind{trip,vergleich,unbekannt}`, nur als Zahlen. `corrupt_trips_*` bleibt unverändert. | Der Monitoring-Vertrag wird nur erweitert. Datenschutz #252. |
| Flanke | Ein Helper wird aus `tripReports()` herausgezogen und bekommt jobID, Betreff und Texte als Parameter. Beide Sub-Jobs nutzen ihn. Compare-Texte: „Vergleichs-Briefing-Totalausfall (#2286)“ und „Vergleichs-Briefing wieder OK (#2286)“. `dataWriteSelftest` bleibt unberührt. | EIN Code für beide Arten (Teilungsregel). |
| Bedeutung von „error“ | Wie beim Trip: mindestens ein Nutzer mit `failed>0`. | Keine neue Semantik erfinden. |
| Provider-Totalausfall im Cron | Der Cron wendet dieselbe Regel an wie der Handversand: Haben alle Orte keine Daten, ergibt das `no_weather` und wird als `failed` gezählt. Es geht dann keine Mail aus lauter Fehlerzellen raus. | Ohne diese Regel ist AC-1 für sein eigenes Motiv nicht erreichbar. ADR-0018: Fallback nicht kaschieren. Hand und Cron verhalten sich danach gleich. |
| Doppelmeldung | Die Job-weite Flanke **und** der #2149-Nutzeralarm gehen beide raus, wie beim Trip. Das wird in der Spec festgehalten. | Die beiden Meldungen haben verschiedene Empfänger: infra und den Nutzer. |
| `duration_s` | Der Compare-Body ergänzt `duration_s`. AC-3 wird über einen Go-Schema-Test geprüft. | Gleicher Body für beide Sub-Jobs. |
| smtp_guard | Der **Unterschied bleibt**, die Begründung kommt in den Code. Der Trip-Guard schreibt künftig ein WARNING-Log, statt still zu bleiben. | Compare versendet pro Preset an die Empfänger des Nutzers, Fehler zählen dort als `failed`. Der Trip-Guard prüft die globale SMTP-Konfiguration. Fehlt sie, ist das ein Deploy-Fehler, den `/api/health` und `prod_selftest` fangen. „kein SMTP ⇒ failed“ würde `test_dispatch_orchestrator.py:310-348` brechen, CI hat kein SMTP. |
| Job-Zuschnitt amtliche Warnungen | **Angleichen an das Trip-Muster:**<br>• `compare_official_alert_checks` geht in `compare_alert_checks` auf.<br>• Der Endpoint führt beide Services nacheinander aus, jeden mit eigenem try, und summiert count/failed.<br>• Go-Job und Handler `compare_official_alert_checks` fallen weg. | Zielbild „nicht gemischt“. Das Falten ist der kleinere Weg, etwa 30 LoC. Den amtlichen Teil beim Trip herauszulösen wäre deutlich größer. Die Fehlerisolation bleibt durch die getrennten try-Blöcke erhalten. |
| Infra-Gegenstück | In `check-gregor20.sh:865` fliegt `compare_official_alert_checks` aus `ALARM_JOB_IDS`. Das macht diese Instanz selbst, **infra zuerst**. | Ohne diese Änderung meldet der Monitor nach dem Deploy einen fehlenden Job. |
| Abgrenzung | `open_pending{kind}` für Compare bleibt bei #1777. | Compare kennt strukturell kein Pending. |

### Affected Files (with changes)

| File | Change Type | Description |
|------|-------------|-------------|
| `internal/scheduler/scheduler.go` | MODIFY | Flanken-Helper; `tripReports()` und `comparePresetsDaily()` nutzen ihn; Job und Handler `compare_official_alert_checks` entfernen |
| `internal/scheduler/briefing_health.go` | MODIFY | `by_kind` aggregieren → `corrupt_briefings_total`, `corrupt_briefings_by_kind` |
| `src/services/trip_report_scheduler.py` | MODIFY | Scanner: Art klassifizieren (Rohtext-Heuristik), Vergleichs-Struktur prüfen, `by_kind` schreiben, MQ-Betreff je Art |
| `src/services/scheduler_dispatch_service.py` | MODIFY | Tolerantes Laden im Dispatch; Cron: alle Orte fehlerhaft → `no_weather` → failed |
| `src/app/loader.py` | MODIFY (ggf.) | toleranter Modus für `load_compare_presets` |
| `src/services/dispatch_orchestrator.py` | MODIFY | Begründungs-Kommentar zu smtp_guard; WARNING-Log beim Trip-Guard |
| `api/routers/scheduler.py` | MODIFY | Compare-Body bekommt `duration_s`; `compare-alert-checks` führt auch den Official-Service aus; der Official-Endpoint entfällt |
| `/home/hem/henemm-infra/scripts/check-gregor20.sh` | MODIFY (infra) | ID aus `ALARM_JOB_IDS` entfernen |
| `tests/tdd/test_compare_preset_loader.py` | MODIFY | `:303-327` auf „übrige Presets laufen, kaputte Datei übersprungen“ umstellen |
| Go- und Python-Tests | CREATE | Compare-Flanke (Totalausfall, Recovery, partial), Status-Schema-Parität, Korrupt-`by_kind`, Cron-Provider-Totalausfall → failed, gefaltete Alarm-Jobs mit Fehlerisolation |
| `docs/specs/modules/dispatch_orchestrator.md`, `scheduler_multi_user.md`, `docs/reference/api_contract.md` | MODIFY | Doku nachziehen |

### Scope Assessment
- Files: ~8 produktiv, das Infra-Skript und ~5 Testdateien
- Estimated LoC (produktiv): ~+190/-60
- Risk Level: **MEDIUM**. Betroffen sind der zentrale Versandpfad und der Monitoring-Vertrag. Dazu kommt eine sichtbare Verhaltensänderung: Bei einem Provider-Totalausfall geht keine Vergleichs-Mail mehr raus, stattdessen kommt eine Meldung.

### Dependencies / Reihenfolge
1. Python: toleranter Loader, Cron-Provider-Regel, Scanner `by_kind`, Body `duration_s`, gefaltete Alarm-Endpoints
2. Go: Flanken-Helper, Aggregat, Job-Entfernung
3. Infra: ID aus `check-gregor20.sh` entfernen, vor dem Prod-Deploy
4. Staging: Wegwerf-Nutzer mit kaputtem Preset bzw. unauflösbaren Orten anlegen, dann `/status` mit `X-GZ-Status-Token` lesen

### Präzisierungen der Issue-ACs (für /30)
- **AC-1:** „scheitert für alle fälligen Presets“ schließt den Provider-Totalausfall ein, also alle Orte ohne Daten. Ausgelöst wird wie beim Trip, sobald mindestens ein Nutzer `failed>0` hat.
- **AC-2:** Wie kaputte Dateien gezählt werden:
  - Kaputtes JSON mit erkennbarem `kind:"vergleich"` zählt als `vergleich`, ohne erkennbare Art als `unbekannt`.
  - Ein strukturell kaputtes Vergleichs-Preset zählt als `vergleich`.
  - Die übrigen Vergleiche des Nutzers werden weiter versendet.
- **AC-3:** Beide Sub-Jobs haben in `/status` und im Python-Body dieselbe Feldmenge.
- **Neue ACs:** Job-Zuschnitt der amtlichen Warnungen (ein Job je Art, Fehlerisolation); Begründung für smtp_guard plus WARNING-Log.

### Open Questions
- Keine PO-Fragen. Die technischen Entscheidungen sind oben begründet, die ACs gibt der PO in `/30` frei.
