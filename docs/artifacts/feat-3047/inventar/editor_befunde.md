# Bereich `editor` — Befunde Runde 7 (#3047, Einstellung = Ausgabe, Spalte Einstellungsseite)

Stand: `main` 6ddf4a1, Worktree `agent-a8d5630bbe0250e82`. Produktcode und Repo-Tests unverändert (`git status` leer).
Prüfskripte: `/tmp/claude-0/-home-user-gregor-zwanzig/8fd24bbd-2477-52fc-adc3-e2681826a5f8/scratchpad/inventar/editor/`.

## Prüfweg

1. `konfigs.json`: 22 Trip- und 13 Orte-Konfigurationen im Persistenzformat (Folgen ungleich Katalog, nie eingestellt,
   bewusst leer, Totalschnitt über Bestandsfälle, Altbestand, Mischzustände).
2. `probe_editor.test.ts` (node --test): echte Lade-Funktionen des Hubs — Reiter Wetter `standAusAbo` (mit echtem
   Vergleichs-Katalog über `loadCompareSelectionEntries`), Reiter Zustellung `standAusTrip`/`standAusPreset`,
   Übergangsblock `kanalStilStart`, `ladeMailZustand` → `editor_sicht.json`.
3. `probe_ausgabe.py`: echte Python-Resolver (Loader `load_trip_from_dict`, `slot_aktiv`, `resolve_report_render_options`,
   `effective_alert_channels`, `effective_compare_briefing_channels`, `resolve_preset_slots`, `resolve_configured_window`,
   `TripAlertService._official_trigger_possible`, Mail-Spalten/Zeilen über die Kettenfunktionen
   `python_trip_tabellen`/`python_orte_vergleichstabelle` aus `test_einstellung_gleich_mail_editor_standard.py`) → `ausgabe_sicht.json`.
4. `vergleich.py`: 596 Prüfpunkte → `vergleich.json`.
5. `probe_folgespeichern.test.ts` + `folge_mergen.py`: Hub lädt, Nutzer ändert etwas Unbeteiligtes („Alarm ab für alle: Rot“
   bzw. Kurzstil), der echte Speicherer baut die Nutzlast, Ebene-1-Merge wie Go → Python-Ausgabe vorher/nachher (`ausgabe_folge.json`, `editor_folge.json`).

Befehle (aus dem Worktree):
```
cd frontend && node --import ./test-lib-loader.mjs --experimental-strip-types --experimental-test-module-mocks --test <S>/probe_editor.test.ts
cd .. && uv run python <S>/probe_ausgabe.py && uv run python <S>/vergleich.py
cd frontend && node --import ./test-lib-loader.mjs --experimental-strip-types --experimental-test-module-mocks --test <S>/probe_folgespeichern.test.ts
cd .. && python3 <S>/folge_mergen.py && uv run python <S>/probe_ausgabe.py konfigs_folge.json ausgabe_folge.json && python3 <S>/folge_mergen.py --diff
```
(`<S>` = `/tmp/claude-0/-home-user-gregor-zwanzig/8fd24bbd-2477-52fc-adc3-e2681826a5f8/scratchpad/inventar/editor`)

Wichtig für die Bewertung: Orte-Abos sieht der Editor nur über den Go-Ladepfad. Der normalisiert beim Lesen
(Slot-Migration 06:00, `alert_channels` materialisieren, Alt-Premium bereinigen, Tagesfenster klemmen,
`internal/store/compare_preset.go:96-117`). Abweichungen, die nur in der Rohdatei bestehen und vom Go-Ladepfad geheilt
werden (O05, O06, O10, Orte-Zeiten), sind deshalb nicht als Befund geführt. Trip-Abos normalisiert Go beim Lesen nicht.

---

## E1 — Grundauswahl „nie eingestellt“: Reiter Wetter zeigt die Vorlage, die Mail etwas anderes (hoch)

