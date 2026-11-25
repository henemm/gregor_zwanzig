# Context: rework-3036-uebergangsblock-aufloesen

## Request Summary
Issue #3036 (Epic #2791 / #3122-Folge): Übergangsblock am Ende des Reiters Zustellung auflösen, Altbausteine und veraltete Tests entfernen. PO-Entscheidung 2026-11-24 (Intake, Kommentar im Issue): Kurz-Zusammenfassung (`show_compact_summary`) und Großwetterlage (`show_stability`) bekommen je einen eigenen Schalter unter „Ganze Blöcke ein- und ausschalten“ in der Karte „Was steht wo“ (nur Trip). Die vier wirkungslosen Altschalter (`show_quick_take_tags`, `show_metrics_summary`, `show_highlights`, `daily_summary_metrics`) und SMS-Schwellen bekommen keine Oberfläche.

## Ist-Stand (origin/main 5c8b44855)
- `UebergangBlock.svelte` (organisms/zustellung-tab) enthält nur noch: Pausieren/Aktivieren-Karte (Snippet `hubActivationCard`, `CompareTabs.svelte:876-893`, übergeben `:847`; Anlegen: `CompareNewEditor.svelte:570/618` `versandActivationBanner`) und Beispiel-Alarm (`AlertPreviewCard`). Rahmen: Kopf „Vorübergehend hier …“ (`zustellung.uebergang.titel/hinweis`), gestrichelte Linie, testid `zustellung-uebergang`.
- Seit #3154/#3332/#3333 werden `WetterMetrikenVersandPanel`, `WeatherMetricsTab`, `MailInhaltCard` nirgends mehr gerendert (tot). Folge: `show_compact_summary`/`show_stability` haben heute keine Bedienstelle. Prod (henning, steffi, default): alle Trips beide `true` bzw. fehlend (= Default true).
- Soll-Bild `mockup-hub-fassung4.html`: Pausieren/Aktivieren im Kebab „⋮“ des Hub-Kopfs (Z. 270, 421-431), Test-Alarm (A14) im Kopf-Menü „Test schicken ▾“ (Z. 274, 418) → Issue #2797 (OPEN). „Ganze Blöcke“ (Z. 713) ohne Kurz-Zusammenfassung/Großwetterlage → neue Schalter gehen bewusst über das Mockup hinaus (PO-Entscheid).

## Related Files
| File | Relevance |
|------|-----------|
| `frontend/src/lib/components/organisms/wetter-tab/WasStehtWoKarte.svelte` | `TRIP_BLOECKE` (Z. 54-58), Block-Abschnitt (Z. 262-284), `nurAusfuehrlich` (Z. 223, 280), `Felder`/`felderAusAntwort`/`felderNutzlast` (Z. 184-238), `KONTEXT` route/vergleich (Z. 48-51) |
| `frontend/src/lib/components/shared/wetter-tab/wasStehtWoSpeicherung.ts:245` | `erstelleFelderSpeicherung`, Teilfeld-PUT, 700 ms Debounce |
| `src/services/placements_view_service.py:424-430` | `blocks`-Antwort der Placements-GET — beide Felder ergänzen |
| `frontend/src/lib/i18n/messages/{de,en}/wetter.json` ~195-202 | Keys `wetter.wsw.bloecke.*`; gepinnt in `i18n/__tests__/deutsch_unveraendert.test.ts:524-528` |
| `frontend/src/lib/components/organisms/zustellung-tab/UebergangBlock.svelte` | aufzulösen |
| `frontend/src/lib/components/shared/zustellung-tab/ZustellungTab.svelte:24,41,52,111` | Mount des Blocks |
| `frontend/src/lib/components/compare/CompareTabs.svelte`, `compare-new/CompareNewEditor.svelte` | Activation-Snippet |
| `src/output/renderers/trip_report.py:218,281`, `email/html.py:1276,1358-1374,1432`, `email/plain.py:225,275` | Wirkung der beiden Schalter (HTML + Text-Mail) |
| `docs/context/einstellungen_neu/elementliste_besitzer.json` | 282 Einträge `verweis #2795`, `art zusaetzlich`, Grund „Übergangsblock …“ → entfernen; Abgleich `scripts/elementliste_abgleich.ts` (`npm run elementliste:abgleich -- --scope zustellung --abnahme`) |
| `frontend/e2e/alarm-ab-nur-lesbar.spec.ts`, `frontend/e2e/s3a2794-zustellung-inventar-speicherweg.spec.ts` | veraltet, löschen |
| weitere Tests mit `zustellung-uebergang`: `e2e/s3b2795-zustellung-uebergang.spec.ts`, `s3b2795-zustellung.helpers.ts:67`, `trip-outlook-metric-selection.staging.spec.ts:70`, `versand-tab.spec.ts:133`, `compare/__tests__/compare_layout_tab_dissolution.test.ts:85,269-272`, `shared/__tests__/infobox_nur_beim_anlegen.test.ts:474-477`, `shared/__tests__/s3a2794_eine_wmt_instanz.test.ts:64` | nachziehen |

