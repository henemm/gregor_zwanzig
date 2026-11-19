---
entity_id: feat_3155_ein_name_ausblick
type: feature
created: 2026-11-19
updated: 2026-11-19
status: draft
version: "1.0"
workflow: feat-3155-ein-name-ausblick
tags: [ausblick, i18n, kanaele, orte, trip, epic-3122]
---

# Was steht wo B4: ein Name „3-Tages-Ausblick“, eine steuernde Stelle (Issue #3155, Epic #3122)

## Approval

- [ ] Approved

> Der Fachinhalt wurde am 17.11.2026 in `docs/specs/modules/feat_3122_was_steht_wo.md` freigegeben (Scheibe B4 = AC-8, AC-9, AC-12, AC-34; Teil A Nr. 6 und Nr. 8; Teil B Nr. 13 und Nr. 15; ADR-0124 Nr. 6, ADR-0055 Nr. 2, ADR-0104). Diese Spec zitiert jene ACs, ändert sie nicht und legt nur fest, wie B4 gebaut und nachgewiesen wird. Die eigenen ACs unten (AC-1 bis AC-13) machen die Ober-Spec-ACs prüfbar; sie erfinden keinen neuen Fachinhalt.

## Purpose

Der 3-Tages-Ausblick heißt in jeder Ausgabe und in der Oberfläche gleich („3-Tages-Ausblick“, EN „3-day outlook“) und wird von genau einer Stelle gesteuert, die in HTML-Mail, Nur-Text-Mail, Kompakt-Mail und Telegram gleich wirkt, für Trip und Orte und auch für Abos, die noch keine Tabelle „Was steht wo“ haben. Behoben wird dabei, dass der Ausblick-Schalter in Telegram und Kompakt-Mail nicht wirkt, dass der Block an vier Stellen anders heißt und dass die Trip-Anlage mit der Karte „Mehrtages-Trend“ eine zweite steuernde Stelle neben der Karte „Was steht wo“ hat.

## Source

- **File:** `src/services/report_config_resolver.py`, `src/services/channel_list_resolver.py`, `src/services/placements.py`, `src/output/renderers/email/{html,plain,compact,outlook,outlook_state_hint,compare_html}.py`, `src/output/renderers/{narrow,comparison}.py`, `internal/handler/compare_preset.go`, Frontend `versand-tab/`, `trip-new/`, `MailInhaltCard`
- **Identifier:** `_options_bisher`, `resolve_channel_lists`/`_abo_schalter`, `_legacy_outlook_reports`, `CreateComparePresetHandler`, Katalog-Schlüssel `mail.ausblick.*`, `telegram.kopf.ausblick`, `vergleich.ausblick.*`

## Scope

Scheibe B4 der Epic-Spec (Bau-Tabelle Zeile B4). Gebaut werden: die Steuerung des Ausblicks über eine Stelle auch im Altbestand, die Vorbelegung bei der Anlage (Trip und Orte), der Name in allen Ausgaben und Katalogen, der Wegfall der Karte „Mehrtages-Trend“, die erweiterten Falllisten und beide Mail-Validatoren.

