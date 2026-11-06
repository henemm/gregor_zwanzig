# Context: S1c-4b #2792 — Umschalten, alle vier Kanäle gleichzeitig

- **Workflow:** `feat-2792-s1c4b-umschalten` · **Epic:** #2791 · **ADR:** ADR-0106 (P1 CAPE ohne Farbe, P2 Gewitter „leicht“ fest gelb), ADR-0095 (Kanal-Parität)
- **Spec:** `docs/specs/modules/feat_2792_s1_profil_ampel.md` **v1.4**, im Lauf `feat-2792-s1c4-umschalten` freigegeben (`spec_approved: true`, Archiv `.claude/workflows/_archive/feat-2792-s1c4-umschalten.json`). Maßgeblich für 4b: Schnitt-Tabelle Zeile S1c-4b, §5 „Nachtrag S1c-4 (v1.4): Pflichten beim Umschalten“ (Punkte 1–10), „Nachtrag S1c-4 (v1.4): Testplan“, AC-1 bis AC-7, AC-15 (Mail-Kopf), AC-19 (a)–(f), AC-21, AC-25, AC-27. `loc_limit_override` Richtwert **900**.
- **Delta-Dokument.** Vollständige Analyse (16 Einstiege, Signaturlücken, Kurzkanäle, Gewitter-Dubletten, Markierung, Prod-Wirkungsliste) steht in `docs/context/feat-2792-s1c4-umschalten.md` (§ Analysis, Befunde 1–11). Hier nur: Stand nach 4a, was 4b konkret vorfindet, und neue Pflichten aus dem 4a-Lauf.
- **Gemessen gegen:** `origin/main` @ `4f3309cd4` (2026-11-06, enthält S1c-4a PR #2835).

## Request Summary
Alle 16 Einstiege lösen die Ampel des Abos auf statt `resolve_ampel(None)`. Damit bewerten E-Mail, Telegram, SMS und Premium-SMS gleichzeitig nach Vorlage bzw. eigener Ampel. Dazu: CAPE ohne Farbe, Gewitter zentral über `thunder_color`, Wertebereich-Markierung aus, `sms_threshold`/`DEFAULTS` ohne Wirkung, ein Prädikat „gelb oder schlechter“ für Kurzkanäle und Mail-Erwähnungen, Temperatur mit Stunde, Kopfzelle „Profil“ mit Vorlagen-Label, Übergangstests umkehren, Wirkungstests je Einstieg, Goldens neu, Doku. Danach ist #2792 schließbar (nach Reihenfolge-Gate und Selftest).

## Was 4a geliefert hat (Bausteine für 4b, alle noch ohne Leser)
| Baustein | Ort | Nutzung in 4b |
|---|---|---|
| `ampel_stufe(ampel, metric_id, wert)` | `src/app/ampel.py:268` | Messwert → Stufe aus dem aufgelösten Objekt (gleicher Kern wie `severity_from_thresholds`) |
| `gelb_oder_schlechter(ampel, metric_id, wert)` | `ampel.py:275` | **das eine** Prädikat für Kurzkanäle (`_mk_metric`, `render_threshold_peak_value(ampel_stufe=)`) und Mail-Erwähnungen (`_sms_mention_threshold`, 6 Stellen `email/helpers.py`) |
| `gewitter_gelb_oder_schlechter(level)` | `ampel.py:280` | Gewitter „≥ leicht“ (ersetzt Schwelle 1,0) |
| `vorlage_label_schluessel(template_id)` | `ampel.py:288` | Kopfzelle „Profil“ (`compare_html.py` ~`:1439/:1468-1483`) → `t(vorlage_label_schluessel(tid), lang)` |
| Katalog `mail.vorlage.<id>` (7, DE/EN) | `src/i18n/messages/{de,en}/mail.json` | dito |
| `hiking_field_min_max_ts` → `(min, max, min_ts, max_ts)` | `src/output/renderers/day_window.py:250` | Temperatur-Token mit `@h` je Hälfte; alte Funktion delegiert, 7 Aufrufer unverändert |
| `context="route"\|"vergleich"` Pflicht an `build_outlook_row`/`_outlook_row` | `email/outlook.py:547/:650` | Zweigwahl ist von der Ampel entkoppelt; 4b macht `ampel=` am Einstieg Pflicht ohne Default |
| `preset` Pflicht an `render_comparison_text` (`comparison.py:193`), `render_compare_email` (reicht durch `:581`), `send_location_deviation_alert` (`notification_service.py:1163`), `send_multi_location_deviation_alert` (`:1190`), `send_multi_location_radar_alert` (`:1268`) | | jetzt nur durchgereicht, 4b löst dort `resolve_ampel(preset)` auf |

## Die 16 Einstiege (gemessen 2026-11-06 auf `4f3309cd4`, `grep -rn "resolve_ampel(None)" src`)
`comparison.py:249` · `email/outlook.py:628` · `email/compact.py:213` · `email/plain.py:154` · `email/compare_html.py:1817` · `narrow.py:713` · `email/html.py:861` · `validator_render_service.py:210/:262` · `radar_alert_service.py:91` · `notification_service.py:1141/:1235/:1316/:1967` · `compare_alert_preview_service.py:140/:184`. Zuordnung Funktion → Abo-Quelle: Tabelle in `feat-2792-s1c4-umschalten.md` (unverändert gültig, nur Zeilen leicht verschoben).

**Abo-Quelle im Trip-Fall:** Spec §5.1 — wo nur `dc` im Scope ist und fehlen kann, das **Trip-Objekt** übergeben (Vorlage über `preset_name`), nie `None`. `resolve_ampel` akzeptiert Trip-Objekt, `display_config`-Hülle und Preset-Dict (empirisch geprüft, Vorgänger-Kontext Zeile 16). Für `render_html/plain/compact`/`render_telegram_bubbles` in /20 klären, ob der Trip im Scope ist oder `dc` reicht (Aufrufer `trip_report.py` `TripReportFormatter.format_email`, `notification_service.py:779`, `preview_service.py:328`).

## Neue Pflichten aus dem 4a-Lauf (stehen sonst nur in Issue-Kommentaren)
1. **F001 (Adversary 4a, MEDIUM):** Trip-Zweig im produktiven Aufrufer (`trip_report_scheduler.py:3068` `context="route"`, `compare_html.py:1310` `context="vergleich"`) ist nur per AST bewacht. **4b-RED:** Verhaltenstest nah am Scheduler mit einem Trip **mit** und einem **ohne** `display_config` und einer Gewitterstunde **nachts** (Tagesfenster #1841): Vertauschen von `route`/`vergleich` muss rot werden.
2. **F002 (Adversary 4a, LOW):** Durchreichen von `preset` im Ein-Ort-Wrapper `send_location_deviation_alert` (`notification_service.py:1156-1178`) nur AST-bewacht. **4b-RED:** Wirkungstest Skitouren ≠ Allgemein über genau diesen Weg.
3. **/60-Hinweis a:** Gleichstand im Minimum von `hiking_field_min_max_ts` hängt an der Eingabereihenfolge (`min(..., key=)` liefert das erste Vorkommen). Der Docstring sagt „früheste Stunde“; das gilt nur bei zeitlich sortierten Punkten. In 4b, wenn `min_ts` erstmals sichtbar wird: deterministisch nach `ts` brechen oder sortierte Eingabe zusichern, plus Test mit unsortierten Punkten.
4. **/60-Hinweis b:** `render_comparison_text`-Tests (`tests/test_wind_chill_max_selectable.py`, `tests/test_selection_conservation_rendered.py`) in 4a mit `preset=None` o. ä. umgestellt; in 4b auf ein Preset **mit Ampel** umstellen, sonst prüfen sie nach dem Umschalten nur noch „allgemein“.
5. **Vorbestehend rot, nicht unser Fehler:** Telegram-Live `test_ac4` („heute/morgen“) war vor und nach 4a rot (Nebenbefund in #1199). In /e2e-verify nicht als Regression werten, aber erneut vergleichen.
6. **Lehre aus S1c-3:** Nach Test-Umstellungen am Ende von /50 einen neuen Adversary-Dialog führen (S1c-3 hat das ausgelassen).

## Unverändert gültige Pflichten (Spec §5 / Vorgänger-Kontext)
- Übergangstests `tests/tdd/test_profil_ampel_kette.py` (`::test_ausblick_einstieg_faerbt_in_s1c1_nach_allgemein`, `::test_cape_traegt_in_s1c1_noch_eine_farbe`, `::test_jeder_einstieg_loest_in_s1c1_genau_allgemein_auf`) umkehren, nicht löschen; AST-Soll-Listen `EINSTIEGE`/`DIENST_EINSTIEGE` und Zähl-Ratschen nur **erweitern**. Zeilennummern nach 4a in /40 neu messen.
- `{}`-Ampel scheitert laut (`schwellen_aus_ampel`), CAPE-Brücke `ampel.py:203-219` raus, `render_compare_html(preset=None)` abschaffen, Luftfeuchte 90 als benannte Konstante, Sicht aus Ampel.
- Gewitter-Dubletten: `outlook.py` `_THUNDER_LEVEL_BG`/`_metric_column_bg`, `compare_html.py` `_sev_thunder`, `trip_command_processor.py` `_BAND_EMOJI` → `thunder_color(level, resolved)`.
- Markierung aus: `corridor_mark.py` löschen, `corridors=` bleibt ignoriertes Argument (AC-24).
- Kurzkanäle: `DEFAULTS` (`tokens/builder.py:165`) und `spec.threshold` ohne Wirkung; `TripReportFormatter.format_sms` bekommt Ampel statt `thresholds=`; `_sms_thr` (`trip_report.py`) und `sms_thresholds=` (`trip_report_scheduler.py:3047-3062`) entfallen.
- Wirkungstest je Einstieg (16) Skitouren vs. Allgemein, zwei Abos nacheinander in beiden Reihenfolgen, zwei Nutzer.
- Goldens: Lauf vor/nach, jede Abweichung einem Buchstaben (a)–(f) aus AC-19 zuordnen; Kurzkanal-Goldens `sms/`, `telegram_briefing/` eingeschlossen.
- Renderer-Commit-Gate: `test_issue_811_mode_matrix.py` + `briefing_mail_validator.py` (+ `email_spec_validator.py`).
- **/70 Reihenfolge-Gate:** Probelauf `scripts/migrate_2792_profil_ampel.py` (ohne `--execute`) auf Prod „nichts zu tun“, Bericht im Issue, **vor** dem Prod-Deploy.
- **E2E:** Trip `briefing_mail_validator.py`, Vergleich `email_spec_validator.py`, Alarm `radar_alert_mail_validator.py`, ggf. `official_alert_mail_validator.py`; DE und EN; Premium-SMS-Empfang über die zweite seven.io-Nummer.

## Dependencies
- **Upstream:** `app.ampel` (`resolve_ampel`, `schwellen_aus_ampel`, `thunder_color`, 4a-Prädikate, `vorlage_label_schluessel`), `app.ampel_templates`, `output.metric_format.severity_from_thresholds`, `thunder_ampel_band`, `day_window.hiking_field_min_max_ts`, `tokens/metrics.render_threshold_peak_value`, i18n-Katalog.
- **Downstream:** alle Kanal-Ausgaben (Trip-Briefing, Ausblick, Vergleich, Alarm Mail/Telegram/SMS/Premium-SMS, Telegram-Kommandos), Golden-Fixtures, Modus-Matrix, vier Mail-Validatoren, `tests/test_metric_tokens_eingefroren.py`.
- **Doku:** `docs/reference/{sms_format,telegram_format,premium_sms_format,api_contract}.md`.

## Existing Specs
- `docs/specs/modules/feat_2792_s1_profil_ampel.md` (maßgeblich, v1.4), daneben `ampel_schwellen_katalog.md`, `ampel_schwellen_renderer.md`, `fix_1491_gewitter_ampelkreis.md`, `fix_1849_ausblick_ampelfarben.md`.

## Risks & Considerations
1. **Größe:** Richtwert ca. 800 LoC (Limit-Override 900). Testlast (16 Wirkungstests, Umstellungen, Goldens) dominiert. Fallback laut Spec: kein dritter Schnitt; wird 900 deutlich überschritten, `loc_limit_override` begründet anheben statt Kanäle zu trennen (Parität).
2. **Sichtbare Prod-Wirkung:** 12 Abos, 11× `allgemein`, 1× `wintersport` (`henning/zillertal`). Auch bei „allgemein“ ändern sich Erwähnungsschwellen (AC-19 e: z. B. Wind erst ab 30 km/h) und die Kopfzelle (AC-19 f). Trip-Konfiguration des PO nicht anfassen.
3. **Stille Fallbacks:** jeder Einstieg mit möglichem `None`-Abo ist eine Falle; Wirkungstests müssen eine Mutation `abo → None` sichtbar machen (nur mit Vorlage ≠ allgemein).
4. **Mandantentrennung/Prozesszustand:** keine Modul-Caches mit Ampel; beide Reihenfolgen testen.
5. **Zeilennummern** in Spec und Vorgänger-Kontext beziehen sich teils auf `5fb07bbc8`; vor Zitaten in /40 neu messen.
6. **Staging-Mailweg:** laut Memory zeitweise kaputt (#2774); /e2e-verify-Nachweise ehrlich benennen.
