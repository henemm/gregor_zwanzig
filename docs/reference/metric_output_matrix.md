# Metrik-Ausgabeorte je Kanal — Referenz & Entscheidungsvorlage

> **Stand: 2026-08-10, Commit-Basis: 1c38a5ac** · Issue #1514 (`triage:po`)
>
> **Abgrenzung:** Dieses Dokument ist reine Analyse. In dem Workflow, der es
> erzeugt hat, wurde **kein Produktivcode** geändert und **kein neues Gate und
> kein neuer Test** eingeführt — beides ist ausschließlich als Folge-Scheibe
> (Abschnitt 6) vermerkt. Auch die in Abschnitt 5 empfohlene Register-Strategie
> ist eine Empfehlung, keine bereits vollzogene Änderung.
>
> **Aktualität:** Die Datei:Zeile-Belege sind eine Momentaufnahme des oben
> genannten Commits und wurden für dieses Dokument einzeln am Code nachgeschlagen.
> Es gibt (noch) keine Ratsche, die sie aktuell hält — siehe Abschnitt 8.

## 1. Zweck & Leitfrage

Anlass ist #1475 (Hagel): drei Recherche-Runden waren nötig, um 12 Ausgabeorte
einer einzigen Metrik zu finden, und Scheibe S5a ging mit 4 von 12 live — ohne
dass Adversary oder Entwickler-Report es bemerkten. Der Grund ist nicht
Nachlässigkeit, sondern fehlende Übersicht: es gibt im Projekt **keine
generische Metrik×Kanal-Matrix**, weder als Doku noch als Test. Vorhandene
Ort-Tabellen sind metrikspezifisch (`docs/features/gewitter-gesamtkonzept.md` §8)
oder aspektspezifisch (Legende, Namensform, Ampel).

Dieses Dokument beantwortet für jeden Ausgabeort dieselben vier Fragen. Die
Leitfrage ist zellenweise anzuwenden — nicht pauschal pro Kanal:

| # | Frage je Zelle (Metrik × Ausgabeort) | Warum sie einzeln gestellt werden muss |
|---|---|---|
| 1 | **Wo?** Datei:Zeile des Ausgabeorts | „Der Renderer" ist keine Adresse; ein Kanal hat mehrere Schreibstellen (E-Mail allein: Tabelle, Pillen, Mobilzeilen, Kurzform, Ausblick) |
| 2 | **Woher?** katalog-getrieben oder handgeschrieben | Katalog-getriebene Orte wachsen mit einer neuen Metrik automatisch mit; handgeschriebene *nicht* — dort entsteht die Lücke |
| 3 | **In welcher Form?** Aggregation, `format_mode`, Symbol-Grammatik, Einheit/Nachkommastellen | Dieselbe Metrik erscheint als Zahl, Pille, Wort und Kürzel; 1:n-Fälle (ein Metrik-Eintrag → mehrere SMS-Kürzel) sprengen die 1:1-Annahme des Katalogs |
| 4 | **Wer bewacht das?** konkreter Test oder ausdrücklich „unbewacht" | Ein grüner Testlauf beweist nur, dass Tests durchlaufen. Ohne benannten Wächter ist die Zelle unbewacht — das ist eine Aussage, keine Lücke im Wissen |

**Merksatz für Frage 4:** Ist die Zusicherung an der Stelle geprüft, an der sie
**wirkt** — oder nur dort, wo der Code steht? Ein Test, der `resolve_metric_col_order()`
prüft, bewacht die E-Mail-Tabelle. Er bewacht **nicht** den Ausblick derselben Mail.

### Grundlage: der Katalog und was er nicht abdeckt

`src/app/metric_catalog.py` ist die Single Source of Truth. `MetricDefinition`
(`metric_catalog.py:28`) trägt rund 30 Felder, von denen viele direkt eine
Ausgabeform definieren: `col_key`/`col_label`, `compact_label`, `sms_code`,
`alert_label`, `format_modes`, `trip_default_rank`, `selectable`.

Gemessen am oben genannten Commit:

- **28 Einträge in `_METRICS`** (`metric_catalog.py:92`), davon **26 selectable**
- **2 nicht-wählbar:** `temperature_cold` und `confidence`. `temperature_cold`
  hat einen `sms_code` — erscheint also in einer Ausgabe, fällt aber aus jeder
  Prüfung, die über `get_all_metrics()` iteriert (siehe Fläche 6)
- **34 Python-Dateien** in `src/`, `api/`, `scripts/` importieren oder nennen
  `metric_catalog`; dazu 28 Frontend-Dateien mit eigenen Metrik-Registern
  (`compareMetricDefs.ts` u.a.). Die Recherche-Notiz nannte „44 Konsumenten";
  diese Zahl war am Commit 1c38a5ac nicht reproduzierbar

## 2. Metrik×Kanal-Landschaft

