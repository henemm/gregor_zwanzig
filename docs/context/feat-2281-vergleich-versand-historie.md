# Context: feat-2281-vergleich-versand-historie

## Request Summary
Issue #2281 (Epic #2345, Etappe P4, nach #2280): Der Ortsvergleich hat keine Versand-Historie. Der Briefing-Log kennt nur `trip_id`, und nur der Trip schreibt ihn. Cockpit, Archiv-Zahlen und Briefing-History sehen deshalb nur Trips. Ziel ist ein kind-neutraler Log-Eintrag, den beide Arten schreiben, und eine kind-neutrale Historie, die in beiden Hubs sichtbar ist.

## Related Files
| File | Relevance |
|------|-----------|
| `internal/store/log.go:10-15` | `BriefingLogEntry{TripID, Kind, SentAt, Channels}`. Ablage `users/<uid>/briefing_log.json` als **ein** JSON-Objekt `{"entries":[...]}`, nicht JSONL. |
| `internal/store/log.go:23-43` | `LoadBriefingLog`: `requireUser`; Datei fehlt oder ist kaputt → leere Liste. Go schreibt nie. |
| `internal/store/log.go:103-116` | `BriefingCountByTrip` zählt nach `TripID`. |
| `internal/store/log.go:51-58, :85-96, :125-140` | **Vorlage aus #1467:** `AlertLogEntry{EntityID, EntityType, TripID omitempty}`. Lese-Regel statt Migration: fehlt `EntityID`, wird `TripID` übernommen; fehlt `EntityType`, gilt `"trip"`. `AlertCountByEntity` zählt nach `"<type>:<id>"`. |
| `src/services/trip_report_scheduler.py:2349` | `_append_briefing_log`, einziger Schreiber. Felder: `trip_id`, `kind`, `sent_at`, `channels`, `on_demand`, `mail_to`. Liest und schreibt die ganze Datei neu, **ohne Sperre und nicht atomar**. Kaputte Datei wird beiseitegelegt (#2231, :2389-2395). |
| `src/services/trip_report_scheduler.py:1956` (in `_send_trip_report_outcome` :1422) | Einziger Aufruf, nur wenn `result.sent`. Cron, SMS-Abfrage, Test-Versand und Befehl „report" laufen alle hier durch. |
| `src/services/scheduler_dispatch_service.py:456` `send_one_compare_preset` | Compare-Engstelle für Cron **und** Handversand (`on_demand=True` :817). `save_compare_preset_status` (:273, Aufruf :773) schreibt nur `letzter_versand`/`top_ort_letzter_versand` ins Preset, nach `outcome == "sent"` (:738-745). |
| `src/services/compare_slot_scheduler.py:39-40, :200-202` | Compare-Slot kennt kein morning/evening, nur `tage_ab_ortstag` (0 = Morgen, 1 = Abend). |
| `src/services/dispatch_orchestrator.py:208-214` | `_STRATEGY = {"route", "vergleich"}`, **nur Cron**. Der Handversand (`api/routers/briefings_send.py`) geht daran vorbei. Das ist deshalb **nicht** der richtige gemeinsame Schreibort. |
| `src/services/alert_log.py:20-23, :389, :419` | Muster für einen Python-Schreiber mit `entity_type` als Pflichtfeld (`"trip"\|"compare"`). |
| `src/services/briefing_slots.py:347-361, :405ff` | `_passt`/`_log_traegt_versand` lesen `trip_id` + `kind` aus dem Log und überspringen `on_demand`. Das ist der Doppelversand-Schutz (#1725/#1897). |
| `internal/handler/briefing_history.go:15-50` | `GET /api/trips/{id}/briefing-history`, filtert nach `TripID`. |
| `internal/handler/cockpit.go:21-33` | `GET /api/cockpit/status`: heutige Log-Einträge roh, ohne Typ-Filter. |
| `internal/handler/archive_stats.go:21-22` | `BriefingCountByTrip` + `AlertCountByEntity`. Kein Frontend-Nutzer mehr seit #611. |
| `internal/router/router.go:250, :293-305` | Trip-History-Route. Unter `/api/briefings/{id}/` gibt es GET, `preview`, `alert-preview` und `send` (kind als Query `?kind=route\|vergleich`), aber noch kein `briefing-history`. |
| `internal/store/user_scope_guard_test.go:87-90` | Reflection-Drift-Liste der Store-Methoden. Neue oder umbenannte Methoden müssen hier eingetragen werden. |
| `internal/store/user.go:456`, `internal/handler/data_export_test.go:50,282` | `briefing_log.json` ist schon im Datenexport. Keine Änderung nötig. |
| `frontend/src/lib/components/briefing-history/BriefingHistoryDialog.svelte` | **Verwaist seit #611 (ee66cc2b0):** kein Importeur. Hart an Trips gebunden (Prop `tripId`, Abruf `/api/trips/${tripId}/briefing-history`, Beschriftungen nur morning/evening). |
| `frontend/src/lib/types.ts:632-637, :642-649` | TS-Typ `BriefingLogEntry` (nur `trip_id`). `AlertLogEntry` zeigt das #1467-Muster. |
| `frontend/src/routes/_home/cockpitHelpers.ts:156-170, :190ff` | `plannedBriefings` filtert `e.trip_id === tripId`. Vorlage mit Typ-Prüfung: `alertsForTrip`. Genutzt in `routes/+page.svelte:143`, geladen in `+page.server.ts:28`. |
| `CompareTabs.svelte:728,770`, `SubscriptionCard.svelte:82`, `homeCompareTimeline` | Zeigen `letzter_versand` an. Muss erhalten bleiben. |
| `scripts/migrate_briefing_log_mail_to_mask.py:48` | Schreibt `briefing_log.json` um. Muss das neue Format vertragen. |

## Existing Patterns
- **#1467 Alarm-Kennung** (`docs/specs/modules/rework_1467_s1_alarm_kennung.md`): neue Felder `entity_id`/`entity_type`, Altfeld `trip_id` `omitempty` nur noch gelesen, **Lese-Regel statt Datei-Migration**, Zähler-Schlüssel `"<type>:<id>"`. Ein Eintrag ohne ID wird nicht verworfen.
- **kind-neutrale Endpunkte unter `/api/briefings/{id}/…`**: preview, alert-preview, send (#2280). Der kind wird per Query mitgegeben.
- **Lesen-Ändern-Schreiben mit Sperre und atomarem Ersetzen** beim Compare-Preset (`_rmw_compare_preset`). Vorlage für einen gleichzeitig beschriebenen Log.

## Dependencies
- **Upstream:** `get_data_dir(user_id)` (Python), `s.WithUser(userID)` + `requireUser` (Go), `briefing_slots` (Doppelversand-Schutz), `alert_log`-Konventionen.
- **Downstream:** Cockpit (Home `plannedBriefings`), Archiv-Stats (ohne Frontend-Nutzer), Trip-Briefing-History-Endpunkt, Datenexport, Migrations-Skript, viele Python-Tests, die `trip_id` direkt aus der Datei lesen. Dazu #2286 (`briefing_health`), nur über das gemeinsame kind-Vokabular und ohne harte Abhängigkeit.

## Existing Specs
- `docs/specs/modules/rework_1467_s1_alarm_kennung.md`: Vorlage für Kennung und Lese-Fallback
- `docs/specs/modules/dispatch_orchestrator.md`: Cron-Versandweg
- `docs/specs/modules/feat_2280_handversand_endpoint.md`: Handversand für beide kinds
- `docs/specs/modules/screen_archive_migration.md`: Archiv-Seite, `/api/archive/stats` dort als „obsolet" vermerkt
- `docs/specs/modules/fix_1396_s2_store_scope_guard.md`: Store-Scope-Guard
- ADR `docs/adr/0031-persistenz-dateibasiert-data-users.md`. Keine ADR zu `briefing_log`.

## Risks & Considerations
1. **Vokabular von `entity_type`:** Das Issue nennt `vergleich`, das Alarm-Log nutzt `"trip"|"compare"`, `briefings/` und der Send-Endpunkt nutzen `route|vergleich`. Muss in der Analyse entschieden werden.
2. **`kind` beim Vergleich:** Er muss aus `tage_ab_ortstag` abgeleitet werden. Für den Handversand gibt es keinen Slot, also braucht es eine Konvention (`on_demand=true`, wie beim Trip).
3. **Datenerhalt:** nur Lese-Regel, keine Datei-Migration. Der Trip schreibt `trip_id` weiter mit, sonst brechen `briefing_slots._passt` (Doppelversand-Schutz) und viele Tests.
4. **Lost Update:** Bisher gibt es einen Schreiber ohne Sperre. Künftig schreiben Trip-Cron, Compare-Cron und Handversand in **dieselbe** Datei, deshalb Sperre und atomares Ersetzen.
5. **Cross-User-Isolation:** Ein neuer Endpunkt `/api/briefings/{id}/briefing-history` braucht die ID-Prüfung wie die anderen `/api/briefings/{id}`-Routen (`entity_traversal_test.go`), einen Test mit zwei Nutzern und einen Eintrag im Scope-Guard.
6. **ID-Kollision Trip ↔ Vergleich:** Zähler mit Schlüssel `"<type>:<id>"`.
7. **Frontend-Annahme im Issue ist falsch:** Der Historien-Baustein ist in **keinem** Hub eingebunden (verwaist seit #611). AC-2 bedeutet also, ihn in beiden Hubs einzubinden. Das berührt die Trip/Compare-Teilungsregel: **ein** Baustein mit `kind`.
8. **Zielbild im Issue** („schreibt aus `dispatch_orchestrator.py`") würde den Handversand verfehlen. Die richtigen Engstellen sind `_send_trip_report_outcome` und `send_one_compare_preset`, über einen geteilten Schreib-Helfer.
9. **Kollisionen:** Epic #2505 und dessen offene Unter-Issues ändern das Log-Format nicht. `trip_report_scheduler.py` und `scheduler_dispatch_service.py` wurden zuletzt häufig geändert (#2280, #2521, #1441), deshalb vor dem Commit gegen `origin/main` rebasen.

## Analysis

### Type
Feature (Epic #2345, Etappe P4). Scope: **full-stack mit UI** (Python + Go + Frontend). Daraus folgen Fresh-Eyes und Staging-Durchklicken in beiden Hubs.

### Verifizierte Zusatzbefunde (Analyse-Phase)
- Go-Leser des Logs sind nur `cockpit.go:21`, `briefing_history.go:25`, `archive_stats.go:21` (über `BriefingCountByTrip`). Kein Go-Health-Code liest den Log. henemm-infra liest ihn nicht.
- Python-Leser sind nur `briefing_slots.py` (`_log_bezeugt_versand` :367, `_log_traegt_versand` :406, `_repair_locked` :250, `_log_unlesbar` :266). Gelesen wird über `eintrag.get("trip_id") == trip_id and kind == slot`, `on_demand` wird übersprungen.
- **`locked_json_rmw` (file_lock.py:124) ist NICHT verwendbar.** Es wirft bei fehlender Datei und bei Parsefehlern. Vorlage ist stattdessen `alert_log._append` (:519): `exclusive_lock` + selbst lesen + `atomic_write_json`. Beim Parsefehler gilt der bestehende Pfad aus #2231 (`lege_beschaedigte_datei_beiseite`) und nicht „neu anlegen".
- `briefing_slots._repair_locked` legt den Log unter der **Slot-Sperre** beiseite, nicht unter der Log-Sperre. Der Schreibhelfer muss deshalb nach dem Erhalt der Sperre frisch lesen. Restfenster: Ein Eintrag kann höchstens in einer gerade beiseitegelegten Datei landen. Das gilt schon heute und ist hinnehmbar.
- Kanäle: Der Trip loggt `result.sent_channels` (trip_report_scheduler.py:1956). Der Compare-Pfad hat `send_result.sent_channels` aus derselben `NotificationResult`-Klasse, die mit email/sms/premium_sms/telegram befüllt wird (notification_service.py:702-797). → **Gleiche Quelle wie beim Trip**, kein Fallback auf `effective_channels`.
- Cockpit-Frontend: `+page.svelte:142` nutzt `cockpitStatus.briefings` nur über `plannedBriefings(…, hero.id)`, das nach `trip_id` filtert. Es gibt **keine** rohe Zählung. Compare-Einträge ohne `trip_id` verfälschen die Hero-Anzeige also nicht.
- `/api/archive/stats` hat keinen Frontend-Nutzer (seit #611).
- #2286 spricht von `kind=vergleich` für Health-Kennzahlen. Das ist API-/Strategie-Vokabular, nicht das Log-Feld.

### Entscheidungen (für die Spec festzuschreiben)
1. **`entity_type` = `"trip"|"compare"`** wie im Alarm-Log (#1467). Dafür spricht: eine Dateifamilie, ein Go-Store, eine Lese-Regel, ein Zählschlüssel `"<type>:<id>"`, derselbe Frontend-Filter wie `alertsForTrip`. Das Issue schreibt `entity_type=vergleich`. **Diese Abweichung wird in AC-1 ausdrücklich genannt.** Der API-Query `?kind=route|vergleich` wird im Go-Handler abgebildet (`route→trip`, `vergleich→compare`).
2. Das Logfeld `kind` bleibt `morning|evening` (Slot) und wird nicht umbenannt. In der Spec wird sauber unterschieden: „Briefing-Art" (Query) vs. „Slot" (Logfeld).
3. **Kompat:** Trip-Einträge schreiben weiter `trip_id` plus zusätzlich `entity_id` + `entity_type:"trip"`. **Compare-Einträge schreiben KEIN `trip_id`.** Zusätzlich kommt ein Guard in `_log_traegt_versand`/`_log_bezeugt_versand`: Es zählt nur `entity_type in (None,"trip")`. Das schützt vor Doppelversand bei ID-Kollision.
4. Compare-Slot: `tage_ab_ortstag` 0 → `morning`, 1 → `evening`. Handversand: `on_demand=true`, Slot ebenfalls aus `tage_ab_ortstag` (Default 0 → morning).
5. **Gemeinsamer Python-Schreibhelfer** `src/services/briefing_log.py` (`append_briefing_log(user_id, entity_type, entity_id, kind, channels, on_demand, mail_to)`), gesperrt und atomar nach dem `alert_log._append`-Muster, mit dem Beiseitelegen aus #2231. `_append_briefing_log` im Scheduler wird ein dünner Wrapper. Der Compare-Aufruf steht in `send_one_compare_preset` direkt nach `outcome == "sent"` (:739) und gilt für Cron UND Hand. **Nicht** im `dispatch_orchestrator`, denn der Handversand geht daran vorbei; damit ist das Zielbild im Issue korrigiert. Ein Log-Schreibfehler kippt den Versand nicht. Bei Sperr-Timeout wird laut protokolliert und nie ungesperrt geschrieben.
6. **Go:** `BriefingLogEntry` bekommt `EntityID`/`EntityType`, `TripID` wird `omitempty`. Die Lese-Regel in `LoadBriefingLog` folgt 1:1 dem Alarm-Log (log.go:85). `BriefingCountByEntity` (`type:id`) ersetzt `BriefingCountByTrip` (kein Frontend-Nutzer). Das Register im Scope-Guard wird angepasst.
7. **Neuer Endpunkt** `GET /api/briefings/{id}/briefing-history?kind=route|vergleich` (`isValidBriefingKind`, `ValidEntityID`, `WithUser`). Antwort: `[{sent_at, kind, channels, on_demand}]`. `GET /api/trips/{id}/briefing-history` bleibt als Alias auf denselben Handler (`kind=route`), es entsteht kein zweiter Code.
8. **Frontend:** ein geteilter Baustein `frontend/src/lib/components/shared/BriefingHistory.svelte` (Props `id`, `kind`) als **Inline-Liste** im Reiter Übersicht, eingebunden in `trip-detail/HubOverview.svelte` und `compare/CompareTabs.svelte`. Der verwaiste `briefing-history/BriefingHistoryDialog.svelte` wird gelöscht. Der TS-Typ `BriefingLogEntry` bekommt `entity_id`/`entity_type`, `trip_id` wird optional. Die Anzeigen von `letzter_versand` bleiben unverändert (Denormalisierung).
9. **AC-3 bewusst ausgelegt (beim AC-Freigabeschritt dem PO sichtbar machen):** Archiv-Zahlen haben seit #611 keine Oberfläche, und das Cockpit zeigt heute nur Hero-Trip-Briefings (gefiltert nach `trip_id`). AC-3 wird deshalb ein **API-Vertrag**: `/api/cockpit/status` liefert je Briefing `entity_type`/`entity_id`, `/api/archive/stats` zählt nach `"trip:<id>"`/`"compare:<id>"`. Eine neue Cockpit-Oberfläche gibt es nicht. Zusätzlich wird zugesichert: Compare-Einträge erscheinen nie als Trip-Briefing in der Hero-Kachel.

### Affected Files (with changes)
| File | Change Type | Description |
|------|-------------|-------------|
| `src/services/briefing_log.py` | CREATE | gemeinsamer, gesperrter, atomarer Schreibhelfer |
| `src/services/trip_report_scheduler.py` | MODIFY | `_append_briefing_log` → Wrapper auf den Helfer (`entity_type="trip"`, `trip_id` bleibt) |
| `src/services/scheduler_dispatch_service.py` | MODIFY | `send_one_compare_preset`: Log-Eintrag nach `outcome=="sent"` |
| `src/services/briefing_slots.py` | MODIFY | Guard `entity_type in (None,"trip")` in den Log-Lesern |
| `scripts/migrate_briefing_log_mail_to_mask.py` | VERIFY | muss Compare-Einträge unverändert durchreichen (Test) |
| `internal/store/log.go` | MODIFY | Felder, Lese-Regel, `BriefingCountByEntity` statt `ByTrip` |
| `internal/store/user_scope_guard_test.go` | MODIFY | Register-Parität |
| `internal/handler/briefing_history.go` | MODIFY | kind-neutraler Handler, Trip-Alias |
| `internal/handler/archive_stats.go` | MODIFY | Zählung nach Entity |
| `internal/handler/cockpit.go` | VERIFY/MODIFY | reicht `entity_type`/`entity_id` durch |
| `internal/router/router.go` | MODIFY | Route `/api/briefings/{id}/briefing-history` |
| `internal/handler/entity_traversal_test.go` | MODIFY | Traversal-Tabelle |
| `frontend/src/lib/components/shared/BriefingHistory.svelte` | CREATE | geteilter Historien-Baustein |
| `frontend/src/lib/components/briefing-history/BriefingHistoryDialog.svelte` | DELETE | verwaist seit #611 |
| `frontend/src/lib/components/trip-detail/HubOverview.svelte` | MODIFY | Baustein einbinden (`kind="route"`) |
| `frontend/src/lib/components/compare/CompareTabs.svelte` | MODIFY | Baustein einbinden (`kind="vergleich"`), mobil + Desktop |
| `frontend/src/lib/types.ts` | MODIFY | `BriefingLogEntry` mit `entity_id`/`entity_type` |
| Tests (Python/Go/Frontend) | CREATE/MODIFY | siehe Pflicht-Tests |

### Pflicht-Tests (für /40)
- Gleiche ID für Trip und Compare im selben Log: Der Doppelversand-Schutz des Trips bleibt unberührt, der Compare-Eintrag zählt nicht als Trip-Versand.
- Nebenläufiges Schreiben (zwei Threads/Prozesse): Kein Eintrag geht verloren.
- Kaputte Log-Datei: wird beiseitegelegt (#2231), der Versand läuft weiter.
- Compare-Cron und Compare-Handversand schreiben je einen Eintrag (`on_demand` korrekt, Slot aus `tage_ab_ortstag`, Kanäle aus `sent_channels`).
- Go-Roundtrip mit einem Alt-Log, das nur `trip_id` enthält: Kein Eintrag geht verloren, die Lese-Regel greift (AC-4).
- Endpunkt: mit zwei Nutzern (Cross-User); Traversal-ID „." → 400; fehlendes `kind` → 400.
- Frontend: Der Baustein rendert im Trip- UND im Compare-Hub (Reiter Übersicht).

### Scope Assessment
- Files: ca. 17 (davon 2 CREATE, 1 DELETE)
- Estimated LoC: ca. +450 prod / ca. +350 Test → **`loc_limit_override 500` ist absehbar nötig**
- Risk Level: MEDIUM. Der Doppelversand-Schutz und der gemeinsam beschriebene Log werden berührt. Beides fangen die Kompat-Regel, der Guard und die Sperre ab, und Pflicht-Tests bewachen es.
- Kein Schnitt in Scheiben (Epics werden themenweise abgeschlossen). `/40` deckt alle vier ACs ab.

### Technical Approach
Empfohlen ist Variante B (Plan/Sonnet). Die Varianten im Vergleich:

| | A: Dialog reaktivieren | **B: Inline-Liste, ein Baustein, Alias** | C: eigener Compare-Log |
|---|---|---|---|
| Teilungsregel | ok | ok | verletzt |
| AC-2 (Reiter Übersicht) | nein (nur Knopf) | ja | ja |
| Aufwand | klein | mittel | groß |
| Risiko Doppelversand-Schutz | gering | gering | keins, aber Doppelstruktur |

Reihenfolge: Python-Helfer + Sperr-Test → Trip-Wrapper → Compare-Aufruf → Guard `briefing_slots` → Go-Lese-Regel + Roundtrip → `ByEntity` + Archiv/Cockpit → Endpunkt + Traversal/2-Nutzer → Frontend-Baustein in beiden Hubs, Dialog löschen → vor dem Commit Rebase auf `origin/main` (`trip_report_scheduler.py`/`scheduler_dispatch_service.py` sind Hotspots).

### Dependencies
- Upstream: `file_lock.exclusive_lock`/`atomic_write_json`, `lege_beschaedigte_datei_beiseite`, `get_data_dir(user_id)`, `s.WithUser`, `isValidBriefingKind`, `ValidEntityID`.
- Downstream: `briefing_slots` (Doppelversand-Schutz), Cockpit (`plannedBriefings`), Archiv-Stats, Datenexport (unverändert), Migrations-Skript.
- #2286 hängt nur über das Vokabular daran, ohne harte Abhängigkeit.

### Open Questions
- [ ] Keine technischen. Die AC-3-Auslegung (API-Vertrag statt neuer Cockpit-Oberfläche) und die Vokabular-Abweichung (`compare` statt `vergleich`) werden dem PO in `/30` bei der AC-Freigabe sichtbar vorgelegt.
