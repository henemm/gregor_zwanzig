---
entity_id: fix_1405_s4b_erfolg_heisst_wirkung
type: module
created: 2026-10-26
updated: 2026-10-26
status: draft
version: "1.1"
tags: [erfolg-heisst-wirkung, waechter, issue-1405, scheduler, inbound, briefing, notification-service]
---

<!-- Issue #1405 Scheibe S4b (Wächter 2, "Erfolg heißt Wirkung"): die letzten 8 Einträge in KNOWN_VIOLATIONS.
     Kontext + Analyse (verbindlich): docs/context/fix-1405-s4b-erfolg-heisst-wirkung.md
     Vorgänger: docs/specs/modules/feat_1405_s4a_befehlsantwort_erfolg_wirkung.md (Stil, Ratsche)
     Wächter-Spec: docs/specs/modules/waechter_1405_erfolg_wirkung.md
     ADR-0086: sent = zugestellt; failed_channels speist den Alarm-Backoff. -->

# Erfolg heißt Wirkung außerhalb der Befehlsverarbeitung — Scheibe S4b

## Approval

- [ ] Approved

## Purpose

Der Wächter `tests/test_success_status_guard.py` führt noch **8 Stellen**, an denen das System
"alles in Ordnung" meldet, obwohl etwas schiefgegangen sein kann. Für den Nutzer heißt das: ein
Briefing kommt nicht an, ein Befehl wird nicht beantwortet oder das Postfach ist nicht erreichbar —
und die Statusseite (`/api/scheduler/status`) und das Monitoring zeigen trotzdem grün. Diese Scheibe
macht den Fehler dort sichtbar, wo er wirkt, und leert die Liste der bekannten Verstöße von 8 auf 0.

| # | Stelle | Was heute still bleibt | Danach |
|---|--------|------------------------|--------|
| 1 | Ortsvergleich-Alarmlauf (`trigger_compare_alert_checks`) | Fehler werden gezählt, Status steht fest auf "ok" | Status "partial", sobald ein Fehler gezählt wurde |
| 2 | Befehls-Posteingang-Lauf (`trigger_inbound`) | Status fest "ok" | meldet `failed` + Status; Go-Laufstatus wertet es aus |
| 3 | Posteingang lesen (`poll_and_process`) | Verarbeitungs-, Versand- und IMAP-Fehler nur im Log | zählt sie als Fehler des Laufs |
| 4 | Telegram-Hinweis "Briefing unvollständig" (Briefing-Pfad und Ortsvergleich-Änderungsalarm) | Fehlschlag nur im Log | Fehlschlag steht als `notice_failed` in der Antwort des Laufs (`/trip-reports`, `/compare-alert-checks`), Status `partial` (nicht `failed`) |
| 5 | Befehlsantwort per E-Mail (`send_command_reply_email`) | nicht zugestellte Antwort unbemerkt | meldet Zustellung; Nicht-Zustellung zählt als Fehler des Posteingang-Laufs |
| 6 | Service-Fehlermail für SMS-only-Trips | Fehlschlag nur im Log | Fehlschlag steht als `notice_failed` in der Antwort des Laufs, Status `partial` (nicht `failed`) |
| 7 | `send_reports` (toter Code, kein Aufrufer) | Zähler ohne Gegenzähler | wird gelöscht |
| 8 | Nachlieferung offener Briefings (`_process_pending_markers`) | gescheiterte Nachlieferung unsichtbar | zählt `failed` und reicht es in die Lauf-Bilanz |

