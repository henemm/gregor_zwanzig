# Bereich trip_mail – Befunde (#3047 Runde 7)

Grundlage: Worktree auf `6ddf4a1` (main nach #3084). Alle Läufe offline über den echten Weg
`load_trip` → `NotificationService.send_trip_report` (bzw. Zeitplaner `_send_trip_report_outcome`) → Transport-Mitschrift.
Prüfskripte: `scratchpad/inventar/trip_mail/` (`test_probe_render.py`, `test_probe_scheduler.py`, `mutationen.py`, `nachlauf.py`).
Aufruf (aus dem Worktree):
`PYTHONPATH=.:src uv run pytest <skript> -q -p no:cacheprovider -c pyproject.toml --rootdir=.`
(der `conftest.py` im Skriptordner übernimmt die Isolation der Repo-conftest).

Ausgangslage: `tests/tdd/test_einstellung_gleich_mail_trip.py` grün (219 Tests, 2 xfail = #3065).
Eigene Prüfskripte: 81 Fälle (53 Versandweg + 28 Zeitplanerweg); rot nur die 6 Fälle zu B-TM1 und B-TM2.

---

## B-TM1 – Kompakt-Mail: amtliche Warnungen stehen nicht an erster Stelle (WV6)

- **Schwere:** mittel (Sicherheitsrelevanz: Warnung unter dem Metrik-Überblick, im Kompaktformat für schwache Verbindungen).
- **Soll:** Konzept `docs/context/einstellungen_neu.md` §3.2 WV6 und §5 Punkt 8: „Amtliche Warnungen als feste Zeile: bei E-Mail/Telegram ‚steht immer zuerst, nicht verschiebbar‘“. Kompakt ist ein E-Mail-Format (W15). Die HTML-/Klartext-Mail setzt das seit #3047 um (`plain.py:219` „Warnblock direkt nach dem Kopf, vor jedem Metrik-Inhalt“).
- **Ist:** Im Kompaktformat kommt `== Metriken-Ueberblick ==` zuerst, danach `== Warnungen ==` (DE und EN, Morgen und Abend).
- **Repro:** `test_probe_render.py::test_r10_wv6_kompakt_warnung_zuerst` (4/4 rot), z. B. „Warnung (Zeile 13) steht HINTER '== Metriken-Ueberblick ==' (Zeile 6)“.
- **Dateien:** `src/output/renderers/email/compact.py:189-220` (Überblick) vor `:222-238` (Warnblock + Ausfall-Hinweis).
- **Fix-Vorschlag:** Warnblock (Zeilen 222-238) direkt hinter den Kopf (nach `lines.append("")` Zeile 186) verschieben, analog `_warn_block_lines` im Klartext; Fallliste `fallliste_trip.json` um `trip-wv6--*--kompakt` ergänzen (heute nur html/klartext), Test `test_wv6_amtliche_warnung_zuerst` um Kompakt erweitern.
- **Einordnung:** innerhalb Spec/Konzept (kein Zielkonflikt).

## B-TM2 – Wieder eingeschaltete Metrik landet in der Mail an alter Stelle statt „hinten angehängt“

- **Schwere:** niedrig.
- **Soll:** `docs/specs/modules/feat_2794_s3a_teil3_wetter.md` AC-19: nach „−“ und „+ Wind“ „taucht [Wind] wieder auf (hinten angehängt)“; Konzept §5 Punkt 6 „steht in allen Listen“.
- **Ist:** `tripMetriken()` hängt den wieder eingeschalteten Eintrag ans **Array-Ende**, übernimmt aber seine alten Felder inkl. `order`. Die Mail sortiert nach `order` (`models._sorted_by_layout`), die Metrik steht also wieder an ihrer alten Position (z. B. `gust, uv_index, temperature, wind` statt `gust, temperature, wind, uv_index`). Eine wirklich neue Metrik (Eintrag ohne `order`) landet korrekt hinten.
  Die Liste „Inhalt je Kanal“ sortiert ebenfalls nach `order` (`metricsEditor.ts:400`), zeigt also dasselbe wie die Mail; abweichend ist nur der Wetter-Reiter (Array-Folge).
- **Repro:** `test_probe_render.py::test_r1_hub_neue_metrik_hinten[wieder_an-html|klartext]` (rot), `[neu_ohne_order-*]` grün.
- **Dateien:** `frontend/src/lib/components/shared/wetter-tab/ampelSchreiben.ts:63-75` (Zeile 71 `liste.push({ ...klon(e), enabled: true })`).
- **Fix-Vorschlag:** beim Wiedereinschalten `order` auf `max(order der aktiven)+1` (Bucket `primary`) setzen; Frontend-Test + Mail-Kettentest mit dieser Speicherform.
- **Einordnung:** innerhalb Spec (AC-19); Bereich Editor, Auswirkung in der Mail. Klären, ob „hinten“ für alle Listen gelten soll (Konzept sagt „steht in allen Listen“, nicht wo) – sonst Zielkonflikt Wetter-Reiter ↔ Kanal-Liste.

## B-TM3 – Testlücke: Schalter „Amtliche Warnungen“ (W20) beim Trip-Briefing ungeschützt

- **Schwere:** mittel (sicherheitsrelevanter Schalter, Verhalten heute korrekt).
- **Soll:** CLAUDE.md „Adversary + Mutations-Gegenprobe“: eine Verfälschung, die kein Test fängt, ist ein Finding; Konzept §5 Punkt 7 (W20+A1).
- **Ist:** Mutation M6 (`trip_report_scheduler.py:1767` `if trip.official_alerts_enabled is not False:` → `if True:`) überlebt den Prüfkatalog, 16 Bestands-Testdateien rund um die Einstellung und 4 gezielt gesuchte Warnungs-Testdateien (`test_issue_1087_trip_official_alerts.py`, `test_vorschau_anzeige_folgen_ortszone.py`, `test_versandpfade_folgen_ortszone.py`, `test_kanaltreue_adhoc_antwort.py`). Nur das eigene Prüfskript fängt sie.
- **Repro:** `test_probe_scheduler.py::test_w20_abruf_gesperrt` (grün im Ist; rot unter M6); `mutationen.py 6`, `nachlauf.py`.
- **Fix-Vorschlag:** Kettentest Zeitplaner-Weg (Muster `test_probe_scheduler.py`: echter `_send_trip_report_outcome`, Naht nur an `_fetch_weather` und am Warnungsabruf) mit `official_alerts_enabled` an/aus, HTML/Klartext/Kompakt, in die Fallliste aufnehmen.
- **Einordnung:** innerhalb Spec (AC-14 Mutations-Gegenprobe).

## B-TM4 – Hinweis (keine Fehlwirkung): Prüfkatalog umgeht zwei render-wirksame Weichen

- **Schwere:** niedrig (Restrisiko).
- **Ist:** `render_trip_mit_ausblick` baut den Ausblick immer und ruft den Zeitplaner nicht; das Gate „Erscheint im Morgen/Abend“ (`multi_day_trend_reports`, Resolver `report_config_resolver.py:157`) und das Tagesfenster (`trip_report.py:118-121`) prüft der Katalog nicht. M1, M5, M13 bleiben im Katalog unbemerkt; gefangen nur von `test_report_config_render_contract.py` (M1, M5) bzw. `tests/integration/test_config_persistence.py` (M13, Loader-Ebene), nicht an der zugestellten Mail. Das Verhalten selbst ist korrekt (eigene 20 Zeitplaner-Fälle + 3 Tagesfenster-Fälle grün).
- **Fix-Vorschlag:** `test_probe_scheduler.py::test_ausblick_erscheint_im` und `test_probe_render.py::test_r5_tagesfenster_wirkt` als Fälle in den Katalog übernehmen.

## Keine Befunde (geprüft, korrekt)

Grundauswahl Auswahl/Folge, E-Mail-Liste (an/aus, Folge, Roh/Einfach je Liste gegen globale Einstellung in beide Richtungen), Kanal-Liste je Bericht, Morgen/Abend je Metrik (Stunden + Ausblick + Kompakt), Ausblick (Auswahl, Folge, Roh/Einfach, bewusst leer), „Erscheint im“ 5 Varianten × Morgen/Abend × Voll/Kompakt, `show_outlook`, Zusatzblöcke, `email_format`, Tagesfenster (Kopf-Einzeiler und Überblick „ab 04:00“ → „ab 10:00“ in allen drei Formaten), Vorlage (`ampel.template` und Altform `preset_name`: allgemein → orange, wandern → gelb; Kompakt `!!`/`!`, Schwelle >30/>40), Ampel-Abweichung je Metrik, Sprache EN (keine deutschen Reste außer Fixture-Etappennamen; „Gust/Temp/Rain“ in DE sind col_label-Protokoll-Token, bewusst unübersetzt; Fuß Generated/Data = #3074), zwei Nutzer DE/EN ohne Vermischung.
Kompakt-Überblick folgt der E-Mail-Liste (Auswahl und Folge).

---

## Mutationen (16 + Nachlauf)

Lauf je Mutation: A = Prüfkatalog `test_einstellung_gleich_mail_trip.py`; B = 16 Bestandsdateien (Liste in `mutationen.py`); P = eigene Prüfskripte (abzüglich der 6 Basis-Roten). Sicherungskopie in `trip_mail/backup/`, nach jedem Lauf Byte-Vergleich + `git diff --stat` leer (Worktree am Ende sauber, `git status` leer). Rohdaten: `trip_mail/mutationen_ergebnis.json`, `nachlauf_ergebnis.json`.

| Nr | Datei | Ersetzung | gefangen | von |
|---|---|---|---|---|
| M1 | `services/report_config_resolver.py` | `show_multi_day_trend=report_type in trend_reports` → `True` | ja (A nein) | B `test_report_config_render_contract::test_effective_field_changes_output[multi_day_trend_reports]`; P `test_ausblick_erscheint_im` |
| M2 | dto. | `show_outlook=report_config.show_outlook` → `True` | ja | A `test_ausblick_ausgeschaltet[html,klartext]`; B render_contract |
| M3 | `output/renderers/trip_report.py` | `if not options.show_yesterday_comparison:` → `if False:` | ja | A `test_ac9_zusatzblock_aus[vortag]`; B render_contract |
| M4 | dto. | `if night_weather and dc.show_night_block:` → `if night_weather:` | ja | A `test_ac9_zusatzblock_aus[nachtblock]`; B `test_preview_night_block` |
| M5 | dto. | Tagesfenster → `resolve_configured_window(None, None)` | ja (A nein) | B render_contract `[day_window_*]`; P `test_r5_tagesfenster_wirkt` |
| M6 | `services/trip_report_scheduler.py` | `if trip.official_alerts_enabled is not False:` → `if True:` | **nein** (nur P) | nur `test_probe_scheduler::test_w20_abruf_gesperrt` → B-TM3 |
| M7 | `app/models.py` | `elif mc.morning_enabled is False:` → `elif False:` | ja | A `test_ein_aus_metrik_je_bericht[morgen_aus]`, `test_f007_*`; B `test_trip_metric_cascade_single_source` |
| M8 | dto. | `_sorted_by_layout` ohne `mc.order` | ja | A 65 Fälle (paarweise, ac2, ac3 …); B `test_einstellung_gleich_auslieferung` |
| M9 | `app/ampel.py` | `if abo and abo.get("template"):` → `if False:` | ja (A, B nein) | Nachlauf: `test_migration_2792_profil_ampel`, `test_2794_teil3_auswahl_paritaet` (39 Fälle, Unit-Ebene); an der Mail nur P `test_r7_vorlagenwechsel_wirkt` |
| M10 | `output/renderers/trip_report.py` | `build_friendly_keys(dc)` → `(_dc_uncollapsed)` | nein | äquivalente Mutante in den geprüften Flächen (Roh/Einfach der Mail kommt aus `format_modes`/`indicator_keys` der kollabierten dc; R3-Probe bleibt grün). Kein Befund, Hinweis: Feld wirkt in der Mail nicht sichtbar |
| M11 | `output/renderers/email/compact.py` | Überblick `sorted(resolve_trip_active_metrics(...))` | ja (A nein) | B `test_channel_metric_matrix::test_ac_s7_6_kurz_email_pillen_folgen_der_eingestellten_reihenfolge`, `test_briefing_compact_plain_sprache` |
| M12 | dto. | Kompakt-Kopf `_report_heading(..., "de")` | ja (A nein) | B `test_briefing_compact_plain_sprache::test_ac1_*`; P `test_r6_*[kompakt]` |
| M13 | `app/loader.py` | `multi_day_trend_reports=["evening"] or rc_data.get(...)` | ja (A, B nein) | Nachlauf `test_config_persistence::TestReportOptionsMigration` (Loader-Ebene); an der Mail nur P `test_ausblick_erscheint_im` |
| M14 | `compact.py` | `if outlook_metrics != []:` → `if True:` | ja | A `test_n1_bewusst_leer_kein_ausblick[*--kompakt]` |
| M15 | `trip_report.py` | `resolve_trip_outlook_metrics(_dc_uncollapsed, "evening")` | ja | A `test_ein_aus_metrik_je_bericht`, `test_f007_*` (14); B `test_trip_outlook_dispatch_mail` |
| M16 | `app/loader.py` | Kanal-Layout `use_friendly_format=ch_friendly` → `False` | ja | A paarweise darstellung (6); B `test_einstellung_gleich_auslieferung` |

Ergebnis: 14 von 16 gefangen (M6 überlebt alles = B-TM3; M10 äquivalent). Der Prüfkatalog selbst fängt 9 von 16; blind ist er für Ausblick-Gate (M1, M13), Tagesfenster (M5), W20 (M6), Vorlage (M9) und Kompakt-Überblick/-Sprache (M11, M12) – dort fangen andere Bestandstests außer bei M6.
