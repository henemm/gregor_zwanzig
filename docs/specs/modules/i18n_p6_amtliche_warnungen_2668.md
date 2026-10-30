---
entity_id: i18n_p6_amtliche_warnungen_2668
type: module
created: 2026-10-30
updated: 2026-10-30
status: approved
version: "1.0"
tags: [i18n, epic-2644, issue-2668, python, model-haiku]
---

# i18n P6: Amtliche Warnungen zweisprachig (Rahmentexte, Sprachblock-Wahl, alle vier Kanäle)

**Issue:** #2668 · **Epic:** #2644 · **Modell:** Haiku · **Konventionen:** docs/features/epic-i18n-de-en-konventionen.md Abschnitt(e) 2, 4, 6

## Approval

- [x] Approved (PO-Freigabe 2026-10-30)

## Purpose

Wer Englisch gewählt hat, bekommt amtliche Warnungen (Standalone-Warnmail, Warn-Block in Briefing und Ortsvergleich, Entwarnung, Telegram, SMS) mit englischem Rahmen: Stufenwörter (`YELLOW`, `ORANGE`, `RED`), Gefahrenarten (`Heat`, `Thunderstorm`), Gültigkeit (`Valid`, `all day`), Quellenzeile und Hinweise. Der amtliche Text selbst wird nicht übersetzt; liefert MeteoAlarm einen englischen Sprachblock, wird er bei `en` bevorzugt, sonst bleibt die Quellsprache und ein Katalog-Hinweis nennt sie (`Source text in French`). Orts-, Département- und Regionsnamen sowie Behördennamen bleiben unverändert. Deutsch bleibt byte-gleich.

## Source

- **File:** `src/output/renderers/alert/official_alerts.py`, `src/services/official_alerts/models.py`, `src/services/official_alerts/meteoalarm.py`, `src/services/compare_official_alert.py`, `.claude/hooks/official_alert_mail_validator.py`
- **Identifier:** `_LEVEL_WORDS` (official_alerts.py:43), `_HAZARD_LABELS` (65), `_SOURCE_LABELS` (105), `_AUTHORITY_NOTES` (141), `_EAWS_WORDS` (147), `_display_label` (874), `_de_weekday_short` (919), `_format_validity` (924), `_typ_tag` (954), `_join_de` (1073), `render_official_alert_html` (1568), `render_official_alert_mail_plain` (1655), `render_warn_block` (1958), `render_official_alert_telegram` (1991), `render_official_alert_sms` (2246), `build_official_alert_notices` (2335), `build_compare_official_alert_notices` (2425), `render_official_allclear_*` (2542-2640), `OfficialAlert` (models.py:19), `_pick_preferred_entry` / `_group_and_map_info_entries` (meteoalarm.py:102/147)

> **Schicht-Hinweis:** Reiner Python-Core (`src/output/renderers/alert/`, `src/services/official_alerts/`, `src/services/`). Kein Go-, kein Frontend-Code. Die Warn-Abrufe (`warn_egress.py`) werden **prozessweit zwischengespeichert, nicht je Nutzer**; deshalb darf die Sprachwahl nicht beim Parsen fallen, sondern erst beim Darstellen (siehe Implementation Details).

> **Querschnitts-Prüfpunkte:**
> - **Trip/Ortsvergleich-Teilung:** Alle Warn-Bausteine sind bereits geteilt (Trip und Ortsvergleich nutzen `render_warn_block`, `build_*_official_alert_notices`, `render_official_alerts_html`, ADR-0011). Es entsteht kein Compare-Pendant; alle Texte liegen in `warnung.*`. Der compare-eigene Anteil (`compare_official_alert.py`) reicht `lang` nur durch.
> - **Mandantentrennung:** Zwischengespeicherte Warnungen sind nutzerübergreifend gemeinsam. Der Test AC-6 beweist mit **zwei Nutzern verschiedener Sprache auf demselben Cache-Objekt**, dass jeder Nutzer seine Sprache sieht und der gemeinsame Zustand unverändert bleibt. `user_id` und `resolve_user_lang(user_id)` kommen aus dem Auth-Kontext in P9b; dieses Paket nimmt `lang` nur als Parameter.
> - **Kanäle:** Alarm-/Briefing-Inhalt. Alle vier: E-Mail (HTML/Klartext, `render_official_alert_html`, `render_official_alert_mail_plain`, Warn-Block), Telegram (`render_official_alert_telegram`, `render_official_allclear_telegram`; **in diesem Paket erledigt**, P7 prüft nur), SMS (`render_official_alert_sms`, Kürzel bleiben) und Premium-SMS (derselbe SMS-Text).

