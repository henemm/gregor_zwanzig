---
entity_id: feat_2282_s2_ortsvergleich_befehle_versand
type: feature
created: 2026-10-22
updated: 2026-10-22
status: draft
version: "1.0"
workflow: feat-2282-s2-compare-report
tags: [ortsvergleich, inbound, report, heute, morgen, kanaltreue, epic-2133, epic-2345, issue-2282]
---

# Ortsvergleich-Befehle report/heute/morgen liefern ein echtes Vergleichs-Briefing (#2282 S2)

## Approval

- [ ] Approved

## Purpose

Die Befehle `report`, `heute` und `morgen` antworten am Ortsvergleich heute nur mit einer Übergangsantwort (`_compare_transitional`) und liefern kein Wetter. Diese Scheibe schaltet sie auf den bestehenden Handversand des Ortsvergleichs (`send_compare_preset`) um: `report` verschickt das Vergleichs-Briefing mehrkanalig, `heute`/`morgen` kanaltreu auf dem Kanal, über den der Befehl kam. Scheibe **S2** von Ticket #2282 (Epic #2345, Etappe P5); sie löst die Übergangsantwort aus S1 (`feat_2282_ortsvergleich_eingangskanaele.md`, Nicht-Ziele und AC-11-Umfeld) ab. Die S1-Spec selbst bleibt unverändert.

## Source

- **File:** `src/services/trip_command_processor.py` — `_dispatch_compare` (Weiche, ersetzt `_compare_transitional`), `_report_reply_body`, `_on_demand_failure_body`, `_COMMAND_SPECS`.
- **File:** `src/services/scheduler_dispatch_service.py` — `send_compare_preset` / `send_one_compare_preset` (neue optionale Parameter `restrict_to_channel`, `tage_ab_ortstag`).
- **File:** `src/services/trip_selection.py` — `_BEIDE_KINDS_ONLY_SCHLUESSEL`, Auswahl ohne Namen.

> Schicht: ausschließlich Python-Core (`src/services/`). Kein Go-, kein Frontend-, keine schema-relevante Datei (keine Migration).

> Querschnitt: Trip/Ortsvergleich-Teilung (ADR-0097) wird eingehalten — Kanal-Auflösung und Antworttexte sind je EIN geteilter Baustein. Mandantentrennung: Zwei-Nutzer-Test (AC-12). Kanäle: alle vier (E-Mail, Telegram, SMS, Premium-SMS) sind in den ACs benannt.

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `send_compare_preset` (scheduler_dispatch_service) | function | Bestehender Handversand: Send-Lock `"compare"`, `on_demand=True`, `weather_failure_as_outcome=True`; kein neuer Versandweg |
| `send_one_compare_preset` | function | Kanäle, Berechnung, Render, Versand, briefing_log/Status |
| `effective_compare_briefing_channels` (compare_alert_channels) | function | Mehrkanal-Auswahl für `report` (E-Mail immer, Telegram/SMS Opt-in, Premium-SMS mit Tarif-Gate) |
| `resolve_restricted_channel_flags` | function (neu, geteilt) | EINE Kanal-Auflösung für Trip und Vergleich (aus `_resolve_channel_flags` ausgelagert) |
| `preset_ortstag` (compare_slot_scheduler) | function (neu extrahiert) | Ortstag des Presets in dessen Zeitzone; auch vom Cron genutzt |
| `_report_reply_body`, `_on_demand_failure_body` | functions | Antworttexte-Tabellen, gemeinsam mit Trip |
| `trip_selection` / `_COMMAND_SPECS` | module | Adressierung ohne Namen, Hilfe-Text |
| `inbound_telegram_reader` | module | Ladehinweis „⏳ Wetter wird geladen…" |
| `briefing_log` / `briefing_slots` | module | on_demand-Einträge nehmen kein reguläres Briefing weg |
| `feat_2126_kanaltreue_adhoc_antwort.md` | spec | Kanaltreue-Regeln (`report` mehrkanalig, `heute`/`morgen` kanaltreu) |
| `feat_2439_befehle_antwortzeit.md` | spec | Laufzeitbudget (< 60 s je Lauf, Median < 45 s) |
| ADR-0095, 0097, 0049, 0044/0051, 0035, 0086 | ADR | Kanal-Parität, Code-Teilung, Premium-SMS, Ortstag, Tagesfenster, Erfolg = Zustellung |

