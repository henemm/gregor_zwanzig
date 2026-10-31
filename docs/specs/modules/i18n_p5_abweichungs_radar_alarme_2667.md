---
entity_id: i18n_p5_abweichungs_radar_alarme_2667
type: module
created: 2026-10-30
updated: 2026-10-31
status: approved
version: "1.1"
tags: [i18n, epic-2644, issue-2667, python, model-haiku]
---

# i18n P5: Abweichungs- und Regen-/Radar-Alarme zweisprachig (alle vier Kanäle)

**Issue:** #2667 · **Epic:** #2644 · **Modell:** Haiku · **Konventionen:** docs/features/epic-i18n-de-en-konventionen.md Abschnitt(e) 2, 4, 6

## Approval

- [x] Approved (PO-Freigabe 2026-10-30)

> **PO-Korrektur 2026-10-31** (ADR-0104 „Präzisierung 2026-10-31“, `docs/features/epic-i18n-de-en.md`, hat Vorrang vor dem Rest dieser Spec): SMS (`render_sms`, `_ADDENDUM_SMS_PREFIX`), Premium-SMS und die kurze Telegram-Tokenform bleiben in **jeder** Sprache exakt wie bisher. Kein `lang` an `render_sms`, keine Katalogschlüssel für den SMS-Text (`alarm.sms.nachtrag_praefix` entfällt), SMS-Ausgabe byte-gleich in de und en — auch das Wochentagskürzel (`@Do15` bleibt). Das Modell trägt deshalb weiter die deutschen Kurzform-Werte (`occurred_weekday`, `onset_weekday`, `shift_text`); die Langform übersetzt sie beim Rendern (Wochentag über `fmt_weekday`, Verschiebung über das neue Feld `OnsetShiftEvent.shift_seconds`). Zweisprachig werden Betreff, E-Mail und der lange Alarm-Telegram-Text (`render_telegram`, `_render_telegram_onset`).

## Purpose