**Alle vier Kanäle sind gleichrangig.** Diese Scheibe ändert **keinen Versandweg** (kein Kanal wird
bevorzugt, keiner bekommt einen neuen Text): sie macht nur Fehlschläge sichtbar. Der Briefing-Hinweis
(#4) betrifft Telegram, die Fehlermail (#6) betrifft den SMS-Nutzer, die Befehlsantwort (#5) den
E-Mail-Eingang; die Nachlieferung (#8) und der Ortsvergleich-Lauf (#1) gelten für alle Kanäle.

**Keine Handlungsempfehlung im Produkt:** es kommen keine neuen Nutzertexte hinzu. Es werden nur
Zahlen (`failed`) und Status (`partial`) ergänzt.

## Source

- **Files (Python-Core):**
  `api/routers/scheduler.py` (#1, #2), `src/services/inbound_email_reader.py` (#3, #5),
  `src/services/notification_service.py` (#4, #5, #6, Feld `notice_failures` in `NotificationResult`),
  `src/services/trip_report_scheduler.py` (#7 löschen, #8, Leser des Feldes, Zähler `notice_failed`),
  `src/services/dispatch_orchestrator.py` (`TripDispatchStrategy`: Bilanz + `notice_failed`),
  Alarm-Leser (nur noch einer): `src/services/compare_alert.py` (:444, `CompareAlertService.last_notice_failed`)
- **Files (Go):** `internal/scheduler/push_kick.go` (`pollRun`), `internal/scheduler/scheduler.go`
  (neuer Auswerte-Pfad für `/api/scheduler/inbound-commands`, Spiegel von `triggerPremiumSmsPollEndpointRes`)
- **Files (Wächter/Tests):** `tests/test_success_status_guard.py` (Wächter-Korrektur Klasse 2 + Ratsche),
  `tests/tdd/test_erfolg_heisst_wirkung_s4b.py` (NEU, Verhaltenstests), Go-Test
  `internal/scheduler/scheduler_inbound_status_test.go` (NEU), benannte Alt-Tests siehe unten
- **Files (Doku):** `docs/reference/api_contract.md`, `docs/specs/modules/trip_report_scheduler.md`,
  `docs/specs/modules/waechter_1405_erfolg_wirkung.md` (Changelog), `docs/reference/gates_und_ratschen.md`
  (falls dort Zahlen genannt sind)
- **Identifier:** `trigger_compare_alert_checks`, `trigger_inbound`, `InboundEmailReader.poll_and_process`,
  `_process_single`, `last_failed_count`, `_send_telegram_incomplete_hint`, `_send_service_error_email`,
  `send_command_reply_email`, `NotificationResult.notice_failures`, `TripReportSchedulerService.notice_failed`,
  `CompareAlertService.last_notice_failed`, `_process_pending_markers`, `TripDispatchStrategy.pre_pass/result`, `pollRun`
- **Nicht im Umfang:** die 22 Funde des Auflösungs-Wächters (`test_resolution_loss_guard.py`) und S3 —
  eigene Folgescheiben im selben Ticket #1405 (nicht abgespalten, nur andere Scheiben).

## Estimated Scope

- **Effort:** high (27 ACs, Python + Go, Ortsvergleich-Änderungsalarm zusätzlich zum Briefing-Lauf).
- **LoC produktiv:** ca. +250 / −80 (Python ~7 Dateien inkl. Alarm-Leser, Go 2 Dateien; Tests zählen
  nicht). Das liegt voraussichtlich über 250 → `workflow.py set-field loc_limit_override 500` ist vorab
  einzuplanen (erwarteter Schritt, **nicht abspalten** — die 8 Funde
  gehören zusammen, sonst verrutschen die Anker der Ratsche).
- **Risiko:** MITTEL. Versandpfade selbst bleiben unverändert; neu ist die Wirkung auf Statusseite und
  Monitoring (siehe Risiken).

## Dependencies

| Entity | Typ | Zweck |
|--------|-----|-------|
| `trigger_trip_reports`, `trigger_compare_presets_daily` (`scheduler.py`) | Muster | `status = "partial" if failed > 0 else "ok"`, HTTP 200 |
| `trigger_inbound_sms` + `inbound_sms_reader.last_failed_count` | Muster | Reader setzt Attribut, Router liest es, `status="partial"` |
| `triggerPremiumSmsPollEndpointRes` (`scheduler.go:941-985`) | Muster Go | Auswertung von `failed`/`partial` für einen Poll-Lauf |
| `TripReportSchedulerService.collect_failed` + `TripDispatchStrategy.collect_due` | Muster | Zähler am Dienst, Orchestrator addiert ihn zur Bilanz (#2217) |
| `dispatch_one` (`dispatch_orchestrator.py:78-106`) | Muster | Outcome-Einordnung: sent → sent, `no_channels`/`no_stage` neutral, Rest failed |
| `kickRound` (`push_kick.go:152-169`) | Sperre | Nachversuche hängen nur an `Processed`/`Busy` — ein Fehlerfeld löst nichts aus |
| `scripts/check-gregor20.sh` (henemm-infra) | Monitoring | alarmiert bei `error`; `partial` wird nicht ausgewertet |

## Implementation Details

**0. Wächter-Korrektur zuerst (Klasse 2).** Der Wächter liest heute als Fehlerzähler nur Zähler im
`except`-Handler (`_failure_counter_names`); sein Docstring verspricht aber auch den "Fehlausgangs-Zweig".
Das ist ein Wächter-Fehler und wird **korrigiert, nicht umgangen**: zusätzlich gilt ein lokaler Zähler als
Fehlerzähler, wenn er im `orelse` eines `if` hochgezählt wird, dessen Rumpf einen **Geschwister-Erfolgszähler**
(derselbe Funktionsrumpf, im Rückgabewert verwendet) erhöht. Ein beliebiges `else: failed += 1` genügt nicht.
Die AC-8-Attrappe (`failed = 0`, nie erhöht) bleibt ein Fund. Kein künstliches `try/except` zur Beruhigung.

**1. `trigger_compare_alert_checks`:** `status = "partial" if failed else "ok"` aus der Variablen, wie
`trigger_trip_reports`. Keine Go-Änderung (Go wertet `failed>0` schon als Fehler, `scheduler.go:1176`).

**2. `trigger_inbound`:** die Antwort bekommt `failed` (aus `reader.last_failed_count`, direkter
Attributzugriff wie `trigger_inbound_sms`) und `status = "partial" if failed else "ok"`; `skipped`/`busy`
unverändert. Python wird vor Go ausgeliefert (Go liest ein fehlendes Feld als 0, abwärtskompatibel).
Go: `pollRun` bekommt einen eigenen Zweig für `inbound-commands` (Spiegel von
`triggerPremiumSmsPollEndpointRes`): `fillPollResult` plus `Failed>0` → Laufstatus `error`,
`status=="partial"` → `partialRunError`. `triggerGlobalEndpoint` bleibt für andere Jobs unverändert.

**3. `poll_and_process` + `_process_single` (#3/#5):** `_process_single` liefert `(processed, failed)`.
`failed += 1` im inneren Handler (Verarbeitungs-/Versandfehler, `return 0` heute), wenn die Befehlsantwort
nicht zugestellt wurde (`send_command_reply_email -> bool`, inkl. `trip_not_found`), sowie in den
`IMAP4.error`-/`OSError`-Handlern der Schleife. `poll_and_process` bleibt `-> int` und setzt
`self.last_failed_count`. Fehlende Zugangsdaten bleiben `skipped`; `can_send_email()` falsch = kein
Versuch = kein Fehler. Eine Mail, die ohne Befehl/Trip-Klammer verworfen wird, ist kein Fehler.

**4. B21 — `_send_telegram_incomplete_hint`, `_send_service_error_email`, `send_command_reply_email`:**
alle drei liefern `bool` (`True` = zugestellt bzw. nicht erforderlich, `False` = Versuch gescheitert;
Ausnahme wird weiter gefangen, aber nicht mehr verschluckt). **Nicht erforderlich** gilt auch für
`_send_service_error_email`: ist der Trip SMS-only und kein Mailversand eingerichtet (`can_send_email()`
falsch), gibt es keinen Versuch und die Funktion liefert `True` (Fix-Loop 1, B21 „nicht erforderlich“,
analog AC-4); `False` steht nur für einen tatsächlich gescheiterten Versuch.

**B21 — Endstatus ehrlich festgelegt (Abwägung):** Go wertet in `triggerEndpointForUser`
(`scheduler.go:1176-1180`) **jedes** `failed>0` als `error`; für `trip_reports_hourly` und
`compare_presets_daily` alarmiert das Monitoring (`check-gregor20.sh`) dann sofort. Ein gescheiterter
Hinweis bei einem **zugestellten** Briefing/Alarm ist aber kein verpasstes Briefing. Deshalb:
Hinweis-/Fehlermail-Fehlschläge kommen in ein **eigenes Antwortfeld `notice_failed`** und setzen
`status="partial"` — **nicht** `failed`. Go verbucht `partial` ohne `failed` über den Zweig
`parsed.Status == "partial"` (`scheduler.go:1196-1200`) als `partialRunError`; `runJob` schreibt
daraufhin `last_run.status = "partial"` (`scheduler.go:1069-1075`), im Fan-out gilt die Rangfolge
error > partial > ok (`:402-404`, `:489-495`). Der Lauf steht im Status damit **nicht mehr auf "ok"**,
löst aber keinen Sofort-Alarm aus. `failed` bleibt echten Zustellausfällen vorbehalten (z. B. #8:
Nachlieferung gescheitert = Briefing verpasst). Das gilt nur, solange das Briefing/der Alarm selbst
zugestellt ist; ist nichts zugestellt, greift wie bisher der Fehlerpfad (`failed`/Ausnahme).

**B21-Leserfrage — entschieden (Codelesen):**
- Alle drei Funktionen liefern `bool`. `NotificationResult` bekommt `notice_failures: list[str]`
  (`"telegram_incomplete_hint"`, `"service_error_email"`), **bewusst getrennt** von `failed_channels`
  (ADR-0086: Backoff, Throttle und `delivery_outcome` bleiben unberührt).
- **Briefing-Pfad:** `send_trip_report` (`:898`/`:906`) schreibt die Fehlschläge ins Feld. **Leser:**
  `_send_trip_report_outcome` (~:1993) zählt `self.notice_failed += len(...)`. Die Strategie
  (`TripDispatchStrategy`) hält die Summe; der Tupelvertrag `(sent, failed)` von `run_briefing_dispatch`
  bleibt unverändert, `notice_failed` wird getrennt an die aufrufende Instanz zurückgegeben (z. B.
  `service.last_notice_failed`, Mechanik freie Wahl, Muster `last_failed_count`). **Wirkstelle:**
  `trigger_trip_reports` (`api/routers/scheduler.py:81-92`): `status = "partial"` bei
  `failed > 0 or notice_failed > 0`, die Antwort enthält `notice_failed`.
- **Alarm-Pfad — reduziert auf den Ortsvergleich-Änderungsalarm (PO-Entscheid 2026-10-26):** Den
  Hinweis „Briefing unvollständig“ und damit `NotificationResult.notice_failures` kann im Alarm-Pfad nur
  `send_multi_location_deviation_alert` erzeugen (Telegram-Auffächerung je Ort,
  `notification_service.py:2098-2158`). Trip-Abweichungsalarm, Trip-Radaralarm und Ortsvergleich-Radaralarm
  senden genau **eine** Telegram-Nachricht: sie kommt an oder scheitert komplett, dann greift der
  Transportfehlerweg (`RuntimeError`, `failed`). Dort entsteht kein Hinweis, ein Zähler wäre immer 0 und
  damit ein Leser ohne Wirkung. Deshalb entfallen die Leser in `trip_alert.py` (:2849/:3076) und
  `compare_radar_alert.py` (:423) sowie das Feld `notice_failed` an `/alert-checks`,
  `/radar-alert-checks` und `/compare-radar-alert-checks`; diese beiden Dateien und die drei Router
  bleiben unverändert (Stand `origin/main`). **Einziger Alarm-Leser:**
  `compare_alert.py:444` (`send_multi_location_deviation_alert`) zählt `len(result.notice_failures)` in
  `CompareAlertService.last_notice_failed` (Muster `last_failed_count`). **Wirkstelle:** der Router
  `/compare-alert-checks` (`api/routers/scheduler.py`): die Antwort enthält `notice_failed`,
  `status="partial"` bei `notice_failed > 0` (Go-Zweig wie oben). **Abwägung analog zum Briefing:** der
  Alarm ist zugestellt (mindestens eine Teil-Nachricht kam an, sonst Transportfehler), nur der Hinweis
  fehlt; `error` wäre ein Fehlalarm, `ok` eine Lüge. Throttle, Backoff und `failed_channels` bleiben
  unverändert. Ein bloßes zusätzliches Log ist ausdrücklich **keine** Verwertung (der Hinweis loggt heute
  schon `logger.error`, `notification_service.py:950`).
- **Mandantentrennung des Zählers (Codelesen):** Die Zähler hängen an Instanzen, die **je Anfrage/Lauf
  und je Nutzer neu gebaut** werden: `send_due_reports` delegiert an `run_briefing_dispatch`, das je
  Aufruf eine **neue** `TripDispatchStrategy` mit **neuem** `TripReportSchedulerService(user_id=...)`
  erzeugt (`dispatch_orchestrator.py:56`); die Router bauen `TripReportSchedulerService(user_id=user_id)`
  und `CompareAlertService(user_id=user_id)` je Anfrage; Go ruft je
  Nutzer einzeln auf (`triggerEndpointForUser`). Es gibt keine zwischen Nutzern oder Läufen geteilte
  Instanz. Zurückgesetzt wird beim Anlegen der Instanz (Default 0) und zusätzlich zu Beginn des
  Sammellaufs in `_collect_due_trips` (Muster `collect_failed`, `trip_report_scheduler.py:839`);
  `CompareAlertService.last_notice_failed` setzt am Anfang des Alarmlaufs auf 0 zurück. Kein
  `"default"`-Fallback.

**5. #7:** `send_reports` wird gelöscht (kein Produktionsaufrufer; Präzedenz B13/#1407). Mitziehen:
`tests/e2e/test_e2e_story3_reports.py:455-464`, Zähl-Anker `tests/tdd/test_pytest_collection_and_timeout_safety.py:171`
(Anker bleibt bei 13, siehe AC-16), `tests/tdd/test_issue_339_verify_timing.py:133`, Docstring `:673`,
`docs/specs/modules/trip_report_scheduler.md`.

**6. #8:** `_process_pending_markers -> tuple[int, int]` (`delivered`, `failed`), ausgewertet an beiden
Sendestellen (`:1029` Versandfehler-Marker, `:1065` Daten-Nachlieferung) nach Outcome-Einordnung wie
`dispatch_one`: `sent` → delivered; `no_channels`/`no_stage` → neutral; `no_weather`/`channels_unreachable`
→ failed. `TripDispatchStrategy.pre_pass` addiert beide Werte (`self._sent += d; self._failed += f`).
`already_in_progress` tritt hier nicht auf (der Sperr-Lock sitzt nur in `send_test_report_outcome`).
Liefert ein zuvor fehlendes Segment weiter keine Daten, wird gar nicht gesendet (Lärmschutz #1012,
`attempts += 1`): kein Outcome, kein `failed`.

**Verboten (Gaming, Adversary wertet als BROKEN):** künstliches `try/except` nur zur Scanner-Beruhigung;
ein Rückgabewert/Feld, das kein Aufrufer liest; `getattr(reader, "last_failed_count", 0)` oder jeder
andere Stillrückfall im Produkt (Fakes setzen das Attribut selbst); Statuswert aus Konstante mit
Umbenennung; `failed_channels`/`delivery_outcome` für Hinweis-Fehlschläge zweckentfremden.

## Expected Behavior

- **Input:** Läufe des Schedulers (Ortsvergleich-Alarm, Briefing-Lauf inkl. Nachlieferung,
  Befehls-Posteingang) für je einen Nutzer.
- **Output:** `/api/scheduler/status` zeigt `partial`/`error` genau dann, wenn im Lauf wirklich etwas
  gescheitert ist; sonst `ok`.
- **Side effects:** keine zusätzlichen Nachrichten an Nutzer, keine Nachversuche (Seen-Markierung und
  Marker-Entfernung bleiben, wie sie sind).

## Acceptance Criteria

### A. Ortsvergleich-Alarmlauf (#1)

- **AC-1:** Given der Ortsvergleich-Alarmlauf eines Nutzers, bei dem mindestens ein Ortsvergleich mit einem Fehler scheitert / When der Lauf endet / Then steht in der Antwort `failed >= 1` und `status == "partial"` (nicht "ok"), und `/api/scheduler/status` zeigt für diesen Lauf nach dem Go-Durchlauf einen Fehler-/Teilfehler-Zustand; läuft alles durch, bleibt `status == "ok"` und `failed == 0`.
  - Test: echter Lauf mit einem Ortsvergleich, dessen Prüfung wirft (Fake-Quelle), plus Gegenprobe ohne Fehler; Aufrufer-Verwertung gegen den Go-Pfad `triggerEndpointForUser` (`failed>0` → error) bzw. `partialRunError`.

### B. Befehls-Posteingang (#2, #3, #5)

- **AC-2:** Given das Postfach des Befehls-Eingangs ist nicht erreichbar (IMAP-Anmeldefehler oder Netzwerkfehler) / When der Lauf `POST /api/scheduler/inbound-commands` ausgeführt wird / Then antwortet er mit `failed >= 1` und `status == "partial"` statt `"ok"`; bei fehlenden Zugangsdaten bleibt `status == "skipped"` (kein Fehler), bei laufender Sperre `status == "busy"`.
  - Test: echter Router-Aufruf mit IMAP-Fake, der `login` verweigert bzw. `OSError` wirft; Gegenproben für `skipped` und `busy`.

- **AC-3:** Given eine eingegangene Befehls-Mail, deren Verarbeitung oder Antwortversand scheitert (Ausnahme im inneren Ablauf, den `_process_single_inner` selbst abfängt) / When der Lauf endet / Then zählt diese Mail als Fehler des Laufs (`last_failed_count >= 1`), obwohl die Mail wie bisher als gelesen markiert wird; eine fehlerfrei verarbeitete Mail zählt nur als `processed`.
  - Test: zwei Mails über den echten Lese-Eingang (eine mit Fehler im inneren Ablauf, eine regulär); es wird geprüft, dass der Zähler genau 1 ist und `processed` nur die regulär verarbeitete enthält. Ein Gegenzähler nur im äußeren `except` würde diesen Test nicht erfüllen.

- **AC-4:** Given eine Befehls-Mail für einen unbekannten Trip, und die "Trip nicht gefunden"-Antwort wird nicht zugestellt / When der Lauf endet / Then zählt das als Fehler des Laufs; wird die Antwort zugestellt oder ist der Mail-Versand für diesen Nutzer gar nicht eingerichtet (`can_send_email()` falsch, kein Versuch), zählt es **nicht** als Fehler.
  - Test: drei Fälle (Antwort scheitert / Antwort ok / kein Versand eingerichtet); Fake für `send_command_reply_email` gibt `False`/`True` zurück.

- **AC-5:** Given `send_command_reply_email` und die Aufrufer im Posteingang / When die Antwort per E-Mail nicht zugestellt werden kann / Then liefert sie `False` und der Aufrufer wertet das aus (Fehler des Laufs); zugestellt liefert `True`. Das Verhalten für den Nutzer (Antworttext, Betreff) bleibt unverändert.
  - Test: echter `EmailOutput`-Fehler (SMTP-Fake verweigert) → `False` und Fehlerzähler am Lauf; Erfolgsfall → `True`.

- **AC-6:** Given der Fehlerstatus des Befehls-Posteingangs aus AC-2/AC-3 / When der Go-Scheduler den Lauf (alle 5 Minuten) auswertet / Then steht im Laufstatus (`last_run.status`) `error` bei `failed>0` bzw. `partial` bei `status=="partial"`, **nicht** `ok`; der Weg `triggerGlobalEndpoint` für andere Jobs bleibt unverändert.
  - Test: Go-Test mit Fake-Server, der `{"status":"partial","failed":1,"processed":0}` liefert → Lauf zeigt Fehler; Gegenprobe `{"status":"ok","processed":2}` → ok; andere globale Jobs unverändert.

- **AC-7:** Given der Push-Weckruf-Nachversuch (`kickRound`) / When der Posteingang-Lauf `failed>0` meldet / Then löst das **keinen** zusätzlichen Nachversuch und keinen Doppelversand aus; der Nachversuch hängt weiter nur an `processed`/`busy`. Die Mail ist bereits als gelesen markiert, der Marker einer Nachlieferung bereits entfernt — der Status ändert daran nichts.
  - Test: Go-Test: Lauf mit `failed>0, processed=0` → genau ein Aufruf, kein Nachversuch; Python-Test: kein zweiter Versand durch den Status.

- **AC-8:** Given Befehls-Posteingang-Läufe verschiedener Nutzer / When Nutzer A eine fehlerhafte und Nutzer B eine reguläre Mail hat / Then wird der Fehler nur Lauf und Status des Nutzers A angerechnet; es gibt keinen Rückfall auf `"default"` und keine Vermischung der Nutzer.
  - Test: Zwei-Nutzer-Test über den echten Leser (zwei Absender → zwei Nutzer); je Nutzer wird der Fehlerzähler geprüft.

### C. Briefing-Hinweise (#4, #6) und Nachlieferung (#8)

- **AC-9:** Given ein Telegram-Briefing, bei dem mindestens eine Teil-Nachricht scheitert und danach auch der Hinweis "Briefing unvollständig" nicht zugestellt wird, während das Briefing selbst (mindestens ein Kanal) zugestellt ist / When der Briefing-Lauf endet / Then meldet die Antwort von `/api/scheduler/trip-reports` `status == "partial"`, `notice_failed >= 1` und `failed == 0`, und `/api/scheduler/status` zeigt für `trip_reports_hourly` nach dem Go-Durchlauf `last_run.status == "partial"` (nicht `"ok"`, nicht `"error"`); `failed_channels` des Versandergebnisses bleibt **leer** und `delivery_outcome == "delivered"` (ADR-0086).
  - Test: echter Lauf über den Router mit Telegram-Fake (Teil-Nachricht und Hinweis scheitern); danach Go-Scheduler gegen diesen Router bzw. dessen aufgezeichnete Antwort und Prüfung des echten Werts `last_run.status` in `/api/scheduler/status`. Nicht nur der Python-Zähler wird geprüft.

- **AC-10:** Given ein Trip, der nur per SMS versendet wird, mit gescheiterten Wetter-Segmenten, und die Service-Fehlermail kann nicht zugestellt werden, während die SMS selbst zugestellt wurde / When der Briefing-Lauf endet / Then gilt dasselbe wie AC-9 (`partial`, `notice_failed >= 1`, `failed == 0`, `last_run.status == "partial"`, `failed_channels` leer). Ist der Trip nicht SMS-only, die Fehlermail zugestellt oder für den SMS-only-Trip gar kein Mailversand eingerichtet (`can_send_email()` falsch, kein Versuch = „nicht erforderlich“, `_send_service_error_email` liefert `True`), bleibt es bei `ok` und `notice_failed == 0`.
  - Test: vier Fälle (SMS-only + Mail scheitert / SMS-only + Mail ok / SMS-only ohne eingerichteten Mailversand / E-Mail-Trip), über den Router und den echten Statuswert.

- **AC-11:** Given das neue Feld `notice_failures` in `NotificationResult` / When der Adversary prüft, wer es liest / Then wird es von genau den Pfaden gelesen, die es erzeugen können, und wirkt im Lauf-Status: Briefing-Pfad durch `_send_trip_report_outcome` → `trigger_trip_reports`; Alarm-Pfad nur durch `compare_alert.py:444` (`send_multi_location_deviation_alert`) → `/compare-alert-checks` (AC-25). Für Trip-Abweichungsalarm, Trip-Radaralarm und Ortsvergleich-Radaralarm gibt es bewusst weder Leser noch Feld `notice_failed` (Einzelnachricht, siehe Implementation Details 4). Ein Feld ohne Leser oder ein Leser, der nur loggt, ist verboten.
  - Test: Mutation (Leser auskommentieren) macht AC-9/AC-10/AC-25 rot; Mutation `failed_channels += notice` macht AC-9/AC-25 rot (Prüfung `failed_channels == []`, `delivery_outcome` unverändert).

- **AC-12:** Given ein offener Nachliefer-Vermerk (Marker) und die Nachlieferung scheitert beim Versand (`no_weather` oder `channels_unreachable`) / When der Briefing-Lauf (`pre_pass`) endet / Then steht der Fehlschlag in `failed` der Lauf-Bilanz (Status `partial`); eine gelungene Nachlieferung (`sent`) zählt als `sent`; `no_channels`/`no_stage` zählen **weder** als gesendet noch als Fehler.
  - Test: echter `run_briefing_dispatch` mit vorbereiteter `pending_briefings.json`, je ein Marker je Ausgang (sent / channels_unreachable / no_weather / no_channels / no_stage); geprüft die Bilanz `(sent, failed)`.

- **AC-13:** Given ein Nachliefer-Vermerk, bei dem ein zuvor fehlendes Wetter-Segment weiterhin keine Daten liefert / When der Lauf endet / Then wird **nichts** gesendet (Lärmschutz #1012: `attempts += 1`), und es entsteht **kein** `failed` — ein weiter gestörter Wetterdienst löst nicht stündlich einen Fehlalarm aus.
  - Test: Marker mit Überschneidung der Fehlersegmente → Bilanz unverändert `(0, 0)`, `attempts` erhöht.

- **AC-14:** Given Läufe verschiedener Nutzer / When bei Nutzer A eine Nachlieferung oder ein Hinweis scheitert / Then wird der Fehler nur der Bilanz von Nutzer A zugerechnet (`TripDispatchStrategy` je Nutzer; Zähler am Dienst je Nutzer, Reset je Lauf); kein `"default"`-Fallback.
  - Test: Zwei-Nutzer-Test: Nutzer A scheitert, Nutzer B reguläres Briefing → Bilanz A `failed >= 1`, Bilanz B `(1, 0)`.

- **AC-15:** Given ein Fehlschlag aus AC-9/AC-10/AC-12 / When der Lauf endet / Then löst der Status **keinen** Nachversuch und keinen Doppelversand aus: der Marker ist bereits entfernt (`_remove_pending_marker` vor Versand), der Slot vermerkt, Hinweise werden nicht wiederholt.
  - Test: nach dem Lauf genau so viele gesendete Nachrichten wie vorher; erneuter Lauf desselben Zeitpunkts erzeugt keinen zweiten Versand.

### D. Toter Code (#7)

- **AC-16:** Given `TripReportSchedulerService.send_reports` (kein Produktionsaufrufer) / When die Scheibe fertig ist / Then ist die Methode gelöscht, nichts im Produktionscode, in Doku oder Tests verweist noch darauf, und der Zähl-Anker der Live-Tests (`test_pytest_collection_and_timeout_safety.py`) bleibt bei **13**. Grund: Der gelöschte Test war `email+live` markiert und zählte im Standardlauf nie mit; nur die Zählung mit `-m live` sinkt von 3 auf 2. Gemessen ist 13. `test_issue_339_verify_timing.py` und `docs/specs/modules/trip_report_scheduler.md` sind nachgezogen.
  - Test: Suche nach `send_reports(` (außer `send_reports_for_hour`-Namensfamilie) ohne Treffer; die genannten Tests grün; Anker-Test unverändert bei 13, Zählung mit `-m live` bei 2.

### E. Wächter-Korrektur Klasse 2 (Geschwister-Erfolgszähler)

- **AC-17:** Given der Wächter und eine Funktion, die Erfolge in einem `if`-Zweig zählt und im zugehörigen `else`-Zweig die Fehler (`sent += 1` / `else: failed += 1`, beide im Rückgabewert) / When der Scanner sie prüft / Then gilt sie als **mit Gegenzähler** und ist kein Fund; eine Funktion mit `else: failed += 1`, deren `if`-Rumpf **keinen** Geschwister-Erfolgszähler erhöht, bleibt ein Fund; die AC-8-Attrappe (`failed = 0`, nie erhöht) bleibt ein Fund.
  - Test: positiver und negativer Selbsttest im Wächter (Beispiel-Quelltexte als Strings, gescannt mit dem echten Scanner); Mutation: Korrektur zurücknehmen → der positive Selbsttest wird rot, Verallgemeinerung auf jedes `else` → der negative wird rot.

### F. Ratsche, Anti-Gaming, Mutations-Gegenprobe

- **AC-18:** Given der Wächter `tests/test_success_status_guard.py` / When die Scheibe fertig ist / Then ist `KNOWN_VIOLATIONS` von 8 auf **0** gesunken, `SPEC_LISTED_FINDINGS` und sein Längenanker sind auf den echten Scannerbefund angepasst (die 7 gelisteten Einträge raus, Anker 7 → 0/0), die Sonderprüfung AC-18 `inbound_expected` (fest auf B19) ist entfernt, und `test_known_violations_only_shrink` sowie `test_no_unlisted_success_status_findings` sind grün; Header-/Docstring-Zahlen sind nachgezogen.
  - Test: Wächter-Testdatei komplett grün; Abgleich der Zahlen gegen den tatsächlichen Scan.

- **AC-19:** Given die Ausnahmeliste `INTENTIONAL_CONSTANT_SUCCESS` (+ `_APPROVED_EXCEPTIONS`) / When die Scheibe fertig ist / Then ist sie **nicht gewachsen** (Anzahl wie vor der Scheibe); keine der 8 Stellen wurde als Ausnahme eingetragen.
  - Test: Differenz der Listen gegenüber `origin/main` = leer; `test_intentional_exception_list_cannot_grow` grün.

- **AC-20:** Given die Reparaturen der 8 Stellen / When der Adversary sie prüft / Then ist keine davon Gaming: kein künstliches `try/except`, kein Rückgabefeld/Bool ohne Leser beim Aufrufer, kein `getattr(..., 0)`-Stillrückfall im Produkt (insbesondere nicht für `last_failed_count`), kein Statuswert aus konstanter Variable.
  - Test: Diff-Prüfung; Mutationen aus AC-21 beweisen, dass Prüfungen an der Aufrufer-Verwertung wirken.

- **AC-21:** Given die Verhaltenstests dieser Scheibe / When der Adversary gezielt verfälscht (a) `status` wieder fest `"ok"` in #1 und #2, (b) den Fehlerzähler im inneren Handler von `_process_single_inner` entfernen, (c) den Fehlerzähler im IMAP-/OSError-Handler entfernen, (d) `send_command_reply_email` wieder `None` liefern lassen bzw. das Bool beim Aufrufer ignorieren, (e) den Leser von `notice_failures` entfernen (im Briefing-Pfad `_send_trip_report_outcome` UND im Ortsvergleich-Änderungsalarm `compare_alert.py:444`), (f) Hinweis-Fehlschlag in `failed_channels` eintragen oder als `failed` statt `notice_failed` zählen, (e2) Reset des Zählers entfernen bzw. Zähler zwischen Nutzern teilen (Briefing-Zähler und `CompareAlertService.last_notice_failed`), (g) in #8 den Fehlerzähler entfernen oder `no_stage`/`no_channels` als failed zählen, (h) im Go-Pfad `Failed>0` nicht auswerten / `kickRound` auf `Failed` koppeln / einen `getattr(...,0)`-Rückfall einbauen / Nutzer-A-Fehler in Nutzer-B-Bilanz buchen / `send_reports` nicht löschen / den Wächter-Fix auf jedes `else` erweitern / (i) `INTENTIONAL_CONSTANT_SUCCESS` erweitern / Then wird je Verfälschung mindestens ein **Verhaltenstest** rot, der an der Verwertung misst (Antwort, Bilanz, Go-Laufstatus), nicht nur der Wächter-Scanner.
  - Test: Mutation per String-Ersetzung mit externer Sicherungskopie (nie `git checkout/stash/reset`); gemeldet wird, **welcher** Test rot wurde; bleibt eine Verfälschung grün, ist das ein Finding.

- **AC-22:** Given die neuen Verhaltenstests / When sie laufen / Then gehen sie durch die **echten Eingänge** (Router-Aufrufe `/api/scheduler/*`, `run_briefing_dispatch`, `InboundEmailReader.poll_and_process`, Go-Scheduler-Pfad) mit Fakes nur an den Außengrenzen (IMAP, SMTP, Telegram); kein `patch()`, das nur die eigene Annahme zurückspiegelt.
  - Test: `tests/tdd/test_erfolg_heisst_wirkung_s4b.py`, Kernschicht ohne Netz; Go-Test `internal/scheduler/`.

- **AC-23:** Given die geänderten Alt-Tests und Fakes (siehe Liste unten) / When die Scheibe fertig ist / Then sind genau diese bewusst angepasst (Fake `send_command_reply_email` liefert `True`; Staging-Fake bekommt `last_failed_count`; Erwartung `_process_single` als Tupel; `"notice_failed": 0` in den erwarteten Antworten von `tests/test_dispatch_status_delivery.py`; `send_reports`-Test entfernt) und keine weitere Erwartung wurde still verändert; alle sind grün.
  - Test: Liste im Commit dokumentiert; Kerntests der betroffenen Dateien komplett grün.

- **AC-24:** Given die Doku / When die Scheibe fertig ist / Then dokumentiert `docs/reference/api_contract.md` `partial`/`failed` für `compare-alert-checks` und die Antwortform von `/inbound-commands` (`status`, `count`, `processed`, `failed`), `docs/specs/modules/trip_report_scheduler.md` ist ohne `send_reports`, und das Changelog in `docs/specs/modules/waechter_1405_erfolg_wirkung.md` führt S4b (8 → 0).
  - Test: Doku-Vertragstest (`# doc-compliance-test`), nur Doku-Dateien gelesen, kein Produkt-Quelltext.

### G. Alarm-Pfad, Endstatus und Mandantentrennung der Zähler

- **AC-25:** Given ein Ortsvergleich-Änderungsalarm wird über Telegram je Ort in mehreren Teil-Nachrichten gesendet, mindestens eine Teil-Nachricht kommt an, mindestens eine scheitert, und der Hinweis "Briefing unvollständig" scheitert ebenfalls / When der Alarmlauf endet / Then meldet die Antwort von `/compare-alert-checks` `notice_failed >= 1`, `status == "partial"` und `failed == 0`, und `/api/scheduler/status` zeigt für den Job `last_run.status == "partial"`; `failed_channels`, Retry-Backoff und Throttle des Alarms sind **identisch** zum Lauf mit zugestelltem Hinweis (ADR-0086), und es entsteht kein zusätzlicher Versand. Die Router `/alert-checks`, `/radar-alert-checks` und `/compare-radar-alert-checks` bleiben unverändert und führen kein Feld `notice_failed`.
  - Test: ein Fall für `/compare-alert-checks`, echter Alarmlauf mit Telegram-Fake; Vergleich `delivery_outcome`/Backoff-Eintrag mit dem Lauf ohne Hinweis-Fehlschlag; echter Statuswert im Go-Test.

- **AC-26:** Given Go `triggerEndpointForUser` und eine Antwort `{"status":"partial","notice_failed":1,"failed":0}` / When der Scheduler sie auswertet / Then steht `last_run.status == "partial"` (nicht `"error"`, nicht `"ok"`); bei `{"failed":1,...}` weiterhin `"error"`; bei `{"status":"ok","notice_failed":0}` `"ok"`. Offen festgehalten: das Monitoring (`check-gregor20.sh`) alarmiert `partial` **nicht**; der Hinweis-Fehlschlag ist im Status sichtbar, löst aber keinen Alarm aus (gewollt, siehe Abwägung).
  - Test: Go-Test mit Fake-Server (drei Antworten); im Fan-out zwei Nutzer, einer `partial`, einer `ok` → Job `partial`; einer `partial`, einer `error` → Job `error`.

- **AC-27:** Given die Zähler `notice_failed` (Briefing) und `last_notice_failed` (Ortsvergleich-Änderungsalarm) in Dienst-Instanzen / When zwei Nutzer nacheinander bzw. zwei Läufe desselben Nutzers laufen / Then enthält der Zähler jedes Laufs nur Fehlschläge **dieses** Nutzers und **dieses** Laufs (Instanz je Lauf neu, Reset bei Lauf-/Sammelstart); es gibt keine zwischen Nutzern geteilte Instanz und keinen `"default"`-Fallback.
  - Test: Zwei-Nutzer-Test (A: Hinweis scheitert, B: regulär) über Router/`run_briefing_dispatch` und `/compare-alert-checks`: A `notice_failed >= 1`, B `0`; zweiter Lauf von A nach behobenem Fehler: `0` (kein Übertrag).

## Geänderte Alt-Tests und Fakes (bewusst, benannt)

- `send_command_reply_email`-Fakes (`-> None` → `-> True`): `tests/test_inbound_reader_no_default_settings_lookup.py:129`,
  `tests/tdd/test_inbound_unresolved_sender_no_default.py:128`,
  `tests/tdd/test_inbound_email_sender_authentication.py:173`, `tests/test_befehl_antwortzeit.py:1516`
- `/inbound-commands`-/Reader-Tests (Antwort bekommt `failed`; Reader-Fake setzt `last_failed_count`):
  `tests/test_scheduler_triggers.py:62-90`, `tests/test_inbound_poll_lock.py:302,379`,
  `tests/test_inbound_gate_errors.py`, `tests/test_issue_1009_1019_inbound_robustness.py`,
  Staging-Fake `tests/test_staging_messlauf.py:534`; Go `internal/scheduler/scheduler_kick_test.go` u. a.
- Compare-Alarm (`status`): `tests/test_compare_alert_checks_faltet_amtliche_warnungen.py`,
  `tests/test_scheduler_run_duration_reporting.py:116`, `tests/test_issue_1169_compare_alert_consumer.py:816`,
  `tests/test_alarmlauf_einheit_abschottung.py`
- B21: `tests/tdd/test_telegram_recipient_contract.py:815-831` (Hinweis-Bool), `tests/unit/test_provider_error_handling.py:210-220` (Fehlermail-Bool)
- Briefing-Antwort: `tests/test_dispatch_status_delivery.py` (erwartete Antworten bekommen `"notice_failed": 0`)
- #8: keine Änderung nötig an `tests/test_dispatch_orchestrator.py`, `tests/test_issue_1012_no_data_guard.py`
  und `tests/test_briefing_anchor_survives_dispatch_failure.py`, weil sie den Rückgabewert von
  `_process_pending_markers` nicht lesen; sie bleiben unverändert und müssen grün bleiben
- #7: `tests/e2e/test_e2e_story3_reports.py:455-464`, `tests/tdd/test_pytest_collection_and_timeout_safety.py:171`
  (Anker bleibt 13, Kommentar/Zählung nachgezogen), `tests/tdd/test_issue_339_verify_timing.py:133`

Die genaue Treffermenge wird in `/40` per Suche ermittelt und im Commit genannt.

## Known Limitations

- `partial` wird vom Monitoring (`check-gregor20.sh`) nicht alarmiert; nur `error` alarmiert. Ein
  gescheiterter Hinweis/Fehlermail bei zugestelltem Briefing oder Alarm ist deshalb im Status sichtbar
  (`last_run.status "partial"`, Feld `notice_failed`), aber ohne Sofort-Alarm. Das ist bewusst entschieden
  (ein Fehlalarm bei zugestelltem Briefing wäre falsch). Am Code geprüft: Der Go-Scheduler führt
  `partial` je Nutzer und Job als Serie (`user_run_state.go:198-201`, `ConsecutivePartial`) und schickt
  bei wiederholtem `partial` eine gebündelte Flankenmeldung „Nutzer-Läufe wiederholt unvollständig"
  (`scheduler.go:724-729`, #2149, Priorität normal, einmal je Serie, Entwarnung bei `ok`). Ein dauerhaft
  scheiternder Hinweis wird also gemeldet, ein einzelner nicht. Dieses bestehende Verhalten ist gewollt
  und wird in dieser Scheibe nicht verändert.
- Eine Befehls-Mail, die ohne Trip-Klammer verworfen wird, zählt nicht als Fehler.

## Risiken

- **Monitoring-Wirkung (neu):** ein IMAP-Ausfall macht `inbound_command_poll` künftig zu `error`
  (Alarm ab Streak 2, `check-gregor20.sh:187-206` iteriert über alle Jobs — keine Infra-Änderung nötig).
  Gewollt: ein stummer Ausfall der Befehlsverarbeitung ist genau der Defekt-Typ von #1405.
- Fehlgeschlagene Nachlieferung (#8) macht `trip_reports_hourly` zu `failed`/`partial` — nur bei echt
  gescheitertem Versand (verpasstes Briefing = Schaden), nicht bei Wetterdienst-Störung ohne Versand (AC-13).
- Reihenfolge: Wächter-Korrektur (RED) → Python #1, #7, #8 → B21 → #3/#5 → Router #2 → Go #2 →
  Ratsche leeren → Docs. Python vor Go ausliefern.

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** keine neue. ADR-0086 (sent = zugestellt, `failed_channels` speist Backoff) bleibt
  unverändert und wird durch AC-9/AC-11 ausdrücklich geschützt.
- **Rationale:** Reparatur innerhalb der Wächter-Entscheidung "Erfolg heißt Wirkung" (#1405); keine
  Entscheidungsfläche (Kanäle, Provider, Datenmodell, Auth, Editor, Deploy) verändert.

## Changelog

- 2026-10-26: v1.0 — erste Fassung (spec-writer), Grundlage `docs/context/fix-1405-s4b-erfolg-heisst-wirkung.md`.
- 2026-10-26: v1.1 — PO-Korrektur nach Adversary BROKEN (F001/F002/F007): Alarm-Pfad für `notice_failed` auf den Ortsvergleich-Änderungsalarm (`/compare-alert-checks`, `CompareAlertService.last_notice_failed`) reduziert, weil nur dort ein Teilausfall mit Hinweis entstehen kann (Trip-Abweichung, Trip-Radar und Ortsvergleich-Radar senden eine Einzelnachricht; Leser in `trip_alert.py`/`compare_radar_alert.py` und Feld an `/alert-checks`, `/radar-alert-checks`, `/compare-radar-alert-checks` entfallen, diese Dateien und Router bleiben auf Stand `origin/main`, der Test `test_ac25_alarm_router_antwort_traegt_notice_failed` entfällt ersatzlos); AC-16 Zählanker bleibt bei 13 (gelöschter Test war `email+live`, nur `-m live` 3 → 2); `_send_service_error_email` liefert `True`, wenn bei SMS-only-Trip kein Mailversand eingerichtet ist (AC-10, Implementation Details 4); Alt-Tests: `test_dispatch_status_delivery.py` erwartet `"notice_failed": 0`, drei #8-Alt-Tests unverändert. Betroffen: Purpose #4, Source, Estimated Scope, Implementation Details 4/5, AC-10, AC-11, AC-16, AC-21, AC-23, AC-25, AC-27, Alt-Test-Liste.
