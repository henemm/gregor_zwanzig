---
entity_id: i18n_p2_briefing_mail_html_2664
type: module
created: 2026-10-30
updated: 2026-10-30
status: approved
version: "1.0"
tags: [i18n, epic-2644, issue-2664, python, model-haiku]
---

# i18n P2: Trip-Briefing-Mail HTML (`email/html.py`, `email/helpers.py`) zweisprachig

**Issue:** #2664 · **Epic:** #2644 · **Modell:** Haiku · **Konventionen:** docs/features/epic-i18n-de-en-konventionen.md Abschnitte 2, 4 (Render-Funktionen, Golden-Tests, Mail-Marker)

## Approval

- [x] Approved (PO-Freigabe 2026-10-30)

## Purpose

Wer Englisch eingestellt hat, bekommt die Trip-Briefing-Mail im Format `full` komplett auf Englisch: Überschriften, Kennzahlen-Kacheln, Zeilennamen der Tabellen (aus dem Metrik-Register), Gewitter-Stufenwörter, Legendenzeilen, Hinweise und Fußzeile. Die Spaltenköpfe (`Temp`, `Gust`, `Rain` …) und alle Kürzel bleiben unverändert, die Legende löst sie in der Nutzersprache auf (`Gust = Wind gusts`). Für Deutsch ändert sich kein Byte der Mail; die fünf bestehenden Golden-Dateien bleiben grün.

## Source

- **File:** `src/output/renderers/email/html.py`, `src/output/renderers/email/helpers.py`, `src/output/renderers/email/__init__.py`, `src/output/renderers/trip_report.py`, `src/services/notification_service.py`, `src/app/thunder_scale.py`
- **Identifier:** `render_html`, `render_stability_label_html`, `_render_footer`, `build_origin_footer`, `_MAIL_TYPE_LABELS`, `format_units_legend`, `format_column_legend`, `build_units_legend`, `build_column_legend`, `outlook_legend_pairs`, `build_confidence_hint`, `_pill_for_metric`, `format_trend_tokens`, `_THUNDER_MAP`, `format_hail_note`, `render_email`, `TripReportFormatter.format_email`, `NotificationService._send_email`