### Affected Files

| Datei | CREATE/MODIFY | Zweck |
|---|---|---|
| `src/output/renderers/alert/official_alerts.py` | MODIFY | `lang: Lang = "de"` (keyword-only) an allen Text erzeugenden Funktionen; Konstanten-Wörterbücher `_LEVEL_WORDS`, `_HAZARD_LABELS`, `_LEVEL_POSITION_WORD`, `_EAWS_WORDS`, `_ELEVATION_WORDS`, `_TIME_OF_DAY_WORDS`, `_AUTHORITY_NOTES` werden Katalogschlüssel; `_format_validity`, `_join_de`, `_display_label`, Entwarnung, Telegram- und SMS-Renderer |
| `src/services/official_alerts/models.py` | MODIFY | `OfficialAlert` bekommt additiv `label_by_lang: tuple[tuple[str, str], ...] = ()` und `label_lang: str = ""` (frozen bleibt, `label` bleibt unverändert) |
| `src/services/official_alerts/meteoalarm.py` | MODIFY | `_group_and_map_info_entries` füllt `label_by_lang` (alle Sprachblöcke der Gruppe, Schlüssel = Sprachcode in Kleinbuchstaben, zwei Zeichen) und `label_lang` (Sprache des gewählten `label`); `_pick_preferred_entry` und `label` bleiben unverändert (Standard `de`, dann `en`, dann erster) |
| `src/services/official_alerts/meteoalarm_feed.py` | unverändert | liefert die Sprache je Block bereits (`"lang": info.get("language")`, Zeile 199); durch Test abgesichert |
| `src/services/official_alerts/vigilance.py`, `meteo_forets.py`, `geosphere_warn.py` | unverändert | geprüft 2026-10-30: ihre `label`-Texte (`Sturmböen`, `Extreme Hitze`, `Waldbrand-Gefahr — Stufe N`, `Hitze` …) sind interne deutsche Kennungen für Dedup, Melde-Gedächtnis (`label:{alert.label}`) und die Anzeige-Heuristik; sie ändern sich nicht. Die englische Anzeige entsteht im Renderer aus `hazard` |
| `src/services/official_alerts/warn_egress.py`, `department_mapper.py`, `fr_departments.py` | unverändert | geprüft: `warn_egress.py` hat nur Logs und Code, keinen Nutzertext; Département-/Regionsnamen werden NICHT übersetzt |
| `src/services/compare_official_alert.py` | MODIFY | `lang` an die Notice-Builder und Renderer durchreichen (Parameter mit Default `de`); Log-Zeilen mit Umlaut erhalten `# i18n-log` |
| `src/i18n/messages/de/warnung.json`, `src/i18n/messages/en/warnung.json` | MODIFY | Neue Schlüssel `warnung.*` (nur diese Bereichsdateien anfassen) |
| `.claude/hooks/official_alert_mail_validator.py` | MODIFY | `_VERDICT_RE` (52), `_LEVEL_WORD_RE` (60), `_AVALANCHE_LEVEL_RE`/`_EAWS_WORDS` (68-69), `_OTHER_HAZARD_RE` (78), `_VALIDITY_RE`/`_VALIDITY_VALUE_RE` (86/90), `_SOURCE_ROW_RE` (102), `_ALLCLEAR_TRANSITION_RE` (160), Literale „abgerufen bei“ (315): aus `t(key, lang)`; `lang` aus `X-GZ-Lang` (PV-Gerüst) |
| `tests/fixtures/mail/official_alert_mail_en.eml` | CREATE | Englische Beispiel-Mail (Standalone-Warnung) aus dem Renderer-Pfad |
| `tests/golden/amtliche_warnungen/*.de.html`, `*.de.txt`, `*.en.html`, `*.en.txt` | CREATE | Golden `de` (VOR der Umstellung erzeugen) und Referenz `en`: einzelne Warnung, gemischte Stufen, Lawinen-Lagebericht, Entwarnung, Telegram, SMS |
| `tests/golden/test_amtliche_warnungen_golden.py` | CREATE | Byte-Vergleich `de` |
| `tests/test_amtliche_warnungen_zweisprachig.py` | CREATE | Verhaltenstests der ACs |
| `tests/test_amtliche_warnungen_sprachblock.py` | CREATE | Sprachblock-Wahl und Zwei-Nutzer-Test auf gemeinsamem Cache-Objekt |
| `tests/test_amtliche_warnungen_validator_zweisprachig.py` | CREATE | Validator gegen `de`- und `en`-Fixture |

