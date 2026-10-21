---
entity_id: feat_2281_vergleich_versand_historie
type: feature
created: 2026-10-21
updated: 2026-10-21
status: draft
version: "1.0"
tags: [epic-2345, versand, trip, ortsvergleich, shared, briefing-log, historie]
issue: 2281
workflow: feat-2281-vergleich-versand-historie
---

# Versand-Historie für Trip und Ortsvergleich (kind-neutraler Briefing-Log)

## Approval

- [ ] Approved

## Purpose

Der Briefing-Log (`users/<uid>/briefing_log.json`) hält fest, wann welches Briefing über welche Kanäle zugestellt wurde. Er kennt bisher nur Trips: Das Feld heißt `trip_id`, und nur der Trip-Versand schreibt hinein. Ein Ortsvergleich, der um 07:00 zugestellt wurde, hinterlässt dort keine Spur. Cockpit, Archiv-Zahlen und Versand-Historie sehen deshalb nur Trips. Ticket #2281, Epic #2345 Etappe P4 (nach #2280).

Diese Spec macht den Log **kind-neutral**: Jeder Eintrag trägt eine Kennung (`entity_id`) und eine Art (`entity_type`), beide Arten schreiben ihn, und die Historie wird im Reiter „Übersicht" beider Hubs (Trip und Ortsvergleich) als **ein geteilter Baustein** angezeigt. Alle Teile liegen in dieser einen Spec; nichts wird abgespalten.

### Begriffe (kurz übersetzt)

- **Briefing-Art** (`kind` im Web-Aufruf): `route` (Trip) oder `vergleich` (Ortsvergleich).
- **Slot** (Logfeld `kind`): `morning` oder `evening`, also Morgen- oder Abend-Briefing. Das Logfeld wird **nicht** umbenannt.
- **Kennung / Art im Log** (`entity_id` / `entity_type`): `entity_type` ist `"trip"` oder `"compare"`.
- **Lese-Regel**: Alte Einträge werden nicht umgeschrieben; beim Lesen wird fehlendes Neues aus dem Alten abgeleitet.

### Bewusste Abweichungen vom Ticket-Zielbild (begründet)