## Existing Patterns
- Neue Block-Schalter: Eintrag in `TRIP_BLOECKE` + i18n `titel`/`hinweis` + testid `was-steht-wo-{feld}`; Startwert aus `blocks` (Python), Speichern als Teilfeld-PUT `report_config` (Trip).
- Block-Schalter der ausführlichen Mail sind bei `email_format==='compact'` gesperrt mit Hinweis `nur_ausfuehrlich`.
- Kontext-Unterschied Trip/Orte nur als Daten (`KONTEXT`-Tabelle), Ratsche `context_herkunft_zweige_eingefroren`.

## Dependencies
- Upstream: Placements-GET (`/api/briefings/{id}/placements`), Trip-PUT `/api/trips/{id}` (Go, Merge über report_config).
- Downstream: Mail-Renderer (HTML/Text). Kompakt-Mail und Telegram werten beide Felder nicht aus (Telegram druckt `WL:` immer, `narrow.py:857-858`).

## Abgrenzung zu #3020
Löschen von `WeatherMetricsTab` samt totem Umfeld (WetterMetrikenVersandPanel, MailInhaltCard, VersandTab, BriefingScheduleTab, LayoutTab/LT*, tote versand-tab-Module inkl. `vtBriefingChannelsText.ts` mit `telegram_kurzform`, `sms_schwellen`-Abschnitt) ist #3020. Die Alt-Bausteine aus #3036 sind nur über WeatherMetricsTab erreichbar → sie fallen mit #3020; #3036 löscht sie nicht separat (sonst doppelte Baustelle). Lebend bleiben müssen: `channelConnectionStatus.ts`, `sendTargetLabel.ts`, `dayWindowClamp.ts`, `nextBriefingText.ts`, `naechstesBriefingLader.svelte.ts`, `nextBriefingLoad.ts`, `reportConfigPayload.ts`, `mergeReportConfig.ts`, `ltChannels.ts`, `kanalStilSpeicherung.ts`.

