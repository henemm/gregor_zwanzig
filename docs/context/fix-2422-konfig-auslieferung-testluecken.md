# Context: fix-2422-konfig-auslieferung-testluecken

## Request Summary

Issue #2422 (PO, bug, priority:high): Eine im Trip-Editor eingestellte Kanal-Konfiguration kam
nicht so an, wie eingestellt — und **kein Test hat es gemerkt**. Auftrag: alle Testlücken
„Einstellung → Auslieferung" finden und schließen, nicht nur das Beispiel.

PO-Entscheidungen im Gespräch (2026-09-25/26):
- „Telegram im Kurzstil folgt dem SMS-Tab" ist **in Ordnung** (bleibt so, #1260).
- Wichtigste Frage des PO: **„WARUM SIEHT DAS KEIN TEST?"** — Primärauftrag ist, jede relevante
  Funktionalität mit einem Test abzudecken, der misst, was ankommt.
- Zugesagte Richtung: EIN Invarianten-Test „Einstellung = Auslieferung" über alle wählbaren
  Metriken × alle Kanäle, Einstieg über das Persistenzformat des Editors, Prüfung am an den
  Transport übergebenen Text; seine roten Stellen sind die belegte Lückenliste. Dazu
  „Editor-Anzeige = gespeicherter Stand".

## Das Beispiel (Trip `5f534011` „KHW 403", Nutzer henning, Prod, nur gelesen)

