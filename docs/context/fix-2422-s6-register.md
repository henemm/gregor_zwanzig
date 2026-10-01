# Context: fix-2422-s6-register (#2422 S6 — Ausnahme-Register leeren)

## Request Summary
S1 (#2422) hat vier Produktabweichungen „Einstellung ≠ Auslieferung" befristet im Ausnahme-Register
`tests/helpers/einstellung_auslieferung_orakel.py::AUSNAHMEN` (Z. 100–226) geparkt. S6 behebt sie im
Produkt und entfernt die Einträge: B1, B2, B3 (= eigenes Issue #2429), B5. Der `gust`-Eintrag
(Telegram-7er-Limit, #360, `befristet=False`) bleibt. PO-Entscheid 30.09.: **B1 Variante V1**
(`wind_chill` erscheint in SMS/Premium-SMS/Telegram-Kurzform mit eigenem Kürzel, kein Editor-Hinweis).

## Related Files
| File | Relevanz |
|------|----------|
| `src/app/metric_catalog.py` | Z. 238–261 `wind_chill` (compact_label/sms_code `TF`, col_label `Feels`); Kinder FN/FL/FD Z. 275/299/311; `_SMS_SYMBOL_METRIC_IDS` Z. 802–814; `SMS_SYMBOL_GRAMMAR` Z. 833; `SMS_SYMBOL_BY_METRIC` Z. 840; Kommentar „WC entfällt ersatzlos" Z. 868–874; `SMS_MULTI_SYMBOLS_BY_METRIC` Z. 888; `COMPACT_LABEL_EXCEPTIONS` Z. 899; `_kurzform_kuerzel` Z. 909; friendly_label-Metriken (wind_direction 403, thunder 480, cape 500, cloud_* 563–614, sunshine 656) |
| `src/app/loader.py` | Z. 864–871 `_DERIVED_METRIC_RULES` (Kinder aus Eltern-`enabled`); `_resolve_format_mode` |
| `src/output/renderers/trip_report.py` | Z. 134–142 E-Mail-Kollabierung + **B3-Ursache** `self._friendly_keys = build_friendly_keys(dc)`; Z. 274–301 `_dc_telegram` + `render_telegram_bubbles(friendly_keys=self._friendly_keys)`; Z. 348–466 SMS-Spec-Bau (nur symbol/enabled/position, **kein format_mode** → B2); Z. 582–588, 976–984 wind-dir-Merge |
| `src/output/renderers/sms_trip.py` | Z. 32 `fold_ascii`; Z. 69–91 `build_extended_metric_specs` (kein format_mode); Z. 528/712 `max_length=160` |
| `src/output/tokens/dto.py` | Z. 102–120 `MetricSpec` — **hat** `format_mode`/`use_friendly_format`/`friendly_label` |
| `src/output/tokens/builder.py` | Z. 170–181 `_spec_uses_friendly_token`, `_mk_metric` Z. 202/229 (friendly = festes Label, kein Wert→Kategorie-Formatierer); Temperatur-Token Z. 352–387 (N/L/D/FN/FL/FD); Paar-Zusammenfassung Z. 406–412 |
| `src/output/tokens/metrics.py`, `tokens/render.py` | Wert-Kodierung (ganze Grad), Kürzungsreihenfolge Z. 90/101 |
| `src/output/renderers/email/helpers.py` | Z. 59–69 `_effective_format_mode`; Z. 72–90 `should_merge_wind_dir`; Z. 115–227 Zeilenbau überspringt wind_direction; Z. 262–308 `visible_cols` (E-Mail: keine Geisterspalte); Z. 1226–1247 `build_friendly_keys`/`build_format_modes` |
| `src/output/renderers/channel_layout.py` | Z. 25–55 GSM7-Budget + `CHANNEL_LIMITS`; Z. 112–145 `render_for_channel` → `table_columns` **ohne Merge-Filter** (B5-Ursache) |
| `src/output/renderers/narrow.py` | Z. 76 `_compact_label`; Z. 83–88 `_cell`; Z. 124 Kopf; Z. 698/866 `_narrow_table` |
| `src/output/renderers/email/compare_html.py:966`, `comparison.py:274` | Vorbild: Ortsvergleich filtert die wind_direction-Spalte bereits (`_should_merge_wind_dir`) |
| `src/services/notification_service.py` | Z. 651–686 Premium-SMS + Telegram-Kurzform nutzen denselben `sms_text` |
| `src/services/trip_command_processor.py` | Z. 355–420 `_CODES_WETTER`/`codes_text()` — entfernt `TF` im Trip-Kontext aktiv |
| `api/routers/config.py:60–90` | `/api/sms-symbols` (Frontend `kuerzelMarken.ts` liest nur hier, keine TS-/Go-Kopie) |
| `tests/helpers/einstellung_auslieferung_orakel.py` | Register, `erwartete_kaskade()` Z. 352, `parse_sms_artig` Z. 573, `_SMS_SYMBOL_TO_METRIC` Z. 295 (FL/FD → Kinder-Ids, nicht wind_chill), `abweichungen_fuer_golden` Z. 710 |
| `tests/tdd/test_einstellung_gleich_auslieferung.py` | Invarianten-Test S1 (AC-2/AC-4 hängen explizit an B1-Einträgen, Z. 135–200) |
| `tests/fixtures/einstellung_auslieferung/` | golden_a–d + eingefrorene Erwartungen (Drift-Test aus S2a) |

## Tests, die das heutige Verhalten festschreiben (bei V1 mitzuziehen)
- `tests/unit/test_sms_token_symbol_register_ratchet.py` Z. 469/490/514 (Kollision), 555–573 `_AC9_ERWARTUNG`, 622 `"wind_chill" not in SMS_MULTI_SYMBOLS_BY_METRIC`, 695–712 `test_sms_symbols_endpoint_fuehrt_wind_chill_nicht_mehr`
- `tests/tdd/test_kuerzel_eindeutig.py:82–95` (kein TF im Trip, #2454 AC-6)
- `tests/unit/test_telegram_kuerzel_folgt_register.py:290–320`, `tests/unit/test_keine_doppelten_kennungen.py:282–404`, `tests/unit/test_sms_symbol_grammar_classes.py`, `tests/tdd/test_sms_snow_symbols.py`, `tests/tdd/test_trip_sms_gsm7_charset.py`
- `tests/red/test_issue_435_format_modes.py` (kein Telegram-Fall — B3-Testlücke laut #2429)

## Existing Patterns
- Kürzel-Register ist Single Source in `metric_catalog.py`; Frontend und Go spiegeln nur über `/api/sms-symbols`.
- Kürzel-Entscheidungen haben eigene Specs: `fix_1887_e6a_sms_kuerzel_register.md` (WC entfällt, TF bleibt sms_code), `fix_1926_metrik_kuerzel_englisch.md`, `fix_2232_kuerzel_ein_modell_trip_vergleich.md` (FD/FL statt TF+/TF-).
- Roh/Einfach wird per `_effective_format_mode` → `build_friendly_keys` pro Layout aufgelöst (E-Mail); für Telegram existiert `_dc_telegram` bereits, wird nur nicht für friendly_keys genutzt.
- wind_direction-Merge: E-Mail filtert implizit über Zeilen-Keys, Ortsvergleich explizit (`_should_merge_wind_dir`); Telegram-Trip fehlt der Filter.

## Dependencies
- Upstream: Trip-JSON → `loader` (Kaskade, format_mode, abgeleitete Metriken) → `DisplayConfig.get_metrics_for_channel(kanal)`.
- Downstream: E-Mail HTML/Plain, Telegram rich/Kurzform, SMS, Premium-SMS; Befehls-Antwort `KÜRZEL/CODES`; Editor-Kürzelmarken über `/api/sms-symbols`; Ortsvergleich teilt Katalog + Token-Builder.

## Offene Fragen für /20-analyse
1. **B1 — was fehlt wirklich?** `wind_chill` hat Kinder mit Kürzeln FL/FD/FN; das Orakel mappt FL/FD auf die Kinder-Ids, nicht auf `wind_chill`. Klären: Erscheinen FL/FD in der Golden-SMS tatsächlich (dann ist B1 teils Orakel-Mapping), oder fehlen sie (Ableitung Eltern→Kinder greift im SMS-Layout nicht)? PO-Screenshot im Issue zeigt Konfiguration vs. ausgelieferte Kurzform (KHW 403). V1 kann heißen „Kinder-Token FL/FD erscheinen, wenn Gefühlte Temp. aktiv" statt eines neuen Buchstabenkürzels — Wiederbelebung von `TF`/`WC` kollidiert mit #1887/#2232/#2454-Entscheidungen.
2. **B2 — Einfach-Darstellung in GSM-7:** Katalog-`friendly_label`s sind Emojis (☀️⛅☁️, ⚡, 🟢🟡🔴) und nicht SMS-tauglich. Braucht es eine ASCII-Einfachform (Orakel erkennt `[LMH]`) je Metrik, und für welche Metriken ist „Einfach" in SMS überhaupt sinnvoll? Evtl. PO-Produktfrage (Form), aber nicht technisch.
3. **B3:** Fix ist lokal (`build_friendly_keys(_dc_telegram)`); #2429 mitschließen. Testlücke laut #2429 zu schließen.
4. **B5:** Merge-Filter für Telegram-`table_columns` analog Ortsvergleich; geteilte Helper statt dritter Kopie.
5. Scope/LoC: vier Fixes + Test-Mitzug evtl. > 250 LoC → Scheibenschnitt prüfen (B3+B5 klein, B1 mittel, B2 größer).

## Risks & Considerations
- Kürzel-Wiedereinführung kollidiert mit dokumentierten Entscheidungen (#1887 E6a, #2232, #2454) → ggf. ADR-/Spec-Abgleich; `KÜRZEL`-Befehlsantwort und Editor-Marken müssen mitziehen.
- SMS 160-Zeichen-Budget + Kürzungsreihenfolge: zusätzliche Token verdrängen andere.
- GSM-7-Wächter: keine Emojis in SMS.
- Ortsvergleich teilt Katalog/Builder — Änderungen am Register wirken dort mit (TF wird im Vergleich gesendet).
- Eingefrorene Golden-Erwartungen (S2a-Drift-Test) ändern sich → bewusst neu einfrieren, nicht stillschweigend.
- Renderer-Commit-Gate: Mail-Inhalts-Dateien (helpers.py) → Modus-Matrix + `briefing_mail_validator.py` frisch grün.
- Parallel-Session #2155 S4 (admin-ui) — keine Überschneidung erwartet.

## Analysis

### Type
Bug (vier Produktabweichungen „Einstellung ≠ Auslieferung", befristet geparkt im Register aus S1). Schließt #2429 (B3) mit.

### Befunde je Eintrag (gemessen / belegt, 30.09.)

**B1: `wind_chill` fehlt in SMS / Premium-SMS / Telegram-Kurzform (PO-Entscheid V1: eigenes Kürzel)**
- Gerenderte Golden-SMS (golden_a Kurzform = golden_b sms = premium_sms): `E1: W20@4 R2.0@4 PR60%@4 G45@4 TH:M@4 TH+:- CT70@4 SU16`. Kein TF/FL/FD/FN.
- Goldens a/b haben die drei Kinder `wind_chill_night/_day_low/_day_high` auf allen Ebenen **explizit `enabled:false`**. Explizites false schlägt die Ableitung (`loader.py:~890` `continue`, Regeln `loader.py:864–871`). Die Kinder sind selbst **wählbare** Metriken (FL/FD/FN). Der Nutzer hat also bewusst „Gefühlte Temperatur" gewählt, nicht die Gehzeit-Tagesauswertungen.
- Es ist eine Produktlücke, kein Orakel-Fehler: `builder.py:352–412` hat nur N/L/D/FN/FL/FD-Token, für den Elternteil `wind_chill` entsteht nie ein Token. `_SMS_SYMBOL_TO_METRIC` (Orakel `:295–300`) ist konsistent zum Register.
- Kürzel-Wahl: **`TF`** (bestehender `wind_chill.sms_code`, `metric_catalog.py:~261`). Begründung: Der ADR-0011-Nachtrag #2232 (`docs/adr/0011-…md:136`) definiert `TF` als **eigenständige Größe „Stundenwert"** (Alarm-SMS/Telegram), nicht als Tagesauswertung. Damit doppelt es FL/FD nicht (#1887 E6a: nur `WC` entfiel ersatzlos, weil es FK doppelte). Ein neues Kürzel wäre eine zweite Kennung für dieselbe Größe (verstößt gegen „ein Kürzel = eine Größe", #2232). Trip-Token-Form: Stunden-Extrem mit Uhrzeit analog `W20@4`, Richtung Kälte (min). Die exakte Form legt die Spec fest (Budget 160 Zeichen).
- Was damit abgelöst wird (die Spec muss es benennen, **ADR-0011-Nachtrag** schreiben): #2454 AC-6/AC-7 „TF entfällt im Trip-Kontext" (`tests/tdd/test_kuerzel_eindeutig.py:78–95`, `trip_command_processor.py:~355–420` `bed.pop("TF")` in `codes_text(vergleich=False)`) und der ADR-0011-Nachtrag-E7-Satz „Trip-SMS sendet FK/FD/WC".
- Zu ziehende Tests (sie pinnen „wind_chill hat kein Trip-Kurzform-Kürzel"):
  - `tests/unit/test_sms_token_symbol_register_ratchet.py:469/490/514/555–573/622/695–712`
  - `tests/tdd/test_channel_metric_matrix.py:901/990/1056`
  - `tests/tdd/test_sms_snow_symbols.py:673`
  - `tests/tdd/test_sms_temperature_range_token.py:368`
  - `tests/tdd/test_kuerzel_eindeutig.py:82–95`
  - `tests/unit/test_telegram_kuerzel_folgt_register.py:290–320` (`COMPACT_LABEL_EXCEPTIONS["wind_chill"]`, `metric_catalog.py:~880–899`)
  - `tests/unit/test_keine_doppelten_kennungen.py:282–404`
  - `tests/unit/test_sms_symbol_grammar_classes.py`, `tests/unit/test_kurzform_kuerzel_rangfolge.py`, `tests/unit/test_metric_catalog.py`, `tests/helpers/metrik_listen_scan.py`
  - Nicht gelesen, aber exponiert: `tests/tdd/test_sms_wind_chill_position_inherits_from_anchor.py`, `tests/tdd/test_ac6_sms_byte_identity_without_wc.py`
  - Das Orakel-`_SMS_SYMBOL_TO_METRIC` leitet aus dem Register ab und zieht automatisch mit.
- Ortsvergleich: Die Vergleichs-SMS sendet `TF` heute schon (`comparison.py:~647`, Quelle `kurzform_kuerzel`). Die Register-Änderung darf dort nichts verschieben; Wächter ist `tests/tdd/test_compare_sms_kuerzel.py`.

**B2: SMS / Premium-SMS / Telegram-Kurzform ignorieren Roh/Einfach**
- Ein Fix deckt alle drei ab: Premium-SMS und Kurzform nutzen denselben `report.sms_text` (`notification_service.py:~658–668`, `~677–683`).
- Die Kaskade liefert `format_mode` schon (`_dc_uncollapsed.get_metrics_for_channel("sms", report_type)`, `trip_report.py:~348`). Die `MetricSpec`-Builds (`trip_report.py:~391`, `~426`, `sms_trip.py:69–91 build_extended_metric_specs`) reichen es aber nicht durch. Aufgelöst wird pro Metrik über `_effective_format_mode(mc)` (`email/helpers.py:59–69`). **Nicht** `use_friendly_format` roh setzen.
- Der heutige Einfach-Zweig `_spec_uses_friendly_token`/`_mk_metric` (`builder.py:170–203`) würde das **Emoji-`friendly_label`** ausgeben. Das ist nicht GSM-7 und sprengt 160 Zeichen. Nötig ist ein **GSM-7-Einfach-Zweig**.
- Ist-Stand je Metrik:
  - TH: immer Stufe L/M/H (`builder.py:420/512`, `tokens/metrics.py:14 LEVELS`, `render_threshold_peak_value(is_level=True)` `:30–66`)
  - WD: immer Sektortext
  - CT/CL/CM/CH/CP/SU: immer numerisch (`builder.py:451`, `~487`)
- Die Einfach-Form muss **dieselbe Klassifikation wie die E-Mail** tragen (Kanal-Gleichheit, Epic #2133), nur in ASCII:
  - Wolken: 5-Stufen-Skala aus `metric_format.cloud_emoji` (`metric_format.py:260`, ≤10/≤30/≤70/≤90/>90)
  - Gewitter: `thunder_ampel_band`
  - CAPE/Sonne: die E-Mail-Bänder
  - Die konkreten ASCII-Zeichen sind eine Formfrage. Sie kommen **als AC-Vorschlag in die Spec, der PO gibt sie mit den ACs frei** (keine Vorab-Frage).
- Orakel (`parse_sms_artig` `:573–590`): `-`/`?` bleibt ungeprüft. `[LMH]`-artiger oder sonstiger Nicht-Zahl-Text zählt als „friendly", eine Zahl als „raw". Geprüft wird nur bei Metriken mit Roh/Einfach-Dimension (`:309`, `:749`).
- Goldens:
  - a/b/d: SMS-Layout thunder/cloud_total/cloud_low/wind_direction/sunshine = friendly (d: thunder `symbol`)
  - c: ohne SMS-Layout, globale Liste
  - `nach_aenderung_fall3_roh_einfach_umschalten*.json` (Fall 3 Umschalten): Der Spec-Writer prüft, ob dort eine SMS-Metrik auf **raw** geht. Wenn ja, sind die Roh-Zweige WD°/SU/TH in Scope.
- **Nutzersichtbar für Bestandsnutzer:** Der Katalog-Default ist `symbol` (= einfach). Fast alle SMS-Nutzer sehen Wolken künftig als Stufe statt `CT70@4`. Das muss eine eigene AC sein (bewusste PO-Freigabe).
- Mitziehen: `validator_render_service.build_sms_fidelity_specs` (`:500–512`) baut ebenfalls `MetricSpec`, sonst weicht die Vorschau ab. GSM-7-Wächter: `tests/tdd/test_trip_sms_gsm7_charset.py:133–189`.
- Paritäts-Nebenbefund: Die Ortsvergleich-SMS kennt `format_mode` ebenfalls nicht (`comparison.py:608–643`). Das kommt in den Spec-Scope-Abschnitt „nicht in S6" und als Eintrag in #1199.

**B3: Telegram rich erbt Roh/Einfach aus der E-Mail (#2429)**
- Ursache: `trip_report.py:155` `self._friendly_keys = build_friendly_keys(dc)` nach der E-Mail-Kollabierung (`~:148`). Verbraucht in `:314` `render_telegram_bubbles(..., friendly_keys=self._friendly_keys)`; `dc=_dc_telegram` steht in `:309`, definiert `~:297`.
- Fix: `friendly_keys=build_friendly_keys(_dc_telegram)` in `:314`. Weitere Nutzer von `_friendly_keys`: nur `render_email` (`:245`, korrekt). Der Narrow-Pfad (`narrow.py:697`, `_cell` 83–88, `_narrow_table` 867, Kurzübersicht 513/514) hängt an derselben Quelle und wird mitgeheilt.
- Ortsvergleich-Telegram ist nicht betroffen (`comparison.py:~700–760` ohne friendly_keys).
- Der Test `test_ac9_m3_…` (`test_einstellung_gleich_auslieferung.py:~519`) bleibt gültig, nur die Docstring-Prämisse anpassen. Neuer Test: E-Mail roh plus Telegram einfach, und umgekehrt.

**B5: Geisterspalte `WD` in Telegram rich**
- Der Merge läuft schon (`dp_to_row` `email/helpers.py:112–134` + `fmt_val` `:850–851` ergibt „20 W"). Nur die Layout-Spalte wird nicht gefiltert: `channel_layout.py:112–145 render_for_channel`.
- Fix-Ort: direkt nach dem `VISIBILITY_GATE_IDS`-Filter (`~:125`), vor `primary = sorted(...)`. Das trifft `table_columns` und `demoted_count`. Genutzt wird der geteilte Helfer `should_merge_wind_dir` (`email/helpers.py:72–90`) per **Lazy-Import** (Importzyklus) auf `dataclasses.replace(dc, metrics=enabled)`. Die Ortsvergleich-Helfer (`compare_html.py:966`, `comparison.py:274`) haben ein anderes Vokabular und sind nicht wiederverwendbar. Ortsvergleich-Telegram bleibt unberührt (`compare_metric_ids.py:44`, `compare_hourly_metric_ids.py:101`).
- **Folge für die `gust`-Strukturausnahme:**
  - golden_b Telegram-Slotfolge: precipitation, wind, rain_probability, thunder, cloud_total, cloud_low, wind_direction(7), gust(8).
  - Ohne WD rückt gust auf Slot 7. Der `gust`-Eintrag (befristet=False) wird unbenutzt, dann wird `test_ac6_ac7_…unbenutzten_eintraege` (`:~312`) rot. Den Eintrag zu löschen bricht den Vakuum-Schutz in `test_ac5_…` (`:~222`).
  - **Lösung:** Eintrag NICHT löschen, Guard NICHT lockern. Das golden_b-Telegram-Layout bekommt eine weitere aktive Metrik, damit das 7er-Limit wieder real eine Metrik verdrängt. Kommentar `test_einstellung_gleich_auslieferung.py:~743–748` anpassen.
- Nutzersichtbar: Telegram-rich-Nutzer mit WD im Skalenmodus sehen eine Metrik mehr (die bisher verdrängte).
- Zu prüfen:
  - `tests/tdd/test_issue_1001_telegram_bubbles.py` (Z.141/171/202/303/655)
  - `test_issue_360_channel_renderer.py`, `test_issue_429_channel_layouts.py`, `test_telegram_metric_notice.py`, `test_channel_metric_matrix.py`, `test_trip_renderer_characterization.py`

### Affected Files (with changes)
| File | Change Type | Description |
|------|-------------|-------------|
| `src/output/renderers/trip_report.py` | MODIFY | B3 (:314); B2 format_mode je SMS-Metrik in die Spec-Builds; B1 wind_chill-Spec |
| `src/output/renderers/sms_trip.py` | MODIFY | B2 `build_extended_metric_specs(format_by_metric=None)` |
| `src/output/tokens/builder.py` | MODIFY | B2 GSM-7-Einfach-Zweig statt Emoji-Label; B1 TF-Token |
| `src/output/tokens/metrics.py` | MODIFY | B2 Stufen-Abbildung (Wolken/CAPE/Sonne) aus den E-Mail-Bändern |
| `src/output/renderers/channel_layout.py` | MODIFY | B5 wind_direction-Merge-Filter |
| `src/app/metric_catalog.py` | MODIFY | B1 wind_chill als Trip-Kurzform-Symbol (Register, `COMPACT_LABEL_EXCEPTIONS`, Kommentar ~868) |
| `src/services/trip_command_processor.py` | MODIFY | B1 `TF` im Trip-KÜRZEL-Text nicht mehr entfernen |
| `src/services/validator_render_service.py` | MODIFY | B2 Vorschau-Specs mitziehen |
| `tests/helpers/einstellung_auslieferung_orakel.py` | MODIFY | Einträge B1/B2/B3/B5 raus, `gust` bleibt |
| `tests/fixtures/einstellung_auslieferung/golden_b.json` (+ bewusst neu eingefrorene `erwartung_golden_*.json`) | MODIFY | zusätzliche Telegram-Metrik für das 7er-Limit; Erwartungen bewusst neu einfrieren, nicht still |
| `tests/tdd/test_einstellung_gleich_auslieferung.py` | MODIFY | B1-gebundene AC-2/AC-4/AC-10-Tests, Kommentare |
| B1-Pin-Tests (Liste oben) | MODIFY | Register-Pins auf den neuen Stand |
| `docs/adr/0011-alert-render-single-backend-renderer.md` | MODIFY | Nachtrag: TF auch im Trip (Stundenwert-Größe), löst „TF entfällt im Trip" (#2454 AC-6) ab |

### Scope Assessment
- Produktivdateien: ~8. Produktiv-LoC grob B3 ~1, B5 ~7, B1 ~30–50, B2 ~60–100, zusammen ~100–160 (unter 250; Tests und Doku zählen nicht). Bei Bedarf `loc_limit_override`, **kein** Parken einzelner Einträge.
- Testdateien: ~15 zu ziehen.
- Risk Level: **MEDIUM**:
  - B2 ändert die SMS-Darstellung für nahezu alle Bestandsnutzer.
  - B1 löst eine dokumentierte Kürzel-Entscheidung ab.
  - Renderer-Commit-Gate (trip_report.py) verlangt Modus-Matrix plus `briefing_mail_validator.py` frisch grün.

### Technical Approach
Ein Workflow, vier Fixes, sortiert nach Risiko:
1. B3 (1 Zeile)
2. B5 (Filter + golden_b-Anpassung)
3. B1 (TF-Register + Token + KÜRZEL-Text + ADR-Nachtrag)
4. B2 (format_mode-Durchreichung + GSM-7-Einfach-Zweig nach der E-Mail-Klassifikation)

Nach jedem Fix den zugehörigen Register-Eintrag entfernen; `test_ac6_ac7_…unbenutzten_eintraege` erzwingt das mechanisch. Zum 160-Zeichen-Budget: TF- und Stufen-Token sind nicht länger als die bisherigen Zahl-Token. Die Spec belegt das mit der gemessenen Länge der Golden-SMS.

### Dependencies
- Pfad: Trip-JSON → `loader` (Kaskade, format_mode, Ableitung) → `DisplayConfig.get_metrics_for_channel` → `trip_report` → Token-Builder / Channel-Layout → `notification_service` (SMS, Premium-SMS und Kurzform teilen `sms_text`).
- Die Editor-Kürzelmarken über `/api/sms-symbols` (`api/routers/config.py:60–90`) ziehen automatisch mit dem Register mit.
- Der Ortsvergleich teilt Katalog und Builder, nicht den format_mode-Pfad.

### Open Questions (klärt die Spec, keine Vorab-Frage an den PO)
- [ ] Konkrete ASCII-Einfachform je Metrik (Wolken 5 Stufen, CAPE, Sonne): kommt als AC-Vorschlag in die Spec, der PO gibt sie mit den ACs frei.
- [ ] TF-Token-Form im Trip (nur Kälte-Extrem mit Uhrzeit oder Bereich): die Spec entscheidet nach Budget und ADR-0011 „Stundenwert".
- [ ] Fall 3 (`nach_aenderung_fall3_roh_einfach_umschalten*.json`): Geht dort eine SMS-Metrik auf raw? Das bestimmt, ob die Roh-Zweige WD°/TH/SU in Scope sind.

## Übergabe RED → GREEN (/40, 2026-09-30)

- **CAPE ist über Layout/Kaskade nicht erreichbar:** `cape` hat `selectable=False` (#1585), `models._is_selectable` entfernt es aus jedem Kanal-Layout, `/api/metrics` liefert es nicht. Tech-Lead-Entscheid: `cape` bleibt in `SMS_FORMAT_MODE_METRIC_IDS` (laut Spec), die CAPE-Einfachform wird **nur auf Builder-Ebene** geprüft (AC-6/AC-7). `sms_format_capable` ist im Endpoint real nur für die vier Wolken-Größen sichtbar. #1585 wird NICHT zurückgebaut. Der Vakuum-Schutz „friendly im Orakel" läuft über die Wolken (in-Test-Varianten in `tests/tdd/_sms_einfach_fixtures.py`, weil `cloud_mid/high` in keinem Golden-SMS-Layout stehen).
- **AC-11:** Der Test erwartet `validator_render_service.build_sms_fidelity_specs(..., format_by_metric=...)` (Name analog `build_extended_metric_specs`). Verglichen werden die Wolken-Token, nicht die ganze Zeile (die Vorschau hat keine Layout-Positionen).
- **Mutation 6 (Dedup ohne Tiefstwert) ist äquivalent:** `build_day_window_points` dedupliziert bereits je Stunde, kein Test kann sie fangen. Den Adversary darauf hinweisen.
- `test_channel_metric_matrix.py` Z. 901/1056 (`not in SMS_MULTI_SYMBOLS…`) bleiben gültig, solange `TF` als Einzel-Symbol in `SMS_SYMBOL_BY_METRIC` abgelegt wird.
- `test_kuerzel_eindeutig.py::test_automatische_ausgaben_nach_t_umstellung` bleibt Wächter: `TF` wird nie ohne `MetricSpec` ausgegeben.
- `nach_speichern_golden_b.json` wurde von Hand an `golden_b` angeglichen. In /50 mit `GZ_ERZEUGE_NACH_DATEIEN=1` über `erzeuge_nach_dateien.ts` gegenprüfen.
- `tests/red/test_issue_435_format_modes.py` ist nicht erweitert; die #2429-Telegram-Lücke schließt `test_telegram_rich_roh_einfach_eigenes_layout.py`.
- Umgebung: 8 `SocketBlockedError` + 1 Setup-Error unter `--disable-socket` (TestClient/Premium-SMS-Stub) sind keine RED-Befunde. Der Frontend-Test braucht `npm ci` im Worktree.
- LoC: Die Spec schätzt 200–320 → vor GREEN `workflow.py set-field loc_limit_override 500`.