Legende der Spalte *Quelle*: **katalog-getrieben** = die Liste der Metriken
entsteht aus `_METRICS`/`get_all_metrics()`, eine neue Katalog-Metrik erscheint
automatisch. **handgeschrieben** = eine im Quelltext getippte Liste/Kette; eine
neue Metrik erscheint dort **nur**, wenn jemand daran denkt. **gemischt** =
katalog-getriebene Liste mit handgeschriebenen Ausnahmen.

### 2.1 Trip

| Ausgabeort | Datei:Zeile | Quelle | Wächter |
|---|---|---|---|
| E-Mail-Tabelle (Vollformat, HTML + Klartext) | `src/output/renderers/email/helpers.py:302` `resolve_metric_col_order()`; Aufrufe `email/html.py:1021`, `email/plain.py:144` | katalog-getrieben | `tests/tdd/test_channel_metric_matrix.py:81` (Auswahl/Abwahl/paarweise Reihenfolge) |
| E-Mail-Pillen („Metriken-Überblick") | `src/output/renderers/email/helpers.py:1815` `build_metrics_summary_pills()`; Metrik-Auflösung `src/output/renderers/trip_metric_ids.py:37` `resolve_trip_active_metrics()` | katalog-getrieben | **unbewacht** (keine Metrik×Ort-Prüfung) |
| E-Mail mobile Kompaktzeilen (in der **Voll**mail) | `src/output/renderers/email/html.py:878` `_render_mobile_compact_rows()`; Aufrufe `:1206`, `:1264`, `:1290` (Nachtzeilen) | katalog-getrieben (erbt `col_order`) | **unbewacht** |
| Kurzform-Mail (eigenes Format `compact`) | `src/output/renderers/email/compact.py:96` `render_compact()`; Pillen-Aufruf `:176` | katalog-getrieben über `resolve_trip_active_metrics` | **unbewacht** |
| Kompakt-Zusammenfassung (Fließtext-Block **in** der Vollmail) | `src/output/renderers/compact_summary.py:567` `_format_thunder()`, Aufruf `:243`; aktiviert über `src/output/renderers/trip_report.py:173` `options.show_compact_summary`, Formatter-Einstieg `trip_report.py:942` | handgeschrieben — `thunder` ist die **einzige** Metrik mit eigener Formatier-Methode | nur metrikspezifisch: `tests/tdd/test_hail_compact_summary_thunder.py:75`, `:89`, `:107` (Gewitter/Hagel). Als Metrik×Kanal-Ort **unbewacht** |
| Ausblick / 3-Tages-Tabelle (Trip-Mail) | `src/output/renderers/email/outlook.py:149`, `:343`, `:522` — Spalten aus `src/output/renderers/compare_outlook_metric_ids.py:78` `outlook_columns()` | katalog-getrieben | **unbewacht** (größte Fläche, s. 4.2) |
| Ausblick: Gewitter-Sonderbehandlung | `email/outlook.py:38` `_THUNDER_TOKEN_RE`; Wortlaut-Map `:195–198` (dritte LOW/MED/HIGH-Übersetzung im Code) | handgeschrieben | teilbewacht über Gewitter-Tests, nicht über die Matrix |
| Telegram rich (Bubbles) | `src/output/renderers/narrow.py:661` → `src/output/renderers/channel_layout.py:75` `render_for_channel()`; Limits `channel_layout.py:45` `CHANNEL_LIMITS` | gemischt — Ausnahme `_NIGHT_SCALAR_IDS` `channel_layout.py:88` | `tests/tdd/test_channel_metric_matrix.py:114` |
| Telegram Kurzübersicht / Trendzeile | `narrow.py:346` (Zeilentupel), `narrow.py:528–532`, `narrow.py:586–597` (drei hartkodierte Gewitter-Zweige) | handgeschrieben | **unbewacht** als eigener Ausgabeort |
| SMS Trip (Kurzform) | `src/output/renderers/sms_trip.py:606` `format_sms()`; Symbole `sms_trip.py:116` `SMS_SYMBOL_BY_METRIC` aus `metric_catalog.py:938` `get_sms_code()` | gemischt | `tests/tdd/test_channel_metric_matrix.py:210` (nur Auswahl/Reihenfolge) |
| SMS: Grammatik-Ausnahmen | `sms_trip.py:114` `_SMS_SYMBOL_GRAMMAR` (`thunder` → `TH:`, `fresh_snow` → `NS24+`) | handgeschrieben (2 benannte Fälle) | Ratsche in der SMS-Suite, nicht in der Matrix |
| SMS: Token-Reihenfolge/Auffüllung | `src/output/tokens/builder.py:47` `PRIORITY` (40+ Symbole), `:78` `POSITIONAL` (33), `:112` `DEFAULTS` | handgeschrieben | **unbewacht** gegen den Katalog |
| SMS: Kaskade | `sms_trip.py` liest **weder** `get_metrics_for_channel()` **noch** `cascade_source_for_channel()`; die kanalabhängige Position wird stattdessen in `src/output/renderers/trip_report.py:301` vorbereitet | Bruch | s. Fläche 10 |
| Telegram-Drilldown / Kommandos | `src/services/trip_command_processor.py:227` `_DRILLDOWN_METRICS` (genau 3 Metriken); Regex `:161` `_DRILLDOWN_PATTERN`; Nutzung `:613` | handgeschrieben, als Regex eingefroren | **unbewacht** gegen den Katalog |

### 2.2 Compare (Ortsvergleich)

| Ausgabeort | Datei:Zeile | Quelle | Wächter |
|---|---|---|---|
| Compare-Katalog (Endpunkt/Frontend-Vokabular) | `src/output/renderers/compare_metric_catalog.py:51` (aus zentralem Katalog **abgeleitet**), `:251` `get_compare_metric_catalog()` | katalog-getrieben | Key-Drift-Assertions `compare_metric_catalog.py:171`, `:224` |
| HTML-Übersichtstabelle (Orte = Spalten) | `src/output/renderers/email/compare_html.py:294` `CV2_METRICS`; Beschriftungen abgeleitet `compare_html.py:745` `derive_row_labels()` | handgeschriebene Zeilenliste, abgeleitete Labels | Zeilen-**Existenz** bewacht, **Zellwert unbewacht** (Fläche 4) |
| HTML-Stundentabelle | `compare_html.py:428` über `hourly_selectable_metric_ids()`; Ausnahmen `:384` `_HOUR_FMT_OVERRIDES` (10), `:400` `_HOUR_SEV_OVERRIDES` (3) | gemischt | `tests/unit/test_compare_hourly_catalog_columns.py:122` — der **einzige** echte Wirkungs-Vollständigkeitstest im Bestand |
| Klartext-Teil derselben Mail | `src/output/renderers/comparison.py:70` `_DAILY_PLAIN_ROWS`, `:100` `_PLAIN_ROWS` (je Zeile ein getipptes Tupel aus ID, Label, Format-Lambda); gerendert `:237` | handgeschrieben | Reihenfolge eingefroren in `tests/unit/test_compare_metric_order.py`; Werte-Parität zum HTML nur durch geteilte Formatierer, nicht durch Assertion |
| Compare Telegram | `comparison.py:668` `render_for_channel(channel, dc, …)`; Labels/Formate `comparison.py:498` `_PLAIN_ROWS_BY_ID` | katalog-getrieben | **unbewacht** — der Matrix-Test kennt Compare überhaupt nicht |
| Compare SMS | `comparison.py:486` `_CHANNEL_METRICS` — genau 6 Metriken (Temp, Wind, Sonne, Wolken, Schnee, Neuschnee) | handgeschrieben | **unbewacht** |
| Compare Ausblick | `src/output/renderers/compare_outlook_metric_ids.py:78` `outlook_columns()` (dieselbe Funktion wie Trip-Ausblick) | katalog-getrieben | **unbewacht** |
| Compare-ID-Auswahlmodule | `compare_hourly_metric_ids.py`, `compare_metric_ids.py`, `compare_outlook_metric_ids.py` (Neuformat `{"metric_id","aggregation"}`) | katalog-getrieben | teilbewacht |

### 2.3 Alarme und amtliche Warnungen

| Ausgabeort | Datei:Zeile | Quelle | Wächter |
|---|---|---|---|
| Alarm-Betreff | `src/output/renderers/alert/render.py:292` `render_subject()` | katalog-getrieben (Registry-Import `alert/render.py:10–13`) | **unbewacht** gegen Katalog-Vollständigkeit |
| Alarm-Mail | `alert/render.py:448` `render_email()` | katalog-getrieben | **unbewacht** |
| Alarm-Telegram | `alert/render.py:549` `render_telegram()` | katalog-getrieben | **unbewacht** |
| Alarm-SMS | `alert/render.py:617` `render_sms()` | katalog-getrieben | **unbewacht** |
| **Stiller Ersatzpfad** | `alert/render.py:35` `_HANDLED_UNITS = {"m","km","hPa","%","km/h","°C","mm"}`; Verzweigung `:49` | handgeschriebene Whitelist | **unbewacht** — eine Metrik mit fremder Einheit rutscht ohne Fehler in den Ersatzpfad |
| Alarm-Auswertungskette | `src/services/weather_change_detection.py` (5 Katalog-Importe) | katalog-getrieben | prüft Auslösung, nicht Renderer-Vollständigkeit |

### 2.4 Konfigurationsseite (wo die Reihenfolge herkommt)

| Stelle | Datei:Zeile | Anmerkung |
|---|---|---|
| Kanal-Kaskade (drei Ebenen) | `src/app/models.py:649` `_cascade_source_for_channel()` (geteilte Bedingungsprüfung, #1677 DEC-2), `:762` `get_metrics_for_channel()`, `:802` `cascade_source_for_channel()` | **ein** Ableitungsweg; `per_report` → `per_channel` → `global` |
| Persistenz | `src/app/loader.py:840` (`channel_layouts` lesen), `:872` (`channel_layouts_per_report`), `:914` | Lesen 1×, Schreiben 2× |
| API Metrik-Liste | `api/routers/config.py:73` `get_metrics()` — filtert auf `selectable` | Nicht-wählbare Metriken sind für das Frontend unsichtbar |
| API SMS-Symbole | `api/routers/config.py:31` `get_sms_symbols()`, Hazards `:46`/`:65` | zwei Symbolregister nebeneinander |
| Frontend Trip | `frontend/src/lib/components/shared/WeatherMetricsTab.svelte:411`, `:755–771` — Reihenfolge **je Kanal** (`channel_layouts`) | |
| Frontend Compare | `compareWizardState.svelte.ts` `wiz.activeMetricKeys` + `compareEditorSave.ts` — **eine globale Liste**, keine Kanal-Tabs | struktureller Bruch, offene PO-Frage (7a) |

## 3. Sonderstrecken-Katalog

Sechs Strecken erzeugen sichtbare Ausgaben **ohne** Eintrag im Metrik-Katalog.
Eine Übersicht, die nur Katalog-Konsumenten erfasst, wiederholt genau den
#1475-Fehler — deshalb stehen sie hier getrennt von Abschnitt 2.

| # | Sonderstrecke | Datei:Zeile | Warum außerhalb des Katalogs |
|---|---|---|---|
| S1 | **`thunder_forecast`-Datenkanal** | Aufbau `src/services/trip_report_scheduler.py:2168` `_build_thunder_forecast()`, Trend-/Nachlade-Variante `:1864`, Aufruf `:1030`. Durchreiche: `src/services/notification_service.py:71`, `:323` → `src/output/renderers/trip_report.py` → `src/output/renderers/sms_trip.py:616`, `:682–700` und `src/output/renderers/email/html.py:962`, `:1312` | eigener Datenkanal ohne Katalogeintrag und ohne Editor-Auswahl; speist mindestens drei Kanäle. War Lücke 3 in #1475 |
| S2 | **Hazard-Symbole** (amtliche Warnungen) | `src/output/tokens/hazard_symbols.py:15` `HAZARD_SMS_SYMBOLS`, `:29` `HAZARD_ORDER`; API `api/routers/config.py:46`, `:65` | eigenes Symbolregister **neben** dem Metrikkatalog; Kollisionsfreiheit der Kürzel ist Konvention, nicht geprüft |
| S3 | **System-Blöcke der Kurzform (DEC-4)** | `src/output/tokens/builder.py:61`, `:86`, `:105`; Einsortierung `src/output/tokens/render.py:12` | Blöcke mit eigener Prioritätsstufe und Katalog-Reihenfolge; „strukturell nicht sortierbar" laut Known Limitation 2 in #1677 |
| S4 | **`TokenLine.filter_for_subject`** | `src/output/tokens/dto.py:154` | **Stub**: gibt `self` zurück. Der in `sms_format.md` §11 beschriebene Betreff-Filter (β2) existiert nicht — der Betreff bekommt die volle Tokenzeile |
| S5 | **Wintersport-Block** | Profil-Default `src/output/adapters/trip_result.py:196` `_wintersport_default_config()`; Token `NS24+` erklärt in `sms_trip.py:109–114`, `WC` in `sms_trip.py:154` | eigenes Profil mit eigener MetricSpec-Liste; die gerenderten Token weichen bewusst vom `sms_code` des Katalogs ab (`NS` → `NS24+`) |
| S6 | **`SMS_MULTI_SYMBOLS_BY_METRIC`** | `src/output/renderers/sms_trip.py:180` | **1:n-Strukturbruch**: eine Metrik erzeugt mehrere Kürzel (Grammatik-Klassen). Der Katalog bildet 1:1 ab und kann das strukturell nicht ausdrücken — deshalb die Empfehlung, die Form-Dimension als eigene Achse zu führen (Frage 7b) |

## 4. Unbewachte Flächen mit Priorisierung

Zehn Flächen, in denen heute kein Test prüft, ob eine Metrik dort ankommt.
„Unbewacht" heißt: die Zelle existiert, aber ihr Verschwinden macht keinen Test rot.

### 4.1 Priorität 1 — die drei mit der größten Fallhöhe

**Fläche 1 — Alle Metriken × Alarm-Renderer.** `alert/render.py:292/448/549/617`.
Ein alarmfähiger Katalogeintrag ohne Alarm-Mail-Zeile fällt nirgends auf.
Verschärfend: die `_HANDLED_UNITS`-Whitelist (`alert/render.py:35`) weicht bei
fremder Einheit **still** auf einen Ersatzpfad aus — das Ergebnis ist eine
plausibel aussehende, inhaltlich falsche Alarmmeldung statt eines Fehlers.
*Priorität 1, weil Alarme sicherheitsrelevant sind und der Fehlermodus lautlos ist.*

**Fläche 2 — Alle Metriken × Ausblick-Tabelle.** `outlook_columns()`
(`compare_outlook_metric_ids.py:78`), genutzt von Trip-Mail **und** Compare-Mail
(`email/outlook.py:149`, `:343`, `:522`).
*Priorität 1, weil es flächenmäßig die größte unbewachte Zone ist: zwei
Produktflächen, jede Katalogmetrik, kein einziger Wächter.*

**Fläche 3 — Nicht-wählbare Register-Metriken.** `metric_catalog.py:695` —
`get_all_metrics()` gibt `[m for m in _METRICS if m.selectable]` zurück. Jeder
Vollständigkeitstest iteriert über diese Funktion und **kann** deshalb
`temperature_cold` nicht sehen, obwohl die Metrik einen `sms_code` hat und in
Ausgaben erscheint. Das ist keine Lücke in einem Test, sondern eine Blindstelle
**aller** Matrix-Tests gleichzeitig.
*Priorität 1, weil die Behebung klein ist (ein Test über `_METRICS` statt
`get_all_metrics()`) und die Wirkung strukturell: sie repariert die Aussagekraft
jeder künftigen Achse mit.*

### 4.2 Priorität 2 und 3

| # | Unbewachte Fläche | Ort | Prio | Bemerkung |
|---|---|---|---|---|
| 4 | Compare-Übersichtstabelle: **Zellwert** je Metrik | `compare_html.py:294`, `comparison.py:70/100` | 2 | nur Zeilen-Existenz ist bewacht; ein falscher Wert in der Zelle bleibt grün |
| 5 | **Reihenfolge** in allen Kanälen außer E-Mail und Telegram-rich | `tokens/builder.py:78`, `comparison.py:237` | 2 | Compare-Klartext nutzt die Nutzer-Reihenfolge nur als Sichtbarkeitsfilter (#1356) |
| 6 | Kurzform-Mail, mobile Kompaktzeilen und Kompakt-Zusammenfassung | `email/compact.py:96`, `email/html.py:878`, `compact_summary.py:567` | 2 | **drei** verschiedene Orte, die alle „compact" heißen und regelmäßig verwechselt werden: `render_compact()` ist das eigene Kurzformat, `_render_mobile_compact_rows()` sitzt **in** der Vollmail, `CompactSummaryFormatter` erzeugt den Fließtext-Block ebendort. Nur der dritte hat überhaupt einen Test — und nur für Gewitter/Hagel |
| 7 | **Telegram-Kurzform** als eigener Ausgabeort | `narrow.py:346`, `:528–532`, `:586–597` | 2 | taucht in keiner Matrix auf, obwohl es der Prüfweg für die SMS-Grammatik ist |
| 8 | Einheiten und Nachkommastellen je Kanal | `metric_catalog.get_decimals()`, `compare_html.py:384` | 3 | nur die Compare-Legende ist bewacht |
| 9 | **Frontend** ohne Metrik×Kanal-Matrix | `WeatherMetricsTab.svelte:411`, `compareMetricDefs.ts` | 3 | das Frontend führt eigene Register; Drift zum Backend fällt erst im Betrieb auf |
| 10 | **Trip-SMS liest die Kaskade nicht** | `sms_trip.py:606` `format_sms()` — kein Aufruf von `get_metrics_for_channel()`/`cascade_source_for_channel()`; Ersatz-Verdrahtung `trip_report.py:301` | 2 | dokumentiert in `fix_1575_channel_metric_selection.md`; Folge-Issue #1689 (`format_sms`-Merge verschluckt Spec-Felder) |

## 5. Grundsatz-Entscheidung: Register-Strategie

Die Kernfrage aus #1514 ist nicht „wie sieht die Übersicht aus", sondern
**„wie bleibt sie wahr"**. Drei Wege stehen zur Wahl.

### Option A — reines Dokument

Eine gepflegte Markdown-Matrix, wie dieses Dokument, als Dauerlösung.

- **Dafür:** null Gate-Budget, sofort lesbar, erfasst auch Sonderstrecken und Begründungen.
- **Dagegen (belegt, nicht vermutet):** genau dieses Muster ist im Projekt
  nachweislich verrottet. `docs/specs/modules/output_channel_renderers.md` kennt
  weder Compare noch die Kanal-Kaskade; `docs/specs/modules/telegram_output.md`
  referenziert noch Signal, das am 2026-06-06 app-weit entfernt wurde (#610).
  Der Nutzen bei der **nächsten** Metrik-Änderung ist damit nahe null — und ein
  falsches Register ist schlechter als keines, weil es Vollständigkeit behauptet.

### Option B — zweites maschinenlesbares Register

Eine YAML/Python-Struktur neben dem Katalog, die Metrik × Ausgabeort × Form
deklariert, plus Ratschen, die Code und Register abgleichen.

- **Dafür:** maschinell prüfbar, generierbare Doku.
- **Dagegen:** (a) verstößt gegen das **Regel-Budget** — es entstünden mehrere
  *neue* Pflicht-Gates auf einen Schlag, jedes mit eigenem Prüfdatum;
  (b) wiederholt exakt das Doppel-Quellen-Muster, das in #1356 schon einmal zu
  divergierenden Zahlen in HTML und Klartext derselben Mail geführt hat;
  (c) Sonderstrecken wie `thunder_forecast` (S1) oder der Wintersport-Block (S5)
  haben keinen Katalogbezug — ein „vollständiges" Register wäre an dieser Stelle
  Fiktion, und die Fiktion wäre maschinell bestätigt.

### Option C — Hybrid (Empfehlung)

Den **bestehenden** Matrix-Test `tests/tdd/test_channel_metric_matrix.py` (#1677 B)
schrittweise um Achsen erweitern — Alarm-Renderer, Ausblick, Compare, Formen —
und daneben **ein** schlankes Dokument (dieses hier) nur für das, was Tests nicht
ausdrücken können: Sonderstrecken, Datenkanäle, Architektur-Begründungen,
Entscheidungsstand.

**Grundsatz: alles Prüfbare gehört in Assertions, nicht in Prosa.**

**Regel-Budget-Begründung:** Jede neue Achse ist die **Erweiterung eines
bestehenden, bereits budgetierten Gates** (#1677 B) — kein neues Pflicht-Gate,
kein neues Prüfdatum, keine zusätzliche Blockadefläche am Commit. Das ist der
entscheidende Unterschied zu Option B und der Grund für die Empfehlung.

**Zwei Festlegungen, die zur Empfehlung gehören:**

1. **Form-Dimension als eigene Achse, nicht in der Hauptmatrix.** Die Hauptmatrix
   ist „1 Zeile = 1 Metrik". Die Symbol-Grammatik ist 1:n (S6,
   `SMS_MULTI_SYMBOLS_BY_METRIC`) und würde die Matrix strukturell verzerren.
   Die 1:1-Katalogfelder `format_modes`/`default_format_mode` dürfen dagegen in
   die Hauptmatrix. Ein eigener kleiner Wächter iteriert über die
   Grammatik-Klassen (`tokens/builder.py:47` `PRIORITY`, `:78` `POSITIONAL`),
   nicht über Metrik-IDs. → offene Frage 7b.
2. **Kein Gewitter-Pilot — volle 26 Metriken je neuer Achse.** Gewitter ist
   bereits der bestbewachte Fall (`tests/tdd/test_thunder_low_output_channels.py`
   prüft 6 Renderpfade einer Metrik: Ausblick, Compare-HTML, Trendblock,
   Prosa-Risikofarbe, Telegram-Fußzeile, SMS-Token). Selbst dieses strukturell
   beste Vorbild **übersieht die Kompakt-Zusammenfassung** (`compact_summary.py:567`)
   — ein Beleg dafür, dass „alle Renderpfade" auch bei sorgfältiger Handarbeit
   unvollständig bleibt, solange die Ortsliste nicht aus einer Quelle kommt.
   Teuer ist die Assertion-Logik **pro Zelle**,
   nicht die Metrik-Anzahl — Parametrisierung ist billig. Wo strukturell keine
   Zelle existiert: benannte Ausnahme nach dem Muster `_NIGHT_SCALAR_IDS`
   (`channel_layout.py:88`), nie stilles Überspringen.

## 6. Folge-Scheiben

Acht issue-fähige Einträge. **Keiner davon ist in dem Workflow umgesetzt, der
dieses Dokument erzeugt hat** — er hat ausschließlich diese Datei angelegt.

### Scheibe 1 — Alarm-Renderer × alle `_METRICS`

Matrix-Achse für `render_subject`/`render_email`/`render_telegram`/`render_sms`
(`alert/render.py:292/448/549/617`) über das volle `_METRICS`. Der Test muss
zusätzlich erzwingen, dass keine alarmfähige Metrik in den `_HANDLED_UNITS`-
Ersatzpfad (`alert/render.py:49`) fällt, ohne dort namentlich als Ausnahme zu stehen.
*Risiko: hoch (sicherheitsrelevant, lautloser Fehlermodus). Größe: mittel — vier
Renderer, aber gleichförmige Assertions.* Deckt Fläche 1.

### Scheibe 2 — Ausblick-Tabelle Trip + Compare

Matrix-Achse für `outlook_columns()` (`compare_outlook_metric_ids.py:78`) in
beiden Mail-Pfaden (`email/outlook.py:149`, `:343`, `:522`).
*Risiko: mittel. Größe: mittel–groß — zwei Produktflächen, eine geteilte
Spaltenquelle, deshalb eine Assertion-Familie für beide.* Deckt Fläche 2.

### Scheibe 3 — Nicht-wählbare Register-Metriken

Ein kleiner Test, der über `_METRICS` statt `get_all_metrics()`
(`metric_catalog.py:695`) iteriert und für jede nicht-wählbare Metrik mit
Ausgabefeldern (`sms_code`, `alert_label`, …) prüft, dass sie dort ankommt, wo
das Feld sie hinschickt — heute betrifft das `temperature_cold`.
*Risiko: niedrig. Größe: klein.* **Sollte zuerst laufen** — sie repariert die
Aussagekraft aller anderen Achsen mit. Deckt Fläche 3.

### Scheibe 4 — Kurzform-Mail, Kompaktzeilen, Kompakt-Zusammenfassung, Telegram-Kurzform

Vier bisher namenlose Ausgabeorte als eigene Matrix-Spalten aufnehmen:
`email/compact.py:96`, `email/html.py:878`, `compact_summary.py:567`,
`narrow.py:346/586–597`. Die Verwechslung der ersten drei ist selbst ein
wiederkehrender Fehler und sollte in den Testnamen aufgelöst werden.
*Risiko: mittel. Größe: mittel.* Deckt Flächen 6 und 7.

### Scheibe 5 — Compare-Zellwert-Vollständigkeit

Über die Zeilen-Existenz hinaus prüfen, dass die Zelle je Metrik einen
plausiblen Wert trägt und dass HTML (`compare_html.py:294`) und Klartext
(`comparison.py:70/100`) für dieselbe Wetterlage dieselbe Zahl zeigen.
*Risiko: mittel (Doppel-Quellen-Historie #1356). Größe: mittel.* Deckt Fläche 4.

### Scheibe 6 — Form-Wächter über Grammatik-Klassen

Eigener Wächter über `PRIORITY`/`POSITIONAL` (`tokens/builder.py:47`, `:78`) und
`SMS_MULTI_SYMBOLS_BY_METRIC` (`sms_trip.py:180`): jede Grammatik-Klasse hat
genau eine Prioritätsstufe und eine definierte Position; kein Kürzel kollidiert
mit `HAZARD_SMS_SYMBOLS` (`hazard_symbols.py:15`).
*Risiko: niedrig–mittel. Größe: klein–mittel. Parallel zu 1–5 machbar*, weil sie
eine andere Achse als die Metrik-ID benutzt. Deckt Fläche 8 teilweise, S2, S6.

### Scheibe 7 — Reihenfolge-Wächter jenseits E-Mail und Telegram-rich

Reihenfolge-Zusicherung für SMS, Compare-Klartext und Compare-Telegram.
**Abhängig von der PO-Entscheidung zu Compare-Kanal-Tabs (7a)** — solange
Compare eine globale Metrik-Liste führt (`wiz.activeMetricKeys`) und Trip
kanalweise Layouts (`channel_layouts`), gibt es für Compare keine kanalbezogene
Soll-Reihenfolge, die man prüfen könnte.
*Risiko: mittel. Größe: mittel.* Deckt Fläche 5. **Blockiert bis 7a entschieden ist.**

### Scheibe 8 — Compare-Kanal-Tabs im Frontend

Den strukturellen Bruch zwischen `compareWizardState.svelte.ts`
(`wiz.activeMetricKeys`, eine globale Liste) und dem Trip-Editor
(`WeatherMetricsTab.svelte:755–771`, `channel_layouts` je Kanal) auflösen.
*Risiko: hoch (Datenmodell + Persistenz + Editor). Größe: groß — eigenes
Vorhaben, keine Test-Scheibe.* **Nur nach PO-Entscheidung 7a**; ist sie „nein",
entfällt diese Scheibe und Scheibe 7 wird auf Trip-Kanäle beschränkt.

**Abhängigkeitsbild:** 3 → (1, 2, 4, 5 parallel) · 6 jederzeit parallel ·
7 nach 7a · 8 nur bei 7a = ja.

## 7. PO-Entscheidungsvorlage

Drei Fragen sind **offen** und werden in diesem Dokument bewusst nicht
beantwortet. Wo eine Empfehlung existiert, ist sie als Empfehlung
gekennzeichnet — sie ist keine getroffene Entscheidung.

- [ ] PO-Entscheidung (a) **Compare-Kanal-Tabs — ja oder nein?** Heute führt der
      Compare-Editor eine globale Metrik-Liste (`wiz.activeMetricKeys`), der
      Trip-Editor Layouts je Kanal (`channel_layouts`). Das widerspricht der
      Trip/Compare-Teilungsvorgabe, ist aber ein größerer Umbau (Scheibe 8).
      *Konsequenz eines „nein": Scheibe 8 entfällt, Scheibe 7 deckt nur Trip.*
      Keine Empfehlung — das ist eine Produktentscheidung, keine technische.

- [ ] PO-Entscheidung (b) **Form-Dimension als eigene Achse bestätigen?**
      Empfehlung ist: ja — Form (Aggregation, `format_mode`, Symbol-Grammatik)
      wird separat geführt (Scheibe 6), nicht in die Hauptmatrix gemischt, weil
      `SMS_MULTI_SYMBOLS_BY_METRIC` (S6) 1:n ist. *Konsequenz eines „nein": die
      Hauptmatrix müsste 1:n-fähig werden — deutlich teurer, und jede Zelle
      bekäme eine Sonderfallbehandlung.*

- [ ] PO-Entscheidung (c) **Folge-Scheiben als Epic bündeln oder Einzel-Issues?**
      Acht Scheiben mit Abhängigkeiten (3 vor 1/2/4/5; 7 nach 7a). Ein Epic hält
      die Reihenfolge sichtbar; Einzel-Issues sind leichter parallel zu vergeben.
      Keine Empfehlung — das hängt daran, wie viel parallel laufen soll.

## 8. Anti-Veraltungs-Mechanik

Option A ist verworfen worden, weil Dokumente hier verrotten. Dieses Dokument
darf also nicht auf gute Absichten gebaut sein. Drei Bausteine, in dieser
Reihenfolge belastbar:

**(a) Drift-Schutz durch Parametrisierung — automatisch, greift heute schon.**
`tests/tdd/test_channel_metric_matrix.py` ist über `get_all_metrics()` × Kanäle
parametrisiert. Eine neue Katalog-Metrik erzeugt dort **sofort** neue Testfälle,
ohne dass jemand die Testdatei anfasst. Das ist der Grund, warum die Achsen aus
Abschnitt 6 in **diese** Datei gehören und nicht in neue Einzeltests: der
Drift-Schutz ist dann für jede neue Achse gratis mit dabei. Bekannte Grenze des
Bestands: der Test prüft Auswahl, Abwahl und paarweise Reihenfolge — keine Werte
und keine Formen; sein Kopfkommentar nennt für den Telegram-Aufruf `narrow.py:644`,
der Aufruf steht am Commit 1c38a5ac in `narrow.py:661`.

**(b) Die strukturelle Blindstelle schließen — Scheibe 3.** Solange alles über
`get_all_metrics()` (`metric_catalog.py:695`) iteriert, ist (a) für
nicht-wählbare Metriken wirkungslos. Ein Test über das volle `_METRICS` ist die
Voraussetzung dafür, dass „parametrisiert" auch „vollständig" heißt.

**(c) `doc-compliance-test` für die Prosa-Teile — Vorbild `tests/test_adr_index_drift.py`.**
Dieser Test hält Index und Dateien im ADR-Ordner konsistent und ist das im
Projekt etablierte Muster für „Dokument darf nicht vom Code abweichen"
(er ist zugleich die zugelassene Ausnahme von der Regel, dass
Dateiinhalt-Prüfungen kein Verhaltensnachweis sind — Marker `# doc-compliance-test`).
Übertragen auf dieses Dokument sind zwei Prüfungen sinnvoll und billig:
jede hier genannte Datei existiert, und jeder hier genannte Test existiert.
Das fängt genau den Verrottungsfall von `telegram_output.md` (verweist auf
entfernten Signal-Code). Zeilennummern sollte dieser Test **nicht** prüfen —
sie verschieben sich bei jedem Commit und würden den Test zum Dauerärgernis
machen, ohne einen echten Fehler zu fangen.

**Pflegeregel — wann muss dieses Dokument angefasst werden?**

| Auslöser | Was zu tun ist |
|---|---|
| Neue Metrik in `_METRICS` | nichts, wenn alle Ausgabeorte katalog-getrieben sind — genau dafür ist Spalte *Quelle* da. Sonst: handgeschriebene Orte aus Abschnitt 2 durchgehen |
| Neuer Ausgabeort / neuer Kanal | **immer** eine Zeile in Abschnitt 2, inklusive Wächter-Spalte („unbewacht" ist eine gültige Antwort) |
| Neuer Pfad ohne Katalogbezug | Eintrag in Abschnitt 3 — sonst wiederholt sich #1475 |
| Eine Folge-Scheibe wird umgesetzt | Wächter-Spalte in Abschnitt 2 aktualisieren und die Fläche in Abschnitt 4 streichen |
| PO entscheidet 7a/7b/7c | Checkbox in Abschnitt 7 schließen, Ergebnis dort notieren, Scheiben 7/8 nachziehen |

## Verwandte Dokumente

| Dokument | Verhältnis zu diesem hier |
|---|---|
| `docs/reference/sms_format.md` | gepflegtes Token-Register — Formvorbild für Abschnitt 2, deckt nur SMS ab |
| `docs/reference/renderer_email_spec.md` | „Metric Display Contract" des E-Mail-Vollformats |
| `docs/features/gewitter-gesamtkonzept.md` §8 | beste vorhandene Ort-Tabelle, aber für **eine** Metrik |
| `docs/reference/api_contract.md` §15 | vollständigste Feldreferenz der `MetricDefinition` (`compact_label` fehlt dort) |
| `docs/adr/README.md` (ADR-0042) | maßgebliche Form-Taxonomie Namensform × Platzgrenze; wird hier zitiert, nicht abgelöst |
| `docs/specs/modules/konzept_1514_metrik_ausgabeorte.md` | Spec dieses Dokuments |
| ⚠️ `docs/specs/modules/output_channel_renderers.md`, `telegram_output.md`, `layout_tab_*.md` | **veraltet** — kennen Compare/Kaskade nicht bzw. referenzieren entfernten Signal-Code (#610). Beleg für die Verwerfung von Option A |
