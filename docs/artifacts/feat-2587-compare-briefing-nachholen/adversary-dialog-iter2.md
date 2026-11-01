# Adversary Dialog — feat-2587-compare-briefing-nachholen
Spec: docs/specs/modules/feat_2587_compare_briefing_nachholen.md
Datum: 2026-10-31 12:36

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
**Adversary:** Re-Pruefung nach Fix-Loop 1. Tests: 163 passed (8 Dateien, -v), Go `-count=1 -run BriefingHealth` ok. 23 Mutationen per String-Ersetzung (Sicherung Scratchpad orig2), nach jeder Mutation Original wiederhergestellt, am Ende diff identisch fuer alle 4 Dateien.
Alte Ueberlebende jetzt ROT: F001 (dispatch_orchestrator.py:205-206 -> test_f001_f002), F002 (scheduler_dispatch_service.py:383-386, beide Richtungen), F003 (:338 -> test_f003), F004 (:257-260, date-only, reason entfernt), F005 (:231 -> test_f005), F006 (Nullauffuellung pending_briefings.py -> ac5), F007 (Fail-soft -> test_f007; _trip_marker einzeln -> test_f007_trip_marker). F007 Ladefilter trip_report_scheduler.py:928 einzeln ueberlebt weiter (akzeptiert, nur mit _trip_marker gemeinsam beobachtbar, gemeinsam rot durch AC-4). F008: no_weather-Zweig aus (rot), auch no_channels markieren (rot), slot_hour verloren (rot). Sperre: ganz aus (rot), nur upsert aus (rot).
NEUE Ueberlebende:

Finding:
  ID: F009
  Severity: MEDIUM
  Category: edge_case
  Code reference: src/services/scheduler_dispatch_service.py:341
  Description: Mutation "weather_failure_as_outcome=True" im Nachholversand entfernt - alle 163 Tests gruen. Der F008-Test nutzt wetter_fehlt_je_ort (Ort-Fehler ohne Ausnahme, Ergebnis no_weather ueber Zeile 840), nicht den Pfad "Wetter-Ausnahme" (Zeile 836). Wirft die Engine eine Ausnahme, ginge ohne das Flag der Vermerk still verloren (outcome "error", kein frischer Vermerk).
  Spec requirement: Spec 3 Punkt 4 (F008)
  Conflict: Zusicherung nicht dort geprueft, wo sie wirkt.
  Remediation: Test mit ComparisonEngine.run wirft Ausnahme beim Nachholer => frischer Vermerk.

Finding:
  ID: F010
  Severity: MEDIUM
  Category: edge_case
  Code reference: src/services/scheduler_dispatch_service.py:346
  Description: Mutation marker.get("report_type") -> fest "morning" ueberlebt. Der F008-Test deckt nur Morgen-Vermerke; ein Abend-Vermerk wuerde beim no_weather-Wiederholen als Morgen-Vermerk neu geschrieben (falscher Schluessel, Doppel-/Fehlraeumung).
  Spec requirement: Spec 3 Punkt 4 (Original-Werte)
  Remediation: F008-Test auch mit report_type=evening.

Finding:
  ID: F011
  Severity: LOW
  Category: edge_case
  Code reference: src/services/pending_briefings.py:136 und :151
  Description: Sperre in remove_entries bzw. bump_attempts entfernt ueberlebt (Parallel-Test nutzt nur upsert_entry). Lost-Update bei remove/bump gegen Upsert ungetestet. Ferner ueberlebt das Entfernen von mkdir in _locked (Zeile 78): upsert in noch nicht vorhandenem Nutzerordner scheitert dann (fail-soft verschluckt) - ungetestet. "Nie entsperrt" ist aequivalent (close am with-Ende gibt flock frei).
  Spec requirement: Spec Datenmodell (RMW)
  Remediation: Parallel-Test mit remove/upsert gemischt; Test fehlender Nutzerordner.

### Runde 2
**Adversary:** Seiteneffekte der Sperre geprueft (lesend): (1) Deadlock: keine Verschachtelung - upsert/remove/bump nehmen _locked genau einmal, die match-Lambdas rufen keine Marker-Funktionen; Schreiben erfolgt nur unter Sperre (trip_report_scheduler.py:613 schreibt eine andere State-Datei). flock auf getrennten fds waere bei Verschachtelung blockierend, tritt nicht auf. (2) Fehlender Nutzerordner: _locked legt ihn per mkdir an (pending_briefings.py:78); remove/bump pruefen vorher path.exists() und legen nichts an. Das Anlegen einer Lock-Datei in einem Ordner nicht existierender Nutzer ist nur bei upsert moeglich (gleiche Eigenschaft wie vorher fuer die Ablage). (3) Go-Store: internal/store/user.go:24 liest nur das Nutzerverzeichnis, Export ueberspringt Dateien mit Endung ".lock" (:549-552) und kennt nur die Erlaubnisliste (:467) - ".pending_briefings.lock" wird nicht exportiert; kein Konflikt. (4) Hinweis (LOW, AMBIGUOUS-Anteil): der Wiederholungsvermerk nach no_weather (:346) erhaelt frischen created_at und attempts 0; BriefingHealth "aeltester Vermerk" altert damit bei andauernder Wetterstoerung nie ueber eine Stunde - passt zu AC-6 (frischer created_at), aber schwaecht die Alarmschwelle; Entscheidung PO/Tech Lead.
Code-Referenzen geaenderter Dateien: src/services/pending_briefings.py:76 (_locked), :120 (upsert); src/services/trip_report_scheduler.py:454, :928; src/services/scheduler_dispatch_service.py:218, 248, 302, 341-348, 350; src/services/dispatch_orchestrator.py:193-206.
**Implementierer:** nicht beteiligt.

## Herkunft der Vorbedingungen

kein Sprachprofil konfiguriert (`precondition_origins.default_lang`)

## Verdict

F001-F008 geschlossen (Mutationen jetzt rot, F007-Ladefilter einzeln akzeptiert). Neue Testluecken F009, F010 (MEDIUM), F011 (LOW). Kein Produktivfehler nachgewiesen; Sperre ohne Deadlock/Go-Konflikt.

VERDICT: BROKEN
