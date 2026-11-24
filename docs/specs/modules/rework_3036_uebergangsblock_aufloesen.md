---
entity_id: rework_3036_uebergangsblock_aufloesen
type: refactor
created: 2026-11-24
updated: 2026-11-24
status: draft
version: "1.0"
workflow: rework-3036-uebergangsblock-aufloesen
tags: [zustellung, was-steht-wo, report_config, epic-2791]
---

# Reiter Zustellung (1c): Übergangsblock auflösen + zwei neue Block-Schalter

## Approval

- [ ] Approved

## Purpose

Der Reiter Zustellung verliert den Rahmen „Vorübergehend hier …“: Beispiel-Alarm und die Pausieren/Aktivieren-Karte der Orte bleiben als reguläre Abschnitte erhalten, bis #2797 sie in den Hub-Kopf holt. Zugleich bekommen Kurz-Zusammenfassung (`show_compact_summary`) und Großwetterlage (`show_stability`) je einen eigenen Schalter in der Karte „Was steht wo“ (nur Trip), denn sie haben seit #3154/#3332/#3333 keine Bedienstelle mehr (PO-Entscheidung 2026-11-24, Issue #3036).

## Source

- **File:** `frontend/src/lib/components/organisms/wetter-tab/WasStehtWoKarte.svelte`
- **Identifier:** `TRIP_BLOECKE`, `Felder`, `felderAusAntwort`, `felderNutzlast`; ausserdem `UebergangBlock.svelte` (aufzulösen) und `placements_view_service.py` (`blocks`)

Schichten: Frontend (`frontend/src/...`) und Python-Core (`src/services/placements_view_service.py`). Go-API unverändert (Merge über `mergeConfigMap` in `internal/store/trip.go`).

**Querschnitts-Prüfpunkte:**
- **Trip/Ortsvergleich-Teilung:** Ein Code, Kontext-Unterschied nur als Daten in der `KONTEXT`-Tabelle (`route`/`vergleich`). Die zwei Schalter sind nur Trip-Einträge von `TRIP_BLOECKE`, wie die übrigen Block-Schalter (Ratsche `context_herkunft_zweige_eingefroren` bleibt grün). Orte haben im Renderer kein Pendant zu Kurz-Zusammenfassung/Großwetterlage.
- **Mandantentrennung:** Speichern ändert Nutzerdaten (report_config); getestet mit zwei verschiedenen Nutzern, `user_id` aus dem Auth-Kontext.
- **Kanäle:** Beide Schalter wirken nur auf die ausführliche E-Mail (HTML + Text), wie Etappen-Kennzahlen/Vortag/Nacht („Ganze Blöcke“ = Blöcke der ausführlichen Mail). Kompakt-Mail, Telegram, SMS und Premium-SMS werten die Felder nicht aus (siehe Known Limitations).

## Estimated Scope

- **LoC:** +250/-700 (JSON-Bereinigung der Elementliste dominiert)
- **Files:** ca. 14, davon 2 Löschungen
- **Effort:** medium

## Scope

### Affected Files

