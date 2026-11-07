# Context: fix-1839-trip-vorschau-kalt-502

## Request Summary
Issue #1839 (Epic #2733, Strang C): Wer den Vorschau-Reiter eines Trips als Erster nach einer
Pause öffnet (kalter Cache), bekommt `502 upstream_unreachable` statt seines Briefings. Der
Python-Core rechnet korrekt weiter, der Go-Weiterleiter hat nach 30 s aufgegeben. Warm: < 1 s.

## Stand vor diesem Workflow (wichtig: nicht bei null anfangen)
Das Ticket ist ein **Restposten** aus der Doppel-Arbeit mit #1765 (Compare-Vorschau):
- **Scheibe A** (live, `0fe1c6e2`, PR #1876): 13 `async def` ohne `await` → `def`, Python-Core
  blockiert während einer Vorschau nicht mehr. Der 502 blieb **ausdrücklich unverändert**.
- **Compare-Seite erledigt:** #1765 ist CLOSED (B1 `098226ae`, B1b `38f4c3e0`,
  `run_comparison_parallel()`).
- **Offen = Scheibe B für den Trip-Pfad:** Parallelisierung der Wetterabrufe der Trip-Vorschau
  plus Nachziehen der Timeout-Leiter. Vorarbeit und Messungen:
  `docs/context/fix-1765-1839-vorschau-laufzeit.md` (Messung 2026-08-15), Spec Scheibe A:
  `docs/specs/modules/fix_1765_1839_sa_vorschau_entblockung.md`.

## Gemessene Ursache (2026-08-15, laut Issue-Kommentar, heute NICHT neu gemessen)
- 502 nach 30,03 s über den Weiterleiter bestätigt; kalt 121,14 s, warm 0,69 s.
- Kalt = 7 Segmentabrufe nacheinander (10,1–25,9 s je), Treiber ist die DWD-Gewitter-
  Anreicherung, nicht der HTTP-Abruf. Null Wiederholversuche im Normalbetrieb.
- Parallel ≈ langsamstes Segment ≈ 26 s = 87 % des 30-s-Budgets, daher Timeout als
  Sicherheitsabstand **zusätzlich**, nicht stattdessen.
- Staging-Auto-Deploy startet `gregor-python-staging` neu und leert den In-Memory-Cache:
  danach ist der erste Aufruf wieder kalt (Messfalle).

## Related Files
| File | Relevance |
|------|-----------|
| `internal/handler/preview_proxy.go:16` | `previewProxyTimeout = 30 s`, Wirkort des 502; gilt für Trip- UND Alarm-Vorschau |
| `internal/handler/preview_proxy.go:24-59` | `forwardPreview`: baut `http.Client{Timeout}`, mappt Fehler auf 502 `upstream_unreachable` |
| `internal/handler/briefing_preview.go:46` | zweiter Aufrufer von `forwardPreview` mit `previewProxyTimeout` |
| `internal/handler/proxy.go:15-30` | Zeitgrenzen-Kette: `sendProxyTimeout` 300 s, `nginxProxyReadTimeout` 330 s (Spiegel), `stagesWeatherProxyTimeout` 120 s |
| `internal/handler/proxy_timeout_chain_test.go` | bestehender Wächter der Kette (Konstanten + Wirkort-Test über kurz gesetzte `var`) |
| `internal/router/router.go:281,285` | Routen Alert-Vorschau und `/api/preview/{trip_id}/sms` |
| `src/services/preview_service.py:190` | Hauptabruf `scheduler._fetch_weather(segments)` (serielle Segmente) |
| `src/services/preview_service.py:235-241` | `fetch_night_weather(...)` (Nachtwetter, ca. 24,6 s) |
| `src/services/preview_service.py:256` | `_build_stage_trend()` → eigener Abruf (+1/+2 Tage), teilt sich Code mit Versand (`trip_report_scheduler.py:1398`) |
| `src/services/preview_service.py:~270` | `_build_thunder_forecast_from_trend_or_fetch` (weiterer Abrufpfad) |
| `src/services/trip_report_scheduler.py:2659,2904,3114` | `_fetch_weather` (6 Aufrufer, 4 im Versand/Alarm), `_build_stage_trend`, Thunder-Fallback |
| `src/services/stage_weather.py:14,53,171-180` | **Präzedenzfall** Parallelisierung: `ThreadPoolExecutor(max_workers=min(len, 8))`, indexierte Vorbelegung, Fehler-Wrapper je Segment |
| `src/services/compare_preview_service.py` | Compare-Pendant, bereits parallel (`run_comparison_parallel`) |
| `src/providers/call_log.py`, `src/utils/timezone.py` | Thread-Sicherheit: `ContextVar`-Quelle, Lock um `_tf_instance` (aus B1 laut Vorarbeit schon bzw. noch zu prüfen) |

