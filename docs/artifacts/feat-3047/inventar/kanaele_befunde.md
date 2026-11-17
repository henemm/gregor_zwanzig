# Bereich kanaele — Befunde (#3047 Runde 7, Telegram · SMS · Premium-SMS, Trip und Orte)

Stand: Worktree auf `6ddf4a1` (main nach #3084). Alle Läufe ohne Netz über den echten Weg
(Trip: Trip-JSON → `load_trip` → `NotificationService.send_trip_report`; Orte: Preset-JSON im
Nutzerordner → `load_compare_presets` → `send_one_compare_preset`), Messpunkt
`tests/helpers/transport_mitschrift.py`, je Fall zwei frische Nutzer. Produktcode unverändert
(`git status`/`git diff --stat` nach jeder Mutation leer).

Skripte (Lauf jeweils aus dem Worktree):
- Trip: `uv run pytest -p tests.conftest --rootdir=. -c pyproject.toml /tmp/claude-0/-home-user-gregor-zwanzig/8fd24bbd-2477-52fc-adc3-e2681826a5f8/scratchpad/inventar/kanaele/pruef_trip_kanaele.py -q`
- Orte: dasselbe mit `.../inventar/kanaele/pruef_orte_kanaele.py`
- Mutationen: `python3 .../inventar/kanaele/mutationen.py` (+ `mutationen_breit.py`, `mutationen_zusatz.py`)
- Rohausgaben: `.../inventar/kanaele/out/*.json`

Erwartet rot (= Befunde): Trip `test_t_tg_windrichtung_roh_3063`, `test_t_sprache_en_kappungshinweis`,
`test_t_sms_kuerzung_nach_liste`, `test_t_premium_eigene_liste_n2` (ausgelagert #2801); Orte
`test_o_sms_warnung_zweiter_ort_faellt_als_letztes`, `test_o_leer_und_totalschnitt`,
`test_o_premium_eigene_liste_n2` (ausgelagert #2801).

---

## B-K1 — Trip-Telegram ignoriert „Windrichtung Roh“ (#3063 Punkt 2) · Schwere: mittel

- **Soll:** Roh/Einfach je Zeile wirkt in jeder Liste (Konzept §3.2 W11, §5 P8); Mail Roh zeigt „250°“, Telegram muss dasselbe zeigen (ADR-0095 Pkt 1, gleicher Inhalt).
- **Ist:** `channel_layouts.telegram[wind_direction].format_mode = "raw"` → Telegram-Kurzübersicht `WD W`, Tabellenspalte `WD` = `W`. Mail derselben Sendung „250°“. **Orte-Telegram ist korrekt** (Roh „Windrichtung 250°“, Einfach „Windrichtung W“).
- **Repro:** `pruef_trip_kanaele.py::test_t_tg_windrichtung_roh_3063` (rot); Gegenprobe Orte `pruef_orte_kanaele.py::test_o_tg_windrichtung_roh_3063` (grün).
- **Ursache:** `src/output/renderers/narrow.py:88-96` (`_cell`) ruft `fmt_val(...)` ohne `format_modes`; in `src/output/renderers/email/helpers.py:912-920` gilt für `wind_dir` nur `mode == "raw"` als Roh, `mode` ist ohne `format_modes` `None` → immer Kompass. `friendly_keys` wird für `wind_dir` nicht ausgewertet.
- **Fix-Vorschlag:** in `narrow._cell`/`_overview_line` `format_modes=build_format_modes(dc)` (aus `_dc_telegram`) mitgeben, oder im `wind_dir`-Zweig bei `mode is None` `key not in friendly_keys` als Roh werten. Kettentest an der Telegram-Ausgabe (wie im Skript).
- **Einordnung:** innerhalb Spec/Konzept; gehört zu #3063.

## B-K2 — Trip-Telegram: Kappungshinweis bei EN-Nutzern deutsch · Schwere: mittel

- **Soll:** Nutzertexte in Nutzersprache (ADR-0104, Konzept §8); EN-Katalog hat `allgemein.telegram_limit.route.*` („… +2 more weather values as daily value only (Telegram limit)“).
- **Ist:** EN-Sendung: Kopf „Evening“, „Summary“, „Hr“, „medium“, aber „… +2 weitere Wettergrößen nur als Tageswert (Telegram-Limit)“.
- **Repro:** `pruef_trip_kanaele.py::test_t_sprache_en_kappungshinweis`.
- **Ursache:** `src/output/renderers/narrow.py:911` `telegram_metric_notice(layout.demoted_count, context="route")` ohne `lang=lang` (Orte-Pfad `comparison.py:974` reicht `lang` durch).
- **Fix:** `lang=lang` ergänzen; Test EN-Trip-Telegram mit > 7 Zeilen. Nicht in #3074 enthalten.
- **Einordnung:** innerhalb Spec/Konzept.

## B-K3 — Orte-SMS/Premium-SMS: amtliche Warnung eines weiteren Ortes fällt vor Wetterzellen weg · Schwere: hoch

- **Soll:** Konzept §5 P8 / WV6: Amtliche Warnungen „stehen immer am Ende (Warn-Block mit !) und fallen beim Kürzen als letztes weg“; Design-Leitprinzip Sicherheit vor Optik; `comparison.py` selbst: „Der Marker wird NIE verdrängt“.
- **Ist:** Nur der zweite Ort (Bozen) hat eine Gewitterwarnung (Stufe orange). SMS und Premium-SMS: `Vergleich 08.07.: Innsbruck G 19 km/h D 22C WD 250 W 11 km/h R 3.5 mm PR 40% CT 35% SU 6.0h TH mittel UV 6 +1 Orte` — Bozen samt `!TS:M@10` fällt als „+1 Orte“ weg, Innsbrucks Sonne/UV bleiben. Telegram zeigt die Warnung.
- **Repro:** `pruef_orte_kanaele.py::test_o_sms_warnung_zweiter_ort_faellt_als_letztes` (Rohtext `out/pruef_orte_warnung_bz.json`).
- **Ursache:** `src/output/renderers/comparison.py:1205-1245` — jeder Ortsteil bekommt das Budget „als wäre er der einzige“ (`location_budget`), der erste Ort füllt die SMS, die Einpass-Schleife verwirft danach ganze Orte; der Warn-Marker ist nur innerhalb seines Ortsteils geschützt (`_sms_location_part`, `comparison.py:1146-1163`).
- **Fix-Vorschlag:** Vor dem Verwerfen eines Ortes mit Marker erst Zellen der vorderen Orte kürzen (Budget je Ort nach Anzahl Orte aufteilen) bzw. weggefallene Orte mit Warnung als Kurzform `+1 Orte !Bozen TS:M@10` mitführen; Test zwei Orte, Warnung nur am zweiten, volle Grundauswahl.
- **Einordnung:** innerhalb Konzept (WV6) und sms_format; kein bekanntes Issue gefunden.

## B-K4 — Trip-SMS kürzt nach fester Priorität, nicht nach Listenende · Schwere: mittel · **Zielkonflikt**

- **Soll (Konzept §5 P8):** „Eine SMS hat 160 Zeichen. Was nicht mehr passt, fällt weg; die Liste zeigt, ab welcher Zeile.“, Mockup-Schnittlinie „passt nicht mehr in 160 Zeichen“ (ausgegraute Zeilen ab einer Stelle).
- **Ist:** Nutzer stellt Feuchte (HU) und Taupunkt (DP) an Platz 1 und 2 der SMS-Liste, Gewitter/Regen ans Ende → bei Überlänge fallen HU und DP **zuerst** (feste `DROP_ORDER`, `src/output/tokens/render.py:14-26, 76-130`), die Listen-Folge bestimmt nur die Anzeige. Orte-SMS kürzt dagegen nach Listenfolge von hinten (`comparison.py:1159-1161`) → Trip und Orte verhalten sich verschieden.
- **Bewusst gesichert:** `tests/tdd/test_sms_user_metric_order.py::test_ac6_drop_order_ignores_display_position` (#1677: sicherheitsrelevante Token R/PR/W/G/TH bleiben länger).
- **Repro:** `pruef_trip_kanaele.py::test_t_sms_kuerzung_nach_liste` (Rohtext `out/pruef_trip_sms_kuerzung.json`).
- **Empfehlung:** Liste bestimmt die Kürzung von hinten (amtliche Warnungen fest als Letztes), sicherheitsrelevante Größen über die Vorbelegung vorn; dann ist die Schnittlinie im Editor (#3032) eine echte Linie und Trip = Orte. Alternative: Prioritätskürzung beibehalten, Editor graut wegfallende Zeilen einzeln aus und der Erklärsatz wird angepasst. **PO-Entscheidung nötig** (Konzepttext gegen #1677 AC-6).

## B-K5 — Telegram-Schnittlinie: Konzepttext und Ausgabe widersprechen sich · Schwere: niedrig (Trip) / mittel (Orte) · **Zielkonflikt**

- **Soll (Konzept §5 P8, Erklärsatz V2):** „Die Kurzübersicht oben … zeigt die ersten 7 Zeilen, alle weiteren nur in der Tabelle darunter.“
- **Ist Trip:** umgekehrt — Kurzübersicht zeigt **alle** Zeilen, die Stundentabelle die ersten 7, Hinweis „… +2 weitere Wettergrößen nur als Tageswert“ (`narrow.py:807-913`, `channel_layout.py:150-156`, #1741).
- **Ist Orte:** Zeilen 8+ entfallen je Ort ganz, Hinweis „… vollständig per E-Mail“ (`comparison.py:965-976`). Widerspricht ADR-0095 Pkt 1 („Der Nutzer schaltet unterwegs den Kanal um ist keine Lösung“).
- **Repro:** `pruef_trip_kanaele.py::test_t_tg_schnittlinie_erste7_tabelle` (dokumentiert das Ist), Orte `out/pruef_orte_ohne_listen.json`.
- **Vorschlag:** Trip: Erklärsatz (#3033) an das Ist anpassen („alle Zeilen in der Kurzübersicht, die ersten 7 zusätzlich stündlich in der Tabelle“). Orte: Zeilen 8+ als zweite Zeile je Ort statt Wegfall (4096 Zeichen reichen bei üblicher Ortszahl). Konzepttext-Korrektur bzw. PO-Bestätigung.

## B-K6 — Orte: `channel_layouts.<kanal> = []` zeigt die volle Grundauswahl statt nichts · Schwere: niedrig (heute nur per API/Altbestand erreichbar)

- **Soll:** „leer bleibt leer“ (#1366/#2422; Trip `channel_layouts.sms = []` → leer; Orte `channel_active_metrics.sms = []` → leer; Docstring `resolve_channel_layout_rows` „leer bleibt leer“).
- **Ist:** Orte `channel_layouts.sms = []` und `.telegram = []` → SMS, Premium-SMS und Telegram zeigen alle zehn Grundauswahl-Zeilen. Alle Einträge `enabled:false` → korrekt leer.
- **Repro:** `pruef_orte_kanaele.py::test_o_leer_und_totalschnitt` (rot), Gegenprobe `test_o_alles_aus` (grün).
- **Ursache:** `src/output/renderers/compare_metric_ids.py:395-397` hängt nicht erfasste Grundauswahl-Zeilen (#3039 AC-14) auch bei leerer Liste an.
- **Fix:** `if entries == []: return []` vor dem Anhängen. Relevant, sobald der Orte-Editor `channel_layouts` schreibt (#3031/PR #3042). Datei liegt nicht im Sperrbereich von PR #3087.
- **Einordnung:** innerhalb Spec.

## B-K7 — Orte-Telegram ohne 3-Tages-Ausblick · Schwere: mittel

- **Soll:** Konzept W19/V12 (Ausblick-Liste für Trip und Orte, „Erscheint im Morgen-/Abend-Briefing“), ADR-0055 nennt Telegram als Ausblick-Kanal (SMS/Premium bewusst nicht); ADR-0095 Kanal-Parität; Trip/Orte-Code-Teilung.
- **Ist:** Trip-Telegram hat die Ausblick-Bubble (bzw. Zustandshinweis), `render_compare_telegram` (`comparison.py:850-998`) kennt keinen Ausblick; Orte-Mail zeigt ihn (auch Hinweis „Vorhersage derzeit nicht abrufbar“), Orte-Telegram schweigt.
- **Repro:** `pruef_orte_kanaele.py::test_o_dump_faelle` → `out/pruef_orte_ohne_listen.json` (Mail mit „3-Tages-Ausblick“, Telegram ohne).
- **Fix-Vorschlag:** Ausblick-Zeilen aus `_build_location_outlook_rows` (geteilt mit der Mail) als Telegram-Block je Ort/oder gesammelt; leer gewählte Liste lässt ihn entfallen.
- **Einordnung:** innerhalb Konzept; kein Issue gefunden (#3065 behandelt den Resolver, nicht den Telegram-Ausgang).

## B-K8 — Testlücke: Roh/Einfach in der Orte-Telegram-Liste von keinem Repo-Test bewacht · Schwere: niedrig

- **Ist:** Mutation M09 (`comparison.py:959` `friendly=False`) blieb in allen Repo-Tests grün (u. a. `test_compare_einstellung_auslieferung_kette.py`, `test_channel_metric_matrix.py`, `test_compare_kanal_metriken.py`, `tests/unit/test_compare_metric_order.py`, `tests/test_selection_conservation_rendered.py`); gefangen nur von `pruef_orte_kanaele.py::test_o_tg_reihenfolge_anaus`/`test_o_tg_windrichtung_einfach`.
- **Vorschlag:** Fall „Einfach in channel_layouts.telegram“ in `test_compare_einstellung_auslieferung_kette.py` aufnehmen (zwei Nutzer, Wolken-Symbol und Windrichtung W/250°).

## B-K9 — Kürzel-Legende: „steht auch am Ende jedes Briefings“ stimmt für Telegram/SMS nicht · Schwere: niedrig (Hinweis an #3032)

- **Soll:** Konzept §5 P8 (W21): „Die Legende steht auch am Ende jedes Briefings.“
- **Ist:** Trip- und Orte-Telegram enden mit „Aktionen“ bzw. dem letzten Ort, keine Legende; SMS/Premium-SMS ohne Legende (160 Zeichen; Befehl `KUERZEL` liefert sie). Nur die Mail trägt „Spalten: … = …“.
- **Vorschlag:** in #3032 entscheiden: Telegram-Legende als letzte Bubble ergänzen oder Satz auf „am Ende jeder Mail; per KUERZEL in SMS/Telegram“ ändern.

### Hinweise ohne Befund

- Trip, bewusst leere SMS-Liste: es geht trotzdem `E1:` per SMS und Premium-SMS hinaus (Premium kostet). Gilt als Nutzerwunsch „leer bleibt leer“, ggf. bei #2801 bedenken.
- Premium-SMS eigene Liste (N2): Trip und Orte senden den SMS-Text, `channel_layouts.premium_sms` wirkt nicht — ausgelagert #2801 (dort Umfang Pkt. 2 „Renderer liest die eigene Liste“).
- Telegram-Tabelle bricht bei breiten Zellen (z. B. „20 W“ zusammengeführt) Zeilen hart um (32 Zeichen, AC-9 #1001) — bekanntes Design.

---

## Mutationen (Gegenprobe, String-Ersetzung mit Sicherung unter `.../inventar/kanaele/backup/`)

Testmenge Runde 1: 10 Repo-Testdateien (`test_einstellung_gleich_auslieferung.py`, `test_compare_einstellung_auslieferung_kette.py`, `test_issue_1001_telegram_bubbles.py`, `test_compare_sms_official_alerts.py`, `test_trip_outlook_compact_telegram_dispatch.py`, `test_compare_sms_gsm7_charset.py`, `test_issue_614_telegram_kurzform.py`, `test_compact_summary_hiking_min_and_felt.py`, `test_compare_telegram_official_alerts.py`, `test_issue_944_disabled_metrics_sms.py`) + beide Prüfskripte (bekannt rote Tests ausgenommen). Baseline: nur die 7 erwartet roten. Nicht gefangene in Runde 2 gegen per grep gefundene breitere Mengen.

| ID | Datei | Ersetzung | gefangen | von |
|---|---|---|---|---|
| M01 | narrow.py | Kurzübersicht `for mid in sorted(dc.get_enabled_metric_ids())` | ja | pruef_trip::test_t_tg_reihenfolge_anaus |
| M02 | narrow.py | Warn-Bubble `if warn_bubble is not None and False` | ja | pruef_trip::test_t_tg_warnung_erste_zeile |
| M03 | narrow.py | `fkeys = set()` (Roh/Einfach ignoriert) | ja | pruef_trip::test_t_tg_roh_einfach_bewoelkung; test_einstellung_gleich_auslieferung::test_ac9_m3 u. a. |
| M04 | narrow.py | Kopf `briefing_typ(report_type, 'de')` | ja | pruef_trip::test_t_sprache_en_kopf_… |
| M05 | channel_layout.py | `metric_slots = limit` (8 statt 7) | ja | test_compare_einstellung_auslieferung_kette::test_reihenfolge_…; test_einstellung_gleich_auslieferung::test_ac2/ac10/ac13 |
| M06 | channel_layout.py | Tabellenspalten nach `metric_id` statt `order` | ja | pruef_trip::test_t_tg_reihenfolge_anaus, test_t_altbestand_ohne_layouts; pruef_orte::test_o_tg_windrichtung_roh_3063 |
| M07 | channel_layout.py | SMS `max_chars` 153 → 200 | ja | test_compare_sms_gsm7_charset::test_sms_char_budget_… |
| M08 | comparison.py | Orte-SMS `kept.pop(0)` (vorn kürzen) | ja (Runde 2) | test_compare_sms_kuerzel::test_sms_cuts_whole_metrics_…; test_channel_metric_matrix::test_ac_s7_8c_…; test_selection_conservation_rendered::test_ac12_… |
| M09 | comparison.py | Orte-Telegram `friendly=False` | **nein** in allen Repo-Tests (B-K8); ja nur pruef_orte::test_o_tg_reihenfolge_anaus, test_o_tg_windrichtung_einfach |
| M10 | comparison.py | Orte-SMS Warn-Marker unterdrückt | ja | test_compare_sms_official_alerts (2 Tests); pruef_orte::test_o_warnung |
| M11 | comparison.py | Orte-Kappungshinweis `lang="de"` | ja | pruef_orte::test_o_en |
| M12 | sms/__init__.py | `render_line(token_line, max_length + 40)` | ja (Runde 2) | test_sms_official_alert_tokens::test_ac7_…; test_sms_user_metric_order::test_ac6_…; test_trip_sms_gsm7_charset |
| M13 | sms_trip.py | erweiterte Specs `position=None` | ja | test_einstellung_gleich_auslieferung::test_ac5_golden_c_sms_reihenfolge…, test_hauptmatrix_golden_c_b9… |
| M14 | sms_trip.py | `sms_format_fields` → `{}` (Roh/Einfach aus) | ja | test_einstellung_gleich_auslieferung::test_hauptmatrix…, test_ac2, test_ac10 |
| M15 | sms_trip.py | `_official_alert_entries` → `()` | ja | pruef_trip::test_t_sms_warnung_am_ende |
| M16 | comparison.py | Orte-SMS `_sms_metric_cell(..., False)` | ja | pruef_orte::test_o_sms_einfach_bewoelkung |
| M17 | compact_summary.py | Wolken `if False:` (nur Mail-Kurzzusammenfassung) | ja (Runde 2) | test_einstellung_gleich_mail_trip::test_ac11_altbestand_golden; test_metric_format_slice6_scales |
| M18 | narrow.py | Trip-Kappungshinweis `notice = ""` | ja (Runde 2) | test_telegram_metric_notice (2 Tests); test_telegram_windrichtung_ohne_geisterspalte::test_ac13 |
| M19 | narrow.py | Ausblick `_outlook_lines(multi_day_trend, None, …)` | ja | test_trip_outlook_compact_telegram_dispatch::test_ac3/ac5; test_outlook_darstellungsform::test_ac5 |
| M20 | notification_service.py | amtlicher Trip-Alarm Kurzstil `and False` | ja (gezielte Menge) | test_telegram_kurzstil_trip_alert::TestAC4…; tests/test_slf_bulletin_kanaele (ac18, ac20) |

Ergebnisdateien: `.../inventar/kanaele/mutationen_runde1.json`, `mutationen_breit_ergebnis.json`, `mutationen_m09_nachtest.json`, `mutationen_zusatz_runde1.json`, `mutationen_zusatz_ergebnis.json`.
