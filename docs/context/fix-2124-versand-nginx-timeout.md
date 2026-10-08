# Context: fix-2124-versand-nginx-timeout

## Request Summary
Manueller Trip-Versand (`POST /api/trips/{id}/send`) dauert bis ~3–4 Min. nginx bricht nach 60 s (Default
`proxy_read_timeout`) ab, die Go-API antwortet 502, die GUI zeigt „Versand fehlgeschlagen" — obwohl der
Python-Core vollständig zustellt. Folge: Nachdrücken ⇒ Doppelversand (Prod 30.08.2026, KHW 403).

## Related Files
| File | Relevance |
|------|-----------|
| `internal/handler/proxy.go:266-301` | `SendTripReportProxyHandler`, Timeout 300 s (#1756 AC-8), `NewRequestWithContext(r.Context())` (:273) ⇒ nginx-Abbruch cancelt Upstream-Request ⇒ 502 `upstream unreachable` (:283-287) |
| `internal/handler/compare_preset.go:609-645` | `SendComparePresetHandler` — Compare-Pendant, Timeout 120 s, r.Context(), gleiches 502-Muster, eigener Code |
| `internal/handler/proxy.go:110ff` | `ProxyPostHandler` 120 s (notify/test, Admin-Trigger router.go:250,312,326-328) |
| `internal/handler/proxy.go:205-226` | `StagesWeatherProxyHandler` 60 s, `client.Get` ohne Context (router.go:243) |
| `internal/handler/proxy.go:79`, `preview_proxy.go:39-52` | Compare-/Preview-Proxy 60 s |
| `internal/router/router.go:261,283` | Routen Trip-Send / Compare-Send |
| `api/routers/scheduler.py:229-312` | `send_test_trip_report` — sync `def`, läuft bei Client-Abbruch zu Ende; 409 bei laufendem Versand (:304-310) |
| `api/routers/scheduler.py:315` | `manual_send_compare_preset` → `scheduler_dispatch_service.send_compare_preset` (~690), sync, **ohne Lock** |
| `src/services/trip_report_scheduler.py:397-416,1173,1196,1251,1764-1778` | In-Process-Lock (user,trip,report_type) aus #1756; briefing_log-Eintrag mit `sent_channels` |
| `src/services/notification_service.py:~580-750` | Kanäle sequentiell: E-Mail → SMS → Premium-SMS → Telegram |
| `frontend/src/routes/trips/[id]/+page.svelte:285-326,355,383-386` | `handleTestBriefing`: `disabled` während Laden, 5xx ⇒ Fehlermeldung, nach 4 s wieder klickbar |
| `frontend/src/routes/trips/+page.svelte:322-333`, `trips/tripListSend.ts:32-48` | Trip-Liste: `sendTripTestReport`, **kein** Laufzustands-Guard |
| `frontend/src/lib/components/molecules/TestReportDialog.svelte:33,51` | Dialog während `running` schließbar ⇒ sofort erneuter Versand möglich |
| `frontend/src/lib/components/compare/CompareTabs.svelte:653`, `routes/compare/[id]/+page.svelte:213`, `routes/compare/+page.svelte:156-169` | Compare-Versand-Auslöser, Guards uneinheitlich |
| `frontend/src/lib/components/trip-detail/StageList.svelte:31`, `lib/utils/stageRisk.ts:33` | stages/weather-Aufrufer, fail-soft (Fehler still) |
| `/home/hem/henemm-infra/nginx/gregor20.henemm.com.conf` (location /api/ :46), `staging.gregor20.henemm.com.conf` (:55) | Quelle der vhosts (identisch mit /etc/nginx/sites-available), kein `proxy_*_timeout` |

## Existing Patterns
- Proxy-Handler: je Handler eigener `http.Client{Timeout}` + `NewRequestWithContext(r.Context())`; Fehler ⇒ 502 JSON.
- Doppelversand-Schutz (#1756): In-Process-Lock nur während des Laufs; danach keine Dedup gegen briefing_log/Zeitfenster.
- Kein Async-/Job-/Status-Mechanismus im Projekt (kein BackgroundTasks, kein job_id, kein dispatch_status).
- Go-Server ohne Read/Write/IdleTimeout.

## Dependencies
- Upstream: nginx (henemm-infra) → Go-API → Python-Core (FastAPI, ein uvicorn-Prozess je Umgebung, kein `--workers`).
- Downstream: Trip-Detail-Seite, Trip-Liste (TestReportDialog), Compare-Seiten, Telegram-/Mail-Befehle nutzen eigene Wege (nicht betroffen).

## Existing Specs
- `docs/specs/modules/fix_1756_send_idempotenz_lock.md` — Lock, Timeout 300 s; **lehnt Async/Poll („Option B") ab** (:208-211); empfiehlt `proxy_read_timeout 300s` als Cross-Repo-Follow-up (:236-245) — **nie umgesetzt**.
- `docs/context/fix-1756-send-timeout-502.md` — Analyse inkl. Option B.
- `docs/specs/modules/stage_weather_go_proxy.md`, `stage_weather_python_endpoint.md`, `fix_1912_scheduler_briefing_timeout.md`, `dispatch_orchestrator.md`, `fix_1662_versandfehler_nachliefern.md`.
- `proxy.go:264` verweist auf nicht existierende `issue_695_test_briefing_send.md`.

## Risks & Considerations
- Abweichung von #1756 (Async abgelehnt) bräuchte Begründung/ADR-Prüfung; die naheliegende Lücke ist die nie umgesetzte nginx-Ratsche.
- Infra-Änderung (nginx) ist Cross-Repo: henemm-infra-Arbeitsbaum ist sofort live — Reihenfolge und Reload (`nginx -t`) beachten; Staging + Prod vhost.
- Go-Handler: Upstream-Request hängt am Client-Context ⇒ jeder Abbruch (auch Browser-Tab zu) erzeugt 502, obwohl Python weiterläuft — Entkopplung vom Request-Context erwägen.
- Doppelversand nach Abschluss nicht geschützt; Trip-Liste/Dialog ohne Laufzustand; Compare-Versand ohne Lock (Parität Trip/Compare).
- Nebenbefund briefing_log nur `["email"]`: vermutlich Telegram-`fully_sent`/SMS-Reservierung (notification_service.py:627-641, 714-724) — laut Issue eigener Punkt.

## Analysis

### Type
Bug

### Beweislage 30.08.2026 (Prod-Logs + `briefing_log.json`, gelesen 2026-10-07)
- **GUI-Weg hat genau EINEN Versand ausgelöst:** Go-API sieht im Fenster 19:20–19:45 genau einen
  `POST /api/trips/5f534011/send?report_type=evening` (19:31:45 → 502 nach 60,04 s). Python loggt genau
  einmal `Generating evening report` (19:31:45) und einmal `Trip report sent … via email,sms,premium_sms,telegram`
  (19:34:57). **Kein Nachdrücken in der GUI**, kein 409.
- `briefing_log.json` (henning) hat drei `on_demand`-Einträge: 19:33:23 `["email"]`, 19:34:57 (alle vier),
  19:36:37 `["email","telegram"]`. Nur 19:34:57 ist dem GUI-Versand zuzuordnen. Zu 19:33:23 und 19:36:37 gibt es
  **keine** `Generating`/`Trip report sent`-Zeile im `gregor-python`-Journal — sie stammen also nicht aus dem
  laufenden Prod-Dienst. **Wahrscheinlich, aber nicht belegt:** eine parallele Claude-Sitzung (Worktree
  `feat-2051-s2b`) fuhr zur selben Zeit Einmal-Versände als `claude-gregor` mit `GZ_DATA_DIR=/var/lib/gregor`
  (`/tmp/gz-oneshot-mail.py`; sudo-Starts 19:26:40 [sofort beendet], 19:26:47 [bis 19:30:03, ohne Eintrag für
  5f534011], 19:31:35 [sudo-Sitzung sofort beendet — evtl. Hintergrundprozess]; `rm /run/gz-oneshot.env` 19:36:46).
  Zeiten passen nicht sauber; Transkript der Sitzung nicht auffindbar. → Issue-Nebenbefund `["email"]` bleibt
  **offen** (in #1199 gebucht), nicht Teil dieses Fixes.
- **Folge für den Scope:** Der vom Issue behauptete Doppelversand „durch Nachdrücken" ist für den 30.08. **nicht
  belegt**. Strukturell bleibt das Risiko trotzdem real (Fehleranzeige verleitet zum Nachdrücken; Trip-Liste/
  TestReportDialog ohne Laufzustands-Schutz; Compare-Versand ohne Lock) und wird mit abgedeckt (AC-2 des Issues).
- `GET …/stages/weather` 19:22:26 → 502 nach 60,0 s: Go-Client 60 s == nginx 60 s; der zweite Aufruf 19:31:50 brauchte 9 s.
- Kein CDN/Zwischenproxy: `gregor20` und `staging.gregor20` lösen direkt auf 178.104.143.19 auf.
- Regel-Versanddauern KHW 403 (Scheduler): 20–84 s; der manuelle Fall 30.08. 3 min 12 s.

### Affected Files (with changes)
| File | Change Type | Description |
|------|-------------|-------------|
| `/home/hem/henemm-infra/nginx/gregor20.henemm.com.conf` (`location /api/`) | MODIFY | `proxy_read_timeout`/`proxy_send_timeout` ≈330 s (> Go-Sende-Timeout 300 s) |
| `/home/hem/henemm-infra/nginx/staging.gregor20.henemm.com.conf` (`location /api/`) | MODIFY | dito, Staging zuerst |
| `internal/handler/proxy.go` (`SendTripReportProxyHandler`) | MODIFY | Upstream-Request mit `context.WithoutCancel(r.Context())` (Go 1.25), Timeout aus gemeinsamer Konstante |
| `internal/handler/compare_preset.go` (`SendComparePresetHandler`) | MODIFY | Parität: gleiche Entkopplung + gleiche Konstante (120 s → 300 s) |
| `internal/handler/*_test.go` | CREATE/MODIFY | Client-Abbruch während laufendem Upstream ⇒ Upstream wird zu Ende bedient; Timeout-Kette: jeder Proxy-Timeout < dokumentierte nginx-Grenze |
| `src/services/scheduler_dispatch_service.py` (`send_compare_preset`), `api/routers/scheduler.py` | MODIFY | Compare-Versand bekommt denselben In-Process-Lock wie #1756 (geteilter Helfer, nicht kopiert) + 409 |
| `frontend/src/routes/trips/[id]/+page.svelte` (`handleTestBriefing`) | MODIFY | 5xx/Netzfehler beim Versand ≠ „fehlgeschlagen" → „Ergebnis unklar, Versand kann noch laufen"; 409 → „Versand läuft bereits" |
| `frontend/src/routes/trips/+page.svelte`, `trips/tripListSend.ts`, `molecules/TestReportDialog.svelte` | MODIFY | Laufzustands-Schutz: kein zweiter Auslöser während laufendem Versand |
| `frontend/src/lib/components/compare/CompareTabs.svelte`, `routes/compare/[id]/+page.svelte`, `routes/compare/+page.svelte` | MODIFY | dieselbe Logik über einen geteilten Baustein (Trip/Compare-Teilung) |

### Scope Assessment
- Files: ~12 (davon 2 in henemm-infra)
- Estimated LoC: +230/-40 (gregor-Repo) → `loc_limit_override 500` vorsorglich; **nicht** in Scheiben/Folge-Tickets abspalten (Trip/Compare-Parität gehört in dieses Ticket)
- Risk Level: MEDIUM — Cross-Repo-nginx (Arbeitsbaum sofort live), zentrale Versand-Endpunkte

### Technical Approach
**Option A (synchron bleiben) — Entscheidung, kein neues ADR.** Konsistent mit #1756
(`docs/specs/modules/fix_1756_send_idempotenz_lock.md`: Async/Poll „Option B" abgelehnt, nginx-Ratsche als
Follow-up empfohlen und nie umgesetzt). Async (Job + Status-Poll) bräuchte Job-Store, Mandanten-Isolation,
Poll-UI, ADR und ≥500 LoC — kein Nutzen gegenüber A für AC-1..3.
1. **nginx (henemm-infra, selbst umsetzen, Infra zuerst):** `proxy_read_timeout 330s; proxy_send_timeout 330s;` in
   `location /api/` beider vhosts; Kommentar verweist auf die Go-Konstante. Ablauf: Staging-vhost → `sudo nginx -t`
   → reload → Smoke; dann Prod. Commit/Push in henemm-infra nach dem dort üblichen Weg (PO-Einmal-Skript, infra
   vor gregor). Global auf `/api/` statt Einzelrouten: deckt auch `stages/weather` und `notify/test` (120 s) ab,
   jede Route ist ohnehin durch ihren Go-Client-Timeout begrenzt.
2. **Go:** Upstream-Request der Sende-Handler vom Client-Context entkoppeln (`context.WithoutCancel`), damit ein
   Client-/Proxy-Abbruch den Versand nicht in ein 502 verwandelt; gemeinsame Sende-Timeout-Konstante Trip+Compare.
3. **Python:** Compare-Versand-Lock analog #1756 (Schlüssel user + preset), 409 bei Kollision.
4. **Frontend (geteilt Trip/Compare):** Laufzustands-Sperre an allen Auslösern; Fehlerklassifikation:
   2xx = Ergebnis anzeigen, 409 = „läuft bereits", 5xx/Netz = „Ergebnis unklar — nicht erneut senden, Versandprotokoll prüfen".
5. **Absicherung AC-3:** Go-Test bindet alle Proxy-Timeouts an eine dokumentierte nginx-Untergrenze (CI hat kein
   nginx); echte Prüfung in der Staging-Verifikation (realer Trip-Versand > 60 s über `staging.gregor20…` → 200).

### Dependencies
- nginx → Go-API → Python-Core; Reihenfolge Auslieferung: nginx (Staging, dann Prod) vor/unabhängig vom gregor-Deploy.
- #1756-Lock (`trip_report_scheduler.py:397-416`) wird für Compare wiederverwendet.
- Frontend-Auslöser Trip-Detail, Trip-Liste, TestReportDialog, drei Compare-Stellen.

### Decisions (keine PO-Rückfrage nötig)
- Synchron (Option A), kein ADR — Linie von #1756.
- Ein bewusster zweiter Versand **nach** Abschluss bleibt erlaubt (Nutzerhandlung); geschützt wird nur der Zeitraum, in dem ein Versand läuft.
- Issue-Nebenbefund `["email"]` + Fremd-Einträge: nicht Teil dieses Fixes, in #1199 gebucht (Herkunft unbelegt).

### Hinweise für /30 (Spec)
- **Browser-Timeout:** In den Sende-Aufrufern (`tripListSend.ts`, `trips/[id]/+page.svelte`, `CompareTabs.svelte`,
  `lib/api*`) gibt es **kein** `AbortSignal`/`AbortController`/Timeout — gut so; die Spec darf **keinen**
  Client-Hard-Timeout < 330 s einführen (Bug-Intake-Vorschlag „30 s Hard-Timeout" verworfen).
- **nginx-Ausrollweg:** `/etc/nginx/sites-enabled/*gregor*` sind Symlinks auf `/etc/nginx/sites-available/…`
  (NICHT auf henemm-infra). henemm-infra hält die Quellkopie → Änderung in beiden Orten nötig
  (Quelle committen + nach `sites-available` übernehmen), Rollback = alte Datei zurück + `nginx -t` + reload.
- **Beweis AC-3:** Der Go-Konstanten-Test schützt nur die Go-Seite (vhost-Zeile löschen macht ihn nicht rot) —
  ist ein normaler Test, kein neues Gate. Den echten Beweis liefert Staging: ein Sende-Aufruf, der **> 60 s**
  dauert und **200** zurückgibt (Go-Access-Log). Da Regel-Versände 20–84 s brauchen, muss die Spec einen
  Staging-Testfall festlegen, der verlässlich > 60 s braucht (z. B. Trip mit vielen Etappen + Mehrtages-Ausblick);
  zusätzlich `sudo nginx -T | grep proxy_read_timeout` je vhost als Konfig-Nachweis.

### Open Questions
- keine