## Existing Patterns
- Parallelisierung **außen**, nur im Vorschau-Pfad (Variante V3 aus der Vorarbeit): `_fetch_weather`
  selbst bleibt unangetastet, weil Versand und Alarme sonst mitwandern und die
  `[triage:po]`-Entscheidung aus #1539 vorweggenommen würde.
- Reihenfolge: indexierte Vorbelegung statt Append; Fehler eines Segments reißt nicht alle mit.
- Parallelitätsgrad als benannte Konstante, niedriger als das Vorbild (Météo-France 100 Anfragen/min
  gemeinsames Konto, `docs/reference/decision_matrix.md:229-247`).
- Zeitgrenzen-Kette Python < Go-Client < nginx, Wirkort-Test über Paket-`var` (#2124).

## Dependencies
- Upstream: DWD-/Open-Meteo-/Météo-France-Provider, Wetter-Cache (prozessweit, In-Memory), Zeitzonen-Lookup.
- Downstream: Trip-Vorschau-Reiter im Frontend, Alarm-Vorschau (teilt `previewProxyTimeout`),
  Staging-Specs, die die SMS-Vorschau als Messweg nutzen.

## Existing Specs
- `docs/specs/modules/fix_1765_1839_sa_vorschau_entblockung.md` (Scheibe A)
- `docs/specs/modules/fix_1765_b1_compare_vorschau_parallel.md`, `fix_1765_b1b_versand_sofortvergleich_parallel.md`
- `docs/specs/modules/fix_2124_versand_nginx_timeout.md` (Zeitgrenzen-Kette)

## Risks & Considerations
- **Heutiger Stand ungemessen:** Die Messung ist 12 Wochen alt; seitdem wurden Vorschau-Reiter
  (#1743, #2283), Nutzer-Kontingent (#2387) und Nachtfenster (#2223) geändert. Vor der Spec auf Staging
  kalt neu messen (nach Neustart oder mit leerem Cache), sonst baut die Spec auf alten Zahlen.
- **Drei Aufrufstellen, nicht eine:** Hauptabruf, `_build_stage_trend`, Nachtwetter. Parallelisiert man nur
  eine, bringt es nichts (Befund der Vorarbeit). `_build_stage_trend` ist mit dem Versand geteilt, der
  Zuschnitt muss „außen" bleiben.
- **Nebenläufigkeit:** `call_log`-Quelle unter Threads, `_tf_instance`-Lock, Cache-Stampede bei gleichzeitigem
  Miss (bekannt, offen, bewusst nicht Teil dieses Tickets).
- **Timeout:** Anheben muss unter nginx 330 s bleiben und `proxy_timeout_chain_test.go` fortschreiben;
  `previewProxyTimeout` gilt auch für die Alarm-Vorschau.
- **Rückbau-Pflicht aus dem Ticket:** Der Aufwärmlauf im E2E-Test (bis zu 8 Versuche im `beforeAll`) ist
  eine Umgehung. Die Datei `frontend/e2e/trip-preview-thunder-origin.spec.ts` ist im Arbeitsbaum **nicht
  mehr auffindbar** (Suche nach `thunder-origin`/Aufwärm in `frontend/e2e`, `frontend/tests`, `tests/e2e`
  ohne Treffer). Zu klären, ob der Aufwärmlauf entfallen ist oder anderswo steht.
- **Einordnung #1539:** Die Wurzel (sequenzielle Orts-/Etappenverarbeitung, Scheduler-Überlappung) bleibt
  getrennt; dieses Ticket löst nur den Trip-Vorschau-Teil und soll #1539 nicht vorwegnehmen.

## Offene Fragen für /20-analyse
1. Kalt neu messen: Wie lange braucht die Trip-Vorschau heute, und aus welchen Schritten besteht sie?
2. Passen Hauptabruf, Trend und Nachtwetter in **einen** gemeinsamen Pool, oder sind mehrere Umbauten nötig?
3. Reicht Parallelisierung unter 30 s, oder muss `previewProxyTimeout` zusätzlich steigen (und auf welchen Wert)?
4. Wo steht der Aufwärmlauf heute, und was ist beim Rückbau zu tun?
5. Nutzersicht bei Restlatenz: ehrliche Rückmeldung („Vorschau wird berechnet…") als Ergänzung oder Nicht-Ziel?

## Analysis

### Type
Bug (nutzersichtbar: erster Aufruf des Vorschau-Reiters nach Pause endet in 502).

### Neue Befunde (korrigieren den Stand oben)
1. **Die „serielle" Ausgangslage stimmt nicht mehr.** Seit #1539/#2439 (Okt 2026) laufen
   `_fetch_weather` (`trip_report_scheduler.py:2689`, `fetch_ordered`) und die Trend-Etappen
   (`_build_stage_trend` → `_abrufe_fuer_etappen`) bereits parallel. Scheibe B ist damit zum großen
   Teil ohne dieses Ticket geliefert. **Die Messung vom 15.08. (121 s) ist veraltet**, heutige
   Kaltzeit ungemessen.
2. **Die Parallelität ist gedeckelt:** Slot-Semaphore `open_meteo` = 3 (`parallel_fetch.py:41`),
   der Slot umspannt die ganze Aufgabe samt DWD-Gewitter-Anreicherung. Bei ~8 Abrufen à 10–26 s
   ist kalt mit Größenordnung 45–75 s zu rechnen (Schätzung, nicht gemessen). Die Hoffnung „≈ 26 s,
   87 % des Budgets" aus dem Issue-Kommentar ist damit **nicht belastbar** — Parallelisierung allein
   bringt die Vorschau voraussichtlich nicht unter 30 s.
3. **Echt noch seriell** im Vorschau-Pfad (`preview_service.py:_build_report`): Nachtwetter
   (`fetch_night_weather`, ~25 s, wartet auf `segment_weather[-1]`) läuft NACH dem Hauptabruf und VOR
   dem Trend; Trend ist von beidem unabhängig und könnte gleichzeitig laufen. Der Thunder-Fallback
   (`_build_thunder_forecast_from_trend_or_fetch`) hängt von Trend + Nachtwetter ab und bleibt danach.
4. **Wirkort des 502:** `internal/handler/preview_proxy.go:16` `previewProxyTimeout = 30 s`
   (Aufrufer: `proxy.go:332` Alarm-Vorschau, `briefing_preview.go:46`). nginx läuft in `location /api/`
   mit 330 s, Versand 300 s, Wetter-Lesen 120 s — die 30 s sind der einzige zu enge Wert der Kette.
5. **Aufwärmlauf-Rückbau:** `frontend/e2e/trip-preview-thunder-origin.spec.ts` existiert im Repo
   nicht mehr (`git ls-files` ohne Treffer). Nichts zurückzubauen; im Ticket-Abschluss vermerken.

### Affected Files (with changes)
| File | Change Type | Description |
|------|-------------|-------------|
| `internal/handler/preview_proxy.go` | MODIFY | `previewProxyTimeout` 30 s → 120 s, als Paket-`var` (wie `stagesWeatherProxyTimeout`), Kommentar zur Kette |
| `internal/handler/proxy_timeout_chain_test.go` | MODIFY | Wirkort-Test für Vorschau-Timeout (kurz gesetzte `var`, 502 erst danach) + Kettenregel < nginx 330 s |
| `src/services/preview_service.py` | MODIFY | Trend und Hauptabruf+Nachtwetter gleichzeitig starten (eigener Thread mit `copy_context`, NICHT im gemeinsamen Pool: dort liefe der innere Abruf inline seriell); `_fetch_weather`/`_build_stage_trend` bleiben unangetastet |
| `tests/…` (neu, nach Verhalten benannt) | CREATE | Nachweis: Trend und Nachtwetter überlappen zeitlich; Reihenfolge/Ergebnis unverändert; Fehler eines Zweigs reißt den anderen nicht mit |
| `docs/specs/modules/fix_1839_trip_vorschau_kalt.md` | CREATE | Spec mit ACs |
| Frontend-Vorschau-Reiter (Komponente noch zu lokalisieren: `shared/layout-tab`/Vorschau-Reiter) | MODIFY (optional) | Ladezustand „Vorschau wird berechnet…" |

### Scope Assessment
- Files: 4–6 · Estimated LoC: +120/-10 (Go klein, Python ~40, Tests Rest)
- Risk Level: MEDIUM — Threads im Vorschau-Pfad (call_log-Quelle, `_tf_instance`-Lock, Kontingent je Nutzer
  #2387, Cache-Stampede bei gleichzeitigem Miss); Timeout-Anhebung betrifft auch die Alarm-Vorschau.

### Technical Approach (Empfehlung)
Zwei Maßnahmen, beide nötig, weil Befund 2 zeigt, dass eine allein nicht reicht:
1. **Timeout-Leiter zuerst und sicher:** `previewProxyTimeout` auf 120 s (= Wert für Wetter-Lesen, deutlich
   unter nginx 330 s). Das beseitigt den 502 sofort und unabhängig von der Messung.
2. **Beschleunigung außen:** Trend nebenläufig zu Hauptabruf+Nachtwetter. Mehr ist nicht nötig; weiteres
   Parallelisieren stößt am Slot-Deckel 3 an (Anheben berührt das gemeinsame Open-Meteo-Kontingent → nicht
   Teil dieses Tickets, Bezug #1539).
3. **Rückmeldung bei Restlatenz** (Frage 5): Ladezustand „wird berechnet…" im Vorschau-Reiter. Empfehlung:
   in den Scope, klein, aber erst nach Lokalisieren der Komponente; wenn sie geteilte Trip/Vergleich-Organismen
   berührt, EIN Code (PO-Vorgabe Teilung).

Nicht empfohlen: Vorwärmen beim Seitenöffnen (zusätzliches Kontingent, Verfall bei Neustart, löst nur den Zufallsfall).

### Dependencies
Provider/Cache/Zeitzone wie oben; `parallel_fetch` (Pool + Slots), Frontend-Vorschau-Reiter, Alarm-Vorschau (teilt Timeout).

### Open Questions
- [ ] **Kaltmessung heute fehlt.** Vorschlag: in Phase 5/E2E auf Staging vorher/nachher messen (frisch gestarteter Python-Prozess =
      kalter Cache; kostet Open-Meteo-Kontingent). Die Spec nennt deshalb KEINE Sekundenzusage, sondern „kein 502 bei kaltem Cache
      innerhalb 120 s" und eine Obergrenze, die nach Messung kalibriert wird.
- [ ] Ladezustand im Frontend: in Scope oder eigenes Ticket? (Empfehlung: in Scope, wenn nur eine Stelle.)