Kanäle: Betroffen sind E-Mail (HTML, Nur-Text, Kompakt) und Telegram. SMS und Premium-SMS enthalten keinen 3-Tages-Ausblick (die SMS- und Premium-SMS-Renderer lesen weder `outlook` noch `multi_day_trend_reports`) und bleiben unverändert; die Kanal-Parität (ADR-0095) ist davon nicht berührt, weil der Ausblick dort heute schon fehlt und diese Scheibe daran nichts ändert.

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `docs/specs/modules/feat_3122_was_steht_wo.md` | Spec | Verbindliche, freigegebene ACs 8, 9, 12, 34 |
| ADR-0124 Nr. 6, ADR-0055 Nr. 2, ADR-0104 | ADR | Eine steuernde Stelle; Katalog-Texte DE/EN |
| `src/services/placements.py` (`resolve_outlook_reports`, `outlook_applies`, `_legacy_outlook_reports`) | module | Eine Regel für Vorbelegung und Umrechnung (B1) |
| `WasStehtWoKarte` und Endpoint `PUT /api/briefings/{id}/placements` (B2/B3, #3154) | module | Die Karte schreibt `outlook_reports`; bleibt unverändert |
| `feat_3153_name_orte_ausliefern.md` (B5, #3153) | Spec | Name „Orte“ in den Köpfen; B4 fasst diese Texte nicht an |
| `docs/reference/i18n_konventionen.md` | Doku | Katalog, Protokoll-Token nie übersetzen |
| `.claude/hooks/briefing_mail_validator.py`, `email_spec_validator.py`, `_soll_aus_konfiguration.py` | hook | Nachweis an echt zugestellten Staging-Mails |
| Nachfolger B6 (#3157) | Scheibe | Globale Umstellung des Altbestands, Altfelder entfernen |

## Implementation Details

### Entscheidungen des Tech Leads

1. **Eine Stelle auch ohne Tabelle (Variante A, minimal).** In `_options_bisher`, nur im Zweig mit `report_config`, gilt `show_multi_day_trend = report_type in _legacy_outlook_reports(...)`. Das ist dieselbe Funktion, die die Umrechnung des Altbestands (Nr. 8) benutzt, samt ihrer Kompakt-Ausnahme. `show_outlook` steuert damit nur noch die Großwetterlage. Der Zweig ohne `report_config` (`dc.multi_day_trend_reports or ["evening"]`) bleibt unverändert, sonst würde ein stiller Randfall mit leerer Liste die Ausgabe ändern. Verworfen: `ALTBESTAND_UEBER_UMRECHNUNG = True` (zieht B6 hinein, ändert Reihenfolge und Formate aller Bestands-Abos) und Kompakt/Telegram lesen `show_outlook` selbst (widerspricht Nr. 6).
2. **Bewusste Ausgabeänderung, im Changelog und in der Abnahme (#3037) zu nennen:** Ein Trip ohne Tabelle mit `show_outlook: false` und Format „ausführlich“ zeigt in Telegram keinen Ausblick mehr (bisher zeigte Telegram ihn trotz ausgeschaltetem Schalter). Ein Trip mit `outlook_metrics: []` zeigt den Ausblick in keiner Ausgabe mehr. Ein Trip im Kompakt-Format behält den Ausblick nach `multi_day_trend_reports`, denn dort war der Schalter gesperrt (AC-12 der Ober-Spec). Die Orte-Ausgabe im Altpfad entscheidet schon über eine Stelle und ändert sich dadurch nicht.
3. **Abgrenzung zu B6 (#3157):** Kein Umschalten von `ALTBESTAND_UEBER_UMRECHNUNG`, keine Entfernung von `show_outlook`, `multi_day_trend_reports`, `outlook_enabled` aus Datenmodell oder Bestandsdaten. Nur der Kommentar zu `ALTBESTAND_UEBER_UMRECHNUNG` wird korrigiert (er verweist auf B3, gehört zu B6).
4. **Vorbelegung bei der Anlage (AC-9), Trip.** Die Karte „Mehrtages-Trend“ in `VTSchedulePlan.svelte` entfällt samt ihrer Testids und ihrer Haken. `baueReportConfigPayload` und `tripNewLogic` schreiben `multi_day_trend_reports` nach der Regel aus Nr. 6: `["morning"]`, wenn allein das Morgen-Briefing eingeschaltet ist, sonst `["evening"]`; ein vorhandener Wert gewinnt. Es bleibt bei dem bisherigen Altfeld, weil die Trip-Anlage heute keine Tabelle schreibt (Tabelle beim Anlegen ist #3041).
5. **Vorbelegung bei der Anlage (AC-9), Orte. Entscheidung zu Frage 2a.** Ein neues Orte-Abo hat kein Altfeld, das die Briefings unterscheidet; im Altpfad stünde der Ausblick in jedem eingeschalteten Briefing, und Bestands-Abos mit `outlook_enabled: true` müssen genau so bleiben (AC-12, Nr. 8). Neu und Bestand sind deshalb nur durch eine Marke unterscheidbar, die die Anlage schreibt. Orte entscheidet die Anlage serverseitig in `CreateComparePresetHandler` (Go), unmittelbar nach den Neu-Preset-Defaults der Slot-Felder (dort stehen Morgen/Abend-Schalter fest). Sie legt `display_config.placements = {"version": 1, "outlook_reports": [...]}` an, wenn der Client keine `placements` mitgeschickt hat, mit der Regel aus Nr. 6 (nur Morgen an: `["morning"]`, sonst `["evening"]`). Bewusst ohne `rows`: eine Tabelle mit `rows` würde die im Anlege-Assistenten gewählten Altfelder (Ausblick-Metriken und -Formate, `channel_layouts`) überschreiben, weil dann der neue Eingang gilt. Ohne `rows` bleibt das Abo im Altpfad (`read_placements` liefert `None`), und nur der Ausblick wird gesteuert. Der Python-Kern liest die Marke an einer Stelle: eine kleine Funktion in `placements.py` liefert `outlook_reports` aus `display_config.placements`, auch ohne `rows`; `_abo_schalter` (Ausgabe) und `_legacy_outlook_reports` (Umrechnung, also auch die Tabellen-Antwort der Karte) lesen sie, und beide gehen durch `resolve_outlook_reports`. Damit zeigen Ausgabe und Karte dasselbe. Das erste Speichern der Karte ersetzt `placements` vollständig (B2) und trägt `outlook_reports` mit; die Marke geht nicht verloren. B6 muss die Marke bei der Migration lesen (Vermerk in Known Limitations). Verworfen: Schreiben im Frontend (Python-seitige und künftige Clients wären nicht abgedeckt, Regel doppelt im TypeScript) und `rows: []` (siehe oben).
6. **Ein Name (Katalog).** `mail.ausblick.eyebrow`, `mail.ausblick.titel`, `telegram.kopf.ausblick` und `vergleich.ausblick.eyebrow` zeigen auf „3-Tages-Ausblick“ / „3-day outlook“ (Großschreibung der Eyebrow wie bisher durch den Renderer). `vergleich.ausblick.titel` ist schon richtig. Neuer Schlüssel `mail.ausblick.name` ersetzt `mail.ausblick.naechste_etappen` als Blocktitel in Nur-Text-Mail (`plain.py`), Kompakt-Mail (`compact.py`, ASCII über `_ascii`) und Trip-Ausblick (`outlook.py`); `naechste_etappen` entfällt. Der tote Hardcode `OUTLOOK_HEADING` in `compare_html.py` entfällt. Unberührt bleiben `mail.outlook_state.*` (Großwetterlage), `mail.ausblick.spalte_tag` und alle Protokoll-Token.
7. **Oberfläche (Nr. 15).** `wertebereiche.ausblick.titel` („3-Tages-Vorschau“) wird „3-Tages-Ausblick“ / „3-day outlook“; `wertebereiche.schwelle.hinweis` („Ausblick/Trend-Block“) nennt den Block mit dem einen Namen; `versand.zeitplan.trend` und `versand.zeitplan.trend_sub` entfallen mit der Karte (die falsche Unterzeile „3–7-Tage-Ausblick“ verschwindet mit).
8. **Haken „Ausblick“ in der Karte „E-Mail-Inhalt“. Entscheidung zu Frage 2b.** `layout.mail_inhalt.ausblick` ist noch sichtbar: `MailInhaltCard` ist im Trip-Editor eingebunden (Reiter Wetter im Bearbeiten, `WeatherMetricsTab`, und `TripNewEditor`), und der Haken `report-show-outlook` trägt den Namen „Ausblick“ samt Text „Großwetterlage-Kopf, nächste Etappen …“. Nach Nr. 15 darf „Ausblick“ nicht als Blocktitel eines anderen Dings stehen, und nach B4 steuert `show_outlook` nur noch die Großwetterlage. Darum bekommt dieser Haken den Namen und Text der Großwetterlage: `BAUSTEIN_TEXTE.show_outlook` zeigt auf die vorhandenen Schlüssel `layout.mail_inhalt.grosswetterlage` und `…_text`; `layout.mail_inhalt.ausblick` und `…_text` entfallen. Orte mountet diese Karte nie (Wächtertest `mail_inhalt_rueckbau_waechter`), dort ist nichts zu ändern.

9. **Klarstellung aus TDD RED: Vorbelegung Trip nur bei der Anlage.** Die Regel aus Nr. 4 gilt nur für einen neu angelegten Trip. Beim Speichern eines bestehenden Trips setzt das Frontend `multi_day_trend_reports` nie neu: ein gespeicherter Wert bleibt, ein fehlendes Feld bleibt wie vor B4 (sonst bekäme ein Bestands-Trip mit nur Morgen-Briefing still einen Ausblick am Morgen, Widerspruch zu AC-13). Der Anlagepfad des Versand-Reiters (Trip-Anlage) wendet die Regel an, der Speicherpfad des Bearbeitens nicht; unterscheiden lässt sich das daran, ob ein gespeicherter `report_config` vorliegt (Paritätstest Anlage mit Standardwerten = Anlage durch alle Reiter).
10. **Klarstellung aus TDD RED: Orte-Anlage mit ausgeschaltetem Ausblick.** Schickt die Anlage `outlook_enabled: false`, schreibt `CreateComparePresetHandler` die Marke mit `outlook_reports: []` (leere Liste = aus, ADR-0124 Nr. 6); die Morgen/Abend-Regel aus Nr. 5 gilt nur bei eingeschaltetem oder fehlendem `outlook_enabled` (AC-8: die Wahl im Anlege-Assistenten bleibt wirksam).

### Reihenfolge

1. Backend-Weiche (Entscheidung 1) samt Orte-Marke (Entscheidung 5, Python-Teil) und Tests. 2. Katalognamen und Goldens. 3. Falllisten, Treiber, Validatoren. 4. Go-Anlage Orte, Frontend (Karte weg, Vorbelegung Trip, Kataloge, Haken-Name, E2E). 5. Modus-Matrix, Validator-Lauf DE und EN auf Staging.

## Expected Behavior

- **Input:** Trip oder Orte-Abo (mit oder ohne Tabelle), Briefing Morgen oder Abend, Nutzersprache DE oder EN.
- **Output:** Der Ausblick steht in einem Briefing genau dann, wenn dieses Briefing in der einen Stelle (`outlook_reports`, im Altbestand über `_legacy_outlook_reports`) steht; in allen vier Ausgaben gleich; der Block heißt überall „3-Tages-Ausblick“ / „3-day outlook“.
- **Side effects:** Neue Orte-Abos tragen `display_config.placements` ohne `rows` (nur `outlook_reports`); neue Trips tragen `multi_day_trend_reports`; sonst keine Datenänderung.

## Acceptance Criteria

- **AC-1:** Given ein Trip mit 3-Tages-Ausblick nur im Abend-Briefing, einmal mit Tabelle und einmal ohne Tabelle (Altbestand), in Deutsch und Englisch / When das Morgen- und das Abend-Briefing als HTML-Mail, Nur-Text-Mail, Kompakt-Mail und Telegram erzeugt werden / Then steht der Ausblick abends in jeder der vier Ausgaben und morgens in keiner. (Ober-Spec AC-8)
  - Test: Fallliste `fallliste_trip.json`, Fälle `trip-paar-ausblick-*` mit Feld `briefing` (morning/evening), Feld `sprache` und Format `telegram`; Treiber `test_einstellung_gleich_mail_trip.py`.

- **AC-2:** Given ein Orte-Abo mit 3-Tages-Ausblick nur im Abend-Briefing, in Deutsch und Englisch / When das Morgen- und das Abend-Briefing als HTML-Mail, Nur-Text-Mail und Telegram erzeugt werden (Orte kennt keine Kompakt-Mail) / Then steht der Ausblick abends in jeder dieser Ausgaben und morgens in keiner. (Ober-Spec AC-8)
  - Test: Fallliste `fallliste_orte.json`, Fälle `O-AB-*` mit `briefing`, `sprache` und Format `telegram`; Helper `sende_orte_mail` mit Briefing-Typ und Telegram-Mitschnitt.

- **AC-3:** Given ein Trip und ein Orte-Abo, bei denen Morgen- und Abend-Schalter des Ausblicks beide ausgeschaltet sind (Tabelle mit `outlook_reports: []`; Trip ohne Tabelle mit `show_outlook: false`) / When Morgen- und Abend-Briefing erzeugt werden / Then steht der Ausblick in keiner Ausgabe, auch nicht in Telegram, und ein Trip im Kompakt-Format ohne Tabelle behält ihn nach seinem bisherigen Wert (dort war der Schalter gesperrt). (Ober-Spec AC-8 und AC-12)
  - Test: Fälle `trip-ausblick-aus--*` und `O-AB-*` aus, alle Briefings und Ausgaben, DE und EN; Telegram-Fall für `show_outlook: false` ist der Beleg der bewussten Ausgabeänderung.

- **AC-4:** Given Bestands-Trips ohne Tabelle mit `show_outlook: false`, mit `outlook_metrics: []` und mit Ausblick morgens und abends, und ein Orte-Abo mit `outlook_enabled: false` / When Briefings zugestellt werden / Then steht der Ausblick bei den ersten beiden und beim Orte-Abo nirgends, beim dritten in beiden Briefings, und die Umrechnung der Karte „Was steht wo“ zeigt dieselben Schalter. (Ober-Spec AC-12)
  - Test: Fallliste je Fall plus Backend-Test, der Ausgabe und Tabellen-Antwort (`placements_view_service`) vergleicht.

- **AC-5:** Given ein Bestands-Trip ohne Tabelle mit `show_outlook: false` und ausführlichem Mail-Format / When die HTML-Mail und die Nur-Text-Mail erzeugt werden / Then steht keine Großwetterlage in der Mail, und ein Bestands-Trip mit `show_outlook: true` zeigt sie weiterhin. (Ober-Spec AC-12, letzter Halbsatz)
  - Test: Fall in `fallliste_trip.json` (Großwetterlage vorhanden/nicht vorhanden je Schalterstand), Prüfung auf die Großwetterlage-Zeile der zugestellten Mail.

- **AC-6:** Given der Reiter Wetter eines Trips / When der Nutzer die Karte „E-Mail-Inhalt“ ansieht / Then trägt der bisherige Haken „Ausblick“ den Namen „Großwetterlage“ (EN „Weather pattern“), und nirgends in der Karte steht „Ausblick“ als Name eines Bausteins. (Ober-Spec AC-34, Oberfläche)
  - Test: Frontend `node --test` über `mailInhaltBausteine()` in beiden Sprachen und E2E auf Staging (sichtbarer Haken-Text).

- **AC-7:** Given ein neu angelegter Trip ohne gespeicherte Ausblick-Einstellung / When er mit Morgen- und Abend-Briefing angelegt wird und danach in einem zweiten Fall nur mit eingeschaltetem Morgen-Briefing / Then steht der Ausblick im ersten Fall nur im Abend-Briefing und im zweiten Fall im Morgen-Briefing, die Karte „Mehrtages-Trend“ erscheint in der Anlage nicht mehr, und die Karte „Was steht wo“ zeigt die Schalter genauso. (Ober-Spec AC-9 und AC-34)
  - Test: Frontend `node --test` für Nutzlast der Anlage (`standardwerte_payload_paritaet_trip.test.ts` angepasst, beide Fälle), zugestellte Briefings je Fall in der Fallliste, E2E der Anlage ohne Karte „Mehrtages-Trend“.

- **AC-8:** Given ein neu angelegtes Orte-Abo ohne gespeicherte Ausblick-Einstellung / When es mit Morgen- und Abend-Briefing angelegt wird und danach in einem zweiten Fall nur mit eingeschaltetem Morgen-Briefing / Then steht der Ausblick im ersten Fall nur im Abend-Briefing und im zweiten Fall im Morgen-Briefing, die im Anlege-Assistenten gewählten Ausblick-Metriken und -Formate bleiben unverändert wirksam, und die Karte „Was steht wo“ zeigt die Schalter genauso. (Ober-Spec AC-9)
  - Test: Go-Handlertest für `POST /api/compare/presets` (beide Fälle, mitgeschickte `placements` bleiben unangetastet), Python-Test Ausgabe plus Tabellen-Antwort je Fall, Fallliste `O-AB-*` mit Anlage-Marke.

- **AC-9:** Given zwei verschiedene Nutzer, die je ein Orte-Abo anlegen, einer nur mit Morgen-Briefing / When beide Abos gelesen werden / Then trägt jedes Abo nur seine eigene Vorbelegung, und kein Abo enthält Daten des anderen. (Ober-Spec AC-9, Mandantentrennung)
  - Test: Go-Handlertest mit zwei Nutzern (`WithUser`, echte `user_id` aus dem Auth-Kontext).

- **AC-10:** Given ein Trip und ein Orte-Abo mit eingeschaltetem Ausblick / When das Briefing als HTML-Mail, Nur-Text-Mail, Kompakt-Mail und Telegram zugestellt wird (Orte ohne Kompakt), in Deutsch und Englisch / Then heißt der Block in jeder Ausgabe „3-Tages-Ausblick“ bzw. „3-day outlook“, in der Kompakt-Mail in ASCII-Schreibweise, und der Zustandshinweis zum Ausblick trägt denselben Namen. (Ober-Spec AC-34)
  - Test: Namensfall in den Falllisten (Katalogwert positiv, DE und EN, alle Ausgaben) und Kern-Test auf den Blocktitel jeder Ausgabe.

- **AC-11:** Given dieselben zugestellten Ausgaben und die Kataloge in Deutsch und Englisch / When nach den Wörtern „Mehrtages-Trend“, „3-Tages-Vorschau“, „Nächste Etappen“ (EN „Next stages“) und „Ausblick“ als alleinigem Blocktitel gesucht wird / Then kommt keines davon als Name des Ausblick-Blocks oder einer Oberflächen-Beschriftung vor; „Großwetterlage“ und der Wortlaut „Ausblick im Morgen-/Abend-Briefing“ in der Karte „Was steht wo“ bleiben erlaubt. (Ober-Spec AC-34)
  - Test: Negativfall in den Falllisten über die gerenderten Ausgaben (HTML, Nur-Text, Kompakt, Telegram; DE und EN); Oberfläche über die gerenderten Komponenten (Frontend `node --test` der Karten im Wetter- und Versand-Reiter sowie `mailInhaltBausteine()`) und die E2E-Durchsicht auf Staging. Keine Suche im Dateiinhalt der Kataloge als Verhaltensnachweis (Test-Politik).

- **AC-12:** Given echt zugestellte Staging-Mails eines Trips und eines Orte-Abos, je Morgen- und Abend-Briefing, in Deutsch und Englisch / When `briefing_mail_validator.py` (Trip) und `email_spec_validator.py` (Orte) mit `--konfig` prüfen / Then prüfen beide, dass der Block „3-Tages-Ausblick“ heißt und dass der Ausblick nur in dem Briefing steht, in dem er eingestellt ist, und beide enden mit Exit 0 („E2E bestanden“). (Ober-Spec AC-34 und AC-8)
  - Test: Validator-Lauf auf Staging gegen das Stalwart-Test-Postfach; der Soll-Wert kommt aus einer Regel in `_soll_aus_konfiguration.py` (Tabelle über `resolve_outlook_reports`/`outlook_applies`, sonst `_legacy_outlook_reports`), nicht aus Altfeldern.

- **AC-13:** Given ein Bestands-Abo ohne Tabelle (Trip und Orte) / When B4 ausgeliefert ist / Then ändert sich seine Ausgabe nur dort, wo AC-3, AC-4 oder AC-5 es ausdrücklich verlangen; Reihenfolge, Formate und alle übrigen Blöcke bleiben, und die Daten des Abos sind unverändert. (Ober-Spec AC-12, Nr. 8 Bestand)
  - Test: Differenzfälle der Fallliste für Bestandsfälle ohne Änderungswunsch (Ausgabe vor und nach B4 gleich); kein Test schreibt Bestandsdaten.

## Definition of Done

- AC-1 bis AC-13 durch benannte Tests bzw. beide Mail-Validatoren grün (DE und EN, Morgen und Abend); Adversary mit Mutations-Gegenprobe ohne offenen Befund.
- Kein Text in Oberfläche, Mail oder Telegram sagt mehr „Mehrtages-Trend“ oder „3-Tages-Vorschau“; die Karte „Mehrtages-Trend“ ist aus der Trip-Anlage entfernt.
- Alle sechs CI-Checks grün, Staging-Verifikation mit echt zugestellten Mails, Prod-Deploy, Prod-Selftest Exit 0.
- `renderer_email_spec.md` und `telegram_format.md` tragen den neuen Blocknamen.

## Test Plan

### Automated Tests (TDD RED)

- [ ] Falllisten `fallliste_trip.json` und `fallliste_orte.json` um die Felder `briefing` (morning/evening), `sprache` (de/en) und das Format `telegram` erweitern; Fälle je Briefing × Ausgabe × Sprache für `trip-paar-ausblick-*`, `trip-ausblick-aus--*` (Altpfad `show_outlook` und Tabelle mit `outlook_reports: []`), `O-AB-*`; Namensfall positiv und negativ. Erwartung vor dem Bau: rot (Telegram bei `show_outlook: false`, alter Name, Orte-Morgen/Abend).
- [ ] Treiber `test_einstellung_gleich_mail_trip.py`, `test_einstellung_gleich_mail_orte.py` und Helper `tests/helpers/einstellung_gleich_mail_orte.py` (`sende_orte_mail` mit Briefing-Typ und Telegram-Mitschnitt), `_einstellung_gleich_mail_trip_fixtures.py`; Muster: `*_tabelle.py` (`_ausblick_ueberall`, `telegram_bubbles`). Alle Fälle gehen durch die echten Renderer und Resolver, kein Mock.
- [ ] Backend: GIVEN Bestands-Trip mit `show_outlook: false`, Format „ausführlich“ WHEN `resolve_report_render_options` für beide Briefings THEN `show_multi_day_trend` aus; im Kompakt-Format unverändert (AC-3, AC-4).
- [ ] Backend: GIVEN Orte-Abo mit `placements` ohne `rows` und `outlook_reports: ["evening"]` WHEN Ausgabe und Tabellen-Antwort erzeugt werden THEN zeigen beide den Ausblick nur abends, und der Altpfad (Auswahl, Formate) bleibt (AC-8).
- [ ] Go: `POST /api/compare/presets` schreibt die Marke nach Nr.-6-Regel, lässt mitgeschickte `placements` unangetastet, Zwei-Nutzer-Test (AC-8, AC-9).
- [ ] Frontend `node --test`: Nutzlast der Anlage Trip (`standardwerte_payload_paritaet_trip.test.ts`, `report_config_serialisierung_golden.test.ts`, `merge_report_config_read_modify_write.test.ts`) ohne Trend-Karte und mit Vorbelegung beider Fälle; Katalog-Tests (`f8KatalogAnker.ts`, `de_katalog_vor_i18n.json`, Anker für `versand`, `wertebereiche`, `layout`); `mailInhaltBausteine()` (AC-6, AC-7, AC-11).
- [ ] E2E (Playwright, Staging): `issue-88`, `standardwerte-und-hilfe`, `s3a2794`, `was-steht-wo-karte` ohne „Mehrtages-Trend“ und ohne die `report-*-trend`-Testids; Anlage ohne Karte.
- [ ] Goldens/Fixtures (`trip_briefing_aufbau`, `outlook_trip_parity`, f5/f6/f8/f9) maschinell neu erzeugt, je Datei Diff-Prüfung: nur Namenswechsel.
- [ ] Staging: `briefing_mail_validator.py --konfig` (Trip) und `email_spec_validator.py --konfig` (Orte) gegen echt zugestellte Mails, Morgen und Abend, DE und EN (AC-12).
- [ ] Mutations-Gegenprobe (Adversary): Telegram liest wieder `show_outlook`; `outlook_reports` wirkt in einer Ausgabe nicht; Anlage Orte schreibt immer `["evening"]`; alter Blocktitel in Kompakt zurück; Marke ohne `rows` wird ignoriert. Jede Verfälschung muss ein Test fangen.

## Affected Files

| File | Change Type | Description |
|------|-------------|-------------|
| `src/services/report_config_resolver.py` | MODIFY | Altpfad-Ausblick über `_legacy_outlook_reports` (Entscheidung 1) |
| `src/services/placements.py` | MODIFY | Lesefunktion für `outlook_reports` ohne `rows`; `_legacy_outlook_reports` liest sie für Orte |
| `src/services/channel_list_resolver.py` | MODIFY | `_abo_schalter` wendet die Marke an; Kommentar B3 auf B6 korrigiert |
| `internal/handler/compare_preset.go` (+ Test) | MODIFY | Orte-Anlage schreibt `outlook_reports`-Marke nach Nr.-6-Regel |
| `src/i18n/messages/{de,en}/{mail,telegram,vergleich}.json` | MODIFY | Name, neuer Schlüssel `mail.ausblick.name`, `naechste_etappen` entfällt |
| `src/output/renderers/email/{outlook,plain,compact,html,outlook_state_hint,compare_html}.py`, `narrow.py`, `comparison.py` | MODIFY | Schlüsselwechsel, toten Hardcode `OUTLOOK_HEADING` entfernen |
| `frontend/src/lib/components/shared/versand-tab/VTSchedulePlan.svelte`, `VersandTab.svelte`, `reportConfigPayload.ts` | MODIFY | Karte „Mehrtages-Trend“ entfernen |
| `frontend/src/lib/components/trip-new/tripNewLogic.ts` | MODIFY | Vorbelegung `multi_day_trend_reports` nach Nr.-6-Regel |
| `frontend/src/lib/components/shared/mailInhaltKonstanten.ts` | MODIFY | Haken `show_outlook` trägt Großwetterlage-Texte |
| `frontend/src/lib/i18n/messages/{de,en}/{versand,wertebereiche,layout}.json` | MODIFY | Namen, `trend`/`trend_sub` und `mail_inhalt.ausblick*` entfallen |
| `.claude/hooks/_soll_aus_konfiguration.py`, `briefing_mail_validator.py`, `email_spec_validator.py` | MODIFY | Soll über eine Regel, Blockname und „nur im eingestellten Briefing“ prüfen; Orte optional mit `--briefing` |
| `tests/fixtures/einstellung_gleich_mail/fallliste_{trip,orte}.json` | MODIFY | Felder `briefing`, `sprache`, Format `telegram`, Namensfälle |
| `tests/tdd/test_einstellung_gleich_mail_{trip,orte}.py`, `tests/helpers/einstellung_gleich_mail_orte.py`, `tests/tdd/_einstellung_gleich_mail_trip_fixtures.py` | MODIFY | Treiber und Helper um Briefing, Sprache, Telegram |
| `tests/tdd/test_ausblick_eine_stelle_3155.py` | CREATE | Backend-Weiche, Orte-Marke, Blockname in gerenderten Ausgaben (AC-3, AC-4, AC-8, AC-11) |
| Goldens/Fixtures (`trip_briefing_aufbau`, `outlook_trip_parity`, f5/f6/f8/f9, `de_katalog_vor_i18n.json`, KatalogAnker), Frontend-Tests, E2E-Specs (`issue-88`, `standardwerte-und-hilfe`, `s3a2794`, `was-steht-wo-karte`) | MODIFY | Namen, Karte, Vorbelegung nachziehen |

## Estimated Scope

- Files: ca. 25 Code/Test plus Goldens (mechanisch neu erzeugt)
- LoC: Code ca. +170/-80, Validatoren ca. +100, Tests ca. +300 (ohne Golden-Regeneration)
- Effort: medium

## Known Limitations

- Bei Abos mit Tabelle wirkt der Haken „Großwetterlage“ der Karte „E-Mail-Inhalt“ nicht (Großwetterlage hängt dort an `show_stability`, Nr. 6); die Überführung von `show_outlook` nach `show_stability` für alle Abos ist B6 (#3157).
- Die Orte-Marke (`placements` ohne `rows`) muss die Migration B6 lesen und in die volle Tabelle übernehmen; die Spec dazu ergänzt B6.
- Spätere Änderungen der eingeschalteten Briefings ändern eine gespeicherte Vorbelegung nicht (wie beim Trip mit `multi_day_trend_reports`); der Nutzer stellt sie in der Karte „Was steht wo“ um.

## Risiken

- **Renderer-Commit-Gate:** Mail-Inhalts-Commits blockieren, bis Modus-Matrix-Test und der zuständige Validator frisch grün sind; deshalb Reihenfolge 1 bis 5 und Validator-Lauf vor dem Mail-Inhalts-Commit.
- **Goldens:** viele Golden-Dateien ändern sich durch den Namen; jede Datei wird einzeln auf „nur Namenswechsel“ geprüft, keine blinde Regeneration.
- **Stille Änderung von Bestands-Abos:** nur die in Entscheidung 2 genannten; AC-13 sichert den Rest mit Differenzfällen.
- **Orte-Anlage:** Go-Änderung an einem datenbewegenden Endpoint; Zwei-Nutzer-Test (AC-9) ist Pflicht, mitgeschickte `placements` dürfen nie überschrieben werden.

## Out of Scope

- Umschalten des Altbestands auf die Umrechnung und Entfernen der Altfelder (B6, #3157).
- Tabelle „Was steht wo“ schon beim Anlegen (#3041).
- Name „Orte“ und Ein-Ort-Texte (B5, #3153); Reiter Orte, Menü, Listen (#2798).
- Änderung der Ober-Spec-ACs, Großwetterlage-Logik, `mail.outlook_state.*`, `spalte_tag`.

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** ADR-0124 (Nr. 6), ADR-0055 (Nr. 2), ADR-0104, bereits entschieden
- **Rationale:** B4 setzt die Entscheidung „eine steuernde Stelle“ und den einen Namen um. Die Orte-Marke und der Altpfad-Zweig sind Übergangsmittel bis B6 und ersetzen keine frühere Entscheidung; kein neues ADR nötig.

## Changelog

- 2026-11-19: Klarstellungen 9 und 10 aus TDD RED (keine AC-Änderung)
- 2026-11-19: Initial spec created (Scheibe B4 von #3122, Issue #3155; Entscheidungen zur Orte-Anlage und zum Haken in „E-Mail-Inhalt“ aus dem Quelltext)