## Estimated Scope

- **LoC:** ca. 260 Code (official_alerts.py ~170, meteoalarm.py ~25, models.py ~5, compare_official_alert.py ~15, Validator ~45); ohne Katalogdaten und Tests. Das überschreitet knapp das Limit von 250: `workflow.py set-field loc_limit_override 500` einplanen.
- **Files:** 7 Code-/Hook-Dateien, 2 Katalogdateien plus Tests und Golden-Dateien
- **Effort:** high für Haiku (`official_alerts.py` hat 2.650 Zeilen und eng gekoppelte Heuristiken); bei zweitem Fehlversuch Sonnet

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| #2662 P1 | Paket | `t`, `tn`, `fmt_weekday`, `fmt_date`, `fmt_time` |
| #2663 PV | Paket | `X-GZ-Lang`, sprachfähiger Validator-Rahmen |
| #2664 P2 / #2665 P3 | Pakete | `build_origin_footer`/`render_origin_footer_*` und `unavailable_hint` akzeptieren `lang`; P6 ruft sie mit `lang=lang` |
| #2666 P4, #2667 P5 (davor) | Pakete | rufen `render_warn_block` und `render_official_alerts_html` bisher ohne `lang`; mit P6 bekommen sie ihre Sprache (Aufrufstellen in `compare_html.py` und `alert/render.py` nur um `lang=lang` ergänzen) |
| #2669 P7 (danach) | Paket | prüft den Telegram-Zweig, ändert ihn nicht mehr |
| #2672 P9b (danach) | Paket | reicht `lang` aus `trip_alert`/`compare_official_alert`-Orchestrierung durch und ersetzt `_de_weekday_short` in `trip_alert.py` |
| `services.official_alerts.models.OfficialAlert` | Modul | Datenklasse der Warnung |
| ADR-0104, ADR-0011, ADR-0089 | ADR | Sprache am Nutzer; geteilte Warn-Bausteine; EAWS-Skala |

## Implementation Details

**Katalog-Namensraum:** `warnung` (`src/i18n/messages/{de,en}/warnung.json`). Nur diese beiden Dateien anfassen. das im Glossar verbotene Produktwort ist untersagt.

**Signaturen (Abschnitt 4):** `*, lang: Lang = "de"` keyword-only an jeder Text erzeugenden Funktion (`_display_label(alert, *, lang="de")`, `_format_validity(alert, tz=None, *, lang="de")`, `render_official_alert_html(...)`, `render_official_alert_mail_plain(...)`, `render_warn_block(...)`, `render_official_alert_telegram(...)`, `render_official_alert_sms(...)`, `build_official_alert_notices(...)`, `build_compare_official_alert_notices(...)`, `official_alert_authority_notes(alerts, *, lang="de")`, die `render_official_allclear_*`-Funktionen). Kein Modul-Zustand. `_de_weekday_short(dt)` bleibt als dünner Wrapper auf `fmt_weekday(dt, "de")` erhalten (bis P9b ihn in `trip_alert.py` ablöst); neu `_weekday_short(dt, lang)`.