1. **`entity_type="compare"`, nicht `vergleich`.** Das Ticket schreibt `vergleich`. Der Alarm-Log (#1467) nutzt aber bereits `"trip"|"compare"`. Damit gibt es eine Dateifamilie, eine Lese-Regel, einen Zählschlüssel `"<type>:<id>"` und denselben Frontend-Filter wie bei den Alarmen. Der Web-Aufruf behält `?kind=route|vergleich`; der Go-Handler bildet `route → trip` und `vergleich → compare` ab.
2. **Schreibort sind die beiden Versand-Engstellen, nicht `dispatch_orchestrator.py`.** Das Ticket nennt den Orchestrator. Der läuft aber nur für den Zeitplan (Cron); der Handversand (`api/routers/briefings_send.py`) geht daran vorbei und bliebe ohne Eintrag. Geschrieben wird deshalb in `_send_trip_report_outcome` (Trip) und `send_one_compare_preset` (Ortsvergleich), beide über **einen** geteilten Schreib-Helfer.
3. **Frontend-Annahme des Tickets war falsch.** Der Historien-Dialog ist seit #611 in keinem Hub eingebunden (verwaist). Darum bedeutet „sichtbar in beiden Hubs": ein neuer geteilter Baustein als Inline-Liste, der verwaiste Dialog wird gelöscht.
4. **AC-3 des Tickets (Cockpit- und Archiv-Zahlen) ist als API-Vertrag ausgelegt, nicht als neue Oberfläche** (siehe AC-3 und Out-of-Scope). Das ist eine bewusste Auslegung, weil `/api/archive/stats` seit #611 keine Oberfläche hat und das Cockpit nur Hero-Trip-Briefings zeigt.

## Source

- **Python-Core:** `src/services/briefing_log.py` (neu), `src/services/trip_report_scheduler.py`, `src/services/scheduler_dispatch_service.py`, `src/services/briefing_slots.py`
- **Go-API:** `internal/store/log.go`, `internal/handler/briefing_history.go`, `internal/handler/archive_stats.go`, `internal/handler/cockpit.go`, `internal/router/router.go`
- **Frontend:** `frontend/src/lib/components/shared/BriefingHistory.svelte` (neu), `frontend/src/lib/components/trip-detail/HubOverview.svelte`, `frontend/src/lib/components/compare/CompareTabs.svelte`, `frontend/src/lib/types.ts`
- **Identifier:** `append_briefing_log`, `BriefingLogEntry`, `BriefingCountByEntity`, `GET /api/briefings/{id}/briefing-history`

## Estimated Scope

- **LoC:** produktiv ca. +450, Tests ca. +350. `loc_limit_override 500` ist absehbar nötig.
- **Files:** ca. 17 (2 CREATE, 1 DELETE) plus Tests
- **Effort:** medium. Risiko MEDIUM: berührt den Doppelversand-Schutz und einen gemeinsam beschriebenen Log; beides fangen Lese-Regel, Guard und Sperre ab, Pflicht-Tests bewachen es.

## Scope

### In Scope

- Gemeinsamer, gesperrter und atomarer Schreib-Helfer für den Briefing-Log.
- Ortsvergleich schreibt bei Zustellung einen Eintrag, per Cron und per Hand.
- Go-Lese-Regel, Zählung nach `"<type>:<id>"`, kind-neutraler Historien-Endpunkt mit Trip-Alias.
- Ein geteilter Historien-Baustein im Reiter Übersicht beider Hubs.

### Out of Scope

- **Keine neue Cockpit-Oberfläche** und keine Archiv-Seite für die Zahlen (AC-3 ist API-Vertrag).
- Keine Datei-Migration des bestehenden Logs; nur Lese-Regel.
- Keine Umbenennung des Slot-Felds `kind`; keine Änderung an Versandlogik, Kanälen, Schwellen.
- Kein eigener Compare-Log (verletzte die Trip/Compare-Teilungsregel).
- Gesundheits-Kennzahlen (#2286) hängen nur über das kind-Vokabular daran, ohne harte Abhängigkeit.

### Affected Files

| File | Change Type | Description |
|------|-------------|-------------|
| `src/services/briefing_log.py` | CREATE | gemeinsamer, gesperrter, atomarer Schreib-Helfer `append_briefing_log(user_id, entity_type, entity_id, kind, channels, on_demand, mail_to)` |
| `src/services/trip_report_scheduler.py` | MODIFY | `_append_briefing_log` wird dünner Wrapper (`entity_type="trip"`, `trip_id` bleibt zusätzlich) |
| `src/services/scheduler_dispatch_service.py` | MODIFY | `send_one_compare_preset`: Eintrag direkt nach `outcome == "sent"` |
| `src/services/briefing_slots.py` | MODIFY | Guard `entity_type in (None, "trip")` in `_log_traegt_versand` und `_log_bezeugt_versand` |
| `scripts/migrate_briefing_log_mail_to_mask.py` | VERIFY | reicht Compare-Einträge unverändert durch (Test) |
| `internal/store/log.go` | MODIFY | Felder `EntityID`/`EntityType`, `TripID` wird `omitempty`, Lese-Regel, `BriefingCountByEntity` ersetzt `BriefingCountByTrip` |
| `internal/store/user_scope_guard_test.go` | MODIFY | Methoden-Register angepasst |
| `internal/handler/briefing_history.go` | MODIFY | kind-neutraler Handler; Trip-Route als Alias |
| `internal/handler/archive_stats.go` | MODIFY | Zählung nach Entity |
| `internal/handler/cockpit.go` | VERIFY/MODIFY | reicht `entity_type`/`entity_id` durch |
| `internal/router/router.go` | MODIFY | Route `/api/briefings/{id}/briefing-history` |
| `internal/handler/entity_traversal_test.go` | MODIFY | Traversal-Tabelle um die neue Route |
| `frontend/src/lib/components/shared/BriefingHistory.svelte` | CREATE | geteilter Baustein (Props `id`, `kind`) |
| `frontend/src/lib/components/briefing-history/BriefingHistoryDialog.svelte` | DELETE | verwaist seit #611 |
| `frontend/src/lib/components/trip-detail/HubOverview.svelte` | MODIFY | Baustein einbinden (`kind="route"`) |
| `frontend/src/lib/components/compare/CompareTabs.svelte` | MODIFY | Baustein einbinden (`kind="vergleich"`), mobil und Desktop |
| `frontend/src/lib/types.ts` | MODIFY | `BriefingLogEntry` mit `entity_id`/`entity_type`, `trip_id` optional |

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `file_lock.exclusive_lock`, `atomic_write_json` | Python | Sperre und atomares Schreiben (Vorlage `alert_log._append`) |
| `lege_beschaedigte_datei_beiseite` (#2231) | Python | kaputte Log-Datei beiseitelegen |
| `get_data_dir(user_id)` | Python | Nutzerpfad des Logs |
| `briefing_slots` | Python | Doppelversand-Schutz (#1725/#1897), liest den Log |
| `AlertLogEntry`-Lese-Regel (#1467) | Go | Vorlage für Kennung und Fallback (`log.go`) |
| `s.WithUser`, `requireUser`, `isValidBriefingKind`, `store.ValidEntityID` | Go | Mandantentrennung und Eingabeprüfung |
| `shared/`-Tab-Bausteine, `HubOverview`, `CompareTabs` | Frontend | Einbindung des Bausteins |
| ADR-0031 | Entscheidung | dateibasierte Persistenz unter `data/users/` |

## Implementation Details

**Eintragsform.** Neue Einträge tragen `entity_id`, `entity_type` (`"trip"|"compare"`), `kind` (Slot `morning|evening`), `sent_at`, `channels`, `on_demand`, `mail_to`. Trip-Einträge schreiben **zusätzlich** weiter `trip_id`, weil `briefing_slots` und viele Tests es lesen. Compare-Einträge schreiben **kein** `trip_id`.

**Schreib-Helfer.** `src/services/briefing_log.py` folgt `alert_log._append`: Sperre holen, danach **frisch** lesen, Eintrag anhängen, atomar schreiben. `locked_json_rmw` ist nicht verwendbar (wirft bei fehlender oder kaputter Datei). Bei einem Parse-Fehler gilt der Pfad aus #2231 (Datei beiseitelegen, mit leerer Liste weiterschreiben), nie „stillschweigend überschreiben". Bei Sperr-Timeout wird laut protokolliert und **nie ungesperrt** geschrieben. Ein Schreibfehler kippt den Versand nicht.

**Compare-Aufruf.** In `send_one_compare_preset` direkt nach `outcome == "sent"`; das gilt für Cron und Handversand (`on_demand=True` im Handversand). Slot: `tage_ab_ortstag` 0 → `morning`, 1 → `evening`; im Handversand ebenfalls aus `tage_ab_ortstag` (Default 0 → `morning`). Kanäle kommen aus `send_result.sent_channels` (dieselbe `NotificationResult`-Quelle wie beim Trip), kein Rückgriff auf die konfigurierten Kanäle.

**Doppelversand-Schutz.** `_log_traegt_versand` und `_log_bezeugt_versand` zählen nur Einträge mit `entity_type in (None, "trip")`. Damit kann ein Compare-Eintrag mit zufällig gleicher ID den Trip-Versand nicht fälschlich als „schon gesendet" ausweisen.

**Go.** `BriefingLogEntry` bekommt `EntityID`/`EntityType`, `TripID` wird `omitempty`. Lese-Regel wie im Alarm-Log: fehlt `EntityID`, gilt `TripID`; fehlt `EntityType`, gilt `"trip"`. `BriefingCountByEntity` zählt nach `"<type>:<id>"` und ersetzt `BriefingCountByTrip` (kein Frontend-Nutzer). Neuer Endpunkt `GET /api/briefings/{id}/briefing-history?kind=route|vergleich` (Prüfung per `isValidBriefingKind` und `ValidEntityID`, Nutzer über `WithUser`); Antwort `[{sent_at, kind, channels, on_demand}]`. `GET /api/trips/{id}/briefing-history` ruft denselben Handler mit `kind=route` auf (kein zweiter Code).

**Frontend.** `shared/BriefingHistory.svelte` ist eine Inline-Liste (Slot-Beschriftung Morgen/Abend, Kanäle, Zeitpunkt, Kennzeichnung „von Hand"), eingebunden im Reiter Übersicht beider Hubs. Die Anzeigen von `letzter_versand` (`CompareTabs`, `SubscriptionCard`, `homeCompareTimeline`) bleiben unverändert. Die Cockpit-Filterung `plannedBriefings` bleibt auf Trips beschränkt (Typ-Prüfung nach dem Muster `alertsForTrip`).

## Expected Behavior

- **Input:** zugestellter Versand (Cron oder Hand) eines Trips oder Ortsvergleichs; `GET /api/briefings/{id}/briefing-history?kind=…`.
- **Output:** ein Log-Eintrag je Zustellung; Historien-Liste je Briefing, neueste zuerst wie bisher.
- **Side effects:** `users/<uid>/briefing_log.json` wächst um einen Eintrag; keine Änderung an Bestandseinträgen.

## Acceptance Criteria

- **AC-1:** Given ein Ortsvergleich wird zugestellt, per Zeitplan (Cron) oder per Hand-Versand, When der Versand an den Kanälen erfolgreich war, Then steht im Briefing-Log des Nutzers genau ein neuer Eintrag mit `entity_type="compare"` (nicht `vergleich`, bewusste Abweichung vom Ticket, gleiche Kennzeichnung wie im Alarm-Log #1467), der Preset-Kennung als `entity_id`, dem Slot aus `tage_ab_ortstag` (0 = morning, 1 = evening), den tatsächlich zugestellten Kanälen und `on_demand` = wahr bei Handversand bzw. falsch bei Cron, und kein `trip_id`. Wirkort: die beiden Versand-Engstellen `_send_trip_report_outcome` und `send_one_compare_preset` (nicht `dispatch_orchestrator.py`, denn der Handversand ginge daran vorbei); der Trip schreibt weiterhin, jetzt mit `entity_type="trip"` und zusätzlich `trip_id`.

- **AC-2:** Given ein Nutzer öffnet den Reiter Übersicht eines Trips oder eines Ortsvergleichs, When die Seite geladen ist, Then zeigt in beiden Hubs derselbe geteilte Baustein `shared/BriefingHistory.svelte` die bisherigen Zustellungen als Liste (Slot, Kanäle, Zeitpunkt, „von Hand" gekennzeichnet) oder einen Leerzustand, und der verwaiste Dialog `briefing-history/BriefingHistoryDialog.svelte` existiert nicht mehr. Wirkort: gerenderte Hub-Seiten (`HubOverview.svelte` und `CompareTabs.svelte`), nicht nur der Baustein allein.

- **AC-3:** Given der Briefing-Log enthält Einträge von Trips und Ortsvergleichen, When `/api/cockpit/status` und `/api/archive/stats` aufgerufen werden, Then liefert der Cockpit-Status je Briefing-Eintrag `entity_type` und `entity_id`, die Archiv-Zahlen zählen nach den Schlüsseln `"trip:<id>"` und `"compare:<id>"` (gleiche ID bei Trip und Ortsvergleich ergibt zwei getrennte Zähler), und ein Compare-Eintrag erscheint nie als Trip-Briefing in der Hero-Kachel des Cockpits. Dies ist bewusst als API-Vertrag ausgelegt, nicht als neue Cockpit- oder Archiv-Oberfläche. Wirkort: Go-Handler `cockpit.go` und `archive_stats.go` sowie der Hero-Filter `plannedBriefings` im Frontend.

- **AC-4:** Given ein bestehender Briefing-Log, der nur Einträge mit `trip_id` (ohne `entity_id`/`entity_type`) enthält, When Go ihn liest und über Cockpit, Archiv-Zahlen und Historie ausgibt, Then geht kein Eintrag verloren, jeder Alt-Eintrag erscheint mit `entity_type="trip"` und `entity_id` = altem `trip_id`, und die Datei auf der Platte bleibt unverändert (Lese-Regel, keine Datei-Migration). Wirkort: Go-Lesepfad `LoadBriefingLog`, geprüft als Roundtrip Datei → Go → JSON.

- **AC-5:** Given ein Trip und ein Ortsvergleich haben dieselbe ID und stehen im selben Log, When der Doppelversand-Schutz prüft, ob der Trip-Slot schon zugestellt wurde, Then zählt der Compare-Eintrag nicht als Trip-Versand: ein Trip-Briefing wird nicht unterdrückt, nur weil ein Ortsvergleich mit gleicher ID gesendet hat, und ein echter Trip-Eintrag schützt weiterhin vor Doppelversand. Wirkort: `briefing_slots._log_traegt_versand` und `_log_bezeugt_versand`.

- **AC-6:** Given Trip-Cron, Ortsvergleich-Cron und Handversand schreiben gleichzeitig in denselben Briefing-Log, When mehrere Schreibvorgänge zeitlich überlappen, Then enthält die Datei danach jeden einzelnen Eintrag und ist gültiges JSON (Sperre plus atomares Ersetzen, kein verlorener Eintrag). Wirkort: Schreib-Helfer `append_briefing_log`, geprüft mit parallelen **Threads im selben Prozess** (so laufen Handversand im FastAPI-Threadpool und Scheduler im Python-Core tatsächlich; `exclusive_lock` nutzt `flock` mit eigenem Dateideskriptor je Aufruf und sperrt deshalb auch zwischen Threads) und zusätzlich mit parallelen Prozessen.

- **AC-11:** Given zwei Nutzer A und B, die je einen Ortsvergleich bzw. Trip besitzen, When A per Cron und per Hand zustellt, Then landen die Einträge ausschließlich in `data/users/A/briefing_log.json` — nie in der Datei von B und nie unter `default`; fehlt die `user_id`, wird nichts geschrieben (kein Rückfall auf `default`). Wirkort: Schreib-Helfer, aufgerufen mit der `user_id` aus `send_one_compare_preset` bzw. `_send_trip_report_outcome`.

- **AC-7:** Given die Log-Datei des Nutzers ist kaputt (kein gültiges JSON), When ein Versand zugestellt wird, Then wird die kaputte Datei beiseitegelegt (wie #2231), der Versand läuft normal weiter und meldet Erfolg, und der neue Eintrag steht in einer frischen Datei; ein Schreibfehler am Log lässt den Versand nie scheitern. Wirkort: Schreib-Helfer, aufgerufen aus beiden Engstellen.

- **AC-8:** Given zwei verschiedene Nutzer mit je eigenem Briefing, When `GET /api/briefings/{id}/briefing-history?kind=…` aufgerufen wird, Then sieht jeder Nutzer nur die Einträge seiner eigenen Datei: eine fremde oder unbekannte ID ergibt HTTP 200 mit leerer Liste `[]` (wie der bestehende Trip-Handler heute; keine Existenzprüfung, damit AC-9 die Antwort des Trip-Aufrufs nicht verändert), eine ungültig geformte ID wie `.` oder `..` ergibt 400, und ein fehlendes oder ungültiges `kind` ergibt 400. Wirkort: Go-Handler `briefing_history.go` mit `WithUser`, Router und Traversal-Test.

- **AC-9:** Given ein Trip mit bisherigen Zustellungen, When der bestehende Aufruf `GET /api/trips/{id}/briefing-history` benutzt wird, Then liefert er dieselben Einträge in derselben Form wie `GET /api/briefings/{id}/briefing-history?kind=route`, ohne eigene zweite Implementierung. Wirkort: Go-Router und -Handler (Alias auf denselben Handler).

- **AC-10:** Given ein Ortsvergleich mit gespeichertem `letzter_versand`, When der neue Log-Eintrag geschrieben wird und die Anzeigen gerendert werden, Then zeigen `CompareTabs`, `SubscriptionCard` und die Home-Zeitleiste `letzter_versand` unverändert wie zuvor (der Wert wird weiterhin im Preset gespeichert, nicht aus dem Log abgeleitet). Wirkort: Preset-Speicherpfad `save_compare_preset_status` und die Frontend-Anzeigen.

## Test Plan

Testdateien sind nach Verhalten benannt, nie nach Issue-Nummer.

### Automated Tests (TDD RED)

**Kern-Schicht (deterministisch, ohne Netz):**

- [ ] Test 1: GIVEN ein Ortsvergleich mit Preset-Kennung und Slot 0/1 WHEN er per Cron und per Hand zugestellt wird THEN steht je ein Eintrag mit `entity_type="compare"`, richtigem `kind`, `on_demand` und `sent_channels`, ohne `trip_id` (`tests/tdd/test_briefing_log_vergleich_eintrag.py`, AC-1).
- [ ] Test 2: GIVEN ein Trip WHEN er zugestellt wird THEN trägt der Eintrag `entity_type="trip"`, `entity_id` und weiterhin `trip_id` (`tests/tdd/test_briefing_log_vergleich_eintrag.py`, AC-1).
- [ ] Test 3: GIVEN Trip und Ortsvergleich mit gleicher ID im selben Log WHEN der Doppelversand-Schutz prüft THEN zählt nur der Trip-Eintrag (`tests/tdd/test_briefing_slots_id_kollision.py`, AC-5).
- [ ] Test 4: GIVEN mehrere parallele Schreiber (Threads im selben Prozess UND getrennte Prozesse) WHEN alle anhängen THEN sind alle Einträge vorhanden und die Datei ist gültig (`tests/tdd/test_briefing_log_nebenlaeufig.py`, AC-6).
- [ ] Test 5: GIVEN eine kaputte Log-Datei WHEN ein Versand zugestellt wird THEN wird sie beiseitegelegt und der Versand meldet Erfolg (`tests/tdd/test_briefing_log_kaputte_datei.py`, AC-7).
- [ ] Test 6: GIVEN ein Log mit Compare-Einträgen WHEN `migrate_briefing_log_mail_to_mask.py` läuft THEN bleiben sie unverändert (AC-1, Datenerhalt).
- [ ] Test 7: GIVEN ein Alt-Log nur mit `trip_id` WHEN Go liest und Cockpit/Archiv/Historie ausgibt THEN geht nichts verloren und die Datei bleibt byte-gleich (`internal/store/briefing_log_lese_regel_test.go`, AC-4).
- [ ] Test 8: GIVEN gleiche ID bei Trip und Ortsvergleich WHEN Archiv-Zahlen und Cockpit-Status abgefragt werden THEN gibt es `trip:<id>` und `compare:<id>` getrennt, Typ und Kennung stehen im Cockpit-Eintrag (`internal/handler/archive_stats_briefing_test.go`, `cockpit_briefing_entity_test.go`, AC-3).
- [ ] Test 9: GIVEN zwei Nutzer mit gleichlautenden IDs WHEN beide den Historien-Endpunkt aufrufen THEN sieht jeder nur Eigenes; ID `.` ergibt 400; fehlendes und ungültiges `kind` ergibt 400 (`internal/handler/briefing_history_test.go`, `entity_traversal_test.go`, AC-8).
- [ ] Test 10: GIVEN dieselben Daten WHEN der Trip-Alias und der neue Endpunkt mit `kind=route` aufgerufen werden THEN sind die Antworten gleich (`internal/handler/briefing_history_test.go`, AC-9).
- [ ] Test 11: GIVEN der Scope-Guard WHEN die Store-Methoden per Reflection verglichen werden THEN stimmt das Register (`internal/store/user_scope_guard_test.go`).
- [ ] Test 12: GIVEN Cockpit-Daten mit Compare-Eintrag WHEN `plannedBriefings` für den Hero-Trip läuft THEN erscheint der Compare-Eintrag nicht (`frontend/src/routes/_home/cockpitHelpers.test.ts`, AC-3).
- [ ] Test 13: GIVEN Trip-Hub und Ortsvergleich-Hub WHEN der Reiter Übersicht gerendert wird THEN zeigt jeder `BriefingHistory` mit Einträgen bzw. Leerzustand; der Dialog-Import ist weg (`frontend/src/lib/components/shared/briefing_history_hubs.test.ts`, AC-2).
- [ ] Test 15: GIVEN Nutzer A und B WHEN A einen Ortsvergleich per Cron und per Hand zustellt und A einen Trip zustellt THEN stehen alle Einträge nur in As Log, Bs Log und `default` bleiben unberührt; ohne `user_id` wird nichts geschrieben (`tests/tdd/test_briefing_log_nutzer_isolation.py`, AC-11).
- [ ] Test 14: GIVEN ein Ortsvergleich mit `letzter_versand` WHEN `CompareTabs` und `SubscriptionCard` rendern THEN bleibt die Anzeige unverändert (bestehende Tests bleiben grün, AC-10).

**Mutations-Gegenproben (Adversary):** `entity_type` im Compare-Eintrag auf `"trip"` setzen, den Guard in `briefing_slots` entfernen, die Sperre im Helfer weglassen, die Lese-Regel in Go entfernen, die ID-Prüfung des Endpunkts entfernen, den Compare-Aufruf in `send_one_compare_preset` entfernen. Jede Verfälschung muss genau den zuständigen Test rot machen.

**Live-Schicht (nur `/e2e-verify`):** auf Staging mit Wegwerf-Nutzer `gregor-test+…` je ein Handversand von Trip und Ortsvergleich durch die Oberfläche und Sichtprüfung der Historie im Reiter Übersicht beider Hubs.

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** keine
- **Rationale:** Keine ADR wird berührt oder abgelöst. Persistenzort und -form bleiben wie in ADR-0031 (`data/users/<user_id>/briefing_log.json`, ein JSON-Objekt). Die neuen Felder `entity_id`/`entity_type` folgen dem bereits gelieferten Muster des Alarm-Logs (#1467, Lese-Regel statt Migration). Eine neue ADR ist deshalb nicht nötig.

## Datenerhalt

- Bestehende `briefing_log.json`-Dateien werden **nicht** umgeschrieben (Lese-Regel). Neue Einträge werden per Lesen-Ändern-Schreiben mit Sperre angehängt, Bestandseinträge bleiben feldweise unverändert.
- Trip-Einträge behalten `trip_id`, damit Doppelversand-Schutz und Bestandstests unverändert funktionieren.
- `briefing_log.json` ist bereits im Datenexport; keine Änderung nötig.
- `internal/store/log.go` ist schema-relevant; der Pre-Snapshot-Hook sichert vor dem Edit automatisch.

## Risiken

| Risiko | Absicherung |
|---|---|
| ID-Kollision Trip/Compare löst oder blockiert Trip-Versand | Guard `entity_type in (None,"trip")`, AC-5 |
| Verlorener Eintrag bei mehreren Schreibern | Sperre + atomares Schreiben, AC-6 |
| Kaputte Datei blockiert Versand | Beiseitelegen, Versand läuft weiter, AC-7 |
| Fremde Nutzerdaten über neuen Endpunkt | `WithUser`, ID-Prüfung, Zwei-Nutzer-Test, AC-8 |
| Alt-Einträge verschwinden aus Cockpit/Archiv | Lese-Regel, AC-4 |
| Hotspot-Dateien (`trip_report_scheduler.py`, `scheduler_dispatch_service.py`) | vor dem Commit auf `origin/main` rebasen |

## Known Limitations

- **Restfenster beim Beiseitelegen:** `briefing_slots._repair_locked` legt den Log unter der Slot-Sperre beiseite, nicht unter der Log-Sperre. Der Schreib-Helfer liest nach dem Erhalt der Sperre frisch; im ungünstigen Fall landet ein Eintrag in einer gerade beiseitegelegten Datei. Das gilt schon heute und wird hingenommen.
- Archiv-Zahlen haben weiterhin keine Oberfläche (seit #611); diese Spec liefert nur den API-Vertrag.
- Alt-Einträge behalten dauerhaft das Format mit `trip_id`; die Lese-Regel bleibt damit dauerhaft nötig.
- `entity_type` ist ein freier Text. Ein Tippfehler an einer künftigen Aufrufstelle erzeugt einen neuen Typ statt eines Fehlers (wie im Alarm-Log).

## Changelog

- 2026-10-21: Initial spec created (Ticket #2281, Epic #2345 Etappe P4)
