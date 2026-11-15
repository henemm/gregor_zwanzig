# Context: feature-3031-inhalt-je-kanal-listen

Issue #3031 (Sub-Issue A1 von Epic #2795, Epic #2791 „Einstellungen neu“).

## Request Summary
Im Reiter **Wetter** (Trip und Ortsvergleich, ein Code) entsteht die Karte „Inhalt je Kanal und Fläche“ nach Mockup Fassung 3: Segment E-Mail · Telegram · SMS · Premium-SMS (folgt bis S9 der SMS-Liste); je Kanal eine Liste (Teilmenge der Wetter-Metriken) mit Griff zum Umsortieren, Name „Temperatur (Temp | T)“ (`col_label` | `sms_code`), Roh/Einfach je Zeile mit Beispiel, Schalter an/aus; feste Zeile „Amtliche Warnungen“ (E-Mail/Telegram zuerst, SMS/Premium-SMS am Ende). Schnittlinie/Budget/Legende = A2 (#3032), „Weitere Einstellungen“ = A3 (#3033), Ausblick = A4 (#3034), Stundenverlauf = A5 (#3035), Übergangsblock auflösen = A6 (#3036).

## Related Files
| File | Relevance |
|------|-----------|
| frontend/src/lib/components/shared/WetterTab.svelte:1-12 | dünne Seite → Organismus |
| frontend/src/lib/components/organisms/wetter-tab/WetterTabInhalt.svelte | Karten: Vorlage :238, Metriken :251-277, WarnungenRadarKarte :278-284, AnpassenKarte :285-289 → neue Karte zwischen :284 und :285 |
| frontend/src/lib/components/shared/wetter-tab/wetterTabLaden.ts | Laden (Vergleich zusätzlich Katalog, `WetterTabInhalt.svelte:54,95-111`) |
| frontend/src/lib/components/shared/wetter-tab/wetterZustand.ts | `Z.standAusAbo` |
| frontend/src/lib/components/shared/wetter-tab/wetterTabSpeicherung.ts | EIN Speicherer (Owner `wetter-ampel` :24). Trip: PUT `/api/trips/{id}/weather-config` (ampel+metrics) + `/api/trips/{id}`, `saveController.schedule(…,700)` :86-101. Vergleich: PUT `/api/compare/presets/{id}` mit If-Match, 412 → neu laden (:103ff), nur `ampel`+`active_metrics` (:72-84). Meldung nur bei geänderter `signatur` (`WetterTabInhalt.svelte:93,118-124`) |
| frontend/src/lib/components/shared/weather-metrics-tab/weatherMetricsTabSections.ts:65-90 | `layout_kanal` in ZUSTELLUNGS_SECTIONS (heute nur im Übergangsblock sichtbar) |
| organisms/zustellung-tab/UebergangBlock.svelte:147 → shared/WetterMetrikenVersandPanel.svelte:64 → shared/WeatherMetricsTab.svelte (2186 Z.) | heutige Kette der Layout-Bedienung |
| shared/WeatherMetricsTab.svelte:1686ff (Trip), :1534-1564 + :1223-1275 (Vergleich) | heutige Kanal-Layout-Bedienung, `buildWeatherPayload` :922-963, PUT :994 |
| shared/layout-tab/LayoutTab.svelte, LTChannelPicker, ltChannels.ts, LTCutLine | Kanalwahl, Schnittlinie (alt) |
| shared/weather-metrics-tab/WeatherV2Reihenfolge.svelte | Editor: SortableList, DragHandle, Segmented Roh/Einfach :176-179 |
| shared/weather-metrics-tab/channelMetricLayouts.ts | Copy-on-write: `startChannelOverride` :71, `splitChannelMetricsForDisplay` :136, `mergeAllChannelLayoutsForSave` :161 |
| shared/weather-metrics-tab/compareChannelMetricLayouts.ts:27-96, weatherMetricsCompareSave.ts:183,351 | Vergleich: `display_config.channel_active_metrics[ch]` (email/telegram/sms), nur geordnete Liste |
| internal/handler/weather_config.go:55, internal/handler/config_merge.go:8-22, internal/router/router.go:314-317 | Go RMW je Top-Level-Key; `channel_layouts` wird als Ganzes ersetzt → immer vollen Stand senden |
| internal/model/trip.go:121, compare_preset.go:48 | `display_config` untypisiert (`map[string]interface{}`) |
| src/app/models.py:669-700 (MetricConfig), :822ff (UnifiedWeatherDisplayConfig, `per_channel_layouts` :843, `per_report_layouts` :847), :938-990 `get_metrics_for_channel` | Datenmodell/Kaskade |
| src/app/loader.py:1035-1066, :1070, :1655 | `channel_layouts` → `per_channel_layouts` (je Eintrag friendly/format_mode) |
| src/output/renderers/channel_layout.py:133, trip_report.py:140/:292, notification_service.py:608/:638, sms_trip.py:96-106 | Renderer-Leser |
| src/output/renderers/compare_metric_ids.py:253-283, src/services/report_config_resolver.py:315/:344 | Vergleich liest `channel_active_metrics`; `outlook_metric_formats` |
| api/routers/config.py:111-150 (`GET /api/metrics`), api/routers/compare.py:12 (`GET /api/compare/metrics`) | Katalog mit `col_label`, `sms_code`, `has_friendly_format`, `format_modes`, `default_format_mode` |
| frontend/src/lib/i18n/messages/{de,en}/wetter.json, layout.json, wertebereiche.json, i18n/hardcode_allowlist.json | Texte |
| docs/context/einstellungen_neu/seiten/mockup-hub-fassung3.html (`const EX` :322, Vorbelegung Einfach ~:490) | Soll, Beispielwerte |
| docs/context/einstellungen_neu/elementliste.json (Abschnitt `kanal-inhalt` ~:361), elementliste_besitzer.json:2103-2108 / :2295-2300 | Elementliste, Besitzer „Kanal-Segmente noch nicht gebaut“ → nach dem Bau entfernen |

## Existing Patterns
- Wetter-Reiter = Organismus aus Atomen/Molekülen (ADR-0112): `atoms/Segmented`, `Switch`, `Card`, `Eyebrow`, `molecules/Einstellungszeile`. Neue Dateien nur in SEITEN_SCOPE oder unter atoms/molecules/organisms (`bausteine_waechter_regeln.ts:417-470`).
- Sortieren: genau ein Baustein (ADR-0024) `shared/dnd/SortableList.svelte` + `DragHandle.svelte` (BESTAND, `bausteine_waechter_regeln.ts:579-580`), Wächter `no_native_draggable_guard.test.ts`.
- Ein Speicherer je Reiter, Signatur-Vergleich, Hub-Schlange mit If-Match beim Vergleich.
- Copy-on-write je Kanal: ohne Eintrag gilt die globale Liste (Kaskade per_report → per_channel → global).

## Dependencies
- Upstream: Katalog-Endpunkte, Wetter-Metrikliste (Teilmenge), Go-RMW-Merge, Python-Loader.
- Downstream: alle Kanal-Renderer (Mail-Tabelle, Telegram, SMS, Vergleichs-Mail), Mail-Validatoren, Einstellung-gleich-Auslieferung-Tests (`tests/tdd/test_einstellung_gleich_auslieferung.py`, Fixture `fall3_roh_einfach_umschalten`), `test_issue_429_channel_layouts.py`, `test_sms_einfach_roh_je_metrik.py`, `test_telegram_rich_roh_einfach_eigenes_layout.py`.

## Existing Specs
- `docs/specs/modules/layout_tab_route.md`, `layout_tab_vergleich.md`, `feat_1703_s8_compare_kanal_tabs.md`, `fix_1575_channel_metric_selection.md`, `fix_2422_einstellung_gleich_auslieferung.md`, `fix_2422_s3_kanal_an_aus_kette.md`, `feat_2794_s3a_teil3_wetter.md`, `fix_2913_metrikliste_mockup.md`, `feat_2913_abgleich_ganzseite.md`, `feat_2795_s3b_teil1_zustellung.md`.

## Risks & Considerations
- **Vergleich kennt heute kein Roh/Einfach je Kanal** (`channel_active_metrics` = nur geordnete Kennungen, kein `enabled`, kein Format). PO-Entscheidung W11: Roh/Einfach in jeder Liste, Trip und Orte gleich → Datenmodell-Erweiterung für den Vergleich (paralleles Feld analog `outlook_metric_formats`, oder Angleichung an `channel_layouts`) plus Renderer-Wirkung in der Vergleichs-Mail/Telegram/SMS. Größter Unsicherheitsposten; ggf. als eigenes Teilstück schneiden.
- Wetter-Speicherer schreibt heute weder `channel_layouts` (Trip) noch `channel_active_metrics` (Vergleich) → erweitern; Go ersetzt den Key komplett → immer vollen Stand senden; Datenverlust-Gefahr (CLAUDE.md „Daten-Schema-Reworks“).
- Zwei Bedienungen desselben Felds parallel (neue Karte im Wetter-Reiter + alte im Übergangsblock) bis A6 → Konkurrenz um denselben Key, Stale-Payload im selben Tab. Entweder den alten Abschnitt `layout_kanal` in A1 aus dem Übergangsblock entfernen (bevorzugt, kein Bedienelement geht verloren, da er umzieht) oder Neu-Laden nach Reiterwechsel sicherstellen.
- Premium-SMS hat keine eigene Liste (ADR-0049, bis S9): Reiter zeigt die SMS-Liste mit Hinweis „folgt der SMS-Liste“, nicht bearbeitbar oder bearbeitet die SMS-Liste — festlegen.
- Teilmengen-Regel (ADR-0050/0059): Liste darf nur abwählen, nichts hinzufügen; neue Metrik im Wetter-Reiter muss in Kanallisten erscheinen (an? aus?).
- Amtliche-Warnungen-Zeile ist reine Anzeige (kein Datenfeld).
- Beispielwerte für Roh/Einfach existieren nur im Mockup → Katalog-/Format-Quelle festlegen, DE/EN.
- Elementliste-Besitzer `kanal-inhalt` (#2795) nach dem Bau auf echten Abgleich umstellen.
- Mutationen/Tests: Wirkung dort prüfen, wo sie wirkt (Renderer-Ausgabe je Kanal), nicht nur Payload.

## Analysis

### Type
Feature (Sub-Issue A1 von Epic #2795).

### Schnitt (Tech-Lead-Entscheidung 2026-11-15)
- **#3039 A1-Vorlauf (eigener Workflow, zuerst ausliefern):** Vergleich bekommt `display_config.channel_layouts` `{ch:[{metric_id, enabled, use_friendly_format}]}` wie der Trip; Lese-Rückfall auf `channel_active_metrics` (alle an, Katalog-Default-Format), dann Grundauswahl; `channel_active_metrics` wird als Übergang weiter mitgeschrieben (nur eingeschaltete IDs, geordnet). Resolver + Renderer-Wirkung (Mail-Vergleichstabelle `email/compare_html.py:430`, Telegram `comparison.py:744/762-771`, SMS `comparison.py:1090`), Konsumenten `scheduler_dispatch_service.py:997/1066/1074`, `compare_preview_service.py:74/84/165`. Keine UI.
- **#3031 (dieser Workflow):** Karte + beide Adapter + Speicherung + `layout_kanal` aus Übergangsblock. Implementierung/Auslieferung erst nach #3039 (sonst geht die Karte beim Vergleich mit halber Parität live). Spec darf jetzt geschrieben werden, setzt #3039 voraus.
- Begründung: zusammen >1.000 LoC über Frontend + Python; Parallelfeld (`channel_metric_formats` + `channel_disabled`) verworfen, weil drei Wahrheiten je Zeile auseinanderlaufen; Angleichung = ein Adapter-Modell für die Karte.

### Affected Files (#3031)
| File | Change Type | Description |
|------|-------------|-------------|
| frontend/src/lib/components/organisms/wetter-tab/KanalInhaltKarte.svelte | CREATE | Organismus: Segmented (E-Mail·Telegram·SMS·Premium-SMS), SortableList+DragHandle, Zeile „Name (col_label \| sms_code)“, Segmented Roh/Einfach mit Beispiel, Switch, feste Zeile Amtliche Warnungen |
| frontend/src/lib/components/organisms/wetter-tab/kanalInhalt.ts | CREATE | neutrales Zeilenmodell `KanalZeile{id, enabled, format}` je Kanal; Normalisierung (Teilmenge der Wetter-Metriken, fehlende Metrik = an, ans Ende); Adapter Trip/Vergleich (beide auf `channel_layouts`) |
| frontend/src/lib/components/organisms/wetter-tab/kanalInhaltBeispiele.ts | CREATE | statische Beispielwerte DE/EN je Metrik aus Mockup `const EX` (mockup-hub-fassung3.html:322); Test gegen Katalog (jede Metrik mit `has_friendly_format` hat Eintrag) |
| frontend/src/lib/components/organisms/wetter-tab/WetterTabInhalt.svelte | MODIFY | Karte zwischen WarnungenRadarKarte (:278-284) und AnpassenKarte (:285) einhängen |
| frontend/src/lib/components/shared/wetter-tab/wetterTabSpeicherung.ts | MODIFY | `tripNutzlast` :56 + `vergleichNutzlast` :73 schreiben vollen `channel_layouts`-Stand (Go ersetzt Key ganz); Vergleich zusätzlich `channel_active_metrics`; Signatur erweitert |
| frontend/src/lib/components/shared/wetter-tab/wetterTabLaden.ts, wetterZustand.ts | MODIFY | Kanal-Layouts laden |
| frontend/src/lib/components/shared/weather-metrics-tab/channelMetricLayouts.ts | REUSE | `startChannelOverride` :71, `splitChannelMetricsForDisplay` :136, `mergeAllChannelLayoutsForSave` :161 |
| frontend/src/lib/components/shared/weather-metrics-tab/weatherMetricsTabSections.ts | MODIFY | `layout_kanal` aus ZUSTELLUNGS_SECTIONS :83 (Übergangsblock); Grundliste :66 prüfen (Wetter-/Vergleichs-Editor Altpfad) |
| frontend tests: s3a2794_bereich_filter.test.ts:35/39, s3b2795_zustellung_struktur.test.ts:227-240 (AC-30), weatherMetricsTabSharing.test.ts:100/146/191, compare_layout_tab_dissolution.test.ts:243-249, wetter_metriken_versand_panel_paritaet.test.ts:240 | MODIFY | an Umzug anpassen |
| frontend/src/lib/i18n/messages/{de,en}/wetter.json | MODIFY | Untertitel, Kopfzeile, Hinweise, „folgt der SMS-Liste“, Warnungs-Zeilen |
| frontend/src/lib/components/bausteine_waechter_regeln.ts (SEITEN_SCOPE) | MODIFY | neue Dateien zulassen (ADR-0112) |
| docs/context/einstellungen_neu/elementliste_besitzer.json:2103-2108/:2295-2300 | MODIFY | Besitzer `kanal-inhalt` „noch nicht gebaut“ → echter Abgleich |
| frontend tests (neu) | CREATE | Zeilenmodell/Normalisierung, Adapter, Speichern sendet alle Kanäle, Karte (Umsortieren, Schalter, Roh/Einfach, Premium-SMS schreibgeschützt), zwei Nutzer; Wirkung (Renderer) über bestehende Trip-Tests `test_einstellung_gleich_auslieferung.py` (Fixture `fall3_roh_einfach_umschalten`) + #3039-Tests |

### Scope Assessment
- #3031: ~10–14 Dateien, ca. +700/−80 LoC inkl. Tests (Karte ~200, Modell/Adapter ~120, Beispiele ~60, Speicherung ~100, Tests ~300). Über dem üblichen LoC-Limit → in der Spec begründen oder Karte und Übergangsblock-Umzug in getrennten Commits.
- Risk Level: MEDIUM (Datenverlust-Gefahr durch Komplett-Ersetzen von `channel_layouts`; zweiter Bediener desselben Felds).

### Technical Approach
1. Karte kennt nur `KanalZeile[]` je Kanal; Trip- und Vergleichs-Adapter lesen/schreiben dieselbe Struktur `channel_layouts` (Vergleich erst nach #3039 wirksam).
2. Speichern immer voller Stand aller Kanäle (Read-Modify-Write, Go ersetzt Key); Vergleich über bestehende If-Match/412-Schlange, Trip über 700-ms-Schlange.
3. **Aus = Zustand:** ausgeschaltete Zeile bleibt mit Position in der Liste (`enabled:false`), Renderer zeigt sie nicht.
4. **Neue Wetter-Metrik:** erscheint in bestehenden Kanallisten **an**, am Ende (Doku `einstellungen_neu.md:460` „in allen Listen“); Normalisierung beim Laden/Speichern in der Karte. Abwahl im Wetter-Reiter wirkt in allen Kanälen (ADR-0050 R3).
5. **Premium-SMS:** Segment zeigt die SMS-Liste schreibgeschützt mit Hinweis „folgt der SMS-Liste“ (bis S9, ADR-0049; laut Issue).
6. **Amtliche Warnungen:** reine Anzeigezeile, nicht sortierbar, kein Datenfeld (E-Mail/Telegram oben, SMS/Premium-SMS unten).
7. **Name:** Katalog `col_label` | `sms_code` (Temperatur `T`, nicht Mockup-`D`).
8. **Übergangsblock:** `layout_kanal` wird in #3031 entfernt (nicht erst A6) — schließt den Stale-Payload-Weg; A6 räumt den Rest.

### Dependencies
- Upstream: #3039 (Vergleich Datenmodell + Renderer) muss vorher live sein; Katalog `GET /api/metrics` (col_label, sms_code, format_modes, has_friendly_format); Go-Merge je Top-Level-Key (`config_merge.go:8-22`).
- Downstream: alle Kanal-Renderer, Mail-Validatoren, A2 (#3032 Schnittlinie/Legende in derselben Karte), A6 (#3036).

### Open Questions
- keine Produktfrage offen (W11, WV6, Premium bis S9, „in allen Listen“ sind entschieden bzw. dokumentiert).