- **Soll:** Konzept §5 Punkt 5/6 (Metrik-Zeilen = was im Briefing steht), Spec feat_3047 §5 („Editor-Standard = Mail-Standard“).
- **Ist:**
  - Trip mit `display_config.metrics` fehlt oder `[]`: Reiter Wetter zeigt die aktiven Metriken der Vorlage
    (allgemein: Temperatur, Wind, Böen, Niederschlag, Regenwahrscheinlichkeit, Gewitter, Bewölkung, Sonne; bei
    `ampel.template=alpen-trekking` 14). Die Mail zeigt den Register-Standard (Temperatur, Wind, Böen, Niederschlag,
    Gewitter, Nullgradgrenze, Sicht, Tagestief, Tageshoch). Der Zustellungs-Reiter (alte Metrik-Oberfläche) zeigt
    ebenfalls den Register-Standard: zwei Reiter derselben Seite zeigen verschiedene Grundauswahlen.
  - Orte ohne `active_metrics`: Reiter zeigt Vorlage (8 bzw. 14), Mail zeigt alle 25 Zeilen (`resolve_enabled_metrics` → None).
  - Folgeschaden (Kette `probe_folgespeichern`): Eine unbeteiligte Geste im Reiter Wetter (z. B. „Alarm ab für alle“,
    Tagesfenster, Warnungen) schreibt die angezeigte Vorlagen-Auswahl fest. Trip-Mail danach: 11 statt 9 Spalten
    (Sonne, Bewölkung, Regenwahrscheinlichkeit kommen dazu, Nullgradgrenze und Sicht fallen weg). Orte-Mail: 8 statt 25 Zeilen.
  - Neue Orts-Briefings aus einer eigenen Standard-Vorlage starten in genau diesem Zustand: Go schreibt nur `ampel`
    (`displayConfigAusVorlage(std, false)`).
- **Repro:** Fälle T01/T02/T03, O01/O04 in `vergleich.json`; `folge_mergen.py --diff` (T01, T02, O01, O04).
- **Dateien:** `frontend/src/lib/components/shared/wetter-tab/ampelModell.ts:392-402` (`auswahlLesen`, Rückfall `aktiveMetriken`),
  `wetterZustand.ts:68-82`, `ampelSchreiben.ts:62-79,94-110`; Python `src/app/loader.py:1007-1009`,
  `src/output/renderers/trip_metric_ids.py:29-35`, `src/output/renderers/compare_metric_ids.py:219-220`;
  Go `internal/handler/metric_preset.go:97-127`, `internal/handler/compare_preset.go:285-290`.
- **Vorschlag Fix:** Eine Regel für beide Seiten. Empfehlung: einmalige Read-Modify-Write-Migration, die bei
  Altbestand die heute ausgelieferte Auswahl ausdrücklich speichert (Trip: Register-Standard als `metrics[]`; Orte:
  die heute gezeigten Zeilen als `active_metrics`), damit sich keine Mail ändert; danach `auswahlLesen` ohne Vorlagen-Rückfall
  für Bestand, Vorlagen-Rückfall nur noch in der Anlege-Kette. Go: neues Orts-Briefing aus Standard-Vorlage schreibt `active_metrics` mit.
  Paritätstest Reiter Wetter gegen `python_trip_tabellen`/`python_orte_vergleichstabelle` (fehlt heute: die editor_standard-Tests prüfen nur die alte Oberfläche).
- **Einordnung:** Zielkonflikt zwischen Specs: feat_2794 AC-39 (und Kommentar `f007_trip_leere_auswahl.test.ts:1-11`) schreibt den
  Vorlagen-Rückfall fest und nimmt an, Python verhalte sich gleich; #3048/#3047 N1 hat Python auf den Register-Standard gestellt.
  Technisch auflösbar ohne Produktentscheidung (Migration „Mail bleibt wie sie ist“), daher Tech-Lead-Entscheid.

## E2 — Mehrtages-Trend „nie eingestellt“: Editor aus, Mail abends an; Kurzstil-Umschalten nimmt den Trend still raus (mittel)

- **Soll:** Konzept §3.2 V12 und §5 Punkt 8 („Vorbelegung: nur abends“).
- **Ist:** Python liest nur `report_config.multi_day_trend_reports`, Standard `["evening"]` (`loader.py:633-636`,
  ohne report_config `report_config_resolver.py` → `["evening"]`). Der Editor (`kanalStilStart` → `ladeReportZustand(rc)` ohne Vorgaben)
  zeigt bei fehlendem Feld Morgen und Abend aus. Umschalten des Telegram-Kurzstils sendet immer auch
  `multi_day_trend_reports: []` mit → der Abend-Trend fällt still weg (Kette T14/T06). Zusätzlich: bei widersprüchlichen
  Flags/Liste (T15) liest der Editor die Flags, Python die Liste.
