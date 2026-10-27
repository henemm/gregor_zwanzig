# Context: fix-2205-wettercode-zwischenstufe

## Request Summary
Issue #2205: Der Wettercode-Ast bildet WMO 95/96/99 pauschal auf `ThunderLevel.HIGH` ab. Code 95 heißt
„Gewitter, schwach oder mäßig"; eine einzige Modellstunde hebt die Tagesstufe auf „hoch" (KHW 24.08.:
eine Stunde Code 95 → Tag HIGH, Mitschnitt blieb LOW). Offen gelassen: (1) 95 niedriger abbilden,
(2) Mindestdauer/Persistenz — die Spec entscheidet.

## Related Files
| File | Relevance |
|------|-----------|
| `src/providers/openmeteo.py:274` (`THUNDER_CODES`), `:678-700` (`_parse_thunder_level`) | Ort des Befunds; aufgerufen `:913` (Parse) und `:457` (`_derive_thunder_fields` nach Fallback-Merge) |
| `src/providers/thunder_enrichment.py:143-203,219-276,327` | Fusion: `wettercode_level` = obiges Ergebnis; Radar-Override hebt max. auf MED |
| `src/output/metric_format.py:329,433-485,488-524,527-596` | `max_thunder`, `_signal_levels`, `thunder_signal_carriers`, `thunder_level_from_signals` (max-Fusion) |
| `src/app/thunder_scale.py` | `thunder_ordinal`, `thunder_low_statement` (ADR-0064/#2176), Herkunfts-Labels |
| `src/app/models.py:35-44` | `ThunderLevel` NONE/LOW/MED/HIGH |
| `src/services/weather_metrics.py:731-749,773-825,1399-1422` | Tag/Segment = max; Onset = erste Stunde ≥LOW; Herkunft `union_of_max_carriers` |
| `src/services/trip_report_scheduler.py:2807-2868,3090-3121` | Vorschausatz („Starkes Gewitter erwartet" vs „Gewitter möglich"), Uhrzeit = früheste Stunde auf Spitzenstufe |
| `src/services/alert_preset.py:114-118` | `ORDINAL_LEVEL_BOUNDS`: entspannt (HIGH, NONE), **standard (HIGH, HIGH)**, sensibel (MED, HIGH) |
| `src/services/weather_change_detection.py:~973-990` | Stufen-Alarm, HIGH→MAJOR, MED→MODERATE |
| `src/services/risk_engine.py:132`, `comparison_scoring.py:141,229` | Risikopunkt / Ortsvergleich-Scoring |
| `src/output/tokens/builder.py:129`, `sms_trip.py:327,595` | SMS `TH:`/`TH+:` Buchstabe H/M/L |
| `src/services/weather_snapshot.py:40,57`, `trip_alert.py:1052,1279`, `compare_alert.py:91` | Gespeicherte Stufen, gegen die der nächste Alarmlauf vergleicht |
| `src/analysis/thunder_ablation.py:26-33,140` | Handkopie des Parsers (Offline-Analyse #2181) |
| `internal/provider/openmeteo/models.go:50-58`, `provider.go:206`, `internal/model/forecast.go:8-14` | Go-Spiegel 95/96/99→HIGH; Go-Enum kennt kein LOW |
| `src/services/radar_service.py:461-463` | 95/96/99 als „konvektiv" (bool, unberührt) |

## Existing Patterns
- Stufe je Signalast in eigener Leiter, Fusion per `max()`, Herkunft = alle Äste auf Spitzenstufe (ADR-0025, ADR-0057).
- Konzept `docs/features/gewitter-gesamtkonzept.md:345` (Zielverfahren Schritt 1): **WMO <95 kein · 95 leicht · 96 mittel · 99 hoch** — der Code ist diesem Konzept nie gefolgt.
- „leicht" ist seit ADR-0064/#2176 **keine Gewitteransage** mehr („schwaches Signal (leicht)").
- Graduierung existiert nur pro Stunde (CAPE-Leiter #1679); **keine** Mindestdauer-/Persistenzregel im Gewitterpfad.

## Dependencies
- Upstream: Open-Meteo `weather_code` (einzige Quelle für `wmo_code`/Wettercode-Ast; MF/DWD/GeoSphere/merge setzen keinen).
- Downstream: Fusion → Tages-/Segment-/Fensterstufe → Vorschausatz, Stundentabelle, Farbband, SMS-Token, Risikopunkt, Ortsvergleich-Scoring, Stufen-Alarme (alle vier Kanäle), Snapshot-Vergleich, Mitschnitt/Replay.

## Existing Specs / ADRs
- `docs/specs/modules/feat_1474_gewitter_befund_stufen.md` (AC-4/AC-8, Z. 381-382 Wettercode-Ast)
- `feat_1679_cin_paarung_cape_leiter.md`, `feat_1759_radar_vorhersage_fusion.md`, `feat_2176_luftmasse_statt_gewitteransage.md`, `fix_1418_gewitter_risikopunkt.md`, `go_provider_openmeteo.md:206`, `feat_2181_s2c_gewitter_archiv_ablation.md`
- ADR-0025 (eine Fusion), ADR-0048 (modellspezifische CAPE-Schwellen; sagt nichts zum Wettercode), ADR-0057, ADR-0064
- Tests, die das Ist festschreiben: `tests/tdd/test_alert_sensitivity_levels.py:420-426` (MED nie erzeugt), `tests/tdd/test_thunder_level_low_ordinal_and_render.py:77` (95→HIGH), `tests/unit/test_weather_code_fallback_merge.py:263-280`, `internal/provider/openmeteo/provider_test.go:159-166`, `tests/tdd/test_thunder_ablation.py:122-130,266`

## Risks & Considerations
- 🔴 **Treffer nicht mitverlieren:** Am KHW trug der Wettercode-Ast 3 der 5 HIGH-Tage (28./29./31.08.) — genau die realen Gewittertage, 29.08. der einzige kräftige. Welche Codes (95/96/99) und wie viele Stunden dort standen, ist noch nicht gemessen → Analyse-Phase muss das gegen `/home/hem/gz-messdaten/khw-2026-08-archiv/` nachrechnen, bevor eine Abbildung gewählt wird.
- 🔴 **Alarm-Wirkung:** Standard- und Entspannt-Preset alarmieren nur auf HIGH. 95→MED/LOW schaltet Stufen-Alarme für Code-95-Gewitter bei diesen Nutzern ab (nur „sensibel" bliebe).
- 🔴 **95→LOW (Konzeptwert) kollidiert mit ADR-0064:** ein vom Modell gerechnetes Gewitter würde als „schwaches Signal", nicht als Gewitter ausgesprochen.
- **Gebiets-Asymmetrie FR/Korsika:** dort ist CAPE bei LOW gedeckelt, kein LPI → HIGH nur über Wettercode oder Blitzdichte; eine Abstufung trifft den GR20 überproportional.
- **Deploy-Übergang:** erster Alarmlauf vergleicht gespeichertes HIGH mit neuem MED/LOW → Schein-Entwarnung (Snapshot). Mitschnitt-Altzeilen bleiben HIGH → Vorher/Nachher-Replay verzerrt.
- **Persistenzregel:** Stufe, Herkunft und Onset müssen über dieselbe Stundenmenge gerechnet werden (Fehlerklasse #1498/#1653); Vorschau-Uhrzeit kann sich verschieben.
- **Spiegel-Drift:** Go-Provider (`models.go`) und `thunder_ablation.py` bilden dieselbe Regel nach; Go-Enum ohne LOW.
- Nicht Teil: #2182 (ADR-0048/CAPE-Deckel), #2206 (CAPE-Zeitpunkt), #2178 (CAPE-Leiter).
- Nebenbefund: `"radar"` fehlt in `THUNDER_SIGNAL_LABEL_DE` (→ #1199-Kandidat).

## Analysis

### Type
Bug-Ticket, nach Messung **umgedeutet**: Die Stufenzuordnung bleibt; geliefert werden Entscheidungsdokumentation + Hagel-Unterscheidung im Text.

### Messung (Archiv ICON-D2, Etappenpunkt, UTC, eigene Nachrechnung 15.09.)
| Tag | Wettercode-Stunden | Echtes Gewitter? |
|---|---|---|
| 24.08. | 19h:95 (eine Stunde, 1,2 mm) | nein — und im echten Vorhersage-Mitschnitt stand nur LOW (hat Nutzer nie erreicht) |
| 28.08. | 17h:99, 18h:95; Nacht 01h:95, 02h:95 | ja |
| 29.08. | 13h:96, 14h:99 | ja, der einzige kräftige |
| 31.08. | 20h:95 (eine Stunde, 5,3 mm) | ja — die Gewitternacht |
| übrige | keine | 02.09. getragen von CAPE, nicht vom Code |

- **24.08. (falsch) und 31.08. (echt) sind nach Code und Dauer identisch.** Keine Zuordnungs- oder Mindestdauer-Regel trennt sie.
- Ticket-Prämisse „9 von 13 Tagen hoch" ist ein Fehlzitat (9 = mittel ODER hoch; hoch = 5 Tage, davon 4 echt). Der Wettercode-Ast trug 3 der HIGH-Tage — alle drei echt. Überprognose-Treiber ist CAPE (#2178/#2206), nicht der Wettercode.
- Varianten gegen Standard-Alarm (ADR-0043: Alarm bei höchster Stufe): 95→LOW (Konzept) und 95→MED und Persistenz ≥2 h verlieren alle den 31.08.-Alarm. 95→LOW macht ihn zusätzlich zur Nicht-Gewitteransage (ADR-0064). Code 99 existiert praktisch nur im ICON-D2-Gebiet (07.09.: icon_eu/AROME/ECMWF 0×99) → auf Korsika wäre „hoch" über den Code kaum erreichbar.
- Hagel: `hail_flag` (96/99 → True) ist verdrahtet und wird in Mail-Tabellen, SMS, Kurzform, Ortsvergleich, `GEWITTER`-Kommando und Vorschausatz-Zusatz („Hagel: ja", `metric_format.format_hail_note`) ausgegeben. **Offen zu prüfen in der Spec-Phase:** Stufen-Alarmtext (`weather_change_detection`/Alarm-Renderer, alle vier Kanäle) — dort kein Hagel-Treffer gefunden.

### PO-Entscheid 2026-09-15
„Heutiges Alarmverhalten behalten, Hagel im Text unterscheiden."

### Hagel je Oberfläche (Explore-Kartierung 15.09., Kernpunkte selbst verifiziert)
**Unterscheidet schon (95 liest sich anders als 96/99):** Mail-Stundentabelle (Doppelring + „Hagel: ja", `email/helpers.py:616,769`), Mail-Tages-Pille (`helpers.py:1755`), 3-Tages-Vorschausatz (Renderer-Zusatz `html.py:1365`, `plain.py:335`), Mail-Ausblickzelle (`thunder_branch.py:206,217`), Kompakt-Zusammenfassung (`compact_summary.py:646`), Telegram-Fußzeile/Etappentabelle (`narrow.py:271`), SMS/Premium-SMS-Briefing (Suffix `+HL`, `tokens/builder.py:28`), `GEWITTER`-Kommando + Drilldown (`trip_command_processor.py:1647`), Ortsvergleich (alle Kanäle).

**Unterscheidet NICHT:**
1. 🔴 **Stufen-Änderungsalarm, alle vier Kanäle** — `AlertEvent` (`src/output/renderers/alert/model.py:16-80`) hat kein Hagelfeld (grep verifiziert), gemeinsame Quelle `notification_service.py:1584-1589`; Texte `alert/render.py` Betreff `:1238`, Mail `:1283/1295/1313`, Telegram `:1559`, SMS-Token `:1621-1632` („TH:M->H@15"). Premium-SMS nutzt denselben `sms_body`. Korridor-Alarm (`render.py:430-453`) ebenso.
2. 🔴 **Nowcast/Radar-Alarm behauptet Hagel für JEDES Gewitter:** `radar_service.py:137` `INTENSITY_CONVECTIVE = "Starker Hagel/Gewitter"`, `_is_convective_weathercode` `:461-463` wirft 95/96/99 zusammen (verifiziert). Code 95 = nachweislich kein Hagel-Code → falsche Aussage.
3. Nacht-Halbsatz „nachts starkes Gewitter ab HH:00" (`app/day_window.py:267`) — kein Hagelwert durchgereicht.
4. Mail-Hervorhebung „⚡ Gewitter möglich ab …" (`trip_report.py:773-777`).
5. Glance-Kommando „⛈ Gewitter: hoch" (`trip_command_processor.py:1586-1591`, `agg["hail_flag"]` liegt schon vor `:1536/1556`), HEUTE/MORGEN-Timeline (`~:1709`), Telegram-Metrikzeile (`narrow.py:522-526`).
6. Kompakt-Mail-/Telegram-Ausblick (`thunder_branch.py:222,233`) — **bewusst ohne Hagel per PO-Entscheid (Docstring) → NICHT anfassen.**

**Regel für Kurzkanäle:** SMS/Premium-SMS bekommen das bestehende Token-Suffix `+HL`, nie „Hagel: ja" (Längenbudget).

### Technical Approach
1. **Keine Änderung** an `_parse_thunder_level` / `THUNDER_CODES` (Python + Go-Spiegel).
2. **ADR** „Wettercode 95/96/99 bleibt auf höchster Stufe" mit der 24.08./31.08.-Messung; hält fest, dass `gewitter-gesamtkonzept.md:345` (95 leicht/96 mittel/99 hoch) bewusst NICHT umgesetzt wird; Konzeptdokument entsprechend nachtragen.
3. **Hagel-Unterscheidung ergänzen, Priorität nach Wirkung:** (a) Stufen-Änderungsalarm alle vier Kanäle — Hagelfeld in `AlertEvent`, befüllt in `alert/project.py`, Ausgabe über `format_hail_note` (Mail/Telegram) bzw. `+HL` (SMS/Premium-SMS); (b) Nowcast-Label trennt 95 („Gewitter") von 96/99 („Gewitter mit Hagel") statt pauschal „Starker Hagel/Gewitter"; (c) kleinere Flächen 3–5 oben. Fläche 6 bleibt unberührt. Kein neuer Wortlaut-Pfad.
4. Bestehende Tests `test_thunder_level_low_ordinal_and_render.py:77` und Go `provider_test.go:159-166` (95→HIGH) sind bereits die Zusicherung der Zuordnung — kein neuer Test dafür, nur ADR-Verweis.
5. Mutations-Gegenprobe muss am **gerenderten Kanaltext** beißen, nicht an `format_hail_note` isoliert.
6. ADR braucht Eintrag in `docs/adr/README.md` (`tests/test_adr_index_drift.py`); vorher `feat_1474_gewitter_befund_stufen.md:381-382` und ADR-0057 auf Konflikt prüfen.
7. Latente Codes 91–94/97 → NONE: **kein Fix** (0 Vorkommen in 230k Std.), nur im ADR vermerken. `"radar"`-Label → #1199.

### Scope Assessment
- Files: ~8–12 (ADR + README, Konzept-Doc, `alert/model.py`, `alert/project.py`, `alert/render.py`, `radar_service.py`, ggf. `day_window.py`/`trip_report.py`/`trip_command_processor.py`/`narrow.py`, Tests)
- Estimated LoC: +150–250 Code/Test → `loc_limit_override` wahrscheinlich nötig, falls (c) mit rein
- Risk Level: MEDIUM (Alarmtexte aller vier Kanäle; Stufen- und Auslöselogik unberührt)
- Deploy-Scope: full-stack (Python) → Staging-Validierung inkl. Alarm-Mail Pflicht; `e2e_scope` vor `/70` per `set-field` richten

### Außerhalb dieses Tickets (PO-Frage 15.09.)
- **Nacht-Gewitter-Warnung je Übernachtungsart (Hütte/Zelt):** existiert NICHT. Vorhanden sind nur die **Ruhezeit** (`alert_quiet_from/_to`, `src/app/trip.py:202`) — unterdrückt die *Zustellung* von Alarmen in einem Zeitraum, filtert nicht nach Wetter-Zeitfenster — und `show_night_block` (reine Anzeige). Früheres Ticket **#16 „F5: Biwak-/Zelt-Modus"** (Übernachtungstyp je Etappe) wurde am 04.08.2026 im Streichdurchgang #1485 gestrichen. → eigenes Ticket, nicht #2205.

### Open Questions
- [ ] Soll #16 (Übernachtungsart je Etappe, inkl. Nacht-Gewitter-Warnung) wiedereröffnet bzw. neu angelegt werden? (PO)
