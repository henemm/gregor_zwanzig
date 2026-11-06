# Context: S1c-4 #2792 — Umschalten, alle vier Kanäle gleichzeitig

- **Workflow:** `feat-2792-s1c4-umschalten` · **Epic:** #2791 · **ADR:** ADR-0106 (P1 CAPE ohne Farbe, P2 Gewitter „leicht“ fest gelb), ADR-0095 (Kanal-Parität), E1/E2
- **Spec:** `docs/specs/modules/feat_2792_s1_profil_ampel.md` (v1.3, Schnitt-Tabelle Zeile S1c-4; §5 „Leser umschalten“). ACs dieses Schritts: **AC-1 bis AC-7, AC-15 (Mail-Kopf), AC-19, AC-21** (AC-20 Struktur schon in S1c-1, Wirkung jetzt)
- **Delta-Dokument.** Die Leserliste, die Träger-Mechanik und die Gewitter-/CAPE-/Kurzkanal-Befunde stehen in `docs/context/feat-2792-s1c-leser.md` (§ Analysis, § „S1c-1: Einstieg vs. intern“). Hier stehen nur der Stand nach S1c-1/2/3 und die Pflichten für S1c-4.
- **Gemessen gegen:** `origin/main` @ `5fb07bbc8` (2026-11-06, enthält S1c-1 #2820, S1c-2 #2821, S1c-3 #2829)

## Request Summary
Letzter Teilschritt von S1: Alle Einstiege lösen die Ampel des Abos auf (`resolve_ampel(sub)` statt `resolve_ampel(None)`). Damit färben und markieren E-Mail, Telegram, SMS und Premium-SMS gleichzeitig nach der Vorlage bzw. der eigenen Ampel. Außerdem: CAPE ohne Farbe, Gewitter über eine zentrale Abbildung, Wertebereich-Markierung entfällt, `sms_threshold`/`DEFAULTS` wirken nicht mehr, Temperatur-Token mit Stunde, Doku. Danach ist #2792 schließbar.

## Stand nach S1c-1/2/3 (was schon da ist)
| Baustein | Ort | Stand |
|---|---|---|
| Ampel als keyword-only Pflichtparameter bis an jede Farbentscheidung | `src/output/**`, `alert/**` | live (S1c-1). Ratsche `tests/tdd/test_kein_leser_liest_display_thresholds.py`, Signatur-Ratsche `test_profil_ampel_kette.py::test_jeder_ampel_parameter_in_src_output_ist_pflicht_und_keyword_only` |
| `schwellen_aus_ampel(ampel, metric_id)` | `src/app/ampel.py:209` | liefert Schwellen der 9 `AMPEL_LESER`; **CAPE-Brücke** `:217-219` liefert noch Katalog-Schwellen; `hat_ampel` `:203` zählt CAPE mit |
| `thunder_color(level, ampel)` | `ampel.py:249` | **empirisch geprüft (2026-11-06):** `resolve_ampel({'preset_name':'wassersport'})` → `template='wassersport'`, `thunder_color(MED, resolved)` = `red`; dasselbe mit `display_config`-Hülle. Mit `None` = `orange`. Risiko 4 aus dem Vorgänger-Kontext ist damit erledigt, **sofern der aufgelöste Wert übergeben wird**. Bis heute ruft kein Renderer `thunder_color` |
| Kurzkanal-Prädikat `ampel_stufe` | `src/output/tokens/metrics.py:52/:75/:104` | vorbereitet, **nicht verdrahtet**; `_mk_metric` (`builder.py:203-220`) nutzt weiter `spec.threshold or DEFAULTS` |
| Migration Vergleichsschlüssel | S1c-2 | Prod gelaufen 2026-11-05, Kontroll-Probelauf „Nichts zu tun“ |
| Altfelder gesperrt (E2) | S1c-3 | live `5fb07bbc8`; `sms_threshold`/`corridors` bleiben beim Speichern erhalten (AC-24) |

## Die 16 Einstiege mit `resolve_ampel(None)` (umzuschalten)
| Einstieg | Funktion | Abo im Scope? | Signaturlücke |
|---|---|---|---|
| `email/html.py:861` | `render_html(*, dc, …)` | `dc` | nein |
| `email/plain.py:154` | `render_plain(*, dc, …)` | `dc` | nein |
| `email/compact.py:213` | `render_compact(*, dc, …)` | `dc` | nein |
| `narrow.py:713` | `render_telegram_bubbles(*, dc, …)` (Telegram-Briefing) | `dc` | nein |
| `email/outlook.py:622` | `build_outlook_row(…, trip_display_config=)` | `trip_display_config` (Scheduler reicht `dc`, `trip_report_scheduler.py:~3066`) | nein. **Pflicht aus Issue-Kommentar 2026-11-04:** Abo-Ampel muss hier wirken, sonst bleibt der Trip-Ausblick auf „allgemein“. Zwei Trips nacheinander testen |
| `email/compare_html.py:1815` | `render_compare_html(result, *, preset=…, preset_name=…)` | `preset` (Dict) | nein |
| `comparison.py:246` | `render_comparison_text(result, profile, …)` (Vergleich Nur-Text) | **nein** (`_ = profile` ohne Wirkung) | **ja**: `preset` von `render_compare_email` (`comparison.py:555`) durchreichen |
| `services/radar_alert_service.py:91` | `build_onset_alert_message(trip, …)` | `trip` | nein |
| `services/validator_render_service.py:210` | `render_alert_preview(trip_obj, …)` | `trip_obj` | nein |
| `services/validator_render_service.py:262` | `_deviation_preview_message(trip_obj, …)` | `trip_obj` | nein |
| `services/compare_alert_preview_service.py:140` | `_deviation(preset, …)` | `preset` (Dict) | nein |
| `services/compare_alert_preview_service.py:184` | `_onset(preset, …)` | `preset` (Dict) | nein |
| `services/notification_service.py:1141` | `send_deviation_alert(trip, …)` | `trip` | nein |
| `services/notification_service.py:1227` | `send_multi_location_deviation_alert(entities, …)` | **nein** (nur Orts-Tupel) | **ja**: Aufrufer `services/compare_alert.py:476` hat das Preset ⇒ Preset/Ampel durchreichen |
| `services/notification_service.py:1307` | `send_multi_location_radar_alert(entities, …)` | **nein** | **ja**: Aufrufer `services/compare_radar_alert.py:426` |
| `services/notification_service.py:1958` | `send_radar_alert(trip, …)` | `trip` | nein |

- **Weitere Einstiege ohne `resolve_ampel` im Code:** `TripReportFormatter.format_email` (`trip_report.py`, Aufrufer `notification_service.py:779`, `preview_service.py:328`) reicht `dc` an html/plain/compact; `format_sms` bekommt `thresholds=` aus `sms_threshold` (E1 ⇒ muss die Ampel bekommen). `compare_preview_service.py:162` und `scheduler_dispatch_service.py:971` rufen `render_compare_email` mit Preset.
- **Vergleichs-SMS/-Telegram** (`comparison.py:783` `render_compare_telegram`, `:1085` `render_compare_sms`): kein Farb- und kein Hervorhebungsleser (gemessen: keine `threshold`/`severity`/`ampel`-Zugriffe). Kein versteckter Leser. In /20 bestätigen, dass Kanal-Parität (ADR-0095) für den Vergleich damit trotzdem gilt.
- **Trip-Telegram-Kommandos** `trip_command_processor.py:578` `_BAND_EMOJI` über `thunder_ampel_band`: Gewitter-Dublette ⇒ über `thunder_color` mit der Trip-Ampel.

## Pflichten aus S1c-1/2/3 (stehen bisher nur in Issue-Kommentaren)
1. **Wirkungstest je Dienst-Einstieg** (Adversary S1c-1, LOW → Pflicht): `compare_alert_preview_service` (2×), `notification_service` (alle Alarm-Pfade, inkl. der zwei Multi-Location-Pfade), `validator_render_service` (2×), `radar_alert_service`. Je ein Test „Skitouren-Abo färbt anders als Allgemein-Abo“. Bei „allgemein“ bleibt eine Mutation unsichtbar.
2. **Leeres Ampel-Dict:** `schwellen_aus_ampel({}, 'gust')` liefert still `{}` (2026-11-06 nachgemessen). In S1c-4 laut scheitern lassen oder per Test absichern.
3. **CAPE-Brücke entfernen** (`ampel.py:203-219`, P1); `test_cape_traegt_in_s1c1_noch_eine_farbe` wird zur Zusicherung „CAPE trägt keine Farbe“ (AC-6).
4. **Übergangstests umkehren, nicht löschen:** `test_profil_ampel_kette.py::test_jeder_einstieg_loest_in_s1c1_genau_allgemein_auf` (:905), `::test_ausblick_einstieg_faerbt_in_s1c1_nach_allgemein` (:656), `::test_cape_traegt_in_s1c1_noch_eine_farbe` (:779) werden absichtlich rot. Sie werden zu S1c-4-Zusicherungen („jeder Einstieg löst das Abo auf“, nie still `None`). Keine Ratsche abschwächen.
5. **Kein Aufrufer mit Default `None` fällt still auf „allgemein“** (Vorgänger-Kontext :234): `build_outlook_row(trip_display_config=None)` u. a. prüfen.
6. **Reihenfolge-Gate in /70:** Probelauf `scripts/migrate_2792_profil_ampel.py` (ohne `--execute`) auf Prod erneut, Ergebnis „nichts zu tun“, Bericht im Issue, **vor** dem Prod-Deploy.
7. **E2E-Umfang:** Trip-Mail `briefing_mail_validator.py`, Vergleich `email_spec_validator.py`, Alarm `radar_alert_mail_validator.py` (+ `official_alert_mail_validator.py`, falls die amtliche Warnung berührt wird); DE und EN.

## Kurzkanäle (E1, AC-1, AC-7)
- **`DEFAULTS`** (`tokens/builder.py:165`): `R`→`precipitation` 0,2 · `PR`→`rain_probability` 20 · `W`→`wind` 10 · `G`→`gust` 20 · `TH:`/`TH+:`→`thunder` 1,0. Alle Symbole haben einen Ampel-Leser (4 in `AMPEL_LESER`, Gewitter über `thunder_color`). Ein Wegfall ändert also keine Metrik ohne Ampel still. **Sichtbare Wirkung:** Heute erscheint z. B. Wind ab 10 km/h als Spitzenwert, künftig erst ab Gelb (Allgemein 30). SMS-Golden-Dateien ändern sich in diesem Punkt; das ist von AC-19 **nicht** abgedeckt (AC-19 nennt nur Mail). In /20 klären, ob AC-19 (a–d) die Kurzkanal-Abweichungen mitnennt, sonst Spec-Nachtrag.
- **Gewitter-Schwelle 1,0** = ab „leicht“ = fest gelb (P2) ⇒ „gelb oder schlechter“ ist dieselbe Menge. Nur Wassersport ändert nichts an der Hervorhebung (nur die Farbe).
- **Temperatur mit Stunde:** `hiking_field_min_max` (`day_window.py:232`) liefert `(min, max, max_ts)`. `min_ts` zu ergänzen ändert die Tupelform für **7 Aufrufer**: `sms_trip.py:260/261`, `compact_summary.py:103/104`, `narrow.py:730`, `email/outlook.py:523/524`. Alternative: neue Funktion daneben, alte unverändert ⇒ in /20 entscheiden (weniger Churn).
- `_sms_mention_threshold` (`helpers.py`, Sicht 2,0 km, Luftfeuchte 90): Sicht aus der Ampel, Luftfeuchte bleibt fest (Spec §5).

## Golden-Dateien und Tests, die sich ändern werden (AC-19 einzeln benennen)
- (a) CAPE-Farbe entfällt, (b) Temperatur im Ausblick gefärbt, (c) Gewitter-Dubletten → zentrale Abbildung, (d) Wertebereich-Markierung entfällt.
- Kandidaten unter `tests/golden/`: `email/`, `vergleichs_mail/`, `f5_wertebereiche/`, `f8_layout_korridor/`, `f10_vergleich_flaechen/`, `sms/`, `telegram_briefing/`, `abweichungs_radar_alarm/`, `text_report/`. Welche tatsächlich kippen, misst /40 (Golden-Lauf vor und nach). Jede Abweichung wird einzeln benannt.
- **Renderer-Commit-Gate:** `tests/tdd/test_issue_811_mode_matrix.py` + `briefing_mail_validator.py` frisch grün; für die Vergleichs-Mail zusätzlich `email_spec_validator.py`.
- Bestehende Testdateien mit globalen Farb-Erwartungen: Liste im Spec-Testplan (u. a. `test_ampel_schwellen_katalog.py`, `test_compare_katalog_schwellen.py`, `test_outlook_metric_ampelfarben.py`, `test_thunder_column_ampel.py`, `test_gewitter_ampel_bandtreu.py`, `tests/unit/test_cape_ampel_thresholds.py`).

## Wertebereich-Markierung (aus)
`email/corridor_mark.py`; Leser `email/html.py:24/:663/:856`, `email/compare_html.py:44/:582`, Erwähnung `design_tokens.py:29`. Parameter `corridors=` an `render_compare_html` und `render_html`. Abschalten heißt: Leser entfernen bzw. nicht mehr aufrufen. Die Daten bleiben gespeichert (S1c-3 schützt sie beim Speichern).

## Gewitter-Dubletten (eine Abbildung)
`email/outlook.py:257` `_THUNDER_LEVEL_BG` (Nutzung `:302`), `outlook.py:444` `_metric_column_bg`, `email/html.py:166` `_thunder_risk_level`, `email/compare_html.py:245` `_sev_thunder`, `trip_command_processor.py:578` `_BAND_EMOJI`. Alle über `thunder_color(level, resolved)`.

## Dependencies
- **Upstream:** `app.ampel` (`resolve_ampel`, `schwellen_aus_ampel`, `thunder_color`, `template_for_profil`), `app.ampel_templates`, `severity_from_thresholds`, `thunder_ampel_band`, `day_window.hiking_field_min_max`, `tokens/metrics._peak_per_ampel_stufe`.
- **Downstream:** alle Kanal-Ausgaben (Trip-Briefing, Vergleich, Alarm Mail/Telegram/SMS/Premium-SMS), Golden-Fixtures, Modus-Matrix, drei bis vier Mail-Validatoren, `tests/test_metric_tokens_eingefroren.py` (Kürzel bleiben).
- **Doku:** `docs/reference/sms_format.md`, `telegram_format.md`, `premium_sms_format.md` („@14“ = erste Stunde gelb oder schlechter laut Ampel, Temperatur mit `@h`), `api_contract.md` (`sms_threshold`/`corridors` „ohne Wirkung, erhalten“).

## Existing Specs
- `docs/specs/modules/feat_2792_s1_profil_ampel.md` (maßgeblich), `ampel_schwellen_katalog.md`, `ampel_schwellen_renderer.md`, `fix_1491_gewitter_ampelkreis.md`, `fix_1849_ausblick_ampelfarben.md`.

## Risks & Considerations
1. **Spec-Freigabe:** Spec `status: draft`, Kästchen „Approved v1.3“ nicht angehakt (die Freigabe 2026-11-04 deckt v1.0). S1c-4 braucht vor /40 eine freigegebene Fassung. In /20 bzw. /30 prüfen, ob v1.3 schon freigegeben wurde (S1c-3-Lauf), sonst neu vorlegen (dabei auch die Fragen unten zu AC-19 und Kurzkanälen klären).
2. **Nicht nach Kanälen schneidbar:** Alle vier Kanäle schalten gleichzeitig um (ADR-0095). Umfang realistisch: 16 Einstiege (3 mit Signaturlücke), Kurzkanal-Verdrahtung + Temperatur-`@h` (7 Aufrufer), 5 Gewitter-Dubletten, CAPE-Brücke, Markierung aus, 3 umzukehrende Übergangstests, Wirkungstests je Dienst, Golden-Änderungen, 4 Doku-Dateien. **Richtwert 500 LoC trägt vermutlich nicht; Schätzung eher 800–1100 inkl. Tests.** Schnittoption für /20: S1c-4a „Umschalten + Pflichten (byte-gleich bei allgemein außer AC-19 a–d)“ und S1c-4b „Temperatur mit Stunde“. Das geht nur, wenn kein Kanal zwischenzeitlich anders bewertet; die Stunde ist reine Anzeige, die Bewertung bleibt gleich ⇒ in /20 prüfen.
3. **Sichtbare Änderung für echte Nutzer:** Prod-Abos mit Vorlage ≠ „allgemein“ oder eigener Ampel färben nach dem Deploy anders. Aus den Migrationsberichten bekannt: `henning/5f534011` (u. a. `sms_threshold`, verliert seine Wirkung nach E1), `cp-ac57aa1e29c65649`, `cp-eb6ba0b239d90e37`, `zillertal-t-glich`, dazu 12 Dateien aus S1b. **Nicht gemessen:** Die vollständige Liste „Vorlage ≠ allgemein“ auf Prod. Die Lesemessung per `sudo -n -u claude-gregor` mit Skript blockiert der Worktree-Wächter; in /20 außerhalb des Wächters nachholen (nur lesen, an der Trip-Konfiguration des PO nichts ändern).
4. **SMS-Wirkung:** Durch den Wegfall von `DEFAULTS` erscheinen Spitzenwerte in SMS/Premium-SMS/Telegram seltener (erst ab Gelb). Das ist laut E1 gewollt, ändert aber SMS-Goldens (siehe oben).
5. **Mandantentrennung / Prozesszustand (AC-2, AC-20):** keine Modul-Caches mit Ampel; zwei Presets bzw. Trips nacheinander in beiden Reihenfolgen.
6. **Byte-Gleichheit „allgemein“ (AC-19)** nur mit den vier benannten Abweichungen; `test_issue_811_mode_matrix.py` als Commit-Gate.
7. **Zweisprachigkeit:** Neue Nutzertexte sind nicht erwartet. Das Vorlagen-Label im Vergleichs-Kopf (AC-15) kommt aus `WEATHER_TEMPLATES`; in /20 prüfen, ob es für EN übersetzt vorliegt.

## Analysis

### Type
Feature (letzter Teilschritt S1c-4 von #2792, Epic #2791)

### Neue Befunde aus /20 (2026-11-06, gegen `5fb07bbc8`)
1. **16 Einstiege bestätigt** (`grep resolve_ampel(None)` = genau die Tabelle oben, Zeilen stimmen).
2. **Signaturlücken genauer:** `render_compare_email` (`comparison.py:493`) hat nur `preset_name: str`, kein Preset-Dict ⇒ neuer Parameter `preset`, Aufrufer `compare_preview_service.py:162`, `scheduler_dispatch_service.py:971`. Zusätzlicher Wrapper `notification_service.py:1171` (delegiert an `send_multi_location_deviation_alert`) muss mit. `compare_alert.py:476` und `compare_radar_alert.py:426` haben `preset: dict` im Scope. Tests `tests/test_wind_chill_max_selectable.py:185`, `tests/test_selection_conservation_rendered.py:131` rufen `render_comparison_text` ohne Preset ⇒ werden mit Pflichtparameter rot, gehören zum Test-Umfang.
3. **Zwei stille „allgemein“-Fallbacks** (Pflicht 5): (a) `build_outlook_row(trip_display_config=None)` (Default `outlook.py:539`); einziger Aufrufer `trip_report_scheduler.py:3060` mit `dc = getattr(stage_trip, "display_config", None)` (kann None sein); bei None läuft `outlook.py:647/653/799` in den **Ortsvergleichs-Zweig** — Ampel und Zweigwahl hängen heute an derselben None-Prüfung. (b) `render_compare_html(preset=None)`.
4. **`sms_threshold` wirkt auch in der Mail:** Erwähnungsschwellen `_sms_mention_threshold` (`email/helpers.py:1428`, 6 Aufrufstellen `:1744/:1767/:1792/:1819/:1914/:1937`), Quelle `mc.sms_threshold` in `html.py:1299-1307`, `compact.py:201`, `plain.py:210`; Fallback `DEFAULTS`; Sicht 2,0 km, Luftfeuchte 90 fest. Weitere Leser: `trip_report.py:146/151/374-389` (`_sms_thr` → `format_sms(thresholds=)`), `trip_report_scheduler.py:3047-3062` (`sms_thresholds=`). ⇒ Mail-Erwähnungen ändern sich **auch bei „allgemein“** (Wind 10→30 usw.), AC-19 (a–d) deckt das nicht.
5. **Kurzkanal-Verdrahtung fehlt ganz:** `render_threshold_peak_value(ampel_stufe=)` (`tokens/metrics.py:76-105`) hat keinen Aufrufer; `_mk_metric` (`builder.py:205`) kennt den Parameter nicht; es gibt keine Funktion Messwert→Stufe aus der aufgelösten Ampel. Gewitter ist ordinal ⇒ eigener Pfad („≥ leicht“ = heutige Schwelle 1,0 = fest gelb, P2).
6. **Gewitter-Dubletten präzisiert:** `outlook.py:257` `_THUNDER_LEVEL_BG` (LOW hart `#fbe6c3`, MED/HIGH fest orange/rot), `outlook.py:444` `_metric_column_bg` (ordinal-Zweig dito), `compare_html.py:245` `_sev_thunder` (liest `ampel` nicht), `trip_command_processor.py:578` `_BAND_EMOJI` (Emoji aus festem Band). `html.py:166` `_thunder_risk_level` liefert nur Zeilen-Risiko, keine Farbe ⇒ nur anfassen, falls es eine Farbe entscheidet. Gemeinsamer Nenner `thunder_ampel_band`; `thunder_color` hat keinen Aufrufer.
7. **AC-15 Kopfzelle „Profil“:** existiert (`compare_html.py:1439/1468-1483`, Katalogschlüssel `vergleich.kopf.profil`), Wert ist heute `profile_signature(profile, lang).eyebrow` (`profile_signature.py:96-109`), **nicht** das Vorlagen-Label. `WEATHER_TEMPLATES` (`metric_catalog.py:1296`) hat nur DE-Labels; `mail.profil.*` (EN `mail.json:70-73`) sind **Profil-IDs** (`summer_trekking`, …), nicht Vorlagen-IDs; für `alpen-trekking`, `skitouren`, `radtour`, `wassersport` fehlt EN. ⇒ neue Nutzertexte (ADR-0104). Vergleichs-SMS/-Telegram zeigen **kein** Profil-Label (gemessen `comparison.py:783-1200`) ⇒ Kopfzelle ist Mail-Kopf-Metadatum, in der Spec ausdrücklich so benennen. Auch bei „allgemein“ ändert sich der Zellwert sichtbar (Eyebrow „WETTER-BRIEFING“ o. ä. → „Allgemein“) ⇒ eigene AC-19-Abweichung.
8. **Übergangstests** `test_profil_ampel_kette.py:656/:779/:905` arbeiten per AST-Scan (`_aufloesungen` :884, Soll-Listen `EINSTIEGE` :796 (7 Renderer), `DIENST_EINSTIEGE` :853 (9 Dienste)); Ratschen `:872/:876` zählen `resolve_ampel`-Aufrufe je Funktion ⇒ ein neuer Helfer, der `resolve_ampel` ruft, muss in die Soll-Liste (ausdrücklich erweitern, nicht abschwächen).
9. **`hiking_field_min_max`:** 7 Aufrufstellen in 4 Dateien lesen per Index bzw. reichen das Tupel durch; `narrow.py:730` nutzt `found[2]` (= `max_ts`). Eine Tupel-Erweiterung am Ende wäre index-kompatibel, aber eine Schwesterfunktion ist churnfreier.
10. **Prod-Wirkungsliste gemessen** (2026-11-06, `sudo -n -u claude-gregor`, nur gelesen, `/var/lib/gregor/users/*/briefings/*.json`): 12 echte Abos (henning 11, steffi 1, default 1 Altdatei), **alle tragen bereits `ampel`** (Migration S1b/S1c-2). Vorlage: **11× `allgemein`, 1× `wintersport`** (`henning/zillertal`). Sichtbare Vorlagen-Wirkung nach Deploy also vor allem `zillertal`; bei den übrigen wirken nur die AC-19-Vereinheitlichungen plus eigene migrierte Ampel-Abweichungen (z. B. aus `sms_threshold`/`corridors` von `5f534011`, `cp-ac57aa1e29c65649`, `cp-eb6ba0b239d90e37`, `zillertal-t-glich`). `validator-issue110` (8 Testdateien) ohne Ampel ⇒ löst zu „allgemein“ auf.
11. **Spec v1.3 nicht freigegeben** (nur v1.0 am 2026-11-04). /30 legt v1.4 zur Freigabe vor; ohne Freigabe kein /40.

### Affected Files (with changes)
| File | Change Type | Description |
|------|-------------|-------------|
| `src/app/ampel.py` | MODIFY | CAPE-Brücke raus (`hat_ampel`, `schwellen_aus_ampel`); `{}`-Ampel scheitert laut; Prädikat „gelb oder schlechter“ (beidseitig) für Kurzkanal + Mail-Erwähnung; Gewitter-Prädikat |
| `src/app/metric_catalog.py` | MODIFY | CAPE-Schwellen entfallen (falls noch Leser) |
| `src/output/renderers/email/{html,plain,compact}.py` | MODIFY | `resolve_ampel(dc)`; Erwähnungsschwellen aus Ampel statt `mc.sms_threshold`; Markierung aus (html) |
| `src/output/renderers/email/helpers.py` | MODIFY | `_sms_mention_threshold` → Ampel-Prädikat; Luftfeuchte 90 als benannte Konstante |
| `src/output/renderers/email/outlook.py` | MODIFY | `ampel` Pflichtparameter; Zweigwahl expliziter Parameter statt `dc is None`; Gewitter über `thunder_color` |
| `src/output/renderers/email/compare_html.py` | MODIFY | Preset-Ampel; `_sev_thunder` über `thunder_color`; Markierung aus; Kopfzelle Vorlagen-Label |
| `src/output/renderers/email/corridor_mark.py` | DELETE | Markierung entfällt (Daten bleiben, `corridors=` wird ignoriert) |
| `src/output/renderers/comparison.py` | MODIFY | `render_compare_email(preset=)`, `render_comparison_text` mit Ampel |
| `src/output/renderers/narrow.py`, `sms_trip.py`, `day_window.py`, `compact_summary.py` | MODIFY | Telegram-Briefing auf Abo; Temperatur mit Stunde (`min_ts`) |
| `src/output/tokens/{builder,metrics}.py` | MODIFY | `DEFAULTS`/`spec.threshold` ohne Wirkung, `ampel_stufe` verdrahtet |
| `src/output/renderers/trip_report.py`, `src/services/trip_report_scheduler.py` | MODIFY | `_sms_thr` entfällt; `build_outlook_row` je `stage_trip` mit dessen Ampel |
| `src/services/{notification_service,radar_alert_service,validator_render_service,compare_alert_preview_service,compare_alert,compare_radar_alert,compare_preview_service,scheduler_dispatch_service}.py` | MODIFY | Einstiege auf Abo, Signaturlücken schließen |
| `src/services/trip_command_processor.py` | MODIFY | `_BAND_EMOJI` aus `thunder_color` mit Trip-Ampel |
| `src/i18n/messages/{de,en}/mail.json` | MODIFY | Vorlagen-Labels `mail.vorlage.<template_id>` (7 Vorlagen, DE = `WEATHER_TEMPLATES`) |
| `tests/tdd/test_profil_ampel_kette.py` | MODIFY | 3 Übergangstests umkehren, AST-Soll-Listen anpassen |
| `tests/tdd/test_*corridor_mark.py`, `test_thunder_column_ampel.py`, `test_gewitter_ampel_bandtreu.py`, `test_outlook_metric_ampelfarben.py`, `tests/unit/test_cape_ampel_thresholds.py`, `test_ampel_schwellen_katalog.py`, `test_compare_katalog_schwellen.py`, `test_thunder_mention_threshold_shared.py`, SMS-/Schwellen-Tests (`test_issue_872_threshold_ux.py`, `test_mail_pillen_schwelle_bei_eigenem_layout.py`, `test_thunder_pill_*`, `test_issue_624_metric_thresholds.py`, `test_th_plus_follows_thunder_metric_and_gap.py`, `test_sms_user_metric_order.py`) | MODIFY | globale/`sms_threshold`-Erwartungen auf Ampel umstellen (umkehren, nicht löschen) |
| `tests/tdd/test_s1c4_*.py` (neu) | CREATE | Wirkungstests je Einstieg (Skitouren ≠ Allgemein), zwei Abos nacheinander beide Reihenfolgen, AC-1..7/15/21 |
| `tests/golden/{sms,telegram_briefing,abweichungs_radar_alarm,email,vergleichs_mail,f5_wertebereiche,f8_layout_korridor,f10_vergleich_flaechen}/` | MODIFY | Neuaufnahme, jede Abweichung einzeln benannt (welche kippen, misst /40) |
| `docs/reference/{sms_format,telegram_format,premium_sms_format,api_contract}.md` | MODIFY | „@14“ aus Ampel, Temperatur `@h`, `sms_threshold`/`corridors` ohne Wirkung, erhalten |

### Scope Assessment
- Files: ca. 25 src + ca. 20 Tests + Goldens + 4 Doku
- Estimated LoC: src ca. +250/−200 (viel Entfernen), Tests ca. +600–800 ⇒ gesamt ca. 900–1200 (Richtwert 500 hält nicht)
- Risk Level: **HIGH** — schaltet die Bewertung aller vier Kanäle gleichzeitig um, ändert sichtbar auch „allgemein“-Ausgaben, 16 Einstiege mit stillen Fallback-Fallen

### Technical Approach
**Entscheidung Schnitt (technisch, Tech Lead):** Der vom Plan-Agenten vorgeschlagene Schnitt „4a Umschalten / 4b Temperatur mit Stunde“ wird **verworfen**: Die Temperatur-Hervorhebung in den Kurzkanälen ist laut AC-1 ampelabhängig, also **Bewertung**, nicht Anzeige. Nach 4a färbte die Mail +9 °C beim Skitouren-Abo orange, SMS/Premium-SMS/Telegram nicht ⇒ Verstoß gegen die Reihenfolge-Regel der Spec („kein Zeitpunkt, an dem die Kanäle unterschiedlich bewerten“, ADR-0095).
**Gewählt: byte-gleicher Vorbau + Umschalt-PR**, beide unter #2792:
- **S1c-4a „Vorbau“ (byte-gleich):** Prädikat-Funktionen in `ampel.py` (noch ohne Leser), `hiking_field_min_max_ts` (Schwesterfunktion, alte delegiert), Plumbing der Signaturlücken (`render_compare_email(preset=)`, `render_comparison_text`, beide Multi-Location-Alarme + Wrapper `:1171`; der neue Parameter wird durchgereicht, aufgelöst wird weiter `None`), expliziter Zweig-Parameter in `outlook.py`, Katalogschlüssel `mail.vorlage.*` DE/EN. **Prüfstein:** keine Golden-Datei kippt, Modus-Matrix unverändert, Übergangstests `:656/:779/:905` bleiben grün. Kein neuer `resolve_ampel`-Aufrufer (sonst Ratsche `:872/:876` rot) — Helfer, die auflösen, kommen erst in 4b.
- **S1c-4b „Umschalten“ (alle vier Kanäle gleichzeitig):** 16 Einstiege lösen das Abo auf (bei Trip ohne `display_config` das Trip-Objekt übergeben, nie `None`); `build_outlook_row(ampel=)` Pflicht ohne Default, je `stage_trip`; CAPE-Brücke raus; Gewitter-Dubletten über `thunder_color`; Markierung aus (`corridors=` bleibt als ignoriertes Argument, Daten erhalten, AC-24); `sms_threshold`/`DEFAULTS` ohne Wirkung — **ein** Prädikat „gelb oder schlechter“ (beidseitig, Wassersport-Untergrenzen) für Kurzkanäle **und** Mail-Erwähnungen; Gewitter „≥ leicht“; Luftfeuchte 90 als benannte Konstante; Temperatur-Token mit Stunde; `{}`-Ampel scheitert laut; Kopfzelle „Profil“ = Vorlagen-Label; Übergangstests umkehren, Wirkungstests je Dienst-Einstieg; Goldens neu mit Einzelbenennung; Doku.
- Begründung: 4a senkt das Diff-Volumen von 4b um die reine Mechanik (ca. 250–350 LoC), ohne dass sich irgendeine Ausgabe ändert — gleiches Muster wie S1c-1. Fällt 4a kleiner aus als erwartet, darf /30 auf **einen** PR mit `loc_limit_override` ca. 1200 zurückfallen (ebenfalls paritätstreu). Kein dritter Weg.

**Spec-Nachträge v1.4 (für /30):**
1. Schnitt-Tabelle: S1c-4a (Vorbau, byte-gleich, ca. 350) / S1c-4b (Umschalten, ca. 800), ACs je Schritt, Paritätsbegründung.
2. AC-19 um **(e)** Erwähnungs-/Spitzenwertschwellen in Mail und Kurzkanälen folgen der Ampel (auch bei „allgemein“, z. B. Wind erst ab 30 km/h) und **(f)** Kopfzelle „Profil“ zeigt das Vorlagen-Label erweitern; Kurzkanal-Goldens (`sms/`, `telegram_briefing/`, Premium-SMS) einzeln benennen.
3. AC-15: Label-Quelle `mail.vorlage.<template_id>` (7 Vorlagen, DE gleich `WEATHER_TEMPLATES`, EN neu), Zelle nur im Mail-Kopf (Vergleichs-SMS/-Telegram zeigen kein Profil).
4. §5: kein Einstieg fällt still auf `None` (Trip-Objekt statt `dc`), `build_outlook_row(ampel=)` Pflicht + expliziter Zweig-Parameter, `render_compare_html(preset=None)` abschaffen, `{}`-Ampel scheitert laut, Luftfeuchte-Konstante, `hiking_field_min_max_ts`.
5. Testplan: Wirkungstest je Einstieg (16) mit Skitouren vs. Allgemein (bei „allgemein“ bleibt eine Mutation unsichtbar), zwei Abos nacheinander in beiden Reihenfolgen (AC-2/AC-20), Umkehr der drei Übergangstests + AST-Listen, die zwei `render_comparison_text`-Tests.

### Dependencies
Siehe Abschnitt „Dependencies“ oben; zusätzlich `profile_signature.py` (Kopfzelle, wird für die Zelle „Profil“ nicht mehr gelesen; Eyebrow/Titel bleibt), `src/i18n/messages/*/mail.json`.

### Open Questions
- [x] AC-19 Kurzkanal-/Erwähnungs-Abweichungen ⇒ ja, Nachtrag (e)/(f) in v1.4 (technisch, keine PO-Designfrage)
- [x] `hiking_field_min_max` ⇒ Schwesterfunktion `hiking_field_min_max_ts`
- [x] Schnitt ⇒ Vorbau (byte-gleich) + Umschalten; 4a/4b nach Temperatur verworfen (Parität)
- [x] Prod-Wirkungsliste ⇒ gemessen (11× allgemein, 1× wintersport, alle mit Ampel)
- [ ] Spec v1.4 freigeben ⇒ in /30 per `AskUserQuestion` (PO)
- [ ] Reihenfolge-Gate /70: Migrations-Probelauf auf Prod „nichts zu tun“ vor Prod-Deploy von 4b

## Open Questions (für /20, Stand vor der Analyse)
- [ ] AC-19 nennt nur Mail-Abweichungen. Kurzkanal-Golden-Änderungen durch E1 (`DEFAULTS` weg) und Temperatur-`@h` ausdrücklich in die Spec aufnehmen? (technisch, Spec-Nachtrag, keine PO-Designfrage)
- [ ] `hiking_field_min_max` erweitern oder Schwesterfunktion mit `min_ts`?
- [ ] Schnitt S1c-4a/4b ja oder nein (Parität prüfen).
- [ ] Prod-Wirkungsliste (Abos mit Vorlage ≠ allgemein) außerhalb des Worktree-Wächters messen.
- [ ] Ist Spec v1.3 freigegeben? Sonst vor /40 Freigabe einholen.
