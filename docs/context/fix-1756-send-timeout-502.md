# Context: fix-1756-send-timeout-502

## Request Summary
Der manuelle Sendeknopf im Trip-Editor (`POST /api/trips/{id}/send`) liefert nach ~60s einen 502
im Browser, obwohl der Versand im Hintergrund 3–4 Minuten später trotzdem erfolgreich abschließt.
Kein Erfolgs-Feedback, Risiko doppelter Zustellung durch Wiederholungsklicks.

## Root-Cause-Verifikation (heute nachgemessen, nicht nur aus dem Issue übernommen)

1. **Timeout-Quelle gefunden:** `/home/hem/henemm-infra/nginx/gregor20.henemm.com.conf` setzt
   **kein** `proxy_read_timeout` — es greift Nginx' Default von **60s**. Das erklärt den exakten
   60,0s-Cutoff aus dem Issue-Log; der Go-Client-Timeout (120s, `proxy.go:275`) wird nie erreicht,
   weil Nginx vorher killt. Diese Datei liegt in einem **anderen Repo** (`henemm-infra`) — eine
   reine Timeout-Anhebung müsste dort separat ausgeliefert werden (Cross-Repo-Änderung).
2. **Laufzeit-Ursache bestätigt, aber kein Bug:** `_send_trip_report_outcome()`
   (`src/services/trip_report_scheduler.py:1001`) baut für `evening` standardmäßig den
   Mehrtages-Ausblick (`_build_stage_trend`, Zeile ~1242, aktiv wenn
   `render_options.show_multi_day_trend`) und darauf aufbauend die Gewitter-Vorschau
   (`_build_thunder_forecast_from_trend_or_fetch`). Das ist **beabsichtigter Bestandteil** des
   Abend-Briefings — der Testversand soll ja exakt das zeigen, was auch real verschickt wird
   (`docs/specs/_archive/modules/issue_695_test_briefing_send.md`, AC-4: "sendet ... genau das
   E-Mail-Briefing"). Die Langsamkeit selbst liegt am bekannten Ein-Request-je-Zeitschritt-je-
   Parameter-Abruf bei DWD (`providers/dwd.py`, ~7–20s/Segment) für die künftigen Tage.
3. **Kein Idempotenz-Schutz gefunden:** Weder Backend (`api/routers/scheduler.py`,
   `trip_report_scheduler.py`) noch Frontend haben einen serverseitigen Lock/Dedup gegen einen
   zweiten Sendeversuch für denselben Trip+`report_type` während ein erster noch läuft. Der
   Frontend-Button sperrt nur, solange `testBriefingLoading` in DERSELBEN Browser-Session true
   ist — sobald der 502 zurückkommt, wird `testBriefingLoading` in `finally` wieder `false`
   (`+page.svelte:246`), der Button ist wieder klickbar, obwohl der erste Versand serverseitig
   noch läuft. Genau das erzeugte im Issue-Log zwei echte POSTs 68s auseinander.

## Related Files

| File | Relevance |
|------|-----------|
| `internal/handler/proxy.go:254-293` (`SendTripReportProxyHandler`) | Synchroner Go-Proxy, `client.Timeout: 120s`, gibt bei jedem `client.Do`-Fehler pauschal 502 zurück — unterscheidet nicht zwischen "Upstream tot" und "Upstream noch am Rechnen" |
| `api/routers/scheduler.py:205-279` (`send_test_trip_report`) | Python-Endpunkt, synchron, ruft `send_test_report_outcome()` und blockt bis zum fertigen Versand |
| `src/services/trip_report_scheduler.py:908-935` (`send_test_report_outcome`) | Öffentlicher Outcome-Wrapper, `allow_test_fallback=True, angefordert=True` |
| `src/services/trip_report_scheduler.py:1001-1330` (`_send_trip_report_outcome`) | Kernpfad: Segmente, Wetterabruf, Mehrtages-Ausblick, Gewitter-Vorschau, Versand — hier entsteht die Laufzeit |
| `src/services/trip_report_scheduler.py:1721-1850` (`_fetch_weather`) | Pro-Segment-Abruf mit Retry/Backoff — läuft für JEDES Ausblick-Segment, nicht nur die angefragte Etappe |
| `providers/dwd.py` | Bekannter langsamer Pfad: ein API-Request je Zeitschritt je Parameter (siehe Memory `reference_gewitter_apis_vier_dienste_und_eichung.md`) |
| `frontend/src/routes/trips/[id]/+page.svelte:209-250` (`handleTestBriefing`) | Blockierender `fetch`, kein serverseitiger Lock, `testBriefingLoading` wird bei jedem Abschluss (auch Fehler) zurückgesetzt |
| `/home/hem/henemm-infra/nginx/gregor20.henemm.com.conf` | Kein `proxy_read_timeout` gesetzt → Nginx-Default 60s greift; **anderes Repo** |
| `docs/specs/_archive/modules/issue_695_test_briefing_send.md` | Ursprüngliche Spec des Sendeknopfs — synchrones Design war zum Zeitpunkt (#695) bewusste Entscheidung, AC-4 verlangt inhaltliche Deckungsgleichheit mit dem echten Versand |

## Existing Patterns

- **Kein Async-Job/Poll-Muster im Code vorhanden** (`BackgroundTasks`, `job_id`, o. ä. — Grep über
  `api/` und `src/services/` ergab nichts). Ein Poll-basiertes Muster für diesen Bug wäre
  architektonisches Neuland in diesem Projekt, kein Wiederverwenden eines bestehenden Bausteins.
- Der bestehende `/api/scheduler/status`-Endpoint trackt bereits `last_run`/Fehler pro
  Scheduler-Job (siehe CLAUDE.md "Monitoring") — strukturell ähnlich zu dem, was ein
  Status-Poll-Endpoint für den Testversand bräuchte, aber für Cron-Jobs, nicht für
  On-Demand-Sends pro Trip.
- `send_on_demand_report()` (Zeile 936ff.) ist ein Geschwisterpfad (SMS "heute"/"morgen") mit
  demselben `_send_trip_report_outcome()`-Kern — eine Lösung, die dort ebenfalls durchschlägt,
  sollte geprüft werden, ist aber laut Issue nicht gemeldet (SMS-Inbound hat vermutlich andere
  Zeitbudgets/keinen synchronen Browser-Request).

## Dependencies

- **Upstream:** `NotificationService` (Renderer + Versand), `SegmentWeatherService` →
  `providers/openmeteo.py` + `providers/dwd.py` (Gewitter-Anreicherung), `WeatherPatternService`
  (Stabilitäts-Label)
- **Downstream:** Nur der Trip-Editor-Sendeknopf (`+page.svelte`) konsumiert
  `POST /api/trips/{id}/send` — kein weiterer bekannter Aufrufer dieses spezifischen Go-Routes.
  `send_test_report_outcome()` selbst hat laut Docstring **6 bestehende bool-Aufrufer** über
  `send_test_report()` (unangetastet, nicht Teil dieses Bugs) plus den einen
  Outcome-Aufrufer hier.

## Existing Specs
- `docs/specs/_archive/modules/issue_695_test_briefing_send.md` — Ursprungs-Spec des Sendeknopfs (archiviert)

## Risks & Considerations

- **Cross-Repo-Anteil:** Eine reine Nginx-Timeout-Anhebung liegt in `henemm-infra`, nicht in
  diesem Repo — wenn die Lösung diesen Hebel braucht, ist eine MQ-Nachricht an `infra` oder ein
  separater PR dort nötig. Timeout-Anhebung allein behebt laut Issue-Vorschlag ohnehin nicht die
  zugrunde liegende Langsamkeit.
- **Inhaltliche Parität wahren:** Der Testversand-Button soll weiterhin exakt das senden, was der
  echte Abend-Report enthält (AC-4 aus #695) — den Mehrtages-Ausblick für den Testpfad einfach
  wegzulassen würde diese Garantie brechen und wäre eine stille Verhaltensänderung.
- **Idempotenz/Doppel-Versand ist der eigentliche Schaden**, nicht nur die falsche
  Fehlermeldung — jede Lösung muss einen zweiten Klick während eines laufenden Sends
  server-seitig abfangen (bisher nicht vorhanden), sonst bleibt das Kernrisiko aus dem Issue
  auch nach einem UI-Fix bestehen.
- **Mandantenfähigkeit:** Ein etwaiger Lock/Status muss pro `user_id` + `trip_id` (+ `report_type`)
  scopen, nicht global — sonst blockiert Nutzer A den Testversand von Nutzer B.
- **Go-Proxy unterscheidet nicht** zwischen "Python tot" und "Python rechnet noch" — beides
  landet aktuell als generisches 502 `upstream unreachable`, was die irreführende Fehlermeldung
  im Issue erklärt.

## Analysis

### Type
Bug

### Optionen-Bewertung (Plan/Sonnet-Agent, gegengeprüft gegen `proxy.go`/`scheduler.py`/`+page.svelte`)

| Option | Ansatz | Idempotenz gelöst? | Scope | Risiko |
|---|---|---|---|---|
| A — nur Timeout-Kette anheben | Nginx `proxy_read_timeout` + Go `client.Timeout` hoch | Nein | ~5 LoC, cross-repo | gering, aber unzureichend |
| B — voller Async/Poll | 202+`job_id`, neuer Status-Endpoint, Frontend-Poll-Loop, State-Store | Ja (Nebenprodukt) | deutlich >250 LoC, sprengt Standard-Budget | architektonisches Neuland, kein bestehendes Muster |
| **C — In-Process-Lock + Timeout-Anhebung (empfohlen)** | Lock `(user_id, trip_id, report_type)` um `_send_trip_report_outcome()`, bei Belegung 409 statt 502; Timeout-Kette moderat hoch als Trittstein | **Ja, direkt** | ~60–90 LoC Hauptrepo + kleine Nginx-Änderung (nicht Budget-relevant) | gering — nutzt bestehendes Fehler-Response-Schema (analog no_stage/no_weather/no_channels) |

### Affected Files (with changes) — Option C

| File | Change Type | Description |
|------|-------------|-------------|
| `src/services/trip_report_scheduler.py` | MODIFY | In-Process-Lock (Dict + `threading.Lock`, Key `(user_id, trip_id, report_type)`) um `_send_trip_report_outcome()`-Aufruf im Test-Pfad; bei Belegung eigener Outcome-Wert statt normalem Ablauf |
| `api/routers/scheduler.py` | MODIFY | Neuer Outcome → HTTP 409 mit sprechendem Detail ("Versand läuft bereits"), analog zu bestehenden 422-Zweigen |
| `internal/handler/proxy.go` | MODIFY | `client.Timeout` moderat anheben (z. B. 300s); 409 unverändert durchreichen (Passthrough funktioniert bereits generisch über `resp.StatusCode`) |
| `frontend/src/routes/trips/[id]/+page.svelte` | MODIFY | 409 → eigene Meldung ("Versand läuft bereits, bitte warten") statt genereller Fehlermeldung; kein automatischer Retry |
| `henemm-infra/nginx/gregor20.henemm.com.conf` | MODIFY (anderes Repo) | `proxy_read_timeout` setzen (z. B. 300s), synchron zu Go-Timeout — per MQ-Nachricht an `infra` |

### Scope Assessment
- Files: 4 im Hauptrepo + 1 im `henemm-infra`-Repo
- Estimated LoC: ~60–90 (Hauptrepo, unter dem 250-LoC-Standard-Budget)
- Risk Level: LOW — kein neues Architekturmuster, Lock hängt sich an bestehendes Fehler-Schema

### Technical Approach
**Empfehlung: Option C.** Das Issue benennt zwei Symptome, aber nur eines ist der tatsächliche
Schaden: das reale Doppel-Zustellungsrisiko durch fehlende Idempotenz-Sperre — nicht die
irreführende 502-Meldung als solche. Option C behebt das direkt und ursächlich mit minimalem,
bestehende Patterns nutzendem Code, bleibt sicher unter dem LoC-Budget und führt keine neue
Architektur-Kategorie (Async/Polling) ein, die es im Projekt noch nie gab (größtes Neurisiko
bei Option B). Die Timeout-Anhebung (Kern von Option A) wird als Trittstein mitgenommen, aber
nicht als alleinige Lösung — die 3–4 Minuten Wartezeit bleiben, sind aber mit ehrlicher
Fehlermeldung bei Doppelklick vertretbar und wahren die Paritäts-Garantie aus AC-4 (#695), da
der synchrone Pfad unverändert bleibt. Volles Async/Polling (Option B) bleibt eine legitime
spätere Ausbaustufe, falls „minutenlanges blindes Warten" selbst zum wiederkehrenden
Beschwerdepunkt wird.

**Einschränkung dokumentieren:** Der In-Process-Lock wirkt nur pro Systemd-Prozess. Laut
Architektur laufen `gregor-python`/`-staging` je als ein Prozess — unkritisch, aber als Kommentar
im Code festhalten, falls das Deployment künftig auf Multi-Worker wechselt.

### Dependencies
- Upstream: keine neuen Abhängigkeiten — nutzt bestehendes Fehler-Response-Schema in
  `scheduler.py` (422-Zweige) als Vorbild für den neuen 409-Zweig.
- Downstream: `send_test_report()` (6 bestehende bool-Aufrufer) bleibt unberührt — anderer
  Codepfad, nicht der hier geänderte `send_test_report_outcome()`-Wrapper.
- Reihenfolge: zuerst Python-Lock + Router-Mapping + Go-Passthrough + Frontend im Hauptrepo
  (dieser Workflow), danach MQ-Nachricht an `infra` für die Nginx-Timeout-Anhebung — beide
  unabhängig deploybar, aber der Lock sollte zuerst live sein, damit auch vor der
  Infra-Änderung kein Doppelversand mehr möglich ist.

### Open Questions
- [ ] Soll `send_on_demand_report()` (SMS "heute"/"morgen", derselbe `_send_trip_report_outcome()`-Kern) denselben Lock mitbekommen, obwohl im Issue nicht gemeldet? (Empfehlung: ja, gleicher Lock-Key-Raum, minimal-invasiv, verhindert dieselbe Klasse Doppelversand über einen anderen Trigger)
- [ ] 409-Text im Frontend: reicht eine einfache Meldung, oder soll der Button währenddessen einen Poll starten, um automatisch auf "gesendet" umzuschalten? (Empfehlung: nein für diesen Fix — das wäre bereits ein Stück Option B; einfache Meldung reicht, User kann Seite neu laden)

## Next Step
Weiter mit `/20-analyse` zur Lösungsoptionen-Bewertung (Async/Poll vs. schlankerer Testpfad vs.
Timeout-Kette) und Empfehlung.
