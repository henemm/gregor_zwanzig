# Context: fix-1405-s1-alarm-zustellung

Issue #1405 (Wächter 2, „Erfolg heißt Wirkung"), Scheibe 1 — Epic #2505 (Versand-Zuverlässigkeit).

## Request Summary

Alarm-Versand meldet `sent=True`, sobald ein Kanal **betreten** wurde — auch wenn ALLE Transporte scheitern.
Alle Alarm-Aufrufer gaten Zustand/Throttle/Tageskontingent/Event-Identität auf `result.sent` ⇒ ein komplett
gescheiterter Alarm gilt als zugestellt und wird nie wiederholt (still verloren). Dazu die Restliste-Einträge
B14a/B14c (8), B1, B15, B16 aus `tests/test_success_status_guard.py` abbauen.

## Related Files

| File | Relevanz |
|------|----------|
| `src/services/notification_service.py:136-168` | `NotificationResult`: `sent`, `sent_channels` (= „betreten"), `failed_channels`, Property `delivered_channels` |
| `src/services/notification_service.py:1064ff` | `send_official_alert` — append vor try (B14a, 4 Kanäle), `sent=bool(sent_channels)` |
| `src/services/notification_service.py:1370ff, 1446-1477` | `send_multi_location_official_alert` — Helfer liefert bool, Kanal landet auch bei False in `sent_channels` (vom Wächter NICHT als B14 gelistet, gleiche Wirkung) |
| `src/services/notification_service.py:1678ff, 1824` | `_dispatch_alert_message` — append vor try (B14c, 4 Kanäle); trägt deviation/radar/compare-Alarme |
| `src/services/notification_service.py:498ff, 1238ff` | Gegenmuster: `send_trip_report`/`send_compare_report` appenden NACH erfolgreichem Send |
| `src/services/trip_alert.py:905/953, 2784/2828, 3269/3323/3347, 3013` | Trip-Änderungs-, Radar-, Amtlich-Alarm: gaten State, Throttle, `alert_daily_limit`, `record_event_identity`, `record_nowcast_sent` auf `result.sent` |
| `src/services/compare_official_alert.py:311, 362` | Ortsvergleich amtlich: `if not result.sent: return False`, sonst State/Kontingent/Identität (kein Throttle) |
| `src/services/compare_alert.py:431, 508-511` | Ortsvergleich Änderungsalarm: `any_sent` ⇒ finalize/Throttle/Kontingent |
| `src/services/compare_radar_alert.py:409, 459` | Ortsvergleich Radar: analog |
| `src/services/alert_log.py:423-444` | `append_entry`: `entries` vs. `not_delivered` bewusst über `reachable_channels` (Cockpit-Zahl, #1459 AC-11) |
| `api/routers/scheduler.py:342` | B1 `send_test_trip_report`: konstant `"sent": True`; alle Nicht-`sent`-Outcomes vorher 422/409 ⇒ formaler Fund |
| `src/services/trip_command_processor.py:2464-2480` | B15 `_trigger_report`: bool von `send_test_report` verworfen ⇒ Nutzer bekommt „Report gesendet" auch bei no_stage/no_weather/channels_unreachable — **nutzersichtbar falsch** |
| `src/services/trip_command_processor.py:1524-1553` | B16 `_trigger_on_demand`: Text korrekt variiert, nur `success=True` in beiden Zweigen (formal; `CommandResult.success` liest niemand) |
| `src/services/trip_report_scheduler.py:1162, 1814-1830` | `send_test_report_outcome`: sent/no_stage/no_weather/no_channels/channels_unreachable/already_in_progress |
| `tests/test_success_status_guard.py` | Detektor 1c `_find_pre_try_success_marker_violations` (:772), Klasse 1 `_find_constant_success_violations` (:573), `KNOWN_VIOLATIONS` (:1498), `SPEC_LISTED_FINDINGS` (:1835) + harter Test `len==26, sum==35` (:1983), Ratschen :2050/:2086, `test_intentional_exception_list_cannot_grow` (:3358) |

## Existing Patterns

- **Wächter-Auflösung 1c:** Eintrag verschwindet, wenn append im try NACH dem Send / nach dem try steht, ODER Handler `sent_channels.remove(..)` macht, ODER Handler weiterwirft.
- **Wächter-Auflösung Klasse 1:** Erfolgswert ist abgeleitete Variable (`success=ok`, `"sent": outcome == "sent"`), oder kein Aufruf vor dem return, oder except-return mit anderem Wert.
- Schlüssel `pfad::funktion::ordinal` — Ordinale verschieben sich beim Entfernen einzelner Treffer.
- `delivered_channels` ist schon die Wahrheit für „zugestellt" in Alarm-Protokoll und Kanal-Anker (#1987).
- Norm im Haus: `run_briefing_dispatch()` → `(sent, failed)`, Status aus `failed > 0`.

## Dependencies

- Upstream: `EmailOutput`, `TelegramOutput`, `SMSOutput`, `PremiumSmsOutput`, `_sms_gate_reserve`, `sms_daily_limit`.
- Downstream: 6 Alarm-Aufrufer (oben), `alert_log`, `alert_daily_limit`, `_throttle_store`, `record_event_identity`, `record_nowcast_sent`, `check_all_trips` (`alerts_sent`-Zähler), Scheduler-Status/Health-Journal (#2218).

## Existing Specs

- `docs/specs/modules/waechter_1405_erfolg_wirkung.md` (Tabelle :427-431 — muss mitgezogen werden)
- `docs/specs/_archive/modules/issue_684_alert_email_guard.md` (:78, **AC-3** :94)
- `docs/specs/modules/feat_1459_alert_protokoll.md` (:178-217, D4-Nachtrag v1.4, AC-11/AC-15)
- `docs/specs/modules/feat_1701_alarm_premium_sms.md` (:277-296, **D7**)
- `docs/specs/modules/fix_1987_kanal_anker.md` (:84, 160-166)
- `fix_1662_versandfehler_nachliefern.md`, `dispatch_orchestrator.md`, `fix_2218_*`, `fail_closed_versand_defaults.md`

## 🔴 Kernkonflikt: dokumentierte Gegenentscheidung (dreifach)

Die heutige Semantik ist **bewusst** und dreimal festgeschrieben:

1. **#684 AC-3** (2026-06): transienter Fehler ⇒ trotzdem `True`, Throttle + Log gesetzt. Begründung: „sonst Alarm-Spam alle 30 Min";
   Memory-Lehre „Anti-Pattern #656": „Alert-Recording NIE an Live-SMTP-Erfolg koppeln (Rate-Limit→flaky). ‚Deliverable' = Kanal konfiguriert".
   (#656 selbst ist das Radar-Nowcast-Feature; die Lehre stammt aus dessen Tests.)
2. **#1459 D4 v1.4:** `reachable_channels` eingeführt, damit die Cockpit-Zahl unverändert bleibt („AC-11 gewinnt").
3. **#1701 D7:** „Buchung hinter den try ziehen … ist FALSCH" — würde `sent`/`reachable`-Unterscheidung zerstören; Ratsche 3→4 angehoben.

Kein ADR. Nach CLAUDE.md wird eine dokumentierte Entscheidung **nie still rückgängig** gemacht ⇒ die Spec muss die
Abkehr ausdrücklich begründen (ggf. neues ADR) und die Spam-Sorge von #684 anders lösen.

**Tests, die die alte Semantik festnageln** (müssen bewusst geändert/gelöscht werden, mit Begründung):
- `tests/tdd/test_issue_684_alert_email_guard.py::test_ac3_configured_smtp_transient_failure_still_records`
- `tests/tdd/test_914_slice4_alert_sms_dispatch.py::test_ac3_sms_http_error_logged_email_still_delivers` (faktisch Totalausfall ⇒ True)
- `tests/tdd/test_alert_log_channels.py::test_ac15_konfiguriert_aber_nichts_zugestellt_bleibt_in_entries`, `::test_ac11_fehlgeschlagener_versand_veraendert_die_angezeigte_zahl_nicht`
- indirekt: `test_alarm_pruefstrecke_selbstschutz.py:263`, `test_radar_convective_check_failure.py:230`

## Risks & Considerations

- **Alarm-Sturm bei Dauerausfall:** Wird bei Totalausfall nicht gebucht, versucht jeder Lauf (Takt 5–30 Min) erneut. Bei echtem
  Totalausfall erreicht nichts den Nutzer ⇒ kein Spam beim Nutzer, aber: **mehrdeutige Fehlschläge** (Timeout NACH Annahme beim
  Provider) könnten real zugestellt sein ⇒ Doppelzustellung je Lauf. Braucht begrenzte Wiederholung (Wiederholungs-Deckel / eigener
  Fehlversuchs-Zähler) statt ungebremster Retries.
- **Teilerfolg** (≥1 Kanal zugestellt) MUSS weiter als erledigt buchen — sonst Doppelzustellung auf den funktionierenden Kanälen.
- **SMS-Tageslimit-Reservierung** wird im Fehlerfall bereits zurückgegeben — Wechselwirkung beim Retry prüfen.
- **Cockpit-Zahl / Alarm-Protokoll** (#1459 AC-11) darf sich nicht unbeabsichtigt verschieben; `entries` vs. `not_delivered` klären.
- **Parität Trip ↔ Ortsvergleich:** alle 6 Aufrufer + `send_multi_location_official_alert` (nicht vom Wächter erfasst, gleiche Wirkung) einheitlich.
- **Premium-SMS:** Fehlschlag landet zusätzlich in `blocked_channels`; bewusste Sperre (kein Transportfehler) ≠ Fehlschlag.
- **Wächter-Pflege:** `KNOWN_VIOLATIONS`, `SPEC_LISTED_FINDINGS` (+ harte Zahlen 26/35), Spec-Tabelle `waechter_1405_erfolg_wirkung.md` — Ordinal-Verschiebung beachten.
- **B15 ist nutzersichtbar** (falsches „Report gesendet" auf Kommando) — echter Fix; B1/B16 sind formal (Ableitung statt Literal).
- Mehrdeutig, ob `NotificationResult.sent` umdefiniert oder ein neues Feld eingeführt wird — Analyse-Entscheidung.

## Analysis

### Type
Bug (mit bewusster Abkehr von dokumentierter Altentscheidung → neues ADR-0086)

### Kernbefund (verifiziert, Stand efd468761)
- `NotificationResult` (`notification_service.py:137-167`): `sent_channels` = „betreten", `delivered_channels` = Property (sent − failed). Kein `reachable`-Feld; `reachable_channels` ist nur Parameter von `alert_log.append_entry` und wird mit `result.sent_channels` befüllt.
- `send_official_alert` append vor try (:1158/1172/1196/1217), `sent=bool(sent_channels)` :1231. `_dispatch_alert_message` append vor try (:1826/1842/1927/1946), return :1957.
- `send_multi_location_official_alert` (:1451-1477) append unbedingt nach Helfer; **Tageslimit-Sperre liefert False ⇒ Kanal in sent+failed+blocked ⇒ bewusste Sperre ergibt `sent=True`** (Inkonsistenz zu den anderen zwei Pfaden).
- Konsumenten von `.sent`: `trip_alert.py:953` (State, Identität, Throttle `trip`, Daily-Limit), `:2828` Radar (`record_nowcast_sent`, Identität), `:3323` amtlich (+ return → `alerts_sent`, nur geloggt); `compare_alert.py:446/499`, `compare_radar_alert.py:457`, `compare_official_alert.py:360`. Kein Health-Journal liest `.sent` (#2218 C hängt an `alert_fetch`).
- `alert_log.append_entry` liest `sent` nie; alle Aufrufer rufen es VOR dem sent-Guard. `entries` vs `not_delivered` über `reachable_channels`.
- Takt: Trip-/Compare-Änderung + amtlich `*/15`, Radar (beide) alle 5 min. **Für Alarme gibt es keinen Retry-Mechanismus** (#1662-Nachliefern nur Briefings, Zähler dort bewusst abgelehnt).
- Mehrdeutige Fehlschläge real möglich: SMTP-Timeout nach DATA / QUIT-Fehler, Telegram-ReadTimeout nach Annahme, seven.io-ReadTimeout nach Annahme (dann zusätzlich `release_reservation` ⇒ Kontingent unterzählt).
- Sperre vs. Transportfehler: einziger sauberer Diskriminator = Key in `blocked_reason_codes`. Premium-Transportfehler steht in `blocked_channels` OHNE Code.
- ADR-0021 (`docs/adr/0021-shared-deviation-alert-engine.md:314, :337`) verlangt bereits „Buchung nur nach erfolgreicher Zustellung" — die Ist-Semantik widerspricht ihm. Nächste freie ADR-Nummer: **0086**.
- B15 (`trip_command_processor.py:2464-2480`): bool von `send_test_report` verworfen, immer „Report gesendet"; Exception ohne except. Eingänge: `inbound_email_reader._process_single` :251, Telegram-Webhook → `InboundTelegramReader._dispatch_and_reply` (Fallback `_VALID_COMMANDS` :714), `inbound_sms_reader._verarbeite_befehl` :352/369/400.

### Affected Files (with changes)
| File | Change Type | Description |
|------|-------------|-------------|
| `src/services/notification_service.py` | MODIFY | Neues Feld `attempted_channels` (betreten, vor try); `sent_channels.append` NACH erfolgreichem Send im try; `sent=bool(sent_channels)`. Drei Pfade inkl. Multi-Location (Sperre ≠ Fehlschlag) |
| `src/services/trip_alert.py` | MODIFY | 3 Aufrufer: `reachable_channels=attempted_channels`; Totalausfall ⇒ keine State/Identität/Daily-Limit/nowcast-Buchung, stattdessen Fehlversuchs-Backoff |
| `src/services/compare_alert.py`, `compare_radar_alert.py`, `compare_official_alert.py` | MODIFY | Parität zu Trip (gleiche Buchungsregel, Backoff) |
| `src/services/alert_log.py` | evtl. MODIFY | nur falls Backoff-Gate den append bündelt; Default-Logik (:477) bleibt |
| `src/services/trip_command_processor.py` | MODIFY | B15: `send_test_report_outcome` auswerten, Text je Outcome, Exception fangen; B16: `success` ableiten |
| `api/routers/scheduler.py` | MODIFY | B1: `"sent": outcome == "sent"` |
| `tests/test_success_status_guard.py` | MODIFY | B14a (:1548-1564), B14c (:1588-1600), B1, B15, B16 aus KNOWN_VIOLATIONS/SPEC_LISTED_FINDINGS; harte Zahlen 26/35 (:1983) nachziehen; Ordinal-Verschiebung |
| `tests/tdd/test_issue_684_alert_email_guard.py:239` | MODIFY | ac3 umschreiben: transienter Totalausfall ⇒ `sent=False`, kein State, Backoff gesetzt (Verweis ADR-0086) |
| `tests/tdd/test_914_slice4_alert_sms_dispatch.py:281` | MODIFY | Totalausfall ⇒ `False`; Teilerfolg ⇒ `True` |
| `tests/tdd/test_alert_log_channels.py:191/:227` | MODIFY | Eingabe auf `attempted_channels`, Aussage (AC-15/AC-11) bleibt |
| neue Verhaltenstests (z.B. `test_alarm_totalausfall_wird_wiederholt.py`, `test_report_kommando_meldet_echtes_ergebnis.py`) | CREATE | Totalausfall/Teilerfolg/Sperre je Pfad, Trip+Ortsvergleich; B15 durch echten Kommando-Eingang |
| `docs/adr/0086-*.md` + `docs/adr/README.md` | CREATE/MODIFY | Abkehr von #684 AC-3 / Präzisierung #1459 D4, #1701 D7 |
| `docs/specs/modules/waechter_1405_erfolg_wirkung.md` (:427-431) | MODIFY | Tabelle mitziehen |

### Scope Assessment
- Files: ~10 produktiv/Test + ADR + Spec-Tabelle
- Estimated LoC: prod ~+250-350 / Tests ~+300-400 ⇒ **`loc_limit_override 500` ist ein erwarteter Schritt** (nicht abspalten: B15 und Parität gehören dazu)
- Risk Level: **MEDIUM-HIGH** — zentrale Alarm-Buchungslogik aller 6 Alarmarten, ändert dreifach dokumentierte Semantik

### Technical Approach (Entscheidungen — technisch, nicht PO-Frage)
1. **Feldsemantik:** `sent` = „mindestens ein Kanal zugestellt". Neues Feld `attempted_channels` (= betreten, vor try) speist `reachable_channels`/Cockpit ⇒ #1459 AC-11/AC-15 und #1701 D7 (sent vs. reachable unterscheidbar) bleiben erhalten, die Unterscheidung wandert nur auf ein ehrlich benanntes Feld. `sent_channels.append` nach dem Send (Muster `send_trip_report`) ⇒ Wächter 1c löst sich semantisch, nicht per Umgehung. `delivered_channels` bleibt.
2. **Buchung:** Erfolg/Teilerfolg ⇒ alles wie heute. Totalausfall (keine Zustellung, keine bewusste Sperre) ⇒ KEIN State/Identität/Daily-Limit/nowcast; stattdessen **Fehlversuchs-Backoff** im bestehenden `ThrottleStore` mit eigenem Scope (`<scope>:retry`, 30 min). Löst die #684-Spam-/Flaky-Sorge ohne neuen Zähler und begrenzt Dubletten bei mehrdeutigen Fehlschlägen auf ≤1 je 30 min. **Kein Versuchsdeckel** (wäre ein Zähler, bei #1662 abgelehnt); Wiederholung endet natürlich, wenn das Ereignis entfällt (Warnung abgelaufen, Nowcast-Fenster vorbei).
3. **Alarm-Protokoll:** Totalausfall bleibt in `entries` mit `delivery_failed` (AC-15, „AC-11 gewinnt"); append im Totalausfall hinter das Backoff-Gate ⇒ max. ein Eintrag je Backoff-Fenster statt einer je Lauf.
4. **Sperre (Key in `blocked_reason_codes`) = terminal**, kein Retry, zählt nicht als Fehlschlag. Premium-Transportfehler (ohne Code) = Fehlschlag. Multi-Location-Pfad entsprechend angleichen (Parität).
5. **Telegram-Fan-out:** ≥1 Blase zugestellt ⇒ Kanal zugestellt (keine Wiederholung, sonst Dubletten); Fehlblase bleibt in `failed_channels` sichtbar.
6. **B15:** `send_test_report_outcome` nutzen, `success = outcome == "sent"`, eigener Text je Outcome, Exception ⇒ `success=False`. Nachweistest durch echten Kommando-Eingang. B16/B1 formal ableiten.
7. **ADR-0086:** `sent` = belegte Zustellung; Totalausfall begrenzt wiederholt via Backoff statt als Erfolg gebucht; Sperre terminal, Teilerfolg erledigt. Löst #684 AC-3 ab, präzisiert #1459 D4 / #1701 D7, setzt ADR-0021 :314/:337 und PO-Auftrag #1405 + Epic #2505 (jüngere PO-Entscheidung) um.

### Reihenfolge
ADR-0086 + Spec → RED (Semantik, Backoff, Sperre, Teilerfolg, Parität Trip/Ortsvergleich, B15 über Eingang) → `NotificationResult` + 3 Pfade → Aufrufer-Umstellung + Backoff → B15/B16/B1 → Wächter-Pflege (Ordinale!) → Spec-Tabelle.

### Risks
- Dubletten bei mehrdeutigen Fehlschlägen (Backoff begrenzt, verhindert nicht) — in ADR benennen.
- `sent_channels` wird in `notification_service.py` ~46× genutzt; Briefing-Pfade (`trip_report_scheduler.py:1759-1772`) nutzen es schon als „zugestellt" — dürfen nicht kippen.
- Ordinal-Verschiebung in `KNOWN_VIOLATIONS`; harter Zähltest 26/35.
- Prüfen, ob `attempted_channels.append` vor try vom Detektor 1c NICHT als Erfolgsmarker gewertet wird.
- Weitere Fixture-Nutzer prüfen: `tests/helpers/alert_log_fixtures.py`, `test_alert_channel_anchor_delivery.py`, `test_alert_state_briefing_reset.py`, `test_briefing_anchor_survives_dispatch_failure.py`.

### Open Questions
- keine PO-Fragen offen; Backoff-Dauer (30 min) und „kein Deckel" sind technische Entscheidungen, die der PO über die ACs freigibt.

## Hinweise aus TDD RED (für /50-implement)

- **Radar-Fingerabdruck muss das Zeitfenster enthalten:** Nowcast-Gefahrenklasse ist laut `resolve_hazard_class` immer `wet`; Ereignis B in `test_alarm_totalausfall_wird_wiederholt.py` unterscheidet sich nur im Zeitfenster (Regen in 50 statt 12 Min).
- **AC-6 Telegram-Teilzustellung:** Kanal gilt als zugestellt ⇒ `sent=True`, `delivery_outcome == "delivered"`, `telegram_fully_sent == False`. Telegram sollte dann NICHT in `failed_channels` stehen (sonst fehlt er in `delivered_channels`).
- **AC-20 Sperrfall:** im Sammelpfad enthält `attempted_channels` den gesperrten Kanal, in den anderen beiden Pfaden nicht (Spec Punkt 1) — Test vergleicht im Sperrfall nur `delivery_outcome`.
- **Kommando „report“ über Premium-SMS ist englisch:** Fehlschlag-Text mit „not sent“ formulieren, nie „nothing was sent“ (Test-Regex wertet „sent“ ohne vorangestelltes „not “/„never “ als Erfolgsmeldung).
- **B1 (`send_test_trip_report`)** ist nur über ein unbekanntes Outcome beobachtbar (Test nutzt `"zugestellt_teilweise"`) ⇒ `"sent": outcome == "sent"`.
- **Live-/E-Mail-Marker:** `test_issue_684_alert_email_guard.py` und `test_914_slice4_alert_sms_dispatch.py` laufen nur mit `-m "live or email"`. Dort sind `test_914…::test_ac1_sms_configured_sends_via_seven`, `test_issue_684…::test_ac2_…` und `::test_ac4_…` schon vor der Änderung rot, weil sie uhrzeitabhängig sind (Briefing-Sperre #1594, Testdaten ohne Briefing-Zeiten). Das ist keine Regression; Nebenbefund für #1196.
- Kommentare in `test_alarm_pruefstrecke_selbstschutz.py` / `test_radar_convective_check_failure.py` („triggered_count zählt den Versuch (#656)“) nach GREEN mitziehen.
- RED-Belege: `docs/artifacts/fix-1405-s1-alarm-zustellung/test-red-output.txt` (57 rot / 115 grün, CI-Socket-Flags) und `test-red-output-live.txt`.
