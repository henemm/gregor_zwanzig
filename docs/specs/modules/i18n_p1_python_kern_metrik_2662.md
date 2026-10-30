---
entity_id: i18n_p1_python_kern_metrik_2662
type: module
created: 2026-10-30
updated: 2026-10-30
status: approved
version: "1.0"
tags: [i18n, epic-2644, issue-2662, python, model-sonnet]
---

# i18n P1: Python-i18n-Kern — Katalog `src/i18n`, `t()`, Datums-/Wochentagsformat, Metrik-Register `label_en`/`alert_label_en`, `GET /api/metrics`

**Issue:** #2662 · **Epic:** #2644 · **Modell:** Sonnet · **Konventionen:** docs/features/epic-i18n-de-en-konventionen.md Abschnitte 2, 4 (inkl. Tabelle „Englische Namen der Wettergrößen“)

## Approval

- [x] Approved (PO-Freigabe 2026-10-30)

## Purpose

Alle Python-Renderer (E-Mail, Telegram, SMS, Premium-SMS, Alarme, Inbound-Antworten) sollen ihre Nutzertexte künftig aus **einer** Stelle in der Sprache des Nutzers beziehen; ohne diesen Kern kann kein Kanal Englisch. Dieses Paket legt den Katalog `src/i18n` mit `t()`, `tn()` und den Formatfunktionen an (alle Bereichsdateien zunächst leer) und gibt dem Metrik-Register englische Anzeigenamen für die Formen „voll“ und „Alarm-Kurzform“. Die Protokoll-Token (`sms_code`, `compact_label`, `col_label`) bleiben unangetastet und werden durch einen Wächter-Test eingefroren; die deutsche Ausgabe ändert sich nicht.

## Source

- **File:** `src/i18n/__init__.py` (neu), `src/i18n/catalog.py` (neu), `src/i18n/lang.py` (aus S1), `src/i18n/format.py` (neu), `src/app/metric_catalog.py`, `api/routers/config.py`
- **Identifier:** `t`, `tn`, `resolve_user_lang`, `fmt_date`, `fmt_weekday`, `fmt_time`, `relative_day`, `MetricDefinition.label_en` / `alert_label_en` / `friendly_label_en`, `MetricDefinition.label()` / `alert_label_for()` / `friendly_label_for()`, `aggregation_label`, `get_metrics` (Route `GET /api/metrics`)

> **Schicht-Hinweis:** Python-Core. `src/i18n/**` ist ein neues Paket neben `src/app`, `src/output`, `src/services` (Import wie bei den übrigen Paketen: `from i18n import t`). `api/routers/config.py` ist die FastAPI-Route hinter dem Go-Proxy. Kein Go-, kein Frontend-Code (F5 und F7 konsumieren `label_en` später).
>
> **Querschnitts-Prüfpunkte:**
> - **Trip/Ortsvergleich-Teilung:** Das Register ist bereits die gemeinsame Quelle für Trip (`email/helpers.py`) und Ortsvergleich (`compare_metric_catalog.py`); die neuen Felder und Methoden erben das. Es entsteht kein Pendant. Gemeinsame Texte beider Seiten liegen später in `allgemein.*`.
> - **Mandantentrennung:** Es gibt keine prozessglobale Sprache. `resolve_user_lang(user_id)` liest `data/users/<user_id>/user.json` über `get_data_dir()` und ist die einzige Auflösung; `t()` und die Formatfunktionen sind reine Funktionen mit ausdrücklichem `lang`. Ein Fehlen des Feldes oder der Datei bedeutet `de`, nie ein Standardnutzer `default`.
> - **Kanäle:** Berührt noch keinen Kanal-Inhalt. Der Kern dient allen vier Kanälen (E-Mail, Telegram, SMS, Premium-SMS) gleichermaßen; Kurzform bleibt Platzform (ADR-0042), die Token ändern sich nicht.

### Affected Files