**Beispiel-Schlüssel (de wörtlich wie heute, en laut Glossar):**

| Schlüssel | de | en | Stelle |
|---|---|---|---|
| `warnung.stufe.gruen` | `GRÜN` | `GREEN` | `_LEVEL_WORDS`, official_alerts.py:44 |
| `warnung.stufe.gelb` | `GELB` | `YELLOW` | :45 |
| `warnung.stufe.orange` | `ORANGE` | `ORANGE` | :46 |
| `warnung.stufe.rot` | `ROT` | `RED` | :47 |
| `warnung.stufe.position.hoechste` | `höchste` | `highest` | `_LEVEL_POSITION_WORD`, :62 |
| `warnung.gefahr.extreme_heat` | `Hitze` | `Heat` | `_HAZARD_LABELS`, :66 |
| `warnung.gefahr.thunderstorm` | `Gewitter` | `Thunderstorm` | :67 |
| `warnung.gefahr.rain` | `Starkregen` | `Heavy rain` | :70 |
| `warnung.gefahr.access_ban` | `Zugang gesperrt` | `Access closed` | :74 |
| `warnung.gefahr.wildfire_risk` | `Waldbrand-Gefahr` | `Wildfire risk` | :82 |
| `warnung.gefahr.flood` | `Hochwasser/Erdrutsch` | `Flood/landslide` | :85 |
| `warnung.gefahr.avalanche_bulletin` | `Lawinenstufe` | `Avalanche level` | :88 |
| `warnung.eaws.erheblich` | `erheblich` | `considerable` | `_EAWS_WORDS`, :147 |
| `warnung.kopf.warnstufe` | `Warnstufe` | `Warning level` | render_official_alert_telegram, :2038 |
| `warnung.kopf.hoechste_stufe` | `höchste Stufe` | `highest level` | :2038 |
| `warnung.verdict.anzahl.one` / `.other` | `{count} amtliche Warnung` / `{count} amtliche Warnungen` | `{count} official warning` / `{count} official warnings` | Verdict-Zeile, Validator `_VERDICT_RE` |
| `warnung.zeit.ganztaegig` | `ganztägig` | `all day` | `_format_validity`, :941 |
| `warnung.zeit.unbekannt` | `unbekannt` | `unknown` | :929 |
| `warnung.zeile.gueltig` | `Gültig` | `Valid` | :821 |
| `warnung.zeile.quelle` | `Quelle` | `Source` | :1712 |
| `warnung.zeile.abgerufen_bei` | `abgerufen bei {quelle}` | `retrieved from {quelle}` | :1638, :1723 |
| `warnung.entwarnung.titel` | `Entwarnung` | `All clear` | :2546, :2560 |
| `warnung.hinweis.massgeblich_slf` | `Maßgeblich ist der Originalbericht des SLF.` | `The original SLF report is authoritative.` | `_AUTHORITY_NOTES`, :142 |
| `warnung.hinweis.quelltext_sprache` | `Quelltext: {sprache}` | `Source text in {sprache}` | neu |
| `warnung.sprache.fr` | `Französisch` | `French` | neu |
| `warnung.sprache.it` / `.sl` / `.hr` / `.es` / `.de` / `.en` | `Italienisch` / `Slowenisch` / `Kroatisch` / `Spanisch` / `Deutsch` / `Englisch` | `Italian` / `Slovenian` / `Croatian` / `Spanish` / `German` / `English` | neu |

