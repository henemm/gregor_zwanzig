# Context: fix-2598-ortsvergleich-alarm-kopfzeile

## Request Summary
Issue #2598: Ortsvergleich-Änderungsalarme zeigen in Telegram den Ortsnamen doppelt in der
Kopfzeile (`Ort Eins · Ort Eins · ↑ Böen`) und eine sinnlose Ortszeile `km 0–0`. Kanalparität
verlangt, E-Mail/SMS auf dieselben Felder zu prüfen.

## Gemessener Ist-Stand (Probe gegen `origin/main` 4fd66fa74)
Probe: `to_multi_point_alert_message(...)` → `render_subject/render_telegram/render_sms/render_email`.

| Fall | Kanal | Ausgabe heute | Befund |
|------|-------|---------------|--------|
| 1 Ort, 1 Metrik | Telegram | `<b>Ort Eins · Ort Eins · ↑ Böen</b>` … `km 0–0 · stärkste Stunde 14:00` | doppelt + km 0–0 |
| 1 Ort, 1 Metrik | Betreff (Mail) | `[Ort Eins] Ort Eins · ↑ Böen: 30 km/h→60 km/h` | doppelt |
| 1 Ort, 1 Metrik | Mail-Körper | `Wo & wann: Ort Eins · stärkste Stunde 14:00` | korrekt |
| 1 Ort, 2 Metriken | Telegram | `<b>Ort Eins · Ort Eins · 1 über Schwelle</b>` | doppelt |
| 1 Ort, 2 Metriken | Betreff | `[Ort Eins] Ort Eins · ↑ 1 über Schwelle: …` | doppelt |
| 2 Orte | Telegram (nur Vorschau/Bündel; echter Versand fächert je Ort auf) | `<b>Ort Eins, Ort Zwei · Ort Eins, Ort Zwei · …</b>` | doppelt |
| 2 Orte | Betreff | `[Ort Eins, Ort Zwei] Ort Eins, Ort Zwei · …` | doppelt |
| alle | SMS ohne `location_positions` | `Ort Eins Ort Eins: G30->60@14` | doppelt, ABER im echten Versand nicht erreichbar: `send_multi_location_deviation_alert` übergibt immer `location_positions` → Kopf entfällt (#1467 K-1/K-2) |

Echter Versandweg: `compare_alert.py` → `NotificationService.send_multi_location_deviation_alert`
→ `_dispatch_alert_message` (`notification_service.py:1991`): Betreff `render_alert_subject(alert_msg)`
(Bündel), Telegram `rich` je Ort `to_multi_point_alert_message([group])` → `render_alert_telegram`
(`:2207-2220`), Telegram `kurzform` und SMS/Premium-SMS = `render_alert_sms(..., location_positions=…)`.
Vorschau `compare_alert_preview_service.py:84-88` nutzt dieselben Renderer.

## Ursache
- `src/output/renderers/alert/project.py:521-524` `to_multi_point_alert_message`: `trip_short=collective_label`
  UND `location_label=collective_label`.
- `render.py:289` `_km_str(msg)` → `_location_of(events, msg.location_label)` → `format_alert_location`
  (`segments.py:120`) liefert bei gesetztem `location_label` den Ortsnamen. Die Kopfzeilen bauen
  `f"{msg.trip_short} · {km} · …"` (Telegram `render.py:1713`, `:1724`) bzw. `f"[{msg.trip_short}] {km} · …"`
  (Betreff `render.py:1357`, `:1364`, `:1376`) → Name zweimal.
- `km 0–0`: Telegram-Einzelereignis-Zweig `render.py:1717` ruft `_where_when(e, lang=lang)` OHNE
  `location_label`; Events tragen `km_from=km_to=0.0` (`project.py:512`) → Stufe 4 in
  `format_alert_location` → `km 0–0`. Die E-Mail macht es richtig: `render.py:1585`
  `_datablock_single(e, e.location_label or msg.location_label)`.

## Related Files
| File | Relevance |
|------|-----------|
| `src/output/renderers/alert/render.py` | `render_subject` (1340ff), `render_telegram` (1701ff), `_km_str` (289) — Fix-Ort |
| `src/output/renderers/alert/project.py` | `to_multi_point_alert_message` setzt beide Felder (Invariante #1169 AC-7: 1 Gruppe byte-identisch zu `to_point_alert_message`) |
| `src/output/renderers/alert/segments.py` | `format_alert_location` (SSOT Ortsauflösung, nicht ändern) |
| `src/services/notification_service.py` | Dispatch, Telegram-Fan-out je Ort |
| `src/services/compare_alert_preview_service.py` | Vorschau, gleiche Renderer |
| `tests/tdd/test_alert_preview_compare_paritaet.py`, `test_compare_alert_telegram_per_location.py`, `test_fix_1767_nowcast_mehrort_kurzform.py` | Bestandstests Compare-Alarm |

## Existing Patterns
- #1467 K-1/K-2 (`render_sms`, `render.py:1895-1934`): genau dieselbe Doppelung im SMS-Kopf wurde
  dort durch Wegfall des Kopfes beseitigt — Präzedenz „Name nur einmal".
- #1767 (gerade gemergt): Radar-Mehrort-Kopf ohne Namens-Join, ohne `km 0–0` (`telegram_format.md:51`).
- Trip-Pfad: `trip_short` = Trip-Name, `location_label=None`, `km` = Etappen-/km-Angabe → Kopf
  `GR20 · S3 · ↑ Böen` bleibt unverändert (Regressionsinvariante).

## Dependencies
- Upstream: `format_alert_location`, `_location_of`, `_where_when`, i18n-Katalog `t(...)`.
- Downstream: alle Alarmwege (Trip-Δ, Trip-Radar, Compare-Δ, Compare-Radar, Vorschau, Validator-Render
  `validator_render_service.py:231`), Mail-Validatoren (`email_spec_validator.py`, Briefing-Validator) lesen Betreff.

## Existing Specs
- `docs/specs/modules/feat_2293_s2_compare_alarm_kanaele.md`, `alert_render_foundation.md`,
  `feat_1737_alarm_stundenzeilen.md`; Formate `docs/reference/telegram_format.md` §Änderungs-Alarm,
  `renderer_email_spec.md`.

## Risks & Considerations
- Trip-Alarme dürfen sich byte-genau nicht ändern (Trip hat `location_label=None`).
- Radar/Onset-Pfade (`render.py:606/618/1007`) nutzen ebenfalls `{trip_short} {km}` — Compare-Radar
  mit einem Ort prüfen (seit #1767 Mehrort korrekt; Einzelort `_km_str_onset` bewusst ohne Label).
- Bestehende Tests, die die Doppelung wörtlich erwarten, müssen bewusst angepasst werden.
- Nicht im Scope: „Änderung unter" bei Regel „über" (#1895), roher `stand_at` nur Probe-Artefakt.
- DE/EN: keine neuen Nutzertexte nötig (nur Weglassen), Protokoll-Token unberührt.

## Analysis

### Type
Bug (Darstellungsfehler aller Ortsvergleich-Alarme mit genau einem bzw. gebündelten Orten).

### Zusätzlich gemessene Fälle (Probe 2026-11-09 gegen 4fd66fa74, Skripte im Scratchpad)
Gleiche Fehlerklasse „Ort ohne Kilometrierung wird als `km 0–0` bzw. doppelt genannt", bisher nicht im Issue:

| Fall | Kanal | Ausgabe heute |
|------|-------|---------------|
| Compare-Δ, 1 Ort, nur Beginn-Verschiebung | Betreff | `[Ort Eins] km 0–0 · …-Beginn 10:00 (2 h früher)` |
| dito | Telegram/Mail-Zeile | `…-Beginn: 12:00 → 10:00 (2 h früher · km 0–0)` |
| Compare-Δ, 1 Ort, Δ + Beginn-Verschiebung | Telegram + Mail | Beginn-Zeile `(… · km 0–0)` |
| **Compare-Radar, 1 Ort** (`to_multi_location_onset_alert_message`, 1 Gruppe: `location_label=None`, `trip_short=Ort`) | Betreff | `[Ort Eins] km 0–0 · Regen in 30 Min` |
| dito | Telegram | `<b>Ort Eins · km 0–0 · Regen in 30 Min</b>` |
| dito | Mail-Körper | `Wo & wann: km 0–0 · ab 14:30` |
| Compare-Δ, 2 Orte, nur Beginn-Verschiebung | alle | korrekt (je Event `location_label`) |
| Trip (Kontrolle) | alle | `[GR20] Segment 3 · ↑ Böen…`, `Segment 3 · stärkste Stunde` — muss byte-gleich bleiben |

Echter Versandweg Compare-Radar: `notification_service.py:1304` → `to_multi_location_onset_alert_message` (auch für einen Ort). Also produktiv sichtbar.

**Scope-Entscheidung (Tech Lead):** Radar-Einzelort und Beginn-Verschiebung gehören in dieses Ticket — dieselbe Ursache (Punkt-Kontext ohne km fällt auf `format_alert_location` Stufe 4 bzw. doppelt den Namen), dieselbe Nachrichtenfläche, Issue ist `go-live-pflicht`, Kanalparität verlangt es (Issue-Text „E-Mail/SMS auf dieselben Felder prüfen"). Kein neuer Nutzertext, keine Produktentscheidung → kein PO-Halt. Kommentar im Issue.

### Zielbild (aus Trip-Analogie + Mail-Körper, der heute schon richtig ist)
- **Kopfzeilen (Betreff, Telegram-Kopf):** Name genau einmal. Compare: `[Ort Eins] ↑ Böen: 30 km/h→60 km/h`, `<b>Ort Eins · ↑ Böen</b>`, `<b>Ort Eins, Ort Zwei · 2 Änderungen seit dem Briefing</b>`, `[Ort Eins] Regen in 30 Min`, `<b>Ort Eins · Regen in 30 Min</b>`, `[Ort Eins] …-Beginn 10:00 (2 h früher)`.
- **Ereignis-/Ortszeilen:** statt `km 0–0` der Ortsname, wie die Mail heute schon (`Wo & wann: Ort Eins · stärkste Stunde 14:00`). Telegram-Einzelereignis: `Ort Eins · stärkste Stunde 14:00`; Radar-Mail `Wo & wann: Ort Eins · ab 14:30`; Beginn-Zeile `(2 h früher · Ort Eins)`.
- **Nirgends mehr `km 0–0`** in einem Ortsvergleich-Alarm (alle Kanäle).
- **Trip-Alarme byte-identisch** (Trip setzt `location_label` nie).
- SMS/Premium-SMS: realer Versand bereits korrekt (Kopf entfällt per `location_positions`, #1467); der unerreichbare Zweig `render.py:1933` (`"{trip} {location_label}:"` ohne Positionen) wird mitbereinigt, damit Vorschau/Validator-Render nicht doppelt zeigen.

### Affected Files (with changes)
| File | Change Type | Description |
|------|-------------|-------------|
| `src/output/renderers/alert/render.py` | MODIFY | Eine Hilfsfunktion „Ortsteil der Kopfzeile" (leer im Punkt-Kontext, d. h. `msg.location_label` gesetzt — Name steht schon im `trip_short`-Slot); genutzt von `render_subject` (1357/1364/1376, 1349), `render_telegram` (1713/1724), Onset-Kopf (`_render_subject_onset` 618, `_render_telegram_onset` 1007). Ereignis-Ort mit Fallback `e.location_label or msg.location_label`: Telegram-Einzelzweig 1717 (wie Mail 1585), `_onset_shift_where` (Fallback durchreichen), `_km_str_onset` für den Einzelort-Radar (Mail „Wo & wann", Telegram-Zeile). SMS-Kopf 1933 ohne Doppelung. |
| `src/output/renderers/alert/project.py` | MODIFY | `to_multi_location_onset_alert_message`: bei genau einer Gruppe nachrichtenweites `location_label=<Ort>` setzen (per-Event bleibt `None`, Invariante #1041 AC-5 bleibt). Damit erkennt der Renderer den Punkt-Kontext einheitlich an `msg.location_label`. Prüfen, dass `_render_sms_onset` (erkennt Einzelort an `COMPARE_RADAR_SOURCE`) davon unberührt bleibt. |
| `tests/tdd/test_fix_2598_ortsvergleich_alarm_kopfzeile.py` | CREATE | RED-Tests über die echten Projektionen (`to_multi_point_alert_message`, `to_multi_location_onset_alert_message`) → alle Renderer; Fälle: 1 Ort/1 Metrik, 1 Ort/2 Metriken, 2 Orte, 1 Ort nur Beginn-Verschiebung, Radar 1 Ort, Radar 2 Orte; Trip-Kontrolle byte-gleich; DE + EN. |
| `tests/tdd/test_alert_location_vocabulary.py` | MODIFY | 400–405 und 435 frieren die Doppelung/`km 0–0` als „Bestandsverhalten" ein (ausdrücklich „NICHT Gegenstand von #1744") → bewusst auf Zielbild umstellen. |
| `tests/fixtures/alarm_kette/ortsvergleich_radar_verdopplung_vor_2848.json` | MODIFY? | enthält `[Verschaerfungsdorf] km 0–0 …` — prüfen, ob Fixture erwartete Ausgabe ist (dann anpassen) oder historischer Eingangsbeleg (dann lassen). |
| weitere Bestandstests Compare-Alarm (`test_issue_1169_*`, `test_issue_1170_*`, `test_alert_preview_compare_paritaet.py`, `test_compare_alert_telegram_per_location.py`, `test_fix_1767_*`) | MODIFY (nur falls sie die Doppelung wörtlich erwarten) | Developer ermittelt per gezieltem Lauf. |
| `docs/reference/telegram_format.md`, `renderer_email_spec.md` | MODIFY | Beispiele Ortsvergleich-Kopf ohne Doppelung/km. |

### Scope Assessment
- Files: ~3 Produktiv/Doku + 1 neue Testdatei + 2–5 Testanpassungen
- Estimated LoC: Produktivcode +30/−15, Tests +200
- Risk Level: MEDIUM — zentraler Alarm-Renderer aller Alarmarten; Schutz: Trip setzt `location_label` nie, daher ist die Änderung an diese Bedingung gekoppelt; Trip-Byte-Gleichheit als eigener Test.

### Technical Approach
Fix im Renderer, nicht in der Projektion von `trip_short`: Das `[Name]`-Präfix im Betreff ist Hausform für alle Alarme (Trip: `[GR20]`) und wird von Postfach-Filtern/Validatoren gelesen; es bleibt. Stattdessen entfällt im Punkt-Kontext der zweite Ortsteil der Kopfzeile, und Ereigniszeilen fallen auf den Ortsnamen zurück. `format_alert_location` (SSOT, Stufenfolge) bleibt unverändert — die Korrektur liefert ihr nur das bereits vorhandene Label. Ein Kriterium für „Punkt-Kontext" (`msg.location_label` gesetzt), damit Δ- und Radar-Pfad dieselbe Regel sprechen (ADR-0021 / Code-Teilung Trip-Vergleich).

Verworfen: `trip_short` auf einen Sammelbegriff ändern (bricht #1169-AC-7-Invariante und Betreff-Hausform); `location_label` nur im Telegram-Zweig unterdrücken (Betreff/Mail blieben doppelt — Kanalparität verletzt).

### Dependencies
Upstream: `format_alert_location`, `_location_of`, `_where_when`, `_onset_shift_where`, `_km_str_onset`, i18n-Katalog (keine neuen Schlüssel). Downstream: alle Alarmwege, Vorschau (`compare_alert_preview_service.py`), Validator-Render (`validator_render_service.py:231`), Mail-Validatoren (lesen Betreff nur per Fragment).

### Open Questions
- keine an den PO (reiner Darstellungsfehler, Zielbild folgt aus Mail-Körper und Trip-Analogie).
