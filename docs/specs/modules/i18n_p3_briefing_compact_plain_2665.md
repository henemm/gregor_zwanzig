---
entity_id: i18n_p3_briefing_compact_plain_2665
type: module
created: 2026-10-30
updated: 2026-10-30
status: draft
version: "1.0"
tags: [i18n, epic-2644, issue-2665, python, model-haiku]
---

# i18n P3: Trip-Briefing-Mail compact/plain und Hinweis-Bausteine zweisprachig

**Issue:** #2665 · **Epic:** #2644 · **Modell:** Haiku · **Konventionen:** docs/features/epic-i18n-de-en-konventionen.md Abschnitte 2, 4 (Render-Funktionen, Golden-Tests, Mail-Marker)

## Approval

- [ ] Approved

## Purpose

Wer Englisch eingestellt hat, bekommt auch die Varianten `compact` und `plain` des Trip-Briefings sowie alle Hinweis-Bausteine der Mail (Starkregen, Gewitter-Zelle, „Warnungen nicht abrufbar“, „nicht zugestellt“, Ausblick-Zustand, Ersatzquelle, Antwort-Kommandos) auf Englisch. `compact` bleibt reines ASCII, die Kürzel und Spaltenköpfe bleiben unverändert. Für Deutsch ändert sich kein Byte; die Texte der Bausteine, die auch Telegram und der Ortsvergleich nutzen, bleiben dort bis zu deren Paketen (P4, P7) deutsch.

## Source

- **File:** `src/output/renderers/email/compact.py`, `plain.py`, `starkregen_hint.py`, `thunder_branch.py`, `unavailable_hint.py`, `undelivered_hint.py`, `outlook_state_hint.py`, `outlook.py`, `profile_signature.py`, `command_block.py`, `src/output/renderers/fallback_notice.py`, `compact_summary.py`, `src/app/thunder_scale.py`
- **Identifier:** `render_compact`, `render_plain`, `format_starkregen_hint`, `render_official_alerts_unavailable_html/_plain`, `render_undelivered_plain/_html`, `outlook_state_text`, `render_outlook_table`, `render_outlook_plain`, `profile_signature`, `render_commands_plain/_html`, `build_fallback_lines`, `CompactSummaryFormatter`, `format_location_summary`, `thunder_cell_html/_plain/_compact`

