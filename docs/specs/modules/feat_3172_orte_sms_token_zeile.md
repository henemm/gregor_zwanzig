---
entity_id: feat_3172_orte_sms_token_zeile
type: feature
created: 2026-11-19
updated: 2026-11-19
status: approved
version: "1.0"
workflow: feat-3172-orte-sms-token-zeile
tags: [orte, sms, premium-sms, telegram, kurzstil, token-zeile, kanal-paritaet]
---

# Orte-SMS und Orte-Kurzstil in der Token-Schreibweise der Trip-SMS (Issue #3172)

## Approval

- [x] Approved — PO-Vorgabe 2026-11-19 im Issue #3172 (wörtlich: „Also so in der Richtung sollte es aussehen … `E3: N12 D17 R- PR53%@13 W21@13 G26@10(31@13) TH:- TH+:-` … Und ich will das NICHT im Detail diskutieren weil es bereits abschließend definiert war.“). Der Fachinhalt ist die bestehende Token-Zeile aus `docs/reference/sms_format.md` §2–§6; die offenen Punkte 1–3 des Issues sind dort ausdrücklich als Tech-Lead-Entscheidungen ausgewiesen und hier nach der Trip-Definition entschieden (ADR-0125).

## Purpose

Die Orte-SMS geht heute in einer eigenen, ausgeschriebenen Zellform heraus (`Aabenraa FL -5C FD -0C W 13 km/h WD 33 +12 ?1`), obwohl `sms_format.md` die kompakte Token-Zeile als einzige Schreibweise für alle Kanäle festlegt. Nach dieser Spec schreibt die Orte-SMS – und damit Premium-SMS und Telegram-Kurzstil der Orte, die denselben Text senden – je Ort die Token-Zeile der Trip-SMS, die Orte durchgezählt wie Etappen (`O1 D-5/0 W13@9 G26@10(31@13) R- PR53%@13 TH:- O2 …`), gebaut über denselben Token-Baukasten.

**PO-Nachtrag 2026-11-19:** „Die Orte dürfen in der SMS NICHT ausgeschrieben werden. Sie müssen durch gezählt werden. Es gibt nur 160 Zeichen … O1: xxx O2: xxxx muss reichen.“ Damit entfallen Ortsnamen in der SMS ganz. Weitere PO-Auswahl gleichen Tags („Jedes Zeichen ist kostbar!!!“): **kein Kopf** (`Orte TT.MM.:` entfällt, wie die Trip-SMS mit `E3` beginnt die Orte-SMS mit `O1`), **kein Doppelpunkt** nach `O1` und **kein Strichpunkt** zwischen Orten; Grenze **160** Zeichen wie die Trip-SMS. Der Doppelpunkt der Trip-SMS (`E3:`) fällt im Folge-Ticket #3174.

## Source

- **File:** `src/output/renderers/orte_sms.py` (NEU), `src/output/renderers/comparison.py`, `src/services/compare_briefing_aufbau.py`, `src/services/placements_view_service.py`
- **Identifier:** `render_compare_sms`, `_sms_location_variants`, `_sms_fit_locations` (comparison.py); NEU `orte_token_formen` (orte_sms.py)

> **Schicht-Hinweis:** Python-Core. Kein Go-Code. Frontend nur die E2E-Spec der Karte (`frontend/e2e/was-steht-wo-karte.spec.ts`, WS-8 erwartet heute ` W \d+ km/h`). `src/output/renderers/sms_trip.py` und `src/output/tokens/*` bleiben **unverändert** (Trip-SMS zeichengleich; `sms_trip.py` liegt zudem unter dem Renderer-Mail-Gate). Wiederverwendet werden deren öffentliche bzw. modulweite Helfer per Import.

## Scope

Nur die Orte-Kurznachricht (SMS, Premium-SMS, Telegram-Kurzstil der Orte). Mail, Telegram-Normalstil, Alarme und die Trip-SMS bleiben unverändert.

## Estimated Scope

- **LoC:** ca. +280 / −180 Produktionscode, dazu Testanpassungen
- **Files:** ca. 6 Produktionsdateien, ca. 25 Testdateien (alte Zellform in Erwartungen), 5 Doku-Dateien
- **Effort:** high

### Affected Files

