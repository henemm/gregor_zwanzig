# Adversary Dialog — feat-2587-compare-briefing-nachholen
Spec: docs/specs/modules/feat_2587_compare_briefing_nachholen.md
Datum: 2026-10-31 12:46

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
**Adversary:** Re-Pruefung nach Fix-Loop 2. Tests: 166 passed (8 Dateien, -v), Go `-count=1 -run BriefingHealth` ok. 21 Mutationen per String-Ersetzung (Sicherung Scratchpad orig3), jeweils Original wiederhergestellt, am Ende diff identisch fuer alle 4 Dateien. ALLE 21 rot:
- F009: weather_failure_as_outcome=True entfernt (scheduler_dispatch_service.py:348) -> test_f009.
- F010: report_type fest "morning" (:353) -> test_f010; Zieltag verschoben -> test_f008.
- F011: Sperre in remove_entries / bump_attempts entfernt (pending_briefings.py) -> test_parallele_schreiber; mkdir in _locked entfernt (:78) -> test_upsert_legt_fehlenden_nutzerordner_an.
- retry_of beide Richtungen (scheduler_dispatch_service.py:243-245): created_at frisch -> rot; attempts nicht erhoeht -> rot; attempts nicht gesetzt -> rot; retry_of nicht uebergeben (:354) -> rot; retry_of immer aktiv (AC-6-Pfad wuerde altern) -> test_ac6 rot.
- Stichprobe frueherer Mutationen weiter rot: F001 (dispatch_orchestrator.py:205-206), F002 (:383-386), F003 (:338), F004, F005 (:231), F006, F007 (Fail-soft), F008 (no_weather-Zweig), Sperre komplett aus, on_demand im except-Zweig.
Keine neuen Findings.

### Runde 2
**Adversary:** Lesende Gegenpruefung der retry_of-Logik. (1) retry_of=marker ist der Vertreter der Dedup-Gruppe (fruehester slot_hour); die uebrigen Gruppenmitglieder werden vor dem Senden entfernt, ihr attempts fliesst nicht ein - unerheblich (Diagnosewert, kein Abbruchkriterium). (2) created_at faellt auf frisches Datum zurueck, wenn das Original keines traegt (`or`), kein Absturz. (3) Der AC-6-Pfad (Ausnahme/channels_unreachable beim Nachholen) laeuft ueber send_one_compare_preset ohne retry_of und schreibt frisch mit attempts 0 (Spec AC-6) - durch "retry_of always" abgesichert. (4) Sperre: keine Verschachtelung/Deadlock, Lock-Datei .pending_briefings.lock wird vom Go-Export uebersprungen (internal/store/user.go:549-552), user.go:24 liest nur Verzeichnisse; fehlender Nutzerordner jetzt getestet. (5) Go-Gesundheit: BriefingHealth zaehlt weiter jeden Eintrag (AC-14 Test gruen); ein andauernd wiederholter no_weather-Vermerk altert jetzt ehrlich (created_at bleibt), das vorherige AMBIGUOUS ist damit geloest.
Code-Referenzen: src/services/pending_briefings.py:76 (_locked), :120 (upsert); src/services/trip_report_scheduler.py:454 (_trip_marker), :928 (Filter, einzeln akzeptiert gemeinsam mit _trip_marker ueber AC-4 bewacht); src/services/scheduler_dispatch_service.py:218-250 (_mark_compare_undelivered/retry_of), :341-356 (_send_catchup), :350ff (process_compare_pending_markers); src/services/dispatch_orchestrator.py:193-206.
**Implementierer:** nicht beteiligt.

**Confirmations** (Code-Referenzen aus Runde 2 im Gate-Format):
- Sperre `_locked` und Read-Modify-Write `upsert_entry`
  Code reference: src/services/pending_briefings.py:76
- Trip-Filter `_trip_marker` (gemeinsam mit Ladefilter :928 über AC-4 bewacht)
  Code reference: src/services/trip_report_scheduler.py:454
- `_mark_compare_undelivered` inkl. `retry_of` / Nachhol-Schleife `_send_catchup`
  Code reference: src/services/scheduler_dispatch_service.py:218
- Nachhol-Schleife im Compare-`pre_pass` inkl. Zählung
  Code reference: src/services/dispatch_orchestrator.py:193

## Herkunft der Vorbedingungen

kein Sprachprofil konfiguriert (`precondition_origins.default_lang`)

## Verdict

F001-F011 geschlossen, alle Mutationen rot. Einziger einzeln unbeobachtbarer Rest: Ladefilter trip_report_scheduler.py:928 (aequivalent geschuetzt durch _trip_marker, gemeinsam rot).

VERDICT: VERIFIED

## Geprüfte Dateien

- sha256:7eae799a11003eae5cfa216fe400dc8ce9553c06b77a5cc6ea0c0d2ac1a2c31d  src/services/dispatch_orchestrator.py
- sha256:279b2c540be3883b995f0dcd5c347c4bd7a7dc7dfd56af61868cbfca37b6e2fc  src/services/pending_briefings.py
- sha256:ea1abb506793f5db12af9af4e410209be06757055972ec5dc0e99ebe5c5c876e  src/services/scheduler_dispatch_service.py
- sha256:87c93cee52c41fc9eb74f5a627b7532675062ee4a139d3953e587aaec18f2a66  src/services/trip_report_scheduler.py

## Prüfbasis

- base: b535d3423e9dfdc7038d6f191c51a142c96a6c08
- blob:d606687aa83223e12fdfbb53da5a3678274d6c1b  src/services/dispatch_orchestrator.py
- blob:ebfa805f6aa2f051ada9afe51e2cdb6cd62a6aed  src/services/pending_briefings.py
- blob:314db05c0b686e9a09b1b0565588820bb9f4a97e  src/services/scheduler_dispatch_service.py
- blob:886af58b81b5fe5c57c3ebfc73bc0bf0e52eed4d  src/services/trip_report_scheduler.py
