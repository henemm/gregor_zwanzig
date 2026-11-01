---
entity_id: feat_2587_compare_briefing_nachholen
type: feature
created: 2026-10-31
updated: 2026-10-31
status: draft
version: "1.0"
tags: [briefing, ortsvergleich, dispatch, retry, issue-2587, observability, code-teilung]
---

# Ortsvergleich-Briefing nach Versandfehler nachholen (Issue #2587)

## Approval

- [ ] Approved

## Purpose

Scheitert der automatische Zeitplan-Versand eines Ortsvergleich-Briefings auf allen Kanälen, wird das heute nur im Diagnose-Journal (#1629/#2280) verbucht, aber nie nachgeholt: das Briefing ist für den Nutzer verloren und taucht im Monitoring-Signal `open_pending_briefings` nicht auf. Diese Spec stellt Gleichstand mit dem Trip her (#1662): Ein vollständig gescheiterter Zeitplan-Versand wird vorgemerkt, in einer späteren Stunde **desselben Zieltags** nachgeholt (mit Hinweis „Nachgeliefert — …“) und bis dahin als „offen“ in `briefing_health` geführt. Folge aus #2280 (Adversary-Befund F-ADV6).

Herleitung, Code-Verifikation und alle Tech-Lead-Entscheidungen: `docs/context/feat-2587-compare-briefing-nachholen.md` (Abschnitt „Analysis“). Diese Spec wiederholt sie nicht, sondern zieht den Scope daraus.

## Source

- **File:** `src/services/pending_briefings.py` (neu, geteilt), `src/services/scheduler_dispatch_service.py`, `src/services/dispatch_orchestrator.py`, `src/services/trip_report_scheduler.py`
- **Identifier:** `pending_briefings.*` (Marker-Operationen), `send_one_compare_preset` (Marker schreiben/löschen), `CompareDispatchStrategy.pre_pass` (Nachhol-Schleife), `TripReportSchedulerService._process_pending_markers` (Filter)

> **Schicht-Hinweis:** Betroffene Schicht ist ausschließlich der **Python-Core** (`src/services/`). Kein Frontend-Code. **Kein Go-Produktivcode** und **keine Infra-Änderung**: `BriefingHealth` (`internal/scheduler/briefing_health.go`) zählt jeden Eintrag aus `users/*/pending_briefings.json`, liest `trip_id` nicht, ignoriert unbekannte Felder (`PendingBriefingEntry`), und die Export-Erlaubnisliste (`internal/store/user.go`) führt die Datei bereits. `henemm-infra/scripts/check-gregor20.sh` zählt Compare-Marker dadurch automatisch mit; es ist keine MQ-Nachricht an `infra` nötig. Einzige Go-Änderung: ein Test.

## Scope

Im Umfang:

- Marker-Schreiben bei **vollständig gescheitertem** automatischem Zeitplan-Versand eines Ortsvergleichs (Ausnahme beim Senden **oder** `channels_unreachable`), nur bei `not on_demand`.
- Marker-Löschen bei Erfolg des regulären Versands desselben `(preset_id, report_type)`.
- Nachhol-Schleife im Compare-`pre_pass` (nach der Auto-Pause) mit Verfallsregel über den Zieltag in Preset-Ortszeit.
- Nachhol-Hinweis „Nachgeliefert — die Zustellung um HH:00 ist fehlgeschlagen“ in E-Mail (HTML + Plain, Compact-ASCII) und Telegram, über den bestehenden Präfix-Baustein (`_prepend_hint`-Logik), geteilt statt kopiert.
- Extrakt der Marker-Operationen in ein geteiltes Modul; `kind`-Diskriminator, damit der Trip-Nachholpfad Compare-Marker nicht löscht.
- Go-Test: `briefing_health.open_pending_briefings` zählt eine Mischdatei (Trip + Compare).

## Out of Scope

- **`no_channels`** (Konfigurationsfehler, durch Nachholen nicht behebbar) — kein Marker.
- **`no_weather`** und durchschlagende Wetter-Exceptions im Ortsvergleich — kein Marker; beim Trip trägt das der eigene #1012-Mechanismus. Nebenbefund → Sammel-Issue #1199.
- **SMS/Premium-SMS ohne Nachhol-Hinweis:** gilt für Trip **und** Ortsvergleich gleichermaßen (160-Zeichen-Budget; ADR-0095-Parität). Beidseitige Lücke, kein Teil dieser Scheibe. Nebenbefund → #1199. Der **Inhalt** wird auf allen vier Kanälen nachgeholt, lediglich der Hinweis fehlt in SMS/Premium-SMS.
- **Kein Go-Produktivcode**, **keine Infra-Änderung** (siehe Schicht-Hinweis).
- Kein Nachhol-Fenster über den Zieltag hinaus (#1777 bleibt eigenes Thema), keine Teilzustellung (ein Vermerk entsteht nur, wenn KEIN Kanal zugestellt hat — wie Trip #1662).
- Aufschlüsselung von `open_pending_briefings` nach Grund/Art.

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `alert_briefing_anchor.briefing_target_day_is_current` | function | reine Verfallsfunktion (#1662), Docstring sieht Compare-Wiederverwendung ausdrücklich vor |
| `alert_briefing_anchor.record_briefing_dispatch_failure` | function | bestehende Diagnose-Schreibstellen; bleiben unverändert aktiv, Marker kommt zusätzlich |
| `compare_slot_scheduler.presets_due_for_hour` | function | exakte Stunde, Morgen (Offset 0) / Abend (Offset 1) — Quelle für „reguläre Fälligkeit mit gleichem Zieltag“ |
| `scheduler_dispatch_service.send_one_compare_preset` | function | Fehlererkennung (Ausnahme :751-755, `channels_unreachable` :765-773), Marker-Hooks |
| `dispatch_orchestrator.CompareDispatchStrategy` | class | `pre_pass` bekommt die Nachhol-Schleife |
| `trip_report_scheduler._process_pending_markers` | function | bekommt `kind`-Filter (Blocker) |
| `preset_ortstag`, `is_silenced`, `_load_presets_for_dispatch`, `outcome_from_result`, `SendOutcomeError`, `append_briefing_log` | functions | Ortstag, Stilllegung, Preset-Laden, Outcome-Auswertung, Versand-Historie (#2281) |
| ADR-0018 | decision | Grundsatz „Ausweichen, aber ohne Kaschieren“ (dort für Wetter-Quellen; hier sinngemäß: ein Versandausfall wird nicht still verschluckt) |
| ADR-0035 | decision | ein Tagesfenster für Trip und Ortsvergleich |
| ADR-0044 / ADR-0051 | decision | Kalendertage folgen der Ortszeit; drei Zeitbegriffe |
| ADR-0097 | decision | Trip/Ortsvergleich-Code-Teilung (Pendant-Sperre) |
| `fix_1662_versandfehler_nachliefern` | module | Vorbild-Spec Trip-Nachholen; Compare-Ausklammerung (:73-76) wird hier abgelöst |

## Estimated Scope

- **LoC:** Produktiv +250/−100 (ca. 100 davon reiner Extrakt), Tests +400–500, Go nur Test (~30)
- **Files:** 5 Produktivdateien (`pending_briefings.py` neu, `trip_report_scheduler.py`, `scheduler_dispatch_service.py`, `dispatch_orchestrator.py`, `notification_service.py` klein), 2 Testdateien, 2 Spec-Ablösungen
- **Effort:** medium; Risiko MEDIUM (berührt den Trip-Nachholpfad und eine gemeinsam genutzte Nutzerdatei)

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** keine neue; folgt ADR-0097 und erfüllt ADR-0018.
- **Rationale:** Die Nachhol-Mechanik bekommt ein Compare-Pendant. Nach ADR-0097 wird sie nicht kopiert, sondern als geteiltes Modul ohne `trip_`/`compare_`-Präfix gebaut. Neue Entscheidungsfläche entsteht nicht: kein neuer Kanal, Provider, Auth- oder Editor-Weg; das Datenmodell wird rückwärtskompatibel um optionale Felder erweitert (keine Migration).

## Ablösung bestehender Spec-Aussagen

Diese Spec **löst ausdrücklich ab** (die beiden Dateien selbst werden von der Implementierung angepasst, nicht von dieser Spec-Erstellung):

1. **`docs/specs/modules/dispatch_orchestrator.md:95`** — Tabellenzeile `pre_pass`: bisher „Trip: Catch-up-Marker-Verarbeitung | Compare: Auto-Pause-Loop“. Neu: Compare = **Auto-Pause-Loop, danach Nachhol-Schleife für Compare-Marker**. Die dort dokumentierte, PO-getragene Aufteilung gilt damit nicht mehr; sie wird nicht still umgangen, sondern ersetzt.
2. **`docs/specs/modules/fix_1662_versandfehler_nachliefern.md:73-77`** — Abschnitt „Nicht in dieser Scheibe“, Punkt „Nachhol-Mechanik für den Ortsvergleich“ (dort „existiert bis heute kein Pending-Marker-Mechanismus“) sowie die Dependency-Zeile zu `dispatch_orchestrator.md:95` (:59). Beides ist mit #2587 überholt; die Trip-ACs von #1662 bleiben unverändert gültig.

## Datenmodell

Ablage unverändert: `data/users/<user_id>/pending_briefings.json`, `{"entries":[ … ]}`. **Keine separate Datei** (verworfen: Go-Glob, Export-Liste und Infra-Prüfung müssten für denselben Effekt erweitert werden).

**Compare-Eintrag:**

| Feld | Wert |
|---|---|
| `kind` | `"vergleich"` |
| `preset_id` | ID des Presets (kein `trip_id`) |
| `report_type` | `"morning"` oder `"evening"` |
| `date` | Zieltag (ISO-Datum; Abend-Slot: morgen) |
| `slot_hour` | Stunde des gescheiterten Slots (Preset-Ortszeit) |
| `reason` | `"dispatch_error"` |
| `failed_segment_ids` | `[]` |
| `attempts` | Zähler (Diagnosewert, kein Abbruchkriterium) |
| `created_at` | Zeitstempel |

**Schlüssel:** `(preset_id, report_type)` — ein Preset kann Morgen- und Abend-Slot mit verschiedenen Zieltagen haben; beide Marker koexistieren. Pro Schlüssel höchstens ein Eintrag (neuer Fehlschlag ersetzt den alten).

**Rückwärtskompatibilität:** Ein Eintrag **ohne** `kind` (Bestand) oder mit `kind == "route"` gehört dem Trip. Keine Migration. Trip-Einträge behalten ihr Format und Schlüssel `trip_id` unverändert.

**Schreibweise:** Read-Modify-Write mit Merge (bestehende Datei laden, nur den eigenen Schlüssel ersetzen/entfernen, fremde Einträge — auch die der anderen Art — unangetastet zurückschreiben; niemals Replace der Gesamtdatei, #102). Atomares Schreiben (temporäre Datei + Umbenennen). Lesen fail-soft (fehlende/defekte Datei ⇒ leere Liste, wie `_load_pending_entries`). Wegen der Edits an Schema-Dateien greift der Pre-Snapshot-Hook `data_schema_backup.py`.

## Code-Teilung (ADR-0097)

Neues geteiltes Modul `src/services/pending_briefings.py` **ohne** `trip_`/`compare_`-Präfix. Es enthält die kind-/schlüsselparametrisierten Marker-Operationen: laden, atomar schreiben, schreiben/ersetzen, entfernen, `attempts` hochzählen, `dispatch_error`-Marker räumen.

- Die Trip-Methoden (`_write_pending_marker`, `_mark_briefing_undelivered`, `_clear_dispatch_error_marker`, `_remove_pending_marker`, `_bump_pending_marker_attempts`) bleiben **dünne Delegierer mit unveränderter Signatur**; `_load_pending_entries` und `_write_pending_data` bleiben aus `trip_report_scheduler` importierbar (bestehende Tests).
- Die Nachhol-**Schleifen** bleiben getrennt (Trip: Segmente/Wetter; Compare: Preset). Gemeinsam sind die Verfallsregel `briefing_target_day_is_current` und der Präfix-Baustein für den Hinweis.
- Reihenfolge der Umsetzung: (1) reiner Extrakt, Trip-Tests bleiben grün; (2) `kind`-Filter mit rotem Test; (3) Compare-Hooks; (4) Nachhol-Schleife; (5) Spec-Ablösungen und Go-Test.

## Implementation Details

### 1. Marker schreiben (in `send_one_compare_preset`)

`_dispatch_due_preset` verwirft das Outcome; deshalb sitzt der Hook in `send_one_compare_preset`, neben den zwei bestehenden `record_briefing_dispatch_failure`-Stellen:

- Ausnahme um `send_compare_report` (:751-755) und
- Rückgabe `channels_unreachable` (:765-773).

An beiden Stellen wird — **nur bei `not on_demand`** — ein Marker mit der echten `user_id` (nie `"default"`) geschrieben. Wichtig: Der `except`-Zweig prüft heute kein `on_demand`; die Bedingung muss dort explizit ergänzt werden. Handversand-Endpunkt (#2280) und HEUTE/MORGEN-Befehle setzen `on_demand=True` und erzeugen nie einen Marker.

### 2. Marker löschen

Nach `outcome == "sent"` und `not on_demand`: nur Einträge mit `reason == "dispatch_error"` desselben Presets entfernen, und zwar die mit gleichem `report_type` **sowie** die mit gleichem Zieltag (`date`). Letzteres folgt aus AC-9a: das erfolgreiche reguläre Morgen-Briefing für Tag D räumt auch einen offenen Abend-Vermerk für D (Präzisierung bei der Implementierung, siehe Changelog).

### 3. Nachhol-Schleife (`CompareDispatchStrategy.pre_pass`, nach der Auto-Pause)

Je Compare-Marker (`kind == "vergleich"`) des Nutzers:

1. Preset fehlt, ist stillgelegt (`is_silenced`) oder `end_date` ist abgelaufen ⇒ Marker verwerfen, nichts senden.
2. Zieltag vorbei (`briefing_target_day_is_current(date, today=preset_ortstag(preset, locs, now_utc))`) ⇒ Marker verwerfen, nichts senden.
3. Fällt in dieser Stunde ein regulärer Slot **desselben Presets mit demselben Zieltag** an (`presets_due_for_hour`) ⇒ kein Catch-up; der reguläre Versand ist der „letzte Versuch“, der Marker bleibt bis zu dessen Erfolg bestehen (Trip #1662 AC-5/AC-6). Damit ersetzt das reguläre Morgen-Briefing von Tag D einen offenen Abend-Marker für D. Fällt nur ein Slot mit **anderem** Zieltag an, wird nachgeholt.
4. Sonst: Marker **vor** dem Senden entfernen (kein Doppelversand bei Absturz), dann senden mit Hinweis „Nachgeliefert — die Zustellung um HH:00 ist fehlgeschlagen“ (HH = `slot_hour`). Scheitert der Nachhol-Versand erneut, schreibt der Fehlerpfad aus Punkt 1 einen frischen Marker. Endet der Nachhol-Versand mit `no_weather` (vorübergehend, auch eine durchschlagende Wetter-Ausnahme), wird ebenfalls ein frischer Marker mit den Original-Werten geschrieben, damit die nächste Stunde es erneut versucht, bis der Zieltag verfällt; bei `no_channels` (Konfigurationsfehler) entsteht kein neuer Marker. Dieser `no_weather`-Wiederholungsmarker behält das ursprüngliche `created_at` und erhöht `attempts` um 1, damit er in `briefing_health` ehrlich altert und eine andauernde Wetterstörung nicht kaschiert wird (ADR-0018); der AC-6-Pfad (erneuter Versandfehler) bleibt frisch mit `attempts` 0.
5. Tagesbezug aus **einer** Zeitabfrage: `tage_ab_ortstag = (date − preset_ortstag(now)).days` (Vertrag #1661). Der Slot (`report_type`) wird aus dem Marker durchgereicht, damit `append_briefing_log` einen Abend-Nachholer nach Mitternacht nicht als „morning“ verbucht.
6. Zählung wie beim Trip: `sent` ⇒ `_success`, `no_channels` neutral, alles andere ⇒ `_failed`.
7. Je `(preset_id, date)` wird höchstens **einmal** nachgeholt: Liegen mehrere Compare-Vermerke desselben Presets mit demselben Zieltag vor (z. B. Folgefall von AC-9b), werden alle vor dem Senden entfernt und es geht genau eine Zustellung hinaus; Slot und Hinweis stammen vom Vermerk mit der frühesten `slot_hour`, und scheitert sie, wird ein frischer Vermerk mit dessen Werten geschrieben (AC-9-Grundsatz: eine Zustellung je Zieltag).

### 4. Hinweis-Transport

Nur E-Mail (HTML + Plain; Compact-ASCII über `_ascii_hint`) und Telegram — wie beim Trip. Kein Renderer-Eingriff: der Hinweis wird über die bestehende Präfix-Logik (`NotificationService._apply_prefixes/_prepend_hint`) vor dem Versand vorangestellt; ist das aufrufseitig nicht lösbar, wird `send_compare_report` um einen optionalen Präfix-Parameter ergänzt. Die Logik wird geteilt, nicht kopiert.

### 5. Blocker: Trip-Schleife darf Compare-Marker nicht löschen

`_process_pending_markers` ruft für Einträge ohne passenden Trip `_remove_pending_marker(trip_id)`. Bei einem Compare-Eintrag ist `trip_id` leer; das würde **alle** Compare-Marker löschen, und weil der Cron `trip-reports` **vor** `compare-presets-daily` ruft, sähe der Compare-Lauf seine Marker nie. Pflicht: Die Trip-Schleife und alle Trip-Marker-Funktionen filtern auf Trip-Einträge (kein `kind` oder `kind == "route"`); Compare-Einträge werden weder gelesen noch verändert noch gelöscht. Umgekehrt verarbeitet die Compare-Schleife nur `kind == "vergleich"`.

## Expected Behavior

- **Input:** ein automatischer (Zeitplan-)Versand eines Ortsvergleich-Briefings, der auf allen konfigurierten Kanälen scheitert; später der stündliche Vorlauf des Compare-Dispatch.
- **Output:** ein Marker unter dem echten Nutzer; in einer späteren Stunde desselben Zieltags wird das Briefing mit Nachhol-Hinweis zugestellt; nach Zieltag verfällt der Marker ohne Versand. Solange der Marker existiert, zählt ihn `briefing_health.open_pending_briefings` (und das Infra-Monitoring alarmiert nach der bestehenden Schwelle).
- **Side effects:** `pending_briefings.json` wird per Read-Modify-Write geändert; Versand-Historie (#2281) verbucht Nachholer mit korrektem Slot; Diagnose-Journal (#1629) bleibt unverändert aktiv.

## Acceptance Criteria

- **AC-1:** Given ein Nutzer hat einen aktiven Ortsvergleich-Zeitplan, dessen automatischer Versand zur Slot-Stunde auf allen Kanälen scheitert (Versand wirft eine Ausnahme), When der Scheduler-Lauf dieser Stunde beendet ist, Then liegt unter der Ablage dieses Nutzers genau ein Vermerk mit Art „Ortsvergleich“, der Preset-Kennung, dem Slot (Morgen/Abend), dem Zieltag, der Slot-Stunde und dem Grund „Versandfehler“.
  - Test: echtes Preset unter einem tmp-Datenverzeichnis anlegen, den Slot über den echten Scheduler-Aufruf mit garantiert scheiterndem E-Mail-Kanal auslösen, danach `pending_briefings.json` lesen und die Felder prüfen.

- **AC-2:** Given der automatische Versand eines Ortsvergleichs endet nicht mit einer Ausnahme, sondern mit dem Ergebnis „kein Kanal erreichbar“ (`channels_unreachable`), When der Scheduler-Lauf beendet ist, Then entsteht derselbe Vermerk wie bei AC-1; bleibt der Versand dagegen mit „keine Kanäle konfiguriert“ oder „keine Wetterdaten“ ohne Zustellung, Then entsteht KEIN Vermerk.
  - Test: Preset nur mit einem scheiternden Kanal (Gateway auf einem geschlossenen Port) auslösen und den Vermerk prüfen; zweite Läufe mit einem Preset ohne Kanäle bzw. ohne Wetterdaten, danach prüfen, dass keine Datei bzw. kein Eintrag entstanden ist.

- **AC-3:** Given ein Ortsvergleich-Versand scheitert vollständig, aber er wurde von Hand ausgelöst (Handversand-Endpunkt) oder über einen HEUTE/MORGEN-Befehl (`on_demand`), When der Aufruf beendet ist, Then entsteht KEIN Vermerk — weder bei Ausnahme noch bei „kein Kanal erreichbar“.
  - Test: beide Fehlerformen über den echten On-Demand-Aufruf auslösen und danach prüfen, dass `pending_briefings.json` für den Nutzer keinen Eintrag enthält.

- **AC-4:** Given in der Ablage eines Nutzers liegen ein Ortsvergleich-Vermerk, ein Trip-Vermerk ohne Art-Feld (Bestandsformat) und ein Trip-Vermerk mit Art „route“, When der Trip-Nachholdurchlauf (`trip-reports`) läuft — auch für einen Trip, der nicht (mehr) existiert —, Then bleibt der Ortsvergleich-Vermerk unverändert bestehen, und die Trip-Vermerke behandelt der Trip-Lauf wie bisher (Bestandsverhalten, inklusive Löschen eines Vermerks zu einem nicht mehr vorhandenen Trip).
  - Test: Mischdatei mit allen drei Einträgen schreiben, den Trip-Nachholdurchlauf über den echten Scheduler-Aufruf ausführen, die Datei danach lesen: Compare-Eintrag Byte-gleich vorhanden, Trip-Einträge nach Bestandsregel behandelt. Dieser Test ist vor der Implementierung des Filters rot (Compare-Marker würde gelöscht).

- **AC-5:** Given ein Ortsvergleich-Vermerk für den Morgen-Slot 07:00 von heute (Preset-Ortszeit) und es ist 10:00 Preset-Ortszeit am selben Tag, kein regulärer Slot dieses Presets mit demselben Zieltag fällig, When der stündliche Compare-Vorlauf läuft, Then wird das Briefing an die Empfänger des Nutzers zugestellt, und der zugestellte Text beginnt in E-Mail (HTML und Plain) und in Telegram mit „Nachgeliefert — die Zustellung um 07:00 ist fehlgeschlagen“.
  - Test: Vermerk anlegen, Vorlauf mit funktionierendem Kanal zur Stunde 10:00 ausführen, die tatsächlich zugestellte E-Mail (HTML + Plain) und die Telegram-Nachricht (im tmp-Test-Postfach bzw. Test-Telegram-Ausgang, kein Mock der eigenen Logik) auf den Hinweis prüfen.

- **AC-6:** Given ein Ortsvergleich-Vermerk wird nachgeholt, When der Nachhol-Versand beginnt, Then ist der Vermerk bereits vor dem Senden aus der Ablage entfernt; scheitert der Nachhol-Versand erneut, Then liegt danach ein neuer Vermerk (frischer `created_at`, `attempts` zurückgesetzt) für denselben Preset und Slot vor, und es existiert nie mehr als ein Vermerk je (Preset, Slot).
  - Test: Versandkanal im Nachholmoment so präparieren, dass er die Ablage beim Senden liest (Datei darf den Vermerk nicht mehr enthalten) und anschließend scheitert; danach Ablage lesen: genau ein neuer Vermerk.

- **AC-7:** Given ein Ortsvergleich-Vermerk, dessen Zieltag in der Preset-Ortszeit bereits vorbei ist (z. B. Morgen-Vermerk von gestern; Preset in einer Zeitzone, deren lokaler Tag vom UTC-Tag abweicht), When der stündliche Compare-Vorlauf läuft, Then wird nichts zugestellt und der Vermerk ist danach entfernt; liegt der Zieltag in Preset-Ortszeit noch nicht hinter „heute“ (Abend-Slot mit Zieltag morgen), Then wird der Vermerk nicht verworfen.
  - Test: zwei Presets in unterschiedlichen Zeitzonen mit festem „jetzt“ (UTC) so wählen, dass UTC-Datum und Ortsdatum auseinanderfallen; Vorlauf ausführen; Versandzähler und Ablage prüfen.

- **AC-8:** Given ein Abend-Vermerk (Slot 19:00, Zieltag morgen) und der Nachhol-Lauf findet nach Mitternacht Preset-Ortszeit statt (Zieltag ist nun „heute“), When der Vorlauf den Vermerk nachholt, Then wird die Zustellung in der Versand-Historie als „Abend“ (nicht „Morgen“) verbucht und der Tagesbezug des Briefings ist der Zieltag (nicht um einen Tag verschoben).
  - Test: Vermerk mit `report_type=evening` und Zieltag = Ortstag des „jetzt“ anlegen, Vorlauf ausführen, danach den Historien-Eintrag des Nutzers lesen (Slot „evening“, Zieltag korrekt).

- **AC-9:** Given ein Ortsvergleich-Vermerk und zur selben Stunde ist derselbe Preset mit demselben Zieltag regulär fällig (z. B. Abend-Vermerk für Tag D, und um 07:00 an Tag D fällt der Morgen-Slot für D), When der Compare-Lauf dieser Stunde beendet ist, Then erhält der Nutzer genau EINE Zustellung (die reguläre), der Vermerk wird bei deren Erfolg entfernt; scheitert die reguläre Zustellung, Then bleibt der Vermerk für die Folgestunde bestehen. Fällt dagegen nur ein Slot mit anderem Zieltag an, Then wird zusätzlich nachgeholt.
  - Test: drei Läufe mit festem „jetzt“: (a) regulärer Slot gleicher Zieltag, Versand ok ⇒ Zustellzähler 1, Ablage leer; (b) Versand scheitert ⇒ Vermerk bleibt; (c) Slot mit anderem Zieltag ⇒ Zustellzähler 2 (regulär + nachgeholt).

- **AC-10:** Given ein Ortsvergleich-Vermerk, dessen Preset stillgelegt ist (`is_silenced`), dessen `end_date` abgelaufen ist oder das gelöscht wurde, When der stündliche Compare-Vorlauf läuft, Then wird nichts gesendet und der Vermerk ist danach entfernt.
  - Test: drei Vermerke zu drei Presets (stillgelegt, abgelaufen, gelöscht) anlegen, Vorlauf ausführen, Versandzähler = 0 und Ablage ohne diese Vermerke prüfen.

- **AC-11:** Given ein Ortsvergleich-Vermerk mit Grund „Versandfehler“ liegt vor, When der reguläre (nicht On-Demand-)Versand desselben Presets und Slots erfolgreich zustellt, Then ist dieser Vermerk entfernt; ein erfolgreicher On-Demand-Versand desselben Presets lässt ihn dagegen bestehen, ebenso einen Vermerk eines anderen Slots oder Presets.
  - Test: Vermerke für zwei Presets und beide Slots anlegen; regulären Versand für (Preset A, Morgen) erfolgreich ausführen, danach nur dieser Eintrag weg; On-Demand-Erfolg ändert nichts.

- **AC-12:** Given ein Preset hat gleichzeitig einen gescheiterten Morgen- und einen gescheiterten Abend-Versand, When beide Läufe beendet sind, Then liegen zwei getrennte Vermerke (Slot „Morgen“ mit Zieltag heute, Slot „Abend“ mit Zieltag morgen) vor, und der Verfall des einen betrifft den anderen nicht.
  - Test: beide Slots nacheinander scheitern lassen, Ablage lesen (2 Einträge, verschiedene Zieltage); danach den Morgen-Vermerk verfallen lassen und prüfen, dass der Abend-Vermerk bleibt.

- **AC-13:** Given zwei verschiedene Nutzer (echte, verschiedene Kennungen) haben je einen gescheiterten Ortsvergleich-Versand, When beide Vermerke geschrieben und der Vorlauf ausgeführt ist, Then liegt jeder Vermerk ausschließlich in der Ablage seines Nutzers, Nachholen und Verfall betreffen nur den eigenen Nutzer, und das Nachholen erreicht nur die Empfänger des jeweiligen Nutzers.
  - Test: zwei tmp-Nutzerverzeichnisse mit je einem Preset und unterschiedlichen Empfängern; beide scheitern lassen; Ablagen einzeln lesen; einen Vermerk verfallen lassen, den anderen nachholen; Empfänger prüfen.

- **AC-14:** Given eine Datei `users/<id>/pending_briefings.json` mit einem Trip-Eintrag und einem Ortsvergleich-Eintrag, When `briefing_health` ausgewertet wird, Then ist `open_pending_briefings` gleich 2 (Misch-Zählung) und `degraded_segments_total` unverändert durch den Compare-Eintrag.
  - Test: Go-Test in `internal/scheduler/briefing_health_test.go` mit echter Mischdatei im tmp-Datenverzeichnis, Aufruf von `BriefingHealth()`.

- **AC-15:** Given die bestehende Trip-Test-Suite für Marker, Nachholen und Versandfehler (`test_briefing_anchor_survives_dispatch_failure.py`, `test_erfolg_heisst_wirkung_s4b.py`, `test_versandpfade_folgen_ortszone.py`, `test_briefing_slot_faelligkeit_und_alarmsperre.py`), When sie nach dem Extrakt in das geteilte Modul ausgeführt wird, Then bleibt sie unverändert und vollständig grün (Trip-Verhalten unverändert; #1662-ACs gelten weiter).
  - Test: die genannten Testdateien benannt ausführen; keine Änderung an ihren Erwartungen.

## Geplante Tests

- **Neu:** `tests/tdd/test_compare_briefing_nachholen.py` (Dateiname nach Verhalten) — deckt AC-1 bis AC-13 ab; echte Dateien unter tmp-Datenverzeichnis, echte Scheduler-Aufrufe (`presets_due_for_hour`/`pre_pass`/`send_one_compare_preset`), Zeit über das Parameter-„jetzt“ der Funktionen, kein Mock der eigenen Annahmen. Der Test zu AC-4 (Trip-Lauf lässt Compare-Marker stehen) wird zuerst rot nachgewiesen. Fixture-Helfer: `tests/helpers/briefing_imminent_fixtures.py`.
- **Erweitert:** `internal/scheduler/briefing_health_test.go` — Mischdatei (AC-14).
- **Unverändert grün:** Trip-Suite (AC-15) sowie die Compare-Bestandstests `test_compare_preset_send.py`, `test_compare_briefing_anchor_survives_dispatch_failure.py`, `test_compare_dispatch_failed_tally.py`.
- Zwei-Nutzer-Test ist Pflicht (AC-13).

## Betroffene Dateien

| Datei | Änderung |
|---|---|
| `src/services/pending_briefings.py` | NEU — geteilte Marker-Operationen |
| `src/services/trip_report_scheduler.py` | Delegierer auf geteiltes Modul; `kind`-Filter in `_process_pending_markers` und allen Marker-Funktionen |
| `src/services/scheduler_dispatch_service.py` | Marker schreiben an beiden Fehlerstellen (`not on_demand`), Löschen nach `sent`, Parameter Slot + Nachhol-Hinweis |
| `src/services/dispatch_orchestrator.py` | Compare-`pre_pass`: Nachhol-Schleife nach Auto-Pause, Zählung in `result()` |
| `src/services/notification_service.py` | klein: Präfix-Baustein für Compare nutzbar (E-Mail/Telegram), falls nicht aufrufseitig lösbar |
| `docs/specs/modules/dispatch_orchestrator.md` | Zeile 95 ablösen (siehe „Ablösung“) |
| `docs/specs/modules/fix_1662_versandfehler_nachliefern.md` | Compare-Ausklammerung (:73-77, :59) ablösen |
| `tests/tdd/test_compare_briefing_nachholen.py` | NEU |
| `internal/scheduler/briefing_health_test.go` | Mischdatei-Test |

## Known Limitations

- Ein Vermerk entsteht nur, wenn **kein** Kanal zugestellt hat; fällt nur ein Kanal aus, während ein anderer zustellt, wird nicht nachgeholt (Doppelzustellung strukturell ausgeschlossen, wie Trip #1662).
- Der Nachhol-Hinweis erscheint nur in E-Mail und Telegram, nicht in SMS/Premium-SMS (beidseitig, → #1199).
- `no_channels` und `no_weather` werden im Ortsvergleich nicht nachgeholt (→ #1199).
- `open_pending_briefings` unterscheidet weiterhin nicht nach Trip/Ortsvergleich/Grund (bewusst; Bedeutungsverschiebung wie in #1662 beschrieben).
- Nachholen nur bis Ende des Zieltags (Preset-Ortszeit); ein weitergehendes Nachhol-Fenster ist #1777.

## Changelog

- 2026-10-31: Initiale Spec (Issue #2587). Löst `dispatch_orchestrator.md:95` und `fix_1662_versandfehler_nachliefern.md:73-77` für den Ortsvergleich ab.
- 2026-10-31 (Implementierung): §2 präzisiert — ein regulärer Erfolg räumt auch Vermerke desselben Presets mit gleichem Zieltag (AC-9a geht der früheren Formulierung „nur `(preset_id, report_type)`“ vor). §3 Punkt 7 ergänzt — Nachholen je `(preset_id, date)` höchstens einmal, Vertreter ist der Vermerk mit der frühesten `slot_hour` (Orchestrator-Entscheidung zum AC-9b-Folgefall). Hinweis-Text nennt die Stunde zweistellig (`07:00`) für Trip und Ortsvergleich. ACs unverändert.
- 2026-10-31 (Fix-Loop 1, Adversary F008 + Nebenläufigkeit): §3 Punkt 4 ergänzt — ein Nachholer mit `no_weather` hinterlässt einen frischen Marker (Original-Werte), `no_channels` nicht (Tech-Lead-Entscheidung). Alle Read-Modify-Write-Operationen in `pending_briefings.py` laufen unter einem exklusiven `fcntl.flock` auf `<nutzerordner>/.pending_briefings.lock`, damit sich `trip-reports` und `compare-presets-daily` kein Update überschreiben.
- 2026-10-31 (Fix-Loop 2, Tech-Lead-Entscheidung): `no_weather`-Wiederholungsmarker behält `created_at` des Originals und zählt `attempts` hoch (ehrliches Altern in `briefing_health`, ADR-0018); AC-6-Pfad unverändert frisch.
