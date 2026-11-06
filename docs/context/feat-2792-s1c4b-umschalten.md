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

## Analysis

### Type
Feature (Umschalt-Schritt S1c-4b von #2792, Epic #2791). Delta-Analyse: die Vollanalyse (Befunde 1–11, Dateitabelle) in `docs/context/feat-2792-s1c4-umschalten.md` § Analysis gilt unverändert. Den Explore-Fächer und den Plan-Agenten habe ich übersprungen, weil schon alles gemessen ist. Unten steht nur, was 4b neu misst und entscheidet (gemessen 2026-11-06 gegen `24fa5e876`, also `4f3309cd4` plus Kontext-Commit).

### Neue Befunde (Delta)
1. **16 Einstiege bestätigt**, Zeilen wie im Abschnitt „Die 16 Einstiege“ oben (`grep -rn "resolve_ampel(None)" src` = 16 Treffer).
2. **„Trip-Objekt statt `dc`“ ändert für die vier Trip-Renderer nichts.** `Trip` (`src/app/trip.py`) hat kein `preset_name`/`profil`, die Vorlage liegt nur in `display_config` (`models.py:827` `preset_name`, `:873` `ampel`). `_aufloesen` (`ampel.py`) liefert für einen Trip ohne `dc` dasselbe wie `resolve_ampel(None)`, also „allgemein“. `format_email` baut `dc = display_config or build_default_display_config()` (`trip_report.py:127`). Der Default (`metric_catalog.py:1286`) setzt weder `preset_name` noch `ampel` und ergibt damit ebenfalls „allgemein“. **Entscheidung:** `render_html`, `render_plain`, `render_compact` und `render_telegram_bubbles` lösen `resolve_ampel(dc)` mit der `dc` auf, die sie ohnehin bekommen. Einen neuen Parameter gibt es nicht. Ein RED-Test „Trip ohne `dc` ⇒ allgemein“ wäre nicht rot zu bekommen und entfällt. Pflicht ist stattdessen der Wirkungstest mit `dc.preset_name="skitouren"` bzw. `dc.ampel` (Skitouren ≠ Allgemein).
3. **Vorschau und Versand haben dieselbe Quelle.** Der Versand nutzt `TripReportRequest.display_config = trip.display_config` (`trip_report_scheduler.py:2186`), die Vorschau `trip.display_config` (`preview_service.py:328`). Abgeleitete Kopien entstehen nur per `dataclasses.replace(dc, metrics=…)` (`trip_report.py:156`, `:298` `_dc_telegram`) und behalten `ampel`/`preset_name`. Eine Divergenz gibt es also nicht. **RED-Pflicht:** ein Wirkungstest über `format_email` mit Skitouren-`dc` muss in HTML, Plain, Compact **und** Telegram-Blasen die Skitouren-Bewertung zeigen. Er fängt eine Mutation, die beim `replace` die Ampel verliert.
4. **Der Ausblick-Einstieg wandert in den Scheduler.** `build_outlook_row(ampel=)` wird Pflicht ohne Default. Der Aufruf `outlook.py:628` `resolve_ampel(None)` entfällt, dafür kommt `trip_report_scheduler.py` (~`:3044-3070`) mit `ampel=resolve_ampel(stage_trip)` hinzu. Der Import kommt aus `app.ampel`, und die Wache `test_scheduler_has_no_output_imports` (`tests/unit/test_notification_service.py:221`) verbietet nur `output.*`-Bezüge. Im selben Block entfallen `_sms_thr`/`sms_thresholds=` (`:3042-3048`, `:3062`). **AST-Listen in `test_profil_ampel_kette.py`:** `build_outlook_row` wandert aus der „löst auf“-Soll-Liste in eine neue Soll-Liste „nimmt `ampel` als Pflichtparameter ohne Default“ (per AST prüfen: Parameter da, kein Default). Die Scheduler-Funktion kommt neu in `DIENST_EINSTIEGE`. Das ist eine Erweiterung, keine Abschwächung: Jeder der 16 Wege bleibt bewacht, die Prüfung sitzt nur dort, wo aufgelöst wird. Die Zähl-Ratschen werden in /40 neu gemessen.
5. **`format_sms(thresholds=)` hat genau einen Aufrufer:** `trip_report.py:471` (`SMSTripFormatter().format_sms(…, thresholds=_sms_thr or None, …)`), und `_sms_thr` stammt aus `sms_threshold`. In 4b reicht er stattdessen die Ampel durch (`resolve_ampel(dc)`, dieselbe `dc` wie für die Mail). `_sms_threshold`/`alert_channel_thresholds` (`:464`, amtliche Warnstufe der SMS, #1461) ist **etwas anderes** und bleibt unberührt.
6. **F001/F002/Hinweis a/b** aus dem 4a-Lauf: siehe „Neue Pflichten aus dem 4a-Lauf“ oben, unverändert in den 4b-RED-Umfang übernommen.

### Affected Files (with changes)
Die Tabelle aus `feat-2792-s1c4-umschalten.md` § Analysis gilt. Ergänzungen bzw. Präzisierungen:

| File | Change Type | Description |
|------|-------------|-------------|
| `src/output/renderers/trip_report.py` | MODIFY | `format_sms` bekommt die Ampel statt `thresholds=_sms_thr` (`:471`); `_sms_thr` fällt weg; `_sms_threshold` (#1461) bleibt |
| `src/output/renderers/sms_trip.py` | MODIFY | `format_sms`/`render_sms`: `thresholds=` raus, Ampel rein, Hervorhebung über `gelb_oder_schlechter` |
| `src/services/trip_report_scheduler.py` | MODIFY | `ampel=resolve_ampel(stage_trip)` an `build_outlook_row`; `_sms_thr`-Block raus |
| `src/output/renderers/email/outlook.py` | MODIFY | `ampel` Pflicht ohne Default, `resolve_ampel(None)` `:628` raus, Gewitter über `thunder_color` |
| `src/output/renderers/day_window.py` | MODIFY | Gleichstand im Minimum von `hiking_field_min_max_ts` deterministisch nach `ts` (/60-Hinweis a) |
| `tests/tdd/test_profil_ampel_kette.py` | MODIFY | Übergangstests umkehren; neue Soll-Liste „Pflichtparameter `ampel`“ (`build_outlook_row`); Scheduler in `DIENST_EINSTIEGE` |
| `tests/test_wind_chill_max_selectable.py`, `tests/test_selection_conservation_rendered.py` | MODIFY | Preset mit Ampel statt `preset=None` (/60-Hinweis b) |
| `tests/tdd/test_s1c4b_*.py` | CREATE | 16 Wirkungstests, beide Reihenfolgen, zwei Nutzer, F001 (Scheduler, Trip mit/ohne `dc`, Gewitter nachts), F002 (Ein-Ort-Wrapper), `format_email`-Vierkanal-Test (Befund 3) |

### Scope Assessment
- Files: ca. 25 src + ca. 20 Tests + Goldens + 4 Doku (wie Vorgänger-Analyse, abzüglich der 4a-Mechanik)
- Estimated LoC: Richtwert ca. 800, `loc_limit_override` 900 (Spec v1.4); src überwiegend Entfernen (CAPE-Brücke, `corridor_mark.py`, `_sms_thr`, Gewitter-Dubletten), Tests dominieren
- Risk Level: **HIGH**. Der Schritt schaltet die Bewertung aller vier Kanäle gleichzeitig um und ändert auch bei „allgemein“ sichtbar die Erwähnungsschwellen und die Kopfzelle (AC-19 e/f).

### Technical Approach
Vorgehen nach Spec v1.4 §5, Nachtrag Punkte 1–10, unverändert. Präzisierungen aus den Befunden 2–5: Die Trip-Renderer lösen ihre `dc` auf. Der Ausblick bekommt die Ampel vom Scheduler, der sie aus `stage_trip` auflöst. Die SMS bekommt die Ampel aus derselben `dc` wie die Mail. Reihenfolge in /50: (1) `ampel.py` (`{}` scheitert, CAPE-Brücke raus) → (2) Gewitter-Dubletten → `thunder_color` → (3) 16 Einstiege + Scheduler → (4) Prädikat in Kurzkanälen und Mail-Erwähnungen, `DEFAULTS`/`spec.threshold`/`sms_threshold` ohne Wirkung → (5) Markierung aus → (6) Kopfzelle „Profil“ → (7) Goldens neu mit Zuordnung (a)–(f) → (8) Doku. Am Ende von /50 führe ich einen neuen Adversary-Dialog (Lehre S1c-3).

### Befunde, die gegen den Plan sprechen
- **Größe:** 800 bis 900 LoC in einem PR sind viel zu prüfen. Ein Teilen nach Kanälen verstieße gegen die Parität (ADR-0095, Spec-Reihenfolge-Regel). Ein dritter Schnitt ist laut Spec ausgeschlossen. Übersteigt der Umfang 900 deutlich, hebe ich `loc_limit_override` mit Begründung an und teile nicht.
- **„allgemein“ ist bei Mutationen blind:** 11 von 12 Prod-Abos nutzen „allgemein“. Ein vergessener Einstieg fällt in Prod kaum auf. Abhilfe ist der Wirkungstest je Einstieg mit Skitouren-Abo (Pflicht).
- Sonst keine: Befund 3 schließt die befürchtete Abweichung zwischen Vorschau und Versand aus, und Befund 2 macht keinen neuen Parameter nötig.

### Spec-Status
Spec v1.4 ist im Lauf `feat-2792-s1c4-umschalten` freigegeben (Archivlauf unter `_archive/`). Die Befunde 2–5 **passen zu v1.4 im vorliegenden Wortlaut**. §5.1 verlangt das Trip-Objekt nur dort, „wo `dc` fehlen kann“; das betrifft genau den Scheduler/Ausblick (Befund 4). Für die Renderer ist `dc` nach Befund 2 gleichwertig. §5.9 verlangt die Ampel an `format_sms` (Befund 5). **⇒ Kein v1.5-Nachtrag, keine neue Freigabe.** /30 trägt nur die freigegebene v1.4 im neuen Workflow ein (Spec-Pfad und Verweis auf die Freigabe im Archivlauf).

### Open Questions
- [x] Trip im Scope der vier Trip-Renderer? ⇒ nicht nötig, `dc` ist gleichwertig (Befund 2)
- [x] Gleiche Quelle für Vorschau und Versand? ⇒ ja (Befund 3)
- [x] AST-Listen bei wanderndem Ausblick-Einstieg ⇒ Erweiterung um eine Pflichtparameter-Liste (Befund 4)
- [ ] /70 Reihenfolge-Gate: Migrations-Probelauf auf Prod „nichts zu tun“ vor dem Prod-Deploy (bleibt Pflicht, kein PO-Thema)