## Existing Specs
- `docs/specs/modules/feat_3122_was_steht_wo.md` (Teil B Nr. 14, AC-30)
- `docs/specs/modules/feat_2795_s3b_teil1_zustellung.md` (AC-30 Übergangsblock)
- `docs/specs/modules/feat_3332_zustellung_anlegen_trip.md` (MailInhaltCard entfällt, Known Limitation `show_stability`)
- ADR-0124 (`docs/adr/0124-was-steht-wo-eine-tabelle.md`, Z. 94: Frage gehört zu #3036)

## Risks & Considerations
- Nie ein Zeitpunkt ohne Bedienstelle: Pausieren/Aktivieren und Beispiel-Alarm bleiben im Reiter Zustellung, nur ohne „Vorübergehend“-Rahmen, bis #2797 sie in den Hub-Kopf holt.
- Neue Schalter: Teilfeld-PUT darf andere report_config-Felder nicht überschreiben (Read-Modify-Write auf Go-Seite, Test mit zwei Nutzern).
- Kanal-Parität: beide Schalter wirken nur auf die ausführliche Mail (wie Etappen-Kennzahlen); bei Kompakt gesperrt. Telegram-`WL:` bleibt unabhängig → in Spec als Known Limitation/Folgefrage.
- Elementlisten-Abgleich nur mit Prüfkonto-Login + Seed-IDs.
- Mail-Inhalt ändert sich nicht (nur Bedienstelle) → Renderer-Gate voraussichtlich nicht berührt.

## Analysis

### Type
Feature/Rückbau (Tiefe Summe 3: Kontext + Analyse in einem Durchgang, strategische Bewertung inline)

### Affected Files (with changes)
| File | Change Type | Description |
|------|-------------|-------------|
| `frontend/src/lib/components/organisms/wetter-tab/WasStehtWoKarte.svelte` | MODIFY | `TRIP_BLOECKE` + `show_compact_summary`, `show_stability`; `Felder`, `felderAusAntwort`, `felderNutzlast` (rc-Schlüssel); gesperrt bei Kompakt wie die übrigen Blöcke |
| `src/services/placements_view_service.py` | MODIFY | `blocks` + `show_compact_summary`, `show_stability` (Default true) |
| `frontend/src/lib/i18n/messages/{de,en}/wetter.json` | MODIFY | `wetter.wsw.bloecke.kurz[_hinweis]`, `…grosswetterlage[_hinweis]` |
| `frontend/src/lib/components/organisms/zustellung-tab/UebergangBlock.svelte` | DELETE/ersetzen | Rahmen „Vorübergehend hier“ entfällt; Beispiel-Alarm als eigener Abschnitt (`BeispielAlarm.svelte`), Pausieren/Aktivieren-Karte als fester Platz oben im Reiter (Orte) |
| `frontend/src/lib/components/shared/zustellung-tab/ZustellungTab.svelte` | MODIFY | Mount anpassen |
| i18n `zustellung.uebergang.*` | MODIFY | Keys entfernen (DE/EN), Katalog-Tests nachziehen |
| `docs/context/einstellungen_neu/elementliste_besitzer.json` | MODIFY | 282 Übergangsblock-Ausnahmen (#2795, art zusaetzlich) entfernen |
| `frontend/e2e/alarm-ab-nur-lesbar.spec.ts`, `frontend/e2e/s3a2794-zustellung-inventar-speicherweg.spec.ts` | DELETE | veraltet |
| Tests mit `zustellung-uebergang` (s. oben) | MODIFY | auf neue testids |
| neue Tests: Karte (Schalter sichtbar Trip, nicht Orte, gesperrt bei Kompakt, PUT nur geänderte Felder), Python `blocks`, E2E Schalter → Mail (HTML) | CREATE | |

### Scope Assessment
- Files: ~14 (davon 2 Löschungen, 1 große JSON-Bereinigung)
- Estimated LoC: +250/−700 (JSON-Bereinigung dominiert)
- Risk Level: MEDIUM (Bedienoberfläche Hub, Speicherpfad report_config; Renderer unverändert)

### Technical Approach
1. Zwei neue Block-Schalter nach exakt dem Muster der bestehenden (`show_stage_stats` …). Speichern als Teilfeld-PUT `report_config`; Go merged per `mergeConfigMap` (`internal/store/trip.go`), keine Go-Änderung. Startwert aus `blocks` der Placements-GET. Beide wirken nur auf die ausführliche Mail (HTML + Text); bei Kompakt gesperrt mit Hinweis `nur_ausfuehrlich`.
2. Übergangsblock auflösen: kein „Vorübergehend“-Rahmen mehr. Beispiel-Alarm bleibt als regulärer Abschnitt am Ende des Reiters Zustellung, Pausieren/Aktivieren (nur Orte) als fester Abschnitt direkt unter dem Kopf. Beide wandern später mit #2797 in den Hub-Kopf (Soll-Bild Kebab / „Test schicken ▾“). Kein Zeitpunkt ohne Bedienstelle.
3. Alt-Bausteine (versand-tab-Cluster, layout-tab, `vtBriefingChannelsText.ts` mit `telegram_kurzform`, `sms_schwellen`) sind ausschließlich über das tote `WeatherMetricsTab` erreichbar → Löschung gesammelt in #3020 (nächstes Issue des Auftrags), hier nur dokumentiert, um doppelte Baustelle zu vermeiden.
4. Elementliste: Übergangsblock-Ausnahmen raus, Abgleich `--scope zustellung --abnahme` DE+EN mit Prüfkonto gegen Staging grün.

### Dependencies
- Placements-GET (Python) → Karte; Trip-PUT (Go, Merge) → report_config; Renderer `trip_report.py` liest die Felder unverändert.

### Befunde gegen den Plan
- Kanal-Parität (ADR-0095): Telegram druckt `WL:` unabhängig von `show_stability`, Kompakt-Mail ignoriert beide. Gleiches gilt heute schon für Etappen-Kennzahlen/Vortag/Nacht („Ganze Blöcke“ = Blöcke der ausführlichen Mail). Hinweistext macht das sichtbar; Telegram-Angleichung als Nebenbefund (#1199), nicht Teil dieses Issues.

### Open Questions
- keine (Produktfrage am 2026-11-24 entschieden)