## Estimated Scope

- **LoC:** ca. +170/−40 produktiv (Limit 250)
- **Files:** ca. 8 produktiv, 2 Tests
- **Effort:** medium (Risiko MEDIUM; einzige Trip-Berührung ist die Auslagerung der Kanal-Auflösung, abgesichert durch `test_kanaltreue_adhoc_antwort.py`)

### Affected Files

| File | Change Type | Description |
|------|-------------|-------------|
| src/services/trip_report_scheduler.py | MODIFY | `_resolve_channel_flags` Restrict-Zweig in geteilte Modulfunktion auslagern; Methode delegiert; Trip-Verhalten byte-gleich |
| src/services/user_tier.py (oder neue kleine Datei) | MODIFY/CREATE | `resolve_restricted_channel_flags(restrict, user_id)` |
| src/services/scheduler_dispatch_service.py | MODIFY | `restrict_to_channel` + `tage_ab_ortstag` an `send_compare_preset` / `send_one_compare_preset`; `None` = byte-gleich |
| src/services/compare_slot_scheduler.py | MODIFY | Ortstag-Berechnung als `preset_ortstag(...)` extrahieren; Cron und Befehl nutzen sie |
| src/services/trip_command_processor.py | MODIFY | `_dispatch_compare` ruft Versand statt `_compare_transitional` (entfällt); Antworttexte mit Label Trip/Ortsvergleich; `invalid_preset` + `fehlende_orte`; `suppress_email_reply` bei heute/morgen-Erfolg; `_COMMAND_SPECS`/Hilfe |
| src/services/trip_selection.py | MODIFY | `report`/`heute`/`morgen` in die Beide-kinds-Auswahl (PO-Variante B) |
| src/services/inbound_telegram_reader.py | MODIFY | Ladehinweis am Vergleich für report/heute/morgen einschalten |
| tests/tdd/test_ortsvergleich_befehle_versand.py | CREATE | Neues Verhalten (siehe Test Plan) |
| tests/tdd/test_vergleich_befehlsablehnung.py | MODIFY | Zwei Tests umdrehen (Übergangsantwort ca. :142, Ladehinweis unterdrückt ca. :258) |
| tests/tdd/test_kanaltreue_adhoc_antwort.py | unverändert | Trip-Regressionsschutz, muss grün bleiben |

## Implementation Details