- **Repro:** `vergleich.json` Prüfpunkt `trend_abend` T05–T21; `folge_mergen.py --diff` (T14, T06).
- **Dateien:** `frontend/src/lib/components/shared/zustellung-tab/kanalStilSpeicherung.ts:26-42`,
  `frontend/src/lib/components/shared/versand-tab/reportConfigPayload.ts:48-57,65-82`; `src/app/loader.py:633-636`, `src/services/report_config_resolver.py` (resolve_report_render_options).
- **Vorschlag Fix:** `trendAus` liest zuerst `multi_day_trend_reports` (Quelle der Mail), Rückfall `["evening"]` wie Python;
  `kanalStilNutzlast` sendet nur geänderte Felder (Kurzstil ohne Trend-Felder). Innerhalb Konzept.

## E3 — Trip-Altformat in `metrics[]` (Zeichenkette / ohne `enabled`): Editor zeigt „nicht gewählt“, Speichern zerstört den Trip (hoch)

- **Soll:** CLAUDE.md „Daten-Schema-Reworks: Bestandsdaten bleiben erhalten (Read-Modify-Write)“; Spec feat_3047 §2 Punkt 8 (Altbestand).
- **Ist:** Python wertet `"wind"` und `{metric_id}` ohne `enabled` als gewählt (`loader.py:906,1019,1041`). Der Reiter Wetter
  zählt nur `enabled === true` mit `metric_id` (`ampelModell.ts:400`) → Wind und Böen erscheinen als „Nicht im Briefing“, die Mail zeigt sie.
  Eine beliebige Speicherung im Reiter schreibt für den Zeichenketten-Eintrag `{"0":"w","1":"i","2":"n","3":"d","enabled":false}`
  (`ampelSchreiben.ts:62-79`, `klon` einer Zeichenkette, gespreizt). Go nimmt das ungeprüft an (`weather_config.go:91-109`,
  nur Ampel-Prüfung). Der Python-Loader bricht danach mit `KeyError: 'metric_id'` ab (`loader.py:1025`) und überspringt den
  Trip („Skipping corrupt trip“, `loader.py:1775`): keine Briefings und Alarme mehr für diesen Trip.