| File | Change Type | Description |
|------|-------------|-------------|
| `frontend/src/lib/components/organisms/wetter-tab/WasStehtWoKarte.svelte` | MODIFY | `TRIP_BLOECKE` + `show_compact_summary`, `show_stability`; `Felder`, `felderAusAntwort`, `felderNutzlast`; gesperrt bei Kompakt |
| `src/services/placements_view_service.py` | MODIFY | `blocks` der Placements-GET + beide Felder (Default true) |
| `frontend/src/lib/i18n/messages/de/wetter.json`, `.../en/wetter.json` | MODIFY | Keys `wetter.wsw.bloecke.kurz[_hinweis]`, `...grosswetterlage[_hinweis]`; Pin-Test `deutsch_unveraendert.test.ts` ergänzen |
| `frontend/src/lib/components/organisms/zustellung-tab/UebergangBlock.svelte` | DELETE/ersetzen | Rahmen entfällt; `BeispielAlarm.svelte` (Abschnitt am Ende) und fester Abschnitt für Pausieren/Aktivieren |
| `frontend/src/lib/components/shared/zustellung-tab/ZustellungTab.svelte` | MODIFY | Mount anpassen |
| `frontend/src/lib/components/compare/CompareTabs.svelte`, `compare-new/CompareNewEditor.svelte` | MODIFY | Activation-Snippet an neuen Platz (direkt unter dem Kopf) |
| i18n `zustellung.uebergang.*` (DE/EN) | MODIFY | Keys entfernen, Katalog-Tests nachziehen |
| `docs/context/einstellungen_neu/elementliste_besitzer.json` | MODIFY | Übergangsblock-Ausnahmen (#2795, `art zusaetzlich`) entfernen |
| `frontend/e2e/alarm-ab-nur-lesbar.spec.ts`, `frontend/e2e/s3a2794-zustellung-inventar-speicherweg.spec.ts` | DELETE | veraltet |
| `frontend/e2e/s3b2795-zustellung-uebergang.spec.ts`, `s3b2795-zustellung.helpers.ts`, `trip-outlook-metric-selection.staging.spec.ts`, `versand-tab.spec.ts`, `compare/__tests__/compare_layout_tab_dissolution.test.ts`, `shared/__tests__/infobox_nur_beim_anlegen.test.ts`, `shared/__tests__/s3a2794_eine_wmt_instanz.test.ts` | MODIFY | `zustellung-uebergang` auf neue testids nachziehen |
| neue Tests (Karte, Python `blocks`, E2E Schalter-zu-Mail) | CREATE | siehe Test Plan |

### Nicht in dieser Spec

- **Löschen der Alt-Bausteine und der Anzeige `telegram_kurzform` → #3020.** Grund: Alle diese Bausteine (Versand-Reiter-Cluster, Layout-Reiter, `vtBriefingChannelsText.ts` samt `telegram_kurzform`-Anzeige, `sms_schwellen`-Abschnitt) werden ausschließlich vom toten `WeatherMetricsTab` importiert. Sie lassen sich nicht löschen, ohne `WeatherMetricsTab` selbst zu löschen, und genau das weist das Issue #3036 selbst („Rückbau `WeatherMetricsTab` selbst: #3020“) dem Issue #3020 zu. #3020 ist das nächste Issue desselben Auftrags. Für Nutzer ändert sich dadurch nichts: keiner dieser Bausteine wird heute angezeigt.
- **Ziel SMS-Schwellen (geklärt):** Kein Ziel, die Einstellung entfällt (Epic #2791 DoD-1, Konzept W13: seit der Profil-Ampel ohne Wirkung). Heute nirgends sichtbar; der tote Abschnitt fällt mit #3020.
- Verlegung von Pausieren/Aktivieren und Beispiel-Alarm in den Hub-Kopf → #2797.
- Telegram-`WL:` bzw. Kompakt-Mail an die beiden Schalter binden → Nebenbefund.

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| Placements-GET `/api/briefings/{id}/placements` | Python-API | liefert Startwerte in `blocks` |
| Trip-PUT `/api/trips/{id}` (Go, `mergeConfigMap`) | Go-API | Teilfeld-Speichern von `report_config` mit Merge |
| `wasStehtWoSpeicherung.ts` (`erstelleFelderSpeicherung`, 700 ms Debounce) | Frontend | Teilfeld-PUT |
| `trip_report.py`, `email/html.py`, `email/plain.py` | Renderer | werten `show_compact_summary`/`show_stability` unverändert aus |
| `briefing_mail_validator.py` | Validator | prüft zugestellte Staging-Mail |
| `scripts/elementliste_abgleich.ts` | Skript | Abnahme-Abgleich Reiter Zustellung |
| #2797 (offen), #3020 (offen) | Issues | Hub-Kopf-Lösung bzw. Löschen des toten `WeatherMetricsTab`-Umfelds |

## Implementation Details

1. **Neue Schalter:** In `TRIP_BLOECKE` zwei Einträge nach dem Muster von `show_stage_stats`; testids `was-steht-wo-show_compact_summary` und `was-steht-wo-show_stability`; Startwert aus `blocks` der Placements-GET (fehlendes Feld = an); Speichern als Teilfeld-PUT auf `report_config` (nur das geänderte Feld). Bei `email_format==='compact'` gesperrt mit Hinweis `nur_ausfuehrlich`. Texte über den Katalog (ADR-0104).
2. **Python:** `placements_view_service.py` ergänzt `blocks` um beide Felder (Default true).
3. **Übergangsblock auflösen:** Rahmen, gestrichelte Linie, Kopf `zustellung.uebergang.titel/hinweis` und testid `zustellung-uebergang` entfallen. Beispiel-Alarm (`AlertPreviewCard`) wird eigener Abschnitt am Ende des Reiters (Trip und Orte). Pausieren/Aktivieren-Karte (nur Orte) wird fester Abschnitt direkt unter dem Kopf (Hub: Snippet `hubActivationCard`; Anlegen: `versandActivationBanner`), Bedienung unverändert. Beides wandert mit #2797 in den Hub-Kopf; bis dahin gibt es nie einen Zeitpunkt ohne Bedienstelle.
4. **Elementliste:** Ausnahmen mit Verweis #2795, `art zusaetzlich`, Grund „Übergangsblock …“ entfernen; Abgleich `npm run elementliste:abgleich -- --scope zustellung --abnahme` für DE und EN mit Prüfkonto gegen Staging.
5. **Abgrenzung zu #3020:** Alt-Bausteine (versand-tab-Cluster, layout-tab, `vtBriefingChannelsText.ts` mit `telegram_kurzform`, `sms_schwellen`-Abschnitt) sind nur über das tote `WeatherMetricsTab` erreichbar und fallen mit #3020; hier keine Löschung. Lebend bleiben: `channelConnectionStatus.ts`, `sendTargetLabel.ts`, `dayWindowClamp.ts`, `nextBriefingText.ts`, `naechstesBriefingLader.svelte.ts`, `nextBriefingLoad.ts`, `reportConfigPayload.ts`, `mergeReportConfig.ts`, `ltChannels.ts`, `kanalStilSpeicherung.ts`.
6. **Keine Oberfläche** für `show_quick_take_tags`, `show_metrics_summary`, `show_highlights`, `daily_summary_metrics` und SMS-Schwellen; gespeicherte Werte bleiben unverändert (Merge, nie Replace; ADR-0101, CLAUDE.md Daten-Schema-Pflicht).

## Expected Behavior

- **Input:** Nutzer öffnet Trip-Hub, Reiter Wetter, Karte „Was steht wo“; schaltet einen der zwei neuen Blöcke um.
- **Output:** Teilfeld-PUT mit genau diesem Feld; die nächste ausführliche Mail zeigt oder verbirgt den Block.
- **Side effects:** Reiter Zustellung ohne Übergangsrahmen; Elementliste ohne Übergangsblock-Ausnahmen.

## Test Plan

### Automated Tests (TDD RED)

- [ ] Unit (`node --test`): Karte zeigt beide Schalter im Kontext `route`, nicht im Kontext `vergleich`; Startwert fehlend = an; bei Kompakt gesperrt mit Hinweis.
- [ ] Unit (`node --test`): `felderNutzlast` erzeugt Teilfeld-Nutzlast nur mit dem geänderten Schlüssel.
- [ ] Unit (`node --test`): Katalog DE/EN enthält die neuen Keys, `zustellung.uebergang.*` fehlt; Pin-Test ergänzt.
- [ ] Unit (`node --test`): Reiter Zustellung rendert kein `zustellung-uebergang`, aber Beispiel-Alarm-Abschnitt und (Orte) Aktivierungs-Abschnitt unter dem Kopf.
- [ ] pytest: Placements-GET `blocks` enthält `show_compact_summary` und `show_stability` (gesetzt und fehlend = true).
- [ ] pytest/Go-nahe Prüfung gegen Staging-API: Teilfeld-PUT erhält übrige `report_config`-Felder inkl. der vier Altfelder; zweiter Nutzer unberührt.
- [ ] Playwright E2E (Staging): Schalter umlegen, Mail zustellen, `briefing_mail_validator` prüft HTML und Text.
- [ ] Elementlisten-Abgleich `--scope zustellung --abnahme` DE und EN mit Prüfkonto.

## Acceptance Criteria

- **AC-1:** Given ein Trip-Hub mit geöffnetem Reiter Wetter / When die Karte „Was steht wo“ unter „Ganze Blöcke ein- und ausschalten“ betrachtet wird / Then erscheinen zwei zusätzliche Schalter Kurz-Zusammenfassung und Großwetterlage (`was-steht-wo-show_compact_summary`, `was-steht-wo-show_stability`) mit dem Startwert aus der gespeicherten report_config (fehlendes Feld = an), und beim Orts-Vergleich sind sie nicht sichtbar.
  - Test: Unit `node --test` (Karte, Kontext route/vergleich, fehlendes Feld) und Playwright E2E gegen Staging (Trip sichtbar, Ortsvergleich nicht).

- **AC-2:** Given ein Trip mit gespeicherter report_config inkl. weiterer Felder / When der Nutzer einen der beiden neuen Schalter umlegt / Then wird nur das geänderte Feld per Teilfeld-PUT gespeichert, alle anderen report_config-Felder (auch die vier Altfelder) bleiben unverändert erhalten, und die Daten eines zweiten Nutzers bleiben unberührt.
  - Test: pytest/API gegen Staging mit zwei verschiedenen Nutzern (Vorher/Nachher-Vergleich der report_config) und Unit `node --test` auf die Teilfeld-Nutzlast.

- **AC-3:** Given eine zugestellte ausführliche Trip-Mail / When Kurz-Zusammenfassung bzw. Großwetterlage ausgeschaltet ist / Then enthalten HTML- und Text-Teil der Mail den jeweiligen Block nicht, und bei eingeschaltetem Schalter enthalten sie ihn.
  - Test: Playwright E2E gegen Staging mit echt zugestellter Mail im Stalwart-Testpostfach, geprüft über `briefing_mail_validator`.

- **AC-4:** Given ein Trip mit E-Mail-Format Kompakt / When die Karte „Was steht wo“ angezeigt wird / Then sind beide neuen Schalter gesperrt und zeigen den vorhandenen Hinweis „nur ausführlich“ wie die übrigen Block-Schalter.
  - Test: Unit `node --test` (gesperrter Zustand, Hinweistext) und Playwright E2E gegen Staging.

- **AC-5:** Given ein Trip mit gespeicherter oder fehlender report_config / When die Placements-GET `blocks` liefert / Then enthält die Antwort `show_compact_summary` und `show_stability` (fehlend = true).
  - Test: pytest gegen `placements_view_service` mit echten Trip-Daten, ohne Mocks.

- **AC-6:** Given Sprache Deutsch oder Englisch am Nutzer / When die zwei neuen Schalter angezeigt werden / Then erscheinen Titel und Hinweis in der Nutzersprache aus dem i18n-Katalog (ADR-0104), ohne feste Texte in der Komponente.
  - Test: Unit `node --test` (Katalog-Vollständigkeit DE/EN, Pin-Test) und Playwright E2E mit EN-Nutzer.

- **AC-7:** Given der Reiter Zustellung eines Trips oder Orts-Vergleichs / When er geöffnet wird / Then gibt es keinen Block „Vorübergehend hier“ mehr (testid `zustellung-uebergang` und Keys `zustellung.uebergang.*` entfallen), der Beispiel-Alarm steht als eigener Abschnitt am Ende (Trip und Orte), und die Pausieren/Aktivieren-Karte der Orte steht als fester Abschnitt direkt unter dem Kopf (Hub und Anlegen) und ist wie bisher bedienbar.
  - Test: Playwright E2E gegen Staging (Abschnitte sichtbar, Pausieren/Aktivieren umschaltbar) und Unit `node --test` (Katalog ohne `zustellung.uebergang.*`).

- **AC-8:** Given der Teststand nach der Auflösung / When die Frontend-Tests laufen / Then fehlen die zwei veralteten E2E-Specs (`alarm-ab-nur-lesbar.spec.ts`, `s3a2794-zustellung-inventar-speicherweg.spec.ts`), und alle übrigen Tests mit früherem `zustellung-uebergang` laufen gegen die neuen testids grün.
  - Test: `node --test` der nachgezogenen Unit-Tests und Playwright-Lauf der nachgezogenen E2E-Specs gegen Staging (Verhalten, kein Dateiinhalt-Check).

- **AC-9:** Given die Elementliste für den Reiter Zustellung / When der Abgleich `--scope zustellung --abnahme` mit dem Prüfkonto gegen Staging läuft / Then ist er für DE und EN grün, und `elementliste_besitzer.json` enthält keine Übergangsblock-Ausnahmen (#2795, art zusaetzlich, Grund „Übergangsblock …“) mehr.
  - Test: `npm run elementliste:abgleich -- --scope zustellung --abnahme` in DE und EN mit Prüfkonto und Seed-IDs, Exit 0.

- **AC-10:** Given gespeicherte Werte von `show_quick_take_tags`, `show_metrics_summary`, `show_highlights`, `daily_summary_metrics` und SMS-Schwellen / When ein Nutzer im Hub Einstellungen ändert und speichert / Then erscheint dafür keine neue Oberfläche, und die gespeicherten Werte bleiben unverändert erhalten.
  - Test: pytest/API gegen Staging (Werte vor und nach einem Schalter-PUT identisch) und Playwright E2E (kein Bedienelement für diese Felder im Hub).

## Definition of Done

- AC-1 bis AC-10 durch Kern-Tests (`node --test`, pytest, ohne Mock-Theater) und E2E grün; die neuen Schalter und der fehlende Übergangsrahmen zuerst rot nachgewiesen.
- Bestehende Tests mit `zustellung-uebergang` angepasst und grün; Ratsche `context_herkunft_zweige_eingefroren` und Wächterliste ohne neue Verstöße.
- Staging: Prüfkonto schaltet Kurz-Zusammenfassung und Großwetterlage aus und wieder an, zugestellte Mail per `briefing_mail_validator` geprüft; zweiter Nutzer unberührt; Elementlisten-Abgleich Zustellung DE+EN grün.
- Live auf Produktion, Selftest Exit 0. Keine Änderung an Gate-Konfiguration.

## Known Limitations

- Telegram druckt `WL:` unabhängig von `show_stability`, die Kompakt-Mail wertet beide Felder nicht aus. Der Hinweistext macht das sichtbar; Angleichung ist Nebenbefund (#1199), nicht Teil dieses Issues.
- Alt-Bausteine, `telegram_kurzform` und `sms_schwellen`-Abschnitt werden mit #3020 gelöscht, nicht hier.
- Die neuen Schalter gehen bewusst über das Soll-Bild `mockup-hub-fassung4.html` (Fassung 4) hinaus (PO-Entscheidung 2026-11-24).
- Pausieren/Aktivieren und Beispiel-Alarm sind Übergangsplätze bis #2797 (Hub-Kopf: Kebab bzw. „Test schicken“).
- Mail-Inhalt ändert sich nicht, nur die Bedienstelle; das Renderer-Gate ist voraussichtlich nicht berührt.

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** keine neue; berührt ADR-0124 (Was steht wo, Frage gehört zu #3036), ADR-0101 (Merge), ADR-0095, ADR-0104.
- **Rationale:** Bestehende Muster werden um zwei Einträge erweitert; keine Entscheidungsfläche wird geändert.

## Changelog

- 2026-11-24: Initial spec created