1. **Ein gemeinsamer Pfad.** Alle drei Befehle rufen `send_compare_preset` (Send-Lock `"compare"`, `on_demand=True`, `weather_failure_as_outcome=True`). Kein neuer Versandweg (ADR-0097). Der Lock wird mit Scheduler und Web-Handversand geteilt.
2. **`report`:** ohne Einschränkung, mehrkanalig über `effective_compare_briefing_channels`, Zieltag heute (wie Web-Handversand und Trip-`report`).
3. **`heute`/`morgen`:** `restrict_to_channel=Anfragekanal`, `tage_ab_ortstag` 0 bzw. 1; Zieltag = Ortstag des Presets (dessen Zeitzone) + Versatz über `preset_ortstag`, dieselbe Funktion wie im Cron. `target_date` und `tage_ab_ortstag` werden immer gemeinsam gesetzt.
4. **Eingeschränkter Pfad:** Der Anfragekanal ist aktiv, auch wenn das Preset ihn nicht aktiviert hat (expliziter Nutzerwunsch, Parität ADR-0095). Es gelten nur die Tarif-Gates (`sms_allowed`/`premium_sms_allowed`) wie beim Trip. Die Bedingung `alert_channels is not None` aus `effective_compare_briefing_channels` gilt dort **ausdrücklich NICHT**. Die Auflösung ist EINE geteilte Funktion `resolve_restricted_channel_flags` für Trip und Vergleich. Die Versand-Gates (`can_send_*`, SMS-Tageslimit) bleiben aktiv; ein unerreichbarer Anfragekanal ergibt `channels_unreachable`.
5. **Antworttexte** über dieselben Tabellen wie Trip (`_report_reply_body`, `_on_demand_failure_body`), Label Trip bzw. Ortsvergleich. Codes: `ok`, `already_in_progress`, `no_weather`, `no_channels`, `channels_unreachable`, `invalid_preset`; dazu `fehlende_orte` als Hinweis, wenn einzelne Orte keine Daten lieferten. `heute`/`morgen` setzen bei Erfolg `suppress_email_reply=True` (das Briefing ist die Antwort).
6. **Ladehinweis** „⏳ Wetter wird geladen…" wird am Vergleich für `report`/`heute`/`morgen` eingeschaltet (Parität, gemessene Wartezeit 10–25 s).
7. **Adressierung ohne Namen — PO-Entscheidung 2026-10-22, Variante B („immer nachfragen").** `report`/`heute`/`morgen` kommen wie `pause`/`weiter` in die Beide-kinds-Auswahl. Trip + Vergleich ohne Namen: Rückfrage ohne Wirkung (Premium-SMS ≤ 160 Zeichen). Nur Vergleich(e): genau einer wird angesprochen, bei mehreren Rückfrage. Nur Trip (kein Vergleich): unverändert. Die Telegram-Query-Keys (`glance`, `gewitter` usw.) bleiben trip-only. Mit Namen wird direkt der benannte Trip oder Vergleich angesprochen. `hilfe` am Vergleich zeigt `report`/`heute`/`morgen`.
8. **Laufzeit.** Gemessen 2026-10-22 (`run_comparison_parallel`, Open-Meteo live, kalt, ohne Render/Versand): 3 Orte 9,7–14,1 s, 6 Orte 17,1–25,5 s. Budget aus #2439 (< 60 s je Lauf, Median < 45 s) gehalten, #2234 (Vorhersage-Cache im Vergleichspfad) wird **nicht** vorgezogen. Vorbehalt (Render, Versand, Météo-France fehlten): Staging-Kaltlauf mit ≥ 6 Orten als AC-13.
9. **briefing_log/Anker.** `send_compare_preset` setzt `on_demand=True`; die Rückwärts-Ableitung der Briefing-Slots überspringt solche Einträge. Eine Anfrage nimmt dem Nutzer sein reguläres Briefing nicht weg und berührt Anker/Erst-Briefing-Markierung nicht.

## Test Plan

### Automated Tests (TDD RED)

Tests nach Verhalten benannt, echte Kanal-/Dispatch-Kette mit gezählten Transporten (Fixture-Muster `versand`), kein Mock-Theater.

- [ ] `tests/tdd/test_ortsvergleich_befehle_versand.py` (neu): GIVEN Vergleich mit Premium-Tarif / WHEN `report` pro Kanal / THEN mehrkanaliger Versand; `heute`/`morgen` nur Anfragekanal; Zieltag und Slot; Fehlercodes; Lock; Opt-in-Override; Tarif-Gates; Zwei-Nutzer-Test; Adressierung ohne Namen (inkl. Nur-Trip-Regression); Ladehinweis; Hilfe; briefing_log-Nicht-Regression; Parität `resolve_restricted_channel_flags` Trip/Vergleich.
- [ ] `tests/tdd/test_vergleich_befehlsablehnung.py`: Test zur Übergangsantwort (ca. :142) und Test „Ladehinweis unterdrückt" (ca. :258) umdrehen; der `_ROUTE_ONLY`-Test (ca. :221) wird an Variante B angepasst.
- [ ] `tests/tdd/test_kanaltreue_adhoc_antwort.py`: unverändert grün (Trip-Regressionsschutz der ausgelagerten Kanal-Auflösung).
- [ ] Bestehende Regressionssuiten grün: `test_eingangsauswahl_trip_und_vergleich.py`, `test_vergleich_pause_weiter.py`, `test_trip_eingang_regressionskontrolle.py`, `test_compare_send_lock.py`, `test_compare_dispatch_channel_fanout.py`.

### Staging-Verifikation (Live-Schicht, `/e2e-verify`)

- Echte Compare-Mail (≥ 3 Orte) per Befehl ausgelöst, zugestellt ins Test-Postfach, gegen `uv run python3 .claude/hooks/email_spec_validator.py` (`X-GZ-Mail-Type: compare`), Exit 0.
- Telegram- und Premium-SMS-Eingang durch den echten Kanal-Eingang durchgespielt (zweite seven.io-Nummer empfängt), nicht nur Prozessor-Aufruf.
- Kaltlauf mit ≥ 6 Orten gemessen (AC-13).

## Acceptance Criteria

- **AC-1:** Given ein Nutzer hat einen aktiven Ortsvergleich und genau diesen angesprochen / When er per Telegram `report` sendet / Then erhält er das Vergleichs-Briefing auf allen für diesen Vergleich aktivierten Kanälen (E-Mail immer, Telegram/SMS/Premium-SMS nach Opt-in und Tarif) und auf Telegram eine kurze Bestätigung im selben Wortlaut-Muster wie beim Trip-`report`.
  - Test: Befehl `report` durch den Telegram-Eingang; gezählte Transporte zeigen genau die aktivierten Kanäle, je einmal.

- **AC-2:** Given ein Ortsvergleich mit aktiviertem Telegram-Kanal / When der Nutzer per Telegram `heute` sendet / Then kommt das Vergleichs-Briefing für den heutigen Ortstag ausschließlich auf Telegram an, und es geht weder eine E-Mail noch eine SMS noch eine Premium-SMS an Empfänger.
  - Test: `heute` über Telegram; Transport-Zähler E-Mail/SMS/Premium-SMS bleiben bei null, Telegram bei eins.

- **AC-3:** Given ein Ortsvergleich, dessen Ortszeitzone vom Server abweicht und bei dem der Ortstag bereits der nächste Kalendertag ist / When der Nutzer `morgen` sendet / Then betrifft das Briefing den Ortstag des Vergleichs plus einen Tag, wird als Abend-Slot geführt und ist derselbe Tag, den der Cron für diesen Vergleich berechnet.
  - Test: feste Uhrzeit nahe Mitternacht UTC bei Zeitzone mit Versatz; Zieltag aus der Antwort gleich `preset_ortstag(...)` + 1; Log-Slot „evening".

- **AC-4:** Given ein Nutzer hat den Vergleich per E-Mail angesprochen und im Vergleich ist E-Mail aktiv / When er per E-Mail `heute` sendet / Then kommt das Briefing als Vergleichs-Mail (mit Marker `X-GZ-Mail-Type: compare`) und es folgt keine zusätzliche Text-Antwortmail.
  - Test: `heute` über den E-Mail-Eingang; genau eine Mail im Postfach mit Compare-Marker, keine zweite Antwortmail (`suppress_email_reply`).

- **AC-5:** Given ein Ortsvergleich mit aktivierter SMS und Tarif, der SMS erlaubt / When der Nutzer per SMS `heute` sendet / Then kommt die Antwort als SMS in der kompakten Form (≤ 160 Zeichen je Nachricht, Tokens nach dem SMS-Vertrag) und nur auf SMS; ist das SMS-Tageslimit erreicht, erhält er eine Absage statt eines Versands.
  - Test: `heute` über den SMS-Eingang mit und ohne ausgeschöpftem Tageslimit; Zähler SMS 1 bzw. 0, Absagetext vorhanden.

- **AC-6:** Given ein Nutzer mit Premium-Tarif sendet `heute` per Premium-SMS (inReach) an einen Ortsvergleich, der Premium-SMS im Preset nicht aktiviert hat / When der Befehl verarbeitet wird / Then wird das Briefing trotzdem auf Premium-SMS zugestellt, weil der Anfragekanal nur an den Tarif gebunden ist; ohne Premium-Tarif wird der Kanal nicht bedient und der Nutzer erhält die Antwort „Kanal nicht erreichbar".
  - Test: Preset ohne Premium-SMS-Opt-in und ohne `alert_channels`; Premium-Tarif → Zustellung; Basis-Tarif → `channels_unreachable`-Text.

- **AC-7:** Given Trip und Ortsvergleich nutzen den Kanal-Override / When der Anfragekanal im jeweiligen Objekt nicht aktiviert ist / Then lösen Trip und Ortsvergleich die Kanal-Flags über dieselbe Funktion `resolve_restricted_channel_flags` auf, und das Trip-Verhalten ist gegenüber vorher unverändert.
  - Test: Paritätstest (gleiche Eingaben → gleiche Flags für beide Wege) plus unveränderte Suite `test_kanaltreue_adhoc_antwort.py` grün.

- **AC-8:** Given der Versand scheitert aus einem benannten Grund / When der Nutzer `report`, `heute` oder `morgen` am Ortsvergleich sendet / Then erhält er für `already_in_progress`, `no_weather`, `no_channels`, `channels_unreachable` und `invalid_preset` jeweils einen eigenen verständlichen Text aus denselben Tabellen wie beim Trip, mit dem Label „Ortsvergleich" statt „Trip"; ohne Fehler und ohne Wetterdaten für einzelne Orte nennt die Antwort die fehlenden Orte.
  - Test: je Code ein Lauf (Lock gehalten, alle Orte ohne Wetter, keine Kanäle, Kanal gesperrt, ungültiges Preset); Antworttext wird auf Code-Unterscheidung und Label geprüft, bei Teilausfall erscheinen die Ortsnamen.

- **AC-9:** Given ein Befehl läuft bereits für denselben Ortsvergleich (oder der Cron versendet gerade) / When der Nutzer erneut `report` sendet / Then wird kein zweites Briefing erzeugt und er erhält die Antwort „bereits in Arbeit".
  - Test: Send-Lock `"compare"` gehalten; zweiter Befehl führt zu null zusätzlichen Transporten und Text für `already_in_progress`.

- **AC-10:** Given ein Nutzer hat einen aktiven Trip und mindestens einen aktiven Ortsvergleich / When er per Telegram oder Premium-SMS `report`, `heute` oder `morgen` ohne Namen sendet / Then erhält er eine Rückfrage, welcher gemeint ist (Premium-SMS ≤ 160 Zeichen), und es wird nichts versendet oder verändert; mit vorangestelltem Namen wird direkt der benannte Trip bzw. Ortsvergleich bedient.
  - Test: Telegram- und Premium-SMS-Eingang, ohne und mit Namen; ohne Namen null Transporte und Rückfragetext, mit Namen genau ein Versand am richtigen Objekt.

- **AC-11:** Given ein Nutzer hat nur Ortsvergleiche und keinen Trip / When er `heute` ohne Namen sendet / Then wird bei genau einem Vergleich dieser bedient, bei mehreren Vergleichen kommt eine Rückfrage, und der Text „Kein aktiver Trip" erscheint nicht mehr; hat ein Nutzer nur Trips und keinen Vergleich, bleibt das Verhalten von `report`/`heute`/`morgen` unverändert, und die Telegram-Query-Befehle (`glance`, `gewitter` usw.) bleiben auf Trips beschränkt; `hilfe` am Ortsvergleich nennt `report`, `heute` und `morgen`.
  - Test: drei Konstellationen (nur ein Vergleich, mehrere Vergleiche, nur Trip) durch den echten Eingang; Nur-Trip-Läufe gegen aufgezeichnete Vorher-Antworten, `hilfe`-Text enthält die drei Befehle.

- **AC-12:** Given zwei verschiedene Nutzer A und B mit je eigenem Ortsvergleich und eigenen Empfängern / When A `report` oder `heute` sendet (auch mit dem Namen von Bs Vergleich) / Then wird ausschließlich As Vergleich berechnet und nur an As Empfänger zugestellt, und bei B ändert sich weder Versand noch Status noch briefing_log.
  - Test: Zwei-Nutzer-Test mit getrennten `data/users/<user_id>/`; Zähler und Datenstände von B unverändert.

- **AC-13:** Given ein Ortsvergleich mit mindestens 6 Orten auf Staging / When der Nutzer `heute` nach Kaltstart (ohne Wetter-Cache) sendet / Then liegt die Zeit bis zur Zustellung jedes Laufs unter 60 s und der Median mehrerer Läufe unter 45 s, ohne dass #2234 vorgezogen wird.
  - Test: Staging-Kaltlauf, mindestens 3 Läufe mit Zeitmessung, Ergebnis im Verifikationsbericht.

- **AC-14:** Given ein Nutzer sendet per Telegram `report`, `heute` oder `morgen` an einen Ortsvergleich / When das Laden mehrere Sekunden dauert / Then sieht er sofort den Hinweis „⏳ Wetter wird geladen…", wie beim Trip, bevor das Briefing eintrifft.
  - Test: Telegram-Eingang mit verzögerter Wetterabfrage; Ladehinweis wird vor dem Briefing gesendet (ersetzt den Test, der das Unterdrücken belegte).

- **AC-15:** Given ein Ortsvergleich hat sein reguläres Morgen-Briefing noch nicht erhalten / When der Nutzer `report` oder `heute` sendet / Then bleibt das reguläre Briefing für diesen Tag fällig und wird danach weiter planmäßig zugestellt, und die Änderungs-Anker des Vergleichs bleiben unberührt.
  - Test: Befehl vor dem Cron-Lauf; anschließend ist das reguläre Briefing weiterhin fällig und der Anker unverändert (on_demand-Eintrag zählt nicht als Versand).

- **AC-16:** Given eine echte Vergleichs-Mail mit mindestens 3 Orten wurde per Befehl auf Staging ausgelöst / When sie im Test-Postfach ankommt / Then besteht sie `email_spec_validator.py` (Exit 0), und der Telegram- und Premium-SMS-Eingang liefern auf Staging nachweislich je ein Briefing.
  - Test: Staging-Live-Schicht: Validator-Exit 0 für die echte Mail; Telegram- und zweite-seven.io-Nummer-Empfang bestätigt.

## Known Limitations

- Die Übergangsantwort aus S1 entfällt ersatzlos; `_compare_transitional` wird gelöscht.
- Der Ortsvergleich nutzt weiterhin keinen Vorhersage-Cache (#2234); bei deutlich mehr als 6 Orten kann das 60-s-Budget knapp werden — dann ist #2234 vorzuziehen.
- Variante B kostet Nutzern mit Trip und Vergleich eine Rückfrage-Runde bei jedem Befehl ohne Namen (PO-Entscheidung, nicht erneut vorlegen).
- E-Mail-Antwort auf Vergleichs-Mails per Betreff (S3) und Shortcodes (S4) bleiben außerhalb dieser Scheibe.

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** keine neue; folgt ADR-0097 (Code-Teilung Trip/Vergleich), ADR-0095 (Kanal-Parität), ADR-0049.
- **Rationale:** Bestehende Bausteine (Handversand, Antworttabellen, Kanal-Auflösung) werden geteilt statt neu gebaut; keine bestehende Entscheidung wird geändert.

## Changelog

- 2026-10-22: Initial spec created (Scheibe S2, PO-Entscheidung Variante B zur Adressierung ohne Namen)