- **Repro:** Fall T22 in `vergleich.json`; `probe_folgespeichern.test.ts` + `folge_mergen.py` + `probe_ausgabe.py konfigs_folge.json …` (Traceback).
- **Dateien:** `frontend/src/lib/components/shared/wetter-tab/ampelModell.ts:399-402`, `ampelSchreiben.ts:62-79`, `internal/handler/weather_config.go:91-109`, `src/app/loader.py:897-907,1019-1041`.
- **Vorschlag Fix:** Frontend normalisiert Einträge wie `_coerce_metric_entry` (Zeichenkette → `{metric_id, enabled:true}`, fehlendes `enabled` = an) beim Lesen
  und in `tripMetriken`; Go weist `metrics[]`-Einträge ohne `metric_id` mit 400 ab. Innerhalb Spec. Erreichbarkeit: Altbestand
  mit Flach-Zeichenketten (#1262) — Umfang im Bestand vor dem Fix zählen.

## E4 — Amtliche Warnungen, Altbestand-Mischzustand: Schalter „an“, Briefing ohne Warnungen; Speichern schaltet still ein (mittel)

- **Soll:** Konzept §3.2 W20/A1 zusammengelegt: ein Schalter „im Briefing und als Alarm“.
- **Ist:** Ohne `official_warnings` ignoriert die Lese-Regel `official_alerts_enabled` (`amtlicheWarnungen.ts:24-31`):
  Bestand `official_alerts_enabled:false` (alter getrennter Briefing-Schalter #1087) zeigt „an“, das Briefing holt keine Warnungen
  (`trip_report_scheduler.py:1767`, Orte `scheduler_dispatch_service.py:952`). Jede Speicherung im Reiter Wetter schreibt
  beide Felder auf `true` → Briefing-Warnungen still wieder an (Kette T08, O09). Weitere Mischfälle: Alarm aus/Briefing an zeigt „an“
  (ODER-Regel, so in Spec feat_2794 festgelegt, T10); `official_warnings` nur mit `sources` zeigt „aus“, Ausgabe beide an (T09, nur Rohdatei).
- **Repro:** T08/T09/T10, O09 in `vergleich.json`; `folge_mergen.py --diff` (T08, O09).
- **Dateien:** `frontend/src/lib/components/shared/wetter-tab/amtlicheWarnungen.ts:24-37`; `src/services/trip_alert.py:1118-1135`, `src/services/compare_official_alert.py:184-197`.
- **Vorschlag Fix:** Einmalige Migration, die beide Felder angleicht (Wert = was heute im Briefing wirkt), danach Lese-Regel
  „an nur wenn Briefing UND Alarm an“. **Zielkonflikt** mit der in feat_2794 festgelegten ODER-Regel; Entscheidung, welcher
  Wert beim Angleichen gewinnt, ist fachlich (Briefing-Wert vs. Alarm-Wert).

## E5 — Trip-Tagesfenster Altbestand halbes Paar oder Start = Ende: Editor zeigt etwas anderes als gilt (niedrig)

- **Soll:** ADR-0035; Konzept §5 Punkt 9.
- **Ist:** `tagesfensterLesen` liest jede Grenze einzeln mit Ersatz 4/19 (`wetterZustand.ts:52-64`): `{start:6}` zeigt 6–19, `{8,8}` zeigt 8–8;
  Python wertet nur gültige Paare (`day_window.py:46-55`, `loader.py:125-135`) → 4–19. Die nächste Speicherung im Reiter
  schreibt 6–19 fest, die Ausgabe ändert sich still (Kette T11). Orte nicht betroffen (Go klemmt beim Laden, `store/compare_preset.go:116`).
- **Repro:** T11/T12 in `vergleich.json`; `folge_mergen.py --diff` (T11).
- **Dateien:** `frontend/src/lib/components/shared/wetter-tab/wetterZustand.ts:52-64`; `internal/store/trip.go:224-266` (kein Lade-Klemmen wie bei Orten).
- **Vorschlag Fix:** dieselbe Paarregel im Frontend (oder Go klemmt auch beim Trip-Laden). Innerhalb Spec.

## E6 — Orte: „Tiefsttemperatur Nacht“ aus Vorlagen steht im Reiter, die Mail verwirft sie still (mittel)

- **Soll:** Konzept §5 Punkt 5/6; Angebot im Vergleich nur aus dem Vergleichs-Katalog (#2944, `ampelModell.ts:345-351`).
- **Ist:** 6 von 7 Systemvorlagen aktivieren `temperature_night`; der Vergleichs-Katalog kennt die Größe nicht. Der Reiter zeigt die Zeile
  (Auswahl aus der Vorlage, ohne Katalog-Filter), speichert `{metric_id: temperature_night, aggregation: max}` (Rückfall `'max'`,
  `WetterTabInhalt.svelte:99`), `resolve_enabled_metrics` verwirft den Eintrag mit Warnung (`compare_metric_ids.py:233-240`). Gilt auch für
  neu angelegte Orts-Briefings aus diesen Vorlagen (Anlege-Kette nutzt dieselbe Nutzlast).
- **Repro:** `editor_folge.json` vs `ausgabe_folge.json`, Fall `O04_vorlage_alpen_ohne_liste__wetter`; statisch: Vorlagen ∖ Vergleichs-Katalog (`probe_ausgabe.py`-Umgebung).
- **Dateien:** `frontend/src/lib/components/shared/wetter-tab/ampelModell.ts:392-402`, `ampelSchreiben.ts:85-104`, `frontend/src/lib/components/organisms/wetter-tab/WetterTabInhalt.svelte:99`.
- **Vorschlag Fix:** Auswahl im Vergleich auf `katalogIds` schneiden (gleiche Regel wie `briefingAngebot`) oder `temperature_night` im Vergleich
  auf Temperatur-Minimum abbilden. Innerhalb Spec.

## E7 — Trip: abgeleitete Größen (Tiefsttemperatur Nacht, Tagestief/-hoch, Windchill-Kinder) in der Mail, im Reiter „nicht im Briefing“ (mittel)

- **Soll:** Konzept §5 Punkt 6 („Nicht im Briefing“ heißt: steht nicht in der Mail).
- **Ist:** Ist Temperatur gewählt und haben die Kind-Größen keinen eigenen Eintrag, leitet der Python-Loader sie als gewählt ab
  (`loader.py:916-958`); die Mail zeigt Nacht-Tiefst, Tagestief, Tageshoch. Der Reiter Wetter zeigt nur „Temperatur“ und bietet die drei unter
  „Nicht im Briefing: +“ an (`ampelModell.ts:355-360`). Die alte Metrik-Oberfläche im Zustellungs-Reiter leitet sie ab (gleich der Mail).
  Jede Vorlage ohne `temperature_night` (z. B. allgemein) erzeugt diesen Zustand.
- **Repro:** `probe_angebot.test.ts` → `angebot.json` gegen Fall T04 (`ausgabe_sicht.json`, `mail_spalten`); Kette T01 nachher.
- **Dateien:** `frontend/src/lib/components/shared/wetter-tab/ampelModell.ts:333-360,399-402`, `ampelSchreiben.ts:62-79`; `src/app/loader.py:916-958`.
- **Vorschlag Fix:** Reiter Wetter nutzt dieselbe Ableitung (`deriveMissingChildMetrics` existiert im Frontend) oder schreibt beim Speichern
  `enabled:false` für nicht gewählte Kind-Größen. Innerhalb Spec/Konzept.

## E8 — Mail-Inhalt-Altwerte `null`: Editor „an“, Mail ohne Block (niedrig)

- **Ist:** `report_config.show_stage_stats: null` bzw. `show_yesterday_comparison: null` → Editor an (`mailInhaltZustand.ts:28-32`), Python `.get(k, True)` liefert `None` (`loader.py:637,649`) → Block fehlt. `email_format: null` → beide „Ausführlich“ (gleich).
- **Repro:** Fall T17. Erreichbarkeit gering (kein bekannter Schreibweg für `null`).
- **Vorschlag Fix:** Python `is not False` bzw. Coercion beim Laden. Innerhalb Spec.

---

## Testlücken ohne Fehlverhalten (überlebende Mutationen)

| ID | Mutation | Wirkung, die kein Test fängt |
|---|---|---|
| TL1 | M4 `zustellungModell.ts:255` Abend-Standard Orte `?? false` → `?? true` | Editor zeigt Abend-Briefing an, Versand aus |
| TL2 | M6 `zustellungModell.ts:212` Stille Stunden `&&` → `||` | halbe Ruhezeit als aktiv angezeigt |
| TL3 | M7 `kanalStilSpeicherung.ts:52` Orte-Kurzstil beim Laden ignoriert | Schalter „aus“, Telegram bekommt Kurzform |
| TL4 | M8 `reportConfigPayload.ts:55` Vorrang Flags/Liste | siehe E2 |
| TL5 | M16 `internal/handler/trip.go:484` Feld-Merge `alert_channels.email` | PUT ohne `email` verliert den Wert |
| TL6 | M21 `internal/store/compare_preset.go:116` Lade-Klemme Tagesfenster Orte | Orte-Editor zeigte halbes Paar |
| TL7 | M25 `zustellungModell.ts` Trip `send_email` Standard | Editor zeigt E-Mail aus, Versand an |
| TL8 | M1 `ampelModell.ts:400` `enabled === true` → `!== false` | (macht den Editor Python-gleich, siehe E3) |

## Mutationen (25, je mit Sicherungskopie unter `editor/sicherung/`, danach `git diff --stat` leer)

Skript: `mutationen.py` (Ergebnis `mutationen.json`, zweite Runde `--breit` mit 50 bzw. 67 Testdateien für Überlebende).

| Nr | Datei | Ersetzung | gefangen | von |
|---|---|---|---|---|
| M1 | wetter-tab/ampelModell.ts | `m?.enabled === true` → `!== false` | nein | — (breit 674 Tests) |
| M2 | wetter-tab/amtlicheWarnungen.ts | ODER-Regel ohne `official_alerts_enabled` | ja | amtlicheWarnungen.test.ts ac20_lesen_ow_false_alerts_true_* |
| M3 | wetter-tab/wetterZustand.ts | Standard-Tagesfenster 4 → 5 | ja | f004_trip_tagesfenster_lesequelle „leeres Abo ⇒ 4–19“ |
| M4 | zustellung-tab/zustellungModell.ts | Orte Abend-Standard `false` → `true` | nein | — (breit 67 Dateien) |
| M5 | zustellung-tab/zustellungModell.ts | unbekannte Dringlichkeit → MODERATE | ja | zustellungModell.test.ts ac17_* |
| M6 | zustellung-tab/zustellungModell.ts | Stille `&&` → `||` | nein | — |
| M7 | zustellung-tab/kanalStilSpeicherung.ts | Orte-Kurzstil immer `rich` | nein | — |
| M8 | versand-tab/reportConfigPayload.ts | Trend: Liste vor Flags | nein | — |
| M9 | mailInhaltZustand.ts | Vortag-Standard `true` → `false` | ja | mail_inhalt_zustand.test.ts leerer_blob__defaults_* |
| M10 | wetter-tab/ampelSchreiben.ts | `tripMetriken` enabled immer true | ja | ampelSchreiben.test.ts ac37_trip_metrics_* |
| M11 | wetter-tab/ampelSchreiben.ts | `radar_alert_enabled: true` | ja | ampelSchreiben.test.ts ac21_ac20_vergleich_radar_* |
| M12 | zustellung-tab/zustellungModell.ts | Cooldown-Standard 120 → 60 | ja | zustellungModell.test.ts ac26_cooldown_* |
| M13 | zustellung-tab/zustellungSpeicherung.ts | Gesamtschalter `||` → `&&` | ja | zustellungSpeicherung.test.ts f002_* |
| M14 | internal/handler/config_merge.go | Merge überschreibt vorhandene Schlüssel nicht | ja | TestTeil3_2794_ComparePreset_ZweiNutzer_FeldErhalt |
| M15 | internal/handler/trip.go | `official_warnings.sources` nicht erhalten | ja | TestUpdateTripHandler_OfficialWarningsEnabledOnlyPreservesSources |
| M16 | internal/handler/trip.go | `alert_channels.email` nicht erhalten | nein | — (breit nur netzabhängige Fehlschläge) |
| M17 | internal/handler/metric_preset.go | `order++` entfernt | ja | TestF3047_NeuerTripAusVorlageBehaeltVorlagenFolge |
| M18 | internal/handler/weather_config.go | display_config ersetzen statt mergen | ja | TestPutTripWeatherConfigMergesDisplayConfig, TestTeil3_2794_TripWeatherConfig_ZweiNutzer_FeldErhalt |
| M19 | internal/store/compare_preset.go | Migrationszeit 06:00 → 07:00 | ja | TestLoadComparePresets_LegacyPresetGetsMorningSlotDefaults |
| M20 | internal/handler/trip.go | Tagesfenster-Klemme beim Schreiben entfernt | ja | TestUpdateTripHandler_ClampsInvalidDayWindowPairOnWrite |
| M21 | internal/store/compare_preset.go | Tagesfenster-Klemme beim Laden entfernt | nein | — |
| M22 | weather-metrics-tab/channelMetricLayouts.ts | Kanal-Liste ohne Folge-Sortierung | ja | editor_aenderung_gleich_erwartung fall1_* |
| M23 | weather-metrics-tab/channelMetricLayouts.ts | Roh/Einfach je Kanal-Zeile immer Roh | ja | editor_aenderung_gleich_erwartung fall1_* |
| M24 | wetter-tab/amtlicheWarnungen.ts | Legacy-Zweig immer an | ja | amtlicheWarnungen.test.ts ac20_fallback_* |
| M25 | zustellung-tab/zustellungModell.ts | Trip E-Mail-Standard `!== false` → `=== true` | nein | — (breit 67 Dateien) |

Gefangen 17 von 25 (Frontend 10/16, Go 7/9 — M16 und M21 überleben).

## Weitere Belege

- Go zwei Nutzer: `go test ./internal/handler/ -run 'Teil3_2794|WeatherConfigEditorRoundtrip|S3a2794_AC2[2-5]|F3047|DayWindow|AlertChannelsCrossUser|LegacyPremium|SlotSchedule|AlertChannelThresholdsCrossUser|TwoUsers|ZweiNutzer|SameNameDifferentUsers' -count=1` → 62 PASS.
- Sprache: `node --test` i18n `paritaet_de_en`, `keine_hartkodierten_nutzertexte`, `en_katalog_regeln`, `versand_tab_sprache`, `wertebereiche_sprache`, `katalog_sprache_3021` → 288 PASS; 381 Schlüssel `wetter.`/`zustellung.`/`wertebereiche.` alle in EN, Vorlagennamen über `vorlageName.ts` aus dem Katalog.
- Bestandstests vor den Mutationen: editor_standard/anzeige/änderung + wetter-tab + zustellung-tab → 543 PASS.
- Hinweis zur Hub-Struktur: Auf `main` liegen die Kanal-Listen, Ausblick, Stundenverlauf, E-Mail-Format, Zusatzblöcke und SMS-Schwellen noch in der alten
  Metrik-Oberfläche (`WeatherMetricsTab bereich=zustellung`) im „Übergangsblock“ des Reiters Zustellung; die Karte „Inhalt je Kanal“ ist #3031 (PR #3042).
  Die vorhandenen editor_standard-Tests prüfen nur diese alte Oberfläche, nicht die Grundauswahl des neuen Reiters Wetter (Ursache, dass E1/E3/E6/E7 unentdeckt blieben).