Weitere Schlüssel nach demselben Muster: alle übrigen Gefahrenarten und EAWS-Wörter (`mäßig` -> `moderate`, `gering` -> `low`, `groß` -> `high`, `sehr groß` -> `very high`), die acht Lawinenproblem-Namen (`Triebschnee` -> `wind slab`, `Altschnee` -> `persistent weak layers`, `Neuschnee` -> `new snow`, `Nassschnee` -> `wet snow`, `Gleitschnee` -> `gliding snow`, `Wechten` -> `cornices`, `kein ausgeprägtes Lawinenproblem` -> `no distinct avalanche problem`, `günstige Situation` -> `favourable situation`), `oberhalb`/`unterhalb` -> `above`/`below`, `vormittags`/`nachmittags` -> `in the morning`/`in the afternoon`, `und` (für `_join_de`, in `allgemein.json`: `allgemein.liste.und` / `and`), die Quellen-Zusätze `Präfektur (Zugangssperre)` -> `Prefecture (access closure)`, `Météo-France (Waldbrand)` -> `Météo-France (wildfire)`. Unbekannter Sprachcode im Hinweis: der Code in Großbuchstaben (`NL`).

**Eigennamen bleiben:** `DWD`, `MeteoAlarm`, `Météo-France`, `GeoSphere Austria`, `Protezione Civile (DPC)`, `Lawinenwarndienst Tirol/Südtirol/Trentino/Kärnten, avalanche.report` und `WSL-Institut für Schnee- und Lawinenforschung SLF` (Behördennamen), alle Orts-, Département- und Regionsnamen, Massiv-Namen. `_SOURCE_LABELS` wird nur an den beschreibenden Klammerzusätzen und dem Sammelwort `Lawinenwarndienste, avalanche.report` angepasst.

**Sprachblock-Wahl (Mandantentrennung!):** Die Warnungen liegen im prozessweiten Cache. Deshalb wird beim Parsen **nichts** nach Nutzersprache gewählt. `_group_and_map_info_entries` (meteoalarm.py:147) sammelt zusätzlich `label_by_lang = tuple((entry_lang[:2].lower(), event or headline) ...)` über alle Blöcke der Gruppe und `label_lang` = Sprachcode des bisher gewählten `label` (`_pick_preferred_entry`, Reihenfolge `de`, `en`, erster, UNVERÄNDERT, damit Dedup-Schlüssel und Melde-Gedächtnis `label:{alert.label}` stabil bleiben). Der Renderer wählt zur Anzeige mit der neuen Funktion `_label_for_lang(alert, lang) -> tuple[str, str]` (Text, Sprachcode): `lang == "en"` nimmt den `en`-Block, sonst `de`-Block, sonst `alert.label` (Sprache `label_lang`); `lang == "de"` nimmt den `de`-Block, sonst `alert.label`. Ein Block mit leerem Text zählt nicht.

**Anzeige-Titel `_display_label(alert, lang)`:** Für `lang == "de"` bleibt die gesamte bestehende Logik wörtlich erhalten (Fälle a bis d, `_SOURCE_LEVEL_SUFFIX`). Für `lang == "en"`: Typ-Wort `typ_en = t("warnung.gefahr.<hazard>", "en")`; Text aus `_label_for_lang`; zuerst das Quell-Stufen-Suffix entfernen (`_SOURCE_LEVEL_SUFFIX`); enthält der Text das Detail-Trennzeichen `—` (Massiv-Name, z. B. `Zugang gesperrt — Monts Toulonnais`), dann `typ_en + " — " + Detail` (Detail ist ein Eigenname und bleibt); stammt der Text aus einem Block mit `lang == "en"` und enthält `typ_en`, dann der Blocktext; sonst `typ_en`. Der Lawinen-Lagebericht (`avalanche_bulletin_text`) baut seinen Wortlaut aus `warnung.eaws.*` und `warnung.gefahr.avalanche_bulletin`.