Wer Englisch als Konto-Sprache gewählt hat, bekommt Abweichungs-Alarme (Wetter ändert sich seit dem Briefing) und Regen-/Radar-Alarme in Betreff, E-Mail, Telegram und SMS/Premium-SMS in Betreff, E-Mail und Telegram auf Englisch: Sätze, Wochentage (`Thu`), Tageswörter (`yesterday`, `tomorrow`), Cooldown-Hinweis und die Alarm-Kurzform der Wettergrößen (`Gusts` statt `Böen`). Alle vier Kanäle sagen dasselbe (ADR-0095, Alarm-Parität #1701). Die deutsche Ausgabe bleibt byte-gleich; der SMS-Text ist in jeder Sprache byte-gleich zu heute (PO-Korrektur 2026-10-31).

## Source

- **File:** `src/output/renderers/alert/render.py`, `project.py`, `model.py`, `segments.py`, `src/services/radar_service.py`, `radar_alert_service.py`, `compare_radar_alert.py`, `compare_alert_preview_service.py`, `src/utils/timezone.py`, `src/app/metric_catalog.py`, `.claude/hooks/radar_alert_mail_validator.py`
- **Identifier:** `render_subject`, `render_email`, `render_telegram`, `render_sms` (render.py:1203, 1388, 1528, 1683), `_time_with_day` (274), `_stufe_unit` (62), `_num_raw` (112), `_label`/`_deviation_label` (190/195), `_onset_wann_kopf` (563), `_onset_end_suffix` (603), `_render_telegram_onset` (908), `_ADDENDUM_SMS_PREFIX` (1680), `render_deviation_alert` (1876), `_onset_shift_text` (project.py:212), `_when_fields` (249), `event_end_display` (38), `to_alert_message` (345), `format_alert_location`/`format_segment_reference` (segments.py:91/32), `side_label` (model.py:328), `RadarNowcastService.format_now_text` (radar_service.py:747), `_cooldown_display` (radar_alert_service.py:22), `_format_cooldown_display` (compare_radar_alert.py:99), `format_reference_at` (utils/timezone.py:158), `format_metric_value` (metric_catalog.py:1526)

> **Schicht-Hinweis:** Reiner Python-Core (`src/output/renderers/alert/`, `src/services/`, `src/utils/`, `src/app/`). Kein Go-, kein Frontend-Code. Der Cron-Takt kommt aus Go, die Fälligkeit entscheidet Python; dieses Paket ändert nur Texte und reicht `lang` durch die reinen Funktionen. Die Orchestrierer (`trip_alert.py`, `compare_alert.py`) übergeben `lang` erst mit P9b (#2672).

> **Querschnitts-Prüfpunkte:**
> - **Trip/Ortsvergleich-Teilung:** Der Alarm-Renderer ist schon geteilt (`AlertMessage` für Trip und Ortsvergleich, ADR-0011). Es entsteht kein Compare-Pendant; Texte beider Flächen liegen in `alarm.*`. Geteilte Texte der Zeitangabe (`alarm.zeit.*`) werden nicht dupliziert.
> - **Mandantentrennung:** Reine Funktionen ohne Nutzerdaten-Zugriff und ohne Modul-Zustand; `lang` ist Parameter. AC-7 beweist, dass zwei Aufrufe nacheinander (`en`, `de`) sich nicht beeinflussen. Die Auflösung `resolve_user_lang(user_id)` aus dem Auth-Kontext macht P9b.
> - **Kanäle:** Alarm-Inhalt. Alle vier: E-Mail (`render_email`, `render_subject`), Telegram (`render_telegram`, `_render_telegram_onset`), SMS (`render_sms`) und Premium-SMS (sendet denselben Text wie `render_sms`, siehe Kommentar render.py:1674-1680); beide Alarmarten (Abweichung, Regen/Radar) in Trip und Ortsvergleich.

### Affected Files

| Datei | CREATE/MODIFY | Zweck |
|---|---|---|
| `src/output/renderers/alert/render.py` | MODIFY | `lang: Lang = "de"` (keyword-only) an allen öffentlichen Funktionen (`render_subject`, `render_email`, `render_telegram`, `render_sms`, `render_deviation_alert`) und allen Text erzeugenden Helfern; alle Nutzertexte über `t`/`tn`; `_time_with_day`, `_stufe_unit`, `_num_raw`, `_ADDENDUM_SMS_PREFIX` |
| `src/output/renderers/alert/project.py` | MODIFY | `lang` in `to_alert_message`, `to_multi_point_alert_message`, `to_multi_location_onset_alert_message`, `to_point_alert_message`, `_when_fields`, `event_end_display`, `_onset_shift_text`; `_de_weekday_short` -> `fmt_weekday(..., lang)` an den Stellen 74, 262, 624 |
| `src/output/renderers/alert/model.py` | MODIFY | `side_label(e, lang="de")`; Kommentare „DE-Wochentagskürzel“ -> „Wochentagskürzel“; die internen `cmp`-Werte `"über"`/`"unter"` bleiben (Katalogwerte, kein Nutzertext) |
| `src/output/renderers/alert/segments.py` | MODIFY | `format_segment_reference(segment_ids, lang="de")`, `format_alert_location(..., lang="de")` (`Segment 3`, `N Segmente`, `🏁 Ziel`) |
| `src/output/renderers/alert/hours.py` | unverändert | geprüft 2026-10-30: kein Nutzertext (nur Docstrings); der Hinweis „betroffen HH:MM–HH:MM“ steht in `render.py:1357/1377` |
| `src/services/radar_service.py` | MODIFY | `intensity_text(label, lang)` (DE-Konstante -> Katalogschlüssel); `format_now_text(..., lang="de")` für den Klartext-Zweig; `INTENSITY_*`-Konstanten bleiben UNVERÄNDERT (Vergleichsschlüssel) |
| `src/services/radar_alert_service.py` | MODIFY | `_cooldown_display(trip, lang="de")` und `build_onset_alert_message(..., lang="de")` |
| `src/services/compare_radar_alert.py` | MODIFY | `_format_cooldown_display(cooldown_minutes, lang="de")`; Aufruf Zeile 425 mit `lang` |
| `src/services/compare_alert_preview_service.py` | MODIFY | Aufruf Zeile 173 mit `lang` (Default `de`) |
| `src/utils/timezone.py` | MODIFY | `format_reference_at(..., lang="de")` (`gestern 18:03 Uhr` / `yesterday 18:03`) |
| `src/app/metric_catalog.py` | MODIFY | NUR falls P2/P3 es nicht schon getan haben (vorher Grep `lang` in `format_metric_value`): `format_metric_value(unit, value, *, signed=False, lang="de")`; `en` mit Dezimalpunkt und Tausender-Komma |
| `src/services/weather_change_detection.py`, `deviation_alert_engine.py`, `alert_state.py`, `alert_gate.py`, `compare_alert.py`, `compare_alert_channels.py`, `compare_alert_guard.py` | unverändert (Log-Kommentare) | geprüft 2026-10-30: keine Nutzertexte, nur Kommentare und `logger`-Meldungen; Log-Zeilen mit Umlaut/Signalwort erhalten den Zeilenkommentar `# i18n-log` (Text bleibt deutsch) |
| `src/i18n/messages/de/alarm.json`, `src/i18n/messages/en/alarm.json` | MODIFY | Neue Schlüssel `alarm.*` (nur diese Bereichsdateien anfassen) |
| `.claude/hooks/radar_alert_mail_validator.py` | unverändert | seit PV #2663 sprachfähig (`alarm.radar.*`, `alarm.segment.*` aus dem Katalog, `lang` aus `X-GZ-Lang`); der Renderer benutzt dieselben Schlüssel |
| `tests/fixtures/mail/radar_alert_en.eml` | CREATE | Englische Beispiel-Mail aus dem Renderer-Pfad |
| `tests/golden/abweichungs_radar_alarm/*.de.txt`, `*.de.html`, `*.en.txt`, `*.en.html` | CREATE | Golden `de` VOR der Umstellung (Abweichung Wind, Abweichung Mehrfach, Regen-Alarm Einzelort, Regen-Alarm Bündel, Nachtrag), Referenz `en` |
| `tests/golden/test_alarm_golden.py` | CREATE | Byte-Vergleich `de` (vier Kanäle) |
| `tests/test_alarm_zweisprachig.py` | CREATE | Verhaltenstests der ACs |
| `tests/test_alarm_validator_zweisprachig.py` | CREATE | Radar-Validator gegen `de`- und `en`-Fixture |

## Estimated Scope

- **LoC:** ca. 300 Code (render.py ~150 Aufrufstellen, project.py ~25, radar_service ~45, segments ~15, timezone ~15, Kleinteile ~50); ohne Katalogdaten und Tests. Das überschreitet das Workflow-Limit von 250: `workflow.py set-field loc_limit_override 500` einplanen.
- **Files:** 17 Code-/Katalog-/Validator-Dateien plus Tests und Golden-Dateien
- **Effort:** high für Haiku (`render.py` hat 1.900 Zeilen); bei zweitem Fehlversuch Sonnet

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| #2662 P1 | Paket | `t`, `tn`, `fmt_weekday`, `fmt_time`, `relative_day`, `MetricDefinition.alert_label_for(lang)` |
| #2663 PV | Paket | Header `X-GZ-Lang`, sprachfähiger Radar-Validator-Rahmen |
| #2664 P2 / #2665 P3 | Pakete | `build_origin_footer`/`render_origin_footer_*` in `email/helpers.py` (`_with_origin`, render.py:1335) nehmen `lang` an; P5 ruft sie mit `lang=lang` |
| #2668 P6 | Paket (danach) | `_de_weekday_short` in `official_alerts.py` bleibt dort; P5 benutzt es nicht mehr in `project.py` |
| #2672 P9b | Paket (danach) | `trip_alert.py` (Zeilen 2704-2733 Wochentag, 2871-2880 Nachtrag-Bezug) und `compare_alert.py` rufen die Funktionen mit `lang` auf |
| #2671 P9a | Paket (danach) | `notification_service.py` (Zeilen 1091, 1179, 1259, 1894) reicht `lang` an die Renderer |
| `app.metric_catalog` | Modul | `get_metric`, `get_alert_label` -> `get_metric(id).alert_label_for(lang)` |
| ADR-0104, ADR-0042, ADR-0095 | ADR | Sprache am Nutzer; Alarm-Kurzform ≤ 12 Zeichen; Kanal-Parität |

## Implementation Details

**Katalog-Namensraum:** `alarm` (`src/i18n/messages/{de,en}/alarm.json`). Nur diese beiden Dateien anfassen. das im Glossar verbotene Produktwort ist untersagt (Produktbegriffe: Trip, Etappe, Ortsvergleich, Briefing).

**Signaturen (Abschnitt 4):** `*, lang: Lang = "de"` keyword-only an jeder Funktion, die Text baut oder weiterreicht; kein Modul-Zustand. Beispiele:

```
def render_subject(msg: AlertMessage, *, lang: Lang = "de") -> str
def render_email(msg: AlertMessage, *, lang: Lang = "de") -> tuple[str, str]
def render_telegram(msg: AlertMessage, *, lang: Lang = "de") -> str
def render_sms(msg, limit=140, location_positions=None, addendum=False, *, lang: Lang = "de") -> str
def to_alert_message(changes, segments, trip_name, *, tz, stand_at, ..., lang: Lang = "de") -> AlertMessage
def intensity_text(label: str, lang: Lang) -> str     # radar_service.py, DE-Konstante -> Katalog
```

**Beispiel-Schlüssel (de wörtlich wie heute, en laut Glossar/Konventionen):**

| Schlüssel | de | en | Stelle |
|---|---|---|---|
| `alarm.zeit.gestern` | `gestern {zeit}` | `yesterday {zeit}` | `_time_with_day`, render.py:293 |
| `alarm.zeit.vor_tagen` | `vor {n} Tagen {zeit}` | `{n} days ago {zeit}` | render.py:295 |
| `alarm.zeit.morgen` | `morgen {zeit}` | `tomorrow {zeit}` | render.py:297 |
| `alarm.zeit.in_tagen` | `in {n} Tagen {zeit}` | `in {n} days {zeit}` | render.py:299 |
| `alarm.zeit.seit` | `seit` | `since` | `past_word` Vorgabe, render.py:276 |
| `alarm.zeit.war` | `war` | `was` | render.py:321 |
| `alarm.einheit.stufe.one` / `.other` | `Stufe` / `Stufen` | `level` / `levels` | `_stufe_unit`, render.py:66 |
| `alarm.betreff.aenderungen` | `{n} Änderungen seit dem Briefing` | `{n} changes since the briefing` | render.py:1227 |
| `alarm.betreff.ueber_schwelle` | `{n} über Schwelle: {liste}` | `{n} over threshold: {liste}` | render.py:1238 |
| `alarm.mail.h1_mehrere` | `{n} Werte über der Alarm-Schwelle` | `{n} values above the alert threshold` | `_h1`, render.py:1250 |
| `alarm.mail.stand_vergleich` | `Stand: heute {stand} · verglichen mit {referenz}` | `As of today {stand} · compared with {referenz}` | render.py:1411 |
| `alarm.mail.referenz_letztes_briefing` | `dem letzten Briefing` | `the last briefing` | render.py:1413 |
| `alarm.mail.wo_wann` | `Wo & wann` | `Where & when` | `_datablock_single`, render.py:1301 |
| `alarm.regen.betreff_buendel` | `Regen-Alarm: {n} Orte` | `Rain alert: {n} locations` | render.py:515 |
| `alarm.regen.laeuft_bereits` | `läuft bereits` | `already ongoing` | `_onset_wann_kopf`, render.py:571 |
| `alarm.regen.in_minuten` | `in {min} Min` | `in {min} min` | render.py:584 |
| `alarm.regen.ende_untergrenze` | ` · Regen mindestens bis {zeit}` | ` · rain until at least {zeit}` | `_onset_end_suffix`, render.py:638 |
| `alarm.regen.ende_bekannt` | ` · letzter Regen gegen {zeit}` | ` · last rain around {zeit}` | render.py:639 |
| `alarm.regen.cooldown` | `Cooldown: Du erhältst diese Warnung höchstens einmal in {dauer}. Bei Meldungen aus anderen Quellen (amtliche Warnung/Radar) greift dieser Cooldown nicht.` | `Cooldown: you receive this alert at most once every {dauer}. Alerts from other sources (official warning/radar) are not affected by this cooldown.` | render.py:776, 861 |
| `alarm.dauer.stunden.one` / `.other` | `{count} Stunde` / `{count} Stunden` | `{count} hour` / `{count} hours` | `_cooldown_display`, radar_alert_service.py:27 |
| `alarm.dauer.minuten.other` | `{count} Minuten` | `{count} minutes` | radar_alert_service.py:28 |
| `alarm.intensitaet.stark` | `Starker Regen` | `Heavy rain` | `INTENSITY_HEAVY`, radar_service.py:171 |
| `alarm.nachtrag.amtlich` | `Ergänzung zur amtlichen Warnung` | `Addendum to the official warning` | trip_alert.py:2874 (Aufruf P9b) |
| `alarm.nachtrag.abweichung` | Nachtrag Abweichungs-Alarm | Follow-up deviation alert | P9b |
| `alarm.nachtrag.von` | Nachtrag von {zeit} | Follow-up from {zeit} | P9b |
| ~~`alarm.sms.nachtrag_praefix`~~ | entfällt (PO-Korrektur 2026-10-31: SMS unverändert) | | |
| `alarm.segment.ziel` (Bestand aus PV #2663) | `Ziel` | `Destination` | `format_segment_reference` setzt `🏁 {ziel}`; der Radar-Validator liest denselben Schlüssel |

Weitere Schlüssel nach demselben Muster: die übrigen `INTENSITY_*`-Stufen (`Starker Hagel/Gewitter` -> `Heavy hail/storm`, `Gewitter` -> `Thunderstorm`, `Mäßiger Regen` -> `Moderate rain`, `Leichter Regen` -> `Light rain`, `Kein Niederschlag` -> `No precipitation`), Beginn-Verschiebung (`{label}-Beginn verschiebt sich` -> `{label} onset is shifting`, `{n} Beginn-Zeiten verschieben sich` -> `{n} onset times are shifting`, `{betrag} h früher/später` -> `{betrag} h earlier/later`), `Gewitter ungeprüft` -> `thunderstorm check not done`, `Ausdehnung unvollständig gemessen` -> `extent only partly measured`, `Radar reicht bis {zeit}` -> `radar covers until {zeit}`, `Ortsangabe ab {zeit} unscharf` -> `location is imprecise from {zeit}`, `betroffen {von}–{bis}` -> `affected {von}–{bis}`, `Bis jetzt`/`Ab jetzt` -> `So far`/`From now`, `Segment {liste}` -> `Segment {liste}`, `{n} Segmente` -> `{n} segments`, `Wetter ändert sich seit dem Briefing` -> `Weather is changing since the briefing`, `unter Schwelle` -> `below threshold`, `Änderung` -> `Change`, `Schwelle` -> `Threshold`, `über`/`unter` (aus `side_label`) -> `above`/`below`.

**Alarm-Kurzform:** `_label(e)` (render.py:190) ruft statt `get_alert_label(e.metric_id)` das Register: `get_metric(e.metric_id).alert_label_for(lang)`. Die Werte `alert_label_en` trägt P1 (z. B. `gust` -> `Gusts`, `precipitation` -> `Precip`, alle ≤ 12 Zeichen). `_code(e)` (SMS-Code) bleibt unverändert.

**Beispiel-Umstellung 1 (render.py:274-302, `_time_with_day`), vorher:**

```
def _time_with_day(hhmm, day_offset=0, is_past=False, *, past_word="seit"):
    if day_offset == -1:
        tag = f"gestern {hhmm}"
    elif day_offset < -1:
        tag = f"vor {-day_offset} Tagen {hhmm}"
    ...
    return f"{past_word} {tag}" if is_past else tag
```

**nachher** (der String-Parameter `past_word` wird ein Schlüssel `past_key`, weil kein dynamischer Schlüsselbau erlaubt ist; der Aufrufer in Zeile 319 übergibt `past_key="alarm.zeit.war"`):

```
def _time_with_day(hhmm, day_offset=0, is_past=False, *, past_key="alarm.zeit.seit", lang: Lang = "de"):
    if day_offset == -1:
        tag = t("alarm.zeit.gestern", lang, zeit=hhmm)
    elif day_offset < -1:
        tag = t("alarm.zeit.vor_tagen", lang, n=-day_offset, zeit=hhmm)
    ...
    return f"{t(past_key, lang)} {tag}" if is_past else tag
```

**Beispiel-Umstellung 2 (project.py:262, Wochentag), vorher:** `weekday = _de_weekday_short(local_dt(target_utc, tz)) if offset else None`. **nachher:** `weekday = fmt_weekday(local_dt(target_utc, tz), lang) if offset else None`, mit `_when_fields(target_utc, now_utc, tz, *, lang="de")`. Gleiches Muster Zeile 74 (`event_end_display`) und 624. Der Import `from .official_alerts import _de_weekday_short` (project.py:23) entfällt. Das Modell speichert weiterhin fertige Strings (`occurred_weekday`, `onset_weekday`), nur eben in der Nutzersprache.

**Beispiel-Umstellung 3 (radar_alert_service.py:22-28, Plural), vorher:**

```
if cooldown_min % 60 == 0:
    n = cooldown_min // 60
    return f"{n} Stunde" if n == 1 else f"{n} Stunden"
return f"{cooldown_min} Minuten"
```

**nachher:** `return tn("alarm.dauer.stunden", n, lang)` bzw. `tn("alarm.dauer.minuten", cooldown_min, lang)`.

**Zahlenformat:** `_num_raw` (render.py:112) und `format_metric_value` (metric_catalog.py:1526) formatieren heute mit deutschen Trennern (`12.240 m`, `1,5 mm`). Für `en` gilt Dezimalpunkt und Tausender-Komma (`12,240 m`, `1.5 mm`), sonst liest ein englischer Nutzer `12.240` als 12,24. Für `de` bleibt alles byte-gleich. (ADR-0104 Nr. 6: Dezimaltrennzeichen Punkt; die SMS-Token verwenden schon Punkt und Ganzzahlen und bleiben.)

**Intensität:** `OnsetEvent.intensity_label` und `NowcastResult.intensity_label` behalten die deutsche Konstante (sie ist Vergleichsschlüssel in `alert_urgency.py:60-62`, `rain_extent.py:38-43`, `trip_report_scheduler.py:2411`). Angezeigt wird `intensity_text(label, lang)`; render.py importiert `radar_service` lazy per Modulreferenz wie schon in `_onset_wann_kopf` (render.py:576). Der Pfad `format_now_text(..., englisch=True)` (Kurzform, #2417) bleibt unverändert; `lang` wirkt nur im nicht-englisch-Zweig.

**Nicht ändern:** `_stage_prefix` (`S5 `), SMS-Token (`TH:M->H`, `Rest3@15`, `@Thu15` nur das Kürzel selbst folgt `fmt_weekday`), `km`-Spannen, `LEVELS`, `_sms_hail_suffix`, Unit-Strings (`km/h`, `°C`), `msg.trip_short`, Orts- und Trip-Namen, `cmp`-Werte, alle `logger`-Texte.

**Allowlist-Eintrag, der entfällt:** In `tests/fixtures/i18n_python_allowlist.json` (Ratsche P11) die Präfixe `src/output/renderers/alert/render.py`, `.../alert/project.py`, `.../alert/model.py`, `.../alert/segments.py`, `src/services/radar_service.py`, `src/services/radar_alert_service.py`, `src/services/compare_radar_alert.py` entfernen. Existiert die Datei zu diesem Zeitpunkt noch nicht (vorher `Glob tests/fixtures/i18n_python_allowlist.json`), entfällt der Schritt und P11 holt ihn nach.

**Golden-Fixture:** Deterministisch (feste Zeit `2026-10-29T06:00+02:00`, Nutzer `golden-de`, festes Wetter): Abweichung Wind einzeln (Einzel-Event, `Do`-Wochentag mit Versatz), Abweichung mit drei Metriken, Regen-Alarm einzeln, Regen-Alarm Bündel (zwei Orte), Nachtrag. Je Fall E-Mail (HTML + Klartext), Betreff, Telegram, SMS. **Zuerst** die `*.de.*`-Dateien mit unverändertem Code erzeugen und committen, danach umstellen.

**Validator:** `radar_alert_mail_validator.py` bildet `_INTENSITY_LABELS`, das Segmentmuster (`Segment`, `Ziel` -> `Finish`) und den Cooldown-Satz (`höchstens einmal in` -> `at most once every`) aus `t(key, lang)`; `lang` kommt aus `X-GZ-Lang`. Staging-Lauf in beiden Sprachen führt `/e2e-verify` aus.

**Token-Wächter:** `tests/test_metric_tokens_eingefroren.py` bleibt grün; `sms_code`, `compact_label`, `col_label` werden nicht angefasst.

**Pflicht für den Developer-Agenten:** (1) RED-Tests der ACs grün, (2) deutsche Golden-Ausgabe byte-gleich, (3) Allowlist-Eintrag entfernen, (4) Paritäts- und Ratschen-Test grün, (5) keine Änderung an `col_label`/`compact_label`/`sms_code`/Kürzeln. Nicht tun: andere Bereichsdateien ändern, Schlüssel umbenennen, deutsche Texte „verbessern“, neue Abhängigkeiten.

## Expected Behavior

- **Input:** `AlertMessage` (Abweichung oder Radar-Onset) bzw. die Projektions-Eingaben (`changes`, `segments`, `now_utc` …) plus `lang` (`"de"`/`"en"`, Default `"de"`).
- **Output:** Betreff, E-Mail (HTML/Klartext), Telegram-Text, SMS-/Premium-SMS-Text in der gewählten Sprache. `de`: byte-gleich zu heute. `en`: englische Sätze und Tageswörter, Wochentag `Thu`, Alarm-Kurzform laut Register (`Gusts`), Cooldown-Satz englisch, Zahlenformat englisch; SMS-Token, Kürzel, Einheiten und Namen unverändert; SMS-Länge ≤ übergebenes Limit (140).
- **Side effects:** Keine. Beim Fehlen eines englischen Schlüssels fällt der Kern auf Deutsch zurück und loggt einmal (`i18n fallback`); der Paritätstest verhindert das im Repo.

## Acceptance Criteria

- **AC-1:** Given ein Abweichungs-Alarm für Böen bei Sprache `en` mit Ereigniszeit an einem anderen Tag (Donnerstag) / When Betreff, E-Mail und Telegram-Text gerendert werden / Then sind Sätze englisch, die Alarm-Kurzform lautet `Gusts`, der Wochentag `Thu`, und der Text enthält kein deutsches Katalogwort.
  - Test: tests/test_alarm_zweisprachig.py — rendert die Fixture mit `lang="en"` und prüft über `t(key, "en")` und `get_metric("gust").alert_label_for("en")` (keine Literale) sowie einen Scan auf deutsche Katalogwerte.

- **AC-2:** Given Sprache `de` / When alle fünf Golden-Fälle über E-Mail, Betreff, Telegram und SMS gerendert werden / Then ist jede Ausgabe byte-gleich zu den vorab eingecheckten `*.de.*`-Dateien, einschließlich der Kurzform `Do15` und der deutschen Zahlenformate.
  - Test: tests/golden/test_alarm_golden.py — Byte-Vergleich je Fall und Kanal.

- **AC-3:** Given ein Regen-Alarm (Einzelort und Bündel aus zwei Orten) bei Sprache `en` und einem Cooldown von 60, 120 und 90 Minuten / When E-Mail, Telegram und SMS gerendert werden / Then stehen `1 hour`, `2 hours` und `90 minutes` im Cooldown-Satz, die Intensität lautet `Heavy rain`, und das Bündel heißt `Rain alert: 2 locations`.
  - Test: tests/test_alarm_zweisprachig.py — Plural-Fälle über `tn`, Bündel-Betreff, Intensität über `intensity_text`.

- **AC-4:** Given Sprache `en` / When die SMS eines Abweichungs- und eines Regen-Alarms mit Tagesversatz gerendert wird / Then ist der SMS-Text in jeder Sprache byte-gleich zu heute (PO-Korrektur 2026-10-31; auch das Wochentagskürzel `Do` bleibt), und die Länge liegt bei höchstens 140 Zeichen.
  - Test: tests/test_alarm_zweisprachig.py — vergleicht die SMS aller Golden-Fälle in `de`/`en` byte-genau mit der deutschen Golden-SMS und prüft die Länge, auch bei Kürzung durch das Limit.

- **AC-5:** Given Sprache `en` und die Intensitäts-Konstanten des Radar-Dienstes / When die Dringlichkeit eines Regen-Alarms berechnet wird / Then bleibt das Ergebnis von `urgency_from_radar` für `de` und `en` gleich (die Logik hängt nicht an der angezeigten Sprache), und `format_now_text(..., englisch=True)` liefert unverändert den bisherigen Kurzform-Text.
  - Test: tests/test_alarm_intensitaet_logik_unveraendert.py — Dringlichkeit für alle fünf Intensitätsstufen in beiden Sprachen; Byte-Vergleich des Kurzform-Textes.

- **AC-6:** Given die Beispiel-Mails `radar_alert_en.eml` (Header `X-GZ-Lang: en`) und die deutsche Radar-Alarm-Mail (Header `de`) / When `radar_alert_mail_validator.py` läuft / Then endet jeder Lauf mit Exit 0; mit vertauschtem Header (englischer Inhalt, Header `de`) endet er mit Exit ungleich 0.
  - Test: tests/test_alarm_validator_zweisprachig.py — ruft `validate_message` auf beiden Fixtures und dem Fehlfall auf.

- **AC-7:** Given zwei aufeinanderfolgende Render-Aufrufe für zwei Nutzer, erst `en`, dann `de`, mit derselben Fixture / When die Ergebnisse verglichen werden / Then ist das zweite Ergebnis byte-gleich zur Golden-`de`-Ausgabe (kein Zustand zwischen Nutzern), und das erste enthält keinen deutschen Katalogtext.
  - Test: tests/test_alarm_zweisprachig.py — Reihenfolge `en`, `de`, `en` über alle vier Kanäle.

## Known Limitations

- `trip_alert.py` (Wochentag Zeilen 2704-2733, Nachtrag-Bezug Zeilen 2871-2880) und `notification_service.py` rufen die Renderer erst mit P9a/P9b mit `lang` auf; bis dahin sendet das System weiter deutsch. Die Schlüssel `alarm.nachtrag.*` legt dieses Paket an.
- Amtliche Warnungen (`official_alerts.py`) sind P6; die Ergänzung „zur amtlichen Warnung“ ist nur der Bezugssatz, nicht der Warntext.
- Annahme: `OnsetEvent.intensity_label` bleibt die deutsche Konstante als Vergleichsschlüssel; die Anzeige übersetzt `intensity_text`. Eine Umstellung der Konstanten selbst würde `alert_urgency.py` und `rain_extent.py` brechen.
- ~~Annahme: Das Wochentagskürzel folgt auch in der SMS/Premium-SMS der Nutzersprache.~~ Überholt durch PO-Korrektur 2026-10-31: die SMS bleibt in jeder Sprache unverändert (`Do15`).
- Die Langform eines Abweichungs-Alarms nennt keinen Wochentag, sondern Tageswörter (`tomorrow 15:00`); der Wochentag `Thu`/`Fri` erscheint in der Langform nur in der Regen-Alarm-Kopfzeile jenseits der Güte-Grenze (`from Fri15:40`). AC-1 prüft den Wochentag deshalb dort.
- `format_now_text` (Klartext-Zweig) bleibt unverändert: einziger Aufrufer ist der Inbound-Befehl `/jetzt` (P10 #2673), kein Alarm-Pfad.
- `render_deviation_alert` (Kompat-Shim, nur Bestandstests): Kopf, Fußzeile und Zahlen folgen `lang`; Metrikname und Segment-Bezug (`build_segment_label`, E-Mail-Helfer) bleiben deutsch.
- Annahme: `format_metric_value` wird nur ergänzt, wenn P2/P3 es nicht schon sprachfähig gemacht haben; der Default `de` bleibt byte-gleich.
- Annahme: `src/utils/timezone.py::format_reference_at` gehört wegen `reference_at` im Alarm-Modell zu diesem Paket.
- Annahme: `_stage_prefix` (`S5 `) bleibt (Kürzel, in beiden Sprachen verständlich).
- Log-Zeilen bleiben deutsch, tragen bei Umlaut/Signalwort den Kommentar `# i18n-log`.

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** ADR-0104 (zusätzlich ADR-0042 für Alarm-Kurzform und Token, ADR-0095 für Kanal-Parität)
- **Rationale:** Die Sprache ist eine Nutzereigenschaft und wird in die reinen Renderer gereicht; Vergleichsschlüssel und Protokoll-Token bleiben, damit Dringlichkeitslogik und SMS-Grammatik stabil sind.

## Changelog

- 2026-10-30: Initial spec created (Planung Epic #2644)
- 2026-10-31: PO-Korrektur (SMS in jeder Sprache unverändert): AC-4 angepasst, `alarm.sms.nachtrag_praefix` gestrichen; Ziel-Wort aus Bestandsschlüssel `alarm.segment.ziel` (Validator-Gleichlauf).