| File | Change Type | Description |
|------|-------------|-------------|
| `src/output/renderers/orte_sms.py` | CREATE | Je Ort `NormalizedForecast` aus `LocationResult` bilden, `MetricSpec`-Liste aus der SMS-Spalte, Formen der Token-Zeile von „alle Listenzeilen“ bis „keine“ |
| `src/output/renderers/comparison.py` | MODIFY | `_sms_location_variants` liefert Token-Formen; `_sms_fit_locations` gleiche Zeilenzahl je Ort; `render_compare_sms(…, ampel=…)`; `+N`/`?N` entfallen; `_sms_metric_cell` entfällt für die SMS |
| `src/services/compare_briefing_aufbau.py` | MODIFY | `ampel=resolve_ampel(preset)` an `render_compare_sms` |
| `src/services/placements_view_service.py` | MODIFY | Karte „Was steht wo“: SMS-Beispielwerte und „passt nicht mehr“ aus den Token-Formen, Rest-Zähler entfällt |
| `frontend/e2e/was-steht-wo-karte.spec.ts` | MODIFY | WS-8 erwartet Token statt ` W \d+ km/h` |
| `docs/reference/sms_format.md` | MODIFY | §5b neu (Token-Zeile auch für Orte), §6 Orts-Überlauf, Versionseintrag |
| `docs/reference/telegram_format.md`, `premium_sms_format.md` | MODIFY | Kurzstil/Premium der Orte = Token-Zeile |
| `docs/specs/modules/compare_kanal_metriken.md` | MODIFY | Hinweis „§3 Zellform abgelöst durch ADR-0125“ |
| `docs/adr/0125-…`, `docs/adr/README.md` | CREATE/MODIFY | Entscheidung |

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `output/tokens/builder.py::build_token_line` | module | Einzige Token-Grammatik (Trip und Orte) |
| `output/tokens/render.py::_fuse`, `_drop_last_list_row` | module | Warnblock-Fusion `!`, Kürzung ganzer Listenzeilen vom Ende |
| `output/renderers/sms_trip.py` | module | `_dominant_wind_sector`, `_dominant_precip_type_code`, `sms_format_fields` (nur Import) |
| `app/metric_catalog.py` | module | `SMS_SYMBOL_BY_METRIC`, `SMS_MULTI_SYMBOLS_BY_METRIC` |
| `output/renderers/email/compare_html.py::_metric_value`, `_daily_summary` | module | Tageswerte der Mail (Parität SMS ↔ Mail) |
| `app/ampel.py::resolve_ampel` | module | Hervorhebung `@h` nach der Abo-Ampel |
| ADR-0124, ADR-0125, `sms_format.md` | doc | Fachliche Grundlage |

## Implementation Details

