<!-- Kontext-Dokument zu Issue #1719 Scheibe S2 (Backend-Verfeinerung).
     Erhoben 2026-08-11 auf Basis-Commit 32b781ed (Merge PR #1735 = S1).
     S1 (ADR-0050 + Pruefstand) ist geliefert; S3 (Frontend) und S4 (Legende)
     sind spaetere Scheiben. -->

# Context: Metrik-Kaskade — die Kanal-Ebene schneidet die Grundauswahl, statt sie zu ersetzen (#1719 Scheibe S2)

## Request Summary

`UnifiedWeatherDisplayConfig.get_metrics_for_channel()` waehlt heute **eine**
Kaskadenebene aus und gibt sie **vollstaendig** zurueck; eine Kanal-Ebene
ersetzt damit die Grundauswahl komplett und kann eine global abgewaehlte
Metrik wieder scharfschalten. ADR-0050 legt das Gegenteil fest: die
Grundauswahl ist das Maximum, ein Kanal darf nur abwaehlen. S2 baut den
Lesepfad auf diese Verfeinerungs-Semantik um, sodass der in S1 gebaute
Pruefstand-Test AC-7 (`xfail(strict=True)`) gruen wird und seine Markierung
entfaellt.

## Related Files

| Datei | Relevanz |
|---|---|
| `src/app/models.py:825-863` | **Der Wirkort.** `get_metrics_for_channel()` — dreistufige Auswahl (per_report > per_channel > global), jede Stufe gibt ihre Liste ungeschnitten zurueck |
| `src/app/models.py:670-703` | `_filter_metrics_by_report_type()` — gemeinsamer Filter fuer morning/evening-Flags + `selectable`-Gate (#1585). Definiert, was „global aktiv fuer diesen Report-Typ" heisst |
| `src/app/models.py:712-734` | `_cascade_source_for_channel()` — geteilte Ebenen-Erkennung, genutzt von `get_metrics_for_channel()` UND `cascade_source_for_channel()`. Seit #1677 DEC-2 gibt es keine zweite Kopie der drei if-Zweige |
| `src/output/renderers/trip_report.py:126-139` | **Die Falle.** `dataclasses.replace(dc, metrics=active_metrics)` ersetzt die Grundauswahl durch die E-Mail-Auswahl (und zwingt alles auf `enabled=True`). Ab hier „luegt" `dc` ueber die eigene Grundauswahl |
| `src/output/renderers/trip_report.py:132, 295, 301` | `_dc_uncollapsed` — die in #1575 eingefuehrte Absicherung, damit SMS die Kollabierung nicht mitbekommt. Vorbild fuer das, was Telegram fehlt |
| `src/output/renderers/trip_report.py:256-276` | Uebergibt `dc=dc` (die **kollabierte** Instanz) an `render_telegram_bubbles` |
| `src/output/renderers/narrow.py:661` | `render_for_channel("telegram", dc, report_type)` — laeuft damit auf der kollabierten `dc` |
| `src/output/renderers/channel_layout.py:86-90` | `render_for_channel()` — einziger Telegram-Tabellen-Einstieg in die Kaskade, erbt jede Aenderung automatisch |
| `api/routers/validator.py:141-159, 292` | Validator-Endpoint `/api/_validator/metrics-for-channel`; delegiert an die echten Methoden, erbt automatisch |
| `src/app/loader.py:758` | `data.get("metrics") or []` — eine fehlende globale Liste wird zu `[]`, nicht katalog-aufgefuellt |
| `src/app/loader.py:836-871` | Parse-Zweig `channel_layouts` — erzeugt `per_channel_layouts`; fehlt der Schluessel, bleibt `None` (Rueckfall auf global) |
| `tests/tdd/test_channel_metric_matrix.py:820-846` | **AC-7**, `xfail(strict=True)`, Ziel `dewpoint` (global AUS, SMS-Ebene AN). Wird S2 gruen, meldet `strict` die abgelaufene Ausnahme selbst |
| `tests/fixtures/metric_cascade/khw_display_config_widerspruch.json` | Anonymisierte Fixture: 26 globale Metriken, `channel_layouts.sms` mit 26 Eintraegen, davon `wind_chill`/`cape` abgewaehlt. Enthaelt **keinen** hinzufuegenden Fall — AC-7 konstruiert ihn |
| `docs/adr/0050-metrik-kaskade-verfeinerung-nicht-ersetzung.md` | Die Zusage, gegen die S2 gebaut wird |

## Gemessene Befunde (2026-08-11)

### 1. Bestandsdaten: der verbotene Zustand kommt in Produktion nicht vor

Datenwurzel ist ausschliesslich `/var/lib/gregor` (`GZ_DATA_DIR` der
Produktions-Units; `loader.py:1084-1101` bestaetigt die Aufloesung). Trip-
Konfiguration liegt unter `users/<uid>/briefings/<id>.json`; der frueher
genutzte `trips/`-Ordner ist dort bereits als tot umbenannt.

| Pruefung | Ergebnis |
|---|---|
| `display_config`-Traeger insgesamt (4 Nutzer) | 16 |
| davon mit non-leerem `channel_layouts` | 2 |
| mit `channel_layouts_per_report` | 0 |
| **verbotener Widerspruch** (global `false` + Kanal `true`) | **0** |
| erlaubte Gegenrichtung (global `true` + Kanal `false`) | sms 2, telegram 1 |

**Folge:** Die im Issue-Text vorgesehene einmalige Zusammenfuehrung von
Bestandstrips hat kein Migrationsvolumen. Ein Schnitt im Lesepfad genuegt.
Der Verzicht ist damit gemessen begruendet, nicht angenommen.

**Sonderfall ohne Handlungsbedarf:** Compare-Preset `cp-eb6ba0b239d90e37`
traegt `channel_layouts` (je 24 Metriken) **ohne** globale `metrics`-Liste —
aelteres Schema mit `active_metrics`. Da der Ortsvergleich die Kaskade gar
nicht benutzt (s. Befund 3), ist diese Datenlage inert. Der Fall bleibt
trotzdem als Regel relevant (s. Befund 4).

### 2. Der Telegram-Pfad laeuft auf einer kollabierten Grundauswahl

`trip_report.py:138` ersetzt `dc.metrics` durch die aufgeloeste **E-Mail**-
Auswahl. `trip_report.py:259` reicht genau diese Instanz an
`render_telegram_bubbles` weiter, das bei `narrow.py:661`
`render_for_channel("telegram", dc, report_type)` aufruft. Die Dicts
`per_channel_layouts`/`per_report_layouts` ueberleben `dataclasses.replace`
unveraendert — nur `metrics` ist ersetzt.

Heute faellt das nicht auf: der `per_channel`-Zweig liest `self.metrics`
ueberhaupt nicht. **Sobald S2 gegen `self.metrics` schneidet, schneidet
Telegram gegen die E-Mail-Auswahl** (`Telegram ∩ E-Mail`). Eine Metrik, die
fuer Telegram gewaehlt und fuer E-Mail abgewaehlt ist, verschwaende still —
aus dem Bugfix wuerde ein neuer Bug derselben Familie.

Fuer SMS ist diese Falle in #1575 bereits getreten und mit `_dc_uncollapsed`
(`trip_report.py:132`) umschifft worden. Telegram hat diese Absicherung nicht.

### 3. Nicht betroffene Pfade (Scope-Einsparung, gemessen)

- **Ortsvergleich:** `comparison.py:647-670` (`_channel_layout_for_metrics`)
  baut eine Wegwerf-`UnifiedWeatherDisplayConfig` **ohne** Kanal-Ebenen —
  `_cascade_source_for_channel()` liefert dort immer `"global"`. Compare-
  Channel-Layouts wurden mit #1351 entfernt
  (`scripts/migrate_1351_drop_compare_channel_layouts.py`). ADR-0050 beruehrt
  den Compare-Pfad nicht.
- **Premium-SMS:** `premium_sms.py:19-21` sendet `report.sms_text`
  unveraendert — kein eigener Renderpfad, keine eigene Kanal-Ebene noetig.
  Damit ist die offene Frage der S1-Spec („bekommt Premium-SMS eine eigene
  Ebene?") fuer S2 beantwortet: nein, es erbt die SMS-Kaskade transitiv.
- **Alarme:** `src/output/renderers/alert/*` kennt die Kaskade nicht (0
  Treffer); Alarm-Auswahl laeuft ueber `metric_alert_levels` /
  `get_alert_enabled_metrics()` — eine andere Auswahlachse.
- **Go:** `channel_layouts` wird in `internal/handler/compare_preset.go:333`
  und `internal/model/compare_preset.go:46` nur als opaker JSON-Schluessel
  durchgereicht, ohne Interpretation. `internal/handler/proxy.go:370` ist
  reiner HTTP-Forward. Keine Go-Aenderung noetig.
- **Frontend:** keine Stelle ruft `/api/_validator/metrics-for-channel` auf;
  `channelLayoutsDirty.ts:41` vergleicht nur Roh-Arrays. Es gibt heute keine
  Live-Vorschau der aufgeloesten Kaskade im Editor — Frontend ist S3.

### 3b. Schreibpfad — falls doch eine Migration beschlossen wird

- **Go schreibt `display_config` an zwei Stellen:**
  `internal/handler/weather_config.go:99` (`PutTripWeatherConfigHandler`) und
  `internal/handler/trip.go:305-306` (`UpdateTripHandler`), beide via
  `mergeConfigMap` (`internal/handler/config_merge.go:11-22`). Das ist ein
  **flacher Merge auf oberster Schluesselebene**: wird `channel_layouts`
  gesendet, wird der ganze Teilbaum ersetzt, nicht pro Kanal gemergt. Das
  Frontend gleicht das aktiv aus (`WeatherMetricsTab.svelte:754-775` →
  `channelMetricLayouts.ts:25-34`, Docstring nennt BUG-DATALOSS-GR221).
- **Python `save_trip()`** (`loader.py:1657-1723`) macht RMW ueber
  `_deep_merge_preserve_unknown` (Z.125-137): Dicts rekursiv, **Listen
  komplett ersetzt**. `metrics` und `channel_layouts.<kanal>` sind Listen —
  ein Python-Schreibvorgang ueberschreibt sie also vollstaendig mit dem
  In-Memory-Stand. Aufrufer: `trip_command_processor.py` (Inbound-Kommandos),
  `trip_report_scheduler.py:646`.
- **Praezedenzfall „Lazy-Migration beim Speichern":**
  `internal/store/trip.go:235` ruft `migrateMetricAlertLevels()` (Z.283-305)
  nur im Save-Pfad. Zeigt, dass es dafuer ein etabliertes Muster gibt, falls
  eine physische Bereinigung doch gewuenscht wird.
- **Migrations-Skript-Muster** (13 Stueck unter `scripts/migrate_*.py`,
  Ausfuehrung dokumentiert in `docs/reference/operations_playbook.md:341-380`):
  Dry-Run-Default, `--execute`, `--backup-dir`, zweiphasig
  `_collect_plan()`/`_apply()`, Idempotenz-Pflicht. Naechster Verwandter:
  `scripts/migrate_1262_flat_metrics.py` (dieselbe Baustelle
  `display_config.metrics`).
- **Compare hat keine `channel_layouts` mehr** — mit #1351 ersatzlos
  entfernt; das Migrationsskript nennt ausdruecklich, dass Trip-Presets
  (`kind=route`) unangetastet bleiben, weil `channel_layouts` dort eine echte
  Kaskadenstufe ist. S2 ist damit **Trip-only**.
- **`channel_layouts_per_report` hat keine Frontend-Schreibstelle** — nur
  Lesevorkommen (`types.ts:291`) und ein Dirty-Check
  (`cockpitHelpers568.ts:58`). Die dritte Kaskadenstufe wird heute von
  keinem Bedienelement erzeugt.

### 4. Vorbestehende Kaskaden-Umgehungen (nicht S2-Scope, aber zu benennen)

- `narrow.py:735/741/776` — die Telegram-**Kurzuebersicht** und die
  Tagesfusszeile lesen `dc.get_enabled_metric_ids()` statt der Kanal-Kaskade
  und damit (wegen Befund 2) die E-Mail-Auswahl. Der Docstring bei
  `narrow.py:648` beschreibt das als beabsichtigt („alle konfigurierten
  Metriken, `telegram_kurzform` wirkungslos — AC-10"). Aendert sich durch S2
  nicht von selbst.
- `validator.py:115,134` — `get_enabled_metrics()` bewusst global, andere
  Fragestellung (Erkennung, ob ueberhaupt eine `display_config` gesetzt ist).

## Existing Patterns

- **Ein Ableitungsweg je Frage (#1677 DEC-2):** Ebenen-Erkennung liegt
  ausschliesslich in `_cascade_source_for_channel()`; `models.py` und
  `api/routers/validator.py` teilen sie. Ein S2-Schnitt gehoert nach
  demselben Muster an genau **eine** Stelle, nicht in jeden Renderer.
- **Kollabierungs-Schutz per unverfaelschter Kopie:** `_dc_uncollapsed`
  (`trip_report.py:132`) ist das etablierte Muster, wenn ein Kanal nach der
  E-Mail-Kollabierung noch die echte Grundauswahl braucht.
- **Altbestand ist ein eigenes Signal, keine leere Liste:**
  `_trip_metrics_altbestand` (`trip_report.py:128`) unterscheidet „Feld fehlt"
  von „alles bewusst abgewaehlt" und wird an alle drei E-Mail-Renderer
  durchgereicht (`html.py:984`, `compact.py:114`, `plain.py:127`).
- **Zentraler Choke-Point fuer Katalog-Regeln:**
  `_filter_metrics_by_report_type()` traegt bereits das `selectable`-Gate
  (#1585) — der natuerliche Ort, an dem auch das globale Maximum wirken kann.

## Dependencies

- **Upstream:** `src/app/loader.py` (`_parse_display_config`) liefert
  `metrics`, `per_channel_layouts`, `per_report_layouts`;
  `src/app/metric_catalog.py` liefert `selectable`.
- **Downstream:** E-Mail (`trip_report.py:135` → `html.py`/`compact.py`/
  `plain.py`/`compact_summary.py`), SMS (`trip_report.py:295` →
  `sms_trip.py`), Premium-SMS (transitiv), Telegram-Tabellen
  (`narrow.py:661` → `channel_layout.py:90`), Validator-Endpoint
  (`validator.py:292`) und ueber ihn der Go-Proxy.

## Existing Specs

- `docs/adr/0050-metrik-kaskade-verfeinerung-nicht-ersetzung.md` — die Zusage
  (Regeln 1-5); Regel 4 ist Frontend/S3.
- `docs/specs/modules/fix_1719_s1_kaskade_pruefstand.md` — Pruefstand, AC-7
  als `xfail(strict=True)`, offene Fragen die S2 beantworten muss.
- `docs/reference/metric_output_matrix.md` (#1514) — Ausgabeorte je Metrik.
- ADR-0049 (Kanalliste E-Mail · Telegram · SMS · Premium-SMS).

## Risks & Considerations

1. **Der Schnitt gegen eine kollabierte `dc`** (Befund 2) ist das groesste
   Risiko: er verwandelt den Fix in einen neuen Bug derselben Familie und
   waere gruen, wenn der Test nur SMS und E-Mail prueft. Ein Telegram-AC mit
   einer Metrik, die in Telegram AN und in E-Mail AUS ist, ist Pflicht.
2. **Leere/fehlende Grundauswahl darf nicht „alles verboten" heissen.**
   `loader.py:758` macht aus einem fehlenden `metrics`-Feld `[]`. Ein
   Maximum-Filter, der `[]` als „nichts erlaubt" liest, wuerde Altbestands-
   Trips (und den Compare-Sonderfall aus Befund 1) auf null Metriken
   schneiden — Totalausfall statt Bugfix. Regel muss lauten: **keine globale
   Ebene ⇒ kein Maximum definiert ⇒ nicht schneiden.**
3. **Report-Typ-Flags im Schnitt.** Das Maximum ist report-typ-abhaengig
   (`morning_enabled`/`evening_enabled`). Ein Kanal-Eintrag mit
   `evening_enabled=True`, dessen globaler Eintrag `evening_enabled=False`
   traegt, fuegt fuer diesen Report-Typ hinzu — muss also ebenfalls fallen.
4. **Reihenfolge und Format bleiben kanal-eigen** (ADR-0050 Regel 5). Der
   Schnitt darf nur Eintraege ENTFERNEN, nie die Position oder
   `format_mode`/`use_friendly_format` des Kanal-Eintrags veraendern.
5. **Stufe 1 (`per_report_layouts`) muss mitgeschnitten werden**, sonst
   verlagert sich das Schlupfloch nur eine Ebene nach oben. Heute im Bestand
   ungenutzt (0 Traeger) — genau deshalb billig jetzt, teuer spaeter.
6. **Metrik im Kanal, die global gar nicht vorkommt:** unter Regel 1 nicht
   im Maximum ⇒ faellt. Im Bestand nur im inerten Compare-Sonderfall
   vorhanden; muss dennoch bewusst entschieden und getestet werden.
7. **`xfail(strict=True)` entfernen ist Teil der Definition of Done** —
   sonst schlaegt AC-7 als XPASS fehl und die CI-Ampel kippt.
8. **Doku-Drift:** Der Docstring bei `models.py:826-841` beschreibt die
   Ersetzungs-Semantik; ebenso `loader.py:836-841`. Beide behaupten nach dem
   Umbau etwas Falsches ueber den eigenen Code.

## Analysis

### Type

Bug (ADR-0050 ist die Zusage; der Code haelt sie nicht ein).

### Zwei Korrekturen an den Befunden oben (Adversary-Runde der Analyse)

**K1 — „0 Widerspruechen im Bestand" ist eine Momentaufnahme, keine
Invariante.** Der bereits ausgelieferte Editor erzeugt den verbotenen
Zustand jederzeit neu, ohne S3: `editActiveChannel()`
(`WeatherMetricsTab.svelte:638`) legt beim ERSTEN Anfassen eines Kanal-Tabs
eine Kopie der globalen Auswahl an (`channelMetricLayouts.ts:67-79`,
`startChannelOverride`); danach lebt sie unabhaengig weiter, und
`onToggleMetric` (Z.662-673) aendert ausschliesslich die globale Ebene.
`buildWeatherPayload()` (Z.754-775) sendet beide Ebenen unabgeglichen in
EINEM PATCH; `config_merge.go:11-22` validiert nichts quer.
**Reproduktionsfolge, die jeder Nutzer heute ausloesen kann:** SMS-Tab
oeffnen → zurueck zur Grundauswahl → dort eine Metrik abwaehlen → speichern.
Konsequenz: Der Schnitt muss **jeden Aufruf** schuetzen; eine Einmal-
Migration wuerde den Zustand nur bis zum naechsten Speichern aufraeumen.
Das ist das staerkere Argument gegen die Migration als die Zaehlung selbst.

**K2 — Telegram folgt schon HEUTE der E-Mail-Auswahl, nicht erst nach S2.**
Hat ein Trip eine eigene `channel_layouts.email`-Ebene und **keine**
Telegram-Ebene, faellt `get_metrics_for_channel("telegram", …)` auf Stufe 3
und liest `self.metrics` — das ist zu diesem Zeitpunkt die kollabierte
E-Mail-Auswahl (`trip_report.py:138`). Das ist ein **bereits scharfer
Fehler**, kein blosses Risiko des Umbaus. S2 behebt ihn mit.

### Verworfen: `seg_tables` global verbreitern

Der Vorschlag, die Stundenzeilen einmal aus dem vollen Maximum zu bauen,
weil die E-Mail ihre Spalten ohnehin aus `dc.metrics` ziehe, ist **am Code
widerlegt**: `html.py:673` und `html.py:903` leiten die Spalten ueber
`visible_cols(rows)` aus den **Zeilen-Schluesseln** ab
(`email/helpers.py:296-299`). Gefiltert wird nur ueber `allowed_col_keys`,
und `_allowed_col_keys_for_horizon()` (`html.py:924-947`) liefert bei
`horizon=None` ausdruecklich `None` — `horizon` ist `None` fuer **alle
Etappen ab Tag 4** (`helpers.py:318-322`). Breitere Zeilen haetten dort neue
Spalten in die Trip-Mail geschoben. Stattdessen bekommt Telegram eine
**eigene** Zeilenmenge; der E-Mail-Pfad bleibt unberuehrt.

### Technical Approach (Entscheidungen)

- **D1 — Ort des Schnitts:** in `get_metrics_for_channel()`
  (`models.py:825-863`), **nicht** im geteilten
  `_filter_metrics_by_report_type()`. Letzteres wird mit drei verschiedenen
  Listen aufgerufen, darunter `self.metrics` selbst; ein Maximum-Parameter
  waere an zwei von drei Aufrufstellen unbenutzt und vermischte zwei
  Zustaendigkeiten.
- **D2 — Schnittmenge:** gegen die **IDs** aus
  `self.get_metrics_for_report_type(report_type)`, nicht gegen rohe
  `enabled`-Flags. Nur so wirkt ADR-0050 Regel 3 auch fuer
  `morning_enabled`/`evening_enabled`, und die abgeleiteten Nachtgroessen
  (`temperature_night`/`wind_chill_night`, `loader.py:803-834`) sowie das
  `selectable`-Gate (#1585) bleiben korrekt beruecksichtigt.
- **D3 — beide Kanal-Ebenen gegen dieselbe globale Menge**, NICHT verkettet:
  `per_report_layouts[rt][ch]` wird gegen die globale Menge geschnitten, nicht
  zusaetzlich gegen `per_channel_layouts[ch]`. ADR-0050 Regel 1 nennt
  ausdruecklich die Grundauswahl als Maximum, keine Zwischenebene; eine
  Verkettung wuerde einen Report-Typ-Override auf das einschraenken, was der
  allgemeine Kanal-Layer zufaellig enthaelt.
- **D4 — leere Grundauswahl:** `if not self.metrics: nicht schneiden`. Die
  Pruefung sitzt direkt an der Schnittstelle (Pruefort = Wirkort), nicht als
  Wiederverwendung von `_trip_metrics_altbestand` (`trip_report.py:128`) aus
  einer anderen Datei.
- **D5 — Telegram:** `trip_report.py` uebergibt `dc=_dc_uncollapsed` an
  `render_telegram_bubbles` UND baut fuer Telegram eine eigene Zeilenmenge
  aus derselben unverfaelschten Grundauswahl. Ohne die zweite Haelfte
  erschienen Spalten ohne Werte („–"), weil `_dp_to_row()`
  (`trip_report.py:636-638`) nur Metriken eintraegt, die in der uebergebenen
  `dc` aktiv sind.
- **D6 — keine Datenmigration.** Begruendung: kein Bestandsfall (gemessen)
  UND der Editor erzeugt den Zustand laufend neu (K1) — eine Einmal-
  Migration loeste das Problem nicht dauerhaft, der Lesepfad-Schnitt schon.
  Das entspricht dem in ADR-0050 bereits benannten Preis „stiller Rueckfall
  auf AUS fuer Alt-Konfigurationen".
- **D7 — Premium-SMS** bekommt keine eigene Ebene (erbt `report.sms_text`,
  `notification_service.py:412/428/449`); **Compare** bleibt unberuehrt
  (`compare_preset_from_dict` ruft `_parse_display_config()` gar nicht auf,
  `loader.py:238-289`).

### Affected Files

| Datei | Aenderung | Beschreibung |
|---|---|---|
| `src/app/models.py` | MODIFY | Maximum-Schnitt in `get_metrics_for_channel()` + Docstring-Korrektur |
| `src/output/renderers/trip_report.py` | MODIFY | `_dc_uncollapsed` an Telegram + eigene Telegram-Zeilenmenge |
| `src/app/loader.py` | MODIFY | nur Docstring-Korrektur (Z.836-841 behauptet Ersetzung) |
| `tests/tdd/test_channel_metric_matrix.py` | MODIFY | `xfail(strict)` entfernen + neue ACs (Telegram-Wert, per_report, leere Grundauswahl) |
| `tests/tdd/test_issue_429_channel_layouts.py` | MODIFY | 2 Fixtures: Kanal-Metriken global ergaenzen |
| `tests/tdd/test_issue_434_per_report_layouts.py` | MODIFY | 1 Fixture |
| `tests/integration/test_issue_448_validator_metrics_for_channel.py` | MODIFY | 2 Fixtures |

### Scope Assessment

- Dateien: 7 (3 Produktivcode, 4 Tests)
- Geschaetzte LoC: ~+110 / -25 (Limit 250)
- Risiko: **MEDIUM-HIGH** — Produktivpfad aller vier Kanaele; das Risiko
  liegt nicht im Schnitt selbst, sondern in seinen Wechselwirkungen mit der
  E-Mail-Kollabierung.

### Bekannt rot werdende Bestandstests (mechanisch zu reparieren)

`test_issue_429_channel_layouts.py::test_ac3_…` (Z.189-203) und
`::test_ac5_…` (Z.224-238), `test_issue_434_per_report_layouts.py::test_ac3_…`
(Z.170-183), `test_issue_448_validator_metrics_for_channel.py::test_ac2_…`
(Z.232-247) und `::test_ac3_…` (Z.249-264). Alle fuenf haben Kanal-Metriken,
die in der globalen Liste **nicht** vorkommen — genau das von ADR-0050
verbotene Muster. Reparatur = globale Liste um diese IDs ergaenzen.

### Open Questions

- Keine blockierenden. Bewusst **ausserhalb** S2: die Telegram-
  Kurzuebersicht (`narrow.py:735/741/776`) umgeht die Kaskade und liest
  `get_enabled_metric_ids()` direkt — sie bleibt an die E-Mail-Kollabierung
  gekoppelt. Durch S2 wird das nicht schlimmer (Adversary Angriff 5).
- Die Wurzel — dass `dataclasses.replace(dc, metrics=…)` die `dc` ueber ihre
  eigene Grundauswahl luegen laesst — bleibt bestehen; sie sauber
  aufzuloesen hiesse, drei E-Mail-Renderer von `dc.metrics` zu entkoppeln.
  Als Folgearbeit notieren, nicht in S2.