**Quelltext-Hinweis:** `official_alert_authority_notes(alerts, *, lang)` (official_alerts.py:215) liefert zusätzlich `t("warnung.hinweis.quelltext_sprache", lang, sprache=<Sprachname>)` für jede Warnung, deren **angezeigter** Text der rohe Behördentext ist (nicht das Katalog-Typ-Wort) und dessen Sprache nicht `lang` ist. Der Hinweis erscheint nur in Langform (Mail, Telegram), nie in der SMS (wie `_AUTHORITY_NOTES`).

**Beispiel-Umstellung 1 (official_alerts.py:924-942, `_format_validity`), vorher:**

```
if not alert.valid_from or not alert.valid_to:
    return "unbekannt"
...
tag, date_str = _de_weekday_short(vf), vf.strftime("%d.%m.")
...
    return f"{tag} {date_str} · ganztägig"
```

**nachher** (`fmt_date(..., "kurz")` liefert für `de` genau `Fr 10.07.`, also byte-gleich):

```
if not alert.valid_from or not alert.valid_to:
    return t("warnung.zeit.unbekannt", lang)
...
tag_datum = fmt_date(vf, lang, "kurz")
...
    return f"{tag_datum} · {t('warnung.zeit.ganztaegig', lang)}"
```

**Beispiel-Umstellung 2 (official_alerts.py:2036-2040, Telegram-Kopf), vorher:**

```
_emoji, leading_word = _LEVEL_WORDS.get(leading.alert.level, ("🔴", "ROT"))
kind = "Warnstufe" if uniform else "höchste Stufe"
head = f"{prefix} · {scope_part}{kind} {leading_word} ({pos}/3)"
```

**nachher** (`_LEVEL_WORDS` hält nur noch Emoji und Schlüssel, z. B. `4: ("🔴", "warnung.stufe.rot")`):

```
_emoji, leading_key = _LEVEL_WORDS.get(leading.alert.level, ("🔴", "warnung.stufe.rot"))
kind = t("warnung.kopf.warnstufe" if uniform else "warnung.kopf.hoechste_stufe", lang)
head = f"{prefix} · {scope_part}{kind} {t(leading_key, lang)} ({pos}/3)"
```

Wichtig: `_LEVEL_WORDS` wird auch von `compare_html.py:915` gelesen (`_LEVEL_WORDS.get(...)[1]`). Dort den Zugriff auf den Schlüssel umstellen: `t(_LEVEL_WORDS.get(level, ("🔴", "warnung.stufe.rot"))[1], lang)`. Beide Stellen mit Grep `_LEVEL_WORDS` finden.

**Nicht ändern:** SMS-Kürzel und Stufenbuchstaben (`_SMS_LEVEL_LETTERS`, `HAZARD_SMS_SYMBOLS`), Regions-/Département-Namen, Behördennamen, CSS-Klassennamen (`gruen`, `gelb`, `rot` in `_LEVEL_CLASS` – strukturell, vom Validator gelesen), `OfficialAlert.label` und alle Dedup-/Melde-Gedächtnis-Schlüssel (`official_alert_state_key`), `logger`-Texte.

**Allowlist-Eintrag, der entfällt:** In `tests/fixtures/i18n_python_allowlist.json` (Ratsche P11) die Präfixe `src/output/renderers/alert/official_alerts.py` und `src/services/compare_official_alert.py` entfernen (vorher `Glob tests/fixtures/i18n_python_allowlist.json`; existiert sie noch nicht, holt P11 den Schritt nach).

**Golden-Fixture:** Deterministisch (feste Zeit `2026-10-29T06:00+02:00`, Nutzer `golden-de`, feste `OfficialAlert`-Objekte, keine Netz-Abrufe). **Zuerst** `*.de.*` mit dem unveränderten Code erzeugen und committen, danach umstellen.

**Validator:** `uv run python3 .claude/hooks/official_alert_mail_validator.py` bildet seine Erwartungen aus dem Katalog (`t(key, lang)`), `lang` aus `X-GZ-Lang`. Die fachlichen Zusicherungen (Stufenträger, Gültigkeits-Zeile, Quellenzeile, Lawinenstufe plausibel) bleiben dieselben; nur Wortlisten und Muster wechseln die Sprache. Der Staging-Lauf mit echter `en`-Mail (Postfach `+en`) gehört zu `/e2e-verify`.