> **Schicht-Hinweis:** Python-Core, Renderer-Schicht (`src/output/renderers/`), dazu die Domänenschicht `src/app/thunder_scale.py` (Gewitter-Wortschatz, Wächter #1365: kein Import einer Darstellungsschicht dort). Kein Go-, kein Frontend-Code. `src/output/renderers/day_window.py` enthält nach Grep (2026-10-30) nur Kommentare mit deutschem Text und bleibt unverändert.
>
> **Querschnitts-Prüfpunkte:**
> - **Trip/Ortsvergleich-Teilung:** `outlook.py`, `outlook_state_hint.py`, `unavailable_hint.py`, `undelivered_hint.py`, `command_block.py` (Parameter `kind="route"|"vergleich"`) und `compact_summary.py` (Wrapper `format_location_summary` für den Ortsvergleich) sind bereits geteilt. Sie bekommen `lang` als Schlüsselwort mit Standard `"de"`; der Ortsvergleich (P4) und Telegram (P7) rufen sie bis zu ihrer Umstellung unverändert deutsch auf. Es entsteht kein Pendant; gemeinsame Texte liegen in `mail.*` und `allgemein.*`.
> - **Mandantentrennung:** `lang` kommt aus `resolve_user_lang(user_id)` einmal je Versand in `NotificationService.send_trip_report` (aus P2), nie ein Fallback `default`, keine globale Sprache.
> - **Kanäle:** E-Mail `compact` und `plain`; benannt und gleichrangig: Telegram (P7), SMS und Premium-SMS (P8). Die Hinweisbausteine liefern denselben Inhalt in kanalgerechter Form; der Wortlaut für Telegram (`narrow.py` importiert `unavailable_hint`, `starkregen_hint`, `outlook_state_hint`, `fallback_notice`) wird dort mit P7 umgestellt.

### Affected Files

| Datei | CREATE/MODIFY | Zweck |
|---|---|---|
| `src/output/renderers/email/compact.py` | MODIFY | `render_compact(..., lang)`; `_STABILITY_TEXTS` (Z. 106–119), Kopf (Z. 159, 172), Metriken-Überblick (Z. 211), Wetterlage (Z. 242), „Nächste Etappen“ (Z. 260, 299); Ausgabe bleibt reines ASCII |
| `src/output/renderers/email/plain.py` | MODIFY | `render_plain(..., lang)`; Überblick (Z. 216), Stabilität (Z. 227–236), Änderungen (Z. 253), Nacht und Ankunft (Z. 303–304), Nächste Etappen (Z. 353) |
| `src/output/renderers/email/__init__.py` | MODIFY | `render_email` reicht `lang` zusätzlich an `render_plain` und `render_compact` (Z. 112–132, 181–213) |
| `src/output/renderers/email/starkregen_hint.py` | MODIFY | `format_starkregen_hint(..., lang)` (Z. 19–89), `render_starkregen_hint_*` unverändert (Text kommt fertig) |
| `src/output/renderers/email/thunder_branch.py` | MODIFY | `thunder_cell_html/_plain/_compact(tok, stage, *, lang)` und `_tagesteil` (Z. 144–230): Stufenwörter und Hagel-Zusatz in Nutzersprache; Telegram-Zelle (`thunder_cell_telegram`) bleibt auf dem rohen Token |
| `src/output/renderers/email/unavailable_hint.py` | MODIFY | Text (Z. 18–20), Titel und Detail (Z. 46–50), `render_*(…, lang)` |
| `src/output/renderers/email/undelivered_hint.py` | MODIFY | Überschriften (Z. 33–34), Gründe (Z. 48–69), Auslöser (Z. 99–103), Rest-Hinweis (Z. 209–210), `render_undelivered_*(…, lang)`; Kanalnamen bleiben (Eigennamen) |
| `src/output/renderers/email/outlook_state_hint.py` | MODIFY | Texte (Z. 45–49), Titel „Ausblick“ (Z. 98), `outlook_state_text(state, horizon_days, *, lang)` |
| `src/output/renderers/email/outlook.py` | MODIFY | Spaltenkopf „Tag“ (Z. 202, 227), ACC-Wörter `_ACC_STUFEN` (Z. 50–55; `ACC_LABEL` bleibt), `render_outlook_plain(heading=…)` (Z. 323), `lang` an `render_outlook_table`/`render_outlook_plain` |
| `src/output/renderers/email/profile_signature.py` | MODIFY | Eyebrows (Z. 69, 75, 81, 87) → `profile_signature(profile, lang="de")` |
| `src/output/renderers/email/command_block.py` | MODIFY | `render_commands_plain/_html(kind, *, lang)`: Kopfzeile, Eyebrow, Hinweis; die zwei `command_rows(kind)`-Aufrufe (Z. 18, 25) ändert P10 |
| `src/output/renderers/fallback_notice.py` | MODIFY | `build_fallback_lines(meta, *, lang)`; Texte Z. 87, 204–205, 228; `_METRIK_KLARTEXT` (Z. 57–85) und Zusatz „gröbere Auflösung“ (Z. 34–42) |
| `src/output/renderers/compact_summary.py` | MODIFY | `format_stage_summary`, `format_weather_summary`, `_format_*`, `_precip_adjective`, `format_location_summary(loc, enabled_metrics, *, lang="de")` |
| `src/app/thunder_scale.py` | MODIFY | Satzbausteine mit `lang`: `thunder_low_statement`, `thunder_low_statement_sentence`, `thunder_headline_sentence`, `thunder_signal_label`; englische Tabellen neben den deutschen |
| `src/output/renderers/trip_report.py` | MODIFY | `_generate_compact_summary` reicht `lang` an `CompactSummaryFormatter` (Z. 1002 ff.) |
| `src/services/notification_service.py` | MODIFY | `format_starkregen_hint(..., lang=lang)` in `send_trip_report` (Z. 722) |
| `src/i18n/messages/de/mail.json`, `src/i18n/messages/en/mail.json` | MODIFY | Namensraum `mail.*` (Gruppen siehe unten) |
| `tests/golden/email/regenerate.py` | MODIFY | Option `--format compact`: schreibt `*-compact.txt` bzw. mit `--lang en` `*-compact.en.txt`; Standardlauf unverändert |
| `tests/golden/email/{gr20-summer-evening,gr20-spring-morning,gr221-mallorca-evening,arlberg-winter-morning,corsica-vigilance}-compact.txt` | CREATE | deutscher Kompakt-Golden, **vor** der ersten Codeänderung aus dem heutigen Code erzeugt |
| `tests/golden/email/*-compact.en.txt`, `*-plain.en.txt` | CREATE | englische Golden-Dateien (Review-Hilfe, Regressionsschutz) |
| `tests/golden/email/test_email_compact_golden.py`, `test_email_plain_golden_en.py` | CREATE | byte-genaue Vergleiche (Szenario-Bauer aus `test_email_html_golden.py`) |
| `tests/fixtures/mail/briefing_compact_en.eml` | CREATE | echte englische Kompakt-Mail über `build_mime_message` |
| `tests/unit/test_briefing_compact_plain_sprache.py` | CREATE | Tests zu AC-1, AC-3, AC-6 |
| `tests/unit/test_briefing_hinweise_sprache.py` | CREATE | Test zu AC-4 |
| `tests/unit/test_gewitter_zelle_zusammenfassung_sprache.py` | CREATE | Test zu AC-5 |
| `tests/unit/test_briefing_compact_plain_sprache_je_nutzer.py` | CREATE | Test zu AC-7 |

## Estimated Scope

- **LoC:** ca. 330 Code ohne Katalogdaten, Goldens und Tests (13 Dateien aus dem Issue-Umfang plus `thunder_scale.py`, `__init__.py`, Durchreichen). Über dem Workflow-Limit von 250 LoC: `workflow.py set-field loc_limit_override 500` einplanen.
- **Files:** ca. 30
- **Effort:** high (viele kleine Bausteine, geteilte Aufrufer)

## Dependencies

| Entity | Type | Purpose |
|---|---|---|
| #2662 P1 | Paket | `t`, `tn`, `MetricDefinition.label(lang)`, `get_alert_label(metric_id, lang)` |
| #2663 PV | Paket | Validatoren sprachfähig, `--eml` |
| #2664 P2 | Paket | `lang` in `render_html`, `render_email`, `TripReportFormatter.format_email`, `NotificationService.send_trip_report`; `THUNDER_LABEL_EN`, `format_hail_note(lang)`; Schlüssel `mail.stabilitaet.*`, `mail.nacht.am_ziel`, `mail.ausblick.*`, `mail.stats.*` |
| #2673 P10 | Paket (danach) | ändert in `command_block.py` nur die zwei `command_rows`-Aufrufe auf `command_rows(kind, lang=lang)` |
| `.claude/hooks/briefing_mail_validator.py`, `renderer_mail_gate.py` | script/gate | `--eml`-Lauf; Gate verlangt frischen Modus-Matrix-Test und Validator |
| `src/output/renderers/narrow.py` (P7), `comparison.py`/`compare_html.py` (P4) | module | Mitnutzer der Bausteine; bleiben bei `lang="de"` |
| `docs/reference/i18n_glossar.md`, ADR-0104, ADR-0042 | doc/adr | bindende Wortliste (Trip, Etappe, Ortsvergleich, Briefing); Kürzel nie übersetzen |

## Implementation Details

**Katalog-Namensraum:** `mail.*` (nur `src/i18n/messages/{de,en}/mail.json`). Gruppen: `mail.hinweis.*`, `mail.starkregen.*`, `mail.undelivered.*`, `mail.outlook_state.*`, `mail.befehle.*`, `mail.profil.*`, `mail.fallback.*`, `mail.zusammenfassung.*`, `mail.gewitter.*`, `mail.acc.*`, `mail.kompakt.*` (ASCII-Fassungen für `compact`). Texte, die schon P2 angelegt hat (`mail.stabilitaet.*`, `mail.nacht.am_ziel`, `mail.ausblick.eyebrow`, `mail.legende.*`), werden **wiederverwendet**, nie ein zweites Mal angelegt (Plain und HTML tragen dort denselben Text). Die ASCII-Fassung für `compact` ist ein eigener Schlüssel mit `_kompakt`, weil der Text sich unterscheidet (`Grosswetterlage`).

**Beispiel-Schlüssel (de wortgleich zum Quelltext, en nach Glossar):**

| Schlüssel | de | en | Stelle |
|---|---|---|---|
| `mail.hinweis.warnungen_nicht_abrufbar.text` | Amtliche Warnungen aktuell nicht abrufbar — bitte selbst pruefen. | Official warnings are currently unavailable — please check yourself. | `unavailable_hint.py:18` |
| `mail.hinweis.warnungen_nicht_abrufbar.titel` | Amtliche Warnungen aktuell nicht abrufbar | Official warnings currently unavailable | `unavailable_hint.py:46` |
| `mail.starkregen.beginn` | {label} ab ca. {zeit} (in ~{min} Min) | {label} from about {zeit} (in ~{min} min) | `starkregen_hint.py:62` |
| `mail.starkregen.ende_letzter` | , letzter Regen gegen {zeit} | , last rain around {zeit} | `starkregen_hint.py:70` |
| `mail.undelivered.kopf_fehlgeschlagen` | FEHLGESCHLAGEN — da ist etwas schiefgegangen | FAILED — something went wrong | `undelivered_hint.py:33` |
| `mail.undelivered.kopf_zurueckgehalten` | ZURÜCKGEHALTEN — so hast du es eingestellt | HELD BACK — as you set it up | `undelivered_hint.py:34` |
| `mail.undelivered.rest` | und {count} weitere | and {count} more | `undelivered_hint.py:210` |
| `mail.undelivered.grund.quiet_hours` | Stille Stunden | Quiet hours | `undelivered_hint.py:50` |
| `mail.outlook_state.zu_weit.one` / `.other` | Nächste Etappe liegt zu weit voraus (max. {count} Tage). (beide gleich) | Next stage is too far ahead (max. {count} day). / (max. {count} days). | `outlook_state_hint.py:47` |
| `mail.befehle.hinweis` | Antworte auf diese E-Mail mit einem Schlüsselwort. | Reply to this email with a keyword. | `command_block.py:46` |
| `mail.profil.wandern` | WANDERN | HIKING | `profile_signature.py:75` |
| `mail.kompakt.stabil` | Wetterlage: STABIL - Die Grosswetterlage ist stabil. Prognosen fuer die naechsten Etappen sind verlaesslich. | Weather pattern: STABLE - The overall weather pattern is stable. Forecasts for the next stages are reliable. | `compact.py:107` |
| `mail.zusammenfassung.regen.stark` | starker Regen | heavy rain | `compact_summary.py:434` |

Die weiteren Profil-Eyebrows (`wintersport`: `WINTERSPORT · PISTE` / `WINTER SPORTS · PISTE`, `allgemein`: `WETTER-BRIEFING` / `WEATHER BRIEFING`, `summer_trekking`: deutscher Wert wortgleich aus `profile_signature.py` Z. 81 übernehmen, englisch `ALPINE TREKKING`), die Gründe und Auslöser der nicht zugestellten Meldungen (`Versand fehlgeschlagen` = `Delivery failed`, `Tageslimit` = `Daily limit`, `unter deiner Schwelle` = `below your threshold`, `Amtliche Warnung` = `Official warning`, `Regenradar` = `Rain radar`, `Wetteränderung` = `Weather change`), die ACC-Wörter (`hoch`/`mittel`/`niedrig`/`sehr niedrig` = `high`/`medium`/`low`/`very low`) und die Regen- und Wind-Wörter der Zusammenfassung folgen demselben Muster. Wörter, die das Glossar nicht kennt (zum Beispiel „Wetterlage“ für `weather_code`), werden zuerst im Glossar ergänzt (`docs/reference/i18n_glossar.md`). Namen von Wetterdiensten und Kanälen (`DWD`, `Météo-France`, `MET Norway`, `ECMWF`, `GeoSphere`, `E-Mail`, `Telegram`, `SMS`, `Premium-SMS`) sind Eigennamen und bleiben; nur Zusätze wie „gröbere Auflösung“ (`coarser resolution`) werden übersetzt.

**Beispiel-Umstellung 1 (einzelner Satz mit Platzhaltern), `starkregen_hint.py` `format_starkregen_hint()` Z. 58–70:**

```python
# vorher (Z. 62 und Z. 68)
satz = f"{intensity_label} ab ca. {time_str} (in ~{onset_minutes} Min)"
satz += f", Regen mindestens bis {end_str}"
# nachher: Signatur format_starkregen_hint(..., lang: Lang = "de")
satz = t("mail.starkregen.beginn", lang, label=intensity_label, zeit=time_str, min=onset_minutes)
satz += t("mail.starkregen.ende_mindestens", lang, zeit=end_str)
```

Die Satzteile (Ende, Reichweite, Ortsangabe) bleiben je ein eigener Schlüssel, der in der heutigen Reihenfolge angehängt wird; das ist die einzige Stelle mit Teilsatz-Anhängen und ändert die deutsche Zeichenfolge nicht. `intensity_label` kommt fertig vom Nowcast-Dienst und wird mit P5/P9b übersetzt.

**Beispiel-Umstellung 2 (Plural), `outlook_state_hint.py` Z. 62–77:** statt `template.format(n=n)` bei `BEYOND_HORIZON`: `tn("mail.outlook_state.zu_weit", n, lang)`; die deutschen Werte `.one` und `.other` sind identisch (heute steht auch bei 1 „Tage“), das Englische unterscheidet `day`/`days`. `_OUTLOOK_STATE_TEXT` (Z. 45–49) entfällt zugunsten der Schlüssel; die Funktionssignaturen `outlook_state_should_warn`, `outlook_state_text`, `render_outlook_state_html/_plain` behalten die Reihenfolge der Parameter und bekommen nur `*, lang`.

**Beispiel-Umstellung 3 (Konstanten, die Tests importieren), `undelivered_hint.py`:** `HEADING_FAILED`, `HEADING_WITHHELD` und `_REASON_LABELS` werden von sechs Bestandstests importiert und bleiben als **deutsche Referenzwerte** erhalten (`HEADING_FAILED = t("mail.undelivered.kopf_fehlgeschlagen", "de")`, `_REASON_LABELS = {code: t(f"mail.undelivered.grund.{code}", "de") for code in …}`, mit `# i18n-dynamic: mail.undelivered.grund.`). Die Renderer holen die Texte sprachabhängig über neue Funktionen `_heading(block, lang)` und `_reason_label(code, lang)`; unbekannte Codes erscheinen wie heute roh. `_subject()` ruft `get_alert_label(str(metric_id), lang)` (aus P1).

**Gewitter-Wortschatz (Lücke im Issue-Umfang).** Die Gewitter-Wörter und -Sätze liegen in der Domänenschicht `src/app/thunder_scale.py` (`THUNDER_LABEL_DE`, `THUNDER_SIGNAL_LABEL_DE`, `THUNDER_NIGHT_ADJECTIVE_DE`, `_LOW_KERN_*`, Satzbauer) und kommen in keinem Paketumfang vor, obwohl `thunder_branch.py` und `compact_summary.py` sie ausgeben. P3 ergänzt dort **parallele englische Tabellen** (`THUNDER_SIGNAL_LABEL_EN`, `THUNDER_NIGHT_ADJECTIVE_EN`, Kernsätze `unstable air mass` / `weak signal`, Kopfsätze `No thunderstorm expected`, `Thunderstorm possible`, `Strong thunderstorm expected`, Anhang ` from {when}`) und gibt den Funktionen ein Schlüsselwort `lang="de"`. Es wird bewusst **kein** `src/i18n`-Katalog in die Domänenschicht importiert (Wächter #1365); die Tabellen folgen dem Muster der deutschen. Das Stufenwort-Mapping `THUNDER_LABEL_EN` und `format_hail_note(lang)` liefert P2 (siehe dort).

**Compact bleibt ASCII.** Jeder neue englische Text in `mail.kompakt.*` ist reines ASCII (kein `—`, `·`, `ü`); der bestehende `_ascii()`-Übersetzer (Z. 54–70) bleibt als Sicherheitsnetz. Der Kopf `{trip_name} - {report_type.title()} Report` (Z. 159, 172) ist in beiden Sprachen derselbe englische Ausdruck und bleibt unverändert.

**Durchreichen.** `lang: Lang = "de"` nur als Schlüsselwort. `render_email` reicht `lang` jetzt auch an `render_plain` und `render_compact`; `render_plain`/`render_compact` an `render_outlook_*`, die Hinweis-Bausteine, `build_fallback_lines`, `render_commands_*`, `profile_signature`, `build_origin_footer` und die Legendenfunktionen (aus P2).

**Golden.** Schritt 0, **vor** der ersten Codeänderung: den deutschen Kompakt-Golden aus dem heutigen Code erzeugen (`uv run python3 tests/golden/email/regenerate.py --format compact`) und einchecken. Deutsch Plain: die bestehenden `tests/golden/email/*-plain.txt` bleiben unverändert grün. Englisch: `--lang en` (und `--format compact`) erzeugt `*-plain.en.txt` und `*-compact.en.txt`, einmal von Hand gegen das Glossar gelesen.

**Validator.** `uv run python3 .claude/hooks/briefing_mail_validator.py --eml tests/fixtures/mail/briefing_compact_de.eml` und `… briefing_compact_en.eml` (beide Exit 0); dazu `uv run pytest tests/tdd/test_issue_811_mode_matrix.py` (Renderer-Commit-Gate).

**Allowlist-Eintrag, der entfernt wird:** in `tests/fixtures/i18n_python_allowlist.json` (P11, sofern die Datei beim Umsetzen schon existiert; sonst legt P11 sie ohne diese Einträge an) die Präfixe `src/output/renderers/email/compact.py`, `plain.py`, `starkregen_hint.py`, `thunder_branch.py`, `unavailable_hint.py`, `undelivered_hint.py`, `outlook_state_hint.py`, `outlook.py`, `profile_signature.py`, `command_block.py`, `src/output/renderers/fallback_notice.py`, `src/output/renderers/compact_summary.py`.

**Token-Wächter.** `tests/test_metric_tokens_eingefroren.py` muss grün bleiben. Nicht anfassen: `col_label`, `compact_label`, `sms_code`, `ACC_LABEL`, die Gewitter-Token der Telegram-Kurzform (`mittel@14`), die Kürzel in der Legende.

## Expected Behavior

- **Input:** Ein Trip-Briefing im Format `compact` oder die Klartext-Fassung der Vollversion, dazu optionale Hinweise (Starkregen, Warnungen nicht abrufbar, nicht zugestellte Meldungen, Ausblick-Zustand, Ersatzquelle), `lang` `"de"` oder `"en"`.
- **Output:** Bei `en` durchgehend englischer Text (`compact` weiterhin reines ASCII, Zeilenlängen und Struktur unverändert); bei `de` byte-gleich zur heutigen Ausgabe. Kürzel, Spaltenköpfe, Zeiten, Zahlen und Namen des Nutzers unverändert.
- **Side effects:** Keine neuen Schreibzugriffe. Aufrufer ohne `lang` (Telegram, Ortsvergleich, Vorschau) behalten ihr deutsches Verhalten.

## Acceptance Criteria

- **AC-1:** Given Nutzer mit Sprache Englisch / When das Briefing im Format `compact` und die Klartext-Fassung gerendert werden / Then enthalten beide kein deutsches Wort außer Orts- und Trip-Namen, `compact` besteht `str.isascii()`, und die Kürzel und Spaltenköpfe (`Temp`, `Gust`, `Rain`) sind unverändert.
  - Test: `tests/unit/test_briefing_compact_plain_sprache.py` — echter Aufruf von `TripReportFormatter.format_email(..., lang="en")` mit den Golden-Szenarien, Prüfung gegen deutsche Signalwörter (`Naechste Etappen`, `Wetterlage`, `Metriken-Ueberblick`, `Nacht am Ziel`) und `isascii()`.

- **AC-2:** Given Nutzer mit Sprache Deutsch (oder ohne `lang`) / When dieselben fünf Referenz-Szenarien als `compact` und `plain` gerendert werden / Then ist die Ausgabe byte-gleich zur Ausgabe vor der Umstellung (Golden-Vergleich), und die englischen Ausgaben sind byte-gleich zu den eingecheckten `*.en.txt`.
  - Test: `tests/golden/email/test_email_compact_golden.py` (neu, Deutsch und Englisch), `tests/golden/email/test_email_plain_golden.py` (unverändert) und `tests/golden/email/test_email_plain_golden_en.py`.

- **AC-3:** Given die deutsche und die englische Kompakt-Mail als `.eml` über `build_mime_message` / When `briefing_mail_validator.py --eml` jeweils läuft / Then ist der Exit-Code in beiden Fällen 0, und die englische Mail trägt den Kopf `X-GZ-Lang: en`.
  - Test: `tests/unit/test_briefing_compact_plain_sprache.py` — startet den Validator als Prozess gegen `briefing_compact_de.eml` und `briefing_compact_en.eml`. Der Lauf gegen eine live zugestellte englische Staging-Mail folgt in A2 (#2681).

- **AC-4:** Given Sprache Englisch / When die Hinweise „Starkregen“, „Warnungen nicht abrufbar“, „nicht zugestellt“ (beide Blöcke, Gründe, Rest-Zeile), „Ausblick-Zustand“ (mit n = 1 und n = 3 Tagen) und „Ersatzquelle“ erzeugt werden / Then sind alle Texte englisch (zum Beispiel `1 day` und `3 days`, `and 2 more`), Eigennamen (`DWD`, `Telegram`) bleiben, und bei Deutsch sind sie wortgleich zu heute (`Tage` auch bei 1).
  - Test: `tests/unit/test_briefing_hinweise_sprache.py` — echte Aufrufe der Bausteine in beiden Sprachen; die Bestandstests (`tests/tdd/test_undelivered_reason_in_briefing.py`, `tests/unit/test_fallback_notice.py`, `tests/tdd/test_official_alerts_unavailable_hint.py`) laufen unverändert grün.

- **AC-5:** Given Sprache Englisch und eine Etappe mit Gewitter (Stufen leicht, mittel, hoch, mit Hagel) und Regen- und Windmuster / When Gewitter-Zelle (`html`, `plain`, `compact`) und Kurz-Zusammenfassung erzeugt werden / Then stehen Stufenwörter, Hagel-Zusatz und Sätze englisch (`light`, `medium`, `high`, `heavy rain`), Uhrzeiten und Zahlen bleiben, und der Ortsvergleichs-Wrapper `format_location_summary` ohne `lang` liefert weiter deutschen Text.
  - Test: `tests/unit/test_gewitter_zelle_zusammenfassung_sprache.py` — echte Aufrufe von `thunder_cell_*`, `CompactSummaryFormatter` und `format_location_summary` in beiden Sprachen.

- **AC-6:** Given Sprache Englisch / When der Antwort-Kommando-Block für `kind="route"` und `kind="vergleich"` in Klartext und HTML gerendert wird / Then sind Kopfzeile, Eyebrow und Hinweis englisch (`Reply commands`, `Reply to this email with a keyword.`), der Befehlsteil kommt unverändert aus `command_rows` (seine Umstellung folgt mit P10), und bei Deutsch ist der Block wortgleich zu heute.
  - Test: `tests/unit/test_briefing_compact_plain_sprache.py` — beide Arten, beide Sprachen.

- **AC-7:** Given Nutzer A mit `language: "en"` und Nutzer B ohne Feld, beide mit Format `compact` / When für beide nacheinander im selben Prozess der echte Versandpfad `send_trip_report` läuft / Then trägt A's Mail englischen Inhalt und `X-GZ-Lang: en`, B's Mail deutschen Inhalt und `X-GZ-Lang: de`, in beliebiger Reihenfolge.
  - Test: `tests/unit/test_briefing_compact_plain_sprache_je_nutzer.py` — Muster `tests/unit/test_briefing_recipient_logging.py` (nur `EmailOutput._dial_and_send` als Netzrand ersetzt), zwei echte Nutzerverzeichnisse.

- **AC-8:** Given die Mitnutzer der Bausteine (Telegram-Kurzform, Ortsvergleichs-Mail) / When sie die geteilten Hinweis-Bausteine ohne `lang` aufrufen / Then bleibt ihre Ausgabe byte-gleich zu heute.
  - Test: bestehende Tests laufen unverändert grün: `tests/tdd/test_telegram_trip_unavailable_hint.py`, `tests/tdd/test_compare_unavailable_hint.py`, `tests/tdd/test_outlook_state_visible_in_channels.py`, `tests/tdd/test_starkregen_kurzfristhinweis.py`.

## Known Limitations

- Annahme: `src/app/thunder_scale.py` wird hier mit englischen Parallel-Tabellen erweitert, weil kein Paket der Planung es nennt, die Gewitter-Zelle und die Zusammenfassung es aber ausgeben. Dieselbe Lücke betrifft Alarme (P5), Telegram (P7), den Scheduler (P9b: `app/day_window.py` Nacht-Halbsatz, `trip_report_scheduler.py`) und Inbound (P10: `GEWITTER`-Kommando); sie rufen die hier geschaffenen Funktionen mit `lang` auf.
- Annahme: Die Antwort-Kommandos (`command_rows`) bleiben bis P10 deutsch; die Mail trägt in der englischen Fassung also vorübergehend deutsche Befehlsbeschreibungen. Das ist ein bekannter Zwischenstand und kein Fehler dieses Pakets.
- Annahme: `intensity_label` (Starkregen-Stufe) und die Quellen-Namen in `fallback_notice` kommen von Nowcast-Dienst und Providern; ihre Übersetzung gehört zu P5 (Radar-Alarme) und P9b.
- Teilsatz-Anhänge im Starkregen-Hinweis (Ende, Reichweite, Ortsangabe) sind je ein Schlüssel und werden wie heute angehängt; die Wortstellung ist in beiden Sprachen so gewählt, dass das ohne Umstellung funktioniert.
- Die Zeichenbudgets der Kompaktform sind nicht ausgemessen; englische Texte können länger sein. Der Validator-Lauf (Byte-Limit 2048) und der Fresh-Eyes-Abschluss (F12) decken das ab; ein Überschreiten wäre ein Nebenbefund.
- `trip_report.py` `_build_units_legend` (ungenutzt, in `KNOWN_VIOLATIONS`) bleibt, siehe P2.

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** ADR-0104 (zusätzlich ADR-0042)
- **Rationale:** Alle Kanäle sprechen die Sprache des Nutzers mit demselben Inhalt (ADR-0095); Kurzform bleibt Platzform und ASCII-Pflicht der Kompaktform bleibt, Kürzel werden nie übersetzt.

## Changelog

- 2026-10-30: Initial spec created (Planung Epic #2644)
