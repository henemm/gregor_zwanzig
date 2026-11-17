# Bereich „luecken“ – Befunde (#3047 Runde 7, Lückenschluss der Matrix)

Auftrag: alle 402 Zellen „ungeprueft“ der konsolidierten Matrix entscheiden (382 davon von keinem Bereich betrachtet).
Ergebnis: `status_updates.json` (402 Einträge: 219 gruen, 111 nicht_anwendbar, 45 rot, 24 ausgelagert, 3 ungeprueft),
danach `konsolidieren.py` gelaufen. Ausgenommene bekannte Befunde (B-K*, E*, B-TM*, B-OM-*, B-V*) sind in den Zellen nur
referenziert, nicht erneut gemeldet.

## Prüfweg

Alle Sonden ohne Netz, über den echten Lese- und Versandweg, je Fall zwei frische Nutzer, Folgen ungleich Katalogfolge.
Lauf aus dem Worktree: `uv run pytest -p tests.conftest --rootdir=. -c pyproject.toml <Datei> -q`
(Validator-Sonde mit `PLAYWRIGHT_BROWSERS_PATH=/opt/pw-browsers`).

| Datei (unter `scratchpad/inventar/luecken/`) | Weg |
|---|---|
| `test_trip_luecken.py` | Trip-JSON → `load_trip` → `NotificationService.send_trip_report` → Transport-Mitschrift (alle vier Kanäle, Mail Voll/Kompakt) |
| `test_trip_sched_luecken.py` | echter Zeitplaner `_send_trip_report_outcome` mit allen vier Kanälen (Ausblick in Telegram, W20) |
| `test_trip_alarm_luecken.py` | Alarm-Felder im JSON → `load_trip` → `TripAlertService.check_and_send_alerts` → `AlarmPruefstrecke` (4 Kanäle) |
| `test_orte_luecken.py` | Preset-JSON → `send_one_compare_preset` → Mitschrift; Engine-Naht zeichnet Fenster/Warnschalter auf |
| `test_orte_alarm_luecken.py` | Preset-JSON → `CompareAlertService` (Kettenhelfer #2422 S5) → Mitschrift |
| `test_zustellung_luecken.py` | Golden D auf Platte → `TripReportSchedulerService.send_due_reports` (Uhrzeit, Slots, Kanäle) |
| `zz_luecken_vorlage_probe_test.go` + `test_vorlage_kette_luecken.py` | echte Go-Handler (POST Vorlage als Standard → POST Trip/Orts-Vergleich), Datei nur temporär im Paket, danach gelöscht; Python rendert die von Go geschriebene `display_config` |
| `test_validator_luecken.py` | Validatoren `--konfig --eml` auf echt gerenderte Mails + gezielte Verfälschungen |
| `probe_editor_luecken.test.ts` (+ `editor_konfigs.py`) | echte Ladefunktionen des Hubs (Kanal-Listen, `standAusAbo` gegen Python `resolve_ampel`, `ladeMailZustand`, `standAusPreset`), SSR-Render von `OutlookLayoutControls`/`CompareHourlyLayoutControls` |
| `mutationen.py` | 33 Mutationen, Ergebnis `out/mutationen_ergebnis.json` |

---

## B-L1 — Trip-Telegram-Kurzübersicht ignoriert das Tagesfenster · Schwere: mittel

- **Soll:** ADR-0035 Punkt 1/2 („ein Tagesfenster, wirksam auf Anzeige und Bewertung“) und ADR-0095 (jeder Kanal
  beantwortet dieselbe Frage gleich): „ab wann wird es gelb“ muss in Mail, SMS und Telegram dieselbe Stunde nennen.
- **Ist:** Tagesfenster 10–19: SMS `R2.0@10 G45@10`, Mail „Böen … ab 10:00“, Telegram-Kurzübersicht `R 2.0@08`,
  `G 45@08` (Gehzeit-Beginn, außerhalb des Fensters). Auch beim Standard 4–19 nennt Telegram 08, SMS/Mail 04.
- **Repro:** `test_trip_luecken.py::test_tagesfenster_telegram` (rot erwartet).
- **Dateien:** `src/output/renderers/narrow.py:459-500` (`_overview_line`, Docstring: „NUR Gewitter wechselt auf das
  Tagesfenster; alle übrigen Metriken behalten die Gehzeit als Bezugsrahmen“, #1498).
- **Vorschlag:** Kurzübersicht für alle Metriken über dieselbe Fensterauflösung wie SMS/Mail
  (`day_window.resolve_configured_window`, wie es #1498 für Gewitter schon tut).
- **Einordnung:** **Zielkonflikt** zwischen Scheiben-Entscheidung #1498 (Gehzeit) und ADR-0035/ADR-0095 (jüngere ADRs).

## B-L2 — Orte-Telegram/SMS/Premium-SMS ohne Hinweis „Warnungen nicht abrufbar“ · Schwere: mittel

- **Soll:** ADR-0095 Kanal-Parität; Konzept §5 P8 Kürzel-Legende „X? Warnquelle nicht erreichbar“. Der Trip zeigt den
  Hinweis in Telegram (`narrow.py:790`) und SMS (`sms_trip.py:545`).
- **Ist:** Vergleich mit `official_alerts_unavailable`: HTML-Mail zeigt „nicht abrufbar“, Telegram und SMS/Premium
  schweigen; ein Nutzer unterwegs hält „keine Warnung“ für „geprüft, nichts los“.
- **Repro:** `test_orte_luecken.py::test_warnungen_nicht_abrufbar`, `::test_warnungen_nicht_abrufbar_sms` (rot erwartet).
- **Dateien:** `src/output/renderers/comparison.py:850ff` (`render_compare_telegram`), `:1167ff` (`render_compare_sms`)
  — kein Bezug auf `official_alerts_unavailable`.
- **Vorschlag:** gleiche Bausteine wie Trip (`any_official_alerts_unavailable`, `render_official_alerts_unavailable_plain`;
  SMS-Marker wie `sms_trip`).
- **Einordnung:** innerhalb Konzept/ADR (der Klartext-Teil derselben Lücke ist B-OM-1).

## B-L3 — Orte-Telegram: Ampel-Grenzen ohne Wirkung, „Einfach“ zeigt Windwort · Schwere: niedrig

- **Soll:** Konzept §4.2 (Ampel je Ort änderbar), §5 P8 („Einfach = Ampelpunkt, Symbol, Wort“, Beispiel
  „30 km/h · ● gelb“); ADR-0097 (ein Code Trip/Orte) — Trip-Telegram zeigt die Ampel als `@`-Marke.
- **Ist:** Böen Einfach in der Orte-Telegram-Liste: `Böen mäßig` bei Grenzen 100/110/120 und bei 5/10/15 gleich; HTML
  ändert die Ampelfarbe. Alarme folgen den Grenzen korrekt (`test_orte_alarm_luecken.py`).
- **Repro:** `test_orte_luecken.py::test_ampel_grenzen_alle_kanaele` (rot erwartet).
- **Dateien:** `src/output/renderers/comparison.py:636-660` (`_friendly_overview_text` → `_friendly_outlook_text`,
  Windwort statt Ampel).
- **Vorschlag:** PO-Klärung, ob Einfach für Ampel-Größen in Text-Kanälen Ampelzeichen (●/Stufe) zeigen soll; dann
  `resolve_ampel(preset)` in die Telegram-Zelle.
- **Einordnung:** **Zielkonflikt** (Wort- vs. Ampel-Darstellung für Ampel-Größen in Text-Kanälen).

## B-L4 — Orts-Vergleich „nie eingestellt“ / jede Neuanlage: Telegram und SMS zeigen alten Sechsersatz · Schwere: hoch

- **Soll:** Konzept §5 P8 (Listen ⊆ Grundauswahl, Telegram = erste 7 der Liste), ADR-0095 (gleicher Inhalt je Kanal).
- **Ist:** `active_metrics` fehlt (Altbestand UND jede Neuanlage, weil Go `displayConfigAusVorlage(…, mitMetriken=false)`
  keine Auswahl schreibt): Mail zeigt alle Register-Zeilen (Temperatur, Wind, Niederschlag, Regenwahrsch., Gewitter, …),
  Telegram/SMS/Premium nur `Temp, Wind, Sonne, Wolken, Schneehöhe, Neuschnee` — Regen, Böen, Gewitter fehlen ganz,
  ohne „+N weitere“-Hinweis.
- **Repro:** `test_orte_luecken.py::test_nie_eingestellt` (rot erwartet); Neuanlage: `test_vorlage_kette_luecken.py`.
- **Dateien:** `src/output/renderers/comparison.py:891-894` und `:1133-1136` (Rückfall `_CHANNEL_METRICS`), dagegen Mail
  `comparison.py:163-177` (`None` = alle Zeilen); `internal/handler/metric_preset.go:97-127`.
- **Vorschlag:** `None` in Telegram/SMS auf dieselbe Liste wie die Mail (CV2-Folge) abbilden; zusammen mit E1 lösen.
- **Einordnung:** innerhalb Konzept/ADR (Verhältnis zu E1: E1 = Reiter ≠ Mail, B-L4 = Telegram/SMS ≠ Mail).

## B-L5 — Validatoren: weitere ungeprüfte Einstellungen · Schwere: niedrig (Testlücke)

- **Soll:** Spec #3047 AC-19 (Validator prüft die Mail gegen die gespeicherte Konfiguration).
- **Ist (je Gegenprobe Exit 0 auf eine falsche Mail):** Trip: amtliche Warnungen trotz Schalter aus / Position
  (Validator kennt sie gar nicht), Kachelfolge des Metriken-Überblicks, Ampelfarbe gegen Grenzen/Vorlage;
  Orte: Zeilen bei nie eingestellter Grundauswahl, Zieltag-Datum (Morgen = heute / Abend = morgen), Hinweis
  „nicht abrufbar“ (kein Bezug im Validator), Ampelfarbe.
- **Repro:** `test_validator_luecken.py::test_trip_ueberblick_folge_ungeprueft`, `::test_trip_amtliche_warnung_ungeprueft`,
  `::test_trip_ampelfarbe_ungeprueft`, `::test_orte_nie_eingestellt_zeilen_ungeprueft`, `::test_orte_datum_ungeprueft`.
- **Dateien:** `.claude/hooks/briefing_mail_validator.py:984-1012` (`pruefe_soll`), `:773-785` (`_soll_ueberblick`
  nur Anwesenheit), `.claude/hooks/_soll_aus_konfiguration.py:497-520` (`orte_soll`: `uebersicht None` ⇒ kein Soll).
- **Vorschlag:** Soll um `official_alerts_enabled`, Überblick-Folge, Farbe aus `resolve_ampel`, Zieltag, Unavailable-Hinweis
  und Register-Zeilen bei `active_metrics` fehlt erweitern.
- **Einordnung:** innerhalb Spec (keine Fehlwirkung im Produkt, Prüfwerkzeug-Lücke; ergänzt B-V1…B-V8, #3083).

## B-L6 — Trip-Altformat ohne `order`: Validator lehnt die korrekte Mail ab · Schwere: niedrig

- **Soll:** Validator und Renderer leiten die Folge aus derselben Regel ab (Spec #3047 AC-19).
- **Ist:** `metrics: ["gust","precipitation","temperature"]` (oder ohne `enabled`): Renderer ordnet nach Register-Priorität
  (`loader.py:1015` `auto_distribute`) in allen Kanälen gleich (Temp, Böen, Regen); Validator-Soll nach Array-Folge
  (`_soll_aus_konfiguration.py:206` `_sortiert`, `order` fehlt = 0) → „SOLL: an Position 1 steht 'Temp' statt 'Gust'“, Exit 1.
- **Repro:** `test_validator_luecken.py::test_trip_altformat` (rot erwartet).
- **Vorschlag:** PO/Tech-Lead-Klärung, welche Folge für Altbestand ohne `order` gilt (Array-Folge = gespeicherte Absicht
  vs. Register-Priorität); dann eine gemeinsame Regel.
- **Einordnung:** **Zielkonflikt** (Altbestandsregel; Editor-Seite desselben Altformats ist E3).

### Hinweise ohne Befund

- Trip „nie eingestellt“ und ausdrücklich gespeicherter Register-Standard unterscheiden sich nur im Nachttief (SMS `N15`):
  der Loader hängt abgeleitete Größen nur an gespeicherte Listen (`loader.py:1054`, #3047 N1) — Thema E7.
- `show_outlook` ist reines Mail-Feld (Karte „E-Mail-Inhalt“); Telegram-Ausblick folgt nur `multi_day_trend_reports`.
- Stille Stunden und Mindestabstand haben je zwei Sperren (Trip-Adapter + geteilter Kern). Einzelmutationen einer Sperre
  überleben deshalb (bewusste Redundanz); M03/M04/M31/M32 mutieren beide bzw. den Kern und werden gefangen.
- 3 Zellen bleiben `ungeprueft`: `orte.ortsfolge`, `orte.orte_auswahl`, `orte.ortsnamen` × Einstellungsseite — der
  Orte-Reiter löst `location_ids` inline in `CompareTabs.svelte:263-268` auf; ohne SSR-/Browser-Prüfstand für
  `CompareTabs` nicht ausführbar.

## Mutationen (33, String-Ersetzung mit Sicherung unter `luecken/backup/`, danach zurückkopiert, `git diff --stat` leer)

| Nr | Datei | Ersetzung | gefangen | Test |
|---|---|---|---|---|
| M01 | src/services/report_config_resolver.py | `show_multi_day_trend=report_type in trend_reports` → `True` | ja | test_trip_sched_luecken.py -k erscheint_im |
| M02 | src/services/trip_report_scheduler.py | `if trip.official_alerts_enabled is not False:` → `if True:` | ja | test_trip_sched_luecken.py -k w20 |
| M03 | src/services/deviation_alert_engine.py | Ruhezeit-Prüfung immer „keine“ | ja | test_trip_alarm_luecken.py -k stille |
| M04 | trip_alert.py + deviation_alert_engine.py | beide Sperrzeit-Prüfungen aus | ja | test_trip_alarm_luecken.py -k cooldown |
| M05 | src/services/ampel_alarm.py | `"red": 3` → `2` | ja | test_trip_alarm_luecken.py -k alarm_ab |
| M06 | src/services/ampel_alarm.py | `"yellow": 1` → `2` | ja | test_orte_alarm_luecken.py -k alarm_ab |
| M07 | src/services/alert_channel_threshold.py | Kanal-Schwelle ignoriert | ja | test_trip_alarm_luecken.py -k dringlichkeit |
| M08 | src/output/renderers/trip_report.py | SMS-Ampel `resolve_ampel({})` | ja | test_trip_luecken.py -k ampel/vorlage |
| M09 | src/services/scheduler_dispatch_service.py | `official_alerts_enabled=True` | ja | test_orte_luecken.py -k amtliche |
| M10 | src/output/renderers/email/compare_html.py | Ortsfolge umgekehrt | ja | test_orte_luecken.py -k ortsfolge |
| M11 | frontend/.../wetter-tab/ampelModell.ts | `alarm_ab` nicht übernommen | ja | probe_editor_luecken.test.ts |
| M12 | frontend/.../wetter-tab/ampelModell.ts | obere Grenzen nicht übernommen | ja | probe_editor_luecken.test.ts |
| M13 | frontend/.../mailInhaltZustand.ts | `show_outlook` Standard `false` | ja | probe_editor_luecken.test.ts |
| M14 | frontend/.../zustellungModell.ts | `endDate: null` | ja | probe_editor_luecken.test.ts |
| M15 | frontend/.../OutlookLayoutControls.svelte | `outlookFriendlyMap = {}` | ja | probe_editor_luecken.test.ts |
| M16 | src/output/renderers/narrow.py | Telegram-Ampel `resolve_ampel({})` | ja | test_trip_luecken.py -k ampel/vorlage |
| M17 | src/output/renderers/comparison.py | Telegram-Liste umgekehrt | ja | test_orte_luecken.py -k altformat |
| M18 | src/services/notification_service.py | Alarm-Kurzstil aus | ja | tests/tdd/test_compare_alarm_einstellung_auslieferung_kette.py -k kurzstil |
| M19 | src/services/compare_radar_alert.py | Radar-Schalter ignoriert | ja | dto. -k radar_alarm_standard |
| M20 | src/services/compare_slot_scheduler.py | `end_date` ignoriert | ja | dto. -k abgelaufen |
| M21 | src/services/compare_slot_scheduler.py | `morning_enabled = True` | ja | tests/tdd/test_compare_einstellung_auslieferung_kette.py -k slots |
| M22 | src/services/compare_alert_channels.py | `send_telegram` ignoriert | ja | dto. -k kanalmatrix |
| M23 | frontend/.../nurEinBericht.ts | „nur morgens“ nie | ja | nur_ein_bericht_kennzeichnung.test.ts |
| M24 | frontend/.../channelMetricLayouts.ts | Totalschnitt-Rückfall aus | ja | probe_editor_luecken.test.ts |
| M25 | frontend/.../ampelSchreiben.ts | eigene Vorlage ohne Ampel | ja | vorlageDialogPayload.test.ts |
| M26 | frontend/.../compareMetricSelection.ts | nie eingestellt → `[]` | ja | editor_standard_gleich_mail.test.ts |
| M27 | src/services/compare_slot_scheduler.py | Morgenzeit fest 06:00 | ja | tests/test_2795_viertelstunden_faelligkeit.py -k vergleich |
| M28 | src/services/alert_channels.py | alle Alarm-Kanäle an | ja | test_compare_alarm_…kette.py -k trennt_zwei_nutzer |
| M29 | src/services/alert_channels.py | dto. | ja | test_trip_alarm_luecken.py -k kanaele_einzeln |
| M30 | src/services/alert_channel_threshold.py | Kanal-Schwelle ignoriert | ja | test_compare_alarm_…kette.py -k kanalmenge_schwelle |
| M31 | src/services/deviation_alert_engine.py | Ruhezeit aus | ja | test_compare_alarm_…kette.py -k ruhezeit |
| M32 | deviation_alert_engine.py + compare_alert.py | beide Sperrzeit-Prüfungen aus | ja | dto. -k ruhezeit |
| M33 | frontend/.../zustellungModell.ts | Unterzeilen Orte vertauscht | ja | zustellungModell.test.ts |

Vorläufer überlebten (dokumentiert, ersetzt): Einzelsperre Ruhezeit/Sperrzeit (Redundanz s. o.), `red`→2 für Orte
(Testdaten ohne Orange-Fall), Sortierung nach Namen (gleich der Testfolge), Filter auf falsches Vokabular.
