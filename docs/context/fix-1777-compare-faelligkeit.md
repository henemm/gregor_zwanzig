# Context: fix-1777-compare-faelligkeit

## Request Summary
Issue #1777 (S4b aus Epic #1722): Der Ortsvergleich entscheidet die Fälligkeit seiner
Briefing-Slots heute per exakter Stundengleichheit. Umstellen auf ein Fälligkeitsfenster
`stunde <= ortsstunde < stunde + 3` plus Idempotenz-Vermerk je `(preset_id, slot, ortstag)`,
analog zum Trip-Pfad seit #1725. Sonst entfällt ein auf 02:00 gestellter Vergleich am
Frühjahrs-Umstellungstag, geht am Herbsttag doppelt raus und fällt bei jedem ausgefallenen
Cron-Tick ersatzlos aus.

## Related Files
| File | Relevance |
|------|-----------|
| `src/services/compare_slot_scheduler.py:142-220` | `presets_due_for_hour`: Stundengleichheit `slots.*_time.hour == hour` (Z. 211/213). Reine Funktion ohne IO. Zielort des Fensters. |
| `src/services/dispatch_orchestrator.py:123-238` | `CompareDispatchStrategy`: `collect_due` (ruft `presets_due_for_hour`, hier gehört der Vermerk-Filter hin, Prüfort = Wirkort), `pre_pass` (Auto-Pause + Nachhol-Vermerke #2587, bekommt `due`), `dispatch_one` (→ `_dispatch_due_preset`). `dispatch_one` erhält `now_utc` bereits als Parameter. |
| `src/services/scheduler_dispatch_service.py:151-192` | `_dispatch_due_preset`: Versand eines fälligen Presets, schluckt alle Ausnahmen → bool. Hier muss reserve/record/release um `send_one_compare_preset` gelegt werden. |
| `src/services/scheduler_dispatch_service.py:674-1062` | `send_one_compare_preset`: wirft `SendOutcomeError` mit `channels_unreachable` (Z. 779/1006-1014), `no_channels` (782), `no_weather` (853/859); `ValueError` bei Skip-Pfaden. Schreibt am Erfolg `briefing_log` mit `entity_type="compare"` (1021-1029, #2281) und `letzter_versand` (reine Anzeige, 490-526). |
| `src/services/scheduler_dispatch_service.py:200-403` | Nachhol-Vermerke des Vergleichs (#2587): `_mark_compare_undelivered`, `process_compare_pending_markers`, `_catchup_verdict` mit `due_keys` aus `due` (Verdict „wait", wenn der reguläre Slot jetzt fällig ist). Wechselwirkung mit dem Fenster. |
| `src/services/scheduler_dispatch_service.py:1064-1128` | `send_compare_preset`: Handversand/Befehl (on_demand=True). Darf vom Vermerk NICHT berührt werden (Trip-AC-12-Analogie). |
| `src/services/briefing_slots.py` | `BriefingSlotStore` (Trip): Schlüssel `(trip_id, slot, local_day)`, `reserve`/`record_outcome`/`release`/`is_recorded`/`is_recorded_or_claimed`, fail-closed, CLAIM_TTL 900 s, Reparatur #2231, Rückwärts-Ableitung aus `briefing_log.json` nur solange eigene Datei fehlt; filtert Log-Einträge auf `entity_type in (None, "trip")` (#2281 AC-5) und überspringt `on_demand`. Felder heißen `trip_id`. |
| `src/services/trip_report_scheduler.py:130, 355-394, 764-912` | Vorbild: `NACHHOL_FENSTER_STUNDEN = 3`, `nachhol_fenster_offen`, `_slot_faellig_vor_ort`, `trip_slot_due`, `_collect_due_trips` (Filter in der Sammelphase), `_dispatch_due_item` (reserve-then-release, unbekannter Ausgang ⇒ sperren). |
| `src/services/compare_alert.py:340-355`, `src/services/compare_official_alert.py:245-258` | Alarm-Sperre „Briefing steht bevor" (#1594): `check_briefing_imminent(briefing_due_at=lambda m: due_or_raise(presets_due_for_hour([preset], ..., m)))`. Ändert sich die Semantik von `presets_due_for_hour`, ändert sich die Sperre mit. Trip-Pendant nutzt Fenster + `is_recorded` (sonst schweigt der Alarm bis 3 h nach zugestelltem Briefing). |
| `src/services/next_briefing.py:190-230` | Anzeige „Nächstes Briefing" für den Vergleich: fragt `presets_due_for_hour` an exakten Slot-Zeitpunkten; Doku sagt „Exakte Slot-Stunde, kein Nachholfenster". Trip-Pendant nimmt einen `BriefingSlotStore` read-only entgegen. |
| `api/routers/internal.py:~220-250` | Endpoint für nächstes Briefing (Trip mit Store, Compare ohne). |
| `src/services/trip_command_processor.py:1471` | nutzt `preset_ortstag` (unberührt). |
| `internal/store/user.go:468`, `internal/handler/data_export_test.go:52` | Go-Liste der Nutzerdateien (Export/Löschung) kennt `briefing_slots.json`. Eine NEUE Datei (z. B. eigener Compare-Speicher) müsste dort ergänzt werden. |
| `internal/scheduler/scheduler.go:~292` | Go-Cron (`robfig/cron` mit `WithLocation(Europe/Vienna)`), fällt an Umstellungstagen aus; Kommentar referenziert `briefing_slots.py` CLAIM_TTL. |

## Existing Patterns
- **Fenster + Vermerk in der Sammelphase** (#1725): `nachhol_fenster_offen` → `is_recorded_or_claimed` → `due.append`. Ein Prädikat für Sammellauf, Alarm-Sperre und Anzeige (#1969 AC-11).
- **reserve-then-release** im Versand: `reserve` (fail-closed, False ⇒ kein Versand), Ausgang in `VERMERK_AUSGAENGE` ⇒ `record_outcome`, `channels_unreachable`/Ausnahme ⇒ `release`, unbekannter Ausgang ⇒ sperren.
- **Rückwärts-Ableitung** aus `briefing_log.json` beim Rollout; Compare schreibt dort bereits Einträge mit `entity_type="compare"`, `kind`=Slot, `on_demand`-Flag — die Ableitung ist für den Vergleich also datenseitig möglich (Feld heißt `trip_id`/Entity-ID prüfen in `briefing_log.append_briefing_log`).
- **Zone je Preset** (#1726): `_preset_ortszeit` / `first_resolvable_tz` über den ersten auflösbaren Ort. Ortstag und Ortsstunde aus EINER Auflösung.
- **Fehlerisolation je Preset** (#2217): `DueList.failed_ids`, `report_unit_failure`.
- **Code-Teilung Trip/Vergleich ist Gate** (CLAUDE.md): Fenster-Konstante, Fensterprädikat und Vermerk-Speicher sollten geteilt statt dupliziert werden.

## Dependencies
- Upstream: `utils.timezone` (`local_dt`, `first_resolvable_tz`), `compare_alert_guard.is_silenced`, `services.file_lock`, `briefing_log`.
- Downstream: `CompareDispatchStrategy` (Go → `POST /api/scheduler/*` → `run_briefing_dispatch`), `process_compare_pending_markers` (due_keys), Alarm-Sperre in `compare_alert`/`compare_official_alert`, `next_compare_briefing` + internal-Endpoint, Go-Export/Löschung der Nutzerdateien.

## Existing Specs
- `docs/specs/modules/fix_1725_faelligkeit_und_idempotenz.md` — Vorbild (Trip), 506 Zeilen, inkl. Adversary-Funde F004/F006.
- `docs/specs/modules/fix_1726_ruhezeit_und_zaehler_ortszone.md` — Ortszone des Vergleichs.
- `docs/specs/modules/compare_preset_zeitplan.md` — Slot-Modell des Vergleichs (#1232).
- `docs/adr/0051-drei-zeitbegriffe-zone-an-den-daten.md` (Stundengleichheit unzulässig, Idempotenz-Schlüssel), `docs/adr/0044-kalendertage-folgen-der-ortszeit.md`.
- Bestehende Tests: `tests/test_briefing_slot_fail_closed.py`, `tests/test_briefing_slot_reparatur.py`.

## Risks & Considerations
- **Speicher-Entscheidung (Analyse):** `BriefingSlotStore` generalisieren (Entity-Typ im Schlüssel, Altbestand ohne Typ = Trip) vs. eigener Compare-Speicher. Generalisieren erfüllt die Teilungs-Pflicht, berührt aber den Trip-Pfad (Kollision gleicher IDs Trip/Preset, vgl. #2281 AC-5). Eigene Datei ⇒ Go-Dateiliste (`internal/store/user.go`) ergänzen.
- **Rückwärts-Ableitung beim Rollout:** Die Existenz-Bedingung „eigene Datei fehlt" greift nicht, wenn `briefing_slots.json` durch Trips schon existiert — für den Vergleich wäre dann kein Rollout-Schutz da. Muss entity-spezifisch gelöst werden.
- **Zwei Commits in einem PR:** erst Vermerk bei unverändertem `==`, dann Fenster öffnen (Issue-Vorgabe).
- **Testfalle Fensterbreite:** nur am ausgefallenen Tick messbar; Schwelle am Wert daneben prüfen (H+1, H+2 fällig, H+3 nicht).
- **Semantik-Wechsel für Mitnutzer von `presets_due_for_hour`:** Alarm-Sperre (#1594) und Anzeige „Nächstes Briefing". Ein Fenster ohne Vermerk-Blick ließe den Alarm 3 h nach zugestelltem Briefing schweigen; die Anzeige erwartet exakte Slot-Stunden.
- **Nachhol-Vermerke #2587:** `_catchup_verdict` „wait" hängt an `due_keys`; mit Fenster bleibt ein fehlgeschlagener Slot länger „fällig" — prüfen, ob Nachholer und regulärer Fensterversand doppelt senden können. Bei `channels_unreachable` schreibt `send_one_compare_preset` bereits einen Nachhol-Vermerk UND der Slot würde per `release` im Fenster wieder fällig ⇒ potenzielle Doppelung.
- **Ausgang-Mapping:** Compare liefert Ausnahmen statt Ausgangs-Strings (`SendOutcomeError.code`, `ValueError` für no-recipient); `_dispatch_due_preset` schluckt alles. Für reserve-then-release braucht es eine eindeutige Abbildung auf sent / no_channels / no_weather / channels_unreachable / Fehler.
- **Weekly-Presets:** Fenster über Mitternacht hinaus? (Slot 23:00 → Fenster bis 01:59 am Folgetag — Ortstag wechselt; Trip-Lösung prüfen, wie dort mit `stunde + 3 > 24` umgegangen wird.)
- **Mandantentrennung:** Speicher je `user_id`, Test mit zwei Nutzern; zwei Presets desselben Nutzers in verschiedenen Zonen.
- **Handversand / HEUTE/MORGEN-Befehl** (`send_compare_preset`) darf den Vermerk weder schreiben noch vom Vermerk blockiert werden.

## Analysis

### Type
Bug (nutzersichtbar: ausgefallener bzw. doppelter Vergleichs-Versand an Umstellungstagen und nach ausgefallenem Cron-Tick).

### Befunde (verifiziert, Analyse 2026-11-01)
- `BriefingSlotStore` (`src/services/briefing_slots.py`): Einträge `{trip_id, slot, local_day, recorded_at, outcome}`, `_passt` vergleicht fest auf `trip_id` (346-355). Rückwärts-Ableitung (`_log_bezeugt_versand`, 367-404) nur solange die Datei fehlt oder `rebuilt_from_log_at` gesetzt ist; `_log_traegt_versand` filtert `entity_type in (None,"trip")` (434) und `on_demand` (438). **PO-Entscheidung 2026-08-11 (Docstring 383-388):** enge Lesart; das einmalige Rollout-Restfenster („ein anderer Eintrag hat die Datei schon angelegt") ist bewusst akzeptiert.
- `briefing_log` Compare-Einträge (`scheduler_dispatch_service.py:1021-1029`, `briefing_log.py:56-66`): `entity_type="compare"`, `entity_id=preset_id`, `kind=morning|evening`, `sent_at` UTC, `on_demand`; kein `trip_id`, kein Ortstag (aus `sent_at` + Preset-Zone rekonstruierbar).
- Trip-Fenster `nachhol_fenster_offen` (`trip_report_scheduler.py:355-359`): `stunde <= h < stunde + NACHHOL_FENSTER_STUNDEN` (=3, Z. 130), **ohne** Mitternachts-Überlauf (Slot 23 ⇒ nur 23:00-23:59); Schlüssel-Ortstag = Lauftag.
- Trip `_dispatch_due_item` (850-912): reserve (False ⇒ kein Versand) · Ausnahme ⇒ release+raise · `VERMERK_AUSGAENGE={sent,no_stage,no_weather,no_channels}` ⇒ record · `channels_unreachable` ⇒ release · unbekannt ⇒ record (sperren). `no_weather` wird vermerkt, weil der #1012-Pending-Marker die Nachlieferung abdeckt (Kommentar 104-110).
- **Compare `no_weather` im Cron schreibt heute KEINEN Nachhol-Vermerk** (Raise in `send_one_compare_preset` Z. 853/859 liegt vor dem Versand-`try`; Marker nur bei Versand-Ausnahme Z. 992 und `channels_unreachable` Z. 1012; Re-Mark bei no_weather nur im Nachholer selbst, Z. 354). Heute fällt ein Vergleich bei kurzem Wetterausfall also ersatzlos aus.
- `_dispatch_due_preset` (151-192) gibt nur `bool` zurück; `SendOutcomeError` (Unterklasse `ValueError`, `.code`) geht verloren; `no_channels` zählt in `CompareDispatchStrategy.dispatch_one` als failed (Trip: neutral). Aufrufer: `dispatch_orchestrator.py:226` (truthy-Prüfung) und `tests/tdd/test_compare_preset_send.py:186`.
- Nachhol-Vermerke #2587: `process_compare_pending_markers` im `pre_pass`, `_catchup_verdict` (311-330) „wait", wenn `(preset, Zieltag)` in `due_keys`. Mit Fenster + Vermerk-Filter fehlt ein bereits versendeter Slot in `due_keys` ⇒ bleibt ein Marker ungeräumt (`_clear_compare_dispatch_error` ist fail-soft), liefert das Verdict „send" ⇒ Doppelversand.
- Mitnutzer von `presets_due_for_hour`: `CompareDispatchStrategy.collect_due` (dispatch_orchestrator.py:162-175), Alarm-Sperre `compare_alert.py:343-355` + `compare_official_alert.py:245-258` (Trip-Pendant `trip_briefing_due_at` mit Fenster + `is_recorded`), `next_briefing.next_compare_briefing` (exakte Slot-Momente, 190-230; Trip-Pendant mit Store read-only), `run_compare_presets_daily(?hour=)` (manueller Auslöser, 439-455).

### Affected Files (with changes)
| File | Change Type | Description |
|------|-------------|-------------|
| `src/services/briefing_slots.py` | MODIFY | Klasse parametrieren (`filename`, `entity_type`, `id_key`; Defaults = Trip, byte-gleich); Compare-Ableitung über `entity_type=="compare"` + `entity_id`; Lese-Methode für den Ausgang eines Vermerks; geteiltes reines Fensterprädikat + Konstante |
| `src/services/trip_report_scheduler.py` | MODIFY | `nachhol_fenster_offen` nutzt das geteilte Prädikat, Konstante re-exportiert (keine Verhaltensänderung) |
| `src/services/compare_slot_scheduler.py` | MODIFY | Z. 211/213 `==` ⇒ Fensterprädikat (Commit 2); optionaler read-only Store (Vermerk-Blick) |
| `src/services/scheduler_dispatch_service.py` | MODIFY | Versand liefert Ausgang statt bool; reserve/record/release um `send_one_compare_preset`; Cron-`no_weather` schreibt Nachhol-Vermerk; `_catchup_verdict` prüft Store (drop nur bei Ausgang `sent`) |
| `src/services/dispatch_orchestrator.py` | MODIFY | `collect_due`: Vermerk-Filter (`is_recorded_or_claimed`); `dispatch_one`: Zählung nach Ausgang (no_channels neutral) |
| `src/services/compare_alert.py`, `src/services/compare_official_alert.py` | MODIFY | Alarm-Sperre mit Fenster + `is_recorded` (Commit 2) |
| `src/services/next_briefing.py`, `api/routers/internal.py` | MODIFY | Anzeige „Nächstes Briefing" für Compare mit Store read-only, Fenster/überfällig wie Trip (Commit 2) |
| `internal/store/user.go`, `internal/handler/data_export_test.go` | MODIFY | neue Nutzerdatei `briefing_slots_compare.json` in Export/Löschung |
| `tests/tdd/test_compare_preset_slot_dispatch.py`, `tests/tdd/test_next_briefing.py`, `tests/tdd/test_compare_preset_send.py` | MODIFY | Z. 84 (`due_at_8 == []` bei Slot 7) und Z. 506 (AC-9 „ohne Nachholfenster") bewusst umschreiben; bool-Rückgabe |
| neue Testdatei(en) für Fenster/Vermerk/Rollout/Nachholer | CREATE | siehe AC-Kandidaten |

In RED zu prüfen (ungeprüft, Risiko): `test_compare_briefing_nachholen.py`, `test_dispatch_orchestrator.py`, `test_compare_anchor_target_date.py`, `test_compare_dispatch_failed_tally.py`, Tests mit `run_compare_presets_daily(hour=6)`.

### Scope Assessment
- Files: ~10 produktiv (+2 Go-Zeilen), ~4-6 Testdateien
- Estimated LoC: Commit 1 ~+140/-20, Commit 2 ~+60/-15 (produktiv); Tests ~+300
- Risk Level: MEDIUM-HIGH (zentraler Versandpfad, berührt die geteilte Trip-Klasse; Fehler = Doppel- oder Ausfall-Versand)

### Technical Approach (Entscheidungen Tech-Lead, mit Begründung)
1. **Speicher: dieselbe Klasse `BriefingSlotStore`, parametriert, eigene Datei `briefing_slots_compare.json`** (Variante B). Teilungs-Gate erfüllt (ein Code), Trip-Pfad byte-gleich über Defaults, Kollision Trip-/Preset-ID konstruktionsbedingt ausgeschlossen, und die Compare-Datei fehlt beim Rollout ⇒ die vorhandene Rückwärts-Ableitung greift für den Vergleich. Verworfen: (A) gleiche Datei mit Typfeld (höchstes Trip-Regressionsrisiko, Existenz-Bedingung greift für Compare nie), (C) eigene Klasse (verletzt Teilungs-Gate). Eintragsfeld `preset_id`.
2. **Rollout-Ableitung: identische Semantik wie Trip** (PO-Entscheidung 2026-08-11, enge Lesart). Kein `seeded_at`-Sondermechanismus: das wäre eine stille Abweichung von einer PO-Entscheidung und müsste dann für beide Pfade gelten (eigenes Ticket, falls je gewünscht).
3. **Ein Schlüssel-Helfer:** `(preset_id, slot, ortstag)` aus EINER `_preset_ortszeit`-Auflösung; derselbe Helfer für `collect_due`-Filter, `reserve`, `_catchup_verdict`-Prüfung und Log-Ableitung (`zone` = Preset-Zone). Weicht eine Stelle ab, entsteht stiller Doppelversand.
4. **Fenster:** geteiltes reines Prädikat + Konstante (3 h) in `briefing_slots.py`, von Trip und Compare genutzt; kein Mitternachts-Überlauf (Trip-Parität). Das Weekly-Gate prüft den Ortstag des Laufs.
5. **Ausgangs-Abbildung Compare:** Erfolg ⇒ `sent`; `SendOutcomeError.code` ⇒ Code; sonstige `ValueError`/Ausnahme ⇒ release + Fehler. Vermerkt werden `sent`, `no_channels`, `no_weather` (geteilte `VERMERK_AUSGAENGE`); `channels_unreachable` und Ausnahmen ⇒ release; unbekannt ⇒ sperren. `no_channels` zählt neutral (Trip-Parität). Beide Aufrufer der bisherigen bool-Funktion explizit anpassen (kein truthy-Vergleich auf Strings).
6. **`no_weather` im Cron:** vermerken UND Nachhol-Vermerk schreiben (Trip-Parität: dort deckt der Pending-Marker die Nachlieferung). Schließt nebenbei die heutige Lücke „kurzer Wetterausfall ⇒ Vergleich fällt ersatzlos aus".
7. **Nachholer:** `_catchup_verdict` prüft zusätzlich den Store. Slot mit Ausgang `sent` ⇒ drop; bei `no_weather`/`no_channels` NICHT droppen (dort ist der Marker der Retry). Eigener AC.
8. **Ein Prädikat für Sammellauf, Alarm-Sperre und Anzeige** (#1969 AC-11-Parität): Sammellauf `is_recorded_or_claimed`, Alarm/Anzeige `is_recorded`. `test_next_briefing.py:506` (frühere Spec-Entscheidung „exakte Slot-Stunde, kein Nachholfenster") wird in der neuen Spec ausdrücklich als **abgelöst** benannt, Begründung ADR-0051.
9. **Handversand/Befehle** (`send_compare_preset`, `on_demand=True`): schreiben keinen Vermerk und werden vom Vermerk nicht blockiert; die Log-Ableitung überspringt `on_demand`.
10. **Zwei Commits in einem PR** (Issue-Vorgabe): Commit 1 Vermerk bei unverändertem `==` (verhaltensneutral bis auf no_channels-Zählung und no_weather-Marker), Commit 2 Fenster + Alarm/Anzeige. Testfalle: Die Fensterbreite ist nur am ausgefallenen Tick messbar (H+1, H+2 fällig, H+3 nicht).
11. **Manueller Auslöser `run_compare_presets_daily(?hour=)`** läuft über denselben Sammelpfad inkl. Vermerk (kein Sonderpfad).

### Dependencies
Upstream: `utils.timezone` (`local_dt`, `first_resolvable_tz`), `services.file_lock`, `briefing_log`, `send_outcomes`. Downstream: Go-Cron → `POST /api/scheduler/*` → `run_briefing_dispatch` → `CompareDispatchStrategy`; Nachholer #2587; Alarm-Sperre #1594; Anzeige „Nächstes Briefing"; Go-Export/Löschung der Nutzerdateien.

### AC-Kandidaten für die Spec
Frühjahr (Ortsstunde 02 fehlt ⇒ genau ein Versand um 03) · Herbst (zweimal 02 ⇒ genau ein Versand) · ausgefallener Tick (H+1, H+2 fällig, H+3 nicht) · Preset mit Morgen- und Abend-Slot am selben Tag · zwei Presets desselben Nutzers in verschiedenen Zonen · zwei Nutzer isoliert · Rollout: Log-Eintrag vom Ortstag ⇒ kein zweiter Versand · on_demand-Log-Eintrag blockiert nicht · channels_unreachable ⇒ Retry im Fenster, kein Doppel mit Nachholer · Marker ungeräumt + Slot `sent` ⇒ kein Nachhol-Doppel · no_weather ⇒ vermerkt + Nachhol-Vermerk · no_channels neutral · Schreibfehler ⇒ fail-closed (kein Versand) · Alarm-Sperre schweigt nach zugestelltem Briefing nicht weiter · Handversand unberührt.

### Open Questions
Keine an den PO; alle Punkte oben sind als Tech-Lead-Entscheidungen festgehalten.
