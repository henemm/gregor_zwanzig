# Adversary Dialog — feat-2587-compare-briefing-nachholen
Spec: docs/specs/modules/feat_2587_compare_briefing_nachholen.md
Datum: 2026-10-31 12:19

## Checkliste
- [x] **Input:** ein automatischer (Zeitplan-)Versand eines Ortsvergleich-Briefings, der auf allen konfigurierten Kanälen scheitert; später der stündliche Vorlauf des Compare-Dispatch.
- [x] **Output:** ein Marker unter dem echten Nutzer; in einer späteren Stunde desselben Zieltags wird das Briefing mit Nachhol-Hinweis zugestellt; nach Zieltag verfällt der Marker ohne Versand. Solange der Marker existiert, zählt ihn `briefing_health.open_pending_briefings` (und das Infra-Monitoring alarmiert nach der bestehenden Schwelle).
- [x] **Side effects:** `pending_briefings.json` wird per Read-Modify-Write geändert; Versand-Historie (#2281) verbucht Nachholer mit korrektem Slot; Diagnose-Journal (#1629) bleibt unverändert aktiv.
- [x] **AC-1:** Given ein Nutzer hat einen aktiven Ortsvergleich-Zeitplan, dessen automatischer Versand zur Slot-Stunde auf allen Kanälen scheitert (Versand wirft eine Ausnahme), When der Scheduler-Lauf dieser Stunde beendet ist, Then liegt unter der Ablage dieses Nutzers genau ein Vermerk mit Art „Ortsvergleich“, der Preset-Kennung, dem Slot (Morgen/Abend), dem Zieltag, der Slot-Stunde und dem Grund „Versandfehler“.
- [x] **AC-2:** Given der automatische Versand eines Ortsvergleichs endet nicht mit einer Ausnahme, sondern mit dem Ergebnis „kein Kanal erreichbar“ (`channels_unreachable`), When der Scheduler-Lauf beendet ist, Then entsteht derselbe Vermerk wie bei AC-1; bleibt der Versand dagegen mit „keine Kanäle konfiguriert“ oder „keine Wetterdaten“ ohne Zustellung, Then entsteht KEIN Vermerk.
- [x] **AC-3:** Given ein Ortsvergleich-Versand scheitert vollständig, aber er wurde von Hand ausgelöst (Handversand-Endpunkt) oder über einen HEUTE/MORGEN-Befehl (`on_demand`), When der Aufruf beendet ist, Then entsteht KEIN Vermerk — weder bei Ausnahme noch bei „kein Kanal erreichbar“.
- [x] **AC-4:** Given in der Ablage eines Nutzers liegen ein Ortsvergleich-Vermerk, ein Trip-Vermerk ohne Art-Feld (Bestandsformat) und ein Trip-Vermerk mit Art „route“, When der Trip-Nachholdurchlauf (`trip-reports`) läuft — auch für einen Trip, der nicht (mehr) existiert —, Then bleibt der Ortsvergleich-Vermerk unverändert bestehen, und die Trip-Vermerke behandelt der Trip-Lauf wie bisher (Bestandsverhalten, inklusive Löschen eines Vermerks zu einem nicht mehr vorhandenen Trip).
- [x] **AC-5:** Given ein Ortsvergleich-Vermerk für den Morgen-Slot 07:00 von heute (Preset-Ortszeit) und es ist 10:00 Preset-Ortszeit am selben Tag, kein regulärer Slot dieses Presets mit demselben Zieltag fällig, When der stündliche Compare-Vorlauf läuft, Then wird das Briefing an die Empfänger des Nutzers zugestellt, und der zugestellte Text beginnt in E-Mail (HTML und Plain) und in Telegram mit „Nachgeliefert — die Zustellung um 07:00 ist fehlgeschlagen“.
- [x] **AC-6:** Given ein Ortsvergleich-Vermerk wird nachgeholt, When der Nachhol-Versand beginnt, Then ist der Vermerk bereits vor dem Senden aus der Ablage entfernt; scheitert der Nachhol-Versand erneut, Then liegt danach ein neuer Vermerk (frischer `created_at`, `attempts` zurückgesetzt) für denselben Preset und Slot vor, und es existiert nie mehr als ein Vermerk je (Preset, Slot).
- [x] **AC-7:** Given ein Ortsvergleich-Vermerk, dessen Zieltag in der Preset-Ortszeit bereits vorbei ist (z. B. Morgen-Vermerk von gestern; Preset in einer Zeitzone, deren lokaler Tag vom UTC-Tag abweicht), When der stündliche Compare-Vorlauf läuft, Then wird nichts zugestellt und der Vermerk ist danach entfernt; liegt der Zieltag in Preset-Ortszeit noch nicht hinter „heute“ (Abend-Slot mit Zieltag morgen), Then wird der Vermerk nicht verworfen.
- [x] **AC-8:** Given ein Abend-Vermerk (Slot 19:00, Zieltag morgen) und der Nachhol-Lauf findet nach Mitternacht Preset-Ortszeit statt (Zieltag ist nun „heute“), When der Vorlauf den Vermerk nachholt, Then wird die Zustellung in der Versand-Historie als „Abend“ (nicht „Morgen“) verbucht und der Tagesbezug des Briefings ist der Zieltag (nicht um einen Tag verschoben).
- [x] **AC-9:** Given ein Ortsvergleich-Vermerk und zur selben Stunde ist derselbe Preset mit demselben Zieltag regulär fällig (z. B. Abend-Vermerk für Tag D, und um 07:00 an Tag D fällt der Morgen-Slot für D), When der Compare-Lauf dieser Stunde beendet ist, Then erhält der Nutzer genau EINE Zustellung (die reguläre), der Vermerk wird bei deren Erfolg entfernt; scheitert die reguläre Zustellung, Then bleibt der Vermerk für die Folgestunde bestehen. Fällt dagegen nur ein Slot mit anderem Zieltag an, Then wird zusätzlich nachgeholt.
- [x] **AC-10:** Given ein Ortsvergleich-Vermerk, dessen Preset stillgelegt ist (`is_silenced`), dessen `end_date` abgelaufen ist oder das gelöscht wurde, When der stündliche Compare-Vorlauf läuft, Then wird nichts gesendet und der Vermerk ist danach entfernt.
- [x] **AC-11:** Given ein Ortsvergleich-Vermerk mit Grund „Versandfehler“ liegt vor, When der reguläre (nicht On-Demand-)Versand desselben Presets und Slots erfolgreich zustellt, Then ist dieser Vermerk entfernt; ein erfolgreicher On-Demand-Versand desselben Presets lässt ihn dagegen bestehen, ebenso einen Vermerk eines anderen Slots oder Presets.
- [x] **AC-12:** Given ein Preset hat gleichzeitig einen gescheiterten Morgen- und einen gescheiterten Abend-Versand, When beide Läufe beendet sind, Then liegen zwei getrennte Vermerke (Slot „Morgen“ mit Zieltag heute, Slot „Abend“ mit Zieltag morgen) vor, und der Verfall des einen betrifft den anderen nicht.
- [x] **AC-13:** Given zwei verschiedene Nutzer (echte, verschiedene Kennungen) haben je einen gescheiterten Ortsvergleich-Versand, When beide Vermerke geschrieben und der Vorlauf ausgeführt ist, Then liegt jeder Vermerk ausschließlich in der Ablage seines Nutzers, Nachholen und Verfall betreffen nur den eigenen Nutzer, und das Nachholen erreicht nur die Empfänger des jeweiligen Nutzers.
- [x] **AC-14:** Given eine Datei `users/<id>/pending_briefings.json` mit einem Trip-Eintrag und einem Ortsvergleich-Eintrag, When `briefing_health` ausgewertet wird, Then ist `open_pending_briefings` gleich 2 (Misch-Zählung) und `degraded_segments_total` unverändert durch den Compare-Eintrag.
- [x] **AC-15:** Given die bestehende Trip-Test-Suite für Marker, Nachholen und Versandfehler (`test_briefing_anchor_survives_dispatch_failure.py`, `test_erfolg_heisst_wirkung_s4b.py`, `test_versandpfade_folgen_ortszone.py`, `test_briefing_slot_faelligkeit_und_alarmsperre.py`), When sie nach dem Extrakt in das geteilte Modul ausgeführt wird, Then bleibt sie unverändert und vollständig grün (Trip-Verhalten unverändert; #1662-ACs gelten weiter).

## Dialog

### Runde 1
**Adversary:** Tests (8 Dateien) 155 passed, Go BriefingHealth ok (Artefakt adversary-test-output.txt). 26 Mutationen per String-Ersetzung mit Sicherung im Scratchpad; nach jeder Mutation Original wiederhergestellt, am Ende diff identisch fuer alle 4 Dateien.
Gefangen (rot): on_demand im except-Zweig (M0) und bei channels_unreachable (M1); Clear bei on_demand (M5), Clear entfernt (M6), Clear nur report_type (M7); Verfall abgeschaltet (M10), Wait entfernt (M11), is_silenced (M12), end_date (M13), Entfernen vor Senden geloescht (M14); Slot-Durchreichung report_type (M15, M18); Hinweis entfernt (M17, M23); Dedup/Sortierung (M19, M20); Upsert ohne RMW (M25).
UEBERLEBT (kein Test rot), Findings:

Finding:
  ID: F001
  Severity: MEDIUM
  Category: edge_case
  Code reference: src/services/dispatch_orchestrator.py:205-206
  Description: Mutation "self._success += sent / self._failed += failed" durch "pass" ersetzt - alle 155 Tests gruen. Die Zaehlung der Nachhol-Schleife im pre_pass ist nirgends dort geprueft, wo sie wirkt (result()-Tupel).
  Spec requirement: Spec 3 Punkt 6 - sent => _success, alles andere => _failed
  Conflict: ein gescheiterter Nachholer bliebe fuer Job-Flanke/Monitoring unsichtbar; Test fehlt.
  Remediation: Test ueber CompareDispatchStrategy.result() nach erfolgreichem und gescheitertem Nachholer.

Finding:
  ID: F002
  Severity: MEDIUM
  Category: edge_case
  Code reference: src/services/scheduler_dispatch_service.py:383-386
  Description: Mutationen "elif False: failed += 1" und "elif True: failed += 1" (no_channels als failed) ueberleben beide. Die Unterscheidung sent / no_channels neutral / Fehler in process_compare_pending_markers ist ungeprueft.
  Spec requirement: Spec 3 Punkt 6
  Conflict: Zaehllogik ungeprueft.
  Remediation: Direkttest process_compare_pending_markers fuer sent/failed/no_channels.

Finding:
  ID: F003
  Severity: MEDIUM
  Category: edge_case
  Code reference: src/services/scheduler_dispatch_service.py:338
  Description: Mutation tage_ab_ortstag=(target - ortstag).days -> 0 ueberlebt. Der Versatz fliesst in send_one_compare_preset zu _write_compare_alert_snapshots (Zeile 910, Alarm-Anker). Der AC-8-Test (01:00 nach Mitternacht, Versatz 0) zeigt den Unterschied nicht; "Abend-Vermerk D+1, Nachholen am selben Abend (Versatz 1)" ist ungetestet.
  Spec requirement: AC-8 / Spec 3 Punkt 5 (Vertrag #1661)
  Conflict: falscher Alarm-Anker-Tag beim Same-Day-Abend-Nachholer unentdeckt moeglich.
  Remediation: Test mit Abend-Vermerk, jetzt 20:00 am Vortag des Zieltags, Anker-Tag pruefen.

Finding:
  ID: F004
  Severity: LOW
  Category: edge_case
  Code reference: src/services/scheduler_dispatch_service.py:257-260
  Description: Variante "nur gleicher Zieltag" raeumt (statt Slot ODER Zieltag) ueberlebt; ebenso Entfernen der reason==dispatch_error-Bedingung. "Gleicher Slot, alter Zieltag" ist ungetestet (Spec 2 verlangt beides).
  Spec requirement: AC-11 / Spec 2
  Conflict: Testluecke, kein Produktivfehler nachgewiesen.
  Remediation: Test mit altem Morgen-Vermerk (gestern) + heutigem Erfolg; Vermerk anderer reason.

Finding:
  ID: F005
  Severity: LOW
  Category: edge_case
  Code reference: src/services/scheduler_dispatch_service.py:231
  Description: Der Schutz user_id == "default" => kein Marker ueberlebt Entfernen; die Cross-User-Pflichtregel ist ungeprueft.
  Spec requirement: Spec 1 (echte user_id, nie "default")
  Conflict: kein Test rot, Rueckfall-Konto koennte Marker bekommen.
  Remediation: Test send_one_compare_preset mit user_id="default" scheitert => keine Datei.

Finding:
  ID: F006
  Severity: LOW
  Category: anti_pattern
  Code reference: tests/tdd/test_compare_briefing_nachholen.py:68 (Produktiv: src/services/pending_briefings.py:149)
  Description: Regex akzeptiert "0?7:00"; Mutation ":02d" entfernt ueberlebt. AC-5 und fix_1662-Changelog fordern "07:00".
  Spec requirement: AC-5 - Wortlaut 07:00
  Conflict: Test prueft schwaecher als der AC.
  Remediation: Regex auf "um 07:00" festziehen.

Finding:
  ID: F007
  Severity: LOW
  Category: edge_case
  Code reference: src/services/scheduler_dispatch_service.py:236-239
  Description: Fail-soft beim Marker-Schreiben (Schreibfehler verschlucken) auf "durchreichen" umgestellt ueberlebt. Ausserdem: nur _trip_marker-Filter (trip_report_scheduler.py:454) ODER nur entries_matching-Filter (:928) entfernt ueberlebt einzeln (Defense-in-depth; gemeinsam rot) - kein Fehler.
  Spec requirement: Spec Datenmodell (fail-soft)
  Conflict: Testluecke.
  Remediation: Test mit nicht schreibbarer Ablage.

Finding:
  ID: F008
  Severity: MEDIUM
  Category: edge_case
  Code reference: src/services/scheduler_dispatch_service.py:376-384 (Entfernen vor Senden) i.V.m. 834/840 (no_weather)
  Description: Der Vermerk wird VOR dem Senden entfernt. Scheitert der Nachholer mit no_weather (raise ausserhalb des try) oder no_channels, entsteht kein frischer Vermerk (nur Ausnahme/channels_unreachable schreiben einen). Das Briefing ginge still verloren, open_pending_briefings faellt auf 0.
  Spec requirement: AC-6 / Spec 3 Punkt 4 ("scheitert erneut => frischer Marker")
  Conflict: AMBIGUOUS - Spec-Ausklammerung "no_weather kein Marker" deckt den Erstfehler, nicht den Wiederholungsfall.
  Remediation: Entscheidung des PO/Tech Lead; ggf. Marker bei no_weather im Nachholfall erhalten.

### Runde 2
**Adversary:** Zweiter Mutationsdurchlauf (Familien aus den Leitfragen): Trip-Filter beide entfernt (rot ac4), is_trip_entry -> True (rot ac4), is_compare_entry -> True (rot ac1), UTC- statt Ortstag (rot ac7), Entfernen NACH dem Senden (rot ac6; der Lese-waehrend-Senden-Test wirkt), members[-1] (rot), wait->send (rot ac9a), drop->wait (rot ac7); ueberlebt: Nullauffuellung (F006), Fail-soft (F007). Go-Test AC-14 vorhanden (internal/scheduler/briefing_health_test.go:1013-1041, Commit 7c5c28bd3). Trip-Hinweis "7:00" -> "07:00" ist in fix_1662_versandfehler_nachliefern.md:431 dokumentiert (kein stiller Bruch). Nebenlaeufigkeit: trip-reports (scheduler.go:782) und compare-presets-daily (scheduler.go:1011) sind getrennte Cron-Jobs; RMW ohne Lock (pending_briefings.py:98-124) - Lost-Update bei Ueberlappung nicht ausgeschlossen, nicht verifiziert.
Code-Referenzen geaenderter Dateien: src/services/pending_briefings.py:98 (upsert_entry); src/services/trip_report_scheduler.py:454 (_trip_marker), :928 (Filter); src/services/scheduler_dispatch_service.py:218, 248, 302, 350, 967, 988, 992; src/services/dispatch_orchestrator.py:193-206.
**Implementierer:** nicht beteiligt (reiner Adversary-Lauf).

## Herkunft der Vorbedingungen

kein Sprachprofil konfiguriert (`precondition_origins.default_lang`)

## Verdict

AC-1..AC-15 verhalten sich im Code korrekt (155 Tests + Go gruen; AC-14 durch Go-Test belegt). Mutations-Gegenprobe: mehrere Verfaelschungen ueberleben (F001-F008) - Zusicherungen nicht dort geprueft, wo sie wirken.

VERDICT: BROKEN