| Datei | CREATE/MODIFY | Zweck |
|---|---|---|
| `src/i18n/__init__.py` | CREATE | `Lang`, `t()`, `tn()`; Re-Export von `resolve_user_lang`, `fmt_date`, `fmt_weekday`, `fmt_time`, `relative_day` |
| `src/i18n/catalog.py` | CREATE | Laden von `messages/{de,en}/<bereich>.json`, Fallback und Einmal-Log |
| `src/i18n/lang.py` | MODIFY (von S1 angelegt; fehlt sie, CREATE) | `resolve_user_lang(user_id, data_dir=None) -> Lang`, einzige Auflösung |
| `src/i18n/format.py` | CREATE | `fmt_date`, `fmt_weekday`, `fmt_time`, `relative_day` |
| `src/i18n/messages/de/{allgemein,mail,vergleich,alarm,warnung,telegram,sms,versand,inbound,api}.json` | CREATE | 10 Bereichsdateien, Inhalt `{}` |
| `src/i18n/messages/en/{allgemein,mail,vergleich,alarm,warnung,telegram,sms,versand,inbound,api}.json` | CREATE | 10 Bereichsdateien, Inhalt `{}` |
| `src/app/metric_catalog.py` | MODIFY | Felder `label_en`, `alert_label_en`, `friendly_label_en` (nach Z. 102), Methoden, Tabelle `_ENGLISH_NAMES`, `aggregation_label()`, `get_alert_label(metric_id, lang="de")` |
| `api/routers/config.py` | MODIFY | `get_metrics()` (Z. 93–147) um `label_de`, `label_en`, `alert_label`, `alert_label_en` und `label_en` je Auswertung erweitern |
| `docs/reference/api_contract.md` | MODIFY | Zeile `/api/metrics` (Z. 245): die neuen Felder nennen |
| `tests/fixtures/metric_tokens_frozen.json` | CREATE | `{metric_id: {"col_label", "compact_label", "sms_code"}}` aus dem Ist-Stand |
| `tests/test_metric_tokens_eingefroren.py` | CREATE | Wächter, byte-genauer Vergleich |
| `tests/unit/test_i18n_t_platzhalter_plural_fallback.py` | CREATE | Test zu AC-1 |
| `tests/unit/test_i18n_katalog_paritaet.py` | CREATE | Test zu AC-2 |
| `tests/unit/test_i18n_format_datum_wochentag.py` | CREATE | Test zu AC-3 |
| `tests/unit/test_metric_catalog_englische_namen.py` | CREATE | Test zu AC-4 |
| `tests/unit/test_metrics_endpoint_englische_namen.py` | CREATE | Test zu AC-6 |
| `tests/unit/test_i18n_sprache_zwei_nutzer.py` | CREATE | Test zu AC-7 |

## Estimated Scope

- **LoC:** ca. 270 Code ohne Katalog- und Registerdaten und ohne Tests (`catalog.py` ~70, `__init__.py` ~60, `format.py` ~60, `metric_catalog.py` ~55, `config.py` ~12, `lang.py` Rest ~15). Das Workflow-Limit von 250 LoC wird berührt: `workflow.py set-field loc_limit_override 500` einplanen.
- **Files:** ca. 38 (davon 20 leere Katalogdateien, 1 Fixture, 7 Tests)
- **Effort:** medium

## Dependencies

