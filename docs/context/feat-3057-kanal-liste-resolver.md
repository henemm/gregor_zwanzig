# Context: feat-3057-kanal-liste-resolver

> **Hinweis (2026-11-17, [ADR-0124](../adr/0124-was-steht-wo-eine-tabelle.md), Issue #3122):** Diese Notiz ist Historie eines gebauten Schritts. Wo sie die Karte „Inhalt je Kanal und Fläche“ (eigene Liste je Kanal und Fläche, #3031–#3037, PR #3042, #3060) als künftiges Soll nennt, gilt das nicht mehr: ADR-0124 (PO 2026-11-17) ersetzt die Karte durch **eine** Tabelle „Was steht wo“ im Reiter Wetter. Aktueller Stand: ADR-0124 und `docs/context/einstellungen_neu.md`. Das gespeicherte Format (ADR-0121) wird mit dem Bau zu #3122 neu geschnitten.

Issue #3057 (Phase 2 von Epic #3047 „Einstellung = Mail“). Phase 1 (#3056, Prüfkatalog) ist ausgeliefert; ihr Katalog ist die Messlatte.

## Request Summary

Eine kanonische Kanal-Liste (Metrik, Reihenfolge, an/aus, Roh/Einfach) je Kanal und Fläche für Trip und Orte, mit Lese-Adapter und Migration der Bestandsdaten (Read-Modify-Write), und ein gemeinsamer Resolver bzw. Mail-View-Model, aus dem Editor und Renderer lesen. Braucht eigene Spec und ADR (nächste freie Nummer: ADR-0121). Umstellung der Kanäle (Phase 3), Zusatzblöcke (Phase 4) und UI (Phase 5) sind NICHT Teil dieser Phase.

Konzept: `docs/context/einstellungen_neu.md` §5 Punkt 6 und 8 (Karte „Inhalt je Kanal und Fläche“: Segment E-Mail · Telegram · SMS · Premium-SMS · 3-Tages-Ausblick · (Orte) Stundenverlauf; jede Liste nimmt nur aus der Grundauswahl, kann abwählen, nicht hinzufügen; je Zeile Roh/Einfach).

## Ist-Datenmodell

### Trip (`display_config`, Python `UnifiedWeatherDisplayConfig` src/app/models.py:825; Go ungetypte Map internal/model/trip.go:121; TS frontend/src/lib/types.ts:253-351)
- `metrics: [MetricConfig]` (models.py:672): `metric_id`, `enabled`, `morning_/evening_enabled`, `use_friendly_format` (veraltet), `format_mode` (raw|simplified|None=Katalog-Standard), `bucket`, `order`, `sms_threshold`, `horizons`, `derived` (nicht persistiert).
- `channel_layouts{kanal:[MetricConfig]}` → Modell `per_channel_layouts` (:846). None = erbt global, [] = leer.
- `channel_layouts_per_report{morning|evening:{kanal:[…]}}` → `per_report_layouts` (:850).
- `outlook_metrics` (:869): None = Grundauswahl erben, [] = Block entfällt, gefüllt = Folge. `outlook_metric_formats {id: bool}` (:877), fehlend = Roh.
- Dazu `sms_metrics` (veraltet), `show_night_block`, `night_interval_hours`, `telegram_kurzform`.

### Orte (`ComparePreset` models.py:1328; Go internal/model/compare_preset.go:48/66/71; display_config freie Map)
- `active_metrics` (Strings oder `{metric_id, aggregation}`), None = kein Filter.
- `channel_active_metrics{email|telegram|sms:[…]}`.
- `channel_layouts{kanal:[{metric_id, enabled, use_friendly_format}]}` (ADR-0119), Vorrang vor `channel_active_metrics`; fehlendes Format = **Roh** (Trip: Katalog-Standard!).
- `hourly_metrics` (None = 9 Vorgabe-Spalten `HOURLY_DEFAULT_METRIC_IDS`, [] = leer), kein Roh/Einfach.
- `outlook_metrics`, `outlook_metric_formats` wie Trip. Top-Level `hourly_enabled`, `outlook_enabled` (fehlend = True).
- Orte-Editor schreibt `channel_layouts` noch nicht (nur erhalten, pickEigenfelder.ts:79).

## Ist-Resolver (Python)

Trip:
- `get_metrics_for_channel` (models.py:941), Kaskade per_report → per_channel → global ∩ Grundauswahl (`_cascade_source_for_channel` :777). Aufrufer trip_report.py:140 (E-Mail), :292 (Telegram), :355 (SMS); notification_service.py:608/638 (Alarm).
- `_effective_format_mode` (email/helpers.py:50) → `loader._resolve_format_mode` (loader.py:62).
- `resolve_metric_col_order` (helpers.py:305) für html.py:873, plain.py:193.
- `resolve_trip_active_metrics` (trip_metric_ids.py:37) für html.py:1289, plain.py:243, compact.py:196.
- Nachtblock `_aggregate_night_block` (trip_report.py:572) nutzt E-Mail-Liste.
- Ausblick `resolve_trip_outlook_metrics`/`_formats` (compare_outlook_metric_ids.py:197/272); `build_outlook_row` (outlook.py:524) aus trip_report_scheduler.py:3076. Ausblick ohne Kanal-Ebene.

Orte:
- `resolve_compare_render_options` (services/report_config_resolver.py:257) → `CompareRenderOptions` (:164) mit `enabled_metrics_by_channel`, `channel_rows_by_channel`, `metric_formats(kanal)` (:234). Kanäle email/telegram/sms; Premium-SMS nutzt SMS-Text (ADR-0049).
- Kaskade `resolve_channel_layout_rows` (compare_metric_ids.py:350, `_friendly_effective` :335) → `resolve_channel_enabled_metrics` (:251) → `resolve_enabled_metrics(_report)` (:195/:170).
- Stundenverlauf `resolve_hourly_metrics` (compare_hourly_metric_ids.py:167), `_visible_hour_metrics` (email/compare_html.py:1071).
- Ausblick `resolve_compare_outlook_metrics`/`_formats` (:231/:289), gemeinsam mit Trip `_erbe_grundauswahl` (:151), `outlook_columns` (:305).
- Aufrufer scheduler_dispatch_service.py:981-1080, compare_preview_service.py:74-182.

## Frontend

- Trip: `WeatherMetricsTab.svelte` (:482 lesen, :924-949 schreiben; `channel_layouts` wird ganz ersetzt); Hilfen in `frontend/src/lib/components/shared/weather-metrics-tab/` (`channelMetricLayouts.ts` :71/:104/:166/:217, `weatherMetricsSavePayload.ts`); Standardfolge `trip-detail/metricsEditor.ts` (`METRIC_PRIORITY` :208).
- Orte: `compare/compareEditorSave.ts:133` (RMW, [] explizit), Hydration `weatherMetricsCompareSave.ts`, `compare/compareHubHydration.ts:51`; gespiegelte Standards `DEFAULT_OUTLOOK_METRIC_KEYS` (compareMetricOrder.ts:37), `HOURLY_DEFAULT_FOLGE` (CompareHourlyLayoutControls.svelte:100); `OutlookLayoutControls.svelte:204`.

## Go-API

Reicht die Felder ungeprüft durch (ADR-0077). Geprüft nur `ampel` und Wachstumsgrenze 200 Schlüssel (wachstumsgrenzen.go:27). `mergeConfigMap` (config_merge.go:11) nur oberste Ebene (Unterschlüssel komplett ersetzt). Orte `applyComparePresetPatch` (compare_preset.go:328) feldweise eine Ebene tiefer. `displayConfigAusVorlage` (metric_preset.go:97) erzeugt Trip-`metrics` mit order/bucket, Orte nur `ampel`.

## Loader / Migration

loader.py: `_resolve_format_mode` :62, `_normalize_legacy_mode` :772, `_coerce_metric_entry` :895, `_append_derived_metrics` :924, `_parse_display_config` :972-1127, `_metric_to_dict` :153, Trip-Serialisierung :1862-1892, `compare_preset_from_dict` :250 (trägt `raw` mit), `_migrate_preset_display_config` :815 (nur Alarmstufen).

## Existing Specs / ADRs

- Spec Phase 1: `docs/specs/modules/feat_3047_einstellung_gleich_mail_pruefkatalog.md` (Ausblick Phase 2–5 ab Z. 222).
- ADRs: 0037 (Ausblick datengetrieben), 0049 (Premium-SMS sendet SMS-Text), 0050 (Kaskade verfeinert, Grundauswahl = Maximum), 0053 (Orte Auswahl je Kanal), 0055 (Trip-Ausblick wählbar), 0059 (Ausblick erbt Grundauswahl), 0068 (`col_label`), 0077 (Kanal-Schicht Top-Level-Map, Go ungeprüft), 0095 (Kanal-Parität), 0097 (Trip/Orte teilen Code), 0101 (RMW-Migration), 0119 (Orte `channel_layouts`, Default Roh).

## Prüfkatalog (Messlatte)

- Fallisten `tests/fixtures/einstellung_gleich_mail/fallliste_{trip,orte,editor,validatoren}.json` + Fixtures.
- Tests `tests/tdd/test_einstellung_gleich_mail_{trip,orte,fallliste,editor_standard,validatoren}.py`, `test_einstellung_gleich_auslieferung.py`, `test_compare_einstellung_auslieferung_kette.py`, `test_compare_alarm_einstellung_auslieferung_kette.py`; Helpers `tests/helpers/einstellung_gleich_mail_{trip,orte}.py`, `einstellung_auslieferung_orakel.py`, `transport_mitschrift.py`, `vergleichs_mail_fixture.py`.
- Frontend `weather-metrics-tab/__tests__/editor_standard_gleich_mail.test.ts`, `editor_{aenderung,anzeige}_gleich_erwartung.test.ts`.

## Divergenzen, die die kanonische Liste auflösen muss

1. Fehlendes Format: Orte Roh, Trip Katalog-Standard.
2. Orte zwei parallele Kanalfelder (`channel_layouts` vor `channel_active_metrics`); Trip ein Feld + per_report-Ebene.
3. Stundenverlauf (Orte) ohne Roh/Einfach; Trip hat keine eigene Stundenverlauf-Liste (Haupttabelle ist Stundentabelle).
4. Premium-SMS ohne eigene Liste (Konzept S9 #2801 sieht eigene Liste vor; ADR-0049 sagt heute: SMS-Text).
5. Ausblick-Format als `{id: bool}`-Map statt je Zeile; Ausblick ohne Kanal-Ebene.
6. Standardfolgen dreifach (Python `HOURLY_DEFAULT_METRIC_IDS`, TS `HOURLY_DEFAULT_FOLGE`, `DEFAULT_OUTLOOK_METRIC_KEYS`, `METRIC_PRIORITY`).
7. Produktfrage O1 aus #3047: eine gemeinsame Reihenfolge über Flächen oder je Fläche eigene Folge (Konzept §5.8: je Liste eigene Folge).

## Risks & Considerations

- **Parallele Arbeit:** #3048 (Trip-Altbestand ohne `display_config.metrics`) und #3052 laufen in einem anderen Fenster und berühren Trip-Resolver/Loader. Vor Implementierung gegen `origin/main` neu abgleichen.
- Daten-Schema-Rework: RMW mit Merge, Pre-Snapshot-Hook, zwei Nutzer je datenbewegendem Endpoint (CLAUDE.md).
- Go-`mergeConfigMap` ersetzt Unterschlüssel komplett: neue verschachtelte Struktur darf beim Teil-Speichern nichts verlieren.
- Alte Felder werden in Phase 2 noch gelesen (Altpfade entfallen erst in Phase 3); Lese-Adapter muss beide Welten verlustfrei abbilden.
- Alarm-Pfad (notification_service) nutzt dieselbe Kanal-Kaskade: Kanal-Parität (ADR-0095).
- Umfang: Phase 2 muss so geschnitten werden, dass sie ohne Phase 3 auslieferbar ist (Resolver neu, Renderer noch alt oder per Adapter gespeist), sonst entsteht wieder eine Übergangsschicht ohne Contract-Phase (Retro #3047).

## Laufender Umbau rund um Epic #3047 (Stand 2026-11-16 06:10)

- **Phase 1 (#3056)** live (Prod 4b5e8749f), Staging-Validatoren mit `--konfig` bestanden. Teile davon kamen aus einer Cloud-Sitzung (PRs #3051, #3055, Zweig `claude/zustellung-email-darstellung-bv1ifa`, gemerged).
- **Unabhängige Nachprüfung (Kommentar 05:58, AMBIGUOUS)**, offene Punkte, die Phase 2 strukturell erschlagen soll bzw. nicht verschärfen darf:
  1. Orte-Stundenverlauf: Mail schneidet `hourly_metrics` mit der Grundauswahl (report_config_resolver.py:308-311 → compare_hourly_metric_ids.py:211), Editor nicht; Validator `_soll_aus_konfiguration.py:247` ebenfalls ohne Schnitt.
  2. Trip ohne `display_config.metrics` (= #3048, läuft im Nachbarfenster).
  3. Nie eingestellter Orte-Stundenverlauf ignoriert Grundauswahl (feste `HOURLY_DEFAULT_METRIC_IDS`); Soll laut Konzept §5.8: Schnitt Grundauswahl ∩ stündlich verfügbar in Standardfolge.
  4. Validator Ortsfolge bei rohem Preset still übersprungen (`_soll_aus_konfiguration.py:279`).
  5. `briefing_mail_validator --konfig` wertet Roh/Einfach nicht aus.
  6. Mutation `morning_enabled=False` (models.py:751-757) überlebt.
  7. Global zugeschaltete Metrik erreicht bearbeitete Listen nur beim nächsten Editor-Speichern; Backend hängt nur bei `channel_layouts` an. → Kandidat für den kanonischen Resolver (Anhängen beim Lesen).
  8. Veralteter Kommentar comparison.py:257-258; kein Drift-Wächter für eingefrorene Frontend-Kataloge.
- **Befunde #3063/#3064** (Telegram-Kopf „Evening“, Windrichtung-Roh in Telegram, englische Briefing-Art) neu angelegt; #3048+#3052 laufen gebündelt im Nachbarfenster (Phase 6).
- **#3039** (Orte-Renderer folgt Kanal-Layouts) ist live; damit ist **PR #3042 / #3031** (Karte „Inhalt je Kanal“ im Reiter Wetter, schreibt `display_config.channel_layouts` als vollen Stand für Trip und Orte, Premium-SMS = SMS-Liste schreibgeschützt) auslieferbar und noch offen. Das ist faktisch die UI von Phase 5 und schreibt bereits ein Format, das die kanonische Liste von Phase 2 übernehmen bzw. lesen können muss. Reihenfolge klären: Phase 2 darf das von #3042 geschriebene Format nicht brechen; idealerweise ist `channel_layouts` (Liste von `{metric_id, enabled, format}`) bereits die Keimzelle der kanonischen Liste.
- Cloud-Zweig `claude/trips-ortsvergleiche-analyse-a61it9` ist alt (Sept., #2285) und nicht relevant.

## Analysis

### Type
Feature (Datenmodell + Resolver, ohne Änderung der Mail-Ausgabe)

### Affected Files (with changes)
| File | Change Type | Description |
|------|-------------|-------------|
| src/services/channel_list_resolver.py | CREATE | Reiner Resolver `resolve_channel_lists(display_config, surface="trip"\|"compare", report_type)` → frozen `MailViewModel` (je Liste `ChannelRow(metric_id, enabled, format, order, source)`): email, telegram, sms, premium_sms, outlook, hourly (nur Orte). Bündelt bestehende Primitive (`_cascade_source_for_channel`, `allowed_metric_ids_for_report_type`, `_clip_to_global_maximum`, `resolve_channel_layout_rows`), schreibt keine Regel neu (ADR-0097). |
| src/app/models.py | MODIFY | `get_metrics_for_channel` (:941) wird dünner Adapter über den Resolver, Signatur bleibt. |
| src/services/report_config_resolver.py | MODIFY | `resolve_compare_render_options` (:257) liest aus dem Resolver, `CompareRenderOptions` bleibt. |
| src/output/renderers/compare_metric_ids.py, compare_hourly_metric_ids.py, compare_outlook_metric_ids.py | MODIFY | Primitive bleiben, ggf. als Bausteine exportiert. |
| src/app/loader.py | MODIFY (klein) | Lese-Adapter: Zeilen mit `use_friendly_format`, `format_mode` oder `format` gleichwertig; `outlook_metric_formats {id:bool}` → Zeilenformat. |
| api/ (Python) + internal/handler (Go) | CREATE | Lese-Endpoint „Mail-View“ je Trip / Orts-Vergleich (Go → Python mit Nutzer-Kontext), damit der Editor später dieselbe Auflösung liest statt TS-Spiegel (Divergenz 6). Ggf. eigener Schnitt 2c. |
| tests/tdd/test_3057_*.py | CREATE | Differenztest neu = alt über alle Phase-1-Fallisten + Kombinationen (None/[]/gefüllt × per_report × morning/evening × Alarm); Lese-Adapter; Warnungen-Position; Anhängen beim Lesen; zwei Nutzer am Endpoint. |
| docs/adr/0121-kanonische-kanal-liste.md | CREATE | ADR: Datenform, Resolver, Lazy-Migration, Premium-SMS-Liste (Fallback = SMS-Liste), Abgrenzung zu ADR-0049/0050/0119. |
| docs/specs/modules/feat_3057_kanal_liste_resolver.md | CREATE | Spec mit ACs. |
| docs/reference/api_contract.md | MODIFY | Datenform `channel_layouts` erweitert, Endpoint. |

### Scope Assessment
- Files: ca. 10-12
- Estimated LoC: +1500-1800 (davon ca. 700 Tests) / -50
- Risk Level: MEDIUM (zentrale Auflösung für alle Kanäle und den Alarmpfad; abgesichert, weil die Mail-Ausgabe per Differenztest unverändert bleiben muss und nichts geschrieben wird)

### Technical Approach (Tech-Lead-Entscheidung)
1. **Datenform = Superset von `channel_layouts`** (Variante A; B „neuer Schlüssel `kanal_listen`“ wäre drittes Vokabular = verbotene Übergangsschicht; C „nur lesen, nichts persistieren“ löst Divergenz 2/5 nicht). Schlüssel `email|telegram|sms|premium_sms|outlook|hourly(Orte)`; Zeile `{metric_id, enabled, order, format}` mit `format ∈ raw|simplified|null`; `null` = Flächen-Standard (Trip Katalog-Standard, Orte Roh, bleibt in Phase 2 unverändert, Vereinheitlichung wäre Ausgabeänderung). Reader akzeptiert zusätzlich `use_friendly_format` (#3042, ADR-0119) und `format_mode` (Trip-MetricConfig).
2. **Resolver rein lesend, ohne I/O**; neue Grundauswahl-Metriken werden beim Lesen an jede gefüllte Liste angehängt (Konzept §5 Pkt. 6a, löst Nachprüfungs-Punkt 7). Amtliche Warnungen werden nicht gespeichert, der Resolver setzt ihre feste Position (Mail/Telegram vorn, SMS/Premium-SMS hinten). Kaskade per_report > channel > global bleibt Stufe im Resolver (report_type-Parameter; Mutation `morning_enabled=False` wird abgedeckt).
3. **Adapter statt Umstellung:** Renderer und ~12 Aufrufer bleiben unberührt (Umstellung = Phase 3, #3058). Gleichheitsbeweis: Differenztest gegen den Altpfad als Test-Orakel + Phase-1-Prüfkatalog unverändert grün. Orakel wird in Phase 3 mit den Altpfaden gelöscht.
4. **Migration lazy** (Lese-Adapter). Kein Eager-RMW-Skript in Phase 2; das ist der Contract-Schritt von Phase 3, wenn Altpfade wegfallen (ADR-0101, Pre-Snapshot). Resolver schreibt nie. Go-`mergeConfigMap` ersetzt `channel_layouts` komplett, daher neue Schlüssel (`premium_sms`, `outlook`, `hourly`) in Phase 2 nur lesbar; Schreiben erst mit dem Phase-5-Editor (voller Stand).
5. **Premium-SMS:** Konzept (PO-freigegeben) und PO-Kommentar 15.11. sehen eine eigene Liste vor. Phase 2: Resolver liefert `premium_sms` aus eigenem Schlüssel, fehlt er ⇒ SMS-Liste (= heutiges Verhalten, ADR-0119 Nr. 5). Keine Ausgabeänderung; ADR-0121 hält das fest.
6. **Leere Liste:** ADR-0050 „leer bleibt leer“ gilt; Anhängen beim Lesen betrifft nur gefüllte Listen, nicht explizit leere. ADR-0121 grenzt ADR-0119 Nr. 6 dagegen ab.
7. **Schnitt (falls LoC-Limit greift):** 2a Resolver + Adapter + Differenztest für E-Mail/Telegram/SMS/Premium-SMS (Trip + Orte) · 2b Ausblick + Stundenverlauf · 2c Lese-Endpoint. Jeder Schnitt allein auslieferbar (rein lesend). Entscheidung in /30-write-spec anhand des LoC-Limits; Folge-Schnitte dann als eigene Kind-Issues unter Epic #3047.

### Dependencies
- Aufrufer `get_metrics_for_channel`: notification_service.py:608/638, renderers/channel_layout.py:133, trip_report.py:140/292/355, api/routers/validator.py:592. `resolve_compare_render_options`: compare_preview_service.py:155, scheduler_dispatch_service.py:981. `_effective_format_mode`: email/helpers.py:82/1252/1276, notification_service.py:614, trip_report.py:408. `resolve_trip_outlook_metrics`: email/outlook.py:652, trip_report.py:223. `resolve_trip_active_metrics`: email/html.py:1289, compact.py:196, plain.py:243. `resolve_metric_col_order`: html.py:873, plain.py:193.
- **#3048** (Nachbarfenster, noch kein Zweig auf dem Server) ändert `get_metrics_for_channel`/`DEFAULT_TRIP_METRIC_IDS` → vor Phase 6 gegen `origin/main` abgleichen; dessen Rückfall wird Teil des Resolvers.
- **PR #3042** (offen, nur Frontend) schreibt `channel_layouts` `{email|telegram|sms: [{metric_id, enabled, use_friendly_format, bucket:"primary", order}]}` als vollen Stand für Trip und Orte, Orte zusätzlich `channel_active_metrics` (nur aktive, `{metric_id, aggregation}`), löscht `format_mode` auf diesen Zeilen; `premium_sms` nur Anzeige. Phase 2 liest dieses Format verlustfrei; #3042 braucht keine Änderung.
- #3052 ohne Überschneidung (narrow.py, Katalog).

### Bereits entschiedene Produktfragen (nicht erneut vorlegen)
- O1: je Liste eigene Folge (PO 15.11., Konzept §5.8). Teilmenge der Grundauswahl, Neuzugang in alle Listen, Roh/Einfach je Liste und Zeile (auch Stundenverlauf, Umsetzung Phase 3/W11), amtliche Warnung fest.
- Premium-SMS eigene, kürzere Liste (Konzept Pkt. 8): Phase 2 nur lesbar, Fallback SMS-Liste.
- Nie eingestellter Orte-Stundenverlauf: Konzept §5 Pkt. 6b ⇒ Schnitt Grundauswahl ∩ stündlich verfügbar. Ändert die Mail bestehender Orte ⇒ nicht in Phase 2 (Ausgabe bleibt gleich), sondern Phase 3 (#3058); Spec benennt die Abweichung ausdrücklich.

### Open Questions
- Keine Produktfragen offen. Technisch in /30-write-spec: LoC-Grenze und ob 2b/2c abgespalten werden; Go-Proxy-Mechanik für den Endpoint (bestehenden Validator-Weg prüfen).
