# Context: S1c #2792 — Alle Leser auf die Profil-Ampel umstellen

- **Workflow:** `feat-2792-s1c-leser` · **Epic:** #2791 · **ADR:** ADR-0106 (P1 CAPE ohne Farbe, P2 Gewitter „leicht“ fest gelb, P3)
- **Spec (freigegeben, gilt unverändert):** `docs/specs/modules/feat_2792_s1_profil_ampel.md` — S1c = §5 „Leser umschalten“, ACs **AC-1 bis AC-7, AC-15 (Mail-Kopf), AC-19 bis AC-22**
- **Vorgänger-Kontext (nicht duplizieren):** `docs/context/feat-2792-s1-profil-ampel.md` §3 (Leserliste mit Datei:Zeile), §4 (E1/E2)
- **Gemessen gegen:** `origin/main` @ `8661a1e86` (2026-11-04, enthält S1a #2805 und S1b #2809)

## Request Summary
Der dritte und letzte Schritt von S1: Jeder Renderer aller vier Kanäle (Mail HTML/Plain/Compact, Ausblick, Vergleich, Alarm, SMS, Premium-SMS, Telegram) färbt bzw. hebt hervor nach der Ampel des Abos (`ampel_for`) statt nach dem globalen `display_thresholds`; Gewitter über eine zentrale Abbildung, CAPE ohne Farbe; Wertebereiche-Reiter und SMS-Schwellwerte im Frontend nur noch lesbar mit Hinweis (E2). Danach ist #2792 schließbar.

## Was S1a/S1b bereits geliefert haben (Stand HEAD)
| Baustein | Ort | Bemerkung |
|---|---|---|
| `ampel_for(subscription) -> {metric_id: thresholds}` | `src/app/ampel.py:188` | Form genau wie `severity_from_thresholds` (`yellow/orange/red`, `*_lt`, offene weggelassen). Nimmt Trip, ComparePreset, `display_config` (Objekt oder Dict) |
| `resolve_ampel`, `template_id_for` | `ampel.py:172`, `:150` | Rückfallkette Abo → `ampel.template` → `preset_name` → `profil` → `allgemein` |
| `thunder_color(level, ampel)` | `ampel.py:218` | keins grün, leicht gelb (über `thunder_ampel_band`), mittel/hoch nach Vorlage/Abo. **Signatur nimmt die rohe Ampel (`display_config.ampel`), nicht das Abo** — bei Trips ohne `ampel` greift dann `allgemein`, nicht `preset_name` ⇒ in /20 klären (ggf. `resolve_ampel(sub)` übergeben) |
| `template_for_profil` | `ampel.py:115` | für AC-15-Mail-Kopf |
| `UnifiedWeatherDisplayConfig.ampel` | `src/app/models.py:872` | Kommentar „in S1a ohne Leser“ |
| Migration gelaufen | Issue-Kommentar 2026-11-04 | Prod 12 Dateien; Trips ohne `display_config` fallen beim Lesen auf die Vorlage |

**Bis heute ruft kein Renderer `ampel_for`/`thunder_color`** (einziger Treffer außerhalb `ampel.py`: Kommentar in `models.py`).

## Related Files (Leser, nachgemessen)
| File | Relevanz |
|---|---|
| `src/output/metric_format.py:141` `severity_for`, `:152` `severity_from_thresholds`, `:232` `escalate_pair_watch`, `:311/:319` `thunder_ampel_band` | Einspeisepunkt; `severity_for` liest Katalog (`:148`). **46 Treffer `severity_for`** in metric_format, outlook, helpers, compare_html, html, metric_catalog |
| `src/output/renderers/email/helpers.py` | `ampel_level` (:732/:741), `_ampel_dot_severity` (CAPE :899), `_extreme_ampel_tone` (:1593), Kacheln `build_metrics_summary_pills`/`_pill_for_metric` (direkte Katalog-Nachschläge :1744, :1769, :1794, :1924), `_sms_mention_threshold` (8 Treffer), `ampel_dot`, `ampel_stage_*` |
| `src/output/renderers/email/html.py` | Stundentabelle, `_row_risk`, `_thunder_risk_level` (Dublette), `escalate_pair_watch`-Aufruf |
| `src/output/renderers/email/plain.py`, `compact.py` | `tone_symbol`, `sms_threshold`-Lesestellen |
| `src/output/renderers/email/outlook.py:130/:135` `_catalog_thresholds`, `_THUNDER_LEVEL_BG`, `_metric_column_bg` | Ausblick Trip+Vergleich; Temperatur bisher nie gefärbt (AC-19 b) |
| `src/output/renderers/email/compare_html.py` | `CV2_METRICS`/`HOUR_METRICS` statisch auf Modulebene, `_make_hour_sev` (:460 Katalog), `_sev_thunder`, `profile_signature` (AC-15) |
| `src/output/renderers/comparison.py` | `render_compare_email` → `render_compare_html` (Preset kommt an) |
| `src/output/renderers/alert/hours.py:40` `_stage` → `ampel_level(metric_id, value)` | **Pfad weicht von Spec ab** (Spec: `src/services/alert/`) |
| `src/output/renderers/alert/project.py:317` `_hour_fields`, `:350` `to_alert_message`; `alert/model.py:270` `AlertMessage`; `alert/render.py` | Ampel muss beim Projizieren mitgegeben werden |
| `src/output/tokens/builder.py` (:165 `DEFAULTS`, :215), `tokens/metrics.py:49` `render_threshold_peak_value` (14 Treffer, nur obere Seite) | SMS/Premium-SMS/Telegram „@14“ |
| `src/output/renderers/sms_trip.py`, `src/output/renderers/narrow.py`, `email/thunder_branch.py` | weitere `render_threshold_peak_value`-Aufrufer. **Telegram-Pfad ist `renderers/narrow.py`** (Spec: `telegram/narrow.py`) |
| `src/output/renderers/trip_report.py`, `src/services/trip_report_scheduler.py` | `sms_threshold`-Weitergabe (27 Treffer gesamt in 9 Dateien), Highlights `_compute_highlights` |
| `src/services/trip_command_processor.py` `_BAND_EMOJI` | Gewitter-Dublette Telegram-Emoji |
| `src/app/metric_catalog.py` | `display_thresholds` = Vorgabe „allgemein“; CAPE-Schwellen entfallen |
| `frontend/src/lib/components/shared/corridor-editor/CorridorEditor.svelte`, `CorridorEditorMobile.svelte`, `wertebereicheVergleichSpeicherung.ts` | Wertebereiche-Reiter (geteilt Trip/Vergleich) → nur lesbar (E2) |
| `frontend/src/lib/components/shared/WeatherMetricsTab.svelte:1838-1905`, `weather-metrics-tab/weatherMetricsSavePayload.ts` | SMS-Schwellwert-Regler → nur lesbar; Speicher-Payload darf `sms_threshold` nicht mehr schreiben (aber erhalten) |
| `frontend/src/lib/i18n/messages/{de,en}/wertebereiche.json` | Hinweistext DE/EN |

## Existing Patterns
- **Träger durch die Renderkette:** `dc` (display_config) wird schon bis in html/plain/compact durchgereicht; Vorbild `corridors` → `marks` (`html.py:826/:863`). Naheliegend: `ampel_for(dc)` einmal je Rendern berechnen und als Dict an die Wrapper geben (Wrapper haben teils schon Dict-Varianten: `ampel_dot`, `ampel_stage_*`).
- **Reine Kernfunktion bleibt:** `severity_from_thresholds` ist beidseitig, keine neue Rechnung.
- **Statische Modullisten** im Compare je Rendern neu bauen (AC-20, Zustandsübernahme vermeiden).
- **Gewitter:** eine Abbildung (`thunder_color`), Dubletten rufen sie.

## Dependencies
- Upstream: `app.ampel` (S1a), `app.ampel_templates`, `metric_catalog`, `thunder_scale`, `severity_from_thresholds`.
- Downstream: alle Kanal-Ausgaben; Golden-Fixtures; `tests/tdd/test_issue_811_mode_matrix.py` (Renderer-Commit-Gate); Validatoren `briefing_mail_validator.py`, `email_spec_validator.py`, `radar_alert_mail_validator.py` (Alarm-Mail wird angefasst ⇒ in den E2E-Umfang).
- Tests mit globalen Farb-Erwartungen: 34 Dateien (Liste im Vorgänger-Kontext §3, Spec Test Plan).

## Existing Specs
- `docs/specs/modules/feat_2792_s1_profil_ampel.md` (maßgeblich), `ampel_schwellen_katalog.md`, `ampel_schwellen_renderer.md`, `fix_1491_gewitter_ampelkreis.md`, `fix_1849_ausblick_ampelfarben.md`.

## Risks & Considerations
1. **Umfang:** Spec schätzt ~650 LoC, Richtwert `loc_limit_override` 700. Allein 46 `severity_for`-Aufrufe, 27 `sms_threshold`-Stellen, 34 Testdateien, plus Frontend. In /20 prüfen, ob S1c selbst in zwei PRs (z. B. **S1c-1** Python-Renderer aller Kanäle + Gewitter/CAPE, **S1c-2** Frontend-Sperre E2) geschnitten wird; beide unter derselben Spec, ohne AC-Änderung.
2. **Zwei Spec-Pfade veraltet** (Alarm unter `src/output/renderers/alert/`, Telegram `src/output/renderers/narrow.py`) — reine Pfadkorrektur, keine fachliche Änderung; in /20 im Spec-Changelog nachtragen.
3. **ID-Räume:** `ampel_for` liefert Katalog-IDs (`gust`, `temperature`…). Alarm-Stunden/`AlertMetric` und Compare-Summary-Keys nutzen andere IDs (`wind_gust`, `gust_max_kmh`, `temp_max_c`) — Zuordnung je Leser prüfen, sonst still „allgemein“ bzw. keine Farbe.
4. **`thunder_color`-Signatur** (rohe Ampel statt aufgelöstes Abo) — Trip mit `preset_name=wassersport` ohne `ampel` bekäme „mittel“ orange statt rot (AC-5). In /20 entscheiden.
5. **Byte-Gleichheit „allgemein“ (AC-19)** außer den drei benannten Abweichungen (CAPE, Ausblick-Temperatur, Gewitter-Dubletten). Golden-Fixtures entsprechend einzeln benennen; **keine Ratsche abschwächen**.
6. **E1-Folge:** `sms_threshold` wirkt nicht mehr, bleibt gespeichert; Frontend darf ihn nicht löschen (Read-Modify-Write, ADR-0101).
7. **Renderer-Commit-Gate** blockt Commits an Mail-Dateien bis Modus-Matrix + Validator frisch grün.
8. **Mandantentrennung (AC-2):** Test mit zwei Nutzern über Go-API; Prozess-globaler Zustand (Caches, Modullisten) darf keine Ampel eines Nutzers an einen anderen weitergeben.
9. **Zweisprachigkeit:** neuer Hinweistext nur über Katalog DE/EN; Protokoll-Token unverändert (`tests/test_metric_tokens_eingefroren.py`).
10. **Doku:** `sms_format.md`, `telegram_format.md`, `premium_sms_format.md`, `api_contract.md` (Corridor/`sms_threshold` „ohne Wirkung, erhalten“) gehören zu S1c.

## Analysis

### Type
Feature (dritter Schritt S1c der freigegebenen Spec `feat_2792_s1_profil_ampel.md`). Keine AC wird geändert, die Spec braucht aber Ergänzungen in /30 (siehe unten).

### Befund Träger-Kette (nachgemessen 2026-11-04 @ `8661a1e86`)
- **Kein Farbentscheider bekommt heute das Abo.** Einstiege mit `dc`/Trip: `TripReportFormatter.format_email` (`trip_report.py:65`, Aufrufer `notification_service.py:778`, `preview_service.py:328`), `render_html` (`html.py:792`), `render_plain` (`plain.py:106`), `render_compact` (`compact.py:123`). Vergleich: `render_compare_email(preset)` (`comparison.py:476`) → `render_compare_html(preset)` (`compare_html.py:1660`).
- **19 `severity_for`-Aufrufe:** html 8 (`:225-244`, `:637`), compare_html 8 (`:123-159`, `:441`), helpers 2 (`:726`, `:1717`), outlook 1 (`:460`).
  - Dazu **direkte `display_thresholds`-Zugriffe:** `helpers.py:741, 1593, 1744, 1769, 1794, 1924`, `outlook.py:135`, `compare_html.py:460`.
  - An keiner dieser Stellen ist `dc` im Scope.
- **Durchzureichen (ca. 15–25 Signaturen):**
  - Mail-Tabellen und Werte: `_render_html_table`, `_render_mobile_compact_rows`, `_render_text_table`, `fmt_val`, `_ampel_dot_severity`, `ampel_level`, `_row_risk`.
  - Kacheln: `build_metrics_summary_pills`, `_pill_for_metric`, `_extreme_ampel_tone`, `ampel_stage_tone/_index`.
  - Ausblick: `render_outlook_table`, `_catalog_thresholds` (entfällt), `_metric_column_bg`, `build_outlook_row`. Letztere **läuft im Scheduler** (`trip_report_scheduler.py:3042-3062`) und berechnet die Hintergrundfarbe vor.
- **Compare:** `CV2_METRICS` (`compare_html.py:327`) und `HOUR_METRICS = _build_hour_metrics()` (`:471`) werden beim Import gebaut.
  - Sie werden Funktionen `build_cv2_metrics(ampel)` / `build_hour_metrics(ampel)` und je Rendern neu gebaut (AC-20).
  - Der Compare-ID-Raum ist unkritisch: Die `_sev_*` sind je Katalog-ID fest verdrahtet (`precip_sum` → `precipitation`, `:334`).
- **Highlights** `_compute_highlights` (`trip_report.py:774`) lesen `highlight_threshold`, nicht die Ampel ⇒ **nicht** Teil von S1c. Spec §5 nennt sie; in /30 klarstellen.
- **Alarm:**
  - Kette: `to_alert_message` (`alert/project.py:350`, ohne Abo) → `_hour_fields` (`:317`, Aufrufe `:426/:493`) → `affected_hours` (`hours.py:113`) → `_stage` (`:40`) → `ampel_level` (Katalog).
  - Aufrufer: `notification_service.py:1132`, `validator_render_service.py:260/264`. Der Trip ist dort jeweils verfügbar.
  - Die IDs sind 1:1 Katalog: `_LEVEL_METRICS` (`hours.py:22`) = `wind, gust, precipitation, rain_probability, cape` plus `thunder`.
  - Mail, Telegram und SMS rendern dasselbe `AlertMessage` (`alert/render.py:1537`, `:907`).
  - `radar_alert_service.py:47` baut ein `AlertMessage` ohne Stundenzeilen (unberührt).
- **Kurzkanäle:**
  - Hauptkette: `MetricConfig.sms_threshold` → `trip_report.py:373` → `format_sms(thresholds=)` (`:477`) → `sms_trip.py:666-687` `MetricSpec` → `builder.py:215` `_mk_metric` (`spec.threshold or DEFAULTS`, `:165`) → `render_threshold_peak_value` (`tokens/metrics.py:49`).
  - `render_threshold_peak_value` prüft **nur die obere Seite** (`>=`; `peak<=0 → "-"`).
  - Zweite Kette: Scheduler `sms_thresholds` → `outlook.py:534/698` → `helpers.py:1057-1100`.
  - `_sms_mention_threshold` (`helpers.py:1428`) hat zwei feste Werte:
    - Sicht 2,0 km, entspricht Gelb der Vorlage „allgemein“.
    - Luftfeuchte 90. Luftfeuchte hat in S1 keinen Leser, bleibt also wie heute und wird **nicht** aus der Ampel gefärbt.
  - Symbole: R→precipitation, PR→rain_probability, W→wind, G→gust, TH:/TH+:→thunder.
- **Temperatur in Kurzkanälen (AC-1):**
  - `D`/`L`/`FD`/`FL` zeigen heute nur den Wert (`render_temperature`, `builder.py:366-399`).
  - Die Stunde ist aber vorhanden: `hiking_field_min_max` (`day_window.py:232`) liefert `max_ts`, Telegram nutzt `@{h}` schon. `min_ts` fehlt, ist aber billig zu ergänzen.
  - ⇒ **AC-1 ist wie freigegeben umsetzbar** (`D9@14` nur bei Gelb oder schlechter). Das Vokabular „23@5 = schwelle“ besteht; `sms_code` und `compact_label` bleiben unverändert.
  - Die Form des Bereichs-Tokens `D{min}/{max}` legt /30 fest (technisch, **keine PO-Frage**).
  - `render_threshold_peak_value` bekommt eine Prädikat-Variante (Stufe ≥ gelb, beidseitig) statt der Zahlenschwelle.
- **Gewitter:**
  - `thunder_color(level, ampel)` (`ampel.py:218`) liest nur `ampel["template"]` und ignoriert `preset_name`/`profil` ⇒ **Signatur auf das aufgelöste Objekt umstellen** (`resolve_ampel(sub)`). Heute ruft sie niemand auf.
  - Dubletten heute (keins / leicht / mittel / hoch):
    - `outlook._THUNDER_LEVEL_BG` (`:254`): leer / #fbe6c3 / orange / rot.
    - `outlook._metric_column_bg` (`:441`): wie oben.
    - `html._thunder_risk_level` (`:165`): ok / yellow / watch / risk. Der Zahl-Fallback (`:190-195`) bleibt vor dem Aufruf.
    - `compare_html._sev_thunder` (`:244`): None / gelb / orange / rot.
    - `trip_command_processor._BAND_EMOJI` (`:578`).
  - Keine dieser Stellen beachtet `ampel.thunder`.
  - Ungeprüft sind noch Stellen mit „thunder“ und Farbe in `corridor_mark.py`, `compact.py`, `day_window.py`, `comparison.py`, `design_tokens.py` ⇒ in /40 per grep abschließen.
- **CAPE-Farbe (P1):** entfällt an `helpers._ampel_dot_severity("cape")` (`:711`, Aufruf `:899`), an der Ampel-Spalte `html.py:553/:640` und bei `_AMPEL_CAPABLE_METRIC_IDS` (`:1281`). Die Fusion `metric_format.py:473` bleibt.
- **Wertebereich-Markierung:**
  - `corridor_mark.py` (Leser in `html.py`, `compare_html.py`, `design_tokens.py`) färbt heute nach den `corridors` des Nutzers.
  - Nach ADR-0106 ist die Ampel die einzige Bewertung ⇒ mit dem Umschalten entfällt diese Markierung, sonst gäbe es zwei Bewertungen.
  - In /30 ergänzen (folgt aus ADR-0106/E2, keine AC-Änderung).
- **Frontend (E2):**
  - Es gibt kein readonly-Muster, nur CSS `.ce-effect.disabled` (`CorridorEditor.svelte:628`, `CorridorEditorMobile.svelte:568`).
  - Die SMS-Regler (`WeatherMetricsTab.svelte:~1840-1871`, `data-testid="sms-thresholds"`) lösen `scheduleAutoSave()` aus.
  - **Datenrisiko:**
    - `buildGlobalMetricsForSave` (`weatherMetricsSavePayload.ts:49-71`) schreibt bzw. löscht `sms_threshold` aktiv.
    - Go `mergeConfigMap` (`config_merge.go:11-22`) mischt nur auf einer Ebene; `display_config.metrics` wird als ganze Liste ersetzt ⇒ ein Eintrag ohne `sms_threshold` **löscht** den Wert.
    - `corridors` wegzulassen ist sicher (`trip.go:405`), `[]` löscht.
  - ⇒ Die Sperre muss Bestandswerte unverändert durchreichen und darf sie nie weglassen oder leeren.
  - Tests laufen über `node --test` (`corridor-editor/__tests__/`, `weather-metrics-tab/__tests__/`).

### PO-Hinweis 2026-11-04: Migration unvollständig für Vergleichs-Wertebereiche (PFLICHT vor dem Prod-Deploy des Umschaltens)
- **Befund:** Der Migrationsbericht (Kommentar in #2792 vom 2026-11-04) führt als „nicht zuordenbar“ u. a. `wind_max_kmh`, `visibility_min_m`, `precip_sum_mm`, `sunny_hours_h`, `cloud_avg_pct`, `wind_chill_*`, `pop_max_pct`, `humidity_avg_pct`, `thunder_level_max`, `cape_max_jkg`, `snow_new_sum_cm`.
- **Auf Prod betroffen:** `henning/5f534011`, `cp-ac57aa1e29c65649`, `cp-eb6ba0b239d90e37`, `zillertal-t-glich`.
- **Folge:** Nach dem Umschalten gälte dort die Vorlage statt der Nutzerwerte ⇒ die Farben ändern sich sichtbar.
- **Ergänzung `_ZUORDNUNG`** (`scripts/migrate_2792_profil_ampel.py:39`); die Einheiten sind geprüft (Katalog-Einheit = Schlüssel-Einheit):

  | Vergleichsschlüssel | Ampel-Metrik | Bemerkung |
  |---|---|---|
  | `wind_max_kmh` | `wind` | km/h |
  | `visibility_min_m` | `visibility` | m; wirkt auf der unteren Seite (`von`), Katalog `*_lt` |
  | `precip_sum_mm` | `precipitation` | mm; die Vergleichs-Übersicht färbt die Summe schon heute mit `precipitation` (`compare_html.py:334`) |
  | `pop_max_pct` | `rain_probability` | % |
  | `snow_new_sum_cm` | `fresh_snow` | cm |
  | `wind_chill_*` (min/max) | `wind_chill` | °C; Seitenregel wie `temperature_min/max` |
  | `sunny_hours_h`, `cloud_avg_pct`, `humidity_avg_pct` | `sunshine`, `cloud_total`, `humidity` | nur Daten (in S1 kein Leser) |
  | `thunder_level_max`, `cape_max_jkg` | — | bleiben „nicht zuordenbar“: Gewitter hat keine Zahlengrenzen, CAPE keine Farbe (P1). Vorher prüfen, ob die heutige Corridor-Markierung diese Spalten sichtbar färbt, und im Bericht begründen |

- Die vollständige Schlüsselliste vor /40 aus `compare_html.py:640-660` (Mapping `precip_sum → precip_sum_mm` usw.) und aus dem Probelauf ziehen, nicht nur aus dem Kommentar.
- **Wiederholbarkeit trägt:** Ein erneuter `--execute` ergänzt fehlende Metriken in einer vorhandenen Ampel und überschreibt keine (`_ampel_planen` `:151-161`).
  - Nachlauf auf Staging und Prod: Probelauf → `--execute` → zweiter `--execute` mit „nichts zu tun“, Sicherung als tar.gz.
- **Reihenfolge-Gate:** Der Migrations-Nachlauf auf **Prod** muss **vor** dem Prod-Deploy des Umschalt-PR gelaufen und im Issue berichtet sein.
- **Neuer Migrations-Test:** Vergleichs-Preset mit `wind_max_kmh`, `visibility_min_m`, `precip_sum_mm` → Ampel-Grenzen, zwei Nutzer.

### Affected Files (with changes)
| File | Change | Description | PR |
|---|---|---|---|
| `src/app/ampel.py` | MODIFY | `thunder_color(level, resolved)` auf das aufgelöste Objekt; ggf. Helfer „mindestens gelb“ | S1c-1 |
| `src/output/metric_format.py` | MODIFY | `severity_for` nur noch mit übergebenen Schwellen (bzw. entfällt zugunsten `severity_from_thresholds`); `thunder_ampel_band` bleibt Kern | S1c-1 |
| `src/output/renderers/email/{html,plain,compact,helpers,outlook}.py` | MODIFY | `ampel` keyword-only durchreichen; CAPE-Farbe raus; Gewitter über `thunder_color`; Corridor-Markierung aus | S1c-1 / S1c-4 |
| `src/output/renderers/email/compare_html.py`, `comparison.py` | MODIFY | Listen je Rendern bauen; `profile_signature` zeigt das Vorlagen-Label (AC-15) | S1c-1 / S1c-4 |
| `src/output/renderers/trip_report.py`, `src/services/trip_report_scheduler.py` | MODIFY | Auflösung am Einstieg, `build_outlook_row(ampel=)`; `sms_threshold` wirkt nicht mehr | S1c-1 / S1c-4 |
| `src/output/renderers/alert/{hours,project,model,render}.py`, `src/services/notification_service.py`, `validator_render_service.py` | MODIFY | `AlertMessage` trägt die Ampel, `_stage` liest sie | S1c-1 / S1c-4 |
| `src/output/tokens/{builder,metrics,dto}.py`, `src/output/renderers/{sms_trip,narrow,day_window}.py` | MODIFY | Hervorhebung beidseitig über Prädikat, `DEFAULTS` raus, Temperatur mit `@h` (`min_ts` ergänzen) | S1c-1 / S1c-4 |
| `src/services/trip_command_processor.py` | MODIFY | `_BAND_EMOJI` über `thunder_color` | S1c-4 |
| `scripts/migrate_2792_profil_ampel.py` | MODIFY | `_ZUORDNUNG` ergänzt | S1c-2 |
| `frontend/src/lib/components/shared/corridor-editor/*`, `WeatherMetricsTab.svelte`, `weatherMetricsSavePayload.ts`, `i18n/messages/{de,en}/wertebereiche.json` | MODIFY | Sperre + Hinweis; Bestandswerte unverändert durchreichen | S1c-3 |
| `tests/tdd/test_profil_ampel_leser.py`, `test_sms_hervorhebung_aus_ampel.py`, `test_gewitter_zentrale_abbildung.py`, Ratsche `test_kein_leser_liest_display_thresholds.py`, `frontend/.../altfelder_gesperrt.test.ts` | CREATE | neue Tests | S1c-1 bis S1c-4 |
| ca. 34 bestehende Testdateien (Context-Vorgänger §3) | MODIFY | Erwartungen auf Vorlage „allgemein“; CAPE-Erwartungen mit Begründung entfernt | S1c-4 |
| `docs/reference/{sms_format,telegram_format,premium_sms_format,api_contract}.md` | MODIFY | „@14“ aus der Ampel, Temperatur mit `@h`, `sms_threshold`/`corridors` als „ohne Wirkung, erhalten“ | S1c-4 |

### Scope Assessment
- **Dateien:** ca. 30 Produkt, ca. 40 Test.
- **Geschätzte LoC:** **1000–1300** inkl. Tests. Die Spec-Schätzung von 650 trägt nicht ⇒ Schnitt nötig.
- **Risiko: HOCH.** Gründe:
  - Zentrale Farbentscheidung aller vier Kanäle.
  - Byte-Gleichheit AC-19.
  - Mandantentrennung.
  - Gefahr von Datenverlust beim Speichern im Frontend.

### Technical Approach (Empfehlung)
1. **Träger explizit, kein `ContextVar`.**
   - Am Einstieg einmal `resolved = resolve_ampel(sub)` für Trip oder ComparePreset; ohne Abo `resolve_ampel(None)` = „allgemein“. Die Schwellen (`ampel_for`) werden daraus abgeleitet.
   - Das Objekt geht als **keyword-only Pflichtparameter ohne Default** durch alle internen Funktionen. Ein Default „allgemein“ würde ein vergessenes Durchreichen genau bei Skitouren und Wassersport verdecken.
   - `ContextVar` ist verworfen: versteckter Zustand, `copy_context` im Scheduler (`parallel_fetch.py:153`), und Tests fänden vergessene Stellen nicht.
2. **Ratsche:** Ein AST/grep-Test verbietet in `src/output/**` (inkl. `renderers/alert/**`) jeden `display_thresholds`-Zugriff und jeden `severity_for(`-Aufruf ohne Schwellen. Ausnahmen stehen in einer Whitelist, die nur schrumpfen darf.
3. **Schnitt in vier PRs.** Die Reihenfolge stellt sicher, dass zu keinem Zeitpunkt Kanäle unterschiedlich bewerten (ADR-0095) oder Altfelder still wirkungslos sind (E2).
   - **S1c-1 Durchreichen (byte-gleich):**
     - Ampel-Objekt bis an jede Farbentscheidung, Compare-Listen je Rendern, `AlertMessage` trägt die Ampel, Prädikat-Hervorhebung vorbereitet. Ratsche hier.
     - Die Einstiege übergeben noch `resolve_ampel(None)` ⇒ die Ausgabe bleibt **unverändert**. Golden-Fixtures und Modus-Matrix sichern den großen Signaturumbau ab.
   - **S1c-2 Migration nachziehen:** `_ZUORDNUNG` ergänzen, Test; Probelauf/`--execute`/Wiederholung auf Staging und Prod; Bericht im Issue.
   - **S1c-3 Frontend-Sperre (E2):** darf vor dem Umschalten live gehen. Bis dahin wirken die Werte noch; der Hinweis „deine Werte sind übernommen“ stimmt nach S1c-2.
   - **S1c-4 Umschalten, alle vier Kanäle gleichzeitig:**
     - Einstiege auf das Abo.
     - CAPE ohne Farbe, Gewitter zentral, Corridor-Markierung aus.
     - E1: `sms_threshold` und `DEFAULTS` ohne Wirkung; Temperatur mit `@h`.
     - Die drei AC-19-Abweichungen einzeln benannt; Doku.
     - **Prod-Deploy erst, wenn S1c-2 auf Prod gelaufen ist.**
   - S1c-1, S1c-2 und S1c-3 in beliebiger Reihenfolge, S1c-4 zuletzt.
   - `loc_limit_override` je PR vor /50 setzen. Richtwerte: S1c-1 ~450, S1c-2 ~120, S1c-3 ~150, S1c-4 ~500.
4. **Tests am Entstehungsort:**
   - Je Leser eine Mutationsgegenprobe (Ampel durch Katalog ersetzt) mit Skitouren- oder Wassersport-Abo; bei „allgemein“ wäre sie unsichtbar.
   - Zwei Nutzer (AC-2).
   - Zwei Presets im selben Prozess, in beiden Reihenfolgen (AC-20).
   - Zwei Trips nacheinander für `build_outlook_row`.

### Dependencies
- **Upstream:** `app.ampel` (`resolve_ampel`, `ampel_for`, `thunder_color`), `ampel_templates`, `severity_from_thresholds`, `thunder_ampel_band`, `day_window.hiking_field_min_max`.
- **Downstream:**
  - alle Kanal-Ausgaben und Golden-Fixtures;
  - `tests/tdd/test_issue_811_mode_matrix.py` (Renderer-Commit-Gate);
  - Validatoren für Trip, Compare und Alarm (`briefing_mail_validator.py`, `email_spec_validator.py`, `radar_alert_mail_validator.py`);
  - `tests/test_metric_tokens_eingefroren.py`.

### Spec-Ergänzungen für /30 (keine Änderung an bestehenden ACs, Changelog-Einträge)
- **Pfadkorrekturen:** Alarm liegt unter `src/output/renderers/alert/` (nicht `src/services/alert/`), Telegram unter `src/output/renderers/narrow.py` (nicht `telegram/narrow.py`).
- **Schnitt:** S1c in vier PRs (oben), inkl. Reihenfolge-Gate „Migration vor Umschalt-Deploy“; `Estimated Scope` aktualisieren.
- **Migration:** ergänzte Zuordnung der Vergleichsschlüssel (Tabelle oben) plus neue AC für den Nachlauf. Vorschlag AC-23: Ein Vergleichs-Preset mit `wind_max_kmh`/`visibility_min_m`/`precip_sum_mm` ergibt Ampel-Grenzen; ein zweiter Lauf ändert nichts.
- **Corridor-Markierung** entfällt mit dem Umschalten (folgt aus ADR-0106).
- **Highlights** `_compute_highlights` bleiben unberührt (lesen keine Farbschwelle).
- **`thunder_color`:** Signatur auf das aufgelöste Objekt.
- **Temperatur in Kurzkanälen:** Form `D9@14` bzw. Bereich `D{min}/{max}` mit der Stunde des schlechtesten Werts. Luftfeuchte bleibt ohne Ampel-Leser.

### S1c-1: Einstieg vs. intern (festgelegt in /40, nicht in /50 neu entscheiden)
- **Träger** = das aufgelöste Objekt `resolve_ampel(sub)` (Schlüssel `template/metrics/thunder`). **Falle:** `ampel_for(resolve_ampel(...))` fällt still auf „allgemein" (das aufgelöste Dict hat kein `ampel`/`preset_name`). Schwellen daher über die neue Funktion `app.ampel.schwellen_aus_ampel(ampel, metric_id)`:
  - liefert nur für die 9 heutigen Katalog-Leser (`temperature, wind_chill, wind, gust, precipitation, rain_probability, visibility, uv_index, fresh_snow`) Schwellen aus der Ampel; für Vorlagen-Zeilen ohne heutigen Leser (`dewpoint`, `cloud_*`, `sunshine`, `temperature_night`, `freezing_level`, `snowfall_limit` …) `{}`;
  - **CAPE-Brücke:** `cape` liefert in S1c-1 noch das Katalog-`display_thresholds` (byte-gleich); entfällt in S1c-4 (P1). Die Brücke liegt in `src/app`, damit die Ratsche über `src/output/**` leer bleibt.
- **Einstiege** (haben das Abo als Argument, lösen selbst auf; in S1c-1 fest `resolve_ampel(None)`, Argument ignoriert; **kein** optionaler `ampel=`-Override): `TripReportFormatter.format_email`, `render_html`, `render_plain`, `render_compact`, `render_compare_html`/`render_compare_email`, `build_outlook_row` (`trip_display_config`); im Alarm-Pfad die aufrufenden Services (`notification_service`, `validator_render_service`, `radar_alert_service`).
- **Intern** (keyword-only `ampel`, ohne Default; Signatur-Test `test_profil_ampel_durchreichen.py::test_interne_farbentscheider_verlangen_die_ampel`): `metric_format.severity_for`, `helpers.ampel_level`, `outlook._metric_column_bg`, `outlook.render_outlook_table`, `alert.hours._stage`, `alert.hours.affected_hours`, `alert.project.to_alert_message`, `to_point_alert_message`, `compare_html.build_cv2_metrics`, `build_hour_metrics` (ersetzen `CV2_METRICS`/`HOUR_METRICS`). Alle übrigen Zwischenfunktionen bis zur Farbentscheidung ebenso (Ratsche: kein `severity_for(` ohne `ampel=` in `src/output/**`).
- **`AlertMessage.ampel`**: Feld vorhanden (Test). Bevorzugt `field(kw_only=True)` ohne Default (Python 3.12); 121 Test-Konstruktionen. Ist das im LoC-Budget nicht tragbar, Default `None` nur mit Begründung im Code, und die Projektion setzt es immer.
- **Kurzkanäle vorbereitet, nicht verdrahtet:** `render_threshold_peak_value(..., ampel_stufe=fn)` (fn: Wert → Ampelstufe); hervorgehoben ab Gelb beidseitig, erste Stunde ab Gelb, „Spitze" = schlimmste Stufe; Wert 0 wird nicht verschluckt. `DEFAULTS`/`sms_threshold` wirken in S1c-1 unverändert.
- **Testaufrufer** der internen Funktionen ziehen mit `ampel=resolve_ampel(None)` nach (ca. 87 `severity_for`, 60 `render_outlook_table`, 66 `to_alert_message`, 8 `to_point_alert_message`); keine Ratsche lockern. `loc_limit_override` vor /50 entsprechend realistisch setzen (Test-Churn zählt mit).
- **S1c-4-Pflicht (nachgemessen):** Produktions-Aufrufer reichen das Abo-Argument bereits: `comparison.py:530` `preset=preset`, `trip_report_scheduler.py:3066` `trip_display_config=dc`. In S1c-4 prüfen, dass kein Aufrufer mit Default `None` still auf „allgemein" fällt.

### Open Questions
- [x] AC-1 Temperatur mit Stunde: umsetzbar (`hiking_field_min_max` liefert `max_ts`), keine PO-Frage.
- [x] Träger-Mechanik: explizit, Pflichtparameter.
- [ ] (technisch, /30) Exakte Form des Bereichs-Tokens mit Stunde.
- [ ] (technisch, /40) Färbt die heutige Corridor-Markierung `thunder_level_max`/`cape_max_jkg` sichtbar? Davon hängt der Migrationsbericht ab.