- `report_config.telegram_style = "kurzform"`, `send_sms = false`, Abendversand 17:00.
- Ausgeliefert 2026-09-25 17:03 (Telegram): `E3: W- WD:N G24@5(27@10) R- PR- TH:- TH+:- SU12`
  („E3" = `Trip.numbered_stage_label()`, `src/app/trip.py:294-310`, morgige Etappe).
- Gespeichert (Stand nach Save 2026-09-26 06:13; davor letzter Save 2026-09-24 20:48, also
  kein Save zwischen Screenshot und Versand):
  - `channel_layouts.telegram` aktiv: wind_chill 0, wind 1, wind_direction 2, gust 3,
    precipitation 4, rain_probability 5, thunder 6, visibility 7, cloud_total 8, …
  - `channel_layouts.sms` aktiv: wind_chill 0, wind 1, wind_direction 2, gust 3,
    precipitation 4, rain_probability 5, thunder 6, **sunshine 7**
  - Auslieferung = SMS-Layout 1:1 (Kurzstil sendet `report.sms_text`).
- Screenshot (Telegram-Tab) zeigte Böen an Pos. 7 → gespeichert heute Pos. 4. Code-Nachrechnung:
  Editor zeigt gespeicherte `order` treu → wahrscheinlich Umsortierung beim Save 06:13
  (Hypothese „Anzeige lügt" für diese Daten nicht reproduzierbar, „Save geht verloren" kein Pfad
  gefunden). Belastbar erst per Staging-Kopie.
- **Gefühlte Temperatur** (`wind_chill`, Pos. 1 in beiden Tabs) fehlt: kein Kurzform-Token
  (seit #1887 E6 Scheibe A; `src/app/metric_catalog.py:754-842`); nur die Kinder
  `wind_chill_day_low/_day_high/_night` (FL/FD/FN) tragen Kürzel — sie sind aus. Stiller Wegfall,
  Editor bietet die Metrik ohne Hinweis an.

## Befunde: Einstellung wirkt nicht / anders als angezeigt (belegt)

| # | Befund | Beleg |
|---|---|---|
| B1 | Kurzform/SMS/Premium: Metrik ohne Kürzel (`wind_chill`, `temperature`) im Layout aktiv → fällt still weg | `metric_catalog.py:792,840`; Editor `weather-metrics-tab/kuerzelMarken.ts` |
| B2 | Kurzform/SMS/Premium ignorieren Roh/Einfach — `MetricSpec` ohne `format_mode`/`use_friendly_format` (beobachtet: SMS-Layout cloud_total friendly → `CT85`) | `trip_report.py:376-421`; `output/tokens/dto.py:110`; `tokens/builder.py:142-153` |
| B3 | Telegram rich übernimmt Roh/Einfach aus dem **E-Mail**-Layout (`friendly_keys` aus email-kollabiertem `dc`) — beobachtet in beide Richtungen | `trip_report.py:142` → `:301`; `email/helpers.py:1226` |
| B4 | Telegram-Kurzstil: Telegram-Tab komplett wirkungslos, Editor sagt es nicht | `notification_service.py:667-677`; `trip_report.py:335` |
| B5 | Telegram rich: `wind_direction` im Skalenmodus + `wind` → Geisterspalte `WD` mit `–` | `email/helpers.py:72-90`; `trip_report.py:656-668` |
| B6 | Kanal-Layout kann nur abwählen (globales Maximum); im Kanal an, global aus → erscheint nicht | `models.py:993-1015` (ADR-0050, gewollt — Editor-Anzeige prüfen) |
| B7 | Editor ignoriert `bucket`, `morning_enabled/evening_enabled`, `channel_layouts_per_report` — Python beachtet sie → Anzeige ≠ Versand bei solchen Daten | `channelMetricLayouts.ts:42-64`; `models.py:753-766, 804-823`; `channel_layout.py:113-148` |
| B8 | `show_outlook` wirkt nur auf E-Mail (Schalter steht im Mail-Bereich, vermutlich gewollt; Beschriftung prüfen) | `trip_report.py:242`; kein Parameter in `narrow.py`/`sms_trip.py` |
| B9 | SMS-Nutzerposition wirkt nur bei Kaskadenquelle per_channel/per_report | `trip_report.py:341-346` |

B3 ist nutzersichtbar und eigenständig → eigenes Issue (Nebenbefund-Triage). AST-/`inspect.getsource`-
„Verhaltenstests" (z. B. `test_issue_434_per_report_layouts.py::test_ac7_*`,
`test_issue_435_format_modes.py::test_ac10_*`) → Sammel-Eintrag #1196.

## Warum kein Test es sah (Kern von #2422)

1. Zwei getrennte Testarten, nie verkettet: (A) Persistenz-Roundtrip über echten Loader, (B)
   Render mit handgebautem `UnifiedWeatherDisplayConfig`/`Trip`. Kein Test: Editor-Format →
   Loader → Formatter/Dispatch → an Transport übergebener Text.
2. Vorhandene Ende-zu-Ende-Vergleiche vergleichen Ausgabe mit Ausgabe
   (`test_telegram_kurzstil_trip_briefing.py::TestAC2…` Telegram == SMS byte-identisch;
   `test_sms_user_metric_order.py::test_ac11_*`) — beide falsch ⇒ grün.
3. Wegfall von `wind_chill`-Token abgesichert als „kein Kürzel", nie als „eingeschaltet ⇒
   erscheint oder sichtbarer Hinweis".
4. `test_channel_metric_matrix.py` (4878 Zeilen) prüft Zwischenschichten
   (`resolve_metric_col_order`, `get_metrics_for_channel`) — nicht den gesendeten Text.
5. Keine Kette Editor-Logik (`channelOverrideFromMetrics`/`splitChannelMetricsForDisplay`) ↔
   Python-Kaskade mit derselben Fixture. Playwright-Reorder+Reload nur im Email-Tab
   (`e2e/layout-tab-route.spec.ts:163-196`), kein Telegram/SMS-Reorder.

## Related Files

| File | Relevance |
|------|-----------|
| `src/app/loader.py:400,895,958-989,860-892` | `load_trip`, `_parse_display_config`, Kanal-Layouts, abgeleitete Metriken |
| `src/app/models.py:739-823,939-1015` | Kaskade `get_metrics_for_channel`, `_sorted_by_layout`, Maximum-Schnitt |
| `src/output/renderers/trip_report.py:63-459` | Formatter: E-Mail-/Telegram-/SMS-Zweig, friendly_keys, MetricSpecs |
| `src/output/renderers/narrow.py:66,76,697,782-852` | Telegram rich Bubbles, Kurzübersicht (zuverlässige Reihenfolge) |
| `src/output/renderers/channel_layout.py:46-148` | `CHANNEL_LIMITS`, `render_for_channel`, `VISIBILITY_GATE_IDS` |
| `src/output/renderers/sms_trip.py`, `src/output/tokens/{builder,render,dto,metrics}.py` | Kurzform-Tokens, Sortierung, 160er-Budget, DROP_ORDER |
| `src/output/renderers/email/helpers.py:72-104,311,1226-1284`, `email/html.py`, `email/plain.py` | E-Mail-Spalten, friendly |
| `src/app/metric_catalog.py:99,754-842,849,1061` | Katalog, Kürzel-Orakel `SMS_SYMBOL_BY_METRIC ∪ SMS_MULTI_SYMBOLS_BY_METRIC` |
| `src/services/notification_service.py:489-700,2104` | Versand je Kanal (Naht für Aufzeichnung) |
| `src/services/trip_report_scheduler.py:473,916,1077,1195,1726-1859` | Einstiege, Kanalflags |
| `frontend/src/lib/components/shared/weather-metrics-tab/WeatherV2Reihenfolge.svelte` | Anzeige Reihenfolge/Kappung/Roh-Einfach |
| `frontend/src/lib/components/shared/WeatherMetricsTab.svelte:336-359,450-513,773-1028,1716-1745` | Init, Edit, Auto-Save |
| `frontend/src/lib/components/shared/channelMetricLayouts.ts:42-129`, `trip-detail/metricsEditor.ts:232-236,336-370` | Anzeige-Ableitung, Save-Serialisierung |
| `frontend/src/lib/components/shared/TelegramKurzstilToggle.svelte:62` | Kurzstil-Hinweistext |
| `internal/handler/weather_config.go:55-122`, `config_merge.go:11-22` | PUT weather-config (channel_layouts ersetzt, order unverändert) |

## Existing Patterns / wiederverwendbare Test-Bausteine

- Transport-Naht: Klassen `EmailOutput`/`SMSOutput`/`PremiumSmsOutput`/`TelegramOutput` in
  `services.notification_service` per `monkeypatch` ersetzen — Vorlage
  `tests/tdd/test_kanaltreue_adhoc_antwort.py:88-225` (`_TRANSPORT_ENV`, `_nutzer_anlegen`,
  `_trip_anlegen`, Aufzeichner; Aufzeichner um `body`/`plain_text_body`/`parse_mode` erweitern).
  Alternative echte HTTP-Stubs: `test_telegram_kurzstil_trip_briefing.py:50-227`.
- Loader-Einstieg mit SMS-Text: `tests/tdd/test_sms_wind_chill_position_inherits_from_anchor.py:54-84`.
- Token-Parser: `test_sms_user_metric_order.py:121-160` (`_token_index`, `_present`);
  Ausnahmemengen `test_channel_metric_matrix.py:155-190`; Compare-Parser `tests/helpers/compare_order.py`.
- Wetter: `fixtures/openmeteo/*.json` via `GZ_TEST_FIXTURE_DIR` (conftest:70-86) — Lücken bei
  humidity, dewpoint, pressure, wind_chill_c, cloud_mid/high, precip_type, snow_new_24h →
  synthetisch `tests/tdd/_min_temp_felt_fixtures.py`.
- Trip-JSON mit Kanal-Layouts: nur `tests/fixtures/metric_cascade/khw_display_config_widerspruch.json`.
- Frontend: `node --test` (kein Vitest); Anzeige-Logik ist reine TS-Funktion → gleiche Fixture
  in TS und Python prüfbar.

## Dependencies

- Upstream: Metrik-Katalog, Kaskade (ADR-0050), Token-Register, Provider/FixtureProvider.
- Downstream: alle vier Kanäle, Trip-Briefing; Ortsvergleich hat eigene Auswahl
  (`display_config.channel_active_metrics`, `report_config_resolver.py:300-339`,
  `comparison.py:692`, `send_compare_report` mit eingebauten Sinks) — keine Darstellung je Kanal,
  kein Kurzstil/Premium im Vergleich.

## Existing Specs / ADRs

- `docs/specs/modules/feat_1260_telegram_kurzstil.md` (Kurzstil = SMS-Text, bleibt)
- ADR-0050 Metrik-Kaskade (Verfeinerung, nicht Ersetzung), ADR-0014 Telegram-Multi-Bubble,
  ADR-0042 Namensform folgt Platzgrenze
- `feat_2207_kurzform_verlauf.md`, `fix_1482_th_plus_metrik_luecke.md`

## Strukturelle Ausnahmen (Testorakel muss sie kennen)

Globales Maximum (B6) · Kurzstil/Premium ← SMS-Layout · 160er-Budget mit DROP_ORDER (Teilmengen
oder `render_line_with_survivors` als Orakel) · L+D→`D x/y`, FL+FD zusammengezogen, N/FN nur
abends · 6 `VISIBILITY_GATE_IDS` ohne Stundenspalte · Telegram-Tabelle max 7, Rest in
Kurzübersicht · `horizons` und morning/evening in E-Mail · `email_format=compact` ohne
Stundentabelle · friendly nur bei `has_friendly_format` · FixtureProvider-Lücken.
Jede Ausnahme muss entweder im Produkt **sichtbar** gemacht werden (Editor-Hinweis) oder ist ein
Defekt — „still weg" ist nie korrekt.

## Risks & Considerations

- **Parallel-Sitzung #2417** ändert uncommittet `notification_service.py`, `trip_selection.py`,
  `inbound_*_reader.py`, `channels/telegram.py`, `trip_report_scheduler.py` → vor `/50`
  per `SendMessage` an `gregor-zwanzig-15` abstimmen bzw. auf deren Merge aufsetzen.
- Test ist anfangs breit rot → Scheibenschnitt nötig (LoC-Limit 250/Workflow; Tests zählen nicht
  produktiv). RED-Tests lassen sich nicht committen (Memory).
- Kein Mock-Theater: Naht nur am Transport; Loader/Kaskade/Formatter echt.
- Herkunftssperre im Worktree (`app/origin_guard.py`): Nutzerkennung ohne „test"/„tdd",
  `telegram_test_chat_id`, SMS-Sandbox-Key; `sms_verified_number` Pflicht (#2406).
- KHW 403 nie anfassen; Verifikation nur am Staging-Test-Trip bzw. Staging-Kopie.
- Offene Punkte für Analyse: Alarm-Familie (Schwellen, Radar/Regen, amtliche Warnungen) noch nicht
  auditiert; Kanal an/aus, Empfänger, Versandzeiten, Erwähnungsschwellen `sms_threshold`,
  `email_format` ohne verkettete Kette.

## Analysis

### Type
Bug (Testlücke mit nutzersichtbaren Folgen): Einstellung im Trip-Editor ≠ Auslieferung, kein Test misst die Kette.

### Ergänzende Lücken (Phase 2, über B1–B9 hinaus)

| # | Bereich | Befund | Code-Ort |
|---|---|---|---|
| L1 | Alarm-Familie (Schwellen, Radar/Regen, amtliche Warnungen) | `AlarmPruefstrecke`-Tests (`test_alarm_szenario_ein_ereignis_ein_alarm.py:276-354`) bauen den Trip im Speicher — keine Kette gespeichertes JSON → Loader → Kanal-Auflösung → Transport | `trip_report_scheduler.py:1771-1780`, `notification_service.py:619,642,664` |
| L2 | Kanal an/aus im Slot-Briefing | nur On-Demand bewacht (`test_kanaltreue_adhoc_antwort.py`), nicht der reguläre Morgen-/Abendversand | `trip_report_scheduler.py:1771-1780` |
| L3 | `email_format=compact`, `morning_enabled`/`evening_enabled`, `sms_threshold` | kein Test Einstellung → Versand | `models.py:739-823`, `loader.py:860-892` |
| L4 | Ortsvergleich `channel_active_metrics` + Kanalwahl | keine Kette Vergleichs-JSON → `effective_compare_briefing_channels` → `send_compare_report` → Text | `compare_alert_channels.py:32-53`, `notification_service.py:1231-1340` |

### Bestätigte Code-Fakten (Plan-Agent)
- Kurzstil/SMS/Premium senden identisch `report.sms_text` (`notification_service.py:566,596,653,672`).
- B3 im Code bestätigt: `trip_report.py:142-145` — `build_friendly_keys(dc)` nach E-Mail-Kollabierung, Telegram rich erbt sie.
- Go-PUT `mergeConfigMap` (`config_merge.go:11-22`) ist top-level-shallow: `channel_layouts` wird als Ganzes ersetzt; das Frontend baut den vollständigen Baum (`channelMetricLayouts.ts:112-129`). Go-Test prüft: Teil-Body ohne `channel_layouts` lässt sie unverändert; mit `channel_layouts` wird exakt der gesendete Baum gespeichert.
- Kürzel-Orakel-Quellen: `SMS_SYMBOL_BY_METRIC`, `SMS_MULTI_SYMBOLS_BY_METRIC`, `SMS_SYMBOL_GRAMMAR` (`metric_catalog.py:772-842`), `COMPACT_LABEL_EXCEPTIONS` (~843). Das sind Register (Daten), keine Produktfunktionen — als Orakel-Wissen erlaubt.
- Aufzeichner in `test_kanaltreue_adhoc_antwort.py:139-176` zeichnet nur `subject` auf → Ausbau um `body`/`plain_text_body`/`parse_mode`.
- Kein fertiger Parser für Telegram-rich-Tabellenkopf und E-Mail-Spaltenreihenfolge — neu (Testcode).
- FixtureProvider-Lücken → neue synthetische Wetter-Fixture mit ALLEN Feldern, sonst wird die Matrix an Rohdaten statt an Konfig-Logik rot.

### Technical Approach (Empfehlung)

**Kern: Invarianten-Test „Einstellung = Auslieferung" mit Ausnahme-Ratsche.**
1. **Orakel = gespeicherte Einstellung.** Erwartung (aktive Metriken + Reihenfolge je Kanal) wird direkt aus dem Trip-JSON (`display_config.metrics`, `channel_layouts.<kanal>`) + Kürzel-Register + expliziter Ausnahmeliste abgeleitet. VERBOTEN als Orakel: `get_metrics_for_channel`, `resolve_metric_col_order`, `_sorted_by_layout` oder jede andere Produktfunktion (sonst wieder Ausgabe-gegen-Ausgabe, Ursache 2).
2. **Einstieg = Persistenzformat des Editors** (Golden-Trip-JSON), echter `load_trip`, echter Formatter/Dispatch; Naht NUR am Transport (`EmailOutput`/`SMSOutput`/`PremiumSmsOutput`/`TelegramOutput` per monkeypatch), Prüfung am übergebenen Text.
3. **Matrix:** alle wählbaren Metriken × E-Mail html · E-Mail plain · Telegram rich · Telegram Kurzstil · SMS · Premium-SMS; Dimensionen „erscheint", „Reihenfolge", „Roh/Einfach".
4. **Eine Golden-Datei, drei Beine:** TS (`node --test`: Editor-Serialisierung ergibt Golden; Editor-Anzeige aus Golden = gespeicherter Stand), Go (PUT-Merge erhält Golden), Python (Golden → Transport-Text). Staging-Kopie ist NICHT nötig (Staging-Daten für `hem` ohnehin nicht lesbar).
5. **Ausnahme-Ratsche:** Register `{metrik, kanal, dimension, befund(B-Nr./Issue), grund}`. Rot bei neuer Abweichung ohne Eintrag UND bei Eintrag, dessen Zelle inzwischen stimmt (veraltet). Zieht nur Richtung Schließung. Regel-Budget: **Prüfdatum +90 Tage** (2026-12-25) in `gates_und_ratschen.md` — NICHT `test_channel_metric_matrix.py` ersetzen (bewacht andere Zwischenschichten).
6. **Mutations-Pflichtfänge** (für Adversary `/50`): (M1) Sortkey in `_sorted_by_layout` invertiert → Reihenfolge rot; (M2) `_clip_to_global_maximum` lässt eine Metrik zusätzlich durch / droppt eine → Präsenz rot; (M3) `build_friendly_keys` aus falscher `dc` → Roh/Einfach rot; (M4) Formatter liest globale `dc.metrics` statt Kanal-Layout → Reihenfolge/Auswahl rot.

### Klassifikation der Befunde

| # | Kategorie | Behandlung |
|---|---|---|
| B1 | Produktentscheidung (AC-Variante in Spec) | V1: eigenes Kürzel für gefühlte Temperatur (Achtung: `WC` wurde wegen Dopplung mit `FK` entfernt, #1887) · V2: Editor-Hinweis „erscheint in SMS/Kurzform nicht". Empfehlung V2 |
| B2 | Fix (eigene Scheibe) | `format_mode` in Kurzform/SMS/Premium-MetricSpec |
| B3 | eigenes Issue | Telegram rich Roh/Einfach aus E-Mail-Layout — nutzersichtbar, eigenständig |
| B4 | Editor-Hinweis (Scheibe) | Telegram-Tab bei Kurzstil sichtbar als wirkungslos kennzeichnen; Verhalten bleibt (#1260) |
| B5 | Fix (eigene Scheibe) | Geisterspalte `WD` |
| B6 | gewollt (ADR-0050) → Register + Editor-Anzeige prüfen | |
| B7 | Editor-Hinweis (Scheibe) — höchstes Wiederholungsrisiko | Anzeige ≠ Versand bei `bucket`/morning/evening/`channel_layouts_per_report` |
| B8 | gewollt → Register, Beschriftung prüfen | |
| B9 | strukturelle Ausnahme → Register + Kaskadenquelle im Editor zeigen | |
| L1–L4 | eigene Test-Scheiben (Kette JSON → Transport) | Alarme, Kanal an/aus + Versandzeiten + Format + Schwelle, Ortsvergleich |

### Scheibenschnitt (Vorschlag für Spec)

| Scheibe | Inhalt | LoC prod / Test |
|---|---|---|
| **S1 (dieser Workflow)** | Golden-Trip-JSON + synthetische Voll-Wetter-Fixture + Aufzeichner-Ausbau + Kürzel-/Parser-Orakel + Python-Invariante Metriken×Kanäle + Ausnahme-Register (anfangs mit allen belegten Lücken B1–B9 befüllt, jede rote Zelle belegt) | ~0-20 / ~500 |
| S2 | TS-Bein (Editor-Serialisierung + Anzeige ↔ Golden) + Go-Bein (PUT-Merge ↔ Golden) | 0 / ~300 |
| S3 | Kette Kanal an/aus, Versandzeiten, `email_format`, `sms_threshold` (L2/L3) | 0 / ~200 |
| S4 | Kette Alarm-Familie JSON → alle vier Kanäle (L1) | 0 / ~250 |
| S5 | Kette Ortsvergleich (L4) | 0 / ~200 |
| S6+ | Fixes B2, B5; Editor-Hinweise B4/B7/B9; B1 nach PO-Variante — je eigene Scheibe, jede entfernt ihre Register-Einträge (Ratsche) | je 60-150 prod |

Reihenfolge: S1 → (S2 ∥ S3 ∥ S4 ∥ S5) → Fixes. Umsetzung als Sammel-Issue mit Unter-Issues je Scheibe (#2422 bleibt Dach).

### Scope Assessment (S1)
- Dateien: ~5 neu (Test, Register, Golden-JSON, Wetter-Fixture, Parser-Helfer), 1 geändert (Aufzeichner als geteilter Helfer extrahieren) + `gates_und_ratschen.md` (Prüfdatum)
- Produktiv-LoC: ~0-20 · Test-LoC: ~500
- Risiko: MITTEL — kein Produktverhalten geändert, aber Orakel-Konstruktion entscheidet, ob der Test überhaupt etwas bewacht

### Dependencies / Risiken
- **Parallelsitzung #2417** ändert `notification_service.py`/`trip_report_scheduler.py` (noch nicht in `origin/main`, Stand 2026-09-26). S1 setzt die Naht nur per monkeypatch der Output-Klassen → Konfliktfläche klein; vor `/50` per `ListAgents`/`SendMessage` abstimmen.
- Herkunftssperre `app/origin_guard.py:29-34`: Worktree = Testmodus; Nutzerkennung ohne „test"/„tdd", `sms_verified_number` Pflicht (#2406).
- RED-Tests nicht committbar → S1 ist grün MIT Register (rote Zellen = Register-Einträge); RED-Nachweis = Test ohne Register bzw. Mutationen M1–M4.
- KHW 403 nie anfassen.

### Open Questions (für Spec, nicht an PO als Technikfrage)
- [ ] B1: Variante V1 (Kürzel) vs. V2 (Editor-Hinweis) → als AC-Varianten zur Freigabe
- [ ] Spec-Umfang: nur S1 im Detail, S2–S6 als Unter-Issues anlegen
