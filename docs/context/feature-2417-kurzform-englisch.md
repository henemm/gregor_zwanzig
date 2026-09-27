# Context: feature-2417-kurzform-englisch

## Request Summary
PO-Entscheid 27.09.2026 (#2417): Die Kurzform (SMS, Premium-SMS/Garmin, Telegram-Kurzform) ist englisch, also müssen dort auch die **Befehle** englisch sein. Die SMS-Hilfe nennt nur englische Befehle (HELP, TODAY, TOMORROW, NOW, STORMS, ROUTE km, RESTDAY n, STATUS, PAUSE 2D, SKIP, STOP, RESUME), jeweils mit der **Wirkung** („was kommt zurück“) statt einer Wortübersetzung. Ein neuer Befehl CODES liefert die Wetter-Kürzel mit Bedeutung. Deutsch und Englisch werden auf **allen** Kanälen als Befehl akzeptiert. E-Mail und Telegram-Langform bleiben deutsch.

Auslöser: Der Prod-Test am 27.09. (AC-27) lieferte auf `hilfe` den Text „Commands: HEUTE today, MORGEN tomorrow, … Codes: D,Night,L,DayMax,TF,…“. Er übersetzt nur Wörter, die Kürzel stehen ohne Bedeutung da, und deutsche Befehle stehen in einer englischen SMS. Die alten Tests prüften nur Vollständigkeit und Länge, nicht den Nutzen.

## Related Files
| File | Relevance |
|------|-----------|
| `src/services/trip_command_processor.py:190-206` | `_BARE_KEYWORD_MAP`: englisch heute nur `now`, `help` |
| `src/services/trip_command_processor.py:222-235` | `_COMMAND_SPECS`: einzige Quelle des Befehlssatzes (#2134), mit `kinds` für den Ortsvergleich (#2282) |
| `src/services/trip_command_processor.py:287-323` | `_KURZHILFE_ENGLISCH` (wertlose Wortübersetzung, zweite Map = Anti-Pattern zu #2134) und `premium_sms_kurzhilfe()` |
| `src/services/trip_command_processor.py:390` | `_BRIEFING_HINWEIS` nutzt `today`/`tomorrow` als interne day_token. Das ist kein Befehlswort, aber Verwechslungsgefahr |
| `src/app/metric_catalog.py:29-97` | `MetricDefinition` hat keine englische Kürzel-Bedeutung, das Feld ist nötig |
| `src/output/renderers/sms_trip.py:792-842` | `SMS_SYMBOL_BY_METRIC` / `SMS_MULTI_SYMBOLS_BY_METRIC`: die TATSÄCHLICH gesendeten Kürzel. Sie weichen von `sms_code`/`col_label` ab. CODES muss hieraus ableiten |
| `src/output/channels/telegram.py:122-140` | `BOT_COMMANDS`: statisches Literal, `prod_selftest.py` liest es per `ast.literal_eval`. Es muss ein Literal bleiben |
| `src/output/renderers/email/plain.py:366`, `email/html.py:477` | E-Mail-Fußzeile leitet aus `_COMMAND_SPECS` ab. Muss deutsch bleiben |
| `src/services/inbound_sms_reader.py:90-121` | Code-Gestalt `XX…` vor dem Befehl. Neue Wörter kollidieren nicht (Präfix XX) |

## Existing Patterns
- Einzelquelle `_COMMAND_SPECS` → Hilfe, Fehlertexte, Telegram-Menü, E-Mail-Fußzeile (#2134). Englische Wirkungstexte gehören als Spalte hierher, nicht in eine zweite Map.
- E2E durch den echten Kanal-Eingang: `tests/tdd/_befehl_e2e_fixtures.py`, `test_befehle_{email,telegram,premium_sms}_e2e.py`, `test_befehlsangebot_vollstaendig.py`, `test_kommandoliste_einzelquelle.py` (#2417).
- Premium-SMS-Live-Dialog in Prod: manuell mit dem Handy des PO über den Verknüpfungscode (27.09. bestanden). Lesen mit `.claude/tools/seven_journal.py` (PR #2440).

## Dependencies
- Upstream: Metrik-Katalog, SMS-Renderer-Kürzel, Store (Trip/Vergleich), Kanal-Transporte.
- Downstream: Telegram `setMyCommands`/`getMyCommands`, `prod_selftest.py::_load_bot_commands`, E-Mail-Fußzeilen, alle Tests, die das `_COMMAND_SPECS`-Tupel strukturell entpacken (bei einer Spaltenerweiterung von 4 auf 5 oder 6 Felder brechen sie).

## Existing Specs
- `docs/specs/modules/feat_2417_befehle_e2e_echter_eingang.md`: AC-10/AC-11/AC-23 (Kurzhilfe) werden abgelöst bzw. verschärft.
- `docs/specs/modules/feat_2282_ortsvergleich_eingangskanaele.md`: `kinds` / Ablehnung beim Vergleich.

## Risks & Considerations
- Die Grenze von höchstens 3 Segmenten für HELP (GSM-7, 153 Zeichen je Segment) bei 12 Befehlen plus Wirkung plus CODES-Verweis vorab durchrechnen, die Wirkungstexte sehr knapp halten.
- Telegram-Slash-Namen erlauben nur `[a-z0-9_]`: `/restday`, deutsches CODES-Pendant z. B. `/kuerzel`.
- BOT_COMMANDS wächst von 17 auf etwa 26 Einträge (Limit 100). Selftest-Parser und Drift-Test mitziehen.
- Normale (Nicht-Premium-)SMS: Einen Eingangsweg prüfen, bevor eine AC dafür versprochen wird.
- LoC: 13 bis 16 Dateien, etwa +150 bis +250 produktiv. `loc_limit_override` 500 früh setzen und ACs nicht auf eine Scheibe verengen.
- Nebenbefund Etappennummer (E4 vs. „02“) ist ausgelagert nach #2441, nicht Teil dieser Spec.

## Analysis

### Type
Feature (mit Defekt-Anteil: die Kurzhilfe nennt teils falsche Kürzel)

### Kernbefund: Kürzel-Widersprüche IM Katalog (gemessen 27.09.)
Der Metrik-Katalog `src/app/metric_catalog.py` ist die einzige Quelle. Er trägt aber je Metrik drei Kürzel-Felder: `sms_code`, `col_label`, `sms_multi_symbols`, plus `SMS_SYMBOL_GRAMMAR`. Eingabe (Stundenverlauf-Abfrage, Kurzhilfe) nutzt `sms_code or col_label` (`trip_command_processor.py:322, 694, 2292`). Die Ausgabe der SMS nutzt `SMS_SYMBOL_BY_METRIC` / `SMS_MULTI_SYMBOLS_BY_METRIC` (`metric_catalog.py:792, 840`). Bei 24 von 29 Metriken stimmen beide überein. Die Widersprüche:
| Metrik | Eingabe (`sms_code or col_label`) | in der SMS gelesen | Folge |
|---|---|---|---|
| `temperature` | `D` | — (nur Stundenverlauf) | **`D` doppelt belegt:** in der SMS = Tageshöchstwert, als Befehl = Temperatur-Stundenverlauf |
| `temperature_day_high` | `DayMax` (kein `sms_code`) | `D` | gelesenes Kürzel ist nicht sendbar |
| `temperature_night` | `Night` (kein `sms_code`) | `N` | gelesenes Kürzel ist nicht sendbar |
| `fresh_snow` | `NS` | `NS24+` | Suffix, lösbar per Normalisierung |
| `wind_chill` | `TF` | — | nur Stundenverlauf, kein Widerspruch |
Dazu **Gefahren-Symbole** der Warn-SMS (`src/output/tokens/hazard_symbols.py:15`): `FL` = Flut (Metrik: gefühltes Tagestief), `CL` = Sperrung (Metrik: tiefe Wolken), `W`/`TH` doppelt. Diese Kürzel sind nur im Warn-Kontext eindeutig.
Ziel: **Ein Kürzel = eine Bedeutung, und was man liest, kann man senden.** Das Katalogfeld wird zur Einzelquelle. CODES, HILFE, die Eingabe-Erkennung und der SMS-Renderer leiten daraus ab. Für die drei Temperatur-Widersprüche muss der Katalog bereinigt werden, z. B. `temperature` bekommt ein eigenes Kürzel (etwa `T`) und `D`/`N` werden Eingabe-Kürzel von Tageshöchst- und Nachtwert.

### Affected Files (with changes)
| File | Change Type | Description |
|------|-------------|-------------|
| `src/services/trip_command_processor.py` | MODIFY | `_COMMAND_SPECS` → benannte Struktur (NamedTuple) mit `wort_en` + `wirkung_en`; `_KURZHILFE_ENGLISCH` streichen; englische Wörter in `_BARE_KEYWORD_MAP` (abgeleitet, keine dritte Liste); HELP-Kurzform aus der Wirkung; neuer Befehl CODES; Kanalsprache für Hilfe, Fehlertexte und Bestätigungen; Eingabe akzeptiert Ausgabe-Kürzel |
| `src/app/metric_catalog.py` | MODIFY | Kürzel-Widersprüche beheben (`D`/`N`/`T`), englische Kurzbedeutung je Ausgabe-Kürzel |
| `src/output/tokens/hazard_symbols.py` | MODIFY (nur lesend genutzt) | englische Bedeutung der Warn-Kürzel für CODES (Abschnitt „Alerts“) |
| `src/services/inbound_sms_reader.py` | MODIFY | `hilfe`/`codes` auf Premium-SMS → englische Kurzform |
| `src/services/inbound_telegram_reader.py` | MODIFY | Telegram-Kurzform (`telegram_style=kurzform` am aufgelösten Ziel) → englische Texte; neue englische Wörter erkennen |
| `src/output/channels/telegram.py` | MODIFY | `BOT_COMMANDS`-Literal um englische Slash-Befehle erweitern (`/today`, `/restday`, `/codes`, …); bleibt Literal wegen `prod_selftest.py` |
| `src/output/renderers/email/plain.py`, `email/html.py` | MODIFY (nur Feldzugriff) | Fußzeile liest weiter die deutsche Beschreibung |
| `.claude/hooks/prod_selftest.py` | MODIFY ggf. | Menü-Anzahl |
| `tests/tdd/test_befehlsangebot_vollstaendig.py`, `test_kommandoliste_einzelquelle.py`, `test_befehle_{email,telegram,premium_sms}_e2e.py`, `_befehl_e2e_fixtures.py` | MODIFY | Tupel-Entpacken, abgelöste ACs |
| `tests/tdd/test_kurzform_befehle_englisch.py`, `test_kuerzel_eindeutig.py` | CREATE | Wirkung je Befehl; CODES vollständig über die AUSGABE-Register (nicht über das Bedeutungs-Wörterbuch); Kürzel-Disjunktheit; Eingabe akzeptiert jedes Ausgabe-Kürzel |
| `docs/specs/modules/feat_2417_befehle_e2e_echter_eingang.md` | MODIFY | AC-10/AC-11/AC-23 ausdrücklich als abgelöst vermerken |

### Scope Assessment
- Dateien: ~14 bis 17
- Geschätzte LoC: produktiv +250 bis +400 / -60; Tests +250 bis +350. **`loc_limit_override 500` ist gesetzt.**
- Risk Level: **MEDIUM**. Betrifft den zentralen Befehlssatz aller vier Kanäle und die Kürzel des Katalogs, die auch im SMS-Renderer wirken. Deshalb sind der Renderer-Commit-Gate und der Mail-Validator zu beachten, falls `sms_code` von `temperature` sich ändert.

### Gemessenes Längenbudget (GSM-7, `sms_segments()` aus `_befehl_e2e_fixtures.py`)
- HELP-Entwurf (12 Befehle mit Wirkung + CODES-Verweis + „German words work too“): 337 Zeichen = **3 Segmente**
- CODES-Entwurf (alle Ausgabe-Kürzel + feste Zeichen `E4`, `@`, `(…)`, `-`, `+HL`): 396 Zeichen = **3 Segmente**
- CODES + Abschnitt „Alerts“ (10 Warn-Kürzel): 496 Zeichen = **4 Segmente**
- Entwurfstexte: Scratchpad `messen.py`. In der Spec gilt: HELP höchstens 3 Segmente, CODES höchstens 4 Segmente.

### Technical Approach
1. `_COMMAND_SPECS` wird ein NamedTuple mit `wort`, `wort_en`, `arg`, `beschreibung_de`, `wirkung_en`, `kinds`. Alle Leser greifen per Feldname zu. Die Erkennung von Deutsch und Englisch wird aus `wort` und `wort_en` abgeleitet.
2. Sprache der Antwort: Premium-SMS ist immer englisch. Telegram ist englisch, wenn das aufgelöste Ziel `telegram_style == "kurzform"` hat: Trip `report_config.telegram_style` (`trip_alert.py:314`), Vergleich `display_config.telegram_style` (`compare_alert_channels.py:56`). Sonst deutsch. E-Mail ist immer deutsch. `_KURZFORM_KANAELE` wird NICHT um `telegram` erweitert, sonst Seiteneffekt auf den Drilldown (`trip_command_processor.py:1423, 1476`).
3. Sprachumfang: Nicht nur HELP, sondern **jede** Antwort, die auf einem Kurzform-Kanal ankommt, wird englisch. Das betrifft den Fehlertext bei unbekanntem Befehl (`unknown_command_body`/`command_overview`), die Ortsvergleich-Ablehnung (`_compare_unavailable`) und die Bestätigungen von PAUSE, SKIP, STOP, WEITER, RUHETAG sowie den STATUS-Kopf. Sonst wirbt die Fehlermeldung weiter mit deutschen Befehlen. Die vollständige Liste der erreichbaren Texte legt die Spec an (114 `confirmation_*`-Stellen im Prozessor, nicht alle kurzform-erreichbar).
4. CODES wird aus den Ausgabe-Registern plus den festen Zeichen plus den Warn-Kürzeln abgeleitet. Die Bedeutung steht beim Kürzel. Ein Kürzel ohne Bedeutung lässt einen Test rot werden.
5. Telegram-Menü (`BOT_COMMANDS`): Ein Menü gilt für den ganzen Bot und kann dem Stil pro Trip nicht folgen. Die Spec legt fest, dass das Menü die deutschen und die englischen Slash-Befehle enthält.
6. Premium-SMS-Code-Trennung: Der Verknüpfungs-Code hat die Gestalt `^XX[A-HJKMNP-Z]{3}[2-9]{3}$` (`inbound_sms_reader.py:90`). Kein neues Wort kollidiert damit. Trotzdem ist eine AC nötig: `<Code> tomorrow` und `<Code> restday 2` laufen durch den echten Eingang.

### Dependencies
- Upstream: Metrik-Katalog (Kürzel), `hazard_symbols.py`, Trip-/Vergleich-Store (`telegram_style`).
- Downstream: SMS-Renderer (liest `SMS_SYMBOL_BY_METRIC`), Telegram `setMyCommands`, `prod_selftest.py::_load_bot_commands`, E-Mail-Fußzeilen, `/api/sms-symbols`.

### Open Questions
- [x] Was ist „Telegram-Kurzform“? → Stil `kurzform` am aufgelösten Trip bzw. Vergleich, schon vorhanden. Keine PO-Frage.
- [x] Gehören die Warn-Kürzel in CODES? → Ja, als eigener Abschnitt „Alerts“, 4 Segmente gemessen. Jeder Kanal muss jede Frage beantworten.
- [ ] Neues Kürzel für `temperature` (Stundenverlauf Temperatur), damit `D` eindeutig Tageshöchstwert heißt. Vorschlag `T`. Das wird in der Spec als AC zur Freigabe vorgelegt.
- [x] Mehrdeutigkeit von `FL`/`CL`/`W`/`TH`: **überholt durch PO-Vorgabe 27.09.** („keine Dopplung von Kürzeln", dauerhafter Wächter). Die Warn-Kürzel werden umbenannt (Spec AC-25–AC-27), Bedeutungen der Wettermetriken nur im Katalog (AC-23/AC-24). Die Spec ist freigegeben (27.09.2026).

## Hinweis für /40-tdd-red (Arbeitsstand bei Freigabe)
- Dieser Worktree steht auf Branch `tools/seven-journal-reader` (PR #2440, Lese-Werkzeug, noch OPEN). Die Feature-Arbeit gehört NICHT auf diesen Branch: vor dem ersten Test einen eigenen Branch ab `origin/main` anlegen (z. B. `feat/2417-kurzform-englisch`) und Spec, Kontext und Briefing (derzeit untracked) mitnehmen.
- Verbindlicher HELP-/CODES-Wortlaut steht in der Spec. Das Messskript mit `sms_segments()` liegt nur im Sitzungs-Scratchpad und kann aus der Spec nachgebaut werden (HELP 402 Zeichen/3 Segmente, CODES 758/5).

## Für /50-implement: bestehende Tests mit alten Kürzeln (Stand RED)

Ermittelt per grep am 27.09.2026 (Agent B, /40-tdd-red). Diese Dateien erwarten die alten Warn-/Météo-France-Kürzel oder `temperature` → `D` und müssen in GREEN mitgezogen werden (erwarteter Wechsel: `TH`→`TS`, `FL`→`FO`, `HR`→`RA`, `W`→`WG`, `CL`→`AB` für Warnungen; `HR:`/`TH:` → `VR:`/`VT:` für Météo-France; `temperature.sms_code` `D`→`T`).

**Produktivcode mit den alten Kürzeln:** `src/output/tokens/hazard_symbols.py`, `src/output/tokens/builder.py` (`VIGI_TH`/`VIGI_HR`, `PRIORITY`, `POSITIONAL`), `src/output/renderers/alert/official_alerts.py` (`_HAZARD_DISPLAY`), `src/app/metric_catalog.py` (`temperature.sms_code`, `COMPACT_LABEL_EXCEPTIONS["temperature"]`), Doku `docs/reference/sms_format.md`.

**Tests, die `HAZARD_SMS_SYMBOLS`/`VIGI_HR`/`VIGI_TH` nennen:**
- `tests/tdd/test_hazard_symbols.py`
- `tests/tdd/test_sms_official_alert_tokens.py`
- `tests/tdd/test_official_alert_sms_ortskopf.py`
- `tests/tdd/test_alert_preview_official_render.py`
- `tests/tdd/test_issue_917_alert_renderer.py`
- `tests/tdd/test_compare_sms_gsm7_charset.py`
- `tests/tdd/test_trip_sms_gsm7_charset.py`
- `tests/tdd/test_sms_snow_symbols.py`
- `tests/unit/test_metrik_listen_register_ratchet.py`
- `tests/unit/test_sms_symbol_grammar_classes.py`
- `tests/helpers/metrik_listen_scan.py`
- `frontend/src/lib/components/shared/__tests__/officialAlertLegend.test.ts`

**Tests mit alten Warn-Token-Literalen (`!TH:`, `FL:`, `HR:`, `W:`, `CL`):**
- `tests/golden/test_subject_golden.py`, `tests/unit/test_subject_filter.py`
- `tests/tdd/test_alert_channel_threshold.py`, `tests/tdd/test_compare_alert_channel_threshold.py`
- `tests/tdd/test_compare_local_time_basis.py`, `tests/tdd/test_compare_sms_official_alerts.py`, `tests/tdd/test_compare_telegram_official_alerts.py`
- `tests/tdd/test_official_alert_channel_scope.py`, `tests/tdd/test_official_alert_sms_marker.py`
- `tests/tdd/test_sms_user_metric_order.py`

**Tests/Fixtures mit dem Météo-France-Baustein `HR:` (bzw. `TH:` als Vigilance):**
- `tests/golden/test_sms_golden.py` + `tests/golden/sms/corsica-vigilance.txt`, `gr20-summer-evening.txt`, `gr20-spring-morning.txt`
- `tests/unit/test_token_builder.py`, `tests/tdd/test_sms_letter_value_separator.py`, `tests/tdd/test_briefing_mail_inhalt.py`
- `frontend/src/lib/components/shared/__tests__/weather_metric_kuerzel_marken.test.ts`

**Tests, die `temperature` → `D` festschreiben:**
- `tests/tdd/test_issue_917_alert_renderer.py:493` (`get_sms_code("temperature")`)
- `tests/tdd/test_adhoc_kurzform_verlauf.py:83` (Kommentar/Erwartung `sms_code "D"`)
- `tests/tdd/test_compare_outlook_metric_selection.py:52` (Kommentar „bisher D" — prüfen)
- `tests/unit/test_telegram_kuerzel_folgt_register.py` (in RED bereits umgestellt: Ausnahme `temperature` entfällt)
- `frontend/src/lib/components/shared/__tests__/metricKuerzelLegende.test.ts` (in RED umgestellt, siehe Befund unten)

**Befunde aus RED, die GREEN blockieren (Spec-Klärung nötig, Details im Agent-B-Report):**
1. `builder.POSITIONAL` erzeugt `MAX` (Brandzonen „max"), der freigegebene CODES-Wortlaut erklärt `MAX` nicht → `test_codes_vollstaendig_gegen_ausgabe_register` und der zeichengenaue Wortlaut-Test können nicht beide grün werden.
2. `N` gehört zu zwei Metriken: `temperature_cold.sms_code="N"` und `temperature_night.sms_multi_symbols=("N",)` → AC-25 Punkt 2 bleibt rot, die Spec sieht dafür keine Ausnahme vor.
3. AC-22 „Ortsvergleich zeigt T statt D": die Vergleichs-SMS liest für `temp_max`/`temp_min` über `kuerzel_metric_id` die Größen `temperature_day_high`/`temperature_day_low` (D/L), nicht `temperature` — die Stelle ist nicht beobachtbar.
4. Frontend-Legende: die beiden `D`-Zeilen sind `temp_max_c` und `temp_min_c` (beide `metric_id="temperature"`, `sms_code` aus `temperature`), nicht `temperature`/`temperature_day_high`. Nach AC-12 würden beide `T` → „D einmal, T einmal" ist mit der heutigen Vergleichs-Katalogableitung nicht erreichbar.

→ **Aufgelöst in Spec v1.1 (27.09.2026):** 1 = `MAX` in CODES aufgenommen; 2 = AC-28 (Kälte-Alarm `T`); 3 = AC-22 korrigiert; 4 = AC-29 (Vergleichsauswahl folgt `kuerzel_metric_id`, Legende „D einmal, L einmal").

## Für /50-implement: Hinweise aus RED (Agent A, Befehle & Sprache)

1. **Sprachentscheidung — vier Telegram-Pfade:** unbekannter Befehl vor Zielauflösung (`_send_unknown_command`: deutsch + „English: send HELP"); ziellos (`ZIELLOS_SCHLUESSEL`: Sprache folgt Wort); `ziel.kind is None` (`ziel.text` wird ohne `process()` gesendet: Sprache folgt Wort, gleich lautende Wörter englisch); Ziel aufgelöst (Sprache folgt `telegram_style`).
2. **Premium-SMS-Mehrdeutigkeit** geht an `process()` vorbei (`send_command_reply_premium_sms(hinweis)` in `inbound_sms_reader.py`) — Übersetzung nur im Prozessor reicht nicht. `inbound_sms_reader.py` importiert `premium_sms_kurzhilfe` lokal für `hilfe`.
3. `ZIELLOS_SCHLUESSEL` (`trip_selection.py`) um `codes`/`kuerzel` ergänzen.
4. **`FEHLERTEXTE`** in `tests/tdd/_befehl_e2e_fixtures.py` ist nur deutsch — englische Fehlertexte (unbekannter Befehl, Mehrdeutigkeit, kein Ziel) dort ergänzen, sonst prüfen die Fehlertext-Checks auf Premium-SMS-Pfaden nichts mehr.
5. **Übergangs-Shim `spec_feld()`** in `_befehl_e2e_fixtures.py` (Zweig für das alte Tupel-Layout) nach GREEN löschen.
6. **4-Tupel-Leser außerhalb der RED-Dateien:** `tests/tdd/test_befehle_email_live.py:325`, `tests/tdd/test_issue_686_telegram_functional_live.py:424,496`; prüfen: `tests/tdd/test_issue_882_pause_skip.py`, `tests/helpers/adhoc_metrik_fixtures.py::wort_von`. Produktiv-Leser auf Feldnamen umstellen: `command_rows`, `command_overview`, `_show_help_for_kind`, E-Mail-Fußzeilen `email/plain.py`, `email/html.py`.
7. **Menüzahl** in `prod_selftest.py` und `test_issue_685_selftest_menu_gate.py` mitziehen (BOT_COMMANDS wächst).
8. **`api/routers/config.py:70,88`** liest `HAZARD_SMS_SYMBOLS` (`/api/sms-symbols`) — Umbenennung der Warn-Kürzel wirkt dort mit.
9. Premium-SMS-Matrixzweig `ERGEBNIS_ANTWORT_VERGLEICH` (L4, „pause 2d") erwartet den Vergleichsnamen in der englischen Antwort.
10. AC-3 per E-Mail ist nicht unterscheidend (Betreff nennt immer den Trip).
11. **Frontend-`node_modules`** im Worktree ist ein Symlink auf den Hauptcheckout — kein `npm install`/`npm ci` hier; entfernen nur mit `rm frontend/node_modules` (ohne `/`, ohne `-rf`).
12. **Premium-SMS im Test:** pro Test genau ein Recorder (Journal-IDs starten sonst neu bei 1).