1. **Forecast je Ort (`orte_sms.py`).** Aus `LocationResult.hourly_data` (Stundenwerte des Tagesfensters, Ortszeit über `resolve_location_tz`) eine `NormalizedForecast(days=(today,))` bilden, Feld für Feld wie `sms_trip._segments_to_normalized_forecast` (Stundenproben nur `> 0` für R/PR/W/G/TH/HU/DP/CT/CL/CM/CH/UV; Tiefstwert-Proben ohne Filter für VS/FZ; je Stunde Höchst- bzw. Tiefstwert). Tageswerte, die die Orte-Mail als Zahl zeigt (`L`, `D`, `FL`, `FD`, `SU`, `HP`, `SD`, `NS24+`, `SL`), kommen aus `_metric_value(loc, renderer_id, summary)` (dieselbe Quelle wie die Mail); die Stunde von Tiefst-/Höchstwert für `@h` aus `hourly_data`. `WD:` = vorherrschende Himmelsrichtung (`_dominant_wind_sector`), `PT:` = vorherrschende Niederschlagsart (`_dominant_precip_type_code`). Amtliche Warnungen: `official_alerts_to_sms_entries(loc.official_alerts, tz, min_level=…("LOW"))` wie heute. `official_alerts_unavailable` bleibt beim Ort **aus** der Zeile (Orte führen ` X?` einmal am Nachrichtenende, wie bisher).
2. **Specs aus der SMS-Spalte.** Für jede Katalog-Metrik mit SMS-Symbol (`SMS_SYMBOL_BY_METRIC`, `SMS_MULTI_SYMBOLS_BY_METRIC`) eine `MetricSpec(symbol, enabled=<in der SMS-Liste>, position=<Listenindex>, **sms_format_fields(...)>)`; Renderer-IDs der SMS-Liste über `_RENDERER_TO_CATALOG_METRIC_ID`. „Nie eingestellt“ (`None`) = `_NIE_EINGESTELLT_IDS` in dieser Folge. `N`, `FN`, `TH+:` und `TF` sind für Orte immer `enabled=False` (ADR-0125 Nr. 5). Einfach (`metric_formats[rid] is True`) ergibt den Einfach-Modus des Trips (`CT:SCT@13`), sonst Roh.
3. **`?` statt `?N`.** Ist eine gewählte Größe an einem Ort ohne Wert (Tageswert `None` bzw. alle Stundenwerte des zugehörigen Feldes `None`, oder `hourly_data` leer), trägt ihr Token `?` statt `-` (`W?`, `D?`). `-` bleibt „geprüft, unauffällig“. Unmappbare Einträge (`unresolved_count`) erzeugen kein Zeichen mehr in der SMS (sie fehlen an jedem Ort; die Mail weist sie aus).
4. **Formen je Ort.** `build_token_line(forecast, specs, report_type="morning", stage_name=<Name>, ampel=ampel)`; daraus die Formen „alle Listenzeilen“, „eine weniger“, … „keine Listenzeile“ über `render._drop_last_list_row`, gezeichnet als `f"O{n} " + " ".join(render._fuse(tokens))`; n = 1-basierter Platz in `location_render_order` (über alle Orte, auch ohne Daten; entfallene Orte nummerieren nie um). Auch bei genau einem Ort `O1 …`. Fehler-Ort: `O{n} n/a`. Orte werden nur durch ein Leerzeichen getrennt. Ortsnamen stehen nicht in der SMS.
5. **Kürzung (`_sms_fit_locations`).** Gesucht wird die größte Zeilenzahl k, bei der alle gezeigten Orte mit je k Listenzeilen (bzw. allen, wenn ein Ort weniger hat) in `max_chars` passen. Ab k = 1 ohne Erfolg entfallen Orte vom Ende als ` +k Orte`, Orte ohne `!`-Warnung zuerst; sind nur noch Orte mit Warnung oder ein Ort übrig, darf auch die erste Listenzeile fallen (k = 0, Warnblock bleibt). Kein Kopf; Grenze 160 (wie `SMSTripFormatter.format_sms`); ` X?` unverändert; die Namenskürzung im Degenerationsfall entfällt mit den Namen.
6. **`render_compare_sms(result, *, enabled_metrics, unresolved_count, metric_formats, ampel=None)`**: `ampel=None` → `resolve_ampel({})` (Standard-Vorlage). `compare_kanaltexte_rendern` übergibt `resolve_ampel(preset)`. Premium-SMS der Orte wie Trip (#3100): Text ≤ 153 → derselbe Text, sonst mit Grenze 153 neu gekürzt. Die Karte meldet `max_length` 160 auch für Orte.
7. **Karte „Was steht wo“ (`placements_view_service.py`).** Das SMS-Beispiel bleibt der Renderer-Text. Beispielwert je Zeile = Token(s) der Metrik im ersten Ort, wie sie in der SMS stehen (z. B. `W13@9`, bei L+D der Bereich `D-5/0`); „passt nicht mehr“ = die Metrik hat Token, keiner steht in der SMS. `_sms_kuerzel` (Legende) nennt für Orte dieselben Symbole wie für Trip (Doppelpunkt gehört zur Grammatik). `overflow`/Rest-Zähler entfällt für Orte (`None` wie beim Trip). Die Legende der Orte bekommt den festen Eintrag `O1` = „Ort 1 in der Reihenfolge des Abos“ (EN „Location 1 in the order of the subscription“, Katalog); die Trip-Legende bleibt unverändert.

## Expected Behavior

- **Input:** Orte-Abo mit 1 bis n Orten, SMS-Spalte der Tabelle „Was steht wo“ (oder nie eingestellt), Abo-Ampel, Stundenwerte je Ort.
- **Output:** SMS ≤ 160 Zeichen (Premium-SMS ≤ 153), z. B. (Werte illustrativ, exakte Zeichen aus dem Renderer im Test):
  - 1 Ort: `O1 D-5/0 W- G26@10(31@13) R- PR53%@13 TH:- SU2 CT:BKN@9 UV1 VS10.0@8 …`
  - 3 Orte: `O1 D-5/0 W- G26@10(31@13) R- PR53%@13 TH:- O2 D-4/1 W- G24@11 R- PR40%@12 TH:- O3 D-6/0 W- G- R- PR- TH:-`
  - 5 Orte: `O1 D-5/0 W- G26@10(31@13) R- O2 D-4/1 W- G24@11 R- O3 D-6/0 W- G- R- O4 D-3/2 W25@12 G41@12 R- O5 D-4/1 W- G- R-`
- **Side effects:** keine Datenänderung. Premium-SMS und Telegram-Kurzstil der Orte senden denselben Text.

## Acceptance Criteria

- **AC-1:** Given ein Orte-Abo mit drei Orten, dessen SMS-Spalte Temperatur, Wind, Böen, Regen, Regenwahrscheinlichkeit und Gewitter führt, und Stundenwerte mit Wind und Böen über Gelb der Abo-Ampel / When das Briefing über den echten Versandweg (`compare_kanaltexte_rendern`) gebaut wird / Then beginnt die SMS ohne Kopf direkt mit `O1 `, die Ortsteile lauten `O1 `, `O2 `, `O3 ` (Reihenfolge des Abos, kein Ortsname, kein Doppelpunkt, nur Leerzeichen als Trenner) gefolgt von den Token in Listenfolge, und jeder Ortsteil ist zeichengleich mit der Token-Zeile, die `build_token_line` aus denselben Werten mit derselben Ampel ergibt (z. B. `W21@13`, `G26@10(31@13)`, `R-`, `PR53%@13`, `TH:-`).
  - Test: `tests/tdd/test_3172_orte_sms_token_zeile.py` (Kern-Schicht, Gegenbau über `build_token_line`).

- **AC-2:** Given beliebige Orte-Werte inklusive Temperaturen zwischen −0,5 und 0 °C und einer Windrichtung von 330° / When die Orte-SMS gerendert wird / Then enthält sie keine alte Zellform mehr (kein ` km/h`, keine Temperatur mit `C`, kein `°`, kein Kürzel mit Leerzeichen vor dem Wert, keine Zähler `+N`/`?N` im Ortsteil), keine negative Null (`-0`), und die Windrichtung steht als Himmelsrichtung (`WD:NW`).
  - Test: Kern-Schicht, Parametrisierung über Werte und Auswahl.

- **AC-3:** Given eine gewählte Größe, die an einem Ort geprüft und unter Gelb liegt, und eine gewählte Größe, für die an einem anderen Ort kein Wert vorliegt / When die Orte-SMS gerendert wird / Then trägt die erste Größe den Leerwert `-` (z. B. `W-`) und die zweite `?` (z. B. `PR?`), wie in der Trip-SMS.
  - Test: Kern-Schicht.

- **AC-4:** Given Orte-Abos mit einem, drei und fünf Orten und voller SMS-Liste (nie eingestellt) / When die SMS gerendert wird / Then ist sie höchstens 160 Zeichen lang (die Premium-SMS höchstens 153 und bis 153 Zeichen zeichengleich mit der SMS), alle gezeigten Orte tragen gleich viele Listenzeilen (gekürzt vom Listenende), Orte entfallen als ` +k Orte` erst, wenn je Ort nur die erste Listenzeile steht, ein Ort mit amtlicher Warnung bleibt mit `!`-Block sichtbar, und ` X?` steht am Ende, sobald an einem Ort der Warndienst ausgefallen ist.
  - Test: Kern-Schicht, je Ortszahl; bestehende Fälle `test_compare_channel_overflow.py`, `test_3047_runde7_orte_luecken.py` auf die Token-Form umgestellt.

- **AC-5:** Given ein Orte-Abo mit Gewitter und Temperatur in der SMS-Liste, als Morgen- und als Abend-Briefing / When die SMS gerendert wird / Then erscheinen weder `N`, `FN` noch `TH+:`; die Gewitter-Zeile ist `TH:` allein.
  - Test: Kern-Schicht.

- **AC-6:** Given ein Orte-Abo mit genau einem Ort, eines mit einem Ort ohne Daten unter mehreren und eines mit lauter Orten ohne Daten / When die SMS gerendert wird / Then lautet sie `O1 {Token}`, bzw. `… O2 n/a …` (die übrigen Orte behalten ihre Nummer), bzw. `O1 n/a O2 n/a …`; in keinem Fall steht ein Ortsname, `Orte` oder ein Datum am Anfang der SMS.
  - Test: Kern-Schicht; `tests/tdd/test_orte_bereichsname_in_ausgaben.py` auf die Nummern umgestellt (Mail und Telegram-Normalstil unverändert).

- **AC-7:** Given dasselbe Orte-Abo für einen deutschen und einen englischen Nutzer, Telegram im Kurzstil / When Briefing-SMS, Premium-SMS und Telegram-Kurzstil gebaut werden / Then sind alle drei Texte zeichengleich, in beiden Sprachen identisch, und verwenden die Token-Zeile.
  - Test: Kern-Schicht über `compare_kanaltexte_rendern` und den Premium-Pfad.

- **AC-8:** Given eine SMS-Spalte mit nutzergewählter Reihenfolge, einer abgewählten Größe und Bewölkung auf Einfach / When die SMS gerendert wird / Then folgen die Token der Listenfolge, die abgewählte Größe fehlt ganz, und die Bewölkung steht als Stufe (`CT:SCT@13`), auf Roh als Zahl (`CT70@13`).
  - Test: Kern-Schicht.

- **AC-9:** Given zwei verschiedene Nutzer mit je einem Orte-Abo (drei Orte) / When jeder die Karte „Was steht wo“ abruft / Then zeigt das SMS-Beispiel jeweils die Token-Zeile des eigenen Abos, die Beispielwerte der SMS-Spalte sind Token derselben SMS (z. B. `W13@9`), Metriken, deren Token nicht mehr in die SMS passen, tragen „passt nicht mehr“, und kein Nutzer sieht Orte des anderen.
  - Test: `tests/tdd/test_placements_tabelle_endpoint.py` / `test_placements_tabelle_nachzug.py` (angepasst), E2E-Karte WS-2/WS-8 auf Staging.

- **AC-10:** Given die Trip-SMS mit den bestehenden Konfigurationen (mit und ohne gespeicherte Tabelle, Morgen/Abend, Premium) / When sie vor und nach dieser Änderung gerendert wird / Then ist sie zeichengleich.
  - Test: bestehende Trip-SMS-Goldens und `tests/unit/test_sms_kuerzel_trip_gleich_vergleich.py` grün; `sms_trip.py` und `output/tokens/*` ohne Diff.

## Definition of Done

- AC-1 bis AC-10 durch benannte Tests grün; Adversary mit Mutations-Gegenprobe ohne offenen Befund.
- Alle sechs CI-Checks grün; Staging-Verifikation der Karte (WS-2/WS-8) und eine echt zugestellte Orte-SMS/Telegram-Kurzstil auf Staging; Prod-Deploy, Selftest Exit 0.
- `sms_format.md` §5b/§6, `telegram_format.md`, `premium_sms_format.md` tragen die neue Form; ADR-0125 im Index.

## Test Plan

- **Kern-Schicht (ohne Netz):** `tests/tdd/test_3172_orte_sms_token_zeile.py` (AC-1 bis AC-8) über den echten Versandweg `compare_kanaltexte_rendern` mit kaltem Datensatz (`placements_beispiel.orte_ergebnis`, Orte Aabenraa/Flensburg/Schleswig/…); Gegenbau über `build_token_line` für die Parität (AC-1); Mutation „Ortsname statt `O{n}`“ muss rot werden.
- **Umgestellte Bestandstests:** alle Tests, die die alte Zellform (` km/h`, `D 20C`, `+N`, `?N`) erwarten, prüfen dieselbe Zusicherung in der Token-Form; keine Zusicherung entfällt ersatzlos außer den durch ADR-0125 abgelösten Zählern `+N`/`?N`.
- **RED-Nachweis:** der neue Test läuft gegen `origin/main` rot (alte Zellform).
- **Mutations-Gegenprobe:** alte Zelle zurück (`f"{code} {wert}"`), Ampel nicht durchgereicht (`@h` fehlt), `?` → `-`, `TH+:` aktiviert, Zeilenzahl je Ort ungleich, ` X?` vergessen, Trip-Präfix gekürzt (`_sanitize_stage_name`) – jede Verfälschung muss ein Test fangen.
- **Staging:** Karte „Was steht wo“ (Playwright WS-2/WS-8), Vorschau eines Orte-Abos mit drei Orten.

## Known Limitations

- Bei Werten ab Gelb ist `@h(max@h)` länger als die alte Zelle; bei drei und mehr Orten stehen dann weniger Größen je Ort.
- Verdrängte Größen werden nicht mehr gezählt (wie im Trip). Wer alles sehen will, liest Mail oder Telegram-Normalstil.
- Die SMS nennt keine Ortsnamen; die Zuordnung `O1`… folgt der Reihenfolge der Orte im Abo (wie in Mail und Liste).

## Out of Scope

- Trip-SMS, Mail, Telegram-Normalstil, Alarm-SMS.
- Eigene Premium-SMS-Auswahl (#2801).
- Nachtwert und Folgetag-Gewitter für Orte (ADR-0125 Nr. 5).

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** ADR-0125
- **Rationale:** Löst die freigegebene Zellform von `compare_kanal_metriken.md` §3 und den Zähler `?N` (`sms_format.md` §5b) ab; eine Entscheidung wird nie still rückgängig gemacht.

## Changelog

- 2026-11-19: Initial spec created (Issue #3172, PO-Vorgabe gleichen Tags)
- 2026-11-19: PO-Nachtrag: Orte als `O1`, `O2` … statt Namen; kein Kopf, kein Doppelpunkt, kein Strichpunkt, 160 Zeichen wie Trip
