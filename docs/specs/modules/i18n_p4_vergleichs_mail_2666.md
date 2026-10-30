---
entity_id: i18n_p4_vergleichs_mail_2666
type: module
created: 2026-10-30
updated: 2026-10-30
status: draft
version: "1.0"
tags: [i18n, epic-2644, issue-2666, python, model-haiku]
---

# i18n P4: Ortsvergleich-Mail (HTML, Klartext, Telegram, SMS) zweisprachig

**Issue:** #2666 · **Epic:** #2644 · **Modell:** Haiku · **Konventionen:** docs/features/epic-i18n-de-en-konventionen.md Abschnitt(e) 2, 4, 6 (und 9 für die Reihenfolge)

## Approval

- [ ] Approved

## Purpose

Wer einen Ortsvergleich abonniert hat und Englisch als Konto-Sprache gewählt hat, bekommt die Vergleichs-Mail (HTML und Klartext) sowie die Ortsvergleich-Nachrichten für Telegram und SMS in englischer Sprache: Überschriften, Zeilenbeschriftungen der Übersicht, Legende, Fußzeile und Hinweise. Die englischen Kurzformen der Stundentabelle (`col_label`, ADR-0042/0068) bleiben unverändert. Die deutsche Ausgabe bleibt byte-gleich zur heutigen Mail (Golden).

## Source

- **File:** `src/output/renderers/email/compare_html.py`, `src/output/renderers/comparison.py`, `src/services/day_comparison.py`, `src/output/renderers/compare_metric_catalog.py`, `src/output/renderers/channel_layout.py`, `src/app/thunder_scale.py`, `src/output/metric_format.py`, `.claude/hooks/email_spec_validator.py`
- **Identifier:** `render_compare_html`, `_render_header` (Zeile 1341), `_render_legend` (1500), `_render_abo_footer` (1549), `_render_app_footer` (1572), `_warn_short` (558), `derive_row_labels` (467), `OUTLOOK_HEADING` (1237), `render_compare_email` (comparison.py:440), `render_comparison_text` (147), `render_compare_telegram` (715), `render_compare_sms` (998), `summarize_day_comparison` (day_comparison.py:156), `get_compare_metric_catalog` (compare_metric_catalog.py:364), `format_hail_note` (thunder_scale.py:42), `thunder_signal_label` (thunder_scale.py:136)