| Entity | Type | Purpose |
|---|---|---|
| #2646 S1 | Paket | Feld `language` in `user.json`, `src/i18n/lang.py` mit `resolve_user_lang` |
| `app.loader.get_data_dir(user_id)` | function | Pfadlogik mit Testisolation (`_DATA_ROOT`, `GZ_DATA_DIR`), prüft `user_id` |
| `app.metric_catalog` (`_METRICS`, `get_all_metrics`, `aggregation_label_de`, `get_alert_label`) | module | Register, das erweitert wird |
| `api.routers.config` | module | Route `GET /api/metrics` |
| `docs/reference/i18n_glossar.md` | doc | bindende Wortliste für `label_en`; Verbot das im Glossar verbotene Produktwort ist untersagt |
| ADR-0104, ADR-0042 | adr | Sprache am Nutzer; Klasse 1 (Token) nie übersetzen, Klasse 2 „voll“ und „Alarm-Kurzform“ sprachabhängig |
| Blockiert | Pakete | PV (#2663), P2–P11 (#2664–#2674), F5 (#2654), F7 (#2656) |

## Implementation Details

**Katalog.** Dateien `src/i18n/messages/{de,en}/<bereich>.json` mit den Bereichen `allgemein`, `mail`, `vergleich`, `alarm`, `warnung`, `telegram`, `sms`, `versand`, `inbound`, `api`; in diesem Paket alle `{}`. Schlüssel `bereich.gruppe.element`, nur `[a-z0-9_.]`, 2–4 Segmente; der erste Teil muss zum Dateinamen passen. Platzhalter `{name}` in snake_case, Plural als `x.one` und `x.other`, kein HTML, keine Satzkonkatenation.

**API (aus den Konventionen, unverändert):**

```python
Lang = Literal["de", "en"]
def t(key: str, lang: Lang = "de", /, **params: object) -> str
def tn(key: str, count: int, lang: Lang = "de", /, **params: object) -> str
def resolve_user_lang(user_id: str, data_dir: str | Path | None = None) -> Lang
def fmt_date(d: date | datetime, lang: Lang, style: Literal["kurz", "lang"] = "kurz") -> str
def fmt_weekday(d: date | datetime, lang: Lang, kurz: bool = True) -> str
def fmt_time(d: datetime) -> str
def relative_day(delta_days: int, lang: Lang) -> str
```

**Verhalten von `t()` und `tn()`.** Jeder Wert außer `"en"` gilt als `"de"`. Fehlt der Schlüssel in `en`, kommt der deutsche Text und einmal je Prozess und Schlüssel die Logzeile `i18n fallback: <key>`. Fehlt er auch in `de`, wird der Schlüssel selbst zurückgegeben (ein Briefing darf nie an einem Textfehler scheitern) und einmal `i18n missing: <key>` geloggt. Platzhalter werden per Regex `\{([a-z][a-z0-9_]*)\}` ersetzt, nicht per `str.format`; ein nicht übergebener Platzhalter bleibt als `{name}` stehen und wird einmal geloggt. `tn("x", 1, …)` nimmt `x.one`, jede andere Zahl `x.other`; `{count}` ist implizit verfügbar. Der einzige Zustand ist der geladene Katalog und die Menge der schon gemeldeten Schlüssel (reine Log-Entdopplung, keine Sprache).

**Format (`format.py`).** Wochentags- und Monatsnamen stehen als feste Tabellen im Code (kein `strftime`, damit keine Prozess-Locale hineinspielt); das Datum 2026-10-29 ist ein Donnerstag:

| Aufruf | de | en |
|---|---|---|
| `fmt_date(date(2026,10,29), lang, "kurz")` | `Do 29.10.` | `Thu 29 Oct` |
| `fmt_date(date(2026,10,29), lang, "lang")` | `Donnerstag, 29. Oktober 2026` | `Thursday, 29 October 2026` |
| `fmt_weekday(d, lang)` / `kurz=False` | `Do` / `Donnerstag` | `Thu` / `Thursday` |
| `fmt_time(datetime(2026,10,29,14,30))` | `14:30` | `14:30` |
| `relative_day(0/1/2, lang)` | `heute` / `morgen` / `übermorgen` | `today` / `tomorrow` / `day after tomorrow` |

`relative_day` löst für andere Werte als 0, 1, 2 `ValueError` aus. Das Dezimaltrennzeichen bleibt der Punkt (keine Funktion nötig). Dieses Paket stellt **keine** Aufrufer um: die deutschen Wochentagstabellen in `email/html.py` (Z. 1068, 1373), `email/compare_html.py` (Z. 160, 1179), `alert/official_alerts.py` (Z. 100) und `services/trip_report_scheduler.py` (Z. 2958) ersetzen die Pakete P2, P4, P5/P6 und P9b durch `fmt_weekday`. Der Verweis im Issue auf `alert/model.py` trifft nicht zu: dort gibt es keine Wochentagslogik.

**Register (`metric_catalog.py`).** Neue Felder am Ende von `MetricDefinition` (nach `kuerzel_bedeutung_de`, Z. 102), alle mit Standard `""`: `label_en`, `alert_label_en`, `friendly_label_en`. Methoden:

```python
def label(self, lang: str = "de") -> str:            # en: label_en or label_de
def alert_label_for(self, lang: str = "de") -> str:  # de: alert_label or label_de; en: alert_label_en or label_en, sonst wie de
def friendly_label_for(self, lang: str = "de") -> str:  # en: friendly_label_en or friendly_label; de: friendly_label
```

`aggregation_label(aggregation, lang)` steht neben `aggregation_label_de` (Z. 1102, bleibt unverändert) und nutzt eine neue Tabelle `_AGGREGATION_LABELS_EN` neben `_AGGREGATION_LABELS_DE` (Z. 963). `get_alert_label(metric_id, lang="de")` (Z. 1510) bekommt ein optionales zweites Argument mit Standard `"de"`; ohne Argument ist das Verhalten byte-gleich. Die englischen Namen stehen nicht in den 32 Einzeleinträgen, sondern in **einer** Tabelle `_ENGLISH_NAMES: dict[str, tuple[str, str, str]]` (Kennung → `label_en`, `alert_label_en`, `friendly_label_en`) unmittelbar vor dem Aufbau von `_METRICS_BY_ID` (Z. 953), angewandt mit `dataclasses.replace` in einem zweiten Durchlauf nach der bestehenden Kürzel-Ableitung (Z. 944–950). So bleibt der Diff gegen die Konventionen-Tabelle 1:1 prüfbar.

**Englische Namen (vollständig, Quelle Konventionen Abschnitt 4 plus drei Ergänzungen):**

| id | `label_de` | `label_en` | `alert_label` → `alert_label_en` |
|---|---|---|---|
| temperature | Temperatur | Temperature | Temp → Temp |
| temperature_cold | Tiefsttemperatur-Alarm | Low temperature alert | Temp → Temp |
| temperature_night | Nacht-Tiefsttemperatur | Night low | — |
| temperature_day_low | Tages-Tiefsttemperatur (Gehzeit) | Daytime low (walking hours) | — |
| temperature_day_high | Tages-Höchsttemperatur (Gehzeit) | Daytime high (walking hours) | — |
| wind_chill | Gefühlte Temperatur | Feels-like temperature | — |
| wind_chill_night | Gefühlte Nacht-Tiefsttemperatur | Feels-like night low | — |
| wind_chill_day_low | Gefühlte Tages-Tiefsttemperatur (Gehzeit) | Feels-like daytime low (walking hours) | — |
| wind_chill_day_high | Gefühlte Tages-Höchsttemperatur (Gehzeit) | Feels-like daytime high (walking hours) | — |
| humidity | Luftfeuchtigkeit | Humidity | Feuchte → Humidity |
| dewpoint | Taupunkt | Dew point | — |
| wind | Wind | Wind | Wind → Wind |
| gust | Böen | Wind gusts | Böen → Gusts |
| wind_direction | Windrichtung | Wind direction | — |
| precipitation | Niederschlag | Precipitation | Niedersch → Precip |
| rain_probability | Regenwahrscheinlichkeit | Rain probability | Regen% → Rain% |
| confidence | Sicherheit | Confidence | — (nicht wählbar, #710) |
| thunder | Gewitter | Thunderstorm | Gewitter → Thunder |
| cape | Gewitterenergie (CAPE) | Thunderstorm energy (CAPE) | CAPE → CAPE |
| snowfall_limit | Schneefallgrenze | Snow line | 0°-Grenze → 0° line |
| precip_type | Niederschlagsart | Precipitation type | — |
| cloud_total | Bewölkung | Cloud cover | — |
| cloud_low | Tiefe Wolken | Low clouds | — |
| cloud_mid | Mittelhohe Wolken | Mid-level clouds | — |
| cloud_high | Hohe Wolken | High clouds | — |
| visibility | Sichtweite | Visibility | Sicht → Visib |
| sunshine | Sonnenstunden | Sunshine hours | — |
| uv_index | UV-Index | UV index | UV-Index → UV index |
| pressure | Luftdruck | Air pressure | — |
| freezing_level | Nullgradgrenze | Freezing level | Nullgradgrenze → Freezing lvl |
| snow_depth | Schneehöhe | Snow depth | Schneehöhe → Snow depth |
| fresh_snow | Neuschnee | Fresh snow | Neuschnee → Fresh snow |

Auswertungen: `min` Minimum / Minimum, `max` Maximum / Maximum, `avg` Mittel / Average, `sum` Summe / Total. Alle `alert_label_en` haben höchstens 12 Zeichen (ADR-0042, Alarm-Kurzform etwa 10). `friendly_label_en` bleibt für alle Einträge leer, weil jeder vorhandene `friendly_label` (`N/S/W/E`, Blitz, Ampel-Kreise, Wetter-Symbole) sprachneutral ist.

**Wächter ADR-0042 Klasse 1.** `tests/fixtures/metric_tokens_frozen.json` wird einmalig aus dem **heutigen Register** erzeugt (Wegwerf-Skript, nicht eingecheckt): für alle 32 Einträge von `_METRICS` (auch `selectable=False`) die **endgültigen** Werte nach der Kürzel-Ableitung: `{"temperature": {"col_label": "Temp", "compact_label": "<Istwert>", "sms_code": "T"}, …}`. Datei mit `sort_keys=True`, `indent=2`, Zeilenende `\n`. `tests/test_metric_tokens_eingefroren.py` lädt `app.metric_catalog._METRICS`, bildet dieselbe Struktur und vergleicht serialisiert **byte-genau** mit dem Dateiinhalt; Meldung nennt Kennung und Feld. Ein Eintrag im Register ohne Eintrag in der Fixture (und umgekehrt) ist ebenfalls rot.

**Route `GET /api/metrics`.** `get_metrics()` (Z. 93–147) behält `"label"` (deutsch, bestehende Verbraucher) und ergänzt je Größe `"label_de"` (= `label`), `"label_en"`, `"alert_label"`, `"alert_label_en"`; je Eintrag in `"aggregations"` kommt `"label_en"` aus `aggregation_label(a, "en")` hinzu. Der Filter `selectable=False` (#710, `confidence`, `temperature_cold`) bleibt unverändert.

**Beispiel-Schlüssel** (de / en, aus dem Glossar; in P1 nur als Testkatalog in einem temporären Verzeichnis verwendet, die echten Einträge legen P2 ff. in die Bereichsdateien):

| Schlüssel | de | en |
|---|---|---|
| `mail.legende.einheiten` | Einheiten: {liste} | Units: {liste} |
| `mail.legende.spalten` | Spalten: {liste} | Columns: {liste} |
| `mail.nacht.am_ziel` | Nacht am Ziel ({hoehe}m) | Night at destination ({hoehe}m) |
| `mail.ausblick.eyebrow` | Ausblick · nächste 3 Tage | Outlook · next 3 days |
| `alarm.hinweis.weitere.one` / `.other` | und {count} weitere | and {count} more |

**Beispiel-Umstellung (Konsument des Registers, kommt in P2).** `src/output/renderers/email/helpers.py` Z. 638 `pairs.append((col_label, get_metric_by_col_key(col_key).label_de))` wird dort zu `… .label(lang)`; die Kurzform `col_label` bleibt. P1 selbst ändert diese Zeile **nicht**.

**Allowlist-Eintrag.** Keiner: die Python-Ratsche (P11) und ihre Allowlist `tests/fixtures/i18n_python_allowlist.json` entstehen später. Der Wächter `metric_tokens_frozen.json` ist die Ratsche dieses Pakets.

**Token-Wächter (ADR-0042 Klasse 1).** Siehe oben: `sms_code`, `compact_label` und `col_label` bleiben bytegleich; eine Änderung eines Tokens färbt den Test rot (Mutations-Gegenprobe des Adversary: ein `sms_code` per String-Ersetzung ändern).

## Expected Behavior

- **Input:** Schlüssel, Sprache und Parameter für `t`/`tn`; Datum/Uhrzeit für die Formatfunktionen; eine `user_id` für `resolve_user_lang`; eine Metrik-Kennung und Sprache für die Registermethoden; `GET /api/metrics`.
- **Output:** Der Text in der Sprache des Nutzers (Fallback Deutsch), formatierte Datums- und Wochentagsangaben, englische Metriknamen; `GET /api/metrics` enthält zusätzlich `label_de`, `label_en`, `alert_label`, `alert_label_en`.
- **Side effects:** Einmalige Logzeilen bei Fallback oder fehlendem Schlüssel. Keine Schreibzugriffe auf Nutzerdaten, keine Änderung der deutschen Ausgabe, keine Änderung eines Tokens.

## Acceptance Criteria

- **AC-1:** Given ein Testkatalog mit `mail.betreff.briefing` (de und en), einem Plural-Paar `x.one`/`x.other` und einem Schlüssel nur auf Deutsch / When `t` und `tn` mit `de`, `en` und unbekannter Sprache aufgerufen werden / Then liefert `en` den englischen Text mit ersetztem Platzhalter, `de` und unbekannte Sprache den deutschen, `tn` wählt `.one` genau bei 1, und der nur deutsche Schlüssel kommt mit `en` auf Deutsch zurück und wird genau einmal geloggt.
  - Test: `tests/unit/test_i18n_t_platzhalter_plural_fallback.py` — echte Katalogdateien in einem temporären Verzeichnis, Logzeile über `caplog`, kein Mock der Funktion.

- **AC-2:** Given die echten Katalogordner `src/i18n/messages/de` und `en` sowie ein absichtlich verdorbener Testkatalog / When der Paritätstest läuft / Then sind alle zehn Bereichsdateien in beiden Sprachen vorhanden und gültiges JSON, und der Test wird rot mit Nennung des Schlüssels, wenn `en` einen Schlüssel oder `{platzhalter}` gegenüber `de` verliert oder hinzufügt.
  - Test: `tests/unit/test_i18n_katalog_paritaet.py` — Lauf über die echten Ordner plus Selbsttest mit verdorbenem Testkatalog (`# doc-compliance-test`: Paritätstest).

- **AC-3:** Given der Donnerstag 29.10.2026, 14:30 / When `fmt_date`, `fmt_weekday`, `fmt_time` und `relative_day` mit `de` und `en` aufgerufen werden / Then entstehen exakt die Werte der Format-Tabelle (`Do 29.10.` und `Thu 29 Oct`, `14:30` in beiden), unabhängig von der Prozess-Locale, und ein `delta_days` außerhalb 0–2 löst `ValueError` aus.
  - Test: `tests/unit/test_i18n_format_datum_wochentag.py` — Beispielwerte aus der Tabelle, einmal mit gesetzter fremder Locale (`LC_ALL`) zur Gegenprobe.

- **AC-4:** Given das Metrik-Register / When alle 32 Einträge und beide Sprachen abgefragt werden / Then hat jeder Eintrag ein nicht leeres `label_en` laut Namenstabelle (zum Beispiel `gust` → `Wind gusts`, `snowfall_limit` → `Snow line`), jedes vorhandene `alert_label_en` hat höchstens 12 Zeichen, `label("de")`, `alert_label_for("de")` und `get_alert_label()` liefern byte-gleich die bisherigen deutschen Werte, und `aggregation_label("avg", "en")` ist `Average`.
  - Test: `tests/unit/test_metric_catalog_englische_namen.py` — Vergleich gegen die Tabelle aus dieser Spec und gegen die vor der Änderung festgehaltenen deutschen Werte.

- **AC-5:** Given die eingefrorene Fixture der Token / When ein `sms_code`, `compact_label` oder `col_label` im Register geändert wird / Then schlägt der Wächter mit Kennung und Feld fehl; unverändert ist er grün.
  - Test: `tests/test_metric_tokens_eingefroren.py` — byte-genauer Vergleich; Mutationsprobe: ein `sms_code` per String-Ersetzung ändern (Sicherungskopie extern, kein `git checkout/stash/reset`).

- **AC-6:** Given `GET /api/metrics` / When die Antwort gelesen wird / Then trägt jedes Element ein nicht leeres `label_en`, `label` bleibt der deutsche Name, `label_de`, `alert_label` und `alert_label_en` sind vorhanden, jede Auswertung trägt `label_en`, und `confidence` und `temperature_cold` fehlen weiterhin.
  - Test: `tests/unit/test_metrics_endpoint_englische_namen.py` — echter FastAPI-`TestClient` gegen `api.routers.config.router`, kein Mock.

- **AC-7:** Given zwei Nutzer, A mit `language: "en"` und B ohne Feld, in einer temporären Datenwurzel / When abwechselnd `resolve_user_lang("A")`, `resolve_user_lang("B")` und `t(...)` mit der jeweiligen Sprache aufgerufen werden / Then sieht A englischen und B deutschen Text in jeder Reihenfolge, und ein unbekannter Nutzer ergibt `de` ohne Ausnahme.
  - Test: `tests/unit/test_i18n_sprache_zwei_nutzer.py` — echte `user.json`-Dateien unter `_DATA_ROOT` (Testisolation), verschränkte Aufrufe.

- **AC-8:** Given der unveränderte Renderer-Pfad / When die bestehenden Golden-Tests der Trip-Mail laufen / Then bleiben sie byte-gleich grün, weil das Paket keine deutsche Ausgabe ändert.
  - Test: `tests/golden/email/test_email_html_golden.py` und `tests/golden/email/test_email_plain_golden.py` laufen unverändert grün.

## Known Limitations

- Annahme: `src/i18n/lang.py` mit `resolve_user_lang` existiert nach S1; P1 konsolidiert nur (ein Re-Export in `__init__.py`, keine zweite Implementierung). Fehlt die Datei, legt P1 sie nach der Beschreibung in den Konventionen an.
- Annahme: Die Wochentags-, Monats- und Relativtag-Namen sind Code-Tabellen in `format.py`, nicht Katalogeinträge, damit die Bereichsdateien wie vereinbart leer bleiben und das Format nie von einer Katalogdatei abhängt.
- Annahme: `wind_chill_day_low`, `wind_chill_day_high` und `sunshine` fehlen in der Konventionen-Tabelle; ihre englischen Namen sind aus den Nachbarzeilen (Gehzeit-Form) und dem Glossar (Sonnenstunden = Sunshine hours) abgeleitet.
- Annahme: Die Antwort von `GET /api/metrics` behält `label` (deutsch) zusätzlich zu `label_de`, damit bestehende Verbraucher nicht brechen; F5 wählt über `metricLabel(def, lang)`.
- Annahme: `get_alert_label` bekommt das optionale Argument `lang` (additiv), damit P3 und P5 ohne zweite Funktion auskommen.
- Die Konventionen nennen als Beispieldatum „Do 30.10.“; der 30.10.2026 ist ein Freitag. Maßgeblich ist der Kalender (Tabellen und Tests oben nutzen den Donnerstag 29.10.2026).
- Alle Bereichsdateien sind leer; ein Schlüssel ohne Eintrag liefert bis zur Migration den Schlüssel selbst. Die Python-Ratsche (P11) verhindert das im Repo.
- Telegram-Kurzstil und Premium-SMS bleiben Platzform (ADR-0042): Dieser Kern ändert daran nichts, er stellt nur die Sprache für Auflösung und Antworttexte bereit.

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** ADR-0104 (zusätzlich ADR-0042)
- **Rationale:** Ein Katalog je Schicht und eine einzige Sprachauflösung; ADR-0042 trennt unveränderliche Token (Klasse 1) von sprachabhängigen Anzeigenamen (Klasse 2), was der Wächter erzwingt.

## Changelog

- 2026-10-30: Initial spec created (Planung Epic #2644)