**Pflicht für den Developer-Agenten:** (1) RED-Tests der ACs grün, (2) deutsche Golden-Ausgabe byte-gleich, (3) Allowlist-Eintrag entfernen, (4) Paritäts- und Ratschen-Test grün, (5) keine Änderung an `col_label`/`compact_label`/`sms_code`/Kürzeln. Nicht tun: andere Bereichsdateien ändern, Schlüssel umbenennen, deutsche Texte „verbessern“, neue Abhängigkeiten, Dedup-Schlüssel oder `label` verändern.

## Expected Behavior

- **Input:** Liste `OfficialAlert` (aus dem gemeinsamen Cache oder Test-Objekten), Trip- oder Ortsvergleich-Kontext, `lang`.
- **Output:** Warnmail (HTML + Klartext), Warn-Block in Briefing und Ortsvergleich, Telegram- und SMS-Text, Entwarnung. `de` byte-gleich zu heute. `en`: Rahmen, Stufen- und Gefahrenwörter, Gültigkeit, Quelle, Entwarnung englisch; angezeigter Behördentext aus dem `en`-Block, falls vorhanden, sonst Quellsprache mit Hinweis `Source text in <Sprache>`; Namen, Kürzel und Stufenbuchstaben unverändert.
- **Side effects:** Keine. Der Cache und die `OfficialAlert`-Objekte werden nie verändert (frozen); `label` und Dedup-Schlüssel bleiben.

## Acceptance Criteria

- **AC-1:** Given eine MeteoAlarm-Warnung mit `de`- und `en`-Info-Block und Sprache `en` / When die Standalone-Warnmail und der Telegram-Text gerendert werden / Then ist der Rahmen englisch (`ORANGE`, `Warning level`, `Valid`, `Source`) und der Text des `en`-Blocks wird verwendet; mit Sprache `de` wird der `de`-Block verwendet.
  - Test: tests/test_amtliche_warnungen_sprachblock.py — baut die Warnung über `_group_and_map_info_entries` aus beiden Blöcken, rendert in beiden Sprachen und prüft über `t(key, lang)` den Rahmen und den gewählten Blocktext.

- **AC-2:** Given eine Warnung, deren einziger Sprachblock Französisch ist und deren Behördentext angezeigt wird (Label mit Detail-Trenner `—`, z. B. `Orages — Chablais`), und Sprache `en` / When die Warnmail gerendert wird / Then ist der Rahmen englisch, der Behördentext bleibt französisch und der Hinweis `Source text in French` aus dem Katalog steht in Mail und Telegram, nicht in der SMS.
  - Test: tests/test_amtliche_warnungen_sprachblock.py — Hinweis über `t("warnung.hinweis.quelltext_sprache", "en", sprache=t("warnung.sprache.fr", "en"))`; kein Hinweis in `render_official_alert_sms`; kein Hinweis, wenn nur das Katalog-Typ-Wort angezeigt wird.

- **AC-3:** Given Sprache `de` / When alle Golden-Fälle (einzelne Warnung, gemischte Stufen, Lawinen-Lagebericht, Entwarnung) über E-Mail, Telegram und SMS gerendert werden / Then ist jede Ausgabe byte-gleich zu den vorab eingecheckten `*.de.*`-Dateien.
  - Test: tests/golden/test_amtliche_warnungen_golden.py — Byte-Vergleich je Fall und Kanal.