> **Schicht-Hinweis:** Python-Core, Renderer-Schicht (`src/output/renderers/email/`) und die Domänenschicht `src/app/thunder_scale.py` für das Stufenwort (Wächter #1365: dort kein Import einer Darstellungsschicht). Kein Go-, kein Frontend-Code. `email/corridor_mark.py` und `email/design_tokens.py` enthalten nach Grep (2026-10-30) keine Nutzertexte und bleiben unverändert (keine Änderung ist die richtige Antwort; die Python-Ratsche P11 bestätigt das).
>
> **Querschnitts-Prüfpunkte:**
> - **Trip/Ortsvergleich-Teilung:** `helpers.py` ist der geteilte Baustein von Trip und Ortsvergleich (`format_units_legend`, `format_column_legend`, `outlook_legend_pairs`, `build_origin_footer` werden von `compare_html.py` und den Alarm-Renderern mitgenutzt). Alle neuen Parameter heißen `lang` (nur Schlüsselwort, Standard `"de"`); der Ortsvergleich (P4) und die Alarme (P5/P6) behalten bis zu ihrer Umstellung ihr deutsches Verhalten. Es entsteht kein zweiter Legenden- oder Fußzeilen-Baustein.
> - **Mandantentrennung:** `lang` kommt aus `resolve_user_lang(user_id)` des angemeldeten Nutzers, **einmal je Versand** in `NotificationService.send_trip_report` (`self._require_user()`), nie ein Fallback auf `default`. Kein globaler Zustand: zwei Nutzer nacheinander im selben Prozess bekommen je ihre Sprache.
> - **Kanäle:** Diese Spec betrifft den Kanal E-Mail (`full`). Telegram, SMS und Premium-SMS sind benannt und folgen in P7/P8; `compact` und `plain` in P3. Gleicher Inhalt in kanalgerechter Form; die Kürzel bleiben in allen Kanälen gleich.

### Affected Files

| Datei | CREATE/MODIFY | Zweck |
|---|---|---|
| `src/output/renderers/email/html.py` | MODIFY | `render_html(..., lang)`; Stabilität (Z. 95–133), Fußzeile `_render_footer` (Z. 474–528), Kennzahlen (Z. 1031–1039), Datumskopf (Z. 1067–1081), Etappen-Zähler (Z. 1106–1117), Nacht (Z. 1285), Ausblick-Eyebrow (Z. 1395, 1411), Metriken-Überblick (Z. 1444), Hagel-Legende (Z. 853), `<html>` (Z. 1688) |
| `src/output/renderers/email/helpers.py` | MODIFY | `lang` für `format_units_legend` (Z. 393), `format_column_legend` (Z. 410), `build_units_legend` (Z. 548), `outlook_legend_pairs` (Z. 575), `build_column_legend` (Z. 608), `build_confidence_hint` (Z. 349), `build_origin_footer` / `_MAIL_TYPE_LABELS` (Z. 486–528), `_THUNDER_MAP` und `format_trend_tokens` samt `_TREND_THUNDER_LABELS` (Z. 936–1090), `_pill_for_metric` und `build_metrics_summary_pills` (Z. 1572 ff.) |
| `src/app/thunder_scale.py` | MODIFY | `THUNDER_LABEL_EN` neben `THUNDER_LABEL_DE` (Z. 281), `thunder_label(level, lang="de")`, `format_hail_note(hail_flag, lang="de")` (Z. 42) |
| `src/output/renderers/email/__init__.py` | MODIFY | `render_email(..., lang)` reicht `lang` an `render_html` durch (Z. 143–180); `render_plain`/`render_compact` folgen in P3 |
| `src/output/renderers/trip_report.py` | MODIFY | `TripReportFormatter.format_email(..., lang="de")` reicht an `render_email` (Z. 64–92, 236–267) |
| `src/services/notification_service.py` | MODIFY | `send_trip_report` (Z. 682 ff.): `lang = resolve_user_lang(self._require_user())` einmal; an `format_email` und `_send_email(report, lang)` (Z. 2416–2434) |
| `src/i18n/messages/de/mail.json`, `src/i18n/messages/en/mail.json` | MODIFY | Namensraum `mail.*`; Schlüssel aus PV (`mail.nacht.am_ziel`, `mail.ausblick.spalte_tag`, `mail.pille.kein_regen`) unverändert übernehmen |
| `tests/golden/email/regenerate.py` | MODIFY | Option `--lang en`: schreibt `*-html.en.txt`; ohne Option unverändert (überschreibt nie die deutschen Dateien) |
| `tests/golden/email/{gr20-summer-evening,gr20-spring-morning,gr221-mallorca-evening,arlberg-winter-morning,corsica-vigilance}-html.en.txt` | CREATE | englische Golden-Dateien (Review-Hilfe und Regressionsschutz) |
| `tests/golden/email/test_email_html_golden_en.py` | CREATE | vergleicht die englische Ausgabe byte-genau; Szenario-Bauer aus `test_email_html_golden.py` |
| `tests/fixtures/mail/briefing_full_en.eml` | CREATE | echte englische Renderer-Ausgabe über `build_mime_message` (Kopf `X-GZ-Lang: en`) |
| `tests/unit/test_briefing_html_sprache.py` | CREATE | Tests zu AC-1, AC-3 und AC-6 |
| `tests/unit/test_briefing_mail_sprache_je_nutzer.py` | CREATE | Test zu AC-5 (zwei Nutzer, echter Versandpfad) |
| `tests/tdd/test_briefing_modus_matrix_sprachen.py` | CREATE | Test zu AC-4 |

## Estimated Scope

- **LoC:** ca. 260 Code ohne Katalogdaten, Goldens und Tests (71 Literale in `html.py`, 46 in `helpers.py`, Gewitter-Stufenwort ~25, Durchreichen von `lang` ~60). Über dem Workflow-Limit von 250 LoC: `workflow.py set-field loc_limit_override 500` einplanen.
- **Files:** ca. 19
- **Effort:** medium

## Dependencies

| Entity | Type | Purpose |
|---|---|---|
| #2662 P1 | Paket | `t`, `tn`, `fmt_weekday`, `MetricDefinition.label(lang)`, `aggregation_label` |
| #2663 PV | Paket | Kopf `X-GZ-Lang`, Validator liest Katalogtexte; Schlüssel `mail.nacht.am_ziel`, `mail.ausblick.spalte_tag`, `mail.pille.kein_regen` |
| `.claude/hooks/briefing_mail_validator.py` | script | `--eml`-Lauf gegen deutsche und englische Mail |
| `.claude/hooks/renderer_mail_gate.py` | gate | blockt Commits an Mail-Inhalts-Dateien bis Modus-Matrix-Test und Validator frisch grün sind |
| `docs/reference/i18n_glossar.md`, `docs/reference/mail_validators.md` | doc | bindende Wortliste (Trip, Etappe, Ortsvergleich, Briefing); Validator-Referenz |
| `email/compare_html.py` (P4), `alert/*` (P5/P6) | module | Mitnutzer der Hilfsfunktionen; behalten `lang="de"` bis zur eigenen Umstellung |
| ADR-0104, ADR-0042 | adr | Sprache am Nutzer; Kürzel und `col_label` nie übersetzen, Auflösung in Nutzersprache |

## Implementation Details

**Katalog-Namensraum:** `mail.*` (nur `src/i18n/messages/{de,en}/mail.json`). Gruppen: `mail.kopf.*`, `mail.stats.*`, `mail.stabilitaet.*`, `mail.nacht.*`, `mail.ausblick.*`, `mail.legende.*`, `mail.hinweis.*`, `mail.pille.*`, `mail.fusszeile.*`, `mail.herkunft.*`. Keine anderen Dateien anfassen. Texte, die auf Trip- und Ortsvergleich-Flächen identisch sind (zum Beispiel Wochentags- oder Datumsworte), gehören nach `allgemein.*` (P4 nutzt sie mit).

**Beispiel-Schlüssel (de wortgleich zum Quelltext, en nach Glossar):**

| Schlüssel | de | en | Stelle |
|---|---|---|---|
| `mail.kopf.briefing` | {typ}-Briefing | {typ} briefing | `html.py:499` (`{typ}` = `report_type.title()`) |
| `mail.fusszeile.trip_oeffnen` | Trip-Übersicht öffnen → | Open trip overview → | `html.py:512, 519` |
| `mail.fusszeile.zeitplan` | Briefing-Zeitplan | Briefing schedule | `html.py:516, 520` |
| `mail.stats.aufstieg` / `mail.stats.max_hoehe` | Aufstieg / Max Höhe | Ascent / Max elevation | `html.py:1034, 1038` |
| `mail.legende.einheiten` | Einheiten: {liste} | Units: {liste} | `helpers.py:407` |
| `mail.legende.spalten` | Spalten: {liste} | Columns: {liste} | `helpers.py:439` |
| `mail.nacht.am_ziel` (aus PV) | Nacht am Ziel ({hoehe}m) | Night at destination ({hoehe}m) | `html.py:1285` |
| `mail.pille.kein_regen` (aus PV) | kein Regen | no rain | `helpers.py:1752` |
| `mail.hinweis.verlaesslichkeit` | Ab {wochentag} ist die Vorhersage weniger verlässlich. | From {wochentag} the forecast is less reliable. | `helpers.py:390` |
| `mail.herkunft.vergleich` | Ortsvergleich | Location comparison | `helpers.py:489` |
| `mail.herkunft.amtliche_warnung` | Amtliche Warnung | Official warning | `helpers.py:490` |
| `mail.herkunft.abweichungs_alarm` | Abweichungs-Alarm | Deviation alert | `helpers.py:492` |

Die übrigen Texte folgen demselben Muster: Stabilitäts-Box (`mail.stabilitaet.stabil|wechselhaft|fragil`, Z. 112–125; der interne Wert `STABIL` bleibt, im englischen Text steht `STABLE`), Kennzahlen Distanz, Abstieg, Segmente, Pillen (`Regen ab {zeit} · {summe} mm`, `Regen-W. max …`, `kein Gewitter`, `helpers.py:1634–1871`), Hagel-Legende (Z. 853), Etappen-Zähler (`Etappe {nr} / {gesamt}`, en: `Stage {nr} / {gesamt}`), Ausblick-Eyebrow (`Ausblick · nächste 3 Tage`, en: `Outlook · next 3 days`), `mail.herkunft.trip_voll|trip_kompakt|radar_alarm` für die übrigen Einträge von `_MAIL_TYPE_LABELS`. Die Wörter „Hinweis“, „Stand“ und „Vorschau“ heißen laut Glossar `note`, `as of`, `preview`.

**Beispiel-Umstellung 1 (Fußzeile), `html.py` `_render_footer()` Z. 474–528:**

```python
# vorher (Z. 499 und Z. 512)
f'{report_type.title()}-Briefing</span>'
f'text-decoration:none;">Trip-Übersicht öffnen →</a>'
# nachher: Signatur _render_footer(*, ..., lang: Lang = "de")
f'{t("mail.kopf.briefing", lang, typ=report_type.title())}</span>'
f'text-decoration:none;">{t("mail.fusszeile.trip_oeffnen", lang)}</a>'
```

**Beispiel-Umstellung 2 (geteilter Legenden-Baustein), `helpers.py` Z. 393–439:** `format_units_legend(label_units, *, lang="de")` liefert `t("mail.legende.einheiten", lang, liste=" · ".join(parts))`, `format_column_legend(label_pairs, *, lang="de")` entsprechend `mail.legende.spalten`. `build_column_legend(...)` (Z. 636–641) bildet die Paare mit dem Namen in Nutzersprache und dem **unveränderten** Kürzel:

```python
# vorher (Z. 638)
pairs.append((col_label, get_metric_by_col_key(col_key).label_de))
# nachher
pairs.append((col_label, get_metric_by_col_key(col_key).label(lang)))
```

Gleiches in `outlook_legend_pairs` (Z. 597: `m.label_de` → `m.label(lang)`). Ergebnis für `gust`: deutsch `Gust = Böen`, englisch `Gust = Wind gusts`.

**Beispiel-Umstellung 3 (Wochentag im Datumskopf), `html.py` Z. 1068–1079:** die lokale Tabelle `_WEEKDAY_ABBR` entfällt, `wd = fmt_weekday(_sent_local, lang)`; der restliche Stempel (`%d.%m.%Y`, `%H:%M`, Zeitzonenkürzel) bleibt in beiden Sprachen unverändert. Dasselbe für `_WEEKDAY_DE` in `build_confidence_hint` (Z. 389): `fmt_weekday(first_day, lang, kurz=False)`; die Tabelle `_WEEKDAY_DE` (Z. 46) entfällt, sobald kein Aufrufer sie mehr nutzt.

**Gewitter-Stufenwörter (Lücke im Issue-Umfang).** Die Stufenwörter der Gewitter-Zelle (`kein`, `leicht`, `mittel`, `hoch`) stammen aus `THUNDER_LABEL_DE` in `src/app/thunder_scale.py` (Z. 281) und fließen über `_THUNDER_MAP` und `_TREND_THUNDER_LABELS` (`helpers.py` Z. 936–1057) in jede Gewitter-Zelle; ohne sie enthielte die englische Mail das deutsche Wort „mittel“. P2 ergänzt dort `THUNDER_LABEL_EN` (`none`, `light`, `medium`, `high`) als **parallele Tabelle** im Domänenmodul (kein `src/i18n`-Import in die Domänenschicht, Wächter #1365), `thunder_label(level, lang)` und `format_hail_note(hail_flag, lang)` (`Hagel: ja` / `Hail: yes`). `format_trend_tokens(stage, *, lang="de")` baut `_THUNDER_MAP` und `_TREND_THUNDER_LABELS` je Sprache; die Modulkonstanten `_THUNDER_MAP` (importiert von `thunder_branch.py`, `compare_html.py`) bleiben mit **deutschem** Wert bestehen. Telegram und SMS rufen `format_trend_tokens` weiter ohne `lang` auf (bleiben deutsch bis P7/P8). Die Satzbauer (`thunder_low_statement`, `thunder_headline_sentence`, Signalnamen) stellt P3 um.

**Metrik-Namen.** Überall, wo der ausgeschriebene Name gezeigt wird, `metric.label(lang)` statt `label_de`; Alarm-Kurzformen `alert_label_for(lang)`. `col_label`, `compact_label`, `sms_code` werden nicht angefasst (Wächter aus P1).

**Durchreichen.** `lang: Lang = "de"` ist überall nur Schlüsselwort. `render_email` reicht an `render_html`; `TripReportFormatter.format_email` an `render_email`; `NotificationService.send_trip_report` löst `lang` einmal auf und gibt es an `format_email` und `_send_email(report, lang=lang)`, das `lang` an `EmailOutput.send(..., lang=lang)` weitergibt (Kopf `X-GZ-Lang`, aus PV). `<html>` (Z. 1688) bleibt für Deutsch unverändert (Golden) und wird nur für Englisch zu `<html lang="en">`.

**Golden.** Deutsch: die fünf bestehenden Dateien `tests/golden/email/*-html.txt` (eingefrorene Uhr 2026-04-28 12:00 UTC aus `conftest.py`, Referenz-Fixtures GR20, GR221, Arlberg, Korsika) bleiben **unverändert** und müssen byte-gleich grün bleiben; sie sind der Deutsch-Beweis (das Verzeichnis `tests/golden/<paket>/` der Konventionen wird hier nicht doppelt angelegt). Englisch: `uv run python3 tests/golden/email/regenerate.py --lang en` schreibt die fünf `*-html.en.txt`; sie werden einmal von Hand gegen das Glossar gelesen und eingecheckt.

**Validator.** Vor dem Commit: `uv run python3 .claude/hooks/briefing_mail_validator.py --eml tests/fixtures/mail/briefing_full_de.eml` und `… briefing_full_en.eml` (beide Exit 0), außerdem `uv run pytest tests/tdd/test_issue_811_mode_matrix.py tests/tdd/test_briefing_modus_matrix_sprachen.py` (Renderer-Commit-Gate).

**Allowlist-Eintrag, der entfernt wird:** in `tests/fixtures/i18n_python_allowlist.json` (Python-Ratsche P11, sofern die Datei beim Umsetzen bereits existiert; sonst legt P11 sie ohne diese Einträge an) die Präfixe `src/output/renderers/email/html.py` und `src/output/renderers/email/helpers.py`.

**Token-Wächter.** `tests/test_metric_tokens_eingefroren.py` (P1) muss grün bleiben; keine Änderung an `col_label`, `compact_label`, `sms_code`.

## Expected Behavior

- **Input:** Ein Trip-Briefing mit Etappen, Anzeigekonfiguration, `lang` `"de"` oder `"en"` (aus dem Nutzerkonto).
- **Output:** HTML-Mail `full`: bei `en` durchgehend englische Texte (Namen von Trip, Etappen und Orten bleiben, wie der Nutzer sie vergeben hat); bei `de` byte-gleich zur heutigen Ausgabe. Kopf `X-GZ-Lang` entspricht der Sprache des Inhalts.
- **Side effects:** Keine neuen Schreibzugriffe. `NotificationService.send_trip_report` liest zusätzlich `user.json` (Sprache) über `resolve_user_lang`.

## Acceptance Criteria

- **AC-1:** Given Nutzer mit Sprache Englisch und ein Trip mit englisch-neutralen Namen und einer Etappe mit mittlerem Gewitter / When das Briefing `full` gerendert wird / Then enthält der sichtbare Text kein deutsches Wort außer Orts- und Trip-Namen, die Legende löst `Gust` als `Wind gusts` auf (nicht „Böen“), die Gewitter-Zelle zeigt `medium` statt „mittel“, und Datum, Wochentag und Fußzeile sind englisch.
  - Test: `tests/unit/test_briefing_html_sprache.py` — echter Aufruf von `TripReportFormatter.format_email(..., lang="en")` mit den Golden-Szenarien, Prüfung des sichtbaren Textes gegen eine Liste deutscher Signalwörter (`Böen`, `Nacht am Ziel`, `Ausblick`, `Aufstieg`, `Einheiten`, `Spalten`, `kein Regen`, `mittel`).

- **AC-2:** Given Nutzer mit Sprache Deutsch (oder `lang` nicht angegeben) / When dieselben fünf Referenz-Szenarien gerendert werden / Then ist die HTML-Ausgabe byte-gleich zur heutigen (Golden-Vergleich auf den unveränderten Dateien `tests/golden/email/*-html.txt`), und die englische Ausgabe derselben Szenarien ist byte-gleich zu den eingecheckten `*-html.en.txt`.
  - Test: `tests/golden/email/test_email_html_golden.py` (unverändert) und `tests/golden/email/test_email_html_golden_en.py`.

- **AC-3:** Given die deutsche und die englische Mail als `.eml` über `build_mime_message` / When `briefing_mail_validator.py --eml` jeweils läuft / Then ist der Exit-Code in beiden Fällen 0, und die englische Mail trägt den Kopf `X-GZ-Lang: en`.
  - Test: `tests/unit/test_briefing_html_sprache.py` — startet den Validator als Prozess gegen `briefing_full_de.eml` und `briefing_full_en.eml`. Der Lauf gegen eine live zugestellte englische Staging-Mail folgt in A2 (#2681).

- **AC-4:** Given die Modus-Matrix des Briefings (Format, Profil, Metrikauswahl) / When sie für `de` und `en` läuft / Then bleibt sie in beiden Sprachen grün, und die englische Ausgabe enthält in keinem Modus das deutsche Wort „Nacht“ oder „Ausblick“ als Überschrift.
  - Test: `tests/tdd/test_briefing_modus_matrix_sprachen.py` neben `tests/tdd/test_issue_811_mode_matrix.py` (unverändert grün).

- **AC-5:** Given Nutzer A mit `language: "en"` und Nutzer B ohne Feld, je mit eigenem Trip / When für beide nacheinander im selben Prozess der echte Versandpfad `send_trip_report` läuft / Then trägt A's Mail englischen Inhalt und `X-GZ-Lang: en`, B's Mail deutschen Inhalt und `X-GZ-Lang: de`, und in keiner Reihenfolge färbt die Sprache des einen auf den anderen ab.
  - Test: `tests/unit/test_briefing_mail_sprache_je_nutzer.py` — Muster `tests/unit/test_briefing_recipient_logging.py` (nur `EmailOutput._dial_and_send` als Netzrand ersetzt), zwei echte Nutzerverzeichnisse.

- **AC-6:** Given der Trip-Briefing-Pfad, die Ortsvergleichs-Mail und die Telegram-Kurzform / When sie die geteilten Legenden-, Fußzeilen- und Gewitter-Bausteine ohne `lang` aufrufen / Then liefern sie unverändert deutsche Texte (`Einheiten: …`, `Spalten: …`, `Ortsvergleich`, `mittel`), und mit `lang="en"` liefern sie `Units: …`, `Columns: …`, `Location comparison`, `medium`.
  - Test: `tests/unit/test_briefing_html_sprache.py` — direkte Aufrufe von `format_units_legend`, `format_column_legend`, `build_origin_footer`, `format_trend_tokens` und `format_hail_note` in beiden Sprachen.

## Known Limitations

- Annahme: Der Datumsstempel im Kopf (`Do · 29.10.2026 · 06:00 CEST`) behält in beiden Sprachen das Format `%d.%m.%Y`; nur der Wochentag folgt der Sprache. Eine englische Schreibweise des Datums wäre eine Änderung am deutschen Stempel und widerspricht dem Golden-Grundsatz.
- Annahme: Der Betreff der Mail (`TripReportFormatter._generate_subject`, `output/subject.py`) und der Etappenname, den der Scheduler erzeugt (`Etappe N: …`), bleiben bis P9a und P9b deutsch; der Etappen-Parser in `html.py` (Z. 1062) akzeptiert deshalb zusätzlich `Stage N: …`. Die live zugestellte englische Mail ist erst mit P9a/P9b vollständig englisch.
- Annahme: Die englischen Golden-Dateien nutzen dieselben Referenz-Fixtures und die eingefrorene Uhr der bestehenden Golden-Tests (statt der Konventionen-Uhr 2026-10-29T06:00+02:00), damit Deutsch und Englisch vergleichbar bleiben.
- Annahme: `src/app/thunder_scale.py` (Stufenwort `THUNDER_LABEL_EN`, Hagel-Notiz) gehört in keinen Paketumfang der Planung, wird aber von jeder Gewitter-Zelle gebraucht; P2 ergänzt nur die Stufenwörter, P3 die Satzbauer. Dieselbe Lücke betrifft P5, P7, P9b und P10, die die hier geschaffenen Funktionen mit `lang` aufrufen.
- `TripReportFormatter._build_units_legend` (`trip_report.py` Z. 730) hat keinen Aufrufer, steht aber in `KNOWN_VIOLATIONS` des Wächters `tests/test_resolution_loss_guard.py` und bleibt unverändert; die P11-Allowlist führt die Datei bis dahin.
- Die Vorschau (`preview_service.py`) ruft `format_email` ohne `lang` und bleibt deutsch bis P9a.
- Die Ampel- und Risikofarben, Zahlenformate (Punkt als Dezimaltrennzeichen) und Einheiten bleiben unverändert.

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** ADR-0104 (zusätzlich ADR-0042)
- **Rationale:** Die Mail spricht die Sprache des Nutzers, die Kürzel der Tabellen bleiben Platzform (ADR-0042) und werden in der Legende in der Nutzersprache aufgelöst.

## Changelog

- 2026-10-30: Initial spec created (Planung Epic #2644)