> **Schicht-Hinweis:** Reiner Python-Core (`src/output/renderers/`, `src/services/`, `src/app/`, `src/i18n/`). Kein Go-, kein Frontend-Code. Der Ort des Aufrufers ist `send_one_compare_preset` in `src/services/scheduler_dispatch_service.py:460` (Zeilen 648, 720, 727) und `src/services/compare_preview_service.py` (Zeilen 59-152); **dort wird `lang` erst in P9b (#2672) durchgereicht**, P4 liefert nur die `lang`-fähigen Render-Funktionen mit Default `"de"`.

> **Querschnitts-Prüfpunkte:**
> - **Trip/Ortsvergleich-Teilung:** Die geteilten Bausteine bleiben geteilt. Zeilenbeschriftung kommt wie im Trip aus dem Register über `derive_row_labels` (`metric.label(lang)`, `aggregation_label(aggregation, lang)`), nicht aus einer Compare-Kopie. Texte, die Trip und Ortsvergleich identisch brauchen (z. B. Hinweis „gewählte Wettergrößen ohne Wert“ in `channel_layout.py`), liegen in `allgemein.*`; compare-eigene Texte (Übersicht, Abo-Fuß, Kopfzeile) in `vergleich.*`. Kein neuer Trip-/Compare-Doppelbaustein.
> - **Mandantentrennung:** Die Renderer sind reine Funktionen ohne Nutzerdaten-Zugriff und ohne Modul-Zustand. Die Sprache kommt als Parameter; AC-6 beweist, dass zwei aufeinanderfolgende Aufrufe (`en`, dann `de`) sich nicht beeinflussen. Die Auflösung `resolve_user_lang(user_id)` mit `user_id` aus dem Auth-Kontext macht P9b.
> - **Kanäle:** Briefing-Inhalt des Ortsvergleichs. Alle vier Kanäle: E-Mail (HTML und Klartext, dieses Paket), Telegram (`render_compare_telegram`, dieses Paket), SMS (`render_compare_sms`, dieses Paket) und Premium-SMS (sendet denselben SMS-Text wie `render_compare_sms`, siehe `scheduler_dispatch_service.py:718-732`, und ist damit abgedeckt). Gleicher Inhalt, kanalgerechte Form; Kürzel und GSM-7-Regeln der SMS bleiben.

### Affected Files

| Datei | CREATE/MODIFY | Zweck |
|---|---|---|
| `src/output/renderers/email/compare_html.py` | MODIFY | Alle Nutzertexte über `t(..., lang)`; `lang`-Parameter an `render_compare_html` und allen `_render_*`-Funktionen; `<html lang>` und `<title>` |
| `src/output/renderers/comparison.py` | MODIFY | `lang` an `render_compare_email`, `render_comparison_text`, `render_compare_telegram`, `render_compare_sms`; `_PLAIN_ROWS`/`_DAILY_PLAIN_ROWS`: deutsches Label wird Katalog-Schlüssel |
| `src/output/renderers/channel_layout.py` | MODIFY | `telegram_metric_notice` und `selection_gap_notice` bekommen `lang: Lang = "de"` (keyword-only) |
| `src/app/thunder_scale.py` | MODIFY | Quelle der Gewitter-Wörter (Domänenschicht, #2176): `lang`-fähige Varianten `thunder_label(level, lang)`, `thunder_signal_label(name, lang="de")` (Zeile 136), `format_hail_note(hail_flag, lang="de")` (Zeile 42); `THUNDER_LABEL_DE` bleibt unverändert erhalten |
| `src/output/metric_format.py` | MODIFY | Re-Export der neuen Funktionen aus `thunder_scale.py`; neu `precip_type_label(value, lang)` neben `PRECIP_TYPE_LABEL_DE` (Zeile 297, bleibt unverändert) |
| `src/i18n/format.py` | MODIFY | Ergänzung `fmt_date_numeric(d, lang)` (de `29.10.2026`, en `29 Oct 2026`) neben den Funktionen aus P1 |
| `src/services/day_comparison.py` | MODIFY | `summarize_day_comparison(..., *, lang="de")`, `_DIRECTION_WORDS` und Satzbau über Katalog |
| `src/output/renderers/email/html.py` | MODIFY | Nur der Aufruf in Zeile ~1464: `summarize_day_comparison(..., lang=lang)` (eine Zeile, `lang` existiert dort seit P2) |
| `src/output/renderers/email/plain.py` | MODIFY | Nur der Aufruf in Zeile ~185: `summarize_day_comparison(..., lang=lang)` (eine Zeile, `lang` existiert dort seit P3) |
| `src/output/renderers/compare_metric_catalog.py` | MODIFY | `get_compare_metric_catalog` liefert zusätzlich `label_en`, `aggregation_label_en` (nur additiv, Wirkung auf `de` null) |
| `src/i18n/messages/de/vergleich.json` | MODIFY | Neue Schlüssel `vergleich.*` (deutsch = heutiger Wortlaut) |
| `src/i18n/messages/en/vergleich.json` | MODIFY | Gleiche Schlüsselmenge, englischer Text |
| `src/i18n/messages/de/allgemein.json` | MODIFY | Nur die Schlüssel `allgemein.hinweis.gewaehlt_ohne_wert.*` und `allgemein.hinweis.telegram_limit.*` (de) |
| `src/i18n/messages/en/allgemein.json` | MODIFY | Gleiche Schlüsselmenge (en) |
| `docs/reference/i18n_glossar.md` | MODIFY | Nur anhängen: Stundenverlauf = hourly view, Abo = subscription, Übersicht = overview |
| `.claude/hooks/email_spec_validator.py` | MODIFY | Erwartungen (`_OVERVIEW_WARN_LABEL` Zeile 503, „Metrik“ Zeile 754, „Zeit“ Zeilen 575/795/857) aus `t(key, lang)`; `lang` aus Header `X-GZ-Lang` (Gerüst aus PV #2663) |
| `tests/fixtures/mail/compare_mail_en.eml` | CREATE | Englische Beispiel-Mail aus dem Renderer-Pfad (Validator-Fixture) |
| `tests/golden/vergleichs_mail/ortsvergleich_3orte.de.html`, `.de.txt`, `.en.html`, `.en.txt` | CREATE | Golden `de` (VOR der Umstellung erzeugen!) und Review-Referenz `en` |
| `tests/golden/vergleichs_mail/telegram_sms.de.txt`, `telegram_sms.en.txt` | CREATE | Golden Telegram und SMS (je eine Datei mit beiden Texten, getrennt durch `----`) |
| `tests/golden/test_vergleichs_mail_golden.py` | CREATE | Vergleicht `de` byte-genau, prüft `en` gegen die Referenz |
| `tests/test_vergleichs_mail_zweisprachig.py` | CREATE | Verhaltenstests der ACs 1, 2, 4, 6 |
| `tests/test_tagesvergleich_zeile_zweisprachig.py` | CREATE | Verhaltenstest AC-5 (Vortag-Zeile) |
| `tests/test_vergleichs_mail_validator_zweisprachig.py` | CREATE | Validator-Lauf gegen die `.eml`-Fixtures in beiden Sprachen |

`src/services/comparison_scoring.py` wird **nicht** geändert: die Datei enthält nur `calculate_score(...) -> int` und keine Nutzertexte (verifiziert 2026-10-30). Der Satz „Bewertungstexte“ im Issue trifft die Datei nicht.

## Estimated Scope

- **LoC:** ca. 290 Code (compare_html ~110, comparison ~90, thunder_scale/metric_format ~30, day_comparison ~30, channel_layout ~15, format ~10, Rest Einzeiler); ohne Katalogdaten und Tests. Das überschreitet das Workflow-Limit von 250: `workflow.py set-field loc_limit_override 500` einplanen.
- **Files:** 17 Code-/Katalog-/Hook-Dateien (davon 5 Test- und Fixture-Dateien sowie 5 Golden-Dateien zusätzlich)
- **Effort:** high für Haiku (große Dateien, viele Einzelstellen); bei zweitem Fehlversuch Sonnet (Workflow-Regel)

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| #2662 P1 | Paket | `src/i18n` (`t`, `tn`, `fmt_weekday`, `fmt_date`), `MetricDefinition.label(lang)`, `aggregation_label(aggregation, lang)`, Token-Wächter |
| #2663 PV | Paket | Marker `X-GZ-Lang`, sprachfähiger `email_spec_validator.py` |
| #2664 P2, #2665 P3 | Pakete | `lang` in `html.py`/`plain.py` und in den geteilten Hinweis-Bausteinen (`outlook_state_hint`, `undelivered_hint`, `unavailable_hint`, `command_block`, `profile_signature`, `helpers`); P4 ruft sie mit `lang=lang` auf |
| #2672 P9b | Paket (danach) | Reicht `lang` aus `send_one_compare_preset` und `compare_preview_service` durch |
| #2668 P6 | Paket (danach) | Amtliche Warnblöcke (`render_warn_block`, `render_official_alerts_html`, `_LEVEL_WORDS`) werden dort zweisprachig; bis dahin bleiben sie deutsch (Known Limitations) |
| `app.metric_catalog` | Modul | `get_metric`, `aggregation_label_de` -> `aggregation_label` |
| `output.renderers.email.profile_signature` | Modul | `profile_signature(profile)` (Eyebrow, P3 macht ihn sprachfähig) |
| ADR-0104, ADR-0042, ADR-0068 | ADR | Sprache am Nutzer; Kurzform ist Platzform; Spaltenköpfe bleiben |

## Implementation Details

**Katalog-Namensraum:** `vergleich` (Dateien `src/i18n/messages/{de,en}/vergleich.json`). Nur für die zwei geteilten Hinweise `allgemein` (`allgemein.json`). Andere Bereichsdateien nicht anfassen. das im Glossar verbotene Produktwort ist untersagt.

**Signaturen (Konvention Abschnitt 4):** Jede Render-Funktion bekommt `*, lang: Lang = "de"` (keyword-only, Default bewahrt Alt-Aufrufer):

```
def render_compare_html(result, *, ..., lang: Lang = "de") -> str
def render_compare_email(result, *, ..., lang: Lang = "de") -> tuple[str, str]
def render_comparison_text(result, profile=None, enabled_metrics=None, *, ..., lang: Lang = "de") -> str
def render_compare_telegram(result, *, ..., lang: Lang = "de") -> str
def render_compare_sms(result, *, ..., lang: Lang = "de") -> str
def summarize_day_comparison(comparison, *, selected_metrics=None, lang: Lang = "de") -> str
def derive_row_labels(rows, form="short", *, lang: Lang = "de") -> list[dict]
def selection_gap_notice(count, *, scope, lang: Lang = "de") -> str
def telegram_metric_notice(demoted_count, *, context, lang: Lang = "de") -> str
```

Alle privaten `_render_*`/`_fmt_*`-Funktionen, die Text erzeugen (`_render_header`, `_render_section_head`-Aufrufer, `_render_legend`, `_render_abo_footer`, `_render_app_footer`, `_render_warn_banner`, `_render_outlook_unavailable`, `_render_location_outlook`, `_render_hour_table`, `_warn_short`, `_fmt_thunder`, `_fmt_precip_type`, `_telegram_notice`, `_telegram_no_data_notice`, `_sms_location_overflow_notice`) bekommen `lang` als Parameter und reichen ihn weiter. Keine Modul-Variable `_LANG`.

**Beispiel-Schlüssel (de wörtlich wie heute, en laut Glossar):**

| Schlüssel | de | en | Stelle |
|---|---|---|---|
| `vergleich.kopf.titel` | `ORTS-VERGLEICH` | `LOCATION COMPARISON` | compare_html.py:1342 |
| `vergleich.kopf.profil` | `Profil` | `Profile` | compare_html.py:1386 |
| `vergleich.kopf.orte` | `Orte` | `Locations` | compare_html.py:1387 |
| `vergleich.kopf.erstellt` | `Erstellt` | `Created` | compare_html.py:1388 |
| `vergleich.uebersicht.titel` | `Alle Orte · gewählte Metriken` | `All locations · selected metrics` | compare_html.py:1723 |
| `vergleich.uebersicht.warnzeile` | `Amtliche Warnungen` | `Official warnings` | CV2_METRICS[0], compare_html.py:322 |
| `vergleich.uebersicht.spalte_metrik` | `Metrik` | `Metric` | compare_html.py:853 |
| `vergleich.ausblick.titel` | `3-Tages-Ausblick` | `3-day outlook` | `OUTLOOK_HEADING`, compare_html.py:1237 |
| `vergleich.stunden.spalte_zeit` | `Zeit` | `Time` | compare_html.py:1086 |
| `vergleich.fuss.naechster_versand` | `Nächster Versand` | `Next delivery` | compare_html.py:1565 |
| `vergleich.warnchip.hitze` | `Hitze` | `Heat` | `_warn_short`, compare_html.py:561 |
| `vergleich.warn.n_von_m_orten` | `{n} von {gesamt} Orten` | `{n} of {gesamt} locations` | compare_html.py:933 |
| `vergleich.telegram.kopf_datum` | `Datum: {datum}` | `Date: {datum}` | comparison.py:758 |
| `vergleich.telegram.uebersprungen` | `… +{n} weitere Orte (Telegram-Limit) — vollständig per E-Mail` | `… +{n} more locations (Telegram limit) — full version by email` | `_telegram_notice`, comparison.py:869 |
| `vergleich.sms.orte_ueberlauf` | ` +{n} Orte` | ` +{n} locs` | `_sms_location_overflow_notice`, comparison.py:1115 |
| `vergleich.zeile.regen` | `Regen` | `Rain` | `_DAILY_PLAIN_ROWS`, comparison.py:75 |
| `allgemein.hinweis.gewaehlt_ohne_wert.vergleich` | `in diesem Vergleich` | `in this comparison` | `selection_gap_notice`, channel_layout.py:121 |
| `vergleich.vortag.zusammenfassung` | `Vergleich zum Vortag: heute {woerter} als gestern` | `Compared with yesterday: today {woerter} than yesterday` | `summarize_day_comparison`, day_comparison.py:322 |

Weitere Schlüssel nach demselben Muster: je ein Schlüssel für jede Legendenstufe (`vergleich.legende.unkritisch`/`achtung`/`warnung`/`gefahr` = `unkritisch`/`Achtung`/`Warnung`/`Gefahr` -> `OK`/`Caution`/`Warning`/`Danger`), Abo-Fuß (`Dieses Abo` -> `This subscription`, `Vergleich in App öffnen →` -> `Open comparison in app →`, `Abo bearbeiten` -> `Edit subscription`, `Orte ändern` -> `Change locations`, `Abmelden` -> `Unsubscribe`), Abschnittsköpfe (`ÜBERSICHT` -> `OVERVIEW`, `STUNDEN` -> `HOURLY`, `AUSBLICK` -> `OUTLOOK`, `Stundenverlauf · alle Orte` -> `Hourly view · all locations`, `← scrollen` -> `← scroll`), die 26 Zeilenlabels des Klartext/Telegram (`vergleich.zeile.<zeilenschlüssel>`), Telegram-Kopf (`ORTS-VERGLEICH — {name}` -> `LOCATION COMPARISON — {name}`, `Fehler: {fehler}` -> `Error: {fehler}`, `keine Werte` -> `no values`), `Keine Vergleichsdaten verfügbar.` -> `No comparison data available.`, SMS-Kopf (`Vergleich {datum}:` -> `Compare {datum}:`), `{name} n/a` bleibt (ASCII-Token, kein Katalog).

**Beispiel-Umstellung (compare_html.py, `_render_header`, Zeilen 1342 und 1385-1388), vorher:**

```
label_text = f"ORTS-VERGLEICH · {_html.escape(sig.eyebrow)}"
desktop_cells = (_cell("Profil", profil_val, "33%") + _cell("Orte", orte_val, "33%")
                 + _cell("Erstellt", erstellt_val, "34%"))
```

**nachher:**

```
label_text = f"{t('vergleich.kopf.titel', lang)} · {_html.escape(sig.eyebrow)}"
desktop_cells = (_cell(t("vergleich.kopf.profil", lang), profil_val, "33%")
                 + _cell(t("vergleich.kopf.orte", lang), orte_val, "33%")
                 + _cell(t("vergleich.kopf.erstellt", lang), erstellt_val, "34%"))
```

`_render_header(result, sig, tz)` wird zu `_render_header(result, sig, tz, lang)`.

**Beispiel-Umstellung mit Register (compare_html.py:519-535, `derive_row_labels`), vorher:**

```
lang = form == "long"        # `lang` ist hier ein bool
return metric.label_de if lang else metric.col_label
zusatz = aggregation_label_de(zusatz) or zusatz
```

**nachher** (Variable umbenennen, `form`-Logik unverändert):

```
lang_long = form == "long"
return metric.label(lang) if lang_long else metric.col_label
zusatz = aggregation_label(zusatz, lang) or zusatz
```

Achtung Namenskollision: die lokale Bool-Variable `lang` in `derive_row_labels` (Zeile 519) muss umbenannt werden, sonst überdeckt sie den neuen Parameter. `col_label` (kurze Form, Stundentabelle) bleibt unangetastet.

**Weitere feste Stellen:**

- compare_html.py:1086/1088: `columns = ["Zeit"] + ...` und der Vergleich `col == "Zeit"` für die Ausrichtung: die Ausrichtung nach **Index** (`i == 0`) statt nach dem Wort entscheiden, sonst bricht `en` (`Time`).
- compare_html.py:160 `_WEEKDAY_ABBR` und :1179 `_WEEKDAYS_DE_OUTLOOK`: ersetzen durch `fmt_weekday(d, lang)`. `_build_location_outlook_rows` bekommt `lang`; `build_outlook_row(summary, day_points, weekday, ...)` bekommt den fertigen Wochentag (die Signatur gehört P3, der Aufruf bleibt gleich).
- compare_html.py:1817/1821: `<html lang="{lang}">` und `<title>{t('vergleich.kopf.titel_kurz', lang)}</title>` (de `Orts-Vergleich`, en `Location comparison`).
- compare_html.py:1349-1353 Datumszeile: de bleibt `f"{weekday}, {target_date:%d.%m.%Y}"`; Aufbau über `fmt_weekday(result.target_date, lang)` und `fmt_date_numeric(result.target_date, lang)`.
- comparison.py:220 (`Datum: %A, %d.%m.%Y`): der `de`-Zweig behält den bestehenden `strftime`-Ausdruck unverändert (Golden); `en` nutzt `fmt_weekday(d, "en", kurz=False)` und `fmt_date_numeric`.
- comparison.py `_PLAIN_ROWS`/`_DAILY_PLAIN_ROWS`: das zweite Tupel-Element (deutsches Kanal-Label, z. B. `"Regen"`) wird der Katalog-Schlüssel `"vergleich.zeile.regen"`; `_plain_metric_cell` (Zeile 674) liest `t(label_key, lang)`. Die Kürzel der SMS (`kurzform_kuerzel`) bleiben.
- Gewitter-, Hagel- und Niederschlagsart-Wörter: Quelle ist `src/app/thunder_scale.py` (`THUNDER_LABEL_DE`, `format_hail_note`, `thunder_signal_label`), von `output/metric_format.py` re-exportiert, und `PRECIP_TYPE_LABEL_DE` in `metric_format.py:297`. Vor dem Anlegen mit Grep (`def format_hail_note`, `lang`) prüfen, ob P2/P3 bereits `lang`-fähige Varianten angelegt haben. Falls nicht, anlegen: `thunder_label(level, lang)`, `thunder_signal_label(name, lang="de")`, `format_hail_note(hail_flag, lang="de")`, `precip_type_label(value, lang)`; vorhandene Konstanten und Aufrufe ohne `lang` verhalten sich unverändert (Default `de`). `_THUNDER_LEVEL_LABEL` und `_PRECIP_TYPE_LABEL` in compare_html.py (Zeilen 166, 260) fallen weg und rufen diese Funktionen; das `NONE`-Zeichen `—` bleibt lokal.
- Geteilte Hinweis-Bausteine aus P2/P3 (`render_outlook_state_html`, `render_undelivered_html`, `render_official_alerts_unavailable_html`, `render_commands_html`, `profile_signature`, `render_origin_footer_html`) werden mit `lang=lang` aufgerufen. Ihre Texte gehören P3, nicht P4.

**Allowlist-Eintrag, der entfällt:** In `tests/fixtures/i18n_python_allowlist.json` (Ratsche P11) die Präfixe `src/output/renderers/email/compare_html.py`, `src/output/renderers/comparison.py`, `src/services/day_comparison.py` entfernen. Falls die Datei zum Zeitpunkt von P4 noch nicht existiert (P11-Teil 1 legt sie früh an), steht der Eintrag dort erst nach P11; dann entfällt dieser Schritt und wird in P11 nachgeholt (nicht erfinden, vorher `Glob tests/fixtures/i18n_python_allowlist.json`).

**Golden-Fixture (Konvention Abschnitt 4):** Deterministische Fixture in `tests/golden/vergleichs_mail/fixture.py`: drei Orte, feste Zeit `2026-10-29T06:00+02:00`, feste Wetterwerte, Nutzer `golden-de`, Aufruf `render_compare_email(result, enabled_metrics=..., hourly_enabled=True, outlook_enabled=True, preset_name="Golden-Vergleich", lang="de")`. **Reihenfolge zwingend:** zuerst die `*.de.*`-Dateien mit dem unveränderten Code erzeugen und committen (RED/GREEN-Anker), danach umstellen. Die Fixture enthält keine amtlichen Warnungen (siehe Known Limitations).

**Validator (Vergleichs-Mail-Pfad):** `uv run python3 .claude/hooks/email_spec_validator.py`. Die Konstanten `_OVERVIEW_WARN_LABEL`, die Kopfzelle „Metrik“ und die erste Stundenspalte „Zeit“ werden aus `t("vergleich.uebersicht.warnzeile", lang)`, `t("vergleich.uebersicht.spalte_metrik", lang)`, `t("vergleich.stunden.spalte_zeit", lang)` gebildet; `lang` stammt aus dem Header `X-GZ-Lang` (Fehlt er: `de` und Warnung, Übergang laut PV). Staging-Lauf gegen eine echte `de`- und eine echte `en`-Mail (Postfach `+en`, Konvention Abschnitt 6) macht `/e2e-verify`, nicht der Developer.

**Token-Wächter:** `tests/test_metric_tokens_eingefroren.py` (aus P1) muss grün bleiben. `col_label` und `compact_label` werden in diesem Paket weder gelesen-und-verändert noch ersetzt; die Stundentabellen-Kurzformen (`derive_row_labels(form="short")`) bleiben identisch zur `de`-Ausgabe.

**Pflicht für den Developer-Agenten:** (1) RED-Tests der ACs grün machen, (2) deutsche Golden-Ausgabe byte-gleich, (3) Allowlist-Eintrag (siehe oben) entfernen, (4) Paritäts- und Ratschen-Test grün, (5) keine Änderung an `col_label`/`compact_label`/`sms_code`/Kürzeln. Nicht tun: andere Bereichsdateien ändern, Schlüssel umbenennen, deutsche Texte „verbessern“, neue Abhängigkeiten.

## Expected Behavior

- **Input:** `ComparisonResult` (mindestens drei Orte), Render-Optionen wie bisher, zusätzlich `lang` (`"de"` oder `"en"`, Default `"de"`).
- **Output:** HTML-Mail, Klartext, Telegram-Text und SMS-Text in der gewählten Sprache; bei `de` byte-gleich zur heutigen Ausgabe. Bei `en`: Überschriften, Übersichts-Zeilenbeschriftung (voller Registername, z. B. `Precipitation`), Legende, Abo-Fuß, Telegram-/SMS-Hinweise englisch; Stundentabellen-Spaltenköpfe (`Temp`, `Gust`, `Humid` …) und SMS-Kürzel unverändert; Datum `Thu, 29 Oct 2026`, Uhrzeit 24 h.
- **Side effects:** Keine (reine Funktionen). Kein Modul-Zustand, kein Log außer dem einmaligen `i18n fallback`-Log des Kerns.

## Acceptance Criteria

- **AC-1:** Given ein Ortsvergleich mit drei Orten und Sprache `en` / When die Vergleichs-Mail (HTML und Klartext) gerendert wird / Then sind Kopfzeile, Abschnittsüberschriften, Legende und Abo-Fuß englisch (`LOCATION COMPARISON`, `Official warnings`, `3-day outlook`, `Next delivery`) und es kommt kein deutsches Wort außer Orts- und Preset-Namen vor.
  - Test: tests/test_vergleichs_mail_zweisprachig.py — rendert die Golden-Fixture mit `lang="en"` und prüft über `t(key, "en")`-Werte (nie Literale) die Überschriften; ein Wortlisten-Scan der sichtbaren Textknoten findet kein deutsches Wort der Liste der `de`-Katalogwerte.

- **AC-2:** Given Sprache `en` / When die Stundentabelle und die Übersicht gerendert werden / Then bleiben die Spaltenköpfe der Stundentabelle die englischen Kurzformen (`col_label`) wie in der deutschen Mail, die Übersichtszeilen tragen den ausgeschriebenen englischen Registernamen (`Precipitation`, `Wind gusts`), und die feste erste Spalte heißt `Time`.
  - Test: tests/test_vergleichs_mail_zweisprachig.py — vergleicht die Menge der Kurzform-Spaltenköpfe von `de` und `en` (gleich) und die Zeilenbeschriftung der Übersicht gegen `metric.label("en")` aus dem Register.

- **AC-3:** Given Sprache `de` / When die Mail, der Klartext, der Telegram-Text und der SMS-Text mit der Golden-Fixture gerendert werden / Then ist jede Ausgabe byte-gleich zu den vor der Umstellung eingecheckten `*.de.*`-Dateien.
  - Test: tests/golden/test_vergleichs_mail_golden.py — Byte-Vergleich HTML, Klartext, Telegram und SMS gegen `tests/golden/vergleichs_mail/*.de.*`.

- **AC-4:** Given Sprache `en` und zwölf Orte / When der SMS-Text und der Telegram-Text gerendert werden / Then hält die SMS die Grenze `CHANNEL_LIMITS["sms"]["max_chars"]`, der Telegram-Text die Grenze 4096, und die Überlauf-Hinweise (`+N locs`, `more locations (Telegram limit)`) stehen am Ende; SMS-Kürzel und `n/a`-Token sind identisch zur deutschen Ausgabe.
  - Test: tests/test_vergleichs_mail_zweisprachig.py — Längenprüfung für `en` und `de` mit zwölf Orten, Token-Vergleich der SMS-Zellen (Kürzel) zwischen den Sprachen.

- **AC-5:** Given ein englischer Nutzer mit Trip-Briefing, in dem ein Vortag-Vergleich steht / When `summarize_day_comparison(..., lang="en")` aufgerufen wird / Then lautet die Zeile `Compared with yesterday: today warmer and wetter than yesterday` (Beispiel mit Wörtern aus dem Katalog), und mit `lang="de"` bleibt sie `Vergleich zum Vortag: heute wärmer und nasser als gestern`.
  - Test: tests/test_tagesvergleich_zeile_zweisprachig.py — baut ein `DayComparison` mit bekannten Deltas und prüft beide Sprachen sowie den Fall „ähnliches Wetter“ und die Leerauswahl (`""`).

- **AC-6:** Given zwei Render-Aufrufe unmittelbar nacheinander, erst `en` dann `de`, mit derselben Fixture / When beide Ergebnisse verglichen werden / Then ist das zweite Ergebnis byte-gleich zur Golden-`de`-Ausgabe (kein Zustand zwischen Nutzern) und das erste enthält keinen deutschen Katalogtext.
  - Test: tests/test_vergleichs_mail_zweisprachig.py — Reihenfolge `en`, `de`, `en`; Ergebnisse jeweils gegen Golden.

- **AC-7:** Given die englische Beispiel-Mail `compare_mail_en.eml` mit Header `X-GZ-Lang: en` und die deutsche Mail mit `X-GZ-Lang: de` / When `email_spec_validator.py` gegen beide läuft / Then endet der Lauf jeweils mit Exit 0; mit vertauschten Headern (englischer Inhalt, Header `de`) endet er mit Exit ungleich 0.
  - Test: tests/test_vergleichs_mail_validator_zweisprachig.py — ruft den Validator über seine `run_validation`-Funktion auf den Fixtures auf und prüft die Exit-Logik inklusive Fehlfall.

## Known Limitations

- **Amtliche Warnblöcke** (`render_warn_block`, `render_official_alerts_html`, Stufenwörter wie `ROT`, der Satz „höchste Stufe …“ nur sein Rahmen) bleiben bis P6 (#2668) deutsch; P4 übersetzt nur den Rahmen, den es selbst baut (`vergleich.warn.n_von_m_orten`, `Lawinenstufe`/`Avalanche level`). Die Golden-Fixture enthält deshalb keine amtliche Warnung. Dieses Fenster ist bewusst (Reihenfolge P4 vor P6).
- Annahme: Die deutsche Datumszeile im Klartext (`%A`, serverabhängig) bleibt für `de` unverändert, damit der Golden byte-gleich bleibt; eine Korrektur wäre Verhaltensänderung und gehört nicht in dieses Epic.
- Annahme: `src/services/comparison_scoring.py` hat keine Nutzertexte und bleibt unverändert; `compare_metric_catalog.py` bekommt nur zusätzliche Felder.
- Annahme: `src/i18n/format.py` bekommt die kleine Ergänzung `fmt_date_numeric`, weil P1 nur `kurz`/`lang` kennt und die Kopfzeile ein Datum mit Jahr zeigt.
- Annahme: Der SMS-Überlauf-Hinweis heißt `+N locs` (Platzform, ASCII, gleiche Länge wie `Orte`); die SMS-Kürzel selbst folgen ADR-0042 und bleiben.
- Annahme: `summarize_day_comparison` gehört laut Issue zu diesem Paket, obwohl die Zeile im Trip-Briefing steht (Aufrufer `html.py`, `plain.py`); die Aufrufe dort werden mit einer Zeile mitgeführt.
- Die Auflösung der Sprache und die Durchreichung (Aufrufer in `scheduler_dispatch_service.py`, `compare_preview_service.py`) ist P9b; ohne P9b sendet das System weiter deutsch.
- Neue Glossarbegriffe (Stundenverlauf, Abo, Übersicht) werden mit diesem Paket angehängt (nur Anhängen, keine Änderung bestehender Zeilen).

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** ADR-0104 (zusätzlich ADR-0042 für Kurzform und Spaltenköpfe, ADR-0068 für die Ausblick-Spalten)
- **Rationale:** Die Sprache gehört dem Nutzer und wird als Parameter in die reinen Renderer gereicht; Protokoll-Token und Kurzformen bleiben, damit SMS-Länge und Validatoren stabil sind.

## Changelog

- 2026-10-30: Initial spec created (Planung Epic #2644)