- **AC-4:** Given Sprache `en` / When eine Warnung des Typs Waldbrand-Gefahr aus `meteo_forets.py` (Label `Waldbrand-Gefahr — Stufe 3`, Département `Haute-Corse`) und eine Zugangssperre (`Zugang gesperrt — Monts Toulonnais`) gerendert werden / Then lauten die Titel `Wildfire risk` und `Access closed — Monts Toulonnais`, das Quell-Stufen-Suffix `Stufe 3` erscheint nicht, und Département- und Massivname bleiben unverändert.
  - Test: tests/test_amtliche_warnungen_zweisprachig.py — prüft Titel in Mail, Telegram und Betreff; keine deutschen Katalogwörter außerhalb der Eigennamen.

- **AC-5:** Given die englische Beispiel-Mail `official_alert_mail_en.eml` (Header `X-GZ-Lang: en`) und die deutsche Mail (Header `de`) / When `official_alert_mail_validator.py` gegen beide läuft / Then endet jeder Lauf mit Exit 0; mit vertauschtem Header endet er mit Exit ungleich 0.
  - Test: tests/test_amtliche_warnungen_validator_zweisprachig.py — `validate_message` auf beiden Fixtures und dem Fehlfall.

- **AC-6:** Given zwei Nutzer, `golden-en` (Sprache `en`) und `golden-de` (Sprache `de`), die dieselbe zwischengespeicherte Warnung (dasselbe Objekt) erhalten / When beide nacheinander (`en`, dann `de`, dann `en`) rendern / Then sieht jeder seine Sprache, die Objekte und ihre `label`/Dedup-Schlüssel sind danach unverändert, und der Melde-Gedächtnis-Schlüssel ist für beide gleich.
  - Test: tests/test_amtliche_warnungen_sprachblock.py — gleiche Instanz, drei Aufrufe, Vergleich von `official_alert_state_key` vor und nach dem Rendern.

- **AC-7:** Given Sprache `en` und der Lawinen-Lagebericht (EAWS Stufe 3) / When Mail und SMS gerendert werden / Then lautet die Stufe `Avalanche level 3 (considerable)`, der SLF-Behördenname bleibt unverändert, und die SMS-Token (Kürzel, Stufenbuchstabe) sind identisch zur deutschen SMS.
  - Test: tests/test_amtliche_warnungen_zweisprachig.py — Vergleich der SMS-Token zwischen den Sprachen, Stufenwort über `t("warnung.eaws.erheblich", "en")`.

## Known Limitations

- Der amtliche Warntext wird nie maschinell übersetzt; fehlt ein `en`-Block, bleibt die Quellsprache mit Hinweis. Die Anzeige-Heuristik zeigt Rohtexte der Behörde nur in den bestehenden Fällen (Detail-Trenner, Typ-Wort im Text, unbekannte Gefahrenart); sonst zeigt sie das Katalog-Typ-Wort.
- Annahme: `render_official_alert_telegram` und die Entwarnungs-Telegram-Funktion werden in diesem Paket erledigt (sie teilen `_display_label`, `_LEVEL_WORDS`, `_format_validity`); P7 prüft nur noch.
- Annahme: Die Wahl des Sprachblocks fällt erst beim Darstellen; die Warn-Caches bleiben nutzerunabhängig. `OfficialAlert.label` bleibt die deutsch bevorzugte Kennung (Dedup, Melde-Gedächtnis).
- Annahme: `_de_weekday_short` bleibt als Wrapper für `trip_alert.py` bis P9b.
- Annahme: Das Schlüsselwort `vormittags/nachmittags` wird `in the morning/in the afternoon`; weitere EAWS-Zeitwörter nur bei Bedarf.
- Bis P9b sendet das System die Warnungen weiter deutsch (keine Durchreichung von `lang`).

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** ADR-0104 (zusätzlich ADR-0011 für die geteilten Warn-Bausteine, ADR-0089 für die EAWS-Skala)
- **Rationale:** Die Sprache gehört dem Nutzer und wird erst beim Darstellen angewandt, weil die Warn-Daten nutzerübergreifend zwischengespeichert sind; Behördentexte und Eigennamen bleiben im Original.

## Changelog

- 2026-10-30: Initial spec created (Planung Epic #2644)
