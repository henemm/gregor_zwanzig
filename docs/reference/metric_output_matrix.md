# Metrik-Ausgabeorte je Kanal — Referenz & Entscheidungsvorlage

> **Stand: 2026-08-13, Commit-Basis: 21a6a1ef** · Issue #1514 (`triage:po`)
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

> **🔴 Seit #1719 S4 (2026-08-13) ist `compact_label` KEIN unabhängig gepflegtes
> Feld mehr**, sondern wird aus dem Register-Kürzel (`sms_code`) **abgeleitet**.
> Abweichen darf nur, was in einer benannten Ausnahmeliste mit Begründung steht
> — heute `temperature` (`T`) und `wind_chill` (`TF`), weil deren Register-Kürzel
> eine *Tagesauswertung* bezeichnen (`D`/`K` bzw. `FK`/`FD`/`WC`), die
> Telegram-Zelle aber einen *Stundenwert* zeigt. Ein Wächter
> (`tests/unit/test_telegram_kuerzel_folgt_register.py`) macht jeden neuen
> Alleingang rot.
>
> Grund: die beiden Felder wurden getrennt von Hand gepflegt und sind
> auseinandergelaufen — 11 von 25 Größen trugen in Telegram ein anderes Kürzel
> als in der SMS, ohne fachlichen Grund (Luftdruck `P` vs. `HP`, Bewölkung `C`
> vs. `CT`, Nacht-Tiefsttemperatur `TN` vs. `N`). Wer hier ein Kürzel ändern
> will, ändert `sms_code` — nicht `compact_label`.

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
| Kompakt-Zusammenfassung (Fließtext-Block **in** der Vollmail) | `src/output/renderers/compact_summary.py:567` `_format_thunder()`, Aufruf `:243`; aktiviert über `src/output/renderers/trip_report.py:173` `options.show_compact_summary`, Formatter-Einstieg `trip_report.py:942` | handgeschrieben — `thunder` ist die **einzige** Metrik mit eigener Formatier-Methode | nur metrikspezifisch: `tests/tdd/test_hail_compact_summary_thunder.py:75`, `:89`, `:107` (Gewitter/Hagel) und seit #1680 S2 `test_thunder_origin_trip.py` für den Herkunfts-Zusatz (beide Textzweige, bis `email_plain`). Als Metrik×Kanal-Ort weiterhin **unbewacht** |
| Ausblick / 3-Tages-Tabelle (Trip-Mail) | `src/output/renderers/email/outlook.py:174–298` (HTML), `:353–403` (Klartext) — **feste** Spalten Tag/N/D/R/PR/Wind/Böen/Gew (+ACC) | **nicht** katalog-getrieben: alle drei Trip-Aufrufstellen (`email/html.py:1357`, `email/plain.py:338`, `trip_report_scheduler.py:1844`) übergeben **kein** `metrics` | `tests/tdd/test_trip_outlook_parity.py` (Byte-Golden über das GANZE HTML + Klartext) — strenger als eine Metrik-Achse; **keine Metrik×Kanal-Fläche**, weil der Nutzer hier nichts wählen kann (gemessen 2026-08-11, #1703 S2) |
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
| Compare SMS | `comparison.py:488` `_CHANNEL_METRICS`; Zellbau `comparison.py:641` `_sms_metric_cell()` über `_fmt_overview_cell()` | handgeschrieben | **unbewacht** · 🔴 **Korrektur 2026-08-11 (am Code gemessen):** hier stand „genau 6 Metriken“ — das ist falsch. `_CHANNEL_METRICS` ist eine **Rangliste** für die Platzvergabe, **keine Auswahl**. Jede vom Nutzer gewählte Metrik erscheint in der Compare-SMS, auch Gewitter. Wer sich auf die alte Lesart verlässt, hält einen Ausgabeort für tot, der lebt |
| **Herkunft der Gewitterstufe — Ortsvergleich** (Zusatz `· CAPE`, #1680 S1, live 2026-08-12) | Träger-Ermittlung `src/output/metric_format.py` `thunder_signal_carriers()` + Katalog `THUNDER_SIGNAL_LABEL_DE`; Ortsauflösung `compare_html.py` `loc_thunder_signals()`; Anhängen `_fmt_thunder(v, hail, signals)`; Kanalschalter `comparison.py` `_fmt_overview_cell(..., include_origin=)` | katalog-getrieben (vier feste Signalschlüssel; ein unbekannter Name fällt roh durch, wird nie erfunden) | `tests/tdd/test_thunder_origin_compare.py` (12 ACs, jedes durch die volle Renderkette bis zum zurückgegebenen Body) + `test_thunder_origin_snapshot_roundtrip.py`. **Erscheint NUR in HTML-Übersicht, Klartext und Telegram** — SMS/Premium-SMS aktiv abgewählt (`include_origin=False`, mit Begründungskommentar im Code), Compare-**Stundentabelle** bewusst ohne (`_HOUR_FMT_OVERRIDES` übergibt den Parameter nicht) |
| **Herkunft der Gewitterstufe — Trip** (#1680 S2, live 2026-08-12) | Vereinigungsregel `src/output/metric_format.py` `union_of_max_carriers()` (**die eine** Stelle, an der `"thunder_level_max_signals": "union_of_max_carriers"` gerechnet wird; Vorbild `hail_priority()`). Drei Andockstellen, alle über denselben Helfer: `weather_metrics.py:616` `_compute_thunder_level_signals()` (Stunden→Segment, jetzt dünner Wrapper) · `trip_command_processor.py:804` `_aggregate_day()` (Wegpunkte→Tag) · `day_window.py:56` `_merge_hour()` (Punkte→Stunde). Anzeige: `compact_summary.py:567` `_format_thunder()` und `trip_command_processor.py:863` `_fmt_gewitter()` | katalog-getrieben; Nennreihenfolge = Erstauftrittsreihenfolge, die pro Datenpunkt bereits die Katalogreihenfolge von `THUNDER_SIGNAL_LABEL_DE` ist | `tests/tdd/test_thunder_origin_trip.py` (13 Tests, jeder bis zum zugestellten Text: `email_plain` bzw. `confirmation_body`). **Erscheint NUR in Kurzzusammenfassung und GEWITTER-Antwort**, also E-Mail + Telegram — SMS/Premium-SMS aktiv abgewählt mit Begründungskommentar. 🔴 `_format_thunder()` hat **zwei** Textzweige (`friendly=True` → `⚡ möglich …`, Default aus `build_default_display_config()`; `False` → `Gewitter möglich …`) — beide tragen den Zusatz, je ein eigener Test. Ein Suffix nur an einem Zweig wäre grün getestet und für den Normalnutzer unsichtbar |
| **Herkunft der Gewitterstufe — vier weitere Orte** (#1680 S3, live 2026-08-13) | Pille `email/helpers.py:1743` `_pill_for_metric()` (Träger über `union_of_max_carriers()` aus den Tagesfenster-Punkten) · Kommando-Timeline `trip_command_processor.py:954` `_fmt_timeline()` (aus `p.metrics.thunder_level_max_signals`) · GLANCE-Tageszeile `trip_command_processor.py:853` `_fmt_day_agg()` (liest `agg["thunder_signals"]`, seit S2 vorhanden) · Ortsvergleich-Stundentabelle `compare_html.py:992` `_render_hour_row()` und `comparison.py:330` (dritter Parameter an `_fmt_thunder`, seit S1 vorhanden) | katalog-getrieben | `tests/tdd/test_thunder_origin_four_places.py` (17 Tests, jeder bis zum zugestellten Text). 🔴 **Die F001-Garantie aus S2 trägt an der Stundenzelle NICHT** — dort wird `dp.thunder_level_signals` **roh** durchgereicht, ohne `union_of_max_carriers()`. Dass eine `NONE`-Stunde nicht zu `— · CAPE` wird, hält allein `thunder_signal_carriers()` (leere Liste bei `NONE`); einziger Wächter ist `test_ac16_ohne_gewitter_bleibt_die_compare_stundenzelle_zeichengleich`. 🔴 **„kein Gewitter" heißt an den Orten DREI verschiedene Dinge**: Pille `kein Gewitter` · Timeline/GLANCE `kein` · Compare-Stundenzelle `—`. Nicht harmonisieren. Der Zusatz sitzt an der **Aufrufstelle**, nicht im Rumpf von `_fmt_thunder` — der speist auch die S1-Übersichtszeile |
| **Herkunft der Gewitterstufe — Trip-Stundentabelle** (#1680 S4, live 2026-08-13) | Seitenkanal Pro-Stunde `trip_report.py:692` `_dp_to_row()` (`row["_thunder_signals"] = getattr(dp, "thunder_level_signals", None)`, kein eigener `NONE`-Guard — hängt an `thunder_signal_carriers()`s Garantie) · Seitenkanal Nacht-Block `trip_report.py:651` `_aggregate_night_block()` (`union_of_max_carriers(...)`, F001-Garantie aus S2 greift hier direkt) · Anhängen `email/helpers.py:751-757` `fmt_val()` Roh-/Klartext-Zweig (`thunder_signal_label()`, Muster `_fmt_thunder()`/S1) | katalog-getrieben | `tests/tdd/test_thunder_origin_trip_hour_table.py` (13 ACs, jeweils bis zum zurückgegebenen `email_plain`/`html_body`/Telegram-Bubble-Text). **Erscheint im E-Mail-Klartext/Roh-HTML UND strukturell mit-vererbt in der Telegram-rich-Stundentabelle** (Bubbles) — `narrow.py::_cell()` ruft `fmt_val()` ohne `html=True` über dieselbe `_dp_to_row()`-Konstruktion, kein eigener Telegram-Code-Pfad, aber der feste 32-Zeichen-Umbruch (`narrow.py:60` `_TG_TABLE_WIDTH`) kann Stufe und Zutat auf zwei Zeilen trennen (bewusst hingenommen, kein Datenverlust). SMS/Premium-SMS aktiv abgewählt geblieben (Rückfall `sms_text or email_plain` als unproblematisch nachgewiesen). **HTML-Ampel-Kreis-Modus bewusst unverändert** — kein visueller Herkunfts-Indikator. Compare bleibt strukturell unberührt: `fmt_val()` wird von keinem Compare-Rendermodul importiert (grep-belegt) |
| Herkunft der Gewitterstufe — **weiterhin ohne** | Mehrtages-Ausblick `email/outlook.py:174–298`/`:353–403` · Gewitter-Vorschau `email/html.py:1307`/`plain.py:307` | — | bewusst unverändert (#1680 offen). Bei beiden gehen die Träger **strukturell** verloren: `HourlyValue` (`src/output/tokens/dto.py:15-18`) ist ein frozen Dataclass mit nur `hour` und `value`. `aggregate_stage()` (`weather_metrics.py:1168`) kennt die Regel weiterhin **nicht** (`else` → `values[0]`); der Mehrtages-Ausblick (`trip_report_scheduler.py:2026`) wäre sein erster Verbraucher. **Go-DTO und Frontend fallen ersatzlos** — in `internal/` wird `model.SegmentWeatherSummary` nirgends konstruiert oder gelesen, im Frontend rendert keine Komponente eine echte Gewitterstufe |
| Compare Ausblick | `src/output/renderers/compare_outlook_metric_ids.py:78` `outlook_columns()`; Aufrufe `comparison.py:348` (Klartext), `compare_html.py:1101`/`:1175` (HTML) — **der einzige** Pfad, der `outlook_columns()` tatsächlich erreicht | katalog-getrieben, 25 Paare aus `get_compare_metric_catalog()` | `tests/tdd/test_channel_metric_matrix.py` AC-S2-1..8 (#1703 S2) — Spalte, Kopf-Eindeutigkeit, **Zellwert**, beide Aggregationspfade gegeneinander; Soll aus `tests/helpers/outlook_columns.py` gerechnet |
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
| Frontend Compare | Übersicht: `compareWizardState.svelte.ts` `wiz.channelActiveMetricKeys` (#1703 Scheibe 8, live 2026-08-13) — kanalweise wie beim Trip. Ausblick/Stundenverlauf: weiterhin `wiz.activeMetricKeys` + je eigene globale Liste, **keine Kanal-Tabs** | struktureller Bruch besteht nur noch für Ausblick/Stundenverlauf; Übersicht gelöst (ADR-0053), Wächter `tests/unit/test_compare_channel_metrics_reach_the_renderer.py` (Wirkung) + `frontend/e2e/compare-uebersicht-kanal-{bedienung,persistenz}.staging.spec.ts` (Oberfläche) |

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

**✅ Erledigt (2026-08-11, Epic #1703 Scheibe 1):** Wächter in
`tests/tdd/test_channel_metric_matrix.py` (`test_ac_s1_1_alarm_beschriftung_in_betreff_mail_telegram`,
`test_ac_s1_2_sms_kuerzel_als_eigenstaendiger_token` + `…_sms_praefix_gegenprobe`,
`test_ac_s1_3_soll_menge_wird_gerechnet_und_ist_plausibel`,
`test_ac_s1_4_handled_units_deckt_sich_mit_der_katalog_formatierung`,
`test_ac_s1_5_gewitter_allein_/_gebuendelt_ohne_prozentzeichen`,
`test_ac_s1_6_uebrige_groessen_behalten_ihre_katalog_einheit` + `…_prozentzeichen_bleibt_wo_die_einheit_es_verlangt`,
`test_ac_s1_7_doppeldeutige_beschriftung_ist_benannt` + `…_gleichnamige_groessen_trennt_nur_die_kurznachricht`).
Parametrisiert über die **gemessene Soll-Menge von 11** alarmfähigen Katalog-Kennungen —
gerechnet aus dem Produktivmodul (`_ALERT_METRIC_TO_CATALOG_ID`,
`weather_change_detection.py:82-99`), nie im Test aufgezählt: `cape`, `freezing_level`,
`fresh_snow`, `gust`, `precipitation`, `snowfall_limit`, `temperature`, `temperature_cold`,
`thunder`, `visibility`, `wind`. Auch die `_HANDLED_UNITS`-Whitelist ist jetzt gegen das
tatsächliche Formatierungsverhalten des Katalogs gehalten (beide Richtungen, 12 Fälle über
die Vereinigung aus Katalog-Einheiten und Whitelist-Einträgen). Mitrepariert: der
Gewitter-Sonderfall in `_unit_display()` hängte im **gebündelten** Alarm ein Prozentzeichen
an eine Stufe (0–3) — ersatzlos entfernt, PO-Entscheidung #1585 löst die ältere
#978-Design-Vorlage ab; die drei Bestands-Assertions in
`tests/tdd/test_978_deviation_line_readability.py` (:218, :232, :350) und der dortige
Modul-Docstring sind nachgezogen. Spec:
`docs/specs/modules/fix_1703_s1_alert_renderer_matrix.md`.

**Grenzen dieses Wächters (benannt, nicht behoben):**
- `CorridorEvent` (Wertebereichs-Alarm) bleibt unbewacht — toter Pfad:
  `evaluate_corridor_thresholds()` (`corridor_threshold.py:68`) hat keinen Aufrufer in
  `src/`/`api/`, und der produktive `_send_alert()` (`trip_alert.py:296`) übergibt
  `corridor_hits` nicht.
- `OnsetEvent` (Radar-Beginn) bleibt unbewacht — strukturell metrik-los: die
  Datenstruktur hat kein `metric_id`-Feld (`alert/model.py:30-46`), der Renderer
  verzweigt binär über `is_convective` mit festen Wörtern.
- Für `snowfall_limit`, `temperature_cold` und `wind` kann **kein** Test bemerken, wenn
  sie aus der Rückwärts-Abbildung entfernt werden: sie deklarieren im Katalog kein
  `alert_metrics` und hängen allein an `_ALERT_METRIC_TO_CATALOG_ID`. Die
  Größenschranke des Vakuum-Schutzes (≥ 8) fängt eine einzelne Entfernung nicht
  (11 − 1 = 10).

**Fläche 2 — Alle Metriken × Ausblick-Tabelle.** `outlook_columns()`
(`compare_outlook_metric_ids.py:78`).

> **✅ Erledigt (2026-08-11, Epic #1703 Scheibe 2, PR #1748, Merge `9aced271`).**
>
> **Die hier ursprünglich behauptete Prämisse war falsch und ist korrigiert:** Diese Zeile
> sagte, `outlook_columns()` werde „von Trip-Mail **und** Compare-Mail" genutzt. Gemessen
> übergeben **alle drei** Trip-Aufrufstellen kein `metrics`-Argument und laufen im festen
> Legacy-Spaltenpfad; `outlook_columns()` erreicht **nur** der Ortsvergleich. Der
> Trip-Ausblick hat keine wählbaren Spalten und damit keine Metrik×Kanal-Fläche — er ist
> zudem durch den Byte-Golden `test_trip_outlook_parity.py` strenger bewacht, als eine
> Matrix-Achse es wäre. Die Scheibe ist deshalb **Compare-only** (PO-freigegeben).
>
> Wächter: `tests/tdd/test_channel_metric_matrix.py` AC-S2-1..8, Soll-Menge (25 Paare) aus
> `get_compare_metric_catalog()` gerechnet via `tests/helpers/outlook_columns.py` inkl.
> Vakuum-Schutz. Ist-Werte aus der **echten** Mail (`render_compare_email()`, HTML und
> Klartext in einem Aufruf).
>
> **Mitrepariert — der eigentliche Fund:** Fünf der 25 wählbaren Spalten waren *dauerhaft
> leer* (Schneehöhe, Neuschnee, Windrichtung, Gefühlte Temperatur Min/Max). `summarize_points()`
> (`weather_metrics.py:1071`) ist eine handgepflegte Aufzählung und hatte fünf `_compute_*`-Regeln
> nie verdrahtet, die `compute_extended_metrics()` (`:752-760`) längst nutzt. Gegenrichtung zu
> #1391; #1324/#1392 sind Flicken an derselben Naht. AC-S2-5 hält beide Pfade nun gegeneinander.
>
> **Adversary-Finding F001 (HIGH), geschlossen:** „Soll rechnen statt tippen" sichert
> Vollständigkeit, **nie Zuordnung** — und die Lücke lag diesmal nicht im Katalog, sondern im
> Fix selbst: eine Vertauschung von `wind_chill_min_c`/`wind_chill_max_c` blieb grün, weil kein
> Test im Repo die *Zahlenwerte* prüfte. AC-S2-8 schließt das mit unabhängig gerechneten
> Erwartungswerten. Details: `docs/specs/modules/fix_1703_s2_ausblick_matrix.md`.
>
> Grenzen: Telegram (`narrow.py:571`) und Kompakt-Mail (`email/compact.py:227`) haben eigene
> Ausblick-Implementierungen, die `outlook.py` nicht importieren → Scheibe 4.
>
> **Nachtrag (2026-08-12, Scheibe 4 abgeschlossen):** dieser Trend-/Ausblick-Pfad
> (`narrow.py:571` `_outlook_lines()`, `email/compact.py` "Naechste Etappen"-Block —
> beide über `format_trend_tokens()`) ist NICHT Teil dessen, was Scheibe 4 bewacht.
> Deren vier Ausgabeorte (s. Abschnitt 6) sind die Metrik-Übersichts-/Kurzform-Pfade
> (Pillen, mobile Zeilen, Fließtext-Zusammenfassung, Telegram-Kurzübersicht), nicht
> dieser separate Trend-Block. Der „→ Scheibe 4"-Verweis ist damit nur teilweise
> eingelöst; der Trend-/Ausblick-Pfad in Telegram und Kompakt-Mail bleibt unbewacht.

**Fläche 3 — Nicht-wählbare Register-Metriken.** `metric_catalog.py:695` —
`get_all_metrics()` gibt `[m for m in _METRICS if m.selectable]` zurück. Jeder
Vollständigkeitstest iteriert über diese Funktion und **kann** deshalb
`temperature_cold` nicht sehen, obwohl die Metrik einen `sms_code` hat und in
Ausgaben erscheint. Das ist keine Lücke in einem Test, sondern eine Blindstelle
**aller** Matrix-Tests gleichzeitig.
*Priorität 1, weil die Behebung klein ist (ein Test über `_METRICS` statt
`get_all_metrics()`) und die Wirkung strukturell: sie repariert die Aussagekraft
jeder künftigen Achse mit.*

**✅ Erledigt (2026-08-10, Epic #1703 Scheibe 3):** Wächter in
`tests/tdd/test_channel_metric_matrix.py` (`test_ac1_confidence_absent_from_mail_telegram_compare`
bis `test_ac8_non_selectable_metrics_stay_out_unless_exempt`) — parametrisiert über `_METRICS` +
`_SELECTABLE_GATE_EXEMPT`, deckt `confidence`/`cape`/`temperature_cold` einzeln ab plus generisch
jede künftige `selectable=False`-Metrik mit Ausgabefeld. Spec:
`docs/specs/modules/fix_1703_s3_selectable_metrics.md`. Adversary VERIFIED (Finding F001 zu AC-3
korrigiert — der Kältealarm bleibt nicht wegen der Exemption aktiv, sondern über den OR-Tupel-
Mechanismus in `is_alert_metric_active()`, s. Spec-Korrekturabschnitt). Nebenbefund (kein Fix
dieser Scheibe): `temperature_cold` erscheint als echte Dublette „TmpMin"/„Temp" in der
Stundentabelle (AC-6, Charakterisierung).

### 4.2 Priorität 2 und 3

| # | Unbewachte Fläche | Ort | Prio | Bemerkung |
|---|---|---|---|---|
| 4 | Compare-Übersichtstabelle: **Zellwert** je Metrik | `compare_html.py:294`, `comparison.py:70/100` | 2 | ✅ Erledigt (2026-08-12, Epic #1703 Scheibe 5): Bei Nachmessung trug die pauschale Aussage „nur Zeilen-Existenz bewacht" nicht mehr — 15 der 25 `CV2_METRICS`-Zeilen hatten aus #1296/#1324/#1351/der Gewitter-Suite bereits Wert+Paritäts-Tests. Neuer Wächter `tests/tdd/test_channel_metric_matrix.py` AC-S5-1 (Soll-Menge 15+10=25, disjunkt), AC-S5-2 (die 10 verbleibenden Zeilen, HTML+Klartext gegen unabhängig gerechnete Werte über `render_compare_email()`), AC-S5-3 (Engine-Vorrang vor Live-Ableitung), AC-S5-4 (Formatierungs-Konsistenz `format_value()` vs. `CV2_METRICS`-`decimals`, 10 Felder einzeln), AC-S5-5 (Fehlzeichen-Divergenz HTML `—` vs. Klartext `-`, charakterisiert), AC-S5-6 (Abhängigkeits-Anker auf die 15 bereits gedeckten Zeilen). Reine Charakterisierung, kein Produktivcode-Fix. Spec: `docs/specs/modules/fix_1703_s5_compare_zellwerte.md` |
| 5 | **Reihenfolge** in allen Kanälen außer E-Mail und Telegram-rich | `email/helpers.py:1908`, `comparison.py:127/729`, `compare_html.py:798` | 2 | ✅ Erledigt (2026-08-14, Epic #1703 Scheibe 7). 🔴 **Zwei Angaben dieser Zeile waren bei Nachmessung falsch und sind hier ersetzt:** (a) `tokens/builder.py:78` — die Trip-SMS-Reihenfolge ist seit #1677/#1660 B bewacht (`test_channel_metric_matrix.py::test_ac15_…` (c), paarweise über alle 26 Katalog-Metriken, `_POSITION_SORTABLE_CATEGORIES`); (b) „Compare-Klartext nutzt die Reihenfolge nur als Sichtbarkeitsfilter (#1356)" — überholt seit #1359, `_ordered_rows()` (`comparison.py:127-140`) setzt sie um, der HTML-Zwilling `_visible_metrics()` (`compare_html.py:798`) ebenso. Tatsächlich fehlte die **Katalog-Deckung** (bewacht waren 4 von 25 Metriken über `tests/unit/test_compare_metric_order.py`) und die **Kanal-Achse** aus Scheibe 8. Neuer Wächter `tests/tdd/test_channel_metric_matrix.py` AC-S7-1 (Soll-Menge 25 gerechnet + Vakuum-Schutz), AC-S7-2/3 (HTML und Klartext derselben Sendung, alle 25 paarweise), AC-S7-4 (Altbestands-Divergenz HTML `CV2_METRICS` vs. Klartext `_PLAIN_ROWS` ab Position 3 — charakterisiert, nicht gefixt, → #1199), AC-S7-5 (drei Kanäle, drei Reihenfolgen, EINE Sendung — gemessen an der zugestellten Ausgabe über Versand- **und** Vorschaupfad), AC-S7-6 (**Produktivcode-Fix**, s.u.), AC-S7-7 (Trip-Telegram-Kurzübersicht; benennt die zwei Ordnungsquellen in `render_telegram_bubbles()`), AC-S7-8 (Compare-Telegram/SMS unter Kappung — Telegram 7 Spalten, SMS 153 Zeichen), AC-S7-9 (Kompakt-Zusammenfassung ohne Reihenfolge-Achse, benannte Ausnahme). Spec: `docs/specs/modules/fix_1703_s7_reihenfolge_matrix.md` |
| 6 | Kurzform-Mail, mobile Kompaktzeilen und Kompakt-Zusammenfassung | `email/compact.py:96`, `email/html.py:878`, `compact_summary.py:567` | 2 | ✅ Erledigt (2026-08-12, Epic #1703 Scheibe 4): **drei** verschiedene Orte, die alle „compact" heißen und regelmäßig verwechselt werden — `render_compact()` ist das eigene Kurzformat, `_render_mobile_compact_rows()` sitzt **in** der Vollmail, `CompactSummaryFormatter` erzeugt den Fließtext-Block ebendort — jetzt einzeln bewacht: `tests/tdd/test_channel_metric_matrix.py` AC-S4-1/2/3 (Ort 1), AC-S4-5 (Ort 2), AC-S4-6/6b/7/8-10 (Ort 3). Reine Charakterisierung, kein Produktivcode-Fix. Spec: `docs/specs/modules/fix_1703_s4_kompaktform_matrix.md` |
| 7 | **Telegram-Kurzform** als eigener Ausgabeort | `narrow.py:346`, `:528–532`, `:586–597` | 2 | ✅ Erledigt (2026-08-12, Epic #1703 Scheibe 4): Wächter `tests/tdd/test_channel_metric_matrix.py` AC-S4-12/13/14 (Auswahl/Abwahl generisch über alle wählbaren Metriken, Resolver-Divergenz zu Ort 1 als Charakterisierung, confidence-Absenz). Reine Charakterisierung, kein Produktivcode-Fix. Spec: `docs/specs/modules/fix_1703_s4_kompaktform_matrix.md` |
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

### Scheibe 1 — Alarm-Renderer × alle `_METRICS` ✅ ERLEDIGT (2026-08-11)

Matrix-Achse für `render_subject`/`render_email`/`render_telegram`/`render_sms`
(`alert/render.py:292/448/549/617`) über das volle `_METRICS`. Der Test muss
zusätzlich erzwingen, dass keine alarmfähige Metrik in den `_HANDLED_UNITS`-
Ersatzpfad (`alert/render.py:49`) fällt, ohne dort namentlich als Ausnahme zu stehen.
*Risiko: hoch (sicherheitsrelevant, lautloser Fehlermodus). Größe: mittel — vier
Renderer, aber gleichförmige Assertions.* Deckt Fläche 1.

Umgesetzt als 7 ACs (AC-S1-1 bis AC-S1-7) in `tests/tdd/test_channel_metric_matrix.py`,
parametrisiert über die gemessene Soll-Menge von **11** alarmfähigen Kennungen — gerechnet
aus `_ALERT_METRIC_TO_CATALOG_ID`, nicht über `_METRICS` iteriert: die vier Metriken mit
`alert_label`, aber ohne produktiven Alarmweg (`humidity`/`rain_probability` als
Vorboten-Größen, `uv_index`/`snow_depth` ohne Mapping-Eintrag) müssten sonst sofort
wieder ausgenommen werden. Gemessen an den vier echten Renderern, nicht an
`_val()`/`_unit_display()` isoliert. Mitrepariert: Gewitter-Prozentzeichen im gebündelten
Alarm (PO-Entscheidung #1585 löst die #978-Vorlage ab). Details, Soll-Menge, Grenzen und
Mutations-Gegenprobe: `docs/specs/modules/fix_1703_s1_alert_renderer_matrix.md`.

### Scheibe 2 — Ausblick-Tabelle (Compare) ✅ ERLEDIGT (2026-08-11)

Matrix-Achse für `outlook_columns()` (`compare_outlook_metric_ids.py:78`). Deckt Fläche 2.

**Der Titel hieß bis zum Umsetzen „Trip + Compare" — das war falsch.** Gemessen erreicht
`outlook_columns()` nur den Ortsvergleich; alle drei Trip-Aufrufstellen übergeben kein
`metrics`. Der Trip-Ausblick hat keine wählbaren Spalten (feste Sieben) und wird vom
Byte-Golden `test_trip_outlook_parity.py` strenger bewacht, als eine Metrik-Achse es könnte.
Zuschnitt daher **Compare-only**, PO-freigegeben 2026-08-11.

Umgesetzt als 8 ACs (AC-S2-1..8) in `tests/tdd/test_channel_metric_matrix.py`, Soll-Menge
**25 Paare** aus `get_compare_metric_catalog()` gerechnet (`tests/helpers/outlook_columns.py`,
Vakuum-Schutz ≥ 20). Gemessen an der echten Mail über `render_compare_email()` — HTML und
Klartext aus einem Aufruf, damit der Klartext-blinde Fleck des Mail-Validators mitfällt.

**Produktivfix:** fünf dauerhaft leere Spalten (Schneehöhe, Neuschnee, Windrichtung, Gefühlte
Temperatur Min/Max), Ursache in `summarize_points()`; AC-S2-5 hält beide Tages-Aggregationspfade
gegeneinander. **F001 (HIGH, geschlossen):** die Zuordnungs-Blindstelle bestand im Fix selbst,
nicht nur im Katalog — AC-S2-8 prüft die Zahlenwerte gegen unabhängig gerechnete Erwartungen.
Details, Fehlzeichen-Falle (`–` U+2013 vs. `—` U+2014) und Grenzen:
`docs/specs/modules/fix_1703_s2_ausblick_matrix.md`.

### Scheibe 3 — Nicht-wählbare Register-Metriken ✅ ERLEDIGT (2026-08-10)

Ein kleiner Test, der über `_METRICS` statt `get_all_metrics()`
(`metric_catalog.py:695`) iteriert und für jede nicht-wählbare Metrik mit
Ausgabefeldern (`sms_code`, `alert_label`, …) prüft, dass sie dort ankommt, wo
das Feld sie hinschickt — heute betrifft das `temperature_cold`.
*Risiko: niedrig. Größe: klein.* **Sollte zuerst laufen** — sie repariert die
Aussagekraft aller anderen Achsen mit. Deckt Fläche 3.

Umgesetzt als 8 ACs (AC-1 bis AC-8) in `tests/tdd/test_channel_metric_matrix.py`, gemessen
gegen den echten Renderpfad (`TripReportFormatter().format_email()`, nicht die produktiv
ungenutzte `email/helpers.py::dp_to_row()`). Details, Sollzustand je Metrik, Mutations-
Gegenprobe: `docs/specs/modules/fix_1703_s3_selectable_metrics.md`.

### Scheibe 4 — Kurzform-Mail, Kompaktzeilen, Kompakt-Zusammenfassung, Telegram-Kurzform ✅ ERLEDIGT (2026-08-12)

Vier bisher namenlose Ausgabeorte als eigene Matrix-Spalten aufnehmen:
`email/compact.py:96`, `email/html.py:878`, `compact_summary.py:567`,
`narrow.py:346/586–597`. Die Verwechslung der ersten drei ist selbst ein
wiederkehrender Fehler und sollte in den Testnamen aufgelöst werden.
*Risiko: mittel. Größe: mittel.* Deckt Flächen 6 und 7.

Umgesetzt als 15 ACs (AC-S4-1 bis AC-S4-15, teils als kombinierte
Positiv-/Negativ-Assertion in einer parametrisierten Testfunktion
zusammengefasst) in `tests/tdd/test_channel_metric_matrix.py`, gemessen
gegen den echten Renderpfad (`TripReportFormatter().format_email()`,
`email_format="compact"` bzw. Telegram-Pfad) statt isolierter
Direktaufrufe — dieselbe Prüfort-=-Wirkort-Pflicht wie in Scheibe 3.
Reine Charakterisierung, **kein Produktivcode-Fix**, auch dort nicht, wo
die Recherche eine strukturelle Eigenheit aufdeckte: Resolver-Divergenz
Ort 1 (`resolve_trip_active_metrics()`, Fallback auf
`DEFAULT_TRIP_METRIC_IDS` bei leerer Auswahl) vs. Ort 5
(`get_enabled_metric_ids()`, kein Fallback) — als Nebenbefund in #1199
gebucht (Eintrag 2026-08-12), kein Fix hier; Positivliste von
`format_stage_summary()` bleibt akzeptierter Dauerzustand (PO-Anschluss
an #1214 Scheibe 5c). Ort 4 (`format_location_summary()`,
Compare-Wrapper) bleibt ohne Test — totes Gleis seit #1300. **Nicht
Gegenstand dieser Scheibe:** die eigenen Ausblick-/Trend-Implementierungen
in `narrow.py:571` (`_outlook_lines()`) und `email/compact.py`
("Naechste Etappen"-Block), die `outlook.py` nicht importieren (s.
Fläche 2 Grenzen, Nachtrag oben) — Scheibe 4 deckt die
Metrik-Übersichts-/Kurzform-Pfade, nicht diesen separaten Trend-Block.

**Adversary-Finding F001 (geschlossen):** die ursprüngliche Spec-Fassung
behauptete für AC-S4-3 (Ort 1) und AC-S4-8 (Ort 3), dieselbe zentrale
`_is_selectable()`-Gate-Wirkung greife wie an Ort 5. Die
Mutations-Gegenprobe widerlegte das — Ort 1 und Ort 3 sind durch lokale,
gate-unabhängige Mechanismen geschützt (Pillen-Katalog-Whitelist
`_PILL_CATALOG_ORDER` bzw. fehlender `confidence`-Zweig in
`compact_summary.py`); nur AC-S4-14 (Telegram) belegt die Gate-Wirkung
tatsächlich. Spec entsprechend korrigiert (Docstrings + AC-Wortlaut).
Details: `docs/specs/modules/fix_1703_s4_kompaktform_matrix.md`.

### Scheibe 5 — Compare-Zellwert-Vollständigkeit ✅ ERLEDIGT (2026-08-12)

Über die Zeilen-Existenz hinaus prüfen, dass die Zelle je Metrik einen
plausiblen Wert trägt und dass HTML (`compare_html.py:294`) und Klartext
(`comparison.py:70/100`) für dieselbe Wetterlage dieselbe Zahl zeigen.
*Risiko: mittel (Doppel-Quellen-Historie #1356). Größe: mittel.* Deckt Fläche 4.

**Korrektur der Scheiben-Prämisse (bei Nachmessung, vor dem Schreiben der
ACs):** Die pauschale Aussage „nur Zeilen-Existenz bewacht" traf nur noch auf
10 der 25 `CV2_METRICS`-Zeilen zu — 15 hatten aus #1296/#1324/#1351 und der
Gewitter-Testsuite bereits Wert+Paritäts-Tests. Die Wert-**Quelle** war zudem
bereits geteilt (`comparison.py` importiert `_metric_value` direkt aus
`compare_html.py`), das eigentliche Risiko lag in der **Formatierung**
(drei parallele Wege: geteilte Formatter, eigene Lambdas, katalog-getriebenes
`format_value()`), nicht im Wert selbst.

Umgesetzt als 6 ACs (AC-S5-1 bis AC-S5-6, 29 parametrisierte Testfälle) in
`tests/tdd/test_channel_metric_matrix.py`, gemessen gegen die echte Mail
(`render_compare_email()`, HTML und Klartext in einem Aufruf). AC-S5-1 rechnet
die 15+10-Aufteilung der 25 Zeilen disjunkt und lückenlos; AC-S5-2 sichert die
10 zuvor ungeprüften Zeilen wertmäßig ab (unabhängig aus rohen Stundenwerten
gerechnet, nicht aus `summarize_points()` übernommen — Lehre aus AC-S2-8/F001);
AC-S5-3 belegt den Engine-Vorrang vor Live-Ableitung; AC-S5-4 hält
`format_value()`-Dezimalstellen gegen `CV2_METRICS`-`decimals` für alle 10
betroffenen Felder einzeln synchron (Nebenbefund: `wind_chill_min/max` und
`dewpoint_avg` lesen im Klartext die `temperature`-Katalog-ID statt der
eigenen — heute folgenlos, in #1199 gebucht); AC-S5-5 charakterisiert die
Fehlzeichen-Divergenz (HTML `—` U+2014 vs. Klartext `-` U+002D) bewusst ohne
Fix (PO-Entscheidung dieser Spec: kosmetisch); AC-S5-6 verankert die 15
bereits gedeckten Zeilen gegen stillen Verlust ihrer Testabdeckung.
**Kein Produktivcode-Fix.** Adversary VERIFIED, alle 4 Pflicht-Mutationen plus
eine selbst gewählte Zusatz-Mutation exakt vom vorgesehenen Test gefangen.
Details: `docs/specs/modules/fix_1703_s5_compare_zellwerte.md`.

### Scheibe 6 — Form-Wächter über Grammatik-Klassen ✅ ERLEDIGT (2026-08-13)

Eigener Wächter über `PRIORITY`/`POSITIONAL` (`tokens/builder.py:47`, `:78`) und
`SMS_MULTI_SYMBOLS_BY_METRIC` (`sms_trip.py:180`): jede Grammatik-Klasse hat
genau eine Prioritätsstufe und eine definierte Position; kein Kürzel kollidiert
mit `HAZARD_SMS_SYMBOLS` (`hazard_symbols.py:15`).
*Risiko: niedrig–mittel. Größe: klein–mittel. Parallel zu 1–5 machbar*, weil sie
eine andere Achse als die Metrik-ID benutzt. Deckt Fläche 8 teilweise, S2, S6.

Umgesetzt als 6 ACs (AC-S6-1 bis AC-S6-6) in einer **eigenständigen** neuen
Testdatei `tests/unit/test_sms_symbol_grammar_classes.py` (nicht als Achse in
`test_channel_metric_matrix.py` — PO-Vorentscheidung §7b: „Form-Dimension als
eigene Achse, nicht in die Hauptmatrix gemischt", weil `SMS_MULTI_SYMBOLS_BY_METRIC`
1:n ist). AC-S6-1/2 sichern die bidirektionale Vollständigkeit
`PRIORITY`↔`POSITIONAL` (36 bzw. 38 Einträge, `TH:`-Doppeleintrag bewusst über
`_POSITION_SORTABLE_CATEGORIES` abgesichert); AC-S6-3/4 sichern die
Katalog-Vollständigkeit (30 eindeutige Symbole aus beiden Katalog-Registern +
6 benannte Systemzeichen = alle 36 `PRIORITY`-Schlüssel erklärt); AC-S6-5 hält
die Format-Invariante fest, dass der `!`-Block-Marker der einzige verlässliche
Diskriminator gegenüber `HAZARD_SMS_SYMBOLS` ist.

**Mitrepariert — echter, sicherheitsrelevanter Fund (AC-S6-6, einziger
Produktivcode-Fix dieser Scheibe):** Ein Wind-Datenausfall und der dedizierte
„amtliche Warnungen nicht abrufbar"-Marker renderten **bytegleich** `"W?"` —
unabhängig voneinander auslösbar, für den Leser nicht unterscheidbar (konnte
verschleiern, dass amtliche Warnungen ausgefallen waren). `UNAVAILABLE_SYMBOL`
(`tokens/builder.py`) auf `"X?"` geändert (`X` ist im gesamten
Wetter-Kürzel-Alphabet unbenutzt und dafür reserviert); zwei Bestandstests
(`test_sms_trip_unavailable_marker.py`, `test_sms_user_metric_order.py`)
mechanisch mitgezogen, `docs/reference/sms_format.md` §3.4d aktualisiert.
Adversary VERIFIED, alle 5 Pflicht-Mutationen exakt vom vorgesehenen Test
gefangen. **Bekannte, bewusst unbehobene Grenze:** eine strukturell ähnliche,
aber toter-Pfad-Kollision zwischen `TH:`/`HR:` (Hazard) und der
Météo-France-Vigilance (`_vigilance()`, nie erreicht: kein Aufrufer setzt
`provider="meteofrance"`) bleibt dokumentiert, nicht gefixt. Details:
`docs/specs/modules/fix_1703_s6_form_waechter.md`.

### Scheibe 7 — Reihenfolge-Wächter jenseits E-Mail und Telegram-rich ✅ ERLEDIGT (2026-08-14)

Deckt Fläche 5. Spec: `docs/specs/modules/fix_1703_s7_reihenfolge_matrix.md`.

🔴 **Der Zuschnitt dieser Scheibe war zweimal falsch beschrieben — beide
Korrekturen sind vor dem Schreiben der ACs gemessen worden.** Hier stand
„Reihenfolge-Zusicherung für SMS, Compare-Klartext und Compare-Telegram":

- **Die Trip-SMS war längst bewacht.** `test_channel_metric_matrix.py::test_ac15_…`
  (c) prüft die Nutzer-Reihenfolge seit #1677 paarweise über alle 26
  Katalog-Metriken; die in Fläche 5 genannte Lücke `tokens/builder.py:78` ist
  mit #1677/#1660 B geschlossen (`_POSITION_SORTABLE_CATEGORIES`,
  `MetricSpec.position`).
- **Der Compare-Klartext folgt der Reihenfolge.** Die Notiz „nutzt sie nur als
  Sichtbarkeitsfilter (#1356)" ist seit #1359 überholt (`_ordered_rows()`,
  `comparison.py:127-140`).

Was tatsächlich fehlte: die **Katalog-Deckung** (bewacht waren 4 von 25
Metriken, `tests/unit/test_compare_metric_order.py` mit zwei getippten
Reihenfolgen) und die **Kanal-Achse**, die es erst seit Scheibe 8 gibt. Damit
wiederholt sich exakt das Muster aus Scheibe 2: *das Prinzip war bewacht, die
Deckung nicht.*

**Geliefert:** neun ACs (`AC-S7-1` bis `AC-S7-9`) in
`tests/tdd/test_channel_metric_matrix.py`, 142 Testfälle, plus
`tests/helpers/compare_order.py`. Der Nachweis der Kanal-Achse hängt an der
**zugestellten Ausgabe** — drei Kanäle führen dieselbe Metrik-Menge in drei
Reihenfolgen, geprüft über Versandpfad (`send_one_compare_preset()` mit Sinks)
und Vorschaupfad, zusammen alle acht Aufrufstellen. Adversary VERIFIED; alle
fünf Pflicht-Mutationen exakt vom vorgesehenen Test gefangen, die
Kanal-Mutation an zwei unabhängigen Stellen.

**Der Produktivcode-Fix (AC-S7-6):** `build_metrics_summary_pills()`
(`email/helpers.py:1908`) kollabierte die geordnete Metrikliste zu
`set(metric_ids)` und rendert danach eine feste Katalogordnung — die im Editor
je Kanal eingestellte Reihenfolge konnte den Pillen-Überblick **strukturell
nicht erreichen**. Ein Bedienelement ohne Wirkung, also genau die Fehlerklasse
dieses Epics. Der Katalog bleibt weiße Liste (welche Größen überhaupt eine
Pille haben), gibt aber nicht mehr die Ordnung vor.

Zwei Nebenwirkungen, beide gemessen und gewollt: Der Fix wirkt auf **drei**
Ausgabeorte (Kurz-E-Mail `compact.py:176` **und** beide Teile der Voll-Mail,
`html.py:1432`/`plain.py:205`) — dabei schlug **kein** Golden- oder
Paritätstest an, die Pillen-Reihenfolge der Voll-Mail war also von nichts
bewacht. Und für Trips ohne jede gespeicherte Auswahl tauschen `visibility`
und `freezing_level` ihre Plätze, weil `DEFAULT_TRIP_METRIC_IDS` seit #1552
aus `trip_default_rank` stammt und nicht aus `_PILL_CATALOG_ORDER` — eine
Ordnungsquelle statt zweier.

**Abgelöste Entscheidung, nicht still vollzogen:** `email_metrics_summary_664.md:88`
(2026-06-08) legte ausdrücklich fest „Reihenfolge = Katalog-Reihenfolge, nicht
Eingabereihenfolge", und `test_metric_order_follows_catalog` fror das ein. Die
alte Wahl war unter ihren Bedingungen richtig — im Juni 2026 gab es keine
nutzergesetzte Reihenfolge, die Kanal-Layouts kamen erst mit #1575/#1677 (Trip)
bzw. #1335/#1359 (Compare); die „Eingabereihenfolge" war die zufällige Folge
der Config-Einträge und trug keine Absicht. Der Test heißt jetzt
`test_metric_order_follows_input`, prüft paarweise statt einseitig und trägt
den Ablösungsvermerk (#664 → abgelöst durch #1703 S7), ebenso der Docstring von
`build_metrics_summary_pills()`.

**Zuschnitt-Grenze, bewusst offen:** Ausblick (`outlook_columns()`) und
Stundenverlauf (`hourly_selectable_metric_ids()`) des Ortsvergleichs führen
weiterhin je eine einzige globale Liste ohne Kanal-Ebene (ADR-0053 Punkt 1) —
für sie gibt es keine kanalbezogene Soll-Reihenfolge, gegen die sich prüfen
ließe. Ein Wächter dafür bräuchte zuerst deren eigene Kanal-Kette.

**Weitere Grenzen:** Die Altbestands-Divergenz zwischen HTML (`CV2_METRICS`)
und Klartext (`_PLAIN_ROWS`) ab Position 3 ist charakterisiert, nicht gefixt —
die `_PLAIN_ROWS`-Ordnung ist in `test_compare_metric_order.py` AC-7 als
Altbestands-Standard eingefroren, ein Fix wäre eine eigene Entscheidung
(→ #1199). `render_telegram_bubbles()` führt zwei Ordnungsquellen
(`dc.get_enabled_metric_ids()` für die Kurzübersicht, `render_for_channel()`
für die Tabellen-Bubbles); im Versandpfad fallen sie zusammen, das Driftrisiko
ist benannt (AC-S7-7). `format_stage_summary()` hat keine Reihenfolge-Achse
(AC-S7-9).

### Scheibe 8 — Compare-Kanal-Tabs im Frontend ✅ ERLEDIGT (2026-08-13)

Den strukturellen Bruch zwischen `compareWizardState.svelte.ts`
(`wiz.activeMetricKeys`, eine globale Liste) und dem Trip-Editor
(`WeatherMetricsTab.svelte:755–771`, `channel_layouts` je Kanal) für die
**Übersichtstabelle** aufgelöst. PRs #1813 + #1819, Merge `2fd4be0b`/`21a6a1ef`.

Geliefert: kanal-eigene Metrikauswahl (E-Mail/Telegram/SMS) für
`display_config.channel_active_metrics`, die volle Kette Oberfläche →
Speicherweg → Resolver → Renderer — nicht nur die Oberfläche, das war die von
ADR-0053 verlangte Bedingung für die Entscheidungs-Umkehr gegenüber
#1287/#1291/#1351 („Attrappen"). Backend: `resolve_channel_enabled_metrics()`
(`compare_metric_ids.py:200-241`) additiv neben `resolve_enabled_metrics()`;
`CompareRenderOptions.enabled_metrics_by_channel`
(`report_config_resolver.py:206-208`) additiv neben `enabled_metrics`; acht
Aufrufstellen umgestellt (`scheduler_dispatch_service.py:439/505/509`,
`compare_preview_service.py:65/70/105/122/186`).

**Zuschnitt-Korrektur festhalten:** Stundenverlauf (`hourly_metrics`) und
Ausblick (`outlook_metrics`) bleiben **global** — eigene, getrennt
gespeicherte Auswahllisten, bewusste Schnitt-Entscheidung (ADR-0053), keine
Auslassung. Eine Folge-Scheibe müsste dieselbe Kette (Resolver, Persistenz,
Editor) dafür wiederholen.

Bauform: additiv. `CompareRenderOptions.enabled_metrics` behält seine
Bedeutung (reine globale Auflösung); `enabled_metrics_by_channel` tritt
daneben. Kein Go-Schema-Change — `DisplayConfig`
(`internal/model/compare_preset.go:48`) bleibt untypisiertes Blob,
`config_merge.go` ersetzt `channel_active_metrics` als GANZEN Top-Level-Key
(RMW-Pflicht beim Speichern, wie beim Trip).

**ADR-0053** löst die Abschaffungs-Entscheidungen aus #1287/#1291
(2026-07-18, „Attrappen") und #1351 Teil 2 (2026-07-24) ab; schreibt
ADR-0050 (Metrik-Kaskade, Regeln 1-4) unverändert für Compare fort, statt sie
zu duplizieren.

**Mitrepariert:** Die Kappungs-Aussage war an **drei** Anzeigestellen falsch
— SMS zeigte den Trip-Wert 160 statt 153, weil `LTChannelPicker` die feste
Modul-Konstante `LT_CHANNELS` iterierte statt `smsCharLimit` zu respektieren
(neue Funktion `ltChannelsFor()`, `ltChannels.ts:70`). `hasLabelColumn` ist
jetzt Pflicht-Prop ohne Default — der bisherige `context === 'vergleich'`-
Default zeigte auf den seit #1360 aufgelösten Hub-Layout-Reiter (Orte als
Spalten), nicht auf den heute einzig lebenden Compare-Fall (Metriken als
Zeilen).

Nachweis: Adversary VERIFIED nach einer Fix-Runde; Staging VERIFIED nach
einem Fix (fehlgeschlagenes Speichern wurde fälschlich als Erfolg gemeldet —
behoben in #1819).

**Ehrlich benennen:** `CompareTabs.svelte:710/737/782` (Snapshot-Kopie,
Hydration, Rollback von `channelActiveMetricKeys`) sind offline nicht
bewachbar — `.svelte`-Dateien sind unter `node:test` (ADR-0020) nicht
importierbar, kein DOM im Projekt. Einziger Wächter sind die Klickpfade
gegen Staging: `frontend/e2e/compare-uebersicht-kanal-bedienung.staging.spec.ts`,
`frontend/e2e/compare-uebersicht-kanal-persistenz.staging.spec.ts`.

Details, alle 15 ACs (AC-S8-1 bis AC-S8-15), Mutations-Gegenproben:
`docs/specs/modules/feat_1703_s8_compare_kanal_tabs.md`.

**Abhängigkeitsbild (Stand 2026-08-14):** **alle acht Scheiben ✅ erledigt.**
Die Flächen 1–7 aus Abschnitt 4 tragen damit jeweils einen Wächter in
`tests/tdd/test_channel_metric_matrix.py` (Achsen `AC-S1-*` bis `AC-S7-*`);
Fläche 5 ist mit Scheibe 7 als letzte geschlossen worden.

**Offen bleiben bewusst** — beides braucht eine eigene Entscheidung, keine
Fortsetzung dieses Epics: (a) Ausblick und Stundenverlauf des Ortsvergleichs
haben weiterhin keine Kanal-Ebene (ADR-0053 Punkt 1), also auch keine
kanalbezogene Soll-Reihenfolge; (b) die Flächen 8, 9 und 10 aus Abschnitt 4.2
(Einheiten/Nachkommastellen je Kanal · Frontend ohne Metrik×Kanal-Matrix ·
Trip-SMS liest die Kaskade nicht) standen nie im Zuschnitt der acht Scheiben.

## 7. PO-Entscheidungsvorlage — ENTSCHIEDEN (PO, 2026-08-10)

Alle drei Fragen sind vom PO entschieden (Issue #1514). Die ursprüngliche
Abwägung bleibt zur Nachvollziehbarkeit stehen.

- [x] PO-Entscheidung (a) **Compare-Kanal-Tabs: JA.** Der Compare-Editor bekommt
      Kanal-Layouts wie der Trip-Editor (Scheibe 8 ist damit beauftragt,
      Scheibe 7 deckt Trip UND Compare).
      🔴 **Präzisierung nach Lieferung von Scheibe 8 (2026-08-13):** „Scheibe 7
      deckt Trip UND Compare" ist zu großzügig formuliert. Scheibe 8 hat die
      Kanal-Ebene **nur für die Compare-Übersichtstabelle** geliefert; Ausblick
      und Stundenverlauf führen weiterhin je eine einzige globale Liste. Scheibe 7
      kann für Compare daher vorerst **nur die Übersicht** abdecken. Wer diesen
      Satz ohne die Präzisierung liest, schneidet Scheibe 7 zu breit zu.
      Ursprüngliche Abwägung: Heute führt der
      Compare-Editor eine globale Metrik-Liste (`wiz.activeMetricKeys`), der
      Trip-Editor Layouts je Kanal (`channel_layouts`) — der Umbau stellt die
      Trip/Compare-Teilungsvorgabe auch hier her.

- [x] PO-Entscheidung (b) **Form-Dimension als eigene Achse: JA** (Empfehlung
      bestätigt). Form (Aggregation, `format_mode`, Symbol-Grammatik) wird
      separat geführt (Scheibe 6), nicht in die Hauptmatrix gemischt, weil
      `SMS_MULTI_SYMBOLS_BY_METRIC` (S6) 1:n ist.

- [x] PO-Entscheidung (c) **Folge-Scheiben als EPIC gebündelt: Epic #1703.**
      Acht Scheiben mit Abhängigkeiten (3 vor 1/2/4/5; 8 vor 7; 6 parallel)
      laufen unter Epic #1703, das die Reihenfolge sichtbar hält.

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
